---
phase: "01"
slug: "cpu-acceptance-experiment"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-01"
---

# Phase 01 — Validation Strategy

This is a proposed execution contract reconciled with the four executable plans and [phase research](01-RESEARCH.md), not a record of passing CPU tests. Status remains draft; no implementation or validation audit has run.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | Pinned Unity 2.7.0, explicit C runners and CTest |
| Config file | `CMakeLists.txt` — Wave 0 creates it |
| Configure | `cmake -S . -B build/cpu -G Ninja -DGLUEYNEO_CPU_EXPERIMENT=ON` |
| Build | `cmake --build build/cpu` |
| Quick run | `ctest --test-dir build/cpu -L cpu-fast --output-on-failure --no-tests=error` |
| Full run | `ctest --test-dir build/cpu -L cpu --output-on-failure --no-tests=error` |
| Runtime | Unmeasured; quick feedback target is under 30 seconds |

ASan/UBSan uses `build/cpu-asan` with `-DGLUEYNEO_CPU_SANITIZER=ADDRESS_UNDEFINED`; TSan uses `build/cpu-tsan` with `-DGLUEYNEO_CPU_SANITIZER=THREAD`. Both options instrument the actual adapted runtime as well as tests. The compiler launch probes in research do not establish backend sanitizer results. Plan 01 task 1 creates the runnable infrastructure within the first tracer; there is no separate scaffolding-only execution wave. All commands above are proposed and are not yet runnable.

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
| 01-01-01 | 01 | 1 | CPU-01, CPU-03, CPU-05 | T-01-01–04 | Freeze precedes adaptation; bounded original arithmetic guest and consequential control | Integration | `ctest --test-dir build/cpu -R '^cpu_guest(_negative)?$' --output-on-failure --no-tests=error` | Missing — task 01-01-01 | Pending |
| 01-01-02 | 01 | 1 | CPU-01, CPU-05 | T-01-01, T-01-04 | Licensed complete closure; reproducible generation and inclusive caps | Source/control | `ctest --test-dir build/cpu -R '^cpu_(closure|budget|audit_controls)$' --output-on-failure --no-tests=error` | Missing — task 01-01-02 | Pending |
| 01-02-01 | 02 | 2 | CPU-02, CPU-04 | T-01-05–06 | Distinct/cold instances retain complete ownership | Concurrency | `ctest --test-dir build/cpu -R '^cpu_(isolation(_negative)?|cold)' --output-on-failure --no-tests=error` | Missing — task 01-02-01 | Pending |
| 01-02-02 | 02 | 2 | CPU-01, CPU-02 | T-01-07–08 | Every allocation failure and guest fault preserves healthy witness; actual instrumentation | Fault/inventory | `ctest --test-dir build/cpu -R '^cpu_(faults|inventory|budget)$' --output-on-failure --no-tests=error` | Missing — task 01-02-02 | Pending |
| 01-03-01 | 03 | 3 | CPU-03 | T-01-09–10 | Requests/reset/STOP/IRQ/exceptions remain bounded and source-qualified | Timing/boundary | `ctest --test-dir build/cpu -R '^cpu_(timing|faults|isolation|budget)$' --output-on-failure --no-tests=error` | Missing — task 01-03-01 | Pending |
| 01-03-02 | 03 | 3 | CPU-04 | T-01-11–12 | Fresh destination continues complete state; invalid restore is atomic | Continuation | `ctest --test-dir build/cpu -R '^cpu_(state(_negative)?|inventory|timing|isolation|budget)$' --output-on-failure --no-tests=error` | Missing — task 01-03-02 | Pending |
| 01-04-01 | 04 | 4 | CPU-01–05 | T-01-13–14 | Empty/stale/over-budget evidence cannot admit; source/runtime evidence separate | Qualification controls | `python3 tools/cpu/acceptance.py self-test` | Missing — task 01-04-01 | Pending |
| 01-04-02 | 04 | 4 | CPU-01–05 | T-01-13–16 | Current independent review and all mandatory evidence required; rejection is GAPS_FOUND | Admission | `python3 tools/cpu/acceptance.py verify --require-accepted` | Missing — task 01-04-01 | Pending |

## Wave 0 Requirements

- [ ] C17 target-based CMake, CTest and pinned Unity with explicit nonempty runners.
- [ ] Private CPU adapter, bounded bus, annotated original guest bytes, independent manual-derived expectations, and two distinguishable scenarios.
- [ ] Regeneration/source closure manifest, upstream patch counter, semantic change classification and cumulative attempt/time ledger.
- [ ] Cold-process concurrency runner, fail-each-allocation injection and healthy-instance witness, bounded trace observations.
- [ ] Private field-wise state codec and complete state inventory, excluding host pointers and jump buffers.
- [ ] Separate sanitizer configurations; unavailable or unsupported outcomes remain explicit.
- [ ] Current-revision acceptance receipt with exact source/configuration/input identities and a rejection path that leaves CPU-01 through CPU-04 pending.

## Manual-Only Verifications

No physical hardware, commercial media or account action is required for this local CPU experiment. Automated evidence covers only the selected behaviors and cannot establish hardware-wide fidelity. Independent source/rights review accompanies the automated checks.

## Validation Sign-Off

- [ ] All tasks have an automated verification or explicit Wave 0 dependency.
- [ ] No three consecutive tasks lack automated verification.
- [ ] Wave 0 covers all missing references.
- [ ] No watch-mode flags; all loops and test runs are bounded.
- [ ] Measured feedback latency is recorded against the proposed target.
- [ ] `nyquist_compliant: true` is set only after a validation audit establishes it.

**Approval:** Pending planning and execution evidence.
