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

`GNMV` contains a 16-byte big-endian header (`GNMV`, bundle version, profile
identifier, role count), followed by six 12-byte role/64-bit-length descriptors
and the region bytes. The native API consumes only this normalized in-memory
representation. The Libretro adapter recognizes the bundle magic, bounds each
descriptor against the supplied content span, copies the media via the native
API, and does not link the archive decoder.

The standalone C17 `mvs_importer` currently accepts a closed ZIP32 subset with
one canonical role member per profile region: `bios.bin`, `program.bin`,
`fixed.bin`, `audio.bin`, `samples.bin`, and `sprites.bin`. These member payloads
must have the exact profile lengths. The `program.bin` member uses MAME's
`ROM_LOAD16_WORD_SWAP` source ordering; the importer validates its source CRC,
then swaps adjacent bytes into bus order in the resulting GNMV bundle. Other
members are copied in the selected synthetic fixture's mapped order. The
importer does not extract paths, modify the input archive, or expose member
names in diagnostics. This narrow synthetic contract has stored-entry and
DEFLATE coverage; it is not yet proof that an unmodified commercial game
archive and a separate BIOS archive can be loaded directly. MEDIA-03 therefore
remains Pending until the documented local import/load path is directly
qualified, and the selected private compatibility result remains private.

The role names, lengths, and program transform are a structural profile only.
The importer does not authenticate cartridge or BIOS revision content against
public checksums or a local allowlist. The selected content identity therefore
remains unqualified, and no selected-profile compatibility claim is made.

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

| Claim | Evidence class | Current result |
|---|---|---|
| Region sizes and declared load transforms | Pinned MAME source metadata | Reproducible implementation reference; emulator-derived, not hardware truth |
| Normalized role bundle parse, program byte transform, and API ownership | Synthetic automated test | Passed at the current revision |
| ZIP32 stored/DEFLATE validation and error taxonomy | Public synthetic archive tests | Passed at the current revision; hostile-input review remains required |
| Selected private BIOS/media identity | Local-only evidence | Unqualified; identity is not checked and no private identifier is published |
| Guest reaches Metal Slug X attract/start | Guest execution | Not established; GAME-02 remains Pending |
| Actual pinned RetroArch GUI behavior | Direct app observation | Manual-only/unknown; callback tests do not close it |
| Physical MVS/AES behavior | Hardware observation | Not established |

The local qualification command must keep inputs under ignored `local/roms/`,
write only ignored `local/qualification/phase05.json`, and emit only bounded
generic statuses plus the first unsupported guest event. Never put private
media identities, paths, bytes, or derived data in tracked outputs.
