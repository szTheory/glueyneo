---
gsd_state_version: "1.0"
milestone: v0.1
milestone_name: CPU/bus diagnostic SDK alpha
current_phase: 01
current_phase_name: CPU acceptance experiment
status: paused
stopped_at: User requested pause before 01-04 independent review; workflow/model checkpoints enabled
last_updated: "2026-10-01T19:35:26Z"
last_activity: 2026-10-01
last_activity_desc: GSD health audited; only non-repairable W019 methodology-registry mismatch and expected 01-04 incomplete-plan info; awaiting authorization for Task 2
state_head: 6be55c2fd1ea402fe36f55774ed5226e968908b3
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 4
  completed_plans: 3
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-01)

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 01 — CPU acceptance experiment
**Current milestone:** v0.1 — CPU/bus diagnostic SDK alpha

## Current Position

Phase: 01 (CPU acceptance experiment) — PAUSED BY USER
Plan: 4 of 4
Status: Plans 01-01 through 01-03 complete; 01-04 Task 1 complete; paused before Task 2 independent review
Last activity: 2026-10-01 — User requested model/workflow pause; saved review-pending collection and discussion preferences

Progress: [░░░░░░░░░░] 0%

Requirement completion remains 0%; Phase 1 has 3/4 plans complete, with Task 1 of plan 01-04 complete. Candidate status is ready-for-review / GAPS_FOUND, not accepted.

## Performance Metrics

**Velocity:**

- Total plans completed: 3
- Average recorded duration: 42.3min
- Total recorded execution time: 127min; conservatively charged effort 19,265 seconds including review and closeout allowances; plan 01-04 remains incomplete

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 127min | 42.3min |

**Recent Trend:**

- Last 5 plans: 01-01, 01-02, 01-03
- Trend: Not established

**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 84min | 2 tasks | 73 files |
| Phase 01 P02 | 21min | 2 tasks | 28 files |
| Phase 01 P03 | 22min | 2 tasks | 28 files |

## Accumulated Context

### Decisions

- [User clarification 2026-10-01]: Pause between named GSD workflow steps for review and model selection; no automatic chaining. Apply METHODOLOGY.md for relevant role analysis, adversarial synthesis, and small, flat dependency decisions.

Current decisions: PROJECT.md Key Decisions; dated provenance: preparation/DECISIONS.md.

- v0.1 delivers an actual CPU/bus diagnostic SDK; next milestone outlines interactive graphics/input/sound, real RetroArch macOS, continuation and persistence.
- Phase 1 must set a finite effort/patch budget before CPU adaptation and demonstrate real execution, isolation, state, timing and host safety.
- CPU-05 can record rejection; Phase 1 completion/Phase 2 admission require accepted CPU-01–04 evidence or an explicit reconciled roadmap revision.
- All-C runtime, host-owned I/O and separate ABI/snapshot/replay/durable-save identities remain constraints; no backend or support matrix is qualified yet.
- Local initialization has no remote fork base. OpenGSD selected sequential execution; `git.branching_strategy` is temporarily `none` so this run uses the existing `chore/initialize-project` feature branch. Restore phase branching when a remote/default base is established; no main merge or hosted qualification is implied.
- [Phase 01, historical]: Initial procedural halt was resolved by approved bounded recovery; frozen budget remains unchanged and no CPU requirement is complete.
- [Phase 01]: Plan 01-01 completed under unchanged cumulative caps; native guest and source audits pass, CPU requirements and backend admission remain pending.
- [Phase 01]: Plan 01-02 proves selected isolation and host containment within unchanged caps; timing, continuation and final CPU admission remain pending.
- [Phase 01]: Plan 01-03 qualifies selected timing and explicit fresh-destination continuation within frozen caps; CPU admission and all requirements remain pending final plan 01-04 and independent verification.

### Pending Todos

- User will choose the next session model and workflow step. Read METHODOLOGY.md and the pause handoff before resuming. Do not automatically advance.

### Blockers/Concerns

- User-requested pause is active. Current configuration is interactive with auto_advance and _auto_chain_active false. The original --auto invocation is superseded by this pacing preference.

- Native private guest, source closure, FPU/SoftFloat exclusion, selected isolation, timing, host safety and fresh-destination continuation pass. Final current-evidence admission and independent phase verification remain before CPU acceptance.
- Preserve all counterexamples: odd IRQ crash, fixture UBSan, reset accounting/NMI, BSD address-error boundary and malformed-state/zero-request guards. The explicit state codec passes eight continuation checkpoints; raw upstream context-copy APIs remain unsuitable.
- Frozen cumulative charges are 2,614 handwritten, 523 helper and 483 semantic lines, leaving 77 helper and 17 semantic lines. Both attempts have started. Charged effort is 19,265 seconds total / 18,119 seconds in the final attempt, including an executor allowance through 19:30 UTC and 1,800 seconds reserved for independent review. Preserve charges; on resumption append actual active intervals rather than charging the user pause as active effort.
- Remote/CI/protection/release authority is not configured; future delivery dependency. Continue independent implementation and artifact preparation; repeat remote triage at setup/shipping.
- Evidence is limited to the native experiment; no supported platform, compatibility or performance claim is established. All 27 requirements remain pending.
- Two substantive adaptation attempts are consumed. Preserve cumulative caps in later plans; no automatic further adaptation attempt is authorized. Phase 2 remains blocked on full CPU acceptance.

## Deferred Items

Items acknowledged at milestone close (none yet); future scope is outlined in ROADMAP.md.

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-01T19:35:26Z
Stopped at: Session resumed; awaiting user model selection and authorization for 01-04 Task 2 independent acceptance review
Resume file: .planning/phases/01-cpu-acceptance-experiment/.continue-here.md
