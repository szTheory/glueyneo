# First Playable Game — Milestone Research

**Prepared:** 2026-10-07  
**Status:** Research recommendations accepted and reused for the user-approved [requirements](REQUIREMENTS.md) and [roadmap](ROADMAP.md). Milestone initialization is complete; implementation has not started.
**Scope:** Decision input for the `first-playable-game` workstream. This note is not implementation evidence or a compatibility claim.

**Discussion update — 2026-10-07:** The user approved evaluating/admitting `ymfm` as a narrow C++14 dependency behind a private C interface, subject to the admission checks below (PROJECT-D-48). C remains the default; incremental replacement or a licensed C port may be considered later, without adding a replacement framework or rewrite to this milestone. The supplied BIOS archive is now available in the Git-ignored local media directory; the copy matches its source and passes ZIP CRC validation. Its exact MVS profile and compatibility are not yet qualified. No private source path, media checksum or archive contents are recorded here.

**Research choice — 2026-10-07:** The user chose to reuse this accepted research for milestone requirements rather than repeat domain research. Phase-specific implementation research and the bounded chip admission spikes remain required where the plans need them; the project-wide research preference is unchanged.

## Recommended milestone outcome

Use Metal Slug X as the user's local play target and a tiny first-party Neo Geo fixture for public CI. The target configuration should start with one MVS profile and one pinned macOS RetroArch setup. “Playable” means reaching active gameplay, moving and firing, observing scrolling, and hearing representative game sound. Full-game completion, broad cartridge compatibility, AES, save states, durable saves, rewind, netplay, and performance claims remain out of scope.

The public fixture must exercise the same native and libretro interfaces where practical, but passing it does not establish Metal Slug X compatibility. Keep commercial game and BIOS data, private paths/checksums, captures, traces, and logs out of Git, CI, and release artifacts. The user-provided local archive's identity check is evidence about the archive only, not emulator compatibility.

## Decision recommendations

| Area | Recommendation | Rationale and boundary |
|---|---|---|
| Product target | A local MVS Metal Slug X play scenario plus a separate redistributable first-party CI fixture. | A target-only path poorly exercises public automation; a homebrew-only milestone would miss the user's stated goal. Keep the two evidence claims separate. |
| First useful result | Prove a first-party guest through the ordinary native API and an actual pinned RetroArch build early: render a software frame and respond to input. | This exposes the board/API/frontend seam before the full commercial-game bring-up. It is a tracer, not proof of commercial compatibility. |
| Native/frontend boundary | Keep the native core host-independent, deterministic, and per-instance. Put file/archive access, frontend callbacks, host pacing, and input mapping in the libretro adapter/import boundary. Use software video first. | Libretro advances one frame per `retro_run`, expects input polling and one video callback, and leaves host pacing to the frontend. The API does not guarantee thread safety/reentrancy. |
| CPU/board | Continue the accepted owned C17 68000 and own the Neo Geo bus, video model, and scheduler. Expand CPU behavior only against title needs and source-qualified tests. | Phase 01 admission covers only the bounded diagnostic subset; it does not provide a game-capable CPU or board. Do not treat MAME-derived vectors as independent hardware truth. |
| Z80 | Spike the pinned `floooh/chips` Z80 candidate; admit only after Glueyneo tests for cycle accounting, interrupts, bus effects, continuation, and two-instance isolation. | It is a compact C header with explicit tick/pin interaction and upstream ZEX tests; integration correctness remains unproven. |
| YM2610 | The user approved the C++14 exception for `ymfm`. Put a bounded admission spike early in the roadmap before committing to full sound integration. Keep the dependency behind a private C interface and test per-instance state, deterministic clock/sample behavior and build/consumer linkage. | A C wrapper does not turn C++ into a C dependency. Admission remains conditional on evidence. Prefer a small replaceable interface over a speculative plugin framework; any later C port retains licensing, provenance and regression obligations. |
| Game media | Keep normalized media buffers in the native contract. First test what the pinned frontend provides. If ZIP bytes reach the adapter, use bounded archive parsing and an established decompressor; never hand-write DEFLATE. Defer general archive formats. | ZIP parsing must cap entry count, expanded size, path/name handling, duplicates, and malformed input. Add a dependency only if the required frontend path makes it necessary. |
| Fixtures and rights | Prefer an original fixture generated from tracked source over a third-party “homebrew” ROM until the exact source, assets, binary, and redistribution terms are audited. | The examined ngdevkit example repository shows a GPL-3.0 GitHub label while its README text says LGPL-3.0; a repository badge or “homebrew” label does not settle every asset's rights. |
| Reference evidence | Use MAME as a differential implementation reference with exact revision and oracle ancestry recorded. Keep hardware uncertainty explicit. | MAME's Neo Geo model identifies separate main/audio CPUs, YM2610, sprites, BIOS regions, and banking. Its Metal Slug X protection code includes an unresolved calculation comment, so its implementation is not a complete hardware oracle. |
| Versioning and delivery | Keep this a separately scoped workstream; do not call it v0.2 or imply v0.1 is complete while Phase 03 remains open. | The v0.1 hosted release gate is still active elsewhere. Before code execution, isolate the work from the Phase 03 branch and reconcile the existing dirty planning relocation. |

## Proposed phase sequence for roadmap discussion

These are sequencing recommendations, not approved numbered phases:

1. **Playable tracer:** original guest fixture, native API path, software frame, input response, and an actual pinned RetroArch consumer. Run the short Z80/YM2610 feasibility spikes early enough to inform later scope.
2. **MVS game boot path:** define BIOS and cartridge inputs, expand the owned CPU against demonstrated needs, and implement the required MVS address map, memory/banking, and timing to reach the selected title's boot/attract path.
3. **Interactive title behavior:** implement the title's required protection and remaining video/input behavior; reach an active scene with movement, firing, and scrolling.
4. **Sound and qualification:** deliver representative YM2610/Z80 sound, exercise the private local game scenario in the pinned RetroArch setup, and keep recurring CI on the first-party fixture only.

Reorder or split these only after the tracer reveals actual dependency and effort. Preserve a playable end-to-end path as soon as possible; avoid a large sequence of isolated chip implementations that produces no visible game progress.

## Acceptance and evidence

- Public CI builds from a clean tree and runs the first-party fixture through native and libretro consumers. Tests assert lifecycle/error behavior, one-frame advancement, frame dimensions/pitch, input effects, deterministic output for a fixed guest/input sequence, and safe malformed-fixture handling.
- Local qualification uses a pinned RetroArch/core revision and one stated MVS/BIOS setup. The selected game reaches active gameplay and responds to the documented controller mapping with representative sound. Record only generic pass/fail and public build/configuration identity in public evidence; keep private media identity and all derived outputs local.
- Compare relevant behavior against MAME only with revision, input, and oracle ancestry recorded. Distinguish emulator agreement from measured hardware truth. Preserve unknown/unsupported results.
- Use a human play check only for experience that automated evidence cannot establish; deterministic machine assertions should cover frame, input, and audio behavior first.

## Important unknowns and scope gates

1. BIOS availability is resolved: the user supplied a local archive, copied into the ignored media directory and checked for byte equality and ZIP CRC integrity. Selecting and qualifying the exact MVS BIOS configuration remains open. Public fixture work does not distribute a production BIOS.
2. The YM2610 language exception is approved (PROJECT-D-48); a bounded spike must still establish source/state inventory, independent instances, deterministic timing/sample output and build/linkage behavior before dependency admission.
3. The current 68000 implementation is diagnostic-only. Estimate the title-required expansion from early execution evidence; do not promise a full general-purpose 68000 compatibility claim by inference.
4. The private title may expose protection or timing behavior where MAME is the only available model. Keep those claims qualified until independent evidence exists.

## Source references

Primary/upstream references consulted on 2026-10-07; mutable branch URLs must be pinned to immutable revisions in implementation plans:

- [Libretro core development guide](https://docs.libretro.com/development/cores/developing-cores/) — lifecycle, `need_fullpath`, frame callbacks, input, timing, serialization, and thread-safety boundaries.
- [Canonical libretro header](https://github.com/libretro/libretro-common/blob/master/include/libretro.h) — normative API declarations and callback contracts.
- [MAME Neo Geo model](https://github.com/mamedev/mame/blob/master/src/mame/snk/neogeo.h) — device and clock structure; implementation evidence, not silicon truth.
- [MAME Metal Slug X protection](https://github.com/mamedev/mame/blob/master/src/devices/bus/neogeo/prot_mslugx.cpp) — dedicated protection model and documented uncertainty.
- [floooh/chips at examined revision](https://github.com/floooh/chips/tree/9e88298ce56319953ac7a43213a1120359f7a3a6) and [Z80 test harness](https://github.com/floooh/chips-test/blob/master/tests/z80-zex.c) — C candidate and separate upstream CPU tests.
- [ymfm at examined revision](https://github.com/aaronsgiles/ymfm/tree/81aec25ccbb98f4873a255f7551ac4dadac59b4a) — YM2610 support, BSD-3-Clause license, and C++14 requirement.
- [ngdevkit examples](https://github.com/dciabrin/ngdevkit-examples) — useful reference material, but license labeling needs per-file/content reconciliation before fixture reuse.
- Current project constraints: [AGENTS.md](../../../AGENTS.md), [project description](../../PROJECT.md), [v0.1 requirements](../cpu-bus-diagnostic-sdk-alpha/REQUIREMENTS.md), and [v0.1 roadmap](../cpu-bus-diagnostic-sdk-alpha/ROADMAP.md).
