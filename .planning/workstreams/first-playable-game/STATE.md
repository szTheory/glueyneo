---
gsd_state_version: "1.0"
milestone: first-playable-game
milestone_name: First Playable Game
current_phase: 04
current_phase_name: Public Playable Tracer
current_plan: 6
status: ready_for_verification
stopped_at: Completed 04-06-PLAN.md
last_updated: "2026-10-07T22:07:50.372Z"
last_activity: 2026-10-07
  last_activity_desc: Phase 04 Plan 06 complete; clean static/shared installs and CTest passed; HOST-02 remains unknown
state_head: 2647a987d64ddf22af175f3a4184613012a70964
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 6
  completed_plans: 6
  percent: 0
---

# Project State

## Project Reference

See [PROJECT.md](../../PROJECT.md) for the current project contract.

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 04 — Public Playable Tracer

## Current Position

Phase: 04 (Public Playable Tracer) — READY TO EXECUTE
Plan: 6 of 6
Status: Ready for verification
Last activity: 2026-10-07 — Phase 04 Plan 06 complete; clean static/shared installs and 34/34 CTests passed; HOST-02 remains unknown

Progress: [░░░░░░░░░░] 0%

## Progress

**Phases Complete:** 0
**Current Plan:** 6

## Performance Metrics

**Plans completed:** 6 of 6 planned.
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 04 P01 | 10min | 3 tasks | 12 files |
| Phase 04 P02 | 11min | 2 tasks | 7 files |
| Phase 04 P03 | 16min | 2 tasks | 5 files |
| Phase 04 P04 | 13min 33sec | 3 tasks | 9 files |
| Phase 04 P05 | 10 min | 3 tasks | 17 files |
| Phase 04 P06 | 9min | 2 tasks | 6 files |

## Session Continuity

**Last session:** 2026-10-07T22:07:50.372Z

**Stopped At:** Completed 04-06-PLAN.md
**Resume File:** None

## Scope Notes

- Accepted research and primary-source references are preserved in [RESEARCH.md](RESEARCH.md). Outcome: locally reach interactive Metal Slug X gameplay with movement, firing, scrolling, and representative sound in one pinned MVS/macOS RetroArch setup; public CI uses a separate first-party fixture and never commercial game/BIOS data. All 20 requirements and their primary allocations in the roadmap are user-approved.
- Planning milestone ID: `first-playable-game`; release version remains unassigned. Phase 04 Plans 01–06 are complete; clean install/consumer and 34-test CTest evidence passed, while HOST-02 remains unknown pending a successful actual RetroArch screenshot run. Project Phase 04 begins this workstream; independent playable work does not close or depend on completion of the sibling hosted-release gate.
- Milestone-start triage on 2026-10-07 found no open issues and one draft PR, [#1](https://github.com/szTheory/glueyneo/pull/1), for the separate diagnostic release work. It supplies no playable-game requirement or completion evidence.
- Work is isolated on `docs/first-playable-game-milestone`. The existing 138 planning relocations into the diagnostic workstream were verified byte-identical and committed; unrelated pre-existing methodology/configuration/preparation edits remain outside this milestone's commits.
- Carry-forward constraints: keep the owned native C17 core deterministic and host-independent; introduce the libretro/software-video path early; keep media/archive I/O outside the native core; retain the owned 68000 direction and gate Z80/YM2610 admission on evidence. PROJECT-D-48 permits the narrow ymfm C++14 exception behind a private C interface; a future C replacement is optional. The supplied BIOS is available locally, but the exact MVS profile and compatibility remain unqualified.
- Approved Phase 04–07 sequencing is in [ROADMAP.md](ROADMAP.md): public playable tracer and early Z80/ymfm admission → selected MVS boot including required sound-CPU handshakes → active title control → sound and qualification. Phase 04 has six plans across five waves; Plans 01–06 are complete and the phase is ready for verification.
- Goal: advance from the diagnostic SDK toward a playable Neo Geo game.
- Local qualification: a user-provided private game archive is stored under the Git-ignored `local/roms/` directory. Keep its contents and private checksums out of tracked files, CI, and release artifacts.
- The user-provided BIOS archive is also stored under the Git-ignored `local/roms/` directory. The copy matches its source, passes ZIP CRC validation and is untracked; those checks do not establish BIOS compatibility.
- Public CI: use original fixtures and/or homebrew assets only after confirming redistribution rights for the specific ROM assets; a source-code license alone is not sufficient evidence for bundled game data.
- The local archive passed ZIP CRC checks and matched all 13 ROM size/SHA-1 entries in MAME's current Neo Geo software list. That confirms the archive identity, not emulator compatibility.
- Next GSD command: `$gsd-verify-work 04 --ws first-playable-game`.

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

### Blockers

- HOST-02 remains blocked/unknown: pinned RetroArch 1.22.2 executable matched its expected digest but exited with status -6 before a screenshot; rerun after diagnosing or replacing the app installation.
