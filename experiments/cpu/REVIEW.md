# Independent CPU source review

## Identity and disposition

- Reviewer: `codex:cpu_acceptance_review_01` (independent of the implementation role)
- Evaluated source revision: `94f468326e5e529fd7c54f28434816c27f80f379`
- Content digest: `81aa0d99145d7b214a7336ae02f9a825eff328c8c26011fd2eef35fbe977b527`
- Evidence digest: `6dafb025bf1b3ba2a52750cae3e9f50a1db3a552ebb8507edebb8fa2ec493c66`
- Disposition: **No open findings.** The reviewed candidate is suitable for the plan's private, instruction-boundary 68000 experiment. The low-severity documentation count discrepancy identified during review was corrected and independently confirmed. This source review does not itself seal the acceptance report or complete Phase 1.

The current receipt has 56 passing records, but its decision remains `ready-for-review`, `phase_status` is `GAPS_FOUND`, and `review` is null (`experiments/cpu/acceptance-results.json:107-1289`). I independently recomputed both digests and verified all 56 retained output digests. All 65 input hashes match both the collector's source revision and the originally reviewed revision `6be55c2fd1ea402fe36f55774ed5226e968908b3`; the inspected source inputs are byte-identical across those revisions.

## Scope and methods

I read the Task 2 instructions and D-12 context, the four Phase 01 plan threat models, frozen admission contract, budget ledger, state inventory, source manifest, fixture manifest, oracle, adapter and Musashi source, adaptation and audit tools, acceptance reducer, and guest, isolation, cold-start, fault, timing, state, and negative-control tests. I inspected source and ownership paths directly rather than relying on the receipt summary.

I checked the receipt's case denominator, status counts, identities, output digests, supported configurations, unsupported entries, budget totals, and review state. I verified the report's content digest from its 65 input hashes, its canonical evidence digest, and each input hash against both the evaluated Git tree and current checkout. I scanned the tracked CPU evidence and source text for absolute user paths, private email addresses, and secret-like assignments; the only email match is an upstream author contact retained in Musashi's generator source. No private machine identity, commercial ROM, BIOS, or binary guest fixture was found.

This is a source and receipt audit. I did not recollect evidence, execute tests, build binaries, run sanitizers, or claim a new race/safety-instrumentation result. Runtime outcomes below are the submitted, identity-matched evidence that I inspected, not independent runtime reruns.

## Findings

### REV-LOW-01 — State inventory count in the acceptance narrative is stale — resolved

- Severity: `low`
- Status: `resolved`
- Evidence: The initial review found `experiments/cpu/ACCEPTANCE.md:270-273` saying 98 compiled objects/fields. `experiments/cpu/state-inventory.json:14-1317` contains 99 object entries, including `cpu_instance.active` at lines 1307-1316. `tools/cpu/state_inventory.py:53-56,83` requires exact compiled-declaration coverage and reports the number of inventory rows. The acceptance narrative now says 99.
- Impact: The machine-readable inventory and its declaration-coverage check include the active flag; the former prose count understated the reviewed inventory by one and did not identify a missing state field.
- Resolution: The acceptance narrative now says 99, matching the 99 object entries in `state-inventory.json` (`experiments/cpu/ACCEPTANCE.md:270-273`; `experiments/cpu/state-inventory.json:14-1317`). I independently confirmed the corrected count against the inventory.

No high- or critical-severity source finding remains open.

## Source and evidence review

### Rights, fixture ancestry, and oracle

`tools/cpu/source-manifest.json` enumerates 43 distributed inputs and generated outputs, pins Musashi to `313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd`, pins Unity, retains the upstream license notices, and records each file's role and host-call disposition. `third_party/musashi/PROVENANCE.md:7-28,30-50` and `third_party/unity/PROVENANCE.md:3-14` document source acquisition, notices, and scope. The fixture manifest identifies original MIT guest and test-local byte arrays, states that firmware is not required, and says there is no separately distributed binary fixture (`tests/cpu/fixture-manifest.json:3-21`).

The oracle derives the MOVEQ, ADDQ.L, absolute-long store, STOP, exception-frame, and selected timing expectations from the listed Motorola manuals, not emulator agreement (`tests/cpu/ORACLE.md:7-41,61-101`). The referenced editions are the 1992 M68000 Family Programmer's Reference Manual and the ninth-edition 1993 M68000 User's Manual. The fixture bytes are authored in-tree; no third-party game or BIOS bytes are used. The report and checked-in evidence contain repository-relative paths and no private local paths. Rights and fixture provenance are adequate for this private experiment.

### Closure, generation, FPU/SoftFloat, and host calls

The runtime target contains only the adapter, `m68kcpu.c`, and generated `m68kops.c`; generator and Unity targets are separate (`experiments/cpu/CMakeLists.txt:9-18,30-43`). The adaptation recipe disables later CPU/MMU configurations, removes FPU/MMU/SoftFloat dependency edges, replaces 040 FPU/MMU dispatch with unsupported-instruction exceptions, and generates the opcode sources from the pinned input (`tools/cpu/adapt.py:15-49,91-110`). The selected configuration keeps prefetch and address-error handling on (`third_party/musashi/m68kconf.h:67-84,223-234,254-255`). I found no real FPU or SoftFloat implementation in the runtime closure.

The submitted `cpu_closure` evidence records the runtime objects, compiler dependency and preprocessed-source closure, AST references, archive imports, and minimal-consumer link map; `regeneration` records two parallel scratch generations matching the checked-in generated bytes. The source audit implements these checks in `tools/cpu/audit.py:267-329,226-251`. I inspected the recorded receipts and generated-source provenance; I did not regenerate them. The declared host calls are bounded memory/initialization, current-call jump-frame, and compiler support calls. Runtime bus operations use explicit callbacks (`experiments/cpu/cpu_adapter.c:25-38`); no runtime file/device/network/environment or wall-clock service is exposed. The generator's host I/O and process exit are isolated from the runtime archive.

### Explicit context propagation and mutable ownership

Each adapter instance owns its `m68ki_context`, allocator, readiness/fault/active flags, and bus binding (`experiments/cpu/cpu_adapter.c:7-11`). The adapted Musashi context owns CPU state, cycle scratch, trace/address-error fields, jump frames, dispatch/cycle tables, bus data/callbacks, and instruction count (`third_party/musashi/m68kcpu.h:1016-1040`). Core macros resolve through the explicit `ctx`, and generated handlers take that context (`third_party/musashi/m68kcpu.h:326-400`; `tools/cpu/adapt.py:56-90`). I found no mutable global current-instance pointer, TLS route, global execution lock, or lazy global opcode initialization. Shared opcode/cycle/shift tables in the state inventory are `const`; per-instance opcode tables are built by `m68ki_build_opcode_table(ctx)` (`third_party/musashi/m68kcpu.c:1059-1074`).

The compiler-derived state inventory has 99 entries and binds each declared field/global to a reviewed class, owner, mutation sites, and restore disposition. `tools/cpu/state_inventory.py:17-45,47-83` extracts declarations, checks exact equality with the inventory, rejects mutable shared globals, and verifies guest-field codec mappings. Guest arrays and scalars are copied in both directions; host allocator/bus/callback pointers and `jmp_buf`s remain on the destination; derived tables and CPU constants are rebuilt; transient cycle scratch is normalized (`experiments/cpu/cpu_adapter.c:87-124`; `experiments/cpu/state-inventory.json:14-1317`).

### Cold initialization, failure cleanup, and fault frames

`cpu_create` validates callbacks and model before its sole allocation, initializes the whole instance, then builds its own backend tables (`experiments/cpu/cpu_adapter.c:39-49`). Allocation failure returns with `*out == NULL`; there is no later allocation to leak. Destruction retains and calls the instance allocator, while overlapping/reentrant same-instance lifecycle calls are rejected or prohibited by contract (`experiments/cpu/cpu_adapter.c:51-59`; `cpu_adapter.h:15-20`). The recorded cold tests start two workers behind a barrier before backend creation and compare their results to isolated baselines (`tests/cpu/test_cold.c:7-20`); the fault tests fail each observed allocation position and preserve a healthy witness (`tests/cpu/test_faults.c:14-23`). The receipt reports native and TSan cold lanes as executed and passing; this review did not repeat those runs.

Reset and run install a host-fault `setjmp` frame for that call, clear `active` and mark the instance terminal when a bus callback fails, and permit subsequent reset/destruction only (`experiments/cpu/cpu_adapter.c:54-79`). Musashi installs its address-error and bus-error frames at execution entry before IRQ stack/vector accesses (`third_party/musashi/m68kcpu.c:928-950`); the address-error path handles nested stack failures and exhausted cycle budgets (`third_party/musashi/m68kcpu.h:612-667,2073-2102`). Tests retain reset/fetch/store/IRQ-stack/exception-stack/nested-stack/odd-IRQ regressions with healthy witnesses (`tests/cpu/test_faults.c:25-53`). Callback failure is explicitly a host fault, not a guest bus-error frame. True 68000 guest bus errors remain unsupported.

### Cycles, exception bounds, and selected guest behavior

The public-private adapter entry accepts signed requests from 0 through 1,000,000, returns before backend entry on zero, rejects invalid bounds, and checks instruction-counter headroom before positive execution (`experiments/cpu/cpu_adapter.h:21-24`; `experiments/cpu/cpu_adapter.c:61-79,100-114`). With the request bounded below signed-int limits and the selected overshoot tied to the finite instruction/exception tables, the current arithmetic has substantial `int` headroom. Tests cover exact neighboring reset-debt requests, overshoot, zero, STOP idle, invalid requests, instruction budgets, RESET, TRAP, illegal and privilege exceptions, IRQ/RTE, and address error (`tests/cpu/test_timing.c:6-58,60-109`). The oracle explicitly limits claims to selected instruction and exception boundaries; it does not claim bus-cycle suspension, board timing, or hardware measurements (`tests/cpu/ORACLE.md:79-101`).

The original guest's expected value 10 comes from MOVEQ #7, ADDQ.L #3, and a big-endian store; the supervised operand mutation must produce the intended assertion failure with 11 (`tests/cpu/guest_fixture.c:4-10`; `tests/cpu/test_guest.c:21-39`; `tests/cpu/negative.py:1-9`). Isolation, IRQ/RTE ownership, and state mutations have similarly consequential comparisons rather than crash-only controls (`tests/cpu/test_isolation.c:16-46`; `tests/cpu/state_negative.py:1-11`; `tests/cpu/test_state.c:110-122`).

### Fresh-destination bindings and continuation

The state test creates a destination with a distinct owner, copies guest RAM separately, restores a typed guest record, destroys and overwrites the source, then compares six continuation calls, RAM, full state, and ordered bus observations (`tests/cpu/test_state.c:54-78`). It covers reset debt, prefetch, STOP, masked IRQ, pending NMI with pins low, illegal/address-error entry, and post-RTE normal modes (`tests/cpu/test_state.c:33-52`). Restore validates a private temporary before mutating live state, rebuilds CPU-derived fields, and does not copy host pointers or jump buffers (`experiments/cpu/cpu_adapter.c:100-124`). The report's native and ASan/UBSan continuation and mutation records pass. These are private same-build continuation observations; the report correctly makes no durable or public ABI claim.

### Budget, review identity, and admission tooling

The frozen contract permits two attempts, 16 cumulative hours, 8 hours per attempt, six selected upstream files, and the listed handwritten/semantic/helper/generated caps (`experiments/cpu/ACCEPTANCE.md:63-110`). The report's computed values are within all caps: 2 attempts, 20,005 total seconds, 18,859 final-attempt seconds, 6 upstream files, 2,614 handwritten lines, 483 semantic lines, 523 helper lines, and 36,559 generated lines / 832,698 bytes (`experiments/cpu/acceptance-results.json:78-97`). The effort ledger and audit retain cumulative history and bind semantic review to source hashes (`tools/cpu/audit.py:128-180`; `experiments/cpu/budget-ledger.json`). This review does not reset or expand the frozen allowance.

The reducer requires exact source/configuration identities, the complete per-lane required-case denominator, nonzero matching observed counts, supported toolchain identity, exact unsupported denominator, cap compliance, and a review matching source and evidence digests (`tools/cpu/acceptance.py:77-142`). Verification checks the evaluated commit's input bytes, ledger/history, frozen contract, output digests, regeneration receipt, and review receipt (`tools/cpu/acceptance.py:294-343`). The receipt has 56/56 passing records but still has `review: null` and `GAPS_FOUND`; that is an appropriate non-admitting state before this review is sealed.

The following remain explicitly unsupported, and this review does not promote them: distinct compiler/toolchain lane, true 68000 guest bus-error fidelity, arbitrary bus-cycle suspension, Neo Geo board/BIOS/game compatibility, public/durable state compatibility, and release-platform support (`experiments/cpu/acceptance-results.json:39-45`). The recorded Apple Clang ASan/UBSan and TSan outcomes are runtime evidence supplied in the report; this source audit is neither a sanitizer rerun nor a new race-detector result.

## Limitations

This review covers the exact evaluated Musashi adaptation, current source/fixtures, and submitted report. It does not establish hardware truth beyond the cited manual-derived cases; actual Neo Geo hardware, full board/BIOS/game compatibility, unsupported guest bus errors, arbitrary mid-instruction or bus-cycle checkpoints, public state compatibility, other compiler families, or release platform support. The report's native runtime, ASan/UBSan, TSan, cold-start, and continuation outcomes were inspected as receipts only and were not rerun by this reviewer.

## Machine-readable review metadata

```json
{
  "reviewer": "codex:cpu_acceptance_review_01",
  "independent": true,
  "source_revision": "94f468326e5e529fd7c54f28434816c27f80f379",
  "content_digest": "81aa0d99145d7b214a7336ae02f9a825eff328c8c26011fd2eef35fbe977b527",
  "evidence_digest": "6dafb025bf1b3ba2a52750cae3e9f50a1db3a552ebb8507edebb8fa2ec493c66",
  "inspected": [
    "rights-oracles",
    "closure-generation",
    "explicit-call-graph",
    "all-state-fields",
    "cold-init-cleanup",
    "fault-frames",
    "cycles-exceptions",
    "fresh-bindings",
    "consequential-controls",
    "budgets-effort",
    "admission-tooling",
    "public-hygiene"
  ],
  "findings": [
    {
      "id": "REV-LOW-01",
      "severity": "low",
      "status": "resolved",
      "summary": "The initial review found ACCEPTANCE.md said 98 state inventory entries; the checked inventory has 99.",
      "resolution": "ACCEPTANCE.md now says 99, matching all 99 entries in state-inventory.json; no runtime-source change was needed."
    }
  ]
}
```
