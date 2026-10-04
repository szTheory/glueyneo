---
phase: 01-cpu-acceptance-experiment
plan: "23"
subsystem: validation
tags: [budget-ledger, monotonicity, inclusive-limits, contributor-docs]
requires:
  - phase: "01-22"
    provides: Repaired guest continuation and distinct current evidence profile
provides:
  - Monotonic cumulative churn validation with named category/entry rejection
  - Inclusive seal budget checks consistent with frozen canonical caps
  - Current README description and repository-relative evidence navigation
affects: [01-24, 01-25, phase-verification]
actuals:
  tokens: 5881
  tasks: 2
  commits: 9
tech-stack:
  added: []
  patterns: [append-only-monotonic-accounting, shared-inclusive-budget-policy]
key-files:
  created:
    - .planning/phases/01-cpu-acceptance-experiment/01-23-TASK1-RED.json
    - .planning/phases/01-cpu-acceptance-experiment/01-23-TASK2-RED.json
    - .planning/phases/01-cpu-acceptance-experiment/01-23-SUMMARY.md
  modified:
    - tools/owned_cpu/contract.py
    - tests/owned_cpu/test_contract.py
    - tools/owned_cpu/acceptance.py
    - tests/owned_cpu/test_acceptance.py
    - README.md
    - experiments/owned_cpu/budget-ledger.json
key-decisions:
  - "Cumulative churn categories are append-only and nondecreasing; any decrease rejects with its category and entry number."
  - "Seal checks use the frozen inclusive caps and reject the canonical pause outcome or an active pause record."
requirements-completed: []
coverage:
  - id: D1
    description: Cumulative churn refunds and hidden threshold crossings reject, while monotonic and exact-limit history remains valid.
    verification:
      - kind: unit
        ref: "tests/owned_cpu/test_contract.py (27 tests, normal and optimized Python)"
        status: pass
      - kind: integration
        ref: "python3 tools/owned_cpu/contract.py budget; python3 tools/owned_cpu/contract.py validate"
        status: pass
    human_judgment: false
  - id: D2
    description: Seal limits match the frozen inclusive policy and README identifies the private, unadmitted candidate with current evidence links.
    verification:
      - kind: unit
        ref: "tests/owned_cpu/test_acceptance.py (22 tests, normal and optimized Python)"
        status: pass
      - kind: integration
        ref: "README local-link check (19 links; none missing)"
        status: pass
    human_judgment: true
    rationale: "A maintainer should confirm that the contributor-facing status and evidence map make the candidate's unadmitted scope clear."
duration: 44min
completed: 2026-10-03
status: complete
---

# Phase 01 Plan 23: Monotonic resource gates and current contributor status Summary

**The ledger now rejects cumulative churn refunds, seal checks accept exact frozen caps, and README describes the implemented private candidate without suggesting admission.**

## Performance

- **Duration:** 44 minutes
- **Started:** 2026-10-04T02:08:30Z
- **Completed:** 2026-10-04T02:52:17Z
- **Tasks:** 2
- **Plan files modified:** 6

## Accomplishments

- Added a copied-ledger counterexample with a penultimate `runtime_added=6001` crossing and a lower final entry. Validation rejects the decrease with reason `cumulative_decrease`; all four category decreases identify the offending field and entry. Equal/increasing histories pass, and a combined added-plus-deleted crossing requires the existing named active pause.
- Changed candidate seal budget checks to use inclusive limits from `contract.py` constants. Each exact cap and all exact caps together pass; limit-plus-one, zero/Boolean/nonnumeric totals, canonical pause-for-review, and an active pause record reject. Frozen values were not changed.
- Updated README to say the private C17 diagnostic runtime is implemented but unadmitted, link the subset/contract/amendment/acceptance and both reviews, preserve exact `0x4AFC` exclusion and unknown original-silicon saved PC, and route maintainers through gap closure and separate phase verification. All 19 local links resolve.
- Kept actual ledger entries append-only. The two task records validate at 48,060 active seconds, 2,565 diagnostic seconds, 1,228 runtime churn lines, and 6,512 test/tool churn lines. No threshold pause is active and the frozen caps remain 115,200 / 6,000 / 8,000.

## Task Commits

1. **Task 1: reject refundable cumulative churn** — `a933c17` RED, `461290a` all-category controls, `7861217` validator repair, and `67ec428` accounting.
2. **Task 2: align seal limits and contributor status** — `e89638b` RED, `306500a` inclusive policy and README, and `86e86bc` accounting.

**Plan metadata:** committed with this summary, state, and roadmap update.

## Checks Performed

- Both Task 1 RED evidence and Task 2 RED evidence were accepted by the installed GSD checker.
- `test_contract.py` passed all 27 tests in normal and optimized Python. `test_acceptance.py` passed all 22 tests in normal and optimized Python.
- `python3 tools/owned_cpu/contract.py budget` and `contract.py validate` passed. The current candidate remains not admitted, CPU-01–05 stay Pending, and Phase 02 remains gated.
- The README local-link check found 19 links and no missing targets. A fresh inventory CTest passed for each task's measured ledger record.

## Decisions Made

- Enforce nondecreasing values independently for runtime-added, runtime-deleted, test/tool-added, and test/tool-deleted lines; never refund a previous cumulative charge.
- Derive seal limits from canonical frozen constants and treat exact equality as within budget; an active pause still blocks.
- Describe implemented behavior and current qualification blockers from the repository's current evidence records, not preparation-era proposals.

## Deviations from Plan

None. No actual ledger history, frozen cap, real acceptance collection, or seal was rewritten.

## Issues Encountered

None. Both intentional RED cases were reproduced and recorded before their implementations.

## Next Phase Readiness

Plan 01-23 is complete. Plans 01-24 and 01-25 remain ordered for source-manifest/evidence refresh and independent current reassessment. Phase 01 remains incomplete/GAPS_FOUND, CPU-01–05 remain Pending, and Phase 02 remains gated. Run separate `$gsd-verify-work 01` only after the remaining gap-closure plans.

## Self-Check: PASSED

Both RED cases are persisted, all specified normal/optimized verification passed, the frozen ledger validates with no pause, and the two new effort records append to the existing history.

---
*Phase: 01-cpu-acceptance-experiment*
*Completed: 2026-10-03*
