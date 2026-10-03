---
phase: 01-cpu-acceptance-experiment
plan: "19"
subsystem: cpu
tags: [continuation, negative-controls, receipt-profiles, tdd]
requires:
  - phase: "01-18"
    provides: Exact canonical unsupported boundary and additive P01-C-14 amendment
provides:
  - Thirteen retained continuation boundaries with six fresh-owner calls each
  - Exact unsupported-status negative control and ambiguity rejection
  - Versioned receipt validation and independent review/security deferred seals
affects: [01-20, 01-21]
tech-stack:
  added: []
  patterns: [immutable historical profile, bounded current attestations, deferred phase admission]
key-files:
  created: []
  modified:
    - tests/owned_cpu/test_semantics.c
    - tests/owned_cpu/test_state.c
    - experiments/owned_cpu/state-inventory.json
    - tests/owned_cpu/negative_timing.py
    - experiments/owned_cpu/CMakeLists.txt
    - tools/owned_cpu/acceptance.py
    - tests/owned_cpu/test_acceptance.py
    - experiments/owned_cpu/budget-ledger.json
key-decisions:
  - "Historical profile remains immutable; current receipts require owned-p01-c14-1 and the exact active amendment."
  - "Candidate sealing requires bounded independent review/security and always defers phase admission."
requirements-completed: []
actuals:
  tokens: 15975
  tasks: 3
  commits: 6
plan_head_before: 967c9a02045564149768dcc43bdbef6e8cc75010
plan_head_after: 4edcd12b30ec97682de4c76acd33fbd83ea18e33
coverage:
  - id: D1
    description: Canonical semantic rejection and all 13 fresh-owner continuation boundaries
    verification:
      - kind: integration
        ref: "ctest --preset owned-debug -R '^owned_cpu_(semantics|state)$' --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D2
    description: Exact one-case cycle/status negative controls
    verification:
      - kind: integration
        ref: "ctest --preset owned-debug -R '^owned_cpu_(timing_negative|unsupported_negative)$' --output-on-failure --no-tests=error"
        status: pass
    human_judgment: false
  - id: D3
    description: Profile, amendment, historical preservation and independent deferred-seal validation
    verification:
      - kind: unit
        ref: "python3 -m unittest discover -s tests/owned_cpu -p test_acceptance.py"
        status: pass
      - kind: unit
        ref: "python3 -O -m unittest discover -s tests/owned_cpu -p test_acceptance.py"
        status: pass
    human_judgment: false
duration: 18min
completed: 2026-10-03
status: complete
---

# Phase 01 Plan 19: Candidate continuation and exact evidence profiles Summary

**Canonical rejection now has semantic and 78-call fresh-owner continuation evidence; current receipts require six exact controls, amendment identity and independent review/security before a deferred seal.**

## Performance and scope

Three tasks changed eight declared files. Six task commits were measured from the persisted plan ledger; the realized diff is 63,900 characters / four, or 15,975 estimated tokens. No runtime implementation, dependency, public ABI or state format was added. Phase 01 remains incomplete/GAPS_FOUND; CPU-01–05 remain Pending, Phase 02 gated, F14-03 and T-01-15-03 HIGH/open, and original-silicon saved PC unknown.

## Accomplishments and verification

- Targeted Debug semantics/state: 2/2 CTests, 17 semantic and five state Unity cases. The replaced canonical boundary and the twelve retained boundaries each execute six continuation calls (13/13, 78 calls), after source destruction/overwrite with separate destination bus/memory ownership. Exact unsupported status, PC/IR, zero dispatch/cycles and opcode-only callbacks are asserted. Invalid/stale state identity, omissions, active/terminal-state and binding controls remain.
- Inventory self-test passed its missing/extra-field, stale identity/hash, hidden-global, callback-owner and manifest controls. Current runtime/header/semantic/state hashes were reconciled in the private inventory; later source-manifest refresh remains owned by Plan 01-20.
- Both consequential negative CTests passed (2/2). Each child exits one with exactly one intended Unity assertion, one test, zero ignored, and expected=observed=1. Wrapper self-tests cover exact status, multiple summaries/assertions, wrong numeric/name suffixes, denominator changes, unrelated failure, crash, pass and timeout.
- Acceptance regression suite passed 21/21 methods under normal Python and 21/21 under `-O`. Collector self-test passed six negative and two classification controls in each mode. New policy expects 13 CTests, 25 ordinary timing declarations, six named controls and the exact 13-boundary/78-call trace. Legacy policy keeps 12 CTests, 23 timing cases, five controls and its original checkpoint definitions.
- New bounded review requires one complete current section, exact revision/collection/amendment/source-map identity, independent non-author declaration, explicit F14-01/02/03 evidence dispositions and hardware-unknown status. Current security requires exact integer schema/ASVS level, block-high, independent status verified, zero high/critical findings and identical identities. A valid synthetic deferred seal remains unqualified/GAPS_FOUND with `phase-goal-verification-pending`; changed audit bytes and blocked/stale/malformed/duplicate attestations reject.
- Independent read-only review found two validator gaps (multiline HIGH/open metadata and Boolean numeric fields). Both were repaired, covered under normal/optimized modes and independently rechecked. This narrow validator review does not replace Plan 01-21's actual candidate source/security audits.

## Task commits

1. `aea8941` — test: reconcile canonical rejection and 13 continuation boundaries.
2. `65a60b1` — test: require exact unsupported-status negative control.
3. `1b3e0d0` — feat: classify exact unsupported-status assertion failures.
4. `3e822a1` — test: reject profile spoofing and relabeled legacy receipts.
5. `7195b76` — fix: reject ambiguous negative-control summaries and status text.
6. `4edcd12` — feat: bind amended receipts and defer admission behind independent audits.

## TDD evidence and sequencing

Task 1 reconciles test-only expectations with runtime behavior already implemented by Plan 01-18. The initial run exposed the two obsolete expectations; updated positive tests passed immediately because no new runtime behavior was required.

Task 2's new wrapper test intentionally failed `test_exact_unsupported_failure_is_required` with `0 != 1` before implementation. Task 3 intentionally failed `test_current_profile_rejects_unknown_and_legacy_relabel` because three spoofed profiles raised no EvidenceError. Their persisted records contain command, exit, target, expected/actual and explicitly normalized TAP summaries of the observed unittest assertions; the SDK returned RED_EVIDENCE_OK for each. RED commits precede GREEN commits. Sequencing deviation: Task 2's record was persisted/SDK-validated after the first implementation edit, before GREEN execution/commit. The phase runtime TDD-mode flag is false; task-level TDD still applied. No refactor commit was needed.

## Deviations from plan

- [Rule 1 — Bug] Canonicalized the security document's relative path against the resolved checkout root, after the temporary-subject test exposed a macOS directory-symlink mismatch. Covered by the deferred-seal regression.
- [Rule 1 — Bug] Tightened negative output boundaries and uniqueness of summaries/denominators; a status suffix or additional summary must not impersonate the intended one-case failure. Commit `7195b76`.
- [Rule 1 — Bug] Independent review's multiline blocker and Boolean schema findings were fixed in Task 3; re-review confirmed rejection under both Python modes. Commit `4edcd12`.
- The Task 2 RED-record sequencing deviation above is retained explicitly.

## History and resource preservation

All 23 pre-plan ledger entries compare unchanged; five append-only entries charge 1,849 additional agent-seconds, including a conservatively bounded 600-second independent review and two labeled 180-second closeout/metadata allowances. Frozen budget passes: total active 40,863 seconds, diagnostic gate unchanged at 2,565 seconds, runtime churn unchanged at 1,221, test/tool churn 6,126; no pause requested. Python/control/review observations are recorded as supplemental checks without inventing whole-candidate collection. The final metadata accounting entry is committed with the summary/state; measured task actuals above stop before that metadata commit.

Protected SHA-256 identities compare byte-for-byte against the pre-plan revision:

| Artifact | SHA-256 |
|---|---|
| owned acceptance-results.json | `0bd5a8ece637ec26136ea2af8fe7aec6bf55dc66cf7fb0bb0bb64af3982031bb` |
| illegal-reconciliation.json | `b6118fe7b4f846784ac06497509934e58481a5135f9116b6f99cf8eea2588298` |
| frozen CONTRACT.md | `6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73` |
| Plan 01-17 adjudication | `22f647c2e9c56d63aeb9f6a909f7a38622d97fc9f3b282216ebe3b40b80dfadb` |

No old collection was overwritten, relabeled or rerun. Original Musashi history remains governed by the unchanged frozen ledger identities.

## Deferred issues and next step

No implementation stubs, skipped planned tests or unrun Plan 01-19 verification commands remain. Whole-candidate collection and source-manifest freshness intentionally await Plan 01-20; actual independent current candidate/security judgment awaits Plan 01-21. The new file-attestation surface is covered by T-01-36; no undeclared endpoint, auth path or public persistence schema was introduced. Continue the already authorized sequential execution at Plan 01-20; after the execute workflow ends, pause for the separate user-controlled verification step.

## Self-Check: PASSED

All eight modified task paths and all six task commits exist. No task commit deleted tracked files. The ledger prefix and protected artifact identities compare unchanged; final targeted regressions and both Python modes pass. Summary is written on disk before GSD state updates.
