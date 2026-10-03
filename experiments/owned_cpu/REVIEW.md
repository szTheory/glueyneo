# Independent review — Phase 01, Plan 01-12 Task 1

## Reviewed revision:

`1e451ac283cf625d2ddebc8a750f09524b41d58b` (captured before review). The initial worktree was clean. The principal owned-core source identity is SHA-256 `c4eaac805176cf6120dc8fd887e0096cfd34fe2047b9651087c9fe2e8e2e4f0d`; `cpu.h` is `3eac455ea9b07e48c5d3e792788bc2c6a2bd955632e2928d0cb1f4b4222dd457`. The continuation fixture under review is `tests/owned_cpu/test_state.c`, SHA-256 `a43fcb4eea57b8e1ffe438966764ac6c504194cae2eb9c49341925280ac274e4`.

Reviewed the owned compiled closure (10 translation units), `CMakeLists.txt`, owned CPU tests and controls, `ORACLE.md`, `CONTRACT.md`, `SUBSET.md`, state inventory, budget ledger, Phase 01 requirements/context/methodology, and the prior review. `inventory.py check --build-dir build/owned-cpu` reports 26 owned fields, 10 compiled sources, zero runtime mutable globals, and zero callback-owner mutation findings. CMake's owned archive target contains only `cpu.c`; the compile closure lists no CPU generator or imported emulator core. CMake applies required C17, disables extensions, and compiles the listed targets with `-Wall -Wextra -Werror`. This is evidence for this configuration on AppleClang 21.0.0 / arm64-apple-darwin25.6.0, not a portability claim.

Unity's pinned source and MIT license hashes match `third_party/unity/PROVENANCE.md` and pin `b6763fbd9cedfacaa89e2ad9fd00d615a234e355`. The Unity code is compiled as a test-only library, not into `libowned_cpu.a`. Provenance and hashes were checked; this review does not claim a complete line-by-line behavioral audit of the 4,876 lines of vendored Unity source.

## Reviewer independence:

This was a separate review agent with sole write ownership of this report. No implementation, test, build, planning, or evidence file was edited. The review was bound to committed HEAD, and prior findings were used only as prompts. No claim of personal/human reviewer identity independence is made.

## Prior findings:

The six prior blockers concern Musashi variable-shift range handling, signed remainder shifting in division, signed bit-31 shifts, and three Musashi generator defects (argument overflow, EOF sentinel, and array-capacity boundary). None is evidenced in the current owned closure: those instruction families are outside the declared subset and no generator is compiled or invoked. The prior two warnings concern historical budget assertions under optimization and a relative-path replay issue; neither is in the owned runtime closure. These dispositions do not reuse historical receipts as current evidence.

## Evidence runs and denominators:

- Native: `cmake --build build/owned-cpu --parallel 2 && ctest --test-dir build/owned-cpu --output-on-failure --no-tests=error` — 12/12 CTest cases passed. Unity denominators include diagnostic 2/2, semantics 17/17, timing 23/23, isolation 4/4, faults 5/5, and state 4/4. The native state binary SHA-256 is `1a02da76a413d8adf0650b73bc8a0bb129e2ef550281c2a27f7198564127e0d1`.
- ASan+UBSan: corresponding build and full CTest run — 11/12 CTest cases passed; `owned_cpu_state` failed, with Unity reporting 4 tests and 1 failure at `test_state.c:542`. `ctest --test-dir build/owned-cpu-asan -R '^owned_cpu_state$' --repeat until-fail:10 --output-on-failure` failed again on the first repetition at the same assertion. State binary SHA-256: `d2f874f85ccb0f7af45d46f7558a6d32183c308794752cdcc3437fea4f0c1ef5`.
- TSan / optimized: corresponding build and full CTest run — 12/12 passed. State binary SHA-256: `85a3b1c7f4e1b676f4803e30a605cb44aa915b5d335359dbdd03db9e0e6aed16`.
- The native negative diagnostic control reports that mutating expected D0 from 10 to 11 fails only the named guest arithmetic/store assertion; isolation and timing negative controls also passed. The CTest inventory check passed. These controls support test sensitivity but do not qualify hardware behavior.
- Build identities: native `CMakeCache.txt` SHA-256 `9122ef4cb48e4e903f3fc3f305dc0ee9b9d885c1999fd9d8970674330b1d8d3b`, compile database `9ec056bca4335738576e4d0e3285f81ac1025e7f62aabd4cd6ac775bdedea838`; ASan cache `66a2c79a355c79e5c9720d31928299192df4a4023d0792f5723a41c2ac811869`, compile database `3031937f4ddafdf3fc09cbe0806e784e5e9538f28b766faa6af9a09d81625a86`; TSan cache `48fcc61b78aad2d16a6124c4aa286fe7509100bb5d37fc0db91a47d250fb81ad`, compile database `21ebfda190320dd92e2db5a0ea6d76bb2232515f97cd1c86b8c7aa06b3f56719`.
- Budget snapshot from `python3 tools/owned_cpu/contract.py budget --require-diagnostic-gate`: pass; 16,396 active seconds, diagnostic gate 2,565 seconds, runtime churn 1,194, test/tool churn 4,472, five records; phase disposition remains `not-admitted`. This is the ledger state observed during review and does not include a separate post-review ledger update.

## Oracle ancestry:

`tests/owned_cpu/ORACLE.md` cites Motorola/NXP *MC68000 User's Manual*, Rev. 9.1 (2006-01-25), and the *M68000 Programmer's Reference Manual* (2000-07-01), with instruction, exception, timing, and interrupt claims tied to named tables/sections. The four-instruction diagnostic expected values are authorial, checked against the documented operations and timing. Ordered callback traces and partial bus-failure effects are the project's explicit functional-bus contract, not hardware captures. Address-error saved-PC choice is expressly implementation-defined because the manual calls it unpredictable. Emulator outputs (including Musashi/MAME comparisons) are comparisons, not hardware truth. There is no physical-silicon capture or independent board oracle in this evidence set; instruction coverage remains the exact narrow subset in `SUBSET.md`.

## Findings and dispositions:

### BL-01 — BLOCKER — Uninitialized state-test destination makes the sanitizer result unreliable

**File/line:** `tests/owned_cpu/test_state.c:518-525` (failure at 542; helper at 209-214; allocator counter at 120-125).

**Reproducer / evidence:** `malformed_and_incompatible_records_reject_atomically()` declares `state_machine destination` without initialization and calls `machine_create_fresh()`, which only constructs bus/allocator bindings and does not clear the fixture. `state_allocate()` increments the indeterminate `live_allocations`; the malformed-record helper also reads other fixture fields, including `event_count`. The ASan+UBSan state executable failed the final zero-allocation assertion (`Expected 0 Was 1`) and repeated with the same failure. This is a test-fixture defect; it prevents treating that state sanitizer path as green.

**Affected claim:** atomic rejection / sanitizer-clean continuation state validation. The current ASan+UBSan full-suite result is 11/12, not a passing gate.

**Narrow repair/test path:** initialize the entire destination fixture before binding it (or make the fresh helper initialize its fixture under a documented ownership rule); rerun the four state tests under ASan+UBSan, repeat the state test, and rerun its native and negative-control cases.

**Oracle ancestry:** test fixture and allocator bookkeeping only; no CPU-manual oracle. The failure is directly observed in the current sanitizer run.

### WR-01 — WARNING — Restore accepts an impossible diagnostic-counter state

**File/line:** `experiments/owned_cpu/cpu.c:889-900`; the existing mutation is `tests/owned_cpu/test_state.c:401-403`.

**Reproducer / evidence:** Starting from a post-instruction captured state, set only `instructions = 0` while retaining nonzero `instruction_cycles` and the existing total. `state_valid()` checks the aggregate cycle sum and reset-pending counters but does not relate the completed-instruction counter to event history/counters; `owned_cpu_restore_state()` accepts the candidate. The test itself performs this mutation as `OMIT_INSTRUCTION_COUNTER`. Per `SUBSET.md:119-125`, `instructions` counts completed dispatches while `instruction_cycles` records instruction clocks, so this produces a restored diagnostic state that cannot describe the preceding execution.

**Affected claim:** continuation record validation and truthful counter continuation. Architectural execution may continue, but post-restore counters can misreport prior completed work; current omission control normalizes this invalid state as acceptable.

**Narrow repair/test path:** define and enforce conservative counter consistency invariants for the supported event model; convert the omission control into a malformed-record rejection control or construct its test state through a controlled valid transition. Add a rejection-atomicity assertion for the counter mismatch and keep manual-derived cycle expectations separate from this local counter invariant.

**Oracle ancestry:** counter meanings are the local `SUBSET.md` policy and `ORACLE.md` event accounting; Motorola tables ground instruction cycles but do not define this private record format.

**Inconclusive observation:** `CONTRACT.md:20-27` describes restore into a fresh destination, while `cpu.c:916-928` rejects active/faulted destinations but permits a ready destination. Existing tests cover only newly created destinations, and the phrase's status as a mandatory precondition is ambiguous. No finding is raised without a test or stricter contract clarifying whether restore-over-ready is unsupported.

**Disposition:** BL-01 blocks admission because the required ASan+UBSan state run fails. WR-01 remains open. No other instruction-semantic defect was established in the reviewed narrow subset; unsupported opcodes, board-cycle behavior, hardware equivalence, public ABI, durable snapshots, cross-build state compatibility, and ASVS-style certification remain unsupported claims.
