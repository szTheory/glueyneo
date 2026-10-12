---
phase: 01-cpu-acceptance-experiment
reviewed: 2026-10-05
depth: deep
files_reviewed: 8
files_reviewed_list:
  - experiments/owned_cpu/cpu.c
  - experiments/owned_cpu/CMakeLists.txt
  - tools/owned_cpu/contract.py
  - tools/workflow/phase01_admission.py
  - tests/owned_cpu/test_isolation.c
  - tests/owned_cpu/test_faults.c
  - tests/owned_cpu/test_state.c
  - tests/owned_cpu/cold.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
assessment: accept_recommended
---

# Plan 01-29 independent CPU admission assessment

Assessment checkpoint: `4945f348cf67777f3f90f87ef8331250a2c7add9`.
Reviewer: `/root/admission_review`, independent of runtime, checker and decision authors.
Ownership is limited to this report. No runtime, old receipt, old review, ledger or source-manifest edits were made.

## Narrative Findings (AI reviewer)

### WR-01 — WARNING — Privilege continuation documentation invents an extension fetch

**Files:** `experiments/owned_cpu/ACCEPTANCE.md:94`, `tests/owned_cpu/ORACLE.md:43`.
**Source:** `experiments/owned_cpu/cpu.c:499`–`527`; `tests/owned_cpu/test_state.c:452` onward.

Both prose descriptions state that the user-mode MOVE-to-SR at PC $104 reads its immediate at $106 before privilege entry. The current source tests supervisor mode immediately after opcode fetch and enters vector 8 before the extension-fetch branch. The continuation fixture checks owner equivalence, frame values and event duration; it does not independently assert an extension read. Repeating that sentence as an observed trace would overstate the evidence.

**Correction and disposition:** For this admission assessment the current candidate functional sequence is opcode read $104, PC-high/PC-low/SR writes $2ffc/$2ffe/$2ffa, then vector reads $20/$22; no $106 read occurs. This statement supersedes only those two prose trace sentences for this report's recommendation. It adds no silicon claim and changes no immutable source, collection, oracle or receipt bytes. Future canonical documentation should carry that correction when those source-bound documents are deliberately revised. No runtime repair is indicated by this finding. The 15/90 continuation comparison, SR/stack preservation and 34-clock privilege event remain applicable; absolute extension-prefetch behavior was never qualified.

## Summary and requirement judgment

The current recorded experiment supplies sufficient evidence for a **bounded candidate admission recommendation**, conditional on executor closeout preservation/accounting and the separate whole-phase verifier. This report itself admits no backend, completes no CPU requirement and opens no Phase 02 gate.

The assessment re-read current runtime behavior and its caller/test seams, challenged metadata-only admission, baseline correlation, host ownership, timing precision, private continuation reachability, licensing closure and refund/threshold cases. The code uses a single authored C17 runtime translation unit; persistent CPU fields are per-instance, bus and allocator callbacks are explicit, and event counters are checked before committed event effects. Unsupported encodings report a distinct outcome. Host callback failure preserves completed partial writes and becomes terminal until reset. Same-instance overlap remains forbidden.

| Requirement | Judgment | Concrete basis and limit |
|---|---|---|
| CPU-01 | sufficient | 38-row rights/compile/distribution inventory; 39 current source hashes; one authored runtime C source; Unity stays pinned and test-only. Only recorded native toolchain is exercised. |
| CPU-02 | sufficient | Distinguishable original guest results, 32 interleaved + 32 concurrent cold pairs, six compared boundaries and 16 fresh processes per lane; five fault-suite tests include seven callback failpoints, reentry and allocation cleanup. Compliant independent owners only. |
| CPU-03 | sufficient | 2 diagnostic, 17 semantic and 25 timing/exception cases per lane; bounded progress, event overshoot, IRQ/privilege/address error and exact unsupported outcome. Manual-derived architectural/event expectations and owner-defined functional bus policy have distinct ancestry. WR-01 corrects the specific nonqualifying trace sentence. |
| CPU-04 | sufficient | 26 instance fields plus transient/callback audit; 15 checkpoint / 90 call fresh-owner continuation, source destruction and complete observable comparisons. Private accessible same-build record and caller-cloned memory only. |
| CPU-05 | sufficient | Preimplementation frozen caps, retained failed history and reproducible monotonic accounting; current budget check passes. Final additive all-agent charges and preservation validation remain required before recommendation freeze. |

All four recorded current-profile lanes are pass: debug, release, ASan+UBSan and TSan. Each records 13 expected/observed CTest tests, six consequential negative controls and the same named denominators. I inspected their stored commands, configuration identities, exits and counts; **I did not rerun native lanes or recollect evidence**. These are observations dated 2026-10-04 at recorded source revision `bd390a7f5f6ede0a69df42f8df1fc98905d171ea`, not execution at the assessment checkpoint. Exact source hashes bridge that identity; no shared ancestry is upgraded to hardware truth.

Fresh read-only checks in this assessment: `candidate_identity(Path.cwd())` passed and rehashed the 39 included source paths with the exact manifest/collection/report chain; `python3 tools/owned_cpu/contract.py budget` exited 0 with 47 records and 79,763 active / 2,565 diagnostic seconds, 1,228 runtime / 6,540 tool-test churn. The executor's reported `pending_gate` mismatch is the exact ROADMAP phrase and must be repaired in Task 2 before final validators pass; it is an administrative prerequisite, not a new runtime or silicon finding.

## Historical findings and uncertainty

F14-01 and F14-02 have recorded regression-backed receipt-command and failure-history repairs, including normal and optimized Python; inspection of the retained collection commands/configuration shows no contrary current evidence. CR-01's reachable odd-PC/selected-stack rejection is repaired by preservation and continuation of the named ready boundaries. CR-02 and WR-01's cumulative-decrease/exact-cap defects are repaired by monotonic and inclusive current source checks. WR-02's old unimplemented-runtime description was corrected at its dated source identity. None of these statements erases historical reports or claims their controls ran in this assessment.

F14-03 is superseded **only for exact candidate opcode 0x4AFC** under P01-C-14. Intentional ILLEGAL users are unsupported. Original-silicon saved PC remains unknown under P01-C-13; neither $100 nor $102 is selected. The old unqualified/deferred candidate receipt remains unchanged; its historical HIGH/open text is historical uncertainty, not a silently resolved hardware result.

All nine historical specless flags remain unresolved metadata: CPU-01 concurrency; CPU-02/03/04 unclassified; CPU-05 boundary, adjacency, empty, ordering and precision. They are not assertions, passes or additional unfulfilled acceptance predicates. Current requirement judgments above use the explicit canonical CPU predicates and direct bounded evidence.

No CMake 3.20 execution, other host/platform, full ISA, original BIOS/game, board/pin timing, public SDK ABI, snapshot/replay/durable save, physical silicon or gameplay performance is qualified. The four native lane recipes, negative controls and existing archive identities make future reproduction possible within those bounds; finite observations cannot prove every schedule, guest program or caller.

## Closeout boundary

This report binds the identical candidate and the planned bounded assessment ceiling: at most 7,200 summed active seconds including all agents/closeout and 800 added/deleted tool/test lines; existing caps are unchanged. CPU-05 requires the final append-only ledger and preservation checks to pass before the executor freezes its recommendation. The final ledger digest belongs in that decision to avoid changing this report or making a recursive ledger hash. I will confirm final accounting read-only when supplied.

There is no additional material evidence blocker for the scoped recommendation. The next admission authority is exactly one separate whole-phase verifier. CPU-01–05 remain Pending, Phase 01 remains open/GAPS_FOUND and Phase 02 remains gated throughout this execution.

## Exact machine assessment

```json
{
  "schema": 1,
  "kind": "cpu-admission-review",
  "agent_id": "/root/admission_review",
  "independent_non_author": true,
  "assessment_commit": "4945f348cf67777f3f90f87ef8331250a2c7add9",
  "identity": {
    "profile": "owned-p01-c14-continuation-2",
    "source_revision": "bd390a7f5f6ede0a69df42f8df1fc98905d171ea",
    "collection_sha256": "cb77285dd7b821993e1e12ec96e72ed5e13bbf57da7d6dd433f07b3940275738",
    "source_map_sha256": "be6e2c45f9590425a227bb9d6622d7629d080cca778eba29d5304bef3bd13a6d",
    "amendment_sha256": "3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad",
    "active_contract_identity_sha256": "27af8df79b55f83bffdef63981defc23984fff6b4e0002d10e99621310340419",
    "contract_sha256": "6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73",
    "subset_sha256": "5fc0c0aa872a6a2ec2e39e86b085e8426f4b378cf3c48736317c8f10961efb4c",
    "acceptance_sha256": "62663275b785137cba2d225f2b4a4572e3696d7ed7245c7cd87dd89432ecf23c",
    "receipt_sha256": "fb14db2af97e7c1c10d8632892bc152189de5db7bae4df104391ce8516c6e7f0",
    "source_manifest_sha256": "ae481ac75ac88dd40cc86de52fa827a4941280ca3ce6f4e0952c71ecf3a47eab",
    "state_inventory_sha256": "42ab974ac633b73a15c7ac10d3ba604dccfdc0aa8453905a03934a54b17acbab",
    "runtime_sha256": "f11a282d5f571a67fff687c08cc90a44f5b6ff54bb5334b9c21bf17a4abcbee7",
    "oracle_sha256": "2af54ed3fd35303c68d92b551ce02a65b1fb94f4b42a84779d03734e264771e0",
    "old_review_sha256": "ecbe3c6fe6767ccfe8eb5b81e12223ac8b25a812bddd0b2b3adc335c5d7049ce",
    "old_security_sha256": "27d9974e72c9e58b8131d30883c5555c03665718a32b997bb3d138980d0137e2",
    "hardware_saved_pc": "unknown",
    "unsupported_opcodes": [
      "0x4AFC"
    ]
  },
  "hardware_saved_pc": "unknown",
  "unsupported_opcodes": [
    "0x4AFC"
  ],
  "hardware_claim": "none",
  "requirements": {
    "CPU-01": {
      "decision": "sufficient",
      "evidence": [
        {
          "path": "experiments/owned_cpu/source-manifest.json",
          "sha256": "ae481ac75ac88dd40cc86de52fa827a4941280ca3ce6f4e0952c71ecf3a47eab",
          "claim": "38 per-file origin/license/compiled/distributed records; cpu.c alone is the runtime archive source and generated runtime list is empty.",
          "denominator": 38,
          "oracle": "Immutable source inventory plus recorded compile/archive inspection.",
          "limitation": "Inventory is bounded to current experiment; generated build products are local outputs and Unity is test-only."
        },
        {
          "path": "experiments/owned_cpu/cpu.c",
          "sha256": "f11a282d5f571a67fff687c08cc90a44f5b6ff54bb5334b9c21bf17a4abcbee7",
          "claim": "Independent direct read found all persistent mutable fields in owned_cpu, explicit per-owner bus/allocator callbacks, bounded standard C memory operations, and no imported CPU/FPU/generator or direct ambient host services.",
          "denominator": 1,
          "oracle": "Direct source inspection at assessment commit.",
          "limitation": "C17 acceptance is for the recorded native compiler; this does not qualify the CMake 3.20 floor or another platform."
        }
      ],
      "limitation": "Native Darwin arm64/AppleClang 21 evidence only; no public SDK, installed consumer, other toolchain or platform claim."
    },
    "CPU-02": {
      "decision": "sufficient",
      "evidence": [
        {
          "path": "experiments/owned_cpu/acceptance-results.json",
          "sha256": "fb14db2af97e7c1c10d8632892bc152189de5db7bae4df104391ce8516c6e7f0",
          "claim": "Per lane: two distinguishable isolated owners, 32 interleaved pairs and 32 concurrent cold pairs compare observations, guest RAM and ordered callbacks at six boundaries; 16 independent fresh processes also pass.",
          "denominator": 64,
          "oracle": "Recorded source-bound four-lane fixture observations; project-original recipes and Motorola/NXP manual-derived expectations, not silicon captures.",
          "limitation": "Finite two-owner schedules; no same-instance overlap or arbitrary concurrent caller-supplied bus proof."
        },
        {
          "path": "tests/owned_cpu/test_isolation.c",
          "sha256": "35a5a515e1df3798bcae4a190387e32c4ea6ce6a0aa2ac628789111d85d7e155",
          "claim": "Boundary comparator includes distinguishable D0/store/IRQ results; swapped-owner negative control is meaningful and cold pairs compare all six boundaries.",
          "denominator": 64,
          "oracle": "Project-original isolated baseline oracle; expected guest stores derive from original diagnostic recipe.",
          "limitation": "Matching baselines alone cannot establish ISA truth."
        },
        {
          "path": "tests/owned_cpu/test_faults.c",
          "sha256": "71e09309af7c556b907563229ae6e176958ee91dbe7ddad5ceff124fabe071fa",
          "claim": "Five named test functions cover invalid creation/allocation, callback reentry, reset fault/recovery, seven execution callback faults and STOP wake; owner release counters remain zero after teardown.",
          "denominator": 5,
          "oracle": "Direct fixture assertions of error reason, callback count, allocation ownership and partial-write preservation.",
          "limitation": "One allocation site; caller-provided accessible buffers and correctly aligned allocator storage remain host obligations."
        }
      ],
      "limitation": "Evidence supports independent instances with compliant separately owned callbacks and buffers. Same-instance concurrent calls, callback lifetime violations and general multithreaded host correctness are unsupported."
    },
    "CPU-03": {
      "decision": "sufficient",
      "evidence": [
        {
          "path": "experiments/owned_cpu/acceptance-results.json",
          "sha256": "fb14db2af97e7c1c10d8632892bc152189de5db7bae4df104391ce8516c6e7f0",
          "claim": "Per lane: two original diagnostic scenarios produce 10 and 16, 17 semantic cases and 25 timing/exception cases pass with exact command/configuration identities and nonzero CTest denominator.",
          "denominator": 25,
          "oracle": "Recorded source-bound four-lane fixture observations; project-original recipes and Motorola/NXP manual-derived expectations, not silicon captures.",
          "limitation": "Selected instruction/event model only; finite cases do not qualify full ISA, prefetch, pin cycles, wait states or board timing."
        },
        {
          "path": "tests/owned_cpu/ORACLE.md",
          "sha256": "2af54ed3fd35303c68d92b551ce02a65b1fb94f4b42a84779d03734e264771e0",
          "claim": "Manual references, named result/frame/event assertions and consequential wrong-cycle/unsupported controls describe the bounded timing oracle; this review corrects the SR_switch_odd_USP extension-read sentence.",
          "denominator": 25,
          "oracle": "MC68000UM Rev 9.1 sections/timing tables and M68000PRM encodings; functional callback order and fault-PC values are project policy.",
          "limitation": "No silicon capture; the SR_switch_odd_USP $106 read sentence is unsupported and superseded by WR-01 below."
        },
        {
          "path": "experiments/owned_cpu/illegal-reconciliation.json",
          "sha256": "b6118fe7b4f846784ac06497509934e58481a5135f9116b6f99cf8eea2588298",
          "claim": "P01-C-14 excludes only exact 0x4AFC; P01-C-13 original-silicon saved PC remains unknown.",
          "denominator": 1,
          "oracle": "Explicit owner-approved capability amendment, not a hardware oracle.",
          "limitation": "Intentional ILLEGAL-using guest code is unsupported; no hardware saved-PC value is selected."
        }
      ],
      "limitation": "Instruction-boundary timing and the explicitly supported forms only. WR-01 corrects a nonqualifying trace sentence; continuation equivalence is not an independent silicon trace oracle."
    },
    "CPU-04": {
      "decision": "sufficient",
      "evidence": [
        {
          "path": "experiments/owned_cpu/state-inventory.json",
          "sha256": "42ab974ac633b73a15c7ac10d3ba604dccfdc0aa8453905a03934a54b17acbab",
          "claim": "26 persistent instance fields plus automatic transient state and callbacks have explicit ownership/disposition; private record rebinds host ownership and reconstructs readiness.",
          "denominator": 26,
          "oracle": "Direct comparison with owned_cpu struct and capture/restore source.",
          "limitation": "Conventional-source inventory tooling is not a general C parser; private fixed accessible C record only."
        },
        {
          "path": "tests/owned_cpu/test_state.c",
          "sha256": "02f7689a0f2f58d3ef402638c980a70e5d37b0f5da30cdeb7b14a55ae926f5d8",
          "claim": "15 named checkpoint sequences perform fresh destination restore with cloned guest memory, destroy/overwrite source ownership and compare six subsequent results, fields, memory and ordered callback streams.",
          "denominator": 90,
          "oracle": "Project-original uninterrupted-versus-restored owner equivalence plus direct named boundary assertions.",
          "limitation": "Equivalence cannot certify absolute hardware state; public snapshots, cross-build compatibility and arbitrary byte parsing are excluded."
        },
        {
          "path": "experiments/owned_cpu/acceptance-results.json",
          "sha256": "fb14db2af97e7c1c10d8632892bc152189de5db7bae4df104391ce8516c6e7f0",
          "claim": "Current profile records 15 checkpoints / 90 continuation calls in each of four exercised lanes; older profiles and counterexamples remain separate history.",
          "denominator": 90,
          "oracle": "Recorded source-bound four-lane fixture observations; project-original recipes and Motorola/NXP manual-derived expectations, not silicon captures.",
          "limitation": "Finite supported ready boundaries; no mid-instruction suspension or terminal-fault serialization."
        }
      ],
      "limitation": "Private same-build continuation only. Guest memory is caller-cloned; allocator/callback bindings remain destination-owned; no public snapshot/replay/durable-save promise."
    },
    "CPU-05": {
      "decision": "sufficient",
      "evidence": [
        {
          "path": "experiments/owned_cpu/CONTRACT.md",
          "sha256": "6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73",
          "claim": "Frozen 115200-active-second, 28800-diagnostic-second, 6000-runtime-line and 8000-test/tool-line ceilings predate owned implementation and require failed/reverted work with no refunds.",
          "denominator": 4,
          "oracle": "Frozen contract and append-only accounting policy.",
          "limitation": "Effort logs are maintainer evidence rather than independently provable time; final Plan 01-29 all-agent accounting remains a required executor closeout."
        },
        {
          "path": "tools/owned_cpu/contract.py",
          "sha256": "ceed2df6d9f0438e9e9981f4e91f4033febc605636006d6e8f3a6267c1e99650",
          "claim": "Independent inspection confirms monotonic cumulative churn, inclusive exact caps, named pause outcomes, original diagnostic gate and historical hash checks; fresh read-only budget reports 47 records, 79763 active seconds, 2565 diagnostic seconds, 1228 runtime and 6540 test/tool churn.",
          "denominator": 47,
          "oracle": "Frozen budget policy with regression-backed historical independent review; current read-only budget output.",
          "limitation": "This assessment does not approve a future crossed threshold. Ledger hash is bound by final decision preservation, not by this pre-append report."
        },
        {
          "path": "experiments/owned_cpu/REVIEW.md",
          "sha256": "ecbe3c6fe6767ccfe8eb5b81e12223ac8b25a812bddd0b2b3adc335c5d7049ce",
          "claim": "Historical F14-01/F14-02 receipt guards and CR-02/WR-01 budget fixes retain dated normal/-O evidence; candidate-specific F14-03 supersession does not select hardware truth.",
          "denominator": 7,
          "oracle": "Independent dated review and source-backed finding dispositions.",
          "limitation": "The existing current section was metadata-only; this new full-scope judgment does not convert its old native executions into fresh runs."
        }
      ],
      "limitation": "Sufficient bounded decision basis conditional on final append-only charges and unchanged caps passing Task 2. Reserve ceiling is 7200 summed active seconds and 800 added/deleted tool/test lines, not an authorization to extend scope."
    }
  },
  "blocker": null
}
```

