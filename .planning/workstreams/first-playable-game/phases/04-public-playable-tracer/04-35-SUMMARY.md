---
phase: 04-public-playable-tracer
plan: 35
subsystem: testing
tags: [private-paths, independent-review, security-register, runtime-storage-audit, process-safety]

requires:
  - phase: 04-public-playable-tracer
    provides: 04-34 contained independent review with 11 residual IDs
provides:
  - Test-first repairs for all 11 residual IDs, none outside the 14-file bound
  - Ignored classification and repair accounting consumed by 04-36
affects: [04-36 focused re-review, rights inventory]

actuals:
  tokens: 9000
  tasks: 3
  commits: 12
plan_head_before: cd2b0d846085cdc3b55a66442e909c8d2b47598a
plan_head_after: a84bbc6393002970a545f7f0c9eddce2fe41f8cb
commits: 12

tech-stack:
  added: []
  patterns: [cluster-wise NFKC before casefold, fail-closed on unconfirmed liveness, quiet argparse]

key-files:
  created: []
  modified:
    - tools/private_paths.py
    - tools/verify_playable.py
    - tools/independent_review.py
    - tests/tools/check_runtime_storage.py
    - tests/tools/check_security_register.py
    - tests/tools/test_private_paths.py
    - tests/tools/test_verify_playable.py
    - tests/tools/test_independent_review.py
    - tests/tools/test_check_runtime_storage.py
    - tests/tools/test_check_security_register.py
    - docs/testing.md
    - docs/rights-inventory.md

key-decisions:
  - "T-04-56 and WR-08 are classified gates although their verdicts also cite CMakeLists.txt: the cited defect and fix are in tests/tools/check_runtime_storage.py; CMakeLists.txt was cited as context only and is unchanged."
  - "Malformed stream event shapes are reported as not-contained: malformed-event (fail closed) rather than exit 2."

requirements-completed: []  # QUAL-03, HOST-02, API-05 stay open: 04-36 owns final status

coverage:
  - id: D1
    description: "NFC and NFD spellings of a runtime root and the username token match (T-04-11, T-04-15, T-04-18, T-04-20)"
    requirement: "QUAL-03"
    verification:
      - kind: unit
        ref: "tests/tools/test_private_paths.py#UnicodeCompositionTest"
        status: pass
    human_judgment: false
  - id: D2
    description: "The RetroArch lane never escalates to SIGKILL on an unconfirmed pgrep listing; duplicate review frontmatter keys are rejected (T-04-67, WR-11)"
    requirement: "HOST-02"
    verification:
      - kind: unit
        ref: "tests/tools/test_verify_playable.py#test_t_04_67_unconfirmed_listing_never_escalates_to_sigkill"
        status: pass
      - kind: unit
        ref: "tests/tools/test_verify_playable.py#test_wr_11_duplicate_review_frontmatter_keys_are_rejected"
        status: pass
    human_judgment: false
  - id: D3
    description: "Review tool rejects tilde paths and malformed streams and never echoes argument errors (T-04-61, T-04-65); register gate counts loosely written tables (T-04-62); storage audit parses every Mach-O binding and common symbols (T-04-56, WR-08)"
    requirement: "API-05"
    verification:
      - kind: unit
        ref: "tests/tools/test_independent_review.py, test_check_security_register.py, test_check_runtime_storage.py"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-10-10
status: complete
---

# Phase 04 Plan 35: Residual Repairs Summary

**All 11 residual IDs from the contained 04-34 review were repaired test-first inside the 14-file bound: NFC/NFD-safe private-path scanning, no SIGKILL on unconfirmed liveness, tilde and malformed-stream containment in the review tool, loose-header register tables, and full Mach-O binding coverage in the storage audit.**

## Performance

- **Duration:** about 40 min
- **Tasks:** 3
- **Files modified:** 12 (all within `files_modified`)
- **Commits:** 12 (measured from the plan-head ledger)

## Branch

None. `04-34-branch.txt` is absent, so the full repair path ran.

## Classification and outcome

| ID | Group | Outcome | Test commit | Fix commit |
|----|-------|---------|-------------|------------|
| T-04-11 | runner | repaired | 722127e | 0e8088e |
| T-04-15 | runner | repaired | 722127e | 0e8088e |
| T-04-18 | runner | repaired | 722127e | 0e8088e |
| T-04-20 | runner | repaired | 722127e | 0e8088e |
| T-04-67 | runner | repaired | 20298ab | e069895 |
| WR-11 | runner | repaired | 20298ab | e069895 |
| T-04-56 | gates | repaired | c305352 | 6c96250 |
| WR-08 | gates | repaired | c305352 | 6c96250 |
| T-04-62 | gates | repaired | d1cc1a8 | 499d9ea |
| T-04-61 | gates | repaired | d1cc1a8 | 5f946d0 |
| T-04-65 | gates | repaired | d1cc1a8 | 5f946d0 |

Repaired IDs for 04-36 "Repair to verify": all eleven. No ID is `unrepaired`; there are no open outside-bounds items. `04-33-writable-findings.txt` is empty, so no T-04-56/GWR-02 C-source routing applies. Statuses of every threat, finding and crosswalk row are unchanged; 04-36 owns closure.

Each reproducing test was observed failing for the cited reason before its fix (for example `['(was']` parsed instead of the demoted symbol for T-04-56, a SIGKILL sent after an all-`None` listing for T-04-67, a `TypeError` traceback for T-04-65).

## Decisions Made

- Normalization now composes each base character with its combining marks before casefolding (NFKC, casefold, NFKC); the home username token uses the same form.
- `_recorded_listed` returns `None` when no listing ever succeeded; the lane reports `still-running` instead of signalling.
- D-GAP-01 boundary tests (`equal`, `sibling`, `dotdot`, `symlink`, `relative_inside`) still pass; containment was only strengthened.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Crosswalk state mutation had become a no-op**
- **Found during:** Task 1 (verify run of `tests/tools/test_verify_playable.py`)
- **Issue:** `CrosswalkProvenanceTest.test_rows_must_equal_the_disposition_record` "state differs" set CR-01 to `fixed`, but 04-34 had already made the live row `fixed`, so the mutation asserted "did not change the crosswalk". Failing at the plan start revision, independent of this plan's fixes, and the plan's verify requires the suite green.
- **Fix:** the mutation now toggles away from the live state (`fixed` to `open`, otherwise to `fixed`). The expectation and error regex are unchanged and the mutation is stronger, not weaker.
- **Files modified:** tests/tools/test_verify_playable.py
- **Committed in:** 6125afe

**2. [Rule 1 - Bug] T-04-65 shape test passed review-only arguments to `gate`**
- **Found during:** Task 2 (GREEN run)
- **Issue:** the new test invoked `gate` with `--review` and `--prompt`, which `gate` rejects.
- **Fix:** invoke `gate` with its own arguments; re-verified the test still fails against the pre-fix tool.
- **Committed in:** 5f946d0 (with the fix)

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug). **Impact:** none on scope; both inside the file bound.

## Issues Encountered

- One of four consecutive runs of `tests/tools/test_verify_playable.py` early in Task 1 showed a single failure that did not reproduce in the next five runs; the failing test was not captured. Recorded as an unexplained flake, not investigated further.
- Intermediate fix commits fail the CI rights gate by design (each changes test bytes before the final `docs(04-35): refresh rights inventory` commit rebinds them); the PR must be evaluated at its head (or squash-merged).

## Verification

- `test_verify_playable.py` 73 tests, `test_private_paths.py` 32, `test_independent_review.py` 59, `test_check_security_register.py` 21, `test_check_runtime_storage.py` 15, `test_retroarch_smoke.py` 68: all OK.
- `tools/verify_playable.py --check-docs` passed; `validate_repository_inventory()` returned `passed: True, items: 46`; `tests/workflow/test_public_content.py` 17 OK; `check_security_register.py first-playable-game` PASS.
- `git diff --name-only` since the start revision lists only `files_modified` entries. `pgrep -x RetroArch` exits 1; no RetroArch was launched.
- The real built runtime libraries (`libglueyneo.a`, `libglueyneo_private_runtime.a`) still pass the widened storage audit.

## Known Stubs

None.

## Threat Flags

None. No new network, auth or file-access surface; the changes strengthen existing checks.

## Next Phase Readiness

Ready for 04-36: re-review the eleven repaired IDs plus T-04-SC (04-35) against the committed head, then set statuses and requirement marks under a contained verdict. Use `04-35-repairs.txt` and `04-35-start-rev.txt` (ignored, local) for scope and freshness.

## Self-Check: PASSED

All fix and test commits exist in history, all 12 modified files exist, and every focused suite passed at the plan head.
