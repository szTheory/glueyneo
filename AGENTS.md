# Glueyneo working rules

Glueyneo is a portable C Neo Geo MVS/AES emulation core in its initial CPU acceptance experiment; no backend is qualified yet. Begin with .planning/PROJECT.md and STATE.md, then read REQUIREMENTS.md and ROADMAP.md as appropriate. Use .planning/preparation/README.md to find dated evidence and DECISIONS.md for decision provenance; current canonical documents own active scope. Do not treat proposed designs or historical sibling-project receipts as implemented behavior.

## Engineering

- Keep runtime code and selected runtime dependencies in C. C17, target-based CMake, CTest and a small pinned Unity dependency are initial defaults; prove actual platform support.
- Keep the native core independent of frontend, filesystem, audio device, graphics API, network, secrets and wall clock. Use opaque per-instance state and explicit ownership, buffers, errors and deterministic time.
- Audit reused CPU/audio code for every mutable global, callback, initialization race and state field. A context API alone does not establish reentrancy. Keep third-party changes small, pinned, licensed and documented.
- Prefer small, flat dependency trees. For small, understandable functionality, another audited copy or local implementation can be better than another dependency. Add a dependency when its concrete correctness or maintenance value justifies its full transitive tree; retain licenses, provenance and an update/ownership plan for copied code too.
- Prefer simple concrete modules, defined integer behavior, explicit byte order and checked resource limits. Hardware comments should explain evidence and timing. Avoid speculative frameworks and optimizations without representative profiles.
- Distinguish emulated hardware time from host pacing. Preserve original hardware behavior, including slowdown, unless an option explicitly describes a deviation.
- Keep durable saves, emulator snapshots, replay compatibility and public ABI versions separate. Test actual continuation and instance isolation before making those claims.

## Evidence and documentation

- Use primary sources where available. Record exact references, revision/date, supported claim, uncertainty and test-oracle ancestry. A reference emulator's output is not automatically hardware truth.
- Pair a behavioral change with appropriate automated evidence and documentation in the same PR. Use compiled examples, real consumer tests, meaningful boundary tests, properties and fuzz regressions. Keep test cost proportional to fault value.
- Record unsupported/skipped/unknown outcomes explicitly. Do not update goldens, relax budgets or rerun away failures merely to get green CI. Explain intentional baseline changes.
- Keep release and performance claims tied to exact code, dependency, configuration and input identities. Proposed numbers remain targets until measured.
- Keep one current contract per topic. Preserve dated preparation as provenance with supersession links. Update stale instructions and examples when behavior changes.

## Delivery and autonomy

- Use OpenGSD @opengsd/gsd-core and its installed workflow/schema. Preserve .planning/preparation during initialization. Keep a detailed current milestone, outlined next milestone and revisable longer horizon.
- Pause between named GSD workflow steps, including initialization, discuss, plan, execute, verify and shipping, and before advancing to another phase or milestone. Summarize the result and proposed next step, then let the user continue and change models. Do not auto-chain steps unless explicitly authorized for that run.
- At each GSD workflow boundary, identify the exact phase and plan just completed, state whether the phase itself is complete, and give the concrete next GSD command derived from current state and verification. Prefer that command over a generic router when the destination is known; do not start the next step before the user continues.
- Apply .planning/METHODOLOGY.md to each discussion and substantive decision: adapt the user's breadth/depth role analysis, adversarial review and synthesized recommendations to the actual project context.
- The user authorizes subagent work, routine PRs, qualifying merges and automated releases within the selected step. Use clear file ownership and integrate independent work without reverting others. Follow through within that step without repeated approval requests for already authorized actions; respect the workflow pauses above.
- Prefer branches and PRs, protected green main, current-revision checks and an independent review pass. Triage relevant open issues/PRs at milestone start and shipping. Do not bypass protections or treat stale green checks as approval.
- Automate repeatable verification and release tasks within the authorized workflow step. In addition to the user's workflow/model checkpoints, surface unavailable credentials/account decisions or physical evidence that actually requires human involvement. Keep the unverified claim narrow and continue independent work within the approved step.
- Keep CI small and reliable. Measure critical path and runner-minutes, remove duplicate preparation, bound parallelism by memory, and cache only when it helps. Retain cold builds and fail-safe change classification.
- Bind releases to tested commits and artifacts. Stage complete releases before publication; verify token/event behavior. Keep untrusted PR execution separate from signing/publishing authority.

## Public repository hygiene

- Original Glueyneo work uses MIT. Preserve imported licenses/notices and audit each dependency and fixture at an immutable revision. No game/BIOS redistribution without an established right.
- Keep commercial ROMs, BIOS, private save states/captures and private test outputs outside Git and public CI. A hash identifies bytes; it does not establish redistribution permission.
- The library requires no secrets. Explicit local automation may use ignored .env.local; use GitHub Actions secrets for CI credentials and configuration variables for nonsecrets. Never print secret values or dump environments.
- Do not publish personal absolute paths, private emails, machine identifiers or private repository/account URLs. Check staged files, commit identity, generated docs, debug paths, archives and logs before public publication. Use an established public/noreply identity.
- Other projects used as research evidence are read-only unless the user separately requests changes there.

These rules capture project preferences, not an assertion that the proposed tooling, tests or automation already exists. Respect applicable runtime permissions and higher-priority instructions.
