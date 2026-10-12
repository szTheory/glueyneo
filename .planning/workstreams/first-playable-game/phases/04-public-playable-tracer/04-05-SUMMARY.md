---
phase: 04-public-playable-tracer
plan: 05
subsystem: audio
tags: [ymfm, YM2610, C++14, C17, CMake, static, shared]

requires:
  - phase: 04-public-playable-tracer
    provides: accepted pinned YM2610 candidate identity and PROJECT-D-48 conditional exception
provides:
  - Pinned nine-file YM2610 source closure with BSD-3-Clause notice and mutable-state/callback inventory
  - Private opaque C candidate interface with deterministic clock/sample cadence and bounded external callbacks
  - Passing source, direct behavior, and installed static/shared C-consumer admission report
affects: [04-public-playable-tracer final validation, phase 05 sound CPU integration, phase 07 audible sound]

actuals:
  tokens: 72758
  tasks: 3
  commits: 5
commits: 5
plan_head_before: eef4d92a7c7090cb500c8ad57aa4adb7b555a5f4
plan_head_after: af70ec720e9d4e947461842c30ddace811aa0126

tech-stack:
  added: [pinned ymfm YM2610 source closure, private C++14 candidate target]
  patterns: [opaque C ABI around imported C++ engine, target-scoped C++14, CMake-propagated C++ runtime linkage]

key-files:
  created:
    - third_party/ymfm/LICENSE
    - third_party/ymfm/NOTICE.md
    - third_party/ymfm/src/ymfm.h
    - third_party/ymfm/src/ymfm_adpcm.cpp
    - third_party/ymfm/src/ymfm_adpcm.h
    - third_party/ymfm/src/ymfm_fm.h
    - third_party/ymfm/src/ymfm_fm.ipp
    - third_party/ymfm/src/ymfm_opn.cpp
    - third_party/ymfm/src/ymfm_opn.h
    - third_party/ymfm/src/ymfm_ssg.cpp
    - third_party/ymfm/src/ymfm_ssg.h
    - src/chips/ym2610_candidate.cpp
    - src/chips/ym2610_candidate.h
    - tests/chips/check_ym2610.py
    - tests/chips/test_ym2610.c
  modified: [CMakeLists.txt]

key-decisions:
  - "Admitted only the pinned ymfm YM2610 subset at upstream revision 81aec25ccbb98f4873a255f7551ac4dadac59b4a after all nine source, behavior, failure, bounds, and consumer gates passed."
  - "The private candidate generates chip-native samples at one frame per 16 input clocks; it adds no resampler, host clock, or frontend audio service."
  - "YM2610 sample evidence proves candidate output only; audible game sound, driver compatibility, and physical-hardware fidelity remain unqualified."

patterns-established:
  - "Copy callback tables into each candidate and require caller-owned userdata to outlive the instance."
  - "Reject callback reentry and out-of-range ADPCM/I/O addresses before forwarding across the C boundary."
  - "Export only explicit C entry points from the shared candidate and propagate the static C++ runtime through the installed CMake target."

requirements-completed: [SND-02]
coverage:
  - id: D1
    description: "Pinned ymfm YM2610 candidate passes source/state, deterministic clock/sample, isolation, reset/continuation, callback/exception/bounds, and installed static/shared C-consumer admission gates."
    requirement: SND-02
    verification:
      - kind: unit
        ref: "python3 tests/chips/check_ym2610.py source"
        status: pass
      - kind: integration
        ref: "ctest --preset sdk-debug -R '^ym2610_admission$' --output-on-failure --no-tests=error"
        status: pass
      - kind: integration
        ref: "python3 tests/chips/check_ym2610.py link --both-linkages"
        status: pass
    human_judgment: false

duration: 10 min
completed: 2026-10-07
status: complete
---

# Phase 04 Plan 05: YM2610 Candidate Admission Summary

**Pinned ymfm YM2610 source now passes the private C-boundary, deterministic sample, failure, and installed static/shared C-consumer admission checks.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-10-07T21:44:56Z
- **Completed:** 2026-10-07T21:55:03Z
- **Tasks:** 3
- **Files modified:** 17, including the phase deferred-items record

## Accomplishments

- Vendored the smallest compiled YM2610 closure from immutable upstream revision `81aec25ccbb98f4873a255f7551ac4dadac59b4a`; all nine source files and the BSD-3-Clause license are hash-checked and the notice inventories per-instance state, callbacks, timer/sample assumptions, failure paths, and serialization limits.
- Added a private C API over a target-scoped C++14 candidate. It copies callbacks, checks external address bounds, rejects reentry, catches C++ exceptions, latches callback errors until reset, bounds each clock step and output capacity, and emits three-channel chip-native samples at the documented 16-clock cadence.
- Passed five direct C17 behavior tests and the same five tests from actual installed static and shared C consumers. The report records 256 generated frames, 128 nonzero channel values, and sample fingerprint `fnv1a64:e456cbb957de9a25`.
- Passed all nine SND-02 gates. The ignored report is `build/ym2610-admission/ym2610-admission.json`, SHA-256 `aebe1389c45758afd07e8e126c912cede7eef14d1852b8fce3b590012cf2d762`, generated against Glueyneo revision `af70ec720e9d4e947461842c30ddace811aa0126` on AppleClang 21.0.0.21000101, macOS 26.6.2 arm64. Shared-library inspection found exactly the eight intended C symbols, no exported ymfm C++ names, and the expected `libc++.1.dylib` dependency. The static C target supplied `-lc++` through its imported CMake interface.

## Task Commits

1. **Task 1: Pin YM2610 source closure and inventory license and state** — `5d9d87a` (`feat`)
2. **Task 2 RED: Add failing YM2610 candidate contract** — `8705ed3` (`test`)
3. **Task 2 GREEN: Add deterministic YM2610 C shim** — `600ba4e` (`feat`)
4. **Task 3 correction: Bound external callbacks and reject reentry** — `834c069` (`fix`)
5. **Task 3: Verify installed static and shared C consumers** — `af70ec7` (`test`)

The TDD RED record is `build/ym2610-admission/tdd-red.json`. The named create-instance TAP assertion failed as intended against the temporary stub; `gsd check tdd-red-evidence` returned `RED_EVIDENCE_OK`. The same TAP assertion passed after the implementation.

## Files Created/Modified

- `third_party/ymfm/` - pinned source closure, upstream license, hashes, and state/callback inventory.
- `src/chips/ym2610_candidate.h` and `src/chips/ym2610_candidate.cpp` - private C ABI and contained YMFM engine instance.
- `tests/chips/test_ym2610.c` and `tests/chips/check_ym2610.py` - direct and installed-consumer tests, source verification, symbol/runtime audit, and machine report.
- `CMakeLists.txt` - isolated C++14 candidate target and installed package export, disabled when tests/admission are disabled.
- `.planning/workstreams/first-playable-game/phases/04-public-playable-tracer/deferred-items.md` - records the existing unrelated full-suite documentation failures.

## Decisions Made

- The selected closure excludes unrelated YMFM chip families and upstream build files; the tested four C++ translation units compile and link from the nine hashed upstream files.
- The candidate exposes reset-boundary and chunked-clock continuation evidence only. YMFM's upstream byte-vector serializer is versionless/unbounded, so Glueyneo does not expose it or claim durable state compatibility.
- SND-02 admission does not imply a public audio path or audible game sound. SND-03 and physical Neo Geo sound behavior remain unqualified for Phase 07.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Enforced explicit callback bounds and non-reentrancy**
- **Found during:** Task 3 consumer review
- **Issue:** The first shim version forwarded YMFM external accesses without checking per-class address lengths and did not reject nested calls from callbacks.
- **Fix:** Copy callback tables and sizes into the instance, reject out-of-range ADPCM-A/ADPCM-B/I/O accesses before invocation, and latch nested API calls as callback failure.
- **Files modified:** `src/chips/ym2610_candidate.h`, `src/chips/ym2610_candidate.cpp`, `tests/chips/test_ym2610.c`, `third_party/ymfm/NOTICE.md`
- **Commit:** `834c069`
- **Verification:** direct admission test plus installed static/shared C consumers pass.

## Issues Encountered

- The full `sdk-debug` suite ran 34 tests: 32 passed and two pre-existing package documentation checks failed because the root README links to `.planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md`, which now lives in the diagnostic workstream. The YM2610 admission test and installed consumers passed. The repeated failure is recorded in `deferred-items.md`; it is outside this plan's source scope.
- Upstream ymfm emits unused-parameter warnings under the selected compiler warning flags. They remain warnings on the imported dependency target; owned candidate and C consumer code compile with the project’s strict C warnings.

## Self-Check: PASSED

- All plan-created files exist and the five plan commits are ancestors of HEAD.
- The machine report has all nine required gates set to `pass`; its static and shared consumer entries each record five tests and zero test errors.
- No YM2610 task stub or placeholder remains. The only outstanding full-suite checks are the unrelated README path checks listed above.

## Next Phase Readiness

Plan 04-05 and SND-02 candidate admission are complete; Phase 04 itself remains in progress. `SND-02` remains unchecked in workstream REQUIREMENTS until Plan 04-06 finishes because that plan also declares the shared requirement and must incorporate this report digest. HOST-02 remains unqualified/unknown as already recorded. Next command: `$gsd-execute-phase 04 --ws first-playable-game`.

---
*Phase: 04-public-playable-tracer*
*Plan: 05*
*Completed: 2026-10-07*
