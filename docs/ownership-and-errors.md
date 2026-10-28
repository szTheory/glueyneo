# Ownership, lifecycle, and errors

Glueyneo's native API accepts the bounded firmware-free diagnostic profile and
the separately documented normalized MVS profiles. A `gn_instance` owns its
loaded media, CPU, chip and converter state. It does not open
files, read a clock, contact a device or service, or terminate the host process.

## Lifecycle

Create an instance, load a manifest, then reset, run, and observe it as needed.
The states and recovery operations are:

| State | Operation | Result |
| --- | --- | --- |
| Created or unloaded | `gn_reset`, `gn_run`, `gn_observe` | `GN_STATUS_INVALID_STATE` (`instance has no loaded media`) |
| Created or unloaded | `gn_unload` | `GN_STATUS_OK`; repeated unload is safe |
| Loaded, ready, stopped, or guest-faulted | `gn_reset` | `GN_STATUS_OK`; restores the initial RAM image and CPU reset state |
| Loaded | `gn_unload` | `GN_STATUS_OK`; releases the image and keeps the instance reusable |
| Any valid instance | `gn_destroy` | Releases its image and handle; no further use is valid |

`gn_destroy(NULL)` is a no-op. A null required handle or output argument returns
`GN_STATUS_INVALID_ARGUMENT`; a valid `gn_create` output pointer is set to null
before allocation is attempted. `gn_run` and `gn_observe` clear their valid
output records before returning an error. Reset, unload, and destroy may be
repeated according to the table. Destroying a handle twice, using a dangling or
fabricated pointer, or racing calls on one instance violates the caller
contract; C cannot safely diagnose those cases.

Each successful `gn_load` copies the ROM bytes and RAM initialization prefix.
Callers may release or overwrite source buffers as soon as `gn_load` returns.
RAM bytes outside that prefix start at zero. Reset restores the copied prefix,
zero-fills the remainder, and resets the CPU, so the same loaded diagnostic can
be run again. Unload releases the copy; the instance itself remains valid for
another load.

## MVS frame and PCM ownership

After a supported normalized MVS load, query `gn_mvs_audio_capacity_v1`, then
use the separate `gn_mvs_frame_request_v1`/`gn_mvs_frame_result_v1` layouts with
`gn_mvs_advance_frame_v1`. Both size arguments must equal their v1 structure
sizes; the earlier diagnostic frame layouts remain separate. The capacity is
812 stereo frames, with source-model/event ancestry in
[audio-contract.md](audio-contract.md#caller-ownership-discard-and-lifecycle).
The native library copies loaded media; request/result, pixel and aligned
signed-16 audio buffers remain caller-owned and may not overlap. `audio=NULL`
with capacity zero advances and discards output without queuing it.

Malformed preflight leaves guest state, result and caller buffers untouched.
An error after execution begins returns the actual elapsed clocks and valid
written PCM prefix; it cannot promise an untouched requested frame. Reset clears
chip/filter history while retaining loaded media, unload releases it, and failed
replacement preserves the prior machine. Internal watchdog reset preserves a
call's already-written prefix and active sink. Calls on one handle must not
overlap; independent-handle sound continuation is covered separately. See the
[installed C recipe](audio-contract.md#installed-c-sound-consumer) for the real
create/load/query/frame/reset/destroy sequence and buffer release.

## MVS durable save boundaries

The saved-byte transfer and receipt rules are specified in
[`native-save.md`](native-save.md). These lifecycle effects are part of the
instance ownership contract. `dirty` describes core-side pending guest work;
host publication uncertainty is a separate host-owned state.

| Operation | Backup-RAM effect | Ownership or error effect |
|---|---|---|
| Successful MVS load | Creates the new image's SRAM | Resets per-load lineage and opens startup import; a failed replacement preserves the previous image |
| MVS reset or watchdog reset | Preserves SRAM bytes | Does not clear dirty state; does not reopen a closed startup gate |
| First guest execution | No direct SRAM change | Closes startup baseline import for that load |
| Valid startup import | Copies the fully validated payload | Establishes baseline and can repeat before first guest execution; malformed, foreign-media, or late input leaves SRAM unchanged |
| Successful GNST continuation restore | Replaces SRAM with snapshot history | Marks save dirty, advances restore branch, and invalidates the previous receipt after validation and apply |
| Rejected GNST restore | Preserves SRAM | Leaves save lineage unchanged |
| GNSV export | Copies current SRAM to caller storage | Returns the latest receipt but does not clear dirty state |
| Receipt ACK | No SRAM copy | Clears dirty only for the exact latest current receipt after the host has completed publication |
| Successful load replacement, unload, or destroy | Ends the old image lifetime | Resolve host pending work before transition; legacy public signatures are unchanged |
| Checked lifecycle transition | `ALLOW_DISCARD` may discard pending core SRAM after successful staging | `REQUIRE_RESOLVED` requires host attestation and clean core state; failed replacement preserves the current image and receipt |

An export, snapshot restore, guest reset, or clean core status does not publish a
host slot. After atomic rename, any later directory sync, close, or ACK failure
leaves the host outcome uncertain; keep the immutable exported bytes and block
further lifecycle transitions until that outcome is resolved. The core itself
does no filesystem I/O. The reference Darwin order and its limits are in
[`native-save.md`](native-save.md#synchronous-host-commit-order).
The measured Darwin/APFS syscall and process-interruption rows in that
contract do not qualify other host filesystems or physical power-loss recovery.

The checked `gn_load_mvs_v3_checked_v1`, `gn_unload_checked_v1`, and
`gn_destroy_checked_v1` calls accept `GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED`
or `GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD`, plus a `host_work_resolved`
attestation. Both policies require resolved host work; discard applies only
to pending core SRAM. The core cannot verify that claim against host storage.
`discarded_pending` reports SRAM dropped by a successful checked transition;
it does not mean the prior host transaction became durable. Checked destroy
clears the caller's handle only when successful. Legacy load, unload, and
void destroy signatures retain their existing behavior and require the caller
to resolve or deliberately discard host work first.

## Validated diagnostic manifest

Version 1 accepts only profile `GN_PROFILE_DIAGNOSTIC` and exactly two
descriptors: one ROM and one RAM. ROM has guest base `0`, mapped size `512`,
and source size `512`. RAM has guest base `0x1000`, mapped size `4096`, and a
10-byte initialization prefix. The manifest has no caller-selected permission
field: this fixed profile exposes ROM as read-only and RAM as writable. Other
regions or profiles are rejected rather than clipped.

Before allocating or copying, loading checks that nonempty source prefixes have
non-null pointers, each prefix fits its mapping, every nonempty mapped span has
an in-range exclusive endpoint in the 32-bit guest address space, descriptors
have unique supported roles, and mapped spans do not overlap. The combined
`source_size + mapped_size` for all descriptors is capped at 1 MiB. The reset
vector is read explicitly as big-endian bytes: initial SSP must be `0x2000`,
and the initial PC must be even and leave at least one instruction word inside
the 512-byte ROM. Malformed descriptors and size arithmetic are rejected before
source bytes are read. The two reset-vector words are then read explicitly and
checked before any candidate storage is allocated.

Calls on one instance must not overlap or re-enter. Distinct instances own
separate mutable CPU and memory state and may be used concurrently. The public
API uses standard C allocation. Allocation failure is reported as
`GN_STATUS_OUT_OF_MEMORY`; failed initial loads leave an instance unloaded, and
failed replacements retain the previously loaded image.

## Status strings

| Status | `gn_status_string` | Meaning |
| --- | --- | --- |
| `GN_STATUS_OK` | `ok` | Operation completed |
| `GN_STATUS_INVALID_ARGUMENT` | `invalid argument` | Required argument is null or a bounded request is invalid |
| `GN_STATUS_INVALID_STATE` | `instance has no loaded media` | Operation requires a loaded image |
| `GN_STATUS_INVALID_MEDIA` | `invalid diagnostic media` | Manifest or mapped diagnostic data is malformed/unsupported |
| `GN_STATUS_UNSUPPORTED_PROFILE` | `unsupported diagnostic profile` | Profile is outside this alpha |
| `GN_STATUS_OUT_OF_MEMORY` | `out of memory` | Required instance or candidate allocation failed |
| `GN_STATUS_CPU_FAILURE` | `CPU backend failure` | The private CPU backend could not complete the operation |

These strings contain no host pointers or private paths. A guest CPU fault is
reported in `gn_run_result` with `GN_RUN_FAULT`; it does not invalidate the
handle. Reset it to replay the loaded diagnostic or unload it to release media.

## MVS import and load errors

The standalone `mvs_importer --selected game.zip bios.zip output.gnmv` returns
the failure class itself as its process exit code, prints one fixed generic
line on stderr, and leaves no output file: the normalized bundle is published
by atomic rename only after the whole import succeeds, so a rejected run never
leaves a partial `output.gnmv` or a sibling temporary, and a previously
published valid bundle is untouched. The messages never contain a path, member
name, size or digest from the input. The local wrapper
`tools/mvs/qualify_local_boot.py` records the class token below (never stderr)
as `import_error_class`. The canonical six-role mode keeps its original exit
codes 1 to 7 (`IMPORT_PROFILE` = 4 is returned only there).

| Exit | Class token | Cause | Action |
| ---: | --- | --- | --- |
| 1 | `malformed` | Truncated archive, bad end-of-central-directory, corrupt central directory or local header, inconsistent or overlapping extents, unsafe member name | Re-obtain the archive; do not repair it |
| 2 | `unsupported_feature` | ZIP64, multi-disk, encrypted or data-descriptor entry, unsupported compression method | Re-pack as a plain ZIP32 with stored or DEFLATE members |
| 3 | `limit_exceeded` | Source archive over 96 MiB, combined limits, over 64 entries, member over 8 MiB expanded | Supply the expected archive; the limits are not configurable |
| 5 | `decompress_failed` | DEFLATE stream, expanded size or member CRC validation failed | Re-obtain the archive |
| 6 | `memory` | Bounded allocation for the import failed | Free memory and retry |
| 7 | `ambiguous` | Duplicate member name or more than one valid end record | Re-pack with one entry per name |
| 8 | `missing_input` | A game or BIOS path does not exist or cannot be read | Check both paths |
| 9 | `unsupported_set` | Game archive has a member that is not in the supported set, a wrong size or identity, or the set is incomplete | Supply the supported game archive |
| 10 | `bios_missing` | BIOS archive has no `sp-s2.sp1` member | Supply the Europe MVS v2 BIOS archive |
| 11 | `bios_incompatible` | The selected main BIOS or optional audio BIOS member has the wrong size, CRC or SHA-1 | Supply bytes matching the pinned public source metadata |
| 12 | `output_failed` | The normalized bundle could not be published atomically | Check the output directory is writable |
| 13 | `zoom_incompatible` | Optional `000-lo.lo` board zoom data has the wrong size, CRC or SHA-1 | Supply bytes matching the pinned public source metadata |

Matching is by content and identity, never by file name alone. A BIOS archive
is checked before the game archive, so a missing or wrong BIOS is reported as
such even when the game archive is also unsupported. If one input has several
causes, the first failing check reports; fix it and run again. Exit 2 from the
command line with the wrong number of arguments is a usage error printed as
`usage: ...`, not an import class.

The local qualification wrapper removes the configured importer artifact before
building the `build/owned-debug/mvs_importer` and `mvs_qualify` targets, forcing the
configured executable to be linked again. It captures the rebuilt importer path
and SHA-256, confirms a no-work Ninja dry run, and requires both to remain
unchanged at each importer launch. An alternate wrapper, a multi-token command,
a missing artifact or changed importer bytes is refused with the fixed
`importer_identity_rejected` token and `qualifier_build: unchecked`. A refusal
before the first launch executes no importer or guest; if changed bytes are found
after an earlier negative-control launch, that completed diagnostic may have run,
but subsequent launches stop and no input identity is recorded. Synthetic path
and digest identities are test-only and always carry
`importer_identity_scope: synthetic`, so they cannot produce a production
qualification result. The `--check-fresh` command performs the same rebuild and
identity comparison before it can print `qualifier fresh`.

The Libretro adapter links no archive decoder and consumes only `GNMV`. When
the frontend offers `RETRO_ENVIRONMENT_GET_LOG_INTERFACE` it emits exactly one
line per `GNMV` load, always fixed text, and `retro_load_game` returns false on
every rejection with no instance retained, so the next valid load succeeds and
`retro_deinit` leaves nothing to release. Without a log interface the loads
behave the same and stay silent.

| Log line | Cause |
| --- | --- |
| `glueyneo: MVS bundle loaded` | The bundle was accepted by the compatible v1/v2 or v3 native loader |
| `glueyneo: MVS bundle rejected: malformed` | Truncated bundle, a region descriptor outside the content, or an unrepresentable length |
| `glueyneo: MVS bundle rejected: unsupported profile` | Bundle version, profile, region count or total size outside the selected profile |
| `glueyneo: MVS bundle rejected: missing audio BIOS` | Legacy v1 lacks the reset-selected audio source; rejection occurs before instance creation |
| `glueyneo: MVS bundle rejected: native load rejected` | `gn_load_mvs` returned a status other than success or out-of-memory, or the frontend refused XRGB8888 |
| `glueyneo: MVS bundle rejected: allocation failed` | `gn_create` failed or `gn_load_mvs` returned `GN_STATUS_OUT_OF_MEMORY` |

The native MVS v1 prefix remains loadable for compatibility; execution cannot
fetch missing audio BIOS bytes. The local qualifier reports
`missing_audio_region` without guest execution for such a bundle. Version 2
carries an explicit audio BIOS region. Version 3 adds the required Y-zoom
lookup role and keeps audio BIOS optional. Both use exact size, ownership and
transactional-load validation. A failed Libretro legacy load leaves the
adapter ready to accept a valid v2 or v3 bundle.

## Private MVS execution diagnostics

`native_execution_error` remains an error even if the guest protocol observer
also saw an attract/start predicate; an execution failure cannot be promoted
to success. The current qualifier may attach a `native_failure` object with the
exact shape `{component, stage, reason}`. `safe_result` accepts only known ASCII
tokens and valid combinations: `main_cpu` observe/IRQ-update/execute internal
failures or bus-access failures; `sound_cpu` bus-access failures or sound
catch-up failures (`internal_failure`, `cycle_limit`, `invalid_state`, or
`clock_overflow`); a board watchdog-reset internal failure; or an internal
timing-accounting mismatch. Extra keys, missing keys, wrong types, Unicode
confusables, and unknown combinations fail closed. Older generic error results
without `native_failure` remain unclassified rather than acquiring an inferred
cause.

The top-level `guest_executed` boolean describes completed main-CPU
instructions for this one native qualifier invocation. It stays false when an
instruction was only attempted, when elapsed time contains only idle or
interrupt clocks, or when only the sound CPU advanced. Counts accumulate over
all bounded main-CPU chunks and the first failure remains stable while later
catch-up or unwind work runs. Reset and successful reload clear both the first
failure and cumulative progress. Per-sound-candidate status resets with the
candidate; this host diagnostic state is private per instance and is not guest
snapshot or durable-save state.

The wrapper separately owns `qualification_invocation_state`: `not_started`
means no native qualifier launch occurred, `attempted` is set immediately
before launch and counts even a zero-instruction result, and `uncertain` records
a timeout or lost result after launch may have begun. Producer JSON cannot
assert this state. Importer rejection remains `not_started`; neither progress
nor a missing result grants a free selected invocation. The state is written
only to the ignored local qualification report.

The source-mapped sound candidate presents a pending command to the Z80 only
when guest I/O has enabled command NMI. The synthetic `mvs_board_sound`
control checks that a disabled interval leaves the pending latch, reply and
handler RAM untouched, then enables through guest I/O and proves the retained
command reaches the handler without a second write. Reset clears those sound
states. This verifies the modeled mapping and software path; it is not a
physical-device timing claim.

The `allocation failed` line has no automated fault-injection test in the
adapter suite (the allocator seam covers the native library, not the adapter);
the importer's `memory` class is exercised through a test-only build seam.
Unsupported, skipped or unknown outcomes are reported as such and are never
promoted to a pass.

## Reproducing lifecycle checks

Configure and run the named lifecycle suite from the repository root:

```sh
cmake --preset sdk-debug
cmake --build --preset sdk-debug
ctest --preset sdk-debug -L sdk-lifecycle --output-on-failure --no-tests=error
```

The suite exercises null arguments, cleared outputs, unloaded-state errors,
idempotent unload/reset, reload, and deterministic repeated results. It also
checks that the native runtime source and linked symbols do not introduce
filesystem, clock, device, network, process, or thread-service calls. Allocation
failure reproduction is exercised through a private test-only build seam and is
kept separate from the installed public API.

The media suite uses a private test build to compare a digest over the full ROM,
RAM seed and live RAM, plus all named CPU continuation fields. That digest and
the private hooks are test evidence only; neither is part of the installed API,
snapshot format, or persistence contract.

The private fault suite routes each test instance through its own allocation
counter and fails one selected allocation call. It sweeps create, initial load,
and replacement through the first position beyond all allocations, recording
attempt count, live allocation count, and requested live bytes. The private
allocator state must outlive its test instance. Failed initial loads remain
unloaded; failed replacements preserve the complete image digest and continued
guest results. The test target is compiled separately from the public runtime;
the installed header and library contain no fault-injection API.

Run the allocation-failure and recovery checks with:

```sh
ctest --preset sdk-debug -L sdk-faults --output-on-failure --no-tests=error
```
