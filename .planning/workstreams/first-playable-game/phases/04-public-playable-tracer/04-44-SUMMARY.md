---
phase: 04-public-playable-tracer
plan: 44
subsystem: testing
tags: [python, qualification-runner, T-04-11, error-handling]
requires:
  - phase: 04-public-playable-tracer
    provides: 04-43 security register checker
provides:
  - "entry() CLI guard and guarded qualification setup with typed tokens"
  - "_write_minimal_fail_receipt(token) shared by setup and receipt catch-alls"
affects: [04-45, 04-49, 04-50]
actuals:
  tokens: 6000
  tasks: 2
  commits: 3
plan_head_before: 0e8f7af44a782b2e648130039c3274b18d219e29
plan_head_after: c64060e
tech-stack:
  added: []
  patterns: ["typed sanitized error tokens through emit_error; entry guard wraps main"]
key-files:
  created: []
  modified: [tools/verify_playable.py, tests/tools/test_verify_playable.py, docs/testing.md]
key-decisions:
  - "Setup failures emit `qualification: setup-error: <Type>` and a minimal fail receipt only when OUTPUT exists"
  - "Script entry maps uncaught Exception to internal-error (exit 1) and KeyboardInterrupt to interrupted (exit 130); SystemExit passes through"
requirements-completed: [HOST-02, QUAL-03]
coverage:
  - id: D1
    description: "Setup and entry failures give typed tokens with no traceback or private path"
    requirement: "HOST-02"
    verification:
      - kind: unit
        ref: "tests/tools/test_verify_playable.py -k t_04_11"
        status: pass
    human_judgment: false
duration: 12min
completed: 2026-10-10
status: complete
---

# Phase 04 Plan 44: Qualification setup and entry guard Summary

**T-04-11 closed at the code level: output setup and the script entry now emit sanitized typed tokens (`setup-error`, `internal-error`, `interrupted`) instead of tracebacks.**

## Performance

- **Tasks:** 2 (tracer TDD task, docs task)
- **Files modified:** 3

## Accomplishments
- `OUTPUT.mkdir` and `mkdtemp` wrapped; failures print `qualification: setup-error: <Type>`, write a minimal fail receipt when OUTPUT exists, `receipt: receipt-write-failed` otherwise.
- `entry()` replaces the direct `main()` call in `__main__`; exit 1 / 130, SystemExit untouched.
- `_write_minimal_fail_receipt` extracted; receipt catch-all output unchanged.
- docs/testing.md "Qualification receipt errors" updated, including the import-time limit.

## Task Commits

1. Task 1 RED: `f4961f3` (test) - 6 new `test_t_04_11_*`; red summary `FAILED (failures=5)`, no `errors=`; the argparse pass-through test passes at base by design (regression guard).
2. Task 1 GREEN: `9065363` (fix)
3. Task 2: `c64060e` (docs)

New tests: output_mkdir_error_is_a_typed_token, mkdtemp_error_writes_a_setup_fail_receipt, setup_error_with_failed_receipt_write, entry_maps_uncaught_errors_without_traceback, entry_maps_interrupt_to_130, argparse_exit_passes_through.

## Verification
- `-k t_04_11`: 9 tests OK. Full module: 90 tests OK. Probes print `entry guarded` and `entry contracts ok`. Docs diff has 0 personal-path additions.
- Leaked run directories: `build/playable-qualification/clean-*` count was 22 before and 22 after the t_04_11 run (and after the full suite).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. No RetroArch process was running and none was launched. No register row changed and no requirement was marked complete (per orchestrator instruction); the T-04-11 row stays open for the headless audit.

## Next Phase Readiness
Ready for 04-45 (G3WR-01/G3WR-04 in the same file).

## Self-Check: PASSED
