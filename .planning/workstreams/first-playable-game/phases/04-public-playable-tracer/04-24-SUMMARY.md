---
phase: 04-public-playable-tracer
plan: 24
subsystem: testing
tags: [private-paths, redaction, canonicalization, receipt, qualification-tools]
requires:
  - phase: 04-public-playable-tracer
    provides: plan 04-23 qualification tooling baseline
provides:
  - one canonical private-path matcher with origin index map (canonicalize, redact, scan_public)
  - scan_public_value over decoded keys and values plus the JSON form
  - fail receipt on early --clean failure; redacted CLI error output; smoke catch-all
affects: [04-VERIFICATION gap 1, QUAL-03, HOST-02]
status: complete
commits: 7
plan_head_before: 3da6f8ab8cde982850497448c83d26184ffea53c
plan_head_after: 79cc4699a9610d30cfd8e1d44b61b34e651926b7
actuals:
  tokens: 9700
  tasks: 3
  commits: 7
tech-stack:
  added: []
  patterns: ["canonical form + origin index map for redaction", "generic roots anchored to path starts"]
key-files:
  created: []
  modified:
    - tools/private_paths.py
    - tests/tools/test_private_paths.py
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - tests/libretro/retroarch_smoke.py
    - docs/rights-inventory.md
key-decisions:
  - "Specific roots match anywhere in the canonical text; generic roots only at path starts (benign build/tmp-like and docs/tmp/notes pass)."
  - "Receipt dict keys are not rewritten by redaction: a key holding a private root fails the receipt closed, which keeps the existing receipt-writer test expectation."
  - "Username-token check keeps its original tokenization (dash and dot stay inside a token) so a CI user such as 'runner' does not reject 'runner-source-mismatch'."
requirements-completed: [QUAL-03, HOST-02]
---

# Phase 04 Plan 24: Private-path canonicalization Summary

Private-path redaction and scanning now use one canonical form (escape decode, bounded percent fixpoint, NFKC+casefold, separator-run collapse) with an origin index map, and every public sink scans decoded keys and values.

## Tasks and commits

| Task | Commit | Notes |
| ---- | ------ | ----- |
| 1 red | 9a032ed | test: CanonicalRootTest |
| 1 | 0d756e2 | fix: canonicalize (CR-01) |
| 2 red | 557ad16 | test: BypassMatrixTest and sink cases |
| 2 | a975d39 | fix: scan_public_value at every sink (CR-02) |
| 3 red | 8350b70 | test: MainErrorPathTest, smoke catch-all |
| 3 | 289c67c | fix: lanes guard, emit_error, smoke catch-all (CR-08, CR-09) |
| 3 rights | 79cc469 | docs: rights inventory rows for the three changed test candidates |

First 04-24 commit: 9a032ed.

## Red runs (before each fix)

- Task 1, Tests A-C (`python3 tests/tools/test_private_paths.py`): `Ran 11 tests ... FAILED (failures=4)` (division-slash redact, json-escaped scan, receipt sink key and value).
- Task 2: `Ran 19 tests ... FAILED (errors=4)` for `scan_public_value` (missing function). The BypassMatrixTest cases already passed on the Task 1 canonical module, so their red evidence is an oracle run of the same class against the pre-fix `private_paths.py` (9a032ed): `FAILED (failures=38)` across 4 tests, including `docs/tmp/notes` being wrongly cut.
- Task 3: `test_verify_playable.py` `FAILED (failures=1, errors=4)` (AttributeError on `runner.lanes`, raw OSError/UnicodeDecodeError, raw path in stderr); smoke catch-all `struct.error` escaped `main()` (error in test_private_paths.py).

Final: test_private_paths 20 OK, test_verify_playable 32 OK, test_retroarch_smoke 35 OK, `--check-docs` passes, `ctest --preset owned-debug -L qualification-tools` 5/5 pass.

## Rights inventory

Rows for tests/tools/test_private_paths.py and tests/tools/test_verify_playable.py cite 8350b70 (full SHA in the inventory) and tests/libretro/retroarch_smoke.py cites 289c67c; the verify script printed `passed: True` and `rights rows bound 3`. The fix commits before 79cc469 fail the CI rights gate by design; the final commit passes.

## Deviations from Plan

**1. [Rule 1 - Existing test preserved] Receipt keys not rewritten.** Plan step 1.6 said to redact dict keys in `sanitize`. Doing so made the existing `test_receipt_writer_fails_closed_on_a_surviving_path` (key holding the home path must yield a fail receipt) pass as `pass`, which would relax an existing expectation (prohibited). Keys are therefore left as is so the decoded-key scan fails the receipt closed; documented in a code comment. Test C accepts either outcome.

**2. emit_error signature** accepts `BaseException | str` so the fixed type-name fallback goes through the same redact+scan path.

**3. Cut position.** `redact` also drops the separator run directly before a specific-root match (leaves `err`, not `err U+2215`).

No auth gates. Known stubs: none. Threat flags: none.

## Self-Check: PASSED

Files exist (tools/private_paths.py, tools/verify_playable.py, tests, docs/rights-inventory.md); commits 9a032ed, 0d756e2, 557ad16, a975d39, 8350b70, 289c67c, 79cc469 are ancestors of HEAD.
