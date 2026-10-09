---
status: diagnosed
trigger: "Phase 05 G-05-3: selected guest executes through the 256-chunk hard bound without a source-defined guest-written attract/start checkpoint"
created: 2026-10-09T19:30:00Z
updated: 2026-10-09T19:31:00Z
---

## Current Focus

hypothesis: The native qualifier cannot report attract/start because it has no source-defined guest-written predicate or acceptance branch; the selected guest's actual progress remains unclassified.
test: Enumerate all qualifier result paths and compare the exposed observation fields with the UAT acceptance contract and sanitized run outcome.
expecting: The qualifier emits only fault, stop, budget and setup/error statuses, with no reachable attract/start result.
next_action: Hand this diagnosis to Phase 05 gap planning; define a guest-state predicate from rights-clear source and bounded private observation before any acceptance claim.
bug_class: Bohrbug in qualification logic; selected-guest progression is an unresolved evidence gap.
candidate_causes:
  - "code: qualifier lacks a selected attract/start predicate and result path"
  - "config: 256-chunk ceiling may end before the relevant transition, if one exists"
  - "data: selected guest may follow an unmodeled hardware path, but tracked data cannot establish that"
and_gate: "No for the observed inability to classify attract/start: absent predicate alone prevents acceptance. Whether actual guest progression also requires more hardware behavior is unknown."

## Symptoms

expected: The selected normalized game and BIOS execute through the owned core to an independently source-defined guest-written attract/start predicate.
actual: The selected pair imports and executes, then reaches the hard 256-chunk bound without an unsupported event or accepted attract/start predicate.
errors: No unsupported event reported in the sanitized tracked result.
reproduction: Run the ignored local selected-pair qualification; only its sanitized tracked summary is in scope for this diagnosis.
started: Phase 05 Plan 05-03 remains halted; prior archive mapping failure was resolved during this plan.

## Eliminated

- hypothesis: The former archive-to-region mapping failure still prevents guest execution.
  evidence: Sanitized 05-03 receipt reports selected import, native guest execution, 32,255,007 instructions and 256,000,794 cycles.
  timestamp: 2026-10-09T19:31:00Z
- hypothesis: The run stopped at a reported unsupported CPU or bus event.
  evidence: Sanitized 05-03 receipt reports hard-budget exhaustion without an unsupported event; qualifier's fault paths are separate.
  timestamp: 2026-10-09T19:31:00Z

## Evidence

- timestamp: 2026-10-09T00:00:00Z
  checked: Phase 05 UAT and 05-03 plan
  found: G-05-3 requires direct source-defined guest-written attract/start; successful import, guest execution, and the first unsupported event are insufficient.
  implication: A budget stop cannot close the gap even if all public synthetic tests pass.

- timestamp: 2026-10-09T19:31:00Z
  checked: tools/mvs/mvs_qualify.c complete main loop and result paths
  found: The 256-iteration loop handles native errors, bus faults, CPU faults and STOP; after the loop it unconditionally prints guest_instruction_budget_exhausted. It contains no attract_start literal, guest-written state check or acceptance branch.
  implication: The qualifier cannot positively classify attract/start, even if the guest reaches it during an iteration.

- timestamp: 2026-10-09T19:31:00Z
  checked: include/glueyneo/glueyneo.h observation shape and src/instance.c observation/run implementation
  found: The exported MVS observation exposes generic bus fault, video/output latch, palette-bank and watchdog fields. gn_run_mvs reports budget, stop, fault or error and does not return a selected-title checkpoint.
  implication: The present public observation contract has no independently defined selected guest mode/state signal for the qualifier to test.

- timestamp: 2026-10-09T19:31:00Z
  checked: tests/mvs/test_mvs.c and tests/mvs/test_mvs_qualification.py
  found: The public boot checkpoint is a synthetic work-RAM sentinel followed by STOP; the qualification Python test deliberately rejects a spoofed attract_start status. Neither proves selected-title attract/start.
  implication: Passing public tests cannot fill the selected-guest evidence gap.

- timestamp: 2026-10-09T19:31:00Z
  checked: 05-03-SUMMARY.md and 05-VALIDATION.md sanitized final result
  found: The selected run exhausted 256 chunks after 32,255,007 instructions and 256,000,794 cycles, with device-state changes and watchdog pets but no accepted checkpoint. Fetch-ring provenance was checked privately against the normalized buffer.
  implication: Guest execution is established; the observed activity does not identify an attract/start transition or a specific missing board behavior.

- timestamp: 2026-10-09T19:31:00Z
  checked: src/instance.c MVS IRQ and audio state
  found: The MVS interrupt acknowledge path explicitly says there are no modeled IRQ producers; the audio selection state is only a latch and validation expressly makes no sound-handshake claim.
  implication: These are plausible future guest-path dependencies, but the sanitized evidence does not prove that either caused this run's budget exhaustion.

## Resolution

root_cause: "The Phase 05 qualifier has no source-defined guest-written attract/start predicate or success branch, so the bounded selected run can only end as fault, stop or budget exhaustion. The underlying selected guest's progress and any additional required hardware behavior remain unknown from tracked sanitized evidence."
fix: "Diagnosis only. Derive a selected guest mode/state transition from source-qualified private observation, expose the minimal per-instance guest-write signal, and test it with rights-clear positive and wrong-behavior controls. Then rerun bounded qualification; investigate hardware behavior only from observed events."
verification: "Static exhaustive qualifier result-path inspection agrees with sanitized Plan 05-03 budget result; no private media or traces read and no code fix attempted."
files_changed: []
