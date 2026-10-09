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
| The selected guest has not reached attract/start. | Blocker to selected-media qualification | The exact configured pair imports and executes in the native runner. The 256-chunk run exhausted its bound without attract/start or an unsupported event. Sanitized chunk profiles show output/latch, video, and bank state transitions but no source-defined checkpoint predicate. MEDIA-03, MEDIA-04, and GAME-02 remain Pending. |

The structural `GNMV` contract remains useful for synthetic and C-consumer
testing. The selected-source profile checks exact public source identities,
and the configured pair reaches native guest execution. Its bounded run and
synthetic proof do not establish selected guest compatibility. No phase
acceptance claim is based on callback or local execution alone.

## Threat-model evidence

| Plan threat | Evidence / disposition |
|---|---|
| T-05-01, untrusted ZIP metadata | Checked local/central spans, exact sizes, duplicate/overlap/feature rejection, CRC and decompression checks, malformed mutations, fuzz corpus, ASan/UBSan. |
| T-05-02, resource exhaustion | Profile input/member/expanded/output caps, bounded CPU runs, allocator failure test, checked arithmetic, and bounded mutation corpus. |
| T-05-03, private-data disclosure | Generic CLI/importer errors; local report path is ignored. The ignored report may contain a bounded fetch ring, final execution PC/opcode, and first unsupported event's PC/opcode or MVS bus address/access/width for local diagnosis; tracked output retains only generic status, chunk-level state-transition counts and watchdog counts. |
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
fidelity. The local selected guest now imports and executes, with source-backed
CPU and MVS behavior added from observed events. The latest run ends at its
bounded instruction budget without direct attract/start or a new unsupported
event. G-05-3, G-05-5, and the actual-app row remain unaccepted pending their
stated evidence.

An independent review of this smoke-runner diff first found an oversized-read
race: a GNMV could grow after `stat()` and cause an unbounded read. The runner
now reads at most `GNMV_MAX_BYTES + 1` bytes, and the synthetic sparse oversized
input test confirms rejection before process launch. The reviewer rechecked
the fix and found no new actionable issues. This review covers only the
smoke-runner change. Subsequent changes add only source-backed, guest-observed
CPU/MVS semantics with synthetic controls. Hosted
current-SHA evidence and the required CPU/board review remain open.

## Plan 05-04 checkpoint evidence review — 2026-10-09

No classifier or emulator behavior was added in Plan 05-04. The current
selected native report remains `guest_instruction_budget_exhausted` after
guest execution, and no independent attract/start observation is available.
The prior pinned-app abort is not repeated because its launch context has not
materially changed. Therefore there is no source-defined predicate to review,
and no independent code review of a new implementation was performed. The
generic blocker is retained; no Phase 04 acceptance or disposition is changed.
The structural RetroArch runner suite passed 31/31 and the MVS CTest suite
passed 7/7 on the current checkout. These tests do not launch RetroArch with
selected media and do not close the selected guest checkpoint.

## Plan 05-03 BIOS-extra contract review

The continuation review below supersedes earlier Plan 05-03 statements that
selected media was absent, execution had not started, or the video index-6
event remained the current blocker.

The selected-source parser continues to enforce ZIP32 metadata and local/central
consistency, flat safe names, entry and aggregate bounds, duplicate rejection,
nonoverlapping extents, supported methods, and successful decompression plus
CRC for every BIOS entry. Python classifier checks mirror the C parser's
local/central metadata, ZIP64 rejection, and extent rules. DEFLATE option-hint
bits are permitted only on DEFLATE entries; data descriptors and other flags
remain unsupported. Only the exact selected BIOS is mapped, and its
release build still checks the pinned CRC/SHA-1 identity. The game archive
continues to reject unknown members. Synthetic positive and negative importer
tests pass. Independent read-only re-review is pending. The sanitized local
runner result is `native_execution_error` with no structured output and no
guest execution. No selected boot, frontend, or hardware acceptance claim is
made.


## Plan 05-03 CPU/MVS continuation review

The selected source loop added exact MOVE.B Dn→absolute-long and MOVE.W
#immediate→absolute-long semantics with the NXP/Motorola *M68000 User's Manual*
cycle rows, explicit byte bus writes, flag assertions, odd-address controls, and
cycle totals. Pinned MAME map evidence supports BIOS vectors/high mirror,
MAME-differential dropped low byte writes, watchdog timing/reset, and video
register index-0 offset selection. The versioned per-instance diagnostic API is
additive and records only local bus fault data and scalar counters/state; the
public contract is versioned and tests assert version/width semantics. Synthetic
tests cover the offset latch and reject a neighboring unsupported register. The
current guest still stops at a source-mapped video-register index-6 write: MAME
acknowledges interrupt-pending bits and updates IRQ lines, but this core does not
model interrupt sources/pending state. Rendering and physical MVS behavior remain
outside the claim.

A reviewer raised a watchdog mirror-mask concern using `0x01ffe0`; inspection of
the pinned MAME `neogeo_main_map` at
`31e52312c59e4d60d70235118bcbccd220f5232e` shows `.mirror(0x01fffe)` for the
watchdog mapping, matching the implementation's decoded mask. No code change
was made for that finding.

## Earlier Plan 05-03 CPU/MVS review

**Reviewed:** 2026-10-09
**Scope:** Current Plan 05-03 CPU, instance/MVS mapping, public observation
version 11 at that review checkpoint, synthetic tests, and privacy-facing
qualification changes.
**Verdict:** No blockers found.

The reviewer confirmed the MOVE.W immediate-to-Dn mask selects all data
registers while limiting the supported addressing mode and word size; the
implementation preserves the upper register half and X, updates word N/Z/V/C,
and has a wrong-EA control. BSR.W/RTS semantics and timing paths have direct
register/stack/cycle tests. Vector-bank selection uses the addressable-latch
strobe address and selected bit state; tests retain the BIOS high mirror and
cover cartridge-vector select/restore. Audio source-select state, system
output state, and both lockout channels are per instance and reset with the
candidate image. Coin-counter controls remain unsupported. Dropped writes are
byte-width-specific and bounded to the reviewed window. The versioned
observation API exposes per-instance scalar state and generic diagnostics
without private media identity. No physical audio, video, coin output, or
full-board behavior is claimed.

At that review checkpoint, the local guest stopped at an unsupported CPU
event. The trace's private opcode, address, and PC remained in ignored output;
tracked evidence recorded only the generic stop. That review did not accept
G-05-3, hosted current-SHA evidence does not exist for G-05-5, and the actual
RetroArch smoke was correctly not launched. This review covers source, tests,
and API privacy; it does not establish title boot, physical hardware behavior,
or frontend behavior.

## Exception contract addendum — 2026-10-09

The accumulated CPU delta now includes a narrowly scoped vector-4 path for the
observed reserved byte- and long-EORI destinations. Both are covered by
synthetic short-frame/no-operand-write tests and use MC68000 Table 7-15 timing (62 clocks), not
the Section 8 / MC68010 figure. Existing CPU exception/reset denominators were
also reconciled to the MC68000 table: reset 64, IRQ 72, address/bus error 94,
and privilege/TRAP/illegal instruction 62. The primary reference is Motorola/
NXP User's Manual Rev. 9.1 Table 7-15, printed p. 7-11. The instruction path
does not establish general exception support or attract/start; G-05-3 and
G-05-5 remain open.

## Final runner/profile re-review — 2026-10-09

Independent re-review found no remaining issue in the current qualifier status
handling or profile sanitizer. The wrapper accepts only the in-tree runner's
allowlisted non-checkpoint statuses, has no runner-path override, and rejects a
synthetic `attract_start` status as `native_qualification_failed`. The current
256-chunk profile and validation text agree. The latest selected run remains
budget-exhausted; the observed device-state transitions provide no guest-written
attract/start predicate. G-05-3 and G-05-5 remain open.
