# Phase 03 hosted qualification receipts

**Status: repository created; remaining hosted qualification pending.** This file records
only observations made against the configured target repository. Local workflow
tests and YAML inspection do not qualify GitHub protections, hosted events, App
permissions, runner identities, or publication.

## Pending evidence

| Claim | Status | Exact evidence required | External actor |
| --- | --- | --- | --- |
| Repository identity and issue/PR triage | observed 2026-10-06 | Public repository [szTheory/glueyneo](https://github.com/szTheory/glueyneo), owner-authorized creation with GitHub CLI; administrator authority observed; zero open issues and PRs at setup | Repository owner |
| Protected `main` and strict current-SHA checks | pending | Ruleset/branch-protection receipt naming `CI / ci-policy`, strict up-to-date requirement, review requirement, and any bypass actors | Repository administrator |
| Independent current-head GSD review and merge | pending | PR number, exact head SHA, review record/run ID, all findings resolved or evidence-dispositioned, matching passing aggregate SHA, and observed protected merge commit | Maintainer with review and merge authority |
| Fork workflow approval and read-only boundary | pending | First-time fork PR run ID, approval event, effective token permissions, absence of secrets, and exact tested head SHA | Repository administrator approves the workflow under repository settings |
| Hosted CI support and cost | pending | Per-job run IDs and exact image/compiler/SDK/OS/architecture/configuration identities, source SHA, assertion/lane counts, cold-build duration, critical path, and runner-minutes | Repository maintainer triggers CI after remote setup |
| Release App installation and event behavior | pending | App installation/repository scope, requested permissions, token lifetime observation without token values, Release Please run ID, retry/no-new-release result, and same-workflow downstream job IDs | App owner and repository administrator |
| Draft, downloaded artifacts, and publication | pending | Tested commit/tag, expected asset inventory and SHA-256 values, download/consumer run IDs, source rebuild receipt, publication run ID, and downloaded published asset digest checks | Repository administrator enables trusted workflow credentials and runs release qualification |
| Hosted secret scanning and push protection | enabled configuration observed | GitHub repository API reports `secret_scanning.status=enabled` and `secret_scanning_push_protection.status=enabled`; non-provider patterns and validity checks disabled; no live credential canary tested | Repository administrator |

The repository and `origin` remote now exist. No source had been pushed when
the publication audit was captured. Plan 03-05 Task 2 remains incomplete;
App installation/token authority, fork approval and protected merge/release
events have not been observed. No repository secrets are configured. The
current CLI authentication cannot list App installations; this does not prove
that the account has none. Do not substitute local fixtures for hosted receipts.

Before source publication, the isolated publication history passed the complete
bounded scan and complementary literal-home check: 351 tracked files and
1,106 unique historical blobs. See `03-PUBLICATION-AUDIT.json` and
`03-PUBLICATION-COMMIT-MAP.txt`. The original private local refs are retained
and must never be pushed. Historical receipts keep their original identities.

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

## CHECKPOINT REACHED

**Type:** human-verify
**Gate:** blocking-human
**Plan:** 03-05
**Progress:** 1/2 tasks complete

**Current task:** Task 2, “Qualify hosted repository authority and release
events,” remains incomplete pending observed repository protections, App
installation/token authority, fork approval, and protected merge/publication
events. The public repository and sanitized publication branch are prepared;
no unobserved hosted outcome is claimed.

**Awaiting:** configure and observe the hosted authority for
`szTheory/glueyneo`, then capture the exact run, ruleset, review, App-scope, and published-asset
receipts listed above. Keep this plan and mapped delivery requirements
incomplete until those facts have been observed.
