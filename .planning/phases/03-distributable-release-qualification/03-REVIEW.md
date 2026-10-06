---
phase: 03-distributable-release-qualification
reviewed: 2026-10-06T20:21:22Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - CMakeLists.txt
  - tests/consumers/check_package.py
  - tests/consumers/test_exports.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
reviewed_revision: f74f4cd77cb88fe0803697b74ea423765e94cae7
initial_reviewed_revision: 1ba5b3c75ba7bda878e652ecf13d8544c6510bc2
diff_base: 8ddebb9856e70e0e753e0747059b97a9a8e63a32
re_reviewed_revision: cb4834ed89e2422491387eb8ef4a2598fb5824dd
re_review_status: issues_found
re_review_open_findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
latest_reviewed_revision: 2c7926383222cee174ede5ddde06374b43002191
latest_review_status: clean
latest_open_findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
latest_hosted_run: 37525280735
latest_hosted_run_status: success
publication_head_reviewed: f74f4cd77cb88fe0803697b74ea423765e94cae7
publication_review_status: clean_bounded_scan
historical_private_refs_reviewed: false
---

# Phase 03: Code Review Report

**Reviewed:** 2026-10-06
**Depth:** standard
**Files Reviewed:** 3
**Status:** clean at `2c7926383222cee174ede5ddde06374b43002191`; hosted release qualification remains pending
**Revision:** `2c7926383222cee174ede5ddde06374b43002191`

## Summary

The latest review covered cross-compiler source identity and the Windows DUMPBIN export-inspector correction. The exact-SHA hosted CI matrix and aggregate pass at the reviewed revision, and the focused local Windows controls and installed consumers pass. Earlier failures remain documented with their fixes. No source findings remain open at this revision. The hosted release App, fork approval, protected merge, draft/retry/download/publication behavior, and public release assets remain unqualified.

The historical findings and counts below preserve each review iteration. Their current dispositions are recorded in the dated follow-up sections; the latest exact-SHA review has no open findings.

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

## Final publication re-review at `f74f4cd77cb88fe0803697b74ea423765e94cae7`

**Verdict:** No open code-review findings remain in the reviewed current public HEAD scope. CR-01, CR-02, CR-04, WR-01, WR-02, WR-03, and PUB-01 are resolved for this publication head. This is a clean bounded scanner and rights-inventory review, not a global guarantee of secret absence or legal rights, and it does not qualify unobserved hosted behavior.

**HEAD-only verification:** A temporary single-branch repository was constructed from the current `HEAD` commit only; local private refs and uncommitted user planning changes were not included. The clone resolved to the exact reviewed SHA. `python3 tests/workflow/test_public_content.py` passed 16/16 tests in 4.337 seconds. `python3 tools/public_content.py` passed with 98 repository-scope files (2,137,247 bytes), 1,115 history entries (29,246,607 bytes), zero unresolved findings, and two exact history dispositions.

**Full tracked-tree verification:** The complete tracked content at current HEAD contains 355 files (9,498,009 bytes). Raw pattern scanning reports one hit at `third_party/musashi/m68kmake.c` under `private-identity`; this is the exact upstream public contact recorded in the publication audit, not user or private data. Its file digest matches the separate Musashi retained-grant record and its corresponding history object disposition. The committed audit snapshot at sanitized source `a8b78788799fb70a18e4198d54f86dc3d4ee17ba` records 351 files and 9,444,231 bytes; the current HEAD has later documentation and evidence files, so the fresh 355-file result is the current denominator.

**Rights and history evidence:** The current repository rights check passes with 21 records. All nine repository-only Musashi records match the committed SHA-256 values; provenance pins upstream revision `313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd` and states the source retains the upstream permissive notices. `tools/release_manifest.py` includes Unity and excludes `third_party/musashi`, keeping the experimental candidate out of SDK archives while preserving its notices in the repository. The 323-entry publication commit map has unique, well-formed old/new IDs and includes the audit source revision. The audit's complementary literal-home check is recorded as passed; this review did not enumerate or inspect preserved local private refs.

**Resolved finding trail:**

- **CR-01 — RESOLVED for selected publication history.** The scanner covers reachable blobs; the clean HEAD-only history scan has zero unresolved findings and retains only the two exact, provenance-bound dispositions.
- **CR-02 and CR-04 — RESOLVED.** The exact test-source path allowlist and 21-item inventory now reject unrecorded test assets without suffix exceptions.
- **WR-01 — RESOLVED.** Workflow and root release configuration files are in repository scan scope while the SDK archive scope stays separate.
- **WR-02 and WR-03 — RESOLVED.** Windows home paths and OpenPGP private-key headers have explicit rules and redaction tests; all 16 focused tests pass.
- **PUB-01 — RESOLVED for selected publication history.** The sanitized public history scan no longer reports the former plan-path matches. The preserved local refs remain outside this reviewed scope and must not be pushed.

The full tracked-tree detector and rights inventory remain bounded mechanisms. A negative result covers only configured patterns, files, refs, and limits actually scanned; an affirmative row and digest do not independently establish legal permission. Repository secret scanning/push protection were observed enabled in the hosted receipt, but no live credential canary was used. Hosted CI lane identities, branch protection, App installation/token authority, fork approval, protected merge, release event delivery, downloaded published asset verification, and actual publication remain pending in `03-HOSTED-QUALIFICATION.md`.

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
**Issue:** The home-path patterns recognize common POSIX user-home layouts, but not common Windows absolute paths such as a drive-root user-home path. The project builds on Windows, and its privacy rule prohibits publishing personal absolute paths, so a Windows path in tracked content or a supplied log currently passes this detector.
**Reproduction:** A read-only `scan_bytes` probe for a synthetic Windows drive-root home path returned an empty finding list.
**Fix:** Add a Windows drive-root home-path pattern with boundaries and redacted output, plus positive and synthetic-path controls.

### WR-03: OpenPGP private-key armor is not detected

**Severity:** WARNING
**File:** `tools/public_content.py:54-55`
**Issue:** The new `private-key` expression recognizes common PEM headers, including OPENSSH, but not OpenPGP's a header composed of five hyphens, `BEGIN PGP PRIVATE KEY BLOCK`, and five hyphens armor. A tracked private-key export or supplied log containing that header therefore passes the new key-header detector.
**Reproduction:** A read-only `scan_bytes` probe for a synthetic a header composed of five hyphens, `BEGIN PGP PRIVATE KEY BLOCK`, and five hyphens header returned an empty finding list.
**Fix:** Add the OpenPGP private-key block header to the detector and add a test that verifies the rule is emitted without echoing the header or key body.

## Independent follow-up review at `4fb54e4b28ca30d89e4e713af0b610e70d3a688e`

**Verdict:** One blocker remains open. The changed Windows host-thread support and matrix plumbing reach MSVC, but its required build fails on a warning promoted to an error in the SDK mutation test. Do not treat Windows support as qualified until the current source passes this lane and the aggregate check.

**Scope:** Reviewed the 18 non-planning files changed since `0712ed83b5e05a768f24a1e50528be5add3bbff2`. The three unrelated user-modified planning files were not read as implementation scope or changed. The preserved private local refs were not inspected or treated as public history.

**Verification:** `tests/workflow/test_ci_policy.py`, `tests/sdk/test_matrix_evidence.py`, `tests/consumers/test_exports.py` (5 tests), and `tests/workflow/test_public_content.py` (17 tests) passed. Python syntax compilation and `git diff --check` passed. Hosted run `37520769390`, exact head `4fb54e4b28ca30d89e4e713af0b610e70d3a688e`, completed failed: Linux GCC/Clang, macOS, sanitizer, fuzz, and public-content jobs passed; Windows MSVC failed, so `ci-policy` failed as expected. Its bounded diagnostic artifact reported MSVC C4457 at `tests/fuzz/sdk_mutation.c:665`; no raw runner path or canary value is retained here. No release, App, protected-merge, or publication claim is inferred from CI.

### CR-03: MSVC warning-as-error prevents the Windows matrix from compiling

**Severity:** BLOCKER
**File:** `tests/fuzz/sdk_mutation.c:665`
**Issue:** `run_sequence_operation` takes a parameter named `index` at line 607, then declares another `index` in the storage-counting loop at line 665. MSVC reports C4457 (“declaration of 'index' hides function parameter”); the test targets use `/W4 /WX`, so `sdk_mutation.c` fails to compile. This stops the Windows MSVC matrix before its package consumers can run and makes the aggregate CI check fail, blocking the phase's Windows platform qualification.
**Reproduction:** Hosted run `37520769390` at this exact revision failed its `windows-msvc` job while compiling `sdk_mutation.c`; the uploaded bounded failure receipt preserved the diagnostic after redaction. The source location is `for (unsigned index = 0u; index < MUTATION_LIVE_LIMIT; ++index)` inside `run_sequence_operation`.
**Fix:** Rename the loop variable to a distinct name such as `owner_index` and use it for both `owners[owner_index]` accesses. Rerun the full exact-revision hosted matrix and require the Windows lane and aggregate to pass before counting Windows as qualified.

The latest hosted run's other passing lanes establish only their named runner/configuration outcomes. They do not establish Windows support or complete hosted release qualification.

## Final independent review at `a91e98efe1f507df4b3424705d89b64cac65184d`

**Verdict:** CR-03 is resolved. One blocker remained at this revision: Windows MSVC builds stamped test result records with `unknown` instead of the exact source revision, so the verifier rejected the diagnostic result and the Windows lane and CI aggregate failed.

**Scope:** Reviewed the nine non-planning files changed since `4fb54e4b28ca30d89e4e713af0b610e70d3a688e`. The release-App setup note was read for boundary claims but is a planning artifact and is excluded from the source-file count. The unrelated pre-existing user planning edits and preserved private local refs were left untouched.

**Verification:** `python3 tests/consumers/test_exports.py` passed 10/10, including the generated Windows COFF closure controls; `python3 tests/sdk/test_matrix_evidence.py` and `python3 tests/workflow/test_public_content.py` (17 tests) passed. Python syntax compilation passed. `cmake --preset sdk-debug`, the debug build, and `ctest --preset sdk-debug -R '^sdk_host_closure$' --output-on-failure` passed on the local host. These local and synthetic controls do not establish native Windows qualification.

Hosted run `37524266388` completed failed at this exact SHA. Linux GCC, Linux Clang, macOS, sanitizer, fuzz, and public-content jobs passed; Windows MSVC failed and `ci-policy` failed as a result. The uploaded, bounded Windows receipt reports `SDK result identity/count/outcome failed for diagnostic` and binds the failure to this SHA. The prior C4457 attempt at `4fb54e4` remains a preserved counterexample; that specific compile issue is fixed by the `owner_index` rename. No hosted release App, fork-approval event, protected merge, release, or publication was observed or inferred.

### CR-05: MSVC test records contain no usable source revision

**Severity:** BLOCKER
**File:** `CMakeLists.txt:130-143`
**Issue:** The configure logic obtains `GLUEYNEO_SOURCE_REVISION` from `git rev-parse` only when the compiler ID is GNU, Clang, or AppleClang. Every other compiler, including MSVC, is explicitly assigned `unknown`. The SDK test executables include this value in each `SDK_RESULT` record, while `tools/verify_sdk.py:381-395` requires the record's revision to equal the first 12 characters of the current Git `HEAD`. Consequently, the Windows diagnostic CTest can never pass the identity check in a normal MSVC build. The workflow already sets `SDK_SOURCE_REVISION`, but CMake does not consume it.
**Reproduction:** Exact-SHA hosted run `37524266388` failed the `windows-msvc` lane. Its uploaded failure receipt records `SDK result identity/count/outcome failed for diagnostic`; the source check confirms MSVC configures the test record as `unknown`, which cannot satisfy the verifier's SHA comparison. The previous Windows attempt's build output also identified `GLUEYNEO_SOURCE_REVISION` as `unknown` before reaching this later test stage.
**Fix:** Resolve the source revision for all compiler families (for example, run `git rev-parse --short=12 HEAD` without the compiler-ID guard), and fail configuration if it is absent or malformed. Alternatively, pass the workflow's exact `SDK_SOURCE_REVISION` into CMake and validate its format before defining the test macro. Rerun the exact hosted Windows lane and aggregate after the change.

The public repository content scan passed at this revision. Release App installation and token scope, first-time fork approval and read-only/no-secret behavior, independent approval and protected merge, draft/retry/download/publication events, and public release assets remain unqualified pending the documented account setup and exact hosted receipts.

## Final independent re-review at `2c7926383222cee174ede5ddde06374b43002191`

**Verdict:** No open source findings. CR-05 is resolved: CMake now obtains the checkout identity independently of compiler family, retaining `unknown` only when Git is unavailable. The prior DUMPBIN-version failure is also resolved: the version banner is read from a successful `/EXPORTS` invocation on the tested DLL.

**Scope:** Reviewed the three source/configuration files changed since `a91e98efe1f507df4b3424705d89b64cac65184d`. No unrelated user edits or preserved private refs were changed or included.

**Verification:** `python3 tests/consumers/test_exports.py` passed 12/12 tests, including generated Windows COFF closure and DUMPBIN identity controls. `python3 tests/consumers/check_package.py --suite consumers` passed both installed static/shared consumer cases. The local CMake debug build and `sdk_host_closure` test passed (1/1). Hosted run `37525280735` completed successfully at this exact SHA: all six matrix lanes (Linux GCC, Linux Clang, macOS, Windows MSVC, sanitizer, fuzz), public-content, and `ci-policy` passed. The preceding Windows attempt, `37524853015` at `1c1265a79f2ab5d556a79f93e3cf39941ebb532c`, passed the diagnostic and static consumer but failed the shared consumer because the DUMPBIN help invocation exited nonzero; the bounded receipt showed this failed inspector command. The updated control obtains the tool banner from successful `/EXPORTS` inspection. These failed attempts remain preserved above and in their hosted receipts as counterexamples, with each correction tied to current evidence.

### CR-03 disposition

- **CR-03 — RESOLVED.** The C4457 variable shadow was corrected by renaming the loop variable. The exact-SHA Windows MSVC lane now passes.

### CR-05 disposition

- **CR-05 — RESOLVED.** Git revision lookup no longer depends on compiler ID. The hosted Windows diagnostic result and static consumer passed on the prior candidate; the latest exact-SHA Windows lane and aggregate pass after the DUMPBIN correction.

The release qualification phase still has external evidence outstanding: no release App currently exists, and App installation/token scope, first-time fork approval and read-only/no-secret behavior, independent PR approval, protected merge, release draft/retry, downloaded assets, and publication have not been observed. This is a phase-delivery boundary, not an open code-review finding. Do not infer protected-merge readiness or release qualification from the CI pass alone.
