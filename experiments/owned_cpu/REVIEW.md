# Independent final owned CPU review — Plan 01-14

## Reviewed revision:

Plan 01-16 final independent seal binding: `04e7f84b23957c2e4a7a6115bb6da653740183a8`. The reviewer independently rechecked exact snapshot equality at this HEAD: source-map `577d468a3169dd84c459e9c9d8553bdb4a1b8fe9d2a7c5b413fdc01c41a2c2b7`, manifest `10c00df7a0733c9d620a6da43e8d2be3426e2a276f03831972d6b8f2c4499da0`, collection `9ab91a0ba44cb20eadcb3383d147925b4ffd00bf859ba1ff1dd4ff96950875ed` at ancestor `17a2e90ca4535dd9ee8353f238c2867602722d35`. This is an independent metadata-only handoff after the report commit: included source/report bytes did not change. REVIEW, ledger and result receipts are excluded derived evidence, so their final updates do not require a new native collection. Read-only verification still reports four collections, unqualified, with no lane blockers; F14-03 remains HIGH/open. No further reviewer behavioral execution or phase verification is claimed by this rebinding.

Plan 01-16 independent review revision: `a10f2bf9d86482baffaecf6a4155d30a9355855d`. Fresh executor collection revision: `17a2e90ca4535dd9ee8353f238c2867602722d35`; collection SHA-256: `9ab91a0ba44cb20eadcb3383d147925b4ffd00bf859ba1ff1dd4ff96950875ed`; canonical JSON source-map SHA-256: `577d468a3169dd84c459e9c9d8553bdb4a1b8fe9d2a7c5b413fdc01c41a2c2b7`; manifest SHA-256: `10c00df7a0733c9d620a6da43e8d2be3426e2a276f03831972d6b8f2c4499da0`. Independent snapshot equality passes with 38 manifest entries, including the authored reconciliation record. Runtime/header/state inventory/timing fixture/oracle bytes match the historical Plan 14 closure. Collection ancestry and all three earlier collections are preserved. This binding supersedes the current-binding role of the Plan 14 paragraphs below; those paragraphs remain historical evidence.

Final seal/review and collected revision: `3cd2d7d5192d0e85ebc4be9f472deace1a4511de`. Final canonical source-map digest: `e0dc3cc73902ee8dbbf215a375ee74dfb515d01ba40a057e9f14b11f3f5ddc6d`; manifest digest: `b4800575f955afd9177ae55c780b96a7330469a034b097921016a11cd4ec836b`; latest collection digest: `1b09aaa3d55a9b05db117e81d0aa5a170729654c373770093a75eb63b620838f`. The reviewer independently confirmed exact snapshot equality, zero manifest errors and 37 current manifest entries. The documentation delta includes authored MIT `ACCEPTANCE.md` in the source closure and refreshes its manifest; runtime/tool/test/preset files remain byte-identical to `ca79b00`. No additional reviewer behavioral execution is claimed. The executor's fresh final collection records all four lanes passing 12/12. Findings and dispositions remain unchanged.

Historical document-only alias `34bf236ffbc872e70fee59fc506a8d44e7137829` briefly lacked the new report's manifest entry. That transient mismatch is reconciled by the explicit report/manifest commit and fresh collection at `3cd2d7d`; no prior receipt was replaced. The actual distribution rule includes `ACCEPTANCE.md`, so report prose avoids self-referential current receipt digests. This is document/manifest evidence work, not a new CPU qualification or runtime change. The repaired code review and original repaired collection identities below remain historical exact evidence.

Repaired code review and original repaired collection revision: `ca79b00f368120a4087705d669eaa10de7e930ab`. Repaired canonical JSON source-map SHA-256: `8d78b6706d84cb469be849dd4ed0cd06a1e2f85ab1bb8f8cf6511edd04631cd8`; repaired manifest SHA-256: `e2aaa95cc3aad109b3e2c9e30453ba4b7d064652a41f9de95b77b88abb652f04`; repaired collection SHA-256: `3b31b169be64a09c68eed8600135e23566752819501740662dcf8b2ff5771380`. The repaired source snapshot matches exactly. Runtime, header and state-test hashes below remain unchanged. Initial findings are preserved in commit `a43b93e`; code/regression repair and mechanical source-manifest refresh are in `ca79b00`.

Initial reviewed HEAD: `8e26d7c3ffc8dd31b7741cfe2f4ed8d55b248b82`; starting tree clean. Collection revision: `dfd281091626b05c40c4e90789442e7c19fd97c2`. Source hashes match the current manifest exactly. Canonical JSON source-map SHA-256: `601e1b27a96b8ee1c9238e133bab34041f1ad946498e991b19b244181bc016ed`; manifest SHA-256: `013d53c42c0070fcc791724d2e304728c202b6e370e058476df66510ffde487c`; collection SHA-256: `a96c08b486ee48e960b98b058bb763d3c6b5067dd33b85c00e193897d9536fc9`. Runtime `cpu.c`: `8ac6ded7859184651f6eb3fff8a87c073f8e24a98d66175b64c3d86f69cbd15f`; header: `afdc50cbfdce47cdb17f881fed6fe47b72d919e3220b9c599f6262f868d50eee`; state fixture: `25b12a79f08049cd7eb0bdf8af2f97ca74ba1798184397bccc90fa1cff308b31`.

Scope: private runtime/header, target CMake closure/presets, source/state inventories, fixture and semantic/timing/isolation/fault/state tests, controls, collector, contract, provenance, manual oracle and historical receipts. The manifest has 36 distributed inputs and 10 compiled translation units; only `cpu.c` enters the runtime archive. Unity is test-only at immutable MIT pin `b6763fbd9cedfacaa89e2ad9fd00d615a234e355`; pinned source/notice hashes match. This bounded source review is not a formal proof or a full behavioral audit of Unity.

## Reviewer independence:

Plan 01-16 reviewer: a fresh separate non-author agent, sole write owner of this report; no runtime, collector, test, manifest, result, accounting or acceptance-report edits. Read-only controls ran against the supplied closure. Native timing execution used the executor-built Debug binary; no reviewer configure/build or four-lane native rerun is claimed. Executor collection and independent execution are distinguished below. Final metadata-only closure rebinding is completed in the first reviewed-revision paragraph before executor sealing.

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

## Historical Plan 01-21 current review (full prior section preserved)

<!-- owned-cpu-historical-review:start -->

# Plan 01-21 independent P01-C-14 candidate review

## Reviewed revision:

Reviewed source/report revision: `931e2f07e85a17a9360d74b1b98ed6e1b89e340f`.
Task 3 independent final confirmation: the original source review was performed
at `a3cec086a75c3c7783bcde610f6e8c4234354eeb`. Comparing that revision to this
final revision finds no included-source change; all 39 snapshot entries and all
five collection records are identical. This is metadata rebinding after review,
security, validation and append-only accounting commits, with no native rerun
claimed. The security assessor's bounded attestation independently reports
ASVS L1/block-high, verified, zero current candidate high/critical findings and
the same collection/amendment/source-map; it preserves the withheld historical
frame mitigation and unknown silicon result. Its initial assessment revision is
`0e2003fe8fdb4a1e804fb6a5fe92c618b909b43a`; assessor-owned final rebinding must
confirm this same final revision before the deferred seal.

Task 3 bounded recovery confirmation: the initially created deferred seal at
`635714631770a6450e1f2e46bef6a377571aabd5` later failed read-only verification
after security report metadata changed, making its recorded document hash stale.
The failure was preserved at `931e2f0`; it is not a behavioral test failure or
a passing final receipt. Executor recovery preserves the entire prior seal
exactly in additive `superseded_seals[0]`, with reason/revision, and removes only
its active-seal designation. Independent comparison to the seal committed at
`33c2f48` confirms exact object equality. All five collections still equal the
preplan array, all 39 included hashes equal current bytes, and ten frozen
historical file hashes pass. No implementation or test changed.
Unsealed verification passes as unqualified/GAPS_FOUND; that result does not
replace the live final seal gate. Both independent reports must rebind to this
recovery revision before a fresh deferred receipt, then remain frozen while
exact receipt verification runs. No native rerun or silicon conclusion is
claimed. The separate assessor owns current security outcome; live T-01-43
closure remains contingent on fresh exact-document seal verification.

Collection revision: `7411a33bf63428516a3efee289c393e1a8418b28`;
collection SHA-256 `53ea6a7162902edea4e4372e85b3713ad4092f0522501c33a59115573101337e`;
profile `owned-p01-c14-1`;
source-map SHA-256 `e63834b8585912d81f99e82e2dd9070139fbc8acc25854e23274105d8cad861b`;
manifest SHA-256 `02a276b37a73cc36508801bbb079297cfd3a7dff6014ca9b399fd6a365850560`.
The 39 included identities equal current bytes. All five prior/current collections
remain equal to the Plan 20 committed collection array. All 44 lane build-artifact
identities independently match current files. Metadata-only future rebinding must
preserve these source and collection identities; it is not another behavioral run.

Frozen contract SHA-256
`6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`;
additive amendment content SHA-256
`3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad`;
active candidate identity SHA-256
`27af8df79b55f83bffdef63981defc23984fff6b4e0002d10e99621310340419`.
Runtime SHA-256 `b03d3458c99012e7d20a21b408ea1b5e72ae4fa6ac2f36ac5078d349b0d953b8`
equals the private continuation identity. Input fixture SHA-256
`3a85140f2c50f0958d15b4d028108539a84486016c6931f8304b533f8889a83d`;
owned oracle SHA-256 `c95fe0ed27fe09fdfccde465b494dff14686cfd8f8b39357edc7666dd197961e`;
timing test SHA-256 `606f7c2d2b08c368a65def9b25b0f36eb9122f0e751bd37c9ae5666d5493bbce`;
state test SHA-256 `b8ceb6be17b209f661f5a55699460776f879f78dad8e395c9f973e6502edaae1`.

```json
{
  "schema": 1,
  "independent_non_author": true,
  "hardware_saved_pc": "unknown",
  "evidence_revision": "931e2f07e85a17a9360d74b1b98ed6e1b89e340f",
  "collection_sha256": "53ea6a7162902edea4e4372e85b3713ad4092f0522501c33a59115573101337e",
  "amendment_sha256": "3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad",
  "source_map_sha256": "e63834b8585912d81f99e82e2dd9070139fbc8acc25854e23274105d8cad861b",
  "prior_findings": {
    "F14-01": {
      "disposition": "resolved",
      "evidence": "Exact command/configuration/artifact/output guards retained; independent normal and optimized acceptance regressions pass 21/21 each."
    },
    "F14-02": {
      "disposition": "resolved",
      "evidence": "Shared historical failure guard retained and independently exercised under normal and optimized acceptance tests; five collection prefix preserved."
    },
    "F14-03": {
      "disposition": "superseded",
      "evidence": "Candidate claim only: owner-approved exact 0x4AFC exclusion supersedes disputed supported ILLEGAL behavior via additive P01-C-14. Independent native zero-effect and retained-event controls passed; separate Task 2 non-author ASVS L1/block-high security gate verified zero current candidate high/critical findings. Task 3 confirmed unchanged exact source/collection. Final deferred seal remains required; original-silicon saved PC stays unknown."
    }
  }
}
```

## Reviewer independence:

Independent reviewer: fresh separate non-author agent `/root/phase01_plan21/independent_review`.
Authored runtime/collector/tests: no

Sole repository write ownership is this report; no implementation, tests, receipt,
inventory or ledger changes and no reviewer commit. The project-root pin passed
before writing. The reviewer configured and compiled a new ignored
`build/owned-review21` directory independently; executor-built binaries do not
serve as the independent rebuild. This is an automated agent assessment, not a
human signoff or physical capture.

## Prior findings:

| Finding/observation | Current bounded disposition |
|---|---|
| F14-01 command/configuration receipts | Resolved; exact lane guards and mutation controls pass in both Python modes. |
| F14-02 historical failure guard | Resolved; accepted/deferred paths share historical blockers; failure/unknown/skipped mutations reject. |
| F14-03 canonical ILLEGAL discrepancy | Superseded for the revised candidate claim only following independently passed source/control and Task 2 security gates; exact deferred seal remains the final gate. |
| BL-01 state destination initialization | Resolved; destination is zeroed before fresh creation and restore; independent fresh-owner continuation passes. |
| WR-01 impossible instruction count | Resolved for the reported invariant; mismatch rejection retains destination/bus atomicity. Validator does not prove every record reachable. |
| Restore-over-ready | Remains unclaimed; required fresh-owner path is tested, permissive ready-destination implementation is not promoted. |
| Musashi shifts/division/generator defects | Outside owned runtime closure; historical rejected engine and ten frozen hashes preserved. |
| Optimized assertions / relative path receipts | Explicit exceptions survive optimized Python; current receipts use sanitized root-relative commands. |

Historical sections and former severities/dispositions above are immutable review
history. The separate security assessor supersedes T-01-15-03 for the amended
candidate capability scope only after its independently executed controls. Silicon
uncertainty is retained independently of candidate-scope disposition.

## Evidence runs and denominators:

Reviewer executed on the reviewed source, all exit 0:

- Independent configure: `cmake -S . -B build/owned-review21 -G Ninja -DGLUEYNEO_CPU_EXPERIMENT=OFF -DGLUEYNEO_OWNED_CPU_EXPERIMENT=ON -DCMAKE_BUILD_TYPE=Debug -DGLUEYNEO_OWNED_CPU_OPTIMIZATION=NONE -DGLUEYNEO_OWNED_CPU_SANITIZER=NONE`; `cmake --build build/owned-review21 -j2`, 22 build steps.
- `ctest --test-dir build/owned-review21 -R '^owned_cpu_(timing|unsupported_negative|semantics|state)$' --output-on-failure --no-tests=error`: 4/4. Direct independent binaries: semantics 17/17, timing 25/25, state 5/5 Unity cases, zero failures/ignored.
- Private state: 13 named checkpoints, six continuation calls each (78); original source destroyed and overwritten; 15 invalid records, four null inputs, counter mismatch, active/reentrant and terminal checks preserve destination/bus atomicity.
- `PYTHONDONTWRITEBYTECODE=1 python3 [-O] -m unittest discover -s tests/owned_cpu -p test_contract.py`: 23/23 separately in normal and optimized modes. Amendment omission/order/root/archive/history/hardware-selection mutations and unchanged caps/history/pending gates are exercised.
- Same normal/optimized command for `test_acceptance.py`: 21/21 each. Legacy/current profile, exact named unsupported/continuation controls, stale/duplicate/multiline review and security bindings, command/configuration history guards all execute.
- `python3 -O tools/owned_cpu/acceptance.py self-test`: six rejection and two classification controls; normal self-test also executes inside acceptance tests.
- `python3 tools/owned_cpu/inventory.py check --build-dir build/owned-review21`: 26 owned fields / 10 compiled source files, no mutable runtime globals or callback-owner mutation.
- Required preset targeted CTest command above with `--preset owned-debug`: 4/4, separately labeled execution of collector-built binaries.
- Read-only `acceptance.verify`, `snapshot`, `contract.validate`, strict frozen archive and historical checks: five collections, exact 39-file source snapshot, 44/44 lane artifacts, 10/10 frozen Musashi hashes; 24 contract markers. Budget before reviewer charge: pass, 41,335 seconds / 31 records, runtime churn 1,221 and test/tool churn 6,126; accounting remains executor-owned.

The independent build archive SHA-256 is
`109939880fb7d7e009a496f2645595ebad6de0f60cc74b918991b9d04b3a8552`;
semantics binary `d5bf5f95adddc359fb2426f4cfeacb6ac337533683cbd9d63da6675ad7d537f1`;
timing binary `424471b972fe23810285db29e22a0f84b46f8768ba6be63363e9ab24fd02e31f`;
state binary `6b3b6c0a93e226441bba152a588c96ba057c8cc697de1dcd8e092e47654fc24e`.
Reviewer build is Debug without sanitizers, Apple Clang 21.0.0.21000101, C17,
CMake 4.4.3, Ninja 1.13.2, Darwin arm64. All build output remains ignored.

Plan 20 collection evidence, independently reconciled but not independently
rebuilt in all lanes by this reviewer: Debug, Release/O2, ASan+UBSan and TSan
each 13/13 CTests (52 total), with diagnostic2/semantics17/timing25/isolation4/
faults5/state5 Unity counts, 13 boundaries/78 calls, 32 interleaved pairs,
32 concurrent pairs, 16 fresh cold processes/two instances, six named controls.
Recorded whole-lane build directories were reused; cold process checks are a
different observation. Exact CMake 3.20 and other platforms remain unknown.

## Oracle ancestry:

No new source acquisition or repeated finite search was performed. Reviewed
Plan 17 adjudication remains ambiguous: original-MC68000 silicon saved PC for
exact `4AFC` is unknown. The stronger fault-PC inference (`$100`) combines UM
pre-execution detection, next-unexecuted-PC language and tracing distinction;
it retains the premise that the general rule applies to deliberately encoded
canonical ILLEGAL. The competing sequential-PC inference (`$102`) imports
trap/following-PC selection through UM §6.3.6 group/trap wording and the frozen
specific table. Shared frame structure does not prove identical PC selection,
but rejecting the analogy still requires the reserved interpretive judgment.
Neither inference is selected here.

Reopening requires an applicable original-MC68000 instruction-specific vendor
sentence/correction addressing the analogy, or a legitimately accessible silicon
receipt binding CPU/revision, exact opcode/address, frame bytes, capture method
and oracle ancestry; a reviewed derivation that defeats the competing premise
could also reopen the existing standard. Emulator consensus, derivative manuals,
local fixtures and absence of errata do not settle this question.

Authored arithmetic/store expectations and candidate capability assertions share
project ancestry with implementation; they enforce a declared contract rather
than independently measure silicon. Retained IRQ/privilege/address-error/TRAP/RTE
recipes retain cited manual ancestry and functional bus/timing limits. This
amendment excludes candidate ILLEGAL support; it does not change MC68000 vector4
or claim hardware has no frame.

## Findings and dispositions:

Disposition: clean

No unresolved implementation/evidence finding was reproduced within this bounded
candidate scope. Exact `0x4AFC` succeeds only at opcode fetch, records logical
fault PC/IR and returns unsupported before event preflight. Tests assert exactly
one successful read, no vector4/frame accesses, unchanged observation/memory,
zero dispatch/charge, repeated rejection and odd/inaccessible stack independence.
Prior reset40, IRQ44 and NOP4 retain their completed charges; failed fetch is
terminal host fault, and odd fetch retains address-error handling. Retained
privilege, TRAP/RTE and IRQ controls pass without widening instruction scope.

The core has opaque per-instance state, explicit host bindings, unsigned bounded
arithmetic, defined byte order and checked event counters. No new runtime
dependency, public ABI, ambient I/O/time/network service or mutable global is
introduced. Callback failures retain completed writes and prohibit recursive
exception retry. Fresh restoration stages named fields, rejects invalid records
without bus access, preserves destination bindings and continues real execution.
Same-instance concurrency and cross-build/persistent state remain unsupported.

The amendment pins one additive exclusion, preserves strict archived contract
bytes and every historical reconciliation field, and does not select silicon PC.
Receipt verification is an internal consistency control, not cryptographic proof
against an actor fabricating every identity/result consistently. Candidate
consumer documentation clearly states intentional ILLEGAL incompatibility and
explicit caller recovery. Text scan of all 39 included files found no personal
home paths; provenance retains MIT original work, pinned Unity test-only notices,
and original fixtures without commercial media or manufacturer PDF distribution.

Final recommendation: independent source/control and separate security gates
substantiate the candidate-scope supersession of F14-03/T-01-15-03. The historical
discrepancy and withheld frame mitigation remain preserved; original silicon
saved PC is still unknown. Task 3 independently confirms unchanged identities
at the final revision, with final assessor metadata binding and deferred seal
still required. This does not admit the backend, finish phase verification,
or complete CPU-01–05. The final seal must remain deferred,
unqualified/GAPS_FOUND; Phase 01 is incomplete, Phase 02 gated, and all nine
specless flags remain unresolved.

<!-- owned-cpu-historical-review:end -->

## Historical Plan 01-25 current review (complete prior current section preserved verbatim)


# Plan 01-25 independent review of the repaired candidate

## Reviewed revision:

Final reviewed source revision: `780c720c4e20ac8e9b61eff40da02fbe601a6f38`.
This is the committed Plan 01-25 UAT+README revision. Its inclusion does not
change the collected 39-file source map; exact current source bytes, profile,
collection, map, and amendment were rechecked before this metadata-only rebind.
The native collection remains the executor's earlier collection at
`bd390a7f5f6ede0a69df42f8df1fc98905d171ea`; no reviewer native run is being
rebound or newly claimed here. Final metadata-rebind interval was
`2026-10-04T06:48:27Z`–`2026-10-04T06:50:22Z` (115 active seconds), including
the identity comparison, binding edits, and first final-revision review gate.

Current receipt identity: collection
`cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738`, source-map
`be6e2c45f9590425a227bb9d6622d7629d080cca778eba29d5304bef3bd13a6d`, profile
`owned-p01-c14-continuation-2`, amendment
`3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad`, frozen
contract `6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`,
active candidate identity
`27af8df79b55f83bffdef63981defc23984fff6b4e0002d10e99621310340419`, and
source-manifest SHA-256
`ae481ac75ac88dd40cc86de52fa827a4941280ca3ce6f4e0952c71ecf3a47eab`. The
receipt binds 39 source files and records all four lanes passing 13/13 CTests
each. Those are the executor's lane results; they are distinct from the fresh
reviewer build and tests below. No seal was created by this reviewer. The
receipt remains unqualified, and original-silicon saved PC remains unknown.

## Reviewer independence:

Reviewer: fresh Plan 01-25 non-author agent. I authored none of the runtime,
collector, tests, manifest, collection, or budget ledger. I did not alter those
files and did not commit. The independent build used a separate ignored
`build/owned-review25` directory, not the executor's lane directories. This is
an automated source and regression review, not a human signoff, silicon
measurement, or hardware qualification.

Independent reviewer: fresh separate non-author Plan 01-25 reviewer.
Authored runtime/collector/tests: no

UTC execution interval: `2026-10-04T06:11:57Z` through
`2026-10-04T06:24:44Z`; active effort: 767 seconds. This includes independent
review and report drafting through the provisional review-check pass. Final
metadata-rebind work is separately timed below and must be charged by the
executor.

## Prior findings:

| Finding | Current bounded disposition |
|---|---|
| F14-01 — false-green lane command/configuration receipt | Resolved in the earlier repair/re-review. Current acceptance-control suite passes 22/22 normally and under `-O`; no contradictory lane record was found in the bound six-collection receipt. |
| F14-02 — accepted history could omit a prior failure | Resolved in the earlier repair/re-review. Current acceptance-control suite passes 22/22 normally and under `-O`; the six-collection prefix remains present and unqualified. |
| F14-03 — frozen ILLEGAL saved-PC contract disagreed with the candidate observation | Superseded only for the candidate's exact `0x4AFC` support boundary by P01-C-14. Exact `0x4AFC` is explicitly unsupported and has zero vector/frame side effects. Original-MC68000 saved PC is still unknown under P01-C-13; neither `$100` nor `$102` is selected. |

The complete prior Plan 01-21 current section, including its full F14 history,
all evidence, and limitations, remains in the labelled historical block above.
This crosswalk does not erase its original open disposition or reuse its
historical pass as evidence for the new continuation profile.

## Evidence runs and denominators:

### Independent configure/build and native controls

Plan 01-21's proven configure recipe was repeated in an ignored reviewer-owned
directory, with no more than two build jobs:

```sh
cmake -S . -B build/owned-review25 -G Ninja -DGLUEYNEO_CPU_EXPERIMENT=OFF -DGLUEYNEO_OWNED_CPU_EXPERIMENT=ON -DCMAKE_BUILD_TYPE=Debug -DGLUEYNEO_OWNED_CPU_OPTIMIZATION=NONE -DGLUEYNEO_OWNED_CPU_SANITIZER=NONE
cmake --build build/owned-review25 -j2
ctest --test-dir build/owned-review25 --output-on-failure --no-tests=error
```

Configure passed; the fresh C17 build completed all 22 steps; CTest passed
13/13. The required focused command
`ctest --test-dir build/owned-review25 -R '^owned_cpu_(timing|unsupported_negative|semantics|state)$' --output-on-failure --no-tests=error`
also passed 4/4. Direct reviewer binaries passed diagnostic 2/2, semantics
17/17, timing 25/25, isolation 4/4, faults 5/5, and state 5/5 Unity cases.
The six runner denominators sum to 58/58 Unity assertions/cases, with zero
failures or ignored cases. `owned_cpu_state --continuation-only` passed its
single continuation test and printed exactly 15 named boundaries / 90
continuation calls, with the source owner destroyed and overwritten.

Direct state controls report 15 malformed/incompatible records, four null
inputs, one instruction-counter mismatch, active-operation capture/restore
rejection, and terminal restore rejection. Destination state and bus activity
remain atomic; active/terminal attempts produced zero restore callbacks or
additional callbacks. The full 5/5 state runner also passed. CTest includes
the exact-`0x4AFC` unsupported mutation control and wrong-address-error-cycle
control; the timing suite includes `canonical_unsupported_has_only_opcode_fetch`
and named retained IRQ/TRAP/privilege/address-error/RTE cases.

`python3 tools/owned_cpu/inventory.py check --build-dir build/owned-review25`
passed: 26 owned fields, 10 compiled source files, zero mutable runtime globals,
and zero callback-owner mutations. `contract.py validate` and `contract.py
budget` passed; current totals are 59,690 active seconds, 2,565 diagnostic
seconds, 1,228 runtime-churn lines, and 6,540 test/tool-churn lines, with no
active pause. `acceptance.py verify` passed with six collections, disposition
unqualified, and zero lane blockers. These checks preserve, rather than waive,
the frozen limits.

Fresh Python commands and observed counts:

```sh
python3 -m unittest discover -s tests/owned_cpu -p test_contract.py
python3 -O -m unittest discover -s tests/owned_cpu -p test_contract.py
python3 -m unittest discover -s tests/owned_cpu -p test_acceptance.py
python3 -O -m unittest discover -s tests/owned_cpu -p test_acceptance.py
```

Contract controls passed 27/27 in each mode; acceptance controls passed 22/22
in each mode (49/49 per mode total). CR-02's `test_cumulative_churn_cannot_refund_penultimate_threshold_crossing`,
`test_all_cumulative_churn_categories_reject_decreases`,
`test_equal_and_increasing_cumulative_churn_pass`, and
`test_combined_churn_limits_are_inclusive_and_crossings_require_active_pause`
exercise the original false-green shape and all four added/deleted counters.
WR-01's `test_budget_check_includes_exact_limits_and_rejects_overages_or_pause`
accepts each exact cap and the combined exact caps, rejects each cap-plus-one,
rejects active pause and invalid totals in both interpreter modes.

The first provisional `acceptance.py review-check --review
experiments/owned_cpu/REVIEW.md --revision HEAD` returned `fail` with reason
`review independence not recorded`; the report lacked the parser's required
literal independence metadata. After adding `Independent reviewer:` and
`Authored runtime/collector/tests: no`, the same command passed at revision
`9fba16b864cf74e3b8a9c97047bb27a5db544b59` with status `clean` and report
SHA-256 `a13de062807a4ff62773edb9772f19404cb8f2aba7fd11d2bbfc2b5b39c39740`.
That is preserved as the first repaired provisional pass. After the committed
UAT+README revision, the final report binding is
`780c720c4e20ac8e9b61eff40da02fbe601a6f38`; the exact-source review gate was
rerun after this final metadata edit. The final read-only gate passed `clean`;
its command output and current report SHA are returned to the executor.

A separate temporary-root CR-02 reproduction set a prior cumulative category
above its cap, left the next record below it, and called `validate_budget`.
Each of `runtime_added`, `runtime_deleted`, `test_tool_added`, and
`test_tool_deleted` rejected with `cumulative_decrease` at entry 3 (runtime
crossing 6,001; test/tool crossing 8,001). The actual ledger was not edited.
Separate direct normal and `-O` calls to `acceptance.budget_check` accepted all
three exact caps and rejected all three plus-one values.

### Independent artifact identities

The reviewer build used AppleClang 21.0.0, C17, Debug `-O0 -g`,
`-Wall -Wextra -Werror`, CMake 4.4.3 and Ninja 1.13.2 on Darwin arm64. Sanitizers
were disabled for this independent Debug build. The 22-step configure/build
command and target CTest results above are reviewer-run, not executor receipts.
The fresh archive SHA-256 is
`aa27f496ef8981966b100a1d27a4d3e01c8ac4a3f5140aca5d5da0a3f4b9bda5`; binary
identities are:

| Independent artifact | SHA-256 |
|---|---|
| `owned_cpu_state` | `d22a27af79b47601218f1ff06314afa1a460bb82b2b22ff5020634426d720df0` |
| `owned_cpu_semantics` | `c1084def7a6e73fc365a068b2c2d86d56b289d2c0cdaed88c019d82b0d5dcfab` |
| `owned_cpu_timing` | `eb12b66360b980be406955713f6830598c22528be008381f4898f7f8d1443f08` |
| `owned_cpu_diagnostic` | `7bf2e916c254e0b5b57f2c14785dbb5c1e2fa6ccaf5c4e3295a716cd21e0adb2` |
| `owned_cpu_isolation` | `9d02cd7bbdecc60a17213db0338f623a849277fe7ed23be5aac838de94c74c50` |
| `owned_cpu_faults` | `d6c0abffc2e38bafdefad6f6e6428491d7eccac9d1797424dfdad9faea0233a1` |

The independent build is one Darwin arm64 Debug observation. It does not add
platform support or replace the executor's four-lane results.

## Oracle ancestry:

The diagnostic's 10/16 outputs are from the authored original guest and remain
bounded to the named instruction subset. Exception frame values and timing
expectations cite the Motorola User's Manual; the Programmer's Reference
Manual supports instruction encodings. Callback order is an explicit
functional-bus contract, not a pin trace. Emulator-derived comparisons retain
their documented shared ancestry and do not establish hardware truth. No
original-silicon capture or full-coverage claim was found or inferred.

For the disputed PC question, the existing P01-C-13 record retains the
competing manual readings and the exhausted source-search limit. This review
does not repeat that search, decide a hardware PC value, or use candidate
behavior as hardware evidence.

## Findings and dispositions:

### CR-01 — fixed for private candidate continuation; no silicon claim

The prior reproducer reached a ready boundary after a supported RTE with PC
`$101`, then `state_valid` rejected its capture for alignment. At the reviewed
source, the validator preserves guest-reachable odd addresses and still checks
the SR-selected A7/USP/SSP bank relationship. Fresh guest-derived
`RTE_odd_PC` capture, fresh-owner restore, source destruction/overwrite and
six subsequent calls match the uninterrupted owner: whole run results,
architecture/private state, memory and ordered callbacks. The next odd fetch
enters local vector 3, writes the asserted frame in seven ordered writes,
reads vector `$0c/$0e`, charges 50 clocks and completes zero instructions.
Original silicon's saved PC remains unknown.

`SR_switch_odd_USP` reaches user SR zero with active A7/USP `$2801` and inactive
SSP `$3000`; it can be captured and restored. The actual following privileged
MOVE-to-SR enters vector 8 on the even supervisor stack, costs 34 clocks, and
stores old SR zero / PC `$104`. This fixture does not access the odd USP, and
does not demonstrate an odd-stack address error or host fault. The former
counterexample is fixed at the state-acceptance/continuation boundary without
overstating the next event.

### CR-02 — fixed; cumulative charges cannot decrease

The earlier false-green shape (an over-limit cumulative value followed by a
lower final value) now fails before threshold interpretation. All four
added/deleted counters reject decreases; equal/increasing histories pass. The
unchanged contract still requires an active named pause for an actual crossing.
No entry, frozen charge or cap was rewritten.

### WR-01 — fixed; exact caps inclusive, plus-one blocked

Canonical budget and seal checks now agree at exact values: 115,200 active
seconds, 6,000 runtime added/deleted lines, and 8,000 test/tool added/deleted
lines pass if no active pause is present. Every cap-plus-one, active pause,
invalid type and zero effort case remains rejected. The separate 28,800-second
diagnostic gate remains unchanged and is checked by contract validation.

### WR-02 — fixed at the reviewed source identity

The historical README at the original review revision said that no owned CPU
runtime had been implemented. The current README says the private C17 runtime
and diagnostic subset are implemented but unadmitted; it links the active
subset/contract/amendment/acceptance/review/receipt and names the exact
`0x4AFC` exclusion, unknown original-silicon saved PC, Pending CPU requirements,
open Phase 01 and gated Phase 02. A read-only link scan found 19 Markdown links,
all local and all resolving. It makes no public SDK, game, board, platform, or
performance qualification claim. Its Plan 01-25 “continue” wording describes
the state at this bound Plan 01-24 source revision, where Plan 01-25 was still
pending.

**Independent README recheck after owner update:** the current worktree text
now says Plans 01-22 through 01-25 close later review findings into unqualified,
deferred candidate evidence, and names `$gsd-verify-work 01` as the next GSD
step. It keeps CPU-01–05 Pending, Phase 01 open / GAPS_FOUND, Phase 02 gated,
and the original-silicon saved PC unknown. The stale
`$gsd-execute-phase 01 --gaps-only` resume instruction is absent. A fresh scan
again found 19 Markdown links, all 19 local targets present, zero external links,
and no missing local target; `git diff --check -- README.md` returned success.
This read-only review ran 2026-10-04T06:28:29Z–06:29:40Z (71 active seconds),
at worktree HEAD `9fba16b864cf74e3b8a9c97047bb27a5db544b59` with the README
change uncommitted. It performed no build/test and does not change the
provisional source-revision binding; final rebinding waits for the UAT+README
commit. The later committed revision and metadata-only rebind are recorded in
the final binding section above; the README review outcome and 19-link result
are unchanged.

Disposition: clean

Bounded current review residual: zero unresolved Critical/high findings among
CR-01, CR-02, WR-01 and WR-02. The independent security reassessment and
separate phase-goal verification are distinct gates; this report does not
claim their completion or backend admission. D1-13 and D1-14 remain scoped as
stated below.

### D1-01 through D1-14 decision crosswalk

| Decision | Independent bounded assessment |
|---|---|
| D1-01 | Consistent: runtime is authored C17 and exercised as a private whole-CPU diagnostic slice. No accepted production backend is implied. |
| D1-02 | Consistent: both substantive Musashi attempts, frozen history, charges and original caps remain preserved; no third adaptation, refund or increase is authorized. |
| D1-03 | Consistent: the runtime closure contains authored `cpu.c`; no imported CPU core was adopted. Unity is a pinned test-only dependency. |
| D1-04 | Consistent: C17 and a small dependency tree; no public CPU plugin ABI, loader, C++ engine or generalized backend framework was found. |
| D1-05 | Consistent within the private seam: state and bus/allocator bindings are per instance; fresh destination ownership is retained by restore. |
| D1-06 | Supported for named tests only: equivalent source/baseline and restored owners compare architectural state, whole-event results, memory and callback traces at 15 checkpoints/90 calls. Cross-build restoration is not claimed. |
| D1-07 | Consistent: the whole static owned backend is used; no mixed opcode engine or live state conversion is present. |
| D1-08 | Consistent: selection is build/test scoped; no production runtime selector, shipped backend or accepted integration is asserted. |
| D1-09 | Consistent: exact supported diagnostic/exception subset and explicit unsupported result are documented; exact `0x4AFC` is excluded. |
| D1-10 | Consistent: concrete registers, bus, exceptions, counters and selected instruction forms; no generator, micro-op layer or unprofiled optimization was added. |
| D1-11 | Bounded: cited primary manual rules and authored guest assertions ground named expectations; they do not establish full ISA coverage or original-silicon behavior. |
| D1-12 | Preserved: MAME/Musashi/other emulator agreement remains comparison evidence with ancestry, never hardware truth. |
| D1-13 | Explicit unknown retained: original-MC68000 saved PC for exact `0x4AFC` remains unknown; neither `$100` nor `$102` is selected and the finite search is not repeated. |
| D1-14 | Exact candidate exclusion retained: only numeric opcode `0x4AFC` is unsupported by this decision; its candidate rejection has no vector/frame/dispatch/cycle effect, while other selected exceptions remain tested. This is not a claim that hardware rejects ILLEGAL. |

The evidence supports only this candidate-scoped disposition. CPU-01–05 remain
Pending, Phase 01 remains GAPS_FOUND until its separate verification, Phase 02
is gated, and no SDK admission follows from this report.

```json
{
  "schema": 1,
  "independent_non_author": true,
  "hardware_saved_pc": "unknown",
  "evidence_revision": "780c720c4e20ac8e9b61eff40da02fbe601a6f38",
  "collection_sha256": "cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738",
  "amendment_sha256": "3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad",
  "source_map_sha256": "be6e2c45f9590425a227bb9d6622d7629d080cca778eba29d5304bef3bd13a6d",
  "prior_findings": {
    "F14-01": {
      "disposition": "resolved",
      "evidence": "Earlier non-author regression repair retained; current normal and optimized acceptance controls pass 22/22 and the six-collection record has no lane blocker."
    },
    "F14-02": {
      "disposition": "resolved",
      "evidence": "Earlier shared historical blocker repair retained; current normal and optimized acceptance controls pass 22/22 and collection history remains preserved."
    },
    "F14-03": {
      "disposition": "superseded",
      "evidence": "Only the candidate obligation to support exact 0x4AFC is superseded by P01-C-14; independent timing/state controls retain its zero-vector/frame unsupported result. P01-C-13 original-silicon saved PC remains unknown, and no hardware truth or admission is claimed."
    }
  }
}
```

---

_Reviewed: 2026-10-04T06:24:44Z; final 780c720 metadata rebind completed 2026-10-04T06:50:22Z_
_Reviewer: the agent (Plan 01-25 independent non-author)_
_Depth: deep_

<!-- owned-cpu-current-review:start -->

# Plan 01-27 independent review of the closeout metadata rebind

## Reviewed revision:

Reviewed/evidence revision: `e65ea35fe36a0d9cbcbd2f938142f247f3bbf3e2` (replacement checkpoint C).
This is a metadata/source-identity reconciliation of the unchanged candidate at
the frozen closeout checkpoint. The current source set, collection, profile,
amendment, source map, and frozen contract remain the identities recorded
below. No runtime or collector change is part of this review.

The report-binding delta is limited to the two SECURITY register rows added at
`84dec332adfe5c02f1cbba9a82654077865c77b2`: the 2026-10-04 ASVS scan-count
row and T-01-58 row. The older sealed SECURITY bytes have SHA-256
`a2ffd1aea37e9d5d0b4f31a1c017126127bbe34beded3049658f9673640285c6`; the
pre-repair current SECURITY bytes have SHA-256
`6f435327a7d74c28f6cc1841d66958faf2fe9bea341754c9fb01586af8b20934`.
The earlier validator-pass statement is evidence about its dated report bytes,
not a pass for the changed report. The stale seal and failed current
reproduction remain preserved for the independent security assessor and final
receipt check.

## Reviewer independence:

Independent reviewer: fresh separate non-author Plan 01-27 reviewer and sole
write owner of this report. I authored no runtime, collector, tests, source
manifest, receipt, ledger, or security assessment. This turn performs only
read-only evidence comparison plus this report's metadata rebind. No tests or
native executions were run for this report; dated prior native evidence remains
attributed to the Plan 01-25 report and SUMMARY.

Authored runtime/collector/tests: no

UTC review interval: `2026-10-04T21:23:17Z` through `2026-10-04T21:45:35Z`;
active time: 1338 seconds.

Metadata rebind interval: `2026-10-04T22:42:32Z` through `2026-10-04T22:43:14Z`; active time:
42 seconds. At replacement checkpoint C, the 39/39 source hash comparison
was reconfirmed with zero mismatches; collection and source-map identities are
unchanged.

## Prior findings:

| Finding | Retained disposition |
|---|---|
| F14-01 | Resolved by the earlier regression-backed repair; the Plan 01-25 normal and optimized acceptance-control outcomes remain dated evidence. |
| F14-02 | Resolved by the earlier history-guard repair; the Plan 01-25 normal and optimized acceptance-control outcomes remain dated evidence. |
| F14-03 | Superseded only for the candidate's exact `0x4AFC` support boundary. The original-silicon saved PC remains unknown. |
| CR-01 | Fixed for private candidate continuation only; no silicon claim. |
| CR-02 | Fixed; cumulative charges cannot decrease. |
| WR-01 | Fixed; exact caps are inclusive and plus-one remains blocked. |
| WR-02 | Fixed at the reviewed source identity. |

These statuses are carried forward from the dated Plan 01-25 review. They are
not new behavioral findings or fresh rerun claims.

## Evidence runs and denominators:

This review compared the immutable closeout archive, current derived metadata,
and actual included source bytes. It did not run behavioral tests.

- The six archived payloads in `01-27-CLOSEOUT.json` pass strict base64
  decoding and match their recorded SHA-256 values: 6/6.
- Before this edit, the archived REVIEW bytes matched the current
  Plan 01-25 report exactly (SHA-256
  `e0a4aba91f4a9e21b2c382dbed9b1b74de1cf19484a7a7a45cd69ecd2e797a78`).
  That complete prior current section is retained verbatim as labelled history
  outside the parser markers immediately above this section.
- All six collection objects in the current receipt equal the archived
  pre-repair collection objects: 6/6. The two earlier superseded-seal records
  are unchanged, and the archived former active seal is preserved as the third
  superseded record with its seal object byte-for-byte equal at the JSON-object
  level.
- The prior ledger prefix is unchanged: 45/45 entries match the archived
  prefix; all frozen non-entry ledger fields match. The checkpoint ledger has
  46 entries including the appended closeout charge.
- Every included source hash matches the current working-tree file bytes:
  39/39, zero mismatches. The canonical source-map digest is
  `be6e2c45f9590425a227bb9d6622d7629d080cca778eba29d5304bef3bd13a6d`.
- The collection digest is
  `cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738`;
  profile is `owned-p01-c14-continuation-2`; amendment digest is
  `3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad`.
  Frozen CONTRACT SHA-256 is
  `6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`;
  source-manifest SHA-256 is
  `ae481ac75ac88dd40cc86de52fa827a4941280ca3ce6f4e0952c71ecf3a47eab`.

The previous dated native evidence supports only its recorded diagnostic
subset and continuation profile. This metadata comparison adds no runtime
qualification, hardware observation, or fresh native result. No backend is
admitted.

## Oracle ancestry:

The existing oracle ancestry and its limits are unchanged. Dated Plan 01-25
native observations remain evidence for the named private candidate cases;
they are not new observations and do not establish original-silicon behavior.
Manual wording, emulator comparisons, and project-authored expectations retain
the ancestry and uncertainty recorded in the preserved report.

All nine historical specless flags remain unresolved metadata: CPU-01
concurrency; CPU-02, CPU-03, and CPU-04 unclassified; and CPU-05 boundary,
adjacency, empty, ordering, and precision. They are not treated as passes or
new behavioral predicates.

D1-13 remains unknown for original-silicon saved PC: neither `$100` nor
`$102` is selected, no silicon capture is claimed, and the finite search is
not repeated. D1-14 remains limited to the candidate's exact numeric opcode
`0x4AFC`: the candidate reports unsupported with no vector, frame, dispatch,
or cycle charge. That is not a claim that hardware rejects ILLEGAL.

## Findings and dispositions:

The narrow metadata/source-identity review found no residual mismatch. Threat
T-01-59 is addressed within this scope by preservation of the failed binding,
exact report/source identities, and the unchanged report-binding guard; its
earlier normal and optimized tamper-control results remain dated evidence and
were not rerun here. T-01-60 is addressed within this scope by the 6/6 archive,
6/6 collection, 45/45 ledger-prefix, and 39/39 source comparisons above. The
historical failure remains recoverable, and no admission or phase outcome is
promoted by this report.

CPU-01–05 remain Pending. Phase 01 remains open/GAPS_FOUND, Phase 02 remains
gated, and admission remains deferred. The final security report rebinding and
exact receipt verification remain separate closeout checks.

Disposition: clean

```json
{
  "schema": 1,
  "independent_non_author": true,
  "hardware_saved_pc": "unknown",
  "evidence_revision": "e65ea35fe36a0d9cbcbd2f938142f247f3bbf3e2",
  "collection_sha256": "cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738",
  "amendment_sha256": "3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad",
  "source_map_sha256": "be6e2c45f9590425a227bb9d6622d7629d080cca778eba29d5304bef3bd13a6d",
  "prior_findings": {
    "F14-01": {
      "disposition": "resolved",
      "evidence": "The Plan 01-25 independent report retains its earlier regression-backed resolution; this report did not rerun the controls."
    },
    "F14-02": {
      "disposition": "resolved",
      "evidence": "The Plan 01-25 independent report retains its earlier history-guard resolution; this report did not rerun the controls."
    },
    "F14-03": {
      "disposition": "superseded",
      "evidence": "Only the candidate obligation to support exact 0x4AFC is superseded. Original-silicon saved PC remains unknown, and no hardware truth or admission is claimed."
    }
  }
}
```

---

_Reviewed: 2026-10-04T22:43:14Z_
_Reviewer: fresh non-author Plan 01-27 reviewer_
_Depth: deep metadata/source identity reconciliation_

<!-- owned-cpu-current-review:end -->
