# Glueyneo

Glueyneo is a portable Neo Geo MVS/AES emulator core project written in C. Phase 01 accepted an owned C17 68000 backend for a bounded CPU/bus diagnostic subset. There is no public SDK yet, and the repository does not deliver a complete playable emulator or qualify game compatibility, original-silicon behavior, platform support, or performance.

The earlier private Musashi experiment remains rejected for SDK use; its diagnostic and immutable history remain in the [Musashi acceptance record](experiments/cpu/ACCEPTANCE.md). The accepted candidate's implemented boundary is documented in the [CPU subset](experiments/owned_cpu/SUBSET.md), the frozen [candidate contract](experiments/owned_cpu/CONTRACT.md), the additive [P01-C-14 amendment](experiments/owned_cpu/illegal-reconciliation.json), and the [owned acceptance report](experiments/owned_cpu/ACCEPTANCE.md). The candidate-level receipt remains `unqualified`; separate whole-phase evidence admits the bounded subset for Phase 02 integration. See the [Phase 01 verification](.planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md) for its exact evidence and limits.

Each core repository targets a reusable library, a headless diagnostic runner and a thin libretro adapter. RetroArch is the interactive frontend until Playstead or a separate shared host is ready; no core repository will own a GUI or windowed host application. See the [project contract](.planning/PROJECT.md), [requirements](.planning/REQUIREMENTS.md) and [roadmap](.planning/ROADMAP.md).

The accepted candidate excludes exactly numeric opcode `0x4AFC` under P01-C-14. The original-MC68000 saved-PC behavior remains unknown under P01-C-13; the candidate does not claim that its behavior is hardware truth. CPU-01–05 are complete only for the bounded Phase 01 scope. No game, board, BIOS, cross-platform, performance, or public SDK qualification is established.

The fresh Phase 01 whole-phase verifier passed 10/10 at source revision `09476ed57ee29c0798f8be8f082e05ad73776e3b`, after Plan 01-29. It freshly exercised 41 bounded native assertions plus cold-process, inventory, and contract boundary checks; see the verification report for exact commands and historical-versus-current evidence. No historical UAT row was replayed. The candidate receipt remains an unqualified experiment artifact; the verifier is the separate phase-level acceptance decision. The unchanged source-bound candidate contract checker records the pre-admission gate and is not the current phase router. Current status and routing live in [STATE.md](.planning/STATE.md) and [ROADMAP.md](.planning/ROADMAP.md).

The preserved [preparation index](.planning/preparation/README.md), [brief](.planning/preparation/BRIEF.md) and [decision register](.planning/preparation/DECISIONS.md) contain dated hardware sources, engineering recommendations, sibling-project lessons and the rationale behind the plan. They do not establish implemented behavior.

To resume with the installed OpenGSD workflow, follow the exact next action in [current project state](.planning/STATE.md). That canonical document owns routing at each workflow boundary; pause after each named step.

OpenGSD initialization used the brief's automatic defaults. See [config.json](.planning/config.json) for workflow settings and [AGENTS.md](AGENTS.md) for working rules.

Original project work is licensed under [MIT](LICENSE). Imported dependencies retain their own notices; see the [Musashi provenance](third_party/musashi/PROVENANCE.md) and [Unity provenance](third_party/unity/PROVENANCE.md). Commercial game images and BIOS files are not included.
