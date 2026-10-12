---
phase: 05-selected-mvs-boot
plan: 02
subsystem: media-and-ci
tags: [c17, mvs, zip32, zlib-1.3.2, ctest, qualification]
requires:
  - phase: 05-selected-mvs-boot
    plan: 01
    provides: bounded canonical ZIP32 importer, normalized GNMV contract, synthetic MVS guest runner
provides:
  - Selected mslugx game ZIP plus separate sp-s2.sp1 BIOS source mapping with public member identity checks
  - Private-safe local selected-media qualification wrapper and synthetic split archive regression
  - Exact seven-test MVS CTest lane bound to relevant source identity and current revision
affects: [first-playable-game-phase-05, mvs-media, sdk-verification]
actuals:
  tokens: 55878
  tasks: 3
  commits: 8
tech-stack:
  added: []
  patterns: [selected source identity validation before mapping, private-safe local report publication, source-bound named CTest lane]
key-files:
  created: []
  modified:
    - tools/mvs/mvs_import.c
    - tools/mvs/qualify_local_boot.py
    - tests/mvs/test_mvs_qualification.py
    - docs/mvs-media.md
    - tools/verify_sdk.py
    - tools/sdk_evidence.py
    - tests/sdk/test_matrix_evidence.py
    - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-VALIDATION.md
    - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-REVIEW.md
key-decisions:
  - "Accept only the pinned public mslugx member identities with the separate sp-s2.sp1 BIOS profile; keep synthetic identities behind test-only compilation."
  - "Keep selected-media qualification local and emit only sanitized status/checkpoint information; private media remains outside Git and CI."
  - "Treat the split-source synthetic guest sentinel as a mapping prerequisite, not proof of selected-game compatibility or attract/start behavior."
  - "Require all seven named MVS CTests in the matrix and bind the result to the relevant source digest and source revision."
requirements-completed: []
coverage:
  - id: D1
    description: "A bounded split game/BIOS source pair maps through the production importer into normalized MVS regions and the synthetic native guest checkpoint."
    verification:
      - kind: integration
        ref: "ctest --preset sdk-debug --output-on-failure --no-tests=error"
        status: pass
      - kind: integration
        ref: "ctest --test-dir build/sdk-asan-ubsan -L mvs --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D2
    description: "The seven-test MVS CTest lane is required and source-bound in the local matrix verification."
    verification:
      - kind: integration
        ref: "python3 tools/verify_sdk.py --suite matrix"
        status: pass
      - kind: unit
        ref: "python3 tests/sdk/test_matrix_evidence.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Selected private media compatibility, selected guest execution, and direct frontend behavior remain unobserved."
    verification: []
    human_judgment: true
    rationale: "No local archive pair matched the supported profile, and the phase still requires direct selected guest attract/start and hosted CI evidence in dependent Plan 05-03."
duration: 617min
completed: 2026-10-09
status: complete
commits: 8
plan_head_before: 85a5e47914a214876ef9dfb89c3b79a2f7131953
plan_head_after: 916cb9f7251acc0ea5d9892aa2ff14bdcaaf6c95
---

# Phase 05 Plan 02: Selected MVS Source Mapping and CI Summary

**The C17 importer now verifies and maps a pinned split mslugx game/BIOS pair, and the seven-test MVS lane is required in source-bound matrix evidence; selected-game boot remains unqualified.**

## Performance

- **Duration:** 617 minutes from the persisted plan start marker
- **Started:** 2026-10-09T02:40:41Z
- **Completed:** 2026-10-09T12:57:05Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added an explicit selected-source importer path for separate game and BIOS ZIPs. It validates pinned public source member names, sizes, CRCs, and SHA-1 identities before mapping the six normalized MVS roles and atomically publishing GNMV output. The canonical six-role import path remains available.
- Added synthetic split archive coverage for region byte vectors, native guest sentinel execution, malformed/ambiguous inputs, wrong identities, resource bounds, and failed output publication. The test identity seam is compiled only for the test importer.
- Added local-only pair selection and a sanitized ignored report. The current local run reported `no_supported_role_bundle_archive`; no selected media reached the native runner, and no local identity was emitted.
- Added an exact named seven-test MVS matrix lane and expanded relevant-source hashing. Current lane evidence passed on revision `7e92926ea291b6663d60bc2a5f152bc89b281e88` with relevant-source digest `105deb95d946a075ef1586553271579f3983b4e3533062a72a108fb1bf9c8b82`.
- Updated the phase validation map and independent review. The review found no remaining actionable issues after the local report temporary-file race was fixed.

## Task Commits

1. **Task 1: split game and BIOS archive tracer** — `9e667f4` (RED tests), `13e2d63` (GREEN implementation).
2. **Task 2: exact MVS matrix evidence lane** — `f274572` (RED tests), `0888f46` (GREEN implementation), `5affd8b` (fix duplicate source identity), `7e92926` (sanitizer-compatible synthetic importer build).
3. **Task 3: verification and independent review** — `4b32e79` (unique atomic local report file), `916cb9f` (validation and review docs).

## Verification

- `cmake --preset sdk-debug && cmake --build --preset sdk-debug && ctest --preset sdk-debug --output-on-failure --no-tests=error` — passed, 41/41.
- `cmake --preset sdk-asan-ubsan && cmake --build build/sdk-asan-ubsan --target mvs_qualify mvs_test mvs_importer mvs_import_fuzz && ctest --test-dir build/sdk-asan-ubsan -L mvs --output-on-failure --no-tests=error` — passed, 7/7.
- `python3 tests/sdk/test_matrix_evidence.py` — passed exact inventory, omission, denominator, failed-outcome, and stale-source checks.
- `python3 -m py_compile tools/mvs/qualify_local_boot.py tests/mvs/test_mvs_qualification.py` and `git diff --check` — passed.
- `python3 tools/verify_sdk.py --suite matrix` — passed the local matrix. The local hosted-platform subreceipt is `unknown` because this environment is not a GitHub-hosted runner; it is not represented as hosted CI evidence.

## TDD Gate Compliance

- **Task 1 RED:** `mvs_import_contract` selected-source regression failed before implementation because the importer did not accept `--selected`; `gsd_run check tdd-red-evidence` returned `RED_EVIDENCE_OK` after report and assertion review. RED commit: `9e667f4`.
- **Task 1 GREEN:** production mapping and local wrapper implemented; focused importer/native guest tests and the full Debug suite passed. GREEN commit: `13e2d63`.
- **Task 2 RED:** the named MVS matrix inventory test failed before implementation because `CTEST_CASES` omitted `mvs`; `gsd_run check tdd-red-evidence` returned `RED_EVIDENCE_OK` after semantic review. RED commit: `f274572`.
- **Task 2 GREEN:** MVS collection, validation, and source identity were implemented; the focused evidence tests and full local matrix passed. GREEN commit: `0888f46`.
- **REFACTOR:** no separate refactor commit was needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Security] Replaced predictable local report temporary path**
- **Found during:** Task 3 independent review
- **Issue:** A fixed `.json.tmp` path could collide across concurrent runs or follow a preexisting symlink.
- **Fix:** Use a unique exclusive temporary file in the ignored report directory, atomically replace the destination, and remove the temporary file on failure.
- **Files modified:** `tools/mvs/qualify_local_boot.py`
- **Commit:** `4b32e79`

**2. [Rule 1 - Bug] Removed duplicate public header from matrix source inventory**
- **Found during:** Task 3 matrix verification
- **Issue:** A duplicate path caused the verifier's unique-and-sorted identity validation to fail closed.
- **Fix:** Keep the public header once in the canonical relevant-source inventory.
- **Files modified:** `tools/sdk_evidence.py`
- **Commit:** `5affd8b`

## Deferred Issues

- The first configured post-wave `owned-debug` run exposed one inherited stale source identity: `owned_cpu_inventory_check` rejected the `CMakeLists.txt` hash recorded before Phase 05-01 added MVS targets. The source-manifest refresh changed only that exact hash; the inventory check and complete 54-test suite then passed. Historical acceptance receipts and budget ledgers remain unchanged.
- A full `sdk-asan-ubsan` build also attempted unrelated package-consumer targets and stopped at unresolved sanitizer runtime symbols from the Unity static archive. The focused MVS sanitizer targets built and passed 7/7; the unrelated consumer/link path remains outside this plan's source scope.
- No supported local game/BIOS pair was available, so selected guest execution, attract/start behavior, and direct frontend observation remain unknown for dependent Plan 05-03.

## Self-Check: PASSED

The validation and review files exist; all eight task commits are ancestors of the plan head recorded above. Plan 05-02 claims neither G-05-3 nor G-05-5 resolved and does not change Phase 04 dispositions.
