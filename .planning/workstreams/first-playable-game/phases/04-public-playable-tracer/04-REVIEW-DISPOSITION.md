---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "Frontend smoke does not enforce the pinned fixture identity"
  - id: WR-02
    severity: warning
    disposition: open
    title: "Diagnostic path sanitization leaks path suffixes when paths contain spaces"
  - id: WR-03
    severity: warning
    disposition: open
    title: "Repository-backed receipt validation accepts forged file-content hashes"
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "[BLOCKER] Qualification receipt can identify the wrong source revision"
    source: "04-07-SUMMARY.md immutable source snapshot; 04-VERIFICATION.md current source identity finding"
open: 3
total: 4
recorded: 2026-10-08T03:23:56.000Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| CR-01 | critical | fixed | 04-07-SUMMARY.md immutable source snapshot; 04-VERIFICATION.md current source identity finding |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
