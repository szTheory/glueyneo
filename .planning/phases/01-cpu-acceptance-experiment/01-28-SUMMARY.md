---
phase: 01-cpu-acceptance-experiment
plan: "28"
subsystem: workflow
tags: [cpu-acceptance, documentation, regression, deferred-admission]
requires:
  - phase: 01-27
    provides: independently bound deferred seal
provides:
  - restored exact admission interface and canonical README navigation
  - bounded local document regression with four negative controls
  - additive current-revision UAT row and fresh-verifier handoff
affects: [phase-01-verification, cpu-05]
tech-stack:
  added: []
  patterns: [canonical state navigation, mutation controls, additive evidence]
key-files:
  created:
    - tests/workflow/test_phase01_docs.py
    - .planning/phases/01-cpu-acceptance-experiment/01-28-SUMMARY.md
  modified:
    - README.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
    - .planning/phases/01-cpu-acceptance-experiment/01-UAT.md
    - .planning/phases/01-cpu-acceptance-experiment/.continue-here.md
key-decisions:
  - Route README through STATE rather than embedding a fixed Phase 01 execution command.
  - Preserve Pending CPU requirements and pause for a separate fresh whole-phase verifier.
requirements-completed: []
coverage:
  - id: DOCUMENT-INTERFACE
    description: Current admission wording and README navigation reproduce the deferred decision.
    verification:
      - kind: unit
        ref: tests/owned_cpu/test_contract.py#ContractControls.test_frozen_subject_and_pending_gate_validate
        status: pass
      - kind: other
        ref: python3 tools/owned_cpu/contract.py validate
        status: pass
      - kind: other
        ref: python3 tools/owned_cpu/acceptance.py verify
        status: pass
    human_judgment: false
  - id: LOCAL-REGRESSION
    description: Current documents pass while four deliberate gate/link/route mutations fail.
    verification:
      - kind: unit
        ref: tests/workflow/test_phase01_docs.py#WorkflowDocsControls
        status: pass
    human_judgment: false
  - id: SCOPED-EVIDENCE
    description: UAT row 50 preserves historical rows and routes to separate phase-goal verification.
    verification:
      - kind: other
        ref: Task 2 historical_rows_preserved and row_50_present assertion
        status: pass
      - kind: other
        ref: git diff --check
        status: pass
    human_judgment: false
actuals:
  tokens: 11273
  tasks: 2
  commits: 2
commits: 2
plan_head_before: b0b3b7aa123b2b18e0caf651624547b77cb7176c
plan_head_after: ed35fb118cc4f6cb74cd350cd4e14bdfca085f13
duration: 6min
completed: 2026-10-05
status: complete
---

# Phase 01 Plan 28: Documentation gate and navigation Summary

**Restored frozen admission wording and canonical contributor navigation with five local regression controls and additive current evidence.**

## Performance

- Started: 2026-10-05T14:30:57.419Z after context loading.
- Completed: 2026-10-05T14:38:14.794Z at summary authoring.
- Duration: 6 minutes.
- Tasks: 2; files: 7 including execution bookkeeping.
- Commit measurement covers the two task commits through plan_head_after; the subsequent metadata commit is outside that measured window.

## Accomplishments

- Restored exactly `Phase 01 remains open / GAPS_FOUND and Phase 02 gated` without changing frozen validators. ROADMAP describes the fresh 2026-10-05 8/9 verdict, the closed report-binding issue and bounded repair.
- README now resolves through STATE, retains 49/49 as historical evidence and removes the stale fixed execution route. A standalone unittest under tests/workflow derives its checkout root and checks the actual documents plus four mutations.
- Appended row 50 with Task 1 revision and three SHA-256 identities. The active recorded aggregate is 50/50, comprising 49 historical passes plus one current document pass. Historical rows, aggregates and source identities remain verbatim; phase admission is unchanged.

## Verification

At base `b0b3b7aa123b2b18e0caf651624547b77cb7176c` before document repair:

| Command | Observed result | Exit |
|---|---|---|
| Targeted frozen-subject contract test | 1 test, 1 pending_gate error | 1 |
| contract.py validate | status fail, reason pending_gate, admission gate changed | 2 |
| acceptance.py verify | status fail, admission gate changed | 1 |
| New docs module | 5 tests, 4 expected failures caused by bad current documents | 1 |

Isolated in-memory probes also detected the missing STATE link and stale execution route, avoiding masking by the missing ROADMAP gate. These expected failures did not alter candidate evidence.

At committed Task 1 revision `612c24558d010eef2cbc14958a7d34e1b8b208ef`, all four checked commands passed. The tracer gate reran them before Task 2:

| Command | Observed result | Exit |
|---|---|---|
| `PYTHONPATH=. python3 tests/owned_cpu/test_contract.py ContractControls.test_frozen_subject_and_pending_gate_validate` | 1/1 tests | 0 |
| `python3 tools/owned_cpu/contract.py validate` | status pass; 24 markers; 10 historical files; 47 budget records; CPU-01–05 Pending; saved PC unknown; Phase 02 gated | 0 |
| `python3 tools/owned_cpu/acceptance.py verify` | status pass; 6 collections; no lane blockers; disposition unqualified | 0 |
| `PYTHONPATH=. python3 tests/workflow/test_phase01_docs.py` | 5/5 tests; 20 Markdown links, 20/20 local resolved | 0 |

Negative controls reject removed admission gate, removed STATE link, broken local link and reintroduced fixed execute route. No fixed link count is embedded in the test.

Task 2 pre-commit `git diff --check` exited 0. Its exact planned preservation assertion printed `historical_rows_preserved: True` and `row_50_present: True`, exit 0. A further byte comparison confirmed the entire former UAT is an exact prefix of the appended file.

Existing budget remains 79,763 active seconds, 2,565 diagnostic seconds, 1,228 runtime churn and 6,540 test/tool churn, no pause. Candidate source, tools, owned tests, manifests, receipt, reports and ledger remain unchanged. No native lane or historical UAT replay was needed.

Final sequential bookkeeping changed ROADMAP status/count prose, so the four affected commands ran again on working-tree base ed35fb118cc4f6cb74cd350cd4e14bdfca085f13. Results remained 1/1 and 5/5 tests, 20/20 links, validate pass, six collections/unqualified/no lane blockers, all exits 0. Final ROADMAP SHA-256 is f5db0e06851b2b59e48e47b57bbb6fe285922ebb3b2d493b633f20205069b563. README and test identities remain those recorded in row 50.

## Task Commits

1. `612c245` — fix(01-28): restore admission gate and canonical contributor navigation.
2. `ed35fb1` — docs(01-28): append scoped evidence and fresh verifier handoff.

## Decisions and Deviations

The plan is implemented within its seven-file scope. Requirements-completed remains empty despite CPU-05 traceability in the plan: the explicit plan and owner constraints forbid marking CPU acceptance complete. Generic state/progress counters must retain the distinction between 28 summaries, 27 execution-complete plans and an open phase; Plan 01-17 remains at its answered incomplete checkpoint.

The executor tracer protocol requires an end-to-end gate rerun after Task 1, so the four focused commands ran again at its committed revision. Task 2 reused that evidence without replaying historical rows. No test expectation, validator or budget was relaxed.

The initial .git ledger write was sandbox-denied and succeeded under reviewed escalation. Normal commits used hooks; no bypass. One malformed patch combining delete/add on the same handoff path was rejected before mutation and replaced with a normal update.

## Post-execution assurance gates — 2026-10-05

The Nyquist audit reconciled all five tasks in Plans 01-27 and 01-28 against
their recorded automated checks; all 12 plan verification blocks pass and no
new test is needed. The current Plan 01-28 checks include 5/5 documentation
tests, 20/20 local README links, and four negative controls.

The Plan 01-28 threat register was checked at ASVS L1 against its recorded
evidence: T-01-61 (admission-text tampering) CLOSED by the exact restored gate
and passing contract/acceptance checks; T-01-62 (navigation/status spoofing)
CLOSED by the resolving STATE pointer, mutation controls and additive row 50;
T-01-63 (candidate-evidence repudiation) CLOSED by passing read-only receipt
verification and unchanged sealed inputs; T-01-SC (dependency installation)
ACCEPTED as low risk by the plan disposition because the change adds no
dependency, package install, runtime code or network surface. Open high or
critical findings: 0. CPU-01–05 remain Pending and original-silicon saved PC
remains unknown.

The current `01-SECURITY.md` bytes are bound by the deferred receipt at SHA-256
`27d9974e72c9e58b8131d30883c5555c03665718a32b997bb3d138980d0137e2`. Editing
that report to append this documentation-only crosswalk would make
`acceptance.py verify` fail with a stale security document and require another
independent report rebind. The crosswalk is recorded here; the sealed security
report and receipt remain unchanged.

## Preservation and Scope

All three pre-existing out-of-scope edited files retain their starting SHA-256 identities: METHODOLOGY, whole-phase VERIFICATION and dated verification-loop preparation evidence. They were not staged. No new dependency, network endpoint, auth path, schema or runtime surface was introduced. No known stub, skipped test or unrun plan verification remains.

CPU-01–05 remain Pending, candidate unqualified and admission deferred. Phase 01 remains open / GAPS_FOUND, Phase 02 gated and original-silicon saved PC unknown.

## Self-Check: PASSED

Both task commits exist; the new test file and this summary exist. UAT preservation and sealed-scope comparison pass. All changed implementation inputs passed their required current checks.

## Next Step

Plan 01-28 execution is complete; Phase 01 is incomplete. Pause for one separate fresh whole-phase `gsd-verifier` assessment and refresh of `01-VERIFICATION.md`. Installed OpenGSD 1.15.0 routing defects require direct dispatch; there is no verified user CLI command for that workaround. Do not repeat UAT broadly, create another gap plan from the old verdict, reopen the finite silicon search or start Phase 02.
