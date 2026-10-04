---
phase: 01-cpu-acceptance-experiment
plan: "25"
subsystem: acceptance-evidence
tags: [independent-review, native-security, uat, deferred-seal, budget]
requires:
  - phase: "01-24"
    provides: Current 15-boundary/90-call continuation profile and four-lane receipt
provides:
  - Independent current disposition for CR-01, CR-02, WR-01 and WR-02
  - Preserved 39 historical UAT rows plus four current outcomes
  - Exact-source deferred receipt with final review, security and budget identities
affects: [phase-verification]
actuals:
  tasks: 3
  commits: 2
tech-stack:
  added: []
  patterns: [append-only-qualification, independent-exact-source-binding, deferred-admission]
key-files:
  created:
    - .planning/phases/01-cpu-acceptance-experiment/01-25-SUMMARY.md
  modified:
    - README.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/phases/01-cpu-acceptance-experiment/01-UAT.md
    - .planning/phases/01-cpu-acceptance-experiment/01-REVIEW.md
    - .planning/phases/01-cpu-acceptance-experiment/01-SECURITY.md
    - .planning/phases/01-cpu-acceptance-experiment/01-VALIDATION.md
    - experiments/owned_cpu/REVIEW.md
    - experiments/owned_cpu/acceptance-results.json
    - experiments/owned_cpu/budget-ledger.json
key-decisions:
  - "Disposition the four later findings within the repaired candidate, documentation and resource-control scope; retain the hardware saved-PC result as unknown."
  - "Seal only with admission deferred. CPU-01–05 remain Pending, Phase 01 remains GAPS_FOUND, and Phase 02 remains gated."
  - "Freeze reviewer, security and validation reports before the receipt seal; later metadata commits are checked against the exact sealed revision."
patterns-established:
  - "Preserve historical UAT rows verbatim and append separately sourced exact-current outcomes."
  - "Keep executor lane receipts distinct from fresh non-author reviewer and assessor runs."
requirements-completed: []
coverage:
  - id: CR-01
    description: Independent fresh-owner continuation and state-guard evidence covers the expanded 15/90 profile.
    verification:
      - kind: integration
        ref: "Independent Debug build 22/22 steps; focused CTest 4/4; continuation-only 1/1 with 15 boundaries/90 calls; state 5/5"
        status: pass
    human_judgment: false
  - id: CR-02
    description: Cumulative resource accounting is monotonic and cannot hide a previous threshold crossing.
    verification:
      - kind: unit
        ref: "Contract controls 27/27 normal and optimized; all four decrease probes and prior-crossing/lower-final control reject"
        status: pass
    human_judgment: false
  - id: WR-01
    description: Inclusive caps pass while cap-plus-one and active-pause cases remain rejected.
    verification:
      - kind: unit
        ref: "Acceptance controls 22/22 normal and optimized; exact-cap and plus-one/pause controls pass their expected outcomes"
        status: pass
    human_judgment: false
  - id: WR-02
    description: README status and local navigation match the current unadmitted phase state.
    verification:
      - kind: documentation
        ref: "README status assertions pass; 19/19 local links resolve in executor and independent reviewer checks"
        status: pass
    human_judgment: false
  - id: CLOSEOUT
    description: Independent review, native security, history, budget and exact deferred seal agree.
    verification:
      - kind: integration
        ref: "review-check clean; deferred seal unqualified with phase-goal-verification-pending only; verify and budget pass"
        status: pass
    human_judgment: false
duration: 80min
completed: 2026-10-04
status: complete
---

# Phase 01 Plan 25: Independent review and deferred closeout

**The four Plan 01-25 findings have independent, bounded dispositions and the exact current candidate has a verified deferred seal. Phase 01 remains GAPS_FOUND pending separate phase-goal verification.**

## Performance

- **Duration:** 80 minutes from 2026-10-04T06:08:15Z through closeout.
- **Tasks:** 3.
- **Commits:** 2. The UAT/README/initial-accounting commit is 780c720; the final report, receipt, ledger and planning-state commit follows this summary.
- **Code changes:** No runtime or test source was changed in Plan 01-25.

## Independent review

The separate non-author reviewer configured a fresh ignored Debug build at build/owned-review25, built with two jobs (22/22 build steps), and passed the complete CTest suite (13/13) plus the focused timing, unsupported-opcode, semantics and state set (4/4). Direct runners passed diagnostic 2/2, semantics 17/17, timing 25/25, isolation 4/4, faults 5/5 and state 5/5. The fresh-owner continuation-only runner passed 1/1 with 15 named boundaries and 90 continuation calls. State guards covered 15 malformed records, four null inputs, one counter mismatch, and active/terminal rejection.

Contract controls passed 27/27 in normal Python and 27/27 under -O; acceptance controls passed 22/22 in each mode. The reviewer independently exercised each cumulative decrease category, the prior-threshold/lower-final case, exact caps, plus-one controls and pause rejection. It rechecked README status and all 19 local links.

The review resolves CR-01, CR-02, WR-01 and WR-02 within the candidate continuation, resource-accounting and documentation scope. F14-01 and F14-02 remain resolved. F14-03 is superseded only for the candidate's exact 0x4AFC support boundary; original-MC68000 saved PC remains unknown. The review binds to revision 780c720c4e20ac8e9b61eff40da02fbe601a6f38, collection cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738, profile owned-p01-c14-continuation-2, source map be6e2c45f9590425a227bb9d6622d7629d080cca778eba29d5304bef3bd13a6d, and amendment 3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad.

Final reviewer report SHA-256: e0a4aba91f4a9e21b2c382dbed9b1b74de1cf19484a7a7a45cd69ecd2e797a78. Final review-check status: clean.

## Independent security and validation

A separate non-author assessor used build/security-audit-plan25, built 22/22 Ninja steps, and passed targeted CTest (4/4). Direct continuation passed 1/1 with 15/90; state passed 5/5, including malformed and terminal guards; timing passed 25/25, semantics 17/17 and faults 5/5. The full Python suite passed 59/59 in both normal and optimized modes. Inventory reported 26 owned fields, 10 compiled sources, zero runtime mutable globals and zero callback-owner mutations.

The current native/evidence security assessment is ASVS L1, block-on-high, verified, with zero current high/critical findings. It preserves all historical failures and all nine unresolved historical specless flags. The assessor's post-seal raw comparison passed all 18 checks: the seal's review/security records exactly match current report bytes; all 39 collected source hashes match; the current collection/profile/map/amendment and pending requirements agree; and the budget equals the final ledger.

Final security report SHA-256: a2ffd1aea37e9d5d0b4f31a1c017126127bbe34beded3049658f9673640285c6.

## UAT and documentation

The UAT retains its 39 historical Plan 01-01–01-21 row bodies verbatim and labels the prior 39/39 result as historical scope. Four current rows record CR-01, CR-02, WR-01 and WR-02 with exact commands, tested source revision, denominators and repository-relative evidence. The structural check found 39/39 original rows unchanged and 43/43 current rows passing.

The README now distinguishes an implemented private diagnostic core from backend admission, keeps CPU-01–05 Pending and Phase 02 gated, preserves the unknown saved-PC result, points to $gsd-verify-work 01, and removes the obsolete gap-resume command. All 19 local links resolve.

## Deferred receipt and resource accounting

- **Sealed revision:** 780c720c4e20ac8e9b61eff40da02fbe601a6f38.
- **Collected source revision:** bd390a7f5f6ede0a69df42f8df1fc98905d171ea.
- **Collection:** six records; current SHA-256 cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738.
- **Disposition:** unqualified; defer_admission is true; the sole blocker is phase-goal-verification-pending; no lane blockers.
- **Final budget:** 45 records, 67,834 active seconds, 2,565 diagnostic seconds, 1,228 runtime churn lines and 6,540 test/tool churn lines; no active pause. Original caps are unchanged.

The first post-seal checkpoint identified that the prepaid 900-second closeout allowance had elapsed while awaiting the raw independent comparison. The elapsed overrun and assessor interval were charged, and the receipt was refreshed before final verification. The refreshed seal's budget exactly matches the current ledger.

Several intermediate metadata/control failures are retained: the reviewer's first check lacked the required independence phrase; a pre-rebind check detected a stale report revision; the first ledger draft had an interval-sum mismatch; and one report-edit precondition matched an unexpected count without changing files. Each was corrected before final sealing, with the failure preserved in the reviewer/security/validation/accounting record. No failed behavioral check was rerun or hidden.

## Checks performed

- UAT structure: original 39 rows unchanged; current denominator 43/43, all passing.
- README control: 19 Markdown links, 19/19 local targets resolved; status and next-step assertions pass.
- contract.py validate, contract.py budget, acceptance.py verify, inventory.py check --build-dir build/owned-debug: pass.
- acceptance.py review-check --review experiments/owned_cpu/REVIEW.md --revision 780c720c4e20ac8e9b61eff40da02fbe601a6f38: clean.
- acceptance.py seal --defer-admission --security .planning/phases/01-cpu-acceptance-experiment/01-SECURITY.md: unqualified, admission deferred.
- Sequential read-only acceptance.py verify and contract.py budget: pass after the final budget refresh.
- Independent post-seal identity, source, security, review, requirement and budget comparison: all 18 assertions pass.

## Outcome

Plan 01-25 is complete. CPU-01–05 remain Pending; Phase 01 remains incomplete/GAPS_FOUND; Phase 02 remains gated; original-silicon saved PC remains unknown. No backend or SDK admission is claimed.

## Next step

Stop at the execute-phase boundary. The separate next command is $gsd-verify-work 01; it has not been started.

---
*Phase: 01-cpu-acceptance-experiment*
*Completed: 2026-10-04*
