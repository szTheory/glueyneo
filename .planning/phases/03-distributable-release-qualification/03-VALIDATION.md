---
phase: "03"
slug: "distributable-release-qualification"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-06"
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Plan/task IDs and final wave assignments are filled from the verified plans before execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | CTest integrated with CMake; Python standard-library controlled collectors and scanner tests |
| **Config file** | `CMakePresets.json` (schema `2`; CMake floor `3.20`) |
| **Quick run command** | `python3 tools/verify_sdk.py` (use focused selectors as implemented) |
| **Full suite command** | `python3 tools/verify_sdk.py` plus the source-archive, consumer, scanner, classifier, workflow, and release-recovery suites added in this phase |
| **Estimated runtime** | Measure during the first complete local run; record actual critical path and runner minutes in CI evidence |

---

## Sampling Rate

- **After every task commit:** Run the focused new suite for the changed behavior and its existing relevant CTest/package suite.
- **After every plan wave:** Run `python3 tools/verify_sdk.py` plus workflow static validation and changed-path-classifier fixtures.
- **Before `$gsd-verify-work`:** Full local current-revision evidence must be green; all exercised matrix lanes must have positive denominators; downloaded release assets must pass digest, offline rebuild, relocation, and consumer checks.
- **Max feedback latency:** Measure focused and full-suite durations during implementation; preserve an explicit measured budget rather than inventing one.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| assigned from plan | assigned from plan | assigned from plan | BUILD-03 | — | Downloaded install works after original paths are absent; source archive rebuild is offline | Package integration | `python3 tools/verify_sdk.py --suite release-consumer` | ❌ Wave 0 | ⬜ pending |
| assigned from plan | assigned from plan | assigned from plan | BUILD-04 | — | Every lane records exact identity and distinct pass/fail/skipped/unsupported/unknown outcomes | Evidence validation | `python3 tools/verify_sdk.py --suite matrix` | ❌ Wave 0 | ⬜ pending |
| assigned from plan | assigned from plan | assigned from plan | DEL-01 | — | Unknown paths select every lane; missing/failed/cancelled lanes and zero assertions fail the aggregate | Unit + workflow integration | `python3 tools/verify_sdk.py --suite ci-policy` | ❌ Wave 0 | ⬜ pending |
| assigned from plan | assigned from plan | assigned from plan | DEL-02 | — | Fork PR jobs have no secrets/write permission; only latest-SHA checks and independent review permit protected merge | Hosted integration | Static workflow checks locally; hosted PR/fork/review/ruleset/App-event qualification on the configured repository | ❌ external hosted behavior | ⬜ pending |
| assigned from plan | assigned from plan | assigned from plan | DEL-03 | — | Retry accepts only a matching release target/version/asset set and digest; wrong or incomplete drafts cannot publish | State-machine integration | `python3 tools/verify_sdk.py --suite release-recovery` | ❌ Wave 0 | ⬜ pending |
| assigned from plan | assigned from plan | assigned from plan | DEL-04 | — | Digest mismatch, missing, extra, or replaced assets block publication; real downloaded consumer passes first | Adversarial package integration | `python3 tools/verify_sdk.py --suite release-consumer` plus hosted dry-run | ❌ Wave 0 / hosted | ⬜ pending |
| assigned from plan | assigned from plan | assigned from plan | DEL-05 | — | Scanner fails closed on limits/traversal, redacts match values, and rejects unapproved media/corpus | Unit + security integration | `python3 tools/verify_sdk.py --suite public-content` | ❌ Wave 0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] Windows DLL export inspection and fixture-backed expected-export tests.
- [ ] Matrix evidence schema/aggregator and conservative changed-path classifier controls.
- [ ] Public-content scanner with safe archive traversal, bounded IO, notices/inventory, and synthetic secret canaries.
- [ ] Source archive offline rebuild and relocated installed-artifact consumer using downloaded bytes.
- [ ] Release draft state-machine/retry cases for wrong target SHA, absent/extra asset, digest mismatch, no-new-release retry, and interruption between assets.
- [ ] Workflow syntax/security/static validation and a documented hosted qualification path.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confirm repository rules, required-check settings, GitHub App installation permissions, and actual fork approval/event behavior | DEL-02 | These facts are controlled by an external repository/account authority and cannot be established by local workflow tests | After repository/App configuration exists, run a fork PR and trusted PR through the actual event graph; inspect effective token permissions, required checks on the current SHA, independent review gate, and merge result. Keep DEL-02 pending until evidence is captured. |
| Confirm any unresolved fixture/dependency redistribution rights | DEL-05 | A scanner can inspect notices and provenance but cannot determine legal permission where the applicable rights are unknown | Obtain the specific license or written permission record for the exact shipped item; keep the item excluded and the rights claim unknown until then. |

All other phase behaviors should have automated local, CI, package, or downloaded-artifact verification. Do not substitute local static checks for these external authority/rights observations.

---

## Validation Sign-Off

- [ ] All plan tasks have `<automated>` verify steps or documented external evidence dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing test references.
- [ ] No watch-mode flags.
- [ ] Feedback latency recorded from measured runs.
- [ ] Task IDs, plan assignments, waves, and threat references reconciled to final plans.
- [ ] `nyquist_compliant: true` set only after validation evidence is complete.

**Approval:** pending
