---
phase: 04-public-playable-tracer
plan: 43
subsystem: testing
tags: [security-register, frontmatter, gfm-tables, fail-closed, T-04-48, T-04-62, G3IN-03]
requires:
  - phase: 04-public-playable-tracer
    provides: "04-42 round-3 gap closure and the security register checker"
provides:
  - "frontmatter_keys: normalized top-level key reader with duplicate and unsupported-line errors"
  - "register_tables: GFM Threat ID table scanner with a fail-closed sweep"
  - "misnamed security register detection in the unscoped run"
affects: [04-49, headless security audit]
tech-stack:
  added: []
  patterns: ["fail closed on any frontmatter or table form the reader cannot classify"]
key-files:
  created: []
  modified:
    - tests/tools/check_security_register.py
    - tests/tools/test_check_security_register.py
    - docs/testing.md
key-decisions:
  - "Frontmatter line numbers in errors are file line numbers (frontmatter starts at line 2)."
  - "A register-shaped file with a non-register name is detected by a threats_open key, a parsed Threat ID table or an unrecognized Threat ID header line."
status: complete
commits: 5
plan_head_before: 9b502dd681df611019049e139a8337dd1aa0d0ac
plan_head_after: 223bea0f0aec60f185f626fc5c46237ce6cad1b0
actuals:
  tokens: 30000
  tasks: 3
  commits: 5
---

# Phase 04 Plan 43: Register checker fail-closed hardening Summary

**The security-register checker now reads frontmatter as normalized keys, counts every GFM-rendered Threat ID table, and fails closed on misnamed registers and unreadable forms.**

## Commits

| ID | Red (test) | Fix |
|----|------------|-----|
| T-04-48 | 34b4f87 `test(04-43): reproduce T-04-48 quoted and duplicate frontmatter keys` | e3a557d `fix(04-43): read register frontmatter as normalized keys and fail on duplicates (T-04-48)` |
| T-04-62, G3IN-03 | 01ebd52 `test(04-43): reproduce T-04-62 GFM table forms and G3IN-03 misnamed registers` | 2587c6e `fix(04-43): count every GFM threat table form and fail closed on misnamed registers (T-04-62, G3IN-03)` |
| docs | n/a | 223bea0 `docs(04-43): document register frontmatter, GFM table and misnamed-file rules` |

Red runs (captured under the ignored `build/playable-qualification/`): `04-43-red-t_04_48.txt` ended `FAILED (failures=24)` and `04-43-red-t_04_62.txt` ended `FAILED (failures=17)`; neither has an `errors=` count, so both are assertion failures.

## Tests

- `FrontmatterKeyTest.test_t_04_48_*` (8): quoted/re-cased duplicates, quoted key alone, status duplicates and quoted status, any duplicate key, unsupported lines with line number, commented/indented keys, bare-integer rule, accepted forms.
- `GfmTableFormTest.test_t_04_62_*` (7): no edge pipes, indent 1-3, mixed pipes, delimiter alignment, unparsed header forms (4 spaces, tab, blockquote, no delimiter, wrong cell count), malformed row, prose not a table.
- `PhaseScopeTest.test_g3in_03_*` (3): misnamed register-shaped files fail, non-register documents are `SKIP:`ped, `verified` with trailing comment.
- Full module: 56 tests, `OK`.

## Intentional baseline change

`test_g2wr_04_non_register_names_are_not_counted`: its register-shaped `04-draft-SECURITY.md` previously passed silently (exit 0, file ignored). That silent skip was the G3IN-03 defect, because it hid open rows. The test now expects exit 1 with `misnamed security register 04-draft-SECURITY.md`. The `--phase 04.1` half is unchanged and runs without the misnamed file. The "not counted" property is kept by `test_g3in_03_non_register_documents_are_skipped_and_reported`.

## Real-register gate outputs

- `python3 tests/tools/check_security_register.py first-playable-game` -> exit 0, `PASS: 2 security registers reconcile ...; blocking open: 04-SECURITY.md=3, 05-SECURITY.md=9; block_on high from .planning/config.json`
- `... --require-closed --phase 04` -> exit 1, `FAIL: 04-SECURITY.md: 3 blocking open threats`
- The docs probe printed `register contracts ok`.
- The cpu-bus-diagnostic-sdk-alpha workstream still fails for its pre-existing `01-SECURITY.md` count mismatch (unchanged, not an acceptance check); its `01-29-ADMISSION-SECURITY.md` is reported as `SKIP:`.

## Deviations from Plan

**1. [Rule 1 - Bug] Fixture delimiter row had the wrong cell count**
- **Found during:** Task 2 (GREEN)
- **Issue:** `test_table_with_only_one_of_severity_or_status_errors` case `neither` used a 3-cell header with a 5-cell delimiter row. Under the GFM rule (delimiter cell count must equal header cell count) that is not a table, so the error became `unrecognized threat table form` instead of `lacks Severity or Status`.
- **Fix:** The fixture's delimiter now has 3 cells, with a comment citing T-04-62. The assertion is unchanged, so it was not loosened.
- **Files modified:** tests/tools/test_check_security_register.py
- **Commit:** 2587c6e

**Total deviations:** 1 auto-fixed (1 Rule 1). **Impact:** none on scope; the intended assertion still runs.

## Boundaries kept

No SECURITY.md row, `threats_open` or `status` changed (T-04-48 rule). No CTest ran in `owned-debug`. No receipt-bound path was edited. No packages were installed. The two unrelated preparation files were left unstaged.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- Files exist: tests/tools/check_security_register.py, tests/tools/test_check_security_register.py, docs/testing.md.
- Commits 34b4f87, e3a557d, 01ebd52, 2587c6e and 223bea0 are ancestors of HEAD; `git rev-list --count` from the plan base measured 5.
- Acceptance greps: `def frontmatter_keys` 1, `^KEY_LIKE = ` 0, `def test_t_04_48_` 8, `def register_tables` 1, non-comment `^HEADER = ` 0.
