---
gsd_state_version: "1.0"
milestone: v0.1
milestone_name: CPU/bus diagnostic SDK alpha
current_phase: 01
current_phase_name: CPU acceptance experiment
status: executing
stopped_at: Phase 01 UAT automation is complete; one fresh phase-goal verifier pass remains, with the installed GSD routing workaround recorded.
last_updated: "2026-10-05T01:54:52Z"
last_activity: 2026-10-04
last_activity_desc: Diagnosed stale gaps_found routing; recorded bounded gap-closure rule and direct-verifier workaround.
state_head: 43eec29133b55378299ca8fe153a4c22e3ce3f4f
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 27
  completed_plans: 27
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-03)

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 01 — CPU acceptance experiment
**Current milestone:** v0.1 — CPU/bus diagnostic SDK alpha

## Current Position

Phase: 01 (CPU acceptance experiment) — EXECUTING; phase goal remains open; last GAPS_FOUND report predates Plan 01-27 and must be refreshed
Plan: 27 of 27 — gap-closeout execution complete
Status: UAT and execution evidence are recorded; phase goal remains open pending one fresh verifier pass
Last activity: 2026-10-04 — GSD verification-loop cause and workaround recorded

Progress: [░░░░░░░░░░] 0% (zero of three phases complete)

GSD frontmatter completed_plans counts matching SUMMARY files: 27/27, including Plan 01-17’s answered checkpoint summary. Execution-complete plans are 01-01–01-16 and 01-18–01-27 (26); Plan 01-17 remains incomplete at its answered checkpoint. Plan 01-27 preserved the stale report-binding failure and prior seal, recovered only derived metadata, independently rebound the reports, and reproduced the deferred seal at C2. The current `01-VERIFICATION.md` predates Plan 01-27 and still reports the old binding failure. Installed OpenGSD 1.14.0 routes this `gaps_found` status inconsistently; do not create another gap plan or use `$gsd-execute-phase 01` to refresh it. Dispatch `gsd-verifier` directly once against current evidence, then act only on its fresh findings. The evidence and routing defect are recorded in `.planning/preparation/2026-10-04-gsd-verification-loop.md`.

Current UAT is 49/49 automated checks: rows 1–44 retain their recorded scope, rows 45–48 cover Plans 01-26/27 at the current relevant revision, and row 49 checks README routing. No human UAT checkpoint remains for these machine-observable claims. CPU-01–05 remain Pending. The original-silicon saved PC for candidate-only 0x4AFC exclusion remains unknown. See PROJECT.md, METHODOLOGY.md, preparation/DECISIONS.md and phase 01 UAT for the current contracts and provenance.

## Performance Metrics

**Velocity:**

- Total plans in phase: 27; execution-complete: 26; Plan 01-17 remains at its answered checkpoint; Plan 01-27 closes only the stale report binding
- Average recorded duration: 44.5min across 26 execution-complete plans
- Total recorded execution time: 1,158min; exact owned-core active effort/churn remain in experiments/owned_cpu/budget-ledger.json; Phase 01 remains open pending verification

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 26 of 27 | 1,158min | 44.5min |

**Recent Trend:**

- Last 5 plans with execution metrics: 01-23, 01-24, 01-25, 01-26, 01-27
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

## Accumulated Context

### Decisions

- Phase 01 uses a private owned C17 candidate with explicit host-I/O boundaries and frozen Musashi rejection history; see PROJECT.md and preparation/DECISIONS.md.
- P01-C-14 excludes only exact 0x4AFC from the candidate subset. Original-silicon saved PC remains unknown; do not repeat the finite search or infer hardware truth.
- The candidate remains unqualified. CPU-01–05 remain Pending and Phase 02 remains gated until fresh phase-goal verification passes.
- Phase 01 effort/churn limits and all consumed attempts remain frozen in experiments/owned_cpu/budget-ledger.json. Current closeout validates at 79,763 active seconds with no pause.
- Plan 01-27 changes only derived report/receipt/accounting metadata. C2 binds the exact independent review/security report bytes; source collection remains unchanged.
- The initial project branch has no remote base; no main merge or hosted qualification is implied.

### Pending Todos

- Plan 01-17 remains an answered incomplete checkpoint; do not repeat its finite silicon search. Plans 01-18–01-27 have closed their scoped candidate and evidence gaps. CPU-01–05 remain Pending; Phase 01 is open pending a fresh whole-phase verdict; Phase 02 is gated. Next GSD action: dispatch `gsd-verifier` directly once. `$gsd-verify-work` is UAT-only here, while the installed execute-phase/status routing can skip the needed verifier pass.

### Blockers/Concerns

- Fresh phase-goal verification remains required. The current receipt is unqualified, admission is deferred, and its sole blocker is `phase-goal-verification-pending`. Do not reopen `--gaps` planning until the fresh verifier distinguishes an actionable repository gap from external evidence or a tooling/report defect.
- Original-silicon saved PC, unsupported platforms, public persistence formats, board/BIOS compatibility and performance qualification remain unknown or outside scope.
- Preserve the historical odd-IRQ, fixture-UBSan, reset-accounting/NMI, BSD address-error and malformed-state/zero-request counterexamples.
- Both original Musashi adaptation attempts are consumed. Do not repeat them automatically.

## Deferred Items

Items acknowledged at milestone close (none yet); future scope is outlined in ROADMAP.md.

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-04T23:05:53Z
Stopped at: UAT automation and GSD loop diagnosis recorded; one direct phase-goal verifier pass remains. Do not use the stale gaps_found route to create another plan.
Resume file: None
