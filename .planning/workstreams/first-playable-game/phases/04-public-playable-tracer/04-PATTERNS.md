# Phase 04: Public Playable Tracer - Pattern Map

**Mapped:** 2026-10-07  
**Files analyzed:** 20 proposed files/modules (exact implementation paths remain planner decisions)  
**Analogs found:** 15 / 20; the Libretro, renderer, and chip-adapter seams have no existing in-repository implementation analog.

This map uses proposed paths from `04-RESEARCH.md` as planning targets, not as existing files. The closest analogs below were verified as git-tracked source. Phase 04 introduces new video/input/frontend behavior; the current SDK diagnostic is evidence only for ownership, bounded execution, fixture generation, and testing patterns.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `include/glueyneo/glueyneo.h` (modify) | provider / public API | request-response | same file, current lifecycle API | role-match |
| `src/frame.c` (proposed) | service | request-response | `src/instance.c` | role-match |
| `src/fixture_board.c` (proposed) | model / service | event-driven | `src/instance.c` bus callbacks | partial |
| `src/video_software.c` (proposed) | utility / service | transform | none | none |
| `src/libretro/libretro_core.c` (proposed) | adapter / controller | event-driven | none | none |
| `tests/fixture/guest_fixture.c` (proposed) | fixture generator | transform | `tests/sdk/guest_fixture.c` | role-match |
| `tests/fixture/guest_fixture.h` (proposed) | model/header | request-response | `tests/sdk/guest_fixture.h` | role-match |
| `tests/fixture/test_fixture.c` (proposed) | test | request-response | `tests/sdk/test_sdk.c` | role-match |
| `tests/fixture/ORACLE.md` (proposed) | test documentation | transform | `tests/sdk/ORACLE.md` | role-match |
| `tests/fixture/rights-manifest.json` (proposed) | config/provenance | transform | `docs/rights-inventory.md` | role-match |
| `tests/libretro/callback_harness.c` (proposed) | test | event-driven | none | none |
| `tests/libretro/retroarch_smoke.*` (proposed) | test / runner | event-driven | `tools/verify_sdk.py` | partial |
| `CMakeLists.txt` (modify) | config / build | transform | same file, SDK fixture rules | exact |
| `tools/verify_sdk.py` (modify or new phase runner) | utility / runner | batch | same file | exact |
| `docs/public-content.md` (modify) | documentation | transform | same file | exact |
| `docs/rights-inventory.md` (modify) | documentation / manifest | transform | same file | exact |
| `tests/sdk/ORACLE.md` (leave diagnostic scope; cross-reference only if needed) | test documentation | transform | same file | exact |
| `src/z80_adapter.c` (candidate only) | adapter / service | request-response | none | none |
| `src/ym2610_c_api.cpp` (candidate only) | adapter / service | request-response | none | none |
| `tests/chips/*` (candidate admission suite; exact paths TBD) | tests | request-response | `tests/owned_cpu/*` isolation/continuation tests | partial |

The Z80 and YM2610 files are conditional admission work, independent from the playable tracer. Research requires these gates but proposes no tracked implementation paths for them. Treat the above names as placeholders and search upstream candidate trees only after immutable revisions and license closure are selected. No `libretro.h`, RetroArch, or third-party chip source path is an existing project analog.

## Pattern Assignments

### `include/glueyneo/glueyneo.h` (public API, request-response)

**Analog:** `include/glueyneo/glueyneo.h`

Public ABI types use standard integer/size types, opaque state, named status enums, and explicit lifecycle ownership. Keep the new frame contract similarly explicit; do not imply that old diagnostic profile behavior provides video/input.

**Imports and ABI guard** (lines 5-22):

```c
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
```

**Opaque instance and status conventions** (lines 30-40, 87-101):

```c
typedef struct gn_instance gn_instance;
typedef enum {
    GN_STATUS_OK = 0,
    GN_STATUS_INVALID_ARGUMENT,
    GN_STATUS_INVALID_STATE,
    GN_STATUS_INVALID_MEDIA,
    GN_STATUS_UNSUPPORTED_PROFILE,
    GN_STATUS_OUT_OF_MEMORY,
    GN_STATUS_CPU_FAILURE
} gn_status;

/* ...document pointer lifetime and per-instance threading... */
GN_API gn_status gn_create(gn_instance **out_instance);
GN_API gn_status gn_load(gn_instance *instance, const gn_manifest *manifest);
```

Add only contract fields required by API-05: sampled logical input, format/dimensions/pitch/capacities, produced audio count and metadata, progress/stop reason, and actionable status. Use a separate profile constant for the public fixture.

### `src/frame.c` and `src/fixture_board.c` (service/model, request-response and event-driven)

**Analog:** `src/instance.c`

The existing instance implementation keeps mutable machine and memory data behind `gn_instance`, checks manifest bounds before access, and returns explicit statuses. Reuse its per-instance organization and preflight discipline. Do not copy its diagnostic address map or infer Neo Geo board semantics from it.

**Per-instance ownership** (`src/instance.c`, lines 17-48):

```c
typedef struct {
    gn_allocator allocator;
    gn_memory_region rom;
    gn_memory_region ram;
    uint8_t *ram_seed;
    size_t ram_seed_size;
    owned_cpu *cpu;
} gn_image;

struct gn_instance {
    gn_allocator allocator;
    gn_image *image;
};
```

**Validation before use** (`src/instance.c`, lines 160-213):

```c
if ((region->source == NULL && region->source_size != 0u) ||
    region->mapped_size == 0u ||
    region->source_size > (size_t)region->mapped_size) {
    return GN_STATUS_INVALID_MEDIA;
}
const uint64_t start = (uint64_t)region->guest_base;
const uint64_t end = start + (uint64_t)region->mapped_size;
if (end > (UINT64_C(1) << 32)) return GN_STATUS_INVALID_MEDIA;
```

**Core callback and byte-order pattern** (`src/instance.c`, lines 93-119):

```c
if (image == NULL || value == NULL || (address & UINT32_C(1)) != 0u) {
    return 0;
}
/* Resolve a mapped region and bounds before dereferencing. */
observed = (uint16_t)(((uint16_t)image->rom.bytes[offset] << 8) |
                      (uint16_t)image->rom.bytes[offset + 1u]);
if (found == 0) return 0;
*value = observed;
return 1;
```

For frame code, preflight pointers, dimensions, pitch multiplication, format and capacities before advancing any guest state. Keep counters/time and board state in the instance. The board model owns input-latched guest effects and VRAM state; a renderer should consume that state without host-authored movement.

### `src/video_software.c` (utility/service, transform)

**Analog:** No renderer exists in tracked source.

Use the project's explicit-width and checked-arithmetic style from `src/instance.c` validation above, but the rendering behavior itself has no analog. Follow the bounded sprite subset selected in planning, derive output only from guest-programmed board state and fixture graphics, and report unsupported formats/paths explicitly. The community Neo Geo references in RESEARCH.md are implementation guidance with stated uncertainty, not existing code or a hardware oracle.

### `src/libretro/libretro_core.c` (adapter/controller, event-driven)

**Analog:** No Libretro adapter or frontend callback implementation exists in tracked source.

Keep this boundary thin: own a single frontend instance, map RetroPad state into logical native input, call one native frame per `retro_run`, and synchronously forward native pixels through Libretro's software-video callback. Content must enter via ordinary `retro_load_game()` bytes and be released by unload. Use pinned upstream header/API patterns during implementation research; never put frontend callbacks, pacing, filesystem access, or host drawing in the native service. Frontend threading/reentrancy is unqualified.

### `tests/fixture/guest_fixture.c` and `.h` (generator/model, transform)

**Analog:** `tests/sdk/guest_fixture.c`, `tests/sdk/guest_fixture.h`

The current builder is a small deterministic C recipe over tracked source; it writes explicit big-endian guest words and initializes scenario bytes. Use that shape for one original fixture, not its CPU-only behavior.

**Generator pattern** (`tests/sdk/guest_fixture.c`, lines 6-25):

```c
void guest_fixture_build(guest_fixture_image *image,
                         guest_fixture_scenario scenario) {
    static const uint16_t words[] = { UINT16_C(0x7007), UINT16_C(0x5680) };
    if (image == NULL) return;
    memset(image, 0, sizeof(*image));
    for (size_t index = 0u; index < sizeof(words) / sizeof(words[0]); ++index) {
        const size_t offset = 0x100u + index * 2u;
        image->rom[offset] = (uint8_t)(words[index] >> 8);
        image->rom[offset + 1u] = (uint8_t)words[index];
    }
}
```

Keep generated bytes in the build tree with one output producer. Same artifact should feed native and RetroArch consumers; document source, generator identity, rights, and generated digest separately.

### `tests/fixture/test_fixture.c` (test, request-response)

**Analog:** `tests/sdk/test_sdk.c`

Tests use named cases and check status plus guest observations, boundary behavior, and explicit expected results. Keep expected pixels tied to an independently stated fixture rule; add wrong-direction/no-input controls that prove the expected assertion can fail.

**Named result and run checks** (`tests/sdk/test_sdk.c`, lines 115-135):

```c
SDK_CASE("sdk.diagnostic.original-a");
gn_run_result run;
SDK_CHECK_STATUS("sdk.run.status", GN_STATUS_OK, gn_run(instance, 172u, &run));
SDK_CHECK_U64("sdk.run.elapsed-cycles", 172u, run.elapsed_cycles);
SDK_CHECK_STATUS("sdk.run.reason-stopped", GN_RUN_STOPPED, run.reason);
SDK_CHECK_U64("sdk.observe.arithmetic", 10u, observations.arithmetic_result);
```

Assert guest-owned marker position and semantic output pixels at specified frame boundaries. Include exact-capacity, one-byte-short, padded-pitch, null, overflow, stop/error progress, and wrong-input cases as API-05/host-safety evidence. Frame hashes may supplement these checks, never replace them.

### `tests/fixture/ORACLE.md` (test documentation, transform)

**Analog:** `tests/sdk/ORACLE.md`

Current oracle docs distinguish primary manual-derived instruction outcomes from project-defined bus contracts and call out what is not physical hardware evidence.

**Ancestry boundary** (`tests/sdk/ORACLE.md`, lines 9-16):

```markdown
Expected effects are derived from ... primary manuals below. They are not
copied from the owned CPU output or another emulator. ... the mapped ROM/RAM
callback ordering is the project's functional diagnostic contract, not a
physical Neo Geo bus capture.
```

Create a separate fixture oracle. Attribute guest instruction encoding, sprite/VRAM community documentation, pixel expectations, and any MAME differential comparison independently. State that none of these alone establish physical video accuracy.

### `tests/fixture/rights-manifest.json`, `docs/rights-inventory.md`, `docs/public-content.md` (provenance/config)

**Analogs:** `docs/rights-inventory.md`, `docs/public-content.md`

Every public fixture/source/notice needs exact path and identity, rights basis, provenance, and retained notice. `rights-inventory.md` says unknown items are excluded and requires exact source revision/digest/license/notice (lines 20-29); `public-content.md` clearly limits scanner claims (lines 3-8). Add only original material or affirmative rights evidence. A hash binds bytes but does not establish permission.

### `tests/libretro/callback_harness.c` (test, event-driven)

**Analog:** No callback-driven frontend harness exists.

Use a synthetic harness only to test callback ordering, input polling, one frame per run, content load/unload, and forwarding of the exact native output. It cannot satisfy HOST-02; retain the separate actual pinned macOS RetroArch consumer check.

### `tests/libretro/retroarch_smoke.*` and `tools/verify_sdk.py` (runner, batch)

**Analog:** `tools/verify_sdk.py`

The existing runner uses named fail-closed suites, a bounded worker count and child timeout, and build-tree-only artifacts (`tools/verify_sdk.py`, lines 17-31, 33-57). Reuse suite naming and bounded process handling. Keep frontend identity/artifact digest and unsupported outcomes explicit; do not claim actual RetroArch behavior from a mock harness or an aborted version probe.

### `CMakeLists.txt` (config/build, transform)

**Analog:** `CMakeLists.txt`

The existing build has one generator executable, one `add_custom_command(OUTPUT ...)`, explicit `DEPENDS`, and one named custom target (lines 144-186). It also applies strict C17 target properties and target-scoped warning flags (lines 97-128).

**Build-tree generator pattern** (lines 176-186):

```cmake
add_custom_command(
  OUTPUT "${GLUEYNEO_DIAGNOSTIC_FIXTURE}"
  COMMAND $<TARGET_FILE:glueyneo-diagnostic> --write-fixture
          "${GLUEYNEO_DIAGNOSTIC_FIXTURE}"
  DEPENDS glueyneo-diagnostic
  VERBATIM
)
add_custom_target(glueyneo-original-fixture ALL
  DEPENDS "${GLUEYNEO_DIAGNOSTIC_FIXTURE}")
```

Use a single output rule for the new fixture. Add its runtime modules to the runtime target and matching test target deliberately; avoid accidentally linking a test-only implementation into production.

### `src/z80_adapter.c`, `src/ym2610_c_api.cpp`, `tests/chips/*` (conditional adapters and tests)

**Analogs:** no imported chip adapter exists. For instance and continuation test shape, see tracked `tests/owned_cpu/test_isolation.c`, `test_state.c`, and `test_timing.c`; each is a partial match only.

No code excerpt can establish admission for these absent dependencies. Preserve pinned source and license closure; inventory mutable globals/callbacks/init, then test cycle or clock behavior, interrupts/bus, continuation/reset, determinism, separate instances and failure containment. For ymfm, keep C++ objects/exceptions behind a private C ABI and verify static/shared linkage with a real C consumer. Do not couple either gate to fixture video correctness.

## Shared Patterns

### Opaque per-instance state and explicit ownership

**Source:** `include/glueyneo/glueyneo.h` lines 87-100; `src/instance.c` lines 17-48.  
**Apply to:** frame, board, video state and private chip adapters. Keep machine state on the instance, validate before mutation, and document caller buffer lifetimes.

### Bounded execution and progress

**Source:** `include/glueyneo/glueyneo.h` lines 62-78; `tests/sdk/test_sdk.c` lines 186-220.  
**Apply to:** native frame API and guest execution. Preserve requested/actual work, stop/fault boundary and error status; do not use host elapsed time for machine progress.

### Public rights and oracle ancestry

**Source:** `tests/sdk/ORACLE.md` lines 3-16; `docs/rights-inventory.md` lines 20-29.  
**Apply to:** new fixture source/assets/output, oracle docs, candidate code/notices, and public archives. Keep private media out of all tracked evidence.

### Same generated artifact; real consumer evidence

**Source:** `CMakeLists.txt` lines 176-186; `tools/verify_sdk.py` lines 33-57.  
**Apply to:** native test and Libretro content load. One CMake output and named target prevent fixture divergence; mock callback tests supplement, rather than replace, a real RetroArch smoke.

### Error and resource limits

**Source:** `src/instance.c` lines 160-213.  
**Apply to:** content envelope parsing and frame output. Check lengths, arithmetic, and capacities before allocation or state advancement; use the existing status vocabulary where suitable and add documented statuses if needed.

## No Analog Found

| File/area | Role | Data Flow | Reason |
|---|---|---|---|
| `src/video_software.c` | renderer | transform | No video/renderer implementation is tracked. |
| `src/libretro/libretro_core.c` | frontend adapter | event-driven | No Libretro header, callback bridge, or frontend integration exists. |
| `tests/libretro/callback_harness.c` | test | event-driven | No callback seam or harness exists. |
| Z80/YM2610 adapter sources | chip adapters | request-response | These candidate dependencies are not currently admitted or vendored. |

## Metadata

**Analog search scope:** `include/`, `src/`, `tests/`, `tools/`, `docs/`, and root CMake.  
**Tracked-source gate:** all named existing analogs were checked with `git ls-files`; no ignored `.gsd/capabilities` mirror paths are used.  
**Pattern extraction date:** 2026-10-07.
