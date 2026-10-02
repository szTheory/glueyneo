# Discussion and decision method

Current user preferences, clarified 2026-10-01. Apply these to each GSD discussion
and substantive decision. Adapt the analysis to the phase and evidence available.

## Workflow and model control

- Pause after each named GSD step: initialization, discuss, plan, execute,
  verify and shipping; also pause before a new phase or milestone.
- State what finished, what remains, and the proposed next step. Let the user
  continue and choose the model before starting that step.
- Do routine work autonomously inside the approved step. A workflow pause is
  not a request to seek permission for every tool call or implementation detail.
- Keep automatic advancement off unless the user explicitly enables it for a
  specified run. Inherit the user-selected session model; do not assume the
  expensive kickoff model should be used throughout the project.

## Breadth, depth and synthesis

For each meaningful decision:

1. State the project goal, decision, constraints, existing commitments and
   evidence gaps. Separate established behavior from proposals.
2. Fan out across the relevant stakeholder and technical roles. For Glueyneo,
   these can include emulator/hardware accuracy, C architecture and ABI,
   memory and host safety, timing/determinism, state and persistence,
   integration/frontend consumers, testing and independent oracles,
   portability/build/release operations, performance, maintainability,
   licensing/supply chain, and product/documentation usability.
3. Examine viable options in depth: pros, cons, concrete examples, tradeoffs,
   failure modes, patterns, antipatterns, best practices, footguns and lessons
   from relevant products and ecosystems. Use independent subagents when they
   add useful perspectives; scope roles to the actual decision.
4. Research online when useful or needed to verify claims. Prefer primary
   documentation, exact revisions and reproducible evidence. Explain transfer
   limits when borrowing lessons from other languages or ecosystems.
5. Run an adversarial pass: challenge assumptions, look for counterexamples,
   hidden costs, trust boundaries, compatibility traps and operational failure.
6. Reconcile conflicts among roles into one coherent recommendation per
   decision, aligned with the project goals. Include the rationale, strongest
   alternative, rejected options, risks, confidence, validation needed and the
   evidence that would change the recommendation. Do not manufacture certainty.
7. Present the decision set together, using a compact comparison matrix when
   helpful. Surface unresolved choices for the user, then pause at the workflow
   boundary instead of automatically launching planning or execution.

For UI/UX work, add relevant design/accessibility roles and examine existing
conventions, least surprise, interaction patterns, consistency, visual hierarchy
and usability. Select rendering, 2D/3D graphics, audio or other specialties only
when the current scope needs them.

## Dependency preference

The user's default is: **another copy and paste can be better than another
dependency**. Favor small, flat dependency trees and concrete code over an
abstraction or package that brings unrelated functionality.

Compare local implementation, a small audited copied/vendored subset, and a
dependency. Count the entire transitive tree, security and update exposure,
build/portability cost, API fit, ownership, testing, license/provenance duties
and long-term maintenance. A dependency is appropriate when its concrete value
justifies those costs. Copied code still needs clear ownership, retained notices,
source identity, applicable tests and an update strategy.

## Evidence-first delivery and bounded repair

- Reach the first useful executable emulator result early. Governance scripts,
  audit dashboards and evidence plumbing must stay proportional to the failure
  they prevent; they do not replace a guest that actually runs.
- Use resource caps for work actually performed, not executor correction counts
  or orchestration retries. Record active effort and code churn from failed and
  reverted work. Do not add a substantive-attempt counter that a tooling halt
  can consume.
- Reserve room inside the approved budget for independent review, targeted
  fixes, regression tests and re-review. A reproducible finding triggers repair
  when it fits the agreed scope and budget. If a resource threshold prevents a
  required fix, pause with the finding open and replan; the threshold alone does
  not establish that the core is defective. Never turn a review finding into an
  automatic pass.
- Behavioral sign-offs name their scope, revision, command and actual test
  counts. A document-only audit may reconcile prior evidence, but it must not
  imply fresh execution. For C undefined-behavior risks, pair UBSan with small
  boundary cases that assert the intended architectural result; exhaustive
  operand enumeration is unnecessary when boundary vectors cover the fault.
- Add fuzz targets when the project has useful hostile-input surfaces such as
  media, state or public call-sequence parsers. Keep C warnings target-scoped,
  disable compiler extensions on owned C targets, and introduce presets/CI
  lanes as configurations become real. When hosted CI exists, use one local
  CI entrypoint and check its workflow parity. Add content scanning before
  public artifacts, and state the scanner's known blind spots.

## Decision namespaces

Use stable prefixes in cross-document references: `PROJECT-D-##` for current
project decisions, `PREP-D-##` for the dated preparation register, `P01-C-##`
for Phase 1 context decisions, and `P01-R-##` for Phase 1 research decisions.
Keep immutable historical receipts intact; add a crosswalk or supersession note
when an old local identifier remains relevant.

## Reusable discussion prompt

> For each decision in this phase, fan out broadly and deeply across the
> stakeholder and specialist roles relevant to Glueyneo and this scope.
> Compare viable options with pros, cons, tradeoffs, examples, patterns,
> antipatterns, best practices, footguns and lessons from other systems.
> Research primary sources and relevant ecosystems where it improves the
> decision. Challenge the options adversarially, reconcile competing concerns,
> and synthesize one clear recommendation per decision with assumptions,
> confidence, risks and validation needs. Favor small, flat dependency trees;
> justify any dependency against an understandable local or copied alternative.
> Keep recommendations coherent with our current project goals and contracts.
> Present the recommendations and unresolved choices, then pause before the
> next GSD step so I can review and change models.
