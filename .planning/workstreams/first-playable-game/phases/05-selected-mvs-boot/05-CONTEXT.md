# Phase 05: Selected MVS Boot - Context

**Gathered:** 2026-10-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Add one bounded MVS media profile and host-side import path, then implement the board, guest execution, banking, protection, timing/interrupt behavior, and sound-CPU handshake needed for the selected Metal Slug X revision and BIOS configuration to reach its attract/start path. The native core remains C17, deterministic, per-instance, filesystem-free, and frontend-independent. Phase 05 engineering may proceed using the already-verified Phase 04 native API/fixture foundation; Phase 04 remains blocked until its actual pinned RetroArch observation and all user-directed threat dispositions are resolved. Phase 05 must not change those dispositions or claim Phase 04 acceptance.

</domain>

<decisions>
## Implementation Decisions

### Phase sequencing and evidence gates
- **P05-C-01:** Continue Phase 05 engineering while Phase 04 remains `gaps_found`, because the native API and fixture behavior are verified and the remaining Phase 04 GUI/security signoffs are not prerequisites for synthetic media, board, and guest-execution work. Keep HOST-02, frontend QUAL-03, and all seven user-directed open threats unchanged and explicitly open. This supersedes the stale `STATE.md` instruction not to start Phase 05; the installed GSD planning transition must update the current position without closing Phase 04.
- **P05-C-02:** Keep Phase 04, Phase 05, and final milestone evidence separate. A synthetic MVS fixture proves contracts and machine behavior only for that fixture; MAME agreement is differential evidence, not hardware truth; only an actual pinned RetroArch run can establish its frontend behavior.

### Native media contract and profile
- **P05-C-03:** Preserve the existing diagnostic/fixture manifest-v1 contract. Add an additive, versioned MVS-specific region contract rather than widening the fixed two-region v1 struct in place. Describe the selected profile and every required region with explicit byte order/layout, source span, mapped size, and ownership lifetime. Validate all counts, ranges, overlap, arithmetic, and aggregate allocation before use; copy caller-owned bytes transactionally so a failed load preserves the previous valid image.
- **P05-C-04:** Support one documented MVS profile and one selected Metal Slug X revision. Establish exact BIOS and cartridge region identities/sizes from pinned public MAME metadata plus local-only checks against the user-provided media. Identify members by content identity and expected layout, never by filenames alone. Do not commit or print private paths, checksums, media bytes, save data, or derived captures.

### Archive/import and dependency boundary
- **P05-C-05:** Keep filesystem and archive work outside both the native core and Libretro adapter. Use a small C17 host importer that reads one ZIP32 archive and atomically emits a versioned normalized MVS bundle for RetroArch to load. Implement only the bounded central-directory/container subset needed by the selected profile; use pinned zlib 1.3.2 solely for raw DEFLATE, with CRC and exact-size checks. This single leaf dependency is justified because DEFLATE is not small, safe functionality to copy or reimplement; do not add a general archive framework. Bound archive/member/count/compressed-size/expanded-size/aggregate-size, reject duplicate or unsafe member names and unsupported features, never extract paths to disk, and leave originals untouched. The native core receives validated in-memory region descriptors; the adapter consumes only the normalized bundle, so user loading does not depend on unobserved frontend ZIP extraction behavior. Keep zlib out of the core's public link interface and retain its upstream license, commit, and update owner.
- **P05-C-06:** Keep import error categories distinct and actionable (missing input, malformed archive, unsupported set/profile, incompatible BIOS, exceeded limit, allocation/load failure). Redact private paths and content identities from logs. Preserve the native API's transactional unload/reload and failed-load recovery behavior; Libretro's boolean load result may be accompanied only by bounded, privacy-safe log messages.

### Boot implementation and verification
- **P05-C-07:** Keep the first verification fixture synthetic and rights-clear. Prove the MVS media API through a compiled native C consumer, then exercise bundle import and the Libretro callback seam with generated archives. Add boundary/negative cases and a bounded fuzz target for hostile archive/bundle inputs. Follow the existing CTest/CMake patterns and use sanitizers for the relevant parser and region arithmetic.
- **P05-C-08:** Expand the owned 68000 and MVS board only for behavior demonstrated by the selected boot path. Implement real memory banking, interrupts/timing, protection, and sound-CPU handshakes as guest-visible behavior; do not fake the BIOS or title transition. Pin implementation references and record oracle ancestry. If the CPU/board gap cannot reach attract/start within this phase, report the exact unsupported instruction/event and leave GAME-02 open rather than relaxing acceptance.
- **P05-C-09:** Sound-CPU command/reply behavior needed by boot belongs here. Audible YM2610/game music qualification remains in Phase 07; no non-silent/silicon-fidelity claim is made from the current synthetic candidate admission.

### the agent's Discretion
- Choose concrete limits only after measuring the selected public region sizes and accounting for both compressed input and normalized output. Prefer conservative caps that cover this one selected profile with headroom.
- Use small local parsing/validation code where it remains easy to audit; add a dependency only when its established correctness justifies the full transitive, license, and offline-build costs. Preserve provenance and update ownership for any copied code.
- Select narrow CTest, importer mutation, and fuzz regressions that directly establish the stated contracts; keep private game media out of public tests.

### Planner Coverage Aliases
The installed plan-coverage gate recognizes D-IDs. These aliases preserve the phase-scoped decisions above without changing them.
- **D-01:** Proceed with Phase 05 while preserving Phase 04 acceptance blockers (P05-C-01).
- **D-02:** Keep Phase 04, Phase 05, and milestone evidence separate; MAME is differential only (P05-C-02).
- **D-03:** Add a versioned MVS contract and select one exact documented profile with private identity local (P05-C-03, P05-C-04).
- **D-04:** Use the standalone C17 ZIP32 importer, normalized bundle, and pinned zlib raw DEFLATE dependency (P05-C-05).
- **D-05:** Preserve distinct privacy-safe errors and transactional recovery (P05-C-06).
- **D-06:** Use synthetic rights-clear fixtures, consumer/callback tests, and bounded hostile-input tests (P05-C-07).
- **D-07:** Implement only guest-driven source-qualified boot behavior; do not fake transitions or device responses (P05-C-08).
- **D-08:** Implement only boot-required sound-CPU handshake; audible qualification remains in Phase 07 (P05-C-09).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Current scope and delivery rules
- `.planning/PROJECT.md` — core/product boundary, host-owned file I/O, licensing and privacy constraints.
- `.planning/workstreams/first-playable-game/REQUIREMENTS.md` — MEDIA-02/03/04 and GAME-02 acceptance requirements.
- `.planning/workstreams/first-playable-game/ROADMAP.md` — Phase 05 scope, dependency amendment, evidence boundaries, and later phase allocation.
- `.planning/workstreams/first-playable-game/STATE.md` — current status and private-media handling; its earlier “Do not start Phase 05” note is superseded by the current roadmap and must not override P05-C-01.
- `.planning/workstreams/first-playable-game/RESEARCH.md` — accepted milestone decisions, MVS/BIOS uncertainties, and source ancestry.
- `.planning/METHODOLOGY.md` — stakeholder analysis, dependency preference, shift-left checks, forward progress under external blockers, and phase-closeout rules.

### Preparation evidence and prior-phase gates
- `.planning/preparation/README.md` — evidence/source policy and document map.
- `.planning/preparation/DECISIONS.md` — PREP-D-20 (normalized media outside archive layer) and PREP-D-21 (bounds at hostile-input boundaries), plus the dependency comparison method.
- `.planning/preparation/NEOGEO-HARDWARE-AND-ECOSYSTEM.md` — MVS maps, BIOS, banking/protection, Z80 interaction, hardware uncertainty, and MAME source ledger.
- `.planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VERIFICATION.md` — verified Phase 04 truths and current open frontend/security blockers.
- `.planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md` — the seven user-directed open threats; preserve their status.
- `.planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md` — Phase 04 automated/manual evidence boundary.

### Existing implementation seams
- `include/glueyneo/glueyneo.h` — current public API, manifest-v1 layout, ownership, status, and limits.
- `src/instance.c` — transactional load pattern, profile checks, memory regions, and current diagnostic bus.
- `src/libretro/libretro_core.c` — current in-memory GNFX-only content adapter and callback lifecycle.
- `third_party/libretro/libretro.h` — vendored Libretro ABI declarations; use its exact checked-in contract rather than mutable documentation as implementation truth.
- `tests/sdk/test_sdk.c`, `tests/libretro/callback_harness.c`, and `tests/tools/test_verify_playable.py` — existing lifecycle, callback, error, and local-tool test patterns.
- `.planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-RESEARCH.md` — phase-specific implementation research, primary sources, options, and test recommendations.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `gn_load` builds a candidate image, copies source data, initializes it, and swaps only after complete success; reuse that transaction boundary for MVS loading.
- Existing test allocators and SDK tests already exercise allocation failure, invalid region layouts, reload recovery, and instance isolation.
- The Libretro callback harness can exercise the normalized bundle path without claiming a real frontend run.

### Established Patterns
- The current manifest is a fixed two-region diagnostic contract, not a general cartridge API. Preserve it and add an explicit MVS contract.
- The 68000 bus currently handles only diagnostic ROM/RAM plus one fixture input port; it has no MVS BIOS map, bank switching, protection, or device timing. Extending the manifest alone cannot boot the game.
- The adapter uses static Libretro callbacks and owned frame/audio buffers, accepts only GNFX bytes, and advertises `.bin`; it has no MVS loader today. Phase 05's selected import path is a separate C17 ZIP-to-normalized-bundle tool; the adapter must not acquire ZIP parsing or zlib linkage.
- Build and tests are target-based CMake/CTest with strict owned-C warnings and Python tooling. A new importer must not make the native core or SDK require Python.

### Integration Points
- Add the new MVS contract to `include/glueyneo/glueyneo.h` and transactional profile handling to `src/instance.c` while preserving the fixture path.
- Keep ZIP parsing and local file I/O in the standalone importer; load the normalized package through Libretro and invoke the core with explicit in-memory regions.
- Add synthetic archive/bundle builders and a C consumer to the existing test/build setup. Keep any local commercial-media run opt-in, ignored, and privacy-safe.

</code_context>

<specifics>
## Specific Ideas

- The user's dependency default is “another copy and paste is better than another dep”; evaluate the whole transitive tree and maintainability before adding a package. Never hand-write DEFLATE.
- Use one MVS configuration and the selected Metal Slug X revision. Retain exact claim boundaries and do not broaden into AES or general archive compatibility.
- Avoid retrying the unchanged aborting RetroArch launch context. Keep actual frontend behavior manual-only until a materially changed, functioning pinned setup can be observed.

</specifics>

<deferred>
## Deferred Ideas

- Active-scene movement/firing/scrolling and the broader video contract belong to Phase 06.
- Audible game music/effects and combined scenario qualification belong to Phase 07; Phase 05 implements only boot-required sound-CPU handshakes.
- AES, broad cartridge compatibility, arbitrary archive formats, save-state compatibility, and commercial-media distribution remain out of scope.

</deferred>

---

*Phase: 05-Selected MVS Boot*
*Context gathered: 2026-10-08*
