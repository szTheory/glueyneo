---
phase: "03"
slug: "distributable-release-qualification"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-07"
---

# Phase 03 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail. This report verifies implemented controls at configured ASVS L1 grep depth; it is not an ASVS compliance claim or hosted release qualification.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Pull request to CI | Untrusted source changes enter read-only CI. CI has no release credentials, write token, or privileged checkout. | Source, workflow metadata, test artifacts |
| Trusted release workflow to GitHub API | A protected trusted job requests a repository-scoped, least-permission App token; the private key is supplied only through an Actions secret in trusted jobs. | Release metadata and staged SDK assets |
| Archive to validator and consumer | Downloaded release bytes are treated as untrusted input and pass bounded archive, digest, inventory, and real-consumer checks. | Archive members, manifests, symbols, source/build inputs |
| Staging to publication | Publication depends on current release control, complete staged assets, and successful downloaded-byte verification. | Version/tag identity, asset names/sizes/digests, release draft state |
| Repository content to public distribution | Tree/history/log/archive scans and a separate rights inventory gate public content; detector success does not establish legal rights. | Source, history objects, CI receipts, notices, dependency fixtures |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-03-01 | Tampering | release archives | high | mitigate | Exact source/version, bounded safe members, final-byte digests, and real consumer checks in `tools/release_manifest.py`, `tools/release_state.py`, and `tests/consumers/test_release_consumer.py`. | closed |
| T-03-02 | Information disclosure | package metadata | medium | mitigate | Public-content inventory rejects source-path leakage and limits shipped files; bounded scan is exercised by `tests/workflow/test_public_content.py`. | closed |
| T-03-SC | Tampering | package installs | high | mitigate | No runtime package-manager dependency is introduced; third-party Actions are pinned to full commit SHAs and provenance is retained in workflow comments/docs. | closed |
| T-03-03 | Information disclosure | public-content scanner | high | mitigate | Bounded tree/history/log/archive inputs and redacted findings; exercised by scanner adversarial tests. | closed |
| T-03-04 | Tampering | archive scanner | high | mitigate | Rejects links, traversal, duplicates, unreadable inputs, and configured limit violations; exercised by scanner adversarial tests. | closed |
| T-03-05 | Repudiation | rights inventory | medium | mitigate | Shipped items require recorded provenance, digest, and redistribution disposition; unknown rights items remain excluded. | closed |
| T-03-06 | Elevation of privilege | PR workflow | high | mitigate | PR CI has read-only permissions, no secrets, no privileged event checkout, and no artifact trust path into release authority; tested by `tests/workflow/test_ci_policy.py`. | closed |
| T-03-07 | Spoofing | matrix evidence | high | mitigate | Evidence is bound to exact SHA, runner/compiler/configuration identity, and positive case/assertion counts; tested by `tests/sdk/test_matrix_evidence.py`. | closed |
| T-03-08 | Tampering | aggregate check | high | mitigate | Always-started aggregate validates the classifier plan and every required lane/result and rejects missing or empty evidence; tested by `tests/workflow/test_ci_policy.py`. | closed |
| T-03-09 | Tampering | draft recovery | high | mitigate | Each retry checks tag SHA, version, exact asset set, sizes, and hashes; incomplete or mismatched drafts cannot publish; tested by `tests/workflow/test_release_recovery.py`. | closed |
| T-03-10 | Elevation of privilege | App token | high | mitigate | Release API tokens are minted only in trusted jobs with requested repository/content write scope after untrusted-code checks; token values are not written to receipts. | closed |
| T-03-11 | Information disclosure | release contents | high | mitigate | Staged publishable bytes pass the bounded content/rights gate before publication; downloaded release content is checked by the release workflow. | closed |
| T-03-12 | Spoofing | review receipt | high | mitigate | Merge readiness binds required checks, independent review, and findings dispositions to the exact PR head and rejects stale evidence. Hosted review and protected-merge receipts remain transferred to the manual qualification gate. | closed |
| T-03-13 | Elevation of privilege | hosted App | high | transfer | Trusted-job isolation and least-permission token requests are implemented. Effective installation grant, token lifecycle, first-time fork behavior, and App event receipts remain unverified and are explicit preconditions in `03-HOSTED-QUALIFICATION.md`; no release is qualified until observed. | closed |
| T-03-14 | Repudiation | support claims | medium | mitigate | Exact run IDs, source identities, measurements, failures, and unknown outcomes are recorded in the hosted qualification evidence; unobserved release claims remain pending. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open.*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party or hosted evidence gate).* 

## Accepted Risks Log

No accepted risks.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-07 | 15 | 15 | 0 | Phase 03 security gate, ASVS L1 |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-07 for implemented L1 controls; hosted qualification remains pending.
