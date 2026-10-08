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
| Nyquist WR-01 | 04-12 | 10 | Review audit | WR-01 | Accept reconciled current review IDs and dispositions, while rejecting contradictory records | checker regression | `python3 -m unittest discover -s tests/tools -p 'test_check_phase04_validation_map.py' -v` | Yes | escalated: fails at the hardcoded current review ID assertion (line 110) when repaired CR-01 is absent from a reconciled review/disposition fixture |

## Threat Coverage

| Threat | Evidence and disposition |
|--------|--------------------------|
| T-04-11 information disclosure | Plan 04-10 adds whitespace-containing path redaction regressions in the tools and frontend suites. Retained evidence stays under ignored `build/`; private media is not copied into tracked output. Finding remains open pending independent audit. |
| T-04-12 repudiation | Receipt records source revision and selected source hashes, compiler/CMake/SDK/OS/architecture, fixture/core/frontend hashes, candidate revisions, command status and log hashes. |
| T-04-SC dependency closure | Z80 and ymfm immutable source checks passed; YM2610 report records the pinned source and license evidence. Candidate outcomes remain separate from runtime integration. |
| T-04-20 → T-04-11/T-04-15/T-04-18 | Plan 04-10 adds complete path-span redaction and path-with-spaces regression coverage; these older high findings remain open pending independent audit. |
| T-04-21 → T-04-16 | Plan 04-10 checks the pinned public fixture digest before frontend launch; T-04-16 is closed by the current independent audit. Actual app behavior remains unknown. |
| T-04-22 → T-04-17 | Plan 04-10 validates the pinned bundle identifier before quit commands; T-04-17 is closed by the current independent audit. |
| T-04-23 → T-04-13 | Plan 04-11 derives archive rows from committed member bytes and rejects forged receipt rows; T-04-13 is closed by the current independent audit, while carried WR-03 remains open pending independent review. |
| T-04-24 receipt numeric types | Plan 04-12 rejects booleans in bytes, entry_count, file_count and symlink_count before aggregate/archive comparison. Fresh repository-backed regressions pass; independent post-fix audit is still required. |

## Review Finding Crosswalk

| Review Finding | Existing Threat Scope | Disposition |
|----------------|-----------------------|-------------|
| CR-01 | T-04-24, exact numeric receipt types | Plan 04-12 fixes the boolean-count bypass and the fresh review no longer reports CR-01. The stale current-state row remains in the disposition/crosswalk and is part of Nyquist WR-01. |
| CR-02 | T-04-11 / T-04-15 / T-04-18, ambiguous path disclosure | Plan 04-12 supplies complete-span regressions. Disposition remains open pending independent review. |
| WR-01 | Current audit and validation-map evidence boundary | Current stale-checker finding, distinct from historical WR-01 fixture identity. Disposition remains open pending independent review. |
| WR-02 | T-04-11 / T-04-15 / T-04-18 / T-04-20, complete path redaction | Corroborates the same disclosure findings; no separate threat scope. Disposition remains open pending independent review. |
| WR-03 | T-04-13 / T-04-23, receipt row-to-archive binding | Same finding scope; code repair is present and disposition remains open pending independent review. |

## Revision Context

- Plan 04-07's immutable source snapshot implementation is recorded in [04-07-SUMMARY.md](04-07-SUMMARY.md), including commit `36df674`. [04-VERIFICATION.md](04-VERIFICATION.md) preserves that source identity evidence. Plan 04-12 fixes the later boolean-count bypass; the fresh review no longer reports CR-01, but its stale disposition/crosswalk row remains unresolved under Nyquist WR-01.
- Plan 04-10's historical focused runs were 14 tools tests and 24 frontend smoke tests, recorded in [04-10-SUMMARY.md](04-10-SUMMARY.md) at commit `e7aa255`. After the Plan 04-11 implementation commit `a2ea677`, the tools suite was rerun with 17 tests and the frontend smoke suite with 24 tests. The three added tools regressions account for the tools denominator change.
- Plan 04-12 reran the focused suites on implementation `33bef8c`: 19 tools tests and 25 frontend smoke tests passed. Earlier denominators above remain dated history. New controls cover booleans equal to integer values, punctuation/phrase path components, quoted controls and supplied temporary-root descendants. Conservative unquoted redaction intentionally removes ambiguous trailing status; status preceding a private span and bounded structured diagnostics survive.
- These focused suites verify repository behavior only. The current independent audit has T-04-13/T-04-16/T-04-17 closed and T-04-11/T-04-15/T-04-18 open, with security blocked. The disposition ledger still has five open rows, including CR-01 which the fresh review no longer reports; WR-01 keeps that map unreconciled. HOST-02 and actual frontend QUAL-03 remain unknown until the requested pinned-app observations exist.

## Actual Frontend Evidence Handoff

Human evidence is still required: run the generated public fixture in the pinned RetroArch 1.22.2 build and observe a fresh screenshot, repeated no-input frames, RIGHT movement, the LEFT negative control, content unload, and normal application exit. Expected behavior is guest-produced software pixels, stable no-input output, a RIGHT-driven marker change that LEFT does not reproduce, and successful unload and exit. The app previously aborted before its first screenshot; no GUI retry was made because the environment has not materially changed.

## Wave 0 and Sign-Off

- [x] Original fixture source, generator, rights record and oracle contract are present and checked by digest.
- [x] Native frame, input, rendering and negative-control tests run in the clean CTest suite.
- [x] Libretro callback contract and actual RetroArch smoke are separate checks; only the actual smoke can satisfy HOST-02.
- [x] Z80 synthetic admission and YM2610 candidate gates remain distinct, with static/shared C consumers for ymfm.
- [x] Clean install/load procedure includes exact tested compiler, SDK, OS, architecture, frontend and artifact identities.
- [x] Every task maps to an executable command; full clean CTest provides a 34-test denominator.
- [x] No watch-mode acceptance commands are used.

Every plan task has an automated command or an explicit human-evidence route, but Nyquist validation is not compliant while WR-01 remains escalated. The Phase 04 goal is not accepted: HOST-02 remains unknown because the pinned frontend exited before producing a screenshot. The native fixture, Z80 synthetic workload and YM2610 candidate results do not resolve that frontend gap or establish BIOS/game compatibility.

---
*Phase: 04-public-playable-tracer*
*Updated: 2026-10-07*

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

- At that earlier source state, `python3 tests/tools/check_phase04_validation_map.py` failed because it expected six open security findings. Plan 04-12 refreshed the threat assertions; the current gate instead fails at the hardcoded current review-ID assertion documented under Nyquist WR-01. No assertions or goldens were relaxed to make either run pass.
- Read-only reproductions confirmed that a repository receipt with a one-byte row changed from `bytes: 1` to `bytes: true` and a recomputed aggregate digest is accepted, and that commas inside unquoted private paths leave suffixes in both qualification and frontend diagnostic output. These are current code-review blockers.
- The earlier post-wave CTest result was 46/47, with only `owned_cpu_inventory_check` failing because of stale CPU identity/source-manifest and strict compile-command expectations. Plan 04-12 later refreshed that evidence and its summary records 47/47. The pinned RetroArch GUI result remains unknown; no new GUI observation was made.

## Validation Audit 2026-10-08

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 0 |
| Escalated | 1 |
