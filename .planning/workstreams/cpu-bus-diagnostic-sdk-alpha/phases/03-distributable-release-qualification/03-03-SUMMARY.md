---
phase: 03-distributable-release-qualification
plan: 03
subsystem: ci-and-evidence
tags: [github-actions, platform-matrix, evidence, consumers]
requires:
  - phase: 03-distributable-release-qualification
    provides: deterministic SDK package and privacy scanner
provides:
  - Exact, fail-safe platform-matrix evidence schema with positive lane and assertion denominators.
  - Conservative path classification, read-only pull-request jobs, and an always-started current-SHA aggregate.
  - Current-source local verification receipt and bounded local content-scan evidence.
affects: [release-qualification, ci, platform-support]
actuals:
  tokens: 38893
  tasks: 2
  commits: 5
plan_head_before: 8759416
plan_head_after: 2054c3d6d07427d0e4a045b2388bcc933478bec9
tech-stack:
  added: []
  patterns: [conservative path selection, current-SHA aggregate, exact hosted identity evidence]
key-files:
  created: [.github/workflows/ci.yml, tools/workflow/ci_policy.py, tests/workflow/test_ci_policy.py, tests/sdk/test_matrix_evidence.py]
  modified: [tools/sdk_evidence.py, tools/verify_sdk.py, tests/consumers/check_package.py, evidence/sdk/verification.json, docs/evidence-schema.md, docs/testing.md]
key-decisions:
  - "A successful local matrix observation remains unknown for hosted support unless the exact GitHub runner identity is present."
  - "Unknown paths and comparison failures select the full required lane set; missing, failed, cancelled, empty, stale-SHA, or zero-denominator evidence fails the aggregate."
  - "Hosted platform, workflow, and runner-cost qualification remains pending until receipts are captured from configured GitHub runners."
patterns-established:
  - "Bind matrix records to exact OS, compiler, architecture, configuration, source revision, fixture, and runner identities."
  - "Keep scanner evidence bounded and report detector coverage without treating a negative result as proof of absence."
requirements-completed: []
coverage:
  - id: M1
    description: Local matrix diagnostic and installed-consumer evidence is bound to measured host identity and cannot qualify unrun hosted lanes.
    requirement: BUILD-04
    verification:
      - kind: unit
        ref: python3 tests/sdk/test_matrix_evidence.py (positive and adversarial schema controls)
        status: pass
      - kind: integration
        ref: python3 tools/verify_sdk.py --suite matrix at source revision 2054c3d
        status: pass
      - kind: hosted
        ref: Linux Clang/GCC, hosted macOS AppleClang, Windows MSVC, sanitizer/fuzz matrix receipts
        status: pending
    human_judgment: false
    rationale: The remaining evidence is an objective hosted-run result; no hosted runner execution or account configuration was available in this step.
  - id: C1
    description: Every PR and push starts a conservative required aggregate over actual job results and exact current-SHA evidence.
    requirement: DEL-01
    verification:
      - kind: unit
        ref: python3 tests/workflow/test_ci_policy.py (classifier, workflow contract, and aggregate adversarial cases)
        status: pass
      - kind: static
        ref: actionlint .github/workflows/ci.yml
        status: pass
      - kind: hosted
        ref: configured repository workflow run and measured hosted runner minutes
        status: pending
    human_judgment: false
    rationale: Hosted workflow behavior and runner cost require an actual configured GitHub run; local controls cannot establish them.
  - id: P1
    description: PR jobs use read-only token permissions and no secrets or privileged artifact execution.
    requirement: DEL-02
    verification:
      - kind: unit
        ref: python3 tests/workflow/test_ci_policy.py (workflow authority and artifact contract checks)
        status: pass
      - kind: hosted
        ref: repository protection, fork approval, and required-check settings
        status: pending
    human_judgment: false
    rationale: Account-level protection and hosted event configuration are externally observable facts, not inferred from workflow YAML.
duration: 32min
completed: 2026-10-06
status: complete
---

# Phase 03 Plan 03: Evidence-Gated CI Summary

**The repository now has a conservative GitHub Actions matrix and an aggregate that can only qualify exact, current-SHA lane evidence; hosted results remain pending until the workflow runs on configured runners.**

## Performance

- **Duration:** 32 min (approximate active execution time)
- **Completed:** 2026-10-06
- **Tasks:** 2
- **Implementation files:** 10
- **Task commits:** 5 before this summary and workflow-state closeout

## Accomplishments

- Added six exact lane definitions: Linux Clang, Linux GCC, macOS arm64 AppleClang, Windows x64 MSVC, and Linux Clang sanitizer and seeded-fuzz controls. Matrix rows bind measured compiler, OS, architecture, SDK, build and fixture identities, source revision, clean-tree status, outcome, positive assertion counts, and observed durations.
- Added a fail-open-to-full-matrix path classifier and an always-started aggregate. Missing, skipped, failed, cancelled, empty, stale-SHA, unplanned, or zero-denominator results cannot pass. Pull-request jobs declare read-only repository contents access and receive no secrets; pinned actions use full commit SHAs.
- Added focused verifier selectors and adversarial local tests for classifier behavior, lane evidence, workflow authority, and aggregate outcomes.
- The full local verifier passed at source revision `78045c5d18e3dd45f6702067438a330412932b1f`: 63 lane executions, 1,154,987 assertions, no failed lanes, and four unknown dimensions. ASan/UBSan passed 8 tests; TSan passed 2 serialized tests. The receipt is retained in `evidence/sdk/verification.json`.
- The committed-head local matrix run at `2054c3d6d07427d0e4a045b2388bcc933478bec9` passed 36 diagnostic cases and 1,440 assertions over nine lane executions, including installed static/shared consumers. Its local host record is deliberately `unknown` with zero qualifying support assertions because it has no GitHub hosted runner identity. Local measurements were 9.374 seconds lane duration and 1.636 seconds cold build; these are not hosted critical-path or runner-minute measurements.
- The bounded local public-content scan passed over one captured machine-readable receipt, 92 source files, and 58,695 bytes of reachable history metadata. `detector_negative_only` remains true; this does not establish absence of all sensitive content.

## Task Commits

1. **Task 1: Produce exact matrix identities and support outcomes** — `672d738`.
2. **Task 1 evidence correction: require exact clean hosted lane identities** — `5f2fa01`.
3. **Task 2: Run a conservative required CI aggregate** — `587faff`.
4. **Docs-consumer integration correction: stage the real release manifest** — `78045c5`.
5. **Retain current-source verifier receipt** — `2054c3d`.

## Verification and Evidence

- `python3 tests/sdk/test_matrix_evidence.py` passed positive and adversarial matrix controls.
- `python3 tests/workflow/test_ci_policy.py` passed classifier and aggregate controls; `python3 tools/verify_sdk.py --suite ci-policy` passed both focused test programs.
- `actionlint .github/workflows/ci.yml`, Python compilation, and `git diff --check` passed.
- The first required full verifier attempt exposed a docs-consumer fixture omission: its isolated project copy lacked the tracked `.release-please-manifest.json`, now the real CMake version input. The run failed in docs-static/docs-shared before qualification; the failed observation was retained in `build/sdk-debug/verify-sdk/logs/all-failed.log` and `baseline-failed.log` as local ignored diagnostics. `tests/consumers/check_package.py::stage_documentation_project` now copies that exact tracked manifest. The affected docs suite passed all three cases with 136 assertions, and the one required full-verifier rerun passed at `78045c5`.
- No Linux, Windows, or hosted macOS lane was run. No configured repository workflow run, account protection state, hosted critical path, or runner-minute measurement is claimed. BUILD-04, DEL-01, and DEL-02 remain pending for those hosted observations.

## Deviations from Plan

**1. [Rule 1 - Blocking integration defect] Included the release manifest in isolated docs-consumer projects.**
- **Found during:** Task 2 full verification.
- **Issue:** Plan 03-01 made `.release-please-manifest.json` the actual package-version input; the existing docs-consumer staging helper omitted it, causing isolated static/shared CMake configuration to fail.
- **Fix:** Copy the tracked manifest into the temporary docs project and rerun the docs suite and full verifier.
- **Files modified:** `tests/consumers/check_package.py`.
- **Commit:** `78045c5`.

## Decisions Made

- Keep local diagnostics distinct from hosted support: a local host observation is unknown as matrix qualification until a GitHub job ID and exact hosted image identity are recorded.
- Leave all hosted platform and account-level requirements pending; no hosted authority was available or implied.

## Self-Check: PASSED

- All plan artifacts exist; task commits `672d738`, `5f2fa01`, `587faff`, `78045c5`, and `2054c3d` are ancestors of `2054c3d`.
- The full local verifier receipt binds source revision `78045c5`; the separately measured local matrix binds source revision `2054c3d` and remains unqualified for hosted support.
