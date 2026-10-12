---
phase: 04-public-playable-tracer
plan: 52
subsystem: testing
tags: [snapshot-integrity, qualification, red-green-evidence, security-register]
requires:
  - phase: 04-public-playable-tracer
    provides: 04-49 round-4 evidence; debug resolution of the 04-50 receipt-halt (f72e513)
provides:
  - verify_snapshot directory-set guard (snapshot-inventory-mismatch, path-free detail)
  - docs/testing.md Snapshot integrity contract
  - Refreshed rights row for tests/tools/test_verify_playable.py
  - 04-SECURITY.md round-4 continuation evidence with open T-04-SC (04-52..04-54) rows
affects: [04-53, 04-54, secure-phase]
status: complete
actuals:
  tokens: 14000
  tasks: 3
  commits: 5
plan_head_before: 4ffd4b5e547311180db0dd06da6c161b0f395935
plan_head_after: e3dbe3a80666910819aa842a8edd04bf57f45e36
tech-stack:
  added: []
  patterns: [directory-set comparison alongside file inventory, detached-worktree red re-proof]
key-files:
  created: []
  modified:
    - tools/verify_playable.py
    - tests/tools/test_verify_playable.py
    - docs/testing.md
    - docs/rights-inventory.md
    - .planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-SECURITY.md
key-decisions:
  - "Directory-set guard lives in verify_snapshot only and reuses the snapshot-inventory-mismatch reason with a distinct fixed, path-free detail; inventory rows, digest, record and schema are unchanged."
  - "All register rows stay open; evidence recorded only (T-04-48)."
requirements-completed: [QUAL-03]
---

# Phase 4 Plan 52: Snapshot directory-set guard Summary

`verify_snapshot` now also compares the materialized real-directory set with the parent directories of the recorded rows, so a lane that adds an empty directory (for example `build/playable-qualification`) fails at its own lane check with `snapshot-inventory-mismatch` and the detail `materialized source directory set changed after archive creation`.

## Commits

- RED `c8e952aeabd0762858f1c67aab82a035fd2e1026` test(04-52): snapshot verification must detect added empty directories
- FIX `08c35aa9c6d1ca60ccce7b1eecfaa0183d506c40` fix(04-52): fail snapshot verification on an added directory
- `6437598` docs(04-52): document the snapshot directory-set check
- `f4e7e22` docs(04-52): refresh rights inventory for the snapshot directory test
- `e3dbe3a` docs(04-52): record the 04-50 debug resolution and snapshot directory guard evidence (rows open pending audit)

## Evidence

- Red re-proof (detached worktree at RED, removed afterwards): `SNAPSHOT-DIR red c8e952aeabd0 exit 1 failures 2 errors 0 green 08c35aa9c6d1 ok`.
- Real-HEAD probe (no RetroArch launch) printed `snapshot directory guard ok`.
- Full `python3 tests/tools/test_verify_playable.py`: 105 tests, `OK`. The control test (directory symlink) passes at both commits.
- Rights row refreshed: `tests/tools/test_verify_playable.py` only (sha256 `009d8f9c...`, source_revision FIX). `validate_repository_inventory()` ok; `test_repository_inventory_matches` OK.
- `threats_open`: 15 (checker-computed, equals the planning-time prediction). `check_security_register.py first-playable-game` exit 0; `--require-closed --phase 04` exit 1 (`FAIL: 04-SECURITY.md: 15 blocking open threats`), the expected pre-audit state. `--check-docs` printed `Phase 04 documentation gate passed.`
- Register diff changed only T-04-SC (04-50) and (04-51) Mitigation cells among existing rows; no Status, Severity or Disposition changed. The debug session's untracked 2ac2097 receipt is not cited.

## Deviations from Plan

None - plan executed exactly as written. Note: the plan commit ledger was written after the first (RED) commit using its parent (`4ffd4b5`), which is the true pre-plan HEAD, so `commits: 5` is accurate.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

All five commits are ancestors of HEAD; modified files exist; ignored evidence files are present in build/playable-qualification/.
