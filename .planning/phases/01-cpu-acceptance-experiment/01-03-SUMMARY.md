---
phase: 01-cpu-acceptance-experiment
plan: "03"
subsystem: cpu
tags: [c17, musashi, timing, continuation, sanitizer]
requires:
  - phase: 01-02
    provides: Explicit instance ownership, complete source inventory and host-fault containment
provides:
  - Manual-qualified signed request, reset, IRQ, STOP and selected exception timing
  - Explicit guest-only state with fresh-destination continuation and atomic rejection
affects: [01-04, 02-executable-diagnostic-sdk]
actuals:
  tokens: 85242
  tasks: 2
  commits: 4
plan_head_before: 1059403df9e8e465f7a16e6c0935abb2158a9aa4
tech-stack:
  added: []
  patterns: [field-wise private state codec, destination-owned bindings, consequential state mutation controls]
key-files:
  created: [tests/cpu/test_timing.c, tests/cpu/test_state.c, tests/cpu/state_negative.py, experiments/cpu/evidence/plan-01-03/qualification.json]
  modified: [experiments/cpu/cpu_adapter.c, experiments/cpu/cpu_adapter.h, experiments/cpu/state-inventory.json, third_party/musashi/m68kcpu.c, third_party/musashi/m68kcpu.h, tools/cpu/adapt.py, tools/cpu/state_inventory.py]
key-decisions:
  - Retain the qualified IRQ-entry-plus-first-instruction boundary and document its exact accounting.
  - Preserve raw arithmetic flag intermediates and copy every guest field explicitly while retaining destination host bindings.
  - Keep CPU requirements and backend admission pending for plan 01-04 and independent phase verification.
requirements-completed: []
coverage:
  - id: timing
    description: Signed budgets and selected instruction/exception timing with primary-manual oracles
    verification:
      - kind: integration
        ref: "ctest --test-dir build/cpu -R '^cpu_(timing|faults|isolation|budget)$' --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: continuation
    description: Eight source-destroyed continuation checkpoints, malformed atomicity and consequential controls
    verification:
      - kind: integration
        ref: experiments/cpu/evidence/plan-01-03/qualification.json
        status: pass
    human_judgment: false
duration: 22min
completed: 2026-10-01
status: complete
---

# Phase 1 Plan 3: CPU Timing and Complete Continuation Summary

**Selected 68000 instruction/exception timing and eight fresh-destination
continuations pass through a private explicit guest-state codec within the
unchanged source, effort and attempt caps.**

## Outcome

Both tasks are complete. No backend is admitted, no CPU requirement is marked
complete, and no later plan was executed. Four task commits are measured from
the persisted plan ledger before this summary commit. Actual tokens are
ceiling(realized diff characters / 4), including source, tests and evidence,
across 28 changed files; they are not model token consumption. Execution and
closeout took approximately 22 minutes, ending around 18:28 UTC.

## Timing Evidence

Eight Unity timing cases cover zero, negative and out-of-range requests;
one/exact/neighboring instruction budgets; reset 39/40/41 returning 40/40/44;
maximum 1,000,000 stopped idle; reset debt consumed exactly once; RESET
instruction 132; masked IRQ/unmask/STOP/resume/RTE; TRAP, illegal, privilege and
address error. Returned elapsed cycles, completed dispatches and overshoot are
distinct. Split 40+12 and combined 52 reach the same guest boundary.

Primary oracle: Motorola MC68000UM ninth edition, Tables 8-12/8-14,
pp. 8-10–8-11; normal and address-error frames in Figures 6-5/6-7,
pp. 6-10/6-17; exception semantics in sections 6.3.1–6.3.9. PRM 1992,
pp. 6-83–6-85 covers RESET/RTE/STOP. Exact original encodings, references,
ancestry and limits are recorded in `tests/cpu/ORACLE.md`.

IRQ entry 44 shares an existing call boundary with ADDQ 8, returning 52 and one
completed instruction. Unmasking MOVE-to-SR 16 plus IRQ 44 returns 60 at handler
entry. These are qualified backend boundaries, not inflated hardware IRQ
timings. Ordinary frames and restored SR/PC/SP are checked. Address error 50
returns before the handler, with status/address/IR/SR frame observations and
zero completed dispatches. Native Apple/BSD sigsetjmp is exercised, not disabled.

## Continuation Evidence

The private fixed-width record explicitly captures register banks, saved
registers, PC/previous PC/IR, raw arithmetic flags, masks, STOP, prefetch,
pending reset/IRQ/NMI, instruction/run modes, address-error metadata and
instruction observations. Raw flag intermediates remain full-width because
the backend stores arithmetic results and masks their relevant bits.

Destination creation builds private dispatch/cycle tables; restore reconstructs
model constants and table pointers. Allocator, bus callbacks and userdata remain
destination-owned. Jump frames are installed only by a new active call. Inactive
later-model storage stays invariant zero under this API. Request-local cycle
scratch is normalized with next-use overwrite proof in the inventory.

Eight checkpoints cover reset debt, populated prefetch, STOP, masked level 3,
latched level 7 with pins subsequently low, illegal exception entry, address-error
entry and post-RTE normal modes. Each source is destroyed and its host storage
overwritten before six continuation calls. Every guest record field, all RAM,
ordered bus observations, destination owner and actual progress match an
uninterrupted baseline. Twenty-five malformed records reject atomically and
continue like an untouched witness. Active callback capture/restore rejects.

Two supervised mutations fail exact guest-result assertions: removing pending
NMI produces D1=0 instead of 1; changing prefetched ADDQ#3 to ADDQ#5 produces
D0=12 instead of 10. Crashes, timeouts and unrelated failures do not qualify.
Compiled inventory now covers 99 fields/objects, seven immutable globals, and
checks every guest mapping against both codec directions. Three controls reject
omitted NMI, missing codec mapping and introduced shared mutable storage.

## Verification

Final native **28/28 CTests passed in 37.53 seconds**; **8/8 ASan+UBSan passed
in 5.25 seconds**; **18/18 TSan passed in 18.69 seconds**. No final sanitizer
diagnostic was present. Runtime source was unchanged between the instrumented
runs; the final native/ASan runs also include the reviewed malformed-test
isolation correction. The receipt verifies three actual runtime objects per
lane, instrumentation flags, archive hashes, manifest/inventory/ledger hashes,
sanitized logs and nonzero expected test counts.

Native O0/O2 source closure, all earlier audit controls and two independent
regenerations pass. Generated output remains 36,559 lines/832,698 bytes.
Toolchain is Apple Clang 21.0.0, Darwin 25.6.0 arm64, SDK 26.5. Distinct queried
GCC/Clang lanes remain unavailable, not passing. Public-path scan found no
personal paths in changed tracked material; public noreply commit identity was
retained. No files were deleted.

## Task Commits

| Task/evidence | Commit |
|---|---|
| Task 1 intentional request RED | 63b67d4 |
| Task 1 timing GREEN | 8c71731 |
| Task 2 intentional absent-state-contract RED | 6cb6606 |
| Task 2 continuation and final evidence GREEN | 14e7be1 |

## Budget

| Cumulative charge | Actual | Frozen cap |
|---|---:|---:|
| Substantive attempts | 2 | 2 |
| Handwritten added/deleted lines | 2,611 | 5,000 |
| Helper lines, included above | 520 | 600 |
| Semantic lines, included above | 483 | 500 |
| Original upstream inputs | 6 | 6 |
| Generated outputs | 2 | 2 |
| Generated lines / bytes | 36,559 / 832,698 | 50,000 / 2,097,152 |
| Cumulative charged seconds | 15,065 | 57,600 |
| Maximum charged attempt seconds | 13,919 | 28,800 |

The unchanged ledger preserves every prior charge. This plan charges 109
additional semantic lines, including the entire codec C/header change rather
than excluding its ownership plumbing, four discarded helper lines and a
conservative margin. Independent review adds 515 seconds. The attempt 2 executor
interval is conservatively charged from 16:40 through 18:50 UTC, retaining the
prior 3,600-second closeout overcharge as well. These are upper-bound charges;
no refund or allowance reset occurred. This closeout finished before 18:50.

## Deviations and Preserved Counterexamples

1. **Rule 1 — reset accounting/NMI:** request 41 returned 4 rather than 44, and
   reset retained a stale NMI edge. Preserved before the attempt 2 ownership
   amendment and minimal core/recipe repair in 8c71731.
2. **Rule 1 — BSD address-error boundary:** native address error returned 58
   rather than 50 because the BSD macro continued into ADDQ. Preserved before
   extending ownership to the internal header and reproducing the generic
   exhausted-budget return. Recipe parity and regeneration pass. Commit 8c71731.
3. **Test-oracle corrections:** reset does not guarantee CCR, so normal frames
   compare the recorded pre-exception SR; actual 68000 RTE explicitly clears
   instruction/run modes, so tests distinguish exception entry from post-RTE.
   No backend change or relaxed expected hardware behavior was used.
4. **Rule 1 — reviewed adapter boundaries:** inconsistent reset-state records
   were accepted; zero work near the instruction-counter limit was rejected.
   Failing assertions precede stricter temporary validation and corrected guard
   order. Final malformed cases independently exercise each reset flag.
   Commit 14e7be1; repaired deviations are WINDOWS entries 6 and7.
5. Evidence bookkeeping refreshed recipe/source identities and reconciled
   charged duration with the ledger's exact interval arithmetic before final
   passing audits. No source cap or mandatory verification was waived.

No authentication gate or architectural change occurred. Scope extensions
were limited to the original six inputs, recipe and necessary evidence tools.

## TDD Gate Compliance

Both installed RED checks returned RED_EVIDENCE_OK and precede GREEN commits.
Task 1 asserts rejected oversized work before the private contract changes.
Task 2's initial RED asserts absence of the state API; behavioral continuation,
atomicity and mutation tests then qualify the implementation. This initial
API-availability assertion alone is not continuation evidence. The tracer gate
was rerun successfully before task 2. There are no skipped mandatory tests.

## Limits and Known Stubs

No new runtime stub remains. Retained upstream later-model timing TODOs remain
the pre-existing WINDOWS entry 3; those models are not qualified. This private
same-build typed record requires a complete live allocation and separate host
memory copying. It is not an arbitrary byte-buffer parser or public durable
snapshot format. Host faults are terminal and do not quantify partial progress
or roll back prior bus writes. Guest bus-error fidelity, bus-cycle suspension,
board/BIOS/game compatibility and release platforms remain unsupported or
unqualified. Final CPU acceptance is plan 01-04 work.

## Self-Check: PASSED

All declared test/summary/evidence files exist and all four task commits resolve.
Current manifest, inventory and ledger hashes match the qualification receipt;
all three nonempty passing lane logs match their recorded hashes. The final
budget and regeneration receipts pass, with no uncommitted runtime source.
