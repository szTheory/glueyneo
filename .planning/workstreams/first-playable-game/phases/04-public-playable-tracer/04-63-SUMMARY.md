---
phase: 04-public-playable-tracer
plan: 63
subsystem: qualification-tests
tags: [squash-merge, history-gates, test-fixtures, G5WR-01]
requires: [04-62]
provides:
  - qualification suite passes in full in a squash-simulated fresh clone
affects: [04-64, 04-65]
tech-stack:
  added: []
  patterns: [forge receipts against the checkout's own HEAD; full-history sibling with explicit recorded skip]
key-files:
  modified:
    - tests/tools/test_verify_playable.py
    - docs/rights-inventory.md
    - docs/testing.md
key-decisions:
  - "C1 fixed in the test helper (copies rights-row working-tree files, never overwrites); gates untouched"
  - "C2 and C3 repaired by forging receipts against the checkout's own HEAD, same asserted outcomes"
  - "Live receipt inventory binding stays pinned on full history by a sibling test that skips only when the revision is absent"
requirements-completed: [QUAL-03]
status: complete
commits: 7
plan_head_before: 4bb76b3241977859920ac2f5acf70f7c0b935cd3
plan_head_after: c0bfda9333f01a909ea2a04bdbcf4555526e3c53
actuals:
  tokens: 14000
  tasks: 3
  commits: 7
completed: 2026-10-11
---

# Phase 04 Plan 63: Squash-merge history repair of the qualification suite Summary

The six tests that failed only in a squash-merged clone (04-60 halt `scope-split-needed: 6`) are repaired at their causes in the test fixtures, with a red squash run at START and a green one at the final revision; no gate was changed. QUAL-03 is restored evidence, not new delivery.

## Revisions

- START: `4bb76b3241977859920ac2f5acf70f7c0b935cd3`
- RED `e8f5a981ad64` (test), FIX `02fe1c807354` (C1 helper), rights refresh `e82f80ab7aaf`, C2 `d5f3293`, C3 `027e417`, docs `8c622e2`, rights refresh `c0bfda9`.
- No orchestrator-edits commit was needed (tree was clean at start); no stale `04-63-*` records existed.

## Evidence lines (`build/playable-qualification/04-63-evidence.txt`)

```
G5WR-01-doc-copies red e8f5a981ad64 exit 1 green 02fe1c807354 ok
G5WR-01-squash-suite red 4bb76b324197 failures 6 green c0bfda9333f0 ok tests 156
C2-live-binding main ok squashed skipped: live receipt revision 4e6a40e66e9e absent from history (squashed checkout); binding is pinned on full history
```

## Red squash run at START (run 1, GEN=1)

Ran 154 tests, `FAILED (failures=1, errors=5)`; the set equals the six 04-60 failures.

| Test | Class | Cause |
|------|-------|-------|
| test_check_docs_accepts_complete_status_generated_from_tracked_receipt | C1 | helper omits rights-row working-tree files |
| test_check_docs_binds_the_live_record_and_rejects_a_stripped_revision | C1 | same |
| test_check_docs_requires_generated_status_to_match_evidence | C1 | same |
| test_digests_and_pinned_revisions_outside_the_block_are_allowed | C1 | same |
| test_explicit_repository_binds_the_copied_evidence | C1 + C3 | helper, then a second history dependency (below) |
| test_tracked_receipt_must_match_its_committed_inventory | C2 | checks out the live receipt `source_revision` |

## Simulation runs

| Run | Revision | check-docs | Suite | Result |
|-----|----------|-----------|-------|--------|
| 1 | START | exit 0 | exit 1 | 6 failures (above) |
| 2 | after C1 FIX + refresh | exit 0 | exit 1 | 2 errors: C2 test and test_explicit_repository_binds_the_copied_evidence (C3) |
| 3 | HEAD `c0bfda9` | exit 0 | exit 0 | Ran 156, `OK (skipped=1)` (the full-history sibling, history-absent reason) |

Run 3 checks: SIM-CHECK `squash check-docs ok 132 tolerated of 132 rows`; the five C1 tests each `Ran 1 test` / `OK` by name in the squashed clone; SUITE-CHECK `squash suite ok 0 causally verified environmental: []`; LOCAL-SQUASH `local squash matches fresh clone`. No environmental entries or provisioning.

## Refactors: before and after assertions

- C2 `test_tracked_receipt_must_match_its_committed_inventory`: before, a clone of ROOT was checked out at the live `summary["source_revision"]` and the receipt forged with zero `inventory_sha256` (asserts `RuntimeError` matching `inventory digest does not match`). After, the receipt is forged with `source_revision` = ROOT HEAD (also checked out in the clone) and zero digest; the same message is asserted; `assertIsNotNone(load_frontend_evidence(ROOT))` is kept.
- New sibling `test_live_receipt_binds_its_committed_inventory_on_full_history`: when the live revision is an ancestor of HEAD, asserts `load_frontend_evidence(ROOT, unverifiable=notes)` is not None with `notes == []`, then the pre-refactor forged-at-live-revision `inventory digest does not match`. Otherwise `skipTest('live receipt revision <12> absent from history (squashed checkout); binding is pinned on full history')`. Results: main checkout `ok`, full-history working clone (`sim-branch`) `ok`, squashed clone skipped with that reason.
- C3 `test_explicit_repository_binds_the_copied_evidence`: before, `rev-parse <live revision>^` as `head` (asserts `not a committed ancestor`), then zero digest with the live receipt (asserts `inventory digest does not match`). After, the receipt is forged against ROOT HEAD (guide status block and validation row regenerated for it), `head=HEAD^` asserts `not a committed ancestor`, then zero digest asserts `inventory digest does not match`. The initial `check_docs(source_root, repository=ROOT)` on the live receipt is unchanged.
- Helper `DocumentationCopies.copy_review_provenance` now copies each non-third_party rights-row file from the ROOT working tree, never overwriting a caller-placed file; guard `test_g5wr_01_documentation_copies_carry_rights_row_files`.

## Deviations from Plan

**1. [Rule 1 - Bug] Third history dependency (C3) in test_explicit_repository_binds_the_copied_evidence**
- **Found during:** Task 2 (green run 2)
- **Issue:** After the C1 fix this test still errored in the squashed clone because it resolves `rev-parse <live receipt revision>^`, and a later assertion needs the live revision in history. The plan attributed it to C1 only.
- **Fix:** equivalent fixture refactor with identical asserted messages (see above), committed on its own (`027e417`), as the plan's rule for an extra failure allows. Only one repair batch was needed; run 3 was green.
- **Files modified:** tests/tools/test_verify_playable.py

**Total deviations:** 1 auto-fixed (Rule 1). **Impact:** none on scope; no gate, allowlist or record touched.

## Scope and gates

- `git diff --name-only START HEAD` lists only tests/tools/test_verify_playable.py, docs/rights-inventory.md, docs/testing.md (plus this SUMMARY). `tools/` and `docs/history-allowlist.json` untouched; hygiene scan of START..HEAD found no personal absolute paths.
- Main checkout: the four suites `OK` (verify_playable 156 tests); ctest `100% tests passed out of 63`; branch `--check-docs` passes with no tolerated-row line; security register gate exits 0; `pgrep -x RetroArch` exits 1.
- Threat T-04-107 mitigated: copies come only from non-third_party rights rows, never overwrite, guard compares bytes with ROOT.

## Known Stubs

None.

## TDD Gate Compliance

RED `test(04-63)` precedes FIX `fix(04-63)`; RED-PROOF exit 1 at `e8f5a981ad64`, green at `02fe1c807354`.

## Next step

Phase 04 is not complete. No halt marker was written (`04-63-branch.txt` absent). Continue with `/gsd-execute-phase 04 --ws first-playable-game` for 04-64 (records, allowlist freeze, rehearsal and later-branch probes), then 04-65.

## Self-Check: PASSED
