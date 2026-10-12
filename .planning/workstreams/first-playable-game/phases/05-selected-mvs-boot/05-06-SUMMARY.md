---
phase: 05-selected-mvs-boot
plan: 06
subsystem: testing
tags: [mvs, source-evidence, public-content, hosted-ci]
dependency_graph:
  requires: [05-01, 05-02, 05-04]
  provides: [reviewed-public-candidate, exact-sha-hosted-mvs-receipt]
  affects: [G-05-3, G-05-5, MEDIA-02, MEDIA-03, MEDIA-04, GAME-02]
tech-stack:
  added: []
  patterns: [canonical-receipts, exact-source-identity, public-rights-inventory]
key-files:
  created: [.planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-06-SUMMARY.md]
  modified:
    - tests/sdk/ORACLE.md
    - fixtures/diagnostic/manifest.json
    - docs/rights-inventory.md
    - tools/verify_hosted_mvs.py
    - tools/verify_sdk.py
    - tests/sdk/test_hosted_mvs_receipt.py
    - tests/sdk/test_matrix_evidence.py
    - .github/workflows/ci.yml
    - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-VALIDATION.md
    - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-REVIEW.md
    - .planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-HOSTED-QUALIFICATION.md
decisions:
  - No selected-media predicate or compatibility result is claimed without independent selected-configuration evidence.
  - Hosted MVS qualification is limited to the exact PR candidate SHA and does not establish guest attract/start or frontend behavior.
metrics:
  duration: 20h 15m
  completed: 2026-10-09
  plan_head_before: 304199e4398cc48755705f272d60e8434693c252
  plan_head_after: d8a996f973da2c81931facd78066c1f2bb7a7866
  commits: 1
status: halted
actuals:
  tokens: 10336
  tasks: 2
  commits: 1
coverage:
  - id: D1
    description: "The reviewed oracle identity and affirmative public-rights rows clear the candidate public-content and MVS matrix gates."
    verification:
      - kind: unit
        ref: "python3 tests/sdk/test_matrix_evidence.py"
        status: pass
      - kind: integration
        ref: "PR #2 candidate SHA e80672845fc60d94d8a44eab416377534c9a99f1: public-content/history scan; zero findings and 42 rights rows. Candidate-only historical evidence."
        status: pass
      - kind: integration
        ref: "python3 tools/verify_sdk.py --suite matrix"
        status: pass
      - kind: integration
        ref: "Shared checkout HEAD c2a46f1e6735fc2dfe6432a628b47437c2ca3ef6: python3 tools/public_content.py --root . --history-revision HEAD; failed because local branch history contains personal-path findings. This checkout is not publishable."
        status: fail
    human_judgment: false
  - id: D2
    description: "The selected guest reaches an independently justified guest-written attract/start predicate within the measured bound."
    verification:
      - kind: integration
        ref: "Selected native qualification; latest accepted observation remains budget exhaustion without a source-backed predicate."
        status: unknown
    human_judgment: true
    rationale: "No independent selected configuration or sourced guest-write predicate is available; do not invent a watchpoint or repeat the unchanged bounded run."
  - id: D3
    description: "The reviewed public candidate has an eligible hosted exact-SHA seven-test MVS receipt."
    verification:
      - kind: integration
        ref: "PR #2 candidate SHA e80672845fc60d94d8a44eab416377534c9a99f1; hosted run 38001400110; seven named MVS tests, positive denominator, matching source/output digests, passing aggregate. Candidate-only; PR remains REVIEW_REQUIRED."
        status: pass
    human_judgment: false
  - id: D4
    description: "The selected media loads through the actual pinned RetroArch flow and satisfies the selected-game behavior."
    verification: []
    human_judgment: true
    rationale: "The selected guest checkpoint prerequisite is unmet and the prior app launch preconditions did not materially change; actual selected-media app behavior remains unknown/manual-only."
---

# Phase 05 Plan 06: Selected MVS evidence and exact-SHA hosted qualification

**The diagnostic oracle and public rights gates are corrected, and hosted MVS CI now verifies the exact candidate receipt; selected-game execution remains blocked by missing sourced configuration and guest predicate evidence.**

## Performance

- **Started:** 2026-10-09T02:40:41Z
- **Completed:** 2026-10-09T22:56:04Z
- **Tasks completed:** 2 of 3 (Task 2 intentionally stopped at its evidence gate)
- **Files changed in the public candidate:** 12 across its task commits

## Accomplishments

- Task 1 completed in shared commit `d8a996f`: corrected the diagnostic cycle contract and source identity, added affirmative exact-byte rights rows for the 13 omitted public test paths, and narrowly dispositioned the two upstream zlib attribution blobs while preserving notices. Local source identity, public-content, focused checks, and the complete SDK matrix passed.
- Task 2 reviewed available source and prior validation evidence but found no independently observed selected configuration or sourced guest-written attract/start predicate. The existing 256-chunk run exhausted its instruction budget without a checkpoint. No new selected run, behavior change, raised bound, or guessed predicate was made. This is the plan's intended narrow stop; GAME-02 and selected compatibility remain open.
- Task 3 produced public-safe PR #2 at `e80672845fc60d94d8a44eab416377534c9a99f1`. The candidate emits a path-free MVS lane receipt alongside the canonical output and the hosted CI policy job validates both artifacts against the exact event, current source identity, and aggregate. Independent review passed the exact candidate SHA.
- Hosted run `38001400110` passed all six matrix lanes, public-content, and `ci-policy`. Artifacts from that same run passed `tools/verify_hosted_mvs.py` with all seven named MVS CTests, a positive denominator, matching source/output digests, and a passing aggregate. Local matrix results are documented separately from hosted evidence.
- PR #2 remains open and unmerged because protected `main` requires one approving PR review. Its current state is `REVIEW_REQUIRED` / `BLOCKED`; protection was not bypassed. The hosted evidence qualifies the exact candidate revision, not a merge or release.
- Actual selected-media RetroArch import/load remains unknown/manual-only. Its launch preconditions did not materially change, so no app launch was attempted. Phase 04 and `05-UAT.md` remain untouched.

## Key Candidate Paths in PR #2 (not merged)

- Diagnostic provenance and privacy gates: `tests/sdk/ORACLE.md`, `fixtures/diagnostic/manifest.json`, `docs/rights-inventory.md`, `tools/public_content.py`, `tools/sdk_evidence.py`, `tools/verify_playable.py`, `tests/sdk/test_evidence.py`, `tests/workflow/test_public_content.py`, `tests/tools/test_verify_playable.py`, `tests/libretro/retroarch_smoke.py`, `tests/libretro/test_retroarch_smoke.py`.
- Hosted and source-slice evidence: `tools/verify_sdk.py`, `tools/verify_hosted_mvs.py`, `.github/workflows/ci.yml`, `CMakeLists.txt`, `src/chips/z80_candidate.c`, `tools/mvs/mvs_import.c`, `tests/sdk/test_hosted_mvs_receipt.py`, `tests/sdk/test_matrix_evidence.py`, `tests/mvs/test_mvs_qualification.py`, `tests/fixture/test_public_guest.c`, `tests/libretro/callback_harness.c`.

## Planning Records Created/Updated

- `05-VALIDATION.md`, `05-REVIEW.md`, and `05-HOSTED-QUALIFICATION.md` record exact Task 2/3 status without private media details.
- `STATE.md` and `ROADMAP.md` retain Plan 05-06 as blocked and point to the named verify-work step.

## Verification

- `python3 tests/sdk/test_matrix_evidence.py` — passed.
- `python3 tests/sdk/test_hosted_mvs_receipt.py` — passed, 11 tests.
- `python3 tools/public_content.py --root . --history-revision HEAD` — passed with zero findings and 42 rights rows.
- `python3 tools/verify_sdk.py --suite evidence` — passed.
- `python3 tools/verify_sdk.py --suite matrix` — passed, 1,440 assertions / 43 cases / 10 local lanes.
- Hosted PR run `38001400110` — passed for exact candidate `e80672845fc60d94d8a44eab416377534c9a99f1`; downloaded event, receipt, output, and aggregate accepted by the receipt checker.
- Independent review — passed for exact candidate SHA.

## Current shared checkout refresh — 2026-10-09

- The local evidence matrix and SDK matrix pass on shared checkout HEAD
  `c2a46f1e6735fc2dfe6432a628b47437c2ca3ef6`.
- A fresh `python3 tools/public_content.py --root . --history-revision HEAD`
  scan fails because local branch history contains personal-path findings.
  The finding details are intentionally not copied into this planning record;
  this shared checkout history must not be published.
- This local history failure does not change the separately recorded
  zero-finding scan for public candidate `e80672845fc60d94d8a44eab416377534c9a99f1`.
  Candidate CI and hosted-receipt results remain scoped to that exact SHA.

## Deviations from Plan

**1. [Rule 3 - Blocking] Added the missing hosted MVS receipt artifact route**
- **Found during:** Task 3
- **Issue:** The existing CI route uploaded only the canonical CTest summary, leaving the final receipt checker without the exact lane receipt it must validate.
- **Fix:** Persisted the validated path-free MVS lane receipt, uploaded/downloaded it on matrix-planned events, and ran the checker against the current checkout's relevant-source digest and same-run aggregate. Added a docs-only condition so the receipt check does not fail when the classifier intentionally skips the matrix.
- **Files modified:** `tools/verify_sdk.py`, `.github/workflows/ci.yml`, `tests/sdk/test_matrix_evidence.py`, `tests/sdk/test_hosted_mvs_receipt.py`
- **Verification:** Focused receipt and matrix tests, public-content/history scan, local evidence/matrix, independent review, and exact-SHA hosted run passed.
- **Candidate revision:** `e80672845fc60d94d8a44eab416377534c9a99f1`

## Deferred Issues

- Task 2 needs an independently observed selected configuration and source-backed guest-written attract/start predicate before the bounded selected qualification can run. The specific missing evidence is recorded in `05-VALIDATION.md`; no private media identity or trace is included here.
- PR #2 needs one approving PR review to satisfy protected `main`. This is separate from the passing exact-SHA hosted receipt.
- Phase 05 remains incomplete. The next named GSD step after this execution boundary is `$gsd-verify-work 05 --ws first-playable-game`, which must preserve the selected-boot blocker and keep `05-UAT.md` reconciliation in that step.

## Self-Check: PASSED

- Summary file exists at the planned path.
- Task 1 commit `d8a996f` exists in the shared project history.
- Task 3 candidate review, hosted run, and downloaded receipt correspond to exact SHA `e80672845fc60d94d8a44eab416377534c9a99f1`.

## Post-verification continuity — 2026-10-10

- The subsequent `$gsd-verify-work 05 --ws first-playable-game` step completed
  and left Phase 05 blocked: the selected configuration and source-backed
  guest-written attract/start predicate are still unsupported by independent
  evidence. No new repository defect authorized another gap plan.
- A diagnostic comparison then tested fresh no-content startup and
  core-plus-public-fixture startup with pinned RetroArch 1.22.2. Both exited
  -6 with SIGABRT before the first screenshot. The comparison does not identify
  a core/content fault or establish selected-media behavior; see
  05-VALIDATION.md.
- Phase 05 remains incomplete. Do not rerun verify-work or create a gap plan
  while these findings are unchanged. Once the selected configuration and
  source-backed guest predicate are available, resume the existing plan with
  `$gsd-execute-phase 05 --gaps-only --ws first-playable-game`. Phase 06
  depends on Phase 05 and is not ready to plan.

---
*Phase: 05-selected-mvs-boot*
*Completed: 2026-10-09 (execution halted at Task 2 evidence gate)*
