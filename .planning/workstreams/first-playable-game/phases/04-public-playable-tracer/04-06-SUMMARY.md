---
phase: 04-public-playable-tracer
plan: 06
subsystem: build-qualification
tags: [CMake, CTest, Libretro, RetroArch, macOS, Z80, ymfm]
dependency_graph:
  requires: [04-01 fixture and native tracer, 04-02 Libretro smoke, 04-03 guest fixture, 04-04 Z80 candidate, 04-05 YM2610 candidate]
  provides: [clean static/shared install workflow, installed C consumer check, exact identity and qualification receipt, integrator build guide]
  affects: [QUAL-03, HOST-02, TRAC-01, SND-01, SND-02]
tech_stack:
  added: [Python clean qualification runner, installed Libretro artifact]
  patterns: [fresh build and install prefixes, status per validation lane, fixture and toolchain identity, unknown frontend result preserved]
key_files:
  created:
    - tools/verify_playable.py
    - tests/consumers/test_playable_install.py
    - docs/first-playable-build.md
  modified:
    - CMakeLists.txt
    - README.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md
decisions:
  - "Install the shared Libretro adapter under lib/libretro so the clean runner can load the installed artifact."
  - "Keep the pinned RetroArch result unknown after exit -6 before screenshot; callback tests do not qualify HOST-02."
  - "Retain Z80 synthetic-workload and YM2610 candidate-only claim boundaries."
requirements-completed: []
metrics:
  duration: 9min
  completed: 2026-10-07
  status: complete
  commits: 2
  plan_head_before: 3f5a54c2e49697adaba8037e0b318266a70a4674
  plan_head_after: f808391833f59fdac5d53280e9b07b95ea406018
actuals:
  tokens: 9949
  tasks: 2
  commits: 2
coverage:
  - id: D1
    description: "Fresh static/shared native installs and real out-of-tree C consumers pass."
    requirement: QUAL-03
    verification:
      - kind: integration
        ref: "tools/verify_playable.py --clean; consumer-static-check and consumer-shared-check"
        status: pass
    human_judgment: false
  - id: D2
    description: "The generated public fixture and full clean CTest suite pass with recorded identities."
    requirement: TRAC-01
    verification:
      - kind: integration
        ref: "build/playable-qualification/receipt.json; full CTest 34/34"
        status: pass
    human_judgment: false
  - id: D3
    description: "Pinned RetroArch loads and presents the fixture, applies input, and unloads."
    requirement: HOST-02
    verification:
      - kind: e2e
        ref: "tests/libretro/retroarch_smoke.py; RetroArch exited -6 before screenshot"
        status: unknown
    human_judgment: true
    rationale: "The app exited before producing a screenshot, so the frontend interaction could not be observed."
  - id: D4
    description: "The pinned Z80 candidate passes the documented synthetic workload."
    requirement: SND-01
    verification:
      - kind: integration
        ref: "tests/chips/check_z80_source.py and clean CTest z80_admission*; synthetic workload only"
        status: pass
    human_judgment: false
  - id: D5
    description: "The pinned YM2610 candidate passes source, direct and installed static/shared C consumer gates."
    requirement: SND-02
    verification:
      - kind: integration
        ref: "build/ym2610-admission/ym2610-admission.json SHA-256 a6faf3de0dc68dec67e80743413d4e53de6ade6620123db5ccb6d3fec2e02"
        status: pass
    human_judgment: false
---

# Phase 04 Plan 06: Clean Build and Qualification Summary

**Fresh macOS static/shared installs and C consumers pass with a reproducible public fixture and candidate receipts; actual RetroArch remains unknown after exiting before its first screenshot.**

## Performance

- **Duration:** 9 minutes
- **Started:** 2026-10-07T21:59:25Z
- **Completed:** 2026-10-07T22:08:31Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added a bounded runner that creates fresh static/shared CMake build and install prefixes, runs installed C consumers, verifies the generated public fixture, runs all 34 CTests, and records each candidate/frontend lane with exact identities and a command-log hash.
- Installed the Libretro shared core beside the SDK package and verified the out-of-tree C consumer against both native linkages.
- Recorded the macOS compiler, SDK, OS, architecture, CMake, Ninja, Python, RetroArch artifact, fixture and YM2610 report identities in the integrator guide and ignored qualification receipt.
- Updated the validation map with task IDs, waves, measured latency, threat mapping and actual statuses. HOST-02 remains unknown because the pinned RetroArch process exited with status `-6` before a screenshot.

## Task Commits

1. **Task 1: Verify clean native/Libretro install and real consumers** — `12ed41c` (`feat`)
2. **Task 2: Publish exact macOS build/load instructions and final validation map** — `f808391` (`docs`)

## Files Created/Modified

- `tools/verify_playable.py` — fresh static/shared qualification runner; fails aggregate status on mandatory failures or unknowns.
- `tests/consumers/test_playable_install.py` — checks the installed diagnostic runner, fixture and C consumer, and verifies the installed Libretro artifact exists.
- `CMakeLists.txt` — installs `glueyneo_libretro` under `lib/libretro`.
- `docs/first-playable-build.md` — exact clean commands, tested macOS identity, artifact hashes, unsupported configurations and claim limits.
- `README.md` — fixes planning links to the active workstream paths so clean documentation/package CTests can resolve them.
- `.planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md` — execution-complete validation map with the unqualified frontend outcome retained.

## Decisions Made

- The clean package includes the Libretro adapter at `lib/libretro`, while native static/shared packages retain their ordinary consumer contract.
- The actual frontend run is `unknown`, not a pass. Native callback tests and successful install checks do not substitute for screenshot evidence from RetroArch.
- Z80 evidence remains limited to its named synthetic workload. YM2610 evidence remains candidate-only even though its source, direct test and installed static/shared consumers pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Install the Libretro core used by the clean load check**
- **Found during:** Task 1
- **Issue:** CMake built `glueyneo_libretro` but did not install it, so the requested clean installed-frontend path had no artifact to load.
- **Fix:** Added an install rule under `${CMAKE_INSTALL_LIBDIR}/libretro` and made the runner use the installed core.
- **Files modified:** `CMakeLists.txt`, `tools/verify_playable.py`, `tests/consumers/test_playable_install.py`
- **Verification:** Fresh static/shared installs contain the core; native consumers pass. The actual RetroArch run reached the pinned app and then exited before screenshot.
- **Committed in:** `12ed41c`

**2. [Rule 3 - Blocking] Update stale README planning links that failed clean package checks**
- **Found during:** Task 1
- **Issue:** Full clean CTest's README-link and capability checks failed on links to removed flat-mode `.planning/` paths.
- **Fix:** Pointed the README links at the current workstream verification/state/requirements/roadmap files.
- **Files modified:** `README.md`
- **Verification:** The complete clean CTest suite passed 34/34 after the link fix.
- **Committed in:** `12ed41c`

**Total deviations:** 2 auto-fixed (one Rule 2, one Rule 3). Both were required for the clean install and full-suite workflow.

## Issues Encountered

- The selected RetroArch 1.22.2 executable matched its pinned SHA-256, but exited with status `-6` before a screenshot. HOST-02 remains unknown and needs a fresh actual frontend run after the app issue is resolved.
- The qualification command returns nonzero while that frontend gate is unknown, as required by the fail-closed contract. Static/shared builds, installs, installed native C consumers, fixture identity, all 34 CTests, Z80 synthetic gate and YM2610 candidate gates passed.

## Known Stubs

None. The unresolved RetroArch result is an unavailable acceptance observation, not a stub in the runner.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: native-module-load | `CMakeLists.txt` | The installed Libretro shared object is loaded by an external frontend; the runner records its digest and preserves the failed actual-load outcome as unknown. |

## Next Phase Readiness

Plan 04-06 is complete; Phase 04 is not accepted because HOST-02 remains unknown. The public fixture, native trace and chip-candidate evidence are recorded for phase verification. The verifier must retain the unresolved actual frontend result and may route a bounded follow-up if fresh evidence makes that gap actionable.

## Self-Check: PASSED

- Created artifacts exist: `tools/verify_playable.py`, `tests/consumers/test_playable_install.py`, `docs/first-playable-build.md`, and `04-VALIDATION.md`.
- Task commits `12ed41c` and `f808391` are ancestors of HEAD.
- No stub or placeholder patterns were found in the files created or modified for this plan.

---
*Phase: 04-public-playable-tracer*
*Completed: 2026-10-07*
