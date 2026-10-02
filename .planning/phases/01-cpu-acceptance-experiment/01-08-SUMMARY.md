---
phase: 01-cpu-acceptance-experiment
plan: "08"
subsystem: owned-cpu-diagnostic
tags: [68000, c17, diagnostic, accounting]
provides:
  - Private per-instance C17 CPU for the original arithmetic/store diagnostic
  - Exact supported instruction subset, boundaries, and unsupported outcomes
  - Passing original guest, semantics cases, and supervised mutation control
  - Measured first diagnostic gate with source and CTest identities
affects: [phase-01-execution, owned-cpu-admission]
actuals:
  tokens: 17671
  tasks: 2
  commits: 5
plan_head_before: ea75296497482c9c407798c378beb0debd7a98ba
tech-stack:
  added: [Owned C17 CPU target, test-only Unity integration]
  patterns: [per-instance mutable state, explicit bus callbacks, bounded instruction progress]
key-files:
  created:
    - experiments/owned_cpu/cpu.c
    - experiments/owned_cpu/cpu.h
    - experiments/owned_cpu/SUBSET.md
    - tests/owned_cpu/test_diagnostic.c
    - tests/owned_cpu/test_semantics.c
    - tests/owned_cpu/negative.py
  modified:
    - CMakeLists.txt
    - experiments/owned_cpu/CMakeLists.txt
    - experiments/owned_cpu/budget-ledger.json
    - tools/owned_cpu/contract.py
    - tests/owned_cpu/test_contract.py
key-decisions:
  - "Build this private whole-CPU experiment only when GLUEYNEO_OWNED_CPU_EXPERIMENT is selected; it is not a public ABI or accepted backend."
  - "Keep guest PC and effective addresses 32-bit and apply the 24-bit mask only at bus callbacks; preserve ordered partial writes on callback failure."
  - "The diagnostic gate passed in 2,565 seconds; later admission obligations remain open."
duration: 43min
completed: 2026-10-02
status: complete
---

# Phase 1 Plan 08: Owned CPU diagnostic slice

**The original guest now runs on a private owned C17 CPU, and the first diagnostic gate passed with measured effort and churn.**

## Performance

- **Duration:** 43 minutes, measured conservatively from the first Plan 08 behavioral test at 19:07 UTC through gate recording at 19:49:45 UTC
- **Tasks:** 2
- **Plan-scoped source, tests, and ledger files changed:** 11

## Accomplishments

- Added an opt-in, target-scoped C17 owned CPU experiment. Its instance owns registers, status, timing counters, STOP/IRQ inputs, and execution state. Bus and allocator callbacks plus userdata are explicit and per instance. The owned build omits the rejected candidate, generator, FPU/SoftFloat, and Musashi targets.
- Implemented reset-vector reads and the contracted `MOVEQ`, `ADDQ.L` register-direct, `MOVE.L Dn,(abs.L)`, and supervisor `STOP` path. Guest PC/effective addresses retain 32-bit values; callbacks apply the 24-bit physical mask. Callback faults stop the instance until reset/destruction and ordered long writes retain a successful first word if the second fails.
- The unchanged original fixture computes and stores 10 at `0x1000` and 16 at `0x1004`. Both diagnostic cases stop after four instructions at PC `0x10e`, with 36 instruction cycles separate from the 40 reset cycles. Zero budget makes no callbacks or state changes.
- Added 17 semantic cases for register fields, sign/CCR behavior, quick value zero meaning eight, overflow/carry, STOP stack-bank switching, unsupported opcode/mode reporting, odd addresses, incomplete fetch, host faults, 24-bit bus masking, and defined 32-bit wrapping. `SUBSET.md` records exact implemented and unsupported behavior, timing sources, and limitations.
- The supervised `--mutate` control changes the result from 10 to 11 and accepts only the named `guest arithmetic/store result` assertion failure. CTest log parsing was corrected against the host's real `LastTest.log` format and now uses each current test block, with regression coverage for stale failure logs and current failures.
- The gate receipt records tested source commit `d8c5450ff40fc5121605d8429773098caac29f2c`, build identity, original fixture hashes, all three passing CTest targets, 2,565 diagnostic seconds, and cumulative churn of 517 runtime lines and 1,623 test/tool lines added plus deleted. This remains within the 8-hour diagnostic gate, 6,000 runtime-line cap, and 8,000 test/tool-line cap.

## Task Commits

1. **Gate churn control and red diagnostic:** `fce061c`, `905586f`
2. **Owned CPU, exact subset, semantics, and mutation control:** `49c6ba9`
3. **Current CTest receipt parser and regressions:** `d8c5450`
4. **Measured diagnostic gate receipt:** `2d092da`

## Files Created/Modified

- `experiments/owned_cpu/cpu.c` and `cpu.h` — private CPU instance, lifecycle, reset, execution, and observation seam.
- `experiments/owned_cpu/SUBSET.md` — implemented operations, behavior, timing, and explicit exclusions.
- `tests/owned_cpu/test_diagnostic.c`, `test_semantics.c`, and `negative.py` — original guest, boundary cases, and exact mutation supervisor.
- `tools/owned_cpu/contract.py` and `tests/owned_cpu/test_contract.py` — cumulative measurement plus CTest receipt parsing and controls.
- `experiments/owned_cpu/budget-ledger.json` — measured diagnostic receipt and cumulative budget status.
- `CMakeLists.txt` and `experiments/owned_cpu/CMakeLists.txt` — opt-in whole-core target and scoped test registration.
- `.planning/ROADMAP.md`, `.planning/STATE.md`, and `.planning/phases/01-cpu-acceptance-experiment/.continue-here.md` — current plan position and next-step handoff.
- `.planning/phases/01-cpu-acceptance-experiment/01-08-SUMMARY.md` — this plan receipt.

## Verification

- The owned CMake configure and C17 build passed. CTest passed `owned_cpu_negative`, `owned_cpu_diagnostic`, and `owned_cpu_semantics` (3 expected, 3 observed); the diagnostic's 2 Unity cases and all 17 semantics cases passed.
- The negative control passed only after observing the exact `Expected 10 Was 11:guest arithmetic/store result` assertion in its child process. The direct unmutated diagnostic passed both scenarios.
- The contract unit command python3 -m unittest discover -s tests/owned_cpu -p test_contract.py passed 13 tests. Contract self-tests passed in normal and optimized Python with two positive cases and six named negative controls each.
- `contract.py validate` and `contract.py budget --require-diagnostic-gate` passed. The canonical story is valid with no errors, ten historical files are unchanged, CPU-01–05 remain Pending, and Phase 02 remains gated.
- The simultaneous CPU-option configuration control rejected both whole-core experiments as required. The configured target inventory contains the owned CPU and no rejected candidate, generator, guest-runtime, or Musashi target.

## Decisions & Deviations

The first gate record attempt found that `_test_results` expected a different CTest log presentation than the installed CTest emits. A regression reproduced the mismatch, then the parser was fixed to inspect per-test blocks in `LastTest.log` and a fresh passing receipt was recorded. Auxiliary status from earlier runs is not treated as the current run's result. No CPU contract or threshold changed.

This slice does not implement exception frames or IRQ acceptance/wakeup, NOP or later instruction families, a complete 68000, board timing, durable/public state, or backend admission. The test-only register seed hook is private to the experiment test build.

## Next Phase Readiness

Plan 09 can now qualify the named interrupt, exception, instruction-boundary timing, and bus limits. Phase 01 remains open / GAPS_FOUND; CPU-01–05 remain Pending until all current evidence is reviewed and fresh phase verification supports a disposition. Phase 02 remains gated.
