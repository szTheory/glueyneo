---
phase: 02-executable-diagnostic-sdk
plan: "01"
subsystem: sdk
tags: [c17, native-api, diagnostic, cmake, ctest, unity]

requires:
  - phase: 01-cpu-acceptance-experiment
    provides: Bounded accepted owned MC68000 backend for the documented diagnostic subset
provides:
  - Opaque C instance API with copied ROM/RAM initialization and bounded guest execution
  - Original two-scenario arithmetic, initialized-data, and BSS diagnostic through the API and runner
  - Counted SDK CTest preset plus reproducible fixture/oracle provenance
affects: [Phase 02 lifecycle, timing, package consumers, hostile-input and evidence plans]

actuals:
  tokens: 13146
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - Strict C17 target settings and private warnings on SDK/runtime/test executables
    - Per-instance heap-owned image with transactional load and private CPU bus callbacks
    - Host-side shared word-array fixture; native runtime has no filesystem or clock access

key-files:
  created:
    - include/glueyneo/glueyneo.h
    - src/instance.c
    - tools/diagnostic/main.c
    - tests/sdk/test_sdk.c
    - tests/sdk/guest_fixture.c
    - tests/sdk/guest_fixture.h
    - tests/sdk/ORACLE.md
  modified:
    - CMakeLists.txt
    - CMakePresets.json

key-decisions:
  - "Expose a bounded boundary PC in run results so instruction-boundary outcomes can be checked without exposing the CPU register file."
  - "Use one host-side fixture module for both the public API tests and runner to keep scenario bytes identical."

patterns-established:
  - "Media load validates first, copies source bytes, resets a candidate image, then swaps it into the instance."
  - "The SDK diagnostic test emits stable case/assertion IDs and a nonzero structured result denominator."

requirements-completed: [API-01, API-02, API-03, DIAG-01, DIAG-02, BUILD-01, EVID-01, EVID-03]
coverage:
  - id: D1
    description: Opaque native instance API owns bounded media and returns finite execution results and named observations.
    requirement: API-01
    verification:
      - kind: integration
        ref: "ctest --preset sdk-debug -L sdk-diagnostic --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D2
    description: The original firmware-free guest runs through the API and headless runner with arithmetic, initialized-data, BSS, cycle, instruction, and PC expectations.
    requirement: DIAG-01
    verification:
      - kind: integration
        ref: "build/sdk-debug/glueyneo-diagnostic; scenario A and B"
        status: pass
      - kind: unit
        ref: "sdk_diagnostic: 4 cases, 119 counted assertions, including all 13 cumulative instruction boundaries"
        status: pass
    human_judgment: false
  - id: D3
    description: Schema-2 SDK debug preset selects counted contract tests and rejects empty CTest selections.
    requirement: BUILD-01
    verification:
      - kind: other
        ref: "ctest --preset sdk-debug -L sdk-contract --output-on-failure --no-tests=error; empty label selection rejected with exit 8"
        status: pass
    human_judgment: false
  - id: D4
    description: Scenario fixture bytes and ordered fixed-width outputs have manual-derived expectations, rights, dependency notices, and reproducible identities.
    requirement: EVID-01
    verification:
      - kind: integration
        ref: "ctest --preset sdk-debug -L 'sdk-provenance|sdk-diagnostic' --output-on-failure --no-tests=error"
        status: pass
      - kind: other
        ref: "tests/sdk/ORACLE.md; scenario A/B fixture and output SHA-256 identities"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-10-05
status: complete
---

# Phase 02 Plan 01: Executable diagnostic SDK Summary

**Opaque C instance API now runs the original two-scenario CPU/bus diagnostic through counted tests and a headless runner.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-10-06T00:00:28Z
- **Completed:** 2026-10-06T00:20:42Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added the C17 instance lifecycle, finite media/run limits, big-endian ROM/RAM bus, copied initialization seed, reset, unload, named observations, and transactional candidate loading around the accepted private CPU backend.
- Executed scenarios A and B through the ordinary API and real runner. Both reported 172 cycles, 12 instructions, STOP at PC `0x12e`; named results were A `(10, 0x1237, 1)` and B `(16, 0x2348, 1)`.
- Registered the `sdk-debug` schema-2 preset and counted CTest contract, diagnostic, and provenance checks. The Unity executable reported 4 cases and 119 assertions; the runner reported 14 checks per scenario.
- Added reproducible 522-byte ROM-plus-initialization fixture generation/checking and an oracle record with manual derivation, lawful provenance, exact fixture/output hashes, and the measured Darwin arm64 toolchain.

## Task Commits

Each task was committed atomically:

1. **Task 1: Execute the original guest through the API and runner** — `a3e1aa1` (`feat`)
2. **Task 2: Add counted focused SDK verification** — `1e5084a` (`test`)
3. **Task 3: Freeze the shared fixture and oracle** — `67368cd` (`feat`)

**Plan metadata:** this summary/state/roadmap closeout commit.

## Files Created/Modified

- `include/glueyneo/glueyneo.h` — Opaque public C API and bounded manifest/run/observation types.
- `src/instance.c` — Owned image storage, checked diagnostic bus, transactional load and native lifecycle.
- `tools/diagnostic/main.c` — Public-API runner and host-side fixture write/check commands.
- `tests/sdk/guest_fixture.c`, `tests/sdk/guest_fixture.h` — Shared original A/B guest recipe.
- `tests/sdk/test_sdk.c` — Counted lifecycle, outputs, failed-replacement/reset and cycle-boundary assertions.
- `tests/sdk/ORACLE.md` — Independent instruction/timing derivation, fixture rights and exact identities.
- `CMakeLists.txt`, `CMakePresets.json` — SDK/test targets, focused labels and schema-2 debug preset.

## Decisions Made

- `gn_run_result` includes the bounded instruction-boundary PC for exact terminal/boundary checks; it does not expose the CPU register file.
- A single host-side fixture source feeds both tests and the runner, preventing their byte recipes from drifting.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Integrated the shared recipe into the test executable and added API boundary assertions**
- **Found during:** Task 3 (Freeze the independently checked fixture and its lawful provenance)
- **Issue:** The task's three-file list omitted the test source, common fixture interface, and CMake source wiring required by its instruction to share one recipe and confirm every cumulative boundary through the ordinary API.
- **Fix:** Added `guest_fixture.h`, linked `guest_fixture.c` into both executables, and checked all 13 cumulative cycle/PC/instruction boundaries in the SDK test.
- **Files modified:** `CMakeLists.txt`, `tests/sdk/test_sdk.c`, `tests/sdk/guest_fixture.h`
- **Verification:** `sdk_diagnostic` passed with 4 cases and 119 counted assertions; provenance and diagnostic CTest labels passed.
- **Committed in:** `67368cd`

**2. [Rule 1 - Bug] Removed an unused runner helper caught by strict warnings**
- **Found during:** Task 1 (Execute the original extended guest through the ordinary API and runner)
- **Issue:** The first strict build rejected an unused big-endian reader in the runner.
- **Fix:** Removed the unused helper; result decoding remains inside the public API and observations.
- **Files modified:** `tools/diagnostic/main.c`
- **Verification:** Rebuilt and reran the tracer CTest and both runner scenarios successfully.
- **Committed in:** `a3e1aa1`

---

**Total deviations:** 2 auto-fixed (Rule 2: 1; Rule 1: 1).  
**Impact on plan:** The additions make the recipe genuinely shared and close the planned API-boundary evidence; no product scope or dependency was added.

## Issues Encountered

- The initial strict build caught the unused helper described above; after removal, the tracer passed.
- The first empty-CTest-selection probe used zsh's read-only `status` variable after CTest returned exit 8. Repeating the probe with `ctest_rc` confirmed the required nonzero rejection; no project code was affected.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 02-02 can add lifecycle misuse, media boundary, exhaustive allocation-failure, and ownership recovery evidence on top of this API. Timing controls, installed consumers, hostile-input lanes, aggregate evidence, and phase verification remain pending.

## Self-Check: PASSED

- All nine committed plan files exist.
- Task commits `a3e1aa1`, `1e5084a`, and `67368cd` are present.
- The frozen Phase 01 fixture and oracle files have no changes.
- CTest reported 3/3 selected tests passing; scenario A and B runner checks passed.

---
*Phase: 02-executable-diagnostic-sdk*
*Completed: 2026-10-05*
