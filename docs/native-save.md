# Native MVS backup RAM

## Scope

The v1 durable-save surface transfers only the modeled 65,536-byte MVS MSX
backup RAM allocation. It is independent of `gn_state_*_v1`: continuation
snapshots can rewind historical SRAM bytes and therefore branch persistence
lineage, while a durable save represents bytes the host has authoritatively
committed. The core owns no file, slot, device, network, secret, or clock
access. The host owns all input/output buffers and chooses the authoritative
slot and trusted directory.

Only the normalized MVS MSX profile is supported. The diagnostic profile
reports `supported=0` and `save_id=0`; unsupported profiles are rejected and
receive no save identity. MVS reports save identity 1.
This semantic save identity is separate from state format, replay, profile,
configuration, and public ABI identities. The normalized media digest
associates bytes with the loaded image; it is not authentication or proof of
rights.

The tested RetroArch state-file, raw `SAVE_RAM` pointer, and SRAM policy
boundaries are collected in [frontend-continuation.md](frontend-continuation.md).
The frontend raw SRAM file and its historical/hybrid restore policies do not
change the separate native `GNSV` v1 envelope or host receipt protocol.

## Public records and operations

Every record is sized, fixed-width, caller-owned, and initialized by the API
before it reports a supported result. API details use their own numeric reason
enum; `gn_status` retains its existing values. These are the declarations and
field lists checked against `glueyneo.h` by the direct documentation test.

| Kind | Name | Fields or declaration | Bytes / contract |
|---|---|---|---|
| record | `gn_mvs_save_scope_v1` | `size, reserved, scope[16]` | 24; nonzero host-issued scope, never reused across instance lifetimes |
| record | `gn_mvs_save_receipt_v1` | `size, reserved, scope[16], load_generation, restore_branch, mutation_sequence, export_sequence` | 56; exact tuple for one successful export |
| record | `gn_mvs_save_info_v1` | `size, supported, save_id, profile_id, media_identity_sha256[32], envelope_bytes, dirty, baseline_known, scope_valid, exhausted, startup_import_allowed, reserved[3]` | 60; current support and ownership state |
| record | `gn_mvs_save_detail_v1` | `size, reason, field, offset` | 16; numeric diagnostics only |
| record | `gn_mvs_save_lifecycle_result_v1` | `size, discarded_pending` | 8; reports core SRAM discarded by a successful checked transition; never claims host durability |
| api | `gn_mvs_save_query_v1` | `gn_status gn_mvs_save_query_v1(const gn_instance *instance, gn_mvs_save_info_v1 *out_info, size_t info_size, gn_mvs_save_detail_v1 *detail, size_t detail_size);` | Queries save support and lineage without running the guest or doing I/O |
| api | `gn_mvs_save_export_v1` | `gn_status gn_mvs_save_export_v1(gn_instance *instance, void *buffer, size_t capacity, size_t *out_written, gn_mvs_save_receipt_v1 *out_receipt, size_t receipt_size, gn_mvs_save_detail_v1 *detail, size_t detail_size);` | Writes one canonical envelope and issues the latest receipt only after success; export does not clear dirty state |
| api | `gn_mvs_save_import_baseline_v1` | `gn_status gn_mvs_save_import_baseline_v1(gn_instance *instance, const void *bytes, size_t length, gn_mvs_save_detail_v1 *detail, size_t detail_size);` | Validates the full envelope, then copies its payload as the authoritative startup baseline |
| api | `gn_mvs_save_ack_v1` | `gn_status gn_mvs_save_ack_v1(gn_instance *instance, const gn_mvs_save_receipt_v1 *receipt, size_t receipt_size, gn_mvs_save_detail_v1 *detail, size_t detail_size);` | Consumes the exact latest unconsumed receipt after the host commit completes |
| api | `gn_mvs_save_scope_renew_v1` | `gn_status gn_mvs_save_scope_renew_v1(gn_instance *instance, const gn_mvs_save_scope_v1 *scope, size_t scope_size, gn_mvs_save_detail_v1 *detail, size_t detail_size);` | Binds a caller-issued nonzero scope; the host promises lifetime nonreuse |
| api | `gn_mvs_save_reason_string` | `const char *gn_mvs_save_reason_string(gn_mvs_save_reason reason);` | Static fixed text; unknown values return fixed generic text |
| api | `gn_load_mvs_v3_checked_v1` | `gn_status gn_load_mvs_v3_checked_v1(gn_instance *instance, const gn_mvs_manifest_v3 *manifest, gn_mvs_save_lifecycle_policy_v1 policy, uint32_t host_work_resolved, gn_mvs_save_lifecycle_result_v1 *out_result, size_t result_size, gn_mvs_save_detail_v1 *detail, size_t detail_size);` | Stages and validates a replacement image before applying the selected pending-save policy |
| api | `gn_unload_checked_v1` | `gn_status gn_unload_checked_v1(gn_instance *instance, gn_mvs_save_lifecycle_policy_v1 policy, uint32_t host_work_resolved, gn_mvs_save_lifecycle_result_v1 *out_result, size_t result_size, gn_mvs_save_detail_v1 *detail, size_t detail_size);` | Unloads only after the selected pending-save policy succeeds |
| api | `gn_destroy_checked_v1` | `gn_status gn_destroy_checked_v1(gn_instance **inout_instance, gn_mvs_save_lifecycle_policy_v1 policy, uint32_t host_work_resolved, gn_mvs_save_lifecycle_result_v1 *out_result, size_t result_size, gn_mvs_save_detail_v1 *detail, size_t detail_size);` | Destroys and clears the caller handle only after the selected policy succeeds |
| legacy | `gn_load` | `gn_status gn_load(gn_instance *instance, const gn_manifest *manifest);` | Successful image replacement discards the previous save lineage |
| legacy | `gn_load_mvs` | `gn_status gn_load_mvs(gn_instance *instance, const gn_mvs_manifest *manifest);` | Successful image replacement discards the previous save lineage |
| legacy | `gn_load_mvs_v3` | `gn_status gn_load_mvs_v3(gn_instance *instance, const gn_mvs_manifest_v3 *manifest);` | Successful image replacement discards the previous save lineage |
| legacy | `gn_unload` | `gn_status gn_unload(gn_instance *instance);` | Unload ends the current image and save lineage |
| legacy | `gn_destroy` | `void gn_destroy(gn_instance *instance);` | Destruction ends the instance and save lineage |
| compatibility | `durable_save_id` | `gn_state_compatibility_info_v1.durable_save_id` | 1 for supported MVS MSX; 0 for diagnostic; unsupported profiles are rejected |

All buffers must cover their advertised sizes for the complete call and must
not overlap each other or known live instance storage. The core retains no
caller pointer. Output records and counts are initialized deterministically;
rejected export does not change payload or receipt bytes. The owner permits one
caller at a time per instance. Renew the scope before relying on a new host
lifetime, including after address reuse.

Checked load rejects result/detail overlap with the manifest or any source
region before writing outputs, and accepts only v3 manifests.

The checked lifecycle policy is `GN_MVS_SAVE_LIFECYCLE_REQUIRE_RESOLVED` or
`GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD`. The checked calls take
`host_work_resolved` as an explicit host attestation; the core cannot inspect
the filesystem or know whether a prior rename/sync outcome is uncertain.
Both policies require `host_work_resolved=1`; unresolved host work is refused
with `GN_MVS_SAVE_REASON_HOST_WORK_PENDING`. `REQUIRE_RESOLVED` also refuses
core-dirty SRAM. `ALLOW_DISCARD` permits discarding pending core SRAM, and
reports that loss only after a replacement has been fully prepared and committed. On any rejected or
out-of-memory replacement, the previous image, continuation, SRAM backing,
and receipt eligibility remain intact. Checked unload and destroy have no
fallible staging after policy acceptance; checked destroy sets
`*inout_instance` to null only on success. Legacy `gn_load*`, `gn_unload`, and
`gn_destroy` remain available with their original signatures; their callers
must resolve host work or deliberately accept data loss before using them.

### Numeric save reasons

| Reason | Value |
|---|---:|
| `NONE` | 0 |
| `INVALID_ARGUMENT` | 1 |
| `INVALID_STATE` | 2 |
| `UNSUPPORTED_PROFILE` | 3 |
| `CAPACITY` | 4 |
| `FORMAT` | 5 |
| `VERSION` | 6 |
| `RESERVED` | 7 |
| `DURABLE_ID` | 8 |
| `PROFILE` | 9 |
| `MEDIA_IDENTITY` | 10 |
| `INTEGRITY` | 11 |
| `SCOPE` | 12 |
| `STALE_RECEIPT` | 13 |
| `RECEIPT_CONSUMED` | 14 |
| `STARTUP_CLOSED` | 15 |
| `HOST_WORK_PENDING` | 16 |
| `COUNTER_EXHAUSTED` | 17 |
| `SCOPE_REUSED` | 18 |

## GNSV v1 envelope

All integers are unsigned fixed-width big-endian. The 96-byte header and
65,536-byte SRAM payload are caller-owned transfer bytes; the envelope contains
no host path, scope, receipt, snapshot, work RAM, BIOS, ROM, or public C
structure representation.

| Offset | Length | Field | Value |
|---:|---:|---|---|
| 0 | 4 | Magic | ASCII `GNSV` |
| 4 | 4 | Envelope version | `GN_MVS_SAVE_FORMAT_V1_VERSION` (1) |
| 8 | 4 | Header length | `GN_MVS_SAVE_HEADER_V1_BYTES` (96) |
| 12 | 4 | Total length | `GN_MVS_SAVE_ENVELOPE_V1_BYTES` (65,632) |
| 16 | 4 | SRAM payload length | `GN_MVS_SAVE_PAYLOAD_V1_BYTES` (65,536) |
| 20 | 4 | Durable save identity | `GN_MVS_SAVE_ID_V1` (1) |
| 24 | 4 | Profile | `GN_MVS_PROFILE_MSX` |
| 28 | 4 | Reserved | Zero |
| 32 | 32 | Normalized media identity | SHA-256 identity cached for the loaded MVS image |
| 64 | 32 | Envelope digest | SHA-256 of domain bytes, header bytes `[0,64)`, and payload bytes `[96,65632)` |
| domain | 20 | Digest domain | ASCII `Glueyneo MVS save v1`; no terminating NUL |
| 96 | 65,536 | MVS backup RAM | Exact canonical byte-addressed SRAM contents |

The digest domain is the exact ASCII byte string `Glueyneo MVS save v1`, with
no terminating NUL. The decoder validates length, magic, version, IDs, profile,
reserved bytes, media identity, and digest before it copies SRAM. A valid digest
binds bytes against accidental corruption; it is not a MAC or authenticity
claim.

## Ownership and lifecycle

`dirty` means guest or restore work needs a later host commit. `baseline_known`
means this core instance has an affirmative baseline from a validated import or
an acknowledged current receipt. A core-clean state does not prove that a host
slot is published or resolved; host unresolved work is maintained by the host
and blocks further commits, scope changes, and lifecycle transitions.

| Event | Core state effect | Required host/core rule |
|---|---|---|
| Successful MVS load | Resets per-load branch, mutation, export, dirty, baseline, and receipt state; opens startup import; advances `load_generation` when a scope is already bound | Bind or renew a never-reused scope before persistence work |
| Effective changed unlocked byte or word store | Sets dirty and advances `mutation_sequence`; exhaustion latches conservatively without blocking the guest store | Locked and same-value stores do not advance the sequence |
| MVS reset or watchdog reset | Preserves SRAM bytes and save lineage | Reset does not reopen startup import after it closes |
| Valid startup baseline import | Copies SRAM only after full envelope validation; sets baseline known, clears dirty, and branches lineage | May repeat before first guest execution while no guest, export, receipt, or unresolved host work is pending |
| First guest execution | Permanently closes startup import for that loaded image | Later clean state or reset cannot reopen the gate |
| Successful full continuation restore | Restores historical SRAM, sets dirty, advances `restore_branch`, and invalidates the prior receipt | Snapshot restore is not a disk commit and may replace newer SRAM history |
| Successful export | Advances `export_sequence`, returns an exact receipt, and leaves dirty set | Keep immutable exported bytes until host commit outcome is resolved |
| Successful ACK | Consumes only the exact latest current receipt; clears dirty and establishes baseline | Call only after complete host publication and namespace synchronization |
| Rejected import, restore, or ACK | Does not copy SRAM or clean pending state | Stale, foreign, reordered, and duplicate receipts cannot clear dirty state |
| Successful load replacement, unload, or destroy | Ends the old image's save ownership lifetime | Legacy signatures remain unchanged; resolve host work before replacement or unload |
| Checked lifecycle transition | Both policies refuse host attestation=false; `REQUIRE_RESOLVED` also refuses dirty core state; `ALLOW_DISCARD` reports pending core SRAM loss only after success | Host supplies its unresolved-work attestation; a failed replacement leaves the existing image and receipt usable |

The ownership record is per `gn_instance`, outside guest snapshots and durable
files. The image-to-owner pointer is non-owned and bound only when a candidate
image is committed. `state-inventory.md` lists the exact owner fields and
snapshot exclusions. A successful restore triggers the core's restore-branch
hook only after state validation and commit; rejected restores leave lineage
unchanged.

## Startup authoritative-slot outcomes

The reference reader distinguishes a new slot from an existing save that
cannot be read safely. A readable byte envelope still passes the core's full
format, integrity, profile, and media validation before any SRAM import.

| Outcome | File condition | Startup behavior |
|---|---|---|
| `missing` | Opening the selected slot returns `ENOENT` | Keep zero-filled SRAM, leave the baseline unknown, and run the guest without import |
| `readable` | A regular slot has the exact-size envelope and a complete read/close | Validate the envelope; malformed or incompatible bytes, including a bad digest or media identity, fail visibly before import |
| `invalid` | An existing slot is unreadable, nonregular (including a FIFO), wrong-size, truncated, or has a trailing byte | Open the selected path nonblocking and reject nonregular files before reading; fail visibly and never treat invalid data as a fresh zero baseline |
| `not_applicable` | A writer starts a new slot without reading a prior save | Start from zero-filled SRAM and write a new transaction |

The reference reader assumes the selected save directory is trusted. It opens
the slot with `O_NONBLOCK`, then checks the descriptor with `fstat` and rejects
nonregular files before reading. This makes a FIFO with no writer fail as
`invalid` instead of blocking startup; it does not establish safe traversal of
an attacker-controlled directory hierarchy.

## Synchronous host commit order

The process witness is a reference Darwin host path with one writer and a
trusted directory. It reads only the authoritative save file at startup, with
an exact 65,632-byte bound; temporary files are ignored. Before rename, failure
is not committed. A known pre-rename failure keeps the pending receipt and dirty
SRAM blocked until retry succeeds or an explicit discard. After rename, any
directory-sync, close, or ACK failure has an uncertain outcome and must retain
the host's immutable pending transfer and block further transitions. The core
never weakens a missing host sync primitive into a successful commit.

The same-process host transaction retains the slot, immutable exported bytes,
receipt, and owning instance while the outcome is uncertain. Its bounded
resolution loop permits only an explicit retry or discard: retry republishes
the same bytes through a new exclusive temporary file, complete write,
`F_FULLFSYNC`, checked file close, rename, directory sync, and checked directory
close, then ACKs the retained receipt. A readable file alone never completes
the retry. Discard never ACKs. Guest, slot, scope, and lifecycle transitions
remain blocked until one of those choices resolves the transaction. Failed
retry attempts reset their stage suffix; stage recording is best-effort and
cannot gate filesystem operations. A single resolution call is limited to 32
actions, and a single publication is limited to 32 write and temporary-name
attempts. A later explicit resolution call may try again. These values live in
process memory.

Process-interruption recovery is exercised by a pipe-gated live writer and a
distinct fresh reader. The parent terminates the writer after exclusive temp
creation, partial and full writes, `F_FULLFSYNC`, checked temp close, rename,
directory sync, checked directory close, protocol completion before ACK, and
ACK. First-create and A-to-B replacement are checked at every stage. Before
rename, the authoritative path remains absent or retains A; at and after rename,
the tested APFS run exposes the complete B envelope. Fresh startup reads only
the authoritative path and ignores every orphan temp, including a complete B
envelope staged before rename.

While a real writer is paused before rename, all six transition barriers reject
state restore, save-scope renewal, slot change, transaction replacement,
unload, and destroy. After the writer completes, the witness restores the
captured state, publishes branch B, and reads B in a new process. Its obsolete-publication
control bypasses the barrier and lands A after B; the disk assertion fails at
`save.disk-latest-branch` even though the stale ACK remains rejected.

The post-rename unresolved state has a separate failure gate, paused with
`active=0` and `publication_in_flight=0`. All six transitions
are probed again in that state, and destroy must return without clearing the
owner handle. The retry control captures the entire immutable envelope
(65,632 bytes) before failure, compares every byte and its SHA-256 digest after
republication, checks the envelope digest, and imports the result in a distinct
fresh reader.

The distinct `commit_failed` state covers known pre-rename failures. Restore,
scope renewal, slot change, transaction replacement, unload, and destroy stay
blocked while the original receipt and immutable bytes remain pending. The
caller can retry the same transaction; only a successful checked lifecycle
call with explicit `ALLOW_DISCARD` may clear it without a commit. Tests verify
that a successful retry ACKs the retained receipt and that an explicit discard
reports the pending bytes it drops.

The stage supervisor allows at most one child, waits at most 15 seconds for a
stage event or child completion, captures at most 1 MiB from each output stream,
and reaps every child. These process results qualify only the observed local
Darwin filesystem and syscall stages. They do not prove power-loss survival,
device failure behavior, hostile directory safety, or multi-writer conflict
handling.

The process target compiles a small unsupported stub on non-Darwin platforms,
and CTest marks that host-protocol case skipped. This keeps POSIX file and
process calls out of MSVC builds; it is not evidence that an MSVC build was
executed or that the Darwin commit protocol is supported elsewhere.

| Order | Stage | Requirement | ACK allowed |
|---:|---|---|---|
| 1 | `temp-created` | Exclusive same-directory temporary file | No |
| 2 | `write` | Write the complete bounded envelope, retrying short writes and `EINTR` | No |
| 3 | `file-fullfsync` | `F_FULLFSYNC` succeeds | No |
| 4 | `file-close` | Temporary file descriptor closes successfully | No |
| 5 | `rename` | Atomically replace the authoritative slot | No; later failures are outcome-uncertain |
| 6 | `directory-open` | Open the containing directory | No |
| 7 | `directory-fsync` | Synchronize the directory namespace | No |
| 8 | `directory-close` | Directory descriptor closes successfully | No |
| 9 | `ack` | Consume the receipt corresponding to these committed bytes | Yes, only after every prior stage succeeds |

## Uncertain outcome resolution

| Action | Behavior | Allowed transition |
|---|---|---|
| `retry` | Retain the original slot, bytes, receipt, and owner; republish those bytes through exclusive create, complete write, `F_FULLFSYNC`, checked file close, rename, directory sync and checked directory close; ACK that receipt last; never ACK from readback; reset failed-attempt trace suffixes | Unblocks only after the full publication protocol and exact receipt ACK succeed; otherwise remains blocked |
| `discard` | Retain transaction state until the host explicitly chooses discard; do not ACK or claim the save committed | Allows deliberate shutdown after the host accepts unresolved data loss |

## Malformed authoritative target regressions

Fresh-reader processes test each existing malformed authoritative target. Wrong
sizes are rejected by the host reader; exact-size bad-digest and incompatible
media envelopes reach the core import validator. Every case exits visibly
before guest output and is never treated as a missing slot or zero baseline.

| Case | Host read | Core import | Guest work |
|---|---|---|---|
| `truncated` | Invalid: wrong-size envelope | Not attempted | No |
| `trailing-byte` | Invalid: oversized envelope | Not attempted | No |
| `bad-digest` | Readable exact-size file | Reject digest | No |
| `media-incompatible` | Readable exact-size file | Reject media identity | No |

The direct process witness verifies the table against its emitted host-stage
trace, writer exit, fresh reader, shared media identity, and exact guest output.
Its Python supervisor drains stdout and stderr concurrently into fixed byte
buffers, terminates and reaps a child when either output cap is exceeded, and
also retains only bounded prefixes when a child times out.
It does not prove generic filesystem guarantees, universal power-loss survival,
multi-writer conflict handling, or hardware behavior. See
[`tests/fixture/ORACLE.md`](../tests/fixture/ORACLE.md#native-mvs-save-diagnostic-guest)
for the original guest and its emulator-only assertion ancestry.

## Measurements and pending evidence

| Claim | Status | Value |
|---|---|---|
| `fixture_bytes` | measured | 67,108,976 |
| `fixture_sha256` | measured | `9cefb11420e190f5902e8861f5becda1c63c7ccd988118d7d93dc814a1b36690` |
| `shared_media_identity_a_b` | measured | true |
| `host_stage_trace` | measured | `temp-created,write,file-fullfsync,file-close,rename,directory-open,directory-fsync,directory-close,ack` |
| `process_interruption_stage_cases` | measured | 20 (10 publication stages × first-create and A-to-B replacement) |
| `writer_reader_process_pairs` | measured | 2 |
| `child_timeout_bound_seconds` | bound | 15 |
| `child_output_bound_bytes` | bound | 1,048,576 |
| `tested_host_identity` | measured | macOS 26.6.2 / Darwin 25.6.0 / APFS |
| `save_source_identity_sha256` | measured | `d92b02ad77bea285179f9b8c0b151c9ebb95df3db76be483300c09e282f080c7` |
| `guest_fixture_source_sha256` | measured | `af74e58521d294c324c9510a2fba7432cbfcf57f2489f26c7d7045db5868734d` |
| `build_identity` | measured | AppleClang 21.0.0.21000101; Debug; SDK sanitizer NONE |
| `supported_sync_operations` | measured | F_FULLFSYNC, checked file close, atomic rename, directory fsync, and directory close |
| `host_fault_matrix_cases` | measured | 18 (9 syscall stages × first-create and A-to-B replacement) |
| `unsupported_host_protocol` | bound | Linux/Windows native save subset only; host commit protocol unsupported |
| `save_suite_critical_path_bound_seconds` | bound | 900 |
| `peak_restore_staging_bytes` | pending | Not measured by this save-process witness |
| `interrupted_commit_recovery` | pending | Process interruption is measured; physical power-loss recovery is not qualified |
| `physical_board_or_game_save_behavior` | pending | Physical power loss and commercial board/game save behavior not qualified |

The measured host row is macOS 26.6.2 on Darwin 25.6.0 using APFS. The save
source identity binds the public API, instance owner, native host writer,
receipt/lifecycle cases, and guest fixture; the separate guest-source hash and
the immutable GNMV fixture size/hash bind the inputs. The build identity is
AppleClang 21.0.0.21000101, Debug, with the SDK sanitizer disabled. On this
host the observed writer order includes file `F_FULLFSYNC`, checked close,
atomic rename, directory `fsync` and close, then receipt ACK. The suite records
its current `critical_path_seconds` on every run and enforces the 900-second
bound; it does not treat one elapsed-time sample as a permanent performance
claim. Each child has a 15-second timeout and fixed 1,048,576-byte capture
limit per output stream. Requested restore-staging memory remains unmeasured.

The 18 syscall-fault cases cover first creation and A-to-B replacement; the
20 process-kill cases cover ten publication stages across those same histories.
They verify only local process interruption and fresh-process reopening on the
measured Darwin/APFS path. Other hosts run the native save checks and retain
this Darwin row as reference evidence, but their host commit protocol is
unsupported. Physical power loss and commercial board/game save behavior are
not qualified. Pending evidence stays unqualified; file identity is neither
filesystem support nor a rights/authenticity claim.

## Native persistence support matrix

This matrix is owned by the native GNSV and host-publication checks. It records
source/build, OS/filesystem, writer ownership, and the measured commit or
failure stages. Outcomes are exactly `pass`, `fail`, `unsupported`, `skipped`,
and `unknown`. A failed or skipped host campaign is not a pass; unknown means
there is no matching observation. Package consumption and native state
exchange are separate owners; see the [package matrix](testing.md#package-consumption-support-matrix)
and [GNST matrix](native-state.md#native-state-exchange-support-matrix).

| Source/build identity | OS / filesystem | Host and slot ownership | Commit / failure evidence | Outcome | Limit |
|---|---|---|---|---|---|
| Save source SHA-256 `d92b02ad77bea285179f9b8c0b151c9ebb95df3db76be483300c09e282f080c7`; fixture source SHA-256 `af74e58521d294c324c9510a2fba7432cbfcf57f2489f26c7d7045db5868734d`; fixture 67,108,976 bytes; AppleClang 21.0.0.21000101, Debug, sanitizer NONE | macOS 26.6.2 / Darwin 25.6.0 / APFS | One owning writer per authoritative slot; trusted directory | Nine checked commit stages; 18 syscall-fault cases; 20 process-interruption stage cases; explicit ACK after directory sync and close | `pass` | Local process interruption and fresh-reader evidence only; not physical power-loss qualification |
| Non-Darwin host commit protocol | Linux / Windows host implementation boundary | No supported native host writer in this sample; portable save API has separate evidence | Non-Darwin host commit operation returns unsupported; host tests are marked skipped where the Darwin-only process path cannot run | `unsupported` | Does not assert that each listed OS/compiler pair was built by this host row |
| Physical power-loss recovery and commercial board/game save behavior | No physical hardware/filesystem observation | No physical owner or storage path exercised | No matching measurement | `unknown` | Not qualified by emulator process termination |

The status vocabulary also permits `fail` for a recorded failing attempt and
`skipped` for a row not run. Neither is present as a passing measurement here.
There is one writer per authoritative slot. Successful ACK consumes the exact
receipt and clears the core dirty marker only after publication; it does not
roll guest SRAM backward or replace the current guest bytes. A full historical
SRAM rollback occurs only when the host explicitly restores an older `GNST`
continuation, which dirties the save lineage and requires a new commit.
`discard` is an explicit loss choice: it does not ACK, flush, or silently
publish. All six restore/scope/slot/replacement/unload/destroy transitions stay
blocked while a receipt is unresolved. Read [frontend policy](frontend-continuation.md)
for the separate preserve-current versus historical SRAM route.
