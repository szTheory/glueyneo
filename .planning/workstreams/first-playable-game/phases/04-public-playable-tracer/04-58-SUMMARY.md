---
phase: 04-public-playable-tracer
plan: 58
subsystem: qualification-tooling
tags: [gap-closure, rights-provenance, lane-output, security-register, retroarch-requalification]

requires:
  - phase: 04-public-playable-tracer
    provides: 04-55 register table-end fix and the 04-53 receipt at 09e43f0c4ea0
provides:
  - G4WR-01..04 and G4IN-01..03 repaired test-first with red/green evidence
  - recurring rights source_revision check (rights_revision_errors) wired into --check-docs and the qualification_runner CTest
  - independent in-run review of the repair diff (all seven FIXED; D58 findings repaired)
  - R3/R4 verdicts transcribed (60 records, none open)
  - pinned RetroArch re-qualified once at cdfbc99bafe7 and bound
affects: [04-verification, code-review-04, verify-work-04, phase-05]

actuals:
  tokens: 42254
  tasks: 5
  commits: 16
plan_head_before: b6977421e5c6a6abc4b8cc749ac1a4ef2fa89bca
plan_head_after: f128facafebc705bae4fd33071e07639d6444198

tech-stack:
  added: []
  patterns:
    - byte-level lane pipe decoded once (replace) with one newline translation
    - exact-spelling register declarations with case-insensitive duplicate detection
    - five-part rights source_revision predicate checked before any Git call

key-files:
  created:
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-58-SUMMARY.md
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - tests/tools/check_security_register.py
    - tests/tools/test_check_security_register.py
    - tests/libretro/retroarch_smoke.py
    - tests/libretro/test_retroarch_smoke.py
    - docs/rights-inventory.md
    - docs/testing.md
    - docs/first-playable-build.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-FRONTEND-RECEIPT.json
    - .planning/workstreams/first-playable-game/REQUIREMENTS.md
    - .planning/workstreams/first-playable-game/ROADMAP.md
    - .planning/workstreams/first-playable-game/STATE.md

key-decisions:
  - "Lane Popen is byte mode; earlier segment, drained chunks and new tail are joined and decoded once (G4WR-01/03)."
  - "rights_revision_errors enforces exactly the five-part predicate; the working-tree digest stays with public_content.validate_repository_inventory (D58IN-02 deferred)."
  - "Requirement rows keep Gaps Found; requirements mark-complete was not run because the plan reserves that flip for phase completion after /gsd-verify-work."

requirements-completed: [TRAC-01, TRAC-02, TRAC-03, HOST-02, API-05, SND-01, SND-02, QUAL-03]

coverage:
  - id: D1
    description: "G4WR-04 recurring rights source_revision check (five-part predicate) in --check-docs and the real-repository CTest, with the inventory corrected"
    requirement: "QUAL-03"
    verification:
      - kind: unit
        ref: "tests/tools/test_verify_playable.py#test_g4wr_04_*"
        status: pass
    human_judgment: false
  - id: D2
    description: "G4WR-01/G4WR-03/D58WR-02 lane output kept once, in order, decoded once; non-UTF-8 recorded; a closed-pipe lane is still signalled"
    requirement: "TRAC-01"
    verification:
      - kind: unit
        ref: "tests/tools/test_verify_playable.py#test_g4wr_01_*, test_g4wr_03_*, test_d58wr_02_*"
        status: pass
    human_judgment: false
  - id: D3
    description: "G4WR-02/G4IN-01 register checker exact declarations, ASCII digits and security-named candidate scan"
    requirement: "QUAL-03"
    verification:
      - kind: unit
        ref: "tests/tools/test_check_security_register.py#test_g4wr_02_*, test_g4in_01_*"
        status: pass
    human_judgment: false
  - id: D4
    description: "G4IN-02/D58IN-01/D58IN-03 rollback debris reporting and G4IN-03 diagnostic stop after pid-record"
    requirement: "HOST-02"
    verification:
      - kind: unit
        ref: "tests/tools/test_verify_playable.py#test_g4in_02_*, test_d58in_*; tests/libretro/test_retroarch_smoke.py#test_g4in_03_*"
        status: pass
    human_judgment: false
  - id: D5
    description: "Independent in-run diff review (headless claude -p) and transcription of R3/R4 verdicts with round-ordered provenance"
    requirement: "QUAL-03"
    verification:
      - kind: other
        ref: "python3 tools/verify_playable.py --check-docs"
        status: pass
    human_judgment: true
    rationale: "The review verdicts are model judgments; the formal diff-scoped /gsd-code-review and /gsd-verify-work 04 own acceptance."
  - id: D6
    description: "Pinned RetroArch 1.22.2 re-qualified once at cdfbc99bafe7: status pass, retroarch_status pass, frontend_unloaded true, all 17 lanes pass, one sampled instance"
    requirement: "HOST-02"
    verification:
      - kind: e2e
        ref: "python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean --check-docs"
        status: pass
    human_judgment: false

duration: 52min
completed: 2026-10-11
status: complete
---

# Phase 04 Plan 58: G-04-35 gap closure Summary

**Byte-level lane decoding, exact register declarations and a recurring rights `source_revision` check, with an independent in-run review, R3/R4 verdict transcription and a single pinned-RetroArch re-qualification at cdfbc99bafe7.**

## Performance

- **Duration:** 52 min
- **Started:** 2026-10-11T12:38:36Z
- **Completed:** 2026-10-11T13:30:00Z
- **Tasks:** 5 of 5 (pass path; no review-halt or receipt-halt)
- **Files modified:** 16 (tracked, START..HEAD)

## Accomplishments

- G4WR-01/03: the lane pipe is binary; the first segment, drained chunks and new tail are joined and decoded once with replacement and one newline translation, so a detached pipe holder, CRLF during the grace and a split multibyte character are all recorded correctly, and non-UTF-8 output no longer raises.
- G4WR-02/G4IN-01: `threats_open` and `status` must be spelled exactly, only ASCII digits form the integer, and every security-named `*.md` in scope is a candidate in unscoped and `--phase` runs.
- G4WR-04: `rights_revision_errors` (path form, 40 lowercase hex, resolves, ancestor of head, blob digest) runs in `--check-docs` and the `qualification_runner` CTest; the unresolvable `check_fixture.py` revision and the stale rows are corrected, and the definition is in docs/rights-inventory.md.
- G4IN-02/03: rollback reports `.restore`/`.tmp` debris apart from unrestored files; the diagnostic runner skips the second probe after a `pid-record` failure.
- The R3/R4 verdicts are transcribed: 27 rows moved from `open` to `fixed`, `open: 0`, `total: 60`, crosswalk preface 60.
- Pinned RetroArch 1.22.2 re-qualified once; receipt bound and fresh.

## Task Commits

START = `b6977421e5c6a6abc4b8cc749ac1a4ef2fa89bca`.

1. **Task 1 (tracer, G4WR-04)** - RED `409fe9f705f0`, FIX `9a0d02b7c7de`, DOCS `dc3549303b06`.
2. **Task 2 (G4WR-01, G4WR-03, G4IN-02)** - RED `c84609fda108`, FIX `f783c73668b2` (docs in the FIX commit).
3. **Task 3 (G4WR-02, G4IN-01, G4IN-03)** - RED `138a8676471f`, FIX `856592e5ae89` (docs in the FIX commit).
4. **Task 4 (review, repairs, rights, transcription)** - D58 RED `a8705366`, FIX `7501de51` (D58WR-02, D58IN-01), rights refresh `8db07862` (D58WR-01), FIX `1f513e33` (D58IN-03), rights refresh `3ca62dba`, records `53fff627`.
5. **Task 5 (re-qualification, status text)** - STATE start commit `cdfbc99b` (QUALIFIED_REV), receipt `a5624f86`, status text `f128faca`.

**Plan metadata:** this SUMMARY commit follows (`docs(04-58): complete G-04-35 gap-closure plan`).

## Red/green evidence (build/playable-qualification/04-58-evidence.txt)

```
G4WR-04 red 409fe9f705f0 exit 1 green dc3549303b06 ok
G4WR-01 red c84609fda108 exit 1 green f783c73668b2 ok
G4WR-03 red c84609fda108 exit 1 green f783c73668b2 ok
G4IN-02 red c84609fda108 exit 1 green f783c73668b2 ok
G4WR-02 red 138a8676471f exit 1 green 856592e5ae89 ok
G4IN-01 red 138a8676471f exit 1 green 856592e5ae89 ok
G4IN-03 red 138a8676471f exit 1 green 856592e5ae89 ok
```

Each red run was a detached worktree at the RED commit (exit 1, `FAILED (`), then `OK` in the main checkout. The G4WR-04 real-repository test is red at its FIX commit by design and green at the DOCS commit.

## Independent in-run review

- Route (identical lines 1-4 of build/playable-qualification/04-58-diff-review.md, ignored): `Reviewer route: headless claude -p identity claude -p --tools Read,Grep,Glob < 04-58-review-prompt.txt > 04-58-review-raw.txt model unknown` (the runtime had no subagent tool, so the plan's headless route was used). The reviewer had read-only tools and read the diff from an ignored file.
- Block 1: reviewed revision `856592e5ae89c9ec2a56c6651c59ffacc778e836`, prompt sha256 `9d1a2057134c5b6293cf4ee17f686c072f20b27fba590bb66255bcc90fc09b5c`, raw output sha256 `c67908b8c1bc0366345e3582e65b4d33ecc32ea459011afe665851b9de06acca`. Verdicts: `VERDICT G4WR-01..04 FIXED`, `VERDICT G4IN-01..03 FIXED`.
- It raised D58WR-01 (five stale rights digests at HEAD), D58WR-02 (a lane that closed its pipe was never signalled on timeout, and the new ValueError catch hid it), D58IN-01 (rollback replaced an interrupt with a RuntimeError).
- Block 2 (re-check, reviewed revision `8db07862dfda6839e769ca15f5257165a66280ea`, `-2` digests recorded in the file): `VERDICT D58WR-01 FIXED`, `VERDICT D58WR-02 FIXED`, `VERDICT D58IN-01 FIXED`; it raised D58IN-02 and D58IN-03.
- Handling: D58WR-02 and D58IN-01 repaired test-first (`a8705366` then `7501de51`); D58WR-01 repaired by the rights refresh `8db07862` (the public-content gate failed with `rights-digest` before and passed after); D58IN-03 fixed in `1f513e33` (named in its subject) with the follow-up refresh `3ca62dba`. D58IN-02 deferred: a working-tree digest comparison inside `rights_revision_errors` would extend the five-part predicate that the docs define as the whole check; `public_content.validate_repository_inventory` already enforces the digest and the refresh is the final step of each round. It is recorded in the STATE `### Backlog` subsection for the diff-scoped review to re-raise.

## Dispositions and register

- 04-REVIEW-DISPOSITION.md: 27 rows (WR-11, G2CR-01/02, G2WR-01..06, G2IN-01..03, G3WR-01..05, G3IN-01..03, G4WR-01..04, G4IN-01..03) moved `open` to `fixed`; `open: 0`, `total: 60`; crosswalk preface 60. Cited revisions are full 40-hex forms bound by `review_provenance_errors`.
- 04-SECURITY.md stays `status: verified`, `threats_open: 0`; T-04-103 (medium) and T-04-SC (04-58) (low) were added open; no existing row changed (`grep -E '^-\| T-04' 04-58-security.diff` prints nothing).

## Re-qualification record

- QUALIFIED_REV `cdfbc99bafe7a92c87fea9cf9bec6a7f4de1f747`; receipt-bound diff since 09e43f0c4ea0: tests/libretro/retroarch_smoke.py, tests/libretro/test_retroarch_smoke.py, tools/verify_playable.py.
- Pre-flight: clean tracked tree, `validate_repository_inventory()` ok, all 14 test/fix/docs(04-58) commits ancestors, no leftover RetroArch (`pgrep -x RetroArch` exit 1).
- One invocation in the default command sandbox, no escalation: `python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean --check-docs`, exit 0, sampled maximum 1 instance, post-flight `pgrep -x RetroArch` exit 1. Receipt checks: status pass, retroarch_smoke pass, documentation pass, `identity.source_revision` equals QUALIFIED_REV and is newer than the launch marker, executable SHA-256 `ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65`, all 17 lanes pass.
- Bound: `--record-frontend-evidence`, committed as `a5624f86`; non-clean `--check-docs` prints `Phase 04 documentation gate passed.`; freshness (`receipt fresh cdfbc99bafe7`), bound-receipt status (`status` pass, `retroarch_status` pass, `frontend_unloaded` true, every lane pass) and requirement-lane probes pass. Run files: build/playable-qualification/04-58-* (ignored).

## Closeout checks

- Four suites: test_independent_review 70 OK; test_check_security_register 65 OK; test_retroarch_smoke 78 OK; test_verify_playable 125 OK in six consecutive full runs (see Issues Encountered for one earlier unreproduced error).
- `cmake --preset owned-debug && cmake --build --preset owned-debug && ctest --preset owned-debug`: 100% tests passed out of 63 (run before qualification and again after the status commit).
- `check_security_register.py first-playable-game --require-closed --phase 04`: PASS, exit 0. `tools/verify_playable.py --check-docs`: `Phase 04 documentation gate passed.`
- `pgrep -x RetroArch`: exit 1. Public-hygiene scan of the START..HEAD diff: no `/Users/` or `/home/` path.

## Deviations from Plan

**1. [Rule 3 - Blocking] Committed the orchestrator's pending STATE.md change before the qualification pre-flight**
- **Found during:** Task 5 pre-flight (the clean-tracked-tree gate)
- **Issue:** STATE.md carried the orchestrator's uncommitted execution-start edit, which the gate (only `.planning/preparation` excluded) treats as dirty.
- **Fix:** committed it alone (`cdfbc99b`, `docs(04-58): record Phase 04 execution start in STATE`); that commit is QUALIFIED_REV. STATE.md is not receipt-bound.

**2. [Rule 1 - Bug, review-raised] D58WR-02, D58IN-01, D58IN-03 repaired; D58WR-01 repaired by the planned rights refresh**
- **Found during:** Task 4 in-run review. See the review section for commits.

**3. Intentional contract and test-double changes (G4IN-02, G4WR-03)**
- test_g3wr_04_restore_unlink_failure_does_not_abort_rollback now expects `evidence rollback complete; could not remove:` instead of `incomplete` (every file was restored; this is the G4IN-02 contract change).
- Lane-like helpers (`lane_output_after_timeout`, test_g2in_02), the fake `Proc.communicate` in test_no_group_signal_is_sent_after_the_leader_is_reaped and three `Popen` doubles now return bytes, matching the binary lane pipe. `DocumentationCopies` now copies docs/rights-inventory.md so `check_docs(repository=ROOT)` on a copied root can run the rights check.

**4. Source cells of transcribed rows**
- The stale phrases `Pending focused re-review.` and `Not yet repaired.` were replaced by the new clause instead of leaving a self-contradicting cell; the rest of each Source cell is unchanged.

**5. Requirements not marked complete**
- `requirements.mark-complete` was not run: the plan requires the eight rows to keep `Gaps Found` until `/gsd-verify-work 04` passes and phase completion marks them Complete.

**6. Reviewer inputs**
- The reviewer cannot run git, so the START..HEAD diff was supplied as an ignored file named in the prompt; the prompt file records the exact text and its digest.

**Total deviations:** 6 documented (1 blocking, 1 review-driven bug set, 4 judgment/contract notes). **Impact:** no gate, golden or budget was relaxed.

## Issues Encountered

- One full run of tests/tools/test_verify_playable.py during the closeout printed `FAILED (errors=1)`; the output was truncated to its tail and the error was not reproduced. Six subsequent full runs (logs build/playable-qualification/04-58-suite-run-1..6.log) and two ctest runs (which include `qualification_runner`) were all OK. The suite contains lane tests with 2-second timeouts that are timing-sensitive under load; the diff-scoped review should treat this as an unexplained flake, not a closed matter.
- Stale-record reset: `build/playable-qualification/04-58-*` held no files at start, so none were deleted.
- D58IN-02 deferred (see above and the STATE `### Backlog`).

## Known Stubs

None.

## Threat Flags

None. `rights_revision_errors` passes inventory fields to Git, which T-04-103 (added in this plan) covers.

## Next Phase Readiness

Phase 04 is not complete: all 58 plans have summaries except the superseded 04-51, 04-56 and 04-57, but acceptance needs the diff-scoped re-review and re-verification. Next command: `/gsd-code-review 04 --ws first-playable-game` (scoped to START..HEAD of 04-58), then `/gsd-verify-work 04 --ws first-playable-game`.

## Self-Check: PASSED

All 13 key files exist; all recorded commits (`409fe9f7`, `9a0d02b7`, `dc354930`, `c84609fd`, `f783c736`, `138a8676`, `856592e5`, `a8705366`, `7501de51`, `8db07862`, `1f513e33`, `3ca62dba`, `53fff627`, `cdfbc99b`, `a5624f86`, `f128faca`) are ancestors of HEAD; the evaluation-scope resolver lists the 04-58 commits.

---
*Phase: 04-public-playable-tracer*
*Completed: 2026-10-11*
