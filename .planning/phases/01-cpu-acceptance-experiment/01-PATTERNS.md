# Phase 1: CPU acceptance experiment - Pattern Map

**Mapped:** 2026-10-01  
**Files classified:** 41 proposed files  
**Analogs found:** 0 / 41

## Scope and Evidence

The tracked repository contains planning/preparation documents, root instructions, README, license and ignore rules. It contains no implemented runtime, vendored dependency, CMake target or test runner. `git ls-files` enumerated 29 tracked paths at mapping time; none is a runtime/build/test implementation. There are therefore **no existing implementation analogs or source excerpts to copy**. Historical sibling-project receipts, proposed snippets and research scratch checkouts are not Glueyneo implementation.

Inputs: `01-CONTEXT.md` Implementation Decisions and Existing Code Insights; `01-RESEARCH.md` Standard Stack, Architecture Patterns, Quantitative Adaptation Budget and Validation Architecture; root `AGENTS.md` and current canonical scope documents. The installed OpenGSD pattern-mapper role was consulted. No project-local `.codex/skills/` or `.agents/skills/` directory was found.

Research specifies directory responsibilities, root/private CMake configuration and selected upstream filenames rather than a complete final filename list. The concrete names below are **proposed planner assignments**, not locked user decisions or files that already exist. The planner may combine small helper files or rename them while preserving all obligations. Source pins and quantitative budget remain owned by research and the pre-adaptation acceptance artifact.

## File Classification

Every row is a creation in this repository. Imported Musashi inputs also undergo bounded upstream modification. Documentation and manifests use the nearest available classification role, config/model, rather than implying executable behavior.

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `CMakeLists.txt` | config | transform | None | no existing analog |
| `experiments/cpu/CMakeLists.txt` | config | transform | None | no existing analog |
| `experiments/cpu/cpu_adapter.h` | model | request-response | None | no existing analog |
| `experiments/cpu/cpu_adapter.c` | service | request-response | None | no existing analog |
| `experiments/cpu/cpu_state.h` | model | transform | None | no existing analog |
| `experiments/cpu/cpu_state.c` | utility | transform | None | no existing analog |
| `experiments/cpu/test_bus.h` | model | request-response | None | no existing analog |
| `experiments/cpu/test_bus.c` | utility | request-response | None | no existing analog |
| `experiments/cpu/ACCEPTANCE.md` | config | batch | None | no existing analog |
| `experiments/cpu/state-inventory.json` | model | transform | None | no existing analog |
| `experiments/cpu/acceptance-results.json` | model | batch | None | no existing analog |
| `third_party/musashi/m68kcpu.c` | service | transform | None | no existing analog |
| `third_party/musashi/m68kcpu.h` | model | transform | None | no existing analog |
| `third_party/musashi/m68k.h` | model | request-response | None | no existing analog |
| `third_party/musashi/m68kconf.h` | config | transform | None | no existing analog |
| `third_party/musashi/m68k_in.c` | utility | transform | None | no existing analog |
| `third_party/musashi/m68kmake.c` | utility | file-I/O | None | no existing analog |
| `third_party/musashi/m68kops.c` | service | transform | None | no existing analog |
| `third_party/musashi/m68kops.h` | model | transform | None | no existing analog |
| `third_party/musashi/PROVENANCE.md` | config | batch | None | no existing analog |
| `third_party/unity/src/unity.c` | test | batch | None | no existing analog |
| `third_party/unity/src/unity.h` | test | batch | None | no existing analog |
| `third_party/unity/src/unity_internals.h` | test | batch | None | no existing analog |
| `third_party/unity/LICENSE.txt` | config | batch | None | no existing analog |
| `third_party/unity/PROVENANCE.md` | config | batch | None | no existing analog |
| `tests/cpu/guest_fixture.h` | model | transform | None | no existing analog |
| `tests/cpu/guest_fixture.c` | test | transform | None | no existing analog |
| `tests/cpu/ORACLE.md` | config | batch | None | no existing analog |
| `tests/cpu/fixture-manifest.json` | model | batch | None | no existing analog |
| `tests/cpu/test_guest.c` | test | batch | None | no existing analog |
| `tests/cpu/test_isolation.c` | test | batch | None | no existing analog |
| `tests/cpu/test_cold.c` | test | event-driven | None | no existing analog |
| `tests/cpu/test_timing.c` | test | batch | None | no existing analog |
| `tests/cpu/test_state.c` | test | transform | None | no existing analog |
| `tests/cpu/failure_allocator.h` | model | request-response | None | no existing analog |
| `tests/cpu/failure_allocator.c` | test | request-response | None | no existing analog |
| `tools/cpu/regenerate.cmake` | utility | file-I/O | None | no existing analog |
| `tools/cpu/check_closure.cmake` | utility | batch | None | no existing analog |
| `tools/cpu/check_budget.cmake` | utility | batch | None | no existing analog |
| `tools/cpu/check_acceptance.cmake` | utility | batch | None | no existing analog |
| `tools/cpu/source-manifest.json` | model | transform | None | no existing analog |

## Pattern Assignments

**Analog for every assignment:** none. **Imports, guard, core, error, validation and test excerpts:** unavailable because no implementation exists. The following are concrete responsibilities derived from phase decisions and research, not extracted code.

| Proposed file | Implementation responsibility |
|---------------|-------------------------------|
| `CMakeLists.txt` | Root opt-in C17 experiment; target-scoped settings. |
| `experiments/cpu/CMakeLists.txt` | Private runtime, host generator and CTest targets; separate sanitizer configurations. |
| `experiments/cpu/cpu_adapter.h` | Opaque private handle, ownership, bounded run result and fault contracts. |
| `experiments/cpu/cpu_adapter.c` | Explicit instance creation/reset/run/destroy; checked budget and active fault frame. |
| `experiments/cpu/cpu_state.h` | Explicit guest-only checkpoint fields and validation contract. |
| `experiments/cpu/cpu_state.c` | Validate temporary record then atomically apply; reconstruct destination host bindings. |
| `experiments/cpu/test_bus.h` | Per-instance buffers, callback userdata and bounded observation record. |
| `experiments/cpu/test_bus.c` | Checked guest address/width, explicit byte order, trace bounds and recoverable host fault. |
| `experiments/cpu/ACCEPTANCE.md` | Budget frozen before adaptation; attempt ledger, outcomes, limitations and admission decision. |
| `experiments/cpu/state-inventory.json` | Every adapted field: owner, mutation, callback access, save class and restore rule. |
| `experiments/cpu/acceptance-results.json` | Exact code/tool/configuration/input identities; distinct pass/fail/skipped/unsupported/unknown. |
| `third_party/musashi/m68kcpu.c` | Adapt pinned core to explicit context throughout execution, callbacks and exception handling. |
| `third_party/musashi/m68kcpu.h` | Instance-owned machine/transient state, pure constants, context-aware helpers and guards. |
| `third_party/musashi/m68k.h` | Private candidate declarations with explicit context and checked model seam. |
| `third_party/musashi/m68kconf.h` | 68000-only compile closure; disable later variants, PMMU, MAME and runtime logging. |
| `third_party/musashi/m68k_in.c` | Context-aware opcode input and dispatch/cycle construction; remove excluded dependencies. |
| `third_party/musashi/m68kmake.c` | Separate host generator; update emitted signatures consistently with dispatch types. |
| `third_party/musashi/m68kops.c` | Reproducibly generated opcode output; never hand edit. |
| `third_party/musashi/m68kops.h` | Reproducibly generated declarations; never hand edit. |
| `third_party/musashi/PROVENANCE.md` | Immutable source pin, notices, upstream hashes and patch/generation recipe references. |
| `third_party/unity/src/unity.c` | Pinned unmodified test-only assertion implementation. |
| `third_party/unity/src/unity.h` | Pinned public test assertion declarations. |
| `third_party/unity/src/unity_internals.h` | Pinned required internal test declarations. |
| `third_party/unity/LICENSE.txt` | Retain exact imported MIT notice. |
| `third_party/unity/PROVENANCE.md` | Immutable Unity subset provenance and per-file identities. |
| `tests/cpu/guest_fixture.h` | Original annotated guest/vector constants shared by explicit test runners. |
| `tests/cpu/guest_fixture.c` | Two distinguishable original guests and independent writable memory scenarios. |
| `tests/cpu/ORACLE.md` | Exact primary manual locations, encodings, expected effects and ancestry. |
| `tests/cpu/fixture-manifest.json` | Original authorship/license, recipe, digest and oracle references. |
| `tests/cpu/test_guest.c` | Guest arithmetic/store assertions and consequential negative control. |
| `tests/cpu/test_isolation.c` | Isolated/interleaved/concurrent equivalence at equal actual boundaries. |
| `tests/cpu/test_cold.c` | Fresh-process barrier-started create/run/capture/destroy; finite reported rounds. |
| `tests/cpu/test_timing.c` | Zero/reset/overshoot/STOP/IRQ/RTE/exception cases and hostile bus faults. |
| `tests/cpu/test_state.c` | Fresh-instance continuation, pending-state sensitivity and invalid restore atomicity. |
| `tests/cpu/failure_allocator.h` | Harness-only allocation injection declarations and accounting. |
| `tests/cpu/failure_allocator.c` | Fail each construction allocation while healthy witness continues; partial cleanup. |
| `tools/cpu/regenerate.cmake` | Fresh output directories, host generator execution and byte comparison. |
| `tools/cpu/check_closure.cmake` | Inventory/dependency/preprocess/link evidence, forbidden imports and actual source absence. |
| `tools/cpu/check_budget.cmake` | Pristine/adapted churn and generated caps; semantic/support classifications and attempt limits. |
| `tools/cpu/check_acceptance.cmake` | Nonempty required receipts and rejection cannot enable Phase 2 admission. |
| `tools/cpu/source-manifest.json` | Per-file copied/generated/compiled/distributed flags, hashes, notices and host-call disposition. |

### Build and vendor assignments

Use `01-RESEARCH.md:117` (Standard Stack), `:193` (Recommended Project Structure), `:215` (Minimal compiled AND distributed closure) and `:372` (Test Framework) for the CMake, dependency and generator rows. Import only audited subsets at the recorded immutable pins. Configure without downloads. Unity remains test-only; its explicit C runners can live in each test translation unit. Preserve all upstream notices in source as well as provenance records.

The six proposed handwritten Musashi inputs map directly to the research budget: core source, internal header, external header, configuration, opcode input and generator. Generated opcode source/header are separate accounting categories. Do not infer permission to import FPU, MMU, SoftFloat, disassembler or upstream Makefile from their appearance in the research source ledger. Any retained file requires its own actual closure and notice disposition.

### Adapter, bus and state assignments

Use research `:205` (Explicit context propagation), `:231` (Complete state inventory) and `:252` (Timing and host-fault mechanics). Thread the same explicit instance through direct calls, inline helpers, macro expansions, function pointers, generator output and callbacks. The private adapter must report bounded faults without terminating the embedding host.

The bus and allocation injector are harness facilities. Keep host thread orchestration, filesystem access and evidence output outside the runtime linkage. Save guest fields explicitly; bus memory is copied separately. Restore validates before mutation and binds the destination's callbacks and transient call state.

### Test, fixture and acceptance assignments

Use research `:386` (Requirements → Test Map), `:400` (Concrete fixtures and stress), `:149` (Quantitative Adaptation Budget) and `:325` (Recommended Tracer Plans). Register nonempty named CTest cases for closure, guest, isolation, cold initialization, timing, state and acceptance. Pair the first adaptation slice with real guest execution and a consequential wrong-behavior control.

A single test file may register multiple explicit runner cases. Make sanitizer configurations separate and instrument the actual adapted runtime. An unavailable lane is an explicit unsupported/skipped result. Original fixture rights and manually justified expected effects must precede any acceptance claim.

## Shared Patterns

These are **required design constraints**, with no existing implementation excerpt.

| Concern | Apply to | Required implementation / source |
|---------|----------|----------------------------------|
| Explicit ownership | Adapter, bus, backend, state codec | Instance-owned mutable state and callback bindings; no global/TLS current CPU or global execution lock. Context D-06; research Explicit context propagation. |
| Initialization | Backend tables and cold runner | Build private dispatch/cycle tables per instance from immutable descriptors; concurrent first use must be exercised. Research Architecture Patterns. |
| Host safety | All runtime translation units | No process exit, ambient file/device/network/environment I/O or wall clock. Fault frames must be active before reset/IRQ/vector/stack access. Context D-05; research Timing and host-fault mechanics. |
| Validation | Adapter, bus, state restore | Checked resource bounds, defined integer arithmetic, explicit byte order and atomic rejection. Zero budget does not enter the candidate. |
| Timing | Adapter and timing/isolation/state tests | Report actual elapsed cycles, instruction progress, overshoot and stop/fault reason; compare equal guest boundaries. No bus-cycle precision or board-accuracy inference. |
| State | Codec, field ledger and continuation tests | Classify every mutable compiled field; never serialize host pointers, callback identities or jump buffers. Reconstruct destination bindings and prove continuation. |
| Reproducibility | Import/generation/build tools and manifests | Immutable input identities, retained notices, explicit closure flags, fresh regeneration and byte comparison; no hand-edited generated output. |
| Error evidence | Test runners and receipts | Preserve minimized failures, bounded traces and distinct outcomes; no regenerated goldens or weakened budgets to force success. |
| Public hygiene | All authored files and receipts | Repository-relative paths and public-safe identities; no proprietary media, secrets or personal machine paths. |
| Admission | Budget checker and acceptance receipt | Freeze the finite numeric cap before adaptation; at most two attempts in the same cumulative budget. Rejection fulfills CPU-05 only and leaves CPU-01–04 pending. |

Authentication, web routing, sessions, database transactions and API response middleware are not applicable to this native private CPU experiment. Native lifecycle validation must not be described as an authentication pattern.

## No Analog Found

All 41 files in File Classification have no tracked implementation analog. The following groups explain the gaps and the appropriate fallback:

| File group | Roles / data flows | Reason and fallback |
|------------|--------------------|---------------------|
| Root and private CMake files | config / transform | No build system exists; use research target boundaries and validation commands as proposals. |
| Private adapter, state and bus files | service, model, utility / request-response, transform | No runtime API or backend exists; implement from current ownership/timing/state requirements. |
| Selected Musashi inputs and generated outputs | service, model, utility, config / transform, request-response, file-I/O | Candidate source is not vendored or accepted; pinned upstream is an import source, not a tracked project analog. |
| Unity subset and notices | test, config / batch | No test framework is vendored; admit exact upstream subset and write explicit runners. |
| Guests, oracle, manifests and test support | test, model, config / batch, transform, event-driven, request-response | No redistributable fixture or experiment runner exists; author original inputs with independent expected effects. |
| Regeneration, closure, budget and acceptance tools | utility, model / file-I/O, batch, transform | No automation implementation exists; build bounded host-only tools alongside the runnable guest. |
| Acceptance notes, state inventory and result receipt | config, model / batch, transform | Research describes future evidence; implementation must produce actual receipts before acceptance. |

Preparation remains dated provenance. No local runtime/plugin mirror, untracked scratch source or sibling repository is assigned as an analog. No source excerpts are fabricated to fill these gaps.

## Metadata

- **Analog search scope:** Full Git-tracked repository inventory; proposed `experiments/cpu/`, `third_party/`, `tests/cpu/` and `tools/cpu/` have no tracked implementations.
- **Files scanned:** 29 tracked path entries; 0 candidate implementation files to extract.
- **Files classified:** 41 proposed files; exact analog 0, role-match analog 0, no analog 41.
- **Pattern extraction date:** 2026-10-01.
- **Scope exclusions:** Public native ABI, installed SDK consumers, board bootstrap, hosted CI/release qualification, Z80/YM2610, libretro, public snapshots and durable saves belong to later phases/milestones.
- **Mapping outcome:** Ready for planning with explicit greenfield gaps. This map establishes no runtime, test, sanitizer, platform or backend acceptance result.

