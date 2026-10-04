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

## Additive Plan 01-25 independent later-finding disposition

This section appends fresh evidence for the repaired Plan 01-24 source and does
not alter the original frontmatter, timestamps, counterexamples, or findings
above. The previous four open labels and all original reproductions remain
historical. Final reviewed source revision:
`780c720c4e20ac8e9b61eff40da02fbe601a6f38`. Receipt identity: profile
`owned-p01-c14-continuation-2`, collection
`cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738`, source-map
`be6e2c45f9590425a227bb9d6622d7629d080cca778eba29d5304bef3bd13a6d`, amendment
`3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad`. Before
rebinding, exact current snapshot equality passed for all 39 source hashes;
the recorded/current source-map digest, collection hash, profile, and amendment
also match. This is a metadata-only rebind to the committed UAT+README revision,
not another native run. Rebind interval: `2026-10-04T06:48:27Z`–
`2026-10-04T06:50:22Z` UTC (115 active seconds); the exact-source review gate
was rerun after the final report edit.

### CR-01: Continuation rejects reachable state after a supported RTE — resolved within the candidate contract

The independent build command used the Plan 01-21 recipe with the distinct
ignored `build/owned-review25` directory, Debug C17 flags, and `-j2`. It built
in 22 steps; full CTest passed 13/13, including `owned_cpu_state`. Direct
`owned_cpu_state --continuation-only` passed 1/1 and reported 15 named
checkpoints, 90 fresh-owner continuation calls, and source destruction plus
overwrite. The complete state runner passed 5/5 Unity cases. Its malformed
record controls rejected 15 invalid/incompatible records and four null inputs
atomically; instruction-counter, active-operation and terminal guards also
passed without destination mutation or extra bus callbacks.

The former counterexample is reproduced at the guest boundary: a supported
RTE returns PC `$101`, which is captured and restored into a fresh owner. The
next odd fetch enters the local vector-3 address-error event and returns to
`$180`: seven ordered frame writes, vector reads `$000c/$000e`, 50 clocks, zero
completed instructions. Full run result, CPU state, memory and bus events
match the uninterrupted instance over the whole event and subsequent calls.
The companion `SR_switch_odd_USP` checkpoint carries user SR `$0000`, active
odd USP/A7 `$2801`, even inactive SSP `$3000`, and PC `$104`; its next
privileged MOVE-to-SR selects vector 8 on the even supervisor stack (34 clocks,
old SR `$0000`, PC `$104`). It does not access the odd USP and does not show an
odd-stack address error/host fault. Original-silicon saved PC remains unknown.

### CR-02: Earlier exceeded churn can disappear behind a lower final entry — resolved

Normal and optimized `test_contract.py` passed 27/27 each. The
`test_cumulative_churn_cannot_refund_penultimate_threshold_crossing`,
`test_all_cumulative_churn_categories_reject_decreases`,
`test_equal_and_increasing_cumulative_churn_pass`, and combined-limit controls
exercise the earlier-crossing/lower-final counterexample. An additional
temporary-root probe set each of `runtime_added`, `runtime_deleted`,
`test_tool_added`, and `test_tool_deleted` above its cap in one entry, followed
by a lower value. Each rejected with `cumulative_decrease`; the actual ledger
was not changed. No prior charges or thresholds were rewritten.

### WR-01: Sealing rejects resource totals allowed by the frozen validator — resolved

Normal and optimized `test_acceptance.py` passed 22/22 each. Its
`test_budget_check_includes_exact_limits_and_rejects_overages_or_pause`
accepts each exact limit and their combined exact values, rejects each
plus-one value, and rejects an active pause or invalid total. Direct normal
and `-O` probes reproduced all three inclusive exact caps (115,200 active
seconds; 6,000 runtime churn; 8,000 test/tool churn) and rejected each cap plus
one. Contract validation separately preserves the 28,800-second diagnostic
cap and requires pause on an actual cumulative crossing.

### WR-02: README says the implemented owned runtime does not exist — resolved at the reviewed source identity

The historical README at the earlier reviewed revision contains the quoted
false statement that no owned CPU runtime has been implemented. At this
reviewed source revision README describes the private C17 diagnostic runtime
as implemented but unadmitted, links its current contract/subset/amendment/
acceptance/review/receipt, states exact `0x4AFC` exclusion and unknown silicon
saved PC, and keeps CPU requirements Pending / Phase 01 open / Phase 02 gated.
A read-only link scan checked 19 Markdown links; all 19 local targets resolve.
No public SDK, game, board, platform, timing, or performance qualification is
claimed.

The six Unity runner denominators were diagnostic 2/2, semantics 17/17,
timing 25/25, isolation 4/4, faults 5/5, and state 5/5. Python totals were
49/49 in each mode: contract 27/27 and acceptance 22/22 normally, and the same
under `-O`. Executor collection remains separate: four owned lanes passed
13/13 CTests each; it is not counted as reviewer execution. Independent Debug
archive SHA-256 is
`aa27f496ef8981966b100a1d27a4d3e01c8ac4a3f5140aca5d5da0a3f4b9bda5`.

### D1-01 through D1-14 crosswalk

| Decision | Bounded current disposition |
|---|---|
| D1-01 | Owned C17 CPU and private diagnostic slice are present; no production acceptance is inferred. |
| D1-02 | Two rejected Musashi attempts, frozen charges and caps remain preserved; no third adaptation/refund/cap increase. |
| D1-03 | No imported CPU adoption; Unity remains test-only. |
| D1-04 | Small C17 tree; no public CPU ABI, dynamic loader, C++ runtime, or generic framework. |
| D1-05 | Private per-instance state, explicit callback ownership, and fresh destination continuation are bounded by the named tests. |
| D1-06 | Fifteen same-build named boundaries compare architectural state, whole-event results, memory and ordered bus traces; no cross-build claim. |
| D1-07 | Whole static CPU implementation; no mixed opcode handlers or live state conversion. |
| D1-08 | No shipping backend selector or admitted production engine. |
| D1-09 | Exact subset and explicit unsupported result retained. |
| D1-10 | Concrete instruction/event architecture; no unmeasured generator, micro-op framework, or optimization. |
| D1-11 | Primary manual and authored guest ancestry cover named expectations only, not the full ISA or silicon. |
| D1-12 | Correlated emulator output remains comparison evidence, not hardware truth. |
| D1-13 | Original-silicon saved PC for exact `0x4AFC` remains unknown; neither candidate PC inference is selected and the finite search was not repeated. |
| D1-14 | Candidate exclusion is exact numeric `0x4AFC`; retained exception cases remain tested. This is no claim that original hardware rejects ILLEGAL. |

Within this bounded current review, CR-01, CR-02, WR-01 and WR-02 have no
unresolved high/critical finding (0). This is only their candidate-scoped
source/reproduction disposition. It is not a security attestation, hardware
adjudication, final seal, phase verification, requirement completion, or SDK
admission.

### WR-02 README follow-up after owner update

I re-read the changed README in the current worktree. It now describes Plans
01-22 through 01-25 as closing the later review findings with only unqualified,
deferred evidence; names `$gsd-verify-work 01` as the next GSD step; and says
Phase 01 remains open / GAPS_FOUND until verification passes. CPU-01–05 remain
Pending, Phase 02 remains gated, the original-silicon saved PC remains unknown,
and the stale `$gsd-execute-phase 01 --gaps-only` resume instruction is absent.
The first paragraph continues to distinguish an implemented private owned C17
diagnostic runtime from backend admission, a public SDK, and a complete playable
emulator.

Read-only link checking found 19 Markdown links: all 19 are local targets, all
exist, none are external, and none are missing. `git diff --check -- README.md`
returned success. This follow-up interval was 2026-10-04T06:28:29Z through
2026-10-04T06:29:40Z, 71 active seconds. Worktree HEAD remained the provisional
`9fba16b864cf74e3b8a9c97047bb27a5db544b59`; README was dirty and uncommitted.
No build or test was run. The current review report remains provisionally
bound to the prior source receipt and will be rebound only after the UAT+README
commit, as requested. The later final metadata-only rebind is recorded above;
the 19-link outcome and README status conclusions remain unchanged. The final
owned-review gate passed at committed HEAD `780c720c4e20ac8e9b61eff40da02fbe601a6f38`;
its latest report SHA and exact command output were returned to the executor.
