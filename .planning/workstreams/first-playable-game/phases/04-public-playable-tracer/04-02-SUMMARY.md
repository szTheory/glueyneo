---
phase: 04-public-playable-tracer
plan: 02
subsystem: libretro
tags: [C17, Libretro, RetroArch, CMake, public-fixture]
requires:
  - phase: 04-public-playable-tracer
    plan: 01
    provides: generated GNFX v1 public fixture and bounded native frame API
provides:
  - target-scoped Libretro shared core with ordinary in-memory fixture loading
  - callback harness for native/frame equivalence and opted-out ABI behavior
  - pinned RetroArch smoke runner with explicit real-frontend result reporting
affects: [04-03-native-qualification, phase-07-consumer-qualification]
tech-stack:
  added: [canonical libretro.h at libretro-common 2b96a82bd8479bb3547d271e1eefadc82dd2161e]
  patterns: [single-instance frontend adapter, synchronous static frame storage, content bytes through gn_load]
key-files:
  created:
    - src/libretro/libretro_core.c
    - third_party/libretro/libretro.h
    - third_party/libretro/NOTICE.md
    - tests/libretro/callback_harness.c
    - tests/libretro/retroarch_smoke.py
  modified:
    - CMakeLists.txt
    - tests/consumers/check_package.py
key-decisions:
  - "The adapter uses only the ordinary in-memory content path, maps RetroPad RIGHT to the native frame input, and forwards native XRGB8888 pixels synchronously."
  - "Serialization, special loading, memory exposure, and cheats remain explicit safe opt-outs in this bounded fixture core."
  - "The actual RetroArch runner uses local keyboard and screenshot automation; its UDP command interface is not enabled."
actuals:
  tokens: 93411
  tasks: 2
  commits: 5
commits: 5
plan_head_before: 5016f0a4e15ef3fc83b3efe196e23f20a32f5fdb
plan_head_after: c86082da2816226b40ae8c5fa99c748a3be2b818
requirements-completed: [TRAC-01, TRAC-02, TRAC-03, API-05]
coverage:
  - id: P04-02-CALLBACK
    description: The Libretro bridge runs one native fixture frame and forwards input and pixels through the callback ABI.
    requirement: TRAC-02
    verification:
      - kind: integration
        ref: "libretro_callback; adapter output matched a separate native instance for no-input, RIGHT, and no-RIGHT traces"
        status: pass
    human_judgment: false
  - id: P04-02-ABI
    description: The exported opted-out symbols resolve and return the specified safe values; callbacks and native frames agree.
    verification:
      - kind: integration
        ref: "libretro_callback; bad version and native fixture body rejected, valid retry succeeded; all 25 exports inspected with nm -gU and opted-out exports resolved with dlsym"
        status: pass
    human_judgment: false
  - id: P04-02-HOST
    description: Actual pinned RetroArch load, input, software video, and unload behavior.
    requirement: HOST-02
    verification:
      - kind: frontend
        ref: "retroarch_smoke.py matched app version 1.22.2 and executable digest ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65; the process exited with status -6 before a screenshot"
        status: blocked_unknown
    human_judgment: false
duration: 11min
completed: 2026-10-07
status: complete
---

# Phase 04 Plan 02: Libretro Public Fixture Summary

**The generated GNFX fixture now has a thin Libretro consumer whose callback output is checked against the native API; the pinned RetroArch executable still aborts before frontend behavior can be observed.**

## Performance

- **Duration:** 11 minutes
- **Started:** 2026-10-07T21:07:14Z
- **Completed:** 2026-10-07T21:18:35Z
- **Tasks:** 2
- **Files modified:** 7 implementation, test, dependency, and package-check files

## Accomplishments

- Added a C17 shared core that rejects missing or malformed content, negotiates XRGB8888, builds the ordinary public-fixture manifest, and loads the supplied bytes through `gn_load`.
- The core polls once per `retro_run`, maps RetroPad RIGHT to native RIGHT, advances one bounded frame, and presents native pixels synchronously. It advertises fixed 320x224 geometry and nominal 60 fps while leaving pacing and devices with RetroArch.
- Exported the complete Phase 04 Libretro ABI surface. The callback harness checks every opted-out export, safe return values, pixel-format rejection, no-content/malformed rejection, callback counts, synchronous pixels, input controls, and frame equality against an independent native instance.
- Vendored the canonical `libretro.h` unchanged from libretro-common revision `2b96a82bd8479bb3547d271e1eefadc82dd2161e`; its SHA-256 is `c928d8f176b4e4bc45ee2a41ef236d25cc19e9bc2abc2e2e4c32cf08d6423801`.
- Added a macOS runner that checks the exact RetroArch, core, fixture, OS, and architecture identities before attempting actual frontend control and semantic screenshot checks.

## Validation

- `cmake --preset sdk-debug`, building `glueyneo_libretro` and `libretro_callback_test`, and `ctest --preset sdk-debug -R '^libretro_callback$' --output-on-failure --no-tests=error` passed.
- The shared core exported all 25 required symbols. The callback test resolved each opted-out export, rejected a truncated file, unsupported version, native fixture validation failure, and rejected pixel format, then proved valid loading still succeeded. It verified safe opted-out returns and native-versus-adapter frame equality.
- `python3 -m py_compile tests/libretro/retroarch_smoke.py` passed. The actual runner matched RetroArch `1.22.2` and its planned executable digest, then reported `blocked_or_unknown`: the app exited with status `-6` before producing a screenshot. Load, input, presentation, and unload therefore remain unobserved. A callback-harness pass is not HOST-02 evidence.
- The full `sdk-debug` suite initially ran 27 tests: 23 passed and four failed. Two failures came from the isolated package source copy omitting `third_party/libretro`; the copy list was fixed, and both static/shared package documentation checks passed on rerun. The remaining two failures are the pre-existing README path checks documented by Plan 01; their incorrect `.planning/phases/...` link still points outside the active workstream.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Included the vendored header in isolated package builds**
- **Found during:** Overall SDK CTest
- **Issue:** The documentation-package test copies the runtime source tree but omitted the new Libretro header directory, so static and shared isolated builds could not compile the adapter.
- **Fix:** Added `third_party/libretro` to the package-check source staging list.
- **Files modified:** `tests/consumers/check_package.py`
- **Verification:** `sdk_package_docs_static` and `sdk_package_docs_shared` both passed after the fix.
- **Commit:** `a16ba0c`

**2. [Rule 2 - Missing security mitigation] Kept RetroArch control local**
- **Found during:** Task 2 runner review
- **Issue:** The initially selected UDP command interface in pinned RetroArch 1.22.2 has no loopback bind option and can listen on all interfaces.
- **Fix:** Replaced UDP commands with local keyboard input and frontend screenshots; the runner does not enable the network command interface.
- **Files modified:** `tests/libretro/retroarch_smoke.py`
- **Commit:** `6d179b4`

**3. [Rule 2 - Missing critical boundary coverage] Verified malformed-load cleanup**
- **Found during:** Final acceptance review
- **Issue:** The harness rejected truncated content but did not directly cover same-size invalid envelope metadata or a native `gn_load` failure after instance creation.
- **Fix:** Added unsupported-version and invalid-fixture-body cases, then verified valid content loads after each rejected attempt.
- **Files modified:** `tests/libretro/callback_harness.c`
- **Verification:** `libretro_callback` passed with all malformed-load and cleanup assertions.
- **Commit:** `c86082d`

## Deferred Issues

- **HOST-02 remains blocked/unknown.** The local pinned executable matched version `1.22.2` and SHA-256 `ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65`, but it aborted with status `-6` before a screenshot. Diagnose this installation or obtain a working artifact with the same accepted identity, then rerun `python3 tests/libretro/retroarch_smoke.py --retroarch /Applications/RetroArch.app --core build/sdk-debug/glueyneo_libretro.dylib --content build/sdk-debug/public-playable.bin`. Do not mark HOST-02 complete until actual load, mapped input, software output, and clean unload are observed.
- The two remaining full-suite failures are the pre-existing root README links to `.planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md`; the artifact is stored in the diagnostic SDK workstream. Plan 01 already recorded this out-of-scope issue.

## Decisions Made

- The adapter owns Libretro callback translation only. The native API owns fixture parsing, guest input behavior, pixel generation, and frame timing.
- Libretro serialization, special loading, raw memory access, and cheat operations are explicitly unsupported for this fixture core.
- The frontend runner retains only public identity hashes and deletes screenshots/configuration/logs from its temporary directory when it exits.

## Self-Check: PASSED

- Adapter, vendored header and notice, callback harness, runner, and package-copy update exist.
- Task commits `996a696`, `3245de3`, `a16ba0c`, `6d179b4`, and `c86082d` are ancestors of the measured plan head `c86082d`.
- Five plan commits were measured from ledger base `5016f0a4e15ef3fc83b3efe196e23f20a32f5fdb` through `c86082da2816226b40ae8c5fa99c748a3be2b818`.
- HOST-02 remains pending; this plan does not claim actual RetroArch qualification.

---
*Phase: 04-public-playable-tracer*
*Completed: 2026-10-07*
