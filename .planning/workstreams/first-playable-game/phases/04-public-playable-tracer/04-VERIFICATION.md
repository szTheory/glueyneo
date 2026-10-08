---
phase: 04-public-playable-tracer
verified: 2026-10-08T16:29:00Z
status: gaps_found
score: 3/5 roadmap truths verified
covered_files:
  - ".planning/workstreams/first-playable-game/REQUIREMENTS.md"
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
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-14-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-14-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-15-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-15-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-16-PLAN.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-16-SUMMARY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md"
  - ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md"
  - "docs/first-playable-build.md"
  - "include/glueyneo/glueyneo.h"
  - "src/chips/ym2610_candidate.cpp"
  - "src/chips/z80_candidate.c"
  - "src/instance.c"
  - "src/libretro/libretro_core.c"
  - "tests/chips/test_ym2610.c"
  - "tests/chips/test_z80.c"
  - "tests/fixture/test_public_guest.c"
  - "tests/libretro/callback_harness.c"
  - "tests/libretro/retroarch_smoke.py"
  - "tests/libretro/test_retroarch_smoke.py"
  - "tests/tools/check_phase04_validation_map.py"
  - "tests/tools/test_check_phase04_validation_map.py"
  - "tests/tools/test_verify_playable.py"
  - "third_party/chips/z80.h"
  - "tools/verify_playable.py"
covered_digest: "v3:sha256:e3903afb49c2c503294def5a767d09196ebc365d7e53f37ab5e7a6f5d3e823d6"
behavior_unverified: 0
overrides_applied: 0
decision_coverage:
  honored: 3
  total: 3
  not_honored: []
re_verification:
  previous_status: gaps_found
  previous_score: 3/5 roadmap truths verified
  gaps_closed:
    - "Plan 04-16 removes newline-containing private-path suffixes in both sanitizers; current qualification and frontend suites pass 23/23 and 27/27."
    - "The crosswalk predicate now requires one normalized controlled state; contradiction and normalization controls pass against a coherent temporary evidence map."
  gaps_remaining:
    - "T-04-11, T-04-15, T-04-18 and T-04-20 remain high/open by user direction."
    - "WR-06 is actionable: check_docs accepts contradictory Pending/unknown plus closure text, and current review evidence is not reconciled into the map."
    - "Actual pinned RetroArch behavior and frontend QUAL-03 load evidence remain unknown."
  regressions:
    - "A temporary document mutation reproduced check_docs accepting both frontend requirements as passing while also labeled Pending/unknown."
    - "The current validation-map suite fails 9/10 because WR-06 lacks reconciled evidence and provenance."
gaps:
  - truth: "Phase 04 security review has no unresolved high-severity disclosure threats."
    status: failed
    reason: "The current security register is blocked with four high/open findings: T-04-11, T-04-15, T-04-18 and T-04-20. Plan 04-16 regression suites pass, but the user explicitly directed that these threats stay open and block completion."
    artifacts:
      - path: ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md"
        issue: "The security status is blocked and threats_open is 4."
    missing:
      - "A future security disposition supported by independent evidence; do not close or accept these threats in this verification."
  - truth: "Documentation and validation gates reject contradictory frontend closure claims and reconcile every current review finding."
    status: failed
    reason: "WR-06 reproduces: check_docs accepts HOST-02 Pending; frontend QUAL-03 Pending; unknown; both requirements pass. The mutation suite runs 10 tests and fails 9; the direct checker exits 1 with WR-06 has no provenance source. The validation crosswalk lacks WR-06."
    artifacts:
      - path: "tools/verify_playable.py"
        issue: "The status check requires Pending and unknown substrings but does not reject conflicting pass/closed/complete claims."
      - path: "tests/tools/test_verify_playable.py"
        issue: "The false-closure mutation omits Pending, so it does not test mixed Pending/unknown and closure text."
      - path: ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md"
        issue: "WR-06 is recorded with source -, which the evidence gate rejects."
      - path: ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md"
        issue: "The current review crosswalk has no WR-06 row."
    missing:
      - "Reject contradictory frontend closure claims and add a mixed-status mutation test."
      - "Add WR-06 provenance and a matching crosswalk row; update mutation fixtures and rerun the evidence-map tests and direct gate."
advisory: []
human_verification:
  - test: "Observe the public fixture in actual pinned RetroArch 1.22.2 after the required materially changed functioning launch context is independently available."
    expected: "A fresh screenshot shows guest-produced pixels; no-input frames are stable; RIGHT changes guest state and output while LEFT does not reproduce that trace; content unload and normal exit succeed."
    why_human: "The prior attempt exited -6 before a screenshot, LaunchServices reported kLSNoExecutableErr, and the required changed launch context is unavailable. Native/callback evidence cannot establish actual frontend behavior."
---

# Phase 4: Public Playable Tracer Verification Report

**Phase Goal:** A maintainer can rebuild and run an original guest with visible, input-driven behavior through the ordinary native API and an actual pinned RetroArch build, while resolving the selected sound candidates' admission gates before full integration.
**Verified:** 2026-10-08T16:29:00Z
**Status:** gaps_found
**Re-verification:** Yes — after Plan 04-16 and fresh security/code-review audits.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A maintainer can rebuild the original rights-audited fixture, run it through a C consumer, and observe a guest-produced frame with checked dimensions, format, pitch, and bounds. | ✓ VERIFIED | Current owned-debug CTests public_guest_contract, public_guest_trace, sdk_fixture_write and sdk_provenance pass. |
| 2 | A C integrator can advance bounded frames with sampled input and owned buffers; controlled input changes guest/output and wrong-input controls fail. | ✓ VERIFIED | Current public_guest_contract, public_guest_trace, public_guest_negative_left and public_guest_negative_none tests pass. |
| 3 | A user can load, run, control and unload the fixture in an actual pinned macOS RetroArch build. | ? UNCERTAIN | Actual app launch, screenshot, input, unload and exit observations remain absent. No RetroArch app was launched during this verification. |
| 4 | A maintainer can reproduce passing admission evidence for the pinned Z80 and private-interface ymfm YM2610 candidates, including timing, continuation, isolation, failure containment and C linkage. | ✓ VERIFIED | Current owned-debug z80_admission_contract and ym2610_admission tests pass; source/state records and consumer evidence bound these claims to selected workloads. |
| 5 | An integrator can follow the clean-tree build/install/load procedure and identify tested and untested environment identities. | ? UNCERTAIN | The guide and identity list exist and the docs gate passes, but WR-06 makes its contradiction check incomplete and actual frontend load remains unknown. |

**Score:** 3/5 roadmap truths verified; 2 remain uncertain. The unresolved security and documentation-gate findings block phase completion.

### Re-verification Findings

- **Closed — newline redaction:** Both sanitizers remove the complete remaining diagnostic value after a private-root match. Current suites pass 23/23 qualification tests and 27/27 frontend contract tests.
- **Closed — exact crosswalk-state predicate:** The checker accepts one normalized controlled state matching its record. Targeted contradiction and normalization controls pass against a coherent temporary evidence map. The actual current evidence map still fails because WR-06 lacks provenance and a crosswalk row.
- **Blocking security gate:** The independent security artifact remains blocked with T-04-11, T-04-15, T-04-18 and T-04-20 high/open, as explicitly directed. This report does not close or accept them.
- **Actionable WR-06:** A temporary current-map mutation made check_docs accept the contradictory status “HOST-02 Pending; frontend QUAL-03 Pending; unknown; both requirements pass.” The current negative test only checks pass text without Pending/unknown.
- **Current review map is stale:** The latest review includes WR-06, but the validation crosswalk omits it and the disposition source is -. The evidence-map suite fails 9/10; the direct checker exits 1 with “WR-06 has no provenance source.”
- **Separate frontend evidence:** HOST-02 and frontend QUAL-03 remain Pending. No functioning changed launch context or direct app observation exists.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| tests/fixture, include/glueyneo/glueyneo.h, src/instance.c | Rights-audited source, ordinary native load/frame and guest-produced output | ✓ VERIFIED | Artifacts are substantive and wired through the generated fixture path; current consumer and provenance checks pass. |
| src/libretro/libretro_core.c, tests/libretro | Ordinary content/input/video/unload adapter and actual frontend path | ⚠️ PARTIAL | Callback and sanitizer tests pass; real pinned-app presentation and lifecycle remain unobserved. |
| src/chips, tests/chips and notices/inventories | Bounded Z80 and ymfm admission evidence | ✓ VERIFIED | Candidate tests pass for their documented workloads. |
| tools/verify_playable.py, tests/tools/test_verify_playable.py | Snapshot-bound qualification, private-safe diagnostics and truthful documentation gate | ✗ FAILED | Whole-value redaction passes, but WR-06’s mixed Pending/unknown closure mutation is accepted. |
| tests/tools/check_phase04_validation_map.py and its tests | Current review/threat evidence reconciliation | ✗ FAILED | Current review ID WR-06 lacks provenance/crosswalk data; 9/10 tests and the direct gate fail. |
| 04-SECURITY.md, 04-REVIEW.md, 04-REVIEW-DISPOSITION.md | Current audit evidence and dispositions | ⚠️ BLOCKED | Four high/open threats remain; WR-06 lacks evidence-map provenance. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Generated fixture | Native guest frame | CMake producer → gn_load → gn_frame | ✓ WIRED | Current fixture, trace and provenance checks pass. |
| Libretro content | Native frame/video callback | retro_load_game → gn_load; retro_run → gn_frame → video_refresh | ✓ WIRED / runtime unknown | Callback test passes; actual frontend was not run. |
| Pinned candidate sources | Admission criteria | Private adapters → tests/source checks → CTest/installed consumers | ✓ WIRED | Current candidate admission tests pass for declared workloads. |
| Qualification diagnostics | Retained logs/receipts/output | Command runner → redactor → receipt and output sinks | ✓ WIRED | 23-test suite covers newline paths through retained and printed sinks. |
| Frontend diagnostics | Sanitizer | Diagnostic/crash output → sanitizer → serialized result | ✓ WIRED | 27-test suite covers newline paths through diagnostic and crash sinks. |
| Review/disposition/crosswalk | Validation evidence gate | Current review → disposition records → controlled crosswalk comparison | ✗ PARTIAL | Exact state predicate exists, but current WR-06 lacks provenance/crosswalk data, so the evidence gate fails. |
| Frontend status | Documentation gate | Validation row → check_docs | ✗ PARTIAL | Required substrings are checked, but contradictory closure language is accepted. |

### Data-Flow Trace

| Artifact | Data | Source | Produces real data | Status |
|---|---|---|---|---|
| Native guest renderer | Pixels and guest marker | Guest instructions and board state in GNFX fixture | Yes; C consumer observes guest-produced pixels | ✓ FLOWING |
| Libretro video callback | Pixels | Native frame output | Real adapter buffer in callback test; frontend presentation unknown | ⚠️ Runtime unknown |
| Qualification receipt | Identity/status/output digest | Committed snapshot and build/test lanes | Yes; newline diagnostic suffixes are removed | ✓ FLOWING |
| Candidate admission | Cycle/sample and consumer results | Pinned sources and bounded tests | Yes for named candidate workloads only | ✓ FLOWING |
| Frontend requirement status | Pending/unknown disposition | Validation status row | Actual row is pending, but validator accepts conflicting claims | ⚠️ Validation incomplete |

### Requirements Coverage

| Requirement | Source plans | Description | Status | Evidence |
|---|---|---|---|---|
| TRAC-01 | 04-01, 03, 06–14 | Rebuild rights-audited original fixture | ✓ SATISFIED | Tracked generator, rights/oracle records, current fixture and provenance CTests. |
| TRAC-02 | 04-01, 02 | Native guest-produced software frame | ✓ SATISFIED | Bounded API and current guest contract test. |
| TRAC-03 | 04-01–03, 08 | Input trace changes guest/output; wrong-input controls fail | ✓ SATISFIED | Current RIGHT trace and LEFT/no-input controls pass. |
| HOST-02 | 04-02, 06, 08–10, 12–15 | Actual pinned RetroArch load/control/unload | ? NEEDS HUMAN / PENDING | No app launch, screenshot, input, unload or exit observation is available. |
| API-05 | 04-01 | Bounded frame API and ownership/timing/error semantics | ✓ SATISFIED | Public contract and current native frame tests. |
| SND-01 | 04-04, 06, 14 | Pinned Z80 admission for named synthetic workload | ✓ SATISFIED (bounded) | Current admission test passes; claims remain limited to the declared workload. |
| SND-02 | 04-05, 06, 14 | Pinned ymfm YM2610 behind private C API | ✓ SATISFIED (bounded) | Current admission test passes; no game-sound or silicon-fidelity claim. |
| QUAL-03 | 04-06–16 | Clean-tree build/install/load and environment identities | ? NEEDS HUMAN / PENDING | Procedure and identities are documented; actual frontend load is unknown and the contradictory-status gate is incomplete. |

All eight Phase 04 requirements appear in plan traceability; no orphaned requirement was found. The active ledger keeps HOST-02 and QUAL-03 Pending and limits SND-01/02 to bounded candidate admission.

### Decision Coverage

The decision-coverage gate found 3/3 trackable CONTEXT.md decisions honored; not_honored is empty. This gate does not affect status.

### Behavioral Spot-Checks

| Behavior | Command/evidence | Result | Status |
|---|---|---|---|
| Native guest and input trace | ctest --test-dir build/owned-debug --output-on-failure -R '^(public_guest_contract|public_guest_trace)$' | 2/2 passed | ✓ PASS |
| Wrong-input controls | ctest --test-dir build/owned-debug --output-on-failure -R '^(public_guest_negative_left|public_guest_negative_none)$' | 2/2 passed | ✓ PASS |
| Z80/YM2610 and callback seam | ctest --test-dir build/owned-debug --output-on-failure -R '^(ym2610_admission|z80_admission_contract|libretro_callback)$' | 3/3 passed | ✓ PASS |
| Fixture generation/provenance | ctest --test-dir build/owned-debug --output-on-failure -R '^(sdk_fixture_write|sdk_provenance)$' | 2/2 passed | ✓ PASS |
| Qualification tests | python3 tests/tools/test_verify_playable.py -v | 23/23 passed | ✓ PASS |
| Frontend diagnostic contract | python3 tests/libretro/test_retroarch_smoke.py -v | 27/27 passed | ✓ PASS |
| Docs gate on current evidence | python3 tools/verify_playable.py --check-docs | Exit 0 | ✓ PASS; does not catch WR-06 |
| WR-06 mixed-status control | Temporary Pending/unknown plus closure row passed to check_docs | Contradictory row accepted | ✗ FAIL |
| Review-map mutation suite | python3 tests/tools/test_check_phase04_validation_map.py -v | 10 tests run; 9 fail from WR-06 evidence mismatch | ✗ FAIL |
| Current validation evidence map | python3 tests/tools/check_phase04_validation_map.py | Exit 1: WR-06 has no provenance source | ✗ FAIL |
| Exact crosswalk mutation controls on coherent temporary map | Contradictory and normalized-state controls | 2/2 passed | ✓ PASS |
| Actual pinned RetroArch presentation/input/unload | Not run; app evidence remains null/unknown | No screenshot or app observation | ? SKIP — human/external prerequisite unavailable |

### Probe Execution

No phase-declared probe-*.sh paths were found in Plans 04-01 through 04-16 or their summaries; no shell probe was required.

### Test Quality Audit

| Test File | Linked Requirement | Disabled-only coverage | Circular expected-value generation | Assertion/evidence assessment |
|---|---|---|---|---|
| tests/fixture/test_public_guest.c | TRAC-01/02/03, API-05 | None identified | None identified | Guest state, frame bounds, pixels and positive/negative input traces have behavioral assertions. |
| tests/chips/test_z80.c | SND-01 | None identified | None identified | Candidate workload checks compare timing/bus/state behavior to documented expectations. |
| tests/chips/test_ym2610.c | SND-02 | None identified | None identified | Candidate behavior, isolation and consumer boundaries are covered for recorded inputs. |
| tests/libretro/test_retroarch_smoke.py | HOST-02, QUAL-03 | None identified | None identified | 27 active contract/privacy tests; they cannot prove actual RetroArch UX. |
| tests/tools/test_verify_playable.py | QUAL-03 | None identified | None identified | 23 active tests; missing mixed Pending/unknown plus closure mutation leaves WR-06. |
| tests/tools/test_check_phase04_validation_map.py | Evidence-map gate | None identified | None identified | 10 active tests; 9 currently fail before intended assertions due missing WR-06 evidence records. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| tools/verify_playable.py | 672–676 | Requires Pending/unknown substrings without rejecting conflicting completion language | 🛑 BLOCKER | Reproduced false-closure acceptance under WR-06. |
| tests/tools/test_check_phase04_validation_map.py | Fixture setup | Mutation fixtures do not reconcile the new WR-06 evidence row | 🛑 BLOCKER | 9/10 tests and the current direct gate fail. |
| tests/libretro/retroarch_smoke.py | 201 | Empty non-macOS crash-report snapshot | ℹ️ INFO | Intentional platform-specific empty snapshot; collection is macOS-only, not a runtime stub. |

No unreferenced TBD/FIXME/XXX debt markers were found in the modified implementation/test paths. Placeholder strings in the gate and negative tests are intentional controls.

### Advisory (New Scope, Unevidenced)

None. WR-06 and the current evidence-map failure have reproducible evidence; no other new-scope blocker was promoted.

### Human Verification Required

#### Pinned RetroArch public-fixture flow

**Test:** After a materially changed functioning launch context is independently confirmed, run the generated fixture in pinned RetroArch 1.22.2 and inspect a fresh screenshot, stable no-input frames, RIGHT movement, LEFT negative control, unload and normal exit.

**Expected:** Guest-produced pixels appear; no-input output remains stable; RIGHT changes guest state and visible output while LEFT does not reproduce that trace; content unload and normal exit complete. HOST-02 and frontend QUAL-03 remain Pending until these observations and identities exist.

**Why human:** The prior attempt exited -6 before a screenshot, LaunchServices returned kLSNoExecutableErr, and unified-log inspection was blocked. The required changed launch context is unavailable. Native/callback evidence cannot establish actual app behavior.

### Gaps Summary

The native tracer and bounded sound-candidate gates pass their current focused checks. Phase 04 is not achieved: four high disclosure threats remain open by explicit direction; WR-06 demonstrates that the docs gate can accept false frontend closure; and the latest review is not reconciled into the evidence map, whose mutation suite and direct gate fail. HOST-02 and frontend QUAL-03 remain human/external unknowns. No later Phase 5–7 criterion explicitly resolves these specific Phase 04 gates, so no gap is deferred.

---

_Verified: 2026-10-08T16:29:00Z_
_Verifier: the agent (gsd-verifier)_
