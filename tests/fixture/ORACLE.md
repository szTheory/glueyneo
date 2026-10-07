# Public playable fixture oracle and provenance

The public tracer is original Glueyneo C source licensed under the repository
MIT license. `public_guest.c` deterministically builds the sole content artifact
used by its native consumer. The `GNFX` version-1 envelope contains a 512-byte
guest ROM, a ten-byte RAM initialization prefix, and an 8x8 one-bit marker tile.
It contains no BIOS, game ROM, commercial data, or third-party guest bytes.
The generated file is a build artifact and is not committed.

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

Existing forms `MOVE.W (abs.L),Dn` and `STOP #$2700` were already in the
documented owned CPU subset. This guest added only two opcode/addressing pairs:
`ADD.W D0,D1` and `MOVE.W D1,(abs.L)`. Their effects, flags, and cycle counts
are tested against Motorola, *M68000 Family Programmer's Reference Manual*
(1992), §4-4 and the MOVE instruction entry, plus *M68000 8-/16-/32-Bit
Microprocessors User's Manual*, ninth edition (1993), tables 8-2 and 8-4.
Those primary manuals support CPU instruction semantics and timing only.

The input port, `GNFX` envelope, reset-entry-per-frame behavior, pixel format,
backdrop, marker, and 12 MHz / 60 cycle ratio are first-party fixture
semantics. The cycle ratio is not established Neo Geo timing. This fixture
does not establish physical board/video behavior, BIOS compatibility, normal
MVS boot, commercial-game compatibility, or hardware truth. The community
Neo Geo Development Wiki display/sprite/VRAM pages are implementation context
only; MAME is differential reference material, not an independent oracle.

## Rebuild and test

`cmake --preset sdk-debug && cmake --build --preset sdk-debug --target
glueyneo-public-fixture public_guest_test && ctest --preset sdk-debug -R
'^public_guest_tracer$' --output-on-failure --no-tests=error` rebuilds the
artifact and runs the ordinary C API consumer.
