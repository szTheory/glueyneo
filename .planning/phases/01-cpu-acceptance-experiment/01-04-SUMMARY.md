---
phase: 01-cpu-acceptance-experiment
plan: "04"
subsystem: cpu
tags: [68000, Musashi, acceptance, C17, CTest, sanitizers]

requires:
  - phase: 01-03
    provides: selected timing contract and private same-build continuation evidence
provides:
  - Independently reviewed and sealed CPU candidate decision tied to current source, evidence, and review identities
  - Reproducible accepted-only admission check and explicit unsupported-scope record
affects: [phase-01-verification, phase-02-cpu-admission]

actuals:
  tokens: 194000
  tasks: 2
  commits: 8

tech-stack:
  added: []
  patterns: [fail-closed evidence collection, independent digest-bound source review]

key-files:
  created:
    - experiments/cpu/REVIEW.md
  modified:
    - experiments/cpu/ACCEPTANCE.md
    - experiments/cpu/acceptance-results.json
    - experiments/cpu/budget-ledger.json
    - experiments/cpu/evidence/plan-01-04/

key-decisions:
  - "Accept the pinned Musashi candidate only for the bounded private 68000 experiment; keep broader hardware and platform claims unsupported."
  - "Bind the independent review to source revision 94f468326e5e529fd7c54f28434816c27f80f379 and the refreshed canonical evidence digest."
  - "Leave Phase 1 completion and Phase 2 admission for the separate GSD phase-goal verification step."

patterns-established:
  - "A candidate decision is admitted only after current-source identities, retained outputs, budget, and an independent review all verify."

requirements-completed: [CPU-01, CPU-02, CPU-03, CPU-04, CPU-05]

coverage:
  - id: D1
    description: "Current-source candidate evidence and independent review produce a sealed accepted decision within the frozen limits."
    requirement: CPU-05
    verification:
      - kind: other
        ref: "python3 tools/cpu/acceptance.py verify --require-accepted"
        status: pass
    human_judgment: false
  - id: D2
    description: "Native, ASan/UBSan, TSan, and acceptance-control evidence passes the CPU admission suite."
    requirement: CPU-01
    verification:
      - kind: integration
        ref: "ctest --test-dir build/cpu-final -L cpu --output-on-failure --no-tests=error (30/30)"
        status: pass
    human_judgment: false

duration: 31min
completed: 2026-10-01
status: complete
---

# Phase 1 Plan 04: CPU candidate acceptance summary

**Pinned Musashi 68000 accepted for the private bounded experiment after independent source review and 56 passing evidence records.**

## Performance

- **Duration:** 31 minutes
- **Started:** 2026-10-01T19:50:54Z
- **Completed:** 2026-10-01T20:21:03Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments

- Sealed the candidate decision as `accepted`; the report records 56/56 passing evidence records: 30 native, 8 ASan/UBSan, and 18 TSan.
- Completed an independent source review with no unresolved blocking findings. Its only low finding, an inventory count corrected from 98 to 99, is resolved.
- Verified all 30 CPU-labeled CTests and retained exact budget, unsupported outcomes, source identity, content digest, evidence digest, and review receipt identity.
- Kept the acceptance scope private and bounded; this does not establish board, BIOS, game, public-state, bus-cycle-suspension, or release-platform compatibility.

## Task Commits

1. **Task 1: Reproduce the candidate and collect a fail-closed acceptance report** — `6be55c2` (`feat(01-04): record complete non-admitting CPU qualification`)
2. **Task 2: Independently review the actual source and seal only qualified acceptance** — `9c57316` (`feat(01-04): seal reviewed CPU candidate acceptance`)

## Files Created/Modified

- `experiments/cpu/REVIEW.md` — independent source review tied to the evaluated revision and evidence digest.
- `experiments/cpu/acceptance-results.json` — accepted decision with 56 passing records and exact identities.
- `experiments/cpu/ACCEPTANCE.md` — reproduction steps, final scope, limits, and decision.
- `experiments/cpu/budget-ledger.json` — cumulative effort and unchanged-cap accounting.
- `experiments/cpu/evidence/plan-01-04/` — final native and instrumented configure/build/test outputs.

## Accepted Evidence Identity

- **Source revision:** `94f468326e5e529fd7c54f28434816c27f80f379`
- **Content digest:** `81aa0d99145d7b214a7336ae02f9a825eff328c8c26011fd2eef35fbe977b527`
- **Canonical evidence digest:** `6dafb025bf1b3ba2a52750cae3e9f50a1db3a552ebb8507edebb8fa2ec493c66`
- **Independent review SHA-256:** `254fae71bfdb3a468dec1126bfd4f8b4e73f8c194b6cc594945219243b17c649`

The frozen limits remain unchanged. The ledger records two attempts, 20,005 cumulative active seconds, 18,859 seconds for attempt 2, 2,614 handwritten lines (483 semantic and 523 helper lines), six selected upstream inputs, and two generated files totaling 36,559 lines and 832,698 bytes. All are within their caps.

## Limitations and Phase Readiness

The evidence is native Apple Clang 21 on Darwin arm64. Distinct compiler toolchains and a release-platform matrix are unsupported. Guest bus-error frames and bus-cycle suspension are unqualified; timing covers selected instruction and exception boundaries. No board, BIOS, or game compatibility is claimed. The same-build typed record does not establish a public state format or compatibility promise.

Plan 01-04 is complete and its candidate decision is accepted. Phase 1 remains open until the separate phase-goal verification step; Phase 2 must not start before that gate completes.

## Issues Encountered

The independent review initially found that `ACCEPTANCE.md` counted 98 state inventory entries while the inventory contains 99. The document was corrected, the reviewer confirmed the correction, and the final seal records the finding as resolved. Refreshing evidence after the ledger update changed the collector’s source revision field from the earlier reviewed identity to `94f468326e5e529fd7c54f28434816c27f80f379`; all 65 input hashes remained byte-identical, and the reviewer rebound the receipt to the refreshed report.

## User Setup Required

None.

## Self-Check: PASSED

- `python3 tools/cpu/acceptance.py verify --require-accepted` — pass.
- `ctest --test-dir build/cpu-final -L cpu --output-on-failure --no-tests=error` — 30/30 pass.
- `python3 tools/cpu/audit.py budget` — pass; all frozen limits remain within budget.

---
*Phase: 01-cpu-acceptance-experiment*
*Completed: 2026-10-01*
