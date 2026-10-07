---
gsd_state_version: "1.0"
milestone: first-playable-game
milestone_name: First Playable Game
status: planning
last_updated: "2026-10-07T18:05:13.751Z"
last_activity: 2026-10-07
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Current Position

Phase: Not started (creating roadmap)
Plan: —
Status: Requirements approved — creating roadmap
Last activity: 2026-10-07 — User approved all 20 milestone requirements

## Progress

**Phases Complete:** 0
**Current Plan:** N/A

## Session Continuity

**Stopped At:** `$gsd-new-milestone --ws first-playable-game` is creating the roadmap after user approval of all 20 [requirements](REQUIREMENTS.md). Reuse the accepted research. Present the completed roadmap for approval before committing it; do not start phase discussion/planning. The v0.1 Phase 03 hosted-evidence gate remains unchanged.
**Resume File:** `.planning/workstreams/first-playable-game/STATE.md`

## Scope Notes

- Accepted research and primary-source references are preserved in [RESEARCH.md](RESEARCH.md). Outcome: locally reach interactive Metal Slug X gameplay with movement, firing, scrolling, and representative sound in one pinned MVS/macOS RetroArch setup; public CI uses a separate first-party fixture and never commercial game/BIOS data. All 20 requirements are user-approved; the roadmap remains to be created.
- Planning milestone ID: `first-playable-game`; release version remains unassigned. No phase or plan has started. Continue project phase numbering after Phase 03 when the roadmap is created; independent playable work does not close or depend on completion of the sibling hosted-release gate.
- Milestone-start triage on 2026-10-07 found no open issues and one draft PR, [#1](https://github.com/szTheory/glueyneo/pull/1), for the separate diagnostic release work. It supplies no playable-game requirement or completion evidence.
- Work is isolated on `docs/first-playable-game-milestone`. The existing 138 planning relocations into the diagnostic workstream were verified byte-identical and committed; unrelated pre-existing methodology/configuration/preparation edits remain outside this milestone's commits.
- Carry-forward constraints: keep the owned native C17 core deterministic and host-independent; introduce the libretro/software-video path early; keep media/archive I/O outside the native core; retain the owned 68000 direction and gate Z80/YM2610 admission on evidence. PROJECT-D-48 permits the narrow ymfm C++14 exception behind a private C interface; a future C replacement is optional. The supplied BIOS is available locally, but the exact MVS profile and compatibility remain unqualified.
- Proposed sequencing is in RESEARCH.md: playable fixture tracer → MVS game boot path → interactive title behavior → sound and qualification. These are not numbered or approved phases yet.
- Goal: advance from the diagnostic SDK toward a playable Neo Geo game.
- Local qualification: a user-provided private game archive is stored under the Git-ignored `local/roms/` directory. Keep its contents and private checksums out of tracked files, CI, and release artifacts.
- The user-provided BIOS archive is also stored under the Git-ignored `local/roms/` directory. The copy matches its source, passes ZIP CRC validation and is untracked; those checks do not establish BIOS compatibility.
- Public CI: use original fixtures and/or homebrew assets only after confirming redistribution rights for the specific ROM assets; a source-code license alone is not sufficient evidence for bundled game data.
- The local archive passed ZIP CRC checks and matched all 13 ROM size/SHA-1 entries in MAME's current Neo Geo software list. That confirms the archive identity, not emulator compatibility.
- Next GSD command: `$gsd-new-milestone --ws first-playable-game`.
