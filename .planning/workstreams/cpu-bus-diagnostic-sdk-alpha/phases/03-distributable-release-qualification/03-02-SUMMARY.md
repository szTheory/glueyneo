---
phase: 03-distributable-release-qualification
plan: 02
subsystem: release-hygiene
tags: [public-content, privacy, rights-inventory, archive, python]
requires:
  - phase: 03-distributable-release-qualification
    provides: deterministic source and SDK archives from Plan 03-01
provides:
  - Bounded standard-library scanner for public source, reachable history, supplied logs, and release archives.
  - Redacted privacy findings, archive path/type/size/count rejection, and explicit detector limits.
  - Item-level fixture and Unity rights inventory checked against exact bytes and notices.
affects: [03-distributable-release-qualification, ci, release-packaging]
actuals:
  tokens: 10519
  tasks: 2
  commits: 4
plan_head_before: c040fd2a53ae3eefa64e1225d79b74e6552ae6c3
plan_head_after: 9ad0f0d108cce2672b3c6f0c9c792e05e2b557c3
tech-stack:
  added: []
  patterns: [stdlib-only release scanning, deterministic redacted rule findings, digest-bound item-level rights records]
key-files:
  created: [tools/public_content.py, tests/workflow/test_public_content.py, docs/public-content.md, docs/rights-inventory.md]
  modified: []
key-decisions:
  - "Scan exactly the source path set used by tools/release_manifest.py, with a regression test to keep both policies aligned."
  - "Treat a negative scan as detector coverage only; rights records remain a separate affirmative gate."
  - "Keep hosted CI log, secret-scanning, and publication evidence pending until captured against the configured repository."
patterns-established:
  - "Emit stable rule IDs and repository-relative locations without matched values."
  - "Validate archive members and limits before reading their bodies; never extract during scanning."
requirements-completed: []
coverage:
  - id: D1
    description: Scan bounded public source, commit metadata, logs and release archives with redacted findings and explicit detector limits.
    requirement: DEL-05
    verification:
      - kind: unit
        ref: python3 tests/workflow/test_public_content.py (9 tests)
        status: pass
      - kind: integration
        ref: python3 tools/public_content.py with generated source and Darwin arm64 SDK archives at 9ad0f0d
        status: pass
      - kind: integration
        ref: local CTest log scan (21 logs; findings limited to personal-path)
        status: unknown
    human_judgment: true
    rationale: No captured hosted CI logs or hosted secret-scanning configuration are available; the scanned local CTest logs are private build outputs and trigger the path detector.
  - id: D2
    description: Bind every included fixture and Unity dependency path to affirmative rights, immutable provenance, digest, and notice evidence.
    requirement: DEL-05
    verification:
      - kind: unit
        ref: python3 tests/workflow/test_public_content.py#rights inventory and archive controls
        status: pass
      - kind: integration
        ref: source archive rights scan at 9ad0f0d (13 inventory entries)
        status: pass
    human_judgment: false
duration: 13min
completed: 2026-10-06
status: complete
---

# Phase 03 Plan 02: Public Content and Rights Gate Summary

**A standard-library scanner checks release source, history and archives with redacted findings, while a 13-item digest inventory keeps unknown or changed fixtures and dependencies out.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-10-06T17:11:00Z (approximate; executor start was not separately timestamped)
- **Completed:** 2026-10-06T17:24:04Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Implemented deterministic scanning for the exact source paths selected by `tools/release_manifest.py`, reachable Git commit metadata, optional bounded logs, and every supplied release archive. Findings include rule IDs and safe relative locations without matched values.
- Rejected unreadable, linked, special, absolute/traversing, duplicate, over-count, and over-size inputs before archive extraction; reported scanned byte/file denominators and stated the detector's limits.
- Added an item-level rights inventory for the original MIT diagnostic fixture assets and Unity at immutable upstream commit `b6763fbd9cedfacaa89e2ad9fd00d615a234e355`; exact path/digest, affirmative rights, provenance, and notice checks reject additions and mutations.
- Built source and Darwin arm64 SDK archives at exact commit `9ad0f0d108cce2672b3c6f0c9c792e05e2b557c3`; both archives scanned without findings, and all 13 source fixture/dependency inventory entries passed.

## Task Commits

1. **Task 1: Scan proposed public bytes with bounded redacted findings** - `916a60a` (scanner, adversarial tests, and shared rights gate) plus `2abc283` and `9ad0f0d` (scanner self-canary and path-policy regressions).
2. **Task 2: Gate shipped fixtures and dependencies on rights records** - `916a60a` (rights enforcement and inventory) plus `e75a5db` (scanner/rights documentation).

The implementation and rights controls share `tools/public_content.py` and its mutation suite, so their initial implementation landed together. The plan produced four commits before its summary metadata commit.

## Files Created/Modified

- `tools/public_content.py` - Bounded source, history, log, archive, and rights inventory scanner.
- `tests/workflow/test_public_content.py` - Nine canary, adversarial archive, limit, rights, coverage, and source-path parity tests.
- `docs/public-content.md` - Scanner interface, bounds, detector coverage/limits, and pending hosted evidence.
- `docs/rights-inventory.md` - Canonical item-level JSON records, provenance, notices, exclusions, and unknown rights policy.

## Verification and Evidence

- RED/GREEN: The scanner canary tests first failed against the unimplemented API. The rights controls then failed for missing archive inventory/notice enforcement. The final suite passed 9/9 with no skipped cases.
- `python3 -m py_compile tools/public_content.py tests/workflow/test_public_content.py` passed.
- Final source tree scan: 90 files, 2,037,374 bytes; all reachable history metadata: 56,773 bytes; 13/13 rights records passed. No findings were emitted.
- Exact 0.1.0 source and Darwin arm64 SDK archives: 115 files, 2,205,899 uncompressed bytes combined. Both archive scans passed with no findings; the source archive carried all required notices and inventory items.
- Combined local scan with actual archived artifacts and local CTest logs: 21 logs, 36,321,383 bytes, and 21 redacted `personal-path` findings. These are ignored private build outputs, not publishable CI logs; if supplied to a publication scan, they correctly fail.
- No CI-captured log set, remote repository, hosted secret-scanning enablement, or published/downloaded artifact evidence was available. Consequently, DEL-05 remains pending until the required hosted/publication evidence is captured and scanner findings for proposed bytes are cleared.

## Decisions Made

- The scanner source inventory is tested against the existing release archive path policy to prevent scope drift.
- GitHub noreply identities and reserved synthetic test domains are treated as non-private examples; canaries are assembled from fragments so they do not contaminate the public source scan.
- The content detector and rights gate remain separate: a negative pattern scan never creates a redistribution permission.

## Deviations from Plan

**1. [Rule 1 - Bug] Excluded synthetic canary text from public-source findings without weakening canary detection**
- **Found during:** Task 1 full proposed-source scan.
- **Issue:** Static canary literals in the new tests were correctly detected when scanning the public test sources.
- **Fix:** Constructed canary values at runtime from fragments and allowed only reserved example domains and the configured GitHub noreply domain.
- **Files modified:** `tools/public_content.py`, `tests/workflow/test_public_content.py`.
- **Verification:** The full source scan returned no findings; 9/9 tests passed.
- **Committed in:** `2abc283` and `9ad0f0d`.

**Total deviations:** 1 auto-fixed (Rule 1).
**Impact on plan:** Required for the detector's own tests to be distributable while retaining positive canary coverage.

## Issues Encountered

- Local CTest logs contain machine-local path material. They remain excluded local build output and are not treated as captured CI evidence; the scanner's fail-closed result is retained rather than rewritten.
- The scanner is a local verification tool. A later CI/release workflow plan must invoke it on each proposed artifact and captured CI logs before publication.

## User Setup Required

None for local scans. Hosted CI log, repository secret-scanning, and publication evidence require the configured remote and its actual workflow runs.

## Next Phase Readiness

Plan 03-02 implementation is complete. DEL-05 remains pending for hosted log coverage, observed secret-scanning configuration, and published-artifact qualification. The next plan is 03-03, which adds the always-started CI aggregate and should run this scanner on applicable paths.

## Self-Check: PASSED

The summary exists, all four recorded task commits are ancestors of the current plan head, and the measured task-commit count is four.

---
*Phase: 03-distributable-release-qualification*
*Completed: 2026-10-06*
