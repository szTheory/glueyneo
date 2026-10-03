---
phase: 01-cpu-acceptance-experiment
plan: "17"
subsystem: owned-cpu-source-adjudication
tags: [68000, primary-sources, ambiguous, blocking-human]
requires:
  - phase: 01-16
    provides: Unresolved exact-source F14-03 challenge
provides:
  - Ten-candidate bounded acquisition with exact protected baseline and public source identities
  - Independently authored ambiguous verdict bound to committed acquisition
  - Blocking human decision with explicit unapplied claim-revision alternative
affects: [phase-01-gap-planning, phase-01-security, phase-02-admission]
tech-stack:
  added: []
  patterns: [finite source acquisition, independent exact-record adjudication, append-only charges]
key-files:
  created:
    - .planning/phases/01-cpu-acceptance-experiment/01-17-ILLEGAL-EVIDENCE.json
    - .planning/phases/01-cpu-acceptance-experiment/01-17-ILLEGAL-ADJUDICATION.md
  modified: [experiments/owned_cpu/budget-ledger.json]
key-decisions:
  - "Terminal B: preserve ambiguous authority and stop at blocking-human decision; no saved-PC assumption selected."
requirements-completed: []
status: checkpoint
duration: 22min
completed: null
checkpoint_date: 2026-10-03
actuals:
  tokens: 17562
  tasks: 2
  commits: 2
  active_seconds: 1445
plan_head_before: f0af6bc3815d35c52c06db3c04cf75da6f147991
plan_head_after: b6472112d027c950dd8070076dc3d4e9702fc22b
coverage:
  - id: D1
    description: Finite exact-source acquisition and preserved history
    human_judgment: false
    verification:
      - {kind: other, ref: "Plan 01-17 evidence structural checks 9/9 and protected hashes 181/181", status: pass}
  - id: D2
    description: Independent authority judgment and reserved human scope decision
    human_judgment: true
    rationale: "No explicit original-MC68000 4AFC saved-PC authority or qualified capture defeats the competing interpretation; assumption requires explicit approval."
    verification:
      - {kind: other, ref: "Plan 01-17 adjudication binding/preservation checks 8/8", status: pass}
---

# Phase 01 Plan 17: Bounded ILLEGAL authority search Summary

**Ten inspected candidates and independent source challenge strengthen the fault-PC derivation while retaining an explicit unresolved original-MC68000 saved-PC decision.**

## Terminal status

Evidence acquisition and independent adjudication were performed. Plan 01-17 is **awaiting a blocking-human decision**, not complete. The independent verdict is exactly **ambiguous**. Phase 01 remains open/GAPS_FOUND, F14-03 and T-01-15-03 HIGH/open, CPU-01–05 Pending, and Phase 02 gated. All nine plan assumptions remain unresolved. No saved-PC rule, scope amendment, repair or acceptance was selected.

## Accomplishments and evidence binding

The acquisition binds baseline `f0af6bc3815d35c52c06db3c04cf75da6f147991`, 181 protected nonledger files, initial ledger hash/count and unchanged original reconciliation/archive. The original contract remains SHA-256 `6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`; reconciliation remains `03130a6b9499c176842ce489ed12ab92afa81e682a45182914baefda8f32fee4`.

Acquisition JSON SHA-256 is `4278e050a270d8ba662dc7ba4c89eeed58e950166cc7ae5b4cf1af1c425d6adf`. Independently authored adjudication SHA-256 is `22f647c2e9c56d63aeb9f6a909f7a38622d97fc9f3b282216ebe3b40b80dfadb`. The report binds that exact committed JSON, independently reopens all eight PDFs, matches all ten candidate byte hashes and preserves all 181 protected hashes.

Four finite routes were classified: manufacturer catalogs, older Motorola archives and official errata/addenda were inspected; qualifying existing original-silicon receipts remained unavailable after two accessible candidates were inspected. Ten distinct documents exhaust the local candidate bound. Every retrieval used a 30-second timeout and 16 MiB read bound; the largest response was 11,152,468 bytes. Eight existing-tool PDF extractions succeeded. No retry loop, account creation, vendor message, capture request, package/tool installation or extra candidate search followed.

New material exceeds the preceding UM/PRM/PRMER reopening: official M68000UMAD, MC68000UMAD and EC000UM; an archived scanned manual; Motorola's April 1983 original-MC68000 document; and ELECTRELIC/WinUAE CPUTEST receipt candidates. Exact source hashes, public URLs, printed identities, pages, model limits and ancestry live in the acquisition/report. Copyrighted PDFs, raw web bytes and extracted text remain outside tracked distribution.

## Source judgment and locator corrections

The official UM prints Ninth Edition/copyright 1993. Its grouping heading is §6.2.3 at 6-8/PDF92; Table6-3 is 6-9/PDF93. The archive filename Rev8 also prints Ninth Edition, so its repeated wording supplies no independent behavioral resolution. Official catalog revisions/dates do not establish separately printed exception semantics.

The independent reviewer corrects two acquisition UMAD locators without rewriting the committed author record: PDF4 is printed5, low-power discussion; PDF7 is printed8, example trap routine/electrical transition. The report explicitly does not rely on the mistaken section summaries. These corrections affect citation precision and do not change the verdict.

Motorola April1983 directly applies to original MC68000 and corroborates pre-execution illegal detection, usual next-unexecuted PC and absent illegal-instruction trace. This strengthens `$100` but supplies no explicit instruction-specific saved-PC statement or correction of later wording. EC000 shares core ancestry but repeats the trap analogy; user-code compatibility does not prove original supervisor exception-PC identity. Addenda/PRMER silence selects neither PC. ELECTRELIC positively describes fault-PC handler behavior, but lacks a qualified CPU/mask/opcode-site/raw-frame/capture receipt. CPUTEST describes emulator-derived expectations and hardware capability without the needed exact capture.

The unresolved premise is whether UM §6.3.6's trap/group-2-frame similarity imports §6.3.5's following-PC rule or describes only exception processing/shared frame layout while §6.2.3/5 leaves the unexecuted opcode at `$100`. Fault PC is the stronger derivation, but calling it sufficient under the unchanged standard requires the disputed human judgment reserved by the plan.

## Task commits

1. Task 1: `23291ff` — bounded acquisition JSON and first author charge.
2. Task 2: `b647211` — independent ambiguous adjudication and review/closeout charges.

Checkpoint-summary commit is separate. Actual commit count and before/after revisions are measured from the persistent Git sentinel, excluding the later summary metadata commit. Token actuals use realized task diff characters/4, not model usage.

## Fresh verification and accounting

All eight exact automated commands from Plan 01-17 were run by extracting its `<automated>` elements and executing them from repository root. Final exits are all zero: JSON parse; evidence9/9; contract validation; budget; adjudication8/8; ledger preservation3/3; final contract validation; final budget. Contract checks report24 markers,10 historical hashes,CPU-01–05 Pending and Phase02 gated. Protected-byte comparison passes181/181; strict archive equality passes; original19 ledger entries remain an equal prefix and every non-entry field is unchanged.

Budget passes before acquisition, before review and after final charges:37,952 active seconds,21 records,no pause; diagnostic gate retains2,565 seconds; runtime churn1,206 and test/tool churn5,252 remain unchanged. Plan charges total1,445 seconds:527 acquisition;918 review/handoff/finalization/closeout. The independent measured review interval is329 seconds, plus60 explicitly estimated initial-read allowance. Acquisition includes180 conservative initial-read seconds preceding baseline capture. Final accounting includes180 conservative closeout seconds, explicitly an allowance rather than fresh behavioral execution. Idle reviewer waits are excluded from the executor's recorded active segments.

The document ledger entries inherit historical build/fixture identities explicitly labeled historical. Nonzero new results are document/preservation checks. **No CPU/native lane, wrong-PC mutation control, new architectural test, collector, seal, phase verifier or security audit ran.** Structural checks establish provenance and preservation, not hardware truth.

## Issues and deviations

The initial contract validator failed `pending_gate` due to orchestrator-owned ROADMAP wording; the orchestrator restored the exact literal while preserving the gate, then validation passed. The executor initially attributed that failure to STATE; the acquisition corrects that attribution. No protected source repair occurred.

The executor sandbox denied Git sentinel/index writes. The installed GSD commit wrapper returned `staging_failed`; the executor did not retry it or bypass the wrapper. The orchestrator committed the authorized paths with elevated GSD tooling and established the sentinel. Failure handling and source-citation correction work are included in accounting. STATE/ROADMAP/requirements remain orchestrator-owned and were not edited by this executor.

No runtime stubs, skipped planned verification, new dependency or unmodeled product security surface was introduced. The known missing authoritative evidence is the intended blocking result, not a fabricated placeholder.

## Blocking decision and next workflow

Recommendation under the unchanged claim: preserve unknown and keep admission blocked. The concrete alternatives are an identified genuinely available authoritative document/qualified existing receipt route, or explicit approval of this bounded assumption:

“For this private diagnostic experiment, assume exact original-MC68000 ILLEGAL 4AFC stacks its opcode address (`$100` for this fixture), based on the stronger primary derivation; original-silicon correctness of this saved-PC value remains unverified.”

That optional choice would require a preserved amendment to the frozen next-PC requirement, narrowed conformance claims and same-phase replanning. Hardware could contradict it and return behavior/consumers could be affected. Approval must expressly select the assumption and claim reduction; generic continue or silence does not do so. No such choice is applied here. A newly available authoritative route also needs an exact bounded scope; no additional capture availability is asserted.

After an explicit claim decision or resolved authoritative evidence, the concrete separate workflow is `$gsd-plan-phase 01 --gaps`. Later canonical/direct-frame repair, refreshed qualification, independent review, security reassessment and phase-goal verification remain required. This executor starts none of them.

## Self-Check: PASSED

All three new artifacts exist; commits23291ff andb647211 exist and include only authorized task paths. Acquisition/report hashes match independent binding. All181 protected hashes,19 preceding ledger entries and every non-entry field remain unchanged. All eight planned automated commands pass; no unexpected tracked deletion or generated untracked output exists. Summary status records the blocking checkpoint and no CPU requirement completion.
