---
phase: 01-cpu-acceptance-experiment
plan: "05"
subsystem: cpu-admission
tags: [68000, evidence, governance, rejection]
requires:
  - phase: 01-04
    provides: Historical accepted report and independent review
provides:
  - Valid canonical acceptance story and explicit SDK gate
  - Byte-identical archived acceptance report and review
  - Independently reconciled non-admitting current source decision
affects: [01-06, phase-01-verification, phase-02-admission]
actuals:
  tokens: 131348
  tasks: 3
  commits: 3
plan_head_before: 1507376b5e0264c171a2d25f973961f75b79c250
tech-stack:
  added: []
  patterns: [immutable historical receipts, source-qualified rejection]
key-files:
  created:
    - experiments/cpu/evidence/plan-01-05/prior-acceptance-results.json
    - experiments/cpu/evidence/plan-01-05/prior-REVIEW.md
  modified:
    - .planning/ROADMAP.md
    - .planning/STATE.md
    - .planning/REQUIREMENTS.md
    - experiments/cpu/ACCEPTANCE.md
    - experiments/cpu/REVIEW.md
    - experiments/cpu/acceptance-results.json
key-decisions:
  - "Reject current CPU admission for six unresolved source blockers; defer repair/replacement direction to blocking plan 01-06."
  - "CPU-05 alone satisfies its bounded-decision obligation; CPU-01–04 remain Pending, Phase 01 open and Phase 02 gated."
requirements-completed: [CPU-05]
duration: 10min
completed: 2026-10-02
status: complete
---

# Phase 1 Plan 05: Current admission rejection Summary

**Canonical acceptance grammar now validates, while the unchanged CPU source is rejected for six independently reconciled blockers and historical receipts remain intact.**

## Performance

- Started: 2026-10-02T11:34:25Z.
- Tasks: 3; scoped files changed: 8.
- Governance elapsed interval: approximately 10 minutes, including independent source reconciliation; no adaptation effort, refund, cap change or new attempt is recorded.
- Actuals use 525,391 realized diff characters / 4, rounded up to 131,348 tokens; immutable archived report payload dominates the diff. The persisted plan ledger measures three task commits at summary creation; subsequent metadata commits are separate.

## Accomplishments and evidence

The exact canonical story is: “As a maintainer, I want to reproduce acceptance of a C 68000 backend, so that I can build the diagnostic SDK on independent instances with explicit state and timing limits.” Installed OpenGSD 1.14.0 `user-story.validate` returned exit 0, `valid: true`, and `errors: []`. The canonical ROADMAP goal matches it exactly. Both task checks were repeated after the tracer commit and passed; end-of-phase automated tracer feedback allowed continuation.

Task 2 created both archives exclusively, compared them byte-for-byte with the still-unmodified active sources, and computed their SHA-256 values. Task 3 independently repeated both comparisons and hash checks before mutation:

| Archive | SHA-256 |
| --- | --- |
| `experiments/cpu/evidence/plan-01-05/prior-acceptance-results.json` | `3b9d6a736fb7ac8e647aed77f1ca9c10cc17233b3f1991c2d3be13ae25f9a2d3` |
| `experiments/cpu/evidence/plan-01-05/prior-REVIEW.md` | `254fae71bfdb3a468dec1126bfd4f8b4e73f8c194b6cc594945219243b17c649` |

Independent reviewer `/root/phase01_plan05/review_reconcile` inspected the cited template expressions, representative generated handlers and dispatch entries, CMake wiring, generator paths/EOF/capacity, replay assertions and patch normalization. Its current receipt distinguishes the historical twelve-category scope from targeted reconciliation. It does not claim a new exhaustive audit, CPU run, build, regeneration or sanitizer result. The earlier clean review and later phase review retain their separate provenance.

| Finding | Current disposition |
| --- | --- |
| CR-01 | Critical/open; width-invalid register shifts block runtime admission. |
| CR-02 | Critical/open; negative signed DIVS remainder shift blocks runtime admission. |
| CR-03 | Critical/open; signed bit-31 masks block runtime admission. |
| CR-04 | Critical/open; unchecked/empty generator paths block safe generator qualification. |
| CR-05 | Critical/open; unsigned EOF sentinel blocks safe generator qualification. |
| CR-06 | Critical/open; capacity guards admit out-of-bounds writes and block generator qualification. |
| WR-01 | Medium/open; optimized Python removes replay validation and blocks trusting that path. |
| WR-02 | Medium/open; relative pristine paths break patch normalization/replay claims. |
| REV-LOW-01 | Low/resolved; historical inventory prose count correction remains resolved. |

Every open finding retains exact source references, supported consequences, uncertainty and explicit no-repair status in ACCEPTANCE.md and REVIEW.md. The six source blockers are not new observed crashes; prior selected passes do not qualify their operand/input boundaries.

## Structured rejection and CPU-05 rationale

All five exact task 3 automated commands passed. With `PYTHONOPTIMIZE` removed from each subprocess environment, both `python3 tools/cpu/acceptance.py seal --require-accepted` and read-only `verify --require-accepted` returned exit **1**, each with:

```json
{"decision":"rejected","phase_status":"GAPS_FOUND","reasons":["blocking review finding"]}
```

The existing seal represented actual blockers without schema or identity errors. Normal-Python verification does not resolve WR-01. Integrity checks proved equality of every report field except review/result, unchanged ledger bytes, all 65 source input hashes, archive-review identity and the complete eight-finding ledger. Whitespace/archive-hash checks passed. Final CPU-01–04 unchecked/Pending, CPU-05 checked/Complete and structured rejection checks passed.

CPU-05 alone is Complete because the current explicit reject/defer decision preserves the pre-adaptation effort/patch contract and exact cumulative charges, supplies reproducible commands/results, retains all eight source counterexamples and uncertainties, and prohibits SDK integration while referring repair/replacement direction to blocking plan 01-06 and separate replanning. The independent reviewer confirmed all these criteria after inspecting the sealed result. This referral authorizes no repair, replacement, third attempt or scope change. CPU-01–04 remain Pending; the historical verifier refused grammar preflight without deciding that all four behaviors failed. Task 1's CPU-05 Pending entries are explicitly earlier chronological checkpoints.

## Preserved identities and limits

- Source revision: `94f468326e5e529fd7c54f28434816c27f80f379`.
- Content digest: `81aa0d99145d7b214a7336ae02f9a825eff328c8c26011fd2eef35fbe977b527`.
- Canonical evidence digest: `6dafb025bf1b3ba2a52750cae3e9f50a1db3a552ebb8507edebb8fa2ec493c66`.
- Current review receipt SHA-256: `35bf8e3a849d05e90e7291c9868cffcae014ada4d1607ad3542de7f912e9be6e`.
- Frozen block, budget-ledger, recovery recipes/patches, 56 historical passing records and every source input remain unchanged.
- Two consumed attempts; 2,614 handwritten, 523 helper and 483 semantic lines; 20,005 cumulative / 18,859 final-attempt seconds; six upstream files; two generated files, 36,559 lines / 832,698 bytes. No refunds. Original caps remain 2 attempts, 57,600 cumulative / 28,800 per-attempt seconds, 6 upstream files, 5,000 handwritten / 600 helper / 500 semantic lines, 2 generated files / 50,000 lines / 2,097,152 bytes.
- Preserve odd IRQ crash, fixture UBSan, reset accounting/stale NMI, BSD address-error, malformed-state/zero-request guards, eight continuation checkpoints, 99 state entries, manual oracle ancestry and all earlier failures.
- Native Apple Clang evidence and D-04–D-11 limitations remain historical. No new platform, board/BIOS/game, guest bus-error, bus-cycle suspension, public/durable state or release-support claim is established.

## Task commits

1. `86b8728` — correct acceptance story and expose admission gate.
2. `e09b7f8` — archive prior acceptance report and source review.
3. `94a21e4` — reject current CPU admission and reconcile requirements.

## Deviations from Plan

None in task execution. The generic summary/requirements closeout instruction to copy or complete every plan requirement is constrained by this plan's explicit CPU-01–04 Pending contract and AGENTS.md evidence rules: only CPU-05 is recorded as completed. Git metadata writes needed sandbox escalation; authorized commits succeeded without bypassing hooks or changing checkouts. Closeout corrected the SDK-generated `executedd` typo and generic roadmap progress status so the phase's admission rejection remains explicit; no acceptance scope changed.

## Issues and remaining gate

No known stubs, skipped task validations or new threat surface were introduced. CPU suite execution is outside this governance plan, so no runtime test was skipped as a promised verification. All source blockers/warnings remain unresolved as recorded findings; their disposition does not repair them.

Plan 01-05 is complete. Phase 01 remains open / GAPS_FOUND and Phase 02 gated. Plan 01-06 owns the next blocking developer-direction checkpoint. This executor starts neither that plan nor phase verification.

## Self-Check: PASSED

All created archive files exist; each of the three task commits exists. Exact story validation, both archive comparisons, all five task 3 checks, 65 input hashes, freeze equality and ledger identity passed in this execution. Independent review confirmed the sealed findings and CPU-05 criterion set.
