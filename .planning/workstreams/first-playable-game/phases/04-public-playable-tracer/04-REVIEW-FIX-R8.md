---
phase: 04-public-playable-tracer
fixed_at: 2026-10-11T00:00:00Z
review: 04-REVIEW-GAPS-R8.md
review_path: .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-GAPS-R8.md
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report (Round 8)

**Source review:** 04-REVIEW-GAPS-R8.md
**Iteration:** 1
**Scope:** G8IN-01 (info; scope `all`).

All verification ran in the main checkout (`workflow.use_worktrees: false`).

## Fixed Issues

### G8IN-01: The recorded reason for not adding a post-squash stale gate is wrong

**Commit:** bd48475
**Files:** `docs/testing.md`, `tools/verify_playable.py` (docstring only)
**Fix:**
- `docs/testing.md` ("History gates after a squash merge"): the false claim is gone. It said a legitimate post-squash rights refresh "voids a listed row" and that failing on it would leave "no way to proceed". The text now uses the review's wording: an unrefreshed edit to a listed rights file already fails the tolerated branch's digest check, a refreshed row cites a main commit and is evaluated strictly, and an orphaned allowlist row is inert. The allowlist cannot be edited after the squash because `ci` mode refuses on squashed history, so a gate that failed on orphaned rows could never be satisfied.
- `history_allowlist_check_applies` docstring: the same reasons were added. The old docstring did not state the false claim itself. It only said `--check-docs` is the post-squash gate.
- I searched for other copies of the claim ("voids a listed row", "no way to proceed", "stuck with no way", staleness wording) in `.github/`, `CMakeLists.txt`, `tools/`, `docs/` and the READMEs. There are no other current contract copies. The `history_allowlist_stale` docstring (`tools/verify_playable.py`, "A voided row is already evaluated strictly") is accurate and was left alone.
- **Dated record not rewritten:** `04-REVIEW-FIX-R7.md` still gives the incorrect rationale under its G7WR-02 deviation bullet. It is a dated record. Treat this report and the corrected `docs/testing.md` as superseding that sentence. The deviation itself, adding no stale gate, stands as R8 assessed it.

**Rights inventory:** Neither edited file is pinned by SHA-256 in `docs/rights-inventory.md`, so no row needed refreshing. Only `tests/tools/test_verify_playable.py` is pinned among the tooling files, and it was not touched.

## Verification

| Check | Result |
|---|---|
| `python3 -c "import ast; ..."` on `tools/verify_playable.py` | parses |
| `python3 tests/tools/test_verify_playable.py` (the CTest runner) | Ran 167 tests (about 148 s): FAILED (failures=8, errors=5). Every failure and error is `review findings have no disposition record: G8IN-01`, either raised directly or as the first `check_docs` error hiding the error a test expects. These tests run `check_docs` against the live records. The cause is the R8 review file committed at eec37f1, not this fix, which changes only prose and a docstring. They should pass once the orchestrator records the G8IN-01 disposition. Affected tests: ConsumerInputTest (4), EvidenceBindingTest (1), GuideClaimTest (1), ReviewProvenanceTest (2, including the t_04_38 subtests), CrosswalkProvenanceTest (2), RightsRevisionTest (1). |
| `python3 tools/verify_playable.py --check-docs` | exit 1: `review findings have no disposition record: G8IN-01`. This is expected until the orchestrator records the disposition. There were no other errors. |
| `python3 tools/verify_playable.py --history-allowlist check --base origin/main` | `History allowlist is current (145 rows).` exit 0, at committed HEAD bd48475 before any disposition edits |

Not touched: the two `.planning/preparation` files, `04-REVIEW-DISPOSITION.md`, `04-VALIDATION.md` and `docs/history-allowlist.json`. No push. RetroArch was not launched. This report is uncommitted.

---

_Fixed: 2026-10-11_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_

## Orchestrator follow-up

The G8IN-01 disposition and crosswalk rows were recorded after this fix, along with the six G7 rows moved to "Confirmed fixed by 04-REVIEW-GAPS-R8.md (eec37f1)". The G7WR-02 Source cell now gives the corrected reason. The allowlist was regenerated against these records with `--history-allowlist write --base origin/main` (146 rows, base 4b2120d57f48). The gate results after that commit are listed in the commit that adds this report.
