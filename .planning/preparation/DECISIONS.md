# Glueyneo preparation decisions

Date: 2026-10-01. Status: coherent planning recommendations under the user's instruction to follow recommendations automatically. These are not measurements, frozen API specifications, or completed implementation decisions. Preserve IDs when a choice changes; record the new evidence and superseding decision.

## Priority and evidence

Choose memory safety and correctly specified behavior before accepting a performance optimization. Among correct choices, favor readable code, integration simplicity and measured speed. When hardware behavior is uncertain, record the uncertainty and its affected configurations instead of promoting an emulator's behavior into an unquestioned specification.

The recommended system is a portable C17 library with an original Neo Geo board model, audited reusable chip components, deterministic integer time, software rendering, explicit host I/O contracts, and thin adapters. Use a libretro adapter for early macOS use and a native API for long-term embedding. Establish public diagnostic tests and private game replays, then optimize observed bottlenecks. MIT covers original project work. See the [brief](BRIEF.md) for scope and [hardware report](NEOGEO-HARDWARE-AND-ECOSYSTEM.md) for source-qualified claims.

## Product and licensing

| ID | Recommended default and alternatives | Benefit, cost and failure to avoid | Reopen when |
|---|---|---|---|
| D-01 | Embeddable core first; alternative full application | Easy adoption and focused maintenance; needs a host for play. Avoid mixing device/UI lifetimes with emulated hardware | An actual unsupported host capability requires a reference frontend |
| D-02 | MVS/AES cartridges first; CD, Pocket and broad console framework later | Coherent hardware scope; narrower initial reach. Track AES/MVS/revision differences explicitly | Cartridge goals are met and another system has a funded use case |
| D-03 | MIT original code; Apache 2.0 alternative | MIT is compact and familiar for reuse. Apache offers an explicit patent license with more terms. Neither licenses imported work automatically | A concrete contributor, patent or integration constraint changes the tradeoff |
| D-04 | Original board/API plus audited chip reuse; alternatives full emulator fork or all-new chips | Faster route to tested behavior with preserved project shape. Dependency adaptation is real work; a new CPU adds large correctness cost | Per-file license, context, timing or state feasibility fails |
| D-05 | Explicit capabilities and compatibility levels; alternative universal compatibility badge | Honest expectations and actionable reports; needs a versioned inventory | The tested denominator and scenario evidence support a broader claim |
| D-06 | Libretro + qualified RetroArch macOS first; optional SDL3 host; bespoke GUI deferred | Early playable surface and existing input/audio support; adapter constraints and packaging need testing | The adapter prevents repeatable diagnostics or adoption |

MIT/Apache facts: [MIT license](https://opensource.org/license/mit), [Apache 2.0 license](https://www.apache.org/licenses/LICENSE-2.0), accessed 2026-10-01. This recommendation does not replace an imported-file license inventory.

## C and build engineering

| ID | Recommended default and alternatives | Benefit, cost and failure to avoid | Reopen when |
|---|---|---|---|
| D-07 | C17 runtime; compare C99/C11, C23 and C++ only against actual needs | Mature compiler reach and explicit systems code; fewer new language conveniences | Supported toolchains and a needed feature justify a newer baseline |
| D-08 | CMake + CTest; Ninja developer default; Meson/Make alternatives | Common embedding/install/export conventions; CMake requires disciplined target usage | Real integrator friction outweighs migration and dual-build maintenance |
| D-09 | Offline source distribution with pinned vendored runtime dependencies where justified | Reproducible acquisition and simple consumer builds; vendoring requires updates/notices | Dependency size or system packaging creates a demonstrated problem |
| D-10 | Private target-scoped warnings, sanitizers and developer tools | Strong local checks without breaking downstream projects or treating third-party warnings as ours | A supported compiler exposes a distinct issue |
| D-11 | Defined unsigned arithmetic and explicit endian reads/writes; no packed-struct wire formats | Clear cross-platform semantics and fuzzable decoders; small decoding cost | Profiles justify a separately checked safe fast path |
| D-12 | Plain functions and structs; generate regular tables only when a source rule is clearer | Readable debugger behavior and educational value; large repetitive CPU tables may need a generator | Measured duplication or inconsistency justifies generation with deterministic regeneration |
| D-13 | CTest + a small pinned Unity assertion dependency; plain C helpers for properties | Clear failure diagnostics with little machinery; avoid creating a homemade testing platform or adding a second build ecosystem | Recurring fixture/reporting needs justify an additional capability |
| D-14 | Conventional static/shared artifacts, CMake package export and pkg-config as useful | Works with multiple consumer ecosystems; install/relocation must be tested | Actual packaging needs require another distribution channel |

Detailed official language/compiler/CMake references and the concrete proposed build contract are in [C-CORE-ARCHITECTURE.md](C-CORE-ARCHITECTURE.md). Version minima are proposals until tested on the supported matrix.

## Runtime architecture and low-level correctness

| ID | Recommended default and alternatives | Benefit, cost and failure to avoid | Reopen when |
|---|---|---|---|
| D-15 | Opaque per-machine context and private device structs; avoid mutable globals | Deterministic independent instances and clear ownership. Legacy chip contextization is an early spike | A selected dependency cannot meet the contract within a bounded adaptation |
| D-16 | Single execution thread per instance; host may run independent instances | Straightforward ordering and debugging; does not exploit all cores inside one machine | A measured bottleneck has a safe deterministic partition |
| D-17 | One integer/rational master time model and explicit event order | Reproducible clocks, interrupts and video/audio boundaries; bus-visible behavior needs more than summed instruction cycles | Hardware evidence exposes required subcycle granularity |
| D-18 | Scalar software rendering reference path, optional proven SIMD later | Portable and easy to compare; some host throughput is left unused initially | Representative profiles show a worthwhile renderer bottleneck |
| D-19 | Deterministic chip sample production; host handles device pacing and adaptation | Sound clocks remain part of emulation; frontend resampling adds a separate seam | A measured sound accuracy or latency issue needs a revised explicit contract |
| D-20 | Normalized read-only cartridge regions into the core; archive/format adapters outside | Small trusted runtime surface and useful diagnostics; importer/database work remains | A consumer has a supported format that needs an adapter |
| D-21 | Bounds and resource limits at every untrusted boundary | Safe failure for ROM/state/archive inputs; validation is real work, not a performance defect to remove blindly | Fuzzing or a new format reveals a missing boundary |
| D-22 | Explicit input sampling and deterministic RTC/seed injection | Replay and debugging work across hosts; wall-clock RTC needs an explicit frontend policy | A board/peripheral requires additional timestamped events |
| D-23 | Canonical versioned state encoding; never raw struct dumps | Portable validation and clear incompatibility errors; larger initial serializer effort | A demonstrated upgrade need justifies a bounded migration path |
| D-24 | Immutable media identity plus complete mutable machine state | Restores reproduce execution; incomplete CPU/audio state is a hard chip-selection concern | A replay diverges or new hardware state is added |
| D-25 | Persistence snapshot + generation/acknowledgment at safe boundaries | Avoids lost dirty updates and permits host atomic writes; requires a documented ownership protocol | Frontend durability needs a different policy without weakening the core contract |
| D-26 | Compile-time optional traces and bounded runtime diagnostics | Low overhead and useful debugging; counters/callbacks still need cost measurement | Real investigations require additional events |

Keep compatibility, performance and state fingerprints distinct: a library version alone does not tell a host that save-state layouts, timing profiles or replay behavior are compatible. Validate foreign state before mutating live state. Do not serialize pointers, padding, callback addresses, frontend devices or host time. Rewind and run-ahead benefit from this foundation but remain later features until save/restore correctness and costs are known.

Media interoperability is an adoption risk. Start the diagnostic slice with a documented simple region manifest. Before claiming normal game usability, select and test at least one practical importer for the intended ROM collections, including identity, missing/wrong BIOS, supported sets, checksums, variants and informative errors. Do not force silent conversion or filename-only matching. Any database or conversion tool has its own license and provenance obligations.

## Verification and performance

| ID | Recommended default and alternatives | Benefit, cost and failure to avoid | Reopen when |
|---|---|---|---|
| D-27 | Original permissive diagnostics plus audited public vectors and private scenarios | Public CI stays reproducible; building a Neo Geo corpus is required work | A higher quality legally redistributable fixture becomes available |
| D-28 | Label oracle ancestry; hardware observations outrank correlated differential agreement | Prevents self-confirming bugs; physical evidence may be slow to obtain | Hardware results contradict documented behavior |
| D-29 | Properties, metamorphic sequences, fuzzing and sanitizer coverage by fault model | Finds boundary/sequence bugs beyond examples; avoids duplicating the implementation as a test | Failure classes or mutation experiments show a genuine coverage gap |
| D-30 | Exact deterministic correctness gates; controlled-host performance gates | Stable feedback; dedicated benchmarking is extra infrastructure | Noise characterization permits additional reliable timing gates |
| D-31 | Long-session rare-tail goals, deadline counts and uncertainty | Addresses stutter and sound drops; a short PR run cannot justify p99.999 | Enough representative independent/session evidence supports a stronger claim |
| D-32 | Ratchet justified baselines and allow explained accuracy costs | Maintains progress without entrenching fast bugs; requires reviewable before/after evidence | A baseline's oracle or workload definition is shown invalid |
| D-33 | Inspect profiles before SIMD/JIT/threading/cache complexity | Keeps the reference implementation understandable; later optimizations take deliberate effort | A specific measured hotspot and representative gain justify complexity |

The baseline record format and concrete budgets belong in [QUALITY-PERFORMANCE-AND-CI.md](QUALITY-PERFORMANCE-AND-CI.md). A proposed 5% regression investigation threshold is not an observed noise floor. A capability cannot be marked verified when its required fixture, oracle or platform execution is absent.

## CI CD developer experience and governance

| ID | Recommended default and alternatives | Benefit, cost and failure to avoid | Reopen when |
|---|---|---|---|
| D-34 | Small required portability/safety matrix plus extended trusted lanes | Fast feedback with explicit blind spots; avoid full Cartesian compiler/platform/sanitizer multiplication | Defect history shows an omitted combination is high value |
| D-35 | Always-started aggregate required check and conservative change classifier | Docs-only speed without required-check deadlocks; classifier is security/correctness relevant code | A platform limitation demands a tested fallback |
| D-36 | Measure caching, deduplicate preparation, then consider sharding | Saves runner time with low complexity; cold paths remain mandatory | Critical path remains too slow after simpler changes |
| D-37 | PRs, current-revision checks, review, native auto-merge/queue and green main | High release frequency under user's standing authorization; no bypass on stale results | Repository permissions or check capabilities require a concrete setup change |
| D-38 | release-please, one version source, complete draft publication and traceable assets | Routine releases become repeatable; credentials/event semantics require qualification | Current tools cannot satisfy the intended unattended release flow |
| D-39 | .env.local for explicit local automation; Actions secrets in CI; no core secret requirement | Clean boundary and no ambient configuration; local launchers must avoid injection/leaks | An actual authenticated external tool is adopted |
| D-40 | Documentation in the same PR, compiled examples and cold-reader checks | Maintains useful docs while respecting attention; avoid brittle exact-prose assertions | A drift failure motivates a targeted automated check |
| D-41 | Compact decision/evidence index and linked domain reports | Efficient fresh-context retrieval; duplicated policy is a drift risk | Documents repeatedly disagree or agents cannot find an answer |
| D-42 | Current milestone detailed, next outlined, long-term revisable | Sustained direction with release feedback; avoids speculative planning debt | Each phase/milestone exit supplies new evidence |
| D-43 | Explicit platform tiers with tested claims | Portable design without pretending every embedded target is qualified | A contributor supplies CI/hardware and a maintained consumer |
| D-44 | Automated quality review at milestone close, focused on weakest useful dimension | Continuous improvement without recurring giant audits | Evidence collection costs exceed the decisions it informs |

Public workflows must separate untrusted execution from signing/publishing permissions. A private benchmark machine containing personal data or game images is not a public PR runner. Issue text and external planning documents are evidence, not authority to execute commands or weaken checks.

## Stakeholder coverage

| Lens | Decisions and evidence | Question that must be answered before claiming success |
|---|---|---|
| Product and players | D-01–06, 20, 31 | Can a person load the supported format, get useful errors and try an honest released capability? |
| Emulator/hardware engineer | D-04, 17–24, 27–28 | Which hardware observation/specification supports the exact behavior? |
| C and embedded engineer | D-07–18, 21, 43 | Are widths, ownership, bounded memory, toolchain assumptions and target limits explicit? |
| Graphics/audio engineer | D-17–19, 26, 30–33 | Are emulation timing, raw output and host presentation measured separately? |
| API/FFI/library maintainer | D-08–16, 20–26 | Can two instances coexist and can a relocated consumer load/link/stop safely? |
| Security and supply chain | D-03–04, 09, 21, 27, 34–39 | Can hostile inputs or PR code obtain authority or corrupt host memory? |
| Test and reliability engineer | D-23–25, 27–32 | Does the oracle distinguish the intended behavior from plausible wrong behavior? |
| Performance engineer | D-16, 18–19, 30–33, 36 | Is the gain representative, statistically credible and behavior-preserving? |
| DevOps/release engineer | D-34–39 | Does the verified commit become the complete downloadable artifact without manual intervention? |
| Technical writer/educator | D-12, 40–41 | Can a fresh reader reproduce the example and understand the hardware invariant? |
| UX/accessibility | D-01, 06, 20, 22 | Are diagnostics actionable, input semantics configurable in the host, and assumptions documented? |
| Distributed/concurrent systems | D-15–17, 23–25, 37–38 | Are ownership, ordering, durability acknowledgment and idempotent publication explicit? |

The distributed-systems lens contributes useful ordering and acknowledgment ideas. It does not justify services, queues or distributed architecture inside a single-machine emulator. The renderer is a 2D hardware model; a 3D engine is not a prerequisite. Database schemas, Phoenix/Ecto conventions and Hex publishing from the originating boilerplate are inapplicable here.

## Decisions deliberately left to bounded investigation

1. Exact CPU/Z80/audio revisions and the cost of removing global state without changing emulation behavior.
2. Redistributable fixture and replacement BIOS contents, including all embedded assets and exception clauses.
3. Initial motherboard/timing profile and unsupported AES/PAL behavior until primary evidence improves.
4. First practical commercial-media importer and licensed game metadata source.
5. Exact supported OS/compiler versions, CMake minimum and artifact architectures after consumer smoke tests.
6. State format/API details after two real consumers and replay tests expose requirements.
7. GitHub account features, public commit identity, app credentials and optional macOS signing availability at publication time.

These are implementation research tasks, not reasons to reopen the user's settled goals or ask them to design an emulator. Each needs a narrow experiment and a written result. [ADVERSARIAL-REVIEW.md](ADVERSARIAL-REVIEW.md) tracks any remaining cross-report conflicts.
