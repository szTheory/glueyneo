---
phase: 04-public-playable-tracer
reviewed: 2026-10-12T00:00:00Z
depth: standard
diff_base: 2ec2e64f695e23c2e63990008fd909238c14e2d4
reviewed_head: 87d76c8843c263e405ba660a943c8b0aaddac1d4
files_reviewed: 5
files_reviewed_list:
  - tools/verify_playable.py
  - tools/public_content.py
  - tests/tools/test_verify_playable.py
  - tests/tools/test_private_paths.py
  - tests/workflow/test_public_content.py
findings:
  critical: 0
  warning: 0
  info: 3
  total: 3
status: issues_found
---

# Phase 04: Gap-Closure Re-Review R10 (G9 fixes and the two crosswalk gate fixes, diff-scoped)

**Reviewed:** 2026-10-12
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

This round reviews `git diff 2ec2e64..87d76c8` over the five listed files. All three R9 findings are confirmed fixed, and both gate fixes from commit 6510e09 are sound. I found no way for either to accept a wrong scope. Three info items remain.

| Check | Result |
|---|---|
| `python3 -m unittest tests.tools.test_verify_playable.CrosswalkProvenanceTest` | 9 tests, OK |
| `python3 tests/tools/test_private_paths.py` | 32 tests, OK |
| `python3 tests/workflow/test_public_content.py` | 18 tests, OK |
| `python3 tools/verify_playable.py --check-docs` | "Phase 04 documentation gate passed." |

No source file was modified and RetroArch was not run.

## Verdicts on the R9 findings

- **G9WR-01: CONFIRMED FIXED.** `tests/tools/test_private_paths.py:218` now parenthesises `(RUNNER_HOME + "/work/x").replace("/", "∕")`. Every separator, including the root's, is converted again, so the fully homoglyph runner-home input is covered as it was originally.
- **G9IN-01: CONFIRMED FIXED.** `tools/public_content.py` builds `_SYNTHETIC_PATH_OBJECT_IDS` and raises `RuntimeError` at import time on a repeated ID inside the tuple or on any collision with the pre-existing `HISTORY_FINDING_DISPOSITIONS` keys. It is an explicit raise, not an `assert`, so `python -O` cannot strip it. It runs before the `update`, so nothing is overwritten first. The module imports cleanly, so today's 94 + 4 rows pass. See G10IN-02 for the missing test.
- **G9IN-02: CONFIRMED FIXED.** `tests/workflow/test_public_content.py:138-142` adds the three lookalikes as subtests (a trailing-domain suffix, a prefixed local part, a subdomain). Each asserts `private-identity`. The suite passes, so the exact-match property is pinned.

## Gate fix 1: `crosswalk_errors` draws reviewed paths from `review_round_paths`

Sound. It cannot widen to arbitrary paths:

- The reviewed set comes only from the `files_reviewed_list` frontmatter block, via the unchanged `_reviewed_paths`. That function reads only `_frontmatter(...)` lines and stops at the first non-list line, so a body list or a code block in a round file adds nothing.
- `_reviewed_paths` still raises on duplicate frontmatter keys, and `review_round_paths` calls it for every round file, so duplicate-key rejection applies to rounds as well (a crash with `RuntimeError`, consistent with the existing 04-REVIEW.md behaviour).
- The glob is non-recursive and confined to `PHASE_DIRECTORY` under `source_root`.
- The other path checks are unchanged and run first: the parent-segment and absolute-path rejection, and `(source_root / path).is_file()`. A reviewed entry therefore only matters for paths that already exist as files in the root.
- In a clean snapshot root, only the rounds copied there count. `DocumentationCopies.copy_review_provenance` copies the same glob through `REVIEW_ROUNDS`, so the test snapshot and the gate agree. A snapshot missing a round gets a narrower set (fail closed), never a wider one.
- `test_scope_may_cite_a_path_reviewed_only_by_a_later_round` computes the "later only" set and asserts `tools/public_content.py` is in it, so the new capability is tested against the real tree.

## Gate fix 2: `THREAT_REFERENCE` and `_register_threats`

Sound. The pattern `T-04-(?:\d{2,}(?!\d)|SC \(04-\d{2}\))` reads a whole ID. Because `(?!\d)` follows the greedy run, backtracking cannot produce a prefix match: `T-04-103` yields `T-04-103`, not `T-04-10`. The test pins `T-04-103 / T-04-10 / T-04-SC (04-58)` and that `T-04-109999` is rejected as unknown.

- Newly accepted: only three-digit (or longer) IDs that actually appear as register rows. `04-SECURITY.md` has rows `T-04-102` through `T-04-109`. These were previously skipped, so scopes citing them used to fail (or be misread as a two-digit prefix). That was the bug, and it is fixed.
- Newly rejected: nothing legitimate. A scope citing an ID absent from the register is still rejected, now by its whole ID.
- Single-digit IDs are still not matched, as before.
- Other consumers: `_register_threats` and `THREAT_REFERENCE` are used only inside `verify_playable.py` (`crosswalk_errors` and the register parser). `tools/independent_review.py:70` has its own, separate pattern that already allows more than two digits. The parser change therefore alters no other consumer.

## Info

### G10IN-01: `_review_round_findings` hardcodes the round glob

**File:** `tools/verify_playable.py:1304`
**Issue:** The new `REVIEW_ROUNDS` constant is used by `review_round_paths` and the test helper, but `_review_round_findings` still spells `"04-REVIEW-GAPS*.md"` inline. The two sets of rounds (paths cited and findings requiring a disposition) must stay identical, and a future rename would silently split them.
**Fix:** `sorted(directory.glob(REVIEW_ROUNDS))`.

### G10IN-02: The G9IN-01 import-time guard has no test

**File:** `tools/public_content.py:206-209`
**Issue:** The guard is correct today, but nothing exercises it, so removing or loosening it would pass the suite. The condition cannot be triggered through the module without re-importing a modified table.
**Fix:** Move the check into a small function taking the pre-existing keys and the synthetic rows, and unit test it with a duplicate and a collision.

### G10IN-03: Round file path lists are self-attested, and the register change has only a parser-level test

**File:** `tools/verify_playable.py:1266-1272`, `tests/tools/test_verify_playable.py:1384-1387`
**Issue:** Any new `04-REVIEW-GAPS*.md` file can add paths to the citable set by listing them. This is acceptable (the file must exist, and the round's own findings need dispositions through `_review_round_findings`), but it is a trust boundary worth stating in the docstring. Separately, the three-digit test checks `findall` and one unknown-ID rejection, but no test asserts that a scope citing a real three-digit register row (for example `T-04-103`) now passes.
**Fix:** Add a short docstring sentence, and a positive test using `self.with_scope("CR-05", "T-04-103")` expecting no errors.

Note for the caller: finding headings in this file match `REVIEW_FINDING_HEADING` (`G10IN-NN`), so the disposition record needs rows for G10IN-01 to G10IN-03 or `--check-docs` will fail on the next run.

---

_Reviewed: 2026-10-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
