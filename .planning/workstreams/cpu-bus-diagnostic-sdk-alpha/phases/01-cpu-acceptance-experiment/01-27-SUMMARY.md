---
phase: 01-cpu-acceptance-experiment
plan: "27"
subsystem: evidence
tags: [cpu-acceptance, report-binding, deferred-seal]
requires:
  - phase: 01-26
    provides: canonical gate wording and frozen candidate identities
provides:
  - exact archive and reproduction of the stale security-report binding
  - independently rebound unqualified receipt sealed with admission deferred
affects: [phase-01-verification, cpu-05, owned-cpu-acceptance]
actuals:
  tokens: 323996
  tasks: 3
  commits: 5
tech-stack:
  added: []
  patterns: [append-only evidence recovery, exact report-byte and revision binding]
key-files:
  created:
    - .planning/phases/01-cpu-acceptance-experiment/01-27-CLOSEOUT.json
    - .planning/phases/01-cpu-acceptance-experiment/01-27-SUMMARY.md
  modified:
    - experiments/owned_cpu/acceptance-results.json
    - experiments/owned_cpu/budget-ledger.json
    - experiments/owned_cpu/REVIEW.md
    - .planning/phases/01-cpu-acceptance-experiment/01-SECURITY.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
key-decisions:
  - Preserve the stale active seal and failed reproduction, clearing only supported derived binding metadata.
  - Keep the candidate unqualified and admission deferred until separate fresh phase-goal verification.
requirements-completed: []
coverage:
  - id: D1
    description: Exact stale-binding evidence and append-only recovery preserve source and history.
    verification:
      - kind: other
        ref: 01-27-CLOSEOUT.json archive and receipt/ledger preservation comparisons
        status: pass
      - kind: other
        ref: python3 tools/owned_cpu/contract.py validate and acceptance.py verify
        status: pass
    human_judgment: false
  - id: D2
    description: Independent report bindings produce a current deferred seal with no admission.
    verification:
      - kind: unit
        ref: tests/owned_cpu/test_acceptance.py#AcceptanceControls.test_deferred_seal_binds_review_security_and_never_admits
        status: pass
      - kind: other
        ref: review-check at C2, seal, verify, contract validate, and budget
        status: pass
    human_judgment: false
duration: 110min
completed: 2026-10-04
status: complete
---

# Phase 01 Plan 01-27: Stale security report binding closeout

**Preserved the fail-closed mismatch and rebound exact report bytes in an admission-deferred seal at source checkpoint C2.**

## Performance

- **Duration:** 110 minutes at summary authoring
- **Started:** 2026-10-04T21:04:58.444Z (phase execution); closeout evidence began at 2026-10-04T21:14:00.741794Z
- **Completed:** 2026-10-04T22:55:00Z (summary authoring)
- **Tasks:** 3
- **Files changed:** six plan artifacts; STATE.md and ROADMAP.md also changed in GSD closeout
- **Measured independent intervals:** reviewer 1,338s plus 42s rebind; assessor 1,873s plus 96s rebind and 84s final check

## Accomplishments

- Archived six exact byte payloads and the pre-repair failure. Contract validation passed; acceptance verification reproduced the expected stale sealed security document rejection. A first wrapper capture omitted subprocess streams; exact commands were rerun and the incident was retained.
- Recovered only derived receipt metadata under Plan 01-21's supported procedure. The former active seal is preserved exactly as superseded record 3; all six collections, other receipt fields, the original 45 ledger entries and frozen fields are unchanged.
- Rebound REVIEW and SECURITY independently to C2, e65ea35fe36a0d9cbcbd2f938142f247f3bbf3e2. Sealed report hashes are REVIEW ecbe3c6fe6767ccfe8eb5b81e12223ac8b25a812bddd0b2b3adc335c5d7049ce and SECURITY 27d9974e72c9e58b8131d30883c5555c03665718a32b997bb3d138980d0137e2. Collection, amendment and source-map identities remain cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738, 3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad, and be6e2c45f9590425a227bb9d6622d7629d080cca778eba29d5304bef3bd13a6d.
- The final seal binds C2 and both exact report attestations; admission is deferred and the sole blocker is phase-goal-verification-pending. Independent post-seal comparison matched 39 source identities, 44 artifact hashes, six collections, three superseded seals and the validated budget.
- Ledger charges are append-only: 45 original entries plus 6,425 seconds for initial closeout/reserves and 5,504 seconds for measured overrun and non-refundable replacement-rebind/final-closeout allowances. Final budget is 79,763/115,200 active seconds, 2,565 diagnostic seconds, 1,228 runtime churn lines, 6,540 test/tool churn lines, and no pause.

## Verification

- Normal targeted regression: PYTHONPATH=. python3 tests/owned_cpu/test_acceptance.py AcceptanceControls.test_deferred_seal_binds_review_security_and_never_admits — pass, 1 test.
- Optimized targeted regression: same command with python3 -O — pass, 1 test.
- review-check at C2 — pass, clean.
- seal --defer-admission — pass; unqualified disposition and sole phase-verification blocker retained.
- contract.py validate, acceptance.py verify, and contract.py budget — pass; six collections, no lane blockers.
- Execute-wave schema-drift gate — pass, no drift. Codebase-drift gate skipped because the repository has no STRUCTURE.md.
- Execute:post advisory code review — clean across the three changed closeout evidence artifacts; prior phase review retained as dated history. No blocker or warning.

No runtime, tool, test or collection source changed, and no native qualification was rerun. The assessor found zero current high/critical residuals in this evidence-integrity scope. Its initial 1,873-second interval exceeded reserve by 73 seconds; executor overrun was also charged before replacement checkpoint C2. Both reports rebound at C2, preserving earlier bindings as history.

## Task Commits

1. Task 1 archive and stale reproduction — 2d84fa9.
2. Task 2 derived metadata recovery and checkpoint C — 7ac8e65.
3. Task 3 measured overrun charge and replacement checkpoint C2 — e65ea35.
4. Task 3 report/seal/summary artifact commit — cdcd2e8.
5. Execute:post advisory code-review report — 38abbf4.

## Files Created and Modified

- 01-27-CLOSEOUT.json — six exact byte archives and captured stale-binding reproduction.
- acceptance-results.json — prior seal preserved; current deferred seal binds both independent reports.
- budget-ledger.json — append-only closeout and overrun accounting; caps and churn unchanged.
- experiments/owned_cpu/REVIEW.md and 01-SECURITY.md — independent metadata/source identity rebinds at C2.
- 01-27-SUMMARY.md — scoped execution outcome; CPU-05 is not completed.
- STATE.md and ROADMAP.md — plan progress and next verification position.
- 01-REVIEW.md — Plan 01-27's advisory post-execution code review; earlier phase review preserved in full.

## Deviations and Issues

- The initial output-capture wrapper omitted subprocess streams. Exact commands were rerun immediately; the incident remains documented in the archive.
- The assessor exceeded its reserve by 73 seconds and executor closeout exceeded its original reserve. Measured excess and conservative rebind/final-closeout allowances were added before sealing. No allowance was refunded.
- No source, contract scope, collection, admission status, frozen cap or hardware claim changed.

## Next Phase Readiness

Plan 01-27 execution is complete. Phase 01 remains open and GAPS_FOUND; CPU-01–05 remain Pending, the candidate remains unqualified, Phase 02 is gated, and original-silicon saved PC remains unknown. Next separate command: $gsd-verify-work 01. Do not run it within this execution boundary.

---
*Phase: 01-cpu-acceptance-experiment*
*Plan: 27*
*Completed: 2026-10-04*
