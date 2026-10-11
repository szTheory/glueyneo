---
phase: 04-public-playable-tracer
fixed_at: 2026-10-11T00:00:00Z
review: 04-REVIEW-GAPS-R6.md
review_path: .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-GAPS-R6.md
iteration: 1
findings_in_scope: 3
fixed: 2
partial: 1
skipped: 0
status: partial
---

# Phase 04: Code Review Fix Report (Round 6)

**Source review:** 04-REVIEW-GAPS-R6.md
**Iteration:** 1
**Scope:** G6WR-01, G6WR-02, G6WR-03. The G6IN info items were left alone.

All verification ran in the main checkout, not in a worktree. Each fix has a
regression test that was confirmed to fail on the pre-fix `tools/verify_playable.py`
and pass after it.

## Fixed Issues

### G6WR-02: Duplicate allowlist rows

**Commit:** 4fddcaa
**Files:** `tools/verify_playable.py`, `tests/tools/test_verify_playable.py`
**Fix:** `load_history_allowlist` raises "history allowlist is malformed" when a
(kind, key, revision) triple repeats, instead of letting the last row win.
**Test:** `SquashMergeHistoryTest.test_g6wr_02_duplicate_rows_are_malformed`.

### G6WR-01: History allowlist is self-attested (fixed in part)

**Commits:** 362d6d2 (verification and tests), 0a7ad97 (CTest wiring and docs)
**Files:** `tools/verify_playable.py`, `tests/tools/test_verify_playable.py`, `CMakeLists.txt`, `docs/testing.md`
**Fix:**
- New `history_allowlist_anchor_errors` validates the allowlist against git.
  `base_revision` must resolve to a commit and be an ancestor of the checked head.
  A row whose revision resolves must not be reachable from `base_revision`, which
  puts it outside main's history per the documented scope.
- New `anchored_history_allowlist` drops rows that fail the check, so they become
  strict. It is applied inside `load_frontend_evidence`, `review_provenance_errors`
  and `rights_revision_errors`. `check_docs` also fails with the reason.
- CTest `qualification_history_allowlist` runs `--history-allowlist check`. It is
  registered only in a Git checkout that tracks the allowlist. `docs/testing.md`
  states the trust model.

**Tests:** `test_g6wr_01_forged_base_revision_voids_tolerance` (unresolvable base and
non-ancestor base) and `test_g6wr_01_row_reachable_from_base_is_rejected`.

**Skipped parts, needs user decision:**
- "The revision exists": a row whose revision does not resolve is still tolerated
  on its pin alone. Requiring existence would remove the squash tolerance for
  fresh clones, which is the 2026-10-11 user decision (G5WR-01 scope tolerance).
- The per-record pins stay self-attested. Binding them to history needs a signing
  scheme or removing the tolerance. Both are policy changes.
- The CTest fails by design on a squashed or shallow checkout, because
  `--history-allowlist check` refuses there. It is a pre-ship gate. If the user
  wants it off the default CTest list on the main branch, gate it behind a cache
  option.

### G6WR-03: Rights tolerated branch reads through symlinks

**Commit:** d155f24
**Files:** `tools/verify_playable.py`, `tests/tools/test_verify_playable.py`
**Fix:**
- `_rights_path_is_relative_posix` also rejects empty and `.` segments and
  backslashes, so `a/./b`, `a//b` and a trailing `/` are rejected.
- New `_confined_file_bytes` reads the working-tree file only when no path
  component is a symlink, the target is a regular file and its resolved path is
  under the resolved source root. Otherwise the row reports "working-tree file is
  missing". Git object reads are impossible here because the revision is absent
  by definition, so the fallback from the finding was used.

**Tests:** `test_g6wr_03_symlinked_rights_file_is_not_hashed` and
`test_g6wr_03_symlinked_directory_and_unnormalized_paths_are_rejected`.

## Verification

- `python3 -m unittest tests.tools.test_verify_playable -k g6wr`: 5 tests OK.
  On the pre-fix source: 5 failures and 1 error.
- `python3 tools/verify_playable.py --history-allowlist check`: "History allowlist is current (141 rows)."
- `python3 tools/verify_playable.py --check-docs`: only the expected failure,
  "review findings have no disposition record: G6IN-01, G6IN-02, G6IN-03, G6WR-01, G6WR-02, G6WR-03".
- Full `python3 tests/tools/test_verify_playable.py`: 161 tests in about 96 s, 8
  failures and 5 errors. The same 13 fail on baseline 1f1d953 in a scratch worktree
  (identical failure list). They come from the missing G6 disposition record that
  `check_docs` reports. They are not caused by these fixes.

Not touched: `04-REVIEW*.md`, `04-REVIEW-DISPOSITION.md`, and the two unrelated
`.planning/preparation` files. The fix report is not committed.

_Fixer: Claude (gsd-code-fixer)_

## Follow-up: G6WR-01 residual resolved as deferred

The user asked for the recommended handling of the two open points, and this follow-up applies it:
- **Self-attested pins after the squash:** deferred as an accepted, documented risk under the 2026-10-11 squash-tolerance decision. No signing scheme is added.
- **CTest on squashed checkouts:** `qualification_history_allowlist` is now opt-in (`-DGLUEYNEO_PRE_SHIP_HISTORY_CHECK=ON`). CI's public-content job runs `--history-allowlist check --base <PR base>` on every pull request that changes `docs/history-allowlist.json`, from a full-history checkout.
