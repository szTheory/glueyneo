---
phase: 01-cpu-acceptance-experiment
reviewed: 2026-10-03T21:34:39Z
depth: standard
files_reviewed: 40
files_reviewed_list:
  - AGENTS.md
  - CMakeLists.txt
  - CMakePresets.json
  - README.md
  - experiments/cpu/ACCEPTANCE.md
  - experiments/cpu/REVIEW.md
  - experiments/cpu/acceptance-results.json
  - experiments/cpu/evidence/plan-01-05/prior-REVIEW.md
  - experiments/cpu/evidence/plan-01-05/prior-acceptance-results.json
  - experiments/owned_cpu/ACCEPTANCE.md
  - experiments/owned_cpu/CMakeLists.txt
  - experiments/owned_cpu/CONTRACT.md
  - experiments/owned_cpu/PROVENANCE.md
  - experiments/owned_cpu/REVIEW.md
  - experiments/owned_cpu/SUBSET.md
  - experiments/owned_cpu/acceptance-results.json
  - experiments/owned_cpu/budget-ledger.json
  - experiments/owned_cpu/cpu.c
  - experiments/owned_cpu/cpu.h
  - experiments/owned_cpu/illegal-reconciliation.json
  - experiments/owned_cpu/source-manifest.json
  - experiments/owned_cpu/state-inventory.json
  - tests/owned_cpu/ORACLE.md
  - tests/owned_cpu/cold.py
  - tests/owned_cpu/isolation_fixture.h
  - tests/owned_cpu/negative.py
  - tests/owned_cpu/negative_timing.py
  - tests/owned_cpu/test_acceptance.py
  - tests/owned_cpu/test_cold.c
  - tests/owned_cpu/test_contract.py
  - tests/owned_cpu/test_diagnostic.c
  - tests/owned_cpu/test_faults.c
  - tests/owned_cpu/test_inventory.py
  - tests/owned_cpu/test_isolation.c
  - tests/owned_cpu/test_semantics.c
  - tests/owned_cpu/test_state.c
  - tests/owned_cpu/test_timing.c
  - tools/owned_cpu/acceptance.py
  - tools/owned_cpu/contract.py
  - tools/owned_cpu/inventory.py
findings:
  critical: 2
  warning: 2
  info: 0
  total: 4
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-10-03T21:34:39Z
**Revision:** `2e237a73c986cbb1cbc16a2e3a982874913303cb`
**Diff base:** `6f38c21d61825bfd14c8f84293247aaa301821d5`
**Depth:** standard
**Files Reviewed:** 40
**Status:** issues_found

## Summary

The resolved scope contains the owned C17 runtime, build configuration, tests, evidence validators, provenance and retained rejection history. Findings concern loss of continuation at a reachable supported instruction boundary, bypass of cumulative churn enforcement, inconsistent resource limits and incorrect current documentation. The existing passing receipts and Plan 01-21 clean assessment do not cover these counterexamples.

Project instructions and current project/phase contracts were read. No project skill directories were present; the configured agent-skills map was empty. No structural pre-pass or external reviewer evidence was supplied. File citations below are complete repository-relative paths to preserve public repository hygiene.

## Narrative Findings (AI reviewer)

### Critical Issues

### CR-01: Continuation rejects reachable state after a supported RTE

**Classification:** BLOCKER
**Severity:** Critical
**Status:** open
**File:** `experiments/owned_cpu/cpu.c:887-894`
**Related:** `experiments/owned_cpu/cpu.c:432-436`, `experiments/owned_cpu/cpu.c:295-307`, `experiments/owned_cpu/cpu.c:919`, `experiments/owned_cpu/SUBSET.md:24-32`, `tests/owned_cpu/test_state.c:486`

**Issue:** The state validator requires an even PC, although supported RTE commits the PC from a short frame without that restriction. A normal guest short frame containing SR `0x2700` and return PC `0x101` therefore leaves a ready, idle, nonterminal instance which can be observed and run, but cannot be captured or restored. The next run enters the already implemented odd-fetch address-error path. Capturing between these two events is necessary to preserve that continuation; a destination cannot reproduce it through the state API. The analogous active-stack alignment restriction can also reject a deferred stack fault after an accepted stack-bank switch. Treating an odd PC as malformed in the state tests encodes the mismatch rather than proving that such a boundary is unreachable.

**Evidence:** A temporary C17 harness compiled the current `cpu.c` with private hooks, using ordinary reset and bus callbacks and a six-byte RTE frame. It executed reset debt and requested one event at a time. The independently observed output was:

```text
RTE reason=8 pc=101 clocks=20 capture=1 ready_observe=0
next reason=8 pc=180 clocks=50 capture=0
```

Here `8` is `OWNED_CPU_BUDGET`, `1` is `OWNED_CPU_INVALID_ARGUMENT`, and `0` is `OWNED_CPU_OK`. No execution-state seed was needed. This is a candidate API/continuation defect; it makes no claim about ILLEGAL saved PC or silicon restart fidelity.

**Fix:** Allow reachable odd PC and stack-pointer values in the private continuation record while retaining the S-selected A7/bank consistency check. Preserve them exactly so the next run performs the same address-error or terminal-stack-fault event. Replace the unconditional odd-PC corruption expectation with genuinely invalid metadata checks and add fresh-owner continuation after RTE returning an odd PC, including subsequent frame bytes, ordered bus effects and cycle/result comparisons. If these boundaries are intentionally excluded, explicitly restrict the accepted execution/continuation contract and report the capability limit at that boundary rather than presenting the returned state as ordinarily capturable.

### CR-02: Earlier exceeded churn can disappear behind a lower final entry

**Classification:** BLOCKER
**Severity:** Critical
**Status:** open
**File:** `tools/owned_cpu/contract.py:346-355`
**Related:** `tools/owned_cpu/contract.py:368-376`, `experiments/owned_cpu/CONTRACT.md:133-142`

**Issue:** `validate_budget` checks that every cumulative churn value is a nonnegative integer, but never checks that the four cumulative fields are nondecreasing. It then evaluates thresholds only against the final entry. An earlier entry can exceed the frozen runtime/test-tool threshold and a later lower value can remove the crossing without an explicit owner scope review. This violates the contract's cumulative, no-refund accounting and pause-on-crossing policy. Both scope validation and acceptance budget gates consume this result, so an internally inconsistent ledger can be presented as passing and unpaused. The submitted ledger is currently monotonic; the finding concerns the enforcement failure, not an accusation that its actual charges were refunded.

**Evidence:** A read-only in-memory substitution of the current ledger changed only the penultimate entry's `runtime_added` to `6001`, leaving its existing deletions and the final entry intact. Actual `validate_budget()` returned:

```text
status=pass
runtime_churn_added_deleted=1221
pause=None
```

The earlier cumulative runtime churn exceeded 6,000, but was ignored. No receipt or ledger file was modified.

**Fix:** Track the preceding cumulative values and reject decreases in every added/deleted category with a named error. Evaluate threshold crossings throughout the entry sequence and require the explicit authorized pause/resolution record for a historical crossing. Add controls for a decreased category, an earlier crossing followed by an under-threshold final record, and a legitimate monotonic history. Keep current historical bytes and charges intact.

### Warnings

### WR-01: Sealing rejects resource totals allowed by the frozen validator

**Classification:** WARNING
**Severity:** Warning
**Status:** open
**File:** `tools/owned_cpu/acceptance.py:411-416`
**Related:** `tools/owned_cpu/contract.py:350-351`, `tools/owned_cpu/contract.py:368-369`, `tests/owned_cpu/test_acceptance.py:272-277`

**Issue:** `budget_check` requires effort and both churn totals to be strictly less than their caps. `validate_budget` permits effort equal to 115,200 seconds and pauses churn only when it is greater than 6,000/8,000. A total exactly at an authorized limit therefore passes the canonical validator but cannot be sealed, even with `status: pass`. This introduces an undocumented stricter limit and an unnecessary pause/replan. The existing acceptance unit test explicitly expects this inconsistent rejection.

**Evidence:** Direct in-memory calls to `budget_check` with otherwise passing nonzero totals rejected effort exactly `EFFORT_CAP_SECONDS` with `budget requires pause/replan`, and runtime churn exactly `RUNTIME_CHURN_CAP` with `churn threshold requires pause/replan`.

**Fix:** Use inclusive upper bounds consistent with the frozen contract and retain rejection when the canonical validator reports a pause. Share the boundary policy or constants through one validator. Change the boundary controls to accept the exact authorized limits and reject limit-plus-one and explicit paused status. Do not alter the frozen cap values.

### WR-02: README says the implemented owned runtime does not exist

**Classification:** WARNING
**Severity:** Warning
**Status:** open
**File:** `README.md:5-9`

**Issue:** The current repository entry point says “no owned CPU runtime has been implemented” and describes Plans 01-07–01-14 as upcoming gap closure. The scoped `cpu.c`, native tests and current Plan 01-21 receipt establish an implemented private candidate, with phase admission still pending. The statement conflates implementation with admission and prevents a fresh contributor from discovering the actual candidate and its current evidence. This violates the project's requirement to update stale instructions when behavior changes; it is a factual status defect rather than a wording preference.

**Fix:** State that an owned private diagnostic runtime is implemented but remains unadmitted, link the current subset/acceptance record and explain that Phase 01 verification remains pending. Describe the active frozen contract plus P01-C-14 amendment, retaining the exact `0x4AFC` capability exclusion and unknown silicon saved PC. Remove the outdated implementation claim and completed-plan instructions without promoting any public SDK or hardware qualification.

## Review evidence and limits

Full source review covered the resolved scope and relevant called validators, private state hooks and build/test contracts. Focused reproductions were the temporary compiled RTE harness and read-only in-memory budget probes above. Existing CTest suites and sanitizer lanes were not rerun; submitted passing results remain historical evidence, not evidence against these new boundary cases. The temporary harness and its binary were removed automatically. No tracked source, test, receipt, ledger or planning-state file was modified; only this report was replaced. No commit was made.

Exact canonical `0x4AFC` remains excluded under P01-C-14. The prior Musashi rejection and original-MC68000 saved-PC uncertainty remain historical, unchanged findings outside the revised candidate claim. This report establishes neither silicon truth, backend admission, phase completion nor Phase 02 readiness.

---

_Reviewed: 2026-10-03T21:34:39Z_
_Reviewer: the agent (gsd-code-reviewer), independent of implementation_
_Depth: standard_
