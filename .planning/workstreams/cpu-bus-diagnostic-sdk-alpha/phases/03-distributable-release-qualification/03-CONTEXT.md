# Phase 03: Distributable release qualification - Context

**Gathered:** 2026-10-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Qualify an unsigned, offline-rebuildable and relocatable diagnostic SDK release bound to a tested commit. Establish truthful, exact compiler/SDK/OS/architecture/build claims; always-started required CI with cost evidence; protected current-revision PR checks and independent review; recoverable complete release staging and downloaded-consumer verification; and public-content evidence for notices, privacy, and excluded material.

This phase does not qualify game/BIOS compatibility, hardware behavior beyond the accepted diagnostic subset, signing/notarization, or untested platform/version combinations. The repository has no configured remote, hosted CI, branch protection, GitHub App, or release authority. Those are future delivery dependencies, not blockers to local/package implementation; keep authority- and event-dependent requirements pending until exercised against the real repository.
</domain>

<decisions>
## Implementation Decisions

### Platform support and CI matrix
- **D-01:** Qualify Linux x64 with Clang and GCC, macOS arm64 with AppleClang, and Windows x64 with MSVC. Run core diagnostics and installed consumers on all three operating systems; run sanitizer and fuzz lanes on Linux Clang.
- **D-02:** Publish only exact exercised compiler, SDK, OS, architecture, configuration, and build identities. Expand the support claim when new evidence exists; do not infer a compatibility range from one green lane.
- **D-03:** Keep an always-started required aggregate and classify changes inside the workflow. Relevant source/build/package/release changes run the portability matrix; known documentation-only changes still run documentation/privacy checks; unknown paths run every lane. Do not use workflow-level path filters that can omit the required aggregate. Record actual lane/assertion counts, cold-build duration, critical path, and runner minutes.
- **D-04:** Implement Windows shared-export inspection so the consumer check proves the same public/private symbol contract on all supported platforms; an unsupported inspector must fail rather than silently skip.

### Trusted PR checks and merge authority
- **D-05:** Validate `pull_request` code with a read-only `GITHUB_TOKEN`, no secrets, and no write authority. Keep fork execution separated from trusted write/release jobs; retain GitHub's first-time contributor workflow-approval safeguard, then run read-only checks.
- **D-06:** Use protected main, strict current-revision required checks, independent review, and native auto-merge first. Add a merge queue only if merge contention demonstrates a need. Do not accept stale green checks or bypass protection.
- **D-07:** Run a separate GSD code review for every exact PR SHA. Keep merge blocked until each review finding is fixed or receives an evidence-backed disposition and the current SHA has a passing review.
- **D-08:** Use a narrowly permissioned GitHub App installation token for trusted write jobs. Qualify actual App/token event behavior, rules, and repository authority before claiming unattended operation; local workflow validation is not proof of hosted authority.

### Release staging, recovery, and publication
- **D-09:** Use the root `.release-please-manifest.json` version as the single source of truth and have CMake/package metadata read it at configure time; do not maintain a second manually synchronized version. Pin and qualify the selected release-please configuration/schema before implementation.
- **D-10:** Build and test the exact versioned commit. Stage an offline-rebuildable source archive and complete unsigned SDK archives for each tested OS/architecture. Include the installed library variants, public headers, CMake package files, diagnostic runner and fixture, notices, README, artifact manifest, and SHA-256 digests as applicable to each package.
- **D-11:** Serialize release work and make retries idempotent. On retry, inspect an existing draft even when release-please reports no newly created release; resume only if tag target, version/manifest, expected asset set, and digests match. Reject missing, unexpected, or mismatched content. Do not depend on a tag/release event emitted by a `GITHUB_TOKEN`-initiated draft flow; use explicit same-workflow job dependencies.
- **D-12:** Before publication, download the staged artifacts, verify their expected digests, rebuild the source archive offline, relocate the installed package away from source/build/install paths, and execute its real diagnostic consumer. Publish automatically only after these gates pass, using trusted App authority. Keep signing and notarization out of this unsigned SDK scope.

### Public-content, privacy, and licensing gate
- **D-13:** Start with a small Python standard-library scanner, not a new dependency. Scan the proposed public source/content, commit identities and metadata in the publishable history, captured CI logs, and bounded release archives. Check required notices/provenance; detect personal paths, private identity, machine identifiers, and secret patterns; and reject unallowlisted media or corpus files against an explicit inventory of permitted fixtures/dependencies.
- **D-14:** Fail closed on unreadable inputs, archive traversal/links, or configured size/count limits; avoid printing matched secret values; test detector rules with synthetic canaries. Use hosted secret scanning/push protection as an additional backstop only when actually enabled. State detector limits and never present a clean scan as proof that every secret is absent.
- **D-15:** Rights remain evidence-based: require an established license/redistribution record for each shipped dependency and fixture. A content scan cannot establish legal permission; keep any unresolved rights question explicitly unknown and request only the specific external confirmation needed.

### the agent's Discretion
- Choose concrete action/compiler/CMake versions and immutable action pins based on current primary documentation and exercised runner images; record their exact identities.
- Select the Windows symbol-table utility and implement the expected-export comparison with parity to Linux/macOS.
- Design the conservative path classifier, matrix fan-out, workflow permissions, artifact manifest, and bounded archive inspection around the existing local verification entrypoint. Preserve a cold build and cap parallelism based on measured runner memory/cost.
- Keep the scanner and workflow support code narrow. Add a scanner dependency only if canary/history evidence exposes a material detection gap that the small implementation cannot address reliably.
- Use objective local, CI, package, and downloaded-artifact evidence to clear machine-observable acceptance. Hand off only unavailable repository/App authority, first-time fork workflow approval, unresolved redistribution rights, or other evidence that truly requires an external actor.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Current project scope and workflow
- `.planning/PROJECT.md` — active v0.1 goals, C17/CMake constraints, privacy/licensing requirements, delivery decisions, and shift-left decision PROJECT-D-45.
- `.planning/REQUIREMENTS.md` — BUILD-03/04 and DEL-01–05 acceptance requirements and traceability.
- `.planning/ROADMAP.md` — Phase 03 goal, success criteria, sequencing guidance, and unconfigured hosted-authority dependency.
- `.planning/STATE.md` — Phase 02 completion and Phase 03 current position; do not follow stale Phase 01 routing text.
- `.planning/METHODOLOGY.md` — role-based discussion, dependency preference, evidence-first work, zero-human-UAT default, and workflow pauses.
- `.planning/preparation/README.md` — dated research/provenance index; preparation is evidence, not current implementation.
- `.planning/preparation/DECISIONS.md` — dated decision provenance, including release, CI, privacy, and dependency background.
- `.planning/preparation/QUALITY-PERFORMANCE-AND-CI.md` — CI quality, cost, portability and measurement rationale.
- `.planning/phases/02-executable-diagnostic-sdk/02-CONTEXT.md` — accepted SDK/package patterns and explicit deferral of hosted CI, PR authority and release qualification.

### Existing build, package, and evidence implementation
- `CMakeLists.txt` — current CMake project version and installed static/shared library, diagnostic, headers, fixture, and license layout.
- `CMakePresets.json` — current CMake 3.20/preset floor and bounded local configurations.
- `cmake/GlueyneoConfig.cmake.in` — installed CMake package contract.
- `tests/consumers/check_package.py` — installed C/C++ consumer verification, relocation checks, and current Linux/macOS-only shared-export inspection.
- `tests/consumers/CMakeLists.txt` — out-of-tree static/shared consumer targets.
- `tools/sdk_evidence.py` and `docs/evidence-schema.md` — source/tool/build/input identities and machine-readable evidence outcomes.
- `tools/verify_sdk.py` and `docs/testing.md` — local SDK verification entrypoint and existing automated checks.
- `tools/diagnostic/main.c` and `fixtures/diagnostic/manifest.json` — shipped diagnostic runner and fixture provenance.
- `LICENSE` and `third_party/unity/PROVENANCE.md` — original project license and pinned Unity provenance/notices.

### Primary platform, PR authority, and release references
- [CMake 3.20 release notes](https://cmake.org/cmake/help/v3.20/release/3.20.html) — preset schema/version baseline.
- [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) — runner images and platform availability; qualify the actual selected images.
- [Required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks) and [repository rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) — current-revision and protected merge configuration.
- [Secure use of `pull_request_target`](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target), [workflow events and fork permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), and [fork workflow approval settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository) — untrusted PR boundaries, token behavior, and first-run approval.
- [GITHUB_TOKEN](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token) and [GitHub App authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/about-authentication-with-a-github-app) — token permission and trusted write-job model.
- [release-please action](https://github.com/googleapis/release-please-action), [CLI/draft behavior](https://github.com/googleapis/release-please/blob/main/docs/cli.md), [manifest releaser](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md), [configuration customization](https://github.com/googleapis/release-please/blob/main/docs/customizing.md), and [configuration schema](https://github.com/googleapis/release-please/blob/main/schemas/config.json) — versioning, draft/tag, manifest, and pinned action behavior to qualify.
- [Managing GitHub releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository), [immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases), [upload-artifact digest behavior](https://github.com/actions/upload-artifact/blob/main/README.md), and [release integrity verification](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verify-release-integrity) — draft assembly, artifact digest handling, and consumer-side verification.

### Primary privacy and secret-scanning references
- [Secret-scanning scope and limitations](https://docs.github.com/en/code-security/reference/secret-security/secret-scanning-scope) and [push protection](https://docs.github.com/en/code-security/how-tos/secure-your-secrets/prevent-future-leaks/enable-push-protection) — hosted backstop coverage and limits.
- [Gitleaks](https://github.com/gitleaks/gitleaks) — evaluated alternative if local canary/history evidence demonstrates that a dedicated secret scanner's value justifies a new tool dependency.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/verify_sdk.py` is the existing local verification path; hosted lanes should invoke it or a thin shared wrapper to preserve local/CI parity.
- `tools/sdk_evidence.py` already emits exact compiler, CMake, SDK, OS, architecture, configuration, flags, and explicit outcome identities.
- `tests/consumers/check_package.py` already builds and runs installed consumers and checks public shared-library exports on Linux and macOS.
- `CMakeLists.txt` installs the core, diagnostic runner, public headers, license, and fixture; use this as the starting point for release archive composition and installed-consumer evidence.

### Established Patterns
- CMake 3.20 and preset schema 2 are the current floor; don't raise them absent a demonstrated toolchain requirement.
- Verification uses bounded deterministic evidence, exact identities, retained failure outcomes, and explicit unsupported/unknown status.
- Static/shared package consumption, C++ public-header compile/link, fixture/license provenance, and offline dependency checks are already part of the local SDK work.
- The project favors a small dependency surface and requires source/action/dependency provenance; preserve notices and do not include commercial media or private corpus data.

### Integration Points
- Extend the consumer export-inspection branch for Windows; current code explicitly errors for Windows.
- Extend the local SDK verification/evidence path to produce platform matrix counts and CI cost measurements.
- Connect PR/release workflows to current-revision verification, exact-SHA review, source archive rebuild, relocated installed consumers, privacy checks, and final downloaded artifact verification.
- No `.github` workflow files or remote are configured, so hosted authority and actual external event behavior cannot be inferred from local code.

</code_context>

<specifics>
## Specific Ideas

Apply the user's standing preference: automate repeatable verification as early as practical and hand off only genuinely external or human-only evidence. Use primary documentation for current action and service behavior. Prefer a small auditable local implementation over an extra dependency when it covers the required failure modes; accept a new dependency when evidence justifies its maintenance and security cost. The user authorized following the synthesized recommendation for the remaining decisions.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 03 scope.

</deferred>

---

*Phase: 03-distributable-release-qualification*
*Context gathered: 2026-10-06*
