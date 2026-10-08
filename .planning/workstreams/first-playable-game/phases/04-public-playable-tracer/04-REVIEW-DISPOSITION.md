---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
  - id: CR-02
    severity: critical
    disposition: open
    title: "Literal quotes inside private paths still expose suffixes [BLOCKER]"
  - id: WR-04
    severity: warning
    disposition: open
    title: "Validation-map parser rejects valid Info findings [WARNING]"
  - id: WR-01
    severity: warning
    disposition: open
    title: "Validation-map checks require historical findings to stay reported and open [WARNING]"
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
total: 6
recorded: 2026-10-08T13:13:20Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-02 | critical | open | 04-SECURITY.md and 04-REVIEW.md independently reproduce the suffix leak; unresolved pending a fix |
| WR-04 | warning | open | 04-REVIEW.md current finding; parser grammar gap awaits plan |
| WR-01 | warning | open | 04-REVIEW.md current finding; implementation awaits independent code-review audit (not in the current review) |
| CR-01 | critical | fixed | Plan 04-12 exact-integer receipt validation and focused regression; absent from the fresh current review |
| WR-02 | warning | open | Carried from the earlier review with no independent disposition evidence; open. No separate threat scope. (not in the current review) |
| WR-03 | warning | open | Carried from the earlier review with no independent disposition evidence; open. (not in the current review) |

`open` means recorded and unresolved; `fixed`, `skipped`, and `deferred` preserve explicit prior decisions. A finding absent from a fresh narrative review remains in this ledger with its provenance and actual disposition. Reused IDs are reconciled against the current narrative and do not silently inherit an older finding's decision.
