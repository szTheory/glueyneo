# Roadmap: Glueyneo

## Overview

The `first-playable-game` planning milestone advances the bounded diagnostic SDK toward one playable Metal Slug X MVS scenario in a pinned macOS RetroArch build. An original redistributable fixture provides the first visible native and frontend result and all public CI inputs. The private game and BIOS path is qualified separately. Phase 03 of the sibling diagnostic SDK workstream remains open; this roadmap does not depend on its hosted-release gate or assign a release version.

## Milestones

- 🚧 **first-playable-game** First Playable Game
- 📋 **Next milestone: snapshots and durable saves** — outlined only; define restored continuation, versioning, and recovery contracts after gameplay evidence and user priorities are known.
- 📋 **Longer horizon** — additional board/game profiles, measured optimization, platform qualification, and shared-host integration remain revisable.

## first-playable-game — First Playable Game

**Status:** Approved by the user on 2026-10-07. Phases 4–7; release version unassigned. Plans 04-01 through 04-15 are executed; gap-closure Plan 04-16 is planned. Fresh security review counted 46 threats (42 closed, four high disclosure threats remain open). Fresh code review confirms CR-02 and WR-04 fixed and records CR-03/WR-05 open; carried WR-01/WR-02/WR-03 remain open, while CR-01 is fixed history. HOST-02 and frontend QUAL-03 remain Pending. Phase 04 is incomplete pending the two repository repairs, fresh independent audit/review, and later actual pinned-app evidence. Phases 05–07 have not started.

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

**Plans**: 15/16 plans executed across 14 waves. Gap-closure plans 04-14 and 04-15 are complete in Waves 12 and 13; Plan 04-16 is planned in Wave 14. The fresh security and code-review audits are recorded; Phase 04 remains blocked by four high disclosure threats and open review findings, and still needs actual pinned-app evidence before completion.
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
- [ ] 04-16-PLAN.md — Repair newline-path diagnostic disclosure and contradictory review-state acceptance

**UI hint**: no

### Phase 5: Selected MVS Boot

**Goal**: A user can load the selected private MVS media and see the guest-executed game reach its attract/start path with a documented, bounded configuration.
**Depends on**: Phase 4; the sound-CPU interaction needed by BIOS/game boot is delivered here even though audible output is qualified in Phase 7.
**Requirements**: MEDIA-02, MEDIA-03, MEDIA-04, GAME-02
**Success Criteria** (what must be TRUE):
  1. A C integrator can supply immutable normalized cartridge and BIOS regions for the selected MVS profile under explicit lifetimes, layout, byte order, and resource limits.
  2. A user can load the selected unmodified local game and BIOS archives through a documented RetroArch/import path whose bounded archive handling stays outside the native core.
  3. A user gets distinct, actionable missing, incompatible, unsupported, malformed, and limit errors; after a rejected load, valid media can load or the instance can be destroyed safely.
  4. In the selected configuration, the guest reaches the game's attract/start path through the owned 68000 and required MVS banking, protection, timing, interrupts, and sound-CPU handshakes, with source-qualified regression evidence and no canned boot or fabricated handshake.

**Plans**: TBD

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

**Execution Order:** Phase 4 → Phase 5 → Phase 6 → Phase 7. Plans 04-01 through 04-15 are executed and summarized. T-04-11/T-04-15/T-04-18/T-04-20 remain high/open; CR-02/WR-04 are fixed, while CR-03/WR-05 and carried WR-01/WR-02/WR-03 remain open. Plan 04-15 preserved the unavailable actual pinned-app prerequisite; HOST-02/frontend QUAL-03 remain Pending. Next: plan Phase 04 gap closure, execute it, rerun independent audits, then attempt whole-phase verification only if the security gate clears. Actual RetroArch behavior remains unknown; do not advance to Phase 5.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 4. Public Playable Tracer | 15/15 | In Progress | - |
| 5. Selected MVS Boot | 0/TBD | Not started | - |
| 6. Active Title Control | 0/TBD | Not started | - |
| 7. Sound and Scenario Qualification | 0/TBD | Not started | - |
