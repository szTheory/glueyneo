# Phase 05 Validation Map

This map combines earlier phase evidence with the later Plan 05-06 candidate
receipt. The dated Plan 05-01 through 05-05 entries below are historical
snapshots; statements in those entries that G-05-5 has no hosted receipt are
superseded by the exact-candidate evidence recorded at the end of this map.

## Plan 05-04 checkpoint investigation — 2026-10-09

- The existing evidence does not provide an independently observed selected
  attract/start state or a source-qualified guest-write predicate. The only
  selected native result is `guest_instruction_budget_exhausted` after guest
  execution; the current sanitized local report continues to classify the
  frontend observation as `manual-only-unknown`. The observed device-state
  counters in the prior bounded run are not a guest-write transition.
- The required independent observation is unavailable in this checkout. The
  earlier pinned RetroArch launch aborted before a frame in an unchanged app
  launch context. Per the plan gate and project state, that app is not launched
  again until a native checkpoint passes and the launch context materially
  changes. No alternate direct observation of the selected configuration is
  recorded. Without that observation, any candidate derived from private
  program bytes would lack the required independent corroboration; no watched
  address, value, sequence, or acceptance predicate was chosen.
- `cmake --build --preset sdk-debug --target mvs_qualify mvs_test` — passed
  (no rebuild required). `ctest --preset sdk-debug -R
  '^(mvs_boot_checkpoint|mvs_synthetic_trace)$' --output-on-failure
  --no-tests=error` — passed, 2/2. These existing synthetic tests do not
  qualify the selected program.

## Plan 05-04 bounded selected-run result — 2026-10-09

- `cmake --preset sdk-debug && cmake --build --preset sdk-debug --target
  mvs_qualify mvs_test && ctest --preset sdk-debug -R '^mvs_' --output-on-failure
  --no-tests=error` — passed, 7/7.
- `python3 tools/mvs/qualify_local_boot.py --input-root local/roms --report
  local/qualification/phase05.json` — exited 1; generic status
  `guest_instruction_budget_exhausted`, `guest_executed=true`, with no
  checkpoint. Private input, addresses, hashes, traces, and profile details
  remain ignored. No selected RetroArch app launch was attempted.
- G-05-3 remains open. MEDIA-03, MEDIA-04, and GAME-02 remain Pending. No
  independent predicate or behavior review was possible because no predicate
  or behavior change was accepted. Phase 04 status and artifacts were not
  changed.

Phase 05 validation accumulates evidence across its execution plans. The results
below do not change Phase 04's `gaps_found` verdict,
HOST-02/frontend QUAL-03 unknown/manual-only status, or its seven open threat
rows.

| Requirement | Status | Evidence and command | Limit / remaining work |
|---|---|---|---|
| MEDIA-02 | Complete | `ctest --preset sdk-debug -R '^(mvs_synthetic_trace|mvs_media_contract)$' --output-on-failure`; versioned `gn_mvs_manifest`, documented MSX-shaped region map, explicit layout/size limits, owned copies, transform and failure-recovery assertions | The contract describes a structural MSX profile. It does not authenticate a selected cartridge or BIOS revision. |
| MEDIA-03 | Pending | `ctest --preset sdk-debug -R '^(mvs_import_contract|mvs_import_mutation|mvs_callback_contract|libretro_callback)$' --output-on-failure`; public synthetic importer suite; local-only qualification | Synthetic canonical role archives pass and the configured pair imports to the native runner. Directly observed user import/load flow remains unproven. |
| MEDIA-04 | Pending | `mvs_import_mutation`, `mvs_media_contract`, and the public synthetic importer suite exercise distinct structural errors, limits, CRC checks, allocation failure, valid recovery, and callback reload | Same-sized but incorrect cartridge/BIOS content is not identified. The selected profile identity is therefore unqualified. |
| GAME-02 | Pending | `ctest --preset sdk-debug -R '^(mvs_synthetic_trace|mvs_boot_checkpoint)$' --output-on-failure` proves a synthetic guest sentinel; the ignored local qualification command records a sanitized native run outcome and per-chunk state-transition profile | The selected guest executes but the latest run exhausted its bounded 256-chunk instruction budget without attract/start or a surfaced unsupported event. Device-state activity does not establish an acceptance checkpoint. |

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

## Plan 05-03 current-revision evidence

- The local qualifier was rerun on 2026-10-09 and reported
  `no_supported_role_bundle_archive` at `archive_to_region_mapping` before the
  BIOS-extra compatibility adjustment. The selected guest did not execute on
  that first run; no CPU, bank, protection, IRQ, or sound behavior was inferred
  or changed from a private trace.
- The pinned RetroArch smoke now has a synthetic GNMV structure-validation
  branch alongside the unchanged exact GNFX fixture identity gate. Its GUI-free
  tests cover a generated valid six-region bundle, malformed and missing
  bundle rejection before launch, and omission of content digest/path from the
  selected-content identity record.
- `python3 tests/libretro/test_retroarch_smoke.py -v` — passed, 31/31,
  including generated selected-bundle, missing, malformed, and sparse oversized
  inputs. `git diff --check` passed.
- `cmake --preset sdk-debug && cmake --build --preset sdk-debug && ctest
  --preset sdk-debug -R '^(mvs_|owned_)' --output-on-failure --no-tests=error`
  — passed, seven registered MVS tests.
- `cmake --build --preset sdk-asan-ubsan --target mvs_qualify mvs_test
  mvs_importer mvs_import_fuzz && ctest --test-dir build/sdk-asan-ubsan -R
  '^mvs_' --output-on-failure --no-tests=error` — passed, 7/7. The full
  sanitizer preset build remains blocked by the inherited Unity static-library
  sanitizer-runtime link failure in the unrelated YM2610 admission target.
- The ignored local qualifier wrote the generic report and exited 1 for
  `no_supported_role_bundle_archive`, as required for a nonaccepted run.
- The actual RetroArch app was not launched. The required selected guest
  attract/start precondition was not met, so the app row remains unknown; the
  earlier Phase 04 abort is not reused as a Phase 05 observation.
- G-05-3 and G-05-5 remain open. No final-SHA hosted seven-test matrix receipt
  was obtained, and no Phase 04 status or UAT resolution field was changed.

## Plan 05-03 continuation: bounded BIOS archive extras

The following continuation evidence supersedes stale 05-03 statements below
that no selected guest executed or no CPU/board behavior was added. It does not
change Phase 04 dispositions or UAT resolution fields.

- The selected importer and local classifier accept flat, safe, bounded BIOS
  extras only after ZIP metadata/extents and decompression/CRC validation. The
  selected BIOS remains exactly one pinned identity; the game archive still
  requires its exact member set. Synthetic tests cover valid extras, corrupt
  extra payloads, unsafe names, duplicates, and DEFLATE option-hint boundaries.
- The classifier checks exact EOCD end/count, central-directory consumption,
  ZIP64 rejection, local/central consistency, and extent overlap. A crafted
  invalid EOCD signature in a valid archive comment can still make Python
  conservatively reject an archive that the C importer accepts after ignoring
  that candidate. This is a classifier false negative only; importer failure
  remains fail-closed.
- Pinned Motorola/NXP sources support the observed `MOVE.B Dn,absolute-long`
  semantics and 12-clock timing (M68000 PRM §4 MOVE; MC68000 User's Manual,
  Table 9-2, p. 9-3). The private CPU bus now has an explicit byte-write
  callback. Public synthetic tests check byte width, an odd byte address,
  unchanged source register, condition flags, exact cycles, and neighboring
  byte preservation.
- The selected MVS bus maps the BIOS high mirror with MAME's documented
  `0xc00000-0xc1ffff` mapping mirrored across `0xc00000-0xcfffff`; boundary
  tests cover every mirror end, preserve the low reset/vector read, and reject
  the next unmapped window. Pinned MAME's map also leaves the low address gap
  unmapped except for its read-only vector handler. Its default unmapped-write
  callback logs and drops writes. The core follows that differential for
  low-gap byte writes only and counts them in the versioned observation. This
  is emulator-source behavior, not a physical-board claim.
- Pinned MAME documents the MVS watchdog mapping at `0x300001` mirrored by
  `0x01fffe`, and configures 3,244,030 master ticks at 24 MHz. Because the main
  CPU is master/2, the selected profile uses 1,622,015 CPU cycles per timeout.
  MAME's watchdog device reloads on reset writes and schedules a soft reset on
  expiry. Synthetic tests cover pet postponement, no-pet expiry, reset-vector
  reload, and work-RAM preservation. CPU-cycle accounting is instruction-boundary
  deterministic; physical hardware behavior remains unverified.
- The later observed `MOVE.W #<data>,absolute-long` is implemented narrowly
  from NXP/Motorola *M68000 User's Manual*, Table 9-2, p. 9-3: 20 clocks. The
  synthetic CPU vector checks one destination word write, flags/PC, exact
  elapsed cycles, and an odd-address error control.
- Focused CPU semantics pass 21/21; focused MVS/import CTest set passes 5/5.
  The latest sanitized local run executes the selected guest through its
  bounded 256-chunk cycle limit (256,000,794 cycles; 32,255,007 instructions)
  and reports `guest_instruction_budget_exhausted`. Its sanitized profile records
  140 stable chunks, 20 output/latch transition chunks, 97 video-state transition
  chunks, 17 bank-transition chunks, 6,472,496 watchdog pets, zero resets, and
  no repeated final chunk-boundary suffix. These are coarse per-chunk state
  transitions, not write counts or a guest acceptance predicate. The fetch ring
  is ignored local output; comparison against the normalized manifest buffer
  matched all 16 captured fetches and the final cursor matches the run boundary.
  No unsupported event or attract/start checkpoint surfaced.
- No actual attract/start was observed, so pinned RetroArch was not launched.
  G-05-3 remains open. No current-revision hosted receipt is available through
  a safe route; the current branch is 288 commits ahead of `origin/main`, so
  G-05-5 remains open. Phase 04 dispositions and UAT resolution fields are
  unchanged.
- No hosted receipt was obtained. An exact-revision hosted route would require
  publishing a branch with the known 288-commit delta, which remains outside
  this plan's safe route. G-05-3 and G-05-5 remain open; no Phase 04 status or
  UAT resolution field was changed.

## Plan 05-03 continued selected-guest evidence (2026-10-09)

- The local BIOS classifier now accepts only bounded, flat-safe extras after
  ZIP metadata/extents and decompression/CRC validation; the exact selected BIOS
  identity is still required once, and game members remain exact. Python/C
  parsing permits DEFLATE option hints only on method 8, while data descriptors
  and other flags remain rejected. The earlier EOCD-comment warning was
  independently reviewed: both parsers reject malformed candidates and accept
  exactly one structurally valid end record; EOCD-like data inside a valid
  comment is covered by the synthetic regression.
- Source-backed CPU changes are limited to the observed instruction families:
  MOVE.B Dn→absolute-long (12 clocks), MOVE.B immediate→absolute-long (20),
  MOVE.W immediate→absolute-long (20), MOVE.W immediate→Dn (8), BSR.W (18),
  RTS (16), and LEA absolute-long (12). Timing uses the exact NXP/Motorola
  *M68000 User's Manual* rows; the immediate-to-Dn vector checks upper-half
  preservation, N/Z/V/C, X, register selection, exact instruction cycles, and
  unsupported neighboring addressing forms.
- Subsequent private local decode added JSR PC-displacement (18 clocks),
  MOVEM.L `(An)+`→register list (`12+8n` clocks), MOVEA.L `(An)+,An` (14 clocks),
  MOVEA.L `An,An` (4 clocks), MOVE.W `Dn,Dn` (4 clocks), and MOVE.B
  `Dn,(An)` (8 clocks, one byte write), plus MOVE.W `Dn,(An)+` (8 clocks,
  one word write), condition-F DBF (10-cycle taken/16-cycle expired paths),
  and MOVE.W `(An),Dn` (8 clocks, two reads).
  Tests cover
  extension/return behavior, mask
  order and base-register override, full-width transfer, source postincrement,
  partial-width destination preservation, N/Z/V/C updates, X preservation,
  unchanged MOVEA flags, register aliases, exact cycles, and unsupported
  neighboring addressing modes, adjacent-byte preservation, word postincrement,
  odd-address exception handling, and DBF low-word decrement/branch/fallthrough.
  Indirect word-load tests cover upper-word preservation, flags, even/odd source
  alignment, and unsupported postincrement.
  Sources are Motorola *M68000 Family Programmer's Reference
  Manual* §4 JSR p. 4-109, §4 MOVEM pp. 4-128–4-129, §4 MOVEA pp. 4-119–4-120;
  §4 DBcc pp. 4-90–4-91;
  NXP/Motorola *M68000 User's Manual* Tables 8-3 p. 8-3, 8-8 p. 8-8, 8-10
  p. 8-8, 9-2 p. 9-3, and 9-15 p. 9-10.
- The MVS delta adds only the observed source-backed vector-bank latch, audio
  source-select observation bit, video offset latch, zero-pending interrupt
  acknowledgement, watchdog/reset accounting, width-bounded MAME dropped-byte
  writes, and per-instance two-channel coin-lockout state. Synthetic guest
  vectors cover set/clear, mapped/wrong-index or wrong-width controls, mirror
  boundaries, watchdog expiry/pet behavior, and instance-scoped observations.
  The audio-select bit makes no audio/handshake claim; vector selection maps one
  configured cartridge slot only. Physical hardware behavior remains unknown.
- Focused validation passed after the latest CPU/vector change:
  `cmake --build --preset owned-debug --target owned_cpu_semantics &&
  build/owned-debug/experiments/owned_cpu/owned_cpu_semantics` (26/26);
  `cmake --build --preset sdk-debug && ctest --preset sdk-debug -L mvs
  --output-on-failure --no-tests=error` (7/7); and the synthetic importer
  commands `python3 tests/mvs/test_mvs_qualification.py --importer
  build/sdk-debug/mvs_importer --mode positive` (6/6) and `--mode mutation`
  (7/7). The unqualified all-tests direct invocation uses the production
  identity table against synthetic identity fixtures and is not the intended
  command; the CTest target supplies the synthetic-identity harness.
- At the time of this earlier validation snapshot, sanitized local qualification exited nonzero with
  `unsupported_guest_event` after guest execution. The report retains the exact
  private fault details only in ignored local storage. No event was accepted as
  attract/start. No actual RetroArch app launch occurred because that
  precondition is unmet. G-05-3 remains open.
- The independent review at that earlier snapshot found no
  blockers. No exact-revision hosted route is safe: the current 288-commit delta
  would be included in a push/PR. No hosted receipt was obtained; G-05-5 remains
  open. Phase 04 dispositions and UAT resolution fields remain unchanged.

## Final Plan 05-03 execution-boundary evidence

- The latest current-source run uses a hard 256-chunk limit and ends at
  `guest_instruction_budget_exhausted` after 32,255,007 instructions and
  256,000,794 cycles. The sanitized per-chunk profile reports 140 stable
  chunks, 20 output/latch transition chunks, 97 video-state transition chunks,
  17 bank-transition chunks, 6,472,496 watchdog pets, zero resets, and no
  repeated final chunk-boundary suffix. These observations do not constitute a
  guest-written attract/start predicate.
- Fetch provenance was checked locally against the exact normalized GNMV
  manifest buffer: all 16 bounded fetch-ring entries matched the bytes fetched
  at their recorded PCs, and the final fetch cursor matched the runner boundary.
  Raw values remain only in ignored local output.
- `cmake --build --preset sdk-debug && ctest --preset sdk-debug
  --output-on-failure` passed 41/41; `cmake --build --preset owned-debug &&
  ctest --preset owned-debug --output-on-failure` passed 54/54, followed by
  `python3 tools/owned_cpu/inventory.py check --build-dir build/owned-debug`
  passing with 30 fields, 10 compiled sources, and no mutable runtime globals.
- ASan/UBSan focused MVS build and CTest passed 7/7. Wrapper positive and
  mutation modes passed 9/9 and 7/7; GUI-free RetroArch smoke tests passed
  31/31. Independent re-review passed the status allowlist, in-tree runner,
  profile sanitizer, and 256-chunk documentation changes.
- Current `origin/main..HEAD` is 288 commits, with additional uncommitted plan
  changes; no safe exact-current-source hosted receipt route exists. G-05-3,
  G-05-5, and actual-app behavior remain open/unknown.

## MC68000 exception contract correction — 2026-10-09

The selected CPU is MC68000. Exception/reset timing tests and expectations use
the MC68000 column of Motorola/NXP User's Manual Rev. 9.1 Table 7-15 (printed
p. 7-11): reset 64, IRQ 72, address/bus error 94, and illegal instruction,
privilege exception, and TRAP 62 clocks. The earlier Section 8 / MC68010
figures were inconsistent with this contract and are superseded. The bounded
vector-4 implementation is restricted to the observed reserved byte- and
long-EORI destination encodings; unknown valid-but-unimplemented instructions
remain fail-closed. Its regressions check old SR, pre-instruction PC,
supervisor stack/vector behavior, 62 cycles, and no operand write.

## Plan 05-06 execution evidence — 2026-10-09

- Task 1 is complete in shared commit `183c489`. The diagnostic oracle wording
  and fixture source identity now agree with the reviewed reset-cycle contract;
  all 13 omitted public test paths have affirmative exact-byte rights rows,
  and the two pinned upstream zlib attribution blobs have narrow history
  dispositions with original notices preserved. Local public-content, focused
  docs/evidence/frontend checks, and the complete SDK matrix passed at the
  reviewed source candidate.
- Task 2 stopped at the plan's narrow evidence gate. Review of the available
  public source and prior validation records found no independently observed
  selected configuration and no sourced guest-written attract/start predicate.
  The existing 256-chunk run ended at the instruction budget without a
  checkpoint; no new 256-chunk run, CPU/board change, or predicate was
  fabricated. Selected compatibility and GAME-02 remain open. The actual
  RetroArch selected-media flow remains unknown/manual-only because its launch
  preconditions did not materially change.
- Task 3's public-safe candidate is
  `e80672845fc60d94d8a44eab416377534c9a99f1` on PR #2. Local
  source-identity/evidence, rights, matrix (1,440 assertions, 43 cases, 10
  lanes), hosted-receipt tests, and public-content/history checks passed.
  Independent review passed that exact SHA.
- Hosted PR run `38001400110` passed on the exact candidate SHA: all six matrix
  lanes, public-content, and `ci-policy`. The downloaded event, MVS receipt,
  canonical MVS output, and aggregate from that run were accepted by
  `tools/verify_hosted_mvs.py`; the receipt contains the seven named passing
  MVS CTests with positive denominator and matching source/output digests.
  This closes the candidate's G-05-5 hosted-evidence gate only. PR #2 remains
  unmerged because protected `main` requires one approving PR review and the
  PR has `REVIEW_REQUIRED`; no protection was bypassed.

### Current hosted-receipt coverage disposition

| Task / requirement | Test type | Candidate command and artifact | Result and scope |
|---|---|---|---|
| 05-06 Task 3 / G-05-5 — reject malformed or mismatched hosted MVS receipts | Unit (receipt validator) | `python3 tests/sdk/test_hosted_mvs_receipt.py` (`tools/verify_hosted_mvs.py`) | Passed 11 tests on candidate `e80672845fc60d94d8a44eab416377534c9a99f1`; validates event eligibility and SHA, lane/test inventory, positive denominator, source/output digests, and aggregate. The test and checker are not present in shared checkout HEAD `f9e02f94d664c3f8170f4dc7ae8aa30bc24c13f6`, so this command is candidate evidence and is not runnable or asserted as a HEAD test. |
| 05-06 Task 3 / G-05-5 — hosted MVS lane and aggregate | Hosted CI receipt | Run `38001400110`, PR event for candidate SHA `e80672845fc60d94d8a44eab416377534c9a99f1`; artifacts accepted by `tools/verify_hosted_mvs.py` on that candidate | Passed for the exact candidate: seven named MVS CTests, positive denominator, matching source/output digests, and passing aggregate. This does not qualify shared checkout HEAD, selected-game boot, merge, release, or frontend behavior. |
| 05-06 Task 2 / G-05-3, GAME-02 | Manual/source evidence gate | No executable selected-game predicate command is justified yet | Open/unknown. Required before running the bounded private qualification: an independently observed selected configuration and an independently sourced guest-written attract/start predicate with source-flow evidence and oracle ancestry. Without those, do not invent a predicate or interpret coarse device-state activity as acceptance. |
| Selected-media RetroArch flow / MEDIA-03 frontend observation | Manual | No command; launch preconditions did not materially change | Unknown/manual-only. Required evidence is direct observation in the functioning pinned RetroArch setup of selected-media import/load, stable presentation, input response, unload, and normal exit. Existing synthetic callback tests do not establish this flow. |

The candidate's 11-test receipt-validator command and hosted artifacts are
recorded from Plan 05-06's candidate history. They must not be presented as
tests of `f9e02f94d664c3f8170f4dc7ae8aa30bc24c13f6`; the checker and test are
absent from that shared checkout. G-05-5 is resolved only for the stated
candidate evidence. The selected guest compatibility/checkpoint requirement
and the actual frontend flow remain open/unknown.

Phase 05 remains incomplete: selected guest compatibility/checkpoint evidence
is still missing. Phase 04 status, its threat dispositions, and `05-UAT.md` were
not changed.
