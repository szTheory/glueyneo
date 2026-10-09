---
status: diagnosed
trigger: "Phase 05 UAT gap G-05-5: public MVS regression tests are omitted from the current-revision PR/main CI evidence matrix."
created: 2026-10-09
updated: 2026-10-09
---

## Current Focus

hypothesis: Confirmed: the matrix collector lacks an MVS lane and exact MVS test inventory, so the configured public cases cannot enter matrix receipts.
test: Compared CTest discovery, collector label selection, CI invocation, path classification, and source identity inventory.
expecting: Adding a named MVS lane with exact cases to the existing collector should put seven tests into each applicable matrix receipt; this direction remains unimplemented.
next_action: Return diagnosis to UAT orchestrator for consolidated gap planning.
bug_class: Bohrbug (deterministic integration omission)
candidate_causes:
  - "code: fixed label and case inventory in the evidence collector omitted the new MVS suite"
  - "config: CI path classifier might skip matrix for MVS paths (eliminated)"
  - "data: CMake might fail to register MVS CTests (eliminated)"
and_gate: "No for test omission: fixed collector inventory alone excludes the tests. The separate relevant-source digest omission also needs correction for full source identity coverage."

## Symptoms

expected: Existing PR/main current-SHA evidence includes the MVS region, importer, callback, guest-checkpoint, and bounded fuzz-corpus CTests with exact names and positive counts.
actual: At checkout d65dc2c, tools/verify_sdk.py defines no MVS CTest lane and its matrix suite enumerates SDK labels. CMake registers Phase 05 tests under mvs, and local CTests pass.
errors: No failing command; CI parity and evidence coverage are absent.
reproduction: Test 5 in .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-UAT.md.
started: Phase 05 implementation.

## Eliminated

## Evidence

- timestamp: 2026-10-09
  checked: Knowledge base
  found: No .planning/debug/knowledge-base.md exists.
  implication: No prior resolution candidate to test.
- timestamp: 2026-10-09
  checked: CMakeLists.txt and configured CTest discovery
  found: CMake registers seven named mvs tests under label mvs; `ctest --preset sdk-debug -N -L mvs` discovers all seven with a positive denominator.
  implication: The tests exist and local discovery is intact.
- timestamp: 2026-10-09
  checked: tools/verify_sdk.py SUITE_LABELS, CTEST_CASES, run_existing_ctest, suite_matrix
  found: SUITE_LABELS and CTEST_CASES contain only SDK lanes; suite_matrix iterates contract, diagnostic, run, controls, isolation, provenance, and capabilities. run_existing_ctest selects by only the chosen label and exact case inventory.
  implication: No matrix invocation can select an mvs-labeled test or record its named denominator.
- timestamp: 2026-10-09
  checked: .github/workflows/ci.yml and tools/workflow/ci_policy.py
  found: PR/main jobs call verify_sdk.py --suite matrix at the event SHA; classifying tests/mvs/test_mvs.c and tools/mvs/mvs_import.c selects both matrix and public-content jobs.
  implication: CI invokes the matrix; path classification is not the omission.
- timestamp: 2026-10-09
  checked: tools/sdk_evidence.py RELEVANT_FILES
  found: Its source digest inventory contains no mvs path, while source_revision still derives from git HEAD.
  implication: This is a separate identity coverage weakness to address when adding the MVS lane, but not the cause of test nonselection.
- timestamp: 2026-10-09
  checked: tests/sdk/test_matrix_evidence.py and tests/workflow/test_ci_policy.py
  found: Tests exercise matrix receipt identity, omission of whole matrix lanes, and workflow policy; none asserts inclusion of the seven MVS named CTests in suite_matrix output.
  implication: The existing controls did not detect the new suite omission.

## Resolution

root_cause: The Phase 05 CMake tests were added with the mvs label, but the fixed label/case inventory and suite_matrix loop in tools/verify_sdk.py were not extended; CI runs that collector, so successful matrix receipts omit every MVS test.
fix: "Proposed only: add an mvs label/case inventory and collect it in suite_matrix; assert the seven exact names and positive denominator in a collector-level regression test; include MVS source/test/importer paths in current-source identity as appropriate. Keep the existing CI runners."
verification: "Diagnosis: ctest -N -L mvs discovers seven cases; collector inventories and loop contain zero MVS entries; CI classifier selects matrix for MVS paths. No fix applied or hosted run claimed."
files_changed: []
