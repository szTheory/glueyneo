---
phase: 01-cpu-acceptance-experiment
plan: "10"
subsystem: owned-cpu-safety
tags: [68000, c17, isolation, faults, inventory, sanitizers]
provides:
  - Interleaved, barrier-started concurrent, and fresh-process cold instance evidence
  - Bounded allocator, callback, lifecycle, host-fault and recovery regressions
  - Source-hashed inventory of owned fields, test globals, callbacks and compile closure
  - Target-scoped ASan+UBSan and ThreadSanitizer configurations
affects: [phase-01-execution, owned-cpu-admission]
actuals:
  tokens: 20000
  tasks: 2
  commits: 4
plan_head_before: 2f6ddbd79b5c594af05a5bfff1cfcc92a71b994b
tech-stack:
  added: []
  patterns: [per-instance callback ownership, barrier-started cold tests, source-bound compile inventory]
key-files:
  created:
    - experiments/owned_cpu/state-inventory.json
    - tests/owned_cpu/cold.py
    - tests/owned_cpu/isolation_fixture.h
    - tests/owned_cpu/test_cold.c
    - tests/owned_cpu/test_faults.c
    - tests/owned_cpu/test_inventory.py
    - tests/owned_cpu/test_isolation.c
    - tools/owned_cpu/inventory.py
  modified:
    - experiments/owned_cpu/CMakeLists.txt
    - tests/owned_cpu/negative.py
key-decisions:
  - "Independent instances may be used concurrently when each instance and callback userdata have one owner; overlapping calls on the same instance remain unsupported."
  - "The active byte rejects synchronous callback reentry; it is not a same-instance thread synchronization primitive."
  - "Sanitizers instrument the owned core, Unity test object and each linked C test target; tool output is bounded source-review support, not an independent completeness proof."
duration: 37min
completed: 2026-10-02
status: complete
---

# Phase 1 Plan 10: Instance safety and state inventory

**Distinct owned instances now match isolated outcomes across interleaving, concurrent first use and fresh processes, with bounded host-fault controls and a source-bound inventory.** This evidence applies to the tested native Apple Clang 21 / Darwin arm64 setup; it does not admit the backend or establish support on other platforms.

## Accomplishments

- Added two original diagnostic owners with separate ROM, RAM, IRQ levels, callback traces and allocation accounting. At six named boundaries, the tests compare the complete public observation, run result, every RAM byte and the ordered word-bus trace against isolated baselines.
- Added 32 interleaved pairs and 32 barrier-started concurrent pairs. The cold runner starts two threads before either creates a CPU and supervises 16 separate fresh processes. Each pair creates, resets, runs and destroys both instances. The swapped-owner control is accepted only when Unity reports the named `Expected 10 Was 16:swapped-owner guest D0` failure.
- Added allocation failure/output-null checks, malformed lifecycle and callback inputs, terminal reset/fetch/data/store/stack/vector faults, preserved first-word side effects on a failed second long write, reset recovery, same-instance callback reentry rejection and level-7 wake from STOP. Existing Plan 09 cases retain coverage for odd PC/stack/data, nested exception failure, maximum request/address boundaries and counter overflow. All fault checks run in-process and require clean teardown.
- Added `state-inventory.json` with 26 exact owned-struct fields, callback and allocator bindings, initialization sites, reset/capture dispositions, automatic CPU scratch values, mutable test-runner globals, source digests and the nine distinct compiled C translation units. The checker verifies C17 flags and actual compile commands; sanitizer checks inspect each owned executable's Ninja linker command. It rejects missing/extra fields, declaration drift, stale hashes, hidden runtime globals, direct host-service calls and callback owner reassignment by named reasons.
- Added target-scoped `GLUEYNEO_OWNED_CPU_SANITIZER=NONE|ADDRESS_UNDEFINED|THREAD` and `GLUEYNEO_OWNED_CPU_OPTIMIZATION=NONE|RELEASE`. The runtime, Unity source and all six C test executables receive the selected compile flags; every executable receives the matching link flags. `Threads::Threads` remains test-only. No runtime code or dependency changed in this plan.

## Test Evidence

- Native strict C17 build and full owned CTest suite passed: 11 expected, 11 observed, including the exact owner-mutation control, 16 supervised cold processes, inventory tests and actual compile-database check.
- ASan+UBSan configuration built successfully; all six `owned-safety` CTests passed. ThreadSanitizer configured, built at `-O2`, and all six safety CTests passed on this host. The native `NONE`/`-O0` and TSan `RELEASE`/`-O2` modes both passed source/compile/link inventory checks. These are results for this machine and compiler/runtime only.
- Inventory's seven unit controls passed in normal Python and `python3 -O`; its self-test passed in both modes, including missing/extra fields, stale digest, hidden global and callback-owner mutation controls. The contract self-test passed with two positive cases and six named negative controls. The Plan 10 receipt records 2,217 active seconds; cumulative effort is 11,630 seconds, with 989 runtime and 3,728 test/tool added/deleted lines. The frozen budget/churn check passes with no threshold pause.
- Early failures were retained and corrected: the first ASan capability probe compiled with instrumentation but omitted sanitizer linker flags, falsely reporting the compiler lane unavailable; the probe now links with the same sanitizer flags. An expanded lifecycle test initially compared the fixture helper's boolean return to the CPU status enum; the assertion now checks truth. The inventory gate also correctly rejected one stale test-source digest after that edit; the digest is current and the complete suites pass.
- `git diff --check` passed before commit. Implementation/evidence commit: `79f36c8`.

## Scope limits

The callback `active` field detects same-thread reentry while a guarded operation invokes host code; it is not atomic and does not make concurrent same-instance calls safe. Separate-instance concurrency was exercised with pthread-backed CMake Threads on Apple Clang 21 / Darwin arm64 only. ASan+UBSan and TSan both ran successfully there; no claim is made for another compiler, operating system, architecture or sanitizer runtime.

The source inventory checker recognizes the current C source shape and known fixture callbacks. It is a regression aid that supports later independent review, not a parser or proof that no object was overlooked. This plan does not implement durable saves, replay, public ABI compatibility or state continuation; Plan 11 owns restore-into-fresh-instance continuation evidence. CPU-01–05 remain Pending, Phase 01 stays open / GAPS_FOUND, and Phase 02 remains gated.

## Next

Continue with Plan 11 in the active gaps-only execute-phase step: capture the declared state, restore it into a fresh destination, and prove identical continuation and atomic rejection.

## Self-Check: PASSED

- All created artifacts exist and the implementation commit `79f36c8` is present.
- The 11-case native CTest suite, six-case ASan+UBSan safety suite and six-case TSan safety suite pass on the recorded host.
- Instance isolation, fault containment, callback reentry rejection, compile closure and inventory corruption controls match the Plan 10 acceptance criteria.
- Same-instance overlapping calls, other host/compiler portability, and state continuation remain outside this plan's evidence.
