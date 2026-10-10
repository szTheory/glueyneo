---
phase: 04-public-playable-tracer
plan: 48
subsystem: testing
tags: [python, retroarch-smoke, G3WR-03, G3IN-02, T-04-66, T-04-47]
requires:
  - phase: 04-public-playable-tracer
    provides: 04-47 review tooling fixes
provides:
  - "run_launch_probe splits Popen and record_child_pid; PID-record failure reports stage pid-record"
  - "compare_launch_probes finding diagnostic-pid-record-failed"
  - "run_smoke pid-record branch raises one SmokeBlocked keeping the OSError class"
affects: [04-49, 04-50]
actuals:
  tokens: 9000
  tasks: 3
  commits: 5
plan_head_before: 48e0c52410ef1f1a03d05ffef2cfd3ce5401d7a9
plan_head_after: f14f29e4d57aff1b72fe9e2428d23d87be8b72cb
tech-stack:
  added: []
  patterns: ["split launch and pid-record failure handling inside one launch_window"]
key-files:
  created: []
  modified: [tests/libretro/retroarch_smoke.py, tests/libretro/test_retroarch_smoke.py, docs/testing.md]
key-decisions:
  - "pid-record is checked first in compare_launch_probes, before survival rules."
  - "run_smoke builds no inner diagnostic for pid-record; the outer handler builds the single one."
requirements-completed: []
duration: 10min
completed: 2026-10-10
status: complete
coverage:
  - id: D1
    description: "Probe and run_smoke report child-PID record failure as pid-record with cause kept; frontend still killed"
    requirement: HOST-02
    verification:
      - kind: unit
        ref: "python3 -m unittest discover -s tests/libretro -p test_retroarch_smoke.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "docs/testing.md smoke-harness bullet true for both paths"
    requirement: HOST-02
    verification:
      - kind: other
        ref: "docs contract probe prints smoke contracts ok"
        status: pass
    human_judgment: false
---

# Phase 04 Plan 48: Smoke pid-record reporting Summary

**The diagnostic probe and `run_smoke` now both report a child-PID record failure as `pid-record` with the OSError class kept, and the comparison finds `diagnostic-pid-record-failed`.**

## Task Commits

| ID | RED (test) | GREEN/docs |
|----|-----------|-----------|
| G3WR-03 | `2ecb47c` | `96a413c` |
| G3IN-02 | `35b5487` | `4ca3218` |
| Docs | - | `f14f29e` |

Red runs: `FAILED (failures=3)` (g3wr_03) and `FAILED (failures=2)` (g3in_02), no `errors=` count (build/playable-qualification/04-48-red-*.txt, ignored).

## Tests

`test_g3wr_03_probe_pid_record_failure_is_not_a_launch_failure`, `test_g3wr_03_probe_popen_failure_is_still_launch` (passes at RED by design; guards the unchanged launch label), `test_g3wr_03_compare_launch_probes_reports_pid_record`, `test_g3wr_03_run_diagnostics_reports_pid_record_finding`, `test_g3in_02_pid_record_detail_keeps_the_error_class`, `test_g3in_02_single_pid_record_diagnostic`. Full module: 77 tests `OK`. All mocked; `pgrep -x RetroArch` exited 1 before and after; no frontend launched.

## Deviations from Plan

None - plan executed exactly as written. A fourth G3WR-03 test (`run_diagnostics`) was added to cover the plan's fourth behavior bullet.

## Known Stubs
None.

## Threat Flags
None. No register row in 04-SECURITY.md was closed (T-04-66 and T-04-47 get evidence only); no requirement was marked complete. No signal mask added; Popen and record_child_pid remain inside one launch_window().

## Issues Encountered
None.

## Next Phase Readiness
Last receipt-bound change of the round; 04-49 records evidence and 04-50 re-qualifies the actual smoke.

## Self-Check: PASSED
