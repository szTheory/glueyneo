---
phase: 04-public-playable-tracer
plan: 45
subsystem: testing
tags: [python, qualification-runner, G3WR-04, G3WR-01, T-04-53, T-04-54]
requires:
  - phase: 04-public-playable-tracer
    provides: 04-44 qualification setup and entry guard
provides:
  - "Guarded .restore/.tmp cleanup in write_frontend_records rollback (G3WR-04)"
  - "Single-copy, ordered timed-out lane output in _terminate_lane_group (G3WR-01)"
affects: [04-49, 04-50]
actuals:
  tokens: 5000
  tasks: 2
  commits: 3
plan_head_before: 9c5c225ea2b905c4e63952bb8f880b47a893e5ab
plan_head_after: d7486e7a4647f4bcfcaa16f9150c861d8d87e044
tech-stack:
  added: []
  patterns: ["every restore and cleanup attempted; failures aggregated by base name", "earlier output once, drained chunks, then communicate tail"]
key-files:
  created: []
  modified: [tools/verify_playable.py, tests/tools/test_verify_playable.py, docs/testing.md]
key-decisions:
  - "A .restore unlink failure is appended to the unrestored base names instead of aborting; .tmp unlink failures are ignored per file"
  - "Lane output is not duplicated: earlier output is decoded and newline-normalized, and dropped from the communicate tail only when the tail begins with it"
requirements-completed: [QUAL-03]
coverage:
  - id: D1
    description: "Rollback cleanup errors never abort restoration or mask the original error"
    requirement: QUAL-03
    verification:
      - kind: unit
        ref: "tests/tools/test_verify_playable.py#test_g3wr_04_restore_unlink_failure_does_not_abort_rollback"
        status: pass
      - kind: unit
        ref: "tests/tools/test_verify_playable.py#test_g3wr_04_temporary_unlink_failure_does_not_mask_the_result"
        status: pass
    human_judgment: false
  - id: D2
    description: "Timed-out lane diagnostics hold each output segment once, in emission order"
    requirement: QUAL-03
    verification:
      - kind: unit
        ref: "tests/tools/test_verify_playable.py#test_g3wr_01_timed_out_lane_output_is_single_copy_in_order"
        status: pass
      - kind: unit
        ref: "tests/tools/test_verify_playable.py#test_g3wr_01_no_earlier_output"
        status: pass
    human_judgment: false
duration: 20min
completed: 2026-10-10
status: complete
---

# Phase 04 Plan 45: Rollback cleanup and lane output Summary

**Guarded `.restore`/`.tmp` cleanup in the evidence rollback plus single-copy, in-order timed-out lane output in tools/verify_playable.py, test-first with docs.**

## Performance

- **Duration:** about 20 min
- **Completed:** 2026-10-10T22:40Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- G3WR-04: `write_frontend_records` rollback no longer aborts when removing a `.restore` file fails; the stray name joins `evidence rollback incomplete: <base names>`, chained from the original error. `.tmp` cleanup is guarded per file.
- G3WR-01: `_terminate_lane_group` no longer seeds drained chunks from `expired.output`; earlier output is recorded once, then drained chunks, then the remaining tail. SIGTERM/SIGKILL/reap ordering unchanged (T-04-54).
- docs/testing.md "Evidence recording" and "Lane timeouts" contracts updated.

## Task Commits

1. **Task 1 RED: reproduce G3WR-04 and G3WR-01** - `aeae3a7` (test)
2. **Task 1 GREEN: fix both** - `930be6b` (fix)
3. **Task 2: docs** - `d7486e7` (docs)

Red failure class line: `FAILED (failures=3)` (no `errors=`); red run at build/playable-qualification/04-45-red-g3wr.txt names `test_g3wr_04_restore_unlink_failure_does_not_abort_rollback`, `test_g3wr_04_temporary_unlink_failure_does_not_mask_the_result` and `test_g3wr_01_timed_out_lane_output_is_single_copy_in_order` as `FAIL:`. `test_g3wr_01_no_earlier_output` is a guard that already passes at base.

Suite: `python3 tests/tools/test_verify_playable.py` ran 94 tests, OK.

## Files Created/Modified
- `tools/verify_playable.py` - rollback cleanup guards; lane output assembly
- `tests/tools/test_verify_playable.py` - 2 `test_g3wr_04_*`, 2 `test_g3wr_01_*`
- `docs/testing.md` - contract bullets

## Decisions Made
See key-decisions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test header false match**
- **Found during:** Task 1 red run
- **Issue:** The `TimeoutExpired` header line quotes the lane program text (containing `LATE`/`EARLY`), inflating counts, so the guard test failed at red for the wrong reason.
- **Fix:** The helper strips the header line before counting. Done before the RED commit.
- **Files modified:** tests/tools/test_verify_playable.py

**Total deviations:** 1 auto-fixed (test-only). **Impact:** none on scope.

## Issues Encountered
None.

## Known Stubs
None.

## User Setup Required
None.

## Next Phase Readiness
tools/verify_playable.py is RECEIPT_BOUND and is re-qualified in 04-50; no RetroArch, clean qualification or CTest ran here. No register row or requirement status was changed.

## Self-Check: PASSED
