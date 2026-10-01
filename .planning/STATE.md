---
gsd_state_version: "1.0"
milestone: v0.1
milestone_name: CPU/bus diagnostic SDK alpha
current_phase: 01
current_phase_name: CPU acceptance experiment
status: in_progress
stopped_at: Completed 01-02-PLAN.md; later plans not started
last_updated: "2026-10-01T18:04:34.002Z"
last_activity: 2026-10-01
last_activity_desc: Plans 01-01 and 01-02 complete; isolation and native sanitizer evidence pass; no backend admitted
state_head: 2bc690ac1701d8e9eed0d82720841bf9af4fcf5e
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 4
  completed_plans: 2
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-01)

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 01 — CPU acceptance experiment
**Current milestone:** v0.1 — CPU/bus diagnostic SDK alpha

## Current Position

Phase: 01 (CPU acceptance experiment) — IN PROGRESS
Plan: 3 of 4
Status: Plans 01-01 and 01-02 complete; plan 01-03 ready, not started
Last activity: 2026-10-01 — Completed isolation, inventory and host-safety evidence; no backend accepted

Progress: [░░░░░░░░░░] 0%

Requirement completion remains 0%; planned Phase 1 tasks are 2/4 plans complete.

## Performance Metrics

**Velocity:**

- Total plans completed: 2
- Average recorded duration: 52.5min
- Total recorded execution time: 105min; conservatively charged effort 11,568 seconds including concurrent review and closeout allowance

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 2 | 105min | 52.5min |

**Recent Trend:**

- Last 5 plans: 01-01, 01-02
- Trend: Not established

**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 84min | 2 tasks | 73 files |
| Phase 01 P02 | 21min | 2 tasks | 28 files |

## Accumulated Context

### Decisions

Current decisions: PROJECT.md Key Decisions; dated provenance: preparation/DECISIONS.md.

- v0.1 delivers an actual CPU/bus diagnostic SDK; next milestone outlines interactive graphics/input/sound, real RetroArch macOS, continuation and persistence.
- Phase 1 must set a finite effort/patch budget before CPU adaptation and demonstrate real execution, isolation, state, timing and host safety.
- CPU-05 can record rejection; Phase 1 completion/Phase 2 admission require accepted CPU-01–04 evidence or an explicit reconciled roadmap revision.
- All-C runtime, host-owned I/O and separate ABI/snapshot/replay/durable-save identities remain constraints; no backend or support matrix is qualified yet.
- Local initialization has no remote fork base. OpenGSD selected sequential execution; `git.branching_strategy` is temporarily `none` so this run uses the existing `chore/initialize-project` feature branch. Restore phase branching when a remote/default base is established; no main merge or hosted qualification is implied.
- [Phase 01, historical]: Initial procedural halt was resolved by approved bounded recovery; frozen budget remains unchanged and no CPU requirement is complete.
- [Phase 01]: Plan 01-01 completed under unchanged cumulative caps; native guest and source audits pass, CPU requirements and backend admission remain pending.
- [Phase 01]: Plan 01-02 proves selected isolation and host containment within unchanged caps; timing, continuation and final CPU admission remain pending.

### Pending Todos

None yet.

### Blockers/Concerns

- Native private guest, source closure, FPU/SoftFloat exclusion, selected isolation and host safety pass. Complete qualified timing, fresh-instance continuation and final review before CPU admission.
- Preserve the odd IRQ crash and UBSan fixture counterexamples and repairs. Plan 01-03 must resolve pending NMI/reset behavior and reset-cycle accounting; raw upstream context-copy APIs cannot prove continuation.
- Remote/CI/protection/release authority is not configured; future delivery dependency. Continue independent implementation and artifact preparation; repeat remote triage at setup/shipping.
- Evidence is limited to the native experiment; no supported platform, compatibility or performance claim is established. All 27 requirements remain pending.
- Two substantive adaptation attempts are consumed. Preserve cumulative caps in later plans; no automatic further adaptation attempt is authorized. Phase 2 remains blocked on full CPU acceptance.

## Deferred Items

Items acknowledged at milestone close (none yet); future scope is outlined in ROADMAP.md.

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-01T18:04:33.978Z
Stopped at: Completed 01-02-PLAN.md; later plans not started
Resume file: None
