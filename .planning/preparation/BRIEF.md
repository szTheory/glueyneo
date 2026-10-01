# Glueyneo project brief

Prepared 2026-10-01 for a fresh OpenGSD new-project session. This is an idea document and research handoff, not an initialized GSD project, implemented emulator, approved ABI, or measured performance baseline.

## Intent

Build Glueyneo: a fast, correct, portable, readable Neo Geo emulator written in C, designed primarily as an embeddable core. Make it straightforward to integrate into Playstead and other frontends. Provide an early way to try playable releases on macOS without waiting for Playstead. Publish a public open-source repository, useful documentation and frequent automated releases.

The core value is **trustworthy Neo Geo emulation that other software can embed easily**. Speed matters, but compatibility, hardware conformance, deterministic behavior and host safety must each have their own evidence. The ambition is eventual comprehensive game coverage; do not market universal compatibility or hardware-perfect timing before it is demonstrated.

Keep the implementation understandable as educational systems code. Prefer small explicit modules, plain control flow, documented hardware facts and a small dependency surface. Comments should explain timing, invariants and surprising hardware behavior. Avoid speculative framework construction, giant abstractions and clever undefined behavior. Apply the simplicity preference in [Ponytail](https://ponytail.dev/) as judgment about unnecessary code; line-count minimization never overrides validation, readable C or hardware fidelity.

## Users and outcomes

| User | Outcome |
|---|---|
| Frontend integrator | Build/install the library, provide media/input/time, receive video/audio, persist state, and diagnose errors without adopting a GUI or framework |
| Player using an existing frontend | Load supported media with useful diagnostics, obtain stable pacing and sound, preserve saves, and understand supported configurations |
| Maintainer or contributor | Reproduce a bug with a small case, understand the responsible hardware behavior, change it safely, and ship with rapid feedback |
| Hardware researcher or educator | Inspect assumptions, trace events, run diagnostics and compare against documented or measured behavior |
| Release maintainer | Merge qualifying PRs, produce traceable artifacts and recover from failures without repeated manual ceremonies |

## Scope defaults

Start with Neo Geo MVS/AES cartridge hardware. Plan AES/MVS mode, BIOS selection, timing differences, video, input, sound, banking/protection and persistent storage explicitly. Multi-slot behavior, uncommon peripherals and regional variants need their own coverage claims. Neo Geo CD, Pocket/Pocket Color, network services, a game-library GUI, JIT compilation, rollback netplay and generalized multi-system frameworks are later candidates, not first-milestone obligations.

The intended architecture is a native opaque-instance C API with deterministic emulated time and host-controlled execution. Host adapters own filesystem access, archives, windowing, device audio, input mapping, host pacing and networking. The core exposes explicit media, input, video, audio, reset, state and persistence contracts. No hidden process-global mutable machine state, ambient filesystem/environment reads, compulsory threads or network telemetry.

Use portable C17, target-scoped CMake, CTest and Ninja as initial defaults, subject to the concrete compiler/build matrix in the architecture report. Maintain an offline source build, a static/shared library path and a real installed-package consumer. Avoid imposing developer lint flags or dependencies on downstream consumers. The core and bundled runtime dependencies should remain C; a C++ engine behind a C ABI is a substantive scope alternative, not equivalent to this requirement.

Favor audited permissive CPU/audio reuse behind private adapters where it preserves readability and correctness. Early research identifies global-state and serializer coupling in candidate implementations. Before committing to any chip engine, prove license provenance, independent machine contexts, complete state handling, interrupt/timing integration and representative conformance. If a bounded adaptation is unsuitable, document the evidence and reassess; do not lock in a broken foundation to meet an arbitrary deadline.

Choose MIT for original Glueyneo work to favor straightforward reuse. Retain all third-party licenses, attribution and notices. Evaluate each imported file and asset at a pinned revision. Repository-level license labels alone are insufficient; no code or data should be copied from a differently licensed emulator merely because it is a useful behavioral reference. See [MIT](https://opensource.org/license/mit) and the [Apache 2.0 alternative](https://www.apache.org/licenses/LICENSE-2.0); this is a project licensing choice, not a legal determination about every future dependency.

Use a thin libretro adapter and a qualified RetroArch macOS build for the first playable releases. Keep the native API independent of libretro's single-instance model. Add a small SDL3 reference host if it has recurring diagnostic value or the adapter path blocks useful releases. Avoid building a full frontend. Playstead currently provides process-launch integration, not an established native Glueyneo FFI; preserve a clean route for both a host executable and future direct embedding.

## Quality commitments

Build the evidence system alongside the earliest executable slices:

- Deterministic chip/bus tests, boundary cases, original diagnostics, API integration tests, state continuation and multiple-instance isolation.
- Property and metamorphic tests for meaningful invariants; coverage-guided fuzzing for parsers/state/public call sequences; sanitizer builds with known scope.
- Separate hardware observations from reference-emulator-generated vectors. Shared implementation ancestry weakens differential independence.
- A fixture manifest with code/data licenses, source revision, build recipe, output digest, BIOS requirement, input script and oracle.
- A compatibility inventory identifying title/revision/BIOS/region/mode/scenario and attainment level, including unknown configurations.
- Recorded throughput, frame-time distributions, memory, allocations, load/state costs and frontend deadline/underrun measurements on named host classes.
- Fast PR checks, trusted longer campaigns and statistically defensible dedicated performance runs. Extreme tail aspirations must not become noisy hosted-runner gates.

All numeric targets in preparation are hypotheses. There is no existing Glueyneo baseline. Do not invent values, waive failures or regenerate expected outputs automatically to make CI green. An evidence-backed accuracy improvement may require an explained performance-budget adjustment.

Create public Neo Geo diagnostics with clear redistribution rights. Playstead offers useful testing patterns, but its inspected ROM fixtures target GBA and include a private game; they do not establish a ready public Neo Geo corpus. Commercial media and BIOS remain outside Git, public CI, release assets and public failure artifacts. Support an opt-in private local corpus and scrubbed summaries. Do not infer distribution rights from ownership or availability online.

## Delivery and working preferences

The user explicitly requests autonomous recommendations, subagent research/implementation where useful, PR-based work, green main, issue/PR triage, automatic merging when qualifying checks and review pass, and automated releases. Carry that authorization forward without repeated permission questions. Preserve platform permissions and branch protections. Report concrete credential/account or hardware blockers precisely; continue independent authorized work.

Automate reproducible verification at the seam that matters. Minimize human UAT. Physical measurement is occasionally necessary; narrow the claim if that evidence is unavailable. Do not substitute mocked internals or passing unit tests for a promised installed package, loadable core, persistence continuation or playable result.

Use release-please with a suitable C version-source strategy and an unattended token/event design. Validate the exact release commit, build usable artifacts, stage a complete draft, then publish. Favor a scoped GitHub App over a long-lived broad personal token. Never publish from an arbitrary PR head or silently overwrite released bytes.

Apply 12-factor ideas where useful: explicit configuration, no secrets in source, local automation credentials in ignored .env.local, CI credentials in GitHub Actions secrets, and nonsecret configuration in appropriate variables. The emulation library itself needs no dotenv loader, cloud account or service runtime.

The Elixir/Phoenix/Ecto/Plug/Hex and database-specific examples in the originating request were generic quality boilerplate. Translate them into C conventions, portable build/package behavior, a versioned API, useful examples, safe state formats and automated releases. Do not introduce an Elixir runtime, database, package publication to Hex, or web application.

Keep public material free of personal absolute paths, private email addresses, machine/account identifiers, secrets and commercial assets. Use an established public/noreply commit identity before publication. Other repositories inspected for this research remain untouched.

## OpenGSD initialization instructions

Use **OpenGSD @opengsd/gsd-core**. The inspected local runtime reported version 1.14.0; verify identity again if the environment has changed. Preserve this preparation directory. Read [README.md](README.md) and [DECISIONS.md](DECISIONS.md), then route research agents to the specific reports they need. Run targeted fresh checks of unresolved assumptions and moving dependencies; do not repeat all of the completed research without a reason.

The user has asked to follow sensible recommendations automatically. Use these preparation defaults for configuration unless the installed schema or new evidence requires an adjustment:

| Preference | Default |
|---|---|
| Mode | Autonomous/YOLO within the authorized scope |
| Phase granularity | Coarse, with small independently reviewable plans and demonstrable vertical slices |
| Parallelization | Yes for independent responsibilities; ownership and integration contracts explicit |
| Planning tracked | Yes, after public-content/privacy checks |
| Agent model profile | Inherit the active runtime/session model; do not silently change model providers |
| Research | Yes, focused on phase-specific uncertainty and new evidence |
| Plan checking and verification | Yes; real automated seams, not ceremony |
| Source grounding/drift guard | Yes when supported by installed OpenGSD |
| Validation planning | Yes where the installed workflow supports it |
| Auto advance | Yes through the authorized workflow; truthful stopping conditions |
| PR description | Acceptance/results, material risks/dependencies and release evidence; no standing human sign-off checklist |

These are recommended operational choices implementing the user's broad delegation, not a claim that the user individually selected each menu option. Use the installed configuration helper/schema, not an invented config format. The auto command may still surface configuration gates; use the already stated preferences under the user's authorization where the workflow permits.

Create canonical PROJECT, REQUIREMENTS, ROADMAP, STATE and config through the actual new-project workflow. Do not treat the preparation roadmap as already executed or validated. Plan only the first deliverable in detail, retain an outline for the next milestone and a revisable longer horizon. Initial candidate sequence: prove the reusable foundation → run an original Neo Geo diagnostic through the native API and libretro host → expand commercial-game behavior and protection coverage → optimize proven bottlenecks and integration ergonomics.

The first milestone should ship a small honest alpha capability with real consumer evidence. Bootstrap automation early, but do not let process setup displace the first actual emulation result. When prerequisites make a larger slice risky, ship a clearly labeled SDK/diagnostic alpha first and keep the first interactive macOS slice next.

## Reading map

- [DECISIONS.md](DECISIONS.md): coherent defaults, tradeoffs and reopening conditions.
- [C-CORE-ARCHITECTURE.md](C-CORE-ARCHITECTURE.md): language, build, runtime and integration contracts.
- [NEOGEO-HARDWARE-AND-ECOSYSTEM.md](NEOGEO-HARDWARE-AND-ECOSYSTEM.md): hardware evidence, emulator lessons, chip/fixture candidates and source provenance.
- [PROJECT-DNA.md](PROJECT-DNA.md): lessons from inspected active projects, with repository-relative evidence.
- [QUALITY-PERFORMANCE-AND-CI.md](QUALITY-PERFORMANCE-AND-CI.md): baselines, test strategy, performance statistics and release protocol.
- [ROADMAP-SEED.md](ROADMAP-SEED.md): provisional milestones and feasibility gates.
- [OPENGSD-HANDOFF.md](OPENGSD-HANDOFF.md): verified command behavior and preservation rules.
- [ADVERSARIAL-REVIEW.md](ADVERSARIAL-REVIEW.md): cross-report review and unresolved risks.
