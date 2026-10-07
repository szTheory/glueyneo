---
phase: 03-distributable-release-qualification
plan: 04
subsystem: release
tags: [github-actions, release-please, sdk, artifact-integrity]
requires:
  - phase: 03-03
    provides: Versioned source and platform SDK archive production and consumer checks
provides:
  - Fail-closed draft recovery and exact staged asset inventory validation
  - Serialized release workflow gated on downloaded archive bytes and consumer checks
  - Narrow local workflow evidence with hosted publication explicitly pending
affects: [release, delivery, sdk]
actuals:
  tokens: 17167
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns: [read-only GitHub release API validation, exact-byte download verification, draft-only staging]
key-files:
  created: [.github/workflows/release.yml, release-please-config.json, docs/releasing.md, tools/release_state.py, tests/workflow/test_release_recovery.py]
  modified: [tools/release_manifest.py, tools/public_content.py, tools/verify_sdk.py, tests/consumers/test_release_consumer.py]
key-decisions:
  - "Every retry queries the tag and only resumes exact already-uploaded bytes; it never replaces an existing asset."
  - "Publication requires all expected downloaded assets to match the staged manifest and pass platform consumer and public-content gates."
  - "Hosted token/event/publication claims remain pending until the workflow runs with configured repository authority."
patterns-established:
  - "Separate stage and publish jobs; publication re-queries the draft after all downloaded-byte gates pass."
  - "Cross-platform consumers exercise the downloaded SDK archive for their own runner platform."
requirements-completed: []
coverage:
  - id: D1
    description: Exact draft identity and asset recovery rejects stale, altered, duplicate, unexpected, and already-published states.
    verification:
      - kind: unit
        ref: tests/workflow/test_release_recovery.py
        status: pass
    human_judgment: false
  - id: D2
    description: Downloaded package bytes are checked against a staged trusted manifest before an offline rebuild and relocated SDK consumer run.
    verification:
      - kind: integration
        ref: tests/consumers/test_release_consumer.py
        status: pass
    human_judgment: false
  - id: D3
    description: Trusted publication stays behind exact-commit staging, three platform download/consumer jobs, and Linux public-content and rights gates.
    verification:
      - kind: other
        ref: actionlint .github/workflows/release.yml
        status: pass
    human_judgment: true
    rationale: The repository remote and release App authority are not configured, so actual hosted token, event, runner, and publication behavior has not been observed.
duration: 22min
completed: 2026-10-06
status: complete
plan_head_before: bc799f42e50cdf30795d01d050504ea637467ed0
plan_head_after: 5f106d89d56e987d3aa2232a3060c8f1bfc62e47
---

# Phase 03 Plan 04: Serialized release recovery and byte verification Summary

**Serialized draft recovery now validates exact release identity and assets, with publication blocked until downloaded bytes pass cross-platform consumer and content gates.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-10-06T17:57:45Z (state timestamp at dispatch; approximate)
- **Completed:** 2026-10-06T18:19:29Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Added read-only GitHub draft lookup and validation of the tested commit, root version, tag, exact filenames, byte sizes, and SHA-256 values. Empty or partial uploads are resumable only when every existing asset matches; no code path replaces uploaded bytes.
- Added a serialized GitHub release workflow that creates or recovers a draft, builds the exact versioned commit across Linux, macOS, and Windows, downloads the staged release into clean jobs, checks every expected package and manifest digest, rebuilds source offline, and runs the downloaded platform SDK consumer.
- Kept draft publication behind the Linux content and rights gate and successful downloaded-byte consumer jobs on all three platforms. The focused recovery suite is integrated into the SDK verifier. Local source/archive and scanner tests pass; hosted execution remains unqualified.

## Task Commits

Each task was committed atomically:

1. **Task 1: Validate and recover an exact draft release** - `db24fc8` (feat)
2. **Task 2: Verify downloaded bytes before trusted publication** - `5f106d8` (feat)

**Plan metadata:** pending final metadata commit.

## Files Created/Modified

- `.github/workflows/release.yml` - Serialized release control, matrix builds, draft staging, downloaded-byte verification, and gated publication.
- `release-please-config.json` - Pinned v17.3.0 schema and draft manifest-mode configuration.
- `docs/releasing.md` - Retry, byte identity, publication gates, and hosted qualification boundaries.
- `tools/release_state.py` - Read-only draft query, exact asset validation, and downloaded-file digest validation.
- `tools/release_manifest.py` - Platform archive naming, canonical release identity manifest, source archive inclusion, and Windows Release configuration.
- `tools/public_content.py` - Includes release-state source in its synchronized source archive scan allowlist.
- `tools/verify_sdk.py` - Adds `release-recovery` selector and aggregate integration.
- `tests/workflow/test_release_recovery.py` - Adversarial draft-state, retry, manifest, and workflow structure controls.
- `tests/consumers/test_release_consumer.py` - Exact downloaded byte controls and offline archive rebuild/relocated consumer workflow.

## Decisions Made

- Always query the existing tag even when release-please reports no new release. Treat its boolean output as a trigger signal, never as proof of identity or publishability.
- Compare every existing draft asset against the deterministic staged name/size/digest inventory before resuming. Publish only when the draft is complete and freshly revalidated.
- Do not mark hosting requirements complete without a configured remote/App and an observed hosted run.

## Deviations from Plan

### Correctness adjustments

**1. Synchronized the new release-state module with both source archive and public-content allowlists.**
- **Found during:** Task 2
- **Issue:** The release workflow source archive contains the validator, but the repository source scan policy initially did not include that new source path.
- **Fix:** Added the validator path to both inventories and retained the equality regression.
- **Files modified:** `tools/release_manifest.py`, `tools/public_content.py`
- **Verification:** `tests/workflow/test_public_content.py` passes 9/9.
- **Committed in:** `5f106d8`

**2. Selected the Release configuration for Windows multi-config CMake builds.**
- **Found during:** Task 2
- **Issue:** The Windows runner's Visual Studio generator needs an explicit configuration when building/installing package archives.
- **Fix:** Pass `--config Release` to the archive build/install path.
- **Files modified:** `tools/release_manifest.py`
- **Verification:** Full local release consumer suite passes 5/5; hosted Windows behavior is still pending.
- **Committed in:** `5f106d8`

**Total deviations:** 2 correctness adjustments. Both were needed to keep archive/scanner scope aligned and support the planned Windows archive build.

## Verification

- `python3 tests/workflow/test_release_recovery.py` - 10/10 passed.
- `python3 tools/verify_sdk.py --suite release-recovery` - pass, 10 cases and 10 assertions.
- `python3 tests/consumers/test_release_consumer.py` - 5/5 passed, including offline source archive rebuild and relocated static/shared SDK consumers.
- `python3 tests/workflow/test_public_content.py` - 9/9 passed.
- `actionlint .github/workflows/release.yml` - passed.
- `python3 -m py_compile` for the changed Python sources/tests and `git diff --check` - passed.
- Hosted release-please event behavior, GitHub App token authority, hosted platform runners, real draft download, and publication were not run because no repository remote or App credentials are configured.

## Issues Encountered

- The first recovery suite run exposed the not-yet-created module during TDD red phase; the completed validator and focused suite now pass. No unresolved local test failures remain.

## User Setup Required

Repository/App setup is needed before hosted qualification: configure the narrowly scoped release GitHub App credentials and run the workflow against the repository. Local artifact and consumer behavior is qualified by the checks above; no hosted behavior is claimed.

## Next Phase Readiness

- Plan 03-04 local implementation and verification are complete. Delivery requirements remain pending until actual hosted execution and publication evidence exist.
- Phase 03 Plan 03-05 is the next named plan; do not advance until the user continues the GSD workflow.

## Self-Check: PASSED

- Summary file exists and both task commits are ancestors of the current plan head.
- Actual task-commit count measured from the plan ledger is 2.

---
*Phase: 03-distributable-release-qualification*
*Completed: 2026-10-06*
