---
phase: 05-selected-mvs-boot
plan: 01
subsystem: media
tags: [c17, zip32, zlib-1.3.2, mvs, libretro, qualification]
requires:
  - phase: 04-public-fixture
    provides: additive native instance API and synthetic Libretro callback baseline
provides:
  - Versioned MVS region contract with transactional owned copies
  - Standalone bounded ZIP32 importer and normalized GNMV bundle
  - Synthetic importer-to-native-guest-to-Libretro tracer and evidence map
affects: [first-playable-game-phase-05, mvs-media, native-api, libretro]
actuals:
  tokens: 248002
  tasks: 3
  commits: 3
tech-stack:
  added: [vendored zlib 1.3.2 inflater subset]
  patterns: [isolated host-side importer, role-tagged immutable regions, transactional instance replacement]
key-files:
  created:
    - tools/mvs/mvs_import.c
    - tools/mvs/mvs_qualify.c
    - tools/mvs/qualify_local_boot.py
    - tests/mvs/test_mvs.c
    - tests/mvs/test_mvs_qualification.py
    - tests/mvs/fuzz_import.c
    - docs/mvs-media.md
  modified:
    - include/glueyneo/glueyneo.h
    - src/instance.c
    - src/mvs/mvs_bus.c
    - src/libretro/libretro_core.c
    - CMakeLists.txt
    - .planning/workstreams/first-playable-game/REQUIREMENTS.md
key-decisions:
  - "Keep ZIP parsing in a standalone C17 tool and use only the pinned minimal zlib 1.3.2 inflate/CRC source set; core and Libretro remain archive-decoder-free."
  - "Normalize the program ROM word swap in the importer after validating source CRC, then pass GNMV regions to the native API as linear bus-order spans."
  - "Treat the profile as structural until selected game and BIOS identities are verified; leave MEDIA-04 pending."
  - "Do not infer selected title boot or frontend behavior from synthetic guest and callback tests."
requirements-completed: [MEDIA-02]
coverage:
  - id: D1
    description: "C integrators can load the documented MSX-shaped MVS region contract with bounded immutable owned regions."
    requirement: MEDIA-02
    verification:
      - kind: integration
        ref: "ctest --preset sdk-debug -R '^(mvs_synthetic_trace|mvs_media_contract)$' --output-on-failure"
        status: pass
    human_judgment: false
  - id: D2
    description: "Bounded canonical ZIP32 role archives can normalize into GNMV and run the synthetic guest sentinel."
    verification:
      - kind: integration
        ref: "ctest --preset sdk-debug -R '^(mvs_import_contract|mvs_import_mutation|mvs_boot_checkpoint|mvs_import_fuzz_corpus)$' --output-on-failure"
        status: pass
    human_judgment: false
  - id: D3
    description: "Selected local game and BIOS import, selected title boot, and pinned RetroArch behavior are qualified."
    verification: []
    human_judgment: true
    rationale: "Local qualification stopped before native load because no input matched the canonical role-bundle contract; selected identity, title execution, and direct frontend observation remain unknown."
duration: 20min
completed: 2026-10-09
status: complete
commits: 3
plan_head_before: 9fc03e37eaf87abdb988a84daad5d518c7473cc0
plan_head_after: 975f0d7bded5c1e6c44c548a5e12e85c1bb5cad9
---

# Phase 05 Plan 01: Selected MVS Media and Boot Summary

**A bounded C17 ZIP32-to-GNMV path now drives a synthetic MVS guest through the native API and Libretro callback seam, while selected media compatibility and title boot remain open.**

## Performance

- **Duration:** 20 minutes
- **Started:** 2026-10-09T02:40:41Z
- **Completed:** 2026-10-09T03:00:19Z
- **Tasks:** 3
- **Files modified:** 34, including the pinned zlib source subset

## Accomplishments

- Added a separate versioned MVS media API with exact region-size checks, explicit linear/word-swapped layouts, per-instance bus state, copied ownership, and transactional replacement.
- Added an isolated standalone ZIP32 importer with bounded spans and resource limits, stored/raw-DEFLATE support, CRC and exact-size checks, safe diagnostics, and pinned zlib 1.3.2 inflater/CRC sources. The native runtime and Libretro adapter do not parse ZIP.
- Added synthetic archive, malformed-input, local-extra-field, EOCD-comment-decoy, allocation-failure, recovery, callback reload, guest-sentinel, and bounded mutation-corpus checks.
- Added a private local qualification command and evidence map. The run reported `no_supported_role_bundle_archive` at `archive_to_region_mapping`; no private identity was emitted and no selected guest ran.
- Preserved Phase 04 `gaps_found`, HOST-02/frontend QUAL-03 unknown/manual-only status, and its seven open threat rows.

## Task Commits

1. **Task 1: Trace one synthetic MVS bundle from ZIP import through guest execution** — `ca040e9` (`feat`)
2. **Task 2: Close importer, profile, callback, and recovery boundaries** — `a141dbb` (`feat`)
3. **Task 3: Implement evidence-led title boot dependencies and close the phase evidence map** — `975f0d7` (`feat`)

**Plan metadata:** GSD advanced the current pointer and updated roadmap counts; state-position output needs reconciliation because a Phase 04 milestone lock remained active.

## Files Created/Modified

- `include/glueyneo/glueyneo.h`, `src/instance.c`, and `src/mvs/mvs_bus.c` — additive MVS contract, ownership, validation, and guest bus.
- `tools/mvs/mvs_import.c` and `third_party/zlib/` — bounded host-side ZIP32 normalization using the pinned inflater subset.
- `src/libretro/libretro_core.c` — normalized GNMV content path without ZIP handling.
- `tests/mvs/` and `CMakeLists.txt` — synthetic end-to-end, mutation, callback, package, and sanitizer coverage.
- `tools/mvs/qualify_local_boot.py`, `tools/mvs/mvs_qualify.c`, and `docs/mvs-media.md` — ignored local qualification path and evidence boundaries.
- `05-VALIDATION.md`, `05-REVIEW.md`, and the workstream `REQUIREMENTS.md` — current requirement status, review disposition, and evidence traceability.

## Decisions Made

- The normalized GNMV contract is structural. It checks role names and profile sizes but does not authenticate selected cartridge or BIOS content; no selected-media compatibility claim is made.
- MEDIA-02 is complete for the documented structural C contract. MEDIA-03, MEDIA-04, and GAME-02 remain Pending because direct import/load, selected-content identity, and selected title boot have not been established.
- A synthetic sentinel and fake Libretro callbacks prove only the synthetic path. The actual pinned RetroArch flow remains manual-only/unknown.
- The importer validates archive CRC over original program bytes before normalizing the program word swap into bus order.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Validate local ZIP extra-field bounds before parsing**
- **Found during:** Task 2 review
- **Issue:** An untrusted local extra-field length could be read before its full span was proven in-bounds.
- **Fix:** Validate the complete local name-plus-extra span first and add an oversized local-extra mutation regression.
- **Files modified:** `tools/mvs/mvs_import.c`, `tests/mvs/test_mvs_qualification.py`
- **Verification:** Debug and ASan/UBSan importer mutation suites passed.
- **Committed in:** `a141dbb` / follow-up regression in `975f0d7`

**2. [Rule 1 - Bug] Validate complete EOCD candidates and normalize the importer transform**
- **Found during:** Task 2 independent review
- **Issue:** A comment-contained EOCD-shaped sequence could hide a valid archive; the test path also did not prove that importer output and API layout agreed.
- **Fix:** Parse every end-of-file candidate fully and accept exactly one valid directory; normalize program word lanes after CRC verification and test the resulting bus-order bytes through the native API.
- **Files modified:** `tools/mvs/mvs_import.c`, `tests/mvs/test_mvs.c`, `tests/mvs/test_mvs_qualification.py`
- **Verification:** Decoy EOCD regression, MVS tests, and independent re-review passed.
- **Committed in:** `975f0d7`

**3. [Rule 3 - Blocking] Update installed-package self-check for the private zlib source and additive exports**
- **Found during:** Full CTest
- **Issue:** Documentation staging omitted the new vendored zlib source tree, and shared-export expectations did not include the two new public MVS entry points.
- **Fix:** Stage the zlib source in the offline documentation-build fixture and update the public shared export allowlist.
- **Files modified:** `tests/consumers/check_package.py`
- **Verification:** Full static/shared build, consumer, and docs CTests passed.
- **Committed in:** `975f0d7`

**Total deviations:** 3 auto-fixed (2 Rule 1, 1 Rule 3). All were required for parser safety or verification correctness.

## Issues Encountered

- The local qualification input did not include an archive matching the normalized six-region bundle contract. The run stopped before native loading, so no selected guest instruction/opcode can truthfully be reported. The first concrete blocker is archive-to-region mapping; the next dependency is to map the supported game and BIOS archives to the normalized MVS region contract.
- The independent review’s selected-content identity blocker remains open by design. The docs and requirement status make that limitation explicit.
- The first complete CTest pass exposed package-test harness integration gaps; the scoped harness fixes resolved them and the subsequent full suite passed.
- The GSD state updater reported an active Phase 04 milestone lock while advancing Phase 05. It wrote the Phase 05 frontmatter pointer and roadmap count, but its state prose/progress summary remains internally inconsistent; a concurrent phase-position write was avoided.

## User Setup Required

None. Local private media remains optional and ignored.

## Next Phase Readiness

The structural media contract, ZIP32 parser, synthetic guest tracer, native recovery, and adapter callback seams are ready for verification. Phase 05 itself is **not complete**: MEDIA-03, MEDIA-04, and GAME-02 remain Pending, and selected identity/title execution are unobserved. The next technical work is to map supported game and BIOS archives into the normalized MVS regions, then qualify that path; no RetroArch retry is needed until a materially changed functioning launch context exists.

## Self-Check: PASSED

All listed implementation/evidence files exist, and task commits `ca040e9`, `a141dbb`, and `975f0d7` are ancestors of the current plan head.

---
*Phase: 05-selected-mvs-boot*
*Completed: 2026-10-09*
