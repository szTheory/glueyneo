---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
  - id: WR-06
    severity: warning
    disposition: open
    title: "Frontend closure blacklist misses equivalent success claims [WARNING]"
  - id: WR-07
    severity: warning
    disposition: open
    title: "Evidence-map fixtures mask removal of the required verification sentence [WARNING]"
  - id: CR-03
    severity: critical
    disposition: open
    title: "Newline in diagnostic path exposes the remaining private path [BLOCKER]"
  - id: WR-05
    severity: warning
    disposition: open
    title: "Crosswalk disposition check accepts contradictory wording [WARNING]"
  - id: WR-01
    severity: warning
    disposition: open
    title: "Validation-map checks require historical findings to stay reported and open [WARNING]"
  - id: CR-02
    severity: critical
    disposition: fixed
    title: "Raw literal quotes inside private paths exposed suffixes [BLOCKER]"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "Validation-map parser rejected valid Info findings [WARNING]"
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "Boolean byte count bypass fixed by exact integer validation"
  - id: WR-02
    severity: warning
    disposition: open
    title: "Diagnostic path sanitization leaks path suffixes when paths contain spaces"
  - id: WR-03
    severity: warning
    disposition: open
    title: "Repository-backed receipt validation accepts forged file-content hashes"
open: 7
total: 10
recorded: 2026-10-08T17:39:55.739Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-06 | warning | open | 04-REVIEW.md current |
| WR-07 | warning | open | 04-REVIEW.md current |
| CR-03 | critical | open | Fresh post-04-14 review reproduces a newline-boundary suffix leak through both sanitizers and their diagnostic sinks. (not in the current review) |
| WR-05 | warning | open | Fresh review shows contradictory crosswalk wording can satisfy the open-state check. (not in the current review) |
| WR-01 | warning | open | Historical checker issue remains carried without independent disposition evidence. (not in the current review) |
| CR-02 | critical | fixed | Plan 04-14 closes the raw-literal-quote case; fresh review confirms that specific suffix case is removed. CR-03 remains open for newline-containing paths. (not in the current review) |
| WR-04 | warning | fixed | Plan 04-14 adds Info/IN parsing and severity reconciliation; fresh review confirms this finding is addressed. (not in the current review) |
| CR-01 | critical | fixed | Plan 04-12 exact-integer receipt validation; absent from the fresh current review. (not in the current review) |
| WR-02 | warning | open | Carried from the earlier review without independent disposition evidence; its path-sanitization scope overlaps CR-03. (not in the current review) |
| WR-03 | warning | open | Carried from the earlier review without independent disposition evidence; no separate threat scope was newly established. (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
