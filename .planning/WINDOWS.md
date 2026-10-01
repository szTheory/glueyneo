---
schema_version: 1
open_count: 3
waived_count: 0
fixed_count: 0
total_count: 3
last_updated: 2026-10-01T16:33:14.562Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 01 | unrun-verify | .planning/phases/01-cpu-acceptance-experiment/01-01-PLAN.md |  | Task 1 guest/control CTests and Task 2 closure/budget controls remain unrun because the adapted backend does not compile. | open |  | 2026-10-01T16:32:36.895Z |  |
| 2 | 01 | unmet-truth | experiments/cpu/cpu_adapter.c | 63 | CPU experiment does not compile: CPU_STOPPED macro collision and generated immediate OPER_I calls omit context; source adaptation halted after three correction attempts. | open |  | 2026-10-01T16:33:14.447Z |  |
| 3 | 01 | todo | third_party/musashi/m68kmake.c | 53 | Retained upstream TODOs and incomplete later-model instructions/timings are not qualified; compiled 68000 closure and semantic review remain pending. | open |  | 2026-10-01T16:33:14.562Z |  |

````json
[
  {
    "id": 1,
    "kind": "unrun-verify",
    "phase": "01",
    "file": ".planning/phases/01-cpu-acceptance-experiment/01-01-PLAN.md",
    "line": null,
    "description": "Task 1 guest/control CTests and Task 2 closure/budget controls remain unrun because the adapted backend does not compile.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-10-01T16:32:36.895Z",
    "resolved_at": null,
    "milestone": "v0.1"
  },
  {
    "id": 2,
    "kind": "unmet-truth",
    "phase": "01",
    "file": "experiments/cpu/cpu_adapter.c",
    "line": 63,
    "description": "CPU experiment does not compile: CPU_STOPPED macro collision and generated immediate OPER_I calls omit context; source adaptation halted after three correction attempts.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-10-01T16:33:14.447Z",
    "resolved_at": null,
    "milestone": "v0.1"
  },
  {
    "id": 3,
    "kind": "todo",
    "phase": "01",
    "file": "third_party/musashi/m68kmake.c",
    "line": 53,
    "description": "Retained upstream TODOs and incomplete later-model instructions/timings are not qualified; compiled 68000 closure and semantic review remain pending.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-10-01T16:33:14.562Z",
    "resolved_at": null,
    "milestone": "v0.1"
  }
]
````
