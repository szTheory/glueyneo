---
phase: 04-public-playable-tracer
reviewed: 2026-10-08T03:40:06Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - tools/verify_playable.py
  - tests/tools/test_verify_playable.py
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/check_phase04_validation_map.py
findings:
  critical: 2
  warning: 1
  info: 0
  total: 3
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-10-08T03:40:06Z  
**Depth:** standard  
**Files Reviewed:** 5  
**Status:** issues_found

## Summary

Reviewed the qualification receipt validator, diagnostic redaction paths, the frontend smoke and focused regression tests, and the Phase 04 validation-map checker. Fixture digest enforcement and archive-derived content rows address the earlier findings, but a JSON boolean can still pass as an integer byte count in repository-backed receipts, and unquoted path redaction can expose suffixes. The validation-map checker also rejects the current security audit state because it still requires six threats, including T-04-13, T-04-16, and T-04-17, to remain open. No tests were run for this read-only review.

## Critical Issues

### CR-01: Boolean byte counts bypass repository receipt equality [BLOCKER]

**File:** `tools/verify_playable.py:417`
**Issue:** Python treats `bool` as a subclass of `int`, and `True == 1`. A forged receipt can replace a one-byte committed file's `bytes: 1` with `bytes: true`, recompute `inventory_sha256`, and pass the structural check at this line. The final archive-derived row comparison at lines 455–457 also accepts the mismatch because Python dictionary equality considers those values equal. This allows a malformed, modified inventory row to validate against the repository despite the archive-binding check.
**Fix:** Require exact integer types for all numeric receipt fields, for example `type(byte_count) is int`, and apply the same exact-type check to `entry_count`, `file_count`, and `symlink_count` before comparing them.

### CR-02: Unquoted private paths can leak suffixes at valid path delimiters [BLOCKER]

**File:** `tools/verify_playable.py:490`; `tests/libretro/retroarch_smoke.py:75`
**Issue:** Both redactors treat punctuation and diagnostic phrases such as `,`, `:`, and ` in ` as the end of an unquoted path. Those characters and phrases can occur in valid POSIX path components. For example, an unquoted diagnostic containing `/Users/alice/private,capture/secret.rom` is reduced to `[home],capture/secret.rom`, leaving the private suffix in retained output. The frontend sanitizer also replaces a supplied temporary root with `[temporary]` at line 56 while preserving all descendant path components. This conflicts with the security contract to remove complete private paths and matches the remaining path-suffix disclosure risk.
**Fix:** Redact the entire unquoted absolute path when its boundary is ambiguous, or parse known diagnostic formats with explicit path quoting/boundaries. When replacing `temporary_root`, remove the complete root-plus-suffix path span as well. Add regressions with commas, colons, delimiter phrases, and descendants of a temporary root.

## Warnings

### WR-01: Validation-map checker requires superseded security findings to remain open [WARNING]

**File:** `tests/tools/check_phase04_validation_map.py:108-123`
**Issue:** The checker requires WR-01/WR-02/WR-03 all to remain open and requires `threats_open: 6`, including T-04-13, T-04-16, and T-04-17 as open. The current security audit records those three threats as closed and `threats_open: 3`, with T-04-11, T-04-15, and T-04-18 still open. Therefore the checker fails against the current audited state even when the focused test counts match. Its disposition checks at lines 132–145 also assume the old three-open-finding crosswalk.
**Fix:** Make the checker validate the current audit/disposition state: assert the three closed threats are closed, the three path-redaction threats remain open, and compare the review crosswalk to current dispositions instead of requiring every historical finding to stay open.

---

_Reviewed: 2026-10-08T03:40:06Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
