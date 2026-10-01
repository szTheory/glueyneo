# Phase 1: CPU acceptance experiment - Context

**Gathered:** 2026-10-01
**Status:** Ready for planning
**Mode:** Automatic continuation from new-project; choices below are agent recommendations under the supplied brief's standing authorization, not individual user answers.

<domain>
## Phase Boundary

Qualify a reproducible C 68000 backend by executing a tiny real guest with demonstrated instance independence, complete backend state handling, host safety and explicit timing limits. CPU-01–CPU-05 define acceptance. This is a private feasibility harness; the native public API, board diagnostic SDK and release qualification follow in Phases 2–3. No backend has been accepted.
</domain>

<decisions>
## Implementation Decisions

IDs below are local to Phase 1; preparation D-01–D-44 remain separate historical provenance.

### Bounded candidate experiment

- **D-01:** Investigate Musashi at `313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd` as one candidate. Do not implement multiple production backends or an all-new CPU during this phase. Failure produces a counterexample and replacement/replanning decision.
- **D-02:** Allow at most two substantive adaptation attempts. The planner must inspect the source and set an explicit numeric budget for changed handwritten upstream files/lines, account separately for reproducible generated output, and record stopping/repair rules **before any adaptation**. Acceptance is bounded by both attempts and that patch budget. An exceeded cap is a reported rejection/replan condition, not permission to expand silently.
- **D-03:** Keep the experiment private and reviewable. Use enough CMake/CTest scaffolding and original guest input to reproduce results; do not freeze a public ABI, implement future devices, or turn the experiment into a full emulator fork.

### Compiled closure and host safety

- **D-04:** Prefer a demonstrated minimal 68000 source closure. Inventory every copied, generated, compiled and distributed file at its immutable identity, including generator provenance. Prove FPU/SoftFloat exclusion if claimed; build flags or unused runtime paths alone are insufficient. If any files remain, document their actual notices, obligations and host-call disposition before admission.
- **D-05:** Retain all applicable notices and document small upstream patches. The experimental runtime must remain C and cannot call process exit, perform ambient file/device/network/environment I/O, or use wall clock for guest execution. Dependency guest errors must return bounded observations/errors to the harness without terminating its host.
- **D-06:** Inventory every mutable global, lazy-initialized table, callback, counter, exception field and host jump buffer. A context copy, global current-instance pointer, thread-local current-instance workaround or global execution lock does not fulfill the opaque independent-instance direction. Shared tables must be immutable with safe construction; per-machine mutation belongs to an explicit instance.

### Observable timing and continuation

- **D-07:** Start with a qualified instruction-boundary execution contract, reporting actual guest progress and any overshoot. Include the selected interrupt/exception and stop/resume cases needed for the tiny guest experiment. Do not imply arbitrary bus-cycle suspension, Neo Geo board accuracy or original BIOS compatibility from CPU cycle totals.
- **D-08:** Capture and restore all mutable **backend guest** state at defined supported boundaries, then compare uninterrupted and restored execution/observations. Host pointers, callback identities and jump buffers are rebound or reconstructed; they are not serialized guest data. This remains a private experimental representation, without a public snapshot/ABI compatibility promise.

### Acceptance evidence and failure disposition

- **D-09:** Use a small original, redistributable guest and hand-justified expectations from exact CPU primary references. Include meaningful guest-computed memory/register effects and a consequential wrong-behavior control. Emulator agreement retains its ancestry and does not replace the independent oracle. Full board bootstrap/BSS evidence belongs to Phase 2; CPU reset/startup assumptions used here must still be explicit.
- **D-10:** Compare distinguishable isolated, interleaved and concurrent instances, simultaneous cold initialization and failing creation/teardown paths. Compare guest state/observations at equal boundaries. Audit plus supported race/safety instrumentation and meaningful behavioral stress provide separate evidence; unavailable tools must be recorded honestly.
- **D-11:** Begin on the available native toolchain and run useful additional toolchains when available. Record exact compiler/configuration/architecture identities and unsupported/skipped outcomes. This experiment does not establish the release platform matrix. Keep host threading/test mechanisms outside the all-C runtime's host-independent contract.
- **D-12:** Acceptance requires CPU-01–CPU-04 evidence and CPU-05's documented decision. A rejection satisfies only the decision obligation. Preserve failures and counterexamples; do not weaken isolation/timing/rights requirements, regenerate goldens, or claim Phase 1 complete to enable Phase 2. Reconcile any necessary scope change explicitly with the roadmap.

### Agent's Discretion

The brief delegates routine technical choices. The researcher/planner chooses the finite numeric patch budget from inspected source, private harness structure, exact instruction cases, field encoding and fault injection strategy. Those choices must implement the decisions above and remain testable within the recorded cap. No external credentials or physical hardware are prerequisites for this local experiment; unavailable physical evidence narrows its claim.
</decisions>

<canonical_refs>
## Canonical References

Downstream agents must read the current scope and the relevant source-qualified evidence before planning or implementation.

### Current contracts

- `AGENTS.md` — engineering, public hygiene, autonomy and evidence rules.
- `.planning/PROJECT.md` — current v0.1 scope, all-C/ownership constraints and next milestone.
- `.planning/REQUIREMENTS.md` — CPU-01–CPU-05; Phase 2 isolation requirements must not be mistaken for already verified behavior.
- `.planning/ROADMAP.md` — Phase 1 acceptance and Phase 2 admission gate.
- `.planning/config.json` — installed OpenGSD runtime/workflow configuration.

### Research and dated provenance

- `.planning/research/STACK.md` — exact candidate, source-closure/FPU/SoftFloat and build findings.
- `.planning/research/ARCHITECTURE.md` — explicit contexts, timing, complete mutable state and host boundaries.
- `.planning/research/PITFALLS.md` — P1–P4 admission and oracle failures, with recovery rules.
- `.planning/research/SUMMARY.md` — cross-report implications and unresolved gates.
- `.planning/preparation/BRIEF.md` — original task, authorized automatic defaults and first-deliverable intent.
- `.planning/preparation/DECISIONS.md` — D-04, D-07–D-17, D-21–D-24, D-27–D-33 and reopening conditions.
- `.planning/preparation/C-CORE-ARCHITECTURE.md` — timing/device boundaries, integer rules, state and actual consumer contracts.
- `.planning/preparation/NEOGEO-HARDWARE-AND-ECOSYSTEM.md` — CPU primary-source ledger and source/oracle ancestry.
- `.planning/preparation/ROADMAP-SEED.md` — bounded feasibility experiment and CPU-only alpha boundary.
- `.planning/preparation/ADVERSARIAL-REVIEW.md` — A-02 global/init/host-state risk and preserved implementation gates.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- MIT license, ignore rules, preparation and current planning documents exist.
- No runtime code, dependency checkout, build system, test harness, diagnostic binary or codebase map exists yet.

### Established Patterns

- Original runtime work is C17 with target-scoped CMake/CTest and test-only pinned Unity as adopted defaults.
- Planning is tracked on `chore/initialize-project`; phase branches and review are configured. No remote repository or hosted checks are configured.
- Existing research contains candidate evidence; it cannot substitute for a runnable experiment.

### Integration Points

- The experiment should expose a private adapter boundary suitable for later native API integration without committing that ABI now.
- Future source/package/license inventories and original fixture manifests should reuse the experiment's immutable provenance.
</code_context>

<specifics>
## Specific Ideas

Compare two guests with distinguishable state and bus results so accidental cross-instance callbacks or shared counters are observable. Test cold initialization from a fresh process, including concurrent creation, instead of relying solely on warm sequential instances. Track generated opcode provenance and keep failure output free of personal paths and private media.
</specifics>

<deferred>
## Deferred Ideas

- Public native SDK lifecycle/media API, full board diagnostic/bootstrap and installed consumers — Phase 2.
- Release platform matrix, protected hosted delivery, release-please and downloadable alpha — Phase 3.
- Z80/YM2610 implementation, selected graphics/input/audio, real RetroArch macOS, public snapshot continuation and durable persistence — next milestone.
- Commercial BIOS/game compatibility and representative gameplay optimization — later evidence-driven milestones.
</deferred>

---
*Phase: 01-cpu-acceptance-experiment*
*Context gathered: 2026-10-01, automatic single pass.*
