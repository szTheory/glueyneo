# Phase 05 Validation Map

Phase 05 advanced through one three-task execution plan. The results below are
current-revision evidence; they do not change Phase 04's `gaps_found` verdict,
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

## Frontend and security boundaries

The direct pinned RetroArch launch remains manual-only/unknown; no unchanged
launch context was retried. Phase 04 acceptance and its threat dispositions
remain exactly as recorded there. Phase 05's private media identity remains
unqualified and the local report is ignored.
