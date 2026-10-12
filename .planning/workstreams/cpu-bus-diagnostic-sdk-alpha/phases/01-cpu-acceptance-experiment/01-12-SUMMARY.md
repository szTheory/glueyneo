---
phase: 01-cpu-acceptance-experiment
plan: "12"
subsystem: owned-cpu-review
tags: [68000, c17, adversarial-review, state-validation, sanitizer]
requires:
  - phase: 01-cpu-acceptance-experiment Plan 11
    provides: private same-build state continuation and source-bound inventory
provides:
  - Exact-revision independent review of the owned CPU source and evidence
  - Atomic rejection of impossible private instruction-counter continuations
  - Sanitizer-clean malformed-state test fixture initialization
affects: [owned-cpu-admission, phase-01-review, fresh-run-qualification]
actuals:
  tasks: 4
  commits: 4
  active_seconds: 13972
tech-stack:
  added: []
  patterns: [independent exact-revision review, conservative state-counter invariant, atomic malformed-record regression]
key-files:
  created:
    - experiments/owned_cpu/REVIEW.md
  modified:
    - experiments/owned_cpu/cpu.c
    - experiments/owned_cpu/cpu.h
    - experiments/owned_cpu/SUBSET.md
    - experiments/owned_cpu/state-inventory.json
    - tests/owned_cpu/test_state.c
    - tests/owned_cpu/negative.py
    - experiments/owned_cpu/budget-ledger.json
key-decisions:
  - "Review findings were bound to the pre-repair revision; repaired behavior is verified separately and Plan 14 must re-review the final revision."
  - "Private continuation validation uses the supported subset's four-clock minimum only as a conservative counter-consistency bound, not as a timing oracle or admission claim."
  - "Keep the private state record same-build and destination-owned; guest memory, bus and allocator bindings are not serialized."
patterns-established:
  - "Review exact source, test, build and fixture identities; treat historical defects as prompts, not current evidence."
  - "Reject malformed continuation records before destination state or bus activity can change."
requirements-completed: []
coverage:
  - id: R1
    description: Independent review records exact-revision findings, evidence denominators, oracle ancestry, and unsupported claims.
    requirement: CPU-05
    verification:
      - kind: other
        ref: experiments/owned_cpu/REVIEW.md
        status: pass
    human_judgment: false
  - id: R2
    description: Restore rejects an impossible instruction-counter mismatch atomically.
    requirement: CPU-03
    verification:
      - kind: unit
        ref: tests/owned_cpu/test_state.c#instruction_counter_mismatch_rejects_atomically
        status: pass
      - kind: integration
        ref: ctest --test-dir build/owned-cpu -R '^owned_cpu_(state|negative)$' --output-on-failure --no-tests=error
        status: pass
    human_judgment: false
  - id: R3
    description: Malformed-state tests initialize destination allocator bookkeeping and pass repeated ASan+UBSan execution.
    requirement: CPU-03
    verification:
      - kind: integration
        ref: ctest --test-dir build/owned-cpu-asan -R '^owned_cpu_state$' --repeat until-fail:10 --output-on-failure --no-tests=error
        status: pass
    human_judgment: false
duration: 119min
completed: 2026-10-02
status: complete
---

# Phase 1 Plan 12: Independent CPU review and bounded state repairs

**The exact-revision review found two state-path defects, and both were repaired with direct regressions.** Plan 12 does not admit the backend; the final evidence collection and independent decision remain in Plans 13 and 14.

## Performance

- **Duration:** 1h 59m
- **Started:** 2026-10-02T22:55:51Z
- **Completed:** 2026-10-03T00:54:26Z
- **Tasks:** 4
- **Files modified:** 8
- **Agent effort:** 13,972 person-seconds across the primary agent, reviewer and fixer intervals.

## Accomplishments

- An independent reviewer examined the owned source, CMake closure, tests, state inventory, oracle, contract, Unity provenance and prior findings at `1e451ac283cf625d2ddebc8a750f09524b41d58b`. The report records source/build/fixture identities, test denominators, primary-reference ancestry and unsupported claims. It found no actionable diagnostic, instruction-semantic, timing, bus, isolation, host-fault or provenance issue in the reviewed subset.
- The initial native run passed 12/12 CTest cases. TSan passed 12/12. ASan+UBSan passed 11/12 because the malformed-state test initialized callback bindings on an uninitialized destination fixture; repeating the state test reproduced the same failure. The destination fixture is now zero-initialized before those bindings are created.
- Restore now rejects an instruction counter inconsistent with the saved cycle counters. The regression captures one MOVEQ (one completed dispatch and four instruction clocks), drops only the counter, then checks `OWNED_CPU_INVALID_ARGUMENT` and unchanged destination fields, memory and bus trace. The state negative control now expects this rejection rather than treating the malformed record as a valid continuation.
- Updated the private subset contract, core SHA-256 identity and state inventory hashes. No guest-memory, host callback or allocator binding was added to the saved record.
- Task 3 required no timing, bus, isolation or host-fault source changes. The state omission expectation in `negative.py` changed only to match the repaired state validation. The reviewer’s restore-over-ready observation remains inconclusive because the contract wording does not define that destination precondition; no finding or support claim was added.

## Task Commits

1. **Task 1: Independent exact-revision review** — `39f8a43` (`docs(01-12): record independent CPU review`).
2. **Tasks 2–4: Repair state findings and controls** — `8678438` (`fix(01-12): validate private state instruction counters`).
3. **Plan effort receipt** — appended to `budget-ledger.json` at `8678438`; closeout metadata is committed separately.

## Test Evidence

- On the committed revision, `cmake --build build/owned-cpu --parallel 2` succeeded. Native diagnostic/semantics/negative passed 3/3; state/negative passed 2/2; the combined diagnostic/semantics/state/negative gate passed 4/4.
- ASan+UBSan diagnostic/semantics/negative passed 3/3; state passed `--repeat until-fail:10` (10/10); state/negative passed 2/2. The failure found by BL-01 is cleared. TSan was not rerun after the repairs because they do not affect shared or concurrent state; the independent review’s pre-repair TSan run was 12/12.
- `python3 tools/owned_cpu/inventory.py check --build-dir build/owned-cpu` passed for 26 fields and 10 compiled translation units. The inventory unit suite (9 tests) passed. `git diff --check` passed during repair.
- The independent report’s native/ASan+UBSan/TSan evidence belongs to reviewed revision `1e451ac…`; the post-repair tests above belong to `8678438…`. Native `owned_cpu_state` SHA-256: `3b5a13a0da07c04a9fe19b1345b442d50e7c2458bbf33fa2c33922a3b72db68a`; ASan+UBSan `owned_cpu_state` SHA-256: `702d8f44a89863a9cd78e4ea8e1df62ef45a873f20844bf81daacf5083ae5a54`.
- Final source identities: `cpu.c` `8ac6ded7859184651f6eb3fff8a87c073f8e24a98d66175b64c3d86f69cbd15f`; `cpu.h` `afdc50cbfdce47cdb17f881fed6fe47b72d919e3220b9c599f6262f868d50eee`; `test_state.c` `25b12a79f08049cd7eb0bdf8af2f97ca74ba1798184397bccc90fa1cff308b31`.
- Build identities: native CMake cache `9122ef4cb48e4e903f3fc3f305dc0ee9b9d885c1999fd9d8970674330b1d8d3b`, Ninja file `f6bf68327b2c91e8265b742d17f18e20e2918645e87c6dfadfb68596992b9ae6`, compile database `9ec056bca4335738576e4d0e3285f81ac1025e7f62aabd4cd6ac775bdedea838`; ASan+UBSan cache `66a2c79a355c79e5c9720d31928299192df4a4023d0792f5723a41c2ac811869`, Ninja file `bcc1e34b51e1309d9682955a1a030c5a37fb77f443337221d1beec0b013680c0`, compile database `3031937f4ddafdf3fc09cbe0806e784e5e9538f28b766faa6af9a09d81625a86`.
- The `plan-01-12` ledger entry records 13,972 active agent-seconds. Cumulative effort is 30,368 seconds; runtime churn is 1,206 and test/tool churn is 4,538 added/deleted nonblank lines. The frozen budget check passes with no pause. The independent report contains the complete initial evidence, oracle lineage, finding dispositions and unsupported-claim limits.

## Deviations and Remaining Work

- One state finding crossed the task file groups by requiring a `cpu.c` invariant, a `test_state.c` regression, and the matching state-counter negative-control update in `negative.py`. All changed files were explicitly listed in Plan 12’s overall `files_modified` scope; other negative controls were unchanged.
- The private continuation still makes no public ABI, durable save, replay, cross-build compatibility, full-MC68000, hardware-equivalence or ASVS certification claim. CPU-01–05 remain Pending, Phase 01 remains open / GAPS_FOUND, and Phase 02 remains gated. Plan 14 must independently review the post-repair revision.

## Self-Check: PASSED

- Both reported findings have direct repairs; the destination-atomicity and sanitizer regressions pass on the repaired revision.
- Required native, ASan+UBSan, inventory and review-marker checks pass. The ledger records exact build, fixture and test identities without changing frozen caps or clearing GAPS_FOUND.
- Plans 13 and 14 remain required before the execute-phase run can close.

---
*Phase: 01-cpu-acceptance-experiment*
*Completed: 2026-10-02*
