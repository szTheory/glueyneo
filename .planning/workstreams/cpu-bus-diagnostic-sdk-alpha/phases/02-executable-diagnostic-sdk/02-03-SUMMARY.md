---
phase: 02-executable-diagnostic-sdk
plan: "03"
subsystem: sdk
tags: [c17, bounded-execution, callback-trace, negative-controls, concurrency]

requires:
  - phase: 01-cpu-acceptance-experiment
    provides: Accepted owned C17 CPU backend for the bounded diagnostic subset
  - phase: 02-executable-diagnostic-sdk
    provides: Opaque per-instance API, original diagnostic fixture, and transactional media lifecycle
provides:
  - Actual bounded run progress, faults, reset debt and stopped idle results through the public API
  - Bounded instance-local test trace and exact consequential behavior controls
  - Equal-boundary repeat, split, interleaved, concurrent and cold-instance evidence
  - Updated manual-derived oracle, exact control mappings and mutable-state inventory
affects: [Phase 02 package consumers, hostile-input tests, sanitizer and evidence plans]

actuals:
  tokens: 19945
  tasks: 3
  commits: 3
  plan_head_before: 3554c6f09a936a2646a9e2503097df9b2e9d694d
  plan_head_after: 184f3a3a1f32ba3eb0f808ee504574bef6735ec7

tech-stack:
  added: []
  patterns:
    - Public run results report backend event charges without clamping; guest faults and host failures remain distinct
    - Bounded trace and mutation seams are stored per image in the test-only target
    - Compare distinct instances against owner-specific public-API baselines at exact cumulative guest boundaries
    - Keep thread primitives and private failure hooks out of the production runtime

key-files:
  created: []
  modified:
    - CMakeLists.txt
    - src/instance.c
    - src/sdk_private.h
    - tests/sdk/test_sdk.c
    - tests/sdk/controls.py
    - tests/sdk/ORACLE.md

key-decisions:
  - "Report actual guest event charges, reset recovery overshoot and stopped idle progress; reject invalid or overflowing work before partial guest-state mutation."
  - "Keep the 256-event callback trace, drop count and mutation controls instance-local and compiled only into the test target."
  - "Compare only the selected exact schedule at matching boundaries; do not infer equivalence for arbitrary request partitions or concurrent calls on one instance."
  - "Use the available POSIX thread API through CMake Threads::Threads in the test executable because this AppleClang environment lacks <threads.h>; leave the C17 runtime unchanged."

patterns-established:
  - "Named diagnostic claims carry a stable assertion ID and one isolated mutation with fixed expected/observed values."
  - "Cold concurrency supervision uses fresh processes and host-only timeouts; guest progress remains independent of wall time."

requirements-completed: [API-03, DIAG-01, DIAG-02, DIAG-03, EVID-02, EVID-03]

coverage:
  - id: D1
    description: Bounded execution reports actual cycles, dispatches, overshoot, stop/fault reason and integer-edge results.
    requirement: API-03
    verification:
      - kind: integration
        ref: "cmake --preset sdk-debug && cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-run --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D2
    description: The functional callback trace and eight consequential mutations agree with fixed, exact assertions; four independent runner processes produce matching scenario outputs.
    requirement: DIAG-02
    verification:
      - kind: integration
        ref: "cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-controls --output-on-failure --no-tests=error"
        status: pass
      - kind: integration
        ref: "cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-diagnostic --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D3
    description: Repeat, split, interleaved and concurrent distinct-instance execution matches owner-specific baselines at 13 selected boundaries; cold creation, replacement failure, reset and teardown are exercised in eight fresh processes.
    requirement: DIAG-03
    verification:
      - kind: integration
        ref: "cmake --build --preset sdk-debug && ctest --preset sdk-debug -L sdk-isolation --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D4
    description: Run, controls and isolation results include nonzero assertion denominators, outcome categories, source revision, configuration and compiler identity.
    requirement: EVID-03
    verification:
      - kind: other
        ref: "sdk-run: 6 cases / 149 assertions; sdk-controls: 1 / 154; sdk-isolation: 1 / 11; sdk-cold child: 1 / 19; source 184f3a3a1f32, Debug, AppleClang 21.0.0.21000101"
        status: pass
    human_judgment: false
  - id: D5
    description: Bounded execution, exact-boundary comparisons, allocation-failure recovery and cold lifecycle paths add automated boundary/property evidence toward EVID-02; broader fuzz and sanitizer obligations remain phase-level work.
    requirement: EVID-02
    verification:
      - kind: integration
        ref: "ctest --preset sdk-debug -L 'sdk-run|sdk-isolation' --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false

duration: 27min
completed: 2026-10-05
status: complete
---

# Phase 02 Plan 03: Bounded Execution and Instance Determinism Summary

**The diagnostic API now reports actual bounded CPU progress, checks functional bus claims with exact mutations, and proves selected equal-boundary behavior across distinct instances.**

## Performance

- **Duration:** 27 min
- **Started:** 2026-10-05T20:50:50-04:00
- **Completed:** 2026-10-05T21:17:09-04:00
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added counted run checks for requests `0, 1, 39, 40, 41, 172, 173, 1,000,000` and rejected `1,000,001`, including reset debt, STOP idle, zero-state mutation, overflow, bounded fault details and integer vectors. The focused suite passes with 6 cases and 149 assertions.
- Recorded at most 256 numeric functional callback events per test image, with an explicit dropped count, and added eight exact consequential controls plus eight supervisor rejection self-controls. The normal controls suite passes with 1 case and 154 assertions.
- Compared scenario A/B at 13 equal guest-cycle boundaries; passed 16 interleaved pairs, 16 barrier-started concurrent pairs and eight fresh cold child processes. Cold coverage includes 16 owner runs, 16 failed candidate replacements, 16 reset recoveries and zero teardown leaks.
- Added the exact assertion/control matrix and complete runtime/test mutable-state inventory to [ORACLE.md](../../tests/sdk/ORACLE.md). The independent CPU oracle remains the cited Motorola/NXP manuals; callback order is only the implementation's functional mapping contract.

## Exact Assertion and Control Mapping

The runner controls require a normal exit status of 1, one Unity failure, the exact assertion ID and expected/observed pair, one case, and a positive assertion count. The eight supervisor self-controls reject normal exit, signal, unrelated failure, unchanged value, multiple failures, zero denominator, zero cases and timeout outcomes.

| Mutation | Assertion ID | Expected | Observed | Child assertions |
|---|---|---:|---:|---:|
| Arithmetic guest input | `sdk.observe.arithmetic` | 10 | 11 | 5 |
| Initialized word | `sdk.observe.initialized` | 4663 | 4664 | 5 |
| BSS read adapter | `sdk.observe.bss` | 1 | 2 | 6 |
| Instruction count adapter | `sdk.run.instructions` | 12 | 13 | 6 |
| Elapsed-cycle adapter | `sdk.run.elapsed-cycles` | 172 | 173 | 6 |
| STOP reason adapter | `sdk.run.reason-stopped` | 1 | 0 | 6 |
| Arithmetic byte-order adapter | `sdk.observe.arithmetic-byte-order` | 10 | 167772160 | 6 |
| First vector-read order adapter | `sdk.bus.event.00.address` | 0 | 2 | 9 |
| Swapped scenario owner | `sdk.isolation.owner.arithmetic` | 10 | 16 | 3 |
| Altered split-progress result | `sdk.isolation.split-progress` | 40 | 41 | 5 |

The functional trace contains 35 events with zero drops in the original guest case. Each of four independent runner processes uses a distinct temporary JSON result path; two scenario A and two scenario B processes agree.

## Equal-Boundary and Cold Counts

The split requests were `40,4,8,20,4,16,8,20,4,16,8,20,4`; cumulative boundaries were `40,44,52,72,76,92,100,120,124,140,148,168,172`. At each boundary the suites compared public observations, PC, reason, cumulative cycles/instructions/overshoot, per-call results for split runs, pointer-free ROM/RAM/CPU-state digest and trace digest/count/drop count. The single 172-cycle call is compared at its matching terminal boundary. These results do not imply equivalence for arbitrary partitions.

| Evidence | Count | Result |
|---|---:|---|
| Selected cumulative boundaries | 13 | All match the isolated A/B baselines |
| Interleaved A/B instance pairs | 16 | Pass |
| Barrier-started concurrent A/B pairs | 16 | Pass; 32 candidate replacement failure paths |
| Cold child processes | 8 | Pass; each starts one concurrent pair |
| Cold owner executions | 16 | Pass |
| Cold candidate failure paths | 16 | Preserved image digest and allocator live counts |
| Cold reset recoveries | 16 | Pass |
| Cold teardown leaks | 0 | Pass |

## Task Commits

Each task was committed atomically:

1. **Task 1: Expose and test actual bounded guest progress** - `439a8b3` (`feat`)
2. **Task 2: Prove every consequential runner and functional bus assertion** - `0ae595b` (`test`)
3. **Task 3: Compare equal-boundary repeat, split and distinct concurrent instances** - `184f3a3` (`test`)

The plan metadata commit includes this summary and GSD tracking updates; its hash is recorded in the executor result.

## Files Modified

- `src/instance.c` - actual run progress translation, bounded trace, per-image test controls.
- `src/sdk_private.h` - private trace and test-hook declarations.
- `tests/sdk/test_sdk.c` - run boundary, control, trace, equal-boundary and cold lifecycle cases.
- `tests/sdk/controls.py` - exact mutation validation, independent runner records and cold-process supervisors.
- `CMakeLists.txt` - focused CTest suites and test-only thread dependency.
- `tests/sdk/ORACLE.md` - manual ancestry, functional trace assertions, isolation schedule and mutable-state inventory.

## Decisions Made

- `gn_run` reports backend event charges, including reset-event overshoot and stopped idle work; invalid or overflowing requests leave guest state unchanged.
- Trace and mutation state stays per image in the test build, bounded to 256 records with explicit drops; public headers and runtime exports remain free of test hooks.
- Determinism claims apply to the exact selected request schedule and equal boundaries. The results do not establish arbitrary-budget equivalence, same-instance concurrency, physical Neo Geo bus behavior or original-hardware truth.
- POSIX threads are linked only into the SDK test executable because the active AppleClang environment has no `<threads.h>` header.

## Deviations from Plan

None - the plan's outcomes and ownership boundaries were preserved.

## Issues Encountered

- The first Task 3 build showed this AppleClang toolchain lacks `<threads.h>`. The test-only barrier harness uses POSIX threads through `Threads::Threads`; a rebuild and the focused isolation suite passed. No thread dependency or concurrency primitive was added to the runtime library.

## User Setup Required

None - no external service configuration is required.

## Next Phase Readiness

Plan 02-03 is complete; Phase 02 is still in progress with Plans 02-04 through 02-06 outstanding. Shared-requirement readiness allowed API-03 and DIAG-02 to be marked complete now; DIAG-01, DIAG-03, EVID-02 and EVID-03 remain pending other phase plans. Do not start Plan 02-04 in this execution. After the user continues, the concrete next command is `$gsd-execute-phase 02`.

---
*Phase: 02-executable-diagnostic-sdk*
*Completed: 2026-10-05*

## Self-Check: PASSED

- Summary file exists and passes the installed GSD `summary` frontmatter schema.
- Task commits `439a8b3`, `0ae595b` and `184f3a3` exist; the measured plan commit count is 3.
- `verify-summary` found its claimed project files and commit references.
- All focused run, controls, diagnostic, isolation and cold-process verifications passed at source revision `184f3a3a1f32`.
