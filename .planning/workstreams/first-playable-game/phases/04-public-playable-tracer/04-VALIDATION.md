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

Plan and task IDs are intentionally pending until the planner creates the executable plans. These rows define the requirement-level checks the plans must assign; no Phase 04 tests exist yet.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | TRAC-01 | TBD | Generated fixture is original, reproducible, bounded, and accompanied by rights, notices, and oracle ancestry | integration/provenance | `cmake --preset sdk-debug && cmake --build --preset sdk-debug && ctest --preset sdk-debug --output-on-failure --no-tests=error` (add a fixture identity/provenance test) | No — Wave 0 | pending |
| TBD | TBD | TBD | TRAC-02 | TBD | Ordinary C API validates format, dimensions, pitch, capacity, and caller-buffer lifetime before writes | integration/boundary | Same SDK preset command (add C consumer and pixel/buffer boundary tests) | No — Wave 0 | pending |
| TBD | TBD | TBD | TRAC-03 | TBD | Guest state and semantic pixels follow sampled input; wrong-direction/no-input control fails | integration/negative control | Same SDK preset command (add fixed-trace and negative-control tests) | No — Wave 0 | pending |
| TBD | TBD | TBD | HOST-02 | TBD | Actual pinned RetroArch loads the same generated content, polls mapped input, presents software video, and unloads | frontend smoke | Plan must select and run an actual RetroArch command/automation path; a mocked callback harness is insufficient | No — Wave 0 | pending |
| TBD | TBD | TBD | API-05 | TBD | Native core uses bounded deterministic time and explicit capacities/progress/errors without host services | contract/boundary/symbol audit | Same SDK preset command (add API boundary and host-service closure checks) | No — Wave 0 | pending |
| TBD | TBD | TBD | SND-01 | TBD | Pinned Z80 candidate passes license/state, cycle, interrupt, bus, continuation, and instance-isolation evidence before admission | candidate conformance | Same SDK preset command plus the admission runner selected by the plan | No — Wave 0 | pending |
| TBD | TBD | TBD | SND-02 | TBD | Pinned ymfm subset passes source/state, deterministic clock/sample, isolation, contained-failure, and static/shared C-link evidence before admission | candidate conformance/consumer | Same SDK preset command plus the admission runner and installed static/shared C consumers selected by the plan | No — Wave 0 | pending |
| TBD | TBD | TBD | QUAL-03 | TBD | Clean macOS build/install/load procedure names exact identities and untested configurations | clean package/consumer smoke | Plan must specify the clean install/load commands and actual frontend check; preserve the SDK preset command | No — Wave 0 | pending |

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
