---
phase: 04-public-playable-tracer
plan: 36
subsystem: qualification-and-review
tags: [retroarch, independent-review, security-register, traceability, residual-branch]
requires: [04-35]
provides:
  - RetroArch re-qualification at 323fa1453329 (receipt-bound tools changed since 04-34)
  - contained focused re-review of 73 IDs transcribed into register, dispositions and crosswalk
  - reconciled SECURITY, VALIDATION, REQUIREMENTS, ROADMAP and STATE on the residual branch
affects: [04 gap planning]
key-files:
  modified:
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-FRONTEND-RECEIPT.json
    - docs/first-playable-build.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md
    - .planning/workstreams/first-playable-game/REQUIREMENTS.md
    - .planning/workstreams/first-playable-game/ROADMAP.md
    - .planning/workstreams/first-playable-game/STATE.md
key-decisions:
  - "Residual branch: CLOSURE exit 1; REQUIREMENTS keep Gaps Found with acceptance pending the Phase 04 security closure"
  - "D-GAP-02 rows T-04-52/55/60 stay accepted; their CLOSED verdicts are evidence only"
requirements-completed: []  # TRAC-01/02/03, HOST-02, API-05, SND-01/02, QUAL-03 stay Gaps Found: acceptance pending Phase 04 security closure
status: complete
commits: 3
plan_head_before: 323fa14533299144cac976b263629292809b86f3
plan_head_after: 5248cef16baad64605b053b7e668966bd4c523b6
actuals:
  tokens: 60000
  tasks: 2
  commits: 3
duration: 35min
completed: 2026-10-10
---

# Phase 04 Plan 36: Focused re-review and closure reconciliation Summary

Pinned RetroArch was re-qualified at 323fa1453329, a contained 73-ID focused review confirmed all 04-35 repairs except five IDs it still judges open, and Phase 04 lands on the residual branch (CLOSURE exit 1, threats_open 2).

## Branch

**residual.** No halt: `04-34-branch.txt`, `04-35-branch.txt` and `04-36-branch.txt` are absent, no `REVIEW HALTED:` line, the stream gate printed `contained`. `--require-closed --phase 04` exits 1 and four register rows plus one finding are open. Next command (in STATE): `/gsd-plan-phase 04 --gaps --ws first-playable-game`.

## Task 1: Re-qualification (commit d36b22c) and focused review (commit 977c855)

- CHANGED since the 04-34 qualified revision (45952598202a), excluding `.planning`: docs/first-playable-build.md, docs/rights-inventory.md, docs/testing.md, tests/tools/{check_runtime_storage,check_security_register,test_check_runtime_storage,test_check_security_register,test_independent_review,test_private_paths,test_verify_playable}.py, tools/{independent_review,private_paths,verify_playable}.py. **CHANGED intersect RECEIPT_BOUND** = `tools/verify_playable.py`, `tools/private_paths.py`, so re-qualification ran.
- QUALIFIED_REV = REVIEWED_REV = `323fa1453329`. `--clean --check-docs` passed all lanes; receipt `status` and `retroarch_smoke` pass, `documentation` pass, source revision equals the revision, executable SHA-256 `ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65`. `pgrep -x RetroArch` exit 1 before and after; 1-second sampled maximum 1. Default command sandbox; no escalation requested or needed. The executor issued no GUI action.
- `--record-frontend-evidence` regenerated the receipt summary, guide block and 04-15 T2 row; committed (three files); post-commit non-clean `--check-docs` printed `Phase 04 documentation gate passed.` `grep -c "Complete at ..."` gave 1; private-path grep on the receipt gave 0.
- **SCOPE = 73 IDs** (44 threats, 29 findings): 11 residual (T-04-11, 15, 18, 20, 56, 61, 62, 65, 67, WR-08, WR-11, each with its 04-35 repair stated), 60 FRESH, and T-04-SC (04-35) and (04-36). FRESH was computed mechanically from the cited-source rule: 32 threats and 28 findings. Most are fail-closed (the ID cites no file, so any change makes it FRESH); the ones with a matching changed file include T-04-34 (tests/tools/test_verify_playable.py), T-04-48 and CR-06, WR-07 (check_security_register.py), T-04-60 and T-04-64 (docs/testing.md), CR-01 and WR-06 (tools/private_paths.py), CR-02, CR-03, CR-05, CR-08, CR-09, WR-01, WR-02, WR-03, WR-09 (tools/verify_playable.py), CR-04 and IN-01 (docs/first-playable-build.md) and IN-04 (three changed test files). T-04-44 was not FRESH and was not re-judged.
- Review: Claude Code 2.1.296; init tools Glob, Grep, Read; model claude-opus-5-5; cwd scratch directory (redacted), matched the scratch path; `permission_denials: []`; tool calls Read 18, Grep 21, Glob 2. `preflight` printed `scratch-ok`; `gate` printed `contained`. Scratch directory removed afterwards.
- Verdicts: 40 threats CLOSED and 4 OPEN; 28 findings FIXED and 1 OPEN. `independent_review.py check`: `transcribed 73 ids (contained)`.
- OPEN at 323fa1453329 (not repaired here; this plan changes no code):
  - T-04-11 (high): `tools/verify_playable.py:1513-1531` builds the receipt outside any try block, so `sha256(fixture_shared)` and `_artifact_tree` errors can escape as a raw traceback.
  - T-04-61 (high): `tools/independent_review.py:94-105` `glob_contained` misses a brace alternative such as `{/etc/*,x}`.
  - T-04-38 (medium): `tools/verify_playable.py` does not parse or validate the `reviewed_revision` record or `covered_digest` freshness.
  - T-04-67 (medium) and WR-11: `tools/verify_playable.py:1059-1074` rejects duplicate frontmatter keys but not a malformed sole review revision value (the SIGKILL part of T-04-67 is fixed).
- Closed by this review: T-04-15, T-04-18, T-04-20, T-04-56, T-04-62, T-04-65 and all earlier-open fresh rows except those above; WR-08 FIXED therefore `deferred` with its documented residual (CMakeLists.txt, docs/testing.md); GIN-01 and GIN-04 stay `deferred`.
- D-GAP-02 rows in scope (T-04-52, 55, 60): verdicts CLOSED, recorded as evidence only, status `accepted`. Neither they nor T-04-44 appear in `04-34-residual-ids.txt` or `04-35-repairs.txt`.

## Task 2: Gates and reconciliation (commit 5248cef)

- `cmake --preset owned-debug && cmake --build --preset owned-debug && ctest --preset owned-debug`: 63/63 passed (35.40 s real).
- Focused suites, all OK: test_verify_playable 73, test_private_paths 32, test_independent_review 59, test_check_security_register 21, test_check_runtime_storage 15, test_check_package 5, retroarch smoke 68, test_public_content 17. `validate_repository_inventory()` passed, 46 items.
- `check_security_register.py first-playable-game`: PASS (blocking open 04-SECURITY.md=2, 05-SECURITY.md=9). `--check-docs`: `Phase 04 documentation gate passed.`
- **CLOSURE** (`--require-closed --phase 04`) = 1: 2 blocking open threats in 04-SECURITY.md (T-04-11, T-04-61). **UNSCOPED** (`--require-closed`) = 1: 2 attributed to 04-SECURITY.md plus 9 to the Phase 05 draft register 05-SECURITY.md, which is outside Phase 04 closure and was not edited.
- 04-SECURITY.md: threats_open 2 (status open), 101 rows, 4 open (97 closed or accepted); 04-REVIEW-DISPOSITION.md: 30 fixed, 3 deferred, 1 open; Sign-Off left unticked with the branch stated in the Approval line. 04-VALIDATION.md: focused-suites row, E1-E6 statuses and a dated note updated (E1 keeps `open implementation defect` because T-04-11 stays open).
- REQUIREMENTS.md: the eight Phase 04 rows keep `Gaps Found`; Status line and Traceability paragraph say they are implemented and evidenced but acceptance is pending the Phase 04 security closure (threats_open 2). ROADMAP: Status line, Plans line, checklist, Phase 5 Depends on and Execution Order restated; Progress row 4 reads `36/36`, status stays `In Progress`. STATE: single `Phase 04:` clause naming `/gsd-plan-phase 04 --gaps --ws first-playable-game`, new Blockers line, D-GAP-02 and 04-36 decision entries.
- 04-35 unrepaired IDs: none; `04-33-writable-findings.txt` is empty, so no writable runtime symbol is routed. The five IDs above are new open items from this review, routed to gap planning with their paths: tools/verify_playable.py (T-04-11, T-04-38, T-04-67, WR-11) and tools/independent_review.py (T-04-61). None is a user decision or human checkpoint (D-GAP-02).
- Forbidden-file check: no 04-VERIFICATION.md, 04-UAT.md, 04-REVIEW.md, 04-REVIEW-GAPS.md or `phases/05-` file changed since the 04-35 start revision. `pgrep -x RetroArch` exits 1.

## Deviations from Plan

**1. [Rule 1 - Bug] Plan verify passed T-04-44 to `--maintainer-accepted`.** `independent_review.py check` refuses an accepted ID that is not a review ID ("T-04-44 is not a review ID"). T-04-44 cites no changed file and is not residual, so it is correctly outside SCOPE. I ran `check` with `--maintainer-accepted T-04-52,T-04-55,T-04-60` (the accepted IDs actually in scope). No gate was relaxed.

**2. [Rule 1 - Bug] Plan verify asserts lowercase `never use` in the system prompt.** The verdict-only system prompt (copied from 04-34) says "Never use `..` ..." and "relative to the scratch root", so the case-sensitive substring `never use` is absent although the rule is stated. The file was not altered after the run (it is the exact text the reviewer received); the same two substrings were checked case-insensitively. Review scope, FRESH recomputation and `Review IDs:` equality were verified with the plan's own logic (scope 73, fresh 60, set equal).

**3. [Rule 3 - Blocking] `check` requires the scratch directory to exist.** As in 04-34, an empty directory was recreated at the recorded path for the check and removed again. No tracked change.

**4. Minor.** D-GAP-01 already had a Decisions entry; only the D-GAP-02 and a 04-36 outcome entry were appended. SND prose in REQUIREMENTS line 48 ("two completed sound requirements") was reworded to match the Gaps Found table.

**Total deviations:** 3 auto-fixed (2 plan-verify bugs, 1 blocking), 1 minor note. **Impact:** none on evidence or on any status.

## Known Stubs

None.

## Threat Flags

None. No new network, auth or file-access surface; no code changed.

## Next Phase Readiness

Phase 04 is not accepted. The plan is complete (36/36) but the phase is not: run `/gsd-plan-phase 04 --gaps --ws first-playable-game` for T-04-11, T-04-38, T-04-61, T-04-67 and WR-11 (paths above), then re-run the focused review and `/gsd-verify-work 04 --ws first-playable-game`. Intermediate fix commits fail the CI rights gate by design; evaluate the PR at its head.

## Self-Check: PASSED

Commits d36b22c, 977c855 and 5248cef are ancestors of HEAD; the edited files exist; the register checker, `--check-docs` and the Task 2 reconciliation check pass; `pgrep -x RetroArch` exits 1; no machine-local absolute path in the SUMMARY or 04-SECURITY.md.
