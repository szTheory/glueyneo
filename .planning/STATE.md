---
gsd_state_version: "1.0"
milestone: v0.1
milestone_name: CPU/bus diagnostic SDK alpha
current_phase: 01
current_phase_name: CPU acceptance experiment
status: executing
stopped_at: Plan 01-07 complete; execute-phase continues with dependent gap plans 01-08–01-14
last_updated: "2026-10-02T19:06:00Z"
last_activity: 2026-10-02
last_activity_desc: Plan 01-07 froze the owned-core contract and budget before runtime work; Phase 01 remains open / GAPS_FOUND
state_head: 2b10ab6a3b8d80b95669953ba407a62aa11fd7c2
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 14
  completed_plans: 7
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-02)

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 01 — CPU acceptance experiment
**Current milestone:** v0.1 — CPU/bus diagnostic SDK alpha

## Current Position

Phase: 01 (CPU acceptance experiment) — GAP CLOSURE EXECUTING
Plan: 7 of 14 complete; next is 01-08
Status: Plan 01-07 completed the owned-core contract, scope reconciliation, and separate budget freeze. Plans 01-08 through 01-14 remain in the authorized gaps-only execution chain. The owned CPU runtime has not started or been accepted. Phase 01 remains open / GAPS_FOUND and Phase 02 gated.
Last activity: 2026-10-02 — Closed Plan 01-07 with nine contract tests, optimized-Python controls, preserved-history checks, and a revision-3 ledger baseline.

Progress: [░░░░░░░░░░] 0%

Historical task-level evidence exists for CPU-01 through CPU-05 (5/27 v1 requirements), but the later source review disputes clean backend admission. The current verification is `gaps_found`; Phase 1 remains open and Phase 2 stays gated.

Historical Plan 01-05 task 1 checkpoint (superseded): CPU-01–04 were Pending current admission; the full verifier refused grammar preflight without concluding all four behaviors failed. CPU-05 then awaited the Musashi decision. Current consolidated CPU-05 remains Pending for the owned-core decision; both original Musashi attempts remain consumed and no further adaptation is authorized.

## Performance Metrics

**Velocity:**

- Total plans completed: 7
- Average recorded duration: 31.7min
- Total recorded execution time: 229min; conservatively charged effort 23,365 seconds including review and closeout allowances; Phase 01 remains open with gaps

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 7 | 229min | 32.7min |

**Recent Trend:**

- Last 5 plans: 01-03, 01-04, 01-05, 01-06, 01-07
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

## Accumulated Context

### Decisions

- [User clarification 2026-10-01]: Pause between named GSD workflow steps for review and model selection; no automatic chaining. Apply METHODOLOGY.md for relevant role analysis, adversarial synthesis, and small, flat dependency decisions.

Current decisions: PROJECT.md Key Decisions; dated provenance: preparation/DECISIONS.md.

- v0.1 delivers an actual CPU/bus diagnostic SDK; next milestone outlines interactive graphics/input/sound, real RetroArch macOS, continuation and persistence.
- Phase 1 uses bounded effort/churn guardrails for owned work, with no substantive-attempt counter; tooling halts do not consume an attempt. Review findings trigger in-scope regression-backed repair within the remaining budget. A threshold pauses work and preserves GAPS_FOUND; it is not a correctness verdict. The first owned diagnostic runs in Plan 01-08 before scope expansion.
- The historical CPU-05 obligation recorded the Musashi rejection; consolidated CPU-05 remains pending for the owned-core decision. Phase 1 completion/Phase 2 admission require accepted CPU-01–04 evidence or an explicit reconciled roadmap revision. The 01-04 receipt records bounded private-candidate acceptance; the later phase review found six blockers, so admission is unresolved pending disposition and fresh verification.
- All-C runtime, host-owned I/O and separate ABI/snapshot/replay/durable-save identities remain constraints. No release platform matrix or broad compatibility claim is qualified.
- Local initialization has no remote fork base. OpenGSD selected sequential execution; `git.branching_strategy` is temporarily `none` so this run uses the existing `chore/initialize-project` feature branch. Restore phase branching when a remote/default base is established; no main merge or hosted qualification is implied.
- [Phase 01, historical]: Initial procedural halt was resolved by approved bounded recovery; frozen budget remains unchanged.
- [Phase 01, checkpoint]: Plan 01-01 completed under unchanged cumulative caps; native guest and source audits passed, with later requirements still pending at that checkpoint.
- [Phase 01, checkpoint]: Plan 01-02 proved selected isolation and host containment within unchanged caps; timing, continuation and candidate admission were still pending at that checkpoint.
- [Phase 01, checkpoint]: Plan 01-03 qualified selected timing and explicit fresh-destination continuation within frozen caps; final candidate admission is recorded in plan 01-04.
- [Phase 01, verification 2026-10-01]: OpenGSD returned `gaps_found`. Its MVP story validator rejected the canonical ROADMAP goal before implementation scoring; 0/5 is not a claim that all requirements failed. A later independent source review corroborated six blockers. No tests were rerun during verification; the current source/admission claim needs disposition and a fresh verification pass.
- [Phase 01]: Reject current CPU admission for six unresolved source blockers; defer repair/replacement direction to blocking plan 01-06.
- [Phase 01, historical]: The Musashi decision satisfied its bounded-decision obligation. Consolidated CPU-05 remains Pending for the owned-core decision; CPU-01–04 remain Pending, Phase 01 open and Phase 02 gated.
- [Phase 01, historical checkpoint]: Developer selected C: reject/defer current Musashi candidate and discuss backend replanning; at that checkpoint the owned C core/private seam and strangler transition remained proposals, with no source work, attempt, cap, backend selection or scope change authorized. Superseded by the later owner approval of owned-core gap planning below.
- [Phase 01, planning 2026-10-02]: The developer approved the owned C17 core behind a private whole-CPU seam, diagnostic-first scope, and evidence-led expansion as the gap-planning direction. Revised plans 01-07–01-14 pass the installed structural, story, dependency and Nyquist checks. Plan 01-12 is a bounded source/test review-repair tranche; Plan 01-13 owns inventory, presets and fresh run evidence; Plan 01-14 owns independent final review and sealing. The proposed 32-hour owned-core cap is not frozen until Plan 01-07 executes; all consumed Musashi charges/caps remain immutable. No implementation or backend admission has occurred.
- [Phase 01, Plan 01-07]: Froze the revision-3 owned-core budget ledger and 32-hour / 8-hour gates before any CPU runtime or behavioral test change. Charged 3,360 seconds for governance; baseline churn is 0 runtime and 636 added test/tool lines. The official MC68000 manual review corrected level-7 acceptance and explicit MOVE absolute opcode patterns. CPU-01–05 remain Pending; Phase 02 remains gated.

### Pending Todos

- Seven plans are complete; reviewed gap plans 01-08–01-14 remain in the active gaps-only execution chain. Plan 01-08 must run the original diagnostic first, preserve the eight-hour diagnostic gate, and retain budget for independent review and regression-backed repair. Phase 02 remains gated.

### Blockers/Concerns

- The explicit gaps-only command cleared the pre-execution pause. Pause again after this named execute-phase step; current configuration keeps auto_advance and _auto_chain_active false.
- No per-core GUI is in scope. Each core repository targets a library, headless diagnostic runner and thin libretro adapter; RetroArch remains the interactive frontend until a shared Playstead/external host is ready.
- UI-phase/review and AI-integration gates are disabled for this C-only, non-AI project. Keep API coverage enabled for phases that integrate external APIs/SDKs such as libretro; the installed gate is conditional on those integrations.

- Earlier plan receipts record the private guest, source closure, FPU/SoftFloat exclusion, selected isolation, timing, host-safety, and fresh-destination continuation evidence. The later independent review found legal-instruction undefined behavior and generator defects; do not treat the old acceptance receipt alone as current SDK admission evidence.
- Preserve all counterexamples: odd IRQ crash, fixture UBSan, reset accounting/NMI, BSD address-error boundary and malformed-state/zero-request guards. The explicit state codec passes eight continuation checkpoints; raw upstream context-copy APIs remain unsuitable.
- Frozen cumulative charges are 2,614 handwritten, 523 helper and 483 semantic lines, leaving 77 helper and 17 semantic lines. Both attempts are consumed. Charged effort is 20,005 seconds total / 18,859 seconds in the final attempt. Preserve these charges; any future work must remain inside the original limits or be separately replanned.
- Remote/CI/protection/release authority is not configured; future delivery dependency. Continue independent implementation and artifact preparation; repeat remote triage at setup/shipping.
- Evidence is limited to the native Apple Clang 21 / Darwin arm64 experiment; no release platform matrix, board/BIOS/game compatibility, public state format, or performance claim is established. Task-level records exist for CPU-01 through CPU-05, but the current phase verification did not certify them; the other 22 v1 requirements remain pending.
- Both original Musashi adaptation attempts are consumed. Preserve those historical caps/charges and do not start another Musashi attempt automatically. The separate owned-core plans use their own proposed effort cap; Phase 2 remains blocked until current source findings are dispositioned and Phase 1 verification passes.

## Deferred Items

Items acknowledged at milestone close (none yet); future scope is outlined in ROADMAP.md.

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-02 — execute-phase 01 --gaps-only; Plan 01-07 complete
Stopped at: Continue with Plan 01-08 in the active execute-phase step
Resume file: .planning/phases/01-cpu-acceptance-experiment/.continue-here.md
