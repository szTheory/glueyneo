# Phase 03: Distributable release qualification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-06
**Phase:** 03-distributable release qualification
**Areas discussed:** Platform support and CI matrix, Trusted PR checks and merge authority, Release staging/recovery/publication, Public-content/privacy/licensing gate

---

## Platform support and CI matrix

| Option | Description | Selected |
|--------|-------------|----------|
| Desktop trio | Linux x64 (Clang/GCC), macOS arm64 (AppleClang), Windows x64 (MSVC) | ✓ |
| Linux only | GCC and Clang; other platforms untested | |
| Linux + macOS | Defer Windows | |

| Option | Description | Selected |
|--------|-------------|----------|
| Core + installed consumers everywhere | Sanitizers and fuzz on Linux Clang | ✓ |
| Full suite everywhere | Run each supported check on every platform/toolchain | |
| Linux full, others smoke | Build and diagnostic smoke on macOS and Windows | |

| Option | Description | Selected |
|--------|-------------|----------|
| Exact tested baseline | Claim one exact compiler/SDK baseline per platform and expand on evidence | ✓ |
| Version range | Specify minimum and current compiler/SDK versions on each platform | |
| Other range | Choose another compatibility range | |

| Option | Description | Selected |
|--------|-------------|----------|
| Conservative classifier | Relevant changes run the matrix; unknown paths run all lanes | ✓ |
| Full matrix for every tracked change | Simplest selection rules; highest recurring CI cost | |
| Runtime/API-only classifier | Only runtime/API changes run the matrix | |

**User's choice:** Desktop trio; core diagnostics and installed consumers everywhere with sanitizer/fuzz on Linux Clang; exact exercised baselines; conservative classifier.
**Notes:** Implement Windows shared-export inspection before claiming Windows qualification. Keep the aggregate always started and do not use workflow-level path filters to skip required status.

---

## Trusted PR checks and merge authority

| Option | Description | Selected |
|--------|-------------|----------|
| Native auto-merge first | Protected main, strict current-revision checks and review; add a queue if contention warrants it | ✓ |
| Merge queue from the start | Require queue participation for every protected merge | |
| Manual merge | Human merges after checks | |

| Option | Description | Selected |
|--------|-------------|----------|
| GitHub App + read-only PR token | App token for trusted writes; read-only `GITHUB_TOKEN`, no secrets for `pull_request` validation | ✓ |
| GITHUB_TOKEN only | Keep follow-on validation in the same trusted run | |
| Fine-grained PAT | Use a PAT for write automation | |

| Option | Description | Selected |
|--------|-------------|----------|
| GSD review per exact PR SHA | Block merge until findings are fixed or evidence-backed and the current SHA passes review | ✓ |
| Human GitHub approval | Require a human approval on every PR | |
| Independent review App | Install a separate review App as required check | |

| Option | Description | Selected |
|--------|-------------|----------|
| First-time approval safeguard | Keep GitHub's first-time contributor workflow approval; then run read-only checks without secrets | ✓ |
| Auto-run every fork PR | Use read-only permissions without first-time approval | |
| Approve every external contributor | Require approval for each external contributor | |

**User's choice:** Native auto-merge first; GitHub App for write jobs and read-only token for PR validation; separate GSD review per PR SHA; first-time fork workflow approval safeguard.
**Notes:** The user explicitly selected the first three recommendations and then said “auto follow ur recs,” which authorizes the remaining recommended default. No remote/App authority is configured yet; hosted behavior remains unqualified.

---

## Release staging, recovery, and publication

| Option | Description | Selected |
|--------|-------------|----------|
| Single manifest version source | Root `.release-please-manifest.json` is canonical; CMake/package metadata reads it | ✓ |
| Duplicated version fields | Manually synchronize release manifest and `CMakeLists.txt` | |
| Source-only distribution | Publish source and ask consumers to rebuild all SDK artifacts | |

| Option | Description | Selected |
|--------|-------------|----------|
| Exact-commit complete draft | Stage offline source and tested platform SDK artifacts against the tested commit | ✓ |
| Build on each retry | Restart staging from scratch after every interruption | |
| Publish then verify | Verify the consumer and digests after publication | |

| Option | Description | Selected |
|--------|-------------|----------|
| Idempotent recovery and gates | Resume only matching drafts/assets; verify digests and downloaded consumer before publication | ✓ |
| Tag/release event chaining | Depend on an event emitted by the release workflow's `GITHUB_TOKEN` | |
| Local-only authority claim | Treat local workflow validation as proof of hosted release authority | |

**User's choice:** “Auto follow ur recs” — accepted the synthesized recommendation for a single version source, complete exact-commit draft, idempotent recovery, downloaded-consumer/digest gates, and real hosted authority qualification.
**Notes:** Draft/tag behavior varies with release-please configuration. Keep explicit same-workflow dependencies and qualify the selected pinned action/schema. Do not claim hosted release authority until the actual configured repository is exercised.

---

## Public-content, privacy, and licensing gate

| Option | Description | Selected |
|--------|-------------|----------|
| Small stdlib scanner | Scan publishable source, history identity, CI logs, and bounded archives; use canaries and a hosted secret-scanning backstop where enabled | ✓ |
| Dedicated scanner only | Add pinned Gitleaks as the sole scanner | |
| Hosted scanning only | Rely only on GitHub secret scanning | |

| Option | Description | Selected |
|--------|-------------|----------|
| Observable checks plus rights evidence | Automate notices/privacy/content checks; require external rights evidence when file contents cannot establish permission | ✓ |
| Treat clean scan as rights proof | Infer redistribution rights from a clean scan | |
| Manual inspection of every item | Require a human to inspect all source and archives for each privacy criterion | |

**User's choice:** “Auto follow ur recs” — accepted the small auditable stdlib scanner, allowlisted fixture/dependency inventory, fail-closed bounded archive checks, redacted findings, synthetic canaries, and explicit scanner limitations. Use hosted secret scanning only as an actual additional backstop; keep unresolved rights unknown until supported by provenance/license evidence.
**Notes:** A clean scan does not prove every secret is absent or establish legal rights. Add a new scanner dependency only if concrete canary/history results justify it.

---

## the agent's Discretion

- Select exact pinned action and tool versions from current primary documentation and actual runner evidence.
- Choose a Windows symbol inspector with parity to the current Linux/macOS checks.
- Design the classifier, artifact manifest, bounded archive inspection, and CI parallelism around the local verification entrypoint and measured cost.
- Keep hosted/repository authority, first-time fork approval, and unresolved redistribution permission as narrow external evidence needs.

## Deferred Ideas

None.
