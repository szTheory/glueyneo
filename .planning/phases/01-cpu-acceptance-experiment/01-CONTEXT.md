# Phase 1: CPU acceptance experiment - Context

**Gathered:** 2026-10-02
**Status:** Developer approved the owned C-core direction for gap-closure planning; backend implementation is not accepted.

Stable Phase 01 decision references remain `P01-C-##`; bold `D1-##` labels are aliases for the installed GSD decision-coverage parser only. `P01-R-##` refers to dated Phase 1 research decisions; `PREP-D-##` refers to the project preparation register.

<domain>
## Phase Boundary

Phase 01 remains the CPU acceptance experiment. Its declared goal is reproducible acceptance of a C 68000 backend before SDK integration. It is still open / GAPS_FOUND: the current pinned Musashi candidate is rejected/deferred, CPU-01–04 remain Pending, CPU-05's bounded-decision obligation is complete, and Phase 02 remains gated.

The developer approved the owned C17-core direction behind a private whole-CPU seam, beginning with the exact v0.1 diagnostic subset and expanding only after evidence, for gap-closure planning. This is an architecture and planning decision; it does not accept an implementation, revise canonical requirements or the roadmap, change the experiment caps, or authorize source work. The gap plan must explicitly reconcile the candidate-specific CPU-01–04 obligations and define a separate, bounded development budget while preserving all consumed Musashi charges.

This context supersedes the earlier Musashi-only implementation preference where it conflicts with the direction below. The earlier experiment, source identities, failures, and accounting remain historical evidence in the linked receipts and summaries.

## Current Phase Handoff — 2026-10-03

Plans 01–14 are executed. Gap-closure Plans 01-15 and 01-16 are planned and have passed the independent plan, requirement and decision-coverage gates. Phase 01 itself remains open / GAPS_FOUND; CPU-01–05 remain Pending, and Phase 02 is gated. The next command is `$gsd-execute-phase 01 --gaps-only`, which runs only Plans 01-15 and 01-16 in dependency order. Phase verification remains a separate later step.

Plan 01-14's F14-03 remains HIGH/open: frozen `experiments/owned_cpu/CONTRACT.md:61` specifies ILLEGAL saving next PC, while `experiments/owned_cpu/cpu.c`, `experiments/owned_cpu/SUBSET.md`, `tests/owned_cpu/ORACLE.md` and `tests/owned_cpu/test_timing.c` exercise the faulting PC. The independent review cites the Motorola User Manual §§6.2.4–6.2.5, §6.3.7 and Programmer's Reference Manual ILLEGAL entry; it concludes that the specific wording is unresolved. This is a contract/evidence discrepancy, not a demonstrated silicon or C defect. Plans 01-15 and 01-16 now order primary-source adjudication, only-justified direct repair, dependent qualification and independent review. Preserve all prior receipts and hashes; if primary evidence remains ambiguous, leave F14-03 HIGH/open and the result unqualified. After execution, fresh phase verification must separately assess CPU-01–05.

Read `experiments/owned_cpu/REVIEW.md`, `experiments/owned_cpu/ACCEPTANCE.md`, `experiments/owned_cpu/acceptance-results.json`, `.planning/phases/01-cpu-acceptance-experiment/01-14-SUMMARY.md` and Plans 01-15/01-16 for exact findings, identities, outcomes and budget. This dated handoff supplements the 2026-10-02 planning context; it does not change the phase contract, declare F14-03 resolved, or accept the backend.

</domain>

<decisions>
## Implementation Decisions

### Backend ownership and evidence boundary

- **D1-01:** (stable reference P01-C-01). For the replacement direction, build an owned C17 CPU core behind the private whole-CPU seam, starting with the exact v0.1 diagnostic subset and expanding only after evidence. The developer approved this direction for planning because correctness and ownership outweigh the apparent speed of building on a questionable foundation, while delivery efficiency remains a goal. This does not claim all third-party code is flawed or that a future implementation is accepted.
- **D1-02:** (stable reference P01-C-02). The current pinned Musashi candidate remains rejected/deferred. Its two substantive adaptation attempts and all recorded charges/caps remain unchanged. No third adaptation, refund, or cap increase is authorized. Any later repair or replacement work needs a distinct plan and explicit budget.
- **D1-03:** (stable reference P01-C-03). Reconsider an imported CPU core only if a bounded source review shows a material correctness or delivery advantage that justifies its full code, build, license, provenance, and maintenance costs. Rocket68 is a possible comparison reference, not an approved dependency: its upstream project describes itself as early and lists tests from Musashi and the MAME-derived m68000 corpus.
- **D1-04:** (stable reference P01-C-04). Keep the runtime C17 and dependency tree small. Do not introduce a public CPU plugin ABI, dynamic loader, C++ runtime engine, or generic backend framework as part of this decision.

### Replacement boundary and incremental migration

- **D1-05:** (stable reference P01-C-05). Put any future CPU implementation behind a thin private per-instance boundary covering lifecycle/reset, bounded execution, interrupt input, bus access, explicit result/error reporting, and test-only observation. The existing experimental cpu_instance adapter shows a useful boundary shape, but it embeds Musashi-specific state and is not accepted production code.
- **D1-06:** (stable reference P01-C-06). If two implementations are compared, replace the whole CPU backend at that boundary. Start each run from equivalent fresh guest state and separate mutable memory/bus fixtures, then compare architectural observations and ordered bus effects at named instruction boundaries. Measure cycle counts and bus traces as separate claims.
- **D1-07:** (stable reference P01-C-07). Do not mix opcode handlers from two engines or live-swap opaque CPU state. Prefetch, exceptions, interrupts, bus order, and internal state cross instruction boundaries; state conversion would be its own compatibility contract and is not needed to learn whether a new core is correct.
- **D1-08:** (stable reference P01-C-08). “Strangler-style” applies here as a seam for replacing the complete CPU component, not routing production traffic: Glueyneo has no qualified shipping backend yet. Keep backend choice static per test/build unless later evidence justifies a runtime selector.

### Scope and correctness

- **D1-09:** (stable reference P01-C-09). The project's v0.1 contract is an original deterministic CPU/bus diagnostic with an exact supported subset; it does not promise a full game-ready 68000 or full Neo Geo emulation. Recommend starting with a named diagnostic instruction/exception/timing contract and reporting every unsupported instruction explicitly. Never silently treat unsupported opcodes as NOPs.
- **D1-10:** (stable reference P01-C-10). Preserve an architecture that can grow toward broader MC68000 coverage: clear register/flag rules, effective-address behavior, exception/interrupt paths, explicit byte order, bounded bus access, and instruction-family tests. Build vertical slices; do not add a generator, micro-op framework, JIT, or hot-path optimization before representative evidence makes its value clear.
- **D1-11:** (stable reference P01-C-11). Use the Motorola MC68000 manuals and original, independently justified guest expectations for documented CPU behavior. The existing original guest demonstrates a small starting slice (MOVEQ, ADDQ.L, MOVE.L, STOP, reset vectors, and selected IRQ/exception cases); it does not prove complete coverage or hardware behavior.
- **D1-12:** (stable reference P01-C-12). Treat Musashi, MAME, Rocket68, and emulator-generated corpora as useful for finding disagreements, with source and test ancestry recorded. Agreement among implementations with shared ancestry is not an independent oracle. Where feasible, add board captures only with exact board/revision/setup provenance; CPU manuals alone do not establish Neo Geo board timing.

### Decisions the gap plan must make explicit before implementation

1. Define the exact instruction, addressing-mode, reset, interrupt, exception, and timing cases required to run and qualify the v0.1 diagnostic. The first implementation slice is the named diagnostic subset, not broader MC68000 coverage.
2. Reconcile CPU-01–04 with the owned implementation: source/build provenance, per-instance behavior, bounded progress, complete private mutable-state inventory, continuation, and supported-boundary limits need measurable acceptance criteria.
3. Set a new development budget and stop/review rule independently from the exhausted Musashi adaptation budget. Estimate and measure the first vertical slice before expanding coverage.
4. Decide whether a source-only, time-bounded screen of another core would materially improve correctness or delivery. Do not adopt Rocket68 or another library by default; preserve the approved owned-core path unless evidence justifies changing it.
5. Before a later phase verification, preserve the CPU admission gaps as pending until current evidence supports each requirement. The earlier MVP story-format blocker was corrected in Plan 01-05; F14-03 is the current HIGH/open evidence discrepancy.

### the agent's Discretion

Recommend concrete module boundaries, test organization, supported-opcode reporting shape, and instrumentation during research/planning, provided they remain private, C17, explicitly bounded, and consistent with the acceptance requirements. Report unsupported or unknown behavior honestly. Do not expand the runtime dependency tree without showing a concrete correctness or maintenance advantage.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Current project contracts and workflow
- AGENTS.md — C17, ownership, host isolation, evidence, dependency, and delivery constraints.
- .planning/PROJECT.md — v0.1 scope; diagnostic subset; C17 and no speculative frameworks.
- .planning/REQUIREMENTS.md — CPU-01–05 and Phase 02 admission gate.
- .planning/ROADMAP.md — Phase 01 goal and current open/GAPS_FOUND status.
- .planning/METHODOLOGY.md — breadth, adversarial review, synthesis, and dependency tradeoff method.
- .planning/STATE.md — current workflow position, frozen accounting, and next-step pause.

### CPU decision and evidence
- .planning/phases/01-cpu-acceptance-experiment/01-05-SUMMARY.md — current rejection and finding disposition.
- .planning/phases/01-cpu-acceptance-experiment/01-06-DIRECTION.md — developer selected backend-replanning discussion and authorization boundary.
- .planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md — prior preflight refusal, CPU admission gaps, and separate MVP format blocker.
- .planning/phases/01-cpu-acceptance-experiment/01-REVIEW.md — independent phase-source review.
- experiments/cpu/ACCEPTANCE.md, experiments/cpu/REVIEW.md, and experiments/cpu/budget-ledger.json — current candidate disposition, blockers, and frozen effort/patch accounting.
- experiments/owned_cpu/ACCEPTANCE.md, REVIEW.md, acceptance-results.json, source-manifest.json, and budget-ledger.json — current owned-core decision, independent findings, exact evidence identities, source closure and accounting.
- .planning/phases/01-cpu-acceptance-experiment/01-12-SUMMARY.md, 01-13-SUMMARY.md, and 01-14-SUMMARY.md — state review/fix, fresh qualification, and final independent decision.
- third_party/musashi/PROVENANCE.md — exact local source provenance; upstream descriptions do not establish local qualification.

### Existing experimental shape and independent fixture
- experiments/cpu/cpu_adapter.h and experiments/cpu/cpu_adapter.c — private cpu_instance, bus, bounded run, IRQ, observation, and private state-codec shape; implementation is Musashi-specific.
- experiments/cpu/state-inventory.json — the current candidate's mutable-state and callback inventory; not a future core inventory.
- tests/cpu/ORACLE.md and tests/cpu/guest_fixture.c — original diagnostic expectations and their Motorola manual ancestry.

### Research and preparation
- .planning/research/STACK.md — backend candidates, build/source closure, and dependency findings.
- .planning/research/ARCHITECTURE.md — instance ownership, timing, host boundary, and continuation constraints.
- .planning/research/PITFALLS.md — correlated oracles, undefined behavior, state, and admission traps.
- .planning/preparation/NEOGEO-HARDWARE-AND-ECOSYSTEM.md — primary-source ledger, hardware evidence limits, and candidate research.
- .planning/preparation/DECISIONS.md — durable project decision provenance and reopening conditions.

### Primary and candidate sources
- [Motorola M68000 User Manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) — reset, bus, interrupt/exception behavior, and timing tables; primary CPU documentation, not Neo Geo board evidence.
- [Motorola M68000 Programmer's Reference Manual](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf) — instruction behavior and encodings.
- [Musashi upstream](https://github.com/kstenerud/Musashi) — upstream C 680x0 core description and MIT notice; not proof of the local fork's safety or fit.
- [SingleStepTests m68000](https://github.com/SingleStepTests/m68000) — useful vectors, explicitly generated from MAME's microcoded core.
- [Rocket68 upstream](https://github.com/habedi/rocket68) — possible C11 comparison candidate; upstream labels itself early and lists tests from Musashi and m68000.
- [Martin Fowler's Strangler Fig description](https://martinfowler.com/bliki/StranglerFigApplication.html) — gradual whole-component replacement pattern; transfer is limited because Glueyneo has no qualified production backend or live traffic.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- experiments/cpu/cpu_adapter.h: an opaque per-instance handle with explicit bus callbacks, lifecycle/reset, bounded run result, IRQ input, and private inspection/state calls. Reuse the stable conceptual seam, not the embedded Musashi context, raw state layout, or claim of acceptance.
- tests/cpu/guest_fixture.c and tests/cpu/ORACLE.md: original MIT fixture with manual-derived register/store assertions and a negative control; a useful first vertical slice.
- Existing CMake/CTest and pinned Unity setup under experiments/cpu/ and third_party/unity/: research/planning can assess which parts remain useful after the backend changes.

### Established Patterns
- Keep runtime and chosen runtime dependencies in C17; opaque instance owns all mutable state; host callbacks and memory are explicit; deterministic guest cycles are separate from host pacing.
- Original fixture inputs and their oracle ancestry are recorded. Keep test results tied to exact binary, source, toolchain, configuration, and fixture identity.
- The current candidate's prior runtime passes are historical and do not override the six open source blockers or prove a new implementation.

### Integration Points
- A replacement core connects to the private CPU boundary and the machine bus, before public SDK API and board devices are finalized.
- Future SDK integration remains gated on a newly reconciled and accepted CPU contract; no backend-specific private state becomes a public snapshot or persistence format.

</code_context>

<specifics>
## Specific Ideas

The developer wants to build as much of the emulator as practical, especially where reuse would create a flawed foundation, while preserving correctness and efficient delivery. A strangler-style migration is welcome. The developer approved planning an owned C17 core behind a thin private whole-CPU seam, starting with an explicit SDK-diagnostic slice and expanding after measured evidence. This is not implementation authorization or a backend acceptance claim.

</specifics>

<deferred>
## Deferred Ideas

- Full commercial-game compatibility and full Neo Geo MVS/AES machine support remain outside v0.1.
- Public CPU plugin ABI, dynamically loadable CPU engines, public snapshots, live CPU-state conversion, JIT, and optimizations without representative profiles remain deferred.

</deferred>

---

*Phase: 01-cpu-acceptance-experiment*
*Context gathered: 2026-10-02*
