# Phase 02: Executable diagnostic SDK - Pattern Map

**Mapped:** 2026-10-05  
**Files analyzed:** 15 proposed file groups / representative paths  
**Analogs found:** 12 / 15 (role or partial matches; no exact public-SDK matches)

Scope comes from `02-CONTEXT.md` locked P02-C-01–18 and the Wave 0 gaps / deliverables in `02-RESEARCH.md`. Names below are proposed planning paths inferred from that research; the plan may choose concrete alternatives. Deferred ideas and `02-DISCUSSION-LOG.md` were not used. The repository currently has no public `include/`, `src/`, package export, out-of-tree consumer, SDK runner, or one-command SDK verification entrypoint.

## File Classification

| New/Modified File (proposed) | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `include/glueyneo/glueyneo.h` | provider / public API header | request-response | `experiments/owned_cpu/cpu.h` | role-match; private CPU surface only |
| `src/instance.c` | service / instance lifecycle | CRUD | `experiments/owned_cpu/cpu.c` | role-match; no media-owning instance exists |
| `src/diagnostic_bus.c` | service / memory and bus | transform | `tests/owned_cpu/isolation_fixture.h` | partial; test bus and ownership fixtures |
| `tools/diagnostic/main.c` | CLI runner | file-I/O, request-response | `tests/owned_cpu/test_diagnostic.c` | partial; test executable, not file-reading CLI |
| `fixtures/diagnostic/*` and fixture manifest | fixture / evidence | transform | `tests/cpu/guest_fixture.c`, `tests/cpu/ORACLE.md` | role-match |
| `tests/sdk/test_*.c` | test | CRUD, request-response | `tests/owned_cpu/test_faults.c`, `test_isolation.c` | role-match |
| `tests/consumers/{CMakeLists.txt,*.c,*.cpp}` | test / consumer | request-response | `experiments/owned_cpu/CMakeLists.txt` | partial; no installed consumer analog |
| `CMakeLists.txt`, `cmake/GlueyneoConfig.cmake.in`, `CMakePresets.json` | config / package | transform | root `CMakeLists.txt`, `experiments/owned_cpu/CMakeLists.txt` | partial; no install/export pattern |
| `tools/verify_sdk.py` | tooling / local entrypoint | batch | `tools/owned_cpu/contract.py` | role-match for CLI/evidence validation, not SDK aggregation |
| machine-readable result schema and collector (e.g. `tools/diagnostic/results.py`) | tooling / evidence | batch | `tools/owned_cpu/contract.py` | partial; no SDK result schema |
| bounded fuzz harnesses under `tests/fuzz/` | test | transform | `tests/owned_cpu/test_faults.c` | partial; no fuzzer target/harness exists |
| `docs/getting-started.md`, ownership/error and capabilities docs | documentation | request-response | `README.md`, `tests/cpu/ORACLE.md` | partial |
| baseline protocol/results under `docs/` or `evidence/` | evidence | batch | `tests/cpu/ORACLE.md` | partial; no cost-baseline protocol/result artifact |
| `third_party/unity/PROVENANCE.md` (retain/update only if files change) | provenance/config | file-I/O | `third_party/unity/PROVENANCE.md` | exact for existing Unity pin |
| SDK regression tests for package relocation / static/shared / C++ header linkage | test | request-response | no tracked analog | none |

Tracked-source gate: every analog named in this map was checked with `git ls-files -- <path>` and is tracked. No install/runtime mirrors are referenced.

## Pattern Assignments

### `include/glueyneo/glueyneo.h` (public API header, request-response)

**Analog:** `experiments/owned_cpu/cpu.h` (lines 1–99)

This is the closest shape for fixed-width C declarations, opaque handles, enums and bounded run results, but it is explicitly a private backend interface. Do not copy the public CPU register observation or allocator-callback API; P02-C-03 keeps allocation callbacks private and P02-C-07 keeps full CPU state private.

**Header and opaque handle pattern** (lines 1–11, 44–47):
```c
/* SPDX-License-Identifier: MIT */
#ifndef GLUEYNEO_OWNED_CPU_H
#define GLUEYNEO_OWNED_CPU_H

#include <stddef.h>
#include <stdint.h>

typedef struct owned_cpu owned_cpu;
```

**Bounded result pattern** (lines 18–29):
```c
typedef struct {
    owned_cpu_status reason;
    uint64_t requested_cycles;
    uint64_t elapsed_cycles;
    uint64_t overshoot_cycles;
    uint64_t instructions;
    uint32_t pc;
    uint32_t fault_pc;
    uint16_t instruction_register;
} owned_cpu_run_result;
```

Public header must add documented C++ linkage guards and expose only the instance, media descriptor, bounded outcomes, and named diagnostic observations. Those have no current public-header analog.

### `src/instance.c` and `src/diagnostic_bus.c` (services, CRUD and transform)

**Analogs:** `experiments/owned_cpu/cpu.c` (private core implementation) and `tests/owned_cpu/isolation_fixture.h` (test bus/machine ownership). Both tracked. The former establishes backend cycle/error behavior; neither owns immutable source media, implements transactional replacement, or supplies the public instance lifecycle.

**Bus callback shape** (from `experiments/owned_cpu/cpu.h`, lines 31–40):
```c
typedef struct {
    void *userdata;
    int (*read16)(void *userdata, uint32_t address, uint16_t *value);
    int (*write16)(void *userdata, uint32_t address, uint16_t value);
} owned_cpu_bus;
```

**Failure and lifecycle precedent** (`tests/owned_cpu/test_faults.c`, lines 11–39):
```c
TEST_ASSERT_EQUAL(OWNED_CPU_UNSUPPORTED_MODEL,
                  owned_cpu_create(UINT32_C(68020), bus, allocator, &cpu));
TEST_ASSERT_NULL(cpu);
TEST_ASSERT_FALSE(iso_machine_create_with_failure(&machine, 0u, 1u));
TEST_ASSERT_NULL(machine.cpu);
TEST_ASSERT_EQUAL_UINT(0u, machine.live_allocations);
```

Carry forward explicit checked bounds, complete cleanup, and error-return conventions. New code needs a candidate-image transaction and owned copied media; no existing analog proves replacement rollback or source-buffer release safety.

### `fixtures/diagnostic/*` and fixture manifest (fixture, transform)

**Analogs:** `tests/cpu/guest_fixture.c` (lines 1–10) and `tests/cpu/ORACLE.md` (lines 1–40).

**Fixture construction** (`guest_fixture.c`, lines 4–9):
```c
void guest_fixture(uint8_t rom[512], unsigned scenario, int mutate) {
 const uint8_t program[]={0x70,7,0x56,0x80,0x23,0xc0,0,0,0x10,0,0x4e,0x72,0x27,0};
 memset(rom,0,512); rom[2]=0x20; rom[6]=1;
 memcpy(rom+0x100,program,sizeof(program));
 if(scenario) {rom[0x101]=11; rom[0x102]=0x5a; rom[0x109]=4;}
 if(mutate) rom[0x101]++;
}
```

**Oracle/provenance pattern** (`ORACLE.md`, lines 3–5, 14–29, 38–40): state original-work/license and firmware needs; derive outcomes from instruction encodings and primary manual citations; state timing exclusions and uncertainty; name the mutated behavior and exact expected failed assertion. Phase 02 must extend, not silently replace, this recipe with initialized RAM/BSS and named bus observations. Hash exact fixture/output bytes and preserve the recipe and manual ancestry in its manifest. The proposed extended guest values remain unexecuted in RESEARCH.md, so derive/verify them before freezing expected results.

### `tests/sdk/test_*.c` (tests, CRUD/request-response)

**Analogs:** `tests/owned_cpu/test_faults.c` (lines 11–69), `tests/owned_cpu/test_diagnostic.c` (lines 64–134), and `tests/owned_cpu/test_isolation.c` (lines 14–32, 35–100).

Use Unity setup/teardown, named tests, exact error/status and state assertions, and output explicit assertion/case denominators. The diagnostic analog checks guest result and execution boundary; faults cover invalid input/allocation/lifecycle and leak counts; isolation computes independent baselines then compares named boundaries. Extend to native instance/media semantics rather than linking tests straight to the CPU backend. The test analogs do not substitute for independent installed consumers.

### `tools/diagnostic/main.c` and result collector (CLI, file-I/O / batch)

**Analogs:** `tests/owned_cpu/test_diagnostic.c` (lines 124–144) for controlled executable arguments and denominator checks; `tests/owned_cpu/negative.py` (lines 1–58) for supervising named failure controls; `tools/owned_cpu/contract.py` (lines 651–760) for structured outcomes and command dispatch.

**Fail-closed control precedent** (`negative.py`, lines 43–58):
```python
if child.returncode != 1 or expected_assertion not in output or expected_summary is None or not one_failure or not denominator:
    return fail("failure was not the single named 10-versus-11 guest result assertion", output)

print("PASS: mutation changed 10 to 11; only the named guest arithmetic/store assertion failed")
return 0
```

**Machine-readable error precedent** (`contract.py`, lines 736–760): catch only named contract errors, emit JSON with status/reason/message, and use a defined nonzero code. New tooling must distinguish pass/fail/skipped/unsupported/unknown; require exact identity fields and nonzero assertion counts. Runner owns host file reads and host-time cost measurements; the native core does neither. `contract.py` is bound to the historical Phase 01 gate, so copy mechanics only—do not invoke its obsolete Pending predicate as the Phase 02 router.

### CMake targets, package templates, presets and CTest registration (config)

**Analogs:** root `CMakeLists.txt` (lines 1–15), `experiments/owned_cpu/CMakeLists.txt` (lines 52–67, 100–135, 173–180), and `third_party/unity/PROVENANCE.md` (lines 1–14).

**Target-scoped C17 and test registration** (`experiments/owned_cpu/CMakeLists.txt`, lines 108–135):
```cmake
foreach(target IN LISTS OWNED_CPU_TARGETS)
  set_target_properties(${target} PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO)
  target_compile_options(${target} PRIVATE -Wall -Wextra -Werror
    ${OWNED_CPU_OPTIMIZATION_FLAGS} ${OWNED_CPU_SANITIZER_FLAGS})
endforeach()

add_test(NAME owned_cpu_diagnostic COMMAND owned_cpu_diagnostic)
set_tests_properties(owned_cpu_diagnostic PROPERTIES
  LABELS "owned-cpu;owned-diagnostic"
  TIMEOUT 30)
```

Keep Unity test-only and pinned with notice/digests. Root CMake currently only gates private experiments. No existing example exports/install interfaces, relocatable config, static/shared package selection, or consumer-language test exists. Research's package guidance (relative GNUInstallDirs, exported namespaced target, colocated config+targets, separate prefixes) is therefore a new pattern to implement and prove. No CMake consumer must inherit sanitizer/test flags.

### `tests/consumers/*` (installed consumer tests, request-response)

**Analog:** none. `experiments/owned_cpu/CMakeLists.txt` links in-tree targets only. Implement as independent out-of-tree configure/build/run projects that discover only a relocated install prefix; test static and shared C, then compile/link public headers from C++. No existing fixture can establish installed loader resolution or package relocation.

### `tools/verify_sdk.py`, bounded fuzz targets, and baseline protocol (batch/transform)

**Analog:** `tools/owned_cpu/contract.py` (lines 98–117 and 651–760) for hashing, stable named validation failures, self-test mutations, CLI subcommands and JSON results; `tests/owned_cpu/cold.py` (lines 8–35) for finite subprocess bounds and explicit case count.

Use one local entrypoint orchestrating focused CTest labels and independent consumer builds. Preserve per-suite output and identities, do not make a broad opaque pass. No existing script aggregates SDK local verification, fuzzes public media/call sequences, records SDK machine-readable artifact identities, or measures diagnostic load/memory/build baselines. Those are new implementation responsibilities. No fuzzer engine or availability is established in the codebase.

### `docs/*` (integrator documentation, request-response)

**Analogs:** root `README.md` (lines 3–19) for truthful scope/limits and link structure; `tests/cpu/ORACLE.md` (lines 3–40) for primary-source and uncertainty wording. No compiled public API example or lifecycle/ownership/error guide exists. Plan a compiled example verified against installed static/shared artifacts and document actual supported profile, error recovery, source lifetime, and unsupported game/BIOS/video/audio/snapshot claims.

## Shared Patterns

### Opaque handle, bounded guest execution, and explicit failure

**Sources:** `experiments/owned_cpu/cpu.h:7-29,44-73`; `tests/owned_cpu/test_faults.c:11-69`. Use fixed-width public values, finite cycle requests, explicit status, and no process exit. Keep backend registers and private hooks outside the SDK.

### Deterministic evidence and consequential controls

**Sources:** `tests/cpu/ORACLE.md:14-40`; `tests/owned_cpu/test_diagnostic.c:95-134`; `tests/owned_cpu/negative.py:43-58`. Compare against named independent expected values. Controls must fail one intended assertion with an observed denominator; a crash or generic nonzero exit is not evidence.

### Distinct-instance ownership evidence

**Sources:** `tests/owned_cpu/test_isolation.c:14-32,35-100`; `tests/owned_cpu/cold.py:8-35`. Build distinguishable isolated baselines and compare the same boundaries for interleaved/concurrent schedules. Keep host cold-process checks distinct from guest cycles.

### Offline pinned test dependency and private flags

**Sources:** `experiments/owned_cpu/CMakeLists.txt:52-67,108-135`; `third_party/unity/PROVENANCE.md:3-14`. Retain Unity's immutable pin, notice and file digests; keep test support out of runtime exports and apply C17/warnings/sanitizers per owned target.

## No Analog Found

| File / area | Role | Data Flow | Gap |
|---|---|---|---|
| Public installed package config/export and relocation tests | package/config and test | transform/request-response | No install/export or installed consumer implementation |
| Native source-media owning instance with transactional load/unload | service | CRUD | Private CPU takes callbacks; no machine instance owns/copies media |
| Public C++ linkage consumer | test | request-response | No public header or C++ consumer |
| Bounded C fuzz harnesses | test | transform | No fuzz target or harness |
| SDK evidence schema and cost baselines | evidence | batch | Phase 01 tool records its own contract and is unsuitable as current SDK report schema |
| Compiled public getting-started example | documentation/test | request-response | README is descriptive; no installed SDK consumer exists |

## Metadata

**Analog search scope:** root build/docs, `experiments/owned_cpu/`, `tests/cpu/`, `tests/owned_cpu/`, `tools/owned_cpu/`, and `third_party/unity/`.  
**Files scanned:** 11 primary analogs plus root CMake/README and Unity provenance; exhaustive file count not meaningful for this focused search.  
**Pattern extraction date:** 2026-10-05
