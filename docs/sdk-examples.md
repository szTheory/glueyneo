# Build and run the native SDK examples

This guide starts from an extracted Glueyneo source tree that contains this
file. The published [v0.2.1 diagnostic SDK](https://github.com/szTheory/glueyneo/releases/tag/v0.2.1)
does not contain these continuation and persistence examples. Use the current
source delivery that includes them; do not infer these capabilities from the
older diagnostic package.

The CMake consumer reads the exact package version from
`.release-please-manifest.json`. The commands below build and install both
static and shared libraries, then compile the examples against the installed
`Glueyneo::glueyneo` target. They use original public fixture recipes and
need no network, private media, private headers or manual linker flags. The
commands use a POSIX shell and must start at the extracted source root.

Each run creates new paths beneath `build/`. If one of those named paths
already exists, stop and choose a fresh name before running that block again.
The persistence example generates an original public MVS fixture with an
extent of approximately 64 MiB; its generation and load are bounded by the
fixture recipe. No peak-memory measurement is claimed.

## Static installed package

<!-- sdk-examples:static-commands:start -->
```sh
cmake -S . -B build/sdk-static \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF \
  -DGLUEYNEO_BUILD_TESTS=OFF \
  -DBUILD_TESTING=OFF \
  -DCMAKE_INSTALL_PREFIX="$PWD/build/install-static"
cmake --build build/sdk-static --config Release --parallel 2
cmake --install build/sdk-static --config Release
cmake -S tests/consumers -B build/examples-static \
  -DGlueyneo_DIR="$PWD/build/install-static/lib/cmake/Glueyneo" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DGLUEYNEO_CONSUMER_C_SOURCE="$PWD/examples/diagnostic.c"
cmake --build build/examples-static --config Release --parallel 2
mkdir build/sdk-static-first-run
./build/examples-static/glueyneo-installed-sound \
  --write-fixture build/sdk-static-first-run/public-sound-mvs.bin
./build/examples-static/glueyneo-installed-continuation --produce \
  build/sdk-static-first-run/public-sound-mvs.bin \
  build/sdk-static-first-run/position.gnst \
  build/sdk-static-first-run/expected.gnct
./build/examples-static/glueyneo-installed-continuation --consume \
  build/sdk-static-first-run/public-sound-mvs.bin \
  build/sdk-static-first-run/position.gnst \
  build/sdk-static-first-run/expected.gnct \
  build/sdk-static-first-run/observed.gnct
./build/examples-static/glueyneo-installed-persistence \
  --mode portable --role producer --value A \
  --slot build/sdk-static-first-run/portable.gnsave \
  --scope 00000000000000000000000000000001
./build/examples-static/glueyneo-installed-persistence \
  --mode portable --role reader \
  --slot build/sdk-static-first-run/portable.gnsave \
  --scope 00000000000000000000000000000002
mkdir build/sdk-static-host
./build/examples-static/glueyneo-installed-persistence \
  --mode host --role producer --value A \
  --slot build/sdk-static-host/slot.gnsave \
  --scratch-dir build/sdk-static-host \
  --scope 00000000000000000000000000000003
./build/examples-static/glueyneo-installed-persistence \
  --mode host --role reader --reopen \
  --slot build/sdk-static-host/slot.gnsave \
  --scratch-dir build/sdk-static-host \
  --scope 00000000000000000000000000000004
```
<!-- sdk-examples:static-commands:end -->

## Shared installed package

<!-- sdk-examples:shared-commands:start -->
```sh
cmake -S . -B build/sdk-shared \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=ON \
  -DGLUEYNEO_BUILD_TESTS=OFF \
  -DBUILD_TESTING=OFF \
  -DCMAKE_INSTALL_PREFIX="$PWD/build/install-shared"
cmake --build build/sdk-shared --config Release --parallel 2
cmake --install build/sdk-shared --config Release
cmake -S tests/consumers -B build/examples-shared \
  -DGlueyneo_DIR="$PWD/build/install-shared/lib/cmake/Glueyneo" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DGLUEYNEO_CONSUMER_C_SOURCE="$PWD/examples/diagnostic.c"
cmake --build build/examples-shared --config Release --parallel 2
mkdir build/sdk-shared-first-run
./build/examples-shared/glueyneo-installed-sound \
  --write-fixture build/sdk-shared-first-run/public-sound-mvs.bin
./build/examples-shared/glueyneo-installed-continuation --produce \
  build/sdk-shared-first-run/public-sound-mvs.bin \
  build/sdk-shared-first-run/position.gnst \
  build/sdk-shared-first-run/expected.gnct
./build/examples-shared/glueyneo-installed-continuation --consume \
  build/sdk-shared-first-run/public-sound-mvs.bin \
  build/sdk-shared-first-run/position.gnst \
  build/sdk-shared-first-run/expected.gnct \
  build/sdk-shared-first-run/observed.gnct
./build/examples-shared/glueyneo-installed-persistence \
  --mode portable --role producer --value A \
  --slot build/sdk-shared-first-run/portable.gnsave \
  --scope 00000000000000000000000000000005
./build/examples-shared/glueyneo-installed-persistence \
  --mode portable --role reader \
  --slot build/sdk-shared-first-run/portable.gnsave \
  --scope 00000000000000000000000000000006
mkdir build/sdk-shared-host
./build/examples-shared/glueyneo-installed-persistence \
  --mode host --role producer --value A \
  --slot build/sdk-shared-host/slot.gnsave \
  --scratch-dir build/sdk-shared-host \
  --scope 00000000000000000000000000000007
./build/examples-shared/glueyneo-installed-persistence \
  --mode host --role reader --reopen \
  --slot build/sdk-shared-host/slot.gnsave \
  --scratch-dir build/sdk-shared-host \
  --scope 00000000000000000000000000000008
```
<!-- sdk-examples:shared-commands:end -->

Each continuation pair is a fresh-process route: `--produce` writes a GNST
snapshot and expected future trace, while `--consume` loads matching immutable
media into a separate process, restores the snapshot, applies the same future
inputs and compares guest effects, deterministic time, video and PCM. The
result records begin with `SDK_CONTINUATION`. A truncated or foreign-media
state is rejected before the destination changes; the example then checks
that the destination still continues correctly.

The portable persistence pair exercises save query/export/import and guest
consumption. Its `SDK_PERSISTENCE` record reports
`host_file_commit=not_claimed`; it is not evidence of a durable host-file
commit. The separate host route publishes through the example-owned single
writer and ACKs only after the checked commit completes. It reports a measured
commit only on the supported Darwin/APFS route; other hosts return an explicit
`unsupported` result for that file protocol while retaining the portable API
route.

The host route refuses an existing slot. To inspect a previously written slot,
use the explicit `--reopen` reader operation shown above. Never rerun a
producer against a slot that may contain the only committed save. The owning
host keeps one writer for each authoritative slot and resolves all outstanding
work before changing the slot or destroying the instance. A failed or uncertain
result stays unresolved until the host retries the retained bytes through the
full commit protocol or explicitly discards them. `--discard` accepts the
loss; it does not perform a hidden flush.

On a supported host, a producer aimed at an existing slot returns exit status 2
and `SDK_PERSISTENCE` with `outcome=invalid` and `reason=slot_already_exists`;
the existing bytes remain untouched. A host reader of a missing path reports
`slot_missing`; a non-save file reports `slot_invalid`; a readable file with an
invalid GNSV envelope reports `slot_format_invalid`. Those are distinct
failures, not a new zero baseline. An unsupported host returns an explicit
`outcome=unsupported` and does not claim a file commit. The executable guide
test checks these outcomes where the host protocol is supported.

## Choose the operation and its contract

Use [native state](native-state.md) for snapshot boundaries and state-exchange
identities, [native save](native-save.md) for guest SRAM, slot ownership and
host commit outcomes, and [frontend continuation](frontend-continuation.md)
for the separately tested RetroArch operations. These contracts keep package
consumption, native state exchange, host persistence and frontend policy
evidence separate. A passing package or portable API run does not qualify a
different host's state exchange or file durability.

For support rows, exact source/build identities and sanitizer package
limitations, see [testing and support](testing.md). A successful return is
only the example's reported result; it does not add game, BIOS, board,
cross-platform state, threaded frontend, hardware-fidelity or performance
support.
