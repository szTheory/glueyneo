# Phase 03 hosted qualification receipts

**Status: pending external repository and account authority.** This file records
only observations made against the configured target repository. Local workflow
tests and YAML inspection do not qualify GitHub protections, hosted events, App
permissions, runner identities, or publication.

## Pending evidence

| Claim | Status | Exact evidence required | External actor |
| --- | --- | --- | --- |
| Repository identity and issue/PR triage | pending | Configured remote URL recorded in private operator configuration; public-safe repository identity, open issue/PR triage result, and date | Repository owner configures the remote and grants read access for triage |
| Protected `main` and strict current-SHA checks | pending | Ruleset/branch-protection receipt naming `CI / ci-policy`, strict up-to-date requirement, review requirement, and any bypass actors | Repository administrator |
| Independent current-head GSD review and merge | pending | PR number, exact head SHA, review record/run ID, all findings resolved or evidence-dispositioned, matching passing aggregate SHA, and observed protected merge commit | Maintainer with review and merge authority |
| Fork workflow approval and read-only boundary | pending | First-time fork PR run ID, approval event, effective token permissions, absence of secrets, and exact tested head SHA | Repository administrator approves the workflow under repository settings |
| Hosted CI support and cost | pending | Per-job run IDs and exact image/compiler/SDK/OS/architecture/configuration identities, source SHA, assertion/lane counts, cold-build duration, critical path, and runner-minutes | Repository maintainer triggers CI after remote setup |
| Release App installation and event behavior | pending | App installation/repository scope, requested permissions, token lifetime observation without token values, Release Please run ID, retry/no-new-release result, and same-workflow downstream job IDs | App owner and repository administrator |
| Draft, downloaded artifacts, and publication | pending | Tested commit/tag, expected asset inventory and SHA-256 values, download/consumer run IDs, source rebuild receipt, publication run ID, and downloaded published asset digest checks | Repository administrator enables trusted workflow credentials and runs release qualification |
| Hosted secret scanning and push protection | pending | Repository security-settings receipt naming enabled products/scope, or explicit disabled status | Repository administrator |

No remote is configured in this checkout, so no repository, PR, run, App, or
release identifiers can truthfully be recorded yet. Do not replace these rows
with simulated receipts or local fixture results.

## Local evidence that remains distinct

- CI classifier, aggregate, and merge-readiness policy controls run locally;
  they prove deterministic rejection behavior only.
- Release recovery fixtures cover exact draft identity and asset bytes; they do
  not exercise GitHub API authority or event delivery.
- The local matrix receipt at source `2054c3d6d07427d0e4a045b2388bcc933478bec9`
  records 36 cases, 1,440 assertions, nine lane executions, 9.374 seconds total
  lane duration, and 1.636 seconds for one clean build. It does not qualify a
  hosted support row or hosted runner cost.
- The bounded public-content scanner is detector evidence. Item-level
  redistribution status is governed by `docs/rights-inventory.md`; the scanner
  cannot establish legal permission. Any newly introduced item without
  affirmative rights evidence remains excluded and unknown.

## Resume condition

Resume the hosted portion of Plan 03-05 only after the repository remote,
protected repository, GitHub App installation, and necessary account authority
are available. Capture each receipt above against exact current commit/run IDs,
update the relevant documentation, then execute the plan's hosted acceptance
criteria. Keep DEL-02, DEL-03, DEL-04, and DEL-05 pending until their hosted
facts have been observed; local implementation does not complete them.
