# Adversarial review of the preparation dossier

Reviewed 2026-10-01. Status: **ready for project initialization, with explicit implementation gates**. Reviewed the brief, decision register, four domain reports, roadmap seed, final handoff/index, and root working rules. This is a document and source review, not implementation verification. No emulator code, builds, tests, remote repository actions, private media, or credentials were exercised. Findings distinguish corrected handoff defects from evidence gates that correctly remain future work.

## Assessment

The product direction is coherent: an original C board model, audited chip reuse, an independent native API, deterministic execution, and a thin libretro adapter. The roadmap's first release is a CPU/bus diagnostic SDK. That scope is achievable in principle without simultaneously solving all graphics, sound, protection, original BIOS boot, and frontend distribution. Feasibility still depends on the first chip experiment; no research document establishes that its adaptation will be small.

The dossier avoids several consequential overclaims. Playstead's GBA fixtures are not presented as Neo Geo evidence. Emulator-generated instruction vectors are distinguished from hardware observations. C++ behind a C ABI is explicitly a scope alternative. Private media do not become public fixtures merely because they are available locally. Percentile targets are hypotheses, and absent compatibility evidence remains unknown.

## Findings and corrections

### A-01 — Draft release sequencing needs an explicit qualification gate

**Severity:** high if implemented incorrectly. **Status:** corrected in preparation; workflow qualification remains open.

**Evidence:** [Quality / CI lanes](QUALITY-PERFORMANCE-AND-CI.md#ci-lanes-and-efficient-feedback) originally described the release trigger as a qualified tagged commit, while its publication policy stages assets in a draft. The current release-please schema explains that GitHub may defer tag creation until the draft is published. A design that waits for a tag event to build the assets needed for publication can therefore stall. The schema has a `force-tag-creation` option, but the pinned action's bundled library must actually support it. [release-please schema](https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json)

**Disposition:** the quality report now requires manifest configuration with the simple version strategy and explicit draft behavior, dependent build/staging jobs bound to the release commit and draft identity, and recovery after interruption. It no longer requires a nonexistent tag event. The action's simple `release-type` shortcut alone does not expose advanced configuration. [Action configuration](https://github.com/googleapis/release-please-action#advanced-release-configuration)

**Unresolved gate:** demonstrate correct commit binding, incomplete-asset refusal, interrupted staging recovery, retries, and publication only after the expected asset set is complete. Existing-draft recovery must work even when a repeated release-please run reports no newly created release. Qualify this before enabling immutable publication.

### A-02 — Dependency reentrancy remains the largest architectural risk

**Severity:** high implementation risk. **Status:** intentionally unresolved, with a sound early gate.

**Evidence:** [Architecture / Timing and dependency gates](C-CORE-ARCHITECTURE.md#timing-device-boundaries-and-dependency-gates) and [Roadmap phase 1](ROADMAP-SEED.md#1-resolve-dependency-feasibility-and-establish-the-execution-contract) recognize state outside nominal CPU contexts. Independent inspection of pinned Musashi confirms global cycle counters, CPU state, exception fields, and jump buffers. A copied CPU context or global mutex does not fulfill the intended independent-instance contract. [Pinned Musashi source](https://raw.githubusercontent.com/kstenerud/Musashi/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd/m68kcpu.c)

**Disposition:** the roadmap explicitly covers simultaneous cold initialization and failing creation/load paths alongside alternating/threaded execution. The architecture excludes host jump buffers from guest serialization. Inventory mutable storage, lazy initialization, callbacks, generated tables, and error paths; keep adaptation patches reviewable against the upstream pin.

**Unresolved gate:** no backend is approved until these properties, its timing limitations, and its complete imported-file license inventory are demonstrated. A failed experiment must produce a counterexample and a scope/backend decision. C++ adoption requires a recorded change to the pure-C requirement.

### A-03 — Canonical guest state and persistence bookkeeping need separate identities

**Severity:** medium. **Status:** clarified in preparation; actual schema and continuation evidence remain open.

**Evidence:** [Architecture / State](C-CORE-ARCHITECTURE.md#state-replay-rewind-and-trust-boundaries) requires persistence generations to remain monotonic when old snapshots are restored. [Quality / Evidence ladder](QUALITY-PERFORMANCE-AND-CI.md#build-an-evidence-ladder) also requires canonical-state continuation equality. Hashing host acknowledgment counters as guest state would make a valid restore appear nondeterministic, or tempt an implementation to roll back dirty generations to satisfy a hash.

**Disposition:** the architecture now explicitly excludes host-only counters and diagnostics from canonical emulated-state hashes. Guest persistence bytes can rewind while the host's generation advances to identify a new dirty snapshot. Implementation must specify the compared fields and compare outputs at equal consumption boundaries.

**Unresolved gate:** before persistence/state claims, demonstrate restoration after newer durable writes, an old acknowledgment arriving after new writes, and uninterrupted-versus-restored guest equivalence without losing dirty data. Exact fields and encodings appropriately belong to the implementation phase.

### A-04 — Two smaller cross-report policy conflicts

**Severity:** low for tooling; medium for private metadata. **Status:** both resolved in preparation.

The architecture selected Unity while the initial decision register preferred bare C executables unless a framework became necessary. D-13 now deliberately selects CTest plus a small pinned Unity dependency, matching the architecture. This is a coherent resolution; it does not require a second build ecosystem.

The quality report initially allowed hashes in private scenario summaries while the hardware report excluded private hashes from publication. The quality report now keeps private corpus fingerprints local by default, permitting already-public content identities or separately authorized metadata in public summaries. Hashes identify bytes but do not establish redistribution rights or make private corpus membership public-safe automatically.

## Gates to preserve during planning

| Gate | Severity / status | Required outcome |
|---|---|---|
| First-slice effort | Medium; planning choice | Set an explicit experiment budget and defer decision. Inventorying future audio candidates must not require a complete sound-engine port before the CPU diagnostic SDK. Deferred devices remain visibly unsupported. |
| Timing contract | High; known design uncertainty | State observable precision and stop boundaries. CPU cycle totals and a half-master-clock scheduler representation alone do not establish bus timing. Prove the first profile's required interactions before expanding claims. |
| Fixture/license provenance | High; admission work pending | Audit actual compiled/generated files and guest assets at immutable pins, including notices and source obligations. Original diagnostics need a justified oracle and startup checks; a custom bootstrap is not original BIOS compatibility. |
| Practical media adoption | Medium; correctly deferred beyond SDK | Qualify at least one useful importer, BIOS identity/error handling, board selection, and bounded malformed input before describing ordinary games as usable. A normalized-region API alone is insufficient. |
| Performance evidence | Medium; calibration pending | Establish named workloads, hosts, output equivalence, and noise before enforcing regression percentages. Do not promote SDK microbenchmarks into gameplay performance claims. |
| Public distribution | High; actual release gate | Check archive/debug metadata, licenses, executable consumer examples, exact artifact provenance, and installed frontend behavior for products actually shipped. Missing signing credentials do not block an honestly labeled unsigned SDK. |

These gates do not justify importing later milestones into the first alpha. The current platform minima, resampler, binary state schema, full AES/PAL coverage, and future Playstead native integration are deliberately deferred decisions, not preparation defects.

## Source, statistics, trust, and maintenance checks

Current GitHub documentation corroborates the quality report's token caveat: certain PR events made with `GITHUB_TOKEN` create runs requiring approval, while other recursive events remain suppressed. A scoped GitHub App token is the appropriate unattended path described by GitHub. The older blanket wording still present in the release-please README must not override GitHub's current service documentation. [GitHub token behavior](https://docs.github.com/en/actions/concepts/security/github_token)

GitHub also confirms draft → attach assets → publish for immutable releases. This validates the intended policy, not an unbuilt workflow. Untrusted PR execution, release credentials, trusted runners, and current-revision check authority are already separated in the dossier. Preserve those boundaries in the actual event graph. [Immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)

The rare-tail arithmetic is correctly limited: 299,572 independent zero-failure trials supports the stated one-sided binomial bound, not a precise p99.999 latency estimate. Correlation, workload diversity, missed deadlines, and coordinated omission are addressed. There is no statistical basis yet for a mandatory 5% timing gate on hosted runners.

Sources are substantially qualified by type and limitation. Upstream issues demonstrate reported failures, not prevalence; hardware wiki drafts remain provisional; source pins are not completed license audits. Keep those distinctions when converting prose into requirements. The final index and working rules establish dated preparation as provenance, supersession links, and one current contract per topic. Preserve that policy instead of adding large prose-lock tests or independently maintained support claims throughout the dossier.

A targeted scan and document review found no personal home paths, email addresses, obvious token strings, or private-key markers in the reviewed preparation files. That is a bounded content check, not proof about future archives or untouched sibling repositories. No private source material needs to be copied to reproduce the recommendations.

## Cold-reader result

**Result: a fresh agent can identify the command and plan the first deliverable.** The root README, preparation index, and [handoff](OPENGSD-HANDOFF.md) consistently give this Codex skill invocation:

```text
$gsd-new-project --auto @.planning/preparation/BRIEF.md
```

The inspected installed skill accepts automatic mode with an idea-document reference. The handoff distinguishes it from a shell command, warns that configuration can still surface, preserves preparation and handcrafted instructions, and establishes future canonical planning as the current authority. It accurately limits initialization: this command does not guarantee every future milestone is implemented or released.

The first deliverable is an offline installable C SDK running an original, deterministic CPU/bus diagnostic through the ordinary native API. The phase plan must cap chip experiments; full audio adaptation is explicitly unnecessary for this alpha. An interface stub or a green workflow without executed assertions does not meet the deliverable. Backend feasibility, hardware accuracy, and release automation remain unproven; their named gates can be pursued without another broad research cycle.
