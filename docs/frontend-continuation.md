# RetroArch frontend continuation and save policies

## Scope and tested route

This contract describes the current Libretro adapter and the local selected
MVS continuation route. The native state codec supports the diagnostic
`GN_PROFILE_DIAGNOSTIC` and MVS MSX profiles; the tested selected-scene
frontend continuation route is MVS MSX only. The GNFX v1 public tracer remains a diagnostic content fixture;
it is not the MVS continuation route and its startup screenshot does not prove
saved-state continuation.

The local acceptance path saves a state through the pinned RetroArch
frontend, advances the loaded MVS guest, restores through the frontend's
actual load path, and compares the restored native payload and future behavior
against a separate native witness. The route passed on source revision
`c045d4805a14983b5222e71d4ec6b560b7e4ee0e` with the pinned RetroArch
1.22.2 executable SHA-256
`ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65`, built
from upstream revision
[`69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576`](https://github.com/libretro/RetroArch/tree/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576).
That run was on the local macOS arm64 host. Its ignored local report retains
the exact core, observed-core, private content, scene-configuration, build,
and input identities. Private content and configuration hashes remain in
that report only; this document does not publish them.

The `private-state` CLI prints only a fixed receipt containing its route and
`pass`, `fail`, or `blocked_or_unknown` status. The owner-only local report
retains the full private result, including source bindings, media, scene,
state and capture identities and nested witness evidence. The receipt omits
those fields, failure diagnostic text and exception identities from stdout
and stderr. It is a reporting boundary, not additional continuation evidence.

## Four distinct byte formats

| Bytes | Owner and meaning | Boundary |
|---|---|---|
| `GNST` | Native continuation envelope for the loaded supported profile | `retro_serialize` emits the native payload; `retro_unserialize` accepts exactly the loaded MVS capacity. The capacity is fixed for that loaded image. The public MVS sound fixture measures 224,113 bytes; that value is not asserted for every possible image. |
| `RASTATE` | RetroArch state-file container | The tested file has the `RASTATE` version-1 header and one complete uncompressed `MEM` block containing the `GNST` bytes, followed by its end marker. The bounded local parser validates block order, sizes, padding, and trailing bytes. This outer container is not the native payload. |
| raw `SAVE_RAM` | The Libretro memory interface's 65,536-byte MVS backup-RAM view | RetroArch reads or writes these raw bytes through `RETRO_MEMORY_SAVE_RAM`. They have no `GNSV` header and are not a continuation envelope. |
| `GNSV` v1 | Native durable-save envelope for supported MVS backup RAM | This separate 65,632-byte envelope consists of its 96-byte header and 65,536-byte SRAM payload. It belongs to the native save API and its host receipt protocol, not to a RetroArch state file or raw SRAM file. |

MVS memory inside `GNST` is 217,088 bytes in the current public fixture. The
backup-RAM window begins at offset `0x10000` and is exactly 65,536 bytes.
Capture uses caller-owned storage sized for the loaded image's exact capacity;
success writes the exact envelope length. Restore requires that exact length,
validates and stages the payload before changing live state, and does not keep
the caller's buffer. A changed image may have a different capacity; run,
reset, capture, and restore do not change the capacity of an already loaded
image. See [native state](native-state.md) and [native save](native-save.md)
for the complete native API contracts.

## Safe capture, restore, and retained SRAM

The adapter's `retro_serialize_size` is nonzero only for a loaded MVS image.
The current route captures after a completed frame or normal `STOP` boundary.
Native capture and restore do not run the guest, poll input, call video or
audio callbacks, perform file I/O, write output, or read host time. The current
instance retains its media and fixed working allocations; the frontend owns
the serialized bytes.

`retro_get_memory_data(RETRO_MEMORY_SAVE_RAM)` returns a direct pointer to the
core's retained 65,536-byte backup-RAM allocation for the loaded MVS image.
An external frontend write through that pointer changes the core's live SRAM
immediately; it is not a staged copy. The pointer remains tied to that loaded
image through frames, reset, state capture, and state restore, and is no
longer valid after unload, successful image replacement, or instance
destruction. The retention tests cover the actual Libretro endpoint and the
native save tests cover their separate `GNSV` envelope.

## State load, undo, and SRAM policy

The two `block_sram_overwrite` settings intentionally produce different
results when an older state is loaded after the live SRAM has changed:

| Setting | Loaded machine state | Claim supported by the measured route |
|---|---|---|
| `block_sram_overwrite=false` | `GNST` restores the historical SRAM bytes with the historical machine state. | Historical continuation when the actual restored payload and future witness match. |
| `block_sram_overwrite=true` | RetroArch preserves the current SRAM while it restores other machine state, producing a hybrid of historical machine state and current SRAM. | Preserve-current SRAM only; this is not an exact historical whole-machine restore. |

The preserve-current result depends on RetroArch allocating its SRAM backup
copy. At the pinned upstream revision, failure to allocate the block array
leaves the copy count at zero and does not abort state loading; therefore this
frontend option has an upstream out-of-memory limit and is not an unconditional
core guarantee. The behavior is visible in the pinned
[`task_save.c`](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/task_save.c).

Quick Menu **Undo Load State** restores the frontend's in-memory snapshot from
before the last load. In this pinned RGUI route, Undo Load State dispatches
`CMD_EVENT_RESUME` and closes the menu automatically; automation waits for
neutral guest callbacks and does not toggle the menu again. **Undo Save State**
restores the prior state-file bytes from RetroArch's one-use save backup. It is
a file operation, not a live machine restore, and the selected continuation
route does not use it. These behaviors are source-pinned to the same
[RetroArch revision](https://github.com/libretro/RetroArch/tree/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576).

Startup SRAM import, clean-exit writeback, and nonzero periodic autosave are
separate operations. The measured periodic route uses
`autosave_interval=1` without state operations. State-load and undo routes use
`autosave_interval=0`, so a threaded periodic writer is not interleaved with
restore. The combined threaded-autosave and state-operation case is
unsupported by the tested operation matrix. A normal frontend exit or an
autosave interval does not establish crash atomicity, power-loss durability,
or a native `GNSV` acknowledgement.

## Frontend operation support matrix

This matrix is owned by the pinned RetroArch/core operation checks. The
frontend executable identity, upstream source revision, Glueyneo source
revision, host/configuration, and allowed operation set travel together.
Outcomes are exactly `pass`, `fail`, `unsupported`, `skipped`, and `unknown`;
a failed or skipped route is not counted as pass, and unknown means no matching
operation set was observed. The public callback/registration suite is separately
listed in the [SDK testing guide](testing.md#frontend-continuation-and-recurring-public-coverage).

| Frontend/core source identity | Host / configuration | Allowed operation set | Outcome | Claim or limit |
|---|---|---|---|---|
| Glueyneo source `c045d4805a14983b5222e71d4ec6b560b7e4ee0e`; RetroArch 1.22.2 executable SHA-256 `ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65`; upstream source `69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576` | macOS arm64; `block_sram_overwrite=false`; `autosave_interval=0`; selected MVS MSX scene | State save, guest advance, state load, future callback comparison, and Undo Load State | `pass` | Exact historical continuation for the measured route; private core/content identities remain in the ignored local report |
| Same pinned frontend/core identity | macOS arm64; `block_sram_overwrite=true`; `autosave_interval=0` | State load after live SRAM changes | `pass` | Preserve-current SRAM only; not exact historical whole-machine continuation |
| Same pinned frontend/core identity | macOS arm64; `autosave_interval=1`; no state load or undo | Periodic save and restart | `pass` | Separate periodic route; no concurrent state operation |
| Same pinned frontend/core identity | `autosave_interval=1` with state load or undo | Threaded periodic autosave concurrent with state operations | `unsupported` | Not part of the measured operation set |
| Other RetroArch binaries, core source revisions, hosts, or operation combinations | No matching pinned identities/configuration | Not executed by this matrix | `unknown` | The one local selected-scene result is not general frontend support |

Here `fail` denotes a run that failed, `skipped` a route that did not execute,
and `unknown` the absence of matching evidence; none of those outcomes can be
promoted to pass. The selected-scene binary and private inputs are not copied
into the public matrix. Package consumption, native `GNST`, and native `GNSV`
have separate identity owners in [testing](testing.md), [native state](native-state.md),
and [native save](native-save.md).

Phase 05's original 105/106 regression and the affected targeted manifest
repair 2/2 remain separate historical results; neither is relabelled as a
Phase 06 frontend result.

## What output comparison establishes

The actual route compares emitted core callbacks: raw video callback pixels,
delivered core PCM, emulated cycles, and sampled MVS input transitions against
the independent native witness after restore. These values describe output
produced by this core and sampled input. They do not identify what the display
compositor showed, what an audio device queue played, or a frontend replay
position. A screenshot, menu message, or documentation check is not evidence
of guest continuation, durable-save behavior, or physical hardware truth.

## Local command and evidence limits

The public recurring callback and registration suite is
[`python3 tools/verify_sdk.py --suite frontend`](testing.md#frontend-continuation-and-recurring-public-coverage).
It uses public fixtures only. The separate actual selected-scene command is
local-only and uses existing authorized environment inputs:

```sh
# Enable the local observation target (production defaults keep it off), then
# build it and the independent native witness before running the route:
cmake --preset owned-debug \
  -DGLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS=ON
cmake --build --preset owned-debug \
  --target glueyneo_libretro_observed sdk_state_process

python3 tests/libretro/retroarch_smoke.py \
  --retroarch "$GLUEYNEO_RETROARCH_APP" \
  --core build/owned-debug/glueyneo_libretro.dylib \
  --observed-core build/owned-debug/glueyneo_libretro_observed.dylib \
  --content "$GLUEYNEO_PRIVATE_MVS_BUNDLE" \
  --private-contract "$GLUEYNEO_PRIVATE_SCENE_CONTRACT" \
  --witness build/owned-debug/sdk_state_process \
  --continuation-route private-state \
  --report "$GLUEYNEO_FRONTEND_WORK/private-state.json" \
  --timeout 120
```

This invocation ran with the selected local content and passed its actual
frontend-save, load, restored-payload, and native-witness comparisons. It is a
local macOS arm64 observation for the exact identities retained in the ignored
report, not a general platform, renderer, device, or game-save claim. The
route has one per-invocation timeout capped at 120 seconds, no background
watcher, and no lifetime observation counter. Missing host access or local
inputs produces a narrow blocked/unknown result; it cannot be replaced by a
public fixture or treated as a pass. The route requires no human UAT; its GUI
actions are automated and screenshots are not acceptance evidence.
