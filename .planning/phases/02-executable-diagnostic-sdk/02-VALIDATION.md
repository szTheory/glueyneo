---
phase: "02"
slug: "executable-diagnostic-sdk"
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-06"
---

# Phase 02 — Validation Strategy

> Retrospective validation map for the completed Executable diagnostic SDK phase.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | C17 tests with pinned Unity, CTest registration, and Python standard-library supervisors |
| **Config file** | CMakePresets.json and CMakeLists.txt |
| **Quick run command** | `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-contract --output-on-failure --no-tests=error` |
| **Full suite command** | `python3 tools/verify_sdk.py` |
| **Estimated runtime** | A single full-gate wall time was not recorded. Incremental ASan+UBSan and TSan supervisors took about 0.87 s and 3.68 s, respectively; see 02-05-SUMMARY.md and 02-06-SUMMARY.md. |

## Sampling Rate

- Every task has a named automated verification command recorded below; plan summaries report the corresponding focused checks passing.
- The final aggregate command ran at Plan 02-06 and passed 63 lane executions with 1,154,951 assertions at source revision `814d7c4fa7e40841a3ae463705f354e5ee222b9a`.
- CTest and Python supervisor commands are one-shot; no watch-mode runner is used.
- Per-task maximum feedback latency was not consolidated into a single measurement.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | API-01, API-02, API-03, DIAG-01, DIAG-02 | T-02-01, T-02-02 | Validate and own diagnostic media; bound guest work and expose explicit failure results | integration | `cmake -S . -B build/sdk-debug -G Ninja -DGLUEYNEO_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Debug && cmake --build build/sdk-debug && ctest --test-dir build/sdk-debug -R '^sdk_diagnostic$' --output-on-failure --no-tests=error` | tests/sdk/test_sdk.c | ✅ green |
| 02-01-02 | 01 | 1 | EVID-03 | T-02-03 | Count named cases and assertions and retain child failures | integration | `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-contract --output-on-failure --no-tests=error` | tests/sdk/test_sdk.c | ✅ green |
| 02-01-03 | 01 | 1 | EVID-01, DIAG-01 | T-02-03, T-02-SC | Reproduce the lawful fixture and bind its output and dependency provenance | integration | `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L "sdk-provenance\|sdk-diagnostic" --output-on-failure --no-tests=error` | tests/sdk/guest_fixture.c; tests/sdk/ORACLE.md | ✅ green |
| 02-02-01 | 02 | 2 | API-01, API-04, DOC-01 | T-02-07 | Return bounded errors and preserve safe lifecycle behavior without exposing host details | integration | `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-lifecycle --output-on-failure --no-tests=error` | tests/sdk/test_sdk.c | ✅ green |
| 02-02-02 | 02 | 2 | API-02, EVID-02 | T-02-04, T-02-06 | Check lengths and spans before allocation; keep replacement transactional and instance-local | boundary | `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-media --output-on-failure --no-tests=error` | tests/sdk/test_sdk.c | ✅ green |
| 02-02-03 | 02 | 2 | API-04, EVID-02 | T-02-05, T-02-06 | Clean up every failed candidate and retain peer-instance state and recovery | fault injection | `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-faults --output-on-failure --no-tests=error` | tests/sdk/test_sdk.c; tests/sdk/test_support.h | ✅ green |
| 02-03-01 | 03 | 3 | API-03, DIAG-02 | T-02-08 | Bound requests and accounting; report actual guest progress | boundary | `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-run --output-on-failure --no-tests=error` | tests/sdk/test_sdk.c | ✅ green |
| 02-03-02 | 03 | 3 | DIAG-01, DIAG-03, EVID-03 | T-02-10, T-02-11 | Require exact failure identity, positive assertion counts, and bounded public observations | mutation/control | `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-controls --output-on-failure --no-tests=error && cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-diagnostic --output-on-failure --no-tests=error` | tests/sdk/controls.py; tests/sdk/test_sdk.c | ✅ green |
| 02-03-03 | 03 | 3 | API-01, EVID-02 | T-02-09 | Keep runtime state per instance and compare equal-boundary concurrent and cold instances | concurrency | `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-isolation --output-on-failure --no-tests=error` | tests/sdk/test_sdk.c; tests/sdk/controls.py | ✅ green |
| 02-04-01 | 04 | 4 | BUILD-01, BUILD-02 | T-02-12, T-02-SC | Build offline static and shared packages with only intended public exports | package build | `python3 tests/consumers/check_package.py --suite build` | tests/consumers/check_package.py | ✅ green |
| 02-04-02 | 04 | 4 | BUILD-01, BUILD-02, DIAG-01 | T-02-13 | Verify relocated C/C++ consumers load and call the moved installed package | integration | `python3 tests/consumers/check_package.py --suite consumers` | tests/consumers/check_package.py; tests/consumers/header.cpp | ✅ green |
| 02-04-03 | 04 | 4 | DOC-01, DOC-02 | T-02-14 | Compile guide examples, reproduce media errors, and preserve explicit capability limits | documentation/package | `python3 tests/consumers/check_package.py --suite docs && python3 tests/consumers/check_package.py --suite capabilities` | tests/consumers/check_package.py; examples/diagnostic.c | ✅ green |
| 02-05-01 | 05 | 5 | EVID-02, DIAG-03 | T-02-15, T-02-16 | Bound mutation inputs and work; require exact invariant and failure preservation | mutation | `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-mutation --output-on-failure --no-tests=error` | tests/fuzz/sdk_mutation.c; tests/fuzz/minimize.py | ✅ green |
| 02-05-02 | 05 | 5 | EVID-02, EVID-03 | T-02-17, T-02-18 | Instrument runtime paths and distinguish sanitizer startup from executed assertions | sanitizer/concurrency | `python3 tests/sdk/controls.py --sanitizers` | tests/sdk/controls.py; CMakePresets.json | ✅ green |
| 02-06-01 | 06 | 6 | EVID-01, EVID-04 | T-02-19, T-02-20, T-02-21, T-02-SC | Reject missing, stale, contaminated, or mismatched identity and evidence records | evidence controls | `python3 tools/verify_sdk.py --suite evidence && python3 tools/verify_sdk.py --suite provenance` | tests/sdk/test_evidence.py; tools/sdk_evidence.py | ✅ green |
| 02-06-02 | 06 | 6 | EVID-03 | T-02-22 | Retain raw samples and keep host timing, guest cycles, allocation, and unknown RSS distinct | measurement | `python3 tools/verify_sdk.py --suite baseline` | tools/sdk_baseline.py; tests/sdk/test_evidence.py | ✅ green |
| 02-06-03 | 06 | 6 | EVID-01, EVID-03, EVID-04, DOC-01, DOC-02 | T-02-19, T-02-20, T-02-21, T-02-SC | Require every mandatory lane and bind current-source evidence and public capability claims | aggregate | `python3 tools/verify_sdk.py` | tools/verify_sdk.py; evidence/sdk/verification.json | ✅ green |

## Wave 0 Requirements

Existing infrastructure and the in-phase CMake/CTest setup cover all phase requirements. No standalone Wave 0 gap or dependency installation was needed.

## Manual-Only Verifications

All Phase 02 requirements have automated verification. Original-silicon saved-PC behavior, other platform/compiler combinations, the CMake 3.20 floor, matching libFuzzer availability, and process RSS remain explicitly unknown or outside this phase's claims; they are not silently treated as passed.

## Validation Sign-Off

- [x] All tasks have automated verification commands
- [x] Sampling continuity: no task lacks an automated verify command
- [x] Wave 0 covers all MISSING references: no gaps were found
- [x] No watch-mode flags
- [ ] Feedback latency under 30 seconds: not established as a consolidated phase-wide measurement
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-10-06; phase evidence remains host- and configuration-specific as recorded in the summaries.
