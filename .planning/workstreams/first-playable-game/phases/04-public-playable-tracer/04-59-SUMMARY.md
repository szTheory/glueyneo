---
phase: 04-public-playable-tracer
plan: 59
subsystem: verification-gates
tags: [history-allowlist, squash-merge, rights-provenance, review-provenance, frontend-receipt, G5WR-01]
requires:
  - phase: 04-public-playable-tracer
    provides: "04-58 round-5 review and G5WR-01 finding"
provides:
  - "Per-row, per-record-pinned allowlist tolerance of history-absent pre-ship rows in the rights, review-provenance and frontend-receipt gates"
  - "check_docs returns tolerated notes; CLI prints one `unverifiable-history:` line per tolerated row"
  - "history_allowlist_stale report; SquashMergeHistoryTest fixture suite"
affects: [04-60, 04-61, 04-62]
tech-stack:
  added: []
  patterns: ["per-record canonical-digest pins", "history-absent rule (unresolvable or unrelated history)"]
key-files:
  created: []
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - docs/rights-inventory.md
key-decisions:
  - "No repository-wide mode; tolerance is per listed row with per-record pin plus (rights) working-tree digest (user decision 2026-10-11, scope tolerance)"
  - "A revision resolving on unrelated history is history-absent, so a local squash behaves like a fresh clone"
  - "Ancestor and descendant revisions and unlisted or edited rows stay strict; stale allowlist rows are reported, not a check_docs failure"
status: complete
commits: 5
plan_head_before: cfdf4a07a28a651abcf2af72761a69846bbd7d22
plan_head_after: dfba807067e8631eb2953a5d708e93fc0e916a02
actuals:
  tokens: 60000
  tasks: 3
  commits: 5
completed: 2026-10-11
---

# Phase 04 Plan 59: G5WR-01 per-row history allowlist Summary

Per-row allowlist tolerance (pinned per record, digest-bound) lets pre-ship rows of the first-playable-game branch pass `--check-docs` after a squash merge, in all three history gates, while every ancestor, descendant, unlisted or edited row stays strict.

## Commits

- START (diff base for the next `/gsd-code-review`): `cfdf4a07a28a651abcf2af72761a69846bbd7d22`
- RED 1: `f3f80ca` test(04-59) rights row and CLI line
- FIX 1: `37e9f0f` fix(04-59) allowlist loader, pins, rights tolerance, check_docs notes, CLI lines
- RED 2: `71f937b` test(04-59) review, receipt and adversarial cases
- FIX 2: `1a20824` fix(04-59) review and frontend gates, `history_allowlist_stale`, DocumentationCopies copies the allowlist
- DOCS: `dfba807` docs(04-59) rights inventory refresh (only `tests/tools/test_verify_playable.py` changed)
- Evidence line: `G5WR-01 red f3f80ca43d2c exit 1 green 1a208248331f ok`

## Decision and constraints

User decision (2026-10-11, "Scope tolerance"): no global mode; tolerance per row. Scope interpretation (orchestrator, 2026-10-11): the allowlist covers pre-ship records of the first-playable-game milestone branch; notes say `allowlisted pre-ship row (first-playable-game branch)`.

- Tolerated only if the revision is history-absent (unresolvable, or resolving on unrelated history), the row is listed with a pin equal to the current record, and for rights the working-tree file hashes to the recorded sha256.
- Pins are per record: `reviewed_revision` field, the finding's disposition row, the canonical receipt digest, the inventory item. Appends void nothing (tested); editing a row voids only that row (tested).
- Path-form and 40-hex checks still run before any Git call (`test_g5wr_01_form_checks_precede_git`).
- No repository-wide mode exists (`phase_history_complete` absent; no environment or history-shape switch). No allowlist is committed; fixture allowlists live in temporary directories. Merge settings untouched.

## Verification

- `-k g5wr_01`: 15 tests OK. Full `tests/tools/test_verify_playable.py`: 140 tests OK.
- `ReviewProvenanceTest`, `RightsRevisionTest`, `EvidenceBindingTest`, `ConsumerInputTest`: 35 tests OK; no existing assertion changed result.
- Branch `--check-docs` passes with no `unverifiable-history:` line; the branch probe printed `branch history fully verified`.
- Rights inventory validates (`inventory ok`).

## Deviations from Plan

None - plan executed as written. The Task 1 RED commit was used as the RED reference for the red/green evidence line as the plan states; the Task 2 RED commit adds 13 further cases. In one test (`side_branch_and_descendant`) a tracked-file restore of the inventory was added to the fixture before a detached checkout (test fixture fix, no behavior change). Deleted debris: none (no `04-59-*` files existed).

Frontmatter requirement IDs are inherited Phase 04 coverage, not new delivery by this gap-closure plan.

## Known Stubs

None.

## Threat Flags

None beyond T-04-104 (planned; 04-62 records the row).

## Next step

Execute plan 04-60 (same `/gsd-execute-phase 04 --ws first-playable-game` run when it continues to wave 57). Phase 04 is not complete.

## Self-Check: PASSED
