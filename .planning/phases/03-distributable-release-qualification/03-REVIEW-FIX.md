---
phase: 03-distributable-release-qualification
fixed_at: 2026-10-06T19:00:11Z
review_path: .planning/phases/03-distributable-release-qualification/03-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-10-06T19:00:11Z  
**Source review:** `.planning/phases/03-distributable-release-qualification/03-REVIEW.md`  
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-01: Historical file contents are outside the privacy scan

**Files modified:** `tools/public_content.py`, `tests/workflow/test_public_content.py`, `docs/public-content.md`  
**Commit:** `cb4834e`  
**Applied fix:** Scan commit metadata and every unique reachable blob body, including deleted paths. Enforce 50,000 reachable objects, 64 MiB per blob, and 512 MiB combined history bytes; fail closed when object enumeration, metadata, or blob reads are incomplete. Findings remain value-free. Two exact history hits are retained as visible, provenance-bound dispositions, each requiring the expected immutable object ID, path, and exact rule set: upstream Musashi copyright contact `007bd7fabaee7b0c171cb38a2581abeacf0f0c15` (`private-identity`) and synthetic redaction-test path `1c94ae35fe4334c8a1ecbb273a12e1e12a60fa79` (`personal-path`). Other history hits remain failures.

### CR-02: Uncatalogued test assets bypass redistribution-rights validation

**Files modified:** `tools/public_content.py`, `tests/workflow/test_public_content.py`, `docs/rights-inventory.md`, `docs/public-content.md`  
**Commit:** `cb4834e`  
**Applied fix:** Require exact affirmative inventory coverage for every non-code or non-text path under `tests/`, including unknown and extensionless paths. Repository-tree and archive validation share the classification; an uncatalogued `tests/cpu/title.bin` fails both gates. Existing fixture recipes retain their individual provenance records. The existing hardlink regression helper now uses `os.link`, preserving that control on Python 3.9.

### WR-01: CI privacy scan omits workflow source files

**Files modified:** `tools/public_content.py`, `tests/workflow/test_public_content.py`, `docs/public-content.md`  
**Commit:** `cb4834e`  
**Applied fix:** Add `.github/workflows` and `release-please-config.json` to the repository-publication scan paths while leaving `SOURCE_PATHS` unchanged for SDK archive construction. The existing CI and release scanner invocations now include repository workflow/configuration sources through the default path list.

## Verification

The 12-case focused public-content suite passed, and the scanner/test files passed Python syntax compilation. The complete local integration scan passed against 98 repository files, all 1,095 reachable blobs plus commit metadata, and a 95-file source archive; the rights inventory covered 13 items. It reported zero unresolved findings and the two visible exact history dispositions above. Verification ran in the isolated worktree `gsd-reviewfix/03-3133` before its commit was fast-forwarded to the user's branch. No hosted CI or independent re-review result is claimed here.

---

_Fixed: 2026-10-06T19:00:11Z_  
_Fixer: the agent (gsd-code-fixer)_  
_Iteration: 1_

## Follow-up fixes

The follow-on review corrections were committed in `30d29db` at
`30d29dbc66d84cbeb500ed2029ce06f1667a74df`.

The rights gate now classifies test source files by exact repository-relative
path. All other test paths require their own digest, affirmative rights,
provenance, and notice record, regardless of suffix or apparent text encoding.
Eight previously unrecorded oracle/evidence files now have records, bringing
the inventory to 21 items. Synthetic `title.bin`, `title.json`, `title.txt`,
`title.md`, `title.py`, unknown-extension, and extensionless paths fail both
repository-tree and archive rights checks unless explicitly recorded.

The privacy detector now catches home-directory paths after `@` and in
parenthesized/Markdown references, plus private-key PEM headers. Eight Phase 01
and Phase 02 plan files replace 16 local home-prefix references with `$HOME`;
the matched local path is never included in scanner output.

The 14-case focused suite and Python syntax compilation passed. A scan of the
current tree and 95-file source archive passed its rights check with all 21
records. The local all-refs history scan correctly remains **failed**: it found
24 `personal-path` matches across 8 distinct historical plan paths. These are
real historical paths, not dispositions, and the findings contain only
repository-relative locations and rule IDs. The scan inspected 1,099 reachable
blobs plus commit metadata, bounded by 50,000 objects, 64 MiB per blob, and
512 MiB combined history bytes. The two previously reviewed exact dispositions
remain separately visible. The publication clone must be sanitized before its
history scan can pass; original local history was not rewritten. Independent
re-review and any public push remain pending.
