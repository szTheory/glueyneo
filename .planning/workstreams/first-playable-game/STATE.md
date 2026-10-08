---
gsd_state_version: "1.0"
milestone: first-playable-game
milestone_name: First Playable Game
current_phase: 04
current_phase_name: Public Playable Tracer
current_plan: 19
status: executing
stopped_at: Completed 04-19-PLAN.md; awaiting execute-phase post hooks
last_updated: "2026-10-08T23:31:54.613Z"
last_activity: 2026-10-08
last_activity_desc: Phase 04 planning complete — 20 plans ready
state_head: 910fc380ed28293efd09d6ebfa388ac88d5542da
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 20
  completed_plans: 19
  percent: 0
---

# Project State

## Project Reference

See [PROJECT.md](../../PROJECT.md) for the current project contract.

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 04 — Public Playable Tracer

## Current Position

Phase: 04 (Public Playable Tracer) — READY TO EXECUTE
Current Plan: 19 (completed; awaiting fresh post-execution audits and verification)
Total Plans in Phase: 20
Status: Awaiting execute-phase post hooks; Phase 04 remains blocked
Last activity: 2026-10-08 — Phase 04 execution started
Last Activity Description: Phase 04 planning complete — 20 plans ready

Progress: [░░░░░░░░░░] 0%

## Progress

**Phases Complete:** 0
**Current Plan:** 19 (completed)

## Performance Metrics

**Plans completed:** 19 of 19; Phase 04 acceptance remains incomplete
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 04 P01 | 10min | 3 tasks | 12 files |
| Phase 04 P02 | 11min | 2 tasks | 7 files |
| Phase 04 P03 | 16min | 2 tasks | 5 files |
| Phase 04 P04 | 13min 33sec | 3 tasks | 9 files |
| Phase 04 P05 | 10 min | 3 tasks | 17 files |
| Phase 04 P06 | 9min | 2 tasks | 6 files |
| Phase 04 P07 | 13min | 2 tasks | 4 files |
| Phase 04 P08 | 12min | 2 tasks | 6 files |
| Phase 04 P09 | 6min | 1 tasks | 1 files |
| Phase 04 P10 | 7min | 3 tasks | 4 files |
| Phase 04 P11 | 13min | 2 tasks | 8 files |
| Phase 04 P12 | 9min | 3 tasks | 12 files |
| Phase 04 P13 | 15min | 2 tasks | 8 files |
| Phase 04 P14 | 54m 46s | 3 tasks | 9 files |
| Phase 04 P15 | 6min | 2 tasks | 3 files |
| Phase 04 P16 | 10min | 2 tasks | 7 files |
| Phase 04 P17 | 23 min | 2 tasks | 6 files |
| Phase 04 P18 | 5 min | 3 tasks | 4 files |
| Phase 04 P19 | 15 min | 3 tasks | 8 files |

## Session Continuity

**Last session:** 2026-10-08T23:05:15.500Z

**Stopped At:** Completed 04-19-PLAN.md; awaiting execute-phase post hooks
**Resume File:** None

## Scope Notes

- Accepted research and primary-source references are preserved in [RESEARCH.md](RESEARCH.md). Outcome: locally reach interactive Metal Slug X gameplay with movement, firing, scrolling, and representative sound in one pinned MVS/macOS RetroArch setup; public CI uses a separate first-party fixture and never commercial game/BIOS data. All 20 requirements and their primary allocations in the roadmap are user-approved.
- Planning milestone ID: `first-playable-game`; release version remains unassigned. Plans 04-01 through 04-18 have execution summaries. Plan 04-14 repaired the raw-quote and Info/IN parser cases; Plan 04-15 preserved the unavailable actual-frontend prerequisite without retrying RetroArch. Plan 04-18 restored the current security-count, report-evidence, and frontend claim gates without changing evidence dispositions. The fresh security audit verified 46 threats: 42 closed and four high disclosure threats remain open by user direction; T-04-34 remains medium/open. The fresh review confirms CR-02/WR-04 fixed and records CR-03/WR-05 open; carried WR-01/WR-02/WR-03 remain open. HOST-02 and frontend QUAL-03 remain Pending/unknown. Project Phase 04 begins this workstream; independent playable work does not close or depend on completion of the sibling hosted-release gate.
- Milestone-start triage on 2026-10-07 found no open issues and one draft PR, [#1](https://github.com/szTheory/glueyneo/pull/1), for the separate diagnostic release work. It supplies no playable-game requirement or completion evidence.
- Work is isolated on `docs/first-playable-game-milestone`. The existing 138 planning relocations into the diagnostic workstream were verified byte-identical and committed; unrelated pre-existing methodology/configuration/preparation edits remain outside this milestone's commits.
- Carry-forward constraints: keep the owned native C17 core deterministic and host-independent; introduce the libretro/software-video path early; keep media/archive I/O outside the native core; retain the owned 68000 direction and gate Z80/YM2610 admission on evidence. PROJECT-D-48 permits the narrow ymfm C++14 exception behind a private C interface; a future C replacement is optional. The supplied BIOS is available locally, but the exact MVS profile and compatibility remain unqualified.
- Approved Phase 04–07 sequencing is in [ROADMAP.md](ROADMAP.md): public playable tracer and early Z80/ymfm admission → selected MVS boot including required sound-CPU handshakes → active title control → sound and qualification. Plans 04-01 through 04-18 have summaries. Phase 04 remains incomplete. T-04-11, T-04-15, T-04-18 and T-04-20 remain high/open; T-04-34 remains medium/open. CR-02/WR-04 are fixed; CR-03/WR-05 and carried WR-01/WR-02/WR-03 remain open. Plan 04-18 restored the direct current-evidence gates; WR-06's independent disposition remains open. HOST-02 and frontend QUAL-03 remain Pending/unknown.
- Goal: advance from the diagnostic SDK toward a playable Neo Geo game.
- Local qualification: a user-provided private game archive is stored under the Git-ignored `local/roms/` directory. Keep its contents and private checksums out of tracked files, CI, and release artifacts.
- The user-provided BIOS archive is also stored under the Git-ignored `local/roms/` directory. The copy matches its source, passes ZIP CRC validation and is untracked; those checks do not establish BIOS compatibility.
- Public CI: use original fixtures and/or homebrew assets only after confirming redistribution rights for the specific ROM assets; a source-code license alone is not sufficient evidence for bundled game data.
- The local archive passed ZIP CRC checks and matched all 13 ROM size/SHA-1 entries in MAME's current Neo Geo software list. That confirms the archive identity, not emulator compatibility.
- Next GSD work: `$gsd-execute-phase 04 --ws first-playable-game` executes the one bounded 04-19 independent-audit/disposition plan, followed by fresh whole-phase verification. Actual pinned RetroArch evidence remains manual-only; HOST-02/frontend QUAL-03 remain Pending/unknown. Do not start Phase 05.

## Decisions

- [Phase 04]: The public fixture profile uses distinct tagged value 0x50554246 and a strict 602-byte GNFX v1 envelope.
- [Phase 04]: The guest adds only ADD.W D0,D1 and MOVE.W D1,(abs.L), the two missing opcode/addressing pairs in its bounded instruction inventory.
- [Phase 04]: Each fixture frame restarts at the BIOS-free reset vector while guest RAM persists; its 200000-cycle ratio is fixture timing, not qualified Neo Geo timing.
- [Phase 04]: XRGB8888 is represented as native-endian uint32_t 0x00RRGGBB; audio metadata is signed-16 interleaved stereo at 48 kHz with zero produced frames.
- [Phase 04]: The adapter uses in-memory GNFX content, forwards native XRGB8888 frames synchronously, and maps RetroPad RIGHT to the native frame input.
- [Phase 04]: Serialization, special loading, raw memory exposure, and cheats remain explicit safe opt-outs for the bounded fixture core.
- [Phase 04]: The RetroArch smoke runner uses local keyboard and screenshot automation without enabling the frontend UDP command interface.
- [Phase 04]: Recorded the GNFX source, assertion, generator, and 602-byte output as separate identities with affirmative MIT rights.
- [Phase 04]: Kept Motorola instruction evidence, community board references, emulator comparisons, and physical hardware claims at separate evidence levels.
- [Phase 04]: Admitted the pinned floooh/chips Z80 candidate for the explicitly documented synthetic Phase 04 workload only; private game sound-driver behavior remains unqualified.
- [Phase 04]: A failed Z80 bus callback remains latched through checkpoint restore; reset is required before execution can resume.
- [Phase 04]: Admitted the pinned ymfm YM2610 subset after all nine source, behavior, bounds, failure, and installed C-consumer gates passed; this does not qualify audible game sound or physical-hardware fidelity.
- [Phase 04]: The private candidate generates chip-native samples at one frame per 16 input clocks and adds no resampler or host audio service.
- [Phase 04]: Install the shared Libretro adapter under lib/libretro so clean installed frontend qualification uses the installed artifact.
- [Phase 04]: Keep the RetroArch smoke unknown after exit -6 before screenshot; callback tests do not qualify HOST-02.
- [Phase 04]: Keep Z80 synthetic-workload and YM2610 candidate-only claim boundaries.
- [Phase 04]: Keep HOST-02 unknown after fresh no-content and core/content launches abort before screenshot; preserve exact precondition and do not attribute failure to core or fixture without evidence.
- [Phase 04]: Use bounded path-span redaction and fail closed through ambiguous unquoted line tails.
- [Phase 04]: Require the documented public fixture digest and exact pinned RetroArch bundle identifier before frontend process actions.
- [Phase 04]: Repository-backed receipt rows derive from bounded committed archive bytes; passing tests do not close security or actual frontend gates.
- [Phase 04]: Plan 04-13 validates escaped JSON quote boundaries and redacts ambiguous path spans through end of line; independent security and frontend gates remain open.
- [Phase 04]: Valid JSON escape rules are required before preserving a diagnostic quote boundary; ambiguous apostrophe or malformed spans redact through end of line.
- [Phase 04]: Plan 04-13 repository tests do not close the four high disclosure threats or establish pinned RetroArch HOST-02/QUAL-03 behavior.
- [Phase 04]: Keep the frontend claim unknown when the materially changed functioning launch context is unavailable.
- [Phase 04]: Derive HOST-02 and QUAL-03 separately; neither passes without the actual frontend load evidence.
- [Phase 04]: After a private root appears in unstructured diagnostics, discard the entire remaining value because newline and punctuation do not prove a path boundary.
- [Phase 04]: Accept only one normalized open/fixed/skipped/deferred disposition matching its record; keep actual frontend requirements Pending/unknown without app evidence.
- [Phase 04]: Reject frontend closure language that conflicts with Pending/unknown status; keep WR-06 open with current-review provenance pending independent review.
- [Phase 04]: Security blocking count remains four high/open rows; T-04-34 remains medium/open.
- [Phase 04]: HOST-02 and frontend QUAL-03 remain Pending/unknown without actual pinned-app evidence.
- [Phase 04]: Retain WR-06/T-04-34 medium/open because independent code review reproduced affirmative frontend-claim paraphrases after bounded repairs.
- [Phase 04]: Keep HOST-02 and frontend QUAL-03 Pending/unknown and manual-only until direct pinned RetroArch observations exist.

### Blockers

- Owned-debug is now 47/47 passing, including refreshed identity/source-manifest and target-scoped inventory checks. This repairs the prior deterministic failure without establishing frontend acceptance.
- HOST-02 remains unknown: pinned RetroArch 1.22.2 aborts before the first screenshot in fresh no-content and core/content launches (EXC_CRASH SIGABRT, return -6). LaunchServices reported kLSNoExecutableErr despite bundle/executable/signature checks; unified-log inspection was sandbox-blocked. A functioning interactive macOS app launch context is still required; cause is not established. Preserve the screenshot, stable no-input frames, RIGHT/LEFT controls, unload and normal-exit observation; do not repeat the launch while its environment is unchanged.
- WR-06 remains open after independent review because affirmative paraphrases still pass the bounded docs gate; fresh post-execution audits must confirm current dispositions.
- T-04-11, T-04-15, T-04-18, and T-04-20 remain high/open by user direction; Plan 04-16 sanitizer tests pass, but no threat closure was granted.
