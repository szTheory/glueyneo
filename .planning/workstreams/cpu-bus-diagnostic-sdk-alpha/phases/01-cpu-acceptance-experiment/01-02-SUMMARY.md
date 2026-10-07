---
phase: 01-cpu-acceptance-experiment
plan: "02"
subsystem: cpu
tags: [c17, musashi, isolation, sanitizer, ownership]
requires:
  - phase: 01-01
    provides: Explicit-instance guest and frozen cumulative source/effort audit
provides:
  - Nine-boundary isolated/interleaved/concurrent and cold lifecycle evidence
  - Complete compiled mutable-state inventory and omission controls
  - Allocation and guest-fault containment with actual runtime sanitizer evidence
affects: [01-03, 01-04, 02-executable-diagnostic-sdk]
actuals:
  tokens: 83443
  tasks: 2
  commits: 4
plan_head_before: 01add568906bf2ba2f0af0a2efd3d0a06b673c49
tech-stack:
  added: [test-only pthread lifecycle harness, Clang AST declaration inventory]
  patterns: [explicit boundary observations, failure witness, fatal sanitizer diagnostics]
key-files:
  created: [tests/cpu/test_isolation.c, tests/cpu/test_cold.c, tests/cpu/test_faults.c, experiments/cpu/state-inventory.json, tools/cpu/state_inventory.py, tools/cpu/record_safety.py, experiments/cpu/evidence/plan-01-02/qualification.json]
  modified: [experiments/cpu/cpu_adapter.c, experiments/cpu/cpu_adapter.h, experiments/cpu/CMakeLists.txt, third_party/musashi/m68kcpu.c, tools/cpu/adapt.py, tools/cpu/audit.py]
key-decisions:
  - Preserve the odd IRQ-stack crash and repair live trap ordering within the final adaptation attempt.
  - Treat sanitizer diagnostics as failure even when the test runner exits successfully.
  - Keep CPU requirements and backend admission pending until timing, continuation and final review.
requirements-completed: []
coverage:
  - id: isolation
    description: Independent and cold guest lifecycle observations
    verification:
      - kind: integration
        ref: "ctest --test-dir build/cpu -R '^cpu_(isolation(_negative)?|cold)' --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: safety
    description: Allocation/fault containment and compiled-state completeness
    verification:
      - kind: integration
        ref: "ctest --test-dir build/cpu -L cpu --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: instrumentation
    description: Actual native runtime ASan/UBSan and TSan evidence
    verification:
      - kind: integration
        ref: "experiments/cpu/evidence/plan-01-02/qualification.json"
        status: pass
    human_judgment: false
duration: 21min
completed: 2026-10-01
status: complete
---

# Phase 1 Plan 2: CPU Instance Isolation and Host Safety Summary

**Distinct CPU instances match full boundary observations through interleaved,
parallel and cold execution; malformed guests return terminal faults with
healthy witnesses and clean native sanitizer evidence.**

## Outcome and Accomplishments

Both tasks are complete. Task 1 compares 64 bounded interleavings and 64
concurrent pairs with isolated A/B baselines at nine guest boundaries each.
Sixteen fresh CTest processes each barrier-start two independent constructions
before any backend initialization. Every comparison checks D/A registers,
PC/SR/STOP/IRQ observations, instruction/cycle results, full 4,096-byte RAM
and bounded ordered callback-owner traces. The swapped-baseline control fails
the intended ownership assertion. Each native instance makes one allocation
of 853,104 bytes; measured creation durations remain individual log observations,
not performance guarantees.

The source inventory covers **98 compiled fields/objects**, including seven
immutable globals, retained inactive fields, callback/userdata bindings,
derived tables and host jump/lifecycle state. Independent source review and
Clang AST extraction agree. Removing pending NMI or adding an unclassified
mutable global causes the inventory check to fail. Source hashes bind the
reviewed dispositions to the actual admitted configuration.

Task 2 fails the single actual construction allocation, verifies zero live
allocations and a healthy running witness, and checks invalid requests and
allowed NULL cleanup. Seven guest-fault cases cover reset vectors, fetch,
store, IRQ stack, exception stack, secondary address-error stack failure,
and odd IRQ stack. Terminal instances reject run, inspection and IRQ changes;
reset/destruction remain allowed. Failed reset recovery also retains the
earlier guest regression. Same-instance callback reentry remains unsupported.

Final verification: **25 native CTests in 22.28 seconds**, **5 ASan+UBSan
tests in 2.98 seconds**, and **18 TSan tests in 15.63 seconds**, with no final
sanitizer diagnostic. All three runtime objects carry the requested flags;
the receipt binds their hashes and the actual archive. Native source closure
passes O0/O2, all 13 earlier audit controls pass, and two scratch generations
match the unchanged generated outputs. Source identities, safe relative logs,
native measurements and separate lane outcomes are in
`experiments/cpu/evidence/plan-01-02/qualification.json`.

Toolchain: Apple Clang 21.0.0 (clang-2100.1.1.101), Darwin 25.6.0 arm64,
SDK 26.5; runtime O0 for behavioral lanes. ASan/UBSan adds
`-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer`;
TSan uses `-fsanitize=thread -fno-omit-frame-pointer`. Queried distinct GCC
and Clang executables were unavailable: unsupported, not a passing lane.

## Task Commits

| Task/evidence | Commit |
|---|---|
| Task 1 intentional observation RED | cc053d2 |
| Task 1 isolation/cold/inventory GREEN | fbc1ce0 |
| Task 2 terminal-fault RED | d5a5355 |
| Task 2 containment, audit and instrumented evidence | fc45d7d |

Four commits measured from the persisted ledger before this summary commit.
Actual tokens are ceiling(realized diff characters / 4), including detailed
source-audit logs and inventory, across 28 changed files. No harness token
count is substituted. Execution/closeout interval is approximately
17:42–18:03 UTC; the cumulative ledger deliberately overcharges earlier
preparation and closeout rather than subtracting idle/tool time.

## Budget and Effort

| Cumulative measurement | Actual | Frozen maximum |
|---|---:|---:|
| Substantive attempts | 2 | 2 |
| Handwritten added/deleted lines | 2,489 | 5,000 |
| Helper lines, included above | 404 | 600 |
| Semantic lines, included above | 374 | 500 |
| Handwritten upstream inputs | 6 | 6 |
| Generated files | 2 | 2 |
| Generated lines / bytes | 36,559 / 832,698 | 50,000 / 2,097,152 |
| Charged cumulative seconds | 11,568 | 57,600 |
| Maximum charged attempt seconds | 10,422 | 28,800 |

No cap or prior semantic classification changed. The trap repair and terminal
status changes add a conservative 18 semantic lines. A discarded incorrect
inspector call adds two helper lines beyond committed-transition accounting.
Independent reviews add 360 and 120 seconds. The earlier conservative
3,600-second closeout allowance is retained, not refunded; this closeout is
inside its recorded 18:35:11 UTC bound. Remaining limits must be carried into
later plans; there is no third adaptation attempt.

## TDD Gate Compliance

Task 1 deliberately failed the missing register-observation assertion, then
implemented the private observer and proved full isolation. Task 2 deliberately
failed terminal-instance inspection before fixing its lifecycle behavior.
Both installed RED evidence checks returned `RED_EVIDENCE_OK`; raw assertion
details and narrow TAP translations are committed. The Task 1 record now
accurately records CTest's exit 8. Task 2's GREEN uses a `fix` commit because
it repairs reproduced behavior; no throwaway backend replaced the real runtime.

## Deviations from Plan

1. **Rule 1 — inspector declaration:** a compile error exposed the adapted
   three-argument getter signature. Corrected before Task 1 GREEN; discarded
   line churn is separately charged.
2. **Rule 1 — odd IRQ host crash:** the test reached case 6 then terminated
   with SIGSEGV. The counterexample and final-attempt scope were recorded
   before moving current-call address/bus traps ahead of IRQ stack/vector
   access. The adapter maps unrecoverable HALT to terminal host fault. Recipe,
   source audit and regeneration remain coherent. Commit fc45d7d.
3. **Rule 1 — sanitizer failure in test bus:** initial ASan/UBSan tests exited
   successfully but emitted an intermediate out-of-bounds pointer diagnostic.
   Preserved the failure, parenthesized the validated offset, and made sanitizer
   diagnostics fatal. Affected lanes then passed without diagnostics; no
   suppression or weakened count was used. Commit fc45d7d.
4. **Rule 3 — receipt input discovery:** an old unlinked object remained in the
   reused build directory. The receipt now reads actual Ninja archive inputs
   instead of treating every historical object file as linked runtime.
5. Requirements remain pending despite plan completion: CPU-04 still needs
   continuation, CPU-03 timing and CPU-05 final review. No backend admission
   or Phase 2 authorization is inferred from these narrow results.

No authentication gate or architectural change occurred. The independent
follow-up source/repair review found no blocking issue. Raw diagnostic logs
retain Unity's original whitespace; source path redaction does not rewrite
their behavioral output.

## Known Stubs and Deferred Issues

No new runtime stub or skipped mandatory test remains. Retained upstream
68040 timing TODOs at `third_party/musashi/m68kcpu.c:409` and `:875` concern
unsupported later models, matching the existing WINDOWS.md later-model entry.
The two repaired counterexamples are recorded as fixed in that ledger.

Pending NMI across reset, reset-cycle accounting and complete fresh-instance
continuation remain explicit plan-01-03 obligations. Upstream raw context-copy
APIs are unsuitable: they omit surrounding state and transplant a source-instance
cycle pointer. Do not use them as a continuation implementation. No later plan
was started, no CPU requirement completed and no release-platform claim made.

## Self-Check: PASSED

All declared test, inventory and qualification files exist; all four commits
resolve. The current qualification receipt has nonzero 25/5/18 passing test
counts, three instrumented runtime objects per sanitizer lane, zero final
diagnostics, passing source/budget audits and retained original counterexamples.
The task-1 tracer gate was rerun successfully before task 2.
