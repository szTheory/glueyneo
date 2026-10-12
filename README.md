# Glueyneo

Glueyneo is a portable C Neo Geo MVS/AES core project. Its current v0.1 alpha
delivers an offline-installable C17 library, a headless runner, and one bounded,
firmware-free CPU/bus diagnostic. It is not a playable emulator, and the local
package checks do not qualify a platform support matrix or release artifact.

## Build and consume the installed SDK

The package exports `Glueyneo::glueyneo` and version `0.1.0`. The commands
below build and install separate static and shared packages, then compile C
and C++ consumers against the installed package. The C example reads the
installed original fixture in the host application and passes its bytes to the
ordinary API. It checks the guest results, resets and runs again, unloads, and
destroys the instance. The C++ program includes the same public header and
calls the C API.

<!-- docs:installed-commands:start -->
```sh
# Static package and out-of-tree C/C++ consumers
cmake -S . -B build/sdk-static \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF \
  -DGLUEYNEO_BUILD_TESTS=OFF \
  -DBUILD_TESTING=OFF \
  -DCMAKE_INSTALL_PREFIX="$PWD/build/install-static"
cmake --build build/sdk-static --parallel 2
cmake --install build/sdk-static
cmake -S tests/consumers -B build/consumer-static \
  -DGlueyneo_DIR="$PWD/build/install-static/lib/cmake/Glueyneo" \
  -DGLUEYNEO_CONSUMER_C_SOURCE="$PWD/examples/diagnostic.c"
cmake --build build/consumer-static --parallel 2
./build/consumer-static/glueyneo-installed-c \
  build/install-static/share/glueyneo/diagnostic-original-a.bin
./build/consumer-static/glueyneo-installed-cxx
./build/consumer-static/glueyneo-installed-c \
  build/install-static/share/glueyneo/diagnostic-original-a.bin --recovery

# Shared package and out-of-tree C/C++ consumers
cmake -S . -B build/sdk-shared \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=ON \
  -DGLUEYNEO_BUILD_TESTS=OFF \
  -DBUILD_TESTING=OFF \
  -DCMAKE_INSTALL_PREFIX="$PWD/build/install-shared"
cmake --build build/sdk-shared --parallel 2
cmake --install build/sdk-shared
cmake -S tests/consumers -B build/consumer-shared \
  -DGlueyneo_DIR="$PWD/build/install-shared/lib/cmake/Glueyneo" \
  -DGLUEYNEO_CONSUMER_C_SOURCE="$PWD/examples/diagnostic.c"
cmake --build build/consumer-shared --parallel 2
./build/consumer-shared/glueyneo-installed-c \
  build/install-shared/share/glueyneo/diagnostic-original-a.bin
./build/consumer-shared/glueyneo-installed-cxx
./build/consumer-shared/glueyneo-installed-c \
  build/install-shared/share/glueyneo/diagnostic-original-a.bin --recovery
```
<!-- docs:installed-commands:end -->

The consumer project calls `find_package(Glueyneo 0.1.0 EXACT CONFIG REQUIRED)`.
For lifecycle, ownership, status strings, and allocation-failure recovery, see
[Ownership, lifecycle, and errors](docs/ownership-and-errors.md). The malformed
manifest recovery is the final `--recovery` command above: it expects
`GN_STATUS_INVALID_MEDIA` (`invalid diagnostic media`) for a malformed
replacement, then confirms the previously loaded guest still returns the
expected results. The executable prints an `SDK_RECOVERY` result record when
that rejection and recovery pass.

## Local verification

Run the current-revision SDK gate from the repository root:

```sh
python3 tools/verify_sdk.py
```

It checks counted focused CTest lanes, static/shared installed C and C++
consumers, compiled documentation examples, capabilities, provenance, evidence,
the retained local baseline, and supported sanitizer lanes. It writes the
canonical public-safe result to `evidence/sdk/verification.json`. This local
gate does not qualify hosted CI, release authority, other platforms, or the
CMake 3.20 minimum-version claim. Coverage-guided libFuzzer is unsupported on
the current AppleClang toolchain; deterministic seeded mutation is used. The
ThreadSanitizer lane runs its process-heavy CTest cases one at a time to avoid
host resource contention.

## What this alpha implements

The public `GN_PROFILE_DIAGNOSTIC` accepts exactly two mapped regions:

| Region | Guest base | Mapped size | Input bytes | Access |
| --- | ---: | ---: | ---: | --- |
| ROM | `0x0000` | 512 bytes | 512 | Read-only |
| RAM | `0x1000` | 4096 bytes | 10-byte initialization prefix | Writable |

The remaining RAM starts at zero. The reset vector requires supervisor stack
pointer `0x2000` and an even program counter in ROM with at least one
instruction word remaining. Successful loads copy
the media; each instance owns its image and CPU state. Calls on one instance
must not overlap or re-enter, while distinct instances may run concurrently.
The diagnostic fixture uses `MOVEQ`, `ADDQ.L`, absolute-long-address `MOVE.L`
stores, absolute-long-address `MOVE.W` loads, and `STOP`; its named results are arithmetic `10`, initialized data
`0x1237`, and BSS `1`.

The accepted private CPU candidate implements only selected encodings and
addressing forms, recorded in the [candidate subset](experiments/owned_cpu/SUBSET.md):

| Form | Candidate boundary |
| --- | --- |
| `MOVEQ #imm8,Dn` | D0–D7, signed 8-bit immediate |
| `ADDQ.L #1..8,Dn` | D0–D7 direct; encoded zero means 8 |
| `MOVE.L Dn,(abs.L)` | D0–D7 sources; high word then low word |
| `NOP` | Exact opcode `0x4e71` |
| `RESET` | Exact opcode `0x4e70`, supervisor only; records a signal event, no device callback |
| `RTE` | Exact opcode `0x4e73`, supervisor-only six-byte short frame |
| `TRAP #0` | Exact opcode `0x4e40`, vector 32 |
| `MOVE.W #imm16,SR` | Exact opcode `0x46fc`, supervisor only |
| `MOVE.W (abs.L),Dn` | D0–D7 destination |
| `STOP #imm16` | Exact opcode `0x4e72`, supervisor only |

Other valid but unsupported encodings return an unsupported-opcode outcome.
Exact `0x4AFC` is excluded from this candidate only; it does not enter vector 4.
That candidate exclusion does not select an original-MC68000 saved PC.

Logical word and long accesses use big-endian bytes and ordered 16-bit
functional bus transfers. Guest address arithmetic remains 32-bit while bus
callbacks receive the low 24 address bits. Odd word/long accesses and odd
instruction fetches take the selected address-error path. This is not a
physical pin or Neo Geo board-bus model. `gn_run` accepts at most 1,000,000
requested guest cycles and
processes whole reset, interrupt, instruction/exception, or stopped-idle
events. Instructions and exceptions are not split to meet a budget; a completed
event can overshoot it, and the result reports elapsed and overshoot cycles.
Stopped-idle progress consumes the exact remaining request without bus access.
`GN_RUN_STOPPED` reports CPU state; it is not a success verdict. The consumer
checks named guest observations to decide whether its diagnostic passed.

This alpha does not claim a full 68000 ISA, physical bus-pin timing, Neo Geo
board behavior, commercial game or BIOS compatibility, video, audio, public
snapshots, replay, durable saves, CPU plugins, cross-build state compatibility,
or gameplay performance. The public SDK has no filesystem, device, network, or
wall-clock service.

## Evidence and limits

The fresh [Phase 01 whole-phase verification](.planning/workstreams/cpu-bus-diagnostic-sdk-alpha/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md)
passed 10/10 must-haves at source revision
`09476ed57ee29c0798f8be8f082e05ad73776e3b` and admitted the bounded candidate
for Phase 02 integration. The frozen candidate receipt remains
`unqualified` with `phase_admitted: false`; it records a candidate-level
disposition and is not the separate phase-level admission. The original-silicon
saved-PC behavior remains unknown. Exact `0x4AFC` remains unsupported by this
candidate only.

The Phase 01 verifier retains documentation warning WR-01: older
`ACCEPTANCE.md` and `ORACLE.md` prose describes an immediate-extension read at
`0x106` on a user-mode `MOVE.W #imm16,SR` privilege path. The observed
functional sequence checks supervisor status after the opcode read at `0x104`,
then enters vector 8 without reading `0x106`; the frame writes and vector reads
are listed in the verifier. Historical documents are preserved, and this
correction is not a physical-pin trace. No original-hardware saved-PC result is
inferred.

The declared CMake floor is 3.20, but the package and consumers have only been
executed on Darwin arm64 with AppleClang 21.0.0.21000101 and CMake 4.4.3. The
floor and other platforms remain unqualified. Build, consumer, documentation,
and capability checks are local evidence, not hosted CI or release authority.
See the [CPU/bus SDK workstream state](.planning/workstreams/cpu-bus-diagnostic-sdk-alpha/STATE.md)
for that deliverable's contributor workflow, and its [requirements](.planning/workstreams/cpu-bus-diagnostic-sdk-alpha/REQUIREMENTS.md)
and [roadmap](.planning/workstreams/cpu-bus-diagnostic-sdk-alpha/ROADMAP.md)
for scope and next steps.

The original project is MIT licensed. Imported code retains its own notices;
see [Unity provenance](third_party/unity/PROVENANCE.md) and
[Musashi provenance](third_party/musashi/PROVENANCE.md). The diagnostic fixture
is original and firmware-free; its recipe and oracle ancestry are in
[the SDK oracle record](tests/sdk/ORACLE.md). No game image or BIOS is included.
