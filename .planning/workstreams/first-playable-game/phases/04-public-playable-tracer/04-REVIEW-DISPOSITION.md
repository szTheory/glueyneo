---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
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
open: 5
total: 8
recorded: 2026-10-08T15:13:58Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-03 | critical | open | Fresh post-04-14 review reproduces a newline-boundary suffix leak through both sanitizers and their diagnostic sinks. |
| WR-05 | warning | open | Fresh review shows contradictory crosswalk wording can satisfy the open-state check. |
| WR-01 | warning | open | Historical checker issue remains carried without independent disposition evidence. |
| CR-02 | critical | fixed | Plan 04-14 closes the raw-literal-quote case; fresh review confirms that specific suffix case is removed. CR-03 remains open for newline-containing paths. |
| WR-04 | warning | fixed | Plan 04-14 adds Info/IN parsing and severity reconciliation; fresh review confirms this finding is addressed. |
| CR-01 | critical | fixed | Plan 04-12 exact-integer receipt validation; absent from the fresh current review. |
| WR-02 | warning | open | Carried from the earlier review without independent disposition evidence; its path-sanitization scope overlaps CR-03. |
| WR-03 | warning | open | Carried from the earlier review without independent disposition evidence; no separate threat scope was newly established. |

`open` means recorded and unresolved; `fixed`, `skipped`, and `deferred` preserve explicit prior decisions. A finding absent from a fresh narrative review remains in this ledger with its provenance and actual disposition. Reused IDs are reconciled against the current narrative and do not silently inherit an older finding's decision.
