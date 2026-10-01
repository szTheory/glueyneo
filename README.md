# Glueyneo

Glueyneo is a planned portable Neo Geo MVS/AES emulator core written in C, intended for reuse in Playstead and other frontends.

The project is initialized for development. There is no playable emulator or buildable core yet. The first milestone is a CPU/bus diagnostic SDK alpha: a small native C API, deterministic execution of an original diagnostic, explicit host I/O boundaries and a real installed-package consumer.

Phase 1 has begun as a bounded CPU acceptance experiment. Its first adaptation currently fails to compile; the [halted experiment summary](.planning/phases/01-cpu-acceptance-experiment/01-01-SUMMARY.md) records the exact counterexamples and remaining work. No backend has been accepted, and dependent plans remain blocked.

Start with the [project](.planning/PROJECT.md), [requirements](.planning/REQUIREMENTS.md), [roadmap](.planning/ROADMAP.md) and [current state](.planning/STATE.md). These are the current planning contracts. The next milestone outlines an interactive diagnostic through libretro and RetroArch on macOS; game compatibility expands after that evidence exists.

The preserved [preparation index](.planning/preparation/README.md), [brief](.planning/preparation/BRIEF.md) and [decision register](.planning/preparation/DECISIONS.md) contain dated hardware sources, engineering recommendations, sibling-project lessons and the rationale behind the plan. They do not establish implemented behavior.

To resume with the installed OpenGSD workflow:

```text
$gsd-progress
```

OpenGSD initialization used the brief's automatic defaults. See [config.json](.planning/config.json) for workflow settings and [AGENTS.md](AGENTS.md) for working rules.

Original project work is licensed under [MIT](LICENSE). Imported dependencies retain their own notices; see the [Musashi provenance](third_party/musashi/PROVENANCE.md) and [Unity provenance](third_party/unity/PROVENANCE.md). Commercial game images and BIOS files are not included.
