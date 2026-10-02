# Roadmap: Glueyneo

## Overview

Deliver an offline installable C SDK whose ordinary native API runs an original deterministic CPU/bus diagnostic. Qualify the CPU before SDK integration, demonstrate the complete consumer workflow, then distribute a tested unsigned alpha. Phase 1 plan evidence is recorded, but its phase-level verification found gaps; Phases 2–3 remain unplanned and release evidence remains pending. [PROJECT.md](PROJECT.md) and [REQUIREMENTS.md](REQUIREMENTS.md) govern scope; [research synthesis](research/SUMMARY.md), [roadmap seed](preparation/ROADMAP-SEED.md) and [adversarial gates](preparation/ADVERSARIAL-REVIEW.md) supply dated rationale.

## Milestones

- 🚧 **v0.1 CPU/bus diagnostic SDK alpha** — current; Phases 1–3 detailed below, ready for planning.
- 📋 **Next: Interactive diagnostic alpha** — outlined below; version and phase allocation await v0.1 evidence.
- **Longer horizon:** Commercial scenarios, hardware profiles, integration and measured performance; revisable, without release promises.

## v0.1 — CPU/bus diagnostic SDK alpha

**Milestone goal:** Deliver the qualified, offline installable CPU/bus diagnostic SDK and its complete unsigned release. All three phases below belong to v0.1.

## Phases

Integer phases are planned milestone work. Decimal phases are reserved for inserted work and execute in numeric order. Granularity is coarse; each phase will use small reviewable vertical plans.

- [ ] **Phase 1: CPU acceptance experiment** - Qualify a reproducible C backend with real guest, isolation, state and timing evidence.
- [ ] **Phase 2: Executable diagnostic SDK** - Run a meaningful original guest through a safe native API and real installed consumers.
- [ ] **Phase 3: Distributable release qualification** - Qualify relocated artifacts, delivery authority and a complete commit-bound unsigned release.

## Phase Details

### Phase 1: CPU acceptance experiment

**Goal**: As a maintainer, I want to reproduce acceptance of a C 68000 backend, so that I can build the diagnostic SDK on independent instances with explicit state and timing limits.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: CPU-01, CPU-02, CPU-03, CPU-04, CPU-05
**Success Criteria** (what must be TRUE):

  1. A maintainer can rebuild the pinned candidate and account for every copied, generated, compiled and distributed file, its notices and host calls, including demonstrated FPU/SoftFloat exclusion or complete retained disposition. (CPU-01)
  2. Distinguishable instances execute a tiny real guest alternately and concurrently with isolated-baseline results, including simultaneous cold initialization and failing creation/teardown; guest failures do not terminate or corrupt the host. (CPU-02; CPU-01 host-call disposition)
  3. A maintainer can observe guest-computed progress, bounded stops and overshoot, and the selected interrupt/exception interactions, with supported precision and unsupported behavior stated. (CPU-03)
  4. A maintainer can inspect the complete mutable-state/callback inventory and restore backend state at supported boundaries with identical continuation, excluding host pointers and jump buffers. (CPU-04)
  5. A maintainer can reproduce the explicit acceptance decision, commands and results against a finite effort/patch budget fixed before adaptation; failed or over-budget candidates have counterexamples and a replacement/replanning disposition. (CPU-05)

**Plans**: 4/6 plans completed; gap-closure plans are ready to execute

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Private guest, native source closure, regeneration and cumulative budget controls complete; failed attempts preserved; backend not admitted.

**Wave 2** *(complete)*

- [x] 01-02-PLAN.md — Independent/cold instances, compiled-state inventory and bounded host failures pass; native ASan/UBSan and TSan evidence retained.

**Wave 3** *(complete)*

- [x] 01-03-PLAN.md — Qualify timing and complete fresh-destination continuation.

**Wave 4** *(plan execution complete; verification gaps found)*

- [x] 01-04-PLAN.md — The bounded private-candidate acceptance receipt was sealed. A later independent phase review found six blockers; current backend admission is unresolved.

**Wave 5** *(gap closure; follows Wave 4)*

- [ ] 01-05-PLAN.md — Correct the canonical MVP story, preserve historical evidence, and record a truthful current candidate disposition.

**Wave 6** *(blocked on Wave 5 completion)*

- [ ] 01-06-PLAN.md — Pause for developer direction before any further backend work or scope change.

Planning guidance: First set a concrete finite effort cap, patch budget and stopping/replacement rules. Then use small CMake/CTest experiment scaffolding, a licensed original tiny guest, source/host-call audit, and isolation/timing/continuation experiments. Evaluate the research's pinned Musashi candidate without presuming acceptance. Inventory future sound candidates only as needed; a Z80/YM2610 port is not admission work for this alpha.

**Admission gate:** CPU-01–04 are Pending for current admission. Historical task evidence exists; the phase verifier refused grammar preflight rather than establish that all four behaviors failed. At plan 01-05 task 1, CPU-05 is Pending final disposition; task 3 owns its evidence-conditioned requirement result. Both adaptation attempts are consumed; no further adaptation is authorized. Execution closes governance gaps and does not qualify the backend. CPU-05 may be satisfied by a reproducible rejection or deferral. That does not satisfy CPU-01–04 or complete this phase. The historical 01-04 accepted receipt is contradicted for current admission by six later source blockers. Phase 01 remains open with `gaps_found`, and Phase 02 stays gated until accepted evidence and fresh phase verification or an explicitly reconciled roadmap revision. Plan 01-06 owns developer direction before further work. Research prose, a context-shaped stub or a global execution lock does not establish acceptance. Backend continuation here establishes no public board-snapshot contract.

### Phase 2: Executable diagnostic SDK

**Goal**: An external C integrator can install an offline SDK and execute a meaningful original CPU/bus diagnostic through its ordinary native API, with safe failures and reproducible evidence.
**Mode:** mvp
**Depends on**: Phase 1 acceptance gate
**Requirements**: API-01, API-02, API-03, API-04, DIAG-01, DIAG-02, DIAG-03, BUILD-01, BUILD-02, EVID-01, EVID-02, EVID-03, EVID-04, DOC-01, DOC-02
**Success Criteria** (what must be TRUE):

  1. An integrator can create/reset/destroy an opaque host-independent instance, load bounded diagnostic regions under explicit immutable-media ownership, and receive actionable errors with safe recovery/destruction for invalid sizes, unsupported capabilities, lifecycle misuse and allocation/load failures, without leaks, process exit or unintended state mutation. (API-01, API-02, API-04)
  2. An external consumer's create/load/run/results/destroy flow executes the original guest through bounded native calls reporting actual progress and stop reasons; initialized-data/BSS and named CPU/bus observations match justified oracles, and a deliberate wrong-behavior control fails. (API-03, DIAG-01, DIAG-02)
  3. Maintainers obtain isolated-baseline guest observations at equal boundaries for repeat/split execution and distinguishable native instances run both interleaved and concurrently, including concurrent native creation/load/teardown. Meaningful boundary/lifecycle/property, bounded input/call-sequence fuzz and supported sanitizer results retain discovered regressions. (DIAG-03, EVID-02)
  4. An integrator builds C17 static/shared libraries offline with target-scoped CMake/CTest and pinned test-only Unity, executes the diagnostic from out-of-tree installed C consumers for both variants, and compiles/links C++ public-header consumers. Compiled getting-started, ownership/error and failure-reproduction guidance matches the artifacts and states the exact supported subset and excluded game/BIOS/video/audio/public-state/persistence claims. (BUILD-01, BUILD-02, DOC-01, DOC-02)
  5. A maintainer can audit every public dependency/fixture's rights, notices, source and recipe, output digest, firmware needs and oracle ancestry; reproduce nonempty machine-readable results with exact identities and distinct outcomes; and reproduce diagnostic execution, memory/allocation, load and build-cost baselines on named hosts with uncertainty and no gameplay or uncalibrated-threshold claims. (EVID-01, EVID-03, EVID-04)

**Plans**: TBD

Planning guidance: Slice from opaque lifecycle and bounded media through the real diagnostic and installed consumer; add only its evidenced bus/bootstrap subset. Couple each behavior to its tests, provenance, compiled example and capability statement. Separate diagnostic-oracle research from standard package work. Begin lightweight CI and public-content checks as infrastructure permits; final hosted delivery acceptance belongs to Phase 3.

### Phase 3: Distributable release qualification

**Goal**: A release consumer can download a complete unsigned SDK bound to a tested commit, rebuild or relocate it, and reproduce its diagnostic under truthful support claims.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: BUILD-03, BUILD-04, DEL-01, DEL-02, DEL-03, DEL-04, DEL-05
**Success Criteria** (what must be TRUE):

  1. An integrator executes the relocated installed diagnostic after original source/build/install access is removed, rebuilds the release source archive offline, and can identify exercised compiler/SDK/OS/architecture/build combinations with failed, skipped, unsupported and untested cases explicit. (BUILD-03, BUILD-04)
  2. A maintainer receives an always-started aggregate required CI check with conservative change classification and meaningful execution counts, plus recorded cold-build, critical-path and runner-minute evidence. (DEL-01)
  3. Qualifying PRs merge through protection only after current-revision required checks and independent review; setup/shipping issue and PR triage and actual bot/App event behavior demonstrate unattended operation with untrusted execution separated from publication authority. (DEL-02)
  4. Pinned release-please automation uses one C version source to stage a complete unsigned SDK draft bound to the tested commit, recovers interrupted staging and no-new-release retries, refuses incomplete/wrong-commit publication, and yields a published download whose expected digests and real diagnostic consumer pass. (DEL-03, DEL-04)
  5. A maintainer can inspect public-content evidence covering source, documentation, commit identity, logs and archives for notices and exclusion of personal paths/private identity, secrets, commercial media and private corpus material before publication. (DEL-05)

**Plans**: TBD

Planning guidance: Qualify relocated/offline consumers and the exact support matrix; then required checks/protected PRs and the actual release event/recovery graph; then stage, inspect, publish and verify the downloaded artifacts. Do not wait for a tag event that the configured draft flow cannot emit. Treat action/service behavior as requiring current qualification. Unsigned SDK delivery does not require application notarization.

**Delivery dependency:** Remote repository, hosted CI, protection and release authority are not configured. This is a future delivery dependency, not a present blocker to implementation or artifact qualification. Keep affected delivery requirements pending until actual authority and event behavior are exercised; never substitute local green results for them.

## Progress

Execution order: 1 → 2 → 3, subject to the explicit backend admission gate.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. CPU acceptance experiment | v0.1 | 4/4 | Verification gaps found; gap planning required | - |
| 2. Executable diagnostic SDK | v0.1 | 0/TBD | Not started | - |
| 3. Distributable release qualification | v0.1 | 0/TBD | Not started | - |

Coverage: 27/27 current requirements assigned exactly once; 5 in Phase 1, 15 in Phase 2, 7 in Phase 3. Task-level records for CPU-01–05 exist, but phase verification is `gaps_found` and later source findings block current backend admission; the other 22 remain Pending in [traceability](REQUIREMENTS.md#traceability). Deferred v2 requirements are not allocated to these phases.

## Next Milestone Outline — Interactive Diagnostic Alpha

This is an outline, not allocated phase scope or a promised release version. Refresh it from v0.1 receipts before assigning requirements and phases.

- **Visible and audible diagnostic:** An original guest exercises selected FIX/sprite/palette behavior and logically sampled input under an explicit board/timing and firmware/bootstrap strategy. Real chip-generated sound follows separate C Z80/YM2610 license, instance, state and timing admission gates, with raw emulated output distinguished from host resampling/device evidence. (Deferred PLAY-01, PLAY-02)
- **Real frontend qualification:** A thin libretro adapter uses the ordinary native API and matches native observations. A released core loads, runs and unloads in an actual pinned RetroArch macOS build, recording architecture, core/frontend/media/firmware identities and output evidence; a contract host alone is insufficient. (Deferred HOST-01)
- **Continuation and persistence:** Fresh-instance restoration matches uninterrupted execution; malformed/incompatible snapshots reject atomically. A fresh process reopens durable data that the guest demonstrably consumes. Restoring old snapshots and receiving stale acknowledgments cannot lose newer dirty data. ABI, snapshots, replay and durable-save identities remain distinct. (Deferred STATE-01, SAVE-01)

## Revisable Longer Horizon

1. Qualify a practical host-side media importer, useful BIOS/set/revision diagnostics and a first private commercial scenario with explicit game/BIOS/region/mode identity and public minimal regressions where lawful.
2. Expand original BIOS/board profiles and banking, protection, raster, audio and peripheral families from concrete evidence, preserving hardware slowdown and recording unknowns.
3. Demonstrate Playstead integration and a second real consumer before stabilizing broader API policy; select a minimal SDL3 host only for a recurring integration need.
4. Optimize representative measured workloads with behavior equivalence and controlled-host calibration. Revisit broader platforms and optional advanced state features only when correctness and maintenance evidence support them.

At milestone close, reconcile requirement evidence and failures, triage relevant issues/PRs, refresh docs and actual support claims, review diagnostic/CI costs, and revise the next outline and horizon. Preparation remains provenance; no historical sibling-project receipt proves Glueyneo behavior.
