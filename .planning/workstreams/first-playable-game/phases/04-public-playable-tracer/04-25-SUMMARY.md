---
phase: 04-public-playable-tracer
plan: 25
subsystem: testing
tags: [security-register, closure-gate, mutation-tests, qualification-tools]
requires:
  - phase: 04-public-playable-tracer
    provides: plan 04-24 qualification tooling baseline
provides:
  - frontmatter-only exact-one threats_open parsing, all-table row collection, unescaped-pipe cells
  - verified-while-open rejection, FAIL lines for bad config and workstream name
  - --require-closed closure mode and per-register blocking counts on the PASS line
affects: [04-VERIFICATION gap 4, QUAL-03, T-04-48, T-04-51]
status: complete
commits: 5
plan_head_before: be8e0d8e05da0a74a1d92306c0c5b977bc87f36b
plan_head_after: 6fad089f1b7d0bf5b68b121568dd7904e7419ae7
actuals:
  tokens: 9000
  tasks: 2
  commits: 5
tech-stack:
  added: []
  patterns: ["consistency mode vs explicit closure mode"]
key-files:
  created: []
  modified:
    - tests/tools/check_security_register.py
    - tests/tools/test_check_security_register.py
    - docs/testing.md
    - docs/rights-inventory.md
key-decisions:
  - "Default mode stays a consistency check; closure is the separate --require-closed mode, and the PASS line lists per-register blocking counts so a PASS cannot be read as closure."
  - "Any frontmatter line matching ^\\s*#?\\s*threats_open\\s*: counts as a key candidate, so commented and indented copies fail while the 'threats_open =' template comment does not."
requirements-completed: [QUAL-03]
---

# Phase 04 Plan 25: Security register gate hardening Summary

Strict security register gate: frontmatter-only exact-one `threats_open`, rows counted from every Threat ID table, unescaped-pipe cell split, verified-while-open rejection, `FAIL:` lines instead of tracebacks, and an explicit `--require-closed` mode.

## Tasks

| Task | Commit | Notes |
| ---- | ------ | ----- |
| 1 RED | fdf46ba | `test(04-25): add failing multi-table register mutations` |
| 1 GREEN | 0dfa733 | `fix(04-25): count rows from every security register table (CR-06)` |
| 2 RED | 4bc8c4b | `test(04-25): add failing frontmatter, cell and closure-mode mutations` |
| 2 GREEN | 6e0d3ca | `fix(04-25): strict frontmatter, cells and closure mode for the register gate (CR-06)` (includes docs/testing.md section) |
| 2 rights | 6fad089 | `docs(04-25): refresh rights inventory for changed test sources` |

FIRST_TEST_SHA=fdf46ba, LAST_FIX_SHA=6e0d3ca. `git diff --name-only fdf46ba^..6e0d3ca` lists no `*-SECURITY.md` file.

## Red runs (observed before the parser change)

Task 1 (`python3 tests/tools/test_check_security_register.py`): `Ran 3 tests ... FAILED (failures=2)`:
- `case='second table hides open high row'`: `AssertionError: 0 != 1`
- `case='second table counted when declared'`: `AssertionError: 1 != 0`

Task 2: `Ran 6 tests ... FAILED (failures=6, errors=3)`. Failing subtests: mutations `unknown block_on`, `missing config`, `unreadable config` (ERROR, traceback), `commented key`, `indented duplicate`, `body-only key`, `verified while open`; control `escaped pipe cell`; and `test_require_closed_mode`. The `duplicate key`, `bad workstream name`, duplicate-ID-across-tables and `flag before workstream` cases already returned 1 before the change, but only by accident (count mismatch or no registers found); they now fail for the intended reason.

## Green and real-register results

- Mutation suite: `Ran 6 tests ... OK`.
- Default mode: `PASS: 2 security registers reconcile with block_on; blocking open: 04-SECURITY.md=6, 05-SECURITY.md=9`.
- `--require-closed` (exit 1): `FAIL: 04-SECURITY.md: 6 blocking open threats` and `FAIL: 05-SECURITY.md: 9 blocking open threats`.
- `ctest --preset owned-debug -R planning_security_register`: 2/2 passed.
- Rights verify: `validate_repository_inventory()` passed (42 items); `rights rows bound 2`.
- `grep -c "## Planning security register gate" docs/testing.md` is 1; `--require-closed` appears 2 times.

## Deviations from Plan

None - plan executed exactly as written. Note for the 04-31 reconciliation: the real 05-SECURITY.md (status draft) has 9 blocking open rows, so `--require-closed` reports it as well as 04; no register was edited.

## Known Stubs

None.

## Threat Flags

None. T-04-51 (workstream glob) is mitigated by the name regex check before globbing; T-04-48 gains mitigation evidence.

## Self-Check: PASSED

Modified files exist; commits fdf46ba, 0dfa733, 4bc8c4b, 6e0d3ca, 6fad089 are ancestors of HEAD.
