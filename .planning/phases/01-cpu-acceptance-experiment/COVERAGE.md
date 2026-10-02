No external API integration: the current gap scope builds a private in-process owned C CPU and local harness; the detector's “CPU API” signal refers to our internal boundary, not a vendor service or endpoint. The deterministic scan ran on all six new plan files on 2026-10-02; current source coverage is in 01-GAP-COVERAGE.md.

# Phase 1 Source Coverage

Historical original-plan coverage below predates the approved owned-core direction and implemented experiment. It remains provenance; 01-GAP-COVERAGE.md supersedes it for plans 01-07–01-14.

Discovery consumes current pinned-source phase research and the greenfield pattern inventory. There is no existing runtime, prior implementation summary or proven verify command. Implementation paths are new outputs or earlier-plan dependencies. Project skills/graph are absent; agent_skills is empty. Calibration factor 1, zero samples, low confidence. No package-manager install or ORM/schema task exists. Assumption-delta detector returned detected:false. The API declaration above is a reasoned scope declaration, not an assertion that its detector ran.

## Multi-Source Coverage Audit

| Source | ID | Required outcome/constraint | Plan/task | Status |
|---|---|---|---|---|
| GOAL | Goal | Reproducible accepted C backend for SDK foundation | 01–04 | COVERED |
| GOAL | SC1 | Pinned source, notices and closure | 01.1–2, 04 | COVERED |
| GOAL | SC2 | Distinct/cold/failing lifecycle isolation | 02 | COVERED |
| GOAL | SC3 | Actual guest progress and selected timing limits | 01.1, 03.1 | COVERED |
| GOAL | SC4 | Complete inventory and continuation | 02.1, 03.2 | COVERED |
| GOAL | SC5 | Budget, decision, rejection/replanning | 01, 04 | COVERED |
| REQ | CPU-01 | Reproducible inventoried C closure | 01, 02, 04 | COVERED |
| REQ | CPU-02 | Independent/cold/failing lifecycles | 02, 04 | COVERED |
| REQ | CPU-03 | Actual progress and qualified timing | 01, 03, 04 | COVERED |
| REQ | CPU-04 | Complete state and continuation | 02, 03, 04 | COVERED |
| REQ | CPU-05 | Frozen bounds and explicit decision | 01, 04 | COVERED |
| RESEARCH | A1 | One pin/two attempts/all caps/cumulative accounting | 01.1–2, 04.1 | COVERED |
| RESEARCH | A2/context | Explicit full call graph, generator signatures/private tables | 01.1, 02.1 | COVERED |
| RESEARCH | A2/closure | Absent FPU/SoftFloat, debug/release dependency/link proof | 01.1–2 | COVERED |
| RESEARCH | A2/generation | Independent regeneration and file/notices inventory | 01.2, 04.1 | COVERED |
| RESEARCH | A3 | All compiled fields, destination binding/pending state | 02.1, 03.2 | COVERED |
| RESEARCH | A4/bounds | Zero/negative/max/reset/overshoot/STOP and actual boundaries | 01.1, 03.1 | COVERED |
| RESEARCH | A4/exceptions | IRQ/RTE/TRAP/illegal/privilege/address error and unsupported bus error | 02.2, 03.1 | COVERED |
| RESEARCH | A4/host | Active fault frames, nested-fault host survival | 01.1, 02.2, 03.1 | COVERED |
| RESEARCH | A5/oracle | Original bytes, exact manuals, mutation controls/ancestry | 01.1, 03 | COVERED |
| RESEARCH | A5/stress | Distinct instances, fresh barrier start, every allocation failure | 02 | COVERED |
| RESEARCH | A5/evidence | Actual tools, finite counts/timeouts, cost, current review | 02.2, 03.2, 04 | COVERED |
| RESEARCH | A6 | Native memory/resource/host/evidence threat model | All plans | COVERED |
| CONTEXT | D-01 | Exact pinned candidate only | 01.1 | COVERED |
| CONTEXT | D-02 | Freeze caps before adaptation/bounded repair | 01, 04.1 | COVERED |
| CONTEXT | D-03 | Private experiment and real tracer | 01.1 | COVERED |
| CONTEXT | D-04 | Complete compiled/distributed closure | 01 | COVERED |
| CONTEXT | D-05 | Notices, C and host safety | 01, 02.2 | COVERED |
| CONTEXT | D-06 | Every mutable object explicitly owned | 01.1, 02.1 | COVERED |
| CONTEXT | D-07 | Qualified instruction-boundary timing | 01.1, 03.1 | COVERED |
| CONTEXT | D-08 | Complete guest state and fresh binding | 02.1, 03.2 | COVERED |
| CONTEXT | D-09 | Original guest/qualified oracle/control | 01.1, 03 | COVERED |
| CONTEXT | D-10 | Isolated/interleaved/concurrent/cold/failure | 02 | COVERED |
| CONTEXT | D-11 | Actual toolchains/tools and truthful limits | 02.2, 04 | COVERED |
| CONTEXT | D-12 | Rejection leaves requirements pending and blocks admission | All rejection rules, 04 | COVERED |

Deferred context and later-phase requirements are excluded, not gaps. No source item above is missing. Outcomes remain unimplemented/unverified.

## Edge Probe — Seven Rows

| Requirement | Engine category | Disposition | Predicate or flagged assumption | Plan |
|---|---|---|---|---|
| CPU-01 | concurrency | resolved / explicit | Independent generation directories; interrupted output cannot admit success | 01 truth/audit controls |
| CPU-02 | unclassified | unresolved / flagged | EDGE-CPU02: concrete concurrency/failure cases do not imply exhaustive engine classification | 02 |
| CPU-03 | unclassified | unresolved / flagged | EDGE-CPU03: exact timing tests define supported claim; engine supplied no category | 03 |
| CPU-04 | unclassified | unresolved / flagged | EDGE-CPU04: inventory/continuation tests do not imply exhaustive engine classification | 03 |
| CPU-05 | adjacency | resolved / explicit | Exact inclusive cap allowed; one-over any cap rejects | 04 truth/controls |
| CPU-05 | empty | resolved / explicit | Missing/empty/null/stale/contradictory evidence cannot admit | 04 truth/controls |
| CPU-05 | ordering | resolved / explicit | Input permutation yields stable normalized decision ordered by case/lane/identity | 04 truth/controls |

Accounting: 7 applicable = 4 resolved predicates lifted as plain must_haves.truths + 3 explicit flagged assumptions. Zero dismissed/dropped. No backstop was needed. These flags remove no concrete requirement.

## Two-Stage Prohibition Recall

| Requirement | Stage 1 raw candidates considered | Stage 2 precision |
|---|---|---|
| CPU-01 | Wrong pin/file/digest/generator, stale output, wrong closure, lost notice, proprietary input, host call, privacy leak | Routine audit concerns; rights/privacy/host constraints already explicit in AGENTS/D-04/D-05 and enforced by 01/04 |
| CPU-02 | Shared context, TLS routing, crossover, lazy race, warm-only test, leak, teardown, serialization, identical guests, hidden failure | Routine ownership/correctness or explicit forbidden workarounds; covered by 02 |
| CPU-03 | Zero execution, overflow, reset duplication, hidden overshoot, STOP progress, IRQ, wrong frame, stale jump, broad claim, oracle laundering | Behavioral edges covered by 03; honest claims and ancestry already explicit in D-07/D-09 |
| CPU-04 | Missing fields, pointers, callbacks, jump target, raw layout, non-atomic restore, unobserved pending state, same-instance proof, compatibility claim, lifetime | Routine safety covered by 03; public compatibility exclusion explicit in D-08 |
| CPU-05 | Empty ledger, reordered decision, exact cap, lost attempt, reset effort, stale green, absent review, hidden denominator, relaxed cap, rejection-as-complete | Reducer edges covered by 04; transparency/budget/admission intent explicit in D-02/D-11/D-12 |

Generic memory/resource/input security is canon-owned by native threat models and secure-phase review, not minted as a new prohibition. No novel bespoke omission survives precision. Installed probe-core `projectProhibitions([])` returned `[]`, authored in each plan. No check descriptor is fabricated or surfaced prohibition auto-dismissed. Existing rights/privacy/provenance/honest-claim constraints retain concrete tasks and independent review.

## Dependency Graph

| Task | Needs | Creates/refines | Checkpoint |
|---|---|---|---|
| 01-01-01 | Pinned research/manuals | Frozen contract and complete real guest path | None; freeze commit precedes adaptation |
| 01-01-02 | Guest/pristine identities | Reproducible closure/budget controls | None |
| 01-02-01 | Explicit instance path | Isolation/cold proof and state ledger | None |
| 01-02-02 | Ownership/callbacks | Fault cleanup and actual instrumentation | None |
| 01-03-01 | Safe independent execution | Timing/exception boundaries | None |
| 01-03-02 | Boundaries/state ledger | Complete fresh-instance continuation | None |
| 01-04-01 | All mandatory cases | Current normalized evidence | None; review-pending cannot admit |
| 01-04-02 | Current source/evidence | Independent review and decision | None; authorized agent review |

Waves 1 → 2 → 3 → 4 serialize shared adapter/CMake/evidence ownership. Rejected candidates do not satisfy dependencies.
