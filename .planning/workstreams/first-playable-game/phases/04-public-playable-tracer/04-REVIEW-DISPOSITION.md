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
    disposition: open
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
open: 2
total: 34
recorded: 2026-10-10T12:57:15.286Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/private_paths.py:95-141 canonicalizes escapes, percent decoding to a fixpoint and separator runs; the full table, including a non-home root, is tested at tests/tools/test_private_paths.py:124-162. |
| CR-02 | critical | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/private_paths.py:59,98-99 decodes `\uXXXX`; :287 serializes with ensure_ascii=False; JSON-encoded bypasses are tested at tests/tools/test_private_paths.py:102-104,159-175. |
| CR-03 | critical | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:922-936 fails without a repository and binds `--clean` runs via repository=ROOT (:1544) under a clean env and timeout; tests at tests/tools/test_verify_playable.py:917-960. |
| CR-04 | critical | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:825-829,948-954,1213-1215 reject claims outside the block; the stale 706516 prose is gone from docs/first-playable-build.md; tests at tests/tools/test_verify_playable.py:1086-1119. |
| CR-05 | critical | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:1130-1144 resolves threat IDs and paths and reports each failure separately; tests at tests/tools/test_verify_playable.py:985-1000. |
| CR-06 | critical | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/tools/check_security_register.py:94-161 reads frontmatter only, requires one key, scans every table and splits on unescaped pipes; mutations at tests/tools/test_check_security_register.py:72-118. |
| CR-07 | critical | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:614-648,685-693 and tests/libretro/retroarch_smoke.py:707-738 add the pre-launch refusal, process groups, signal cleanup and quit-by-PID unless ours is the sole instance; tests at tests/tools/test_verify_playable.py:641-716. |
| CR-08 | critical | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:1501 uses `runner.lanes if runner is not None else {}`; test at tests/tools/test_verify_playable.py:1236-1248. |
| CR-09 | critical | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:493-500,1342-1358 route errors through `emit_error` and catch OSError/UnicodeError; tests at tests/tools/test_verify_playable.py:1250-1279. |
| WR-01 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:986-1035 validates all targets before temp-and-replace; tests at tests/tools/test_verify_playable.py:1153-1177. |
| WR-02 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:844-868 type-checks retroarch, os, core_sha256, input_mapping and rejects bool markers; mutations at tests/tools/test_verify_playable.py:791-796. |
| WR-03 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:685-693,527-545 use Popen(start_new_session) and kill the group while keeping partial output; tests at tests/tools/test_verify_playable.py:505-566. |
| WR-04 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/libretro/retroarch_smoke.py:215-241 requires IEND plus a stable size/mtime; :331-377 wraps decode errors and bounds inflation; tests at tests/libretro/test_retroarch_smoke.py:628-676. |
| WR-05 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/libretro/retroarch_smoke.py:875-877 checks st_size==602 before reading; test at tests/libretro/test_retroarch_smoke.py:678. |
| WR-06 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/private_paths.py:213-219 (start-only generic roots), :242-243 (service account) and :172-175,236-239 (guarded Path.home); tests at tests/tools/test_private_paths.py:177-230. |
| WR-07 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): CMakeLists.txt:883-905 registers conditionally from a variable; tests/tools/check_security_register.py:54-91,197 validate severity and name without tracebacks; tests at tests/tools/test_check_security_register.py:88-178. |
| WR-08 | warning | open | Tool-scoped independent review (04-34, 0d9612130092): tests/tools/check_runtime_storage.py:35 never parses Mach-O `private external`, `weak external` or `(common)` lines, so hidden-visibility mutable globals in the duplicated runtime (CMakeLists.txt:160-168) go unaudited on macOS. The guard's limits are documented in place (CMakeLists.txt:929-935). |
| WR-09 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:927-930,1155-1158 run git with clean_environment() and a timeout. |
| IN-01 | info | fixed | Tool-scoped independent review (04-34, 0d9612130092): docs/first-playable-build.md:84-96 has a single historical section with no 706516 or Plan 04-08 text; pinned by tests/tools/test_verify_playable.py:1117-1119. |
| IN-02 | info | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/libretro/retroarch_smoke.py:89-101 no longer has the `cursor > len` check, and validate_inputs (:846-848) only does the equality check; tests at tests/libretro/test_retroarch_smoke.py:367-372. |
| IN-03 | info | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/consumers/check_package.py:312 uses a regex for otool paths, :448 has the formatting fixed, :334-342 adds the system allowlist; tests at tests/consumers/test_check_package.py:50-67. |
| IN-04 | info | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/tools/test_private_paths.py:141-183 (JSON forms, non-home root), tests/tools/test_check_security_register.py:72-118 and tests/tools/test_verify_playable.py:917-1248 cover each listed gap. |
| WR-10 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/tools/test_verify_playable.py:966-974 asserts the mutation changed the text and checks a target-specific error regex (:985-1018). |
| WR-11 | warning | open | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:1048-1058 no tracked code parses or rejects duplicate or malformed review revision keys, and `_reviewed_paths` keeps the first `files_reviewed_list` while ignoring duplicates. No regression test exists in tests/tools/test_verify_playable.py. |
| GWR-01 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/tools/check_security_register.py:127-129 errors on a table lacking Severity or Status; mutation at tests/tools/test_check_security_register.py:181-217. |
| GWR-02 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/tools/check_runtime_storage.py:31-37,92-104 add Cc/Ss, the `__thread_*` sections, a zero-parse failure and skip on empty nm; tests at tests/tools/test_check_runtime_storage.py:62-121. The Mach-O private-external gap is a separate defect, recorded under T-04-56. |
| GWR-03 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): CMakeLists.txt:883-905 renames the test to `_consistency` and fails configure on an explicit missing workstream; `--require-closed` exists (tests/tools/check_security_register.py:228-233); the local config cannot weaken the threshold (:88-89), documented at docs/testing.md:98-105. |
| GWR-04 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:514-545 signals only before reaping, using WNOWAIT; :577-599 escalates and reports; tests at tests/tools/test_verify_playable.py:568-594,664-685. |
| GWR-05 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tests/libretro/retroarch_smoke.py:664-704 defers signals in the launch window; :612-661 sweeps the group of an exited, unreaped leader; tests at tests/libretro/test_retroarch_smoke.py:1195-1346. |
| GWR-06 | warning | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:977-1035 restores originals, writes the guide last and documents the crash limit; tests at tests/tools/test_verify_playable.py:1179-1214. |
| GIN-01 | info | deferred | Tool-scoped independent review (04-34, 0d9612130092): tools/private_paths.py:264-266 documents the accepted fail-closed overmatch, pinned by tests/tools/test_private_paths.py:272-278.; residual accepted: `private_paths` specific-root matching overmatches by design (fail-closed, documented in place) |
| GIN-02 | info | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/private_paths.py:286-289 raises PrivatePathError("unscannable-value"); test at tests/tools/test_private_paths.py:265-270. |
| GIN-03 | info | fixed | Tool-scoped independent review (04-34, 0d9612130092): tools/verify_playable.py:1139-1140 rejects `..`, and tests/tools/check_security_register.py:50 accepts the quoted status; tests at tests/tools/test_verify_playable.py:997-1000 and tests/tools/test_check_security_register.py:99-100. |
| GIN-04 | info | deferred | Tool-scoped independent review (04-34, 0d9612130092): docs/first-playable-build.md:82 states the 7-to-40 hex limit and that other prose is not machine-checked; pinned by tests/tools/test_verify_playable.py:1130-1136.; residual accepted: the prose-claim gate checks 7-to-40 hex tokens only, stated in the guide |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
