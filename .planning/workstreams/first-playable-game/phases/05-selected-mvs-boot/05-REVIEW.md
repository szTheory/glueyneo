# Phase 05 Independent Review

Review scope: current Phase 05 importer, normalized bundle/native MVS path,
synthetic test seams, callback contract, and local qualification output. The
reviewer did not inspect or print private media and did not claim GUI or
hardware observation.

## Findings and disposition

| Finding | Severity | Disposition |
|---|---|---|
| Local ZIP extra-field parsing could read beyond the validated local-record variable span. | Blocker | Fixed before task close: validate the full local name-plus-extra span before inspecting extra fields; added a `local_extra_oob` malformed-archive regression. Focused debug and ASan/UBSan importer tests pass. |
| Importer/API transform did not prove a coherent normalized program byte order. | Blocker | Fixed: validate CRC over archive bytes, then normalize the program's adjacent byte lanes in the importer; the synthetic imported bundle is consumed as LINEAR and the native bus asserts the expected word. |
| CTest names for media, callback, and boot had all run the same combined path. | Warning | Fixed: distinct `mvs_test` modes now isolate media ownership/recovery, callback reload, and synthetic boot; CTest targets invoke the corresponding mode. |
| An EOCD-shaped sequence inside the ZIP comment could mask the real EOCD. | Warning | Fixed: parse every end-of-file candidate fully, accept exactly one structurally valid candidate, and reject multiple valid candidates as ambiguous. A regression uses a six-entry, zero-size decoy with an offset at its own location. Independent re-review confirmed the fix. |
| Importer acceptance identifies a structural region bundle by names, roles, and lengths but does not authenticate selected cartridge/BIOS revision contents. | Blocker to selected-media qualification | Remains open and explicit. No private/public selected identity allowlist was added. The documentation makes no selected-content compatibility claim; MEDIA-04 remains Pending, and MEDIA-03/GAME-02 remain Pending. The local run stopped before native load at `archive_to_region_mapping`. |

The structural `GNMV` contract remains useful for synthetic and C-consumer
testing; it is not evidence that a selected private media set is compatible.
No phase acceptance claim is based on the callback test alone.

## Threat-model evidence

| Plan threat | Evidence / disposition |
|---|---|
| T-05-01, untrusted ZIP metadata | Checked local/central spans, exact sizes, duplicate/overlap/feature rejection, CRC and decompression checks, malformed mutations, fuzz corpus, ASan/UBSan. |
| T-05-02, resource exhaustion | Profile input/member/expanded/output caps, bounded CPU runs, allocator failure test, checked arithmetic, and bounded mutation corpus. |
| T-05-03, private-data disclosure | Generic CLI/importer errors; local report path is ignored; report contains only generic status/checkpoint/dependency; no ROM-derived output is tracked. |
| T-05-04, failed load corrupts instance | Synthetic tests show rejected allocation/media loads preserve the accepted image and allow valid recovery. |
| T-05-05, emulator output mistaken for hardware truth | MAME is identified as pinned differential metadata only. Title execution and protection behavior remain unobserved; GAME-02 stays Pending. |
| T-05-06, archive path traversal | Importer does not extract; names are bounded and restricted to safe canonical role identifiers. |
| T-05-07, private identity disclosure | No identity is emitted. Identity verification itself remains an explicit compatibility gap, not a completed mitigation claim. |
| T-05-SC, dependency provenance/isolation | Vendored zlib 1.3.2 source/license is pinned and limited to importer targets; static/shared package and consumer checks pass. |

Phase 04 artifacts and verdict were not changed by the review or this plan.
