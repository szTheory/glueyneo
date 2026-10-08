---
phase: 04-public-playable-tracer
reviewed: 2026-10-08T23:12:03Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - tools/verify_playable.py
  - tests/tools/test_verify_playable.py
  - tests/tools/check_phase04_validation_map.py
  - tests/tools/test_check_phase04_validation_map.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-10-08T23:12:03Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** two warnings remain open

## Summary

The current qualification/privacy suite passes 25/25 and the validation-map mutation suite passes 14/14. Neither result establishes actual pinned RetroArch behavior, which remains manual-only and unknown. I reproduced two accepted affirmative claims in temporary copies of the consumer guide, and the evidence checker still preserves a stale 23/23 qualification result in the current verification report without comparing it to the observed 25-test run.

## Warnings

### WR-01: Guide claim filter accepts affirmative frontend paraphrases

**Severity:** warning
**File:** `tools/verify_playable.py:632-650`
**Issue:** `check_docs()` uses a finite set of phrase patterns to reject frontend success claims. In a temporary copy of the current guide, both `The frontend booted the game and showed its output.` and `The controls worked as expected in RetroArch.` were accepted by `check_docs()`. The explicit Pending/unknown record therefore does not prevent all contradictory prose from passing this gate. This is the known bounded WR-06 paraphrase gap; it does not imply that actual frontend behavior was observed.
**Fix:** Keep WR-06/T-04-34 open until the gate checks a structured, authoritative evidence/status field or the documented claim surface is constrained so arbitrary prose cannot assert success. Add these exact counterexamples as regressions before changing the open disposition.

### WR-02: Evidence checker accepts a stale current qualification denominator

**Severity:** warning
**File:** `tests/tools/check_phase04_validation_map.py:176-180, 430`
**Issue:** The current verification spot-check is pinned to `23/23 passed`, but the current qualification suite reports 25 tests. `require_current_frontend_row()` checks the spot-check row against that stale constant; `main()` does not compare its denominator with the live result returned by `run_suite()`. As a result, the direct evidence-map checker can pass while the current verification report states the wrong test denominator. Historical rows may retain their historical counts, but this current spot-check is not reconciled.
**Fix:** Compare the current verification spot-check denominator with the observed qualification suite count, or generate that row from the same observed result. Add a mutation test that changes only the spot-check denominator and requires the checker to reject it.

---

_Reviewed: 2026-10-08T23:12:03Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
