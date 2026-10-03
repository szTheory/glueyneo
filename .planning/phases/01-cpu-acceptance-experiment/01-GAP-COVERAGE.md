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

## F14-03 Final Plan Set — 2026-10-03

The preceding Plan 01-15 task/file counts and five-task mapping are a preserved
planning snapshot, superseded by the final two-plan split below. The split
responds to independent plan-check scope feedback while retaining the same
single F14-03 issue, exact-source decision, no-admission outcome and nine
unresolved assumption flags. No runtime, tests, source evidence, or phase
verification were executed during this planning revision.

| Plan | Wave/dependency | Current bounded scope | Files/tasks | Gap disposition |
|---|---|---|---|---|
| 01-15 | Wave 15; depends on 01-14 | Primary-source/errata interpretation, reversible contract reconciliation, and conditional direct ILLEGAL fixture/runtime correction | 9 files; 2 tasks; no task exceeds 5 paths | Resolved only with source support; otherwise exact HIGH/open evidence need |
| 01-16 | Wave 16; depends on 01-15 | Refresh affected state/source identity, collect bounded lanes, independent REVIEW-only review, final rebind and honest seal | 6 files; 3 tasks; no task exceeds 5 paths | May seal only the supported bounded result; unresolved source stays unqualified/GAPS_FOUND |

Both plans are additive and `gap_closure: true`; `$gsd-execute-phase 01
--gaps-only` therefore targets this two-plan closure after planning gates pass.
Plan 01-15 owns the decision and any direct behavior repair. Plan 01-16 owns
dependent qualification and review; the independent reviewer edits only
`experiments/owned_cpu/REVIEW.md` and binds its disposition to the final exact
closure. `budget-ledger.json` remains append-only across the ordered plans.
No plan marks CPU-01–05 complete, closes Phase 01, or opens Phase 02.

## P01-C-14 Additive Gap Plans — 2026-10-03

Current CONTEXT/ROADMAP and owned-core source govern this four-plan addition.
RESEARCH/PATTERNS/VALIDATION predate P01-C-14; their Musashi/empty-tree and
canonical-ILLEGAL qualification statements are dated provenance, not the active
candidate claim. Historical preflight was not a behavioral failure count.
Plans 01-01–01-17 and all summaries/adjudication/source receipts remain unchanged.
Plan 01-17 has a checkpoint summary and is not scheduled for another acquisition.
P01-C-14 supplies the separate owner decision; P01-C-13 still preserves unknown
original-silicon saved PC. Planning itself executes no native test or qualification.

| Source | ID | Required outcome/constraint | Plan/task | Status |
|---|---|---|---|---|
| GOAL | story/SC1 | Reproducible C candidate and rights/source closure | 18.2,20.1–2,21.1–3 | COVERED; admission pending |
| GOAL | SC2 | Distinct isolated/interleaved/concurrent/cold/fault-safe owners | Retained 08–14 cases,19.1,20.2,21.1 | COVERED; fresh qualification planned |
| GOAL | SC3 | Actual bounded progress and retained exception/timing limits | 18.1,19.1–2,20.2,21.1–2 | COVERED |
| GOAL | SC4 | Complete private state and fresh-owner continuation | 18.1,19.1,20.2,21.1 | COVERED |
| GOAL | SC5 | Frozen resource gates, independent evidence/review/decision | 18.2,19.3,20.2,21.1–3 | COVERED; Pending |
| REQ | CPU-01 | Exact C17 source/build/notice/host-call closure | 18.2,19.3,20.1–2,21 | COVERED; Pending |
| REQ | CPU-02 | Independent instances/cold/failing lifecycle against isolated baselines | 19.1,20.2,21.1–2 plus retained tests | COVERED; Pending |
| REQ | CPU-03 | Exact unsupported and retained selected event semantics | 18.1,19.1–2,20.2,21.1–2 | COVERED; Pending |
| REQ | CPU-04 | Inventory/private identity and actual fresh continuation | 18.1,19.1,20.2,21.1–2 | COVERED; Pending |
| REQ | CPU-05 | Unchanged active effort/churn, actual outcomes and honest closeout | 18.2,19.3,20.2,21.3 | COVERED; Pending |
| RESEARCH | pin/source/rights/host closure | Owned authored closure and pinned Unity, no runtime dependency install | 18.1,20.1–2,21.1–2 | COVERED; obsolete Musashi implementation is historical |
| RESEARCH | mutable/callback state and stress | Explicit owners, cold/concurrent/fault and fresh continuation | 19.1,20.2,21.1 | COVERED; existing cases retained |
| RESEARCH | timing/exceptions/faults | Whole-event bounded time, retained IRQ/TRAP/privilege/address-error/RTE | 18.1,19.1,20.2,21.1–2 | COVERED; exact 4AFC qualification superseded by P01-C-14 |
| RESEARCH | oracle and negative controls | Manual/fixture ancestry and exact consequential rejection control | 18.1,19.2–3,20.2,21.1 | COVERED |
| RESEARCH | evidence/budgets/security | Exact profile/receipt histories, resource enforcement and native high blocking | 18.2,19.3,20,21 | COVERED |
| CONTEXT | D1-01/P01-C-01 | Owned C17 diagnostic whole core | 18.1,20.2,21.1 | COVERED |
| CONTEXT | D1-02/P01-C-02 | Preserve consumed Musashi attempts and frozen charges/caps | 18.1–2,20.2,21.3 | COVERED |
| CONTEXT | D1-03/P01-C-03 | No unapproved imported-core adoption | 18.1,21.1 | COVERED; no comparison/adoption added |
| CONTEXT | D1-04/P01-C-04 | C17, small tree, no public plugin ABI/framework | 18.1,19.2,20.1,21.1 | COVERED |
| CONTEXT | D1-05/P01-C-05 | Private explicit per-instance result and state boundary | 18.1,19.1,21.1 | COVERED |
| CONTEXT | D1-06/P01-C-06 | Fresh equivalent guests/owners and separate architectural/cycle/trace claims | 19.1,20.2,21.1 | COVERED |
| CONTEXT | D1-07/P01-C-07 | No mixed opcode engines/live-state conversion | 18.1,21.1 | COVERED |
| CONTEXT | D1-08/P01-C-08 | Static whole backend, no shipping selection claim | 18.1,21.1 | COVERED |
| CONTEXT | D1-09/P01-C-09 | Exact diagnostic subset and explicit unsupported result | 18.1–2,19,20.1–2 | COVERED |
| CONTEXT | D1-10/P01-C-10 | Concrete architecture/selected behavior, no speculative engine framework | 18.1,19.1,21.1 | COVERED |
| CONTEXT | D1-11/P01-C-11 | Primary manual/original guest scope, no full coverage inference | 18.1,19.3,20.1,21.1 | COVERED |
| CONTEXT | D1-12/P01-C-12 | Correlated emulator ancestry is not hardware authority | 18.1,19.3,20.1,21.1 | COVERED |
| CONTEXT | D1-13/P01-C-13 | Original silicon PC remains unknown; exhausted search not repeated | All four, especially18/21 | COVERED; superseded only for candidate boundary |
| CONTEXT | D1-14/P01-C-14 | Only exact4AFC excluded; zero vector/frame/dispatch/cycles, retained others | 18.1–2,19,20,21 | COVERED |

### Dependency/ownership and sizing

| Plan | Wave/needs | Produces | Tasks/max paths per task | Checkpoint |
|---|---|---|---|---|
| 01-18 | 18;01-17 evidence/answered separate claim | Runnable tracer and frozen-root additive candidate amendment | 2/5 | None; P01-C-14 already selected |
| 01-19 | 19;01-18 private behavior/amendment | Semantics/continuation/control and receipt/review policy | 3/4 | None |
| 01-20 | 20;01-19 current evidence profile | Current report/closure and fresh native receipt | 2/3 | None |
| 01-21 | 21;01-20 exact qualification | Non-author source review, separate security assessment and deferred seal | 3/3 | None; genuine independent gates |

Serial ordering follows shared evidence/ledger/source coupling, not arbitrary
chaining. Reviewer owns REVIEW only; separate assessor owns SECURITY/VALIDATION;
executor owns ledger/result writes and cannot overwrite independent judgments.
Calibration returned factor1, appliedfalse, sample_count0, confidencelow.
Four plans instead of the coarse default avoid tasks exceeding five paths and
separate actual qualification from its independent judgments. Discovery is
existing-source pattern confirmation with no new package/architecture research.

### Edge-probe and hook accounting

All nine supplied rows are copied as unresolved flagged assumptions in 01-18
must_haves: CPU-01 concurrency; CPU-02/03/04 unclassified; CPU-05 boundary,
adjacency, empty, ordering, precision. Applicable9=unresolved9+resolved0;
unclassified3. No new acceptance predicate is invented for these flags.
Ordinary direct candidate tests implement P01-C-14, not automatic probe resolution.

No external API integration: this scope is the existing private in-process C
core and local harness. Preserve COVERAGE.md's declaration; SDK/API prose does
not introduce an external vendor capability. Core/backend identity: no-change;
historical Plan01-17 “additional applicable original-MC68000 evidence” explains
the pluralization false positive. No platform/backend/tenant/truth authority,
ORM/schema work, UI, new dependency or public ABI enters the plan set.

### Limits and exact historical protection

CONTRACT.md stays byte-identical at original code_start digest. The existing
reconciliation's frozen_contract archive and every old key/value remain intact;
an additive candidate_contract_amendments array records only authorized scope
supersession, not a silicon decision or pre-freeze rewrite. New receipts use an
explicit current profile and amendment digest; old collections retain their
own denominator/profile and bytes. Plan01-17 evidence/adjudication/summary are
read-only. F14-03/T-01-15-03 stay HIGH/open during planning and until actual
reconciliation, fresh qualification, independent review and security gates pass.
Deferred-admission sealing keeps CPU-01–05 Pending, Phase01 open/GAPS_FOUND and
Phase02 gated even if the candidate discrepancy is later dispositioned. A
separate current phase-goal verification is required. Deferred context ideas
and later-phase work remain excluded, not missing source items.

All nine previously unresolved spec-less probe rows remain unresolved and
flagged. Their meaning and evidence need are unchanged; duplicating flags in
the dependent plan does not add criteria or resolve any row. Historical Plan
01-15 versions remain in Git as provenance; this table is the active plan-set
mapping.

## Later independent review reconciliation — Plans 01-22–01-25

Planning inspection on 2026-10-03 confirms the canonical ROADMAP story passes
the installed grammar validator. The current Plan21 receipt is an exact deferred
seal at931e2f0 with five collections, unchanged included source hashes,
unqualified disposition and only phase-goal-verification-pending. Plan21's
derived-record recovery succeeded; its earlier transient T-01-43 failure is not
an unimplemented repair. UAT records39/39 passed and no new UAT issue.

However, the later independent `01-REVIEW.md`, reviewed at2e237a73 at21:34:39Z,
supplies additional concrete counterexamples outside that earlier clean scope.
Current source inspection confirms their cited conditions remain: state_valid
unconditionally rejects odd PC/active stack although supported RTE/SR switching
can produce ready deferred-fault boundaries (CR-01); validate_budget does not
check cumulative category monotonicity (CR-02); budget_check excludes exact
frozen limits that canonical validation permits (WR-01); README says no owned
runtime exists and lists completed work as upcoming (WR-02). No test or new
behavioral reproducer was run during this planning. Prior passing receipts and
UAT are retained as evidence for their actual coverage and cannot dismiss these
later counterexamples. This is concrete repair/evidence work, not a filler plan
to rerun phase verification.

### Current role synthesis and adversarial outcome

Reuse the context's hardware, ownership, deterministic time, maintenance,
resource, evidence and product lenses. The recommended continuation repair
preserves reachable guest state and lets the subsequent existing execution
path handle the deferred fault; a narrower continuation claim would abandon
the current contract and was rejected. Monotonic category enforcement protects
all failed/reverted work; merely checking final totals cannot protect a ledger
with decreases. Inclusive frozen limits remove an unintended stricter seal
policy without raising a cap. A new explicit evidence profile protects older
denominators while identifying expanded coverage. Independent reproduction
and review are necessary because both previous reviewers and the test matrix
missed these boundaries. Documentation distinguishes implementation from
admission. No package choice, hardware search, ISA expansion, public ABI,
platform claim or new architecture is reopened. Original0x4AFC silicon saved
PC stays unknown; exact candidate exclusion and all other selected exception
interactions remain. Confidence in repair disposition awaits execution and
independent reassessment; source inspection alone is not a repair result.

### Four-source coverage audit

| Source | ID | Required outcome/constraint | Plan/task | Status |
|---|---|---|---|---|
| GOAL | story/SC1 | Reproducible C closure and source/rights evidence | Retained07–21;23.2,24.1–2,25 | COVERED; grammar valid, admission pending |
| GOAL | SC2 | Independent instances and safe explicit host ownership | Retained10–21;22.1,24.2,25.1–2 | COVERED; old and fresh owners distinguishable |
| GOAL | SC3 | Actual bounded execution with selected event/fault timing | Retained09–21;22.1,24.1–2,25.1–2 | COVERED; no silicon restart inference |
| GOAL | SC4 | Complete state inventory and actual fresh continuation | 22.1–2,24.1–2,25.1–2 | COVERED; reachable deferred-fault boundary repaired |
| GOAL | SC5 | Frozen resources, independent review and reproducible decision | 23.1–2,24.2,25.1–3 | COVERED; phase verification remains separate |
| REQ | CPU-01 | Exact source/build/license/host closure | 23.2,24.1–2,25.1–3 | COVERED; Pending |
| REQ | CPU-02 | Independent lifecycle/ownership/baselines | 22.1,24.2,25.1–2; retained isolation/cold/fault cases | COVERED; Pending |
| REQ | CPU-03 | Supported progress/stop/exception/fault semantics | 22.1,24.1–2,25.1–2 | COVERED; Pending |
| REQ | CPU-04 | Complete private state and fresh-owner continuation | 22.1–2,24.1–2,25.1–2 | COVERED; Pending |
| REQ | CPU-05 | Cumulative no-refund resource gates and bounded decision | 23.1–2,24.2,25.1–3 | COVERED; Pending |
| RESEARCH | source/rights/closure | Current owned authored C17 closure; historical imported proposals superseded | Retained07–21;24.1–2,25.1 | COVERED; no new research/install |
| RESEARCH | instance/state/callback inventory | Explicit independent owners and actual continuation | 22.1–2,24.1–2,25.1–2 | COVERED |
| RESEARCH | timing/exceptions/oracle ancestry | Existing exact selected events, bounded functional bus observations and manual limits | 22.1,24.1–2,25.1–2 | COVERED; original silicon unknown |
| RESEARCH | evidence/security/resources | Nonempty exact evidence, preserved history, independent high-blocking review and limits | 22.2,23.1–2,24.2,25 | COVERED |
| CONTEXT | D1-01/P01-C-01 | Owned diagnostic core | 22.1,24.1,25.1 | COVERED |
| CONTEXT | D1-02/P01-C-02 | Frozen consumed Musashi attempts and no refunds/cap increase | 22.1,23.1,24.2,25.3 | COVERED |
| CONTEXT | D1-03/P01-C-03 | No imported core adoption without separate decision | 23.2,25.1 | COVERED; no adoption |
| CONTEXT | D1-04/P01-C-04 | C17, small tree, no public plugin/framework | 23.2,24.1,25.1 | COVERED |
| CONTEXT | D1-05/P01-C-05 | Private explicit per-instance seam | 22.1,25.1 | COVERED |
| CONTEXT | D1-06/P01-C-06 | Separate fresh guests/owners and architectural/bus/cycle observations | 22.1,24.2,25.1 | COVERED |
| CONTEXT | D1-07/P01-C-07 | No mixed engines/live conversion | 23.2,25.1 | COVERED |
| CONTEXT | D1-08/P01-C-08 | Static whole backend | 23.2,25.1 | COVERED |
| CONTEXT | D1-09/P01-C-09 | Exact diagnostic supported scope and unsupported status | 22.1,24.1,25.1 | COVERED |
| CONTEXT | D1-10/P01-C-10 | Concrete architecture and incremental evidenced growth | 22.1,25.1 | COVERED |
| CONTEXT | D1-11/P01-C-11 | Primary/manual and original guest expectations | 24.1,25.1 | COVERED |
| CONTEXT | D1-12/P01-C-12 | Correlated emulator output is not hardware truth | 24.1,25.1 | COVERED |
| CONTEXT | D1-13/P01-C-13 | Unknown silicon saved PC; exhausted search unrepeated | 22.1,23.2,24.1,25.1–3 | COVERED |
| CONTEXT | D1-14/P01-C-14 | Exact0x4AFC candidate-only exclusion; retained other events | 22.1–2,23.2,24.1–2,25.1–3 | COVERED |
| LATER REVIEW | CR-01 | Reachable odd-PC/stack continuation | 22.1–2,24.1–2,25.1–3 | COVERED; repair not yet executed |
| LATER REVIEW | CR-02 | Nondecreasing cumulative category enforcement | 23.1,25.1–3 | COVERED; repair not yet executed |
| LATER REVIEW | WR-01 | Inclusive frozen limits and pause rejection | 23.2,25.1–3 | COVERED; repair not yet executed |
| LATER REVIEW | WR-02 | Accurate implementation/admission status | 23.2,25.1 | COVERED; repair not yet executed |

No applicable source item is omitted. Deferred context ideas and requirements
assigned to later phases remain excluded. Nine historical specless flags remain
unresolved: CPU-01 concurrency; CPU-02/03/04 unclassified; CPU-05 boundary,
adjacency, empty, ordering and precision. New targeted tests are explicit
current-contract defect regressions, not an automatic resolution of those flags.

### Dependency, ownership and estimates

| Plan | Wave/dependency | Creates for next plan | Tasks/max modified paths per task | Estimate raw/calibrated |
|---|---|---|---|---|
| 01-22 | 22;01-21 | Repaired continuation and distinct profile; preserved legacy parsing | 2/4 | 24000/24000 |
| 01-23 | 23;01-22 | Monotonic/inclusive resource gates and current README | 2/4 | 20000/20000 |
| 01-24 | 24;01-23 | Exact repaired closure and appended native qualification | 2/5 | 18000/18000 |
| 01-25 | 25;01-24 | Independent later-finding/security dispositions and deferred seal | 3/3 | 26000/26000 |

Serial waves follow real acceptance.py/ledger/source coupling; no same-wave
file conflict exists. Reviewer owns both review reports only, separate assessor
owns SECURITY/VALIDATION, executor owns receipts/accounting. Calibration factor1,
appliedfalse, sample_count0, confidencelow applies to every plan. No external
API/SDK integration, new schema, UI or dependency enters scope. Existing C17,
CTest/Unity, Python controls, collector and inventory commands supply direct
checks; no scaffolding-only wave is invented. Discovery remains Level0 current
pattern confirmation; --gaps skips research. Project skill directories are
absent and graphify is disabled. All command paths are checkout-relative.

These additive plans keep all previous plans/summaries and unknown hardware
adjudication unchanged. Planning ran no runtime/test qualification and changed
no source or real receipt. After plan checks, the execution command is
`$gsd-execute-phase 01 --gaps-only` for Plans22–25. Only after clean executed
repair/qualification/review/security may the next separate step be
`$gsd-verify-work 01`. Phase01 remains incomplete/GAPS_FOUND and CPU-01–05 Pending;
the historical verifier is not silently replaced by planning or passing UAT.
