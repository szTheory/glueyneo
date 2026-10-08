---
phase: 04-public-playable-tracer
plan: 08
subsystem: libretro-qualification
tags: [RetroArch, diagnostics, qualification, consumer-tests]

# Dependency graph
requires:
  - phase: 04-public-playable-tracer
    provides: installed Libretro adapter, generated fixtures, pinned RetroArch smoke, and immutable qualification snapshot
provides:
  - bounded and sanitized diagnosis for pinned RetroArch pre-screenshot exits
  - regression coverage for fresh screenshots, process status, crash parsing, and installed fixture wiring
  - final commit-bound qualification receipt with frontend result explicitly unknown
affects: [HOST-02, QUAL-03, TRAC-01, TRAC-03]

# Actuals
actuals:
  tokens: 10564
  tasks: 2
  commits: 6

# Tech tracking
tech-stack:
  added: []
  patterns: [fresh per-run GUI profiles and captures, bounded sanitized crash diagnostics, receipt-bound installed consumer fixtures]

key-files:
  created: []
  modified:
    - tests/libretro/retroarch_smoke.py
    - tests/libretro/test_retroarch_smoke.py
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - docs/first-playable-build.md

key-decisions:
  - "A pinned app exit before the first screenshot remains unknown for HOST-02 even when the failure is reproducible and diagnosed to the frontend launch stage."
  - "Compare a fresh no-content launch with a fresh core/content launch to localize an abort; neither is frontend acceptance evidence."
  - "The installed native consumer must receive the diagnostic-original-a.bin fixture that its assertions compare, not the distinct public-playable.bin GNFX fixture."
  - "Keep app crash details bounded and sanitized; retain raw captures and logs only in ignored local output."

patterns-established:
  - "Each GUI smoke run owns fresh temporary configuration and screenshot state; old images cannot satisfy a later run."
  - "A pre-screenshot failure records stage, return code, process survival, and an available bounded macOS crash reason without relaxing the acceptance gate."

requirements-completed: []

coverage:
  - id: D1
    description: "Pinned RetroArch failures are localized with bounded diagnostics while missing frontend observations remain unknown."
    requirement: HOST-02
    verification:
      - kind: integration
        ref: "build/playable-qualification/receipt.json#retroarch_smoke; fresh no-content and core/content diagnosis"
        status: unknown
    human_judgment: true
    rationale: "The pinned app aborted before a screenshot in both fresh launch modes. HOST-02 needs real screenshot, control, unload, and exit observations, which remain unavailable until the pinned app launches in a functioning interactive macOS context."
  - id: D2
    description: "The final qualification binds source, fixture, installed artifacts, consumers, candidate gates, tests, and frontend outcome to one committed snapshot."
    requirement: QUAL-03
    verification:
      - kind: integration
        ref: "build/playable-qualification/receipt.json; source snapshot 5e2b3799c981d1987404c65138a69fc09b20613d"
        status: unknown
    human_judgment: true
    rationale: "The receipt binds the exact source and successful native build/install/consumer lanes, but its overall status is fail because the actual frontend lane is unknown. The clean install/load claim remains incomplete until that frontend evidence exists."
  - id: D3
    description: "Generated public fixture rebuild and native consumer checks remain covered by the final clean qualification."
    requirement: TRAC-01
    verification:
      - kind: integration
        ref: "build/playable-qualification/receipt.json#fixture,consumer-static-check,consumer-shared-check,full-sdk-ctest"
        status: pass
    human_judgment: false
  - id: D4
    description: "The native fixed-input fixture controls and wrong-input assertions remain covered by the SDK regression suite."
    requirement: TRAC-03
    verification:
      - kind: integration
        ref: "build/playable-qualification/receipt.json#full-sdk-ctest (34 tests); tests/libretro/test_retroarch_smoke.py (16 GUI-free tests)"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-10-07
status: complete
---

# Phase 04 Plan 08: Pinned Frontend Diagnosis Summary

**The pinned RetroArch abort is now captured as a bounded pre-screenshot failure, and the final qualification is bound to the corrected committed snapshot; HOST-02 remains unknown because no frontend screenshot or control observation was produced.**

## Performance

- **Duration:** 12 minutes
- **Started:** 2026-10-08T00:04:35Z
- **Completed:** 2026-10-08T00:16:50Z
- **Tasks:** 2
- **Files modified:** 6, including this summary.

## Accomplishments

- Added GUI-free tests for fresh screenshot selection, process survival and exit stage, bounded crash-reason parsing, output redaction, no-content/content launch comparison, and unavailable keyboard authority. All 16 `tests/libretro/test_retroarch_smoke.py` tests pass.
- Captured the pinned RetroArch 1.22.2 run as `unknown` at `first-screenshot`, return code `-6`, with no survival before screenshot and a bounded `EXC_CRASH SIGABRT / SIGNAL 6 Abort trap: 6` reason. The installed-core/content and no-content launches both abort before a screenshot; neither result is HOST-02 acceptance.
- Documented the observed boundary and retained the exact pinned app, fixture, core, and environment identities. The LaunchServices probe returned `kLSNoExecutableErr`; unified-log inspection was unavailable in the sandbox. The external precondition remains a functioning interactive macOS app launch context. The evidence does not establish a core or fixture defect.
- Added an installed-consumer regression after the first qualification exposed that the check passed `public-playable.bin` while its assertions compare the generated `diagnostic-original-a.bin`. The corrected static and shared consumer checks pass with the matching fixture.
- Ran the final clean qualification once after the fix. Its receipt binds commit `5e2b3799c981d1987404c65138a69fc09b20613d`, source inventory digest `d6b668e38b77cb65a4bb1b79988792845feebebfbb6404db688461b0827856bf`, and fixture SHA-256 `59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0`. Static/shared builds and installs, both installed consumers, all 34 CTests, candidate gates, and docs checks passed. The command exits nonzero only because the actual pinned frontend gate is unknown.

## Task Commits

1. **Task 1: Diagnose the pinned app's exit before its first screenshot** — `6453aed` (test), `bc7f635` (feat), `07b34bb` (diagnostic hardening).
2. **Task 2: Run the installed core in pinned RetroArch and regenerate qualification evidence** — `8f033c6` (docs), `7389979` (consumer regression), `5e2b379` (fix and final committed source snapshot).

## TDD Gate Compliance

- Task 1's initial failing tests covered diagnostic stage/exit/survival, fresh screenshot state, launch comparison, crash parsing, and redaction. The GSD red-evidence check classified target `test_failure_diagnostic_preserves_stage_exit_and_survival` as `RED_EVIDENCE_OK`; the implemented suite then passed.
- The first full qualification exposed a separate installed-consumer fixture mismatch. Regression `test_installed_consumer_check_uses_original_diagnostic_fixture` failed against the wrong `public-playable.bin` path and was classified `RED_EVIDENCE_OK`; commit `5e2b379` corrected the input, and the matching installed-consumer command and final receipt passed that lane.
- The first failed receipt remains local and ignored as diagnostic provenance. The final corrected clean qualification was run once from the committed snapshot.

## Files Modified

- `tests/libretro/retroarch_smoke.py` — bounded launch/crash diagnosis and fresh-run evidence.
- `tests/libretro/test_retroarch_smoke.py` — process, screenshot, crash parsing, launch comparison, and privacy regressions.
- `tools/verify_playable.py` — supply the fixture matching the installed-consumer assertions.
- `tests/tools/test_verify_playable.py` — guard the installed-consumer fixture wiring.
- `docs/first-playable-build.md` — actual diagnosis, exact observed failure, and unknown boundary.
- `04-08-SUMMARY.md` — this plan execution record.

## Deviations from Plan

The pinned app consistently aborts before its first screenshot in both no-content and core/content launches. The repository has no evidenced local cause to correct, and replacing the pinned app or claiming frontend success would invalidate the acceptance contract. The plan therefore records the narrow external launch-context precondition and leaves HOST-02 unknown. The consumer-fixture correction was a contained qualification bug discovered by the required full run and fixed before the final run.

**Total deviations:** 1 external frontend blocker and 1 contained consumer-test wiring fix.  
**Impact on plan:** Diagnostic and source-bound qualification work is complete; frontend acceptance and overall phase completion remain open.

## Issues Encountered

- `/usr/bin/open -n -W -a` reported `kLSNoExecutableErr` despite valid bundle metadata, an executable file, and successful code-signature verification. Unified log access was blocked by the sandbox. The root cause remains unknown.
- The final receipt status is `fail` because the actual pinned RetroArch load/input/video/unload gate is unknown. Its static/shared and native consumer lanes pass; it is not a passing overall QUAL-03 receipt.

## Next Phase Readiness

Plan 04-08 is complete. Phase 04 is not complete: HOST-02 and overall QUAL-03 remain unverified pending a working interactive launch of the pinned RetroArch build, followed by fresh screenshot, input-control, unload, and exit observations. Run phase goal verification now; it must preserve this blocker.

## Self-Check: PASSED

- The GUI-free RetroArch diagnostic tests (16), qualification runner tests (11), Python compilation, docs contract check, and `git diff --check` pass.
- Final receipt source identity is the committed corrected snapshot, and the installed-consumer lanes use the matching generated diagnostic fixture.
- No requirements or phase completion status was advanced by this summary.

---
*Phase: 04-public-playable-tracer*
*Completed: 2026-10-07*
