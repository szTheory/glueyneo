# Feature Research

**Domain:** Portable C Neo Geo MVS/AES cartridge emulation core and integration SDK
**Researched:** 2026-10-01
**Confidence:** MEDIUM for ecosystem findings and planning synthesis; implementation evidence is absent.

**Scope update — 2026-10-02:** Current scope in [PROJECT.md](../PROJECT.md), [REQUIREMENTS.md](../REQUIREMENTS.md), and [ROADMAP.md](../ROADMAP.md) supersedes the conditional SDL3-host references in this dated research. Each core repository targets a library, headless diagnostic runner, and thin libretro adapter; GUI ownership stays with RetroArch and the future shared host. Preserve this report as research provenance.

## Scope and Evidence Status

[PROJECT.md](../PROJECT.md) owns current scope. The launch milestone is **v0.1 — CPU/bus diagnostic SDK alpha**: an integrator installs an offline C package and executes an original deterministic guest program through its ordinary native API. This is a useful emulation slice, not a complete Neo Geo machine or a game-playing release. The next milestone is an interactive diagnostic with selected video/input, real chip-generated sound, continuation/persistence and qualification in actual RetroArch on macOS.

All Glueyneo capabilities below are proposed. Preparation is dated provenance, not implementation evidence. Complexity estimates are relative engineering judgments, not schedules. In the tables, **SDK** means required for v0.1; **Interactive** means required for the next milestone's supported diagnostic; **Games** means required before claiming the relevant game/configuration works. Broader emulator table stakes do not automatically become SDK launch requirements. Sources S1–S8 below distinguish project decisions from ecosystem observations.

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Real CPU/bus execution through the native API | An SDK must deliver executable behavior an integrator can exercise | HIGH | **SDK.** Qualify a pinned C 68000 backend; execute an original program with a justified observable result. Document its memory map, bootstrap, instructions and timing limits. A stub or direct test-only CPU call is insufficient. S1–S4. |
| Explicit instance lifecycle, ownership and errors | A library must coexist safely with its caller | MEDIUM | **SDK.** Create/load/reset/bounded run/unload/destroy as supported by the agreed contract; documented buffers, allocation failures, invalid lifecycle handling and failed-load recovery. No process exit or ambient host services. S1, S3, S5. |
| Proven independent instances | Integrators need repeatable independent jobs and safe teardown | HIGH | **SDK.** Audit imported globals, callbacks and initialization. Exercise alternating instances, concurrent independent instances and cold initialization. A global lock or context-copy API alone is not acceptance. S1, S3–S5. |
| Deterministic bounded execution | Hosts need controllable stop points and reproducible results | HIGH | **SDK.** Explicit guest-time budget, stop reason and actual progress; disclose instruction-boundary overshoot if present. Identical supported inputs/configuration produce the specified result. No host wall clock or sleeping inside the core. S3–S5. |
| Safe normalized diagnostic media and resource limits | Bad input must yield an actionable error without corrupting the host | MEDIUM | **SDK.** A small documented region/manifest contract, checked sizes and arithmetic, maximum memory/work bounds and explicit immutable-media lifetime. Archives and filesystem discovery stay outside the core. S3–S5. |
| Offline, installed and relocated C package | Consumers need to use the library without the source tree or network | MEDIUM | **SDK.** Static/shared C17 package with target-based CMake exports, pinned dependencies and notices. A real out-of-tree C consumer must load/run the diagnostic; compile a C++ header consumer for linkage only. Test release archives and state exact supported toolchains/platforms. S1, S4, S5. |
| Useful capability report, examples and evidence | Users need to distinguish supported behavior from planned behavior | MEDIUM | **SDK.** Compile the getting-started example; publish ownership/error guidance, fixture provenance and machine-readable pass/fail/skipped/unsupported/unknown records. No fake video/audio or compatibility percentages. S1, S4, S6. |
| Traceable downloadable SDK and repeatable qualification | Integrators need a release they can reproduce and diagnose | MEDIUM | **SDK.** Unsigned alpha, tested commit and artifact identities, current-revision checks/review, complete staging before publication, license/privacy checks. Hosted authority setup is an external dependency, not an implemented feature. S1, S4, S6. |
| Selected graphics, logical input and real sound | An interactive diagnostic must visibly and audibly respond | HIGH | **Interactive.** Selected FIX/sprite/palette behavior, defined input sampling, Z80 communication and a justified YM2610 sound case. Validate raw output separately from host presentation. Full video/audio chip coverage is later work. S2–S6. |
| Load/run/unload in a real frontend | A distributed libretro core must work in the intended consumer | MEDIUM | **Interactive.** Thin adapter through the native API, callback contract tests, package metadata and actual pinned RetroArch macOS qualification. A fake host cannot establish real frontend loading. S1, S4. |
| Save/load continuation and durable persistence | Players expect progress to survive and snapshots to resume correctly | HIGH | **Interactive.** Fixture must read and use prior state, including fresh instance/process reopening. Separate snapshots, persistent media, replay and ABI identities; test stale persistence acknowledgements and failed restoration. Not a v0.1 compatibility promise. S3–S6. |
| Practical media importer and useful BIOS/set diagnostics | A playable release must accept a supported real media path | HIGH | **Games.** Select one practical format outside the native core; identify regions/revisions, missing or wrong BIOS and unsupported profiles. Diagnostic normalization alone does not establish commercial-media usability. S3, S7, S8. |
| Profile-specific hardware and game behavior | Users expect advertised games and configurations to work beyond boot | HIGH | **Games.** BIOS boot, required interrupts/banking/protection, sound/video and persistence must satisfy named scenarios. Track AES/MVS, board, region, BIOS and cartridge revision separately. Preserve original slowdown. S2, S3, S6. |

### Differentiators (Competitive Advantage)

These are proposed sources of value, not claims that competitors lack them. Prioritize embedding reliability and inspectable evidence rather than feature count.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Ordinary API plus redistributable diagnostic as the release demonstration | A fresh integrator can reproduce meaningful execution without commercial media | MEDIUM | **Start in SDK.** Publish original source, build recipe, provenance and exact expected observation. Differentiate by reproducibility; hardware accuracy still needs independent evidence. S1, S4, S6. |
| Small host-independent C implementation with audited ownership | Supports FFI, headless diagnostics and multiple consumers with few imposed services | HIGH | **Start in SDK.** Keep runtime and chosen dependencies in C; document every imported modification. Acceptance depends on actual builds and isolation checks. S1, S3, S5. |
| Claim-level evidence and explicit limitations | Integrators can assess whether their exact use case is supported | MEDIUM | **Start in SDK, expand with capabilities.** Keep safety, determinism, conformance, compatibility, throughput and frontend behavior distinct. Oracle ancestry and skipped/unknown states are visible. S3, S6. |
| Bounded traces and small behavior-focused reproductions | Researchers and maintainers can locate the first divergence | MEDIUM | **Add only to support concrete investigations.** Optional traces use emulated timestamps and finite storage; diagnostics must not perturb execution semantics or expose private bytes publicly. S5, S6. |
| Equivalent native and frontend diagnostic observations | Adapter bugs can be separated from emulation bugs | MEDIUM | **Interactive.** Compare like-for-like raw output and scripted input; host resampling/presentation has a separate contract. S4–S6. |
| Reliable upgrade and compatibility policy after real consumer experience | Reduces downstream churn and silent save loss | HIGH | **Later.** Freeze only contracts exercised by at least two consumers; snapshots may remain version-bound while durable saves have their own policy. S1, S3–S5. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full game/BIOS/video/audio implementation in v0.1 | Immediate player appeal | Replaces the selected diagnostic SDK with an unbounded machine implementation | Ship the real CPU/bus slice, then the selected interactive diagnostic. |
| Bespoke game library GUI, device management or networking inside the core | Convenient all-in-one experience | Creates another product and entangles deterministic machine behavior with host lifetimes | Use existing frontends and explicit native boundaries; SDL3 only for a recurring unresolved integration need. |
| Universal compatibility or hardware-perfect badges | Simple marketing | Conceals untested configurations and oracle uncertainty | Versioned scenario inventory with exact attainment levels and known discrepancies. |
| Commercial ROM/BIOS bundles or publicly uploaded private traces | Easy demos and bug reproduction | Redistribution rights are not established; traces can contain proprietary bytes | Original permissive fixtures and opt-in private local scenarios with scrubbed public summaries. |
| Silent overclocking, frameskip or removal of hardware glitches | Higher apparent speed or cleaner output | Changes guest behavior and invalidates conformance claims | Preserve defaults; revisit separately labeled deviations only with demonstrated user demand and tests. |
| Immediate JIT, SIMD or intra-machine threads | Anticipated speed | Adds correctness/portability complexity before a representative bottleneck exists | Audited interpreter and scalar reference paths; optimize profiles from meaningful workloads. |
| Rewind, run-ahead and rollback before complete state | Attractive latency/session features | Incomplete restoration or repeated durable side effects can corrupt behavior and saves | Prove continuation, deterministic replay, side-effect policy and snapshot cost first. |
| Permanent ABI/state compatibility from the first alpha | Appears reassuring for integrations | Freezes unexercised contracts and conflates unrelated compatibility promises | Explicit pre-1.0 evolution; separate ABI, snapshot, replay and durable-save versions. |
| Multi-system plugin framework, CD/Pocket support or multiple default CPU backends | Future flexibility | Expands unsupported combinations and maintenance before cartridge scope is established | Concrete MVS/AES modules and one qualified production backend. Revisit other systems only for a funded use case. |
| Always-on telemetry, credentials or cloud services | Centralized reporting | Unnecessary host coupling for a local C library | Local structured results and optional explicitly authorized external automation. |

Anti-features express project scope and tradeoffs (S1, S3–S6), not claims that these features are impossible or universally undesirable.

## Feature Dependencies

```text
Pinned C backend + license/state/timing audit
  -> instance-safe CPU and bus execution
  -> original diagnostic through ordinary bounded native API
  -> installed/relocated consumer executing that diagnostic
  -> qualified complete SDK alpha artifacts

CPU/bus execution + explicit scheduler + accepted Z80/YM2610 components
  -> selected video/input/real sound diagnostic
  -> native/libretro equivalence + actual RetroArch macOS qualification

Complete mutable-state model + deterministic boundaries
  -> snapshot continuation and fresh-instance restoration
Persistent medium model + export/acknowledgement contract
  -> fresh-process durable persistence
Both + explicit side-effect policy + measured costs
  -> optional rewind/run-ahead; rollback needs additional host/network work

Interactive behavior + supported BIOS/profile + practical importer
  -> first private game scenario + public diagnostic equivalents
  -> hardware-family coverage -> representative profiling -> justified optimization
```

### Dependency Notes

- **Package scaffolding and evidence schema can proceed alongside backend qualification.** A shippable SDK still depends on real execution in the installed consumer; automation alone is not the milestone outcome.
- **State inventory starts during backend acceptance.** Public serialization and continuation are next-milestone features. Full sound contextization must not block the CPU-only alpha.
- **Original diagnostic bootstrap and original BIOS boot are distinct.** The former is sufficient for the SDK; the latter needs independent evidence for a supported game/profile.
- **The libretro adapter depends on the native API.** It must not introduce a second emulation path or dictate process-global native state.
- **Hardware measurements resolve specific uncertainty.** Missing physical evidence narrows a conformance claim without stopping unrelated integration work.

## MVP Definition

### Launch With (v0.1 — CPU/bus diagnostic SDK alpha)

- [ ] Accepted pinned C 68000 backend with bounded adaptation decision, license notices, mutable-state inventory and timing limits.
- [ ] Opaque native lifecycle, diagnostic media normalization, explicit ownership/errors/limits and bounded deterministic execution.
- [ ] Original redistributable guest program with a justified result through the ordinary API; actual independence and failure-path evidence.
- [ ] Offline source package, static/shared builds, installed/relocated C consumer and compiled example; exact exercised platform matrix.
- [ ] Proportionate boundary/property/fuzz/sanitizer evidence and measured diagnostic cost/memory/build baselines. Gameplay performance remains unmeasured.
- [ ] Honest supported-subset documentation and a complete, traceable unsigned SDK alpha with qualified release gates.

### Add After Validation (next milestone — interactive diagnostic)

- [ ] Selected graphics/input and real chip-generated audio — begin after CPU acceptance and specific Z80/YM2610 feasibility work.
- [ ] Thin libretro adapter and actual RetroArch macOS load/run/unload — qualify after deterministic raw outputs exist; retain exact frontend/core/configuration identities.
- [ ] Snapshot continuation and durable persistence — implement against complete state/device models and a guest that demonstrably consumes restored data.
- [ ] Optional minimal SDL3 host — only if it removes a recurring blocker that native tests and the selected frontend cannot resolve.

### Future Consideration (no promised release number)

- [ ] First commercial-game scenario — after one practical importer, BIOS/profile evidence and lawful private inputs are available. Select by hardware simplicity and reproducibility.
- [ ] Banking/protection/raster/audio expansion — each new family requires a minimal fixture, provenance and representative scenario.
- [ ] Additional modes/boards/peripherals — only with explicit source evidence, fixtures and a maintained target configuration.
- [ ] Direct Playstead integration and stronger API stability — after a real integration spike and second consumer expose requirements; existing process launching is not established native FFI.
- [ ] Performance acceleration and broader platforms — after representative profiles or a supported consumer demonstrate need; keep scalar behavior as reference.
- [ ] Rewind/run-ahead, achievements and netplay — only after state, memory-inspection, side-effect and host contracts needed by each are separately justified.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Executable CPU/bus diagnostic and qualified backend | HIGH | HIGH | P1 |
| Safe deterministic native instances and bounded errors | HIGH | HIGH | P1 |
| Offline installed consumer/package, example and release | HIGH | MEDIUM | P1 |
| Honest capability/evidence reporting | HIGH | MEDIUM | P1 |
| Interactive video/input/sound diagnostic | HIGH | HIGH | P2 |
| Actual RetroArch qualification | HIGH | MEDIUM | P2 |
| Continuation and durable persistence | HIGH | HIGH | P2 |
| Practical commercial-media importer and first game profile | HIGH | HIGH | P3 |
| Broader cartridge mechanisms and modes | HIGH | HIGH | P3 |
| Optimization, advanced session features and additional platforms | CONDITIONAL | HIGH | P3 |

**Priority key:** P1 is required for v0.1; P2 belongs to the outlined next milestone; P3 requires its stated revisit trigger. P2/P3 are not spare-capacity additions to v0.1.

## Competitor Feature Analysis

This is a qualitative comparison of official product descriptions, not an executed accuracy or performance comparison. It does not rank popularity or infer missing competitor capabilities.

| Feature | Geolith | FBNeo/libretro | Glueyneo Approach |
|---------|---------|----------------|-------------------|
| Scope and media | Current README advertises AES/MVS/CD/CDZ; cartridge loading uses `.NEO` and requires appropriate BIOS | Broad arcade/system scope; documentation describes archive/set and BIOS requirements | MVS/AES cartridges only; diagnostic normalized regions now, one practical importer before game usability claims |
| Interactive features | Describes a playable Neo Geo experience with explicit accuracy caveats | Documents rewind, run-ahead, netplay and achievements | Selected interactive diagnostic next; advanced features await state and side-effect evidence |
| Accuracy claims | Separates instruction-level CPUs and best-effort video from its broad playability claims | Official documentation discusses accuracy and deliberate quality-of-life changes | Record hardware evidence, scenario compatibility and optional deviations separately |
| Integration lesson | Simple cartridge format can aid integration but implies conversion/identity work | BIOS/set mismatch and state-version questions need usable diagnostics | Make ownership, content errors, capability limits and reproducible examples part of the deliverable |

S7 and S8 support the competitor descriptions at MEDIUM confidence. Their actual behavior was not run here. The fresh Geolith README has broader system scope than the dated preparation summary; preserve that distinction without broadening Glueyneo's scope.

## Sources

| ID | Source and date/revision | Supported Claim | Limitations / Confidence |
|----|--------------------------|-----------------|--------------------------|
| S1 | [Current project contract](../PROJECT.md), initialized 2026-10-01 | v0.1 scope, next milestone and constraints | Authoritative local scope; no implemented behavior claimed |
| S2 | [Preparation brief](../preparation/BRIEF.md), 2026-10-01 | Intended users, core value and eventual outcomes | User-intent synthesis, not market survey or implementation evidence |
| S3 | [Decision register](../preparation/DECISIONS.md), PREP-D-01–PREP-D-44, 2026-10-01 | Adopted design/scope defaults and revisit conditions | Planning provenance; detailed contracts remain subject to bounded experiments |
| S4 | [Roadmap seed](../preparation/ROADMAP-SEED.md), 2026-10-01 | Vertical milestones and meaningful acceptance | Proposal superseded by current PROJECT and eventual REQUIREMENTS/ROADMAP |
| S5 | [C core architecture](../preparation/C-CORE-ARCHITECTURE.md), 2026-10-01 | Ownership, scheduling, state and real consumer constraints | Dated research with source ledger; all API details proposed |
| S6 | [Quality/evidence plan](../preparation/QUALITY-PERFORMANCE-AND-CI.md) and [hardware/ecosystem](../preparation/NEOGEO-HARDWARE-AND-ECOSYSTEM.md), 2026-10-01 | Distinct evidence dimensions, fixture ancestry and broader hardware coverage | No measured Glueyneo results; reused source claims retain original limitations |
| S7 | [Geolith official README](https://github.com/libretro/geolith-libretro/blob/master/README), accessed 2026-10-01 | Current advertised scope, cartridge format and timing caveats | MEDIUM; current upstream description/search retrieval, not independent verification. Pinned raw README fetch failed; current text must not be attributed to the preparation pin |
| S8 | [FBNeo official Libretro documentation](https://docs.libretro.com/library/fbneo/), accessed 2026-10-01 | Media/BIOS integration and mature interactive features | MEDIUM; living product documentation, publication revision not stated; no executable evaluation |

### Research Method and Open Questions

The installed research-plan seam selected `jina` for two targeted source checks. That provider was unavailable, so built-in web retrieval/search was used; official descriptions were cross-checked with the preparation. `classify-confidence --provider websearch --verified` returned **MEDIUM**, which is the external finding tier used here. Digests were cached with the pinned-fetch failure and current-source substitution explicit. Local scope is a project instruction, not a provider-derived empirical finding; priorities/dependencies are recommendations based on that scope.

Unresolved questions are the CPU adaptation budget/outcome, exact supported diagnostic bus subset, compiler/platform matrix, next-milestone firmware strategy and sound acceptance, first commercial importer, and physical evidence for disputed hardware behavior. There is no direct user-adoption study or independent competitor benchmark in this research. These gaps warrant bounded phase research, not added v0.1 scope.

---
*Feature research for Glueyneo. No implementation, compatibility or performance claims are established by this document.*
