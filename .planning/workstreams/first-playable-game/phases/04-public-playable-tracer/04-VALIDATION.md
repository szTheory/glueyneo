---
phase: "04"
slug: "public-playable-tracer"
status: validated
nyquist_compliant: true
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

## Threat Coverage

| Threat | Evidence and disposition |
|--------|--------------------------|
| T-04-11 information disclosure | Plan 04-10 adds whitespace-containing path redaction regressions in the tools and frontend suites. Retained evidence stays under ignored `build/`; private media is not copied into tracked output. Finding remains open pending independent audit. |
| T-04-12 repudiation | Receipt records source revision and selected source hashes, compiler/CMake/SDK/OS/architecture, fixture/core/frontend hashes, candidate revisions, command status and log hashes. |
| T-04-SC dependency closure | Z80 and ymfm immutable source checks passed; YM2610 report records the pinned source and license evidence. Candidate outcomes remain separate from runtime integration. |
| T-04-20 → T-04-11/T-04-15/T-04-18 | Plan 04-10 adds complete path-span redaction and path-with-spaces regression coverage; these older high findings remain open pending independent audit. |
| T-04-21 → T-04-16 | Plan 04-10 checks the pinned public fixture digest before frontend launch; the security disposition remains open pending independent audit. |
| T-04-22 → T-04-17 | Plan 04-10 validates the pinned bundle identifier before quit commands; the security disposition remains open pending independent audit. |
| T-04-23 → T-04-13 | Plan 04-11 derives archive rows from committed member bytes and rejects forged receipt rows; WR-03 remains open pending independent audit. |

## Review Finding Crosswalk

| Review Finding | Existing Threat Scope | Disposition |
|----------------|-----------------------|-------------|
| WR-01 | T-04-16 / T-04-21, pinned fixture identity | Same finding scope; code repair is present and disposition remains open pending independent review. |
| WR-02 | T-04-11 / T-04-15 / T-04-18 / T-04-20, complete path redaction | Corroborates the same disclosure findings; no separate threat scope. Disposition remains open pending independent review. |
| WR-03 | T-04-13 / T-04-23, receipt row-to-archive binding | Same finding scope; code repair is present and disposition remains open pending independent review. |

## Revision Context

- Plan 04-07's immutable source snapshot implementation is recorded in [04-07-SUMMARY.md](04-07-SUMMARY.md), including commit `36df674`. The fresh [04-VERIFICATION.md](04-VERIFICATION.md) identifies current source identity as protected; together these records support marking historical CR-01 fixed.
- Plan 04-10's historical focused runs were 14 tools tests and 24 frontend smoke tests, recorded in [04-10-SUMMARY.md](04-10-SUMMARY.md) at commit `e7aa255`. After the Plan 04-11 implementation commit `a2ea677`, the tools suite was rerun with 17 tests and the frontend smoke suite with 24 tests. The three added tools regressions account for the tools denominator change.
- These focused suites verify repository behavior only. They do not close any security finding; the independent audit must decide all six open high-severity dispositions. HOST-02 and actual frontend QUAL-03 remain unknown until the requested pinned-app observations exist.

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

The validation strategy and its automation are complete. The Phase 04 goal is not yet accepted: HOST-02 remains unknown because the pinned frontend exited before producing a screenshot. The native fixture, Z80 synthetic workload and YM2610 candidate results do not resolve that frontend gap or establish BIOS/game compatibility.

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
