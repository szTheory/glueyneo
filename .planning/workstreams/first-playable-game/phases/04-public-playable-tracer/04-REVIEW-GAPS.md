---
phase: 04-public-playable-tracer
reviewed: 2026-10-10T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - CMakeLists.txt
  - docs/first-playable-build.md
  - docs/rights-inventory.md
  - docs/testing.md
  - experiments/owned_cpu/source-manifest.json
  - tests/consumers/check_package.py
  - tests/consumers/test_check_package.py
  - tests/libretro/retroarch_smoke.py
  - tests/libretro/test_retroarch_smoke.py
  - tests/tools/check_runtime_storage.py
  - tests/tools/check_security_register.py
  - tests/tools/test_check_runtime_storage.py
  - tests/tools/test_check_security_register.py
  - tests/tools/test_private_paths.py
  - tests/tools/test_verify_playable.py
  - tests/workflow/test_public_content.py
  - tools/private_paths.py
  - tools/verify_playable.py
findings:
  critical: 0
  warning: 6
  info: 4
  total: 10
status: issues_found
---

# Phase 04: Incremental Code Review of Gap-Closure Changes

**Reviewed:** 2026-10-10
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

This is the incremental re-review of the gap-closure changes (plans 04-24..04-31) since diff_base `20dea9db5beb01df265d33fda6a44bfa37571a8e`. It is separate from `04-REVIEW.md`, which stays as provenance for the crosswalk gate. Finding IDs use GCR/GWR/GIN so they cannot collide with CR/WR/IN.

RetroArch was not launched. I ran the pure-Python suites (`test_private_paths`, `test_check_runtime_storage`, `test_check_security_register`, `test_check_package`, `test_public_content`), `verify_playable.py --check-docs`, and the security-register gate. All passed.

The prior blockers are largely fixed correctly:
- Private-path scanning is now a single canonical-form matcher with an origin map, and every public sink calls `scan_public_value`.
- Process control is scoped. The runner and smoke refuse to stack instances. The bundle-id quit is used only when the launched PID is the sole instance. The runner signals only the PID the smoke recorded, and only while it is a group leader.
- The frontend evidence is now bound to committed bytes with no silent skip when `.git` is absent.

No new blockers. The remaining defects are fail-open gaps in the new gates and a few process-control edge cases.

## Warnings

### GWR-01: Security-register gate silently ignores a `Threat ID` table that lacks Severity or Status columns

**File:** `tests/tools/check_security_register.py:111-113`
**Issue:** `register_errors` now `continue`s past any `| Threat ID |` table whose header lacks `Severity` or `Status`. The old code reported an error. Only `no threat register table` is reported, and only when no table qualifies. A second register table with a renamed column (for example `Sev`) is skipped, so its open high threats are not counted. `threats_open` can then be set to match the undercount and the gate passes. This is fail-open in a gate whose purpose is to be fail-closed.
**Fix:**
```python
if "Severity" not in columns or "Status" not in columns:
    errors.append(f"{path.name}: threat table at line {index + 1} lacks Severity or Status columns")
    continue
```
Add a mutation test for this case.

### GWR-02: Writable-storage audit can pass without checking anything

**File:** `tests/tools/check_runtime_storage.py:23-25, 37-47`
**Issue:** Three gaps make the control fail-open.
- (a) ELF types `C`/`c` (common) and `S`/`s` (small data and bss) are not in `ELF_WRITABLE`. I confirmed that `0000 C common` is not reported. A `-fcommon` archive therefore yields mutable shared state with a PASS.
- (b) Mach-O thread-local sections (`__DATA,__thread_bss` and `__thread_data`) are not selected. I confirmed that `__thread_bss` is not reported.
- (c) Nothing checks that any symbol line was parsed. If an `nm` format change or a bad `--nm` makes the regexes match nothing, the result is `PASS: no writable runtime storage`. An empty `CMAKE_NM` becomes `--nm ""`, which reports FAIL as an OSError rather than SKIP.

**Fix:** Add `Cc` and `Ss` to `ELF_WRITABLE`. Add the `__thread_*` sections to `DARWIN_SECTIONS`. Count the lines that parsed as symbols of any kind and fail if the count is zero. In CMake, skip with code 77 when `CMAKE_NM` is empty.

### GWR-03: CTest green does not mean threats closed, and the register gate can be absent

**File:** `CMakeLists.txt:872-886`, `tests/tools/check_security_register.py:187-190`
**Issue:** There are two problems.
- (a) The `planning_security_register` test runs without `--require-closed`. Today it prints `PASS ... 04-SECURITY.md=14, 05-SECURITY.md=9` while 23 blocking threats are open. The docstring discloses this, but a green qualification-tools label next to a security gate reads as closure. `--require-closed` currently exits 1.
- (b) The test is not registered when the workstream directory is missing. In a source archive or a renamed workstream the gate disappears with only a STATUS message.
- (c) The workstream `config.json` that can lower `security_block_on` is untracked (see git status). Local and CI thresholds can therefore differ.

**Fix:** Name the test `planning_security_register_consistency` so it does not claim closure. Run `--require-closed` at the ship and release gate. Track the workstream config, or document that it is local. Fail configure when `GLUEYNEO_PLANNING_WORKSTREAM` is set explicitly and absent.

### GWR-04: Lane timeout can SIGKILL a process group after its leader is reaped, and survivor cleanup does not escalate

**File:** `tools/verify_playable.py:497-515, 561-567`
**Issue:** There are two problems.
- (a) `_terminate_lane_group` unconditionally sends `SIGKILL` to `os.killpg(proc.pid)` after the leader has been reaped by `communicate`. Once the pgid has no members, a recycled PID can become an unrelated group. The risk is small, but this is the same class of defect that `kill_launched_group` avoids with its `poll()` guard.
- (b) The survivor path sends only `SIGTERM` to the recorded RetroArch group and reports it as signalled without checking that it exited. A frontend that ignores SIGTERM stays running, and the next lane then refuses with `already-running`.

**Fix:** For (a), send the final SIGKILL only if `os.killpg(pid, 0)` still finds members, and do it before the leader is reaped, or use `Popen.kill` semantics on the live leader. For (b), poll `_retroarch_pids()` briefly after SIGTERM and escalate to SIGKILL on the same recorded group, then report whether it is gone.

### GWR-05: Async signal handler can orphan a child, and descendants are not killed once the leader has exited

**File:** `tests/libretro/retroarch_smoke.py:595-609, 585-593`
**Issue:** There are two problems.
- (a) `interrupted` raises `SmokeBlocked` from the signal handler at an arbitrary bytecode boundary. If it fires between the fork inside `Popen` and the assignment of `process`, the child exists but is untracked. No cleanup runs and no PID file is written.
- (b) `kill_launched_group` returns early when the leader has already exited (`poll() is not None`). Group members that outlive the leader (RetroArch helper processes) are then left running.

**Fix:** For (a), block the signals around `Popen` with `signal.pthread_sigmask` and unblock after the PID is recorded. For (b), when the leader has exited, verify that `os.killpg(pid, 0)` still succeeds and the group is ours before killing. Alternatively, track the group by the recorded PID.

### GWR-06: Evidence recording is atomic per file but not across the three files

**File:** `tools/verify_playable.py:~936-946`
**Issue:** The records are validated and scanned first, which is good. They are then replaced one after another with `os.replace`. A failure on the second or third replace leaves the evidence JSON updated while the guide or validation row is stale. `--check-docs` then fails with a mismatch, so it is detectable rather than silent. The docstring and WR-01 imply all-or-nothing.
**Fix:** Write the status block last, so that the gate fails closed until the bundle is complete. Or restore the originals on failure. Document the actual guarantee.

## Info

### GIN-01: `private_paths` specific-root matching has no word boundary

**File:** `tools/private_paths.py:181-189`
**Issue:** Specific needles match anywhere in the canonical string. A root such as `var/tmp` or a short two-component checkout name matches inside unrelated text (`docs/var/tmp-like`, `xusers/jonathan`). Output is over-redacted or falsely rejected. This is fail-closed and acceptable, but it can make a public sink fail for benign content.
**Fix:** Require that the match start at a canonical `/` boundary or at index 0, and end at `/` or the end of the string.

### GIN-02: `scan_public_value` raises TypeError rather than PrivatePathError on unserializable keys

**File:** `tools/private_paths.py:277-279`
**Issue:** `json.dumps(..., sort_keys=True, default=str)` raises `TypeError` for dict keys that are tuples or mixed types. Callers that catch only `PrivatePathError` (`_write_receipt`, `public_json`) propagate the error. The CLI top-level handlers cover it, but a sink that fails open on an exception path is worth closing.
**Fix:** Catch `TypeError` and `ValueError` in `scan_public_value` and raise `PrivatePathError("unscannable-value")`.

### GIN-03: Crosswalk path regex and verified-status match are loose

**File:** `tools/verify_playable.py:~1012` (`PATH_REFERENCE`), `tests/tools/check_security_register.py:84`
**Issue:** `PATH_REFERENCE` admits a leading `..`, so a scope can cite `../x.md`. The reviewed-list check limits the damage. The `status: verified` pattern misses the quoted form (`status: "verified"`), which skips the `threats_open: 0` requirement.
**Fix:** Reject `..` segments. Strip quotes before matching the status.

### GIN-04: Coverage stays narrower than the guide's wording

**File:** `tools/verify_playable.py` (`_GUIDE_CLAIM_PATTERNS`), `docs/first-playable-build.md`
**Issue:** The prose-claim gate rejects hex tokens of 7 to 40 characters only. A 64-character digest passes, and the lowercase `complete` passes. The guide states the gate behavior accurately, so this is only a note: it is not a general claim detector, and nothing should treat it as one.
**Fix:** None required. Keep the guide wording as is.

---

_Reviewed: 2026-10-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
