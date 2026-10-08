# First Playable public tracer build and load

This procedure builds the public GNFX v1 tracer from a complete committed Git snapshot, installs the native package and Libretro core into temporary prefixes under ignored `build/`, and checks both static and shared native consumers. It uses only the original 602-byte public fixture. It does not read or package a game ROM or BIOS.

## Run the qualification

On the selected macOS host with CMake, Ninja, Python 3, and the pinned RetroArch app installed, run:

```sh
python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean
```

The runner configures fresh static and shared CMake builds, builds `glueyneo-original-fixture` and `glueyneo-public-fixture`, installs each prefix, and compiles/runs an out-of-tree C17 consumer against each installed native package. It compares the installed diagnostic fixture to the generated copy, checks `public-playable.bin` against its recorded identity, runs the full CTest suite, runs the pinned Z80 and YM2610 source/admission checks, then starts the actual RetroArch smoke with the installed shared Libretro core and the generated public fixture. `--check-docs` also verifies this guide and the validation map:

```sh
python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean --check-docs
```

The runner resolves `HEAD` to one full commit ID, creates a complete committed Git archive under a fresh ignored run directory, and compares the executing runner with the archived runner before qualification begins. Every CMake configure/build/install, consumer, test, candidate gate, documentation check, and actual frontend invocation uses that snapshot as its source root. A complete tree comparison rejects omitted archive files (including `export-ignore` omissions), submodules, unsafe paths or symlinks, and ambiguous names. Any mutation of the materialized snapshot is checked before and after each source-consuming command and fails the receipt.

Therefore dirty and untracked checkout files do not enter the build; the archived commit is the sole source. If `tools/verify_playable.py` itself differs from the archived copy, the runner writes a failed receipt with `runner-source-mismatch`. Build, install, fixture, and admission outputs stay in the ignored run directory outside the archived source tree. CMake and Python injection variables are removed from subprocess environments, and CMake's user package registry is disabled.

The receipt is written to ignored `build/playable-qualification/receipt.json`; sanitized per-command logs and fresh build/install prefixes are retained in that run directory. `identity.source_snapshot` records the full commit, archive SHA-256, inventory schema and algorithm, aggregate inventory SHA-256, entry counts, and every archived regular file and symlink. Each entry has a repository-relative path, type, byte length, and SHA-256; regular-file entries preserve the executable bit, while symlink entries also contain the exact relative target. `artifacts` separately records generated fixture/core hashes, installed-tree inventories, and the YM2610 report/build identities. Toolchain, OS, SDK, and pinned frontend identities remain in the receipt. A zero exit means every required lane passed. A nonzero exit preserves lane outcomes and a named failure reason; mock Libretro harnesses never count as an actual frontend pass.

## Fixture and consumer paths

The build generates `public-playable.bin` through the `glueyneo-public-fixture` target. Its expected SHA-256 is `59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0` (602 bytes). The generator and assets are original Glueyneo work under MIT; the fixture has no external guest bytes, game ROM, BIOS, private media, or derived capture. The source, rights and oracle limits are recorded in `tests/fixture/rights-manifest.json` and `tests/fixture/ORACLE.md`.

Native `public_guest_*` CTests run the generated fixture through the guest's ordinary frame and input path, including no-input, wrong-direction and right-direction observations. The installed-package C consumer separately loads the installed original diagnostic fixture to prove package relocation and C linkage. The Libretro smoke loads the same generated GNFX fixture used by the native tracer, requests frontend screenshots, checks its guest marker, verifies mapped and wrong input, then quits RetroArch to check unload.

To run the frontend smoke directly after a build, pass the exact `.app` bundle, installed `glueyneo_libretro.dylib`, and generated fixture paths:

```sh
python3 tests/libretro/retroarch_smoke.py \
  --retroarch /Applications/RetroArch.app \
  --core <installed-prefix>/lib/libretro/glueyneo_libretro.dylib \
  --content <build-directory>/public-playable.bin
```

The smoke pins RetroArch 1.22.2 by executable digest. It expects software-visible output, no-input stability, a Left Arrow negative control, Right Arrow movement, and clean application exit after content unload. A frontend process exit before the first screenshot is `unknown` for HOST-02, not a pass. The runner records the failed stage, process status, bounded stdout/stderr and RetroArch log output, and a sanitized macOS crash reason when available. An `input` failure caused by macOS rejecting keyboard automation is reported as unavailable; it cannot satisfy the input controls.

For bounded diagnosis before the acceptance run, add `--diagnose` to the direct smoke command. It launches the pinned app once without content and once with the installed core and generated fixture. Each probe receives a fresh temporary RetroArch config and capture directory; the result is explicitly `diagnostic_only` and never counts as HOST-02 evidence:

```sh
python3 tests/libretro/retroarch_smoke.py \
  --retroarch /Applications/RetroArch.app \
  --core <installed-prefix>/lib/libretro/glueyneo_libretro.dylib \
  --content <build-directory>/public-playable.bin \
  --diagnose
```

## Current pinned frontend diagnosis

The 2026-10-07 probes used RetroArch 1.22.2 (`ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65`), the installed core (`9d26c9a63493dcaf4fc021dc003d89b9879df521dce60db0059a7556fa1d914e`), and the expected 602-byte fixture (`59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0`). Both the no-content startup and ordinary core/content launch exited with status `-6` before a screenshot. Fresh macOS crash reports identified `EXC_CRASH SIGABRT` and `SIGNAL 6 Abort trap: 6`; neither stdout/stderr nor RetroArch's own log contained startup output. Since no-content startup fails the same way, these observations do not implicate the core or fixture and do not justify changing the Libretro adapter.

A separate LaunchServices check (`open -n -W -a ...`) returned `kLSNoExecutableErr` even though the pinned bundle declares an executable that exists, is executable, and passes code-signature verification. The macOS unified log query was unavailable in this execution environment, so the underlying abort cause remains unknown. The required external precondition is a working interactive macOS launch context for this pinned app, with its startup failure diagnosable. HOST-02 remains unknown; neither launch probe is acceptance evidence.

## Previous qualification observation

The values below are from the 2026-10-07 run made before complete source snapshots were introduced. They remain useful as toolchain and artifact history, but that receipt is superseded for QUAL-03 because it did not bind every input to its source. Plan 04-08 regenerates the receipt using the snapshot procedure above.

## Historical toolchain and frontend observation

The clean run was performed 2026-10-07 at source revision `290e218fe4bed3f11f984fef0d4f2f768d23917d`: macOS 26.6.2, arm64, AppleClang C/C++ 21.0.0.21000101, macOS SDK 26.5, CMake 4.4.3, Ninja 1.13.2 and Python 3.14.4. CMake used Debug configuration, Ninja, C17 owned targets and C++14 only for the private YM2610 candidate. The selected RetroArch artifact was 1.22.2, bundle ID `com.libretro.dist.RetroArch`, executable SHA-256 `ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65`.

Both generated public fixtures had SHA-256 `59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0`. The installed shared Libretro core used for the frontend attempt had SHA-256 `9d26c9a63493dcaf4fc021dc003d89b9879df521dce60db0059a7556fa1d914e`; the static-configured build's Libretro artifact was `7a9edc9d7eca363526f500ae9aaa097838799e5cf0ab80f27fdfb0043517a1d5`.

The fresh full CTest run passed all 34 tests in 6.37 seconds. Static and shared installed C consumers passed. The Z80 source pin is `9e88298ce56319953ac7a43213a1120359f7a3a6`; its gate passed for the exact synthetic instruction, bus, IRQ, reset, continuation and instance workload in `tests/chips/Z80-ADMISSION.md`. This does not qualify a private game sound program or broad Z80 compatibility. The YMFM source pin is `81aec25ccbb98f4873a255f7551ac4dadac59b4a`; the YM2610 candidate's source, direct C consumer and installed static/shared C consumers passed. Its report SHA-256 was `a6faf3de0dc68dec67e80743413d4e53de6ade6620123db5ccb6d3fec2e02`. This remains candidate-only evidence, not YM2610 admission or production audio integration.

Only the listed macOS arm64 toolchain and app artifact were exercised. Other operating systems, architectures, compiler versions, SDK versions and RetroArch builds remain unsupported or untested. The diagnostic fixture and candidate tests establish their own bounded claims. They do not establish production BIOS behavior, commercial-game compatibility, scrolling or representative production audio; those remain in Phases 05–07.

If any required lane fails, retain its status and identity in the receipt, fix the cause or leave it unknown, and rerun the clean command. Do not change fixture hashes, test expectations, or unsupported status to make the aggregate command green.
