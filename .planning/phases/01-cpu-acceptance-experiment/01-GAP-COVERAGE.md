# Phase 01 owned-core gap plan coverage — 2026-10-02

This covers plans 01-07–01-14 after the 2026-10-02 owner-directed review/repair and evidence/seal splits. Existing plans 01-01–01-06 are complete historical work and are not rewritten. Current CONTEXT owns direction. Historical RESEARCH/PATTERNS/VALIDATION predate it, and their empty-tree and Musashi-only assumptions are superseded by actual source and current contracts. Existing candidate receipts remain rejected; this audit describes proposed work, not acceptance.

## Scope and discovery

Canonical ROADMAP story already validates syntactically after 01-05; 01-07 preserves and checks it. The historical verifier's preflight refusal/0-of-5 score is not a current failed CPU behavior count. Requirement reconciliation is planned execution in 01-07, not a planning-time rewrite. Requirements remain CPU-01–05 with exact diagnostic scope, pending replacement admission and Phase02 gate.

Discovery uses current source/fixture/manual evidence, not a new package choice. Motorola UM ninth edition1993 was retrieved from https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf on2026-10-02; it identifies CPU reset, exception and section8 MC68000 timing, not board fidelity. PRM https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf could not be fetched in this planning run; existing original ORACLE cites edition/pages, and implementation must retrieve/verify those instruction semantics before coding. A failed retrieval establishes no new PRM qualification. https://github.com/SingleStepTests/m68000 was inspected2026-10-02 and explicitly describes MAME microcoded generation; importing it is not planned. No copyrighted manual text/assets are copied.

Calibration query: factor1, appliedfalse, sample_count0, confidencelow; plans emit raw projection unchanged. Eight gap-closure plans use explicit dependencies. Each task modifies at most five paths; Plan 01-12 caps its plan-wide source/test repair tranche at fourteen paths, Plan 01-13 owns inventory/presets/fresh runs, and Plan 01-14 owns final review and sealing. No graph/project skill artifact or new runtime dependency is assumed.

## Multi-source coverage audit

| Source | ID | Required outcome/constraint | New plan | Status |
|---|---|---|---|---|
| GOAL | story | Reproducible accepted CPU foundation with independent instances/state/timing | 07–14 | COVERED |
| GOAL | SC1 | Exact C build, copied/generated/compiled/distributed rights and host-call closure | 07,08,10,12,13,14 | COVERED |
| GOAL | SC2 | Distinct/cold/failing instance behavior, host survival | 08,10 | COVERED |
| GOAL | SC3 | Actual bounded progress, named stops/IRQ/exception limits | 08,09 | COVERED |
| GOAL | SC4 | Complete state inventory and true fresh continuation | 10,11 | COVERED |
| GOAL | SC5 | Bounded budget, repair reserve and independent current decision/replanning | 07,08,12,13,14 | COVERED |
| REQ | CPU-01 | Exact authored-source closure and build/provenance/FPU disposition | 07,08,10,12,13,14 | COVERED |
| REQ | CPU-02 | Independent/cold/concurrent/fault-safe lifecycle | 08,10,11,12,13,14 | COVERED |
| REQ | CPU-03 | Progress, explicit supported precision and selected IRQ/exception behavior | 07,08,09,11,12,13,14 | COVERED |
| REQ | CPU-04 | Complete owned state/callback inventory and continuation | 07,10,11,12,13,14 | COVERED |
| REQ | CPU-05 | Historical frozen rejection plus separate authored finite-budget decision | 07–14 | COVERED |
| RESEARCH | source pin/closure | Exact identities/notices, immutable history, actual compiled C closure | 07,08,12,13,14 | COVERED |
| RESEARCH | original adaptation budget | Preserve all two consumed attempts/charges; no imported-core repair | 07,12 | COVERED |
| RESEARCH | context/host calls | Explicit owner throughout call graph, no ambient machine/host state | 08,10,11,12 | COVERED |
| RESEARCH | generator/FPU | Small deterministic build; demonstrate absent generator/FPU/SoftFloat | 07,08,12,13,14 | COVERED; original regeneration protocol remains historical only |
| RESEARCH | complete state | Every mutable field/callback, destination rebinding, no raw struct dumps | 10,11,12,14 | COVERED |
| RESEARCH | timing limits | Signed request/zero/reset/STOP/overshoot, actual boundaries | 08,09,12,14 | COVERED; Musashi IRQ coalescing is not inherited |
| RESEARCH | selected exceptions | IRQ/RTE/TRAP/illegal/privilege/address error, unsupported bus-error | 09,10,11,14 | COVERED |
| RESEARCH | faults | Nested failures, allocation/teardown/reentry host safety | 08,09,10,14 | COVERED |
| RESEARCH | oracles | Original bytes/manual expectations, wrong-behavior controls, ancestry | 08,09,11,12,14 | COVERED |
| RESEARCH | isolation/stress | Isolated/interleaved/concurrent/cold, consequential ownership | 10,12,14 | COVERED |
| RESEARCH | evidence | Actual tools/instrumentation/case counts, distinct outcomes, current review | 10,12,13,14 | COVERED |
| RESEARCH | native threats | Guest/callback/state/evidence boundaries and mitigations | All eight | COVERED |
| CONTEXT | P01-C-01 | Owned C17 core and exact diagnostic first | 07,08 | COVERED |
| CONTEXT | P01-C-02 | Old candidate rejected and charges/caps immutable | 07,12,13,14 | COVERED |
| CONTEXT | P01-C-03 | Imported core only if proven material bounded advantage | 07.1,12.2 | COVERED; reconsideration trigger, no default adoption |
| CONTEXT | P01-C-04 | Runtime C17, flat dependencies, no plugin/framework | 07,08,10,12 | COVERED |
| CONTEXT | P01-C-05 | Private explicit-instance lifecycle/run/IRQ/bus/error seam | 07,08,10,11 | COVERED |
| CONTEXT | P01-C-06 | Whole-core/fresh distinct fixtures, separated evidence claims | 07,08,09,10 | COVERED; optional comparison not required |
| CONTEXT | P01-C-07 | No mixed handlers or live state conversion | 07,08,11 | COVERED |
| CONTEXT | P01-C-08 | Static whole-component selection; no shipping-traffic fiction | 07,08,12,14 | COVERED |
| CONTEXT | P01-C-09 | Exact subset and explicit unsupported instruction status | 07,08,09,12 | COVERED |
| CONTEXT | P01-C-10 | Concrete register/EA/exception boundaries, defined integers, no generator/JIT | 07,08,09,10,11 | COVERED |
| CONTEXT | P01-C-11 | Original independently justified manual expectations | 07,08,09,11,12 | COVERED |
| CONTEXT | P01-C-12 | Emulator ancestry/board-capture limitations | 07,09,12,13,14 | COVERED |

Deferred commercial games, full machine/video/audio, public plugin/snapshot/state compatibility, live conversion and unprofiled optimization are excluded, not unplanned gaps. No current required source item is missing.

## Dependency graph and ownership

| Plan | Needs | Produces/refines | Wave |
|---|---|---|---|
| 07 | Completed06/current direction and historical receipt | Reconciled canonical contract and distinct fixed budget | 7 |
| 08 | Frozen07 plus remaining first-gate allowance | Original diagnostic tracer/decode boundaries and measured gate | 8 |
| 09 | Passing08 and budget | Named exception/IRQ/timing/bus cases | 9 |
| 10 |09 supported behavior | Consequential isolation/fault cases and complete inventory | 10 |
| 11 |10 inventory/host safety | Atomic private codec and fresh continuation | 11 |
| 12 |All required cases/current identities | Independent implementation review and bounded regression-backed repairs | 12 |
| 13 |Reviewed/repaired Plan 12 revision | Source/rights inventory, CMake presets and fresh execution evidence | 13 |
| 14 |Current Plan 13 evidence | Independent final review, narrow evidence-tool repair and bounded disposition | 14 |

No parallel runtime editing lane is promised because shared implementation/build ownership is real. Plan 01-12's independent reviewer owns the initial REVIEW.md; separate fixers address findings in a fourteen-path tranche with per-task ownership. Plan 01-13 owns source identity and fresh evidence; Plan 01-14 independently reviews the final revision and seals the disposition. Missing gates or a hard effort limit stop dependent work with GAPS_FOUND, not an automatic backend rejection. The proposed 32-hour active-effort cap includes all agents/review/fixes; the separate eight-hour diagnostic gate starts with the first owned runtime or behavioral-test change. The 6,000/8,000-line churn thresholds pause work for review; they are not correctness caps or reasons to discard a repairable finding. A tooling halt does not consume an attempt. These remain proposed resource guardrails, not feasibility estimates.

## Contribution receipts

The API-coverage detector's earlier hit on “CPU API” was a false positive: Phase 1 uses a first-party private in-process seam, not an external API/SDK/service. The installed gate is retained for later external integration such as libretro; classify future detector hits against that exact scope instead of disabling the gate project-wide. Its earlier receipt predates plans 01-13 and 01-14 and is not current validation.

Assumption-delta scan01 returned detectedfalse/signals[] before and after the earlier plan set. Nonetheless CPU backend is the substantive transition: **promote** the owned-core direction in active contracts, retain Musashi as rejected historical evidence rather than add-alongside selectable backends. No optional/required or derived/chosen switch is introduced. Plan 07 records that resolution.

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

## Additive F14-03 coverage — Plan 01-15

This section preserves every earlier row. Plans 01-07–01-14 are completed
receipts, not current acceptance. The 2026-10-01 VERIFICATION preflight gaps
are historical: Plan 01-05 corrected the canonical story and explicitly
rejected/deferred Musashi. Latest STATE/CONTEXT/01-14 evidence identifies only
F14-03 as the active blocker. No fresh phase verification is claimed here;
RESEARCH/PATTERNS/VALIDATION remain superseded where their earlier assumptions
conflict with current source and decisions.

Plan 01-15 targets the canonical ILLEGAL saved-PC discrepancy without choosing
its behavior during planning. It has five sequential tasks, explicitly
authorized by the orchestrator to keep one focused gap plan and at most five
modified paths per task: source interpretation/tracer; contract/freeze
supersession; conditional direct behavioral reconciliation; dependent identity
and qualification refresh; independent review and seal. Conditional ownership
is explicit. All artifacts are reachable from existing guest fixtures,
contract validators, inventory tooling and collector; no new framework,
external API/service, schema or platform is introduced. Installed calibration
reports factor 1, applied false, sample_count 0, confidence low; raw/calibrated
projection is 44,000 tokens for five tasks. No implementation tests or runtime
changes were made during planning.

| Source | ID | Current required outcome/constraint | Plan/task | Status |
|---|---|---|---|---|
| GOAL | story/SC1–SC5 | Reproducible bounded CPU evidence with explicit source, state, isolation and timing limits | Existing 07–14 plus 15.1–15.5 narrowly reconcile F14-03 | COVERED; no admission claim |
| REQ | CPU-01 | Exact changed source/tool/report closure and historical provenance | 15.2,15.4,15.5; retained 07–14 receipts | COVERED; Pending |
| REQ | CPU-02 | Retain independent-instance/cold/fault evidence; requalify affected runtime identity | 15.3–15.5; retained 10–14 receipts | COVERED; Pending |
| REQ | CPU-03 | Precisely justified ILLEGAL frame rule, bounded event and direct control | 15.1,15.3–15.5 | COVERED; Pending |
| REQ | CPU-04 | Preserve state ownership/inventory; refresh private identity and continuation if runtime changes | 15.3–15.5; retained 10–14 receipts | COVERED; Pending |
| REQ | CPU-05 | Append-only effort/churn, unchanged freeze/caps, repair or explicit unresolved decision | 15.2,15.4,15.5 | COVERED; Pending |
| RESEARCH | source/closure, original budgets, mutable state, timing/exception, oracles and evidence | Applicable constraints remain in completed 07–14; exact source interpretation and affected identity refresh added | 15.1–15.5 | COVERED; obsolete Musashi-only/empty-tree proposals are superseded, not new work |
| CONTEXT | P01-C-01,P01-C-02 | Owned diagnostic scope and frozen consumed Musashi accounting | 15.2,15.4,15.5 | COVERED |
| CONTEXT | P01-C-03,P01-C-04 | No unapproved imported replacement, C17 and small dependencies | 15.2,15.3 | COVERED; no adoption/install |
| CONTEXT | P01-C-05,P01-C-06 | Private instance seam and distinct fresh fixture/claim boundaries | 15.3,15.4 | COVERED |
| CONTEXT | P01-C-07,P01-C-08 | Whole static CPU, no mixed handlers/live conversion | 15.3 | COVERED |
| CONTEXT | P01-C-09,P01-C-10 | Exact supported diagnostic behavior and concrete architecture | 15.2,15.3 | COVERED |
| CONTEXT | P01-C-11,P01-C-12 | Exact primary-source rule and honest correlated-oracle/hardware limits | 15.1,15.3–15.5 | COVERED |
| CONTEXT | current handoff F14-03 | Resolve primary-source/contract discrepancy or retain HIGH/open with exact evidence need | 15.1–15.5 | COVERED |

The unchanged frozen `code_start.contract_sha256` currently gates budget
validation against active CONTRACT bytes. Plan 15.2 therefore requires a
separate validated append-only supersession chain rooted in preserved original
bytes before changing canonical wording; it never replaces the code-start
identity or pretends a post-implementation change happened before the freeze.
Runtime repair is conditional on the primary-source result. Exact affected
private state/header, inventory, manifest, review and collection identities
must be refreshed, preserving all prior evidence. Ambiguous sources leave the
finding HIGH/open and GAPS_FOUND; no silicon claim or physical capture is
invented. Resource thresholds pause repair/replanning and establish no CPU
correctness verdict.

### Spec-less probe accounting

No Phase 01 SPEC Edge Coverage/Prohibitions exists. The current requirement-text
probe supplied applicable=9, resolved=0, unresolved=9. All nine rows are
authored verbatim in intent as `must_haves.flagged_assumptions` in Plan 01-15;
none is dismissed, resolved via backstop, or converted into a fabricated
acceptance criterion:

| Requirement | Shape | Disposition |
|---|---|---|
| CPU-01 | concurrency | flagged unresolved |
| CPU-02 | unclassified | flagged unresolved |
| CPU-03 | unclassified | flagged unresolved |
| CPU-04 | unclassified | flagged unresolved |
| CPU-05 | boundary | flagged unresolved |
| CPU-05 | adjacency | flagged unresolved |
| CPU-05 | empty | flagged unresolved |
| CPU-05 | ordering | flagged unresolved |
| CPU-05 | precision | flagged unresolved |

No-silent-drop equality: nine surfaced = nine flagged assumptions + zero new
resolved predicates. These flags do not expand this gap beyond F14-03 or
qualify the pending CPU requirements. Prohibition recall keeps no new item:
commercial-media redistribution and unsupported silicon/performance/ABI claims
are already forbidden by current canonical decisions; ordinary security
constraints are owned by the concrete STRIDE register. Existing no-external-API
coverage declaration remains valid for the first-party private in-process CPU
seam. Assumption-delta detected=false; no schema paths/push task; ASVS L1 is a
workflow level, not native-C certification. Deferred ideas remain excluded.
