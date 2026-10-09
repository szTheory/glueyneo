# Phase 05 Validation Map

Phase 05 validation accumulates evidence across its execution plans. The results
below do not change Phase 04's `gaps_found` verdict,
HOST-02/frontend QUAL-03 unknown/manual-only status, or its seven open threat
rows.

| Requirement | Status | Evidence and command | Limit / remaining work |
|---|---|---|---|
| MEDIA-02 | Complete | `ctest --preset sdk-debug -R '^(mvs_synthetic_trace|mvs_media_contract)$' --output-on-failure`; versioned `gn_mvs_manifest`, documented MSX-shaped region map, explicit layout/size limits, owned copies, transform and failure-recovery assertions | The contract describes a structural MSX profile. It does not authenticate a selected cartridge or BIOS revision. |
| MEDIA-03 | Pending | `ctest --preset sdk-debug -R '^(mvs_import_contract|mvs_import_mutation|mvs_callback_contract|libretro_callback)$' --output-on-failure`; `python3 -m unittest discover -s tests/mvs -p 'test_*.py' -v`; local-only qualification | Synthetic canonical role archives pass. Local qualification reports `no_supported_role_bundle_archive` at `archive_to_region_mapping`; the raw game/BIOS archive mapping and directly observed user import/load flow remain unproven. |
| MEDIA-04 | Pending | `mvs_import_mutation`, `mvs_media_contract`, and the public synthetic importer suite exercise distinct structural errors, limits, CRC checks, allocation failure, valid recovery, and callback reload | Same-sized but incorrect cartridge/BIOS content is not identified. The selected profile identity is therefore unqualified. |
| GAME-02 | Pending | `ctest --preset sdk-debug -R '^(mvs_synthetic_trace|mvs_boot_checkpoint)$' --output-on-failure` proves a synthetic guest sentinel; the ignored local qualification command records its first blocker | No selected guest archive was imported, so no selected guest instruction/event or attract/start transition was observed. Next dependency: map supported game and BIOS archives to the normalized MVS region contract. |

## Executed verification

- `cmake --preset sdk-debug && cmake --build --preset sdk-debug && ctest --preset sdk-debug --output-on-failure` — passed, 41/41.
- `cmake --preset sdk-asan-ubsan && cmake --build --preset sdk-asan-ubsan --target mvs_test mvs_importer && ctest --preset sdk-asan-ubsan -R '^(mvs_synthetic_trace|mvs_media_contract|mvs_import_contract|mvs_import_mutation|mvs_callback_contract|mvs_boot_checkpoint|mvs_import_fuzz_corpus)$' --output-on-failure` — passed, 7/7.
- `python3 -m unittest discover -s tests/mvs -p 'test_*.py' -v` — passed, including malformed local extra-field and decoy EOCD-in-comment coverage.
- `python3 tools/mvs/qualify_local_boot.py --input-root local/roms --report local/qualification/phase05.json` — completed with a generic unsupported-bundle status. Both paths are ignored; no private identity or derived data entered tracked files.
- `git diff --check` — passed.
- Static/shared installed-consumer and documentation checks ran within full CTest. The first pass exposed missing zlib staging and an outdated public export allowlist; both test harness issues were fixed, then the full 41-test suite passed.

### Plan 05-02 foundation evidence

- `cmake --preset sdk-debug && cmake --build --preset sdk-debug && ctest --preset sdk-debug --output-on-failure --no-tests=error` — passed, 41/41. The exact MVS label contains seven named tests.
- `cmake --preset sdk-asan-ubsan && cmake --build build/sdk-asan-ubsan --target mvs_qualify mvs_test mvs_importer mvs_import_fuzz && ctest --test-dir build/sdk-asan-ubsan -L mvs --output-on-failure --no-tests=error` — passed, 7/7 with AddressSanitizer and UndefinedBehaviorSanitizer. The full sanitizer preset build also attempted unrelated package-consumer targets and stopped because the Unity static archive's sanitizer runtime symbols were not linked into a consumer executable; those unrelated targets were excluded from the focused MVS build.
- `python3 tools/verify_sdk.py --suite matrix` — passed locally. The focused MVS matrix lane recorded seven exact tests (`mvs_boot_checkpoint`, `mvs_callback_contract`, `mvs_import_contract`, `mvs_import_fuzz_corpus`, `mvs_import_mutation`, `mvs_media_contract`, `mvs_synthetic_trace`) on source revision `492f51f30ae43f33af431c978af91991b1240e0e`; relevant-source SHA-256 `105deb95d946a075ef1586553271579f3983b4e3533062a72a108fb1bf9c8b82`; CTest output SHA-256 `b0f6b89a753b2e11731255bed11cd7db3a31c0a32ad824b3622ef1820ca34218`. The local hosted-platform lane is `unknown` because this machine is not a GitHub-hosted runner; this is not hosted CI evidence.
- `python3 tests/sdk/test_matrix_evidence.py` — passed, including omission, zero/renamed inventory, failed outcome, and stale-source controls.
- `python3 tools/mvs/qualify_local_boot.py` — completed with `no_supported_role_bundle_archive`; no supported private game/BIOS pair was present. Its ignored report records no private identity. This does not establish selected-game compatibility or direct boot behavior.
- `python3 -m py_compile tools/mvs/qualify_local_boot.py tests/mvs/test_mvs_qualification.py` — passed.
- The configured post-wave `owned-debug` gate initially passed 53/54 tests: `owned_cpu_inventory_check` rejected the recorded `CMakeLists.txt` digest, which predated Phase 05-01's MVS target wiring. `python3 tools/owned_cpu/inventory.py refresh-manifest` changed only that exact source identity; `python3 tools/owned_cpu/inventory.py check --build-dir build/owned-debug` then passed, and the full `ctest --preset owned-debug` rerun passed 54/54. Historical acceptance receipts and budget ledgers were not rewritten.

Plan 05-02 remains an intermediate foundation: it claims neither G-05-3 nor
G-05-5 resolved. Plan 05-03 must provide the selected guest's direct attract/start
evidence and hosted seven-test receipt before either gap can close.

## Frontend and security boundaries

The direct pinned RetroArch launch remains manual-only/unknown; no unchanged
launch context was retried. Phase 04 acceptance and its threat dispositions
remain exactly as recorded there. Phase 05's private media identity remains
unqualified and the local report is ignored.
