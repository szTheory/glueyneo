---
phase: "04"
slug: "public-playable-tracer"
status: blocked
threats_open: 4
asvs_level: 1
created: "2026-10-07"
updated: "2026-10-08"
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Native API inputs | Caller-provided fixture envelopes and frame buffers enter the owned C instance. | Fixture bytes, profile and length fields, input bits, video/audio buffers and capacities |
| Libretro adapter | An external frontend supplies content and callbacks to the shared core. | Content pointer and size, controller state, pixel format, callbacks and frame pixels |
| Imported chip candidates | Pinned third-party CPU/audio source is called through private adapters. | Bus operations, clocks, callback tables, sample buffers and candidate state |
| Qualification tooling | Local build and frontend tools produce ignored receipts and logs. | Source/tool/artifact identities, command output, public fixture and local frontend observations |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-04-01 | Tampering | `gn_load` fixture bytes | high | mitigate | `src/instance.c` validates profile, exact length, envelope and guest program before loading. | closed |
| T-04-02 | Denial of service | frame output | high | mitigate | `src/instance.c` checks arguments and capacity before advancing; `tests/fixture/test_public_guest.c` covers canaries and rejected requests. | closed |
| T-04-SC (04-01) | Tampering | source imports | high | mitigate | The fixture is built from tracked first-party source; this plan adds no imported source. | closed |
| T-04-03 | Tampering | `retro_load_game` | high | mitigate | `src/libretro/libretro_core.c` checks data and size, checks `gn_load`, and destroys the instance after failed loads. | closed |
| T-04-04 | Denial of service | `retro_run` callbacks | medium | mitigate | `src/libretro/libretro_core.c` checks callbacks, calls the bounded frame API and retains pixels through the synchronous video callback. | closed |
| T-04-SC (04-02) | Tampering | vendored Libretro header | high | mitigate | `third_party/libretro/NOTICE.md` records the immutable revision, digest and license notice; the tracked header digest matches. | closed |
| T-04-05 | Repudiation | fixture provenance | high | mitigate | `tests/fixture/check_fixture.py` verifies source, artifact and rights identities and scans tracked paths for private media. | closed |
| T-04-SC (04-03) | Tampering | fixture generator inputs | high | mitigate | `tests/fixture/check_fixture.py` checks the single CMake producer, deterministic rebuild and mutation rejection. | closed |
| T-04-06 | Tampering | Z80 import | high | mitigate | `tests/chips/check_z80_source.py` checks the pinned digest, notice, include closure and state inventory. | closed |
| T-04-07 | Denial of service | Z80 tick and bus | medium | mitigate | `src/chips/z80_candidate.c` bounds ticks and latches bus failures; `tests/chips/test_z80.c` covers boundaries and instance separation. | closed |
| T-04-SC (04-04) | Tampering | Z80 source closure | high | mitigate | `tests/chips/check_z80_source.py` gates the exact source closure and license notice without a registry install. | closed |
| T-04-08 | Tampering | ymfm source closure | high | mitigate | `tests/chips/check_ym2610.py` checks source digests, BSD license and inventory sections against `third_party/ymfm/NOTICE.md`. | closed |
| T-04-09 | Denial of service | C/C++ YM2610 shim | high | mitigate | `src/chips/ym2610_candidate.cpp` checks callback bounds and reentry, limits clock/capacity and catches exceptions at the C boundary; failure tests cover these paths. | closed |
| T-04-10 | Denial of service | installed consumer linkage | medium | mitigate | `tests/chips/check_ym2610.py` compiles and runs installed static/shared C consumers and inspects exports and runtime dependencies. | closed |
| T-04-SC (04-05) | Tampering | ymfm source closure | high | mitigate | `tests/chips/check_ym2610.py` gates the pinned Git source closure and BSD notice without a registry install. | closed |
| T-04-11 | Information disclosure | qualification logs | high | mitigate | Plan 04-16 verifies whole-value redaction through retained and printed diagnostics; keep high/open pending explicit closure direction. | open |
| T-04-12 | Repudiation | qualification receipt | medium | mitigate | `tools/verify_playable.py` records command status and log hashes with source, toolchain, frontend, fixture and artifact identities. | closed |
| T-04-SC (04-06) | Tampering | qualification dependency closure | high | mitigate | The clean runner requires pinned Z80 and ymfm source and installed-linkage gates; it contains no package-manager install. | closed |
| T-04-13 | Tampering | snapshot/receipt binding | high | mitigate | Derive bounded rows from the committed archive and compare the complete row list, including type, size, mode, digest and symlink target. | closed |
| T-04-14 | Elevation of privilege | archived path/symlink execution | high | mitigate | `tools/verify_playable.py` rejects unsafe archive paths and links, sanitizes the build environment and routes lanes through the snapshot root. | closed |
| T-04-SC (04-07) | Tampering | dependency/source closure | high | mitigate | `tools/verify_playable.py` reuses the pinned Z80 and ymfm source gates without package-manager installation. | closed |
| T-04-15 | Information disclosure | receipt and qualification logs | high | mitigate | Plan 04-16 verifies whole-value redaction through receipt and log sinks; keep high/open pending explicit closure direction. | open |
| T-04-16 | Tampering | frontend process/input evidence | high | mitigate | Hash the fixture bytes and reject any mismatch against the pinned public fixture digest before launching the direct smoke. | closed |
| T-04-17 | Elevation of privilege | local app/script execution | high | mitigate | Check the exact pinned bundle identifier before constructing AppleScript quit commands; the shared quit helper enforces it for normal and cleanup paths. | closed |
| T-04-18 | Information disclosure | screenshots/crash logs | high | mitigate | Plan 04-16 verifies whole-value redaction through frontend diagnostics and crash-reason serialization; keep high/open pending explicit closure direction. | open |
| T-04-SC (04-08) | Tampering | installed runtime/dependency closure | high | mitigate | The final qualification uses the committed snapshot and existing pinned source and linkage gates without new package installation. | closed |
| T-04-19 | Tampering | P04-02-HOST coverage metadata | high | mitigate | `04-02-SUMMARY.md` retains `automated_ui`/`unknown` and `human_judgment: true`; the installed classifier reports zero errors, routes HOST to `present[]`, and excludes it from `auto_passed[]`. | closed |
| T-04-SC (04-09) | Tampering | installed GSD classifier/template | high | mitigate | Plan 04-09 uses the installed local classifier and template without package installation. | closed |
| T-04-20 | Information disclosure | qualification/frontend diagnostics | high | mitigate | Plan 04-16 verifies newline-path suffix removal in both diagnostic pipelines; keep high/open pending explicit closure direction. | open |
| T-04-21 | Tampering | direct smoke fixture identity | high | mitigate | `tests/libretro/retroarch_smoke.py` checks the generated fixture SHA-256 against the documented digest before launch. | closed |
| T-04-22 | Elevation of privilege | app bundle quit target | high | mitigate | `tests/libretro/retroarch_smoke.py` validates the pinned Info.plist identifier before constructing either AppleScript quit path. | closed |
| T-04-SC (04-10) | Tampering | dependency closure | high | mitigate | Plan 04-10 uses the Python standard library and existing test infrastructure; no package or runtime dependency was added. | closed |
| T-04-23 | Tampering | snapshot receipt row binding | high | mitigate | `tools/verify_playable.py` derives bounded archive inventory from committed bytes and compares every receipt row exactly. | closed |
| T-04-SC (04-11) | Tampering | archive parsing/dependency closure | high | mitigate | Plan 04-11 uses the existing bounded Git-archive path and Python standard library; unsafe members reject without a package install. | closed |
| T-04-24 | Tampering | receipt numeric type validation | high | mitigate | `tools/verify_playable.py` rejects JSON booleans in byte/count fields before aggregate and committed archive comparison. | closed |
| T-04-SC (04-12) | Tampering | dependency/source closure | high | mitigate | Plan 04-12 uses existing pinned source and Python standard library only; no package install or new source import. | closed |
| T-04-25 | Information disclosure | quoted qualification/frontend diagnostic paths | high | mitigate | Plan 04-13 covers escaped quotes and repeated sanitation through qualification receipts and frontend diagnostics; later review found a separate newline-boundary variant within the four existing open disclosure threats. | closed |
| T-04-26 | Tampering | review/disposition/validation evidence | medium | mitigate | Plan 04-13 reconciles review history, disposition, validation crosswalk and counts with contradiction controls. | closed |
| T-04-SC (04-13) | Tampering | dependency/source closure | high | mitigate | Plan 04-13 uses existing pinned inputs and Python standard library only; no package install or new imported source. | closed |
| T-04-27 | Information disclosure | qualification/frontend diagnostic redaction | high | mitigate | Plan 04-14 closes the raw-literal-quote boundary through both sanitizers and sinks; newline-containing paths remain covered by T-04-11, T-04-15, T-04-18 and T-04-20, which stay open. | closed |
| T-04-28 | Tampering | review severity reconciliation | medium | mitigate | `IN-`/Info findings and severity-bearing crosswalk reconciliation are covered by focused mutation tests. | closed |
| T-04-29 | Repudiation | sound admission requirement ledger | low | mitigate | SND-01/02 completion is tied to exact existing verifier evidence and bounded workload language. | closed |
| T-04-SC (04-14) | Tampering | source/dependency closure | high | mitigate | Plan 04-14 uses already pinned source and Python standard library; no dependencies or imports were added. | closed |
| T-04-30 | Repudiation | actual frontend evidence and requirement disposition | high | mitigate | Plan 04-15 records unavailable app/core/fixture identities and direct observations as unknown; HOST-02 and frontend QUAL-03 remain Pending. | closed |
| T-04-31 | Tampering | frontend input/video/lifecycle claim | high | mitigate | Plan 04-15 requires screenshot, stable no-input, RIGHT, LEFT negative control, unload and normal exit before any actual-app claim; unavailable precondition preserves unknown. | closed |
| T-04-SC (04-15) | Tampering | source/dependency closure | high | mitigate | Plan 04-15 uses the existing pinned app/core/fixture and standard-library harness; no dependencies or sources were added. | closed |
| T-04-32 | Information disclosure | qualification and frontend diagnostic sinks | high | mitigate | Both sanitizers remove the complete unstructured diagnostic suffix after a private-root match; retained and printed sinks have newline-path regressions. | closed |
| T-04-33 | Tampering | review validation crosswalk | medium | mitigate | The direct checker compares one normalized controlled state exactly with the disposition record; mutation tests reject contradictory state text. | closed |
| T-04-SC (04-16) | Tampering | source/dependency closure | high | mitigate | Plan 04-16 uses Python standard-library and repository code only; no dependency or external source was added. | closed |
| T-04-34 | Tampering | `check_docs()` frontend qualification status | medium | mitigate | The current-state row and known affirmative-claim controls are checked, but fresh independent code review still reproduced alternate positive claims in the consumer guide; retain open under WR-06. | open |
| T-04-SC (04-17) | Tampering | source/dependency closure | high | mitigate | Plan 04-17 uses existing Python standard-library tooling and tracked documents; no package install or external source is added. | closed |
| T-04-35 | Tampering | validation-map authorization and status rows | medium | mitigate | The evidence-map checker binds each row to the current controlled threat and requirement states; mutation tests reject stale and invented authorities. | closed |
| T-04-36 | Tampering | frontend documentation closure grammar | medium | mitigate | `tools/verify_playable.py` constrains frontend state claims and cross-checks controlled requirement rows; mutation tests cover contradictory and unsupported claims. | closed |
| T-04-SC (04-18) | Tampering | source/dependency closure | high | mitigate | Plan 04-18 changes tracked Python standard-library tooling and documentation only; it adds no dependency or external source. | closed |
| T-04-37 | Repudiation | review/disposition/evidence crosswalk | medium | mitigate | Plan 04-19 records revision-scoped independent findings, commands, denominators, limits, and explicit unresolved dispositions; mutation-checked records retain WR-06 as open. | closed |
| T-04-SC (04-19) | Tampering | source/dependency closure | high | mitigate | Plan 04-19 uses tracked Python standard-library code and existing tests only; no dependency or external source was added. | closed |

## Threat Flags

| Flag | Source | Audit note |
|------|--------|------------|
| `threat_flag: native-module-load` | 04-06 SUMMARY, `CMakeLists.txt` | Mapped to T-04-16, frontend process/core evidence. The pinned RetroArch process exited `-6` before a screenshot, so actual loading remains unknown; this security review does not claim HOST-02 acceptance. |

## Accepted Risks Log

No accepted risks.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-07 | 18 | 18 | 0 | gsd-security-auditor |
| 2026-10-08 | 36 | 32 | 4 | gsd-security-auditor |
| 2026-10-08 | 49 | 45 | 4 | gsd-security-auditor |
| 2026-10-08 | 54 | 49 | 5 | gsd-security-auditor |

## Sign-Off

- [x] All declared threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [ ] `threats_open: 0` confirmed — T-04-11, T-04-15, T-04-18 and T-04-20 remain HIGH/open
- [ ] `status: verified` set in frontmatter — status is blocked pending mitigation

**Approval:** blocked 2026-10-08; user selected to keep unresolved high-severity threats open.

## Security Audit 2026-10-08

| Metric | Count |
|---|---|
| Threats found | 28 |
| Closed | 22 |
| Open | 6 |

## Security Audit 2026-10-08

| Metric | Count |
|---|---|
| Threats found | 28 |
| Closed | 25 |
| Open | 3 |

## Security Audit 2026-10-08 — post-04-12 source

| Metric | Count |
|---|---|
| Threats found | 36 |
| Closed | 32 |
| Open | 4 |

The earlier ASVS L1 audit verified threats authored in the first 12 phase plans. T-04-11, T-04-15, T-04-18 and T-04-20 remain HIGH/open; the post-04-14 review found a newline-containing path variant, so these threats remain open pending complete-span redaction. HOST-02 remains unknown; no actual RetroArch acceptance is implied.

## Security Audit 2026-10-08

| Metric | Count |
|---|---|
| Threats found | 36 |
| Closed | 32 |
| Open | 4 |
| Bypass variants reproduced | 1 |

The independent post-04-13 audit reproduced a literal-quote bypass in arbitrary diagnostic text. Plan 04-14 repaired that case and the fresh post-04-14 audit verified the declared plan mitigations; a separate code review then reproduced a newline-boundary bypass. T-04-11, T-04-15, T-04-18 and T-04-20 remain high/open pending redaction through the complete diagnostic value and another independent audit. No GUI launch was repeated.

## Security Audit 2026-10-08

| Metric | Count |
|---|---|
| Threats found | 46 |
| Closed | 42 |
| Open | 4 |

The fresh ASVS L1 audit verified the Phase 04 threat register. T-04-11, T-04-15, T-04-18 and T-04-20 remain HIGH/open as directed. The independent review separately found a newline-containing path variant within this same disclosure scope; the security count does not treat that variant as a resolved risk. HOST-02 and frontend QUAL-03 remain unknown/Pending because no functioning pinned RetroArch observation was available.

## Security Audit 2026-10-08

| Metric | Count |
|---|---|
| Threats found | 49 |
| Closed | 45 |
| Open | 4 |

## Security Audit 2026-10-08

| Metric | Count |
|---|---|
| Threats found | 51 |
| Closed | 47 |
| Open | 4 |

The ASVS L1 audit inspected all 51 plan-authored threats. Mitigations were verified for 47, including new Plan 04-17 threats T-04-34 and T-04-SC (04-17). T-04-11, T-04-15, T-04-18, and T-04-20 remain high/open by explicit user direction; no risks were accepted, and the phase remains blocked. The sole summary threat flag, `native-module-load`, maps to T-04-16. HOST-02 and frontend QUAL-03 remain Pending/unknown because actual pinned-app behavior was not observed.

## Security Audit 2026-10-08

| Metric | Count |
|---|---|
| Threats found | 51 |
| Closed | 46 |
| Open | 5 |

Subsequent independent code review found that T-04-34's frontend closure mitigation is incomplete: `check_docs()` still accepts an alternate affirmative app-load claim alongside Pending/unknown. T-04-34 is therefore open at medium severity pending a constrained status check and regression. The four explicitly reserved high findings remain open, so `threats_open` stays 4 under the high-severity blocking threshold; Phase 04 remains blocked.

## Security Audit 2026-10-08 — post-04-18

| Metric | Count |
|---|---|
| Threats found | 54 |
| Closed | 49 |
| Open | 5 |

The fresh ASVS L1 review verified Plan 04-18's three additions: T-04-35, T-04-36, and T-04-SC (04-18). T-04-34 remains medium/open pending independent post-fix review; T-04-11, T-04-15, T-04-18, and T-04-20 remain high/open by explicit direction. The high-severity blocking count stays 4, no risks were accepted, and the phase remains blocked. HOST-02 and frontend QUAL-03 remain Pending/unknown because actual pinned RetroArch behavior was not observed.

## Security Audit 2026-10-08 — final current-source review

| Metric | Count |
|---|---|
| Current register rows reviewed | 54 |
| Closed | 49 |
| Open | 5 |
| Blocking open (`block_on: high`) | 4 |

The current register was reconciled against the 18 plan threat models and the prior ASVS L1 evidence; the active source delta since the 54-row audit is limited to Phase 04 evidence checkers, their tests, and the validation record. The checker changes were reviewed at ASVS L1 against the exact paths and current controlled records, and the full register still has no accepted risks or unmapped summary threat flag.

| Threat ID | ASVS L1 result | Current evidence |
|---|---|---|
| T-04-35 | CLOSED | `tests/tools/check_phase04_validation_map.py` parses all current security rows, rejects duplicate IDs, counts only high/open blockers, requires the exact four high/open IDs plus T-04-34 medium/open, rejects other open rows, and requires the blocking count to equal the parsed rows. It pins current frontend requirement/report rows; `tests/tools/test_check_phase04_validation_map.py` exercises count, severity, status, duplicate-row, and contradictory-evidence mutations. The direct checker and 14-test mutation suite pass. |
| T-04-36 | CLOSED | `tools/verify_playable.py::check_docs()` requires exactly one current `04-15 T2` row, checks that both requirements are named, and full-matches the status against the Pending/unknown grammar. Its tests accept the canonical pending state and reject affirmative, appended, placeholder, missing, and contradictory status claims. The 23-test qualification suite and docs-only gate pass. |
| T-04-34 | OPEN — medium, retained after independent post-fix review | The known-phrase detector rejects enumerated mutations, but the code reviewer reproduced alternate app-run and control-success claims. It does not count toward `threats_open` because `block_on: high`. |
| T-04-11, T-04-15, T-04-18, T-04-20 | OPEN — high, retained by explicit direction | No closure is inferred from the checker tests or this review. The four disclosure threats continue to block the phase. |

That audit's 54-row inventory had 49 closed and 5 open: the four directed high-severity disclosure threats and T-04-34 at medium severity. Thus `threats_open: 4` remains the severity-filtered blocking count. HOST-02 and frontend QUAL-03 remain Pending/unknown, and actual pinned RetroArch load, display, controls, unload, and exit remain manual-only and unobserved; GUI-free tests are not frontend proof.

## Security Audit 2026-10-08 — Plan 04-19 independent current-revision pass

| Metric | Count |
|---|---:|
| Reviewed source revision | `9804351907e456b3ab85ebe4a49959c05b0714bb` |
| Current threat rows reviewed | 54 |
| Closed | 49 |
| Open | 5 |
| Blocking open (`block_on: high`) | 4 |

The independent ASVS L1 audit covered `tools/verify_playable.py`, the read-only frontend diagnostic sanitizer in `tests/libretro/retroarch_smoke.py`, focused tests, evidence-map checker/mutations, and current Phase 04 security, review, disposition, validation, verification, and plan records. The qualification suite passed 23/23, frontend contract suite 27/27, and evidence-map mutation suite 14/14; the docs-only gate and direct evidence-map checker passed. Forged receipt file rows remain rejected after aggregate recomputation; newline, space, escaped-quote and apostrophe path controls pass across retained/printed sinks. No GUI was launched. These checks do not establish actual RetroArch loading or behavior.

The code reviewer reproduced WR-06 in the consumer guide even though the independent auditor initially inferred closure from the exact verification-row gate: an affirmative app-load/pixel sentence and a separate RIGHT-input/unload sentence were both accepted when appended to a temporary guide. T-04-34 therefore remains medium/open. T-04-11, T-04-15, T-04-18, and T-04-20 remain high/open by direction. No risks are accepted; HOST-02 and frontend QUAL-03 remain Pending/unknown and manual-only.

## Security Audit 2026-10-08 — Plan 04-19 post-fix reconciliation

| Metric | Count |
|---|---:|
| Current threat rows | 56 |
| Closed | 51 |
| Open | 5 |
| Blocking open (`block_on: high`) | 4 |

The independent security auditor reviewed the bounded docs-check patch at `2a82c455f85671ba144a42923318c4ff7d53b9a2` and found the original and enumerated paraphrases rejected by the 25/25 qualification suite and `--check-docs`; it supported closing T-04-34 for that tested set. The independent code reviewer then reproduced further affirmative claims in temporary guide copies: `The frontend booted the game and showed its output.` and `The controls worked as expected in RetroArch.` Since a direct contradictory claim still passes, this register conservatively keeps T-04-34 medium/open. The new Plan 04-19 threats are closed: review provenance is recorded under T-04-37, and no dependency or external source was added under T-04-SC (04-19). Four directed high/open disclosures remain blockers. HOST-02 and frontend QUAL-03 remain Pending/unknown; no GUI was launched.
