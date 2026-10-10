---
phase: 05-selected-mvs-boot
verified: 2026-10-10T00:39:34Z
status: gaps_found
score: 1/5 must-haves verified
covered_files:
  - .github/workflows/ci.yml
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-01-PLAN.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-01-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-02-PLAN.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-02-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-03-PLAN.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-03-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-04-PLAN.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-04-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-05-PLAN.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-05-SUMMARY.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-06-PLAN.md
  - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-06-SUMMARY.md
  - docs/mvs-media.md
  - docs/rights-inventory.md
  - experiments/owned_cpu/cpu.c
  - experiments/owned_cpu/cpu.h
  - fixtures/diagnostic/manifest.json
  - include/glueyneo/glueyneo.h
  - src/instance.c
  - src/libretro/libretro_core.c
  - src/mvs/mvs_bus.c
  - src/sdk_private.h
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/mvs/test_mvs.c
  - tests/mvs/test_mvs_qualification.py
  - tests/owned_cpu/test_semantics.c
  - tests/sdk/ORACLE.md
  - tests/sdk/test_matrix_evidence.py
  - tools/mvs/mvs_import.c
  - tools/mvs/mvs_qualify.c
  - tools/mvs/qualify_local_boot.py
  - tools/sdk_evidence.py
  - tools/verify_sdk.py
covered_digest: "v3:sha256:4a65202f9e734b4a4b317c3ee98a4c62fde4ddaa3cc353619e82a3bd2ceab793"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 1/5
  gaps_closed:
    - "An eligible exact-SHA hosted MVS receipt now exists for PR #2 candidate e80672845fc60d94d8a44eab416377534c9a99f1; this closure applies to that candidate only."
  gaps_remaining:
    - "Selected private media has not been qualified through the actual pinned RetroArch/import path."
    - "Selected-media compatibility and user-visible incompatibility handling remain unqualified."
    - "The selected guest has no accepted attract/start checkpoint."
    - "The current shared checkout differs from the hosted candidate and lacks its receipt checker."
  regressions: []
gaps:
  - truth: "The selected unmodified game and BIOS archives load through the documented, tested pinned RetroArch/import path."
    status: partial
    reason: "The importer, normalized bundle contract, and generated-bundle smoke checks are present and tested, but no current selected-media actual-app observation proves this path. The native attract/start precondition for the app smoke is not met."
    artifacts:
      - path: "tools/mvs/qualify_local_boot.py"
        issue: "The private-safe wrapper exists, but selected-media compatibility and actual frontend load are not established by the synthetic path."
      - path: "tests/libretro/retroarch_smoke.py"
        issue: "The actual-app runner exists; this verification ran only its GUI-free generated-bundle tests."
    missing:
      - "A sourced, privacy-safe selected-pair compatibility result followed by the bounded actual-app smoke once the native checkpoint exists."
  - truth: "The user receives distinct actionable missing, incompatible, unsupported, malformed, and limit errors, and rejected loads recover safely."
    status: partial
    reason: "Current tests prove structural error classification, bounded parsing, and synthetic recovery. They do not qualify the selected BIOS/game identity or prove the complete selected-media user path."
    artifacts:
      - path: "tools/mvs/mvs_import.c"
        issue: "The source-member identity checks are implemented, but no independently qualified selected pair has established the positive selected-media case."
      - path: "src/libretro/libretro_core.c"
        issue: "The adapter consumes normalized GNMV content; it does not establish end-user error behavior for selected ZIP inputs."
    missing:
      - "A privacy-safe selected-pair compatibility result and direct evidence that the documented consumer path distinguishes the selected incompatibility cases."
  - truth: "The selected guest reaches the game's attract/start path through owned CPU and required MVS behavior with source-qualified regressions and no fabricated behavior."
    status: failed
    reason: "The latest accepted selected native observation exhausted its 256-chunk instruction budget without an accepted guest-written checkpoint. No independently justified predicate exists; synthetic guest sentinels and device-state transitions do not prove the selected title path."
    artifacts:
      - path: "tools/mvs/mvs_qualify.c"
        issue: "It reports budget exhaustion or unsupported events but has no accepted selected-title attract/start predicate."
      - path: "src/mvs/mvs_bus.c"
        issue: "The implemented source-backed device behavior has not been shown sufficient for the selected guest path."
    missing:
      - "An independently justified selected-configuration guest-written predicate with wrong-source/value/order controls and regressions for only the behavior demanded by that observed path."
      - "A current bounded selected run that reaches that predicate before its documented limit."
  - truth: "The current shared checkout contains and can verify the exact-SHA hosted MVS receipt route for its own public-safe source revision."
    status: partial
    reason: "The exact hosted receipt is recorded for candidate e80672845fc60d94d8a44eab416377534c9a99f1, not shared HEAD 46dbab8aa7595f44fcb39fad6f8fbd20b8d5f13a. The receipt checker and its test are absent from this checkout; the current shared-branch history scan also fails its public-content gate. Do not reuse the candidate receipt as proof for shared HEAD."
    artifacts:
      - path: "tools/verify_hosted_mvs.py"
        issue: "Absent from the shared checkout; present only in PR #2 candidate evidence."
      - path: "tests/sdk/test_hosted_mvs_receipt.py"
        issue: "Absent from the shared checkout; present only in PR #2 candidate evidence."
      - path: ".planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-HOSTED-QUALIFICATION.md"
        issue: "Records a passing candidate receipt, not a receipt for shared HEAD."
    missing:
      - "Integrate the reviewed candidate through the protected PR route, or establish a public-safe shared source revision and bind a passing hosted receipt to that exact revision."
advisory: []
---

# Phase 5: Selected MVS Boot Verification Report

**Phase Goal:** A user can load the selected private MVS media and see the guest-executed game reach its attract/start path with a documented, bounded configuration.

**Verified:** 2026-10-10T00:39:34Z
**Status:** gaps_found
**Re-verification:** Yes — after the Phase 05-06 evidence refresh

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | A C integrator can supply immutable normalized cartridge and BIOS regions for the selected MVS profile under explicit lifetimes, layout, byte order, and limits. | VERIFIED | The public versioned MVS contract and per-instance ownership are in current source. The current seven-test MVS CTest set passes, including media-contract and recovery cases. This proves the structural contract, not selected private media identity. |
| 2 | The selected unmodified game and BIOS archives load through the documented pinned RetroArch/import path. | UNCERTAIN (partial) | The selected ZIP importer, normalized GNMV path, adapter loader, and actual-app runner exist. This pass exercised synthetic inputs only; actual selected-media RetroArch behavior remains unknown/manual-only and its prerequisite is unmet. |
| 3 | Missing, incompatible, unsupported, malformed, and limit failures are distinct and rejected loads recover safely. | UNCERTAIN (partial) | Seven current MVS CTests and the matrix cover synthetic parsing, error, limit, and recovery behavior. Selected-pair compatibility and the complete user-visible selected-media flow remain unqualified. |
| 4 | The selected guest reaches the attract/start path through owned CPU and required MVS behavior, backed by source-qualified regressions and without fabricated behavior. | FAILED — BLOCKER | The latest accepted bounded selected run ended with guest_instruction_budget_exhausted and no checkpoint. The qualifier code exposes no accepted predicate. No synthetic sentinel or device-state counter is substituted for the selected-title result. |
| 5 | The exact public-safe hosted source revision has an eligible seven-test MVS receipt, with matching source/output identity and aggregate. | UNCERTAIN for shared HEAD; candidate-only pass | PR #2 candidate SHA e80672845fc60d94d8a44eab416377534c9a99f1 has a recorded passing hosted run 38001400110 with seven named MVS tests, a positive denominator, matching digests, and a passing aggregate. The candidate public-content/history scan recorded zero findings and 42 rights rows. PR #2 remains open and REVIEW_REQUIRED/BLOCKED. Shared HEAD is 46dbab8aa7595f44fcb39fad6f8fbd20b8d5f13a, not that candidate; its public-content/history scan fails and its tree lacks the receipt checker. The shared-checkout run is not qualified by the candidate receipt. |

**Score:** 1/5 must-haves verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| include/glueyneo/glueyneo.h | Versioned normalized MVS contract | VERIFIED | Explicit role, layout, size limits, and copied ownership are implemented. |
| tools/mvs/mvs_import.c | Bounded ZIP32 importer and selected profile mapper | VERIFIED | Importer is substantive and isolated from the native runtime; synthetic positive, malformed, identity, and limit paths are tested. |
| src/mvs/mvs_bus.c | Per-instance MVS guest-visible bus behavior | VERIFIED | Substantive implementation is wired into instance execution and tested at synthetic boundaries. Selected-title sufficiency is not established. |
| tests/mvs/test_mvs.c | Independent synthetic checkpoints and adverse controls | VERIFIED (synthetic scope) | The current MVS CTest set passes; the guest sentinel is not a selected-game oracle. |
| tools/mvs/mvs_qualify.c | Bounded selected guest checkpoint classifier | PARTIAL | It enforces the run bound and reports unsupported/budget outcomes; no accepted selected attract/start predicate exists. |
| tests/libretro/retroarch_smoke.py | Bounded actual pinned-app smoke | PRESENT, actual behavior unverified | The runner is wired for normalized content. This pass ran only GUI-free contract tests and did not launch RetroArch. |
| tools/verify_hosted_mvs.py | Exact-SHA hosted event/receipt checker | MISSING from shared checkout; candidate-only | The candidate has the checker; it cannot be imported into current shared source evidence. |
| tests/sdk/test_hosted_mvs_receipt.py | Receipt checker regression suite | MISSING from shared checkout; candidate-only | No local shared-checkout execution is possible. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| tools/mvs/mvs_import.c | include/glueyneo/glueyneo.h | Normalized bundle descriptors become versioned MVS regions | WIRED | Selected and synthetic import paths populate the API contract; synthetic integration tests pass. |
| src/instance.c | src/mvs/mvs_bus.c | Per-instance machine state and guest bus callbacks | WIRED | The CPU reaches the MVS bus through per-instance callbacks; the MVS CTest set passes. |
| src/libretro/libretro_core.c | normalized GNMV | retro_load_game parses bounded bundle data and calls the native MVS loader | WIRED | Adapter accepts normalized bundles only; fake callback tests do not demonstrate the real app flow. |
| tools/mvs/qualify_local_boot.py | tools/mvs/mvs_import.c and tools/mvs/mvs_qualify.c | Select input pair, normalize, then run native qualifier | WIRED | Code path exists; selected compatibility and attract/start acceptance remain unproven. |
| .github/workflows/ci.yml | tools/verify_hosted_mvs.py | Hosted artifact receipt validation | NOT WIRED in shared checkout | The candidate implements the checker route; the shared checkout does not contain the checker or its test. |

### Data-Flow Trace

| Artifact | Data | Source | Real data? | Status |
|---|---|---|---|---|
| MVS synthetic integration tests | GNMV regions | Generated test-only archives | Yes, synthetic | FLOWING through importer, native loader, guest execution, and callback seam; does not prove selected media. |
| tools/mvs/qualify_local_boot.py | Selected bundle | Local ignored game/BIOS archives, when available | Unknown in this verification | No private media was inspected. The latest accepted selected run reached native execution but did not reach a checkpoint. |
| tests/libretro/retroarch_smoke.py | Selected app content | Normalized GNMV | Not exercised with selected content | Current 31 tests use generated fixtures; actual app behavior remains unknown. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Public MVS importer, contract, recovery, synthetic guest and callback regressions | ctest --preset sdk-debug -R '^mvs_' --output-on-failure --no-tests=error | 7/7 passed on shared HEAD 46dbab8aa7595f44fcb39fad6f8fbd20b8d5f13a | PASS; synthetic scope |
| Matrix receipt construction and negative controls | python3 tests/sdk/test_matrix_evidence.py | Passed on shared HEAD | PASS |
| Current local SDK matrix | python3 tools/verify_sdk.py --suite matrix | 1,440 assertions; 43 cases; 10 lane executions; MVS lane 7/7; source revision 46dbab8aa7595f44fcb39fad6f8fbd20b8d5f13a | PASS; local evidence only |
| GUI-free selected-bundle validation and diagnostics | python3 tests/libretro/test_retroarch_smoke.py -v | 31/31 passed; no app launched | PASS; structural scope only |
| Selected guest attract/start | Latest accepted bounded local qualification recorded in 05-VALIDATION.md | guest_instruction_budget_exhausted at the documented 256-chunk cap; no accepted checkpoint | FAILED for GAME-02; this pass did not inspect private media or repeat the unchanged run |
| Shared-checkout public-content/history safety | python3 tools/public_content.py --root . --history-revision HEAD | Exit 1; findings include personal-path history; finding paths are intentionally omitted | FAIL; shared checkout must not be published |
| Candidate hosted receipt | PR #2 candidate SHA e80672845fc60d94d8a44eab416377534c9a99f1, run 38001400110 | All seven named MVS tests pass with positive denominator, matching digests, and passing aggregate; candidate scan recorded zero findings and 42 rights rows | Candidate-only; PR remains REVIEW_REQUIRED/BLOCKED |

### Probe Execution

No plan or summary declares a probe-*.sh file. No probe applies.

### Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|---|---|---|---|
| MEDIA-02 | 05-01 | SATISFIED | Versioned region contract, bounds, byte order, and ownership are present; current MVS contract tests pass. |
| MEDIA-03 | 05-01 through 05-06 | PENDING | Generated-input tests pass; selected-media import/load in actual pinned RetroArch remains unobserved. |
| MEDIA-04 | 05-01, 05-02, 05-04, 05-06 | PENDING | Structural negative cases and recovery are tested; selected identity compatibility and complete consumer error path remain unqualified. |
| GAME-02 | 05-01 through 05-06 | PENDING / BLOCKED | Latest selected bounded execution exhausted its budget without the accepted guest-written attract/start predicate. |

No additional Phase 05 requirement mapped to this phase was orphaned. No later roadmap phase explicitly satisfies the still-open Phase 05 success criteria, so none are deferred.

### Test Quality Audit

| Test File | Linked Requirement | Active | Circular | Assertion Scope | Verdict |
|---|---|---:|---:|---|---|
| tests/mvs/test_mvs.c | MEDIA-02, MEDIA-04, GAME-02 | Yes | No issue found | Value and behavior assertions on synthetic inputs | Good synthetic evidence; not a selected-title oracle |
| tests/mvs/test_mvs_qualification.py | MEDIA-03, MEDIA-04 | Yes | No issue found | Generated archive parsing, mapping and negative controls | Good synthetic evidence; selected private identity not tested |
| tests/libretro/test_retroarch_smoke.py | MEDIA-03 | Yes | No issue found | 31 active generated-fixture checks | Good pre-launch validation; no actual-app assertion in this run |
| tests/sdk/test_matrix_evidence.py | Hosted MVS evidence | Yes | No issue found | Identity, count, outcome, and cost-control checks | Passes locally; does not create hosted evidence |

No disabled linked tests or circular expected-value generation were found in the focused test files. The marker scan's XXXXXX match is the mkstemp temporary-name template, not a debt marker.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|---|---|---|---|
| None established in current source paths | — | — | No unreferenced TBD/FIXME/XXX debt marker or stub was found. |

### Human Verification Required

No manual UAT item is actionable now. The pinned-app check has a deterministic runner, but it must remain blocked until the selected native attract/start checkpoint and required launch preconditions exist. The missing guest predicate/configuration is an external evidence blocker; do not invent it or rerun the unchanged bounded qualification.

### Gaps Summary

The current checkout proves the C media contract, bounded synthetic importer/native guest path, seven MVS regressions, and structural smoke contracts. The selected private media path, selected identity compatibility, and attract/start behavior remain unqualified; the latest recorded selected run exhausted its documented limit without a checkpoint. The exact hosted receipt is real for PR #2 candidate SHA e80672845fc60d94d8a44eab416377534c9a99f1 only. The shared checkout is a different revision, lacks the candidate receipt checker, and fails the public-content/history scan, so it must not be published or treated as covered by that hosted run.

The phase remains blocked. No unchanged gap plan is warranted: the remaining guest checkpoint and selected-input evidence cannot be synthesized from current artifacts, and the hosted candidate still requires the protected review/integration route. Phase 04 status, frontend unknown/manual-only result, and threat dispositions are unchanged.

---
_Verified: 2026-10-10T00:39:34Z_
_Verifier: gsd-verifier_
