# Independent CPU source review reconciliation

## Identity and current disposition

Reviewer: `/root/phase01_plan05/review_reconcile`, the independent agent assigned to plan 01-05 task 3. This agent did not implement the candidate.

**Admission rejected/deferred:** six critical findings and two medium warnings remain open. No repair was performed. This reconciliation does not qualify a backend or complete Phase 01.

- Evaluated source revision: `94f468326e5e529fd7c54f28434816c27f80f379`
- Content digest: `81aa0d99145d7b214a7336ae02f9a825eff328c8c26011fd2eef35fbe977b527`
- Canonical evidence digest: `6dafb025bf1b3ba2a52750cae3e9f50a1db3a552ebb8507edebb8fa2ec493c66`

All 65 input hashes in the archived acceptance report match the current checkout. The canonical evidence digest independently recomputes to the value above using `tools/cpu/acceptance.py:68-74`. No runtime record or source identity is changed by this reconciliation.

## Provenance and inspection limits

The earlier clean review by `codex:cpu_acceptance_review_01` is preserved byte-for-byte in `experiments/cpu/evidence/plan-01-05/prior-REVIEW.md`, SHA-256 `254fae71bfdb3a468dec1126bfd4f8b4e73f8c194b6cc594945219243b17c649`. Its clean disposition is historical and superseded for current admission. Its corresponding accepted report is preserved as `experiments/cpu/evidence/plan-01-05/prior-acceptance-results.json`, SHA-256 `3b9d6a736fb7ac8e647aed77f1ca9c10cc17233b3f1991c2d3be13ae25f9a2d3`.

The later `.planning/phases/01-cpu-acceptance-experiment/01-REVIEW.md` is dated `2026-10-01T22:01:37Z`; it examined 44 handwritten files with generated handlers as supporting evidence. Its imported instruction template, helper header, generator and Unity coverage was targeted at relevant surfaces, not a complete line-by-line audit. Uninspected imported branches remain unknown. It ran no builds, tests, sanitizers or fresh runtime reproductions.

This agent independently inspected cited template expressions; representative generated handlers and dispatch entries; integer typedefs; generator path, EOF and capacity code; CMake runtime/generator wiring and sanitizer configuration; replay assertions and their audit caller; recorder normalization and scratch consumers; and review schema/digest logic. Full citation extents below retain the later review's references; representative inspection does not claim exhaustive generated-handler coverage.

The machine-readable `inspected` array retains the twelve historical scope names because the existing schema requires exact `REVIEW_SCOPE` equality (`tools/cpu/acceptance.py:35-38,125-138`). It records historical scope carried forward with this targeted independent reconciliation, **not a claim that this agent repeated all twelve audits**. The extra scope provenance makes that distinction explicit. Earlier rights/oracle, closure, ownership, state, cold-init, fault, cycle, binding, control, budget and hygiene narratives remain historical observations in the immutable archive.

This is source-only review. I did not build, regenerate, execute CPU fixtures, run sanitizers or rerun adaptation. No newly observed crash, diagnostic, race result or hardware conformance is claimed.

## Findings

Each finding remains unresolved. No repair or fresh behavioral qualification was performed.

### CR-01 — Register shift counts reach undefined shifts before guards

- Severity/status: `critical` / `open`.
- Sources: `third_party/musashi/m68k_in.c:1984-1987,2040,2093,2224,2262,2300,5351,5389,5427,5536,5574,5612; third_party/musashi/m68kcpu.h:75-79; generated third_party/musashi/m68kops.c:3631-3635,34952`.
- Supported consequence: ASR/ASL/LSR/LSL compute `DX & 0x3f` and evaluate the C shift before operand-width guards. On the documented 32-bit unsigned-int configuration, legal counts 32–63 invoke undefined behavior, including narrow guest operands represented as `uint`. ASR.L D1,D0 with D1=32 reaches a generated handler with a nonzero 68000 dispatch entry.
- Uncertainty: No new shift execution or sanitizer abort was observed; other integer widths remain unqualified. Selected prior cases do not cover these boundaries.
- Disposition: Blocks runtime admission. No repair performed; any repair and validation require separately authorized work.

### CR-02 — DIVS shifts a negative signed remainder

- Severity/status: `critical` / `open`.
- Sources: `third_party/musashi/m68k_in.c:4446,4484; generated third_party/musashi/m68kops.c:12136-12164,34711`.
- Supported consequence: Signed `%` can yield negative `sint remainder`; `(remainder << 16)` is undefined in C17. D0=-7 divided by 3 yields fitting quotient -2 and remainder -1, reaching the generated register form. The same template expression supplies memory/immediate forms.
- Uncertainty: No fresh negative-remainder execution or exhaustive generated-form testing; selected historical passes do not cover this counterexample.
- Disposition: Blocks runtime admission. No repair performed; any repair and validation require separately authorized work.

### CR-03 — Bit 31 masks shift a signed int into its sign bit

- Severity/status: `critical` / `open`.
- Sources: `third_party/musashi/m68k_in.c:2407,2428,2449,2470,3190,3211,3269,3281; generated third_party/musashi/m68kops.c:4865-4868 and corresponding BCLR/BSET/BTST handlers; third_party/musashi/m68kcpu.h:75-79`.
- Supported consequence: Longword BCHG/BCLR/BSET/BTST use signed literal `1 << (bit & 0x1f)`. Legal immediate or register bit 31 yields an unrepresentable signed-int value on the admitted 32-bit configuration. Assigning to `uint` afterward does not define the shift.
- Uncertainty: No fresh bit-31 execution or sanitizer observation; consequences on other integer-width hosts are unqualified.
- Disposition: Blocks runtime admission. No repair performed; any repair and validation require separately authorized work.

### CR-04 — Generator path arguments overflow buffers or access before them

- Severity/status: `critical` / `open`.
- Sources: `third_party/musashi/m68kmake.c:1248-1255; experiments/cpu/CMakeLists.txt:9-11`.
- Supported consequence: Unchecked `strcpy` copies argv paths into 1024-byte arrays; overlong paths overflow, and the appended slash can overflow a full path. An empty output argument reaches `output_path[strlen(output_path)-1]` outside storage. The generator is a separate host executable, not an ambient filesystem service in the CPU archive.
- Uncertainty: No malformed/limit argument was executed here. Earlier successful generation with ordinary paths does not qualify these bounds.
- Disposition: Blocks safe generator qualification. No repair performed; any repair and validation require separately authorized work.

### CR-05 — Unsigned EOF sentinel bypasses generator error handling

- Severity/status: `critical` / `open`.
- Sources: `third_party/musashi/m68kmake.c:594-599,1171-1176,1184-1202 and other fgetline callers`.
- Supported consequence: `size_t fgetline` returns `-1`, converted to `SIZE_MAX`, while callers test `< 0`. Truncation immediately after an insert header can bypass rejection, perform invalid `ptr += SIZE_MAX` and write a newline outside valid storage. Other scanning loops can process stale contents at EOF.
- Uncertainty: No truncated/I/O-failure input was executed. The complete historical template avoids this path; a safe failure claim is unsupported.
- Disposition: Blocks safe generator qualification. No repair performed; any repair and validation require separately authorized work.

### CR-06 — Generator capacity guards permit the first invalid entry

- Severity/status: `critical` / `open`.
- Sources: `third_party/musashi/m68kmake.c:795-801,1020-1026; array declarations :208,271`.
- Supported consequence: Pre-write guards use `>` rather than `>=`. A 301st body row reaches `body[300]` and a 3001st output entry reaches table index 3000, outside their arrays; rejection only on a following iteration is too late.
- Uncertainty: Exact-capacity and one-over controls were not run. The submitted template stays below these limits; terminator capacity requires validation during any repair.
- Disposition: Blocks safe generator qualification. No repair performed; any repair and validation require separately authorized work.

### WR-01 — Python optimization removes historical replay validation

- Severity/status: `medium` / `open`.
- Sources: `experiments/cpu/evidence/recovery-accounting/replay.py:19,31-57; tools/cpu/audit.py:139`.
- Supported consequence: Replay uses `assert` for subprocess statuses, hashes, churn, recipe identity and totals. Its caller inherits the environment. `PYTHONOPTIMIZE=1` removes these checks, including churn expressions, while a hardcoded passing receipt still claims all four stages replayed.
- Uncertainty: No evidence shows historical optimization was enabled, so historical charges are not changed. No optimized replay ran here; normal-Python sealing does not resolve this defect.
- Disposition: Blocks trusting optimized replay as validation. No repair performed; any repair and validation require separately authorized work.

### WR-02 — Relative pristine paths produce unreplayable patch prefixes

- Severity/status: `medium` / `open`.
- Sources: `tools/cpu/record_attempt.py:35-46; tools/cpu/audit.py:102-116; experiments/cpu/evidence/recovery-accounting/replay.py:24-31`.
- Supported consequence: Normalization searches `"a" + str(pristine)`: for relative pristine/m68k.h it seeks `apristine/m68k.h` while Git emits `a/pristine/m68k.h`. Old diff/--- paths retain directories incompatible with consumers' basename-only scratch trees.
- Uncertainty: No relative/absolute recorder reproduction ran. This conditional counterexample does not declare the preserved historical patch invalid or change any charged total.
- Disposition: Blocks relative-path patch replay claims. No repair performed; any repair and validation require separately authorized work.

### REV-LOW-01 — Historical inventory prose count — resolved

Severity/status: `low` / `resolved`. The archived review found the acceptance narrative said 98 at its then-current `experiments/cpu/ACCEPTANCE.md:270-273`, while `experiments/cpu/state-inventory.json:14-1317` contained 99 entries, including `cpu_instance.active`. It independently confirmed the prose correction to 99. This historical resolution is retained and does not resolve any CR/WR.

## Consequences and retained limits

`experiments/cpu/CMakeLists.txt:11,30-43` compiles generated handlers into the runtime and configures `-fsanitize=address,undefined -fno-sanitize-recover=all` for its ASan/UBSan lane. CR-01–03 can therefore terminate that lane on legal operands; this is a source-derived possibility, not a fresh observed sanitizer failure. CR-04–06 concern the separate generator at lines 9–10; runtime independence from host filesystem services remains a separate contract.

The submitted 56/56 passing records, selected cold/isolation/fault/timing/continuation outcomes and sanitizer receipts are historical evidence, retained without a new denominator or runtime claim. Distinct compiler lanes, true 68000 guest bus-error fidelity, arbitrary bus-cycle suspension, board/BIOS/game compatibility, public/durable state compatibility and release-platform support remain unsupported. Uninspected branches remain unknown.

Frozen allowance remains two attempts, 16 cumulative hours, 8 hours per attempt and every existing patch/source cap. Both attempts are consumed. Charges remain 2,614 handwritten, 523 helper and 483 semantic lines, 20,005 total seconds and 18,859 final-attempt seconds. This review grants no refund, extra attempt, repair or replacement. CPU-01–04 admission remains pending, Phase 01 stays open and Phase 02/SDK integration stays gated. Blocking plan 01-06 owns developer direction and referral to separately authorized replanning before further repair/replacement or integration.

## Machine-readable review metadata

```json
{
  "reviewer": "/root/phase01_plan05/review_reconcile",
  "independent": true,
  "source_revision": "94f468326e5e529fd7c54f28434816c27f80f379",
  "content_digest": "81aa0d99145d7b214a7336ae02f9a825eff328c8c26011fd2eef35fbe977b527",
  "evidence_digest": "6dafb025bf1b3ba2a52750cae3e9f50a1db3a552ebb8507edebb8fa2ec493c66",
  "inspected": [
    "rights-oracles",
    "closure-generation",
    "explicit-call-graph",
    "all-state-fields",
    "cold-init-cleanup",
    "fault-frames",
    "cycles-exceptions",
    "fresh-bindings",
    "consequential-controls",
    "budgets-effort",
    "admission-tooling",
    "public-hygiene"
  ],
  "scope_provenance": {
    "inspected_meaning": "Historical scope retained from archived review; current reviewer performed targeted source reconciliation, not a repeated exhaustive audit.",
    "historical_reviewer": "codex:cpu_acceptance_review_01",
    "historical_review": "experiments/cpu/evidence/plan-01-05/prior-REVIEW.md",
    "historical_review_sha256": "254fae71bfdb3a468dec1126bfd4f8b4e73f8c194b6cc594945219243b17c649",
    "later_review": ".planning/phases/01-cpu-acceptance-experiment/01-REVIEW.md",
    "current_inspection": [
      "cited-template-expressions",
      "representative-generated-handlers-and-dispatch",
      "integer-typedefs",
      "generator-path-eof-capacity",
      "cmake-wiring",
      "replay-and-audit-caller",
      "patch-normalization-and-consumers",
      "acceptance-schema-and-identities"
    ],
    "runtime_rerun": false,
    "repair_performed": false
  },
  "findings": [
    {
      "id": "CR-01",
      "severity": "critical",
      "status": "open",
      "summary": "Register shift counts reach undefined shifts before guards; Blocks runtime admission."
    },
    {
      "id": "CR-02",
      "severity": "critical",
      "status": "open",
      "summary": "DIVS shifts a negative signed remainder; Blocks runtime admission."
    },
    {
      "id": "CR-03",
      "severity": "critical",
      "status": "open",
      "summary": "Bit 31 masks shift a signed int into its sign bit; Blocks runtime admission."
    },
    {
      "id": "CR-04",
      "severity": "critical",
      "status": "open",
      "summary": "Generator path arguments overflow buffers or access before them; Blocks safe generator qualification."
    },
    {
      "id": "CR-05",
      "severity": "critical",
      "status": "open",
      "summary": "Unsigned EOF sentinel bypasses generator error handling; Blocks safe generator qualification."
    },
    {
      "id": "CR-06",
      "severity": "critical",
      "status": "open",
      "summary": "Generator capacity guards permit the first invalid entry; Blocks safe generator qualification."
    },
    {
      "id": "WR-01",
      "severity": "medium",
      "status": "open",
      "summary": "Python optimization removes historical replay validation; Blocks trusting optimized replay as validation."
    },
    {
      "id": "WR-02",
      "severity": "medium",
      "status": "open",
      "summary": "Relative pristine paths produce unreplayable patch prefixes; Blocks relative-path patch replay claims."
    },
    {
      "id": "REV-LOW-01",
      "severity": "low",
      "status": "resolved",
      "summary": "Earlier narrative inventory count was 98 while the checked inventory has 99.",
      "resolution": "The archived review independently confirmed prose corrected to 99; historical resolution retained, no runtime-source change."
    }
  ]
}
```
