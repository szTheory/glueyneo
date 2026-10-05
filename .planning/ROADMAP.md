# Roadmap: Glueyneo

## Overview

Deliver an offline installable C SDK whose ordinary native API runs an original deterministic CPU/bus diagnostic. Qualify the CPU before SDK integration, demonstrate the complete consumer workflow, then distribute a tested unsigned alpha. Phase 1 has 27 plan summaries across 28 plans; the fresh 2026-10-05 verdict is 8/9 GAPS_FOUND with the old report-binding issue closed and Plan 01-28 repairing the sole documentation gap, while Phases 2–3 remain unplanned and release evidence remains pending. [PROJECT.md](PROJECT.md) and [REQUIREMENTS.md](REQUIREMENTS.md) govern scope; [research synthesis](research/SUMMARY.md), [roadmap seed](preparation/ROADMAP-SEED.md) and [adversarial gates](preparation/ADVERSARIAL-REVIEW.md) supply dated rationale.

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

  1. A maintainer can build the owned C17 candidate and account for every authored, copied, generated, compiled and distributed file, its notices and host calls, with imported CPU/FPU/SoftFloat/generator code excluded from its runtime closure. (CPU-01)
  2. Distinguishable instances execute a tiny real guest alternately and concurrently with isolated-baseline results, including simultaneous cold initialization and failing creation/teardown; guest failures do not terminate or corrupt the host. (CPU-02; CPU-01 host-call disposition)
  3. A maintainer can observe guest-computed progress, bounded stops and overshoot, and the selected interrupt/exception interactions, with supported precision and unsupported behavior stated. (CPU-03)
  4. A maintainer can inspect the complete mutable-state/callback inventory and restore backend state at supported boundaries with identical continuation, excluding host pointers and jump buffers. (CPU-04)
  5. A maintainer can reproduce the explicit owned-core decision, commands and results against finite effort/churn limits fixed before implementation; failed work and findings are preserved, actionable issues receive budgeted repair, and resource thresholds trigger review/replanning rather than automatic backend rejection. (CPU-05)

**Plans**: 26/28 execution-complete; 27 plans have summaries, including Plan 01-17, which remains incomplete at its answered checkpoint. Plan 01-27 closed the report-binding failure at C2. The fresh 2026-10-05 `01-VERIFICATION.md` is 8/9 `GAPS_FOUND`: it confirms the old binding issue is closed and identifies one current ROADMAP/validator wording gap plus a stale README route. Plan 01-28 addresses only those findings and is ready for gap-only execution. UAT rows 1–49 remain historical evidence; row 49 recorded the earlier README route. The receipt remains unqualified and admission deferred; CPU-01–05 remain Pending, Phase 01 is open, and Phase 02 stays gated. After Plan 01-28 execution, dispatch one fresh whole-phase `gsd-verifier` directly; the installed GSD 1.15.0 router mishandles this `gaps_found` report. See [the dated routing diagnosis](preparation/2026-10-04-gsd-verification-loop.md).

Plans:

**Wave 28** *(bounded gap closure; follows Wave 27)*
- [ ] 01-28-PLAN.md — Restore the verified CPU-05 documentation interface, route contributors through canonical state, and add bounded local regression evidence; phase verification remains separate
- [x] 01-27-PLAN.md — Preserve the stale security-binding failure and prior seal; independently rebind exact reports and reproduce the deferred seal; separate phase-goal verification remains required
- [x] 01-26-PLAN.md — Reconcile the canonical gate wording and reproduce the read-only decision checks
- [x] 01-17-PLAN.md (answered checkpoint; incomplete)

**Wave 18** *(gap closure; follows the answered Wave 17 checkpoint)*
- [x] 01-18-PLAN.md

**Wave 19** *(complete)*
- [x] 01-19-PLAN.md

**Wave 20** *(complete)*
- [x] 01-20-PLAN.md

**Wave 21** *(complete; admission deferred)*
- [x] 01-21-PLAN.md — Independent source/security review and exact deferred seal completed after preserving and recovering stale derived metadata. The temporary T-01-43 binding blocker is resolved; later phase-review findings remain open for Plans 01-22–01-25.

**Wave 22** *(gap closure; follows Wave 21)*
- [x] 01-22-PLAN.md — Repair CR-01 continuation behavior and bind expanded continuation to a distinct receipt profile; retain unknown silicon behavior.

**Wave 23** *(gap closure; depends on Wave 22)*
- [x] 01-23-PLAN.md — Make cumulative churn monotonic, align exact-cap sealing, and correct contributor-facing README status.

**Wave 24** *(gap closure; complete)*
- [x] 01-24-PLAN.md — Rebuild and qualify the repaired source across the owned debug, release and sanitizer lanes with exact identities; preserve the 15/90 profile and old seal history.

**Wave 25** *(gap closure; complete; admission deferred)*
- [x] 01-25-PLAN.md — Independently reassess the four findings, preserve and append UAT outcomes, and seal the exact source with admission deferred. Separate phase-goal verification remains pending.

- [x] 01-15-PLAN.md
- [x] 01-16-PLAN.md

**Wave 1**

- [x] 01-01-PLAN.md — Private guest, native source closure, regeneration and cumulative budget controls complete; failed attempts preserved; backend not admitted.

**Wave 2** *(complete)*

- [x] 01-02-PLAN.md — Independent/cold instances, compiled-state inventory and bounded host failures pass; native ASan/UBSan and TSan evidence retained.

**Wave 3** *(complete)*

- [x] 01-03-PLAN.md — Qualify timing and complete fresh-destination continuation.

**Wave 4** *(plan execution complete; verification gaps found)*

- [x] 01-04-PLAN.md — The bounded private-candidate acceptance receipt was sealed. A later independent phase review found six blockers; current backend admission is unresolved.

**Wave 5** *(gap closure; follows Wave 4)*

- [x] 01-05-PLAN.md — Correct the canonical MVP story, preserve historical evidence, and record a truthful current candidate disposition.

**Wave 6** *(historical direction checkpoint; later owned-core planning approved)*

- [x] 01-06-PLAN.md — Developer selected C: reject/defer the current candidate and discuss backend replanning; implementation work is authorized only within reviewed owned-core gap plans.

**Wave 7** *(gap closure; contract and budget)*

- [x] 01-07-PLAN.md — Reconcile the owned-core acceptance contract and freeze its separate budget without changing historical Musashi accounting; no CPU runtime has been accepted.

**Wave 8** *(gap closure; diagnostic tracer complete)*

- [x] 01-08-PLAN.md — Execute the original diagnostic through the owned CPU's private whole-core seam; first measured diagnostic gate passed without backend admission.

**Wave 9** *(gap closure complete; timing and exceptions)*

- [x] 01-09-PLAN.md — Qualify named interrupt, exception, instruction-boundary timing, and bus limits with a 23-case timing harness; admission remains open.

**Wave 10** *(gap closure complete; instance safety and inventory)*

- [x] 01-10-PLAN.md — Prove cold/concurrent instance isolation, fault containment, and source-bound mutable-state inventory on the current native host; broader portability remains open.

**Wave 11** *(next; continuation)*

- [x] 01-11-PLAN.md — Restore captured state into a fresh destination and prove identical continuation and atomic rejection.

**Wave 12** *(blocked on Waves 8–11; independent qualification)*

- [x] 01-12-PLAN.md — Independently review the owned implementation and fix findings within a bounded source/test tranche.

**Wave 13** *(blocked on Wave 12; source inventory and fresh evidence)*

- [x] 01-13-PLAN.md — Complete source/rights inventory, portable presets, collector controls and current execution evidence.

**Wave 14** *(blocked on Wave 13; final independent review and disposition)*

- [x] 01-14-PLAN.md — Independently review the final revision, repair narrow evidence-tool findings, and seal only a fully supported disposition.

**Wave 15** *(F14-03 gap closure; source and direct behavior reconciliation)*

- [x] 01-15-PLAN.md — Exact-source interpretation completed through unresolved branch; original freeze and behavior preserved, F14-03 HIGH/open.

**Wave 16** *(F14-03 gap closure; depends on Wave 15; qualification and review)*

- [x] 01-16-PLAN.md — Exact identities and fresh lanes independently reviewed; F14-03 HIGH/open, sealed unqualified/GAPS_FOUND.

**Wave 17** *(F14-03 gap closure; depends on Wave 16; answered decision checkpoint, still incomplete)*

- [x] 01-17-PLAN.md — Acquire and independently adjudicate additional applicable original-MC68000 evidence; preserve HIGH/open and stop at a decision checkpoint if unresolved. The owner preserved hardware uncertainty (P01-C-13); P01-C-14 later selected a candidate-only `0x4AFC` unsupported boundary. Plans 01-18–01-21 reconcile that claim without rewriting this evidence record.

Planning guidance: Plans 01-07–01-14 built and assessed the owned-core candidate; Plans 01-15–01-17 preserve the original-silicon uncertainty and answered checkpoint. P01-C-14 excludes exact `0x4AFC` from this candidate only; original-silicon saved PC remains unknown. Plans 01-18–01-27 close scoped candidate and evidence gaps, but do not admit the backend or complete Phase 01. Plan 01-27 has an exact deferred seal; fresh verification confirms the prior binding issue is closed and Plan 01-28 targets the remaining bounded documentation gap. Only a fresh phase-goal verifier can pass Phase 01 and permit Phase 02. Because the installed status/execution router mishandles the current `gaps_found` report, run the planned gap-only execution, then dispatch `gsd-verifier` directly once and pause before routing any findings. See [the dated routing diagnosis](preparation/2026-10-04-gsd-verification-loop.md).

**Admission gate:** CPU-01–05 remain Pending. Historical task evidence and the old Musashi rejection decision do not qualify current backend admission; both Musashi adaptation attempts are consumed. The candidate-only exact `0x4AFC` exclusion and later bounded repairs remain unqualified pending fresh phase-goal verification. Plan 01-27 closed only the stale security-report binding: it preserves the failed reproduction and old seal, independently rebinds exact report bytes, and retains admission deferred. Fresh verification on 2026-10-05 is 8/9 `GAPS_FOUND`, confirms that binding is current and identifies the documentation/validator mismatch addressed by Plan 01-28. Phase 01 remains open / GAPS_FOUND and Phase 02 gated. Original-silicon saved PC remains unknown; no phase admission or hardware result is inferred from this scoped gap plan.

### Phase 2: Executable diagnostic SDK

**Goal**: As a C integrator, I want to install an offline SDK and run a meaningful original CPU/bus diagnostic through its ordinary native API and a headless runner, so that I can reproduce results with safe failures and clear evidence.
**Mode:** mvp
**Depends on**: Phase 1 acceptance gate
**Requirements**: API-01, API-02, API-03, API-04, DIAG-01, DIAG-02, DIAG-03, BUILD-01, BUILD-02, EVID-01, EVID-02, EVID-03, EVID-04, DOC-01, DOC-02
**Success Criteria** (what must be TRUE):

  1. An integrator can create/reset/destroy an opaque host-independent instance, load bounded diagnostic regions under explicit immutable-media ownership, and receive actionable errors with safe recovery/destruction for invalid sizes, unsupported capabilities, lifecycle misuse and allocation/load failures, without leaks, process exit or unintended state mutation. (API-01, API-02, API-04)
  2. An external consumer's create/load/run/results/destroy flow and a headless diagnostic runner execute the same original guest through the ordinary native API; bounded calls report actual progress and stop reasons, initialized-data/BSS and named CPU/bus observations match justified oracles, and a deliberate wrong-behavior control fails. (API-03, DIAG-01, DIAG-02)
  3. Maintainers obtain isolated-baseline guest observations at equal boundaries for repeat/split execution and distinguishable native instances run both interleaved and concurrently, including concurrent native creation/load/teardown. Meaningful boundary/lifecycle/property, bounded input/call-sequence fuzz and supported sanitizer results retain discovered regressions. (DIAG-03, EVID-02)
  4. An integrator builds C17 static/shared libraries offline with target-scoped CMake/CTest and pinned test-only Unity, executes the diagnostic from out-of-tree installed C consumers for both variants, and compiles/links C++ public-header consumers. Compiled getting-started, ownership/error and failure-reproduction guidance matches the artifacts and states the exact supported subset and excluded game/BIOS/video/audio/public-state/persistence claims. (BUILD-01, BUILD-02, DOC-01, DOC-02)
  5. A maintainer can audit every public dependency/fixture's rights, notices, source and recipe, output digest, firmware needs and oracle ancestry; reproduce nonempty machine-readable results with exact identities and distinct outcomes; and reproduce diagnostic execution, memory/allocation, load and build-cost baselines on named hosts with uncertainty and no gameplay or uncalibrated-threshold claims. (EVID-01, EVID-03, EVID-04)

**Plans**: TBD

Planning guidance: Slice from opaque lifecycle and bounded media through the real diagnostic and installed consumer; add only its evidenced bus/bootstrap subset. Couple each behavior to its tests, provenance, compiled example and capability statement. Separate diagnostic-oracle research from standard package work. Begin lightweight CI and public-content checks as infrastructure permits; final hosted delivery acceptance belongs to Phase 3.

### Phase 3: Distributable release qualification

**Goal**: As a release consumer, I want to download a complete unsigned SDK bound to a tested commit and rebuild or relocate it, so that I can reproduce its diagnostic under truthful support claims.
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

| Phase | Milestone | Execution-complete plans | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. CPU acceptance experiment | v0.1 | 26/28 | In Progress|  |
| 2. Executable diagnostic SDK | v0.1 | 0/TBD | Not started | - |
| 3. Distributable release qualification | v0.1 | 0/TBD | Not started | - |

Coverage: 27/27 current requirements assigned exactly once; 5 in Phase 1, 15 in Phase 2, 7 in Phase 3. Task-level records for CPU-01–05 exist, but current phase-goal verification must be refreshed before any admission decision; backend admission remains deferred and the other 22 remain Pending in [traceability](REQUIREMENTS.md#traceability). Deferred v2 requirements are not allocated to these phases.

## Next Milestone Outline — Interactive Diagnostic Alpha

This is an outline, not allocated phase scope or a promised release version. Refresh it from v0.1 receipts before assigning requirements and phases.

- **Visible and audible diagnostic:** An original guest exercises selected FIX/sprite/palette behavior and logically sampled input under an explicit board/timing and firmware/bootstrap strategy. Real chip-generated sound follows separate C Z80/YM2610 license, instance, state and timing admission gates, with raw emulated output distinguished from host resampling/device evidence. (Deferred PLAY-01, PLAY-02)
- **Real frontend qualification:** A thin libretro adapter uses the ordinary native API and matches native observations. A released core loads, runs and unloads in an actual pinned RetroArch macOS build, recording architecture, core/frontend/media/firmware identities and output evidence; a contract host alone is insufficient. (Deferred HOST-01)
- **Continuation and persistence:** Fresh-instance restoration matches uninterrupted execution; malformed/incompatible snapshots reject atomically. A fresh process reopens durable data that the guest demonstrably consumes. Restoring old snapshots and receiving stale acknowledgments cannot lose newer dirty data. ABI, snapshots, replay and durable-save identities remain distinct. (Deferred STATE-01, SAVE-01)

## Revisable Longer Horizon

1. Qualify a practical host-side media importer, useful BIOS/set/revision diagnostics and a first private commercial scenario with explicit game/BIOS/region/mode identity and public minimal regressions where lawful.
2. Expand original BIOS/board profiles and banking, protection, raster, audio and peripheral families from concrete evidence, preserving hardware slowdown and recording unknowns.
3. Demonstrate Playstead or shared-host integration and a second real consumer before stabilizing broader API policy. Interactive GUI ownership stays outside individual core repositories. For process integration, qualify the ROM path and explicit save-directory override, prove no save is written beside the ROM, verify periodic and on-demand battery-save flush with a stated loss window, test graceful SIGTERM shutdown, and verify distinct exit codes for normal completion, guest errors, and host errors. Treat these as target requirements, not current Playstead support: `AdapterPin.json` and `SUPPORT-MATRIX.md` at inspected revision `1de3e954166eaf0a52fe0e4a950b46756139884d` (2026-10-02) specify `{saveDir}/{romBaseName}.sav`, periodic flush every 24 seconds, no on-demand flush, a 24-second loss window, and SIGTERM classified as killed rather than graceful save-and-quit. Recheck the live launcher contract when planning this work.
4. Optimize representative measured workloads with behavior equivalence and controlled-host calibration. Revisit broader platforms and optional advanced state features only when correctness and maintenance evidence support them.

At milestone close, reconcile requirement evidence and failures, triage relevant issues/PRs, refresh docs and actual support claims, review diagnostic/CI costs, and revise the next outline and horizon. Preparation remains provenance; no historical sibling-project receipt proves Glueyneo behavior.
