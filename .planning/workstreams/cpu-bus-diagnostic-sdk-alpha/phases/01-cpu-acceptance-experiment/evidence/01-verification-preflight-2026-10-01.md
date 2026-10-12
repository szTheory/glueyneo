---
phase: 01-cpu-acceptance-experiment
verified: 2026-10-01T22:08:27Z
status: stale
verification_scope: preflight_only
score: 0/5 must-haves verified
score_note: "Verification refused by MVP format guard; zero is not a claim that all five implementation truths failed."
covered_files: [".gitignore",".planning/REQUIREMENTS.md",".planning/ROADMAP.md",".planning/phases/01-cpu-acceptance-experiment/01-01-PLAN.md",".planning/phases/01-cpu-acceptance-experiment/01-01-SUMMARY.md",".planning/phases/01-cpu-acceptance-experiment/01-02-PLAN.md",".planning/phases/01-cpu-acceptance-experiment/01-02-SUMMARY.md",".planning/phases/01-cpu-acceptance-experiment/01-03-PLAN.md",".planning/phases/01-cpu-acceptance-experiment/01-03-SUMMARY.md",".planning/phases/01-cpu-acceptance-experiment/01-04-PLAN.md",".planning/phases/01-cpu-acceptance-experiment/01-04-SUMMARY.md",".planning/phases/01-cpu-acceptance-experiment/01-REVIEW.md",".planning/phases/01-cpu-acceptance-experiment/01-SECURITY.md",".planning/phases/01-cpu-acceptance-experiment/01-UI-REVIEW.md",".planning/phases/01-cpu-acceptance-experiment/01-VALIDATION.md","AGENTS.md","CMakeLists.txt","README.md","experiments/cpu/ACCEPTANCE.md","experiments/cpu/CMakeLists.txt","experiments/cpu/REVIEW.md","experiments/cpu/acceptance-results.json","experiments/cpu/budget-ledger.json","experiments/cpu/cpu_adapter.c","experiments/cpu/cpu_adapter.h","experiments/cpu/evidence/attempt-1/2026-10-01-halted-summary.md","experiments/cpu/evidence/attempt-1/build-failure.txt","experiments/cpu/evidence/attempt-1/receipt.json","experiments/cpu/evidence/attempt-1/source.patch","experiments/cpu/evidence/attempt-2/audit-control-path-failure.txt","experiments/cpu/evidence/attempt-2/closure-first.json","experiments/cpu/evidence/attempt-2/closure-second.json","experiments/cpu/evidence/attempt-2/compiler-1.patch","experiments/cpu/evidence/attempt-2/compiler-1.txt","experiments/cpu/evidence/attempt-2/qualification.json","experiments/cpu/evidence/attempt-2/tracer.json","experiments/cpu/evidence/plan-01-02/cpu-asan.log","experiments/cpu/evidence/plan-01-02/cpu-tsan.log","experiments/cpu/evidence/plan-01-02/cpu.log","experiments/cpu/evidence/plan-01-02/irq-fault-counterexample.json","experiments/cpu/evidence/plan-01-02/qualification.json","experiments/cpu/evidence/plan-01-02/sanitizer-counterexample.json","experiments/cpu/evidence/plan-01-03/budget.json","experiments/cpu/evidence/plan-01-03/cpu-asan.log","experiments/cpu/evidence/plan-01-03/cpu-tsan.log","experiments/cpu/evidence/plan-01-03/cpu.log","experiments/cpu/evidence/plan-01-03/qualification.json","experiments/cpu/evidence/plan-01-03/regeneration.json","experiments/cpu/evidence/plan-01-03/reset-counterexamples.md","experiments/cpu/evidence/plan-01-03/review.md","experiments/cpu/evidence/plan-01-03/state-red.json","experiments/cpu/evidence/plan-01-03/state-review-counterexamples.md","experiments/cpu/evidence/plan-01-03/timing-red.json","experiments/cpu/evidence/plan-01-04/acceptance-controls.log","experiments/cpu/evidence/plan-01-04/acceptance-red.json","experiments/cpu/evidence/plan-01-04/asan-ubsan-build.log","experiments/cpu/evidence/plan-01-04/asan-ubsan-configure.log","experiments/cpu/evidence/plan-01-04/asan-ubsan-ctest.log","experiments/cpu/evidence/plan-01-04/collection-1-diagnosis.md","experiments/cpu/evidence/plan-01-04/collection-1-failure.json","experiments/cpu/evidence/plan-01-04/collection-2-diagnosis.md","experiments/cpu/evidence/plan-01-04/collection-2-failure.json","experiments/cpu/evidence/plan-01-04/native-build.log","experiments/cpu/evidence/plan-01-04/native-configure.log","experiments/cpu/evidence/plan-01-04/native-ctest.log","experiments/cpu/evidence/plan-01-04/tsan-build.log","experiments/cpu/evidence/plan-01-04/tsan-configure.log","experiments/cpu/evidence/plan-01-04/tsan-ctest.log","experiments/cpu/evidence/recovery-accounting/classify.py","experiments/cpu/evidence/recovery-accounting/core-semantic-refinement.json","experiments/cpu/evidence/recovery-accounting/history.json","experiments/cpu/evidence/recovery-accounting/replay.py","experiments/cpu/evidence/recovery-accounting/semantic-residuals.txt","experiments/cpu/evidence/recovery-accounting/stage-0/adapt.py","experiments/cpu/evidence/recovery-accounting/stage-0/recipe.patch","experiments/cpu/evidence/recovery-accounting/stage-0/transition.patch","experiments/cpu/evidence/recovery-accounting/stage-1/adapt.py","experiments/cpu/evidence/recovery-accounting/stage-1/recipe.patch","experiments/cpu/evidence/recovery-accounting/stage-1/transition.patch","experiments/cpu/evidence/recovery-accounting/stage-2/adapt.py","experiments/cpu/evidence/recovery-accounting/stage-2/recipe.patch","experiments/cpu/evidence/recovery-accounting/stage-2/transition.patch","experiments/cpu/evidence/recovery-accounting/stage-3/adapt.py","experiments/cpu/evidence/recovery-accounting/stage-3/recipe.patch","experiments/cpu/evidence/recovery-accounting/stage-3/transition.patch","experiments/cpu/evidence/recovery-accounting/tighten_core_semantics.py","experiments/cpu/state-inventory.json","experiments/cpu/test_bus.c","experiments/cpu/test_bus.h","tests/cpu/ORACLE.md","tests/cpu/audit-red-evidence.json","tests/cpu/faults-red-evidence.json","tests/cpu/fixture-manifest.json","tests/cpu/guest_fixture.c","tests/cpu/guest_fixture.h","tests/cpu/isolation-red-evidence.json","tests/cpu/isolation_fixture.h","tests/cpu/isolation_negative.py","tests/cpu/negative.py","tests/cpu/red-evidence.json","tests/cpu/state_negative.py","tests/cpu/test_acceptance.py","tests/cpu/test_audit.py","tests/cpu/test_cold.c","tests/cpu/test_faults.c","tests/cpu/test_guest.c","tests/cpu/test_inventory.py","tests/cpu/test_isolation.c","tests/cpu/test_state.c","tests/cpu/test_timing.c","third_party/musashi/PROVENANCE.md","third_party/musashi/m68k.h","third_party/musashi/m68k_in.c","third_party/musashi/m68kconf.h","third_party/musashi/m68kcpu.c","third_party/musashi/m68kcpu.h","third_party/musashi/m68kmake.c","third_party/musashi/m68kops.c","third_party/musashi/m68kops.h","third_party/unity/LICENSE.txt","third_party/unity/PROVENANCE.md","third_party/unity/src/unity.c","third_party/unity/src/unity.h","third_party/unity/src/unity_internals.h","tools/cpu/acceptance.py","tools/cpu/adapt.py","tools/cpu/audit.py","tools/cpu/record_attempt.py","tools/cpu/record_safety.py","tools/cpu/red.py","tools/cpu/source-manifest.json","tools/cpu/state_inventory.py"]
covered_digest: "v1:sha256:d1292b51d6719b00baa804c71f1aa40c4ff3c99cbaef13efea9739cc7038568b"
behavior_unverified: 0
overrides_applied: 0
human_verification: []
gaps:
  - truth: "The MVP phase has a valid canonical user-story goal before verification."
    status: failed
    reason: "Installed user-story.validate rejects the ROADMAP goal: missing ', I want to [capability],' and ', so that [outcome].'. MVP verifier must refuse verification."
    artifacts:
      - path: .planning/ROADMAP.md
        issue: "Phase 1 declares mode mvp with a goal outside the required user-story grammar."
    missing:
      - "Run /gsd mvp-phase 1 to establish the canonical user-story goal, then rerun goal verification."
  - truth: "Accepted status requires independent review of actual current source with no unresolved blocking findings."
    status: failed
    reason: "Accepted receipt records only one resolved low finding; the later independent phase review identifies six unresolved blockers. Three runtime defects were independently corroborated in the template, generated 68000 handlers, and runtime CMake wiring."
    artifacts:
      - path: experiments/cpu/acceptance-results.json
        issue: "Still records accepted/ACCEPTED; its sealed review findings do not include the later blockers."
      - path: third_party/musashi/m68k_in.c
        issue: "Legal register shifts, signed DIVS remainder packing and bit-31 masks contain undefined C expressions."
      - path: third_party/musashi/m68kmake.c
        issue: "Unchecked path copies, unsigned EOF sentinel and capacity guard errors remain."
    missing:
      - "Disposition the findings through bounded repair and renewed source/runtime evidence and independent review, or explicit rejection/defer with SDK admission blocked."
      - "Preserve the frozen cumulative budget and consumed attempt count; do not silently increase caps."

---

# Phase 1: CPU acceptance experiment Verification Report

> **Current lifecycle note — 2026-10-04:** The frontmatter status is now `stale`. This report is a preserved 2026-10-01 preflight-only refusal; its then-current `gaps_found` result and 0/5 score do not assess the later owned-core plans or the corrected roadmap goal. The original findings below remain historical evidence. Run `$gsd-execute-phase 01` to resume at the verification gates and refresh canonical phase-goal verification; `$gsd-verify-work` cannot rewrite a stale report.

**Phase Goal:** As a maintainer, I can reproduce acceptance of a C 68000 backend so I can build the diagnostic SDK on independent instances with explicit state and timing limits.
**Verified:** 2026-10-01T22:08:27Z
**Status:** gaps_found — pre-flight refusal; phase goal verification not completed.
**Re-verification:** No — no previous VERIFICATION.md exists.

## User Flow Coverage

The canonical roadmap declares **Mode: mvp**. The installed OpenGSD 1.14.0 format guard rejects its goal. Per the verifier's MVP instructions, verification stops here. This report records the guard and independently corroborated source concerns; it does not substitute a rewritten story or claim an implementation pass.

| Step | Expected | Evidence | Status |
| --- | --- | --- | --- |
| Establish the MVP story | Canonical “As a …, I want to …, so that ….” goal | Installed validator returns valid=false with both missing capability/outcome grammar errors | FAILED — BLOCKER |
| Rebuild and inspect candidate | Pinned C build and complete source/notice/host-call inventory | Not evaluated after format refusal | UNCERTAIN — WARNING; rerun required |
| Exercise independent instances | Isolated/interleaved/concurrent and cold/failure behavior | Not behaviorally evaluated in this run | UNCERTAIN — WARNING; rerun required |
| Inspect timing and continuation | Explicit qualified limits and identical fresh-destination continuation | Not behaviorally evaluated in this run | UNCERTAIN — WARNING; rerun required |
| Use acceptance for SDK admission | Current clean independent review and reproducible decision | Receipt says accepted; later blocking findings remain in compiled source | FAILED — BLOCKER |

No standard technical verification pass follows an incomplete MVP flow. Supporting source observations below are a bounded triage attachment, not a completed Steps 3–7 verification.

## Pre-flight Evidence

Command:

`node <installed-gsd-runtime>/bin/gsd-tools.cjs query user-story.validate --story 'As a maintainer, I can reproduce acceptance of a C 68000 backend so I can build the diagnostic SDK on independent instances with explicit state and timing limits.'`

Result: exit 0; `valid: false`; errors:

- Story must include “, I want to [capability],” (capability must be non-empty).
- Story must include “, so that [outcome].” (outcome must be non-empty).

The query's process success does not mean the goal passes validation. PLAN body prose contains “I want to … so that …”, but the roadmap owns the canonical goal. No override exists, and no goal text was changed.

Project context, all four PLAN/SUMMARY files, requirements/roadmap, validation/security/UI/source review reports, ACCEPTANCE.md and the acceptance receipt were consulted. SUMMARYs and audit sign-offs were treated as claims. No project-local skills were discovered; the agent-skills query supplied no additional skill package.

## Requirements Cross-reference

All plan requirement IDs exist in REQUIREMENTS.md. All five Phase 1 mapped requirements occur in at least one PLAN; **orphaned requirement IDs: none**. Checked boxes are task-level records and do not establish phase-goal verification.

| Requirement | Source Plans | Obligation | Result in this run |
| --- | --- | --- | --- |
| CPU-01 | 01, 02, 04 | Pinned reproducible C build; complete copied/generated/compiled/distributed inventory, notices and host calls; FPU/SoftFloat disposition | UNCERTAIN — full verification refused; generator findings affect tooling safety but do not by themselves disprove the exact pinned happy-path rebuild |
| CPU-02 | 02, 04 | Distinguishable alternating/concurrent/cold/failure instances with isolated baselines and no shared mutable machine state | UNCERTAIN — isolation not rerun; roadmap's additional host-survival assertion is contradicted by admitted undefined instruction expressions |
| CPU-03 | 01, 03, 04 | Actual progress, bounded stop/overshoot and selected IRQ/exception behavior, explicit unsupported scope | UNCERTAIN — selected timing experiment not rerun; instruction defects require acceptance disposition, not a fabricated claim that every selected timing case fails |
| CPU-04 | 02, 03, 04 | Complete state/callback inventory and backend continuation excluding host pointers/jump buffers | UNCERTAIN — state transitions not rerun; unrelated arithmetic defects do not establish a state-codec defect |
| CPU-05 | 01, 04 | Explicit finite-budget decision, commands/results/counterexamples and replacement/replanning for failed candidate | BLOCKED for accepted admission — current accepted seal does not disposition the later blockers; rejection/defer remains a permitted outcome |

**Score:** 0/5 roadmap truths verified in this run; remaining truths were not admitted to formal verification. No behavior-dependent truth was marked VERIFIED from presence or prior log claims.

## Corroborated Source Findings and Goal Impact

The phase source review did not run tests. This verifier independently checked the cited expressions and their generated/compiled wiring. Runtime termination remains a source-based consequence under the documented nonrecovering UBSan configuration, not a newly observed crash. No new fixtures or tests were created.

| Finding | Independent source evidence | Effect on goal |
| --- | --- | --- |
| CR-01 register shifts | m68k_in.c:1984–1987 evaluates src >> shift after DX & 0x3f before width guards; generated m68kops.c:3630–3635 and 68000 dispatch entry :34952; uint is unsigned int in m68kcpu.h:79 | BLOCKER to clean accepted C backend: count 32–63 on the admitted 32-bit configuration reaches undefined shift behavior |
| CR-02 signed division | m68k_in.c:4446 packs signed remainder << 16; generated register handler m68kops.c:12136–12164 and 68000 dispatch :34711 | BLOCKER to accepted host-safe backend: negative nonzero remainder reaches undefined signed shift |
| CR-03 high bit operations | m68k_in.c:2407 uses signed literal 1 << (DX & 0x1f); generated BCHG handler m68kops.c:4865 and 68000 dispatch :34456 | BLOCKER to accepted backend: legal bit 31 reaches unrepresentable signed shift |
| CR-04 generator paths | m68kmake.c:1248–1255 unchecked strcpy, empty-path strlen-1 index, unchecked appended slash | Separate host-tool safety blocker requiring disposition; exact pinned inputs avoid it, so it is not proof of failed happy-path regeneration |
| CR-05 generator EOF | m68kmake.c:594 returns size_t and -1; read_insert :1171–1202 checks unsigned length < 0 and advances pointer by the result | Separate malformed-template host-tool blocker requiring disposition |
| CR-06 generator bounds | m68kmake.c:795 and :1020 use > before indexed writes at the first disallowed table/body index | Separate generator capacity blocker requiring disposition |
| WR-01 historical replay | recovery-accounting/replay.py:19,31–57 places subprocess/hash/churn/cap checks inside assert; audit invokes that script | WARNING: Python optimization removes factual validation; frozen-budget trust needs explicit checks |
| WR-02 failed-attempt patches | record_attempt.py:35–46 normalizes “a” + str(pristine), incompatible with relative git diff a/ prefix | WARNING: relative pristine paths do not yield documented basename replay patches |

CMake explicitly compiles m68kops.c into cpu_runtime and separately compiles m68kmake.c as cpu_generator. The actual runtime's ADDRESS_UNDEFINED lane specifies `-fsanitize=address,undefined -fno-sanitize-recover=all`. Thus the runtime concerns reach the admitted C runtime; they are not dormant FPU or later-model branches. Selected arithmetic/store, timing and state tests cannot establish absence of defects in other admitted 68000 handlers.

The acceptance reducer checks high/critical entries in the sealed report's own review ledger (acceptance.py:123–139). That ledger currently contains only REV-LOW-01, resolved. The later 01-REVIEW.md does not automatically become a finding in the seal. A digest-bound prior review is reproducible evidence of that review, not proof that later source counterexamples disappear. The earlier security and validation sign-offs do not resolve this contradiction.

## Behavioral Spot-Checks and Probe Execution

SKIPPED — MVP pre-flight guard refused verification before implementation checks. No test suite, named behavioral test, build, server or probe was executed. Recorded native/sanitizer pass counts were not promoted to fresh behavioral evidence.

## Deferred Items

None moved to later phases. The current roadmap specifically gates SDK integration on CPU acceptance; Phase 2/3 goals do not specifically defer legal-instruction undefined behavior or unresolved acceptance findings.

## Human Verification Required

No artificial UI or manual runtime task is introduced for this internal foundation experiment. The required developer action is to establish a valid canonical MVP goal and choose a bounded disposition for source findings. This report makes no behavioral pass claim.

## Gaps Summary

Formal goal verification is blocked by the malformed MVP goal. Independently, the accepted receipt is insufficient for SDK admission while six later source blockers remain undispositioned; three legal 68000 runtime defects were corroborated through generated handlers and compilation. The isolated-baseline, selected timing and fresh-destination continuation claims remain unverified in this run, rather than being inferred from SUMMARYs.

Run `/gsd mvp-phase 1` to establish the canonical goal, then rerun verification. Repair/requalify within the unchanged remaining budget, or explicitly reject/defer and replan before SDK integration. No implementation, test, canonical goal, requirement checkbox or accepted receipt was modified. No commit was made.

---
_Verifier: gsd-verifier; pre-flight refusal and bounded source triage only._

