---
gsd_state_version: "1.0"
milestone: v0.1
milestone_name: CPU/bus diagnostic SDK alpha
current_phase: 01
current_phase_name: CPU acceptance experiment
status: "Phase 01 verifier: GAPS_FOUND (9/10); admission remains unqualified"
stopped_at: "Phase 01 whole-phase verification complete: GAPS_FOUND (9/10); phase incomplete; next: $gsd-plan-phase 01 --gaps"
last_updated: "2026-10-05T16:31:14.150Z"
last_activity: 2026-10-05
last_activity_desc: "Fresh whole-phase Phase 01 verifier: GAPS_FOUND (9/10); one CPU admission outcome remains unresolved"
state_head: 6e9a0ca70c83e2c8bca7c64d5ab8ed5f83a87533
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 28
  completed_plans: 28
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-03)

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 01 — CPU acceptance experiment
**Current milestone:** v0.1 — CPU/bus diagnostic SDK alpha

## Current Position

Phase: 01 (CPU acceptance experiment) — OPEN / GAPS_FOUND
Plan: 28 of 28 (execution complete; Plan 01-17 remains an answered incomplete checkpoint)
Status: Phase 01 verifier: GAPS_FOUND (9/10); admission remains unqualified
Last activity: 2026-10-05 — fresh Phase 01 whole-phase verification completed

Progress: [░░░░░░░░░░] 0% (zero of three phases complete)

GSD completed_plans counts SUMMARY files: 28/28 summaries exist, including Plan 01-17’s answered checkpoint. Execution-complete plans are 01-01–01-16 and 01-18–01-28 (27); Plan 01-17 remains incomplete. Plan 01-28 restored the exact ROADMAP admission literal and canonical README navigation, with regression controls outside the sealed candidate closure. Plan 01-27's deferred seal, sources, reports, receipts and ledger remain unchanged.

At Task 1 revision 612c24558d010eef2cbc14958a7d34e1b8b208ef, contract controls passed 1/1, documentation controls 5/5 and local links 20/20; contract validate and acceptance verify passed with six collections, no lane blockers and an unqualified disposition. Code-review hardening at `73a422dc7dd7149bb5c7cb8b1cde9528cc20338f` expands the docs regression to 8/8 with six negative controls; standard-depth review is clean. UAT records 51/51: 49 historical rows plus two current documentation rows, not a replay of all 51 at the current revision. The previous 2026-10-05 whole-phase verdict is 8/9 GAPS_FOUND and predates this repair. A separate fresh whole-phase assessment must reconcile it before any more gap planning or phase admission.

CPU-01–05 remain Pending; candidate admission deferred, Phase 01 open, Phase 02 gated and original-silicon saved PC unknown. See PROJECT.md, METHODOLOGY.md, preparation/DECISIONS.md and Phase 01 UAT for scope and provenance.

## Performance Metrics

**Velocity:**

- Total plans in phase: 28; execution-complete: 27; Plan 01-17 remains at its answered checkpoint; Plan 01-28 is executed
- Average recorded duration: 43.1min across 27 execution-complete plans
- Total recorded execution time: 1,164min; exact owned-core active effort/churn remain in experiments/owned_cpu/budget-ledger.json; Phase 01 remains open pending verification

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 27 of 28 | 1,164min | 43.1min |

**Recent Trend:**

- Last 5 plans with execution metrics: 01-24, 01-25, 01-26, 01-27, 01-28
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

## Accumulated Context

### Decisions

- Phase 01 uses a private owned C17 candidate with explicit host-I/O boundaries and frozen Musashi rejection history; see PROJECT.md and preparation/DECISIONS.md.
- P01-C-14 excludes only exact 0x4AFC from the candidate subset. Original-silicon saved PC remains unknown; do not repeat the finite search or infer hardware truth.
- The candidate remains unqualified. CPU-01–05 remain Pending and Phase 02 remains gated until acceptance reproduction and fresh phase-goal verification pass.
- Phase 01 effort/churn limits and all consumed attempts remain frozen in experiments/owned_cpu/budget-ledger.json. Current closeout validates at 79,763 active seconds with no pause.
- Plan 01-27 changes only derived report/receipt/accounting metadata. C2 binds the exact independent review/security report bytes; source collection remains unchanged.
- The initial project branch has no remote base; no main merge or hosted qualification is implied.
- [Phase 01]: Plan 01-28 routes README through canonical STATE; preserve Pending CPU requirements and pause for a separate fresh whole-phase verifier.
- [Phase 01]: Fresh 2026-10-05 whole-phase verification is GAPS_FOUND (9/10); Plan 01-28 closed the prior documentation/routing gap. The verifier step is complete; do not repeat it before addressing the current admission outcome. Next: $gsd-plan-phase 01 --gaps; Phase 02 remains gated. — Current 01-VERIFICATION.md confirms contract and receipt integrity but no accepted backend; CPU-01–04 remain Pending.

### Pending Todos

None yet.

### Blockers/Concerns

- Original-silicon saved PC, unsupported platforms, public persistence formats, board/BIOS compatibility and performance qualification remain unknown or outside scope.
- Preserve the historical odd-IRQ, fixture-UBSan, reset-accounting/NMI, BSD address-error and malformed-state/zero-request counterexamples.
- Both original Musashi adaptation attempts are consumed. Do not repeat them automatically.
- Fresh 2026-10-05 whole-phase verification is 9/10 GAPS_FOUND: Plan 01-28 closed the former documentation/routing gap, but no owned CPU backend is admitted and CPU-01–04 remain Pending. Next: make a current evidence-backed admission decision or revise the roadmap target; Phase 02 remains gated.

## Deferred Items

Items acknowledged at milestone close (none yet); future scope is outlined in ROADMAP.md.

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-05T16:30:28.150Z
Stopped at: Phase 01 whole-phase verification complete: GAPS_FOUND (9/10); phase incomplete; next: $gsd-plan-phase 01 --gaps
Resume file: .planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md
