---
phase: 04-public-playable-tracer
plan: 64
subsystem: qualification-evidence
tags: [retroarch, receipt, history-allowlist, squash-merge, G5WR-01, G5WR-02, G5IN-01]
requires: [04-63]
provides:
  - fresh single-instance pinned RetroArch receipt at the final code revision
  - G5WR-01, G5WR-02, G5IN-01 recorded fixed pending the independent diff-scoped review
  - frozen docs/history-allowlist.json proven by a GEN=0 squash simulation
affects: [04-65]
tech-stack:
  added: []
  patterns: [allowlist generated only by the tool after the last pinned-record change]
key-files:
  modified:
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-FRONTEND-RECEIPT.json
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md
    - docs/first-playable-build.md
    - docs/testing.md
  created:
    - docs/history-allowlist.json
key-decisions:
  - "G5 rows use the controlled state fixed with the mandatory pending-review clause (T-04-108)"
  - "Allowlist frozen once (no re-freeze, no probe defect, no halt)"
requirements-completed: [TRAC-01, TRAC-02, TRAC-03, HOST-02, API-05, SND-01, SND-02, QUAL-03]
status: complete
commits: 4
plan_head_before: ad6981543b34ed40898a7f60f7c69034365b4069
plan_head_after: e8d40032d028ee5b83ddc0e85589d8fc12fb77ea
actuals:
  tokens: 30000
  tasks: 3
  commits: 4
completed: 2026-10-11
---

# Phase 04 Plan 64: Re-qualification, G5 disposition and allowlist freeze Summary

Pinned RetroArch 1.22.2 was re-qualified exactly once at ad6981543b34, the three G5 rows were recorded `fixed` pending the independent review, and the pre-ship history allowlist (141 rows) was frozen and proven on a squash-simulated clone with the committed file. The eight requirement IDs are restored evidence, not new delivery. The `commits: 4` count excludes this SUMMARY commit.

## Outcome

Complete on the pass path. No halt marker (`04-63-branch.txt` absent), no probe-defect marker (`04-64-probe-defect.txt` absent), no re-freeze.

## Pre-flight

`git status --porcelain --untracked-files=all` (excluding `.planning/preparation`) printed nothing, so there were no orchestrator edits to commit and no pre-flight commit. RUN_START `ad6981543b34ed40898a7f60f7c69034365b4069` is in `04-64-start-rev.txt`. Step 0 stale reset found nothing to delete. Receipt-bound diff since 4e6a40e66e9e: `tools/verify_playable.py` only. Every `fix(04-59)`..`fix(04-61)` and `fix(04-63)` commit is an ancestor of the qualified revision.

## Receipt (Task 1)

- QUALIFIED_REV `ad6981543b34ed40898a7f60f7c69034365b4069`; one invocation (`--retroarch /Applications/RetroArch.app --clean --check-docs`), runner exit 0, sampled max instances 1, `pgrep -x RetroArch` exit 1 before and after.
- Receipt: `status` pass, `retroarch_status` pass, `frontend_unloaded` true, 17 lanes all pass, executable SHA-256 `ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65`.
- Commit `8880413 test(04-64): re-qualify pinned RetroArch at ad6981543b34`; non-clean `--check-docs`, freshness (`receipt fresh ad6981543b34 single instance`), status and lane probes passed. No code or test path changed after the receipt.

## Requirement-to-lane map (receipt at ad6981543b34, all lanes pass)

| Requirement | Evidencing lanes and fields |
|-------------|-----------------------------|
| TRAC-01 | `fixture_sha256` 59ed3645b156..., `full-sdk-ctest` pass |
| TRAC-02 | `full-sdk-ctest` pass, `observations` (core and content launched, bounded screenshots, no-input screenshots stable) |
| TRAC-03 | `marker_before` [16,16,1], `marker_after_right` [47,16,1], `input_mapping` (RetroPad RIGHT from Right Arrow; LEFT control from Left Arrow), `full-sdk-ctest` pass |
| HOST-02 | `actual-retroarch-smoke` pass, `frontend_unloaded` true, `retroarch.executable_sha256` pinned, sampled max instances 1 |
| API-05 | `full-sdk-ctest`, `consumer-static-{configure,build,check}`, `consumer-shared-{configure,build,check}` all pass |
| SND-01 | `z80-source` pass |
| SND-02 | `ym2610-source`, `ym2610-installed-linkages` pass |
| QUAL-03 | `static-{configure,build,install}`, `shared-{configure,build,install}` pass; squashed-clone suite (156 tests) passes |

The map shows which lane evidences each requirement; it adds no claim beyond the lanes. Edge semantics remain the flagged assumptions listed in the plan.

## Disposition (Task 2)

- RIGHTS-REFRESH changed nothing (no stale row); `validate_repository_inventory` prints `inventory ok`.
- Commit `90d522b docs(04-64): record G5 fixes as fixed pending the diff-scoped review`: G5WR-01, G5WR-02 and G5IN-01 are `fixed` in the frontmatter, table and 04-VALIDATION.md crosswalk. Each Source keeps `Reported by 04-REVIEW-GAPS-R5.md (d21f71d).` and carries `Fix landed; independent verdict pending the diff-scoped /gsd-code-review, which confirms or reopens this row` with backticked 40-hex revisions (G5WR-01: 37e9f0f6, 1a208248, 9dc602c3, 26667557, 02fe1c80, d5f32933, 027e4177; G5WR-02 and G5IN-01: 591d0f79). `open: 0`, `total: 63`, crosswalk preface `(63 current disposition records)`.
- Commit `1d9e77f docs(04-64): describe the frozen pre-ship history allowlist` rewrites the `Plan 04-62 leaves` sentence in docs/testing.md.

## Freeze and simulation

- Freeze commit `e8d40032d028ee5b83ddc0e85589d8fc12fb77ea` (`docs(04-64): freeze Phase 04 pre-ship history allowlist`, docs/history-allowlist.json only, 141 rows); SHA in `04-63-freeze-rev.txt`.
- `--history-allowlist check`: `History allowlist is current (141 rows).` at the freeze and again at plan end; branch `--check-docs` prints no `unverifiable-history:` line.
- SQUASH-SIM GEN=0 at the freeze: `final squash simulation ok 141 tolerated of 141 rows; clone suite ran 156`; SUITE-CHECK `squash suite ok 0 causally verified environmental: []` (suite `OK (skipped=1)`, the recorded full-history-only sibling skip from 04-63); no environmental entries.
- REHEARSAL: `full-history rehearsal ok` (`--check-docs` passes with no tolerated-row line; suite 156 tests OK). LATER-BRANCH: `later branch ok` (unlisted row fails with exactly `rights source_revision <12> for tests/later_probe.txt does not resolve`; clone back on clean `sim-main`).
- `refreeze bound ok` (1 freeze, 0 reverted). No post-freeze failure of class (a), (b) or (c).

## Closeout (Task 3)

`--check-docs` passes; no file changed after the freeze before this SUMMARY; hygiene scan of `04-63-start-rev.txt`..HEAD clean; `lane map names match receipt lanes`; `pgrep -x RetroArch` exits 1.

## Deviations from Plan

None - plan executed exactly as written. The `.planning/preparation` working-tree changes were left untouched.

## Next

Phase 04 is not complete. Next plan is 04-65 (register rows T-04-107..T-04-109, status text): `/gsd-execute-phase 04 --ws first-playable-game`, then `/gsd-code-review 04 --ws first-playable-game` and `/gsd-verify-work 04 --ws first-playable-game`.
