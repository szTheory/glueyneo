---
phase: 04-public-playable-tracer
reviewed: 2026-10-10T00:00:00Z
depth: standard
diff_base: b0a1487
files_reviewed: 11
files_reviewed_list:
  - docs/first-playable-build.md
  - docs/rights-inventory.md
  - docs/testing.md
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/check_security_register.py
  - tests/tools/test_check_security_register.py
  - tests/tools/test_independent_review.py
  - tests/tools/test_verify_playable.py
  - tools/independent_review.py
  - tools/verify_playable.py
findings:
  critical: 0
  warning: 5
  info: 3
  total: 8
status: issues_found
---

# Phase 04: Gap-Closure Re-Review R3 (04-37..04-42)

**Reviewed:** 2026-10-10
**Depth:** standard (changes since b0a1487, with surrounding code)
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Round 3 closes the two R2 criticals correctly. Independent_review.py and verify_playable.py unit suites pass (66, 24 and 84 tests in the independent-review, security-register and verify-playable modules). Every SHA-256 in `docs/rights-inventory.md` matches the working tree, and each `source_revision` equals the last commit touching that file. No receipt-bound path changed after the 3d90990 re-qualification (only planning files and docs), so the "complete at `3d90990e5cd0`" status line is consistent with the receipt-currency rule it documents.

No critical issues remain. Five warnings: one new regression the drain change introduced (confirmed by reproduction), one forward-compatibility gap that blocks the next round's own gate, the known probe-path mislabel, an incomplete rollback guarantee, and a provenance window whose claim is stronger than what it proves.

### Status of R2 findings claimed fixed

| R2 finding | Verdict | Notes |
|---|---|---|
| G2CR-01 / T-04-61 (absolute group alternative) | Fixed, complete for the R2 cases | Reproduced all four R2 patterns plus `x/{a, /etc}`, `@(a\|/etc)`, `{$HOME,x}`: all return not contained. Ordinary `{a,b}/{c,d}` and `/tmp/scr/a b` stay contained. Residual: see G3IN-01. |
| G2CR-02 / T-04-11 (receipt-time traceback) | Fixed | The whole receipt construction through `_write_receipt` is inside one handler that emits only `receipt-error: <Type>` and writes a minimal fail receipt; a second failure degrades to `receipt-write-failed`. Only the exception type name is printed. |
| G2WR-01 (provenance binds nothing) | Partially fixed | Window now exists, docs state the narrower guarantee (the alternative R2 offered). The window is anchored to the original review, which weakens it for gap-round findings: G3WR-05. |
| G2WR-02 / WR-11 (malformed `reviewed_revision`) | Fixed | Exactly one 40-lowercase-hex value required, quote/pad-normalized key matching for duplicates, ancestor and resolve check on the value. Unterminated or commented values fail closed. |
| G2WR-03 (revision prefix match) | Fixed | `--revision` must match `[0-9a-f]{40}` (exit 2, value not echoed) and the first line must equal `Reviewed revision: <rev>` after `rstrip`. |
| G2WR-04 (decimal registers) | Fixed | `phases/*/[0-9][0-9]*-SECURITY.md` filtered by one shared `REGISTER_NAME` fullmatch. See G3IN-03 for a residual silent skip. |
| G2WR-05 (rollback) | Partially fixed | Absent files are handled (None, unlinked on rollback) and a failed restore no longer aborts the loop, with one aggregated error. The `finally` that removes the `.restore` file can itself raise: G3WR-04. |
| G2WR-06 (launch window / pid-record) | Fixed in `run_smoke`, not in the diagnostic probe | Signal now raised from `finally` and chained from the body error; `record_child_pid` has its own `pid-record` stage. The probe still mislabels: G3WR-03. |
| G2IN-01 (`verified` case) | Fixed | `re.IGNORECASE`. |
| G2IN-02 (undrained lane pipe) | Fixed for the drain, but introduced a regression | See G3WR-01. |
| G2IN-03 (bare `redact` in qualification reasons) | Fixed | Both build-failure branches use `_public_reason`. |
| T-04-38 / T-04-67 provenance window | Works as coded | Cited revisions must resolve, descend from (or equal) `reviewed_revision`, and be ancestors of head. See G3WR-05 on what that proves. |

## Warnings

### G3WR-01: Lane timeout output is duplicated and out of order after the drain change (regression from G2IN-02)

**File:** `tools/verify_playable.py:547-590` (`_terminate_lane_group`, `_collect_after_kill`), caller at 741-744
**Issue:** `expired.output` holds what the first `communicate(timeout=...)` already read, and `Popen` also keeps that data in its internal per-fd buffer. `_terminate_lane_group` appends `expired.output` to `chunks`, drains new data with `os.read`, and then `_collect_after_kill` calls `communicate` a second time, which returns the buffered earlier data plus anything unread. The earlier output therefore appears twice, and the late output sits between the two copies. Reproduction against the real function with a lane that prints `EARLY`, then on SIGTERM prints `LATE`:

```
TimeoutExpired: ... timed out after 1.5 seconds
EARLY
LATE
EARLY
```

This is the diagnostic text recorded for a timed-out lane, so the evidence for exactly the failing case is misleading. The new tests do not catch it because they use distinct markers rather than asserting each marker appears exactly once in order.
**Fix:** Do not seed `chunks` from `expired.output`. Take the earlier part from the second `communicate` result instead, and append drained chunks only for data read via `os.read`. Simplest ordering-safe form: `partial = <expired.output decoded> + drained_chunks + <communicate tail minus the already-included prefix>`, or have `_collect_after_kill` slice off `len(earlier)` characters from its return value. Add a regression asserting `EARLY` and `LATE` each occur exactly once and in order.

### G3WR-02: Reviewer gate does not recognize G3 finding IDs; the ID alternation is hand-extended every round

**File:** `tools/independent_review.py:65` (`ID_PATTERN`), `docs/testing.md` "Review-tool containment" bullet
**Issue:** `ID_PATTERN` lists `G2CR|G2WR|G2IN` literally. This round's findings use `G3CR/G3WR/G3IN`, and the next focused re-review will be asked about them. `ATTEMPT` does not match `VERDICT G3WR-01 ...`, so `parse_verdicts` returns OPEN for every such ID. The gate fails closed, so it is not a bypass, but it makes it impossible to record a FIXED verdict for any G3 finding until the tool is edited again, and `is_threat`/status mapping silently depend on the same pattern. The R2 cycle already needed the same hand edit (GWR, GIN, then G2*).
**Fix:** Generalize the alternation, for example `(?:G\d*)?(?:CR|WR|IN)-\d{2}|GWR-\d{2}|GIN-\d{2}`, or `G\d?(?:CR|WR|IN)` plus the existing `GWR/GIN`, and add a parametrized test for `G3CR-01`, `G3WR-01`, `G3IN-01`. Update the docs bullet to describe the pattern instead of listing R2 IDs.

### G3WR-03: Diagnostic probe still labels a child-PID-record failure as `launch` and reports a running frontend as not started

**File:** `tests/libretro/retroarch_smoke.py:768-815`, claim at `docs/testing.md` "Smoke harness (G2WR-06)"
**Issue:** `run_launch_probe` keeps `Popen` and `record_child_pid` in one `with launch_window():` whose only handler is `except OSError` at line 805. An `OSError` from `record_child_pid` after a successful launch yields a diagnostic with `stage="launch"`, `survived_window=False`, `return_code=None`, even though a frontend was started (the inner `finally` kills it). `compare_launch_probes` then reasons from a record that says the launch failed, and `run_diagnostics` returns a `finding` built on it. The docs state without qualification that "a child-PID record failure is reported as `pid-record`", which is false for this path. The probe has no test of this case (the new test exercises only `run_smoke`).
**Fix:** Split the two operations as in `run_smoke`: catch `OSError` around `Popen` only (stage `launch`); wrap `record_child_pid` separately and produce a diagnostic with `stage="pid-record"` and a survival value of `None` (the frontend was running). Add a probe test with `record_child_pid` raising, and narrow the docs sentence if the probe is intentionally left as is.

### G3WR-04: Rollback can still abort mid-way through the `.restore` cleanup, defeating "every restore is attempted" (G2WR-05)

**File:** `tools/verify_playable.py:1078-1095`
**Issue:** In the rollback loop, the `try/except OSError` records a failed restore, but the `finally: restore.unlink(missing_ok=True)` is outside that handler. When the disk or directory is the failing component (the exact situation the loop exists for), `unlink` can raise `OSError` (for example `PermissionError` or `EROFS`). That exception propagates out of the loop, skips restoring the remaining files, and replaces the original error with a raw one that has no `rollback incomplete` message. It also happens when the restore itself succeeded and only the stray `.restore` removal failed.
**Fix:** Move the cleanup inside its own guard, for example:

```python
finally:
    try:
        restore.unlink(missing_ok=True)
    except OSError:
        unrestored.append(restore.name)   # or ignore: the file is unused debris
```

Add a test where `Path.unlink` raises for the `.restore` name and assert the other files are still restored and the aggregated error is raised.

### G3WR-05: Provenance window is anchored to the original review, so it cannot order dispositions of later gap-round findings

**File:** `tools/verify_playable.py:1262-1299`, `docs/testing.md` "Review provenance"
**Issue:** `reviewed_revision` is read from 04-REVIEW.md (867f317...). Every disposition for a finding raised by a later review (GWR/GIN, G2*, G3*) trivially passes the "descends from reviewed_revision" test with any commit made after that early revision. The docstring says the gate proves "a cited verdict postdates the review it answers", but for a gap-round finding the review it answers is the gap review, which the gate never reads. A closure for G2CR-01 that cites a commit from before R2 existed passes. Equality is also accepted, so a row can cite the review commit itself. The docs do state that freshness comes from the changed-path rule, which limits the damage, but the sentence "postdates the review it answers" is still an overclaim for these rows.
**Fix:** Either narrow the wording (state the window is relative to the original 04-REVIEW.md only), or have each gap review carry its own `reviewed_revision` and bind a finding to the review that raised it (for example per-round frontmatter, with the disposition row naming the round). At minimum require strict descent (`revision != reviewed`) for closure-bearing rows.

## Info

### G3IN-01: `$`-prefixed patterns are refused inside groups but not at the top level, contradicting the comment and docs

**File:** `tools/independent_review.py:53-59, 103-115`
**Issue:** The comment says the gate fails closed on `$` because "a variable reference cannot be proven scratch-relative". But `glob_contained("$HOME/x", ...)` and `"${HOME}/x"` return True (a relative pattern), while `{$HOME,x}` returns False. The two are inconsistent. Glob and Grep do not shell-expand today, so this is not exploitable, but the stated invariant does not hold.
**Fix:** Also refuse a pattern that starts with `$`, or drop `$` from `ABS_IN_GROUP` and the comment so the behavior and its rationale agree.

### G3IN-02: Dead launch diagnostic in `run_smoke` for the `pid-record` branch

**File:** `tests/libretro/retroarch_smoke.py:947-954`
**Issue:** The `pid-record` handler builds a diagnostic with `stage="launch"`, then raises `SmokeBlocked("pid-record", ...)`. Because `process` is already assigned, the outer `except SmokeBlocked` at line 1013 overwrites `error.diagnostic` with one using `stage=error.stage`. The inner diagnostic, including its `stage="launch"`, is discarded, and the original OSError text it carried is lost from the final record. It reads as if the diagnostic is labeled `launch`, which is misleading.
**Fix:** Drop the inner `build_diagnostic` call (pass no diagnostic) and let the outer handler build it, or include the `OSError` class name in the detail so the cause survives.

### G3IN-03: Register checker silently ignores mis-named register files and `verified` with a trailing comment

**File:** `tests/tools/check_security_register.py:52-57, 211-214`
**Issue:** The widened glob `[0-9][0-9]*-SECURITY.md` is post-filtered by `REGISTER_NAME`, so a file such as `04-draft-SECURITY.md` or `04.1a-SECURITY.md` is dropped with no message, which is the same fail-open class G2WR-04 was about. `VERIFIED` also requires the whole line to be the status, so `status: verified  # note` is not treated as verified and skips the `threats_open: 0` requirement.
**Fix:** Print or fail on files that match the wide glob but not `REGISTER_NAME`, and allow an optional trailing `#` comment in `VERIFIED`. Add one test for each.

---

_Reviewed: 2026-10-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
