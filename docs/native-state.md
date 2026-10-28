# Native continuation state

## Scope and ownership

`gn_state_*_v1` encodes bounded native continuation for two explicitly
implemented profiles: `GN_PROFILE_DIAGNOSTIC` and the admitted MVS MSX
profile. The diagnostic profile records its 68000 CPU and 4 KiB mapped RAM.
The MVS profile records the current bounded CPU, board, video, memory, Z80,
PCM converter, and YM2610 continuation. Each restore requires a separately
loaded owner with the same profile, configuration, replay behavior, and
normalized media identity. These schemas are not durable saves or replay
files. Their current tests do not establish cross-build compatibility or
broad hardware fidelity.

The Libretro frontend's actual state-file and selected MVS continuation
behavior is documented in [frontend-continuation.md](frontend-continuation.md).
That contract separates the native `GNST` payload from RetroArch's outer
`RASTATE` file and from durable SRAM saves.

The separate MVS backup-RAM transfer uses `durable_save_id` and the GNSV v1
contract in [`native-save.md`](native-save.md). It has its own owner, host
publication protocol, and narrower measured host limits; GNST restore is not a
disk commit.

The caller owns capture storage and may overwrite or release it as soon as
`gn_state_restore_v1` returns. The instance retains no caller buffer. Capture
and restore do not run the guest, call external devices, read or write files,
write output, or read host time. The native core continues to own the loaded
media, CPU, RAM, and callbacks for the full instance lifetime. Calls on one
instance remain single-threaded and non-reentrant.

## Public operations

| Operation | Contract |
| --- | --- |
| `gn_state_capacity_v1` | Requires a loaded diagnostic or MVS image and a naturally aligned writable `size_t`. Diagnostic capacity is 4,336 bytes. MVS capacity is derived once from its loaded memory extents and the checked Z80/YM payload sizes. Run, reset, capture, and restore do not change that loaded-image capacity. |
| `gn_state_capture_v1` | Requires a loaded supported image, a non-null caller buffer with the profile's exact capacity or more, a naturally aligned writable count, and either no detail (`NULL`, size 0) or an aligned v1 detail record of exactly `sizeof(gn_state_detail_v1)`. Success writes exactly the profile capacity; extra bytes stay untouched. A failed capture sets a safe non-overlapping count to zero. |
| `gn_state_restore_v1` | Requires a loaded supported image, a readable caller byte range whose length exactly matches that image's envelope, and an optional detail record using the same exact-size rule. The input is fully validated and staged before live guest state changes. |
| `gn_state_compatibility_v1` | Requires a loaded supported image and an aligned writable `gn_state_compatibility_info_v1` buffer whose size equals `sizeof` that record. Failure leaves the output record untouched. |
| `gn_state_reason_string` | Returns static fixed text for a reason value; unknown values return `unknown state reason`. The strings contain no guest input, host pointer, or path. |

All non-null pointers must refer to valid readable or writable host memory for
their advertised size and full call. Input, output, and detail ranges must not
overlap each other or live instance storage. The implementation detects known
instance, image, media, RAM, and CPU allocation ranges with overflow-safe
address arithmetic. It does not validate arbitrary, dangling, or fabricated
pointers. On an aliased output range, the function returns
`GN_STATUS_INVALID_ARGUMENT` without writing through the alias; the caller's
non-overlap precondition is not met. State input is consumed only during the
call and never retained.

The capacity and compatibility queries are side-effect free. Capacity is the
maximum emitted length, not a promise that an instance is currently eligible
to capture. For both supported profiles, capture is eligible after successful
load or reset and after a completed raw run or normal STOP. Capture does not
advance the guest, tick a chip, poll input, flush audio, or read host time. A
status-OK `GN_RUN_FAULT` or a latched MVS bus/device/sound failure blocks
capture with `GN_STATUS_INVALID_STATE` until reset or a successful restore.
Active CPU execution, an active PCM capture, and an active PCM sink also block
capture. The nested Z80 capture rejects a latched bus failure or invalid decoder
state; the YM capture rejects an active callback or latched candidate failure.
Capture does not stage candidates or evaluate the wrapper-to-chip relations
checked during restore. Restore can replace a previously faulted continuation
only after its entire profile-specific envelope has validated and all
staging/rebind work succeeds. Reset retains the cached media identity and
capacity.

`gn_status` values 0 through 6 remain unchanged. State details use the separate
fixed-width `gn_state_reason` and `gn_state_detail_v1` record. `detail_size`
must be zero when detail is null and must exactly match the v1 record size
otherwise. A detail record reports only numeric `reason`, `section`, `field`,
and byte `offset`; no input strings, addresses, or source bytes are returned.

| Detail reason | Status | Meaning |
| --- | --- | --- |
| `NONE` | `GN_STATUS_OK` | Operation succeeded. |
| `INVALID_ARGUMENT` | `GN_STATUS_INVALID_ARGUMENT` | Required pointer, size, or call argument is invalid. |
| `INVALID_STATE` | `GN_STATUS_INVALID_STATE` | No loaded image or no cached supported-profile identity/capacity. |
| `UNSUPPORTED_PROFILE` | `GN_STATUS_UNSUPPORTED_PROFILE` | Loaded image is outside the diagnostic and MVS MSX codecs, or a requested identity is not implemented. |
| `ACTIVE_CALL` | `GN_STATUS_INVALID_STATE` | CPU execution is active. |
| `GUEST_FAULT` | `GN_STATUS_INVALID_STATE` | A raw status-OK guest fault or MVS bus/device failure is latched since load/reset/restore. |
| `CPU_STATE` | `GN_STATUS_CPU_FAILURE` for capture; `GN_STATUS_INVALID_MEDIA` for an invalid encoded record | CPU capture or semantic CPU relation is invalid. |
| `CAPACITY` | `GN_STATUS_INVALID_ARGUMENT` | Non-null capture buffer capacity is below the loaded profile's exact size; payload bytes are untouched and a separate count is zero. A null capture buffer reports `INVALID_ARGUMENT`, including when capacity is zero. |
| `TRUNCATED` / `TRAILING_BYTES` | `GN_STATUS_INVALID_ARGUMENT` | Restore length is smaller/larger than the exact envelope. |
| `FORMAT` | `GN_STATUS_INVALID_ARGUMENT` | Magic, envelope version, header size, total size, or format ID does not match. |
| `SECTION` / `RESERVED` | `GN_STATUS_INVALID_MEDIA` | Required section shape/order or zero-reserved field is invalid. |
| `REPLAY_IDENTITY` / `PROFILE_IDENTITY` / `CONFIGURATION_IDENTITY` | `GN_STATUS_UNSUPPORTED_PROFILE` | The corresponding semantic identity is not implemented by this reader. |
| `MEDIA_IDENTITY` | `GN_STATUS_INVALID_MEDIA` | The loaded immutable normalized media differs from the envelope. |
| `ALIAS` | `GN_STATUS_INVALID_ARGUMENT` | A known live-owned range overlaps capture input/output. |

Some precondition failures that make the detail destination itself unsafe or
aliased leave that detail destination untouched. Aliased count/payload ranges
are rejected before any attempted write. A restore whose detail record overlaps
its input bytes is rejected before detail initialization, leaving both ranges
untouched. A valid, separate count is set to
zero before capacity, lifecycle, eligibility, or CPU-state failures.

## MVS MSX continuation profile

MVS MSX uses the shared v1 `GNST` envelope header and five required sections
in fixed order: CPU (1), memory (2), board (3), sound (4), YM2610 (5). Every
integer is fixed-width big-endian; native C structure bytes and pointers are
never serialized. The header uses format ID 1, replay ID 1, profile
`GN_MVS_PROFILE_MSX`, configuration ID 2, the cached MVS media digest, section
count 5, and a zero reserved word. Length must equal the capacity cached for
the loaded image, with no truncated or trailing bytes.

| Section | Payload contract | Current public fixture measurement |
| --- | --- | ---: |
| CPU (1) | Named 68000 CPU fields and counters; 152 bytes. | 152 bytes |
| Memory (2) | Work RAM, backup RAM, palette RAM, then video RAM words encoded big-endian. Length is derived from the loaded allocations. | 217,088 bytes: 65,536 + 65,536 + 16,384 + 34,816 × 2 |
| Board (3) | Fixed schema for registers, protection/banks, input, raster/IRQ/frame carry, watchdog, calendar, scheduler, progress counters, and bounded protocol observations. | 2,794 bytes |
| Sound (4) | Canonical `GZ80` v1 payload followed by guest handshake/RAM/banks, PCM phase, and both filter histories. | 2,781 bytes: 76-byte Z80 + 2,705-byte fixed payload |
| YM2610 (5) | Exact checked private `GYM1` v1 payload; size is queried from the staged/current candidate. | 1,186 bytes for this fixture and source revision |

With the public fixture produced by `public_sound_test --write-fixture`, the
measured envelope capacity is **224,113 bytes**: 72-byte header + 40 bytes of
section headers + the five payload sizes above. Capacity is calculated from
the loaded memory extents plus actual Z80 and YM payload sizes at successful
load, then remains stable across run, reset, capture, restore, and failed media
replacement. The 1,186-byte YM payload is a measurement for this fixture, not
a universal constant. No ROM/BIOS bytes are included in this evidence.

The media identity is SHA-256 over a domain tag, MVS profile/configuration,
then every role from BIOS through Y-zoom in ascending role order. For each
role, it hashes the role number and a presence flag, and, when present, the
effective loaded extent and transformed bytes. Thus manifest descriptor order
and the caller's linear/word-swap selector do not affect identity when the
effective bytes match. Optional audio-BIOS presence, any effective role bytes
or extent, profile, or configuration changes the digest. The digest is cached
only on successful load; a failed replacement preserves the previous image,
identity, and capacity. Reset and restore do not recompute it.

Restore checks outer identities and exact section IDs/lengths before nested
validation. It stages the CPU state, board and sound scalar payloads, GZ80 and
GYM1 candidates, destination callbacks, and owned allocations before changing
the live image. The commit keeps the destination image, allocator, media,
callbacks, and work/save/palette/video allocation addresses; it copies the
historical guest bytes into those existing allocations and transfers staged
chip ownership. The current commit path makes no fallible image allocation or
callback after apply begins. Rejected restores leave the previous state and
backup-RAM address unchanged. The caller may overwrite or free the input as
soon as restore returns; the core never retains it.

MVS capture is eligible after load/reset and completed raw, frame, or STOP
boundaries, provided no active call, bus fault, MVS failure, sound failure, or
active PCM sink/capture is latched. A raw `GN_RUN_FAULT` with `GN_STATUS_OK`
is also fault-latched and blocks capture. A validated restore can recover the
tested raw guest-fault and sound-device-fault classes by installing a clean
continuation; it does not run the guest to repair state. Rejected input does
not advance the guest, tick chips, poll controls, write output, or clear the
fault. Capture failures leave payload bytes untouched and set a safe separate
count to zero. A null payload pointer is `INVALID_ARGUMENT`, even with a zero
capacity; a non-null short buffer is `CAPACITY`; an oversized capture writes
only the exact envelope; and restore rejects short/trailing input before
mutation. Known caller/live-storage aliases are rejected before writing
through the alias.

The resource bounds below account for C/C++ requested objects and stack guest
staging separately from the 224,113-byte envelope. The private MVS transaction
suite verifies exact future
guest/video/PCM/time continuation, status-OK raw-fault rejection/recovery,
sound-fault recovery, stable backup-RAM address, and caller transfer-buffer
lifetime. The identity suite verifies normalized role/layout equivalence,
foreign-media/configuration/profile/replay/format/section rejection, optional
role presence, reset/failed-replacement capacity stability, and rejected-load
state-byte equality.

## Diagnostic envelope v1

Every integer is unsigned, fixed-width, and big-endian. The diagnostic
envelope is exactly 4,336 bytes: a 72-byte header followed by the required CPU
and RAM sections in that order. No native C structure layout is serialized.

| Offset | Size | Field | Value |
| ---: | ---: | --- | --- |
| 0 | 4 | Magic | ASCII `GNST` |
| 4 | 4 | Envelope version | 1 |
| 8 | 4 | Header size | 72 |
| 12 | 4 | Total length | 4,336 |
| 16 | 4 | Format ID | 1 |
| 20 | 4 | Replay behavior ID | 1 |
| 24 | 4 | Profile ID | `GN_PROFILE_DIAGNOSTIC` (1) |
| 28 | 4 | Configuration ID | Diagnostic configuration v1 (1) |
| 32 | 32 | Media identity | Cached SHA-256 digest |
| 64 | 4 | Required section count | 2 |
| 68 | 4 | Reserved | Must be zero |

Each section starts with a big-endian `(section_id, payload_length)` pair. CPU
section ID 1 has a 152-byte payload; RAM section ID 2 has a 4,096-byte payload.
The RAM section is the mapped diagnostic region at guest address `0x1000`.
Reserved header and CPU bytes must be zero. Missing, reordered, duplicate,
unknown, or incorrectly sized sections are rejected.

The CPU payload encodes named D0-D7 and A0-A7 registers, PC, previous PC, USP,
SSP, fault PC, SR, instruction register, stopped/IRQ/reset/exception fields,
then completed instruction, instruction, reset, exception, idle, total-cycle,
and reset-signal counters. Its 3 reserved bytes follow the five one-byte
control fields. Validation checks CPU scalar domains, active stack relation,
reset debt, and counter arithmetic before apply. Capture and restore preserve
the current diagnostic backend's exact integer counters; the implementation
does not infer fractional sound phase or MVS frame carry.

The envelope includes only future-affecting guest state and required immutable
identity. Private CPU pointers, callbacks, allocator bindings, trace history,
host observations, frontend output, and test hooks are not serialized. CPU
apply preserves the destination's bus and allocator bindings and clears its
observation-only fetch trace. RAM and CPU are staged and validated before a
no-allocation, no-callback apply. A successful restore copies staged RAM and
clears the diagnostic guest-fault latch; rejection leaves live CPU and RAM
unchanged.

## Independent compatibility identities

`gn_state_compatibility_info_v1` exposes separate fields for format, replay
behavior, durable-save, public ABI, profile, and configuration compatibility.
The current format, replay, and public ABI IDs are 1. Diagnostic profile and
configuration IDs are 1; MVS uses `GN_MVS_PROFILE_MSX` and configuration ID 2.
They occupy separate fields and have separate meanings; their values may be
versioned independently. Durable backup-RAM bytes have a separate GNSV codec
and ownership contract in [`native-save.md`](native-save.md); they are not part
of this GNST continuation schema.

### Durable save compatibility field

| Loaded profile | `durable_save_id` | Meaning |
|---|---:|---|
| `GN_PROFILE_DIAGNOSTIC` | 0 | No durable-save transfer for the diagnostic profile |
| `GN_MVS_PROFILE_MSX` | 1 | `GN_MVS_SAVE_ID_V1`; the bounded MVS backup-RAM transfer is available |
| Unsupported profile | — | Compatibility query rejects the profile; no save identity is issued |

No network-security claim follows from either continuation or save identity.
The named full-SDK Debug/Release continuation evidence is limited to the exact
executed pair below.

The format, replay, profile, and configuration IDs are import gates. A
reader rejects unsupported values before nested CPU or RAM state can be
applied. The public ABI ID is descriptive compatibility metadata; it is not a
claim that a state byte buffer is a C ABI. The media SHA-256 is also an import
gate, but it is not a source-code hash, MAC, signature, proof of authenticity,
proof of distribution rights, or evidence that two implementations are
equivalent.

At successful diagnostic load, the core hashes one canonical role order:

1. A domain tag, profile and configuration IDs.
2. ROM role, guest base, mapped length, source length, and all immutable ROM
   bytes.
3. RAM role, guest base, mapped length, supplied initialization-prefix length,
   and all 4,096 effective initial RAM bytes after zero-fill.

Manifest descriptor order and host source pointers are excluded. Role, base,
extent, source-prefix presence/length, effective mapped bytes, profile, or
configuration changes alter the normalized preimage. The digest is cached
after load and remains fixed through reset, run, capture, and restore; unload
or replacement ends that cache lifetime.

For MVS, the normalized identity hashes a separate domain tag, MVS profile and
configuration, then each role in ascending role order: role number, explicit
presence flag, and, when present, effective owned extent and transformed bytes.
The caller's descriptor order and layout selector are excluded after the
loader has copied or word-swapped bytes. Equivalent effective role bytes
therefore produce equal identities when manifest order or layout
representation differs. Optional audio-BIOS or Y-zoom presence is part of the
preimage, as are every role's length and bytes. The v3 MVS manifest requires
Y-zoom in this profile; audio BIOS is optional. The digest is computed once
after successful MVS load and remains cached across reset and restore.

SHA-256 follows the algorithm in [RFC 6234](https://www.rfc-editor.org/rfc/rfc6234.html),
published May 2011, sections 4.1, 5.1, 6.1, and 6.2. This small C17
implementation was written from the algorithm specification; no RFC sample
code was copied and no new dependency was introduced. Empty, `abc`, the
56-byte padding-boundary vector, and a 640-byte exact-block-multiple vector
are checked against the RFC 6234 Section 8.5 SHA-256 test driver vectors.
These vectors establish implementation correctness for those tested cases,
not authenticity of a captured envelope.

## Executed Debug/Release continuation matrix

This matrix records the one full-SDK build pair actually exercised on 2026-10-26
UTC. Each direction ran same-build controls first, then exchanged state between
distinct Debug and Release executables. Fresh importers independently loaded the
public diagnostic and authored MVS fixtures; every row compared complete future
observations, including guest effects, emulated cycles, all raw pixels and exact
PCM. A source hash is recorded as provenance and freshness evidence. It is not an
import compatibility gate; the native import gates remain the versioned schema,
profile, configuration and normalized media identities above.

| Exporter to importer | Result | Diagnostic future | MVS future |
| --- | --- | --- | --- |
| Debug to Release | Pass, 22 assertions per profile | 12 observations, 132 cycles, trace SHA-256 `0a01ef3a09e0f520dd9b61b40db0da38d82438f084750aee19867bf0740449ee` | 4 observations, 811,010 cycles, 4 raw frames (1,146,880 bytes; 48 nonzero bytes), 3,244 delivered PCM frames (6,488 samples; 4,186 nonzero), trace SHA-256 `d159a5d2a3c3bbb8b9b78ac2249ee6daaa9ea80d6591f97fa7f71c1bfe09a194` |
| Release to Debug | Pass, 22 assertions per profile | 12 observations, 132 cycles, trace SHA-256 `0a01ef3a09e0f520dd9b61b40db0da38d82438f084750aee19867bf0740449ee` | 4 observations, 811,010 cycles, 4 raw frames (1,146,880 bytes; 48 nonzero bytes), 3,244 delivered PCM frames (6,488 samples; 4,186 nonzero), trace SHA-256 `d159a5d2a3c3bbb8b9b78ac2249ee6daaa9ea80d6591f97fa7f71c1bfe09a194` |

Both directions used source revision `1aee4c0369f1efb8f7e244eadb8522124c063909`, source-content SHA-256 `b3a375ddbbfeec24d099b2f6fa3ea6fa01d7e03d5eb81955f5c2e2b8f29d4325`, and future-input schedule SHA-256 `5ac7ae6c3d2ca4dcd09e834667ce6a829b663c36be0b04a21b6416d1d64bca1a`. Normalized media SHA-256 values were `a3c05bd4f292a31540bfaf704035256ba56cca71980185a6590979d905331654` for diagnostic and `fcd7dc20de2b48820bcf5b4db086902837655863362a5c444eb2f7941bca0463` for MVS. Their profile/configuration IDs are diagnostic `1/1` and MVS `1297307725/2`. MVS state payloads were 224,113 bytes; diagnostic payloads were 4,336 bytes.

| Build identity | Debug | Release |
| --- | --- | --- |
| Platform | Darwin 25.6.0, arm64 | Darwin 25.6.0, arm64 |
| Generator / CMake | Ninja / 4.4.3 | Ninja / 4.4.3 |
| C and C++ compiler | AppleClang 21.0.0.21000101 | AppleClang 21.0.0.21000101 |
| Compile-command set | 67 commands, SHA-256 `dc144d0b40c2828d78bf5097c89335d5cadcdc75f2f78794824be76aff996a49` | 67 commands, SHA-256 `4ceda37a3d5cb93ac3504618a18048371421f167514c4c4e344daf726ecf4d0f` |
| Normalized SDK options | SHA-256 `d4912b17bce92af6e5e2d56215fdf3224e157438e50716b191b27c0ef0645e1d` | SHA-256 `b695c3a7ade783c28b5dce076592f063baf0d43303c2a0e2a27c08658fbfd166` |

Dependency provenance for this run: floooh/chips Z80 revision
`9e88298ce56319953ac7a43213a1120359f7a3a6`, source SHA-256
`6ca70ffd91b1bdbaf00f7a41e7092b326145fd1c95dcdd7bb01183370de734f3`; ymfm
revision `81aec25ccbb98f4873a255f7551ac4dadac59b4a`, with the local source
closure SHA-256 `617bd146950c0c7684d7a7ee522a0bc3301784928b7975d99cd22e1bd0d59dac`
and notice SHA-256 `9cade9b33dc8465552b41eb9fdd39b61d08c91b977e7c140e8cc2a533e86c929`.

This is evidence for this macOS arm64 compiler/configuration pair and these
source, dependency, media and input identities. It does not qualify other
operating systems, architectures, compilers, SDK distributions or shipped
packages.

## Native state exchange support matrix

This matrix is owned by the native `GNST` exchange tests. Its semantic
identities are independent of the package version: format, replay behavior,
profile, configuration, and normalized loaded-media identity must match the
reader's supported contract. Source revision and content hashes identify the
tested builds and provenance; they are not import gates. The outcome values
are exactly `pass`, `fail`, `unsupported`, `skipped`, and `unknown`. A failed
or skipped run is never counted as a pass; unknown means no matching exchange
was observed.

| Source/build identity | Profile/media/semantic identities | Actual build pair | Outcome | Scope |
|---|---|---|---|---|
| Source revision `1aee4c0369f1efb8f7e244eadb8522124c063909`; source-content SHA-256 `b3a375ddbbfeec24d099b2f6fa3ea6fa01d7e03d5eb81955f5c2e2b8f29d4325`; input schedule SHA-256 `5ac7ae6c3d2ca4dcd09e834667ce6a829b663c36be0b04a21b6416d1d64bca1a` | Diagnostic profile/configuration `1/1`, format/replay `1/1`, media `a3c05bd4f292a31540bfaf704035256ba56cca71980185a6590979d905331654`; MVS MSX profile/configuration `1297307725/2`, format/replay `1/1`, media `fcd7dc20de2b48820bcf5b4db086902837655863362a5c444eb2f7941bca0463` | Darwin 25.6.0 arm64; AppleClang 21.0.0.21000101; Ninja/CMake 4.4.3; Debug ↔ Release, both directions | `pass` | Both diagnostic and MVS futures matched; 22 assertions per profile per direction; exact trace identities and payload sizes are in the executed matrix above |
| Any other OS, architecture, compiler, SDK, or Debug/Release pair | No matching build/media/input identities are recorded | Not executed by this matrix | `unknown` | The executed pair does not qualify another build |
| A profile outside diagnostic and MVS MSX | No implemented state codec identity | No state exchange attempted | `unsupported` | Reader rejects the requested profile |

Here `fail` means a run was attempted and failed, `skipped` means it did not
execute, and `unknown` means there is no matching observation. The current
matrix contains no failed or skipped row to relabel. See the [SDK testing
matrix](testing.md#package-consumption-support-matrix) for package/artifact
consumption; it is a separate owner and result.

## Independent distribution and exchange identities

| Identity | Current value or source | Governs | Does not govern |
|---|---|---|---|
| Package version | `find_package` version from the release manifest; v0.2.1 is a separate diagnostic-only release | Selecting a package/artifact for the build | GNST import compatibility |
| Public ABI ID | `1` in `gn_state_compatibility_info_v1` | Reported API compatibility metadata | The native state byte layout or a C struct image |
| GNST format ID | `1` | Envelope structure reader acceptance | Package version or replay semantics |
| Replay behavior ID | `1` | The reader's implemented deterministic replay behavior | Package version or durable-save compatibility |
| Profile/configuration IDs | Diagnostic `1/1`; MVS MSX `1297307725/2` | Supported guest/profile and configuration contract | Package version or source SHA |
| Normalized media identity | Cached SHA-256 of the effective loaded media, role order, extents, profile, and configuration | Matching the saved guest's immutable input | Source/build identity or distribution rights |
| `durable_save_id` | `0` for diagnostic; `1` (`GN_MVS_SAVE_ID_V1`) for MVS MSX | The separate GNSV durable-save contract | GNST format or package release |
| Source revision/content SHA-256 | Exact matrix provenance above | Identifying the observed source/build inputs | A condition for importing a state |

These identifiers have separate owners and can be versioned independently.
There is no package-version or source-SHA import condition, automatic state
migration, permanent cross-build exchange guarantee, or promise that an
envelope from an untested build will be accepted. A reader applies only the
format, replay, profile, configuration, and normalized media checks its
implemented schema defines.

## Local selected-scene continuation (2026-10-26)

The local-only qualifier completed the already selected MVS scene using the
existing local media/configuration contract. It exported at a nontrivial
audio/timer/filter phase and a raw-frame boundary, stopped the exporter, then
started a separate importer that independently loaded the same scene. Four
future raw frames, exact PCM output, guest-visible results and emulated time
matched the uninterrupted witness. The run also passed malformed-import
atomicity and historical backup-RAM/address-retention checks (31 assertions).
The public MVS envelope remained 224,113 bytes. The public self-test separately
passed through the same subprocess and comparison path using only the authored
fixture (30 assertions).

The selected-scene configuration, media, payloads, raw traces and report remain
in ignored local storage; CI does not read them. Only the local report binds the
run to its source, input and configuration identities. No private media or
identity hashes are copied here.

### Resource and work measurements

The prior public-fixture restore instrumentation at Phase 04 Plan 04-06 source
revision `cdbdc79c9f66` observed 0 outer-parser and 0 CPU-state heap allocation
sites; the 2 Z80 staging sites reached 208 requested bytes at high-water, and
the 38 YM construction points reached 6,632 requested bytes at high-water. One
restore used 91,000 ns of host process CPU time. These are requested-byte and
single-observation measurements: they exclude allocator metadata and
stack-resident staging, do not bound total staging peak or worst-case import
work, and do not change emulated guest time. They remain historical observations.
The following source-derived bounds supersede that evidence gap; the serialized
payload is not used as a staging-memory cap.

#### Per-import derived bounds

`gn_test_state_resources_read` exposes the budget privately in test builds.
The codec and component `sizeof` expressions determine it anew for each build;
no caller field chooses an allocation extent or iteration limit. The measured
Debug AppleClang 21.0.0.21000101 build has these limits:

| Resource / unit | Diagnostic | MVS MSX |
| --- | ---: | ---: |
| Exact admitted input bytes | 4,336 | 224,113 |
| Stack guest staging and span visitor object bytes, conservative sum | 4,576 | 6,353 |
| Requested heap object bytes, including replacement chips | 0 | 6,840 |
| Aggregate staging object bytes, conservative sum | 4,576 | 13,193 |
| Admitted schema/bulk-byte work charges | 9,152 | 253,099 |
| Nonrepeatable fixed work stages | 4 | 9 |
| Public entry-guard invocations before charged stages | 1 | 1 |
| C / C++ allocation attempts | 0 / 0 | 2 / 38 |

Storage derivation: diagnostic reserves two `owned_cpu_state` objects (the
decoder and CPU apply's private validated copy) plus 4,096 RAM bytes. MVS
reserves those same two CPU objects, `gn_state_mvs_board` including protocol
arrays, `gn_state_mvs_sound` including sound RAM/filter arrays, Z80 decoder
`z80_t`/pin/cycle copies, and YM wrapper clock/latch copies plus its span visitor.
The sum is conservative: the extra CPU apply copy and Z80 decoder copy need
not coexist. The heap bound is the Z80 staged-state plus replacement candidate
and the YM candidate plus six FM channels, 24 FM operators, six ADPCM-A
channels and one ADPCM-B channel. Fixed configuration creates all of these
regardless of guest register values. Measured requested peaks equal the
derived 208 Z80 and 6,632 YM bytes; both chip graphs coexist before commit.
The complete chip heap graph fits within the aggregate sum alongside all
listed stack staging. No board-memory heap copy is made: its validated input
span is copied directly into retained work/save/palette/video storage.

These are **staging object storage** bounds. They include structure padding
within each `sizeof` object. They exclude the caller's transfer buffer,
already-loaded machine/media, allocator bookkeeping/size classes, exception
runtime storage, compiler spill slots/frame alignment/call metadata, and
total process RSS. Small parser scalars, pointers and constructor/cache-map
temporaries are fixed host bookkeeping, not extra guest snapshots. Their
compiler stack footprint and allocator/RSS costs remain unmeasured; these
numbers must not be advertised as a process-memory or native-stack cap.

Work is a deterministic envelope, not a host deadline or instruction count.
One byte-work charge reserves an admitted schema byte visit or bulk-object
initialization/copy byte. Each stage reserves its full conservative charge
before entry, even when validation fails early. Charges therefore bound work
without claiming the early-reject path read all reserved bytes. Fixed scalar
validation/reconstruction is bounded separately by nonrepeatable stages:

| Stage | Maximum charged byte work | Fixed work inside the stage |
| --- | --- | --- |
| Envelope | header + 8 bytes per required section | owner/range/identity checks; 2 diagnostic or 5 MVS section headers |
| CPU decode | 152 | two 8-register loops; scalar semantic validation |
| Board (MVS) | twice board wire bytes + twice board object bytes | decode/zero/apply and protocol revalidation; 64 events, 32 polled rows, 8 SR and 5 PC buckets; polled count validated before its loop |
| Sound (MVS) | fixed sound wire bytes + twice sound object bytes | sound RAM/bank copy and two fixed filter-tap loops |
| Z80 stage (MVS) | 76 + three times Z80 heap bound + Z80 stack guest bytes | fixed decoder, semantic checks, calloc/field copies |
| YM stage (MVS) | YM wire bytes + twice YM heap bound | one fixed constructor graph and one checked traversal |
| Rebind (MVS) | Z80 heap bound | one replacement Z80 constructor, one callback rebind, state apply/discard |
| CPU apply | three times CPU object bytes | named copy, revalidation, register apply; no callbacks |
| Memory commit | MVS memory bytes, or twice diagnostic RAM bytes | fixed RAM copies; MVS 34,816 big-endian video-word iterations |

The fixed YM stage includes a 1,024-entry waveform-construction loop, six FM
channel and 24 operator constructors, six ADPCM-A and one ADPCM-B constructors,
and a six-by-four operator assignment. Traversal visits fixed register arrays,
six FM channels, 24 operators, three SSG tone channels, six ADPCM-A channels
and one ADPCM-B channel. Timer wrapper loops have two entries. Cache invalidation
and prescaler/resampler selection are fixed work; imported time/sample counts
never drive a tick/generate loop. Generic saved-state array/64-bit byte loops
use compile-time array extents / eight bytes. Once the reader fails, later
fixed visitor calls cannot read more input. Its actual consumed-byte count is
recorded and checked against the trusted YM wire length. Import creates no
vector; vector growth belongs to capture. Destruction/unwind visits at most
the same fixed chip graph and never guest-selected counts. Alias checks visit
only the loaded bounded region table, not region contents. The public entry
guard runs once, including at most two owner scans (detail and input): each
has at most eight region iterations plus ten fixed owner-range checks, for
at most 36 range comparisons. This fixed prefix precedes byte charges; an
early invalid-call/length rejection can therefore report zero charged stages
while still doing bounded entry-guard work. Identity checks
compare cached 32-byte digests; restore never hashes media.

Length gates precede staging, section extents must equal trusted component
lengths, and the stage graph has no back edge, recursion or guest execution.
Thus each byte charge and fixed stage occurs at most once per import. All
fallible allocation/reconstruction/rebinding completes before CPU apply's
first live write; the remaining copies/swaps/destruction cannot reject.
Resource counters reset per call and are absent from canonical state and
consumer runtime. They impose no lifetime observation limit.

`sdk_state_tracer` checks diagnostic success and rejection. The 32-recipe
`sdk_state_hostile` corpus measures C/C++ requested-byte peaks for early/late
malformed and nested semantic failures; `sdk_state_oom` compares actual peaks
and construction counts with the derived component bounds and sweeps every
C/C++ failure point. Both assert per-import work envelopes and retain their
future-continuation, independent-peer and owner-address witnesses. These
claims cover the current fixed diagnostic/MVS schemas, not new profiles,
changed chip constructors or broader platform support.

The automated public verification route passed 13 state CTests with 1,673
assertions in 37.85 seconds on the named local toolchain; the full Debug CTest
and sanitizer evidence is recorded in [testing.md](testing.md). Per-test
timeouts and resource limits remain enforced. The complete field and ownership
cross-check is in [state-inventory.md](state-inventory.md); this selected-scene
run adds no fields to the serialized schema.

## Validation and mutation boundary

Restore validates in this order: API/lifecycle and pointer contract; exact
trusted length and outer magic/version/header/format; replay/profile/
configuration/media identities; required section count/order/length and
reserved fields; nested CPU, board, sound, Z80, and YM fields plus the YM
relations below; bounded staging and destination callback rebinding; then the
no-fail guest apply and retained-memory copy. Input strings are never
interpreted, and no caller buffer is retained. Unsupported IDs, malformed
bytes, invalid nested state, and media mismatch are rejected before live
mutation.

Before live mutation, `gn_state_mvs_ym_irq_relation_valid` requires
`sound.ym_irq` to equal the staged YM chip IRQ state. A mismatch reports
`CPU_STATE` in section `MVS_SOUND`, with the offset at the sound `ym_irq` byte;
hostile recipe `state.sound.ym-irq-mismatch` exercises this relation.
`check_wrapper_chip_relation` requires the YM wrapper's `timer_active` flag to
match the staged chip's `timer_running` flag in both directions. A mismatch
reports `CPU_STATE`, section `MVS_YM2610`, field `9` (`INVARIANT`), and the
offset of the offending wrapper flag; recipes
`state.ym.timer-running-without-active` and
`state.ym.timer-active-without-running` exercise the two directions.
The YM traversal requires an active timer deadline to be strictly after `now`.
For a future active deadline, `check_wrapper_chip_relation` also rejects values
more than 147456 clocks after `now` for timer A or 589824 clocks after `now`
for timer B. The staged YM detail is `INVARIANT` (field `9`) in
`MVS_YM2610`, with the offset at the offending deadline; recipe
`state.ym.timer-due-beyond-period` exercises the upper bound.
The YM busy deadline may be expired, but if it is in the future it must be no
more than 192 clocks after `now`. A failure reports the same YM section,
`INVARIANT` field, and the `busy_end` offset; recipe
`state.ym.busy-end-beyond-window` exercises this bound.

Not enforced: the chip-internal IRQ formula relating `m_irq_state` to status,
IRQ masks, and the status mask is not recomputed, and deadlines for inactive
timers are not checked against chip state.

The codecs remain limited to the implemented diagnostic and bounded MVS MSX
profiles. Plans 04-02 through 04-04 supplied canonical, validated device
sections; later phase work must close its independent compatibility,
portability and broader phase-goal evidence before making
additional claims. See
[state-inventory.md](state-inventory.md) for the field-by-field ownership,
validation, observer-reset, and downstream-chip obligations.
