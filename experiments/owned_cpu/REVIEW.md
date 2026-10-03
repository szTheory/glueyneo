# Independent final owned CPU review — Plan 01-14

## Reviewed revision:

Initial reviewed HEAD: `8e26d7c3ffc8dd31b7741cfe2f4ed8d55b248b82`; starting tree clean. Collection revision: `dfd281091626b05c40c4e90789442e7c19fd97c2`. Source hashes match the current manifest exactly. Canonical JSON source-map SHA-256: `601e1b27a96b8ee1c9238e133bab34041f1ad946498e991b19b244181bc016ed`; manifest SHA-256: `013d53c42c0070fcc791724d2e304728c202b6e370e058476df66510ffde487c`; collection SHA-256: `a96c08b486ee48e960b98b058bb763d3c6b5067dd33b85c00e193897d9536fc9`. Runtime `cpu.c`: `8ac6ded7859184651f6eb3fff8a87c073f8e24a98d66175b64c3d86f69cbd15f`; header: `afdc50cbfdce47cdb17f881fed6fe47b72d919e3220b9c599f6262f868d50eee`; state fixture: `25b12a79f08049cd7eb0bdf8af2f97ca74ba1798184397bccc90fa1cff308b31`.

Scope: private runtime/header, target CMake closure/presets, source/state inventories, fixture and semantic/timing/isolation/fault/state tests, controls, collector, contract, provenance, manual oracle and historical receipts. The manifest has 36 distributed inputs and 10 compiled translation units; only `cpu.c` enters the runtime archive. Unity is test-only at immutable MIT pin `b6763fbd9cedfacaa89e2ad9fd00d615a234e355`; pinned source/notice hashes match. This bounded source review is not a formal proof or a full behavioral audit of Unity.

## Reviewer independence:

Independent reviewer: fresh separate non-author review agent, with sole write ownership of this report.
Authored runtime/collector/tests: no

The reviewer changes no implementation, tests, inventory, accounting or results. Reproducers mutate receipts only in memory. Repairs belong to a separate fixer/executor. Independence concerns implementation authorship; no human review or physical hardware measurement is asserted.

## Prior findings:

The actual Plan 12 artifact is `REVIEW.md`, preserved at `39f8a43`, SHA-256 `c88cca6f9e79e7c824e8d6eb3eda70b954603df69b2085855c2c16da1e2d7c52`, corroborated by `01-12-SUMMARY.md`; no `SOURCE_REVIEW.md` exists.

| Finding | Current disposition |
|---|---|
| BL-01: indeterminate state-test destination | Fixed: destination is zeroed before binding allocator. Fresh ASan+UBSan full suite 12/12; state repeat 10/10. |
| WR-01: impossible instruction counter accepted | Fixed for the reported case: `state_instruction_count_valid` rejects nonzero instruction clocks with zero dispatches. Fresh state and counter control pass with destination/bus atomicity. This conservative invariant is not a reconstruction of every reachable history. |
| Restore-over-ready observation | Still inconclusive, no promoted claim: runtime permits ready nonfaulted destinations; contract says fresh destination. Required fresh-owner continuation is exercised. |
| Musashi variable-shift range defect | Absent from owned runtime; variable shifts outside subset. |
| Musashi signed division remainder shift | Absent; division outside subset. |
| Musashi signed bit-31 shift | Absent; current runtime uses unsigned bounded shifts. UBSan and expected-result boundaries pass. |
| Generator argument overflow | Not applicable: no generator in compiled/invoked owned closure. |
| Generator EOF sentinel | Not applicable: no generator in closure. |
| Generator array capacity | Not applicable: no generator in closure. |
| Historical optimized assertion warning | Current explicit exceptions work under `-O`; existing tests miss new receipt-binding defects below. |
| Historical relative-path replay warning | Current preset invocation is from repo root with sanitized recorded paths; old receipts are historical only. |

Independent `contract.check_history` matched all 10 frozen historical hashes: Musashi ledger, acceptance/review/results, prior acceptance/review, both attempt receipts, patch and recovery history. No historical bytes or charges changed. These matches reconcile documents; they are not fresh Musashi qualification.

## Evidence runs and denominators:

Fresh reviewer execution on the reviewed source, using existing collector-built binaries:

- `ctest --preset owned-debug --output-on-failure --no-tests=error`: 12/12 passed.
- Same command for `owned-release`, `owned-asan-ubsan` and `owned-tsan`: each 12/12 passed.
- `ctest --test-dir build/owned-asan-ubsan -R '^owned_cpu_state$' --repeat until-fail:10 --output-on-failure --no-tests=error`: 10/10 repetitions passed, five state tests each.
- `python3 -O tools/owned_cpu/acceptance.py self-test`: six rejection plus two classification controls passed.
- `python3 -m unittest discover -s tests/owned_cpu -p test_acceptance.py`: 12/12 passed. Existing controls miss F14-01/F14-02.
- Both in-memory false-qualification reproducers below executed; actual receipts untouched.

Each lane contains diagnostic 2, semantics 17, timing 23, isolation 4, faults 5 and state 5 Unity cases. Continuation exercises 13 checkpoints with six continuation calls each (78); isolation 32 interleaved and 32 concurrent pairs; cold supervision 16 fresh processes with two concurrent instances each. Five named negative controls run. Inventory checks cover 26 owned fields and 10 compiled sources. This review reran tests, not configure/build; build/binary identities are reconciled with collector receipts and actual inventory checks. Apple Clang 21 / Darwin arm64 is the only measured host. Exact CMake 3.20 execution and other platforms remain unknown.

Architecture/decode review found opaque per-instance ownership, explicit caller allocator/bus bindings, no mutable runtime global or ambient clock/filesystem/network/device/process service. Same-instance overlap remains unsupported; `active` is not a concurrency lock. Masks select the declared instruction forms. Unsigned sign extension/modulo arithmetic and bounded shifts avoid the historical UB mechanisms; ADDQ flags and word-MOVE preservation have expected-result boundary cases under UBSan. Odd accesses precede bus callbacks; partial writes persist on terminal host faults; nested frame/vector faults do not recurse. IRQ/reset/instruction/idle are separate whole events. Capture/restore stage named fields and retain destination host bindings; tests destroy/overwrite source owners and continue actual execution. The continuation validator intentionally establishes only stated conservative invariants. No public CPU ABI, durable state, arbitrary partition equivalence or full ISA is qualified.

Current closure/receipt textual privacy scans found no personal home path, private email, credentials or private media. Ignored caches/logs stay local. This is a bounded textual scan, not proof about arbitrary future tool output. The original MIT fixture bytes are authored; no commercial ROM/BIOS or manual PDF bytes enter the distribution.

## Oracle ancestry:

Authored original fixture/assertions ground diagnostic arithmetic/store values. Official [MC68000 User's Manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf), ninth edition (locally cited Rev. 9.1 / 2006-01-25), supplies IRQ/frame/exception/timing evidence; official [M68000 Programmer's Reference Manual](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf), NXP-hosted 1992 manual, supplies operations/encodings. Local publication/retrieval-date differences do not establish a hardware revision. This review reopened the official PDFs, including UM §§6.2.4–6.3.7, Table 8-14 and PRM ILLEGAL printed p.4-107.

UM §6.3.2 supports level-7 transition and comparison. §6.3.7 explicitly saves the privilege-offending instruction address. §§6.2.4/6.2.5 describe the next unexecuted instruction, which is not uniformly the following sequential instruction. The specific ILLEGAL contract discrepancy below remains unresolved; the manual does not justify silently changing the frozen contract or calling all observations compliant. Address-error saved-PC selection is local, not a restart guarantee. Functional callback order/host-fault handling are project contracts, not per-pin captures. MAME/Musashi/SingleStepTests/Rocket68 comparisons share ancestry and cannot establish hardware truth. No silicon/board capture, BIOS/game support, full ISA, Neo Geo timing or gameplay-performance claim is established.

## Findings and dispositions:

### F14-01 — HIGH — open — Successful receipts lack command/configuration binding

Location: `tools/owned_cpu/acceptance.py`, initial `verify` lines280–291. Scope: repairable within Plan 14 Task 2.

Executed reproducer: deepcopy the real result; replace the `owned-asan-ubsan` lane configuration with `{'GLUEYNEO_OWNED_CPU_SANITIZER': 'NONE'}` and test command with `['true']`; rehash collection using `digest` excluding `sha256`; `verify(document, False)` returns pass with no lane blockers. Preserved logs/counts suffice. Successful rows require only nonempty commands/configuration and zero exits, without exact command/configuration/status binding. Even the positive unit fixture repeats configure three times with an unrelated configuration key.

Impact: read-only verification qualifies a required sanitizer lane despite contradictory recorded identity. The normal collector constructs correct commands, but validation is an explicit integrity boundary. Repair requires exact per-lane configure/build/test sequence/configuration, coherent statuses, and direct mutation regressions. Preserve the first real receipt.

### F14-02 — HIGH — open — Accepted verification omits historical failure guard

Location: `tools/owned_cpu/acceptance.py`, accepted `verify` branch versus `seal`. Scope: repairable within Plan 14 Task 2.

Executed reproducer: prepend to a deepcopy of real results a rehashed collection whose first lane is `unknown`; set disposition `accepted` plus clean review/collection binding sufficient for `verify(..., False)`. Result: pass, accepted, two collections, no lane blockers. `seal` refuses earlier fail/unknown/skipped lanes, but `verify` omits the guard. Share the guard and regress all three statuses. No current recorded lane failed; this is an integrity counterexample, not a native CPU failure.

### F14-03 — HIGH — open — Canonical ILLEGAL requirement disagrees with tested frame PC

Location: `experiments/owned_cpu/CONTRACT.md:61`, `cpu.c:478–487`, `tests/owned_cpu/test_timing.c:264`, and oracle. Scope: outside the five authorized repair paths; preserve GAPS_FOUND for user-directed reconciliation.

The specific canonical table requires ILLEGAL to stack old SR and next PC. Runtime passes `instruction_pc` to vector4; named test/oracle require `$100` for ILLEGAL at `$100`, instead of following sequential `$102`. Fresh timing execution passes that fault-PC assertion. The later next-unexecuted wording can accommodate an offending instruction not executed, but leaves the table's specific wording contradictory. This is a contract/evidence disagreement, not a demonstrated C safety or CPU semantic defect. It prevents asserting every canonical observation is satisfied. Do not modify runtime to follow disputed wording or mutate the frozen contract/hash within Plan 14. Authorize primary-source contract reconciliation and refresh affected evidence without rewriting history.

Disposition: GAPS_FOUND

F14-01/F14-02 require in-scope regression-backed repair and independent re-review. F14-03 remains an admission blocker. Required native tests and prior state fixes pass within recorded scope. CPU-01–04 stay Pending, Phase 01 stays open and Phase 02 gated. No budget cap, historical charge or phase verification changes here; a resource threshold is not CPU rejection.
