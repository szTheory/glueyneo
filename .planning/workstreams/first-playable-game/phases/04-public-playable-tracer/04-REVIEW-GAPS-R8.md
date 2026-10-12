---
phase: 04-public-playable-tracer
reviewed: 2026-10-11T00:00:00Z
depth: standard
diff_base: bb0f4eb8452488e28f1c2f1ed469e21e83c359bf
reviewed_head: d638d3ef086e957af7d40b2e64767af7e5c492d4
files_reviewed: 7
files_reviewed_list:
  - .github/workflows/ci.yml
  - CMakeLists.txt
  - docs/history-allowlist.json
  - docs/rights-inventory.md
  - docs/testing.md
  - tests/tools/test_verify_playable.py
  - tools/verify_playable.py
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: issues_found
---

# Phase 04: Gap-Closure Re-Review R8 (G7 fixes, diff-scoped)

**Reviewed:** 2026-10-11
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

This round reviews `git diff bb0f4eb..d638d3e` over the seven listed files: the round-7 fix commits 6103b9e..91f51ac and the records commit d638d3e. All six round-7 findings are closed. I found no new blocker or warning. One info item: the documented reason for the G7WR-02 deviation is wrong, although the deviation itself is sound.

What I ran (no tracked file was changed, RetroArch was not run):

| Check | Result |
|---|---|
| `python3 tests/tools/test_verify_playable.py` | Ran 167 tests, OK (run twice, about 8 minutes each under load) |
| `python3 tools/verify_playable.py --check-docs` | passes |
| `--history-allowlist check --base origin/main` | current (145 rows) |
| `--history-allowlist ci --base origin/main` | applies ("differs from origin/main"), then current (145 rows), exit 0 |
| Rights digests: all 46 rows in `docs/rights-inventory.md` against `git show HEAD:<path>` | 46 of 46 match. The `tests/tools/test_verify_playable.py` row (`2d5fdf58...`, source e71e283) is also the last commit that touched the file. |
| Squash simulation (HEAD tree committed onto 4b2120d in a scratch clone) | `--check-docs` passes. `ci --base <squash commit>` on a later commit prints "does not apply" and exits 0. `ci --base 4b2120d` on the squash commit itself applies and refuses, as designed. |
| Post-squash rights refresh (edit a listed file) | Without an inventory refresh: fails with "file at the checked head does not hold the recorded SHA-256". With a refreshed row citing the new main commit: `--check-docs` passes. |

## Round-7 finding verdicts

| ID | Verdict | Evidence |
|---|---|---|
| G7CR-01 | **Closed** | All 46 rights digests match HEAD (above). The row for `tests/tools/test_verify_playable.py` points at the last commit that touches that file. `history_allowlist_document` now refuses a listed rights row whose blob at the checked head differs from the recorded SHA-256 (`tools/verify_playable.py:1888-1893`). The test is `test_g7cr_01_generator_refuses_rights_row_stale_at_head`, and it first asserts the strict branch alone misses the case. The squash simulation passes. |
| G7CR-02 | **Closed** | The default base is `HISTORY_DEFAULT_BASE = "origin/main"` (`:1819`). The generator refuses when the base does not resolve (`:1851-1853`). The CTest passes `--base "${GLUEYNEO_HISTORY_BASE}"` (`CMakeLists.txt:884`). The committed file has `base_revision` 4b2120d57f48, equal to the true PR base, and `check --base origin/main` reports current. The 12 stale-base rows are gone. |
| G7WR-01 | **Closed** | The docstring (`:1495-1496`) and `docs/testing.md` now describe the anchoring as a consistency check, and name the CI `ci` step as the only forged-row defence. That matches the code. The `t_04_38` test isolation (`tests/tools/test_verify_playable.py:1587-1589`) removes the copied allowlist so the gate under test is reached, and the assertion is unchanged. |
| G7WR-02 | **Closed, with the deviation accepted on its merits** | The `ci` mode runs on every pull request (`ci.yml:142-152`). The `public_content` job is always selected by the classifier (`tools/workflow/ci_policy.py:131-139`), so the step is not skipped by path. The full `check` runs when the allowlist differs from the base or any listed revision is an ancestor of the head (`:1916-1934`). That covers the pre-squash gap I raised: an edit to a pinned record without touching the file. A failed `git diff` counts as a difference. See G8IN-01 for the rationale. |
| G7WR-03 | **Closed** | `_head_blob` (`:1566-1587`) reads the entry with `ls-tree -z` and accepts only a regular blob (100644 or 100755) whose listed name equals the path. It hashes the object with `cat-file`, not the working tree. Symlinks, submodules, symlinked directories and missing entries return None. `test_g7wr_03_tolerated_rights_row_ignores_working_tree_bytes` covers dirty, deleted and untracked files. The old symlink tests now commit the tampering, so they still exercise the new path. |
| G7IN-01 | **Closed** | `check_docs` raises the base-missing error before the frontend gate (`:1955-1961`), and only that one error is moved earlier. Test: `test_g7in_01_check_docs_reports_unanchored_allowlist_first`. `docs/testing.md` states the history requirement. |

### Assessment of the G7WR-02 deviation

The deviation is correct: no history-independent stale gate after the squash.

- The pre-squash risk is covered by the `ci` mode, as above.
- After the squash, an unrefreshed edit to a listed rights file is already rejected by the tolerated branch itself (reproduced in the scratch clone above). A stale-row gate would add nothing for that case.
- An edit to a listed item voids that row's pin, so the row is evaluated strictly. A refresh that cites a real main commit passes (reproduced). A stale allowlist row left behind is inert.
- A new gate that failed on orphaned rows would then be unfixable, because editing the allowlist after the squash triggers `ci` mode, which refuses on squashed history. So not adding the gate is the right call.

## Structural Findings (fallow)

None provided.

## Narrative Findings (AI reviewer)

## Info

### G8IN-01: The recorded reason for not adding a post-squash stale gate is wrong

**File:** `docs/testing.md:281-284` (same claim in `04-REVIEW-FIX-R7.md`, G7WR-02 deviation, and in the `history_allowlist_check_applies` docstring at `tools/verify_playable.py:1920-1927`)

**Issue:** The text says a legitimate post-squash rights refresh "voids a listed row, and failing on that would leave no way to proceed". That is not what happens. I refreshed a listed file and its inventory row in a scratch squash clone, citing the new main commit, and `--check-docs` passed. The real reasons are the two that I listed under the deviation assessment above: the tolerated branch already fails an unrefreshed edit, and an orphaned row is inert and cannot be removed by editing the allowlist. Anyone relying on the recorded reason would believe a refresh is blocked after the squash, and may try to work around a path that works.

**Fix:** Replace the sentence in `docs/testing.md` with, for example: "No history-independent staleness check was added: after the squash an unrefreshed edit to a listed rights file already fails the tolerated branch's digest check, a refreshed row cites a main commit and is evaluated strictly, and an orphaned allowlist row is inert. The allowlist cannot be edited after the squash because `ci` mode refuses on squashed history."

---

Note for the orchestrator (not a finding): the committed allowlist is current at HEAD (145 rows). Any later edit to a pinned record, such as recording the disposition of this round's findings in `04-REVIEW-DISPOSITION.md`, makes it stale until the documented pre-ship `--history-allowlist write --base origin/main` runs. The CI public-content job also still carries the separately tracked branch-history personal-path findings, which were out of scope for this round and which I did not run.

_Reviewed: 2026-10-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
