---
phase: "04"
slug: "public-playable-tracer"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-07"
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | CTest with the repository's pinned Unity test dependency |
| **Config file** | `CMakePresets.json`; use the existing `sdk-debug` configure/build/test presets |
| **Quick run command** | `cmake --preset sdk-debug && cmake --build --preset sdk-debug && ctest --preset sdk-debug --output-on-failure --no-tests=error` |
| **Full suite command** | `cmake --preset sdk-debug && cmake --build --preset sdk-debug && ctest --preset sdk-debug --output-on-failure --no-tests=error` |
| **Estimated runtime** | Not measured for Phase 04; capture it after the new targets exist |

The existing SDK suite is the regression floor. A passing callback harness cannot substitute for the actual pinned RetroArch smoke required by HOST-02. Keep the workstream's existing SDK and CPU diagnostic checks in the selected test preset.

## Sampling Rate

- **After every task commit:** Run the focused test target added by that task, then the existing SDK regression command above when the task changes shared runtime behavior.
- **After every plan wave:** Run the full `sdk-debug` build and CTest command above, including the diagnostic SDK regressions.
- **Before `$gsd-verify-work`:** Rebuild the fixture from a clean source tree, run native and actual RetroArch consumers, run both chip-admission gates, and complete clean install/load qualification. Record exact inputs and tool identities.
- **Max feedback latency:** Not measured; measure focused selectors as they are introduced and keep ordinary task feedback bounded.

## Per-Task Verification Map

Plan and task IDs below map the planned checks. The named new test files and targets do not exist until their plan executes; every row remains pending until a real run records its result.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01 T1 / 04-03 T2 | 04-01 / 04-03 | 1 / 2 | TRAC-01 | T-04-01, T-04-05 | Original, reproducible fixture plus rights/oracle record | integration/provenance | `python3 tests/fixture/check_fixture.py --source tests/fixture/public_guest.c --artifact build/sdk-debug/public-playable.bin --rights tests/fixture/rights-manifest.json --check-rebuild --negative-control` | No — planned | pending |
| 04-01 T1-T2 | 04-01 | 1 | TRAC-02 | T-04-02 | C API validates output buffers before write | integration/boundary | `cmake --build --preset sdk-debug --target public_guest_test && ctest --preset sdk-debug -R '^public_guest_' --output-on-failure --no-tests=error` | No — planned | pending |
| 04-01 T3 | 04-01 | 1 | TRAC-03 | T-04-02 | Guest state and pixels follow input; controls fail expected trace | integration/negative control | `ctest --preset sdk-debug -R '^public_guest_(trace|negative)' --output-on-failure --no-tests=error` | No — planned | pending |
| 04-02 T1-T2 | 04-02 | 2 | HOST-02 | T-04-03, T-04-04 | Actual pinned RetroArch loads, polls, presents and unloads | frontend smoke | `python3 tests/libretro/retroarch_smoke.py --retroarch /Applications/RetroArch.app --core build/sdk-debug/glueyneo_libretro.dylib --content build/sdk-debug/public-playable.bin` | No — planned | pending |
| 04-01 T2 | 04-01 | 1 | API-05 | T-04-02 | Bounded machine time, capacities, progress/errors, silent-audio metadata | contract/boundary | `ctest --preset sdk-debug -R '^public_guest_' --output-on-failure --no-tests=error` | No — planned | pending |
| 04-04 T1-T3 | 04-04 | 3 | SND-01 | T-04-06, T-04-07 | Pinned Z80 passes state, cycle, IRQ, bus, continuation, isolation | candidate conformance | `python3 tests/chips/check_z80_source.py && ctest --preset sdk-debug -R '^z80_admission' --output-on-failure --no-tests=error` | No — planned | pending |
| 04-05 T1-T3 | 04-05 | 4 | SND-02 | T-04-08, T-04-09, T-04-10 | Pinned ymfm passes state, clock/sample, isolation, failure, C links | candidate conformance/consumer | `ctest --preset sdk-debug -R '^ym2610_admission' --output-on-failure --no-tests=error && python3 tests/chips/check_ym2610_link.py --both-linkages` | No — planned | pending |
| 04-06 T1-T2 | 04-06 | 5 | QUAL-03 | T-04-11, T-04-12 | Clean install/load and exact tested identities | clean package/consumer smoke | `python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean --check-docs` | No — planned | pending |

## Wave 0 Requirements

- [ ] Add the original fixture source/assets, bounded generator, rights/notices record, oracle, and deterministic regeneration check.
- [ ] Add native frame/input/video/audio-buffer contract and C-consumer tests, including malformed input and exact-size, short, padded-pitch, null, and overflow boundaries.
- [ ] Add guest-state and semantic-pixel checks with controlled-input and wrong-input/no-input cases.
- [ ] Add a Libretro callback-contract harness, while keeping it separate from the actual RetroArch acceptance check.
- [ ] Establish a runnable pinned macOS RetroArch smoke path for ordinary load, run, input, software video, and unload; if the selected app cannot run, report HOST-02 as blocked/unknown rather than substituting a mock.
- [ ] Add separate Z80 and ymfm admission evidence, including source/license/state inventories, deterministic behavior, independent instances, and real static/shared C consumers for ymfm.
- [ ] Add clean macOS install/load instructions with compiler, SDK, OS, architecture, frontend, source, and artifact identities.

## Manual-Only Verifications

No behavior is designated manual-only at planning time. First attempt to automate the actual RetroArch input/presentation path. If the selected pinned application or host environment makes one interaction irreducibly manual, record the narrow residual check and exact reason; do not count it as satisfied by the callback harness.

## Validation Sign-Off

- [ ] Every plan task has an executable `<automated>` verification or an explicit Wave 0 dependency.
- [ ] Sampling continuity: no three consecutive tasks lack automated verification.
- [ ] Wave 0 covers every currently missing Phase 04 test lane.
- [ ] No watch-mode flags are used in acceptance commands.
- [ ] Replace `nyquist_compliant: false` only after validation is run and its actual coverage is recorded.

**Approval:** pending
