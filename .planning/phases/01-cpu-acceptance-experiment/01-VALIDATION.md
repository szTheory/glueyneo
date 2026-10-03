---
phase: "01"
slug: "cpu-acceptance-experiment"
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-01"
updated: "2026-10-03"
---

# Phase 01 — Validation Strategy

The original map below records the historical Plan 01-01–01-04 candidate evidence. The current plan set and its per-task commands are covered by the 2026-10-03 audit at the end of this file. Validation coverage does not establish backend admission; CPU-01–05 remain Pending while F14-03 is unresolved.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | Pinned Unity 2.7.0, explicit C runners, CTest, and Python standard-library controls |
| Config files | Root `CMakeLists.txt` and `experiments/cpu/CMakeLists.txt` |
| Configure | `cmake -S . -B build/cpu-final -G Ninja -DGLUEYNEO_CPU_EXPERIMENT=ON` |
| Build | `cmake --build build/cpu-final` |
| Full run | `ctest --test-dir build/cpu-final -L cpu --output-on-failure --no-tests=error` — 30/30, as recorded by Plan 01-04 |
| Instrumented runs | Plan 01-04 acceptance receipt records 8 ASan/UBSan and 18 TSan passes; unavailable lanes remain explicitly unsupported |

ASan/UBSan uses `build/cpu-asan` with `-DGLUEYNEO_CPU_SANITIZER=ADDRESS_UNDEFINED`; TSan uses `build/cpu-tsan` with `-DGLUEYNEO_CPU_SANITIZER=THREAD`. Both configurations instrument the actual adapted runtime as well as tests. Final sanitizer results are recorded in the acceptance receipt and Plan 01-04 evidence; compiler launch probes alone are not counted as backend sanitizer results. The runnable infrastructure was established in the first tracer, with no separate scaffolding-only execution wave.

## Sampling Rate

- After every task: run its affected tests and the quick suite once available.
- After every plan wave: run the full suite and applicable sanitizer configurations.
- Before phase acceptance: run the full suite on the current revision, capture exact input/toolchain/source identities, reconcile the budget ledger, and obtain independent review.
- Use finite iterations and CTest timeouts. Measure feedback latency before claiming a time budget is met.
- Every executable test must assert behavior and reject zero tests. A supervised negative control must fail its intended assertion; a crash does not count.

## Per-Task Verification Map

These rows use actual plan/task identifiers. Every command has a nearest following fails_when sibling in its PLAN.md. A nonzero command, zero tests or the named behavioral mismatch is failure; missing infrastructure must be implemented by the owning task before verification.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | CPU-01, CPU-03, CPU-05 | T-01-01–04 | Freeze precedes adaptation; bounded original arithmetic guest and consequential control | Integration | `ctest --test-dir build/cpu-final -R '^cpu_guest(_negative)?$' --output-on-failure --no-tests=error` | `tests/cpu/test_guest.c`; acceptance receipt | COVERED |
| 01-01-02 | 01 | 1 | CPU-01, CPU-05 | T-01-01, T-01-04 | Licensed complete closure; reproducible generation and inclusive caps | Source/control | `ctest --test-dir build/cpu-final -R '^cpu_(closure|budget|audit_controls)$' --output-on-failure --no-tests=error` | `tests/cpu/test_audit.py`; `tests/cpu/test_inventory.py` | COVERED |
| 01-02-01 | 02 | 2 | CPU-02, CPU-04 | T-01-05–06 | Distinct/cold instances retain complete ownership | Concurrency | `ctest --test-dir build/cpu-final -R '^cpu_(isolation(_negative)?|cold)' --output-on-failure --no-tests=error` | `tests/cpu/test_isolation.c`; `tests/cpu/test_cold.c` | COVERED |
| 01-02-02 | 02 | 2 | CPU-01, CPU-02 | T-01-07–08 | Every allocation failure and guest fault preserves healthy witness; actual instrumentation | Fault/inventory | `ctest --test-dir build/cpu-final -R '^cpu_(faults|inventory|budget)$' --output-on-failure --no-tests=error` | `tests/cpu/test_faults.c`; `tests/cpu/test_inventory.py` | COVERED |
| 01-03-01 | 03 | 3 | CPU-03 | T-01-09–10 | Requests/reset/STOP/IRQ/exceptions remain bounded and source-qualified | Timing/boundary | `ctest --test-dir build/cpu-final -R '^cpu_(timing|faults|isolation|budget)$' --output-on-failure --no-tests=error` | `tests/cpu/test_timing.c`; `tests/cpu/test_faults.c` | COVERED |
| 01-03-02 | 03 | 3 | CPU-04 | T-01-11–12 | Fresh destination continues complete state; invalid restore is atomic | Continuation | `ctest --test-dir build/cpu-final -R '^cpu_(state(_negative)?|inventory|timing|isolation|budget)$' --output-on-failure --no-tests=error` | `tests/cpu/test_state.c`; `tests/cpu/test_inventory.py` | COVERED |
| 01-04-01 | 04 | 4 | CPU-01–05 | T-01-13–14 | Empty/stale/over-budget evidence cannot admit; source/runtime evidence separate | Qualification controls | `python3 tools/cpu/acceptance.py self-test` | `tests/cpu/test_acceptance.py`; acceptance controls log | COVERED |
| 01-04-02 | 04 | 4 | CPU-01–05 | T-01-13–16 | Current independent review and all mandatory evidence required; rejection is GAPS_FOUND | Admission | `python3 tools/cpu/acceptance.py verify --require-accepted` | `tools/cpu/acceptance.py`; accepted receipt and independent review | COVERED |

## Wave 0 Requirements

- [x] C17 target-based CMake, CTest and pinned Unity with explicit nonempty runners.
- [x] Private CPU adapter, bounded bus, annotated original guest bytes, independent manual-derived expectations, and two distinguishable scenarios.
- [x] Regeneration/source closure manifest, upstream patch counter, semantic change classification and cumulative attempt/time ledger.
- [x] Cold-process concurrency runner, fail-each-allocation injection and healthy-instance witness, bounded trace observations.
- [x] Private field-wise state codec and complete state inventory, excluding host pointers and jump buffers.
- [x] Separate sanitizer configurations; unavailable or unsupported outcomes remain explicit.
- [x] Current-revision acceptance receipt with exact source/configuration/input identities and a rejection path that leaves CPU-01 through CPU-04 pending.

## Manual-Only Verifications

No physical hardware, commercial media or account action is required for this local CPU experiment. Automated evidence covers only the selected behaviors and cannot establish hardware-wide fidelity. Independent source/rights review accompanies the automated checks.

## Validation Sign-Off

- [x] All tasks have an automated verification or explicit Wave 0 dependency.
- [x] No three consecutive tasks lack automated verification.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags; all loops and test runs are bounded.
- [x] Recorded feedback latency and test counts are retained with phase evidence.
- [x] `nyquist_compliant: true` is set only after a validation audit establishes it.

**Approval:** Nyquist audit found all phase tasks and requirements covered by retained current-revision evidence.

## Validation Audit 2026-10-01

| Metric | Count |
|--------|-------|
| Genuine coverage gaps | 0 |
| Task rows covered | 8/8 |
| Requirements covered | 5/5 |
| Tests rerun during audit | 0 |

The original `Pending`/`Missing` entries were stale planning metadata. The final Plan 01-04 summary records 30/30 native CTests, 8/8 ASan/UBSan tests, and 18/18 TSan tests; the retained pre-acceptance collection log records 28 native CTests before the two acceptance CTests were included. Unsupported platform and hardware claims remain explicitly outside this phase's scope.

## Current Execution Validation Audit 2026-10-03

The current phase plan set contains 38 tasks across 16 plans. Each task has at least one nonempty automated verification command (105 command declarations total); exact commands and failure conditions remain in each plan's `<verify>` block, and outcomes are recorded in the corresponding SUMMARY. No tests were added or rerun during this audit. The original Plan 01-01–01-06 receipts remain historical and do not qualify the owned-core admission decision.

| Plan | Tasks | Automated checks per task | Validation record |
|------|-------|---------------------------|-------------------|
| 01-01 | 2 | 3, 2 | Historical candidate checks; not current admission evidence |
| 01-02 | 2 | 2, 8 | Historical candidate checks; not current admission evidence |
| 01-03 | 2 | 2, 4 | Historical candidate checks; not current admission evidence |
| 01-04 | 2 | 4, 2 | Historical candidate decision; current rejection remains authoritative |
| 01-05 | 3 | 2, 1, 5 | Scope/admission reconciliation recorded in SUMMARY |
| 01-06 | 1 | 1 | Developer direction checkpoint recorded in SUMMARY |
| 01-07 | 3 | 1, 1, 1 | Freeze/governance checks recorded in SUMMARY |
| 01-08 | 2 | 3, 4 | Original diagnostic and negative control recorded in SUMMARY |
| 01-09 | 2 | 2, 3 | Timing/exception checks recorded in SUMMARY |
| 01-10 | 2 | 2, 6 | Isolation, fault and inventory checks recorded in SUMMARY |
| 01-11 | 2 | 2, 4 | Continuation checks recorded in SUMMARY |
| 01-12 | 4 | 1, 2, 2, 2 | Bounded repair and regression checks recorded in SUMMARY |
| 01-13 | 3 | 1, 5, 3 | Inventory, preset and fresh-run checks recorded in SUMMARY |
| 01-14 | 3 | 1, 1, 1 | Independent review and unqualified seal recorded in SUMMARY |
| 01-15 | 2 | 6, 4 | Archive/validator/timing checks passed; rule remains unresolved, so behavior repair was withheld |
| 01-16 | 3 | 4, 1, 6 | Four fresh lanes passed 12/12 each; independent review retains F14-03 HIGH/open |

### Current Owned-Core Test Evidence

- Plan 01-15's normal and optimized validator suites passed 13/13 each; the direct timing target passed 23 Unity cases. These checks validate archive integrity, ledger preservation and observed fixture behavior; they do not establish the hardware saved-PC rule for `ILLEGAL` `0x4AFC`.
- Plan 01-16's four fresh qualification lanes each passed 12/12 cases. Its final receipt checks passed, while `review-check` returned its expected blocking result for F14-03.
- The independent primary-source review could not resolve the competing fault-PC and next-PC readings. That is a documented evidence limitation and phase blocker, not a missing test suite. No CPU requirement is promoted to complete.

## Decision Reconciliation 2026-10-03 — Preserve Unknown

The user selected P01-C-13 after Plan 01-17's bounded acquisition and independent adjudication returned an ambiguous saved-PC verdict. Existing automated evidence and historical task counts above remain unchanged; Plan 01-17's document/preservation checks are recorded in its SUMMARY and are not new CPU behavior coverage. This decision authorizes no test, oracle, contract, runtime, supported-subset or admission change. In particular, accepting either `$100` or `$102` in a conformance test would weaken the frozen contract and would not resolve F14-03. A future behavior test becomes a conformance gate only after genuinely applicable authority or a separately explicit owner decision establishes the supported claim. Keep T-01-15-03 HIGH/open; this reconciliation does not qualify phase verification or admission.

| Metric | Count |
|--------|-------|
| Current plan tasks with automated verification | 38/38 |
| Declared automated verification commands | 105 |
| Nyquist coverage gaps | 0 |
| Tests rerun during this audit | 0 |

## P01-C-14 Planning Reconciliation — 2026-10-03

The owner separately selected P01-C-14 after preserve-unknown P01-C-13.
P01-C-14 changes only the owned candidate's exact-0x4AFC supported boundary;
original-silicon saved PC remains unknown. All previous audit sections and
denominators are preserved as historical evidence. Their covered/validated
labels do not qualify the changed candidate. Plans 01-18–01-21 add ten tasks;
their automated commands and adjacent failure conditions are declarations for
execution, with no native build/test, qualification, review or security audit
performed by this planning reconciliation. Existing infrastructure supplies the
commands; no scaffolding wave, package, external API or schema push is needed.

| Task | Planned evidence | Threat refs | Status |
|---|---|---|---|
| 01-18-01 | Direct exact unsupported PC/IR/trace/counters and retained timing | T-01-29,T-01-32 | PLANNED |
| 01-18-02 | Immutable root/archive, additive amendment and normal/optimized controls | T-01-30,T-01-31 | PLANNED |
| 01-19-01 | Semantic/fresh-owner continuation and complete inventory | T-01-33 | PLANNED |
| 01-19-02 | One-case exact unsupported-status negative control | T-01-34 | PLANNED |
| 01-19-03 | Legacy/current profiles, current review, security binding/deferred seal | T-01-35,T-01-36 | PLANNED |
| 01-20-01 | Current candidate documentation and licensed source closure | T-01-37,T-01-39 | PLANNED |
| 01-20-02 | Exact fresh native/sanitizer qualification and preserved histories | T-01-38,T-01-40 | PLANNED |
| 01-21-01 | Independent exact-current source/control review | T-01-41 | PLANNED |
| 01-21-02 | Independent ASVS L1 high-blocking reassessment and actual task map | T-01-42,T-01-15-03 | PLANNED |
| 01-21-03 | Final exact review/security/receipt/accounting, admission deferred | T-01-43,T-01-44 | PLANNED |

All nine supplied specless assumption flags remain unresolved (including
three unclassified rows); planning creates no resolution or new acceptance
predicate. F14-03/T-01-15-03 remain HIGH/open until actual reconciliation,
fresh qualification, independent review and security gates pass. CPU-01–05
remain Pending, Phase01 open/GAPS_FOUND, Phase02 gated. The earlier Nyquist
sign-off is historical, not a fresh audit of these changed claims. Execution's
01-21-02 must append actual commands, denominators and outcomes without
overwriting these planning declarations or the retained audits.

## P01-C-14 execution validation audit — 2026-10-03

Independent non-author assessor: `/root/phase01_plan21/security_assessor`.
Evidence revision: `0e2003fe8fdb4a1e804fb6a5fe92c618b909b43a`; current profile
`owned-p01-c14-1`, collection
`53ea6a7162902edea4e4372e85b3713ad4092f0522501c33a59115573101337e`.
The preceding audits and ten PLANNED rows are retained as dated declarations.
This table records implemented outcomes; command details and actual assessor
denominators are in the bounded SECURITY reassessment. None of these rows
completes a CPU requirement or phase admission.

| Task | Actual verification command/control | Nearest failure condition | Threat refs | Actual outcome |
|---|---|---|---|---|
| 01-18-01 | Targeted `ctest --preset owned-debug -R '^owned_cpu_(timing\|unsupported_negative\|semantics\|state\|faults\|isolation\|cold_processes\|state_negative\|timing_negative\|isolation_negative\|diagnostic_negative)$' --output-on-failure --no-tests=error`; direct timing binary | Nonzero/empty count, wrong PC/IR, vector/frame/memory/register mutation, charge/dispatch or failed-fetch classification | T-01-29,T-01-32 | EXECUTED: targeted8/8; direct timing25/25, retained exceptions/prior charges pass |
| 01-18-02 | `python3 [-O] -m unittest discover -s tests/owned_cpu -p test_contract.py`; `contract.py validate` | Frozen root/archive/history/caps change; missing/tampered/broadened/reordered amendment or hardware-PC selection accepted | T-01-30,T-01-31 | EXECUTED:23/23 separately normal/-O; archive/history/pending gate pass |
| 01-19-01 | Direct `owned_cpu_state`; semantics/state in targeted CTests; `inventory.py check --build-dir build/owned-debug` | Missing boundary, stale identity, mismatched result/state/bus or changed destination binding | T-01-33 | EXECUTED: state5/5,13 boundaries/78 calls; semantics17 via targeted test; inventory26 fields/10 compiled sources |
| 01-19-02 | `negative_timing.py --unsupported build/owned-debug/experiments/owned_cpu/owned_cpu_timing`; `negative_timing.py --self-test` | Child crash/empty/unrelated failure, duplicate summary/status, altered count/ignored or timeout accepted | T-01-34 | EXECUTED: one exact child status failure; wrapper2/2 adversarial methods; both negative CTests pass |
| 01-19-03 | `python3 [-O] -m unittest discover -s tests/owned_cpu -p test_acceptance.py` | Legacy/current spoof, stale/ambiguous/blocked independent attestation, changed audit bytes or accepting deferred seal | T-01-35,T-01-36 | EXECUTED:21/21 separately normal/-O; actual current seal still belongs to21.3 |
| 01-20-01 | `contract.py validate`; read-only `acceptance.snapshot()` equality against collection/HEAD and source rights/path audit | Missing/stale source or unsupported hardware/dependency/publication claim | T-01-37,T-01-39 | EXECUTED:39/39 inputs and public-path scan; retained MIT/pinned Unity notices and original fixtures |
| 01-20-02 | `acceptance.py verify`; `inventory.py check`; lane artifact SHA-256 and historical prefix comparisons; `contract.py budget` | Failed/unknown/skipped lane promoted, missing instrumented object/artifact, changed historical prefix or budget pause | T-01-38,T-01-40 | EXECUTED in Plan20: four lanes13/13 each,52 total; assessor reconciles all44 artifacts and histories, does not rerun four lanes |
| 01-21-01 | Independent review-check against recorded `a3cec086a75c3c7783bcde610f6e8c4234354eeb`; independent reviewer Debug build/native/control evidence | Current review stale/ambiguous/not independent or unresolved high finding | T-01-41 | EXECUTED: reviewer own build22 steps/native4/4 plus normal/-O suites; assessor review-check clean; Task1 commit metadata source equality verified |
| 01-21-02 | `contract.py validate`; `acceptance.py verify`; `inventory.py check`; assessor direct native/control runs and bounded security-binding validation | Changed claim/source/state/receipt, unsupported mitigation or missing task/threat map | T-01-42,T-01-15-03 | EXECUTED: applicable native L1/block-high, zero current high/critical; candidate mitigation supersedes original withheld mitigation only within P01-C-14 |
| 01-21-03 | Live `review-check --revision HEAD`, `seal --defer-admission --security .planning/phases/01-cpu-acceptance-experiment/01-SECURITY.md`, read-only `verify` and `contract.py budget` | Final binding stale, high finding, backend admitted, history changed or cap pause | T-01-43,T-01-44 | BLOCKED final gate: verify at33c2f48 fails stale sealed security document; reseal preflight rejects existing stale receipt. Initial6357146 clean review/deferred seal and budget44,170s/34 pass remain historical; final audit hash is not successfully sealed |

Assessor independently executed88 Python method runs (contract23 and
acceptance21, each normal/-O), targeted10/10 CTests across two commands,
direct timing25 and state5, plus wrapper2/2. Six native consequential controls,
13 continuation boundaries/78 calls, retained fault safety and16 cold processes
are covered by these native targets. These are runs of collector-built Debug
binaries; the separate source reviewer rebuilt its own Debug target. Full
Debug/Release/ASan+UBSan/TSan52/52 remains Plan20 collection evidence, independently
identity-checked here. This audit did not generate receipts, tests or code.

Applicable9=unresolved9+resolved0 remains unchanged: CPU-01 concurrency;
CPU-02/03/04 unclassified; CPU-05 boundary, adjacency, empty, ordering, precision.
None is reclassified as resolved by the candidate amendment or green tests.
Original-silicon saved PC stays unknown; intentional ILLEGAL users remain
incompatible. CPU-01–05 Pending, Phase01 incomplete/GAPS_FOUND and Phase02 gated.

Final metadata confirmation binds `635714631770a6450e1f2e46bef6a377571aabd5`:
the same assessor verified all39 committed inputs equal the current snapshot
and collection source map before rebinding SECURITY. Following the executor's
real Task3 seal, the assessor independently executed read-only receipt verify,
budget and exact seal/source/security equality checks. All pass with the same
collection/amendment identities. Ten new tasks now have executed evidence;
the current report append requires final audit-hash resealing rather than a
new behavioral qualification. Earlier PLANNED and historical audits remain
unaltered. This closes the candidate evidence tasks while phase verification
and backend admission remain pending.

### Final Task3 gate failure — supersedes clean closeout claim

The preceding initial pass and proposed reseal are historical observations.
At `33c2f480bd19f7008723ef9e6523284cf9b622f4`, the assessor independently
reran `python3 tools/owned_cpu/acceptance.py verify` and reproduced nonzero
`stale sealed security document`. Updated SECURITY bytes differ from the
initial seal's hash; the reseal implementation verifies the stale old receipt
before replacing it. Final21.3 is BLOCKED and T-01-43 HIGH/open. Nine completed
task outcomes and all native/initial-seal counts remain; the tenth task has
executed failure evidence and is incomplete. The claimed clean closeout above
is superseded by this final failure, not rerun away. Original silicon remains
unknown, nine specless flags unresolved, requirements Pending and Phase01/
Phase02 gates unchanged. Gap repair and independent final binding are required.
