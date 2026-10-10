---
phase: 04-public-playable-tracer
plan: 38
subsystem: testing
tags: [receipt, redaction, review-provenance, tdd]
requires:
  - phase: 04-public-playable-tracer
    provides: 04-36 gap-closure round 2 tooling and R2 review findings
provides:
  - Post-build receipt section contained behind a fixed `receipt-error: <Type>` token with a minimal fail receipt (T-04-11, G2CR-02)
  - Build failure reasons pass through `_public_reason` (G2IN-03)
  - Parsed 40-hex `reviewed_revision` and reviewed-revision..head ordering window for dispositions (T-04-38 narrowed, T-04-67, WR-11, G2WR-01, G2WR-02)
affects: [04-39, 04-40, 04-41, 04-42]
status: complete
commits: 4
plan_head_before: 38dcce6ab2dfcd88d95c9e9ea13ac10027fd8f3c
plan_head_after: 8c20410b0f1c4d0612e7fa5c64d75115d47c2224
actuals:
  tokens: 9000
  tasks: 2
  commits: 4
tech-stack:
  added: []
  patterns: ["one outer catch-all with type-name-only token and minimal fallback write", "revision window ordering check via merge-base --is-ancestor"]
key-files:
  created: []
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW.md
key-decisions:
  - "Provenance binding is a revision window (reviewed_revision..head), proving ordering only; not verdict-to-file binding or freshness"
  - "A cited revision that fails to resolve reports only the not-a-committed-ancestor error, not also the descend error"
requirements-completed: [QUAL-03, HOST-02, API-05, TRAC-03]
duration: 25min
completed: 2026-10-10
---

# Phase 04 Plan 38: Receipt containment and review provenance window Summary

**No post-build exception can print a traceback or message (fixed `receipt-error: <Type>` token, minimal fail receipt), and review dispositions are ordered after a parsed 40-hex `reviewed_revision`.**

## Accomplishments
- `main()` post-build section wrapped in one outer `except Exception`: prints `receipt: receipt-error: <Type>`, writes a minimal fail receipt, falls back to `receipt: receipt-write-failed`, returns 1.
- Both build-failure handlers use `_public_reason` (G2IN-03).
- `_reviewed_revision` (exactly one 40-hex lowercase value, quotes allowed), `_frontmatter_keys` with quote/padding-normalized duplicate detection, and a window check in `review_provenance_errors`. Docstring states ordering-only limit.
- `04-REVIEW.md` gained `reviewed_revision: 82a75795e24c5fd62ff79bd0af564d16fb9fe0da`.

## Task Commits (red/green pairs)
1. Task 1 (T-04-11, G2CR-02, G2IN-03): RED `0adeacb` (test) -> GREEN `756c242` (fix)
2. Task 2 (T-04-38, T-04-67, WR-11, G2WR-01, G2WR-02): RED `858aedf` (test) -> GREEN `8c20410` (fix)

RED evidence: Task 1 RED run had 1 failure + 5 errors across the 4 target tests (raw PermissionError/KeyError/OSError tracebacks escaping `main()`; G2IN-03 assertion that `_public_reason` was called failed). Task 2 RED run had 12 errors (`_reviewed_revision` missing) + 3 failures (no window check). Semantic assessment: every target failed on the planned behavior, not on setup. The `OSError(2, ...)` subtest is reported as `FileNotFoundError` (Python maps errno 2), and the test uses the actual type name.

## 04-REVIEW.md revision checks
- `git rev-parse 82a7579^{commit}` = `82a75795e24c5fd62ff79bd0af564d16fb9fe0da` (matches).
- Report Summary scope sentence: "ea63b03 through 82a7579" (line 37).
- `git diff --quiet 82a7579 f80f82f69cb4e8254fdd3be020a4c429f9955d0b -- . ':(exclude).planning'` exit 0 (no code change).
- Step 4: `0d9612130092` and `bd74482e0050` both descend from 82a7579 (`merge-base --is-ancestor` exit 0).

## Deviations from Plan
- Fixture edit (as the plan allowed): `ReviewProvenanceTest.errors` now writes a fixture 04-REVIEW.md with `reviewed_revision` = first commit so pre-existing cases stay in-window; no existing test was loosened or deleted. Added `import contextlib` and a `receipt_run` helper to `MainErrorPathTest`.
- Otherwise none; plan executed as written.

## Verification
- `python3 tests/tools/test_verify_playable.py`: 80 tests OK. `-k t_04_11`: 3 passing plus 1 more (4 tests incl. g2in_03 matched by pattern separately); `python3 tools/verify_playable.py --check-docs` prints `Phase 04 documentation gate passed.`
- No cmake/CTest or RetroArch run (per prohibitions). No register row, severity or status edited; 04-40 records evidence.

## Known Stubs
None.

## Threat Flags
None.

## Self-Check: PASSED
