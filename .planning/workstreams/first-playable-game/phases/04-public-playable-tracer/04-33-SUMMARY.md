---
phase: 04-public-playable-tracer
plan: 33
subsystem: qualification-tooling
tags: [process-groups, signals, provenance, redaction, storage-audit, gap-closure]
requires:
  - phase: 04-public-playable-tracer
    provides: "04-28 lane and smoke process control; 04-32 gate-integrity tooling"
provides:
  - "Lane and smoke process control that never signals a reaped group (T-04-54), escalates only the recorded survivor, defers launch-window signals and sweeps the frontend group while the leader is unreaped"
  - "review_provenance_errors: non-open review dispositions bound to committed ancestor revisions (T-04-38)"
  - "--clean --check-docs exception path recorded as a redacted receipt failure (T-04-11)"
  - "All-or-nothing in-process evidence write; unscannable values fail closed; storage audit without vacuous pass"
affects: [04-34, 04-35, 04-36]
tech-stack:
  added: []
  patterns: ["non-reaping os.waitid WNOWAIT leader check before group signals", "deferred (not masked) signal handling around fork/exec"]
key-files:
  created: []
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - tests/libretro/retroarch_smoke.py
    - tests/libretro/test_retroarch_smoke.py
    - tools/private_paths.py
    - tests/tools/test_private_paths.py
    - tests/tools/check_runtime_storage.py
    - tests/tools/test_check_runtime_storage.py
    - docs/testing.md
    - docs/rights-inventory.md
key-decisions:
  - "GIN-01 (specific-root over-match) and GIN-04 (claim-gate hex limit) are accepted fail-closed limits, each pinned by a regression test and documented in place; 04-34 transcribes them as deferred when the reviewer confirms"
  - "Smoke defers signals in a launch window instead of masking them, because a blocked mask is inherited across fork/exec"
  - "check_docs skips review provenance only when there is neither a repository nor tracked frontend evidence; tracked evidence without a repository still fails closed"
requirements-completed: [HOST-02, QUAL-03, API-05]
status: complete
duration: 13 min
completed: 2026-10-10
commits: 9
plan_head_before: 12044f983bae9b0f3ea2a5ad54c940ee043bce1c
plan_head_after: 907a11c56574570baecf3722fd411cf0828ff090
actuals:
  tokens: 20500
  tasks: 4
  commits: 9
coverage:
  - deliverable: "Process-group safety: no post-reap killpg, survivor SIGKILL escalation on the recorded group only, launch window and group sweep"
    human_judgment: false
    verification:
      - {kind: test, ref: "tests/tools/test_verify_playable.py#ProcessGroupTest", status: pass}
      - {kind: test, ref: "tests/libretro/test_retroarch_smoke.py#LaunchWindowTest", status: pass}
      - {kind: test, ref: "tests/libretro/test_retroarch_smoke.py#LeaderSweepTest", status: pass}
  - deliverable: "Documentation-check exception redaction, review provenance binding, scope parent segments, claim-gate limit pin"
    human_judgment: false
    verification:
      - {kind: test, ref: "tests/tools/test_verify_playable.py#ReviewProvenanceTest", status: pass}
      - {kind: command, ref: "python3 tools/verify_playable.py --check-docs", status: pass}
  - deliverable: "All-or-nothing evidence write, unscannable-value fail-closed, specific-root over-match pin"
    human_judgment: false
    verification:
      - {kind: test, ref: "tests/tools/test_verify_playable.py#AtomicRecordTest", status: pass}
      - {kind: test, ref: "tests/tools/test_private_paths.py#SinkTest", status: pass}
  - deliverable: "Writable-storage audit coverage and non-vacuous result"
    human_judgment: false
    verification:
      - {kind: test, ref: "tests/tools/test_check_runtime_storage.py", status: pass}
      - {kind: command, ref: "ctest --preset owned-debug -R '^runtime_writable_storage'", status: pass}
  - deliverable: "Rights inventory rebound to the six changed test sources"
    human_judgment: false
    verification:
      - {kind: command, ref: "validate_repository_inventory(); rights rows bound 6", status: pass}
---

# Phase 04 Plan 33: Qualification-tool defect closure Summary

**Process-group signalling that never touches a reaped group (WNOWAIT leader checks), recorded-survivor SIGKILL escalation, a deferred launch-window signal handler, review provenance bound to committed ancestors, a redacted clean documentation-error path, an all-or-nothing evidence write and a storage audit that cannot pass vacuously.**

## Accomplishments

- GWR-04a / T-04-54: `_terminate_lane_group` sends SIGTERM, polls `_leader_exited` (non-reaping `os.waitid` with `WNOWAIT`), then SIGKILLs the group while the leader is still unreaped, and only then calls `communicate`. A real-process test shows a SIGTERM-ignoring grandchild is killed; a mocked ordering test (both leader-exits and leader-stuck paths) asserts every `killpg` sees `returncode is None`.
- GWR-04b: the survivor branch escalates SIGTERM to SIGKILL on the recorded group only (`getpgid(recorded) == recorded`), reports `terminated`, `killed`, `still-running` or `not-signalled`, and never signals unrecorded PIDs.
- GWR-05 / T-04-66: the smoke defers termination signals inside `launch_window()` (around `Popen`, `process` assignment and `record_child_pid`) and raises `SmokeBlocked("interrupted")` on window exit so the existing cleanup sees the child. No `pthread_sigmask` (a blocked mask would be inherited by the frontend). `frontend_exited`, `reap_frontend` and `frontend_returncode` replace direct `poll`/`wait` (3 direct calls remain), and the frontend group is swept while the zombie leader pins it.
- T-04-11: `--clean --check-docs` records `documentation-check-error: <Type>` for non-RuntimeError failures and passes RuntimeError text through redaction and the public scan (`private-path-survived` fallback).
- T-04-38: `review_provenance_errors` requires every non-open disposition to cite a revision (`review (04-NN, <hex>)` or ``revision `<40 hex>` ``) that resolves to a commit and is an ancestor of the checked head; digests are ignored. The live record passes.
- GIN-03: crosswalk scope paths containing `..` (or absolute) are rejected. GIN-02: `scan_public_value` raises `PrivatePathError("unscannable-value")`. GIN-01 and GIN-04 accepted and pinned (tests plus in-place documentation).
- GWR-06 / T-04-53: `write_frontend_records` restores replaced files byte-for-byte on a replace failure, writes evidence, validation row, guide block in that order, and documents the crash limit.
- GWR-02 / T-04-56: ELF `C c S s` and Mach-O `__thread_*` sections are covered; zero parsed symbols fail with `no symbols parsed`; an empty `--nm` skips with code 77.

## TDD commit pairs

- Task 1 (tracer): RED `2fb083c` (6 failing target-behavior tests plus 9 launch-window and sweep errors), GREEN `a591132`. Tracer verified end-to-end (both suites green) before the later tasks.
- Task 2: RED `f212b4a` (11 errors, 4 failures), GREEN `688ffdf`.
- Task 3: RED `7bc7d10` (3 failures, 2 errors), GREEN `1764956`.
- Task 4: RED `0966cf9` (6 failures, 1 error), GREEN `a5d2400`, rights refresh `907a11c`.
- Plan start revision (diff baseline): `12044f983bae9b0f3ea2a5ad54c940ee043bce1c`. `git diff` of `tools/private_paths.py` against it touches only `scan_public_value`.

## Counts

- `tests/tools/test_verify_playable.py`: 71 tests OK (was 52 at plan start).
- `tests/libretro/test_retroarch_smoke.py`: 68 tests OK (was 55).
- `tests/tools/test_check_runtime_storage.py`: 13 tests OK (was 7). `tests/tools/test_private_paths.py`: 28 OK.
- `ctest --preset owned-debug`: 63/63 passed, equal to 04-32's count.
- `test_check_security_register.py` and `test_independent_review.py` OK; `check_security_register.py first-playable-game` prints `PASS:`; `verify_playable.py --check-docs` prints `Phase 04 documentation gate passed.`; rights inventory 46 items, `rights rows bound 6`.
- GWR-02 real-library result: `runtime_writable_storage` and `runtime_writable_storage_audit` pass with the widened audit; no writable, common, small-data or thread-local symbol found (empty `04-33-writable-findings.txt`). No open T-04-56/GWR-02 defect.
- No frontend was launched; `pgrep -x RetroArch` exits 1.

## Deviations from Plan

**1. [Rule 1 - Bug] Existing survivor test expected exactly one SIGTERM**
- **Found during:** Task 1 GREEN
- **Issue:** `test_survivor_recorded_as_our_own_child_gets_one_group_sigterm` asserted `assert_called_once_with(8, SIGTERM)`, which contradicts the planned SIGKILL escalation of a survivor that stays listed.
- **Fix:** it now asserts the first call is SIGTERM; the new escalation, exit-after-SIGTERM and still-running tests pin the rest. The `run_lane` helper gained a `later` listing sequence and a `gone_after_sigkill` switch.
- **Files modified:** tests/tools/test_verify_playable.py
- **Commit:** 2fb083c / a591132

**2. [Rule 2 - Missing critical] Provenance gate skipped only with no repository and no tracked evidence**
- **Found during:** Task 2
- **Issue:** existing documentation-copy tests run `check_docs` without a repository or evidence; failing there would break unrelated placeholder assertions, while weakening the evidence-bound path is forbidden.
- **Fix:** `review_provenance_errors` runs whenever a repository is explicit or `source_root/.git` exists; tracked evidence without a repository still fails closed in `load_frontend_evidence`. Documented in the `check_docs` docstring.
- **Commit:** 688ffdf

**3. [Note] `_git_exit` helper instead of `_git`**
- The plan named `_git`, which raises one error for both non-zero exit codes and cannot distinguish an unresolvable revision from a non-ancestor, so a small exit-code helper was added with the same clean environment and timeout.

**Total deviations:** 2 auto-fixed (Rule 1, Rule 2), 1 note. **Impact:** none on scope.

Intermediate fix commits fail the CI rights gate by design; the PR must be evaluated at its head (or squash-merged).

## Known Stubs

None.

## Threat Flags

None. The new surfaces (group signalling, launch window) are covered by T-04-66 and T-04-67 in the plan threat model. Statuses of T-04-54, T-04-11, T-04-38, T-04-53, T-04-56 and T-04-45 change only under the 04-34 contained verdict.

## Self-Check: PASSED

- Files found: tools/verify_playable.py, tests/libretro/retroarch_smoke.py, tools/private_paths.py, tests/tools/check_runtime_storage.py, docs/testing.md, docs/rights-inventory.md.
- Commits 2fb083c, a591132, f212b4a, 688ffdf, 7bc7d10, 1764956, 0966cf9, a5d2400, 907a11c are ancestors of HEAD.
