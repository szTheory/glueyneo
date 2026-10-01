---
gsd_state_version: "1.0"
milestone: v0.1
milestone_name: CPU/bus diagnostic SDK alpha
current_phase: 1
current_phase_name: CPU acceptance experiment
status: planning
stopped_at: Phase 1 context gathered
last_updated: "2026-10-01T15:31:47.033Z"
last_activity: 2026-10-01
last_activity_desc: Created initial roadmap and mapped all 27 requirements; implementation pending.
state_head: d5841dabe742ac21e179ce3013a237c2bac1da2a
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-01)

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 1 — CPU acceptance experiment
**Current milestone:** v0.1 — CPU/bus diagnostic SDK alpha

## Current Position

Phase: 1 of 3 (CPU acceptance experiment)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-10-01 — Created initial roadmap and mapped all 27 requirements; implementation pending.

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: Not measured
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: None
- Trend: Not established

## Accumulated Context

### Decisions

Current decisions: PROJECT.md Key Decisions; dated provenance: preparation/DECISIONS.md.

- v0.1 delivers an actual CPU/bus diagnostic SDK; next milestone outlines interactive graphics/input/sound, real RetroArch macOS, continuation and persistence.
- Phase 1 must set a finite effort/patch budget before CPU adaptation and demonstrate real execution, isolation, state, timing and host safety.
- CPU-05 can record rejection; Phase 1 completion/Phase 2 admission require accepted CPU-01–04 evidence or an explicit reconciled roadmap revision.
- All-C runtime, host-owned I/O and separate ABI/snapshot/replay/durable-save identities remain constraints; no backend or support matrix is qualified yet.

### Pending Todos

None yet.

### Blockers/Concerns

- No current planning blocker. CPU feasibility and FPU/SoftFloat disposition remain Phase 1 admission risks.
- Remote/CI/protection/release authority is not configured; future delivery dependency. Continue independent implementation and artifact preparation; repeat remote triage at setup/shipping.
- No runtime, platform, compatibility or performance claim is verified. All 27 requirements remain pending.

## Deferred Items

Items acknowledged at milestone close (none yet); future scope is outlined in ROADMAP.md.

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-01T15:31:47.009Z
Stopped at: Phase 1 context gathered
Resume file: .planning/phases/01-cpu-acceptance-experiment/01-CONTEXT.md
