---
phase: 04-public-playable-tracer
plan: 04
subsystem: sound-cpu
tags: [z80, C17, CMake, CTest, admission, interrupts]
requires:
  - phase: 04-public-playable-tracer
    provides: Native C17 and test/build conventions from Plans 01-02
provides:
  - Pinned floooh/chips Z80 source and closed source/license/state inventory
  - Private per-instance tick/bus adapter and bounded SND-01 admission evidence
affects: [04-05, 04-06, selected-MVS-boot]
actuals:
  tokens: 51990
  tasks: 3
  commits: 4
tech-stack:
  added: [floooh/chips Z80 at 9e88298ce56319953ac7a43213a1120359f7a3a6]
  patterns: [Private opaque C adapter with per-instance bus userdata and continuation record]
key-files:
  created:
    - third_party/chips/z80.h
    - third_party/chips/NOTICE.md
    - src/chips/z80_candidate.c
    - src/chips/z80_candidate.h
    - tests/chips/test_z80.c
    - tests/chips/check_z80_source.py
  modified:
    - CMakeLists.txt
    - tests/chips/Z80-ADMISSION.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/deferred-items.md
key-decisions:
  - "Admit the pinned Z80 candidate for the exact synthetic Phase 04 workload; this does not qualify a private game sound program or broad Z80 compatibility."
  - "A failed bus callback stays latched through checkpoint restore; reset is required before execution can resume."
patterns-established:
  - "Keep imported CPU state, current pins, and tick count per instance; bus memory and callback ownership remain external."
  - "Record candidate output-pin callback stage separately from instruction T-state totals and physical silicon claims."
requirements-completed: [SND-01]
coverage:
  - id: D1
    description: "Pinned Z80 candidate admitted for the named synthetic instruction, bus, IRQ, reset, continuation, bounded-work and instance workload."
    requirement: SND-01
    verification:
      - kind: unit
        ref: "ctest --preset sdk-debug -R '^z80_admission' --output-on-failure --no-tests=error"
        status: pass
      - kind: unit
        ref: "ctest --preset sdk-asan-ubsan -R '^z80_admission' --output-on-failure --no-tests=error"
        status: pass
      - kind: unit
        ref: "ctest --preset sdk-tsan -R '^z80_admission' --output-on-failure --no-tests=error"
        status: pass
      - kind: other
        ref: "python3 tests/chips/check_z80_source.py"
        status: pass
    human_judgment: false
duration: "13m 33s"
completed: 2026-10-07
status: complete
plan_head_before: 52d62c464113d68d97bfdded30e22b7292063493
plan_head_after: d9400b6152a1c08ed3a98f6f8c023e6283f36ca7
commits: 4
---

# Phase 04 Plan 04: Z80 Candidate Admission Summary

**Pinned floooh/chips Z80 candidate admitted for a bounded C17 workload with cycle, bus, IRQ, continuation, reset, and independent-instance evidence.**

## Performance

- **Duration:** 13m 33s
- **Started:** 2026-10-07T21:28:21Z
- **Completed:** 2026-10-07T21:41:54Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Vendored the unchanged `floooh/chips` Z80 header at revision `9e88298ce56319953ac7a43213a1120359f7a3a6`, recorded its SHA-256 and full zlib/libpng notice, and added an offline source/include/state inventory checker.
- Built a private opaque C adapter with per-instance bus callback/userdata, one-cycle stepping, explicit reset, continuation records, checked cycle overflow, and latched callback errors. The candidate is absent from the playable runtime source list.
- Added eight positive behavior cases and five expected-failure observation mutations for instruction cycles, bus reads/writes, interrupt timing, reset, continuation, overflow and instance separation. Six focused CTest entries pass in debug, ASan/UBSan, and TSan configurations.
- Admitted SND-01 for the exact synthetic Phase 04 workload documented in [Z80-ADMISSION.md](./Z80-ADMISSION.md). The report distinguishes Zilog manual expectations, candidate pin-stage observations, and unmeasured hardware behavior.

## Task Commits

Each task was committed atomically. Task 3 used a TDD RED/GREEN pair.

1. **Task 1: Pin and inventory the Z80 candidate** — `21c6241` (`chore`)
2. **Task 2: Build private Z80 tick and bus adapter** — `10bf875` (`feat`)
3. **Task 3 RED: Prove selected-workload admission** — `85ec950` (`test`)
4. **Task 3 GREEN: Fix failure-latch restore and complete admission evidence** — `d9400b6` (`fix`)

The task commits span four commits from `plan_head_before` through `plan_head_after` as measured in the frontmatter. The final planning metadata commit is recorded separately by GSD.

## Files Created/Modified

- `third_party/chips/z80.h` and `third_party/chips/NOTICE.md` — pinned implementation and complete license notice.
- `src/chips/z80_candidate.c` and `src/chips/z80_candidate.h` — private per-instance tick, bus, reset, failure and continuation seam.
- `tests/chips/test_z80.c` — cycle, bus, IRQ, reset, continuation, overflow, fault and interleaved/concurrent instance checks plus mutation controls.
- `tests/chips/check_z80_source.py` — source digest, include closure, mutable-static and inventory completeness checks.
- `tests/chips/Z80-ADMISSION.md` — source/state inventory, named workload, exact oracle ancestry and bounded admission verdict.
- `CMakeLists.txt` — isolated admission executable, CTest entry, and five expected-failure mutation controls.
- `deferred-items.md` — current full-SDK baseline failure recorded without changing the unrelated README/package checks.

## Decisions Made

- SND-01 admission is limited to the named synthetic Phase 04 workload; later private game sound-driver behavior remains unqualified.
- The upstream CPU and its two immutable lookup tables have no mutable file-scope state. `z80_t`, active pins, callback ownership and cycle count are per-instance.
- A checkpoint cannot clear a bus fault. Reset explicitly clears the latch; externally owned memory is not part of the CPU snapshot.
- The Zilog manual supplies independent expected instruction/interrupt timing ancestry. No emulator comparison or fixture result is presented as original-silicon proof.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Prevent checkpoint restore from bypassing a failed bus callback**

- **Found during:** Task 3 RED probe.
- **Issue:** `z80_candidate_restore()` cleared the adapter's `bus_failed` latch, allowing a caller to resume after an external bus failure without reset.
- **Fix:** Restore now returns `Z80_CANDIDATE_BUS_FAILURE` while the latch is set; reset clears the latch and resets the cycle counter.
- **Files modified:** `src/chips/z80_candidate.c`, `tests/chips/test_z80.c`.
- **Verification:** The RED target failed specifically on expected status 4 versus actual 0; GSD returned `RED_EVIDENCE_OK`. The GREEN probe, focused debug CTest, ASan/UBSan, and TSan all pass.
- **Committed in:** `d9400b6`.

**2. [Rule 2 - Missing Critical] Resolve the plan's tick-overflow boundary probe**

- **Found during:** Task 3.
- **Issue:** The adapter had checked overflow behavior but no direct test for a cycle count at `UINT64_MAX`.
- **Fix:** Added a restored-maximum counter case proving `CYCLE_LIMIT` returns before CPU tick or bus activity.
- **Files modified:** `tests/chips/test_z80.c`.
- **Verification:** The case passes in debug, ASan/UBSan, and TSan suites.
- **Committed in:** `d9400b6`.

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical boundary check).
**Impact on plan:** Both changes close adapter failure/overflow correctness gaps in the planned admission scope.

## TDD Task Evidence

The named `test_bus_failure_cannot_restore_without_reset` probe failed on the intended Unity assertion and passed the GSD `tdd-red-evidence` classifier as `RED_EVIDENCE_OK`. After the restore guard was added, the same focused probe passed. The raw reporter output stays outside Git because compiler diagnostics contain the local absolute checkout path.

## Issues Encountered

- The upstream `z80_opdone()` helper reports instruction completion on the following overlapped M1/T2 step; tests separately assert the 7-T architectural result and the helper's report boundary.
- The full `sdk-debug` CTest run executed 33 tests: 31 passed and two existing package documentation checks failed on a stale root README link to `.planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md`. The same failure is recorded in `deferred-items.md`; no unrelated README or package-check behavior was changed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 04-04 is complete; Phase 04 is not complete. Plans 04-05 and 04-06 remain. Run `$gsd-execute-phase 04 --ws first-playable-game` to continue with the next runnable plan. The Z80 admission is bounded to this synthetic workload; any future private sound-program workload needs its own instruction/bus coverage before a broader support claim.

## Self-Check: PASSED

All eight required implementation/report files exist, and task commits `21c6241`, `10bf875`, `85ec950`, and `d9400b6` are ancestors of the current plan head.

---
*Phase: 04-public-playable-tracer*
*Plan: 04*
*Completed: 2026-10-07*
