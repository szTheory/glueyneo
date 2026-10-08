---
phase: 04-public-playable-tracer
reviewed: 2026-10-08T01:03:55Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - docs/first-playable-build.md
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/test_verify_playable.py
  - tools/verify_playable.py
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-10-08T01:03:55Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

The qualification runner and snapshot tests were reviewed alongside the frontend smoke and its documentation. The targeted Python test suites pass (27 tests), but the direct smoke accepts any structurally plausible 602-byte GNFX file, diagnostic path sanitization leaves suffixes of paths containing spaces, and repository-backed receipt validation does not bind file hashes to the committed archive contents.

## Warnings

### WR-01: Frontend smoke does not enforce the pinned fixture identity

**File:** `tests/libretro/retroarch_smoke.py:543-549`
**Issue:** `validate_inputs` checks only the content length, `GNFX` magic, and version. It records the observed digest but does not compare it with the public fixture digest (`59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0`). As a result, the documented direct smoke command can report a pass for a different 602-byte GNFX payload that happens to exhibit the expected marker behavior. The qualification runner separately checks its generated fixture, but the direct smoke entry point does not uphold the same fixture identity contract.
**Fix:** Define the expected fixture digest in this module and reject content whose SHA-256 differs before launching RetroArch.

### WR-02: Diagnostic path sanitization leaks path suffixes when paths contain spaces

**File:** `tests/libretro/retroarch_smoke.py:52-60`
**Issue:** The path expressions stop at whitespace. For example, `/Users/alice/private capture/secret.rom` is sanitized to `[user] capture/secret.rom`; paths under `/Volumes` and temporary directories leak the same way. These diagnostics are emitted and retained as qualification evidence, so a private capture or save-state filename can remain visible despite the documented sanitization. Existing tests cover path components without spaces and miss this case.
**Fix:** Redact the complete path, including space-containing components, using quoted-path boundaries where available and a conservative rule for unquoted absolute paths; add tests for user, volume, and temporary paths containing spaces.

### WR-03: Repository-backed receipt validation accepts forged file-content hashes

**File:** `tools/verify_playable.py:417-429`
**Issue:** With `repository` supplied, the validator checks that inventory paths and entry types match the commit and that the archive digest matches, but it never compares each file row's byte count and SHA-256 to the corresponding archived file. I confirmed that changing one file row's SHA-256, recomputing `inventory_sha256`, and validating against the real repository is accepted. A receipt can therefore claim content identities different from the pinned source while passing this source check.
**Fix:** Materialize or stream the commit archive during repository validation and compare every file's size, digest, and mode plus each symlink target against the receipt entries before accepting it.

---

_Reviewed: 2026-10-08T01:03:55Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
