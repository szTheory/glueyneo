# Unsigned SDK release process

The root `.release-please-manifest.json` is the release version source. CMake
reads the same file when configuring the package. The pinned Release Please
configuration creates a draft and forces the version tag to exist so its target
can be checked before any artifact is trusted.

On each `main` push, the serialized release workflow runs Release Please and
queries GitHub for the manifest's tag even when the action reports no new
release. An absent release after an ordinary push is a no-op. An existing draft
is treated as a recovery candidate. A release tag must resolve to the exact
commit that the workflow tests, the version and tag must match the root manifest,
and every already uploaded asset must match the expected name, byte count, and
SHA-256. Matching partial uploads are retained and only missing assets are
uploaded. Extra, replaced, malformed, or published assets stop recovery without
deletion or replacement.

The workflow builds an offline source archive and complete static/shared SDK
archives on Linux x64, macOS arm64, and Windows x64. It writes
`release-manifest.json` with the exact source commit and final archive hashes,
then stages the five expected release assets in the draft. Three independent
hosted jobs download the GitHub release assets again, verify every archive
against the staged manifest, rebuild the downloaded source archive with
FetchContent disconnected, and run the installed diagnostic consumer against
that platform's downloaded SDK archive. The Linux job also scans the repository
history, downloaded archives, and rights inventory. A separate final job
rechecks the complete draft and publishes it only after all three downloaded
consumer jobs pass. No signing or notarization is performed.

The workflow uses a short-lived, repository-scoped GitHub App token only in
trusted release-control, staging, and final publication jobs. Configure the
repository App installation with contents write, pull request write, and issue
write for Release Please; the staging and publication jobs request contents
write only. Store the App ID and private key as `RELEASE_APP_ID` and
`RELEASE_APP_PRIVATE_KEY` Actions secrets. Build and downloaded-consumer jobs do
not receive those secrets or write permissions. Release Please's own action
output does not authorize publication; the API tag target, draft state, exact
asset inventory, downloaded bytes, rebuild, consumers, and content gate are
independent required checks.

For a failed staging or verification run, rerun that workflow run or dispatch
the workflow with the existing tag. Recovery still reads the root manifest and
requires its tag and version to match. The workflow does not depend on an event
triggered by the App token. It serializes by workflow ref and does not cancel an
in-progress release. Every publish attempt creates a fresh short-lived App token
and revalidates the draft after the consumer jobs finish.

## Current qualification boundary

The local recovery fixtures cover exact and partial drafts, retry lookup when
Release Please reports no new output, wrong tag targets, version disagreement,
published state, duplicate/extra/missing/replaced assets, unordered responses,
and downloaded-byte tampering. Local consumer tests also rebuild a source
archive offline and relocate installed packages. These checks qualify the
local release logic only. The repository has no configured remote or App
installation receipt, so GitHub runner identities, token and event behavior,
repository protections, hosted runner costs, and actual publication remain
pending until the workflow runs in the target repository. A clean scanner result
is detector evidence; the affirmative item-level records in
[`rights-inventory.md`](rights-inventory.md) remain the distribution-rights
authority, and any unresolved rights question blocks publication.

## Protected merge policy

Configure `main` as protected and require the `CI / ci-policy` aggregate with
strict up-to-date branches. The independent GSD code review is a separate
current-head gate: every proposed PR head needs a review bound to its full
commit SHA, and every finding must be fixed or have a written disposition
supported by evidence. Any head change invalidates both the review and checks
for merge readiness; rerun the review and require checks for the new SHA. Keep
security-review threat dispositions separate from code-review findings.

Use GitHub's native auto-merge after these controls are configured and observed.
Add a merge queue only if measured merge contention shows that strict branch
protection causes repeated integration failures. Triage relevant open issues and
PRs when repository authority is configured and again before shipping. Local
workflow tests establish parser and policy behavior only; they do not establish
protection, required-check, App, or event settings in GitHub.

The local policy receipt can be checked with:

```sh
python3 tools/workflow/ci_policy.py merge-readiness \
  --receipt merge-readiness.json --head-sha <full-pr-head-sha> \
  --output merge-readiness-result.json
```

The receipt uses `schema_version: 1`, `pr_head_sha`, `required_aggregate`, and
`independent_review`. The aggregate includes `sha`, `outcome`, `lane_count`,
and `assertion_count`; the review includes `sha`, `review_type` set to
`gsd-code-review`, `outcome`, and an explicit `findings` list. Each finding must
be `resolved` with resolution evidence, or `dispositioned` with both a
nonempty disposition and evidence reference. Both SHAs must equal the proposed
head, the aggregate and review must pass, and lane/assertion counts must be
positive. This local validator does not fetch GitHub receipts or grant merge
authority; attach the actual current-run/check and GSD review identifiers when
the hosted workflow is qualified.
