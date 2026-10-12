# API Coverage — GitHub Actions and release automation

> Full coverage by default for the GitHub integration surface used by this phase. This matrix covers the required PR, App-token, ruleset, and release operations; unrelated GitHub platform capabilities are explicitly excluded.

| capability | decision | reason |
|---|---|---|
| `pr_readonly_current_sha_checks` | INTEGRATE | Required by D-05 and DEL-02; untrusted PR code stays outside trusted write and publication authority. |
| `protected_current_sha_merge_gate` | INTEGRATE | Required by D-06 and D-07; stale checks cannot authorize merge. |
| `github_app_installation_token` | INTEGRATE | Required by D-08 and DEL-02/DEL-03; qualify actual token and event behavior before claiming unattended operation. |
| `release_please_manifest_pr` | INTEGRATE | Required by D-09 and DEL-03; the root manifest remains the single version source. |
| `draft_release_target_validation` | INTEGRATE | Required by D-10 and D-11; retries inspect drafts even when no release was newly created. |
| `release_asset_inventory_transfer_digest` | INTEGRATE | Required by D-10 through D-12 and DEL-04; missing, extra, or mismatched assets block publication. |
| `verified_draft_publication` | INTEGRATE | Required by D-12 and DEL-04; trusted App authority publishes only after all gates pass. |
| `user_oauth_pat_or_runtime_network` | OPT-OUT | No user identity or runtime network service is required; read-only `GITHUB_TOKEN` covers untrusted PR validation and App authority is reserved for trusted writes (D-05, D-08). |
| `token_generated_release_event_chain` | OPT-OUT | D-11 requires explicit same-workflow dependencies because a `GITHUB_TOKEN` write does not trigger another workflow. |
| `pull_request_target_untrusted_execution` | OPT-OUT | It violates the untrusted-code boundary in D-05 and creates unnecessary write/secret exposure. |
| `merge_queue_by_default` | OPT-OUT | D-06 selects native auto-merge first; add a queue only if observed merge contention justifies it. |
| `signed_or_notarized_artifacts` | OPT-OUT | The selected deliverable is an unsigned SDK alpha; signing and notarization are outside this phase (D-12). |
| `unrelated_github_api_surface` | OPT-OUT | Issue, discussion, deployment, package-registry, and user-management APIs do not contribute to Phase 03 acceptance and would add permissions without a consumer need. |
