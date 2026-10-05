# Phase 02: Executable diagnostic SDK - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `02-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-10-05  
**Phase:** 02-executable-diagnostic-sdk  
**Areas discussed:** Native instance/media lifecycle; deterministic run results; diagnostic/oracle; shift-left evidence and package verification

---

The user asked for broad, relevant technical and stakeholder lenses, primary-source research where useful, an adversarial pass, and synthesized recommendations. The options and tradeoffs below were considered in that process. The user explicitly directed the agent to follow the recommendations for all areas and separately selected copy-on-load for media.

## Native instance, media ownership, lifecycle and failure guarantees

| Option | Description | Selected |
|--------|-------------|----------|
| Copy on load into bounded instance-owned storage | Simplifies caller lifetime and destruction; costs one bounded allocation/copy. Load validates and allocates before replacing working state. | ✓ |
| Borrow immutable media | Avoids a copy but requires the caller to retain stable bytes through unload/destroy. | |
| Transfer ownership with custom release/allocator hooks | Avoids a copy but expands the callback and allocator lifetime contract. | |

**User's choice:** “follow ur recs for all these plz”; selected the recommended copy-on-load option in the preceding question.
**Notes:** Reset preserves loaded media; unload and destroy release media explicitly. Failed validation/allocation/replacement leaves a prior usable instance unchanged. Start with standard C allocation; test allocation failure privately rather than exposing custom allocator callbacks without a concrete consumer need.

---

## Deterministic bounded execution and public observations

| Option | Description | Selected |
|--------|-------------|----------|
| Guest-cycle budget and explicit run result | Reports elapsed cycles, instruction-boundary overshoot, instruction count and named stop/error reason; no host clock. | ✓ |
| Instruction-count budget only | Bounds completed instructions but does not express guest-time progress. | |
| Wall-clock budget or success-on-STOP | Couples guest semantics to host scheduling or treats a CPU state as diagnostic success. | |

**User's choice:** Follow the synthesized recommendation.
**Notes:** Expose named diagnostic observations and bounded progress, not the complete CPU state, private continuation record, or unrestricted bus history. Keep functional bus trace assertions in test/runner instrumentation unless a named public acceptance claim requires additional fields. A stopped guest is an execution result; the caller still checks expected diagnostic output.

---

## Original diagnostic, functional bus observation, and independent oracle

| Option | Description | Selected |
|--------|-------------|----------|
| Original guest results plus bounded manual-derived functional bus trace | Checks meaningful guest-computed outputs and named bus effects without claiming physical pin timing. | ✓ |
| Guest end-state checks only | Simpler, but may miss address, width, order, or extra bus-access errors. | |
| Emulator output as the expected golden | Useful for discrepancy discovery but may have correlated ancestry and does not establish hardware truth. | |

**User's choice:** Follow the synthesized recommendation.
**Notes:** Use a lawful firmware-free fixture through both the ordinary API and headless runner; cover initialized data and BSS. Derive expected behavior from the original fixture and Motorola/NXP manuals. Keep exact wrong-behavior controls and reject crash, timeout, unrelated failure, and zero-assertion outcomes. Record fixture rights, source/recipe, digest, tool/configuration, and oracle ancestry. No BIOS, commercial media, board-accuracy, or hardware-pin claims.

---

## Shift-left evidence, package consumers, automation, and cost

| Option | Description | Selected |
|--------|-------------|----------|
| Focused CTest-backed local entrypoint with claim-mapped suites | Automates boundaries, lifecycle, deterministic integration, installed consumers, and bounded hostile-input evidence while keeping suite denominators clear. | ✓ |
| Separate scripts/formats for every lane | Gives each lane independence but increases duplication and drift. | |
| One broad smoke test or manual UAT | Hides missing assertions and does not automate deterministic acceptance. | |

**User's choice:** Follow the synthesized recommendation.
**Notes:** Include same-boundary repeat/split and concurrent-instance checks, real installed out-of-tree C consumers for static/shared plus C++ header linkage, bounded fuzzing for hostile media/call sequences, supported ASan/UBSan and concurrency sanitizer configurations, and exact machine-readable outcomes/identities. Preserve failures as deterministic regressions. Record named-host cost baselines and uncertainty without uncalibrated thresholds. Phase 03 owns hosted required CI, branch protection, release automation, and publication qualification.

---

## the agent's Discretion

- Concrete C names, enum values, normalized manifest encoding, machine-readable result schema, test target names, and bounded fuzz duration, provided the implementation follows `02-CONTEXT.md`.
- Select a C-native fuzz engine available in the exercised compiler; no runtime fuzzing dependency.
- Keep the public allocator contract simple unless a concrete integrator need demonstrates otherwise.

## Deferred Ideas

- Commercial ROM/BIOS import, game support, video/audio, GUI/front-end integration, public snapshots, and durable persistence are outside Phase 02.
- Hosted CI authority, protected PRs, unattended App/bot events, release staging/publication, and release artifact qualification remain Phase 03.

## Phase 01 gate refresh (2026-10-05)

The original discussion decisions remain unchanged. After a separate fresh Phase 01 verifier passed 10/10, `02-CONTEXT.md` was updated to record that Phase 02 is unblocked for planning, distinguish the phase-level admission from the frozen candidate receipt, and preserve the original-silicon saved-PC unknown. No prior discussion choices or historical UAT rows were replayed.
