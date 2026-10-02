---
phase: 01-cpu-acceptance-experiment
plan: "06"
subsystem: cpu-direction
tags: [68000, governance, rejection, replanning]
requires:
  - phase: 01-05
    provides: Structured rejected/GAPS_FOUND disposition and preserved historical evidence
provides:
  - Actual option C selection with discussion-only authorization boundaries
  - Preserved consumed attempts, charges, caps and SDK admission gate
affects: [backend-replanning-discussion, phase-01-verification, phase-02-admission]
actuals:
  tokens: 4508
  tasks: 1
  commits: 1
plan_head_before: 57b49c97eadc0b340657b18478a8fed36c2e2fd2
tech-stack:
  added: []
  patterns: [explicit workflow authorization boundary]
key-files:
  created:
    - .planning/phases/01-cpu-acceptance-experiment/01-06-DIRECTION.md
    - .planning/phases/01-cpu-acceptance-experiment/01-06-SUMMARY.md
  modified: [.planning/STATE.md, .planning/ROADMAP.md]
key-decisions:
  - "Developer selected C: reject/defer the current Musashi candidate and discuss backend replanning; no further source work or scope change authorized."
  - "Investigate an owned C 68000 core and possible strangler-style transition only as upcoming discussion proposals, prioritizing correctness and efficiency."
requirements-completed: [CPU-05]
duration: 5min
completed: 2026-10-02
status: complete
---

# Phase 1 Plan 06: Backend direction Summary

**The developer selected rejection/deferral of the current Musashi candidate and a separate backend replanning discussion, with every experiment limit and admission gate preserved.**

## Accomplishments

Recorded the actual option C response supplied to this fresh continuation, replacing the pending checkpoint status. The next named step is discuss backend replanning, after the execute-phase workflow/model pause. The developer prefers building as much as possible themselves and considering a strangler-style migration; correctness and an efficient path take priority. The next discussion must compare architecture, CPU emulation, testing and oracle ancestry, maintainability, dependency and integration tradeoffs under METHODOLOGY.md.

An owned C 68000 core behind a narrow private replacement seam is a proposal for that discussion. No implementation, final backend choice, cap change or roadmap/milestone rescope is settled or authorized. Source work, another adaptation attempt, phase verification and Phase 02 execution remain outside this plan.

Both consumed attempts remain consumed. Charges remain 2,614 handwritten / 523 helper / 483 semantic lines; 20,005 cumulative / 18,859 final-attempt seconds; six upstream files; two generated files totaling 36,559 lines / 832,698 bytes. Caps remain two attempts; 57,600 cumulative / 28,800 per-attempt seconds; six upstream files; 5,000 handwritten / 600 helper / 500 semantic lines; two generated files / 50,000 lines / 2,097,152 bytes. Governance effort adds no adaptation charge or refund.

CPU-05's previously completed bounded-decision obligation is retained. CPU-01–04 remain Pending, Phase 01 open / GAPS_FOUND, and Phase 02 gated. Plan completion does not qualify the backend or complete the phase.

## Task Commits

1. **Choose the next separately authorized backend path** — `af1d7b8` (docs).

The persisted ledger measures one task commit at summary creation; final metadata is committed separately. Actuals use realized diff characters / 4, rounded up, rather than harness usage.

## Verification

Read-only precondition checks confirmed plan 01-05's complete summary and passed self-check, current rejected/GAPS_FOUND receipt, blocking review reason, and six critical plus two medium unresolved findings. Prior plan commits exist. The exact plan 01-06 automated artifact check passed, as did scoped whitespace checking. Consent fidelity was checked against the actual supplied response: C is selected, preferences remain proposals, and only the next named discussion/planning step is authorized.

No build, CPU/sanitizer execution, regeneration or phase verification was required or run. Historical archives, receipt, source, budget ledger and tests were unchanged. No new runtime surface or implementation stub was introduced.

## Deviations from Plan

None — plan executed within the actual checkpoint response and its stated boundaries. Git metadata writes required a sandbox escalation because the repository's Git directory is read-only in the default sandbox; the authorized task commit succeeded after escalation.

## Next Step

Pause after execute-phase for user review/model selection. The proposed next named step is discuss backend replanning. This executor starts neither that discussion nor planning nor phase verification.

## Self-Check: PASSED

Both created plan artifacts exist; task commit `af1d7b8` exists. The plan artifact check and whitespace check passed. The actual response is recorded with unchanged admission and accounting boundaries.
