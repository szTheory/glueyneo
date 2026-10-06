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

> Per-phase validation contract for feedback sampling during execution. IDs and waves match the Phase 03 plans. Missing test files are created first in their named task before the behavior is implemented; hosted receipts remain external.

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
| 03-01-T1 | 03-01 | 1 | BUILD-03, DEL-03/04 | T-03-01 | Offline source rebuild and relocated real consumer from release bytes | Package integration | `python3 tests/consumers/test_release_consumer.py` | ❌ create first in task | ⬜ pending |
| 03-01-T2 | 03-01 | 1 | BUILD-03 | T-03-01 | All three shared formats enforce exact exports | Export integration | `python3 tests/consumers/test_exports.py` | ❌ create first in task | ⬜ pending |
| 03-02-T1 | 03-02 | 1 | DEL-05 | T-03-03/04 | Bounded redacted scan of tree/history/log/archive | Security controls | `python3 tests/workflow/test_public_content.py` | ❌ create first in task | ⬜ pending |
| 03-02-T2 | 03-02 | 1 | DEL-05 | T-03-05 | Inventory and notice gate rejects unapproved bytes | Security controls | `python3 tests/workflow/test_public_content.py` | ❌ extend in task | ⬜ pending |
| 03-03-T1 | 03-03 | 2 | BUILD-04 | T-03-07 | Exact identities/outcomes and positive denominators | Evidence validation | `python3 tests/sdk/test_matrix_evidence.py` | ❌ create first in task | ⬜ pending |
| 03-03-T2 | 03-03 | 2 | DEL-01/02 | T-03-06/08 | Unknown diff runs all; empty/missing lane fails aggregate; PR read-only | Workflow controls | `python3 tests/workflow/test_ci_policy.py` | ❌ create first in task | ⬜ pending |
| 03-04-T1 | 03-04 | 3 | DEL-03 | T-03-09 | Wrong/incomplete draft and retry cannot publish | State-machine integration | `python3 tests/workflow/test_release_recovery.py` | ❌ create first in task | ⬜ pending |
| 03-04-T2 | 03-04 | 3 | DEL-04 | T-03-10/11 | Downloaded digests and real consumer precede publish | Package integration | `python3 tests/consumers/test_release_consumer.py` | ❌ extend in task | ⬜ pending |
| 03-05-T1 | 03-05 | 4 | DEL-02 | T-03-12/14 | Stale SHA/review and unsupported claim fail | Workflow controls | `python3 tests/workflow/test_ci_policy.py` | ❌ extend in task | ⬜ pending |
| 03-05-T2 | 03-05 | 4 | DEL-02/03/04 | T-03-13 | Real fork/App/ruleset/event/release receipts | Hosted integration | External live receipt; precondition blocks if authority absent | ❌ external | ⬜ pending |

---

## Wave 0 Requirements

- [ ] 03-01-T1/T2 create release-consumer and export controls before production behavior.
- [ ] 03-02-T1/T2 create scanner canaries and rights controls before production behavior.
- [ ] 03-03-T1/T2 create matrix and classifier controls before production behavior.
- [ ] 03-04-T1/T2 create release-retry and downloaded-byte adversarial controls before production behavior.
- [ ] 03-05-T1 extends current-SHA policy controls; 03-05-T2 requires external hosted evidence.

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
