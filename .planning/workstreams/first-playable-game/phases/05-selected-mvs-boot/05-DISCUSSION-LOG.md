# Phase 05: Selected MVS Boot - Discussion Log

> **Audit trail only.** Decisions are captured in `05-CONTEXT.md`.

**Date:** 2026-10-08
**Phase:** 05-Selected MVS Boot
**Areas discussed:** Phase sequencing, native media contract, archive/import boundary, profile identity, errors and security, boot verification

The user asked for broad role-based analysis and accepted recommendations. The GSD `--auto` path selected the recommended option for each area. Phase 04 acceptance and open threats remain unchanged.

---

## Phase sequencing and evidence gates

| Option | Description | Selected |
|--------|-------------|----------|
| Stop all later-phase work until Phase 04 is accepted | Preserves strict sequencing but waits indefinitely on external/user-directed gates even where verified artifacts suffice. | |
| Proceed on verified technical artifacts while keeping Phase 04 blockers open | Separates implementation dependency from acceptance/signoff; requires an explicit roadmap amendment and independent evidence. | ✓ |

**Selected recommendation:** Proceed with Phase 05 engineering while Phase 04 remains `gaps_found`; never transfer or close Phase 04 evidence.

## Native media contract

| Option | Description | Selected |
|--------|-------------|----------|
| Widen manifest v1 in place | Fewer API entry points, but changes the existing fixed public struct and fixture contract. | |
| Add a versioned MVS-specific contract | Preserves the verified diagnostic/fixture ABI and gives MVS regions explicit types/lifetimes. | ✓ |

**Selected recommendation:** Add a bounded, versioned MVS manifest/API and retain v1 semantics.

## Archive/import boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Parse ZIP inside the native core | Violates host-independent core boundary. | |
| Add a C archive library or broad libarchive dependency | Established code, but adds runtime/build/transitive and license/update costs. | |
| Use a standalone C17 ZIP32-to-normalized-bundle importer with a bounded local container reader and pinned zlib 1.3.2 for DEFLATE | Adds one justified leaf dependency and keeps Python, archive parsing, file I/O, and zlib out of the native core and Libretro adapter. The normalized package path avoids relying on unobserved frontend ZIP extraction behavior. | ✓ |
| Use a Python standard-library importer | Avoids a new native dependency but makes Python a user-facing runtime prerequisite and still leaves the actual supported package/load contract to define. | |
| Implement DEFLATE locally | Avoids a dependency but creates a large, security-sensitive codec implementation; rejected by project policy. | |

**Selected recommendation:** Keep one constrained ZIP32 parser in the host-side importer and use upstream zlib as its single DEFLATE dependency. Preserve zlib's exact source/license/update record and isolate its linkage to the importer target. The bundle and frontend callback remain separately tested; actual pinned RetroArch observation stays manual-only until a functioning environment is available.

## Profile identity and BIOS

| Option | Description | Selected |
|--------|-------------|----------|
| Select by filename or archive label | Simple but accepts renamed/wrong media and does not identify a revision. | |
| Select one profile from pinned public metadata and content identity | Verifiable while keeping user-supplied bytes and private hashes local. | ✓ |

**Selected recommendation:** Derive exact region and BIOS requirements from a pinned public source, then verify provided local bytes privately; report unresolved compatibility as unknown.

## Errors, security, and recovery

| Option | Description | Selected |
|--------|-------------|----------|
| One generic load failure | Small interface but not actionable or diagnostic. | |
| Distinct bounded status categories and privacy-safe messages | Supports recovery and media diagnosis without revealing private paths or data. | ✓ |

**Selected recommendation:** Distinguish missing, malformed, unsupported, incompatible, limit, allocation, and core-load failures; test failed-load recovery and preserve redaction.

## Boot verification

| Option | Description | Selected |
|--------|-------------|----------|
| Treat MAME agreement as machine truth | Faster but overstates a differential implementation. | |
| Use synthetic contract tests plus source-qualified private boot evidence | Separates parser/API correctness, emulator agreement, private target behavior, and hardware truth. | ✓ |

**Selected recommendation:** Start with rights-clear synthetic media, then qualify selected guest behavior against pinned MAME evidence and keep hardware uncertainty explicit. Actual RetroArch remains unknown until directly observed.

## the agent's Discretion

- Set resource caps from pinned public region sizes plus tested headroom.
- Keep tests in existing CMake/CTest and Python tooling; no second framework.
- Use a fuzz target only for the hostile parser/bundle surface with fixed runtime bounds.

## Deferred Ideas

- Active-scene control, broad video, and audible game sound remain in Phases 06 and 07.
- AES, general cartridge support, and arbitrary archive formats remain out of scope.
