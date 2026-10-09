---
phase: "04"
slug: "public-playable-tracer"
status: validated
nyquist_compliant: false
wave_0_complete: true
created: "2026-10-07"
completed: "2026-10-07"
updated: "2026-10-08"
---

# Phase 04 — Validation Strategy

> Execution record for feedback sampling and acceptance evidence.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | CTest with pinned Unity; Python qualification and provenance checks |
| **Config file** | `CMakePresets.json`; `sdk-debug` remains the developer regression preset |
| **Clean qualification** | `python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean --check-docs` |
| **Full clean CTest** | 34/34 passed on 2026-10-07; measured 6.37 seconds |
| **Environment** | macOS 26.6.2 arm64, AppleClang 21.0.0.21000101, SDK 26.5, CMake 4.4.3, Ninja 1.13.2, Python 3.14.4 |

The receipt and sanitized command logs are retained under ignored `build/playable-qualification/`. A fresh run produced the same 602-byte public fixture in static and shared configurations (SHA-256 `59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0`). The runner builds and installs both native variants, runs an out-of-tree C consumer against each install, runs the full CTest suite, and invokes the actual frontend and chip gates. Its overall result remains nonzero when HOST-02 is unknown.

## Sampling Rate and Measured Latency

- **After each task commit:** run the task's focused path and `git diff --check`; Task 1 clean install consumers each completed in under 0.2 seconds after build.
- **Full phase feedback:** fresh configure/build/install for static and shared targets, installed consumer runs, and full CTest completed successfully; full CTest took 6.37 seconds.
- **Candidate source checks:** Z80 source check 0.068 seconds; YM2610 source check 0.130 seconds; YM2610 installed static/shared C linkage check 1.938 seconds.
- **Actual frontend smoke:** 0.672 seconds before RetroArch exited with status `-6` and no screenshot. This result is unknown, not a pass.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01 T1, 04-03 T2 | 04-01 / 04-03 | 1 / 2 | TRAC-01 | T-04-01, T-04-05 | Original fixture regeneration, hash, rights and oracle ancestry | integration/provenance | `cmake --build <clean-build> --target glueyneo-public-fixture`; full CTest `public_guest_*` | Yes | pass; both clean fixture hashes match |
| 04-01 T1-T2 | 04-01 | 1 | TRAC-02 | T-04-02 | Validate input/output buffers and render guest-produced pixels | integration/boundary | full clean CTest; `public_guest_contract` | Yes | pass |
| 04-01 T3 | 04-01 | 1 | TRAC-03 | T-04-02 | Input changes guest state/pixels; no-input and wrong-direction controls hold | integration/negative control | full clean CTest; `public_guest_trace`, `public_guest_negative_left`, `public_guest_negative_none` | Yes | pass |
| 04-02 T1-T2 | 04-02 | 2 | HOST-02 | T-04-03, T-04-04 | Actual pinned RetroArch loads content, polls input, presents video and unloads | actual frontend smoke | `python3 tests/libretro/retroarch_smoke.py --retroarch /Applications/RetroArch.app --core <installed-prefix>/lib/libretro/glueyneo_libretro.dylib --content <build-directory>/public-playable.bin` | Yes | unknown; RetroArch 1.22.2 exited `-6` before screenshot |
| 04-01 T2 | 04-01 | 1 | API-05 | T-04-02 | Bounded machine time, capacities, progress/errors and audio metadata | contract/boundary | full clean CTest; `public_guest_*` and SDK contract lanes | Yes | pass |
| 04-04 T1-T3 | 04-04 | 3 | SND-01 | T-04-06, T-04-07 | Pinned Z80 source and exact synthetic cycle/bus/IRQ/reset/continuation/instance workload | candidate conformance | `python3 tests/chips/check_z80_source.py`; full clean CTest `z80_admission*` | Yes | pass for the documented synthetic workload only |
| 04-05 T1-T3 | 04-05 | 4 | SND-02 | T-04-08, T-04-09, T-04-10 | Pinned ymfm source/state/clock/isolation/callback behavior and real C linkage | candidate conformance/consumer | `python3 tests/chips/check_ym2610.py source`; full clean CTest `ym2610_admission`; `python3 tests/chips/check_ym2610.py link --both-linkages` | Yes | pass; candidate-only, report SHA-256 `a6faf3de0dc68dec67e80743413d4e53de6ade6620123db5ccb6d3fec2e02` |
| 04-06 T1-T2 | 04-06 | 5 | QUAL-03 | T-04-11, T-04-12, T-04-SC | Clean static/shared install and C consumers with exact identity; actual frontend outcome retained | clean package/consumer/frontend smoke | `python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean --check-docs` | Yes | native static/shared build, install and consumer pass; actual frontend load unknown |
| 04-07 T1-T2 | 04-07 | 6 | QUAL-03, TRAC-01 | T-04-13, T-04-14, T-04-15, T-04-SC | Complete committed snapshot inventory binds fixture, tests, dependencies and all source-consuming qualification lanes; mutation and checkout-injection controls fail closed | snapshot integration/privacy | `python3 -m unittest discover -s tests/tools -p 'test_verify_playable.py' -v` | Yes | 11 focused tests pass; final receipt binds native qualification lanes; frontend remains unknown |
| 04-08 T1 | 04-08 | 7 | HOST-02 | T-04-16, T-04-17, T-04-18, T-04-SC | Fresh app profiles and screenshots; bounded process/crash diagnostics; private paths redacted; unavailable GUI authority remains unknown | GUI-free smoke regression | `python3 -m unittest discover -s tests/libretro -p 'test_retroarch_smoke.py' -v` | Yes | 16 focused tests pass; actual pinned app exits `-6` before screenshot, so HOST-02 remains unknown |
| 04-08 T2 | 04-08 | 7 | HOST-02, QUAL-03, TRAC-01, TRAC-03 | T-04-16, T-04-17, T-04-18, T-04-SC | One committed snapshot feeds native builds, installed consumers, candidate gates and actual frontend; unknown frontend observations cannot pass | clean qualification integration | `python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean --check-docs` | Yes | static/shared builds, consumers, candidate gates and 34 CTests pass; receipt fails closed because actual frontend is unknown |
| 04-09 T1 | 04-09 | 8 | HOST-02 | T-04-19, T-04-SC | Installed coverage schema routes unresolved pinned-app evidence to human review and excludes it from automatic passes | coverage classifier | `node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" uat classify-coverage --summary .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-02-SUMMARY.md` | Yes | classifier passes with zero errors; HOST-02 remains human-needed and unknown |
| 04-10 T1 | 04-10 | 8 | QUAL-03, TRAC-01 | T-04-20, T-04-21, T-04-22 | Qualification path redaction, fixture digest enforcement, and pinned app quit identity have focused regression coverage; gates remain open for independent audit | focused regression | `python3 -m unittest discover -s tests/tools -p 'test_verify_playable.py' -v` | Yes | pass, 17 tests on source `a2ea677` (current tree includes 3 Plan 04-11 tests); historical Plan 04-10 result was 14 tests at `e7aa255` |
| 04-10 T2-T3 | 04-10 | 8 | HOST-02, QUAL-03 | T-04-20, T-04-21, T-04-22 | Frontend diagnostic redaction, fixture pinning, and fixed-shape quit handling are covered without launching the GUI; actual app behavior remains unknown | GUI-free focused regression | `python3 -m unittest discover -s tests/libretro -p 'test_retroarch_smoke.py' -v` | Yes | pass, 24 tests on source `a2ea677`; the actual pinned app was not launched |
| 04-11 T1 | 04-11 | 9 | QUAL-03, TRAC-01 | T-04-23, T-04-SC | Every receipt row is compared with the corresponding committed archive bytes, mode, digest, and symlink target | repository-backed receipt regression | `python3 -m unittest discover -s tests/tools -p 'test_verify_playable.py' -v` | Yes | pass, 17 tests on source `a2ea677`; no live checkout input is used |
| 04-12 T1 tools | 04-12 | 10 | QUAL-03, TRAC-01 | T-04-11, T-04-15, T-04-18, T-04-24 | Exact integer receipt fields and complete ambiguous path redaction, including persisted and printed receipts | repository/privacy regression | `python3 -m unittest discover -s tests/tools -p 'test_verify_playable.py' -v` | Yes | pass, 19 tests on source `33bef8c`; 2026-10-08 |
| 04-12 T1 frontend | 04-12 | 10 | HOST-02, QUAL-03 | T-04-11, T-04-15, T-04-18, T-04-24 | Complete path spans and supplied temporary-root descendants removed from diagnostics and crash reasons; no GUI launch | GUI-free privacy regression | `python3 -m unittest discover -s tests/libretro -p 'test_retroarch_smoke.py' -v` | Yes | pass, 25 tests on source `33bef8c`; 2026-10-08; actual frontend unknown |
| 04-12 T2 | 04-12 | 10 | HOST-02, QUAL-03 | T-04-11, T-04-15, T-04-18 | Parse current audit register and unresolved review rows; preserve frontend unknown | evidence-map check | `python3 tests/tools/check_phase04_validation_map.py` | Yes | historical pass recorded in 04-12-SUMMARY.md; current direct gate fails at the hardcoded current-review-ID assertion after review `df9e2c4`; see Nyquist WR-01 |
| 04-13 T1 tools | 04-13 | 11 | QUAL-03 | T-04-11, T-04-15, T-04-18, T-04-20 | Escaped JSON quotes and embedded apostrophes cannot expose qualification path suffixes through repeated sanitation, logs, receipts or printed output | privacy regression | `python3 -m unittest discover -s tests/tools -p 'test_verify_playable.py' -v` | Yes | pass, 20 tests on source `04-13`; repository privacy evidence only |
| 04-13 T1 frontend | 04-13 | 11 | HOST-02, QUAL-03 | T-04-11, T-04-15, T-04-18, T-04-20 | Escaped JSON quotes and embedded apostrophes cannot expose frontend or crash-diagnostic suffixes; actual app remains unobserved | GUI-free privacy regression | `python3 -m unittest discover -s tests/libretro -p 'test_retroarch_smoke.py' -v` | Yes | pass, 26 tests on source `04-13`; no GUI launch |
| 04-13 T2 | 04-13 | 11 | Review audit | T-04-26 | Current review findings and carried history reconcile across YAML, table, crosswalk, severity, disposition and counts | checker mutation controls | `python3 -m unittest discover -s tests/tools -p 'test_check_phase04_validation_map.py' -v` | Yes | pass, 5 tests; direct gate runs both current privacy suites |
| 04-14 T1 qualification | 04-14 | 12 | QUAL-03 | T-04-11, T-04-15, T-04-18, T-04-20 | Raw literal quotes cannot expose qualification path suffixes through repeated sanitation, logs, receipt JSON or printed results | privacy regression | `python3 -m unittest discover -s tests/tools -p 'test_verify_playable.py' -v` | Yes | pass, 20 tests on source `e4e63b0`; arbitrary text redacts through line end |
| 04-14 T1 frontend | 04-14 | 12 | HOST-02, QUAL-03 | T-04-11, T-04-15, T-04-18, T-04-20 | Raw literal quotes cannot expose frontend diagnostic or crash-reason suffixes; actual app remains unobserved | GUI-free privacy regression | `python3 -m unittest discover -s tests/libretro -p 'test_retroarch_smoke.py' -v` | Yes | pass, 26 tests on source `e4e63b0`; no GUI launch |
| 04-14 T2 | 04-14 | 12 | Review audit | T-04-26 | Info/IN findings reconcile across narrative, disposition and severity-bearing crosswalk; mismatches fail closed | checker mutation controls | `python3 -m unittest discover -s tests/tools -p 'test_check_phase04_validation_map.py' -v` | Yes | pass, 8 tests on source `10a0cbe`; direct gate passes with four high/open threats and frontend unknown |
| 04-15 T1 | 04-15 | 13 | HOST-02, QUAL-03 | T-04-30, T-04-31 | Fresh actual-app evidence only from a materially changed functioning launch context; otherwise retain explicit unknown and prerequisite | smoke-script contract | `python3 -m unittest discover -s tests/libretro -p 'test_retroarch_smoke.py' -v` | Yes | 26 tests pass; launch precondition unavailable, no RetroArch invocation, no screenshot, frontend claim unknown |
| 04-15 T2 | 04-15 | 13 | HOST-02, QUAL-03 | T-04-30, T-04-31 | Reconcile each requirement from the machine-readable direct-observation predicate | evidence reconciliation | Task 1 observation JSON predicate; focused smoke suite only | Yes | HOST-02 Pending; frontend QUAL-03 Pending; actual-app identities and observations unavailable; frontend claim unknown |
| 04-16 T1 qualification | 04-16 | 14 | QUAL-03 | T-04-11, T-04-15, T-04-18, T-04-20 | Remove the entire unstructured diagnostic suffix after a private-root match across retained and printed sinks | privacy regression | `python3 tests/tools/test_verify_playable.py -v` | Yes | pass, 23 tests; no new dependency |
| 04-16 T1 frontend | 04-16 | 14 | HOST-02 | T-04-11, T-04-15, T-04-18, T-04-20 | Remove the entire unstructured diagnostic suffix after a private-root match across frontend serialization sinks | privacy regression | `python3 tests/libretro/test_retroarch_smoke.py -v` | Yes | pass, 27 tests; no app launch |
| 04-16 T2 | 04-16 | 14 | Review audit | T-04-33 | Compare one normalized controlled crosswalk state with each recorded disposition; reject contradiction and placeholders | checker mutation controls | `python3 tests/tools/test_check_phase04_validation_map.py -v` | Yes | pass, 10 tests; direct documentation and crosswalk gates pass; four high/open threats and frontend unknown preserved |
| 04-17 T1 | 04-17 | 15 | QUAL-03 | T-04-34, T-04-SC | Reject mixed Pending/unknown and affirmative frontend-closure claims while retaining the truthful current status | docs gate and mutation controls | `python3 tests/tools/test_verify_playable.py -v`; `python3 tools/verify_playable.py --check-docs` | Yes | historical pass, 23 tests at Plan 04-17; current source is covered by Plan 04-19 rows |
| 04-17 T2 | 04-17 | 15 | Review audit | WR-06, WR-07 | Reconcile current finding provenance, open crosswalk rows, and adversarial false-closure controls | checker mutation controls | `python3 tests/tools/test_check_phase04_validation_map.py -v`; `python3 tests/tools/check_phase04_validation_map.py` | Yes | original Plan run passed 12/12; current post-review run has 6/12 failures, including synthetic WR-07 collision and medium T-04-34/open-count mismatch; direct gate fails at the security open-count assertion |
| Nyquist WR-01 | 04-12 / 04-16 | 10 / 14 | Review audit | WR-01 / T-04-33 | Accept reconciled current review IDs and dispositions; reject contradictory and placeholder states | checker regression | `python3 tests/tools/test_check_phase04_validation_map.py -v` | Yes | resolved by 04-16: current suite passes 10/10, including the repaired-finding-absent mutation case and exact-state contradiction controls; the earlier line-110 failure remains historical |
| 04-18 T1 | 04-18 | 16 | Review audit, HOST-02, QUAL-03 | T-04-35, T-04-SC | Reconcile the four high/open disclosure IDs and medium/open T-04-34 with the severity-aware count; require current-report frontend uncertainty and preserve pending/unknown requirements | direct evidence-map checker | `python3 tests/tools/check_phase04_validation_map.py` | Yes | pass; current security/review/report crosswalk reconciles; four high/open threats and T-04-34 medium/open remain; actual pinned frontend remains unobserved |
| 04-18 T2 | 04-18 | 16 | Review audit, HOST-02, QUAL-03 | T-04-35, T-04-SC | Source-faithful mutations reject colliding IDs, malformed/duplicate requirement rows, inconsistent review/disposition/crosswalk counts, changed report status, and positive claims in every current frontend evidence row | checker mutation controls | `python3 tests/tools/test_check_phase04_validation_map.py -v` | Yes | pass, 14 tests; source-derived exact report rows reject appended/paraphrased frontend success claims; HOST-02 and frontend QUAL-03 remain Pending/unknown |
| 04-18 T3 | 04-18 | 16 | HOST-02, QUAL-03 | T-04-36, T-04-SC | Constrained 04-15 T2 Pending/unknown cell rejects tested affirmative load, display, input, or unload claims; docs gate does not establish actual RetroArch behavior | qualification regression and docs gate | `python3 tests/tools/test_verify_playable.py -v`; `python3 tools/verify_playable.py --check-docs`; `python3 tests/tools/test_check_phase04_validation_map.py -v` | Yes | historical pass, 23 qualification tests and 14 evidence-map tests at Plan 04-18; current source is covered by Plan 04-19 rows |
| 04-19 T1 qualification | 04-19 | 17 | QUAL-03 | T-04-11, T-04-15, T-04-18, T-04-20, T-04-37 | Independent review triages retained/printed diagnostics, forged receipt rows, and consumer documentation; four directed threats remain open | privacy and docs-claim regression | `python3 tests/tools/test_verify_playable.py -v` | Yes | pass, 25 tests at `2a82c455`; code review still reproduced alternate affirmative guide claims, so WR-06/T-04-34 remain open |
| 04-19 T1 frontend | 04-19 | 17 | HOST-02 | T-04-11, T-04-15, T-04-18, T-04-20, T-04-37 | GUI-free frontend diagnostics redact private paths; no app claim is inferred from these tests | frontend diagnostic regression | `python3 tests/libretro/test_retroarch_smoke.py -v` | Yes | pass, 27 tests at `9804351`; no GUI launch; HOST-02 remains manual-only/unknown |
| 04-19 T2 | 04-19 | 17 | QUAL-03 | T-04-34, T-04-SC (04-19) | Reject tested affirmative guide claims and preserve explicit negative statements; remaining alternate claims are recorded open under the bounded stop condition | qualification regression and docs gate | `python3 tests/tools/test_verify_playable.py -v`; `python3 tools/verify_playable.py --check-docs` | Yes | pass, 25 tests and docs gate at `2a82c455`; alternate-claim limitation remains open; no actual frontend observation |
| 04-19 T3 | 04-19 | 17 | HOST-02, QUAL-03 | T-04-34, T-04-37, T-04-SC (04-19) | Reconcile one current open WR-06 disposition with medium/open T-04-34, preserve four high/open blockers and Pending/unknown frontend status | evidence-map mutation and direct checker | `python3 tests/tools/test_check_phase04_validation_map.py -v`; `python3 tests/tools/check_phase04_validation_map.py`; `python3 tools/verify_playable.py --check-docs` | Yes | pass, 14 mutation tests; direct checker and docs gate pass, checker reruns 25 qualification and 27 frontend tests; WR-06/T-04-34 remain open |
| 04-20 T1 | 04-20 | 18 | HOST-02, QUAL-03 | T-04-38, T-04-39, T-04-40 | Current WR-01/WR-02 provenance is specific; copied current-report mutations preserve frontend unknown and reject stale qualification denominator | evidence-map mutation and direct gate | `python3 tests/tools/test_check_phase04_validation_map.py -v`; `python3 tests/tools/check_phase04_validation_map.py` | Yes | pass, 15 mutation tests including stale 23/23 rejection; direct checker observes current 25-test qualification count; no app behavior inferred |
| 04-20 T2 | 04-20 | 18 | HOST-02, QUAL-03 | T-04-11, T-04-15, T-04-18, T-04-20, T-04-34, T-04-38 | Independent review includes frontend sanitizer source and test at exact current revision; GUI-free evidence remains distinct from app behavior | frontend diagnostic and sanitizer counterexample review | `python3 tests/libretro/test_retroarch_smoke.py -v`; focused newline/quote/apostrophe/space/private-root suffix cases | Yes | 27/27 tests; five focused cases show no tested suffix leak; WR-01/T-04-34 and four high threats remain open; frontend unknown |
| 04-20 T3 | 04-20 | 18 | HOST-02, QUAL-03 | T-04-34, T-04-38, T-04-39 | Reconcile current review finding states with evidence and exact crosswalk; retain four high/open threats and frontend Pending/unknown | mutation suite, direct checker, docs gate | `python3 tests/tools/test_check_phase04_validation_map.py -v`; `python3 tests/tools/check_phase04_validation_map.py`; `python3 tools/verify_playable.py --check-docs` | Yes | 15/15 mutation tests, direct checker and docs gate pass; WR-02 fixed by independent review; WR-01/T-04-34 remain open; no app claim |
| Post-execution review | 04-20 | 18 | HOST-02, QUAL-03 | T-04-34 | Evidence-map uncertainty filter must reject affirmative output claims while actual frontend status is unknown | review mutation gap | `tests/tools/check_phase04_validation_map.py:214-220` counterexample in 04-REVIEW.md WR-08 | Yes | open: “a frame was rendered to the window” passes beside unknown status; no app observation is inferred |
| Post-audit checker reconciliation | 04-20 | 18 | QUAL-03 | T-04-38 | Reconcile all audited medium/open threat rows without relaxing the security register | evidence-map regression | `python3 tests/tools/test_check_phase04_validation_map.py -v`; `python3 tests/tools/check_phase04_validation_map.py` | Yes | blocked: 5/15 mutation tests fail and direct checker rejects the additional T-04-38 medium/open row; retain finding for follow-up plan |
| 04-21 T1 | 04-21 | 19 | HOST-02, QUAL-03 | T-04-41, T-04-43, T-04-SC | Source-derived evidence-map mutations enforce exact security rows and WR-01 review provenance; preserve all open threats and frontend unknown | checker mutation controls | `python3 tests/tools/test_check_phase04_validation_map.py -v` | Yes | pass, 22/22; direct evidence-map gate also passes and reconciles current focused suite counts |
| 04-21 T2 | 04-21 | 19 | HOST-02, QUAL-03 | T-04-42, T-04-SC | Copied report/guide mutations reject tested affirmative output, control and guest-pixel claims; GUI-free contract and qualification behavior remain distinct from actual app evidence | qualification/privacy and GUI-free contract regressions; docs gate | `python3 tests/tools/test_verify_playable.py -v`; `python3 tests/libretro/test_retroarch_smoke.py -v`; `python3 tools/verify_playable.py --check-docs` | Yes | pass, qualification 27/27 and frontend contract 27/27; docs gate passes; no actual RetroArch behavior inferred |
| 04-21 T3 | 04-21 | 19 | HOST-02, QUAL-03 | T-04-41, T-04-42, T-04-43, T-04-SC | Frozen independent review and current direct gates reconcile exact review provenance, dispositions, current denominators and remaining manual-only limits | independent review evidence and integration gates | `python3 tests/tools/check_phase04_validation_map.py`; `python3 tools/verify_playable.py --check-docs`; `ctest --preset owned-debug --output-on-failure` | Yes | independent review of `f1c8a1de5f25224b83da6ec9e4bc40bf51a249ae` found no new actionable issue; direct checker and docs gate pass; CTest 47/47; HOST-02/frontend QUAL-03 remain Pending/unknown |

## Threat Coverage

| Threat | Evidence and disposition |
|--------|--------------------------|
| T-04-11 information disclosure | Plan 04-13 adds escaped-quote, apostrophe, second-pass, retained-log, receipt and printed-output regressions. Synthetic roots and suffixes are absent from captured sinks. Finding remains open pending independent audit. |
| T-04-12 repudiation | Receipt records source revision and selected source hashes, compiler/CMake/SDK/OS/architecture, fixture/core/frontend hashes, candidate revisions, command status and log hashes. |
| T-04-SC dependency closure | Z80 and ymfm immutable source checks passed; YM2610 report records the pinned source and license evidence. Candidate outcomes remain separate from runtime integration. |
| T-04-20 → T-04-11/T-04-15/T-04-18 | Plan 04-13 recognizes a closing quote only inside a valid escaped JSON string; otherwise it removes the ambiguous line remainder. The four high disclosure findings remain open pending independent audit. |
| T-04-21 → T-04-16 | Plan 04-10 checks the pinned public fixture digest before frontend launch; T-04-16 is closed by the current independent audit. Actual app behavior remains unknown. |
| T-04-22 → T-04-17 | Plan 04-10 validates the pinned bundle identifier before quit commands; T-04-17 is closed by the current independent audit. |
| T-04-23 → T-04-13 | Plan 04-11 derives archive rows from committed member bytes and rejects forged receipt rows; T-04-13 is closed by the current independent audit, while carried WR-03 remains open pending independent review. |
| T-04-24 receipt numeric types | Plan 04-12 rejects booleans in bytes, entry_count, file_count and symlink_count before aggregate/archive comparison. Fresh repository-backed regressions pass; independent post-fix audit is still required. |
| T-04-34 | Plan 04-18 constrains the current Pending/unknown status cell; Plan 04-19 adds regression-tested guide claim checks. WR-06 and post-execution WR-08 show unlisted affirmative wording remains possible, so this medium threat remains open. |
| T-04-37 | Plan 04-19 records revision-scoped independent review, exact counterexamples, dispositions, commands, denominators, and limitations; unresolved WR-06 remains open. |
| T-04-43 | Phase-wide review WR-09 reproduced acceptance of a nonexistent extra path in the claimed review scope; retain medium/open pending exact-scope enforcement. |

## Review Finding Crosswalk

| Review Finding | Severity | Existing Threat Scope | Disposition |
|----------------|----------|-----------------------|-------------|
| WR-06 | warning | Alternate affirmative frontend success paraphrases pass beside Pending/unknown in the consumer guide | open |
| WR-07 | warning | Evidence-map fixture source-faithful verification-row mutation contract | fixed |
| CR-03 | critical | T-04-11 / T-04-15 / T-04-18 / T-04-20, newline-containing path disclosure | fixed |
| WR-05 | warning | Review disposition and validation crosswalk consistency | fixed |
| WR-01 | warning | `check_docs()` accepts the two affirmative frontend paraphrases reproduced at 2026-10-08T23:12:03Z; actual frontend remains unknown | open |
| WR-08 | warning | Evidence-map uncertainty matcher accepts ordinary output success wording while frontend status remains unknown; review counterexample at `tests/tools/check_phase04_validation_map.py:214-220` | open |
| CR-02 | critical | T-04-11 / T-04-15 / T-04-18 / T-04-20, raw-literal-quote disclosure | fixed |
| WR-04 | warning | Validation-map review grammar for informational findings | fixed |
| CR-01 | critical | T-04-24, exact numeric receipt types | fixed |
| WR-03 | warning | T-04-13 / T-04-23, repository receipt validation rejects forged file-content hashes | fixed |
| WR-02 | warning | Independent review `870848e553aca6e43f6fec8ae0acefac87270f5b` confirms live 25/25 comparison and stale 23/23 mutation rejection | fixed |
| WR-09 | warning | T-04-43: the review provenance gate accepts a nonexistent extra path in the claimed scope; reproduced by the current standard-depth review at revision `48befe7a92d7c545e7c900c57e027b9e15952a7f` | open |
| WR-10 | warning | T-04-SC: evidence-map mutation tests now reach and assert their intended checks on the current report baseline | fixed |
| WR-11 | warning | T-04-43: duplicate reviewed_revision keys now fail closed, including malformed duplicate values | fixed |

### Plan 04-20 Task 1 Current Evidence — 2026-10-08

The copied mutation baseline retains the actual current `04-VERIFICATION.md`, `04-REVIEW.md`, disposition, and validation documents. No expected sentence or synthetic historical review is appended. The direct evidence checker reads the current report's Goal Achievement, Required Artifacts, Key Link Verification, Data-Flow Trace, Requirements Coverage, and Behavioral Spot-Checks sections. Its qualification denominator is read from the single current `Qualification/privacy tests` result and compared with a fresh `python3 tests/tools/test_verify_playable.py -v` run. The mutation suite passes 15/15, including a stale 23/23 mutation against the live 25-test count. The independent current-revision review confirmed this repair, so WR-02 is fixed. WR-01 and WR-06/T-04-34 remain open; no actual-app claim is made.

### Plan 04-20 Task 2 Independent Review — 2026-10-08

The independent reviewer inspected `tests/libretro/retroarch_smoke.py`, `tests/libretro/test_retroarch_smoke.py`, and both validation-map files at revision `870848e553aca6e43f6fec8ae0acefac87270f5b`. The frontend contract suite passed 27/27. Five focused sanitizer cases covered newline, escaped quote, apostrophe, spaces, and a temporary-root suffix crossing a newline; no tested suffix leaked through sanitized text or serialized diagnostics. The reviewer also confirmed the live qualification suite passed 25/25, the 15/15 mutation suite rejected stale 23/23, and the direct checker passed. WR-02 is fixed with this independent evidence. WR-01 and T-04-34 remain open, all four directed high/open threats remain, and HOST-02/frontend QUAL-03 remain Pending/unknown. No GUI was launched and no actual-app claim is made.

### Post-Execution Code Review — 2026-10-08

The standard-depth review of `tests/tools/check_phase04_validation_map.py` and its mutation tests found WR-08: `has_frontend_load_uncertainty()` can accept “a frame was rendered to the window” alongside an explicit unknown frontend status. Keep WR-08 open under T-04-34 pending a targeted mutation and gate correction. This review covers only the two listed files; the earlier Plan 04-20 sanitizer review remains recorded above and in `04-20-SUMMARY.md`. No actual frontend behavior was observed.

### Post-Audit Security Reconciliation — 2026-10-08

The fresh ASVS L1 audit added T-04-38 as a medium/open finding because the evidence-map checker does not enforce the sanitizer source path or reviewed revision. The current checker requires exactly T-04-34 as its medium/open set. With the truthful 59-row register, the mutation suite fails 5/15 and the direct checker exits at `required medium/open T-04-34 differs from the active security register`. No assertion or threat status was relaxed. This is a new bounded checker/security reconciliation gap; keep the four high blockers and both medium findings open for the next plan.

## Plan 04-19 Current-Revision Reconciliation — 2026-10-08

The current qualification suite passed 25/25, frontend smoke-contract suite 27/27, and evidence-map mutation suite 14/14. `python3 tests/tools/check_phase04_validation_map.py`, `python3 tools/verify_playable.py --check-docs`, and the direct evidence-map checker passed; the direct checker reran the focused qualification and frontend suites with their current denominators. The first independent security/code-review pass at `9804351907e456b3ab85ebe4a49959c05b0714bb` resolved six carried review findings and reproduced WR-06 in the consumer guide. Three bounded correction commits added focused guide-claim controls. The post-fix code review at `2a82c455f85671ba144a42923318c4ff7d53b9a2` still reproduced two affirmative app/control claims accepted by the docs gate, so WR-06 remains open and T-04-34 stays medium/open. This is the bounded stop condition, not a pass. T-04-11, T-04-15, T-04-18, and T-04-20 remain high/open by direction. HOST-02 and frontend QUAL-03 remain Pending/unknown and manual-only; no GUI was launched. `nyquist_compliant` remains false.

| Metric | Count |
|---|---:|
| Carried review findings dispositioned | 7 |
| Fixed with current evidence | 6 |
| Retained open | 1 (WR-06 / T-04-34) |
| Directed high blockers | 4 |

## Revision Context

### Fresh Post-04-14 Audit and Review

The security audit assessed 46 threats: 42 closed and four high-severity disclosure threats remain open by user direction. The independent code review confirms CR-02 and WR-04 are fixed and identifies CR-03 and WR-05 as current open findings. The disposition ledger and crosswalk above reflect the new review; older Plan 04-13/04-14 notes below describe their execution-time state. HOST-02 and frontend QUAL-03 remain Pending because the required functioning pinned RetroArch context was unavailable; no launch was attempted.

### Plan 04-15 Frontend Evidence Boundary

The required precondition remains unavailable: the prior pinned RetroArch context aborted with exit `-6` before a screenshot, LaunchServices reported `kLSNoExecutableErr`, unified-log inspection was blocked, and current computer-use inventory showed neither a RetroArch window nor a running process. No materially changed functioning launch context is evidenced. RetroArch was not invoked or retried. The focused smoke-script contract suite passed 26 tests; these tests do not establish actual app behavior. HOST-02 and frontend QUAL-03 therefore remain Pending. Task 1 records app, core and fixture identities as unavailable and sets the frontend claim to `unknown`. T-04-11, T-04-15, T-04-18 and T-04-20 remain high/open.

- Plan 04-07's immutable source snapshot implementation is recorded in [04-07-SUMMARY.md](04-07-SUMMARY.md), including commit `36df674`. [04-VERIFICATION.md](04-VERIFICATION.md) preserves that source identity evidence. Plan 04-12 fixes the later boolean-count bypass. Plan 04-13 retains CR-01 as fixed history while reconciling the fresh review and crosswalk.
- Plan 04-10's historical focused runs were 14 tools tests and 24 frontend smoke tests, recorded in [04-10-SUMMARY.md](04-10-SUMMARY.md) at commit `e7aa255`. After the Plan 04-11 implementation commit `a2ea677`, the tools suite was rerun with 17 tests and the frontend smoke suite with 24 tests. The three added tools regressions account for the tools denominator change.
- Plan 04-12 reran the focused suites on implementation `33bef8c`: 19 tools tests and 25 frontend smoke tests passed. Earlier denominators above remain dated history. New controls cover booleans equal to integer values, punctuation/phrase path components, quoted controls and supplied temporary-root descendants. Conservative unquoted redaction intentionally removes ambiguous trailing status; status preceding a private span and bounded structured diagnostics survive.
- Plan 04-13 observes 20 qualification tests, 26 frontend-smoke tests, and 5 validation-map mutation tests. The privacy tests cover escaped JSON quotes, apostrophes, repeat sanitation, retained and printed receipts, structured stage/status, crash reason, and a supplied temporary-root descendant. The direct gate reruns both real privacy suites and reconciles retained review history with the current narrative.
- Plan 04-14 adds a synthetic `IN-` finding under `Info`, checks its `info` severity across review, disposition and crosswalk, and rejects a severity mismatch. WR-04 remains open pending independent review; this repository regression does not revise the review report or close security findings.
- Plan 04-14's final verification ran on source commit `8af6725`: qualification 20/20, frontend 26/26, review-map mutation suite 8/8, and `ctest --preset owned-debug --output-on-failure` 47/47. The direct evidence-map command passed. These are repository checks only and do not close the high disclosure threats or establish actual frontend behavior.
- At the time of Plan 04-14, these focused suites verified repository behavior only; the later fresh review confirms CR-02 and WR-04 are fixed and identifies CR-03/WR-05. Security remains blocked with T-04-11/T-04-15/T-04-18/T-04-20 high/open. HOST-02 and actual frontend QUAL-03 remain Pending until the requested pinned-app observations exist.

## Actual Frontend Evidence Handoff — Manual-Only / Unverified

Human evidence is still required: run the generated public fixture in the pinned RetroArch 1.22.2 build and observe a fresh screenshot, repeated no-input frames, RIGHT movement, the LEFT negative control, content unload, and normal application exit. Expected behavior is guest-produced software pixels, stable no-input output, a RIGHT-driven marker change that LEFT does not reproduce, and successful unload and exit. The app previously aborted before its first screenshot; no GUI retry was made because the environment has not materially changed.

## Wave 0 and Sign-Off

- [x] Original fixture source, generator, rights record and oracle contract are present and checked by digest.
- [x] Native frame, input, rendering and negative-control tests run in the clean CTest suite.
- [x] Libretro callback contract and actual RetroArch smoke are separate checks; only the actual smoke can satisfy HOST-02.
- [x] Z80 synthetic admission and YM2610 candidate gates remain distinct, with static/shared C consumers for ymfm.
- [x] Clean install/load procedure includes exact tested compiler, SDK, OS, architecture, frontend and artifact identities.
- [x] Every task maps to an executable command; full clean CTest provides a 34-test denominator.
- [x] No watch-mode acceptance commands are used.

Every plan task has an automated command or an explicit human-evidence route. Nyquist validation remains partial because HOST-02 and the frontend portion of QUAL-03 require direct observation in a functioning pinned frontend; WR-01 was resolved by the Plan 04-16 reconciliation. Phase 04 is not accepted while actual frontend behavior remains unknown and the four high-severity disclosure threats remain open. Native fixture, Z80 synthetic-workload, and YM2610 candidate results do not establish BIOS/game compatibility.

---
*Phase: 04-public-playable-tracer*
*Updated: 2026-10-08*

## Validation Audit 2026-10-07

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

## Validation Audit 2026-10-08

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

## Adversarial Nyquist Probe 2026-10-08 — WR-01

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 0 |
| Escalated | 1 |

`python3 -m unittest discover -s tests/tools -p 'test_check_phase04_validation_map.py' -v` constructs a temporary, internally reconciled review state where the repaired CR-01 finding is absent from both the fresh review and disposition, and the validation crosswalk and disposition totals reflect the change. The checker rejects it at `tests/tools/check_phase04_validation_map.py:110` with `current review IDs changed`. This is an implementation defect in the checker and remains escalated; no implementation assertions were changed during this audit. The direct gate also currently exits 1 at that same assertion against the fresh review.

## Historical Post-Audit Execution Checks (before Plan 04-12; superseded)

- At the pre-04-12 source state, `python3 tests/tools/check_phase04_validation_map.py` failed because it expected six open security findings. After Plan 04-12, the historical direct-gate failure was the hardcoded current review-ID assertion documented under Nyquist WR-01. No assertions or goldens were relaxed to make either historical run pass.
- Read-only reproductions at their recorded revisions confirmed a forged boolean-byte receipt and disclosure through then-current quoted/unquoted path sanitizers. Plan 04-12 repaired the boolean case; Plan 04-13 adds escaped-quote and apostrophe regression coverage for the sanitizer boundary.
- The earlier post-wave CTest result was 46/47, with only `owned_cpu_inventory_check` failing because of stale CPU identity/source-manifest and strict compile-command expectations. Plan 04-12 later refreshed that evidence and its summary records 47/47. The pinned RetroArch GUI result remains unknown; no new GUI observation was made.

## Validation Audit 2026-10-08

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 0 |
| Escalated | 1 |

## Plan 04-13 Reconciliation Run — 2026-10-08

The checker mutation suite accepts a repaired CR-01 absent from the fresh review, current CR-02/WR-01 and carried WR-02/WR-03, and a new finding when every record agrees. It rejects severity, disposition, duplicate or missing IDs, count, crosswalk, security-register, and frontend-status contradictions. The direct gate reruns the real 20-test and 26-test privacy suites. These repository checks do not disposition the current review findings or close security threats.

## Validation Audit 2026-10-08

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

## Nyquist Audit After Plan 04-19 — 2026-10-08

Plan 04-19's three task rows are present in the per-task verification map. I reran the focused automated checks against current revision `b5ea85c40ac4cd54946533aa5a6bbc1cb60c511c`: qualification/doc-claim regressions `python3 tests/tools/test_verify_playable.py -v` passed 25/25; GUI-free frontend diagnostic regressions `python3 tests/libretro/test_retroarch_smoke.py -v` passed 27/27; evidence-map mutation controls `python3 tests/tools/test_check_phase04_validation_map.py -v` passed 14/14; the direct evidence-map checker `python3 tests/tools/check_phase04_validation_map.py` and docs gate `python3 tools/verify_playable.py --check-docs` both passed. The direct checker also reran and reconciled the 25 qualification and 27 frontend tests. Coverage classification of `04-19-SUMMARY.md` returned all three entries as `human_judgment` with zero errors and no auto-passed entries. These results verify repository contracts and record reconciliation; they do not establish that the unresolved affirmative guide paraphrases are comprehensively rejected.

Manual-only/unverified: HOST-02 and frontend QUAL-03 still require direct pinned RetroArch 1.22.2 observations of content load, guest video, stable no-input frames, RIGHT/LEFT controls, unload, and normal exit. No GUI was launched. Keep `nyquist_compliant: false`; WR-06/T-04-34 remains medium/open, and T-04-11, T-04-15, T-04-18, and T-04-20 remain high/open by direction. Phase 04 remains blocked.

## Plan 04-18 Frontend Evidence Gate Hardening — 2026-10-08

Independent review found that free-form semantic matching admitted affirmative paraphrases and that positive claims could be added to current frontend evidence cells outside the goal/requirements tables. The direct checker now compares every current frontend-related verification row against its exact source-derived text and status, including goals 3/5, relevant artifacts, links, data-flow rows, frontend-related behavioral spot-checks, and HOST-02/QUAL-03. The 14-test mutation suite rejects changes across those rows, malformed or duplicate requirement records, and appended success claims. The verification report itself remains unchanged by this correction. The independent review is clean; the direct checker, 14/14 mutation tests, 23/23 qualification tests, and docs-only gate pass. HOST-02 and frontend QUAL-03 remain Pending/unknown; four high/open threats and T-04-34 medium/open remain unresolved, so `nyquist_compliant` remains false.

## Post-04-15 Review Reconciliation — 2026-10-08

The direct gate `python3 tests/tools/check_phase04_validation_map.py` passed after recording the fresh threat and review dispositions; it also ran the qualification and frontend privacy suites. The then-current focused mutation suite recorded eight tests with four fixture failures, and WR-05 remained unresolved at that point. No assertions were relaxed.

## Plan 04-16 Reconciliation — 2026-10-08

The newline-path regression now removes the complete unstructured suffix in qualification and frontend diagnostics. The controlled review crosswalk contains one exact state per finding, and the docs gate accepts the explicit HOST-02/frontend QUAL-03 Pending/unknown boundary while rejecting placeholders and false closure. The focused suites report 23 qualification tests, 27 frontend contract tests, and 10 evidence-map mutation tests; the direct documentation and crosswalk gates pass. No RetroArch app was launched. T-04-11, T-04-15, T-04-18 and T-04-20 remain high/open pending independent security review, and actual frontend evidence remains unavailable.

## Adversarial Nyquist Audit — 2026-10-08

Current repository evidence was rerun: `python3 tests/tools/test_verify_playable.py -v` (23/23), `python3 tests/libretro/test_retroarch_smoke.py -v` (27/27), `python3 tests/tools/test_check_phase04_validation_map.py -v` (10/10), `python3 tools/verify_playable.py --check-docs`, and `python3 tests/tools/check_phase04_validation_map.py` all pass. The focused tests exercise newline-path redaction at retained/printed sinks, frontend diagnostic and crash serialization, exact normalized review states, contradictory-state rejection, and the reconciled-review mutation that previously triggered WR-01. No additional repository-test gap was found, so no test file was added. The direct evidence-map gate also reruns the qualification and frontend suites and preserves four high/open disclosure threats plus frontend unknown status.

Manual-only/unverified: HOST-02 and the frontend portion of QUAL-03 still require an actual pinned RetroArch observation of content load, guest video, no-input stability, RIGHT/LEFT controls, unload and normal exit. No GUI was launched in this audit. The separate security review findings T-04-11, T-04-15, T-04-18 and T-04-20 also remain open by explicit project direction. These items do not convert the passing repository tests into phase acceptance; `nyquist_compliant` remains false.

## Validation Audit 2026-10-08

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 0 |
| Escalated | 1 |

## Nyquist Audit After Plan 04-17 — 2026-10-08

The auditor reran the relevant repository evidence: `python3 tests/libretro/test_retroarch_smoke.py -v` (27/27), `python3 tests/tools/test_verify_playable.py -v` (23/23), `python3 tests/tools/test_check_phase04_validation_map.py -v` (12/12), `ctest --test-dir build/owned-debug --output-on-failure -R '^libretro_callback$'` (1/1), `python3 tools/verify_playable.py --check-docs`, and the direct Phase 04 evidence-map checker; all passed. These checks cover the C callback contract and smoke-runner behavior but cannot prove that the actual RetroArch app loaded and presented the fixture or accepted input.

Manual-only/unverified: HOST-02 and the frontend portion of QUAL-03 still require direct pinned RetroArch 1.22.2 observations of content load, guest video, stable no-input frames, RIGHT/LEFT controls, unload, and normal exit. No app launch was attempted. No additional automated test can establish those GUI observations without a functioning frontend oracle; adding a mock would only test the mock. Preserve both requirements as Pending/unknown and keep `nyquist_compliant: false`. The four high/open disclosure threats are unchanged.

## Post-Plan 04-17 Code Review Reconciliation — 2026-10-08

The current standard-depth review reports two open warnings: WR-06 remains because `check_docs()` accepts “frontend app loaded successfully” alongside Pending/unknown, and WR-07 because the evidence-map fixture appends the required verification sentence instead of testing whether the source report retains it. The disposition ledger and crosswalk now record both findings with current-review provenance. The incomplete WR-06 mitigation reopens plan-authored T-04-34 at medium severity; the four reserved high-severity findings remain open, so `threats_open: 4` and Phase 04 stays blocked.

The latest `python3 tests/tools/test_check_phase04_validation_map.py -v` run reports 12 tests with 6 failures. Failures include a synthetic WR-07 ID collision, fixture expectations that omit the current findings, and the current direct gate stopping at “security frontmatter open count differs from register.” The gate assumes every open register row contributes to `threats_open`, while the active security contract counts blocking severities and leaves medium T-04-34 open but nonblocking. No test assertions, goldens, or threat statuses were relaxed. HOST-02 and frontend QUAL-03 remain Pending/unknown; no RetroArch launch occurred.

## Validation Audit 2026-10-08

| Metric | Count |
|---|---|
| Gaps found | 3 |
| Resolved | 3 |
| Escalated | 0 |

## Nyquist Audit After Plan 04-18 — 2026-10-08

Plan 04-18's three task rows are now mapped to their passing current-revision checks. `python3 tests/tools/check_phase04_validation_map.py`, `python3 tests/tools/test_check_phase04_validation_map.py -v` (12/12), `python3 tests/tools/test_verify_playable.py -v` (23/23), and `python3 tools/verify_playable.py --check-docs` all pass. The direct checker also reconciles the current GUI-free frontend contract results.

Manual-only/unverified: HOST-02 and the frontend portion of QUAL-03 still require actual pinned RetroArch 1.22.2 observations of content load, guest video, stable no-input frames, RIGHT/LEFT controls, unload, and normal exit. No app launch was attempted. Keep `nyquist_compliant: false`; the four reserved high/open threats and T-04-34 medium/open remain unresolved pending independent review.

## Post-Review Fixture Correction — 2026-10-08

The fresh scoped code review produced a clean current report, which exposed three mutation tests that relied on WR-06 remaining in the live report. The copied-review fixtures now seed the synthetic current finding they exercise, create a Warning section for the WR-99 case, and remove the carried marker when making WR-06 current. `python3 tests/tools/test_check_phase04_validation_map.py -v` passes 12/12, `python3 tests/tools/check_phase04_validation_map.py` passes while rerunning the current qualification and GUI-free frontend suites, and `python3 tools/verify_playable.py --check-docs` passes. This correction adds no claim about actual RetroArch behavior; HOST-02/frontend QUAL-03 remain Pending/unknown and the four high/open threats plus T-04-34 remain open.

## Validation Audit 2026-10-08

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

## Fresh Verification Wording Regression — 2026-10-08

The whole-phase verifier regenerated the actual-app uncertainty with different capitalization and punctuation, then changed the requirement table header and rendered QUAL-03 as Pending. The evidence checker now matches the explicit actual-app/load uncertainty semantically, rejects contradictory success claims, accepts the controlled incomplete requirement states, and recognizes either Source Plan header form. Mutations verify actual uncertainty removal and an affirmative success claim are rejected. `python3 tests/tools/test_check_phase04_validation_map.py -v` passes 12/12 against the fresh report, and the direct evidence gate passes while rerunning the current qualification and GUI-free frontend suites.

## Validation Audit 2026-10-08

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

## Validation Audit 2026-10-08

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

## Validation Audit 2026-10-08

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 0 |
| Escalated | 1 |

## Validation Audit 2026-10-09

| Metric | Count |
|---|---|
| Gaps found | 2 |
| Resolved | 0 |
| Escalated | 2 |

## Validation Audit 2026-10-09

| Metric | Count |
|---|---|
| Gaps found | 3 |
| Resolved | 0 |
| Escalated | 3 |

## Plan 04-21 Current-Revision Reconciliation — 2026-10-09

The final independent code review inspected frozen revision `f1c8a1de5f25224b83da6ec9e4bc40bf51a249ae` and all five required paths, including `tests/libretro/retroarch_smoke.py`. It reported no new actionable findings. The reviewer verified that the control-success counterexample is treated as affirmative despite neighboring unknown wording, and that a copied guide containing “Guest pixels were displayed” fails the docs gate. Existing guide mutations also reject the prior WR-06 app-load and control-success phrases. A prior pass found that the denominator fixture synthesized a validation row; the mutation baseline now uses the live source row and the correction was independently reviewed.

| Check | Command | Result |
|---|---|---|
| Evidence-map source mutations | `python3 tests/tools/test_check_phase04_validation_map.py -v` | PASS, 22/22 |
| Qualification/privacy suite | `python3 tests/tools/test_verify_playable.py -v` | PASS, 27/27 |
| GUI-free frontend contract suite | `python3 tests/libretro/test_retroarch_smoke.py -v` | PASS, 27/27 |
| Consumer documentation gate | `python3 tools/verify_playable.py --check-docs` | PASS |
| Current evidence-map direct gate | `python3 tests/tools/check_phase04_validation_map.py` | PASS after final source-identity reconciliation for revision `f1c8a1d`; it re-runs both current suites and compares the denominators below |

Plan 04-21 current suite denominators: qualification 27/27; frontend 27/27.

WR-01 remains open with its exact historical independent-review source: review `04-REVIEW.md` at `87f8d4c`, reviewed revision `870848e553aca6e43f6fec8ae0acefac87270f5b`, timestamp `2026-10-08T23:46:34Z`, carried open. The tested WR-06 and WR-08 counterexamples are now rejected, while both historical review findings remain open for separate disposition under T-04-34. T-04-11, T-04-15, T-04-18 and T-04-20 remain high/open by direction. T-04-34 and T-04-38 remain medium/open; the blocking count remains four high/open rows. No security register or phase verification claim was changed.

HOST-02 and frontend QUAL-03 remain manual-only and Pending/unknown. No RetroArch process or GUI was launched, and no repository test or guide statement is evidence of actual pinned frontend load, presentation, input, unload, or exit. `nyquist_compliant` remains false.

## Post-execution code review — 2026-10-09

The configured standard-depth review of revision `48befe7a92d7c545e7c900c57e027b9e15952a7f` found WR-09: `require_reviewed_source_identity()` accepts a nonexistent extra path in the claimed review scope. WR-09 remains open and is crosswalked to medium/open T-04-43. The security register now has seven open threats (four high, three medium); `threats_open` remains four at the configured high threshold. The current exact-open-set checker predates this newly discovered medium finding and requires a follow-up gap plan before the direct evidence-map gate can pass again. HOST-02/frontend QUAL-03 remain Pending/unknown and manual-only.

## Validation Audit 2026-10-09

| Metric | Count |
|---|---|
| Gaps found | 3 |
| Resolved | 3 |
| Escalated | 0 |

## Plan 04-22 Current Suite Denominators — 2026-10-09

The independent standard-depth review at `04-REVIEW.md` inspected exact source revision `007f331b1507331382826e779218d39a5f31fab4` and found no remaining issues in the reviewed five-file scope. The evidence-map mutation suite passed 24/24, qualification/privacy passed 27/27, GUI-free frontend contracts passed 27/27, the consumer docs gate passed, and the direct evidence-map gate passed after the review receipt named that revision. The direct gate confirmed the live denominators and preserved the four directed high/open and three medium/open threats. WR-10 and WR-11 are fixed on this evidence; WR-09/T-04-43 stays open.

Plan 04-22 current suite denominators: qualification 27/27; frontend 27/27.

HOST-02 remains Pending/unknown and frontend QUAL-03 remains partial/needs-human with actual frontend load unobserved. No RetroArch GUI was launched; callback, smoke-contract, docs, and review checks do not establish actual frontend behavior. Phase 04 remains blocked and `nyquist_compliant` remains false.
