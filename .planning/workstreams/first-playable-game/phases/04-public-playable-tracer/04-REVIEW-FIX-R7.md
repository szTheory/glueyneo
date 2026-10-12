---
phase: 04-public-playable-tracer
fixed_at: 2026-10-11T00:00:00Z
review: 04-REVIEW-GAPS-R7.md
review_path: .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-GAPS-R7.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report (Round 7)

**Source review:** 04-REVIEW-GAPS-R7.md
**Iteration:** 1
**Scope:** G7CR-01, G7CR-02, G7WR-01, G7WR-02, G7WR-03. G7IN-01 is optional, but the fix was trivial, so it was fixed as well (not counted in scope).

All verification ran in the main checkout (`workflow.use_worktrees: false`). The public-content and CI-step checks were repeated in a scratch single-branch clone of the committed HEAD, with a generic CI account profile, the GitHub Actions flag set and no temporary-directory override, to approximate the CI runner. Each code fix has a regression test, and each test was confirmed to fail on the pre-fix `tools/verify_playable.py`.

## Fixed Issues

### G7CR-02: Allowlist generated against a stale local `main`

**Commits:** 6103b9e (code, CTest, docs), 1b7c726 and 91f51ac (allowlist regenerated)
**Files:** `tools/verify_playable.py`, `tests/tools/test_verify_playable.py`, `CMakeLists.txt`, `docs/testing.md`, `docs/history-allowlist.json`
**Fix:**
- `--base` now defaults to `origin/main` (`HISTORY_DEFAULT_BASE`). If the base does not resolve, the generator refuses with a clear message (`git fetch origin` or `--base`). It no longer falls back to whatever local branch is called `main`.
- The opt-in CTest passes `--base "${GLUEYNEO_HISTORY_BASE}"`, a new cache variable that defaults to `origin/main`. The pre-ship step in docs/testing.md now runs `git fetch origin` and then checks against `origin/main`.
- The allowlist was regenerated with `--history-allowlist write --base origin/main`. `base_revision` moved from 2e5d8849a57f to 4b2120d57f48, and the 12 rows already reachable from main are gone (145 → 133 rows). This corrects the base. It is not a regeneration done to get a green result, and the commit messages say so.

**Test:** `test_g7cr_02_default_base_is_the_upstream_main_ref`. The CLI test now passes `--base main` explicitly.

### G7CR-01: Stale `tests/tools/test_verify_playable.py` rights row

**Commits:** b4c6f19 (generator hardening), 1b7c726 and 91f51ac (row refresh plus allowlist)
**Files:** `tools/verify_playable.py`, `tests/tools/test_verify_playable.py`, `docs/rights-inventory.md`, `docs/history-allowlist.json`
**Fix:**
- `history_allowlist_document` now refuses to list a rights row unless the file at the checked head holds the recorded SHA-256. That is the post-squash predicate, so `check`, the CTest and the CI step all catch this class of error.
- The row now records the HEAD bytes: sha256 `2d5fdf587a08...` at source_revision `e71e283b9cb7`, which is the last commit that touches the file and holds exactly those bytes. The test file was edited after the first refresh (1b7c726), so the row was refreshed again in 91f51ac. No other rights row's file was edited this round.

**Test:** `test_g7cr_01_generator_refuses_rights_row_stale_at_head`.

### G7WR-03: Tolerated rights branch hashed working-tree bytes

**Commit:** 7279358
**Files:** `tools/verify_playable.py`, `tests/tools/test_verify_playable.py`, `docs/testing.md`, `docs/rights-inventory.md` (prose only)
**Fix:** A new `_head_blob` reads the entry with `git ls-tree -z <head> -- <path>`. It accepts only a regular blob (100644 or 100755) and hashes `git cat-file blob <oid>`. A committed symlink, a path through a symlinked directory and a missing entry all report "file at the checked head is missing". `_confined_file_bytes` is removed, and the path-form validation stays. The docs now say "file at the checked head".
**Tests:** `test_g7wr_03_tolerated_rights_row_ignores_working_tree_bytes` covers dirty, deleted and untracked files. The G5WR/G6WR digest and symlink tests now commit their tampering.

### G7WR-02: CI step ran only when the allowlist changed

**Commit:** 13c7a37
**Files:** `tools/verify_playable.py`, `tests/tools/test_verify_playable.py`, `.github/workflows/ci.yml`, `CMakeLists.txt` (comment), `docs/testing.md`
**Fix:**
- New `--history-allowlist ci --base <rev>` mode. `--base` is required in this mode.
- The CI step runs on every pull request (the job already uses `fetch-depth: 0`), so the step itself does not decide by path. The tool decides whether the check applies, and it fails safe. The full `check` runs whenever the allowlist differs from the base (a failed diff counts as a difference). It also runs whenever any listed revision is an ancestor of the head, which is true for every pull request from the pre-ship branch. It is skipped only for an unchanged allowlist none of whose rows is in the history, which describes every pull request after the squash.
- **Deviation from the review:** I did not add the suggested history-independent `stale` gate. After the squash, a legitimate rights refresh voids a listed row, and the allowlist can no longer be regenerated, so failing on that row would leave main stuck with no way to proceed. docs/testing.md records this.

**Tests:** `test_g7wr_02_ci_mode_checks_every_pre_ship_pull_request` and `test_g7wr_02_ci_mode_after_the_squash`.

### G7WR-01: Anchoring overstated as protection

**Commits:** 04dd69c (docs and docstring), e71e283 (test isolation)
**Files:** `docs/testing.md`, `tools/verify_playable.py` (docstring only), `tests/tools/test_verify_playable.py`
**Fix:**
- docs/testing.md now says the in-tree anchoring is a consistency check that cannot change a gate outcome. Forged or invented rows are caught only by the CI `--history-allowlist ci` step before merge. The code path is unchanged; I took the review's first option.
- e71e283: `test_t_04_38_unresolvable_reviewed_revision_fails` checked against the first commit with the live allowlist copied in. Since G6WR-01, the anchor error fired before the reviewed-revision gate under test. In round 6 the missing-disposition error hid this, and the test fails the same way with the bb0f4eb tool. The test now removes the copied allowlist, so every row is strict. The assertion is unchanged.

### G7IN-01 (info, optional): Misleading `--check-docs` error on a shallow clone

**Commits:** 9dcff1e, c5eb9e3 (narrowed)
**Files:** `tools/verify_playable.py`, `tests/tools/test_verify_playable.py`, `docs/testing.md`
**Fix:** `check_docs` reports a `base_revision` that is missing from the repository before the frontend gate runs. Every other anchor error keeps its earlier place after the crosswalk check. docs/testing.md says `--check-docs` needs the history back to `base_revision`.
**Test:** `test_g7in_01_check_docs_reports_unanchored_allowlist_first`.

## Planning records (uncommitted, for the orchestrator)

- `04-REVIEW-DISPOSITION.md`:
  - Six G7 rows were added, all `fixed`, with the "verdict pending the next diff-scoped review" wording and full revision citations. The frontmatter total is now 75.
  - G6WR-02 now reads "Confirmed fixed by 04-REVIEW-GAPS-R7.md".
  - G6WR-03 now reads "Confirmed fixed for symlinks and unnormalized paths; the residual is tracked as G7WR-03".
- `04-VALIDATION.md`: six crosswalk rows were added. The scope paths are limited to the files listed in 04-REVIEW.md: `docs/rights-inventory.md` and `tools/verify_playable.py`.
- `docs/history-allowlist.json` was regenerated against the working tree that holds those records (145 rows). The committed version (133 rows) matches the committed records. **Commit these three files together.** The G6 row edits and the new G7 rows citing branch commits change review_citation pins and rows. If the allowlist is not regenerated with them, `check` reports stale.

## Verification

| Check | Result |
|---|---|
| `python3 -m pytest tests/tools/test_verify_playable.py -q` | pytest is not installed in any local interpreter. Ran it with `uvx --from pytest pytest`: 159 passed, 8 failed. All 8 failures are in `ProcessGroupTest`. The same 8 fail under pytest at baseline bb0f4eb, which points to a pytest-harness incompatibility; they pass under unittest. |
| `python3 tests/tools/test_verify_playable.py` (the CTest runner), final state | **Ran 167 tests, OK** |
| `python3 tools/verify_playable.py --history-allowlist check --base origin/main` | current: 133 rows at committed HEAD, 145 rows with the uncommitted records |
| `--history-allowlist ci --base 4b2120d5...` in a clean clone of HEAD 91f51ac | applies, then current (133 rows), exit 0 |
| `python3 tools/verify_playable.py --check-docs` | **passes**, but only with the uncommitted G7 disposition rows present. At committed HEAD alone it reports the G7 findings as undispositioned until the orchestrator commits the records. |
| `python3 tools/verify_sdk.py --suite public-content` | **The rights section passes** (`rights.passed: true`; the G7CR-01 rights-digest failure is gone). The overall outcome still fails, on 117 history `personal-path` findings in blobs that exist only on this branch (for example `04-01-PLAN.md` from 1713847, which contains a private absolute path) and on one source finding in `tests/tools/test_private_paths.py`. The identical 117 findings are present at d46e6e1. Not caused by this round. |
| `tests/workflow` unittest discover | 9 errors before and 9 after: 8 are pre-existing `test_phase01_docs` errors, and the 9th (`test_public_content` rights digest) went away once the row was refreshed. The `test_ci_policy` receipt failure that the orchestrator noted is pre-existing and was left alone. |

**Needs attention (outside this fix scope):** the CI public-content job will probably still fail on this PR because of the pre-existing branch-history personal-path findings. Removing them needs a history decision (for example a filtered PR branch or history dispositions). That is the user's call, so I made no change here.

Not touched: the two `.planning/preparation` files. No push. RetroArch was not launched. This report and the three planning files above are uncommitted.

---

_Fixed: 2026-10-11_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
