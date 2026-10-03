---
schema_version: 1
open_count: 1
waived_count: 1
fixed_count: 6
total_count: 8
last_updated: 2026-10-03T01:37:56.782Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 01 | unrun-verify | .planning/phases/01-cpu-acceptance-experiment/01-01-PLAN.md |  | Task 1 guest/control CTests and Task 2 closure/budget controls remain unrun because the adapted backend does not compile. | fixed |  | 2026-10-01T16:32:36.895Z | 2026-10-01T17:35:10.918Z |
| 2 | 01 | unmet-truth | experiments/cpu/cpu_adapter.c | 63 | CPU experiment does not compile: CPU_STOPPED macro collision and generated immediate OPER_I calls omit context; source adaptation halted after three correction attempts. | fixed |  | 2026-10-01T16:33:14.447Z | 2026-10-01T17:35:11.098Z |
| 3 | 01 | todo | third_party/musashi/m68kmake.c | 53 | Retained upstream TODOs and incomplete later-model instructions/timings are not qualified; compiled 68000 closure and semantic review remain pending. | waived | Later-model instructions and timings remain outside the bounded private 68000 experiment and are explicitly unsupported. The compiled 68000 closure and independent semantic review are complete; this records the retained upstream TODOs as an intentional scope deferral. | 2026-10-01T16:33:14.562Z | 2026-10-01T21:07:56.583Z |
| 4 | 01 | deviation | experiments/cpu/evidence/plan-01-02/irq-fault-counterexample.json |  | Odd IRQ stack host crash repaired within final adaptation attempt; regression and clean sanitizer evidence retained | fixed |  | 2026-10-01T18:01:10.588Z | 2026-10-01T18:01:36.109Z |
| 5 | 01 | deviation | experiments/cpu/evidence/plan-01-02/sanitizer-counterexample.json |  | UBSan test-bus pointer arithmetic repaired; fatal diagnostics enabled and affected lanes rerun clean | fixed |  | 2026-10-01T18:01:36.231Z | 2026-10-01T18:01:36.386Z |
| 6 | 01 | deviation | experiments/cpu/evidence/plan-01-03/reset-counterexamples.md |  | Reset debt, stale NMI and BSD address-error boundary counterexamples repaired within the final frozen attempt | fixed |  | 2026-10-01T18:25:33.135Z | 2026-10-01T18:25:33.314Z |
| 7 | 01 | deviation | experiments/cpu/evidence/plan-01-03/state-review-counterexamples.md |  | Inconsistent reset records and zero-request counter guard repaired with atomicity and no-op regressions | fixed |  | 2026-10-01T18:25:33.491Z | 2026-10-01T18:25:33.655Z |
| 8 | 01 | unmet-truth | experiments/owned_cpu/CONTRACT.md | 61 | F14-03: frozen ILLEGAL next-PC contract conflicts with implemented and tested fault-PC frame; user-directed canonical reconciliation required | open |  | 2026-10-03T01:37:56.782Z |  |

````json
[
  {
    "id": 1,
    "kind": "unrun-verify",
    "phase": "01",
    "file": ".planning/phases/01-cpu-acceptance-experiment/01-01-PLAN.md",
    "line": null,
    "description": "Task 1 guest/control CTests and Task 2 closure/budget controls remain unrun because the adapted backend does not compile.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-10-01T16:32:36.895Z",
    "resolved_at": "2026-10-01T17:35:10.918Z",
    "milestone": "v0.1"
  },
  {
    "id": 2,
    "kind": "unmet-truth",
    "phase": "01",
    "file": "experiments/cpu/cpu_adapter.c",
    "line": 63,
    "description": "CPU experiment does not compile: CPU_STOPPED macro collision and generated immediate OPER_I calls omit context; source adaptation halted after three correction attempts.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-10-01T16:33:14.447Z",
    "resolved_at": "2026-10-01T17:35:11.098Z",
    "milestone": "v0.1"
  },
  {
    "id": 3,
    "kind": "todo",
    "phase": "01",
    "file": "third_party/musashi/m68kmake.c",
    "line": 53,
    "description": "Retained upstream TODOs and incomplete later-model instructions/timings are not qualified; compiled 68000 closure and semantic review remain pending.",
    "status": "waived",
    "reason": "Later-model instructions and timings remain outside the bounded private 68000 experiment and are explicitly unsupported. The compiled 68000 closure and independent semantic review are complete; this records the retained upstream TODOs as an intentional scope deferral.",
    "recorded_at": "2026-10-01T16:33:14.562Z",
    "resolved_at": "2026-10-01T21:07:56.583Z",
    "milestone": "v0.1"
  },
  {
    "id": 4,
    "kind": "deviation",
    "phase": "01",
    "file": "experiments/cpu/evidence/plan-01-02/irq-fault-counterexample.json",
    "line": null,
    "description": "Odd IRQ stack host crash repaired within final adaptation attempt; regression and clean sanitizer evidence retained",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-10-01T18:01:10.588Z",
    "resolved_at": "2026-10-01T18:01:36.109Z",
    "milestone": "v0.1"
  },
  {
    "id": 5,
    "kind": "deviation",
    "phase": "01",
    "file": "experiments/cpu/evidence/plan-01-02/sanitizer-counterexample.json",
    "line": null,
    "description": "UBSan test-bus pointer arithmetic repaired; fatal diagnostics enabled and affected lanes rerun clean",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-10-01T18:01:36.231Z",
    "resolved_at": "2026-10-01T18:01:36.386Z",
    "milestone": "v0.1"
  },
  {
    "id": 6,
    "kind": "deviation",
    "phase": "01",
    "file": "experiments/cpu/evidence/plan-01-03/reset-counterexamples.md",
    "line": null,
    "description": "Reset debt, stale NMI and BSD address-error boundary counterexamples repaired within the final frozen attempt",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-10-01T18:25:33.135Z",
    "resolved_at": "2026-10-01T18:25:33.314Z",
    "milestone": "v0.1"
  },
  {
    "id": 7,
    "kind": "deviation",
    "phase": "01",
    "file": "experiments/cpu/evidence/plan-01-03/state-review-counterexamples.md",
    "line": null,
    "description": "Inconsistent reset records and zero-request counter guard repaired with atomicity and no-op regressions",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-10-01T18:25:33.491Z",
    "resolved_at": "2026-10-01T18:25:33.655Z",
    "milestone": "v0.1"
  },
  {
    "id": 8,
    "kind": "unmet-truth",
    "phase": "01",
    "file": "experiments/owned_cpu/CONTRACT.md",
    "line": 61,
    "description": "F14-03: frozen ILLEGAL next-PC contract conflicts with implemented and tested fault-PC frame; user-directed canonical reconciliation required",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-10-03T01:37:56.782Z",
    "resolved_at": null,
    "milestone": "v0.1"
  }
]
````
