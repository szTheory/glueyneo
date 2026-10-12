# Phase 04: Public Playable Tracer - Research

**Researched:** 2026-10-07  
**Domain:** C17 emulation API, Neo Geo fixture/video path, Libretro/RetroArch integration, chip dependency admission  
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

Source: `[VERIFIED: .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-CONTEXT.md:20-41,109-111]`.

### Locked Decisions

<!-- DATA_7KQ4M2PX_START -->
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
<!-- DATA_7KQ4M2PX_END -->

### the agent's Discretion

<!-- DATA_9R3B6W1T_START -->
The user accepted the recommendations as a set. Downstream research and planning should choose the exact fixture source encoding/generator, board/video implementation, pixel values and dimensions, native frame API details, test commands, and pinned frontend/tool identities. Keep those implementation decisions within the three behavior and claim boundaries above; justify any added dependency against a small local or copied implementation.
<!-- DATA_9R3B6W1T_END -->

### Deferred Ideas (OUT OF SCOPE)

<!-- DATA_5M8C1J7V_START -->
None were proposed during discussion. Broader BIOS/game boot remains in Phase 05, active Metal Slug X graphics/scrolling in Phase 06, and public sound fixture plus private audible scenario in Phase 07.
<!-- DATA_5M8C1J7V_END -->
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRAC-01 | A maintainer can rebuild a tiny original Neo Geo fixture from tracked source and assets, with documented generation tools, redistribution rights, notices, and assertion-oracle ancestry, without commercial game or production BIOS inputs. `[VERIFIED: REQUIREMENTS.md:21]` | Reuse the existing build-tree generator pattern; keep the ROM and graphics source original; add a fixture-specific rights/oracle manifest and reproducibility check. |
| TRAC-02 | A C consumer can execute that fixture through the ordinary native API and observe a software frame produced by guest-driven board/video behavior, with checked pixel format, dimensions, pitch, and buffer bounds. `[VERIFIED: REQUIREMENTS.md:22]` | Add one bounded frame operation and a minimal guest-programmed sprite path; test checked output buffers and semantic pixels through a real C consumer. |
| TRAC-03 | A C consumer can supply a fixed logical input sequence and observe the fixture change its guest state and visible output according to independently justified expected results; a wrong-input control fails the assertions. `[VERIFIED: REQUIREMENTS.md:23]` | Sample logical controls at frame boundaries; assert guest-owned position and independently calculated marker pixels; prove wrong-direction/no-input controls fail. |
| HOST-02 | A user can load, run, and unload the fixture through a thin libretro adapter in an actual pinned macOS RetroArch build, using the ordinary native API, software video, documented controller mapping, and frontend-owned pacing. `[VERIFIED: REQUIREMENTS.md:27]` | Use normal content loading, one native frame call per `retro_run`, Libretro software video/input callbacks, and an actual pinned RetroArch load/control/unload smoke. |
| API-05 | A C integrator can advance the selected machine through a documented bounded frame operation with explicit input sampling, output-buffer ownership/lifetimes, video/audio capacities, audio sample format/channel layout/rate/produced count and relationship to emulated time, progress/stop information, and actionable errors, without native filesystem, device, network, or wall-clock services. `[VERIFIED: REQUIREMENTS.md:28]` | Specify the input boundary, machine-time budget, caller-owned buffers, capacity preflight, audio metadata even while silent, progress/error result, and host-independent implementation. |
| SND-01 | A maintainer can reproduce admission of the pinned C Z80 candidate for the selected workload using license/source and mutable-state inventories plus cycle, interrupt, bus-effect, supported-boundary continuation, and independent-instance evidence. `[VERIFIED: REQUIREMENTS.md:45]` | Gate the pinned cycle-stepped candidate on a direct state/callback inventory and Glueyneo-owned cycle, bus, interrupt, continuation, and instance tests. |
| SND-02 | A maintainer can reproduce admission of a pinned ymfm YM2610 subset behind a private C interface under PROJECT-D-48, with license/source and mutable-state/callback inventories, deterministic clock/sample and instance-isolation evidence, contained C++ failure behavior, and exercised static/shared C-consumer linkage. The C++ exception alone is not admission. `[VERIFIED: REQUIREMENTS.md:46]` | Isolate the exact source closure behind private C calls; inventory every object/global/callback; verify clock/sample/isolation/failure behavior and real static/shared C links before calling it admitted. |
| QUAL-03 | An integrator can follow the documented build/install/load procedure for the native library and libretro adapter from a clean source tree on the selected macOS configuration, with exact dependency/compiler/SDK/OS/architecture/frontend identities and untested configurations stated explicitly. `[VERIFIED: REQUIREMENTS.md:54]` | Reuse current CMake install/preset structure and record the actual macOS compiler, SDK, OS, architecture, candidate source commits, frontend release, and artifact identity after the runnable frontend gate passes. |
</phase_requirements>

## Summary

[VERIFIED: `.planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-CONTEXT.md:9-17`] Phase 04 is a public first-party fixture and native/Libretro seam proof, plus conditional Z80 and ymfm admissions. It does not cover production BIOS boot, the private game scenario, broad video accuracy, or audible output. The user has already fixed the fixture behavior and evidence boundary; the planning decisions still open are the fixture encoding/profile, minimal board/video subset, exact frame and buffer contract, test trace, execution bounds, and actual frontend pin.

[VERIFIED: `include/glueyneo/glueyneo.h:30-67`; `CMakeLists.txt:98-115`] The current public API is an opaque C interface for diagnostic media and cycle-bounded execution. It has no frame, video, input, audio, or Libretro operation. Phase 04 therefore adds a real native seam; it must not infer these capabilities from the existing diagnostic fixture or CPU-only evidence.

[CITED: https://docs.libretro.com/development/cores/developing-cores/; reviewed 2026-10-07] Use `retro_load_game()` with the fixture bytes (set `need_fullpath` false) and the ordinary content path. The Libretro guide says the path may be null in this mode, `retro_run()` advances one frame, input polling occurs at least once, video is delivered once per run, and the frontend owns pacing from fixed reported rates. The guide also says Libretro does not promise thread safety; the thin adapter should own one frontend instance and must not claim frontend reentrancy.

[CITED: https://wiki.neogeodev.org/index.php/Display_timing; https://wiki.neogeodev.org/index.php/Sprites; https://wiki.neogeodev.org/index.php/VRAM; reviewed 2026-10-07] A small Neo Geo sprite tracer can use the documented 320-by-224 active display, one C-ROM sprite tile, and the SCB tile/position records reached through the VRAM registers. These are community-maintained technical references, not an SNK vendor manual or silicon measurement. The fixture can test this bounded documented path, but any hardware-accuracy claim remains open without a primary hardware source or physical observation.

[VERIFIED: `tests/sdk/guest_fixture.c:6-31`; `CMakeLists.txt:176-186`; `tests/sdk/ORACLE.md:3-16`] The existing C-generated diagnostic fixture is original, build-generated, and already demonstrates a useful source recipe and independent CPU-manual oracle. Reuse its fixture-generation and oracle-documentation shape, but add a separate video/input fixture and oracle; the existing fixture contains neither video nor controller behavior.

**Primary recommendation:** Build one small source-generated cartridge-like fixture that starts through a documented BIOS-free fixture profile, runs guest code through the ordinary native API, samples one RetroPad direction per frame, and changes one sprite's guest-programmed position. Render only the documented sprite path into a checked software buffer, send that same output through a thin Libretro adapter, and keep chip admission as separately reviewable gates. Use a local C fixture builder unless implementing the tiny source format proves materially more complex than the complete audited toolchain cost.

### Methodology and adversarial synthesis

[VERIFIED: `.planning/METHODOLOGY.md:20-42`] The relevant role lenses are hardware/oracle, C ABI and host safety, deterministic timing/state, frontend integration, validation reliability, build/release, licensing/supply chain, and maintenance/product usability. The strongest competing approaches are a miniature source-built fixture versus a full Neo Geo toolchain, an actual guest-programmed sprite versus a host-painted marker, and an existing chip candidate versus an owned implementation.

[CITED: https://github.com/dciabrin/ngdevkit; reviewed 2026-10-07] The strongest case for ngdevkit is that its cross-compiler, hardware headers, graphics tools, and examples could produce a conventional homebrew ROM and reduce manual encoding risk. Its full cross-toolchain and split repositories add build, licensing, update, and platform surface for a fixture that needs one guest and one marker. Prefer the small local generator first; reopen ngdevkit only if the required real ROM encoding or asset conversion cannot be kept clear and auditable locally. This is a dependency-cost judgment, not an assertion that ngdevkit is unsuitable for production homebrew.

[CITED: https://docs.libretro.com/development/cores/developing-cores/; https://wiki.neogeodev.org/index.php/Sprites; reviewed 2026-10-07] A host-drawn marker would be easier and would make an attractive screenshot, but it would bypass the guest/API/board/video seam fixed by P04-C-02. Keep pixels derived from guest-written sprite state and fixture graphics. A miniature renderer does not qualify general video behavior; test controls must establish the bounded rule and explicitly leave hardware raster fidelity unknown.

[CITED: https://github.com/mamedev/mame/blob/master/src/mame/snk/neogeo_v.cpp; `.planning/workstreams/first-playable-game/RESEARCH.md:22-29,61-66`] MAME is useful as a differential implementation for fixture and device behavior, but it is not an independent physical oracle. Derive CPU instructions from primary processor documentation, record community board-document ancestry separately, and never call agreement with MAME a hardware pass. The candidate CPU/audio libraries shorten implementation time only if the required state, callback, timing, licensing, and instance evidence closes; a C wrapper does not waive the C++ runtime and failure audit for ymfm.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Frame scheduling, guest input port, fixture board state, software video and output limits | API / Backend | — | Deterministic time and guest state stay in the native instance. `[VERIFIED: AGENTS.md:8,12]` |
| Host input mapping, content bytes, callback wiring, frontend load/unload and pacing | Frontend host adapter | API / Backend | Libretro maps devices and forwards native results; the adapter does not own machine behavior or pacing. `[CITED: https://docs.libretro.com/development/cores/developing-cores/]` |
| Fixture source, sprite bytes and generated content identity | Build / Static | API / Backend | Generation is build-tree scoped; runtime content still enters through the normal API. `[VERIFIED: 04-CONTEXT.md:33-36]` |
| Z80 and ymfm candidate admission | API / Backend | Build / Static | State/timing are machine behavior; source/license/linkage evidence is build evidence. `[VERIFIED: REQUIREMENTS.md:45-46]` |
| Public fixture rights, oracle and qualified-configuration record | Build / Release | API / Backend | Bind source, generated bytes and tests to the public claim without private media. `[VERIFIED: AGENTS.md:17-20,37-40]` |

## Standard Stack

### Core

| Library / tool | Version | Purpose | Why standard |
|---|---|---|---|
| Owned C core | C17 | Native frame API, CPU/board state and software renderer | `[VERIFIED: CMakeLists.txt:101-108]` The existing runtime target has `<!-- DATA_R4C8N6XV_START -->` `C_STANDARD 17`, `C_STANDARD_REQUIRED YES`, `C_EXTENSIONS NO` `<!-- DATA_R4C8N6XV_END -->`. |
| CMake | Minimum 3.20 | Native build, generated fixture target, install/export | `[VERIFIED: CMakeLists.txt:1; CMakePresets.json:1-5]` The project declares `<!-- DATA_Q3W7B5JH_START -->` `cmake_minimum_required(VERSION 3.20)` `<!-- DATA_Q3W7B5JH_END -->` and already uses target-based presets. |
| CTest + vendored Unity | Existing project pins Unity | Native frame, fixture, consumer and admission tests | `[VERIFIED: CMakeLists.txt:227-267; tests/sdk/ORACLE.md:88-91]` The exact source pin is `<!-- DATA_J5P2M8KF_START -->` `b6763fbd9cedfacaa89e2ad9fd00d615a234e355` `<!-- DATA_J5P2M8KF_END -->`; Unity is linked only to tests, not the runtime. |
| Libretro C API | Pin one exact `libretro.h` revision during planning | Thin macOS frontend adapter | `[CITED: https://github.com/libretro/libretro-common/blob/master/include/libretro.h; https://docs.libretro.com/development/cores/developing-cores/]` Header declares pixel-format negotiation and callback ABI; pin the exact header and retain its notice. The workstream's current research explicitly says to recheck and pin it. |
| RetroArch | Candidate release `v1.22.2`; exact macOS artifact digest still required | Actual frontend consumer for load/run/control/unload | `[CITED: https://github.com/libretro/RetroArch/releases/tag/v1.22.2]` Official release exists. A local app bundle reports this version, but its executable's `--version` probe aborted (exit `-6`); this local probe does not establish a working frontend. |

### Conditional chip candidates

| Candidate | Version / source identity | Purpose | Admission rule |
|---|---|---|---|
| `floooh/chips` Z80 | `[VERIFIED: .planning/workstreams/first-playable-game/RESEARCH.md:65]` <!-- DATA_K7V2N5QD_START -->“[floooh/chips at examined revision](https://github.com/floooh/chips/tree/9e88298ce56319953ac7a43213a1120359f7a3a6)”<!-- DATA_K7V2N5QD_END --> | Candidate C Z80 for later sound-CPU work | Do not admit without source/license and mutable-state inventory, cycles, interrupts, bus effects, supported-boundary continuation, and distinguishable independent-instance tests. |
| `ymfm` YM2610 subset | `[VERIFIED: .planning/workstreams/first-playable-game/RESEARCH.md:66]` <!-- DATA_B1M6X4RA_START -->“[ymfm at examined revision](https://github.com/aaronsgiles/ymfm/tree/81aec25ccbb98f4873a255f7551ac4dadac59b4a)”<!-- DATA_B1M6X4RA_END --> | Candidate YM2610 behind private C interface | Do not admit without source/license/callback/state inventory, deterministic clock/sample output, isolation, contained C++ failure behavior, and real static/shared C-consumer linkage. |

[CITED: https://github.com/floooh/chips/blob/master/chips/z80.h; https://github.com/floooh/chips-test/blob/master/tests/z80-zex.c; reviewed 2026-10-07] The upstream Z80 header is a cycle-stepped C implementation: the caller clocks it, services returned memory/I/O pins, and supplies interrupt pins. The separate ZEX harness is useful candidate evidence, not a substitute for Glueyneo's bus, timing, continuation or instance tests. Preserve the zlib/libpng notice and separately audit any test ROM bytes before copying them.

[CITED: https://github.com/aaronsgiles/ymfm/tree/81aec25ccbb98f4873a255f7551ac4dadac59b4a; https://github.com/aaronsgiles/ymfm/blob/81aec25ccbb98f4873a255f7551ac4dadac59b4a/src/ymfm_opn.h; reviewed 2026-10-07] Upstream identifies YM2610 support, C++14, BSD-3-Clause licensing, and consumer-driven chip clocks. `generate()` produces chip-native output data/rate, so rate conversion belongs to a separate consumer layer. The pinned OPN source stores mutable register/LFO/waveform data inside chip objects; this is evidence to inspect object state, not proof that all dependencies/callbacks are instance-safe. Preserve the full notice and record the exact selected source closure.

### Alternatives considered

| Instead of | Could use | Tradeoff |
|---|---|---|
| Local C fixture builder and byte recipe | Pinned ngdevkit toolchain | Full toolchain strengthens conventional ROM production and asset conversion; its tool and repository surface is too broad for one source-built tracer unless local encoding becomes hard to audit. |
| Existing owned 68000 path with narrowly expanded required operations | New CPU dependency or test-only interpreter | A dependency may implement more instructions, but would add another runtime and reentrancy/license burden. A test-only interpreter would bypass the ordinary API and make fixture evidence meaningless. Extend only required instructions with primary-manual tests if the current subset cannot run the guest. |
| CPU-only software Neo Geo sprite subset | Host overlay or a generic graphics framework | Overlay skips guest behavior; a framework obscures the small model. Keep one documented sprite/VRAM path and mark remaining hardware behavior unsupported. |

**Installation:** No package-manager installation command is recommended. The phase's external code candidates are pinned source trees, not registry packages; their source, notices, dependency closure, and admission evidence remain required. Do not add them to the default runtime until their respective gate passes.

## Package Legitimacy Audit

No npm, PyPI, or crates package is proposed. `floooh/chips` and `ymfm` are Git-source candidates and require immutable source, license, dependency-closure and state/callback review under SND-01/SND-02; a registry audit would not establish those properties.

## Architecture Patterns

### System architecture diagram

```text
Tracked guest source + original sprite bytes
                |
                v
       CMake fixture builder
                |
                v
   One generated content artifact
        /                       \
       v                         v
Native C consumer          retro_load_game(content bytes)
       |                         |
       | frame + logical input   | retro_run + input poll
       v                         v
       +----> Native instance API <----+
                    |
                    v
       guest CPU -> fixture board/VRAM
                    |
                    v
        software sprite renderer
          /                  \
         v                    v
 caller-owned pixels     audio buffer metadata/count
         |                    |
         v                    v
 native semantic tests   Libretro audio callback if samples exist
                              |
                              v
                  Libretro software video callback
                              |
                              v
                  Actual pinned RetroArch host
                  (device mapping and pacing)
```

`[ASSUMED]` The initial fixture profile should enter its first-party cartridge guest directly at reset after explicitly initializing only the fixture-required board state. This is a documented BIOS-free fixture entry, not normal MVS BIOS startup. The fixture should use one sprite tile and guest-writable position state; no renderer-side object movement or video overlay is allowed. Keep this profile separate from the later selected MVS/BIOS profile.

### Recommended project structure

`[ASSUMED]` Add small modules that follow current `src/instance.c` and `tests/sdk` ownership patterns:

```text
src/
├── frame.c             # bounded frame/input/output contract
├── fixture_board.c     # fixture profile, logical input port and VRAM writes
├── video_software.c    # bounded sprite/palette-to-pixel path
└── libretro/           # thin adapter and callback translation
tests/
├── fixture/            # source generator, manifest, oracle and rights records
└── libretro/           # callback harness plus actual RetroArch smoke support
```

Do not combine frame scheduling, Libretro callbacks, guest behavior and rendering into one adapter file. The core remains independent of file paths, RetroArch callbacks, device audio, graphics APIs, wall time and host pacing.

### Pattern 1: one bounded native frame

**What:** Sample a single logical controller state at the defined frame boundary, advance one bounded amount of guest machine time, then report progress and fill explicitly sized caller-owned output buffers. The adapter maps RetroPad input before the native call and forwards returned pixels/audio without creating game behavior.

**When to use:** Every ordinary native and Libretro frame. Native code receives values/buffers only; it does not poll controllers or ask the host for time.

**Illustrative contract pseudocode (new names are recommendations, not current API):**

```text
result = advance_frame(instance, sampled_input,
                       video_buffer, video_capacity_bytes,
                       audio_buffer, audio_capacity_frames)
if result is an error:
    report its documented status and progress
else:
    assert dimensions, format, pitch and produced counts
    send returned video/audio to the registered frontend callbacks
```

`[ASSUMED]` Specify video as 320-by-224 software pixels in one explicitly negotiated `XRGB8888` format, with byte pitch and capacity checked as `pitch × height`; allow a padded pitch rather than assuming it equals width times bytes per pixel. This agrees with the cited Neo Geo active area and Libretro's explicit pixel-format negotiation while keeping the tracer small. Confirm format support during `retro_load_game()` and fail the smoke test if negotiation is rejected; do not silently treat a different frontend format as equivalent.

`[ASSUMED]` Specify native audio output as signed 16-bit interleaved stereo at a fixed 48 kHz transport rate so the later Libretro batch callback can consume the same representation. Phase 04 may report zero produced audio frames while retaining explicit capacity/format/channel/rate fields; it must not claim audible sound. If the chosen machine frame ratio is fractional, track it with an integer/rational accumulator when sound is implemented so counts represent emulated time and do not drift.

`[ASSUMED]` Preflight all pointer, capacity, pitch, dimensions and format inputs before mutating machine state. Define whether a guest stop/fault returns partial progress and document that count; never hide it as a successful full frame. Bound execution by machine frame work and any explicit instruction/cycle ceiling, not by host elapsed time. Keep guest time and frontend pacing separate.

### Pattern 2: ordinary Libretro content path

**What:** `retro_load_game()` accepts the generated content buffer and builds the ordinary native instance; `retro_run()` polls the frontend, samples the configured RetroPad direction, invokes one native frame, then calls software video once with the returned pixels. `retro_unload_game()` destroys loaded machine data so another load can follow.

**When to use:** Both the interactive RetroArch path and an automated callback-contract harness. The harness is useful for callback ordering but cannot satisfy HOST-02 by itself.

**Sources:** [Libretro core development guide](https://docs.libretro.com/development/cores/developing-cores/) and [Libretro input API](https://docs.libretro.com/development/input-api/), official documentation reviewed 2026-10-07. The core guide specifies frame callback/polling requirements and frontend-owned pacing; input docs define the RetroPad abstraction. The canonical header should be pinned to an immutable source revision during planning.

### Pattern 3: candidate library isolation

**What:** Put each chip behind an opaque, per-instance private C interface; pass explicit bus/sample callbacks and user data; keep chip state in that instance. Keep all ymfm C++ types and exceptions inside the C++ translation unit and translate failure to the native status/progress contract.

**When to use:** Admission spikes only. The fixture need not produce audible output or integrate these chips just to prove video/input; Phase 04's SND requirements are fulfilled only by their complete gates.

**Admission evidence:** Inventory every source file, mutable global/static, state field, callback, initialization path, license, and transitively required source. Exercise supported-boundary continuation, reset, deterministic clocks/samples, bus and IRQ behavior, failures, multiple instances and actual C consumers. C++ exceptions must not cross the private C boundary. Build both static and shared library configurations and link/run a consumer compiled as C; the wrapper's existence alone is not evidence.

### Anti-patterns to avoid

- **Host-painted movement:** The output can look correct while no guest or board state changed. Render from guest-programmed sprite state and assert guest state separately.
- **Second fixture or API shortcut:** Separate native/frontend binaries or a no-content path can bypass the true content boundary. Use the same generated file and ordinary load path.
- **Frame hash as oracle:** A stable wrong renderer hashes consistently. Assert expected guest state and selected pixels from an independently documented rule, with a wrong-input control.
- **Borrowed emulator truth:** MAME is an implementation reference, not the chip or hardware oracle. Retain its revision and oracle ancestry and label agreement as differential only.
- **Claiming CPU support from the current diagnostic:** The accepted 68000 is bounded to selected diagnostic behavior. First prove the guest's required instruction set; expand only the missing instructions with manual-derived tests.
- **Context API equals reentrant:** Both chip candidates may hide globals/callback state or lazy initialization. Audit source and run distinguishable instances before any such claim.
- **Sound gate collapse:** Build success, silence, or one generated buffer does not admit YM2610 or establish audible SND-03. Keep admission evidence and later sound-fixture evidence separate.
- **Unbounded parser/generator:** If the content artifact uses a container, cap sizes/counts and reject malformed or duplicate entries before allocation. Avoid ZIP/DEFLATE entirely for this single generated file unless the actual frontend packaging requires it.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Build-tree fixture outputs | Ad hoc shell sequencing and duplicate generators | CMake `add_custom_command(OUTPUT ... DEPENDS ...)` plus one named target | `[CITED: https://cmake.org/cmake/help/v3.20/command/add_custom_command.html]` CMake documents generated outputs and explicit dependency edges. Existing project already uses this pattern. |
| General 68000 assembler or full homebrew graphics toolchain | A broad private assembler/asset pipeline for a single tracer | Small, tracked C fixture recipe with explicit guest bytes and the existing C compiler; reconsider pinned ngdevkit only if the real format makes that unclear | This gives deterministic output without importing an entire toolchain. Every encoding remains visible and needs manual-derived assertions. |
| General ROM/archive parser | ZIP, filesystem and content-manager stack for a single public artifact | One bounded fixture content format loaded from Libretro's in-memory bytes | The core needs no filesystem; malformed length and profile checks can be direct. Add established decompression only when a selected real media path needs it. |
| General frontend or renderer abstraction | GUI, GPU backend, host pacing, or reusable engine | Libretro software callback and a small CPU renderer for the selected sprite subset | The user's host owns device/window/pacing concerns; one first-party visible seam needs no renderer framework. |
| Resampling in this phase | YMFM sample-rate behavior or generic DSP framework | Explicit audio metadata and produced-count contract; keep Phase 04 tracer silent | SND-03 belongs to Phase 07. `ymfm` expects a consumer clock and documents output-rate conversion as consumer work. |

**Key insight:** The correctness burden is at the seams: content ownership, sampled input, deterministic frame time, a renderer that uses guest state, safe output bounds, and real consumer linkage. Frameworks do not prove those contracts.

## Common Pitfalls

### Pitfall 1: diagnostic CPU cannot run the fixture guest

**What goes wrong:** A guest may fail before input or video due to an unsupported 68000 operation, while a native-side fallback makes the screenshot pass.  
**Why it happens:** The accepted CPU evidence is explicitly a bounded diagnostic subset.  
**How to avoid:** Define the guest first, enumerate its exact opcodes and expected boundaries, compare them to current source, then either stay within supported behavior or add only required instructions with Motorola manual tests. Never replace failed guest work with host-authored output.  
**Warning signs:** Unsupported-instruction stop, native-only control path, or expected pixels changing while guest state does not.  
**Source:** `[VERIFIED: .planning/workstreams/first-playable-game/RESEARCH.md:24-25,53-55]` and [`tests/sdk/ORACLE.md:93-95`](../../../../../tests/sdk/ORACLE.md).

### Pitfall 2: incorrect buffer arithmetic and lifetime

**What goes wrong:** A short/padded row pitch, arithmetic overflow, or temporary frame storage yields out-of-bounds writes or stale pixels.  
**Why it happens:** Width is mistaken for byte pitch, or output storage expires before the synchronous frontend callback completes.  
**How to avoid:** Make format, dimensions, pitch, capacity and pointer lifetime explicit; validate `pitch >= row_bytes`, checked `pitch * height`, and capacity before stepping. Keep storage valid through the Libretro callback. Test exact-size, one-byte-short, padded-row, null, and overflow boundaries.  
**Warning signs:** Sanitizer failure, only shared build broken, rows sheared, or changes disappearing after the frame function returns.

### Pitfall 3: frontend timing leaks into emulated time

**What goes wrong:** Running faster/slower changes guest position or cycle totals.  
**Why it happens:** The core sleeps or reads a host clock to pace `retro_run()`.  
**How to avoid:** One native bounded frame equals a specified machine-time interval and one input sample. Libretro reports fixed rates; RetroArch controls pacing. Use integer clock ratios/accumulators and preserve frame/stop progress on errors.  
**Warning signs:** Host speed affects boundary observations, system-clock calls in runtime symbols, or frontend-specific frame skipping changes guest state.  
**Source:** `[CITED: https://docs.libretro.com/development/cores/developing-cores/]`.

### Pitfall 4: C++ dependency passes C++ tests but fails real C use

**What goes wrong:** A static library links in a C++ test, but installed C integrators miss the C++ runtime or exception boundary; shared builds also have different runtime dependencies.  
**Why it happens:** Only the source API was wrapped, not the built/transitive link interface.  
**How to avoid:** Compile an actual C consumer against installed static and shared Glueyneo artifacts, run it, and ensure no ymfm type leaks from headers. Audit symbols and runtime dependencies. Catch C++ exceptions inside the shim and return explicit status.  
**Warning signs:** C++ linker driver required at consumer call sites, undefined C++ symbols, exported C++ names, or process termination on a failed allocation.

### Pitfall 5: upstream tests and MAME become circular oracles

**What goes wrong:** Same-implementation agreement is described as independent correctness.  
**Why it happens:** Expected outputs were harvested from the candidate or its reference emulator.  
**How to avoid:** Build fixed guest expectations from the Motorola manual and board behavior from separately identified technical references. Use MAME and upstream ZEX as differential/conformance evidence with ancestry, not silicon proof. Include fixed wrong-behavior controls.  
**Warning signs:** Only golden hashes exist, reference revision absent, or all expected outputs were captured from the tested emulator.

## Code Examples

### Deterministic CMake fixture generation

```cmake
set(FIXTURE_OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/public-fixture.bin")
add_executable(fixture_builder path/to/fixture_builder.c)
add_custom_command(
  OUTPUT "${FIXTURE_OUTPUT}"
  COMMAND $<TARGET_FILE:fixture_builder> --write-fixture "${FIXTURE_OUTPUT}"
  DEPENDS fixture_builder
  VERBATIM
)
add_custom_target(public_playable_fixture
  DEPENDS "${FIXTURE_OUTPUT}"
)
```

The target and symbols above are proposed names, not existing project values. This follows the existing pattern: `[VERIFIED: CMakeLists.txt:176-186]` `add_custom_command(OUTPUT ...)`, `COMMAND $<TARGET_FILE:glueyneo-diagnostic> --write-fixture`, `DEPENDS glueyneo-diagnostic`, and one custom target. CMake's official 3.20 documentation says `OUTPUT` and `DEPENDS` define generated-file rules; do not list a shared output under independent producers.

### Libretro frame callback flow

```text
retro_load_game(content bytes): validate content; create/load native instance
retro_run(): input_poll(); sample RetroPad; advance one native frame
           video_refresh(pixels, width, height, pitch) exactly once
           audio_batch(samples, produced_frames) only when frames exist
retro_unload_game(): destroy the loaded instance
```

This is the official Libretro lifecycle shape, not a Glueyneo implementation. `[CITED: https://docs.libretro.com/development/cores/developing-cores/]` The guide requires one video callback and at least one input poll each frame and defines batch audio as interleaved left/right `int16_t` frames. The current Libretro header describes pixel format negotiation and says the legacy default should not be selected for new code: `[CITED: https://github.com/libretro/libretro-common/blob/master/include/libretro.h]`.

## State of the Art

| Prior approach | Current recommendation | Change / impact |
|---|---|---|
| Treat frontend pacing as part of the emulator loop | Fixed machine-time frame in the native core; frontend owns wall-clock pacing | Official Libretro guide describes fixed rates and frontend pacing; the native API can remain deterministic and host-independent. |
| Use a custom display path for an early proof | Libretro software video plus one native frame-buffer contract | A real callback and actual RetroArch load exercise the chosen consumer without a GUI/graphics dependency. |
| Assume a C-facing wrapper proves chip suitability | Pin and inventory each candidate; test the final C static/shared consumer | This phase can close admission evidence without claiming a general chip or platform compatibility tier. |

**Deprecated/outdated:** Do not use Libretro's implicit/default legacy pixel format as the new API contract. Negotiate an explicit format and fail if the actual target frontend rejects it. `[CITED: https://github.com/libretro/libretro-common/blob/master/include/libretro.h]`

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | Use a BIOS-free fixture profile that directly enters the source-built guest after only fixture-required board initialization. | Architecture Patterns | If this cannot be represented through the ordinary native/content API, the fixture may require more board startup work or a different documented fixture format. |
| A2 | Use a 320-by-224 `XRGB8888` frame, with caller-owned byte buffer and padded pitch allowed. | Pattern 1 | Format negotiation or selected profile may require another explicit format; API or consumer buffers would need adjustment. |
| A3 | The native audio transport should be signed 16-bit interleaved stereo at 48 kHz, with zero produced frames for the silent Phase 04 tracer. | Pattern 1 | The later YM2610 output/resampler and public ABI may need a different rate or layout. |
| A4 | Use the local C generator/explicit guest bytes instead of adding ngdevkit; only introduce it if encoding/asset needs justify its whole toolchain. | Summary / Alternatives | Manual encoding could become hard to audit or unsupported by the current CPU; dependency/toolchain cost may then be justified. |
| A5 | Candidate exact pins from accepted workstream research remain the chosen Z80 and ymfm inputs for Phase 04 admission. | Standard Stack | If exact trees or their source closures differ from the accepted research, repeat provenance/license/state review before admission. |
| A6 | RetroArch `v1.22.2` is the frontend candidate to qualify; its official macOS artifact identity and executable path remain to be captured. | Standard Stack / Environment Availability | Local executable aborts at CLI version probe; a usable official artifact or execution environment may be needed before HOST-02 can pass. |
| A7 | The minimal guest's opcodes fit the accepted 68000 path or require only a bounded manual-tested extension. | Common Pitfalls | Larger CPU scope may block this phase and require explicit replanning; host-side simulation is not an acceptable fallback. |
| A8 | A 48 kHz output contract can relate sample counts to the selected frame clock using a rational accumulator when audio becomes active. | Pattern 1 | Incorrect frame/audio ratio would cause deterministic drift or mismatch at native and frontend boundaries. |

## Open Questions (RESOLVED)

1. **Can the current owned 68000 subset run a guest that polls input and updates sprite state in a loop? — Bounded execution gate**
   - Planning disposition: `04-01-PLAN.md`, Task 1 first inventories the exact opcode/addressing-form pairs against the owned core and primary 68000 documentation. The inventory is limited to the single guest in `tests/fixture/public_guest.c`, with a maximum of eight pairs; it must not expand into a general game-capable CPU claim. Add only missing required operations within that bound, with manual-derived tests. If the guest requires more than eight pairs, unbounded CPU/board work, undocumented behavior, or unsupported operations without primary evidence, stop Task 1 before broadening the core and report the missing instruction/evidence plus a bounded replan; do not claim the tracer complete.
   - Evidence boundary: current accepted CPU evidence remains the diagnostic subset until that task's new instruction evidence passes.

2. **Which fixture content encoding gives the ordinary API and RetroArch a single same file without pretending to be a normal BIOS-booted MVS set? — Chosen implementation**
   - Planning disposition: `04-01-PLAN.md`, Task 1 uses one strict version-1 `GN_PROFILE_PUBLIC_FIXTURE` content envelope generated by `glueyneo-public-fixture`; native and Libretro consumers pass its bytes through ordinary `gn_load`. The BIOS-free first-party reset entry is documented as fixture semantics, never as an SNK BIOS or normal MVS boot. Reject unsupported versions and malformed size/content before execution.

3. **What independent source supports the fixture's board/video register and pixel behavior? — Physical truth explicitly unknown**
   - Planning disposition: use the cited community Neo Geo Development Wiki material as an attributed implementation guide and the independently specified fixture state/pixel rules as the test oracle. MAME remains differential-only. Exact board/video agreement with physical Neo Geo hardware is unknown; no task or success criterion may promote this fixture result to hardware truth. Revisit only with a directly applicable primary source or physical capture.

4. **Can the exact RetroArch release run reliably from a clean command/UI session on the selected macOS configuration? — Bounded execution gate**
   - Planning disposition: `04-02-PLAN.md`, Task 2 runs the actual pinned macOS RetroArch artifact and must establish ordinary content load, documented input delivery, software-video observation, and unload. A callback harness cannot close HOST-02. If the app cannot launch or the runner cannot prove any required observation, record HOST-02 blocked/unknown with exact failed or unavailable observation and artifact identity, stop that acceptance claim, and replan concrete remediation; do not substitute a mock or report a pass.

5. **Can the sound candidates close every admission gate in this phase without delaying the visible tracer? — Separate bounded execution gates**
   - Planning disposition: visible fixture work remains the leading tracer. `04-04-PLAN.md`, Task 3 independently gates the pinned Z80 candidate; any missing cycle, interrupt, bus, continuation, state/license, or instance evidence leaves SND-01 unadmitted and requires bounded replanning. `04-05-PLAN.md`, Task 3 independently gates ymfm, including the private C boundary and installed static/shared C consumers; any failed or unavailable criterion leaves SND-02 unadmitted and requires bounded replanning. Neither gate may be inferred from the other, from source presence, or from fixture success; audible output remains Phase 07.

## Environment Availability

| Dependency | Required by | Available | Version / observation | Fallback |
|---|---|---|---|---|
| CMake | Native build and generated fixture | Yes | 4.4.3 locally; project minimum is separately declared as 3.20 | Use project presets; qualify the documented minimum/selected version in clean-build evidence. |
| Apple Clang / Xcode | macOS native and adapter build | Yes | Apple Clang 21.0.1; Xcode 26.6 locally | None for selected macOS qualification; record exact target SDK/OS/architecture during the pass. |
| Ninja | Existing CMake presets | Yes | 1.13.2 locally | CMake may use another generator, but keep the selected clean build identity explicit. |
| Python | Existing test/build helpers | Yes | Python 3.14.4 locally; CMake currently requests an interpreter without a version bound | Use the project-required interpreter and report its exact identity; no compatibility claim is made from presence alone. |
| Git / source fetch | Pinned candidate source review | Yes | Git 2.41.0; `git ls-remote` to official candidate repositories succeeded | Vendor immutable source revisions and notices for offline clean builds. |
| RetroArch macOS | HOST-02 actual consumer | App bundle present; runnable status unknown | Bundle metadata says 1.22.2; `--version` process aborted (exit `-6`); no core artifact is installed in the app bundle | Obtain/repair the official pinned macOS build and run the actual content path. No mocked fallback can close HOST-02. |
| `floooh/chips` Z80 source | SND-01 candidate | Not present in tracked project | Exact candidate identity is listed in accepted workstream research | Fetch/vendor the exact candidate and required license files only as part of the admission spike. |
| `ymfm` source | SND-02 candidate | Not present in tracked project | Exact candidate identity is listed in accepted workstream research | Fetch/vendor the selected source closure and full notice only as part of the admission spike. |

**Missing dependencies with no fallback:** A working actual pinned RetroArch execution path is not yet demonstrated; this blocks the HOST-02 claim until verified. The two chip sources are not vendored yet, so their admission work cannot begin from the current checkout without fetching the pinned trees.

**Observation quality:** Toolchain and app rows are host-local probes, not platform support evidence. The local RetroArch app metadata and aborted command establish presence/version and a failed CLI probe only, not load, input, video, unload, or reproducible artifact behavior.

## Validation Architecture

### Test framework

| Property | Value |
|---|---|
| Framework | CTest + vendored Unity, both already used by the repository. `[VERIFIED: CMakeLists.txt:227-267]` |
| Config file | `CMakePresets.json`; existing `owned-debug` configure/build/test presets. `[VERIFIED: CMakePresets.json:1-29]` |
| Existing quick command | `cmake --preset owned-debug && cmake --build --preset owned-debug && ctest --preset owned-debug --output-on-failure --no-tests=error` (declared in the preset/config; not run during this research). |
| Existing diagnostic path | `python3 tools/verify_sdk.py` is the current SDK verification entry point, but it does not prove frame, video, input, Libretro, or actual RetroArch behavior. `[VERIFIED: tests/sdk/ORACLE.md:138-145; tools/verify_sdk.py:1-10]` |

### Phase requirements to test map

| Req ID | Behavior | Test type | Automated command | File exists? |
|---|---|---|---|---|
| TRAC-01 | Deterministic artifact regeneration, source/assets rights, notice and ancestry identity | CTest provenance + rights audit | Existing clean build/CTest command; add fixture-specific test before planning names its selector | No phase fixture tests yet |
| TRAC-02 | Ordinary C load/frame, guest-produced software pixels, format/dimension/pitch/capacity checks | Native C consumer + boundary tests | Existing preset command after new tests are added | No |
| TRAC-03 | Fixed logical input trace changes guest state and selected pixels; wrong direction/no input fails | Native integration + negative-control tests | Existing preset command after new tests are added | No |
| HOST-02 | Same generated content loads/runs/unloads through real macOS RetroArch with software video and controller mapping | Actual frontend integration smoke; UI automation or an explicit residual manual input check | Libretro CLI form is documented as `retroarch -L <core> <content> --verbose`; pin an isolated config and exit/input route in the plan | No core or phase smoke exists |
| API-05 | Bounded frame input/output/audio contract, progress/errors, capacities/lifetimes and no host services | API contract, boundary and symbol-closure tests | Existing preset command after new tests are added | No |
| SND-01 | Z80 cycles, interrupts, bus effects, supported continuation, state/license inventory, instance isolation | Candidate conformance + Glueyneo seam tests | Existing preset command plus the admission runner named in the plan | No candidate files/tests |
| SND-02 | YM2610 clock/sample/state/callback/exception behavior and static/shared C consumer | Chip seam tests, exception controls, installed C consumers | Existing preset command plus static/shared consumer commands named in plan | No candidate files/tests |
| QUAL-03 | Clean selected macOS build/install/load with compiler/SDK/OS/architecture/frontend identity | Clean-tree package/consumer build and actual frontend smoke | Existing preset command plus the install/load command selected in plan | No Phase 04 install/load docs |

### Sampling rate and Wave 0 gaps

- **Per task:** Run the focused new fixture/API/consumer test selector once targets and labels are defined; preserve diagnostic regression lanes.
- **Per wave:** Run the full selected preset CTest suite and static/shared installed C consumers.
- **Phase gate:** Clean-tree regeneration, native sequence/control, actual pinned RetroArch content path, and all admission gates must have current identities and positive denominators. Unknown app or chip results remain open.
- **Wave 0 gaps:** New fixture generator/oracle/rights manifest; native frame and output-boundary tests; guest input and meaningful-pixel controls; Libretro callback harness; actual RetroArch smoke automation; candidate admission test suites; real static/shared C-consumer linkage checks for the C++ dependency; install/load documentation. No existing suite covers these new capabilities.

## Security Domain

`[VERIFIED: .planning/config.json:48-50]` The configuration states `<!-- DATA_V8N2D6ST_START -->` `"security_enforcement": true,` `"security_asvs_level": 1,` `<!-- DATA_V8N2D6ST_END -->`. The relevant surface is parsing generated/content bytes, public C pointers and output sizes, external chip callbacks, and importing pinned third-party source. The native core remains free of filesystem/network/device/secret access.

### Applicable ASVS categories

| ASVS area | Applies | Control for this phase |
|---|---|---|
| V1 Architecture, Design and Threat Modeling | Yes | Document the untrusted content and caller-buffer boundaries; keep Libretro host services in the adapter. |
| V2 Authentication | No | There are no users, credentials or authenticated native calls. |
| V3 Session Management | No | The native instance lifecycle is not an authenticated web session. |
| V4 Access Control | No | No user/tenant authorization model exists in this local core. |
| V5 Input Validation (ASVS 4 naming) / ASVS 5.0 validation and business logic | Yes | Check content shape, profile, input masks, pointer/capacity arithmetic, pitch, and supported execution bounds before access/state mutation. |
| V6 Cryptography | No | This phase has no cryptographic operation; do not invent one for fixture identity. Use hashes only as byte identity, not rights proof. |

OWASP ASVS 5.0 taxonomy lists validation/business logic under its second chapter; the older V5 label is shown only to map the repository template. `[CITED: https://owasp.org/projects/asvs; https://cornucopia.owasp.org/taxonomy/asvs-5.0/02-validation-and-business-logic; reviewed 2026-10-07]` This mapping is not a claim that a C emulator core is a web application.

### Known threat patterns

| Pattern | STRIDE | Standard mitigation |
|---|---|---|
| Malformed/truncated fixture header or oversized lengths | Tampering / DoS | Strict format/version and size checks before allocation; reject duplicate/overlapping ranges; do not read past supplied byte length. |
| Null, undersized or overflowed framebuffer/audio buffers | DoS / memory corruption | Validate nullability, checked multiply/add, pitch and byte capacity before stepping or rendering. |
| Guest value drives out-of-range tile/palette/position access | Tampering / memory safety | Mask/validate hardware fields and bound every asset/VRAM lookup; report unsupported behavior instead of using host memory as a fallback. |
| C++ exception escapes ymfm shim or callback re-enters native state | DoS / state corruption | Catch all exceptions in the C++ boundary, map to documented failure/progress, and define callback lifetime/non-reentrancy. |
| Dependency/fixture license or data provenance is incomplete | Supply-chain / rights | Immutable source revision, file/hash/license inventory and notice; original content only; scan staged public artifacts. |

## Sources

### Primary and project sources

- `AGENTS.md` (read 2026-10-07): C17/default C runtime, host boundary, evidence/privacy/dependency rules; exact applicable directives are copied below.
- `.planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-CONTEXT.md` (2026-10-07): locked fixture boot/scene/generator decisions and open planner selections.
- `.planning/workstreams/first-playable-game/REQUIREMENTS.md` and `ROADMAP.md` (2026-10-07): requirement wording, phase boundary and success criteria.
- `include/glueyneo/glueyneo.h`, `src/instance.c`, `CMakeLists.txt`, `CMakePresets.json`, `tests/sdk/guest_fixture.c`, `tests/sdk/ORACLE.md`, `tools/verify_sdk.py`, and public rights/evidence docs (read 2026-10-07): current implemented diagnostic API, generator, tests and licensing patterns. These do not show new Phase 04 behavior.
- [Libretro core development guide](https://docs.libretro.com/development/cores/developing-cores/) and [input API](https://docs.libretro.com/development/input-api/) (official docs reviewed 2026-10-07): lifecycle, in-memory content, frame callbacks, polling, fixed rate/pacing and input abstraction.
- [Canonical Libretro header](https://github.com/libretro/libretro-common/blob/master/include/libretro.h) (official source reviewed 2026-10-07): C ABI and pixel-format negotiation; mutable branch must be pinned before implementation.
- [CMake 3.20 `add_custom_command`](https://cmake.org/cmake/help/v3.20/command/add_custom_command.html): `OUTPUT`/`DEPENDS` behavior at the current project floor.
- [RetroArch v1.22.2 release](https://github.com/libretro/RetroArch/releases/tag/v1.22.2): release candidate; exact macOS artifact digest and successful local run remain outstanding.
- [NeoGeo Development Wiki: display timing](https://wiki.neogeodev.org/index.php/Display_timing), [sprites](https://wiki.neogeodev.org/index.php/Sprites), and [VRAM](https://wiki.neogeodev.org/index.php/VRAM) (community technical references reviewed 2026-10-07): active area, sprite and register model; no physical-hardware validation.
- Motorola, *M68000 Family Programmer's Reference Manual* (1992), and *M68000 8-/16-/32-Bit Microprocessors User's Manual* (1993), exact existing citations in [`tests/sdk/ORACLE.md`](../../../../../tests/sdk/ORACLE.md): CPU instruction effects/timing only, not Neo Geo board truth.
- [MAME Neo Geo video model](https://github.com/mamedev/mame/blob/master/src/mame/snk/neogeo_v.cpp) (implementation reference): differential behavior only; pin revision before using and do not promote to hardware oracle.
- [floooh/chips Z80 source](https://github.com/floooh/chips/tree/9e88298ce56319953ac7a43213a1120359f7a3a6) and [ZEX harness](https://github.com/floooh/chips-test/blob/master/tests/z80-zex.c) (accepted candidate references): cycle/pin API and upstream conformance harness; implementation and test rights/ancestry still require audit.
- [ymfm pinned source](https://github.com/aaronsgiles/ymfm/tree/81aec25ccbb98f4873a255f7551ac4dadac59b4a), [`ymfm_opn.h`](https://github.com/aaronsgiles/ymfm/blob/81aec25ccbb98f4873a255f7551ac4dadac59b4a/src/ymfm_opn.h), and [upstream README](https://github.com/aaronsgiles/ymfm) (reviewed 2026-10-07): YM2610/C++14/BSD-3-Clause/sample-clock model; source closure and admission still pending.
- [ngdevkit](https://github.com/dciabrin/ngdevkit): strongest full-toolchain alternative; no source/toolchain is selected.

## Project Constraints (from AGENTS.md)

- Keep owned runtime and selected runtime dependencies in C by default; the sole current C++ exception is evaluating/admitting the pinned ymfm YM2610 behind a private C interface and all its source/state/isolation/timing/build gates. `[VERIFIED: AGENTS.md:7]`
- Keep the native core independent of frontend, filesystem, audio device, graphics API, network, secrets and wall clock; use opaque per-instance state and explicit ownership, buffers, errors and deterministic time. `[VERIFIED: AGENTS.md:8]`
- Audit reused chip code for mutable globals, callbacks, races and state fields; pin, license, document and minimize third-party changes. `[VERIFIED: AGENTS.md:9]`
- Prefer small flat dependency trees; justify dependencies against local/copied code and keep provenance/notices/update ownership for copied code. `[VERIFIED: AGENTS.md:10]`
- Use concrete modules, defined integer behavior, explicit byte order and checked limits; tie hardware comments to evidence/timing and avoid speculative frameworks or unprofiled optimization. `[VERIFIED: AGENTS.md:11]`
- Separate emulated time from host pacing and preserve original slowdown unless an explicit option changes it. `[VERIFIED: AGENTS.md:12]`
- Keep saves, emulator snapshots, replay compatibility and ABI versions separate; prove continuation and instance isolation before those claims. `[VERIFIED: AGENTS.md:13]`
- Prefer primary sources; record exact source/revision/date, claim, uncertainty and test-oracle ancestry; MAME is not automatically hardware truth. `[VERIFIED: AGENTS.md:17]`
- Pair behavior with automated evidence and documentation; use compiled examples and useful boundary/property/fuzz regressions at proportionate cost. `[VERIFIED: AGENTS.md:18]`
- Record unsupported/skipped/unknown honestly; do not weaken goldens/budgets or rerun away failures. `[VERIFIED: AGENTS.md:19]`
- Bind release/performance claims to exact code/dependency/config/input identities; measured values only. `[VERIFIED: AGENTS.md:20]`
- Keep one current contract per topic and preserve/supersede dated provenance. `[VERIFIED: AGENTS.md:21]`
- Use installed OpenGSD workflow; preserve preparation evidence; keep current/next/longer milestone horizons; pause between named workflow stages. `[VERIFIED: AGENTS.md:25-28]`
- Use independent review, current-revision checks, protected branches and project workflow boundaries; do not accept stale checks or bypass protections. `[VERIFIED: AGENTS.md:26-33]`
- Keep CI small, measure critical path/runner-minutes, preserve cold builds and bound parallelism. `[VERIFIED: AGENTS.md:32]`
- Preserve MIT for original Glueyneo code, retain imported licenses/notices, audit fixtures/dependencies at immutable revisions, and do not distribute game/BIOS media without rights. `[VERIFIED: AGENTS.md:37]`
- Keep commercial/private media, captures, states and private test outputs outside Git/CI/releases; a hash proves bytes only, not rights. `[VERIFIED: AGENTS.md:38]`
- Do not put secrets, personal paths/emails, machine IDs or private account URLs in public artifacts; use an established public/noreply commit identity and scan staged content/logs. `[VERIFIED: AGENTS.md:39-40]`
- Other projects used as research evidence are read-only absent separate authorization. `[VERIFIED: AGENTS.md:41]`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for existing CMake/C17/CTest patterns; MEDIUM for official Libretro contracts; LOW for the working RetroArch target until an actual launch passes.
- Architecture: MEDIUM; the locked separation and official Libretro lifecycle are clear, while new board/video/API work has not been implemented.
- Pitfalls: MEDIUM; current code establishes CPU/API limits and official docs establish frontend constraints, but candidate admission and physical video behavior remain open.

**Research date:** 2026-10-07  
**Valid until:** 2026-11-06 for stable API/build patterns; recheck frontend release/artifact and candidate source pins before planning or implementation.
