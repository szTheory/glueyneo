# Glueyneo preparation index

Research date: **2026-10-01**. Status: preparation ready for initialization; review and dispositions are recorded in [ADVERSARIAL-REVIEW.md](ADVERSARIAL-REVIEW.md). Implementation and OpenGSD initialization remain ahead. Intended reader: a fresh agent or contributor planning the first useful Glueyneo release.

## Start here

Read [BRIEF.md](BRIEF.md), then [DECISIONS.md](DECISIONS.md). The [handoff](OPENGSD-HANDOFF.md) gives the verified command and the [roadmap seed](ROADMAP-SEED.md) proposes small deliverables. These documents distinguish the user's stated goals, adopted planning recommendations, open feasibility questions and absent measurements.

```text
$gsd-new-project --auto @.planning/preparation/BRIEF.md
```

Paste that into a fresh Codex conversation with this project as its working directory. It is a skill invocation. The installed OpenGSD was verified as @opengsd/gsd-core 1.14.0; the handoff explains the configuration and auto-advance behavior.

## Retrieve the evidence for the task

| Question / search terms | Read | Source namespace |
|---|---|---|
| Vision, constraints, user authorization, public privacy, first consumer | [Brief](BRIEF.md) | User instruction and synthesis |
| Alternatives, stakeholder lenses, accepted defaults, reopening a choice | [Decision register](DECISIONS.md) | D-01 through D-44 |
| 68000, Z80, YM2610, clocks, MVS, AES, video, protection, BIOS, emulator complaints | [Hardware and ecosystem](NEOGEO-HARDWARE-AND-ECOSYSTEM.md) | HW source IDs |
| C17, ABI, allocation, scheduler, CMake, CTest, Unity, state, persistence, FFI | [C core architecture](C-CORE-ARCHITECTURE.md) | C source IDs |
| Playstead, LatticeStripe, ExifCleaner, Lockspire, real past failures, fixture provenance | [Project DNA](PROJECT-DNA.md) | DNA source IDs with repository-relative paths and commit/date snapshots |
| Correctness, corpus, fuzzing, p99.999, benchmarks, CI time, cache, auto-merge, release-please | [Quality performance and CI](QUALITY-PERFORMANCE-AND-CI.md) | Q source IDs |
| Current/next/long-term milestones, feasibility spike, SDK alpha, interactive diagnostic | [Roadmap seed](ROADMAP-SEED.md) | Proposed sequence, no completion claims |
| OpenGSD identity, command syntax, config defaults, preserving preparation | [OpenGSD handoff](OPENGSD-HANDOFF.md) | GSD source IDs and local runtime hashes |
| Contradictions, evidence gaps, unresolved gates, cold-reader findings | [Adversarial review](ADVERSARIAL-REVIEW.md) | Review findings and dispositions |

Use headings and stable IDs as retrieval keys. Read the applicable domain report rather than loading every file into every agent. Follow its source ledger for claim provenance. The root [AGENTS.md](../../AGENTS.md) contains concise durable working rules; future canonical project docs govern implemented behavior.

The [validation receipt](VALIDATION.md) records the scope and limits of the final document checks.

## Source and knowledge policy

Prefer original hardware/vendor documents and direct measurements. Use maintained emulator source and issue trackers as primary evidence about those implementations, not automatic proof of the physical machine. Community hardware research is valuable but must retain its experimental limits. User reports show symptoms and priorities; they are not a representative market survey or controlled benchmark.

For each material fact retain the exact URL or repository-relative path, revision where available, access/inspection date, claim supported and caveat. Moving URLs remain discovery references until pinned for implementation. Source dates and access dates have different meanings. Preserve licensing of copied material; the reports mostly paraphrase findings and link to sources rather than archive entire manuals.

For each recommendation retain the practical alternative, benefit/cost, failure mode, evidence and trigger for revisiting it. Unsupported guesses are hypotheses. For each result retain workload/input identity, tool/build identity, command, actual outcome and its limits. A repeated claim in several reports is not independent evidence.

Do not silently rewrite the historical record when a recommendation is superseded. Add a short dated supersession link and put the current contract in the canonical owning document. Avoid duplicating volatile version/support tables across instructions, README and planning. Compile examples and validate important seams rather than freeze incidental prose.

## Preparation scope and limits

Research used three parallel specialist investigations—hardware/ecosystem, portable C/core design, and local project DNA—plus primary CI/performance/OpenGSD research and an independent adversarial pass. Local inspection sampled active projects and selected history; it did not audit every evolutionary decision or re-run their CI. Local repositories were read-only.

No emulator code, game/BIOS downloads, timing benchmarks, hardware capture, GitHub repository creation, releases or GSD initialization were performed. The package contains actionable recommendations and a plan to generate those forms of evidence. Reports identify dependency reentrancy, test-asset rights, timing uncertainties and account-dependent release setup as explicit future gates.

Public preparation excludes private machine/account details, secrets and proprietary inputs. Keep local ROMs, BIOS, save states, private captures and automation credentials outside tracked content. The index intentionally uses repository labels rather than personal remote URLs.
