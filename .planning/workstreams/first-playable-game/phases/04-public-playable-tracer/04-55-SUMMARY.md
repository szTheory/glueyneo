---
phase: 04-public-playable-tracer
plan: 55
subsystem: planning-gate
tags: [security-register, commonmark, gfm, tdd, fail-closed]
requires:
  - phase: 04-public-playable-tracer
    provides: 04-54 audit route; round-4 contained verdict on T-04-48 and T-04-62
provides:
  - Register checker ends a Threat ID table only at CommonMark ATX heading, blockquote or exact fence openers
  - Regression tests and guard for look-alike lines, with isolated red/green evidence
  - docs/testing.md table-end contract and refreshed rights rows
affects: [04-57]
actuals:
  tokens: 9000
  tasks: 2
  commits: 4
plan_head_before: ab4b64e9894bec6e20b95c862fb40b8fb0d064d2
plan_head_after: d26323e82b451a28d4815d2f4a63ee1c6499301b
tech-stack:
  added: []
  patterns: [read every non-block-start line as a row so disagreement fails closed]
key-files:
  created: []
  modified:
    - tests/tools/check_security_register.py
    - tests/tools/test_check_security_register.py
    - docs/testing.md
    - docs/rights-inventory.md
key-decisions:
  - "Option B: TABLE_END matches only CommonMark ATX heading, blockquote and exact fence openers; all other lines are rows and fail closed as malformed rows."
requirements-completed: [QUAL-03]
duration: 12 min
completed: 2026-10-10
status: complete
---

# Phase 04 Plan 55: CommonMark Table-End Rule Summary

**The security register checker now ends a Threat ID table only where CommonMark certainly starts another block, so `#note`, `####### x` and a backtick fence look-alike fail closed as malformed rows instead of hiding later open high rows.**

## TDD record

- RED commit `a3b7d2d44118aa0d10f9bf1a62d29c43ffc5df8e` (`test(04-55)`): three tests added to `GfmTableFormTest`, additions only. `-k table_end` fails on assertions (`0 != 1`), `FAILED (failures=6)`, no `errors=`; the guard `-k still_close_the_table` passes. Semantic assessment: the target tests ran, and failed because the checker exited 0 where the hidden third open row required exit 1.
- GREEN commit `045ed1c6ab93d77773d423e82e67cc80a5a9dc7e` (`fix(04-55)`): `TABLE_END` replaced, docstring updated; full suite 59 tests `OK`.
- Failure count k = 6 (subTests: five hash forms plus the backtick form), reproduced in a detached worktree at RED (since removed).
- Evidence line (ignored `build/playable-qualification/04-55-evidence.txt`): `T-04-62-TABLE-END red a3b7d2d44118 exit 1 failures 6 errors 0 green 045ed1c6ab93 ok`.
- No REFACTOR commit was needed.

## Other commits

- `ca6aea8` docs(04-55): CommonMark table-end contract in docs/testing.md (`ATX heading`, `#note`, `malformed row`, `(T-04-48, T-04-62; 04-55)`).
- `d26323e` docs(04-55): rights inventory rows refreshed for the two changed tests/tools files (sha256 and source_revision only).

## Verification

- `python3 tests/tools/check_security_register.py first-playable-game` exits 0 (04-SECURITY.md=50, 05-SECURITY.md=9 blocking open, unchanged).
- `--require-closed --phase 04` exits 1; Phase 04 stays open.
- Acceptance greps: test diff removes 0 lines; fix diff changes exactly the `TABLE_END` pattern line pair and no `def`; `table end ok` probe printed; no `04-55-red` worktree left.
- Docs probe printed `table-end contract ok`; `validate_repository_inventory()` printed `inventory ok`; `test_repository_inventory_matches` OK; rights diff adds 2 rows, 0 personal paths.

## Deviations from Plan

None - plan executed exactly as written.

## Boundaries kept

No register row, routing file, RECEIPT_BOUND path or `.planning/preparation` file was touched or staged; no RetroArch launch. Closure of T-04-48 and T-04-62 stays with `/gsd-secure-phase`; T-04-102 is recorded by 04-57.

## Known Stubs

None.

## Self-Check: PASSED
