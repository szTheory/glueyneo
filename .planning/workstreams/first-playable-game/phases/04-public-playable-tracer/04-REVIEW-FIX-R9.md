---
phase: 04-public-playable-tracer
fixed_at: 2026-10-12T00:00:00Z
review: 04-REVIEW-GAPS-R9.md
review_path: .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-GAPS-R9.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report (Round 9)

**Source review:** 04-REVIEW-GAPS-R9.md
**Iteration:** 1
**Scope:** G9WR-01 (warning), G9IN-01 and G9IN-02 (info; scope `all`). Fixed inside `/gsd-verify-work 04` under the METHODOLOGY rule that a reproducible in-scope Warning is gap work in the same step.

All verification ran in the main checkout (`workflow.use_worktrees: false`).

## Fixed Issues

### G9WR-01: The U+2215 runner-home input lost its leading homoglyph separators

**Commit:** 060ce42 (rights row refreshed in 2b9971e)
**Files:** `tests/tools/test_private_paths.py`
**Fix:** 41611fc built the runner home from parts but bound `.replace("/", "∕")` to the `/work/x` tail only. The expression is now parenthesized, so the scanned value has U+2215 at every separator again, as it did before 41611fc. The focused suite passes (32 tests).

### G9IN-01: The synthetic-path disposition merge has no duplicate or collision guard

**Commit:** 060ce42
**Files:** `tools/public_content.py`
**Fix:** Before the merge, the module refuses duplicate synthetic-path object IDs and any ID that already has a disposition, raising at import instead of letting `dict.update` overwrite silently. The guard runs on every import, so every public-content test and gate exercises it.

### G9IN-02: The noreply email test omits lookalike addresses

**Commit:** 060ce42
**Files:** `tests/workflow/test_public_content.py`
**Fix:** `test_only_listed_noreply_trailer_identities_are_public` now has subtests for three lookalikes: a longer domain, a longer local part, and a subdomain. Each must report `private-identity`. 18 tests pass.

## Gate defects found while recording the dispositions

Recording the G9 rows in the 04-VALIDATION.md crosswalk exposed two defects in `crosswalk_errors` (`tools/verify_playable.py`). Both were fixed in 6510e09, with tests that fail at the parent and pass at the fix:

- **Later-round reviewed paths.** The scope check read reviewed paths from `04-REVIEW.md` only. A finding from a diff-scoped round could therefore not cite the file that round reviewed (here `tools/public_content.py`). `review_round_paths` now unions the frontmatter `files_reviewed_list` of `04-REVIEW.md` and every `04-REVIEW-GAPS*.md` round. Test: `test_scope_may_cite_a_path_reviewed_only_by_a_later_round`.
- **Three-digit threat IDs.** The threat pattern matched exactly two digits. As a result:
  - `_register_threats` skipped every three-digit register row.
  - A scope citing T-04-103 passed only because its T-04-10 prefix is registered.

  One whole-ID pattern now serves both. Test: `test_three_digit_threat_ids_are_read_whole`.

The `tests/tools/test_verify_playable.py` rights row was refreshed in ec6c190.

## History hygiene

The first R9 report text and the first G9WR-01 commit message quoted the literal runner-home path and lookalike email addresses. The history scan at HEAD rejected them. The seven unpushed commits after 1f8eb28 were rebuilt with descriptive wording. In the same rebuild, commit citations were remapped and the history allowlist was regenerated (87d76c8, 149 rows). The pre-rewrite tip is kept on the local branch `backup/first-playable-game-pre-r9-rewrite`, which contains those strings and must not be pushed.

## Independent verdict

The focused round-10 review of the repair diff (`04-REVIEW-GAPS-R10.md`, a05daa7) confirms G9WR-01, G9IN-01 and G9IN-02 fixed and both gate fixes sound. It reports 0 critical, 0 warning and 3 info findings (G10IN-01..03).

Under the METHODOLOGY review-round convergence rule, an Info-only round closes the loop. G10IN-01..03 are therefore deferred to the backlog with reasons in 04-REVIEW-DISPOSITION.md, and no round-11 repair runs in Phase 04.
