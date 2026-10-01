# Pitfalls Research

**Domain:** Portable C Neo Geo MVS/AES emulator SDK
**Researched:** 2026-10-01
**Confidence:** MEDIUM overall; implementation feasibility remains unverified
**Scope:** v0.1 CPU/bus diagnostic SDK; next milestone interactive diagnostic. These are proposed gates, not passed checks. [PROJECT.md](../PROJECT.md) owns active scope; dated preparation preserves provenance.

Research consolidates the preparation review and targeted official-source checks. The research-plan seam selected Jina for URL extraction; no Jina tool was exposed, so built-in web search/open supplied primary-source checks. The installed confidence classifier returned MEDIUM for cross-checked `websearch` and LOW for `webfetch`, even with verification. Consequently source facts found only through direct fetch retain that conservative tier; no hosted workflow behavior or backend adaptation is claimed proven. Risk controls below are project recommendations, MEDIUM unless explicitly marked otherwise.

## Critical Pitfalls

### P1: A context API hides shared machine state and cold-init races

**What goes wrong:** Two machines corrupt each other's CPU, bus, exception or callback state. Serial runs pass while concurrent creation or an error path fails. Musashi's pinned CPU source contains global CPU/cycle/exception/jump-buffer storage; preparation and fresh stack inspection agree. [S1, S2]

**Why it happens:** Copying visible registers overlooks cycle counters, callback routing, lazy opcode tables, static temporaries and failure cleanup. A global current-instance pointer or whole-core lock conceals the contract violation.

**How to avoid:** Before selection, inventory every mutable global/static and callback in the actual compiled source closure, including generated code. Assign an owner and initialization rule to each. Shared tables must become immutable safely. Separate transient host jump buffers from guest state. Set an explicit adaptation budget and rejection criteria; preserve a small upstream patch set.

**Warning signs:** Sequential-only tests; warmed process before every case; hidden singleton routing; context memcpy as the sole audit; failures requiring process restart.

**Bounded evidence gate:** Two deliberately different instances must match isolated baselines when interleaved and run on separate host threads. Include simultaneous first creation in a fresh process, reset/destroy while another instance lives, allocation/load failures and distinct callbacks/buses. Use race instrumentation where supported and record unsupported coverage. Audit plus behavioral evidence is required; sanitizer silence alone is insufficient.

**Recovery:** Minimize contamination to a counterexample; fix ownership within the budget or reject/defer the backend and record the alternative decision. Do not silently weaken native independence.

**Phase to address:** v0.1 dependency feasibility, before ABI and bus contracts harden. Repeat the audit for future sound dependencies in the interactive milestone; do not require a full sound port for v0.1.

### P2: The compiled dependency is larger and less host-safe than its advertised CPU subset

**What goes wrong:** A nominal 68000-only library retains FPU/SoftFloat source, unreviewed license terms, global floating-point controls or process-level error handling. The pin's `m68kcpu.c` includes `m68kfpu.c` unconditionally; its Makefile adds SoftFloat 2b, and FPU paths contain stderr/exit behavior. These are source findings, not proof every path is reachable in a selected 68000 build. [S2–S5]

**Why it happens:** Feature macros are mistaken for removal from the source/build/distribution closure. A repository's license label is treated as a per-file inventory.

**How to avoid:** Produce exact copied/compiled/generated/distributed file lists. Demonstrate a minimal 68000 build closure, or audit every retained file's state, host calls, notices and redistribution terms. Inspect preprocessing, generated handlers, link dependencies and configuration together. Audit all error paths for exit, printing, file/environment/clock access and uncontrolled allocation. Treat SoftFloat's distinct terms as an explicit review item, not legal approval or rejection by label.

**Warning signs:** “FPU disabled” with no closure receipt; unreviewed `softfloat` directories in the archive; empty third-party manifest; callbacks that can terminate the host.

**Bounded evidence gate:** Build/link the selected configuration with documented inputs; retain closure and symbol/dependency evidence, per-file provenance and a reviewed host-safety inventory. Exercise representative unsupported opcode/exception paths and error translation. Compare behavior after removal/adaptation. Publication requires disposition of all shipped files, including generators and checked-in generated output.

**Recovery:** Remove genuinely unnecessary source with a documented patch and requalify; otherwise finish the retained-source review or select another backend within the declared budget.

**Phase to address:** v0.1 dependency selection and source/package admission. This is a selection blocker, not later cleanup.

### P3: A passing diagnostic proves its own assumptions instead of the hardware

**What goes wrong:** Implementation and expected output share an ancestor or generator; a startup bug masks initialized-data behavior; custom bootstrap success becomes an original BIOS or game-compatibility claim. [S1, S6, S7]

**Why it happens:** Convenient emulator vectors are treated as independent physical evidence; mailbox completion is confused with conformance; public-looking binaries lack actual fixture rights.

**How to avoid:** Record each assertion's origin: specification, physical observation, emulator-generated differential reference or Glueyneo regression. Include source revision, board/configuration, toolchain, expected observation and uncertainty. Audit code, startup, fonts/data/assets and resulting binaries separately. Prefer an original minimal diagnostic without proprietary firmware. Explicitly describe the bootstrap and supported CPU/bus subset.

**Warning signs:** Two references share a CPU engine; expected hashes regenerated after failures; no `.data`/BSS checks; only constant globals; an empty or skipped manifest reports success; license evidence is just a hash.

**Bounded evidence gate:** Run original diagnostic bytes through the ordinary native API and a real consumer; verify startup, named bus effects and nonempty assertion counts. One consequential deliberate wrong-behavior control must fail. Record oracle ancestry and unresolved hardware evidence; unsupported BIOS/video/audio claims remain unsupported.

**Recovery:** Narrow claims, replace correlated assertions with independently justified expectations, correct startup and regenerate fixtures only with an explained baseline change. Quarantine fixtures lacking redistribution evidence.

**Phase to address:** v0.1 diagnostic vertical slice and fixture admission; hardware comparisons and original BIOS/game claims belong to later qualification.

### P4: Cycle counts become an unsupported bus-timing promise

**What goes wrong:** Instruction overshoot, wrong bus access order or interrupt timing produces a plausible CPU result with incorrect device behavior. Wall-clock pacing leaks into guest time; optimization removes real hardware slowdown. [S1, S6]

**Why it happens:** Scheduler resolution is confused with backend observability. Adding a finer timestamp unit does not expose intermediate accesses.

**How to avoid:** Specify stop boundaries, actual time advanced, overshoot, interrupt acknowledgement, access widths/order and unsupported precision. Use defined integer arithmetic, checked lengths and explicit byte order. Native execution reads no wall clock and does not sleep; the host paces presentation.

**Warning signs:** Run always reports requested cycles; unexplained frame-sized stepping; endian pointer casts; signed shifts/overflow used as guest wraparound; debugger reads trigger device effects.

**Bounded evidence gate:** For the supported CPU/bus profile, exercise budget boundaries, zero/maximum limits, exceptions, mirrored and boundary addresses and known bus order. Compare split runs with an equivalent uninterrupted run at valid stop boundaries. Record exact limitations; defer raster/audio timing claims until those devices have their own evidence.

**Recovery:** Correct the timing contract and bus seam before adding devices; retain counterexamples and narrow precision claims where adaptation cannot supply the needed observability.

**Phase to address:** v0.1 feasibility and diagnostic execution; deeper device timing research at interactive milestone entry.

### P5: A release is green but stalls, publishes incomplete assets, or binds the wrong commit

**What goes wrong:** Staging waits for a draft's absent tag; retry ignores an existing draft because release-please reports no new release; moving main is rebuilt and published under an older version. [S8–S10]

**Why it happens:** Workflow outputs are treated as durable release state. A current schema option is assumed supported by an older action's bundled library. Tag, draft and build identities are conflated.

**How to avoid:** Pin the action and qualify manifest `simple` strategy plus draft behavior. The schema describes lazy draft tag creation and `force-tag-creation`; verify availability in the selected bundle. Persist/resolve draft ID, version and exact release commit; bind trusted build run and artifact digests to that commit. Stage and validate the entire expected asset set before publishing. Recovery must discover an existing draft independently of the new-release output. [S8, S9]

**Warning signs:** Checkout uses branch head; publication waits only on a tag event; `release_created` is the only retry path; assets uploaded after publish; checks belong to an old head.

**Bounded evidence gate:** Before enabling unattended publication, exercise interrupted staging, duplicate retry with no new release output, mismatched commit, missing asset and failed consumer cases. All unsafe cases must refuse publication; a valid retry must reuse verified identity and complete once. Verify downloaded bytes and the packaged diagnostic consumer. Immutable-release documentation recommends draft → assets → publish; fetched-only service evidence is LOW by helper classification and actual repository behavior remains a qualification task. [S10]

**Recovery:** Resume the matching draft from its verified manifest. Reject ambiguous identity. Correct published defects with a new release rather than replacing tested bytes or moving tags.

**Phase to address:** v0.1 delivery qualification after working SDK artifacts exist. No signed frontend or commercial-game qualification is required for an honest unsigned SDK alpha.

### P6: Automation authority and public evidence cross the wrong trust boundary

**What goes wrong:** Automation PR checks await approval; untrusted code gains publishing authority; private media, hashes, local paths or debugging metadata reach public logs/artifacts. [S7, S11]

**Why it happens:** Historical token advice is copied without checking current service behavior. A private benchmark machine is reused as a public PR runner. Scrubbing filenames is mistaken for scrubbing captures or archives.

**How to avoid:** Current GitHub docs say `GITHUB_TOKEN` PR opened/synchronize/reopened events create approval-required runs; dispatch events are exceptions, while other recursive events remain suppressed. Use a scoped GitHub App installation token for the unattended PR flow and qualify the actual event graph. Keep untrusted execution separate from publication credentials, trusted artifacts and private corpus access. [S11]

**Warning signs:** Approval banners on release PRs; expected push checks absent; write tokens available to checked-out PR code; uploaded emulator traces, save states, corpus fingerprints or debug paths; secret/env dumps.

**Bounded evidence gate:** Demonstrate current-head required checks for a bot PR and trusted publication flow with minimal permissions. Inspect staged files, commit identity, logs, archives, debug metadata and notices before release. Private scenarios stay outside Git/public CI; only reviewed public-safe summaries leave that boundary, with private fingerprints excluded by default. Missing account credentials remain a narrow external dependency.

**Recovery:** Stop affected publication, remove exposed authority, rotate any exposed credential and follow incident handling. Rebuild scrubbed artifacts; previously public sensitive bytes cannot be assumed retracted. Repair the event/permission graph without bypassing protections.

**Phase to address:** Every public fixture/commit admission and v0.1 delivery; private-corpus rules recur in later compatibility milestones.

### P7: State and persistence appear to work while losing continuation or durable writes

**What goes wrong:** Raw structs serialize pointers/padding; timers or pending output are omitted; restoring old guest bytes rolls back host dirty generations; an old acknowledgement clears newer writes. [S1, S6]

**Why it happens:** CPU registers are confused with the complete machine. ABI, snapshot, replay and durable-save compatibility share a single version.

**How to avoid:** Start complete mutable-state inventory during v0.1, but defer public snapshots/persistence. Later serialize explicit bounded fields and validate atomically. Separate canonical guest state from host callbacks, jump buffers, delivery counters and monotonic persistence generations.

**Warning signs:** Nonempty save file called continuation proof; dump of native struct; reset-on-boot counter as restore oracle; guest hashes include host timestamps/acknowledgements.

**Bounded evidence gate:** In the interactive milestone, prove uninterrupted versus save → destroy → fresh instance → restore continuation at equal output-consumption boundaries. Exercise malformed state leaving the live machine intact, restore after newer durable writes and late old acknowledgements. Version each contract separately and report unsupported combinations.

**Recovery:** Reject incompatible states explicitly, repair schema/ownership, preserve legitimate durable bytes and add minimized sequence regressions. Do not promise migration before implementing it.

**Phase to address:** Inventory in v0.1 feasibility; behavior and formats in the interactive milestone.

## Technical Debt Patterns

| Shortcut | Immediate benefit | Long-term cost | When acceptable |
|---|---|---|---|
| Serialized singleton adapter | Quick CPU experiment | Cannot fulfill independent native instances | Isolated feasibility experiment only; never v0.1 acceptance evidence |
| Custom diagnostic bootstrap | Removes proprietary BIOS dependency | Can mask BIOS/reset assumptions | v0.1 with exact contract and startup assertions |
| Checked-in generated opcodes/diagnostic bytes | Offline and cross-build simplicity | Generator drift and unnoticed asset provenance | With pinned recipe, notices and separate regeneration evidence |
| Freeze every proposed API early | Apparent integration certainty | Expensive ABI constraints around untested devices | Avoid; let real SDK consumer constrain v0.1 |
| Large policy/test framework before execution | Visible automation progress | Delays useful emulation and multiplies maintenance | Avoid; one vertical diagnostic gate first |

## Integration Gotchas

| Integration | Common mistake | Correct approach and bounded gate |
|---|---|---|
| CMake package | In-tree consumer accidentally sees private headers | Install, relocate prefix, hide source/build paths and execute external static/shared consumers for shipped variants |
| Offline build | Warm dependency cache mistaken for offline source completeness | Cold build from release source with network unavailable; generators must run on build host or ship audited generated output |
| Allocators and buffers | Cleanup crosses allocators or failed load partially mutates state | Explicit ownership/lifetimes; failure injection and canary capacity tests through public API |
| Libretro / RetroArch | Native diagnostic success claimed as frontend qualification | Next milestone: actual pinned RetroArch macOS loading/input/output/unload smoke; keep singleton frontend seam outside native core |
| Playstead | Existing process launcher assumed to be native FFI | Future dedicated adapter experiment; historical sibling evidence is read-only provenance |

## Performance Traps

| Trap | Symptoms | Prevention / gate | When it breaks |
|---|---|---|---|
| Invented percentage or rare-tail budget | Hosted-runner noise flips acceptance | Record diagnostic workload/build/host identity and raw paired observations; calibrate before enforcing timing thresholds | First noisy baseline; no gameplay claim follows from v0.1 diagnostic speed |
| p99.999 from inadequate/correlated samples | Impressive number without sample count | Report count, estimator, worst stalls and correlation; a zero-failure binomial bound is not a latency percentile estimate | Rare events and workload transitions |
| Per-access formatted tracing | Trace-enabled results diverge in cost | Bounded numeric traces, drop counts, explicit enabled/disabled cost | CPU hot loops; measure before prescribing a threshold |
| Nested unlimited build/test parallelism | Memory pressure and longer critical path | Measure wall time and runner-minutes; bound workers by memory; remove duplicate preparation before sharding | Matrix expansion; hardware-specific threshold remains unmeasured |
| Overbroad CI skipping or trusted cache hit | Missing tests report green | Unknown diffs default to full scope, required aggregate reports executed counts, retain cold builds | First new file/configuration or incompatible cache entry |

For each performance failure, preserve raw evidence, fix workload/measurement defects first, then profile the representative implementation. Never relax budgets or select favorable reruns merely to restore green CI. These controls enter v0.1 baseline/CI work and expand with actual interactive workloads. [S7]

## Security Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Unchecked size arithmetic before span validation | Host memory corruption | Bounds before pointer arithmetic/multiplication; bounded parser/execution fuzz regressions in v0.1 |
| Guest-invalid input reaches assertion/exit | Host process loss | Structured errors, explicit unsupported operations, audited dependency failure paths |
| Root MIT label applied to all imports | Unreviewed distribution obligations | Per-file/source/generated/asset manifest at immutable revision; resolve uncertainties before shipping |
| “Hash only” private evidence uploaded | Corpus membership or provenance leak | Keep private identifiers local unless already public or separately authorized |

## UX Pitfalls

| Pitfall | User impact | Better approach |
|---|---|---|
| Unsupported feature behaves like successful no-op | Integrator misdiagnoses their host | Stable actionable errors and explicit capability/subset documentation |
| API stub presented as SDK alpha | No useful emulation to evaluate | Execute the original diagnostic from the installed public package |
| All Neo Geo configurations under one compatibility label | Users infer unsupported BIOS/board/game support | Track board, region, BIOS, cartridge revision and scenario separately |

## "Looks Done But Isn't" Checklist

- [ ] **Independent instances:** Fresh-process concurrent cold initialization, failures and teardown exercised; full mutable closure reviewed.
- [ ] **Backend admitted:** Minimal 68000 closure proved or retained FPU/SoftFloat/license/host-I/O state fully dispositioned.
- [ ] **Diagnostic passed:** Ordinary API, nonempty assertions, justified oracle ancestry, startup checks and consequential negative control.
- [ ] **SDK shipped:** Offline source, installed/relocated real consumers, exact artifacts, notices and public-safe metadata checked.
- [ ] **Release qualified:** Current commit bound to build/draft/assets; interrupted and no-new-output reruns recover; missing assets prevent publication.
- [ ] **Performance measured:** Named diagnostic baseline with raw observations; preparation targets remain targets.
- [ ] **Later continuation claimed:** Fresh-instance behavior and persistence ordering proven, separately from ABI/version compatibility.

## Recovery Strategies

| Pitfall | Recovery cost | Recovery steps |
|---|---|---|
| P1/P2 backend contamination or closure surprise | HIGH after adoption; bounded before selection | Preserve reproducer/inventory, cap adaptation, requalify or reject candidate |
| P3 correlated/invalid oracle | MEDIUM | Narrow claims, repair source ancestry/startup, explain any changed goldens |
| P4 timing seam inadequate | HIGH after adding devices | Correct observable timing contract before expanding hardware scope |
| P5 incomplete or mismatched draft | LOW before publish; HIGH after | Resolve exact draft/commit, validate complete manifest, publish once or issue new version |
| P6 authority/data leak | HIGH | Halt affected publication, contain credentials/data exposure, rebuild and audit boundaries |
| P7 missing state/dirty ordering | HIGH after compatibility promise | Explicit rejection/version change, protect durable bytes, add sequence regression |

## Pitfall-to-Phase Mapping

Phase names are recommendations for the roadmapper, not invented canonical phase numbers.

| Pitfall | Prevention phase / milestone | Verification |
|---|---|---|
| P1/P2 | v0.1: bounded CPU dependency feasibility | Source closure, state/host-safety/license inventory, cold concurrent instances and rejection decision |
| P3/P4 | v0.1: native CPU/bus diagnostic vertical slice | Justified diagnostic and startup/bus/timing evidence through ordinary API |
| Packaging and hostile boundaries | v0.1: installable SDK qualification | Relocated consumers, cold offline builds, failed lifecycle/buffer/input cases |
| Unmeasured performance / CI sprawl | v0.1: measured diagnostic baseline | Named raw observations, critical path and runner-minute records; no game-speed extrapolation |
| P5/P6 | v0.1: unsigned SDK delivery | Current-head event qualification, commit-bound complete draft and retry recovery, public artifact inspection |
| P7 and new video/audio/global-state risks | Next milestone: interactive diagnostic | Continuation/persistence sequences and actual pinned frontend evidence |

## Sources

All checks/records accessed **2026-10-01**. Mutable public docs must be rechecked when pinning workflow dependencies. Local links are dated research, not implementation receipts. S2–S5 source facts are carried from fresh [stack research](STACK.md); no backend or license approval follows from them.

| ID | Source / identity | Supported claim and limitation |
|---|---|---|
| S1 | [Adversarial review](../preparation/ADVERSARIAL-REVIEW.md), A-01–A-04 | Reentrancy, release recovery and state bookkeeping gates; preparation only |
| S2 | [Musashi CPU source](https://raw.githubusercontent.com/kstenerud/Musashi/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/m68kcpu.c) | Exact pin, shared CPU state and FPU include; not runtime reachability proof |
| S3 | [Musashi Makefile](https://raw.githubusercontent.com/kstenerud/Musashi/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/Makefile) | Default SoftFloat build closure; Glueyneo selection still open |
| S4 | [Musashi FPU source](https://raw.githubusercontent.com/kstenerud/Musashi/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/m68kfpu.c) | Host error behavior to eliminate/audit, not a claim all paths execute on 68000 |
| S5 | [SoftFloat source](https://raw.githubusercontent.com/kstenerud/Musashi/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/softfloat/softfloat.c) | Distinct Release 2b notice and state; no legal determination |
| S6 | [C architecture](../preparation/C-CORE-ARCHITECTURE.md), C-03/C-14–C-23; [Project DNA](../preparation/PROJECT-DNA.md), DNA-03/04/08/14 | Integer/timing/state contracts, historical startup/oracle and consumer lessons; sibling outcomes are not Neo Geo proof |
| S7 | [Quality/performance/CI](../preparation/QUALITY-PERFORMANCE-AND-CI.md); [Decision register](../preparation/DECISIONS.md), D-27–D-40 | Corpus privacy, performance calibration and delivery principles; no measured Glueyneo baseline |
| S8 | [Release-please schema](https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json) and [manifest documentation](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md) | MEDIUM: draft/tag settings; mutable main may exceed pinned action support |
| S9 | [Release-please action](https://github.com/googleapis/release-please-action) | MEDIUM: advanced configuration and release outputs; no project retry qualification |
| S10 | [GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases) | LOW by direct-fetch classifier: draft/assets/publish guidance; repository settings unverified |
| S11 | [GitHub token behavior](https://docs.github.com/en/actions/concepts/security/github_token) | MEDIUM: current approval-required PR events and App alternative; exact deployed event graph still needs evidence |

Remaining uncertainties are concrete: adaptation effort, minimal dependency closure, exact supported toolchains, independently justified CPU/bus assertions, real host measurements and account/event configuration. Resolve them in their mapped phases; do not broaden v0.1 to absorb full sound, BIOS, commercial games or frontend work.
