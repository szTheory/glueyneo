# Glueyneo OpenGSD handoff

Prepared 2026-10-01. Purpose: start the real project in a fresh context using this dossier, preserving the user's preferences and avoiding another broad discovery loop.

## Command to paste into a fresh Codex conversation

Open the Glueyneo project as the working directory, then invoke:

```text
$gsd-new-project --auto @.planning/preparation/BRIEF.md
```

This is an agent skill invocation, not a shell command. The referenced brief includes the vision, scoped defaults, autonomy preferences, reading map and proposed configuration answers. Use the installed **OpenGSD** skill, not a similarly named workflow from another package.

The installed skill explicitly accepts --auto with an @-referenced idea document. Its workflow creates PROJECT.md, config.json, REQUIREMENTS.md, ROADMAP.md, STATE.md and normal research files under .planning. In the inspected version, --auto also advances to discussion of phase 1. It does not mean that one command guarantees every future milestone is implemented or released. Workflow/runtime limitations still apply. [GSD-01–04]

## What exists now

The repository contains preparation documents and lightweight project guidance. There is no emulator implementation, executable, build configuration, actual CI workflow, measured baseline, GitHub publication, or completed GSD initialization. The source directory was empty when preparation began. No other inspected repository was modified.

Canonical GSD project artifacts are intentionally absent so new-project can initialize normally. Preserve .planning/preparation as the dated evidence archive; let the installed workflow create .planning/research and the project state in its expected format. The word "milestone" in the seed does not mean it already exists in OpenGSD state.

## Verified runtime and command behavior

The installed runtime identity command returned:

```json
{"packageName":"@opengsd/gsd-core","version":"1.14.0"}
```

This was a read-only identity check on 2026-10-01. The workflow was inspected but not executed. The version is the local inspected version, not a claim that it is the latest published release. Official OpenGSD documentation also describes new-project and --auto idea-document ingestion. [GSD-05, GSD-06]

The installed auto configuration step still contains configuration questions before research. The skill adapter permits proceeding on an explicit noninteractive flag or appropriately authorized defaults. The user broadly asked to follow recommendations automatically; the brief records our chosen defaults and their basis. Do not misrepresent those defaults as menu choices individually answered by the user, and do not promise a particular client will suppress all prompts. If it asks, use the recorded settings rather than restarting product discovery.

Recommended settings are coarse phases with small vertical plans; independent parallel work; tracked public-safe planning; research, plan checking, verification and source grounding enabled; model profile inherit; automatic progression within authorized scope; and compact evidence-oriented PR descriptions without a standing manual sign-off requirement. Use the installed helper and current schema. Do not blindly copy a config JSON snippet from a different GSD distribution/version.

After initialization, the installed flow's next action is $gsd-discuss-phase 1, with --auto in its automatic path. $gsd-autonomous is available for the remaining phases of a milestone, but it is a separate orchestration command and must follow its installed workflow. Do not invent a command that promises an unlimited series of milestones from an unreviewed backlog.

## First-context procedure

1. Read the brief and decision register. Confirm the task is C MVS/AES emulation and an embeddable core. Elixir/database/Hex boilerplate is not a technology request.
2. Check installed runtime identity and applicable project instructions. Preserve the handcrafted engineering rules when OpenGSD generates its own instructions; do not force-overwrite them. Its inspected generation path normally leaves a handcrafted file without its markers alone. [GSD-02]
3. Read the adversarial review and use the index to route narrow research. Hardware/chip researchers need the hardware and C reports; CI/release work needs quality and DNA reports. Give agents file ownership and explicit integration contracts.
4. Recheck unresolved dependency, license, fixture and timing evidence. Pin exact revisions before implementation. Historical sibling-project receipts and moving upstream URLs are not current test results.
5. Initialize canonical artifacts with the actual OpenGSD workflow. Translate the first roadmap seed into deliverables and acceptance checks; avoid promising full-game support in a foundation release.
6. Run the earliest feasibility spike before committing to chip engines or a public ABI. Measure real code before setting hard speed targets.
7. Establish a public-safe Git identity, repository, branches and release authority when needed. User authorization for normal PRs/qualifying merges/releases persists; missing credentials are factual setup needs, not repeated permission questions.
8. Execute scoped milestones with automatic verification and update the rolling roadmap from evidence. Keep only genuinely unavailable hardware or account facts for human input.

Before the initial public commit or push, inspect staged content and author metadata. The preparation intentionally avoids personal home paths, private emails, remote account URLs, proprietary assets and credentials. Preserve that property in generated planning, build logs, debug info and artifacts.

## Avoid redoing research by default

Reopen a decision when a cited source changes materially, a dependency fails a feasibility gate, hardware contradicts an assumption, a supported consumer exposes a missing contract, or a profile shows a real bottleneck. A new context window alone is not a reason to repeat the entire survey.

Maintain decisions with stable IDs, a short rationale, evidence links, status and a reopening condition. Promote settled requirements and current contracts into canonical project docs; leave this dated preparation as provenance. Update the index with superseding links so future agents can distinguish historical advice from current behavior. No vector database or search service is needed for this small Markdown corpus.

## Local provenance ledger

Paths below are relative to the relevant installed skill/runtime roots and deliberately contain no personal filesystem information. Hashes identify the inspected content, not public release signatures.

| ID | Evidence | Observed result |
|---|---|---|
| GSD-01 | Installed skill: gsd-new-project/SKILL.md | --auto @ idea document syntax; artifact list; Codex adapter and autonomy exceptions |
| GSD-02 | Runtime: workflows/new-project.md | Initialization artifacts; handcrafted instruction-file preservation; auto progression to discuss phase 1; SHA-256 e96426b7231aae1bb09d164200734441f2d4f611cc868f7083db418ce2e4f272 |
| GSD-03 | Runtime: workflows/new-project/steps/auto-mode-config.md | Configuration questions/options and helper; SHA-256 e59c75d6614bb6813d0e29b4243634a58846c8b46c3fa5efa13681a49b8c73b4 |
| GSD-04 | Runtime: workflows/new-project/steps/auto-mode-detection.md; runtime-identity output | Automatic-mode behavior, document requirement and local package identity; detection SHA-256 a078747a21b67fdfdd2b4a53669a33618b2983f95ef0bdc57cd23660ccff6317 |
| GSD-05 | [Official OpenGSD core](https://github.com/open-gsd/gsd-core) | Correct public project/package identity; accessed 2026-10-01 |
| GSD-06 | [Official quickstart source](https://github.com/open-gsd/docs/blob/main/core/quickstart.mdx), [OpenGSD core product](https://opengsd.net/products/gsd-core) | Project entry point and idea ingestion; accessed 2026-10-01; local runtime defines exact Codex invocation |

Do not install or update OpenGSD merely because this dossier names a version. Verify the existing installation first, then follow its own update procedure only if a concrete compatibility need arises.
