---
phase: 04-public-playable-tracer
plan: 29
subsystem: testing
tags: [writable-storage, nm, ctest, security-register, rights-inventory, qualification-tools]
requires:
  - phase: 04-public-playable-tracer
    provides: plans 04-25 (register gate validation) and 04-28 (launch safety, rights rows)
provides:
  - runtime_writable_storage CTest (nm-based audit of the runtime library) and its unit tests
  - documented limits of the configure-time sdk_private.h guard
  - planning_security_register registered only when GLUEYNEO_PLANNING_WORKSTREAM exists
  - per-workstream workflow.security_block_on precedence in check_security_register.py
  - rights inventory rows (44 items) for the new and changed tests/tools files
affects: [04-31 review disposition for WR-07, WR-08, HOST-02, QUAL-03, T-04-56, T-04-57, T-04-48]
status: complete
commits: 6
plan_head_before: b9f6e738e4463cb73c50a72f6eebc68b89cea402
plan_head_after: 34af25e783da90d83e25c56268350b0d5e10ac33
actuals:
  tokens: 40000
  tasks: 3
  commits: 6
tech-stack:
  added: []
  patterns: ["nm section/type scan with no allowlist", "workstream config overrides root config, fail closed at both levels"]
key-files:
  created:
    - tests/tools/check_runtime_storage.py
    - tests/tools/test_check_runtime_storage.py
  modified:
    - CMakeLists.txt
    - tests/tools/check_security_register.py
    - tests/tools/test_check_security_register.py
    - docs/testing.md
    - docs/rights-inventory.md
    - tests/workflow/test_public_content.py
    - experiments/owned_cpu/source-manifest.json
key-decisions:
  - "WR-08 is partially repaired: the storage audit is the isolation control, the sdk_private.h guard stays heuristic with limits documented in place. Expected 04-31 disposition: deferred, never fixed."
  - "No writable runtime symbol was found, so nothing was made const or allowlisted."
requirements-completed: []
---

# Phase 04 Plan 29: Runtime storage audit and planning-test gate Summary

`runtime_writable_storage` (nm-based, no allowlist, Windows reports unsupported/skip 77) now proves the runtime library holds no writable or zero-initialized storage, the register CTest is gated on the configured workstream existing, and the register gate honors a workstream's own `security_block_on`.

## Tasks

1. Tracer (50b353a red, 88e1603 fix): `check_runtime_storage.py` with `writable_symbols(output, platform)` and a CLI; `runtime_writable_storage` and `runtime_writable_storage_audit` CTests (label `qualification-tools`, skip code 77); documented guard limits; `GLUEYNEO_PLANNING_WORKSTREAM` cache variable gating `planning_security_register` with a `message(STATUS ...)` explaining the skip; docs/testing.md sections.
2. WR-07 (6c176b8 red, 7f903eb fix): `block_on(root, workstream)` reads the workstream `config.json` first, then `.planning/config.json`; unreadable files and unknown severities fail with `FAIL:` at both levels.
3. Rights inventory (0849335): new rows for the audit script and its tests, refreshed rows for the register-gate files, item count assertion 41 -> 44.

## Red runs (failing-first evidence)

- Task 1: `python3 tests/tools/test_check_runtime_storage.py` ended `ModuleNotFoundError: No module named 'check_runtime_storage'` before the module existed; after it, 7 tests OK.
- Task 2: `python3 tests/tools/test_check_security_register.py` ended `FAILED (failures=4)` (workstream override case plus the three bad-workstream-config subtests); after the fix 9 tests OK.

## Verification

- `runtime_writable_storage` prints `PASS: no writable runtime storage in libglueyneo.a` on this macOS host; `libretro_callback` passes.
- Configure with `-DGLUEYNEO_PLANNING_WORKSTREAM=does-not-exist` printed `planning_security_register not registered: .planning/workstreams/does-not-exist does not exist`, and `ctest -N` listed 0 such tests.
- Full `ctest --preset owned-debug`: 61/61 passed. `check_security_register.py first-playable-game` PASS; `verify_playable.py --check-docs` passed.
- `validate_repository_inventory()` passes at the final commit (44 items); the four rows bind to the last commit that changed each file ("rights rows bound 4").
- `pgrep -x RetroArch` was empty before and after every run; RetroArch was never launched.

## Deviations from Plan

**1. [Rule 3 - Blocking] Refreshed the owned-CPU source manifest digest for CMakeLists.txt**
- **Found during:** full CTest after Task 3
- **Issue:** `owned_cpu_inventory_check` failed `stale source manifest record: CMakeLists.txt` because Task 1 changed CMakeLists.txt.
- **Fix:** updated the CMakeLists.txt sha256 in `experiments/owned_cpu/source-manifest.json`; no other record changed.
- **Commit:** 34af25e

**2. Inventory count baseline change (intentional).** `test_repository_inventory_matches_recorded_fixture_and_dependency_bytes` was asserting 41 while the inventory had 42 (one row from f026401); this plan added two rows, so the assertion is now 44. This is the true inventory size, not a relaxed expectation.

## Residuals and notes

- WR-08: the configure-time guard remains heuristic (direct .c/.cpp sources, top-level targets, no generator-expression links, static builds only). Expected 04-31 disposition `deferred` with this rationale in the Source cell, only if the contained reviewer confirms; otherwise `open`.
- The untracked `.planning/workstreams/first-playable-game/config.json` (user file) was not touched or committed; the new precedence reads it when present, and it did not change the register result.
- The Task 3 intermediate commits (50b353a through 7f903eb) fail the CI rights gate by design; the final commit passes.
- No stubs, no new network/auth/file surface beyond planned items.

## Self-Check: PASSED

All created files exist and commits 50b353a, 88e1603, 6c176b8, 7f903eb, 0849335, 34af25e are ancestors of HEAD.
