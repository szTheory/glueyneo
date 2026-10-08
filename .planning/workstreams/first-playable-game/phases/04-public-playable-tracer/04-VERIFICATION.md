---
phase: 04-public-playable-tracer
verified: 2026-10-08T12:11:12Z
status: gaps_found
score: 3/5 roadmap truths verified
covered_files: [".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-01-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-01-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-02-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-02-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-03-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-03-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-04-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-04-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-05-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-05-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-06-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-06-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-07-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-07-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-08-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-08-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-09-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-09-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-10-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-10-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-11-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-11-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-12-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-12-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md", "experiments/owned_cpu/SUBSET.md", "experiments/owned_cpu/cpu.h", "experiments/owned_cpu/source-manifest.json", "experiments/owned_cpu/state-inventory.json", "tests/libretro/retroarch_smoke.py", "tests/libretro/test_retroarch_smoke.py", "tests/owned_cpu/test_inventory.py", "tests/tools/check_phase04_validation_map.py", "tests/tools/test_check_phase04_validation_map.py", "tests/tools/test_verify_playable.py", "tools/owned_cpu/inventory.py", "tools/verify_playable.py"]
covered_digest: "v3:sha256:32637c212398673c77f3bcb1dc3573049dde97b3678b80e040b2de19af34a48a"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/5
  gaps_closed:
    - "Owned CPU identity and target-scoped compile evidence now pass the inventory check and full 47-test owned-debug CTest run."
    - "Exact integer checks reject boolean receipt counts; the focused tools suite passes 19 tests."
  gaps_remaining:
    - "Private diagnostic path redaction remains incomplete: escaped quotes expose path suffixes, with four high-severity threats open."
    - "The validation-map checker still fails its regression test when a repaired review finding is removed from reconciled current state."
    - "Actual pinned RetroArch behavior and the frontend portion of QUAL-03 remain unobserved."
  regressions:
    - "A new adversarial re-review reproduced escaped-quote path disclosure in qualification and frontend sanitizers, receipts, and printed output."
gaps:
  - truth: "Private filesystem paths are completely removed from retained and printed qualification/frontend diagnostics, and the security gate has no unresolved high-severity disclosure threats."
    status: failed
    reason: "A reproducible JSON-escaped quote in a private filename is treated as the quoted path boundary. Both sanitizers output `[user]tail/sensitive.bin\"`, so the suffix survives in diagnostics; the audit marks T-04-11, T-04-15, T-04-18, and T-04-20 high/open and SECURITY.md blocked."
    artifacts:
      - path: "tools/verify_playable.py"
        issue: "redact() uses the next matching quote as a boundary without JSON escape parsing."
      - path: "tests/libretro/retroarch_smoke.py"
        issue: "sanitize_diagnostic_text() repeats the same ambiguous quoted-boundary parsing."
      - path: ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md"
        issue: "Four high-severity information-disclosure threats remain open; security status is blocked."
    missing:
      - "For arbitrary subprocess/crash text, redact the remainder of the line unless a boundary is proven by a grammar with correct escape handling."
      - "Add escaped-double-quote and embedded-apostrophe regressions through both sanitizers, receipt persistence, and printed output; obtain a fresh independent audit."
  - truth: "Phase 04 validation tooling accepts reconciled current review IDs and dispositions and rejects contradictory evidence."
    status: failed
    reason: "The named regression test deterministically fails: `python3 -m unittest discover -s tests/tools -p 'test_check_phase04_validation_map.py' -v` exits 1 at check_phase04_validation_map.py:110 because the checker hardcodes `{CR-01, CR-02, WR-01}` although repaired CR-01 is absent from the current review. The direct checker also exits 1 at that assertion."
    artifacts:
      - path: "tests/tools/check_phase04_validation_map.py"
        issue: "Line 110 freezes the exact current finding-ID set; later assertions also require historical findings to stay open."
      - path: "tests/tools/test_check_phase04_validation_map.py"
        issue: "The reconciled-review regression fails against the current implementation."
    missing:
      - "Derive current findings and unresolved dispositions from reconciled review/disposition records, retaining historical rows without requiring stale IDs or states."
      - "Make the existing named regression pass and keep contradictory-record controls."
deferred:
  - truth: "Phase 05 selected MVS boot, private game media, and BIOS behavior."
    addressed_in: "Phase 5"
    evidence: "ROADMAP.md Phase 5 goal and success criteria explicitly cover selected private MVS media and BIOS/game boot."
  - truth: "Active Metal Slug X scene control and scrolling."
    addressed_in: "Phase 6"
    evidence: "ROADMAP.md Phase 6 goal and success criteria explicitly cover an active scene with movement, firing, graphics, and scrolling."
  - truth: "Representative game sound and private local scenario qualification."
    addressed_in: "Phase 7"
    evidence: "ROADMAP.md Phase 7 goal explicitly covers representative sound and separate private local qualification."
human_verification:
  - test: "Run the generated public fixture in the pinned RetroArch 1.22.2 build; inspect a fresh screenshot, stable repeated no-input frames, RIGHT movement, LEFT negative control, content unload, and normal application exit."
    expected: "Guest-produced software pixels appear; no-input frames are stable; RIGHT changes the guest marker and visible output while LEFT does not reproduce that trace; unload and normal exit complete."
    why_human: "The pinned process previously exited -6 before its first screenshot. Native and callback tests cannot establish actual frontend rendering, input mapping, or application lifecycle."
---

# Phase 04: Public Playable Tracer Verification Report

**Phase Goal:** A maintainer can rebuild and run an original guest with visible, input-driven behavior through the ordinary native API and an actual pinned RetroArch build, while resolving the selected sound candidates' admission gates before full integration.

**Verified:** 2026-10-08T12:11:12Z
**Status:** gaps_found
**Re-verification:** Yes — after Plan 04-12 gap closure and the fresh security and code-review audits.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A maintainer can rebuild the rights-audited original fixture, run it through a C consumer, and observe a guest-produced frame with checked geometry, format, pitch, and bounds. | ✓ VERIFIED | Current `ctest --preset owned-debug --output-on-failure` passed 47/47, including `public_guest_contract` and `public_guest_trace`; fixture source, rights, and oracle artifacts remain tracked. |
| 2 | A C integrator can advance bounded frames with explicit sampled input and owned video/audio buffers, timing and produced-count semantics, progress/stop information, and actionable errors; controlled input changes guest/output and wrong-input controls fail. | ✓ VERIFIED | The 47/47 CTest run includes public guest trace and LEFT/no-input negative controls; API/ownership/error contracts and installed consumer checks are present. |
| 3 | A user can load, run, control, and unload the fixture in an actual pinned macOS RetroArch build with software video, documented mapping, and frontend-owned pacing. | ? UNCERTAIN | The retained pinned RetroArch attempt exited -6 before its first screenshot. No actual video, input, unload, or normal exit has been observed; no GUI retry occurred. |
| 4 | A maintainer can reproduce the selected pinned Z80 and private-interface ymfm YM2610 admission evidence before full integration. | ✓ VERIFIED | Current CTest passes all Z80 admission and mutation cases plus `ym2610_admission`; 04-12 records source/state, deterministic behavior, isolation, failure containment and static/shared C-consumer evidence. This is bounded candidate evidence, not game sound or silicon fidelity. |
| 5 | An integrator can follow the clean-tree native/libretro build, install, and load procedure on the selected macOS configuration and identify exact tested and untested environment identities. | ? UNCERTAIN | Clean static/shared build and installed-consumer evidence and environment identities exist, but actual frontend load is unobserved, so the complete load procedure is not verified. |

**Score:** 3/5 roadmap truths verified; 2 remain uncertain.  
**Human verification:** actual pinned RetroArch behavior remains outstanding.

### Re-verification Evidence

The prior four findings were checked against current code rather than accepted from summaries. The boolean numeric-field defect is fixed: the 19-test tools suite passes and includes `test_repository_receipt_rejects_boolean_numeric_fields`. The owned CPU identity is also repaired: the direct inventory check passes and the complete owned-debug suite passes 47/47. The broader private-path truth remains failed because the review's escaped-quote case still reproduces. The validation-map gap remains failed on its targeted regression.

| Check | Command or input | Result |
|---|---|---|
| Full owned-debug regression | `ctest --preset owned-debug --output-on-failure` | Exit 0; 47/47 passed, including `owned_cpu_inventory_check`. |
| Qualification/privacy suite | `python3 -m unittest discover -s tests/tools -p 'test_verify_playable.py' -v` | 19/19 passed; this does not cover escaped quotes embedded in quoted path text. |
| Frontend/privacy suite | `python3 -m unittest discover -s tests/libretro -p 'test_retroarch_smoke.py' -v` | 25/25 passed; this does not cover escaped quotes embedded in quoted path text. |
| Owned CPU identity | `python3 tools/owned_cpu/inventory.py check --build-dir build/owned-debug` | PASS: 26 fields, 10 compiled source files, zero runtime mutable globals/callback owner mutations. |
| Escaped quote redaction | JSON encoding of synthetic `/Users/synthetic/private\"tail/sensitive.bin`, passed to both current sanitizers | Both return `failure: [user]tail/sensitive.bin\"`; private suffix remains. The input is synthetic and not a real user path. |
| Validation-map direct gate | `python3 tests/tools/check_phase04_validation_map.py` | Exit 1 at line 110: `current review IDs changed`. |
| Validation-map regression | `python3 -m unittest discover -s tests/tools -p 'test_check_phase04_validation_map.py' -v` | Exit 1; the one named test fails at line 110 for the reconciled state where repaired CR-01 is absent. |
| Security audit | Current `04-SECURITY.md` | 32/36 threats closed; T-04-11, T-04-15, T-04-18, T-04-20 remain high/open; status blocked. |
| Review disposition | Current `04-REVIEW-DISPOSITION.md` | 5/5 rows remain open, including repaired CR-01 and carried WR-02/WR-03. |
| Actual pinned frontend | Retained RetroArch attempt | Exit -6 before screenshot; unknown, not pass. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/fixture/public_guest.c`, `tests/fixture/test_public_guest.c` | Original fixture and behavioral C consumer | ✓ VERIFIED | Tracked source and rights/oracle records; public guest behavioral CTests pass. |
| `include/glueyneo/glueyneo.h`, `src/instance.c` | Bounded native API and guest-produced frame | ✓ VERIFIED | Native tests and static/shared installed consumers exercise frame/input contracts. |
| `src/libretro/libretro_core.c`, `tests/libretro/retroarch_smoke.py` | Adapter and actual frontend path | ⚠️ PARTIAL | Adapter callback test passes; actual application behavior remains unknown. Diagnostic sanitization leaks escaped-quote suffixes. |
| `src/chips/z80_candidate.c`, `tests/chips/test_z80.c` | Pinned bounded Z80 candidate and admission suite | ✓ VERIFIED | Current full CTest includes passing admission and mutation cases for the declared workload. |
| `src/chips/ym2610_candidate.cpp`, `tests/chips/test_ym2610.c` | Private C interface and candidate admission | ✓ VERIFIED | Current admission test and retained static/shared C-consumer evidence pass; no broad game-sound claim. |
| `tools/verify_playable.py` | Snapshot receipt and diagnostic validation | ⚠️ PARTIAL | Exact boolean checks and archive row binding pass focused regressions; escaped quoted private paths still leak suffixes. |
| `tests/tools/check_phase04_validation_map.py` | Current evidence-map gate | ✗ FAILED | Direct command and named reconciled-review regression fail at fixed current finding-ID assertion. |
| `tools/owned_cpu/inventory.py`, `experiments/owned_cpu/source-manifest.json` | Current owned CPU identity and target-scoped build evidence | ✓ VERIFIED | Direct inventory check passes; full CTest inventory gate passes. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Public fixture | Guest execution and native output frame | `gn_load` → guest state → renderer → caller buffer | ✓ WIRED | Public fixture CTests pass and verify pixels/state changes and boundaries. |
| Native frame/input | Libretro callbacks | Adapter forwards sampled input and submits native pixels synchronously | ✓ WIRED; app unknown | Callback CTest passes; this does not prove actual RetroArch behavior. |
| Pinned Z80 | Per-instance adapter and admission tests | Private C adapter → CTest | ✓ WIRED | Admission and mutation tests pass in current 47-test suite. |
| Pinned ymfm | Private C shim and installed C consumers | Opaque C API → static/shared library targets | ✓ WIRED | Candidate admission and consumer evidence pass. |
| Committed Git source | Qualification receipt | Archive inventory → exact row validation | ✓ WIRED | Archive-bound validation and forged-row regressions pass. |
| Diagnostic path sources | Persisted/printed diagnostic text | Qualification and frontend redactors | ✗ FAILED | JSON-escaped quote causes both implementations to stop early and retain private path suffix. |
| Current review/disposition | Evidence-map checker | Parsed review, dispositions, map and reconciled-state regression | ✗ FAILED | Hardcoded current ID set rejects the legitimate disappearance of repaired CR-01. |

### Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces real data | Status |
|---|---|---|---|---|
| `src/instance.c` | Guest marker and pixel buffer | Executed fixture state and caller-owned output | Yes; current public guest tests assert guest-produced output | ✓ FLOWING |
| `src/libretro/libretro_core.c` | Input sample and submitted frame | Frontend callbacks and native frame result | Callback harness exercises it; actual pinned frontend observation is absent | ⚠️ FRONTEND UNKNOWN |
| `tools/verify_playable.py` | Receipt inventory rows | Bounded committed Git archive bytes | Yes; exact archive rows are checked; unrelated diagnostic string path has a reproduced sanitizer defect | ✓ FLOWING / SECURITY GAP |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Native fixture frame and input controls | `ctest --preset owned-debug --output-on-failure` | `public_guest_*` tests pass in the 47/47 run | ✓ PASS |
| Z80/YM2610 candidate admission | Same CTest invocation | Z80 admission/mutation cases and `ym2610_admission` pass | ✓ PASS, BOUNDED |
| Owned CPU inventory | Same CTest invocation; direct inventory command above | Both pass against current compiler database | ✓ PASS |
| Actual pinned RetroArch flow | Existing app attempt | Exit -6 before first screenshot; no retry | ? UNKNOWN — human evidence required |
| Private-path redaction | Reproduced escaped quote against both sanitizers | Both leave `tail/sensitive.bin\"` visible | ✗ FAIL |
| Reconciled validation-map state | Named unittest and direct checker | Both fail at current finding-ID assertion | ✗ FAIL |

### Probe Execution

Not applicable: Phase 04 declares no migration/tooling `probe-*.sh` acceptance probe. The actual frontend smoke path is reported separately and remains unknown.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TRAC-01 | 04-01, 04-03, 04-07, 04-10–04-12 | Rebuild original rights-audited fixture | ✓ SATISFIED | Tracked recipe/rights/oracle and current passing guest tests. |
| TRAC-02 | 04-01, 04-02 | Native C consumer sees checked guest-driven frame | ✓ SATISFIED | Current public guest tests and installed C consumers pass. |
| TRAC-03 | 04-01, 04-08 | Controlled input changes output; wrong controls fail | ✓ SATISFIED | RIGHT trace and LEFT/no-input negative controls pass. |
| HOST-02 | 04-02, 04-08–04-10, 04-12 | Actual pinned RetroArch load, input, video, unload | ? NEEDS HUMAN | Existing process aborted before screenshot; actual behavior is unknown. |
| API-05 | 04-01 | Bounded frame/input/output/time/error contract | ✓ SATISFIED | Current CTest and consumer contract checks pass. |
| SND-01 | 04-04 | Pinned Z80 admission for declared workload | ✓ EVIDENCE PRESENT; REQUIREMENT PENDING | Candidate tests and source checks pass, but REQUIREMENTS.md remains unchecked pending phase admission. |
| SND-02 | 04-05 | Pinned ymfm subset behind private C boundary | ✓ EVIDENCE PRESENT; REQUIREMENT PENDING | Admission and static/shared linkage evidence pass; REQUIREMENTS.md remains unchecked pending phase admission. |
| QUAL-03 | 04-06–04-12 | Clean macOS build/install/load procedure and identities | ? NEEDS HUMAN | Build/install/consumer evidence and identities exist; actual pinned load remains unknown. |

No Phase 04 requirement allocation is orphaned; all eight IDs above are declared in the phase plans and workstream requirements.

### Decision Coverage

The installed decision-coverage gate's latest retained result reports 3/3 trackable Phase 04 context decisions honored. This is advisory and does not affect the verdict.

### Test Quality Audit

| Test File | Linked requirements | Active evidence | Disabled-only coverage | Circular | Verdict |
|---|---|---|---|---|---|
| `tests/fixture/test_public_guest.c` | TRAC-01/02/03, API-05 | Passing native behavioral CTests with exact frame/control assertions | None identified | None identified | Adequate for bounded fixture contract |
| `tests/chips/test_z80.c` | SND-01 | Passing admission and mutation cases in current CTest | None identified | None identified | Adequate for declared synthetic candidate workload |
| `tests/chips/test_ym2610.c` | SND-02 | Passing candidate admission; installed linkage report retained | None identified | None identified | Bounded candidate evidence; not game sound |
| `tests/tools/test_verify_playable.py` | TRAC-01, QUAL-03 | 19 active tests pass; quoted escaped filename case is missing | None identified | None identified | Incomplete privacy edge coverage; reproduced redaction defect |
| `tests/libretro/test_retroarch_smoke.py` | HOST-02, QUAL-03 | 25 active GUI-free tests pass; quoted escaped filename case is missing | None identified | None identified | Incomplete privacy edge coverage; GUI evidence remains unknown |
| `tests/tools/test_check_phase04_validation_map.py` | Phase evidence gate | One active test fails on reconciled review state | None identified | None identified | BLOCKER: checker does not accept current reconciled evidence |

No disabled-only requirement test or circular expected-value generation was identified in the reviewed paths. Passing tests do not establish actual frontend behavior or cover the reproduced escaped-quote case.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `tools/verify_playable.py` | 483–492 | Quoted path ends at the next quote without handling escapes | 🛑 BLOCKER | Synthetic JSON-escaped path leaves `tail/sensitive.bin` visible in retained/printed output. |
| `tests/libretro/retroarch_smoke.py` | 66–74 | Same ambiguous quoted-boundary parsing | 🛑 BLOCKER | Frontend/crash diagnostic path suffix disclosure. |
| `tests/tools/check_phase04_validation_map.py` | 110–156 | Exact historical finding IDs and open states are hardcoded | 🛑 BLOCKER | Reconciled review regression and direct gate fail. |
| `experiments/owned_cpu/SUBSET.md`, source/state inventory | — | Previously stale identity/compile evidence | Resolved | Current inventory check and CTest pass; no longer a phase gap. |

No unreferenced `TBD`, `FIXME`, or `XXX` markers were found in the reviewed implementation files. The platform-specific empty dictionary in `crash_report_snapshot()` and empty-list default in the inventory parser are intentional return/default paths, not stubs.

### Advisory (New Scope, Unevidenced)

None. Blocking findings are either carried forward or supported by the named failing regression/direct command and the reproduced sanitization output.

## Human Verification Required

### Pinned RetroArch public-fixture flow

**Test:** Run the generated fixture in the pinned RetroArch 1.22.2 build; capture a fresh screenshot, compare repeated no-input frames, exercise RIGHT and LEFT controls, unload content, and quit normally.

**Expected:** Guest-produced software pixels appear; no-input output remains stable; RIGHT moves the guest marker; LEFT does not reproduce that trace; unload and normal exit complete.

**Why human:** The recorded actual-app attempt exited -6 before its first screenshot. Native and callback tests cannot establish real frontend rendering, input mapping, or lifecycle.

## Gaps Summary

Two in-scope automated gaps remain: escaped quotes in otherwise valid private filenames bypass both diagnostic sanitizers and leave high-severity threats T-04-11/T-04-15/T-04-18/T-04-20 open; and the validation-map checker fails its regression for a reconciled current review. The earlier boolean-receipt and owned CPU inventory defects are fixed and verified by focused tests and the 47/47 full CTest run. HOST-02 and actual frontend QUAL-03 remain unknown pending a successful pinned-app observation. Native fixture behavior and bounded sound-candidate tests pass, but the unresolved security gate and frontend evidence prevent Phase 04 completion.

---

_Verified: 2026-10-08T12:11:12Z_
_Verifier: the agent (gsd-verifier)_
