---
phase: 01-cpu-acceptance-experiment
plan: "20"
subsystem: cpu
tags: [c17, exact-qualification, immutable-history]
requires:
  - phase: "01-19"
    provides: Current profile, continuation and consequential unsupported control
provides:
  - Precise amended candidate reproduction scope and licensed source closure
  - Append-only four-lane native qualification for the committed current profile
affects: [01-21]
tech-stack:
  added: []
  patterns: [source-bound receipts, immutable historical prefix, deferred admission]
key-files:
  created: []
  modified:
    - experiments/owned_cpu/ACCEPTANCE.md
    - experiments/owned_cpu/source-manifest.json
    - experiments/owned_cpu/acceptance-results.json
    - experiments/owned_cpu/budget-ledger.json
key-decisions:
  - "Current whole-lane receipts reuse build directories; only the separate cold-process case claims cold processes."
  - "Current evidence remains unqualified/GAPS_FOUND pending independent review/security and separate phase verification."
requirements-completed: []
actuals:
  tokens: 34585
  tasks: 2
  commits: 2
plan_head_before: e6ee5981de4bb4c44d6ff0a2553cfcb8df07431a
plan_head_after: 4b2944e08f67ec6f2f16e13b96868aa052e78394
duration: 6min
completed: 2026-10-03
status: complete
---

# Phase 01 Plan 20: Exact amended candidate qualification Summary

**Committed licensed source closure reproduced 13/13 CTests in Debug, Release/O2, ASan+UBSan and optional TSan, with immutable historical evidence and pending admission.**

## Exact evidence identity

Collected source revision: `7411a33bf63428516a3efee289c393e1a8418b28`.
Profile: `owned-p01-c14-1`. Collection SHA-256:
`53ea6a7162902edea4e4372e85b3713ad4092f0522501c33a59115573101337e`.
Source-map SHA-256:
`e63834b8585912d81f99e82e2dd9070139fbc8acc25854e23274105d8cad861b`.
P01-C-14 amendment SHA-256:
`3728dc84fc27b2f51262ede8f916d755ff9340b80b069e53a731caea247b36ad`.
Active candidate identity:
`27af8df79b55f83bffdef63981defc23984fff6b4e0002d10e99621310340419`.
Frozen contract remains
`6ec5b901efb87618b2a03e348bd3fc068e28ae0fc24665a4c041067a1f0c2f73`.

The 39-entry snapshot includes the manifest itself and every defined authored/copied distribution input. Unity remains pinned and test-only, with MIT notices; only `cpu.c` is runtime archive source. No online source, dependency or manual bytes were acquired.

## Tasks and verification

1. `7411a33` — published the dated active-scope supersession and refreshed manifest. Historical report paragraphs, findings, observations and collection identifiers remain. Exact 4AFC is candidate-unsupported; original hardware defines ILLEGAL, and original-silicon saved PC remains unknown. Intentional ILLEGAL users are incompatible. Contract validation, manifest refresh, nonempty exact snapshot and budget passed.
2. `4b2944e` — appended current-profile qualification and resource charges. Required Debug, Release/O2 and ASan+UBSan passed; optional TSan passed its actual build/test lane. No unsupported/skipped/fail outcome was converted to success. Collector verification and explicit status/denominator inspection passed. Read-only inventory confirmed 26 owned fields, ten compiled sources, no runtime mutable globals and no callback owner mutation; each lane also verified its actual object/link instrumentation and artifact identities.

| Lane | Actual CTests | Unity cases | Continuation | Named controls |
|---|---|---|---|---|
| Debug | 13/13 pass | 58 | 13 boundaries / 78 calls | 6 |
| Release/O2 | 13/13 pass | 58 | 13 boundaries / 78 calls | 6 |
| ASan+UBSan | 13/13 pass | 58 | 13 boundaries / 78 calls | 6 |
| TSan, optional | 13/13 pass | 58 | 13 boundaries / 78 calls | 6 |

Total: 52/52 CTests. Per lane Unity cases: diagnostic2, semantics17, timing25, isolation4, faults5, state5. Each lane observed 32 interleaved pairs, 32 concurrent pairs and 16 separate cold processes. Whole-lane configure/build runs reused existing directories and are not cold builds. Six controls cover wrong guest arithmetic/store, omitted IRQ continuation, state counter identity, swapped owner, wrong address-error cycle charge and wrong canonical unsupported status. All thirteen named continuation boundaries remain in receipts, including canonical rejection and retained TRAP/privilege/address-error/IRQ/RTE behavior.

Commands executed:

```sh
python3 tools/owned_cpu/contract.py validate
python3 tools/owned_cpu/inventory.py refresh-manifest
python3 -c 'from tools.owned_cpu import acceptance; s=acceptance.snapshot(); acceptance.require(bool(s), "empty source closure"); print("PASS: exact nonempty current source closure", len(s))'
python3 tools/owned_cpu/acceptance.py collect --preset owned-debug --preset owned-release --preset owned-asan-ubsan --optional-preset owned-tsan
python3 tools/owned_cpu/acceptance.py verify
python3 tools/owned_cpu/inventory.py check --build-dir build/owned-debug
python3 tools/owned_cpu/contract.py budget
```

Host: Darwin25.6.0 arm64, Python3.14.4; exact compiler/tool/SDK commands, outputs, configuration and binary hashes reside in the collection. CMake3.20 execution, other platforms, original-silicon saved PC, board/pin timing, full ISA, public ABI/snapshot/replay/save and gameplay performance remain unknown/excluded. Original stores10/16, instruction36 and reset40 remain unchanged. Results are unqualified/GAPS_FOUND; F14-03/T-01-15-03 remain HIGH/open, CPU-01–05 Pending, Phase 01 incomplete and Phase 02 gated. No seal or requirement completion occurred.

## Preservation evidence

Read-only Python/Git comparison against `7726c470aca1293c95d5995d40f6f350564acf1f` passed: four prior collections and 21 prior ledger entries remain equal prefixes; 14 non-entry ledger fields and all 16 old reconciliation key/value pairs match. Five files match byte-for-byte: frozen CONTRACT and Plan01-17 PLAN, SUMMARY, ILLEGAL-EVIDENCE and ILLEGAL-ADJUDICATION. Contract validation separately passed strict frozen archive equality and all ten pinned historical Musashi files. No source/manuscript record was regenerated. The same checks passed after the appended accounting entries.

The executed comparison was a root-relative Python program launched with `PYTHONPATH=. python3` (its temporary script is not distributed). Reproduce its conditions with `python3 -c` containing:

```python
import json, subprocess
from pathlib import Path
from tools.owned_cpu import contract
base = "7726c470aca1293c95d5995d40f6f350564acf1f"
def old(p):
    return subprocess.check_output(["git", "show", f"{base}:{p}"])
def check(ok, message):
    if not ok:
        raise SystemExit("FAIL: " + message)
def pair(p):
    return json.loads(Path(p).read_bytes()), json.loads(old(p))
a, b = pair("experiments/owned_cpu/acceptance-results.json")
check(a["collections"][:len(b["collections"])] == b["collections"], "collections")
a, b = pair("experiments/owned_cpu/budget-ledger.json")
check(a["entries"][:len(b["entries"])] == b["entries"], "ledger entries")
check({k:v for k,v in a.items() if k != "entries"} ==
      {k:v for k,v in b.items() if k != "entries"}, "ledger fields")
a, b = pair("experiments/owned_cpu/illegal-reconciliation.json")
for k, v in b.items():
    check(a.get(k) == v, "reconciliation " + k)
paths = ["experiments/owned_cpu/CONTRACT.md"]
paths += [p for p in subprocess.check_output(["git", "ls-tree", "-r", "--name-only",
    base, ".planning/phases/01-cpu-acceptance-experiment"]).decode().splitlines()
    if Path(p).name.startswith("01-17-")]
for p in paths:
    check(Path(p).read_bytes() == old(p), p)
check(contract.validate(Path(".").resolve())["status"] == "pass", "archive/history")
print("PASS: preservation")
```

## Accounting and deviations

Three append-only stage records charged 472 seconds: scope9, native45 and closeout418. The closeout record includes 180 seconds conservative initial-read allowance, 29 seconds measured scope/commit handling, 29 seconds measured closeout, and 180 seconds conservative finalization allowance. Allowances are estimates, not measured execution; their intervals intentionally overcharge any overlap. Task1's budget record binds the prior two-case LastTest.log and does not claim new native tests. Task2 binds the freshly observed 13-case Debug log.

Final ledger has 31 entries, 41,335 active seconds, diagnostic gate2,565 seconds, runtime churn1,221 and test/tool churn6,126; all frozen caps pass. Failed/reverted historical work remains charged; this plan needed no native repair, retry, golden change or cap relaxation. Realized committed diff is 138,340 characters / four = 34,585 estimated tokens; two task commits are measured from the persisted ledger. Metadata closeout is separate.

No plan deviation, authentication gate, known stub, skipped test or unrun verification was introduced. No new endpoint, trust-boundary schema, runtime file access or auth surface was added.

## Self-Check: PASSED

All four modified artifacts exist and both task commits were verified in Git. Current exact-source verification and preservation checks passed. Plan 01-21 remains for independent review/security; separate phase verification remains required afterward.
