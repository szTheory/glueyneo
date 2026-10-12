---
gsd_state_version: "1.0"
milestone: first-playable-game
milestone_name: First Playable Game
current_phase: 05
current_phase_name: Selected MVS Boot
current_plan: 1
status: planning
stopped_at: Phase 04 complete, ready to plan Phase 05
last_updated: "2026-10-12T15:11:03.003Z"
last_activity: 2026-10-12
last_activity_desc: Phase 04 complete, transitioned to Phase 05
state_head: b81f6fc77b62fab6e261e64a8989c4cb62544464
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 68
  completed_plans: 68
  percent: 25
---

# Project State

## Project Reference

See [PROJECT.md](../../PROJECT.md) for the current project contract.

**Core value:** Trustworthy Neo Geo emulation that other software can embed easily.
**Current focus:** Phase 05 — Selected MVS Boot (Phase 04 complete 2026-10-12; milestone branch not yet shipped)

## Current Position

Phase: 05 — Selected MVS Boot
Current Plan: 05-06 (halted at Task 2)
Total Plans in Phase: 6
Status: Blocked: 05-VERIFICATION.md gaps_found; independent selected configuration and sourced guest-predicate evidence are unavailable
Last activity: 2026-10-12 — Phase 04 shipped in PR #3 (milestone branch); Phase 05 remains blocked at 05-06
Last Activity Description: Phase 04 complete, transitioned to Phase 05

Progress: [███░░░░░░░] 25%

## Progress

**Phases Complete:** 1 (Phase 04)
**Current Plan:** 1

## Performance Metrics

**Plans completed:** Phase 04 62/62 (04-51, 04-56, 04-57 superseded); Phase 04 accepted 2026-10-12
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
| Phase 04 P40 | 25 min | 2 tasks | 3 files |
| Phase 04 P41 | 20 min | 2 tasks | 4 files |
| Phase 04 P42 | 15min | 2 tasks | 3 files |
| Phase 04 P43 | 15 min | 3 tasks | 3 files |
| Phase 04 P44 | 12 min | 2 tasks | 3 files |
| Phase 04 P45 | 20 min | 2 tasks | 3 files |
| Phase 04 P46 | 12 min | 2 tasks | 3 files |
| Phase 04 P47 | 8min | 2 tasks | 3 files |
| Phase 04 P48 | 10min | 3 tasks | 3 files |
| Phase 04 P49 | 35 min | 2 tasks | 3 files |
| Phase 04 P50 | 12 min | 2 tasks | 1 files |
| Phase 04 P52 | 20min | 3 tasks | 5 files |
| Phase 04 P53 | 12 min | 2 tasks | 3 files |
| Phase 04 P55 | 12 min | 2 tasks | 4 files |
| Phase 04 P58 | 52 min | 5 tasks | 16 files |

### Backlog

- 04-64 (2026-10-11): G5WR-01, G5WR-02 and G5IN-01 recorded fixed pending the diff-scoped /gsd-code-review, which confirms or reopens them
- Pre-ship history allowlist step (user decision 2026-10-11; scope: pre-ship rows of the first-playable-game milestone branch, not reachable from git merge-base HEAD main): before the milestone squash merge run python3 tools/verify_playable.py --history-allowlist check; if stale run --history-allowlist write, commit it alone, run --history-allowlist check again, then the squash simulation (docs/testing.md "History gates after a squash merge"); rows added after the milestone squash merge are never covered. Frozen by 04-64 at e3a3a62d3828 (141 rows); the /gsd-code-review disposition edits make it stale until this step runs
- 04-58 in-run review (2026-10-11): D58IN-02 deferred for the diff-scoped /gsd-code-review: a working-tree digest comparison inside `rights_revision_errors` would extend the five-part `source_revision` predicate that docs/rights-inventory.md defines as the whole check; the working-tree digest is already enforced by `public_content.validate_repository_inventory` (and the release archive check), and the rights refresh is the final step of each round. Re-raise it in a tracked review file if the two gates disagree again.

## Session Continuity

**Last session:** 2026-10-11T16:50:02.133Z

**Stopped At:** Phase 04 complete, ready to plan Phase 05
**Resume File:** None

## Scope Notes

- Accepted research and primary-source references are preserved in [RESEARCH.md](RESEARCH.md). Outcome: locally reach interactive Metal Slug X gameplay with movement, firing, scrolling, and representative sound in one pinned MVS/macOS RetroArch setup; public CI uses a separate first-party fixture and never commercial game/BIOS data. All 20 requirements and their primary allocations in the roadmap are user-approved.
- Historical (superseded 2026-10-10; see Blockers): Planning milestone ID: `first-playable-game`; release version remains unassigned. Plans 04-01 through 04-18 have execution summaries. Plan 04-14 repaired the raw-quote and Info/IN parser cases; Plan 04-15 preserved the unavailable actual-frontend prerequisite without retrying RetroArch. Plan 04-18 restored the current security-count, report-evidence, and frontend claim gates without changing evidence dispositions. The fresh security audit verified 46 threats: 42 closed and four high disclosure threats remain open by user direction; T-04-34 remains medium/open. The fresh review confirms CR-02/WR-04 fixed and records CR-03/WR-05 open; carried WR-01/WR-02/WR-03 remain open. HOST-02 and frontend QUAL-03 remain Pending/unknown. Project Phase 04 begins this workstream; independent playable work does not close or depend on completion of the sibling hosted-release gate. Current facts: Plans 04-01 through 04-23 are executed; threats_open is 6 after the independent 04-23 review and the pinned RetroArch receipt is current at a6866818d97e.
- Milestone-start triage on 2026-10-07 found no open issues and one draft PR, [#1](https://github.com/szTheory/glueyneo/pull/1), for the separate diagnostic release work. It supplies no playable-game requirement or completion evidence.
- Work is isolated on `docs/first-playable-game-milestone`. The existing 138 planning relocations into the diagnostic workstream were verified byte-identical and committed; unrelated pre-existing methodology/configuration/preparation edits remain outside this milestone's commits.
- Carry-forward constraints: keep the owned native C17 core deterministic and host-independent; introduce the libretro/software-video path early; keep media/archive I/O outside the native core; retain the owned 68000 direction and gate Z80/YM2610 admission on evidence. PROJECT-D-48 permits the narrow ymfm C++14 exception behind a private C interface; a future C replacement is optional. The supplied BIOS is available locally, but the exact MVS profile and compatibility remain unqualified.
- Historical (superseded 2026-10-10; see Blockers): Approved Phase 04–07 sequencing is in [ROADMAP.md](ROADMAP.md): public playable tracer and early Z80/ymfm admission → selected MVS boot including required sound-CPU handshakes → active title control → sound and qualification. Plans 04-01 through 04-18 have summaries. Phase 04 remains incomplete. T-04-11, T-04-15, T-04-18 and T-04-20 remain high/open; T-04-34 remains medium/open. CR-02/WR-04 are fixed; CR-03/WR-05 and carried WR-01/WR-02/WR-03 remain open. Plan 04-18 restored the direct current-evidence gates; WR-06's independent disposition remains open. HOST-02 and frontend QUAL-03 remain Pending/unknown. Current facts: Plans 04-01 through 04-23 are executed; threats_open is 6 after the independent 04-23 review and the pinned RetroArch receipt is current at a6866818d97e.
- Goal: advance from the diagnostic SDK toward a playable Neo Geo game.
- Local qualification: a user-provided private game archive is stored under the Git-ignored `local/roms/` directory. Keep its contents and private checksums out of tracked files, CI, and release artifacts.
- The user-provided BIOS archive is also stored under the Git-ignored `local/roms/` directory. The copy matches its source, passes ZIP CRC validation and is untracked; those checks do not establish BIOS compatibility.
- Public CI: use original fixtures and/or homebrew assets only after confirming redistribution rights for the specific ROM assets; a source-code license alone is not sufficient evidence for bundled game data.
- The local archive passed ZIP CRC checks and matched all 13 ROM size/SHA-1 entries in MAME's current Neo Geo software list. That confirms the archive identity, not emulator compatibility.
- Next GSD work: no GSD command is warranted while the external evidence is unchanged. Plan 05-06 remains halted at Task 2: selected compatibility and GAME-02 need an independently observed selected configuration plus a source-backed guest attract/start predicate with oracle ancestry. The earlier RetroArch SIGABRT was the sandboxed launch context (debug session `.planning/debug/resolved/retroarch-startup-abort.md`); agent shells in the logged-in session launch the pinned app normally. Do not repeat verify-work or create another unchanged gap plan. When the missing selected-guest evidence is available, resume the existing bounded plan with $gsd-execute-phase 05 --gaps-only --ws first-playable-game. Candidate PR #2 has a passing exact-SHA hosted MVS receipt but remains OPEN / REVIEW_REQUIRED pending one approval. Phase 04: round-8 plans 04-63..04-65 executed on the pass path (receipt 6a15c34aa79b; allowlist frozen at e3a3a62d3828, 141 rows; G5WR-01, G5WR-02 and G5IN-01 `fixed` pending review; `threats_open` is 0 and `--require-closed --phase 04` exits 0). Phase 04 is not complete. Next: `/gsd-code-review 04 --ws first-playable-game` (diff-scoped to 1bc2f01ddbd5..HEAD covering 04-59..04-65; per METHODOLOGY review-round convergence), then `/gsd-verify-work 04 --ws first-playable-game`; pre-ship merge gate: the pre-ship history allowlist step (Backlog) runs before the milestone squash merge.

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
- [Phase 04]: 04-36: receipt re-qualified at 323fa1453329; focused 73-ID re-review left T-04-11, T-04-38, T-04-61, T-04-67 and WR-11 open (residual branch, CLOSURE exit 1); routed to /gsd-plan-phase 04 --gaps
- [Phase 04]: 04-37: glob_contained fails closed on /, ~ or $ alternatives in brace/extglob groups; review --revision pinned to 40-hex whole-line match
- [Phase 04]: 04-38: review provenance is a reviewed_revision..head ordering window; proves ordering only, not verdict-to-file binding
- [Phase 04]: 04-39: final lane reap isolated in _collect_after_kill; drain via select/os.read before SIGKILL (T-04-54 kept)
- [Phase 04]: 04-40: T-04-48 reopened (G2WR-03 defect in its own mitigation); round-3 fix evidence recorded, no row closed pending /gsd-secure-phase
- [Phase 04]: 04-41: receipt re-qualified at 3d90990e5cd0 (single instance, all lanes pass); evidence only, no register closed
- [Phase 04]: 04-38: review provenance binds dispositions to the reviewed_revision..head window, which proves ordering only (docs and T-04-38 narrowed; freshness by focused re-review), not equality — dispositions cite later verdict reviews
- [Phase 04]: 04-40: round-3 fix evidence is recorded with every row open and T-04-48 reopened (G2WR-03 defect in its own mitigation); per T-04-48 only the headless security audit (/gsd-secure-phase) closes rows
- [Phase 04]: 04-41: a gap round that changes a RECEIPT_BOUND path re-qualifies pinned RetroArch at its final code revision before the receipt is cited or routed to audit; a freshness probe (no RECEIPT_BOUND change after the receipt revision) gates the citation
- [Phase 04]: 04-43: register checker reports frontmatter errors with file line numbers and treats a threats_open key, parsed Threat ID table or unparsed Threat ID header as register-shaped for misnamed-file detection
- [Phase 04]: 04-44: qualification setup failures emit setup-error tokens; script entry() maps uncaught errors to internal-error (exit 1) and interrupts to exit 130
- [Phase 04]: 04-45: rollback .restore unlink failures are named in the aggregated error; lane output recorded once in order (earlier, drained, tail)
- [Phase 04]: 04-46: review dispositions anchor per review round (gap-round anchor = commit adding that round's review file); descent strict; claim is ordering only (G3WR-05)
- [Phase 04]: 04-48: pid-record checked first in compare_launch_probes; run_smoke builds a single outer pid-record diagnostic keeping the OSError class
- [Phase 04]: 04-49: round-4 fix evidence recorded on T-04-11/48/62 and G3WR/G3IN findings with all rows open; threats_open 12; closure left to /gsd-secure-phase
- [Phase 04]: 04-50: clean RetroArch re-qualification halted (receipt-halt, snapshot-inventory-mismatch before launch); evidence files unchanged; route to /gsd-debug then gap planning
- [Phase 04]: 04-52: verify_snapshot compares the real-directory set to row parent directories (reason snapshot-inventory-mismatch, path-free detail); rows/digest/schema unchanged
- [Phase 04]: 04-53: single-instance pinned RetroArch qualification passed at 09e43f0c4ea0; receipt bound (2877c18), requirements remain open pending audit
- [Phase 04]: 04-43: the register checker reads frontmatter as normalized keys (any duplicate key in any quoting form, and any unsupported YAML line, fails closed) and counts every GFM-rendered Threat ID table (unparsed Threat ID headers fail closed) — T-04-48/T-04-62
- [Phase 04]: 04-46: review provenance binds each disposition to the review round that raised the finding (04-REVIEW.md reviewed_revision, or the commit that added 04-REVIEW-GAPS[-Rn].md) with strict descent; still ordering only — G3WR-05
- [Phase 04]: 04-52: verify_snapshot also compares the materialized directory set with the inventory's parent directories (same snapshot-inventory-mismatch token, fixed path-free detail), so a lane that creates a directory in the snapshot fails at that lane — debug follow-up of snapshot-inventory-mismatch
- [Phase 04]: 04-51 superseded by 04-54 before execution (its route input was the debugged 04-50 halt); one live routing plan
- [Phase 04]: 04-55: register TABLE_END ends tables only at CommonMark ATX heading, blockquote and exact fence openers; other lines are rows and fail closed as malformed rows
- [Phase 04]: 04-58: lane Popen is byte mode and decoded once; rights source_revision is a five-part predicate checked before any Git call (T-04-103); D58IN-02 deferred to the diff-scoped review

### Blockers

- 04-64 outcome (2026-10-11, round 8 with 04-63 and 04-65; supersedes the 04-62 line below): round 8 completed on the pass path (no halt marker, no probe defect). 04-63 repaired the six squash-only test failures in the test fixtures (red 7daa2d867dcb with 6 failures, green 7e2470631ae9, 156 tests OK with one recorded full-history skip; no gate changed). 04-64 re-qualified pinned RetroArch 1.22.2 once at receipt revision 6a15c34aa79b (17 lanes pass, single instance), recorded G5WR-01, G5WR-02 and G5IN-01 as `fixed` pending the independent diff-scoped `/gsd-code-review`, and froze docs/history-allowlist.json at e3a3a62d3828 (141 rows; GEN=0 squash simulation ok, 156-test clone suite OK, rehearsal and later-branch probes ok). 04-65 recorded T-04-107..T-04-109 and T-04-SC (04-63)..(04-65) open (below `block_on` high; `threats_open` 0, `--require-closed --phase 04` exits 0). No in-run review ran and Phase 04 is not accepted; requirement checkboxes and `Gaps Found` rows are unchanged.
- 04-62 outcome (2026-10-11, round 7 with 04-59..04-61; supersedes the 04-58 line below): review-halt `scope-split-needed: 6` carried from 04-60 (also by 04-61). G5WR-01 per-row history allowlist gates (04-59) and generator (04-60) landed and pass `--check-docs`, but the real-repository squash simulation leaves 6 history-dependent clone-only suite failures (five share one cause: the documentation-copy helper omits the working-tree files of tolerated rights rows); none repaired. G5WR-02 and G5IN-01 fixes landed in 04-61. Dispositions stay `open` (G5WR-01 recorded `Fix incomplete`); no in-run review was performed. Pinned RetroArch was not launched (receipt still cdfbc99bafe7), no allowlist was generated or tracked, REQUIREMENTS.md and ROADMAP.md status text are unchanged. Route: `/gsd-plan-phase 04 --gaps --ws first-playable-game`.
- 04-58 outcome (2026-10-11, supersedes the 04-43..04-54 line below): gap G-04-35 is repaired. G4WR-01..04 and G4IN-01..03 were fixed test-first with red/green pairs re-proven in detached worktrees; a recurring rights `source_revision` check now runs in `--check-docs` and the `qualification_runner` CTest; an independent in-run diff review (headless `claude -p`, not the executor) judged all seven FIXED and its D58WR-01/D58WR-02 warnings and D58IN-01/03 infos were repaired in the run (one deferred item is in the Backlog subsection); the R3/R4 verdicts are transcribed (60 records, no open row). Pinned RetroArch 1.22.2 was re-qualified once at cdfbc99bafe7 (single instance, all lanes pass, receipt fresh). 04-SECURITY.md stays verified with threats_open 0; T-04-103 (medium) and T-04-SC (04-58) (low) are open below block_on for the next headless audit. Phase 04 is not yet accepted. Next: /gsd-code-review 04 --ws first-playable-game, then /gsd-verify-work 04 --ws first-playable-game.
- 04-43..04-54 outcome (2026-10-10, supersedes the 04-37..04-42 line and any 04-50 halt line below): round-4 fixes for T-04-11, T-04-48, T-04-62 and G3WR-01..05/G3IN-01..03 were delivered test-first; the 04-50 halt (snapshot-inventory-mismatch) was debugged (2f5e771, 157b49d, 9ca1fbe) and 04-52 added the directory-set guard; rows and findings stay open pending the headless audit, threats_open 15, `--require-closed --phase 04` exit 1 (expected pre-audit). Pinned RetroArch 1.22.2 re-qualified at 09e43f0c4ea0 (04-53, single instance, all lanes pass, freshness probe `receipt fresh 09e43f0c4ea0`); 04-51 superseded by 04-54. Requirements stay unchecked. Next: /gsd-secure-phase 04 --ws first-playable-game, /gsd-code-review 04 --ws first-playable-game, then /gsd-verify-work 04 --ws first-playable-game.
- 04-37..04-42 outcome (2026-10-10, supersedes the 04-34/04-35/04-36 line below): round-3 fixes for T-04-11, T-04-61, T-04-38 (narrowed to ordering), T-04-67, WR-11 and the eleven R2 findings were delivered test-first (red/green pairs re-proven in 04-40); T-04-48 reopened (G2WR-03 defect in its own mitigation); every row and finding stays open with fix evidence pending the headless audit, threats_open 9, CLOSURE exit 1 and UNSCOPED exit 1 (expected pre-audit). Pinned RetroArch 1.22.2 re-qualified at 3d90990e5cd0 (single instance, all lanes pass, freshness probe `receipt fresh 3d90990e5cd0`), superseding the 323fa1453329 receipt. Requirements stay unchecked. Next: /gsd-secure-phase 04 --ws first-playable-game, /gsd-code-review 04 --ws first-playable-game, then /gsd-verify-work 04 --ws first-playable-game.
- 04-34/04-35/04-36 outcome (2026-10-10, supersedes the 04-31 line below): RetroArch re-qualified at 45952598202a (04-34) and 323fa1453329 (04-36, single instance, pinned 1.22.2); contained reviews (D-GAP-01) at both revisions; 04-35 repaired all 11 residual IDs with none unrepaired and no routed writable runtime symbol. The focused 04-36 re-review (73 IDs: 11 residual, 60 fresh, 2 supply-chain) left threats_open 2 (T-04-11, T-04-61; T-04-38 and T-04-67 also open) and WR-11 open; WR-08, GIN-01 and GIN-04 are deferred; T-04-44/52/55/60 stay accepted (D-GAP-02). Unrepaired paths routed to /gsd-plan-phase 04 --gaps: tools/verify_playable.py (T-04-11 receipt build outside any try block; T-04-38 and WR-11 reviewed_revision not validated; T-04-67 sole review revision value not checked) and tools/independent_review.py (T-04-61 brace-alternative absolute glob). CLOSURE exit 1; UNSCOPED exit 1 (2 in 04-SECURITY.md, 9 in the Phase 05 draft 05-SECURITY.md).
- 04-31 outcome (2026-10-10): clean committed-snapshot qualification passed all 17 lanes at fd39a54b994c (pinned RetroArch 1.22.2) and the fresh summary is bound by the post-commit docs gate; the tool-scoped independent review halted on containment (REVIEW HALTED: containment-violation), so all 33 threat IDs and 22 findings are recorded open and 04-SECURITY.md threats_open is 14. Supersedes the 04-23 line below.
- 04-23 outcome (2026-10-10): clean committed-snapshot qualification passed at a6866818d97e (pinned RetroArch 1.22.2, max one instance sampled); the independent separate-context security review at that revision returned OPEN for 15 of 16 IDs and unscoped Bash made the 16th OPEN by the containment rule, so 04-SECURITY.md threats_open is 6 and WR-01/06/08/09 are open. Supersedes the 2026-10-10 entries below that report these closed.
- Owned-debug is now 47/47 passing, including refreshed identity/source-manifest and target-scoped inventory checks. This repairs the prior deterministic failure without establishing frontend acceptance.
- Resolved 2026-10-10: HOST-02 and frontend QUAL-03 pass from the clean committed-snapshot receipt at 5e6a3b8f50d3 after fixing the shared `mvs_qualify` link and the non-self-contained shared core; the earlier SIGABRT was the sandboxed launch context.
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
