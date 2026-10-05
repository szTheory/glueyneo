---
phase: "02"
slug: "executable-diagnostic-sdk"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-05"
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Existing pinned Unity with CTest; Python standard library may supervise evidence collection and controls |
| **Config file** | `CMakePresets.json` (SDK presets to be created in Wave 0) |
| **Quick run command** | `ctest --preset sdk-debug -L sdk-contract --output-on-failure --no-tests=error` (created in Wave 0) |
| **Full suite command** | `python3 tools/verify_sdk.py` (created in Wave 0; drives named CTest suites and required package lanes) |
| **Estimated runtime** | Not measured; establish from named host and workload during Wave 0 before setting limits |

---

## Sampling Rate

- **After every task commit:** Run the task's focused CTest suite plus its consequential mutation/failure control.
- **After every plan wave:** Run affected accumulated suites; run the full local entrypoint at the phase gate.
- **Before `$gsd-verify-work`:** The full local entrypoint and installed-consumer lanes must have current-revision results.
- **Max feedback latency:** Target at most 30 seconds for focused per-task suites after Wave 0 measurement; report actual duration and revise only from evidence.

---

## Per-Task Verification Map

Plan/task and threat IDs are assigned by the Phase 02 plans; every mapped check is created in Wave 0 before its behavior implementation.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| assigned by plan | TBD | 0 | API-01 | assigned by plan | Opaque instance lifecycle; no ambient host services | Unit/source closure | `ctest --preset sdk-debug -L sdk-lifecycle --output-on-failure --no-tests=error` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | API-02 | assigned by plan | Checked lengths, bounded mappings and copy-on-load ownership | Boundary/unit | `ctest --preset sdk-debug -L sdk-media --output-on-failure --no-tests=error` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | API-03 | assigned by plan | Finite guest-cycle runs report accurate progress and stop/fault results | API integration | `ctest --preset sdk-debug -L sdk-run --output-on-failure --no-tests=error` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | API-04 | assigned by plan | Allocation/load failure preserves usable state and permits safe recovery | Fault/property | `ctest --preset sdk-debug -L sdk-faults --output-on-failure --no-tests=error` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | DIAG-01 | assigned by plan | Ordinary API computes named results from original diagnostic | Integration/consumer | `ctest --preset sdk-debug -L sdk-diagnostic --output-on-failure --no-tests=error` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | DIAG-02 | assigned by plan | Initialized data, BSS, bounded functional bus effects and targeted negative control | Runner/control | `ctest --preset sdk-debug -L sdk-controls --output-on-failure --no-tests=error` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | DIAG-03 | assigned by plan | Equal-boundary repeat/split and distinct interleaved/concurrent instances | Property/concurrency | `ctest --preset sdk-debug -L sdk-isolation --output-on-failure --no-tests=error` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | BUILD-01 | assigned by plan | Offline static/shared build closure with target-scoped C17 settings | Build | `python3 tools/verify_sdk.py --suite build` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | BUILD-02 | assigned by plan | Relocated installed C consumers execute; public headers compile/link as C++ | Package integration | `python3 tools/verify_sdk.py --suite consumers` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | EVID-01 | assigned by plan | Fixture and dependency provenance, rights, notices and recipe are auditable | Manifest/integrity | `ctest --preset sdk-debug -L sdk-provenance --output-on-failure --no-tests=error` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | EVID-02 | assigned by plan | Meaningful boundary, bounded hostile-input and supported sanitizer evidence | Boundary/fuzz/sanitizer | `python3 tools/verify_sdk.py --suite hostile` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | EVID-03 | assigned by plan | Missing, malformed, zero-assertion and contaminated results fail closed | Collector controls | `ctest --preset sdk-debug -L sdk-evidence --output-on-failure --no-tests=error` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | EVID-04 | assigned by plan | Named-host diagnostic, memory/allocation, load and build baselines retain uncertainty | Measurement | `python3 tools/verify_sdk.py --suite baseline` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | DOC-01 | assigned by plan | Compiled example and invalid-input/failure-reproduction guide match the package | Consumer/documentation integration | `python3 tools/verify_sdk.py --suite docs` | ❌ W0 | ⬜ pending |
| assigned by plan | TBD | 0 | DOC-02 | assigned by plan | Capability and exclusion statements match tested results | Contract/source evidence | `ctest --preset sdk-debug -L sdk-capabilities --output-on-failure --no-tests=error` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Public SDK Unity runners and focused CTest suites/labels for lifecycle, media, run, faults, diagnostics, controls, isolation, provenance, evidence and capabilities.
- [ ] SDK debug preset plus `tools/verify_sdk.py` as the single local aggregate over named CTest and package-consumer lanes.
- [ ] Real out-of-tree consumer projects for static/shared installs and C++ public-header linkage.
- [ ] Machine-readable result schema, assertion counting and fail-closed collector controls.
- [ ] Supported sanitizer and bounded hostile-input path, with unsupported toolchain lanes recorded explicitly.

---

## Manual-Only Verifications

All Phase 02 behavioral and package acceptance is planned for deterministic automated evidence. No human UAT is planned. If a required fixture right, external toolchain, or hardware claim cannot be established in this environment, record that narrow item as unknown/unsupported and continue independent work; do not substitute manual confirmation for a machine-checkable result.

---

## Validation Sign-Off

- [ ] Every planned task has an `<automated>` verification or explicit Wave 0 dependency.
- [ ] No three consecutive tasks lack automated verification.
- [ ] Wave 0 creates every required suite before its first dependent behavior task.
- [ ] No watch-mode flags.
- [ ] Focused feedback latency is measured and reported; no uncalibrated threshold is claimed.
- [ ] `nyquist_compliant: true` set in frontmatter after validation.

**Approval:** pending
