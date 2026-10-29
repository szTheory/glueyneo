# Selected MVS media contract

This document describes the current bounded `GNMV` version-3 zoom-table
role-bundle, with explicit version-1/version-2 compatibility, and the public
MAME metadata used for the selected Metal Slug X
profile. Metadata alone does not establish boot or original-hardware behavior;
the actual bounded qualification scope below is separate from that source map.

## Current bounded qualification scope

Phase05 accepted the selected private import/boot/title path; Phase06 accepted
first-character Mission1 opening control and composition. Phase07 machine checks
now add native caller-owned PCM and actual pinned RetroArch1.22.2 recording,
initialized route and causal music/fire/release evidence for that same bounded
scene. Four audio roles pass strict current-source replay and common-input-history
checks; ten fresh visual roles/60 bound captures pass all eight visual predicates.
The final custom collection explicitly revalidates previously acquired actual
audio before fresh visual acquisition, rather than claiming a single new
fourteen-window recording. Exact private media/configuration/output identities
remain local. A separate bound normal-route session supplies the user's
confirmation of recognizable music and firing effects; see
[Phase07 UAT](../.planning/milestones/ws-first-playable-game-2026-10-24/phases/07-sound-and-scenario-qualification/07-UAT.md).
This observation does not establish performance or broader compatibility.

The public original sound guest separately exercises SSG and ADPCM-B through
native/libretro and relocated static/shared C consumers. It does not qualify FM,
ADPCM-A, arbitrary BIOS, later gameplay, raster/electrical accuracy or full-game
compatibility. Source clock/cycle behavior and modeled original slowdown are
preserved; host pacing and development latency are separate. See
[audio-contract.md](audio-contract.md) for capacity, conversion, ownership,
fixture/family coverage, stage-specific evidence and the separate listening observation.
Older implementation and failed-run accounts below remain historical provenance;
this section owns current scope.

## Public profile map

The profile uses MAME `mslugx` at commit
[`31e52312c59e4d60d70235118bcbccd220f5232e`](https://github.com/mamedev/mame/tree/31e52312c59e4d60d70235118bcbccd220f5232e).
The public `ROM_START(mslugx)` declaration specifies these mapped regions:

| Role | MAME region | Mapped bytes | Public layout evidence |
|---|---|---:|---|
| BIOS | `mainbios` | `0x80000` | `NEOGEO_BIOS` region; selected local BIOS identity stays private; broader firmware support is unqualified |
| Program | `cslot1:maincpu` | `0x500000` | P1 and P2 use `ROM_LOAD16_WORD_SWAP` |
| Fixed | `cslot1:fixed` | `0x20000` | `NEO_SFIX_128K` |
| Audio program | `cslot1:audiocpu` | `0x20000` | `NEO_BIOS_AUDIO_128K` |
| Samples | `cslot1:ymsnd:adpcma` | `0xa00000` | Three contiguous sample loads: 4 MiB, 4 MiB, 2 MiB |
| Sprites | `cslot1:sprites` | `0x3000000` | Six 8 MiB `ROM_LOAD16_BYTE` lanes, interleaved in pairs |
| Audio BIOS (v2) | `audiobios` | `0x20000` | Separate SM1 source in `NEO_BIOS_AUDIO_128K`; S25t |
| Y-zoom lookup (v3) | `spritegen:zoomy` | `0x20000` | Separate `000-lo.lo` board-data region; S38/S38a/S38b |

The v1 normalized region payload is `0x3fc0000` bytes (63.75 MiB); v2 with
audio BIOS is `0x3fe0000` bytes (63.875 MiB); v3 without/with audio BIOS is
`0x3fe0000`/`0x4000000` bytes (63.875/64 MiB). These
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

`GN_MVS_MANIFEST_VERSION` and `gn_mvs_manifest` retain the v1/v2 contract and
seven-entry layout. `gn_load_mvs` accepts v2/count7 or legacy v1/count6 and
keeps those paths unchanged. The additive `gn_mvs_manifest_v3` and
`gn_load_mvs_v3` use an eight-entry descriptor array for GNMV v3. V3 requires
roles 1-6 and role 8 (Y-zoom lookup); role 7 (audio BIOS) is optional. Both
loaders validate role uniqueness, exact role sizes, resource limits and byte
layout, then own their copies. A candidate image is initialized before it
replaces the previous image. A rejected candidate leaves the current image
intact.

The native v1 prefix remains loadable, but its absent audio BIOS cannot supply
the reset-selected source. The Libretro loader rejects a structurally valid v1
bundle with a bounded `missing audio BIOS` log before creating an instance; the
qualifier emits `missing_audio_region` without running the guest. A subsequent
valid v2 load still succeeds. The pinned reset path resumes the clocked Z80 at
PC zero (S25r-S25w); no main-CPU-controlled reset hold is wired in that source.
This is emulator differential evidence, not a measured physical reset sequence.

`gn_observe_mvs_bus_fault` takes the writable observation-buffer size and copies
no more than that size. The stable prefix through `valid` is required; appended
fields are returned only when included in the caller's size. This is a new,
pre-release diagnostic API with no legacy binary callers at the base revision;
the function signature and prefix are now fixed for size-aware evolution, while
the observation `version` identifies the full set of fields the library knows.

`GNMV` contains a 16-byte big-endian header (`GNMV`, bundle version, profile
identifier, role count), followed by eight (v3), seven (v2) or six (v1)
12-byte role/64-bit-length descriptors and the region bytes. The native API consumes only this normalized in-memory
representation. The Libretro adapter recognizes the bundle magic, bounds each
descriptor against the supplied content span, copies the media via the native
API, and does not link the archive decoder.

The standalone C17 `mvs_importer` retains the canonical ZIP32 role mode (six legacy roles plus optional `audio-bios.bin`) and
adds a selected-source mode:

```text
mvs_importer --selected game.zip bios.zip output.gnmv
```

Every rejection returns a distinct exit code and generic message, listed with
the cause and the user action in
[MVS import and load errors](ownership-and-errors.md#mvs-import-and-load-errors);
the Libretro adapter's load and rejection log lines are documented there too.

The selected mode accepts exactly one `mslugx` game archive and a separate
board/BIOS archive. Its fixed member table pins all 13 game members and the
selected Europe MVS BIOS (`sp-s2.sp1`) to the CRC/SHA-1 values in the MAME source
revision above. The game archive cannot contain extra members. The BIOS archive
must contain exactly one `sp-s2.sp1` member. Optional `sm1.sm1` is admitted only
at the exact public length/CRC/SHA-1 below and becomes role 7 in v2/v3. The
optional `000-lo.lo` board zoom table is accepted only at its pinned exact
length/CRC/SHA-1 and becomes role 8 in v3. If that table is absent, the importer
preserves the legacy v2 format when audio BIOS is present or v1 otherwise; it
never synthesizes a lookup table. Fractional-Y rendering is unavailable for
those legacy bundles. A mismatched optional member is rejected, never ignored
or replaced. Other entries may have flat safe
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
| `sm1.sm1` (optional) | Audio BIOS, role 7 | Exact `0x20000` copy; never synthesized |
| `000-lo.lo` (optional) | Y-zoom lookup, role 8 | Exact `0x20000` copy; never synthesized |

The selected source identities are:

The optional audio BIOS pin is transcribed from the immutable
[`NEO_BIOS_AUDIO_128K` declaration](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp).
It is public metadata, not a locally derived identity or a redistribution grant.
The optional zoom-table pin comes from `ROM_Y_ZOOM` at the same immutable
source revision. The role is board data used by the video renderer, not a
title-owned asset. The table contents are not copied into tests or source.

| Member | Length | CRC-32 | SHA-1 |
|---|---:|---|---|
| `sm1.sm1` (optional) | `0x020000` | `94416d67` | `42f9d7ddd6c0931fd64226a60dc73602b2819dcf` |
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
seven-entry and 64 MiB output limits. Synthetic expected identities are compiled
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

## Load the selected MVS media in RetroArch: input and frames

For a loaded GNMV profile, each `retro_run` samples joypad Select as coin 1 and
joypad Start as P1 Start, updates the instance input mask, and runs one nominal
MVS frame budget of 202,752 68000 clocks from "Interrupts and timing". The
adapter then sends the same guest-derived 320x224 XRGB8888 frame produced by
the private native renderer. If guest execution or rendering fails, the
adapter submits a freshly initialized blank frame so an earlier image cannot
remain visible. Synthetic callback tests compare native and adapter pixels at
matching input/timing boundaries; this does not establish selected-media title
output or RetroArch presentation.
The generic log line `glueyneo: MVS P1 start indication observed` is emitted
once per load after the native observer reports a guest PLAYER_START fetch
following the accepted attract entry and ordered coin/start input edges, with
a fresh BIOS-written P1 `BIOS_START_FLAG` indication (S29b). An unindicated
title-timeout transfer does not emit this line. This is the documented BIOS P1
Start protocol indication, not proof that the game accepted the start or that
credits were deducted after return. A local headless qualification may render
the frame at this BIOS-to-cartridge boundary, or use the bounded
`--video-advance-frames 1..600` option to inspect a later no-input state. Its
unique PPM remains under ignored `local/qualification` and is not copied to
reports or tests. The local report preserves the requested count and the number
of complete guest frames actually run after the checkpoint; an early stop or
fault keeps its status and records the completed count separately. It marks
`frame_output_written` only after the invocation-matched PPM is fully saved.
Neither the BIOS protocol predicate nor a nonblack frame alone establishes a
rendered title. GNFX continues using its existing 200,000-cycle fixture frame
path. The current local acceptance run through pinned RetroArch 1.22.2 passed
selected import, native guest execution, actual frontend loading and orderly
exit, recognizable title, and exact local identity checks. The software frame
is 320x224. Capture waits for the 720-successful-video-callback checkpoint;
the exact screenshot frame remains unmeasured beyond that lower bound.
The earlier all-black captures, screenshot conversion crash, and the second
debug run's OCR `unknown` remain preserved as historical outcomes. They are
distinct from this current, invocation-bound acceptance result. A separate
native qualification produced a recognizable selected-title frame; native and
frontend observations establish separate claims. The maintained local review
validator resolves only residual
`recognizable_title=unknown` when every other machine predicate passes; it
cannot override an explicit black-frame/title failure. Captures and the bound
local reports remain under ignored `local/qualification`. This evidence does
not establish active gameplay, later stability, or sound output. The native
qualifier's 600-frame boundary includes its BIOS checkpoint prelude; the
frontend screenshot has only the successful-video lower bound, so the two are
not claimed as the same emulated state. Plan 05-04 execution is complete;
the separate named Phase 05 verification/UAT step accepted that bounded boot
scope on 2026-10-20. Phase 06 active control remains a separate claim.

Phase 06 adds a bounded active-scene calibration path. After the existing
ordinary coin/start prelude observes the BIOS P1-start indication, frame zero
is the first requested active frame. `mvs_qualify` accepts up to 3,600 active
frames, 64 ordered full-mask input events in `FRAME:0xMASK` form, and six
strictly ordered capture indices. Requested and completed frames/captures are
reported separately; captures are written only after successful frame
execution to the validated ignored
`local/qualification/phase06/run-<32 lowercase hex>/frame-NNNN.ppm` directory.
The maintained wrapper's `--active-scene calibrate --scene-contract
local/qualification/phase06-contract.json` command records bounded exploratory
images and exact local identities. Calibration leaves `frozen` false and T0
unresolved; native/frontend acceptance requires a separately frozen contract.
Use `--active-capture-frames F0,F1,F2,F3,F4,F5` to select six ascending
checkpoints within that horizon without changing runtime code. The wrapper
binds the selected indices to the configuration, native report and saved
images, and rejects malformed or out-of-range windows before guest execution.
A BIOS start indication or calibration capture does not establish active play.
The native acceptance contract binds the evaluator source as well as the
importer, native qualifier, media and configuration. All fresh action/control
pairs must share the same starting pixels and recorded entry inputs. Movement
uses tracked actor features, allowing a facing reflection; the reserved firing
region cannot supply the actor component. Projectile travel must be separated
from that actor, differ from the matched omitted-fire control and disappear in
post-release observations. Scrolling requires coherent horizontal translation
of a textured region disjoint from the actor, rather than changed-pixel counts.
Palette and overlap checks use cropped RGB references selected and reviewed
during calibration, before fresh acceptance. These private scene regression
references do not establish original-hardware truth. Missing or ambiguous
evidence remains a non-pass, and native evidence does not establish actual
frontend control.

The Phase 06 frontend collector uses an explicitly opted-in
`GLUEYNEO_MVS_INPUT_OBSERVATIONS=ON` core in a separate local build directory;
ordinary builds disable it. Fixed numeric `B/S/V/R/P/X` records identify an
epoch begin, applied complete input-mask change, successful video callback,
attract readiness, P1-start indication and exhausted allowance. Sample sequence
advances on every input poll. Executed clocks are the cumulative actual clocks
returned by the native runner, including any failed execution prefix; failed
execution/rendering never produces successful-video evidence. The adapter emits
at most 256 records per content/reset epoch. The collector rejects a second
begin, limits the whole invocation to 256 records and 12 KiB of protocol data,
and bounds unrelated log scanning separately. Diagnostics contain no guest
memory, paths, media identities or pixel payloads.

For software screenshots, a diagnostic-only RetroPad L3 request increases video
observations to every second successful callback. L3 never enters the emulated
Neo Geo mask, and default builds do not query it. The host preserves the
observations before F8 and after a fresh bounded PNG byte snapshot. It checks
no-follow regular-file identity before/after reading, chunk framing/CRCs and
exact IEND/EOF, then copies and hashes owned bytes under a unique local name.
This constrained check targets the pinned writer; it does not acknowledge
completion of RetroArch's asynchronous screenshot task. Full pixel decoding
and the retained hash are checked after clean exit. The host waits for
observed key release before retrying.
Capture intervals exclude later cleanup callbacks; their submitted frame is
unknown. Actual action/control intervals must overlap, each span at most twelve
callbacks, their union span at most sixteen, and each lie fully before, within
or after the actual observed action/release window as appropriate. Wider,
misaligned or partial intervals cannot establish the pixel predicates.

The active frontend lane continuously drains the owned child's stderr into a
16 MiB capped log and discards mirrored stdout. Overflow is latched separately
from observation parsing and remains a failure after an early child exit.
Retention copies bounded prefixes in chunks; it cannot read or duplicate an
oversized log wholesale. A coincident output failure is recorded alongside the
original failure reason and process readbacks.
RetroArch 1.22.2's macOS logger mirrors to buffered stdout and also flushes its
configured stream; combining those channels duplicates earlier records
([pinned logging implementation](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/verbosity.c#L287-L326)).
Retained stderr remains ignored. The collector rejects unexpected sampled masks,
runtime failures, repeated begin records, truncated/reordered data and early
exit. Input posting alone never establishes guest response. This lane has a
120-second invocation deadline and an independent 8,192-total-frontend-frame
safety cap; its requested active horizon and capture bounds remain separate.
Automatic content patches and durable save loading/writing are disabled in
this fresh temporary frontend configuration. Exit-time config saving is also
disabled; exact launch bytes/hash are retained and any change detected after
clean exit invalidates the invocation. Startup asset extraction is also disabled:
the pinned frontend's [extraction completion callback](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/menu/menu_driver.c#L3718-L3749)
saves the config independently of the exit-save setting. Explicit playlist and
built-in history/favorites directories prevent [legacy path migration](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/configuration.c#L4162-L4257)
from replacing a history-file-only request. The runner validates all requested
destinations against its owned temporary and capture roots before path
canonicalization; this is launch-contract validation, separate from the retained
local effective-setting diagnostic.

Active keyboard presses use the live owned child PID and check foreground
ownership. A different foreground PID triggers reacquisition and held-key
reassertion; failed readback or acquisition is an explicit non-pass. Screenshot
presses and all releases use the same owned target. Sampled-mask and capture
interval checks still decide whether the invocation provides useful evidence;
focus recovery alone cannot establish a scene predicate. These host mechanisms
are exercised in the pinned macOS lane only.

The current native scene proof and frontend calibration cover the first
character on foot at the opening of Mission1, through horizontal movement,
firing away from melee, release, combined direction/fire and a short sustained
camera/background-scroll segment. Under Classic mapping, RetroPad B drives
Neo Geo A, observed as firing in this segment; other title-specific A–D action
labels remain unqualified. Native player/scenery/projectile/HUD composition,
transparency/overlap and palette landmarks retain separately reviewed references
and original guest regressions. Frontend composition establishes correlated
pixel transfer at an admitted replay submission, as described below.
The logical frame cadence follows the source-qualified MVS model documented
below; host pacing is separate, and no speed correction removes modeled guest
slowdown. Snapshot composition does not establish arbitrary mid-scanline or
raster-effect accuracy, analog RGB correctness, performance, or full-game
compatibility. Phase07 machine sound outcomes now pass in this bounded scene;
the separate user listening observation confirms recognizable music and firing,
as scoped above; host pacing/performance remain unqualified.

Earlier current-source campaigns passed selected causal predicates but failed
exact composition references; their reports remain preserved. The subsequent
current strict-equivalent producer run completed ten frontend roles and sixty
captures with replay, sampled-input, configuration and temporal bindings valid.
The private receipt validator confirms all eight original predicates and the
aggregate pass. Criteria, regions, schedules and thresholds were unchanged. This
is bounded evidence for the selected first-character on-foot opening Mission1
scene: horizontal movement, firing away from melee, release, combined
direction/fire and a short sustained camera/background-scroll segment. It does
not establish general stability, physical-board truth, analog RGB accuracy,
performance or full-game compatibility. The successful-video callback bounds
leave exact screenshot frames unresolved. Named Phase06 verification remains
pending.

### Replay-bound frontend composition

The frontend policy `sampled_input_rgb_replay_v1` retains actual keyboard inputs
and screenshots. After each clean frontend invocation, an isolated bounded
consumer loads the identical core and normalized media, applies every recorded
sampled-input transition at its actual sample sequence, and generates every
submitted frame in each admitted screenshot interval. The complete decoded RGB
must equal at least one submission in that interval. Every matching sequence is
recorded; repeated identical frames do not establish a unique actual phase.
Pixels outside earlier reference crops are included. Missing candidates, wrong
geometry/format/pitch, callback errors and incomplete input history cannot pass.

Replay is correlated transfer evidence: it uses the same renderer. Native exact
composition/palette references and original guest overlap/transparency
regressions continue to own renderer correctness. The actual frontend mapping,
scene anchors, movement, projectile, release, combined-input and scrolling
predicates remain mandatory at their existing regions and thresholds. A shared
renderer defect can agree with replay and still fail the independent native
composition checks; replay alone cannot establish correct layers or hardware
truth.

This policy replaces the previous frontend fixed nominal-target crop digests,
not the native composition contract. The inspected retained pair demonstrated
both earlier setup-input variation and asynchronous capture variation. Equal
active origins or later masks did not establish equal complete input history.
The earlier failed calibrations/contracts remain failed and preserved; there is
no fourth golden or relaxed RGB tolerance. Core, media, configuration, complete
history, capture and helper-source identities bind each replay receipt. Any
relevant identity change requires fresh evidence.

`--active-scene frontend --active-frontend-calibrate` records frontend-specific
capture windows in the canonical ignored scene contract. A translated schedule
must preserve the native entry inputs, complete action/control mask sequences,
model clocks, horizon and selected T0; captures remain within the native
endpoint. It carries the exact originating native schedule identity. Changing
that native schedule invalidates the translation. The explicit
`same_controls_bounded_retiming_v1` policy permits at most 64 callbacks of
event-position or hold-duration difference from the native schedule. This
execution deviation accommodates F8 completion and observed release between
captures; replaying adjacent native capture/action indices cannot provide that
host synchronization. It does not change the native schedule or establish
equal response latency across consumers. Pixel thresholds and regions
are inherited, not weakened to accommodate screenshots. Calibration leaves
frontend acceptance unfrozen. An exact-capture local review supplies the
semantic outcome;
`--active-frontend-freeze PRIVATE_REVIEW` validates the explicit replay policy,
current identities, all causal predicates and bound replay receipts for all ten
complete calibration invocations before freezing. Legacy fixed-crop receipts
cannot freeze or qualify under this policy.
`--active-scene frontend` then requires ten fresh actual application
invocations and every required predicate. Native and callback tests cannot
substitute for those frontend results. Current execution and any unresolved
outcomes are recorded in the active phase artifacts; this tooling description
does not itself claim frontend gameplay acceptance.

The owned 68000 subset also contains the source-qualified register-direct
`ABCD.B Dm,Dn` form for valid packed-BCD operands; its overlapping predecrement
memory form remains unsupported. This CPU coverage does not qualify the selected
scene, input labels, or gameplay response.

For a focused local video diagnosis, invoke `mvs_qualify` directly with
`--video-state-diagnostic` alongside `--frame-output`. It writes aggregate
guest-written VRAM/palette counts, visible sprite/zoom counts, and currently
modeled video registers to standard error; the private getter returns no guest
bytes or pixels and does not advance emulated time. The diagnostic is not
included in qualification reports or the public ABI.

The local `mvs_qualify` command can accept the bounded diagnostic option
`--input-script coin@<frame>,start@<frame>` after the normalized bundle path.
Frames are counted from the accepted attract/start checkpoint, must be between
1 and 1200, and the coin frame must precede the start frame. Each scheduled frame
uses the same nominal 202,752-clock budget as the adapter. The diagnostic runner
holds Coin for up to eight scheduled frames from its selected frame, then
releases it; P1 Start stays held from its selected frame until the BIOS P1-start
indication or bounded script end. This lets a delayed guest poll observe Coin
while allowing guest credit/debounce logic to progress after release. The
bounded host-line schedule does not claim a physical coin pulse, credit count,
or repeated-credit behavior. The local wrapper's
`--scripted-start` option uses the fixed schedule `coin@1,start@600`; its public
`input_response` field uses `observed` or `not_observed` for that same bounded
BIOS P1 Start protocol indication. `observed` requires the semantic flag and
transfer; ordered host edges or input-register reads alone do not qualify. The
requested local frame is written at either scripted outcome, including
`not_observed`; output failure is reported instead of silently dropping it. A
stale or failed qualifier build stops before selected-media import or guest
execution. This is a synthetic/local aid and makes no claim about selected
private media unless a separately authorized run is recorded.

When a bounded active-frame request follows the script but the semantic BIOS
P1 indication was not observed, the runner reports
`start_input_not_observed`, zero completed active frames, and no captures. Its
local diagnostic also distinguishes `player_start_entered` from
`p1_start_indication` and includes `watchdog_pets`, `watchdog_resets`, and the
bounded stall diagnosis. These fields explain the no-response outcome; they do
not establish an active scene.

The selected MVS bus maps the low `0x000000-0x00007f` vector window, the
cartridge P1 fixed window described below, plus the
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

The cartridge P1 fixed window maps `0x000080-0x0fffff` as read-only cartridge
program bytes at the same offset, so the BIOS can read the `"NEO-GEO"`
signature at `0x100` and the USER entry jump at `0x122` (S6, S4; pinned MAME
`install_rom` of the same range, S7, differential only). Writes into the window
are dropped and counted like the other pinned-MAME dropped writes. The selected
profile requires a program region larger than the window, so no in-window read
falls beyond loaded bytes; a read past a loaded region would be an unmapped
bus fault. The banked P2 window is now exercised by original synthetic guest
bank-select tests; selected-title compatibility remains unqualified.

| Claim | Evidence class | Current result |
|---|---|---|
| Region sizes and declared load transforms | Pinned MAME source metadata | Reproducible implementation reference; emulator-derived, not hardware truth |
| Normalized role bundle parse, program byte transform, and API ownership | Synthetic automated test | Passed at the current revision |
| Selected MVS BIOS mirror and low unmapped byte-write differential | Pinned MAME map/default-handler source plus synthetic boundary, no-op, and wrong-window tests | Emulator differential only; physical hardware behavior remains unknown |
| ZIP32 stored/DEFLATE validation and error taxonomy | Public synthetic archive tests | Passed at the current revision; hostile-input review remains required |
| Selected private BIOS/media identity | Local-only evidence | Passed for the current bounded invocation; exact identities remain private |
| VBlank interrupt from emulated time, level-sensitive acknowledge | Pinned MAME source plus wiki cross-check, synthetic regressions with wrong-behavior controls | Passed at the current revision; the selected run did not need it and is unchanged by it |
| P1 controls and REG_DIPSW at `$300000` (mask `0x01ff7e`) return released-input `0xff` and the default DSW `0xff`; P2 controls at `$340000` (mask `0x01fffe`) return released-input `0xff` on both byte lanes | Pinned MAME source (S19-S20c, S24-S24g) plus synthetic byte, word, mirror and guest-read regressions | Passed at the current revision with no host input asserted; emulator differential, not physical input-device response; unsupported TEST and system-status neighbors remain faults |
| Video-control word read at `$3c0006` and its `0x01fff8` mirrors, including `$3c000e` and the upper mirror boundary | Pinned MAME map and video-register implementation (S17-S17e), plus synthetic guest raster-boundary, animation-speed, lane and mirror checks | Passed at the current revision using the emulated 68000 raster phase; reference-emulator differential only, not physical timing or rendering acceptance; low-byte-only reads remain unmapped |
| Even/high-byte writes to the implemented video-register subset, including video control at `$3c0006` | Pinned MAME write map and `video_register_w` (S17f-S17g), plus guest-driven high-byte control write and unsupported low-byte write checks | Passed at the current revision; high-byte values are duplicated into both callback lanes; emulator differential only, not physical-board behavior |
| I/O status: REG_STATUS_A byte read at `$320001` (mirror `0x01fffe`); coin 1 is an active-low host input and the uPD4990A time pulse/data out remain live calendar pins | Pinned MAME source and reference-emulator differential (S22-S22j), fetched input sources (S27/S27b/S30), synthetic regression with mirror, input polarity, isolation, reset and fault controls | Passed at the current revision; emulator differential, not hardware truth; bit 5 (4-slot sense) physical value is not established; the prior sound reply fault is now handled by the unqualified candidate described below |
| I/O status: REG_STATUS_B high byte at `$380000` (mirror `0x01fffe`); P1 Start is active low and the absent-card/MVS bits retain their prior values | Pinned MAME source (S23-S23i), fetched input sources (S28/S28b/S30b/S30c), mirror/reset/isolation/input controls | Passed by the synthetic board test; reference-emulator differential, not hardware truth; MAME's start/select callback distinction and physical-board behavior remain unqualified; low-byte and word reads remain unsupported |
| Board registers: system-status low-byte/word reads, system latches, LSPC registers | Pinned MAME source (S24-S24g, S34f) and synthetic latch regressions | System-latch outputs 0, 2, 3, 6 and 7 are retained per image for screen-shadow selection, memory-card lock1/unlock2, save-RAM write enable, and palette-bank selection; reset and instance isolation are covered. Memory-card contents/access and the other latch outputs remain unimplemented; unsupported system-status neighbors and other listed registers fault with a recorded address, access and width. The selected run demanded output 2 at C27; the C28 observation progressed to another CPU blocker; selected-game compatibility remains unqualified. This is reference-emulator differential, not hardware truth. |
| Calendar: uPD4990A control byte write at `$380051` (serial command register, 48-bit shift register, time counter, pulse timers), seed `GN_MVS_CALENDAR_EPOCH` | Pinned MAME source (S21-S21u), synthetic regressions with isolation, timing and fault controls | Passed at the current revision (plan 05-21 rerun 8); emulator differential; the power-on seed is an emulator choice, not hardware and not host time; test mode, sub-second phase, leap day and weekday encoding are not established; primary datasheet not consulted |
| Sound handshake: `$320000` command write and reply read, Z80 and YM2610 | Pinned MAME source (S25-S25t, S9/S9b), synthetic latch-ordering/source-selection/partition checks and subsequent current sound integration | Sound catches up before latch transfers using sequential four-clock MOVE bus slots and consumes the remaining instruction clocks once. The3:1 main/audio ratio derives from S9/S9b/S25q; prefetch, internal-idle placement, wait states and physical bus timing remain unqualified. Fixed-source selection, explicit v2 audio BIOS and original synthetic handler tests remain source-qualified; legacy missing bytes are never fabricated. The old C47 failure remains preserved history. Current native caller-owned PCM, adapter delivery and actual frontend recorder/route/control outcomes pass only within the bounded scope above; physical audibility/recognizability have a separate bound user listening confirmation, as scoped above |
| Banked P2 window | Pinned MAME source (S16-S16h) plus original synthetic guest byte/word writes, bank boundaries, reset and isolation tests | Passed at the current revision as emulator-differential behavior; physical-board behavior and selected-title compatibility remain unqualified |
| Display-position timer interrupt and `$3c0008/$3c000a` counter, power-on IRQ3, PAL timer pause | Pinned MAME source only | Not implemented; the video-control line/counter word at `$3c0006` is implemented as a separate read path; no selected-title or physical-board claim follows |
| Guest reaches the selected title | Native guest execution plus invocation-bound actual frontend capture | Current selected import/native/frontend/title/identity acceptance predicates passed; earlier black failures and OCR unknown remain retained. Phase05 named verification/UAT accepted the bounded boot/title path on2026-10-20 |
| Actual pinned RetroArch selected-media route | Direct app observation plus local process/capture evidence | Pinned RetroArch1.22.2 selected-scene runs pass with320x224 software video, sampled inputs, measured successful-video capture intervals, full RGB replay and orderly exit. Private identities and captures are not published |
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
`MOVE.B Dn,(xxx).L` (16 clocks, 3 reads, 1 write), `MOVE.B #<data>,(xxx).L`
(20 clocks), `MOVE.W #<data>,<data-alterable memory>` (12/12/12/16/18/16/20
clocks across `(An)`, `(An)+`, `-(An)`, `d16(An)`, brief indexed, absolute
short, and absolute long; 2/2/2/3/3/3/4 reads and one word write), and
`MOVE.W #<data>,Dn` (8 clocks), from NXP/Motorola *M68000 User's Manual*
Rev. 9.1, Table 8-2, printed p. 8-2. Absolute-long
stores use the required bus width; odd word destinations take the address-error
path. The immediate-to-Dn form preserves the upper half of the destination,
updates N/Z/V/C, and preserves X. BSR.W (18 clocks), JSR's supported control-EA
forms (16/18/22/18/20/18/22 clocks for `(An)`, `d16(An)`, brief indexed An,
absolute short/long, `d16(PC)` and brief indexed PC), RTS (16 clocks), and LEA
absolute-long (12 clocks) are also covered by their cited manual timing rows.
JSR pushes the continuation after its EA extensions and computes a PC-relative
target from the extension-word address (Motorola *M68000 Family Programmer's
Reference Manual*, §4 JSR p. 4-109 and §2.2.11 p. 2-13). Full-format index and
non-control effective addresses remain unsupported. The owned core performs no
target fetch in the same instruction step; its callback read count reflects the
opcode and required EA extension words, not a claim about silicon bus chronology.
The current owned CPU subset supports MOVEM.W/L register-to-memory and
memory-to-register transfers across the documented addressing forms listed in
`experiments/owned_cpu/SUBSET.md`. Memory-to-register mask order is D0–D7 then
A0–A7; word loads sign-extend, and a postincrement source advances by the
operand width per selected register. If the source base appears in the list,
the final postincremented address supersedes its loaded value (User's Manual
Table 8-10, p. 8-8; Programmer's Reference Manual §4 MOVEM, pp. 4-127–4-130).
This bounded owned-core admission is execution evidence for the selected
profile, not a qualification of broader MVS hardware/platform behavior.
`MOVEA.L (An)+,An` is also covered
at 12 clocks (3 reads, no writes; User's Manual Table 8-3, p. 8-3; Programmer's
Reference Manual §4 MOVEA, pp. 4-119–4-120): it loads the full 32-bit address
register, increments the source by four, and leaves condition codes unchanged.
For a source/destination register alias, the loaded value supersedes the
postincrement. Other unlisted MOVEM forms and neighboring MOVEA forms remain
unsupported. `MOVEA.L An,An` is supported for direct address-register
transfers (4 clocks, 1 read, 0 writes; User's Manual Table 8-3, p. 8-3). It
copies all 32 bits without changing flags, including the source/destination
alias case; byte-sized and unlisted effective-address forms remain unsupported. These are bounded
CPU semantics, not title-boot evidence. `MOVE.W Dn,Dn` is supported for direct
data-register transfers at 4 clocks (1 read, 0 writes; User's Manual Table 8-2,
p. 8-2). It replaces only the destination's low word, sets N/Z/V/C from that
word, and preserves X and the upper destination word. Byte and other EA forms
remain unsupported. `MOVE.B Dn,(An)` is supported as an explicit byte bus write
at 8 clocks (1 read, 1 write; User's Manual Table 8-2, p. 8-2). It updates
N/Z/V/C from the source's low byte, preserves X, and leaves adjacent memory
bytes untouched. Byte memory loads to Dn share one admitted data-alterable
source family: `(An)`, `(An)+`, `-(An)`, `(d16,An)`, brief `(d8,An,Xn)`,
absolute short and absolute long. MC68000 User's Manual Rev. 9.1 Table 8-2,
p. 8-2, gives 8/8/10/12/14/12/16 clocks in that order. Byte accesses may be
odd; the low byte of Dn is replaced, N/Z follow it, V/C clear, X is preserved,
and A7 auto-updates by two. The brief An-index source accepts signed byte
displacement with word- or long-sized D/A index and no scaling (Programmer's
Reference Manual §§2.2.4, 2.2.7 and MOVE pp. 4-116 to 4-118). The PC-indexed
form `MOVE.B (d8,PC,Xn),Dn` remains separately admitted at 14 clocks; other
unlisted byte source/destination encodings remain unsupported. The byte store
`MOVE.B Dn,(d8,An,Xn)` uses the same
MC68000 brief indexed form at 14 clocks (2 reads, 1 write; User's Manual
Rev. 9.1 Table 8-2, p. 8-2). It writes Dn's low byte to An plus the signed
8-bit displacement and signed word- or full-long D/A index, allows odd byte
addresses, sets N/Z, clears V/C, and preserves X. Reserved extension bits and
unlisted destination modes remain unsupported; the regression
`move_byte_data_register_to_indexed_displacement_writes_one_byte_in_14_cycles`
checks the bus count, effective address, flags, and byte-lane boundaries.
`MOVE.W Dn,(An)+` performs a word store and advances An by two at 8 clocks
(1 read, 1 write; User's Manual Table 8-2, p. 8-2); it updates N/Z/V/C while
preserving X. An odd destination follows the 68000 address-error path before
the target write. Other bounded word-store destinations are listed below;
unlisted word addressing modes remain unsupported.
`MOVE.W Dn,(An)` stores the low source word at the selected address register in
8 clocks (1 read, 1 write; User's Manual Table 8-2, p. 8-2), updates N/Z/V/C,
preserves X and the source register, and takes the address-error path for an
odd destination.
`MOVE.W Dn,-(An)` subtracts two from An and stores Dn's low word in 8 clocks
(1 opcode read and 1 word write; User's Manual Rev. 9.1 Table 8-2, p. 8-2).
It sets N/Z from the word, clears V/C, preserves X and synchronizes the active
stack bank when An is A7. The owned-core predecrement remains committed before
an odd-address exception or terminal host write fault, while counter-overflow
preflight leaves it unchanged. The manual supplies the instruction timing and
semantics, not this callback-level partial-fault chronology.
`DBF Dn` (`DBRA`) supports its word displacement form only: it decrements the
counter's low word, preserves the upper word and condition codes, and branches
relative to the address after the opcode unless the result is `0xffff`
(Motorola *M68000 Family Programmer's Reference Manual* §4 DBcc, pp. 4-90–4-91).
The taken path costs 10 clocks/2 reads; the expired path costs 14 clocks/3 reads
(User's Manual Table 8-9, p. 8-7). Other DBcc conditions remain unsupported.
`MOVE.W <readable memory>,Dn` now uses one shared word-source path for D0–D7.
It admits `(An)`, `(An)+`, `-(An)`, `d16(An)`, MC68000 brief
`d8(An,Xn)`, absolute short/long, and PC-relative displacement/brief-index
sources. The source reads one aligned word, replaces Dn's low word, sets N/Z,
clears V/C and preserves X. User's Manual Rev. 9.1 Table 8-2, p. 8-2, gives
8/8/10/12/14/12/16 clocks for the seven memory EAs and 12/14 for PC-relative
forms. Odd addresses take vector 3 before operand access. PI/PD updates on that
exception follow pinned MAME as differential evidence; host callback failures
keep their separate contract. Address extensions are fetched before fixed
counter preflight, which leaves architectural state and the operand untouched
on overflow. Full-format indexed extensions, Dn/An-direct or immediate sources,
MOVEA destinations and illegal destination EAs remain outside this form.
`MOVE.W (An),(Am)+` was the first selected word memory-to-memory case; the complete 49-pair `MOVE.W <data-alterable memory>,<data-alterable memory>` family now includes it. Its dedicated regression remains as a guest-observed case, while row 65 is the current contract for the full timing matrix, flags, bus order, aliases, and alignment boundaries.
`CMPI.W #imm,<data-alterable memory>` now shares one bounded handler across
`(An)`, `(An)+`, `-(An)`, `d16(An)`, brief `d8(An,Xn)`, absolute short and
absolute long. It fetches the immediate before EA extensions, reads one
aligned word, leaves memory unchanged, updates N/Z/V/C while preserving X,
and costs 12/12/14/16/18/16/20 clocks respectively (CMPI.W memory 8 clocks
plus the word EA timing in User's Manual Rev. 9.1 Tables 8-5 and 8-1,
pp. 8-5 and 8-2). Postincrement normally follows a successful read, but an
odd postincrement source advances before vector 3 per pinned MAME differential;
host read-callback failures still defer it. Predecrement is applied before
vector-3 handling. The manuals do not specify this partial-fault chronology. A7 updates its active stack bank, and PC-relative,
scaled/full-index and other size/mode combinations remain unsupported.
`MOVE.W #<data>,<data-alterable memory>` shares one handler across all seven
memory destinations: `(An)`, `(An)+`, `-(An)`, `d16(An)`, MC68000 brief
`d8(An,Xn)`, absolute short and absolute long. It fetches the immediate before
destination extensions, writes one word, updates N/Z/V/C and preserves X, at
12/12/12/16/18/16/20 clocks (2/2/2/3/3/3/4 reads and one write). Odd word
destinations take vector 3 before the operand write; predecrement commits
after exception preflight, and postincrement normally follows a successful write
but advances before vector 3 for an odd destination per pinned MAME differential.
Host write-callback failures still defer postincrement; the manuals do not
establish this partial-fault chronology. `MOVE.W Dn,(d16,An)` remains 12 clocks (2 reads, 1 write), also
listed in Table 8-2, printed p. 8-2. `MOVEA.W #imm,An` is separately
supported: it sign-extends the immediate word to all 32 address-register bits,
preserves CCR and uses the Table 8-3 timing; byte/long immediate stores,
PC-relative and other non-data-alterable destinations remain unsupported.
Unsupported encodings and addressing modes remain faults. These CPU semantics
are source-backed. The maintained no-input local run reaches its BIOS attract/start
checkpoint. After the CMPI.W memory-family repair, scripted input reached
`MOVE.W #imm,-(An)`; this form has now been covered by the shared data-alterable
handler. A prior selected-frontend title observation is not bound to the latest
runtime, whose screenshot-hotkey capture was black and whose current title
predicate failed. The native qualifier's title frame remains a separate
bounded result and does not substitute for frontend acceptance.

The selected profile also routes the observed reserved `EORI.B` and `EORI.L`
destination encodings to MC68000 illegal-instruction vector 4. The handler
stacks the pre-instruction PC and old SR in the short exception frame, enters
supervisor mode, and fetches vector offset `0x10`. The 34-clock cost follows
the MC68000 *M68000 User's Manual*, Rev. 9.1, §6.3.6, Table 6-2 (printed p. 6-7)
and Table 8-14 (printed p. 8-11; plan 05-18 corrected the earlier Table 7-15
attribution, which is the 8-bit-bus table). Other unsupported encodings remain
fail-closed; this exception slice does not imply general exception coverage.
Reset, interrupt, and address-error events use the same MC68000 timing table
(Table 8-14): 40, 44, and 50 clocks respectively. The separately modeled MVS watchdog reset
is a board event and does not use the CPU RESET-instruction timing.

The MVS profile also models the pinned MAME watchdog reset window at
`0x300001` and its mirror, using MAME's 3,244,030 master-tick interval at 24 MHz
(1,622,015 main-CPU cycles at 12 MHz). A write pets the timer; expiry performs a
CPU soft reset while preserving work RAM. Accounting occurs at instruction
boundaries, so the reset observation has that deterministic granularity. The
source is MAME differential evidence, not physical-board proof. The profile also
records the cartridge-audio source-select latch bit and connects it to the fixed audio window (S25n-S25p); fixed-layer rendering remains outside this slice.
Video-register writes use the pinned MAME 16-byte write map mirrored across a
`0x20000`-byte window. For the subset implemented here, word writes and
even/high-byte writes share the same register effects; the high byte is
duplicated into both callback lanes. Low-byte-only writes have no register
effect in MAME and remain fail-closed in this bounded core. Read-side registers
0-3 use the separate four-word map with mirror mask `0x01fff8`, also spanning
`0x20000` bytes. Reads of indexes 0/1 return the VRAM data buffer, index 2
returns modulo, and index 3 returns the video-control word. Low-byte-only reads
are unmapped; high-byte reads and aligned word reads use the same register
value. The read mirror maps `$3c000e` to index 3, while `$3c000c` reads index 2
(modulo); its separate write decode acknowledges interrupts.

The selected profile allocates zeroed per-instance VRAM and tracks the data
read buffer; index 1 writes one word, advances the offset by the configured
modulo while preserving the extended-bank bit, and refreshes the read buffer.
Offset normalization is applied again after increment, including the `0x87ff`
extended-bank limit. These VRAM latches persist across CPU reset as in MAME
`device_reset`; newly loaded images start from zeroed state. The synthetic guest
test checks write/readback, modulo advance, and the upper bound.

The video-control read derives `vpos` from the per-instance 68000 raster count
at 768 CPU clocks per line and applies MAME's `vpos + 0x100` chain, subtracting
the 264-line total at `0x200`. Its low three bits expose the sprite
auto-animation counter, which updates at scanline `0x100`; the high-byte speed
write controls the callback's frame countdown. `STOP` idle fast-forward stops at
that callback boundary. These are MAME-differential values at instruction-time
granularity, not measured hardware timing. Native rendering now covers the
documented fixed/sprite subset below, while selected-screen and physical-board
equivalence remain unclaimed. Sources: pinned MAME
`neogeo_v.cpp` `get_video_control`/`video_register_r`, `neogeo.cpp` video map,
and `neogeo_spr.cpp` animation callback (revision
`31e52312c59e4d60d70235118bcbccd220f5232e`; S17-S17e). Interrupt acknowledgement is a zero-
pending MAME differential for IRQ3 and raster; the VBlank producer is described
under "Interrupts and timing". The observed
two-channel coin-lockout state is tracked per instance from MAME's I/O callback.
Writes to its coin-counter output offsets (I/O words `0x30` and `0x70` with
offset bit 1 clear) are accepted as mapped no-ops; the reference emulator's
bookkeeping counters are not guest-visible and no physical coin-output claim
is made (S21v). System-latch output 6 records the save-RAM write-enable bit and gates a
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
This is MAME-differential storage only: the bounded renderer uses palette pens
and sprite-generator state for the source-qualified subset below, not a complete
sprite-device model. Video-register index 2 is backed by
`video_register_w`/`video_register_r` in the same pinned source
([neogeo_v.cpp lines 228-269](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp#L228-L269)).
The per-instance bus observation contract is version 14. A later unsupported
guest event still stops qualification, so no title-boot result is claimed.

The local qualification command keeps inputs under ignored `local/roms/` and
writes invocation-specific JSON reports under ignored `local/qualification/`;
the default report name is `phase05-<id>.json`. It emits only bounded generic
statuses plus the first unsupported guest event. Never put private media
identities, paths, bytes, or derived data in tracked outputs.

## Interrupts and timing

Plan 05-10 adds one interrupt producer to the selected MVS profile: the VBlank
interrupt, generated from the per-instance count of executed 68000 clocks. No
host clock, frame callback or PC test takes part. Evidence class for every value
below is the pinned MAME differential (`31e52312...`, `neogeo.cpp`,
`neogeo.h`, `neogeo_spr.h`) cross-checked against the NeoGeo Development Wiki
(community documentation, cited by oldid). Neither is hardware truth; the
physical phase of the VBlank flip-flop against the 68000 clock is unverified.

| Constant | Value | Source (rows below) | Evidence class |
|---|---|---|---|
| Master clock | 24,000,000 Hz | S9; wiki S14c, S15 | MAME differential; wiki agrees |
| 68000 clock | master / 2 = 12 MHz | S9b | MAME differential |
| Pixel clock | master / 4 = 6 MHz | S9c; wiki S14c, S15 | MAME differential; wiki agrees |
| Pixels per line | 0x180 = 384 | S8; wiki S14 | MAME differential; wiki agrees |
| Clocks per line | 384 pixels x 4 master / 2 = 768 CPU clocks | derived from S8, S9b, S9c | derived |
| Lines per frame | 0x108 = 264 | S8b; wiki S14b | MAME differential; wiki agrees |
| Clocks per frame | 264 x 768 = 202,752 (59.1856 Hz) | derived; wiki S15b | derived; wiki agrees |
| VBlank start line | 0x0f0 = 240 | S8c | MAME differential |
| VBlank IRQ phase | 56 + 2 master clocks after line start = 29 CPU clocks | S10 | MAME differential |
| First VBlank IRQ | 240 x 768 + 29 = 184,349 clocks after load or reset | S10b | MAME differential |
| VBlank level | 1 | S11, S11d; wiki S13 | MAME differential; wiki agrees |
| Raster (timer) level | 2 | S11b, S11e; wiki S13 | MAME differential; wiki agrees |
| IRQ3 level | 3 | S11c; wiki S13 | MAME differential; wiki agrees |
| Acknowledge bits at `$3C000C` | bit 0 IRQ3, bit 1 raster, bit 2 VBlank | S12, S12b, S12c; wiki S13b | MAME differential; wiki agrees |

Plan 06-03 rechecked the primary SNK specification's printed Hardware page 1:
it states a 12 MHz CPU clock. The scan was fetched again on 2026-10-21 and
matches the SHA-256 in "Video rendering references" below. The 768 clocks/line
and 264 lines/frame retain the pinned MAME ancestry above. Their quotient,
`12000000.0 / 202752.0` (about 59.185606 Hz), is a model-derived cadence,
not a physical measurement or qualification of another video mode.

Logical-frame consumers use the private `gn_mvs_run_frame_budget` seam shared
by libretro and the maintained native runner. It carries already executed
instruction excess into the next minimum cycle budget. Raw `gn_run_mvs` keeps
its explicit minimum-budget contract and reports actual elapsed clocks and
overshoot; its caller still owns the requested budget. All raster, calendar,
sound and interrupt work advances once from those actual clocks. Rendering
continues to observe state without advancing time. Load/reset clear logical
carry; a short failed call retains its reported frame prefix and keeps its
failure status. Explicit raw budget calls do not consume logical-frame carry.

`retro_get_system_av_info` reports this MVS cadence for loaded MVS content and
exactly 60 Hz for the separate GNFX fixture, including unload/reload transitions.
The adapter announces loaded-content AV metadata once from the first
`retro_run`, as required by the pinned `RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO`
contract (libretro-common revision `a3194c18ba65ef89734e1898a2f61403c255d368`,
`include/libretro.h`). An unsupported or rejected update emits one bounded
fixed warning; the metadata query stays correct, while that frontend's pacing
remains unqualified. No wall clock, guest overclock or skipped guest execution
is introduced. The original fixture builder is linked only into the existing
consumer test to check actual content transitions.

The repeated-frame regression uses an original NOP/branch guest whose
instruction period does not divide a frame. Across 64 logical frames it checks
cumulative executed clocks, bounded excess, raster phase, VBlank counts and
animation ticks, followed by a raw multi-frame budget. Reset and an interleaved
second instance test carry ownership. These are deterministic model checks,
not hardware bus-phase or performance measurements.

Behavior in force:

- The frame position starts at 0 on load and on `gn_reset` and advances only by
  executed clocks (instruction clocks, exception-entry clocks and idle clocks
  of a stopped CPU). MAME starts its free-running screen at machine start and
  its timers at each reset (S10b, `start_interrupt_timers`), so a warm reset
  inside MAME keeps the frame phase while this profile restarts it. The
  difference is deliberate and unobserved by the selected run.
- Crossing the VBlank clock sets pending bit 2 (value 4). The highest pending
  source drives the CPU interrupt level: IRQ3 (3), then raster (2), then
  VBlank (1). `gn_run_mvs` applies the level at each instruction boundary,
  which is where a 68000 samples its lines; `owned_cpu_set_irq` is rejected
  while an instruction executes, so an acknowledge write takes effect at the
  next boundary.
- The line is level-sensitive. A write to `$3C000C` clears the pending bits it
  names and nothing else; a handler that does not acknowledge, or acknowledges
  another bit, is entered again as soon as its mask allows.
- A stopped CPU that cannot take a pending level idles in one step up to the
  smaller of the watchdog period, the remaining budget and the next VBlank or
  sprite auto-animation callback. This keeps both raster-visible state and
  pending interrupt state synchronized without adding host-time pacing.
- Not modeled: the display-position timer interrupt and its `$3C0008`/`$3C000A`
  counter, power-on IRQ3 (MAME `m_irq3_pending = 1` at machine start), and the
  PAL timer pause. The live scanline/animation counter returned by video
  control read (S17-S17e) is modeled separately. Pending IRQ3 and raster bits
  exist in the mask but have no producer.
- `interrupts_taken` in the stall diagnosis counts exception-only steps that
  leave an autovector 25-31. The owned CPU charges the Table 8-14 value of 44
  clocks for the entry (corrected by plan 05-18 from the 8-bit-bus Table 7-15
  value 72; see "Exception-entry timing table selection"). Plan 05-10 made the
  check independent of the charge.

Demand record (D-07): the selected-run rerun after this change is identical to
the historical05-08 diagnosis (see [retired Phase05 validation](../.planning/milestones/ws-first-playable-game-2026-10-24/retired/2026-10-16-development-workflow/phase05/05-VALIDATION.md), "Plan 05-10 reruns"). VBlank was an
inferred demand and was not confirmed; it is kept because the plan named it,
sources pin it and regressions cover it, not because the selected run needed it.

Regressions: `mvs_test --board-core` (CTest `mvs_board_behavior`), case group
`irq-timing`: exact first-VBlank clock, four acknowledged entries in four
frames, mask-7 control (zero entries), never-acknowledged and wrong-bit
acknowledge controls (storm), reset restarts the frame phase, and three
interleaved instances in different slice sizes keep independent counts.

The board suite uses six bounded CTest partitions: `mvs_board_behavior`,
`mvs_board_io`, `mvs_board_calendar`, `mvs_board_sound`, `mvs_board_cartridge`
and `mvs_board_video`. Every original board subcheck remains required.
`mvs_test --board-behavior` retains the comprehensive direct-run command;
ordinary CTest runs the partitions with the existing per-case time bound.

## Owned 68000 encodings added for selected boot and active-scene diagnosis

Plan 05-11 admits owned-CPU encodings only when a selected-run rerun stopped at
them (D-07, P05-C-08). Each row names the mnemonic, size and effective-address
(EA) class, never raw instruction words or addresses. Evidence class for the
semantics and condition codes is primary (Motorola/NXP *M68000 Family
Programmer's Reference Manual*, "PRM"); clocks come from the primary
*MC68000 8-/16-/32-Bit Microprocessors User's Manual* Rev. 9.1 ("UM"), Section 8
(MC68000 in 16-bit mode), by printed page. Each row has a semantics, flag,
clock and bus-count regression and at least one still-unsupported neighbor
control in `tests/owned_cpu/test_semantics.c`, and a row in
`tests/owned_cpu/ORACLE.md`.

| Order | Mnemonic, size | EA class | Clocks | Citation |
|---:|---|---|---:|---|
| 0 | Decode repair: `MOVEA.L An,An` | register direct only | 4 | The old mask ignored the destination mode, so a store through `(d16,An)` ran as a register copy (silent wrong execution). The mask now keys on the full destination field. |
| 1 | Initial `MOVE.L An,(d16,An)` support (later consolidated in row 52) | address-register source to displacement destination | 16 | PRM MOVE pp. 4-116 to 4-118; UM Table 8-3 p. 8-3 |
| 2 | `CLR.B` | `(d16,An)`, read before write | 16 | PRM CLR pp. 4-73 to 4-74; UM Table 8-6 p. 8-6 + Table 8-1 p. 8-2 |
| 3 | `TST.B` | `(xxx).L` | 16 | PRM TST pp. 4-192 to 4-193; UM Table 8-6 p. 8-6 + Table 8-1 p. 8-2 |
| 4 | `ADDQ.B #1..8` | `(xxx).L` read-modify-write | 20 | PRM ADDQ pp. 4-11 to 4-12; UM Table 8-5 p. 8-5 + Table 8-1 p. 8-2 |
| 5 | `CMPA.{W,L}` | Seven data-alterable memory source EAs to An in `(An)/(An)+/-(An)/d16(An)/brief-index/abs.W/abs.L` order; word source sign-extends, long compares full width; N/Z/V/C update and X is preserved. The separately listed An-direct long and immediate guest forms also remain supported; Dn-direct, An-direct word, and PC-relative sources are outside this subset | W: 10/10/12/14/16/14/18; L: 14/14/16/18/20/18/22 | PRM CMPA pp. 4-77 to 4-78; UM Rev. 9.1 Tables 8-4 p. 8-4 and 8-1 p. 8-2; PI/PD partial auto-update follows pinned MAME differential, not a hardware chronology claim |
| 6 | `MOVE.L An,Dn` | address register to data register | 4 | PRM MOVE pp. 4-116 to 4-118; UM Table 8-3 p. 8-3 |
| 7 | `MOVE.B` | `(An)+` source, Dn destination (A7 steps by 2) | 8 | PRM MOVE pp. 4-116 to 4-118, section 2.2.4 p. 2-6; UM Table 8-2 p. 8-2 |
| 8 | `CMPI.B` | immediate, Dn destination | 8 | PRM CMPI pp. 4-79 to 4-80; UM Table 8-5 p. 8-5 |
| 9 | `LSL.W #1..8` | Dn | 6+2n | PRM LSL pp. 4-113 to 4-115; UM Table 8-7 p. 8-6 |
| 10 | `MOVEA.L` | `(d8,PC,Xn)` source (brief extension word only) | 18 | PRM MOVEA pp. 4-119 to 4-120, section 2.2.12 p. 2-14; UM Table 8-3 p. 8-3 |
| 11 | `JSR` | `(An)` | 16 | PRM JSR p. 4-109; UM Table 8-10 p. 8-8 |
| 12 | `MOVE.W` | `(An)+` source, Dn destination | 8 | PRM MOVE pp. 4-116 to 4-118, section 2.2.4 p. 2-6; UM Table 8-2 p. 8-2 |
| 13 | `BRA.B` | nonzero 8-bit displacement | 10 | PRM BRA p. 4-55; UM Table 8-9 p. 8-7 |
| 14 | `MOVE.B` | Dn source, Dn destination | 4 | PRM MOVE pp. 4-116 to 4-118; UM Table 8-2 p. 8-2 |
| 15 | `ADDI.W #imm` | Dn | 8 | PRM ADDI pp. 4-9 to 4-10; UM Table 8-5 p. 8-5 |
| 16 | `ANDI.W #imm` | Dn | 8 | PRM ANDI pp. 4-18 to 4-19; UM Table 8-5 p. 8-5 |
| 17 | `OR.{B,W,L} Dm,Dn` | Dn-direct source to Dn destination; byte/word preserve the upper Dn bits, long replaces all bits; N/Z follow the selected-width result, V/C clear, X preserved | 4/4/8 | PRM OR pp. 4-150 to 4-151; UM Table 8-4 p. 8-4 (byte/word 4; footnote ** raises long register-direct base from 6 to 8); `OR.W` added after the selected guest reached the word form |
| 18 | `MOVE.L #imm` | `(An)` destination | 20 | PRM MOVE pp. 4-116 to 4-118; UM Table 8-3 p. 8-3 |
| 19 | `CLR.B` | `(xxx).L`, read before write | 20 | PRM CLR pp. 4-73 to 4-74; UM Table 8-6 p. 8-6 + Table 8-1 p. 8-2 |
| 20 | `LEA` | `(d16,PC)` source, An destination (plan 05-21 rerun 1) | 8 | PRM LEA p. 4-110; UM Table 8-10 p. 8-8 |
| 21 | `CMPM.B` | `(Ay)+,(Ax)+` (A7 steps by 2) (05-21 rerun 2) | 12 | PRM CMPM pp. 4-80 to 4-81; UM Table 8-11 p. 8-9 |
| 22 | `MOVE.L` | Dm source, Dn destination (05-21 rerun 3) | 4 | PRM MOVE pp. 4-116 to 4-118; UM Table 8-3 p. 8-3 |
| 23 | `MOVEM.L` | register list to `-(An)` (05-21 rerun 4) | 8+8n | PRM MOVEM pp. 4-127 to 4-130; UM Table 8-10 p. 8-8 |
| 24 | `MOVE.B` | Historical `(Ay)+` to `(Ax)+` case; now covered by the unified memory-to-memory family in row 65 | 12 | PRM MOVE pp. 4-116 to 4-118 and section 2 postincrement; UM Table 8-2 p. 8-2 |
| 25 | `MOVE.L` | Dn source, `(An)+` destination (05-21 rerun 6) | 12 | PRM MOVE pp. 4-116 to 4-118; UM Table 8-3 p. 8-3 |
| 26 | `ANDI.B #imm` | Dn (05-21 rerun 7) | 8 | PRM ANDI pp. 4-18 to 4-19; UM Table 8-5 p. 8-5 |
| 27 | `ORI.B #imm` | Dn (05-21 rerun 9) | 8 | PRM ORI pp. 4-152 to 4-153; UM Table 8-5 p. 8-5 |
| 28 | `EORI.B #imm` | Dn (05-22 rerun 10) | 8 | PRM EORI pp. 4-101 to 4-102; UM Table 8-5 p. 8-5 |
| 29 | `LSR.B #1..8` | Dn (05-22 rerun 11) | 6+2n | PRM LSL/LSR pp. 4-113 to 4-115; UM Table 8-7 p. 8-6 |
| 30 | `MOVE.B #imm` | Dn destination (05-22 rerun 12) | 8 | PRM MOVE pp. 4-116 to 4-118; UM Table 8-2 p. 8-2 |
| 31 | `EOR.B` | Dm source, Dn destination (05-22 rerun 14) | 4 | PRM EOR pp. 4-99 to 4-100; UM Table 8-4 p. 8-4 |
| 32 | `AND.{B,W,L} Dm,Dn` | All D0–D7 source/destination pairs; byte/word preserve upper destination bits and long replaces all bits; N/Z follow width, V/C clear, X preserved; other EAs remain outside this form | byte/word 4; long 8 | PRM §4 AND pp. 4-15 to 4-17; UM Rev. 9.1 Table 8-4 p. 8-4 (long direct-source ** adjustment) |
| 33 | `SUBI.B #imm` | Dn (05-22 rerun 16) | 8 | PRM SUBI pp. 4-179 to 4-180; UM Table 8-5 p. 8-5 |
| 34 | `CMPI.L #imm` | `(xxx).L`, operand not written (05-22 rerun 17) | 28 | PRM CMPI pp. 4-79 to 4-80; UM Table 8-5 p. 8-5 + Table 8-1 p. 8-2 |
| 35 | `LEA` | `(xxx).W` source, An destination (05-22 rerun 18) | 8 | PRM LEA p. 4-110; UM Table 8-10 p. 8-8 |
| 36 | `ADD.B` | `(An)+` source, Dn destination (A7 steps by 2) (05-22 rerun 19) | 8 | PRM ADD pp. 4-3 to 4-5, section 2.2.4 p. 2-6; UM Table 8-4 p. 8-4 + Table 8-1 p. 8-2 |
| 37 | `CMPI.W #imm,<data-alterable memory>` | `(An)`, `(An)+`, `-(An)`, `d16(An)`, brief indexed, absolute short/long; no write; odd postincrement advances before vector 3 per pinned MAME differential; word EA timing added to CMPI base (05-03 continuation) | 12/12/14/16/18/16/20 | PRM §2.2.4 p. 2-6, §2.2.7 p. 2-9 and CMPI pp. 4-79 to 4-80; UM Tables 8-1 and 8-5 pp. 8-2, 8-5 |
| 38 | `JMP (d16,An)` | signed word displacement to address-register base; target fetch occurs on the next instruction step (05-02 continuation) | 10 | PRM §2.2.6 and §4 JMP pp. 2-9, 4-108; UM Table 8-10 p. 8-8 |
| 39 | `Scc.B` | All 16 conditions to the seven data-alterable memory EAs; read destination byte before writing `$ff` when true or `$00` otherwise; flags unchanged; A7 byte step is two. UM timings by EA are 12/12/14/16/18/16/20. This follows the PRM's explicit MC68000 read-before-write statement; pinned MAME's generated SNE handlers omit the read, a recorded emulator discrepancy rather than hardware truth (05-03 post-entry continuation) | 12–20 | PRM §4 Scc pp. 4-172 to 4-173; UM Rev. 9.1 Tables 8-6 and 8-1 pp. 8-6 and 8-2; MAME differential revision [31e5231](https://github.com/mamedev/mame/tree/31e52312c59e4d60d70235118bcbccd220f5232e) |
| 40 | `LEA` | `(An)` source, An destination | 4 | PRM §4 LEA p. 4-110; UM Rev. 9.1 Table 8-10 p. 8-8; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 41 | `BTST Dm,Dn` | dynamic Dn bit number and Dn destination, modulo-32 | 6 | PRM §4 BTST pp. 4-60 to 4-63; UM Rev. 9.1 Table 8-8 p. 8-7; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 42 | `Scc.B Dn` | All 16 conditions and D0–D7; writes `$ff` when true or `$00` when false to the selected low byte; upper bits and flags stay unchanged. Regression covers every C/V/Z/N combination and fetch count; memory destinations are listed separately | 4 false / 6 true | PRM §4 Scc pp. 4-172 to 4-173; UM Rev. 9.1 Table 8-6 p. 8-6; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 43 | `MOVE.W <readable memory>,Dn` | Seven data-alterable memory EAs plus PC-relative displacement and brief-index sources; word result updates N/Z/V/C and preserves X; full-format index and illegal source/destination forms remain closed | memory 8/8/10/12/14/12/16; PC 12/14 | PRM §2.2.4, §2.2.7, §2.2.10–2.2.11 and §4 MOVE pp. 2-6, 2-9, 2-14, 2-15, 4-116 to 4-118; MC68000 UM Rev. 9.1 Table 8-2 p. 8-2; pinned MAME partial PI/PD update is differential evidence only |
| 44 | `ADDX.W -(Ay),-(Ax)` | word memory-to-memory add with X carry-in, sticky Z and source-first predecrement; byte/long predecrement forms remain unsupported; register-direct forms are listed separately | 18 | PRM §4 ADDX pp. 4-13 to 4-15; MC68000 UM Rev. 9.1 Table 8-11 p. 8-9; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 45 | `ADD.W Dn,(xxx).L` | exact word data-register-to-absolute-long memory read-modify-write; flags from word addition, source Dn preserved; other sizes and EAs remain unsupported | 20 | PRM §4 ADD pp. 4-4 to 4-6; MC68000 UM Rev. 9.1 Tables 8-4 and 8-1 pp. 8-4, 8-2; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 46 | `ROL/ROR.{B,W,L} #n,Dn` (1–8) | rotates within the selected width without X; byte/word preserve upper Dn bits; N/Z from result, V clear, C from the last rotated bit, X preserved | byte/word 6+2n; long 8+2n | PRM §4 ROL/ROR pp. 4-160 to 4-162; MC68000 UM Rev. 9.1 Table 8-7 p. 8-6; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 47 | `EOR.W Dm,Dn` | low-word XOR, destination upper word preserved; N/Z from result, V/C clear, X preserved; word register-direct only (memory destination support is listed separately) | 4 | PRM §4 EOR pp. 4-99 to 4-100; MC68000 UM Rev. 9.1 Table 8-4 p. 8-4; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 48 | `ADD.B Dn,(d8,An,Xn)` | brief indexed byte memory add; signed d8 plus Dn/An word or long index with no scaling; byte RMW, updates X/N/Z/V/C, allows odd addresses | 18 | PRM §2.2.7, §2.4 and §4 ADD pp. 2-9, 2-21, 4-3 to 4-5; MC68000 UM Rev. 9.1 Tables 8-4 and 8-1 pp. 8-4, 8-2; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 49 | `ADD.L Dn,(d8,An,Xn)` | brief indexed long memory add; signed d8 plus Dn/An word or long index with no scaling; aligned read-modify-write, updates X/N/Z/V/C, odd address enters vector 3 before operand access | 26 | PRM §2.2.7, §2.4 and §4 ADD pp. 2-9, 2-21, 4-3 to 4-5; MC68000 UM Rev. 9.1 Tables 8-4 and 8-1 pp. 8-4, 8-2; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 50 | `SUB.B (An),Dn` | byte subtract from Dn[7:0] with A0–A7 sources and D0–D7 destinations; preserves Dn[31:8], updates X/N/Z/V/C, allows odd byte addresses | 8 | PRM §4 SUB p. 4-174; MC68000 UM Rev. 9.1 Tables 8-4 and 8-1 pp. 8-4, 8-2; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 51 | `SUB.B Dm,Dn` | subtracts Dm[7:0] from Dn[7:0] for all Dm/Dn pairs, preserves Dn[31:8], updates X/N/Z/V/C including borrow, no operand bus access | 4 | PRM §4 SUB p. 4-174; MC68000 UM Rev. 9.1 Table 8-4 p. 8-4; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 52 | `MOVE.L An,<data-alterable memory>` | A0–A7 source; `(Am)`, `(Am)+`, `-(Am)`, `d16(Am)`, brief indexed, absolute short and absolute long destinations. The source is sampled before any aliased destination update. Normal forms issue high-word then low-word callbacks as this core's local contract; predecrement issues low at EA+2 then high at EA, matching the pinned generated handler. N/Z follow the long, V/C clear and X is preserved; A7 updates synchronize the active bank. UM Table 8-3 gives 12/12/12/16/18/16/20 clocks. On odd vector 3, PI/PD updates follow pinned MAME EA sequencing as differential evidence only. Terminal callback failures are separate: PD commits before writes, while PI waits for both successful writes. Other sizes and non-An sources, PC-relative/immediate or illegal destinations remain outside this family | PRM §2.2.4 and §4 MOVE pp. 2-6, 4-116 to 4-118; MC68000 UM Rev. 9.1 Table 8-3 p. 8-3; pinned MAME commit `31e52312c59e4d60d70235118bcbccd220f5232e`, generated handlers `x2088`–`x23c8` and [EA helpers](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/cpu/m68000/m68kcpu.h#L318-L321), differential chronology only |
| 53 | `MOVE.B (d16,An),(d16,Am)` | Historical displacement-to-displacement case; now covered by the unified memory-to-memory family in row 65 | 20 | PRM §4 MOVE pp. 4-116 to 4-118; MC68000 UM Rev. 9.1 Table 8-2 p. 8-2 (20(4/1)); [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 54 | `TST.B/W/L Dn` | all D0–D7; tests the selected width without changing the register; N/Z from that value, V/C clear, X preserved; no data access | 4 | PRM §4 TST pp. 4-192 to 4-193; MC68000 UM Rev. 9.1 Table 8-6 p. 8-6 (4(1/0)); [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 55 | `ANDI.B #imm,(d16,An)` | all A0–A7 bases; immediate word then signed displacement; byte read-modify-write, including odd byte addresses; N/Z from the result, V/C clear, X preserved | 20 | PRM §4 ANDI pp. 4-18 to 4-19; MC68000 UM Rev. 9.1 Table 8-5 p. 8-5 (12(2/1)+) plus Table 8-1 p. 8-2 (8(2/0)); [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 56 | `AND.W Dn,(An)+` | all D0–D7 source and A0–A7 destination pairs; one word read and one word write, An += 2; N/Z from result, V/C clear, X preserved; pinned MAME differential advances An before an odd read exception and records the data-read SSW | 12 | PRM §4 AND pp. 4-15 to 4-17; MC68000 UM Rev. 9.1 Table 8-4 p. 8-4 (8(1/1)+) plus Table 8-1 p. 8-2 (4(1/0)); [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf); [pinned MAME handler](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/cpu/m68000/m68kops.cpp#L3290-L3300) and [EA macro](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/cpu/m68000/m68kcpu.h#L300-L302) supply differential, not hardware, evidence for the odd path |
| 57 | `ADD.{B,W,L} Dm,Dn` | all D0–D7 source/destination pairs; byte and word sums preserve Dn upper bits, long replaces all of Dn; each size updates X/N/Z/V/C and reads only the opcode; data-register-direct timings are 4/4/8 clocks | 4/4/8 | PRM §4 ADD pp. 4-4 to 4-6; MC68000 UM Rev. 9.1 Table 8-4 p. 8-4 (byte/word 4 clocks; long 6 plus footnote **'s 2-clock register-direct adjustment); [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 58 | `CMPA.{W,L} #imm,An` | A0–A7 destination; word source sign-extends and long source uses all 32 bits; N/Z/V/C update while X and An stay unchanged | 10 / 14 | PRM CMPA pp. 4-77 to 4-78; UM Rev. 9.1 Tables 8-4 and 8-1 pp. 8-4, 8-2 (immediate word 4 clocks; long 8) |
| 59 | `SUB.W Dm,Dn` | all D0–D7 source/destination pairs; low-word subtraction preserves Dn[31:16], updates X/N/Z/V/C including borrow; one opcode fetch and no data operand access | 4 | PRM §4 SUB pp. 4-174 to 4-175; MC68000 UM Rev. 9.1 Tables 8-4 and 8-1 pp. 8-4, 8-2 |
| 60 | `SUBI.{B,W,L} #imm,Dn` | all D0–D7 destinations; byte/word forms preserve unselected upper Dn bits, long replaces the full register; subtracts at operand width and updates X/N/Z/V/C including borrow. Fetches opcode plus one immediate word for byte/word or two words high-to-low for long; no data writes. Long-family controls cover low-extension read failure and counter overflow before mutation; An-direct and reserved-size encodings remain unsupported | 8 / 8 / 16 | PRM §4 SUBI pp. 4-179 to 4-180; MC68000 UM Rev. 9.1 Table 8-5 p. 8-5 |
| 61 | `ADDA.W #imm,An` | all A0–A7 destinations; sign-extends the word immediate, adds to the full address register, leaves SR unchanged; opcode and immediate word reads, no data write | 12 | PRM §4 ADDA pp. 4-7 to 4-8; MC68000 UM Rev. 9.1 Tables 8-4 and 8-1 pp. 8-4, 8-2 |
| 62 | `SUBA.W #imm,An` | all A0–A7 destinations; sign-extends the word immediate, subtracts from the full address register, leaves SR unchanged; opcode and immediate word reads, no data write | 12 | PRM §4 SUBA pp. 4-177 to 4-178; MC68000 UM Rev. 9.1 Tables 8-4 and 8-1 pp. 8-4, 8-2 |
| 63 | `MOVE.L <data-alterable memory>,<data-alterable memory>` | Both endpoints independently use `(An)`, `(An)+`, `-(An)`, `d16(An)`, MC68000 brief indexed, absolute short, or absolute long. Table 8-3 gives the 7x7 source/destination cycle matrix: source `(An)` or `(An)+` 20/20/20/24/26/24/28; `-(An)` 22/22/22/26/28/26/30; `d16(An)` 24/24/24/28/30/28/32; brief indexed 26/26/26/30/32/30/34; absolute short 24/24/24/28/30/28/32; absolute long 28/28/28/32/34/32/36 (destination order `(An)/(An)+/-(An)/d16/index/abs.W/abs.L`). Reads source high word then low word before resolving destination extensions; source auto-updates precede aliased destination resolution. Writes high then low. N/Z follow the long, V/C clear, X preserved. Tests cover all 49 pairs, exact timing, extension/operand order, same-base postincrement alias, source low-word read fault, destination low-word write fault, and preflight overflow. Partial host callback effects are this owned-core contract, not silicon chronology; manuals establish address exceptions but not this family’s auto-update chronology. Added in Plan 05-03 as a coherent extension of the selected guest’s existing `(An)+` to indirect form. Other sizes, PC-relative/immediate/address-register endpoints and full-format indexes remain outside this family (PRM §§2.2.4, 2.2.7, 2.2.10 and §4 MOVE pp. 2-6, 2-9, 2-14, 4-116 to 4-118; MC68000 UM Rev. 9.1 Table 8-3 p. 8-3 and Figure 2-6 p. 2-7; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf)) | 20–36 |
| 64 | `CLR.L` | all seven data-alterable memory EAs; reads both longword halves before either zero write, N/V/C cleared, Z set, X preserved; odd postincrement reads commit An before vector 3 per pinned MAME differential; full-format index remains unsupported | 20/20/22/24/26/24/28 | PRM §§2.2.4, 2.2.7, 2.2.10 and §4 CLR pp. 2-6, 2-9, 2-14, 4-73 to 4-74; MC68000 UM Rev. 9.1 Tables 8-1 and 8-6 pp. 8-2, 8-6 |
| 65 | `MOVE.B/W <data-alterable memory>,<data-alterable memory>` | Source and destination each use `(An)`, `(An)+`, `-(An)`, `d16(An)`, brief `d8(An,Xn)`, absolute short or absolute long; both sizes use the Table 8-2 timing matrix by destination order `(An)/(An)+/-(An)/d16/index/abs.W/abs.L`: source `(An)` or `(An)+` `12/12/12/16/18/16/20`; `-(An)` `14/14/14/18/20/18/22`; `d16(An)` `16/16/16/20/22/20/24`; brief index `18/18/18/22/24/22/26`; absolute short `16/16/16/20/22/20/24`; absolute long `20/20/20/24/26/24/28`. One operand is copied; N/Z follow it, V/C clear and X is preserved. Byte accesses allow odd addresses and A7 byte steps are two; odd word accesses take vector 3. Regressions cover all 49 source/destination pairs per size, timing, flags, ordered EA extensions, aliases and candidate exception boundaries. In the owned-core family the source is resolved/read before destination extensions; source auto-updates precede aliased destination resolution. Odd postincrement word sources commit before vector 3, and odd postincrement word destinations commit after a successful source read but before vector 3, per pinned MAME differential; normal host callback failures remain deferred. Handlers `x1168_move_b_di_071234fc`, `x3168_move_w_di_071234fc`, `x3158_move_w_pi_071234fc` and `x30d8_move_w_pi_071234fc` are differential evidence, not hardware measurement or fault-chronology authority | 12–28 | PRM §§2.2.4, 2.2.7, 2.2.10 and §4 MOVE pp. 2-6, 2-9, 2-14, 4-116 to 4-118; UM Rev. 9.1 Table 8-2 p. 8-2; [pinned MAME source at revision `31e52312c59e4d60d70235118bcbccd220f5232e`](https://github.com/mamedev/mame/tree/31e52312c59e4d60d70235118bcbccd220f5232e) |
| 66 | `MOVE.B #imm,<data-alterable memory>` | Immediate byte to `(An)`, `(An)+`, `-(An)`, `(d16,An)`, brief `(d8,An,Xn)`, absolute short/long; one extension word for the immediate precedes destination extensions, one byte write, odd destinations valid; N/Z from byte, V/C clear, X preserved; A7 step is two | 12/12/12/16/18/16/20 | PRM §§2.2.4, 2.2.7, 2.2.10 and §4 MOVE pp. 2-6, 2-9, 2-14, 4-116 to 4-118; UM Rev. 9.1 Table 8-2 p. 8-2. Regression checks access order as owned-core behavior, not an independent bus-level hardware observation |
| 67 | `BCHG/BCLR/BSET #imm,<data-alterable memory>` | All three static forms cover `(An)`, `(An)+`, `-(An)`, `(d16,An)`, brief `(d8,An,Xn)`, absolute short and absolute long; byte bit index wraps modulo eight, BCHG toggles, BCLR clears and BSET sets, Z reflects the old bit, X/N/V/C are preserved, odd byte accesses are valid, and A7 byte update is two | 16/16/18/20/22/20/24 | PRM §4 BCHG pp. 4-26 to 4-29, BCLR pp. 4-30 to 4-33 and BSET pp. 4-55 to 4-56; MC68000 UM Rev. 9.1 Tables 8-1 and 8-8 pp. 8-2, 8-7. PC-relative, full-format and unlisted destinations remain unsupported |
| 68 | `CMP.{B,W,L} <data-alterable memory>,Dn` | All seven source EAs: `(An)`, `(An)+`, `-(An)`, `(d16,An)`, brief indexed, absolute short and absolute long; Dn minus source sets N/Z/V/C, X and operands are preserved; odd byte reads are valid, odd word/long addresses enter vector 3 before operand read, with postincrement committed per pinned MAME differential; A7 byte step is two | byte/word 8/8/10/12/14/12/16; long 14/14/16/18/20/18/22 | PRM §2.2.7 p. 2-9 and §4 CMP pp. 4-75 to 4-76; MC68000 UM Rev. 9.1 Tables 8-1 and 8-4 pp. 8-2, 8-4 |
| 69 | `BCLR/BSET #imm,Dn` | Static immediate bit number wraps modulo 32; BCLR clears or BSET sets the selected D0–D7 bit; Z reflects its old value and X/N/V/C are preserved | BCLR 14; BSET 12 | PRM §4 BCLR pp. 4-30 to 4-33 and BSET pp. 4-55 to 4-56; MC68000 UM Rev. 9.1 Table 8-8 p. 8-7 |
| 70 | `OR.{B,W,L} <data-alterable memory>,Dn` | Seven memory source EAs for byte/word/long; byte and word preserve the upper part of Dn, long replaces all of Dn; N/Z from result, V/C clear, X preserved; odd byte is valid, odd word/long uses vector 3 before operand access with postincrement committed per pinned MAME differential; host read-callback failures defer update; A7 byte update is two bytes | byte/word 8/8/10/12/14/12/16; long 14/14/16/18/20/18/22 | PRM §4 OR pp. 4-150 to 4-151; MC68000 UM Rev. 9.1 Tables 8-1 and 8-4 pp. 8-2, 8-4 |
| 71 | `LSL.L #1..8,Dn` | Full 32-bit register shifts left with zero fill; X/C receive the last bit shifted out, N/Z follow the result, V clears; count field zero means eight | 8+2n | PRM §4 LSL pp. 4-113 to 4-115; MC68000 UM Rev. 9.1 Table 8-7 p. 8-6 |
| 72 | `EXG Dx,Dy / Ax,Ay / Dx,Ay` | Three register-register modes exchange full 32-bit values across all D0–D7/A0–A7 pairs; condition codes are unchanged; exchanging A7 synchronizes the active SSP/USP bank | 6 | PRM §4 EXG pp. 4-104 to 4-105; MC68000 UM Rev. 9.1 Table 8-12 p. 8-10 |
| 73 | `SUBX.{B,W,L} Dm,Dn` | All D0–D7 source/destination pairs; subtracts Dm plus incoming X from Dn, preserves upper bits for byte/word, sets X/C on borrow, and keeps Z sticky for zero results; predecrement-memory forms remain unsupported | byte/word 4; long 8 | PRM §4 SUBX pp. 4-182 to 4-184; MC68000 UM Rev. 9.1 Table 8-11 p. 8-9; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 74 | `ADDX.{B,W,L} Dm,Dn` | All D0–D7 source/destination pairs; adds Dm and incoming X to Dn, preserves upper bits for byte/word, sets X/C on carry, and keeps Z sticky for zero results; predecrement-memory forms remain word-only | byte/word 4; long 8 | PRM §4 ADDX pp. 4-13 to 4-15; MC68000 UM Rev. 9.1 Table 8-11 p. 8-9; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 74 | `NOT.{B,W,L} <data-alterable EA>` | D0–D7 or one of seven memory EAs: `(An)`, `(An)+`, `-(An)`, `d16(An)`, brief `d8(An,Xn)`, absolute short or absolute long; complements the selected width, preserves Dn's upper bits for byte/word, sets N/Z from the result, clears V/C and preserves X; byte accesses permit odd addresses and A7 auto-steps by two; odd word/long operands enter vector 3 | Dn: 4/4/6; memory B/W: 12/12/14/16/18/16/20; memory L: 20/20/22/24/26/24/28 | PRM §4 NOT pp. 4-148 to 4-149; MC68000 UM Rev. 9.1 Tables 8-1 and 8-6 pp. 8-2, 8-6; owned CPU tests cover all widths/EAs, flags, exact timing, odd word/long auto-update fault boundaries and unsupported An/PC/immediate modes. Auto-update on odd read faults follows pinned MAME differential evidence only; the manuals do not establish that partial fault chronology (see [`ORACLE.md`](../tests/owned_cpu/ORACLE.md)) |
| 75 | `ADDI.{B,W,L} #imm` | all seven data-alterable memory EAs; immediate words before EA extensions; byte/word/long add with X/N/Z/V/C; odd word/long postincrement commit on vector 3 is pinned MAME differential only | byte/word 16/16/18/20/22/20/24; long 28/28/30/32/34/32/36 | PRM ADDI pp. 4-9 to 4-10; UM Rev. 9.1 Tables 8-5 p. 8-5 + 8-1 p. 8-2; pinned MAME `x0618_addi_b_pi_071234fc`, `x0658_addi_w_pi_071234fc`, `x0698_addi_l_pi_071234fc` for partial-update differential |
| 76 | `LSR.L #n,Dn` | immediate count 1–8; logical zero fill; X/C from the last shifted bit, N clear, Z from the result and V clear; ASR register-result forms are listed separately; register-count LSR, memory, ASL and rotate forms stay unsupported | 8+2n | PRM §4 LSL/LSR pp. 4-113 to 4-115; MC68000 UM Rev. 9.1 Table 8-7 p. 8-6; tests cover all registers/counts and neighboring encodings |
| 77 | `BTST Dm,<data-alterable memory>` | Dynamic Dm bit number modulo eight tests one byte across `(An)`, `(An)+`, `-(An)`, `d16(An)`, brief `d8(An,Xn)`, absolute short and absolute long; Z alone changes, no memory write occurs, and A7 byte auto-update steps by two; PC-relative and dynamic bit-modify forms remain outside this bounded slice | 8/8/10/12/14/12/16 | PRM §4 BTST pp. 4-61 to 4-62; MC68000 UM Rev. 9.1 Tables 8-1 and 8-8 pp. 8-2, 8-7 |
| 78 | `MOVEA.W #imm,An` | A0–A7; fetches one immediate word and sign-extends it to the full 32-bit address register; condition codes are unchanged and A7 updates synchronize the active stack bank. Exact counter preflight follows the extension fetch; two word reads and no writes | 8 | PRM §4 MOVEA pp. 4-119 to 4-120; MC68000 UM Rev. 9.1 Table 8-3 p. 8-3 |
| 78 | `EXT.W/L Dn` | D0–D7; EXT.W sign-extends the low byte into the low word, preserving the upper word; EXT.L sign-extends the low word to all 32 bits. N/Z follow the result width, V/C clear and X is preserved. The bounded regression covers sign/zero boundaries, every register, X set/clear, upper-bit and flag effects, opcode-only access and 4-cycle timing; An-direct encodings remain unsupported | 4 / 4 | PRM §4 EXT, printed p. 4-106; MC68000 UM Rev. 9.1 Table 8-12, printed p. 8-10; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 79 | `ORI/ANDI/EORI.B #imm,CCR` | Special immediate-to-CCR forms; update only X/N/Z/V/C and ignore immediate bits 7–5; preserve upper SR and are legal in user mode. The owned core retains any nonzero reserved CCR bits supplied by state restore; that state-model behavior is not a hardware claim. Each takes 20 clocks | 20 | PRM §1.1.4; ORI pp. 4-154 to 4-155, ANDI pp. 4-19 to 4-20, EORI pp. 4-103 to 4-104; MC68000 UM Rev. 9.1 Table 8-12 p. 8-10 |
| 80 | `ADDA.{W,L} <data-alterable memory>,An` | Seven source EAs: `(An)`, `(An)+`, `-(An)`, `d16(An)`, brief `d8(An,Xn)`, absolute short and absolute long; word sources sign-extend before the 32-bit sum, long sources use all bits, and SR is unchanged. Brief indexes allow Dn/An word/long with no scaling; A7 updates synchronize SSP. Odd word/long addresses enter vector 3 before operand access; PI/PD partial updates on that path follow pinned MAME differential evidence only. Terminal host callback faults keep the owned-core contract: PD is applied before the read, PI after the full source read. PC-relative, full-format and other unlisted memory source forms remain unsupported; direct Dn/An and immediate word forms are listed separately | word 12/12/14/16/18/16/20; long 14/14/16/18/20/18/22 | PRM §§2.2.4, 2.2.7, 2.2.10 and §4 ADDA pp. 2-6, 2-9, 2-14, 4-7 to 4-8; MC68000 UM Rev. 9.1 Tables 8-1 and 8-4 pp. 8-2, 8-4; pinned MAME ADDA handlers are differential evidence only (see [`ORACLE.md`](../tests/owned_cpu/ORACLE.md)) |
| 81 | `SUBI.{B,W,L} #imm,<data-alterable memory>` | Seven memory destinations: `(An)`, `(An)+`, `-(An)`, `d16(An)`, brief `d8(An,Xn)`, absolute short and absolute long. Fetches the width-sized immediate before destination EA extensions, then reads, subtracts and writes at that width; updates X/N/Z/V/C from destination minus immediate; byte immediate uses the low extension byte and A7 byte auto-update steps by two. Odd word/long targets enter vector 3 before operand access; retained PI/PD updates are pinned MAME differential evidence only. Terminal read/write callback faults keep the owned-core contract and remain distinct from vector 3. PC-relative, immediate, An-direct and reserved-size forms stay unsupported | byte/word 16/16/18/20/22/20/24; long 28/28/30/32/34/32/36 | PRM §4 SUBI pp. 4-179 to 4-180; MC68000 UM Rev. 9.1 Tables 8-5 p. 8-5 and 8-1 p. 8-2; pinned generated MAME SUBI PI/PD handlers are differential evidence only (see [`ORACLE.md`](../tests/owned_cpu/ORACLE.md)) |
| 82 | `ADDQ/SUBQ.W/L #1..8,An` | A0–A7 use full-width 32-bit arithmetic even for encoded word size; SR is unchanged, quick field zero means eight, and only the opcode is fetched. The selected implementation uses 8 clocks for all four forms. ADDQ.W timing conflicts: Motorola/NXP UM Rev. 9.1 Table 8-5 and pinned MAME cycle data give 4; Rockwell International 1985 *R68000 16-Bit MPU Data Book* Table 27, printed p. 1-47, gives 8 for word-only An (scanned-source SHA-256 `b3212359327ef2f8c1e219385e51aebb23a76885c1f9b6e355f1cf01a53620ff`). Target-specific Yacht v1.1 analysis at immutable revision `349371ba938863b0c9e41c5a821a1434ed15cb34` uses the Motorola patent's microcode to argue that the UM entry is erroneous and claims real-hardware evaluation confirms 8; its document gives no chip revision, test setup, or raw measurement, and we have not reproduced its analysis or measurement ([Yacht, lines 941–977](https://github.com/larsbrinkhoff/m68k-microcode/blob/349371ba938863b0c9e41c5a821a1434ed15cb34/doc/Yacht.txt#L941-L977)). The test documents this implementation's selected timing, not hardware proof. A7 writes synchronize the active stack bank. Byte An forms and other unlisted EAs remain unsupported | 8 | PRM §4 ADDQ pp. 4-11 to 4-12 and SUBQ pp. 4-181 to 4-182; UM Rev. 9.1 Table 8-5 p. 8-5; Rockwell 1985 Table 27 p. 1-47; pinned MAME revision `31e52312c59e4d60d70235118bcbccd220f5232e` (conflicting cycle data) |
| 83 | `EOR.{B,W,L} Dn,<data-alterable memory>` | XORs the destination width using D0–D7 as source; X is preserved, N/Z follow the result, V/C clear. Supports `(An)`, `(An)+`, `-(An)`, `d16(An)`, MC68000 brief index, absolute short and absolute long; byte A7 updates by two. Word/long odd PI/PD partial updates are pinned-MAME differential evidence only. Host callback failures follow the tested core contract; long split-access order is owned-core behavior, not a hardware subcycle claim. CMPM mode 001 remains a separate supported byte/word handler; other unlisted EOR modes remain unsupported | B/W: 12/12/14/16/18/16/20; L: 20/20/22/24/26/24/28 | PRM §4 EOR pp. 4-99 to 4-101; MC68000 UM Rev. 9.1 Tables 8-1 and 8-4 pp. 8-2 and 8-4; [pinned MAME handlers](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/cpu/m68000/m68kops.cpp#L13662-L13957); [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 84 | `SBCD.B Dm,Dn` | Register-direct byte form only; all D0–D7 pairs and aliases use valid packed-BCD destination−source−X. Low byte is written, upper Dn bits preserved; C/X are decimal borrow and Z is sticky. N/V are undefined in PRM §4 and are left unchanged as a deterministic implementation choice; invalid BCD data is unqualified. Predecrement-memory form remains unsupported | 6 | PRM §4 SBCD pp. 4-169 to 4-170; MC68000 UM Rev. 9.1 Chapter 8 Table 8-11 p. 8-9; [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 85 | `ADDA.{W,L} Dm/Am,An` | All D0–D7/A0–A7 source and A0–A7 destination pairs; word source is sign-extended, long source uses all 32 bits, full-width sum replaces An, SR unchanged. Includes same-An source/destination aliases and active supervisor/user A7 bank updates; only the opcode is fetched, no data writes. Both widths use eight clocks under the UM Table 8-4 register-direct timing/footnote | 8 | PRM §4 ADDA pp. 4-7 to 4-8; MC68000 UM Rev. 9.1 Table 8-4 p. 8-4 (`8(1/0)+` word; long `6(1/0)+**`, register-direct footnote raises it to 8) |
| 86 | `CLR.{B,W,L} Dn` | D0–D7; clears only the selected operand width, preserving upper bits for byte/word; N/V/C clear, Z set, X preserved. Opcode fetch only, no operand access/write. An-direct, PC-relative, immediate and other unlisted EAs remain unsupported | byte/word 4; long 6 | PRM §4 CLR pp. 4-73 to 4-74; MC68000 UM Rev. 9.1 Chapter 8 Table 8-6 p. 8-6 |
| 87 | `MULS.W / MULU.W <ea>,Dn` | Word forms support Dn, seven data-alterable memory EAs, PC-relative displacement/brief index, and immediate sources. MULS is signed and MULU unsigned; both write the full 32-bit result, preserve X, derive N/Z from the result and clear V/C. Source-dependent timing is `38+2n` plus source-EA clocks: MULS counts adjacent 10/01 transitions with a zero LSB appended, MULU counts source one bits. The operand/extension is acquired before exact timing counter preflight; An-direct and reserved sources remain unsupported | `38+2n+EA` | PRM §4 MULS pp. 4-135 to 4-136 and MULU pp. 4-138 to 4-139; MC68000 UM Rev. 9.1 Chapter 8 Tables 8-1 p. 8-2 and 8-4 p. 8-4 |
| 88 | `DIVU.W <readable EA>,Dn` | Admits Dn, all seven data-alterable memory EAs, PC-relative displacement/brief index, and immediate; An-direct, reserved/full-format PC index, and DIVS sources other than its separately listed Dn-direct and immediate forms remain unsupported. Divides the unsigned 32-bit Dn by the word divisor; quotient replaces the low word and remainder the high word. Success preserves X, sets N/Z from quotient and clears V/C. Unsigned quotient overflow leaves Dn unchanged, sets V and clears C; undefined N/Z are retained deterministically. Zero divisor enters vector 5 after source acquisition and saves the PC after source extensions; defined C clears and X is preserved. Source acquisition precedes exact timing/counter preflight; successful auto-updates wait until preflight, vector-3 partial updates follow the owned-core address-error contract rather than a manual chronology claim, and terminal host-read/counter failures leave the base register unchanged | Normal: 76–136 variable + EA; overflow: 10 + EA; zero-divide exception: 38 + EA | PRM §4 DIVU pp. 4-96 to 4-97; MC68000 UM Rev. 9.1 Tables 8-1 p. 8-2, 8-4 p. 8-4 and 8-14 p. 8-11; [Cwik's July 2005 MC68000 timing report](https://forums.tomshardware.com/threads/68000-divu-divs-cycle-accurate-timing.135309/) (partially hardware-tested; GPL-2.0-or-later source SHA-256 `e37f98a5ddbba2ab78a9ddd5587df581698450fdd840dfbdf7a536cf8ef2d3ba`; no source code included). Selected variable timing conflicts with the UM maximum/under-10%-spread note and is not hardware proof |
| 88a | `DIVS.W <Dn or #data>,Dn` | Dn-direct and immediate word sources only; sign-extends the low-word divisor and divides the signed 32-bit destination. Success packs quotient low/remainder high with dividend-signed remainder, preserves X, sets N/Z from quotient and clears V/C. Overflow preserves the destination and sets V; zero enters vector 5 after source acquisition, saving PC after any immediate extension, with N/Z/V undefined and C cleared. Undefined flags are retained deterministically. Other source modes remain unsupported | 120–156 clocks for iterative signed division, 16–18 early absolute overflow, 38 divide-by-zero exception; immediate source adds four EA clocks | PRM §4 DIVS pp. 4-92–4-95; MC68000 UM Rev. 9.1 Tables 8-1 p. 8-2, 8-4 p. 8-4 and 8-14 p. 8-11; Cwik July 2005 timing report (partially hardware-tested; GPL-2.0-or-later SHA-256 `e37f98a5ddbba2ab78a9ddd5587df581698450fdd840dfbdf7a536cf8ef2d3ba`; independently reimplemented) |
| 89 | `ASR.{B,W,L} #1..8,Dn / Dm,Dn` | Immediate-count and Dn-count forms across byte, word and long; immediate zero means eight and register count is modulo 64. Right shift fills from the operand sign; byte/word preserve Dn upper bits. For nonzero counts C/X take the last bit shifted out; for zero C clears while X is unchanged. V clears and N/Z follow the result; ASR.W memory is separately listed; byte/long memory ASR and ASL stay unsupported | B/W 6+2n; L 8+2n | PRM Section 4 ASL/ASR pp. 4-20 to 4-22; MC68000 UM Rev. 9.1 Table 8-7 p. 8-6; tests cover all register pairs/widths, count boundaries, flags, timing, opcode-only access and counter-overflow preflight |
| 89a | `LSR.W <data-alterable memory>` | Added this bounded word-memory form after the no-input continuation exposed it. Supports `(An)`, `(An)+`, `-(An)`, `d16(An)`, brief `d8(An,Xn)`, abs.W and abs.L. Logical right shift with zero fill; C/X take old bit 0, N clears, Z follows the result, V clears. ASR.W memory is separately listed; other unlisted memory shifts remain unsupported. Exception/callback chronology is the owned-core contract, not a hardware bus-cycle claim | 12/12/14/16/18/16/20 clocks in the seven EA order above | PRM §4 LSL/LSR pp. 4-113 to 4-115; MC68000 UM Rev. 9.1 Tables 8-1 and 8-7 pp. 8-2, 8-6; tests cover all seven EAs, flags, ordered word read/write, exact timing, preflight, callback failure, odd address and unsupported neighbors |
| 89b | `ASR.W <data-alterable memory>` | One-bit arithmetic right shift with sign fill; C/X take old bit 0, N/Z follow the word result and V clears. Supports `(An)`, `(An)+`, `-(An)`, `d16(An)`, MC68000 brief `d8(An,Xn)`, abs.W and abs.L. The successful-access matrix covers every EA and address register, result/flag boundaries and exact cycles; it establishes no odd-address or terminal callback chronology. Byte/long memory ASR and other unlisted shifts remain unsupported | 12/12/14/16/18/16/20 clocks in the seven EA order above | PRM §4 ASL/ASR pp. 4-20 to 4-22; MC68000 UM Rev. 9.1 Tables 8-1 and 8-7 pp. 8-2, 8-6; see the source-qualified regression ancestry in [`ORACLE.md`](../tests/owned_cpu/ORACLE.md) |
| 90 | `MOVE.L <readable memory>,Dn` | All seven data-alterable memory sources plus PC-relative d16/brief index to D0–D7; Dn/An direct and immediate sources are separately admitted. Two ordered word reads replace Dn; N/Z follow the longword, V/C clear, X preserved. EA extensions precede counter preflight. A7 updates synchronize the active stack bank. Odd PI/PD vector-3 base updates follow exact pinned MAME handlers `x2018`/`x2020` as differential behavior only; on host read-callback failure PD is committed and PI waits for both successful words | `(An)/(An)+/-(An)/d16/index/abs.W/abs.L`: 12/12/14/16/18/16/20; PC d16/index: 16/18 | PRM §§2.2.4, 2.2.7, 2.2.12 and §4 MOVE pp. 2-6, 2-9, 2-14, 4-116 to 4-118; MC68000 UM Rev. 9.1 Table 8-3 p. 8-3; pinned MAME revision `31e52312c59e4d60d70235118bcbccd220f5232e`, differential chronology only |
| 91 | `PEA <control EA>` | `(An)`, `d16(An)`, brief `d8(An,Xn)`, abs.W/abs.L, PC displacement and brief PC index calculate the full effective address without reading operand memory, then push it as a longword; flags are unchanged. PC-relative forms use the extension-word address. The source A7 value is sampled before the stack decrement and active SSP/USP is synchronized. Extensions precede timing/counter preflight; the stack is unchanged on preflight failure. Odd post-push SP takes vector 3. On host push failure the current helper has already decremented A7, then attempts high word before low; this is an owned callback contract, not an inferred hardware bus order. Postincrement, predecrement, immediate, full-format index and unlisted forms remain unsupported | `(An)` 12; d16/index/abs.W/PC d16/PC index 16–20; abs.L 20 | PRM §§2.2.4, 2.2.7, 2.2.11–2.2.12 and §4 PEA p. 4-159; MC68000 UM Rev. 9.1 Table 8-10 p. 8-8; regressions cover the seven legal control EAs, no operand reads, A7 alias/bank, fault/preflight order and exact read/write totals |
| 92 | `NEGX.{B,W,L} <data-alterable memory>` | All three memory sizes across `(An)`, `(An)+`, `-(An)`, `d16(An)`, brief index, absolute short and absolute long; `0-destination-X` writes the width-limited result, X=C on borrow, N from result, V on signed overflow and Z remains set only if it was already set and the result is zero. A7 byte auto-update steps by two; odd bytes are valid and odd word/long addresses enter vector 3 before operand access. Dn/An-direct, PC-relative, immediate and invalid-size forms remain outside this family | Byte/word 12/12/14/16/18/16/20; long 20/20/22/24/26/24/28 clocks | PRM §4 NEGX p. 4-146; MC68000 UM Rev. 9.1 Tables 8-1 p. 8-2 and 8-6 p. 8-6; `negx_long_displacement_memory_uses_24_cycles_and_long_flags` and `negx_memory_byte_word_long_cover_all_data_alterable_eas` cover the observed long displacement form and all seven EAs/three widths; word odd-address vector entry remains a separately tested owned-core boundary |
| 98 | `NEG.{B,W,L} <data-alterable memory>` | Supports all seven data-alterable memory EAs for each width; computes 0 minus the width-limited operand, sets X=C when nonzero, N/Z from the result and V on signed overflow. Odd byte access is valid, A7 byte auto-update is two, and odd word/long operands enter vector 3 before operand access. Dn-direct is separate; An-direct, PC-relative, immediate and reserved sizes remain unsupported | B/W: 12/12/14/16/18/16/20; L: 20/20/22/24/26/24/28 | PRM §4 NEG pp. 4-142–4-144; MC68000 UM Rev. 9.1 Tables 8-1 and 8-6 pp. 8-2, 8-6; regressions cover the observed long displacement form, all widths/EAs, flags, ordered accesses and odd-word boundary |
| 93 | `TST.L d16(An)` | A0–A7 with a signed displacement; one aligned long operand read as two words; N/Z follow the long value, V/C clear, X preserved, and An/memory unchanged. Odd word alignment enters vector 3 before operand access; brief-indexed mode is listed separately and other long EAs remain outside the subset | 16 | PRM §4 TST pp. 4-192 to 4-193; MC68000 UM Rev. 9.1 Tables 8-6 p. 8-6 and 8-1 p. 8-2; test `tst_long_displacement_memory_uses_16_cycles_and_flags_for_all_address_registers`; [official NXP manuals](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf) and [MC68000 UM](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 94 | `CLR.B (An)` | A0–A7; reads one byte before writing zero, sets Z, clears N/V/C and preserves X. Odd byte addresses are valid; An is unchanged. This row is limited to the observed address-indirect mode | 12 | PRM §4 CLR pp. 4-73 to 4-74; MC68000 UM Rev. 9.1 Tables 8-6 p. 8-6 and 8-1 p. 8-2; test `clr_byte_address_indirect_reads_then_clears_for_all_registers`; [official NXP manuals](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf) and [MC68000 UM](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 95 | `ORI.W #imm,Dn` | D0–D7; immediate word ORs into Dn[15:0], preserves Dn[31:16] and X, sets N/Z from result, clears V/C | 8 | PRM §4 ORI pp. 4-153 to 4-154; MC68000 UM Rev. 9.1 Table 8-5 p. 8-5 (8(2/0)); [official NXP manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 96 | `AND.{B,W,L} Dn,<data-alterable memory>` | Supports `(An)`, `(An)+`, `-(An)`, `d16(An)`, brief indexed, absolute short and absolute long destinations for D0–D7. It ANDs the selected memory width with Dn, leaves Dn unchanged, sets N/Z from the result, clears V/C and preserves X. A7 byte auto-update steps by two. PC-relative/immediate destinations remain unsupported; `AND.W Dn,(An)+` is covered by its separately qualified handler | Byte/word: 12/12/14/16/18/16/20; long: 20/20/22/24/26/24/28 | PRM §4 AND pp. 4-15 to 4-17; MC68000 UM Rev. 9.1 Tables 8-1 p. 8-2 and 8-4 p. 8-4 (`AND Dn,<M>` base 8/12 clocks plus destination-EA cost); [official NXP manuals](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf) and [MC68000 UM](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 97 | `EOR.L Dm,Dn` | D0–D7 source and destination; full-width XOR, N/Z from the result, V/C clear, X preserved; one opcode-word read and no data access | 8 | PRM §4 EOR pp. 4-99 to 4-101; MC68000 UM Rev. 9.1 Table 8-4 p. 8-4 (8(1/0), footnote ***); [official NXP manuals](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf) and [MC68000 UM](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |
| 98 | `TST.L (d8,An,Xn)` | A0–A7 plus the MC68000 brief extension with Dn/An word or long index and signed 8-bit displacement; one aligned long operand read as two words, N/Z from the value, V/C clear and X preserved; no register or memory writes. Odd operands enter vector 3 before data access; PC-indexed and full-format extensions remain outside the admitted form | 18 | PRM §§2.2.7 and 4 TST pp. 2-9, 4-192 to 4-193; MC68000 UM Rev. 9.1 Tables 8-1 and 8-6 pp. 8-2, 8-6; test `tst_long_address_index_uses_18_cycles_for_all_register_forms`; [official NXP manuals](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf) and [MC68000 UM](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) |

`SUB.B Dm,Dn` is a 4-clock data-register-direct subtraction (one opcode read,
no operand read or write; MC68000 User's Manual Rev. 9.1 Table 8-4, p. 8-4).
Only Dn's low byte changes; N/Z/V/C follow the byte result and X follows borrow
(M68000 Family PRM §4 SUB, p. 4-174). The regression
`sub_byte_data_register_to_data_register_covers_registers_and_flags` covers all
64 Dm/Dn pairs, flags and upper-byte preservation. The owned core also admits
`SUB.{B,W,L} <ea>,Dn` for all seven data-alterable memory source EAs, PC-relative
displacement and brief-indexed sources, and immediate sources; it admits
`SUB.{W,L} Am,Dn` while byte An-direct remains illegal. The matching source
family tests cover width masking, timing, flags, auto-update aliases and odd
word/long address errors. Memory destinations, full-format index extensions and
byte An-direct remain unsupported.

`SUB.W Dm,Dn` performs a 4-clock data-register-direct subtraction (one opcode
read, no operand read or write; MC68000 User's Manual Rev. 9.1 Table 8-4,
p. 8-4). Only Dn's low word changes; flags follow the word result, with X
following borrow (M68000 Family PRM §4 SUB, pp. 4-174 to 4-175). The regression
`sub_word_data_register_to_data_register_subtracts_all_pairs_in_4_cycles`
covers all 64 Dm/Dn pairs, flags and upper-word preservation. The source-EA
family is described above; `SUBA` and `SUBX` remain distinct encodings and
handlers.

`SUBX.{B,W,L} Dm,Dn` subtracts the source register and incoming X from the
destination for all D0–D7 pairs. Byte/word writes preserve the destination's
upper bits; C and X report borrow, N/V follow the width-limited result, and Z
remains set only when it was already set and the result is zero. The register
forms take 4 clocks for byte/word and 8 for long (MC68000 UM Rev. 9.1
Table 8-11, p. 8-9; PRM §4 SUBX, pp. 4-182 to 4-184). Regression
`subx_register_data_register_widths_use_sticky_zero_and_manual_cycles` covers
all register pairs, both X inputs, sticky-Z, full-width borrow and overflow;
the predecrement-memory forms remain unsupported.

`ADDX.{B,W,L} Dm,Dn` adds the source register and incoming X to the destination
for all D0–D7 pairs. Byte/word preserve the destination's upper bits; C and X
report carry, N/V follow the width-limited result, and Z remains set only when
it was already set and the result is zero. The register forms take 4 clocks
for byte/word and 8 for long (MC68000 UM Rev. 9.1 Table 8-11, p. 8-9; PRM
§4 ADDX, pp. 4-13 to 4-15). Regression
`addx_register_data_register_widths_use_sticky_zero_and_manual_cycles` covers
all register pairs and widths, X input, sticky-Z, carry/overflow, preserved
upper bits and exact clocks; `addx_register_direct_counter_preflight_preserves_operands`
checks budget-counter overflow before operand mutation. The word
predecrement-memory form remains separately supported; byte/long memory forms
remain unsupported.

Boundaries kept on purpose: a different size, a different EA mode or a
different mnemonic of the same family still ends the run as
`OWNED_CPU_UNSUPPORTED_OPCODE`; `MOVEA.L (d8,PC,Xn),An` rejects extension words
with bits 10-8 set (scale or full-format words are not MC68000 encodings).
Two older tests changed a neighbor control because the control encoding became
an admitted one (`MOVE.L An,Dn` and `MOVE.W (An)+,Dn`); each now points at a
still-unsupported encoding.
Plan 05-20 rows 13-19 continue the same discipline on the Section 8 baseline.
Two more neighbor controls moved because their encodings became admitted
(`MOVE.B Dn,Dn` in the `MOVE.W Dn,Dn` test and `CLR.B (xxx).L` in the CLR
neighbor table). `BRA.W` and `BSR.B` stay unsupported; displacement byte `0xff`
is treated as -1 like the existing Bcc byte form, because the 32-bit
displacement belongs to later family members.

Historical implementation sequence: the early selected-media checks exposed
branch forms, BIOS memory-test/input behavior, calendar access and status-byte
reads while the owned CPU subset expanded. The instruction tables and cited
regressions retain their own supported scope; those intermediate stops do not
describe the current first blocker. See
[retired Phase05 validation](../.planning/milestones/ws-first-playable-game-2026-10-24/retired/2026-10-16-development-workflow/phase05/05-VALIDATION.md)
for the dated observations and moved-neighbor controls.

The observation-count limits, plan ownership handoffs and stop/replan rules in
that record are retired. Current development follows
[DEVELOPMENT.md](../.planning/milestones/ws-first-playable-game-2026-10-24/DEVELOPMENT.md).
GAME-02 remains Pending; historical checks never established attract/start.

### Exception-entry timing table selection

Corrected baseline in force (plan 05-18, 2026-10-12): the owned CPU charges
the MC68000 16-bit-bus values of M68000 User's Manual Rev. 9.1 Section 8,
Table 8-14 (printed p. 8-11): reset 40(6/0), autovector interrupt 44(5/3)
(footnote: acknowledge assumed 4 clocks), address and bus error 50(4/7), and
illegal-instruction, privilege-violation and TRAP exceptions 34(4/3). The
selected Neo Geo processor is a 16-bit-bus 68000, so Table 8-14 applies.

History: plan 05-03 had charged reset 64, interrupt 72, address error 94 and
instruction exceptions 62. Plan 05-11 re-read the manual and found these are
the numbers of Table 7-15 (printed p. 7-11); UM Section 7 is titled "8-Bit
Instruction Execution Times" for the MC68008 and for the MC68HC001/MC68EC000 in
8-bit mode. Plan 05-18 moved the CPU constants and every dependent expectation
together as one intentional, test-first baseline change; each changed
expectation is listed in `tests/owned_cpu/ORACLE.md`, section
"Exception-entry baseline correction — 2026-10-12". The VBlank/frame-phase
expectations pinned by plan 05-10 are frame-clock positions (S8-S10), not CPU
charges, and did not change; only the interleaving of guest execution against
them moves.

Plan 05-19 re-pointed every older instruction-timing citation, which named
Section 9 tables (the MC68010), to the MC68000 Section 8 table and printed
page, and recorded each site in `tests/owned_cpu/ORACLE.md`, section
"Section 8 citation audit — 2026-10-12". Five clock values differed and were
corrected test-first: Bcc byte not taken 8 (was 6), Bcc word not taken 12 (was
10), DBcc counter expired 14 (was 16), `MOVE.B Dn,(xxx).L` 16 (was 12) and
`MOVEA.L (An)+,An` 12 (was 14, Table 8-3 misread). Bcc/BRA taken forms and the
other audited rows already equalled Section 8. Plan 05-19 also keeps the banked
stack pointer of the active mode equal to A7 after every address-register
write, so a state captured after any A7 write restores and a later mode switch
exposes the written value; JSR/BSR/RTS in user mode use the user stack.

## Input, status and calendar

Plan 05-12 implements only the I/O register the selected boot demanded. The
rerun of the selected media after the 05-20 encodings stalled in a loop that
polls `$300001` (REG_DIPSW) while the BIOS alternates its work-RAM and
backup-RAM tests; that read had been answered from cartridge program bytes
because the old program window ran past `$2fffff`.

| Register | Address (mask) | Read value | Source |
|---|---|---|---|
| REG_DIPSW | `$300001` (decode `0x01ff7e` mirror) | `0xff`: every switch in its default Off/Normal/Joystick/cabinet-1 position, active low | S18, S18b, S19-S19g, S20, S20b |
| TEST input port (low byte) | `$300081` (decode `0x01ff7e` mirror) | `0x80` with no host input: active-high unused bits and the callback-free JAMMA sense bit read low; active-low service input is released high | S20c-S20d |
| REG_STATUS_A (byte) | `$320001` (decode `0x01fffe` mirror) | bits 0-4 `1` (coin 1, coin 2, service and two unused-low bits, nothing pressed); bit 5 `0` (4-slot sense, no handler); bit 6 uPD4990A time pulse; bit 7 uPD4990A data out | S22-S22j |
| REG_STATUS_B (high byte) | `$380000` (decode `0x01fffe` mirror, even-byte lane only) | `0xff`: released start/select bits 0-3, absent-card status 7 in bits 4-6, MVS type 1 in bit 7 | S23-S23i |

The value is the pinned MAME DSW port default, not a measured MVS board
setting; the wiki names the register and polarity only. The byte is constant per
instance: it is not state, reset does not change it, and nothing reads the host.
Writes at `$300001` remain the watchdog kick implemented earlier.

The TEST value follows the pinned MAME `TEST` input declaration (S20d), not a
physical-board measurement. With no host input, bits 0-5 are inactive
`IPT_UNUSED` fields and bit 6 is an `IPT_CUSTOM` JAMMA sense field with no
callback in this profile, so both contribute zero; the active-low service bit
7 is released and contributes `0x80`. Only the low-byte lane is served at
`$300081` and its `0x01ff7e` mirrors. The high-byte lane at `$300080` and word
reads remain faults. This is a pinned-reference default, not a claim about a
physical MVS input state.

REG_STATUS_A (plan 05-22 rerun 13) is the low byte of the pinned MAME
`AUDIO_COIN` port. The selected set (`mslugx`) uses the `neogeo` input ports
(S22i), so bits 3 and 4 are unused and read high; the `neogeo_mvs` variant makes
them coin 3 and 4, active low, which reads the same with nothing pressed. Bit 5
is a custom sense bit with no handler and reads 0 in the pinned source; whether
the physical board senses 4 or 6 slots is not established. Data out is returned
as the pin level because output enable is held high at machine start (S22j). The
public MVS input API can press coin 1 at bit 0; coin 2, service and bits 3-5
remain unchanged. The byte is read live from the calendar pins and per-instance
input state, mutates nothing and returns to released coin 1 on reset or load.
The high byte (`$320000`, the sound reply) is not served and stays a recorded
fault.

REG_STATUS_B (plan 05-25 rerun 25) is the high byte of the pinned MAME
`SYSTEM` port. With no host input, start and select lines are released, the
memory card is absent, and the hardware-type bit identifies MVS. The public
MVS input API can press P1 Start at bit 0; all other `SYSTEM` bits remain
unchanged. Reads mutate nothing, and reset or load releases the start line.
Only the observed high-byte lane is served; low-byte and word reads remain
faults.
S23-S23i were fetched on 2026-10-13; the system port, its callbacks and the
arcade joystick input definitions were inspected. This is reference-emulator
differential evidence, not a physical-board measurement.

With no host input asserted, P1 control reads at `$300000` and their
`0x01ff7e` mirrors return `0xff`; `$300001` exposes the default DSW byte, and
word reads combine the released P1 controls with that DSW. P2 control reads at
`$340000` and their `0x01fffe` mirrors return `0xff` on either byte lane and
`0xffff` as a word. This records only the no-host-input idle values, not a
general input-device response. The public held mask now drives P1 UP, DOWN,
LEFT, RIGHT, A, B, C and D as active-low bits 0-7 of the high byte at
`$300000`; the odd-byte lane at `$300001` and the low byte of word reads remain
the default DSW value. The line assignment follows pinned MAME
`neogeo_joy_ac` P1 port definitions (S41) and its edge input to word mapping
(S20). This is reference-emulator differential evidence, not a physical-board
measurement. Unsupported neighbors including `$300080`
(the unserved high-byte lane of the separate TEST decode, S20c) and `$380001`
(system-status low byte) still fault with a recorded address, access and
width; word reads of system status also remain unsupported. The
`--board-behavior` `io-status` group asserts DIPSW and TEST defaults through
mirrors, per-instance repeat/reset behavior and faults for unsupported
neighbors. At this historical pre-integration point, sound handshake and audible
output were unqualified. Current native/actual-frontend machine outcomes and the
separate physical listening observation are scoped above.

### Host input and PLAYER_START observation (plan 05-14)

`gn_set_mvs_inputs` accepts coin 1, P1 Start and all eight P1 direction/button
lines for this bounded profile. The mask is the complete per-instance held
state: a subsequent mask replaces it, zero releases every line, and unsupported
bits are rejected without changing the prior state. Inputs clear after a
successful MVS load or `gn_reset`. Coin 1 drives active-low bit 0 of
REG_STATUS_A at `$320001` (S27, S27b, S30); P1 Start drives active-low bit 0
of the REG_STATUS_B high byte at `$380000` (S28, S28b, S30b, S30c). The other
bits keep their prior idle or calendar-derived values. MAME's `SYSTEM` start
bits are callbacks (S30b), so the bit mapping is supported here by the fetched
memory-register definition and joystick START declaration (S28, S28b, S30c),
not by a claim of hardware equivalence.

For the adapter's Classic RetroPad mapping, Up/Down/Left/Right map directly to
the P1 directions; RetroPad B/A/Y/X map to Neo Geo P1 buttons A/B/C/D; Select
maps to Coin1 and Start maps to P1 Start. Input descriptors name the emulated
hardware lines. RetroArch owns physical-device bindings and remapping. These
line names do not assert title-specific action meanings; selected-title action
labels beyond the bounded firing observation and complete actual frontend
acceptance remain unverified; see the Phase06 scene scope above.

The progress observer latches an accepted BIOS request followed by the
cartridge USER entry, any instruction start at the documented cartridge
PLAYER_START header offset `$000128`, and whether that fetch follows distinct
host coin-1 and then P1 Start press edges after attract. S29 documents that the
System ROM also calls PLAYER_START on title timeout. Therefore
`player_start_entered` reports the guest transfer alone. The version-1 public
field `player_start_with_p1_indication` requires a BIOS-region guest write of
P1 bit 0 set in `BIOS_START_FLAG` ($10FDB4.b, S29b) after the latest ordered host
coin/Start press edges and before the transfer. A later clear or cartridge
write invalidates the candidate; a new Start edge requires a new indication.
Byte writes and the high byte of aligned word writes use the same P1 bit.
The observer latches the first qualifying transfer until successful load/reset.
This conservatively distinguishes an unindicated timeout from the documented
BIOS P1 Start indication. It does not prove game acceptance, credit deduction,
or physical causality, and may miss BIOS implementations that do not write the
indication in that interval. The field was renamed before any SDK release;
its layout and observation prefix size are unchanged. Synthetic guests cover
input-dependent and timer-only paths, including polling-but-ignored inputs.
The BIOS credit counter and physical-board input behavior remain unverified.
All source rows are fetched and digest-checked by `tools/mvs/check_sources.py`.

### uPD4990A calendar (plan 05-21)

The selected boot's first access after the owned 68000 encodings of plan 05-21
was a byte write at `$380051`, the calendar control byte. Plan 05-21 rerun 8
implements the write side and the chip behind it. The chip's two output pins
(data out and time pulse) are read through the status register at `$320001`
since plan 05-22 rerun 13 (REG_STATUS_A, above).

| Item | Value | Source | Evidence class |
|---|---|---|---|
| Control byte | byte write at `$380051` (offset `0x28` of the `$380000-$3800ff` window, mirrored by `0x01ff00`; even addresses are not mapped); bit 0 data in, bit 1 clock, bit 2 strobe | S21, S21b, S21c | MAME differential |
| Mode | chip select and output enable high, command pins high: serial mode, so the command is the 4-bit serial command register | S21d, S21e, S21f | MAME differential |
| Serial protocol | each clock rising edge shifts the command register right (new data bit enters at bit 3) and emits its low bit; in shift mode that bit enters the top of the 48-bit shift register, which shifts right; a strobe rising edge executes the command in the command register | S21f, S21g, S21h, S21u | MAME differential |
| Commands | 0 register hold, 1 shift, 2 time set, 3 time read, 4-7 time pulse 64/256/2048/4096 Hz, 8-11 time pulse 1/10/30/60 s, 12-14 no effect (marked TODO in the pinned source); 15 (test mode) is not modeled and is a recorded bus fault on the strobe write | S21l, S21m, S21n, S21o, S21p, S21q | MAME differential |
| Time base | the chip clock is 32,768 Hz (S21j); the 68000 runs at 12 MHz (S9b), so a chip tick is 46875/128 68000 clocks and one second is exactly 12,000,000 executed clocks; the per-instance integer remainder is carried and no host clock is read | S21i, S21j, S9b | MAME differential, derived |
| Calendar carry | seconds, minutes, hours, day, month and a two-digit year carry with the pinned days-per-month table; no leap year | S21r, S21s, S21t | MAME differential |
| Field layout | six bytes: seconds, minutes, hours, day (BCD), month in the high nibble with the weekday in the low nibble, year (BCD) | S21k | MAME differential |

Power-on seed: `GN_MVS_CALENDAR_EPOCH` (defined only in `src/sdk_private.h`) is
2000-01-01 00:00:00 in that layout. It is an emulator choice (emulator choice,
not hardware-derived and not host time): a real board keeps battery-backed
time, and the pinned MAME seeds from the host clock, which this core never does.
The weekday nibble is 0: weekday encoding not sourced. The seed is restored by
`gn_reset` and by load; a watchdog soft reset of the 68000 leaves the calendar
running, as the RTC is not reset by the CPU's reset line.

Not established: whether the sub-second divider phase after a time set matches
hardware (the pinned source masks the remaining count to under 64 ticks; this
model does the same on the remaining tick count it holds), the physical phase of
the first pulse after a command (the pinned source arms the timers with a zero
delay and this model toggles at the strobe), test mode, leap-day behavior, and
the primary uPD4990A datasheet (not consulted).

Regressions: `mvs_test --board-behavior` groups `calendar` and
`calendar-timing`: a guest program writing the control byte continues without a
bus fault; the seed reads back through time read plus shift; a clock edge
without a strobe leaves the command unlatched; time set loads and freezes the
counter; the mirror works while the even byte and the read direction still
fault; test mode faults; two instances and a reset keep independent seeds; one
second needs exactly 12,000,000 clocks and 60 seconds carry into minutes;
register hold toggles the pulses at the half periods recomputed from the cited
ratio.

## Cartridge program windows

Mapping in force:

- `$000000-$00007f`: vector window, BIOS by default or cartridge when the
  observed latch output selects it.
- `$000080-$0fffff`: read-only cartridge P1 bytes at the same offset (S7).
- `$200000-$2fffff`: the selected program bank, with bank zero beginning at
  program offset `0x100000` after reset (S16). Eight word registers in
  `$2ffff0-$2fffff` select the bank using `data & 7`; guest byte writes are
  packed into the even/high or odd/low lane before the selector sees the word
  (S16c-S16e and MAME's big-endian memory dispatch). A selected bank begins at
  `(bank + 1) * 0x100000`; if that base is outside the loaded program region,
  pinned MAME falls back to bank zero (S16f). Reads remain bounded by the
  loaded image, and `$300000` and above stays in the I/O map.
  These are pinned-MAME differential semantics; physical-board behavior is
  not established.

The `mvs_board_cartridge` regression runs original synthetic 68000 guests that
select bank one with a word or odd-byte write, preserve bank zero with an
even-byte write, read the first and last words of the P2 window, verify an
out-of-range select falls back to bank zero, and check reset and per-instance
isolation. The earlier private trace did not identify the P2 window as its
captured blocker; the mapper is covered by a separate original synthetic guest.
The latest bounded selected-media invocation executes guest code but stops on
an unsupported word write in the selected MSLUGX protection window before the
attract checkpoint; it writes no fresh frame. This is a board-implementation
blocker, not title-render evidence.

## Selected MSLUGX protection port

At the pinned MAME revision, the `NEOGEO_MSLUGX` slot installs 16-bit read and
write protection handlers over `$2fffe0-$2fffef` ([`neogeo.cpp`, lines
1438-1440](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp#L1438-L1440)).
The device stores a command and serial counter. A write at byte offset `$0`
clears the command; writes at `$2` and `$4` OR their word into it; `$6` is a
no-op; and `$a` clears both command and counter. The device initializes both
fields to zero and its MAME `device_reset()` is empty.

For command `0x0001`, reads return one bit from P1 program data at
`0x0dedd2 + ((counter >> 3) & 0xfff)`, selected by `(~counter) & 7`, then
increment the counter. For command `0x0fff`, MAME reads a word from work RAM at
`0x10f00a`, subtracts one, and uses the resulting bit index against the same
P1 table. The MAME source explicitly marks the index calculation uncertain;
matching this path is differential emulator behavior, not physical-board
truth. Other commands return zero in that implementation
([`prot_mslugx.cpp`, lines 35-87](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo/prot_mslugx.cpp#L35-L87)).

The native profile models this selected-title subset with per-instance command
and counter state. Original synthetic guests seed public synthetic P1 bytes and
exercise command `0x0001` and `0x0fff`; private game bytes and captures are not
used as fixtures. This comparison qualifies only the pinned MAME algorithm.

## Predicate sources (fetched)

These rows record an actual fetch of each cited immutable revision on the stated date. `tools/mvs/check_sources.py` re-fetches every row at verify time and requires the raw SHA-256 and the verbatim excerpt to reproduce; the wiki revisions are retrieved through the MediaWiki API (`api.php?action=query&prop=revisions&revids=<oldid>&rvprop=ids|content&rvslots=main`) and hashed as UTF-8 revision wikitext, because the `index.php` raw and HTML routes return HTTP 403 from agent shells. Wikitext table cells are pipe-separated, so an address cell and its description cell are recorded as separate rows of one element (the `b`/`c` suffixes). Revision text was read in full before the excerpts were chosen; no element was contradicted. Plan 05-10 appended rows S8-S17 (interrupt, timing and banking constants for "Interrupts and timing" and "Cartridge program windows"), fetched the same day; the MAME files and the three wiki revisions were read in full. Plan 05-21 appended S21-S21u (uPD4990A calendar, MAME `upd1990a.cpp`, `upd1990a.h`, `dirtc.cpp`, `dirtc.h` and `neogeo.cpp` at the same pinned commit), fetched 2026-10-12 and read in full; excerpts with a pipe character are cut to a pipe-free substring because the table cell separator is the pipe. Required IDs are complete row IDs, including suffixes; `S1b` cannot satisfy `S1`, and duplicate exact IDs fail. The source inventory is append-only; existing IDs are preserved. Raw copies stay under ignored `local/sources/`.

05-02 continuation appended S16g-S16h for pinned MAME's big-endian byte-write packing and simple word-write delegate, fetched 2026-10-19 at the same commit and read in full.
Plan 05-02 task 2 appended S17b-S17h for the video read/write maps, byte-lane behavior, live counter and animation cadence, fetched 2026-10-19 at the same pinned commit and read in full.
Plan 05-03 appended S40-S40h for the selected MSLUGX protection map, command/counter behavior, serial bit source and the explicitly uncertain indexed-read calculation; fetched 2026-10-19 at the same pinned revision.

| id | element | url | fetched | raw_sha256 | excerpt_id | excerpt | class |
|---|---|---|---|---|---|---|---|
| S1 | BIOS_SYSTEM_MODE value meaning | https://wiki.neogeodev.org/index.php?title=BIOS_RAM_locations&oldid=9321 | 2026-10-12 | 3ebd30eaf575e36220762d751c58f731056c86c7b4ebe0147648b9156bba2eda | System Related, BIOS_SYSTEM_MODE description | 0:BIOS wants vblank (system mode), $80:Ok to use vblank (game mode) | community documentation (NeoGeo Development Wiki) |
| S1b | BIOS_SYSTEM_MODE address | https://wiki.neogeodev.org/index.php?title=BIOS_RAM_locations&oldid=9321 | 2026-10-12 | 3ebd30eaf575e36220762d751c58f731056c86c7b4ebe0147648b9156bba2eda | System Related, address cell | $10FD80 | community documentation (NeoGeo Development Wiki) |
| S2 | BIOS_USER_REQUEST request codes | https://wiki.neogeodev.org/index.php?title=BIOS_RAM_locations&oldid=9321 | 2026-10-12 | 3ebd30eaf575e36220762d751c58f731056c86c7b4ebe0147648b9156bba2eda | Game Related, BIOS_USER_REQUEST description | Request code for the [[USER subroutine]]. 0:Init, 1:Boot animation, 2:Demo, 3:Title | community documentation (NeoGeo Development Wiki) |
| S2b | BIOS_USER_REQUEST address | https://wiki.neogeodev.org/index.php?title=BIOS_RAM_locations&oldid=9321 | 2026-10-12 | 3ebd30eaf575e36220762d751c58f731056c86c7b4ebe0147648b9156bba2eda | Game Related, address cell | $10FDAE | community documentation (NeoGeo Development Wiki) |
| S2c | BIOS_USER_REQUEST is set by the BIOS | https://wiki.neogeodev.org/index.php?title=BIOS_RAM_locations&oldid=9321 | 2026-10-12 | 3ebd30eaf575e36220762d751c58f731056c86c7b4ebe0147648b9156bba2eda | Game Related, BIOS_USER_REQUEST row | BIOS_USER_REQUEST | community documentation (NeoGeo Development Wiki) |
| S3 | BIOS_USER_MODE game-written values | https://wiki.neogeodev.org/index.php?title=BIOS_RAM_locations&oldid=9321 | 2026-10-12 | 3ebd30eaf575e36220762d751c58f731056c86c7b4ebe0147648b9156bba2eda | Game Related, BIOS_USER_MODE description | Used by the game to tell what it's doing: 0:Init/Boot animation, 1:Title/Demo, 2:Game | community documentation (NeoGeo Development Wiki) |
| S3b | BIOS_USER_MODE address | https://wiki.neogeodev.org/index.php?title=BIOS_RAM_locations&oldid=9321 | 2026-10-12 | 3ebd30eaf575e36220762d751c58f731056c86c7b4ebe0147648b9156bba2eda | Game Related, address cell | $10FDAF | community documentation (NeoGeo Development Wiki) |
| S4 | USER subroutine entry in the header | https://wiki.neogeodev.org/index.php?title=68k_program_header&oldid=9154 | 2026-10-12 | bc0d74628f6536e8262ae43e54cc729b38409bc76e8cb40eab7aa85bdc779d05 | For cartridge systems, offset $122 description | JMP to [[USER subroutine]] (code start). | community documentation (NeoGeo Development Wiki) |
| S4b | USER entry at $0122 in the minimal header | https://wiki.neogeodev.org/index.php?title=68k_program_header&oldid=9154 | 2026-10-12 | bc0d74628f6536e8262ae43e54cc729b38409bc76e8cb40eab7aa85bdc779d05 | Minimal header example | org $0122 jmp USER ;entry | community documentation (NeoGeo Development Wiki) |
| S5 | PLAYER_START entry in the header | https://wiki.neogeodev.org/index.php?title=68k_program_header&oldid=9154 | 2026-10-12 | bc0d74628f6536e8262ae43e54cc729b38409bc76e8cb40eab7aa85bdc779d05 | For cartridge systems, offset $128 description | JMP to [[PLAYER_START subroutine]]. | community documentation (NeoGeo Development Wiki) |
| S5b | Header jump order USER then PLAYER_START | https://wiki.neogeodev.org/index.php?title=68k_program_header&oldid=9154 | 2026-10-12 | bc0d74628f6536e8262ae43e54cc729b38409bc76e8cb40eab7aa85bdc779d05 | Full header example | jmp USER jmp PLAYER_START jmp DEMO_END jmp COIN_SOUND | community documentation (NeoGeo Development Wiki) |
| S5c | PLAYER_START offset | https://wiki.neogeodev.org/index.php?title=68k_program_header&oldid=9154 | 2026-10-12 | bc0d74628f6536e8262ae43e54cc729b38409bc76e8cb40eab7aa85bdc779d05 | For cartridge systems, address cell | $128 | community documentation (NeoGeo Development Wiki) |
| S6 | NEO-GEO signature description | https://wiki.neogeodev.org/index.php?title=68k_program_header&oldid=9154 | 2026-10-12 | bc0d74628f6536e8262ae43e54cc729b38409bc76e8cb40eab7aa85bdc779d05 | For cartridge systems, offset $100 description | "NEO-GEO" string (first cartridge recognition code). | community documentation (NeoGeo Development Wiki) |
| S6b | NEO-GEO signature offset | https://wiki.neogeodev.org/index.php?title=68k_program_header&oldid=9154 | 2026-10-12 | bc0d74628f6536e8262ae43e54cc729b38409bc76e8cb40eab7aa85bdc779d05 | For cartridge systems, address cell | $100 | community documentation (NeoGeo Development Wiki) |
| S7 | Cartridge ROM window from the cartridge base | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | cart slot install_rom call | space.install_rom(0x000080, 0x0fffff, (uint16_t *)m_slots[m_curr_slot]->get_rom_base() + 0x80/2); | reference emulator, differential (D-02) |
| S7b | Low vectors keep a separate banked read | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_main_map | map(0x000000, 0x00007f).r(FUNC(ngarcade_base_state::banked_vectors_r)); | reference emulator, differential (D-02) |
| S7c | Window is unmapped before each cartridge install | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | cart slot setup | space.unmap_readwrite(0x000080, 0x0fffff); | reference emulator, differential (D-02) |
| S8 | Pixels per line | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.h | 2026-10-12 | 91324fcc5567399a6f524d65d8c7d7c5c82e8f816eee8ddbbb6dc6291bffb08a | NEOGEO_HTOTAL | #define NEOGEO_HTOTAL (0x180) | reference emulator, differential (D-02) |
| S8b | Lines per frame | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.h | 2026-10-12 | 91324fcc5567399a6f524d65d8c7d7c5c82e8f816eee8ddbbb6dc6291bffb08a | NEOGEO_VTOTAL | #define NEOGEO_VTOTAL (0x108) | reference emulator, differential (D-02) |
| S8c | VBlank start line | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.h | 2026-10-12 | 91324fcc5567399a6f524d65d8c7d7c5c82e8f816eee8ddbbb6dc6291bffb08a | NEOGEO_VBSTART | #define NEOGEO_VBSTART (0x0f0) | reference emulator, differential (D-02) |
| S9 | Master clock | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.h | 2026-10-12 | 7722a1c642843eb46dbff72e66ee3bf86860c0010bdf803ab1185ee800b7fb09 | NEOGEO_MASTER_CLOCK | #define NEOGEO_MASTER_CLOCK (24000000) | reference emulator, differential (D-02) |
| S9b | Main CPU clock | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.h | 2026-10-12 | 7722a1c642843eb46dbff72e66ee3bf86860c0010bdf803ab1185ee800b7fb09 | NEOGEO_MAIN_CPU_CLOCK | #define NEOGEO_MAIN_CPU_CLOCK (NEOGEO_MASTER_CLOCK / 2) | reference emulator, differential (D-02) |
| S9c | Pixel clock | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.h | 2026-10-12 | 7722a1c642843eb46dbff72e66ee3bf86860c0010bdf803ab1185ee800b7fb09 | NEOGEO_PIXEL_CLOCK | #define NEOGEO_PIXEL_CLOCK (NEOGEO_MASTER_CLOCK / 4) | reference emulator, differential (D-02) |
| S10 | VBlank IRQ1 flip-flop phase | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.h | 2026-10-12 | 7722a1c642843eb46dbff72e66ee3bf86860c0010bdf803ab1185ee800b7fb09 | NEOGEO_VBLANK_IRQ_HTIM | #define NEOGEO_VBLANK_IRQ_HTIM (attotime::from_ticks(56+2, NEOGEO_MASTER_CLOCK)) | reference emulator, differential (D-02) |
| S10b | VBlank IRQ scheduled each frame | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | vblank_interrupt_callback | m_vblank_interrupt_timer->adjust(m_screen->time_until_pos(NEOGEO_VBSTART) + NEOGEO_VBLANK_IRQ_HTIM); | reference emulator, differential (D-02) |
| S10c | VBlank callback sets the pending flag | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | vblank_interrupt_callback | m_vblank_interrupt_pending = 1; update_interrupts(); | reference emulator, differential (D-02) |
| S11 | VBlank drives the line set at machine start | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | update_interrupts | m_maincpu->set_input_line(m_vblank_level, m_vblank_interrupt_pending ? ASSERT_LINE : CLEAR_LINE); | reference emulator, differential (D-02) |
| S11b | Raster drives its line | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | update_interrupts | m_maincpu->set_input_line(m_raster_level, m_display_position_interrupt_pending ? ASSERT_LINE : CLEAR_LINE); | reference emulator, differential (D-02) |
| S11c | IRQ3 line from its pending flag | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | update_interrupts | m_maincpu->set_input_line(3, m_irq3_pending ? ASSERT_LINE : CLEAR_LINE); | reference emulator, differential (D-02) |
| S11d | VBlank level is 1 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | machine_start | m_vblank_level = 1; | reference emulator, differential (D-02) |
| S11e | Raster level is 2 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | machine_start | m_raster_level = 2; | reference emulator, differential (D-02) |
| S12 | Acknowledge bit 2 clears VBlank | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | acknowledge_interrupt | if (BIT(data, 2)) m_vblank_interrupt_pending = 0; | reference emulator, differential (D-02) |
| S12b | Acknowledge bit 0 clears IRQ3 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | acknowledge_interrupt | if (BIT(data, 0)) m_irq3_pending = 0; | reference emulator, differential (D-02) |
| S12c | Acknowledge recomputes the lines | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | acknowledge_interrupt | m_vblank_interrupt_pending = 0; update_interrupts(); | reference emulator, differential (D-02) |
| S13 | Autovector levels: 1 VBlank, 2 timer, 3 after reset | https://wiki.neogeodev.org/index.php?title=68k_interrupts&oldid=8325 | 2026-10-12 | 0d51f2c3e1831fd586fb4d7a73ec184262989c02465ba231033d98ac74a8824b | AES/MVS interrupt levels | *Level 1: V-blank *Level 2: Timer *Level 3: Pending after reset | community documentation (NeoGeo Development Wiki) |
| S13b | Acknowledge bit layout | https://wiki.neogeodev.org/index.php?title=68k_interrupts&oldid=8325 | 2026-10-12 | 0d51f2c3e1831fd586fb4d7a73ec184262989c02465ba231033d98ac74a8824b | 68k interrupts | *bit 2: Acknowledge v-blank interrupt | community documentation (NeoGeo Development Wiki) |
| S14 | Scanline length in master clocks | https://wiki.neogeodev.org/index.php?title=Display_timing&oldid=5920 | 2026-10-12 | 12bb6f97f70471bdc48bdc0c52f62d44f81db555f97390e83c0a5e10c8ffbe54 | Horizontal | 32 + 112 + 112 + 1280 = 1536 mclks (384px) total per scanline | community documentation (NeoGeo Development Wiki) |
| S14b | Scanlines per frame | https://wiki.neogeodev.org/index.php?title=Display_timing&oldid=5920 | 2026-10-12 | 12bb6f97f70471bdc48bdc0c52f62d44f81db555f97390e83c0a5e10c8ffbe54 | Vertical | There are 264 scanlines per frame: | community documentation (NeoGeo Development Wiki) |
| S14c | Pixel and master clock relation | https://wiki.neogeodev.org/index.php?title=Display_timing&oldid=5920 | 2026-10-12 | 12bb6f97f70471bdc48bdc0c52f62d44f81db555f97390e83c0a5e10c8ffbe54 | Sync | '''mclk''' refers to the 24MHz master [[clock]]. A pixel lasts 4 mclk. | community documentation (NeoGeo Development Wiki) |
| S15 | MVS pixel clock from a 24 MHz master clock | https://wiki.neogeodev.org/index.php?title=Framerate&oldid=5921 | 2026-10-12 | 2e266b30baa0fcafbde5cb6f7886d494de58e7da75dda5ea5494d28cf7770294 | MVS | 24.000000MHz main clock / 4 = 6.000000MHz pixel clock | community documentation (NeoGeo Development Wiki) |
| S15b | MVS frames per second | https://wiki.neogeodev.org/index.php?title=Framerate&oldid=5921 | 2026-10-12 | 2e266b30baa0fcafbde5cb6f7886d494de58e7da75dda5ea5494d28cf7770294 | MVS | 15.625kHz / 264 lines = '''59.1856 frames/second''' | community documentation (NeoGeo Development Wiki) |
| S16 | Cartridge window starts at the second megabyte when larger than one | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | init_cpu | if (len > 0x100000) m_bank_base = 0x100000; | reference emulator, differential (D-02) |
| S16b | Banked read window | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | cartridge install | space.install_read_bank(0x200000, 0x2fffff, m_bank_cartridge); | reference emulator, differential (D-02) |
| S16c | Bank-select write range | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | cartridge install | space.install_write_handler(0x2ffff0, 0x2fffff, write16smo_delegate(*this, FUNC(neogeo_base_state::write_banksel))); | reference emulator, differential (D-02) |
| S16d | Bank base after a select | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | write_banksel | m_bank_base = (bank + 1) * 0x100000; | reference emulator, differential (D-02) |
| S16e | Bank select masks to low three data bits | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | write_banksel | int bank = data & 0x07; | reference emulator, differential (D-02) |
| S16f | Empty bank select falls back to bank zero | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | write_banksel | if ((bank + 1) * 0x100000 >= len) | reference emulator, differential (D-02) |
| S16g | Big-endian byte data is shifted into its native word lane | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/emumem.h | 2026-10-19 | 4285ca50a0c14b6038c7443bab45340834f0e4b741f0549a127c4ba7cc1c3e2e | big-endian masked write | return wop(address & ~NATIVE_MASK, (NativeType)data << offsbits, (NativeType)mask << offsbits); | reference emulator, differential (D-02) |
| S16h | Simple word-write delegate passes packed data without the mask | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/emumem_hedp.cpp | 2026-10-19 | 27b25423ab39477d1b719b8922dc7dab16f712cac43a24d4974890ad7af1aeee | write16smo_delegate write_impl | m_delegate(data); | reference emulator, differential (D-02) |
| S17 | LSPC mode read layout | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-12 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | get_video_control | uint16_t v_counter = m_screen->vpos() + 0x100; | reference emulator, differential (D-02) |
| S17b | Video-register reads use a four-word map mirrored across 0x20000 bytes | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-19 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_main_map | map(0x3c0000, 0x3c0007).mirror(0x01fff8).r(FUNC(neogeo_base_state::video_register_r)); | reference emulator, differential (D-02) |
| S17c | Low-byte-only video-register reads are unmapped | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | video_register_r | if (mem_mask == 0x00ff) | reference emulator, differential (D-02) |
| S17d | Auto-animation advances when the per-frame countdown reaches zero | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | auto_animation_timer_callback | if (m_auto_animation_frame_counter == 0) | reference emulator, differential (D-02) |
| S17e | Sprite auto-animation timer uses scanline 0x100 and frame height 0x108 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.h | 2026-10-19 | 91324fcc5567399a6f524d65d8c7d7c5c82e8f816eee8ddbbb6dc6291bffb08a | raster constants | #define NEOGEO_VSSTART (0x100) | reference emulator, differential (D-02) |
| S17f | Video-register writes map eight word ports across a mirrored 0x20000-byte window | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-19 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_main_map | map(0x3c0000, 0x3c000f).mirror(0x01fff0).w(FUNC(neogeo_base_state::video_register_w)); | reference emulator, differential (D-02) |
| S17g | High-byte-only video writes duplicate the byte into both lanes | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | video_register_w | data = (data & 0xff00) | (data >> 8); | reference emulator, differential (D-02) |
| S17h | Low-byte-only video writes skip the register effects | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | video_register_w | if (mem_mask != 0x00ff) | reference emulator, differential (D-02) |
| S18 | REG_DIPSW is the byte at $300001 | https://wiki.neogeodev.org/index.php?title=Memory_mapped_registers&oldid=9288 | 2026-10-12 | a2db2681b2f4b559ad9b27ed282e9ba5ca152a065010c6b688ad9a7d5a3fd466 | REG_DIPSW | *Address: $300001 *Decode mask: $FE0081 (not sure for write) | community documentation (NeoGeo Development Wiki) |
| S18b | REG_DIPSW read is the hardware DIPs, active low | https://wiki.neogeodev.org/index.php?title=Memory_mapped_registers&oldid=9288 | 2026-10-12 | a2db2681b2f4b559ad9b27ed282e9ba5ca152a065010c6b688ad9a7d5a3fd466 | REG_DIPSW | [[Hardware DIPs]] (active low) | community documentation (NeoGeo Development Wiki) |
| S19 | DSW default: setting mode off (bit 0) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo DSW | PORT_DIPNAME( 0x01, 0x01, "Setting Mode" ) PORT_DIPLOCATION("SW:1") | reference emulator, differential (D-02) |
| S19b | DSW default: cabinet normal (bit 1) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo DSW | PORT_DIPNAME( 0x02, 0x02, DEF_STR( Cabinet ) ) PORT_DIPLOCATION("SW:2") | reference emulator, differential (D-02) |
| S19c | DSW default: joystick controller (bit 2) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo DSW | PORT_DIPNAME( 0x04, 0x04, DEF_STR( Controller ) ) PORT_DIPLOCATION("SW:3") | reference emulator, differential (D-02) |
| S19d | DSW default: cabinet number 1 (bits 3-4) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo DSW | PORT_DIPNAME( 0x18, 0x18, "COMM Setting (Cabinet No.)" ) PORT_DIPLOCATION("SW:4,5") | reference emulator, differential (D-02) |
| S19e | DSW default: link off (bit 5) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo DSW | PORT_DIPNAME( 0x20, 0x20, "COMM Setting (Link Enable)" ) PORT_DIPLOCATION("SW:6") | reference emulator, differential (D-02) |
| S19f | DSW default: free play off (bit 6) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo DSW | PORT_DIPNAME( 0x40, 0x40, DEF_STR( Free_Play ) ) PORT_DIPLOCATION("SW:7") | reference emulator, differential (D-02) |
| S19g | DSW default: freeze off (bit 7) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo DSW | PORT_DIPNAME( 0x80, 0x80, "Freeze" ) PORT_DIPLOCATION("SW:8") | reference emulator, differential (D-02) |
| S20 | Low byte of the word at $300000 is the DSW port | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | in0_edge_r | return (m_edge->in0_r() << 8) | reference emulator, differential (D-02) |
| S20b | Read handler range and mirror | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | machine_start | main_program_space.install_read_handler(0x300000, 0x300001, 0, 0x01ff7e, 0, read16smo_delegate(*this, FUNC(ngarcade_base_state::in0_edge_r))); | reference emulator, differential (D-02) |
| S20c | $300080 is a separate TEST port, outside the REG_DIPSW decode | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_main_map | map(0x300080, 0x300081).mirror(0x01ff7e).portr("TEST"); | reference emulator, differential (D-02) |
| S20d | TEST port declaration with a released active-low service input | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo TEST | PORT_START("TEST") PORT_BIT( 0x003f, IP_ACTIVE_HIGH, IPT_UNUSED ) PORT_BIT( 0x0040, IP_ACTIVE_HIGH, IPT_CUSTOM ) // sense: JAMMA PORT_SERVICE_NO_TOGGLE( 0x0080, IP_ACTIVE_LOW ) PORT_BIT( 0xff00, IP_ACTIVE_LOW, IPT_UNUSED ) | reference emulator, differential (D-02) |
| S21 | I/O control write window (byte at odd addresses) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_map | map(0x380000, 0x3800ff).mirror(0x01ff00).w(FUNC(neogeo_base_state::io_control_w)).umask16(0x00ff); | reference emulator, differential (D-02) |
| S21v | I/O word offsets 0x30/0x70 with bit 1 clear select bookkeeping coin counters | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-20 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | ngarcade_base_state::io_control_w | case 0x30: case 0x70: if (BIT(offset, 1)) machine().bookkeeping().coin_lockout_w(BIT(offset, 0), BIT(offset, 6)); else machine().bookkeeping().coin_counter_w(BIT(offset, 0), BIT(offset, 6)); | reference emulator, differential (D-02) |
| S21b | uPD4990A line wiring from the control byte | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | ngarcade_base_state::io_control_w | m_upd4990a->data_in_w(BIT(data, 0)); m_upd4990a->clk_w(BIT(data, 1)); m_upd4990a->stb_w(BIT(data, 2)); | reference emulator, differential (D-02) |
| S21c | Control byte is offset 0x28 (address $380051) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | ngarcade_base_state::io_control_w | case 0x28: m_upd4990a->data_in_w(BIT(data, 0)); | reference emulator, differential (D-02) |
| S21d | cs, oe and c0-c2 held high at machine start | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-12 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | machine_start | m_upd4990a->cs_w(1); m_upd4990a->oe_w(1); m_upd4990a->c0_w(1); m_upd4990a->c1_w(1); m_upd4990a->c2_w(1); | reference emulator, differential (D-02) |
| S21e | Serial mode when c0-c2 are high | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | is_serial_mode | return (m_variant == TYPE_4990A && m_c_unlatched == 7); | reference emulator, differential (D-02) |
| S21f | Strobe rising edge takes the command from the serial command register | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | stb_w | if (is_serial_mode()) m_c = m_shift_reg[6]; | reference emulator, differential (D-02) |
| S21g | Clock rising edge shifts the command register right and emits its low bit | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | clk_w | in = m_shift_reg[6] & 1; m_shift_reg[6] >>= 1; | reference emulator, differential (D-02) |
| S21h | Shift mode inserts the command-register output at the top of the shift register | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | clk_w | (in << 7); // shift in new bit | reference emulator, differential (D-02) |
| S21i | Time counter increments once per 32,768 chip ticks | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | device_start | m_timer_clock->adjust(attotime::from_hz(clock() / 32768.0), 0, attotime::from_hz(clock() / 32768.0)); // 1 second on XTAL(32'768) | reference emulator, differential (D-02) |
| S21j | uPD4990A chip clock defaults to 32,768 Hz | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.h | 2026-10-12 | f92f8fae4c26cb7aa708b72f4ae38e805a00a9c080d8278e7a1dd1f5f0ed8b08 | upd4990a_device constructor | upd4990a_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 32'768); | reference emulator, differential (D-02) |
| S21k | Time-counter field 4 holds the month in its high nibble (weekday low nibble: day_of_week - 1) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | rtc_clock_updated | m_time_counter[4] = (month << 4) | reference emulator, differential (D-02) |
| S21l | Register hold starts the 64 Hz time pulse (toggling at twice the frequency) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | stb_w MODE_REGISTER_HOLD | m_timer_tp->adjust(attotime::zero, 0, attotime::from_hz((clock() / 512.0) * 2.0)); | reference emulator, differential (D-02) |
| S21m | Time read data-out pulse period | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | stb_w MODE_TIME_READ | m_timer_data_out->adjust(attotime::zero, 0, attotime::from_hz((clock() / div) * 2.0)); | reference emulator, differential (D-02) |
| S21n | uPD4990A divider for the data-out pulse is 32768 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | stb_w MODE_TIME_READ | if (m_variant == TYPE_4990A) div = 32768.0; | reference emulator, differential (D-02) |
| S21o | Time set copies the shift register into the time counter | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | stb_w MODE_TIME_SET | m_time_counter[i] = m_shift_reg[i]; | reference emulator, differential (D-02) |
| S21p | Time read copies the time counter into the shift register | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | stb_w MODE_TIME_READ | m_shift_reg[i] = m_time_counter[i]; | reference emulator, differential (D-02) |
| S21q | Test mode is a separate command with its own timers | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | stb_w MODE_TEST | // enable testmode m_testmode = true; | reference emulator, differential (D-02) |
| S21r | Days per month used when the day carries | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/dirtc.cpp | 2026-10-12 | c19f81a87e2860a215f0cee0481351589904c3b5a97b4756e3327b38390ff731 | dirtc.cpp | static const int DAYS_PER_MONTH[12] = { 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 }; | reference emulator, differential (D-02) |
| S21s | The uPD4990A calendar has no leap-year feature | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/dirtc.h | 2026-10-12 | 0324b3fc55c984a477a6109b2b0dffca9a447681b356da8f66d16b74e5e1b251 | device_rtc_interface | virtual bool rtc_feature_leap_year() const { return false; } | reference emulator, differential (D-02) |
| S21u | The new data bit enters the command register at bit 3 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-12 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | clk_w | (m_data_in << 3); | reference emulator, differential (D-02) |
| S21t | Two-digit year (no Y2K feature) | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/dirtc.h | 2026-10-12 | 0324b3fc55c984a477a6109b2b0dffca9a447681b356da8f66d16b74e5e1b251 | device_rtc_interface | virtual bool rtc_feature_y2k() const { return false; } | reference emulator, differential (D-02) |
| S22 | REG_STATUS_A is the AUDIO_COIN port at $320000-$320001, mirror 0x01fffe | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | ngarcade_base_state::neogeo_main_map | map(0x320000, 0x320001).mirror(0x01fffe).portr("AUDIO_COIN"); | reference emulator, differential (D-02) |
| S22b | Status bit 0 is coin 1, active low | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo AUDIO_COIN | PORT_BIT( 0x0001, IP_ACTIVE_LOW, IPT_COIN1 ) | reference emulator, differential (D-02) |
| S22c | Status bit 1 is coin 2, active low | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo AUDIO_COIN | PORT_BIT( 0x0002, IP_ACTIVE_LOW, IPT_COIN2 ) | reference emulator, differential (D-02) |
| S22d | Status bit 2 is service 1, active low | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo AUDIO_COIN | PORT_BIT( 0x0004, IP_ACTIVE_LOW, IPT_SERVICE1 ) | reference emulator, differential (D-02) |
| S22e | Status bits 3-4 are unused and active low | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo AUDIO_COIN | PORT_BIT( 0x0018, IP_ACTIVE_LOW, IPT_UNUSED ) | reference emulator, differential (D-02) |
| S22f | Status bit 5 is the 4-slot sense custom bit | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo AUDIO_COIN | PORT_BIT( 0x0020, IP_ACTIVE_HIGH, IPT_CUSTOM ) // sense: 4-slot | reference emulator, differential (D-02) |
| S22g | Status bit 6 reads the uPD4990A time pulse | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo AUDIO_COIN | PORT_BIT( 0x0040, IP_ACTIVE_HIGH, IPT_CUSTOM ) PORT_READ_LINE_DEVICE_MEMBER("upd4990a", FUNC(upd1990a_device::tp_r)) | reference emulator, differential (D-02) |
| S22h | Status bit 7 reads the uPD4990A data out | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo AUDIO_COIN | PORT_BIT( 0x0080, IP_ACTIVE_HIGH, IPT_CUSTOM ) PORT_READ_LINE_DEVICE_MEMBER("upd4990a", FUNC(upd1990a_device::data_out_r)) | reference emulator, differential (D-02) |
| S22i | The selected set mslugx uses the neogeo input ports | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | GAME mslugx | mslugx, neogeo, mslugx, neogeo, mvs_led_state | reference emulator, differential (D-02) |
| S22j | Data out is the pin level while output enable is high | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/upd1990a.cpp | 2026-10-13 | 3c12ef633ee513eec80682a5ae4ca318ac62f5943334a6cbc79b3f4dc448b3fb | get_data_out | m_testmode) ? m_data_out : 1; | reference emulator, differential (D-02) |
| S23 | REG_STATUS_B is the SYSTEM port with its mirror | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_main_map | map(0x380000, 0x380001).mirror(0x01fffe).portr("SYSTEM"); | reference emulator, differential (D-02) |
| S23b | System high-byte low nibble reads start and select lines | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo SYSTEM | PORT_BIT( 0x0f00, IP_ACTIVE_HIGH, IPT_CUSTOM ) PORT_CUSTOM_MEMBER(FUNC(ngarcade_base_state::startsel_edge_joy_r)) | reference emulator, differential (D-02) |
| S23c | Absent memory card returns 7 for presence/protect lines | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | get_memcard_status | !m_memcard->present()) ? 0x07 : 0x00; | reference emulator, differential (D-02) |
| S23d | System high-byte bit 7 identifies MVS hardware | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo SYSTEM | PORT_BIT( 0x8000, IP_ACTIVE_LOW, IPT_CUSTOM ) // Hardware type (AES=0, MVS=1). | reference emulator, differential (D-02) |
| S23e | Released arcade start 1 is high | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo_ctrl/joystick.cpp | 2026-10-13 | 6dce1b78684139e9b4e8869af0136253156e0285a863b863c96909777836bdb7 | INPUT_PORTS neogeo_joy_ac START | PORT_BIT( 0x01, IP_ACTIVE_LOW, IPT_START1 ) | reference emulator, differential (D-02) |
| S23f | Released arcade start 2 is high | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo_ctrl/joystick.cpp | 2026-10-13 | 6dce1b78684139e9b4e8869af0136253156e0285a863b863c96909777836bdb7 | INPUT_PORTS neogeo_joy_ac START | PORT_BIT( 0x04, IP_ACTIVE_LOW, IPT_START2 ) | reference emulator, differential (D-02) |
| S23g | Other arcade start-port lines are unused active low | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo_ctrl/joystick.cpp | 2026-10-13 | 6dce1b78684139e9b4e8869af0136253156e0285a863b863c96909777836bdb7 | INPUT_PORTS neogeo_joy_ac START | PORT_BIT( 0xfa, IP_ACTIVE_LOW, IPT_UNUSED ) | reference emulator, differential (D-02) |
| S23h | Arcade connector returns the start port | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo_ctrl/joystick.cpp | 2026-10-13 | 6dce1b78684139e9b4e8869af0136253156e0285a863b863c96909777836bdb7 | neogeo_joy_ac_device::read_start_sel | uint8_t neogeo_joy_ac_device::read_start_sel() { return m_ss->read(); } | reference emulator, differential (D-02) |
| S23i | Memory-card status occupies system bits 12-14 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo SYSTEM | PORT_BIT( 0x7000, IP_ACTIVE_HIGH, IPT_CUSTOM ) PORT_CUSTOM_MEMBER(FUNC(neogeo_base_state::get_memcard_status)) | reference emulator, differential (D-02) |
| S24 | System-latch odd-byte map and mirror | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_map | map(0x3a0000, 0x3a001f).mirror(0x01ffe0).w(m_systemlatch, FUNC(hc259_device::write_a3)).umask16(0x00ff); | reference emulator, differential (D-02) |
| S24b | Memory-card output 3 is unlock2 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_memcard | m_systemlatch->q_out_cb<3>().set(m_memcard, FUNC(ng_memcard_device::unlock2_w)); | reference emulator, differential (D-02) |
| S24c | Latch address selects output and its value; data ignored | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/74259.cpp | 2026-10-13 | eb80c6358a18c13b7a1f75f34f62f552b82b9e5abca1dcac20cf52d2ceabe7e6 | write_a3 | write_bit(offset & 7, (offset & 8) >> 3); | reference emulator, differential (D-02) |
| S24d | Card retains the unlock2 input | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/ng_memcard.cpp | 2026-10-13 | 580cd400b9d3ec603733c08b7657a885f331b0f96c5675ee2dad748fbc168426 | unlock2_w | void ng_memcard_device::unlock2_w(int state) { m_unlock2 = state; } | reference emulator, differential (D-02) |
| S24e | Latch reset assumes clear outputs | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/74259.cpp | 2026-10-13 | eb80c6358a18c13b7a1f75f34f62f552b82b9e5abca1dcac20cf52d2ceabe7e6 | device_reset | clear_outputs(m_enable ? u8(m_data) << m_address : 0); | reference emulator, differential (D-02) |
| S24f | System-latch output 2 drives memory-card lock 1 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-13 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_memcard | m_systemlatch->q_out_cb<2>().set(m_memcard, FUNC(ng_memcard_device::lock1_w)); | reference emulator, differential (D-02) |
| S25 | Main-CPU byte writes at `$320000` mirror `0x01fffe` to the audio command handler | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::base_main_map | map(0x320000, 0x320000).mirror(0x01fffe).w(FUNC(neogeo_base_state::audio_command_w)); | reference emulator, differential (D-02) |
| S25b | The command handler writes the main-to-audio sound latch | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::audio_command_w | m_soundlatch->write(data); | reference emulator, differential (D-02) |
| S25c | Audio Z80 port `$00` reads and clears the command latch, mirrored by `0xff00` | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::audio_io_map | map(0x00, 0x00).mirror(0xff00).rw(m_soundlatch, FUNC(generic_latch_8_device::read), FUNC(generic_latch_8_device::clear_w)); | reference emulator, differential (D-02) |
| S25d | Audio Z80 port `$0c` writes the audio-to-main reply latch, mirrored by `0xff00` | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::audio_io_map | map(0x0c, 0x0c).mirror(0xff00).w(m_soundlatch2, FUNC(generic_latch_8_device::write)); | reference emulator, differential (D-02) |
| S25e | Audio Z80 port `$08` selects the NMI-enable handler by address bit 4 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::audio_io_map | map(0x08, 0x08).mirror(0xff00).select(0x0010).w(FUNC(neogeo_base_state::audio_cpu_enable_nmi_w)); | reference emulator, differential (D-02) |
| S25f | Command-latch data pending feeds input-merger NMI source zero | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | machine configuration | m_soundlatch->data_pending_callback().set(m_audionmi, FUNC(input_merger_device::in_w<0>)); | reference emulator, differential (D-02) |
| S25g | Input-merger output is connected to the audio CPU NMI line | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | machine configuration | m_audionmi->output_handler().set_inputline(m_audiocpu, INPUT_LINE_NMI); | reference emulator, differential (D-02) |
| S25h | Audio Z80 maps banked ROM windows and RAM at `$f800-$ffff` | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::audio_map | map(0x0000, 0x7fff).bankr(m_bank_audio_main); map(0x8000, 0xbfff).bankr("audio_8000"); map(0xc000, 0xdfff).bankr("audio_c000"); map(0xe000, 0xefff).bankr("audio_e000"); map(0xf000, 0xf7ff).bankr("audio_f000"); map(0xf800, 0xffff).ram(); | reference emulator, differential (D-02) |
| S25i | Initial cart audio banks use MAME's non-banked-cartridge defaults | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::init_audio | m_bank_audio_cart[0]->set_entry(0x1e); m_bank_audio_cart[1]->set_entry(0x0e); m_bank_audio_cart[2]->set_entry(0x06); m_bank_audio_cart[3]->set_entry(0x02); | reference emulator, differential (D-02); emulator defaults, not hardware bank power-on values |
| S25j | Audio bank reads select a bank from the Z80 port address | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::audio_cpu_bank_select_r | m_bank_audio_cart[offset & 3]->set_entry(offset >> 8); | reference emulator, differential (D-02) |
| S25k | `get_audio_result` returns the audio-to-main reply latch | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::get_audio_result | return m_soundlatch2->read(); | reference emulator, differential (D-02) |
| S25l | The `AUDIO_COIN` port high byte reads `get_audio_result` | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo AUDIO_COIN | PORT_BIT( 0xff00, IP_ACTIVE_HIGH, IPT_CUSTOM ) PORT_CUSTOM_MEMBER(FUNC(neogeo_base_state::get_audio_result)) | reference emulator, differential (D-02) |
| S25m | Z80 port `$08` enables and `$18` disables NMI | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::audio_cpu_enable_nmi_w | out ($08) enables the nmi, out ($18) disables it | reference emulator, differential (D-02) |

| S25n | Board audio output selects fixed ROM source | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | set_use_cart_audio | m_bank_audio_main->set_entry(m_use_cart_audio); | reference emulator, differential (D-02) |
| S25o | Fixed cart source is initialized independently of the board latch | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | init_audio | m_bank_audio_main->configure_entry(1, ROM); m_bank_audio_main->set_entry(1); | reference emulator, differential (D-02) |
| S25p | Fixed source zero uses a separate audio BIOS when present | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | init_audio | m_bank_audio_main->configure_entry(0, (m_region_audiobios != nullptr) ? m_region_audiobios->base() : ROM); | reference emulator, differential (D-02) |
| S25q | Audio CPU uses master divided by six | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.h | 2026-10-14 | 7722a1c642843eb46dbff72e66ee3bf86860c0010bdf803ab1185ee800b7fb09 | NEOGEO_AUDIO_CPU_CLOCK | #define NEOGEO_AUDIO_CPU_CLOCK (NEOGEO_MASTER_CLOCK / 6) | reference emulator, differential (D-02) |

| S25r | Latch reset clears outputs | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/machine/74259.cpp | 2026-10-14 | eb80c6358a18c13b7a1f75f34f62f552b82b9e5abca1dcac20cf52d2ceabe7e6 | addressable_latch_device::device_reset | clear_outputs(m_enable ? u8(m_data) << m_address : 0); | reference emulator, differential (D-02) |
| S25s | Latch output five drives audio source selection | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | MVS machine configuration | m_systemlatch->q_out_cb<5>().set(FUNC(ngarcade_base_state::set_use_cart_audio)); | reference emulator, differential (D-02) |
| S25t | Audio BIOS is a separate region in the selected audio macro | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | NEO_BIOS_AUDIO_128K | ROM_REGION( 0x20000, "audiobios", 0 ) | reference emulator, differential (D-02) |

| S25u | Machine reset disables audio NMI rather than holding the CPU reset | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-14 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | neogeo_base_state::machine_reset | m_audionmi->in_w<1>(0); | reference emulator, differential (D-02) |
| S25v | Clocked enabled devices resume during reset | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/diexec.cpp | 2026-10-14 | 4205a1f2cc15ca8fa358646faea259c14dcbeaa83137ed996fe1ede8beb03fe7 | device_execute_interface::interface_pre_reset | else if (device().clock() != 0) resume(SUSPEND_ANY_REASON); | reference emulator, differential (D-02) |
| S25w | Z80 reset leaves HALT and starts at address zero | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/cpu/z80/z80.cpp | 2026-10-14 | 138bd48f9f6cd12e3422383e28abe4f73e39610b4d5db54064e29f4bfaadbb73 | z80_device::device_reset | leave_halt(); m_ref = 0xffff00; PC = 0; | reference emulator, differential (D-02) |
| S25x | All four YM2610 ports are read/write and mirrored by the high port byte | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-15 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | audio_io_map | map(0x04, 0x07).mirror(0xff00).rw(m_ym, FUNC(ym2610_device::read), FUNC(ym2610_device::write)); | reference emulator, differential (D-02) |
| S25y | YM2610 uses master divided by three, twice the audio CPU clock | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.h | 2026-10-15 | 7722a1c642843eb46dbff72e66ee3bf86860c0010bdf803ab1185ee800b7fb09 | NEOGEO_YM2610_CLOCK | #define NEOGEO_YM2610_CLOCK (NEOGEO_MASTER_CLOCK / 3) | reference emulator, differential (D-02) |
| S25z | YM2610 IRQ feeds the audio CPU maskable interrupt | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-15 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | machine configuration | m_ym->irq_handler().set_inputline(m_audiocpu, 0); | reference emulator, differential (D-02) |
| S26 | Missing ADPCM-B region falls back to the ADPCM-A region | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/sound/ymopn.cpp | 2026-10-15 | 5f0d3b178856fc830551cce2e88bb8ed415625104d7a5980527ac5b67bd298d6 | ym2610_device_base device_start | else if (m_adpcm_a_region) space(1).install_rom(0, m_adpcm_a_region->bytes() - 1, m_adpcm_a_region->base()); | reference emulator, differential (D-02); checked bounds remain explicit |
| S27 | REG_STATUS_A coin-in 1 is the bit-0 field | https://wiki.neogeodev.org/index.php?title=Memory_mapped_registers&oldid=9288 | 2026-10-15 | a2db2681b2f4b559ad9b27ed282e9ba5ca152a065010c6b688ad9a7d5a3fd466 | REG_STATUS_A 8BitRegister fields are ordered bit 7 through bit 0 | Coin-in 1 | community documentation (NeoGeo Development Wiki) |
| S27b | REG_STATUS_A coin switches are active low | https://wiki.neogeodev.org/index.php?title=Coin_switch&oldid=4697 | 2026-10-15 | 92ab9f0329d1418454d3b11ea771e39a90800cd0e92bae8bf8656d635d7c8423 | REG_STATUS_A coin switch input | active-low bits 1 and 0 | community documentation (NeoGeo Development Wiki) |
| S28 | REG_STATUS_B P1 Start is the bit-0 field | https://wiki.neogeodev.org/index.php?title=Memory_mapped_registers&oldid=9288 | 2026-10-15 | a2db2681b2f4b559ad9b27ed282e9ba5ca152a065010c6b688ad9a7d5a3fd466 | REG_STATUS_B 8BitRegister fields are ordered bit 7 through bit 0 | Start P1 | community documentation (NeoGeo Development Wiki) |
| S28b | REG_STATUS_B player controls are active low | https://wiki.neogeodev.org/index.php?title=Memory_mapped_registers&oldid=9288 | 2026-10-15 | a2db2681b2f4b559ad9b27ed282e9ba5ca152a065010c6b688ad9a7d5a3fd466 | REG_STATUS_B polarity | The player controls bits are active low. | community documentation (NeoGeo Development Wiki) |
| S29 | System ROM calls PLAYER_START for a credited start or title timeout | https://wiki.neogeodev.org/index.php?title=PLAYER_START_subroutine&oldid=9009 | 2026-10-15 | 45b08b268d003c235a1a399ac4e552f3675125a9eef7df34d3aa328afd6265af | PLAYER_START call conditions | The PLAYER_START subroutine is called by the [[System ROM]] if one of the start buttons are pressed while the corresponding player has enough credits or when the time runs out while the game's title screen is being displayed. | community documentation (NeoGeo Development Wiki) |
| S29b | BIOS_START_FLAG address, active-high indication and P1 bit 0 | https://wiki.neogeodev.org/index.php?title=PLAYER_START_subroutine&oldid=9009 | 2026-10-15 | 45b08b268d003c235a1a399ac4e552f3675125a9eef7df34d3aa328afd6265af | BIOS P1 Start indication (8BitRegister fields ordered bit 7 through bit 0) | BIOS_START_FLAG ($10FDB4.b) indicates which player(s) pushed start (active high): | community documentation (NeoGeo Development Wiki) |
| S30 | MAME models coin 1 as active-low bit 0 of AUDIO_COIN | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-15 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo AUDIO_COIN | PORT_BIT( 0x0001, IP_ACTIVE_LOW, IPT_COIN1 ) | reference emulator, differential (D-02) |
| S30b | MAME routes SYSTEM start/select inputs through its edge-joy callback | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-15 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | INPUT_PORTS neogeo SYSTEM | PORT_BIT( 0x0f00, IP_ACTIVE_HIGH, IPT_CUSTOM ) PORT_CUSTOM_MEMBER(FUNC(ngarcade_base_state::startsel_edge_joy_r)) | reference emulator, differential (D-02) |
| S30c | MAME models Start 1 as active-low bit 0 on the arcade START port | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo_ctrl/joystick.cpp | 2026-10-15 | 6dce1b78684139e9b4e8869af0136253156e0285a863b863c96909777836bdb7 | INPUT_PORTS neogeo_joy_ac START | PORT_BIT( 0x01, IP_ACTIVE_LOW, IPT_START1 ) | reference emulator, differential (D-02) |
| S31 | The audio CPU uses the cited audio I/O map | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-16 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | machine configuration audio map connection; mapped writes in S25c-S25e/S25x | m_audiocpu->set_addrmap(AS_IO, &neogeo_base_state::audio_io_map); | reference emulator, differential (D-02) |
| S31b | Address spaces create an unmapped-write handler | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/emumem_aspace.cpp | 2026-10-16 | 2b7411f12eb6305070070f16ff781b5b80a14e52160a59eefc09c018c4bda03c | address_space_specific constructor | m_unmap_w = new handler_entry_write_unmapped<Width, AddrShift>(this, 0); | reference emulator, differential (D-02) |
| S31c | Unspecified write-dispatch entries use the unmapped handler | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/emumem_hedw.ipp | 2026-10-16 | 9aaaa5dc9cab4db87300ac7516a50481d57bcfbe5b51f871660dcedeb1e53f81 | handler_entry_write_dispatch constructor, default handler and slot initialization | handler = space->get_unmap_w<Width, AddrShift>(); | reference emulator, differential (D-02) |
| S31d | The default write getter returns the unmapped-write instance | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/emumem.h | 2026-10-16 | 4285ca50a0c14b6038c7443bab45340834f0e4b741f0549a127c4ba7cc1c3e2e | address_space::get_unmap_w | get_unmap_w() const { return static_cast<handler_entry_write_unmapped<Width, AddrShift> *>(m_unmap_w); } | reference emulator, differential (D-02) |
| S31e | Unmapped writes optionally log and discard the data without a bus fault | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/emu/emumem_heun.cpp | 2026-10-16 | 3a4014cdb03eb6239b340832dd02b34ee17e1eeab0ded10f8824483448239d92 | handler_entry_write_unmapped::write body; no device write or exception | void handler_entry_write_unmapped<Width, AddrShift>::write(offs_t offset, uX data, uX mem_mask)const | reference emulator, differential (D-02); physical electrical behavior unqualified |
| S32 | MAME raw video timing uses the documented horizontal visible boundary | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.h | 2026-10-19 | 91324fcc5567399a6f524d65d8c7d7c5c82e8f816eee8ddbbb6dc6291bffb08a | NEOGEO_HBEND | #define NEOGEO_HBEND (0x01c) | reference emulator, differential (D-02) |
| S32a | MAME raw video timing uses the documented vertical visible boundary | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.h | 2026-10-19 | 91324fcc5567399a6f524d65d8c7d7c5c82e8f816eee8ddbbb6dc6291bffb08a | NEOGEO_VBEND | #define NEOGEO_VBEND (0x010) | reference emulator, differential (D-02) |
| S32b | Screen active bounds are supplied from the raw timing constants | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-19 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | screen raw timing setup | m_screen->set_raw(NEOGEO_PIXEL_CLOCK, NEOGEO_HTOTAL, NEOGEO_HBEND, NEOGEO_HBSTART, NEOGEO_VTOTAL, NEOGEO_VBEND, NEOGEO_VBSTART); | reference emulator, differential (D-02) |
| S33 | The fixed map begins at VRAM word 0x7000 with row indexed by scanline | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | fixed-layer map base | const u16 *video_data = &m_videoram_drawsource[0x7000 | (scanline >> 3)]; | reference emulator, differential (D-02) |
| S33a | Fixed map columns use a 0x20-word stride | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | fixed-layer column stride | video_data = video_data + 0x20; | reference emulator, differential (D-02) |
| S33b | Fixed tile addressing uses 32 bytes per tile and the row low bits | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | fixed-tile ROM address | const int gfx_offset = ((code << 5) | (scanline & 0x07)) & addr_mask; | reference emulator, differential (D-02) |
| S33c | Fixed-pixel byte groups are read in the device's non-linear order | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | fixed-pixel byte offsets | static const u32 pix_offsets[] = { 0x10, 0x18, 0x00, 0x08 }; | reference emulator, differential (D-02) |
| S33d | Each fixed graphics byte emits its low-nibble pen first | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | fixed-pixel low nibble | if (data & 0x0f) | reference emulator, differential (D-02) |
| S33e | Each fixed graphics byte emits its high-nibble pen second | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | fixed-pixel high nibble | if (data & 0xf0) | reference emulator, differential (D-02) |
| S34 | MAME's palette write extracts five color bits per channel and a dark bit | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | palette channel extraction | uint8_t const r = ((data >> 14) & 0x1) | ((data >> 7) & 0x1e); | reference emulator, differential (D-02) |
| S34b | MAME's green channel uses bits 4-7 plus bit 13 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | palette green extraction | uint8_t const g = ((data >> 13) & 0x1) | ((data >> 3) & 0x1e); | reference emulator, differential (D-02) |
| S34c | MAME's blue channel uses bits 0-3 plus bit 12 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | palette blue extraction | uint8_t const b = ((data >> 12) & 0x1) | ((data << 1) & 0x1e); | reference emulator, differential (D-02) |
| S34d | MAME fixed-layer palette selector chooses a 16-pen group | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | fixed-layer character pens | const pen_t *char_pens = &m_pens[code_and_palette >> 12 << m_bppshift]; | reference emulator, differential (D-02) |
| S34e | The selected palette bank offsets the fixed pen base by 0x1000 entries | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | set_palette_bank and set_pens | m_palette_bank = state ? 0x1000 : 0; | reference emulator, differential (D-02) |
| S34a | MAME selects palette word 0xfff as the screen backdrop | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | background palette pen | m_bg_pen = pen_base + 0xfff; | reference emulator, differential (D-02) |
| S34f | System-latch Q0 selects MAME's second, shadow palette pen bank | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | `set_screen_shadow` and `set_pens` | `m_palette->pens() + m_palette_bank + (m_screen_shadow ? 0x2000 : 0)` | reference emulator, differential (D-02) |
| S34g | Palette bit 15 selects the dark lookup; normal and shadow pen banks are computed from four resistor modes | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | `paletteram_w`, lookup variants | `uint8_t const dark = data >> 15;` | reference emulator, differential (D-02) |
| S34h | MAME derives its normal/dark/shadow lookup weights from five color resistors plus 8200-ohm and 150-ohm pull-downs | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | `create_rgb_lookups` | `{3900, 2200, 1000, 470, 220}`; dark `8200`; shadow `150` | reference emulator, differential (D-02) |
| S35 | MAME parses a maximum 381 sprite numbers into at most 96 entries per scanline, preserving their order | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | `parse_sprites`, limits and active-list insertion | `MAX_SPRITES_PER_SCREEN = 381`; `MAX_SPRITES_PER_LINE = 96`; `*sprite_list = sprite_number` | reference emulator, differential (D-02) |
| S35a | A chained sprite inherits the preceding block's Y/row extent and advances X by previous zoom-X plus one | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | `draw_sprites`, chained and new-block controls | `x = (x + zoom_x + 1) & 0x01ff;` | reference emulator, differential (D-02) |
| S35b | MAME's fixed/sprite composition draws sprites before the fixed layer | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_v.cpp | 2026-10-19 | 0532050c3e4c6543979f6145223f69b966bfb8db8ab10010dbcd63ee10689a7d | `screen_update` composition order | `m_sprgen->draw_sprites(...); m_sprgen->draw_fixed_layer(...);` | reference emulator, differential (D-02) |
| S36 | The regular sprite decoder maps four raw bytes to one 8-pixel half-row and emits source bits least-significant first | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | `draw_pixel` regular device plane mapping | `(BIT(src[0x3], x) << 3) | (BIT(src[0x1], x) << 2) | (BIT(src[0x2], x) << 1) | BIT(src[0x0], x)` | reference emulator, differential (D-02) |
| S36a | Optimized sprite decoding places the raw `0x40` half-row before the raw `0x00` half-row in each tile | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | `optimize_helper`, tile/row expansion | `src[0x43 | (y << 2)]` followed by `src[0x03 | (y << 2)]` | reference emulator, differential (D-02) |
| S37 | MAME uses a 16-entry source-pinned horizontal zoom bit pattern; emitted pixels are transparent when pen zero | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | `zoom_x_tables` and sprite `draw_pixel` | `0x0080, 0x0880, 0x0888, 0x2888, 0x288a, 0x2a8a, 0x2aaa, 0xaaaa, 0xaaea, 0xbaea, 0xbaeb, 0xbbeb, 0xbbef, 0xfbef, 0xfbff, 0xffff` | reference emulator, differential (D-02) |
| S37a | Sprite attribute bits select horizontal/vertical flip, four code-animation bits, and a palette group | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | `draw_sprites`, code, flips and line palette | `attr >> 8 << m_bppshift` | reference emulator, differential (D-02) |
| S38 | MAME sources the vertical zoom lookup as a distinct `000-lo.lo` 0x20000-byte region | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-19 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | `ROM_Y_ZOOM` | `ROM_REGION(0x20000, "spritegen:zoomy", 0); ROM_LOAD("000-lo.lo", ...)` | reference emulator, differential (D-02) |
| S38a | MAME indexes vertical zoom with the zoom byte and source scanline, then uses the result for tile/row selection | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo_spr.cpp | 2026-10-19 | 1ad3de4bd399c4dff3ea131f181e45746db623b4feac320af3eab807e93f2668 | `draw_sprites`, vertical zoom lookup | `m_region_zoomy[(zoom_y << 8) | zoom_line]` | reference emulator, differential (D-02) |
| S38b | MAME pins the board lookup source identity | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-20 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | `ROM_Y_ZOOM` | `000-lo.lo`, `0x20000`, CRC `5a86cff2`, SHA-1 `5992277debadeb64d1c1c64b0a92d9293eaf7e4a` | reference emulator, differential (D-02); public metadata validates input but is not hardware truth |
| S40 | Selected MSLUGX slot case installs its protection device | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-19 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | `install_banks` MSLUGX case | case NEOGEO_MSLUGX: | reference emulator, differential (D-02) |
| S40a | MSLUGX slot installs its 16-bit protection read handler | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-19 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | MSLUGX protection read map | space.install_read_handler(0x2fffe0, 0x2fffef, read16m_delegate(*m_slots[m_curr_slot], FUNC(neogeo_cart_slot_device::protection_r))); | reference emulator, differential (D-02) |
| S40b | MSLUGX slot installs its 16-bit protection write handler | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp | 2026-10-19 | 77324df687d4cf49c6874a9f83d6253a69f7db59404b878a51685850207afc97 | MSLUGX protection write map | space.install_write_handler(0x2fffe0, 0x2fffef, write16s_delegate(*m_slots[m_curr_slot], FUNC(neogeo_cart_slot_device::protection_w))); | reference emulator, differential (D-02) |
| S40c | A new MSLUGX command sequence clears the previous command | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo/prot_mslugx.cpp | 2026-10-19 | e54094e80e58c517b8d4bb55be479ddf3424ff974b44858613d159553aa1f9d4 | `protection_w` command reset | m_command = 0; | reference emulator, differential (D-02) |
| S40d | Command 1 reads a serial bit from the P1 protection table | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo/prot_mslugx.cpp | 2026-10-19 | e54094e80e58c517b8d4bb55be479ddf3424ff974b44858613d159553aa1f9d4 | `protection_r` command 1 | res = (space.read_byte(0xdedd2 + ((m_counter >> 3) & 0xfff)) >> (~m_counter & 0x07)) & 1; | reference emulator, differential (D-02) |
| S40e | Command 0x0fff uses an explicitly uncertain work-RAM-selected index | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo/prot_mslugx.cpp | 2026-10-19 | e54094e80e58c517b8d4bb55be479ddf3424ff974b44858613d159553aa1f9d4 | `protection_r` command 0x0fff selector | int32_t select = space.read_word(0x10f00a) - 1; // How should this be calculated? | reference emulator, differential (D-02) |
| S40f | MSLUGX protection counter initializes to zero | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo/prot_mslugx.cpp | 2026-10-19 | e54094e80e58c517b8d4bb55be479ddf3424ff974b44858613d159553aa1f9d4 | constructor counter initialization | m_counter(0), | reference emulator, differential (D-02) |
| S40g | MSLUGX protection command initializes to zero | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo/prot_mslugx.cpp | 2026-10-19 | e54094e80e58c517b8d4bb55be479ddf3424ff974b44858613d159553aa1f9d4 | constructor command initialization | m_command(0) | reference emulator, differential (D-02) |
| S40h | MAME's MSLUGX device reset leaves command and counter unchanged | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo/prot_mslugx.cpp | 2026-10-19 | e54094e80e58c517b8d4bb55be479ddf3424ff974b44858613d159553aa1f9d4 | `device_reset` | void mslugx_prot_device::device_reset() | reference emulator, differential (D-02) |
| S41 | MAME defines P1 joystick directions and buttons A-D as active-low bits 0-7 | https://raw.githubusercontent.com/mamedev/mame/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo_ctrl/joystick.cpp | 2026-10-20 | 6dce1b78684139e9b4e8869af0136253156e0285a863b863c96909777836bdb7 | INPUT_PORTS_START(neogeo_joy_ac), JOY1 | PORT_BIT( 0x01, IP_ACTIVE_LOW, IPT_JOYSTICK_UP ) PORT_PLAYER(1) PORT_BIT( 0x02, IP_ACTIVE_LOW, IPT_JOYSTICK_DOWN ) PORT_PLAYER(1) PORT_BIT( 0x04, IP_ACTIVE_LOW, IPT_JOYSTICK_LEFT ) PORT_PLAYER(1) PORT_BIT( 0x08, IP_ACTIVE_LOW, IPT_JOYSTICK_RIGHT ) PORT_PLAYER(1) PORT_BIT( 0x10, IP_ACTIVE_LOW, IPT_BUTTON1 ) PORT_PLAYER(1) PORT_NAME("%p A") PORT_BIT( 0x20, IP_ACTIVE_LOW, IPT_BUTTON2 ) PORT_PLAYER(1) PORT_NAME("%p B") PORT_BIT( 0x40, IP_ACTIVE_LOW, IPT_BUTTON3 ) PORT_PLAYER(1) PORT_NAME("%p C") PORT_BIT( 0x80, IP_ACTIVE_LOW, IPT_BUTTON4 ) PORT_PLAYER(1) PORT_NAME("%p D") | reference emulator, differential (D6-03/D6-05); not physical-board truth |

## Video rendering references (fetched)

The primary hardware reference used for video layout is SNK, *Neo-Geo Hardware
Specification*, in the publicly hosted scan at
https://www.neogeodev.org/NG.pdf. It was fetched on 2026-10-19 (SHA-256
`910f0f02cafdbf19188bff88053c9427243d087a7aabc2e715e3bc8a1182f111`). The
printed Hardware pages 4-6 and 15-21 and Software Development pages 4-6 describe
the FIX character size, active area, palette fields, sprite dimensions and
priority. The scan has no explicit revision identifier; its cover lists dates
through 1991. Claims in it are treated as primary documentation, with scan/OCR
uncertainty retained. No page image or ROM data is copied into this repository.

The fixed-tile byte order, palette bit extraction, sprite-strip decode,
scanline list bounds, horizontal zoom, vertical lookup index, composition order,
and raw visible origin are cross-checked against pinned MAME revision
`31e52312c59e4d60d70235118bcbccd220f5232e` (S32-S38b). These are
reference-emulator differential evidence, not measured physical-board behavior.

The SNK specification calls `$ff` the maximum 8-bit vertical-reduction value
(Hardware p.4) and describes 256 levels from 100% to 0% (Software Development
p.5), but does not specify the lookup algorithm. GNMV v3 carries the exact
0x20000-byte role-8 board table and the renderer indexes it as
`(zoom_y << 8) | zoom_line`, based on differential MAME evidence S38a. V1/v2
remain supported: they render full-scale Y zoom and return
`GN_STATUS_UNSUPPORTED_PROFILE` when a visible sprite requests fractional
Y-zoom because those versions carry no lookup table. Both index components are
8-bit, so the current lookup index is bounded by `0xffff`; the full 0x20000-byte
source region and identity are still validated. Synthetic table tests use
independently authored values; neither MAME/GPL implementation code nor private
ROM bytes are used as runtime or test oracle.

The native renderer expands each five-bit palette component with
`(value * 255 + 15) / 31`. The palette dark bit and system-latch shadow select
the corresponding dimmed lookup modes. Their fixed-point scaling ratios are
derived from MAME's pinned resistor network and pull-down values; they scale the
linear host representation and are not a reconstruction of MAME's resistor
solver, measurement of the board's analog RGB transfer curve, or physical
hardware claim.
The original synthetic guests select fixed map entries and sprite controls and
write their palette words through the emulated bus. Expected pixels are
calculated from the documented fixed-nibble and sprite-bitplane layouts, the
pinned horizontal zoom table, and independent palette values. Sprite rows are
drawn before the fixed layer, and MAME's dark palette and system-latch shadow
selections are represented by the documented fixed-point host scaling. The
For v3 media the renderer uses the owned role-8 table for visible sprite rows;
for v1/v2 media an active sprite requesting Y zoom other than `0xff` returns
`GN_STATUS_UNSUPPORTED_PROFILE`. The current media loader admits only the
documented 128-KiB fixed-layer region; the renderer also rejects
other sizes because title-specific fixed-layer banking is not implemented.
These are explicit implementation limits, not a claim about the selected
title. Selected-screen behavior must be checked at the real guest boundary
before claiming attract/title coverage.

Plan 06-03 adds a synthetic guest composition check that writes the sprite,
FIX map and scenery/player/projectile palette groups through the emulated bus.
Across three input observations the guest moves scenery beneath stationary
player and projectile strips, while an opaque FIX pixel stays in front and a
transparent FIX pixel leaves the player visible. Native and libretro callback output must match pixel-for-pixel. This
qualifies the shared composition seam and its input-driven movement; it does
not stand in for the separately recorded selected-media scene observations or
establish complete title, analog-color or physical-board fidelity.

## Attract/start predicate

This is the contract plan 05-08 implements; it uses only addresses and values
that appear in the S-row excerpts above. The BIOS publishes a request code in
`BIOS_USER_REQUEST` at `$10FDAE` (S2, S2b: 2 is Demo, 3 is Title) and then
calls the cartridge's USER subroutine through the header jump at `$000122`
(S4, S4b). Games report what they are doing in `BIOS_USER_MODE` at `$10FDAF`
(S3, S3b: 1 is Title/Demo).

The ordered sequence accepted as "the BIOS asked the selected cartridge to run
its attract or title code":

1. A guest write, performed by an instruction in the BIOS region, of the Demo
   (2) or Title (3) value to `$10FDAE`.
2. A later instruction start at the USER entry `$000122` while the stored
   request is still Demo or Title.

A later write of 1 (Title/Demo) to `$10FDAF` by cartridge-region code
corroborates the sequence but is not required. The writer region comes from the
executing instruction's PC (`owned_cpu_current_instruction_pc`), not from a
watchpoint on private bytes.

Rejection reasons, reported instead of acceptance: `TRACE_OVERFLOW` (the bounded
event trace overflowed before a decision), `WRONG_SOURCE` (the request write
came from a non-BIOS region), `WRONG_VALUE` (the request write was not 2 or 3),
`WRONG_ORDER` (the USER-entry start preceded the request write, or the request
no longer held Demo or Title), and `NO_REQUEST` (no request write was observed).

Implementation (plan 05-08, `src/mvs/mvs_protocol.c`): each instance keeps a
fixed 64-event ring of guest byte or word writes that overlap `$10FD80`,
`$10FDAE` or `$10FDAF` plus instruction starts at `$000122`. A word write
yields one event per overlapped variable. The writer region is the class of the
executing instruction's PC: BIOS `$C00000-$CFFFFF`, cartridge fixed
`$000000-$0FFFFF`, cartridge banked `$200000-$2FFFFF`, work RAM
`$100000-$10FFFF`, otherwise other. An instruction start is detected at the
instruction boundary when the next-instruction PC equals `$000122` and the CPU
is not stopped. Identical consecutive events are coalesced, an event that does
not fit increments a dropped counter (reported as `TRACE_OVERFLOW`), and once
an accepted request-then-entry pair exists recording stops except for the
optional corroboration flag. Host-side test hooks run outside the guest run
loop and never record. `mvs_qualify` evaluates the verdict after every chunk
and, when accepted, prints `{"status":"attract_start","guest_executed":true,
"checkpoint":{"user_request":"demo"|"title","chunk":N,
"user_mode_corroborated":true|false}}`; the 256-chunk bound is unchanged.
`tests/mvs/test_mvs.c --attract-predicate` holds the rights-clear synthetic
positive and the wrong-value, wrong-source, wrong-order, no-request and
overflow controls.

The predicate is title-independent: it names only BIOS-published locations and
the common 68k program header, never a game, a program byte or a private value.
It is community documentation (S1-S6) plus a MAME differential for the
cartridge window (S7). Hardware truth is not established: the NeoGeo
Development Wiki is not an authoritative SNK specification and MAME output is
not hardware truth. Acceptance means only that the documented BIOS-to-cartridge
handoff occurred in this emulation; it does not mean the title or attract mode
rendered, and GAME-02 stays Pending until a selected-media run meets it.

`PLAYER_START` at `$000128` (S5, S5b, S5c) is recorded for plan 05-14 and is not
part of this predicate.

## Stall diagnosis

When a bounded selected-media run ends without the predicate, the ignored local
report may carry these fields so the next plan can see where the BIOS is
waiting:

- `polled_registers`: the top 8 most-read registers, restricted to the public
  windows `$300000-$3FFFFF` and `$2FFFE0-$2FFFFF`.
- `interrupts_taken`, `irq_ack_writes`.
- `sr_mask_histogram[8]`: executed instructions bucketed by the SR interrupt
  mask.
- `pc_region_histogram[5]`: executed instructions bucketed by coarse PC region.
- `low_program_window_reads`: reads served by the `$000080-$0FFFFF` cartridge
  window.
- `unmapped_read_count`.
- The last observed `BIOS_SYSTEM_MODE`, `BIOS_USER_REQUEST` and
  `BIOS_USER_MODE` values.

Implementation (plan 05-08): the counters live in the per-instance
`gn_mvs_protocol` and are sampled only from guest activity inside `gn_run_mvs`.
`sr_mask_histogram` and `pc_region_histogram` count instructions per step,
bucketed by the SR mask and PC region the instruction started with (regions as
in the predicate section). `interrupts_taken` counts exception-only steps that
leave an autovector 25-31 (see "Interrupts and timing"); the VBlank producer is
the only source modeled. `low_program_window_reads`
counts every read served from `$000080-$0FFFFF`, including instruction fetches
executed from the window. `polled_registers` keeps up to 32 distinct addresses
as exact access addresses (byte reads keep the odd address), ranked by reads
with ties by ascending address, and reports at most 8 as hex strings in the
ignored report; reads that do not fit the table are counted in
`polled_untracked_reads`. `unmapped_read_count` counts guest reads that raised
the MVS bus fault. The report also carries the last `BIOS_SYSTEM_MODE`,
`BIOS_USER_REQUEST` and `BIOS_USER_MODE` bytes (`bios_variables`) and the
current predicate rejection name (`attract_rejection`, `NONE` while pending).
`qualify_local_boot.py` drops any key, type or row outside this shape, including
polled rows outside the two public windows. Word and byte reads in the P1 and
banked P2 program windows are served from the program region subject to loaded
bytes. `$300000-$3fffff` belongs to the I/O map: documented DIPSW, control,
status, calendar and latch decodes are handled separately, and unsupported
addresses fault rather than falling through to cartridge bytes.

Run `python3 tools/mvs/qualify_local_boot.py` for one local bounded diagnostic, or
`python3 tools/mvs/qualify_local_boot.py --check-fresh` to check the selected
tools without importing media or running the guest. Both commands build the
`mvs_importer` and `mvs_qualify` targets with the `owned-debug` CMake preset;
the normal incremental build preserves existing binaries and retains CMake's
source/build freshness checks. The wrapper confirms a no-work Ninja dry run,
then captures each executable's resolved path and SHA-256 for in-process
identity checks. Importer identity is checked before use, and the qualifier
identity is checked before import and immediately before guest execution.
Changed bytes or pending build work refuse the guest run. These checks do not
defend against a concurrent hostile writer replacing an executable between the
last identity check and process launch.

Each selected invocation has a 180-second build timeout, 30-second freshness
dry-run timeout, 30-second importer timeout, and 120-second native-qualifier
timeout. Input limits remain 96 MiB per source ZIP, 128 MiB combined ZIP bytes,
64 entries, 8 MiB per entry, 128 MiB combined expanded source data, and 64 MiB
for the normalized bundle. The guest runner stops within at most 256 chunks of
1,000,000 emulated cycles each; the optional scripted input schedule is limited
to frame 1200 of 202,752 cycles each after attract/start, holding each button
state until the next scheduled event. The wrapper accepts at
most 1 MiB combined native stdout and stderr and at most 1 MiB per saved JSON
report. These host limits bound diagnosis work while leaving emulated hardware
time explicit.

The default input directory is `local/roms/`, which must remain ignored by
Git. Each run writes an invocation-specific `local/qualification/phase05-<id>.json`
report; negative controls use `phase05-negative-<id>.json`. Reports are private
local output. They are published atomically only after serialization and size
checks, and an existing report is never replaced. Build or import failures,
native errors, timeout receipts, and interrupted native runs remain available
for diagnosis. Raw process output, archive names, media hashes and paths are not
copied into the report. A timeout or interruption after native launch records
`qualification_invocation_state: uncertain`; a completed producer exit alone
does not establish guest success. A successful selected result still requires
the exact `attract_start` schema, producer exit status 0, and
`guest_executed: true`.

The wrapper reports executable identities only to its in-process checks; it
does not create per-run admissions, publication permissions or lifetime
accounting. An absent local input remains an availability outcome. Synthetic
executable identities are confined to tests and cannot produce a production
qualification result. Import/freshness outcomes alone do not qualify a selected
title; the bounded boot/scenario evidence is separate, as scoped above.

Privacy rule: tracked records and public projections contain no private PCs,
fetched instruction words, ROM bytes, private-byte hashes or local paths. Only
the ignored local report may retain the bounded private execution fields
described below; it never contains source media bytes or identities.

Historical sound-candidate disposition: `05-27-SOUND-REVIEW.md` preserves the earlier five findings and relocated-consumer failures. It does not own current routing. Later repairs, native causal sound, current relocated C consumer checks and actual frontend recording/route evidence are recorded by Phase07 Plans04–06 and the current scope above. Synthetic-handler execution alone never closes physical timing or broader selected-program support.

## Native failure diagnosis and guest progress

The private qualifier reports a core or bus fault as `unsupported_guest_event`
and an earlier native orchestration failure as `native_execution_error`.
When the native core captured a first failure, either local outcome can carry
the `native_failure` object:
object has a fixed typed schema: component, stage, reason, finite site/cause/
status tokens and validity flags, emulated cycle/instruction-boundary data,
and optional PC/opcode/bus-operation/address/width values. Unknown details use
explicit unknown tokens and false validity flags; unavailable numeric values
are zero. Components are
`main_cpu`, `sound_cpu`, `board`, or `internal`; stages are `observe`,
`irq_update`, `execute`, `bus_access`, `sound_catchup`, `watchdog_reset`, or
`timing_accounting`; reasons are `internal_failure`, `bus_failure`,
`cycle_limit`, `invalid_state`, `clock_overflow`, or `accounting_mismatch`.
Only tested component/stage/reason/site/cause/status combinations are valid.
For owned-CPU execution failures, `underlying_status` records the bounded CPU
reason (for example, `owned_cpu_unsupported_opcode`); injected failures and
older reports may still leave it unknown. The local report retains these
bounded private execution details for diagnosis.
The separate `public_result` projection contains only generic status,
`guest_executed`, and finite component/stage/reason/site tokens; it drops
validity flags, cycle and instruction counts, PC/opcode, bus details, media
identity, paths, hashes and raw native diagnostics. The historical main-fault
access and underlying cause remain unknown; synthetic diagnostics do not
retroactively identify that event.

`guest_executed` is independent of the failure category. It is true only after
at least one main-CPU instruction completed in this loaded qualifier instance,
including instructions completed in an earlier bounded run chunk. Attempted
instructions, elapsed or idle clocks, interrupt-only steps, and Z80 ticks do
not count. Older generic `native_execution_error` reports without this field
remain unclassified; progress is never inferred from the status token.

The host wrapper accepts `attract_start` only when the native qualifier exits
with status 0 and the exact checkpoint schema above. Exit status 1 may carry a
bounded `unsupported_guest_event` or `native_execution_error` schema. A captured
guest fault includes validated completed-instruction progress, including zero
when the first instruction faults; bus callback faults are guest events, while
other core and orchestration failures retain `native_execution_error`. Other
nonzero or signal-termination results become generic
`native_qualification_failed` receipts without producer fields.
After native launcher entry, a stdout or stderr text-decoding error is also a
generic failure with `qualification_invocation_state: uncertain`. The main
command writes that safe receipt atomically and never includes raw output,
decoder details, or signal values.

The core stores only the first native cause, so later catch-up and unwind errors
cannot replace the event that first stopped the run. The metadata belongs to
one loaded MVS image, is cleared by `gn_reset` and successful image replacement,
and is not canonical guest state or a snapshot/persistence field. The sound
candidate's retained status and stage reset with its own machine state. These
diagnostics explain a native failure; they do not change guest execution or
qualify a title boot.

## Frontend capture readiness

The selected-media smoke waits, within its configured timeout, for the adapter's
final `MVS video checkpoint: 720 frames` log before requesting a screenshot.
The adapter emits six bounded checkpoints at 120-frame intervals through 720;
the earlier checkpoints help distinguish a stalled frontend from a late capture.
The counter advances only after successful guest execution, rendering and video
callback submission, and restarts on reset or unload. This is an empirically
calibrated diagnostic capture boundary, not a hardware timing or title oracle.
Early reset/boot frames can be entirely black; a fixed host sleep can capture
those frames before guest initialization has finished.

The adapter acquires its optional logging interface in `retro_init` and retains
it until `retro_deinit`. Environment setters can also be metadata probes:
[RetroArch's pinned implementation](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/runloop.c#L533-L553)
temporarily replaces that callback, then restores it with environment requests
disabled. Such probes must not erase the initialized runtime logger. Without a
logging interface, the readiness wait cannot establish its checkpoint and fails
within its timeout.

The capture reports `at-least-720-successful-video-frames`: hotkey delivery and
presentation can occur later, so the exact screenshot frame remains unmeasured.
Black images, runtime failures, identity failures and wrong titles still fail
their existing independent checks. Reaching the checkpoint alone cannot pass
recognizable-title acceptance. Missing checkpoints and early exits fail boundedly.

## Disabled command-NMI control

The synthetic `mvs_board_sound` fixture leaves audio NMI disabled while the
main-side command latch is pending. After a deterministic guest wait, the
command remains pending, the reply stays at its initial value, and the Z80
handler's sound-RAM sentinel is untouched. The guest then enables NMI through
its port write without a second command; the original command reaches the
handler, which consumes it, writes a command-derived sound-RAM marker and
publishes the reply. Reset clears the enable, pending, reply and RAM state.
The expectations are bound to the verified S25b-S25e source excerpts and are
synthetic mapping evidence, not physical-hardware, selected-game or audible
qualification.

## Unmapped audio I/O writes

The explicit audio write handlers retain their command, NMI, reply and YM2610
effects. Other sound-CPU I/O writes complete and discard their data, following
the pinned default-dispatch and unmapped-write chain in S31-S31e. This is
reference-emulator differential behavior, not a physical electrical claim.
Unmapped reads remain unsupported; no open-bus value is invented.

The original regression derives its port set from the complement of the cited
write map, using three high-byte boundaries. It verifies 744 guest write paths,
subsequent RAM/reply continuation and unchanged command, pending, NMI, bank and
YM register state. The 558 unsupported read neighbors still fail before those
guest side effects. Its bytes and expected results come from that source map
and original instruction sequences, with no private media ancestry.

A retained private diagnostic identified this write-rejection mechanism.
A later post-repair observation reported a main-bus access fault without its
exact access details. Successful selected continuation, audible output and
Phase05 acceptance remain unqualified. The former observation-permission
protocol is retired; current development follows
[DEVELOPMENT.md](../.planning/milestones/ws-first-playable-game-2026-10-24/DEVELOPMENT.md).
