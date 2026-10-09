---
status: diagnosed
trigger: "Phase 05 UAT gap G-05-3: selected game and BIOS archives do not map into GNMV; local qualification returned no_supported_role_bundle_archive at archive_to_region_mapping."
created: 2026-10-09
updated: 2026-10-09
---

## Current Focus

hypothesis: The implemented import path accepts only one already-normalized six-role ZIP, while qualification is asked to load separate source game and BIOS ZIPs.
test: Code-path inspection plus public synthetic one-member ZIP reproduction; compare with the existing six-member positive test.
expecting: Observed: both public one-member ZIPs return importer profile status 4, while the documented six-member synthetic archive passes. The private archives' individual rejection codes remain unknown because the wrapper suppresses them.
next_action: Return diagnosis to the UAT orchestrator for a targeted gap plan; do not rerun unchanged private qualification.
bug_class: Bohrbug (deterministic input-contract mismatch)
reasoning_checkpoint:
  hypothesis: "The qualifier never composes game and BIOS ZIPs, and the importer demands one ZIP whose six members are already mapped to canonical regions."
  confirming_evidence:
    - "qualify_local_boot.py invokes mvs_importer separately for each ZIP and runs the guest only when exactly one input succeeds."
    - "mvs_import.c requires exactly six entries, canonical names, and exact mapped-region lengths."
    - "Two public synthetic one-member ZIPs each returned profile status 4; the public canonical six-member test passes."
  falsification_test: "Find an implemented path that reads separate game and BIOS ZIPs and constructs one validated six-region GNMV; none exists in the inspected qualifier/importer code."
  fix_rationale: "Add a selected-profile composition and source-member mapping layer around the bounded ZIP decoder, then run it through the existing GNMV/native path."
  blind_spots: "Private archive member structure and exact individual importer rejection codes were intentionally not inspected; selected identity and guest compatibility remain unknown."
  candidate_causes:
    - "code: qualifier invokes the importer once per archive without combining inputs"
    - "data: supported user scenario supplies separate game and BIOS source archives, whereas importer requires one canonical mapped-region archive"
    - "config/environment: importer path or local directory could be wrong, but the recorded status alone does not prove either and this does not explain the missing composition path"
  and_gate: "yes; the mismatch arises from the conjunction of a one-archive contract and a separate-source-archive workflow"

## Symptoms

expected: Supported selected game and BIOS archives map into GNMV, load through the native API, and reach the attract/start checkpoint.
actual: Current-revision local qualification returned no_supported_role_bundle_archive at archive_to_region_mapping; no selected guest ran.
errors: no_supported_role_bundle_archive
reproduction: Phase 05 UAT Test 3, as recorded in 05-UAT.md.
started: First local qualification of the Phase 05 selected media path; no earlier passing selected-media run is documented.

## Eliminated

- hypothesis: Native API, guest execution, or RetroArch caused the observed stop.
  evidence: Qualification returns no_supported_role_bundle_archive before invoking mvs_qualify, gn_load_mvs, or the frontend.
  timestamp: 2026-10-09
- hypothesis: A public canonical six-member archive is rejected by the importer in general.
  evidence: Phase 05 public positive tests pass for the canonical six-member shape; the synthetic one-member inputs fail with profile status 4 as expected.
  timestamp: 2026-10-09

## Evidence

- timestamp: 2026-10-09
  checked: Phase 05 UAT Test 3 and workstream STATE.md
  found: Synthetic importer tests pass, while the selected local qualification stops before native loading.
  implication: Guest execution and frontend behavior cannot explain this observed stop.
- timestamp: 2026-10-09
  checked: qualify_local_boot.py, mvs_import.c, docs/mvs-media.md, test_mvs_qualification.py
  found: Qualification invokes the single-input importer once per ZIP; the importer requires exactly six entries with canonical role names and mapped-region lengths. The only positive synthetic test creates those six members together. Documentation explicitly says the unmodified separate game and BIOS path is unproven.
  implication: There is no archive-composition or source-ROM-to-mapped-region normalization path for the selected inputs. The wrapper suppresses per-archive importer stderr and retains only a generic aggregate status, so no specific private rejection code is available.
- timestamp: 2026-10-09
  checked: Current built importer on two temporary, public synthetic single-member ZIPs
  found: Both returned profile status 4, while the current UAT records the canonical six-member public test as passing.
  implication: The importer rejects separate source inputs by construction. This test confirms the contract gap without examining private media, but does not identify which private member or format condition failed.
- timestamp: 2026-10-09
  checked: Public profile map in docs/mvs-media.md
  found: The six GNMV roles are mapped regions; source game ROMs require program word swapping and sprite byte-lane interleaving, and BIOS selection is separate.
  implication: Combining archives by concatenation or renaming alone would not implement the documented source-to-region map or authenticate the selected profile.

## Resolution

root_cause: "The qualification/import boundary implements only a single canonical six-role ZIP whose payloads are already mapped regions; it has no selected-profile adapter to consume separate source game and BIOS archives, compose and transform their source ROM members, and produce one validated GNMV. Thus the recorded local qualification cannot reach native loading. The exact rejection reason for each private archive is not observable from the generic report."
fix: "Diagnosis only. Smallest direction: add a bounded selected-profile two-archive mapper using the existing ZIP decoder, exact source identity/size checks and pinned public region transforms, preserving ignored private evidence and the current GNMV/native interfaces; add public synthetic split-archive integration tests plus opt-in local qualification. Keep identity, boot, and frontend statuses open until directly observed."
verification: "Current-revision code inspection, public synthetic two-archive reproduction (each separate ZIP profile-rejected), and existing public canonical six-member positive coverage. No unchanged private qualification rerun."
files_changed: []
