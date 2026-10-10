---
phase: 04-public-playable-tracer
reviewed: 2026-10-10T00:00:00Z
depth: standard
diff_base: 2f08a40
files_reviewed: 18
files_reviewed_list:
  - CMakeLists.txt
  - docs/first-playable-build.md
  - docs/rights-inventory.md
  - docs/testing.md
  - experiments/owned_cpu/source-manifest.json
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/check_runtime_storage.py
  - tests/tools/check_security_register.py
  - tests/tools/test_check_runtime_storage.py
  - tests/tools/test_check_security_register.py
  - tests/tools/test_independent_review.py
  - tests/tools/test_private_paths.py
  - tests/tools/test_verify_playable.py
  - tests/workflow/test_public_content.py
  - tools/independent_review.py
  - tools/private_paths.py
  - tools/verify_playable.py
findings:
  critical: 2
  warning: 6
  info: 3
  total: 11
status: issues_found
---

# Phase 04: Gap-Closure Re-Review R2 (04-32..04-36)

**Reviewed:** 2026-10-10
**Depth:** standard (changes since 2f08a40, with surrounding code)
**Files Reviewed:** 18
**Status:** issues_found

## Summary

The gap plans added a containment/verdict/transcription gate (`tools/independent_review.py`), a non-reaping process-group lifecycle in the runner and the smoke harness, a review-provenance ancestor check, an all-or-nothing evidence write, a fail-closed security-register checker with a `--phase` scope, a hardened `nm` audit and NFC/NFD-aware path normalization.

Mechanical checks done: every SHA-256 recorded in `docs/rights-inventory.md` and `experiments/owned_cpu/source-manifest.json` for the reviewed files matches the working tree. `os.waitid` with `WNOWAIT` is available on the macOS host Python (3.14), so the unreaped-leader design is usable on the qualified platform.

The four items the contained review left open are confirmed by direct reproduction or line evidence (G2CR-01, G2CR-02, G2WR-01, G2WR-02). Two new defects are added: a revision prefix match in the transcription gate (G2WR-03) and an inconsistent register glob (G2WR-04).

## Critical Issues

### G2CR-01: Brace-alternative absolute glob escapes containment (T-04-61)

**File:** `tools/independent_review.py:94-105`
**Issue:** `glob_contained` treats a pattern as absolute only if it starts with `/`. Any pattern whose first character is `{`, or that carries a brace alternative that is itself absolute, is classified relative and then judged only by the base directory. Reproduced against a scratch path:

```
{/etc/*,x}                   -> True   (contained)
x/{/etc/passwd,y}            -> True
/tmp/scr/{a,/etc/passwd}     -> True   (prefix before first wildcard is the scratch)
@(/etc)/x, /tmp/scr/!(/etc)  -> True   (extglob forms are not in WILDCARDS)
```

`has_tilde_expansion` already recognizes `{~` and `,~` as brace-expansion escapes (lines 78-80), so the same gap for `/` was knowingly left. A Glob or Grep `glob` call can therefore enumerate outside the scratch tree while `gate` and `check` report `contained`. This is a containment bypass of the security gate whose purpose is to make the review trustworthy, and it keeps T-04-61 (high) open.
**Fix:** Fail closed on any absolute path segment inside a brace or extglob group, in both relative and absolute patterns:

```python
ABS_IN_GROUP = re.compile(r"[{,(|]\s*/")   # absolute alternative inside {..}, @(..), !(..), |

def glob_contained(pattern, scratch, base):
    if has_dotdot(pattern) or has_tilde_expansion(pattern) or ABS_IN_GROUP.search(pattern):
        return False
    ...
```

Alternatively expand braces (bounded) and require every expansion to pass `path_contained`. Add the four patterns above as regression cases in `tests/tools/test_independent_review.py`.

### G2CR-02: Receipt construction and write run outside any try block (T-04-11)

**File:** `tools/verify_playable.py:1513-1595` (also 1577-1592)
**Issue:** The `try` that ends at line 1511 covers the build. Everything after it is unguarded: the `receipt` literal calls `sha256(fixture_shared)`, `_artifact_file(...)` and `_artifact_tree(...)` (each can raise `OSError`, for example on a vanished or unreadable file), the final `verify_snapshot` / `validate_snapshot_record` block only catches `SnapshotError`, and `_write_receipt` (line 1595) calls `validate_snapshot_record` and `mkdir`/`write_text`/`replace` with no handler. Any such exception escapes `main()` as a raw traceback on stderr. Tracebacks carry absolute repository and output paths and bypass `redact`, `scan_public` and the `private-path-survived` sink, which is exactly the T-04-11 disclosure class. No receipt is written either, so a failing run leaves a stale or absent receipt. The new `check_docs` guard at 1561-1573 shows the intended pattern but was applied to one site only.
**Fix:** Wrap the post-`try` section in one handler that downgrades to a fixed token and still writes a minimal receipt:

```python
try:
    receipt = _build_receipt(...)          # lines 1513-1593
    return 0 if _write_receipt(receipt) == "pass" else 1
except Exception as error:
    emit_error("receipt: ", f"receipt-error: {type(error).__name__}")
    _write_receipt({"status": "fail", "reason": f"receipt-error: {type(error).__name__}"})
    return 1
```

Also route lines 1507 and 1511 through `_public_reason` instead of bare `redact`, and test with a file made unreadable between build and receipt.

## Warnings

### G2WR-01: Review provenance accepts any ancestor commit; `reviewed_revision` is never parsed (T-04-38)

**File:** `tools/verify_playable.py:1059-1074, 1165-1195`
**Issue:** `review_provenance_errors` only requires that a non-open disposition cite some 12-40 hex revision that resolves and is an ancestor of `head`. It does not bind the revision to the review record: nothing reads `reviewed_revision` from the REVIEW frontmatter, compares it with the cited revision, or checks that the reviewed files were unchanged since. A row can cite the repository's first commit and pass. The docs (`docs/testing.md`, "Review provenance") describe this as binding to a review revision, which overstates it.
**Fix:** Parse a single `reviewed_revision` from the REVIEW frontmatter (see G2WR-02), require the disposition revision to equal it (prefix-compatible), and require every path in `files_reviewed_list` to be unchanged between that revision and `head` (`git diff --quiet <rev> <head> -- <paths>`), or state the narrower guarantee in the docs.

### G2WR-02: Malformed sole `reviewed_revision` / revision value passes (WR-11, T-04-67 bundle)

**File:** `tools/verify_playable.py:1059-1074`
**Issue:** `_reviewed_paths` rejects duplicate top-level frontmatter keys but never requires that the key exists, appears once, or has a well-formed value (40 hex, resolvable commit). A review with an empty, truncated, non-hex or absent `reviewed_revision` is accepted. The duplicate-key scan also uses `re.match` on unindented lines only, so a duplicate written with trailing-space or quoted key variants is not seen.
**Fix:** Add `_reviewed_revision(review_text)` that requires exactly one `reviewed_revision:` line matching `^[0-9a-f]{40}$` after unquoting, raise `RuntimeError` otherwise, and use it from G2WR-01. Add malformed, empty and missing cases to `tests/tools/test_verify_playable.py`.

### G2WR-03: Transcription gate pins the review by string prefix with an unvalidated revision

**File:** `tools/independent_review.py:420`
**Issue:** `lines[0].startswith(f"Reviewed revision: {args.revision}")` accepts any line that merely begins with the argument. A short or abbreviated `--revision` (for example `bd74482`) matches a review pinned to a different commit that shares the prefix, and an empty `--revision ""` matches any `Reviewed revision: ` line. `--revision` is never checked as hex, never resolved, and never compared with the scratch tree's identity, so "pinned to the revision" is a weaker claim than the failure message states.
**Fix:** Require `^[0-9a-f]{40}$` for `--revision` (usage error otherwise) and compare the whole token: `lines[0].split()[2:3] == [args.revision]` after `Reviewed revision:`.

### G2WR-04: Milestone-wide register gate skips decimal phases that `--phase` accepts

**File:** `tests/tools/check_security_register.py:52, 215` (glob at the `pattern =` line in `main`)
**Issue:** `PHASE_NUMBER` accepts `NN.N`, so `--phase 04.1` resolves `phases/04.1-*/04.1-SECURITY.md`. The unscoped pattern `phases/*/[0-9][0-9]-SECURITY.md` cannot match `04.1-SECURITY.md`. Milestone shipping, which `docs/testing.md` says counts every register, silently omits decimal-phase registers, including blocking open rows. That is a fail-open in the gate the plan made authoritative (GWR-01 / T-04-62 intent).
**Fix:** Use `phases/*/[0-9][0-9]*-SECURITY.md` filtered by `re.fullmatch(r"\d{2}(\.\d+)?-SECURITY\.md", name)`, and add a test with a `04.1` register.

### G2WR-05: Evidence rollback is not robust to a missing file or a failed restore

**File:** `tools/verify_playable.py:1024-1042`
**Issue:** `originals = [path.read_bytes() ...]` raises a bare `FileNotFoundError` (and leaves nothing to restore) when the evidence JSON does not yet exist, so first-time generation fails before any write. In the rollback loop, if one `restore.write_bytes`/`os.replace` raises, the exception replaces the original error and the loop exits, leaving the remaining already-replaced files unrestored. That defeats the stated all-or-nothing guarantee exactly when the disk is failing.
**Fix:** Record `None` for absent files and unlink them on rollback; collect restore failures per index, continue restoring the rest, then raise one `RuntimeError("evidence rollback incomplete: <names>")` chained from the original error.

### G2WR-06: Launch window can swallow a termination signal and mislabel a pid-record failure

**File:** `tests/libretro/retroarch_smoke.py:676-692, 913-935`
**Issue:** `launch_window` raises `SmokeBlocked("interrupted")` only on the non-exceptional exit path. If the body raises (for example `OSError` from `Popen` or from `record_child_pid`) after a signal was deferred, the post-`finally` check is skipped and the signal is silently dropped: the run continues as an ordinary launch failure and the operator's SIGTERM/SIGINT is lost. Separately, `record_child_pid` sits inside the same `try/except OSError` as `Popen` in `run_smoke`, so a pid-file write failure after a successful launch is reported as "pinned RetroArch could not be started" even though a frontend is running (cleanup still happens, but the diagnostic is wrong).
**Fix:** In `launch_window`, evaluate `pending` in the `finally` block and raise `SmokeBlocked` from it (chaining any body exception). Move `record_child_pid` out of the `except OSError` that reports a launch failure, or give it its own reason.

## Info

### G2IN-01: `status: verified` match is case-sensitive

**File:** `tests/tools/check_security_register.py:52`
**Issue:** `VERIFIED` matches `verified` only; `Verified` or `VERIFIED` frontmatter bypasses the `threats_open: 0` requirement while still reading as verified to humans.
**Fix:** Add `re.IGNORECASE`, with a mutation test.

### G2IN-02: Lane termination wait does not drain the pipe

**File:** `tools/verify_playable.py:527-545`
**Issue:** After SIGTERM the loop polls `_leader_exited` for up to `LANE_GRACE_SECONDS` without reading stdout. A leader that writes a shutdown message into a full pipe cannot exit, so every such lane burns the full 30 s before SIGKILL, and the partial output is truncated. The WNOWAIT design is otherwise sound.
**Fix:** Read the pipe in a thread, or use `proc.communicate(timeout=0.1)` in the loop and treat `TimeoutExpired` as "not yet", provided `communicate` is not allowed to reap before the SIGKILL.

### G2IN-03: Qualification-failure reasons use bare `redact` while documentation reasons use the scan-backed helper

**File:** `tools/verify_playable.py:1507, 1511`
**Issue:** `_public_reason` was added for the documentation lane only. The build-failure branches still store `redact(str(error))` directly. `_write_receipt` still fails the whole receipt closed on a survivor, so this is not a disclosure, but it discards the diagnostic and is inconsistent.
**Fix:** Use `_public_reason(str(error))` in both branches.

---

_Reviewed: 2026-10-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
