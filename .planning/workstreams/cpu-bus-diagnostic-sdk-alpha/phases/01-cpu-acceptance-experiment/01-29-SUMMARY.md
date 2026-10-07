---
phase: 01-cpu-acceptance-experiment
plan: 29
subsystem: workflow
tags: [cpu-admission, evidence, security, preservation, phase-verification]
requires:
  - phase: 01-28
    provides: restored current admission gate and separate-verifier routing
provides:
  - independent CPU-01–05 admission recommendation bound to the unchanged candidate
  - separate ASVS L1/high-block assessment and fail-closed terminal-record checker
  - append-only cost/UAT evidence and direct phase-verifier handoff
affects: [phase-01-verification, cpu-05]
actuals:
  tokens: 32355
  tasks: 2
  commits: 4
tech-stack:
  added: []
  patterns: [independent recommendation separate from phase admission, append-only preservation check]
key-files:
  created:
    - tools/workflow/phase01_admission.py
    - tests/workflow/test_phase01_admission.py
    - .planning/phases/01-cpu-acceptance-experiment/01-29-ADMISSION-REVIEW.md
    - .planning/phases/01-cpu-acceptance-experiment/01-29-ADMISSION-SECURITY.md
    - .planning/phases/01-cpu-acceptance-experiment/01-29-ADMISSION.json
    - .planning/phases/01-cpu-acceptance-experiment/01-29-SUMMARY.md
  modified:
    - experiments/owned_cpu/budget-ledger.json
    - .planning/phases/01-cpu-acceptance-experiment/01-UAT.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/phases/01-cpu-acceptance-experiment/.continue-here.md
key-decisions:
  - "Recommend bounded acceptance only after separate CPU and security assessments; the recommendation never admits the candidate or phase."
  - "Keep original-silicon saved PC unknown and exact 0x4AFC candidate-only unsupported."
  - "Preserve the reviewer’s narrow WR-01 warning: the immutable SR-switch documentation claims an unsupported $106 fetch; it does not change runtime behavior or the 15/90 continuation result."
requirements-completed: []
coverage:
  - id: CPU-ADMISSION-RECOMMENDATION
    description: Independent review supports all five bounded CPU predicates and security reports zero HIGH/CRITICAL blockers.
    requirement: CPU-05
    verification:
      - kind: other
        ref: .planning/phases/01-cpu-acceptance-experiment/01-29-ADMISSION.json
        status: pass
      - kind: other
        ref: .planning/phases/01-cpu-acceptance-experiment/01-29-ADMISSION-REVIEW.md and 01-29-ADMISSION-SECURITY.md
        status: pass
    human_judgment: false
  - id: ADMISSION-TERMINAL-CONTROLS
    description: Current report identities, terminal predicates, normal/optimized controls and conditional child exit validate.
    verification:
      - kind: unit
        ref: tests/workflow/test_phase01_admission.py
        status: pass
      - kind: other
        ref: python3 tools/workflow/phase01_admission.py verify --decision .planning/phases/01-cpu-acceptance-experiment/01-29-ADMISSION.json --check-recommendation-exit
        status: pass
    human_judgment: false
  - id: ADMISSION-PRESERVATION
    description: Old receipt/source/report/history prefixes remain exact while one ledger record and six current UAT rows append.
    verification:
      - kind: other
        ref: python3 tools/workflow/phase01_admission.py verify --decision .planning/phases/01-cpu-acceptance-experiment/01-29-ADMISSION.json --check-preservation
        status: pass
      - kind: other
        ref: python3 tools/owned_cpu/contract.py validate, budget; python3 tools/owned_cpu/acceptance.py verify
        status: pass
    human_judgment: false
---

# Phase 01 Plan 29: Independent admission recommendation Summary

**Produced one independently supported, exact-bound accept recommendation while keeping Phase 01 open and Phase 02 gated.**

## Performance

- **Duration:** 73 minutes from the recorded resume handoff through final verification; all-agent charged effort is recorded separately below.
- **Started:** 2026-10-05T18:17:04Z
- **Completed:** 2026-10-05T19:30:06Z
- **Tasks:** 2
- **Files modified:** 11
- **Plan effort:** 6,463 / 7,200 reserved seconds; remaining reserve 737 seconds.
- **Plan-local checker/test churn:** 712 / 800 nonblank added/deleted lines across the RED, GREEN and preservation-fix commits. The frozen owned-core churn counters remain unchanged because these workflow files are outside their measured paths.

## Accomplishments

- Two independent non-author reports bind the unchanged `owned-p01-c14-continuation-2` candidate. CPU-01–05 are each assessed sufficient for the bounded experiment. Security assessed ASVS L1 with zero applicable HIGH/CRITICAL blockers. The machine decision is `accept_recommended`, `phase_admitted: false`, and `blocker: null`.
- Added a read-only standard-library checker and adversarial controls. A preservation return-path `NameError` found during independent assessment was fixed in `54136cf`; the normal and optimized suites both pass 15/15. The documentation gate literal was restored in ROADMAP without changing pending requirements or weakening validators.
- Appended one actual budget record and UAT rows 52–57. The original 47 ledger entries, frozen fields, six candidate collections, three superseded seals, all 39 source-map entries, ten immutable files and UAT bytes for rows 1–51 remain unchanged. Final UAT preservation reports 57 rows; no historical UAT row was replayed.
- Recorded WR-01 as a narrow warning: `ACCEPTANCE.md` and `ORACLE.md` describe a `$106` extension fetch that current source does not perform before privilege entry. Immutable candidate artifacts were left untouched; this wording is a limitation of the assessment, not a runtime repair or hardware claim.

## Verification

| Check | Result |
|---|---|
| `python3 -m unittest discover -s tests/workflow -p test_phase01_admission.py` | 15/15 passed |
| Same admission suite under `python3 -O` | 15/15 passed |
| `PYTHONPATH=. python3 tests/workflow/test_phase01_docs.py` | 8/8 passed; 20/20 local README links resolved |
| `python3 tools/owned_cpu/contract.py validate` | Pass; CPU-01–05 Pending; Phase 02 gated |
| `python3 tools/owned_cpu/contract.py budget` | Pass; 48 entries; 86,226 active seconds; 2,565 diagnostic seconds; 1,228 runtime churn; 6,540 contract-measured tool/test churn; no pause |
| `python3 tools/owned_cpu/acceptance.py verify` | Pass; six collections; zero lane blockers; receipt remains unqualified |
| Admission base verifier and `--check-recommendation-exit` | Both pass; actual child exit 0 returns `accept_recommended`, `phase_admitted=false` |
| `--check-preservation` | Pass; 10 immutable artifacts, 39 candidate sources, six collections, three superseded seals, 47 historical ledger entries, one appended entry, 51 historical UAT rows and 57 total rows |
| Independent final accounting/preservation confirmations | Reviewer and security assessor confirmed ledger identity, prefix/frozen fields, plan reserve and preservation counts read-only |
| `git diff --check 6e9a0ca70c83e2c8bca7c64d5ab8ed5f83a87533 HEAD` | Pass |

The preserved candidate receipt is still `unqualified`; the independent recommendation does not complete the phase. The latest whole-phase report remains 9/10 `GAPS_FOUND` and predates this plan. No native lane was recollected, receipt resealed, or silicon search repeated.

## Threat Flags

| Threat | Final disposition |
|---|---|
| T-01-64 spoofing | Mitigated: distinct independent roles, report hashes, evidence identities and five predicate controls validate. |
| T-01-65 tampering | Mitigated: checker regressions and final append-only preservation pass. |
| T-01-66 elevation | Mitigated: `phase_admitted=false`; requirements stay Pending and Phase 02 gated. |
| T-01-67 repudiation | Mitigated: actual costs, immutable prefixes, final ledger digest and preservation were independently confirmed. |
| T-01-SC dependency mutation | Accepted: no new dependency/install; existing Unity remains pinned and test-only. |

## Task Commits

1. `4256394` — test(01-29): add terminal disposition RED control.
2. `4945f34` — feat(01-29): validate admission terminal records.
3. `54136cf` — fix(01-29): exercise preservation closeout path.
4. Task 2 accounting, recommendation and workflow closeout commit is recorded in git history after this summary was prepared.

## Handoff

Plan 01-29 is complete; Phase 01 is not. The exact next workflow action is one separate direct `gsd-verifier` whole-phase assessment for Phase 01, using the latest 9/10 report, this recommendation and current evidence. The installed OpenGSD 1.15.0 exposes no proven standalone user command for that direct dispatch. `$gsd-verify-work 01` starts conversational UAT and would repeat recorded rows, so do not use it as a substitute. Pause here for the user to continue and choose the next model. Preserve CPU-01–05 as Pending, Phase 02 gated and original-silicon saved PC unknown until that verifier resolves the phase goal.
