# Release App setup and qualification checkpoint

## Owner-reported setup (2026-10-07)

The owner reports that a GitHub App with public App ID `5217741` is installed
for `szTheory/glueyneo`. The owner also reports that repository Actions secret
`RELEASE_APP_PRIVATE_KEY` and variable `RELEASE_APP_ID` are set, with the
variable corrected to the App ID. These are user-reported setup facts; this
execution did not inspect the live App settings, Actions secret, or variable
value. No private key or token value is recorded here.

## Expected App configuration

The registration checklist for the private App under `szTheory` is:

- Name: `szTheory-glueyneo-release` (use an available equivalent if occupied).
- Homepage: `https://github.com/szTheory/glueyneo`.
- Webhook: inactive; this App authenticates workflow API calls.
- Repository permissions: Contents, Issues, and Pull requests, each read/write;
  Metadata read is implicit. No organization or account permissions.
- Installation: only this account, selected repository `szTheory/glueyneo`.
- User authorization during installation: unnecessary for installation tokens.

The actual permission selection and grant have not been independently observed
and remain pending qualification. The pinned token action requests only this
repository and job-specific permissions. GitHub documents installation tokens
as expiring after one hour; the token action's post-job revocation and actual
scope/expiration remain unobserved until the trusted workflow runs. Capture
that behavior without token values. Keep strict branch protection in force; an
App credential does not authorize bypassing current-head checks or independent
review.

## Remaining hosted evidence

Hosted acceptance still needs a first-time fork contributor to exercise
workflow approval and the read-only/no-secret boundary, plus an independent
approval of PR #1 after its final push. Those facts cannot be simulated by the
owner's trusted PR or a local test. After those actors are available, qualify
the protected merge, Release Please draft, retry, downloaded consumers, and
publication against exact source and asset hashes.

References checked 2026-10-06:
[App registration](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app),
[installation token scope and expiration](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).
