---
phase: "01"
slug: "cpu-acceptance-experiment"
status: blocked
threats_open: 1
asvs_level: 1
created: "2026-10-01"
---

# Phase 01 — Security

> Per-phase security contract for the bounded private CPU acceptance experiment. This is a native-code control review, not a web security certification.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Vendored source to runtime | Candidate and generated CPU code execute with host process privileges | Source files, callbacks, generated code |
| Guest to bus and adapter | Guest addresses and cycle requests reach host-owned memory and resources | Addresses, widths, bounded cycle requests |
| CPU instance to CPU instance | Mutable context and callback state must remain isolated | Registers, callback userdata, state tables |
| Captured state to live destination | Restored guest state must not overwrite host bindings or introduce invalid state | Guest-owned fields and validated state records |
| Evidence to admission | Stale or incomplete results could incorrectly accept a candidate | Source/configuration/input identities, test records, review receipt |
| Local evidence to tracked report | Private machine paths or inputs could leak into tracked artifacts | Paths, rights inventory, source and review receipts |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-01-01 | Tampering | Vendored closure | high | mitigate | Immutable per-file pins and notices; FPU/SoftFloat exclusion; regeneration and injected-violation controls (`tools/cpu/source-manifest.json`, `tests/cpu/test_audit.py`, `acceptance-results.json`) | closed |
| T-01-02 | Elevation | Guest bus | high | mitigate | Checked address/width arithmetic, per-call fault framing, and bad-address survival (`tests/cpu/test_guest.c`, `tests/cpu/test_faults.c`, Plan 01-02 summary) | closed |
| T-01-03 | Denial of service | `cpu_run` | high | mitigate | Bounded requests, finite execution and trace limits, zero-request behavior, terminal host-fault outcome (`tests/cpu/test_timing.c`, `acceptance-results.json`) | closed |
| T-01-04 | Repudiation | Budget ledger | high | mitigate | Frozen baseline, cumulative accounting, exact/over-limit and empty-ledger controls (`experiments/cpu/budget-ledger.json`, `tests/cpu/test_audit.py`, `tests/cpu/test_acceptance.py`) | closed |
| T-01-05 | Tampering | Context/callback/table state | high | mitigate | Complete mutable-state inventory, distinct baselines, mismatch control, and actual TSan cold runs (`experiments/cpu/state-inventory.json`, `tests/cpu/test_inventory.py`, `tests/cpu/test_cold.c`) | closed |
| T-01-06 | Information disclosure | Cross-instance callbacks | high | mitigate | Separate buffers and userdata with ownership comparisons (`tests/cpu/test_isolation.c`, Plan 01-02 summary) | closed |
| T-01-07 | Denial of service | Allocation/fault cleanup | high | mitigate | Fault every construction allocation; bounded fault path and healthy-instance witness; ASan/UBSan evidence (`tests/cpu/test_faults.c`, Plan 01-02 and Plan 01-04 summaries) | closed |
| T-01-08 | Repudiation | Instrumentation receipts | medium | mitigate | Exact identities, nonzero counts, and explicit unsupported/skipped outcomes (`experiments/cpu/acceptance-results.json`, Plan 01-04 summary) | closed |
| T-01-09 | Denial of service | Cycle accounting | high | mitigate | Derived safe maximum, neighboring-budget controls, checked totals, and finite STOP behavior (`tests/cpu/test_timing.c`, Plan 01-03 qualification) | closed |
| T-01-10 | Elevation | Exception handling | high | mitigate | Active per-call fault frames, nested invalid stack/vector survival, and ASan/UBSan evidence (`tests/cpu/test_faults.c`, Plan 01-03 summary) | closed |
| T-01-11 | Tampering | State restore | high | mitigate | Temporary validation followed by atomic application; invalid-restore and pending-field controls (`tests/cpu/test_state.c`, Plan 01-03 qualification) | closed |
| T-01-12 | Information disclosure | State representation | high | mitigate | Guest-only state fields; source-destruction continuation test; host pointer/jump-buffer reconstruction inventory (`tests/cpu/test_state.c`, `tests/cpu/test_inventory.py`) | closed |
| T-01-13 | Spoofing | Evidence identity | high | mitigate | Revision/content/configuration/input matching and stale-evidence negative controls (`tests/cpu/test_acceptance.py`, `experiments/cpu/acceptance-results.json`) | closed |
| T-01-14 | Repudiation | Admission reducer | high | mitigate | Complete denominator, cap/empty/order controls, separate source/runtime evidence, and accepted-only gate (`tests/cpu/test_acceptance.py`, `tools/cpu/acceptance.py`) | closed |
| T-01-15 | Information disclosure | Tracked receipts | high | mitigate | Relative paths, rights inventory, and independent content review (`experiments/cpu/ACCEPTANCE.md`, `experiments/cpu/REVIEW.md`) | closed |
| T-01-16 | Tampering | Self-attested review | high | mitigate | Independent actual-source review tied to the evaluated digest; affected receipts must be refreshed after source changes (`experiments/cpu/REVIEW.md`, `experiments/cpu/acceptance-results.json`) | closed |
| T-01-17 | Spoofing | Evidence source binding | high | mitigate | Current targeted review separates historical scope and binds source/evidence digests (`experiments/cpu/REVIEW.md:23`, `tools/cpu/acceptance.py:125`) | closed |
| T-01-18 | Tampering | Contract freeze | high | mitigate | Preserved archive hashes and frozen history/accounting checks (`tools/owned_cpu/contract.py:100,208`) | closed |
| T-01-19 | Repudiation | Admission blockers | high | mitigate | Blocking findings and pending phase gates are rejected (`tools/cpu/acceptance.py:139`, `tools/owned_cpu/contract.py:146`) | closed |
| T-01-20 | Elevation | Authorization and accounting | high | mitigate | `01-06-DIRECTION.md` preserves consumed attempts and bounds the authorized next step | closed |
| T-01-21 | Elevation | Developer direction | high | mitigate | `01-06-DIRECTION.md` records the selected C checkpoint and limits authorization to discussion/planning | closed |
| T-01-22 | Repudiation | Decision record | medium | mitigate | `01-06-DIRECTION.md` records selected status, actual direction, unchanged charges/caps, and no backend acceptance | closed |
| T-01-07-01 | Tampering | Historical accounting | high | mitigate | Frozen history and summed effort checks plus reverted-churn regression (`tools/owned_cpu/contract.py:100,208`, `tests/owned_cpu/test_contract.py:186`) | closed |
| T-01-07-02 | Repudiation | Validation result | high | mitigate | Named negative controls/nonempty denominators and normal/optimized-mode regressions (`tools/owned_cpu/contract.py:554`, `tests/owned_cpu/test_contract.py:232`) | closed |
| T-01-07-03 | Denial of service | Implementation scope | medium | mitigate | Effort/churn limits and pause gates (`tools/owned_cpu/contract.py:208,415`) | closed |
| T-01-07-04 | Spoofing | Oracle ancestry | medium | mitigate | Primary-source mappings and shared-emulator ancestry limits (`experiments/owned_cpu/CONTRACT.md`, `tests/owned_cpu/ORACLE.md`) | closed |
| T-01-08-01 | Denial of service | Decode and arithmetic | high | mitigate | Exact decode, defined unsigned operations, explicit unsupported outcomes, bounded requests (`experiments/owned_cpu/cpu.c:290,638`) | closed |
| T-01-08-02 | Tampering | Bus writes | high | mitigate | Physical address masking and ordered partial writes with failure/wrap regressions (`experiments/owned_cpu/cpu.c:62,77,155`, `tests/owned_cpu/test_semantics.c:414,431`) | closed |
| T-01-08-03 | Spoofing | Positive evidence | high | mitigate | Guest effects, wrong-operand control, and collection identity/count checks (`tests/owned_cpu/test_diagnostic.c:128,187,191`, `tests/owned_cpu/negative.py`) | closed |
| T-01-08-04 | Elevation | Guest STOP/SR | medium | mitigate | Supervisor checks and privilege exception assertions (`experiments/owned_cpu/cpu.c`, `tests/owned_cpu/test_timing.c:520`) | closed |
| T-01-09-01 | Denial of service | Exception recursion/run | high | mitigate | Checked counters, terminal failed exception entry, bounded execution, finite CTest timeouts (`experiments/owned_cpu/cpu.c:112,186,638`, `experiments/owned_cpu/CMakeLists.txt:128`) | closed |
| T-01-09-02 | Tampering | Frame and bus | high | mitigate | Frame contents, saved PCs, addresses, and bus ordering assertions with primary-source mapping (`tests/owned_cpu/test_timing.c:207,309,351,371`, `tests/owned_cpu/ORACLE.md`) | closed |
| T-01-09-03 | Elevation | SR/STOP/RTE | high | mitigate | Stack-bank switching and privilege/SR/RTE assertions (`experiments/owned_cpu/cpu.c:97`, `tests/owned_cpu/test_timing.c:520,685,703`) | closed |
| T-01-09-04 | Spoofing | Timing evidence | medium | mitigate | Separate event counts and named timing control (`experiments/owned_cpu/cpu.c:638`, `tests/owned_cpu/test_timing.c:675`, `tests/owned_cpu/negative_timing.py`) | closed |
| T-01-10-01 | Information disclosure | Shared instance state | high | mitigate | Distinct owners, swapped-owner control, concurrent instances, cold creation (`tests/owned_cpu/test_isolation.c:14,35,46,74`, `tests/owned_cpu/test_cold.c:11`) | closed |
| T-01-10-02 | Denial of service | Callback/allocator failure | high | mitigate | Allocation failures, callback reentry rejection, and terminal fetch/store/stack/vector faults (`tests/owned_cpu/test_faults.c:11,71,90,180`) | closed |
| T-01-10-03 | Tampering | Mutable inventory | high | mitigate | State/global/hash/ownership inventory and corruption controls (`tools/owned_cpu/inventory.py:460`, `tests/owned_cpu/test_inventory.py:23,56,62,67`) | closed |
| T-01-10-04 | Repudiation | Sanitizer result | medium | mitigate | Object/linker instrumentation and distinct unsupported/unknown outcomes (`tools/owned_cpu/inventory.py:382`, `tools/owned_cpu/acceptance.py:154,294`) | closed |
| T-01-11-01 | Tampering | Restore | high | mitigate | Named fields staged and validated before live mutation; atomic rejection assertions (`experiments/owned_cpu/cpu.c:927`, `tests/owned_cpu/test_state.c:485,531`) | closed |
| T-01-11-02 | Information disclosure | Guest record | high | mitigate | Guest fields copied without host bindings; source-destruction continuation (`experiments/owned_cpu/cpu.c:800,927`, `tests/owned_cpu/test_state.c:372`) | closed |
| T-01-11-03 | Spoofing | State completeness | high | mitigate | Complete source-bound field inventory and omitted-state controls (`tools/owned_cpu/inventory.py:216,249,460`, `tests/owned_cpu/test_state.c:641,645`) | closed |
| T-01-11-04 | Denial of service | Invalid transient state | medium | mitigate | Impossible/active/terminal states rejected without callbacks (`experiments/owned_cpu/cpu.c:882,914,927`, `tests/owned_cpu/test_state.c:591,615`) | closed |
| T-01-12-01 | Tampering | CPU state/bus | high | mitigate | Boundary regressions and sanitizer compilation (`tests/owned_cpu/test_semantics.c:414,431,448`, `tests/owned_cpu/test_timing.c:729,752`, `experiments/owned_cpu/CMakeLists.txt:117`) | closed |
| T-01-12-02 | Spoofing | Positive evidence | high | mitigate | Exact revision, independent authorship, oracle ancestry, and source snapshot checks (`experiments/owned_cpu/REVIEW.md:3,19,84`, `tools/owned_cpu/acceptance.py:88,327`) | closed |
| T-01-12-03 | Denial of service | Guest/callback paths | high | mitigate | Bounded calls, explicit failure states, host-survival cases (`experiments/owned_cpu/cpu.c:638`, `tests/owned_cpu/test_faults.c:180`) | closed |
| T-01-12-04 | Repudiation | Review/budget | medium | mitigate | Prior findings retained; effort summed and charges appended (`experiments/owned_cpu/REVIEW.md:28`, `tools/owned_cpu/contract.py:208,467`) | closed |
| T-01-13-01 | Tampering | Evidence and source digests | high | mitigate | Collection/output/source identities and corruption/overwritten-failure regressions (`tools/owned_cpu/acceptance.py:294`, `tests/owned_cpu/test_acceptance.py:79,105,144,151`) | closed |
| T-01-13-02 | Spoofing | Test counts | high | mitigate | Nonzero counts, timeout/error as unknown, optimized-mode controls (`tools/owned_cpu/acceptance.py:62,125`, `tests/owned_cpu/test_acceptance.py:167,191`) | closed |
| T-01-13-03 | Information disclosure | Public paths/assets | high | mitigate | Path sanitization and licensed distribution closure (`tools/owned_cpu/acceptance.py:54`, `tools/owned_cpu/inventory.py:90,112`) | closed |
| T-01-13-04 | Repudiation | Accounting | medium | mitigate | Charges append-only; failed/unknown collections remain blockers (`tools/owned_cpu/contract.py:467`, `tools/owned_cpu/acceptance.py:187,333,360`) | closed |
| T-01-14-01 | Tampering | Evidence and source digests | high | mitigate | Immutable collection digests/current snapshots and append-only collections (`tools/owned_cpu/acceptance.py:257,294,327`) | closed |
| T-01-14-02 | Spoofing | Test/review sign-off | high | mitigate | Denominators, revision, and independent review checks (`tools/owned_cpu/acceptance.py:125,273`, `experiments/owned_cpu/REVIEW.md:23`) | closed |
| T-01-14-03 | Information disclosure | Public paths/assets | high | mitigate | Path sanitization, distribution closure, and pinned notices (`tools/owned_cpu/acceptance.py:54`, `tools/owned_cpu/inventory.py:112`) | closed |
| T-01-14-04 | Repudiation | Final decision | medium | mitigate | Unqualified seal on blockers, preserved counterexamples, append-only accounting (`tools/owned_cpu/acceptance.py:345`, `experiments/owned_cpu/REVIEW.md:28`, `tools/owned_cpu/contract.py`) | closed |
| T-01-15-01 | Spoofing | Primary-source interpretation | high | mitigate | Exact manual hashes/pages/applicability and independent unresolved challenge (`experiments/owned_cpu/illegal-reconciliation.json`, `experiments/owned_cpu/REVIEW.md:84,114`) | closed |
| T-01-15-02 | Tampering | Contract and ledger | high | mitigate | Frozen-root/history checks and tamper/accounting regressions; no contract revision occurred (`tools/owned_cpu/contract.py:208`, `tests/owned_cpu/test_contract.py:46,62,186`) | closed |
| T-01-15-03 | Elevation | ILLEGAL frame writes | high | mitigate | Planned narrow dispatch repair and direct frame/bus assertions are withheld; `cpu.c:479` still stacks `instruction_pc`, and `test_timing.c:264-276` retains only the old `$100` assertion. Fresh lanes do not implement this mitigation (`experiments/owned_cpu/REVIEW.md:63,114`) | open |
| T-01-15-04 | Repudiation | Intermediate source identities | high | mitigate | Preceding hashes/handoff and independent exact-final binding (`experiments/owned_cpu/illegal-reconciliation.json:220,273`, `experiments/owned_cpu/REVIEW.md:5`) | closed |
| T-01-15-05 | Information disclosure | Downloaded sources/evidence | medium | mitigate | Distribution bounds, sanitized paths, original summaries/hashes only (`tools/owned_cpu/inventory.py:74,112`, `tools/owned_cpu/acceptance.py:54`) | closed |
| T-01-15-06 | Denial of service | Qualification/resource gates | medium | mitigate | Finite test/collector timeouts, budget and pause gates (`experiments/owned_cpu/CMakeLists.txt:128`, `tools/owned_cpu/acceptance.py:58`, `tools/owned_cpu/contract.py:208,415`) | closed |
| T-01-15-07 | Tampering | Dependency closure | low | accept | No new package/runtime dependency; existing Unity pin and notices preserved | closed |
| T-01-16-01 | Spoofing | Saved-PC authority/reviewer | high | mitigate | Independent primary-source review and exact-final rebinding; unresolved interpretation is explicit (`experiments/owned_cpu/REVIEW.md:5,19,84,114`) | closed |
| T-01-16-02 | Tampering | State/source identities and receipt history | high | mitigate | Collection history and current snapshot verified; four fresh collections remain unqualified (`tools/owned_cpu/acceptance.py:294,327`) | closed |
| T-01-16-03 | Repudiation | Final revision/collection/review/accounting | high | mitigate | Review-only ownership, final handoff binding, append-only effort (`experiments/owned_cpu/REVIEW.md:5,23`, `tools/owned_cpu/contract.py:208,467`) | closed |
| T-01-16-04 | Elevation | Native exception path qualification | high | mitigate | Fresh ASan+UBSan qualification and fault/continuation/isolation coverage; this does not close T-01-15-03 (`tools/owned_cpu/inventory.py:382`, final collection) | closed |
| T-01-16-05 | Information disclosure | Distributed evidence/report | medium | mitigate | Distribution closure, sanitized paths, public-safe provenance (`tools/owned_cpu/inventory.py:74,112`, `tools/owned_cpu/acceptance.py:54`) | closed |
| T-01-16-06 | Denial of service | Lane collection/resource gates | medium | mitigate | Finite execution, budget/pause enforcement; budget check reports no pause (`experiments/owned_cpu/CMakeLists.txt:128`, `tools/owned_cpu/acceptance.py:58`, `tools/owned_cpu/contract.py:208,415`) | closed |
| T-01-16-07 | Tampering | Dependency closure | low | accept | No package install or new runtime dependency; existing Unity pin and notices preserved | closed |

## Audit Result

The read-only ASVS L1 audit verified 67 of 68 declared controls. T-01-15-03 remains HIGH/open because the declared ILLEGAL frame repair and direct assertions were withheld while the saved-PC interpretation remains unresolved. The two LOW dependency-closure risks were accepted in their plans and are now recorded above. This audit did not rerun native tests and does not establish CPU acceptance or phase completion; Phase 01 remains GAPS_FOUND and Phase 02 remains gated.

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-01-15-07 | T-01-15-07 | No new runtime dependency or package install is introduced; existing pinned test-only Unity dependency and notices remain in force. | User, following Plan 01-15 disposition | 2026-10-03 |
| R-01-16-07 | T-01-16-07 | No new package install or runtime dependency is introduced; existing pinned test-only Unity dependency and notices remain in force. | User, following Plan 01-16 disposition | 2026-10-03 |

Same-instance callback reentry remains unsupported by contract; guards specifically reject capture/restore during callbacks, without claiming comprehensive callback-reentry support. Hardware-wide compatibility, guest bus-error frames, arbitrary bus-cycle suspension, distinct compiler toolchains, and release-platform support also remain explicitly unqualified. These are outside the bounded experiment's claims, not accepted mitigations or evidence of support.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-01 | 16 | 16 | 0 | `gsd-security-auditor` (read-only cross-check) |
| 2026-10-03 | 68 | 67 | 1 | `gsd-security-auditor` (ASVS L1; block_on high) |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [ ] `threats_open: 0` confirmed — T-01-15-03 remains HIGH/open
- [ ] `status: verified` set in frontmatter — status is blocked pending mitigation

**Approval:** blocked 2026-10-03; resolve the declared ILLEGAL frame mitigation, then rerun `$gsd-secure-phase 01`.

<!-- owned-cpu-current-security:start -->
## P01-C-14 reassessment — 2026-10-03

Evidence revision: `635714631770a6450e1f2e46bef6a377571aabd5`.
Independent assessor: separate non-author agent `/root/phase01_plan21/security_assessor`.
Authored runtime/collector/tests/receipts/ledger: no. Sole write ownership is
this report and the appended validation audit; executor owns accounting and
commits. Git root was checked before writing. This is an applicable native
C/evidence ASVS L1 assessment with block_on high, not web certification.

```json
{
  "schema": 1,
  "asvs_level": 1,
  "block_on": "high",
  "independent_non_author": true,
  "status": "blocked",
  "open_high_or_critical": 1,
  "evidence_revision": "635714631770a6450e1f2e46bef6a377571aabd5",
  "collection_sha256": "53ea6a7162902edea4e4372e85b3713ad4092f0522501c33a59115573101337e",
  "amendment_sha256": "3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad",
  "source_map_sha256": "e63834b8585912d81f99e82e2dd9070139fbc8acc25854e23274105d8cad861b"
}
```

### Historical mitigation and current candidate scope

The original T-01-15-03 frame repair was withheld. Its HIGH/open register row,
former blocked frontmatter, audits and approval above remain historical; this
assessment does not claim that repair or its proposed wrong-PC control ran.
P01-C-13/D1-13 preserves original-MC68000 saved PC as unknown. Separately
authorized P01-C-14/D1-14 removes exact vector-4 dispatch for `0x4AFC` from the
candidate's qualified capabilities. `cpu.c:479` returns unsupported after the
successful opcode fetch and before exception preflight/frame/vector access.
The strict additive amendment pins that single exclusion while preserving the
original CONTRACT, archive, all earlier reconciliation fields and frozen caps.

T-01-15-03's candidate-scope disposition is superseded by this evidenced
capability mitigation. F14-03 is eligible for candidate-claim reconciliation;
final closeout remains conditional on Task 3's exact report/source/budget seal.
Neither disposition resolves hardware truth or admits a backend. The independent
Task 1 review passes against `a3cec086a75c3c7783bcde610f6e8c4234354eeb`;
the Task 1 commit changes only derived review/accounting metadata. Every one
of the 39 included source inputs is identical at that review revision, this
assessment revision and collected source `7411a33bf63428516a3efee289c393e1a8418b28`.
Task 3 must rebind both independent reports to its final exact revision.

Task 3 metadata rebinding: independently confirmed at
`635714631770a6450e1f2e46bef6a377571aabd5` that all39 included inputs equal
the committed bytes and current collection source map, with the same collection
and amendment identities. The Task2 commit changed reports/accounting only.
The attestation revision above is rebound to that exact closure; this does not
invent another native/sanitizer execution or resolve silicon evidence. Final
live seal/accounting controls were subsequently verified below.

### Reassessment threat crosswalk

All rows use disposition mitigate. CLOSED means present and concretely checked
in the stated candidate scope; a pending live closeout is identified separately.

| Threat | Severity | Current control evidence | Outcome |
|---|---|---|---|
| T-01-15-03 | high | Exact unsupported PC/IR, no frame/vector/dispatch/charge, odd/inaccessible stack and repeated-call assertions in `test_timing.c:264`; independently run timing25 and state5 | SUPERSEDED for candidate claim; original mitigation withheld, hardware unknown |
| T-01-29 | high | `cpu.c:479`, timing opcode-only bus and memory/register equality; reset40/IRQ44/NOP4 accounting; terminal failed fetch | CLOSED |
| T-01-30 | high | `contract.py:193` strict root/archive/history and one authorized amendment; omission/order/content/broadening/hardware-selection mutations, contract23 normal and optimized | CLOSED |
| T-01-31 | high | Unchanged four old collections, 21 old ledger entries/14 non-entry fields against pre-amendment baseline; five preplan collections/31 entries; Plan17/frozen CONTRACT five files; ten Musashi hashes; summed budget | CLOSED |
| T-01-32 | high | SUBSET/ORACLE/ACCEPTANCE dated P01-C-14 supersession, immutable Plan17 unknown evidence and hardware-selection rejection regression | CLOSED |
| T-01-33 | high | `test_state.c:397` fresh destination, source destruction/overwrite, all13 boundaries/78 calls, destination callbacks/memory equality; inventory26 fields | CLOSED |
| T-01-34 | high | `negative_timing.py` exact unsupported-status classifier: one test/one intended failure/zero ignored, finite20s timeout; wrapper2 adversarial methods and native child | CLOSED |
| T-01-35 | high | `acceptance.py:419` explicit legacy/current profile, pinned amendment and six current controls; rehashed spoof/history/configuration mutations, acceptance21 in both modes | CLOSED |
| T-01-36 | high | Unique bounded review/security JSON, exact identities, historical finding crosswalk, multiline blocker and Boolean numeric rejection; synthetic deferred seal never admits | CLOSED |
| T-01-37 | high | Snapshot39 equals collected/committed inputs; all44 actual lane artifact hashes equal receipts; compiler/configuration/input identities and nonempty native/control counts | CLOSED |
| T-01-38 | high | Immutable collection prefix; inventory compiled-source/archive/object/link checks; four recorded native lanes13/13 each, strict fail/unknown/skipped/history controls | CLOSED |
| T-01-39 | medium | Source-manifest MIT original work and pinned Unity notices, original fixture ancestry; all39 included text inputs scanned for personal home paths; sanitized receipt commands/outputs | CLOSED |
| T-01-40 | high | Append-only explicit agent interval sums and failed/reverted churn, frozen limits and unqualified/GAPS_FOUND receipt | CLOSED |
| T-01-41 | high | Separate REVIEW-only non-author reviewer, independent Debug build22 steps and direct native4/4; exact clean review-check passed against its recorded revision | CLOSED |
| T-01-42 | high | Separate assessor, source/controls independently read/run, this evidence-bound high-blocking native reassessment and unchanged historical reports | CLOSED |
| T-01-43 | high | Initial deferred seal passed; audit metadata then changed; actual final receipt verify fails with stale sealed security document; reseal preflight rejects the existing stale receipt | HIGH/open final binding; initial pass retained below |
| T-01-44 | high | Frozen summed budget, contract pending requirement/phase gate checks; actual seal unqualified/GAPS_FOUND with only phase-goal-verification-pending and budget44,170s/34 records below frozen caps | CLOSED; live Task3 gate passed |

### Assessor-executed evidence

All commands below exited zero. Native commands use the executor/collector-built
Debug binaries; this assessor did not rebuild or rerun the four full lanes.
The separate reviewer did independently build its Debug target. Collection
observations are reconciled evidence, not assessor-run sanitizer claims.

```sh
python3 -m unittest discover -s tests/owned_cpu -p test_contract.py
python3 -O -m unittest discover -s tests/owned_cpu -p test_contract.py
python3 -m unittest discover -s tests/owned_cpu -p test_acceptance.py
python3 -O -m unittest discover -s tests/owned_cpu -p test_acceptance.py
ctest --preset owned-debug -R '^owned_cpu_(timing|unsupported_negative|semantics|state|faults|isolation|cold_processes|state_negative|timing_negative|isolation_negative|diagnostic_negative)$' --output-on-failure --no-tests=error
ctest --preset owned-debug -R '^owned_cpu_(negative|cold)$' --output-on-failure --no-tests=error
build/owned-debug/experiments/owned_cpu/owned_cpu_timing
build/owned-debug/experiments/owned_cpu/owned_cpu_state
python3 tests/owned_cpu/negative_timing.py --unsupported build/owned-debug/experiments/owned_cpu/owned_cpu_timing
python3 tests/owned_cpu/negative_timing.py --self-test
python3 tools/owned_cpu/contract.py validate
python3 tools/owned_cpu/acceptance.py verify
python3 tools/owned_cpu/inventory.py check --build-dir build/owned-debug
python3 tools/owned_cpu/contract.py budget
python3 tools/owned_cpu/acceptance.py review-check --review experiments/owned_cpu/REVIEW.md --revision a3cec086a75c3c7783bcde610f6e8c4234354eeb
```

Contract23/23 in each Python mode; acceptance21/21 in each mode (88 total
method executions). Targeted CTest8/8 plus negative/cold2/2. The first regex
contains unmatched names; only the eight listed actual CTests count. Timing25
and state5 Unity cases, zero failures/ignored; state13 boundaries/78 calls,
15 invalid records/four null inputs, atomic mismatch/active/terminal rejection.
Wrapper2/2 methods reject duplicate/foreign output, wrong numeric suffix/name,
empty/crash/pass/timeout and altered denominators. Its printed FAIL strings
are deliberate rejected classifier inputs; they are not native acceptance passes.
The direct negative child exits1 with exactly its intended status assertion;
the wrapper exits0. Diagnostic negative adds three controls, isolation negative
one, timing negative one, canonical unsupported negative one: six total.

Read-only Python comparisons additionally verified current snapshot39,
all44 recorded lane artifacts, four pre-amendment/five preplan collection
prefixes, preplan31 ledger entries, original reconciliation fields, five frozen
CONTRACT/Plan17 files and no personal-home-path matches in39 included files.
`contract.validate` separately proves ten frozen Musashi hashes and strict
archived CONTRACT equality. `inventory.check` proves26 owned fields/10 compiled
sources, runtime mutable globals0 and callback owner mutation0. The exact
comparison baseline/conditions are reproduced in Plan20 SUMMARY; current
source/artifact comparisons use `acceptance.snapshot()` and each lane's
`artifacts` SHA-256 map against actual bytes, not only printed receipt hashes.

Observed budget before this assessor's executor-owned charge: records32,
active42,147 seconds, diagnostic2,565, runtime churn1,221, test/tool churn6,126.
Caps remain115,200/28,800 seconds and6,000/8,000 churn; no pause. No dependency,
public ABI, state format, network/auth endpoint or runtime ambient I/O was added.
Runtime uses explicit host callbacks and per-instance ownership; fault cleanup,
terminal exception failures, finite event accounting and restore validation are
retained and directly tested. Evidence hash guards prove internal consistency,
not independence from a fully malicious fabricated producer.

### Current result and remaining limits

Initial assessment verified zero candidate high/critical findings. Sixteen new declared
controls plus the original T-01-15-03 candidate reassessment are substantiated;
the older67 closed controls and historical one-open audit remain unchanged.
Task3 initial live seal/accounting passed as recorded below; final binding later
failed and current status is blocked with one HIGH/open threat. Original silicon
saved PC, functional-versus-pin timing, other platforms/CMake3.20 execution,
full ISA, BIOS/games, public ABI and durable/cross-build continuation remain
unknown/excluded. No physical evidence or finite silicon search was acquired
or repeated. All nine specless flags remain unresolved. CPU-01–05 stay Pending,
Phase01 open/GAPS_FOUND, Phase02 gated. This current native assessment supersedes
the former blocked candidate disposition only within P01-C-14's changed scope.

### Initial live closeout confirmation — historical observation

Executor ran the exact Task3 review-check/seal/verify/budget chain against
`635714631770a6450e1f2e46bef6a377571aabd5`. The assessor independently ran
`python3 tools/owned_cpu/acceptance.py verify`, `python3 tools/owned_cpu/contract.py budget`
and read-only equality checks on the actual seal/revision/current snapshot and
`security_check` result. All passed: five collections, no lane blockers,
defer_admission true, unqualified/GAPS_FOUND and exactly
`["phase-goal-verification-pending"]`. The rebound clean independent review
SHA-256 is `774e70d2afd0c840847e599bad85cec41c5f8f9e8b1a493e42be2ec38b9645ff`.
Final charged budget is44,170 active seconds/34 records, diagnostic2,565,
runtime churn1,221 and test/tool churn6,126; no cap change or pause. Source39,
current collection/amendment/map identities and historical prefixes remain
unchanged. Candidate-scope F14-03/T-01-15-03 reconciliation is substantiated;
their former disputed frame mitigation did not run and silicon remains unknown.

This appended outcome changes only audit metadata. The executor must reseal
the final audit-document hash and rerun read-only verification; an earlier seal
cannot authorize changed audit bytes. The evidence revision and all source/
collection/amendment identities stay fixed at the audited closure above.

### Final binding gate failure — current disposition

At `33c2f480bd19f7008723ef9e6523284cf9b622f4`, the assessor independently
reproduced `python3 tools/owned_cpu/acceptance.py verify`: nonzero outcome,
`{"status": "fail", "reason": "stale sealed security document"}`. The initial
seal at6357146 bound the prior audit document; the subsequent appended live
outcome changed its bytes. `acceptance.seal` calls `verify(document)` before
resealing, so a second seal cannot refresh this changed document through the
current implementation. The Task3 commit contains that stale receipt. Earlier
native/qualification controls and the initial exact seal pass remain actual
historical observations; they do not establish final binding.

T-01-43 is HIGH/open for missing reproducible final report/receipt binding.
Current schema attestation is blocked with open_high_or_critical1. T-01-44
budget/pending-admission controls remain evidenced; clean final closeout and
F14-03/T-01-15-03 final candidate registry reconciliation are withheld until
the binding gate is repaired and independently reverified. The changed
capability mitigation remains supported; its original withheld frame repair
and unknown silicon saved PC have not changed. No backend, requirement or
phase admission is permitted. No code, receipt or accounting was modified by
the assessor. Preserve this reproducer in gap planning and refresh affected
review/security bindings only after a separately owned bounded repair.
<!-- owned-cpu-current-security:end -->
