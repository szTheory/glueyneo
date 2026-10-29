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

## Public sound fixture: original GNMV v3 recipe

The sound workload is a separate original source-built fixture. The generator
is `tests/fixture/public_sound_guest.c`; the ordinary C consumer and executable
recipe checks are in `tests/fixture/test_public_sound_guest.c`. CMake's
`glueyneo-public-sound-fixture` target runs
`public_sound_test --write-fixture <build-dir>/public-sound-mvs.bin`, and both
`public_sound_fixture` and the Libretro callback harness load that same
generated path. The deterministic output is 67,108,976 bytes: a 16-byte GNMV
header, eight 12-byte region descriptors, and 64 MiB of region data. Its
recorded build identity and source identities are in
[`rights-manifest.json`](rights-manifest.json). The binary remains ignored
build output and is not committed or released.

The header records GNMV manifest version 3, the normalized MSX profile, and
eight regions serialized as descriptor followed immediately by that region's
bytes, in this order:

| Role | Bytes | Recipe |
|---|---:|---|
| BIOS | `0x80000` | Zero-filled launch substitute except for the original fixture vectors and main-CPU program at `0x100`; it is not SNK firmware. |
| Program | `0x500000` | Zero-filled; the main fixture setup is intentionally in the BIOS-role substitute. |
| Fixed | `0x20000` | Zero-filled except four first-party tile bytes at offsets `0x20`, `0x28`, `0x30`, and `0x38`. |
| Audio program | `0x20000` | Zero-filled; the synthetic Z80 boot and command handler are in the audio-BIOS-role substitute. |
| Samples | `0xa00000` | 256 generated ADPCM-B bytes followed by zeroes. For byte index `i`, high nibble is `(3*i+5) mod 16`, low nibble is `(7*i+2) mod 16`. |
| Sprites | `0x3000000` | Zero-filled. |
| Audio BIOS | `0x20000` | Original fixture Z80 boot, NMI handler, and YM2610 register-write routines. It is not a production BIOS. |
| Y zoom | `0x20000` | Zero-filled. |

The native recipe test checks the exact header, role order and sizes, the launch
vectors, the active-low P1-A polling sequence, sound boot bytes, both command
dispatch values, the ADPCM-B register-write sequence, the four fixed-layer
bytes, all 256 formula-generated sample bytes, zero-filled sample tail, and
byte equality with a fresh generator call. This makes the synthetic launch
substitute and the generated sample part of the executable source contract,
not undocumented fixture data.

The launch main guest writes the fixed-layer palette and tile landmark, sends
music command `0x3c`, and waits for the sound-CPU acknowledgment. It then polls
the MVS input word at `0x00300000`; active-low P1 A sends action command `0xa5`,
waits for acknowledgment, and returns to music after release. The synthetic
Z80 boot enables the fixture command NMI. Its handler reads the command from
port `0x00`, replies through port `0x0c`, and programs the actual YM2610 ports
`0x04/0x05`. Command `0x3c` sets SSG channel A period 125, enables only its tone,
and releases ADPCM-B. Command `0xa5` keeps that tone and starts ADPCM-B from
address block zero through block zero, with Delta-N `0xffff`, maximum output
level, and both left/right routes. Other commands key off the tone and stop
ADPCM-B. The audio-channel distinction is therefore SSG plus ADPCM-B; this
fixture does not exercise FM or ADPCM-A.

### Oracle ancestry and test boundaries

Primary chip documentation is separate from the expected emulator output:

* The [Yamaha YM2610 data sheet](https://dtech.lv/files_ym/ym2610.pdf), pp. 2,
  4, 5, and 8–9, identifies the standard 8 MHz master-clock input, SSG period
  registers, ADPCM-B controls, sample-address registers, Delta-N, and 4-bit
  ADPCM. The available copy is a scan hosted by a third-party mirror.
* The [Yamaha YM2610 Application Manual, version 1.12, dated
  1995-01-20](https://ajworld.net/neogeodev/ym2610am_en.html), Functional Overview and
  ADPCM-B register sections, describes SSG fine/coarse period fields, ADPCM-B
  start, stereo route, 256-byte address units, maximum level, and Delta-N.
  The hosted manual is a translated copy; its Delta-N section explicitly notes
  an ambiguity in the source divisor. The fixture records register values and
  does not claim a physical-chip sample rate from that translated formula.

The `0x7d` SSG period with a zero coarse register and the test's 48-output-frame
correlation are the fixture's 1 kHz source-model expectation. The modified
period `0x3e` is expected to correlate at 24 output frames (about 2 kHz in the
48 kHz consumer stream). These converted periodicities are qualified against
the pinned YMFM implementation plus Glueyneo's clocking and converter path;
they are not measurements of a physical YM2610. The exact register image,
sample data formula, command meanings, CPU launch code, fixed tile, and video
landmark are first-party fixture definitions.

The independent converter source is `tools/audio/design_mvs_pcm.py`; it derives
the normalized 12-phase, 80-tap Q1.30 Kaiser-windowed sinc coefficients and
analytic response with Python's standard library. `src/mvs/mvs_bus.c` contains
the runtime coefficient table and conversion path. Their exact file identities
are recorded in the manifest. The YM2610 implementation is the selected
third-party `ymfm` source closure at revision
`81aec25ccbb98f4873a255f7551ac4dadac59b4a`, with its BSD-3-Clause notice and
Glueyneo reset patch recorded in `third_party/ymfm/NOTICE.md`. YMFM's behavior
is implementation-model evidence; none of its source is claimed as Glueyneo
authorship or physical-chip truth. The native and callback consumer claims are
limited to the verified same-content, same-input, same-frame PCM/video
transfer. Callback acceptance does not establish host-device playback.

The native assertions require the sustained tone, generated sample burst,
equal channels for the dual-route case, tone after burst release, and a fixed
video landmark. Controls make the intended causes discriminating: period 62
must replace the baseline 48-frame correlation with a 24-frame correlation;
a wrong sound-handler command, key-off main command, and omitted launch command
must be silent; left-only routing must alter burst stereo balance; zeroed
original sample bytes must change fire-burst PCM. The consumer and
`libretro_audio_contract` compare transferred PCM/video at matched emulated
frame boundaries. These tests do not qualify FM, ADPCM-A, clipping limits,
physical timing, BIOS behavior, commercial titles, or audible frontend output.
They preserve the separate GNFX v1 silent fixture and its existing byte identity
and timing checks.

`cmake --preset owned-debug && cmake --build --preset owned-debug && ctest
--preset owned-debug -R
'^(public_sound_fixture|public_guest_contract|public_guest_trace|public_guest_negative_left|public_guest_negative_none)$'
--output-on-failure --no-tests=error` regenerates and checks the sound recipe
alongside the unchanged GNFX consumer and its input controls. The separate
`libretro_audio_contract` test exercises the real C adapter callbacks; actual
frontend/device playback remains a later qualification.

### Native whole-machine continuation witness

`tests/sdk/state_fixture.h` builds the same original GNMV v3 guest in memory by
calling `public_sound_guest_build`. Its test-only setup writes the Z80 bank
latch and YM Timer A registers, adds a timer ISR that clears the IRQ latch, and
keeps the authored input-polling main guest active. The two isolation variants
change only first-party fixture bytes: one updates the main/audio command and
SSG setup together; the other also permutes the generated sample nibbles. The
source recipe and all transformations are bound in `rights-manifest.json`.
The 67,108,976-byte bundle is copied by the native load call, overwritten, and
freed before continuation; no generated bundle or captured state is committed.

`tests/sdk/test_state.c` captures/restores only through the public v1 state
API. It compares the complete XRGB8888 frame, every delivered interleaved PCM
sample, guest reply, frame result, board/calendar observations, video carry,
watchdog state, interrupt mask, YM timer/clock state, and filter history against
an independently uninterrupted instance on the same input schedule. The
controls alter one canonical serialized section or one valid field in a copied
state, restore that state through the public API, and require the named future
guest, video, frame-time, or nonzero-PCM assertion to fail. The supervisor
rejects a wrong assertion, extra failed assertion, empty report, crash, sanitizer
diagnostic, or timeout. These controls demonstrate sensitivity to omitted or
corrupted state in the tested observation path; they are not additional
runtime qualification and do not establish hardware truth.

The isolation suite uses three distinct normalized media identities and input
schedules, retained save-RAM addresses, guarded caller state buffers, and
same-instance serial references. Worker threads each query compatibility and
restore one different instance; same-instance concurrent calls are outside the
contract. Repeated successful restores, repeated rejection of the same invalid
payload, and unload/reload are compared using future observations. Ordinary
threaded success does not imply ThreadSanitizer coverage.

### Native MVS save diagnostic guest

`tests/fixture/public_save_guest.c` provides the tracked recipe used by both the
process witness and its `--write-fixture` mode. It calls the original synthetic
GNMV v3 public sound fixture builder, then replaces only that generated bundle's
BIOS-role bytes in memory with an original Glueyneo diagnostic guest. It includes
no production BIOS, game ROM, commercial asset, third-party guest, captured save
or other private output. The rights manifest records the generator and assertion
source sizes, SHA-256 identities, immutable Git revisions, and MIT provenance.

The exact bundle is 67,108,976 bytes. Its emitted SHA-256 is
`9cefb11420e190f5902e8861f5becda1c63c7ccd988118d7d93dc814a1b36690`, matching
the output captured from the original in-runner recipe before extraction. The
bounded generation command is
`sdk_save_process --write-fixture <build-dir>/save-mvs.bin`; it creates the
caller-specified file exclusively, writes no more than the fixture's recorded
size, and refuses to overwrite an existing path. Generated bundles remain
ignored build output and are not committed.

The guest's first pass copies six SRAM bytes to work RAM before it considers any
write: offsets `0`, `1`, `0x1234`, `0x1235`, `0xfffe`, and `0xffff`. The native
runner compares those guest-produced bytes to the expected saved value and
reports the result as `save.guest-output`. On the writer path, MVS input A or B
selects the asymmetric payload below; the input changes execution only, so
both payloads use the same guest and media identity.

| Input | Guest-produced SRAM bytes |
|---|---|
| P1 A | `123456789abc` |
| P1 B | `a1b2c3d4e5f6` |

After the initial reads, the writer attempts a byte store while SRAM is locked,
unlocks SRAM through the MVS control register, then performs two byte stores and
two word stores covering the six observed offsets. The A path repeats an
already-effective byte and word value to check that same-value stores do not
advance persistence lineage. The reader runs in a distinct process after the
writer exits, imports only the authoritative durable envelope, and checks its
guest output. Two causal controls omit import or supply the other valid saved
value; each must fail specifically at `save.guest-output`. Snapshot transfer
is not used.

The guest-output oracle is separate from the host disk-history oracle. Named
host controls reject invalid authoritative targets before guest execution,
reject a false ACK even when the published bytes can be read, preserve the
latest B branch against an obsolete publication, and cover 18 syscall-fault
cases across first-create and A-to-B replacement. A separate 20-case process
kill matrix crosses ten publication stages with both disk histories, then
opens a fresh reader and checks only the authoritative target; temporary
orphans are not promoted. These host observations were run on macOS 26.6.2 /
Darwin 25.6.0 / APFS with F_FULLFSYNC, checked file close, atomic rename,
directory fsync and close. Other host commit protocols and physical power-loss
recovery remain unqualified. The rights manifest binds these cases, their
source files and revisions, the generated input identity, and the distinct
guest-output expectations.

These expectations are authored from the fixture and public persistence API.
They establish that this implementation transfers the specified SRAM bytes
through the exercised process path. They are not a reference to physical MVS
behavior, a claim about any private game's save feature, or evidence of hardware
truth. The guest's instructions, input mapping, and output convention are
fixture semantics; hardware compatibility remains unknown.

## Public persistence guest source provenance

`tests/fixture/public_persistence_guest.c` is the original source recipe for
the public persistence guest. It constructs the guest program in the BIOS role
of the synthetic fixture at test time; it does not include a game ROM,
commercial guest bytes, production firmware, private capture, or saved-state
payload. `public_sound_guest.c` is the original synthetic base recipe. The
`public_persistence_fixture` section of `rights-manifest.json` binds both
source paths to their exact current Git blobs and records affirmative
repository-MIT rights. Its oracle ancestry is the authored recipe and emulator
consumer contract only. Passing these assertions does not establish hardware
truth, production BIOS behavior, or commercial-game behavior.

The example persistence host helper in `examples/persistence_host.[ch]` is a
Glueyneo Maintainers-owned MIT sample copy derived from
`tests/sdk/save_host.[ch]` at immutable revision
`a73a9f543d8743896a5e4b7d2b28d0189f3e94c8`. The `sample_owned_helper` manifest
section records SHA-256 and byte counts for those origin blobs and for the
current sample files. A sample helper edit requires maintainers to review its
drift against the pinned origin and rerun the source-bound checks. This record
does not claim that the sample and test helper remain textually or behaviorally
identical.
