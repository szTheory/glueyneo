---
phase: 04-public-playable-tracer
reviewed: 2026-10-11T00:00:00Z
depth: standard
diff_base: 8c20410b0f1c4d0612e7fa5c64d75115d47c2224
reviewed_head: bdfdc1d6105517c5fad9be08c9657452c55b5050
files_reviewed: 10
files_reviewed_list:
  - docs/first-playable-build.md
  - docs/history-allowlist.json
  - docs/rights-inventory.md
  - docs/testing.md
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/check_security_register.py
  - tests/tools/test_check_security_register.py
  - tests/tools/test_verify_playable.py
  - tools/verify_playable.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 04: Gap-Closure Re-Review R6 (04-38..04-65, diff-scoped)

**Reviewed:** 2026-10-11
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Incremental review of `8c20410..bdfdc1d` for the ten listed files. The diff adds the history allowlist and its gates, the rights `source_revision` gate, the lane-output drain and decode, the evidence-write rollback, the frontmatter and table parser in the security register checker, and the PID-record handling in the RetroArch smoke harness.

RetroArch was not run. These checks passed on the current tree:

- `tools/verify_playable.py --check-docs`
- `tools/verify_playable.py --history-allowlist check` (141 rows, current)
- the 65 `check_security_register` tests
- the 78 `retroarch_smoke` tests
- `tests/tools/check_security_register.py` against the real registers (05-SECURITY.md has 9 blocking open rows, which is expected)

I did not re-run the 1684-line `test_verify_playable.py` suite to completion. I found no blockers. The remaining defects are in the trust model of the new allowlist and in small robustness gaps.

**Scope.** This is a diff-scoped round: `git diff 8c20410..bdfdc1d` over the ten listed files, plus the code those changes call. Finding IDs use the `G6` prefix and the round file is `04-REVIEW-GAPS-R6.md`; `04-REVIEW.md` and `04-REVIEW-DISPOSITION.md` are not changed by this round.

**Earlier findings.** `tools/private_paths.py`, `tests/consumers/check_package.py`, `CMakeLists.txt`, the manifest and `tests/tools/test_private_paths.py` are not in this scope, so I make no claim about CR-01 to CR-09 from the previous report as they apply there. Within these files:

- The former CR-08, the `main()` crash on early snapshot failure, is covered by the new `_write_minimal_fail_receipt` and `entry()` guard.
- CR-09, raw exception text, is covered by `entry()` printing the exception type only.

### Verdicts on the R5 findings marked "independent verdict pending"

| R5 finding | Verdict | Evidence (file:line, re-derived) |
|---|---|---|
| G5WR-01 (rights gate fails after squash merge) | FIXED, with a residual trust gap (G6WR-01) | `tools/verify_playable.py:1489-1498` (`_revision_relation`) classes a revision as `absent` when it does not resolve or is neither ancestor nor descendant of head. `rights_revision_errors` (`:1512`) tolerates only an `absent` row that `allowlist.covers(...)` (`:1565`) and whose working-tree file hashes to the recorded `sha256`; `ancestor` rows stay strict. The same rule is applied to the receipt (`:1064`) and to review citations (`:1648`, `:1676`). `docs/history-allowlist.json` is current (141 rows, `--history-allowlist check` passes). Squash behavior is tested: `test_g5wr_01_rights_row_tolerated_after_squash` (`tests/tools/test_verify_playable.py:2676`), `_review_tolerated_after_squash` (`:2770`), `_branch_cut_from_squashed_main` (`:2880`), plus unlisted, fabricated and edited-row cases (`:2785`, `:2807`, `:2833`). `docs/rights-inventory.md` and `docs/testing.md` state the rule. The row now passes after a squash; what the fix leaves open is that the allowlist is trusted input (G6WR-01). |
| G5WR-02 (lane tests have no readiness handshake) | FIXED | `ProcessGroupTest.wait_ready` (`:543`) polls for `lane.ready` with a 30 s bound and fails with `lane child never became ready`. `ready_gate` (`:552`) makes the first timed `communicate` of the lane argv wait for it. It is used by the runner-lane tests (`:586`, `:621`, `:752`, `:856`). The direct-`Popen` tests call `wait_ready` before `communicate` (`:685`, `:717`). Each child writes `lane.ready` (`:579`, `:611`, `:767`, `:787`, `:803`, `:842`). `test_g5wr_02_slow_start_*` (`:880`, `:884`) delay startup by 3 s, and `test_g5wr_02_never_ready_child_fails_clearly` (`:905`) asserts the message. The one remaining test with `ready=False` (`:814`) never signals the child. |
| G5IN-01 (`third_party/` path-form skip, non-list `items`) | FIXED | `tools/verify_playable.py:1544` raises `rights inventory JSON is malformed` for a non-list `items`. `:1550` runs `_rights_path_is_relative_posix` before the `third_party/` exemption at `:1553`, so `third_party/../x` is rejected. Tests `test_g5in_01_third_party_dot_dot_path_is_not_exempt` (`:1750`) and `test_g5in_01_non_list_items_is_malformed` (`:1762`). Residual path-normalization gap is G6WR-03. |

**G6WR-01 relates to G5WR-01.** G5WR-01 is fixed in mechanism and closes the R5 hazard. G6WR-01 is a new weakness in that fix, not a reopening of it. The per-row tolerance relies on allowlist pins that the same commit can forge. For rights rows the working-tree digest is a real content check, but for review citations and the receipt it is not. The only verifier of the allowlist, `--history-allowlist check`, cannot run after the squash.

## Structural Findings (fallow)

None provided.

## Narrative Findings (AI reviewer)

## Warnings

### G6WR-01: History allowlist is self-attested; the loader does not validate it against history

**File:** `tools/verify_playable.py:1454-1477, 1435-1436, 1444`
**Issue:** The allowlist converts a failed revision binding into a tolerated note. The loader and `covers()` check only the record's shape and that the pin matches the record as it is now.

- `base_revision` is parsed and stored (line 1477) but never read by any gate. Only the generator uses `merge_base`. A row citing a revision that was never in this repository, or one reachable from `main`, is accepted at `--check-docs` time.
- `_reviewed_revision_pin(reviewed)` (line 1435) is `sha256("reviewed_revision: " + reviewed)`. It is computed from the revision that is also the row's key, so it binds nothing. Any author can mint a valid pin for any 40-hex value. The `frontend_receipt` and `rights` pins are digests of the record. They are equally forgeable, because the same commit can edit both the record and the allowlist.
- An invented `reviewed_revision` plus a minted pin makes `anchor_unverifiable` true. Each base-round citation that is also allowlisted then skips its ordering check.
- The only guard against forged rows is `--history-allowlist check`. It regenerates strictly and refuses on a squashed history, so it cannot run after the squash. Nothing in `CMakeLists.txt` or `.github` invokes it, so nothing enforces the "pre-ship step required" rule in `docs/testing.md`.

`docs/testing.md` describes the protection as "the allowlist plus the per-record pin plus (rights) the working-tree digest". For review citations and the receipt, that is a convention rather than a check.

**Fix:** Pick one or more of these.

- Wire `--history-allowlist check` into the pre-ship CTest or release job (full-history jobs only), so a forged or stale row fails before the squash.
- In `load_history_allowlist`, reject rows whose revision is reachable from `base_revision`, or at least record that the check is delegated to the pre-ship step.
- Add `base_revision` to each pin's preimage, or sign the file.
- State plainly in `docs/testing.md` that post-squash the allowlist is trusted input, not verified history.

### G6WR-02: Duplicate allowlist rows are silently collapsed; last row wins

**File:** `tools/verify_playable.py:1476`
**Issue:** `rows[(kind, key, revision)] = pin` overwrites an earlier row with the same triple. A file holding two rows for one triple with different pins is accepted, and only the last pin counts. `history_allowlist_is_current` compares bytes with a regenerated file, so a duplicate fails `check`. `--check-docs` does not run that comparison, so the malformed file is not "malformed" on the gate that ships. The docstring promises "a malformed one fails closed".
**Fix:**
```python
key = (row["kind"], row["key"], row["revision"])
if key in rows:
    raise malformed
rows[key] = row["pin"]
```

### G6WR-03: Rights allowlist branch reads `source_root / path` through symlinks and un-normalized paths

**File:** `tools/verify_playable.py:1506-1509, 1569`
**Issue:** `_rights_path_is_relative_posix` rejects only a leading `/` or `-` and `..` segments. It accepts `a/./b`, `a//b`, backslashes, a trailing `/` and a symlink at `path`. In the tolerated branch, `(source_root / path).read_bytes()` follows a symlink out of the tree. The strict branch uses `git cat-file blob rev:path`, which does not follow symlinks. The same row can therefore pass by tree digest in one branch and be judged on different bytes in the other. The inventory is an editor-controlled file, so this is not remote-exploitable. It does break the claim that the working-tree digest is of the tracked file.
**Fix:** In the tolerated branch, resolve `(source_root / path)` and require it to be a regular, non-symlink file whose resolved path is under `source_root.resolve()`. Reject `.` and empty segments in `_rights_path_is_relative_posix`.

## Info

### G6IN-01: Typing escapes around `HistoryAllowlist.EMPTY`

**File:** `tools/verify_playable.py:1451, 1458, 1772-1776`
**Issue:** `EMPTY` is attached after class creation, and every use needs `# type: ignore[attr-defined]` (five of them). A frozen dataclass cannot hold a mutable default. A module-level `EMPTY_HISTORY_ALLOWLIST = HistoryAllowlist(rows={})` removes the ignores without changing behavior.
**Fix:** Define a module constant and replace the attribute accesses.

### G6IN-02: `strip_comment` is not quote-aware

**File:** `tests/tools/check_security_register.py:159-160`
**Issue:** `re.sub(r"(?:^|\s+)#.*$", "", value)` removes a ` #...` tail even inside a quoted scalar. A value such as `"verified # note"` becomes `"verified`, which `unquoted` no longer recognizes. The `status: verified` rule then silently does not apply. This fails open for that one hand-written spelling, though `verified` with trailing text is not a value GSD itself writes.
**Fix:** Strip the comment only after quote-matching, or only when the value does not begin with a quote.

### G6IN-03: `_drain` treats every `OSError` from `os.read` as EOF

**File:** `tools/verify_playable.py:555-571`
**Issue:** `except OSError: return True` marks the stream finished for any read error, including a transient or unexpected errno. Output after that point is dropped. It is also unreachable for `select` failures: a descriptor of 1024 or more raises `ValueError`, which is only caught indirectly by the new `(OSError, ValueError)` clause in `Runner.run`. Lane termination then relies on the outer `finally`. The consequence is a truncated partial transcript, not a leaked process.
**Fix:** Return True only for expected pipe-closed errnos (`EIO`, `EPIPE`) and let others propagate. Use `selectors.DefaultSelector`, or `poll`, to avoid the `FD_SETSIZE` limit.

---

_Reviewed: 2026-10-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
