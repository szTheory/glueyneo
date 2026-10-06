---
phase: 03-distributable-release-qualification
reviewed: 2026-10-06T18:31:37Z
depth: standard
files_reviewed: 26
files_reviewed_list:
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - CMakeLists.txt
  - tools/release_manifest.py
  - tools/release_state.py
  - tools/public_content.py
  - tools/sdk_evidence.py
  - tools/verify_sdk.py
  - tools/workflow/ci_policy.py
  - tests/consumers/check_package.py
  - tests/consumers/test_release_consumer.py
  - tests/sdk/test_matrix_evidence.py
  - tests/workflow/test_ci_policy.py
  - tests/workflow/test_public_content.py
  - tests/workflow/test_release_recovery.py
  - docs/public-content.md
  - docs/rights-inventory.md
  - .planning/phases/03-distributable-release-qualification/03-REVIEW-FIX.md
  - .planning/phases/01-cpu-acceptance-experiment/01-26-PLAN.md
  - .planning/phases/01-cpu-acceptance-experiment/01-29-PLAN.md
  - .planning/phases/02-executable-diagnostic-sdk/02-01-PLAN.md
  - .planning/phases/02-executable-diagnostic-sdk/02-02-PLAN.md
  - .planning/phases/02-executable-diagnostic-sdk/02-03-PLAN.md
  - .planning/phases/02-executable-diagnostic-sdk/02-04-PLAN.md
  - .planning/phases/02-executable-diagnostic-sdk/02-05-PLAN.md
  - .planning/phases/02-executable-diagnostic-sdk/02-06-PLAN.md
findings:
  critical: 2
  warning: 1
  info: 0
  total: 3
status: issues_found
reviewed_revision: 1ba5b3c75ba7bda878e652ecf13d8544c6510bc2
diff_base: 8ddebb9856e70e0e753e0747059b97a9a8e63a32
re_reviewed_revision: cb4834ed89e2422491387eb8ef4a2598fb5824dd
re_review_status: issues_found
re_review_open_findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
latest_reviewed_revision: 30d29dbc66d84cbeb500ed2029ce06f1667a74df
latest_review_status: issues_found
latest_open_findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
---

# Phase 03: Code Review Report

**Reviewed:** 2026-10-06
**Depth:** standard
**Files Reviewed:** 26
**Status:** issues_found
**Revision:** `1ba5b3c75ba7bda878e652ecf13d8544c6510bc2`

## Summary

Reviewed release archive construction, release recovery and download validation, CI aggregation, privacy/rights scanning, and consumer integration at the requested revision. The exact-SHA and downloaded-byte checks are present, but the publication gates do not inspect historical Git blob contents and can omit unclassified test assets from rights validation. These gaps are material for the stated public repository and redistribution boundary. Hosted CI lanes, repository protections, App token behavior, and publication remain pending as recorded by the phase; no hosted claims were inferred from local evidence. No tests or other commands were run during this review.

## Critical Issues

### CR-01: Historical file contents are outside the privacy scan

**Severity:** BLOCKER
**File:** `tools/public_content.py:320-331`
**Issue:** `_git_history` runs `git log` with author/committer metadata, subject, and message fields only. `scan_inputs` then scans that byte stream as `history/commit-metadata` (`tools/public_content.py:368-371`); it never scans blobs reachable from the refs that will be published. A credential, private ROM/BIOS, save state, capture, or private test output committed and later deleted therefore remains in the public Git history while the current source tree and metadata scan can pass. The release workflow also requests this metadata-only history scan (`.github/workflows/release.yml:305-314`). This defeats the public-content gate for material GitHub publishes even when it is absent from the current checkout.
**Reproduction:** Add a recognizable credential or private file to a commit, then remove it in a later commit. The final worktree and commit metadata contain no matched bytes, so current scan inputs do not include the leaked historical blob.
**Fix:** Scan reachable blob contents under explicit object-count and byte limits, including deleted paths and every ref exposed by publication, with fail-closed handling for omitted/oversized objects. If full history cannot be certified, require a sanitized-history publication policy and gate the repository publication on it.

### CR-02: Uncatalogued test assets bypass redistribution-rights validation

**Severity:** BLOCKER
**File:** `tools/public_content.py:164-169`
**Issue:** Rights candidates include every path under `fixtures/` and `third_party/`, but under `tests/` only names containing `fixture` with a short suffix allowlist qualify. The source archive includes the entire `tests/` tree (`tools/release_manifest.py:22-40`), and archive scanning applies the same heuristic (`tools/public_content.py:205-229`). Thus a binary test input such as `tests/cpu/title.bin` is included in the distributable source archive yet is not required to have an affirmative rights record; if it has no configured privacy-pattern match, the rights gate accepts it. This is not fail-closed for test media and allows unlicensed game/BIOS/corpus material to enter a release.
**Reproduction:** Place an arbitrary binary named `tests/cpu/title.bin` in the tracked source tree/archive. `_is_rights_candidate` returns false because its basename lacks `fixture`; the exact rights path-set comparison never sees it.
**Fix:** Explicitly classify every distributable test asset, rather than inferring rights relevance from filenames. For example, require an affirmative inventory row for every non-code or non-text asset under `tests/`, and reject unknown binary/media extensions before archive acceptance. Keep source-code fixture recipes separately inventoried where their provenance requires it.

## Warnings

### WR-01: CI privacy scan omits workflow source files

**Severity:** WARNING
**File:** `.github/workflows/ci.yml:137-145`
**Issue:** The normal pull-request `public-content` job runs the scanner without explicit paths or logs, so it uses `SOURCE_PATHS`, which does not include `.github/workflows/ci.yml` (see `tools/public_content.py:29-35`). A credential or private machine path introduced in the CI workflow can consequently pass the PR privacy job. The release-time manual scan includes `release.yml` but likewise does not include `ci.yml` (`.github/workflows/release.yml:305-314`). Workflow files are published with the repository even though they are not in the source SDK archive.
**Reproduction:** Add a detector-matching credential assignment to `ci.yml`; the CI job's source list does not read that file, and its captured-log inputs are not a substitute for scanning workflow source.
**Fix:** Add `.github/workflows` and relevant root release configuration files to the repository-publication scan scope, or pass them explicitly as scan inputs in CI and release jobs. Keep the source archive scope separate if those files are intentionally excluded from SDK packages.

## Evidence boundaries

- The phase's local test receipts and static workflow lint are documented in the phase summaries, but were not rerun as part of this review.
- A separate current-repository privacy sweep reported no detected user/private PII or credentials. CR-01 describes the repeatable workflow coverage gap for future or deleted blobs; it does not assert that a current private-data leak was found.
- Linux Clang/GCC, hosted macOS, Windows MSVC, sanitizer/fuzz hosted lanes, repository protection settings, GitHub App event/token authority, actual release download, and publication remain unobserved. The report does not treat them as passing or failing runtime checks.
- Working-tree edits outside this report were not changed.

---

_Reviewed: 2026-10-06_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_

## Re-review at `cb4834ed89e2422491387eb8ef4a2598fb5824dd`

**Re-review verdict:** The three original findings are resolved by the reviewed changes. One related redistribution-rights gap remains open (CR-04 below). This section supplements the original review; its original counts and findings above are retained as the historical first-pass record.

**Verification:** `python3 tests/workflow/test_public_content.py` passed all 12 tests in 3.366 seconds. A read-only scope check confirmed both `.github/workflows/ci.yml` and `.github/workflows/release.yml` are in the default repository scan path set and excluded from the SDK archive path set. The same check confirmed `tests/cpu/title.bin` is now a rights candidate while `tests/cpu/title.json` is not. No hosted checks or publication were performed.

### Original finding dispositions

- **CR-01 — RESOLVED.** `_git_history` now enumerates reachable objects and scans each unique blob body under explicit count and byte limits; missing or malformed object metadata and incomplete body reads fail closed. The focused deleted-file credential regression passed. Known history findings are limited by exact blob object ID, path, and observed rule set, and the report keeps those dispositions visible.
- **CR-02 — RESOLVED for the reported binary/unknown-extension gap.** Test paths outside the configured source/text suffix allowlist, including extensionless paths, now require affirmative rights records. Tree and archive regressions both reject the previously omitted `tests/cpu/title.bin` example.
- **WR-01 — RESOLVED.** The default repository scan path set includes `.github/workflows` and `release-please-config.json`, while the SDK archive path set remains independent. Both tracked workflow files were present in the enumerated repository scan paths.

## Critical Issues (open on re-review)

### CR-04: Text-suffixed test data still bypasses rights inventory

**Severity:** BLOCKER
**File:** `tools/public_content.py:40-43, 186-196`
**Issue:** `_is_rights_candidate` treats every file under `tests/` with a suffix in `TEST_TEXT_SUFFIXES` as rights-exempt unless its name contains `fixture`. A test vector or other redistributable data encoded as JSON, text, Markdown, or a source-like text file can therefore be included in the source archive without an affirmative rights record. For example, `tests/cpu/title.json` currently returns false from `_is_rights_candidate`, even though arbitrary ROM/vector content can be represented as JSON. The privacy pattern scanner does not determine copyright or permission, so this remains a path-based hole in the no-ROM/BIOS and exact-rights contract.
**Reproduction:** `python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, "tools"); import public_content as c; print(c._is_rights_candidate("tests/cpu/title.json"))'` prints `False`.
**Fix:** Use an explicit allowlist for test source and documentation paths that are authored code/text, and require affirmative inventory rows for all other paths under `tests/`. For data-bearing formats such as JSON, use explicit path classification or inventory them regardless of extension.

## Re-review at `30d29dbc66d84cbeb500ed2029ce06f1667a74df`

**Re-review verdict:** CR-04 is resolved by exact repository-relative test-source classification and expanded rights records. The 14-case scanner suite passes, and the 21-item current rights inventory validates. The current local all-refs privacy scan remains failed on historical material, so public repository publication is still blocked pending a sanitized publication copy and a passing full history scan. Two additional detector coverage warnings were reproduced below.

**Verification:** `python3 tests/workflow/test_public_content.py` passed all 14 tests in 4.571 seconds. `validate_repository_inventory(Path.cwd())` passed with 21 records. Enumeration of all 57 tracked test paths found no unclassified paths and no candidate/record mismatch (15 test paths are rights candidates; the full 21 records also cover fixtures and vendored files). Adversarial probes confirmed parenthesized/mention home paths and OpenSSH private-key headers produce redacted findings; probes for a Windows home path and an OpenPGP private-key header produced no finding. No hosted CI or publication was performed.

### CR-04 disposition

- **CR-04 — RESOLVED.** The suffix heuristic is gone. `_is_rights_candidate` exempts only the exact `TEST_SOURCE_PATHS` members (unless a name contains `fixture`), and every other `tests/` path must appear in the affirmative inventory. The expanded tree/archive regression checks `.bin`, `.json`, `.txt`, `.md`, `.py`, unknown-extension, and extensionless names; all are rejected without inventory entries. The 21-record tree inventory check passed.

## Current publication blocker

### PUB-01: Historical absolute paths remain in reachable plan blobs

**Severity:** BLOCKER
**File:** Historical blobs for `.planning/phases/01-cpu-acceptance-experiment/01-26-PLAN.md`, `.planning/phases/01-cpu-acceptance-experiment/01-29-PLAN.md`, and `.planning/phases/02-executable-diagnostic-sdk/02-01-PLAN.md` through `02-06-PLAN.md`.
**Issue:** The current source edits replace local home prefixes with `$HOME`, but the original path-bearing blobs remain reachable in local Git history. The latest full all-refs scan is known to fail with 24 redacted `personal-path` findings across those eight plan paths. These are not covered by the two exact benign-object dispositions and are not resolved by working-tree edits. A public push would publish the reachable history unless the isolated publication copy removes or sanitizes those historical blobs.
**Fix:** Sanitize only the isolated publication copy's reachable history, preserve the working repository's history, and rerun the complete scanner on the exact publication copy and refs. Keep this blocker open until the scan reports no unresolved findings and the observed object/ref denominator is recorded.

The source edit in each of those eight current plan files is limited to replacing the local workflow/template reference prefix with `$HOME`-based references. The change is appropriately narrow, but it does not remove the prior blobs from reachable history.

## Warnings on re-review

### WR-02: Windows home paths are not detected

**Severity:** WARNING
**File:** `tools/public_content.py:45-47`
**Issue:** The home-path patterns recognize POSIX `/Users/...` and `/home/...` values, but not common Windows absolute paths such as a Windows drive-root `Users` path. The project builds on Windows, and its privacy rule prohibits publishing personal absolute paths, so a Windows path in tracked content or a supplied log currently passes this detector.
**Reproduction:** A read-only `scan_bytes` probe for a synthetic Windows drive-root home path returned an empty finding list.
**Fix:** Add a Windows drive-root home-path pattern with boundaries and redacted output, plus positive and synthetic-path controls.

### WR-03: OpenPGP private-key armor is not detected

**Severity:** WARNING
**File:** `tools/public_content.py:54-55`
**Issue:** The new `private-key` expression recognizes common PEM headers, including OPENSSH, but not OpenPGP's a header composed of five hyphens, `BEGIN PGP PRIVATE KEY BLOCK`, and five hyphens armor. A tracked private-key export or supplied log containing that header therefore passes the new key-header detector.
**Reproduction:** A read-only `scan_bytes` probe for a synthetic a header composed of five hyphens, `BEGIN PGP PRIVATE KEY BLOCK`, and five hyphens header returned an empty finding list.
**Fix:** Add the OpenPGP private-key block header to the detector and add a test that verifies the rule is emitted without echoing the header or key body.
