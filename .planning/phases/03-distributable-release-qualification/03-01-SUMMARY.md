---
phase: 03-distributable-release-qualification
plan: 01
subsystem: release-packaging
tags: [cmake, python, source-archive, sdk-archive, exports]
requires: []
provides:
  - Deterministic source and host SDK archive builder bound to a committed revision and manifest version.
  - Offline source rebuild, safe archive extraction, and relocated C/C++ consumer evidence.
  - Shared-library export contract and fail-closed Windows DUMPBIN parser fixtures.
affects: [03-distributable-release-qualification, release-packaging]
actuals:
  tokens: 10987
  tasks: 2
  commits: 3
plan_head_before: 8ddebb9856e70e0e753e0747059b97a9a8e63a32
plan_head_after: 1e8fc5fdec558dcac601cc6e45187b8aecd658bf
tech-stack:
  added: []
  patterns: [stdlib-only Python release tooling, deterministic archive metadata, fail-closed symbol inspection]
key-files:
  created: [.release-please-manifest.json, tools/release_manifest.py, tests/consumers/test_release_consumer.py, tests/consumers/test_exports.py]
  modified: [CMakeLists.txt, tests/consumers/check_package.py]
key-decisions:
  - "The root release-please manifest is the sole CMake project/package version source."
  - "The SDK carries separately relocatable static and shared package prefixes."
  - "Windows export inspection uses DUMPBIN output and requires the exact shared public symbol set."
patterns-established:
  - "Bind archive identity to exact committed source, version, build configuration, and per-file digests."
  - "Reject unsafe archive members and unsupported export-inspector output."
requirements-completed: [BUILD-03, DEL-03, DEL-04]
coverage:
  - id: D1
    description: Rebuild exact source archive offline and run relocated SDK diagnostic plus C and C++ consumers.
    requirement: BUILD-03
    verification:
      - kind: e2e
        ref: python3 tests/consumers/test_release_consumer.py#test_release_archive_rebuilds_offline_and_relocates_consumers
        status: pass
    human_judgment: false
  - id: D2
    description: Root manifest controls CMake project and installed package version and malformed values fail configure.
    requirement: DEL-03
    verification:
      - kind: integration
        ref: python3 tests/consumers/test_release_consumer.py#manifest version tests
        status: pass
    human_judgment: false
  - id: D3
    description: Windows PE export parser fixtures enforce the shared exact public/private symbol contract.
    requirement: DEL-04
    verification:
      - kind: unit
        ref: python3 tests/consumers/test_exports.py (4 fixtures)
        status: pass
    human_judgment: true
    rationale: Fixture parsing passed, but this Darwin arm64 runner cannot inspect a generated Windows DLL; Windows/MSVC qualification remains pending.
duration: 12min
completed: 2026-10-06
status: complete
---

# Phase 03 Plan 01: Reproducible Archives and Export Contract Summary

**Committed-version source and SDK archives rebuild offline and relocate successfully on Darwin arm64, with exact export checks and Windows parser fixtures.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-10-06T16:57:27Z
- **Completed:** 2026-10-06T17:09:32Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added deterministic source and SDK archive generation from an exact committed SHA and root manifest version, with safe bounded extraction and final archive digests.
- Proved offline source rebuilding and relocated static/shared SDK consumers, including the diagnostic runner and compiled C/C++ consumers, on Darwin arm64 with AppleClang 21.0.0.21000101 and CMake 4.4.3.
- Added Windows DUMPBIN parser fixtures and fail-closed exact export comparison. Fixture coverage is not on-runner generated-DLL qualification.

## Task Commits

1. **Task 1: Build and consume one complete release archive** - `c3f120b` (RED tests), `530b38d` (implementation/GREEN).
2. **Task 2: Prove shared export parity on all selected systems** - `1e8fc5f` (parser and fixture implementation).

## Files Created/Modified

- `.release-please-manifest.json` - canonical root version.
- `tools/release_manifest.py` - deterministic archive, identity, digest, and safe extraction tooling.
- `tests/consumers/test_release_consumer.py` - manifest, archive, offline rebuild, relocation, and unsafe-member acceptance tests.
- `tests/consumers/check_package.py` - shared export contract, Windows inspector and consumer suite evidence.
- `tests/consumers/test_exports.py` - DUMPBIN-style parser fixtures and fail-closed controls.
- `CMakeLists.txt` - manifest-derived configure and package version.

## Decisions Made

- Used the root release-please manifest as the single version source.
- Packaged static and shared variants under separate install prefixes so each can relocate independently.
- Chose DUMPBIN `/EXPORTS` for Windows and require an available supported inspector; recorded its identity in shared build evidence.
- Requirements are listed as this plan's traceability references, but the milestone requirement register remains pending because shared acceptance spans later plans and platform/hosted checks.

## TDD Evidence

- Task 1 RED: `build/tdd-red-releaseconsumer.json`; `gsd_run check tdd-red-evidence ...` returned `RED_EVIDENCE_OK` for the missing manifest-controlled CMake/package version behavior. RED commit: `c3f120b`.
- Task 1 GREEN: `python3 tests/consumers/test_release_consumer.py` passed all 4 tests against the committed implementation.
- Task 2 RED: `build/tdd-red-windows-exports.json`; `gsd_run check tdd-red-evidence ...` returned `RED_EVIDENCE_OK` for the missing Windows exact-export inspector contract. RED assertions failed for the absent parser/inspector (not import or syntax errors).
- Task 2 verification: `python3 tests/consumers/test_exports.py` passed 4/4 parser fixtures; `python3 tests/consumers/check_package.py --suite consumers` passed 2/2 local CTest consumer cases, static and shared, with 41 assertions each.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Kept loader diagnostics out of wrong-output assertions**
- **Found during:** Task 2 consumer suite.
- **Issue:** The shared wrong-output control captured local DYLD loader paths, so environment diagnostics could obscure the intended result check.
- **Fix:** Preserved clean output for the negative control and used the relocated package DLL directory for the Windows moved-package PATH.
- **Files modified:** `tests/consumers/check_package.py`.
- **Verification:** Both static/shared consumer cases passed after the correction.
- **Committed in:** `1e8fc5f`.

**Total deviations:** 1 auto-fixed (Rule 1).
**Impact on plan:** Necessary to make the negative control test the consumer result instead of host loader logging; no scope expansion.

## Issues Encountered

- Windows parser fixtures passed, but no Windows runner was available to inspect a generated DLL. Linux/macOS/Windows shared export parity therefore remains unqualified pending the planned platform matrix.
- Hosted release-please behavior, GitHub event/token authority, draft/recovery semantics, and artifact publication were not exercised. Related release claims remain pending.
- No release-signing or public artifact publication was performed.

## User Setup Required

None for local archive generation or consumer testing.

## Next Phase Readiness

Plan 03-01 is complete. Phase 03 is not complete: Windows on-runner generated-DLL inspection and hosted release authority/publication evidence remain pending alongside subsequent plans. Once the user continues, execute the remaining plan with `$gsd-execute-phase 03`.

## Self-Check: PASSED

All six plan-owned files exist; task commits `c3f120b`, `530b38d`, and `1e8fc5f` are ancestors of the plan head recorded above. The measured plan commit count is three.

---
*Phase: 03-distributable-release-qualification*
*Completed: 2026-10-06*
