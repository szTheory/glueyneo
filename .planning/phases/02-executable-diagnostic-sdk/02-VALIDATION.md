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
| **Quick run command** | `ctest --preset sdk-debug -L sdk-contract --output-on-failure --no-tests=error` (02-01 explicitly registers this label in its counted tracer bootstrap) |
| **Full suite command** | `python3 tools/verify_sdk.py` (created in 02-06; wraps existing named CTest suites and required package lanes) |
| **Estimated runtime** | Not measured; measure focused feedback during 02-01 and full/baseline cost during 02-06 before setting limits |

---

## Sampling Rate

- **After every task commit:** Run the task's focused CTest suite plus its consequential mutation/failure control.
- **After every plan wave:** Run affected accumulated suites; run the full local entrypoint at the phase gate.
- **Before `$gsd-verify-work`:** The full local entrypoint and installed-consumer lanes must have current-revision results.
- **Max feedback latency:** Target at most 30 seconds for focused per-task suites after Wave 0 measurement; report actual duration and revise only from evidence.

---

## Per-Task Verification Map

Focused checks are registered by their owning plan before behavior implementation; the full aggregate and collector are created in 02-06. The Wave column names the actual creation owner rather than claiming all checks exist in Wave 0.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-02-01 | 02-02 | 2 | API-01 | T-02-06 | Opaque instance lifecycle; no ambient host services | Unit/source closure | `ctest --preset sdk-debug -L sdk-lifecycle --output-on-failure --no-tests=error` | ❌ owner wave | ⬜ pending |
| 02-02-02 | 02-02 | 2 | API-02 | T-02-04 | Checked lengths, bounded mappings and copy-on-load ownership | Boundary/unit | `ctest --preset sdk-debug -L sdk-media --output-on-failure --no-tests=error` | ❌ owner wave | ⬜ pending |
| 02-03-01 | 02-03 | 3 | API-03 | T-02-08 | Finite guest-cycle runs report accurate progress and stop/fault results | API integration | `ctest --preset sdk-debug -L sdk-run --output-on-failure --no-tests=error` | ❌ owner wave | ⬜ pending |
| 02-02-03 | 02-02 | 2 | API-04 | T-02-05 | Allocation/load failure preserves usable state and permits safe recovery | Fault/property | `ctest --preset sdk-debug -L sdk-faults --output-on-failure --no-tests=error` | ❌ owner wave | ⬜ pending |
| 02-01-01 | 02-01 | 1 | DIAG-01 | T-02-03 | Ordinary API computes named results from original diagnostic | Integration/consumer | `ctest --preset sdk-debug -L sdk-diagnostic --output-on-failure --no-tests=error` | ❌ owner wave | ⬜ pending |
| 02-03-02 | 02-03 | 3 | DIAG-02 | T-02-10 | Initialized data, BSS, bounded functional bus effects and targeted negative control | Runner/control | `ctest --preset sdk-debug -L sdk-controls --output-on-failure --no-tests=error` | ❌ owner wave | ⬜ pending |
| 02-03-03 | 02-03 | 3 | DIAG-03 | T-02-09 | Equal-boundary repeat/split and distinct interleaved/concurrent instances | Property/concurrency | `ctest --preset sdk-debug -L sdk-isolation --output-on-failure --no-tests=error` | ❌ owner wave | ⬜ pending |
| 02-04-01 | 02-04 | 4 | BUILD-01 | T-02-12 | Offline static/shared build closure with target-scoped C17 settings | Build | `python3 tests/consumers/check_package.py --suite build` | ❌ owner wave | ⬜ pending |
| 02-04-02 | 02-04 | 4 | BUILD-02 | T-02-13 | Relocated installed C consumers execute; public headers compile/link as C++ | Package integration | `python3 tests/consumers/check_package.py --suite consumers` | ❌ owner wave | ⬜ pending |
| 02-01-03/02-06-01 | 02-01/02-06 | 1/6 | EVID-01 | T-02-03/19 | Fixture and dependency provenance, rights, notices and recipe are auditable | Manifest/integrity | `ctest --preset sdk-debug -L sdk-provenance --output-on-failure --no-tests=error` | ❌ owner wave | ⬜ pending |
| 02-05-01/02 | 02-05 | 5 | EVID-02 | T-02-15/17 | Meaningful boundary, bounded hostile-input and supported sanitizer evidence | Boundary/fuzz/sanitizer | `ctest --preset sdk-debug -L sdk-mutation --output-on-failure --no-tests=error` plus `python3 tests/sdk/controls.py --sanitizers` | ❌ owner wave | ⬜ pending |
| 02-06-01 | 02-06 | 6 | EVID-03 | T-02-19 | Missing, malformed, zero-assertion and contaminated results fail closed | Collector controls | `ctest --preset sdk-debug -L sdk-evidence --output-on-failure --no-tests=error` | ❌ owner wave | ⬜ pending |
| 02-06-02 | 02-06 | 6 | EVID-04 | T-02-22 | Named-host diagnostic, memory/allocation, load and build baselines retain uncertainty | Measurement | `python3 tools/verify_sdk.py --suite baseline` | ❌ owner wave | ⬜ pending |
| 02-04-03 | 02-04 | 4 | DOC-01 | T-02-14 | Compiled example and invalid-input/failure-reproduction guide match the package | Consumer/documentation integration | `python3 tests/consumers/check_package.py --suite docs` | ❌ owner wave | ⬜ pending |
| 02-04-03 | 02-04 | 4 | DOC-02 | T-02-14 | Capability and exclusion statements match tested results | Contract/source evidence | `ctest --preset sdk-debug -L sdk-capabilities --output-on-failure --no-tests=error` | ❌ owner wave | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Bootstrap and Owning-Plan Requirements

- [ ] Public SDK Unity runners and focused CTest suites/labels for lifecycle, media, run, faults, diagnostics, controls, isolation, provenance, evidence and capabilities.
- [ ] SDK debug preset and explicitly registered sdk-contract/sdk-diagnostic tracer labels in 02-01; the single `tools/verify_sdk.py` aggregate follows in 02-06.
- [ ] 02-04 creates real out-of-tree consumers for static/shared installs and C++ public-header linkage before those checks.
- [ ] 02-01 seeds counted structured results; 02-06 creates the complete schema, manifest and fail-closed collector controls.
- [ ] 02-05 creates supported sanitizer and bounded hostile-input paths before running them; unsupported lanes are recorded explicitly.

---

## Manual-Only Verifications

All Phase 02 behavioral and package acceptance is planned for deterministic automated evidence. No human UAT is planned. If a required fixture right, external toolchain, or hardware claim cannot be established in this environment, record that narrow item as unknown/unsupported and continue independent work; do not substitute manual confirmation for a machine-checkable result.

---

## Validation Sign-Off

- [ ] Every planned task has an `<automated>` verification or explicit Wave 0 dependency.
- [ ] No three consecutive tasks lack automated verification.
- [ ] Each owning plan registers/creates its required suite before its first dependent behavior check.
- [ ] No watch-mode flags.
- [ ] Focused feedback latency is measured and reported; no uncalibrated threshold is claimed.
- [ ] `nyquist_compliant: true` set in frontmatter after validation.

**Approval:** pending
