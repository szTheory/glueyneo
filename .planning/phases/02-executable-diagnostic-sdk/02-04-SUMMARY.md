---
phase: 02-executable-diagnostic-sdk
plan: "04"
subsystem: sdk-packaging
tags: [cmake, static, shared, installed-package, c17, consumers, documentation]

# Dependency graph
requires:
  - phase: 01-cpu-acceptance-experiment
    provides: Bounded owned C17 candidate and original diagnostic evidence admitted for Phase 02 integration.
  - phase: 02-executable-diagnostic-sdk
    provides: Public API, original fixture, lifecycle/ownership contract, and bounded timing behavior from Plans 02-01 through 02-03.
provides:
  - Versioned relocatable Glueyneo::glueyneo CMake package with static/shared offline installation.
  - Moved-prefix C and C++ consumers, installed runner, and original fixture checks for both variants.
  - Compiled getting-started/recovery example and executable README capability contract.
affects: [02-05, 02-06, sdk-verification, package-consumers]

# Actuals (#2632); tokens are changed diff characters / 4, rounded up.
actuals:
  tokens: 14746
  tasks: 3
  commits: 3
commits: 3
plan_head_before: fead60b8706b732253c61db168a1fb0b46d2ae3d
plan_head_after: 08750b7d95909f662f3290c06f3779f768d766a2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - GNUInstallDirs-backed relocatable CMake export and package version metadata.
    - Separate static/shared build and install prefixes verified through independent consumers.
    - Compiled README commands and documentation contract checks in focused CTest labels.

key-files:
  created:
    - cmake/GlueyneoConfig.cmake.in
    - tests/consumers/CMakeLists.txt
    - tests/consumers/header.cpp
  modified:
    - CMakeLists.txt
    - tests/consumers/check_package.py
    - examples/diagnostic.c
    - README.md

key-decisions:
  - "Derive the alpha package version from project VERSION and require the exact 0.1.0 package in the independent consumer."
  - "Keep runtime dependencies empty; install only the public package surface, runner, original fixture, and notices needed by consumers."
  - "Treat relocation as package-metadata and loader evidence on the tested Darwin host, not release-archive or platform-matrix qualification."

patterns-established:
  - "Installed package checks: build separate static/shared trees offline, move the prefix, then compile and execute C and C++ consumers using only the installed package."
  - "Documentation checks: execute copyable README commands and recovery examples against both installed variants, then assert capability statements against the candidate contract."

requirements-completed: [BUILD-01, BUILD-02, DIAG-01, DOC-01, DOC-02]

# Coverage metadata
coverage:
  - id: D1
    description: Offline C17 static and shared SDK packages install with public-only relocatable metadata and no runtime dependency tree.
    requirement: BUILD-01
    verification:
      - kind: integration
        ref: "python3 tests/consumers/check_package.py --suite build"
        status: pass
    human_judgment: false
  - id: D2
    description: Independent C and C++ consumers compile and run from moved static and shared install prefixes; the shared loader selects the moved library and negative controls fail at their intended checks.
    requirement: BUILD-02
    verification:
      - kind: e2e
        ref: "python3 tests/consumers/check_package.py --suite consumers"
        status: pass
    human_judgment: false
  - id: D3
    description: The installed original diagnostic produces arithmetic 10, initialized data 0x1237, BSS 1, and nonzero progress for both library variants.
    requirement: DIAG-01
    verification:
      - kind: e2e
        ref: "python3 tests/consumers/check_package.py --suite consumers"
        status: pass
    human_judgment: false
  - id: D4
    description: Copyable getting-started commands and malformed-manifest recovery compile and execute against both installed package variants.
    requirement: DOC-01
    verification:
      - kind: integration
        ref: "python3 tests/consumers/check_package.py --suite docs"
        status: pass
    human_judgment: false
  - id: D5
    description: Capability documentation states the selected instruction, mapping, bus, event, STOP, overshoot, and exclusion boundaries without claiming unqualified hardware or platform behavior.
    requirement: DOC-02
    verification:
      - kind: unit
        ref: "python3 tests/consumers/check_package.py --suite capabilities"
        status: pass
    human_judgment: false

# Metrics
duration: 19min
completed: 2026-10-05
status: complete
---

# Phase 02 Plan 04: Installed Static/Shared C17 SDK Summary

**An offline relocatable CMake package now builds as static or shared, with moved-prefix C/C++ consumers and compiled setup, recovery, and capability guidance.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-10-05T21:21:05-04:00
- **Completed:** 2026-10-05T21:40:12-04:00
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added an installable `Glueyneo::glueyneo` package at version 0.1.0, generated relocatable config/version metadata, and installed the public header, MIT notice, headless runner, and original firmware-free fixture.
- Verified separate offline static/shared builds and moved install prefixes. C consumers reported arithmetic 10, initialized data 0x1237, BSS 1, 172 guest cycles, 12 instructions, and PC 0x12e; C++ consumers compiled, linked, and called the public API. Five negative package/output controls failed at their intended checks.
- Added a compiled diagnostic example with malformed-manifest recovery and documented the candidate's instruction, address, event, timing, and excluded-capability boundaries. The docs suite executed eight commands per variant and the capability checker validated the claims.

## Test Evidence

All four plan suites passed on Darwin arm64 with AppleClang 21.0.0.21000101 and CMake 4.4.3:

- `python3 tests/consumers/check_package.py --suite build` — 2/2 CTest cases passed. Both variants configured offline with tests disabled; the fixture digest was `495eb195089d0ee7e73f4090514980b47a5fd4a55869d9e7f46376bce1646948`. Shared exports were exactly the eight public `gn_*` symbols. The declared CMake 3.20 floor remains unqualified.
- `python3 tests/consumers/check_package.py --suite consumers` — 2/2 cases passed. Each variant completed 20 C assertions and 2 C++ assertions; all five missing/corrupt package and wrong-output controls behaved as intended. The shared-loader trace resolved to the moved prefix; the static consumer linked its moved installed archive. The installed runner regenerated the 522-byte fixture.
- `python3 tests/consumers/check_package.py --suite docs` — 3/3 cases passed: 16 README commands found and executed, nine local links resolved, and eight commands per variant compiled and ran. Each example variant recovered from `GN_STATUS_INVALID_MEDIA`, then ran the previously loaded diagnostic successfully.
- `python3 tests/consumers/check_package.py --suite capabilities` — 1/1 case passed with 56 contract assertions. The checker preserves unknowns for original-silicon saved PC, CMake 3.20, and other platforms.

The package and consumer evidence is local to this host. It does not establish support for other platforms, a release archive, or full CMake-floor compatibility.

## Task Commits

1. **Task 1: Build an offline installed C17 SDK in both linkage variants** — `0d84e6e` (`feat`)
2. **Task 2: Execute real relocated installed C and C++ consumers** — `edb2102` (`test`)
3. **Task 3: Compile the getting-started guide and automate its failure reproduction** — `08750b7` (`docs`)

## Files Created/Modified

- `CMakeLists.txt` — static/shared targets, install/export metadata, generated package version, runner/fixture installation, and focused CTest registrations.
- `cmake/GlueyneoConfig.cmake.in` — relocatable first-party package config.
- `tests/consumers/CMakeLists.txt` — independent installed-package C/C++ consumer build.
- `tests/consumers/header.cpp` — public-header C++ compile/link/API probe.
- `tests/consumers/check_package.py` — offline build, relocated consumer, README-command, capability, and negative-control supervisor.
- `examples/diagnostic.c` — installed-fixture diagnostic and invalid-manifest recovery example.
- `README.md` — getting-started commands, API use and recovery, current capability boundaries, evidence and limits.

## Decisions Made

- The package version follows the root project `VERSION`; the consumer requires exactly 0.1.0 so package metadata and sample contract cannot silently drift.
- `BUILD_SHARED_LIBS` selects the library form while each check uses its own build and install prefix. Only the public header/library usage requirements are exported; tests and the private CPU backend stay out of the package.
- A moved prefix demonstrates relocatable metadata and loader behavior on the tested host. Release archives, CMake 3.20, and other platforms remain unqualified.

## Deviations from Plan

None — plan executed as written.

## Issues Encountered

- The first build-suite attempt could not find the compiler ID in the CMake cache; the checker was corrected to read generated compiler metadata, after which both variants passed.
- Initial README checker thresholds and a required phrase split across a Markdown line break did not match the actual document. The checks were adjusted to the real links, commands, and stable phrase; final docs and capability suites passed.

## User Setup Required

None — no external service or credential is required.

## Next Plan Readiness

Plan 02-04 is complete; Phase 02 remains in progress. The package, moved-prefix consumers, executable docs, and capability contract are ready for the remaining Phase 02 plan work. The CMake 3.20 floor, original-silicon saved PC, and non-Darwin platform support remain explicitly unknown or unqualified.

---
*Phase: 02-executable-diagnostic-sdk*
*Completed: 2026-10-05*

## Self-Check: PASSED

- All seven plan-owned created/modified files and this summary exist.
- Task commits `0d84e6e`, `edb2102`, and `08750b7` are present in Git history.
