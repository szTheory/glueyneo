---
phase: 01-cpu-acceptance-experiment
reviewed: 2026-10-01T22:01:37Z
depth: standard
files_reviewed: 44
files_reviewed_list:
  - CMakeLists.txt
  - experiments/cpu/CMakeLists.txt
  - experiments/cpu/cpu_adapter.c
  - experiments/cpu/cpu_adapter.h
  - experiments/cpu/test_bus.c
  - experiments/cpu/test_bus.h
  - tests/cpu/guest_fixture.c
  - tests/cpu/guest_fixture.h
  - tests/cpu/isolation_fixture.h
  - tests/cpu/isolation_negative.py
  - tests/cpu/negative.py
  - tests/cpu/state_negative.py
  - tests/cpu/test_acceptance.py
  - tests/cpu/test_audit.py
  - tests/cpu/test_cold.c
  - tests/cpu/test_faults.c
  - tests/cpu/test_guest.c
  - tests/cpu/test_inventory.py
  - tests/cpu/test_isolation.c
  - tests/cpu/test_state.c
  - tests/cpu/test_timing.c
  - third_party/musashi/m68k.h
  - third_party/musashi/m68k_in.c
  - third_party/musashi/m68kconf.h
  - third_party/musashi/m68kcpu.c
  - third_party/musashi/m68kcpu.h
  - third_party/musashi/m68kmake.c
  - third_party/unity/src/unity.c
  - third_party/unity/src/unity.h
  - third_party/unity/src/unity_internals.h
  - tools/cpu/acceptance.py
  - tools/cpu/adapt.py
  - tools/cpu/audit.py
  - tools/cpu/record_attempt.py
  - tools/cpu/record_safety.py
  - tools/cpu/red.py
  - tools/cpu/state_inventory.py
  - experiments/cpu/evidence/recovery-accounting/classify.py
  - experiments/cpu/evidence/recovery-accounting/replay.py
  - experiments/cpu/evidence/recovery-accounting/tighten_core_semantics.py
  - experiments/cpu/evidence/recovery-accounting/stage-0/adapt.py
  - experiments/cpu/evidence/recovery-accounting/stage-1/adapt.py
  - experiments/cpu/evidence/recovery-accounting/stage-2/adapt.py
  - experiments/cpu/evidence/recovery-accounting/stage-3/adapt.py
findings:
  critical: 6
  warning: 2
  info: 0
  total: 8
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-10-01T22:01:37Z
**Depth:** standard
**Files Reviewed:** 44
**Status:** issues_found

## Summary

Three defects in the compiled 68000 instruction handlers invoke undefined C behavior on legal guest operands. Three additional defects affect the host opcode generator's argument and template handling. Historical budget validation and failed-attempt reproduction also have robustness defects. These findings contradict the earlier acceptance review's absence of blocking source findings; the submitted passing cases do not exercise the affected arithmetic and bit instructions.

Scope was reconciled from all four plan summaries, their corresponding plans, the source manifest, and the changes from the first summary's recorded `plan_head_before` (`3977c3bfbfdc752e1b43443aa3911c7012678177`) through the current checkout. Summary `key-files` lists alone omit source changes, including the acceptance collector. Generated `m68kops.c` and `m68kops.h` were excluded from the handwritten source count and inspected as supporting evidence that the affected template handlers reach the compiled runtime. Project instructions, oracle/provenance documents, state/source/fixture manifests, budget ledger, acceptance receipt and earlier review were consulted as evidence. No structural pre-pass was supplied.

This is a source review. No builds, tests, sanitizers or new runtime reproductions were run, and no implementation or tests were modified. Runtime consequences below follow from the current expressions, operand domains, generated handlers and sanitizer build configuration. The review does not establish an exhaustive hardware conformance result or qualify additional platforms.

**Scope limitation:** The adapter, current audit/acceptance tools and experiment tests were traced in context. The large imported instruction template, core helper header, generator and Unity files were inspected at their relevant configuration, execution, arithmetic, parser and assertion surfaces; this report does not claim a complete line-by-line audit of every imported function. Historical adaptation copies were consulted for provenance/replay behavior rather than requalified as runtime implementations. Uninspected imported branches remain **unknown**, and the 44-file list records the files examined, not exhaustive coverage of every branch. The confirmed blockers are sufficient to prevent a clean review result.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Register shift counts reach undefined shifts before their range checks

**Classification:** BLOCKER
**File:** `third_party/musashi/m68k_in.c:1984-1987`, `2040`, `2093`, `2224`, `2262`, `2300`, `5351`, `5389`, `5427`, `5536`, `5574`, `5612`
**Issue:** The register-count ASR, ASL, LSR and LSL templates compute `shift = DX & 0x3f`, then immediately evaluate `src >> shift` or `src << shift`. Their later operand-width branches do not protect that evaluation. On the admitted native configuration, `uint` is a 32-bit unsigned int (`m68kcpu.h:75-79`), so counts 32 through 63 invoke undefined behavior. This affects byte and word variants too because their C operands are still `uint`. A legal `ASR.L D1,D0` with D1=32 reaches the expression in generated `m68kops.c:3631-3635`; its 68000 dispatch entry is present at `m68kops.c:34952`. Equivalent generated left/logical handlers are also compiled. With `-fsanitize=undefined -fno-sanitize-recover=all` this can terminate the host instead of returning a guest result or bounded adapter status. The current selected guest/timing tests contain no large-count shift cases.
**Fix:** Move each shift calculation into the branch where the count is known to be less than the guest operand width. Handle zero, equal-width and greater-width counts explicitly, preserving the existing carry/extend, sign-fill and cycle rules. For example, initialize `res = src` for zero and evaluate `src >> shift` only inside `if (shift > 0 && shift < operand_bits)`. Apply the change through `adapt.py` to the template and regenerate; add boundary cases for 0, 7/8, 15/16, 31/32 and 63 in the actual UBSan runtime lane before rebinding acceptance.

### CR-02: DIVS shifts a negative signed remainder

**Classification:** BLOCKER
**File:** `third_party/musashi/m68k_in.c:4446`, `4484`
**Issue:** Both signed division templates declare `remainder` as signed `sint`, compute it with signed `%`, and pack it using `(remainder << 16)`. For a negative dividend with a nonzero remainder, such as D0=-7 and a divisor of 3, the quotient fits the 16-bit result and remainder=-1 reaches this expression. Left-shifting a negative signed value is undefined in C17. Generated `m68kops.c:12136-12164` contains the actual register handler, and `m68kops.c:34711` assigns it a nonzero 68000 dispatch/cycle entry. The same expression propagates to every generated memory/immediate DIVS form. The configured nonrecovering UBSan lane can terminate the host on this legal instruction.
**Fix:** Convert and mask the remainder before shifting, e.g. `((uint)(uint16)remainder << 16) | ((uint)quotient & 0xffffu)`. Make the template change reproducible through the adaptation recipe and regenerate all affected handlers. Add negative-dividend, nonzero-remainder cases through register and memory/immediate operands, and refresh actual sanitizer evidence and the independent acceptance review.

### CR-03: Bit 31 masks shift a signed int into its sign bit

**Classification:** BLOCKER
**File:** `third_party/musashi/m68k_in.c:2407`, `2428`, `2449`, `2470`, `3190`, `3211`, `3269`, `3281`
**Issue:** Longword BCHG, BCLR, BSET and BTST use literal `1` in `1 << (bit & 0x1f)`. Literal `1` has signed-int type, and the legal bit number 31 produces a value not representable as the admitted 32-bit signed int. Assigning the result to `uint` afterward does not make the shift defined. Both register-specified and immediate bit numbers reach this path. Generated `m68kops.c:4865-4868` and the corresponding BCLR/BSET/BTST handlers retain these expressions. These are compiled 68000 handlers, so testing or changing a register's high bit can invoke undefined behavior and abort the nonrecovering sanitizer build.
**Fix:** Use an unsigned mask base (`1u`, or an explicit `uint32` value) before shifting in every applicable template expression. Preserve the modulo-32 bit selection and existing Z behavior. Regenerate via the recipe and add immediate/register bit-31 cases for all four operations in the actual runtime sanitizer lane.

### CR-04: Generator path arguments can overflow buffers or read before them

**Classification:** BLOCKER
**File:** `third_party/musashi/m68kmake.c:1248-1255`
**Issue:** The compiled host generator copies argv[1] into the 1024-byte `output_path` and argv[2] into the 1024-byte `g_input_filename` using unchecked `strcpy`. An overlong argument writes beyond the buffer. An output path that exactly fills the available bytes can also overflow during the subsequent slash append. An empty output-path argument reaches `output_path[strlen(output_path)-1]`, accessing outside the buffer. The generator is a separate host executable (`experiments/cpu/CMakeLists.txt:9-10`), so this finding concerns host tooling, not an ambient service inside the CPU library. Valid nested filesystem paths can exceed the generator's private limit.
**Fix:** Reject empty output paths and paths that cannot fit their terminator plus an optional appended slash before any copy. Check the input path length independently, use bounded copies/formatting and check formatting results. Exercise empty, exact-limit and one-over arguments as generator controls; retain the pinned template and generator separation.

### CR-05: Unsigned EOF sentinel bypasses generator error handling

**Classification:** BLOCKER
**File:** `third_party/musashi/m68kmake.c:594-599`, `1171-1176`, `1184-1202`
**Issue:** `fgetline` returns `size_t` and returns `-1` on EOF/read failure. This becomes `SIZE_MAX`. Callers throughout the generator test its result with `< 0`, which is always false for that unsigned type. A template truncated immediately after an insert header reaches `read_insert`, bypasses the intended EOF rejection, performs `ptr += SIZE_MAX`, then writes a newline through the resulting invalid pointer. Other scanning loops can repeatedly process stale contents after EOF. The current pinned complete template avoids this path; a truncated or unreadable input to the documented custom-input generator does not fail safely.
**Fix:** Give line reading a distinct failure result that callers actually check: use a signed length type with a checked conversion, or retain `size_t` and test explicitly for `SIZE_MAX` before using the length. Update every caller, not only `read_insert`. Add truncated-template and I/O-failure controls which must return an error promptly without publishing usable output or writing outside buffers.

### CR-06: Generator array guards permit the first out-of-bounds entry

**Classification:** BLOCKER
**File:** `third_party/musashi/m68kmake.c:795-801`, `1020-1026`
**Issue:** The output table contains `MAX_OPCODE_OUTPUT_TABLE_LENGTH` entries and the handler body contains `MAX_BODY_LENGTH` rows (`m68kmake.c:208,271`). Their pre-write guards use `>` instead of `>=`. A handler body with a 301st row reaches `body->body[300]`, and a template expanding beyond 3000 entries reaches `g_opcode_output_table[3000]`; both writes are outside their arrays. Rejection happens only on the following iteration. These are host generator input failures, distinct from the CPU runtime; the submitted template stays below the limits but the declared capacity checks are incorrect.
**Fix:** Change both pre-write capacity guards to `>=`, check capacity before every entry/terminator write, and define whether closing braces/terminators count toward each capacity. Add exact-capacity and one-over template controls that establish rejection before an out-of-bounds access. Preserve the admitted generated outputs until a complete successful generation.

## Warnings

### WR-01: Python optimization removes historical budget validation

**Classification:** WARNING
**File:** `experiments/cpu/evidence/recovery-accounting/replay.py:19`, `31-57`; caller `tools/cpu/audit.py:139`
**Issue:** Historical replay validates subprocess outcomes, pristine/adapted hashes, per-transition churn, recipe identities and final totals exclusively with Python `assert`. `audit.budget()` launches it with `sys.executable` and the inherited environment. When `PYTHONOPTIMIZE=1` is set, Python removes these assertions, including expressions that perform the actual `churn(...)` comparisons. Replay still prints a hardcoded passing receipt with `all_four_source_stages_replayed: true`. Thus the budget audit can claim successful historical replay without checking the facts that support its cumulative source accounting. The current receipt does not establish that optimization was enabled; this is an environment-dependent validation gap.
**Fix:** Replace evidence assertions with explicit checked conditions that raise on mismatch regardless of optimization. Check subprocess statuses explicitly and derive the printed receipt from validated totals. Verify that altered history/recipe/hash subjects reject with both normal Python and `PYTHONOPTIMIZE=1`; do not solve this only by asserting that optimization is disabled.

### WR-02: Relative pristine paths produce unreplayable failed-attempt patches

**Classification:** WARNING
**File:** `tools/cpu/record_attempt.py:35-46`
**Issue:** The recorder accepts a relative pristine directory, but normalizes the old patch path with `"a" + str(pristine)`. For an absolute pristine path, Git's `a/tmp/...` header matches that spelling. For a relative `pristine/m68k.h`, Git emits `a/pristine/m68k.h` while the replacement searches for `apristine/m68k.h`, so it does not replace the old path. The emitted patch also retains the relative directory in its `---` header. `verify_recipe` and historical replay reverse-apply patches in a scratch directory containing only the six basename files (`audit.py:102-116`; `replay.py:24-31`), so a receipt reproduced with an otherwise valid relative pristine path cannot be replayed using the documented process.
**Fix:** Resolve the pristine directory before generating patches and normalize every diff header consistently, or generate the patch from controlled scratch paths whose basenames are known. Check the generated patch by reverse-applying it to an independent scratch tree and checking all pristine hashes before publishing the receipt. Cover both relative and absolute pristine-directory inputs.

## Required disposition

The three runtime findings are reachable through compiled 68000 handlers, independent of the explicitly unsupported board/BIOS/game and bus-error features. They require repair or explicit candidate rejection/defer within the frozen adaptation limits. Generator fixes concern a separate host executable. Any source repair invalidates the source manifest, regeneration/state identities, acceptance evidence and independent-review binding as applicable; update those through the existing bounded process rather than preserving the old accepted seal.

---

_Reviewer: gsd-code-reviewer_
_Depth: standard; source inspection only, no tests executed_
