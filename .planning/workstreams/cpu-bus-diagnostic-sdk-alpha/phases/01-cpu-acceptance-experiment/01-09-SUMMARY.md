---
phase: 01-cpu-acceptance-experiment
plan: "09"
subsystem: owned-cpu-timing
tags: [68000, c17, timing, irq, exceptions]
provides:
  - Manual-derived NOP, RESET, RTE, TRAP, ILLEGAL, privilege, and absolute-word-load paths
  - Level 3/7 interrupt acceptance and bounded short/address-error frames
  - Explicit reset, instruction, IRQ, exception, STOP-idle, and overflow run events
  - Original bus/cycle oracle ledger and wrong-cycle mutation control
affects: [phase-01-execution, owned-cpu-admission]
actuals:
  tokens: 24000
  tasks: 2
  commits: 3
plan_head_before: 9fd9b3a3e9ddf80ffad4cf1cae557333920dbe41
tech-stack:
  added: []
  patterns: [bounded event accounting, manual-backed frame assertions, terminal nested-fault handling]
key-files:
  created:
    - tests/owned_cpu/ORACLE.md
    - tests/owned_cpu/negative_timing.py
    - tests/owned_cpu/test_timing.c
  modified:
    - experiments/owned_cpu/CMakeLists.txt
    - experiments/owned_cpu/SUBSET.md
    - experiments/owned_cpu/cpu.c
    - experiments/owned_cpu/cpu.h
    - tests/owned_cpu/test_diagnostic.c
    - tests/owned_cpu/test_semantics.c
key-decisions:
  - "Charge reset recovery as a one-time 40-cycle event; process instructions and exceptions at whole-event boundaries and idle STOP to the remaining request."
  - "Keep architectural state, ordered 16-bit callbacks, and cycle totals as separate evidence; no prefetch, acknowledge-pin, or board-timing claim is made."
  - "A data/fetch address-error dispatch counts zero completed instructions; TRAP, ILLEGAL, and privilege exception dispatches count one."
duration: 59min
completed: 2026-10-02
status: complete
---

# Phase 1 Plan 09: Timing and exception events

**The named timing and exception slice now runs through bounded guest events, with its frames and callback order recorded separately from cycle evidence.** The owned CPU remains a private experiment and Phase 1 remains open / GAPS_FOUND.

## Accomplishments

- Implemented exact NOP, supervisor RESET, RTE, TRAP #0, canonical ILLEGAL, MOVE.W immediate-to-SR, and MOVE.W absolute-long-to-Dn operations. User execution of STOP, RESET, RTE, or MOVE-to-SR now enters vector 8 before the privileged effect. Supervisor/user stack banking is observed across MOVE-to-SR and RTE.
- Added level 3 masking/unmasking and level 7 edge/held-level behavior. IRQ entry selects the manual autovector and is a separate 44-cycle event. A level 7 edge remains pending after pin deassertion; a held request does not retrigger while the mask remains 7.
- Added short and selected MC68000 address-error frames, odd word/long/fetch detection, 24-bit bus wrap, high-word-first writes, frame/extension/vector read failures, partial writes, and terminal handling for a nested frame or vector fault.
- Defined the run policy and counters: reset40 is consumed once as an event, requests 0..1,000,000 are bounded, completed instructions are never split, stopped idle consumes the exact remainder, event overshoot is reported, and counter additions are checked without wrap. Address-error dispatches count zero; TRAP/ILLEGAL/privilege dispatches count one.
- Recorded exact case expectations and primary manual ancestry in `tests/owned_cpu/ORACLE.md`; updated `SUBSET.md` with the supported boundary and exclusions. Added a supervised wrong-cycle control that accepts only the expected 49-versus-50 assertion.
- Adapted the earlier diagnostic and semantics harnesses to consume reset debt explicitly when they test the original 36 instruction clocks or isolate an instruction. The original guest bytes and expected stored values remain unchanged.

## Verification

- Strict C17 owned-target build passed.
- CTest passed all five cases: `owned_cpu_negative`, `owned_cpu_diagnostic`, `owned_cpu_semantics`, `owned_cpu_timing`, and `owned_cpu_timing_negative` (5 expected, 5 observed). The timing harness reports 23 named passing Unity cases; its supervised mutation produces only the named wrong-cycle assertion.
- The 13 contract unit tests passed. Contract self-tests passed in normal and optimized Python with two positive cases and six named negative controls. `contract.py validate` and `git diff --check` passed.
- One early red regression run identified old semantic tests treating reset debt as already consumed and expecting a long request to stop at STOP without idle time. Test setup now consumes reset debt for instruction-focused cases, and the original guest requests exactly its 36-clock instruction slice. All scoped tests pass under the declared Plan 09 contract.

## Scope limits

Manual clock values qualify only the named events in the declared event policy. The callback trace is a functional 16-bit transaction record, not a per-cycle pin model. Prefetch, trace exceptions, physical interrupt acknowledge, external RESET device behavior, bus-error input, arbitrary mid-instruction suspension, and Neo Geo board timing remain unsupported or unestablished. The manual calls the MC68000 address-error saved PC unpredictable; the fixture's chosen PC is deterministic implementation behavior, not a restart guarantee.

The Plan 09 code and evidence commit is `0d4f1e3`. The effort and cumulative churn receipt is appended to `experiments/owned_cpu/budget-ledger.json` during this execute-phase closeout. CPU-01–05 remain Pending; no backend admission is claimed.

## Next

Continue with Plan 10 in the active gaps-only execute-phase step: prove independent/cold instance behavior, host-fault containment, and a source-bound mutable-state inventory.
