# Phase 05 hosted MVS qualification

Status: **the exact public-safe PR #2 candidate passed hosted MVS qualification; G-05-5 is resolved for that candidate.** PR #2 remains unmerged pending its required approving review. Selected-game attract/start and actual selected-media RetroArch behavior remain open/unknown.

The initial local-candidate record below is historical Plan 05-05 evidence and
is superseded for G-05-5 by the Plan 05-06 exact-SHA qualification at the end of
this file. It describes an earlier candidate, not PR #2.

## Candidate history and scope

- Public base: `main` at `4b2120d57f486ef7561409ff80db109b7494ae5d`, fetched from
  the configured public origin.
- Isolated candidate branch: `agent-phase05-safe-candidate`.
- Candidate head: `288a9d381900719995a0d95dc424f59a5720b2bd`.
- Candidate history contains two commits authored as `szTheory
  <szTheory@users.noreply.github.com>`: one source transplant from the current
  Phase 05 tree and one required public version manifest. It does not contain
  the local planning history, the private verification receipt, or the local
  evidence directory.
- The outgoing candidate was not pushed and no PR was opened. Public-history
  and source review remained incomplete because the required local route checks
  failed.

## Local route rehearsal

- `python3 tests/sdk/test_matrix_evidence.py` passed on the candidate.
- `python3 tools/verify_sdk.py --suite matrix --output build/sdk-debug/verify-sdk/phase05-public-candidate.json`
  failed before the MVS lane with `manifest source identity mismatch:
  tests/sdk/ORACLE.md`. The diagnostic fixture manifest still pins the earlier
  oracle document bytes; the current document was changed in commit `6dee725`
  during Plan 05-03. The source identity cannot be refreshed as a routine
  qualification fix because that oracle update changed timing claims and needs
  its own reviewed reconciliation with the fixture expectations. No golden was
  updated.
- `python3 tools/public_content.py --root . --history-revision HEAD --json
  build/verify-sdk/public-candidate-content.json` failed with
  `rights-path-set`. The candidate's rights inventory lacks affirmative rows
  for these 13 test paths:

  - `tests/chips/Z80-ADMISSION.md`
  - `tests/chips/check_ym2610.py`
  - `tests/chips/check_z80_source.py`
  - `tests/chips/test_ym2610.c`
  - `tests/chips/test_z80.c`
  - `tests/consumers/test_playable_install.py`
  - `tests/libretro/test_retroarch_smoke.py`
  - `tests/mvs/fuzz_import.c`
  - `tests/mvs/test_mvs.c`
  - `tests/mvs/test_mvs_qualification.py`
  - `tests/tools/check_phase04_validation_map.py`
  - `tests/tools/test_check_phase04_validation_map.py`
  - `tests/tools/test_verify_playable.py`

The receipt download and checker were not run. There is no eligible run ID,
downloaded artifact set, hosted runner identity, hosted denominator, or passing
aggregate to record. Local rehearsal evidence does not close G-05-5.

## Required resolution

Reconcile the changed diagnostic oracle document with the frozen fixture
manifest without altering expected outputs merely to pass, and complete the
rights/provenance rows for the listed original test files. Then rerun the
candidate's local matrix and public-content scan, review the full outgoing
history and content, and only then publish a final candidate PR for hosted CI.
Phase 04 findings remain open and unchanged.

## Plan 05-06 exact-SHA hosted qualification — 2026-10-09

- Public-safe candidate PR: #2, exact head
  `e80672845fc60d94d8a44eab416377534c9a99f1`.
- Eligible event: `pull_request`; hosted run `38001400110` completed with
  `success` for the exact PR head. The required CI workflow reports passing
  classify, all six matrix lanes, public-content, and `ci-policy` jobs.
- The current candidate's verifier accepted artifacts downloaded from that
  same run: event metadata, MVS lane receipt, canonical seven-test MVS output,
  and the sealed aggregate. Source revision and relevant-source digest matched
  the candidate; positive CTest denominator, all seven expected test names,
  and output-byte digest matched. The aggregate independently passed its
  current-SHA, required-job, six-lane, and public-content checks.
- Independent candidate review passed the exact SHA. The public-content scan
  found zero findings, and the complete local SDK matrix passed. Local checks
  are recorded separately from this hosted result.
- `main` protection requires one approving PR review. PR #2 reports
  `REVIEW_REQUIRED` and `BLOCKED`; it remains open and unmerged. No hosted
  receipt from an earlier candidate SHA is reused.
- The MVS receipt establishes the hosted CTest and source/aggregate gates only.
  Task 2 could not establish an independently observed selected configuration
  or sourced guest-written attract/start predicate; no selected-media run was
  performed. Actual selected-media RetroArch behavior remains
  unknown/manual-only. G-05-3 and the Phase 05 selected-game requirements
  remain open.
