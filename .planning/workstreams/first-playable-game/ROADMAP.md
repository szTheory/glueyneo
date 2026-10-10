# Roadmap: Glueyneo

## Overview

The `first-playable-game` planning milestone advances the bounded diagnostic SDK toward one playable Metal Slug X MVS scenario in a pinned macOS RetroArch build. An original redistributable fixture provides the first visible native and frontend result and all public CI inputs. The private game and BIOS path is qualified separately. Phase 03 of the sibling diagnostic SDK workstream remains open; this roadmap does not depend on its hosted-release gate or assign a release version.

## Milestones

- 🚧 **first-playable-game** First Playable Game
- 📋 **Next milestone: snapshots and durable saves** — outlined only; define restored continuation, versioning, and recovery contracts after gameplay evidence and user priorities are known.
- 📋 **Longer horizon** — additional board/game profiles, measured optimization, platform qualification, and shared-host integration remain revisable.

## first-playable-game — First Playable Game

**Status:** Approved by the user on 2026-10-07. Phases 4–7; release version unassigned. Plans 04-01 through 04-31 are executed. HOST-02 and frontend QUAL-03 are Complete from the tracked 04-FRONTEND-RECEIPT.json at the clean committed-snapshot receipt for 7615dd911678 (pinned RetroArch 1.22.2, all 17 lanes pass, bound by the post-commit --check-docs). The 04-31 tool-scoped independent review halted on its containment gate (REVIEW HALTED: containment-violation), so no threat or finding was closed or fixed by it: 04-SECURITY.md has threats_open 14 (the six earlier high rows plus the eight T-04-SC rows for 04-24..04-31 recorded open), 22 review findings remain open and 0 are deferred. Phase 04 is not accepted; the review must be re-run under /gsd-secure-phase before fresh whole-phase verification. Phase 05 is in progress (blocked at Plan 05-06); Phases 06–07 have not started.

## Phases

- [ ] **Phase 4: Public Playable Tracer** - A first-party guest produces software video and input response through native C and actual RetroArch consumers; early sound admission establishes feasibility.
- [ ] **Phase 5: Selected MVS Boot** - Normalized private media can boot the selected BIOS and game to attract/start through guest execution and required board behavior.
- [ ] **Phase 6: Active Title Control** - The selected game reaches an active scene with guest-driven movement, firing, graphics, and scrolling.
- [ ] **Phase 7: Sound and Scenario Qualification** - Public sound and regression evidence and the private RetroArch scenario support a bounded playable claim.

## Phase Details

### Phase 4: Public Playable Tracer

**Goal**: A maintainer can rebuild and run an original guest with visible, input-driven behavior through the ordinary native API and an actual pinned RetroArch build, while resolving the selected sound candidates' admission gates before full integration.
**Depends on**: Phases 01/02 provide only bounded CPU/SDK foundations; no dependency on completing sibling Phase 03's hosted-release gate.
**Requirements**: TRAC-01, TRAC-02, TRAC-03, HOST-02, API-05, SND-01, SND-02, QUAL-03
**Success Criteria** (what must be TRUE):
  1. A maintainer can rebuild the original public fixture from tracked, rights-audited source and assets, run it through a C consumer, and see a guest-produced software frame with checked dimensions, format, pitch, and bounds.
  2. A C integrator can advance a bounded frame with explicit sampled input and owned video/audio buffers, capacities, timing and produced-count semantics, progress/stop information, and actionable errors; a controlled input changes the guest and visible output while a wrong-input control fails.
  3. A user can load, run, control, and unload that fixture in an actual pinned macOS RetroArch build with software video, documented controller mapping, and frontend-owned pacing.
  4. A maintainer can reproduce passing admission evidence for the pinned Z80 and private-interface ymfm YM2610 candidates, including license/source/state audits, cycle or clock and interrupt/bus behavior, deterministic timing, continuation and independent-instance evidence, contained C++ failures, and static/shared C-consumer linkage; a failed gate blocks admission and requires bounded replanning rather than phase completion.
  5. An integrator can follow the clean-tree build/install/load procedure for the native library and libretro adapter on the selected macOS configuration and identify exact dependency, compiler, SDK, OS, architecture, and frontend identities plus untested configurations.

**Plans**: 34/36 plans executed; gap-closure plans 04-24 through 04-31 (waves 22–29, sequential because each code plan refreshes docs/rights-inventory.md in its final commit) repair the six 2026-10-10 verification gaps and the remaining open review findings, then re-run the qualification plus a tool-scoped independent review. Plan 04-31 re-qualified pinned RetroArch at 7615dd911678 (receipt passed, summary bound) but its tool-scoped review halted on containment (a path argument equal to the scratch directory itself failed the strict under-directory gate), so 04-SECURITY.md threats_open is 14, 22 findings are open and none are deferred. Phase 04 acceptance awaits a contained independent review and fresh whole-phase verification. Gap-closure plans 04-32 through 04-36 (waves 30–34, sequential) are planned for the 2026-10-10 re-verification gaps. They apply user decisions D-GAP-01 (a path equal to the scratch directory counts as contained) and D-GAP-02 (maintainer acceptance of T-04-44/52/55/60).
- [ ] 04-36-PLAN.md — Focused contained re-review of residual, freshness-affected and T-04-SC (04-35)/(04-36) IDs (with re-qualification if receipt-bound code changed), phase-scoped `--require-closed --phase 04`, reconcile SECURITY/VALIDATION/REQUIREMENTS traceability/ROADMAP/STATE (gap closure, Wave 34)
- [ ] 04-35-PLAN.md — Classify the 04-34 residual open IDs into fixed file groups and repair them test-first within a 14-file bound, or record them unrepaired with reasons (gap closure, Wave 33)
- [x] 04-34-PLAN.md — Re-qualify pinned RetroArch at the repaired HEAD (single instance), contained tool-scoped independent review of 77 IDs (43 threats, 34 findings) gated by tools/independent_review.py, transcribe verdicts, record D-GAP-01/D-GAP-02 (gap closure, Wave 32)
- [x] 04-33-PLAN.md — Qualification-tool robustness: lane/smoke process-group safety (GWR-04/05, T-04-54), clean docs-check exception path (T-04-11), review provenance binding (T-04-38), all-or-nothing evidence write (GWR-06), storage audit (GWR-02), GIN-01..04 (gap closure, Wave 31)
- [x] 04-32-PLAN.md — Gate hardening: tracked independent-review containment/verdict/transcription tool with the D-GAP-01 boundary, register gate fail-closed on schema drift (GWR-01), consistency CTest rename, phase-scoped closure and no-weakening config (GWR-03), quoted status (gap closure, Wave 30)
- [x] 04-31-PLAN.md — Re-qualify pinned RetroArch with --clean --check-docs at the repaired HEAD (fully automated), bind the fresh summary after commit, tool-scoped verdict-only independent review of all open threats and 22 findings, reconcile register/dispositions/ROADMAP/STATE with the computed next command (gap closure, Wave 29)
- [x] 04-30-PLAN.md — Remaining review findings, part 2: username token narrowed to GitHub Actions service accounts with documented residual (WR-06, T-04-60), dead smoke code (IN-02), core dependency parsing (IN-03), rights inventory rows (gap closure, Wave 28)
- [x] 04-29-PLAN.md — Remaining review findings, part 1: runtime writable-storage audit and documented guard (WR-08), workstream-gated register test and workstream block_on (WR-07), rights inventory rows (gap closure, Wave 27)
- [x] 04-28-PLAN.md — Launch safety: pre-launch single-instance refusal, PID-scoped quit, no orphan on outer timeout, process-group lane timeouts, survivor signalling limited to the lane's recorded child (CR-07, WR-03/04/05; gap closure, Wave 26)
- [x] 04-27-PLAN.md — Outside-block claim gate, guide private-path scan, atomic scanned records, guide prose rewrite (CR-04, WR-01, IN-01, IN-04 prose-claim gap; gap closure, Wave 25)
- [x] 04-26-PLAN.md — Mandatory evidence binding incl. .git-less snapshot, field validation, crosswalk provenance (CR-03/05, WR-02/09, IN-04 binding/scope gaps; gap closure, Wave 24)
- [x] 04-25-PLAN.md — Strict security register gate: frontmatter-only key, all register tables, closure mode, documented in docs/testing.md (CR-06, IN-04 register gap; gap closure, Wave 23)
- [x] 04-24-PLAN.md — Canonical private-path matching and fail-closed sinks, early-failure receipt, redacted CLI errors (CR-01/02/08/09, IN-04 scan/receipt gaps; gap closure, Wave 22)
- [x] 04-23-PLAN.md — Re-qualify pinned RetroArch at the current revision and reconcile Phase 04 traceability (gap closure, Wave 21)
- [x] 04-22-PLAN.md
- [x] 04-21-PLAN.md

**Wave 1**
- [x] 04-01-PLAN.md

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 04-02-PLAN.md
- [x] 04-03-PLAN.md

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 04-04-PLAN.md

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 04-05-PLAN.md

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 04-06-PLAN.md

**Wave 6** *(gap closure; blocked on Wave 5 completion)*
- [x] 04-07-PLAN.md — Bind qualification to a complete immutable source snapshot

**Wave 7** *(gap closure; follows Wave 6)*
- [x] 04-08-PLAN.md — Diagnose actual RetroArch exit and regenerate final qualification receipt

**Wave 8** *(gap closure; follows Wave 7)*
- [x] 04-09-PLAN.md — Normalize HOST coverage metadata while preserving human frontend handoff
- [x] 04-10-PLAN.md — Repair diagnostic path redaction, fixture identity, and pinned app quit target

**Wave 9** *(gap closure; blocked on Wave 8 completion)*
- [x] 04-11-PLAN.md — Bind receipt rows to committed archive bytes and reconcile the validation map

**Wave 10** *(gap closure; blocked on Wave 9 completion)*
- [x] 04-12-PLAN.md — Repair receipt types, complete path redaction, validation-map state and CPU inventory evidence

**Wave 11** *(gap closure; blocked on Wave 10 completion)*
- [x] 04-13-PLAN.md — Close escaped-quote path disclosure and reconcile review evidence

**Wave 12** *(gap closure; blocked on Wave 11 completion)*
- [x] 04-14-PLAN.md — Redact raw-quoted diagnostic paths, parse Info findings, and reconcile bounded sound-admission statuses

**Wave 13** *(actual frontend evidence; follows Wave 12)*
- [x] 04-15-PLAN.md — Observe pinned RetroArch only in a materially changed, functioning launch context

**Wave 14** *(gap closure; follows Waves 12 and 13)*
- [x] 04-16-PLAN.md — Repair newline-path diagnostic disclosure and contradictory review-state acceptance

**Wave 15** *(gap closure; follows Wave 14)*
- [x] 04-17-PLAN.md — Reject contradictory frontend closure claims and reconcile WR-06 evidence

**Wave 16** *(gap closure; follows Wave 15)*
- [x] 04-18-PLAN.md — Repair security-count, current evidence-map, and frontend claim gates

**Wave 17** *(bounded gap closure; follows Wave 16)*
- [x] 04-19-PLAN.md — Independently review and reconcile security/review dispositions with direct regressions

**Wave 18** *(bounded gap closure; follows Wave 17)*
- [x] 04-20-PLAN.md — Repair current review/evidence reconciliation and independently review the frontend sanitizer

**UI hint**: no

### Phase 5: Selected MVS Boot

**Goal**: A user can load the selected private MVS media and see the guest-executed game reach its attract/start path with a documented, bounded configuration.
**Depends on**: Phase 4's verified native API and fixture foundation; the Phase 4 threat dispositions reopened by the independent 04-23 review (threats_open 6) do not block Phase 5 engineering, but remain blockers to Phase 4 acceptance (HOST-02/frontend QUAL-03 are Complete at aaf3f093ab0f) and any corresponding frontend/security claim. The sound-CPU interaction needed by BIOS/game boot is delivered here even though audible output is qualified in Phase 7.
**Requirements**: MEDIA-02, MEDIA-03, MEDIA-04, GAME-02
**Success Criteria** (what must be TRUE):
  1. A C integrator can supply immutable normalized cartridge and BIOS regions for the selected MVS profile under explicit lifetimes, layout, byte order, and resource limits.
  2. A user can load the selected unmodified local game and BIOS archives through a documented RetroArch/import path whose bounded archive handling stays outside the native core.
  3. A user gets distinct, actionable missing, incompatible, unsupported, malformed, and limit errors; after a rejected load, valid media can load or the instance can be destroyed safely.
  4. In the selected configuration, the guest reaches the game's attract/start path through the owned 68000 and required MVS banking, protection, timing, interrupts, and sound-CPU handshakes, with source-qualified regression evidence and no canned boot or fabricated handshake.

**Plans**: Six plans are recorded: 05-01, 05-02, and 05-04 complete; 05-03 halted without a selected guest checkpoint; 05-05 halted at local candidate gates; and 05-06 halted at Task 2 because independent selected configuration and sourced guest-predicate evidence are unavailable. Plan 05-06 cleared the diagnostic oracle/rights gates and passed exact-SHA hosted MVS qualification for PR #2, but the selected boot requirement remains open. Phase 05 remains incomplete; selected-media compatibility, attract/start, and actual RetroArch behavior remain unqualified.
**Wave 1**
- [x] 05-01-PLAN.md — MVS media path and guest-driven selected boot

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 05-02-PLAN.md — Split selected game/BIOS mapping and exact seven-test current-revision CI evidence

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 05-03-PLAN.md — Source-qualified selected-guest boot to direct attract/start and pinned-app smoke (halted)
- [x] 05-04-PLAN.md — Source-justified guest-write checkpoint, bounded selected run and conditional pinned-app smoke

**Wave 4** *(05-05 and 05-06 halted; 05-06 hosted candidate gate passed)*
- [x] 05-05-PLAN.md — Reviewed public-safe revision and exact-SHA hosted seven-test MVS receipt
- [x] 05-06-PLAN.md — Reconcile oracle/rights gates, establish bounded selected-guest evidence, and bind hosted results to the final SHA

### Phase 6: Active Title Control

**Goal**: A user can enter and control one stated active Metal Slug X scene with the required visible board behavior.
**Depends on**: Phase 5
**Requirements**: GAME-03, GAME-04
**Success Criteria** (what must be TRUE):
  1. A user can enter the selected active scene in RetroArch and use the documented mapping to move and fire; the effects come from guest execution and emulated input, not title-specific canned output.
  2. A user can see the scene's required graphics, layering, palettes, and scrolling, with the supported scene and unresolved raster/timing behavior stated precisely and original slowdown preserved where modeled.

**Plans**: TBD

### Phase 7: Sound and Scenario Qualification

**Goal**: The selected scene has representative guest-driven sound, and clean-tree public checks plus a separate private local run establish the exact native, libretro, and game claims.
**Depends on**: Phase 6 and the sound admission evidence from Phase 4
**Requirements**: API-06, SND-03, SND-04, QUAL-01, QUAL-02, QUAL-04
**Success Criteria** (what must be TRUE):
  1. A maintainer can run a public guest-driven sound fixture through Z80/YM2610 and reproduce non-silent, signal-qualified output with meaningful controls, identifying native chip output separately from resampling and device behavior.
  2. In the pinned RetroArch setup, a user hears representative music and action-triggered effects while moving and firing in the selected scene; machine-observable steps of the exact local boot-to-play scenario are reproducible by automated checks, with only residual subjective or unavailable evidence requiring a human, and missing sound behavior is stated.
  3. A maintainer can repeat and partition the supported fixture workload and interleave or concurrently run distinguishable native instances while matching isolated-baseline guest, video, and audio results at equal emulated boundaries.
  4. A maintainer can run clean-tree, proportionate local and public-CI checks on the public fixture through native and real libretro consumers, comparing frame, input, and audio observations at matching emulated boundaries with documented conversion, and covering lifecycle, malformed inputs, relevant fuzz/sanitizer, and retained diagnostic SDK regressions.
  5. A consumer can identify the exact qualified private scenario, public fixture coverage, oracle ancestry, and unknown or unsupported behavior in current documentation; private media identities and derived evidence stay local, and fixture success, emulator agreement, or BIOS/archive integrity is not presented as broader hardware or game compatibility.

**Plans**: TBD

## Sequencing and Evidence Boundaries

The Phase 4 frame contract may expose an initially silent audio buffer, but API-06 and native/libretro audio equivalence remain open until Phase 7. Phase 5 must implement any Z80/sound-CPU handshakes that the real boot path requires; deferring audible YM2610 output does not license a fake handshake. A failed sound admission or unexpectedly large CPU/board gap triggers explicit bounded replanning, not reduced acceptance. Public fixture CI and private game qualification are separate claims. Private archives, identities, captures, traces, and logs remain outside Git, public CI, and releases. An implementation-reference match is not original-hardware proof.

Each phase includes the automated evidence and independent review appropriate to its new behavior, including isolation and determinism checks as the relevant machine state is added. Phase 7 owns the final combined audio/video/input and consumer qualification; it does not defer earlier regression testing. Phase 4's first vertical result is visible fixture/input behavior before the bounded sound admission work. Guest framebuffers and the existing RetroArch interface do not require a new core-owned application UI or a separate UI-design workflow.

## Progress

**Execution Order:** Phase 4's verified native API/fixture foundation → Phase 5 MVS boot engineering → Phase 6 → Phase 7. Phase 5 engineering may proceed while Phase 4 acceptance remains blocked: the 04-31 independent review halted on containment and left threat rows open (threats_open 14) although the pinned RetroArch receipt at 7615dd911678 is current. Those findings block Phase 4 acceptance and related claims; they do not establish a technical dependency for the separate media, board, and guest-execution work. Phase 5 must not close or reinterpret Phase 4 findings.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 4. Public Playable Tracer | 34/36 | In Progress | - |
| 5. Selected MVS Boot | 6/6 | In Progress | - |
| 6. Active Title Control | 0/TBD | Not started | - |
| 7. Sound and Scenario Qualification | 0/TBD | Not started | - |
