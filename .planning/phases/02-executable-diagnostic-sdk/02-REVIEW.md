---
phase: 02-executable-diagnostic-sdk
reviewed: 2026-10-06T10:18:07Z
depth: standard
files_reviewed: 30
files_reviewed_list:
  - CMakeLists.txt
  - CMakePresets.json
  - README.md
  - cmake/GlueyneoConfig.cmake.in
  - docs/evidence-schema.md
  - docs/ownership-and-errors.md
  - docs/testing.md
  - evidence/sdk/verification.json
  - examples/diagnostic.c
  - fixtures/diagnostic/manifest.json
  - include/glueyneo/glueyneo.h
  - src/instance.c
  - src/sdk_private.h
  - tests/consumers/CMakeLists.txt
  - tests/consumers/check_package.py
  - tests/consumers/header.cpp
  - tests/fuzz/minimize.py
  - tests/fuzz/regressions.json
  - tests/fuzz/sdk_mutation.c
  - tests/sdk/ORACLE.md
  - tests/sdk/controls.py
  - tests/sdk/guest_fixture.c
  - tests/sdk/guest_fixture.h
  - tests/sdk/test_evidence.py
  - tests/sdk/test_sdk.c
  - tests/sdk/test_support.h
  - tools/diagnostic/main.c
  - tools/sdk_baseline.py
  - tools/sdk_evidence.py
  - tools/verify_sdk.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-10-06T10:18:07Z  
**Depth:** standard  
**Files Reviewed:** 30  
**Status:** issues_found

## Summary

Reviewed the 30 scoped implementation, test, evidence, packaging, and documentation files. The C runtime's fixed-map validation and replacement-load ownership paths are internally consistent on inspection. Two robustness defects remain in malformed evidence handling and packaging of sanitizer-instrumented static libraries.

## Warnings

### WR-01: Malformed manifest rows can escape the evidence error path

**File:** `tools/sdk_evidence.py:551`
**Issue:** The validator calls `r.get(...)` on every `source_inputs` element before confirming each element is a dictionary. Similar assumptions occur while validating identity rows (for example, line 268). A malformed but valid JSON document such as `"source_inputs":[null]` therefore raises `AttributeError` instead of the promised stable `EvidenceError`. The verification CLI catches the latter but not `AttributeError`, so malformed evidence can terminate with a traceback instead of a controlled fail-closed result.
**Fix:** Validate container element types before sorting or accessing fields; reject invalid rows through `require`, e.g. `require(all(isinstance(row, dict) for row in sources), "manifest-identity", "source rows must be objects")`, and apply the same guard to Unity, identity, fixture, and failure-history row collections.

### WR-02: Static runtime becomes unusable when installed from a sanitizer build

**File:** `CMakeLists.txt:58-64`
**Issue:** `glueyneo_apply_sdk_sanitizer` instruments `glueyneo` when the sanitizer option is enabled, but deliberately omits sanitizer link options for static-library targets. The installed static archive then contains ASan/UBSan or TSan references while its exported target does not propagate the required link flags/runtime dependency. A downstream consumer linking the installed archive from such a build can fail with unresolved sanitizer symbols.
**Fix:** Keep sanitizer instrumentation confined to private test targets, or propagate the matching sanitizer link options/runtime requirements through the exported static target when instrumentation is intentionally applied to the public archive. Add an installed static-consumer check for each supported sanitizer mode.

---

_Reviewed: 2026-10-06T10:18:07Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
