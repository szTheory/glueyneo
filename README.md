# Glueyneo

Glueyneo is a planned portable Neo Geo MVS/AES emulator core written in C. The long-term direction is several independent cores used by Playstead or another shared host.

The private Musashi CPU experiment runs an original diagnostic, but that candidate is rejected for current admission after source review found six blockers. Phase 01 is executing a separately budgeted owned C17 replacement experiment, beginning with a private CPU/bus diagnostic subset. The contract and governance validator are in place; no owned CPU runtime has been implemented or accepted. There is no playable emulator or public SDK yet.

Each core repository targets a reusable library, a headless diagnostic runner and a thin libretro adapter. RetroArch is the interactive frontend until Playstead or a separate shared host is ready; no core repository will own a GUI or windowed host application. See the [project contract](.planning/PROJECT.md), [requirements](.planning/REQUIREMENTS.md) and [roadmap](.planning/ROADMAP.md).

Phase 1 remains open / GAPS_FOUND, and Phase 02 stays gated. Plans 01-07 through 01-14 close the owned-core gaps in dependency order; findings receive bounded regression-backed repair, and final qualification remains separate. The [owned-core contract](experiments/owned_cpu/CONTRACT.md) defines the proposed subset and limits. The [Musashi experiment record](experiments/cpu/ACCEPTANCE.md) preserves the rejected candidate's evidence and frozen accounting; it does not qualify the replacement core.

The preserved [preparation index](.planning/preparation/README.md), [brief](.planning/preparation/BRIEF.md) and [decision register](.planning/preparation/DECISIONS.md) contain dated hardware sources, engineering recommendations, sibling-project lessons and the rationale behind the plan. They do not establish implemented behavior.

To resume with the installed OpenGSD workflow:

```text
$gsd-progress
```

OpenGSD initialization used the brief's automatic defaults. See [config.json](.planning/config.json) for workflow settings and [AGENTS.md](AGENTS.md) for working rules.

Original project work is licensed under [MIT](LICENSE). Imported dependencies retain their own notices; see the [Musashi provenance](third_party/musashi/PROVENANCE.md) and [Unity provenance](third_party/unity/PROVENANCE.md). Commercial game images and BIOS files are not included.
