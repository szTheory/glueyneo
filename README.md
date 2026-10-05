# Glueyneo

Glueyneo is a portable Neo Geo MVS/AES emulator core project written in C. A private owned C17 CPU runtime and deterministic bus diagnostic subset are implemented as an acceptance experiment; the backend remains unadmitted, there is no public SDK, and the repository does not yet deliver a complete playable emulator.

The earlier private Musashi experiment is rejected for current admission; its diagnostic and immutable history remain in the [Musashi acceptance record](experiments/cpu/ACCEPTANCE.md). The owned candidate's implemented boundary is documented in the [CPU subset](experiments/owned_cpu/SUBSET.md), the frozen [candidate contract](experiments/owned_cpu/CONTRACT.md), the additive [P01-C-14 amendment](experiments/owned_cpu/illegal-reconciliation.json), and the [owned acceptance report](experiments/owned_cpu/ACCEPTANCE.md). The [current candidate review](experiments/owned_cpu/REVIEW.md), [later independent findings](.planning/phases/01-cpu-acceptance-experiment/01-REVIEW.md), and [current receipt](experiments/owned_cpu/acceptance-results.json) explain why implementation and passing experiment evidence do not grant admission.

Each core repository targets a reusable library, a headless diagnostic runner and a thin libretro adapter. RetroArch is the interactive frontend until Playstead or a separate shared host is ready; no core repository will own a GUI or windowed host application. See the [project contract](.planning/PROJECT.md), [requirements](.planning/REQUIREMENTS.md) and [roadmap](.planning/ROADMAP.md).

The candidate excludes exactly numeric opcode `0x4AFC` under P01-C-14. The original-MC68000 saved-PC behavior remains unknown under P01-C-13; the candidate does not claim that its behavior is hardware truth. No game, board, BIOS, cross-platform, performance, or public SDK qualification is established. CPU-01–05 remain Pending; Phase 01 is open and Phase 02 stays gated.

Plans 01-22 through 01-27 close bounded review and evidence findings and produce only unqualified, deferred candidate evidence. The fresh 2026-10-05 whole-phase verdict is 8/9 `GAPS_FOUND`: the old report-binding issue is closed, and Plan 01-28 repairs the current documentation gate and navigation. The recorded 49/49 automated UAT checks are historical evidence at their recorded source revisions; they predate these ROADMAP/README findings and do not validate changed documents. The repair requires a separate fresh whole-phase verifier before phase admission. CPU-01–05 remain Pending, the candidate remains unqualified with admission deferred, and original-silicon saved PC remains unknown.

The preserved [preparation index](.planning/preparation/README.md), [brief](.planning/preparation/BRIEF.md) and [decision register](.planning/preparation/DECISIONS.md) contain dated hardware sources, engineering recommendations, sibling-project lessons and the rationale behind the plan. They do not establish implemented behavior.

To resume with the installed OpenGSD workflow, follow the exact next action in [current project state](.planning/STATE.md). That canonical document owns routing at each workflow boundary; pause after each named step.

OpenGSD initialization used the brief's automatic defaults. See [config.json](.planning/config.json) for workflow settings and [AGENTS.md](AGENTS.md) for working rules.

Original project work is licensed under [MIT](LICENSE). Imported dependencies retain their own notices; see the [Musashi provenance](third_party/musashi/PROVENANCE.md) and [Unity provenance](third_party/unity/PROVENANCE.md). Commercial game images and BIOS files are not included.
