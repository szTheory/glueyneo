# Project DNA: transferable lessons from active sibling projects

Status: preparation research, not an implementation plan or a claim of passing CI. Inspected 2026-10-01. This report recommends practices for a portable C emulator; it does not import Elixir, Phoenix, Electron, or their deployment architecture.

## Method and evidence boundary

Read project instructions, selected current source and tests, workflow definitions, recent Git history, and relevant planning/postmortem records. The sample covers the three requested projects plus ExifCleaner's closely related native companion and Lockspire. These repositories show recent committed activity; directory modification times were not used. This is a selective investigation, not an audit of every historical decision or every commit.

All source repositories were read only. No tests, builds, remote checks, or release actions were run. Reported test counts and CI durations are historical receipts, not newly reproduced measurements. No private fixture registry, environment file, credential, certificate, ROM, save, or screenshot was opened. Repository labels and relative paths replace personal filesystem paths and remote identities.

| Repository label | Inspected commit | Commit date | Sample emphasis |
|---|---|---|---|
| Playstead | `1de3e954166eaf0a52fe0e4a950b46756139884d` | 2026-09-28 | Adapter, save compatibility, homebrew probes, continuation qualification |
| LatticeStripe | `66379aeb38cf3f5f7dd4cb36b700a275ee066c76` | 2026-09-25 | Public API, documentation, CI, automated releases, adopter smoke |
| ExifCleaner workspace | `32eb66efec18df9bfb428d6733cf771e666db268` | 2026-10-01 | Milestone doctrine and accumulated lessons |
| ExifCleaner Electron | `c100554eebf495e7c35b9ac3854fa21dc9d63f68` | 2026-09-28 | Native installed artifacts, negative controls, publication |
| ExifCleaner Node | `7695c60d95cf3271f76187dac1d65011f011fa59` | 2026-10-01 | CI scope/cost, shared oracle preparation, paired benchmarks |
| Lockspire | `8fadb0984de9252475e8390bf4338c4df055f934` | 2026-10-01 | Host ownership, CI deduplication, recent fixture failures |

Selected history corroborates the documents: LatticeStripe `260edf43` (2026-09-24, milestone review), `1e83a990` (2026-09-25, release 2.3.0), and `cad59ca2` (2026-09-25, release-truth refresh); Electron `aee11dc` (2026-09-28, app rollback-route proof); Node `7695c60` (2026-10-01, failed-oracle-build recovery and cache-path containment). These subjects are paraphrased without author identities.

Playstead had existing uncommitted additions to `AdapterHost.swift` and the continuation qualification ledger. Their diffs were inspected: the added process-identity helper and follow-up attempts are excluded from snapshot evidence. The committed ledger independently records the same blocked qualification. Other selected evidence files were clean when checked.

## Eighteen practices to carry forward

### 1. Make the host boundary the product boundary

LatticeStripe passes configuration explicitly and delegates transport, JSON, and retry behavior through narrow interfaces. Lockspire leaves account ownership and product policy to its host. Glueyneo should likewise expose an opaque instance and explicit input/output, persistence, and diagnostics contracts. Frontends own files, devices, presentation, scheduling, and optional networking. This makes C, Swift, and other consumers practical without adopting a framework. Keep adapters concrete until a second real consumer proves a shared abstraction. **Avoid:** global mutable emulation state, hidden workers, and a generic plugin framework invented before use. [DNA-05, DNA-19]

### 2. Treat the public API as a compatibility commitment

LatticeStripe records the compiled public surface and tests deterministic generation, internal exclusions, and redaction-related protocol implementations. A baseline change requires a compatibility decision. For C, keep a small public header, export only intended symbols, compile C and C++ consumers, and version structures and serialization deliberately. A symbol list alone cannot prove calling convention, structure layout, or behavior. **Tradeoff:** strong contracts slow accidental API expansion and make intentional evolution reviewable; do not freeze speculative emulator internals. [DNA-06]

### 3. Separate persistent saves, machine states, and durable storage

Playstead distinguishes battery saves from emulator states and separates compatibility fields from provenance. It also excludes simultaneous writers to one save. Glueyneo should expose explicit persistent regions, coherent byte snapshots, dirty generations, and host acknowledgements after the host's durability policy succeeds. The core must distinguish a snapshot from a committed disk write. Save states need their own format/version/configuration identity. **Avoid:** presenting process termination or a nonempty save file as proof of safe flush or resumed gameplay. [DNA-01, DNA-02, DNA-04]

### 4. Build deterministic automation into the ordinary integration seam

Playstead's current continuation gate remains blocked because the exact installed emulator has not qualified noninteractive script loading, deterministic input, and a repeatable visible-state oracle. Glueyneo can prevent this integration debt with deterministic stepping, recorded input, explicit stop boundaries, and headless video/audio observations available through the same core API used by frontends. Prove save → shutdown → fresh instance → load → expected resumed behavior. **Avoid:** a test-only simulator that bypasses the shipped machine. [DNA-04]

### 5. Record what each fixture can actually establish

Playstead's simple SRAM writer proves writes and flush observations; its counter resets on boot and cannot establish restored progression. Its startup/linker code also required a fix for writable `.data` placement and initialization, previously masked by a program with no writable globals. Build small Neo Geo diagnostics with explicit assumptions and self-checks, including the test program's startup behavior. A playable title, synthetic probe, CPU vector, and physical-hardware capture answer different questions. **Avoid:** promoting convenient fixture success to platform compatibility. [DNA-03]

### 6. Use independent evidence and targeted negative controls

ExifCleaner pairs a reference implementation with independent payload checks, hostile corpora, metadata-generating properties, and deliberate mutations that must fail. For glueyneo, combine instruction vectors, hardware documentation/captures, differential traces, metamorphic properties, and deterministic homebrew scenarios. Agreement with another emulator is useful evidence, not proof when both may share a mistake. Demonstrate that important gates reject a known bad timing, pixel, save, or bounds mutation. **Tradeoff:** use negative controls for consequential invariants; do not construct a second verification platform for every trivial assertion. [DNA-13, DNA-14]

### 7. Make an empty or skipped test selection visible

Electron checks that named negative controls actually executed, rather than trusting a zero process exit. Playstead distinguishes process doubles from real continuation qualification and preserves a blocked result. Require nonempty test manifests and explicit executed/skipped/unsupported counts for core conformance, frontend smoke, and release jobs. A required target that could not run cannot become compatibility evidence. **Avoid:** guards that return successfully when a fixture or emulator is missing. [DNA-04, DNA-14]

### 8. Test the artifact an adopter receives

LatticeStripe's release smoke copies its adopter into an isolated directory, removes the lock, resolves an exact published registry version, verifies registry provenance, strips credentials, and runs a real integration flow. Electron installs and exercises packaged applications. Glueyneo should install its CMake package to a clean prefix and compile a tiny external consumer against that installation; exercise static/shared outputs when both are shipped. Add a frontend adapter smoke and release-download smoke as those products exist. **Avoid:** source-tree include paths or undeclared build dependencies making the example succeed. [DNA-08, DNA-10, DNA-14]

### 9. Make documentation executable without locking arbitrary wording

LatticeStripe enforces public surface, version prose, warning-free docs, and documentation truth; its exact-string prose tests also demonstrate a maintenance tradeoff. Prefer compiled examples, generated option/error/API tables, checked commands, and link checks for glueyneo. Keep explanatory prose editable. Current source and evidence override old planning: ExifCleaner Node's generated `AGENTS.md` still describes WebP-only scope while current source and qualification cover PNG/JPEG. **Avoid:** duplicating mutable support claims across many independently maintained documents. [DNA-05, DNA-07, DNA-13, DNA-16]

### 10. Narrow expensive CI only with an explicit safe rule

Node's scope classifier defaults unknown paths, invalid diffs, and unrecognized contexts to full qualification; release paths always receive full scope. Its historical docs-only probe used 2.42 job-minutes against a 25.68 job-minute baseline. Glueyneo should start with a compact matrix, then introduce path-based reductions only where dependency boundaries make them sound. C platform sensitivity means a parser change may still warrant compiler/sanitizer coverage. Use one always-reporting aggregate required check. **Avoid:** inheriting Node's many required matrix contexts, which needed no-op jobs after skipped names blocked merges. [DNA-08, DNA-16]

### 11. Remove duplicated work before inventing sharding

Lockspire's earlier CI audit removed a duplicate security scan and added missing minimum-version coverage before considering sharding. Node discovered separate workers/modules repeatedly cold-building the same oracle tools. Measure wall time, summed job time, queue time, setup cost, and slow tests separately. Use Ninja/CTest bounded parallelism matched to available CPU and memory; avoid multiplying build parallelism by test-worker parallelism. Shard only after measured bottlenecks justify it. **Counterexample:** a heavily parallel graph can spend more runner minutes while hiding a serial setup bottleneck. [DNA-16, DNA-18, DNA-20]

### 12. Treat caches as acceleration, never authority

Node now prepares oracle tools once per job, claims the directory exclusively, atomically writes completion last, and verifies executable identities when loading it. It intentionally does not persist those binaries between jobs. For glueyneo, begin with compiler caching where it helps; include toolchain, target architecture, build mode, sanitizer/options, and relevant inputs in compatibility boundaries. Preserve a cold-build path. **Avoid:** trusting a cache-hit flag as integrity evidence or sharing mutable build directories among incompatible jobs. [DNA-08, DNA-18, DNA-20]

### 13. Isolate test resources before increasing concurrency

Playstead found a shared process registry could terminate another test's emulator. Lockspire's recent failure census found shared fixture records and fixed identities contaminating concurrent cases; it repaired ownership and uniqueness rather than relaxing product constraints. Emulator tests need instance-local state, owned temporary directories, unique process identities, fixed seeds, and cleanup of only their own children. Exercise multiple core instances to detect hidden globals. **Avoid:** application-name-wide process cleanup, shared save paths, and rerunning flakes until green. [DNA-01, DNA-20]

### 14. Compare real candidates and preserve raw performance evidence

Node benchmarks distinct packed baseline/candidate artifacts on the same runner, alternates execution order, retains observations, checks correctness first, and specifies its percentile estimator. Transfer artifact identity, workload identity, warmup policy, raw observations, allocation/RSS measurements, and reproducibility. Emulator priorities are frame deadline misses, audio underruns, throughput, and memory on defined hardware. Shared-runner timing initially informs review; deterministic regressions still fail. **Avoid:** claiming p99.999 from tiny samples, selecting favorable reruns, or copying another product's thresholds and elaborate calibration machinery without need. [DNA-13, DNA-17]

### 15. Keep observability optional, bounded, and private

LatticeStripe documents synchronous telemetry handlers and their blocking cost. ExifCleaner prohibits runtime telemetry; its restriction serves that product, not every library. Glueyneo should offer optional counters and bounded diagnostic/trace hooks with explicit units and lifetimes. Keep clocks, formatting, allocation, and callbacks out of hot loops when disabled; measure the enabled cost. Hosts own export. **Avoid:** per-instruction logging by default, filenames or ROM/save data in public receipts, and a background network client in the core. [DNA-11, DNA-13]

### 16. Bind merge and release decisions to the tested revision

LatticeStripe validates a concrete release PR and current head before merging; Electron publishes the artifacts from the successful trusted-main workflow run and checks downloaded bytes. Glueyneo should use PRs, protected main, an aggregate gate, an automated release PR, and publication of artifacts already tested for the release revision. Keep release operations idempotent and published tags immutable. The owner has authorized routine green merges/releases for this project; other repositories' manual-approval policies do not override that instruction. **Avoid:** rebuilding unrelated bytes during publishing or executing untrusted PR code with publishing credentials. [DNA-09, DNA-12, DNA-15]

### 17. Make closeout maintain a rolling roadmap

ExifCleaner's milestone guide keeps near/mid/long horizons and promotes work by measured user outcomes, while LatticeStripe records the cost of accumulating unreviewed local-main commits. At each glueyneo phase, reconcile requirements with executable evidence, update docs, open/finish the PR, and disposition relevant issues. At milestone close, identify the weakest useful quality dimension, refresh current/next/candidate milestones, and retire superseded advice. Backlog ideas remain hypotheses until promoted. **Avoid:** making every discovered improvement part of the current release or delaying all review until milestone end. [DNA-12, DNA-13]

### 18. Budget the verification machinery itself

ExifCleaner's guide records that evidence ceremony consumed weeks and that a reusable qualification kit accelerated the next format. Lockspire documents an overbroad source scan that confused a path string with a file read, plus synthetic history reconstructed from current rather than historical blobs. Keep a small set of reusable behavioral gates with clear failure meanings; retire redundant checks. When a second failure shares a cause, repair the class. **Avoid:** phase-number logic in runtime code, sprawling regex policy suites, and static report counts presented as fresh proof. [DNA-13, DNA-17, DNA-20]

## Playstead integration and fixture findings

The present Mac adapter launches an external mGBA executable through `Foundation.Process`; no in-process C binding was observed. Its declared seam includes argv/configuration, save location/glob, flush triggers, on-demand-flush capability, maximum loss window, media byte sizes, proven media, and compatibility/provenance fields. It distinguishes archive digest from executable digest and verifies the executable before launch. These are requirements for a future glueyneo adapter spike, not evidence that dropping in a Neo Geo core already works. [DNA-01]

`SaveCompatibilityGate` is currently explicit GBA-oriented logic: system, save kind, medium, size, and exact ROM identity or certain title matching. Although comments describe future generic binding fields, the implementation does not dynamically evaluate arbitrary `binding_fields`. Neo Geo backup RAM, memory cards, and states require their own truthful adapter contract. [DNA-02]

| Fixture | Observed provenance and build | What is established | Limitation |
|---|---|---|---|
| AerevenAdvance | Owner-supplied GBA homebrew recorded privately; tracked guide names the private registry but contains no public redistribution grant or reproducible public source pin | Existing local game/save/recovery fixture and prior observations | Private recovery lane; do not redistribute or assume public CI permission. Does not test Neo Geo. |
| `savetest` | Playstead's own `playstead-mac/spike/testrom/` at the Playstead snapshot above; `main.c` and `crt0.s` explicitly declare MIT | Automated SRAM writing and emulator lifecycle/flush probes | Resets counter on boot; zeroed logo region is emulator-specific; no physical-hardware qualification observed. |

The `savetest` recipe runs `arm-none-eabi-gcc` for ARM7TDMI, compiles startup plus C11 source, links without a standard library using `linker.ld`, converts ELF to raw bytes with `arm-none-eabi-objcopy`, then runs `fix-header.py`. The compiler is not pinned in the script; no reproducible build was executed here. Its `-ffast-math` flag is not a recommendation for glueyneo. No direct reference to either fixture was found in the main hosted CI workflow or main Mac verification runner inspected. [DNA-03]

Recommend a corresponding self-authored Neo Geo diagnostic collection with per-file license, immutable source revision, pinned toolchain, build recipe, expected observations, and explicit emulator/hardware coverage. Keep private commercial-ROM compatibility testing local and publish only sanitized aggregate evidence. AerevenAdvance's successful recovery transport and the currently blocked fresh continuation oracle must remain separate facts. [DNA-03, DNA-04]

## Source ledger

All IDs inherit the repository snapshot and inspection date above. Paths are repository-relative. These are local primary project records; archived receipts retain their original limitations. No cited workflow was verified against current hosted branch protection or current GitHub service behavior during this investigation.

| ID | Repository and paths | Evidence used |
|---|---|---|
| DNA-01 | Playstead: `playstead-mac/Playstead/Adapter/AdapterHost.swift`, `AdapterPin.swift`, `AdapterExit.swift` in that directory | Process ownership, mutex, integrity checks, exit and capability contracts |
| DNA-02 | Playstead: `playstead-mac/Playstead/Saves/SaveCompatibilityGate.swift` | Actual compatibility comparisons versus future-facing comments |
| DNA-03 | Playstead: `playstead-mac/docs/TEST-FIXTURES.md`; `playstead-mac/spike/testrom/{main.c,crt0.s,linker.ld,build.sh,fix-header.py}` | Private fixture policy; self-authored probe; startup and build limits. `main.c`/`build.sh` last changed at `35c17a8e12eb03e77beca5fdca5e5f0e233e9368`, 2026-08-30; use the newer whole-tree snapshot for startup fixes. |
| DNA-04 | Playstead: `playstead-mac/docs/CONTINUATION-PROTOCOL.md`; `.planning/phases/06-recovery-proof-ci-and-e2e-pipeline/06-CONTINUATION-QUALIFICATION.md` | Recorded blocked qualification, separate process-double proof and real oracle |
| DNA-05 | LatticeStripe: `CLAUDE.md`; `lib/lattice_stripe/client.ex` | Explicit client/configuration, narrow runtime interfaces, contributor conventions |
| DNA-06 | LatticeStripe: `test/lattice_stripe/api_surface_lock_test.exs`; `lib/lattice_stripe/api_surface.ex` | Public surface, deterministic snapshot, internal exclusions |
| DNA-07 | LatticeStripe: `test/lattice_stripe/docs_truth_test.exs`; `CLAUDE.md` | Documentation/version truth checks and prose-lock tradeoff |
| DNA-08 | LatticeStripe: `.github/workflows/ci.yml` | Minimum/current matrix, optional-dependency absence, adopter, cache keys, aggregate gate |
| DNA-09 | LatticeStripe: `.github/workflows/{release.yml,release-pr-automerge.yml}`; `scripts/maintainer/{release_candidate_check.sh,release_evidence_check.sh}` | Revision-bound release automation; historical bot-trigger comments require fresh GitHub documentation checks |
| DNA-10 | LatticeStripe: `scripts/maintainer/published_hex_adopter_smoke.sh` | Isolated exact-version registry adoption and credential removal |
| DNA-11 | LatticeStripe: `guides/telemetry.md`; `lib/lattice_stripe/client.ex` | Event units, optional request telemetry, synchronous handler cost |
| DNA-12 | LatticeStripe: `.planning/milestones/v1.12-phases/78-release-and-repository-closeout/78-EXECUTION-LEARNINGS.md` | Archived closeout/worktree/PR lessons; not new authorization policy |
| DNA-13 | ExifCleaner workspace: `.planning/MILESTONE-GUIDE.md` | Rolling roadmap, tiered qualification, automated verification, evidence-cost lessons |
| DNA-14 | ExifCleaner Electron: `.github/workflows/ci.yml` | Executed negative controls, native installed-artifact smoke, `.app` transport lesson |
| DNA-15 | ExifCleaner Electron: `.github/workflows/release.yml` | Trusted workflow/run/SHA binding and tested artifact publication |
| DNA-16 | ExifCleaner Node: `docs/ci-budget.md`; `scripts/classify_ci_scope.cjs`; `AGENTS.md` | Historical CI costs, conservative scope, matrix-context footgun, stale generated scope prose |
| DNA-17 | ExifCleaner Node: `docs/benchmark-admission.md`; `scripts/qualification/benchmark-report.cjs` | Paired artifacts, raw observations, correctness-first admission; substantial machinery to avoid copying wholesale |
| DNA-18 | ExifCleaner Node: `docs/ci-budget.md`; `scripts/qualification/build-oracles.cjs` | Once-per-job preparation, complete marker, binary verification and cache boundary |
| DNA-19 | Lockspire: `AGENTS.md`; `.github/workflows/ci.yml` | Embedded host ownership; current separate fast/integration/compatibility/adopter lanes |
| DNA-20 | Lockspire: `.planning/research/v1.35-ci-audit-summary.md`; `.planning/phases/140-bounded-operational-loose-end-triage/140-CI-FAILURES.md` | June 30 audit is historical; October 1 census documents fixture isolation, scan and historical-blob repairs |

## What remains unproven

No benchmark establishes glueyneo's performance yet. No sibling fixture proves Neo Geo hardware behavior. Public redistribution rights for the private homebrew collection were not established. Hosted permissions, secret provisioning, green-main status, and actual automatic publication require checks when glueyneo's repository and workflows exist. Preserve the principles here while keeping the initial machinery smaller than these mature repositories.
