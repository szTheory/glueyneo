---
phase: 03-distributable-release-qualification
plan: 05
subsystem: release-qualification
tags: [github-actions, branch-protection, release-app, sdk-delivery]
requires:
  - phase: 03-distributable-release-qualification
    provides: Exact hosted CI evidence, SDK artifact recovery, and downloaded-consumer gates
provides:
  - Local exact-SHA merge-readiness policy and adversarial regression coverage
  - Updated release and project documentation with owner-reported App setup clearly distinguished from verified authority
  - Narrow hosted qualification checkpoint with remaining external evidence preserved
affects: [release, delivery, hosted-qualification]
actuals:
  tokens: 5107
  tasks: 1
  commits: 3
tech-stack:
  added: []
  patterns: [exact-SHA merge readiness, report hosted authority only from live evidence]
key-files:
  created: [.planning/phases/03-distributable-release-qualification/03-05-SUMMARY.md]
  modified: [tools/workflow/ci_policy.py, tests/workflow/test_ci_policy.py, docs/releasing.md, docs/testing.md, .planning/phases/03-distributable-release-qualification/03-HOSTED-QUALIFICATION.md]
key-decisions:
  - "A local passing merge-readiness policy test does not establish GitHub protection, an independent reviewer, or hosted merge authority."
  - "Record the owner's App setup report without treating it as direct evidence of permissions, secret values, token scope, or event behavior."
  - "Stop Plan 03-05 at its designed hosted-evidence gate until the first-time fork and independent reviewer are available."
patterns-established:
  - "Bind required aggregate and independent GSD review evidence to the exact proposed head SHA; refresh both after a head change."
  - "Keep owner-reported credential setup distinct from observed hosted authority, and never retain credential values."
requirements-completed: []
coverage:
  - id: D1
    description: Local merge-readiness policy rejects stale SHA evidence and requires exact-head checks plus independent review; actual protected-merge qualification remains pending.
    requirement: DEL-02
    verification:
      - kind: unit
        ref: python3 tests/workflow/test_ci_policy.py
        status: pass
      - kind: manual_procedural
        ref: First-time fork approval, current-head independent GitHub review, and observed protected merge
        status: unknown
    human_judgment: true
    rationale: The hosted repository must exercise external fork and reviewer actors; local policy tests cannot prove GitHub enforcement or authority.
  - id: D2
    description: Exact hosted SDK lane identities, assertion counts, aggregate outcome, and measured CI timing are recorded for the qualified source revision.
    requirement: BUILD-04
    verification:
      - kind: integration
        ref: https://github.com/szTheory/glueyneo/actions/runs/37525280735 at source 2c7926383222cee174ede5ddde06374b43002191; six lanes and ci-policy passed
        status: pass
    human_judgment: false
  - id: D3
    description: The hosted always-started CI aggregate passed with a positive denominator, and its measured run timing is recorded for the qualified source revision.
    requirement: DEL-01
    verification:
      - kind: integration
        ref: https://github.com/szTheory/glueyneo/actions/runs/37525280735 at source 2c7926383222cee174ede5ddde06374b43002191; ci-policy passed with recorded lane, assertion, and timing evidence
        status: pass
    human_judgment: false
  - id: D4
    description: Release App authority and Release Please event behavior are not yet directly observed; owner-reported setup is recorded without credential values.
    requirement: DEL-03
    verification:
      - kind: manual_procedural
        ref: Scoped installation permission, token lifetime/revocation, and trusted draft/retry workflow evidence
        status: unknown
    human_judgment: true
    rationale: These claims require live repository authority and workflow events; the owner report alone does not verify them.
  - id: D5
    description: Published archive digests, downloaded consumers, and final public-content checks remain unqualified because no release has been staged or published.
    requirement: DEL-04
    verification:
      - kind: manual_procedural
        ref: Exact tested release, downloaded archive hashes, platform consumers, and publication record
        status: unknown
    human_judgment: true
    rationale: Only actual release artifacts and their hosted verification can establish these delivery outcomes.
  - id: D6
    description: Public-content evidence for the staged and published release remains pending with the release artifact.
    requirement: DEL-05
    verification:
      - kind: manual_procedural
        ref: Release content scan and rights evidence bound to the staged archive and published bytes
        status: unknown
    human_judgment: true
    rationale: Local scanner behavior does not establish the contents or rights status of an artifact that has not yet been produced and published.
duration: not measured
completed: 2026-10-07
status: halted
plan_head_before: 5978661188aeb98b5774fcca3d4f2421d90cf5f8
plan_head_after: 00f7516ac4455a4eb3cd731ffbd5e676127d5911
---

# Phase 03 Plan 05: Exact-SHA merge policy and hosted authority checkpoint

**The local exact-SHA merge-readiness policy is covered by a passing regression, while hosted release qualification is intentionally halted with account and actor evidence still pending.**

## Accomplishments

- Completed Task 1's merge-readiness policy and adversarial controls. The command python3 tests/workflow/test_ci_policy.py passed after the documentation updates; the check retains its explicit current-head SHA, aggregate, independent-review, findings-disposition, and nonzero-count conditions.
- Preserved the exact hosted CI receipt at source `2c7926383222cee174ede5ddde06374b43002191`: six matrix lanes and the `ci-policy` aggregate passed, with measured identities, counts, and timing recorded in the hosted qualification file. This does not qualify a later SHA or a release.
- Re-ran python3 tools/public_content.py --root . --history-revision HEAD against the current working tree and selected history: pass, 99 source files, 1,161 history objects, 21 rights-inventory items, and no findings. The receipt remains detector-negative-only and does not cover release archives or logs that do not yet exist.
- Recorded the owner's 2026-10-07 report that App ID `5217741` is installed for `szTheory/glueyneo` and that the Actions secret and App ID variable are configured. This is reported setup only; the live permission grant, secret or variable values, effective token scope, expiry/revocation, and workflow events were not inspected.
- Corrected current project and release guidance that still described the App as nonexistent, while preserving historical dated review evidence and the distinction between setup and qualification.

## Task Commits

1. **Task 1: Enforce current-SHA review and truthful qualification reports** — `c43e402d444b8b25b2eef3fed515145c3f0ae545` (`feat(03-05)`).
2. **Task 2 hosted checkpoint** — `f5e04d90ef1542921233fce9c1a5589df21854bb` (`docs(03-05)`); records the planned stop for unavailable hosted evidence.
3. **Checkpoint formatting cleanup** — `e86110a5754f4dbdd66b400a7bf03b2d755029f3` (`style(03-05)`).

## Hosted Task Status

Task 2 reached its explicit precondition branch: a first-time fork contributor and an independent GitHub reviewer with approval authority are not available in this execution. The App setup report does not establish permission scope or release-event behavior. Therefore this plan is **halted**, not complete. No first-time fork workflow approval/run, independent approval, protected merge, Release Please draft/retry, downloaded platform consumer, or published release was exercised. Phase 03 is not complete, and the phase requirements remain pending.

The prior exact-hosted CI run and GSD review remain bound to their recorded source SHA. They do not authorize merging a changed head. The owner must arrange a first-time fork contributor and a reviewer who is not the PR author or latest pusher; after those actors are available, resume the hosted portion with `$gsd-execute-phase 03` and qualify every result at the then-current SHA.

## Issues Encountered

The safe-resume checkpoint found the three existing Plan 03-05 commits but no summary. The user selected manual closeout. This summary records the existing work and the plan's designed hosted-evidence stop without replaying committed implementation tasks.

## User Setup

The owner reports that the release App is installed and its repository Actions secret and App ID variable are configured. No credential material is stored in this summary. The remaining setup and qualification details are in [03-RELEASE-APP-SETUP.md](03-RELEASE-APP-SETUP.md).

## Next Phase Readiness

Phase 03 remains incomplete. The hosted work resumes only after a first-time fork contributor and an independent GitHub reviewer with approval authority are available; then the exact-head checks, protected merge, App event chain, release recovery, downloaded consumers, and publication still require actual receipts. Do not start phase verification or shipping from this halted plan.

---
*Phase: 03-distributable-release-qualification*
*Recorded: 2026-10-07*
