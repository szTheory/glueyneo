---
phase: 04-public-playable-tracer
plan: 27
subsystem: testing
tags: [documentation-gate, guide-claims, atomic-write, qualification-tools]
requires:
  - phase: 04-public-playable-tracer
    provides: plan 04-26 evidence binding in check_docs
provides:
  - guide_claims_outside_block() and PINNED_REVISIONS in tools/verify_playable.py
  - check_docs rejects requirement IDs, revision-like hex and status words outside the generated block, and private roots anywhere in the guide
  - write_frontend_records validates, scans, then writes the three evidence files through temp files and os.replace
  - docs/first-playable-build.md prose with no outside-block claims and documented gate rules and limits
affects: [04-VERIFICATION gap 3, HOST-02, QUAL-03, T-04-34, T-04-45, T-04-53]
status: complete
commits: 5
plan_head_before: cacd7fdf0cfc0f0b5b4ddf8aeee7008118f3f5d8
plan_head_after: 682e7c270ee28104952ac3333e6812af47931137
actuals:
  tokens: 22000
  tasks: 2
  commits: 5
tech-stack:
  added: []
  patterns: ["validate-all then scan-all then atomic replace", "claim-token gate outside a generated block"]
key-files:
  created: []
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - docs/first-playable-build.md
    - docs/rights-inventory.md
key-decisions:
  - "Outside the generated block the guide may carry no requirement ID, no 7-40 char revision-like hex other than the pinned YMFM/Z80 revisions, and no capitalized completion/qualification status word. The guide names these words only indirectly so its own prose passes the gate."
  - "Other prose is documented as not a qualification claim and not machine-checked."
requirements-completed: []
---

# Phase 04 Plan 27: Guide claims and atomic evidence writes Summary

The documentation gate now rejects status claims and private roots outside the generated frontend block, the guide prose was rewritten to match the evidence, and `--record-frontend-evidence` computes, scans and replaces all three files atomically.

## Tasks

1. Tracer: `GuideClaimTest` (4 tests), `guide_claims_outside_block`, `PINNED_REVISIONS`, full-guide private-path scan in `check_docs`, and guide rewrite. Commits a684c2a (red), 5aa114a (fix).
2. `AtomicRecordTest` (3 tests) and the rewritten `write_frontend_records`. Commits 9575b3e (red), 959bab6 (fix), 682e7c2 (rights inventory row for `tests/tools/test_verify_playable.py`, source_revision 9575b3e, the last commit that changed it).

## Red runs (failing before the fix)

- GuideClaimTest at a684c2a: `FAILED (failures=6, errors=1)` - five appended claims and the U+2215 private path did not raise `RuntimeError`; `test_live_guide_has_no_outside_block_claims` errored because `guide_claims_outside_block` did not exist.
- AtomicRecordTest at 9575b3e: `FAILED (failures=2)` - `test_missing_validation_row_leaves_all_three_files_unchanged` and `test_private_root_in_generated_block_leaves_all_three_files_unchanged` observed the old writer mutating files before failing.

## Verification

- `python3 tests/tools/test_verify_playable.py`: Ran 45 tests, OK (38 at the start, 42 after Task 1 tests, 45 after Task 2 tests).
- `python3 tools/verify_playable.py --check-docs`: `Phase 04 documentation gate passed.`
- Task 1 snippet printed `guide claims ok`; outside-block requirement-ID grep count is 0; stale-phrase greps 0; `--clean --check-docs` appears twice in the guide; no diff line touches the generated block; no `/Users` or `/home` path in the guide.
- `validate_repository_inventory()` passed (42 items); `rights rows bound 1`.
- `ctest --preset owned-debug -L qualification-tools`: 5 tests passed.

## Deviations from Plan

**1. [Rule 1 - Bug] Gate sentence named the banned status words**
- **Found during:** Task 1
- **Issue:** the first draft of the new rules paragraph spelled out the three rejected words, so the guide failed its own gate.
- **Fix:** the paragraph now refers to "the capitalized completion and qualification status words listed in `tools/verify_playable.py`".
- **Files modified:** docs/first-playable-build.md
- **Commit:** 5aa114a

**Total deviations:** 1 auto-fixed. **Impact:** none on scope.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

All five commits are ancestors of HEAD; the four modified files exist; the recorded rights row matches the committed bytes. 04-FRONTEND-RECEIPT.json, the generated status block and the review/security/verification/UAT documents were not edited.
