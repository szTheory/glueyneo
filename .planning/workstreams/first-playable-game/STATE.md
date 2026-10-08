---
gsd_state_version: "1.0"
milestone: first-playable-game
milestone_name: First Playable Game
current_phase: 04
current_phase_name: Public Playable Tracer
current_plan: 12
status: "Phase 04 incomplete: verifier found gaps (3/5 truths); four high-severity threats remain open; pinned frontend behavior is unknown"
stopped_at: Phase 04 verifier returned gaps_found (3/5); no phase advance
last_updated: "2026-10-08T12:14:04.341Z"
last_activity: 2026-10-08
last_activity_desc: Fresh Phase 04 security and goal audits completed; escaped-quote disclosure and review-map reconciliation remain; next $gsd-plan-phase 04 --gaps --ws first-playable-game
state_head: 8c88bf1b5a5a7c71327e6bb8a3d9fd0ea261a33e
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 12
  completed_plans: 12
  percent: 0
---

# Project State

## Project Reference

See [PROJECT.md](../../PROJECT.md) for the current project contract.

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 04 — close two verification gaps and obtain pinned RetroArch evidence

## Current Position

Phase: 04 (Public Playable Tracer) — INCOMPLETE; execution plans finished
Current Plan: 12
Total Plans in Phase: 12
Status: Phase 04 incomplete: verifier found gaps (3/5 truths); four high-severity threats remain open; pinned frontend behavior is unknown
Last activity: 2026-10-08
Last Activity Description: Fresh Phase 04 security and goal audits completed; escaped-quote disclosure and review-map reconciliation remain; next $gsd-plan-phase 04 --gaps --ws first-playable-game

Progress: [░░░░░░░░░░] 0%

## Progress

**Phases Complete:** 0
**Current Plan:** 12

## Performance Metrics

**Plans completed:** 12 of 12 planned; Phase 04 acceptance remains incomplete.
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

## Session Continuity

**Last session:** 2026-10-08T11:50:07.122Z

**Stopped At:** Phase 04 verifier returned gaps_found (3/5); no phase advance
**Resume File:** None

## Scope Notes

- Accepted research and primary-source references are preserved in [RESEARCH.md](RESEARCH.md). Outcome: locally reach interactive Metal Slug X gameplay with movement, firing, scrolling, and representative sound in one pinned MVS/macOS RetroArch setup; public CI uses a separate first-party fixture and never commercial game/BIOS data. All 20 requirements and their primary allocations in the roadmap are user-approved.
- Planning milestone ID: `first-playable-game`; release version remains unassigned. All twelve Phase 04 plans have execution summaries. Plan 04-12 supplies passing receipt/redaction regressions, a current validation-map checker and 47/47 owned-debug CTests. The prior verifier report is point-in-time evidence; fresh independent security review and phase verification are next. The security audit closed T-04-13/T-04-16/T-04-17 and left T-04-11/T-04-15/T-04-18 open. Project Phase 04 begins this workstream; independent playable work does not close or depend on completion of the sibling hosted-release gate.
- Milestone-start triage on 2026-10-07 found no open issues and one draft PR, [#1](https://github.com/szTheory/glueyneo/pull/1), for the separate diagnostic release work. It supplies no playable-game requirement or completion evidence.
- Work is isolated on `docs/first-playable-game-milestone`. The existing 138 planning relocations into the diagnostic workstream were verified byte-identical and committed; unrelated pre-existing methodology/configuration/preparation edits remain outside this milestone's commits.
- Carry-forward constraints: keep the owned native C17 core deterministic and host-independent; introduce the libretro/software-video path early; keep media/archive I/O outside the native core; retain the owned 68000 direction and gate Z80/YM2610 admission on evidence. PROJECT-D-48 permits the narrow ymfm C++14 exception behind a private C interface; a future C replacement is optional. The supplied BIOS is available locally, but the exact MVS profile and compatibility remain unqualified.
- Approved Phase 04–07 sequencing is in [ROADMAP.md](ROADMAP.md): public playable tracer and early Z80/ymfm admission → selected MVS boot including required sound-CPU handshakes → active title control → sound and qualification. All twelve Phase 04 plans across ten waves have execution summaries. Three high-severity path-disclosure threats and five review dispositions remain open pending independent post-fix assessment; HOST-02 and actual frontend QUAL-03 remain unknown.
- Goal: advance from the diagnostic SDK toward a playable Neo Geo game.
- Local qualification: a user-provided private game archive is stored under the Git-ignored `local/roms/` directory. Keep its contents and private checksums out of tracked files, CI, and release artifacts.
- The user-provided BIOS archive is also stored under the Git-ignored `local/roms/` directory. The copy matches its source, passes ZIP CRC validation and is untracked; those checks do not establish BIOS compatibility.
- Public CI: use original fixtures and/or homebrew assets only after confirming redistribution rights for the specific ROM assets; a source-code license alone is not sufficient evidence for bundled game data.
- The local archive passed ZIP CRC checks and matched all 13 ROM size/SHA-1 entries in MAME's current Neo Geo software list. That confirms the archive identity, not emulator compatibility.
- Next GSD command: `$gsd-secure-phase 04 --ws first-playable-game` for independent post-fix assessment, then fresh whole-phase verification under the project's direct-verifier workaround. Phase 04 remains incomplete until remaining security/review dispositions resolve and the pinned-app evidence is obtained; do not start Phase 05.

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
- [Phase 04]: Plan 04-12 consumes ambiguous unquoted private path tails; owned compile flags follow CMake object target identity; frontend and independent security gates remain open.

### Blockers

- T-04-11, T-04-15 and T-04-18 remain high/open and security blocked pending independent post-fix audit. Plan 04-12 supplies passing complete-span regressions; tests do not close threats.
- CR-01/CR-02/WR-01 and carried WR-02/WR-03 remain open pending independent review. Plan 04-12 rejects boolean byte/count fields, removes ambiguous private suffixes and reconciles the evidence checker; focused suites pass 19/25 and the current map checker passes.
- Owned-debug is now 47/47 passing, including refreshed identity/source-manifest and target-scoped inventory checks. This repairs the prior deterministic failure without establishing frontend acceptance.
- HOST-02 remains unknown: pinned RetroArch 1.22.2 aborts before the first screenshot in fresh no-content and core/content launches (EXC_CRASH SIGABRT, return -6). LaunchServices reported kLSNoExecutableErr despite bundle/executable/signature checks; unified-log inspection was sandbox-blocked. A functioning interactive macOS app launch context is still required; cause is not established.
