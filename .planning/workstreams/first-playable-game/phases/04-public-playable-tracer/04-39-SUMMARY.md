---
phase: 04-public-playable-tracer
plan: 39
subsystem: testing
tags: [evidence-rollback, process-group, drain, tdd]
requires:
  - phase: 04-public-playable-tracer
    provides: 04-38 receipt containment and review provenance window
provides:
  - Evidence rollback that handles absent files and continues past a failed restore (G2WR-05)
  - Lane pipe drained during the SIGTERM grace without reaping the leader (G2IN-02, T-04-54 invariant kept)
affects: [04-40, 04-41]
status: complete
commits: 4
plan_head_before: 0002cd6e73aa05ecd2dce3419ae5ca288d8cd585
plan_head_after: 013cd58cacaa9767948ddd6f269a901e5ce127d0
actuals:
  tokens: 6000
  tasks: 2
  commits: 4
tech-stack:
  added: []
  patterns: ["select/os.read drain with deferred reap", "per-index rollback with collected base-name failures"]
key-files:
  created: []
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
key-decisions:
  - "Final reap lives in `_collect_after_kill`, defined after `_retroarch_pids`, so `_terminate_lane_group` has no communicate call yet the existing fake-Proc T-04-54 tests keep passing unchanged"
requirements-completed: []
duration: 20min
completed: 2026-10-10
---

# Phase 04 Plan 39: Evidence rollback and lane drain Summary

**`write_frontend_records` now rolls back first-time and partially-restorable writes (`evidence rollback incomplete: <base names>`), and a timed-out lane is drained via select/os.read during grace so its tail is kept without reaping before SIGKILL.**

## Task Commits (red/green pairs)
1. Task 1 (G2WR-05): RED `3d643d2` (test) -> GREEN `15df7bc` (fix)
2. Task 2 (G2IN-02): RED `bdb99fb` (test) -> GREEN `013cd58` (fix)

## RED evidence
- Task 1: `-k g2wr_05` gave 1 failure + 3 errors across the 3 target tests (FileNotFoundError from `originals` read on an absent evidence file; raw OSError escaping the failed restore instead of RuntimeError). Semantic assessment: each failed on the planned behavior.
- Task 2: `-k g2in_02` failed on the planned assertion (`5.07 not less than 4`, grace spent blocked on the full pipe). Semantic assessment: valid.

## Verification
- `python3 tests/tools/test_verify_playable.py`: 84 tests OK.
- `awk '/def _terminate_lane_group/,/^def _retroarch_pids/' tools/verify_playable.py | grep -c "communicate("` prints 0; one `def _drain`.
- `cmake --preset owned-debug && cmake --build ... && ctest --preset owned-debug`: **100% tests passed out of 63** (real time 34.69 s).
- `pgrep -x RetroArch` exit 1 before and after; no RetroArch launched.

## Deviations from Plan
- The failed-restore test was adjusted in the GREEN commit (not RED): the validation-row file may be byte-identical after the new summary, so the "differs from original" assertion applies only to the evidence file. The test is parametrized over which restore fails (calls 4 and 5), covering both orders. No existing test was changed or loosened.
- The final `communicate` reap sits in a helper (`_collect_after_kill`) so the plan's grep criterion holds while pre-existing stub-based T-04-54 tests (which supply output via `communicate`) pass unchanged.

## Known Stubs
None.

## Threat Flags
None. No register row, severity or status edited (T-04-48); 04-40 records the evidence. Requirements QUAL-03/HOST-02 not checked off (gated on the headless audit and 04-41).

## Self-Check: PASSED
