# Phase 04: Public Playable Tracer - Context

**Gathered:** 2026-10-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 04 delivers an original, rights-audited public guest fixture that can be rebuilt from tracked source/assets and run through the ordinary native C API and an actual pinned macOS RetroArch build. Guest execution must produce the software frame and input response. The public fixture is a bounded tracer for the guest/API/board/video/frontend seam; it does not qualify production BIOS boot, commercial-game compatibility, broad video accuracy, or the later private Metal Slug X scenario.

Phase 04 also resolves the conditional admission gates for the pinned Z80 candidate and the approved `ymfm` YM2610 subset behind a private C interface. The existing C++14 exception for `ymfm` remains limited to that candidate and does not admit it without source/state, timing, instance, failure-containment, and consumer-linkage evidence. Audible game sound and a public sound fixture remain Phase 07 work.

The bounded frame operation still needs the Phase 04 `API-05` audio-buffer contract: explicit capacity, format, channel layout/rate, produced count, and relation to emulated time. This is an API contract, not a requirement that the Phase 04 tracer produce audible sound or close `SND-03`.

The active workstream requirements and roadmap own this scope. Earlier sibling v0.1 contexts described video/audio as out of scope for the diagnostic SDK; that historical boundary is superseded for this workstream. Reuse the accepted opaque C API, deterministic execution, ownership, build, and evidence patterns without treating the diagnostic fixture or CPU subset as existing video, input, game, or sound support. Phase 05 owns the selected private MVS boot path; Phase 06 owns the private active-scene movement, firing, graphics, and scrolling; Phase 07 owns audible output and scenario qualification.

Planning must select the exact public guest/profile, generation tools, pixel format/dimensions/pitch and buffer contract, fixed input trace and observation boundaries, execution limits, actual RetroArch identity, and clean-tree commands before claiming success. Preserve the separate public-fixture and private-game evidence claims.
</domain>

<decisions>
## Implementation Decisions

### Fixture boot path and claim boundary
- **P04-C-01:** Load original public fixture content through the ordinary native API and normal Libretro content-loading path, with a documented BIOS-free fixture entry. Do not require a production BIOS or use a no-content shortcut for this proof. Any minimal first-party setup code needed to launch the fixture remains source-built fixture code; it must not be described as an SNK BIOS or as BIOS compatibility. The public fixture's result must not be used to claim normal BIOS boot or broader MVS/game compatibility.
- Rationale: This keeps public CI reproducible and exercises the actual content path while avoiding proprietary firmware. Libretro's core guide describes `retro_load_game()` as the content-loading entry and `retro_run()` as the per-frame execution path; its BIOS guidance says system files are not distributed with RetroArch. MAME's ROM-set documentation describes a separate Neo Geo BIOS image, but that is MAME's packaging/model documentation, not independent hardware truth.
- Validation: Load the same generated fixture through the ordinary native and actual RetroArch paths. Record the explicit fixture entry semantics and include a negative control for a wrong launch/input path. Do not use a host-rendered overlay or a test-only bypass to produce the expected frame.

### Visible scene and controls
- **P04-C-02:** Keep the public tracer visually small and immediately legible: a fixed, high-contrast backdrop and one guest-controlled marker. A documented RetroPad direction moves the marker by one logical step per sampled frame. Use a short fixed native input sequence, assert guest state and meaningful output pixels at defined boundaries, and include a wrong-direction or no-input control that fails the expected result. Keep color from being the only distinguishing cue.
- Rationale: One visible response is enough to prove guest input, video output, and frontend mapping. A multi-object or multi-action scene adds renderer, asset, and oracle surface before those paths exist, and risks moving Phase 04 toward Phase 06 gameplay. The host must not draw, move, or repair the marker. The fixture defines its own bounded visual behavior and does not establish general Neo Geo video accuracy.
- Validation: Observe the same fixture and input identity through the native consumer and pinned RetroArch software-video path. Assert guest-owned state and selected semantic pixels rather than relying on a frame hash alone. Document the control mapping. Keep scrolling, multiple layers, and game-specific movement/fire behavior in their allocated later phases.

### Fixture source and rebuild experience
- **P04-C-03:** Tracked guest source and assets are canonical. Generate the fixture into the build tree through a named CMake target, and have native and RetroArch consumers use the same generated artifact. Provide one documented maintainer verification command that builds/regenerates it and runs the applicable consumer checks. Do not add an external fixture/runtime dependency by default. If the required guest or graphics format makes a toolchain necessary, compare a small local generator/copied subset with a pinned build-only dependency and record its full provenance and notices. If a generated binary is checked in for a demonstrated consumer need, require a regeneration identity check so it cannot silently drift from source.
- Rationale: This keeps the default library build lean while making the guest reproducible and preventing separate native/frontend fixtures from diverging. CMake 3.20 documents generated outputs with explicit dependencies; the project's current CMake floor is retained. A full Neo Geo homebrew toolchain is an option only if the actual fixture needs its assembler/graphics tooling; its wider tool surface must justify its maintenance and supply-chain cost.
- Validation: From a clean tree, regenerate deterministically and record source/assets, generator/tool identity, rights/notices, oracle ancestry, and output identity. Run native and actual RetroArch checks with the same artifact. Check build rules for missing dependencies or multiple producers of a generated output.

### the agent's Discretion
The user accepted the recommendations as a set. Downstream research and planning should choose the exact fixture source encoding/generator, board/video implementation, pixel values and dimensions, native frame API details, test commands, and pinned frontend/tool identities. Keep those implementation decisions within the three behavior and claim boundaries above; justify any added dependency against a small local or copied implementation.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Active scope and project contracts
- `.planning/workstreams/first-playable-game/REQUIREMENTS.md` — approved requirements, phase allocations, boundaries, acceptance criteria, and Definition of Done.
- `.planning/workstreams/first-playable-game/ROADMAP.md` — Phase 04 goal, success criteria, dependencies, and sequencing into the private game phases.
- `.planning/workstreams/first-playable-game/RESEARCH.md` — accepted milestone research, candidate admission gates, and boundaries between public and private evidence; research is not implementation evidence.
- `.planning/PROJECT.md` — project architecture, C17 default, host boundary, public-content rules, and `PROJECT-D-48` conditional `ymfm` exception.
- `.planning/METHODOLOGY.md` — breadth/depth, adversarial review, source grounding, dependency comparison, and shift-left verification method.
- `AGENTS.md` — repository working rules for engineering, evidence, privacy, and GSD workflow pauses.
- `.planning/preparation/README.md` — dated preparation evidence index and supersession policy.
- `.planning/preparation/DECISIONS.md` — `PREP-D-##` decision provenance and reopening conditions; proposals there do not assert current implementation.

### Prior native SDK decisions and current implementation
- `.planning/workstreams/cpu-bus-diagnostic-sdk-alpha/phases/02-executable-diagnostic-sdk/02-CONTEXT.md` — prior opaque API, copy-on-load ownership, deterministic execution, and consumer-evidence decisions. Its video/audio exclusions are superseded by this active workstream.
- `include/glueyneo/glueyneo.h` — current public diagnostic API; it has no frame/video/input/audio operation yet.
- `src/instance.c` — current per-instance CPU and ROM/RAM implementation; it is not a video, MVS board, or game implementation.
- `tests/sdk/guest_fixture.c` and `tests/sdk/guest_fixture.h` — original CPU diagnostic fixture generation pattern, not the new Neo Geo video fixture.
- `tests/sdk/test_sdk.c` and `tests/sdk/ORACLE.md` — named observations, exact negative-control pattern, and current oracle ancestry.
- `CMakeLists.txt` and `tools/verify_sdk.py` — current target-based build and local verification entrypoint to assess for reuse.
- `docs/rights-inventory.md`, `docs/public-content.md`, and `docs/evidence-schema.md` — rights, public/private-content boundaries, and evidence fields.

### External API and build references
- `https://docs.libretro.com/development/cores/developing-cores/` — content loading, per-frame `retro_run()` behavior, input polling, software video callbacks, and frontend pacing; official documentation reviewed 2026-10-07. Recheck/pin the exact API header revision during planning.
- `https://docs.libretro.com/guides/bios/` — RetroArch/Libretro do not distribute copyrighted system files; BIOS use is a separate content dependency; official documentation reviewed 2026-10-07.
- `https://cmake.org/cmake/help/v3.20/command/add_custom_command.html` — generated outputs and dependency behavior at the project's CMake floor.
- `https://github.com/dciabrin/ngdevkit` — upstream Neo Geo homebrew toolchain reference considered as a build-only alternative; its broader toolchain is not selected. Pin a revision and audit licenses if future research finds it necessary.
- `https://github.com/mamedev/mame/blob/master/docs/source/usingmame/aboutromsets.rst` — MAME's documented separate BIOS-ROM-set model, useful as emulator packaging context only, not hardware truth; moving reference reviewed 2026-10-07 and must be pinned if used in implementation research.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/sdk/guest_fixture.c` builds a deterministic original CPU guest from tracked C source; it shows an existing small fixture pattern but contains no video or controller behavior.
- `tests/sdk/test_sdk.c` has named guest observations and explicit wrong-behavior controls that can inform how the new public fixture proves input/output behavior.
- `tests/sdk/ORACLE.md` records expected results and oracle ancestry; add a separate fixture oracle for new guest/video behavior rather than extending diagnostic claims.
- `tools/verify_sdk.py` and the root CMake/CTest setup are the current local verification path and can be assessed for one-command fixture generation/consumer checks.

### Established Patterns
- The native core uses C17, opaque per-instance state, explicit ownership and widths, finite deterministic guest-cycle execution, and no ambient host services.
- Tests tie outcomes to inputs and oracle ancestry and use controlled mutations to prove an assertion can fail. Existing checks are diagnostic CPU evidence only.
- The current public API exposes `GN_PROFILE_DIAGNOSTIC`, ROM/RAM regions, cycle-bounded CPU execution, and named CPU observations. It does not yet expose frame advance, video, input, audio, MVS media, or the libretro API.
- Existing code inventory contains no board renderer, input adapter, Z80/YM2610 integration, or libretro target. Phase 04 introduces those seams; it should preserve public/private content separation and avoid claiming a capability from a stub.

### Integration Points
- Extend the ordinary native instance API with the bounded frame/input/video contract from `API-05`; keep guest time and output production inside the core and host pacing/controller mapping in the adapter.
- Add the thin libretro adapter as a consumer of the same native instance API and same generated public fixture used by the C consumer.
- Connect fixture generation and native checks to the existing local verification entrypoint; qualify the actual pinned macOS RetroArch consumer separately with exact frontend/build identities.
- Run Z80 and `ymfm` admission as separate evidence gates; do not couple public fixture licensing or results to private ROM/BIOS assets.

</code_context>

<specifics>
## Specific Ideas

- The user's recurring preference is that a small audited local implementation or copied subset may be preferable to another dependency. Any fixture generator/toolchain must justify its full dependency and license surface.
- The user asked for recommendations to consider product, engineering, frontend, test, build, security/supply-chain, and maintainability lenses, to use primary sources where helpful, and to synthesize recommendations with adversarial tradeoffs. The user accepted all three recommendations on 2026-10-07.
- The boot-path recommendation is an explicit boundary, not a claim that BIOS behavior is unimportant: BIOS compatibility remains part of the separate selected private MVS scenario.
</specifics>

<deferred>
## Deferred Ideas

None were proposed during discussion. Broader BIOS/game boot remains in Phase 05, active Metal Slug X graphics/scrolling in Phase 06, and public sound fixture plus private audible scenario in Phase 07.
</deferred>

---

*Phase: 04-public-playable-tracer*
*Context gathered: 2026-10-07*
