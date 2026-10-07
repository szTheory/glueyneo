# Phase 03 hosted qualification receipts

**Status: exact hosted SDK CI passed; Plan 03-05 Task 2 incomplete.**
These observations qualify the named diagnostic SDK configurations at source
`2c7926383222cee174ede5ddde06374b43002191`. They do not qualify a release, a platform range,
original-silicon behavior or general game compatibility.

## Observed repository controls

The owner authorized creation of the public
[szTheory/glueyneo repository](https://github.com/szTheory/glueyneo) with GitHub CLI.
Setup triage found zero open issues and zero PRs before
[draft PR #1](https://github.com/szTheory/glueyneo/pull/1) was opened. Its base is
sanitized Phase 02 commit `4b2120d57f486ef7561409ff80db109b7494ae5d`.
No merge, tag or release was published.

GitHub API observations on 2026-10-06 establish configuration, not exercised
merge enforcement: `main` requires strict `ci-policy` from GitHub Actions
App ID 15368, one approval, stale-review dismissal, last-push approval,
conversation resolution and linear history; administrators are included;
force push and deletion are disabled. Native auto-merge is enabled, squash is
the only allowed merge method and merged branches are deleted. PR #1 remains
draft with review required. The separate exact-head GSD review remains a
required local merge-readiness condition; a green CI run is insufficient.

Actions default to read permissions and cannot approve PRs. First-time
contributors require workflow approval, but no first-time fork event has been
exercised. Repository secret scanning and push protection are enabled;
non-provider patterns and validity checks are disabled. No live credential
canary has been tested.

On 2026-10-07 the owner reported that release App ID `5217741` is installed
for `szTheory/glueyneo`, and that the repository Actions secret
`RELEASE_APP_PRIVATE_KEY` and variable
`RELEASE_APP_ID` are configured. These setup details are not direct
observations of GitHub's current App permission grant or secret/variable
values. Requested permissions,
effective token scope, expiration, revocation, and release-please events remain
unqualified. No credential values are retained. See
[03-RELEASE-APP-SETUP.md](03-RELEASE-APP-SETUP.md).

## Exact hosted CI evidence

[CI run 37525280735](https://github.com/szTheory/glueyneo/actions/runs/37525280735) passed all six matrix lanes, public-content and the
always-started `ci-policy` aggregate at the exact source above. The independent
GSD review at that source has no open findings; see the dated final section in
[03-REVIEW.md](03-REVIEW.md). Any later PR head needs its own passing checks and
independent review. These dated receipts must not authorize a different SHA.

[03-CI-HOSTED-RECEIPT.json](03-CI-HOSTED-RECEIPT.json) retains per-job IDs/times,
compiler/SDK/image/build identities, fixture and binary digests, downloaded
artifact hashes, aggregate result, protection settings and failed attempts.
All primary runtime lanes use Debug/NONE and test installed static/shared
Release consumers. Sanitizer and seeded-fuzz lanes retain their distinct
instrumentation and workload. All rows use Ninja 1.13.2.

| Lane | Exact image / architecture | Compiler / SDK or userspace | CMake / generator | Result / assertion executions | Cold build / verification seconds |
| --- | --- | --- | --- | --- | --- |
| linux-clang | `ubuntu24@20260927.320.1` / x86_64 | Clang 18.1.3 / GNU/Linux userspace glibc 2.39 | 3.31.6 / Ninja 1.13.2 | pass / 1,440 | 7.239 / 10.928 |
| linux-clang-fuzz | `ubuntu24@20260927.320.1` / x86_64 | Clang 18.1.3 / GNU/Linux userspace glibc 2.39 | 3.31.6 / Ninja 1.13.2 | pass / 576,173 | 9.882 / 13.882 |
| linux-clang-sanitizer | `ubuntu24@20260927.320.1` / x86_64 | Clang 18.1.3 / GNU/Linux userspace glibc 2.39 | 3.31.6 / Ninja 1.13.2 | pass / 577,107 | 27.010 / 33.479 |
| linux-gcc | `ubuntu24@20260927.320.1` / x86_64 | GNU 13.3.0 / GNU/Linux userspace glibc 2.39 | 3.31.6 / Ninja 1.13.2 | pass / 1,440 | 1.730 / 4.254 |
| macos-appleclang | `macos15@20260907.0337.1` / arm64 | AppleClang 17.0.0.17000013 / macOS SDK 15.5 | 4.4.3 / Ninja 1.13.2 | pass / 1,440 | 5.193 / 10.722 |
| windows-msvc | `win25-vs2026@20260925.250.1` / AMD64 | MSVC 19.51.36260.0 / Windows SDK 10.0.26100.0 | 4.4.3 / Ninja 1.13.2 | pass / 1,440 | 11.297 / 22.813 |

The six lanes contain **1,159,040 SDK assertion executions**.
The aggregate records seven job/lane entries and 1,159,503 total
checks, including 463 public-content input-file checks; those file checks are
not additional native behavioral assertions. Successful assertions from earlier
failed attempts are not folded into this passing receipt.

Verifier timing sums to 1.601 execution minutes, with a
33.479-second slowest lane and a maximum
27.010-second cold build. The schema's
`critical_path_seconds` is the slowest verifier execution, not the end-to-end
workflow critical path. GitHub timestamps separately show
112 seconds from run creation to final update and
3.083 summed job wall minutes including setup. Queueing,
`max-parallel: 2`, image preparation and aggregate jobs explain the distinction.
These measurements exclude billing rounding and OS cost multipliers and are
not performance budgets or gameplay claims.

## Preserved failed attempts

Each correction used a new source revision; no failed result was converted into
pass or retried away. Initial sanitizer diagnostics did not expose the
underlying first Linux TSan failure; its cause remains unknown. Later exact
instrumented runs pass, without retroactively diagnosing that failure.

| Run | Source | Outcome | Observed failure / uncertainty |
| --- | --- | --- | --- |
| [37518485800](https://github.com/szTheory/glueyneo/actions/runs/37518485800) | `0712ed83b5e0` | failed | Initial hosted failures: GCC C17 array qualifiers; Linux loader identity; MSVC test allocation alignment; sanitizer failure reporting; scanner CLI and aggregate preparation. |
| [37519741337](https://github.com/szTheory/glueyneo/actions/runs/37519741337) | `c262fb92f392` | failed | Platform failures retained; underlying early Linux TSan failure cause remains unknown because initial diagnostics omitted it. |
| [37520769390](https://github.com/szTheory/glueyneo/actions/runs/37520769390) | `4fb54e4b28ca` | failed | MSVC C4457 shadowed index; other five lanes passed. |
| [37521435284](https://github.com/szTheory/glueyneo/actions/runs/37521435284) | `666433537e7b` | failed | Windows runtime/runner artifact suffix lookup omitted .lib/.exe. |
| [37521728540](https://github.com/szTheory/glueyneo/actions/runs/37521728540) | `98a250ee979c` | failed | Windows CRLF checkout changed canonical fixture manifest bytes. |
| [37524266388](https://github.com/szTheory/glueyneo/actions/runs/37524266388) | `a91e98efe1f5` | failed | MSVC diagnostic revision was unknown and rejected by exact-SHA evidence. |
| [37524853015](https://github.com/szTheory/glueyneo/actions/runs/37524853015) | `1c1265a79f2a` | failed | DUMPBIN /? help returned 1100; shared consumer failed, static consumer passed. |

## Publication and rights boundary

Before the first source push, isolated publication history passed the bounded
scan and complementary literal-home check: 351 tracked files and 1,106 unique
historical blobs. See [03-PUBLICATION-AUDIT.json](03-PUBLICATION-AUDIT.json) and
[03-PUBLICATION-COMMIT-MAP.txt](03-PUBLICATION-COMMIT-MAP.txt). The original
private local refs are retained and must never be pushed. Historical receipts
keep original identities; the map links them to sanitized public commits.

The full-depth public-content job inspected all public reachable refs. A
separate shallow-checkout scan inspected the selected source SHA and six
captured matrix receipts. The first complete aggregate retained the older
generic `history_mode` label; subsequent scanner reports name the selected
revision and explicitly limit scope to objects available in that checkout.
The scanner covers only configured patterns,
inputs and limits. Exact benign historical dispositions remain visible.
Item-level redistribution evidence in
[docs/rights-inventory.md](../../../docs/rights-inventory.md) is separate;
no commercial ROM/BIOS or private corpus is admitted. Released archives and
published downloads remain unobserved.

## Pending evidence and resume condition

| Claim | Required actual evidence | External actor |
| --- | --- | --- |
| Release App authority | Owner-reported App ID, repository target, and Actions secret/variable setup exist; still require observed permission grant, token scope/expiry/revocation without credential values, Release Please and downstream job events | App owner and repository administrator |
| First-time fork boundary | A first-time fork PR, workflow approval event, effective read-only token and no-secret execution at exact head | Independent contributor; repository administrator approves run |
| Protected merge | Independent GitHub approval after final push, exact-head GSD review and passing aggregate, observed protected merge commit | Reviewer other than author/latest pusher; qualifying maintainer |
| Complete SDK release | Tested tag/commit, staged inventory/digests, no-new-release retry, downloaded platform consumers/source rebuild, publication and verified published downloads | Repository administrator after scoped App setup |

Local policy/recovery fixtures remain valid evidence for rejection behavior;
they do not establish the pending hosted outcomes. BUILD-03/04 and
DEL-01–05 remain pending in phase traceability until their complete acceptance
and phase verification have been satisfied.

## CHECKPOINT REACHED

**Type:** human-verify

**Gate:** blocking-human

**Plan:** 03-05

**Progress:** Task 1 complete; Task 2 stopped at its hosted-evidence gate after owner-reported App setup.

Plan 03-05 Task 2's App setup checkpoint is now owner-reported, but the hosted
token/event checks and external actors remain unavailable. Arrange a
first-time fork contributor and an independent GitHub reviewer with approval
authority, then resume the hosted portion. Plans 03-01–04 are complete; Plan
03-05 is halted with its remaining evidence explicit, and Phase 03 itself is
not complete. No phase verification, shipping, next phase, or milestone step
has been started.
