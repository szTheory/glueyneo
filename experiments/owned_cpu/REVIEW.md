# Independent final owned CPU review — Plan 01-14

## Reviewed revision:

Plan 01-16 independent review revision: `a10f2bf9d86482baffaecf6a4155d30a9355855d`. Fresh executor collection revision: `17a2e90ca4535dd9ee8353f238c2867602722d35`; collection SHA-256: `9ab91a0ba44cb20eadcb3383d147925b4ffd00bf859ba1ff1dd4ff96950875ed`; canonical JSON source-map SHA-256: `577d468a3169dd84c459e9c9d8553bdb4a1b8fe9d2a7c5b413fdc01c41a2c2b7`; manifest SHA-256: `10c00df7a0733c9d620a6da43e8d2be3426e2a276f03831972d6b8f2c4499da0`. Independent snapshot equality passes with 38 manifest entries, including the authored reconciliation record. Runtime/header/state inventory/timing fixture/oracle bytes match the historical Plan 14 closure. Collection ancestry and all three earlier collections are preserved. This binding supersedes the current-binding role of the Plan 14 paragraphs below; those paragraphs remain historical evidence.

Final seal/review and collected revision: `3cd2d7d5192d0e85ebc4be9f472deace1a4511de`. Final canonical source-map digest: `e0dc3cc73902ee8dbbf215a375ee74dfb515d01ba40a057e9f14b11f3f5ddc6d`; manifest digest: `b4800575f955afd9177ae55c780b96a7330469a034b097921016a11cd4ec836b`; latest collection digest: `1b09aaa3d55a9b05db117e81d0aa5a170729654c373770093a75eb63b620838f`. The reviewer independently confirmed exact snapshot equality, zero manifest errors and 37 current manifest entries. The documentation delta includes authored MIT `ACCEPTANCE.md` in the source closure and refreshes its manifest; runtime/tool/test/preset files remain byte-identical to `ca79b00`. No additional reviewer behavioral execution is claimed. The executor's fresh final collection records all four lanes passing 12/12. Findings and dispositions remain unchanged.

Historical document-only alias `34bf236ffbc872e70fee59fc506a8d44e7137829` briefly lacked the new report's manifest entry. That transient mismatch is reconciled by the explicit report/manifest commit and fresh collection at `3cd2d7d`; no prior receipt was replaced. The actual distribution rule includes `ACCEPTANCE.md`, so report prose avoids self-referential current receipt digests. This is document/manifest evidence work, not a new CPU qualification or runtime change. The repaired code review and original repaired collection identities below remain historical exact evidence.

Repaired code review and original repaired collection revision: `ca79b00f368120a4087705d669eaa10de7e930ab`. Repaired canonical JSON source-map SHA-256: `8d78b6706d84cb469be849dd4ed0cd06a1e2f85ab1bb8f8cf6511edd04631cd8`; repaired manifest SHA-256: `e2aaa95cc3aad109b3e2c9e30453ba4b7d064652a41f9de95b77b88abb652f04`; repaired collection SHA-256: `3b31b169be64a09c68eed8600135e23566752819501740662dcf8b2ff5771380`. The repaired source snapshot matches exactly. Runtime, header and state-test hashes below remain unchanged. Initial findings are preserved in commit `a43b93e`; code/regression repair and mechanical source-manifest refresh are in `ca79b00`.

Initial reviewed HEAD: `8e26d7c3ffc8dd31b7741cfe2f4ed8d55b248b82`; starting tree clean. Collection revision: `dfd281091626b05c40c4e90789442e7c19fd97c2`. Source hashes match the current manifest exactly. Canonical JSON source-map SHA-256: `601e1b27a96b8ee1c9238e133bab34041f1ad946498e991b19b244181bc016ed`; manifest SHA-256: `013d53c42c0070fcc791724d2e304728c202b6e370e058476df66510ffde487c`; collection SHA-256: `a96c08b486ee48e960b98b058bb763d3c6b5067dd33b85c00e193897d9536fc9`. Runtime `cpu.c`: `8ac6ded7859184651f6eb3fff8a87c073f8e24a98d66175b64c3d86f69cbd15f`; header: `afdc50cbfdce47cdb17f881fed6fe47b72d919e3220b9c599f6262f868d50eee`; state fixture: `25b12a79f08049cd7eb0bdf8af2f97ca74ba1798184397bccc90fa1cff308b31`.

Scope: private runtime/header, target CMake closure/presets, source/state inventories, fixture and semantic/timing/isolation/fault/state tests, controls, collector, contract, provenance, manual oracle and historical receipts. The manifest has 36 distributed inputs and 10 compiled translation units; only `cpu.c` enters the runtime archive. Unity is test-only at immutable MIT pin `b6763fbd9cedfacaa89e2ad9fd00d615a234e355`; pinned source/notice hashes match. This bounded source review is not a formal proof or a full behavioral audit of Unity.

## Reviewer independence:

Plan 01-16 reviewer: a fresh separate non-author agent, sole write owner of this report; no runtime, collector, test, manifest, result, accounting or acceptance-report edits. Read-only controls ran against the supplied closure. Native timing execution used the executor-built Debug binary; no reviewer configure/build or four-lane native rerun is claimed. Executor collection and independent execution are distinguished below. Final metadata-only closure rebinding remains required before sealing.

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

Plan 01-16 fresh independent execution:

- `PYTHONDONTWRITEBYTECODE=1 python3 [-O] -m unittest discover -s tests/owned_cpu -p test_contract.py`: normal and optimized each 13/13 passed.
- Same normal/optimized discovery for `test_acceptance.py`: each 14/14 passed, including the repaired command/configuration and historical-disposition regressions.
- `PYTHONDONTWRITEBYTECODE=1 python3 [-O] tools/owned_cpu/acceptance.py self-test`: each six rejection and two classification controls passed.
- `python3 tools/owned_cpu/contract.py validate`: 24 markers, 10 historical hashes, CPU-01–05 Pending and Phase 02 gated.
- `python3 tools/owned_cpu/contract.py budget`: pass, no pause, 35,825 active seconds, 17 records, runtime churn 1,206 and test/tool churn 5,252 at initial review; subsequent review/closeout charges remain executor-owned.
- `python3 tools/owned_cpu/inventory.py check --build-dir build/owned-debug`: 26 fields / 10 compiled sources passed.
- `build/owned-debug/experiments/owned_cpu/owned_cpu_timing`: 23 Unity cases, zero failures/ignored, including the exact ILLEGAL frame assertion. This establishes the current $100 observation only.
- In-memory inspection through `acceptance.snapshot`, `acceptance.verify` and strict base64 decoding confirmed exact current snapshot equality, four collections, no lane blockers, unqualified disposition, archive equality with active CONTRACT, unchanged runtime/header/state/fixture/oracle bytes, preserved earlier collection prefix and preserved original ledger prefix/non-entry fields. The first inspection used a wrong archive key and exited 1 after successful receipt checks; corrected key `bytes_base64` then passed. No evidence was mutated by either inspection.

The executor's fresh collection independently records four successful configure/build/test lanes, each 12/12. Per lane Unity counts are 2 diagnostic, 17 semantics, 23 timing, 4 isolation, 5 faults and 5 state; receipts report 13 continuation checkpoints, 32 interleaved pairs, 32 concurrent pairs, 16 cold processes and five negative controls. Their exact commands/configurations/counts are checked by the existing verifier. The retained runtime identity makes a new continuation-identity repair unnecessary. No fresh phase verification or new platform support is established.

The proposed one-case/one-assertion/one-failure wrong-ILLEGAL-PC control remains withheld because source adjudication is unresolved. The existing negative timing control targets address-error cycles, not this saved-PC dispute. Its successful receipt must not be promoted into an ILLEGAL-PC control claim. This conditional branch is explicitly unqualified, rather than a skipped acceptance criterion silently counted as passing. All nine flagged plan assumptions remain unresolved.

Fresh reviewer execution on the reviewed source, using existing collector-built binaries:

- `ctest --preset owned-debug --output-on-failure --no-tests=error`: 12/12 passed.
- Same command for `owned-release`, `owned-asan-ubsan` and `owned-tsan`: each 12/12 passed.
- `ctest --test-dir build/owned-asan-ubsan -R '^owned_cpu_state$' --repeat until-fail:10 --output-on-failure --no-tests=error`: 10/10 repetitions passed, five state tests each.
- `python3 -O tools/owned_cpu/acceptance.py self-test`: six rejection plus two classification controls passed.
- `python3 -m unittest discover -s tests/owned_cpu -p test_acceptance.py`: 12/12 passed. Existing controls miss F14-01/F14-02.
- Both in-memory false-qualification reproducers below executed; actual receipts untouched.

Fresh independent re-review on `ca79b00`: normal and optimized `python3 [-O] -m unittest discover -s tests/owned_cpu -p test_acceptance.py` each pass 14/14. Normal and optimized collector self-tests each pass six rejection and two classification controls. The original combined sanitizer/configuration/`true` command reproducer now rejects with `unexpected lane commands`; separately tested configuration/command/status mutations are covered by the new regression. Rehashed accepted history mutations for fail, unknown and skipped each reject with the shared historical-disposition error. `inventory.py check --build-dir build/owned-debug` passes 26 fields / 10 compiled sources. Frozen-history hashes independently match 10/10 again.

The executor's fresh final collection at `ca79b00` independently records configure/build/CTest for all four lanes, each 12/12. The reviewer reconciled their exact revision/source-map/manifest/collection identities and inspected the repair diff; the reviewer did not rerun all four native lanes after this tooling-only repair. Earlier reviewer native executions above remain bound to unchanged runtime and behavioral fixtures. No fresh GSD phase verification was run. This distinction separates executed reviewer controls, executor collection and document reconciliation.

Each lane contains diagnostic 2, semantics 17, timing 23, isolation 4, faults 5 and state 5 Unity cases. Continuation exercises 13 checkpoints with six continuation calls each (78); isolation 32 interleaved and 32 concurrent pairs; cold supervision 16 fresh processes with two concurrent instances each. Five named negative controls run. Inventory checks cover 26 owned fields and 10 compiled sources. This review reran tests, not configure/build; build/binary identities are reconciled with collector receipts and actual inventory checks. Apple Clang 21 / Darwin arm64 is the only measured host. Exact CMake 3.20 execution and other platforms remain unknown.

Architecture/decode review found opaque per-instance ownership, explicit caller allocator/bus bindings, no mutable runtime global or ambient clock/filesystem/network/device/process service. Same-instance overlap remains unsupported; `active` is not a concurrency lock. Masks select the declared instruction forms. Unsigned sign extension/modulo arithmetic and bounded shifts avoid the historical UB mechanisms; ADDQ flags and word-MOVE preservation have expected-result boundary cases under UBSan. Odd accesses precede bus callbacks; partial writes persist on terminal host faults; nested frame/vector faults do not recurse. IRQ/reset/instruction/idle are separate whole events. Capture/restore stage named fields and retain destination host bindings; tests destroy/overwrite source owners and continue actual execution. The continuation validator intentionally establishes only stated conservative invariants. No public CPU ABI, durable state, arbitrary partition equivalence or full ISA is qualified.

Current closure/receipt textual privacy scans found no personal home path, private email, credentials or private media. Ignored caches/logs stay local. This is a bounded textual scan, not proof about arbitrary future tool output. The original MIT fixture bytes are authored; no commercial ROM/BIOS or manual PDF bytes enter the distribution.

## Oracle ancestry:

Plan 01-16 reopened all three official URLs below on 2026-10-03 and independently downloaded/hash-checked bytes in memory without distributing PDFs. UM SHA-256 `89b690b1923f8a3cff508567090bcab0bcd07511c2deff8ffa393a08efda18e1`, PRM `06e4864b78da0e815054cead9326b7ec9914661f240fd39a455f2061ff47c4e8`, and [PRMER](https://www.nxp.com/docs/en/reference-manual/M68000PRMER.pdf) `8ae8228b3e2e54169a4e50310eafcbc14531740c57638b8c419c9751f4e88dc9` match the reconciliation record. Printed identities are UM Ninth Edition/copyright1993, PRM copyright1992 and PRMER Rev.1/03-2007; historical catalog labels below do not establish printed editions. The errata's stated PRM Revision1 applicability is retained with the downloaded PRM cover's revision uncertainty. All errata pages were reopened; listed corrections concern FDBcc, FMOD, FMOVE and FRESTORE, with no ILLEGAL correction. Silence does not select a PC rule.

Independent adversarial reading: UM §6.2.3/Table6-3 puts illegal detection before execution; §6.2.5's general next-unexecuted rule and §6.3.8's tracing distinction therefore favor $100. UM §6.3.6's trap analogy and group2-frame wording, read with §6.3.5's following-instruction rule, support the competing $102 inference. A shared short-frame layout need not imply shared PC selection; conversely, the pre-execution rule alone does not explicitly adjudicate the deliberately encoded 4AFC trap. PRM printed4-107 states PC stacking and the MC68000 frame distinction without fixing this value. These are competing interpretations of vendor prose, not two independently measured silicon outcomes. No instruction-specific correction was established. The stronger fault-PC inference remains insufficient here to silently supersede the frozen specific requirement.

Authored original fixture/assertions ground diagnostic arithmetic/store values. Official [MC68000 User's Manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf), ninth edition (locally cited Rev. 9.1 / 2006-01-25), supplies IRQ/frame/exception/timing evidence; official [M68000 Programmer's Reference Manual](https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf), NXP-hosted 1992 manual, supplies operations/encodings. Local publication/retrieval-date differences do not establish a hardware revision. This review reopened the official PDFs, including UM §§6.2.4–6.3.7, Table 8-14 and PRM ILLEGAL printed p.4-107.

UM §6.3.2 supports level-7 transition and comparison. §6.3.7 explicitly saves the privilege-offending instruction address. §§6.2.4/6.2.5 describe the next unexecuted instruction, which is not uniformly the following sequential instruction. The specific ILLEGAL contract discrepancy below remains unresolved; the manual does not justify silently changing the frozen contract or calling all observations compliant. Address-error saved-PC selection is local, not a restart guarantee. Functional callback order/host-fault handling are project contracts, not per-pin captures. MAME/Musashi/SingleStepTests/Rocket68 comparisons share ancestry and cannot establish hardware truth. No silicon/board capture, BIOS/game support, full ISA, Neo Geo timing or gameplay-performance claim is established.

## Findings and dispositions:

### F14-01 — HIGH — fixed at ca79b00 — Successful receipts lacked command/configuration binding

Location: `tools/owned_cpu/acceptance.py`, initial `verify` lines280–291. Scope: repairable within Plan 14 Task 2.

Executed reproducer: deepcopy the real result; replace the `owned-asan-ubsan` lane configuration with `{'GLUEYNEO_OWNED_CPU_SANITIZER': 'NONE'}` and test command with `['true']`; rehash collection using `digest` excluding `sha256`; `verify(document, False)` returns pass with no lane blockers. Preserved logs/counts suffice. Successful rows require only nonempty commands/configuration and zero exits, without exact command/configuration/status binding. Even the positive unit fixture repeats configure three times with an unrelated configuration key.

Impact: read-only verification qualifies a required sanitizer lane despite contradictory recorded identity. The normal collector constructs correct commands, but validation is an explicit integrity boundary. Repair requires exact per-lane configure/build/test sequence/configuration, coherent statuses, and direct mutation regressions. Preserve the first real receipt.

Final disposition: fixed. The separate fixer centralizes exact lane commands/configuration and binds successful statuses/exits, expected artifact keys and SHA-256 syntax, compiler/diagnostic output digests and diagnostic invocation. `test_rehashed_real_asan_configuration_and_command_cannot_false_green` exercises 11 individual identity/status/output/artifact mutations of the preserved real ASan receipt. All reject, normal and optimized. Independent original combined reproducer rejects. The first collection and report remain preserved; current run identities were refreshed rather than overwritten. This validator is not a cryptographic attestation against an actor able to fabricate every result and identity consistently.

### F14-02 — HIGH — fixed at ca79b00 — Accepted verification omitted historical failure guard

Location: `tools/owned_cpu/acceptance.py`, accepted `verify` branch versus `seal`. Scope: repairable within Plan 14 Task 2.

Executed reproducer: prepend to a deepcopy of real results a rehashed collection whose first lane is `unknown`; set disposition `accepted` plus clean review/collection binding sufficient for `verify(..., False)`. Result: pass, accepted, two collections, no lane blockers. `seal` refuses earlier fail/unknown/skipped lanes, but `verify` omits the guard. Share the guard and regress all three statuses. No current recorded lane failed; this is an integrity counterexample, not a native CPU failure.

Final disposition: fixed. `historical_blockers` is now shared by seal and accepted verification. `test_accepted_history_cannot_silently_replace_failure` retains a qualifying positive fixture and rejects each historical fail/unknown/skipped mutation. Fresh independent mutations of the real repaired collection reject all three statuses. No earlier result was discarded or promoted.

### F14-03 — HIGH — open — Canonical ILLEGAL requirement disagrees with tested frame PC

Location: `experiments/owned_cpu/CONTRACT.md:61`, `cpu.c:478–487`, `tests/owned_cpu/test_timing.c:264`, and oracle. Scope: outside the five authorized repair paths; preserve GAPS_FOUND for user-directed reconciliation.

The specific canonical table requires ILLEGAL to stack old SR and next PC. Runtime passes `instruction_pc` to vector4; named test/oracle require `$100` for ILLEGAL at `$100`, instead of following sequential `$102`. Fresh timing execution passes that fault-PC assertion. The later next-unexecuted wording can accommodate an offending instruction not executed, but leaves the table's specific wording contradictory. This is a contract/evidence disagreement, not a demonstrated C safety or CPU semantic defect. It prevents asserting every canonical observation is satisfied. Do not modify runtime to follow disputed wording or mutate the frozen contract/hash within Plan 14. Authorize primary-source contract reconciliation and refresh affected evidence without rewriting history.

Disposition: GAPS_FOUND

Plan 01-16 independent disposition: F14-01 and F14-02 remain fixed; their fresh normal/optimized regressions pass. F14-03 remains HIGH/open. The embedded original frozen contract equals active canonical bytes and retains the disputed row; there is no contract-revision chain to validate because no canonical transition occurred. SUBSET:61 remains observed-behavior provenance, not adjudicated supersession. The test, runtime and local oracle agree on $100, but their shared project ancestry cannot settle the authoritative requirement.

Applying the hardware/oracle, C/host-safety, test-reliability, evidence, maintenance and product lenses yields one recommendation: preserve unchanged implementation and explicit unqualified/GAPS_FOUND pending authoritative original-MC68000 4AFC saved-PC adjudication that addresses the trap/group wording. A reviewable derivation accepted for the bounded architecture contract could reopen the finding; alternatively a minimal identified silicon capture or explicit user-directed scope/claim revision and replanning could do so. No hardware capture is asserted or automatically required. Premature mutation risks concealing the wrong assumption; continued ambiguity blocks admission without proving a C defect. CPU-01–05 remain Pending, Phase 01 open and Phase 02 gated. No new high/critical finding or unauthorized repair arose in this bounded review.

F14-01/F14-02 are resolved by regression-backed repairs and fresh independent re-review. F14-03 remains an admission blocker outside Plan 14 repair scope. Required native tests and prior state fixes pass within recorded scope. CPU-01–04 stay Pending, Phase 01 stays open and Phase 02 gated. No budget cap, historical charge or phase verification changes here; a resource threshold is not CPU rejection.
