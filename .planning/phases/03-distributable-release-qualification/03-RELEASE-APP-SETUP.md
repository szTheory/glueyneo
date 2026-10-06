# Release App setup checkpoint

The owner confirmed on 2026-10-06 that there is no existing release App.
Repository creation and CI do not establish this separate release authority.
No App credential has been created, stored, or printed by this execution.

Register a private GitHub App for the `szTheory` account using
[GitHub's registration page](https://github.com/settings/apps/new):

- Name: `szTheory-glueyneo-release` (use an available equivalent if occupied).
- Homepage: `https://github.com/szTheory/glueyneo`.
- Webhook: inactive; this App authenticates workflow API calls.
- Repository permissions: Contents, Issues, and Pull requests, each read/write;
  Metadata read is implicit. No organization or account permissions.
- Installation: only this account, selected repository `szTheory/glueyneo`.
- User authorization during installation: unnecessary for installation tokens.

Generate a private key in the App settings and store it directly in the
repository Actions secret `RELEASE_APP_PRIVATE_KEY`. Store the public numeric
App ID in the Actions variable `RELEASE_APP_ID`. Do not paste key or token
values into chat, Git, logs, issues, or pull requests. Record only the public
App ID, installation ID, repository selection and permissions in qualification
receipts.

The pinned token action requests only this repository and job-specific
permissions. GitHub documents installation tokens as expiring after one hour;
the token action's post-job revocation and actual scope/expiration remain
unobserved until the trusted workflow runs. Capture that behavior without token
values. Keep strict branch protection in force; an App credential does not
authorize bypassing the current-head checks or independent review.

The remaining hosted acceptance also needs an independent approval of PR #1
after its final push and a first-time fork contributor to exercise approval and
read-only/no-secret execution. Those facts cannot be simulated by the owner
account's trusted PR or a local test. After account setup, resume
`$gsd-execute-phase 03` to observe the protected merge, Release Please draft,
retry, downloaded consumers and publication against exact source/asset hashes.

References checked 2026-10-06:
[App registration](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app),
[installation token scope and expiration](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).
