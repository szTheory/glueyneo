---
phase: 04
review: 04-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: open
    title: "Private-path redaction and scan miss separator/encoding variants (confirmed)"
  - id: CR-02
    severity: critical
    disposition: open
    title: "`scan_public` is applied to `ensure_ascii` JSON, which defeats NFKC folding at every sink"
  - id: CR-03
    severity: critical
    disposition: open
    title: "Frontend-evidence inventory binding is skipped when `.git` is absent, including the documented `--clean --check-docs` path (confirmed)"
  - id: CR-04
    severity: critical
    disposition: open
    title: "`check_docs` passes affirmative success prose outside the generated status block (confirmed)"
  - id: CR-05
    severity: critical
    disposition: open
    title: "Crosswalk \"Existing Threat Scope\" accepts any non-empty text, including nonexistent paths (confirmed)"
  - id: CR-06
    severity: critical
    disposition: open
    title: "`check_security_register.py` reads only the first `threats_open` and only the first threat table (confirmed)"
  - id: CR-07
    severity: critical
    disposition: open
    title: "Outer timeout orphans the `start_new_session` RetroArch child; no pre-launch instance check (confirmed)"
  - id: CR-08
    severity: critical
    disposition: open
    title: "`main()` raises `AttributeError` on any early failure, so no receipt is written"
  - id: CR-09
    severity: critical
    disposition: open
    title: "Raw exception text is printed unredacted from `--record-frontend-evidence` and `--check-docs`"
  - id: WR-01
    severity: warning
    disposition: open
    title: "`write_frontend_records` is non-atomic and writes before validating its targets"
  - id: WR-02
    severity: warning
    disposition: open
    title: "`validate_frontend_evidence` does not type-check nested fields it later dereferences"
  - id: WR-03
    severity: warning
    disposition: open
    title: "`Runner.command` timeout kills only the direct child"
  - id: WR-04
    severity: warning
    disposition: open
    title: "Screenshot handling is racy and can raise uncaught non-`SmokeBlocked` exceptions"
  - id: WR-05
    severity: warning
    disposition: open
    title: "Unbounded read of non-GNMV content before the size check"
  - id: WR-06
    severity: warning
    disposition: open
    title: "`private_paths` fails closed on benign text (self-inflicted false positives)"
  - id: WR-07
    severity: warning
    disposition: open
    title: "Product CTest couples to planning state and a hard-coded workstream; `block_on` is brittle"
  - id: WR-08
    severity: warning
    disposition: open
    title: "`glueyneo_runtime_static` duplicates runtime state and the configure-time guard is heuristic"
  - id: WR-09
    severity: warning
    disposition: open
    title: "Local `git` invocations use the caller's environment"
  - id: IN-01
    severity: info
    disposition: open
    title: "Stale and contradictory guide text"
  - id: IN-02
    severity: info
    disposition: open
    title: "Dead or redundant code in `retroarch_smoke.py`"
  - id: IN-03
    severity: info
    disposition: open
    title: "Minor issues in `check_package.py`"
  - id: IN-04
    severity: info
    disposition: open
    title: "Test-oracle gaps that let the confirmed defects through"
  - id: WR-10
    severity: warning
    disposition: fixed
    title: "Evidence-map mutation tests fail before exercising their target"
  - id: WR-11
    severity: warning
    disposition: fixed
    title: "Review identity parser accepts duplicate revision keys"
open: 22
total: 24
recorded: 2026-10-10T12:57:15.286Z
---

# Phase 04: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | open | - |
| CR-02 | critical | open | - |
| CR-03 | critical | open | - |
| CR-04 | critical | open | - |
| CR-05 | critical | open | - |
| CR-06 | critical | open | - |
| CR-07 | critical | open | - |
| CR-08 | critical | open | - |
| CR-09 | critical | open | - |
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| WR-06 | warning | open | - |
| WR-07 | warning | open | - |
| WR-08 | warning | open | - |
| WR-09 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| WR-10 | warning | fixed | Independent clean review at `04-REVIEW.md`, revision `007f331b1507331382826e779218d39a5f31fab4`, confirms the current validation row, 24/24 source-derived mutation suite, and target-specific rejection assertions; the original frozen finding at `1781f47c1331b4d5acb7ea52873c3e4125fbca96` is resolved. (not in the current review) |
| WR-11 | warning | fixed | Independent clean review at `04-REVIEW.md`, revision `007f331b1507331382826e779218d39a5f31fab4`, confirms exact-one-key parsing and regressions for valid/malformed duplicates and malformed sole values; the original frozen finding at `1781f47c1331b4d5acb7ea52873c3e4125fbca96` is resolved. The separate WR-09/T-04-43 scope threat remains open. (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
