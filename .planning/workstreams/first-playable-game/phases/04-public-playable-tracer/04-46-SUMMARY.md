---
phase: 04-public-playable-tracer
plan: 46
subsystem: testing
tags: [python, docs-gate, review-provenance, G3WR-05, T-04-38]
requires:
  - phase: 04-public-playable-tracer
    provides: 04-45 qualification runner cleanup fixes
provides:
  - "Per-round review anchors (REVIEW_ROUND_ID, _review_round_anchor, _git_stdout) in tools/verify_playable.py"
  - "Strict descent for closure-bearing dispositions in review_provenance_errors"
  - "Narrowed ordering-only provenance claim in code docstrings and docs/testing.md"
affects: [04-49, 04-50]
actuals:
  tokens: 9000
  tasks: 2
  commits: 3
plan_head_before: 2b71a917b313cc3b9e1be315698d32bf1e1d1b77
plan_head_after: 2e1b4bb03aa13514c8b8303255d1e016cd81ddfd
tech-stack:
  added: []
  patterns: ["gap-round anchor = earliest commit adding the round's review file at the checked head"]
key-files:
  created: []
  modified: [tools/verify_playable.py, tests/tools/test_verify_playable.py, docs/testing.md]
key-decisions:
  - "Gap-round anchors are derived mechanically from git history; no review file was edited."
  - "Descent is strict: a citation equal to its round anchor fails."
requirements-completed: [QUAL-03]
duration: 12min
completed: 2026-10-10
status: complete
coverage:
  - id: D1
    description: "Each closure-bearing disposition is bound to the review round that raised it, with strict descent and fail-closed unknown IDs and uncommitted round files"
    requirement: QUAL-03
    verification:
      - kind: unit
        ref: "python3 tests/tools/test_verify_playable.py -k g3wr_05"
        status: pass
    human_judgment: false
  - id: D2
    description: "docs/testing.md and docstrings state the per-round, strict, ordering-only contract"
    requirement: QUAL-03
    verification:
      - kind: other
        ref: "docs contract probe prints provenance contracts ok"
        status: pass
    human_judgment: false
---

# Phase 04 Plan 46: Per-round review provenance Summary

**`--check-docs` now anchors each non-open review disposition to the review round that raised the finding (04-REVIEW.md `reviewed_revision` or the commit that added 04-REVIEW-GAPS[-R<n>].md) and requires strict descent, with the claim narrowed to ordering only.**

## Performance

- **Duration:** 12 min
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- G3WR-05 fixed test-first: `REVIEW_ROUND_ID`, `_review_round_anchor`, `_git_stdout`, per-round strict-descent errors.
- Docstrings (`review_provenance_errors`, `check_docs`) and docs/testing.md narrowed; the `descends from or equals` wording is gone.
- Real repository still passes: `Phase 04 documentation gate passed.`

## Task Commits

1. **Task 1 RED:** `48bf6e9` (test) - `test_g3wr_05_*` regressions (7 tests)
2. **Task 1 GREEN:** `df7b940` (fix) - per-round anchors with strict descent
3. **Task 2:** `2e1b4bb` (docs) - per-round review provenance documentation

Red failure class line (build/playable-qualification/04-46-red-g3wr_05.txt): `FAILED (failures=6)` with no `errors=` count (the seventh test, open rows need no citation, passes by design).

## Tests
`test_g3wr_05_gap_round_two_closure_must_strictly_follow_its_round_file`, `..._first_gap_round_closure_is_bound_to_its_round_file`, `..._base_round_closure_equal_to_reviewed_revision_is_rejected`, `..._round_file_missing_at_head_fails_closed`, `..._round_file_added_after_head_is_not_committed_at_head`, `..._unknown_finding_id_has_no_review_round`, `..._open_rows_need_no_citation_in_any_round`.

## Adjusted fixtures (both relied on equality being accepted; tested property unchanged)
1. `test_t_04_38_disposition_older_than_reviewed_revision_is_rejected`: the case citing `c1 == reviewed` now expects the `equal to its review round anchor (04-REVIEW.md reviewed_revision)` error instead of `[]`.
2. `test_ancestor_revision_in_either_recognized_form_is_accepted`: cited the first commit, which equals the default reviewed revision; now cites the second commit in the live history, keeping both recognized forms under test.

## Real gate output
`python3 tools/verify_playable.py --check-docs` -> `Phase 04 documentation gate passed.` Full module: 101 tests `OK`.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs
None.

## Threat Flags
None. No register row in 04-SECURITY.md was closed; no requirement was marked complete.

## Issues Encountered
None.

## Next Phase Readiness
Ready for 04-47 (tools/independent_review.py). tools/verify_playable.py is RECEIPT_BOUND and re-qualified once in 04-50.

## Self-Check: PASSED
