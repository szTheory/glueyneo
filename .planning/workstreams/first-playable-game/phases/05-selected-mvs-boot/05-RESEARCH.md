# Phase 05: Selected MVS Boot — Research

**Researched:** 2026-10-09  
**Domain:** C17 emulator media contracts, bounded ZIP ingestion, MVS cartridge/BIOS mapping, 68000 boot behavior  
**Confidence:** MEDIUM overall; HIGH for the inspected public interfaces and pinned reference-source facts, MEDIUM for implementation recommendations, LOW for hardware claims not established by primary measurements.

## User Constraints

No Phase 05 `CONTEXT.md` exists. These constraints come from the current approved requirements, project instructions, and the explicit research assignment:

- Keep native core code in C17 by default, host-independent, filesystem-free, deterministic, opaque, per-instance, and explicit about ownership, buffers, errors, and limits. Keep file/archive work in the importer or libretro/host adapter.
- Prefer a small flat dependency tree. A bounded local ZIP container reader is acceptable; DEFLATE must come from an established decompressor and must never be hand-written.
- Keep commercial ROM/BIOS bytes, private paths, private checksums, captures, traces, and derived outputs outside tracked artifacts, public CI, and releases. A matching media identity or emulator agreement does not establish hardware compatibility.
- Use original/public fixtures for CI and private supplied media only for opt-in local qualification. Separate guest/core behavior from actual RetroArch behavior and keep Phase 04's HOST-02, QUAL-03, and directed threat dispositions open; Phase 05 engineering does not close Phase 04.
- Select one bounded MVS profile and one selected title/revision. Do not silently broaden to AES, additional boards, general archive formats, full-game support, or hardware-perfect claims.
- Build acceptance around source-qualified regressions, useful wrong-behavior controls, boundary tests, clean consumer linkage, and independent review. Keep hardware-reference ancestry and uncertainty explicit.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEDIA-02 | A C integrator can supply normalized immutable cartridge and BIOS regions for one documented MVS configuration under explicit media lifetimes, region layout, byte order, and resource limits. | Expand the native contract from the current two-region diagnostic manifest to an MVS profile with named, immutable, byte-addressed regions; validate exact region set/size/layout and limits before mutating the machine; copy at `gn_load` or define equally explicit retained-buffer lifetime. |
| MEDIA-03 | A user can load the selected local game and BIOS archives through one documented, tested RetroArch/import path, with archive/file handling outside the native core and without modifying the original archives. Required ZIP handling uses bounded parsing and an established decompressor. | Build a frontend/importer-facing bounded ZIP read path, accept only needed ZIP32/store/DEFLATE features, use pinned zlib raw inflate, never extract to disk, and test through a GUI-free libretro harness plus the documented path. Actual pinned RetroArch behavior remains a separate manual observation. |
| MEDIA-04 | A user receives distinct, actionable errors for missing or incompatible BIOS/media, unsupported sets, malformed archives, and exceeded limits; after a rejected load, the consumer can load valid media or destroy the instance safely. | Separate error categories across importer and native APIs; validate completely into temporary allocations before installation; exercise failure/recovery sequences and allocation/decompression/parser faults. |
| GAME-02 | A user can boot the selected Metal Slug X revision and BIOS configuration to its attract/start path through guest execution on the owned 68000 and required MVS board behavior, with added CPU, banking, interrupt/timing, and protection behavior tied to source-qualified regression evidence. | Use the pinned MAME Neo Geo mapping as an implementation reference and test oracle with explicit ancestry, not hardware truth; build the boot path in guest-driven vertical increments with CPU, bus, BIOS vector/overlay, banking, interrupts, Z80 handshakes, and title-specific protection coverage. |

## Summary

Phase 05 is genuinely independent of the remaining Phase 04 acceptance blockers: the current roadmap explicitly says the frontend observation and user-directed threat dispositions block Phase 04 acceptance and related claims, not the Phase 05 media/board/guest-engineering work. Keep those open and proceed with Phase 05. [VERIFIED: `.planning/workstreams/first-playable-game/ROADMAP.md:101-108`] Verbatim: “the unresolved Phase 4 RetroArch observation and user-directed threat dispositions do not block Phase 5 engineering, but remain blockers to Phase 4 acceptance and any corresponding frontend/security claim.”

The first vertical slice should be a private-data-free MVS manifest contract and media-normalization harness using synthetic archives and synthetic region payloads. It should prove checked parsing, expected layout/interleave, error taxonomy, resource ceilings, immutable input handling, and safe failure/recovery before integrating boot logic. Then connect the bounded importer to one documented libretro path, followed by guest boot in increasingly complete steps. Do not use an archive CRC or a known ROM-set digest as a proxy for a successfully booting board.

The native API is currently diagnostic-only: `GN_PROFILE_DIAGNOSTIC`, `GN_PROFILE_PUBLIC_FIXTURE`, `GN_MAX_REGIONS 2u`, `GN_MAX_MEDIA_BYTES` 1 MiB, current statuses, ROM/RAM-only regions, and a manifest with two region slots are present. [VERIFIED: `include/glueyneo/glueyneo.h:24-61`] Verbatim: “#define GN_PROFILE_DIAGNOSTIC UINT32_C(1)”; “#define GN_PROFILE_PUBLIC_FIXTURE UINT32_C(0x50554246)”; “#define GN_MAX_REGIONS 2u”; “#define GN_MAX_MEDIA_BYTES ((size_t)1024u * (size_t)1024u)”; “GN_STATUS_INVALID_MEDIA,” “GN_STATUS_UNSUPPORTED_PROFILE,” “GN_STATUS_OUT_OF_MEMORY,” “GN_REGION_ROM = 1,” “GN_REGION_RAM = 2,” “gn_region regions[GN_MAX_REGIONS];”. The MVS title's public MAME region map is substantially larger than the present cap and includes distinct program, fixed, sound-program, sample, and sprite regions, so the profile needs separately justified per-region and aggregate ceilings before implementation; do not blindly carry the diagnostic cap forward.

For ZIP, use a small, deliberately constrained central-directory reader plus pinned zlib for raw DEFLATE. This best fits the requirements and project preference: it avoids a new general archive framework and its transitive codecs, but accepts only a closed feature set with fail-closed parsing and comprehensive fuzz/boundary tests. Do not implement compression. Keep the parser outside the machine core and avoid filesystem extraction/path traversal altogether. A second viable route is a full archive library (for example libzip/libarchive) if the actual frontend/import route requires broader ZIP interoperability; that increases dependency/build surface and should be justified by required formats rather than hypothetical compatibility.

For GAME-02, the exact boot path remains a systems-integration problem, not a single CPU opcode gap. MAME's pinned source identifies Metal Slug X's MVS PROGEOP board, interleaved program data, fixed ROM, sound program, samples, and sprite planes. Its dedicated protection model also labels a protection selector calculation unresolved. [CITED: https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo/prot_mslugx.cpp] Treat MAME as an emulator implementation with a reproducible revision and known uncertainty, never as independent proof of original silicon. The exact supported BIOS identity/configuration must be selected in a private local test context; public docs must not expose private archives or hashes.

**Primary recommendation:** First deliver one synthetic-data MVS media vertical slice: immutable normalized region contract, a bounded ZIP32 parser that rejects unsupported features, zlib 1.3.2 raw inflate, deterministic specific errors, safe reload-after-failure, and native C-consumer tests. In the same phase, integrate the selected MVS profile in guest-driven boot checkpoints tied to pinned MAME map/source and independent CPU/bus tests; retain private RetroArch/media evidence as a separate opt-in local step.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ZIP discovery, bounded parse, CRC validation, normalized region construction | Importer / frontend adapter | Host file/VFS layer | Parsing and file access are untrusted-content boundaries; keeping them out of core preserves deterministic host independence. |
| MVS media/profile validation and immutable ownership | Native core API | Importer | The core must reject incompatible profile/region combinations and own a stable copy or explicit lifetime contract; importer translates archive layout into normalized regions. |
| Libretro content handoff | Libretro adapter | Frontend | Libretro controls whether it passes a memory buffer or a path; buffer persistence and archive extraction are frontend-sensitive. |
| MVS bus, BIOS mapping, banking, IRQ timing, sound-CPU synchronization, protection | Native machine | CPU/chip devices | These are guest-visible hardware responsibilities requiring deterministic emulated time and per-instance state. |
| Private local Metal Slug X boot qualification | Local test/qualification harness | Actual pinned RetroArch | A native harness isolates machine behavior; only an actual frontend run establishes that frontend load/input/presentation claim. |
| Public regression/CI | Synthetic and first-party guest fixtures | Native and libretro consumers | Keeps proprietary media out of CI while testing contracts and publicly redistributable behavior. |

### Decision Matrix: Stakeholder and Adversarial Lenses

| Lens | Strongest concern / alternative | Recommendation and tradeoff |
|------|-------------------------------|-----------------------------|
| Product/player | Requiring a separate import step creates friction; broad compatibility would feel smoother. | Support one explicit MVS profile and a documented load path first. Reject unknown/mixed sets clearly; expand only from observed demand. A narrow honest path is more useful than a broad silent misload. |
| Core architect | Multi-region MVS media does not fit the diagnostic ROM/RAM model; mixing storage/format logic with guest state spreads complexity. | Add one profile-specific normalized media contract and keep ZIP/filesystem out of the core. This is deliberate API evolution, not a generic media framework. |
| Security engineer | Custom ZIP code is attack surface; a huge archive package expands transitive code and parsers. | Prefer strict central-directory parser + pinned zlib only if closed feature profile remains small, fuzzable and explicit. If feature needs grow, stop and reassess libzip/libarchive rather than extending ad hoc. No extraction-to-disk. |
| Frontend engineer | `need_fullpath` avoids frontend memory duplication but pushes IO to core; `need_fullpath=false` can send transient memory. | Prefer memory mode for ordinary bounded content and copy before callback returns; use `block_extract` only after verifying pinned frontend flow, otherwise document importer conversion. Test the callback path separately from actual GUI behavior. |
| Emulator/board engineer | MAME maps are actionable, but are an emulator with known uncertainty and some title logic is unresolved. | Pin MAME as a differential source, add independent expected tests for generic CPU/bus/layout properties, and mark reference-derived title checkpoints explicitly. Do not claim silicon fidelity. |
| CPU/chip engineer | One title boot can tempt opcodes and device responses that only satisfy observed instruction traces. | Extend owned CPU semantics based on defined instruction/bus behavior with boundary/exception tests; implement only required MVS timing/device scope, but never special-case PC or fake a handshake. |
| QA/test engineer | A screenshot/hash can pass despite wrong byte mapping or fake guest output. | Layer parser properties, transform vectors, bus/checkpoint assertions, wrong-behavior controls, a native C consumer, and separate actual-app observation. Keep golden ancestry explicit. |
| Build/release engineer | System package versions and frontend-linked zlib are inconsistent across targets; offline builds can fail. | Pin a private, target-scoped zlib C dependency with notice and current revision; exercise static/shared consumer linkage and cold/offline configure where project policy requires. Keep any optional system-zlib route separately qualified. |
| License maintainer | MAME contains per-file licenses while complete project is GPL-2.0-or-later; ROM and BIOS images are copyrighted. | Read source only and retain exact citations. Any future copy gets per-file/dependency review. Never place private/commercial media or derived checksums in public artifacts. |
| UX/docs maintainer | Generic failure is not actionable, but exposing filenames/hashes can disclose private corpus. | Report stable generic categories plus safe corrective action (“unsupported compression method”; “required region missing”), not private paths/member identities/digests. Keep detailed local diagnostics redacted/ignored. |

### Efficient Phase Task Shape

Plan Phase 05 as one consolidated plan with dependency-aware waves and execute it in one invocation (consistent with current methodology); do not create a plan per tiny parser edge case. The suggested wave boundaries are:

1. **Media contract and profile groundwork:** add MVS-specific region descriptors and named per-profile limits; unit-test malformed and valid synthetic manifests, byte lanes, immutable lifetime, and all-or-nothing load/recovery. Lock the initial BIOS/profile choice using public source metadata plus private local confirmation without copying private identity into tracked docs.
2. **Importer boundary:** add ZIP32 constrained central-directory reader, pinned zlib inflate, CRC/size/aggregate accounting, stable error categories, and synthetic stored/DEFLATE/malformed corpus. Fuzz parser after basic API tests are meaningful. Wire one GUI-free libretro content path and document a conversion fallback.
3. **Board boot dependencies:** implement selected BIOS ROM mapping/vector overlay, MVS memory regions and cartridge program banking; add independent tests for byte mapping, reset vectors, boundaries, and bus accesses. Extend 68000 behavior only from the first observed boot failures and source/ISA evidence.
4. **Guest boot integration:** implement only demonstrated IRQ/timing, protection, and sound-CPU handshake behavior needed by the boot checkpoint; assert real guest execution reaches attract/start. Run private scenario only locally, classify MAME differential vs independent expected evidence, and keep direct RetroArch observation manual-only unless environment changes.
5. **Closeout in one batch:** run the full existing suite plus phase-specific tests, fuzz regressions, static/shared consumers, sanitizers, current-source independent review and a single phase verification. If attract/start is not reached for a concrete technical gap, produce one bounded follow-up plan after consolidating all repository gaps. Do not reopen Phase 04 dispositions.

This plan shape is not a commitment to arbitrary implementation limits or acceptance shortcuts: exact region budgets, BIOS identity, and observed boot dependencies are Wave 1 evidence decisions. A failed vertical slice should reveal the next concrete dependency rather than trigger repetitive tiny gap plans.

## Standard Stack

### Core

| Library / source | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| C17, target-based CMake, CTest, Ninja | Current project configuration | Owned runtime, private importer targets, headless integration tests | Existing project stack and portability approach. Build targets should preserve the native-core/adapter boundary. |
| zlib | **1.3.2**, upstream tag `v1.3.2`, peeled commit `da607da739fa6047df13e66a2af6b8bec7c2a498` | Raw DEFLATE decode only | Mature C inflater with official raw-DEFLATE API and zlib license. Release date 2026-02-17 per upstream release page. [CITED: https://github.com/madler/zlib/releases] |
| PKWARE APPNOTE | Version 6.3.10 as currently published; moving URL | ZIP record and feature reference | Format authority. Pin a downloaded copy/hash in the implementation task if parser behavior is copied into project docs/tests. It defines the required directory records, offsets, flags, lengths and ZIP64 extensions. [CITED: https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT] |
| libretro API header | Existing project pin `libretro-common` `2b96a82bd8479bb3547d271e1eefadc82dd2161e` | Content buffer/path and frontend callback contract | Existing pinned ABI surface, including `need_fullpath` and `block_extract`; actual frontend semantics still need direct test. [CITED: https://github.com/libretro/libretro-common/tree/2b96a82bd8479bb3547d271e1eefadc82dd2161e] |
| MAME Neo Geo implementation | `mamedev/mame` commit `31e52312c59e4d60d70235118bcbccd220f5232e` | MVS map, BIOS/profile and title-specific differential reference | Maintained, exact-revision implementation source. MAME is GPL-2.0-or-later as a project and files have their own notices; use as a read-only behavioral reference unless every copied file/dependency is separately reviewed. No bulk code reuse is recommended. [CITED: https://github.com/mamedev/mame/tree/31e52312c59e4d60d70235118bcbccd220f5232e] |

### Supporting

| Component | Purpose | When to Use |
|-----------|---------|-------------|
| Project-owned ZIP32 central-directory parser | Bounded container metadata parsing, member lookup, extent checks, stored entries | Use only if the selected path passes ZIP bytes to the core adapter and parser scope can remain small and closed. Never use it to decode DEFLATE. |
| zlib `inflateInit2` / `inflate` | DEFLATE member expansion | Only method 8 entries; use raw mode and separately validate ZIP CRC32, exact output length, full compressed-input consumption, and completion. |
| CTest native integration harness and C consumer | Test MVS manifest/API and static/shared linkage | Run with synthetic payloads in public tests; inject allocation/decompression failures and load valid media after failed loads. |
| libFuzzer or existing fuzz harness | Hostile archive and region-boundary fuzzing | After parser API and bounded input shape exist; retain minimized public synthetic regressions only. |

**Installation/build recommendation:** vendor zlib at its exact upstream commit as a private CMake target (or use a pinned system zlib only where the supported package/build guarantees it). Build only needed functionality where upstream supports that without fragile patching, preserve `LICENSE`, and record origin/commit/update owner. Do not make the frontend's incidental zlib copy a core link dependency: it is not a stable public integration contract. No npm/PyPI/crates package is recommended; package-legitimacy registry check is not applicable to this C source dependency.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Small local ZIP32 parser + zlib inflater (recommended) | Full libzip or libarchive | Full parser gives broader compatibility and reduces custom-parser security responsibility, but brings more API, build/dependency surface and likely additional optional codecs. Choose it if real supported archives require features beyond a small ZIP32 subset, after pin/license/build audit. |
| Pin zlib source | System zlib | Fewer vendored files and possibly smaller downstream artifacts, but consumer/platform versions and link behavior vary. Use only if a real platform matrix guarantees availability and tested compatibility. |
| Direct ZIP input to adapter | Pre-imported normalized `.gneo`/manifest package via a tool | Cleaner runtime path, less archive parser exposure; creates a conversion/user workflow and must preserve provenance/variant identity. A valid alternative if the selected RetroArch path cannot provide robust ZIP bytes. |
| MAME differential reference | Hardware capture / independent public instrumentation | Higher confidence about physical behavior; currently unavailable and cannot be inferred from an emulator's output. Keep hardware claims explicitly unqualified and proceed on bounded implementation evidence. |
| owned 68000 expansion plus small MVS board devices | Port or embed the full MAME machine | Full MAME provides broad functional behavior but has major architectural, licensing and dependency mismatch with this C17 core. Not justified for one bounded MVS slice. |

## Architecture Patterns

### System Architecture Diagram

```text
Local ZIP bytes or frontend content buffer/path
                  |
                  v
     Importer / libretro adapter boundary
       | bounded central-directory scan
       | reject unsupported/encrypted features
       | stored copy or zlib raw DEFLATE
       | CRC + declared-size + region identity checks
                  |
                  v
    temporary normalized immutable MVS regions
                  |
       profile/layout/resource validation
                  |
                  v
  native `gn_load` transaction (copy/own media)
                  |
                  v
  per-instance MVS bus + BIOS overlay + cartridge
  68000 <-> IRQ/timing + Z80 handshake + protection
                  |
                  v
      guest-driven BIOS/title boot observations
       | public synthetic regressions in CI
       | opt-in private local qualification only
```

### Recommended Project Structure

```text
src/
├── media/                 # ZIP boundary and normalized MVS media adapter; outside machine core
├── mvs/                   # profile, address map, banking, IRQ and protection state
├── chips/                 # existing private CPU/sound candidates and wrappers
└── libretro/              # libretro content/VFS handoff; no archive extraction to disk
tests/
├── media/                 # synthetic ZIP fixtures and malformed/bounds tests
├── mvs/                   # public synthetic bus/profile/protection tests
├── local/                 # ignored/private opt-in scenario harness; outputs stay local
└── consumers/             # installed native static/shared C consumer checks
```

Only create modules when implementation seams justify them. Do not invent a plugin system, generic archive framework, full ROM database or host-independent filesystem abstraction.

### Pattern 1: Parse and Normalize Before Mutating the Machine

**What:** Treat media loading as a transaction: parse the complete archive and manifest into temporary owned allocations, validate supported entry names, duplicate detection, methods/flags, sizes, checksums, expected region set, and aggregate resource budget, then call native load once. On any failure release every temporary allocation and leave the current machine in the documented unloaded/previous-valid state.

**When to use:** Any external archive or manifest load, including a failed attempt followed by a valid load.

**Example:**

```c
/* API sketch only; names/statuses are proposed, not current repository enums. */
media_result result = media_import_zip(input, input_size, limits, &temporary);
if (result == MEDIA_OK)
    result = gn_load(instance, &temporary.manifest);
media_release(&temporary);
```

**Source:** PKWARE APPNOTE describes central/local header lengths, offsets and optional descriptors; project API currently copies source bytes only on successful load. [CITED: https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT] [VERIFIED: `include/glueyneo/glueyneo.h:130-136`] Verbatim: “All pointers in a manifest must reference readable caller storage for the duration of gn_load. Successful loads copy every source byte.”

### Pattern 2: Fail-Closed ZIP Feature Profile

**What:** Locate EOCD within a bounded tail window, require one-disk ZIP32 with a bounded entry count and central-directory extent inside the input, parse each fixed record by explicit little-endian byte readers, check every `offset + length` before access, require local and central header agreement for selected members, and reject unsupported flags, encryption, ZIP64 sentinels/fields, multi-disk, compressed/encrypted central directories, unknown methods, duplicate canonical names, path traversal names, symlink/special-file entries, and ambiguous case-folded basename collisions. Accept only stored and DEFLATE method 8 if the real path demonstrates both are needed. ZIP standard fields are little-endian and variable strings are length-delimited. [CITED: https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT]

**When to use:** The importer receives ZIP bytes or local file content.

**Tradeoff:** A strict allowlist may reject valid ZIPs; the error should say which unsupported feature was encountered and offer the documented conversion route. This is safer than pretending to parse all ZIP variants.

### Pattern 3: Exact MVS Profile Regions, Never Filename-Only Guessing

**What:** A profile specifies region role, source/member identity policy, exact byte length, destination layout/interleave, erase-fill value, expected BIOS family/configuration, and whether data is immutable ROM or mutable device state. Normalize byte lanes and word swaps explicitly in the importer; the bus consumes a stable byte-addressed representation. Identify sets using source manifests plus content digests, with exact matches against the pinned MAME metadata when used; filenames are only discovery hints. Never let title-protection logic read host/archive names.

**When to use:** Loading the selected private title and BIOS profile.

**Source boundary:** MAME's pinned `mslugx` definition describes word-swapped program loads, fixed ROM, audio program/samples and byte-interleaved sprite planes. [CITED: https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp#L8640-L8661] This source is a reference implementation; its ROM-set metadata is not a hardware measurement or proof that the user's local set is supported.

### Pattern 4: Guest-Driven Boot With an Observable Checkpoint Ladder

**What:** Add one boot dependency at a time and record guest PC/exception, bus events, interrupt state, MVS device state, and bounded frame progress at reproducible guest boundaries. Checkpoints should test vector overlay, BIOS startup, cartridge program window, bank switch, required protection commands/results, sound-CPU request/acknowledgment, and attract/start transition. Do not skip CPU execution or fabricate device responses to make a title reach a target screen.

**When to use:** Extending the current small diagnostic CPU to the selected BIOS/title path.

**Evidence levels:** ISA/bus tests grounded in Motorola documentation and implementation-source comparisons; synthetic board-device tests with direct expected values; private title scenario tests that compare against a pinned reference emulator where no independent expected oracle exists; actual hardware remains unqualified absent direct measurement. MAME's protection source itself comments “How should this be calculated?” for one selector path, so that behavior must be marked reference-derived/uncertain rather than asserted as physical truth. [CITED: https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo/prot_mslugx.cpp#L456-L480]

### Anti-Patterns to Avoid

- **Filename-only region matching:** renamed or clone/mixed sets can silently map wrong bytes. Verify source identity, role and region shape; report ambiguity.
- **Unbounded extraction or archive path writes:** creates traversal, overwrite, disk exhaustion and TOCTOU risk. Parse in-memory extents, never extract archive members to disk for core loading.
- **Trusting local ZIP headers or declared sizes alone:** descriptors, central directory metadata, malformed extra fields, integer overflow and forged lengths create disagreement. Validate central/local consistency, compressed-input extent, exact decoded size, CRC and budget.
- **Accepting “almost” supported ZIP options:** general-purpose flags, encrypted names, Zip64, multi-volume and unfamiliar codecs need explicit implementations. Reject unsupported cases with an actionable result.
- **Allocating from attacker-declared uncompressed length before checking profile ceilings:** enables memory exhaustion. Check per-entry and cumulative resource ceilings before allocation/decompression, stream if a later task justifies it.
- **Returning one generic `INVALID_MEDIA` for every cause:** distinguish missing file/member, incompatible BIOS/profile, unsupported set/feature, malformed archive, exceeded resource limits, decompression/CRC failure, and allocation failure at the importer boundary. Native statuses should remain stable and small; adapter-specific detail can be represented by a private error enum/message.
- **Mutating CPU/device/media state during validation:** failed load can poison the instance. Parse/allocate/validate privately, then commit atomically; test fail-then-load-valid and fail-then-destroy paths.
- **Treating CRC32 or archive validity as media authenticity:** CRC detects accidental corruption but is not cryptographic authentication and says nothing about compatibility or rights.
- **Using MAME agreement as a silicon oracle:** implementations can share sources/assumptions; cite ancestry and retain hardware unknowns.
- **Building all MVS/AES/board families before first boot:** scope explosion. Gate by selected title profile and actual guest boot demand.
- **Changing historical Phase 04 evidence while starting Phase 05:** Phase 05 results cannot rewrite open threat decisions or actual frontend unknowns.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DEFLATE decoding | Custom Huffman/DEFLATE implementation | Pinned zlib `inflateInit2` raw mode | ZIP embeds raw DEFLATE; zlib documents negative `windowBits` for raw streams and ZIP carries the integrity check. Hand-writing DEFLATE is explicitly out of scope. [CITED: https://www.zlib.net/manual.html#inflateInit2] |
| General ZIP interoperability | A new general-purpose archive framework | Either a tiny constrained reader for only the required ZIP32 profile or a mature archive library if demonstrated required features demand it | ZIP has a large evolving surface (Zip64, descriptors, many methods, encryption and central-directory extensions). Do not claim broad compatibility from a narrow parser. |
| 68000 ISA completeness | An ad hoc title-specific opcode shortcut | Continue the owned CPU with independently testable instruction/addressing/bus behavior; each added subset needs source-qualified regressions | The selected program can exercise many coupled opcodes and exception paths; reaching one target without general CPU semantics is brittle. |
| Full board model | Copying MAME's entire machine or adding a general emulator framework | Small per-instance MVS devices and bus behavior needed by the selected profile | Broad source reuse carries license/build/architecture costs and obscures the current evidence boundary. |
| ROM set database | Silent home-grown universal database/matcher | One explicit MVS profile manifest tied to exact pinned source metadata; add database only after more than one profile requires it | Hash tables/clone inheritance and license/provenance add long-term obligations. |

**Key insight:** Do the hard work at one hostile boundary and one machine profile, with a strict “unsupported” answer elsewhere. A few auditable ZIP metadata reads plus established inflate are preferable to either a homegrown compressor/decompressor or a large general archive stack, as long as coverage tests and a conversion fallback are real.

## Common Pitfalls

### Pitfall 1: ZIP central-directory and local-header mismatch

**What goes wrong:** A parser may use an attacker-controlled local offset or size that overlaps metadata, overflows, points outside the archive, or disagrees with the central directory.  
**Why it happens:** ZIP permits central-directory and streaming data-descriptor structures; the EOCD offset/count/size fields and local records are distinct.  
**How to avoid:** Validate EOCD tail/comment extent, directory count/size/offset, each record's variable-field lengths, member extents, local signature/name/method/flags, optional descriptor behavior, and non-overlap before inflate. Reject multi-disk/Zip64 if not implemented. Fuzz every parser state and addition boundary. [CITED: https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT]  
**Warning signs:** Acceptance changes when a ZIP tool rewrites metadata; huge declared size causes allocation; duplicate names pick different members in different tools; empty/truncated files crash or hang.

### Pitfall 2: DEFLATE output does not match advertised extent

**What goes wrong:** A short stream, trailing garbage, decompression bomb, wrong CRC or wrong output length is accepted.  
**Why it happens:** zlib raw inflate does not apply the ZIP CRC itself; ZIP stores sizes/checksum separately.  
**How to avoid:** Bound input/output before inflate; require `Z_STREAM_END`, exact total output and acceptable total input consumption, CRC32 match, no overrun/trailing ambiguity, and known method. Test zero-length, truncated stream, output one byte too long/short, bad CRC, and repeated inflate failures. [CITED: https://www.zlib.net/manual.html#inflateInit2]  
**Warning signs:** A successful inflate is treated as proof of valid member; `Z_BUF_ERROR` becomes silent EOF; output is appended before all validation completes.

### Pitfall 3: Frontend content lifetime/path assumptions

**What goes wrong:** Adapter retains a frontend pointer past `retro_load_game`, assumes path always exists, assumes ZIP extraction behavior, or relies on unannounced VFS behavior.  
**Why it happens:** libretro supports memory and path modes, path can be null in memory mode, and content persistence extensions vary.  
**How to avoid:** Default toward `need_fullpath=false` where the selected content sizes permit; set/document `block_extract` if the core must receive archive bytes; copy content before returning unless persistence is negotiated; retain a documented import fallback. Tests with a mock prove ABI contracts only, not the pinned RetroArch product path. [CITED: https://docs.libretro.com/development/cores/developing-cores/]  
**Warning signs:** Works via CLI but not Load Content; game data pointer use after load; behavior depends on filename extension instead of bytes.

### Pitfall 4: MVS interleave/word-swap errors look like CPU faults

**What goes wrong:** The wrong bytes appear in 68000 program memory, reset vectors are invalid, fixed layer/sprites are scrambled, or data appears correct only under one host endian.  
**Why it happens:** MAME declarations encode word-swapping and byte lanes as load transforms; raw archive member bytes are not equivalent to mapped bus bytes.  
**How to avoid:** Document each transform with source order, address lanes, endian reads and resulting byte-addressed map. Unit-test transforms on tiny synthetic patterns with expected bytes at both lanes and neighboring addresses, then test pinned title map metadata independently from guest execution. [CITED: https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp#L8640-L8661]  
**Warning signs:** Native little-endian host passes but big-endian emulation semantics differ; whole-word casts hide byte order; MAME load macros are copied without modeling transform meaning.

### Pitfall 5: BIOS/profile compatibility inferred from archive integrity

**What goes wrong:** Correct ZIP CRC or file presence is described as a compatible BIOS.  
**Why it happens:** A set can contain multiple region/revision BIOS members, and board/game support is separate from archive validity.  
**How to avoid:** Match the selected BIOS to an explicit MVS configuration using pinned public metadata in a private local run; report exact reason without revealing private member names/digests. Test missing BIOS, known incompatible profile, ambiguous alternatives, and wrong-size data using synthetic fixtures. Preserve “unknown” when no authoritative mapping exists.  
**Warning signs:** “BIOS found” is the only acceptance assertion; default first-match behavior; a failed boot causes silent fallback to another BIOS.

### Pitfall 6: The game boot target encourages fake progress

**What goes wrong:** Title-specific skips, canned attract output, forced PC jumps, fake Z80 acknowledgments or optimistic interrupt behavior make the target appear reached.  
**Why it happens:** CPU, bus timing, BIOS, protection and sound-CPU synchronization failures are tightly coupled and game boot may be the first large program.  
**How to avoid:** Capture failing guest checkpoints, isolate the first divergent observable, and add a unit/integration regression for every implemented dependency; do not bypass guest execution. If the feature gap is large, record a bounded replan instead of weakening GAME-02.  
**Warning signs:** Only screenshot/hash tests; no guest PC/bus/watchpoint evidence; CPU execution counters remain zero while “boot success” passes.

## Code Examples

### Raw DEFLATE from ZIP with zlib (API pattern)

zlib 1.3.2 manual states `inflateInit2` supports `windowBits` from `-8` through `-15` for raw DEFLATE and that ZIP has its own check value. The stream must still be bounded and CRC/size-checked by the ZIP layer. [CITED: https://www.zlib.net/manual.html#inflateInit2]

```c
z_stream stream = {0};
int rc = inflateInit2(&stream, -MAX_WBITS); /* raw DEFLATE, ZIP wrapper owns CRC */
if (rc != Z_OK) return MEDIA_DECOMPRESS_ERROR;

stream.next_in = compressed;
stream.avail_in = (uInt)compressed_size; /* first prove it fits uInt */
stream.next_out = expanded;
stream.avail_out = (uInt)expanded_capacity; /* bounded profile allocation */
rc = inflate(&stream, Z_FINISH);
bool ok = rc == Z_STREAM_END && stream.total_out == expected_size &&
          stream.total_in == compressed_size;
(void)inflateEnd(&stream);
if (!ok) return MEDIA_DECOMPRESS_ERROR;
/* Independently compute ZIP CRC32 over exactly expected_size bytes. */
```

This is a pattern, not production-ready code: handle zlib integer-width limits, 0-sized entries, `Z_BUF_ERROR`, overflow, all cleanup paths, CRC32, and output-budget accounting before use.

### Libretro content boundary

The current adapter declares `need_fullpath = false` and `block_extract = false` and accepts only in-memory GNFX data. [VERIFIED: `src/libretro/libretro_core.c:80-87`] Verbatim: “info->valid_extensions = \"bin\";”; “info->need_fullpath = false;”; “info->block_extract = false;”. Libretro docs say memory mode permits `path == NULL`; path mode makes the adapter responsible for reading content. Keep archive/filesystem handling in the adapter/host layer, and test either (a) in-memory archive bytes after explicitly requesting `block_extract`, or (b) a deliberately documented importer/preconverted file flow. Do not claim the actual RetroArch route until observed with the pinned app. [CITED: https://docs.libretro.com/development/cores/developing-cores/]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Assume ZIP is a flat list of local headers | Use EOCD + central directory metadata and validate local member extents | In ZIP's established record model; current APPNOTE version 6.3.10 | Correct handling of member offsets and rejection of malformed/multi-feature archives. |
| Implement decompression alongside parser | Use established zlib inflater and a narrow parser allowlist | Existing project requirement | Reduces correctness/security burden while limiting dependency count. |
| Treat `need_fullpath` as always available | Prefer memory mode where feasible; path may be absent, data lifetime must be respected | Current libretro API guidance | Robust to stdin/frontends/patching and avoids stale pointers. |
| Treat reference emulator as truth | Pin emulator commit and disclose ancestry/unknowns; seek physical evidence separately | Current project evidence contract | Agreement remains implementation-level evidence, not original-hardware proof. |

**Deprecated/outdated:** Do not use the old preparation suggestion that a directory importer can wait until after general gameplay; current MEDIA-03 explicitly makes archive loading part of Phase 05. Do not use unpinned `master` URLs for implementation decisions when exact revisions are available.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A constrained in-memory ZIP32 reader plus zlib is sufficient for the selected local archive/import workflow. | Summary, Standard Stack | If the selected RetroArch path requires ZIP64, exotic member encoding, or broader import layouts, implementation will need full library or documented conversion. Confirm using a synthetic/public fixture and actual private local run without publishing identity. |
| A2 | The selected game data can be normalized from the pinned MAME set description without redistributable commercial bytes. | Architecture Patterns | MAME may not match the user's exact revision/region or archive structure; private local comparison must establish match and retain uncertainty. |
| A3 | One MVS BIOS profile and one MVS board revision will suffice for the accepted scenario. | Phase Requirements | Wrong selection blocks boot or changes BIOS behavior; exact private identity selection remains a local qualification task. |
| A4 | CMake can build pinned zlib as a small private C target on the selected macOS toolchain and other currently supported build targets. | Standard Stack | May require source build adaptation; verify compile/link, static/shared consumer, and installed artifact. |
| A5 | MAME public source is adequate as a differential implementation oracle for title-specific boot behavior where direct expected outputs are unavailable. | Summary, Pattern 4 | Shared ancestry or MAME uncertainty can conceal defects; label oracle ancestry, use independent CPU/memory expectations where possible, and never claim hardware fidelity. |

## Open Questions (RESOLVED FOR PLANNING; evidence outcomes remain conditional)

1. **Which exact MVS BIOS configuration is the first supported profile?**
   - What we know: User supplied local BIOS archive; current research says archive integrity was previously checked, but no compatibility/identity claim is established here. The selected phase requires one documented MVS profile.
   - What's unclear: Which BIOS set member/configuration is correct for the selected MVS board/game revision and what switching semantics are required.
   - Recommendation: Plan a private local selection/verification step against the exact pinned MAME machine metadata and a guest boot checkpoint; store identities only in ignored local output; avoid recording any private digest/path in tracked artifacts.
   - **Planning status: RESOLVED.** Derive one profile from the pinned MAME metadata and require a private local compatibility match before claiming it; if the supplied media cannot be matched, keep the affected MEDIA/GAME requirement open. This resolves the selection procedure, not the private compatibility result.
2. **How will the pinned RetroArch pass content?**
   - What we know: Current adapter uses memory mode with archive extraction allowed; docs recommend `need_fullpath=false`; `block_extract` can request unextracted archives.
   - What's unclear: The actual pinned macOS frontend behavior for chosen extensions, archive selection/member naming, VFS and ZIP support has not yet been observed.
   - Recommendation: Begin with a mock callback contract and a documented importer route; include actual pinned-app test as a narrow manual evidence task, not a premise for native media parser work.
   - **Planning status: RESOLVED.** Deliver the standalone normalized-bundle import path and callback contract independently. The direct pinned RetroArch observation remains manual-only; callback evidence alone does not complete MEDIA-03 or Phase 04 HOST-02/QUAL-03.
3. **What are acceptable phase-specific resource ceilings?**
   - What we know: Current native diagnostic media cap is 1 MiB; the MAME title map declares multi-megabyte regions.
   - What's unclear: Peak normalized memory (compressed input + expanded archive members + final native copies) and desired target-device budget.
   - Recommendation: Derive named per-entry, per-region, archive-total, selected-profile-total, and transient-peak limits from public MAME region sizes with checked sums. Make decompression one member at a time if peak allocations otherwise exceed the chosen limit. Record as profile limits, not universal core guarantees.
   - **Planning status: RESOLVED.** Set and test explicit profile-specific ceilings from the public region map and measured peak allocation before accepting input; do not inherit the diagnostic 1 MiB ceiling or claim a universal bound.
4. **Does the actual selected BIOS boot need protection outputs not independently documented?**
   - What we know: Pinned MAME has an `mslugx` protection device and labels one selector calculation unresolved.
   - What's unclear: Whether this code path and exact response values are required before attract/start on the user's revision.
   - Recommendation: Instrument a private local MAME/guest run and add bounded regression tests for the observed command/response sequence; call it emulator differential evidence and leave physical behavior open.
   - **Planning status: RESOLVED.** Implement only the guest-observed path and pin MAME as differential evidence; use direct expected controls for generic device semantics. Keep unresolved source behavior and hardware truth open, and leave GAME-02 pending if the attract/start path depends on unsupported or uncertain behavior.
5. **When should a full archive library replace the small reader?**
   - What we know: ZIP has extensible feature surface; the chosen requirement permits bounded parsing and asks for established decompression.
   - What's unclear: Actual set/tool-generated ZIP features and frontend data path.
   - Recommendation: Use a feature census from synthetic fixtures and nonprivate documented archive variants; only expand features or adopt libzip/libarchive when a specific required input is rejected. Do not silently accept a feature before tests exist.
   - **Planning status: RESOLVED.** Use the accepted ZIP32 subset plus pinned zlib 1.3.2; do not add a general archive dependency or handwritten DEFLATE. Keep unneeded ZIP features explicitly unsupported and stop for a new scoped decision only if the actual required input needs them.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| C compiler / CMake / Ninja | Native and frontend adapter build | ✓ | Existing CMake presets; exact values not recorded in this research pass | Project's existing CMake build tooling |
| zlib source | ZIP method 8 | Not yet added to repository | Pin `v1.3.2` / `da607da739fa6047df13e66a2af6b8bec7c2a498` | Documented pre-import path; do not implement DEFLATE |
| RetroArch pinned macOS app | Actual content-path evidence | Not observed in this research pass; Phase 04 receipt keeps actual GUI evidence manual-only/unknown | Target previously specified as RetroArch 1.22.2 in current workstream evidence | Native importer + GUI-free libretro harness; actual HOST/frontend claim remains open |
| MAME reference source | Region map/differential debugging | ✓ via public source at pinned commit | `31e52312c59e4d60d70235118bcbccd220f5232e` | None needed for source inspection; no assumption of physical truth |
| Private game/BIOS media | Local GAME-02 scenario only | Present by project state; private bytes intentionally not read or reported in this research pass | No private identity included | Synthetic public fixture for CI; local qualification requires owner-supplied files |

**Missing dependencies with no fallback:** None for planning; actual RetroArch behavior cannot be substituted by the mock and remains an explicit future manual evidence task.

## Validation Architecture

Nyquist validation is enabled in the project configuration. Existing test framework is CTest with pinned Unity for C; Python standard-library unittest is also established for tooling. [VERIFIED: `CMakePresets.json:1-33`] Verbatim: `"testPresets"` names include `owned-debug` and `sdk-debug`, and both set `"noTestsAction": "error"`. [VERIFIED: `.planning/config.json:28-29`] Verbatim: `"build_command": "cmake --preset owned-debug && cmake --build --preset owned-debug"`; `"test_command": "ctest --preset owned-debug"`. Use the relevant SDK/owned preset(s) for new targets.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | CTest + existing Unity C unit-test dependency; Python unittest for import/tool contract tests |
| Config file | `CMakeLists.txt`, `CMakePresets.json`; existing `tests/` layout |
| Quick run command | After plan creates targets: `ctest --test-dir build/sdk-debug --output-on-failure -R 'media|mvs'` (pattern is proposed; ensure test names match registered targets) |
| Full suite command | `ctest --preset sdk-debug` plus relevant Python unit tests and consumer checks |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MEDIA-02 | Exact MVS profile region set, bounds, byte layout/interleave, source immutability, copy/retention lifetime, load reset/unload | unit + native C consumer | `ctest --test-dir build/sdk-debug --output-on-failure -R 'media|mvs'` | No — Wave 0 / first plan |
| MEDIA-03 | ZIP32 EOCD/central-local consistency, stored/DEFLATE decode, CRC, unsupported features, limit boundaries, no archive mutation; libretro callback path | unit + fuzz + GUI-free integration; actual RetroArch manual-only | same focused CTest target plus libretro callback harness | No — Wave 0 / first plan |
| MEDIA-04 | Distinct missing/incompatible/unsupported/malformed/limit/decompression errors; fail-then-valid-load and fail-then-destroy | stateful integration + fault injection | focused CTest target and consumer executable | No — Wave 0 / first plan |
| GAME-02 | Guest-driven BIOS/title boot checkpoint, CPU/bus/banking/IRQ/protection/Z80 handshake assertions with wrong behavior controls | unit + integration; private local run outside public CI | focused `mvs_boot` CTest target; local opt-in scenario command (must not print identities) | No — staged after profile/media foundation |

### Sampling Rate

- **Per task commit:** focused target(s) for the touched media/MVS module.
- **Per wave merge:** all CTest targets and public synthetic importer tests.
- **Phase gate:** full SDK/debug and owned CPU regression suites, static and shared installed C consumers, relevant ASan/UBSan, parser fuzz corpus/regressions, independent code/security review; private RetroArch observation stays explicit and separate.

### Wave 0 Gaps

- [ ] Synthetic ZIP fixture builder/corpus with stored and DEFLATE entries, malformed headers and boundary values; no proprietary data.
- [ ] Media importer/parser API and profile-specific MVS region descriptors; current public manifest is diagnostic-only.
- [ ] Fuzz target for bounded ZIP parsing and normalized manifest validation.
- [ ] MVS bus/boot test harness with synthetic BIOS/cart bytes and checkpoint tracing.
- [ ] No test should encode the private game archive's filename, checksum, contents, or derived outputs.

## Security Domain

Security enforcement is enabled, ASVS Level 1. This is a native C/archive boundary, so web authentication/session controls are not applicable; input validation/resource exhaustion/file handling are central. ASVS 5.0.0 identifies itself as a standard for web applications and services; apply its V1/V5 file-handling lessons by analogy only, not as an emulator certification. [CITED: https://owasp.org/projects/asvs] [CITED: https://github.com/OWASP/ASVS/blob/master/5.0/en/0x14-V5-File-Handling.md]

### Applicable ASVS Categories

| ASVS 5.0.0 Category | Applies | Standard Control |
|----------------------|---------|-----------------|
| V1 Encoding and Sanitization | Partial | Canonicalize and validate archive names before policy decisions; do not reflect unsafe names into diagnostics. |
| V5 File Handling | Yes, by analogy to hostile file processing (the standard itself targets web apps/services) | Document accepted ZIP profile and compressed/expanded limits; ignore archive paths and prevent zip-slip; reject malformed or unsupported files. |
| Authentication, session, API/web-service and browser controls | No | This native importer/core has no user account, web session, network endpoint, or browser surface. |

### Known Threat Patterns for Native Media Handling

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Integer wrap in offsets, sizes, allocation totals | Tampering / DoS | Checked addition/multiplication and input-span helper before pointer arithmetic |
| ZIP bomb / excessive entries / oversized media | DoS | Independent per-archive/member/region/aggregate/transient budgets; reject before allocate/decompress |
| Duplicate/case-colliding names or central/local mismatch | Tampering | Reject ambiguous entries and validate both records/extents before use |
| Path traversal or symlink extraction | Tampering / Elevation | Never extract to filesystem; treat names as bounded identifiers only; reject traversal/special members |
| CRC mismatch / truncation / unsupported encryption | Tampering | Validate CRC, exact stream and sizes; explicit unsupported/malformed errors; no fallback to unverified data |
| Failed partial load leaves stale media or device state | Tampering / availability | Transactional load and stateful fail-then-valid recovery tests |
| Private input details leak through diagnostic output | Information disclosure | Generic public errors; local output redaction and no private path/hash/name in tracked receipts |

## Package Legitimacy Audit

No ecosystem registry package is recommended. zlib is an upstream C source dependency, not an npm/PyPI/crates package; the npm legitimacy probe would be the wrong registry and was intentionally not used. Verify upstream tag/commit, license notice, and static/shared C-consumer linkage at integration time. zlib 1.3.2 release notes identify security and ZIP-related fixes in bundled minizip/miniunz, which is another reason to pin the current upstream release rather than reuse an old system copy. [CITED: https://github.com/madler/zlib/releases]

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| zlib 1.3.2 | Upstream C source, not a package registry | Released 2026-02-17 | N/A | github.com/madler/zlib at `da607da739fa6047df13e66a2af6b8bec7c2a498` | N/A | Recommended only for DEFLATE inflate; preserve license and pin source |

**Packages removed due to [SLOP] verdicts:** None.  
**Packages flagged as suspicious [SUS]:** None.

## Sources

### Primary (official specification, upstream docs or source)

- [PKWARE APPNOTE 6.3.10](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT) — ZIP local/central records, EOCD, data descriptors, flags, Zip64, sizes and method registry; access date 2026-10-09.
- [zlib 1.3.2 release](https://github.com/madler/zlib/releases) — version/date/release changes; exact tag commit via upstream Git; access date 2026-10-09.
- [zlib manual, `inflateInit2`](https://www.zlib.net/manual.html#inflateInit2) — raw DEFLATE API, return codes and stream bounds; access date 2026-10-09.
- [Libretro core development documentation](https://docs.libretro.com/development/cores/developing-cores/) — `need_fullpath`, `retro_load_game`, content data and frame callback semantics; access date 2026-10-09.
- [Pinned libretro-common source](https://github.com/libretro/libretro-common/tree/2b96a82bd8479bb3547d271e1eefadc82dd2161e) — exact header ABI surface for `retro_system_info`, `retro_game_info` and `block_extract`.
- [Pinned MAME Neo Geo driver](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/mame/snk/neogeo.cpp) — MVS/title region mappings and load transforms.
- [Pinned MAME Metal Slug X protection source](https://github.com/mamedev/mame/blob/31e52312c59e4d60d70235118bcbccd220f5232e/src/devices/bus/neogeo/prot_mslugx.cpp) — device state/commands and explicit uncertainty comment.
- [Motorola MC68000 User's Manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) — CPU programming and bus semantics; use only for the applicable subset, not Neo Geo board wiring.
- [OWASP ASVS 5.0.0 V5 File Handling](https://github.com/OWASP/ASVS/blob/master/5.0/en/0x14-V5-File-Handling.md) — hostile file handling and decompression-boundary guidance; web-app standard applied by analogy only.

### Project-local source of truth

- `.planning/workstreams/first-playable-game/REQUIREMENTS.md` — current approved requirements and acceptance boundaries.
- `.planning/workstreams/first-playable-game/ROADMAP.md` — Phase 05 dependency permits forward engineering while Phase 04 blockers remain open.
- `.planning/workstreams/first-playable-game/RESEARCH.md` — accepted milestone choices; archive boundary, no handwritten DEFLATE, pinned reference use, privacy.
- `.planning/preparation/DECISIONS.md` — importer identity, explicit manifest and informative-error recommendation.
- `include/glueyneo/glueyneo.h` — exact current API/profile/limit/status definitions; diagnostic scope only.
- `src/libretro/libretro_core.c` — current fixture adapter policy; not an MVS loading implementation.
- `CMakePresets.json`, `.planning/config.json`, `AGENTS.md` — build/test/security and project constraints.

## Project Constraints (from AGENTS.md)

- C17 owned runtime and selected runtime dependencies by default; `ymfm` is the sole narrow C++14 exception and does not change this media work.
- Keep core independent of frontend, filesystem, audio device, graphics API, network, secrets and wall clock; use opaque per-instance state and explicit buffers, errors, ownership and deterministic time.
- Audit every reused engine's mutable globals/callbacks/state; a context API alone does not prove reentrancy.
- Prefer small, flat dependency trees and simple local code for understandable functionality; if copying code, pin/license/audit it and retain provenance/update ownership. Add a dependency only where concrete value justifies its full tree.
- Use explicit byte order, checked integer/resource limits, evidence-backed hardware comments, and avoid speculative frameworks/optimizations.
- Separate emulator/hardware behavior from host pacing and do not silently change original slowdown.
- Keep save states, durable saves, replay contracts and public ABI versions distinct; no snapshot claims in this phase.
- Pair behavioral changes with automated evidence/docs; retain exact source/tool/input identity and oracle ancestry. Record unsupported/skipped/unknown explicitly; do not tune away failures.
- Commercial media/BIOS and private checksums, captures and outputs must remain outside Git/public CI/releases; hashes do not establish rights.
- Follow current GSD workstream contracts and pause at workflow boundaries. Phase 05 can progress while Phase 04 remains In Progress; never reinterpret Phase 04 evidence.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for CMake/CTest and official zlib/Libretro source APIs; MEDIUM for preferred importer implementation until the pinned frontend path is exercised.
- Architecture: MEDIUM; strong project-boundary fit, but region descriptors and BIOS selection remain unimplemented.
- Pitfalls: HIGH for ZIP structural complexity and raw-DEFLATE requirements; MEDIUM for title-specific MVS boot dependencies until a private guest trace confirms the minimum path.

**Research date:** 2026-10-09  
**Valid until:** 2026-11-08 for stable ZIP/API architecture; recheck zlib release/current Libretro header and MAME source when plans pin their exact implementation inputs.
