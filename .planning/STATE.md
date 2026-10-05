---
gsd_state_version: "1.0"
milestone: v0.1
milestone_name: CPU/bus diagnostic SDK alpha
current_phase: 01
current_phase_name: CPU acceptance experiment
status: executing
stopped_at: Plan 01-28 gap planning and independent checks complete; next step is bounded gap-only execution, followed by one fresh whole-phase verifier.
last_updated: "2026-10-05T14:13:56.640Z"
last_activity: 2026-10-05
last_activity_desc: Planned and independently checked bounded Plan 01-28 for the fresh verifier’s ROADMAP/validator and README route findings.
state_head: 5318efeae1cb3849323841db11a7e462a46c661e
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 28
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

Phase: 01 (CPU acceptance experiment) — READY TO EXECUTE
Plan: 28 of 28 — Plan 01-28 is checked and ready for gap-only execution
Status: Phase 01 remains incomplete. The fresh 2026-10-05 whole-phase verdict is 8/9 GAPS_FOUND; Plan 01-28 targets its bounded CPU-05 documentation/validator gap and stale README route.
Last activity: 2026-10-05 — Plan 01-28 passed independent plan verification; execution is next

Progress: [░░░░░░░░░░] 0% (zero of three phases complete)

GSD frontmatter completed_plans counts existing SUMMARY files: 27/28 plans currently have summaries, including Plan 01-17’s answered checkpoint summary. Execution-complete plans are 01-01–01-16 and 01-18–01-27 (26); Plan 01-17 remains incomplete at its answered checkpoint, and newly planned Plan 01-28 is ready to execute. Plan 01-27 preserved the stale report-binding failure and prior seal, recovered only derived metadata, independently rebound the reports, and reproduced the deferred seal at C2. The fresh `01-VERIFICATION.md` closes that old binding gap and identifies one new current CPU-05 failure: `contract.py validate` and `acceptance.py verify` reject ROADMAP because its admission sentence no longer matches the frozen validator; README also has a stale `$gsd-execute-phase 01` route. Its 244-file fingerprint matched when the verifier wrote it. The subsequent METHODOLOGY/STATE/handoff edits only synchronize workflow records with that verdict; do not rerun goal verification solely for these administrative updates. Do not repeat Plan 01-27 or the full UAT before addressing the fresh findings. Installed OpenGSD 1.15.0 has the previously recorded `gaps_found` routing defect. The exact bounded repair scope is recorded in the verification report and `.planning/preparation/2026-10-04-gsd-verification-loop.md`.

The recorded UAT is 49/49 automated checks, but it predates the ROADMAP wording and README route changes identified by the fresh verifier. No human UAT checkpoint remains for these machine-observable claims; rerun only affected current-revision acceptance and route checks after the bounded repair. CPU-01–05 remain Pending. The original-silicon saved PC for candidate-only 0x4AFC exclusion remains unknown. See PROJECT.md, METHODOLOGY.md, preparation/DECISIONS.md and phase 01 UAT for the current contracts and provenance.

## Performance Metrics

**Velocity:**

- Total plans in phase: 28; execution-complete: 26; Plan 01-17 remains at its answered checkpoint; Plan 01-28 is planned but not executed
- Average recorded duration: 44.5min across 26 execution-complete plans
- Total recorded execution time: 1,158min; exact owned-core active effort/churn remain in experiments/owned_cpu/budget-ledger.json; Phase 01 remains open pending verification

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 26 of 28 | 1,158min | 44.5min |

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
- The candidate remains unqualified. CPU-01–05 remain Pending and Phase 02 remains gated until acceptance reproduction and fresh phase-goal verification pass.
- Phase 01 effort/churn limits and all consumed attempts remain frozen in experiments/owned_cpu/budget-ledger.json. Current closeout validates at 79,763 active seconds with no pause.
- Plan 01-27 changes only derived report/receipt/accounting metadata. C2 binds the exact independent review/security report bytes; source collection remains unchanged.
- The initial project branch has no remote base; no main merge or hosted qualification is implied.

### Pending Todos

- Plan 01-17 remains an answered incomplete checkpoint; do not repeat its finite silicon search. Plan 01-27 closed the prior report-seal finding. The fresh 2026-10-05 verifier found one bounded ROADMAP/validator gap and stale README route; Plan 01-28 is checked and ready. CPU-01–05 remain Pending; Phase 01 is open and Phase 02 is gated. Next exact GSD command: `$gsd-execute-phase 01 --gaps-only`. Execute only Plan 01-28, then pause for one fresh whole-phase `gsd-verifier`; do not run UAT broadly or begin Phase 02 in that step.

### Blockers/Concerns

- Fresh phase-goal verification is current at 8/9 `gaps_found`. The current receipt is unqualified and admission is deferred. The actionable repository gap is the ROADMAP/validator mismatch and stale README workflow route; preserve the semantic pending gate, unknown saved PC, and deferred admission while fixing it. Do not add unrelated scope or repeat the prior security-report binding repair.
- Original-silicon saved PC, unsupported platforms, public persistence formats, board/BIOS compatibility and performance qualification remain unknown or outside scope.
- Preserve the historical odd-IRQ, fixture-UBSan, reset-accounting/NMI, BSD address-error and malformed-state/zero-request counterexamples.
- Both original Musashi adaptation attempts are consumed. Do not repeat them automatically.

## Deferred Items

Items acknowledged at milestone close (none yet); future scope is outlined in ROADMAP.md.

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-05T14:17:13Z
Stopped at: Plan 01-28 is planned, structurally validated and independently checked. Phase 01 remains incomplete at the fresh 8/9 GAPS_FOUND verdict; 26 plans are execution-complete and Plan 01-17 remains an answered checkpoint. Next exact command: `$gsd-execute-phase 01 --gaps-only`. After that bounded execution, pause for one fresh whole-phase `gsd-verifier`; do not repeat `$gsd-plan-phase 01 --gaps` or all 49 historical UAT rows.
Resume file: None
