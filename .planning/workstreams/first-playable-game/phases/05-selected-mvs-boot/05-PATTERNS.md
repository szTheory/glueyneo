# Phase 05: Selected MVS Boot — Gap Plan Pattern Map

**Mapped:** 2026-10-09
**Scope:** Fresh `05-VERIFICATION.md` actionable repository gaps only. The selected-media RetroArch observation remains manual-only until the native checkpoint and launch preconditions are met.
**Files analyzed:** 11 likely source/test/evidence files
**Tracked analogs:** 6 / 6 selected analog paths verified with `git ls-files`.

## File Classification

| Likely plan file | Role / data flow | Closest tracked analog | Use |
|---|---|---|---|
| `src/mvs/mvs_bus.c`, `experiments/owned_cpu/cpu.c` | runtime modules / guest execution and bus events | `tests/mvs/test_mvs.c`; `tests/owned_cpu/test_semantics.c` | Add only behavior reached by a reproducible guest checkpoint; retain observable failure details. |
| `tools/mvs/mvs_qualify.c` | qualification utility / bounded batch execution | same existing file; `tests/mvs/test_mvs.c` | Evolve existing bounded runner and result classification; do not infer attract/start from device activity. |
| `tests/mvs/test_mvs.c`, `tests/owned_cpu/test_semantics.c` | tests / deterministic guest execution | each other | Small byte-exact guest vectors, explicit bus effects, cycle/PC assertions, and negative controls. |
| `tests/sdk/ORACLE.md`, `fixtures/diagnostic/manifest.json` | oracle and generated-fixture provenance / source identity | `tests/owned_cpu/ORACLE.md` | Reconcile the changed timing claim against independent evidence and update only source identity fields justified by reviewed behavior; never refresh expected output to silence the gate. |
| `docs/rights-inventory.md` | provenance record / batch inventory | existing inventory rows in the same file | Add affirmative, exact-byte/provenance rows only for reviewed public test files; preserve excluded/private media boundary. |
| `tests/workflow/test_public_content.py`, `tools/public_content.py` | policy test and validator / source-tree scan | same existing test and tool | Exercise the existing exact path-set, digest, and notice checks; avoid weakening scanner policy. |
| `tools/verify_hosted_mvs.py`, `tests/sdk/test_hosted_mvs_receipt.py` (if retained in gap plan) | receipt checker and tests / event-to-artifact validation | `tools/verify_sdk.py`; `tests/sdk/test_matrix_evidence.py` | Bind eligible event, every named lane, aggregate, and exact source revision; reject missing, duplicate, stale, or zero-denominator evidence. |
| `05-HOSTED-QUALIFICATION.md` | evidence record / qualification outcome | existing file | Record exact gate results and keep G-05-5 open absent a current eligible receipt. |

## Pattern Assignments

### Guest behavior and checkpoint tests

**Analogs:** `tests/mvs/test_mvs.c` and `tests/owned_cpu/test_semantics.c` (tracked).

`tests/mvs/test_mvs.c:21-28` runs a large guest budget as bounded chunks and checks each `gn_run_mvs` result. Its synthetic MVS guest setup at `:69-85` uses explicit reset vectors and instruction bytes. `tests/owned_cpu/test_semantics.c:54-67` models big-endian guest word reads and rejects invalid/alignment cases; its per-test bus counters and failure injection (`:17-32`, `:79-107`) make bus order and failure behavior observable. Follow these conventions for any newly established checkpoint: construct guest bytes explicitly, assert guest-written values and exact terminal PC/cycles, and add wrong-value/order/source controls. A MAME-derived expected result must name its ancestry and remain differential, not hardware truth.

### Bounded selected-run qualification

**Analog:** `tools/mvs/mvs_qualify.c` (tracked; current utility is the target, not a generic runner to replace).

The existing utility accumulates bounded chunk/instruction observations and emits stable JSON statuses, including the first unsupported guest event (`:161-210`). Extend the existing status vocabulary and observable checkpoint only when an independent predicate has been justified. Preserve an explicit budget-exhausted/unsupported outcome; do not promote stable device transitions or synthetic sentinels to attract/start success.

### Oracle and generated-fixture identity

**Analogs:** `tests/owned_cpu/ORACLE.md` and `fixtures/diagnostic/manifest.json` (tracked).

`tests/owned_cpu/ORACLE.md:9-16` separates manual-derived CPU expectations from project bus behavior and explicitly disclaims physical bus evidence. `fixtures/diagnostic/manifest.json` stores each `source_inputs` path, byte count, and SHA-256 alongside the oracle ancestry. Use the same separation for any changed diagnostic timing description: establish whether the claim changed, review expected results independently, then update the manifest identity for the actual reviewed document bytes. Do not alter goldens or broaden claims merely to regain matrix green.

### Rights and source-bound hosted evidence

**Analogs:** `docs/rights-inventory.md`, `tools/public_content.py:235-248`, `tests/workflow/test_public_content.py:212-249`, `tools/verify_sdk.py`, and `tests/sdk/test_matrix_evidence.py` (all tracked).

The rights validator compares the exact candidate path set and bytes, then checks notices. The corresponding workflow tests cover unknown/missing inventory items and byte changes. Add the 13 missing test records only after inspecting each file's authorship, dependency provenance, notice, and exact current bytes; compute identities from the reviewed files, not copied stale values. For hosted evidence, retain the SDK verifier's structured receipt practices and test rejection paths with synthetic JSON; require eligible event identity and exact SHA agreement across event, all seven MVS tests, and aggregate. Local success remains rehearsal evidence, never a hosted receipt.

## Shared Patterns

- **Evidence:** Keep an oracle ancestry and uncertainty statement next to newly claimed hardware-facing behavior. A test passing against a synthetic guest establishes only that fixture's contract.
- **Privacy and rights:** Keep private ROM/BIOS identities, paths, captures, and traces out of rights rows and public CI. Rights rows establish public provenance for tracked test assets only.
- **Failure behavior:** Preserve narrow machine-readable outcomes, then test fail-then-valid recovery where mutation or a rejected artifact could poison later runs.
- **Scope:** No analog supports claiming the actual pinned RetroArch flow is verified from harness results. Keep that observation unknown/manual-only, and leave Phase 04 blockers untouched.

## No Analog Found

| File / concern | Reason |
|---|---|
| An independently justified selected Metal Slug X attract/start predicate | Current verification explicitly says none is available. Derive it from defensible guest-visible behavior and wrong-source/value/order controls before coding a pass condition. |
| A current eligible hosted exact-SHA receipt | No hosted event or artifacts exist; local verifier/test patterns validate structure but cannot supply this evidence. |
| Actual selected-media pinned RetroArch observation | The precondition is unsatisfied and the earlier launch failure is stale; synthetic callback tests cannot replace app observation. |

**Search scope:** Phase 05 verification and halted 05-05 records; `src/mvs`, `tools/mvs`, `tests/mvs`, `tests/owned_cpu`, `tests/sdk`, fixture manifests, and public-content inventory/tooling. No local `.codex/skills/` or `.agents/skills/` project skill index was present.

## Post-execution reconciliation — 2026-10-10

This map was prepared before Plan 05-06 ran. The original “No Analog Found”
entries record that planning-time evidence state, not the current result. Plan
05-06 later obtained a hosted MVS receipt for exact candidate
e80672845fc60d94d8a44eab416377534c9a99f1; PR #2 remains open with
REVIEW_REQUIRED, so that receipt does not qualify another revision or a merge.
The selected guest predicate still has no independent source/observation.

The later public-fixture RetroArch process attempt and a diagnostic no-content
versus core-plus-public-fixture comparison both exited -6 with SIGABRT before
the first screenshot. This does not identify a core/content fault or satisfy
the actual selected-media observation. Current detailed evidence is in
05-VALIDATION.md; keep HOST-02 and the selected-media flow open/unknown.
