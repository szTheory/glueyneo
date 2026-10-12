---
phase: 04-public-playable-tracer
plan: 30
subsystem: testing
tags: [private-paths, otool, retroarch-smoke, rights-inventory, qualification-tools]
requires:
  - phase: 04-public-playable-tracer
    provides: plans 04-24 (anchored generic roots) and 04-29 (rights inventory at 44 items)
provides:
  - bare-username token check narrowed to GitHub Actions service accounts (SERVICE_ACCOUNT_NAMES)
  - repository-relative paths pass the JSON-form receipt scan
  - qualification_check_package CTest with full-path otool parsing and macOS system-path allowlist
  - dead smoke checks removed (IN-02)
  - rights inventory at 45 items
affects: [04-31 review disposition for WR-06, IN-02, IN-03, T-04-58, T-04-59, T-04-60]
status: complete
commits: 6
plan_head_before: 5343e25d43489daee60acf71bfa6d312dfd52a22
plan_head_after: d92686291f889a86f91a49ceaf3a7a2b7ea548fa
actuals:
  tokens: 30000
  tasks: 3
  commits: 6
tech-stack:
  added: []
  patterns: ["generic account name relaxed only under GITHUB_ACTIONS", "JSON-serialization scan checks specific roots only; generic roots are checked per decoded string"]
key-files:
  created:
    - tests/consumers/test_check_package.py
  modified:
    - tools/private_paths.py
    - tests/tools/test_private_paths.py
    - docs/testing.md
    - tests/libretro/retroarch_smoke.py
    - tests/libretro/test_retroarch_smoke.py
    - tests/consumers/check_package.py
    - CMakeLists.txt
    - docs/rights-inventory.md
    - tests/workflow/test_public_content.py
    - experiments/owned_cpu/source-manifest.json
key-decisions:
  - "WR-06: bare home-name token is skipped only when the casefolded name is in SERVICE_ACCOUNT_NAMES and GITHUB_ACTIONS is true; residual accepted as T-04-60 and documented in docs/testing.md."
  - "scan_public_value scans the JSON serialization for specific roots and the username only, because JSON punctuation makes every value start look like a path start and flagged repository-relative tmp/home/x."
---

# Phase 4 Plan 30: Private-path token narrowing and core dependency hardening Summary

Generic CI account names and repository-relative inventory paths now pass the receipt scan, while personal names, developer hosts and every home-path form stay rejected. The smoke lost its redundant checks, and the installed-core check reads full `otool -L` paths and rejects non-system dependencies on macOS.

## Tasks

| Task | Commits | Result |
| ---- | ------- | ------ |
| 1 (tracer) WR-06 | 3e14a0e (red), a08641a (fix) | `ServiceAccountTest` plus inventory-path cases; `SERVICE_ACCOUNT_NAMES`; docs "Private-path scan limits" |
| 2 IN-02, IN-03 | be62392 (red), d17ec0a (fix) | `IdentityCheckTest`, `tests/consumers/test_check_package.py`, `qualification_check_package` |
| 3 rights inventory | 2f3c9aa | new row for `test_check_package.py`, refreshed 3 rows, count 44 to 45 |
| (manifest refresh) | d926862 | `CMakeLists.txt` digest in `experiments/owned_cpu/source-manifest.json` |

## Red runs

Task 1 (`python3 tests/tools/test_private_paths.py` before the fix): `FAILED (failures=1, errors=2)`:
- `ERROR test_generic_runner_name_passes_under_github_actions` (`PrivatePathError: private-path-survived` on "the runner wrote a receipt")
- `ERROR test_repository_relative_inventory_paths_pass`
- `FAIL test_runner_receipt_is_written_under_github_actions` (`'fail' != 'pass'`)

The non-CI `build` and personal `alice` cases already raised, as intended, and stay in the suite.

Task 2 (`python3 tests/consumers/test_check_package.py` before the fix): `FAILED (failures=3, errors=1)`; the spaced path returned as `['/Library/Application', ...]`, and `/opt/homebrew/lib/libz.1.dylib` raised no `CheckError`. In `IdentityCheckTest`, `test_validate_inputs_has_no_redundant_pattern_check` failed (the regex and bounds comparison still present). The two bundle-id refusal cases and the truncated-bundle case passed before and after, since the pinned equality already refused them; they guard the removal.

## Deviations from Plan

**1. [Rule 1 - Bug] JSON-form scan flagged repository-relative `tmp/home/x`**
- Found during: Task 1 red run.
- Issue: `scan_public_value` scans `json.dumps(value)`; the `": "` punctuation before a value counts as a path start, so a value beginning `tmp/` matched the generic `/tmp/` root. This was the actual cause of the WR-06 inventory-path failure.
- Fix: the serialization scan checks specific roots and the username only; generic roots are checked per decoded string and key. Non-JSON leaves (stringified by `default=str`) are now scanned as strings so they stay covered.
- Files: `tools/private_paths.py`. Commit: a08641a.

**2. [Rule 1 - Bug] macOS allowlist rejected the core's own install name**
- Found during: Task 2 verification against the built core. `otool -L` lists `@rpath/glueyneo_libretro.dylib` first.
- Fix: dependencies whose basename equals the core's own name are exempt; added `test_own_install_name_line_is_not_a_dependency` (added with the fix, not observed red) and verified `check_core_self_contained` on the real built core. Commit: d17ec0a.

**3. [Rule 3 - Blocking] Source manifest digest stale after the CMakeLists.txt edit**
- `owned_cpu_inventory_check` failed; refreshed the digest as in 34af25e. Commit: d926862.

Task 3 changed the inventory count assertion in `test_repository_inventory_matches_recorded_fixture_and_dependency_bytes` from 44 to 45 (one new row).

## Test change note

`test_scan_rejects_the_bare_local_username` now skips only when the live home name is in `SERVICE_ACCOUNT_NAMES` and `GITHUB_ACTIONS` is `true`. This is the WR-06 behavior change, not a relaxed expectation; the patched `alice` and non-CI `build` cases keep the rejection.

## Verification

- `test_private_paths.py` (26 tests), `test_check_package.py` (5), `test_retroarch_smoke.py` (55), `test_verify_playable.py` (52): OK.
- `ctest --preset owned-debug`: 100% passed (62), including `qualification_check_package`.
- `verify_playable.py --check-docs` passes; `validate_repository_inventory()` passes with 45 items; "rights rows bound 4".
- `pgrep -x RetroArch` empty before and after; RetroArch was never launched.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

Commits 3e14a0e, a08641a, be62392, d17ec0a, 2f3c9aa, d926862 present; `tests/consumers/test_check_package.py` exists.
