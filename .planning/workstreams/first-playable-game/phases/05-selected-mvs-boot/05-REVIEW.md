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
| Selected-media qualification has not been demonstrated with an exact local pair or a selected guest run. | Blocker to selected-media qualification | The 05-02 importer now validates the public MAME `mslugx` member identities and the selected `sp-s2.sp1` BIOS identity before mapping. The local run found no supported game/BIOS pair, so no selected content reached the native runner. The documentation makes no boot-compatibility claim; MEDIA-03, MEDIA-04, and GAME-02 remain Pending. |

The structural `GNMV` contract remains useful for synthetic and C-consumer
testing. The selected-source profile now checks exact public source identities,
but its synthetic proof and local absence of a supported private pair do not
establish selected guest compatibility. No phase acceptance claim is based on
the callback test alone.

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

## Plan 05-02 Independent Review

**Reviewed:** 2026-10-09
**Scope:** `tools/mvs/mvs_import.c`, `tools/mvs/qualify_local_boot.py`, `tests/mvs/test_mvs_qualification.py`, `docs/mvs-media.md`, `tools/verify_sdk.py`, `tools/sdk_evidence.py`, and `tests/sdk/test_matrix_evidence.py`.
**Verdict:** WR-01 is fixed on re-review; no remaining actionable findings in the reviewed implementation.
**Revision status:** The reviewed checkout is uncommitted. Findings apply to the live working-tree contents and cannot be attributed to a stable commit. `tests/sdk/test_matrix_evidence.py` was in the requested scope but was not modified in the current worktree.

### WR-01: Wrapper report temporary file is predictable — Fixed

**Original severity:** WARNING
**File:** `tools/mvs/qualify_local_boot.py:194-205`
**Resolution:** The wrapper now uses `NamedTemporaryFile(delete=False)` in the report directory, writes and closes the unique file before `os.replace`, and removes it if publication fails. This avoids the fixed-name collision and pre-existing symlink issue. Re-review was source inspection only; no tests were run in this pass.

### Review notes

- The selected C importer bounds and validates ZIP32 metadata, rejects unsupported or duplicate entries, validates expanded CRC and pinned member identities before mapping, and publishes the completed bundle through an exclusive sibling temporary file followed by rename.
- The local wrapper selects game and BIOS archives from content identities, constrains the report to the ignored local path, emits only sanitized status/checkpoint data, and now uses unique exclusive temporary report output with cleanup on failure. No private media was opened or reported during this review.
- The SDK matrix lane selects the exact seven named MVS CTests, requires a matching positive denominator, binds the lane to the current source revision and relevant-source digest, and records an output digest. The seven names match the CMake MVS test registrations.
- The source digest inventory includes the new importer, wrapper, docs, MVS qualification tests, SDK evidence collector, and matrix validation code. The seven-file review scope was read from the current working tree; uncommitted status prevents independent attribution to a phase commit.
- Phase 04 dispositions remain unchanged: its directed open threats and manual-only frontend observations remain open/unknown; this review does not close or accept any of them.

## Plan 05-03 Review Note

The smoke-runner change accepts only the bounded version-1 MSX GNMV envelope
with each known role exactly once and at its profile-specific size. Selected
content identity records only `content_kind`; it omits hashes and paths. The
public GNFX branch retains its pinned size, version, and digest checks. The
selected branch does not claim a responsive input result: it reports that
result as unknown and exits nonzero, so screenshots or key injection cannot
be mistaken for selected-title acceptance.

GUI-free tests use generated zero-filled region bytes and reject missing or
wrong-sized bundles before process launch. They do not run RetroArch or prove
selected media mapping, game behavior, actual frontend launch, or hardware
fidelity. The local selected guest remains blocked at archive-to-region
mapping; no CPU or board behavior was inferred. G-05-3, G-05-5, and the actual
app row remain unaccepted pending their stated evidence.

An independent review of this smoke-runner diff first found an oversized-read
race: a GNMV could grow after `stat()` and cause an unbounded read. The runner
now reads at most `GNMV_MAX_BYTES + 1` bytes, and the synthetic sparse oversized
input test confirms rejection before process launch. The reviewer rechecked
the fix and found no new actionable issues. This review covers only the
smoke-runner change; no new CPU or board semantics were added. Hosted
current-SHA evidence and the required CPU/board review remain open.
