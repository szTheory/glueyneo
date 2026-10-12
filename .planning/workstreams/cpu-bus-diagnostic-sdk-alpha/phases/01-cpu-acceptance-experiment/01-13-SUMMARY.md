---
phase: 01-cpu-acceptance-experiment
plan: "13"
subsystem: owned-cpu-evidence
tags: [c17, cmake-presets, provenance, sanitizers, exact-revision]
requires:
  - phase: 01-cpu-acceptance-experiment Plan 12
    provides: reviewed and repaired private state paths
provides:
  - Current source and rights inventory with immutable Unity pin checks
  - Schema-2 owned configure/build/test presets at the unchanged CMake 3.20 floor
  - Append-only exact-source qualification receipts from four exercised native lanes
affects: [owned-cpu-admission, final-independent-review]
tech-stack:
  added: []
  patterns: [explicit optimized-Python validation, append-only collection receipts, exact nonzero denominators]
key-files:
  created: [CMakePresets.json, tools/owned_cpu/acceptance.py, tests/owned_cpu/test_acceptance.py, experiments/owned_cpu/PROVENANCE.md, experiments/owned_cpu/source-manifest.json, experiments/owned_cpu/acceptance-results.json]
  modified: [tools/owned_cpu/inventory.py, tests/owned_cpu/test_inventory.py, experiments/owned_cpu/budget-ledger.json]
key-decisions:
  - Current distribution manifest owns current source hashes while the earlier state inventory remains preserved audit evidence.
  - Collect exact native evidence without admitting the backend; independent final review and bounded decision remain Plan 14 work.
  - CMake 3.20 execution remains unknown; schema 2 and the provisional floor remain unchanged.
requirements-completed: []
actuals:
  tokens: 43493
  tasks: 3
  commits: 3
  active_seconds: 1357
plan_head_before: 479964a268c06cb9ed74210047eedc7ff9150c6a
duration: 23min
completed: 2026-10-03
status: complete
---

# Phase 01 Plan 13: Owned source inventory and qualification evidence Summary

**Four preset-driven native qualification lanes pass at one committed source revision, with complete rights/source closure and append-only receipts; admission remains pending.**

## Accomplishments and Evidence

- Inventory self-test and optimized self-test pass; 10/10 inventory unit cases pass. Manifest controls reject missing, duplicate, stale and forbidden records. The mechanical inventory checks 26 owned fields, ten distinct compiled sources, strict C17, actual runtime archive membership and sanitizer compilation/link flags. Unity source and retained notice match immutable pin `b6763fbd9cedfacaa89e2ad9fd00d615a234e355`. The runtime archive contains only the owned CPU object. Source scanning remains bounded and complements independent review.
- Collector self-tests pass normally and under `python3 -O`: six rejection controls and two classification controls. 12/12 collector unit cases pass, covering corruption, empty/duplicate counts, stale source, false success, exact optional support classification, preset scope/worker/floor changes, review identity/headings/blockers, and effort/churn pauses.
- `cmake --list-presets` lists `owned-debug`, `owned-release`, `owned-asan-ubsan`, and `owned-tsan`. Required configure/build/CTest commands pass in Debug, Release/O2 and ASan+UBSan. Builds and tests use at most two workers. Existing manual-derived MOVEQ sign extension, ADDQ overflow/carry, word/long width, high-bit stores and address-wrap boundary cases execute under UBSan; no exhaustive sweeps or expanded runtime instructions were added.
- Fresh collection at `dfd281091626b05c40c4e90789442e7c19fd97c2` passed 12/12 CTest cases in each of Debug, Release/O2, ASan+UBSan and optional TSan (48/48 total). Each lane reports Unity diagnostic 2, semantics 17, timing 23, isolation 4, faults 5 and state 5; 13 continuation checkpoints, 32 interleaved pairs, 32 concurrent pairs, 16 cold processes and five named negative controls. No behavioral failure or unsupported TSan result occurred in this collection.
- Exact command/exit/output, source/fixture/oracle, compiler/SDK/configuration, build cache/compile database/archive/executable and sanitized test-log identities live in `acceptance-results.json`. No personal source paths, private media or machine names were found in tracked receipts. Collection digest: `a96c08b486ee48e960b98b058bb763d3c6b5067dd33b85c00e193897d9536fc9`. Read-only `acceptance.py verify` passes with disposition `unqualified`, `GAPS_FOUND`, and the explicit Plan 14 review/decision blocker.

## Exact Identities and Limits

- Source manifest SHA-256: `013d53c42c0070fcc791724d2e304728c202b6e370e058476df66510ffde487c` (36 distribution records; collector snapshot also binds the manifest itself).
- Owned `cpu.c` SHA-256: `8ac6ded7859184651f6eb3fff8a87c073f8e24a98d66175b64c3d86f69cbd15f`; original fixture recipe: `3a85140f2c50f0958d15b4d028108539a84486016c6931f8304b533f8889a83d`.
- Executed host: Darwin 25.6.0, arm64; AppleClang 21.0.0.21000101; SDK 26.5; Python 3.14.4; CMake 4.4.3; Ninja 1.13.2. CMake schema fields were checked against the official [3.20 preset manual](https://cmake.org/cmake/help/v3.20/manual/cmake-presets.7.html). An executable at the exact CMake 3.20 floor was unavailable and remains **unknown**; no other compiler/platform is qualified.
- Diagnostic-only single-process elapsed samples, including startup: Debug 0.002728 s, Release 0.002632 s, ASan+UBSan 0.066833 s, TSan 0.338978 s. Child user/system CPU deltas are recorded. Peak resident memory is unknown. These startup-dominated single samples establish no gameplay throughput or performance baseline.
- Manual-grounded original fixture expectations remain the oracle; Musashi/MAME/SingleStepTests/Rocket68 ancestry is explicit and emulator agreement is not hardware truth. No silicon capture, full MC68000, board timing, BIOS/game, public ABI, durable-save or cross-build state claim is established.

## Task Commits

1. Task 1 — `078a481`: source inventory and rights closure.
2. Task 2 — `dfd2810`: shared presets and tested local evidence collector.
3. Task 3 — `89fa40e`: fresh four-lane qualification receipts and cumulative accounting.

`actuals.tokens` measures task diff characters divided by four, rounded up; `actuals.commits` is measured from the persisted per-plan Git ledger before the metadata commit. The receipts include full sanitized logs, which dominate diff size; these are source-diff estimates, not harness token counts.

## Accounting

The Plan 13 qualification tranche charges 1,183 seconds conservatively from 01:01:00Z through the actual record time 01:20:43Z. The start is an inferred conservative allowance approved by the orchestrator; the earliest explicitly captured local clock was 01:08:49Z. A final metadata tranche is recorded separately. Earlier ledger entries and every frozen historical Musashi hash are unchanged.

At the qualification record: 31,551 cumulative active seconds, 2,565 diagnostic-gate seconds, 1,206 runtime churn and 5,146 test/tool churn; budget passes with no pause. The metadata tranche adds 174 seconds through 01:23:37Z, giving 1,357 charged Plan 13 seconds and 31,725 cumulative seconds (8h 48m 45s). Final budget validation passes: runtime churn 1,206, test/tool churn 5,146, diagnostic gate 2,565 seconds, eight preserved/appended records, no pause. The frozen 32-hour, 6,000-runtime and 8,000-test/tool caps remain unchanged, with no refunds. A threshold causes scope review and GAPS_FOUND, never automatic rejection.

## Deviations from Plan

The manifest was refreshed in Task 2 because the collector, presets and unit tests are part of its declared distribution closure. Task 2 also completed immutable Unity pin and actual archive-member checks in the declared `inventory.py` path. The earlier state inventory file was preserved; current source hashes are owned by the new manifest. These changes remain inside Plan 13's declared files and are necessary for current-source closure, without a runtime/dependency/scope change.

No tests or required verify commands were skipped. CMake 3.20 execution and peak-memory measurement are explicitly unknown observations, not passing lanes. All generated caches, binaries and raw logs remain ignored build products. No known stubs or new runtime trust surface were introduced.

## Remaining Work

Plan 14 must independently review the post-repair source and collector, using the required review headings and explicit non-author identity, then seal a truthful bounded decision. `review-check` requires the six existing report topic headings, a matching full revision, `Independent reviewer:`, `Authored runtime/collector/tests: no`, and `Disposition: clean` or `Disposition: GAPS_FOUND`; a blocking disposition fails the check.

CPU-01–05 remain Pending. Phase 01 remains open / GAPS_FOUND and Phase 02 remains gated. This plan did not run phase verification, seal admission, publish artifacts, or start another workflow step.

## Self-Check: PASSED

All six newly created deliverables exist, the three task commits exist, source inventory and read-only receipt verification pass, all required commands ran, and earlier ledger entries remain preserved.
