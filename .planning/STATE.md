---
gsd_state_version: "1.0"
milestone: v0.1
milestone_name: CPU/bus diagnostic SDK alpha
current_phase: 02
current_phase_name: Executable diagnostic SDK
status: executing
stopped_at: Completed 02-03-PLAN.md
last_updated: "2026-10-06T01:21:05.472Z"
last_activity: 2026-10-05
last_activity_desc: Plan 02-03 execution complete; Plan 02-04 is next after user continues
state_head: 184f3a3a1f32ba3eb0f808ee504574bef6735ec7
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 35
  completed_plans: 32
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-05)

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 02 — Executable diagnostic SDK
**Current milestone:** v0.1 — CPU/bus diagnostic SDK alpha

## Current Position

Phase: 02 (Executable diagnostic SDK) — EXECUTING
Plan: 4 of 6 — 02-01 through 02-03 complete; 02-04 is next after user continues
Status: Ready to execute
Last activity: 2026-10-05 — Plan 02-03 execution complete; 02-04 is next after user continues

Progress: [███░░░░░░░] 33% (one of three phases complete)

Phase 01 passed its fresh whole-phase verifier at source revision `09476ed57ee29c0798f8be8f082e05ad73776e3b`: 10/10 must-haves, zero behavior-unverified items, zero overrides, and no human verification required. The report freshly ran 41 bounded native assertions plus cold-process, inventory, and contract-boundary checks; historical lanes and UAT rows were not replayed. It admits the owned backend for the exact bounded diagnostic subset. The candidate-level receipt remains `unqualified`, and original-silicon saved-PC behavior remains unknown.

Phase 01 has 29 plan summaries, of which 28 are execution-complete. Plan 01-17 remains an answered, incomplete hardware-evidence checkpoint; that unknown hardware question is outside the admitted candidate capability. Preserve the historical summaries, receipt, seals, source collection and all UAT rows. Do not repeat Plan 01-29, the fresh verifier, the finite silicon search, or conversational UAT.

The GSD completion transaction updated the active phase and requirements after the report was written. The subsequent edits changed planning status and the documentation-route regression; that focused regression now passes 8/8. No runtime implementation or CPU acceptance evidence changed. Retain `01-VERIFICATION.md` as the point-in-time verdict and do not rerun it just to refresh administrative fingerprints. Installed `query verification.status` reports the fingerprint as stale and suggests `$gsd-execute-phase 01`; this is the known administrative-fingerprint routing problem, not a new acceptance gap. Do not follow that stale route. Phase 02 planning passed its independent review: six plans cover all 15 requirements and 18 decisions, and the installed decision, API-coverage, structure, path, failure-direction and post-plan gap checks passed. Plans 02-01 through 02-03 are execution-complete; bounded progress, exact controls, independent-instance checks, copied-media handling and allocation-recovery evidence pass. Plan 02-04 is next after the user continues, followed by the remaining dependency-ordered plans. The frozen candidate contract checker reproduces its pre-admission gate only at the recorded pre-closeout revision; it is not a current phase router.

## Performance Metrics

**Velocity:**

- Total plans in phase: 29; execution-complete: 28; Plan 01-17 remains at its answered checkpoint; Plans 01-28 and 01-29 are executed
- Average recorded duration: 44.2min across 28 execution-complete plans
- Total recorded execution time: 1,237min across 28 execution-complete plans; exact owned-core active effort/churn remain in experiments/owned_cpu/budget-ledger.json

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 28 completed + 01-17 checkpoint | 1,237min | 44.2min |

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
| Phase 02 P01 | 20 min | 3 tasks | 9 files |
| Phase 02 P02 | 24min | 3 tasks | 6 files |
| Phase 02 P03 | 27min | 3 tasks | 6 files |

## Accumulated Context

### Decisions

- Phase 01 uses a private owned C17 candidate with explicit host-I/O boundaries and frozen Musashi rejection history; see PROJECT.md and preparation/DECISIONS.md.
- P01-C-14 excludes only exact 0x4AFC from the candidate subset. Original-silicon saved PC remains unknown; do not repeat the finite search or infer hardware truth.
- The candidate-level receipt remains unqualified as a frozen experiment artifact. The separate Phase 01 verifier passed bounded acceptance; CPU-01–05 are complete for that scope and Phase 02 is unblocked.
- Phase 01 effort/churn limits and all consumed attempts remain frozen in experiments/owned_cpu/budget-ledger.json. Plan 01-29 adds a 6,463-second all-agent charge; final contract totals are 86,226 active seconds and 6,540 contract-measured test/tool churn, with no pause.
- Plan 01-27 changes only derived report/receipt/accounting metadata. C2 binds the exact independent review/security report bytes; source collection remains unchanged.
- The initial project branch has no remote base; no main merge or hosted qualification is implied.
- [Phase 01]: Plan 01-29's independent CPU review and security assessment were reconciled by a fresh 10/10 whole-phase report at revision `09476ed`; see `01-VERIFICATION.md`. The report is the phase-level admission authority for the bounded subset, separate from the unchanged unqualified candidate receipt. WR-01 remains a documentation warning; original-silicon saved PC remains unknown.
- [Phase 02]: Existing `02-CONTEXT.md` contains the accepted design decisions and was refreshed after the gate passed. Plans 02-01–06 cover all 15 requirements, 18 decisions and 21 edge-probe dispositions. Six sequential waves avoid package rebuilds racing runtime edits. Plans 02-01 through 02-03 completed the executable API/runner tracer, bounded progress, exact functional controls, independent-instance comparisons, lifecycle/media contract and allocation-failure recovery. Plan 02-04 is next after the user continues; the phase remains in progress.
- [Phase 02]: Expose only a bounded instruction-boundary PC alongside run results so exact diagnostic boundaries are observable without publishing the CPU register file.
- [Phase 02]: Share one host-side diagnostic fixture module between runner and SDK tests to prevent byte-recipe drift.
- [Phase 02]: Keep allocator failpoints and full image digests behind a separately compiled test target so installed headers and the public runtime expose no test hooks.
- [Phase 02]: The fixed diagnostic profile has no caller-selected permissions field; ROM is read-only and RAM is writable.
- [Phase 02]: Allocation sweeps stop after the first failure in a candidate path, verify cleanup, and advance to the next injected position.
- [Phase 02]: Report actual guest event charges; preserve reset recovery overshoot, stopped idle progress, and invalid-request atomicity.
- [Phase 02]: Keep trace, mutation and callback-failure test state per image and absent from the production runtime.
- [Phase 02]: Claim equal-boundary determinism only for the selected schedule and distinct instances, not arbitrary partitions or same-instance concurrency.
- [Phase 02]: Use POSIX threads through the test target's Threads::Threads link because this AppleClang host lacks <threads.h>.

### Pending Todos

None yet.

### Blockers/Concerns

- Original-silicon saved PC, unsupported platforms, public persistence formats, board/BIOS compatibility and performance qualification remain unknown or outside scope.
- Preserve the historical odd-IRQ, fixture-UBSan, reset-accounting/NMI, BSD address-error and malformed-state/zero-request counterexamples.
- Both original Musashi adaptation attempts are consumed. Do not repeat them automatically.
- Original-silicon saved PC, unsupported platforms, public persistence formats, board/BIOS compatibility, and gameplay performance remain unknown or outside scope. WR-01 is a documentation warning carried into the Phase 02 plan; it does not block bounded CPU acceptance.

## Deferred Items

Items acknowledged at milestone close (none yet); future scope is outlined in ROADMAP.md.

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-06T01:21:05.445Z
Stopped at: Completed 02-03-PLAN.md
Resume file: None
