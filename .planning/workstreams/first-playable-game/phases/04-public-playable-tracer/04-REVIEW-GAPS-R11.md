---
phase: 04-public-playable-tracer
reviewed: 2026-10-12T00:00:00Z
depth: standard
diff_base: 5861f0aa6a9d1e0e61d315d3a1ff51731678d040
reviewed_head: 55960c64714f23abdd05323ca830f92b179ba122
files_reviewed: 3
files_reviewed_list:
  - tools/verify_playable.py
  - tests/tools/test_verify_playable.py
  - experiments/owned_cpu/source-manifest.json
findings:
  critical: 0
  warning: 0
  info: 3
  total: 3
status: issues_found
---

# Phase 04: Gap-Closure Re-Review R11 (manifest digest refresh and batched history-allowlist reachability, diff-scoped)

**Reviewed:** 2026-10-12
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found (three Info items, no Critical or Warning)

## Summary

Scope is `git diff 5861f0a HEAD` over the three files. Two commits: 588aedf (manifest digest) and 3c00480 (batched reachability).

Focused verification run: `python3 -m unittest tests.tools.test_verify_playable.SquashMergeHistoryTest` ran 37 tests, all OK (about 20 s). `python3 tools/verify_playable.py --check-docs` prints "Phase 04 documentation gate passed." The full suite and ctest were not run, as instructed.

### 1. Manifest digest (588aedf): confirmed legitimate

- The new `CMakeLists.txt` entry in `experiments/owned_cpu/source-manifest.json` is `6f7b3eda...3546`. `shasum -a 256 CMakeLists.txt` on the working tree gives the same value. The worktree has no uncommitted change to `CMakeLists.txt`; the only dirty paths are two `.planning/preparation` files.
- The previous digest was set by d2b3951 (04-32). `git log d2b3951..HEAD -- CMakeLists.txt` shows exactly four commits: e2845e6 and 84ce072 (G6WR-01), 6103b9e (G7CR-02), 13c7a37 (G7WR-02).
- `git diff d2b3951 HEAD -- CMakeLists.txt` is 19 inserted lines and nothing else: the `GLUEYNEO_PRE_SHIP_HISTORY_CHECK` option, the `GLUEYNEO_HISTORY_BASE` cache string, and the opt-in `qualification_history_allowlist` test with `TIMEOUT 120`.
- Those finding IDs appear in the reviewed rounds: 04-REVIEW-FIX-R6/R7/R8 and 04-REVIEW-GAPS-R6/R7/R8. The digest refresh therefore blesses reviewed changes, not an unreviewed edit. The refresh was late (the gap between d2b3951 and 588aedf is why the CTest manifest check failed), but its content is sound.

### 2. Batched reachability (3c00480): verdict equivalent for every input reachable through the loader

Checked by reading the code and by probing `git cat-file --batch-check` in a scratch repository.

- **Inclusive ancestry:** `git rev-list <base>` includes `<base>`, matching `merge-base --is-ancestor`'s reflexive result. The new test covers it (base F2 with rows at F2).
- **Resolution:** the query line is `<revision>^{commit}`, as in the old `rev-parse --verify --quiet`. Probed outcomes:
  - Tag objects peel to the commit oid, and that oid is what is compared. This is correct.
  - A tree or blob prints `missing` (plus a stderr line) and is skipped.
  - A short prefix that is too short, unknown, or ambiguous prints `missing` or `ambiguous` and is skipped, as the old empty `rev-parse` result was.
  - Skipped rows are not reachable, so they are tolerated on their pin alone, as before.
- **Alignment:** `batch-check` emits exactly one line per input line, including for missing and ambiguous. `len(answers) != len(rows)` therefore fails closed with RuntimeError. `cat-file` exits 0 on `missing`, so a non-zero exit is a real failure and also raises.
- **Error paths:** rev-list failure or empty output, timeout, OSError, a non-zero cat-file exit, and a line-count mismatch all raise `RuntimeError("review provenance revision cannot be checked")`. None treats rows as unreachable. Nothing widens tolerance.
- **Shallow clones:** `rev-list` and `merge-base` both stop at the shallow boundary, so ancestry is the same. A missing base is already rejected earlier by the unchanged `rev-parse` check.
- **Whitespace and newline injection:** the loader (`load_history_allowlist`) restricts `revision` to `[0-9a-f]{12,40}`, so injection is unreachable through the file. The helper's own `\n`/`\r` guard covers directly constructed allowlists. Probe: `batch-check` treats the first whitespace as the object/rest separator, so `"<oid> extra^{commit}"` is reported `missing`, not resolved. See G11IN-01 for the residual mismatch.
- **Callers:** `history_allowlist_anchor_errors` returns the same message text, same sorted order, same first-error semantics (callers at about lines 2000 and 2036 use `[0]`). `anchored_history_allowlist` keeps the same filter (drop rows reachable from base; keep unresolved ones). Only difference: a git failure inside the loop now raises (see G11IN-02), where before it silently kept the row.

## Info

### G11IN-01: `splitlines()` and the newline guard are not aligned on exotic separators

**File:** `tools/verify_playable.py:1546-1550`
**Issue:** The guard rejects `\n` and `\r`, but the answers are split with `str.splitlines()`, which also breaks on `\x0b`, `\x0c`, `\x1c`-`\x1e`, `\x85`, ` ` and ` `. `batch-check` echoes the input for `missing` and `ambiguous` lines, so a revision containing one of these would make `len(answers) != len(rows)` and raise. That fails closed (no tolerance widened), and the loader's hex-only rule means it cannot occur from the file. It is only a robustness/consistency gap for directly constructed `HistoryAllowlist` values. Similarly, a space inside a revision is not guarded: git's `batch-check` would split it as object plus `%(rest)`. In the probe it still came out `missing`, so no wrong verdict was seen, but the code does not rely on that by design.
**Fix:** Validate in the helper with `RIGHTS_REVISION_PREFIX = re.compile(r"[0-9a-f]{4,40}")` (or `fullmatch(r"[0-9a-f]+")`) instead of the newline test, and split with `.decode("utf-8", "replace").split("\n")` after stripping one trailing empty element.

### G11IN-02: `anchored_history_allowlist` gains a new raise path, and the helper trusts `base`

**File:** `tools/verify_playable.py:1519, 1566, 1530-1536`
**Issue:** Before, `anchored_history_allowlist` swallowed per-row git failures (only timeouts raised). It now raises `RuntimeError` when `rev-list`/`cat-file` fails, which propagates from `load_frontend_evidence` (line 1064) and the rights/review gates (lines 1650 and 1757). This is the right direction (fail closed) and was probably intended, but it is a behaviour change the commit message does not state. Separately, `_rows_reachable_from` passes `base` to `git rev-list` without validating it. Both current callers have already fullmatched it as 40 hex, so there is no exposure today, but the helper is module-level and a future caller could pass a value beginning with `-`.
**Fix:** Note the new error in the docstring or commit notes; add `RIGHTS_REVISION.fullmatch(base)` (or `--end-of-options`) at the top of `_rows_reachable_from`.

### G11IN-03: The equivalence test is meaningful but narrow

**File:** `tests/tools/test_verify_playable.py:3297-3313`
**Issue:** The test is a real differential oracle: it recomputes the old per-row `rev-parse` plus `merge-base --is-ancestor` algorithm in the test and compares sets. Base F2 gives a non-empty expected set with inclusive and strict ancestors, plus a missing-oid, a 7-character prefix and a non-revision string. Gaps:
- With base B, the expected set is empty, so it asserts nothing positive.
- There is no annotated-tag row (peeling), no tree/blob row (`^{commit}` type failure), no genuinely ambiguous prefix, no revision containing `\n` or `\r` (the guard branch), and no case for a failing `rev-list` or `cat-file` raising `RuntimeError` (the fail-closed claim in item 2 is verified here only by manual probing).
- The 7-character prefix is accepted by the helper but would be rejected by the loader, so that row exercises a non-production input; useful, but not a production-shape check.
**Fix:** Add rows for an annotated tag of F1 and the tree of F1's commit, a `"\n"` revision asserting `RuntimeError`, and a monkeypatched `_git_stdout` returning `None` asserting `RuntimeError`.

---

_Reviewed: 2026-10-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
