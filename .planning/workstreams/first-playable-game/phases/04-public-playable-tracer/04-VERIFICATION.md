---
phase: 04-public-playable-tracer
verified: 2026-10-08T13:16:16Z
status: gaps_found
score: 3/5 roadmap truths verified
covered_files:
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-01-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-01-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-02-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-02-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-03-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-03-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-04-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-04-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-05-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-05-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-06-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-06-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-07-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-07-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-08-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-08-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-09-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-09-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-10-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-10-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-11-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-11-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-12-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-12-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-13-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-13-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md"
  - "CMakeLists.txt"
  - "docs/first-playable-build.md"
  - "docs/public-content.md"
  - "docs/rights-inventory.md"
  - "experiments/owned_cpu/SUBSET.md"
  - "experiments/owned_cpu/cpu.h"
  - "experiments/owned_cpu/source-manifest.json"
  - "experiments/owned_cpu/state-inventory.json"
  - "include/glueyneo/glueyneo.h"
  - "src/chips/ym2610_candidate.cpp"
  - "src/chips/ym2610_candidate.h"
  - "src/chips/z80_candidate.c"
  - "src/instance.c"
  - "src/libretro/libretro_core.c"
  - "tests/chips/Z80-ADMISSION.md"
  - "tests/chips/check_ym2610.py"
  - "tests/chips/check_z80_source.py"
  - "tests/chips/test_ym2610.c"
  - "tests/chips/test_z80.c"
  - "tests/fixture/ORACLE.md"
  - "tests/fixture/check_fixture.py"
  - "tests/fixture/public_guest.c"
  - "tests/fixture/rights-manifest.json"
  - "tests/fixture/test_public_guest.c"
  - "tests/libretro/callback_harness.c"
  - "tests/libretro/retroarch_smoke.py"
  - "tests/libretro/test_retroarch_smoke.py"
  - "tests/owned_cpu/test_inventory.py"
  - "tests/tools/check_phase04_validation_map.py"
  - "tests/tools/test_check_phase04_validation_map.py"
  - "tests/tools/test_verify_playable.py"
  - "tools/owned_cpu/inventory.py"
  - "tools/verify_playable.py"
covered_digest: "v3:sha256:8a706825c780940852568a8b84cd1719bd51146eac1e2ec120a9946255b6422b"
behavior_unverified: 0
overrides_applied: 0
decision_coverage:
  honored: 3
  total: 3
  not_honored: []
re_verification:
  previous_status: gaps_found
  previous_score: 3/5
  gaps_closed:
    - "Plan 04-13 repaired the validation-map stale-ID regression; its five focused mutation tests and direct gate now pass."
    - "Plan 04-13 adds regression coverage for escaped JSON quotes and apostrophes through the qualification and frontend sanitizers and sinks."
  gaps_remaining:
    - "A new independent review reproduces raw-literal-quote path suffix disclosure; four high-severity threats remain open."
    - "The validation-map parser still rejects a valid informational IN finding (WR-04)."
    - "Actual pinned RetroArch behavior and frontend QUAL-03 remain unobserved."
  regressions:
    - "Independent review found the sanitizer still treats a literal quote in arbitrary diagnostic text as a trusted path boundary."
gaps:
  - truth: "Private filesystem paths are completely removed from retained and printed qualification/frontend diagnostics, and the security gate has no unresolved high-severity disclosure threats."
    status: failed
    reason: "The current independent review reproduces `failed status 7: \"/Users/synthetic/private\"tail/sensitive.bin\"` becoming `failed status 7: [user]tail/sensitive.bin\"` in both sanitizers. The suffix can reach retained/printed qualification output and frontend diagnostics. T-04-11, T-04-15, T-04-18 and T-04-20 remain high/open; the security verdict is blocked."
    artifacts:
      - path: "tools/verify_playable.py"
        issue: "redact() accepts the next syntactically escaped JSON quote as a boundary even though arbitrary diagnostic text may contain a raw quote inside a path."
      - path: "tests/libretro/retroarch_smoke.py"
        issue: "sanitize_diagnostic_text() has the same raw-literal-quote disclosure."
      - path: ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md"
        issue: "Four high-severity disclosure threats remain open and the security audit is blocked."
    missing:
      - "For arbitrary subprocess and crash text, redact from a private root through line end unless the source supplies an unambiguous parsed path field."
      - "Add raw-literal-quote regressions through both sanitizers and their retained/printed sinks, then obtain a fresh independent security audit."
  - truth: "The phase validation-map parser accepts reconciled current review IDs and severities, including valid informational findings, and rejects contradictory evidence."
    status: failed
    reason: "The current review identifies WR-04: parse_review_findings accepts only CR-/WR- headings and Critical Issues/Warnings sections. A valid IN- finding under Info is rejected as outside a severity section. Plan 04-13 fixed the stale historical-ID regression, but its mutation suite does not cover the newly reported Info grammar case."
    artifacts:
      - path: "tests/tools/check_phase04_validation_map.py"
        issue: "Current parser has no IN- identifier or Info section mapping."
      - path: ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW.md"
        issue: "WR-04 documents the reproducible parser coverage defect."
    missing:
      - "Parse IN- findings under Info severity and reconcile them with disposition/crosswalk records."
      - "Add a passing consistent-Info fixture and a failing inconsistent-severity control."
human_verification:
  - test: "Run the generated public fixture in the pinned RetroArch 1.22.2 build; inspect a fresh screenshot, stable repeated no-input frames, RIGHT movement, LEFT negative control, content unload, and normal application exit."
    expected: "Guest-produced software pixels appear; no-input output remains stable; RIGHT changes the guest marker and visible output while LEFT does not reproduce that trace; content unload and normal exit complete."
    why_human: "The retained actual-app attempt aborted with exit -6 before its first screenshot. Native and callback tests do not establish real frontend rendering, input mapping, or application lifecycle."
---

# Phase 04: Public Playable Tracer Verification Report

## Plan 04-15 Actual Frontend Observation

The launch precondition was not met: no materially changed functioning launch context is independently confirmed. The retained prerequisite evidence is the prior pre-screenshot exit `-6`, LaunchServices `kLSNoExecutableErr`, blocked unified-log inspection, and the current inventory showing no RetroArch window or process. RetroArch was not invoked. The focused smoke-script contract suite passed 26 tests, which provide no actual-app evidence. App/core/fixture identities are null because they were not independently established from current evidence. The current frontend claim is `unknown`; HOST-02 and frontend QUAL-03 remain Pending. The exact external prerequisite is a materially changed, functioning macOS launch context for the pinned RetroArch 1.22.2 executable, independently confirmed before any app observation.

FRONTEND-OBSERVATION-JSON-BEGIN
```json
{
  "changed_context_confirmed": false,
  "screenshot_captured": false,
  "stable_no_input_frames": null,
  "right_input_observed": null,
  "left_negative_control_passed": null,
  "content_unloaded": null,
  "normal_exit": null,
  "ordinary_native_content_load_observed": null,
  "guest_software_video_observed": null,
  "frontend_owned_pacing_observed": null,
  "controller_mapping_documented": true,
  "qual03_clean_source_build_install_load_documented": true,
  "qual03_exact_dependency_compiler_sdk_os_arch_frontend_identities_documented": true,
  "qual03_untested_configurations_documented": true,
  "app_identity": null,
  "core_identity": null,
  "fixture_identity": null,
  "frontend_claim": "unknown"
}
```
FRONTEND-OBSERVATION-JSON-END

**Phase Goal:** A maintainer can rebuild and run an original guest with visible, input-driven behavior through the ordinary native API and an actual pinned RetroArch build, while resolving the selected sound candidates' admission gates before full integration.

**Verified:** 2026-10-08T13:16:16Z
**Status:** gaps_found
**Re-verification:** Yes — after Plan 04-13 execution and the fresh independent security and code-review audits.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A maintainer can rebuild the rights-audited original fixture, run it through a C consumer, and observe a guest-produced software frame with checked dimensions, format, pitch, and bounds. | ✓ VERIFIED | `tests/fixture/public_guest.c`, `test_public_guest.c`, `ORACLE.md`, rights manifest and checker are present and connected through CMake. The retained latest owned-debug CTest result is 47/47, including the public guest contract, trace and negative controls. |
| 2 | A C integrator can advance bounded frames with explicit sampled input and owned video/audio buffers, capacities, timing and produced-count semantics, progress/stop information and actionable errors; controlled input changes guest/output and wrong-input controls fail. | ✓ VERIFIED | The public header and `src/instance.c` implement the frame contract; native trace and LEFT/no-input negative controls run through `public_guest_test`. The same generated GNFX artifact is consumed by native and libretro paths. |
| 3 | A user can load, run, control and unload the fixture in an actual pinned macOS RetroArch build with software video, documented mapping and frontend-owned pacing. | ? UNCERTAIN | Plan 04-15 could not satisfy its changed-functioning-context precondition and did not invoke RetroArch. The prior pinned launch aborted with exit -6 before a screenshot; no pixels, controls, unload or normal exit were observed. Callback-harness and GUI-free tests do not prove this truth. |
| 4 | A maintainer can reproduce passing admission evidence for the pinned Z80 and private-interface ymfm YM2610 candidates, including source/state audits, timing and bus behavior, continuation, isolation, contained C++ failures and static/shared C-consumer linkage. | ✓ VERIFIED | CTest includes Z80 and YM2610 admission paths; the pinned source/notice and state inventories, candidate wrappers, C tests and static/shared consumer checks are present. This verifies the declared candidate workloads only; it does not prove audible game sound, integration into the game machine or silicon fidelity. |
| 5 | An integrator can follow the clean-tree build/install/load procedure for native and libretro artifacts on selected macOS and identify tested/untested environment identities. | ? UNCERTAIN | The documented clean-source procedure, selected dependency/compiler/SDK/OS/architecture/frontend identities, and explicit untested configurations are present; the frontend load portion remains unobserved, so complete load qualification remains pending. |

**Score:** 3/5 roadmap truths verified; 2 remain uncertain.  
**Human verification:** pinned RetroArch behavior remains outstanding; gaps take precedence in the overall status.

### Plan Must-Haves and Artifacts

All 13 PLAN and SUMMARY files were read. Their artifacts were checked against the current source, CMake wiring, validation records and the later independent audit evidence. The 13 plans declare only the eight requirements listed below; no plan requirement was silently dropped. Plans 04-01, 04-03, 04-04, 04-05, 04-07 and 04-09 have substantive artifacts and wiring supporting their native fixture/provenance, bounded candidate, snapshot identity and coverage-metadata claims. The libretro callback bridge exists and is wired, but actual RetroArch behavior is unverified (04-02/04-08). Qualification receipts and repository-backed checks are implemented, but current sanitizer and review-parser defects fail 04-10 through 04-13's privacy/reconciliation claims. Plan 04-06's identities and clean build/install procedure are evidenced; its actual frontend load remains pending. Plan 04-11 receipt row binding is covered by the security register's closed T-04-23 entry; carried review row WR-03 remains explicitly open without a fresh disposition.

| Artifact group | Level 1: exists | Level 2: substantive | Level 3: wired | Result |
|---|---|---|---|---|
| Native fixture, public API, rights/oracle and CMake consumer (`tests/fixture/*`, `include/glueyneo/glueyneo.h`, `src/instance.c`) | Yes | Guest execution, rendering, bounds, expected trace and rights checks are implemented | Generated fixture feeds native C consumer and tests | ✓ VERIFIED |
| Libretro bridge and frontend smoke (`src/libretro/libretro_core.c`, `tests/libretro/*`) | Yes | Load/run/input/video/unload calls are implemented; smoke requires pinned app observations | Adapter calls ordinary native load/frame API; installed core/fixture are used by smoke runner | ⚠️ PARTIAL — application behavior unknown; sanitizer has CR-02 |
| Z80 and YM2610 candidates (`src/chips/*`, `tests/chips/*`, source notices/inventories) | Yes | Private adapters, test suites, source/license/state evidence and candidate gates exist | CMake admission tests and installed C-consumer checks are connected | ✓ VERIFIED for declared admission workloads |
| Qualification and validation (`tools/verify_playable.py`, `tests/tools/*`, `docs/first-playable-build.md`) | Yes | Snapshot/receipt validation and regression checks exist | Build lanes and evidence-map checker are wired | ✗ FAILED for raw-quote privacy and Info-finding parser cases |
| Owned CPU identity (`tools/owned_cpu/inventory.py`, `experiments/owned_cpu/*`) | Yes | Source/state/target compile evidence is substantive | CTest inventory gate consumes actual build commands | ✓ VERIFIED; latest retained result 47/47 |

The GSD artifact/key-link query helper in installed 1.16.0 returned `invalid` for these PLAN paths; therefore the artifact conclusions above come from direct source/build wiring inspection and the referenced retained test/audit evidence, not a claimed successful helper verdict.

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Fixture CMake producer | Native guest load/frame | Generated GNFX → `gn_load` → `gn_frame` | ✓ WIRED | `CMakeLists.txt`, public guest test and native instance source connect producer, load, guest execution and caller-owned pixels. |
| Libretro content | Native frame/video callback | `retro_load_game` → `gn_load`; `retro_run` → `gn_frame` → video refresh | ✓ WIRED / runtime unverified | Direct adapter calls are present. Actual pinned frontend did not reach screenshot. |
| Pinned Z80/ymfm source | Candidate admission | private adapter → tests and source checks → CTest/report | ✓ WIRED | CMake registers candidate admission paths and the installed C-consumer gate; claim remains bounded to selected workloads. |
| Qualification snapshot | Build/tests/receipt | committed archive → inventory → qualification lanes → receipt | ✓ WIRED / privacy gap | Source-snapshot and row binding exist; raw-literal-quote sanitization still exposes suffixes. |
| Review/security records | Evidence-map checker | parsed current review + dispositions + threat register | ⚠️ PARTIAL | Reconciled current/history case passes after Plan 04-13; current review's valid `IN-`/Info case still fails parser grammar (WR-04). |

### Data-Flow Trace

| Artifact | Data | Source | Produces real data | Status |
|---|---|---|---|---|
| Native guest renderer | frame pixels and guest marker | guest instructions and board state in the GNFX fixture | Yes; C consumer observes guest-produced pixels | ✓ FLOWING |
| Libretro video callback | frame pixels | native `gn_frame` output | Yes in adapter contract; actual frontend presentation unobserved | ⚠️ Runtime unknown |
| Qualification receipts | build identity, statuses and output digests | committed source snapshot and executed build/test lanes | Yes for repository lanes; private paths can leak through diagnostic text | ⚠️ PARTIAL |
| Candidate admission records | Z80/YM2610 results | pinned sources, bounded tests and installed C consumers | Yes for candidate workloads | ✓ FLOWING |

### Requirements Coverage

| Requirement | Source plans | Description | Status | Evidence |
|---|---|---|---|---|
| TRAC-01 | 04-01, 03, 06–08, 10–12 | Rebuild rights-audited original fixture | ✓ SATISFIED | Source, deterministic generator/checker, rights and oracle records; CMake consumers. |
| TRAC-02 | 04-01, 02 | Native guest-produced software frame | ✓ SATISFIED | Bounded API, guest-driven renderer, geometry/format/pitch/bounds assertions. |
| TRAC-03 | 04-01–03, 08 | Fixed input trace changes guest and output; wrong-input controls fail | ✓ SATISFIED | Native RIGHT trace plus LEFT/no-input controls. Actual frontend control mapping is separately pending under HOST-02. |
| HOST-02 | 04-02, 06, 08–10, 12–15 | Load/control/unload through actual pinned RetroArch | ? NEEDS HUMAN / PENDING | Plan 04-15 records `frontend_claim: unknown`: the changed functioning launch context is unavailable and no app was invoked; no screenshot or app/core/fixture identities are available. |
| API-05 | 04-01 | Bounded frame API and ownership/timing/error semantics | ✓ SATISFIED | Public contract and native behavioral tests. |
| SND-01 | 04-04, 06 | Pinned Z80 admission for selected workload | ✓ EVIDENCE PRESENT; workstream requirement still unchecked | Source/license/state and cycle/interrupt/bus/continuation/isolation gates; scope does not establish game workload. |
| SND-02 | 04-05, 06 | Pinned ymfm YM2610 subset behind private C API | ✓ EVIDENCE PRESENT; workstream requirement still unchecked | Source/state, timing/isolation/failure and static/shared C consumer evidence. No game sound claim. |
| QUAL-03 | 04-06–15 | Clean-tree native/libretro build/install/load procedure and identities | ? NEEDS HUMAN / PENDING | Documentation, environment identities and untested configurations are present, but actual frontend load remains unobserved; the load-dependent requirement predicate is false. |

Requirement allocation cross-check: REQUIREMENTS.md maps these same eight IDs to Phase 4, and every one appears in one or more plan frontmatter fields. There are no orphaned Phase 4 requirements. TRAC-01/02/03 and API-05 are checked in REQUIREMENTS.md; HOST-02, SND-01/02 and QUAL-03 remain unchecked/pending there, even where candidate evidence is present.

### Decision Coverage

The installed GSD decision-coverage gate found 3/3 trackable CONTEXT.md decisions honored by shipped artifacts; `not_honored` is empty. This gate is advisory and does not affect the verdict.

### Security, Review, Validation and State Evidence

- `04-SECURITY.md` records 32/36 threats closed and **four high-severity information-disclosure threats still open**: T-04-11, T-04-15, T-04-18 and T-04-20. Security status is `blocked`; Plan 04-13 regression coverage does not close them.
- The current `04-REVIEW.md` and disposition identify **CR-02 (critical) open** for raw-literal-quote path disclosure and **WR-04 (warning) open** because the checker rejects valid Info/IN findings. The disposition also carries WR-01, WR-02 and WR-03 open; CR-01 is fixed history.
- `04-VALIDATION.md` records the prior stale-ID reconciliation failure as resolved by Plan 04-13's 5 mutation tests and direct gate. It also records the remaining privacy threats, current frontend unknown, and WR-04; validation's passing checker case does not cover Info syntax.
- `STATE.md` reports 13/13 plans complete and Phase 04 incomplete pending independent audits and actual frontend evidence. Its current detail and Plan 04-13 summary agree. ROADMAP.md's overview/progress paragraphs still contain stale contradictory text saying 04-13 was unexecuted and must be rerun; the plan checklist and STATE.md say it executed. This report follows current source evidence and explicitly retains the fresh audit findings.

### Behavioral Spot-Checks

| Behavior | Evidence | Result | Status |
|---|---|---|---|
| Native fixture, guest trace and negative input controls | Latest retained `ctest --preset owned-debug --output-on-failure` in 04-12/04-13 evidence | 47/47 pass, including `public_guest_contract`, `public_guest_trace`, LEFT/no-input controls and inventory gate | ✓ PASS (retained result; not rerun here) |
| Plan 04-13 qualification privacy regression | 04-13 summary and 04-VALIDATION | 20/20 focused tests pass, but current CR-02 test demonstrates a separate raw-literal-quote case outside that coverage | ⚠️ Partial |
| Plan 04-13 frontend privacy regression | 04-13 summary and 04-VALIDATION | 26/26 GUI-free tests pass; they do not exercise a raw literal quote inside arbitrary text | ⚠️ Partial |
| Validation-map reconciliation | 04-13 summary and 04-VALIDATION | 5/5 mutation tests and direct gate pass for stale/fixed IDs; WR-04 Info grammar is not covered | ⚠️ Partial |
| Actual pinned RetroArch presentation/input/unload | Retained smoke evidence and current audit | Exit -6 before first screenshot; no qualifying observation | ? SKIP — human/frontend evidence required |

No server, GUI application or external service was started during this verification.

### Anti-Patterns and Quality Findings

| File | Pattern | Severity | Impact |
|---|---|---|---|
| `tools/verify_playable.py` | Arbitrary diagnostic text with raw quote after a private root can leave suffix visible | 🛑 BLOCKER (CR-02; T-04-11/T-04-15) | Private path disclosure reaches receipt/printed diagnostics. |
| `tests/libretro/retroarch_smoke.py` | Same raw-quote boundary assumption | 🛑 BLOCKER (CR-02; T-04-18/T-04-20) | Private path disclosure reaches frontend/crash diagnostics. |
| `tests/tools/check_phase04_validation_map.py` | Parser omits `IN-` and Info severity support | ⚠️ WARNING / failed plan truth (WR-04) | Valid current review outcome cannot pass evidence-map validation. |

No unreferenced TBD/FIXME/XXX markers or empty user-facing implementation stubs were identified in the covered implementation paths. The validation issue and disclosure issue are backed by the current independent review; no Step 9b deferral applies because later roadmap phases do not explicitly resolve these phase acceptance defects.

### Test Quality Audit

| Test area | Disabled-only coverage | Circular expected-value generation | Assertion/evidence assessment |
|---|---|---|---|
| Public fixture/native API | No skip markers found in the requirement-linked directories | No test generator imports the tested native path to write expected outputs | Behavioral value/control assertions are present; retained 47/47 CTest evidence covers the native contract. |
| Z80/YM2610 candidate admission | No skip markers found | Admission values are specified by candidate tests/source checks and consumer runs | Candidate evidence covers the declared synthetic workloads and static/shared linkage; it is not game sound or hardware truth. |
| Qualification/frontend/evidence-map tooling | No skip markers found | Test fixture-writing utilities do not generate their own asserted runtime output | Focused tests pass for covered cases, but current review reproduces the raw-quote leak and Info grammar gap; these are the blockers above. |

No circular-test or disabled-only requirement coverage was found in the scanned Phase 04 test directories. The current review findings take precedence over passing tests that do not exercise those inputs.

### Human Verification Required

#### Pinned RetroArch public-fixture flow

**Test:** Run the generated public fixture in the pinned RetroArch 1.22.2 build; inspect a fresh screenshot, stable repeated no-input frames, RIGHT movement, LEFT negative control, content unload and normal application exit.

**Expected:** Guest-produced software pixels appear; no-input output remains stable; RIGHT changes the guest marker and visible output while LEFT does not reproduce that trace; unload and normal exit complete.

**Why human:** The retained application attempt aborted before its first screenshot. Native tests and the callback harness cannot establish real frontend rendering, controller mapping or application lifecycle. HOST-02 and frontend QUAL-03 therefore remain unobserved and pending.

### Gaps Summary

The native fixture and bounded native API behavior are evidenced, as are the selected Z80 and ymfm candidate admission gates. Phase 04 is not achieved: the current independent review reproduces a private-path suffix disclosure and a validation-map parser gap; all four high-severity disclosure threats remain open. Actual pinned RetroArch behavior and the frontend portion of QUAL-03 are unobserved. Do not claim GUI behavior, close the admission/security gates by inference, or advance Phase 04 to complete.

---

_Verified: 2026-10-08T13:16:16Z_
_Verifier: the agent (gsd-verifier)_
