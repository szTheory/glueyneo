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
    disposition: fixed
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
  - id: G2CR-01
    severity: critical
    disposition: fixed
    title: "Brace-alternative absolute glob escapes containment (T-04-61)"
  - id: G2CR-02
    severity: critical
    disposition: fixed
    title: "Receipt construction and write run outside any try block (T-04-11)"
  - id: G2WR-01
    severity: warning
    disposition: fixed
    title: "Review provenance accepts any ancestor commit; `reviewed_revision` is never parsed (T-04-38)"
  - id: G2WR-02
    severity: warning
    disposition: fixed
    title: "Malformed sole `reviewed_revision` / revision value passes (WR-11, T-04-67 bundle)"
  - id: G2WR-03
    severity: warning
    disposition: fixed
    title: "Transcription gate pins the review by string prefix with an unvalidated revision"
  - id: G2WR-04
    severity: warning
    disposition: fixed
    title: "Milestone-wide register gate skips decimal phases that `--phase` accepts"
  - id: G2WR-05
    severity: warning
    disposition: fixed
    title: "Evidence rollback is not robust to a missing file or a failed restore"
  - id: G2WR-06
    severity: warning
    disposition: fixed
    title: "Launch window can swallow a termination signal and mislabel a pid-record failure"
  - id: G2IN-01
    severity: info
    disposition: fixed
    title: "`status: verified` match is case-sensitive"
  - id: G2IN-02
    severity: info
    disposition: fixed
    title: "Lane termination wait does not drain the pipe"
  - id: G2IN-03
    severity: info
    disposition: fixed
    title: "Qualification-failure reasons use bare `redact` while documentation reasons use the scan-backed helper"
  - id: G3WR-01
    severity: warning
    disposition: fixed
    title: "Lane timeout output is duplicated and out of order after the drain change (regression from G2IN-02)"
  - id: G3WR-02
    severity: warning
    disposition: fixed
    title: "Reviewer gate does not recognize G3 finding IDs; the ID alternation is hand-extended every round"
  - id: G3WR-03
    severity: warning
    disposition: fixed
    title: "Diagnostic probe still labels a child-PID-record failure as `launch` and reports a running frontend as not started"
  - id: G3WR-04
    severity: warning
    disposition: fixed
    title: "Rollback can still abort mid-way through the `.restore` cleanup, defeating \"every restore is attempted\" (G2WR-05)"
  - id: G3WR-05
    severity: warning
    disposition: fixed
    title: "Provenance window is anchored to the original review, so it cannot order dispositions of later gap-round findings"
  - id: G3IN-01
    severity: info
    disposition: fixed
    title: "`$`-prefixed patterns are refused inside groups but not at the top level, contradicting the comment and docs"
  - id: G3IN-02
    severity: info
    disposition: fixed
    title: "Dead launch diagnostic in `run_smoke` for the `pid-record` branch"
  - id: G3IN-03
    severity: info
    disposition: fixed
    title: "Register checker silently ignores mis-named register files and `verified` with a trailing comment"
  - id: G4WR-01
    severity: warning
    disposition: fixed
    title: "Lane timeout output is lost (or reordered) when the post-kill `communicate` yields no tail"
  - id: G4WR-02
    severity: warning
    disposition: fixed
    title: "Register checker accepts case-folded and non-ASCII-digit spellings that the GSD reader does not read as `threats_open`"
  - id: G4WR-03
    severity: warning
    disposition: fixed
    title: "A lane that emits non-UTF-8 bytes raises `UnicodeDecodeError` instead of being recorded (pre-existing, on the path this round rewrote)"
  - id: G4WR-04
    severity: warning
    disposition: fixed
    title: "R3's rights-inventory claim does not hold; one `source_revision` does not resolve and four are stale"
  - id: G4IN-01
    severity: info
    disposition: fixed
    title: "Misnamed-register detection still depends on a two-digit filename prefix"
  - id: G4IN-02
    severity: info
    disposition: fixed
    title: "Rollback reports 'incomplete' for a successful restore and swallows `.tmp` debris silently"
  - id: G4IN-03
    severity: info
    disposition: fixed
    title: "The diagnostic runner proceeds to the second probe after a pid-record failure"
  - id: G5WR-01
    severity: warning
    disposition: fixed
    title: "Rights source_revision gate requires branch commits to be ancestors of head, but the repository only allows squash merges"
  - id: G5WR-02
    severity: warning
    disposition: fixed
    title: "Lane-signalling tests have no readiness handshake with the child they SIGTERM"
  - id: G5IN-01
    severity: info
    disposition: fixed
    title: "third_party/ rows skip the path-form check, and a non-list items raises a bare TypeError"
  - id: G6WR-01
    severity: warning
    disposition: deferred
    title: "History allowlist is self-attested; the loader does not validate it against history"
  - id: G6WR-02
    severity: warning
    disposition: fixed
    title: "Duplicate allowlist rows are silently collapsed; last row wins"
  - id: G6WR-03
    severity: warning
    disposition: fixed
    title: "Rights allowlist branch reads `source_root / path` through symlinks and un-normalized paths"
  - id: G6IN-01
    severity: info
    disposition: deferred
    title: "Typing escapes around `HistoryAllowlist.EMPTY`"
  - id: G6IN-02
    severity: info
    disposition: deferred
    title: "`strip_comment` is not quote-aware"
  - id: G6IN-03
    severity: info
    disposition: deferred
    title: "`_drain` treats every `OSError` from `os.read` as EOF"
  - id: G7CR-01
    severity: critical
    disposition: fixed
    title: "The fix commits made the `tests/tools/test_verify_playable.py` rights row stale, which breaks CI public-content now and `--check-docs` after the squash"
  - id: G7CR-02
    severity: critical
    disposition: fixed
    title: "The committed allowlist was generated against a stale local `main`, so the new CI step fails on this PR and 12 rows cite revisions already on main"
  - id: G7WR-01
    severity: warning
    disposition: fixed
    title: "The in-tree anchoring cannot change any gate outcome; docs/testing.md overstates it"
  - id: G7WR-02
    severity: warning
    disposition: fixed
    title: "The CI step runs only when the allowlist file changes, so a stale allowlist can merge"
  - id: G7WR-03
    severity: warning
    disposition: fixed
    title: "The tolerated rights branch still hashes working-tree bytes, not committed bytes (G6WR-03 partly open)"
  - id: G7IN-01
    severity: info
    disposition: fixed
    title: "`--check-docs` on a shallow clone now fails with a misleading message"
  - id: G8IN-01
    severity: info
    disposition: fixed
    title: "The recorded reason for not adding a post-squash stale gate is wrong"
  - id: G9WR-01
    severity: warning
    disposition: fixed
    title: "The U+2215 runner-home input lost its leading homoglyph separators"
  - id: G9IN-01
    severity: info
    disposition: fixed
    title: "The synthetic-path disposition merge has no duplicate or collision guard"
  - id: G9IN-02
    severity: info
    disposition: fixed
    title: "The noreply email test omits lookalike addresses"
  - id: G10IN-01
    severity: info
    disposition: deferred
    title: "`_review_round_findings` hardcodes the round glob"
  - id: G10IN-02
    severity: info
    disposition: deferred
    title: "The G9IN-01 import-time guard has no test"
  - id: G10IN-03
    severity: info
    disposition: deferred
    title: "Round file path lists are self-attested, and the register change has only a parser-level test"
  - id: G11IN-01
    severity: info
    disposition: deferred
    title: "`splitlines()` and the newline guard are not aligned on exotic separators"
  - id: G11IN-02
    severity: info
    disposition: deferred
    title: "`anchored_history_allowlist` gains a new raise path, and the helper trusts `base`"
  - id: G11IN-03
    severity: info
    disposition: deferred
    title: "The equivalence test is meaningful but narrow"
open: 0
total: 85
recorded: 2026-10-12T01:00:00.000Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/private_paths.py:110-158 canonicalizes escapes, percent encoding, NFKC and separator runs. The full variant table, including a non-home root, is tested at tests/tools/test_private_paths.py:124-170. |
| CR-02 | critical | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/private_paths.py:274-307 scans decoded values and keys and serializes with ensure_ascii=False. Tested at tests/tools/test_private_paths.py:159-162,172-175. |
| CR-03 | critical | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:933-955,1560 binds evidence to ROOT and the snapshot commit using clean_environment and a timeout. Tested at tests/tools/test_verify_playable.py:926-969. |
| CR-04 | critical | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:959-965,1229-1231 rejects claims outside the generated block, and the stale paragraph is gone from docs/first-playable-build.md. Tested at tests/tools/test_verify_playable.py:1108-1144. |
| CR-05 | critical | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:1146-1160 resolves threat IDs and paths and reports each failure separately. Tested at tests/tools/test_verify_playable.py:994-1009. |
| CR-06 | critical | fixed | Tool-scoped independent review (04-36, 323fa1453329): tests/tools/check_security_register.py:96-137 reads frontmatter only, requires exactly one key, reads every table and splits on unescaped pipes. Tested at test_check_security_register.py:85-131. |
| CR-07 | critical | fixed | Tool-scoped independent review (04-34, 45952598202a): tools/verify_playable.py:614-648,685-693 and tests/libretro/retroarch_smoke.py:707-738 add the pre-launch refusal, process groups, signal cleanup and quit-by-PID unless ours is the sole instance; tests at tests/tools/test_verify_playable.py:641-716. |
| CR-08 | critical | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:1517 uses `runner.lanes if runner is not None else {}`. Tested at tests/tools/test_verify_playable.py:1261. |
| CR-09 | critical | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:493-500,1358-1374 sends errors through emit_error with catch-alls. Tested at tests/tools/test_verify_playable.py:1275-1298. |
| WR-01 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:997-1046 computes and validates all three contents before writing, then uses temp files, os.replace and rollback. Tested at tests/tools/test_verify_playable.py:1178-1241. |
| WR-02 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:855-880 type-checks retroarch, os, core_sha256 and input_mapping and rejects bool markers. Tested at tests/tools/test_verify_playable.py:800-805. |
| WR-03 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:696-704,527-545 starts a new session, kills the group and keeps partial output. Tested at tests/tools/test_verify_playable.py:505-535. |
| WR-04 | warning | fixed | Tool-scoped independent review (04-34, 45952598202a): tests/libretro/retroarch_smoke.py:215-241 requires IEND plus a stable size/mtime; :331-377 wraps decode errors and bounds inflation; tests at tests/libretro/test_retroarch_smoke.py:628-676. |
| WR-05 | warning | fixed | Tool-scoped independent review (04-34, 45952598202a): tests/libretro/retroarch_smoke.py:875-877 checks st_size==602 before reading; test at tests/libretro/test_retroarch_smoke.py:678. |
| WR-06 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/private_paths.py:230-236,252-263,189-192 limits generic roots to path starts, makes the username check CI-aware and guards Path.home(). Tested at tests/tools/test_private_paths.py:177-230. |
| WR-07 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): CMakeLists.txt:883-905 registers conditionally. tests/tools/check_security_register.py:56-93,199-201 validates severity and workstream and prints `FAIL:` instead of a traceback. |
| WR-08 | warning | deferred | Tool-scoped independent review (04-36, 323fa1453329): The runtime_writable_storage audit (CMakeLists.txt:910-915, tests/tools/check_runtime_storage.py) proves the copies share no mutable state. The guard's limits are stated at CMakeLists.txt:929-935 and docs/testing.md:193-197.; residual accepted: configure-time sdk_private.h guard remains heuristic, limits documented in CMakeLists.txt and docs/testing.md; reopen on a shared-build link failure the guard misses or any writable runtime symbol |
| WR-09 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:938-941 runs merge-base with clean_environment() and a timeout. |
| IN-01 | info | fixed | Tool-scoped independent review (04-36, 323fa1453329): docs/first-playable-build.md:84-96 has one historical section, and the 5e6a3b8f50d3 and Plan 04-08 text is gone. Pinned by tests/tools/test_verify_playable.py:1142. |
| IN-02 | info | fixed | Tool-scoped independent review (04-34, 45952598202a): tests/libretro/retroarch_smoke.py:89-101 no longer has the `cursor > len` check, and validate_inputs (:846-848) only does the equality check; tests at tests/libretro/test_retroarch_smoke.py:367-372. |
| IN-03 | info | fixed | Tool-scoped independent review (04-34, 45952598202a): tests/consumers/check_package.py:312 uses a regex for otool paths, :448 has the formatting fixed, :334-342 adds the system allowlist; tests at tests/consumers/test_check_package.py:50-67. |
| IN-04 | info | fixed | Tool-scoped independent review (04-36, 323fa1453329): Each defect now has a regression test: tests/tools/test_private_paths.py:141-183, tests/tools/test_check_security_register.py:59-131 and tests/tools/test_verify_playable.py:926-1009,1261. |
| WR-10 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tests/tools/test_verify_playable.py:975-983,1094-1105 asserts that each mutation changed the text and expects the targeted error message. |
| WR-11 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:1059-1074 rejects only duplicate frontmatter keys. Nothing parses or requires exactly one well-formed `reviewed_revision` value, so a malformed sole value passes. Gap-closure fix (04-38) at revision `97fbbdaa75120c27845b24679c3948e6206ec42f`: tools/verify_playable.py _reviewed_revision requires exactly one 40-hex value; regression tests test_wr_11_reviewed_revision_must_appear_exactly_once_and_be_40_hex and test_wr_11_duplicate_review_frontmatter_keys_are_rejected, red commit `1a33f9e1c894737ee9565ef3952c155704c4f5e8`. R3 verdict Fixed (04-REVIEW-GAPS-R3.md at revision `77d5159ee5b77980b6b83bbde5ea5d34709cda34`). |
| GWR-01 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tests/tools/check_security_register.py:129-131 reports the error. Tested at tests/tools/test_check_security_register.py:205-221. |
| GWR-02 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tests/tools/check_runtime_storage.py:32-43,98-110 covers Cc, Ss and __thread_*, counts parsed lines and skips with 77 when `nm` is empty. Tested at tests/tools/test_check_runtime_storage.py:63-151. |
| GWR-03 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): CMakeLists.txt:891-897 renames the test to `planning_security_register_consistency` and fails configure on an explicit missing workstream. docs/testing.md:95-148 documents `--require-closed` and that the workstream config is local. |
| GWR-04 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:514-545 sends the group SIGKILL before reaping, and :597-610 escalates on the recorded group. Tested at tests/tools/test_verify_playable.py:568,671. |
| GWR-05 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tests/libretro/retroarch_smoke.py:664-704 defers signals in the launch window, and :612-661 sweeps the group while the leader is an unreaped zombie. Tested at tests/libretro/test_retroarch_smoke.py:1195-1339. |
| GWR-06 | warning | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:1023-1043 restores originals and writes the guide last, and :989-996 documents the guarantee. Tested at tests/tools/test_verify_playable.py:1204-1226. |
| GIN-01 | info | deferred | Tool-scoped independent review (04-36, 323fa1453329): The fail-closed limit is documented at tools/private_paths.py:282-283 and docs/testing.md:217-220 and pinned by tests/tools/test_private_paths.py:272-278.; residual accepted: `private_paths` specific-root matching overmatches by design (fail-closed, documented in place) |
| GIN-02 | info | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/private_paths.py:303-306 raises unscannable-value. Tested at tests/tools/test_private_paths.py:265-270. |
| GIN-03 | info | fixed | Tool-scoped independent review (04-36, 323fa1453329): tools/verify_playable.py:1154-1156 rejects `..`, and tests/tools/check_security_register.py:52 accepts the quoted verified status. Tested at tests/tools/test_verify_playable.py:1006-1009. |
| GIN-04 | info | deferred | Tool-scoped independent review (04-36, 323fa1453329): The limit is documented at docs/first-playable-build.md:82 and pinned by tests/tools/test_verify_playable.py:1155-1161.; residual accepted: the prose-claim gate checks 7-to-40 hex tokens only, stated in the guide |
| G2CR-01 | critical | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-37) at revision `3c5255e286b3f593b2c0cbc8aeaf36e0ea69263c`: tools/independent_review.py:62,104-106; regression tests test_t_04_61_absolute_group_alternatives_are_not_contained. R3 verdict Fixed (04-REVIEW-GAPS-R3.md at revision `77d5159ee5b77980b6b83bbde5ea5d34709cda34`). |
| G2CR-02 | critical | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-38) at revision `8446d8d16705e3a47e56909603354379f1275daa`: tools/verify_playable.py:1690-1696; regression tests test_t_04_11_unreadable_artifact_writes_a_fail_receipt_without_traceback, test_t_04_11_receipt_errors_of_any_type_are_fixed_tokens. R3 verdict Fixed (04-REVIEW-GAPS-R3.md at revision `77d5159ee5b77980b6b83bbde5ea5d34709cda34`). |
| G2WR-01 | warning | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-38) at revision `97fbbdaa75120c27845b24679c3948e6206ec42f`: tools/verify_playable.py:1264; regression tests test_t_04_38_disposition_older_than_reviewed_revision_is_rejected. R3 partially fixed; residual G3WR-05 judged Fixed by R4 (revision `58a3ba86a76cf85372f6499ac2e826890a61544a`). |
| G2WR-02 | warning | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-38) at revision `97fbbdaa75120c27845b24679c3948e6206ec42f`: tools/verify_playable.py:1124; regression tests test_wr_11_reviewed_revision_must_appear_exactly_once_and_be_40_hex. R3 verdict Fixed (04-REVIEW-GAPS-R3.md at revision `77d5159ee5b77980b6b83bbde5ea5d34709cda34`). |
| G2WR-03 | warning | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-37) at revision `3c5255e286b3f593b2c0cbc8aeaf36e0ea69263c`: tools/independent_review.py:419-420; regression tests test_g2wr_03_revision_must_be_40_hex, test_g2wr_03_revision_line_must_match_whole_token. R3 verdict Fixed (04-REVIEW-GAPS-R3.md at revision `77d5159ee5b77980b6b83bbde5ea5d34709cda34`). |
| G2WR-04 | warning | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-37) at revision `c33c7c0cbbb5b61777eaad98dbcb371a3e67287d`: tests/tools/check_security_register.py:57,213; regression tests test_g2wr_04_unscoped_gate_counts_decimal_phase_registers. R3 verdict Fixed (04-REVIEW-GAPS-R3.md at revision `77d5159ee5b77980b6b83bbde5ea5d34709cda34`). Residual G3IN-03 closed by G4IN-01 at revision `856592e5ae89c9ec2a56c6651c59ffacc778e836`. |
| G2WR-05 | warning | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-39) at revision `15df7bc5d985f0d4d3e98628cb2307a66cabac98`: tools/verify_playable.py:1029-1094; regression tests test_g2wr_05_first_time_generation_with_absent_evidence_file, test_g2wr_05_failed_restore_continues_and_names_files. R3 partially fixed; residual G3WR-04 judged Fixed by R4 (revision `58a3ba86a76cf85372f6499ac2e826890a61544a`). |
| G2WR-06 | warning | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-37) at revision `f866fa49277abffad5ab2b811fc2d5d57934730f`: tests/libretro/retroarch_smoke.py:676,953; regression tests test_g2wr_06_deferred_signal_survives_a_raising_body, test_g2wr_06_pid_record_failure_is_not_a_launch_failure. R3 partially fixed; residual G3WR-03 judged Fixed by R4 (revision `58a3ba86a76cf85372f6499ac2e826890a61544a`). |
| G2IN-01 | info | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-37) at revision `c33c7c0cbbb5b61777eaad98dbcb371a3e67287d`: tests/tools/check_security_register.py:54; regression tests test_g2in_01_verified_status_is_case_insensitive. R3 verdict Fixed (04-REVIEW-GAPS-R3.md at revision `77d5159ee5b77980b6b83bbde5ea5d34709cda34`). |
| G2IN-02 | info | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-39) at revision `013cd58cacaa9767948ddd6f269a901e5ce127d0`: tools/verify_playable.py:528-598; regression tests test_g2in_02_lane_drains_pipe_during_grace. Regression G3WR-01 resolved by G4WR-01 at revision `f783c73668b2cea08108d390b44025e9cfeb858c`. |
| G2IN-03 | info | fixed | Reported by 04-REVIEW-GAPS-R2.md (e7f6b2b). Gap-closure fix (04-38) at revision `8446d8d16705e3a47e56909603354379f1275daa`: tools/verify_playable.py:1598-1601; regression tests test_g2in_03_build_failure_reason_uses_public_reason. R3 verdict Fixed (04-REVIEW-GAPS-R3.md at revision `77d5159ee5b77980b6b83bbde5ea5d34709cda34`). |
| G3WR-01 | warning | fixed | Reported by 04-REVIEW-GAPS-R3.md (77d5159). Gap-closure fix (04-45) at revision `930be6b489dd71d48d7e2cbbbd4dc008b0f9267f`: tools/verify_playable.py:547 `_terminate_lane_group`; regression tests test_g3wr_01_timed_out_lane_output_is_single_copy_in_order, test_g3wr_01_no_earlier_output. R4: partially fixed; residual G4WR-01 repaired at revision `f783c73668b2cea08108d390b44025e9cfeb858c`. |
| G3WR-02 | warning | fixed | Reported by 04-REVIEW-GAPS-R3.md (77d5159). Gap-closure fix (04-47) at revision `c44cb0bd7ff459fca457c8f93c1e4be853c84803`: tools/independent_review.py:71,213 `ID_PATTERN` and `review_ids`; regression tests test_g3wr_02_round_three_and_later_ids_are_reviewable, test_g3wr_02_review_ids_rejects_malformed_ids, test_g3wr_02_malformed_verdict_lines_leave_the_id_open. R4 verdict Fixed (04-REVIEW-GAPS-R4.md at revision `58a3ba86a76cf85372f6499ac2e826890a61544a`). |
| G3WR-03 | warning | fixed | Reported by 04-REVIEW-GAPS-R3.md (77d5159). Gap-closure fix (04-48) at revision `fa55fc2ffdb933a5d3a47e6ca74eeaad9ab0256c`: tests/libretro/retroarch_smoke.py:205,798,974; regression tests test_g3wr_03_*. R4 verdict Fixed (04-REVIEW-GAPS-R4.md at revision `58a3ba86a76cf85372f6499ac2e826890a61544a`). |
| G3WR-04 | warning | fixed | Reported by 04-REVIEW-GAPS-R3.md (77d5159). Gap-closure fix (04-45) at revision `930be6b489dd71d48d7e2cbbbd4dc008b0f9267f`: tools/verify_playable.py:1038 `write_frontend_records`; regression tests test_g3wr_04_restore_unlink_failure_does_not_abort_rollback, test_g3wr_04_temporary_unlink_failure_does_not_mask_the_result. R4 verdict Fixed (04-REVIEW-GAPS-R4.md at revision `58a3ba86a76cf85372f6499ac2e826890a61544a`). |
| G3WR-05 | warning | fixed | Reported by 04-REVIEW-GAPS-R3.md (77d5159). Gap-closure fix (04-46) at revision `492ec02dd46bee14dba19b9c142d6bfc9de8f5ef`: tools/verify_playable.py:1294,1313 `_review_round_anchor` and `review_provenance_errors`; regression tests test_g3wr_05_*. R4 verdict Fixed (04-REVIEW-GAPS-R4.md at revision `58a3ba86a76cf85372f6499ac2e826890a61544a`). |
| G3IN-01 | info | fixed | Reported by 04-REVIEW-GAPS-R3.md (77d5159). Gap-closure fix (04-47) at revision `c44cb0bd7ff459fca457c8f93c1e4be853c84803`: tools/independent_review.py:101,112; regression tests test_g3in_01_leading_dollar_is_not_contained. R4 verdict Fixed (04-REVIEW-GAPS-R4.md at revision `58a3ba86a76cf85372f6499ac2e826890a61544a`). |
| G3IN-02 | info | fixed | Reported by 04-REVIEW-GAPS-R3.md (77d5159). Gap-closure fix (04-48) at revision `3093ff80037ddef9ba6c9d05dc334296ed9a09f5`: tests/libretro/retroarch_smoke.py:798,974; regression tests test_g3in_02_pid_record_detail_keeps_the_error_class, test_g3in_02_single_pid_record_diagnostic. R4 verdict Fixed (04-REVIEW-GAPS-R4.md at revision `58a3ba86a76cf85372f6499ac2e826890a61544a`). |
| G3IN-03 | info | fixed | Reported by 04-REVIEW-GAPS-R3.md (77d5159). Gap-closure fix (04-43) at revision `2587c6ea4704aba8312cff3b4a4c5f62c576224c`: tests/tools/check_security_register.py:148,189; regression tests test_g3in_03_misnamed_register_shaped_files_fail, test_g3in_03_non_register_documents_are_skipped_and_reported, test_g3in_03_verified_may_carry_a_trailing_comment. R4: partially fixed; residual G4IN-01 repaired at revision `856592e5ae89c9ec2a56c6651c59ffacc778e836`. |
| G4WR-01 | warning | fixed | Reported by 04-REVIEW-GAPS-R4.md (58a3ba8). Gap-closure fix (04-58) at revision `f783c73668b2cea08108d390b44025e9cfeb858c`: tools/verify_playable.py `_terminate_lane_group`, `_collect_after_kill`; regression tests test_g4wr_01_pipe_held_by_detached_descendant_keeps_earlier_output, test_g4wr_01_crlf_in_drained_segment_is_translated, test_g4wr_01_multibyte_split_across_segments, red commit c84609fda108. In-run diff review (04-58, 856592e5ae89): FIXED. |
| G4WR-02 | warning | fixed | Reported by 04-REVIEW-GAPS-R4.md (58a3ba8). Gap-closure fix (04-58) at revision `856592e5ae89c9ec2a56c6651c59ffacc778e836`: tests/tools/check_security_register.py `register_errors`, `INTEGER`; regression tests test_g4wr_02_threats_open_key_must_be_spelled_exactly, test_g4wr_02_threats_open_requires_ascii_digits, test_g4wr_02_status_key_must_be_spelled_exactly, test_g4wr_02_duplicates_still_case_insensitive, red commit 138a8676471f. In-run diff review (04-58, 856592e5ae89): FIXED. |
| G4WR-03 | warning | fixed | Reported by 04-REVIEW-GAPS-R4.md (58a3ba8). Gap-closure fix (04-58) at revision `f783c73668b2cea08108d390b44025e9cfeb858c`: tools/verify_playable.py `Runner.command`, `_decode_lane_output`; regression tests test_g4wr_03_non_utf8_lane_output_is_recorded, test_g4wr_03_non_utf8_output_on_the_timeout_path, test_g4wr_03_lane_popen_is_byte_mode, red commit c84609fda108. In-run diff review (04-58, 856592e5ae89): FIXED. |
| G4WR-04 | warning | fixed | Reported by 04-REVIEW-GAPS-R4.md (58a3ba8). Gap-closure fix (04-58) at revision `9a0d02b7c7de62ba07c2d07058f424ab92209306`: tools/verify_playable.py `rights_revision_errors`, `check_docs`; docs/rights-inventory.md; regression tests test_g4wr_04_*, red commit 409fe9f705f0. In-run diff review (04-58, 856592e5ae89): FIXED. |
| G4IN-01 | info | fixed | Reported by 04-REVIEW-GAPS-R4.md (58a3ba8). Gap-closure fix (04-58) at revision `856592e5ae89c9ec2a56c6651c59ffacc778e836`: tests/tools/check_security_register.py `main` candidate scan; regression tests test_g4in_01_stray_register_names_fail, test_g4in_01_non_register_security_named_file_is_skipped, red commit 138a8676471f. In-run diff review (04-58, 856592e5ae89): FIXED. |
| G4IN-02 | info | fixed | Reported by 04-REVIEW-GAPS-R4.md (58a3ba8). Gap-closure fix (04-58) at revision `f783c73668b2cea08108d390b44025e9cfeb858c`: tools/verify_playable.py `write_frontend_records`; regression tests test_g4in_02_restore_succeeded_but_restore_file_remains, test_g4in_02_surviving_tmp_is_named, red commit c84609fda108. In-run diff review (04-58, 856592e5ae89): FIXED. |
| G4IN-03 | info | fixed | Reported by 04-REVIEW-GAPS-R4.md (58a3ba8). Gap-closure fix (04-58) at revision `856592e5ae89c9ec2a56c6651c59ffacc778e836`: tests/libretro/retroarch_smoke.py `run_diagnostics`; regression tests test_g4in_03_pid_record_failure_skips_second_probe, red commit 138a8676471f. In-run diff review (04-58, 856592e5ae89): FIXED. |
| G5WR-01 | warning | fixed | Reported by 04-REVIEW-GAPS-R5.md (9f88c4c). Confirmed fixed by 04-REVIEW-GAPS-R6.md (d46e6e1); the residual trust gap is tracked as G6WR-01: per-row history allowlist (user decision 2026-10-11, scope tolerance; allowlist scope: pre-ship rows of the first-playable-game milestone branch, not reachable from git merge-base HEAD main) at revision `7ad8eef0d10a3f0c97a5bdec64f6c33c0ccedcbb`, revision `ad43068224e968d56e3158b8b2386b06c2e9cf38`, generator revision `c43b9bbe94f58d5ed177a3350c5028bda6b695c3`, revision `18d86dede92015374d41251245bc5e939d81a839`; squash-only test repairs at revision `2481154c0b8e3cd4d9c4c61090d9393b6b5cab13`, revision `019e25d58f1f0c36b2616486c3eb307ac9ad0a76`, revision `0031bb09410d742b035147f439bad53cbd870c88`; squash simulation: full suite passes in the squashed clone (04-63; frozen-file run in 04-64). |
| G5WR-02 | warning | fixed | Reported by 04-REVIEW-GAPS-R5.md (9f88c4c). Confirmed fixed by 04-REVIEW-GAPS-R6.md (d46e6e1): single lane.ready gate before the lane timeout at revision `a10c8c8ae2b7f362220c477742bc28084aea66eb`: tests/tools/test_verify_playable.py `wait_ready`; tests test_g5wr_02_*. |
| G5IN-01 | info | fixed | Reported by 04-REVIEW-GAPS-R5.md (9f88c4c). Confirmed fixed by 04-REVIEW-GAPS-R6.md (d46e6e1); the residual is tracked as G6WR-03: path form before the third_party/ exemption and items shape check at revision `a10c8c8ae2b7f362220c477742bc28084aea66eb`: `rights_revision_errors`; tests test_g5in_01_*. |
| G6WR-01 | warning | deferred | Reported by 04-REVIEW-GAPS-R6.md (d46e6e1). Fixed in part; see 04-REVIEW-FIX-R6.md. At revision `6a7f287ef7a81d1574efb190668d63a3ea84770c`, the loader checks `base_revision` and resolvable rows against git, and revision `e2845e66ab2b3d17a1d0bbe5068ad9704651d242` adds the CTest `qualification_history_allowlist`. Tests: test_g6wr_01_*. Deferred residual (accepted risk under the 2026-10-11 squash-tolerance decision, 2026-10-11): after the squash, rows whose revision does not resolve are still accepted on their self-attested pin. No signing scheme is added because its cost outweighs the fault value. Mitigations: CI verifies the allowlist against the pull request history on every PR that changes it, which rejects any post-squash edit, and the local CTest is opt-in via GLUEYNEO_PRE_SHIP_HISTORY_CHECK so a squashed main stays green (docs/testing.md). |
| G6WR-02 | warning | fixed | Reported by 04-REVIEW-GAPS-R6.md (d46e6e1). Confirmed fixed by 04-REVIEW-GAPS-R7.md (bb0f4eb). Fixed at revision `49dcb76e246a000c3d35b0959a045551073d6fdd`: `load_history_allowlist` rejects repeated (kind, key, revision) rows as malformed. Test: test_g6wr_02_duplicate_rows_are_malformed. |
| G6WR-03 | warning | fixed | Reported by 04-REVIEW-GAPS-R6.md (d46e6e1). Confirmed fixed for symlinks and unnormalized paths by 04-REVIEW-GAPS-R7.md (bb0f4eb); the residual (working-tree bytes) is tracked as G7WR-03. Fixed at revision `6ed52935aded48db2150e2f80aae5fa7574f742a`: path form rejects empty and `.` segments and backslashes, and `_confined_file_bytes` reads only a non-symlink regular file under the source root. Tests: test_g6wr_03_*. |
| G6IN-01 | info | deferred | Reported by 04-REVIEW-GAPS-R6.md (d46e6e1). Assessed at revision `932c1297d020d506f3bb45ed2db02bcf9de0976d`. Deferred to the backlog at Phase 04 close (agent disposition for Info under METHODOLOGY checkpoint pre-flight step 4). Typing cleanup only: the `# type: ignore` escapes do not change runtime behaviour, and no type checker gates this repository. |
| G6IN-02 | info | deferred | Reported by 04-REVIEW-GAPS-R6.md (d46e6e1). Assessed at revision `932c1297d020d506f3bb45ed2db02bcf9de0976d`. Deferred to the backlog at Phase 04 close (agent disposition for Info under METHODOLOGY checkpoint pre-flight step 4). Fail-closed: a quoted register value carrying a ` #` tail is mangled into an unrecognized value, which the checker rejects instead of accepting. No current register uses that form. |
| G6IN-03 | info | deferred | Reported by 04-REVIEW-GAPS-R6.md (d46e6e1). Assessed at revision `932c1297d020d506f3bb45ed2db02bcf9de0976d`. Deferred to the backlog at Phase 04 close (agent disposition for Info under METHODOLOGY checkpoint pre-flight step 4). Diagnostic completeness only: an unexpected read error ends output capture for a lane, but lane status still comes from the exit code and the timeout path. The FD_SETSIZE limit is unreachable with the fixed number of lane pipes. |
| G7CR-01 | critical | fixed | Reported by 04-REVIEW-GAPS-R7.md (bb0f4eb). Confirmed fixed by 04-REVIEW-GAPS-R8.md (1664be2). See 04-REVIEW-FIX-R7.md. At revision `b4c6f197e26d26b3704352838b993e0484652924`, `history_allowlist_document` refuses to list a rights row whose file at the checked head does not hold the recorded SHA-256 (the post-squash predicate), so `check`, the CTest and the CI step catch this class. At revision `91f51ac02c136a1188d0d99025a4050f0f75a80f` (after revision `1b7c72680093ce3e08001704e6dc3e81e6e314bb`), the tests/tools/test_verify_playable.py rights row records the HEAD bytes at revision `e71e283b9cb7abe868f4dcec35d4cfded9092242`. Test: test_g7cr_01_generator_refuses_rights_row_stale_at_head. |
| G7CR-02 | critical | fixed | Reported by 04-REVIEW-GAPS-R7.md (bb0f4eb). Confirmed fixed by 04-REVIEW-GAPS-R8.md (1664be2). At revision `6103b9ed1cc647b06bec1a36c5e76ea332f27414`, `--base` defaults to `origin/main` (HISTORY_DEFAULT_BASE) and refuses when it does not resolve; the opt-in CTest passes GLUEYNEO_HISTORY_BASE. At revision `1b7c72680093ce3e08001704e6dc3e81e6e314bb`, docs/history-allowlist.json is regenerated against origin/main (base_revision 4b2120d57f48, 133 rows; the 12 rows reachable from main are gone), a correction of the base, not a regeneration to green. Test: test_g7cr_02_default_base_is_the_upstream_main_ref. |
| G7WR-01 | warning | fixed | Reported by 04-REVIEW-GAPS-R7.md (bb0f4eb). Confirmed fixed by 04-REVIEW-GAPS-R8.md (1664be2). At revision `04dd69cc4bf4b5cc30a4f75f64d976e6b4ce5ff7`, docs/testing.md and the `history_allowlist_anchor_errors` docstring state that the in-tree anchoring is a consistency check that cannot change a gate outcome, and that forged or invented rows are caught only by the CI `--history-allowlist ci` step before merge. The code path is unchanged; at revision `e71e283b9cb7abe868f4dcec35d4cfded9092242`, test_t_04_38_unresolvable_reviewed_revision_fails no longer copies the live allowlist, whose anchor error had preempted the gate under test since G6WR-01. |
| G7WR-02 | warning | fixed | Reported by 04-REVIEW-GAPS-R7.md (bb0f4eb). Confirmed fixed by 04-REVIEW-GAPS-R8.md (1664be2). At revision `13c7a379e4189a97a9c65a3fbf6365fa25d48230`, the CI step runs `--history-allowlist ci --base <PR base>` on every pull request; the tool runs the full check whenever the allowlist differs from the base or any listed revision is an ancestor of the head (every pre-ship pull request). A history-independent staleness gate was not added: after the squash an unrefreshed edit to a listed rights file already fails the tolerated digest check, a refreshed row cites a main commit and is evaluated strictly, and an orphaned allowlist row is inert (reason corrected under G8IN-01; docs/testing.md). Tests: test_g7wr_02_*. |
| G7WR-03 | warning | fixed | Reported by 04-REVIEW-GAPS-R7.md (bb0f4eb). Confirmed fixed by 04-REVIEW-GAPS-R8.md (1664be2). At revision `727935882640b3d434e3e0123303064d7e18624a`, `_head_blob` reads the regular-file entry at the checked head with `git ls-tree` and `git cat-file`, replacing the working-tree read, so dirty, untracked, ignored or hard-linked content and committed symlinks cannot pass a tolerated row. Test: test_g7wr_03_tolerated_rights_row_ignores_working_tree_bytes. |
| G7IN-01 | info | fixed | Reported by 04-REVIEW-GAPS-R7.md (bb0f4eb). Confirmed fixed by 04-REVIEW-GAPS-R8.md (1664be2). At revision `9dcff1e591f4bc467908537662af2b62c674cdea`, `check_docs` reports a base_revision missing from the repository before the frontend gate (narrowed at revision `c5eb9e380335ff9fddc823d6f5b17f4f643be7e4` so other anchor errors keep their place), and docs/testing.md says `--check-docs` needs the history back to base_revision. Test: test_g7in_01_check_docs_reports_unanchored_allowlist_first. |
| G8IN-01 | info | fixed | Reported by 04-REVIEW-GAPS-R8.md (1664be2). Confirmed fixed by 04-REVIEW-GAPS-R9.md (cafd5a4). See 04-REVIEW-FIX-R8.md. At revision `065cdeeab6728a158b82e04928aa949cb51c983e`, docs/testing.md and the `history_allowlist_check_applies` docstring give the correct reasons no post-squash staleness check exists; 04-REVIEW-FIX-R7.md is a dated record and is superseded on this point. Code paths unchanged. |
| G9WR-01 | warning | fixed | Reported by 04-REVIEW-GAPS-R9.md (cafd5a4). Confirmed fixed by 04-REVIEW-GAPS-R10.md (a05daa7). See 04-REVIEW-FIX-R9.md. At revision `060ce42429c4e167a76309cc9a3e7405ba149920`, tests/tools/test_private_paths.py parenthesizes the runner path before `.replace("/", "\u2215")`, so the fully substituted input from before 41611fc is scanned again; rights row refreshed in 2b9971e. |
| G9IN-01 | info | fixed | Reported by 04-REVIEW-GAPS-R9.md (cafd5a4). Confirmed fixed by 04-REVIEW-GAPS-R10.md (a05daa7). At revision `060ce42429c4e167a76309cc9a3e7405ba149920`, tools/public_content.py refuses duplicate or overlapping history-disposition object IDs at import instead of overwriting one silently. |
| G9IN-02 | info | fixed | Reported by 04-REVIEW-GAPS-R9.md (cafd5a4). Confirmed fixed by 04-REVIEW-GAPS-R10.md (a05daa7). At revision `060ce42429c4e167a76309cc9a3e7405ba149920`, tests/workflow/test_public_content.py asserts that three lookalike Anthropic addresses stay private identities. |
| G10IN-01 | info | deferred | Reported by 04-REVIEW-GAPS-R10.md (a05daa7). Assessed at revision `f80ad8bbf104b9df6ada981b992c5f84a1f69f1e`. Deferred to the backlog under the METHODOLOGY review-round convergence rule: the round-10 focused review of the repair diff reported only Info findings, so the loop closes without another repair round in Phase 04. Consistency only: the glob literal equals `REVIEW_ROUNDS`, so behaviour is unchanged. |
| G10IN-02 | info | deferred | Reported by 04-REVIEW-GAPS-R10.md (a05daa7). Assessed at revision `f80ad8bbf104b9df6ada981b992c5f84a1f69f1e`. Deferred to the backlog under the METHODOLOGY review-round convergence rule: the round-10 focused review of the repair diff reported only Info findings, so the loop closes without another repair round in Phase 04. The guard runs on every import of tools/public_content.py, so every public-content test and gate executes it; only a negative-path test is missing. |
| G10IN-03 | info | deferred | Reported by 04-REVIEW-GAPS-R10.md (a05daa7). Assessed at revision `f80ad8bbf104b9df6ada981b992c5f84a1f69f1e`. Deferred to the backlog under the METHODOLOGY review-round convergence rule: the round-10 focused review of the repair diff reported only Info findings, so the loop closes without another repair round in Phase 04. Round reports are committed review evidence under the same frontmatter checks; the live crosswalk test already exercises the three-digit T-04-103 citations positively. |
| G11IN-01 | info | deferred | Reported by 04-REVIEW-GAPS-R11.md (88c92f4). Assessed at revision `e1274c28f8dab69ee1d0b8cb784ade1d092f3163`. Deferred to the backlog under the METHODOLOGY review-round convergence rule: the round-11 focused review reported only Info findings. Fail-closed robustness only: the loader admits only 12-40 hex revisions, and a misaligned answer count raises RuntimeError. |
| G11IN-02 | info | deferred | Reported by 04-REVIEW-GAPS-R11.md (88c92f4). Assessed at revision `e1274c28f8dab69ee1d0b8cb784ade1d092f3163`. Deferred to the backlog under the METHODOLOGY review-round convergence rule: the round-11 focused review reported only Info findings. The new raise is fail-closed, and both callers validate `base` as 40 hex before the helper runs. |
| G11IN-03 | info | deferred | Reported by 04-REVIEW-GAPS-R11.md (88c92f4). Assessed at revision `e1274c28f8dab69ee1d0b8cb784ade1d092f3163`. Deferred to the backlog under the METHODOLOGY review-round convergence rule: the round-11 focused review reported only Info findings. The differential test covers the inclusive, unresolvable, short-prefix and non-revision rows. Tag, tree and error-path cases are backlog test depth. |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
