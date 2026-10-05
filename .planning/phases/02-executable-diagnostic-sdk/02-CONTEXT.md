# Phase 02: Executable diagnostic SDK - Context

**Gathered:** 2026-10-05  
**Status:** Planning complete; independently checked and ready for execution 2026-10-05

<domain>
## Phase Boundary

Deliver an offline-installable C17 SDK and headless runner that execute one meaningful, original, redistributable CPU/bus diagnostic through the ordinary native instance API. Make instance lifecycle and bounded immutable-media ownership explicit, return actionable host-safe errors and deterministic guest progress, and demonstrate the installed package through real out-of-tree C consumers for static and shared builds plus C++ public-header linkage. Tie diagnostic observations, dependency/fixture provenance, machine-readable results, and cost baselines to exact inputs and revisions.

Phase 02 depends on the Phase 01 CPU acceptance gate, which passed a fresh whole-phase verification at source revision `09476ed57ee29c0798f8be8f082e05ad73776e3b` (10/10 must-haves). CPU-01–05 are complete for the bounded owned diagnostic subset. Phase 02 planning is complete: six independently checked plans cover all 15 requirements, 18 accepted decisions and 21 spec-less edge rows, and the phase is ready for execution. The frozen candidate receipt still says `unqualified` / `phase_admitted: false`; that is its experiment-level disposition, separate from phase-level admission. Original-silicon saved-PC behavior remains unknown, and exact `0x4AFC` remains unsupported for this candidate only. The prior gate-status prose in this context is superseded by this update; no implementation decisions below are reopened.

The source-bound `tools/owned_cpu/contract.py` validation records the pre-admission Pending/gated checkpoint and must not be edited to rewrite the old receipt. It is not the current phase router. The current admission result is `01-VERIFICATION.md` plus the canonical `STATE.md` and `ROADMAP.md`. The unchanged checker no longer accepts the current post-admission planning text; planning must account for that historical gate test without restoring stale Pending status or altering the source-bound receipt. Do not repeat Plan 01-29, Phase 01 verification, or historical UAT.

The installed `query verification.status` reports the 01 report's fingerprint as stale after phase-closeout documentation changed and suggests `$gsd-execute-phase 01`. This is administrative fingerprint drift: no runtime or CPU acceptance evidence changed, and the updated documentation-route regression passed 8/8. Do not follow that stale route or rerun Phase 01 for status-only edits. Phase 02 is the active phase and is ready to execute; the next command is `$gsd-execute-phase 02`.

Out of scope: full game and original-BIOS compatibility, commercial media, video/audio, a GUI, public CPU/plugin state, durable persistence, and Phase 03 hosted CI/protected-PR/release qualification. Do not turn a functional callback trace into a physical bus-pin, Neo Geo board-timing, or hardware-truth claim.

</domain>

<decisions>
## Implementation Decisions

The user instructed: “follow ur recs for all these plz.” This accepts the recommendations summarized here; downstream planning may choose concrete names and internal structure but must surface any material deviation from these behavior and evidence contracts.

### Native instance, media ownership, lifecycle and failure guarantees

- **D2-01:** P02-C-01 — Use an opaque per-instance native C API. Accept a documented, bounded region/manifest input backed by immutable source bytes. Validate sizes, arithmetic, and region bounds before allocating; copy successful input into instance-owned normalized storage so the consumer can release its source buffer after load.
- **D2-02:** P02-C-02 — Commit load transactionally. A rejected manifest, allocation failure, or failed replacement must leave a previously usable instance and its loaded media unchanged. Keep reset distinct from unload: reset restarts the guest from the loaded media, unload explicitly releases media, and destroy releases all instance-owned memory.
- **D2-03:** P02-C-03 — Initially use standard C allocation in the public API. Exercise allocation-failure behavior through private/test-only fault injection; do not add a public allocator callback contract unless a concrete integrator requirement justifies the extra lifetime and callback surface.
- **D2-04:** P02-C-04 — Keep calls on one instance non-overlapping/non-reentrant; allow distinct instances to run concurrently. Keep host file, archive, device, wall-clock, network, and process services outside the native core.

### Deterministic bounded execution and public observations

- **D2-05:** P02-C-05 — Bound native execution by a finite guest-cycle request derived from the accepted Phase 01 timing contract. Return actual elapsed guest cycles, completed instruction count, instruction-boundary overshoot, explicit stop/error reason, and fault PC/instruction details where relevant. Do not use wall-clock time as guest progress or make a host-time timeout part of core semantics.
- **D2-06:** P02-C-06 — Report a guest `STOP` as an execution state/result, not success by itself. The diagnostic runner and consumer determine success from named expected guest results.
- **D2-07:** P02-C-07 — Expose only bounded run information and the diagnostic's named guest-visible observations through the ordinary API. Keep complete CPU registers, private continuation records, and unrestricted bus histories out of the public API. Use a bounded private test/runner trace for the functional bus assertions required by the diagnostic contract.
- **D2-08:** P02-C-08 — Do not expose a public snapshot, replay, persistence, or CPU plugin contract in this phase. Any private state/test seam remains distinct from the SDK ABI and durable formats.

### Original diagnostic, functional bus observation, and independent oracle

- **D2-09:** P02-C-09 — Run the same original, redistributable, firmware-free CPU/bus diagnostic through both the ordinary native API and the headless runner. Extend the evidence to cover initialized data and BSS, guest-computed CPU results, and named, bounded functional bus observations; derive exact fixture contents and outputs during research from the accepted backend contract.
- **D2-10:** P02-C-10 — Derive expected CPU behavior from the original fixture recipe and Motorola/NXP M68000 primary manuals. Other emulator outputs may help locate disagreements, but their ancestry must be recorded and they cannot serve as the hardware oracle. The manuals establish CPU behavior, not Neo Geo board behavior.
- **D2-11:** P02-C-11 — Keep a named wrong-behavior mutation control for each consequential diagnostic claim. It must fail the intended assertion; crashes, timeouts, unrelated failures, nonzero exit alone, and zero executed assertions do not count as a passing negative control.
- **D2-12:** P02-C-12 — Record rights/notices, source and generation recipe, exact fixture/output digest, firmware needs, tool/configuration identities, oracle ancestry, and executed assertion counts. Publish only the original lawful fixture; no commercial ROM, BIOS, or private corpus.

### Shift-left evidence, package consumers, automation, and cost

- **D2-13:** P02-C-13 — Map each observable requirement to its earliest useful automated check in the plan and SUMMARY coverage. Keep one reproducible CTest-backed local verification entrypoint with focused suites and visible denominators; do not create a second testing framework or one opaque all-purpose test.
- **D2-14:** P02-C-14 — Cover bounds, invalid media/lifecycle/error recovery, allocation failure, expected-result integer boundaries, negative controls, repeat/split execution at equal guest boundaries, distinguishable interleaved and concurrent instances, and concurrent cold create/load/teardown. Retain each discovered defect as a deterministic regression.
- **D2-15:** P02-C-15 — Use bounded fuzz targets only for hostile media and public call sequences. Preserve and minimize failures, then promote them to deterministic regressions. Run supported ASan/UBSan and concurrency sanitizer configurations where available; pair UBSan with expected-result boundary cases. Report unsupported sanitizer/toolchain lanes explicitly. Do not let sanitizer or fuzz axes multiply into an unmeasured CI matrix.
- **D2-16:** P02-C-16 — Build and run real out-of-tree installed C consumers against static and shared libraries, and compile/link a C++ consumer of the public headers. Compiled examples and ownership/error/failure-reproduction docs must match the actual installed artifacts. CMake packages must work from relocated prefixes; offline source consumption must not download dependencies at configure time.
- **D2-17:** P02-C-17 — Produce machine-readable pass/fail/skipped/unsupported/unknown outcomes with exact source/dependency/build/configuration/input/fixture/oracle identities and nonzero executed assertions. Record named-host diagnostic execution, memory/allocation, load, and build-cost baselines with workload identity and uncertainty; do not enforce uncalibrated thresholds or claim gameplay performance.
- **D2-18:** P02-C-18 — Keep hosted required CI, branch protection, unattended PR/App behavior, release automation, and published artifact qualification in Phase 03. When hosted CI is introduced, reuse the local verification entrypoint and check parity. Do not claim Phase 03 authority or support-matrix qualification from local Phase 02 checks.

### the agent's Discretion

- Choose concrete function/type names, enum values, manifest encoding, result-record schema, test-suite names, bounded fuzz duration, and test-only allocation-failure injection technique. Keep these choices C17, compact, documented, measurable, offline, and compatible with decisions P02-C-01–P02-C-18.
- Choose a C-native fuzz engine supported by the actual qualified toolchain. LLVM libFuzzer is an optional compiler-matched development tool, not a runtime dependency or a required portable consumer tool.
- Reuse the existing original fixture as a starting point only after the Phase 01 gate passes and after Phase 02 adds the required initialized-data/BSS observations. Do not treat the private candidate's test hooks as public behavior.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Current project scope and workflow
- `AGENTS.md` — project engineering, evidence, public-repository, phase-gate, and autonomy rules.
- `.planning/PROJECT.md` — product scope, C17 and host-boundary contracts, dependency preference, and Phase 01/02 gate.
- `.planning/REQUIREMENTS.md` — exact API, diagnostic, build, evidence, and documentation requirements for Phase 02.
- `.planning/ROADMAP.md` — Phase 02 success criteria and Phase 03 boundary.
- `.planning/STATE.md` — current workflow status; Phase 02 planning is complete and the next step is `$gsd-execute-phase 02`.
- `.planning/METHODOLOGY.md` — role-based synthesis, primary-source use, small-dependency policy, shift-left checks, and stale-verification-loop prevention.
- `.planning/preparation/README.md` and `.planning/preparation/DECISIONS.md` — dated evidence index and PREP-D provenance; current canonical project documents supersede preparation proposals.

### Phase 01 admission and reusable evidence
- `.planning/phases/01-cpu-acceptance-experiment/01-CONTEXT.md` — candidate boundary, original fixture, explicit uncertainty, and prior decisions.
- `.planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md` — current 10/10 whole-phase result, point-in-time at the source revision above; phase-level admission for the bounded candidate.
- `.planning/phases/01-cpu-acceptance-experiment/01-29-SUMMARY.md` and `01-29-ADMISSION-REVIEW.md` — independent bounded CPU recommendation and evidence, reconciled by the current verifier.
- `.planning/preparation/2026-10-04-gsd-verification-loop.md` — reproduced installed-router limitation and the fresh-verifier route.
- `experiments/owned_cpu/CONTRACT.md` and `experiments/owned_cpu/ACCEPTANCE.md` — bounded owned-core scope and frozen candidate evidence/disposition; the receipt is not the phase-level admission authority.
- `experiments/owned_cpu/cpu.h` — current private cycle/run/allocator shape to assess, not a public SDK interface.

### Fixture, architecture, package, and verification evidence
- `tests/cpu/ORACLE.md` and `tests/cpu/guest_fixture.c` — original MIT fixture recipe, manual-derived assertions, and exact negative-control precedent.
- `tests/owned_cpu/ORACLE.md` — candidate-specific observation/evidence examples; not proof of phase admission.
- `.planning/research/STACK.md` — C17/CMake/CTest/Unity and offline package recommendations; superseded Musashi and CMake-floor proposals are explicitly not current decisions.
- `.planning/research/ARCHITECTURE.md` and `.planning/research/PITFALLS.md` — instance ownership, time, host boundaries, state, oracle correlation, and failure modes.
- `.planning/preparation/C-CORE-ARCHITECTURE.md` — dated C API, allocation, and integration research.
- `.planning/preparation/QUALITY-PERFORMANCE-AND-CI.md` — fault-model testing, deterministic checks, measurement uncertainty, and CI cost evidence.
- `.planning/preparation/NEOGEO-HARDWARE-AND-ECOSYSTEM.md` — hardware claims and primary-source ancestry.

### Primary technical sources
- [Motorola M68000 Family Programmer's Reference Manual](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf) — instruction encodings and architectural effects.
- [Motorola M68000 User's Manual, Rev. 9.1](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf) — reset, bus, exception, and timing references; not Neo Geo board evidence.
- [CMake 3.20 `install()` documentation](https://cmake.org/cmake/help/v3.20/command/install.html) — target installation/export behavior at the provisional project floor.
- [LLVM libFuzzer documentation](https://llvm.org/docs/LibFuzzer.html) — seed corpus, bounded runs, and regression use; compiler-matched optional tool.
- [Clang AddressSanitizer documentation](https://clang.llvm.org/docs/AddressSanitizer.html) — memory-error coverage and runtime/resource tradeoffs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `experiments/owned_cpu/cpu.h`: private opaque CPU handle, explicit bus/allocator callbacks, finite guest-cycle budget, result counters, and fault status. The bounded backend passed Phase 01 acceptance; this header is still not the public SDK API.
- `tests/cpu/guest_fixture.c` and `tests/cpu/ORACLE.md`: small original MIT arithmetic/store guest with manual-derived outcomes and a specific mutation control. It is a seed for Phase 02 evidence, not a complete Phase 02 diagnostic.
- `experiments/owned_cpu/CMakeLists.txt`, root `CMakeLists.txt`, and `third_party/unity/`: current experimental CMake/CTest and test-only Unity patterns; they do not yet provide a public library target or installed SDK package.

### Established Patterns
- C17 runtime, explicit widths/byte order, opaque per-instance state, bounded resources, deterministic guest cycles, explicit status/results, and no ambient host services.
- Every fixture/result is tied to source, tool, configuration, input, and oracle ancestry. Unsupported/unknown/skipped outcomes remain explicit.
- No public CPU state, snapshot, replay, or persistence claim is implied by private continuation tests.
- The local build currently contains CPU experiments, not a public `src/` SDK or installed package. Phase 01 admission is complete for the bounded subset; Phase 02 creates and qualifies the public SDK boundary.

### Integration Points
- Place the Phase 01 accepted backend behind the ordinary native instance API and normalized diagnostic media boundary.
- Use the same native path from the headless runner and an installed out-of-tree C consumer; compile/link a separate C++ public-header consumer without adding C++ runtime code.
- Keep CTest, deterministic consumer checks, bounded fuzz/sanitizer configurations, machine-readable evidence, and cost baselines connected through the local verification entrypoint; Phase 03 later qualifies hosted authority and publication.

</code_context>

<specifics>
## Specific Ideas

The user accepted the synthesized recommendations for all four areas and specifically selected copy-on-load media ownership. The standing preferences are to shift deterministic verification left, automate recurring checks with CI value, minimize human UAT, prefer primary sources, and keep dependency trees small and flat. Apply only technical-role lenses relevant to this C CPU/bus SDK; GUI, 2D/3D rendering, databases, distributed services, and unrelated languages are not Phase 02 concerns.

</specifics>

<deferred>
## Deferred Ideas

- Commercial ROM/BIOS import, game compatibility, original-BIOS boot, video/audio, GUI, and full Neo Geo hardware claims remain outside this SDK phase.
- Public CPU/plugin ABI, snapshots, replay compatibility, durable saves, and frontend/libretro or Playstead integration remain deferred to later scopes.
- Hosted CI authority, protected PRs, App/bot event qualification, release staging/publication, and complete artifact qualification belong to Phase 03.
- The original-silicon saved-PC question remains unknown and excluded from the accepted candidate scope; it does not block this Phase 02 SDK plan.

</deferred>

---

*Phase: 02-executable-diagnostic-sdk*  
*Context gathered: 2026-10-05*
