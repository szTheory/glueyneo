---
phase: 02-executable-diagnostic-sdk
verified: 2026-10-06T15:10:43Z
status: passed
score: 5/5 must-haves verified
covered_files: [".planning/phases/02-executable-diagnostic-sdk/02-01-PLAN.md", ".planning/phases/02-executable-diagnostic-sdk/02-01-SUMMARY.md", ".planning/phases/02-executable-diagnostic-sdk/02-02-PLAN.md", ".planning/phases/02-executable-diagnostic-sdk/02-02-SUMMARY.md", ".planning/phases/02-executable-diagnostic-sdk/02-03-PLAN.md", ".planning/phases/02-executable-diagnostic-sdk/02-03-SUMMARY.md", ".planning/phases/02-executable-diagnostic-sdk/02-04-PLAN.md", ".planning/phases/02-executable-diagnostic-sdk/02-04-SUMMARY.md", ".planning/phases/02-executable-diagnostic-sdk/02-05-PLAN.md", ".planning/phases/02-executable-diagnostic-sdk/02-05-SUMMARY.md", ".planning/phases/02-executable-diagnostic-sdk/02-06-PLAN.md", ".planning/phases/02-executable-diagnostic-sdk/02-06-SUMMARY.md", "CMakeLists.txt", "CMakePresets.json", "README.md", "cmake/GlueyneoConfig.cmake.in", "docs/evidence-schema.md", "docs/ownership-and-errors.md", "docs/testing.md", "evidence/sdk/verification.json", "examples/diagnostic.c", "fixtures/diagnostic/manifest.json", "include/glueyneo/glueyneo.h", "src/instance.c", "src/sdk_private.h", "tests/consumers/CMakeLists.txt", "tests/consumers/check_package.py", "tests/consumers/header.cpp", "tests/fuzz/minimize.py", "tests/fuzz/regressions.json", "tests/fuzz/sdk_mutation.c", "tests/sdk/ORACLE.md", "tests/sdk/controls.py", "tests/sdk/guest_fixture.c", "tests/sdk/guest_fixture.h", "tests/sdk/test_evidence.py", "tests/sdk/test_sdk.c", "tests/sdk/test_support.h", "third_party/unity/LICENSE.txt", "third_party/unity/PROVENANCE.md", "third_party/unity/src/unity.c", "third_party/unity/src/unity.h", "third_party/unity/src/unity_internals.h", "tools/diagnostic/main.c", "tools/sdk_baseline.py", "tools/sdk_evidence.py", "tools/verify_sdk.py"]
covered_digest: "v3:sha256:3e30e6b9cdfd1ac4e424a62c32fa7e56fcd80d4100a1eee2bf498305eaafeebf"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 02: Executable Diagnostic SDK Verification Report

**Phase Goal:** As a C integrator, I want to install an offline SDK and run a meaningful original CPU/bus diagnostic through its ordinary native API and a headless runner, so that I can reproduce results with safe failures and clear evidence.
**Verified:** 2026-10-06T15:10:43Z
**Status:** passed
**Re-verification:** No — initial verification

## User Flow Coverage

| User story step | Expected outcome | Evidence in codebase | Status |
|---|---|---|---|
| Install the offline SDK | Static and shared C17 packages install without configure-time downloads and expose relocatable targets. | `CMakeLists.txt`, `cmake/GlueyneoConfig.cmake.in`, and the Phase 02 aggregate package-build lanes; source digest matches the receipt. | ✓ VERIFIED |
| Run the original diagnostic | An external C consumer and the headless runner exercise create/load/run/observe/destroy through the public API on the original fixture. | `tools/diagnostic/main.c`, `src/instance.c`, `tests/consumers/check_package.py`; recorded static/shared relocated-consumer results. | ✓ VERIFIED |
| Reproduce observations | Arithmetic, initialized data, BSS, cycle count, instruction count, stop reason, and PC are compared with named expectations and fixture/oracle identities. | `tests/sdk/ORACLE.md`, `fixtures/diagnostic/manifest.json`, and `evidence/sdk/verification.json`; fixture digest and output identities are recorded. | ✓ VERIFIED |
| Recover from invalid calls and media | Invalid lifecycle/media and allocation/load failures return statuses, clear outputs, preserve prior live state, and permit recovery or destruction. | `tests/sdk/test_sdk.c`; focused lifecycle/media/fault tests passed, including allocation-failure recovery. | ✓ VERIFIED |
| Inspect exact evidence and limits | Results contain source/build/input identities and counted outcomes; unsupported or unknown dimensions remain explicit. | `tools/sdk_evidence.py`, `tools/verify_sdk.py`, evidence schema and local receipt. | ✓ VERIFIED |
| Review runner output and recovery guidance | Installed output fields, schema, identity/path handling, malformed-media rejection, and recovery path are checked against compiled consumers and docs. | Completed `02-UAT.md`; current `sdk_package_consumers_static`, `sdk_package_consumers_shared`, `sdk_package_docs_static`, `sdk_package_docs_shared`, and `sdk_package_docs_readme` passed 5/5. | ✓ VERIFIED |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | An integrator can create/reset/destroy an opaque host-independent instance, load bounded copied diagnostic media, and recover safely from invalid sizes, unsupported profiles, lifecycle misuse, and allocation/load failures. | ✓ VERIFIED | Public API declarations in `include/glueyneo/glueyneo.h`; checked layout and bounded allocation in `src/instance.c`; focused lifecycle, media, and fault tests passed. Native source closure test passed. |
| 2 | External C consumers and the headless runner execute the same original guest through the ordinary API, reporting real bounded progress and justified CPU/data/BSS observations; wrong-behavior controls fail. | ✓ VERIFIED | `tools/diagnostic/main.c` and `examples/diagnostic.c` call the public lifecycle/run/observe API. Fixture bytes and oracle ancestry are documented. The recorded controls cover BSS, counters, stop status, byte order, and trace order; consumer receipts show static/shared execution. |
| 3 | Repeat/split execution and distinct instances match isolated baselines at equal boundaries, including interleaved/concurrent and cold creation/load/teardown paths; bounded mutation and supported sanitizers exercise runtime assertions. | ✓ VERIFIED | `tests/sdk/test_sdk.c`, `tests/sdk/controls.py`, `tests/fuzz/sdk_mutation.c`, and `tests/fuzz/regressions.json`; current focused isolation/cold CTests passed. Receipt records ASan+UBSan 8/8 and TSan 2/2, with 577,107 sanitizer assertions and disclosed unsupported coverage-guided fuzz/RSS dimensions. |
| 4 | Offline static/shared packages, relocated C consumers, C++ public-header consumers, and compiled documentation examples work and accurately state the supported subset and exclusions. | ✓ VERIFIED | Package configuration, consumer harness, compiled example, and README capability contract are wired in CMake and `tests/consumers/check_package.py`. The aggregate receipt records both package variants, relocation, C/C++ consumer assertions, and compiled docs. |
| 5 | Maintainers can audit fixture/dependency rights and oracle ancestry, reproduce source-bound machine-readable outcomes, and inspect named-host workload/allocation/build baselines with uncertainty and explicit unknowns. | ✓ VERIFIED | `fixtures/diagnostic/manifest.json`, `third_party/unity/PROVENANCE.md`, evidence schema/collector, baseline receipt, and aggregate gate. Baseline retains 31 samples and three cold builds; process RSS is explicitly unmeasured. |

**Score:** 5/5 roadmap truths verified; 0 behavior-dependent truths lack tests.

## Required Artifacts

All 19 PLAN-frontmatter artifact entries passed the artifact query (exists, substantive checks). Representative level-three wiring and data flow were then traced manually because several plan links use symbol descriptions rather than file paths and the generic key-link query cannot resolve those values.

| Artifact group | Expected | Status | Details |
|---|---|---|---|
| `include/glueyneo/glueyneo.h`, `src/instance.c`, `src/sdk_private.h` | Public opaque C contract, owned per-instance runtime and private test seam | ✓ VERIFIED | Implementations are substantive; CMake builds runtime from `src/instance.c` and the accepted private CPU source. Public API does not expose test hooks. |
| `tools/diagnostic/main.c`, `tests/sdk/guest_fixture.c`, `tests/sdk/ORACLE.md`, `fixtures/diagnostic/manifest.json` | Same original guest, reproducible fixture and documented provenance | ✓ VERIFIED | Runner creates the same fixture as the tests and reaches `gn_create`, `gn_load`, `gn_run`, `gn_observe`, and `gn_destroy`. Manifest binds rights, recipe, source and fixture digests, firmware status, and oracle ancestry. |
| `tests/sdk/test_sdk.c`, `tests/sdk/controls.py`, `tests/sdk/test_support.h` | Counted contract, exact controls, boundary and instance-isolation checks | ✓ VERIFIED | CTest registers named tests with required labels; test support records case/assertion counts and identities. |
| `tests/fuzz/sdk_mutation.c`, `tests/fuzz/minimize.py`, `tests/fuzz/regressions.json`, `docs/testing.md` | Bounded hostile input and call-sequence mutation, regression retention and sanitizer reporting | ✓ VERIFIED | Seeded finite runs and sanitizer lanes are wired to actual runtime targets; unsupported libFuzzer and RSS measurements are explicit. No new runtime regression was discovered in the recorded mutation runs. |
| `CMakeLists.txt`, `CMakePresets.json`, `cmake/GlueyneoConfig.cmake.in`, `tests/consumers/CMakeLists.txt`, `tests/consumers/check_package.py`, `tests/consumers/header.cpp` | Offline static/shared installs and real relocated C/C++ consumers | ✓ VERIFIED | Package checks configure/install separate prefixes, relocate them, inspect loader resolution and execute the diagnostic. |
| `examples/diagnostic.c`, `README.md`, `docs/ownership-and-errors.md`, `docs/evidence-schema.md` | Compiled integrator guides, failure reproduction and capability/evidence contracts | ✓ VERIFIED | Documentation lanes compile examples and exercise malformed-media recovery; claims exclude games, original BIOS, video/audio, public state and persistence compatibility. |
| `tools/sdk_evidence.py`, `tools/sdk_baseline.py`, `tools/verify_sdk.py`, `tests/sdk/test_evidence.py`, `evidence/sdk/verification.json` | Fail-closed evidence controls, measurements and complete local gate | ✓ VERIFIED | Current aggregate receipt records 63 lane executions and 1,154,987 assertions at implementation source revision `d060614`; its relevant-source digest is `52989a4180314c15bd2323cc3548e48169eb3f4e948ccf11154ab757b6dba905`. Later commits changed review/evidence records, not implementation sources. |
| `third_party/unity/LICENSE.txt`, `third_party/unity/PROVENANCE.md`, Unity sources | Pinned test-only dependency with license/provenance | ✓ VERIFIED | CMake links Unity only into test targets; manifest and identity bind the pinned revision and file digests. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `tools/diagnostic/main.c` | Public API in `src/instance.c` | create/load/run/observe/destroy | ✓ WIRED | Direct calls to each public operation; the runner does not use private CPU functions. |
| `src/instance.c` | `experiments/owned_cpu/cpu.c` | CMake runtime source and private bus/allocator callbacks | ✓ WIRED | `GLUEYNEO_RUNTIME_SOURCES` includes both C files; candidate image binds callbacks and allocator to the per-instance image. |
| Manifest input | CPU bus and public observations | copied ROM/RAM seed → zero-filled RAM → bus reads/writes → `gn_observe` | ✓ FLOWING | `gn_load` copies source bytes before return; CPU bus callbacks address owned region storage; observation values read the guest-written RAM. |
| Installed package metadata | Relocated external C/C++ consumers | `find_package` → imported target → moved-prefix loader | ✓ WIRED | The consumer harness moves installed prefixes and checks loaded shared-library identity; both variants and C++ headers are represented in the receipt. |
| Runtime/test results | Evidence collector and baseline | named outputs → identity/count validation → aggregate | ✓ WIRED | `tools/verify_sdk.py` requires named lanes and positive counters; evidence and baseline controls reject stale/missing/mismatched inputs. |
| Installed runner/docs | Diagnostic output and malformed-media recovery | consumer/schema/path checks → documented status/recovery contract | ✓ WIRED | The completed UAT row and current 5-case package/docs test run cover the former output-clarity checkpoint. |

The generic `verify.key-links` query returned false for all plan entries because their `from`/`to` fields contain symbol or descriptive names (for example, `gn_load`) rather than relative source paths. Manual traces above establish the actual connections; this is a limitation of the plan-link query, not an unwired artifact.

## Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces real data | Status |
|---|---|---|---|---|
| `tools/diagnostic/main.c` | Guest ROM and initialized RAM | Original word-array recipe in `tests/sdk/guest_fixture.c` | Yes; same deterministic fixture feeds the ordinary API and tests | ✓ FLOWING |
| `src/instance.c` | ROM/RAM and named observations | Caller bytes copied into owned allocations; guest CPU bus writes RAM; observation decodes RAM in explicit big-endian order | Yes; fixed-map guest execution, not static return values | ✓ FLOWING |
| `examples/diagnostic.c` and installed consumer | Result records | Calls installed library API and checks expected observations/run result | Yes; real relocated library and original fixture | ✓ FLOWING |
| `evidence/sdk/verification.json` | Lane outcomes and baseline samples | Actual test/consumer/sanitizer outputs, retained raw samples, host/build/source/input identities | Yes; source-bound receipt, with unsupported/unknown fields explicit | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command/result | Status |
|---|---|---|
| API diagnostic, lifecycle, bounded media, allocation faults, run accounting, instance isolation/cold lifecycle, and host-call closure | `ctest --preset sdk-debug -R '^sdk_(diagnostic|lifecycle|media|faults|run|isolation|cold|host_closure)$' --output-on-failure --no-tests=error` — 8/8 passed. | ✓ PASS |
| Evidence rejection controls | `python3 tools/verify_sdk.py --suite evidence` — 18 cases, 36 assertions passed at current source revision. | ✓ PASS |
| Fixture and dependency provenance | `python3 tools/verify_sdk.py --suite provenance` — 4 cases, 4 assertions and 2 fixture checks passed. | ✓ PASS |
| Baseline validation and current measurements | `python3 tools/verify_sdk.py --suite baseline` — 7 cases, 14 assertions passed; 31 samples and 3 cold builds; RSS explicitly unsupported/unmeasured. | ✓ PASS |
| Relocated consumers and documentation/recovery | `ctest --preset sdk-debug -R '^sdk_package_(consumers_(static|shared)|docs_(static|shared|readme))$' --output-on-failure --no-tests=error --parallel 1` — 5/5 passed at current checkout. | ✓ PASS |
| Current Phase 02 aggregate | `python3 tools/verify_sdk.py` receipt: 63 lane executions, 1,154,987 assertions, no failed lanes, source revision `d060614ead84b7a93e968fa5fab70647420df3c7`, relevant-source digest `52989a4180314c15bd2323cc3548e48169eb3f4e948ccf11154ab757b6dba905`. | ✓ PASS |
| Completed output/recovery UAT | `02-UAT.md` records 1 automated pass, 0 issues/pending/skipped/blocked; it cites installed output/schema/path and malformed-media recovery assertions. | ✓ PASS |
| User-directed Phase 01 regression result | `ctest --preset owned-debug` was reported as 12/13 passing; `owned_cpu_inventory_check` failed because the frozen Phase 01 source manifest marks `CMakeLists.txt` and `CMakePresets.json` stale after Phase 02 changes. This result is preserved as a known Phase 01 baseline limitation; the old manifest was not edited and Phase 01 verification was not rerun. | ⚠️ RECORDED FAILURE — outside Phase 02 acceptance |

## Probe Execution

Phase 02 declares exact sanitizer startup probes (02-05). The probe-bearing command was run in its own process and runs each exact compiler/runtime startup probe before its suite.

| Probe | Command | Result | Status |
|---|---|---|---|
| ASan+UBSan startup and SDK lane | `python3 tests/sdk/controls.py --sanitizers` → configure/build passed; `sdk_mutation --startup-probe asan-ubsan` exit 0 with 17 startup checks; focused runtime 8/8 passed, 577,077 assertions. | Probe and lane passed on AppleClang 21.0.0.21000101, Darwin arm64. | PASS |
| TSan startup and isolation/cold lane | Same command → configure/build passed; `sdk_mutation --startup-probe tsan` exit 0 with 18 startup checks; focused runtime 2/2 passed, 30 assertions, serialized. | Probe and lane passed on AppleClang 21.0.0.21000101, Darwin arm64. | PASS |

## Requirements Coverage

All 15 plan requirement IDs were cross-referenced with `.planning/REQUIREMENTS.md`; they are all assigned to Phase 02 and have supporting implementation and test/evidence paths.

| Requirement | Source plan(s) | Status | Evidence |
|---|---|---|---|
| API-01 | 02-01, 02-02 | ✓ SATISFIED | Opaque lifecycle, per-instance ownership, host-call closure, lifecycle/isolation checks. |
| API-02 | 02-01, 02-02 | ✓ SATISFIED | Bounded manifest validation, copied media, ownership and malformed-media boundary checks. |
| API-03 | 02-01, 02-03 | ✓ SATISFIED | Requested/elapsed/overshoot/instruction/stop/fault fields checked through the public run API. |
| API-04 | 02-02 | ✓ SATISFIED | Status errors, cleared outputs, allocation failpoint sweep, prior-image preservation and recovery. |
| DIAG-01 | 02-01, 02-03, 02-04 | ✓ SATISFIED | Original guest runs through ordinary API and out-of-tree static/shared C consumers. |
| DIAG-02 | 02-01, 02-03 | ✓ SATISFIED | Headless runner checks independent arithmetic/data/BSS and CPU/bus expectations; wrong-behavior controls are required to fail. |
| DIAG-03 | 02-03, 02-05 | ✓ SATISFIED | Equal-boundary repeat/split/interleaved/concurrent and cold lifecycle evidence, including TSan. |
| BUILD-01 | 02-01, 02-04 | ✓ SATISFIED | Offline C17 static/shared package lanes, target-scoped CMake and pinned test-only Unity. |
| BUILD-02 | 02-04 | ✓ SATISFIED | Relocated external C consumers for both variants and C++ public-header compile/link. |
| EVID-01 | 02-01, 02-06 | ✓ SATISFIED | Rights/notices, immutable dependency, source/recipe/output digests, firmware and oracle ancestry. |
| EVID-02 | 02-02, 02-03, 02-05 | ✓ SATISFIED | Boundary/lifecycle/property/mutation and supported sanitizer evidence; actual defects were not found, so no runtime regression seed was required. |
| EVID-03 | 02-01, 02-03, 02-05, 02-06 | ✓ SATISFIED | Named machine-readable records carry identities and counts with distinct pass/fail/skipped/unsupported/unknown outcomes. Open malformed-row robustness warning remains recorded below. |
| EVID-04 | 02-06 | ✓ SATISFIED | Named-host execution/load/allocation/cold-build samples and uncertainty; process RSS remains explicitly unmeasured. |
| DOC-01 | 02-02, 02-04, 02-06 | ✓ SATISFIED | Compiled getting-started, ownership/error, failure-reproduction and recovery examples match installed artifacts; current package/docs checks cover output fields and recovery guidance. |
| DOC-02 | 02-04, 02-06 | ✓ SATISFIED | Capability docs bound the CPU/bus subset and disclaim game/BIOS/video/audio/public state/persistence and broad platform claims. |

**Orphaned requirements:** None. Phase 02's roadmap requirement IDs exactly match the union of plan `requirements` fields.

## Anti-Patterns and Open Review Findings

No unreferenced `TBD`, `FIXME`, or `XXX` debt markers were found in the reviewed implementation files. WR-01 and WR-02 remain open in `02-REVIEW-DISPOSITION.md`; WR-03 is fixed by `d060614` and was independently re-reviewed. The two open warnings are disclosed and do not invalidate the tested default SDK flow.

| File | Line | Pattern/finding | Severity | Impact |
|---|---:|---|---|---|
| `tools/sdk_evidence.py` | 268, 551 | WR-01: validation sorts/reads row fields before confirming JSON list entries are objects; a valid JSON manifest/identity containing `null` can escape `EvidenceError` and produce an uncaught traceback. Existing malformed-evidence control covers truncated JSON, not this shape. | ⚠️ Warning (open) | Malformed evidence does not receive the intended stable structured error. Current valid evidence and the tested corruption controls still pass. |
| `CMakeLists.txt` | 58–64, 76–103 | WR-02: sanitizer compile instrumentation is applied to the public runtime archive, while static targets do not propagate sanitizer link flags to installed consumers. | ⚠️ Warning (open) | A static SDK installed from an instrumented sanitizer build may fail to link downstream without sanitizer runtime flags. Default static/shared package consumer lanes pass. |
| `tests/consumers/check_package.py` | fixed in `d060614` | WR-03: prior privacy checks only inspected portions of diagnostic output. The fix scans complete user-facing output, strengthens path patterns, and validates record/assertion field sets. | ℹ️ Resolved | Independent review confirmed the fix; current consumer/docs checks pass. |

## Human Verification Required

None. The former output/recovery item is covered by completed `02-UAT.md` plus current relocated-consumer, schema/path/privacy, malformed-media recovery, and documentation assertions. No residual manual evidence is required by the phase contract.

## Gaps Summary

No roadmap truth, required artifact, or requirement was found failed or unwired. The completed automated output/recovery UAT and current package/docs checks close the previous human-verification item. Phase 02's goal is supported by current implementation and evidence. The Phase 01 frozen-manifest regression remains visible as requested and is not silently treated as a Phase 02 failure. Two independent review warnings remain open: malformed evidence-row handling and sanitizer-instrumented static package linking; WR-03 is fixed and independently reviewed.

---

_Verified: 2026-10-06T15:10:43Z_
_Verifier: the agent (gsd-verifier)_
