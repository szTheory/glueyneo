---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "Guide claim filter accepts affirmative frontend paraphrases"
  - id: WR-02
    severity: warning
    disposition: open
    title: "Evidence checker accepts a stale current qualification denominator"
  - id: WR-06
    severity: warning
    disposition: open
    title: "Frontend closure blacklist misses equivalent success claims [WARNING]"
  - id: WR-07
    severity: warning
    disposition: fixed
    title: "Evidence-map fixtures mask removal of the required verification sentence [WARNING]"
  - id: CR-03
    severity: critical
    disposition: fixed
    title: "Newline in diagnostic path exposes the remaining private path [BLOCKER]"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "Crosswalk disposition check accepts contradictory wording [WARNING]"
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
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "Repository-backed receipt validation accepts forged file-content hashes"
open: 3
total: 10
recorded: 2026-10-08T23:13:27.868Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-06 | warning | open | Post-fix independent review at `2a82c455f85671ba144a42923318c4ff7d53b9a2` still reproduces affirmative claims (“frontend booted the game and showed its output”; “controls worked as expected in RetroArch”) accepted by `check_docs()`; T-04-34 remains open. (not in the current review) |
| WR-07 | warning | fixed | Current mutation fixture reads the actual verification source row before mutation; source-derived checker rows reject removal and false closure (14-test suite). (not in the current review) |
| CR-03 | critical | fixed | Current qualification and frontend regressions remove the complete newline-containing private-path suffix at retained and printed sinks; reviewed at `9804351907e456b3ab85ebe4a49959c05b0714bb`. (not in the current review) |
| WR-05 | warning | fixed | Current checker reconciles normalized exact crosswalk state against disposition records and mutation tests reject contradiction/duplicates. (not in the current review) |
| CR-02 | critical | fixed | Plan 04-14 closes the raw-literal-quote case; fresh review confirms that specific suffix case is removed. CR-03 remains open for newline-containing paths. (not in the current review) |
| WR-04 | warning | fixed | Plan 04-14 adds Info/IN parsing and severity reconciliation; fresh review confirms this finding is addressed. (not in the current review) |
| CR-01 | critical | fixed | Plan 04-12 exact-integer receipt validation; absent from the fresh current review. (not in the current review) |
| WR-03 | warning | fixed | Repository receipt validates committed archive rows and rejects forged file rows after aggregate recomputation; current qualification regression passes. (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
