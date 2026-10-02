# Project Research Summary

**Project:** Glueyneo
**Domain:** Portable C Neo Geo MVS/AES cartridge emulation core and integration SDK
**Researched:** 2026-10-01
**Confidence:** MEDIUM
**Status:** Planning synthesis. No runtime code, backend acceptance, platform qualification, compatibility result or performance measurement is established.

**Scope update — 2026-10-02:** The current [project contract](../PROJECT.md), [requirements](../REQUIREMENTS.md), and [roadmap](../ROADMAP.md) supersede this report's Musashi-first backend recommendation and conditional SDL3-host references. The owner selected planning for an owned C17 CPU core; each core repository targets a library, headless diagnostic runner, and thin libretro adapter, with GUI ownership in RetroArch and the future shared host. Preserve the report as dated research provenance.

## Executive Summary

Glueyneo should begin as an installable **v0.1 CPU/bus diagnostic SDK alpha**. Its defining result is an external C consumer executing an original deterministic guest program through the ordinary native API. Build one concrete machine model with explicit instance ownership, a private audited CPU adapter and host-owned media loading and presentation. The [current project contract](../PROJECT.md) controls scope; dated preparation supplies provenance. The next milestone adds selected video/input/real chip sound, continuation and persistence, and a thin libretro adapter qualified in actual RetroArch on macOS. Commercial-game compatibility follows later.

Use C17, target-based CMake/CTest and a small pinned Unity test dependency. Investigate the pinned Musashi candidate first, under a concrete adaptation budget and accept/reject gate. The gate must prove instance independence, bounded stop semantics and the exact copied/compiled/generated/distributed source closure. Musashi's shared execution state, unconditional FPU inclusion, default SoftFloat dependency with distinct notices, and FPU stderr/exit paths make this a dependency admission question. Configuration flags alone do not establish removal, safe host behavior or license disposition. Reject or reopen the backend choice if the required work exceeds the budget; no qualified alternative is established by this research.

Organize v0.1 into three observable phases: backend qualification, the working diagnostic SDK, and release qualification. Introduce package and evidence scaffolding alongside execution, then qualify static/shared installed and relocated consumers, offline source archives and complete commit-bound release artifacts. The other principal risks are correlated test oracles, overstated timing/support claims and fragile publication authority. Prevent them with explicit oracle ancestry, a consequential negative control, actual consumer receipts, narrow capability statements and tested release recovery. Diagnostic throughput is not gameplay performance; proposed pins, minima and platform lanes remain candidates until exercised.

## Key Findings

### Recommended Stack

The [stack report](STACK.md) favors a small all-C runtime and self-contained source distribution. Keep public headers free of private dependency structures. Ship audited generated opcode source and its regeneration provenance so ordinary consumers do not need a generator toolchain or network access. Cross builds must never execute target binaries as host generators.

| Technology | Recommendation and qualification status |
|---|---|
| C17 | Runtime and selected runtime dependencies; defined integer behavior and explicit byte order. Compiler/SDK minima are unqualified. |
| CMake/CTest | Target-local settings, static/shared builds, exported `glueyneo::glueyneo` and relocatable installation. **3.24 is a proposed minimum**, to test alongside a pinned current version. |
| Musashi | First feasibility candidate: `313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd`. Not selected or approved; source/version labels do not replace this identity. |
| Unity | Test-only candidate v2.7.0, `b6763fbd9cedfacaa89e2ad9fd00d615a234e355`; vendor the small C subset and notice. Upstream identity was checked; project compatibility is untested. |
| Ninja | Developer convenience candidate 1.13.2; consumers may choose another supported executor. |
| Compiler instrumentation | Proportionate ASan/UBSan, race evidence where supported, bounded fuzzing and simple C property loops; toolchain-specific unsupported outcomes stay visible. |

Start platform qualification with proposed macOS arm64, Linux x86-64 and Windows x86-64 lanes. Claim macOS Intel support only after its own evidence. No SDL, libretro, archive framework, resampler, Z80 or YM2610 runtime integration is required for v0.1. Future C chip candidates need separate acceptance; upstream C++ ymfm does not satisfy the current all-C constraint.

### Expected Features

The [feature report](FEATURES.md) separates SDK expectations from eventual player expectations.

**Must have for v0.1:**

- Real CPU/bus execution of an original redistributable diagnostic, with justified expected observations and explicit bootstrap/subset documentation.
- Opaque lifecycle, explicit media/buffer ownership, resource limits, useful errors, failed-load recovery and bounded deterministic execution with actual progress and stop reasons.
- Independent instances demonstrated through interleaving, concurrent execution, cold initialization and failure/teardown paths.
- Offline static/shared source and installed packages, a relocated out-of-tree C consumer executing the diagnostic, compiled examples and C++ header linkage checks.
- Machine-readable evidence, fixture/license provenance, honest supported capabilities, measured diagnostic baselines and a complete traceable unsigned SDK alpha.

**Should have as differentiators:**

- A reproducible release demonstration requiring no commercial media.
- Small host-independent C interfaces and documented upstream changes.
- Claim-level evidence distinguishing safety, determinism, conformance, compatibility and performance. Add bounded traces only for concrete investigations.

**Defer beyond v0.1:**

- Next milestone: selected graphics/input/real sound, actual pinned RetroArch macOS load/run/unload, snapshot continuation and durable persistence.
- Later milestones: practical commercial-media import, original BIOS/profile qualification, first private game scenario, hardware-family expansion and direct Playstead integration.
- Conditional later work: SDL3 host, broader platforms, optimization, stable multi-consumer ABI policy, rewind/run-ahead and netplay. No release number is promised for these.

### Architecture Approach

The [architecture report](ARCHITECTURE.md) recommends explicit instance ownership and one native execution path. Each instance has one active caller; separate instances may run concurrently after qualification. Hosts own files, archives, devices, wall clock, sleeping and network activity. The core owns deterministic guest time and hardware behavior, preserving original slowdown.

**Major components:**

1. **Native API and machine owner:** lifecycle, configuration, checked normalized spans, allocation ownership, failure cleanup and supported-subset errors.
2. **Private 68000 adapter:** instance-bound callbacks, upstream isolation, exception/error translation and the demonstrated execution boundary.
3. **Board bus and execution coordinator:** explicit byte lanes, widths, ordering, diagnostic memory, bounded integer guest time and actual progress.
4. **Diagnostic and consumer evidence:** original fixture/bootstrap, bounded observations and executable package examples through ordinary API calls.
5. **Later device/adapter/state modules:** concrete video/input/sound and cartridge profiles, native-API libretro adapter, explicit snapshot codec and persistence exchange.

Keep shared tables immutable after safe initialization. Disclose instruction-boundary overshoot; integer timestamps do not prove per-access timing. Inventory every state field now, but defer public snapshots. Library release, ABI, snapshot, replay and durable-save compatibility require distinct identities; host pointers, jump buffers and persistence acknowledgments are not canonical guest state.

### Critical Pitfalls

The [pitfalls report](PITFALLS.md) supplies detailed gates and recovery paths. Prioritize these five groups:

1. **Apparent contexts still share state (P1):** audit the entire compiled closure and initialization, then compare separate instances against isolated baselines under interleaving, concurrent cold starts and failures. A global lock/current-instance pointer is not acceptance.
2. **Hidden source/license/host dependencies (P2):** prove the minimal 68000 closure, or disposition every retained FPU/SoftFloat file, notice, mutable field and host call. Test unsupported/exception paths; no guest error may terminate the host.
3. **Self-confirming diagnostic and inflated timing claims (P3/P4):** document oracle ancestry, validate initialized data/BSS and named bus effects, require nonempty assertions and a deliberate wrong-behavior control, and disclose stop/bus precision. Custom bootstrap success proves no original BIOS compatibility.
4. **Green but unsafe/incomplete delivery (P5/P6):** qualify actual bot events and current-head checks; separate untrusted PR execution from publication authority; bind draft, tested commit and asset digests; recover interrupted/no-new-release-output retries; inspect public source and artifacts for private data.
5. **Incomplete restoration loses execution or durable writes (P7):** inventory state during v0.1; next milestone must prove fresh-instance continuation and fresh-process durable reopening, atomic rejection of malformed state and stale acknowledgment handling. A nonempty save file is insufficient.

## Implications for Roadmap

Recommend **three coarse phases for v0.1**, each decomposed into small reviewable vertical plans. These are suggestions for requirements/roadmap derivation, not canonical allocated phases. Keep the next milestone outlined and the longer horizon revisable.

### Phase 1: Qualify the CPU and Execution Contract

**Rationale:** Backend feasibility constrains ownership, stopping and bus contracts; resolve it before hardening a public ABI.

**Delivers:** A reproducible bounded acceptance experiment and explicit accepted/rejected/deferred decision, with counterexamples for failure. Set an effort/patch budget before work. Record exact source/config/generator identities, file/license/host-call closure, mutable-state inventory, safe table initialization, interrupt/exception behavior, actual time and overshoot. An accepted candidate must demonstrate meaningful tiny guest execution, distinguishable independent instances, simultaneous cold starts and failure cleanup. Supported-boundary backend state continuation is scoped evidence, not a public whole-machine snapshot promise.

**Addresses:** Qualified C CPU, independent instances, deterministic bounded execution and dependency provenance from FEATURES.md.

**Avoids:** P1/P2 and premature P4 promises. FPU/SoftFloat closure is an admission blocker. If adaptation exceeds budget, produce a rejection/replanning decision instead of silently weakening the contract. Inventory future sound candidates without requiring their port.

**Research:** Bounded phase research is needed for the selected source closure, configuration, reentrancy and observable timing. Exit on evidence and decision, not indefinite exploration.

### Phase 2: Execute the Diagnostic Through an Installable SDK

**Rationale:** A real consumer should shape the minimal API and package while the first useful behavior is built.

**Delivers:** An original redistributable CPU/bus diagnostic executed through create/load/reset/bounded run/results/destroy as agreed by the contract. Implement only the evidenced bus/bootstrap subset. Establish C17/CMake/CTest and Unity, offline dependency contents, static/shared builds and an external installed C consumer. Include explicit lifecycle/media limits, recovery, startup/bus assertions, independent oracle rationale and a negative control. Record repeat/split-run and isolation results, meaningful boundary/property/fuzz/sanitizer evidence, initial platform receipts and diagnostic memory/execution/build measurements.

**Addresses:** Native API, safe media, useful errors, executable diagnostic, offline package, examples and capability/evidence reporting.

**Avoids:** P3/P4, accidental host coupling, in-tree-only packaging confidence and unmeasured performance claims. Use fast CI with nonempty executed-count reporting; absent video/audio/game capabilities remain unsupported.

**Research:** Targeted research for the diagnostic's exact CPU/bus assertions and bootstrap oracle; standard CMake exports, C lifecycle and Unity patterns can proceed without broad ecosystem research after Phase 1 resolves the execution seam.

### Phase 3: Qualify and Deliver the Unsigned SDK Alpha

**Rationale:** Release automation should distribute established behavior and artifacts. Complete consumer and recovery evidence before unattended publication.

**Delivers:** Compiled getting-started and ownership/error documentation; installed/relocated static/shared execution with source/build access removed; a clean offline release-source build; exact tested toolchain/support matrix and public-safe notices/fixture metadata. Qualify required current-head checks, independent review, scoped automation authority and complete staged release assets bound to the tested commit. Exercise interruption/retry, missing asset, wrong commit and failed consumer refusal paths; verify downloaded package bytes and diagnostic execution. Publish the unsigned alpha when actual authority is available, with outstanding blockers explicit.

**Addresses:** Traceable downloadable SDK, reproducible integration, supported-subset documentation and maintainable release evidence.

**Avoids:** P5/P6, stale checks, partial releases, hidden archive dependencies and publication of private metadata. Measure CI critical path/runner-minutes and retain cold builds; account setup must not block independent artifact preparation.

**Research:** Targeted current documentation and repository experiments for the chosen release-please pin, draft/tag recovery and GitHub App/token event graph. Package relocation and compiled documentation use established patterns.

### Phase Ordering Rationale

- Backend acceptance enables a truthful execution contract; real diagnostic execution enables a useful SDK; working SDK artifacts enable release qualification.
- Package scaffolding and public evidence admission can proceed alongside the CPU experiment. Source/privacy/license checks start at admission, not at publication.
- The three phases all serve v0.1. Do not reinterpret Phase 2 as the interactive milestone or Phase 3 as commercial compatibility.
- The next milestone must add selected video/input/Z80/YM2610 behavior, firmware strategy, native/libretro equivalence, actual pinned RetroArch macOS qualification, continuation and persistence. State and persistence belong within that interactive acceptance scope; they are not postponed until commercial games.
- Later game claims require a practical host-side importer, lawful private media, supported BIOS/board/profile and reproducible scenarios. Expand by hardware family, then optimize representative measured workloads.

### Research Flags

- **Needs focused research:** Phase 1 CPU admission; Phase 2 diagnostic/oracle and supported bus subset; Phase 3 release action/service behavior and deployed authority.
- **Standard patterns, skip broad re-research:** C17 target-local CMake/CTest, small Unity runners, opaque lifecycle, exported/relocated packages and compiled examples. Implementation receipts are still required.
- **Next-milestone research:** Z80/YM2610 C feasibility and state, device timing/output boundaries, diagnostic firmware, sound oracle, actual RetroArch automation, continuation and persistence semantics.
- Use `$gsd-plan-phase <N> --research` for the uncertain parts when their phases are allocated. Existing research and dated preparation should seed bounded questions.

## Confidence Assessment

| Area | Confidence | Notes |
|---|---|---|
| Stack | MEDIUM | Exact candidate identities and official source checks; complete closure, adaptation, compiler support and package compatibility unqualified. |
| Features | MEDIUM | Current scope is authoritative; ecosystem descriptions are qualitative and no adoption study or executed competitor comparison exists. |
| Architecture | MEDIUM | Consistent ownership/consumer patterns and inspected global state; no implemented timing, isolation or device integration evidence. |
| Pitfalls | MEDIUM | Concrete source findings and adversarial preparation; hosted-service claims require qualification, with immutable-release fetch evidence explicitly LOW in the source report. |

**Overall confidence:** MEDIUM in the planning recommendation; implementation feasibility remains unknown. Agreement among these reports often shares preparation/source ancestry and is not four independent empirical validations.

### Gaps to Address

- **CPU cost and closure:** Phase 1 must set the budget, resolve FPU/SoftFloat retention and notices, prove isolation/host safety and select or reject the candidate.
- **Diagnostic truth and boundary:** Phase 2 must choose reproducible source/generation tools, startup semantics, exact bus subset and independently justified assertions. Missing physical evidence narrows claims.
- **Ownership and toolchains:** Exercise one minimal media lifetime policy and actual compiler/SDK/platform combinations before promising API/support stability.
- **Measurements:** All preparation numbers remain targets. Calibrate diagnostic and CI baselines; preserve raw observations and unsupported outcomes.
- **Release authority:** Repository/account configuration and actual bot/event behavior remain external qualification tasks; prepare complete artifacts while resolving them.
- **Future machine behavior:** Firmware strategy, video/audio precision, sound candidates/resampler, complete state/persistence and commercial importer remain next/later milestone decisions.

## Sources

Source classifications below retain the research reports' confidence instead of upgrading a primary source to implemented proof. All research is dated **2026-10-01**; exact external revisions, URLs and claim limitations remain in the linked ledgers.

### Authoritative Project Scope and Dated Provenance

- [PROJECT.md](../PROJECT.md) — current milestone, constraints and outlined next milestone; authoritative scope, no runtime evidence.
- [Decision register](../preparation/DECISIONS.md), PREP-D-01–PREP-D-44; [roadmap seed](../preparation/ROADMAP-SEED.md) — decision ancestry and revisable sequence.
- [C architecture](../preparation/C-CORE-ARCHITECTURE.md), C-01–C-29; [adversarial review](../preparation/ADVERSARIAL-REVIEW.md), A-01–A-04 — ownership, timing, state and failure gates.
- [Quality/performance/CI](../preparation/QUALITY-PERFORMANCE-AND-CI.md) and [hardware/ecosystem](../preparation/NEOGEO-HARDWARE-AND-ECOSYSTEM.md) — evidence dimensions and source ancestry, without current measurements.

### Primary Technical Sources and MEDIUM Research Synthesis

- [STACK.md source ledger](STACK.md#sources), S-01–S-05 — pinned Musashi CPU/config/generator/Makefile/FPU/SoftFloat facts; S-06–S-13 — versioned CMake, Unity, compiler and Ninja documentation/identities.
- [FEATURES.md source ledger](FEATURES.md#sources), S7/S8 — official Geolith README and FBNeo Libretro descriptions; living descriptions, not executed comparisons or immutable qualification.
- [ARCHITECTURE.md source ledger](ARCHITECTURE.md#sources-and-confidence), F1/F2 — pinned Musashi state and MAME CPU interruption model; MAME is implementation evidence, not hardware truth.
- [PITFALLS.md source ledger](PITFALLS.md#sources), S8/S9/S11 — release-please schema/action and GitHub token behavior; mutable documentation must be rechecked at implementation.

### Lower-Confidence Service Evidence

- [PITFALLS.md source ledger](PITFALLS.md#sources), S10 — official GitHub immutable-release documentation classified LOW by the research helper's direct-fetch path; actual repository draft/assets/publication behavior remains untested.

---
*Research completed: 2026-10-01*
*Ready for roadmap: yes; derive canonical requirements and phase plans from the current project scope and these bounded gates.*
