---
phase: 04-public-playable-tracer
plan: 60
subsystem: verification-gates
tags: [history-allowlist, generator, squash-simulation, G5WR-01, scope-split]
requires:
  - phase: 04-public-playable-tracer
    provides: "04-59 per-row history allowlist gates"
provides:
  - "history_allowlist_document / history_allowlist_is_current and CLI `--history-allowlist {write,check}` with `--base`"
  - "Passing real-repository squash simulation of --check-docs (132 of 132 rows tolerated, one line per row)"
  - "Scope-split halt: 6 history-dependent clone-only suite failures recorded and classified"
affects: [04-61, 04-62]
tech-stack:
  added: []
  patterns: ["strict-precheck generator", "per-record pins", "merge-base scoped listing"]
key-files:
  created: []
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - docs/rights-inventory.md
key-decisions:
  - "Generator lists only rows whose revision is not reachable from `git merge-base HEAD <base>` and only after the three gates pass strictly with an empty allowlist"
  - "Review tolerance notes carry the revision as written so 12-hex and 40-hex citations of one commit remain distinct lines"
  - "More than 5 history-dependent suite failures: halt with scope-split-needed, repair nothing"
status: complete
commits: 6
plan_head_before: 08b54777292bd2a46f2eff4fc067a7af0c1c9400
plan_head_after: 7f6a63a7c9f4417e932ea6549e1965450e9ea013
actuals:
  tokens: 55000
  tasks: 3
  commits: 6
completed: 2026-10-11
---

# Phase 04 Plan 60: G5WR-01 allowlist generator and squash simulation Summary

The deterministic, merge-base-scoped allowlist generator and freshness check exist and are proven on the real repository: a simulated squash of HEAD passes `--check-docs` with exactly one `unverifiable-history:` line per allowlist row (132 of 132); the clone suite shows 6 history-dependent failures, which exceeds the plan's bound of 5, so the plan halted with `scope-split-needed: 6` and repaired none.

## Commits

- START (diff base for the next `/gsd-code-review`, 04-59..04-62 base is 04-59's START `cfdf4a07a28a651abcf2af72761a69846bbd7d22`; this plan's base): `08b54777292bd2a46f2eff4fc067a7af0c1c9400`
- RED 1: `1ebc1be` test(04-60) generator, freshness and CLI cases (8 tests; fixture helper gained an optional base-row variant, no assertion changed)
- FIX 1: `9dc602c` fix(04-60) `history_allowlist_document`, `history_allowlist_is_current`, CLI
- DOCS 1: `2b20ab7` rights inventory refresh (needed before the simulation, see Deviations)
- RED 2: `2b4c011` test(04-60) one note per listed revision form
- FIX 2: `2666755` fix(04-60) review notes carry the revision as written
- DOCS 2: `7f6a63a` rights inventory refresh after the note fix
- Evidence line: `G5WR-01-allowlist-generator red 1ebc1be642f4 exit 1 green 9dc602c36f8f ok` (red: 7 failures, 1 error; green: 8 OK)

## Generator behavior

`python3 tools/verify_playable.py --history-allowlist write [--base <rev>]` form-checks `--base` before Git, computes M = `git merge-base HEAD <base>`, runs the frontend, review and rights gates strictly with an empty allowlist (any error or note refuses with `history allowlist cannot be generated: <first>`), then lists only rows whose revision is not an ancestor of M, with the 04-59 per-record pin. Output is sorted JSON with `base_revision` and no timestamp or path. `check` prints `History allowlist is current (<n> rows).` or fails with `history allowlist is stale or missing; run --history-allowlist write; stale rows: ...`. No allowlist is committed (`docs/history-allowlist.json` is absent in the main checkout).

## Squash simulation (real repository)

| Run | Allowlist rows | `--check-docs` | SIM-CHECK | Suite | Provisioned |
| --- | --- | --- | --- | --- | --- |
| 1 | 132 | exit 1: stale digest of the test file's inventory row | not run | 7 failures | none |
| 2 (after DOCS 1) | 132 | exit 0 | 129 lines vs 132 rows | 6 failures | none |
| 3 (after FIX 2, DOCS 2) | 132 | exit 0 | `squash check-docs ok 132 tolerated of 132 rows` | 6 failures | none |

Row kinds: 89 review_citation, 41 rights, 1 frontend_receipt, 1 reviewed_revision.

### Classification of the first full clone-only failure list

All six are history-dependent; none is environmental (no ignored `build/` input is involved, so the environmental and provision lists are empty).

| Test | Class | Cause |
| --- | --- | --- |
| ConsumerInputTest.test_check_docs_accepts_complete_status_generated_from_tracked_receipt | history-dependent | copied docs checked with `repository=ROOT`; the tolerated rights row `fixtures/diagnostic/manifest.json` has no working-tree copy in the temp dir |
| ReviewProvenanceTest.test_check_docs_binds_the_live_record_and_rejects_a_stripped_revision | history-dependent | same |
| ConsumerInputTest.test_check_docs_requires_generated_status_to_match_evidence | history-dependent | same (rights tolerance error precedes the asserted error) |
| GuideClaimTest.test_digests_and_pinned_revisions_outside_the_block_are_allowed | history-dependent | same |
| EvidenceBindingTest.test_explicit_repository_binds_the_copied_evidence | history-dependent | same |
| ConsumerInputTest.test_tracked_receipt_must_match_its_committed_inventory | history-dependent | `git checkout` of the live receipt `source_revision` in a clone; that commit is absent after the squash |

Five of the six share one apparent cause (the documentation-copy helper does not copy the working-tree files of tolerated rights rows). That is an observation for the follow-up plan, not a repair made here: the plan's scope gate counts tests, 6 > 5.

## Halt

`build/playable-qualification/04-59-branch.txt` holds `review-halt` / `scope-split-needed: 6`. Task 2 steps 3-6 (post-repair re-runs, LOCAL-SQUASH, full-history rehearsal, later-branch probe) were not run; SUITE-CHECK was not run because the classified failures are history-dependent and cannot be listed environmental. Route: `/gsd-plan-phase 04 --gaps --ws first-playable-game` for a follow-up gap-closure plan covering the six tests. 04-61 and 04-62 read the marker.

## Deviations from Plan

**1. [Rule 3 - Blocking] RIGHTS-REFRESH before the simulation**
- **Found during:** Task 1 simulation run 1
- **Issue:** Task 3 schedules the rights refresh last, but the clone's `--check-docs` compares the tolerated row's working-tree digest and the test file had changed, so it failed.
- **Fix:** ran the refresh (digest and last-touching revision of the one changed row) and committed it alone before the simulation, and again after FIX 2.
- **Files modified:** docs/rights-inventory.md
- **Commits:** `2b20ab7`, `7f6a63a`

**2. [Rule 1 - Bug] Duplicate notes hid allowlist rows**
- **Found during:** Task 1 SIM-CHECK (129 vs 132)
- **Issue:** a finding citing one commit as both 12-hex and 40-hex lists two allowlist rows but printed one deduplicated note, violating one visible line per row.
- **Fix:** test-first (`test_g5wr_01_one_note_per_listed_revision_form`); the review note carries the revision as written. Existing assertions unchanged.
- **Files modified:** tools/verify_playable.py, tests/tools/test_verify_playable.py

No existing assertion changed result; no gate was loosened; no test was skipped.

## Residuals and known limits

- A test that is both history-dependent and satisfied by supplying an ignored `build/` input cannot be distinguished mechanically; the history-dependent/environmental label is executor-authored and is reviewed by the diff-scoped /gsd-code-review (not exercised this run: no environmental entries).
- On the squashed clone only qualification_runner (`tests/tools/test_verify_playable.py`) and `--check-docs` run, not the other qualification CTest entries.
- Frontmatter requirement IDs are inherited Phase 04 coverage, not new delivery.

## Verification

Main checkout: `test_independent_review` (70), `test_check_security_register` (65), `test_verify_playable` (149), `test_retroarch_smoke` (78) all OK; branch `--check-docs` passes with no `unverifiable-history:` line; no allowlist tracked; tree clean apart from `.planning/preparation`.

## Known Stubs

None.

## Threat Flags

None beyond T-04-106 (planned; 04-62 records the row).

## Next step

Phase 04 is not complete. Plan 04-60 halted at the scope gate (`scope-split-needed: 6`). Next concrete command: `/gsd-plan-phase 04 --gaps --ws first-playable-game` for the follow-up repair of the six history-dependent tests; 04-61 and 04-62 remain pending and read the halt marker.

## Self-Check: PASSED
