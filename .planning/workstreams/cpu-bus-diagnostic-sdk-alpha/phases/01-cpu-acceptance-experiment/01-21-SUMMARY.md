---
phase: 01-cpu-acceptance-experiment
plan: "21"
subsystem: cpu
tags: [independent-review, asvs-l1, deferred-admission]
requires:
  - phase: "01-20"
    provides: Exact P01-C-14 four-lane qualification
provides:
  - Independent candidate review and native security assessment
  - Exact verified deferred seal with superseded stale receipt preserved
affects: [01-verification, 02]
tech-stack:
  added: []
  patterns: [independent-report-ownership, preserved-derived-seal-recovery]
key-files:
  created: [.planning/phases/01-cpu-acceptance-experiment/01-21-SUMMARY.md]
  modified:
    - experiments/owned_cpu/REVIEW.md
    - .planning/phases/01-cpu-acceptance-experiment/01-SECURITY.md
    - .planning/phases/01-cpu-acceptance-experiment/01-VALIDATION.md
    - experiments/owned_cpu/acceptance-results.json
    - experiments/owned_cpu/budget-ledger.json
key-decisions:
  - "Preserve the stale initial derived seal and independently rebind final metadata without changing source or qualification collections."
  - "Final seal defers admission; hardware saved PC remains unknown and Phase 01 remains incomplete."
requirements-completed: []
actuals:
  tokens: 14148
  tasks: 3
  commits: 5
plan_head_before: a3cec086a75c3c7783bcde610f6e8c4234354eeb
plan_head_after: 1034e058c23e129846619aaeccdf347d1eea7ece
duration: 22min
completed: 2026-10-03
status: complete
coverage:
  - id: D1
    description: Independent exact candidate source and applicable native security controls
    verification:
      - kind: other
        ref: "Independent review native4/4; independent security native8/8+2/2 and normal/optimized validators"
        status: pass
    human_judgment: false
  - id: D2
    description: Exact deferred receipt and independently confirmed final security binding
    verification:
      - kind: other
        ref: "review-check exact931e2f0; seal --defer-admission; verify; budget; independent final assessor read-only confirmation"
        status: pass
    human_judgment: false
---

# Phase 01 Plan 21: Independent candidate review and deferred seal Summary

**Independent source/security gates and the recovered exact seal pass; candidate discrepancies are reconciled while hardware saved PC remains unknown and phase admission stays deferred.**

## Exact final identity

Final independently reviewed/sealed revision: `931e2f07e85a17a9360d74b1b98ed6e1b89e340f`.
Collected source revision remains `7411a33bf63428516a3efee289c393e1a8418b28`.
Profile: `owned-p01-c14-1`.
Collection SHA-256: `53ea6a7162902edea4e4372e85b3713ad4092f0522501c33a59115573101337e`.
Source-map SHA-256: `e63834b8585912d81f99e82e2dd9070139fbc8acc25854e23274105d8cad861b`.
Active amendment SHA-256: `3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad`.
Candidate contract identity: `27af8df79b55f83bffdef63981defc23984fff6b4e0002d10e99621310340419`.
Frozen CONTRACT SHA-256: `6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`.
Final REVIEW SHA-256: `8066d4e2b7e59a301b9f0d1f78ddcc84bcd940c8e5e1106df9741d5710f315ef`.
Final SECURITY SHA-256: `d0fdb6b44290433a89f7d0b53a74e01d298429e4602bba5e4f738b902172b329`.
Final VALIDATION SHA-256: `483d5dba55cab04d98a0f1ecff5dbace669c0dc6434553be2706c39df5459092`.

Final receipt is unqualified/GAPS_FOUND with `defer_admission: true` and exactly `phase-goal-verification-pending`. Current source review is clean; applicable native ASVS L1/block-high attestation is verified with zero current high/critical findings. Independent final read-only assessor confirmation at 21:24:00 UTC passed the exact resulting receipt and closed the live T-01-43 binding gate. The final audit documents deliberately leave the live outcome contingent on the resulting receipt; this SUMMARY records the confirmed outcome without modifying and thereby invalidating the sealed audit hash.

F14-01/F14-02 remain resolved. F14-03 and T-01-15-03 are superseded only for the owner-approved candidate support boundary after concrete reconciliation, qualification, independent source/security assessment and exact final seal passed. The original frame mitigation was withheld and never implemented. Exact `0x4AFC` is candidate-unsupported, with logical fault PC/IR and no frame/vector/dispatch/charge; this does not describe MC68000 silicon behavior. Stronger fault-PC and competing sequential-PC inferences remain preserved, with original-silicon saved PC unknown and the finite search unrepeated. CPU-01–05 remain Pending, Phase01 incomplete/GAPS_FOUND, Phase02 gated, nine specless flags unresolved.

## Tasks and commits

1. `0e2003f` — Task1 fresh non-author source reviewer owned REVIEW only and assessed actual runtime/state/timing/oracle/receipt/rights controls. Independent new ignored Debug build22 steps passed targeted4/4 CTests, direct semantics17/timing25/state5 Unity cases, continuation13 boundaries/78 calls. Reviewer normal and optimized Python each passed contract23 and acceptance21. Executor also ran the specified four Python suites and targeted4/4; exact precommit review-check passed.
2. `6357146` — Task2 separate non-author assessor owned SECURITY/VALIDATION only. Native targeted8/8 plus diagnostic negative/cold2/2, direct timing25/state5 and continuation13/78, exact unsupported wrapper2/2, normal/optimized contract23 and acceptance21 passed. Actual inventory26 fields/10 sources, source39 inputs/artifacts44, current review, frozen rights/history and resource gates passed. Unique T01-29–44 and original T01-15-03 crosswalk were assessed; original threat descriptions and audits remained intact. Required executor contract/verify/inventory and task-map commands passed.
3. `33c2f48` — Task3 initial final confirmations, conservative closeout charges and initial seal. Initial review-check/seal/verify/budget passed at6357146. Later post-audit reseal failed on stale security hash. Executor prematurely committed the partial metadata before inspecting that failed result; this commit alone did not complete Task3.
4. `931e2f0` — Independent assessor preserved the failure, temporarily recorded T01-43 HIGH/open and blocked Task21.3. Earlier native and initial-seal observations stayed historical.
5. `1034e05` — Authorized bounded derived-record recovery, same-reviewer/assessor final confirmation, fresh exact deferred seal and postcommit verification passed. This completes Task3. No runtime, test or validator source changed; no native recollection was required.

The final required chain passed: `review-check --revision HEAD` at931e2f0, `seal --defer-admission --security .../01-SECURITY.md`, read-only `verify`, and `contract.py budget`. After later commits, review-check uses sealed exact931e2f0 instead of moving HEAD. Independent assessor's final read-only verification passed five collections/no lane blockers, exact review/security objects and hashes, source39 inputs, deferred flag and only phase-verification blocker.

## Deviations from Plan

### Preserved stale-seal failure and bounded recovery

The assessor appended actual live-seal outcomes after the first seal, changing SECURITY from `a7bee1df1cf95de27680f6932c25b5c421c9124c1a6e076d447ff4a0203a1f22` to `77c6ff065130fc6df1f7b013c4044266e9c2eec60d9115155b5242c45685535c`. `acceptance.seal()` calls `verify(document)` before writing, so the attempted refresh returned `stale sealed security document`. The independent assessor reproduced that failure at33c2f48 and recorded blocked/high1 metadata. No high finding was waived and clean closeout stopped.

The orchestrator explicitly authorized a narrow recovery inside this plan's owned derived receipt. The full stale seal was preserved verbatim in additive `superseded_seals` history; only its active derived metadata was cleared, with explicit pending-rebinding blocker. Existing unsealed verification passed without changing any collection, source, guard or budget. The same reviewer and assessor independently confirmed the complete superseded seal equals the committed failed-attempt receipt, every prior nonseal/nonblocker receipt field and five collections are unchanged, and current39 source identities match collected bytes. They rebound current attestations to931e2f0. Fresh sealing and exact verification then passed; assessor independently confirmed final T43 closure read-only. The temporary blocked assessment and failed command remain preserved historical evidence. No code repair or weakening of verification occurred.

Task3 includes SECURITY/VALIDATION final metadata updates as required by Task2's final independent binding and actual-outcome reporting, in addition to its declared review/receipt/ledger paths. All changes remained in the plan's overall owned files and non-author ownership was maintained.

## Preservation and accounting

Read-only Python/Git comparison against preplan `a3cec086a75c3c7783bcde610f6e8c4234354eeb` passed repeatedly: all five collections and31 preceding budget entries are unchanged prefixes; all frozen non-entry ledger fields, exact reconciliation/CONTRACT, Plan01-17 records and ten historical Musashi files remain unchanged. Included39 source hashes are unchanged from Plan20; metadata rebinding invents no native rerun. The complete initially stale seal is retained in superseded history.

Three append-only charges total2,835 seconds: review812, security523 and final conservative allowances1500. Final budget is44,170 active seconds/34 records, diagnostic gate2,565, runtime churn1,221, test/tool churn6,126 and no pause. Review charge includes measured reviewer152, earlier conservative allowance300, executor initial-read allowance120 and executor wall interval240. Security charge includes measured assessor270 and executor wall interval253. Wall intervals conservatively include orchestration waits. Final allowances are explicit estimates, not measurements: executor900 for seal/summary/state/commits/reporting, reviewer300 and assessor300. Measured final reviewer116 and assessor205 fit their allowances; total measured assessor475. A transient assessor check syntax error was corrected and charged; no failing behavior was hidden. Reporting/closeout remained within the reserved executor interval.

Realized task/corrective/recovery diff56,589 characters /4 rounded up14,148 estimated tokens. Five commits are measured from the persisted preplan ledger; metadata closeout is separate. All three tasks now pass. Caps, failed-work charges, historical inputs and test denominators were never changed.

## Limitations and scans

No new dependency, public ABI, endpoint/auth path, runtime file access or trust-boundary schema was introduced. No new known stub, skipped test or unrun verification remains: final binding failure was preserved and resolved through independently assessed derived-record recovery. Host evidence remains bounded to the existing native Apple Clang21/Darwin arm64 experiment; no other platform, original-silicon saved PC, full ISA/board/BIOS/gameplay, public snapshot/save/replay or performance qualification is inferred.

## Self-Check: PASSED

All five modified plan artifacts and this SUMMARY exist. All five task/corrective/recovery commits exist. Final current verify and exact sealed-revision review-check passed after recovery commit; preservation checks passed. Self-check establishes this plan's artifacts and evidence, not phase admission.

## Workflow boundary

Plan01-21 complete; Phase01 itself remains incomplete/GAPS_FOUND, CPU-01–05 Pending and Phase02 gated. The concrete next separate command is `$gsd-verify-work 01`. Do not launch that step, another phase or shipping inside this execution.
