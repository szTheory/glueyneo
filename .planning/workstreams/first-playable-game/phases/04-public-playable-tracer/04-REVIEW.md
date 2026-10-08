---
phase: 04-public-playable-tracer
reviewed: 2026-10-08T13:11:51Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - tools/verify_playable.py
  - tests/tools/test_verify_playable.py
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/check_phase04_validation_map.py
  - tests/tools/test_check_phase04_validation_map.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-10-08T13:11:51Z  
**Depth:** standard  
**Files Reviewed:** 6  
**Status:** issues_found

## Summary

Reviewed the six Plan 04-13 source and test files, with the phase security register, review disposition, validation map and prior review as context. The reported raw-literal-quote sanitizer bypass reproduces independently in both diagnostic paths: `failed status 7: "/Users/synthetic/private"tail/sensitive.bin"` is reduced to `failed status 7: [user]tail/sensitive.bin"`. The leak reaches qualification receipts and printed results through `redact` and frontend diagnostics through `sanitize_diagnostic_text`. The validation-map parser also rejects a valid informational finding because it only recognizes `CR-` and `WR-` IDs and has no Info section mapping.

These findings retain the phase's existing open disclosure scope. Repository privacy regressions do not establish HOST-02 or actual pinned RetroArch QUAL-03 behavior; both remain unobserved, and the four high disclosure threats remain open.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-02: Literal quotes inside private paths still expose suffixes [BLOCKER]

**File:** `tools/verify_playable.py:484-493`; `tests/libretro/retroarch_smoke.py:68-76`

**Issue:** Both sanitizers treat the first quote returned by `_json_string_end` as a proven close to the quoted path. That helper validates JSON string escaping, but these diagnostics are arbitrary text and may contain an unescaped literal quote in a filename. For example, the input `failed status 7: "/Users/synthetic/private"tail/sensitive.bin"` is sanitized to `failed status 7: [user]tail/sensitive.bin"` by both functions. The suffix is therefore still present after a second pass and is carried into `_write_receipt`'s persisted JSON and printed result or the frontend's diagnostic/crash-reason record. This independently confirms the raw-literal-quote bypass recorded in the security audit and keeps T-04-11, T-04-15, T-04-18 and T-04-20 open.

**Fix:** For arbitrary diagnostic text, do not infer a closing boundary from a quote after a private root. Redact from the root through the end of that line unless the caller supplies a structured, parsed diagnostic format with an unambiguous path field. Add raw unescaped quote regressions alongside the escaped-quote cases and pass them through both sinks, repeat sanitation, persisted/printed receipt output, and frontend crash-reason output.

## Warnings

### WR-04: Validation-map parser rejects valid Info findings [WARNING]

**File:** `tests/tools/check_phase04_validation_map.py:58-75`

**Issue:** `parse_review_findings` recognizes only headings matching `CR-` or `WR-` at line 64 and maps only `critical issues` and `warnings` at lines 69-74. The review schema permits Info findings (`IN-` IDs under `## Info`). Adding a valid informational finding to the current review makes the validation-map gate fail with “outside a severity section,” even when the disposition and crosswalk consistently record it. This couples a valid review outcome to an incomplete parser grammar.

**Fix:** Accept `IN-` finding IDs and map the `info` section to `info` severity. Extend disposition and crosswalk reconciliation to preserve and compare that severity, and add a fixture containing a matching informational finding that passes while inconsistent severity still fails.

---

_Reviewed: 2026-10-08T13:11:51Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
