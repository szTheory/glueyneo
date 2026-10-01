---
phase: 01-cpu-acceptance-experiment
plan: "01"
subsystem: cpu
tags: [c17, musashi, unity, halted, source-provenance]
requires: []
provides:
  - Immutable pre-adaptation admission contract
  - Original manual-derived guest and verified intentional RED evidence
  - Failed explicit-context adaptation with pinned sources and compile counterexamples
affects: [01-02, 01-03, 01-04, 02-executable-diagnostic-sdk]
actuals:
  tokens: 463837
  tasks: 0
  commits: 3
plan_head_before: 3977c3bfbfdc752e1b43443aa3911c7012678177
tech-stack:
  added: [Musashi pinned candidate, Unity 2.7.0 test subset, CMake, CTest]
  patterns: [explicit-context experiment, assertion-first guest, fail-closed admission]
key-files:
  created:
    - experiments/cpu/ACCEPTANCE.md
    - experiments/cpu/evidence/attempt-1/receipt.json
    - experiments/cpu/evidence/attempt-1/build-failure.txt
    - experiments/cpu/evidence/attempt-1/source.patch
    - third_party/musashi/PROVENANCE.md
    - tests/cpu/ORACLE.md
    - tests/cpu/red-evidence.json
    - tools/cpu/adapt.py
    - tools/cpu/record_attempt.py
  modified: []
key-decisions:
  - Defer candidate investigation after executor correction limit; no backend acceptance or proven incompatibility.
  - Preserve the fixed numeric contract and block dependent plans until a bounded continuation or replan resolves the halt.
requirements-completed: []
coverage:
  - id: D1
    description: Original arithmetic/store test fails intentionally before implementation
    verification:
      - kind: other
        ref: node gsd-tools.cjs check tdd-red-evidence tests/cpu/red-evidence.json
        status: pass
    human_judgment: false
  - id: D2
    description: Adapted backend executes original guest
    verification:
      - kind: integration
        ref: cmake --build build/cpu
        status: fail
    human_judgment: false
duration: 18min
completed: 2026-10-01
status: halted
outcome: deferred
---

# Phase 1 Plan 1: CPU Acceptance Tracer — Halted Summary

**The frozen Musashi experiment has a verified arithmetic RED test and a
preserved explicit-context patch, but the adapted backend does not compile.**

## Outcome

Task 1 is unfinished and Task 2 was not started. The executor's three-inline-
correction limit triggered while compiling the first substantive adaptation
attempt. This is a procedural deferral, **not** a numeric-budget rejection or
proof that Musashi cannot satisfy the requirements. No second substantive
adaptation attempt started. The source remains unqualified and dependent plans
01-02, 01-03 and 01-04 must remain blocked. Phase 2 is not admitted.

## Accomplishments

- Committed the numeric admission contract before all source adaptation;
  immutable candidate is `313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd`.
- Explicitly imported only six Musashi inputs, two generated outputs and the
  four-file pinned Unity subset. Preserved notices and per-input hashes.
- Encoded two original MIT arithmetic/store guests and documented primary
  manual pages, independent expectations and reset assumptions.
- Compiled the initial assertion scaffold and ran one targeted intentional
  failure: `guest_adds_and_stores`, expected 10 versus observed 0. The installed
  TDD evidence gate returned `RED_EVIDENCE_OK`.
- Preserved the unfinished source transform, exact current source identities,
  source diff, measured patch/output sizes and sanitized build failure.

## Commits

1. `f9e7dda` — docs(01-01): freeze CPU candidate admission limits.
2. `6ecfa4b` — test(01-01): assert original guest arithmetic before backend adaptation.
3. `f4eb1af` — chore(01-01): preserve halted context adaptation and compile counterexamples.

The third commit preserves a failed attempt; it is not a GREEN implementation
commit. No task is reported complete. The three-commit count is measured from
the on-disk plan ledger before this summary commit. Token actuals are realized
diff characters divided by four (rounded up), including the large imported,
generated and evidence files; they are not agent token consumption.

## Verification Evidence

| Command/evidence | Observed outcome |
|---|---|
| Configure experiment with Ninja | Passed; native Apple Clang 21.0.0.21000101 selected |
| Initial scaffold build | Passed before backend import; not CPU execution evidence |
| Initial full scaffold guest runner | 3 tests, 3 expected missing-implementation failures; not used as the specific RED gate |
| Guest runner `--red` | 1 test, 1 intended arithmetic/store assertion failure, exit 1 |
| `tools/cpu/red.py` and installed `check tdd-red-evidence` | Exact Unity assertion translated to TAP with raw output retained; RED_EVIDENCE_OK |
| Separate C17 host generator | Produced 1,967 handlers from 518 primitives |
| Adapted core-only compilation | Passed after operand-helper and integer-alias corrections; not full runtime closure |
| Final `cmake --build build/cpu` | Failed, exit 1; receipt and diagnostics preserved |
| Guest and consequential negative CTests | Unrun against adapted backend; build prerequisite failed |
| Closure/budget/regeneration controls | Unimplemented and unrun; Task 2 blocked |
| `git diff --cached --check` | Reported retained upstream/generated whitespace and literal patch-context whitespace; not a clean-format claim |

No stale scaffold executable is treated as a successful adapted backend.
No tests were weakened, no golden expectations were changed, and no source
cap was raised. There is no runtime sanitizer or platform-support claim.

## Budget and Effort

Frozen maxima remain two attempts, six handwritten input files, 5,000 total
handwritten added/deleted lines (including helpers), 500 semantic repair lines,
600 helper/shim lines, 16 active hours total/eight per attempt, and exactly two
generated files capped at 50,000 lines and 2 MiB.

Measured current patch: **1,761 upstream added/deleted lines** and **220 current
support lines**, with the **15-line discarded RED scaffold also charged**:
1,996 current subtotal. Generated files total **36,559 lines / 831,218 bytes**.
The source receipt contains hashes and per-file counts. Complete cumulative
accounting and semantic classification remain unreviewed; these figures are
not a passing Task 2 budget audit.

Conservative charged attempt interval: 16:19:53Z–16:31:13Z on 2026-10-01,
680 seconds including preparation/tool time. Adaptation followed the RED
commit at 16:24:08Z. Evidence/summary closeout followed the halt with no further
backend fixes. Plan preparation began approximately 16:16Z; total session was
about 18 minutes through summary creation.

## Deviations from Plan

**[Rule 3 — Blocking issue] Installed RED checker only parses TAP/Node-style
test summaries.** Added a narrow host-only translator that requires the exact
single Unity arithmetic assertion and preserves original relative-path output.
It does not manufacture a failed test from a compile error or crash. Verified
with the installed `RED_EVIDENCE_OK` result in the RED commit.

The planned tracer did not reach GREEN. The executor's correction limit
required stopping with remaining compiler errors. This planned-work failure
is preserved honestly rather than reported as an architectural rejection.

## Deferred Issues

1. Direct `OPER_I_8/16/32()` calls in the opcode template do not supply the
   context argument required by the adapted macro expansion. The generated
   source fails to compile. Repair must change template/generator inputs,
   never hand-edit generated files.
2. Adapter `CPU_STOPPED` status conflicts with the backend macro in
   `cpu_adapter.c:63`.
3. The incomplete runtime needs the full guest, bounded-fault and zero-budget
   checks, source closure and cumulative budget controls before this tracer
   can complete. Subsequent isolation, state and timing evidence is absent.
4. Source-level host faults, reset accounting and exception trap lifetime
   still require actual runtime review/testing. A context-shaped API alone
   does not prove safety or isolation.

## Known Stubs and Unqualified Source

No adapted runtime success is claimed. The RED-only nonexecuting adapter was
replaced, but its historical commit remains intentionally failing evidence.
Upstream generator TODOs (`m68kmake.c:53`, `:322`), later-model timing TODOs
(`m68kcpu.c:409`, `:875`) and later-model opcode TODOs remain imported text;
68000 compiled closure is not proven and no later model is admitted. These
and unrun verification are recorded in `.planning/WINDOWS.md`.

## Next Work

Reconcile this halted attempt and its cumulative budget in a bounded
continuation/replan before any further adaptation or dependent implementation.
All CPU-01–CPU-05 requirements remain pending in this plan; Phase 1 is
incomplete. A second attempt is not a fresh budget. No external credentials
or human-only hardware evidence caused this halt.

## Self-Check: PASSED (Artifact Integrity Only)

Verified the receipt's source/support/generated files and this summary exist,
and Git resolves all three reported commits. This check confirms preserved
evidence, not implementation success; the build remains failed.
