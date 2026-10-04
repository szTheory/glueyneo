---
phase: 01-cpu-acceptance-experiment
plan: "22"
subsystem: cpu
tags: [continuation, state-codec, receipt-profile, gap-closure]
requires:
  - phase: "01-21"
    provides: Frozen owned-core continuation evidence and deferred admission seal
provides:
  - Guest-driven fresh-owner continuation for reachable odd PC and selected odd USP states
  - Distinct continuation receipt profile while preserving historical profile denominators
affects: [01-23, 01-24, 01-25, phase-verification]
actuals:
  tokens: 10939
  tasks: 2
  commits: 7
tech-stack:
  added: []
  patterns: [deferred-guest-fault-continuation, versioned-evidence-denominators]
key-files:
  created:
    - .planning/phases/01-cpu-acceptance-experiment/01-22-TASK1-RED.json
    - .planning/phases/01-cpu-acceptance-experiment/01-22-TASK2-RED.json
    - .planning/phases/01-cpu-acceptance-experiment/01-22-SUMMARY.md
  modified:
    - experiments/owned_cpu/cpu.c
    - experiments/owned_cpu/cpu.h
    - experiments/owned_cpu/state-inventory.json
    - experiments/owned_cpu/budget-ledger.json
    - tests/owned_cpu/test_state.c
    - tests/owned_cpu/test_acceptance.py
    - tools/owned_cpu/acceptance.py
key-decisions:
  - "Keep guest-reachable odd PC and selected stack values in private continuation state so execution reports deferred faults after restore."
  - "Preserve owned-p01-c14-1 as historical 13-boundary/78-call evidence; require owned-p01-c14-continuation-2 for current qualification at 15/90."
requirements-completed: []
coverage:
  - id: D1
    description: Fresh-owner continuation reproduces deferred faults after guest-driven RTE and SR stack-bank transitions.
    verification:
      - kind: integration
        ref: "ctest --preset owned-debug -R '^owned_cpu_state$' --output-on-failure --no-tests=error; owned_cpu_state --continuation-only"
        status: pass
    human_judgment: false
  - id: D2
    description: Historical and expanded evidence profiles enforce their exact boundary names and continuation counts.
    verification:
      - kind: unit
        ref: "tests/owned_cpu/test_acceptance.py (22 tests, normal and optimized Python)"
        status: pass
      - kind: integration
        ref: "ctest --preset owned-debug -R '^owned_cpu_inventory$' --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
duration: 23min
completed: 2026-10-03
status: complete
---

# Phase 01 Plan 22: Reachable odd-state continuation and receipt profile Summary

**The private continuation record now preserves guest-reachable odd addresses through a fresh owner, and a new receipt profile binds the expanded evidence without changing historical counts.**

## Performance

- **Duration:** 23 minutes
- **Started:** 2026-10-04T01:41:29Z
- **Completed:** 2026-10-04T02:04:35Z
- **Tasks:** 2
- **Plan files modified:** 7

## Accomplishments

- Added guest-driven `RTE_odd_PC` and `SR_switch_odd_USP` checkpoints. The restored owner reproduces deferred fault behavior with matching frames, ordered bus effects, results, cycles, and guest state; the matrix now contains 15 boundaries and 90 continuation calls.
- Removed only the private restore validator's unconditional PC and selected-stack alignment rejection. Active A7/S-bank consistency and the remaining metadata, callback, counter, reset, and terminal guards remain enforced. Refreshed the private core identity to `f11a282d5f571a67fff687c08cc90a44f5b6ff54bb5334b9c21bf17a4abcbee7` without changing record layout or version.
- Added `owned-p01-c14-continuation-2` for the 15/90 evidence. `owned-p01-c14-1` remains bound to its historical 13/78 denominator, and absent-profile legacy receipts retain their original 12-case interpretation. The real historical sealed receipt verifies unchanged; no real collection or seal was rewritten.
- Preserved the exact `0x4AFC` candidate exclusion and P01-C-13 unknown original-silicon saved PC. CPU-01–05 remain Pending, the candidate remains unadmitted, and Phase 01 remains GAPS_FOUND.

## Task Commits

1. **Task 1: fresh-owner odd-state continuation** — `ef9b767` RED, `7f55bf7` runtime repair, and `7600155` accounting.
2. **Task 2: distinct expanded continuation profile** — `87d0524` RED, `3932594` profile implementation, and `1c98d1a` accounting.

**Plan metadata:** committed with this summary, state, and roadmap update.

## Checks Performed

- Task 1 RED evidence was accepted by the installed GSD checker. Targeted Debug configure/build/CTest passed; the continuation-only executable reported 15 checkpoints, 90 calls, and source destruction/overwrite coverage.
- Task 2 RED evidence was accepted by the installed GSD checker. The standard and optimized Python acceptance suites each passed all 22 tests. The inventory corruption-control CTest passed.
- Final frozen budget validation passed at 45,433 active seconds, 2,565 diagnostic seconds, 1,228 runtime churn lines, and 6,364 test/tool churn lines. No pause was recorded. This plan appended 808 seconds for Task 1 and 455 seconds for Task 2; historical entries and caps are unchanged.
- The full source distribution manifest remains stale for edited files by design; its refresh is owned by Plan 01-24. The private state inventory identity and continuation metadata were updated here.

## Decisions Made

- Keep reachable odd values in private state and defer alignment faults to execution, preserving guest behavior across capture/restore.
- Bind current evidence to a new exact profile while retaining old profile semantics and bindings for historical verification.

## Deviations from Plan

None. Plan 01-24 owns the distribution source-manifest refresh, so its expected stale-source check remains pending until that plan.

## Issues Encountered

None beyond the planned intermediate stale-manifest state.

## Next Phase Readiness

Plan 01-22 is complete. Plans 01-23 through 01-25 remain in order to close CR-02, WR-01, and WR-02. Phase 01 itself is still incomplete/GAPS_FOUND, CPU-01–05 remain Pending, and Phase 02 remains gated. The separate phase-goal verification remains after all gap-closure plans.

## Self-Check: PASSED

Both tasks have passing verification, RED evidence is persisted for each TDD task, historical receipt bytes remain unchanged, and the two append-only accounting records pass the frozen budget validator.

---
*Phase: 01-cpu-acceptance-experiment*
*Completed: 2026-10-03*
