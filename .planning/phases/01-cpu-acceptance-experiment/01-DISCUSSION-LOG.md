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
