---
phase: 05-selected-mvs-boot
plan: 03
subsystem: mvs-qualification
tags: [c17, mvs, libretro, retroarch, qualification]
requires:
  - phase: 05-02
    provides: selected-source importer, normalized GNMV bundle, seven-test MVS matrix lane
provides:
  - Bounded structural validation for selected-format GNMV content in the local RetroArch smoke runner
  - Nonzero local qualification exit when a selected guest has not reached attract/start
affects: [first-playable-game-phase-05, mvs-media, libretro]
actuals:
  tokens: 4471
  tasks: 0
  commits: 2
tech-stack:
  added: []
  patterns:
    - Selected local content produces generic identity metadata without emitting media paths or digests
    - Unsupported or incomplete guest qualification returns a nonzero command status
key-files:
  created: []
  modified:
    - tools/mvs/qualify_local_boot.py
    - tests/libretro/retroarch_smoke.py
    - tests/libretro/test_retroarch_smoke.py
    - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-VALIDATION.md
    - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-REVIEW.md
key-decisions:
  - "Do not add CPU or board behavior without a selected-guest trace identifying the unsupported event and its source ancestry."
  - "Keep selected RetroArch input response unknown until direct evidence classifies it; screenshots and key injection alone do not pass the smoke."
requirements-completed: []
coverage:
  - id: D1
    description: "The smoke runner validates a bounded selected-format GNMV envelope and preserves the exact public GNFX identity gate."
    verification:
      - kind: unit
        ref: "python3 tests/libretro/test_retroarch_smoke.py -v"
        status: pass
    human_judgment: true
    rationale: "Actual selected guest boot and pinned RetroArch behavior were not observed."
  - id: D2
    description: "The ignored local qualifier reports an unsupported input pair and exits unsuccessfully."
    verification:
      - kind: other
        ref: "python3 tools/mvs/qualify_local_boot.py --input-root local/roms --report local/qualification/phase05.json"
        status: fail
    human_judgment: true
    rationale: "The configured local archives did not match the supported role-bundle profile, so no guest execution occurred."
metrics:
  duration: 9min
  completed: 2026-10-09
status: halted
commits: 2
plan_head_before: c1f26c23a5cf387ad50516ddcfc26c7ad36818db
plan_head_after: 5fe91d0c489c6fa2ad5cce6c10f845557ecdae47
---

# Phase 05 Plan 03: Selected Guest Boot Summary

**The local acceptance paths now fail closed and the frontend smoke can validate a normalized GNMV input, but selected guest boot and hosted current-SHA acceptance remain unproven.**

## Performance

- **Duration:** 9 minutes
- **Started:** 2026-10-09T13:03:18Z
- **Completed:** 2026-10-09T13:12:12Z
- **Tasks completed:** 0 of 3; partial work from Tasks 2 and 3 is committed
- **Files modified:** 5

## Accomplishments

- The local qualifier now writes its sanitized report and exits nonzero unless a guest-executed `attract_start` result is present.
- The RetroArch runner validates the version-1 MSX GNMV header, role set, region sizes, exact bundle length, and a 64 MiB read bound. Its selected-content result stays `unknown` and exits nonzero; the public GNFX digest identity gate remains unchanged.
- Synthetic smoke tests cover valid, malformed, missing, and oversized GNMV input, verify rejection before process launch, and check that selected-content identity output omits the bundle path and digest.
- MEDIA-03, MEDIA-04, and GAME-02 remain Pending. No UAT resolution, STATE.md update, or ROADMAP.md update was made.

## Task Commits

1. **Task 2 partial: Fail local qualification unless attract/start is reached** — `64ef2b2` (`fix`)
2. **Task 3 partial: Validate selected MVS content in frontend smoke** — `5fe91d0` (`feat`)

No task 1 CPU or MVS behavior commit was made because no selected guest event was observed.

## Verification

- `python3 tests/libretro/test_retroarch_smoke.py -v` — passed, 31/31.
- `cmake --preset sdk-debug && cmake --build --preset sdk-debug && ctest --preset sdk-debug -R '^(mvs_|owned_)' --output-on-failure --no-tests=error` — passed, 7/7 registered MVS tests.
- `cmake --build --preset sdk-asan-ubsan --target mvs_qualify mvs_test mvs_importer mvs_import_fuzz && ctest --test-dir build/sdk-asan-ubsan -R '^mvs_' --output-on-failure --no-tests=error` — passed, 7/7.
- `cmake --preset sdk-asan-ubsan && cmake --build --preset sdk-asan-ubsan && ctest --preset sdk-asan-ubsan -R '^mvs_' --output-on-failure --no-tests=error` — blocked during the full build by the inherited Unity static-library sanitizer-runtime link failure in the unrelated YM2610 admission target. The focused MVS sanitizer targets and tests pass.
- `python3 tools/mvs/qualify_local_boot.py --input-root local/roms --report local/qualification/phase05.json` — wrote the ignored generic report with `no_supported_role_bundle_archive`, then exited 1. No guest instruction or device event was observed.
- `python3 tools/verify_sdk.py --suite matrix` — local suite passed on source revision `5fe91d0c489c6fa2ad5cce6c10f845557ecdae47`; `python3 tests/sdk/test_matrix_evidence.py` passed. This is not hosted G-05-5 evidence.
- The hosted CI workflow runs on pull requests or pushes to `main`. This branch has no upstream or open PR; a PR from it would include 287 commits ahead of `main`. No PR was opened, no protected branch was modified, and no hosted receipt is claimed.
- The actual RetroArch smoke was not launched because the selected native guest did not reach attract/start. No Phase 04 RetroArch observation was reused.
- `git diff --check` — passed.

## Independent Review

The smoke-runner change received independent review. The reviewer found an input-size race between `stat()` and the initial file read. The runner now reads at most `GNMV_MAX_BYTES + 1` bytes, and a sparse oversized-input test confirms rejection before process launch. The reviewer rechecked the fix and found no new actionable findings. This review covers only the smoke-runner changes; there were no CPU or board semantics to review.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fail local qualification when attract/start is absent**
- **Found during:** Task 2
- **Issue:** The wrapper returned success for a generic unsupported-bundle result, which could make an unqualified run appear successful to automation.
- **Fix:** The report is still written safely, but the command returns success only for `attract_start` with `guest_executed: true`.
- **Files modified:** `tools/mvs/qualify_local_boot.py`
- **Commit:** `64ef2b2`

**2. [Rule 2 - Security] Bound selected-bundle reads across file-size changes**
- **Found during:** Task 3 independent review
- **Issue:** A GNMV file could grow after the size check and trigger an allocation beyond the planned input limit.
- **Fix:** Read at most one byte beyond the 64 MiB cap and reject before parsing or launch; add a sparse oversized-input regression.
- **Files modified:** `tests/libretro/retroarch_smoke.py`, `tests/libretro/test_retroarch_smoke.py`
- **Commit:** `5fe91d0`

## Blockers

- The ignored local qualification input did not contain a unique pair accepted by the supported role-bundle contract. The first blocking stage remains `archive_to_region_mapping`; selected guest execution, the attract/start predicate, and any source-led CPU/MVS changes remain unknown.
- The hosted seven-test receipt is unavailable on this local branch because the workflow has no manual dispatch and this branch has no PR/upstream. The local matrix does not satisfy G-05-5.
- Actual pinned RetroArch behavior remains unobserved because native selected-game acceptance did not pass.

## TDD Gate Compliance

The active workstream config has `workflow.tdd_mode: false`, so the runtime TDD commit gate was inactive. The selected-guest behavior tasks did not complete and therefore have no RED/GREEN implementation sequence. The frontend smoke tests were added with their implementation; they do not establish selected-game acceptance.

## Next Phase Readiness

Plan 05-03 is **halted**, and Phase 05 remains **incomplete**. Resume after the exact supported game/BIOS archives are available under the configured ignored local input path and the hosted CI receipt can be bound to a reviewable PR revision. Then continue observe → source → rights-clear regression → implement for each selected guest event, verify direct attract/start, and run the actual-app smoke. `$gsd-verify-work 05 --ws first-playable-game` should run only after the gap-closure evidence exists; its `reconcile_gaps` step alone owns UAT resolution.

---
*Phase: 05-selected-mvs-boot*
*Plan: 03*
*Status: halted*

## Self-Check: PASSED

The summary exists, and task commits `64ef2b2` and `5fe91d0` are ancestors of the current HEAD.
