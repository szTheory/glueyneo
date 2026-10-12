---
phase: 02-executable-diagnostic-sdk
plan: "05"
subsystem: testing
tags: [C17, CMake, CTest, ASan, UBSan, TSan, deterministic-mutation]
requires:
  - phase: 02-03
    provides: lifecycle, media, fault, run, and concurrent-instance SDK tests
  - phase: 02-04
    provides: packaged SDK and relocated consumer targets
provides:
  - bounded deterministic media and public-call mutation harnesses
  - startup-gated ASan+UBSan and TSan SDK test presets
  - exact sanitizer, mutation, timing, and coverage-limit records
affects: [02-06, SDK diagnostics, testing]
actuals:
  tokens: 23306
  tasks: 2
  commits: 2
  plan_head_before: d6f796e36429453f6cbbf371f026f48831d66940
  plan_head_after: 4baf32c5642dbdc9af943970773296c3631b065c
tech-stack:
  added: []
  patterns:
    - target-private sanitizer compile and link options
    - exact runtime startup gate before sanitizer CTest suites
key-files:
  created:
    - tests/fuzz/sdk_mutation.c
    - tests/fuzz/regressions.json
    - tests/fuzz/minimize.py
    - docs/testing.md
  modified:
    - CMakeLists.txt
    - CMakePresets.json
    - tests/sdk/controls.py
    - tests/sdk/test_support.h
key-decisions:
  - "Use finite seeded C mutation because the matching AppleClang libFuzzer archive is unavailable; do not install a toolchain or claim coverage guidance."
  - "Keep sanitizer flags target-private and verify both instrumented link commands and the clean installed consumer export."
patterns-established:
  - "Run an exact compiler/runtime probe in each sanitizer lane before treating any SDK CTest result as supported evidence."
  - "Report mutation caps, seeds, measured assertion counts, unsupported tools, and unmeasured memory explicitly."
requirements-completed: [EVID-02, EVID-03, DIAG-03]
coverage:
  - id: D1
    description: "Bounded media and valid public-call mutation runs from fixed seeds and retained original diagnostic inputs."
    requirement: EVID-02
    verification:
      - kind: unit
        ref: "ctest --preset sdk-debug -L sdk-mutation --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D2
    description: "ASan+UBSan and TSan execute their nonempty SDK suites only after exact startup probes pass."
    requirement: EVID-02
    verification:
      - kind: integration
        ref: "python3 tests/sdk/controls.py --sanitizers"
        status: pass
    human_judgment: false
  - id: D3
    description: "Machine-readable suite outcomes carry compiler, configuration, source, and sanitizer identity with positive assertion counts."
    requirement: EVID-03
    verification:
      - kind: integration
        ref: "python3 tests/sdk/controls.py --sanitizers"
        status: pass
    human_judgment: false
  - id: D4
    description: "Unavailable coverage-guided fuzzing and unavailable memory measurement are explicitly identified."
    requirement: EVID-03
    verification:
      - kind: other
        ref: "docs/testing.md#unsupported-coverage"
        status: pass
    human_judgment: false
  - id: D5
    description: "Distinct instances pass equal-boundary interleaving and concurrent cold lifecycle checks under TSan."
    requirement: DIAG-03
    verification:
      - kind: integration
        ref: "python3 tests/sdk/controls.py --sanitizers (sdk_isolation and sdk_cold)"
        status: pass
    human_judgment: false
duration: 40min
completed: 2026-10-05
status: complete
---

# Phase 02 Plan 05: Hostile Input and Sanitizer Evidence Summary

**Two bounded C mutation harnesses and startup-gated ASan+UBSan/TSan suites passed with target-private instrumentation and recorded coverage limits.**

## Performance

- **Duration:** 40 min
- **Started:** 2026-10-06T01:51:29Z
- **Completed:** 2026-10-06T02:31:26Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added seeded media and valid public-call sequence mutation. Both harnesses ran 1,024 iterations with the declared byte, operation, instance, storage, and per-input cycle caps; all three focused mutation CTests passed.
- Added independent ASan+UBSan and TSan presets. AppleClang 21.0.0.21000101 passed each exact startup probe, then the ASan+UBSan lane passed 8/8 SDK tests with 577,077 assertions and TSan passed 2/2 isolation/cold tests with 30 assertions.
- Verified sanitizer compile and link commands are target-private and the installed `GlueyneoTargets.cmake` export contains no sanitizer flags. Documented exact results, costs, and unsupported dimensions in `docs/testing.md`.

## Mutation and Sanitizer Results

- Media seed `0x6e656f67656f3235`: 10 named cases, 1,024 unique generated inputs, 1,034 operations, maximum 432 requested guest cycles per input, and 34,739 assertions.
- Sequence seed `0x6e656f67656f3235 XOR 0xa17f00d5`: two named cases, 1,017 unique inputs, 33,169 operations, maximum 3,313 requested guest cycles per input, peak 20,520 media bytes, and 541,434 assertions. Total cycles across all inputs exceed one million; the per-input maximum remains far below the one-million cap.
- ASan+UBSan startup passed 17 checks; its eight tests covered lifecycle, media, faults, run, diagnostic, both mutation entrypoints, and the minimizer control. TSan startup passed 18 checks including a joined worker thread; the two runtime tests covered 16 interleaved pairs, 16 barrier-synchronized pairs, concurrent failure paths, and eight cold processes.
- The minimizer control reduced a synthetic 25-byte trigger to two bytes while preserving its exact failure ID. No real runtime defect was found, so no real input was minimized or added as a newly discovered regression.
- Final sanitizer supervisor wall time was approximately 0.87 seconds for ASan+UBSan and 3.68 seconds for TSan with incremental builds. The first full lane builds took 0.73 and 0.75 seconds after 1.23 and 0.91 second configure steps. Peak RSS is unmeasured because this host denies `ps` process inspection (`Operation not permitted`).

## Task Commits

1. **Task 1: Bound hostile media and valid public call-sequence mutation** - `d0df265` (`test`)
2. **Task 2: Run actual supported sanitizer suites without multiplying lanes** - `4baf32c` (`test`)

## Files Created/Modified

- `tests/fuzz/sdk_mutation.c` - Seeded, bounded media and public-call sequence entrypoints plus exact sanitizer startup probes.
- `tests/fuzz/regressions.json` - Original diagnostic corpus, mutation seeds, and explicit resource limits.
- `tests/fuzz/minimize.py` - Failure-ID-preserving byte deletion and replay metadata.
- `CMakeLists.txt` - Compiler/linker sanitizer checks and private target instrumentation.
- `CMakePresets.json` - Separate SDK ASan+UBSan and TSan configure/build/test presets.
- `tests/sdk/controls.py` - Stage-by-stage sanitizer supervisor and concurrency result checks.
- `tests/sdk/test_support.h` - Additive sanitizer identity in machine-readable SDK results.
- `docs/testing.md` - Reproduction commands, results, limits, and unsupported coverage.

## Decisions Made

- Kept fuzzing deterministic and finite because the matching AppleClang libFuzzer archive is absent; no toolchain was installed and no coverage-guided execution is claimed.
- Instrumented SDK runtime and host test targets with private flags, then inspected both the sanitized executable link command and installed package export for leakage.
- Kept unavailable RSS as an explicit unknown rather than estimating memory from process data the host denied.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Added Unity lifecycle hooks required by the mutation executable.**
- **Found during:** Task 1
- **Issue:** The initial mutation target linked against Unity without the required `setUp` and `tearDown` symbols.
- **Fix:** Added no-op hooks in the harness, which has no per-test global fixture state.
- **Files modified:** `tests/fuzz/sdk_mutation.c`
- **Verification:** `cmake --build --preset sdk-debug` and the focused mutation CTest passed.
- **Committed in:** `d0df265`

**2. [Rule 1 - Bug] Made sanitizer test selection and CTest accounting exact.**
- **Found during:** Task 2
- **Issue:** The first supervisor run selected `sdk_host_closure` through its overlapping `sdk-lifecycle` label and expected a CTest summary string that this CMake version does not emit.
- **Fix:** Selected the eight named ASan+UBSan tests by exact test-name regex and parsed the emitted test-count form. Kept TSan limited to the exact isolation and cold test names. Preserved the initial run logs locally.
- **Files modified:** `tests/sdk/controls.py`
- **Verification:** The final `python3 tests/sdk/controls.py --sanitizers` run passed both lanes and enforced the expected 8/2 test counts and nonzero identities.
- **Committed in:** `4baf32c`

---

**Total deviations:** 2 auto-fixed (Rule 1: 1, Rule 3: 1)
**Impact on plan:** Both corrections enabled exact, reproducible evidence; no runtime finding was hidden or downgraded.

## Issues Encountered

No sanitizer finding was reported. The host denied process inspection, so peak memory could not be measured; this is recorded as unsupported in the testing guide and sanitizer reports. The matching libFuzzer archive was absent, so coverage-guided fuzzing was not run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 02-05 is complete. Plan 02-06 remains unstarted; this plan does not qualify libFuzzer, other host platforms, arbitrary invalid host pointers, or real-game compatibility. Continue only when the user starts the next named GSD step.

---
*Phase: 02-executable-diagnostic-sdk*
*Completed: 2026-10-05*

## Self-Check: PASSED

- The mutation harness, regression manifest, minimizer, and testing guide exist.
- Task commits `d0df265` and `4baf32c` exist and contain their exact task file sets.
- The summary passes the installed summary frontmatter schema and GSD summary validation.
