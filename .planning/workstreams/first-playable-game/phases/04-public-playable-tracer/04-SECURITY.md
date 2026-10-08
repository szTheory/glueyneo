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
| T-04-11 | Information disclosure | qualification logs | high | mitigate | Redact complete private paths before retaining qualification diagnostics. A literal quote in arbitrary diagnostic text can be mistaken for a JSON boundary and expose `tail/sensitive.bin`. | open |
| T-04-12 | Repudiation | qualification receipt | medium | mitigate | `tools/verify_playable.py` records command status and log hashes with source, toolchain, frontend, fixture and artifact identities. | closed |
| T-04-SC (04-06) | Tampering | qualification dependency closure | high | mitigate | The clean runner requires pinned Z80 and ymfm source and installed-linkage gates; it contains no package-manager install. | closed |
| T-04-13 | Tampering | snapshot/receipt binding | high | mitigate | Derive bounded rows from the committed archive and compare the complete row list, including type, size, mode, digest and symlink target. | closed |
| T-04-14 | Elevation of privilege | archived path/symlink execution | high | mitigate | `tools/verify_playable.py` rejects unsafe archive paths and links, sanitizes the build environment and routes lanes through the snapshot root. | closed |
| T-04-SC (04-07) | Tampering | dependency/source closure | high | mitigate | `tools/verify_playable.py` reuses the pinned Z80 and ymfm source gates without package-manager installation. | closed |
| T-04-15 | Information disclosure | receipt and qualification logs | high | mitigate | Redact complete home, temporary and private paths before persisting diagnostics. A literal quote in arbitrary diagnostic text can expose the remaining suffix in receipt and printed output. | open |
| T-04-16 | Tampering | frontend process/input evidence | high | mitigate | Hash the fixture bytes and reject any mismatch against the pinned public fixture digest before launching the direct smoke. | closed |
| T-04-17 | Elevation of privilege | local app/script execution | high | mitigate | Check the exact pinned bundle identifier before constructing AppleScript quit commands; the shared quit helper enforces it for normal and cleanup paths. | closed |
| T-04-18 | Information disclosure | screenshots/crash logs | high | mitigate | Redact complete frontend and crash diagnostics before machine output or receipt persistence. A literal quote in arbitrary crash text can expose path suffixes. | open |
| T-04-SC (04-08) | Tampering | installed runtime/dependency closure | high | mitigate | The final qualification uses the committed snapshot and existing pinned source and linkage gates without new package installation. | closed |
| T-04-19 | Tampering | P04-02-HOST coverage metadata | high | mitigate | `04-02-SUMMARY.md` retains `automated_ui`/`unknown` and `human_judgment: true`; the installed classifier reports zero errors, routes HOST to `present[]`, and excludes it from `auto_passed[]`. | closed |
| T-04-SC (04-09) | Tampering | installed GSD classifier/template | high | mitigate | Plan 04-09 uses the installed local classifier and template without package installation. | closed |
| T-04-20 | Information disclosure | qualification/frontend diagnostics | high | mitigate | Plan 04-13 covers escaped quotes, but a literal embedded quote in an arbitrary diagnostic can still leave `tail/sensitive.bin` visible in both sanitizers. | open |
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
