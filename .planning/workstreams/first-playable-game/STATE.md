---
gsd_state_version: "1.0"
milestone: first-playable-game
milestone_name: First Playable Game
current_phase: "04"
current_phase_name: Public Playable Tracer
status: planning
last_updated: "2026-10-07T18:22:27.639Z"
last_activity: 2026-10-07
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See [PROJECT.md](../../PROJECT.md) for the current project contract.

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 04 — Public Playable Tracer; ready for discussion after completed milestone initialization.

## Current Position

Phase: 04 (Public Playable Tracer) — first of four approved workstream phases; continuous project numbering 04–07
Plan: None started; plan count TBD
Status: Milestone initialized; ready for Phase 04 discussion; no phase or plan started
Last activity: 2026-10-07 — User approved the roadmap; all 20 requirements mapped to Phases 4–7 and initialization completed

Progress: [░░░░░░░░░░] 0%

## Progress

**Phases Complete:** 0
**Current Plan:** N/A

## Performance Metrics

**Plans completed:** 0; no phase plans exist yet. Duration and trend are not available.

## Session Continuity

**Stopped At:** `$gsd-new-milestone --ws first-playable-game` completed after user approval of the [requirements](REQUIREMENTS.md) and [roadmap](ROADMAP.md). Next: `$gsd-discuss-phase 04 --ws first-playable-game`. Pause here for user continuation and model selection; do not start discussion automatically. No phase or plan was executed or completed. The sibling v0.1 Phase 03 hosted-evidence gate remains open and unchanged.
**Resume File:** `.planning/workstreams/first-playable-game/STATE.md`

## Scope Notes

- Accepted research and primary-source references are preserved in [RESEARCH.md](RESEARCH.md). Outcome: locally reach interactive Metal Slug X gameplay with movement, firing, scrolling, and representative sound in one pinned MVS/macOS RetroArch setup; public CI uses a separate first-party fixture and never commercial game/BIOS data. All 20 requirements and their primary allocations in the roadmap are user-approved.
- Planning milestone ID: `first-playable-game`; release version remains unassigned. No phase or plan has started. Project Phase 04 begins this workstream; independent playable work does not close or depend on completion of the sibling hosted-release gate.
- Milestone-start triage on 2026-10-07 found no open issues and one draft PR, [#1](https://github.com/szTheory/glueyneo/pull/1), for the separate diagnostic release work. It supplies no playable-game requirement or completion evidence.
- Work is isolated on `docs/first-playable-game-milestone`. The existing 138 planning relocations into the diagnostic workstream were verified byte-identical and committed; unrelated pre-existing methodology/configuration/preparation edits remain outside this milestone's commits.
- Carry-forward constraints: keep the owned native C17 core deterministic and host-independent; introduce the libretro/software-video path early; keep media/archive I/O outside the native core; retain the owned 68000 direction and gate Z80/YM2610 admission on evidence. PROJECT-D-48 permits the narrow ymfm C++14 exception behind a private C interface; a future C replacement is optional. The supplied BIOS is available locally, but the exact MVS profile and compatibility remain unqualified.
- Approved Phase 04–07 sequencing is in [ROADMAP.md](ROADMAP.md): public playable tracer and early Z80/ymfm admission → selected MVS boot including required sound-CPU handshakes → active title control → sound and qualification. Phase plans remain undefined; no phase has started.
- Goal: advance from the diagnostic SDK toward a playable Neo Geo game.
- Local qualification: a user-provided private game archive is stored under the Git-ignored `local/roms/` directory. Keep its contents and private checksums out of tracked files, CI, and release artifacts.
- The user-provided BIOS archive is also stored under the Git-ignored `local/roms/` directory. The copy matches its source, passes ZIP CRC validation and is untracked; those checks do not establish BIOS compatibility.
- Public CI: use original fixtures and/or homebrew assets only after confirming redistribution rights for the specific ROM assets; a source-code license alone is not sufficient evidence for bundled game data.
- The local archive passed ZIP CRC checks and matched all 13 ROM size/SHA-1 entries in MAME's current Neo Geo software list. That confirms the archive identity, not emulator compatibility.
- Next GSD command: `$gsd-discuss-phase 04 --ws first-playable-game`.
