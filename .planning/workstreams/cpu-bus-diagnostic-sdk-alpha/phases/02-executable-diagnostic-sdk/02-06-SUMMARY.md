---
phase: 02-executable-diagnostic-sdk
plan: "06"
subsystem: testing
tags: [SDK, CTest, evidence, provenance, baseline, sanitizers]
requires:
  - phase: 02-executable-diagnostic-sdk
    provides: [bounded public API and runner, focused CTest suites, installed consumer and documentation lanes]
provides:
  - Versioned fixture provenance, exact identity/outcome checks, and evidence rejection controls
  - Raw Release workload timing and owned allocation measurements with explicit uncertainty and unsupported RSS
  - Current-revision local aggregate covering all focused, consumer, documentation, capability, and sanitizer lanes
affects: [Phase 02 verification, SDK integrators, Phase 03 planning]
actuals:
  tokens: 49255
  tasks: 3
  commits: 3
plan_head_before: d9db43ce0fa3e93f9ff43788dc94bd631855dd1f
plan_head_after: 814d7c4fa7e40841a3ae463705f354e5ee222b9a
tech-stack:
  added: []
  patterns: [canonical source-bound JSON evidence, batched monotonic timing, exact named lane inventories, serialized TSan runtime tests]
key-files:
  created:
    - tools/sdk_evidence.py
    - tools/sdk_baseline.py
    - tools/verify_sdk.py
    - tests/sdk/test_evidence.py
    - fixtures/diagnostic/manifest.json
    - docs/evidence-schema.md
    - evidence/sdk/verification.json
  modified:
    - tools/sdk_evidence.py
    - tools/sdk_baseline.py
    - tools/verify_sdk.py
    - tests/sdk/test_evidence.py
    - tests/sdk/controls.py
    - fixtures/diagnostic/manifest.json
    - docs/evidence-schema.md
    - README.md
    - evidence/sdk/verification.json
key-decisions:
  - "Bind measured results and sanitizer lanes to exact current source, build, fixture, compiler, and configuration identities; retain failed attempts."
  - "Keep timing observations descriptive and record RSS as unmeasured instead of inferring it from owned allocator counts."
  - "Run only the process-heavy TSan CTest lane serially after same-input serial execution confirmed parallel host contention."
requirements-completed: [EVID-01, EVID-03, EVID-04, DOC-01, DOC-02]
coverage:
  - id: D1
    description: "Auditable diagnostic fixture and dependency provenance with named evidence rejection controls."
    requirement: EVID-01
    verification:
      - kind: integration
        ref: "python3 tools/verify_sdk.py --suite provenance (4 cases, 4 assertions; 2 fixture checks)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Exact source/configuration-bound machine-readable outcomes distinguish pass, fail, skipped, unsupported, and unknown."
    requirement: EVID-03
    verification:
      - kind: integration
        ref: "python3 tools/verify_sdk.py --suite evidence (18 cases, 36 assertions)"
        status: pass
      - kind: integration
        ref: "python3 tools/verify_sdk.py (source revision 814d7c4fa7e40841a3ae463705f354e5ee222b9a)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Retained Release load, execution, allocation, and cold-build observations report raw samples and uncertainty."
    requirement: EVID-04
    verification:
      - kind: integration
        ref: "python3 tools/verify_sdk.py (baseline: 31 paired samples, 3 cold builds, 7 controls)"
        status: pass
    human_judgment: false
  - id: D4
    description: "README getting-started and malformed-media recovery commands match compiled installed C/C++ consumer examples."
    requirement: DOC-01
    verification:
      - kind: integration
        ref: "python3 tools/verify_sdk.py (package docs: 3 CTest cases; consumers: 2 CTest cases)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The capability contract states the bounded CPU/bus subset and retains unverified hardware and platform dimensions as unknown."
    requirement: DOC-02
    verification:
      - kind: integration
        ref: "python3 tools/verify_sdk.py (focused and package capability lanes)"
        status: pass
    human_judgment: false
duration: 429min
completed: 2026-10-06
status: complete
---

# Phase 02 Plan 06: Evidence, Baselines, and Aggregate Summary

**A source-bound local SDK gate now retains fixture provenance, reproducible workload costs, compiled package/doc checks, explicit limitations, and sanitizer history.**

## Performance

- **Duration:** 7h 9m, measured from the first task commit to closeout
- **Started:** 2026-10-05T22:56:55-04:00
- **Completed:** 2026-10-06T06:05:56-04:00
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added a versioned lawful fixture manifest and fail-closed identity, outcome, privacy, provenance, and baseline controls. Focused evidence/provenance checks passed with 18/36 and 4/4 cases/assertions respectively.
- Measured a fixed Release diagnostic workload with 31 retained load/execution samples, three separate cold builds, and private allocator counts. The final receipt records medians of 406 ns/load, 218 ns/run, and 1.075 s/cold build; peak owned allocation was 6 allocations / 7,010 bytes. Host RSS remains unmeasured, and timing values are observations rather than budgets.
- Completed the current-revision aggregate at source revision `814d7c4fa7e40841a3ae463705f354e5ee222b9a`, relevant-source digest `0ebff95705f38b39750ae29ef6e1098a829240f186d4e31229d4c2de74a63aad`, and clean relevant-source tree. It passed 63 lane executions and 1,154,951 assertions, including ASan+UBSan 8/8 and TSan 2/2.
- Kept unsupported and unknown dimensions explicit: matching libFuzzer is unsupported; Release process RSS is unmeasured; CMake 3.20, other platform/compiler combinations, and original-silicon saved-PC behavior remain unknown.

## Task Commits

1. **Task 1: Reject incomplete, mismatched or contaminated SDK evidence** - `bcbba29` (`feat`)
2. **Task 2: Measure reproducible diagnostic, allocation, load and build baselines** - `395898e` (`feat`)
3. **Task 3: Close the current-revision aggregate and reconcile integrator claims** - `814d7c4` (`feat`)

**Plan metadata:** this closeout commit contains the summary, refreshed receipt, and GSD tracking updates.

## Files Created/Modified

- `tools/sdk_evidence.py` - Canonical identities, manifest validation, privacy scan, and baseline record checks.
- `tools/sdk_baseline.py` - Batched load/run timing, owned allocation counts, and cold-build sampling.
- `tools/verify_sdk.py` - Named required-lane catalog, exact outcome checks, package/docs verification, sanitizer aggregation, and current-source receipt generation.
- `tests/sdk/test_evidence.py` - Named negative controls for evidence, provenance, and baseline rejection paths.
- `fixtures/diagnostic/manifest.json` - Fixture source, rights, recipe, output identity, and oracle ancestry.
- `docs/evidence-schema.md` - Public evidence fields and fixed measurement protocol.
- `evidence/sdk/verification.json` - Canonical source-bound aggregate, baseline observations, limitations, and retained TSan failure history.
- `README.md` - Local gate invocation and compiled recovery behavior.
- `tests/sdk/controls.py` - TSan-only CTest serialization, leaving other sanitizer/test parallelism unchanged.

## Decisions Made

- Evidence records bind to current source, artifacts, dependencies, fixture, compiler, configuration, and workload inputs; prior failed outcomes are retained.
- Host time, guest cycles, owned allocator bytes, and process RSS remain separate measurements. Unmeasured RSS is not inferred from allocator counts.
- The aggregate makes local SDK acceptance claims only. Unsupported tools and untested hardware/platform dimensions remain explicit.
- TSan's process-heavy CTest cases run one at a time after the identical test inputs passed in a scoped serial run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Serialized the TSan runtime test lane after parallel contention stalled both cases**
- **Found during:** Task 3 (current-revision aggregate)
- **Issue:** With CTest parallelism 2, `sdk_isolation` and `sdk_cold` both timed out against their configured 180-second per-test limit; CTest reported 470.66 seconds wall time. A scoped rerun of the same tests with `--parallel 1` passed 2/2 in 3.01 seconds.
- **Fix:** Added `--parallel 1` only to the TSan runtime command, exposed its parallelism in the lane record, and retained the old timeout plus serial diagnostic in `failure_history`.
- **Files modified:** `tests/sdk/controls.py`, `tools/verify_sdk.py`, `README.md`, `docs/evidence-schema.md`, `evidence/sdk/verification.json`
- **Verification:** `python3 tests/sdk/controls.py --sanitizers` passed ASan+UBSan 8/8 and TSan 2/2; the final post-commit `python3 tools/verify_sdk.py` passed with TSan CTest wall time 5.69 seconds (1.66 and 4.02 seconds per test).
- **Committed in:** `814d7c4` (part of Task 3 commit)

**Total deviations:** 1 auto-fixed (Rule 3 - Blocking)
**Impact on plan:** The targeted harness repair removes TSan-only host contention; the original failed aggregate remains visible in the final receipt.

## Issues Encountered

- Five early baseline collection attempts stopped before retaining SDK timing samples due to empty-cache handling, a duplicate macro, or single-operation timer quantization. The measurement helper was corrected to batch 32 independent loads/runs; all five collector failures remain in baseline history, and no sample was discarded from the final arrays.
- The first aggregate parser comparison used a full Git hash where the C test emits a 12-character revision prefix, and one controls producer emits `PASS:` text rather than JSON. The verifier now validates each producer's actual named output format and requires positive denominators.
- Initial baseline RSS support was unavailable. The report records this as unmeasured/unsupported rather than filling it with allocator measurements.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 02-06 execution is complete. Phase 02 itself is **not yet verified**; the separate phase-level review/verifier remains for the parent workflow. The local aggregate is ready for that review. Phase 03 was not started.

---
*Phase: 02-executable-diagnostic-sdk*
*Completed: 2026-10-06*

## Self-Check: PASSED

- All seven created deliverable files and this summary exist.
- Task commits `bcbba29`, `395898e`, and `814d7c4` are ancestors of HEAD.
