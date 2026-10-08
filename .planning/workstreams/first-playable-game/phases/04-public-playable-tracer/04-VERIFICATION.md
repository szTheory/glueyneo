---
phase: 04-public-playable-tracer
verified: 2026-10-08T03:44:49Z
status: gaps_found
score: 3/5 roadmap truths verified
covered_files: [".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-01-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-01-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-02-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-02-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-03-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-03-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-04-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-04-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-05-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-05-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-06-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-06-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-07-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-07-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-08-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-08-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-09-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-09-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-10-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-10-SUMMARY.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-11-PLAN.md", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-11-SUMMARY.md", "tests/libretro/retroarch_smoke.py", "tests/libretro/test_retroarch_smoke.py", "tests/tools/check_phase04_validation_map.py", "tests/tools/test_verify_playable.py", "tools/verify_playable.py"]
covered_digest: "v3:sha256:b7b45a2b99c7a9722971a4d9f0387ea87e63ae49446d7905fd467bb112d365a1"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/5
  gaps_closed:
    - "The security audit now closes T-04-13 receipt/archive binding, T-04-16 fixture digest enforcement, and T-04-17 pinned bundle identity checks."
  gaps_remaining:
    - "T-04-11, T-04-15, and T-04-18 remain open, and current review reproduced path-suffix disclosure in both redactors."
    - "Actual pinned RetroArch behavior remains unknown; the prior run aborted before its first screenshot."
    - "The current validation-map checker still asserts superseded audit state and fails."
    - "The owned-debug CTest suite remains 46/47 because owned_cpu_inventory_check fails."
  regressions:
    - "A boolean bytes value passes repository-backed receipt row comparison as integer 1 (CR-01)."
    - "Comma-delimited unquoted private paths leave suffixes visible in both diagnostic redactors (CR-02)."
gaps:
  - truth: "Qualification receipt validation rejects malformed row values, and retained diagnostics remove complete private paths."
    status: failed
    reason: "Two current review blockers are reproducible in modified files. Python accepts bool as int, so bytes: true compares equal to a committed one-byte row after aggregate recomputation. Both redactors stop an unquoted path at a comma and leave the path suffix in output. The independent security audit closed T-04-13/T-04-16/T-04-17, but T-04-11/T-04-15/T-04-18 remain open; these current reproductions mean the security gate is not closed."
    artifacts:
      - path: "tools/verify_playable.py"
        issue: "validate_snapshot_record uses isinstance(byte_count, int) and equality permits True == 1; redact stops at comma delimiters."
      - path: "tests/libretro/retroarch_smoke.py"
        issue: "sanitize_diagnostic_text also stops at comma delimiters in valid unquoted paths."
      - path: "tests/tools/test_verify_playable.py"
        issue: "No exact-type regression currently rejects boolean numeric receipt fields."
      - path: "tests/libretro/test_retroarch_smoke.py"
        issue: "No regression currently proves full-path redaction for commas and other valid delimiters."
    missing:
      - "Require exact integer types for numeric receipt fields before comparison, including byte and row counts."
      - "Redact the full ambiguous unquoted path span, including temporary-root descendants, and add delimiter regressions to both test suites."
      - "Resolve all remaining high-severity path-disclosure threats and obtain a fresh independent security disposition."
  - truth: "Phase 04 validation tooling reflects current audit and review dispositions and passes against current evidence."
    status: failed
    reason: "Running python3 tests/tools/check_phase04_validation_map.py exits 1 at the assertion requiring threats_open: 6. The current security register has threats_open: 3, with T-04-13/T-04-16/T-04-17 closed and T-04-11/T-04-15/T-04-18 open. The checker also encodes obsolete review disposition assumptions."
    artifacts:
      - path: "tests/tools/check_phase04_validation_map.py"
        issue: "The declared evidence checker fails against the current security audit and current review dispositions."
      - path: ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md"
        issue: "Current audit state is blocked with three open threats, contradicting the checker's expected six-open state."
    missing:
      - "Reconcile checker assertions with current threat and review dispositions, preserving explicit blockers and unknowns."
      - "Rerun the exact focused suites and update the map only from observed current results."
  - truth: "The original fixture loads, runs, responds to input, presents software video, and unloads in the actual pinned RetroArch build."
    status: partial
    reason: "The pinned RetroArch 1.22.2 process aborted with status -6/SIGABRT before a screenshot. There is no observation of rendering, mapped input, unload, or normal exit; no GUI retry was made."
    artifacts:
      - path: "tests/libretro/retroarch_smoke.py"
        issue: "The real-app run did not reach the first screenshot or any observable frontend behavior."
      - path: "tests/libretro/callback_harness.c"
        issue: "The callback harness exercises the core contract but cannot establish real RetroArch behavior."
    missing:
      - "A successful actual pinned-app observation of screenshot, stable no-input frames, RIGHT movement, LEFT negative control, unload, and normal exit when an interactive app-launch context is available."
  - truth: "The Phase 04 owned-debug regression suite passes with the phase implementation and current source inventory."
    status: failed
    reason: "Fresh ctest --preset owned-debug --output-on-failure ran 47 tests; 46 passed and owned_cpu_inventory_check failed. It reports stale CPU identity/source-manifest entries and strict compile-command expectations."
    artifacts:
      - path: "tests/owned_cpu/check_inventory.py"
        issue: "The inventory checker rejects the current source identity, manifest, and compile-command configuration."
      - path: "experiments/owned_cpu/SUBSET.md"
        issue: "The checked CPU identity/source manifest does not match current tracked files and build commands."
    missing:
      - "Reconcile the owned CPU inventory and expected compile-command records with the current tree, then rerun the owned-debug CTest suite."
advisory: []
human_verification:
  - test: "Run the generated public fixture in the pinned RetroArch 1.22.2 build and inspect fresh screenshots, repeated no-input frames, RIGHT movement, the LEFT negative control, content unload, and normal application exit."
    expected: "The app remains alive and presents guest-produced software pixels; no-input frames are stable, RIGHT moves the guest marker, LEFT does not reproduce that trace, and unload and normal exit complete."
    why_human: "The retained attempt aborted before its first screenshot. Native and callback tests cannot verify actual frontend rendering, input mapping, or application lifecycle. The current environment has not materially changed, so the GUI run remains unknown."
---

# Phase 04: Public Playable Tracer Verification Report

**Phase Goal:** A maintainer can rebuild and run an original guest with visible, input-driven behavior through the ordinary native API and an actual pinned RetroArch build, while resolving the selected sound candidates' admission gates before full integration.

**Verified:** 2026-10-08T03:44:49Z  
**Status:** gaps_found  
**Re-verification:** Yes — after gap-only Plans 04-10/04-11 and the latest independent security and code-review audits.

## Goal Achievement

The public native fixture path and the two bounded sound-candidate admission paths still have implementation and test evidence. Current verification exposed receipt-type and redaction defects, the Phase 04 evidence-map checker fails against the latest audit state, and the full owned-debug suite has one reproducible inventory failure. The actual pinned RetroArch flow remains unknown. The phase goal is not achieved.

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A maintainer can rebuild the rights-audited original fixture, run it through a C consumer, and observe a guest-produced frame with checked geometry, format, pitch, and bounds. | ✓ VERIFIED | Current `owned-debug` CTest run passes `public_guest_contract`, `public_guest_trace`, `public_guest_negative_left`, and `public_guest_negative_none`; the fixture recipe, rights manifest, and oracle are tracked. The suite's separate owned-CPU inventory failure is recorded below. |
| 2 | A C integrator can advance a bounded frame with explicit sampled input and owned buffers, observe controlled guest/output changes, and reject wrong-input controls. | ✓ VERIFIED | The four public-guest CTest cases pass and assert frame metadata/bounds, guest state and pixel changes, and LEFT/no-input negative controls. |
| 3 | The fixture loads, runs, responds to input, presents software video, and unloads in the actual pinned macOS RetroArch build. | ? UNCERTAIN | The recorded RetroArch 1.22.2 process exited -6/SIGABRT before its first screenshot. No actual rendering, input, unload, or clean-exit observation exists. Callback tests do not prove frontend behavior. |
| 4 | The pinned Z80 and private-interface ymfm YM2610 candidates have reproducible admission evidence for their declared Phase 04 workloads before full integration. | ✓ VERIFIED | Current CTest passes all six `z80_admission*` cases and `ym2610_admission`; retained source/license inventories and the installed static/shared C-consumer admission report identify exact bounded workloads. These results do not claim game sound or physical-hardware fidelity. |
| 5 | An integrator can follow the clean-source native/libretro build, install and load procedure and identify the tested environment and untested configurations. | ? UNCERTAIN | The documented static/shared build and install procedures and environment identities are present. Actual frontend load is unobserved, so the complete build/install/load truth is not established. |

**Score:** 3/5 roadmap truths verified; 2 remain uncertain.  
**Human verification:** actual pinned RetroArch behavior remains outstanding.  
**Additional deterministic failures:** two security/code-review blockers, stale validation-map checker, and one failing owned-debug CTest.

## Re-verification Evidence

The previous report listed six open security threats and the actual frontend gap. The latest security audit closes T-04-13, T-04-16, and T-04-17, but leaves T-04-11, T-04-15, and T-04-18 open. Current code review also records CR-01 and CR-02 as open blockers. I reproduced both against current code:

| Check | Command or input | Result |
|---|---|---|
| Boolean byte-count receipt | In an isolated committed Git fixture, changed the one-byte row's `bytes` from integer `1` to boolean `true`, recomputed `inventory_sha256`, and called `validate_snapshot_record(..., repository=repo)`. | Accepted; defect reproduced. Python equality and `isinstance(bool, int)` permit the malformed row. |
| Qualification redaction | `/Users/alice/private,capture/secret.rom` in unquoted diagnostic text | Output retained `,capture/secret.rom` after `[user]`. |
| Frontend redaction | Same comma-delimited unquoted path through `sanitize_diagnostic_text` | Output retained `,capture/secret.rom` after `[user]`. |
| Validation-map check | `python3 tests/tools/check_phase04_validation_map.py` | Exit 1 at `threats_open: 6`; current security register reports three open threats. |
| Owned-debug CTest | `ctest --preset owned-debug --output-on-failure` | Exit 8; 46/47 passed. Only `owned_cpu_inventory_check` failed on stale CPU identity/source-manifest and strict compile-command expectations. |

No GUI retry was performed. The latest pinned-app evidence remains the prior pre-screenshot abort, and its outcome stays unknown.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/fixture/public_guest.c`, `tests/fixture/test_public_guest.c` | Original fixture and behavioral C consumer | ✓ VERIFIED | Tracked implementation; public fixture contract and trace/control tests pass. |
| `include/glueyneo/glueyneo.h`, `src/instance.c` | Bounded native API and guest-driven frame | ✓ VERIFIED | Native guest state flows to caller-owned pixels; public contract tests pass. |
| `src/libretro/libretro_core.c`, `tests/libretro/retroarch_smoke.py` | Adapter, real frontend smoke path | ⚠️ PARTIAL | Adapter is wired and callback CTest passes; pinned application behavior is not observed. Smoke redaction has a reproduced disclosure defect. |
| `src/chips/z80_candidate.c`, `tests/chips/test_z80.c` | Pinned bounded Z80 candidate and admission suite | ✓ VERIFIED | Current CTest admission cases pass; source/workload claim remains synthetic and bounded. |
| `src/chips/ym2610_candidate.cpp`, `tests/chips/test_ym2610.c` | Private C interface and candidate admission | ✓ VERIFIED | Current CTest passes; retained source, failure containment, deterministic behavior, and installed static/shared consumer evidence remain candidate-only. |
| `tools/verify_playable.py` | Snapshot receipt and diagnostic validation | ✗ FAILED | Current bool byte-count case is accepted; ambiguous comma paths leak suffixes. |
| `tests/tools/check_phase04_validation_map.py` | Current evidence-map gate | ✗ FAILED | Exact invocation exits 1 because assertions encode the superseded six-open security state. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Generated public fixture | Guest execution and native output frame | `gn_load` → guest board state → renderer → caller buffer | ✓ WIRED | Public fixture tests pass and assert pixel/state response. |
| Native frame/input | Libretro callbacks | Adapter forwards input and synchronously submits frame pixels | ✓ WIRED; app unknown | Callback contract passes, but actual RetroArch presentation/input/lifecycle remain unobserved. |
| Pinned Z80 | Per-instance adapter and admission tests | Private C adapter → CTest | ✓ WIRED | Six current CTest cases pass. |
| Pinned ymfm | Private C shim and installed C consumers | Opaque C API → static/shared library targets | ✓ WIRED | Current admission test and retained link report support candidate admission. |
| Committed Git source | Qualification snapshot receipt | Archive inventory → row validation | ⚠️ PARTIAL | Archive-derived row binding is present, but bool/int equality accepts a forged byte-count type. |
| Diagnostic path sources | Persisted or printed diagnostic text | Qualification/frontend redactors | ✗ FAILED | Both leave a comma-delimited private path suffix. |

### Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces real data | Status |
|---|---|---|---|---|
| `src/instance.c` | Guest marker position and pixel buffer | Executed fixture state and caller-owned output storage | Yes; covered by passing native fixture cases | ✓ FLOWING |
| `src/libretro/libretro_core.c` | Input sample and submitted frame | Frontend callback values and native frame result | Yes in callback harness; actual pinned frontend unavailable | ⚠️ FRONTEND UNKNOWN |
| `tools/verify_playable.py` | Receipt inventory rows | Bounded committed Git archive bytes | Yes, with malformed bool row accepted by equality | ⚠️ VALIDATION DEFECT |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Public fixture output/input controls | `ctest --preset owned-debug --output-on-failure` | Four `public_guest_*` tests pass | ✓ PASS |
| Z80 and YM2610 candidate admission | Same CTest invocation | Six Z80 cases and `ym2610_admission` pass | ✓ PASS |
| Actual pinned RetroArch flow | Existing recorded run | Exit -6/SIGABRT before first screenshot; not retried | ? UNKNOWN — human evidence required |
| Receipt boolean rejection | Isolated repository-backed reproduction | `bytes: true` accepted after aggregate recomputation | ✗ FAIL |
| Full diagnostic path removal | Direct redactor reproduction against both modules | Both leave `,capture/secret.rom` | ✗ FAIL |
| Validation-map consistency | `python3 tests/tools/check_phase04_validation_map.py` | Exit 1 at stale six-open threat assertion | ✗ FAIL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TRAC-01 | 04-01, 04-03, 04-07, 04-10, 04-11 | Rebuild original rights-audited fixture | ✓ SATISFIED | Tracked recipe/rights/oracle and passing public guest tests. |
| TRAC-02 | 04-01, 04-02 | Native C consumer observes guest-driven checked frame | ✓ SATISFIED | Public guest contract tests pass. |
| TRAC-03 | 04-01, 04-08 | Controlled input changes guest state/output; wrong controls fail | ✓ SATISFIED | RIGHT trace and LEFT/no-input controls pass. |
| HOST-02 | 04-02, 04-08, 04-09, 04-10 | Actual pinned RetroArch load, input, video and unload | ? NEEDS HUMAN | App aborts before screenshot; no actual frontend behavior observed. |
| API-05 | 04-01 | Bounded frame input/output/time/error contract | ✓ SATISFIED | Passing public guest contract tests cover buffers, metadata, input and errors. |
| SND-01 | 04-04 | Pinned Z80 admission for selected synthetic workload | ✓ SATISFIED, BOUNDED | Current admission cases pass; no private game workload claim. |
| SND-02 | 04-05 | Pinned ymfm YM2610 admission behind private C boundary | ✓ SATISFIED, CANDIDATE-ONLY | Current admission case and retained installed static/shared C linkage evidence pass. |
| QUAL-03 | 04-06, 04-07, 04-08, 04-10, 04-11 | Clean-source build/install/load procedure with environment identities | ? NEEDS HUMAN | Build/install evidence and identities exist; actual frontend load remains unobserved. |

All eight requirement IDs are allocated by the phase plans. No additional Phase 04 requirement mapping is orphaned.

### Behavioral and Test Quality Audit

The native guest and both sound candidates have active, passing behavior tests in the current CTest run. No disabled requirement-linked tests were identified in the reviewed Phase 04 suites. The Phase 04 validation-map checker itself is failing against the current audit state. Its assertion is deterministic and in scope because Plan 04-11 requires the checker to represent current audit and frontend gates accurately.

### Probe Execution

Not applicable. This phase is not a migration/tooling phase with declared `probe-*.sh` acceptance probes; its named tests and audit commands are recorded above.

### Decision Coverage

The installed decision-coverage gate reports 3/3 trackable Phase 04 context decisions honored by shipped artifacts.

### Advisory (New Scope, Unevidenced)

None. Re-verification findings that block are tied to carried-forward gaps, current changed files, or reproducible command/input evidence.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `tools/verify_playable.py` | 417 | `isinstance(bool, int)` plus equality accepts `bytes: true` for a one-byte file | 🛑 BLOCKER | Reproduced against repository-backed receipt validation. |
| `tools/verify_playable.py` | 490 | Redactor treats comma as a path terminator | 🛑 BLOCKER | Reproduced private path suffix disclosure. |
| `tests/libretro/retroarch_smoke.py` | 75 | Frontend redactor treats comma as a path terminator | 🛑 BLOCKER | Reproduced private path suffix disclosure. |
| `tests/tools/check_phase04_validation_map.py` | 119 | Checker requires superseded six-open audit state | 🛑 BLOCKER | Named checker exits 1 against current audit state. |
| `experiments/owned_cpu/SUBSET.md` and source inventory inputs | — | Stale source identity/manifest and compile-command expectations | ⚠️ WARNING | The owned-debug suite is 46/47; `owned_cpu_inventory_check` fails. |

No unreferenced `TBD`, `FIXME`, or `XXX` debt markers were found in the changed implementation and test files. The `return {}` in `crash_report_snapshot()` is the intentional empty result on non-macOS platforms and is not a stub.

## Human Verification Required

### Pinned RetroArch public-fixture flow

**Test:** Run the generated fixture in the identified pinned RetroArch 1.22.2 build; capture a fresh screenshot, compare repeated no-input frames, exercise RIGHT and LEFT controls, unload content, and quit normally.

**Expected:** Guest-produced software pixels appear; no-input output remains stable; RIGHT moves the guest marker; LEFT does not reproduce the trace; unload and normal exit complete.

**Why human:** The recorded app process aborted before its first screenshot. Native and callback tests cannot establish actual frontend rendering, input mapping, or process lifecycle. The GUI run remains unknown because the environment has not materially changed.

## Gaps Summary

Four deterministic gaps remain: receipt validation accepts a boolean byte count; two diagnostic redactors leak valid comma-delimited path suffixes while three high-severity path threats remain open; the Phase 04 validation-map checker fails because its expected security/review state is stale; and the owned-debug CTest suite has one stale CPU inventory failure. Separately, HOST-02 and the actual frontend portion of QUAL-03 remain unknown pending successful pinned-app observations. The native fixture and bounded Z80/YM2610 admission evidence do not resolve these gaps or establish broader game, BIOS, or hardware compatibility.

---
*Verified: 2026-10-08T03:44:49Z*  
*Verifier: the agent (gsd-verifier)*
