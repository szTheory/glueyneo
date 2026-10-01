---
phase: "01"
slug: "cpu-acceptance-experiment"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-01"
---

# Phase 01 — Validation Strategy

This is a proposed execution contract derived from [phase research](01-RESEARCH.md), not a record of passing CPU tests. The planner must reconcile task identifiers, file paths, threat references and sanitizer options with the executable plans.

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

ASan/UBSan and TSan require separate build directories and explicit planner-defined options. The compiler launch probes in research do not establish backend sanitizer results. All commands above depend on Wave 0 infrastructure and are not yet runnable.

## Sampling Rate

- After every task: run its affected tests and the quick suite once available.
- After every plan wave: run the full suite and applicable sanitizer configurations.
- Before phase acceptance: run the full suite on the current revision, capture exact input/toolchain/source identities, reconcile the budget ledger, and obtain independent review.
- Use finite iterations and CTest timeouts. Measure feedback latency before claiming a time budget is met.
- Every executable test must assert behavior and reject zero tests. A supervised negative control must fail its intended assertion; a crash does not count.

## Per-Task Verification Map

These provisional rows describe required coverage. Planning replaces their identifiers with actual plan tasks without dropping a requirement.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | CPU-01 | Pending plan model | Only inventoried licensed source enters the runtime closure | Source closure | `ctest --test-dir build/cpu -R cpu_closure --output-on-failure --no-tests=error` | Missing — Wave 0 | Pending |
| 01-01-02 | 01 | 1 | CPU-03 | Pending plan model | Bounded original guest reaches the expected observable marker | Integration | `ctest --test-dir build/cpu -R cpu_guest --output-on-failure --no-tests=error` | Missing — Wave 0 | Pending |
| 01-02-01 | 02 | 2 | CPU-02 | Pending plan model | Distinguishable instances and concurrent cold initialization cannot affect one another | Concurrency | `ctest --test-dir build/cpu -R 'cpu_isolation|cpu_cold' --output-on-failure --no-tests=error` | Missing — Wave 0 | Pending |
| 01-03-01 | 03 | 3 | CPU-03 | Pending plan model | Invalid inputs, reset, STOP, interrupts and exceptions remain bounded and host-safe | Timing/boundary | `ctest --test-dir build/cpu -R cpu_timing --output-on-failure --no-tests=error` | Missing — Wave 0 | Pending |
| 01-03-02 | 03 | 3 | CPU-04 | Pending plan model | Restore binds destination ownership and continues complete guest-visible state | Continuation | `ctest --test-dir build/cpu -R cpu_state --output-on-failure --no-tests=error` | Missing — Wave 0 | Pending |
| 01-04-01 | 04 | 4 | CPU-05 | Pending plan model | Acceptance requires current evidence within the recorded adaptation budget | Qualification | `ctest --test-dir build/cpu -R cpu_acceptance --output-on-failure --no-tests=error` | Missing — Wave 0 | Pending |

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
