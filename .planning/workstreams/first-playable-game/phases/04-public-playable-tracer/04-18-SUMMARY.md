---
phase: 04-public-playable-tracer
plan: 18
subsystem: evidence-gates
tags: [python, security-crosswalk, frontend-status, regression-tests]
requires: [04-17]
provides: [severity-aware-security-crosswalk, source-faithful-evidence-map-tests, constrained-pending-frontend-gate]
affects: [phase-04-validation, host-02, qual-03]
tech-stack:
  added: []
  patterns: [explicit-current-evidence, constrained-status-grammar]
key-files:
  created: [.planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-18-SUMMARY.md]
  modified:
    - tests/tools/check_phase04_validation_map.py
    - tests/tools/test_check_phase04_validation_map.py
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
decisions:
  - Keep the security frontmatter blocking count at four high/open rows while retaining T-04-34 as medium/open.
  - Require current report and validation-cell evidence to preserve HOST-02 and frontend QUAL-03 as pending or unknown.
requirements_completed: []
coverage:
  - id: D1
    description: Current security and review evidence reconciles with severity-aware counts and source-faithful mutations.
    verification:
      - kind: unit
        ref: "python3 tests/tools/check_phase04_validation_map.py"
        status: pass
      - kind: unit
        ref: "python3 tests/tools/test_check_phase04_validation_map.py -v (14 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: The current frontend status remains Pending/unknown and rejects affirmative app-observation claims.
    requirement: HOST-02
    verification:
      - kind: unit
        ref: "python3 tests/tools/test_verify_playable.py -v (23 tests)"
        status: pass
      - kind: other
        ref: "python3 tools/verify_playable.py --check-docs"
        status: pass
    human_judgment: true
    rationale: Actual pinned RetroArch load, display, input, unload, and exit remain manual-only and unobserved; this plan establishes no GUI proof.
metrics:
  duration: 5min
  completed: 2026-10-08
  tasks: 3
  files: 4
  commits: 3
  plan_head_before: 15c147536aedc18409a00a2072d7013933ea22c0
  plan_head_after: 065d59f152a774e3b3df9e8859f1f09037f1ee1f
status: complete
actuals:
  tokens: 6128.5
  tasks: 3
  commits: 3
---

# Phase 04 Plan 18: Current Evidence Gates Summary

**The evidence checker now distinguishes four high/open blockers from the retained medium/open T-04-34 row and requires explicit current frontend uncertainty.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-10-08T18:01:49Z
- **Completed:** 2026-10-08T18:06:45Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Reconciled the security blocking count against high/open register rows while requiring the exact four reserved high/open IDs and T-04-34 medium/open.
- Updated the evidence-map mutation suite to copy current documents unchanged, use noncolliding synthetic review IDs, reconcile current counts, reject malformed/duplicate requirement rows, and guard all current frontend evidence rows against added or rewritten claims.
- Constrained the current `04-15 T2` status cell to its explicit Pending/unknown grammar; affirmative claims about load, presentation, input, and unload now fail.
- Kept HOST-02 and frontend QUAL-03 Pending/unknown, and all five specified open threats unchanged.

## Task Commits

1. **Task 1: Make the direct current-evidence gate accept truthful blocked records** — `ec688ef` (fix)
2. **Task 2: Align all twelve evidence-map mutations with the current review and report** — `317473d` (test)
3. **Task 3: Reject alternate affirmative frontend load claims in the docs gate** — `065d59f` (fix)

**Plan metadata:** the summary/state/roadmap metadata commit is reported with plan completion.

## Files Created/Modified

- `tests/tools/check_phase04_validation_map.py` — validates severity-aware security counts and current report uncertainty.
- `tests/tools/test_check_phase04_validation_map.py` — aligns mutation fixtures to current evidence and rejects masked report changes.
- `tools/verify_playable.py` — accepts only the constrained current Pending/unknown status representation.
- `tests/tools/test_verify_playable.py` — rejects affirmative frontend observation claims in that cell.

## Decisions Made

- The security frontmatter count remains four because it counts high/open blockers; the checker separately requires T-04-34 as medium/open and rejects other open rows.
- HOST-02 and frontend QUAL-03 remain unresolved. Actual pinned RetroArch evidence is manual-only and was not attempted.

## Deviations from Plan

The plan's original three tasks completed as written. After the fresh scoped code review replaced the current report with a clean review, three mutation tests exposed an assumption that WR-06 remained in the live report. The copied-review tests now seed the exact synthetic current finding they exercise, so they remain meaningful with either clean or non-clean live review output. The test count and intended open dispositions are unchanged.

## Checks Run

- `python3 tests/tools/check_phase04_validation_map.py` — passed; the checker also reran and reconciled the current 23-test qualification suite and 27-test GUI-free frontend suite.
- `python3 tests/tools/test_check_phase04_validation_map.py -v` — passed, 14/14.
- `python3 tests/tools/test_verify_playable.py -v` — passed, 23/23.
- `python3 tools/verify_playable.py --check-docs` — passed.

## Issues Encountered

The managed filesystem initially denied writes to `.git`. The task commits and ledger were completed through reviewed escalation; only task-owned files were staged.

Post-plan review corrections made the `WR-99` case create its own Warning section, explicitly seeded WR-06 for its closure mutation, and matched the disposition's carried-source marker. Independent review then found that free-form semantic matching kept admitting paraphrased success claims and that several current report cells were unchecked. The checker now requires exact source-derived rows for every current frontend-related report surface, including goals, artifacts, links, data flow, behavioral spot-checks, and HOST-02/QUAL-03. It rejects appended claims, malformed rows, and duplicate requirements. The current review is clean, all fourteen mutation tests pass, and the five security findings plus manual-only frontend status remain open.

## Next Phase Readiness

Plan 04-18 is complete. Phase 04 itself remains incomplete: the four reserved high/open threats and T-04-34 medium/open remain unresolved, actual pinned RetroArch GUI evidence remains unknown, and HOST-02/frontend QUAL-03 remain pending. No requirement was marked complete.

---
*Phase: 04-public-playable-tracer*
*Completed: 2026-10-08*

## Self-Check: PASSED

- Summary file exists at the expected phase path.
- Task commits `ec688ef`, `317473d`, and `065d59f` are ancestors of HEAD.
