---
phase: 04-public-playable-tracer
reviewed: 2026-10-12T00:00:00Z
depth: standard
diff_base: d638d3ef086e957af7d40b2e64767af7e5c492d4
reviewed_head: 2ec2e64f695e23c2e63990008fd909238c14e2d4
files_reviewed: 5
files_reviewed_list:
  - tools/public_content.py
  - tools/verify_playable.py
  - tests/tools/test_private_paths.py
  - tests/workflow/test_public_content.py
  - docs/testing.md
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 04: Gap-Closure Re-Review R9 (G8 fix, scrub and disposition changes, diff-scoped)

**Reviewed:** 2026-10-12
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

This round reviews `git diff d638d3e..2ec2e64` over the five listed files. The G8IN-01 fix is confirmed. The history disposition merge and the email allowlist are sound: I found no way for a disposition to suppress a finding it should not. One test edit in `tests/tools/test_private_paths.py` silently weakened an input (G9WR-01). Two info items cover test and guard gaps.

What I ran (no source file was modified, RetroArch was not run):

| Check | Result |
|---|---|
| `python3 tests/workflow/test_public_content.py` | 18 tests, OK |
| `python3 tests/tools/test_private_paths.py` | 32 tests, OK |
| `python3 tools/verify_playable.py --check-docs` | "Phase 04 documentation gate passed." |
| Disposition table audit (script) | 94 new rows, 94 distinct IDs, 0 collisions with the 4 pre-existing IDs (merged table has 98). All 94 blobs exist in the repository. |
| Content audit of all 94 blobs (script) | Every `personal-path` match is synthetic (alice, bob, someone, synthetic, private-person, u, build, runner, `/private/var/folders/...`, detector regex fragments). No real user name appears. |

## Verdict on G8IN-01

**Confirmed fixed.** The new text in `docs/testing.md` (lines 278-289) and the `history_allowlist_check_applies` docstring (`tools/verify_playable.py:1922-1929`) now give the three correct reasons: an unrefreshed edit to a listed rights file fails the tolerated digest check, a refreshed row cites a main commit and is evaluated strictly, and an orphaned row is inert. They also state that the allowlist cannot be edited after the squash because `ci` mode refuses on squashed history. The wrong "legitimate refresh voids a row" rationale is gone. The `verify_playable.py` diff is docstring-only (6 lines); no code path changed. `--check-docs` passes.

## Hash-remap question

The diffs in `tools/verify_playable.py` and `docs/testing.md` against d638d3e are **not hash remaps**. They are exactly the G8IN-01 prose changes above. No commit hash was altered in either file within this diff range, so nothing remap-shaped needed checking here. (The remap commit a2e18e1 falls outside this diff base for these files.)

## Assessment of cbcd28b (dispositions and email allowlist)

- **Different rule:** `_git_history` (`tools/public_content.py:568-577`) requires `actual_rules == disposition["rules"]` exactly. A blob that gains `credential`, `private-identity` or any other rule raises `history-disposition`; a blob that loses all findings also raises. A rule outside `{"personal-path"}` cannot be suppressed.
- **Different path:** it also requires `path == disposition["path"]`, so the same blob appearing at another path fails closed.
- **Real home path added later in the same blob:** not possible. Disposition keys are blob object IDs (content-addressed); any edit produces a new ID that is scanned normally. The residual risk is only that an audited blob already contained a real path. I scanned all 94 blobs and every personal-path match is a synthetic placeholder.
- **Overwrite of pre-existing rows:** `HISTORY_FINDING_DISPOSITIONS.update(...)` could overwrite, but the 94 IDs are disjoint from the 4 pre-existing ones (merged size 98), so nothing was overwritten today. See G9IN-01 for the missing guard.
- **Email allowlist:** `email in PUBLIC_EMAILS` (`:247`) is an exact, case-folded match on the full regex-matched address. The only suffix match is the pre-existing `users.noreply.github.com` and synthetic TLD handling, unchanged. The Anthropic noreply address (local part `noreply`, domain `anthropic.com`) has no wildcard or domain exemption, and another local part at the same domain (`someone`) is still flagged.

## Warnings

### G9WR-01: The Unicode-slash runner-home variant lost its coverage

**File:** `tests/tools/test_private_paths.py:215`
**Issue:** The original loop tested the runner home path plus `/work/x`, and the same string with every `/` replaced by U+2215. The rewrite is `RUNNER_HOME + "/work/x".replace("/", "\u2215")`. Method call binds tighter than `+`, so only the tail is converted. I evaluated it: the second value now keeps the ASCII-slash `RUNNER_HOME` prefix and has U+2215 only in the `work/x` tail, instead of U+2215 at every separator. The fully-homoglyph path, which exercises `_canonical` normalisation of a leading Unicode separator and of the root itself, is no longer tested, although the commit is meant to be a no-input-change refactor. The suite passes, so the weakening is silent.
**Fix:**
```python
for value in (RUNNER_HOME + "/work/x", (RUNNER_HOME + "/work/x").replace("/", "∕")):
```
The other edits in that file (`_home(RUNNER_HOME, ...)`, `"/" + "Users/build"`, `"/" + "Users/alice"`) produce byte-identical inputs and are fine.

## Info

### G9IN-01: Merging the synthetic-path table has no duplicate or collision guard

**File:** `tools/public_content.py:206-210`
**Issue:** `dict.update` silently lets a later row replace an earlier one on the same object ID, including one with a different rule set (for example a Musashi `private-identity` row). Today there are no collisions (94 + 4 = 98), and the repeated `object_id` in the tuple would also collapse silently. The module comment says each row binds one ID to one path and the personal-path rule only, but nothing enforces it.
**Fix:** After building the table, assert `len(HISTORY_FINDING_DISPOSITIONS) == 4 + len(_SYNTHETIC_PATH_HISTORY_OBJECTS)` or build with a loop that raises `ValueError` on an existing key. A unit test over the same invariant would pin it.

### G9IN-02: The new email test pins only two inputs

**File:** `tests/workflow/test_public_content.py:132-137`
**Issue:** The test proves the noreply trailer address passes and the `someone` address at the same domain fails, which is the intended private-identity behaviour. It does not pin the exact-match property that the review question depends on: a lookalike is not covered: the noreply local part at `anthropic.com.evil.test`, the local part `xnoreply` at `anthropic.com`, or the noreply local part at `mail.anthropic.com`. Current code handles these correctly (full-address match), so this is a regression-guard gap only.
**Fix:** Add those three addresses as subtests asserting `private-identity` is reported.

---

_Reviewed: 2026-10-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
