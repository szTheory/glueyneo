---
status: partial
phase: 05-selected-mvs-boot
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md]
started: 2026-10-09T11:41:00Z
updated: 2026-10-09T23:14:22.913Z
---

## Current Test

[testing paused — 2 items outstanding]

## Tests

### 1. Load the documented MVS region contract
expected: C integrators can load the documented MVS region contract with bounded immutable owned regions.
result: pass
source: automated
coverage_id: D1
requirement: MEDIA-02
evidence: |
  Current checkout a236986: `ctest --preset sdk-debug -R '^(mvs_synthetic_trace|mvs_media_contract)$' --output-on-failure --no-tests=error` passed 2/2.
  Rechecked at current checkout 103a1e0: the seven-test `^mvs_` CTest lane passed 7/7; `mvs_media_contract` passed. This still establishes only the normalized contract, not selected private media.
scope: Automated contract and synthetic integration coverage; no selected commercial media claim.

### 2. Normalize ZIP32 role archives and run the synthetic guest sentinel
expected: Bounded canonical ZIP32 role archives normalize into GNMV and run the synthetic guest sentinel.
result: pass
source: automated
coverage_id: D2
evidence: |
  Current checkout a236986: `ctest --preset sdk-debug -R '^(mvs_import_contract|mvs_import_mutation|mvs_boot_checkpoint|mvs_import_fuzz_corpus)$' --output-on-failure --no-tests=error` passed 4/4.
  Rechecked at current checkout 103a1e0: the seven-test `^mvs_` CTest lane passed 7/7, including importer, mutation, checkpoint, and fuzz-corpus cases; `python3 tools/verify_sdk.py --suite matrix` passed 1,440 assertions across 43 cases and 10 lanes.
scope: Synthetic importer, mutation, guest checkpoint, and bounded fuzz-corpus tests; not selected title compatibility.

### 3. Import selected game and BIOS and reach guest execution
expected: The supported selected game and BIOS archives map into GNMV, the native loader accepts them, and the selected guest reaches its attract/start checkpoint.
result: issue
reported: "Automated local qualification returned no_supported_role_bundle_archive at archive_to_region_mapping; no selected guest ran."
severity: major
evidence: |
  Historical qualification recorded in 05-VALIDATION.md stopped before native loading. This did not establish a frontend failure or selected-game compatibility result.
  Latest assessment: 05-06-SUMMARY.md records that there is no independently observed selected configuration or sourced guest-written attract/start predicate. The bounded attempt did not produce an accepted checkpoint; GAME-02 remains open.

### 4. Run the selected content through the pinned RetroArch smoke path
expected: An automated smoke launches the pinned RetroArch build with selected normalized media, observes a game frame and expected scripted input response, unloads content, exits normally, and records only generic private-safe outcomes.
result: blocked
blocked_by: other
reason: "Plan 05-06 could not establish a sourced selected-guest checkpoint, and the pinned-app launch preconditions did not materially change. No selected-media app launch was attempted; actual RetroArch behavior remains unknown/manual-only."
automated_subcheck: |
  Current checkout 103a1e0: `python3 tests/libretro/test_retroarch_smoke.py -v` passed 31/31 structural and privacy tests. These do not exercise the pinned RetroArch app with selected media.

### 5. Run the public MVS regression suite in current-revision CI
expected: The existing pull-request/main CI evidence matrix runs the public MVS region, importer, callback, guest-checkpoint, and bounded fuzz-corpus tests with a positive named-test denominator.
historical_reported: "The shared verify_sdk CI evidence inventory selects sdk-labeled CTest cases and omits the MVS-labeled tests, so Phase 05 regressions are not part of current CI receipts."
evidence: |
  Historical evidence at checkout a236986 showed the collector omitted MVS-labeled CTests; Plan 05-02 repaired that local evidence-lane defect.
  Plan 05-06's public-safe PR #2 candidate `e80672845fc60d94d8a44eab416377534c9a99f1` passed hosted run `38001400110`: all seven named MVS tests, positive denominator, matching source/output digests, and the aggregate passed. Local current checkout 103a1e0 also passed the SDK matrix (1,440 assertions, 43 cases, 10 lanes). PR #2 remains unmerged pending its required approving review; this receipt does not qualify selected boot or frontend behavior.
result: pass
source: automated
resolution: |
  G-05-5 resolved by Plan 05-06's exact-SHA hosted receipt. The earlier failure remains in the gap record for history; no user confirmation was needed for this machine-observable CI claim.

## Summary

total: 5
passed: 3
issues: 1
pending: 0
skipped: 0
blocked: 1

## Gaps

- gap_id: G-05-3
  truth: "The supported selected game and BIOS archives map into GNMV, the native loader accepts them, and the selected guest reaches its attract/start checkpoint."
  status: failed
  reason: "The former archive-mapping failure is fixed, but the selected guest reaches the 256-chunk hard bound without a direct attract/start checkpoint."
  severity: major
  test: 3
  root_cause: "The native qualifier has no guest-written attract/start predicate or success branch, so even a guest that reaches the state cannot be recognized. The 256-chunk run ends as budget exhaustion; whether additional MVS behavior limits actual progress remains unknown."
  artifacts:
    - path: tools/mvs/qualify_local_boot.py
      issue: "The wrapper only returns success for a guest-executed attract_start result, which the current native qualifier cannot produce."
    - path: tools/mvs/mvs_qualify.c
      issue: "Result paths end at fault, STOP, error, or budget exhaustion; no guest-written attract/start predicate or success path exists."
    - path: include/glueyneo/glueyneo.h
      issue: "The exported MVS observation has no selected-guest mode/checkpoint signal for qualification."
    - path: tests/mvs/test_mvs.c
      issue: "The public boot checkpoint is a synthetic RAM sentinel, not selected-title attract/start."
  missing:
    - "Define a source-justified guest-written state transition and expose only the per-instance observation needed to qualify it."
    - "Add rights-clear positive and wrong-behavior controls, then rerun bounded qualification before attributing the budget stop to specific CPU/MVS behavior."
  reconciliation_note: "Kept open after 05-06: although its plan lists this gap, the matching summary is halted and explicitly says no independently observed selected configuration or sourced guest-written predicate was found. Executing a plan is not evidence that this criterion passed."
  debug_session: .planning/debug/phase05-selected-guest-attract-start.md
- gap_id: G-05-5
  truth: "The existing pull-request/main CI evidence matrix runs the public MVS regression suite with a positive named-test denominator."
  status: resolved
  reason: "The local MVS lane now exists and passes, but no hosted exact-current-SHA receipt is available from this checkout."
  severity: major
  test: 5
  root_cause: "The original MVS collector omission is fixed; the final revision has no eligible hosted PR/main run. The CI workflow has no manual trigger, and this local branch has no configured upstream and includes unrelated history that is not safe to publish as-is."
  artifacts:
    - path: tools/verify_sdk.py
      issue: "The source-bound matrix now enumerates all seven MVS tests and validates their passing denominator and evidence identities."
    - path: tools/sdk_evidence.py
      issue: "The current evidence digest covers relevant MVS source and test files, but local success is not a hosted receipt."
    - path: CMakeLists.txt
      issue: "Seven MVS tests are registered and selected by the repaired local matrix lane."
    - path: .github/workflows/ci.yml
      issue: "Hosted matrix runs on pull requests and main pushes; there is no manual dispatch for an unpublished local revision."
  missing:
    - "Prepare a reviewed, public-safe final revision and run existing PR/main CI at that exact committed SHA."
    - "Verify the hosted receipt has all seven named passing MVS tests, a positive denominator, output and source digests, matching revision, and passing aggregate."
  reconciliation_note: "Resolved by Plan 05-06: the eligible hosted PR #2 event and downloaded artifacts were verified against its exact candidate SHA; all seven named MVS tests, positive denominator, source/output identities, and aggregate passed. The PR is still unmerged pending required review, which is separate from this hosted-test criterion."
  resolved_by: 05-06-PLAN.md
  resolved_at: 2026-10-09
  debug_session: .planning/debug/phase05-hosted-mvs-ci-evidence.md
