---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
  - id: CR-02
    severity: critical
    disposition: open
    title: "Quoted private paths still expose filename suffixes [BLOCKER]"
  - id: WR-01
    severity: warning
    disposition: open
    title: "Validation-map checks require historical findings to stay reported and open [WARNING]"
  - id: CR-01
    severity: critical
    disposition: open
    title: "Boolean byte counts bypass repository receipt equality"
  - id: WR-02
    severity: warning
    disposition: open
    title: "Diagnostic path sanitization leaks path suffixes when paths contain spaces"
  - id: WR-03
    severity: warning
    disposition: open
    title: "Repository-backed receipt validation accepts forged file-content hashes"
open: 5
total: 5
recorded: 2026-10-08T12:09:32.441Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-02 | critical | open | - |
| WR-01 | warning | open | - |
| CR-01 | critical | open | 04-REVIEW.md: current finding; prior CR-01 fixed decision refers to a different finding ID/title (not in the current review) |
| WR-02 | warning | open | - (not in the current review) |
| WR-03 | warning | open | - (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
