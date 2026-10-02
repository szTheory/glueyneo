# Phase 1: CPU acceptance experiment - Discussion Log

> Audit trail only. Downstream agents consume CONTEXT.md, not this log.

**Date:** 2026-10-01
**Mode:** `--auto`, continued from new-project
**Areas discussed:** Bounded candidate experiment; compiled closure and host safety; observable timing and continuation; acceptance evidence and failure disposition.

No questions were presented to the user. The brief already authorized recommended defaults. The selections below record agent choices and their rationale, not fabricated user responses.

## Bounded Candidate Experiment

| Option | Description | Selected |
|--------|-------------|----------|
| One bounded candidate experiment | Begin with the research pin; cap adaptation attempts and require a quantified patch budget before edits | Yes, recommended |
| Parallel backend implementations | Build several alternatives before choosing | No |

**Automatic selection:** One candidate, at most two substantive adaptation attempts. The planner quantifies the upstream patch budget after source inspection and before execution.
**Rationale:** Measures the uncertain adaptation cost while keeping a failed experiment actionable. The pure-C and instance contracts remain fixed.

## Compiled Closure and Host Safety

| Option | Description | Selected |
|--------|-------------|----------|
| Proven minimal 68000 closure | Establish exact included files/notices/host calls; prove exclusions | Yes, recommended |
| Retain the broader engine | Audit and safely adapt every retained FPU/SoftFloat path | Conditional only if explicitly justified within budget |

**Automatic selection:** Prefer the minimal proven closure. A candidate is not accepted merely because its repository advertises a permissive license or a build flag disables use of some instructions.
**Rationale:** Research found unconditional FPU inclusion, a SoftFloat dependency with separate terms and process-level host error paths.

## Observable Timing and Continuation

| Option | Description | Selected |
|--------|-------------|----------|
| Measured instruction-boundary contract | Bound calls, report actual cycles/overshoot and qualify selected interrupt/exception cases | Yes, recommended |
| Full bus-cycle suspension first | Require finer scheduling before any SDK progress | No; later precision follows hardware requirements |

**Automatic selection:** Instruction-boundary execution with explicit limitations, plus complete private backend continuation at supported boundaries.
**Rationale:** This establishes a truthful CPU foundation without equating aggregate cycles to physical bus timing or promising a board snapshot format.

## Acceptance Evidence and Failure Disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Evidence gates with explicit rejection | Original guest assertions, isolated/concurrent/cold-init/failure evidence, retained counterexamples | Yes, recommended |
| Continue adaptation without a fixed stopping rule | Expand work until the candidate appears usable | No |

**Automatic selection:** All required backend gates must pass within the recorded budget; rejection or deferral cannot complete Phase 1 or admit SDK integration.
**Rationale:** CPU-05's decision evidence is distinct from CPU-01–CPU-04's successful qualification.

## Agent's Discretion

The user delegated recommendations in the supplied brief. Exact numeric patch budget, private harness layout, instruction cases and fault injection are delegated to focused research/planning within the chosen boundaries. Missing test tooling is reported rather than represented as passing.

## Deferred Ideas

Public SDK API and board diagnostic, package/release qualification, full sound/video devices, frontend qualification, public snapshots/persistence and commercial-game behavior retain their roadmap phases/milestones. No new feature scope was added.

---

## Backend replanning discussion — 2026-10-02

**Areas discussed:** CPU backend ownership, private replacement seam, supported diagnostic scope, correctness evidence and delivery risk.

### CPU backend ownership

| Option | Description | User direction |
| --- | --- | --- |
| Repair pinned Musashi | Mature C core with a narrower known blocker list, but existing two adaptation attempts are consumed and new work needs a separate budget. | Not selected; current candidate remains rejected/deferred. |
| Use another imported C core | Could reduce implementation time, but introduces new source, license, integration and qualification work. Rocket68 describes itself as early and lists tests from Musashi and MAME-derived m68000 vectors. | Kept as a bounded comparison only if it offers clear evidence-based value; not adopted. |
| Build an owned C core | More source and semantic control with a smaller runtime dependency tree; carries the highest correctness and development burden. | Developer leans toward this, prioritizing correctness and efficiency. Final backend choice is still open. |

### Private replacement seam

| Option | Description | Recommendation |
| --- | --- | --- |
| Whole-core private seam | Select a backend per instance/build; compare separate runs from equivalent initial fixtures. | Recommended. |
| Mixed opcode handling or live state conversion | Split one executing CPU across implementations or translate internal state during operation. | Rejected as high risk: prefetch, exceptions, IRQs, bus ordering and hidden state cross instruction boundaries. |

The repository's existing private adapter is useful as a boundary sketch, but its implementation and serialized test state are Musashi-specific. No public plugin or dynamic loading layer is proposed.

### Supported 68000 scope and delivery risk

| Option | Description | Recommendation |
| --- | --- | --- |
| Full MC68000 before alpha | Broad compatibility target with a large implementation and correctness burden. | Not recommended for the diagnostic SDK alpha. |
| Exact diagnostic subset, then expand | Named instruction, exception, interrupt, and timing behaviors; unsupported operations return explicit errors. | Recommended, subject to reconciling CPU-01–04 before planning. |
| Trust advertised third-party coverage | Faster apparent start but source and correctness claims still require qualification. | Not recommended as an acceptance shortcut. |

### Correctness evidence and test ancestry

Use the NXP-hosted Motorola manuals and original manually justified fixtures for documented behavior. Use emulator-derived vectors to expose disagreements, not to certify hardware truth. Run candidate implementations from equivalent but separately owned state and buses. Compare architectural results, bus traffic, and timing as distinct evidence.

The official Musashi repository describes a C 680x0 engine and includes the MIT license, but those upstream facts do not qualify this repository's pinned fork. The SingleStepTests m68000 corpus says it was generated from MAME's microcoded core; Rocket68 lists tests from Musashi and that corpus. Preserve this oracle ancestry when consuming any vectors. The NXP MC68000 User Manual documents reset, bus, interrupt, exception, and instruction timing behavior, but does not establish Neo Geo board timing.

### Synthesis and open choices

Recommended next planning direction: evaluate an owned C17 CPU implementation behind the private whole-core seam, starting with the exact v0.1 diagnostic contract. Define a separate effort budget and stop/review gate; do not reuse or alter the spent Musashi adaptation caps. First reconcile the old candidate-specific CPU requirements, identify unsupported behavior, and preserve a route toward broader 68000 coverage.

The developer's direction is a preference, not a final backend selection, requirements edit, roadmap rescope, or implementation authorization. The next step remains a separate GSD planning step after review.
