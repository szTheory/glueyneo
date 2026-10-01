# Glueyneo rolling roadmap seed

Prepared 2026-10-01. Status: proposal for the OpenGSD roadmapper, not canonical ROADMAP.md. The future workflow should derive scoped requirements and phases from this material. Milestone labels here are conceptual, not allocated OpenGSD phase numbers or release guarantees.

## Sequence by demonstrated capability

| Horizon | Candidate milestone | User-visible outcome | Exit evidence |
|---|---|---|---|
| Current | Foundation and diagnostic SDK alpha | An integrator builds an offline C package, creates independent machines, runs an original tiny CPU/bus diagnostic, and gets deterministic results | Audited selected dependencies, real external consumer, deterministic assertion, sanitizer/error tests, initial measurements and a downloadable SDK alpha |
| Next | Interactive Neo Geo diagnostic alpha | A macOS user loads an original Neo Geo diagnostic through a thin libretro core and can exercise video/input and a documented sound test as implemented | Qualified frontend load, expected raw output and scripted input, sound/timing evidence, state continuation, clear supported-subset documentation |
| Following | First commercial-game compatibility slice | A user provides supported media/BIOS and plays a selected game configuration with saves and useful loading errors | Practical importer, private reproducible scenario, required hardware features, public diagnostic equivalents and truthful limitations |
| Medium | Compatibility by hardware family | Coverage expands through banking, protection, raster effects, sound and system modes | Versioned scenario inventory; no regressions in established cases; unknowns remain visible |
| Medium | Integration and performance maturity | Playstead/other hosts use stable contracts and measured efficient execution | At least two consumers, controlled comparisons, migration policy, release/package reliability |
| Long | Comprehensive cartridge coverage and optional advanced capabilities | Broad evidenced MVS/AES support, efficient rewind/run-ahead where useful, broader platforms | Each added configuration/feature meets its own evidence and maintenance requirements |

The first alpha is a diagnostic SDK, not a claim to run games. A tiny CPU program is not a whole-system boot test. Maintain that distinction in releases. If the first two milestones can be combined into a small reliable vertical slice after feasibility is established, combine them; do not delay an independently useful release merely to satisfy this provisional outline.

## First milestone candidate phases

### 1. Resolve dependency feasibility and establish the execution contract

Inventory candidate CPU/Z80/audio files at immutable revisions. Record licenses, notices, origins, build generators, mutable globals, callbacks, serialization state and timing capabilities. Prototype only enough to answer the architectural questions:

- Can two machines alternate execution without interference, then run independently on separate host threads, including simultaneous cold initialization and failing creation/load paths?
- Can each selected component round-trip all mutable state at its supported execution boundary and continue identically?
- Can bus access ordering, interrupt changes, sound commands and timer scheduling be represented accurately enough for the first supported profile?
- Can the selected code build as C without a hidden C++ runtime or host GUI dependency?
- Is the adaptation a small reviewable upstream patch set, or is it effectively a fork rewrite?

Use tiny owned fixtures and targeted differential tests. Do not implement every opcode or port an entire sound engine before deciding whether the candidate fits. A failed dependency experiment must produce a decision and counterexample, not quietly relax the instance/state contract. Evaluate alternatives in D-04 and D-15; pure-C remains the selected scope unless an explicit reason is recorded for revisiting it.

The phase plan must set a concrete effort cap and defer/replace decision for each candidate before starting. Inventory all proposed devices, but complete acceptance only for devices shipped in the first alpha; full audio contextization is not a prerequisite for a CPU-only diagnostic release. If a device is deferred, expose that absence as an unsupported capability and limit the alpha accordingly; do not use fake output that looks like implemented hardware. These five questions define the experiment's result, not an invitation to research indefinitely.

### 2. Ship a small real embeddable slice

Implement the public lifecycle and minimal media/error contracts; directed internal machine/bus interfaces; deterministic execution using the first chip; and an original small program that writes a checked result through the same API consumers use. Integrate only the board behavior needed for that explicitly documented diagnostic.

Add the C17/CMake/CTest foundation with a pinned small assertion dependency, source/install exports and an offline source archive. A real out-of-tree C consumer must create, load, run and destroy an instance. A C++ header consumer checks linkage portability without changing the runtime language. Include allocation-failure, invalid-size and lifecycle error cases. Publish the precise supported platform/build matrix.

Start fast CI and its aggregate required check, public fixture metadata, machine-readable result records, and source/license/privacy checks. Record a reproducible baseline for the actual diagnostic: execution cost, allocations, memory and build time. Mark all absent game/video/audio/accuracy dimensions not measured or unsupported.

### 3. Make the alpha distributable and maintainable

Provide a concise getting-started example, an API ownership/lifetime guide, supported-subset statement and failure reproduction instructions. Compile the shipped example in CI. Validate an installed/relocated package and release archive in an isolated consumer directory.

Set up PR protections, automated release PRs and complete artifact staging. The repository/account identity, bot permissions and token/event behavior must be checked at implementation time. Add an unsigned SDK artifact path that does not depend on macOS application notarization. Signing is only required for the app distribution experience that actually needs it.

Close with the initial metrics, actual tested configurations, unresolved chip/hardware risks, and an updated next-milestone outline. Neither a green workflow with no meaningful executed assertions nor an interface stub establishes this milestone's outcome.

## Next milestone candidate acceptance

Build a self-authored permissively licensed Neo Geo diagnostic with an explicit boot/firmware strategy. Exercise fixed-layer/sprite/palette behavior selected for the slice, input and a real chip-generated sound case, adding more accurate timing as its tests demand. Each expected result needs a justified oracle. Distinguish a test bootstrap from compatibility with original BIOS boot.

The libretro adapter must use the ordinary core API. Automate a contract host for its callbacks and run at least one real RetroArch macOS qualification against a pinned build. A test double cannot prove the downloaded core loads in that frontend. Record architecture, core/frontend identity, media/firmware identity, load/run/unload result and expected output.

Prove save/load continuation and persistent-media behavior with a fixture that reads and uses prior state. Include fresh process/instance reopening; a counter that always resets cannot be the continuation oracle. Keep state-format, durable-save and API versions separate. Do not ship rewind or run-ahead before side effects and state completeness are settled.

If frontend scripting cannot be automated sufficiently, keep the missing capability explicit and select a minimal SDL3 harness only if it removes a repeatable integration blocker. Do not turn a frontend problem into a general GUI project.

## Compatibility expansion strategy

Choose the first privately tested game by feature simplicity and availability of a reproducible scenario, not popularity alone. Then select titles that add distinct hardware coverage: CPU/interrupt stress, raster writes, sprite zoom and limits, ADPCM/FM paths, banks and cartridge protection, input modes, memory cards, region/BIOS differences and long-run behavior. Record revisions and configuration rather than title names alone.

Derive public minimal regressions from behavior where feasible without embedding proprietary code or assets. Hardware questions become focused diagnostic programs suitable for actual boards. Hardware validation, permissive fixture rights and commercial media access are different dependencies; do not collapse them into a single test-passed checkbox.

Performance work follows representative compatibility. Keep the scalar/correct reference path, profiles, behavior comparisons and complete environment metadata. Add SIMD/data-layout changes only when they materially help a relevant workload. Keep native game slowdown when it is hardware behavior; an overclock option would be a separately labeled feature.

## Day 0 day 1 and day 2

- **Day 0:** clear current status, a source archive that builds, dependency/license inventory, executable example and one reproducible diagnostic.
- **Day 1:** usable frontend adapter, actionable media errors, documented capabilities, reliable persistence and a concrete compatibility scenario.
- **Day 2:** safe upgrade/state policy, reproducible bug reports, performance history, maintained CI budgets, dependable releases and a small rolling roadmap.

Do not require all later-day features for the first release. Early publication must still be honest, reproducible and usable for its claimed capability.

## Milestone closeout protocol

1. Reconcile promised requirements with actual evidence and unknowns. Keep supported claims versioned.
2. Update public examples, integration docs and release notes in the same change as behavior.
3. Review relevant open issues/PRs, resolve or explicitly defer each applicable item, and avoid duplicate work.
4. Merge qualifying PRs and publish automatically under the user's standing authorization; keep unresolved release blockers visible.
5. Review conformance gaps, performance deltas, CI critical path/runner cost, flakes, adoption friction and documentation drift.
6. Choose the weakest high-impact dimension for the next improvement. Retire redundant checks and superseded advice with reasons.
7. Refresh the current, next and longer-horizon milestones; carry forward only actionable uncertainties.

Use [PROJECT-DNA.md](PROJECT-DNA.md) for the concrete historical lessons behind this protocol and [QUALITY-PERFORMANCE-AND-CI.md](QUALITY-PERFORMANCE-AND-CI.md) for measurement rules. Never call historical sibling-project receipts current Glueyneo evidence.
