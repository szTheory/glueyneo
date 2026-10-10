---
gsd_state_version: "1.0"
milestone: first-playable-game
milestone_name: First Playable Game
current_phase: 04
current_phase_name: Public Playable Tracer
current_plan: 4
status: executing
stopped_at: Completed 04-39-PLAN.md
last_updated: "2026-10-10T20:33:48.022Z"
last_activity: 2026-10-10
last_activity_desc: Phase 04 execution started
state_head: f17ce82c6cf72df7fe7c880e43f077a333ff22c9
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 48
  completed_plans: 45
  percent: 0
---

# Project State

## Project Reference

See [PROJECT.md](../../PROJECT.md) for the current project contract.

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 04 — Public Playable Tracer

## Current Position

Phase: 04 (Public Playable Tracer) — EXECUTING
Current Plan: 4
Total Plans in Phase: 42
Status: Ready to execute
Last activity: 2026-10-10 — Phase 04 execution started
Last Activity Description: Phase 04 execution started

Progress: [░░░░░░░░░░] 0%

## Progress

**Phases Complete:** 0
**Current Plan:** 4

## Performance Metrics

**Plans completed:** 22 of 22; Phase 04 acceptance remains incomplete
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
| Phase 04 P20 | 11min | 3 tasks | 5 files |
| Phase 04 P22 | not recorded | 3 tasks | 10 files |
| Phase 05 P01 | 20m | 3 tasks | 34 files |
| Phase 05 P04 | 4min | 3 tasks | 3 files |
| Phase 05 P06 | 20h 15m 23s | 2 tasks | 16 files |
| Phase 04 P24 | 40min | 3 tasks | 6 files |
| Phase 04 P25 | 15 min | 2 tasks | 4 files |
| Phase 04 P26 | 25min | 2 tasks | 4 files |
| Phase 04 P27 | 15 min | 2 tasks | 4 files |
| Phase 04 P28 | 40min | 3 tasks | 6 files |
| Phase 04 P29 | 25min | 3 tasks | 9 files |
| Phase 04 P30 | 30min | 3 tasks | 10 files |
| Phase 04 P31 | 40min | 3 tasks | 7 files |
| Phase 04 P32 | 6 min | 3 tasks | 10 files |
| Phase 04 P33 | 13 min | 4 tasks | 10 files |
| Phase 04 P34 | 35 min | 2 tasks | 5 files |
| Phase 04 P35 | 40 min | 3 tasks | 12 files |
| Phase 04 P36 | 35 min | 2 tasks | 8 files |
| Phase 04 P37 | 25 min | 3 tasks | 6 files |
| Phase 04 P38 | 25min | 2 tasks | 3 files |
| Phase 04 P39 | 20min | 2 tasks | 2 files |

## Session Continuity

**Last session:** 2026-10-10T20:33:47.995Z

**Stopped At:** Completed 04-39-PLAN.md
**Resume File:** None

## Scope Notes

- Accepted research and primary-source references are preserved in [RESEARCH.md](RESEARCH.md). Outcome: locally reach interactive Metal Slug X gameplay with movement, firing, scrolling, and representative sound in one pinned MVS/macOS RetroArch setup; public CI uses a separate first-party fixture and never commercial game/BIOS data. All 20 requirements and their primary allocations in the roadmap are user-approved.
- Historical (superseded 2026-10-10; see Blockers): Planning milestone ID: `first-playable-game`; release version remains unassigned. Plans 04-01 through 04-18 have execution summaries. Plan 04-14 repaired the raw-quote and Info/IN parser cases; Plan 04-15 preserved the unavailable actual-frontend prerequisite without retrying RetroArch. Plan 04-18 restored the current security-count, report-evidence, and frontend claim gates without changing evidence dispositions. The fresh security audit verified 46 threats: 42 closed and four high disclosure threats remain open by user direction; T-04-34 remains medium/open. The fresh review confirms CR-02/WR-04 fixed and records CR-03/WR-05 open; carried WR-01/WR-02/WR-03 remain open. HOST-02 and frontend QUAL-03 remain Pending/unknown. Project Phase 04 begins this workstream; independent playable work does not close or depend on completion of the sibling hosted-release gate. Current facts: Plans 04-01 through 04-23 are executed; threats_open is 6 after the independent 04-23 review and the pinned RetroArch receipt is current at aaf3f093ab0f.
- Milestone-start triage on 2026-10-07 found no open issues and one draft PR, [#1](https://github.com/szTheory/glueyneo/pull/1), for the separate diagnostic release work. It supplies no playable-game requirement or completion evidence.
- Work is isolated on `docs/first-playable-game-milestone`. The existing 138 planning relocations into the diagnostic workstream were verified byte-identical and committed; unrelated pre-existing methodology/configuration/preparation edits remain outside this milestone's commits.
- Carry-forward constraints: keep the owned native C17 core deterministic and host-independent; introduce the libretro/software-video path early; keep media/archive I/O outside the native core; retain the owned 68000 direction and gate Z80/YM2610 admission on evidence. PROJECT-D-48 permits the narrow ymfm C++14 exception behind a private C interface; a future C replacement is optional. The supplied BIOS is available locally, but the exact MVS profile and compatibility remain unqualified.
- Historical (superseded 2026-10-10; see Blockers): Approved Phase 04–07 sequencing is in [ROADMAP.md](ROADMAP.md): public playable tracer and early Z80/ymfm admission → selected MVS boot including required sound-CPU handshakes → active title control → sound and qualification. Plans 04-01 through 04-18 have summaries. Phase 04 remains incomplete. T-04-11, T-04-15, T-04-18 and T-04-20 remain high/open; T-04-34 remains medium/open. CR-02/WR-04 are fixed; CR-03/WR-05 and carried WR-01/WR-02/WR-03 remain open. Plan 04-18 restored the direct current-evidence gates; WR-06's independent disposition remains open. HOST-02 and frontend QUAL-03 remain Pending/unknown. Current facts: Plans 04-01 through 04-23 are executed; threats_open is 6 after the independent 04-23 review and the pinned RetroArch receipt is current at aaf3f093ab0f.
- Goal: advance from the diagnostic SDK toward a playable Neo Geo game.
- Local qualification: a user-provided private game archive is stored under the Git-ignored `local/roms/` directory. Keep its contents and private checksums out of tracked files, CI, and release artifacts.
- The user-provided BIOS archive is also stored under the Git-ignored `local/roms/` directory. The copy matches its source, passes ZIP CRC validation and is untracked; those checks do not establish BIOS compatibility.
- Public CI: use original fixtures and/or homebrew assets only after confirming redistribution rights for the specific ROM assets; a source-code license alone is not sufficient evidence for bundled game data.
- The local archive passed ZIP CRC checks and matched all 13 ROM size/SHA-1 entries in MAME's current Neo Geo software list. That confirms the archive identity, not emulator compatibility.
- Next GSD work: no GSD command is warranted while the external evidence is unchanged. Plan 05-06 remains halted at Task 2: selected compatibility and GAME-02 need an independently observed selected configuration plus a source-backed guest attract/start predicate with oracle ancestry. The earlier RetroArch SIGABRT was the sandboxed launch context (debug session `.planning/debug/resolved/retroarch-startup-abort.md`); agent shells in the logged-in session launch the pinned app normally. Do not repeat verify-work or create another unchanged gap plan. When the missing selected-guest evidence is available, resume the existing bounded plan with $gsd-execute-phase 05 --gaps-only --ws first-playable-game. Candidate PR #2 has a passing exact-SHA hosted MVS receipt but remains OPEN / REVIEW_REQUIRED pending one approval. Phase 04: HOST-02 and frontend QUAL-03 are implemented and evidenced from the passing committed-snapshot receipt at bd74482e0050 (`04-FRONTEND-RECEIPT.json`, bound by the post-commit --check-docs) but acceptance is pending; after the contained 04-34 and 04-36 reviews 04-SECURITY.md has threats_open 2 (T-04-11 and T-04-61; T-04-38 and T-04-67 also open), 1 review finding is open (WR-11) and 3 are deferred, and `--require-closed --phase 04` exits 1 (CLOSURE). Open IDs and paths: tools/verify_playable.py (T-04-11, T-04-38, T-04-67, WR-11) and tools/independent_review.py (T-04-61). Next: `/gsd-plan-phase 04 --gaps --ws first-playable-game`.

The generic GSD progress router currently infers Phase 04 from its incomplete
verification report, while this workstream remains on Phase 05 because the
roadmap permits independent boot engineering to continue. Do not route back to
Phase 04 gap planning unless acceptance evidence or scope materially changes;
the existing Phase 04 report and methodology explicitly prohibit repeating an
unchanged external-blocker plan. Plan/summary counts are not phase acceptance.

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
- [Phase 04]: WR-02 is fixed after independent current-revision review confirms the live qualification denominator and rejects stale 23/23.
- [Phase 04]: WR-01 and WR-06/T-04-34 remain open; the four directed high-severity threats and actual pinned frontend unknown remain unresolved.
- [Phase 04]: Current-source mutation fixtures preserve the actual report baseline and compare qualification counts with a live suite run.
- [Phase 04]: Phase closeout is batched: one pre-plan evidence audit, one consolidated repository-gap plan, and one execute invocation for all waves. — This avoids serial wave-by-wave work and repeated planning while keeping external evidence and user-directed threat blockers open.
- [Phase 05]: Keep G-05-3 open because no independent source-flow artifact or selected-configuration attract/start observation supports a guest-write predicate.
- [Phase 05]: Do not claim selected-game compatibility or attract/start without an independently observed selected configuration and source-backed guest predicate.
- [Phase 05]: The exact-SHA hosted PR receipt establishes MVS CI only; keep PR #2 unmerged until required approval and keep frontend observation separate.
- [Phase 04]: 04-25: security register default mode checks consistency only; closure is the explicit --require-closed mode
- [Phase 04]: 04-26: frontend evidence binding is mandatory in check_docs (explicit repository or own .git, else fail closed); crosswalk scopes must resolve to registered threats or reviewed existing paths
- [Phase 04]: 04-27: guide prose outside the generated block may carry no requirement IDs, revision-like hex (except pinned YMFM/Z80) or capitalized status words; evidence records are written atomically after validate-and-scan
- [Phase 04]: 04-28: smoke lane extracted to run_frontend_smoke_lane; lane signals only the PID its own smoke recorded
- [Phase 04]: 04-29: WR-08 partially repaired by runtime_writable_storage audit; sdk_private.h guard stays heuristic (expected 04-31 disposition deferred)
- [Phase 04]: 04-30: bare home-name token skipped only for generic service-account names under GITHUB_ACTIONS (residual T-04-60 accepted)
- [Phase 04]: D-GAP-01: scratch directory itself is contained in independent_review.py; '..' anywhere and unmatched absolute-prefix globs fail closed
- [Phase 04]: 04-33: GIN-01 and GIN-04 accepted as fail-closed limits pinned by tests; smoke defers launch-window signals instead of masking them (mask is inherited by the frontend)
- [Phase 04]: 04-34: contained review (D-GAP-01) left 9 threats/2 findings open; T-04-44/52/55/60 accepted per D-GAP-02
- [Phase 04]: 04-35: residual verdicts citing CMakeLists.txt only as context (T-04-56, WR-08) classified gates; fix confined to check_runtime_storage.py
- [Phase 04]: D-GAP-02 (2026-10-10): the maintainer accepted T-04-44/52/55/60; they gate Phase 04 closure only through register status accepted, contained verdicts are evidence only
- [Phase 04]: 04-36: receipt re-qualified at bd74482e0050; focused 73-ID re-review left T-04-11, T-04-38, T-04-61, T-04-67 and WR-11 open (residual branch, CLOSURE exit 1); routed to /gsd-plan-phase 04 --gaps
- [Phase 04]: 04-37: glob_contained fails closed on /, ~ or $ alternatives in brace/extglob groups; review --revision pinned to 40-hex whole-line match
- [Phase 04]: 04-38: review provenance is a reviewed_revision..head ordering window; proves ordering only, not verdict-to-file binding
- [Phase 04]: 04-39: final lane reap isolated in _collect_after_kill; drain via select/os.read before SIGKILL (T-04-54 kept)

### Blockers

- 04-34/04-35/04-36 outcome (2026-10-10, supersedes the 04-31 line below): RetroArch re-qualified at 0d9612130092 (04-34) and bd74482e0050 (04-36, single instance, pinned 1.22.2); contained reviews (D-GAP-01) at both revisions; 04-35 repaired all 11 residual IDs with none unrepaired and no routed writable runtime symbol. The focused 04-36 re-review (73 IDs: 11 residual, 60 fresh, 2 supply-chain) left threats_open 2 (T-04-11, T-04-61; T-04-38 and T-04-67 also open) and WR-11 open; WR-08, GIN-01 and GIN-04 are deferred; T-04-44/52/55/60 stay accepted (D-GAP-02). Unrepaired paths routed to /gsd-plan-phase 04 --gaps: tools/verify_playable.py (T-04-11 receipt build outside any try block; T-04-38 and WR-11 reviewed_revision not validated; T-04-67 sole review revision value not checked) and tools/independent_review.py (T-04-61 brace-alternative absolute glob). CLOSURE exit 1; UNSCOPED exit 1 (2 in 04-SECURITY.md, 9 in the Phase 05 draft 05-SECURITY.md).
- 04-31 outcome (2026-10-10): clean committed-snapshot qualification passed all 17 lanes at 7615dd911678 (pinned RetroArch 1.22.2) and the fresh summary is bound by the post-commit docs gate; the tool-scoped independent review halted on containment (REVIEW HALTED: containment-violation), so all 33 threat IDs and 22 findings are recorded open and 04-SECURITY.md threats_open is 14. Supersedes the 04-23 line below.
- 04-23 outcome (2026-10-10): clean committed-snapshot qualification passed at aaf3f093ab0f (pinned RetroArch 1.22.2, max one instance sampled); the independent separate-context security review at that revision returned OPEN for 15 of 16 IDs and unscoped Bash made the 16th OPEN by the containment rule, so 04-SECURITY.md threats_open is 6 and WR-01/06/08/09 are open. Supersedes the 2026-10-10 entries below that report these closed.
- Owned-debug is now 47/47 passing, including refreshed identity/source-manifest and target-scoped inventory checks. This repairs the prior deterministic failure without establishing frontend acceptance.
- Resolved 2026-10-10: HOST-02 and frontend QUAL-03 pass from the clean committed-snapshot receipt at 706516b5a60c after fixing the shared `mvs_qualify` link and the non-self-contained shared core; the earlier SIGABRT was the sandboxed launch context.
- Resolved 2026-10-10: WR-01/06/08/09 fixed or superseded by bound receipt evidence and the retired evidence-map checker.
- Resolved 2026-10-10 (delegated decision): T-04-11/15/18/20 closed by fail-closed private-path sinks; T-04-34/38/43 closed; run-directory logs accepted as medium T-04-44. 04-SECURITY.md threats_open 0.
- Current Phase 04 evidence (2026-10-10): UAT 34/34 pass; HOST-02/frontend QUAL-03 Complete from the bound receipt summary; security register verified with 0 open threats. Whole-phase re-verification is the remaining step.
- Phase 05 Plan 05-05 halted at Task 1 tracer gate: local matrix rehearsal fails because tests/sdk/ORACLE.md no longer matches the pinned diagnostic manifest (updated timing claims from 05-03), and public-content rights inventory lacks 13 test-path rows. No PR or hosted receipt; G-05-5 remains open. Preserve local candidate branch agent-phase05-safe-candidate at 288a9d3 under ignored local/qualification/phase05-safe-candidate; do not publish until the oracle identity is reviewed and rights provenance is complete.
- Plan 05-05 halted at Task 1 tracer gate: local matrix fails on stale tests/sdk/ORACLE.md fixture-manifest identity; public-content rights inventory lacks 13 test-path rows; no PR or hosted receipt, G-05-5 remains open.
- Phase 05 Plan 05-06: independent selected configuration and source-backed guest attract/start predicate are unavailable; do not run or broaden selected-media qualification until this evidence exists.

## Accumulated Context

### Roadmap Evolution

- Phase 5 edited: Clarified Phase 05 technical dependency: verified Phase 04 native API/fixture artifacts permit media and boot engineering while Phase 04 RetroArch and user-directed threat acceptance gates remain blocked; added forward-progress policy.
- Phase 5 edited: Supersedes the stale scope note that Phase 05 must not start: Phase 05 planning and engineering now proceed from verified Phase 04 native API/fixture artifacts while Phase 04 frontend and user-directed threat acceptance blockers remain open.
