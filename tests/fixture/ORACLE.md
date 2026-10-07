# Public playable fixture oracle and provenance

The public tracer is original Glueyneo C source licensed under the repository
MIT license. `public_guest.c` deterministically builds the sole content artifact
used by its native consumer. The `GNFX` version-1 envelope contains a 512-byte
guest ROM, a ten-byte RAM initialization prefix, and an 8x8 one-bit marker tile.
It contains no BIOS, game ROM, commercial data, or third-party guest bytes.
The generated file is a build artifact and is not committed.

## Source, generator, and output identity

The source recipe is `tests/fixture/public_guest.c`; it defines the guest words,
RAM seed, marker bitmap, envelope, and writer. The generator executable is the
ordinary C test consumer, built from `tests/fixture/test_public_guest.c` and
`tests/fixture/public_guest.c`; its `--write-fixture` path calls
`public_guest_write`. CMake target `glueyneo-public-fixture` is the single
producer and writes `build/sdk-debug/public-playable.bin` for the `sdk-debug`
preset. Native CTest and the real RetroArch smoke both receive that same path.
The fixture-specific [`rights-manifest.json`](rights-manifest.json) records
SHA-256 and byte length separately for the recipe, assertion source, generated
asset source, and output. The 602-byte output digest is
`59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0`.
`python3 tests/fixture/check_fixture.py --source tests/fixture/public_guest.c
--artifact build/sdk-debug/public-playable.bin --rights
tests/fixture/rights-manifest.json --check-rebuild --negative-control` checks
source and rights records, verifies the unique CMake producer and shared
consumer path, rebuilds twice, and proves that changed bytes are rejected.

Authorship and redistribution are affirmative: the guest recipe, seed, bitmap,
tests, and documentation were authored for Glueyneo and are distributed under
the repository MIT license, with `LICENSE` retained. The checker records no
commercial material, firmware, private capture, or third-party guest asset.
The generated binary is ignored build output and is not included in source or
release archives. Hash identity binds the stated bytes; it is not itself proof
of legal rights.

## Guest contract

The BIOS-free fixture reset vector starts at ROM offset `0x100` with SSP
`0x2000`. Each `gn_advance_frame` call samples the logical direction mask once,
resets the small fixture CPU to that source-built entry while retaining guest
RAM, and executes a nominal 200,000-cycle frame contract. The guest uses these
forms in order:

| PC | Words | Expected effect |
|---:|---|---|
| `0x0100` | `3039 0030 0000` | Read the sampled right-direction word from fixture input port `0x00300000` into D0. |
| `0x0106` | `3239 0000 1000` | Read guest marker x from RAM `0x1000` into D1. |
| `0x010c` | `d240` | Add the word in D0 to D1, retaining D1's upper word. |
| `0x010e` | `33c1 0000 1000` | Write D1's low word to guest marker x at RAM `0x1000`. |
| `0x0114` | `4e72 2700` | Stop the fixture guest at the frame boundary. |

The guest-owned coordinate begins at `(16,16)`. RIGHT is encoded as one and
advances x by one; LEFT and no input both provide zero to the guest. The native
renderer consumes guest RAM x/y and the fixture-owned bitmap. It produces a
black `320x224` background and a white `8x8` marker using native-endian
`uint32_t` pixel values `0x00RRGGBB`. The selected semantic pixel expectations
are specified by this fixture contract, not copied from an emulator.

The C frame request requires XRGB8888 and exact `320x224` dimensions. Pixel
pitch is bytes per row and the checked minimum capacity is
`(height - 1) * pitch + width * 4`; row padding is not written. A null pixel
pointer is invalid. The fixture reports a 12,000,000/1 machine clock and exact
consumed-cycle progress over that clock; a complete 200,000-cycle frame is
`200000/12000000` seconds (1/60) with no host-time conversion. Audio transport
metadata is signed-16 interleaved stereo at 48 kHz, with zero produced frames
and no buffer writes. A null audio pointer is accepted only with zero frame
capacity. The all-zero output is a silent contract, not audible sound support.

## CPU and board evidence

The independent assertion ancestry is the fixture contract above and the
primary Motorola manuals, not output copied from Glueyneo or another emulator.
The exact manual-derived CPU expectations for `ADD.W D0,D1` (`0xd240`) and
`MOVE.W D1,(abs.L)` (`0x33c1` plus the absolute address) are recorded in
[`tests/owned_cpu/ORACLE.md`](../owned_cpu/ORACLE.md): Motorola, *M68000 Family
Programmer's Reference Manual* (1992), §4-4 and MOVE entry; *M68000 8-/16-/32-Bit
Microprocessors User's Manual*, Rev. 9.1 (1993), tables 8-2 and 8-4. These
primary manuals justify CPU semantics and timing only. The one-step trace
expectations are independently stated here: NONE leaves x=16; RIGHT produces
x=17 then x=18; pixel `(0,0)` remains black; the 8x8 marker's first/last pixels
are white and the next edge is black. Substituting LEFT or NONE must fail the
rightward coordinate and newly occupied edge assertions. These are fixture
assertions, not copied test output.

The input port, `GNFX` envelope, reset-entry-per-frame behavior, pixel format,
backdrop, marker, and 12 MHz / 60 cycle ratio are first-party fixture
semantics. The cycle ratio is not established Neo Geo timing. The community
[Neo Geo Development Wiki display timing](https://wiki.neogeodev.org/index.php/Display_timing),
[sprites](https://wiki.neogeodev.org/index.php/Sprites), and
[VRAM](https://wiki.neogeodev.org/index.php/VRAM) pages were reviewed
2026-10-07; they are community-maintained implementation references with no
immutable revision recorded, not vendor manuals or physical observation. Any
claims derived from them remain uncertain and require separate corroboration.
MAME's [`neogeo_v.cpp`](https://github.com/mamedev/mame/blob/master/src/mame/snk/neogeo_v.cpp)
is a mutable-branch implementation reference only; a pinned comparison can be
differential evidence, never an independent hardware oracle. The accepted
68000 evidence covers only its bounded diagnostic subset plus the two named
instruction forms above. This fixture does not support the diagnostic profile,
general MVS profile, general Neo Geo video behavior, physical board/video
behavior, BIOS compatibility, normal MVS boot, commercial-game compatibility,
or any claim of hardware truth.

## Rebuild and test

The native trace is `[NONE, RIGHT, RIGHT]` and expects coordinates
`[(16,16), (17,16), (18,16)]`. At each boundary the consumer checks the
background, marker interior, and marker edge; after movement it checks both
the vacated edge and newly occupied edge. Separate LEFT-substitution and
no-input controls stay at x=16 and assert that the expected rightward edge is
absent. These controls establish the fixture's own input behavior only.

`cmake --preset sdk-debug && cmake --build --preset sdk-debug --target
glueyneo-public-fixture public_guest_test && ctest --preset sdk-debug -R
'^public_guest_' --output-on-failure --no-tests=error` rebuilds the artifact
and runs the ordinary C API consumer and negative controls. The pinned
RetroArch invocation is recorded in the adjacent 04-02 summary; a real frontend
pass remains unknown until load, input, pixels, and unload are all observed.
