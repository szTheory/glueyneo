---
status: diagnosed
phase: 05-selected-mvs-boot
source: [05-01-SUMMARY.md]
started: 2026-10-09T11:41:00Z
updated: 2026-10-09T12:05:48.223Z
---

## Current Test

[testing complete]

## Tests

### 1. Load the documented MVS region contract
expected: C integrators can load the documented MVS region contract with bounded immutable owned regions.
result: pass
source: automated
coverage_id: D1
requirement: MEDIA-02
evidence: |
  Current checkout d65dc2c: `ctest --preset sdk-debug -R '^(mvs_synthetic_trace|mvs_media_contract)$' --output-on-failure --no-tests=error` passed 2/2.
scope: Automated contract and synthetic integration coverage; no selected commercial media claim.

### 2. Normalize ZIP32 role archives and run the synthetic guest sentinel
expected: Bounded canonical ZIP32 role archives normalize into GNMV and run the synthetic guest sentinel.
result: pass
source: automated
coverage_id: D2
evidence: |
  Current checkout d65dc2c: `ctest --preset sdk-debug -R '^(mvs_import_contract|mvs_import_mutation|mvs_boot_checkpoint|mvs_import_fuzz_corpus)$' --output-on-failure --no-tests=error` passed 4/4.
scope: Synthetic importer, mutation, guest checkpoint, and bounded fuzz-corpus tests; not selected title compatibility.

### 3. Import selected game and BIOS and reach guest execution
expected: The supported selected game and BIOS archives map into GNMV, the native loader accepts them, and the selected guest reaches its attract/start checkpoint.
result: issue
reported: "Automated local qualification returned no_supported_role_bundle_archive at archive_to_region_mapping; no selected guest ran."
severity: major
evidence: |
  The current-revision local qualification recorded in 05-VALIDATION.md stopped before native loading. This is a concrete archive-to-region mapping gap; it does not establish a frontend failure or selected-game compatibility result.

### 4. Run the selected content through the pinned RetroArch smoke path
expected: An automated smoke launches the pinned RetroArch build with selected normalized media, observes a game frame and expected scripted input response, unloads content, exits normally, and records only generic private-safe outcomes.
result: blocked
blocked_by: other
reason: "The selected content did not reach native loading, so a frontend run cannot be exercised. Actual RetroArch behavior remains unknown."

### 5. Run the public MVS regression suite in current-revision CI
expected: The existing pull-request/main CI evidence matrix runs the public MVS region, importer, callback, guest-checkpoint, and bounded fuzz-corpus tests with a positive named-test denominator.
result: issue
reported: "The shared verify_sdk CI evidence inventory selects sdk-labeled CTest cases and omits the MVS-labeled tests, so Phase 05 regressions are not part of current CI receipts."
severity: major
evidence: |
  At current checkout d65dc2c, tools/verify_sdk.py defines no MVS CTest lane and its matrix suite enumerates only SDK labels. CMake registers the Phase 05 CTests under the mvs label, but the PR/main evidence collector does not select that label.

## Summary

total: 5
passed: 2
issues: 2
pending: 0
skipped: 0
blocked: 1

## Gaps

- gap_id: G-05-3
  truth: "The supported selected game and BIOS archives map into GNMV, the native loader accepts them, and the selected guest reaches its attract/start checkpoint."
  status: failed
  reason: "Automated local qualification returned no_supported_role_bundle_archive at archive_to_region_mapping; no selected guest ran."
  severity: major
  test: 3
  root_cause: "The local qualification wrapper passes each ZIP separately to an importer that accepts only one archive with six already-normalized canonical region members; it cannot combine the selected game's source ZIP and separate BIOS ZIP into GNMV."
  artifacts:
    - path: tools/mvs/qualify_local_boot.py
      issue: "Each ZIP is independently sent to the canonical-bundle importer; source archives are not mapped or combined."
    - path: tools/mvs/mvs_import.c
      issue: "Importer accepts canonical region member names and sizes, not the selected profile's source member/transform map across split archives."
    - path: docs/mvs-media.md
      issue: "Documents that unmodified game and separate BIOS archives are not yet directly supported."
  missing:
    - "A bounded selected-profile mapper for the supported game and BIOS source archives, with source identity checks and documented region transforms."
    - "Public synthetic split-archive integration and wrong-member/identity controls; keep real private archive data and derived identity local."
  debug_session: .planning/debug/phase05-selected-media-mapping.md
- gap_id: G-05-5
  truth: "The existing pull-request/main CI evidence matrix runs the public MVS regression suite with a positive named-test denominator."
  status: failed
  reason: "The shared verify_sdk CI evidence inventory does not select CTest tests under the mvs label."
  severity: major
  test: 5
  root_cause: "Phase 05 CTests are labeled mvs, but the current-SHA CI matrix collector has no mvs label/case inventory or collection step; the evidence source-digest inventory also omits MVS source paths."
  artifacts:
    - path: tools/verify_sdk.py
      issue: "The matrix CTest lane and required receipt inventory enumerate SDK labels only."
    - path: tools/sdk_evidence.py
      issue: "Relevant-source identity excludes the MVS importer, API and adapter code."
    - path: CMakeLists.txt
      issue: "Seven mvs-labeled tests exist but are not selected by the evidence collector."
  missing:
    - "An MVS lane in the existing matrix with exact named tests, a positive denominator, and current-revision receipt evidence."
    - "Relevant-source identity coverage for MVS code and regression tests that reject missing or stale lane evidence."
  debug_session: .planning/debug/phase05-mvs-ci-evidence.md
