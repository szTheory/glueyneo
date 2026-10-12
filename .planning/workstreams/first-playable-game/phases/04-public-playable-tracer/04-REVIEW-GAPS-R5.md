---
phase: 04-public-playable-tracer
reviewed: 2026-10-11T00:00:00Z
depth: standard
diff_base: b6977421e5c6a6abc4b8cc749ac1a4ef2fa89bca
files_reviewed: 9
files_reviewed_list:
  - docs/first-playable-build.md
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
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 04: Gap-Closure Re-Review R5 (04-58, diff-scoped)

**Reviewed:** 2026-10-11
**Depth:** standard (`git diff b697742..HEAD` for the nine files, plus the code those changes call)
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Round 5 reviews plan 04-58 only: the byte-level lane output rewrite, the rollback debris reporting, the exact register-key spelling and security-named candidate scan, the `run_diagnostics` early stop, and the new rights `source_revision` gate. As run here: `test_verify_playable.py` 125 tests OK (219 s), `test_check_security_register.py` 65 OK, `tests/libretro/test_retroarch_smoke.py` 78 OK, `tools/verify_playable.py --check-docs` passes, every one of the 46 rights-inventory SHA-256 values equals the working-tree file, and `check_security_register.py first-playable-game --require-closed --phase 04` passes (the unscoped run correctly reports phase 05 as open). Nothing under `src/`, `include/`, `third_party/`, `tests/fixture/`, `tests/libretro/` or the two listed tool files changed after the re-qualified revision `cdfbc99bafe7` (`git log cdfbc99..HEAD` over those paths is empty), so the status line is current.

No critical issues. All seven R4 findings are fixed. The new rights gate has a merge-strategy hazard (G5WR-01), and several new lane tests have no readiness synchronization with the child they signal (G5WR-02).

### Status of R4 findings claimed fixed

| R4 finding | Verdict | Evidence (file:line, re-derived) |
|---|---|---|
| G4WR-01 (lane timeout output lost or reordered) | FIXED | `tools/verify_playable.py:588-624` keeps `earlier` as bytes unconditionally, takes only the suffix `tail[len(earlier):]` from `_collect_after_kill` (`:620-623`), and decodes `earlier + drained + rest` once through `_decode_lane_output` (`:574`), which also applies the one newline translation. `_collect_after_kill` (`:644-665`) returns `again.output` when the second `communicate` expires, reaps with a bounded `wait` and closes the parent pipe end. Regressions at `tests/tools/test_verify_playable.py:706` (detached `setsid` holder keeps the marker), the CRLF test and the split-multibyte test; all pass. |
| G4WR-02 (register checker honoured case-folded keys and Unicode digits) | FIXED | `tests/tools/check_security_register.py:145-157` splits `unquoted_key` (case kept) from `normalized_key` (duplicates only); `:248-251` fails `<key> key must be spelled exactly` for `threats_open` and `status`; `:81` is `[0-9]+`. Tests `test_g4wr_02_*` cover `Threats_Open`, `"THREATS_OPEN"`, `'Threats_open'`, `Status`, U+0663, U+FF13, the still case-insensitive duplicate rule and the case-insensitive `verified` value. |
| G4WR-03 (non-UTF-8 lane bytes raise `UnicodeDecodeError`) | FIXED | The lane `Popen` at `tools/verify_playable.py:799-802` has no `text`/`encoding`/`errors`; both paths decode through `_decode_lane_output` (`:805-806`, `:623`); `:811` also catches `ValueError`. Tests `test_g4wr_03_non_utf8_lane_output_is_recorded`, `..._on_the_timeout_path` and `test_g4wr_03_lane_popen_is_byte_mode` pass. |
| G4WR-04 (rights `source_revision` unresolvable or stale, field undefined) | FIXED | `docs/rights-inventory.md:21-32` defines the field; `tools/verify_playable.py:1403-1440` (`rights_revision_errors`) checks path form, 40-hex, resolves, ancestor of head and blob digest before any value reaches a Git argument; wired into `check_docs` at `:1568`; CTest `qualification_runner` runs `test_g4wr_04_repository_rights_revisions_resolve`. The unresolvable `e6547a1e671a...` row is now `4c55ac2e9b76...`. Residual hazard: G5WR-01. |
| G4IN-01 (misnamed register needed a two-digit prefix) | FIXED | `tests/tools/check_security_register.py:340-343` scans every `*.md` whose name contains `security` (any case) in the scoped or all phase directories; `4-SECURITY.md`, `SECURITY.md`, `phase-04-security.md` fail as `misnamed security register` in both modes (`test_g4in_01_stray_register_names_fail`), and a non-register-shaped file prints `SKIP:`. |
| G4IN-02 (rollback says "incomplete" for a good restore; `.tmp` debris silent) | FIXED | `tools/verify_playable.py:1143` and `:1165-1190` keep `unrestored` and `debris` apart; messages are `evidence rollback complete; could not remove: ...` and `evidence rollback incomplete: ...; could not remove: ...`; the original failure is the `__cause__`; an interrupt is re-raised unchanged with a stderr note and a broken stderr cannot replace it. Tests `test_g4in_02_*`, `test_d58in_01_*`, `test_d58in_03_*` pass. |
| G4IN-03 (diagnostic runner launches second probe after pid-record failure) | FIXED | `tests/libretro/retroarch_smoke.py:855-864` skips the second launch and records `{"probe": "core_content", "status": "not-run", "reason": "skipped-after-pid-record"}`; `compare_launch_probes` (`:202-207`) still returns `diagnostic-pid-record-failed`. `test_g4in_03_pid_record_failure_skips_second_probe` asserts one launch call and the normal two-call path. No consumer reads `probes.core_content` fields. |

### Judgments requested for this round

**D58IN-02 (rights gate does not compare the working-tree digest): not a defect, not raised.** The predicate proves that the cited commit holds bytes with the recorded digest; a row whose file changed after the cited commit passes `--check-docs`, but `tools/public_content.py` (`rights-digest`, run from `.github/workflows/ci.yml` when the public-content plan flag is set) compares the working-tree digest, and all 46 digests match at HEAD (probed). The gap is a scope split, documented in `docs/rights-inventory.md:21-32` as "the whole definition". It would become a defect only if the public-content CI job could be skipped for a change to an inventoried file; I did not find such a classification path in the files in scope.

**ProcessGroupTest startup race: yes, structurally present; raised as G5WR-02.** I ran `ProcessGroupTest` three times with 40 CPU-bound Python processes running (24 tests, OK each time) and a bare `python3 -c pass` takes about 30 ms here, so the margin is roughly 30x and the failure is rare, which fits one error in 14 runs.

## Warnings

### G5WR-01: Rights `source_revision` gate requires branch commits to be ancestors of head, but the repository only allows squash merges

**File:** `tools/verify_playable.py:1403-1440` (`rights_revision_errors`), wired at `:1568`; `tests/tools/test_verify_playable.py` `test_g4wr_04_repository_rights_revisions_resolve`; `docs/rights-inventory.md:21-32`
**Issue:** Every non-`third_party/` row cites a development-branch commit, and the gate fails when that commit does not resolve or is not an ancestor of the checked head. `gh api repos/szTheory/glueyneo` reports `allow_squash_merge: true`, `allow_merge_commit: false`, `allow_rebase_merge: false`, `delete_branch_on_merge: true`. After this branch is squash-merged, `main` HEAD is a new commit that is not a descendant of any cited branch commit, so `merge-base --is-ancestor` exits non-zero for about 25 rows. In a fresh clone the branch commits are not fetched at all, so `rev-parse --verify` fails with `does not resolve`. `main` today is a single commit (`git rev-list --count main` = 1), so no cited revision is on it. The consequence is that `python3 tools/verify_playable.py --check-docs` and the `qualification_runner` CTest (which runs the real-repository test whenever `.git` exists) fail on `main` after the milestone ships, and no later refresh can fix it, since a row cannot cite the commit that contains the refreshed row. The review-provenance check (`review_provenance_errors`, same ancestry rule, pre-existing) has the same exposure, but this round extends it from a handful of review revisions to 25+ rows in a gate that runs on every CI.
**Fix:** Decide the merge strategy before shipping and make the gate match it. Either allow merge commits or rebase merges for milestone PRs, or make the rights check tolerate squash: when a cited revision does not resolve or is not an ancestor, fall back to requiring that the working-tree file at `path` hashes to the recorded `sha256` (the existing `public_content` digest) and report the row as `unverifiable-history` rather than failing. Add a test that squashes a branch into a fresh `main` and runs `rights_revision_errors` against it. State the chosen rule in `docs/rights-inventory.md` and `docs/testing.md`.

### G5WR-02: Lane-signalling tests have no readiness handshake with the child they SIGTERM

**File:** `tests/tools/test_verify_playable.py:629-652` (`test_g2in_02_lane_drains_pipe_during_grace`), `:654-678` (`lane_output_after_timeout`), `:689-748` (`g4_lane` users: CRLF, multibyte, non-UTF-8 timeout, detached-holder tests), `:779-815` (`test_d58wr_02_...`)
**Issue:** Each of these tests starts a fresh `python -c` child and relies on a fixed wall-clock budget (`communicate(timeout=1)` or `timeout=2`) for the child to start the interpreter, install its SIGTERM handler and (for most) write its first marker. Nothing confirms that happened before `_terminate_lane_group` sends SIGTERM. If startup takes longer than the budget (a loaded CI runner, the other CTest cases building in parallel, first-launch scanning on macOS), SIGTERM arrives under the default disposition: the child dies without writing `LATE`/`TAIL-MARKER`, or `EARLY`/`A` was never written, and the test fails on an output assertion. `test_d58wr_02` reads `lane.pid` after the run, which does not exist if the child never ran, and raises `FileNotFoundError`; that is an error, not a failure, and matches the one `FAILED (errors=1)` at closeout that did not reproduce in 14 later runs (the assertion-style tests would be reported as `failures=1`). The tests assert exact byte output, so the gate is red on timing, not on a regression, and a rerun hides it.
**Fix:** Make readiness explicit instead of sleeping. For the direct-`Popen` tests, have the child create a marker file (or write `READY` that the test reads with `proc.stdout.readline()`/`select` before calling `communicate`) after the handler is installed and the first marker is flushed, then start the timeout. For the `Runner.command` tests, the child cannot be waited on first, so raise the lane `timeout` well above the worst startup (for example 10 s) and have the child end itself after a bounded sleep, or poll for the marker file from a helper thread and shorten only the post-ready window. Read `lane.pid` with a bounded retry and fail with a clear message if it never appears.

## Info

### G5IN-01: `third_party/` rows skip the path-form check, and a non-list `items` raises a bare `TypeError`

**File:** `tools/verify_playable.py:1424-1430`
**Issue:** The exemption `path.startswith("third_party/")` runs before `_rights_path_is_relative_posix`, so a row such as `third_party/../tests/x.py` is exempt from the revision binding although it names a non-third-party file. Separately, `json.loads(blocks[0])["items"]` is not checked to be a list: `"items": 3` raises `TypeError` out of `check_docs` instead of the `rights inventory JSON is malformed` message used for the other shapes. Both need an edit to the inventory itself, so the impact is low.
**Fix:** Apply the path-form check first, then the prefix exemption (`not path.startswith(RIGHTS_EXEMPT_PREFIX)` on the normalized form), and raise `RuntimeError("rights inventory JSON is malformed")` when `items` is not a list.

---

_Reviewed: 2026-10-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
