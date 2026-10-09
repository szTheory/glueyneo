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

The standalone C17 `mvs_importer` retains the canonical six-role ZIP32 mode and
adds a selected-source mode:

```text
mvs_importer --selected game.zip bios.zip output.gnmv
```

The selected mode accepts exactly one `mslugx` game archive and a separate
BIOS archive. Its fixed member table pins all 13 game members and the selected
Europe MVS v2 BIOS (`sp-s2.sp1`) to the CRC/SHA-1 values in the MAME source
revision above. The game archive cannot contain extra members. The BIOS archive
may contain only the documented `NEOGEO_BIOS` catalog names; exactly one
`sp-s2.sp1` member is selected, and other catalog members are validated and
ignored. The table is a differential source map and does not claim that this
BIOS variant is compatible with physical hardware.

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
CRC/SHA-1 identity. It rejects unknown or duplicate members, unsupported ZIP
features, ambiguous end records, malformed extents, failed decompression, and
identity mismatch. It does not extract paths or print archive names, local
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

| Claim | Evidence class | Current result |
|---|---|---|
| Region sizes and declared load transforms | Pinned MAME source metadata | Reproducible implementation reference; emulator-derived, not hardware truth |
| Normalized role bundle parse, program byte transform, and API ownership | Synthetic automated test | Passed at the current revision |
| ZIP32 stored/DEFLATE validation and error taxonomy | Public synthetic archive tests | Passed at the current revision; hostile-input review remains required |
| Selected private BIOS/media identity | Local-only evidence | Unqualified; identity is not checked and no private identifier is published |
| Guest reaches Metal Slug X attract/start | Guest execution | Not established; GAME-02 remains Pending |
| Actual pinned RetroArch GUI behavior | Direct app observation | Manual-only/unknown; callback tests do not close it |
| Physical MVS/AES behavior | Hardware observation | Not established |

The local wrapper identifies the game and BIOS archives by exact public member
content and identity, requires exactly one pair, invokes the selected importer
once, and passes its normalized output to the native qualification runner. It
writes only generic statuses to the ignored report; computed local identities
and archive values never enter tracked output. Its first unsupported guest
event is a handoff to the following phase plan, not title-boot evidence.

The local qualification command must keep inputs under ignored `local/roms/`,
write only ignored `local/qualification/phase05.json`, and emit only bounded
generic statuses plus the first unsupported guest event. Never put private
media identities, paths, bytes, or derived data in tracked outputs.
