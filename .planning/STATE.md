---
gsd_state_version: "1.0"
milestone: v0.1
milestone_name: CPU/bus diagnostic SDK alpha
current_phase: 01
current_phase_name: CPU acceptance experiment
status: "Plan 01-29 executed; independent bounded accept recommendation recorded; Phase 01 awaits a separate fresh verifier"
stopped_at: "Plan 01-29 complete; Phase 01 remains incomplete; next: direct gsd-verifier whole-phase assessment per the handoff"
last_updated: "2026-10-05T19:34:02Z"
last_activity: 2026-10-05
last_activity_desc: "Plan 01-29 executed with an independent accept recommendation; execution is complete and fresh phase-goal verification is next"
state_head: 54136cf0ce36a57238debfa0c1e027c6b626c14f
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 29
  completed_plans: 29
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-03)

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 01 — CPU acceptance experiment
**Current milestone:** v0.1 — CPU/bus diagnostic SDK alpha

## Current Position

Phase: 01 (CPU acceptance experiment) — AWAITING FRESH VERIFICATION
Plan: 29 of 29 executed (Plan 01-17 remains an answered incomplete checkpoint)
Status: latest whole-phase verifier is GAPS_FOUND (9/10) and predates Plan 01-29; the bounded admission recommendation is accept_recommended, but no phase admission has occurred
Last activity: 2026-10-05 — Plan 01-29 execution and closeout

Progress: [░░░░░░░░░░] 0% (zero of three phases complete)

GSD completed_plans counts SUMMARY files: 29 summaries exist for 29 planned plans, including Plan 01-17’s answered checkpoint. Execution-complete plans are 01-01–01-16 and 01-18–01-29 (28); Plan 01-17 remains incomplete. Plan 01-28 restored the exact ROADMAP admission literal and canonical README navigation. Plan 01-29 produced an independent recommendation; its separate whole-phase verification is still required. Plan 01-27's deferred seal, sources, reports and receipts remain unchanged; the budget ledger has one append-only Plan 01-29 charge.

At Task 1 revision `4945f348cf67777f3f90f87ef8331250a2c7add9`, the admission checker and 14 original controls passed normal and optimized Python. The preservation return-path defect was fixed at `54136cf0ce36a57238debfa0c1e027c6b626c14f`; the suite now passes 15/15 in both modes. Independent CPU and ASVS L1/high-block reports bind the unchanged candidate; CPU-01–05 are assessed sufficient and zero HIGH/CRITICAL security blockers remain. Current admission/contract/budget/acceptance checks pass with the receipt deliberately unqualified. Plan 01-29 adds current automated evidence after historical UAT rows 1–51; it does not replay them. The latest fresh whole-phase report remains 9/10 `GAPS_FOUND` and predates this recommendation. Do not repeat Plan 01-29 or historical UAT; request exactly one separate whole-phase verifier.

CPU-01–05 remain Pending; candidate admission deferred, Phase 01 open, Phase 02 gated and original-silicon saved PC unknown. See PROJECT.md, METHODOLOGY.md, preparation/DECISIONS.md and Phase 01 UAT for scope and provenance.

## Performance Metrics

**Velocity:**

- Total plans in phase: 29; execution-complete: 28; Plan 01-17 remains at its answered checkpoint; Plans 01-28 and 01-29 are executed
- Average recorded duration: 44.2min across 28 execution-complete plans
- Total recorded execution time: 1,237min; exact owned-core active effort/churn remain in experiments/owned_cpu/budget-ledger.json; Phase 01 remains open pending verification

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 28 of 29 | 1,237min | 44.2min |

**Recent Trend:**

- Last 5 plans with execution metrics: 01-25, 01-26, 01-27, 01-28, 01-29
- Trend: Not established

**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 84min | 2 tasks | 73 files |
| Phase 01 P02 | 21min | 2 tasks | 28 files |
| Phase 01 P03 | 22min | 2 tasks | 28 files |
| Phase 01 P04 | 31min | 2 tasks | 13 files |
| Phase 01 P05 | 10min | 3 tasks | 8 files |
| Phase 01 P06 | 5min | 1 tasks | 4 files |
| Phase 01 P07 | 56min | 3 tasks | 9 files |
| Phase 01 P08 | 43min | 2 tasks | 11 files |
| Phase 01 P09 | 59min | 2 tasks | 14 files |
| Phase 01 P10 | 37min | 2 tasks | 10 files |
| Phase 01 P11 | 79min | 2 tasks | 11 files |
| Phase 01 P12 | 119min | 4 tasks | 8 files |
| Phase 01 P13 | 23min | 3 tasks | 9 files |
| Phase 01 P14 | 30min | 3 tasks | 7 files |
| Phase 01 P15 | 12min | 2 tasks | 2 files |
| Phase 01 P16 | 15min | 3 tasks | 5 files |
| Phase 01 P18 | 13min | 2 tasks | 10 files |
| Phase 01 P19 | 18min | 3 tasks | 8 files |
| Phase 01 P20 | 6min | 2 tasks | 4 files |
| Phase 01 P21 | 22min | 3 tasks | 5 files |
| Phase 01 P22 | 23min | 2 tasks | 7 files |
| Phase 01 P23 | 44min | 2 tasks | 6 files |
| Phase 01 P24 | 196min | 2 tasks | 7 files |
| Phase 01 P25 | 79min | 3 tasks | 10 files |
| Phase 01 P26 | 6min | 2 tasks | 3 files |
| Phase 01 P27 | 110min | 3 tasks | 8 files |
| Phase 01 P28 | 6min | 2 tasks | 7 files |
| Phase 01 P29 | 73min | 2 tasks | 11 files |

## Accumulated Context

### Decisions

- Phase 01 uses a private owned C17 candidate with explicit host-I/O boundaries and frozen Musashi rejection history; see PROJECT.md and preparation/DECISIONS.md.
- P01-C-14 excludes only exact 0x4AFC from the candidate subset. Original-silicon saved PC remains unknown; do not repeat the finite search or infer hardware truth.
- The candidate remains unqualified. CPU-01–05 remain Pending and Phase 02 remains gated until acceptance reproduction and fresh phase-goal verification pass.
- Phase 01 effort/churn limits and all consumed attempts remain frozen in experiments/owned_cpu/budget-ledger.json. Plan 01-29 adds a 6,463-second all-agent charge; final contract totals are 86,226 active seconds and 6,540 contract-measured test/tool churn, with no pause.
- Plan 01-27 changes only derived report/receipt/accounting metadata. C2 binds the exact independent review/security report bytes; source collection remains unchanged.
- The initial project branch has no remote base; no main merge or hosted qualification is implied.
- [Phase 01]: Plan 01-28 routes README through canonical STATE; preserve Pending CPU requirements and pause for a separate fresh whole-phase verifier.
- [Phase 01]: The fresh 2026-10-05 whole-phase report remains GAPS_FOUND (9/10) and predates Plan 01-29. Plan 01-29 produced an independent accept recommendation for CPU-01–05, with zero applicable HIGH/CRITICAL security findings; it did not admit the receipt or phase. The separate fresh phase verifier is the next workflow boundary. Do not repeat the 9/10 pass, Plan 01-29, historical UAT rows or silicon search. Phase 02 remains gated and CPU-01–05 remain Pending.

### Pending Todos

None yet.

### Blockers/Concerns

- Original-silicon saved PC, unsupported platforms, public persistence formats, board/BIOS compatibility and performance qualification remain unknown or outside scope.
- Preserve the historical odd-IRQ, fixture-UBSan, reset-accounting/NMI, BSD address-error and malformed-state/zero-request counterexamples.
- Both original Musashi adaptation attempts are consumed. Do not repeat them automatically.
- Fresh 2026-10-05 whole-phase verification is 9/10 GAPS_FOUND and predates the Plan 01-29 recommendation. No backend or phase is admitted; CPU-01–05 remain Pending and Phase 02 remains gated. The current independent recommendation is accept_recommended with a narrow WR-01 documentation warning; a separate direct gsd-verifier pass must decide the phase goal. If that pass finds a blocker, plan only the distinct missing evidence or repair and do not re-run this same-evidence assessment.

## Deferred Items

Items acknowledged at milestone close (none yet); future scope is outlined in ROADMAP.md.

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-05T19:34:02Z
Stopped at: Plan 01-29 execution and closeout complete; Phase 01 awaits one direct whole-phase gsd-verifier assessment
Resume file: .planning/phases/01-cpu-acceptance-experiment/.continue-here.md
