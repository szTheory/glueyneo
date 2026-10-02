# Phase 01 owned-core gap plan coverage — 2026-10-02

This covers new plans 01-07–01-12. Existing plans 01-01–01-06 are complete historical work and are not rewritten. Current CONTEXT owns direction. Historical RESEARCH/PATTERNS/VALIDATION predate it, and their empty-tree and Musashi-only assumptions are superseded by actual source and current contracts. Existing candidate receipts remain rejected; this audit describes proposed work, not acceptance.

## Scope and discovery

Canonical ROADMAP story already validates syntactically after 01-05; 01-07 preserves and checks it. The historical verifier's preflight refusal/0-of-5 score is not a current failed CPU behavior count. Requirement reconciliation is planned execution in 01-07, not a planning-time rewrite. Requirements remain CPU-01–05 with exact diagnostic scope, pending replacement admission and Phase02 gate.

Discovery uses current source/fixture/manual evidence, not a new package choice. Motorola UM ninth edition1993 was retrieved from https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf on2026-10-02; it identifies CPU reset, exception and section8 MC68000 timing, not board fidelity. PRM https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf could not be fetched in this planning run; existing original ORACLE cites edition/pages, and implementation must retrieve/verify those instruction semantics before coding. A failed retrieval establishes no new PRM qualification. https://github.com/SingleStepTests/m68000 was inspected2026-10-02 and explicitly describes MAME microcoded generation; importing it is not planned. No copyrighted manual text/assets are copied.

Calibration query: factor1, appliedfalse, sample_count0, confidencelow; plans emit raw projection unchanged. Six new plans each contain two tasks; no task modifies more than five files. Required dependencies serialize shared cpu.c/CMake/inventory ownership. No graph/project skill artifact or new runtime dependency is assumed.

## Multi-source coverage audit

| Source | ID | Required outcome/constraint | New plan | Status |
|---|---|---|---|---|
| GOAL | story | Reproducible accepted CPU foundation with independent instances/state/timing | 07–12 | COVERED |
| GOAL | SC1 | Exact C build, copied/generated/compiled/distributed rights and host-call closure | 07,08,10,12 | COVERED |
| GOAL | SC2 | Distinct/cold/failing instance behavior, host survival | 08,10 | COVERED |
| GOAL | SC3 | Actual bounded progress, named stops/IRQ/exception limits | 08,09 | COVERED |
| GOAL | SC4 | Complete state inventory and true fresh continuation | 10,11 | COVERED |
| GOAL | SC5 | Fixed budget and independent current decision/replanning | 07,08,12 | COVERED |
| REQ | CPU-01 | Exact authored-source closure and build/provenance/FPU disposition | 07,08,10,12 | COVERED |
| REQ | CPU-02 | Independent/cold/concurrent/fault-safe lifecycle | 08,10,11,12 | COVERED |
| REQ | CPU-03 | Progress, explicit supported precision and selected IRQ/exception behavior | 07,08,09,11,12 | COVERED |
| REQ | CPU-04 | Complete owned state/callback inventory and continuation | 07,10,11,12 | COVERED |
| REQ | CPU-05 | Historical frozen rejection plus separate authored finite-budget decision | 07–12 | COVERED |
| RESEARCH | source pin/closure | Exact identities/notices, immutable history, actual compiled C closure | 07,08,12 | COVERED |
| RESEARCH | original adaptation budget | Preserve all two consumed attempts/charges; no imported-core repair | 07,12 | COVERED |
| RESEARCH | context/host calls | Explicit owner throughout call graph, no ambient machine/host state | 08,10,11,12 | COVERED |
| RESEARCH | generator/FPU | Small deterministic build; demonstrate absent generator/FPU/SoftFloat | 07,08,12 | COVERED; original regeneration protocol remains historical only |
| RESEARCH | complete state | Every mutable field/callback, destination rebinding, no raw struct dumps | 10,11,12 | COVERED |
| RESEARCH | timing limits | Signed request/zero/reset/STOP/overshoot, actual boundaries | 08,09,12 | COVERED; Musashi IRQ coalescing is not inherited |
| RESEARCH | selected exceptions | IRQ/RTE/TRAP/illegal/privilege/address error, unsupported bus-error | 09,10,11 | COVERED |
| RESEARCH | faults | Nested failures, allocation/teardown/reentry host safety | 08,09,10 | COVERED |
| RESEARCH | oracles | Original bytes/manual expectations, wrong-behavior controls, ancestry | 08,09,11,12 | COVERED |
| RESEARCH | isolation/stress | Isolated/interleaved/concurrent/cold, consequential ownership | 10,12 | COVERED |
| RESEARCH | evidence | Actual tools/instrumentation/case counts, distinct outcomes, current review | 10,12 | COVERED |
| RESEARCH | native threats | Guest/callback/state/evidence boundaries and mitigations | All six | COVERED |
| CONTEXT | D-01 | Owned C17 core and exact diagnostic first | 07,08 | COVERED |
| CONTEXT | D-02 | Old candidate rejected and charges/caps immutable | 07,12 | COVERED |
| CONTEXT | D-03 | Imported core only if proven material bounded advantage | 07.1,12.2 | COVERED; reconsideration trigger, no default adoption |
| CONTEXT | D-04 | Runtime C17, flat dependencies, no plugin/framework | 07,08,10,12 | COVERED |
| CONTEXT | D-05 | Private explicit-instance lifecycle/run/IRQ/bus/error seam | 07,08,10,11 | COVERED |
| CONTEXT | D-06 | Whole-core/fresh distinct fixtures, separated evidence claims | 07,08,09,10 | COVERED; optional comparison not required |
| CONTEXT | D-07 | No mixed handlers or live state conversion | 07,08,11 | COVERED |
| CONTEXT | D-08 | Static whole-component selection; no shipping-traffic fiction | 07,08,12 | COVERED |
| CONTEXT | D-09 | Exact subset and explicit unsupported instruction status | 07,08,09,12 | COVERED |
| CONTEXT | D-10 | Concrete register/EA/exception boundaries, defined integers, no generator/JIT | 07,08,09,10,11 | COVERED |
| CONTEXT | D-11 | Original independently justified manual expectations | 07,08,09,11,12 | COVERED |
| CONTEXT | D-12 | Emulator ancestry/board-capture limitations | 07,09,12 | COVERED |

Deferred commercial games, full machine/video/audio, public plugin/snapshot/state compatibility, live conversion and unprofiled optimization are excluded, not unplanned gaps. No current required source item is missing.

## Dependency graph and ownership

| Plan | Needs | Produces/refines | Wave |
|---|---|---|---|
| 07 | Completed06/current direction and historical receipt | Reconciled canonical contract and distinct fixed budget | 7 |
| 08 | Frozen07 plus remaining first-gate allowance | Original diagnostic tracer/decode boundaries and measured gate | 8 |
| 09 | Passing08 and budget | Named exception/IRQ/timing/bus cases | 9 |
| 10 |09 supported behavior | Consequential isolation/fault cases and complete inventory | 10 |
| 11 |10 inventory/host safety | Atomic private codec and fresh continuation | 11 |
| 12 |All required cases/current identities | Fresh collector/provenance, independent review and decision | 12 |

No parallel runtime editing lane is promised because shared implementation/build ownership is real. Independent review in12 has sole REVIEW.md ownership and reads current exact source; it cannot silently fix or erase blockers. Missing gate or budget exhaustion stops dependent plans. Finite32-hour active effort includes every concurrent agent/reviewer, with8-hour first diagnostic gate,6,000 cumulative runtime churn and8,000 test/tool churn. Numbers are proposed caps, not proven feasibility estimates.

## Contribution receipts

Deterministic API detector ran on the concatenated six new plans: detectedtrue solely for “CPU API” in a read-first instruction. This is a false positive for a first-party private in-process seam, with no third-party service/API integration. COVERAGE.md carries the reasoned no-external-API declaration; no fabricated coverage rows.

Assumption-delta scan01 returned detectedfalse/signals[] before and after plans. Nonetheless CPU backend is the substantive transition: **promote** the owned-core direction in active contracts, retain Musashi as rejected historical evidence rather than add-alongside selectable backends. No optional/required or derived/chosen switch is introduced. 07.2 records that resolution.

Schema inspection scanned new plans for schema.prisma/drizzle/SQL/models.py/schema.rb: no matches. Planned paths contain C, CMake, Python tests/tools and evidence Markdown/JSON only; no ORM schema or schema push task.

Security config is enabled, ASVS-level1, block_onhigh. Every plan has a concrete native trust-boundary register; level labels do not imply native CPU ASVS certification. No npm/pip/cargo install task, so no package-legitimacy checkpoint is invented.

## Synthesized role and adversarial decisions

| Lens/decision | Recommendation and benefit | Strongest alternative/cost | Failure evidence or revisit trigger |
|---|---|---|---|
| Hardware/oracle | Exact original manual-derived subset and separate architecture/bus/cycle claims | Full pin-cycle MC68000 model costs breadth and independent hardware work | A required diagnostic effect depends on unknown prefetch/board timing; stop and replan |
| C architecture/maintainer | Owned concrete per-instance modules, no generator/runtime dep | Audited imported core could deliver broader instructions sooner but carries hidden state/closure | Bounded source review proves material benefit; discussion required before adoption |
| Host/memory/state | Defined unsigned arithmetic, checked bus, terminal faults, named record codec | Raw context copy is fast but leaks hidden state/pointers and padding | Boundary/sanitizer/omission counterexample blocks admission |
| Determinism/performance | Instruction events and descriptive measured diagnostic costs | Optimized/JIT engine has platform and equivalence burden | Representative later profiles justify optimization; current correctness first |
| Integration/product/docs | Private whole-CPU seam, exact unsupported status and truthful subset | General plugin or runtime selector adds ABI/state policy without an admitted consumer | Actual second consumer need; no speculative framework |
| Build/release/license | Own-source C17 closure, pinned test-only Unity, exercised configs only | Copying code reduces effort only with pin/license/update and test duty | Missing notice/toolchain/instrumentation/source identity blocks acceptance |
| Testing/adversarial | Consequential wrong behavior/ownership/state and stale/empty/cap controls | Shared-emulator vectors find disagreement but can confirm common bugs | Correlated ancestry, untested boundaries, weak control, false-green exit or uncounted work rejects |

Confidence is bounded: private seam/scope follows accepted direction; correctness, portability, source size and32-hour feasibility remain unmeasured. No “perfect one-shot” certainty is asserted. Tests/builds/implementation were not run during planning.
