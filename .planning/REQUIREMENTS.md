# Requirements: Glueyneo

**Defined:** 2026-10-01
**Core Value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current milestone:** v0.1 — CPU/bus diagnostic SDK alpha

## v1 Requirements

In this OpenGSD template, v1 means the first scoped deliverable, **v0.1**, not a stable 1.0 API or a complete Neo Geo emulator. Acceptance is evidence from actual execution; preparation and research are design inputs. The current owned-core subset, limits, oracle ancestry and stop rules are defined in the [Phase 01 owned-core contract](../experiments/owned_cpu/CONTRACT.md). CPU-01–05 are complete for that bounded candidate scope under the fresh 10/10 [Phase 01 verification](phases/01-cpu-acceptance-experiment/01-VERIFICATION.md). This does not establish original-silicon saved-PC behavior, a complete ISA, game/BIOS support, board timing, or public SDK compatibility. The candidate receipt remains unqualified as an experiment artifact; the phase verifier records the separate current admission decision. Both Musashi adaptation attempts remain consumed and no further Musashi adaptation is authorized. Phase 02 is unblocked for planning.

### CPU Admission

- [x] **CPU-01**: At a recorded source revision, a maintainer can reproduce the owned C17 68000 build and per-file authored/copied/generated/compiled/distributed inventory with license notices and host-call disposition, proving that imported CPU/FPU/SoftFloat/generator code is absent from the owned runtime closure, as scoped by the [Phase 01 contract](../experiments/owned_cpu/CONTRACT.md).
- [x] **CPU-02**: At recorded source, build and input identities, a maintainer can run distinguishable CPU instances alternately and concurrently, including simultaneous cold initialization and failing creation/teardown paths, with results matching isolated baselines and no shared mutable machine state.
- [x] **CPU-03**: At recorded source and build identities, a maintainer can observe actual guest progress, stop/overshoot behavior and selected interrupt/exception interactions in a bounded execution experiment whose timing precision, bus sequence and unsupported behavior are documented.
- [x] **CPU-04**: At a recorded source revision, a maintainer can inspect a complete mutable-state and callback inventory and reproduce backend continuation at supported boundaries without serializing host pointers or jump buffers; this establishes no public board-snapshot format.
- [x] **CPU-05**: A maintainer can reproduce the owned-core decision against cumulative active-effort limits and churn review thresholds set before implementation, with commands and counterexamples. Do not use a fixed attempt count; tooling halts do not consume an attempt. Repair actionable in-scope findings from the remaining budget. If a hard effort limit or churn threshold prevents repair, preserve GAPS_FOUND and replan; a threshold alone does not reject the backend. This preserves the completed historical Musashi rejection as provenance and adds a separate pending owned-core decision obligation.

Historical Musashi CPU-05 decision evidence: [bounded rejection](../experiments/cpu/ACCEPTANCE.md#current-supersession-and-bounded-rejection--2026-10-02-plan-01-05), [sealed report](../experiments/cpu/acceptance-results.json), [independent reconciliation](../experiments/cpu/REVIEW.md), and [01-05 summary](phases/01-cpu-acceptance-experiment/01-05-SUMMARY.md). Normal-Python seal and read-only verify each return exit 1 with rejected / GAPS_FOUND and `blocking review finding`. The original pre-adaptation limits, two consumed attempts and 2,614 handwritten / 523 helper / 483 semantic lines, 20,005 total / 18,859 final-attempt seconds remain unchanged. All eight later source counterexamples and uncertainties are dispositioned without repair; earlier runtime results remain historical. Integration of the rejected Musashi backend is prohibited. This section completes only that historical decision; the owned-core requirements are now complete for the bounded Phase 01 scope documented in [01-VERIFICATION.md](phases/01-cpu-acceptance-experiment/01-VERIFICATION.md).

### Native API and Host Safety

- [x] **API-01**: A C integrator can create, reset and destroy an opaque instance under documented ownership/allocation/lifecycle rules without requiring filesystem, device, network, wall-clock or process-global machine services.
- [x] **API-02**: A C integrator can load the documented diagnostic region/manifest representation with explicit immutable-media lifetime, checked sizes/arithmetic and finite resource limits.
- [x] **API-03**: A C integrator can request bounded execution and obtain actual progress, stop reason and diagnostic observations through the ordinary native API under the qualified timing contract.
- [x] **API-04**: A C integrator receives actionable errors for invalid sizes, unsupported capabilities, lifecycle misuse and allocation/load failures, and can safely recover or destroy the instance without leaks, process exit or unintended live-state mutation.

### Executable Diagnostic

- [ ] **DIAG-01**: An external C consumer executes an original redistributable CPU/bus guest program through the ordinary create/load/run/results/destroy path and checks meaningful guest-computed observations.
- [x] **DIAG-02**: A maintainer can run a headless diagnostic runner through the ordinary native API and reproduce the diagnostic bootstrap, initialized-data/BSS and named CPU/bus assertions using documented oracle ancestry, with a deliberate wrong-behavior control that fails the checks.
- [ ] **DIAG-03**: A maintainer can repeat and split the supported execution workload and run distinguishable native diagnostic instances both interleaved and concurrently while matching isolated-baseline guest observations at equal execution boundaries, including concurrent native creation/load/teardown paths.

### Build and Package Consumption

- [ ] **BUILD-01**: An integrator can build the C17 static and shared runtime from an offline source tree with target-scoped CMake, CTest and pinned test-only Unity, without inherited developer flags or configure-time dependency downloads.
- [ ] **BUILD-02**: An out-of-tree C consumer can find and link an installed CMake package and execute the diagnostic against both static and shared library variants; a C++ consumer can compile and link the public headers without changing the runtime language.
- [ ] **BUILD-03**: An integrator can relocate the installed package and execute its diagnostic consumer after access to the original source/build/install locations is removed, and can rebuild a release source archive offline.
- [ ] **BUILD-04**: An integrator can identify the exact compiler, SDK, OS, architecture and build variants actually exercised for the release, with failed, skipped, unsupported and untested combinations stated explicitly.

### Evidence and Measurement

- [ ] **EVID-01**: A maintainer can audit every public fixture and dependency from a manifest recording rights/notices, source revision, generation/build recipe, output digest, firmware needs and test-oracle ancestry.
- [ ] **EVID-02**: A maintainer can run proportionate boundary and lifecycle tests, meaningful properties, bounded input/call-sequence fuzzing and supported sanitizer checks, with retained regressions for discovered failures.
- [ ] **EVID-03**: A maintainer receives machine-readable results with exact code/dependency/configuration/input identities, nonzero executed assertions and distinct pass/fail/skipped/unsupported/unknown outcomes.
- [ ] **EVID-04**: A maintainer can reproduce an initial diagnostic execution, memory/allocation, load and build-cost baseline on named host classes, retaining workload/output identity and uncertainty without presenting these measurements as gameplay performance or an enforced uncalibrated threshold.

### Documentation and Delivery

- [ ] **DOC-01**: A new integrator can follow a compiled getting-started example, ownership/lifetime/error guide and small failure reproduction procedure that match the shipped API and artifacts.
- [ ] **DOC-02**: An integrator can inspect the alpha's exact CPU/bus/bootstrap capability subset, timing limitations and unverified dimensions, including explicit absence of game, original-BIOS, video, audio and public snapshot/persistence compatibility claims.
- [ ] **DEL-01**: A maintainer gets a small always-started aggregate required CI check with conservative change classification, meaningful execution counts and recorded cold-build, critical-path and runner-minute evidence.
- [ ] **DEL-02**: Qualifying changes can merge through protected PRs only after current-revision required checks and independent review pass; relevant issues/PRs are triaged at repository setup and shipping, and actual bot/App event behavior is qualified for unattended operation.
- [ ] **DEL-03**: A maintainer can use pinned release-please automation with one C version source to stage a complete unsigned SDK draft bound to the tested release commit, including correct recovery from interrupted staging and retries that report no newly created release.
- [ ] **DEL-04**: Publication refuses wrong-commit or incomplete artifact sets, and a downloaded release's expected digests and diagnostic consumer are verified before claiming the release usable.
- [ ] **DEL-05**: Source, documentation, commit identity, logs and distributed archives pass a public-content check for required notices and excluded personal paths/private identity, credentials, commercial media and private corpus evidence before publication.

## v2 Requirements

Deferred from v0.1. The **next milestone** is an interactive diagnostic, not a promise of stable 2.0 or general game support. The roadmap keeps these as an outline until the first alpha provides evidence.

### Next Milestone — Interactive Diagnostic

- **PLAY-01**: A user runs an original diagnostic that exercises selected FIX/sprite/palette behavior and responds to logically sampled input under a documented firmware/bootstrap and board/timing profile.
- **PLAY-02**: A user hears a justified real chip-generated sound case after C Z80/YM2610 candidates pass license, isolation, timing and state gates; raw emulated output and host resampling/device behavior have separate evidence.
- **HOST-01**: A user loads, runs and unloads the thin per-core libretro adapter through an actual pinned RetroArch macOS build; the adapter uses the ordinary native API, with native/adapter observation equivalence and recorded architecture/core/frontend/media identities. RetroArch remains the interactive frontend until a shared host is available.
- **STATE-01**: A user restores a supported snapshot into a fresh instance and obtains the same continuation as uninterrupted execution; malformed or incompatible states are rejected atomically under explicit snapshot/replay compatibility identities.
- **SAVE-01**: A user reopens durable media in a fresh process and a guest demonstrably consumes prior writes; restoring old snapshots and receiving stale acknowledgments cannot silently discard new dirty data.

### Later — Compatibility and Integration

- **MEDIA-01**: A user imports one practical cartridge-media format outside the native core and receives useful set/revision/region and missing/wrong BIOS diagnostics under bounded malformed-input handling.
- **GAME-01**: A user can identify supported private commercial-game scenarios by title/revision/BIOS/region/mode, with original BIOS/board behavior separately qualified and no proprietary data published.
- **HW-01**: A maintainer expands banking/protection/raster/audio/peripheral families using minimal public regressions and explicit hardware evidence/uncertainty, preserving original slowdown.
- **INTEG-01**: A Playstead consumer can use a demonstrated host-process or direct native integration, with a second real consumer informing API stability decisions. “Host-process” means Playstead launching an existing frontend with GlueyNeo's libretro core, or the future shared host; it does not mean a GlueyNeo-owned GUI executable. The future shared-host process contract must pass the ROM path and explicit save-directory override, never write saves beside the ROM, flush battery saves periodically and on request with a stated maximum-loss window, stop cleanly on SIGTERM, and expose distinct exit codes for normal completion, guest errors, and host errors. These are target requirements, not current Playstead capabilities: `AdapterPin.json` and `SUPPORT-MATRIX.md` at inspected Playstead revision `1de3e954166eaf0a52fe0e4a950b46756139884d` (2026-10-02) specify `{saveDir}/{romBaseName}.sav`, periodic flush every 24 seconds, no on-demand flush, a 24-second loss window, and SIGTERM classified as killed rather than a graceful save-and-quit.
- **PERF-01**: A maintainer optimizes representative measured workloads with behavior-equivalence evidence and calibrated controlled-host budgets before adding architecture-specific acceleration.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Neo Geo CD, Pocket/Pocket Color and generic multi-system framework | Cartridge scope first; revisit only for an explicit funded use case |
| Any GUI or windowed host application owned by an individual core repository; core-owned host device/filesystem/network services | Core repositories provide libraries, headless diagnostic runners, and thin libretro adapters. Interactive GUI ownership belongs to RetroArch today and Playstead or a separate shared host later. |
| C++ runtime engine behind a C API | Does not satisfy the chosen all-C runtime requirement |
| Universal compatibility or hardware-perfect timing claims | Require specific physical/scenario evidence and a defined tested denominator |
| Commercial ROM/BIOS bundles, private capture uploads or public private-corpus identities | Redistribution/publication rights are not established |
| JIT, speculative SIMD, intra-instance parallelism | Defer until a representative profile justifies the complexity |
| Rewind, run-ahead, rollback netplay and silent overclocking | Need mature state/side-effect contracts or separately described behavioral deviations |
| Permanent ABI/snapshot/replay compatibility from the alpha | These identities are distinct and have not been exercised by sufficient consumers |
| Elixir/web/database/cloud infrastructure in the library | Unrelated to the C emulation product |

## User Stories

- As an integrator, I can build and install an offline SDK and run a meaningful original diagnostic from a separate C project.
- As a maintainer, I can reproduce a bounded backend decision and distinguish an unqualified dependency, incorrect guest result and invalid host call.
- As a release consumer, I can identify what the alpha supports, obtain the exact tested artifacts and reproduce the example without commercial media.

## Acceptance Criteria

Each v1 ID above is a checkable acceptance obligation. Phase plans attach concrete commands, fixtures, limits and observed outcomes. Candidate rejection is a valid recorded experiment result for CPU-05; it does **not** satisfy CPU-01–04 or authorize integrating a failed backend. If admission fails, Phase 2 waits for an accepted replacement or an explicit evidence-backed roadmap revision.

Original fixtures require documented rights and independent assertion reasoning. A zero-test run, context API alone, in-tree-only example, mocked frontend, generated hash alone or repeated green run after an unexplained failure cannot substitute for the promised seam. No requirement is complete merely because it appears in a plan.

## Definition of Done

v0.1 is complete when its mapped requirements have current-commit automated evidence, documentation and independent review, and a complete qualified unsigned SDK release is available. Missing repository/App authority keeps delivery requirements pending while artifact work continues. There is no standing human sign-off checklist. Physical evidence is required only for the hardware claims that depend on it; otherwise narrow the claim.

No performance values, platform minima, CPU choice or API/state stability are accepted by this document alone. Preserve failures and unknowns, justify baseline changes and update the next milestone from actual receipts.

## Traceability

Each v1 requirement has exactly one primary phase in v0.1. Later requirements remain outside the current milestone allocation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CPU-01 | Phase 1 | Complete |
| CPU-02 | Phase 1 | Complete |
| CPU-03 | Phase 1 | Complete |
| CPU-04 | Phase 1 | Complete |
| CPU-05 | Phase 1 | Complete |
| API-01 | Phase 2 | Complete |
| API-02 | Phase 2 | Complete |
| API-03 | Phase 2 | Complete |
| API-04 | Phase 2 | Complete |
| DIAG-01 | Phase 2 | Pending |
| DIAG-02 | Phase 2 | Complete |
| DIAG-03 | Phase 2 | Pending |
| BUILD-01 | Phase 2 | Pending |
| BUILD-02 | Phase 2 | Pending |
| BUILD-03 | Phase 3 | Pending |
| BUILD-04 | Phase 3 | Pending |
| EVID-01 | Phase 2 | Pending |
| EVID-02 | Phase 2 | Pending |
| EVID-03 | Phase 2 | Pending |
| EVID-04 | Phase 2 | Pending |
| DOC-01 | Phase 2 | Pending |
| DOC-02 | Phase 2 | Pending |
| DEL-01 | Phase 3 | Pending |
| DEL-02 | Phase 3 | Pending |
| DEL-03 | Phase 3 | Pending |
| DEL-04 | Phase 3 | Pending |
| DEL-05 | Phase 3 | Pending |

**Coverage:**

- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-10-01*
*Last updated: 2026-10-01 after automatic scope definition from the brief and research.*
