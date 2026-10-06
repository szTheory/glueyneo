# Roadmap: Glueyneo

## Overview

Deliver an offline installable C SDK whose ordinary native API runs an original deterministic CPU/bus diagnostic. Phase 01 accepted the owned CPU backend for the bounded diagnostic subset. Phase 02 builds the SDK and proves the complete consumer workflow; Phase 03 qualifies and distributes a tested unsigned alpha. The fresh 2026-10-05 Phase 01 report passed 10/10 after Plan 01-29; see its verification report for source identity, current checks, and limitations. The candidate-level receipt remains `unqualified`, while the independent phase report is the current bounded admission decision. Phase 02 has six independently checked plans and is ready for execution; Phase 03 remains unplanned with delivery evidence pending. [PROJECT.md](PROJECT.md) and [REQUIREMENTS.md](REQUIREMENTS.md) govern scope; [research synthesis](research/SUMMARY.md), [roadmap seed](preparation/ROADMAP-SEED.md) and [adversarial gates](preparation/ADVERSARIAL-REVIEW.md) supply dated rationale.

## Milestones

- 🚧 **v0.1 CPU/bus diagnostic SDK alpha** — current; Phase 02 execution is in progress, with Phase 03 delivery evidence pending.
- 📋 **Next: Interactive diagnostic alpha** — outlined below; version and phase allocation await v0.1 evidence.
- **Longer horizon:** Commercial scenarios, hardware profiles, integration and measured performance; revisable, without release promises.

## v0.1 — CPU/bus diagnostic SDK alpha

**Milestone goal:** Deliver the qualified, offline installable CPU/bus diagnostic SDK and its complete unsigned release. All three phases below belong to v0.1.

## Phases

Integer phases are planned milestone work. Decimal phases are reserved for inserted work and execute in numeric order. Granularity is coarse; each phase will use small reviewable vertical plans.

- [x] **Phase 1: CPU acceptance experiment** - Qualify a reproducible C backend with real guest, isolation, state and timing evidence. (completed 2026-10-05)
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

**Plans**: 28/29 execution-complete; all 29 have summaries. Plan 01-17 remains an answered, incomplete hardware-evidence checkpoint; the unresolved original-silicon saved-PC question stays unknown and outside the accepted candidate capability. Plan 01-29's independent CPU review recommends bounded acceptance, and its security review found zero HIGH/CRITICAL blockers. The separate fresh 2026-10-05 [whole-phase report](phases/01-cpu-acceptance-experiment/01-VERIFICATION.md) passed 10/10 and establishes Phase 01 acceptance for the exact bounded CPU subset. Phase 02 is unblocked. The candidate receipt remains `unqualified` as a frozen experiment artifact; no receipt, seal, source collection, or historical UAT row was rewritten or replayed. Do not repeat Plan 01-29 or the same-evidence verifier pass.

Plans:

**Wave 29** *(bounded gap closure; follows Wave 28)*
- [x] 01-29-PLAN.md — Independent CPU-01–05 review supports bounded acceptance; the separate Phase 01 verifier subsequently passed 10/10

**Wave 28** *(bounded gap closure; follows Wave 27)*
- [x] 01-28-PLAN.md — Restore the verified CPU-05 documentation interface, route contributors through canonical state, and add bounded local regression evidence; phase verification remains separate
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

Planning guidance: Plans 01-07–01-14 built and assessed the owned-core candidate; Plans 01-15–01-17 preserve original-silicon uncertainty and the answered checkpoint. P01-C-14 excludes exact `0x4AFC` from this candidate only; original-silicon saved PC remains unknown. Plans 01-18–01-29 repaired and assessed bounded candidate evidence. The fresh whole-phase verifier passed 10/10 and admits this candidate only for the bounded diagnostic scope. Plan 01-29 and its verifier pass are complete; do not repeat them, replay historical UAT, or restart the silicon evidence search.

**Admission status:** Phase 01 passed whole-phase verification (10/10); Phase 02 is unblocked. The fresh report admits CPU-01–05 for the bounded owned diagnostic subset, with WR-01 retained as a documentation warning. The candidate-level receipt remains `unqualified`; its historical `phase_admitted: false` value was not changed. This phase decision does not establish original-silicon saved-PC behavior, full ISA coverage, board timing, BIOS/game compatibility, platform support, or performance. The original-silicon saved PC remains unknown, and exact `0x4AFC` remains unsupported for this candidate only. The frozen `tools/owned_cpu/contract.py` check records the pre-admission gate at source revision `09476ed`; it is historical evidence, not the current phase router. A post-closeout fingerprint check reports the Phase 01 report stale because planning files changed; per METHODOLOGY.md, do not repeat verification for these administrative updates. Follow this roadmap and STATE for current admission and next-step routing.

### Phase 2: Executable diagnostic SDK

**Goal**: As a C integrator, I want to install an offline SDK and run a meaningful original CPU/bus diagnostic through its ordinary native API and a headless runner, so that I can reproduce results with safe failures and clear evidence.
**Mode:** mvp
**Depends on**: Phase 1 acceptance gate (passed for the bounded candidate scope on 2026-10-05)
**Requirements**: API-01, API-02, API-03, API-04, DIAG-01, DIAG-02, DIAG-03, BUILD-01, BUILD-02, EVID-01, EVID-02, EVID-03, EVID-04, DOC-01, DOC-02
**Success Criteria** (what must be TRUE):

  1. An integrator can create/reset/destroy an opaque host-independent instance, load bounded diagnostic regions under explicit immutable-media ownership, and receive actionable errors with safe recovery/destruction for invalid sizes, unsupported capabilities, lifecycle misuse and allocation/load failures, without leaks, process exit or unintended state mutation. (API-01, API-02, API-04)
  2. An external consumer's create/load/run/results/destroy flow and a headless diagnostic runner execute the same original guest through the ordinary native API; bounded calls report actual progress and stop reasons, initialized-data/BSS and named CPU/bus observations match justified oracles, and a deliberate wrong-behavior control fails. (API-03, DIAG-01, DIAG-02)
  3. Maintainers obtain isolated-baseline guest observations at equal boundaries for repeat/split execution and distinguishable native instances run both interleaved and concurrently, including concurrent native creation/load/teardown. Meaningful boundary/lifecycle/property, bounded input/call-sequence fuzz and supported sanitizer results retain discovered regressions. (DIAG-03, EVID-02)
  4. An integrator builds C17 static/shared libraries offline with target-scoped CMake/CTest and pinned test-only Unity, executes the diagnostic from out-of-tree installed C consumers for both variants, and compiles/links C++ public-header consumers. Compiled getting-started, ownership/error and failure-reproduction guidance matches the artifacts and states the exact supported subset and excluded game/BIOS/video/audio/public-state/persistence claims. (BUILD-01, BUILD-02, DOC-01, DOC-02)
  5. A maintainer can audit every public dependency/fixture's rights, notices, source and recipe, output digest, firmware needs and oracle ancestry; reproduce nonempty machine-readable results with exact identities and distinct outcomes; and reproduce diagnostic execution, memory/allocation, load and build-cost baselines on named hosts with uncertainty and no gameplay or uncalibrated-threshold claims. (EVID-01, EVID-03, EVID-04)

**Plans**: 1/6 plans executed

Plans:
**Wave 1**
- [x] 02-01-PLAN.md — Ordinary API/runner tracer, original fixture and counted Wave 0 verification

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 02-02-PLAN.md — Copied transactional media, lifecycle and allocation-failure recovery

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 02-03-PLAN.md — Bounded timing, exact controls and independent-instance determinism

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 02-04-PLAN.md — Offline static/shared installs, relocated C/C++ consumers and compiled guides

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 02-05-PLAN.md — Bounded hostile mutation, retained regressions and supported sanitizers

**Wave 6** *(blocked on Wave 5 completion)*
- [ ] 02-06-PLAN.md — Exact identities/outcomes, measured local baselines and final aggregate

Execution waves: 1 → 2 → 3 → 4 → 5 → 6. Package checks rebuild the runtime, so they follow source-changing ownership/timing slices. Phase 02 remains unexecuted; separate plan checking precedes execution.

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

Execution order: 1 → 2 → 3. Phase 01's bounded backend admission gate is satisfied. Phase 02 execution is in progress; Plan 02-01 is complete and Plan 02-02 is next.

| Phase | Milestone | Execution-complete plans | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. CPU acceptance experiment | v0.1 | 28/29 (01-17 remains a checkpoint) | Complete | 2026-10-05 |
| 2. Executable diagnostic SDK | v0.1 | 1/6 | In Progress | - |
| 3. Distributable release qualification | v0.1 | 0/TBD | Not started | - |

Coverage: 27/27 current requirements are assigned exactly once; 5 in Phase 1, 15 in Phase 2, and 7 in Phase 3. CPU-01–05 are Complete for Phase 01's bounded backend acceptance. The other 22 remain Pending in [traceability](REQUIREMENTS.md#traceability). Deferred v2 requirements are not allocated to these phases.

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
