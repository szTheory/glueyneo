---
phase: 04-public-playable-tracer
verified: 2026-10-08T19:41:59Z
status: gaps_found
score: 3/5 roadmap truths verified
covered_files:
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-01-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-01-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-02-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-02-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-03-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-03-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-04-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-04-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-05-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-05-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-06-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-06-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-07-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-07-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-08-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-08-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-09-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-09-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-10-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-10-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-11-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-11-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-12-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-12-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-13-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-13-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-14-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-14-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-15-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-15-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-16-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-16-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-17-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-17-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-18-PLAN.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-18-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md
  - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/check_phase04_validation_map.py
  - tests/tools/test_check_phase04_validation_map.py
  - tests/tools/test_verify_playable.py
  - tools/verify_playable.py
covered_digest: "v3:sha256:6707191df09fee8af94dc03255094496f68ec9e7a7ba34fe57bb73e34e6e19e5"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/5
  gaps_closed: []
  gaps_remaining:
    - "Reserved high/open disclosure threats and unresolved independent security/review dispositions"
    - "T-04-34 medium/open and its pending independent post-fix disposition"
  regressions: []
gaps:
  - truth: "The reserved high-severity disclosure threats and unresolved independent review dispositions are resolved before Phase 04 acceptance."
    status: failed
    reason: "The current security register still records T-04-11, T-04-15, T-04-18, and T-04-20 as high/open by direction. The review disposition retains seven open findings, including CR-03 and carried warnings. The fresh clean review covered only the evidence-map checker and its mutation tests; it does not audit the sanitizer, qualification, or reserved disclosure-threat implementation scopes."
    artifacts:
      - path: .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md
        issue: "Four reserved high-severity disclosure threats remain open; security sign-off is blocked."
      - path: .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md
        issue: "Open dispositions remain without fresh independent review across their affected implementation scope."
      - path: .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW.md
        issue: "The latest clean review is expressly limited to the evidence-map checker and its mutation tests."
    missing:
      - "Independent security evidence and authorized disposition for each reserved high-severity threat."
      - "Independent post-fix review and disposition of T-04-34 and the affected carried review findings."
  - truth: "T-04-34 is independently resolved before Phase 04 acceptance."
    status: failed
    reason: "T-04-34 remains medium/open pending independent post-fix disposition. The 14-test suite validates the evidence gate but does not itself change this security disposition."
    artifacts:
      - path: .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md
        issue: "T-04-34 remains medium/open."
    missing:
      - "Independent post-fix review and explicit disposition of T-04-34."
human_verification:
  - test: "Run the public fixture in the pinned macOS RetroArch 1.22.2 build and observe a fresh screenshot, repeated no-input frames, RIGHT movement, LEFT negative control, content unload, and normal application exit."
    expected: "The app loads and presents guest-produced software pixels; no-input output stays stable; RIGHT changes the guest marker while LEFT does not; content unload and normal exit complete with frontend-owned pacing."
    why_human: "The recorded launch aborted with exit -6 before its first screenshot. The actual app, GUI presentation, controls, unload, and exit cannot be established by callback or runner-contract tests."
---

# Phase 04: Public Playable Tracer Verification Report

**Phase Goal:** A maintainer can rebuild and run an original guest with visible, input-driven behavior through the ordinary native API and an actual pinned RetroArch build, while resolving the selected sound candidates' admission gates before full integration.
**Verified:** 2026-10-08T19:41:59Z
**Status:** gaps_found
**Re-verification:** Yes — prior verification had structured gaps; failed security/review gates were rechecked and remain open.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A maintainer can rebuild the original public fixture from tracked, rights-audited source and assets, run it through a C consumer, and see a guest-produced software frame with checked dimensions, format, pitch, and bounds. | ✓ VERIFIED | `tests/fixture/public_guest.c` feeds the named CMake fixture target; `tests/fixture/test_public_guest.c` loads it through `gn_load` and checks guest-driven pixels and bounds. The fixture rights/oracle records are in `tests/fixture/ORACLE.md` and `tests/fixture/rights-manifest.json`. |
| 2 | A C integrator can advance a bounded frame with explicit sampled input and owned video/audio buffers, capacities, timing and produced-count semantics, progress/stop information, and actionable errors; controlled input changes the guest and visible output while wrong-input controls fail. | ✓ VERIFIED | `include/glueyneo/glueyneo.h` defines the bounded frame contract; `src/instance.c` implements checked buffers and progress. Current CTests `public_guest_contract`, `public_guest_trace`, `public_guest_negative_left`, and `public_guest_negative_none` pass. |
| 3 | A user can load, run, control, and unload the fixture in an actual pinned macOS RetroArch build with software video, documented controller mapping, and frontend-owned pacing. | ? UNCERTAIN | Actual pinned-app load, presentation, input, unload, and exit remain unobserved. The recorded app launch aborted with exit -6 before screenshot; GUI-free callback and runner tests do not establish this truth. |
| 4 | A maintainer can reproduce passing admission evidence for the pinned Z80 and private-interface ymfm YM2610 candidates, including source/state, timing, interrupt/bus, continuation/isolation, failure containment, and static/shared C-consumer gates. | ✓ VERIFIED | The scoped requirements ledger marks only the bounded SND-01 synthetic workload and SND-02 candidate admission complete. Current CTests `ym2610_admission`, `z80_admission_contract`, and five Z80 mutation controls pass. Recorded plan 04-06 evidence includes installed static/shared C consumers; this is candidate admission, not game sound or hardware fidelity. |
| 5 | An integrator can follow the clean-tree build/install/load procedure for the native library and libretro adapter on the selected macOS configuration and identify exact dependency, compiler, SDK, OS, architecture, and frontend identities plus untested configurations. | ? UNCERTAIN | `docs/first-playable-build.md` records the procedure and environment identities, and the qualification runner checks its documentation contract. Its actual frontend load lane remains unknown, so successful load on the pinned frontend is not established. |

**Score:** 3/5 roadmap truths verified; two remain uncertain and route to human evidence. The independent security/review blockers are reported separately below.

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/fixture/public_guest.c` | Tracked original guest and fixture recipe | ✓ VERIFIED | Substantive C guest produces the GNFX fixture; CMake names a single generated build artifact. |
| `tests/fixture/test_public_guest.c` | Native C consumer assertions | ✓ VERIFIED | Loads through the ordinary API and asserts state, output, boundary behavior, and controls. Four named native fixture CTests pass. |
| `include/glueyneo/glueyneo.h` and `src/instance.c` | Public bounded frame contract and implementation | ✓ VERIFIED | Declared ownership, formats, sizes, time/progress, errors, and checked buffer handling are connected to the native frame path. |
| `src/libretro/libretro_core.c` | Thin consumer forwarding input, video, and lifecycle | ✓ VERIFIED | Callback contract is linked to native frame advancement; `libretro_callback` passes. This does not prove actual RetroArch behavior. |
| `third_party/chips` Z80 and `third_party/ymfm` candidate sources | Pinned candidate admission behind bounded interfaces | ✓ VERIFIED | Candidate sources, evidence inventories, and admission tests are present; claims remain limited to the named synthetic workload and candidate. |
| `tools/verify_playable.py` and `docs/first-playable-build.md` | Clean qualification procedure and identity reporting | ⚠️ PARTIAL | Documentation and automated gates are substantive; actual pinned frontend load remains unknown. |
| Current security and review records | Complete independent closure for acceptance | ✗ FAILED | Reserved threats and review dispositions remain open; latest review covered one test file only. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Fixture CMake target | `gn_load` and owned guest execution | generated GNFX artifact consumed by native C test | ✓ WIRED | Native fixture tests pass and check guest-produced output. |
| `gn_advance_frame` | caller video/audio buffers and sampled input | `src/instance.c` frame path | ✓ WIRED | Contract and implementation align; named bounds/input tests pass. |
| Libretro callback | native frame API | callback forwards sampled input and frame output | ✓ WIRED | `libretro_callback` passes; actual frontend remains unobserved. |
| Qualification runner | pinned RetroArch process | identity-checked smoke lane and status receipt | ⚠️ PARTIAL | Runner/document contract is tested; app launch is unknown and was not retried. |
| Z80/YM2610 admission harnesses | pinned candidate implementations | candidate-specific tests and installed C consumers | ✓ WIRED | Named admission tests pass; evidence remains bounded to these candidate gates. |

## Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| Native fixture guest and renderer | guest coordinates / framebuffer | guest execution writes board state; renderer reads guest state | Yes | ✓ FLOWING |
| Native frame API | video output and produced counts | machine frame operation writes caller-owned buffers | Yes | ✓ FLOWING |
| Libretro callback | video/input | frontend callback input is forwarded to the native instance; output pixels are submitted through callback | Yes in callback harness | ✓ FLOWING; actual frontend observation remains human-only |
| Qualification evidence | frontend status | actual app observation or explicit unknown | No actual app result exists | ⚠️ UNKNOWN, correctly fail-closed |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Current security/evidence-map consistency and report uncertainty | `python3 tests/tools/check_phase04_validation_map.py` | Passed; preserves four high/open threats, T-04-34 medium/open, and Pending/unknown frontend state. | ✓ PASS |
| Evidence-map mutation cases | `python3 tests/tools/test_check_phase04_validation_map.py -v` | 14/14 passed. | ✓ PASS |
| Qualification/privacy regressions | `python3 tests/tools/test_verify_playable.py -v` | 23/23 passed. | ✓ PASS |
| GUI-free RetroArch runner contract | `python3 tests/libretro/test_retroarch_smoke.py -v` | 27/27 passed. | ✓ PASS |
| Documentation claim gate | `python3 tools/verify_playable.py --check-docs` | Passed. | ✓ PASS |
| Candidate source/state and installed linkage gates | `python3 tests/chips/check_z80_source.py`; `python3 tests/chips/check_ym2610.py source`; `python3 tests/chips/check_ym2610.py link --both-linkages` | Pinned source closures, license/state inventory, and static/shared installed C consumers passed. | ✓ PASS |
| Native guest, callback, and candidate admissions | `ctest --test-dir build/owned-debug --output-on-failure -R '^(public_guest_contract|public_guest_trace|public_guest_negative_left|public_guest_negative_none|libretro_callback|ym2610_admission|z80_admission_contract|z80_admission_mutation_cycle|z80_admission_mutation_bus|z80_admission_mutation_irq|z80_admission_mutation_continuation|z80_admission_mutation_instance)$'` | 12/12 passed. | ✓ PASS |
| Actual pinned RetroArch load, display, controls, and unload | Not run | User direction keeps this manual-only; no GUI launch was made. | ? HUMAN |

## Probe Execution

No conventional `scripts/*/tests/probe-*.sh` files were found, and the phase plans do not declare a runnable probe path. The GUI smoke remains human-only and was not substituted with a mock probe.

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TRAC-01 | 04-01, 04-03, 04-06, 04-08 | Rights-audited, reproducibly generated original fixture | ✓ SATISFIED | Fixture source, rights/oracle manifest, generator, and native consumer evidence. |
| TRAC-02 | 04-01, 04-02 | Guest-produced software frame through ordinary native API with checked bounds | ✓ SATISFIED | Native guest/frame implementation and passing contract CTest. |
| TRAC-03 | 04-01, 04-02, 04-03 | Fixed input trace and falsifying wrong-input controls | ✓ SATISFIED | RIGHT trace and LEFT/no-input controls pass. |
| HOST-02 | 04-02, 04-08, 04-15, 04-18 | Actual pinned RetroArch load, run, control, and unload | ? NEEDS HUMAN / PENDING | No fresh screenshot or actual app input/unload observation; launch previously aborted before screenshot. |
| API-05 | 04-01 | Bounded native frame ownership, timing, buffers, progress, and errors | ✓ SATISFIED | Header/implementation and boundary/canary tests. |
| SND-01 | 04-04, 04-06 | Pinned Z80 admission for named synthetic workload | ✓ SATISFIED | Candidate contract and cycle/bus/IRQ/continuation/instance regressions pass. |
| SND-02 | 04-05, 04-06 | Private C-interface ymfm YM2610 admission and installed consumers | ✓ SATISFIED | Candidate admission CTest passes; recorded static/shared C consumer evidence remains scoped to the candidate. |
| QUAL-03 | 04-06, 04-08, 04-15, 04-18 | Clean-tree build/install/load steps and selected macOS identities | ? NEEDS HUMAN / PENDING | Procedure and identities are documented; successful actual frontend load remains unknown. |

No additional requirement allocated to Phase 04 was found outside these eight IDs. Later phases do not explicitly take over these open Phase 04 acceptance gates, so none is deferred.

## Security and Review State

The security register still has `threats_open: 4`: T-04-11, T-04-15, T-04-18, and T-04-20 remain high/open by direction. T-04-34 remains medium/open pending independent post-fix disposition. The review disposition retains open findings, including CR-03 and carried warnings. The current review is clean, but its scope is only `tests/tools/check_phase04_validation_map.py` and `tests/tools/test_check_phase04_validation_map.py`; it does not independently review the sanitizer, qualification, or reserved threat implementation scope. Passing repository regressions validate the gates and regressions; they do not change security or review dispositions.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| None in the current Phase 04 verification-gate implementation files | — | No unreferenced debt marker or empty/stub implementation found; placeholder tokens occur only in intentional rejection tests/checkers. | ℹ️ Info | No additional code blocker found by the scoped scan. Open threat/review states remain independently blocking. |

### Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
|---|---|---:|---:|---:|---|---|
| `tests/tools/test_check_phase04_validation_map.py` | HOST-02, QUAL-03; current evidence gate | 14 | 0 | 0 | Value-level mutation assertions against copied current evidence | PASS |
| `tests/tools/test_verify_playable.py` | QUAL-03; docs and privacy gates | 23 | 0 | 0 | Value-level rejection/acceptance assertions | PASS |
| `tests/libretro/test_retroarch_smoke.py` | HOST-02, QUAL-03; GUI-free runner safeguards | 27 | 0 | 0 | Value-level parser, identity and fail-closed contract assertions | PASS |

**Disabled tests on requirements:** 0. **Circular patterns detected:** 0 in the current gate suites. **Insufficient assertions:** 0 for these scoped regressions; these tests do not prove actual RetroArch GUI behavior.

### Decision Coverage

Not evaluated: the installed decision-coverage query could not resolve a workstream `config.json`; no decision-coverage counts are claimed. Phase decisions D4-01 through D4-03 were manually cross-checked against fixture generation, input controls, and ordinary consumer paths; this is not a substitute for the unavailable gate.

## Human Verification Required

### Pinned RetroArch fixture flow

**Test:** In a functioning pinned RetroArch 1.22.2 macOS launch context, run the generated public fixture, capture a fresh screenshot, compare repeated no-input frames, exercise RIGHT and the LEFT negative control, unload content, and exit normally.
**Expected:** Guest-produced software pixels appear; no-input output remains stable; RIGHT changes the guest marker while LEFT does not; content unload and application exit complete under frontend-owned pacing.
**Why human:** The recorded app launch aborted with exit -6 before its first screenshot. Runner and callback tests cannot observe GUI presentation, actual app input, unload, or exit.

## Gaps Summary

The native public fixture, bounded frame API, controlled input behavior, and selected Z80/ymfm candidate admission are supported by current repository evidence. Phase 04 remains blocked because four reserved high-severity disclosure threats and T-04-34 remain open, the disposition ledger contains unresolved review items outside the scope of the latest clean two-file review, and the actual pinned RetroArch flow is unobserved. HOST-02 and the frontend portion of QUAL-03 remain Pending/unknown. No requirements or dispositions were changed by this verification.

---

_Verified: 2026-10-08T19:41:59Z_
_Verifier: the agent (gsd-verifier)_
