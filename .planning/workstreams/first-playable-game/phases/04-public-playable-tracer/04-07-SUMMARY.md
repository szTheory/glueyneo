---
phase: 04-public-playable-tracer
plan: 07
subsystem: build-qualification
tags: [Python, CMake, Git archive, source identity, qualification]

# Dependency graph
requires:
  - phase: 04-public-playable-tracer
    provides: public GNFX fixture, native/Libretro consumers, pinned chip candidates, and clean qualification runner
provides:
  - immutable full-commit source snapshot for qualification
  - complete path, mode, symlink-target, and content receipt inventory
  - snapshot-only source routing with fail-closed mutation checks
  - documented source identity contract and focused rejection controls
affects: [QUAL-03, TRAC-01, HOST-02]

# Actuals
actuals:
  tokens: 16432
  tasks: 2
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns: [bounded local Git archive, canonical complete-tree inventory, external generated-output overlay]

key-files:
  created: []
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - docs/first-playable-build.md

key-decisions:
  - "Qualification consumes one complete immutable Git commit archive; checkout dirt and untracked files are excluded."
  - "Record every file mode and symlink target in the aggregate inventory, then recheck snapshot integrity around source-consuming commands."
  - "Keep generated outputs outside the archived source tree and sanitize inherited build/toolchain injection variables."

patterns-established:
  - "Snapshot receipt rows use sorted repository-relative paths, exact content identities, executable mode, and safe relative symlink targets."
  - "Missing, stale, reordered, unsafe, or changed inventory data fails with a named reason."

requirements-completed: []

coverage:
  - id: D1
    description: "Qualification source identity is bound to a full Git commit and a complete fail-closed tree inventory."
    requirement: QUAL-03
    verification:
      - kind: integration
        ref: "tests/tools/test_verify_playable.py#SnapshotTest (10 focused tests); archived CMake fixture build"
        status: pass
    human_judgment: false
  - id: D2
    description: "The qualification guide explains snapshot inputs, receipt fields, and historical frontend evidence."
    verification:
      - kind: unit
        ref: "tools.verify_playable.check_docs(ROOT)"
        status: pass
    human_judgment: false

# Metrics
duration: 13min
completed: 2026-10-07
status: complete
---

# Phase 04 Plan 07: Complete Source Snapshot Summary

**The qualification runner now binds every source-consuming lane to a complete immutable Git snapshot and records a verifiable inventory in its receipt.**

## Performance

- **Duration:** 13 minutes
- **Started:** 2026-10-07T23:49:00Z
- **Completed:** 2026-10-08T00:01:45Z
- **Tasks:** 2
- **Files modified:** 4, including this summary

## Accomplishments

- Materialized qualification sources from one full commit using a bounded local `git archive`, compared its complete tree to Git's commit tree, and rejected unsafe paths, links, submodules, omissions, and ambiguous names.
- Bound runner, build inputs, fixture/vendor/test sources, installed artifacts, and candidate reports to the snapshot identity; recorded every archived file and symlink in the receipt and checked for mutation around source-consuming commands.
- Added isolated controls proving dirty and untracked checkout inputs do not affect the real CMake fixture build, changed committed inputs change the inventory digest, and missing or stale receipt rows are rejected.
- Documented how qualification uses the commit snapshot, where generated outputs live, which environment inputs are removed, and why prior frontend observations are historical until the final run.

## Task Commits

1. **Task 1: Bind one real fixture build and receipt to a complete Git snapshot** — `250a645` (test), `ad635df` (feat)
2. **Task 2: Apply snapshot identity to every qualification lane and explain the receipt** — `a8c7286` (test), `36df674` (feat)

## Files Modified

- `tools/verify_playable.py` — immutable snapshot creation, complete receipt validation, sanitized snapshot-root execution, and integrity checks.
- `tests/tools/test_verify_playable.py` — positive CMake fixture build and negative controls for checkout injection, mutation, unsafe links, stale receipts, and environment injection.
- `docs/first-playable-build.md` — committed-source contract, receipt inventory fields, and historical qualification boundary.
- `04-07-SUMMARY.md` — plan execution record.

## Decisions Made

- The full committed tree is the sole qualification source. A broad worktree-clean gate is unnecessary because no dirty or untracked checkout data enters the archive.
- The receipt preserves exact executable bits and relative symlink targets as part of source identity, rather than hashing regular file bytes alone.
- Generated build and install outputs remain outside the source archive. A temporary `build` overlay is used only for the existing YM2610 gate's fixed output convention, then removed before snapshot validation.

## Deviations from Plan

The existing YM2610 candidate script writes beneath `ROOT/build`. The runner temporarily maps that location to an ignored output directory outside the source snapshot, removes the mapping after the command, and verifies the snapshot afterward. A focused test checks the overlay lifecycle. This preserves the existing gate without changing the candidate script or admitting generated files into source identity.

**Total deviations:** 1 implementation adaptation.  
**Impact on plan:** All qualification source inputs remain snapshot-bound and all generated outputs remain outside the archived tree.

## Issues Encountered

- The existing runner's fixed `ROOT/build` output assumption required the temporary external overlay described above. The adaptation passed its dedicated test.
- The complete qualification receipt was not regenerated in this plan; Plan 04-08 performs the single final clean run after frontend diagnosis and commits.

## Next Phase Readiness

Plan 04-07 is complete. Phase 04 remains unverified: Plan 04-08 must diagnose the pinned RetroArch exit, preserve `HOST-02` as unknown unless fresh screenshots and input controls are observed, then run the final clean qualification once from committed source.

## Self-Check: PASSED

- All 10 focused snapshot tests pass, including an actual isolated CMake build of the public fixture.
- Python compilation, `git diff --check`, and the qualification documentation contract check pass.
- Task commits `250a645`, `ad635df`, `a8c7286`, and `36df674` are ancestors of HEAD.
- No plan or phase completion status was advanced by this summary.

---
*Phase: 04-public-playable-tracer*
*Completed: 2026-10-07*
