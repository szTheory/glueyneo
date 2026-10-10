---
phase: 04-public-playable-tracer
plan: 26
subsystem: testing
tags: [evidence-binding, crosswalk-provenance, documentation-gate, qualification-tools]
requires:
  - phase: 04-public-playable-tracer
    provides: plans 04-24 and 04-25 qualification tooling baseline
provides:
  - mandatory frontend-evidence binding in check_docs with explicit repository/head, fail-closed without Git
  - --clean --check-docs binds the snapshot's evidence to the originating checkout and the snapshot commit
  - stricter validate_frontend_evidence field checks (WR-02)
  - crosswalk_errors(): review crosswalk equals the disposition record and every scope resolves
  - 04-VALIDATION.md crosswalk rewritten to the 24 current disposition records
affects: [04-VERIFICATION gaps 2 and 3, HOST-02, QUAL-03, T-04-46, T-04-38, T-04-43]
status: complete
commits: 5
plan_head_before: fe53ff0f422ce64b18585ea5157200e65dea79d0
plan_head_after: 4baee27084fe8a25de59766eb11439d21385f042
actuals:
  tokens: 20000
  tasks: 2
  commits: 5
tech-stack:
  added: []
  patterns: ["fail-closed binding with explicit repository", "provenance-resolved crosswalk scopes"]
key-files:
  created: []
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md
    - docs/rights-inventory.md
key-decisions:
  - "Evidence binding is mandatory: the repository is the explicit argument or the checked tree's own .git; with neither, check_docs raises rather than skipping."
  - "Tests that accept the tracked evidence pass repository=ROOT and skip without .git, because the snapshot CTest lane has no .git. This is the CR-03 behavior change, not a relaxed expectation."
requirements-completed: []
---

# Phase 04 Plan 26: Evidence binding and crosswalk provenance Summary

`check_docs` now binds tracked frontend evidence to committed bytes in every path (explicit repository, own `.git`, or fail closed), `--clean --check-docs` binds against the originating checkout and snapshot commit with a clean git environment and bounded timeout, and the review crosswalk is checked for exact equality with the disposition record and for resolvable scopes.

## Tasks

| Task | Commit | Notes |
| ---- | ------ | ----- |
| 1 RED | 33cb301 | `test(04-26): add failing evidence-binding regressions` |
| 1 GREEN | ae74669 | `fix(04-26): bind frontend evidence in every check_docs path (CR-03, WR-02, WR-09)` |
| 2 RED | 957a7fb | `test(04-26): add failing crosswalk provenance regressions` (includes the SECURITY/REVIEW/DISPOSITION/PHASE_DIRECTORY constants the tests import) |
| 2 GREEN | ddb891d | `fix(04-26): bind review crosswalk to dispositions, register and reviewed files (CR-05)` (includes the 04-VALIDATION.md crosswalk rewrite) |
| 2 rights | 4baee27 | `docs(04-26): refresh rights inventory for changed test sources` |

04-VALIDATION.md changed only inside the crosswalk section (hunks at old lines 111 and 114, between the `## Review Finding Crosswalk` heading and the next `###`).

## Red runs (observed before each fix)

Task 1 (`python3 tests/tools/test_verify_playable.py`, 32 tests at baseline): `Ran 35 tests ... FAILED (failures=8, errors=2)`:
- `test_evidence_without_a_repository_is_never_accepted` (both `forged_digest=False` and `True`): no `RuntimeError` raised (E2).
- `test_clean_check_docs_binds_to_the_originating_repository_and_snapshot_commit`: `check_docs` was called without `repository`/`head`.
- WR-02 mutations `empty os`, `multi-line os`, `malformed core digest`, `other input mapping`, `boolean marker`: not rejected. `non-dict retroarch` ERROR (`AttributeError`, not a `RuntimeError`).
- `test_explicit_repository_binds_the_copied_evidence`: ERROR (`check_docs` had no `repository` argument).

Task 2: `Ran 38 tests ... FAILED (failures=9, errors=1)`. The rewritten crosswalk was in the working tree for this run so the row mutations applied. Failing: all four `test_scope_references_must_resolve` cases (nonexistent path E4, unreviewed `README.md`, `T-04-99`, `n/a`: not rejected), all five `test_rows_must_equal_the_disposition_record` cases (state, severity, deleted, extra, duplicate row: not rejected), and `test_live_crosswalk_is_accepted` (ERROR, `crosswalk_errors` absent).

Green: 38 tests OK (baseline 32, plus 6 new test methods and 6 new WR-02 subtests).

## Verification

- `python3 tests/tools/test_verify_playable.py`: `Ran 38 tests ... OK`.
- `python3 tools/verify_playable.py --check-docs`: `Phase 04 documentation gate passed.`
- Binding fail-closed snippet: `binding fail-closed ok`. Crosswalk snippet: `crosswalk ok 24`.
- `ctest --preset owned-debug -L qualification-tools`: 5/5 passed.
- Rights inventory: `validate_repository_inventory()` passes; `rights rows bound 1`; the row records SHA-256 `f7d4d6b2...2560` and `source_revision` 957a7fb (the last commit that changed the test file).
- Grep criteria: `if (source_root / ".git").exists():` count 0; `repository=ROOT, head=snapshot.commit` count 1; `EXPECTED_INPUT_MAPPING` count 2.

## Deviations from Plan

**1. [Rule 3 - Blocking] Shared documentation-copy mixin**
- **Found during:** Task 2 tests.
- **Issue:** The new classes needed the same temp-root copy helpers as `ConsumerInputTest`, now also copying the register, review, disposition and every reviewed file.
- **Fix:** Moved the helpers into a `DocumentationCopies` mixin used by `ConsumerInputTest`, `EvidenceBindingTest` and `CrosswalkProvenanceTest`.
- **Files modified:** tests/tools/test_verify_playable.py. **Commit:** 957a7fb.

**2. Red ordering for Task 2.** The tests mutate rows that exist only in the rewritten crosswalk, so the rewrite was present in the working tree (not committed) during the red run to make the red meaningful. The committed order is still test commit, then fix plus rewrite commit.

No auth gates. No stubs introduced. No new threat surface beyond the plan's register (T-04-52 accepted by design: `--check-docs` without `.git` fails closed).

## Known Stubs

None.

## Self-Check: PASSED

Commits 33cb301, ae74669, 957a7fb, ddb891d and 4baee27 exist on the branch; modified files exist; 04-REVIEW.md, 04-REVIEW-DISPOSITION.md, 04-SECURITY.md, 04-VERIFICATION.md, 04-UAT.md and 04-FRONTEND-RECEIPT.json were not edited.
