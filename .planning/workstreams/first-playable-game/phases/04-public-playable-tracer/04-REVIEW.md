---
phase: 04-public-playable-tracer
reviewed: 2026-10-08T11:57:29Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - tools/verify_playable.py
  - tests/tools/test_verify_playable.py
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/check_phase04_validation_map.py
  - tools/owned_cpu/inventory.py
  - tests/owned_cpu/test_inventory.py
  - experiments/owned_cpu/cpu.h
  - experiments/owned_cpu/state-inventory.json
  - experiments/owned_cpu/source-manifest.json
  - experiments/owned_cpu/SUBSET.md
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-10-08T11:57:29Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed Plan 04-12 changes since `7e0d68930b25c91f5da28845a8a21e260cc38ec0` at source revision `d98c61574cd6d0c527aa74a39489fcf0a8b1e672`. The supplied summary and validation document were read as provenance and excluded from the source-file count. Quoted private paths still leak suffixes, and the validation-map checker freezes historical findings and dispositions instead of accepting reconciled review outcomes.

Fresh execution passed 19 qualification tests, 25 GUI-free frontend tests, and 11 owned-inventory controls. `python3 tools/owned_cpu/inventory.py check --build-dir build/owned-debug` passed against the existing build. The validation-map checker passed against the pre-review artifacts, but an in-memory control removing the repaired CR-01 finding was rejected with `current review IDs changed`. The disclosure below was reproduced in both sanitizers, a persisted qualification receipt, and its printed result. No GUI smoke, full clean qualification, or independent security audit was run. Security dispositions are unchanged; HOST-02 and actual frontend QUAL-03 remain unknown.

The former CR-01 boolean-count bypass is no longer reported: exact integer checks reject the reproduced malformed receipts. CR-02 retains the private-path disclosure scope with the remaining quoted-boundary counterexample. WR-01 retains the validation-map checking scope with its remaining hardcoded review-state failure. Carried WR-02/WR-03 decisions remain owned by `04-REVIEW-DISPOSITION.md`; this review does not rewrite them.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-02: Quoted private paths still expose filename suffixes [BLOCKER]

**File:** `tools/verify_playable.py:484-492`; `tests/libretro/retroarch_smoke.py:68-73`

**Issue:** Both quoted-path branches use `body.find` to treat the next matching quote as a proven closing boundary. Quotes are legal POSIX filename bytes, and formats such as JSON escape them. A diagnostic produced by `"failed status 7: " + json.dumps('/Users/synthetic/private"tail/sensitive.bin')` becomes `failed status 7: [user]tail/sensitive.bin"` in both sanitizers: the escaped quote inside the filename terminates redaction and leaves the private suffix. A second sanitizer pass cannot recover the lost root. `_write_receipt` persists this suffix in `receipt.json` and prints it in the machine-readable result; this was reproduced with synthetic inputs. A raw single-quoted filename containing an apostrophe has the same ambiguity. The new punctuation/space tests omit embedded and escaped quotes. This remains within T-04-11/T-04-15/T-04-18's existing disclosure scope, without changing any security disposition.

**Fix:** Recognize a quoted boundary only under an explicit diagnostic grammar with correct escape handling. For arbitrary subprocess text, redact the remainder of the line when the boundary cannot be established, including apparently quoted spans. Add JSON-escaped double-quote and embedded-apostrophe filename regressions through both sanitizers, `build_diagnostic`, persisted/printed receipts, and repeated sanitization. When structured JSON status must survive, parse it and sanitize its path-bearing string values before serialization.

## Warnings

### WR-01: Validation-map checks require historical findings to stay reported and open [WARNING]

**File:** `tests/tools/check_phase04_validation_map.py:109-117`; `tests/tools/check_phase04_validation_map.py:141-156`

**Issue:** The checker reads the current review but requires its IDs to equal exactly `{CR-01, CR-02, WR-01}`, appends historical WR-02/WR-03, and requires every corresponding disposition to remain `open`. An independent re-review that stops reporting the repaired boolean bypass fails at line 110 even if the focused suites and document crosswalks agree. This was reproduced without editing source or evidence files by changing only the CR-01 heading in the in-memory review read while retaining the observed suite counts. Independently recording a finding as `fixed` also necessarily fails lines 149-155. Updating the six-threat assumption repaired the immediate old-audit mismatch but left the same stale-state failure at the review boundary; this report itself removes repaired CR-01 and triggers it.

**Fix:** Derive retained IDs and actual dispositions from the current disposition record, compare its YAML/table representations, and derive unresolved findings from `disposition: open` instead of a fixed ID union. Require current narrative findings to have matching records and the validation crosswalk to reflect each record's actual disposition, preserving carried historical rows. Keep security audit assertions separate from review disposition handling. Add controls for a repaired finding absent from the current review, a retained finding marked fixed, and a newly discovered finding; valid reconciliation should pass and contradictory records should fail.

---

_Reviewed: 2026-10-08T11:57:29Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
