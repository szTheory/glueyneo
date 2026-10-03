---
phase: 01
review: 01-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: open
    title: "Continuation rejects reachable state after a supported RTE"
  - id: CR-02
    severity: critical
    disposition: open
    title: "Earlier exceeded churn can disappear behind a lower final entry"
  - id: WR-01
    severity: warning
    disposition: open
    title: "Sealing rejects resource totals allowed by the frozen validator"
  - id: WR-02
    severity: warning
    disposition: open
    title: "README says the implemented owned runtime does not exist"
open: 4
total: 4
recorded: 2026-10-03T21:38:27.247Z
---

# Phase 01: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | open | - |
| CR-02 | critical | open | - |
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
