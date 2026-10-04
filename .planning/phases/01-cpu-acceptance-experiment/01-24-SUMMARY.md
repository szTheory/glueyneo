---
phase: 01-cpu-acceptance-experiment
plan: "24"
subsystem: acceptance-evidence
tags: [continuation, source-manifest, native-lanes, budget-ledger]
requires:
  - phase: "01-23"
    provides: Monotonic frozen budget accounting and inclusive limit checks
provides:
  - Current continuation profile documentation for guest-reachable odd PC/stack values
  - Refreshed distribution manifest for current sources, tests, and docs
  - Four-lane native receipt and preserved historical seal/collection evidence
affects: [01-25, phase-verification]
actuals:
  tokens: 39205
  tasks: 2
  commits: 3
tech-stack:
  added: []
  patterns: [append-only-qualification, exact-source-lane-identity]
key-files:
  created:
    - .planning/phases/01-cpu-acceptance-experiment/01-24-SUMMARY.md
  modified:
    - experiments/owned_cpu/ACCEPTANCE.md
    - experiments/owned_cpu/SUBSET.md
    - tests/owned_cpu/ORACLE.md
    - experiments/owned_cpu/source-manifest.json
    - experiments/owned_cpu/acceptance-results.json
    - experiments/owned_cpu/budget-ledger.json
key-decisions:
  - "Keep owned-p01-c14-continuation-2 at 15 checkpoints/90 calls and preserve owned-p01-c14-1 at its historical 13/78 denominator."
  - "Document the actual SR_switch_odd_USP next event as vector-8 privilege entry on the even SSP; do not call it an odd-stack bus fault or infer silicon restart behavior."
  - "Retain the prior active seal as an exact superseded object; the new lane receipt remains unqualified pending Plan 01-25 independent review/security and separate phase verification."
patterns-established:
  - "Versioned evidence profiles keep historical denominators intact while adding a new current continuation contract."
  - "Archive a complete derived seal before collection removes its active designation."
requirements-completed: []
coverage:
  - id: D1
    description: The current manifest and source docs identify repaired continuation behavior, retained private-state limits, and actual licensed closure.
    verification:
      - kind: integration
        ref: "cmake --preset owned-debug; cmake --build --preset owned-debug --parallel 2"
        status: pass
      - kind: integration
        ref: "inventory.py check; contract.py validate; manifest matches cpu.c, cpu.h, and state-inventory identities"
        status: pass
    human_judgment: false
  - id: D2
    description: Four native lanes and normal/optimized evidence checks append at exact source identity without erasing historical evidence or granting admission.
    verification:
      - kind: integration
        ref: "acceptance-results.json collection cb77285d…5738; 4/4 lanes and 13/13 CTests per lane"
        status: pass
      - kind: unit
        ref: "tests/owned_cpu Python suite: 59 tests normal and 59 under -O"
        status: pass
      - kind: integration
        ref: "acceptance.py verify; contract.py budget"
        status: pass
    human_judgment: false
duration: 196min
completed: 2026-10-04
status: complete
---

# Phase 01 Plan 24: Repaired source and native qualification summary

**The current continuation source manifest is refreshed and all four owned native lanes pass at the new 15/90 profile. Historical evidence is preserved, while the candidate remains unqualified pending independent reassessment.**

## Performance

- **Duration:** 196 minutes
- **Started:** 2026-10-04T02:52:24Z
- **Completed:** 2026-10-04T06:08:15Z
- **Tasks:** 2
- **Files modified:** 7, including this summary.

## Task Commits

1. **Task 1: Refresh repaired source evidence and manifest** — `bd390a7`.
2. **Task 2: Append four-lane qualification and accounting** — `1e4abfd`.
3. **Plan metadata:** this summary is committed after closeout accounting.

## Accomplishments

- Updated `ACCEPTANCE.md`, `SUBSET.md`, and the owned CPU timing oracle for `owned-p01-c14-continuation-2`: 15 named ready boundaries and 90 continuation calls. The historical `owned-p01-c14-1` profile remains 13/78, and older unnamed receipts retain their original interpretation.
- Documented the exact local behavior after `RTE_odd_PC`: odd fetch enters the vector-3 address-error frame, with seven ordered frame writes, vector reads at `$000c/$000e`, 50 cycles, zero completed instructions, and the fixture's saved PC `$101`. The documentation expressly keeps original-silicon saved PC unknown.
- Documented `SR_switch_odd_USP` from the test's actual outcome: user SR zero, odd USP/A7 `$2801`, even SSP `$3000`, and PC `$104` continue into a vector-8 privilege exception on the supervisor stack. Its short frame records SR zero and PC `$104`; it takes 34 cycles and preserves the odd USP. This fixture does not observe an odd-USP address error or host fault.
- Kept the private fixed named-field record, same-build source identity, separately cloned guest memory, destination-owned bindings, and atomic malformed-record guards. No runtime code, ABI, record layout/version, or hardware claim changed.
- Refreshed source-manifest identities after the docs settled. The current `cpu.c`, `cpu.h`, and `state-inventory.json` identities are respectively `f11a282d…bee7`, `f25bc481…02a1`, and `42ab974a…52b4`. Unity remains a pinned copied test-only dependency; the runtime archive compiles only authored `cpu.c`, with no imported CPU/FPU/SoftFloat/generator code.
- Recorded the CR-02/WR-01 repairs: four cumulative churn fields are monotonic, exact frozen caps pass inclusively, crossings and invalid/active-pause records remain blocked, and reverted effort is never refunded. Caps remain 115,200 active seconds, 28,800 diagnostic seconds, 6,000 runtime lines, and 8,000 test/tool lines.
- Archived the entire previous active seal before collection. The collector removed only the active seal designation and appended one new collection; no previous collection, seal-history entry, or ledger entry was rewritten.

## Qualification receipt

- **Collected revision:** `bd390a7f5f6ede0a69df42f8df1fc98905d171ea`
- **Profile:** `owned-p01-c14-continuation-2`
- **Collection SHA-256:** `cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738`
- **Source-map SHA-256:** `be6e2c45f9590425a227bb9d6622d7629d080cca778eba29d5304bef3bd13a6d`
- **Current host:** Darwin 25.6.0 arm64, AppleClang 21.0.0, CMake 4.4.3, Ninja 1.13.2, Python 3.14.4.
- **Lane result:** Debug, Release, ASan+UBSan, and TSan all passed. Each lane recorded 13/13 CTests, all 15 boundary names/90 calls, five state Unity runners, timing25, semantics17, six consequential controls, interleaved32, concurrent32, and cold-process16. Each receipt binds 11 build artifacts.
- **Actual compiler/link flags:** Debug uses `-std=c17 -O0`; Release uses CMake `-O3` followed by the experiment's `-O2`; ASan+UBSan compile and link use `-fsanitize=address,undefined -fno-sanitize-recover=all`; TSan compile and link use `-fsanitize=thread -fno-sanitize-recover=all`. No lane was unsupported or skipped.
- **Python controls:** 59/59 tests pass normally and 59/59 pass under `python3 -O`.
- `acceptance.py verify` passes with six collections, disposition `unqualified`, and no current lane blockers. `contract.py budget` passes with no active pause. The receipt is not a seal or phase admission.

## Historical and frozen-evidence checks

- The five-collection prefix matches exactly against pre-Plan-22 commit `ea7c61f`; all prior collection objects remain unchanged.
- The former active seal equals the archived object at `superseded_seals[1]` byte-for-byte at the JSON-object level. The existing superseded-seal prefix remains unchanged; no active seal remains after collection.
- The 34-entry pre-Plan-22 budget ledger prefix and every non-entry ledger field match exactly. This plan adds one accounting entry per task and two closeout entries. Current totals: **59,690 active seconds**, **2,565 diagnostic seconds**, **1,228 runtime churn lines**, **6,540 test/tool churn lines**, 42 ledger records; caps remain unchanged and no pause is active.
- The frozen CONTRACT (`6ec5b901…2f73`), reconciliation amendment (`b6118fe7…8298`), all ten frozen Musashi input hashes, and the four Plan 01-17 plan/summary/adjudication/evidence files match the pre-Plan-22 baseline.
- Contract validation continues to report CPU-01–05 Pending, the original-silicon saved PC unknown, and Phase 02 gated.

## Checks performed

- `cmake --preset owned-debug && cmake --build --preset owned-debug --parallel 2 && python3 tools/owned_cpu/inventory.py check --build-dir build/owned-debug && python3 tools/owned_cpu/contract.py validate` — passed.
- Fresh `owned_cpu_inventory` CTest — 1/1 passed for Task 1 accounting.
- Four-preset `acceptance.py collect` — all four lanes passed.
- Normal and optimized `unittest discover` — 59/59 each.
- `python3 tools/owned_cpu/acceptance.py verify` — passed, unqualified with no lane blockers.
- `python3 tools/owned_cpu/contract.py budget` — passed, no pause.
- Historical collection/ledger/seal and frozen-file comparisons described above — passed.

## Deviation from plan wording

The Plan 01-24 action grouped `SR_switch_odd_USP` with a following address-error/host-fault event. The implemented fixture's next instruction is a privileged MOVE-to-SR, which takes vector 8 using the even SSP; no odd-USP memory access occurs on this path. Documentation records the actual asserted behavior and trace comparison. Runtime and tests were not changed, and no silicon conclusion is drawn. Plan 01-25 remains responsible for independent disposition of current evidence.

## Next step

Plan 01-24 is complete. Plan 01-25 remains within the authorized gap-only phase execution and will independently reassess CR-01/CR-02/WR-01/WR-02, update UAT from real outcomes, and produce a deferred exact-source closeout only if all gates pass. CPU-01–05 remain Pending. Do not start separate `$gsd-verify-work 01` until the execute-phase step is complete and the user continues.

## Self-Check: PASSED

The new receipt matches the committed source/profile, all four lane and Python denominators are nonzero and passing, historical prefixes and frozen files compare exactly, and the resource gate remains within its original caps. Admission and phase completion remain pending.

---
*Phase: 01-cpu-acceptance-experiment*
*Completed: 2026-10-04*
