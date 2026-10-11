# Roadmap: Glueyneo

## Overview

The `first-playable-game` planning milestone advances the bounded diagnostic SDK toward one playable Metal Slug X MVS scenario in a pinned macOS RetroArch build. An original redistributable fixture provides the first visible native and frontend result and all public CI inputs. The private game and BIOS path is qualified separately. Phase 03 of the sibling diagnostic SDK workstream remains open; this roadmap does not depend on its hosted-release gate or assign a release version.

## Milestones

- 🚧 **first-playable-game** First Playable Game
- 📋 **Next milestone: snapshots and durable saves** — outlined only; define restored continuation, versioning, and recovery contracts after gameplay evidence and user priorities are known.
- 📋 **Longer horizon** — additional board/game profiles, measured optimization, platform qualification, and shared-host integration remain revisable.

## first-playable-game — First Playable Game

**Status:** Approved by the user on 2026-10-07. Phases 4–7; release version unassigned. Plans 04-01 through 04-58 are executed (04-51, 04-56 and 04-57 superseded). Round-6 gap closure 04-58 repaired G-04-35: the round-4 review findings G4WR-01..04 and G4IN-01..03 test-first, a recurring rights `source_revision` check, an independent in-run review of the repair diff (all judged fixed) and the R3/R4 verdict transcription (no open disposition rows). HOST-02 and frontend QUAL-03 are evidenced from the tracked 04-FRONTEND-RECEIPT.json at the 04-58 clean committed-snapshot receipt for 4e6a40e66e9e (pinned RetroArch 1.22.2, all lanes pass, single instance, bound by the post-commit --check-docs). 04-SECURITY.md is verified with threats_open 0 and `check_security_register.py first-playable-game --require-closed --phase 04` exits 0 (the Phase 05 draft register is outside Phase 04 closure). Phase 04 is not yet accepted: the diff-scoped `/gsd-code-review 04 --ws first-playable-game` and `/gsd-verify-work 04 --ws first-playable-game` come next. Phase 05 is in progress (blocked at Plan 05-06); Phases 06–07 have not started.

## Phases

- [ ] **Phase 4: Public Playable Tracer** - A first-party guest produces software video and input response through native C and actual RetroArch consumers; early sound admission establishes feasibility.
- [ ] **Phase 5: Selected MVS Boot** - Normalized private media can boot the selected BIOS and game to attract/start through guest execution and required board behavior.
- [ ] **Phase 6: Active Title Control** - The selected game reaches an active scene with guest-driven movement, firing, graphics, and scrolling.
- [ ] **Phase 7: Sound and Scenario Qualification** - Public sound and regression evidence and the private RetroArch scenario support a bounded playable claim.

## Phase Details

### Phase 4: Public Playable Tracer

**Goal**: A maintainer can rebuild and run an original guest with visible, input-driven behavior through the ordinary native API and an actual pinned RetroArch build, while resolving the selected sound candidates' admission gates before full integration.
**Depends on**: Phases 01/02 provide only bounded CPU/SDK foundations; no dependency on completing sibling Phase 03's hosted-release gate.
**Requirements**: TRAC-01, TRAC-02, TRAC-03, HOST-02, API-05, SND-01, SND-02, QUAL-03
**Success Criteria** (what must be TRUE):
  1. A maintainer can rebuild the original public fixture from tracked, rights-audited source and assets, run it through a C consumer, and see a guest-produced software frame with checked dimensions, format, pitch, and bounds.
  2. A C integrator can advance a bounded frame with explicit sampled input and owned video/audio buffers, capacities, timing and produced-count semantics, progress/stop information, and actionable errors; a controlled input changes the guest and visible output while a wrong-input control fails.
  3. A user can load, run, control, and unload that fixture in an actual pinned macOS RetroArch build with software video, documented controller mapping, and frontend-owned pacing.
  4. A maintainer can reproduce passing admission evidence for the pinned Z80 and private-interface ymfm YM2610 candidates, including license/source/state audits, cycle or clock and interrupt/bus behavior, deterministic timing, continuation and independent-instance evidence, contained C++ failures, and static/shared C-consumer linkage; a failed gate blocks admission and requires bounded replanning rather than phase completion.
  5. An integrator can follow the clean-tree build/install/load procedure for the native library and libretro adapter on the selected macOS configuration and identify exact dependency, compiler, SDK, OS, architecture, and frontend identities plus untested configurations.

**Plans**: 59/62 plans executed (04-51, 04-56 and 04-57 superseded and excluded from the count). Round-8 gap-closure plans 04-63..04-65 (waves 60-62, sequential) follow the 04-62 halt (`scope-split-needed: 6`): 04-63 repairs the six squash-only test failures test-first and completes the squash simulation; 04-64 re-qualifies pinned RetroArch once, records the G5 fixes as fixed pending the diff-scoped `/gsd-code-review` and freezes the pre-ship history allowlist; 04-65 records the register rows and refreshes status after the freeze. Round-7 gap-closure plans 04-59..04-62 (waves 56-59, sequential) are planned for the round-5 review findings G5WR-01 (history gates fail after a squash merge), G5WR-02 and G5IN-01. Per the user decision of 2026-10-11 ("Scope tolerance"), G5WR-01 uses a per-row allowlist with per-record digest pins (no repository-wide mode) covering pre-ship rows of the first-playable-game milestone branch (cited revision not reachable from `git merge-base HEAD main`; strictly passing rows only): 04-59 adds the gate tolerance, 04-60 the allowlist generator/freshness check and the real-repository squash simulation with a probe-verified suite arbiter, 04-61 repairs G5WR-02/G5IN-01 and documents all three plus the pre-ship regenerate-and-simulate step, and 04-62 records the fix evidence with the G5 rows open pending the independent `/gsd-code-review`, re-qualifies pinned RetroArch once, generates the allowlist current at plan end and refreshes status. Round-6 gap-closure plan 04-58 (wave 55, G-04-35) is executed: R4 warnings and infos repaired test-first, the recurring rights `source_revision` check added, an independent in-run diff review judged the repairs fixed, R3/R4 verdicts transcribed (no open disposition rows) and pinned RetroArch re-qualified at 4e6a40e66e9e because receipt-bound paths changed. History: round-5 plan 04-55 fixed the register table-end rule; 04-56 and 04-57 were superseded on 2026-10-10 by the round-5 /gsd-secure-phase run, which closed every in-scope row (threats_open 0); round-4 plans 04-43..04-54 repaired T-04-11, T-04-48, T-04-62 and G3WR-01..05/G3IN-01..03 and re-qualified after the 04-50 receipt-halt was debugged (snapshot-inventory-mismatch: 59c53b3, 8face2a, 2bbaff3); rounds 1-3 (04-24..04-42) repaired the earlier verification gaps and review findings. Phase 04 acceptance awaits the diff-scoped re-review (`/gsd-code-review 04 --ws first-playable-game`) and re-verification (`/gsd-verify-work 04 --ws first-playable-game`).
- [x] 04-59-PLAN.md — G5WR-01 gates: per-row allowlist tolerance (history-absent revision + matching per-record pin + rights working-tree digest; every resolving revision and unlisted or edited row strict; appends void no pin) in the rights, review-provenance and frontend-evidence gates, `unverifiable-history:` lines, squash-merge fixture tests (gap closure, Wave 56)
- [x] 04-60-PLAN.md — G5WR-01 tooling and proof: deterministic `--history-allowlist write|check` generator listing only strictly verified rows not reachable from `git merge-base HEAD main`, real-repository squash simulation with a probe-verified suite arbiter, full-history rehearsal, branch-cut probe, classified simulation-driven repairs (gap closure, Wave 57, depends on 04-59)
- [x] 04-61-PLAN.md — G5WR-02 single-marker lane readiness and G5IN-01 rights path order, test-first; docs contract for all three IDs including the milestone-branch scope, the pre-ship regenerate-and-simulate step and the openly stated permanent tolerance of listed rows (gap closure, Wave 58, depends on 04-60)
- [x] 04-62-PLAN.md — round-7 closeout (executed as a halt closeout: review-halt scope-split-needed: 6): fix-evidence transcription (G5 rows open pending the independent `/gsd-code-review`; no in-run review) and security rows, orchestrator-edit pre-flight, re-qualify pinned RetroArch once, refresh status with the pre-ship allowlist step, generate the history allowlist current at plan end (gap closure, Wave 59, depends on 04-61)
- [ ] 04-63-PLAN.md — round-8 G5WR-01 completion part 1: repair the six squash-only test failures (documentation-copy helper omits rights-row files; one test checks out the live receipt revision) test-first, red then green in a squash-simulated clone, plus local-squash, full-history rehearsal and branch-cut probes; bounded halt (gap closure, Wave 60, depends on 04-62)
- [ ] 04-64-PLAN.md — round-8 records and freeze: single pinned RetroArch re-qualification, G5WR-01/G5WR-02/G5IN-01 recorded fixed pending the diff-scoped `/gsd-code-review`, freeze the pre-ship history allowlist and prove it with the squash simulation on the committed file, SUMMARY with the requirement-to-lane map; or the halt records (gap closure, Wave 61, depends on 04-63)
- [ ] 04-65-PLAN.md — round-8 closeout after the freeze: register rows T-04-107..109 and T-04-SC (04-63..04-65), status refresh with the review-then-verify route and the pre-ship merge gate, or the halt route (gap closure, Wave 62, depends on 04-64)
- [x] 04-58-PLAN.md — G-04-35: fix G4WR-01..04 and G4IN-01..03 test-first, add the recurring rights source_revision check, independent in-run review of the repair diff, transcribe R3/R4 verdicts, re-qualify pinned RetroArch once, then refresh REQUIREMENTS/ROADMAP/STATE status (gap closure, Wave 55)
- [ ] 04-57-PLAN.md — Superseded on 2026-10-10 by the round-5 /gsd-secure-phase run, not executed. Original scope: record round-5 fix evidence and open rows (T-04-SC 04-55..04-57, T-04-101, T-04-102) in 04-SECURITY.md with a recomputed threats_open; derive the route from evidence; point ROADMAP/STATE at /gsd-secure-phase (canonical reviewer prompt), the focused re-review and re-verification, or gap planning (gap closure, Wave 54)
- [ ] 04-56-PLAN.md — Superseded on 2026-10-10 by the round-5 /gsd-secure-phase run, not executed; that run's reviewer prompt carries the Grep output-size rule. Original scope: tools/independent_review.py `system-prompt`: tracked canonical reviewer system prompt with a Grep output-size rule, test-first, containment gate (D-GAP-01) pinned unchanged; docs and rights refresh (gap closure, Wave 53)
- [x] 04-55-PLAN.md — check_security_register.py ends register tables only at CommonMark block starts so `#note`-style lines cannot hide open rows (T-04-48/T-04-62), test-first with docs and rights refresh (gap closure, Wave 52)
- [x] 04-54-PLAN.md — Compute the route from the 04-49/04-52 evidence, the 04-53 outcome, aggregate docs probe, receipt freshness and named requirement lanes/tests; point ROADMAP/STATE at /gsd-secure-phase, the focused re-review and re-verification, or at /gsd-debug and gap planning; replaces superseded 04-51 (gap closure, Wave 51)
- [x] 04-53-PLAN.md — Re-qualify pinned RetroArch 1.22.2 once at the final round-4 code revision (single instance, pgrep empty before/after), record and bind the receipt, prove it fresh against fix(04-52), assert the named requirement lanes pass; halt to 04-53-branch.txt (gap closure, Wave 50)
- [x] 04-52-PLAN.md — verify_playable.py: snapshot verification also compares the directory set (debug follow-up of snapshot-inventory-mismatch), test-first with docs and rights refresh; record the 04-50 debug resolution and open T-04-SC (04-52..04-54) rows in 04-SECURITY.md (gap closure, Wave 49)
- [ ] 04-51-PLAN.md — Superseded by 04-54 on 2026-10-10, not executed (its route input was the debugged 04-50 halt). Original scope: route from the 04-49 evidence and 04-50 outcome (gap closure, Wave 48)
- [x] 04-50-PLAN.md — Refresh rights inventory, then re-qualify pinned RetroArch 1.22.2 once at the final round-4 code revision (single instance, pgrep empty before/after), record and bind the receipt, prove it fresh, assert the named requirement lanes pass (gap closure, Wave 47)
- [x] 04-49-PLAN.md — Re-prove round-4 red/green evidence (assertion failures only) in detached worktrees; HEAD build plus named CTest requirement evidence; record it on T-04-11/48/62 (rows stay open per T-04-48), add open T-04-SC (04-43..04-51) rows, record G3WR-01..05/G3IN-01..03 open with fix evidence (gap closure, Wave 46)
- [x] 04-48-PLAN.md — retroarch_smoke.py: diagnostic probe reports pid-record (G3WR-03), single pid-record diagnostic keeping the error class (G3IN-02), docs (gap closure, Wave 45)
- [x] 04-47-PLAN.md — independent_review.py: generalized reviewable finding IDs with malformed-ID rejection (G3WR-02), leading-$ containment (G3IN-01), docs (gap closure, Wave 44)
- [x] 04-46-PLAN.md — verify_playable.py: per-round review provenance with strict descent (G3WR-05), docs (gap closure, Wave 43)
- [x] 04-45-PLAN.md — verify_playable.py: rollback cleanup guard (G3WR-04), single-copy lane output (G3WR-01), docs (gap closure, Wave 42)
- [x] 04-44-PLAN.md — verify_playable.py: setup/entry guard with typed tokens and no traceback (T-04-11), docs (gap closure, Wave 41)
- [x] 04-43-PLAN.md — check_security_register.py: normalized frontmatter keys fail closed on quoted/duplicate keys (T-04-48), every GFM table form counted with fail-closed sweep (T-04-62), misnamed registers and verified-with-comment (G3IN-03), docs (gap closure, Wave 40)
- [x] 04-42-PLAN.md — Document round-3 contracts (provenance narrowed to ordering, receipt currency), route STATE/ROADMAP to the headless security audit (/gsd-secure-phase), focused re-review and re-verification after the receipt freshness probe, or to /gsd-debug and gap planning on a halt (gap closure, Wave 39)
- [x] 04-41-PLAN.md — Refresh rights inventory, then re-qualify pinned RetroArch 1.22.2 at the final round-3 code revision (single instance, pgrep empty before/after, 04-34 procedure), record and bind the receipt, prove it fresh against every RECEIPT_BOUND path (gap closure, Wave 38)
- [x] 04-40-PLAN.md — Re-prove red/green evidence in detached worktrees; record it on T-04-11/61/38/67 (rows stay open per T-04-48), reopen T-04-48 with G2WR-03 evidence, narrow T-04-38, add open T-04-SC (04-37..04-42) rows, record WR-11 and the eleven R2 findings open with fix evidence (gap closure, Wave 37)
- [x] 04-39-PLAN.md — verify_playable.py: evidence rollback for absent files and failed restores (G2WR-05), lane pipe drain without reaping (G2IN-02), full CTest after both wave-35 plans (gap closure, Wave 36)
- [x] 04-38-PLAN.md — verify_playable.py: receipt-time catch-all with minimal fail receipt (T-04-11), public build reasons (G2IN-03), reviewed_revision window ordering (T-04-38 narrowed, T-04-67, WR-11) (gap closure, Wave 35)
- [x] 04-37-PLAN.md — Review/register/smoke gates: absolute brace/extglob alternatives fail closed (T-04-61), 40-hex revision pin (G2WR-03), decimal-phase registers (G2WR-04), verified case (G2IN-01), launch-window signal (G2WR-06) (gap closure, Wave 35)
- [x] 04-36-PLAN.md — Focused contained re-review of residual, freshness-affected and T-04-SC (04-35)/(04-36) IDs (with re-qualification if receipt-bound code changed), phase-scoped `--require-closed --phase 04`, reconcile SECURITY/VALIDATION/REQUIREMENTS traceability/ROADMAP/STATE (gap closure, Wave 34)
- [x] 04-35-PLAN.md — Classify the 04-34 residual open IDs into fixed file groups and repair them test-first within a 14-file bound, or record them unrepaired with reasons (gap closure, Wave 33)
- [x] 04-34-PLAN.md — Re-qualify pinned RetroArch at the repaired HEAD (single instance), contained tool-scoped independent review of 77 IDs (43 threats, 34 findings) gated by tools/independent_review.py, transcribe verdicts, record D-GAP-01/D-GAP-02 (gap closure, Wave 32)
- [x] 04-33-PLAN.md — Qualification-tool robustness: lane/smoke process-group safety (GWR-04/05, T-04-54), clean docs-check exception path (T-04-11), review provenance binding (T-04-38), all-or-nothing evidence write (GWR-06), storage audit (GWR-02), GIN-01..04 (gap closure, Wave 31)
- [x] 04-32-PLAN.md — Gate hardening: tracked independent-review containment/verdict/transcription tool with the D-GAP-01 boundary, register gate fail-closed on schema drift (GWR-01), consistency CTest rename, phase-scoped closure and no-weakening config (GWR-03), quoted status (gap closure, Wave 30)
- [x] 04-31-PLAN.md — Re-qualify pinned RetroArch with --clean --check-docs at the repaired HEAD (fully automated), bind the fresh summary after commit, tool-scoped verdict-only independent review of all open threats and 22 findings, reconcile register/dispositions/ROADMAP/STATE with the computed next command (gap closure, Wave 29)
- [x] 04-30-PLAN.md — Remaining review findings, part 2: username token narrowed to GitHub Actions service accounts with documented residual (WR-06, T-04-60), dead smoke code (IN-02), core dependency parsing (IN-03), rights inventory rows (gap closure, Wave 28)
- [x] 04-29-PLAN.md — Remaining review findings, part 1: runtime writable-storage audit and documented guard (WR-08), workstream-gated register test and workstream block_on (WR-07), rights inventory rows (gap closure, Wave 27)
- [x] 04-28-PLAN.md — Launch safety: pre-launch single-instance refusal, PID-scoped quit, no orphan on outer timeout, process-group lane timeouts, survivor signalling limited to the lane's recorded child (CR-07, WR-03/04/05; gap closure, Wave 26)
- [x] 04-27-PLAN.md — Outside-block claim gate, guide private-path scan, atomic scanned records, guide prose rewrite (CR-04, WR-01, IN-01, IN-04 prose-claim gap; gap closure, Wave 25)
- [x] 04-26-PLAN.md — Mandatory evidence binding incl. .git-less snapshot, field validation, crosswalk provenance (CR-03/05, WR-02/09, IN-04 binding/scope gaps; gap closure, Wave 24)
- [x] 04-25-PLAN.md — Strict security register gate: frontmatter-only key, all register tables, closure mode, documented in docs/testing.md (CR-06, IN-04 register gap; gap closure, Wave 23)
- [x] 04-24-PLAN.md — Canonical private-path matching and fail-closed sinks, early-failure receipt, redacted CLI errors (CR-01/02/08/09, IN-04 scan/receipt gaps; gap closure, Wave 22)
- [x] 04-23-PLAN.md — Re-qualify pinned RetroArch at the current revision and reconcile Phase 04 traceability (gap closure, Wave 21)
- [x] 04-22-PLAN.md
- [x] 04-21-PLAN.md

**Wave 1**
- [x] 04-01-PLAN.md

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 04-02-PLAN.md
- [x] 04-03-PLAN.md

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 04-04-PLAN.md

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 04-05-PLAN.md

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 04-06-PLAN.md

**Wave 6** *(gap closure; blocked on Wave 5 completion)*
- [x] 04-07-PLAN.md — Bind qualification to a complete immutable source snapshot

**Wave 7** *(gap closure; follows Wave 6)*
- [x] 04-08-PLAN.md — Diagnose actual RetroArch exit and regenerate final qualification receipt

**Wave 8** *(gap closure; follows Wave 7)*
- [x] 04-09-PLAN.md — Normalize HOST coverage metadata while preserving human frontend handoff
- [x] 04-10-PLAN.md — Repair diagnostic path redaction, fixture identity, and pinned app quit target

**Wave 9** *(gap closure; blocked on Wave 8 completion)*
- [x] 04-11-PLAN.md — Bind receipt rows to committed archive bytes and reconcile the validation map

**Wave 10** *(gap closure; blocked on Wave 9 completion)*
- [x] 04-12-PLAN.md — Repair receipt types, complete path redaction, validation-map state and CPU inventory evidence

**Wave 11** *(gap closure; blocked on Wave 10 completion)*
- [x] 04-13-PLAN.md — Close escaped-quote path disclosure and reconcile review evidence

**Wave 12** *(gap closure; blocked on Wave 11 completion)*
- [x] 04-14-PLAN.md — Redact raw-quoted diagnostic paths, parse Info findings, and reconcile bounded sound-admission statuses

**Wave 13** *(actual frontend evidence; follows Wave 12)*
- [x] 04-15-PLAN.md — Observe pinned RetroArch only in a materially changed, functioning launch context

**Wave 14** *(gap closure; follows Waves 12 and 13)*
- [x] 04-16-PLAN.md — Repair newline-path diagnostic disclosure and contradictory review-state acceptance

**Wave 15** *(gap closure; follows Wave 14)*
- [x] 04-17-PLAN.md — Reject contradictory frontend closure claims and reconcile WR-06 evidence

**Wave 16** *(gap closure; follows Wave 15)*
- [x] 04-18-PLAN.md — Repair security-count, current evidence-map, and frontend claim gates

**Wave 17** *(bounded gap closure; follows Wave 16)*
- [x] 04-19-PLAN.md — Independently review and reconcile security/review dispositions with direct regressions

**Wave 18** *(bounded gap closure; follows Wave 17)*
- [x] 04-20-PLAN.md — Repair current review/evidence reconciliation and independently review the frontend sanitizer

**UI hint**: no

### Phase 5: Selected MVS Boot

**Goal**: A user can load the selected private MVS media and see the guest-executed game reach its attract/start path with a documented, bounded configuration.
**Depends on**: Phase 4's verified native API and fixture foundation; Phase 4 acceptance, now pending only the diff-scoped re-review and re-verification (04-SECURITY.md is verified with threats_open 0 after the round-5 audit; 04-58 repaired G-04-35), does not block Phase 5 engineering, but remains a blocker to Phase 4 acceptance (HOST-02/frontend QUAL-03 are implemented and evidenced at the 04-58 receipt 4e6a40e66e9e, acceptance pending) and any corresponding frontend/security claim. The sound-CPU interaction needed by BIOS/game boot is delivered here even though audible output is qualified in Phase 7.
**Requirements**: MEDIA-02, MEDIA-03, MEDIA-04, GAME-02
**Success Criteria** (what must be TRUE):
  1. A C integrator can supply immutable normalized cartridge and BIOS regions for the selected MVS profile under explicit lifetimes, layout, byte order, and resource limits.
  2. A user can load the selected unmodified local game and BIOS archives through a documented RetroArch/import path whose bounded archive handling stays outside the native core.
  3. A user gets distinct, actionable missing, incompatible, unsupported, malformed, and limit errors; after a rejected load, valid media can load or the instance can be destroyed safely.
  4. In the selected configuration, the guest reaches the game's attract/start path through the owned 68000 and required MVS banking, protection, timing, interrupts, and sound-CPU handshakes, with source-qualified regression evidence and no canned boot or fabricated handshake.

**Plans**: Six plans are recorded: 05-01, 05-02, and 05-04 complete; 05-03 halted without a selected guest checkpoint; 05-05 halted at local candidate gates; and 05-06 halted at Task 2 because independent selected configuration and sourced guest-predicate evidence are unavailable. Plan 05-06 cleared the diagnostic oracle/rights gates and passed exact-SHA hosted MVS qualification for PR #2, but the selected boot requirement remains open. Phase 05 remains incomplete; selected-media compatibility, attract/start, and actual RetroArch behavior remain unqualified.
**Wave 1**
- [x] 05-01-PLAN.md — MVS media path and guest-driven selected boot

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 05-02-PLAN.md — Split selected game/BIOS mapping and exact seven-test current-revision CI evidence

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 05-03-PLAN.md — Source-qualified selected-guest boot to direct attract/start and pinned-app smoke (halted)
- [x] 05-04-PLAN.md — Source-justified guest-write checkpoint, bounded selected run and conditional pinned-app smoke

**Wave 4** *(05-05 and 05-06 halted; 05-06 hosted candidate gate passed)*
- [x] 05-05-PLAN.md — Reviewed public-safe revision and exact-SHA hosted seven-test MVS receipt
- [x] 05-06-PLAN.md — Reconcile oracle/rights gates, establish bounded selected-guest evidence, and bind hosted results to the final SHA

### Phase 6: Active Title Control

**Goal**: A user can enter and control one stated active Metal Slug X scene with the required visible board behavior.
**Depends on**: Phase 5
**Requirements**: GAME-03, GAME-04
**Success Criteria** (what must be TRUE):
  1. A user can enter the selected active scene in RetroArch and use the documented mapping to move and fire; the effects come from guest execution and emulated input, not title-specific canned output.
  2. A user can see the scene's required graphics, layering, palettes, and scrolling, with the supported scene and unresolved raster/timing behavior stated precisely and original slowdown preserved where modeled.

**Plans**: TBD

### Phase 7: Sound and Scenario Qualification

**Goal**: The selected scene has representative guest-driven sound, and clean-tree public checks plus a separate private local run establish the exact native, libretro, and game claims.
**Depends on**: Phase 6 and the sound admission evidence from Phase 4
**Requirements**: API-06, SND-03, SND-04, QUAL-01, QUAL-02, QUAL-04
**Success Criteria** (what must be TRUE):
  1. A maintainer can run a public guest-driven sound fixture through Z80/YM2610 and reproduce non-silent, signal-qualified output with meaningful controls, identifying native chip output separately from resampling and device behavior.
  2. In the pinned RetroArch setup, a user hears representative music and action-triggered effects while moving and firing in the selected scene; machine-observable steps of the exact local boot-to-play scenario are reproducible by automated checks, with only residual subjective or unavailable evidence requiring a human, and missing sound behavior is stated.
  3. A maintainer can repeat and partition the supported fixture workload and interleave or concurrently run distinguishable native instances while matching isolated-baseline guest, video, and audio results at equal emulated boundaries.
  4. A maintainer can run clean-tree, proportionate local and public-CI checks on the public fixture through native and real libretro consumers, comparing frame, input, and audio observations at matching emulated boundaries with documented conversion, and covering lifecycle, malformed inputs, relevant fuzz/sanitizer, and retained diagnostic SDK regressions.
  5. A consumer can identify the exact qualified private scenario, public fixture coverage, oracle ancestry, and unknown or unsupported behavior in current documentation; private media identities and derived evidence stay local, and fixture success, emulator agreement, or BIOS/archive integrity is not presented as broader hardware or game compatibility.

**Plans**: TBD

## Sequencing and Evidence Boundaries

The Phase 4 frame contract may expose an initially silent audio buffer, but API-06 and native/libretro audio equivalence remain open until Phase 7. Phase 5 must implement any Z80/sound-CPU handshakes that the real boot path requires; deferring audible YM2610 output does not license a fake handshake. A failed sound admission or unexpectedly large CPU/board gap triggers explicit bounded replanning, not reduced acceptance. Public fixture CI and private game qualification are separate claims. Private archives, identities, captures, traces, and logs remain outside Git, public CI, and releases. An implementation-reference match is not original-hardware proof.

Each phase includes the automated evidence and independent review appropriate to its new behavior, including isolation and determinism checks as the relevant machine state is added. Phase 7 owns the final combined audio/video/input and consumer qualification; it does not defer earlier regression testing. Phase 4's first vertical result is visible fixture/input behavior before the bounded sound admission work. Guest framebuffers and the existing RetroArch interface do not require a new core-owned application UI or a separate UI-design workflow.

## Progress

**Execution Order:** Phase 4's verified native API/fixture foundation → Phase 5 MVS boot engineering → Phase 6 → Phase 7. Phase 5 engineering may proceed while Phase 4 acceptance remains pending: the register is closed (04-SECURITY.md threats_open 0; the new rows T-04-103 and T-04-SC (04-58) stay open below the blocking threshold for the next audit) and the pinned RetroArch receipt at 4e6a40e66e9e (04-58) is current, but the diff-scoped re-review and /gsd-verify-work 04 are still to run. Those steps gate Phase 4 acceptance and related claims; they do not establish a technical dependency for the separate media, board, and guest-execution work. Phase 5 must not close or reinterpret Phase 4 findings.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 4. Public Playable Tracer | 59/62 | In Progress | - |
| 5. Selected MVS Boot | 6/6 | In Progress | - |
| 6. Active Title Control | 0/TBD | Not started | - |
| 7. Sound and Scenario Qualification | 0/TBD | Not started | - |
