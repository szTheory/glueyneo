---
phase: "02"
slug: "executable-diagnostic-sdk"
status: verified
threats_open: 0
asvs_level: 1
created: "2026-10-06"
---

# Phase 02 — Security

> ASVS L1 review of the threat mitigations declared in the Phase 02 plans.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| C integrator to SDK | Caller supplies handles, manifest descriptors, source buffers, run limits, and output structures | Pointers, lengths, fixed diagnostic mappings, bounded requests and results |
| SDK to CPU/bus diagnostic | The SDK owns per-instance CPU state and maps validated media to a bounded diagnostic bus | Guest reads/writes, instruction progress, cycle counts, status and named observations |
| Package producer to consumer | Installed targets, headers, runner, fixture and relocatable metadata cross an offline install prefix | Public symbols, CMake package files, fixture bytes and loader-resolved libraries |
| Evidence tools to local records | Verification scripts read manifests, lane output, identity records and baseline samples | Local source/build identities, case/assertion counts, failures, timing and allocation results |
| Pinned Unity dependency to test targets | Existing test-only dependency is compiled into test targets and not exported by the runtime package | Source revision, license/notice and test linkage |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-02-01 | Tampering | gn_load candidate | high | mitigate | Validate spans and caps before allocation; copy immutable seed and publish a complete candidate atomically (`src/instance.c`, `tests/sdk/test_sdk.c`) | closed |
| T-02-02 | Denial of service | gn_run | high | mitigate | Bound guest-cycle requests to 0..1,000,000 and report CPU failures (`src/instance.c`, `tests/sdk/test_sdk.c`) | closed |
| T-02-03 | Repudiation | diagnostic oracle | high | mitigate | Independent recipe/manual expectations, named counted assertions and fixture/output digests (`tests/sdk/ORACLE.md`, `tests/sdk/test_sdk.c`) | closed |
| T-02-04 | Tampering | media arithmetic/copy | high | mitigate | Checked subtraction/division, explicit resource caps and boundary tests before allocation (`src/instance.c`, `tests/sdk/test_sdk.c`) | closed |
| T-02-05 | Denial of service | candidate cleanup | high | mitigate | Sweep each allocation failure position and assert cleanup and recovery (`src/instance.c`, `tests/sdk/test_sdk.c`) | closed |
| T-02-06 | Tampering | instance ownership | high | mitigate | Keep stable instance-local userdata and use atomic replacement with peer-instance checks (`src/instance.c`, `tests/sdk/test_sdk.c`) | closed |
| T-02-07 | Information disclosure | error outputs | medium | mitigate | Zero bounded outputs and return statuses without host pointers or private paths (`include/glueyneo/glueyneo.h`, `src/instance.c`) | closed |
| T-02-08 | Denial of service | run accounting | high | mitigate | Bound requested work and check counters before event updates (`src/instance.c`, `tests/sdk/test_sdk.c`) | closed |
| T-02-09 | Tampering | trace/owner bindings | high | mitigate | Keep traces per image and compare distinct concurrent and cold owners (`tests/sdk/test_sdk.c`, `tests/sdk/controls.py`) | closed |
| T-02-10 | Repudiation | mutation supervisor | high | mitigate | Require exact failure IDs and values, one expected failure, positive denominators, and child-result validation (`tests/sdk/controls.py`) | closed |
| T-02-11 | Information disclosure | public observations | medium | mitigate | Expose named bounded observations; keep full CPU state and test hooks private (`include/glueyneo/glueyneo.h`, `CMakeLists.txt`) | closed |
| T-02-12 | Tampering | package exports | high | mitigate | Build separate offline prefixes; validate installed includes, public symbols, and corrupted-package controls (`CMakeLists.txt`, `tests/consumers/check_package.py`) | closed |
| T-02-13 | Spoofing | shared loader resolution | medium | mitigate | Inspect the loaded library identity and reject fallback to the original install (`tests/consumers/check_package.py`) | closed |
| T-02-14 | Information disclosure | exported config/docs | medium | mitigate | Use relocatable paths and scan package/docs outputs for source-path leakage (`tests/consumers/check_package.py`, `README.md`) | closed |
| T-02-15 | Tampering | media/sequence surfaces | high | mitigate | Run bounded seeded mutation with invariant checks, ASan/UBSan, and preserved regression identities (`tests/fuzz/sdk_mutation.c`, `tests/sdk/controls.py`) | closed |
| T-02-16 | Denial of service | mutation work | high | mitigate | Cap bytes, operations, instances, cycles, storage and subprocess time (`tests/fuzz/sdk_mutation.c`, `tests/fuzz/regressions.json`, `tests/sdk/controls.py`) | closed |
| T-02-17 | Tampering | independent concurrency | high | mitigate | Instrument actual runtime code and run owner-distinct concurrency under the supported TSan lane (`CMakeLists.txt`, `tests/sdk/controls.py`) | closed |
| T-02-18 | Repudiation | sanitizer coverage | medium | mitigate | Separate runtime startup probes from executed assertions; retain unsupported lanes as unknown (`tests/sdk/controls.py`, `docs/testing.md`) | closed |
| T-02-19 | Repudiation | evidence collector | high | mitigate | Require named lanes, identities and positive counts; exercise malformed, stale, and erased-failure controls (`tools/sdk_evidence.py`, `tests/sdk/test_evidence.py`) | closed |
| T-02-20 | Spoofing | source/artifact identity | high | mitigate | Compare relevant-source digest and dirty state with runtime, configuration and input identities (`tools/sdk_evidence.py`, `evidence/sdk/verification.json`) | closed |
| T-02-21 | Information disclosure | public records | high | mitigate | Use public-safe host classes and relative paths; reject private/environment contamination (`tools/sdk_evidence.py`, `tests/sdk/test_evidence.py`) | closed |
| T-02-22 | Tampering | baseline samples | medium | mitigate | Retain raw fixed-workload samples, uncertainty and sample counts; reject unexplained discards (`tools/sdk_baseline.py`, `tests/sdk/test_evidence.py`) | closed |
| T-02-SC | Tampering | fixture/dependency closure | high | mitigate | Add no runtime dependency; retain Unity pin, provenance and notice, and keep it test-only (`third_party/unity/PROVENANCE.md`, `CMakeLists.txt`, `tests/sdk/ORACLE.md`) | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open.*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (documented external owner).*

## Accepted Risks Log

No accepted risks.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-06 | 23 | 23 | 0 | Orchestrator, ASVS L1 plan-register check |

## Sign-Off

- [x] All threats have a disposition (mitigate)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed at `security_block_on: high`
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-06
