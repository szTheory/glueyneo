---
phase: 04-public-playable-tracer
plan: 37
subsystem: testing
tags: [independent-review, containment, security-register, retroarch-smoke, tdd]
requires:
  - phase: 04-public-playable-tracer
    provides: 04-36 gap-closure round 2 tooling and R2 review findings
provides:
  - Review-tool containment fails closed on absolute/home/variable alternatives in brace and extglob groups (T-04-61, G2CR-01)
  - 40-hex whole-line revision pin and G2 finding IDs in the review tool (G2WR-03)
  - Register gate counts decimal-phase registers and ignores verified-status case (G2WR-04, G2IN-01)
  - Smoke launch window never drops a deferred signal; pid-record failure has its own reason (G2WR-06)
affects: [04-40, 04-41, 04-42]
status: complete
commits: 6
plan_head_before: 7e6512c125bd10cc9a782e3e49ae5efb289e5694
plan_head_after: 95236847c2ea2af14cda24c4fbfca4875f9907ed
actuals:
  tokens: 5800
  tasks: 3
  commits: 6
tech-stack:
  added: []
  patterns: ["fail-closed regex guard ahead of prefix-based containment", "pending-signal check in finally, chained from body exception"]
key-files:
  created: []
  modified:
    - tools/independent_review.py
    - tests/tools/test_independent_review.py
    - tests/tools/check_security_register.py
    - tests/tools/test_check_security_register.py
    - tests/libretro/retroarch_smoke.py
    - tests/libretro/test_retroarch_smoke.py
key-decisions:
  - "ABS_IN_GROUP refuses any brace/extglob alternative starting with /, ~ or $ regardless of pattern prefix; '(' added to WILDCARDS"
  - "--revision must be exactly 40 lowercase hex (exit 2, value never echoed); first review line must equal the revision line"
  - "REGISTER_NAME fullmatch is the single definition of a register for scoped and unscoped globs"
  - "launch_window raises the deferred signal from finally as SmokeBlocked(interrupted) chained from the body error"
requirements-completed: [QUAL-03, HOST-02, API-05]
coverage:
  - deliverable: "T-04-61 absolute group alternatives not contained"
    human_judgment: false
    verification:
      - {kind: test, ref: "tests/tools/test_independent_review.py#t_04_61", status: pass}
  - deliverable: "G2WR-03 revision pin"
    human_judgment: false
    verification:
      - {kind: test, ref: "tests/tools/test_independent_review.py#g2wr_03", status: pass}
  - deliverable: "G2WR-04 / G2IN-01 register gate"
    human_judgment: false
    verification:
      - {kind: test, ref: "tests/tools/test_check_security_register.py#g2wr_04", status: pass}
      - {kind: test, ref: "tests/tools/test_check_security_register.py#g2in_01", status: pass}
  - deliverable: "G2WR-06 launch window signal"
    human_judgment: false
    verification:
      - {kind: test, ref: "tests/libretro/test_retroarch_smoke.py#g2wr_06", status: pass}
---

# Phase 04 Plan 37: Review-tool, register-gate and smoke-harness R2 fixes Summary

Closed the T-04-61 brace/extglob containment bypass and four further R2 defects (G2WR-03, G2WR-04, G2IN-01, G2WR-06) test-first: each fix has a red `test(04-37)` commit followed by a green `fix(04-37)` commit. No register row, severity or status was edited (04-40 records evidence; the headless audit decides closure).

Duration: about 25 min (start 2026-10-10 ~19:58Z, end 20:24Z). 3 tasks, 6 files.

## Red/green commit pairs

| ID | RED commit | GREEN commit | RED failure count |
|----|-----------|--------------|-------------------|
| T-04-61 (G2CR-01), G2WR-03, G2 finding IDs | c232c64 | 05a21b0 | 7 test methods failing, 18 failures with subtests (6 of the 7 new tests in this task failed on the intended assertion; the scratch-relative-stays-contained assertions already held) |
| G2WR-04, G2IN-01 | a8167a9 | fbb9438 | 3 test methods failing, 5 failures with subtests (non-register-names test fails on the decimal half) |
| G2WR-06 | a863c5d | 9523684 | 2 of 3 failing (signal-survives-raising-body errors with the raw OSError; pid-record reports `launch`); the unchanged-propagation test is a guard and passed |

## Task outcomes

1. Tracer (T-04-61, G2WR-03): `ABS_IN_GROUP` in `glob_contained` before the absolute branch; `(` in `WILDCARDS`; G2CR/G2WR/G2IN in `ID_PATTERN`; `_cmd_check` validates `[0-9a-f]{40}` (InputError "invalid revision", exit 2) and matches the first line as a whole. Probe prints `t-04-61 probe ok`; full suite 66 tests OK. The tracer `<verify>` re-run passed end to end before expansion.
2. G2WR-04/G2IN-01: `REGISTER_NAME` fullmatch over `phases/*/[0-9][0-9]*-SECURITY.md`; `VERIFIED` is `re.IGNORECASE`. Suite 24 tests OK; real registers still `PASS` (04-SECURITY.md=2, 05-SECURITY.md=9, consistency mode only).
3. G2WR-06: pending-signal check in `launch_window`'s `finally`; `run_smoke` splits Popen (reason `launch`) from `record_child_pid` (reason `pid-record`), both inside the launch window so signals stay deferred and cleanup still reaps the started frontend. Suite 71 tests OK.

## Verification results

- `python3 tests/tools/test_independent_review.py`: 66 tests OK.
- `python3 tests/tools/test_check_security_register.py`: 24 tests OK.
- `python3 -m unittest discover -s tests/libretro -p test_retroarch_smoke.py`: 71 tests OK; `-k g2wr_06` 3 tests OK.
- `grep -n '"launch"' tools/verify_playable.py` prints nothing: no smoke-reason allowlist exists outside retroarch_smoke.py, so `pid-record` needs no consumer change. No 04-37 commit touches tools/verify_playable.py.
- `pgrep -x RetroArch` exits 1 (no frontend running). No `pthread_sigmask` call outside the existing warning comment.
- No cmake/CTest run: the full suite is deferred to 04-39 (wave 36). The pinned RetroArch re-qualification of the changed smoke harness is 04-41.

## Deviations from Plan

None - plan executed exactly as written. One execution slip (a first GREEN edit for Task 3 matched the earlier probe launch block and broke syntax) was caught by the first test run and redone before any commit; nothing committed was affected.

Out-of-scope observation (not changed): the diagnostic probe launch path in `retroarch_smoke.py` (around line 768) still records the child PID inside the `except OSError` launch handler, so a PID-record failure there is still labelled `launch`. The plan scoped G2WR-06 to `run_smoke`; consider a follow-up if the probe path matters.

## Known Stubs

None.

## Threat Flags

None. No new network, auth or trust-boundary surface; all changes tighten existing gates. T-04-61, T-04-48, T-04-62, T-04-64 and T-04-66 fix evidence is for 04-40 to record; no register row was changed here.

## Self-Check: PASSED

All six modified files exist; commits c232c64, 05a21b0, a8167a9, fbb9438, a863c5d, 9523684 are ancestors of HEAD; `git rev-list --count` from the ledger base measured 6.
