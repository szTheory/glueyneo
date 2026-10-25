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
then stages the five expected release assets in the draft. The trusted staging
job downloads those private draft assets with its scoped App token and verifies
all bytes against the expected manifest without extracting or executing them.
It relays the raw downloaded files as an immutable workflow artifact. Three
independent read-only hosted jobs receive and verify those same bytes, then
rebuild the downloaded source archive with
FetchContent disconnected, and run the installed diagnostic consumer against
that platform's downloaded SDK archive. The Linux job also scans the repository
history, downloaded archives, and rights inventory. A separate final job
rechecks the complete draft and publishes it only after all three downloaded
consumer jobs pass. No signing or notarization is performed.

The workflow uses a short-lived, repository-scoped GitHub App token only in
trusted release-control, staging, and final publication jobs. Configure the
repository App installation with contents write, pull request write, and issue
write for Release Please; the staging and publication jobs request contents
write only. Configure the nonsecret App ID as the `RELEASE_APP_ID` Actions
variable and store only the private key as the `RELEASE_APP_PRIVATE_KEY`
Actions secret. Build and downloaded-consumer jobs do not receive that secret
or write permissions. Release Please's own action
output does not authorize publication; the API tag target, draft state, exact
asset inventory, downloaded bytes, rebuild, consumers, and content gate are
independent required checks.

The existing Linux Clang CI job also builds an extracted source archive and
relocates its static/shared SDK consumers at a synthetic `9.8.7` release
version. The example carries the root manifest and keeps exact package-version
matching, so a version bump does not rely on rewriting consumer source. The
source archive includes the pinned runtime dependencies; installed SDKs retain
their applicable dependency notices. Hosted runtime cost has not yet been
measured.

For a failed staging or verification run, rerun that workflow run or dispatch
the workflow with the existing tag. Recovery still reads the root manifest and
requires its tag and version to match. The workflow does not depend on an event
triggered by the App token. It serializes by workflow ref and does not cancel an
in-progress release. Every publish attempt creates a fresh short-lived App token
and revalidates the draft after the consumer jobs finish. Matrix verification
keeps full command output only in the runner's private build logs. On failure it
prints and uploads a bounded diagnostic after path, identity, and credential
redaction plus a detector-negative check; the uploaded receipt records the
failed stage and exact source revision without adding successful counts.

## Draft lookup on recovery

The direct `Get a release by tag` lookup is retained for published releases. If
it returns 404, recovery makes read-only `List releases` requests and selects
only a case-sensitive exact `tag_name` match. GitHub documents that the list
includes draft releases only for users with push access. This fallback reads at
most five pages of 100 releases, uses a 10-second timeout per page request, and
rejects a response body larger than 8 MiB. Malformed entries, duplicate exact
tags, an unavailable list endpoint, or a full five-page result fail closed;
they are never treated as an absent release. The API lookup itself performs no
mutations. See GitHub's [Get a release by tag name](https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28#get-a-release-by-tag-name)
and [List releases](https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28#list-releases)
documentation.

On recovery, the tag must identify a full commit that is an ancestor of the
trusted workflow revision, and that tagged source's committed root manifest
must carry the expected version. Build and downloaded-consumer jobs check out
that tagged source; the trusted control, staging, and publication helpers run
from the workflow revision. A newly created release still requires the tag
commit to equal the tested workflow revision. Recovery does not retag commits. Packaging also uses the reviewed
workflow revision's helper through a separate sparse checkout; its `--repo`
and full `--commit` still select the immutable tagged source. This permits a
packager repair without substituting runtime or archive source. Windows CI
runs the archive, offline rebuild and relocated-consumer regression in its
existing MSVC job, alongside the installed SDK matrix. Compiler identity is
read from CMake's generated compiler metadata. Windows SDK packaging selects
Ninja explicitly inside the configured Visual Studio environment; MSVC remains
the compiler/librarian. The complete archive content scan and relocated
consumers qualify the output. The Visual Studio packaging attempt that exposed
a temporary profile path and the subsequent Ninja attempt that retained the
same finding remain failed results. Generator selection alone did not remove
the path.

Packaging now creates its extracted source, static/shared build trees and
install trees inside one automatically cleaned temporary child. Its parent is
the existing absolute `--workspace-dir` when supplied, otherwise `RUNNER_TEMP`
when nonempty, otherwise the system temporary directory. Windows packaging
rejects resolved drive paths beneath the known `Users` and
`Documents and Settings` profile roots (including extended drive paths) before
compilation: compiler or librarian metadata can retain source/build paths even
in Release libraries.
Use the CI runner's neutral temporary parent or provide an existing neutral
directory with `--workspace-dir` for a local Windows build. Relative parents
are rejected to avoid selecting different workspaces from different invocation
directories. Output archives still use `--output-dir`; workspace cleanup never
removes that parent directory. No finished binary is rewritten and the complete
archive content scan remains required. Windows success for this workspace
repair remains pending an exact-revision archive scan and relocated consumers.
This parent check does not recognize every custom or network profile layout;
the archive scanner remains the output gate for those paths too.

## Current qualification boundary

The local recovery fixtures cover exact and partial drafts, retry lookup when
Release Please reports no new output, wrong tag targets, version disagreement,
published state, duplicate/extra/missing/replaced assets, unordered responses,
and downloaded-byte tampering. Local consumer tests also rebuild a source
archive offline and relocate installed packages. These checks qualify the
local release logic only. The public
[szTheory/glueyneo repository](https://github.com/szTheory/glueyneo) now has
hosted CI and strict main protection. Exact observations and failed attempts
are recorded in the
[hosted qualification receipt](../.planning/phases/03-distributable-release-qualification/03-HOSTED-QUALIFICATION.md).
The owner reports a release App installed for this repository and the
`RELEASE_APP_ID` variable and `RELEASE_APP_PRIVATE_KEY` secret configured; the
[setup checkpoint](../.planning/phases/03-distributable-release-qualification/03-RELEASE-APP-SETUP.md)
records that report without inspecting the live permission grant or secret
value. App token/event behavior, first-time fork approval/execution, an
independently approved protected merge and actual release publication remain
pending.
A clean scanner result
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

## Effective release-token scope

Every trusted App-token job queries `GET /installation/repositories` and fails
unless exactly this repository is accessible. It records a small authority
receipt bound to source SHA, workflow run, job and installation ID, without
credential values or unexpected repository names. Redirects are refused before
forwarding authorization. The existing Linux Clang CI job exercises rejection
of broader/mismatched scope, malformed responses and missing job identities.

The receipt names the documented one-hour maximum installation-token lifetime
as an API contract, not a measured expiry. The pinned token action revokes its
token in its post-job step; actual revocation is checked in hosted job logs.
This effective job-token check does not inspect the App's installation-wide
grant. See the [installation-token API](https://docs.github.com/en/rest/apps/installations#list-repositories-accessible-to-the-app-installation)
and [pinned token action](https://github.com/actions/create-github-app-token/tree/bcd2ba49218906704ab6c1aa796996da409d3eb1).

## Staging-only recovery runs

A trusted manual dispatch defaults `publish` to false: it builds, stages and
checks the complete draft through all three downloaded consumers, then leaves
publication skipped. For an already staged current target, dispatch with
`reuse_build_run` pointing to its qualified build run and `publish=true`; all
verification gates run again before publication. A target whose workflow tree
differs from current main may require a broader GitHub App grant to publish;
prefer a fixed patch target with the current workflow tree instead of silently
expanding authority. Normal `main` push behavior remains automated. The input
cannot skip artifact identity, rights, scope or consumer checks.

Under user-approved PROJECT-D-50 (2026-10-25), independent GSD review of the
exact commit satisfies the review prerequisite without a second GitHub account.
Strict protected current-head checks and all trust/artifact gates remain
required. The live first-time fork approval/run stays unverified and deferred
until a contributor exists; the read-only/no-secret workflow and GitHub
first-time-contributor approval setting remain in place.

## Rerun staged verification without rebuilding archives

For an interrupted staging or downloaded-consumer job, rerun that job (or failed
jobs and dependents) within the original workflow run. Keep its successful build
jobs and their immutable archive artifacts; the current retention is three days.
A full new dispatch rebuilds archives and is not a promise of byte reproducibility
across host images or temporary build identities. Existing-asset digest mismatches
continue to reject replacement.

Authority and stage-manifest artifacts use attempt-specific names. Consumers and
publication download the manifest name emitted by the successful staging job,
which also supports rerunning a later consumer while staging remains completed.
A complete draft has no uploads to repeat. No-new-release control is qualified
with a fresh held dispatch; native job reruns exercise artifact reuse separately.

## Recover a held draft after a workflow repair

A fresh dispatch can pass `reuse_build_run` to retain already staged SDK bytes.
The read-only control validates that the initial-attempt origin is this repo's
completed main release workflow, with successful control, all three builds and
staging. Overall consumer failure is allowed because new consumers must run.
It rejects PR/fork origins, wrong workflow/version, nonancestor revisions,
changed packaging-helper bytes, duplicate or missing artifacts, expired
artifacts and malformed metadata. API reads are bounded; no artifact content
or token values are included in the metadata result. This is an immutable
origin contract, not a limit on development or verification runs.

Staging retrieves the three archive artifacts and the original trusted manifest
using a read-only Actions token. Its newly assembled source/tag/version/digest
manifest must match the original bytes exactly before any release asset write.
The scoped stage App token handles private-draft visibility, then the raw
hash-verified download goes to read-only consumer jobs. Downloaded SDK code
never receives the App private key or a write token. Both current manifest and
download artifact names come from the successful stage job and are unique per
attempt; later reruns can retain prior successful outputs.

The current origin adapter supports initial attempts with at most 100 jobs and
100 artifacts per metadata response, and the artifact retention is three days.
Missing/expired or unsupported origins fail closed; they do not authorize asset
replacement or a tag change. Native job reruns and fresh recovery dispatches
remain separate observed scenarios.

## Release path status

The always-started `release-policy` job checks the intended path, including a
qualified reused-build skip, successful staging and consumer jobs, and expected
publication or held publication. An active draft cannot pass solely because its
consumer matrix was skipped. A legitimate no-new-release path is reported as a
no-op without claiming a newly tested artifact source. Consumer and publication
jobs use `!cancelled()` with explicit dependency-result gates so cancellation
is honored and a deliberately skipped build matrix
does not suppress verification of reused archives.
