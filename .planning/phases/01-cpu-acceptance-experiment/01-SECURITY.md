---
phase: "01"
slug: "cpu-acceptance-experiment"
status: verified
threats_open: 0
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

## Accepted Risks Log

No accepted risks.

Same-instance callback reentry remains unsupported by contract; guards specifically reject capture/restore during callbacks, without claiming comprehensive callback-reentry support. Hardware-wide compatibility, guest bus-error frames, arbitrary bus-cycle suspension, distinct compiler toolchains, and release-platform support also remain explicitly unqualified. These are outside the bounded experiment's claims, not accepted mitigations or evidence of support.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-01 | 16 | 16 | 0 | `gsd-security-auditor` (read-only cross-check) |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-01
