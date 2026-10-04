---
gsd_state_version: "1.0"
milestone: v0.1
milestone_name: CPU/bus diagnostic SDK alpha
current_phase: 01
current_phase_name: CPU acceptance experiment
status: executing
stopped_at: "Completed $gsd-plan-phase 01 --gaps; Plan 01-26 passed scoped review and coverage gates. Phase 01 remains open. Next separate step: $gsd-execute-phase 01 --gaps-only."
last_updated: "2026-10-04T19:31:11.725Z"
last_activity: 2026-10-04
last_activity_desc: Phase 01 gap plan 01-26 ready to execute
state_head: e187c4a42f6370736c30297ae48ac8d651e0ab8b
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 26
  completed_plans: 25
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
Plan: 26 of 26 (new gap-closure plan)
Status: Ready to execute
Last activity: 2026-10-04 — Phase 01 gap plan 01-26 ready to execute

Progress: [░░░░░░░░░░] 0%

GSD frontmatter progress.completed_plans counts matching summary files and is 25, including Plan 01-17's answered checkpoint summary. Execution-complete plans are 01-01 through 01-16 and 01-18–01-25 (24); Plan 01-17 remains incomplete at its answered checkpoint. Plan 01-26 is the new unexecuted gap-closure plan, bringing the phase total to 26. Phase 01 remains incomplete; its only canonical verification report records a current 2026-10-04 gap and must be refreshed after execution.

Historical task-level evidence exists for CPU-01 through CPU-05 (5/27 v1 requirements). Plans 01-22–01-25 close the later bounded candidate, resource-control and documentation findings, but do not admit the backend. Current phase-goal verification must be refreshed; Phase 1 remains open and Phase 2 stays gated.

Historical Plan 01-05 task 1 checkpoint (superseded): CPU-01–04 were Pending current admission; the full verifier refused grammar preflight without concluding all four behaviors failed. CPU-05 then awaited the Musashi decision. Current consolidated CPU-05 remains Pending for the owned-core decision; both original Musashi attempts remain consumed and no further adaptation is authorized.

Shift-left verification preference (PROJECT-D-45): deterministic acceptance should be automated at the earliest useful test seam, with CI added only for recurring value. Plan 01-21's 39/39 machine-evidenced UAT remains historical and scoped through that plan. Plan 01-25 preserves those rows and records four later passing outcomes; current UAT is 44/44, including an automated navigation check for the route that was current at its recorded revision. The deferred seal remains unqualified pending refreshed phase-goal verification. Original-silicon 0x4AFC saved PC remains explicitly unknown. See METHODOLOGY.md and 01-UAT.md.

## Performance Metrics

**Velocity:**

- Total plans in phase: 26; execution-complete: 24; Plan 01-17 remains at an answered decision checkpoint; Plans 01-24–01-25 are complete; Plan 01-26 is planned and unexecuted
- Average recorded duration: 43.4min across 24 execution-complete plans
- Total recorded execution time: 1,042min; exact owned-core active effort/churn remain in experiments/owned_cpu/budget-ledger.json; Phase 01 remains open pending verification

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 24 of 26 | 1,042min | 43.4min |

**Recent Trend:**

- Last 5 plans with execution metrics: 01-21, 01-22, 01-23, 01-24, 01-25
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

## Accumulated Context

### Decisions

- [User clarification 2026-10-01]: Pause between named GSD workflow steps for review and model selection; no automatic chaining. Apply METHODOLOGY.md for relevant role analysis, adversarial synthesis, and small, flat dependency decisions.

Current decisions: PROJECT.md Key Decisions; dated provenance: preparation/DECISIONS.md.

- v0.1 delivers an actual CPU/bus diagnostic SDK; next milestone outlines interactive graphics/input/sound, real RetroArch macOS, continuation and persistence.
- Phase 1 uses bounded effort/churn guardrails for owned work, with no substantive-attempt counter; tooling halts do not consume an attempt. Review findings trigger in-scope regression-backed repair within the remaining budget. A threshold pauses work and preserves GAPS_FOUND; it is not a correctness verdict. The first owned diagnostic ran in Plan 01-08 before scope expansion.
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
- [Phase 01, Plan 01-08]: The original arithmetic/store fixture and its named wrong-result control pass on a private owned C17 slice. The diagnostic gate consumed 2,565 seconds; cumulative owned effort is 5,925 seconds, with 517 runtime and 1,623 test/tool added/deleted lines against the frozen baseline. The 8-hour gate and cumulative caps pass. This proves only the documented first slice; CPU-01–05 remain Pending, Phase 01 stays GAPS_FOUND and Phase 02 gated.
- [Phase 01, Plan 01-09]: Added manual-backed named IRQ, exception, odd-address frame, and whole-event timing behavior. The 23-case timing harness, three normal owned CPU CTest targets, and two negative controls pass. The original 36 instruction-clock diagnostic remains separate from reset40 and STOP idle. The core remains private and unadmitted; CPU-01–05 stay Pending and Phase 02 gated.
- [Phase 01, Plan 01-10]: Added 32 interleaved and 32 barrier-started concurrent instance pairs plus 16 supervised cold processes; the complete native 11-case suite and six safety cases each under ASan+UBSan and TSan passed on Apple Clang 21 / Darwin arm64. A 26-field, nine-source inventory and named corruption controls pass. Same-instance overlap and other platforms remain unsupported or untested; CPU-01–05 stay Pending.
- [Phase 01]: Keep the continuation record behind OWNED_CPU_TEST_HOOKS and make no public persistence claim. — The codec is bounded to the exact cpu.c source identity and the reviewed acceptance scope remains private.
- [Phase 01]: Restore keeps destination bus and allocator bindings while the caller clones guest memory. — This preserves owner isolation and ensures validation and restore make no guest bus callbacks.
- [Phase 01]: Validate private continuation counters against the supported dispatch minimum — A captured completed-dispatch count must be consistent with instruction and exception clocks. The four-clock bound is conservative for this subset and does not serve as a timing oracle.
- [Phase 01]: Bind source-review findings to an exact pre-repair revision and verify fixes separately — The independent review is an evidence artifact for the reviewed source identity; repaired code and regressions are recorded in the plan summary and must be independently reviewed again in Plan 14.
- [Phase 01]: Keep restore-over-ready semantics unclaimed until its destination precondition is clarified — The review found contract wording ambiguity while implementation accepts ready destinations. No behavior is promoted to supported without a direct requirement or test contract.
- [Phase 01]: Preserve the earlier state audit while the current distribution manifest owns refreshed source identities; four native preset lanes pass, with admission pending independent Plan 14 review.
- [Phase 01]: Plan 01-14 sealed unqualified/GAPS_FOUND after independent repair re-review; F14-03 frozen ILLEGAL contract discrepancy requires user-directed reconciliation; CPU-01–05 Pending, Phase 01 open and Phase 02 gated.
- [Phase 01]: Plan 01-15 leaves F14-03 HIGH/open after exact UM/PRM/errata interpretation; canonical/runtime/fixture/oracle unchanged, CPU-01–05 Pending, Plan 01-16 owns independent unresolved closeout.
- [Phase 01]: Plan 01-16 freshly qualified exact unchanged behavior and independently retained F14-03 HIGH/open; seal unqualified/GAPS_FOUND, CPU-01–05 Pending and Phase 02 gated.
- [Phase 01, P01-C-13, user decision 2026-10-03]: Preserve the original-MC68000 `ILLEGAL 0x4AFC` saved-PC behavior as unknown under the unchanged claim. The bounded source search and independent adjudication remain ambiguous. Do not select `$100` or `$102`, alter runtime/contract/oracle/subset, repeat the finite search, or claim mitigation/admission. F14-03 and T-01-15-03 remain HIGH/open; CPU-01–05 Pending; Phase 01 GAPS_FOUND/open; Phase 02 gated. Gap planning is authorized; any supported-subset change remains a separate owner decision.
- [Phase 01, P01-C-14, user decision 2026-10-03]: Exclude only exact canonical `0x4AFC` from the owned candidate's qualified subset. Plan for the candidate to return `OWNED_CPU_UNSUPPORTED_OPCODE` with fault PC/IR and no guest ILLEGAL/vector-4 entry, frame/vector bus effects, instruction completion or guest-cycle charge. This states a candidate support boundary, not original MC68000 invalid-opcode behavior. Retain other selected exception interactions. P01-C-14 supersedes P01-C-13 only on the candidate subset boundary; the hardware saved-PC result remains unknown, and Plan 01-17's evidence remains immutable history. This authorizes same-phase gap planning, not implementation, mitigation claims, admission, phase verification or Phase 02.
- [Phase 01]: Plan 01-18 applies exact 0x4AFC candidate rejection and additive P01-C-14 contract only; hardware saved PC stays unknown, CPU-01–05 Pending, HIGH findings open.
- [Phase 01]: Plan 01-19 preserves 13 continuation boundaries and legacy receipt bytes; P01-C-14 receipts require exact controls and independent review/security before deferred admission. CPU-01–05 Pending and HIGH findings remain open.
- [Phase 01]: Plan 01-20 exact-source qualification passed all four lanes; whole-lane builds reused directories, and admission remains deferred to independent review/security and separate phase verification.
- [Phase 01]: Plan 01-21 halted at final seal: independent native/source assessment passed, but post-audit security hash rebinding failed; T-01-43 HIGH/open, no admission, CPU-01–05 Pending, Phase 01 incomplete and Phase 02 gated.
- [Phase 01]: Plan 01-21 recovered only derived seal metadata, preserving the complete stale seal and all5 collections; same reviewer/assessor final exact931e2f0 binding and deferred seal pass. Earlier temporary T01-43 blocker is resolved; Phase01 still incomplete/GAPS_FOUND, CPU01–05 Pending, next separate verify-work01.
- [Phase 01]: Gap planning created Plans 01-22–01-25 for later independent review findings CR-01/CR-02/WR-01/WR-02. The independent plan checker passed after requiring current UAT outcomes to be appended before final sealing. CPU-01–05 remain Pending, Phase 01 remains incomplete/GAPS_FOUND, and Phase 02 remains gated.
- [Phase 01]: Private continuation preserves guest-reachable odd PCs and selected stack pointers; a distinct receipt profile records the expanded continuation denominator. — Guest-driven RTE and SR-transition regressions showed that rejecting odd values at capture time interrupted a reachable continuation before execution could report its deferred fault. The new owned-p01-c14-continuation-2 profile requires fifteen named checkpoints and ninety calls, while owned-p01-c14-1 retains its historical thirteen/78 interpretation. The exact 0x4AFC exclusion and unknown original-silicon saved PC remain unchanged.
- [Phase 01]: Keep cumulative resource charges monotonic and make seal limits inclusive at the frozen caps. — validate_budget rejects any decrease in each of the four cumulative churn fields, with category and entry identity; a prior threshold crossing therefore cannot disappear in a later row. budget_check uses the canonical 115200/6000/8000 caps inclusively but rejects a canonical pause-for-review result or any active pause. No ledger history or cap is rewritten.
- [Phase 01, Plan 01-25]: Independently resolve CR-01/CR-02/WR-01/WR-02 within the exact candidate and documentation scope; preserve all 39 historical UAT rows, append four passing outcomes, and seal only with admission deferred. Final budget is 45 records / 67,834 active seconds with no pause. CPU-01–05 remain Pending, Phase 01 remains GAPS_FOUND, Phase 02 gated, and the original-silicon saved PC remains unknown.

### Pending Todos

- Plan 01-17 preserves the answered checkpoint and unknown original-silicon saved PC; do not repeat the finite search. Plans 01-18–01-25 completed their scoped candidate boundary, controls, qualification, later-finding repairs, independent reassessment and deferred seal. Phase 01 UAT is complete at 44/44 automated checks with no issues. Plan 01-26 plans the current ROADMAP wording gap without changing admission. All CPU requirements remain Pending, Phase 01 is open with current phase-goal verification still required after gap execution, and Phase 02 is gated. Next separate command: `$gsd-execute-phase 01 --gaps-only`.

### Blockers/Concerns

- F14-03/T-01-15-03 are reconciled only for the owner-approved candidate scope after Plan01-21 final exact source/security/seal gates passed. Original-MC68000 saved PC remains unknown and outside the revised support claim. No backend admission or phase completion is inferred; separate current phase-goal verification is still required.
- No per-core GUI is in scope. Each core repository targets a library, headless diagnostic runner and thin libretro adapter; RetroArch remains the interactive frontend until a shared Playstead/external host is ready.
- UI-phase/review and AI-integration gates are disabled for this C-only, non-AI project. Keep API coverage enabled for phases that integrate external APIs/SDKs such as libretro; the installed gate is conditional on those integrations.

- Earlier plan receipts record the private guest, source closure, FPU/SoftFloat exclusion, selected isolation, timing, host-safety, and fresh-destination continuation evidence. Plans 01-25 independently dispositioned the later bounded findings; the candidate remains unqualified and no phase verification has run.
- Preserve all counterexamples: odd IRQ crash, fixture UBSan, reset accounting/NMI, BSD address-error boundary and malformed-state/zero-request guards. The current continuation profile covers 15 named fresh-owner checkpoints and 90 run calls; historical owned-p01-c14-1 evidence remains at 13/78. Raw upstream context-copy APIs remain unsuitable.
- Frozen cumulative charges are 2,614 handwritten, 523 helper and 483 semantic lines, leaving 77 helper and 17 semantic lines. Both attempts are consumed. Charged effort is 20,005 seconds total / 18,859 seconds in the final attempt. Preserve these charges; any future work must remain inside the original limits or be separately replanned.
- Remote/CI/protection/release authority is not configured; future delivery dependency. Continue independent implementation and artifact preparation; repeat remote triage at setup/shipping.
- Evidence is limited to the native Apple Clang 21 / Darwin arm64 experiment; no release platform matrix, board/BIOS/game compatibility, public state format, or performance claim is established. Task-level records exist for CPU-01 through CPU-05, but the current phase verification did not certify them; the other 22 v1 requirements remain pending.
- Both original Musashi adaptation attempts are consumed. Preserve those historical caps/charges and do not start another Musashi attempt automatically. The owned-core evidence remains scoped and unadmitted; Plans 01-24–01-25 are complete, and a fresh Phase 01 verification is still required before Phase 02.
- Resolved temporary Plan01-21 T-01-43 blocker: preserved complete stale seal in superseded history, independently rebound current metadata and generated a fresh verified deferred seal. Current final review/security/source/receipt identities pass; failed attempt and corrective audit remain historical.

## Deferred Items

Items acknowledged at milestone close (none yet); future scope is outlined in ROADMAP.md.

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-04T16:34:48.799Z
Stopped at: Completed $gsd-plan-phase 01 --gaps; Plan 01-26 passed scoped review and coverage gates. Phase 01 remains open. Next separate step: $gsd-execute-phase 01 --gaps-only.
Resume file: None
