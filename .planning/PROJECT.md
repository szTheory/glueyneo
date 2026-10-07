# Glueyneo

## What This Is

Glueyneo is a portable Neo Geo MVS/AES cartridge emulation core written in C, for frontend integrators, players, maintainers and hardware researchers. It is intended to make trustworthy emulation easy to embed in Playstead and other shared hosts, with a thin libretro adapter providing the first interactive path through RetroArch. Phase 01 accepted an owned C17 68000 backend for a bounded CPU/bus diagnostic subset, and Phase 02 produced the offline SDK implementation and consumer workflow. The public repository exists, but no SDK release has been published; broad platform support, game compatibility, original-silicon behavior, and performance remain unqualified.

## Core Value

Trustworthy Neo Geo emulation that other software can embed easily.

## Requirements

### Validated

- Phase 01 accepted the owned C17 CPU backend for the documented bounded diagnostic subset, including guest execution, independent instances, supported-boundary continuation, timing limits, and source/state inventory. See [01-VERIFICATION.md](phases/01-cpu-acceptance-experiment/01-VERIFICATION.md). This does not qualify original-silicon behavior beyond the recorded subset or establish a public SDK.

### Active

Current milestone: **v0.1 — CPU/bus diagnostic SDK alpha**. Its first delivery target is an offline installable C library that executes an original deterministic diagnostic through its ordinary native API. A stub API or green automation without meaningful execution does not satisfy it.

- [ ] Provide an opaque native instance API with explicit ownership, lifecycle, normalized diagnostic media, bounded execution, useful errors and no ambient host dependencies.
- [ ] Execute an original redistributable CPU/bus diagnostic with a justified oracle, deterministic outputs and isolation evidence through a real out-of-tree consumer and a headless diagnostic runner.
- [ ] Ship a C17/CMake/CTest foundation with pinned Unity, static/shared builds, installed/relocated package consumption, compiled examples and a tested platform matrix.
- [ ] Establish proportionate boundary, property, fuzz and sanitizer checks; machine-readable evidence and measured diagnostic baselines; public-safe source and fixture provenance.
- [ ] Deliver a documented unsigned SDK alpha with current-revision CI/review gates and qualified, commit-bound release automation that stages complete artifacts before publication.

The next milestone adds a real interactive diagnostic: selected video/input/sound behavior, continuation and persistence, and a thin per-core libretro adapter qualified in an actual pinned RetroArch macOS build. RetroArch is the interactive frontend until Playstead or a separate shared-host project supports these cores. Commercial-game compatibility, additional board profiles and optimization follow evidence. REQUIREMENTS.md and ROADMAP.md own current scope and sequencing.

### Out of Scope

- Neo Geo CD, Pocket/Pocket Color and a generalized multi-system framework — outside the initial cartridge hardware focus.
- Any GUI or windowed host application owned by an individual core repository — interactive use goes through RetroArch and, later, Playstead or a separate shared host.
- JIT, speculative SIMD, intra-machine threading, rewind, run-ahead and rollback netplay — defer until correctness, complete state and representative profiles justify them.
- Commercial ROM/BIOS distribution and private corpus publication — no established rights; all such inputs and private evidence stay outside Git and public CI.
- Full game support, original BIOS boot, video, audio and durable save/state compatibility in v0.1 — the SDK alpha exposes its exact supported diagnostic subset and reports other capabilities as unsupported.
- Elixir, Phoenix, Ecto, databases, Hex packages, cloud services, networking or telemetry inside the library — unrelated to the selected C library product.
- Universal compatibility, hardware-perfect timing or unmeasured speed/tail-latency claims — require specific evidence and a tested denominator.

## Context

The preparation dossier was produced on 2026-10-01 and is preserved under [preparation/README.md](preparation/README.md). [BRIEF.md](preparation/BRIEF.md) records user intent; [DECISIONS.md](preparation/DECISIONS.md) supplies the dated preparation decision register (`PREP-D-01`–`PREP-D-44`). The dossier is research, not implemented behavior. Current canonical documents supersede its proposed scope where explicitly linked; historical source receipts remain dated. The [Phase 01 owned-core contract](../experiments/owned_cpu/CONTRACT.md) defines the bounded candidate experiment; the separate [Phase 01 verification](phases/01-cpu-acceptance-experiment/01-VERIFICATION.md) records its current phase-level admission.

The intended machine has an original board model and audited reusable chips behind private adapters. Preparation identifies process-global state and serializer/timing coupling in candidate engines. A nominal context API or global lock does not prove reentrancy. Phase 01 now supplies bounded acceptance evidence and admits the owned backend for Phase 02 SDK integration; it does not establish a public CPU ABI, original-silicon truth, complete ISA support, or Neo Geo board behavior. Future Z80/YM2610 candidates are inventoried without making their full implementation a prerequisite for a CPU-only alpha.

Each core repository delivers a reusable library, a headless diagnostic runner, and a thin libretro adapter. The host owns files, archives, media discovery, windowing, device audio, input mapping, host pacing and networking. The native core owns deterministic guest time and hardware behavior. It preserves hardware slowdown. AES/MVS, motherboard, region, BIOS, cartridge revision, peripheral and scenario claims are tracked separately. A diagnostic bootstrap is not proof of original BIOS compatibility.

Playstead or a separate shared-host project owns any future multi-core GUI. GlueyNeo's native lifecycle, ownership, buffer, error, and state conventions are a reference for sibling cores; they do not require identical native ABIs or shared framework code. Libretro is the common frontend integration contract.

Playstead's inspected integration currently launches processes; direct Glueyneo FFI is future work. Its historical GBA fixtures and private game are not Neo Geo conformance evidence or public fixtures. Reference emulators inform research, but correlated implementation ancestry cannot establish hardware truth.

Use original permissive diagnostics, audited public vectors and opt-in private local scenarios. Evidence records exact source/input/tool/configuration identities, oracle ancestry, limitations and pass/fail/skipped/unsupported/unknown status. Behavioral sign-offs state whether tests ran during the audit and name their revision and denominator. Pair UBSan with expected-result boundary cases for implemented risky integer operations; do not add exhaustive operand sweeps without a measured need. Measured diagnostic costs do not become gameplay performance claims. Numeric preparation budgets remain hypotheses until calibrated.

OpenGSD identity was **@opengsd/gsd-core 1.14.0** during initialization; Phase 01 gap routing was checked on **1.15.0**, and Phase 03 execution uses installed **1.16.0**. Initialization used the brief's YOLO and automatic-advancement defaults. On 2026-10-01 the user clarified that each named GSD workflow step must pause so they can review the next action and change models. Current mode is interactive, with automatic advancement and the active auto chain disabled. Coarse phases, small reviewable vertical plans, independent subagent work, tracked planning, inherited session model, research, plan checking, verification, validation planning and source grounding remain configured. The current discussion and dependency-decision method is recorded in [METHODOLOGY.md](METHODOLOGY.md); the Phase 01 gap-routing behavior is recorded in [preparation evidence](preparation/2026-10-04-gsd-verification-loop.md).

The local repository began with preparation only. During Phase 03 execution on 2026-10-06, the owner authorized the public [szTheory/glueyneo repository](https://github.com/szTheory/glueyneo). Its selected publication history was sanitized and audited before pushing; private original local refs must never be published. Hosted CI, strict main protection and setup issue/PR triage now have observations in [03-HOSTED-QUALIFICATION.md](phases/03-distributable-release-qualification/03-HOSTED-QUALIFICATION.md). On 2026-10-07 the owner reported that a release App is installed and the repository Actions secret and App ID variable are configured; the requested permissions, effective token scope, expiry/revocation and event behavior are not directly verified. First-time fork execution, an independently approved protected merge and release publication also remain pending. Repeat triage at milestone start/shipping. External account authority and unavailable physical measurements are narrow dependencies, not grounds to stop independent engineering.

## Constraints

- **Language:** C17 runtime and selected runtime dependencies in C. C++ may test public header linkage; a C++ engine behind a C ABI requires an explicit scope reconsideration.
- **Build:** Target-scoped CMake, CTest, Ninja as developer default and small pinned Unity. Use strict C17 on owned targets, private target-scoped warnings, and presets for exercised configurations; do not impose developer flags on consumers or imported dependencies. CMake 3.20 remains the provisional floor; do not raise it to the research report's 3.24 proposal without platform/toolchain evidence. Preset schema version 2 supports configure/build/test presets at 3.20, so presets alone do not require that increase ([CMake 3.20 release notes](https://cmake.org/cmake/help/v3.20/release/3.20.html)).
- **Architecture:** Opaque per-instance state, single execution thread per instance, explicit buffers/ownership/errors/limits and deterministic integer/rational time. Independent instances may run concurrently. No hidden mutable machine globals, compulsory threads, filesystem/environment reads, clocks, secrets or network dependencies.
- **Correctness:** Defined integer behavior, explicit byte order and checked resources. Audit every imported mutable global, callback, lazy initialization, error path and state field. Keep timing precision and unsupported behavior explicit.
- **State:** Public ABI, library releases, snapshots, replay behavior and durable saves have distinct versions/contracts. Host pointers and host-only bookkeeping are not canonical guest state. Do not claim continuation before testing actual restoration and independent instances.
- **Licensing:** MIT original work. Audit imported/generated files and fixtures at immutable revisions, preserve notices and retain redistribution evidence.
- **Delivery:** Branches/PRs, independent review, current-revision required checks, protected green main and qualifying automatic merges/releases under standing user authorization. No bypasses or stale check approvals. Keep one local CI entrypoint in parity with hosted workflows when CI is introduced; stage complete, traceable releases before publication.
- **Privacy/security:** No personal paths, private emails, machine identifiers, private account/repository URLs, credentials, commercial media or private captures in tracked content or release artifacts. Use established public/noreply author identity. Local automation may use ignored .env.local; CI secrets and nonsecret variables stay distinct. Other research repositories are read-only.
- **Cost/clarity:** Small concrete modules, readable control flow and proportionate tests. Measure CI critical path/runner-minutes and bound parallelism; preserve cold paths. Optimize demonstrated bottlenecks rather than construct speculative frameworks.
- **Planning:** Detail the current deliverable, outline the next milestone and keep the longer horizon revisable. Pause between named GSD steps for user direction and model selection. Apply METHODOLOGY.md to discussion, dependency choices and shift-left verification. Ship a truthful small alpha without allowing automation setup to displace emulation.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| PROJECT-D-01/02: Native embeddable MVS/AES cartridge core first | Focuses hardware and ownership while supporting several hosts | — Pending implementation |
| PROJECT-D-03/04: MIT original board/API plus audited C chip reuse | Reuse may shorten the correctness path without importing an entire emulator architecture | — Phase 01 accepted the owned C17 CPU candidate for the bounded diagnostic subset; full hardware and platform qualification remain open |
| PROJECT-D-06: Per-core libretro adapter and RetroArch macOS qualification after the CPU diagnostic SDK | Provides an early interactive path; GUI ownership stays with RetroArch and the future shared host | — Pending next milestone |
| PROJECT-D-07–14: C17, CMake/CTest, pinned Unity, offline packages | Familiar portable C integration with explicit consumer evidence | — Toolchain matrix pending |
| PROJECT-D-15–22: Explicit contexts, deterministic time, normalized media and host-owned I/O | Supports reproducibility, independent instances and FFI integration | — Timing and lifecycle contract pending |
| PROJECT-D-23–25: Separate state/replay/persistence/ABI identities | Avoids false compatibility and lost durable updates | — Deferred beyond v0.1; backend state audit starts now |
| PROJECT-D-27–33: Source-qualified diagnostics and measurement before optimization | Prevents correlated oracle errors and unsupported performance claims | — No baseline measured |
| PROJECT-D-34–40: Small CI, reviewed PRs, release-please and complete draft publication | Makes frequent delivery repeatable while binding artifacts to tested commits | — Remote authority/event qualification pending |
| PROJECT-D-41–44: One current contract and rolling milestones | Preserves provenance without freezing speculative designs | — Adopted for planning; implementation unverified |
| PROJECT-D-45: Shift-left automated acceptance; human handoff only for irreducibly human or external evidence | Removes repeat UAT toil while keeping unknowns honest and CI proportional | — Default for planning and verification; apply per-phase |
| PROJECT-D-46: Refresh a failed phase verdict before planning more gap work | Prevents stale negative reports and status-router behavior from generating repeated plans; only fresh, actionable in-scope gaps justify another bounded repair | — Default; Phase 01 runtime-routing incident and workaround recorded in [preparation evidence](preparation/2026-10-04-gsd-verification-loop.md) |
| PROJECT-D-47: Keep candidate receipt disposition separate from phase admission | A frozen experiment receipt can remain unqualified while a fresh whole-phase verifier admits the bounded scope; status routing follows the verifier and canonical planning docs | — Phase 01 passed 10/10; candidate receipt remains unchanged and original-silicon saved PC remains unknown |

## Evolution

Current project decisions use `PROJECT-D-##`; dated preparation decisions use `PREP-D-##`. Phase 1 context and research use `P01-C-##` and `P01-R-##` respectively.

This document evolves at phase transitions and milestone boundaries.

After each phase transition:
1. Move invalidated requirements to Out of Scope with reasons.
2. Move verified shipped requirements to Validated with phase references.
3. Add newly discovered requirements to Active.
4. Record decisions, evidence and supersession links.
5. Check that What This Is describes the actual current product.

After each milestone:
1. Review every section and confirm the core value still guides the work.
2. Audit exclusions and refresh actual user, evidence and integration context.
3. Reconcile compatibility, baseline and release claims with exact receipts.
4. Update the current milestone, next outline and revisable longer horizon.

---
*Last updated: 2026-10-05 after Phase 01 acceptance and Phase 02 handoff.*
