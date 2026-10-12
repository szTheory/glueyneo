---
phase: 01-cpu-acceptance-experiment
reviewed: 2026-10-05
depth: bounded-asvs-l1
files_reviewed: 11
findings:
  high: 0
  critical: 0
  medium: 1
  low: 1
status: verified
---

# Plan 01-29 independent admission security assessment

**Verdict: SECURED at ASVS Level 1 with `block_on: high`.** No applicable open HIGH or CRITICAL finding was established. This is a bounded assessment of candidate and recommendation controls; it does not admit the backend or complete Phase 01.

**Assessor:** `/root/admission_security`, independently delegated non-author. The assessor authored no runtime, checker, tests, receipt, ledger or review implementation. The original assessment checkpoint was `4945f348cf67777f3f90f87ef8331250a2c7add9`; follow-up verified the correction at `54136cf0ce36a57238debfa0c1e027c6b626c14f`.

## Threat review

| Threat | Severity | Disposition | Assessment |
|---|---:|---|---|
| T-01-64 — recommendation spoofing | HIGH | Mitigate; closed for implemented controls | Report parsing checks exact report hashes, distinct executor/reviewer/assessor identities, non-author attestations, all five requirement judgments, evidence denominators and oracle ancestry. Controls reject false independence, missing or contradictory predicates, stale identities and open HIGH findings. Final report binding is checked during closeout. |
| T-01-65 — decision/evidence tampering | HIGH | Mitigate; closed for implemented controls | Duplicate JSON keys, unsafe paths, oversized evidence, stale candidate identities, altered ledger prefixes, receipt history and historical UAT bytes are rejected. Normal and optimized controls cover semantic and preservation mutations. The initial closeout reporting defect and correction are detailed below. |
| T-01-66 — unauthorized admission | HIGH | Mitigate; closed | The decision requires `phase_admitted=false`, Pending CPU requirements, the exact open/gated ROADMAP guard, and the existing unqualified candidate receipt. The recommendation cannot itself admit the phase. |
| T-01-67 — cost/history repudiation | MEDIUM | Mitigate; pending Task 2 closeout | The append-only checker and budget validator exist. Actual all-agent charges, final ledger digest, additive UAT records and successful live preservation output must still be assembled and verified. |
| T-01-SC — dependency mutation | LOW | Accept; documentation note remains | No dependency installation or runtime dependency expansion was found. Unity remains pinned and test-only. The historical Phase 01 security log has no exact Plan 01-29 T-01-SC accepted-risk row; this is a nonblocking documentation gap and is recorded here. |

Open blocking threats: **0 HIGH/CRITICAL**. One MEDIUM and one LOW item remain nonblocking pending closeout/documentation.

## Preservation defect and correction

At the original assessment checkpoint, `check_preservation` reached its return statement with an undefined `old_uat` name. The original 14 tests covered preservation helpers but not the complete function return path. This caused a fail-closed reporting error, not a bypass or runtime defect.

Commit `54136cf0ce36a57238debfa0c1e027c6b626c14f` now reads `snapshot["uat"]["historical_rows"]`. A new regression invokes the complete preservation return path and checks the reported historical count. Fresh normal and optimized test runs each passed **15/15**. These checks verify the fix; the live preservation command against final appended accounting is still required.

The exact admission-gate wording was also restored in the active Task 2 ROADMAP edit. Follow-up inspection confirms the literal is present. Contract and acceptance prerequisites passed before final accounting: `contract.py validate` reports status `pass` with all CPU requirements Pending and Phase 02 gated; `contract.py budget` reports 47 historical records, 79,763 active seconds and 6,540 test/tool churn; `acceptance.py verify` reports six collections, no lane blockers and `unqualified`. Final post-accounting reruns remain required.

## Candidate safety and claim limits

The source inventory has **26** runtime fields; direct checks found no missing/extra fields, mutable runtime globals, forbidden direct host-service calls, private-state identity/record mismatches or callback-owner errors. The runtime uses explicit per-instance bus and allocator callbacks, rejects active-instance reentry, marks bus callback failures terminal until reset, and checks relevant counters before committing event effects. These controls support the stated independent-instance, single-thread-per-instance model. The `active` field is not synchronization; same-instance concurrency, callback lifetime violations, and arbitrary caller callback behavior are not qualified.

State restore validates and stages the bounded private fixed-size in-process record before modifying guest fields and retains destination-owned host callbacks. It is not an untrusted serialized format, and establishes no public snapshot compatibility or durable-save claim. `0x4AFC` rejection is candidate-only and happens before exception frame/vector effects. Original-silicon saved PC stays unknown.

The runtime archive contains `cpu.c`; Unity remains in test executables and Threads in test targets. No runtime dependency expansion was found. No full-ISA, physical-hardware, other-platform/toolchain, BIOS/game, public ABI, persistence, or gameplay performance claim is made.

Historical F14-01/F14-02 fixes remain bounded to their receipt/failure controls. F14-03 / T-01-15-03 is superseded only for candidate-only exact `0x4AFC`; no silicon saved-PC value is selected. CR-01, CR-02, WR-01 and WR-02 remain tied to their dated scoped fixes. Nine historical specless flags remain unresolved metadata, not passing assertions. No receipt was resealed and no native lane was recollected for this assessment.

The corrected candidate and original evidence checkpoint remain bound to profile `owned-p01-c14-continuation-2`, recorded revision `bd390a7f5f6ede0a69df42f8df1fc98905d171ea`, unknown silicon saved PC and exact candidate-only unsupported opcode `0x4AFC`. The complete machine identity follows.

```json
{
  "schema": 1,
  "kind": "cpu-admission-security",
  "agent_id": "/root/admission_security",
  "independent_non_author": true,
  "assessment_commit": "4945f348cf67777f3f90f87ef8331250a2c7add9",
  "follow_up_commit": "54136cf0ce36a57238debfa0c1e027c6b626c14f",
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
    "unsupported_opcodes": ["0x4AFC"]
  },
  "hardware_saved_pc": "unknown",
  "unsupported_opcodes": ["0x4AFC"],
  "hardware_claim": "none",
  "status": "verified",
  "asvs_level": 1,
  "block_on": "high",
  "open_high_or_critical": 0,
  "blocker": null
}
```
