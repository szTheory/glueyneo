---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
  - id: WR-09
    severity: warning
    disposition: open
    title: "Review provenance gate accepts unsupported extra file claims"
  - id: WR-10
    severity: warning
    disposition: fixed
    title: "Evidence-map mutation tests fail before exercising their target"
  - id: WR-11
    severity: warning
    disposition: fixed
    title: "Review identity parser accepts duplicate revision keys"
  - id: WR-08
    severity: warning
    disposition: open
    title: "Frontend output claim filter misses common success wording"
  - id: WR-01
    severity: warning
    disposition: open
    title: "Guide claim filter accepts affirmative frontend paraphrases"
  - id: WR-02
    severity: warning
    disposition: fixed
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
open: 4
total: 14
recorded: 2026-10-09T01:01:14.211Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-09 | warning | open | Current standard-depth review at `04-REVIEW.md`, revision `48befe7a92d7c545e7c900c57e027b9e15952a7f`, reproduced acceptance of a nonexistent extra review path; retain open pending exact-scope enforcement. |
| WR-08 | warning | open | Independent review at `04-REVIEW.md`, revision `f1c8a1de5f25224b83da6ec9e4bc40bf51a249ae`, exercised the control-success counterexample; the current claim parser and 22 mutation tests reject it while preserving explicit unknown evidence. Retain open pending broader review/disposition. (not in the current review) |
| WR-01 | warning | open | Historical review `04-REVIEW.md` at `87f8d4c`; reviewed revision `870848e553aca6e43f6fec8ae0acefac87270f5b`, 2026-10-08T23:46:34Z; carried open; the warning remains open pending the separately directed actual frontend evidence. (not in the current review) |
| WR-02 | warning | fixed | Independent current-revision review `04-REVIEW.md` at `870848e553aca6e43f6fec8ae0acefac87270f5b` inspected checker and mutation test; live qualification 25/25, 15/15 mutation tests reject stale 23/23, and direct checker passes. (not in the current review) |
| WR-06 | warning | open | The independent review at revision `f1c8a1de5f25224b83da6ec9e4bc40bf51a249ae` verified current tests reject “frontend booted the game and showed its output,” control-success wording, and a copied guide's “Guest pixels were displayed” claim. Retain open under medium/open T-04-34 pending separate security disposition. (not in the current review) |
| WR-07 | warning | fixed | Current mutation fixture reads the actual verification source row before mutation; source-derived checker rows reject removal and false closure (14-test suite). (not in the current review) |
| CR-03 | critical | fixed | Current qualification and frontend regressions remove the complete newline-containing private-path suffix at retained and printed sinks; reviewed at `9804351907e456b3ab85ebe4a49959c05b0714bb`. (not in the current review) |
| WR-05 | warning | fixed | Current checker reconciles normalized exact crosswalk state against disposition records and mutation tests reject contradiction/duplicates. (not in the current review) |
| CR-02 | critical | fixed | Plan 04-14 closes the raw-literal-quote case; fresh review confirms that specific suffix case is removed. CR-03 remains open for newline-containing paths. (not in the current review) |
| WR-04 | warning | fixed | Plan 04-14 adds Info/IN parsing and severity reconciliation; fresh review confirms this finding is addressed. (not in the current review) |
| CR-01 | critical | fixed | Plan 04-12 exact-integer receipt validation; absent from the fresh current review. (not in the current review) |
| WR-03 | warning | fixed | Repository receipt validates committed archive rows and rejects forged file rows after aggregate recomputation; current qualification regression passes. (not in the current review) |
| WR-10 | warning | fixed | Independent clean review at `04-REVIEW.md`, revision `007f331b1507331382826e779218d39a5f31fab4`, confirms the current validation row, 24/24 source-derived mutation suite, and target-specific rejection assertions; the original frozen finding at `1781f47c1331b4d5acb7ea52873c3e4125fbca96` is resolved. |
| WR-11 | warning | fixed | Independent clean review at `04-REVIEW.md`, revision `007f331b1507331382826e779218d39a5f31fab4`, confirms exact-one-key parsing and regressions for valid/malformed duplicates and malformed sole values; the original frozen finding at `1781f47c1331b4d5acb7ea52873c3e4125fbca96` is resolved. The separate WR-09/T-04-43 scope threat remains open. |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
