---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "Private-path redaction and scan miss separator/encoding variants (confirmed)"
  - id: CR-02
    severity: critical
    disposition: fixed
    title: "`scan_public` is applied to `ensure_ascii` JSON, which defeats NFKC folding at every sink"
  - id: CR-03
    severity: critical
    disposition: fixed
    title: "Frontend-evidence inventory binding is skipped when `.git` is absent, including the documented `--clean --check-docs` path (confirmed)"
  - id: CR-04
    severity: critical
    disposition: fixed
    title: "`check_docs` passes affirmative success prose outside the generated status block (confirmed)"
  - id: CR-05
    severity: critical
    disposition: fixed
    title: "Crosswalk \"Existing Threat Scope\" accepts any non-empty text, including nonexistent paths (confirmed)"
  - id: CR-06
    severity: critical
    disposition: fixed
    title: "`check_security_register.py` reads only the first `threats_open` and only the first threat table (confirmed)"
  - id: CR-07
    severity: critical
    disposition: fixed
    title: "Outer timeout orphans the `start_new_session` RetroArch child; no pre-launch instance check (confirmed)"
  - id: CR-08
    severity: critical
    disposition: fixed
    title: "`main()` raises `AttributeError` on any early failure, so no receipt is written"
  - id: CR-09
    severity: critical
    disposition: fixed
    title: "Raw exception text is printed unredacted from `--record-frontend-evidence` and `--check-docs`"
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "`write_frontend_records` is non-atomic and writes before validating its targets"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "`validate_frontend_evidence` does not type-check nested fields it later dereferences"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "`Runner.command` timeout kills only the direct child"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "Screenshot handling is racy and can raise uncaught non-`SmokeBlocked` exceptions"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "Unbounded read of non-GNMV content before the size check"
  - id: WR-06
    severity: warning
    disposition: fixed
    title: "`private_paths` fails closed on benign text (self-inflicted false positives)"
  - id: WR-07
    severity: warning
    disposition: fixed
    title: "Product CTest couples to planning state and a hard-coded workstream; `block_on` is brittle"
  - id: WR-08
    severity: warning
    disposition: deferred
    title: "`glueyneo_runtime_static` duplicates runtime state and the configure-time guard is heuristic"
  - id: WR-09
    severity: warning
    disposition: fixed
    title: "Local `git` invocations use the caller's environment"
  - id: IN-01
    severity: info
    disposition: fixed
    title: "Stale and contradictory guide text"
  - id: IN-02
    severity: info
    disposition: fixed
    title: "Dead or redundant code in `retroarch_smoke.py`"
  - id: IN-03
    severity: info
    disposition: fixed
    title: "Minor issues in `check_package.py`"
  - id: IN-04
    severity: info
    disposition: fixed
    title: "Test-oracle gaps that let the confirmed defects through"
  - id: WR-10
    severity: warning
    disposition: fixed
    title: "Evidence-map mutation tests fail before exercising their target"
  - id: WR-11
    severity: warning
    disposition: open
    title: "Review identity parser accepts duplicate revision keys"
  - id: GWR-01
    severity: warning
    disposition: fixed
    title: "Security-register gate silently ignores a `Threat ID` table that lacks Severity or Status columns"
  - id: GWR-02
    severity: warning
    disposition: fixed
    title: "Writable-storage audit can pass without checking anything"
  - id: GWR-03
    severity: warning
    disposition: fixed
    title: "CTest green does not mean threats closed, and the register gate can be absent"
  - id: GWR-04
    severity: warning
    disposition: fixed
    title: "Lane timeout can SIGKILL a process group after its leader is reaped, and survivor cleanup does not escalate"
  - id: GWR-05
    severity: warning
    disposition: fixed
    title: "Async signal handler can orphan a child, and descendants are not killed once the leader has exited"
  - id: GWR-06
    severity: warning
    disposition: fixed
    title: "Evidence recording is atomic per file but not across the three files"
  - id: GIN-01
    severity: info
    disposition: deferred
    title: "`private_paths` specific-root matching has no word boundary"
  - id: GIN-02
    severity: info
    disposition: fixed
    title: "`scan_public_value` raises TypeError rather than PrivatePathError on unserializable keys"
  - id: GIN-03
    severity: info
    disposition: fixed
    title: "Crosswalk path regex and verified-status match are loose"
  - id: GIN-04
    severity: info
    disposition: deferred
    title: "Coverage stays narrower than the guide's wording"
open: 1
total: 34
recorded: 2026-10-10T12:57:15.286Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/private_paths.py:110-158 canonicalizes escapes, percent encoding, NFKC and separator runs. The full variant table, including a non-home root, is tested at tests/tools/test_private_paths.py:124-170. |
| CR-02 | critical | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/private_paths.py:274-307 scans decoded values and keys and serializes with ensure_ascii=False. Tested at tests/tools/test_private_paths.py:159-162,172-175. |
| CR-03 | critical | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:933-955,1560 binds evidence to ROOT and the snapshot commit using clean_environment and a timeout. Tested at tests/tools/test_verify_playable.py:926-969. |
| CR-04 | critical | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:959-965,1229-1231 rejects claims outside the generated block, and the stale paragraph is gone from docs/first-playable-build.md. Tested at tests/tools/test_verify_playable.py:1108-1144. |
| CR-05 | critical | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:1146-1160 resolves threat IDs and paths and reports each failure separately. Tested at tests/tools/test_verify_playable.py:994-1009. |
| CR-06 | critical | fixed | Tool-scoped independent review (04-36, bd74482e0050): tests/tools/check_security_register.py:96-137 reads frontmatter only, requires exactly one key, reads every table and splits on unescaped pipes. Tested at test_check_security_register.py:85-131. |
| CR-07 | critical | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:614-648,685-693 and tests/libretro/retroarch_smoke.py:707-738 add the pre-launch refusal, process groups, signal cleanup and quit-by-PID unless ours is the sole instance; tests at tests/tools/test_verify_playable.py:641-716. |
| CR-08 | critical | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:1517 uses `runner.lanes if runner is not None else {}`. Tested at tests/tools/test_verify_playable.py:1261. |
| CR-09 | critical | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:493-500,1358-1374 sends errors through emit_error with catch-alls. Tested at tests/tools/test_verify_playable.py:1275-1298. |
| WR-01 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:997-1046 computes and validates all three contents before writing, then uses temp files, os.replace and rollback. Tested at tests/tools/test_verify_playable.py:1178-1241. |
| WR-02 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:855-880 type-checks retroarch, os, core_sha256 and input_mapping and rejects bool markers. Tested at tests/tools/test_verify_playable.py:800-805. |
| WR-03 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:696-704,527-545 starts a new session, kills the group and keeps partial output. Tested at tests/tools/test_verify_playable.py:505-535. |
| WR-04 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/libretro/retroarch_smoke.py:215-241 requires IEND plus a stable size/mtime; :331-377 wraps decode errors and bounds inflation; tests at tests/libretro/test_retroarch_smoke.py:628-676. |
| WR-05 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/libretro/retroarch_smoke.py:875-877 checks st_size==602 before reading; test at tests/libretro/test_retroarch_smoke.py:678. |
| WR-06 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/private_paths.py:230-236,252-263,189-192 limits generic roots to path starts, makes the username check CI-aware and guards Path.home(). Tested at tests/tools/test_private_paths.py:177-230. |
| WR-07 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): CMakeLists.txt:883-905 registers conditionally. tests/tools/check_security_register.py:56-93,199-201 validates severity and workstream and prints `FAIL:` instead of a traceback. |
| WR-08 | warning | deferred | Tool-scoped independent review (04-36, bd74482e0050): The runtime_writable_storage audit (CMakeLists.txt:910-915, tests/tools/check_runtime_storage.py) proves the copies share no mutable state. The guard's limits are stated at CMakeLists.txt:929-935 and docs/testing.md:193-197.; residual accepted: configure-time sdk_private.h guard remains heuristic, limits documented in CMakeLists.txt and docs/testing.md; reopen on a shared-build link failure the guard misses or any writable runtime symbol |
| WR-09 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:938-941 runs merge-base with clean_environment() and a timeout. |
| IN-01 | info | fixed | Tool-scoped independent review (04-36, bd74482e0050): docs/first-playable-build.md:84-96 has one historical section, and the 706516b5a60c and Plan 04-08 text is gone. Pinned by tests/tools/test_verify_playable.py:1142. |
| IN-02 | info | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/libretro/retroarch_smoke.py:89-101 no longer has the `cursor > len` check, and validate_inputs (:846-848) only does the equality check; tests at tests/libretro/test_retroarch_smoke.py:367-372. |
| IN-03 | info | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/consumers/check_package.py:312 uses a regex for otool paths, :448 has the formatting fixed, :334-342 adds the system allowlist; tests at tests/consumers/test_check_package.py:50-67. |
| IN-04 | info | fixed | Tool-scoped independent review (04-36, bd74482e0050): Each defect now has a regression test: tests/tools/test_private_paths.py:141-183, tests/tools/test_check_security_register.py:59-131 and tests/tools/test_verify_playable.py:926-1009,1261. |
| WR-10 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tests/tools/test_verify_playable.py:975-983,1094-1105 asserts that each mutation changed the text and expects the targeted error message. |
| WR-11 | warning | open | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:1059-1074 rejects only duplicate frontmatter keys. Nothing parses or requires exactly one well-formed `reviewed_revision` value, so a malformed sole value passes. |
| GWR-01 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tests/tools/check_security_register.py:129-131 reports the error. Tested at tests/tools/test_check_security_register.py:205-221. |
| GWR-02 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tests/tools/check_runtime_storage.py:32-43,98-110 covers Cc, Ss and __thread_*, counts parsed lines and skips with 77 when `nm` is empty. Tested at tests/tools/test_check_runtime_storage.py:63-151. |
| GWR-03 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): CMakeLists.txt:891-897 renames the test to `planning_security_register_consistency` and fails configure on an explicit missing workstream. docs/testing.md:95-148 documents `--require-closed` and that the workstream config is local. |
| GWR-04 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:514-545 sends the group SIGKILL before reaping, and :597-610 escalates on the recorded group. Tested at tests/tools/test_verify_playable.py:568,671. |
| GWR-05 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tests/libretro/retroarch_smoke.py:664-704 defers signals in the launch window, and :612-661 sweeps the group while the leader is an unreaped zombie. Tested at tests/libretro/test_retroarch_smoke.py:1195-1339. |
| GWR-06 | warning | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:1023-1043 restores originals and writes the guide last, and :989-996 documents the guarantee. Tested at tests/tools/test_verify_playable.py:1204-1226. |
| GIN-01 | info | deferred | Tool-scoped independent review (04-36, bd74482e0050): The fail-closed limit is documented at tools/private_paths.py:282-283 and docs/testing.md:217-220 and pinned by tests/tools/test_private_paths.py:272-278.; residual accepted: `private_paths` specific-root matching overmatches by design (fail-closed, documented in place) |
| GIN-02 | info | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/private_paths.py:303-306 raises unscannable-value. Tested at tests/tools/test_private_paths.py:265-270. |
| GIN-03 | info | fixed | Tool-scoped independent review (04-36, bd74482e0050): tools/verify_playable.py:1154-1156 rejects `..`, and tests/tools/check_security_register.py:52 accepts the quoted verified status. Tested at tests/tools/test_verify_playable.py:1006-1009. |
| GIN-04 | info | deferred | Tool-scoped independent review (04-36, bd74482e0050): The limit is documented at docs/first-playable-build.md:82 and pinned by tests/tools/test_verify_playable.py:1155-1161.; residual accepted: the prose-claim gate checks 7-to-40 hex tokens only, stated in the guide |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
