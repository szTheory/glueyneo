---
phase: 04-public-playable-tracer
plan: 61
subsystem: verification-gates
tags: [lane-readiness, rights-path-order, history-docs, G5WR-02, G5IN-01, G5WR-01, halt-carried]
requires:
  - phase: 04-public-playable-tracer
    provides: "04-59 per-row history allowlist gates; 04-60 generator and squash simulation (halted)"
provides:
  - "ProcessGroupTest lane.ready handshake: READY_SECONDS, call-time wait_ready, ReadyPopen gate, startup_delay/ready helper parameters"
  - "rights_revision_errors checks path form before the third_party/ exemption and rejects a non-list items"
  - "docs/testing.md `### History gates after a squash merge` and the extended docs/rights-inventory.md source_revision definition"
affects: [04-62]
tech-stack:
  added: []
  patterns: ["single ready marker plus bounded call-time wait", "Popen subclass gating only the lane argv"]
key-files:
  created: []
  modified:
    - tests/tools/test_verify_playable.py
    - tools/verify_playable.py
    - docs/testing.md
    - docs/rights-inventory.md
key-decisions:
  - "One ready marker, lane.ready; the lane timeout is unchanged and starts only after it exists"
  - "g4_lane re-raises AssertionError so a never-ready child reports its clear message instead of `uncaught AssertionError`; the gate SIGKILLs the never-ready child's group"
status: complete
commits: 4
plan_head_before: 0881ae630078658fa40fc59c64177fb63382f2cf
plan_head_after: 4e9c5b0
actuals:
  tokens: 30000
  tasks: 3
  commits: 4
completed: 2026-10-11
---

# Phase 04 Plan 61: G5WR-02 lane readiness, G5IN-01 rights path order, history-gate docs Summary

Lane-signalling tests now wait (bounded, 30 s, read at call time) for one `lane.ready` marker before the lane timeout starts, `rights_revision_errors` rejects `third_party/../x` and a non-list `items`, and the G5WR-01 history-gate contract is documented; the squash re-run was skipped because 04-60's `scope-split-needed: 6` halt carries.

## Commits

- RED `2b68273` test(04-61): slow-start direct and Runner lane tests, never-ready wait test, `third_party/..` path test, non-list items test
- FIX `a10c8c8` fix(04-61): readiness handshake and rights ordering
- DOCS `44464ec` docs(04-61): `### History gates after a squash merge`, amended Lane timeouts and Rights provenance, extended rights-inventory definition
- REFRESH `4e9c5b0` docs(04-61): rights inventory row for tests/tools/test_verify_playable.py (the only non-third_party row whose bytes changed)

Evidence lines (ignored `build/playable-qualification/04-59-evidence.txt`, re-proven in a detached worktree at the RED commit, exit 1 with `FAILED (`; green in the main checkout):

- `G5WR-02 red 2b682735dade exit 1 green a10c8c8ae2b7 ok`
- `G5IN-01 red 2b682735dade exit 1 green a10c8c8ae2b7 ok`

## ProcessGroupTest dispositions

Measured slow-start Runner test: 5.04 s wall (3 s startup + 2 s lane timeout); it asserts at least 4.5 s from launch to the recorded `TimeoutExpired`, which a lane timeout started before `lane.ready` could not meet (about 2 s). The never-ready test fails with `lane child never became ready: lane.ready` in about 1 s.

| Test | Disposition | Final result |
| ---- | ----------- | ------------ |
| test_timeout_kills_the_whole_lane_group_and_keeps_partial_output | GATED (ready after the grandchild line) | OK |
| test_grandchild_ignoring_sigterm_is_killed_after_a_lane_timeout | GATED (same placement) | OK |
| test_no_group_signal_is_sent_after_the_leader_is_reaped | NOT GATED: fake Proc, no child process | OK |
| test_g2in_02_lane_drains_pipe_during_grace | GATED (direct Popen, ready after signal.signal) | OK |
| lane_output_after_timeout (test_g3wr_01_timed_out_lane_output_is_single_copy_in_order, test_g3wr_01_no_earlier_output, test_g5wr_02_slow_start_direct_lane_keeps_late_output) | GATED (ready after signal.signal and optional EARLY) | OK |
| test_g4wr_01_pipe_held_by_detached_descendant_keeps_earlier_output | GATED (after the sleeper print) | OK |
| test_g4wr_01_crlf_in_drained_segment_is_translated | GATED (after the first write) | OK |
| test_g4wr_01_multibyte_split_across_segments | GATED (after the first write) | OK |
| test_g4wr_03_non_utf8_lane_output_is_recorded | NOT GATED (`ready=False`): normal exit, no signal | OK |
| test_g4wr_03_non_utf8_output_on_the_timeout_path | GATED (after the 0xff write) | OK |
| test_g4wr_03_lane_popen_is_byte_mode | NOT GATED: no timeout path; the gate would replace the Popen patch under test | OK |
| test_d58wr_02_lane_closing_its_pipe_is_still_terminated_on_timeout | GATED by the single marker; asserts `lane child never wrote lane.pid` before reading it | OK |
| test_lane_is_refused_when_an_instance_already_runs, test_lane_is_refused_when_enumeration_fails, test_survivor_* (5), test_escalation_reports_a_group_that_is_still_running, test_t_04_67_unconfirmed_listing_never_escalates_to_sigkill, test_unrecorded_survivor_detail_counts_it_as_not_signalled, test_foreign_survivor_is_reported_and_never_signalled, test_clean_lane_passes_through_the_smoke_result | NOT GATED: `run_lane` with a mock runner, no real lane child | OK |
| test_g5wr_02_slow_start_runner_lane_keeps_late_output | GATED by construction | OK |
| test_g5wr_02_never_ready_child_fails_clearly | exercises `wait_ready` directly | OK |

Full suite: 154 tests OK. `-k ProcessGroupTest` ran three times in a row, 27 tests OK each. The dispositions probe printed `lane readiness dispositions ok`. `docs ok` and `--check-docs` passed (`Phase 04 documentation gate passed.`, no `unverifiable-history:` line).

## Squash simulation re-run: SKIPPED, halt carried

`build/playable-qualification/04-59-branch.txt` holds the 04-60 `review-halt` / `scope-split-needed: 6`. Per this plan's own halt-carry rule the SQUASH-SIM (GEN=1), SIM-CHECK and SUITE-CHECK re-run was not performed, `04-59-squash-simulation.txt` was not appended, and no environmental entry was written. The halt carries unchanged to 04-62. Residual: the 6 history-dependent clone-only suite failures recorded by 04-60 are not repaired here, and G5IN-01 (`rights_revision_errors`) changed after 04-60's simulation, so no simulation covers this plan's final code HEAD. A test that is both history-dependent and satisfied by an ignored `build/` input cannot be distinguished mechanically; any such label is executor-authored and reviewed by the diff-scoped `/gsd-code-review`.

## Deviations from Plan

- **[Rule 1 - Bug] `g4_lane` and `test_d58wr_02` re-raise `AssertionError`.** Found during Task 1: their `except Exception` wrapper would turn the clear `lane child never became ready` failure into `uncaught AssertionError`. Added `except AssertionError: raise` ahead of it; no assertion was changed. The gate also SIGKILLs the never-ready child's process group so it does not linger.
- The Task 3 verify commands for the squash artifacts follow the halt branch (marker present), so they were not run against fresh simulation output.

No auth gates. No stubs. No threat flags beyond the planned T-04-105 (bounded wait, 30 s, polling 0.02 s, proven by the never-ready test in under 5 s). The frontmatter requirement IDs are inherited Phase 04 coverage, not new delivery. `docs/history-allowlist.json` was not committed (04-62 freezes it).

## Next step

Execute plan 04-62 (same `/gsd-execute-phase 04 --ws first-playable-game` run, wave 59), carrying the 04-60 `scope-split-needed: 6` halt.

## Self-Check: PASSED

Commits 2b68273, a10c8c8, 44464ec and 4e9c5b0 are ancestors of HEAD; the four modified files exist.
