---
phase: "04"
slug: "public-playable-tracer"
status: open
threats_open: 6
asvs_level: 1
created: "2026-10-07"
updated: "2026-10-10"
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
| T-04-11 | Information disclosure | qualification logs | high | mitigate | `tools/private_paths.py` (c75f577): exact runtime roots in every observed form drop the rest of the value, and each public sink fails closed with `private-path-survived`; `tests/tools/test_private_paths.py` reproduces every audited bypass class; printed qualification output and receipt are covered. Retained run-directory logs are accepted separately as T-04-44. Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, printed output leaks via raw OSError in --record-frontend-evidence, unredacted runner None traceback, and U+2215/dash-mangled/double-percent forms passing redact+scan_public. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): OPEN tools/private_paths.py:109-115 applies NFKC one character at a time, so a decomposed (NFD) non-ASCII root never composes and does not match its NFC form (or the reverse). Both root matching and the username-token check miss it. The `--clean --check-docs` repair itself holds (tools/verify_playable.py:1547-1556). | open |
| T-04-12 | Repudiation | qualification receipt | medium | mitigate | `tools/verify_playable.py` records command status and log hashes with source, toolchain, frontend, fixture and artifact identities. | closed |
| T-04-SC (04-06) | Tampering | qualification dependency closure | high | mitigate | The clean runner requires pinned Z80 and ymfm source and installed-linkage gates; it contains no package-manager install. | closed |
| T-04-13 | Tampering | snapshot/receipt binding | high | mitigate | Derive bounded rows from the committed archive and compare the complete row list, including type, size, mode, digest and symlink target. | closed |
| T-04-14 | Elevation of privilege | archived path/symlink execution | high | mitigate | `tools/verify_playable.py` rejects unsafe archive paths and links, sanitizes the build environment and routes lanes through the snapshot root. | closed |
| T-04-SC (04-07) | Tampering | dependency/source closure | high | mitigate | `tools/verify_playable.py` reuses the pinned Z80 and ymfm source gates without package-manager installation. | closed |
| T-04-15 | Information disclosure | receipt and qualification logs | high | mitigate | `tools/private_paths.py` (c75f577): exact runtime roots in every observed form drop the rest of the value, and each public sink fails closed with `private-path-survived`; `tests/tools/test_private_paths.py` reproduces every audited bypass class; the receipt writer fails closed and artifact inventories omit CMakeFiles internals (`test_receipt_writer_fails_closed_on_a_surviving_path`, `test_artifact_tree_omits_cmake_internals`). Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, receipt sanitize() skips dict keys and scan_public runs on ensure_ascii JSON so fullwidth key and U+2215 value survive. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): OPEN tools/private_paths.py:109-115 per-character NFKC leaves an NFC/NFD form of a runtime root undetected, so the receipt scan in tools/verify_playable.py:1313 passes it. The CMakeFiles omission (tools/verify_playable.py:1278) and the fail-closed receipt test are present. | open |
| T-04-16 | Tampering | frontend process/input evidence | high | mitigate | Hash the fixture bytes and reject any mismatch against the pinned public fixture digest before launching the direct smoke. | closed |
| T-04-17 | Elevation of privilege | local app/script execution | high | mitigate | Check the exact pinned bundle identifier before constructing AppleScript quit commands; the shared quit helper enforces it for normal and cleanup paths. | closed |
| T-04-18 | Information disclosure | screenshots/crash logs | high | mitigate | `tools/private_paths.py` (c75f577): exact runtime roots in every observed form drop the rest of the value, and each public sink fails closed with `private-path-survived`; `tests/tools/test_private_paths.py` reproduces every audited bypass class; smoke stdout passes through `public_json()` (`test_smoke_output_fails_closed_on_a_surviving_path`); screenshots stay in a deleted temporary directory. Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, public_json() passed dash-mangled and U+2215 diagnostics; uncaught struct/zlib errors in decode_png bypass public_json. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): OPEN tools/private_paths.py:109-115 has the same NFD/NFC gap, which also reaches smoke `public_json` (tests/libretro/retroarch_smoke.py:115-123). Screenshots stay in the TemporaryDirectory (tests/libretro/retroarch_smoke.py:901). | open |
| T-04-SC (04-08) | Tampering | installed runtime/dependency closure | high | mitigate | The final qualification uses the committed snapshot and existing pinned source and linkage gates without new package installation. | closed |
| T-04-19 | Tampering | P04-02-HOST coverage metadata | high | mitigate | `04-02-SUMMARY.md` retains `automated_ui`/`unknown` and `human_judgment: true`; the installed classifier reports zero errors, routes HOST to `present[]`, and excludes it from `auto_passed[]`. | closed |
| T-04-SC (04-09) | Tampering | installed GSD classifier/template | high | mitigate | Plan 04-09 uses the installed local classifier and template without package installation. | closed |
| T-04-20 | Information disclosure | qualification/frontend diagnostics | high | mitigate | `tools/private_paths.py` (c75f577): exact runtime roots in every observed form drop the rest of the value, and each public sink fails closed with `private-path-survived`; `tests/tools/test_private_paths.py` reproduces every audited bypass class; no boundary inference remains, and the newline-suffix regressions pass in both pipelines. Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, build_diagnostic+public_json and Runner redact+_write_receipt pass dash-mangled, U+2215, double-percent and HFS/tmpdir forms. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): OPEN tools/private_paths.py:109-115: not every form of a root is caught (decomposed Unicode). The newline-suffix tests and start-only generic matching are present (tools/private_paths.py:205-220). | open |
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
| T-04-34 | Tampering | frontend qualification status and uncertainty claims | medium | mitigate | Superseded (cc73f94): the prose claim scan is retired; frontend status is generated from the tracked receipt summary, which must carry the exact passing lane set, fixture and pinned RetroArch digests, a rightward marker move and an inventory digest reproduced from `git archive`; forgery and mismatch mutations in `tests/tools/test_verify_playable.py`. Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, check_docs passed a forged Complete summary because ancestry/inventory binding runs only when source_root/.git exists, never in the --clean snapshot. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/verify_playable.py:835-876 checks the exact lane set, both digests, the rightward marker move, os, core and mapping; :938-944 re-archives the revision and compares the inventory digest; the forgery mutations are at tests/tools/test_verify_playable.py:766-805. | closed |
| T-04-SC (04-17) | Tampering | source/dependency closure | high | mitigate | Plan 04-17 uses existing Python standard-library tooling and tracked documents; no package install or external source is added. | closed |
| T-04-35 | Tampering | validation-map authorization and status rows | medium | mitigate | The evidence-map checker binds each row to the current controlled threat and requirement states; mutation tests reject stale and invented authorities. | closed |
| T-04-36 | Tampering | frontend documentation closure grammar | medium | mitigate | `tools/verify_playable.py` constrains frontend state claims and cross-checks controlled requirement rows; mutation tests cover contradictory and unsupported claims. | closed |
| T-04-SC (04-18) | Tampering | source/dependency closure | high | mitigate | Plan 04-18 changes tracked Python standard-library tooling and documentation only; it adds no dependency or external source. | closed |
| T-04-37 | Repudiation | review/disposition/evidence crosswalk | medium | mitigate | Plan 04-19 records revision-scoped independent findings, commands, denominators, limits, and explicit unresolved dispositions; mutation-checked records retain WR-06 as open. | closed |
| T-04-SC (04-19) | Tampering | source/dependency closure | high | mitigate | Plan 04-19 uses tracked Python standard-library code and existing tests only; no dependency or external source was added. | closed |
| T-04-38 | Repudiation | current review provenance and sanitizer coverage | medium | mitigate | Superseded (c75f577): the bespoke evidence-map checker is retired; review provenance is the GSD code-review `reviewed_revision`/`files_reviewed_list` record and verification `covered_digest` freshness. Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, no phase-04 gate checks review provenance; check_docs crosswalk accepts any non-empty scope marked fixed. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/verify_playable.py:1169-1193 requires every non-open disposition to cite a revision that resolves and is a committed ancestor; tests at tests/tools/test_verify_playable.py:1038-1080. | closed |
| T-04-39 | Tampering | qualification result crosswalk | medium | mitigate | `tests/tools/check_phase04_validation_map.py` compares the report denominator with the live `run_suite()` count and rejects stale, absent, duplicate, or malformed rows. | closed |
| T-04-40 | Tampering | source/dependency closure (04-20) | high | mitigate | Plan 04-20 checker and test imports use tracked repository code and Python standard library only; no external dependency or source was added. | closed |
| T-04-41 | Tampering | security/evidence-map reconciliation | medium | mitigate | `tests/tools/check_phase04_validation_map.py` enforces the exact open-threat rows and rejects duplicate or unexpected open rows; mutation tests cover those changes. | closed |
| T-04-42 | Tampering | frontend claim predicates and docs gate | medium | mitigate | The validation checker and `tools/verify_playable.py` reject affirmative frontend output, control, and lifecycle claims while actual frontend evidence is unknown. | closed |
| T-04-43 | Repudiation | review provenance | medium | mitigate | Fixed before retirement (exact reviewed-path set at 007f331, rejected nonexistent-path mutation), then superseded with the checker in c75f577. Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, check_docs accepted a crosswalk row naming a nonexistent review path marked fixed. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/verify_playable.py:1137-1144 rejects nonexistent, unreviewed and `..` scope paths; tests at tests/tools/test_verify_playable.py:985-1000. | closed |
| T-04-44 | Information disclosure | retained run-directory logs under ignored `build/playable-qualification/` | medium | accept | The run directory holds raw build trees (`CMakeCache.txt`, compiler logs) that cannot be made publishable; it is git-ignored, no CI job or release reads it, and the guide declares it private. See Accepted Risks Log. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Maintainer acceptance (D-GAP-02, 2026-10-10) is final. Tool-scoped independent review (04-34, 0d9612130092), recorded as evidence only: CLOSED .gitignore:9 ignores /build/. The only reference is OUTPUT in tools/verify_playable.py:37; no file under .github/workflows reads it; docs/first-playable-build.md:82 declares the run directory private. | accepted |
| T-04-SC (04-21) | Tampering | source/dependency closure | high | mitigate | Plan 04-21 uses tracked repository code and Python standard library only; no dependency or external source was added. | closed |
| T-04-45 | Information disclosure | `--record-frontend-evidence` to tracked receipt summary | medium | mitigate | validate_frontend_evidence runs private_paths.scan_public on the summary and fails closed; Task 1 greps the tracked file for home-directory paths. Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, frontend_evidence_summary accepted a fullwidth-separator home path and the generated guide block is written unscanned. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/verify_playable.py:872-875 scans the summary and raises RuntimeError on a hit; tools/private_paths.py:286-289 turns an unserializable structure into PrivatePathError("unscannable-value"), tested at tests/tools/test_private_paths.py:265-270. | closed |
| T-04-46 | Repudiation | receipt-to-revision binding | medium | mitigate | --clean archives committed HEAD only; check_docs re-archives the revision and checks ancestry and inventory digest. Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, load_frontend_evidence skips ancestry and inventory checks when source_root/.git is absent, as in the --clean snapshot. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/verify_playable.py:1385 archives HEAD; :922-944 checks ancestry and re-archives the digest; main passes repository=ROOT, head=snapshot.commit (:1544). | closed |
| T-04-47 | Denial of service | pinned RetroArch launch on the shared host | low | mitigate | `pgrep -x RetroArch` empty before and after each run; sampled maximum 1 during qualification; no retry-to-green. Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, an outer timeout can skip the finally-quit and orphan the app, and no pre-launch instance check exists in the harness. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/verify_playable.py:614-648 runs `pgrep -x RetroArch` before and after the lane; tests/libretro/retroarch_smoke.py:707-711 refuses a stacked launch; there is no retry loop. | closed |
| T-04-48 | Repudiation | threat and review closure records | high | mitigate | Closure needs a verdict from a separate headless gsd-security-auditor session; a zero, duplicate or malformed verdict counts as OPEN; check_security_register.py keeps threats_open equal to open high rows. Independent post-c75f577 review (04-23, aaf3f093ab0f): OPEN, register_errors() returned no errors for a commented or duplicated frontmatter key and for a second table with a high open row. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/independent_review.py:194-213 makes a zero, duplicate, malformed or wrong-vocabulary verdict OPEN; tests/tools/check_security_register.py:156-158 enforces threats_open equal to the blocking count. | closed |
| T-04-SC (04-23) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency is added; the plan uses only tracked tools, the installed GSD agent and the Python standard library. The reviewer found no installs (raw CLOSED) but its session had unscoped Bash, so under the plan containment rule the verdict is treated as OPEN. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED No package installs anywhere in tools/, tests/, CMakeLists.txt or .github; all imports in tools/*.py and tests/tools/*.py are standard library. | closed |
| T-04-49 | Denial of service | canonical generic-root matching | medium | mitigate | Generic roots match only at path starts; benign regression list (`build/tmp-like ok`, `docs/tmp/notes`, `public_users_list`) must pass. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/private_paths.py:213-219 matches generic roots only at path starts; the benign list including `docs/tmp/notes` and `public_users_list` is at tests/tools/test_private_paths.py:177-183. | closed |
| T-04-50 | Denial of service | escape/percent decoding of large logs | low | mitigate | Percent-decode fixpoint bounded to 8 passes; single linear pass per stage with an index map; no prefix re-folding. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/private_paths.py:57,100-106 bounds percent decoding to 8 passes; `_substitute` (:67-80) is a single linear pass with an index map. | closed |
| T-04-51 | Tampering | workstream argument interpolated into a glob | medium | mitigate | The workstream name is validated against `^[A-Za-z0-9][A-Za-z0-9._-]*$` before globbing and fails with `FAIL:` otherwise. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tests/tools/check_security_register.py:45,197-199 validates the workstream name before the glob at :206; the `../x` mutation is at tests/tools/test_check_security_register.py:104. | closed |
| T-04-52 | Denial of service | `--check-docs` in a source archive without `.git` | low | accept | Fail closed by design: without a repository, tracked evidence cannot be bound; the guide documents that the gate runs from a checkout or through `--clean --check-docs`. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Maintainer acceptance (D-GAP-02, 2026-10-10) is final. Tool-scoped independent review (04-34, 0d9612130092), recorded as evidence only: CLOSED tools/verify_playable.py:924-925 fails closed when no repository exists; the limit is documented at docs/first-playable-build.md:82 and tested at tests/tools/test_verify_playable.py:917-926. | accepted |
| T-04-53 | Tampering | multi-file evidence write | medium | mitigate | All contents are computed, validated and scanned first, then written through temp files and `os.replace`; a failed precondition leaves all three files byte-identical (tested). Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/verify_playable.py:986-1035 validates and scans first, writes temp files, restores originals on a failed replace and writes the guide last; tests at tests/tools/test_verify_playable.py:1179-1214. | closed |
| T-04-54 | Elevation of privilege | process-group and PID signalling | medium | mitigate | Signal only process groups or PIDs this code started and has not reaped (`poll() is None`); after a lane, signal only the frontend PID the lane smoke recorded, while it is a survivor and its own group leader; never by process name. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/verify_playable.py:527-545 keeps the leader unreaped (WNOWAIT) while it sends group signals; :583-599 signals only the recorded PID's own group; tests/libretro/retroarch_smoke.py:648-661 never signals after reaping. | closed |
| T-04-55 | Denial of service | pre-launch refusal when a user RetroArch is open | low | accept | By design under the single-instance rule: qualification refuses rather than stacking or touching the user instance; the reason is named and documented. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Maintainer acceptance (D-GAP-02, 2026-10-10) is final. Tool-scoped independent review (04-34, 0d9612130092), recorded as evidence only: CLOSED tools/verify_playable.py:617-619 refuses with the named reason `retroarch-instance-already-running`; documented at docs/first-playable-build.md:52. | accepted |
| T-04-56 | Tampering | duplicated runtime copies sharing hidden mutable state | medium | mitigate | `runtime_writable_storage` CTest fails on any writable data or zero-initialized runtime symbol; no allowlist; Windows reported unsupported rather than passed. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): OPEN tests/tools/check_runtime_storage.py:35 `MACHO_LINE` only accepts `non-external\|external`. Mach-O `nm -m` lines for `private external` (the hidden-visibility globals glueyneo_runtime_static is built with, CMakeLists.txt:167), `weak external` and unlinked `(common)` symbols are never parsed, so writable globals pass unaudited on macOS. | open |
| T-04-57 | Denial of service | product CTest coupled to planning state | low | mitigate | `planning_security_register` is registered only when the configured workstream exists; the mutation suite stays unconditional. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED CMakeLists.txt:885-905 registers the test only when the workstream exists and makes an explicit missing workstream a FATAL_ERROR; the mutation suite is unconditional (:906-907). | closed |
| T-04-58 | Tampering | installed-core self-containment check | low | mitigate | Full-path `otool` parsing and a macOS system-path allowlist so a spaced or third-party dependency cannot slip past. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tests/consumers/check_package.py:312 parses the full path with `(.+?) \(compatibility version`; :334-342 applies the macOS system allowlist; tests at tests/consumers/test_check_package.py:50-67. | closed |
| T-04-59 | Denial of service | username-token false positives in receipts | medium | mitigate | The token check skips a generic service-account name only under GitHub Actions; home paths stay covered by canonical root matching; personal names and non-CI hosts are still rejected. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/private_paths.py:242-243 skips the token only for a service name under GITHUB_ACTIONS; tests at tests/tools/test_private_paths.py:197-226. | closed |
| T-04-60 | Information disclosure | bare generic account name in public output under GitHub Actions | low | accept | A generic account name on a GitHub-hosted runner is not a personal identifier; every full home-path form is still rejected. Residual and invalidation trigger documented in docs/testing.md. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Maintainer acceptance (D-GAP-02, 2026-10-10) is final. Tool-scoped independent review (04-34, 0d9612130092), recorded as evidence only: CLOSED tools/private_paths.py:24-30,242 implement the skip as described; the residual and trigger are documented at docs/testing.md:206-211; no defect contradicts the rationale. | accepted |
| T-04-SC (04-24) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/private_paths.py:41-47 imports only json, os, pathlib, re, tempfile, unicodedata and typing. | closed |
| T-04-SC (04-25) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tests/tools/check_security_register.py:38-41 imports only json, pathlib, re and sys. | closed |
| T-04-SC (04-26) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/verify_playable.py:11-34 imports only the standard library and the tracked private_paths. | closed |
| T-04-SC (04-27) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/verify_playable.py and tests/tools/test_verify_playable.py:4-24 use only the standard library and tracked code. | closed |
| T-04-SC (04-28) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tests/libretro/retroarch_smoke.py:6-24 imports signal, os, subprocess, zlib and other standard modules, plus tracked private_paths. | closed |
| T-04-SC (04-29) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tests/tools/check_runtime_storage.py:23-28 is standard library only; CMakeLists.txt:910-912 uses CMAKE_NM. | closed |
| T-04-SC (04-30) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tests/consumers/check_package.py:6-17 is standard library only and calls the system `otool` (:307). | closed |
| T-04-SC (04-31) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-31, 7615dd911678): REVIEW HALTED: containment-violation, recorded open (the session failed the mechanical containment gate, so no verdict is transcribed). Tool-scoped independent review (04-34, 0d9612130092): CLOSED tools/independent_review.py:41-49 is standard library plus tracked private_paths. | closed |
| T-04-61 | Tampering | review containment path boundary | high | mitigate | `tools/independent_review.py` `path_contained` resolves symlinks and relative paths against the init cwd and accepts only a path equal to or under the scratch realpath (D-GAP-01); any `..` segment is not contained; an absolute pattern's literal prefix must be contained; `preflight` refuses a scratch tree with an external symlink; any violation gives all OPEN. Tool-scoped independent review (04-34, 0d9612130092): OPEN tools/independent_review.py:78-100 does not handle `~`: `path_contained("~", ...)` joins it under cwd and calls it contained, but the Read/Glob/Grep tools expand `~` to the home directory. tests/tools/test_independent_review.py has no tilde case. | open |
| T-04-62 | Repudiation | register table schema drift | high | mitigate | `check_security_register.py` errors on any `Threat ID` table lacking Severity or Status; mutation test reproduces the `Sev`/`State` fail-open; audit tables use `Audited Threat`. Tool-scoped independent review (04-34, 0d9612130092): OPEN tests/tools/check_security_register.py:49 `HEADER` requires an exact `Threat ID` cell and a trailing `\|`. A second register table whose header has no trailing pipe (or a re-cased `Threat Id`) is skipped silently, and its open high rows are not counted. | open |
| T-04-63 | Tampering | untracked workstream config lowering block_on | medium | mitigate | Workstream `security_block_on` may not be less strict than the root config; FAIL otherwise; the PASS line names the threshold and its source. Tool-scoped independent review (04-34, 0d9612130092): CLOSED tests/tools/check_security_register.py:88-91 rejects a weaker workstream value; the PASS line names the threshold and source (:236-237); tests at tests/tools/test_check_security_register.py:279-311. | closed |
| T-04-64 | Repudiation | phase-scoped closure masking other registers | medium | mitigate | `--phase NN` requires exactly one register and prints `scope: phase NN`; milestone shipping runs the unscoped `--require-closed`; documented in docs/testing.md. Tool-scoped independent review (04-34, 0d9612130092): CLOSED tests/tools/check_security_register.py:211-214,235 requires exactly one register and prints `scope: phase NN`; documented at docs/testing.md:123,141-147. | closed |
| T-04-65 | Information disclosure | review tool output | medium | mitigate | CLI messages carry IDs and reason codes only; every printed line passes `private_paths.scan_public` and fails closed as `private-path-survived`; tested. Tool-scoped independent review (04-34, 0d9612130092): OPEN tools/independent_review.py:447-455 catches only InputError. A malformed stream (a non-dict `message` at :119, or unhashable `tools`/`name` at :156,:162) and argparse errors print an unscanned traceback or usage text that carries absolute paths. | open |
| T-04-66 | Denial of service | smoke interrupt during frontend launch | medium | mitigate | Deferred-interrupt launch window around Popen, assignment and PID record; pending signal raised after assignment so cleanup sees the child; no inherited blocked signal mask; tested. Tool-scoped independent review (04-34, 0d9612130092): CLOSED tests/libretro/retroarch_smoke.py:664-704 defers signals around Popen, assignment and the PID record without a signal mask, and raises after assignment; tests at tests/libretro/test_retroarch_smoke.py:1195-1248. | closed |
| T-04-67 | Elevation of privilege | SIGKILL escalation on a surviving frontend | medium | mitigate | Escalate only on the recorded PID's own group (`getpgid(recorded) == recorded`) while it is listed by `pgrep -x RetroArch`; never unrecorded PIDs; tested for the unrecorded and non-leader cases. Tool-scoped independent review (04-34, 0d9612130092): OPEN tools/verify_playable.py:565-574 `_recorded_listed` returns True when `pgrep` fails for the whole grace period, so :594 escalates to SIGKILL without `pgrep -x RetroArch` ever confirming the recorded PID is listed. | open |
| T-04-SC (04-32) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-34, 0d9612130092): CLOSED No package-manager command in tools/, tests/, CMakeLists.txt or .github/workflows; imports are standard library. | closed |
| T-04-SC (04-33) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-34, 0d9612130092): CLOSED No new non-standard import in the qualification path (tools/*.py, tests/tools/*.py). | closed |
| T-04-SC (04-34) | Tampering | npm/pip/cargo installs | high | mitigate | No package or dependency added; only tracked code, the Python standard library and the toolchain. Tool-scoped independent review (04-34, 0d9612130092): CLOSED tests/tools/test_independent_review.py:7-19 is standard library plus the tracked module. | closed |

## Threat Flags

| Flag | Source | Audit note |
|------|--------|------------|
| `threat_flag: native-module-load` | 04-06 SUMMARY, `CMakeLists.txt` | Mapped to T-04-16, frontend process/core evidence. The pinned RetroArch process exited `-6` before a screenshot, so actual loading remains unknown; this security review does not claim HOST-02 acceptance. |

## Accepted Risks Log

| Risk | Asset and boundary | Rationale | Invalidated by | Owner / review |
|------|--------------------|-----------|----------------|----------------|
| T-04-44 | Raw logs, `CMakeCache.txt` and build trees in ignored `build/playable-qualification/` on the qualification host | Local-only and git-ignored; no CI job, release or tracked file reads it; public sinks (receipt, stdout, tracked summary) fail closed instead. Accepted by the project maintainer on 2026-10-10 (D-GAP-02, Phase 04 gap planning; final, register status accepted; the contained review verdict is evidence only) | Any CI upload, release bundle, copied attachment or new sink that reads the run directory | Project maintainer; review at milestone shipping or when a sink is added |
| T-04-52 | `--check-docs` in a source archive without `.git` | Accepted by the project maintainer on 2026-10-10 (D-GAP-02, Phase 04 gap planning; final, register status accepted; the contained review verdict is evidence only): fail closed by design, documented in the guide | A mode that records evidence without a repository | Project maintainer |
| T-04-55 | Pre-launch refusal when a user RetroArch instance is open | Accepted by the project maintainer on 2026-10-10 (D-GAP-02, Phase 04 gap planning; final, register status accepted; the contained review verdict is evidence only): single-instance rule, reason named and documented | Any change that touches or stacks a user instance | Project maintainer |
| T-04-60 | Bare generic account name in public output under GitHub Actions | Accepted by the project maintainer on 2026-10-10 (D-GAP-02, Phase 04 gap planning; final, register status accepted; the contained review verdict is evidence only): not a personal identifier; full home paths still rejected; documented in docs/testing.md | Any hosted runner whose account name is personal, or any non-GitHub CI needing the same skip | Project maintainer |

Accepted 2026-10-10 under the user's delegated decision (verify-work Test 4), after a four-way independent review (security audit, claim-gate analysis, provenance-cost analysis, primary-source research).

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-07 | 18 | 18 | 0 | gsd-security-auditor |
| 2026-10-08 | 36 | 32 | 4 | gsd-security-auditor |
| 2026-10-08 | 49 | 45 | 4 | gsd-security-auditor |
| 2026-10-08 | 54 | 49 | 5 | gsd-security-auditor |
| 2026-10-08 | 59 | 53 | 6 | gsd-security-auditor |
| 2026-10-10 | 69 | 56 | 12 | gsd-security-auditor (headless separate session, 04-23) |
| 2026-10-10 | 89 | 56 | 33 | independent tool-scoped headless session (04-31), halted: containment-violation, all reviewed IDs recorded open |
| 2026-10-10 | 99 | 90 | 9 | independent tool-scoped headless session (04-34) |

## Sign-Off

- [x] All declared threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [ ] `threats_open: 0` not confirmed: the 04-23 independent review reopened rows (threats_open 6)
- [ ] `status: verified` withdrawn; status is open pending repair

**Approval:** withdrawn 2026-10-10 by the independent 04-23 review; the earlier delegated verification (56f4fbd) rested on self-attestation. Earlier 2026-10-08 direction kept the four high threats open until a durable mitigation existed.

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

| Audited Threat | ASVS L1 result | Current evidence |
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

## Plan 04-20 ASVS L1 Audit — 2026-10-08

The phase register contains 59 plan-authored threats: 53 closed and 6 open. The four directed high-severity disclosure threats T-04-11, T-04-15, T-04-18, and T-04-20 remain blockers. T-04-34 and T-04-38 are medium/open and do not increase `threats_open` under `block_on: high`; no risk was accepted. The Plan 04-20 summary preserves the earlier sanitizer review path and revision, but the evidence-map checker does not enforce review paths or revisions. The post-execution code review also found that the uncertainty matcher accepts ordinary output claims; this remains open under T-04-34. T-04-39 is closed by the live denominator comparison and T-04-40 by the standard-library-only source closure. The `native-module-load` summary flag maps to T-04-16. HOST-02 and frontend QUAL-03 remain Pending/unknown because actual pinned RetroArch behavior was not observed.

## Security Audit 2026-10-08

| Metric | Count |
|---|---|
| Threats found | 56 |
| Closed | 51 |
| Open | 5 |

## Security Audit 2026-10-08

| Metric | Count |
|---|---|
| Threats found | 59 |
| Closed | 53 |
| Open | 6 |

## Security Audit 2026-10-09

| Metric | Count |
|---|---|
| Threats found | 63 |
| Closed | 57 |
| Open | 6 |
| Blocking open (block_on=high) | 4 |

## Security Audit 2026-10-09 — post-review WR-09

| Metric | Count |
|---|---|
| Threats found | 63 |
| Closed | 56 |
| Open | 7 |
| Blocking open (block_on=high) | 4 |

The configured ASVS L1 audit verified the Plan 04-21 additions before the phase-wide code review. That review then reproduced WR-09: the review provenance check accepts an unsupported extra path claim. T-04-43 is therefore reopened at medium severity; T-04-34 and T-04-38 plus the four directed high-severity threats remain open. No risk was accepted. The high-severity blocking count remains four, and Phase 04 remains blocked.

## Security Audit — post-review WR-09 2026-10-09

| Metric | Count |
|---|---|
| Threats found | 63 |
| Closed | 56 |
| Open | 7 |
| Blocking open (block_on=high) | 4 |

## Security Audit 2026-10-10 — disposition by delegated decision

| Metric | Count |
|---|---|
| Threats found | 64 |
| Closed | 63 |
| Accepted | 1 |
| Open | 0 |
| Blocking open (block_on=high) | 0 |

An independent adversarial audit at 6f91a7e reproduced bypasses of both regex sanitizers (CMake slashless object paths, word or dot prefixes, percent and JSON escaping, case, `/home`, `/var/tmp`, Windows and fullwidth separators). c75f577 replaces them with exact-root redaction plus a fail-closed scan at every public sink and adds a regression for each bypass class; T-04-11, T-04-15, T-04-18 and T-04-20 close on that evidence. Raw run-directory logs cannot be made publishable and are accepted as medium T-04-44 with explicit invalidation triggers. T-04-34 closes because status is now generated from bound receipt evidence rather than prose; T-04-38 and T-04-43 close with the retired evidence-map checker. `tests/tools/check_security_register.py` (CTest `planning_security_register`) now enforces that `threats_open` equals open rows at `block_on`.

## Security Audit — independent post-c75f577 review (04-23)

Reviewed revision: `aaf3f093ab0fe4dcff453885af3352b9a400196a` (git archive, `.planning` excluded). Route: headless `claude -p --agent gsd-security-auditor` (Claude Code 2.1.296) in a separate context, working directory a scratch extraction, read-and-probe only. Containment: the effective tool list was the agent frontmatter list (Read, Bash, Glob, Grep, Skill), so Bash was unscoped; no permission denials were recorded; no tool call ran subprocess, osascript or git -C, and the only Read calls were under the scratch extraction. Because Bash was unscoped, the plan containment rule treats every verdict as OPEN; the reviewer's own verdict set was 15 OPEN and 1 CLOSED (T-04-SC). Reviewer-raw verdicts:

- T-04-11: OPEN, printed-output leaks (raw OSError path, runner None traceback, alternate separator forms)
- T-04-15: OPEN, receipt sanitize() skips dict keys; scan runs on ensure_ascii JSON
- T-04-18: OPEN, public_json() passes dash-mangled and U+2215 forms; decode_png errors bypass it
- T-04-20: OPEN, both pipelines pass dash-mangled, U+2215, double-percent and HFS forms
- T-04-34: OPEN, forged summary passes check_docs without a .git directory
- T-04-38: OPEN, no phase-04 gate checks review provenance
- T-04-43: OPEN, nonexistent review path accepted in the crosswalk
- T-04-45: OPEN, fullwidth-separator home path accepted into the summary and guide block
- T-04-46: OPEN, ancestry and inventory checks skipped without .git
- T-04-47: OPEN, outer timeout can orphan RetroArch; no pre-launch instance check
- T-04-48: OPEN, register checker misses commented/duplicate frontmatter keys and later tables
- T-04-SC (04-23): CLOSED by the reviewer, recorded OPEN by the containment rule
- WR-01, WR-06, WR-08: OPEN, appended success prose outside the generated block passes the docs gate
- WR-09: OPEN, nonexistent extra review path accepted

Next step: `/gsd-plan-phase 04 --gaps --ws first-playable-game` to plan bounded repairs, then a fresh separate review.

## Security Audit — tool-scoped independent review (04-31)

Reviewed revision: `7615dd911678` (git archive, .planning excluded). Command shape: headless `claude -p --restricted --tools Read,Grep,Glob --strict-mcp-config --append-system-prompt-file <verdict-only system prompt> --output-format stream-json --verbose`, run in a scratch extraction with the prompt on stdin (Claude Code 2.1.296).

Containment result: NOT contained. The session init listed only Glob, Grep and Read and its cwd matched the scratch extraction, and every tool call was Read, Grep or Glob, but one Grep or Read call named the scratch directory itself as an absolute path; the mechanical gate requires absolute paths to resolve strictly under the scratch directory, so the run is a halt, `REVIEW HALTED: containment-violation`. No verdict is transcribed, and every one of the 33 threat IDs (including accepted T-04-44) is recorded open. The raw stream stays in the ignored run directory.

Next step: `/gsd-secure-phase 04 --ws first-playable-game`.

## Security Audit — tool-scoped independent review (04-34)

Reviewed revision: `0d9612130092` (git archive, .planning excluded). Command shape: headless `claude -p --restricted --tools Read,Grep,Glob --strict-mcp-config --append-system-prompt-file <verdict-only system prompt> --output-format stream-json --verbose`, run in a scratch extraction with the prompt on stdin (Claude Code 2.1.296). Scope: 77 IDs (43 threats, 34 findings).

Containment result: contained (`tools/independent_review.py gate` printed `contained`). The init listed only Glob, Grep and Read, its cwd matched the scratch extraction, every tool call was Read, Grep or Glob, and no permission denials were recorded. `preflight` printed `scratch-ok` before launch.

Containment boundary (D-GAP-01): a path equal to the scratch directory counts as contained. The user decided this at Phase 04 gap planning on 2026-10-10, after the 04-31 halt. It corrects an over-strict boundary and does not relax the gate for green. No other 04-31 condition is relaxed. 04-32 added strengthenings under the user-approved simple rule (any `..` segment is not contained, an absolute pattern's literal prefix must be contained, and `preflight` refuses a scratch tree with an external symlink), which a reviewer following the no-`..`, scratch-relative prompt rule never trips.

Maintainer acceptance (D-GAP-02): T-04-44, T-04-52, T-04-55 and T-04-60 are accepted by the project maintainer on 2026-10-10 (final); their contained verdicts are recorded as evidence only.

Verdicts (34 threats CLOSED, 9 threats OPEN):

- T-04-11: OPEN, tools/private_paths.py:109-115 applies NFKC one character at a time, so a decomposed (NFD) non-ASCII root never composes and does not match its NFC form (or the reverse). Both root matching and the username-token check miss it. The `--clean --check-docs` repair itself holds (tools/verify_playable.py:1547-1556).
- T-04-15: OPEN, tools/private_paths.py:109-115 per-character NFKC leaves an NFC/NFD form of a runtime root undetected, so the receipt scan in tools/verify_playable.py:1313 passes it. The CMakeFiles omission (tools/verify_playable.py:1278) and the fail-closed receipt test are present.
- T-04-18: OPEN, tools/private_paths.py:109-115 has the same NFD/NFC gap, which also reaches smoke `public_json` (tests/libretro/retroarch_smoke.py:115-123). Screenshots stay in the TemporaryDirectory (tests/libretro/retroarch_smoke.py:901).
- T-04-20: OPEN, tools/private_paths.py:109-115: not every form of a root is caught (decomposed Unicode). The newline-suffix tests and start-only generic matching are present (tools/private_paths.py:205-220).
- T-04-34: CLOSED, tools/verify_playable.py:835-876 checks the exact lane set, both digests, the rightward marker move, os, core and mapping; :938-944 re-archives the revision and compares the inventory digest; the forgery mutations are at tests/tools/test_verify_playable.py:766-805.
- T-04-38: CLOSED, tools/verify_playable.py:1169-1193 requires every non-open disposition to cite a revision that resolves and is a committed ancestor; tests at tests/tools/test_verify_playable.py:1038-1080.
- T-04-43: CLOSED, tools/verify_playable.py:1137-1144 rejects nonexistent, unreviewed and `..` scope paths; tests at tests/tools/test_verify_playable.py:985-1000.
- T-04-44: CLOSED, .gitignore:9 ignores /build/. The only reference is OUTPUT in tools/verify_playable.py:37; no file under .github/workflows reads it; docs/first-playable-build.md:82 declares the run directory private.
- T-04-45: CLOSED, tools/verify_playable.py:872-875 scans the summary and raises RuntimeError on a hit; tools/private_paths.py:286-289 turns an unserializable structure into PrivatePathError("unscannable-value"), tested at tests/tools/test_private_paths.py:265-270.
- T-04-46: CLOSED, tools/verify_playable.py:1385 archives HEAD; :922-944 checks ancestry and re-archives the digest; main passes repository=ROOT, head=snapshot.commit (:1544).
- T-04-47: CLOSED, tools/verify_playable.py:614-648 runs `pgrep -x RetroArch` before and after the lane; tests/libretro/retroarch_smoke.py:707-711 refuses a stacked launch; there is no retry loop.
- T-04-48: CLOSED, tools/independent_review.py:194-213 makes a zero, duplicate, malformed or wrong-vocabulary verdict OPEN; tests/tools/check_security_register.py:156-158 enforces threats_open equal to the blocking count.
- T-04-49: CLOSED, tools/private_paths.py:213-219 matches generic roots only at path starts; the benign list including `docs/tmp/notes` and `public_users_list` is at tests/tools/test_private_paths.py:177-183.
- T-04-50: CLOSED, tools/private_paths.py:57,100-106 bounds percent decoding to 8 passes; `_substitute` (:67-80) is a single linear pass with an index map.
- T-04-51: CLOSED, tests/tools/check_security_register.py:45,197-199 validates the workstream name before the glob at :206; the `../x` mutation is at tests/tools/test_check_security_register.py:104.
- T-04-52: CLOSED, tools/verify_playable.py:924-925 fails closed when no repository exists; the limit is documented at docs/first-playable-build.md:82 and tested at tests/tools/test_verify_playable.py:917-926.
- T-04-53: CLOSED, tools/verify_playable.py:986-1035 validates and scans first, writes temp files, restores originals on a failed replace and writes the guide last; tests at tests/tools/test_verify_playable.py:1179-1214.
- T-04-54: CLOSED, tools/verify_playable.py:527-545 keeps the leader unreaped (WNOWAIT) while it sends group signals; :583-599 signals only the recorded PID's own group; tests/libretro/retroarch_smoke.py:648-661 never signals after reaping.
- T-04-55: CLOSED, tools/verify_playable.py:617-619 refuses with the named reason `retroarch-instance-already-running`; documented at docs/first-playable-build.md:52.
- T-04-56: OPEN, tests/tools/check_runtime_storage.py:35 `MACHO_LINE` only accepts `non-external|external`. Mach-O `nm -m` lines for `private external` (the hidden-visibility globals glueyneo_runtime_static is built with, CMakeLists.txt:167), `weak external` and unlinked `(common)` symbols are never parsed, so writable globals pass unaudited on macOS.
- T-04-57: CLOSED, CMakeLists.txt:885-905 registers the test only when the workstream exists and makes an explicit missing workstream a FATAL_ERROR; the mutation suite is unconditional (:906-907).
- T-04-58: CLOSED, tests/consumers/check_package.py:312 parses the full path with `(.+?) \(compatibility version`; :334-342 applies the macOS system allowlist; tests at tests/consumers/test_check_package.py:50-67.
- T-04-59: CLOSED, tools/private_paths.py:242-243 skips the token only for a service name under GITHUB_ACTIONS; tests at tests/tools/test_private_paths.py:197-226.
- T-04-60: CLOSED, tools/private_paths.py:24-30,242 implement the skip as described; the residual and trigger are documented at docs/testing.md:206-211; no defect contradicts the rationale.
- T-04-61: OPEN, tools/independent_review.py:78-100 does not handle `~`: `path_contained("~", ...)` joins it under cwd and calls it contained, but the Read/Glob/Grep tools expand `~` to the home directory. tests/tools/test_independent_review.py has no tilde case.
- T-04-62: OPEN, tests/tools/check_security_register.py:49 `HEADER` requires an exact `Threat ID` cell and a trailing `|`. A second register table whose header has no trailing pipe (or a re-cased `Threat Id`) is skipped silently, and its open high rows are not counted.
- T-04-63: CLOSED, tests/tools/check_security_register.py:88-91 rejects a weaker workstream value; the PASS line names the threshold and source (:236-237); tests at tests/tools/test_check_security_register.py:279-311.
- T-04-64: CLOSED, tests/tools/check_security_register.py:211-214,235 requires exactly one register and prints `scope: phase NN`; documented at docs/testing.md:123,141-147.
- T-04-65: OPEN, tools/independent_review.py:447-455 catches only InputError. A malformed stream (a non-dict `message` at :119, or unhashable `tools`/`name` at :156,:162) and argparse errors print an unscanned traceback or usage text that carries absolute paths.
- T-04-66: CLOSED, tests/libretro/retroarch_smoke.py:664-704 defers signals around Popen, assignment and the PID record without a signal mask, and raises after assignment; tests at tests/libretro/test_retroarch_smoke.py:1195-1248.
- T-04-67: OPEN, tools/verify_playable.py:565-574 `_recorded_listed` returns True when `pgrep` fails for the whole grace period, so :594 escalates to SIGKILL without `pgrep -x RetroArch` ever confirming the recorded PID is listed.
- T-04-SC (04-23): CLOSED, No package installs anywhere in tools/, tests/, CMakeLists.txt or .github; all imports in tools/*.py and tests/tools/*.py are standard library.
- T-04-SC (04-24): CLOSED, tools/private_paths.py:41-47 imports only json, os, pathlib, re, tempfile, unicodedata and typing.
- T-04-SC (04-25): CLOSED, tests/tools/check_security_register.py:38-41 imports only json, pathlib, re and sys.
- T-04-SC (04-26): CLOSED, tools/verify_playable.py:11-34 imports only the standard library and the tracked private_paths.
- T-04-SC (04-27): CLOSED, tools/verify_playable.py and tests/tools/test_verify_playable.py:4-24 use only the standard library and tracked code.
- T-04-SC (04-28): CLOSED, tests/libretro/retroarch_smoke.py:6-24 imports signal, os, subprocess, zlib and other standard modules, plus tracked private_paths.
- T-04-SC (04-29): CLOSED, tests/tools/check_runtime_storage.py:23-28 is standard library only; CMakeLists.txt:910-912 uses CMAKE_NM.
- T-04-SC (04-30): CLOSED, tests/consumers/check_package.py:6-17 is standard library only and calls the system `otool` (:307).
- T-04-SC (04-31): CLOSED, tools/independent_review.py:41-49 is standard library plus tracked private_paths.
- T-04-SC (04-32): CLOSED, No package-manager command in tools/, tests/, CMakeLists.txt or .github/workflows; imports are standard library.
- T-04-SC (04-33): CLOSED, No new non-standard import in the qualification path (tools/*.py, tests/tools/*.py).
- T-04-SC (04-34): CLOSED, tests/tools/test_independent_review.py:7-19 is standard library plus the tracked module.
- CR-01: FIXED, tools/private_paths.py:95-141 canonicalizes escapes, percent decoding to a fixpoint and separator runs; the full table, including a non-home root, is tested at tests/tools/test_private_paths.py:124-162.
- CR-02: FIXED, tools/private_paths.py:59,98-99 decodes `\uXXXX`; :287 serializes with ensure_ascii=False; JSON-encoded bypasses are tested at tests/tools/test_private_paths.py:102-104,159-175.
- CR-03: FIXED, tools/verify_playable.py:922-936 fails without a repository and binds `--clean` runs via repository=ROOT (:1544) under a clean env and timeout; tests at tests/tools/test_verify_playable.py:917-960.
- CR-04: FIXED, tools/verify_playable.py:825-829,948-954,1213-1215 reject claims outside the block; the stale 706516 prose is gone from docs/first-playable-build.md; tests at tests/tools/test_verify_playable.py:1086-1119.
- CR-05: FIXED, tools/verify_playable.py:1130-1144 resolves threat IDs and paths and reports each failure separately; tests at tests/tools/test_verify_playable.py:985-1000.
- CR-06: FIXED, tests/tools/check_security_register.py:94-161 reads frontmatter only, requires one key, scans every table and splits on unescaped pipes; mutations at tests/tools/test_check_security_register.py:72-118.
- CR-07: FIXED, tools/verify_playable.py:614-648,685-693 and tests/libretro/retroarch_smoke.py:707-738 add the pre-launch refusal, process groups, signal cleanup and quit-by-PID unless ours is the sole instance; tests at tests/tools/test_verify_playable.py:641-716.
- CR-08: FIXED, tools/verify_playable.py:1501 uses `runner.lanes if runner is not None else {}`; test at tests/tools/test_verify_playable.py:1236-1248.
- CR-09: FIXED, tools/verify_playable.py:493-500,1342-1358 route errors through `emit_error` and catch OSError/UnicodeError; tests at tests/tools/test_verify_playable.py:1250-1279.
- WR-01: FIXED, tools/verify_playable.py:986-1035 validates all targets before temp-and-replace; tests at tests/tools/test_verify_playable.py:1153-1177.
- WR-02: FIXED, tools/verify_playable.py:844-868 type-checks retroarch, os, core_sha256, input_mapping and rejects bool markers; mutations at tests/tools/test_verify_playable.py:791-796.
- WR-03: FIXED, tools/verify_playable.py:685-693,527-545 use Popen(start_new_session) and kill the group while keeping partial output; tests at tests/tools/test_verify_playable.py:505-566.
- WR-04: FIXED, tests/libretro/retroarch_smoke.py:215-241 requires IEND plus a stable size/mtime; :331-377 wraps decode errors and bounds inflation; tests at tests/libretro/test_retroarch_smoke.py:628-676.
- WR-05: FIXED, tests/libretro/retroarch_smoke.py:875-877 checks st_size==602 before reading; test at tests/libretro/test_retroarch_smoke.py:678.
- WR-06: FIXED, tools/private_paths.py:213-219 (start-only generic roots), :242-243 (service account) and :172-175,236-239 (guarded Path.home); tests at tests/tools/test_private_paths.py:177-230.
- WR-07: FIXED, CMakeLists.txt:883-905 registers conditionally from a variable; tests/tools/check_security_register.py:54-91,197 validate severity and name without tracebacks; tests at tests/tools/test_check_security_register.py:88-178.
- WR-08: OPEN, tests/tools/check_runtime_storage.py:35 never parses Mach-O `private external`, `weak external` or `(common)` lines, so hidden-visibility mutable globals in the duplicated runtime (CMakeLists.txt:160-168) go unaudited on macOS. The guard's limits are documented in place (CMakeLists.txt:929-935).
- WR-09: FIXED, tools/verify_playable.py:927-930,1155-1158 run git with clean_environment() and a timeout.
- WR-10: FIXED, tests/tools/test_verify_playable.py:966-974 asserts the mutation changed the text and checks a target-specific error regex (:985-1018).
- WR-11: OPEN, tools/verify_playable.py:1048-1058 no tracked code parses or rejects duplicate or malformed review revision keys, and `_reviewed_paths` keeps the first `files_reviewed_list` while ignoring duplicates. No regression test exists in tests/tools/test_verify_playable.py.
- IN-01: FIXED, docs/first-playable-build.md:84-96 has a single historical section with no 706516 or Plan 04-08 text; pinned by tests/tools/test_verify_playable.py:1117-1119.
- IN-02: FIXED, tests/libretro/retroarch_smoke.py:89-101 no longer has the `cursor > len` check, and validate_inputs (:846-848) only does the equality check; tests at tests/libretro/test_retroarch_smoke.py:367-372.
- IN-03: FIXED, tests/consumers/check_package.py:312 uses a regex for otool paths, :448 has the formatting fixed, :334-342 adds the system allowlist; tests at tests/consumers/test_check_package.py:50-67.
- IN-04: FIXED, tests/tools/test_private_paths.py:141-183 (JSON forms, non-home root), tests/tools/test_check_security_register.py:72-118 and tests/tools/test_verify_playable.py:917-1248 cover each listed gap.
- GWR-01: FIXED, tests/tools/check_security_register.py:127-129 errors on a table lacking Severity or Status; mutation at tests/tools/test_check_security_register.py:181-217.
- GWR-02: FIXED, tests/tools/check_runtime_storage.py:31-37,92-104 add Cc/Ss, the `__thread_*` sections, a zero-parse failure and skip on empty nm; tests at tests/tools/test_check_runtime_storage.py:62-121. The Mach-O private-external gap is a separate defect, recorded under T-04-56.
- GWR-03: FIXED, CMakeLists.txt:883-905 renames the test to `_consistency` and fails configure on an explicit missing workstream; `--require-closed` exists (tests/tools/check_security_register.py:228-233); the local config cannot weaken the threshold (:88-89), documented at docs/testing.md:98-105.
- GWR-04: FIXED, tools/verify_playable.py:514-545 signals only before reaping, using WNOWAIT; :577-599 escalates and reports; tests at tests/tools/test_verify_playable.py:568-594,664-685.
- GWR-05: FIXED, tests/libretro/retroarch_smoke.py:664-704 defers signals in the launch window; :612-661 sweeps the group of an exited, unreaped leader; tests at tests/libretro/test_retroarch_smoke.py:1195-1346.
- GWR-06: FIXED, tools/verify_playable.py:977-1035 restores originals, writes the guide last and documents the crash limit; tests at tests/tools/test_verify_playable.py:1179-1214.
- GIN-01: FIXED, tools/private_paths.py:264-266 documents the accepted fail-closed overmatch, pinned by tests/tools/test_private_paths.py:272-278.
- GIN-02: FIXED, tools/private_paths.py:286-289 raises PrivatePathError("unscannable-value"); test at tests/tools/test_private_paths.py:265-270.
- GIN-03: FIXED, tools/verify_playable.py:1139-1140 rejects `..`, and tests/tools/check_security_register.py:50 accepts the quoted status; tests at tests/tools/test_verify_playable.py:997-1000 and tests/tools/test_check_security_register.py:99-100.
- GIN-04: FIXED, docs/first-playable-build.md:82 states the 7-to-40 hex limit and that other prose is not machine-checked; pinned by tests/tools/test_verify_playable.py:1130-1136.
