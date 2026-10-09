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
  - Trace-demanded MC68000/MVS behavior with rights-clear tests and bounded ignored fetch/profile diagnostics
affects: [first-playable-game-phase-05, mvs-media, libretro]
actuals:
  tokens: 126624
  tasks: 1
  commits: 6
tech-stack:
  added: []
  patterns:
    - Selected local content produces generic identity metadata without emitting media paths or digests
    - Unsupported or incomplete guest qualification returns a nonzero command status
key-files:
  created: []
  modified:
    - experiments/owned_cpu/cpu.c
    - experiments/owned_cpu/cpu.h
    - src/mvs/mvs_bus.c
    - src/instance.c
    - include/glueyneo/glueyneo.h
    - tools/mvs/qualify_local_boot.py
    - tools/mvs/mvs_qualify.c
    - tools/mvs/mvs_import.c
    - tests/owned_cpu/test_semantics.c
    - tests/mvs/test_mvs.c
    - tests/mvs/test_mvs_qualification.py
    - tests/libretro/retroarch_smoke.py
    - tests/libretro/test_retroarch_smoke.py
    - docs/mvs-media.md
    - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-VALIDATION.md
    - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-REVIEW.md
key-decisions:
  - "Add only observed CPU/MVS operations with primary-source semantics, exact timing, and rights-clear controls; keep unsupported events fail-closed."
  - "Treat device-state activity and budget exhaustion as unknown, never as a selected attract/start checkpoint."
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
    description: "The ignored local qualifier reports selected guest budget exhaustion and exits unsuccessfully."
    verification:
      - kind: other
        ref: "python3 tools/mvs/qualify_local_boot.py --input-root local/roms --report local/qualification/phase05.json"
        status: fail
    human_judgment: true
    rationale: "The configured selected pair imports and executes, but the bounded run does not expose a direct guest-written attract/start predicate."
metrics:
  duration: 6h12min
  completed: 2026-10-09
status: halted
commits: 6
plan_head_before: c1f26c23a5cf387ad50516ddcfc26c7ad36818db
plan_head_after: 06cba8125a1b0796446f90ea734232cdc7f18f5b
---

# Phase 05 Plan 03: Selected Guest Boot Summary

**The selected guest imports and runs through a sanitized 256-chunk bound with per-chunk device-state profiling, but no guest-written attract/start predicate or safe hosted receipt is established.**

## Performance

- **Duration:** approximately 6 hours 12 minutes
- **Started:** 2026-10-09T13:03:18Z
- **Completed:** 2026-10-09T13:12:12Z
- **Tasks completed:** 1 of 3; Tasks 2 and 3 remain incomplete because acceptance gates are open
- **Files modified:** 36 tracked files across the six plan commits

## Accomplishments

- The local qualifier now writes its sanitized report and exits nonzero unless a guest-executed `attract_start` result is present.
- The RetroArch runner validates the version-1 MSX GNMV header, role set, region sizes, exact bundle length, and a 64 MiB read bound. Its selected-content result stays `unknown` and exits nonzero; the public GNFX digest identity gate remains unchanged.
- Synthetic smoke tests cover valid, malformed, missing, and oversized GNMV input, verify rejection before process launch, and check that selected-content identity output omits the bundle path and digest.
- MEDIA-03, MEDIA-04, and GAME-02 remain Pending. No UAT resolution, STATE.md update, or ROADMAP.md update was made.

## Task Commits

1. **Task 2: Fail local qualification unless attract/start is reached** — `64ef2b2` (`fix`)
2. **Task 3: Validate selected MVS content in frontend smoke** — `5fe91d0` (`feat`)
3. **Task 1: Implement trace-demanded MC68000/MVS behavior and rights-clear vectors** — `563437e` (`fix`)
4. **Task 2 follow-up: Add sanitized bounded run profiling and spoof-resistant result handling** — `a7c54ba` (`fix`)
5. **Task 3/evidence follow-up: Reconcile review and validation artifacts** — `8c22e75`, `06cba81` (`docs`)

The plan is intentionally halted with Tasks 2 and 3 incomplete: no guest-written attract/start predicate or exact-revision hosted receipt was established.

## Verification

- `python3 tests/libretro/test_retroarch_smoke.py -v` — passed, 31/31.
- `cmake --preset sdk-debug && cmake --build --preset sdk-debug && ctest --preset sdk-debug -R '^(mvs_|owned_)' --output-on-failure --no-tests=error` — passed, 7/7 registered MVS tests.
- `cmake --build --preset sdk-asan-ubsan --target mvs_qualify mvs_test mvs_importer mvs_import_fuzz && ctest --test-dir build/sdk-asan-ubsan -R '^mvs_' --output-on-failure --no-tests=error` — passed, 7/7.
- `cmake --preset sdk-asan-ubsan && cmake --build --preset sdk-asan-ubsan && ctest --preset sdk-asan-ubsan -R '^mvs_' --output-on-failure --no-tests=error` — blocked during the full build by the inherited Unity static-library sanitizer-runtime link failure in the unrelated YM2610 admission target. The focused MVS sanitizer targets and tests pass.
- `python3 tools/mvs/qualify_local_boot.py --input-root local/roms --report local/qualification/phase05.json` — the current run imports and executes the selected guest through 256 chunks (256,000,794 cycles; 32,255,007 instructions), then exits 1 with `guest_instruction_budget_exhausted`. The ignored, sanitized profile reports 140 state-stable chunks, 20 output/latch transition chunks, 97 video-state transition chunks, 17 bank-transition chunks, 6,472,496 watchdog pets, zero resets, and no repeated final chunk-boundary suffix. This activity is not an attract/start predicate.
- `python3 tools/verify_sdk.py --suite matrix` — local suite passed on the earlier source revision `5fe91d0c489c6fa2ad5cce6c10f845557ecdae47`; `python3 tests/sdk/test_matrix_evidence.py` passed. This is not hosted G-05-5 evidence.
- No safe exact-current-revision hosted route was available: the branch contains substantial unrelated history, and publishing it would expose that delta. No PR was opened, no protected branch was modified, and no hosted receipt is claimed.
- The actual RetroArch smoke was not launched because the selected native guest did not reach attract/start. No Phase 04 RetroArch observation was reused.
- `git diff --check` — passed.

## Independent Review

The smoke-runner change received independent review. The reviewer found an input-size race between `stat()` and the initial file read. The runner now reads at most `GNMV_MAX_BYTES + 1` bytes, and a sparse oversized-input test confirms rejection before process launch. The reviewer rechecked the fix and found no new actionable findings. A subsequent independent review covered the accumulated CPU/MVS/API/privacy delta. CPU/board behavior was added from observed guest events; the review does not accept the title boot.

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

- The sanitized local qualification accepts the selected game/BIOS archives and executes the guest, but reaches the 256-chunk hard bound without an unsupported event or direct attract/start. The bounded ignored fetch ring matches the normalized manifest buffer and ends at the same cursor as the run boundary. Device-state transition counts show activity only; no source-defined guest-written checkpoint has been established. G-05-3 remains open.
- The hosted seven-test receipt is unavailable on this local branch because the workflow has no manual dispatch and this branch has no PR/upstream. The branch contains substantial unrelated history, so publishing it is not a safe exact-SHA route. The local matrix does not satisfy G-05-5.
- Actual pinned RetroArch behavior remains unobserved because native selected-game acceptance did not pass.

## TDD Gate Compliance

The active workstream config has `workflow.tdd_mode: false`, so the runtime TDD commit gate was inactive. Guest-demanded CPU/MVS changes were developed with rights-clear RED/GREEN tests and exact source timing assertions; the bounded-run profile and wrapper sanitization have synthetic validation. These checks do not establish selected-game acceptance.

## Next Phase Readiness

Plan 05-03 is **halted**, and Phase 05 remains **incomplete**. The latest selected run reached the measured 256-chunk bound with no unsupported event and no guest-written attract/start predicate. The ignored local report retains bounded diagnostic data; tracked evidence contains only generic status and coarse counters. G-05-3 still requires direct attract/start, G-05-5 requires an exact-revision hosted receipt, and the actual-app smoke remains gated on attract/start. `$gsd-verify-work 05 --ws first-playable-game` should run only after those gap-closure gates are addressed; its `reconcile_gaps` step alone owns UAT resolution.

---
*Phase: 05-selected-mvs-boot*
*Plan: 03*
*Status: halted*

## Self-Check: PASSED

The summary exists, and all six plan commits (`64ef2b2`, `5fe91d0`, `8c22e75`, `563437e`, `a7c54ba`, `06cba81`) are ancestors of the current HEAD. The plan ledger measures six task/evidence commits before this summary commit.
