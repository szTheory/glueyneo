# Stack Research

**Domain:** Portable C Neo Geo MVS/AES emulation core; v0.1 CPU/bus diagnostic SDK alpha
**Researched:** 2026-10-01
**Confidence:** MEDIUM
**Status:** Recommendations and dependency candidates; no backend, platform, package or performance qualification has been completed.

**Scope update — 2026-10-02:** Current project contracts supersede this report's Musashi-first and conditional SDL3-host recommendations. The owner selected planning for an owned C17 CPU core; each core repository targets a library, headless diagnostic runner, and thin libretro adapter, with GUI ownership in RetroArch and the future shared host. The proposed CMake 3.24 floor below is not adopted; keep the existing 3.20 floor provisional until platform/toolchain evidence justifies changing it. Preserve this report as dated research provenance.

This report applies [PROJECT.md](../PROJECT.md) to the stack dimension. It carries forward PREP-D-03/PREP-D-04 and PREP-D-07–PREP-D-14 from [preparation/DECISIONS.md](../preparation/DECISIONS.md), with targeted fresh source checks. The current milestone supersedes the preparation's broader first-release examples: video, sound, libretro, game compatibility and save-state formats are future work. All recommendations below have MEDIUM research confidence; acceptance still requires implementation evidence. The installed research helper classified cross-checked `websearch` findings as MEDIUM. No Context7 MCP or `ctx7` executable was available, so official sources were inspected directly after the research-plan seam selected websearch.

## Recommended Stack

### Core Technologies

| Technology | Version / identity | Purpose | Why Recommended |
|------------|--------------------|---------|-----------------|
| C | C17; exact compiler/SDK minima unqualified | Runtime, board model, native public API and selected runtime dependencies | Matches the project constraint and keeps embedding independent of a C++ runtime. Require defined integer behavior, explicit byte order, 8-bit bytes and needed exact-width types. Avoid optional C features that narrow portability. |
| CMake + CTest | Proposed minimum **3.24**, with a separate pinned current CI version | One target-based build, test registration, static/shared output and installed package | The versioned documentation covers C17 properties, target exports, relocatable packages and presets. The floor is a proposal, not proof that the resulting project works there. [S-06–S-09] |
| Musashi | Candidate commit **313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd**; source identifies 4.60 but file version labels vary | First 68000 feasibility candidate behind a private adapter | Mature portable C implementation with MIT-style notices in core/generator source. Existing global state, file closure and timing need substantial qualification. This is an investigation choice, not an approved dependency. [S-01–S-05] |
| Native C library contract | Pre-1.0, opaque per-instance state; no frozen ABI yet | Create/load/reset/bounded run/results/destroy for an original diagnostic | Keeps host I/O outside the core and lets a real consumer expose ownership and error-contract problems before ABI commitments. Board behavior remains original Glueyneo code. |

Use target-local `C_STANDARD 17`, `C_STANDARD_REQUIRED YES` and `C_EXTENSIONS NO`; the required setting avoids CMake silently selecting an older supported standard. Compiler flags alone do not prove library or platform support. [S-06] MSVC offers `/std:c17` from VS 2019 16.8, with SDK/UCRT caveats and optional-feature gaps; do not convert that historical availability into a Glueyneo minimum. [S-11]

### Supporting Libraries

| Library | Version / identity | Purpose | When to Use |
|---------|--------------------|---------|-------------|
| ThrowTheSwitch Unity | **v2.7.0**, commit **b6763fbd9cedfacaa89e2ad9fd00d615a234e355**, released 2026-07-16 | Test-only C assertions | Vendor its small C core and MIT notice. Use explicit C runners registered with CTest; Ruby, Ceedling and CMock are not required for this setup. Tag and commit were cross-checked through upstream Git refs and GitHub API. [S-10] |
| Platform C runtime | Supplied by each qualified toolchain | Bounded allocation and ordinary C facilities | Keep allocator ownership explicit; avoid required clocks, environment reads, filesystem or process control in the library. Record any platform-specific link dependencies. |
| No additional runtime framework | None | Keep v0.1 dependency surface small | No database, network, GUI, archive parser, audio backend or graphics library is needed to execute a buffer-loaded CPU/bus diagnostic. |

### Development Tools

| Tool | Version / policy | Purpose and Notes |
|------|------------------|-------------------|
| Ninja | Candidate developer pin **1.13.2**, commit **3441b633c2fe2c494e958780ba0f4227b1327634**; release 2025-11-20 | Fast build executor, latest release reported by upstream on access date. Not a runtime dependency or mandatory consumer generator. [S-12] |
| Apple Clang, upstream Clang, GCC, MSVC | Exact versions and SDKs selected and recorded during platform qualification | Start with representative macOS arm64, Linux x86-64 and Windows x86-64 C builds. Add macOS x86-64 evidence before claiming Intel support. These are proposed test lanes, not support claims. |
| ASan/UBSan; targeted race checking | Pin with the selected compatible compiler | Exercise boundaries and imported code. A two-instance threaded harness belongs outside the single-thread-per-instance core. Sanitizer availability differs by toolchain; report unsupported lanes explicitly. |
| libFuzzer and plain C property loops | Compiler-matched, optional development builds | Bounded diagnostic-media/parser and execution regressions; reproducible seeds and retained minimized failures. Use established tools without building a property-testing framework. See [preparation architecture](../preparation/C-CORE-ARCHITECTURE.md), C-19–C-23. |
| Original diagnostic source plus reproducible fixture generation | Exact assembler/generator identity to select | Prefer a tiny documented diagnostic with checked-in redistributable bytes and independent expected effects. Rebuilding fixtures may require a maintainer cross-toolchain; ordinary SDK/source consumers must not. |

## 68000 Feasibility and Acceptance Gate

**Recommendation:** Investigate the pinned Musashi revision first, in a private 68000 adapter. Set a concrete adaptation budget before implementation: time/effort cap, permitted source changes, required behaviors and rejection criteria. Do not select a backend simply because a register test passes.

The fresh source inspection confirms process-global CPU, cycle, tracing, address-error and jump-buffer state in `m68kcpu.c`. It also exposes shared opcode-table construction. An upstream context-copy function does not cover every such object or initialization race. [S-01, S-02] The bounded acceptance should cover:

1. **State inventory:** Enumerate every mutable global/static, callback, user pointer, table initialization and error path in the actual compiled closure. Assign machine state to instances; make shared tables immutable before concurrent use. Keep transient jump buffers out of portable guest state.
2. **Independent instances:** Interleave distinguishable machines, then run separate instances concurrently with separate buses and callbacks. Exercise create/reset/destroy and failures while another instance exists. Reject cross-contamination, unsynchronized lazy initialization, process-global current-instance routing or a global lock offered as full independence.
3. **Timing contract:** Determine instruction-boundary stopping, budget overshoot, interrupt acknowledgement, exception behavior and bus read/write ordering. Document actual cycles returned and unsupported precision. Instruction totals alone do not establish per-access timing. Audit relevant configuration switches rather than inheriting defaults: the pinned configuration defaults interrupt acknowledgement, address-error emulation and some ordering behavior off. [S-03]
4. **Defined behavior:** Review conversions, shifts, pointer aliasing and exceptional control flow under the chosen C subset. Run narrowly meaningful boundary/opcode tests and the original diagnostic through the ordinary public seam. A shared-ancestry reference can corroborate behavior but cannot independently prove hardware fidelity.
5. **Build and license closure:** List every copied, compiled, generated and distributed file, its license, source identity, local patches and update procedure. This gate precedes adoption.

### The default Musashi source closure needs special attention

The pinned Makefile includes `softfloat/softfloat.c` alongside CPU/disassembler/generated opcodes. [S-04] SoftFloat identifies itself as Release 2b, carries responsibility/indemnity and derivative-notice terms distinct from the core's MIT-style grant, and has mutable floating-point control state. Do not describe the entire repository as MIT based on `m68kcpu.c`. [S-05]

The CPU source includes `m68kfpu.c`; that file defines a fatal-error helper that writes to stderr and exits. [S-01, S-05] A 68000-only public API must not inherit ambient process effects from an unused later-CPU feature. **First prove the minimal 68000 source/dependency closure**, including generator output and headers. Do not assume turning variant macros off removes all FPU/SoftFloat references or license obligations; distribution itself also needs an audit. If pruning or contextization exceeds the agreed budget, record rejection and reopen the backend decision before building the rest of the milestone on it. This research does not establish a qualified alternative.

## Offline Source Builds and Package Consumer Seams

Ship generated opcode C/header output in the source tree and source release, alongside the pinned generator/input provenance. Verify regeneration as a maintainer operation. `m68kmake` is a host tool; never execute a target-architecture binary during cross compilation. Normal source consumers should need only the supported C toolchain, CMake and a chosen build executor. [S-02, S-04, S-13]

Vendor the selected audited runtime files and Unity test subset locally. A tag URL, Git submodule needing retrieval, or `FETCHCONTENT_FULLY_DISCONNECTED=ON` on an empty first configure does not provide a self-contained offline source archive. CMake explicitly expects populated content for disconnected use. [S-08] Release archives should contain notices, patch records, dependency checksums and generated-source identities, with no private fixture inputs.

Use one concrete library target with alias/export **`glueyneo::glueyneo`**, `BUILD_SHARED_LIBS` support and namespaced project options. Keep tests/tools disabled by default when embedded. Export usage requirements without developer warnings, sanitizers, machine-specific optimization flags or source-tree include paths. Install a relocatable CMake config/version package and a pkg-config description that accounts for private static-link dependencies. Windows shared builds need explicit exports/imports; package layout and ABI identity require deliberate tests. [S-07]

Required consumer evidence before SDK acceptance:

- Build and run a real C diagnostic consumer from a separate project using `find_package(glueyneo CONFIG REQUIRED)` and the exported target.
- Repeat for static and shared artifacts; relocate the installed prefix and remove access to the original source/build tree.
- Exercise source embedding separately; verify parent build options and warning policy remain under the parent's control.
- Build a clean extracted release source archive offline, without Git history, Python, Ruby, a C++ compiler, frontend libraries or target-code execution during configure/build.
- Compile a separate C++ consumer of the public header to check linkage guards without introducing C++ into runtime dependencies. Record package version and ABI identity separately from future snapshots/replays/saves.

## Installation

There is no implemented build to install yet. The following is the **proposed consumer workflow**, to become a compiled/documented acceptance example once targets and options exist:

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF
cmake --build build
cmake --install build --prefix ./stage

# The consumer is a separate source project with its own main.c and CMakeLists.txt.
cmake -S examples/consumer -B consumer-build -DCMAKE_PREFIX_PATH="$PWD/stage"
cmake --build consumer-build
```

Do not prescribe network package installation for the core. Maintainer verification presets should enable the test option and run `ctest --test-dir build --output-on-failure`; exact preset/option names are for the foundation phase to define. Keep tracked preset schema compatible with the chosen CMake floor and ignore machine-local user presets. [S-09]

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Qualify a small C Musashi adaptation first | Original 68000 interpreter | Reconsider if licensing/source closure, reentrancy or fidelity adaptation exceeds the explicit budget. Original implementation has a much larger semantics/oracle burden. |
| C17 runtime throughout | C++ chip engine behind C ABI | Requires an explicit change to the all-C runtime constraint; a C ABI does not make the implementation C. Keep as a future scope decision, not an implicit workaround. |
| CMake/CTest + Unity | Meson, Ceedling/CMock, custom assertion library | Adopt only for a demonstrated integration or testing need that outweighs duplicate build/tooling maintenance. |
| Checked-in generated C | Mandatory consumer-time regeneration | Appropriate only if the host toolchain and cross-build story are deliberately supported; unnecessary for v0.1 release-source consumption. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Full reference-emulator codebase as the core | Imports broader architecture, licensing and host assumptions | Original board/API plus the audited chip closure |
| Global singleton or process-global current CPU pointer | Violates independent-instance contract and hides callback routing hazards | Explicit instance state and bus ownership |
| Latest-branch downloads at configure time | Breaks reproducibility and offline delivery | Immutable pins, checksums and vendored release content |
| FPU/SoftFloat transitively retained without review | Adds state, process effects and distinct licensing outside the required CPU scope | Prove minimal closure or document/reconsider the actual dependency |
| C23-only facilities, GNU dispatch extensions, JIT, speculative SIMD | Unqualified portability and increased validation cost | Small C17 interpreter integration and measured scalar baseline |
| SDL, libretro, resampler or YM2610 integration as v0.1 prerequisites | Delays the executable CPU/bus diagnostic SDK | Future milestone qualification after the native seam works |

## Stack Patterns by Variant

**SDK alpha:** C17 board/API + one qualified C 68000 engine + original diagnostic; test-only Unity. No full Neo Geo compatibility assertion follows from diagnostic execution.

**Future interactive diagnostic:** Add a thin libretro adapter and qualify it in a pinned actual RetroArch macOS build. Add video/input and select Z80/YM2610 only when that milestone begins. SDL3 remains conditional on a recurring host need.

**Cross compilation:** Consume distributed generated C and use a toolchain file. Regeneration is a separate host build. The exact target ABI, byte order, alignment and integer assumptions remain qualification inputs.

### Future Chip Inventory — Not Selected for v0.1

| Candidate | Examined immutable revision | Rationale and Unresolved Gate |
|-----------|-----------------------------|-------------------------------|
| Jolly Good Z80 from Geolith | `194024931935eff2092e36fc4f8e53e62ed11097` | C/MIT candidate already used in a Neo Geo core; audit instance state, callbacks, NMI/IRQ, banking and timing. |
| chips `z80.h` | `9e88298ce56319953ac7a43213a1120359f7a3a6` | C/zlib candidate with explicit state and cycle interface; compare hardware behavior and integration cost before choosing one backend. |
| YMFM-C from Geolith | `194024931935eff2092e36fc4f8e53e62ed11097` | BSD-3-Clause-header C candidate with mutable synthesis/timer state and serializer coupling; needs a separate bounded feasibility effort. |
| Upstream ymfm | `81aec25ccbb98f4873a255f7551ac4dadac59b4a` | BSD C++14 implementation is comparative evidence and possible future scope reconsideration; incompatible with current all-C runtime selection rule. |

These are dated preparation receipts, not freshly qualified latest versions. Source links, file caveats and ancestry are retained in [hardware/ecosystem evidence](../preparation/NEOGEO-HARDWARE-AND-ECOSYSTEM.md), HW-21–HW-25. No audio resampler is selected.

## Version Compatibility and Phase Implications

| Combination / phase | Status | Required Evidence |
|---------------------|--------|-------------------|
| Musashi pin + C17 + supported compilers | Unknown | First phase: closure/license audit, explicit budget, bounded adaptation, isolation and timing counterexamples |
| Unity 2.7.0 + project CMake/CTest build | Candidate; upstream pin verified | Compile the vendored subset and meaningful project tests on actual toolchains |
| CMake 3.24 floor + selected presets/exports | Proposed | Foundation: test that floor and a separately pinned current version; avoid newer-only preset/schema features |
| Static/shared SDK + macOS/Linux/Windows | Proposed matrix | Real diagnostic consumer, install/relocation and package dependency evidence per claimed lane |
| Generated opcodes + offline/cross source build | Design recommendation | Regeneration comparison plus clean archive build without fetching or target-tool execution |
| Diagnostic output + release artifact | No measured baseline | Integration/release: exact code/dependency/config/input identities, supported subset, tested commit and complete staged artifacts |

Qualify the backend before public ABI hardening. Build an executable diagnostic consumer early enough to constrain API and packaging decisions, then broaden platforms and evidence proportionately. Leave complete Z80/audio and continuation/persistence contracts for the next milestone. The unresolved CPU adaptation cost is the main phase-specific research flag.

## Sources

All fresh accesses were on **2026-10-01**. MEDIUM is the research helper's cross-checked websearch confidence; primary-source inspection establishes source facts, not hardware truth or implementation qualification.

| ID | Exact reference / revision | Supported claim and limitation |
|----|----------------------------|--------------------------------|
| S-01 | [Musashi CPU](https://github.com/kstenerud/Musashi/blob/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/m68kcpu.c) | Global execution state, opcode-table initialization, FPU inclusion and core notice. This pin also matched upstream HEAD at access; not a complete audit. |
| S-02 | [Musashi README](https://github.com/kstenerud/Musashi/blob/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/readme.txt) / [generator](https://github.com/kstenerud/Musashi/blob/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/m68kmake.c) | C engine, context operations and opcode generation; README/version labels are not an immutable release identity. |
| S-03 | [Musashi configuration](https://github.com/kstenerud/Musashi/blob/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/m68kconf.h) | CPU variants, bus/interrupt/exception configuration; selected configuration still needs tests. |
| S-04 | [Musashi Makefile](https://github.com/kstenerud/Musashi/blob/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/Makefile) | Default SoftFloat/source list and generated files; not proof of minimal 68000 linkage. |
| S-05 | [SoftFloat source](https://github.com/kstenerud/Musashi/blob/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/softfloat/softfloat.c) / [FPU source](https://github.com/kstenerud/Musashi/blob/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/m68kfpu.c) | Distinct notices, mutable FP controls, stderr/exit helper. Retrieved directly after a web-cache miss; exact distributed closure and licensing acceptance remain unresolved. |
| S-06 | [CMake 3.24 C_STANDARD](https://cmake.org/cmake/help/v3.24/prop_tgt/C_STANDARD.html) | C17 setting and standard decay/required-property behavior. |
| S-07 | [CMake 3.24 packages](https://cmake.org/cmake/help/v3.24/manual/cmake-packages.7.html) | Exported usage requirements, configs and relocatable packages; actual consumer behavior untested. |
| S-08 | [CMake FetchContent](https://cmake.org/cmake/help/latest/module/FetchContent.html) | First-population/disconnected caveat; moving current docs, not all features apply at the proposed floor. |
| S-09 | [CMake 3.24 presets](https://cmake.org/cmake/help/v3.24/manual/cmake-presets.7.html) | Tracked shared presets, local user presets and versioned schema. |
| S-10 | [Unity release](https://github.com/ThrowTheSwitch/Unity/releases/tag/v2.7.0), [pinned README](https://github.com/ThrowTheSwitch/Unity/blob/b6763fbd9cedfacaa89e2ad9fd00d615a234e355/README.md), [license](https://github.com/ThrowTheSwitch/Unity/blob/b6763fbd9cedfacaa89e2ad9fd00d615a234e355/LICENSE.txt) | Release date, one C source/two headers and MIT notice; no project/toolchain compatibility claim. |
| S-11 | [Microsoft C standard options](https://learn.microsoft.com/en-us/cpp/build/reference/std-specify-language-standard-version?view=msvc-170) | C17 availability, optional features and SDK/UCRT caveats; page dated 2025-01-30. |
| S-12 | [Ninja v1.13.2 release](https://github.com/ninja-build/ninja/releases/tag/v1.13.2) | Release identity/date; Git ref verified, binary/checksum selection still pending. |
| S-13 | [CMake cross-compiling guide](https://cmake.org/cmake/help/book/mastering-cmake/chapter/Cross%20Compiling%20With%20CMake.html) | Host-tool/target separation; no Glueyneo cross-platform result implied. |

---
*Stack research for Glueyneo; reviewed against current CPU/bus SDK scope on 2026-10-01.*
