# Phase 04: Public Playable Tracer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-07
**Phase:** 04-Public Playable Tracer
**Areas discussed:** Fixture boot path, Visible scene and controls, Fixture rebuild experience

---

## Fixture boot path

| Option | Description | Selected |
|--------|-------------|----------|
| Direct fixture entry | Original fixture content is loaded through ordinary native and Libretro paths with a documented BIOS-free entry; claims stay limited to the fixture. | ✓ |
| Tiny first-party bootstrap | Include a minimal original setup/launch sequence if needed; it remains fixture code and is not represented as a production BIOS. | |
| Production BIOS | Use production firmware to emulate the normal private game startup path. Excluded from public fixture requirements and clean public CI. | |

**User's choice:** Accepted the recommendation set for all areas.
**Notes:** The user requested broad role-lens and adversarial comparison, reputable primary sources where useful, and a synthesized recommendation. The public fixture must not claim BIOS or game compatibility.

---

## Visible scene and controls

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal scene with one obvious response | Fixed high-contrast backdrop, one guest-controlled marker, one documented RetroPad direction, fixed input sequence, semantic pixel/state assertions, and a wrong-input control. | ✓ |
| Richer scene with multiple actions | More objects/actions and visual complexity, requiring broader rendering behavior and a larger independent oracle surface. | |

**User's choice:** Accepted the recommendation set for all areas.
**Notes:** Keep the host from drawing or correcting guest output. Defer game-specific movement/fire, scrolling, and multi-layer scene behavior to their allocated phases.

---

## Fixture rebuild experience

| Option | Description | Selected |
|--------|-------------|----------|
| Check in generated ROM alongside source | Convenient ready-to-load artifact, with risk of source/binary drift unless regeneration is checked. | |
| Generate during every ordinary build | One-step clean build, but can impose a generator/toolchain on normal library and cross builds. | |
| Named generation target and verification command | Track source/assets as canonical, generate into the build tree, have native/RetroArch checks use the same artifact, and expose a one-command maintainer path. | ✓ |

**User's choice:** Accepted the recommendation set for all areas.
**Notes:** Add no external dependency by default. If a ROM/graphics toolchain proves necessary, compare it against a small local or copied implementation and retain full provenance/notices. If a binary is checked in for a concrete need, require a regeneration identity check.

---

## the agent's Discretion

The exact guest source encoding or generator, board/video implementation, pixel format and dimensions, API layout, fixed test vector, build commands, and pinned tool/frontend identities remain for downstream research and planning. They must honor the accepted behavior and claim boundaries.

## Deferred Ideas

No new ideas were introduced. Selected private BIOS/game boot, active Metal Slug X graphics and scrolling, and audible sound remain allocated to Phases 05, 06, and 07 respectively.
