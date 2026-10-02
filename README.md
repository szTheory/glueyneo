# Glueyneo

Glueyneo is a planned portable Neo Geo MVS/AES emulator core written in C. The long-term direction is several independent cores used by Playstead or another shared host.

The project is initialized for development. Its private CPU experiment runs an original diagnostic, but the pinned Musashi candidate is rejected for current admission after source review found six blockers. There is no playable emulator or public SDK yet. The first milestone is a CPU/bus diagnostic SDK alpha with an owned C17 core under active planning; no replacement implementation has started or been accepted.

Each core repository targets a reusable library, a headless diagnostic runner and a thin libretro adapter. RetroArch is the interactive frontend until Playstead or a separate shared host is ready; no core repository will own a GUI or windowed host application. See the [project contract](.planning/PROJECT.md), [requirements](.planning/REQUIREMENTS.md) and [roadmap](.planning/ROADMAP.md).

Phase 1 remains open / GAPS_FOUND. Revised plans 01-07 through 01-14 for the owned-core gap closure are saved and awaiting independent recheck before execution. Review findings will receive bounded regression-backed repair; final qualification remains separate. The [experiment contract](experiments/cpu/ACCEPTANCE.md) preserves the rejected candidate's evidence and frozen accounting; it does not qualify a replacement core.

The preserved [preparation index](.planning/preparation/README.md), [brief](.planning/preparation/BRIEF.md) and [decision register](.planning/preparation/DECISIONS.md) contain dated hardware sources, engineering recommendations, sibling-project lessons and the rationale behind the plan. They do not establish implemented behavior.

To resume with the installed OpenGSD workflow:

```text
$gsd-progress
```

OpenGSD initialization used the brief's automatic defaults. See [config.json](.planning/config.json) for workflow settings and [AGENTS.md](AGENTS.md) for working rules.

Original project work is licensed under [MIT](LICENSE). Imported dependencies retain their own notices; see the [Musashi provenance](third_party/musashi/PROVENANCE.md) and [Unity provenance](third_party/unity/PROVENANCE.md). Commercial game images and BIOS files are not included.
