---
phase: 01-cpu-acceptance-experiment
plan: "14"
subsystem: owned-cpu-final-review
tags: [c17, independent-review, receipt-integrity, bounded-decision]
requires:
  - phase: 01-cpu-acceptance-experiment Plan 13
    provides: exact-source four-lane qualification receipts
provides:
  - Independent dispositions for prior findings and final collector repair
  - Regression-backed receipt command/configuration and historical-failure guards
  - Sealed reproducible unqualified outcome with explicit contract blocker
affects: [phase-01-gap-planning, cpu-admission]
tech-stack:
  added: []
  patterns: [non-author fixer, independent repair re-review, append-only evidence]
key-files:
  created: [experiments/owned_cpu/ACCEPTANCE.md]
  modified: [experiments/owned_cpu/REVIEW.md, experiments/owned_cpu/source-manifest.json, experiments/owned_cpu/acceptance-results.json, experiments/owned_cpu/budget-ledger.json, tools/owned_cpu/acceptance.py, tests/owned_cpu/test_acceptance.py]
key-decisions:
  - Keep F14-03 open because the frozen ILLEGAL contract conflicts with the implemented/tested saved PC; canonical reconciliation requires user-directed gap planning.
  - Keep CPU-01–05 Pending, Phase 01 open/GAPS_FOUND and Phase 02 gated; bounded decision evidence does not establish admission.
requirements-completed: []
actuals:
  tokens: 65615
  tasks: 3
  commits: 5
  active_seconds: 2771
plan_head_before: 8e26d7c3ffc8dd31b7741cfe2f4ed8d55b248b82
coverage:
  - id: D1
    description: Receipt integrity repairs reject wrong commands/configuration and hidden historical failures
    verification:
      - kind: unit
        ref: python3 -m unittest discover -s tests/owned_cpu -p test_acceptance.py
        status: pass
      - kind: unit
        ref: python3 -O -m unittest discover -s tests/owned_cpu -p test_acceptance.py
        status: pass
    human_judgment: false
  - id: D2
    description: Exact-source independent review and bounded unqualified decision
    verification:
      - kind: other
        ref: python3 tools/owned_cpu/acceptance.py verify
        status: pass
    human_judgment: true
    rationale: F14-03 remains an open canonical contract discrepancy; independent source review and user-directed reconciliation cannot be replaced by passing tests
duration: 30min
completed: 2026-10-03
status: complete
---

# Phase 01 Plan 14: Final independent review and bounded decision Summary

**Two receipt-integrity findings repaired and independently re-reviewed; final four-lane evidence is sealed unqualified because the frozen ILLEGAL saved-PC contract remains contradictory.**

## Accomplishments

All three tasks completed through the plan's explicit non-admitting outcome. A fresh reviewer authored no runtime, collector, tests or fixes. A distinct non-author fixer changed only `acceptance.py` and its direct tests. The reviewer rechecked every Plan 12 finding: BL-01 fixture initialization and WR-01 counter consistency are fixed; restore-over-ready remains inconclusive/unclaimed; historical Musashi defects remain outside the owned closure. All ten immutable historical hashes match.

F14-01 exposed a real receipt whose rehashed ASan configuration and CTest command could be contradicted while verification passed. F14-02 exposed accepted read-only verification omitting the historical fail/unknown/skipped guard. Direct RED counterexamples preceded the repair. Exact commands, build configuration/statuses, compiler/diagnostic output hashes and complete artifact identities now bind receipts; accepted verification shares the historical guard. Independent original reproducers reject, and all 11 identity mutations plus three historical statuses reject. The initial report and counterexamples are preserved at `a43b93e`.

F14-03 remains **HIGH/open**: `CONTRACT.md:61` requires ILLEGAL next PC, while runtime/test/oracle save faulting PC. This is a canonical contract/evidence conflict, not a demonstrated silicon or C safety defect. Runtime/contract mutation is outside the five-path repair scope. User-directed primary-source reconciliation and gap planning are required before admission. The defect is registered as open in `WINDOWS.md`.

## Commits

1. Task 1 — `a43b93e`: initial independent report and first counterexamples.
2. Task 2 — `ca79b00`: distinct non-author collector repair/regressions and refreshed manifest.
3. Task 2 — `34bf236`: fresh four-lane collection and independent re-review.
4. Task 3 — `3cd2d7d`: bounded acceptance report, report-inclusive source manifest and charge tranche.
5. Task 3 — `32deadf`: final independent report, explicit unqualified seal and cumulative accounting.

`actuals.commits` is measured from the persisted pre-plan ledger before summary/metadata commits. `actuals.tokens` is realized diff characters/4, rounded up; full sanitized appended logs dominate this value. No harness token count is used.

## Exact Evidence and Verification

Final collected/reviewed revision: `3cd2d7d5192d0e85ebc4be9f472deace1a4511de`; runtime/tool/test/preset code is unchanged from repair `ca79b00`. Current collection SHA-256: `1b09aaa3d55a9b05db117e81d0aa5a170729654c373770093a75eb63b620838f`; canonical source map: `e0dc3cc73902ee8dbbf215a375ee74dfb515d01ba40a057e9f14b11f3f5ddc6d`; source manifest: `b4800575f955afd9177ae55c780b96a7330469a034b097921016a11cd4ec836b`; independent review: `fb622bdaaedbea8f9a52ec6d6f0eaa72b34742b913e664cc01804be8df3c8b27`.

Three collections are preserved. The final one passes 12/12 CTest cases in each of Debug, Release/O2, ASan+UBSan and optional TSan (48/48). Per lane: Unity diagnostic2, semantics17, timing23, isolation4, faults5 and state5; continuation13 checkpoints, interleaved32 pairs, concurrent32 pairs, cold16 processes and five named negative controls. Reviewer independently executed four lanes12/12 and ASan state10/10 on the same runtime, then direct repair tests; final report/manifest reconciliation is explicitly document-only, with final lane execution performed by the executor.

Commands/results:

- `acceptance.py self-test` normal and `python3 -O`: pass, six rejection/two classification controls.
- Normal and optimized unittest discovery for the collector: pass14/14 in each mode.
- `acceptance.py collect --preset owned-debug --preset owned-release --preset owned-asan-ubsan --optional-preset owned-tsan`: all lanes pass on each refreshed source closure.
- `inventory.py check --build-dir build/owned-debug`: pass26 fields,10 compiled sources,37 final distribution entries, runtime archive only authored CPU.
- `acceptance.py review-check --review experiments/owned_cpu/REVIEW.md --revision 3cd2d7d`: intentionally fails `blocking review finding`; F14-03 is open. It does not sign off acceptance.
- Ordinary `acceptance.py seal`, read-only `acceptance.py verify` and `contract.py budget`: pass for the explicit unqualified/GAPS_FOUND record; no `--require-accepted` claim.
- `contract.py validate`: pass, canonical story valid,10 historical hashes,CPU-01–05 Pending,Phase02 gated. `git diff --check` and public-path/stub scans pass.

Only Darwin25.6.0 arm64/AppleClang21/SDK26.5/Python3.14.4/CMake4.4.3/Ninja1.13.2 is exercised. CMake3.20 exact execution remains unknown; schema2/provisional floor remain unchanged. The report names exact implemented forms and excludes silicon/board timing, full ISA, BIOS/games, public ABI/state/durable-save and gameplay performance. Startup-dominated descriptive samples are not performance qualifications.

## Accounting and Deviations

Through the final-seal tranche, Plan14 charges1,781 summed agent-seconds, cumulative33,506/115,200; diagnostic gate2,565/28,800; runtime churn1,206/6,000 and tooling5,252/8,000. No cap/pause, refund or attempt counter exists. Primary starts and the fixer's pre-clock activity use explicitly conservative inferred allowances; reviewer intervals total704seconds. Closeout work is charged by a further append-only metadata tranche. Frozen historical bytes/caps and all earlier owned entries remain unchanged.

The source manifest is refreshed as a necessary identity dependency of the two authorized tool changes and new report. The actual inventory includes `ACCEPTANCE.md` despite the earlier provenance's general derived-record exclusion prose; the report avoids recursive current collection identity, and a third collection binds its final bytes. This is a Rule3 identity-blocking adjustment, with zero runtime expansion. The collector's scope remains the two planned tool/test paths; no new runtime trust surface or known stub was introduced.

Required review-check commands ran and honestly failed for the open contract blocker; no verify command was skipped. CPU-05 remains Pending because the unresolved canonical decision is narrow and the current contract validator requires the pending gate. Requirement frontmatter is deliberately not mass-marked complete: the plan explicitly requires non-admission on an open high finding.

## Next Workflow Boundary

Final metadata tranche charges another870 seconds through01:53:00Z, giving
2,651 Plan14 agent-seconds and34,376 cumulative seconds, with11 entries.
An additional conservative120-second administration allowance through01:55:00Z
charges final state/commit/reporting, giving2,771 Plan14 and34,496 cumulative
seconds with12 entries; this is an explicit allowance, not an exact spawn clock.
Final nonblank churn remains1,206 runtime and5,252 tooling. The earlier
seal budget is a dated snapshot; final ledger validation remains authoritative.

Phase01 remains open/GAPS_FOUND; Phase02 remains gated. The authorized execute-phase invocation stops here. Review the narrow F14-03 contract reconciliation before selecting a separate GSD planning/verification step; no phase verification, phase completion or Phase02 work ran.

## Self-Check: PASSED

Acceptance report, final independent review, current source manifest and sealed results exist; all five task commits exist. Nonzero final lane counts, exact snapshot equality, fixed counterexample dispositions, open F14-03, historical hashes and cumulative budget were checked from current receipts. No generated untracked files remain.
