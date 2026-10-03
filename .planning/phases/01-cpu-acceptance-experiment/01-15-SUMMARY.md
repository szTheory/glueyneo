---
phase: 01-cpu-acceptance-experiment
plan: "15"
subsystem: owned-cpu-source-reconciliation
tags: [68000, primary-sources, unresolved, freeze-provenance]
requires:
  - phase: 01-14
    provides: F14-03 HIGH/open contract discrepancy
provides:
  - Exact-source ILLEGAL interpretation and precise unresolved evidence need
  - Byte-identical embedded frozen contract and unchanged implementation identities
  - Append-only effort charges for both conditional tasks and closeout
affects: [01-16, phase-01-verification, phase-02-admission]
tech-stack:
  added: []
  patterns: [explicit unresolved source disposition, immutable freeze archive]
key-files:
  created: [experiments/owned_cpu/illegal-reconciliation.json]
  modified: [experiments/owned_cpu/budget-ledger.json]
key-decisions:
  - "Retain F14-03 HIGH/open: documentary fault-PC inference is stronger but the ILLEGAL-specific trap analogy remains unresolved."
  - "Withhold canonical, validator, runtime, fixture and oracle mutation; Plan 01-16 owns independent unresolved closeout."
requirements-completed: []
status: complete
duration: 12min
completed: 2026-10-03
actuals:
  tokens: 9120
  tasks: 2
  commits: 2
  active_seconds: 796
plan_head_before: 2e3a44f75ed6c5c9053672eda69dc9dab823fe7d
plan_head_after: 6a54e2c0b2747861276853c8e036bd3f2a42ed04
coverage:
  - id: D1
    description: Exact primary source interpretation with unresolved architectural disposition
    human_judgment: true
    rationale: Existing primary passages support competing interpretations; independent Plan 01-16 source challenge remains necessary.
    verification:
      - kind: other
        ref: Plan 01-15 Task 1 strict base64 archive and required-field check
        status: pass
  - id: D2
    description: Frozen contract and historical accounting preserved with append-only charges
    human_judgment: false
    verification:
      - kind: other
        ref: python3 tools/owned_cpu/contract.py budget
        status: pass
      - kind: other
        ref: Git-baseline equality of 12 historical entries and every non-entry ledger field
        status: pass
---

# Phase 01 Plan 15: Unresolved ILLEGAL source reconciliation Summary

**Exact vendor source identities and a byte-preserved contract expose the unresolved $100/$102 ILLEGAL frame dispute without changing CPU behavior.**

## Accomplishments

Both tasks completed through their designed unresolved branch. The original JSON interpretation records official UM ninth edition/copyright1993, PRM copyright1992 and PRMER Rev1/03-2007 bytes, retrieval date, SHA-256, printed pages and zero-based PDF indices. Historical HTTP/catalog revision dates are not presented as printed editions. PDFs and extracted manual text remain outside distribution; the JSON contains original summaries and project-owned contract bytes.

The general UM next-unexecuted and pre-execution/trace language favors fault PC. Its ILLEGAL-specific trap/group-2 analogy leaves a credible sequential-PC reading; PRM stacks PC without explicitly fixing that instruction-specific value. Errata lists no ILLEGAL correction. A read-only independent primary-source challenger reached the same unresolved disposition and authored no implementation or decision-record edits. Neither emulator consensus nor passing local fixtures settles hardware truth. The record names the precise authoritative adjudication needed, the strongest alternative, role synthesis, risks and reopening evidence. It does not mandate unavailable physical hardware or claim that a capture occurred.

The embedded frozen contract strictly decodes to the original bytes and unchanged code-start SHA-256 `6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`. No contract revision chain is needed or added because canonical mutation is withheld. All 12 prior ledger entries and every non-entry ledger field match preceding Git revision `2e3a44f75ed6c5c9053672eda69dc9dab823fe7d`; freeze amendments/status/revision/time, caps, code-start and Musashi history are preserved.

## Task Commits

1. Task 1 — `0e391ca`: exact source/errata/methodology record, original contract archive and first effort charge.
2. Task 2 — `6a54e2c`: append direct-check/withheld-repair charge.

Metadata closeout adds separate charges and a summary/state/roadmap commit. The measured two-commit range above excludes that metadata commit. Actual tokens are realized task-deliverable diff characters/4, rounded up, including pending closeout charges; this is not a harness token count.

## Fresh Verification and Conditional Paths

- Before mutation, `ctest --preset owned-debug -R '^owned_cpu_timing$' --output-on-failure --no-tests=error` passed1/1. Direct harness output confirmed23 Unity tests,0 failures,0 ignored.
- Normal and optimized Python unittest discovery for `test_contract.py` each passed13/13. These are existing validator controls; no supersession/tamper implementation is introduced.
- `contract.py validate` passed:24 contract markers,10 historical hashes, valid story,CPU-01–05 Pending and Phase02 gated.
- Strict base64/required-record-field check passed. Decoded archive equals current CONTRACT and original Git bytes; every recorded baseline source/evidence hash remains unchanged.
- Task2 build returned `ninja: no work to do`; timing CTest freshly passed1/1 again against unchanged native code. This is fresh execution in an existing build, not a cold rebuild or four-lane qualification.
- The exact conditional wrong-PC verification command printed `withheld: unresolved primary source` and exited0. No new `--mutate-illegal-pc` branch or consequential control qualification is claimed.
- Budget passed before mutations and after append-only records with no pause; `git diff --check` passed.

The original guest4AFC at$100 enters vector4/handler$180, saves old SR$2700 at$2ffa and PC$100 at$2ffc/$2ffe, and charges34 clocks/one dispatch in the existing fixture. Source tracing identifies opcode read, PC high/low writes, SR write and vector high/low reads. The existing ILLEGAL test asserts the frame/result/timing; this plan adds no bus-order assertion or pin capture.

## Exact Identity and Qualification Handoff

All old/new hashes are identical:

| Path | Preceding and final SHA-256 |
|---|---|
| experiments/owned_cpu/cpu.c | 8ac6ded7859184651f6eb3fff8a87c073f8e24a98d66175b64c3d86f69cbd15f |
| experiments/owned_cpu/cpu.h | afdc50cbfdce47cdb17f881fed6fe47b72d919e3220b9c599f6262f868d50eee |
| tests/owned_cpu/test_timing.c | 7747995fa198148e941b84130a409cc2a4a9ce688ec5cd64b5f7ccd24fc3b0e4 |
| tests/owned_cpu/ORACLE.md | e5ef2662a2eb5c30e4d6b1127a55c58c82ab34f76f8c5750b2d4e2807d116c7d |
| experiments/owned_cpu/SUBSET.md | 435d0c1a8e991b32c59e732b590bc0d9ae23be2983e0d14eaaadd126e20d078d |
| experiments/owned_cpu/state-inventory.json | d8972b1b359f3c9b260865251cc00e4b7f3ae820d065e8e46c4fed5e98d0d9f2 |

SUBSET:61 is preserved observed-behavior provenance; no justified supersession is asserted. No same-build header digest change is required because cpu.c is unchanged. Reconciliation record SHA-256 is `03130a6b9499c176842ce489ed12ab92afa81e682a45182914baefda8f32fee4`.

Existing REVIEW, acceptance results and source manifest remain byte-identical at the recorded preceding revision. Their hashes and all canonical/validator identities are in the JSON record. No prior collection, review, seal, completed PLAN/SUMMARY or historical VERIFICATION is rewritten. Plan01-16 must refresh the source manifest to include the new authored JSON before collection/review; runtime/state inventory source identities require no behavioral refresh in this branch. Prior four-lane evidence remains historical; this plan qualifies no platform, silicon, board, compatibility or acceptance claim.

## Accounting and TDD

Executor start13:15:00Z is a conservative inferred earlier bound because dispatch time was not captured. Source task charges420 executor seconds plus76 independent-challenger seconds; direct task charges60 executor seconds. Named conservative closeout/administration allowances cover13:23:00–13:27:00Z, including summary/state/commit/reporting; these are allowances, not exact active clocks. Total Plan15 charge796seconds; cumulative35,292/115,200. Diagnostic gate remains2,565/28,800, runtime churn1,206/6,000 and tooling churn5,252/8,000;16 entries and no pause.

Both task TDD flags are conditional on canonical/runtime behavioral mutation. The explicit unresolved branch forbids new validator/tests/runtime/fixture/oracle work; therefore no RED/GREEN repair cycle or fabricated failing architectural assertion is claimed. There is no skipped unconditional verification or known implementation stub. The null selected rule is an explicit unresolved disposition.

## Deviations from Plan

None in task scope: the plan expressly permits unresolved completion. Generic closeout instructions to mass-mark requirements complete are constrained by the plan's explicit Pending/no-admission contract and AGENTS.md evidence rules; `requirements-completed` remains empty. No package, dependency, endpoint, public ABI or new runtime trust surface is introduced.

## Remaining Gate and Readiness

F14-03 remains HIGH/open. CPU-01–05 remain Pending; Phase01 remains open/GAPS_FOUND and Phase02 gated. The exact missing source adjudication is recorded; the existing defect-register entry remains open. This executor runs neither Plan01-16 nor fresh phase verification. Plan01-16 is the ordered dependency within the selected execute-phase step and owns independent review and honest unresolved sealing.

## Self-Check: PASSED

Created reconciliation record exists; both task commits exist. Strict archive identity, all unchanged source/evidence hashes, the original12 ledger-entry prefix and freeze fields passed equality checks. Fresh native counts and both Python modes have nonzero passing denominators.
