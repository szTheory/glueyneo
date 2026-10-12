---
phase: 01-cpu-acceptance-experiment
plan: "07"
subsystem: owned-cpu-governance
tags: [68000, contract, accounting, gsd]
provides:
  - Exact owned-core diagnostic contract and supported-scope boundaries
  - Separate revision-3 effort/churn ledger with preserved historical hashes
  - Executable validation, budget, record and self-test controls
affects: [phase-01-execution, owned-cpu-admission]
actuals:
  tokens: 17647
  tasks: 3
  commits: 8
plan_head_before: 7acc36e4538cc2c152d791763f9b39425122f6db
tech-stack:
  added: [Python governance validator, CTest log measurement]
  patterns: [private owned-core contract, immutable historical hash checks, explicit threshold pauses]
key-files:
  created:
    - experiments/owned_cpu/CONTRACT.md
    - experiments/owned_cpu/budget-ledger.json
    - tools/owned_cpu/contract.py
    - tests/owned_cpu/test_contract.py
  modified:
    - .planning/PROJECT.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - README.md
    - .planning/phases/01-cpu-acceptance-experiment/.continue-here.md
key-decisions:
  - "Keep CPU-01–05 Pending and Phase 02 gated until current implementation evidence and fresh phase verification support admission."
  - "Charge 3,360 seconds of governance to the 32-hour owned-core cap; the separate eight-hour diagnostic gate starts with Plan 01-08 runtime or behavioral-test work."
  - "Preserve the rejected Musashi experiment as immutable history; do not select it or use it as current acceptance evidence."
duration: 56min
completed: 2026-10-02
status: complete
---

# Phase 1 Plan 07: Owned-core contract and budget

**The owned C17 experiment now has a reviewable diagnostic contract, a bounded pre-implementation budget, and executable checks while backend admission stays open.**

## Performance

- **Duration:** 56 minutes, conservatively charged from the first observed GSD activity through plan closeout
- **Tasks:** 3
- **Files modified:** 9 plan-scoped deliverables

## Accomplishments

- Defined the exact first diagnostic, later admission cases, supported opcode/mode scope, exception and bus boundaries, timing limits, and unsupported outcomes in `experiments/owned_cpu/CONTRACT.md`.
- Reconciled active project and requirement wording with the approved private owned-core direction. The canonical roadmap story remains valid, CPU-01–05 remain Pending, and Phase 02 remains gated.
- Froze the separate owned-core ledger before runtime work. It records a 32-hour cumulative cap, the separate eight-hour diagnostic gate, 3,360 governance seconds, zero runtime churn, 636 test/tool lines, and SHA-256 identities for ten historical files.
- Added `validate`, `budget`, `record`, and `self-test` commands. Recording checks explicit agent intervals, build and fixture identities, CTest results, Git churn, and relative paths.
- Corrected the level-7 interrupt acceptance wording and absolute MOVE encodings against Motorola's MC68000 User's Manual, §6.3.2, before runtime implementation.

## Task Commits

1. **Trace and validate the contract:** `22499eb`, `c92b86b`, `44ecf9e`
2. **Reconcile project scope:** `88dc4e8`
3. **Freeze and bind the separate ledger:** `b3c2951`, `bfda2cb`, `b57eb90`, `2b10ab6`

## Verification

- `python3 tools/owned_cpu/contract.py self-test` and its `python3 -O` form passed with two positive cases and six named negative controls.
- `python3 -m unittest discover -s tests/owned_cpu -p test_contract.py` passed all nine tests, including end-to-end record-path checks for interval totals, build/fixture identity, CTest count, relative path privacy, and measured churn.
- `python3 tools/owned_cpu/contract.py validate` passed: canonical story `valid=true`, `errors=[]`; ten historical files matched; CPU-01–05 remain Pending; Phase 02 remains gated.
- `python3 tools/owned_cpu/contract.py budget` passed: 3,360 cumulative active seconds, zero diagnostic-gate seconds, zero runtime churn, 636 test/tool churn lines, and no threshold pause.
- `git diff --check` passed against code start. The historical `experiments/cpu` candidate tree is unchanged.

No owned CPU runtime or behavioral test existed at closeout, so no CPU behavior or backend-admission claim follows from these governance checks.

## Decisions and Deviations

The official manual review narrowed a prior level-7 statement and made the MOVE absolute encodings explicit. This changed contract wording only; no caps, scope, or historical files changed. The record-path test was added before the first runtime slice and recorded in ledger revision 3.

The repository Git metadata is read-only in the default sandbox. Plan 07 was executed sequentially in the authorized existing branch; its scoped GSD commits were written after sandbox review. No worktree was created.

## Next Phase Readiness

Plan 08 may now begin the owned CPU implementation and the separate diagnostic gate. That plan must execute the original fixture first and retain its named wrong-behavior control. Phase 01 remains open / GAPS_FOUND; Phase 02 remains gated.
