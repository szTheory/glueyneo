---
phase: "03"
slug: "distributable-release-qualification"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: validated
nyquist_compliant: false
wave_0_complete: true
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
| **Quick run command** | `python3 tests/workflow/test_ci_policy.py` |
| **Full suite command** | `python3 tools/verify_sdk.py` (all phase selectors and verifier suites) |
| **Estimated runtime** | Largest focused suite: 6.507 seconds; five other focused suites completed in a 4.7-second parallel batch. The latest local SDK matrix subset took 2.96 seconds and consolidated local suite took 20.359 seconds; hosted CI run elapsed 108 seconds. |

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
| 03-01-T1 | 03-01 | 1 | BUILD-03, DEL-03/04 | T-03-01 | Offline source rebuild and relocated real consumer from release bytes | Package integration | `python3 tests/consumers/test_release_consumer.py` | ✅ | ✅ green (5 tests) |
| 03-01-T2 | 03-01 | 1 | BUILD-03 | T-03-01 | All three shared formats enforce exact exports | Export integration | `python3 tests/consumers/test_exports.py` | ✅ | ✅ green (12 tests) |
| 03-02-T1 | 03-02 | 1 | DEL-05 | T-03-03/04 | Bounded redacted scan of tree/history/log/archive | Security controls | `python3 tests/workflow/test_public_content.py` | ✅ | ✅ green (17 tests) |
| 03-02-T2 | 03-02 | 1 | DEL-05 | T-03-05 | Inventory and notice gate rejects unapproved bytes | Security controls | `python3 tests/workflow/test_public_content.py` | ✅ | ✅ green (17 tests) |
| 03-03-T1 | 03-03 | 2 | BUILD-04 | T-03-07 | Exact identities/outcomes and positive denominators | Evidence validation | `python3 tests/sdk/test_matrix_evidence.py` | ✅ | ✅ green |
| 03-03-T2 | 03-03 | 2 | DEL-01/02 | T-03-06/08 | Unknown diff runs all; empty/missing lane fails aggregate; PR read-only | Workflow controls | `python3 tests/workflow/test_ci_policy.py` | ✅ | ✅ green |
| 03-04-T1 | 03-04 | 3 | DEL-03 | T-03-09 | Wrong/incomplete draft and retry cannot publish | State-machine integration | `python3 tests/workflow/test_release_recovery.py` | ✅ | ✅ green (10 tests) |
| 03-04-T2 | 03-04 | 3 | DEL-04 | T-03-10/11 | Downloaded digests and real consumer precede publish | Package integration | `python3 tests/consumers/test_release_consumer.py` | ✅ | ✅ green (5 local tests); hosted download pending in 03-05-T2 |
| 03-05-T1 | 03-05 | 4 | DEL-02 | T-03-12/14 | Stale SHA/review and unsupported claim fail | Workflow controls | `python3 tests/workflow/test_ci_policy.py` | ✅ | ✅ green |
| 03-05-T2 | 03-05 | 4 | DEL-02/03/04/05 | T-03-13 | Real fork/App/ruleset/event/release receipts | Hosted integration | External live receipt; precondition blocks if authority absent | ✅ receipt documented | ⬜ manual-only; external evidence pending |

### Current audit evidence (2026-10-07)

Focused suites were rerun at working-tree source revision `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1`: release consumer 5/5, exports 12/12, public-content 17/17, matrix-evidence controls passed, CI-policy controls passed, and release-recovery 10/10. These checks cover local behavior; they do not replace hosted release events.

The working-tree public-content scan passed with no findings: 99 source files / 2,173,339 bytes, 1,168 reachable history objects / 30,489,834 bytes, and 21 affirmative rights-inventory entries. This is detector-negative-only; no release archives or CI logs were supplied.

The current PR-head CI run [37618668537](https://github.com/szTheory/glueyneo/actions/runs/37618668537) passed at exact SHA `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1`: six matrix lanes, public-content, and `ci-policy`. GitHub timestamps record 108 seconds run elapsed and 2.72 summed job-wall minutes; no billing estimate is inferred.

The post-review local SDK matrix subset passed at source revision `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1` with documentation/planning edits in the working tree and relevant-source digest `7dbfb63af99aaa240e3c4dfed75731b296c77652fd2c9f3b973ff92afa272fef`: 36 cases, 1,440 assertions, and nine lane executions in 2.960 seconds. Identity was AppleClang 21.0.0.21000101, macOS arm64 (`Darwin-26`), CMake 4.4.3, Ninja 1.13.2, Debug/NONE; this local run does not extend hosted or platform-range claims.

The consolidated `python3 tools/verify_sdk.py` run also passed at source revision `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1` and the same relevant-source digest. It recorded 73 lane executions, 1,154,997 assertions, and 20.359 seconds, including ASan/UBSan 8/8 and TSan 2/2. The refreshed `evidence/sdk/verification.json` has SHA-256 `a36b2885cd506c1692def371bb930f0f48485ba2d4dcb1d4435948c66625e9cf`. One libFuzzer dimension remains unsupported and four dimensions remain unknown as recorded in the receipt; this local SDK result does not qualify hosted release behavior.

After correcting `docs/testing.md`, `python3 tests/workflow/test_public_content.py` passed 17/17 and the bounded scan passed with no findings (99 source files / 2,174,290 bytes; 1,168 available history objects / 30,489,834 bytes; 21 rights-inventory items). `python3 tests/workflow/test_ci_policy.py` also passed its conservative-classification and aggregate controls.

The configured regression command `ctest --preset owned-debug --output-on-failure` completed with 12/13 passing. The sole failure was the previously recorded frozen Phase 01 `owned_cpu_inventory_check`: its source manifest and hashes are stale for later CMake, preset, and experiment-source changes. Phase 02 records this limitation in `02-VERIFICATION.md`; the baseline was preserved, and this result is not reported as a passing regression gate.

---

## Test-first task prerequisites

The summaries record explicit RED/GREEN evidence for Plans 03-01 and 03-02, and a TDD red-phase failure followed by passing recovery tests for 03-04. Plan 03-03 and Plan 03-05 summaries record passing controls but do not preserve a per-task RED receipt; this audit does not infer one from a green result.

- [x] 03-01-T1/T2 release-consumer and export controls have recorded RED/GREEN evidence.
- [x] 03-02-T1/T2 scanner canaries and rights controls have recorded RED/GREEN evidence.
- [ ] 03-03-T1/T2 matrix and classifier RED receipts are not recorded in the summaries.
- [ ] 03-04-T1/T2 recovery and downloaded-byte controls have passing results; only the recovery suite's RED phase is explicitly recorded.
- [ ] 03-05-T1 current-SHA policy RED receipt is not recorded; 03-05-T2 requires external hosted evidence.

These are evidence-record gaps, not observed test failures. TDD mode was disabled for phase-level enforcement.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Qualify first-time fork approval and the read-only/no-secret boundary; independent latest-head review and protected merge; Release App scope/token lifetime/revocation; Release Please draft/retry and downloaded platform consumers; exact published assets and rights scan | DEL-02/03/04/05 | These outcomes require external contributor/reviewer actors, repository authority, and actual hosted release bytes; local fixtures and configuration APIs cannot establish event behavior or publication | Arrange a first-time fork contributor and a reviewer other than the PR author/latest pusher. Capture the workflow approval/run, current-head CI and GSD review, protected merge, scoped App token evidence without values, staged-draft retry, downloaded archive digests/consumers, final scanner receipt, and publication at the tested source SHA. Until then, keep only affected hosted claims pending as recorded in `03-HOSTED-QUALIFICATION.md`. |

All other phase behaviors should have automated local, CI, package, or downloaded-artifact verification. Do not substitute local static checks for these external authority/rights observations.

---

## Validation Sign-Off

- [x] All plan tasks have `<automated>` verify steps or documented external evidence dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Per-task RED receipts are incomplete for 03-03 and 03-05 and partial for 03-04; no missing automated tests were found.
- [x] No watch-mode flags.
- [x] Focused feedback latency and consolidated local-suite duration measured.
- [x] Task IDs, plan assignments, waves, and threat references reconciled to final plans.
- [ ] `nyquist_compliant: true` is withheld while hosted evidence and RED-receipt gaps remain.

**Approval:** partial — automated controls pass; hosted evidence and several historical RED receipts remain pending.

## Validation Audit 2026-10-07

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 0 |
| Escalated | 1 |
