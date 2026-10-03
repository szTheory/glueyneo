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

| Metric | Count |
|--------|-------|
| Current plan tasks with automated verification | 38/38 |
| Declared automated verification commands | 105 |
| Nyquist coverage gaps | 0 |
| Tests rerun during this audit | 0 |
