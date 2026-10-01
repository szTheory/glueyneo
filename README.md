# Glueyneo

Glueyneo is a planned portable Neo Geo MVS/AES emulator core written in C, intended for reuse in Playstead and other frontends.

The project is in research and preparation. There is no playable emulator or buildable core yet. The intended foundation is a small native C API, deterministic emulation, explicit host I/O, useful diagnostics, reproducible correctness tests and measured performance.

Start with the [preparation index](.planning/preparation/README.md), [project brief](.planning/preparation/BRIEF.md) and [decision register](.planning/preparation/DECISIONS.md). The dossier contains hardware sources, emulator lessons, portable C recommendations, evidence from active sibling projects, a quality/CI strategy and a provisional roadmap.

To initialize the project in a fresh Codex conversation using the installed OpenGSD skill:

```text
$gsd-new-project --auto @.planning/preparation/BRIEF.md
```

See the [handoff](.planning/preparation/OPENGSD-HANDOFF.md) for verified command behavior and configuration defaults.

Original project work is licensed under [MIT](LICENSE). Future dependencies and fixtures retain their own licenses. Commercial game images and BIOS files are not included.
