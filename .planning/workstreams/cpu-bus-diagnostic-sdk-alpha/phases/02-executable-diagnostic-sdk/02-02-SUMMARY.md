---
phase: 02-executable-diagnostic-sdk
plan: "02"
subsystem: sdk
tags: [c17, lifecycle, media-validation, allocation-failures, ctest]

requires:
  - phase: 01-cpu-acceptance-experiment
    provides: Accepted owned C17 CPU backend for the bounded diagnostic subset
provides:
  - Checked per-instance lifecycle errors, repeatable reset, unload and reuse
  - Transactional copied diagnostic media with checked descriptor bounds
  - Private per-instance allocation failpoints and counted recovery evidence
  - Integrator ownership, lifetime, status and failure-reproduction guide
affects: [Phase 02 timing, package consumers, hostile-input and evidence plans]

actuals:
  tokens: 19833
  tasks: 3
  commits: 3
  plan_head_before: 30cbcac7299386cfc490cd576e9fbc55f5087f81
  plan_head_after: 5dc56d68acc7fbdf2f4ff6c2aeda420d63f2d194

tech-stack:
  added: []
  patterns:
    - Separate public and test-only SDK runtime targets; failpoint and digest hooks stay private
    - Validate all media before allocation, build a candidate, then atomically replace the live image
    - Counted per-instance allocation sweeps with peer-instance recovery checks

key-files:
  created:
    - src/sdk_private.h
    - tests/sdk/test_support.h
    - docs/ownership-and-errors.md
  modified:
    - src/instance.c
    - tests/sdk/test_sdk.c
    - CMakeLists.txt

key-decisions:
  - "Keep allocator failpoints and full image digests behind a separately compiled test target so installed headers and the public runtime expose no test hooks."
  - "The fixed diagnostic profile has no caller-selected permissions field; ROM is read-only and RAM is writable."
  - "Stop allocating a candidate at the first failed allocation and clean it up before returning an actionable status."

patterns-established:
  - "Reject malformed manifests before candidate allocation; preserve the old image until a fully initialized replacement is ready."
  - "Report exact attempts, live allocations and requested live bytes at every injected allocation boundary."

requirements-completed: [API-01, API-02, API-04, EVID-02, DOC-01]

coverage:
  - id: D1
    description: Lifecycle misuse has bounded statuses and cleared outputs; repeated reset/unload, reload and runtime host-service closure are checked.
    requirement: API-01
    verification:
      - kind: integration
        ref: "ctest --preset sdk-debug -L 'sdk-lifecycle|sdk-diagnostic' --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D2
    description: Diagnostic manifests are bounds-checked before allocation and copied transactionally; rejected replacement preserves image digest and continuation.
    requirement: API-02
    verification:
      - kind: integration
        ref: "ctest --preset sdk-debug -L sdk-media --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D3
    description: All 11 injected allocation failures across create, first load and replacement recover; all three first-success boundaries pass, with 14 positions and 476 counted assertions.
    requirement: API-04
    verification:
      - kind: integration
        ref: "ctest --preset sdk-debug -L sdk-faults --output-on-failure --no-tests=error"
        status: pass
      - kind: other
        ref: "ctest --preset sdk-debug -L 'sdk-lifecycle|sdk-media|sdk-diagnostic|sdk-capabilities' --output-on-failure --no-tests=error; public archive has no gn_test_ symbols"
        status: pass
    human_judgment: false
  - id: D4
    description: Ownership guide documents lifecycle, source lifetime, fixed manifest, errors and reproducible private failure checks; this is plan-level evidence toward DOC-01.
    requirement: DOC-01
    verification:
      - kind: other
        ref: "docs/ownership-and-errors.md inspected against the public API and passing lifecycle, media and fault suites"
        status: pass
    human_judgment: true
    rationale: "The phase-level DOC-01 obligation also covers its compiled getting-started example and complete shipped-artifact walkthrough; this plan closes the ownership/error guide portion only."
  - id: D5
    description: Counted lifecycle, malformed-media and allocation-failure cases add boundary and recovery evidence toward EVID-02.
    requirement: EVID-02
    verification:
      - kind: integration
        ref: "ctest --preset sdk-debug -L 'sdk-lifecycle|sdk-media|sdk-faults' --output-on-failure --no-tests=error"
        status: pass
    human_judgment: true
    rationale: "This plan's lifecycle, boundary and allocation coverage does not complete the phase-level fuzzing and supported sanitizer evidence in EVID-02."

duration: 24min
completed: 2026-10-05
status: complete
---

# Phase 02 Plan 02: Copied Media and Failure Recovery Summary

**The diagnostic SDK now validates and owns copied media transactionally, reports lifecycle errors, and recovers across every tested allocation failure.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-10-06T00:23:07Z
- **Completed:** 2026-10-06T00:47:07Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added exact lifecycle error behavior, idempotent reset/unload, reusable unloaded handles, and checks that the runtime has no ambient host-service dependency.
- Validated the fixed ROM/RAM manifest with checked bounds and arithmetic before allocation; copied immutable ROM and RAM seed, kept live RAM separate, and preserved a loaded image when replacement fails.
- Swept 14 allocation positions: 11 injected failures and 3 first-success boundaries across instance creation, first load and replacement. The focused fault suite passed with 3 cases and 476 counted assertions; each failure retained or restored allocation counts and permitted recovery.
- Documented caller ownership, media lifetime, lifecycle statuses, supported manifest, errors and commands for reproducing lifecycle and private failpoint checks.

## Task Commits

Each task was committed atomically:

1. **Task 1: Make lifecycle misuse and repeat operations safe** — `da3195b` (`feat`)
2. **Task 2: Validate and commit media without corrupting the live image** — `155f209` (`fix`)
3. **Task 3: Prove every allocation failure cleans up and permits recovery** — `5dc56d6` (`test`)

The GSD plan metadata commit records this summary and the state/roadmap/requirements updates.

## Files Created/Modified

- `src/instance.c` — Lifecycle statuses, checked media transaction, retained seed, per-instance allocator and failure cleanup.
- `src/sdk_private.h` — Test-only allocator and digest seam, guarded by `GLUEYNEO_SDK_TEST_HOOKS`.
- `tests/sdk/test_sdk.c` — Counted lifecycle, media boundary, transaction and allocation-failure cases.
- `tests/sdk/test_support.h` — Shared counted assertion/test-result harness.
- `docs/ownership-and-errors.md` — Caller ownership, lifecycle, media and recovery contract.
- `CMakeLists.txt` — Separate private test SDK, focused suites and runtime source/symbol closure checks.

## Decisions Made

- Kept private allocation callbacks and complete test digests out of the installed API and public runtime target.
- The accepted diagnostic profile contains fixed ROM/RAM permissions; the manifest has no permission field to validate.
- Allocation sweeps stop after the first failure in a candidate path, verify cleanup, and advance to the next injected position.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added the private test seam with the media transaction work**
- **Found during:** Task 2 (Validate and commit media without corrupting the live image)
- **Issue:** Full-image digest and adjacent/overlap-layout evidence needed a private structural test seam before the later allocator task introduced `src/sdk_private.h`.
- **Fix:** Added the guarded private header and a separate `glueyneo_test` target while implementing media validation; test hooks remain absent from the public target and installed headers.
- **Files modified:** `src/sdk_private.h`, `src/instance.c`, `tests/sdk/test_sdk.c`, `CMakeLists.txt`
- **Verification:** `sdk-media` passed; public archive symbol inspection found no `gn_test_` symbols; host-closure checks passed.
- **Committed in:** `155f209`

**2. [Rule 1 - Bug] Short-circuited candidate allocation after the first failure**
- **Found during:** Task 3 (Prove every allocation failure cleans up and permits recovery)
- **Issue:** The failpoint sweep exposed later allocation attempts after an earlier candidate allocation had failed.
- **Fix:** Made candidate allocation sequential and stop at the first failed allocation, then clean up and return the documented error.
- **Files modified:** `src/instance.c`, `tests/sdk/test_sdk.c`
- **Verification:** The focused `sdk-faults` suite swept all 14 positions and passed; failed candidates retained no extra live allocations and replacement preserved the previous guest state.
- **Committed in:** `5dc56d6`

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both changes support the plan's required digest and exhaustive failure guarantees; public API scope did not expand.

## Issues Encountered

- None beyond the allocation-order defect recorded above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-02 is complete; the phase remains in progress. The next dependency-ordered plan is 02-03, after review of this closeout.
- API-01, API-02 and API-04 are ready for completion tracking. EVID-02 and DOC-01 remain phase-level obligations because broader fuzz/sanitizer and compiled-example coverage is still outstanding.
- The fixed diagnostic manifest and private test seam do not claim broader cartridge, snapshot, or public ABI compatibility.

## Known Stubs

None found in the files changed by this plan; the placeholder/TODO/FIXME scan returned no matches.

## Threat Flags

None. The private failpoint seam is compiled only into the test target; no new public trust boundary or host-service surface was introduced.

## Self-Check: PASSED

- Summary file exists and the GSD coverage classifier reports no schema errors.
- All three task commits are present in Git history.
- The persisted plan ledger measures 3 commits from `30cbcac7299386cfc490cd576e9fbc55f5087f81` through `5dc56d68acc7fbdf2f4ff6c2aeda420d63f2d194`.

---
*Phase: 02-executable-diagnostic-sdk*
*Completed: 2026-10-05*
