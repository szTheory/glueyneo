# Requirements: First Playable Game

**Defined:** 2026-10-07
**Status:** Approved by the user on 2026-10-07; eight requirements are complete: TRAC-01/02/03, API-05, the bounded SND-01/02 candidate admissions, and HOST-02/QUAL-03 (2026-10-10 committed-snapshot receipt), documented below.
**Workstream / planning milestone ID:** `first-playable-game`
**Release version:** Unassigned. This planning identifier is not v0.2 and does not complete v0.1.
**Core Value:** Trustworthy Neo Geo emulation that other software can embed easily.

## Milestone Goal

A user can reach and control an active Metal Slug X scene, move and fire, see scrolling, and hear representative music and effects in one pinned MVS/macOS RetroArch setup using privately supplied game and BIOS media. Public CI proves a separate original fixture through the same native and libretro interfaces; it never establishes commercial-game compatibility by inference.

Scope comes from the accepted [workstream research](RESEARCH.md), the user's BIOS provision and ymfm exception decision, and the decision to reuse that research on 2026-10-07. [PROJECT.md](../../PROJECT.md), [METHODOLOGY.md](../../METHODOLOGY.md), and [AGENTS.md](../../../AGENTS.md) supply engineering and delivery constraints. The sibling [v0.1 state](../cpu-bus-diagnostic-sdk-alpha/STATE.md) retains its separate open Phase 03 hosted-evidence gate.

## v1 Requirements

Here, `v1` means this workstream's scoped deliverable, not a software release version. IDs continue existing category numbering; new categories begin at 01. Each ID maps to exactly one primary phase in the proposed roadmap; implementation remains pending.

### Original Playable Fixture

- [x] **TRAC-01**: A maintainer can rebuild a tiny original Neo Geo fixture from tracked source and assets, with documented generation tools, redistribution rights, notices, and assertion-oracle ancestry, without commercial game or production BIOS inputs.
- [x] **TRAC-02**: A C consumer can execute that fixture through the ordinary native API and observe a software frame produced by guest-driven board/video behavior, with checked pixel format, dimensions, pitch, and buffer bounds.
- [x] **TRAC-03**: A C consumer can supply a fixed logical input sequence and observe the fixture change its guest state and visible output according to independently justified expected results; a wrong-input control fails the assertions.

### Native and Frontend Integration

- [x] **HOST-02**: A user can load, run, and unload the fixture through a thin libretro adapter in an actual pinned macOS RetroArch build, using the ordinary native API, software video, documented controller mapping, and frontend-owned pacing.
- [x] **API-05**: A C integrator can advance the selected machine through a documented bounded frame operation with explicit input sampling, output-buffer ownership/lifetimes, video/audio capacities, audio sample format/channel layout/rate/produced count and relationship to emulated time, progress/stop information, and actionable errors, without native filesystem, device, network, or wall-clock services.
- [ ] **API-06**: A maintainer can repeat and partition the supported fixture workload and run distinguishable native instances interleaved and concurrently while matching isolated-baseline guest, video, and audio results at equal emulated boundaries. This is native-instance evidence, not a claim of libretro frontend reentrancy or public snapshot compatibility.

### Private Game and BIOS Loading

- [x] **MEDIA-02**: A C integrator can supply normalized immutable cartridge and BIOS regions for one documented MVS configuration under explicit media lifetimes, region layout, byte order, and resource limits.
- [ ] **MEDIA-03**: A user can load the selected local game and BIOS archives through one documented, tested RetroArch/import path, with archive/file handling outside the native core and without modifying the original archives. Required ZIP handling uses bounded parsing and an established decompressor.
- [ ] **MEDIA-04**: A user receives distinct, actionable errors for missing or incompatible BIOS/media, unsupported sets, malformed archives, and exceeded limits; after a rejected load, the consumer can load valid media or destroy the instance safely.

### Selected MVS Game Behavior

- [ ] **GAME-02**: A user can boot the selected Metal Slug X revision and BIOS configuration to its attract/start path through guest execution on the owned 68000 and required MVS board behavior, with added CPU, banking, interrupt/timing, and protection behavior tied to source-qualified regression evidence.
- [ ] **GAME-03**: A user can enter an active scene and control movement and firing through the documented RetroArch input mapping; results arise from the guest program and emulated machine rather than canned title-specific output.
- [ ] **GAME-04**: A user can observe the selected active scene's required graphics, layering, palettes, and scrolling, with the supported scene and unresolved raster/timing limitations documented and original hardware slowdown preserved where modeled.

### Sound Admission and Output

- [x] **SND-01**: A maintainer can reproduce admission of the pinned C Z80 candidate for the selected workload using license/source and mutable-state inventories plus cycle, interrupt, bus-effect, supported-boundary continuation, and independent-instance evidence.
- [x] **SND-02**: A maintainer can reproduce admission of a pinned ymfm YM2610 subset behind a private C interface under PROJECT-D-48, with license/source and mutable-state/callback inventories, deterministic clock/sample and instance-isolation evidence, contained C++ failure behavior, and exercised static/shared C-consumer linkage. The C++ exception alone is not admission.

The two completed sound requirements admit only the named synthetic Phase 04 Z80 workload and the selected pinned ymfm YM2610 candidate behind its private C interface. They do not establish a game sound-driver workload, audible game sound, silicon fidelity, or broad compatibility; SND-03/04 and Phase 5 handshakes remain pending.
- [ ] **SND-03**: A maintainer can run a guest-driven public sound fixture through the Z80/YM2610 path and reproduce non-silent, signal-qualified output with justified expected controls, distinguishing native chip timing/output from adapter resampling and frontend audio-device behavior.
- [ ] **SND-04**: A user hears representative game music and action-triggered effects while controlling the selected Metal Slug X scene in the pinned RetroArch setup; evidence identifies the covered scenario and any missing sound behavior.

### Qualification and Consumer Handoff

- [ ] **QUAL-01**: A maintainer can run clean-tree automated native and libretro-consumer checks using only the public fixture, covering equivalent frame/input/audio observations for the same guest/input sequence at matching emulated boundaries (accounting for documented audio conversion), lifecycle and malformed-input boundaries, relevant fuzz/sanitizer regressions, and retained diagnostic-SDK regressions through proportionate local/CI entrypoints.
- [ ] **QUAL-02**: A maintainer can reproduce a private local qualification scenario from boot through active movement, firing, scrolling, and sound in the actual pinned RetroArch build, retaining exact private media identities and derived evidence locally and publishing only permitted generic outcomes and public build/configuration identities. Machine-observable checks are automated; only residual subjective or unavailable evidence needs a human.
- [x] **QUAL-03**: An integrator can follow the documented build/install/load procedure for the native library and libretro adapter from a clean source tree on the selected macOS configuration, with exact dependency/compiler/SDK/OS/architecture/frontend identities and untested configurations stated explicitly.
- [ ] **QUAL-04**: A consumer can identify the exact qualified game scenario, public-fixture coverage, remaining unknown/unsupported behavior, and oracle ancestry in current documentation; emulator agreement, BIOS/archive integrity, and fixture success are not presented as broader hardware or game compatibility.

## Future Requirements

These are outlined follow-on work, not requirements for this milestone:

- Public snapshots, deterministic restored continuation, and durable saves under separate version and loss/recovery contracts. The next milestone's ordering should follow actual gameplay evidence and user priorities.
- Additional title/revision/BIOS/region/board scenarios, AES, broader protection and raster behavior, and full-game qualification.
- Measured optimization, additional platform qualification, and Playstead/shared-host integration after a representative workload exists.
- Incremental replacement of ymfm or an appropriately licensed C port if concrete portability, maintenance, or dependency costs justify it. Preserve provenance and behavioral regression evidence; no port or generic replacement framework is required now.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Completing v0.1's hosted release/authority gates or assigning this workstream a release version | Separately scoped lifecycle; v0.1 Phase 03 remains open |
| Full-game completion, broad cartridge compatibility, or hardware-perfect behavior | Acceptance is one stated scene/configuration with a bounded evidence claim |
| Public commercial ROM/BIOS distribution, private media checksums, captures, traces, or logs | Private qualification assets and derived evidence stay ignored and outside CI/releases |
| A core-owned GUI, device audio, filesystem, networking, or host pacing | RetroArch/import code owns host services; the native machine remains deterministic |
| Public save states, durable saves, rewind, run-ahead, and rollback netplay | Separate state/side-effect contracts are deferred |
| General archive support or a handwritten DEFLATE implementation | Prove the selected loading path with bounded established decompression only when needed |
| General permission for C++ runtime engines | PROJECT-D-48 is limited to the admitted ymfm dependency; owned runtime stays C17 |
| A ymfm C rewrite, plugin framework, JIT, speculative SIMD, or intra-machine threading | Not needed to establish this bounded playable result |
| Performance guarantees or broad embedded-platform claims | Require representative measured workloads and actual toolchain/device evidence |

## User Stories

- As a player, I can load my local media in RetroArch and control a stated Metal Slug X scene with visible scrolling and representative sound.
- As a C integrator, I can use explicit native media/input/output contracts without inheriting frontend or host-service dependencies.
- As a maintainer, I can reproduce meaningful public regressions without commercial media and keep the private game claim separate.

## Acceptance Criteria

Plans must select the exact public fixture, local scenario, MVS profile, frontend revision, controlled input sequence, observation boundaries, execution limits, and commands before claiming success. The early playable tracer and sound admission spikes inform later scope; a failed admission or unexpectedly large CPU/board gap triggers explicit bounded replanning, not a silent fallback or reduced acceptance.

Public fixture checks must assert guest-driven behavior and use meaningful wrong-behavior controls. Frame/audio hashes alone are not independent correctness oracles. Public C-consumer evidence must exercise actual static/shared linkage after adding the C++ dependency. Internal chip continuation checks do not establish a public board snapshot format. Passing fixture CI cannot close the private title requirement, and a mocked libretro consumer cannot establish actual RetroArch compatibility.

Keep public-source oracles separate from private local captures. Record source/configuration identities, executed assertions, outcome denominators, limitations, and pass/fail/skipped/unsupported/unknown results. Do not publish private media-derived outputs or identifiers. Retain MIT for original work and all required imported notices.

## Definition of Done

All 20 current requirements have current-revision evidence, documentation, and independent review for the specified scope. The public fixture works through native and libretro consumers, the selected private game scenario works in actual RetroArch, and sound admission is supported by evidence. Public fixture success without local game qualification does not complete the milestone. No release publication, broad platform support, silicon-perfect behavior, or completion of the sibling v0.1 milestone is implied.

## Traceability

Requirements and their primary phase allocation in [ROADMAP.md](ROADMAP.md) are user-approved. Eight requirements are complete: TRAC-01/02/03, API-05, bounded candidate-admission SND-01/02, HOST-02 and QUAL-03. HOST-02 and frontend QUAL-03 closed on 2026-10-10 from the passing committed-snapshot receipt at `706516b5a60c`, summarized in `phases/04-public-playable-tracer/04-FRONTEND-RECEIPT.json` and enforced by `tools/verify_playable.py --check-docs`.

Historical, superseded on 2026-10-10 by the receipt above: Plan 04-15 reconfirmed HOST-02 and frontend QUAL-03 as Pending from separate observation predicates. The materially changed, functioning launch context required for the pinned RetroArch 1.22.2 observation remains unavailable: the prior launch aborted with exit `-6` before a screenshot, LaunchServices returned `kLSNoExecutableErr`, unified-log inspection was blocked, and the current inventory showed no app window or process. No app was invoked; no current app, core, or fixture identity or actual frontend observation is available. The focused smoke-script contract suite does not satisfy either requirement. HOST-02 still lacks screenshot, stable no-input, RIGHT/LEFT, content-unload, normal-exit, ordinary content-load, guest-video, and frontend-pacing observations. QUAL-03 retains its documented build/install procedure and environment identity list, but its actual frontend load remains unobserved.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TRAC-01 | Phase 4 | Complete |
| TRAC-02 | Phase 4 | Complete |
| TRAC-03 | Phase 4 | Complete |
| HOST-02 | Phase 4 | Complete |
| API-05 | Phase 4 | Complete |
| API-06 | Phase 7 | Pending |
| MEDIA-02 | Phase 5 | Complete |
| MEDIA-03 | Phase 5 | Pending |
| MEDIA-04 | Phase 5 | Pending |
| GAME-02 | Phase 5 | Pending |
| GAME-03 | Phase 6 | Pending |
| GAME-04 | Phase 6 | Pending |
| SND-01 | Phase 4 | Complete |
| SND-02 | Phase 4 | Complete |
| SND-03 | Phase 7 | Pending |
| SND-04 | Phase 7 | Pending |
| QUAL-01 | Phase 7 | Pending |
| QUAL-02 | Phase 7 | Pending |
| QUAL-03 | Phase 4 | Complete |
| QUAL-04 | Phase 7 | Pending |

**Coverage:**

- Current requirements: 20
- Mapped to one primary phase: 20 (approved roadmap)
- Unmapped: 0
- Implemented: 8

---
*Requirements defined: 2026-10-07*
*Last updated: 2026-10-07 — user approved the roadmap and all 20 primary phase allocations; milestone initialization complete.*
