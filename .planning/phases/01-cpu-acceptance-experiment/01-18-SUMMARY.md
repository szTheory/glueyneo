---
phase: 01-cpu-acceptance-experiment
plan: "18"
subsystem: cpu
tags: [c17, candidate-capability, contract-amendment, tdd]
requires:
  - phase: "01-17"
    provides: Preserved ambiguous original-MC68000 saved-PC evidence
provides:
  - Exact 0x4AFC unsupported result before exception side effects
  - Validated additive P01-C-14 candidate contract with immutable historical root
affects: [01-19, 01-20, 01-21]
tech-stack:
  added: []
  patterns: [exact opcode rejection, pinned canonical amendment identity]
key-files:
  created: []
  modified:
    - experiments/owned_cpu/cpu.c
    - experiments/owned_cpu/cpu.h
    - experiments/owned_cpu/SUBSET.md
    - tests/owned_cpu/ORACLE.md
    - tests/owned_cpu/test_timing.c
    - experiments/owned_cpu/illegal-reconciliation.json
    - tools/owned_cpu/contract.py
    - tests/owned_cpu/test_contract.py
    - experiments/owned_cpu/budget-ledger.json
    - .planning/ROADMAP.md
key-decisions:
  - "Applied P01-C-14 only to candidate capability; P01-C-13 hardware saved PC remains unknown."
  - "Active scope is the immutable frozen CONTRACT plus one exact authorized amendment, pinned by canonical SHA-256."
requirements-completed: []
actuals:
  tokens: 11235
  tasks: 2
  commits: 4
plan_head_before: f991a7aaa64674052d8975ef51882107aaa478d9
plan_head_after: 06d700108a2fb910779db7b1669734ebfe9d1483
coverage:
  - id: D1
    description: Exact canonical unsupported boundary with opcode-only callback and zero dispatch/cycle changes
    verification:
      - kind: integration
        ref: "ctest --preset owned-debug -R '^owned_cpu_timing$' --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D2
    description: Active amendment identity and frozen-root/history/tamper controls
    verification:
      - kind: unit
        ref: "python3 -m unittest discover -s tests/owned_cpu -p test_contract.py"
        status: pass
      - kind: unit
        ref: "python3 -O -m unittest discover -s tests/owned_cpu -p test_contract.py"
        status: pass
    human_judgment: false
duration: 13min
completed: 2026-10-03
status: complete
---

# Phase 01 Plan 18: Exact canonical candidate rejection Summary

**Exact 0x4AFC now returns unsupported after its opcode fetch, with no guest exception entry; one additive P01-C-14 amendment binds that candidate scope while preserving the unknown silicon saved PC.**

## Accomplishments

The private C17 runtime reports `OWNED_CPU_UNSUPPORTED_OPCODE`, logical opcode PC/fault PC and fetched IR before any vector-4 read, exception preflight or frame write. Successful rejection commits zero elapsed cycles, overshoot or instructions. Direct tests preserve every observed register, SR, stack bank, previous PC, vector marker, event counter and guest-memory byte, including repeat rejection with failing vector/stack callbacks and an odd exception stack. Earlier reset40, IRQ44 and NOP4 events retain their own charges. Opcode fetch failure remains terminal host fault; the existing odd-fetch address-error and selected exception tests remain active.

The header's private same-build identity was refreshed from the full changed `cpu.c`. SUBSET and ORACLE distinguish candidate rejection from original MC68000 encoding/vector behavior and unknown saved-PC selection. Historical ILLEGAL continuation evidence is explicitly superseded; fresh semantic, continuation, inventory and whole-candidate qualification remain downstream work.

The original CONTRACT root remains `6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`. Strict base64 archive decoding equals that root and current original bytes, independently of amendment content. Every pre-existing reconciliation value, source record, unresolved disposition and null selected PC remains unchanged. A single ordered amendment identifies P01-C-14/D1-14 and its authorization date, exact superseded ILLEGAL row and conflicting references, only numeric opcode 19196, exact unsupported policy and retained operations/limits.

Canonical JSON uses sorted keys, compact separators, ASCII escapes and UTF-8 SHA-256. Active identity is the digest excluding identity and content-digest fields; content digest excludes only itself. Both are pinned to the approved exact content, so recomputing a digest cannot authorize altered scope. Amendment content SHA-256 is `3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad`; active identity is `27af8df79b55f83bffdef63981defc23984fff6b4e0002d10e99621310340419`. Validation reports baseline plus amendment, retaining legacy markers, history hashes, budget and pending admission checks.

## Task Commits

1. Task 1 RED — `877c5f7`: specify exact canonical unsupported boundary.
2. Task 1 GREEN — `0bbcbf7`: reject exact 4AFC without guest exception effects.
3. Task 2 RED — `67393f2`: require additive active candidate amendment.
4. Task 2 GREEN — `06d7001`: validate exact additive candidate contract amendment and append effort.

Measured `git rev-list` count is four between the persisted before/after revisions above. Token actuals are 44,938 realized task-diff characters divided by four, rounded up; they exclude this later summary and session metadata. No refactor was needed.

## Verification

- `cmake --preset owned-debug` and the `owned_cpu_timing` target build pass without dependency or strict-C17 changes.
- The exact planned timing CTest selection passes 1/1 target, with 25/25 Unity cases. The tracer gate repeated configure/build/CTest and passed before expansion.
- `--mutate-unsupported` runs only `canonical_unsupported_wrong_status_expectation`: exit 1, one case, one failure, exactly `canonical unsupported result-status assertion` (expected old status 8, actual unsupported status 6). This is an expected negative-control outcome, not a normal test failure.
- Contract unittest discovery passes 23/23 in normal Python and 23/23 under `python3 -O`. Controls cover missing/empty/duplicate/reordered/malformed chains, altered authorization/root/archive/digest/identity, broad or nonnumeric exclusion, old success status, changed rules/retained cases with recomputed hashes, hardware-PC selection, reconciliation-history changes, frozen caps/history and original marker/root behavior.
- `contract.py validate` and `contract.py budget` pass. Output retains all five CPU requirements Pending, 24 frozen markers, ten Musashi-history hashes, Phase 02 gated and no budget pause.
- Baseline comparisons pass for all original 21 ledger entries, every non-entry ledger field, every pre-existing reconciliation value, CONTRACT bytes, and Plan 01-17 evidence/adjudication/summary/plan bytes. Baseline revision is `f991a7aaa64674052d8975ef51882107aaa478d9`.

## TDD Gate Compliance

Task 1's pre-implementation timing run produced 25 cases with two intended assertions failing: opcode-only rejection received host-fault status 7 through old exception dispatch, and combined reset/rejection received budget status 8. The target `canonical_unsupported_has_only_opcode_fetch` expected unsupported status 6. Raw Unity case records were normalized to testcase XML without changing verdicts; installed `check tdd-red-evidence` returned `RED_EVIDENCE_OK`, `target_test_failed`, before RED commit and implementation.

Task 2's isolated direct amendment-presence assertion failed with one test, one assertion failure and zero load/fixture errors before the amendment was added. The installed evidence gate returned `RED_EVIDENCE_OK` before its RED commit and implementation. An initial full-suite probe had pre-existing roadmap pending-gate errors; those errors were not used as RED evidence. Both tasks have committed RED then GREEN and current passing evidence.

## Accounting

The existing recorder appended one `plan-01-18-runtime-amendment` entry, preserving the 21-entry prefix and all frozen fields, caps, diagnostic gate and Musashi accounting. Charge: 859 seconds, comprising a measured 559-second active interval including intentional RED and failed gate checks, a labeled conservative 180-second initial-context allowance and a labeled conservative 120-second closeout allowance. Recorder build/fixture/CTest identities describe the timing target actually run; supplemental results record both 23-test Python modes and the intentional one-case mutation outcome.

Final budget: 38,811 active seconds, 2,565 diagnostic-gate seconds, 1,221 cumulative runtime churn lines, 5,594 cumulative test/tool churn lines, 22 records, no pause. Frozen 32-hour/6,000-runtime/8,000-test-tool limits remain unchanged. No new CPU backend, package or source acquisition was introduced.

## Deviations from Plan

**1. [Rule 3 - Blocking documentation] Restored the existing canonical admission-gate wording.** The current ROADMAP expressed the open/GAPS_FOUND/Phase02 gate with wording that the unchanged literal validator rejected. The orchestrator explicitly authorized the smallest wording correction. The sentence now includes `Phase 01 remains open / GAPS_FOUND and Phase 02 gated`; its admission meaning and all requirement statuses are preserved. This bounded change is included in Task 2 commit `06d7001`; the validator was not weakened.

Git ledger/index writes initially hit sandbox restrictions. Authorized elevated Git operations made normal commits with hooks; no commit protection was bypassed. Failure-handling effort is charged.

## Qualification limits

F14-03 and T-01-15-03 remain HIGH/open. CPU-01–05 remain Pending; Phase 01 remains open/GAPS_FOUND and Phase 02 gated. This summary completes the two Plan 01-18 tasks only. It does not close Plan 01-17, choose either silicon saved-PC value, establish new continuation/whole-backend qualification, or perform the independent review/security gates owned by 01-21. No stubs, skipped planned tests or unrun Plan 01-18 verification commands remain. New amendment metadata parsing is covered by the declared threat model; no undeclared network/auth/public-ABI surface was added.

## Self-Check: PASSED

All ten modified task paths exist. All four task commits exist; no tracked files were deleted. Protected original bytes/values and ledger prefix comparisons pass. The summary is written on disk before state updates; subsequent metadata commits are separate from the measured task range.
