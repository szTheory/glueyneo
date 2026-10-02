# CPU candidate acceptance experiment

Status: **current admission rejected / GAPS_FOUND; historical acceptance is superseded by unresolved source blockers**. Phase 01 remains open and Phase 02 gated. No further adaptation is authorized; both attempts are consumed. See the current disposition below.

The status field inside `budget-ledger.json` is a historical snapshot from the former candidate workflow. This document and current `.planning` contracts own the present disposition. Preserve the ledger bytes as historical accounting; do not read its legacy status as current acceptance.

## Historical reproduction and admission gate — superseded for current admission

Use the committed checkout containing the final report's evaluated inputs:

```sh
cmake -S . -B build/cpu-final -G Ninja -DGLUEYNEO_CPU_EXPERIMENT=ON
cmake --build build/cpu-final --parallel 2
python3 tools/cpu/acceptance.py self-test
python3 tools/cpu/acceptance.py collect --build-dir build/cpu-final
python3 tools/cpu/acceptance.py verify --require-accepted
ctest --test-dir build/cpu-final -L cpu --output-on-failure --no-tests=error
```

`collect` creates unique fresh native, ASan/UBSan and TSan build trees below
the requested build directory, limits each build to two workers, runs actual
runtime cases, and regenerates twice in separate scratch directories. It excludes
acceptance CTests from collection to avoid recursion. Native required execution
is 28 CTests; ASan/UBSan is 8; TSan is 18. Two additional native source records
cover independent regeneration and ten acceptance control methods (many contain
per-cap/per-case subtests). The final CPU label adds two admission CTests.

Each required case has an expected and observed count, lane/configuration/input
identity, status and retained output with SHA-256. Unity counts count registered
test functions; supervised controls count intended failures; source counts name
the check/control denominator. These are not instruction-coverage percentages.
Runtime object compile blocks and archive/object digests separately prove the
instrumented closure. Source closure, rights, state inventory and cap checks
remain source evidence. Queried absent distinct compilers and unsupported
capabilities remain explicit separate records.

Collection grants only `ready-for-review` / `GAPS_FOUND`. An independent source
reviewer must inspect the current source and the report, then author `REVIEW.md`
with the evaluated revision, content digest and canonical evidence digest.
`python3 tools/cpu/acceptance.py seal --require-accepted` incorporates that
review and rejects unresolved high/critical findings. Recollection intentionally
invalidates an old review even if runtime source is unchanged: the reviewer
must confirm the newly produced evidence digest. `verify` performs read-only
identity/output/decision validation and runs no CPU tests or receipt writes.

The content digest includes runtime/build/test/tool sources, fixtures and their
oracle, notices, source/state/fixture manifests, and immutable recovery-accounting
inputs. Produced reports/logs, review and the mutable effort ledger are excluded
to avoid recursive hashes; the ledger and cumulative Git source-history digest
are checked separately. The frozen contract is compared with its original commit.
Later documentation/evidence-only commits can retain the evaluated revision if
every input byte and cumulative source charge remains identical. Such commits
do not claim another runtime run. These local receipts are not signatures against
a malicious author able to replace both the tool and its evidence; independent
review and the repository's later protected delivery gates remain separate.

The original malformed guest and earlier compiler/sanitizer/timing/state
counterexamples remain under `evidence/attempt-1`, `evidence/attempt-2`,
`evidence/plan-01-02` and `evidence/plan-01-03`. The first final collection's
CTest-output truncation is preserved under `evidence/plan-01-04`; it never
qualified as acceptance. A failed/rejected/deferred candidate keeps CPU-01–04
pending, reports `GAPS_FOUND`, and blocks Phase 2. Replacement or scope changes
need a separate bounded plan; neither a new allowance nor attempt 3 is implied.

## Frozen admission contract

<!-- freeze:start -->
Candidate: Musashi commit `313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd` only.
Starting project revision: `3977c3bfbfdc752e1b43443aa3911c7012678177`.
No candidate adaptation preceded this contract.

Hard limits, with equality permitted and any excess requiring rejection:

| Resource | Maximum |
|---|---:|
| Substantive adaptation attempts | 2 |
| Active engineer/agent effort, cumulative | 16 hours |
| Active effort per attempt | 8 hours |
| Changed handwritten upstream files | 6 |
| Cumulative handwritten added plus deleted lines | 5,000 |
| Semantic repair lines, included in handwritten total | 500 |
| Adaptation helper/shim lines, included in handwritten total | 600 |
| Regenerated output files | 2 |
| Generated output lines, combined | 50,000 |
| Generated output bytes, combined | 2,097,152 |

The only editable handwritten upstream inputs are `m68k.h`, `m68kcpu.h`,
`m68kcpu.c`, `m68kconf.h`, `m68k_in.c` and `m68kmake.c`. The only generated
outputs are `m68kops.h` and `m68kops.c`; hand editing them is prohibited.
Count normal added/deleted lines against pristine inputs without whitespace
exemptions. Include moved/replaced code and adaptation support regardless of
path. Carry cumulative work and attempt maxima forward; neither a fresh file
nor a second attempt resets the allowance. Test, fixture and documentation
classification cannot conceal adaptation. Semantic repairs change instruction,
exception, error or cycle behavior; context/signature plumbing is counted in
the main total. Generated output is accounted separately.

Attempt 1 implements explicit contexts, minimal 68000 closure and one guest.
Attempt 2 may repair recorded concrete counterexamples inside the same total
caps. Stop immediately on exhaustion or an unrepairable rights, host-safety,
isolation or selected timing/state incompatibility. Preserve the failed patch
and counterexample, record rejection and halt dependent implementation. Do not
raise these limits, weaken the oracle or mark CPU-01 through CPU-04 complete.
A rejection may fulfill CPU-05's decision obligation but cannot admit Phase 2
or complete Phase 1. Replacement investigation requires a separate plan.

No global current-instance pointer, TLS routing, context swapping or global
execution lock qualifies. Runtime is C, uses explicit per-instance state and
host-owned bus/allocator bindings, and has no ambient host I/O, clock or process
termination. FPU/MMU/SoftFloat exclusion requires compiled and distributed
closure evidence. Timing is instruction-boundary qualified, not board timing.
<!-- freeze:end -->

## Execution ledger

The freeze commit is the first commit containing this file, identifiable by
`git log --reverse -- experiments/cpu/ACCEPTANCE.md`. Its exact identity will be
recorded below after committing, without changing the frozen section.

- Preparation began 2026-10-01T16:16:00Z; source adaptation has not started.
- Attempts started: 0. Upstream churn: 0. Helpers: 0. Semantic repairs: 0.
- Generated output admitted: none. No CPU tests have run.

## Attempt 1 outcome — halted

Freeze commit: `f9e7dda6ce3593dc176ebfc99f9a6c504bf423f8`.
Assertion-first commit: `6ecfa4b98032478bb8f84730d9e8123bfebb5aee`.
The frozen section above is unchanged. One substantive adaptation attempt
started; no second attempt has started and no allowance has been reset.

Conservative charged interval: 2026-10-01T16:19:53Z through
2026-10-01T16:31:13Z, **680 seconds**, including preparation and tool time.
Source adaptation followed the RED commit at 16:24:08Z. Post-halt evidence
closeout is recorded separately in the plan summary and does not authorize
further source changes.

| Measurement at halt | Result |
|---|---:|
| Changed selected handwritten inputs | 6 |
| Upstream added + deleted lines against pristine | 1,761 |
| Current adaptation support lines (including adapter, header, bus and recipe) | 220 |
| Discarded RED adapter scaffold, conservatively also charged | 15 |
| Current measured handwritten subtotal | 1,996 |
| Generated files | 2 |
| Generated lines | 36,559 |
| Generated bytes | 831,218 |
| Semantic repair classification | Unreviewed; acceptance blocked |

These are measured current-patch quantities, not a completed cumulative audit.
The initial transform measured 1,507 upstream lines and a 96-line recipe;
successive compile-driven edits increased the current patch. A complete
cumulative ledger, reviewed semantic classification and budget controls remain
Task 2 obligations. No cap is asserted exceeded and no cap is raised.

The installed executor limits inline corrective attempts to three per task.
After three corrections, the build still failed:

1. `OPER_AY_*` helpers initially lacked explicit context arguments. Propagating
   their signatures exposed integer aliases formerly supplied by SoftFloat.
2. Replacing `int32` in the internal header and updating the generation recipe
   exposed missing context in generator-produced operand call expressions.
3. Updating the generator's concrete operand formats exposed direct immediate
   `OPER_I_*()` template calls, plus a `CPU_STOPPED` name collision between the
   adapter status and the backend macro. Both remain unresolved.

**Disposition: defer this candidate investigation, preserve this failed patch,
and halt dependent plans pending a bounded continuation/replan.** These are
compile counterexamples, not proof of an unrepairable Musashi limitation. The
numeric candidate budget remains frozen. Any subsequent work must reconcile
the existing patch/effort and executor stop before continuing; do not count
this halt as acceptance or automatically expand to plans 01-02 through 01-04.

The original guest RED test intentionally failed its arithmetic assertion
(expected 10, observed 0) against the pre-implementation scaffold. The installed
TDD gate returned `RED_EVIDENCE_OK`. The adapted backend has **not** executed a
successful guest. The consequential mutation, bounded host fault, zero-budget
behavior, runtime linkage closure, regeneration controls, isolation, timing
and continuation remain unqualified. CPU-01 through CPU-04 stay pending;
this plan claims no requirement completion, including CPU-05's full decision
evidence. The second guest is encoded but has not been run.

Evidence: `evidence/attempt-1/receipt.json`, `source.patch` and
`build-failure.txt`; reproduction script: `tools/cpu/record_attempt.py`.
The build receipt contains public relative paths and current source hashes.

## Recovery accounting — 2026-10-01

The user approved the bounded continuation described in
`.planning/phases/01-cpu-acceptance-experiment/01-01-RECOVERY.md`.
The archived attempt-1 summary, receipt, source patch and failure remain intact.
Recovered original edits replay offline to the exact halted source bytes:
`python3 experiments/cpu/evidence/recovery-accounting/replay.py .`.

The reconciled historical charges supersede the incomplete subtotal above:
1,771 upstream + 302 helpers (including 48 build-file lines) = **2,073
cumulative handwritten lines**. The conservative independently reviewed
semantic ceiling is **471 lines**. Exact transitions, identities, residuals
and classification rationale are in `evidence/recovery-accounting/history.json`.
These are within the unchanged limits; none is reset for the second attempt.
Historical recipe/source copies are immutable evidence of already charged
work, not new helper implementations. Test/evidence tools do not adapt runtime.

`budget-ledger.json` owns machine-readable accounting and time. It charges
the full original preparation-through-closeout interval (1,146 seconds),
1,445 seconds for the independent historical review, and the full recovery
executor interval conservatively from 16:40Z. Parallel effort is additive.
The second substantive attempt has not started at this accounting checkpoint.

## Attempt 2 tracer — 2026-10-01

Accounting commit `b3776f7` preceded the transition at 17:01:29Z. Initial
context/name repairs exposed template integer aliases from excluded SoftFloat
headers; `evidence/attempt-2/compiler-1.txt` and its patch preserve that
counterexample. One corrective pass replaced 14 template lines with the
core's existing signed integer types and regenerated both outputs.

Configure/build and both guest CTests pass. Four Unity cases prove arithmetic
store, zero-budget no-op, bounded invalid-address failure, and reset-vector
fault survival followed by reset recovery. The supervised operand mutation
fails its exact arithmetic assertion (10 versus 11). No expected value changed.

Current charges: **2,417 handwritten**, **340 helper**, **356 semantic**;
six inputs; two outputs, **36,559 lines / 832,698 bytes**. The historical
semantic ceiling was refined from 471 to 327 by independently identifying
72 exact context-only core line pairs (144 lines). All remaining core changes
stay charged; the type repair adds 29. Line-level evidence and its reproducer
are in `evidence/recovery-accounting/core-semantic-refinement.json`.
This refinement changes no handwritten/helper count or frozen limit.

`evidence/attempt-2/tracer.json` records exact source identities and results.
Task 2 is complete; the final qualification receipt below supersedes this tracer checkpoint.

## Plan 01-01 final evidence — 2026-10-01

`evidence/attempt-2/qualification.json` binds the final manifest and source
identities to five passing CTests, 13 host-audit controls and two independent
parallel regenerations. Native Apple Clang 21 closure passes without optimization
and with optimization, including actual dependencies, preprocessed inputs,
function references, archive symbols and minimal-consumer linkage. Distributed
inputs exclude FPU/MMU/SoftFloat; the opcode template is a generator input,
not a compiled test translation unit. This is native experiment evidence only.

Final cumulative source charges are **2,423 handwritten**, **346 helper**,
**356 semantic**, six inputs and two outputs totaling **36,559 lines /
832,698 bytes**. Effort is recorded conservatively in `budget-ledger.json`;
no frozen limit or attempt count was reset. All earlier checkpoint figures
above remain historical observations.

Task 2 reached its correction limit while intended negative controls failed
at an unrelated temporary-path boundary. The preserved failure and explicit
orchestrator continuation are in the recovery record. Canonicalizing the
subject root made both intended controls pass; a separate metadata correction
and regression establish the generator-template role. Neither changed CPU
runtime source or weakened a negative control. Isolation, timing, continuation,
remaining host safety and the final admission decision remain later-plan work.

## Plan 01-02 isolation and host safety — 2026-10-01

The private observer exposes registers and lifecycle observations without a
snapshot format. Distinct A/B guests match isolated baselines across **64
interleavings and 64 concurrent pairs**, each at nine actual guest boundaries.
Comparisons include all 4,096 RAM bytes, all D/A registers, PC/SR/IRQ/STOP,
instruction counts, actual cycles, and bounded ordered read/write owner traces.
The IRQ fixture uses level-7 autovector, ADDQ.L D1 and RTE. These comparisons
establish ownership, not the still-pending independent timing oracle.
Sixteen separate CTest processes each start two construction workers behind a
barrier before any backend exists. Each instance allocates **853,104 bytes in
one allocation** on this native ABI. Creation durations are printed as measured
host observations, not performance guarantees. Swapping A's baseline with B
fails the intended ownership assertion.

`state-inventory.json` covers 99 compiled objects/fields including seven
immutable shared tables. Compiler AST extraction checks exact declaration
names/types and binds reviewed dispositions to source hashes. Disposable
omitted-NMI and injected-mutable-global controls both fail as intended.

Fault injection covers the one actual allocation position with zero live
allocations and an independently executing healthy witness. Seven malformed
guest cases cover reset, fetch, store, IRQ stack, exception stack, secondary
address-error stack failure, and odd IRQ stack. The latter reproduced SIGSEGV;
`evidence/plan-01-02/irq-fault-counterexample.json` preserves the reproduction
and final-attempt scope update. Current-call backend traps now precede IRQ
entry, and unrecoverable backend HALT becomes a terminal adapter host fault.
Failed instances reject execution, IRQ changes and inspection; reset/destruction
remain permitted. No third attempt or frozen-cap change was made.

Actual Apple Clang 21.0.0 runtime objects and tests were instrumented separately:
ASan+UBSan first diagnosed intermediate out-of-bounds pointer arithmetic in
the test bus despite CTest returning success. The preserved sanitizer
counterexample explains the parenthesized offset fix and added fatal-diagnostic
flag. Final ASan+UBSan guest/fault/isolation and TSan isolation/cold outcomes,
exact identities, flags, test results and logs are bound by
`evidence/plan-01-02/qualification.json`. Queried distinct GCC/Clang executables
are unavailable; that lane is unsupported, not passing. No platform matrix,
hardware timing, backend continuation or backend admission is claimed.

## Remaining private contract limitations

The private adapter accepts model 68000 only; instance allocation and bus
callbacks belong to the caller. Each instance requires single-threaded access.
Signed requests outside 0..1,000,000 reject; zero requests return before backend
entry. Plan 01-03 replaces the earlier clamping contract. Actual elapsed time,
overshoot and completed dispatches are reported separately; stopped idle time
does not count as instructions. IRQ entry can share its call boundary with the
first handler instruction. See `tests/cpu/ORACLE.md` for exact manual/configuration
boundaries and the distinction between host faults and unsupported guest bus errors.

The private same-build state record explicitly captures guest fields, including
pending reset/IRQ/NMI, raw arithmetic flags, prefetch and exception metadata.
Capture/restore require a complete live typed record allocation; the size/version
fields detect incompatible records, not arbitrary byte-buffer lengths. Restore
validates before live mutation, retains destination host bindings and rebuilds
model constants/table pointers. Inactive later-model storage stays invariant zero.
Request-local cycle scratch is normalized; next executing entry overwrites it.
Counter exhaustion rejects positive work before overflow; zero remains a no-op.
Terminal host-fault results do not quantify partial progress before the fault;
guest memory writes already performed are not rolled back.
The host must copy guest memory separately. No host pointers or jump frames enter
the record. Calls on one instance cannot overlap; callback capture/restore reject.

Eight original continuation checkpoints compare full records, RAM, ordered bus
observations and actual progress after destroying and overwriting the source.
Twenty-five malformed cases reject atomically, and mutations of pending NMI or
prefetched ADDQ independently fail their intended guest-result comparisons.
Reset accounting, stale NMI and BSD address-error counterexamples and narrow
repairs remain in `evidence/plan-01-03`. No installed headers, public ABI, durable
snapshot compatibility, board, BIOS or platform-support claim is established.
Plan 01-04 now supplies the accepted bounded candidate decision; formal Phase 1
completion and Phase 2 admission remain subject to the separate GSD phase-goal
verification step.

## Plan 01-04 final qualification — 2026-10-01

The candidate is **accepted** for this private, bounded 68000 experiment.
`python3 tools/cpu/acceptance.py verify --require-accepted` confirms the sealed
decision, and `ctest --test-dir build/cpu-final -L cpu --output-on-failure
--no-tests=error` passes all **30/30** admission tests. The normalized report
contains **56/56 passing records**: 30 native, 8 ASan/UBSan and 18 TSan. The
independent source review has no unresolved blocking findings; its sole low
finding (the inventory count, corrected from 98 to 99) is resolved.

The accepted evidence binds to source revision
`94f468326e5e529fd7c54f28434816c27f80f379`, content digest
`81aa0d99145d7b214a7336ae02f9a825eff328c8c26011fd2eef35fbe977b527`, and
canonical evidence digest
`6dafb025bf1b3ba2a52750cae3e9f50a1db3a552ebb8507edebb8fa2ec493c66`.
The independent review receipt SHA-256 is
`254fae71bfdb3a468dec1126bfd4f8b4e73f8c194b6cc594945219243b17c649`.

The frozen limits remain unchanged and all recorded totals are within them:
2 attempts; 20,005 cumulative active seconds and 18,859 seconds in attempt 2;
2,614 handwritten lines, including 483 semantic and 523 helper lines; six
selected upstream inputs; and two generated files totaling 36,559 lines and
832,698 bytes. No allowance was reset or raised.

The acceptance is deliberately narrow. Other compiler toolchains and a release
platform matrix are unsupported; the native evidence is Apple Clang 21 on
Darwin arm64. Guest bus-error frames and bus-cycle suspension are unqualified;
timing evidence covers selected instruction and exception boundaries. No board,
BIOS or game compatibility is established. The same-build typed state record
does not establish a public state format or compatibility promise. These limits
remain constraints on subsequent SDK work. Phase 1 remains open until its
separate goal-verification step.

## Current supersession and bounded rejection — 2026-10-02, plan 01-05

The preceding sections retain historical observations, commands, case denominators
and acceptance claims. They are superseded for current admission by this section
and the current `REVIEW.md` / `acceptance-results.json`. The later independent
phase source review (`.planning/phases/01-cpu-acceptance-experiment/01-REVIEW.md`,
2026-10-01T22:01:37Z) found six blockers and two warnings. Plan 01-05 independently
reconciles their cited source paths and receipt bindings; it performs no CPU run,
build, regeneration or sanitizer run and makes no exhaustive source-audit claim.
The historical verifier refused grammar preflight rather than concluding all
CPU-01–04 behaviors failed. Its report and all four prior SUMMARYs remain intact.

### Preserved receipt identities

Task 2 archived both active receipts byte-for-byte before reconciliation, and task 3
independently compared the original source bytes and these hashes before mutation:

| Archive | SHA-256 |
| --- | --- |
| `evidence/plan-01-05/prior-acceptance-results.json` | `3b9d6a736fb7ac8e647aed77f1ca9c10cc17233b3f1991c2d3be13ae25f9a2d3` |
| `evidence/plan-01-05/prior-REVIEW.md` | `254fae71bfdb3a468dec1126bfd4f8b4e73f8c194b6cc594945219243b17c649` |

The evaluated source revision remains `94f468326e5e529fd7c54f28434816c27f80f379`,
content digest remains `81aa0d99145d7b214a7336ae02f9a825eff328c8c26011fd2eef35fbe977b527`,
and canonical evidence digest remains
`6dafb025bf1b3ba2a52750cae3e9f50a1db3a552ebb8507edebb8fa2ec493c66`.
Only the active review/result change in the report; its execution records, source
inputs, ledger identity, candidate eligibility field and all historical outputs
remain byte-equivalent as parsed records. Historical eligibility describes the
submitted receipt inputs, not current admission. The sealed review's new receipt
hash identifies the current reconciliation; the final plan summary records it.

### Eight unresolved source dispositions

Each row is source-only evidence, with no repair performed and no newly observed
runtime failure. Exact details and proposed repairs remain in the later phase
review and current independent reconciliation. C17 consequences are tied to the
admitted 32-bit unsigned-int configuration and nonrecovering UBSan wiring;
neither emulator agreement nor prior selected case passes establishes hardware truth.

| ID | Source reference and supported consequence | Disposition and uncertainty |
| --- | --- | --- |
| CR-01 | `m68k_in.c:1984–1987`, generated `m68kops.c:3630–3635,34952`: legal register count 32–63 reaches a width-invalid shift before guards. | Open critical; blocks runtime admission. Source consequence, no new operand execution. |
| CR-02 | `m68k_in.c:4446,4484`, generated `m68kops.c:12136–12164,34711`: negative nonzero DIVS remainder is shifted as signed. | Open critical; blocks runtime admission. Example -7/3 follows operand domain, not a fresh result. |
| CR-03 | `m68k_in.c:2407,2428,2449,2470,3190,3211,3269,3281`, generated BCHG/BCLR/BSET/BTST: signed literal 1 shifted to bit 31 is unrepresentable. | Open critical; blocks runtime admission. Actual generated 68000 wiring, no new sanitizer result. |
| CR-04 | `m68kmake.c:1248–1255`: unchecked path copies, slash append and empty-path index permit out-of-bounds access. | Open critical; blocks safe generator qualification. Separate host tool; does not disprove prior pinned happy-path generation. |
| CR-05 | `m68kmake.c:594–599,1171–1176,1184–1202`: unsigned EOF becomes SIZE_MAX, `< 0` checks fail and pointer advance is invalid. | Open critical; blocks safe generator qualification. Malformed/truncated inputs were not executed here. |
| CR-06 | `m68kmake.c:795,1020`: capacity guards use `>` before writes at first disallowed index. | Open critical; blocks safe generator qualification. Prior complete template does not qualify capacity boundaries. |
| WR-01 | `evidence/recovery-accounting/replay.py:19,31–57`: factual subprocess/hash/churn/cap checks are inside `assert` and vanish under optimized Python. | Open medium warning; blocks trusting optimized replay as validation. Normal-Python seal does not resolve it or refund charges. |
| WR-02 | `tools/cpu/record_attempt.py:35–46`: relative pristine path fails diff-header normalization required by basename replay. | Open medium warning; blocks relative-path patch replay claims. Original immutable patches and charges remain; no replacement patch generated. |

### Reproducible current decision and replanning disposition

Use normal Python with `PYTHONOPTIMIZE` absent (plan validation explicitly removes
it from each subprocess environment):

```sh
python3 tools/cpu/acceptance.py seal --require-accepted
python3 tools/cpu/acceptance.py verify --require-accepted
```

Both commands must return exit **1** with the structured result
`{"decision":"rejected","phase_status":"GAPS_FOUND","reasons":["blocking review finding"]}`.
Seal binds the current review; verify is read-only. This expected admission
refusal establishes the governance decision, not CPU acceptance. A metadata
error, stale receipt, timeout or malformed output is not equivalent evidence.

**Decision:** Reject current candidate admission and defer repair/replacement
direction to the blocking developer checkpoint in plan **01-06**. SDK integration
is prohibited until accepted CPU-01–04 evidence and fresh phase verification, or
an explicit reconciled roadmap revision. This referral triggers replanning before
integration; it authorizes no replacement, repair, third attempt or scope change.
Open warnings require separate repair/validation if this candidate path resumes.

The frozen block above, `budget-ledger.json`, recovery recipes/patches and all
source hashes are unchanged. Preserve **2,614 handwritten, 523 helper, 483 semantic
lines**, **20,005 total seconds / 18,859 final-attempt seconds**, two consumed
attempts, six upstream files and 36,559 generated lines / 832,698 bytes. The
remaining 77 helper / 17 semantic lines are headroom, not attempt authorization.
All pre-adaptation caps and prior conservative overcharges remain; governance
effort is recorded separately in the plan summary with no refund.

Historical 56/56 records (30 native, 8 ASan/UBSan, 18 TSan), 30/30 final tests,
99 state entries, eight continuation checkpoints, original manual-derived oracle
and every earlier counterexample remain historical evidence. In particular retain
odd IRQ crash, fixture UBSan, reset accounting/stale NMI, BSD address-error,
malformed-state and zero-request guards. D-04–D-11 limitations remain: original
notices, separate generator, minimal FPU/SoftFloat-free runtime closure, explicit
context ownership, selected instruction-boundary timing, private same-build state,
original fixture ancestry, recorded isolation/cold/failure observations and native
Apple Clang scope. Unsupported toolchains, real guest bus-error fidelity,
bus-cycle suspension, board/BIOS/game behavior, public/durable state and release
platform support remain unsupported or unqualified.

CPU-01–04 remain Pending current admission. CPU-05 may be Complete only after the
actual structured seal and read-only verify match the required rejection and an
independent receipt check confirms this decision, unchanged budgets/charges,
commands/results, all eight counterexamples/uncertainties and SDK-blocking
replanning referral. Its requirement status is owned by REQUIREMENTS.md and the
final summary; task 1's pending entry is an earlier chronological checkpoint.
