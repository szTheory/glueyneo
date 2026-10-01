# Glueyneo

## What This Is

Glueyneo is a planned portable Neo Geo MVS/AES cartridge emulation core written in C, for frontend integrators, players, maintainers and hardware researchers. It is intended to make trustworthy emulation easy to embed in Playstead and other hosts, with a thin libretro adapter providing the first interactive macOS release. Initialization establishes the plan; no emulation, platform support, compatibility or performance result has been implemented or verified yet.

## Core Value

Trustworthy Neo Geo emulation that other software can embed easily.

## Requirements

### Validated

(None yet — ship to validate.)

### Active

Current milestone: **v0.1 — CPU/bus diagnostic SDK alpha**. The first delivered capability is an offline installable C library that executes an original deterministic diagnostic through its ordinary native API. A stub API or green automation without meaningful execution does not satisfy it.

- [ ] Qualify a pinned, permissively licensed C 68000 backend with an explicit adaptation budget, complete mutable-state audit, independent instances and documented timing limits.
- [ ] Provide an opaque native instance API with explicit ownership, lifecycle, normalized diagnostic media, bounded execution, useful errors and no ambient host dependencies.
- [ ] Execute an original redistributable CPU/bus diagnostic with a justified oracle, deterministic outputs and isolation evidence through a real out-of-tree consumer.
- [ ] Ship a C17/CMake/CTest foundation with pinned Unity, static/shared builds, installed/relocated package consumption, compiled examples and a tested platform matrix.
- [ ] Establish proportionate boundary, property, fuzz and sanitizer checks; machine-readable evidence and measured diagnostic baselines; public-safe source and fixture provenance.
- [ ] Deliver a documented unsigned SDK alpha with current-revision CI/review gates and qualified, commit-bound release automation that stages complete artifacts before publication.

The next milestone adds a real interactive diagnostic: selected video/input/sound behavior, continuation and persistence, and a libretro core qualified in an actual pinned RetroArch macOS build. Commercial-game compatibility, additional board profiles and optimization follow evidence. REQUIREMENTS.md and ROADMAP.md own current scope and sequencing.

### Out of Scope

- Neo Geo CD, Pocket/Pocket Color and a generalized multi-system framework — outside the initial cartridge hardware focus.
- Full game-library GUI or a bespoke player application — host frameworks already provide these; a small SDL3 reference host is conditional on a demonstrated recurring integration need.
- JIT, speculative SIMD, intra-machine threading, rewind, run-ahead and rollback netplay — defer until correctness, complete state and representative profiles justify them.
- Commercial ROM/BIOS distribution and private corpus publication — no established rights; all such inputs and private evidence stay outside Git and public CI.
- Full game support, original BIOS boot, video, audio and durable save/state compatibility in v0.1 — the SDK alpha exposes its exact supported diagnostic subset and reports other capabilities as unsupported.
- Elixir, Phoenix, Ecto, databases, Hex packages, cloud services, networking or telemetry inside the library — unrelated to the selected C library product.
- Universal compatibility, hardware-perfect timing or unmeasured speed/tail-latency claims — require specific evidence and a tested denominator.

## Context

The preparation dossier was produced on 2026-10-01 and is preserved under [preparation/README.md](preparation/README.md). [BRIEF.md](preparation/BRIEF.md) records user intent; [DECISIONS.md](preparation/DECISIONS.md) supplies stable D-01–D-44 provenance and reopening conditions. The dossier is research, not implemented behavior. Current canonical documents supersede its proposed scope where explicitly linked; historical source receipts remain dated.

The intended machine has an original board model and audited reusable chips behind private adapters. Preparation identifies process-global state and serializer/timing coupling in candidate engines. A nominal context API or global lock does not prove reentrancy. Phase 1 must produce a bounded acceptance or rejection with counterexamples before committing to a backend or public ABI. Future Z80/YM2610 candidates are inventoried without making their full adaptation a prerequisite for a CPU-only alpha.

The host owns files, archives, media discovery, windowing, device audio, input mapping, host pacing and networking. The native core owns deterministic guest time and hardware behavior. It preserves hardware slowdown. AES/MVS, motherboard, region, BIOS, cartridge revision, peripheral and scenario claims are tracked separately. A diagnostic bootstrap is not proof of original BIOS compatibility.

Playstead's inspected integration currently launches processes; direct Glueyneo FFI is future work. Its historical GBA fixtures and private game are not Neo Geo conformance evidence or public fixtures. Reference emulators inform research, but correlated implementation ancestry cannot establish hardware truth.

Use original permissive diagnostics, audited public vectors and opt-in private local scenarios. Evidence records exact source/input/tool/configuration identities, oracle ancestry, limitations and pass/fail/skipped/unsupported/unknown status. Measured diagnostic costs do not become gameplay performance claims. Numeric preparation budgets remain hypotheses until calibrated.

OpenGSD identity was rechecked as **@opengsd/gsd-core 1.14.0** during initialization. Initialization used the brief's YOLO and automatic-advancement defaults. On 2026-10-01 the user clarified that each named GSD workflow step must pause so they can review the next action and change models. Current mode is interactive, with automatic advancement and the active auto chain disabled. Coarse phases, small reviewable vertical plans, independent subagent work, tracked planning, inherited session model, research, plan checking, verification, validation planning and source grounding remain configured. The current discussion and dependency-decision method is recorded in [METHODOLOGY.md](METHODOLOGY.md).

The local repository began with preparation only. No remote repository, hosted CI, branch protections, App authority, release or issue/PR inventory is established by initialization. Remote triage is presently not applicable; repeat it once the repository is configured and at milestone start/shipping. Account/credential setup and unavailable physical measurements are narrow external dependencies, not grounds to stop independent engineering.

## Constraints

- **Language:** C17 runtime and selected runtime dependencies in C. C++ may test public header linkage; a C++ engine behind a C ABI requires an explicit scope reconsideration.
- **Build:** Target-scoped CMake, CTest, Ninja as developer default and small pinned Unity. Offline source builds, static/shared artifacts and real installed consumers are first-class requirements. Platform/compiler minima are proposals until exercised.
- **Architecture:** Opaque per-instance state, single execution thread per instance, explicit buffers/ownership/errors/limits and deterministic integer/rational time. Independent instances may run concurrently. No hidden mutable machine globals, compulsory threads, filesystem/environment reads, clocks, secrets or network dependencies.
- **Correctness:** Defined integer behavior, explicit byte order and checked resources. Audit every imported mutable global, callback, lazy initialization, error path and state field. Keep timing precision and unsupported behavior explicit.
- **State:** Public ABI, library releases, snapshots, replay behavior and durable saves have distinct versions/contracts. Host pointers and host-only bookkeeping are not canonical guest state. Do not claim continuation before testing actual restoration and independent instances.
- **Licensing:** MIT original work. Audit imported/generated files and fixtures at immutable revisions, preserve notices and retain redistribution evidence.
- **Delivery:** Branches/PRs, independent review, current-revision required checks, protected green main and qualifying automatic merges/releases under standing user authorization. No bypasses or stale check approvals. Stage complete, traceable releases before publication.
- **Privacy/security:** No personal paths, private emails, machine identifiers, private account/repository URLs, credentials, commercial media or private captures in tracked content or release artifacts. Use established public/noreply author identity. Local automation may use ignored .env.local; CI secrets and nonsecret variables stay distinct. Other research repositories are read-only.
- **Cost/clarity:** Small concrete modules, readable control flow and proportionate tests. Measure CI critical path/runner-minutes and bound parallelism; preserve cold paths. Optimize demonstrated bottlenecks rather than construct speculative frameworks.
- **Planning:** Detail the current deliverable, outline the next milestone and keep the longer horizon revisable. Pause between named GSD steps for user direction and model selection. Apply METHODOLOGY.md to discussion and dependency decisions. Ship a truthful small alpha without allowing automation setup to displace emulation.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| D-01/D-02: Native embeddable MVS/AES cartridge core first | Focuses hardware and ownership while supporting several hosts | — Pending implementation |
| D-03/D-04: MIT original board/API plus audited C chip reuse | Reuse may shorten the correctness path without importing an entire emulator architecture | — Backend feasibility and file audit pending |
| D-06: Libretro/RetroArch macOS after the CPU diagnostic SDK | Provides an early interactive path; SDL3 remains conditional | — Pending next milestone |
| D-07–D-14: C17, CMake/CTest, pinned Unity, offline packages | Familiar portable C integration with explicit consumer evidence | — Toolchain matrix pending |
| D-15–D-22: Explicit contexts, deterministic time, normalized media and host-owned I/O | Supports reproducibility, independent instances and FFI integration | — Timing and lifecycle contract pending |
| D-23–D-25: Separate state/replay/persistence/ABI identities | Avoids false compatibility and lost durable updates | — Deferred beyond v0.1; backend state audit starts now |
| D-27–D-33: Source-qualified diagnostics and measurement before optimization | Prevents correlated oracle errors and unsupported performance claims | — No baseline measured |
| D-34–D-40: Small CI, reviewed PRs, release-please and complete draft publication | Makes frequent delivery repeatable while binding artifacts to tested commits | — Remote authority/event qualification pending |
| D-41–D-44: One current contract and rolling milestones | Preserves provenance without freezing speculative designs | — Adopted for planning; implementation unverified |

## Evolution

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
*Last updated: 2026-10-01 after project initialization.*
