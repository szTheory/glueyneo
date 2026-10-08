---
phase: 04-public-playable-tracer
reviewed: 2026-10-08
depth: standard
files_reviewed: 12
files_reviewed_list:
  - tools/verify_playable.py
  - tests/tools/test_verify_playable.py
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/check_phase04_validation_map.py
  - tests/tools/test_check_phase04_validation_map.py
  - docs/first-playable-build.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VERIFICATION.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-19-PLAN.md
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: findings
---

# Phase 04: Code Review Report

**Reviewed revision:** `9804351907e456b3ab85ebe4a49959c05b0714bb`
**Depth:** standard
**Files Reviewed:** 12
**Status:** one bounded warning, reproduced below

## Summary

Two independent, read-only passes reviewed the exact revision above. The security auditor and code reviewer ran the qualification suite (23/23), frontend smoke contract suite (27/27), evidence-map mutation suite (14/14), `python3 tools/verify_playable.py --check-docs`, and `python3 tests/tools/check_phase04_validation_map.py`; all passed. No GUI was launched. Those checks establish repository controls only.

## Critical Issues

None.

## Warnings

### WR-06: Consumer guide admits equivalent affirmative app claims alongside unknown status

**Severity:** warning
**Disposition:** open pending focused guide check and independent re-review
**Reproduction:** append `The actual frontend app loaded successfully and displayed pixels.` to a temporary copy of `docs/first-playable-build.md`; `check_docs()` accepts it. A second probe with `The frontend accepted RIGHT input and unloaded cleanly.` is also accepted.
**Impact:** a documentation gate can pass while the guide overstates unobserved actual RetroArch behavior.
**Scope:** `tools/verify_playable.py::check_docs()` and its guide-consumer regression.

Post-fix reviews at `2a82c455f85671ba144a42923318c4ff7d53b9a2` confirmed that the added known-phrase checks reject the originally reproduced examples, but the code reviewer still accepted `The frontend booted the game and showed its output.` and `The controls worked as expected in RetroArch.` The security auditor considered the bounded detector sufficient for its tested scope; the remaining direct code-review counterexamples mean WR-06 and T-04-34 stay open. Task 2 stopped at its three-attempt bound, leaving the broader natural-language claim gap explicit rather than claiming a complete semantic proof.

| Finding | Current disposition | Evidence |
|---|---|---|
| CR-03 | fixed | Both sanitizers remove the complete unstructured diagnostic suffix after a private-root match; newline-path regressions cover retained and printed qualification output and frontend/crash sinks. |
| WR-02 | fixed | Space-containing paths are removed as complete spans in both pipelines; relevant focused tests pass. |
| WR-03 | fixed | Repository-backed receipt validation derives exact archive rows and rejects forged file rows even after aggregate recomputation. |
| WR-05 | fixed | Exact controlled crosswalk/ledger-state equality, duplicate and contradiction mutations pass. |
| WR-01 | fixed | The checker accepts a repaired finding absent from current review while preserving its historical fixed disposition; mutation coverage passes. |
| WR-07 | fixed with test-scope note | The current checker pins source-derived frontend rows; the fixture first requires source uncertainty, then its mutation removes the source evidence. This differs from earlier behavior that appended a replacement row. |
| WR-06 | open; broader claim gap remains after bounded repairs | The independent reviewer found affirmative claims still accepted after the documented correction attempts; the Pending/unknown evidence remains authoritative and T-04-34 stays medium/open. |

The security reviewer initially considered WR-06's mitigation supported from the exact-row checker and validation-map mutations. The code reviewer's direct consumer-guide counterexample is stronger for this specific claim: the docs gate checks required guide terms but did not reject an affirmative claim in that guide. Therefore T-04-34 remains medium/open pending the focused fix and independent re-review. This report does not close the four directed high/open disclosure threats. HOST-02 and frontend QUAL-03 remain Pending/unknown; no actual frontend behavior is inferred from the GUI-free tests.

### Commands and denominators

- `python3 tests/tools/test_verify_playable.py -v` — 23/23 passed.
- `python3 tests/libretro/test_retroarch_smoke.py -v` — 27/27 passed.
- `python3 tests/tools/test_check_phase04_validation_map.py -v` — 14/14 passed.
- `python3 tests/tools/check_phase04_validation_map.py` — passed; reruns the current crosswalk/focused controls.
- `python3 tools/verify_playable.py --check-docs` — passed on the unmodified guide; the appended-claim temporary mutation was accepted, reproducing WR-06.

---

_Reviewed: 2026-10-08 at revision `9804351907e456b3ab85ebe4a49959c05b0714bb`_
_Reviewers: independent gsd-security-auditor and gsd-code-reviewer_
_Depth: standard_
