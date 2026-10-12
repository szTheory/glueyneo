# Selected MVS media contract

This document describes the current, bounded `GNMV` version-1 role-bundle
contract and the exact public MAME metadata used for the selected Metal Slug X
profile. It does not claim that the private archive or BIOS has been accepted,
that the title boots, or that MAME describes original hardware perfectly.

## Public profile map

The profile uses MAME `mslugx` at commit
[`31e52312c59e4d60d70235118bcbccd220f5232e`](https://github.com/mamedev/mame/tree/31e52312c59e4d60d70235118bcbccd220f5232e).
The public `ROM_START(mslugx)` declaration specifies these mapped regions:

| Role | MAME region | Mapped bytes | Public layout evidence |
|---|---|---:|---|
| BIOS | `mainbios` | `0x80000` | `NEOGEO_BIOS` region; selected local BIOS identity remains unqualified |
| Program | `cslot1:maincpu` | `0x500000` | P1 and P2 use `ROM_LOAD16_WORD_SWAP` |
| Fixed | `cslot1:fixed` | `0x20000` | `NEO_SFIX_128K` |
| Audio program | `cslot1:audiocpu` | `0x20000` | `NEO_BIOS_AUDIO_128K` |
| Samples | `cslot1:ymsnd:adpcma` | `0xa00000` | Three contiguous sample loads: 4 MiB, 4 MiB, 2 MiB |
| Sprites | `cslot1:sprites` | `0x3000000` | Six 8 MiB `ROM_LOAD16_BYTE` lanes, interleaved in pairs |

The total normalized region payload is `0x3fc0000` bytes (63.75 MiB). These
sizes and transforms come from MAME source metadata. They are not observations
of physical silicon. The MAME source comment at the Metal Slug X protection
selector still asks how a selector should be calculated; that path remains an
explicit uncertainty and cannot be promoted to a hardware claim by matching
MAME.

The source excerpt is
[`neogeo.cpp`, `ROM_START(mslugx)`](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp#L8640-L8661).
The shared BIOS region is declared in
[`NEOGEO_BIOS`](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp#L2253-L2287).

## Native API and bundle

`GN_MVS_MANIFEST_VERSION` is additive; the diagnostic manifest-v1 ABI remains
unchanged. `gn_load_mvs` accepts exactly the six roles above, requires their
profile-specific sizes, validates the aggregate limit and byte-lane descriptor,
then owns its copies. A candidate image is initialized before it replaces the
previous image. A rejected candidate leaves the current image intact.

`gn_observe_mvs_bus_fault` takes the writable observation-buffer size and copies
no more than that size. The stable prefix through `valid` is required; appended
fields are returned only when included in the caller's size. This is a new,
pre-release diagnostic API with no legacy binary callers at the base revision;
the function signature and prefix are now fixed for size-aware evolution, while
the observation `version` identifies the full set of fields the library knows.

`GNMV` contains a 16-byte big-endian header (`GNMV`, bundle version, profile
identifier, role count), followed by six 12-byte role/64-bit-length descriptors
and the region bytes. The native API consumes only this normalized in-memory
representation. The Libretro adapter recognizes the bundle magic, bounds each
descriptor against the supplied content span, copies the media via the native
API, and does not link the archive decoder.

The standalone C17 `mvs_importer` retains the canonical six-role ZIP32 mode and
adds a selected-source mode:

```text
mvs_importer --selected game.zip bios.zip output.gnmv
```

The selected mode accepts exactly one `mslugx` game archive and a separate
BIOS archive. Its fixed member table pins all 13 game members and the selected
Europe MVS v2 BIOS (`sp-s2.sp1`) to the CRC/SHA-1 values in the MAME source
revision above. The game archive cannot contain extra members. The BIOS archive
must contain exactly one `sp-s2.sp1` member; other entries may have flat safe
names and are ignored only after ZIP32 metadata/extents, bounded decompression,
and CRC validation. The BIOS archive remains limited to 64 entries, 8 MiB per
entry, 128 MiB combined expanded data, and the existing source archive limits.
Duplicate names, path-like or unsafe names, malformed extents, ZIP64, unsupported
compression/features, invalid CRCs, and an absent or mismatched selected BIOS
are rejected. ZIP32 entries may use only the DEFLATE compression-level hint
bits on DEFLATE members; those bits are rejected on stored members. This
allowance applies only to unrelated BIOS archive entries;
the selected game archive still requires the exact 13-member set. The table is
a differential source map and does not claim that this BIOS variant is
compatible with physical hardware.

| Source members | GNMV region | Mapping |
|---|---|---|
| `250-p1.p1`, `250-p2.ep1` | Program | `0x000000`, `0x100000`; adjacent byte swap |
| `250-s1.s1` | Fixed | Copy at `0x00000` |
| `250-m1.m1` | Audio program | Copy at `0x00000` |
| `250-v1.v1`, `250-v2.v2`, `250-v3.v3` | Samples | Concatenate at `0x000000`, `0x400000`, `0x800000` |
| `250-c1.c1` through `250-c6.c6` | Sprites | Three 8 MiB pairs interleaved into even/odd byte lanes |
| `sp-s2.sp1` | BIOS | Adjacent byte swap into a zero-filled `0x80000` region |

The selected source identities are:

| Member | Length | CRC-32 | SHA-1 |
|---|---:|---|---|
| `250-p1.p1` | `0x100000` | `81f1f60b` | `4c19f2e9824e606178ac1c9d4b0516fbaa625035` |
| `250-p2.ep1` | `0x400000` | `1fda2e12` | `18aaa7a3ba8da99f78c430e9be69ccde04bc04d9` |
| `250-s1.s1` | `0x020000` | `fb6f441d` | `2cc392ecde5d5afb28ddbaa1030552b48571dcfb` |
| `250-m1.m1` | `0x020000` | `fd42a842` | `55769bad4860f64ef53a333e0da9e073db483d6a` |
| `250-v1.v1` | `0x400000` | `c79ede73` | `ebfcc67204ff9677cf7972fd5b6b7faabf07280c` |
| `250-v2.v2` | `0x400000` | `ea9aabe1` | `526c42ca9a388f7435569400e2f132e2724c71ff` |
| `250-v3.v3` | `0x200000` | `2ca65102` | `45979d1edb1fc774a415d9386f98d7cb252a2043` |
| `250-c1.c1` | `0x800000` | `09a52c6f` | `c3e8a8ccdac0f8bddc4c3413277626532405fae2` |
| `250-c2.c2` | `0x800000` | `31679821` | `554f600a3aa09c16c13c625299b087a79d0d15c5` |
| `250-c3.c3` | `0x800000` | `fd602019` | `c56646c62387bc1439d46610258c755beb8d7dd8` |
| `250-c4.c4` | `0x800000` | `31354513` | `31be8ea2498001f68ce4b06b8b90acbf2dcab6af` |
| `250-c5.c5` | `0x800000` | `a4b56124` | `d41069856df990a1a99d39fb263c8303389d5475` |
| `250-c6.c6` | `0x800000` | `83e3e69d` | `39be66287696829d243fb71b3fb8b7dc2bc3298f` |
| `sp-s2.sp1` | `0x020000` | `9036d879` | `4f5ed7105b7128794654ce82b51723e16e389543` |

Before transforming a selected source member, the importer validates ZIP32
central/local consistency, CRC, exact expanded length, and the pinned MAME
CRC/SHA-1 identity for every selected member. It rejects unknown game members,
duplicate members, unsupported ZIP features, ambiguous end records, malformed
extents, failed decompression, and identity mismatch. Bounded flat BIOS extras
are fully validated then discarded. It does not extract paths or print archive names, local
paths, hashes, or bytes. A completed bundle is written to a sibling temporary
file and renamed into place only after the full import succeeds.

Resource ceilings are 96 MiB per source ZIP, 128 MiB combined ZIP bytes,
64 entries per archive, 8 MiB per expanded entry, 128 MiB combined expanded
source data, and 64 MiB for the complete GNMV. The command holds both bounded
input archives, one 8 MiB expansion buffer, and the final bundle concurrently;
the bound is below 200 MiB. The canonical mode retains its existing 64 MiB ZIP,
six-entry and 64 MiB output limits. Synthetic expected identities are compiled
only into a temporary test executable and are not an option in the shipping
importer.

The importer rejects ZIP64, multi-disk archives, encrypted entries, data
descriptors, unsupported compression methods, extra ZIP64 fields, unsafe or
ambiguous names, duplicate roles, inconsistent central/local metadata,
overlapping extents, malformed sizes, decompression errors, CRC mismatches, and
profile or resource-limit mismatches. It supports stored members and raw DEFLATE
through the minimal vendored zlib 1.3.2 inflater/CRC source set pinned to commit
`da607da739fa6047df13e66a2af6b8bec7c2a498`; the upstream license is retained in
`third_party/zlib/LICENSE`. zlib is linked only to importer targets, not the
native library or Libretro adapter. The upstream manual documents negative
`windowBits` as raw DEFLATE mode: [zlib inflate API](https://www.zlib.net/manual.html#inflateInit2).

Resource ceilings are profile-scoped: 6 entries, 48 MiB maximum expanded size
per region, 64 MiB maximum ZIP input/compressed bytes, and 64 MiB maximum
normalized payload. The importer holds the caller's archive and one final
normalized output buffer concurrently; it writes inflate output directly into
the bounded bundle and does not allocate a second expanded-member buffer. The
native API additionally owns a copied region set and 64 KiB work RAM after
import, outside the importer process.

## Evidence and current limits

The synthetic test builds public zero-filled region data, imports it, loads it
through the C API, and executes a small 68000 guest that writes a sentinel to
MVS work RAM before STOP. The same normalized bundle is passed directly to
`retro_load_game` with fake Libretro environment callbacks. These tests establish
the versioned contract, copy lifetime, sentinel bus path, and callback seam.
They do not establish real RetroArch content selection or title boot.

The selected MVS bus maps the low `0x000000-0x00007f` vector window, plus the
BIOS at `0xc00000-0xc1ffff` mirrored across `0xc00000-0xcfffff`. BIOS vectors
are selected by default; the observed system-control latch output can select
the one loaded cartridge's vector bytes and can restore BIOS vectors. This is
a single-slot MAME differential, not general slot switching. The bus also
accepts byte writes into work RAM. For the observed
low-address byte-write case only, the current
implementation follows pinned MAME's differential default: `neogeo_main_map`
has a banked-vector read handler at `0x000000-0x00007f` and no low write map;
MAME's `handler_entry_write_unmapped::write` only logs and drops the write
([`neogeo.cpp` lines 1689-1699](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp#L1689-L1699),
[`neogeo.cpp` lines 1722-1736](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp#L1722-L1736),
[`emumem_heun.cpp` lines 62-72](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/emumem_heun.cpp#L62-L72)). A versioned local observation counts these dropped byte writes explicitly as MAME-differential behavior. This does not establish physical-board semantics or justify dropping other unmapped access widths.

| Claim | Evidence class | Current result |
|---|---|---|
| Region sizes and declared load transforms | Pinned MAME source metadata | Reproducible implementation reference; emulator-derived, not hardware truth |
| Normalized role bundle parse, program byte transform, and API ownership | Synthetic automated test | Passed at the current revision |
| Selected MVS BIOS mirror and low unmapped byte-write differential | Pinned MAME map/default-handler source plus synthetic boundary, no-op, and wrong-window tests | Emulator differential only; physical hardware behavior remains unknown |
| ZIP32 stored/DEFLATE validation and error taxonomy | Public synthetic archive tests | Passed at the current revision; hostile-input review remains required |
| Selected private BIOS/media identity | Local-only evidence | Unqualified; identity is not checked and no private identifier is published |
| Guest reaches Metal Slug X attract/start | Guest execution | Not established; GAME-02 remains Pending |
| Actual pinned RetroArch GUI behavior | Direct app observation | Manual-only/unknown; callback tests do not close it |
| Physical MVS/AES behavior | Hardware observation | Not established |

The local wrapper identifies the game and BIOS archives by exact public member
content and identity, requires exactly one pair, invokes the selected importer
once, and passes its normalized output to the native qualification runner. It
writes generic statuses plus the first unsupported event's diagnostic fields to
the ignored report; computed local identities and archive values never enter
tracked output. Its first unsupported guest
event is a handoff to the following phase plan, not title-boot evidence.

On budget exhaustion, the ignored local report may also include a bounded fetch
ring and sanitized per-chunk profile: stable chunks, output/latch, video and
bank-state transition chunks, watchdog pets/resets, and whether the final chunk
boundary repeated. These are coarse observation aids, not exact write counts
or an attract/start predicate. The current selected run is capped at 256 chunks
of 1,000,000 requested cycles each; reaching that bound remains an unknown
outcome, never a successful boot result.

The selected MVS boot profile includes only event-driven owned 68000 operations
that have pinned evidence and synthetic boundary controls. It supports
`MOVE.B Dn,(xxx).L` (12 clocks), `MOVE.B #<data>,(xxx).L` (20 clocks),
`MOVE.W #<data>,(xxx).L` (20 clocks), and `MOVE.W #<data>,Dn` (8 clocks), from
NXP/Motorola *M68000 User's Manual*, Table 9-2, printed p. 9-3. Absolute-long
stores use the required bus width; odd word destinations take the address-error
path. The immediate-to-Dn form preserves the upper half of the destination,
updates N/Z/V/C, and preserves X. BSR.W (18 clocks), JSR PC-displacement only
(18 clocks), RTS (16 clocks), and LEA absolute-long (12 clocks) are also covered
by their cited manual timing rows. JSR pushes the address after its extension
word and computes the PC-relative target from the extension-word address
(Motorola *M68000 Family Programmer's Reference Manual*, §4 JSR p. 4-109 and
§2.2.11 p. 2-13). Other JSR effective-address forms remain unsupported.
`MOVEM.L (An)+` to the selected register list is limited to memory-to-register
postincrement: register-mask order is D0–D7 then A0–A7, the address register
advances by four bytes per loaded register, and a listed base register receives
the final incremented address (User's Manual Table 8-10, p. 8-8; Programmer's
Reference Manual §4 MOVEM, pp. 4-128–4-129). `MOVEA.L (An)+,An` is also covered
at 14 clocks (3 reads, no writes; User's Manual Table 8-3, p. 8-4; Programmer's
Reference Manual §4 MOVEA, pp. 4-119–4-120): it loads the full 32-bit address
register, increments the source by four, and leaves condition codes unchanged.
For a source/destination register alias, the loaded value supersedes the
postincrement. Other MOVEM widths/addressing modes and neighboring MOVEA forms
remain unsupported. `MOVEA.L An,An` is supported for direct address-register
transfers (4 clocks, 1 read, 0 writes; User's Manual Table 8-3, p. 8-3). It
copies all 32 bits without changing flags, including the source/destination
alias case; neighboring `MOVE.L An,Dn` remains unsupported. These are bounded
CPU semantics, not title-boot evidence. `MOVE.W Dn,Dn` is supported for direct
data-register transfers at 4 clocks (1 read, 0 writes; User's Manual Table 9-2,
p. 9-3). It replaces only the destination's low word, sets N/Z/V/C from that
word, and preserves X and the upper destination word. Byte and other EA forms
remain unsupported. `MOVE.B Dn,(An)` is supported as an explicit byte bus write
at 8 clocks (1 read, 1 write; User's Manual Table 9-2, p. 9-3). It updates
N/Z/V/C from the source's low byte, preserves X, and leaves adjacent memory
bytes untouched. Other byte addressing modes remain unsupported.
`MOVE.W Dn,(An)+` performs a word store and advances An by two at 8 clocks
(1 read, 1 write; User's Manual Table 9-2, p. 9-3); it updates N/Z/V/C while
preserving X. An odd destination follows the 68000 address-error path before
the target write. Only the displacement destination forms documented below are
additionally supported; other word addressing forms remain unsupported.
`MOVE.W Dn,(An)` stores the low source word at the selected address register in
8 clocks (1 read, 1 write; User's Manual Table 9-2, p. 9-3), updates N/Z/V/C,
preserves X and the source register, and takes the address-error path for an
odd destination.
`DBF Dn` (`DBRA`) supports its word displacement form only: it decrements the
counter's low word, preserves the upper word and condition codes, and branches
relative to the address after the opcode unless the result is `0xffff`
(Motorola *M68000 Family Programmer's Reference Manual* §4 DBcc, pp. 4-90–4-91).
The taken path costs 10 clocks/2 reads; the expired path costs 16 clocks/3 reads
(User's Manual Table 9-15, p. 9-10). Other DBcc conditions remain unsupported.
`MOVE.W (An),Dn` is supported for direct-indirect word loads at 8 clocks
(2 reads, 0 writes; User's Manual Table 9-2, p. 9-3). It preserves the
destination's upper word, updates N/Z/V/C, preserves X, and takes the address
error path on an odd source. Other load addressing modes remain unsupported.
`MOVE.W #<data>,(d16,An)` costs 16 clocks (3 reads, 1 write), and
`MOVE.W Dn,(d16,An)` costs 12 clocks (2 reads, 1 write), as listed in Table 9-2,
printed p. 9-3. Both update N/Z/V/C while preserving X; odd word destinations
take the 68000 address-error path. Other destination forms remain unsupported.
Unsupported encodings and addressing modes remain faults. These CPU semantics
are source-backed; the selected guest still has not reached attract/start.

The selected profile also routes the observed reserved `EORI.B` and `EORI.L`
destination encodings to MC68000 illegal-instruction vector 4. The handler
stacks the pre-instruction PC and old SR in the short exception frame, enters
supervisor mode, and fetches vector offset `0x10`. The 62-clock cost follows
the MC68000 *M68000 User's Manual*, Rev. 9.1, §6.3.6, Table 6-2 (printed p. 6-7)
and Table 7-15 (printed p. 7-11). Other unsupported encodings remain
fail-closed; this exception slice does not imply general exception coverage.
Reset, interrupt, and address-error events use the same MC68000 timing table:
64, 72, and 94 clocks respectively. The separately modeled MVS watchdog reset
is a board event and does not use the CPU RESET-instruction timing.

The MVS profile also models the pinned MAME watchdog reset window at
`0x300001` and its mirror, using MAME's 3,244,030 master-tick interval at 24 MHz
(1,622,015 main-CPU cycles at 12 MHz). A write pets the timer; expiry performs a
CPU soft reset while preserving work RAM. Accounting occurs at instruction
boundaries, so the reset observation has that deterministic granularity. The
source is MAME differential evidence, not physical-board proof. The profile also
records the observed cartridge-audio source-select latch bit without claiming
audio CPU, sound handshake, fixed-layer or audio-bank behavior. Video register
video-register indexes 0-2 implement the pinned MAME VRAM offset, data, and
modulo registers. The selected profile allocates zeroed per-instance VRAM and
tracks the data read buffer; index 1 writes one word, advances the offset by the
configured modulo while preserving the extended-bank bit, and refreshes the
read buffer. Offset normalization is applied again after increment, including the
0x87ff extended-bank limit. These VRAM latches persist across CPU reset as in
MAME `device_reset`; newly loaded images start from zeroed state. The synthetic
guest test checks write/readback, modulo advance, and the upper bound.
This is MAME-differential storage only; rendering, timing of sprite consumption,
and physical-board equivalence are not claimed. Source: pinned MAME
`neogeo_v.cpp` `video_register_w`/`video_register_r` and `neogeo_spr.cpp`
`set_videoram_offset`, `set_videoram_data`, and `set_videoram_modulo` (revision
`31e52312c59e4d60d70235118bcbccd220f5232e`). Interrupt acknowledgement is a zero-
pending MAME differential only; no interrupt producer is modeled. The observed
two-channel coin-lockout state is tracked per instance from MAME's I/O callback;
coin-counter events remain unsupported and no physical coin-output claim is
made. System-latch output 6 records the save-RAM write-enable bit and gates a
zero-initialized, per-instance 64 KiB backing region. This follows pinned MAME
revision `31e52312c59e4d60d70235118bcbccd220f5232e`: `set_save_ram_unlock`
sets the bit and `save_ram_w` ignores writes while locked
([neogeo.cpp lines 1043-1052](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp#L1043-L1052);
map at lines 1735-1736). The state is exposed through MVS bus observation v14.
This is volatile emulation state only; save persistence and NVRAM compatibility
are not implemented or claimed. System-latch output 7 tracks the palette-bank
select bit from pinned MAME `neogeo_base_state::set_palette_bank`, which selects
bank `0x1000` or `0` and calls `set_pens` ([neogeo_v.cpp lines 82-85](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp#L82-L85)).
The profile models the two 4K-word palette RAM banks and mirrored byte/word
accesses from `paletteram_r`/`paletteram_w` and the pinned main map
([neogeo_v.cpp lines 89-110](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp#L89-L110);
[neogeo.cpp lines 1722-1736](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp#L1722-L1736)).
This is MAME-differential storage only: color conversion, pens, sprite-generator
consumption and rendering are not modeled. Video-register index 2 is backed by
`video_register_w`/`video_register_r` in the same pinned source
([neogeo_v.cpp lines 228-269](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp#L228-L269)).
The per-instance bus observation contract is version 14. A later unsupported
guest event still stops qualification, so no title-boot result is claimed.

The local qualification command must keep inputs under ignored `local/roms/`,
write only ignored `local/qualification/phase05.json`, and emit only bounded
generic statuses plus the first unsupported guest event. Never put private
media identities, paths, bytes, or derived data in tracked outputs.
