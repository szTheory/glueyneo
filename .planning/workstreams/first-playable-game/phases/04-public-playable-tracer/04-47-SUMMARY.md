---
phase: 04-public-playable-tracer
plan: 47
subsystem: testing
tags: [python, review-gate, G3WR-02, G3IN-01, T-04-48, T-04-61]
requires:
  - phase: 04-public-playable-tracer
    provides: 04-46 per-round review provenance
provides:
  - "Generalized ID_PATTERN in tools/independent_review.py (any G<n>CR/WR/IN round, T-NN-NNN threats)"
  - "Malformed-ID rejection in review_ids (fail closed, ID not echoed)"
  - "Leading-$ refusal in glob_contained/path_contained"
affects: [04-49]
actuals:
  tokens: 6000
  tasks: 2
  commits: 3
plan_head_before: e2a2af8cbd139609cdabf47ed1a93b219121725b
plan_head_after: 7ee9ae3c6fad8ec5bff18360663197fc1e896dc6
tech-stack:
  added: []
  patterns: ["one generalized alternation for every review round, enforced on the prompt ID list"]
key-files:
  created: []
  modified: [tools/independent_review.py, tests/tools/test_independent_review.py, docs/testing.md]
key-decisions:
  - "ID_PATTERN is generalized once, not extended per round; the prompt ID list is validated against it."
  - "A leading $ in a pattern or path fails closed, matching the in-group $ rule."
requirements-completed: []
duration: 8min
completed: 2026-10-10
status: complete
coverage:
  - id: D1
    description: "G3+ finding IDs are reviewable; malformed IDs rejected or left OPEN; leading-$ patterns not contained"
    requirement: QUAL-03
    verification:
      - kind: unit
        ref: "python3 tests/tools/test_independent_review.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "docs/testing.md states the reviewable-ID and leading-$ rules"
    requirement: QUAL-03
    verification:
      - kind: other
        ref: "docs contract probe prints review-id contracts ok"
        status: pass
    human_judgment: false
---

# Phase 04 Plan 47: Generalized review IDs and leading-dollar containment Summary

**`ID_PATTERN` now accepts any `(G<n>)?CR/WR/IN-NN` and `T-NN-NNN` ID, `review_ids` rejects malformed prompt IDs, and patterns or paths beginning with `$` are not contained.**

## Task Commits

1. **Task 1 RED:** `d5a41a4` (test) - `test(04-47): reproduce G3WR-02 G3 IDs and G3IN-01 top-level dollar patterns`
2. **Task 1 GREEN:** `c44cb0b` (fix) - generalized ID_PATTERN, malformed-ID ValueError, leading-`$` refusal
3. **Task 2:** `7ee9ae3` (docs) - docs/testing.md review-tool containment bullet

Red failure class line (build/playable-qualification/04-47-red-g3wr_02.txt): `FAILED (failures=3)` with no `errors=` count; `FAIL:` lines include `test_g3wr_02_review_ids_rejects_malformed_ids` and `test_g3in_01_leading_dollar_is_not_contained`.

## Tests

`test_g3wr_02_round_three_and_later_ids_are_reviewable`, `test_g3wr_02_review_ids_rejects_malformed_ids`, `test_g3wr_02_malformed_verdict_lines_leave_the_id_open`, `test_g3in_01_leading_dollar_is_not_contained`. The malformed-verdict test passes at RED by design (the old pattern also ignored those lines). Full module: 70 tests `OK`.

## Deviations from Plan

None - plan executed exactly as written. The red tests avoid `subTest` so each named test yields exactly one `FAIL:` line, matching the acceptance count.

## Known Stubs
None.

## Threat Flags
None. No register row in 04-SECURITY.md was closed (T-04-48 and T-04-61 get evidence only); no requirement was marked complete.

## Issues Encountered
None.

## Next Phase Readiness
Ready for 04-48 onward; 04-49 records the evidence with rows open.

## Self-Check: PASSED
