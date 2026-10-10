---
phase: 04-public-playable-tracer
plan: 28
subsystem: testing
tags: [retroarch, single-instance, process-group, signal-cleanup, png-decode, qualification-tools]
requires:
  - phase: 04-public-playable-tracer
    provides: plan 04-27 documentation gate and atomic evidence writes
provides:
  - running_retroarch_pids() fail-closed pgrep lister and pre-launch refusal in the smoke
  - PID-scoped bundle-id quit, signal handler, launched-group kill and --child-pid-file
  - Runner.command process-group timeout (LANE_GRACE_SECONDS) and run_frontend_smoke_lane() with before/after instance assertions
  - stable-capture selection, contained and bounded PNG decode, size-checked content read
  - guide "Launch safety" paragraph and refreshed rights rows
affects: [04-VERIFICATION gap 5, HOST-02, QUAL-03, T-04-47, T-04-54, T-04-18]
status: complete
commits: 7
plan_head_before: d31fa7edddc2a062d47cabf3ffca1d02a19fd9e1
plan_head_after: 28e33de3bfa9f9dfd29841ed5d8cc92a4c656300
actuals:
  tokens: 45000
  tasks: 3
  commits: 7
tech-stack:
  added: []
  patterns: ["fail-closed process enumeration before launch", "own-session child with group kill in finally", "lane signals only the PID its own smoke recorded"]
key-files:
  created: []
  modified:
    - tests/libretro/retroarch_smoke.py
    - tests/libretro/test_retroarch_smoke.py
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - docs/first-playable-build.md
    - docs/rights-inventory.md
key-decisions:
  - "The smoke lane moved out of main() into run_frontend_smoke_lane() so the before/after assertions are unit-testable with a stubbed lister; main() keeps its exception handling around the call."
  - "Bundle-id quit is consulted only for a valid pinned identifier, so invalid identifiers still never reach any subprocess."
  - "Survivor signalling is limited to os.killpg(recorded child PID, SIGTERM) when that PID is a survivor and its own group leader; every other survivor is only reported."
requirements-completed: []
---

# Phase 04 Plan 28: RetroArch launch safety Summary

The pinned RetroArch launch no longer stacks, orphans or addresses foreign instances: pre-launch pgrep refusal, PID-scoped quit, SIGTERM-driven group cleanup, process-group lane timeouts, scoped post-lane survivor handling, and hardened capture/decode.

## Tasks

| Task | Commits | Result |
| ---- | ------- | ------ |
| 1 Tracer: refuse to stack, quit own PID | 9d7c3c1 (red), a8c8ad1 | `running_retroarch_pids`, `refuse_stacked_launch` at both launch sites, quit gated on `== {process.pid}` |
| 2 No orphan on outer timeout | bd43ca5 (red), 8a5b4d3 | signal handler + `kill_launched_group`, `--child-pid-file`, `Runner.command` own session + SIGTERM/grace/SIGKILL, `run_frontend_smoke_lane` |
| 3 Captures, decode, docs, rights | 8aa1ef3 (red), c708dc8, 28e33de | IEND + two-sample stability, bounded `decompressobj`, `video` stage wrapping, size check before read, guide paragraph, three rights rows |

## Red runs (observed failing before the fix)

- Task 1: `SingleInstanceTest` ran 43 tests, `FAILED (errors=9)`, each with `AttributeError: ... does not have the attribute 'running_retroarch_pids'`.
- Task 2: `OuterTimeoutTest.test_outer_timeout_leaves_no_fake_frontend_behind` failed with `AssertionError: True is not false : fake frontend survived the outer timeout: pid 33954` (the survivor was killed by hand afterwards; the test cleanup was then fixed to reap by the PID captured in the test body). `ProcessGroupTest` failed: `_retroarch_pids` and `run_frontend_smoke_lane` missing, and the WR-03 log lacked the partial `grandchild <pid>` line (`TimeoutExpired: Command ...` only). The child-pid-file test failed with `FileNotFoundError` on `child.pid`.
- Task 3: `CaptureRobustnessTest` failed 4 failures and 2 errors (truncated IHDR and corrupt IDAT raised `struct.error`/`zlib.error`, zero dimensions accepted, partial and growing PNGs selected, non-GNMV content read before the size check).

## Deviations from Plan

**1. [Rule 3 - Blocking] Existing tests patched `subprocess.run` for `Runner.command`**
- **Issue:** Three tests in tests/tools/test_verify_playable.py mocked `subprocess.run`; the Runner now uses `Popen`.
- **Fix:** Re-pointed them at a fake `Popen` with `communicate()` (same assertions kept).
- **Files modified:** tests/tools/test_verify_playable.py

**2. [Rule 3 - Blocking] Existing smoke tests had no lister stub or IEND trailer**
- **Issue:** Launch-site refusal and the new capture rule broke older fakes (patched `Popen` also intercepts the pgrep call).
- **Fix:** Stubbed `running_retroarch_pids` and added an IEND trailer to synthetic captures in those tests.

**3. [Design] Lane extracted to `run_frontend_smoke_lane()`** so the lane assertions are testable (plan tests required patched `_retroarch_pids`, not a full main()).

## Verification

- `pgrep -x RetroArch` exited 1 (no instance) before and after every test run; no RetroArch was launched. Fake-frontend and `sleep 60` leftovers: none.
- test_retroarch_smoke.py: 52 tests OK (baseline 35). test_verify_playable.py: 52 tests OK. test_private_paths.py OK.
- `python3 tools/verify_playable.py --check-docs`: `Phase 04 documentation gate passed.`
- `ctest --preset owned-debug -L qualification-tools`: 5/5 passed.
- `validate_repository_inventory()` passes; `rights rows bound 3`.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register (T-04-54 mitigated as specified; residual PID-reuse risk accepted).

## Self-Check: PASSED

All commits above exist on the branch; all six modified files exist.
