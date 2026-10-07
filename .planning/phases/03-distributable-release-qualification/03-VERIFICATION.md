---
phase: 03-distributable-release-qualification
verified: 2026-10-07T12:49:51Z
status: gaps_found
score: 13/20 must-haves verified
covered_files:
  - ".github/workflows/ci.yml"
  - ".github/workflows/release.yml"
  - ".planning/phases/03-distributable-release-qualification/03-01-PLAN.md"
  - ".planning/phases/03-distributable-release-qualification/03-01-SUMMARY.md"
  - ".planning/phases/03-distributable-release-qualification/03-02-PLAN.md"
  - ".planning/phases/03-distributable-release-qualification/03-02-SUMMARY.md"
  - ".planning/phases/03-distributable-release-qualification/03-03-PLAN.md"
  - ".planning/phases/03-distributable-release-qualification/03-03-SUMMARY.md"
  - ".planning/phases/03-distributable-release-qualification/03-04-PLAN.md"
  - ".planning/phases/03-distributable-release-qualification/03-04-SUMMARY.md"
  - ".planning/phases/03-distributable-release-qualification/03-05-PLAN.md"
  - ".planning/phases/03-distributable-release-qualification/03-05-SUMMARY.md"
  - ".planning/phases/03-distributable-release-qualification/03-HOSTED-QUALIFICATION.md"
  - ".planning/phases/03-distributable-release-qualification/03-RELEASE-APP-SETUP.md"
  - ".planning/phases/03-distributable-release-qualification/03-REVIEW.md"
  - ".planning/phases/03-distributable-release-qualification/03-SECURITY.md"
  - ".planning/phases/03-distributable-release-qualification/03-VALIDATION.md"
  - ".release-please-manifest.json"
  - "CMakeLists.txt"
  - "docs/evidence-schema.md"
  - "docs/public-content.md"
  - "docs/releasing.md"
  - "docs/rights-inventory.md"
  - "docs/testing.md"
  - "evidence/sdk/verification.json"
  - "release-please-config.json"
  - "tests/consumers/check_package.py"
  - "tests/consumers/test_exports.py"
  - "tests/consumers/test_release_consumer.py"
  - "tests/sdk/test_matrix_evidence.py"
  - "tests/workflow/test_ci_policy.py"
  - "tests/workflow/test_public_content.py"
  - "tests/workflow/test_release_recovery.py"
  - "tools/public_content.py"
  - "tools/release_manifest.py"
  - "tools/release_state.py"
  - "tools/sdk_evidence.py"
  - "tools/verify_sdk.py"
  - "tools/workflow/ci_policy.py"
covered_digest: "v3:sha256:1b33b30d77f25418ea0962c974f51c2e3e2d96a184234c0b519995e5855f1193"
behavior_unverified: 1
overrides_applied: 0
gaps:
  - truth: "A release consumer can download the complete unsigned SDK for the tested commit and reproduce its diagnostic, including offline source rebuild and relocation."
    status: failed
    reason: "Local generated-archive rebuild/relocation passes, but no complete SDK has been staged or published for a release consumer to download and verify."
    artifacts:
      - path: ".github/workflows/release.yml"
        issue: "The staged-download-consumer-publication graph exists but has never run with the configured repository App and an actual release draft."
      - path: ".planning/phases/03-distributable-release-qualification/03-HOSTED-QUALIFICATION.md"
        issue: "Receipt explicitly records no staged or published release and no downloaded release assets."
    missing:
      - "Exercise the release workflow at the exact tested versioned commit, stage all expected assets, download and verify them, then publish and verify the public download."
  - truth: "Qualifying PRs merge through protection only after current-revision checks and independent review, with fork and App event behavior qualified."
    status: failed
    reason: "Exact-head hosted CI passed and protection settings were observed, but PR #1 remains draft with no reviews and no protected merge; no first-time fork approval/run or App event was observed."
    artifacts:
      - path: ".planning/phases/03-distributable-release-qualification/03-HOSTED-QUALIFICATION.md"
        issue: "Pending evidence table names the fork boundary, independent protected merge, and App authority/event chain."
    missing:
      - "Obtain a first-time fork run and workflow approval, an independent final-head review, and an observed protected merge with receipts bound to the same SHA."
      - "Exercise the Release App's effective scope and the release-please draft/retry/downstream event chain without recording credentials."
  - truth: "Release content and rights evidence covers the source, documentation, commit identity, CI logs, and distributed archives before publication."
    status: failed
    reason: "The current source/history scan and rights inventory pass, but there are no release archives or published assets to scan; known scanner blind spots for Windows home paths and OpenPGP private-key armor are also documented in review."
    artifacts:
      - path: "tools/public_content.py"
        issue: "Current detector does not recognize the documented Windows home-path and OpenPGP private-key header probes."
      - path: ".planning/phases/03-distributable-release-qualification/03-HOSTED-QUALIFICATION.md"
        issue: "No release archives or published downloads exist to bind to the scan receipt."
    missing:
      - "Close or explicitly accept the documented detector gaps, then scan the exact staged archives, captured CI logs, source/history, and rights inventory before publication."
behavior_unverified_items:
  - truth: "A trusted hosted release run builds the exact versioned commit, stages the complete draft, and wires downloaded-byte verification through to App-authorized publication."
    test: "Run the release workflow on the trusted repository with the configured App, exercise a fresh draft and a no-new-release retry, and inspect the downloaded assets before publication."
    expected: "The tag, build, manifest, draft, assets, downloaded bytes, consumers, and final publication all bind to the same tested commit; incomplete or changed assets stop publication."
    why_human: "Local fixtures and static workflow checks cannot establish GitHub App permissions, event delivery, stored draft state, or actual published bytes."
---

# Phase 03: Distributable Release Qualification Verification Report

**Phase Goal:** As a release consumer, I want to download a complete unsigned SDK bound to a tested commit and rebuild or relocate it, so that I can reproduce its diagnostic under truthful support claims.
**Verified:** 2026-10-07T12:49:51Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## User Flow Coverage

User story: «As a release consumer, I want to download a complete unsigned SDK bound to a tested commit and rebuild or relocate it, so that I can reproduce its diagnostic under truthful support claims.»

| Step | Expected | Evidence | Status |
|------|----------|----------|--------|
| Obtain the SDK | A complete unsigned SDK archive is available for a versioned, tested commit. | `tools/release_manifest.py` builds deterministic host archives; release workflow stages Linux, macOS, and Windows assets. Hosted receipt says no draft or release was staged or published. | ✗ FAILED |
| Relocate and run | The installed diagnostic and C/C++ consumers work after source, build, and install paths are unavailable. | Local generated-archive consumer checks passed; `03-VALIDATION.md` records release consumer 5/5 at source `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1`. | ✓ VERIFIED (local generated bytes) |
| Rebuild source offline | The exact release source archive rebuilds without network access. | Same local consumer test rebuilds extracted source with FetchContent disconnected. No published release source archive has been downloaded. | ✓ VERIFIED (local generated bytes) |
| Reproduce under truthful claims | A consumer can identify support evidence and reproduce the diagnostic from the downloaded release. | Hosted CI run 37618668537 passed at `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1`; no downloadable release exists, so the story's outcome is not available to a release consumer. | ✗ FAILED |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | **Roadmap:** A consumer runs the relocated installed diagnostic, rebuilds the release source archive offline, and can identify exercised support combinations and explicit failed/skipped/unsupported/untested cases. | ✗ FAILED | Local archive tests and exact support records exist, but no complete SDK or source archive has been released for download; local generated bytes do not fulfill the release-consumer entry step. |
| 2 | **Roadmap:** An always-started aggregate CI check uses conservative change classification, meaningful counts, and recorded build/critical-path/runner-minute evidence. | ✓ VERIFIED | CI run 37618668537 passed classify, six matrix lanes, public-content, and `ci-policy` at the exact current SHA. Receipt records 108 s end-to-end and 163 s summed job wall time; detailed per-lane cold-build and verification timings are retained for run 37525280735. |
| 3 | **Roadmap:** Protected qualifying PRs require current-revision checks and independent review; fork/App events and actual protected merge demonstrate unattended operation. | ✗ FAILED | Branch protection configuration was read and exact-SHA CI/review evidence is documented, but PR #1 remains draft with no reviews; no independent approval, protected merge, first-time fork run, or App event qualification occurred. |
| 4 | **Roadmap:** Release-please stages/recoveries a complete tested-commit draft, and published downloads pass digest and diagnostic consumer checks. | ✗ FAILED | Workflow, state validator, and adversarial recovery tests exist. No hosted draft, no-new-release retry, downloaded release assets, or publication was exercised. |
| 5 | **Roadmap:** Public-content evidence covers source, documentation, commit identity, logs, and release archives before publication. | ✗ FAILED | Current source/history scan and rights inventory pass, but no release archive or published bytes were scanned; review also reproduces Windows home-path and OpenPGP-key-header detector misses. |
| 6 | **Plan 03-01:** A consumer can rebuild the exact source archive offline and run the diagnostic from a relocated SDK archive after original paths are unavailable. | ✓ VERIFIED | Local release consumer suite validates safe extraction, offline source rebuild, moved install prefix, diagnostic runner, and compiled C/C++ consumers; 5/5 passed in current validation. |
| 7 | **Plan 03-01:** The root release-please manifest controls CMake project and installed package versions. | ✓ VERIFIED | `CMakeLists.txt` reads `.release-please-manifest.json` before `project()`; manifest/version tests pass in `tests/consumers/test_release_consumer.py`. |
| 8 | **Plan 03-01:** Shared exports enforce the exact public/private symbol contract on Linux, macOS, and Windows, failing without an inspector. | ✓ VERIFIED | Export parser and fail-closed controls are wired through `tests/consumers/check_package.py`; current validation records 12/12 export tests and hosted Windows matrix success. |
| 9 | **Plan 03-02:** Source, publishable metadata, bounded CI logs, and release archives are scanned with deterministic redacted results. | ✗ FAILED | Scanner handles these input classes and source/history/CI receipts were scanned, but an actual release archive was not produced; detector limitations for Windows home paths and OpenPGP private-key armor are reproduced in the review. |
| 10 | **Plan 03-02:** Unknown media/corpus items or missing affirmative redistribution records prevent packaging. | ✓ VERIFIED | `tools/public_content.py` compares path, digest, provenance, rights, and notices; local rights-inventory tests passed and current inventory reports 21 items. |
| 11 | **Plan 03-02:** Unreadable input, archive links/traversal, or size/count overflow cannot pass cleanly. | ✓ VERIFIED | Scanner mutation tests exercise archive member safety, limits, unreadable inputs, and redacted findings; 17/17 passed in current validation. |
| 12 | **Plan 03-03:** Exact Linux Clang/GCC, macOS arm64 AppleClang, Windows x64 MSVC, sanitizer, and fuzz configurations run diagnostics and installed consumers. | ✓ VERIFIED | Hosted runs 37525280735 and 37618668537 retain passing six-lane results; run 37618668537 is exact current SHA. Unsupported and unknown dimensions remain explicit. |
| 13 | **Plan 03-03:** Required aggregate starts for each PR/push and unknown paths or diff errors select all lanes. | ✓ VERIFIED | `.github/workflows/ci.yml` has unconditional PR/push triggers and `ci-policy`; focused policy tests passed, and exact hosted aggregate passed. |
| 14 | **Plan 03-03:** Support rows name exact identities, outcomes, positive denominators, and measured durations. | ✓ VERIFIED | Hosted receipt and `docs/testing.md` provide six exact identities, assertion counts, cold-build and verifier durations, plus workflow/job-wall timings and explicit limits. |
| 15 | **Plan 03-04:** A serialized release run builds/tests the exact versioned commit before its draft can be published. | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Workflow jobs and dependencies encode the ordering, but no hosted release run exercised this cross-job state transition. See behavior-unverified item. |
| 16 | **Plan 03-04:** Existing-draft retry with no new release output is safe only for the exact target, version, asset set, and hashes. | ✓ VERIFIED | `tests/workflow/test_release_recovery.py` exercises exact identity, partial resume, mismatches, duplicates, and no-new-output lookup; 10/10 passed. |
| 17 | **Plan 03-04:** Downloaded staged assets pass digest, offline rebuild, relocated consumer, and public-content gates before publication. | ✗ FAILED | Local synthetic byte and consumer tests pass, and the workflow graph wires the gates; no actual staged release assets were downloaded or published. |
| 18 | **Plan 03-05:** The exact PR SHA has passing aggregate checks and a separate GSD review with findings resolved or evidenced before protected merge. | ✓ VERIFIED | Current head is `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1`; hosted run 37618668537 and the final review section are bound to that SHA, with no open findings. The later merge itself remains unobserved. |
| 19 | **Plan 03-05:** Hosted fork/App/ruleset/merge/release claims are made only when actual receipts support them. | ✓ VERIFIED | Hosted qualification and setup checkpoint distinguish read-only observed configuration and owner-reported App setup from unobserved permissions, events, actors, merge, and publication. |
| 20 | **Plan 03-05:** Documentation states exact support identities, measured CI costs, scanner limits, and pending authority/rights questions. | ✓ VERIFIED | `docs/testing.md`, `docs/releasing.md`, hosted qualification, and release App setup record exact identities, durations, detector limits, and pending evidence. |

**Score:** 13/20 truths verified (1 present, behavior-unverified)

### Required Artifacts

All 18 plan-declared artifacts exist and contain substantive implementation or evidence. “Verified” below means existence, substantive content, and local wiring; it does not imply a hosted release occurred.

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tools/release_manifest.py` | Deterministic, manifest-bound source/SDK archive builder | ✓ VERIFIED | Builds exact-commit archives, emits digests/identity, safe extraction and local offline rebuild; consumed by release workflow. |
| `tests/consumers/test_release_consumer.py` | Offline rebuild and relocated SDK consumer | ✓ VERIFIED | Exercises archive extraction, moved install prefix, diagnostic runner and C/C++ consumers; 5/5 current. |
| `tests/consumers/test_exports.py` | Cross-format export contract controls | ✓ VERIFIED | Parser and fail-closed fixtures; 12/12 current. |
| `.release-please-manifest.json` | Sole package/release version source | ✓ VERIFIED | Read by CMake and release control. |
| `tools/public_content.py` | Bounded, redacted public-content and rights scanner | ✓ VERIFIED | Tests and CI/release workflow use it; documented detector misses remain. |
| `tests/workflow/test_public_content.py` | Scanner, archive, canary, and rights controls | ✓ VERIFIED | 17/17 current validation. |
| `docs/public-content.md` | Scanner scope, limits, and invocation contract | ✓ VERIFIED | Documents detector scope and limits. |
| `docs/rights-inventory.md` | Item-level redistribution evidence | ✓ VERIFIED | Current inventory contains 21 entries and validates locally. |
| `tools/workflow/ci_policy.py` | Conservative path selection and merge-readiness policy | ✓ VERIFIED | Classifier and exact-SHA policy are exercised by tests and CI workflow. |
| `.github/workflows/ci.yml` | Matrix and always-started aggregate | ✓ VERIFIED | Wired to classifier, matrix, scanner, and `ci-policy`; exact current hosted run passed. |
| `tests/workflow/test_ci_policy.py` | CI and merge-policy adversarial checks | ✓ VERIFIED | Passed current validation; hosted review/merge authority remains external. |
| `tests/sdk/test_matrix_evidence.py` | Exact-identity and denominator schema controls | ✓ VERIFIED | Local validation passed positive/adversarial cases. |
| `tools/release_state.py` | Draft identity/retry and downloaded-byte validator | ✓ VERIFIED | Used by release workflow and tested with fake API/download fixtures. |
| `tests/workflow/test_release_recovery.py` | Release state and retry tests | ✓ VERIFIED | 10/10 current validation. |
| `.github/workflows/release.yml` | Serialized staging, downloaded-byte verification, gated publication | ⚠️ PRESENT — HOSTED BEHAVIOR UNVERIFIED | Static graph and policy are substantive; no actual App-authorized run or draft was exercised. |
| `docs/releasing.md` | Release and protected-merge contract | ✓ VERIFIED | Describes required gates and accurately labels hosted gaps. |
| `docs/testing.md` | Exact support and timing evidence | ✓ VERIFIED | Lists exact supported observations and explicit unknown/unsupported cases. |
| `.planning/phases/03-distributable-release-qualification/03-HOSTED-QUALIFICATION.md` | Hosted authority and release receipts | ✓ VERIFIED | Records exact hosted CI runs and pending actors/events/assets; no release receipt is claimed. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `.release-please-manifest.json` | CMake project/package version | Configure-time manifest parse in `CMakeLists.txt` | WIRED | Project and installed package consume the same version source. |
| `tools/release_manifest.py` | Offline/relocated consumer | Archive build → bounded extraction → source rebuild → moved package consumer | WIRED | Local integration suite exercises the path end to end. |
| `tools/public_content.py` | Rights inventory and notices | Path/digest/provenance/notice validation | WIRED | Scanner tests and actual source scan use the inventory. |
| `.github/workflows/release.yml` | Public-content gate | Publication job depends on scanner/rights job | WIRED | Gate is in the workflow graph; no hosted release execution. |
| `tools/workflow/ci_policy.py` | CI matrix and aggregate | Classifier outputs lane plan; aggregate validates completed jobs/evidence | WIRED | Focused tests and exact hosted CI run pass. |
| `.github/workflows/ci.yml` matrix jobs | Diagnostic and installed consumers | `tools/verify_sdk.py` lane selectors | WIRED | Six hosted lanes report positive evidence. |
| Manifest and tested SHA | Release tag/build/draft/assets | Release-control job and `release_state.py` identity checks | WIRED | Code path is present; actual tag/draft behavior not observed. |
| Staged bytes | Downloaded verification and publication | Same workflow `needs`, fresh download jobs, final revalidation | WIRED | Static graph is present; no staged bytes or publication exist. |
| Required aggregate and independent GSD review | Proposed PR head SHA | Merge-readiness validator | WIRED | Both current receipts are for `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1`; no protected merge was observed. |
| Hosted App/event receipt | Published assets and tested SHA | Trusted workflow execution | NOT WIRED TO OBSERVED EVIDENCE | Setup is reported and secret name/App ID variable checked; permission scope, events, downloads, and published asset digest remain absent. |

### Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces real data | Status |
|---|---|---|---|---|
| `tools/verify_sdk.py` → matrix receipt | lane cases/assertions, source/build identity | Executed diagnostics and installed consumers on hosted runners | Yes; current hosted run and prior detailed receipt contain positive counts | ✓ FLOWING |
| `tools/release_manifest.py` → release manifest | archive names, sizes, SHA-256, commit/version | Final archive bytes and Git commit | Yes for local generated archives; no release assets exist | ⚠️ STATIC FOR HOSTED RELEASE |
| `tools/release_state.py` → publication decision | target, version, asset inventory/digests | GitHub release API and downloaded files | Fixture-backed locally; no live API/draft/download input | ⚠️ NO HOSTED DATA |
| `tools/public_content.py` → content verdict | source/history/log/archive counts and findings | Supplied source, history, logs, and archive bytes | Yes for current source/history and supplied receipts; no release archives supplied | ⚠️ INCOMPLETE INPUT SET |

### Behavioral Spot-Checks

| Behavior | Command/evidence | Result | Status |
|---|---|---|---|
| Offline source rebuild and relocated installed diagnostic/consumers | `python3 tests/consumers/test_release_consumer.py` (validation receipt at exact SHA) | 5/5 passed | ✓ PASS |
| Public-content and rights fail-closed controls | `python3 tests/workflow/test_public_content.py` | 17/17 passed; current source/history scan had no findings and 21 rights items | ✓ PASS (bounded inputs) |
| Shared export contract | `python3 tests/consumers/test_exports.py` | 12/12 passed; hosted Windows lane passed | ✓ PASS |
| Draft identity and interrupted/no-new-release retry state | `python3 tests/workflow/test_release_recovery.py` | 10/10 passed against fixture API states | ✓ PASS (local state logic) |
| Current hosted required aggregate | GitHub run 37618668537 at `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1` | classify, six matrix lanes, public-content, and `ci-policy` passed | ✓ PASS (this exact SHA only) |
| Consolidated native SDK verifier | `python3 tools/verify_sdk.py`, relevant-source digest `7dbfb63af99aaa240e3c4dfed75731b296c77652fd2c9f3b973ff92afa272fef` | 73 lane executions, 1,154,997 assertions, 20.359 seconds; receipt SHA-256 `a36b2885cd506c1692def371bb930f0f48485ba2d4dcb1d4435948c66625e9cf` | ✓ PASS (local SDK scope) |
| Preserved regression baseline | `ctest --preset owned-debug --output-on-failure` | 12/13; sole failure is frozen Phase 01 `owned_cpu_inventory_check` inventory/hash mismatch, previously documented | ✗ NOT GREEN; baseline retained |

The 36-case/1,440-assertion local AppleClang matrix subset also passed at the same source/digest identity. The hosted 37618668537 pass does not qualify release publication.

### Probe Execution

No phase-declared or conventional `scripts/*/tests/probe-*.sh` probes were found; this phase uses focused Python tests and hosted workflow evidence instead.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| BUILD-03 | 03-01, 03-04 | Offline source archive rebuild and relocated installed diagnostic consumer | SATISFIED LOCALLY | Current release consumer suite passed 5/5 with source/build/install paths removed; no published download is implied. |
| BUILD-04 | 03-03, 03-05 | Exact exercised compiler/SDK/OS/architecture/build variants and explicit outcomes | SATISFIED | Hosted six-lane evidence and exact identities/outcomes are documented; untested, unknown, and unsupported dimensions remain explicit. |
| DEL-01 | 03-03, 03-05 | Always-started aggregate, conservative classification, counts, measured CI costs | SATISFIED | Exact current hosted aggregate passed; 108 s end-to-end and 163 s summed job wall time are recorded, with detailed cold-build/lane timings in the earlier exact hosted receipt. |
| DEL-02 | 03-03, 03-05 | Protected current-revision merge, independent review, triage, and actual fork/App event qualification | BLOCKED | Configuration and current-SHA checks/review are evidenced, but independent approval/merge, first-time fork execution, and App event behavior are not. |
| DEL-03 | 03-01, 03-04, 03-05 | Pinned release-please stages a complete unsigned draft and recovers retries | PARTIAL | Manifest, pinned workflow, validator, and local recovery tests exist; no actual hosted draft or retry was observed. |
| DEL-04 | 03-01, 03-04, 03-05 | Wrong/incomplete release rejected; downloaded published assets pass digest and diagnostic checks | BLOCKED | Local synthetic asset controls pass, but no release assets were staged, downloaded, published, or verified. |
| DEL-05 | 03-02, 03-04, 03-05 | Source/docs/identity/logs/archives pass content and rights checks before publication | PARTIAL | Current source/history scan and rights inventory pass. Actual release archives are absent; documented Windows-home-path and OpenPGP-key-header probes are missed by current detector. |

All seven requirement IDs map to at least one plan; no phase-mapped requirement is orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `tools/public_content.py` | 45–55 (review locations) | Windows home-path and OpenPGP private-key headers are not detected by current patterns | ⚠️ WARNING | Synthetic probes reproduced misses; detector limits are documented. They reduce coverage for DEL-05 and should be resolved or explicitly accepted before a public release scan. |
| `ctest --preset owned-debug` baseline | — | Frozen Phase 01 inventory/hash mismatch | ℹ️ INFO | 12/13 result is preserved exactly; this is not reported as a passing regression gate. |

No unreferenced `TBD`, `FIXME`, or `XXX` debt markers were found in the phase implementation files. No release-ready placeholder or static empty user-facing output was found. No probe scripts were declared or discovered.

### Human Verification Required

These external steps remain required after local implementation gaps are addressed. They cannot be established by repository files or fixture APIs.

#### 1. Qualify the protected fork and merge path

**Test:** Have a first-time fork contributor open/update a PR, approve and inspect its workflow run, then obtain an independent reviewer’s final-head GSD review and merge through configured protection.
**Expected:** The fork run has read-only/no-secret authority; required aggregate and independent review bind to the same final SHA; the observed merge is protected and current.
**Why human:** It requires external contributor/reviewer actors and actual GitHub enforcement. Current PR #1 remains draft with no review.

#### 2. Qualify App-authorized release and downloaded bytes

**Test:** Exercise the trusted release workflow with the configured App, inspect effective repository scope and event behavior without exposing credentials, create and retry a draft, download all assets, and complete publication.
**Expected:** Exact tested commit/version, full expected asset set and hashes, offline source rebuild, all platform consumers, content/rights scan, and final published download agree.
**Why human:** Live App permissions, token lifecycle, Release Please events, GitHub draft state, and published bytes cannot be inferred from local tests. No release has been staged or published.

#### 3. Confirm the scanner’s residual detector coverage

**Test:** Decide whether the Windows home-path and OpenPGP private-key-header misses must be fixed before publication; if fixed, rerun their synthetic controls and the full exact-byte scan.
**Expected:** DEL-05 coverage is sufficient for the repository’s public-content policy, with the accepted detector limits explicit.
**Why human:** The exposure threshold is a policy decision; the specific misses themselves are reproducible in the independent review.

### Gaps Summary

The local SDK and archive path is implemented and exercised, exact support identities are recorded, and the required CI aggregate passed at the current SHA. The phase goal remains unmet because there is no complete unsigned SDK available to download and verify. Hosted protection has not produced an independent approval or protected merge, and the Release App flow has not produced a draft, retry, downloaded assets, or publication. The public-content gate has no release bytes to scan and retains two documented detector misses. The 12/13 `owned-debug` regression result remains visible; its frozen Phase 01 inventory/hash failure was not changed or recast as green.

---

_Verified: 2026-10-07T12:49:51Z_
_Verifier: the agent (gsd-verifier)_
