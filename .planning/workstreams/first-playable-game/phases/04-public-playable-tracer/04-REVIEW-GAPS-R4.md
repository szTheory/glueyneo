---
phase: 04-public-playable-tracer
reviewed: 2026-10-11T00:00:00Z
depth: standard
diff_base: f675d7c
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
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 04: Gap-Closure Re-Review R4 (04-43..04-55)

**Reviewed:** 2026-10-11
**Depth:** standard (changes since f675d7c, with surrounding code)
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Round 4 reviews plans 04-43..04-55: the lane-output, rollback, per-round provenance, ID-pattern, probe pid-record, snapshot directory-set, setup/entry guard and security-register frontmatter/table work. The four unit suites pass as run here (independent_review 70, check_security_register 59, verify_playable 105, retroarch_smoke 77 tests), and `python3 tools/verify_playable.py --check-docs` passes. The receipt status line (`5a40e93147bf`) is consistent with the currency rule: nothing under `src/`, `include/`, `third_party/`, `tests/fixture/`, `tests/libretro/` or the two listed tool files changed after that revision, only `tests/tools/` and docs.

No critical issues. The R3 fixes hold for the cases their tests exercise, but one of them (G3WR-01) introduced a new output-loss path that I reproduced against the real function, and the register checker's new key normalization accepts spellings that the downstream GSD reader does not read as `threats_open`. Two older provenance gaps surfaced while re-deriving R3's claim about the rights inventory.

### Status of R3 findings claimed fixed

| R3 finding | Verdict | Notes (re-derived from source and probes) |
|---|---|---|
| G3WR-01 (duplicated, reordered lane timeout output) | Partially fixed | The R3 reproduction (`EARLY`, SIGTERM prints `LATE`) now yields `EARLY\nLATE\n` exactly once each, in order. But the fix drops the earlier segment when the post-kill `communicate` returns `""`, and falls back to a reordered layout when the tail does not start with the earlier text. See G4WR-01. |
| G3WR-02 (ID pattern hand-extended each round) | Fixed | `(?:G\d*)?(?:CR\|WR\|IN)-\d{2}` plus `T-\d{2}-\d{2,}`; `review_ids` now rejects a malformed ID with `fullmatch`. `G3WR-01`, `G12IN-03`, `GCR-01`, `T-04-100` all parse; `VERDICT` lines for them are attempt-matched. The disposition tool's `REVIEW_ROUND_ID` accepts the same family. |
| G3WR-03 (probe labels pid-record failure as launch) | Fixed | `record_child_pid` has its own handler in `run_launch_probe`; the diagnostic uses `stage="pid-record"`, `survived_window=None`, the frontend is still killed by the `finally`, and `compare_launch_probes` returns `diagnostic-pid-record-failed`. Docs now say "by both paths", which is true. Residual: G4IN-03. |
| G3WR-04 (rollback aborts in `.restore` cleanup) | Fixed | Both the per-file `.restore` unlink and the final `.tmp` unlinks are guarded; a stray `.restore` is named in the aggregated error and the remaining restores still run. Residual wording issue: G4IN-02. |
| G3WR-05 (provenance anchored to original review) | Fixed | Each finding is bound to its round: `CR/WR/IN` to `reviewed_revision`, `G`/`G<n>` to the earliest commit that added `04-REVIEW-GAPS[-R<n>].md` (`git log --diff-filter=A`, oldest entry). Equality with the anchor is rejected, a missing round file or unknown ID family fails closed, and the docs now state "relative to the review round that raised the finding". |
| G3IN-01 (`$` handled inconsistently) | Fixed | `path_contained` and `glob_contained` now refuse a leading `$`; comment, docstring and docs agree. |
| G3IN-02 (dead pid-record diagnostic in `run_smoke`) | Fixed | The inner diagnostic is gone; the outer `SmokeBlocked` handler builds the single record, and the detail keeps only the exception class name (no path text). |
| G3IN-03 (register checker silent skips) | Partially fixed | `status: verified # note` is now recognized (probed: non-zero count fails). A register-shaped file named `NN*-SECURITY.md` with a non-register name now fails as `misnamed security register`, and a non-register-shaped one prints `SKIP:`. The glob still requires two leading digits, so `4-SECURITY.md` or `SECURITY.md` with an open high row is silently ignored and `--require-closed` prints PASS. See G4IN-01. |

## Warnings

### G4WR-01: Lane timeout output is lost (or reordered) when the post-kill `communicate` yields no tail

**File:** `tools/verify_playable.py:605-613` (`_terminate_lane_group`), `tools/verify_playable.py:633-638` (`_collect_after_kill`)
**Issue:** The G3WR-01 fix de-duplicates by testing `tail.startswith(earlier)` and, when that is false, sets `earlier = ""` and keeps the whole `tail`. Two ways to reach that branch:

1. `_collect_after_kill` returns `""` when `communicate(timeout=10)` expires again. That happens when a descendant that left the group (`setsid`) keeps the pipe open, which is exactly the case the SIGKILL-then-drain code is written for. Then `"".startswith(earlier)` is false for any non-empty `earlier`, `earlier` is blanked and the output that the first `communicate` had already captured is discarded. Reproduction against the real function (lane prints a marker, spawns a `setsid` sleeper holding stdout, then sleeps; `expired.output == b'<marker>\n'`): the returned diagnostic contains the `TimeoutExpired` line and nothing else, no marker. Before the R3 fix the earlier bytes were always appended, so this is a regression, and it hits the timeout evidence for the hardest-to-diagnose lanes.
2. Any case where Popen's buffered text differs from the independently translated `earlier` (a split multi-byte sequence decodes to U+FFFD in `earlier` but not in `tail`). Then `drained` is emitted before `tail`, which still contains the earlier segment, so the order is wrong. The docs sentence "each segment once, in emission order" is not true on these paths.

Also, `drained` is decoded without newline translation, so CRLF output written during the SIGTERM grace keeps `\r\n` while the other segments are translated (probed: `A\nB\nLATE\r\n`).
**Fix:** Do not infer the earlier segment from `tail`. Keep `earlier` unconditionally (it is the first-communicate bytes decoded once), and obtain only the genuinely new tail from `_collect_after_kill`: record `len(earlier_bytes)` and slice the bytes, or, simpler, have `_collect_after_kill` return raw bytes by reading `proc.stdout` after `wait()` is no longer needed. Decode `earlier_bytes + drained_bytes + tail_bytes` once and then apply one newline translation. Add regressions for (a) a pipe-holding `setsid` descendant keeps the earlier marker, (b) CRLF in the drained segment, (c) a multi-byte character split across segments.

### G4WR-02: Register checker accepts case-folded and non-ASCII-digit spellings that the GSD reader does not read as `threats_open`

**File:** `tests/tools/check_security_register.py:137-142` (`normalized_key`, case-folding), `:70-72` (`INTEGER = \d+`), `:230-239`
**Issue:** The key normalization (quote removal plus `casefold`) is right for duplicate detection, but the same normalized lookup also decides success. A register whose only key is `Threats_Open: 0` (or `"THREATS_OPEN": 0`) passes the checker, yet the GSD secure-phase and ship workflows read the literal field `threats_open` (see the `threats_open` references in `workflows/secure-phase.md`), so the gate they trust is absent. Probe: `register_errors` for frontmatter `Threats_Open: 0` returns `([], 0)`. In the same way `INTEGER = re.compile(r"\d+")` matches Unicode decimal digits: `threats_open: ٣` (Arabic-Indic three) is accepted as 3 although YAML reads it as a string. Likewise `Status: Verified` is honored by the checker's `verified` rule in any case spelling that YAML consumers treat as a different key.
**Fix:** Keep case-insensitive matching for duplicate and guarded-key detection only. For the declaration itself require the exact bare or quoted spelling `threats_open` (after quote removal, no case folding) and fail with `threats_open key must be spelled exactly` otherwise. Use `re.compile(r"[0-9]+", re.ASCII)` (or `fullmatch(r"[0-9]+")`). Add one test per case.

### G4WR-03: A lane that emits non-UTF-8 bytes raises `UnicodeDecodeError` instead of being recorded (pre-existing, on the path this round rewrote)

**File:** `tools/verify_playable.py:772-780` (`Popen(..., text=True)` and the `communicate` / `_terminate_lane_group` handlers), `tools/verify_playable.py:633-638`
**Issue:** The lane `Popen` uses strict text decoding. Any byte that is not valid UTF-8 in a lane's output (a compiler, test binary or RetroArch crash dump) makes `communicate` raise `UnicodeDecodeError`, which is neither `TimeoutExpired` nor `OSError`. The lane log, the `verify_snapshot` call after the lane and the lane record are skipped and the run ends as `internal-error: UnicodeDecodeError` (probed: `communicate` on a child writing `b'\xff'`). In the timeout path the same error escapes `_collect_after_kill` after the group has been SIGKILLed (reproduced with a multi-byte character split across the first and later segments). The G3WR-01 rewrite decodes defensively (`errors="replace"`) for the segments it controls, which makes this gap stand out: the segment Popen decodes is the only one that can raise.
**Fix:** Pass `errors="replace"` (and `encoding="utf-8"`) to the lane `Popen`, so every segment is decoded the same way, and treat `ValueError` from `communicate` like a lane failure. Add a lane test that prints `b'\xff'`.

### G4WR-04: R3's rights-inventory claim does not hold; one `source_revision` does not resolve and four are stale

**File:** `docs/rights-inventory.md` (rows for `tests/fixture/check_fixture.py`, `fixtures/diagnostic/manifest.json`, `tests/fixture/ORACLE.md`, `tests/fixture/rights-manifest.json`, `tests/sdk/ORACLE.md`)
**Issue:** R3 stated that each `source_revision` equals the last commit touching the file. Re-derived from `git log -1 -- <path>` it is true only for 21 of the 46 rows (all 8 rows edited in this range are correct, and every SHA-256 matches the working tree). The remaining 25 rows differ from the last-touching commit; most are harmless (content at the cited commit equals HEAD, or the value is an upstream Unity pin). But: (a) `tests/fixture/check_fixture.py` cites `e6547a1e671a2a615315487bc5d95d5bfe442d70`, which does not exist in the repository (the real commit starting `e6547a1` is `e6547a11dbb631ca...`); the 33 trailing digits are wrong, so the provenance cannot be followed. (b) Four rows cite a commit whose version of the file differs from HEAD although the recorded SHA-256 is the HEAD digest, so the revision/digest pair is internally inconsistent. The document does not define what `source_revision` means, so nothing catches this.
**Fix:** Define the field in the document (for third-party rows the upstream pin, for original files the last commit that changed the file), correct the unresolvable value, refresh the four stale rows, and add a check in `tests/tools/test_private_paths.py` or the rights check that every non-third-party `source_revision` resolves with `git cat-file -e`.

## Info

### G4IN-01: Misnamed-register detection still depends on a two-digit filename prefix

**File:** `tests/tools/check_security_register.py:321-343`
**Issue:** The candidate glob is `phases/*/[0-9][0-9]*-SECURITY.md`. A register named `4-SECURITY.md`, `SECURITY.md` or `phase-04-SECURITY.md` is never a candidate, so it is neither failed nor reported as `SKIP:`. Probed: a workstream with a valid `04-SECURITY.md` and a stray `4-SECURITY.md` holding an open high threat prints `PASS` under `--require-closed`. This is the same fail-open class G3IN-03 addressed, narrowed to a smaller set of names.
**Fix:** Glob `phases/*/*SECURITY*.md` and classify with the existing register-shape test, reporting `SKIP:` for non-register-shaped files.

### G4IN-02: Rollback reports "incomplete" for a successful restore and swallows `.tmp` debris silently

**File:** `tools/verify_playable.py:1123-1140`
**Issue:** If the restore succeeded and only the stray `.restore` unlink failed, the file name is appended to `unrestored` and the raised message says `evidence rollback incomplete` although the evidence is intact. Conversely the final `.tmp` cleanup `pass`es with no record, so a stray `<name>.tmp` can remain next to tracked evidence with no signal.
**Fix:** Keep a separate `debris` list: leave `unrestored` for files whose content was not restored and mention debris in a distinct clause (`evidence rollback complete; could not remove: ...`), and at least name a surviving `.tmp` file in the error output.

### G4IN-03: The diagnostic runner proceeds to the second probe after a pid-record failure

**File:** `tests/libretro/retroarch_smoke.py:861-871` (`run_diagnostics`)
**Issue:** After `no_content` reports `stage="pid-record"`, the second probe still launches a second frontend and the PID file may hold the previous (killed) probe's PID. The runner's scoped survivor cleanup then reads a PID that no longer identifies the live child. The comparison already collapses to `diagnostic-pid-record-failed`, so the second launch adds nothing to the result.
**Fix:** Return early from `run_diagnostics` when the first probe's diagnostic stage is `pid-record`, and mark the second probe as not run.

---

_Reviewed: 2026-10-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
