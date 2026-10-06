# Ownership, lifecycle, and errors

Glueyneo's current native API accepts one bounded firmware-free diagnostic
profile. A `gn_instance` owns its loaded image and CPU state. It does not open
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
