---
phase: 04-public-playable-tracer
reviewed: 2026-10-11T00:00:00Z
depth: standard
diff_base: 1f1d953e6c00335fc336bebac4d14f5c8e27553e
reviewed_head: f443a0356627f9e6061a0b49c55682c4063f11d9
files_reviewed: 6
files_reviewed_list:
  - .github/workflows/ci.yml
  - CMakeLists.txt
  - docs/history-allowlist.json
  - docs/testing.md
  - tests/tools/test_verify_playable.py
  - tools/verify_playable.py
findings:
  critical: 2
  warning: 3
  info: 1
  total: 6
status: issues_found
---

# Phase 04: Gap-Closure Re-Review R7 (G6WR-01..03 fixes, diff-scoped)

**Reviewed:** 2026-10-11
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

This round reviews `git diff 1f1d953..f443a03` over the six listed files. Those commits are the round-6 fixes: duplicate-row rejection, history anchoring of the allowlist, the opt-in CTest, the PR-time CI step, and the confined working-tree read for tolerated rights rows.

G6WR-02 is closed. G6WR-03 is closed for symlinks and unnormalized paths, but it still hashes uncommitted bytes. G6WR-01 is closed only through the CI step. The in-tree anchoring adds no protection against forged rows.

There are two blockers. Both show up when the current head goes through CI or the squash merge, and both are reproduced below.

1. The fix commits edited `tests/tools/test_verify_playable.py` but did not update its rights-inventory row. The CI public-content scan fails now, and `--check-docs` fails on main after the squash.
2. The committed allowlist was generated against a stale local `main`. The new CI step compares against the real PR base, so it fails on this PR.

What I ran (RetroArch was not run, and no tracked file was modified):

| Check | Result |
|---|---|
| `python3 tests/tools/test_verify_playable.py` | 161 tests, 1 failure: `test_check_docs_requires_generated_status_to_match_evidence` (`incomplete-archive`). It passed when re-run alone. It ran while I was cloning the repository in parallel, so I treat it as load-related and not caused by this diff. |
| `-k g6wr -k g5wr` subset | 33 tests OK |
| `tools/verify_playable.py --check-docs` (full checkout) | passes |
| `tools/verify_playable.py --history-allowlist check --base origin/main` | **stale** (see G7CR-02) |
| `tools/public_content.py --root .` and `tools/verify_sdk.py --suite public-content` | **fail**, `rights-digest` (see G7CR-01). At 1f1d953 the rights section passed. |
| Simulated squash: `commit-tree HEAD^{tree} -p <remote main>` in a scratch clone, then `--check-docs` | **fail** on the rights row for `tests/tools/test_verify_playable.py` (G7CR-01) |
| Depth-1 clone of HEAD, then `--check-docs` | fails with `frontend evidence revision cannot be checked` (G7IN-01) |

## Prior findings status

| R6 finding | Status | Evidence (re-derived) |
|---|---|---|
| G6WR-01 (allowlist self-attested) | **PARTIAL.** The CI step matches 04-REVIEW-FIX-R6.md. The in-tree anchoring is vacuous. The step is bound to a different base than the generator and runs only when the file changes. | The CI step is at `.github/workflows/ci.yml:142-153`. The opt-in CTest is at `CMakeLists.txt:52, 875-885`. The documented residual (self-attested pins after the squash) is accepted and **not re-raised**; the implementation is not weaker than the fix report on that point. New gaps: G7CR-02 (base mismatch), G7WR-01 (anchoring is vacuous) and G7WR-02 (CI trigger is too narrow). |
| G6WR-02 (duplicate rows) | **CLOSED** | `tools/verify_playable.py:1477-1480` raises `malformed` on a repeated (kind, key, revision) triple. Every loader caller (`check_docs`, `history_allowlist_stale`, the gates and `main`) goes through it. Test: `test_g6wr_02_duplicate_rows_are_malformed` (`tests/tools/test_verify_playable.py:3144`). A row whose revision is spelled short in one place and long in another is not ambiguous, because `covers()` matches the record's exact string. |
| G6WR-03 (symlinks, unnormalized paths) | **PARTIAL** | `_rights_path_is_relative_posix` (`:1555-1558`) now rejects empty, `.` and `..` segments and backslashes. `_confined_file_bytes` (`:1561-1578`) rejects any symlink component, a non-regular file and a resolved path outside the root. Tests are at `:3191` and `:3203`. Gap (G7WR-03): the read still hashes working-tree bytes, not committed bytes, so untracked, ignored, dirty or hard-linked content is accepted. The fix report says Git object reads are impossible here. That is incorrect: `<head>:<path>` resolves. |

## Structural Findings (fallow)

None provided.

## Narrative Findings (AI reviewer)

## Critical Issues

### G7CR-01: The fix commits made the `tests/tools/test_verify_playable.py` rights row stale, which breaks CI public-content now and `--check-docs` after the squash

**File:** `tests/tools/test_verify_playable.py:3144-3215` (the edit). Also `docs/rights-inventory.md:90` (not updated), and `tools/verify_playable.py:1636-1645`, `:1815-1877` (no guard).

**Issue:** This round added about 73 lines to `tests/tools/test_verify_playable.py`. The file's rights row still says `source_revision 027e41777783…` with `sha256 bad5bc34d0a8…`. That digest matches the bytes at 1f1d953 but not at HEAD (HEAD hashes to `05d6997f1aa3…`). Because `tests/tools/test_verify_playable.py` is a rights candidate for `tools/public_content.py`, two things break:

- **CI now.** `tools/public_content.py --root .`, and therefore `tools/verify_sdk.py --suite public-content` (the first step of the `public-content` job, `ci.yml:140-141`), fails with `rights-digest: shipped item bytes differ from the rights inventory`. At 1f1d953 the rights section passed. The PR's required public-content job fails before it reaches the new allowlist step.
- **Main after the squash.** The row is allowlisted (027e417 is a branch-only commit), so after the squash it takes the tolerated branch. That branch compares the working-tree digest with the recorded `sha256`, and they differ. A simulated squash (tree of HEAD committed onto the remote main tip) fails `--check-docs` with `rights source_revision 027e41777783 for tests/tools/test_verify_playable.py is unverifiable-history … and the working-tree file does not hold the recorded SHA-256`. After the squash, the allowlist cannot be regenerated, because `write` refuses on squashed history. Main would then be stuck failing the gate.

Neither `--history-allowlist check` (in the CTest or the CI step) nor the generator catches this. On full history the strict branch reads the blob at 027e417, which still matches. The only safeguard is the manual "squash simulation" in `docs/testing.md:272-277`, which is not automated.

**Fix:**
1. Update the row to the bytes now in HEAD: set `sha256` to the HEAD digest, and set `source_revision` to a commit that holds those bytes (the last commit that touches the file). Then regenerate the allowlist with the correct base (G7CR-02).
2. Make the generator check the post-squash predicate, so that `check`, the CTest and the CI step all catch this class of error:
```python
# in history_allowlist_document, after the strict gates pass
for item in json.loads(inventory[0])["items"]:
    if item["path"].startswith(RIGHTS_EXEMPT_PREFIX) or not introduced(item["source_revision"]):
        continue
    held = _git_bytes(repository, ["cat-file", "blob", f"{head}:{item['path']}"])
    if held is None or hashlib.sha256(held).hexdigest() != item.get("sha256"):
        raise _allowlist_refusal(f"rights row {item['path']} would fail after the squash: "
                                 "the checked head does not hold the recorded SHA-256")
```

### G7CR-02: The committed allowlist was generated against a stale local `main`, so the new CI step fails on this PR and 12 rows cite revisions already on main

**File:** `docs/history-allowlist.json` (`base_revision`), `tools/verify_playable.py:2089`, `CMakeLists.txt:880-882`, `.github/workflows/ci.yml:146-152`, `docs/testing.md:263-264, 272-273`

**Issue:** The committed file has `base_revision` `2e5d8849a57f…` and 145 rows. That is `git merge-base HEAD main` against the **local** `main` branch, which is 297 commits behind the remote `main` tip (`4b2120d57f48…`). That remote tip is already an ancestor of HEAD. The CI step passes `--base "$BASE_SHA"`, the PR base, so `history_allowlist_document` computes `merge_base = 4b2120d5…`. Running `--history-allowlist check --base origin/main` locally produces 133 rows and reports **stale**, exit 1. A PR from this branch to `main` therefore fails the new step.

The difference is 12 rights rows (`tests/cpu/ORACLE.md`, `tests/cpu/*-red-evidence.json`, `tests/cpu/guest_fixture.{c,h}`, `tests/cpu/isolation_fixture.h`, `tests/cpu/fixture-manifest.json`, `tests/fuzz/regressions.json`, `tests/sdk/guest_fixture.{c,h}`). Each cites a revision reachable from the current remote `main`. That contradicts `docs/testing.md`: "rows citing a revision reachable from main are never listed". `history_allowlist_anchor_errors` accepts these rows because it checks reachability against the file's own self-reported `base_revision`.

The root cause is the default `--base main` (`:2089`). It resolves to whatever local branch is called `main`. The CTest has no `--base`, and the documented pre-ship step runs `check` without `--base`, while CI uses the PR base SHA. `docs/testing.md:263` says the CTest "runs the same check locally", but it does not use the same base. In a fresh CI-style clone with no local `main` branch, the CTest refuses outright.

**Fix:**
- Regenerate now: `git fetch origin && python3 tools/verify_playable.py --history-allowlist write --base origin/main`. Commit the file, then confirm `check --base origin/main` reports current.
- Make the bases agree. Add a `GLUEYNEO_HISTORY_BASE` cache variable (default `origin/main`) and pass `--base ${GLUEYNEO_HISTORY_BASE}` to the CTest. Change the documented pre-ship step to `git fetch origin` followed by `--history-allowlist check --base origin/main`. Alternatively, have `main()` require `--base` explicitly instead of defaulting to a possibly stale local branch.

## Warnings

### G7WR-01: The in-tree anchoring cannot change any gate outcome; docs/testing.md overstates it

**File:** `tools/verify_playable.py:1484-1526`, `:1063`, `:1605`, `:1712`, `:1943-1945`; `docs/testing.md:250-254`; `tests/tools/test_verify_playable.py:3178-3189`

**Issue:** Tolerance is granted only when a revision's relation to `head` is `absent` (`:1064`, `:1636`, `:1719`, `:1745`). `history_allowlist_anchor_errors` first verifies that `base_revision` is an ancestor of `head`. It then drops a row only when the row's revision is an ancestor of `base_revision`. Ancestry is transitive, so any revision it drops is an ancestor of `head`, which makes its relation `ancestor`. That row was always going to be checked strictly. Dropping it changes no gate result. The only real effect is the `RuntimeError` in `check_docs`.

The base check rejects only a fabricated `base_revision`. Anyone forging rows can keep a real ancestor, as the committed file does (see G7CR-02, where a stale but real base passes). Rows citing revisions that do not resolve, which is the actual G6WR-01 threat, pass anchoring unchanged by design.

The regression test asserts only that the row is removed from `kept.rows`, not that any gate decision changes, which is consistent with this. `docs/testing.md` says "The allowlist is checked against git… a row failing either test is dropped to strict". That reads as a protection. Against forged rows, the CI step is the only check.

**Fix:** Pick one.
- State in `docs/testing.md` that anchoring is a consistency check, so forged or invented rows are caught only by the CI `check` step before merge.
- Or delete `anchored_history_allowlist` and its three call sites, keeping `history_allowlist_anchor_errors` as a `check_docs` lint. This also removes about four git subprocesses per row per gate.

### G7WR-02: The CI step runs only when the allowlist file changes, so a stale allowlist can merge

**File:** `.github/workflows/ci.yml:149-153`; `docs/testing.md:260-262`

**Issue:** The gate is skipped whenever `docs/history-allowlist.json` is byte-identical to the PR base. A PR can still change a pinned record without touching the allowlist: a disposition row edited by `/gsd-code-review`, a rights item, the receipt, or a rights file's bytes (G7CR-01). That voids or invalidates listed rows. On full history these rows still pass strictly, so CI stays green. After the squash they fail `--check-docs`, and the file can no longer be regenerated. The documented guarantee ("a changed allowlist cannot merge unless every row verifies") is literally true, but the invariant that matters is not enforced: the allowlist that ships must still be current.

**Fix:** On every PR, run a history-independent staleness check: `history_allowlist_stale(ROOT)`, plus the rights working-tree digest check from G7CR-01 for each listed row. Both work before and after the squash. Keep the full `check --base` when the file changes, or whenever every listed revision still resolves. For example, add a `--history-allowlist stale` mode that exits non-zero on any stale row, and call it unconditionally in this step.

### G7WR-03: The tolerated rights branch still hashes working-tree bytes, not committed bytes (G6WR-03 partly open)

**File:** `tools/verify_playable.py:1561-1578, 1638-1639`

**Issue:** `_confined_file_bytes` rejects symlinks and escapes. But a regular file under the root is accepted even when it is untracked, ignored, a dirty uncommitted edit, or a hard link to content outside the tree. The strict branch judges committed bytes (`git cat-file blob rev:path`). The tolerated branch judges whatever is on disk. A local `--check-docs` on a dirty tree can therefore pass a row that a fresh clone fails, or fail one it passes.

G6WR-03 asked that "the working-tree digest is of the tracked file". The fix report says "Git object reads are impossible here because the revision is absent by definition". That is incorrect. The absent revision cannot be read, but the checked `head` always can. `git cat-file blob <head>:<path>` returns the tracked bytes. For a symlink it returns Git's link blob (the target string), so a symlink fails the digest without special handling. In the `--clean` qualification path `head` is `snapshot.commit` (`:2339`), so the result stays consistent.

**Fix:**
```python
blob = _git_bytes(repository, ["cat-file", "blob", f"{head}:{path}"])
held = hashlib.sha256(blob).hexdigest() if blob is not None else None
```
Keep the path-form validation. Update `docs/testing.md`, which says "working-tree digest" in several places, to "digest of the file at the checked head".

## Info

### G7IN-01: `--check-docs` on a shallow clone now fails with a misleading message

**File:** `tools/verify_playable.py:1063, 1910-1911, 1943-1945`; `docs/testing.md:265-266`

**Issue:** In a depth-1 clone, `base_revision` does not resolve. `anchored_history_allowlist` then empties the allowlist, and `load_frontend_evidence` raises `frontend evidence revision cannot be checked` (from the `merge-base` exit-128 path). It never reaches the clearer `history allowlist base_revision is not a commit of this repository`, because `check_docs` runs the anchor check only after `load_frontend_evidence`. Before this diff, the frontend gate tolerated the receipt in the same shallow clone. `docs/testing.md` mentions shallow checkouts only for the CTest, which implies `--check-docs` works on them.

**Fix:** In `check_docs`, run `history_allowlist_anchor_errors` before `load_frontend_evidence` when a repository is available. Add a line to `docs/testing.md` saying that `--check-docs` needs the history back to `base_revision` (a full clone or `--shallow-since`).

---

_Reviewed: 2026-10-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
