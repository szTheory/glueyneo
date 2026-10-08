---
phase: 04-public-playable-tracer
plan: 10
subsystem: qualification
tags: [python, privacy, retroarch, fixture-identity]
requires:
  - phase: 04-public-playable-tracer
    provides: generated 602-byte GNFX public fixture and pinned RetroArch identity
provides:
  - Complete redaction of private path spans in qualification and frontend diagnostics
  - Pinned fixture digest enforcement before direct frontend launch
  - Shared validated RetroArch quit path for normal unload and cleanup
affects: [phase-04-security-audit, frontend-qualification]
actuals:
  tokens: 7303
  tasks: 3
  commits: 7
tech-stack:
  added: []
  patterns: [standard-library bounded path redaction, pre-launch content digest validation]
key-files:
  created: []
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - tests/libretro/retroarch_smoke.py
    - tests/libretro/test_retroarch_smoke.py
key-decisions:
  - "Stop unquoted path redaction at explicit diagnostic delimiters and redact ambiguous tails through line end."
  - "Require the documented fixture digest and exact pinned RetroArch bundle identifier before frontend use."
requirements-completed: []
coverage:
  - id: D1
    description: Qualification and frontend diagnostic sinks remove complete private paths while preserving bounded status details.
    verification:
      - kind: unit
        ref: python3 -m unittest discover -s tests/tools -p test_verify_playable.py -v
        status: pass
      - kind: unit
        ref: python3 -m unittest discover -s tests/libretro -p test_retroarch_smoke.py -v
        status: pass
    human_judgment: false
  - id: D2
    description: Direct smoke accepts the generated fixture identity and rejects same-size modified bytes before Popen.
    verification:
      - kind: unit
        ref: tests/libretro/test_retroarch_smoke.py#FixtureIdentityTests
        status: pass
    human_judgment: false
  - id: D3
    description: Both normal and cleanup quit requests accept only the pinned bundle identifier and use bounded fixed-shape AppleScript.
    verification:
      - kind: unit
        ref: tests/libretro/test_retroarch_smoke.py#BundleIdentifierTests
        status: pass
    human_judgment: false
duration: 7 min
completed: 2026-10-08
status: complete
commits: 7
plan_head_before: 8755ca0e2e3bb71d30949e45622a198da67ce1ff
plan_head_after: e7aa2552318923a2c456a38411d612086238cddb
---

# Phase 04 Plan 10: Qualification Boundary Repairs Summary

**Path-space redaction, generated-fixture digest pinning, and validated RetroArch quit handling now protect retained diagnostic evidence and direct smoke inputs.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-08T03:06:12Z
- **Completed:** 2026-10-08T03:13:48Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Removed complete synthetic home, temporary, repository, and volume path spans from qualification logs, command metadata, receipts, machine summaries, frontend logs, and crash reasons while retaining stage and status details.
- Enforced SHA-256 `59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0` before direct smoke can launch a frontend; a generated known fixture passes and a same-size mutation is rejected before `Popen`.
- Pinned the app identity to `com.libretro.dist.RetroArch` and routed normal and cleanup shutdown through one bounded helper; malformed, missing, quoted, newline, control-character, and command-shaped identifiers cannot reach `osascript`.
- Kept the six high-severity findings open in `04-SECURITY.md`; HOST-02 and actual frontend QUAL-03 remain unknown. No GUI run or requirement status change was performed.

## TDD Evidence

- **Task 1 RED:** The target path-redaction test failed on assertions showing private path suffixes remained; `gsd_run check tdd-red-evidence` returned `RED_EVIDENCE_OK`. **GREEN:** both focused suites passed after the two sanitizers and retained-output sinks were updated.
- **Task 2 RED:** The target wrong-digest test observed the mocked frontend process boundary and failed because the stage was `launch` instead of `input`; classifier returned `RED_EVIDENCE_OK`. **GREEN:** the exact generated fixture passed input validation and modified bytes failed before `Popen`.
- **Task 3 RED:** The target invalid-identifier test observed malformed values passed to `subprocess.run`; classifier returned `RED_EVIDENCE_OK`. **GREEN:** plist validation rejects unexpected identifiers and the common helper skips AppleScript and terminates the owned process for unsafe values.

## Task Commits

1. **Task 1 RED:** `93c7bef` — add path redaction regressions
2. **Task 1 GREEN:** `eff633a` — sanitize retained diagnostics
3. **Task 2 RED:** `6543a98` — reject unpinned frontend fixtures
4. **Task 2 GREEN:** `3b77034` — pin direct smoke fixture digest
5. **Task 3 RED:** `1332df0` — reject unsafe frontend quit targets
6. **Task 3 GREEN:** `2fed3e8` — constrain frontend quit identity
7. **Task 3 cleanup:** `e7aa255` — clarify mock executable fixtures

## Files Created/Modified

- `tools/verify_playable.py` — complete private path-span redaction for returned command text, lane metadata, persisted output, receipt data, and machine summary.
- `tests/tools/test_verify_playable.py` — adversarial path and serialization boundary coverage.
- `tests/libretro/retroarch_smoke.py` — complete diagnostic path redaction, fixture digest check, pinned bundle identifier, and centralized bounded quit handling.
- `tests/libretro/test_retroarch_smoke.py` — generated-fixture, no-launch mutation, path, metadata, and cleanup regressions.

## Decisions Made

- Unquoted private path tails are redacted through end of line unless an explicit delimiter separates the following diagnostic text; quoted paths stop at their closing quote.
- Fixture bytes and app metadata are validated before the frontend process or quit subprocess can receive them.

## Deviations from Plan

None. The test-only fixture naming cleanup remained within the plan's declared files and introduced no behavior change.

## Issues Encountered

- The initial GSD commit-helper attempt could not create `.git/index.lock` under the workspace sandbox. The same helper and declared file list succeeded with repository-write escalation; no raw git staging or commit command was used.

## User Setup Required

None.

## Next Phase Readiness

Plan 04-10 is complete. Phase 04 remains incomplete: a separate security audit must evaluate the six still-open findings, and HOST-02/actual frontend QUAL-03 still require fresh pinned-app evidence. No requirement status was advanced.

## Self-Check: PASSED

- All four declared implementation and test files exist.
- All seven task commits are ancestors of the current plan head.
- `gsd_run check evaluation-scope --plan 04-10 --commits-only` resolved this plan's seven commits.
- Exact focused tools and frontend smoke suites passed (14 and 24 tests).
- Security register remains blocked with six open findings; no requirement status was changed, and HOST-02/actual frontend QUAL-03 remain unknown.

---
*Phase: 04-public-playable-tracer*
*Completed: 2026-10-08*
