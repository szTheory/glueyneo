---
phase: 04-public-playable-tracer
plan: 34
subsystem: qualification-and-review
tags: [retroarch, independent-review, security-register, containment]
requires: [04-33]
provides:
  - fresh clean-snapshot RetroArch receipt at the post-04-33 revision
  - contained independent review of 77 IDs transcribed into register, dispositions and crosswalk
affects: [04-35, 04-36]
key-files:
  modified:
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-FRONTEND-RECEIPT.json
    - docs/first-playable-build.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW-DISPOSITION.md
key-decisions:
  - "D-GAP-01 boundary applied by tools/independent_review.py; review contained"
  - "D-GAP-02: T-04-44/52/55/60 recorded accepted; verdicts (all CLOSED) are evidence only"
requirements-completed: [TRAC-01, TRAC-02, TRAC-03, HOST-02, API-05, SND-01, SND-02, QUAL-03]
status: complete
commits: 2
plan_head_before: 45952598202aa22dfaec0ca6291552e7a6f4720d
plan_head_after: 8e443e85972987e03b5362e938102a62e8fd212f
actuals:
  tokens: 60000
  tasks: 2
  commits: 2
---

# Phase 04 Plan 34: Re-qualification and contained independent review Summary

A clean pinned-RetroArch qualification passed at the post-04-33 revision, and a mechanically contained 77-ID review left 9 threats (6 high) and 2 findings open for 04-35.

Note: `requirements-completed` copies the plan's requirement list verbatim; per orchestrator instruction REQUIREMENTS.md was not edited and 04-36 owns final requirement status.

## Task 1: Re-qualification (commit 4971f42)

- QUALIFIED_REV: `45952598202a` (post-04-33; its `docs(04-33)` rights-inventory commit is an ancestor).
- `--clean --check-docs` passed every lane; `retroarch_smoke` pass. Executable SHA-256 `ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65`.
- `pgrep -x RetroArch`: exit 1 before and after; 1-second sampled maximum 1. Default command sandbox, no escalation requested.
- `--record-frontend-evidence` regenerated the receipt summary, guide block and 04-15 T2 row; committed (three files only); post-commit non-clean `--check-docs` printed `Phase 04 documentation gate passed.`
- `grep -c "Complete at ..."` gave 1; private-path grep on the receipt gave 0.

## Task 2: Contained review (commit 8e443e8)

- Claude Code 2.1.296; init tools Glob, Grep, Read; model claude-opus-5-5; cwd scratch directory (redacted), `cwd_matches_scratch: true`; `permission_denials: []`; tool calls Read 16, Grep 16, Glob 2. `preflight` printed `scratch-ok`; `gate` printed `contained`. No sandbox escalation.
- Branch file absent (review completed). Scratch directory removed.
- Verdicts: 34 CLOSED, 32 FIXED, 11 OPEN. Check output: `transcribed 77 ids (contained)`; scope check `scope 77 ok` with counts (33, 10, 24, 10, 77).
- Open threats: T-04-11, T-04-15, T-04-18, T-04-20 (NFD/NFC root forms in `tools/private_paths.py`), T-04-56 (Mach-O `private external`/`weak external`/common lines in `tests/tools/check_runtime_storage.py`), T-04-61 (tilde expansion in `tools/independent_review.py`), T-04-62 (register header variants in `tests/tools/check_security_register.py`), T-04-65 (unscanned traceback/usage in `tools/independent_review.py`), T-04-67 (`_recorded_listed` fail-open in `tools/verify_playable.py`).
- Open findings: WR-08 (same Mach-O gap), WR-11 (no duplicate-revision-key rejection). GIN-01 and GIN-04 are `deferred` with residuals accepted. threats_open = 6 (high); `check_security_register.py first-playable-game` passes; `--require-closed --phase 04` exit code 1.
- D-GAP-02: T-04-44/52/55/60 recorded `accepted`; all four verdicts CLOSED, so none enters the residual file.
- Residual IDs (04-34-residual-ids.txt, ignored): T-04-11, T-04-15, T-04-18, T-04-20, T-04-56, T-04-61, T-04-62, T-04-65, T-04-67, WR-08, WR-11.
- Disposition `total: 34`, `open: 2`; crosswalk equals dispositions (docs gate passes).

## Deviations from Plan

**[Rule 3 - Blocking] `independent_review.py check` requires the scratch directory to exist.** The plan removes the scratch directory yet verify runs `check`. A temporary empty directory at the recorded path was created for the check and removed again; the stream gate verdict was computed earlier against the real extraction. No tracked change.

Otherwise none. Intermediate fix commits fail the CI rights gate by design; the PR must be evaluated at its head (or squash-merged).

## Known Stubs

None.

## Self-Check: PASSED

Commits 4971f42 and 8e443e8 are ancestors of HEAD; edited files exist; `pgrep -x RetroArch` exits 1.
