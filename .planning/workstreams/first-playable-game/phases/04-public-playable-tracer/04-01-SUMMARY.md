---
phase: 04-public-playable-tracer
plan: 01
subsystem: native-api
tags: [C17, CMake, CTest, guest-fixture, frame-api, 68000]
requires:
  - phase: 01-cpu-acceptance-experiment
    provides: bounded owned MC68000 execution subset
provides:
  - strict GNFX v1 public fixture loaded through gn_load
  - guest-driven native 320x224 software frame with sampled direction input
  - bounded pixel, audio, timing, and failure-progress contract
affects: [04-02-libretro-consumer, 04-03-native-qualification, phase-07-qualification]
tech-stack:
  added: []
  patterns: [tracked C fixture recipe, named generated CMake artifact, checked caller-owned frame buffers]
key-files:
  created:
    - tests/fixture/public_guest.c
    - tests/fixture/test_public_guest.c
    - tests/fixture/ORACLE.md
  modified:
    - CMakeLists.txt
    - include/glueyneo/glueyneo.h
    - src/instance.c
    - experiments/owned_cpu/cpu.c
    - experiments/owned_cpu/SUBSET.md
    - tests/owned_cpu/test_semantics.c
    - tests/owned_cpu/ORACLE.md
    - tests/consumers/check_package.py
    - tests/consumers/test_exports.py
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/deferred-items.md
key-decisions:
  - "The public fixture profile uses the distinct tagged value 0x50554246 and a strict 602-byte GNFX v1 envelope."
  - "The guest adds only ADD.W D0,D1 and MOVE.W D1,(abs.L), the two missing opcode/addressing pairs in its bounded instruction inventory."
  - "Each fixture frame restarts at the BIOS-free reset vector while guest RAM persists; its 200000-cycle ratio is fixture timing, not qualified Neo Geo timing."
  - "XRGB8888 is represented as native-endian uint32_t 0x00RRGGBB; audio metadata is signed-16 interleaved stereo at 48 kHz with zero produced frames."
actuals:
  tokens: 9750.5
  tasks: 3
  commits: 5
commits: 5
plan_head_before: 171384704ac6a7ba57f959ec15603e9449b915cd
plan_head_after: 3de6caa5f2002fb6b51436c425f80f8c86842750
requirements-completed: [TRAC-01, TRAC-02, TRAC-03, API-05]
coverage:
  - id: D1
    description: Original generated public guest loads through gn_load and draws a guest-state marker.
    requirement: TRAC-01
    verification:
      - kind: integration
        ref: "public_guest_contract; deterministic repeat matched SHA-256 59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0"
        status: pass
    human_judgment: false
  - id: D2
    description: Native frames validate caller video/audio buffers and report exact cycle-based progress.
    requirement: API-05
    verification:
      - kind: unit
        ref: "public_guest_contract#bounded_frame_metadata_and_canary_are_exact"
        status: pass
      - kind: unit
        ref: "public_guest_contract#frame_preflight_rejections_do_not_mutate_guest_or_touch_canary"
        status: pass
    human_judgment: false
  - id: D3
    description: Right input moves the guest marker and wrong-direction/no-input controls fail the expected trace.
    requirement: TRAC-03
    verification:
      - kind: integration
        ref: "public_guest_trace; public_guest_negative_left; public_guest_negative_none"
        status: pass
    human_judgment: false
duration: 10min
completed: 2026-10-07
status: complete
---

# Phase 04 Plan 01: Public Playable Tracer Summary

**An original C guest now drives a checked 320x224 native frame through the public API, with exact input, pixel, and timing controls.**

## Performance

- **Duration:** 10 minutes
- **Started:** 2026-10-07T20:55:55Z (commit-ledger creation time)
- **Completed:** 2026-10-07T21:06:10Z
- **Tasks:** 3
- **Files modified:** 12 implementation, test, and evidence files; plus this summary and deferred-items record

## Accomplishments

- Added a tracked C17 guest recipe and `glueyneo-public-fixture` target that generates the single `build/sdk-debug/public-playable.bin` artifact. The ordinary `gn_load` path validates the strict GNFX v1 envelope and copies the guest, RAM seed, and marker tile into the instance.
- The guest samples the right input port, updates its RAM coordinate, and stops at the fixture frame boundary. The native renderer reads that guest state to draw a black backdrop and white marker into caller-owned XRGB8888 storage.
- Added a public frame contract for checked dimensions, pitch, capacity, input masks, exact consumed-cycle rational time, zero-frame signed-16 stereo audio metadata, progress, and retry behavior. Canary, malformed-envelope, ownership, positive trace, and negative-control tests cover those boundaries.
- Audited the guest's bounded CPU needs. It adds two exact instruction/addressing pairs, each backed by manual-derived semantics and timing tests. A regeneration repeat matched the generated artifact hash `59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0`.

## Task Commits

1. **Task 1: Execute one original input-controlled guest frame end to end** — `ca25ed4` (`feat`)
2. **Task 2: Complete bounded frame, video and silent-audio contracts** — `02006da` (`feat`)
3. **Task 3: Prove fixed trace and wrong-input control** — `eeaa604` (`test`)

Additional corrective and regression commits:

- `cd6b969` — distinguished the public profile from the diagnostic profile's unsupported-value probe and added `gn_advance_frame` to the shared export contract.
- `3de6caa` — proved fixture source bytes are owned after load and malformed envelope rejection preserves the current image.

## Files Created/Modified

- `tests/fixture/public_guest.c` — original GNFX v1 guest, bitmap, and deterministic artifact writer.
- `tests/fixture/test_public_guest.c` — generated-artifact consumer, frame contract checks, fixed trace, controls, and malformed-content coverage.
- `tests/fixture/ORACLE.md` — guest encoding, manual ancestry, fixture semantics, and explicit hardware/evidence limits.
- `include/glueyneo/glueyneo.h`, `src/instance.c` — public fixture profile, frame API, content validation, and software output.
- `experiments/owned_cpu/cpu.c`, `tests/owned_cpu/test_semantics.c`, and CPU evidence docs — the two bounded guest instruction forms.
- `CMakeLists.txt` and `tests/consumers/*` — generated artifact/test targets and the shared-library export contract.
- `.planning/workstreams/first-playable-game/phases/04-public-playable-tracer/deferred-items.md` — unrelated full-suite README-link failures.

## Validation

- Task 1 build and `public_guest_tracer` passed before Task 2 expansion and passed again after its commit. The tracer feedback gate therefore continued without a human checkpoint under the configured end-of-phase verification mode.
- Task 2 RED used CTest's JUnit report; `gsd_run check tdd-red-evidence` returned `RED_EVIDENCE_OK` for the expected missing time metadata and null-audio-capacity rejection. After implementation, `cmake --build --preset sdk-debug --target public_guest_test` and `ctest --preset sdk-debug -R '^public_guest_' --output-on-failure --no-tests=error` passed.
- Task 3's `public_guest_trace`, `public_guest_negative_left`, and `public_guest_negative_none` tests passed. The full public-fixture contract test also passed.
- The owned CPU semantic test passed. Shared static/shared SDK builds and consumers, package export tests (`python3 -m unittest tests/consumers/test_exports.py`), diagnostic SDK suites, mutation tests, isolation tests, and all public-fixture tests passed.
- The final full `sdk-debug` CTest run executed 26 tests: 24 passed and two documentation/package checks failed on the same pre-existing missing README link. Details are in [deferred-items.md](./deferred-items.md); the run was not weakened or repeated to hide the failure.

## Decisions Made

- The fixture starts through its source-built BIOS-free reset vector. This is fixture behavior, not an SNK BIOS or normal MVS boot claim.
- Each frame samples one logical input, restarts the bounded fixture CPU at its reset vector, preserves guest RAM, and executes the explicit 200000-cycle contract.
- Physical Neo Geo board/video behavior, hardware timing, BIOS boot, and commercial-game compatibility remain unqualified.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Avoided collision with the diagnostic unsupported-profile probe**
- **Found during:** Full SDK regression after Task 3
- **Issue:** Assigning the new profile value `2` caused existing diagnostic tests to interpret `GN_PROFILE_DIAGNOSTIC + 1` as a malformed public fixture instead of an unsupported profile.
- **Fix:** Assigned the public fixture profile the tagged value `0x50554246` and preserved the existing status strings.
- **Files modified:** `include/glueyneo/glueyneo.h`, `src/instance.c`
- **Verification:** `sdk_media` and `sdk_mutation_media` passed.
- **Committed in:** `cd6b969`

**2. [Rule 2 - Missing critical functionality] Registered the new public symbol in shared-consumer checks**
- **Found during:** Full SDK regression after Task 3
- **Issue:** Shared package checks rejected the newly exported `gn_advance_frame` symbol as an unreviewed extra export.
- **Fix:** Added the frame function to the exact export contract and updated its Windows parser fixture.
- **Files modified:** `tests/consumers/check_package.py`, `tests/consumers/test_exports.py`
- **Verification:** Static/shared package build and consumer tests passed; all 12 export tests passed.
- **Committed in:** `cd6b969`

**3. [Rule 2 - Missing critical functionality] Added explicit public-content ownership and rejection regressions**
- **Found during:** Final acceptance review
- **Issue:** Task 1 required copied-content ownership and strict envelope rejection, but the initial C consumer did not directly verify those paths.
- **Fix:** Overwrote source bytes after successful load and verified execution still worked; rejected a modified envelope version while retaining the live image.
- **Files modified:** `tests/fixture/test_public_guest.c`
- **Verification:** The full `public_guest_*` CTest selection passed.
- **Committed in:** `3de6caa`

**Total deviations:** 3 auto-fixed (one Rule 1 bug, two Rule 2 completeness fixes). They close direct profile, ABI, and threat-model evidence gaps.

## Deferred Issues

The two failing full-suite checks are documented in [deferred-items.md](./deferred-items.md). Their root README link points at a flat `.planning/phases/` path while the verification file is stored under the sibling diagnostic workstream; this is outside the 04-01 task scope.

## User Setup Required

None.

## Next Phase Readiness

Plan 04-01 is complete and supplies the public guest artifact and native consumer contract for the next Phase 04 plan. Phase 04 itself is not complete; the pinned RetroArch path, sound-candidate admissions, and remaining qualification plans are still open.

## Self-Check: PASSED

- Summary and deferred-items files exist.
- All five task commits are ancestors of the current plan head (`3de6caa`).
- The measured plan commit count is five, matching the recorded task/fix commits.

---
*Phase: 04-public-playable-tracer*
*Completed: 2026-10-07*
