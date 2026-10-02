# Plan 01-06: Backend direction checkpoint

Status: **developer selected C — reject/defer this current Musashi candidate and discuss backend replanning**. Gate: **blocking-human**, satisfied by the actual developer response supplied to this continuation. Task 1 is complete; this records future direction, not backend acceptance or Phase 01 completion.

## Established decision evidence

Plan 01-05 is complete. Its current structured result is `decision: rejected`, `phase_status: GAPS_FOUND`, with reason `blocking review finding`. Its normal-Python seal and read-only verification both returned the intended non-admitting result. At this checkpoint, read-only checks confirmed the summary, rejection fields and both archived SHA-256 identities.

The independent source reconciliation retains six critical/open findings: width-invalid register shifts (CR-01), negative signed DIVS remainder shift (CR-02), signed bit-31 masks (CR-03), unsafe generator paths (CR-04), unsigned EOF sentinel (CR-05), and off-by-one generator capacity guards (CR-06). Two medium/open warnings concern optimized Python replay validation (WR-01) and relative-path patch normalization (WR-02). No repair or new runtime reproduction is claimed.

Historical passes, failures, source identities, oracle ancestry and counterexamples remain preserved. The prior accepted report and prior review are archived under `experiments/cpu/evidence/plan-01-05/`; current evidence is in `experiments/cpu/ACCEPTANCE.md`, `REVIEW.md` and `acceptance-results.json`.

CPU-05's bounded decision obligation is complete. CPU-01–04 remain Pending for current admission. Phase 01 remains open / GAPS_FOUND; Phase 02 remains gated. Historical grammar-preflight refusal did not establish that all four behaviors failed. Current source blockers prevent admission.

## Frozen accounting and authorization boundaries

Both substantive adaptation attempts are consumed. Retained charges: 2,614 handwritten lines, 523 helper lines, 483 semantic lines; 20,005 cumulative effort seconds and 18,859 final-attempt seconds. Six upstream files and two generated files totaling 36,559 lines / 832,698 bytes are charged. No refund, new adaptation attempt or cap change is authorized.

Original caps remain: two attempts; 57,600 cumulative / 28,800 per-attempt seconds; six upstream files; 5,000 handwritten / 600 helper / 500 semantic lines; two generated files / 50,000 lines / 2,097,152 bytes. Remaining numeric allowance does not authorize a third attempt.

Every option preserves these historical charges and the current phase gate. A reply identifying a future path authorizes only its next named discussion/planning step, subject to the user's workflow/model pause. It does not authorize source repair, budget revision, a replacement backend, roadmap rescope, phase verification or Phase 02 execution.

## Considered checkpoint choices

| Choice | Next direction | Value and tradeoff |
| --- | --- | --- |
| A — Keep deferred and paused (recommended current state) | Preserve the candidate deferral and gate while deciding. | Adds no commitment or adaptation; the SDK remains blocked. |
| B — Discuss a repair/requalification contract | Separately discuss and plan explicitly authorized Musashi repair work with a reconciled attempt/budget contract retaining all old charges. | Reuses existing experiments; bounded repair feasibility and new qualification evidence still need assessment. |
| C — Reject/defer and discuss backend replanning | Separately discuss/replan the backend path and any necessary roadmap changes. | Opens alternatives; candidate research, adaptation cost and milestone consequences remain unqualified. |

A was the checkpoint's recommended paused state; B was its strongest alternative for obtaining Musashi repair evidence. The developer explicitly selected C. The current candidate remains rejected/deferred, and none of these choices qualifies a backend.

## Actual developer direction and next workflow boundary

The developer prefers building as much as possible themselves because a flawed foundation is not worth reusing, while wanting to consider a strangler-style migration. Correctness and an efficient path take priority. The next discussion must compare options and tradeoffs across relevant architecture, CPU emulation, testing and independent oracles, maintainability, dependency and integration roles, applying METHODOLOGY.md's breadth, adversarial review and synthesized recommendations.

One proposal to investigate is an owned C 68000 core behind a narrow private replacement seam, with a strangler-style transition. This is a discussion preference, not a settled design, implementation instruction, final backend selection or acceptance claim. Existing Musashi evidence may inform comparison only within its recorded limitations; it does not become an independent hardware oracle or an admitted production foundation.

The next named step is **discuss backend replanning**. Option C authorizes only that next discussion/planning step, with the workflow/model pause before it starts. This execution records the selection and stops. It authorizes no source work, repair, third adaptation attempt, cap changes, final backend selection, roadmap/milestone scope changes, phase verification or Phase 02 execution. Any later implementation or contract/scope revision requires its own explicit reconciliation and authorization. Both attempts, all charges and all caps above remain unchanged; CPU-01–04 remain Pending, CPU-05's bounded decision remains complete, Phase 01 remains open / GAPS_FOUND and Phase 02 gated.
