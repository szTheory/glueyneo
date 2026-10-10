---
phase: 04-public-playable-tracer
plan: 32
subsystem: qualification-tooling
tags: [independent-review, containment, security-register, gap-closure, ctest]
requires:
  - phase: 04-public-playable-tracer
    provides: "04-31 inline containment, verdict and transcription procedure; 04-25/04-29 register checker"
provides:
  - "tools/independent_review.py: tracked, tested containment (D-GAP-01), verdict parser and transcription check with preflight, gate, verdicts and check subcommands"
  - "check_security_register.py fail-closed on Threat ID table schema drift, --phase NN scope, no-weakening workstream config, quoted verified status"
  - "CTests qualification_independent_review and planning_security_register_consistency; explicit-workstream configure failure"
affects: [04-33, 04-34, 04-36]
tech-stack:
  added: []
  patterns: ["fail-closed gate with report-only evidence for maintainer-accepted threats (D-GAP-02)", "output scanned by private_paths.scan_public"]
key-files:
  created:
    - tools/independent_review.py
    - tests/tools/test_independent_review.py
  modified:
    - tests/tools/check_security_register.py
    - tests/tools/test_check_security_register.py
    - CMakeLists.txt
    - docs/testing.md
    - docs/rights-inventory.md
    - tests/workflow/test_public_content.py
    - experiments/owned_cpu/source-manifest.json
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md
key-decisions:
  - "D-GAP-01: the scratch directory itself is contained (realpath equal or under); the only correction to 04-31 conditions"
  - "Any '..' substring in a path, pattern, glob or base is not contained (fail closed); absolute pattern literal prefix up to the last '/' before the first wildcard must be contained"
  - "D-GAP-02: --maintainer-accepted expects Disposition accept and Status accepted whatever the verdict; the verdict is evidence only"
requirements-completed: [QUAL-03, HOST-02]
status: complete
duration: 6 min
completed: 2026-10-10
commits: 6
plan_head_before: 3a8af0e46d3c3dcae36dbdb7ef6a21fdc3d3ee31
plan_head_after: 098a4210fb65fdc4cc1fc944301cba9bee409e72
actuals:
  tokens: 17000
  tasks: 3
  commits: 6
coverage:
  - deliverable: "Tracked independent-review tool with D-GAP-01 containment"
    human_judgment: false
    verification:
      - {kind: test, ref: "tests/tools/test_independent_review.py", status: pass}
  - deliverable: "Register gate fail-closed (GWR-01), phase scope, no-weakening, quoted verified (GIN-03)"
    human_judgment: false
    verification:
      - {kind: test, ref: "tests/tools/test_check_security_register.py", status: pass}
  - deliverable: "CTest rename and explicit-workstream configure failure (GWR-03)"
    human_judgment: false
    verification:
      - {kind: command, ref: "cmake -DGLUEYNEO_PLANNING_WORKSTREAM=does-not-exist fails with the named message", status: pass}
  - deliverable: "Rights inventory bound to committed bytes"
    human_judgment: false
    verification:
      - {kind: command, ref: "validate_repository_inventory(); rights rows bound 3", status: pass}
---

# Phase 04 Plan 32: Gate-integrity tooling Summary

**Tracked, tested independent-review tool (containment with the D-GAP-01 boundary, verdict parsing, transcription check) plus a register gate that fails closed on schema drift, scopes closure per phase and cannot be weakened by a local config.**

## Accomplishments

- `tools/independent_review.py` holds `has_dotdot`, `path_contained`, `glob_contained`, `external_symlinks`, `containment`, `review_ids`, `parse_verdicts`, `expected_status`, `transcription_errors` and the `preflight`, `gate`, `verdicts`, `check` commands. Zero, duplicate or malformed verdicts, any halt and any non-contained stream are OPEN in tracked code (T-04-48 mitigation).
- D-GAP-01 implemented: equal-to-scratch is contained. No 04-31 condition is relaxed. The documented strengthenings (any `..`, absolute-prefix check, `<scratch>*/x` rejected, `preflight` external-symlink refusal) are tested not to halt an all-in-scratch review that avoids `..`.
- D-GAP-02: `--maintainer-accepted` expects `accept`/`accepted` for listed threats regardless of verdict; a finding ID there is a usage error (exit 2).
- GWR-01: a `Threat ID` table lacking Severity or Status is an error (the real 04-SECURITY.md audit table was caught and renamed `Audited Threat`, header cell only). GWR-03: `planning_security_register_consistency` CTest, empty-means-auto cache default, explicit missing workstream fails configure, `--phase NN`, no-weakening rule, closure gates documented in docs/testing.md. GIN-03 register half: quoted `verified`.
- No threat Status, `threats_open` or disposition changed. Current: `--phase 04` PASS (14 blocking open, per register); `--require-closed --phase 04` exits 1 as expected.

## TDD commit pairs

- Task 1 (tracer, tdd): RED `139bb8d` test(04-32) (54 tests, ERROR from skeleton NotImplementedError, target tests exercised); GREEN `2e45a85` feat(04-32) (54 tests OK, CTest registered). Tracer verified end-to-end (unit suite, CTest, boundary probe printed `boundary ok`) before Task 2.
- Task 2 (tdd): RED `2d55ad8` test(04-32) (11 failures incl. the Sev/State mutation returning code 0 before the fix); GREEN `9c9802a` fix(04-32).
- Task 3: `42a23cf` docs(04-32) rights inventory; rows bound (`rights rows bound 3`), item count assertion 45 to 46 because exactly one row was added (`tests/tools/test_independent_review.py`); this is the true inventory size, not a relaxed expectation.
- Plan start revision (diff baseline): `3a8af0e46d3c3dcae36dbdb7ef6a21fdc3d3ee31`. The 04-SECURITY.md diff from it shows exactly 2 table-row lines (old and new audit header).

## Verification

- `python3 tests/tools/test_independent_review.py` (54 tests) and `test_check_security_register.py` (20 tests) OK.
- `ctest --preset owned-debug`: 63/63 passed (62 plus `qualification_independent_review`). `ctest -N` lists `planning_security_register_consistency` once and `planning_security_register_mutations` once.
- Configure with `-DGLUEYNEO_PLANNING_WORKSTREAM=does-not-exist` fails with `names no .planning/workstreams directory`.
- `verify_playable.py --check-docs` prints `Phase 04 documentation gate passed.`; `pgrep -x RetroArch` exits 1 (no frontend launched).

## Deviations from Plan

**1. [Rule 3 - Blocking] Refreshed owned-CPU source manifest digest for CMakeLists.txt**
- **Found during:** plan-level full CTest
- **Issue:** `owned_cpu_inventory_check` failed `stale source manifest record: CMakeLists.txt` because Task 1/2 changed CMakeLists.txt (same as 04-29).
- **Fix:** updated only the CMakeLists.txt sha256 in `experiments/owned_cpu/source-manifest.json`.
- **Commit:** 098a421

**2. [Rule 3 - Blocking] CMake FATAL_ERROR message split across two string arguments**
- **Found during:** Task 2 verify
- **Issue:** CMake word-wraps a long message so `names no .planning/workstreams directory` landed on two lines and the plan's grep failed.
- **Fix:** an explicit line break after the variable assignment keeps the phrase intact; wording is otherwise as planned.
- **Commit:** 9c9802a

**3. RED skeleton.** The RED commit for Task 1 includes a skeleton `tools/independent_review.py` whose functions raise NotImplementedError, so the tests fail on target behavior rather than on an import error (an import failure is INVALID_RED).

**Total deviations:** 2 auto-fixed (Rule 3), 1 note. **Impact:** none on scope.

Intermediate fix commits fail the CI rights gate by design; the PR must be evaluated at its head (or squash-merged).

## Known Stubs

None.

## Threat Flags

None. New surface (review tool CLI) is covered by T-04-61 and T-04-65 in the plan threat model.

## Self-Check: PASSED

- Files found: tools/independent_review.py, tests/tools/test_independent_review.py.
- Commits 139bb8d, 2e45a85, 2d55ad8, 9c9802a, 42a23cf, 098a421 are ancestors of HEAD.
