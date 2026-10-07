# SDK testing

Run these focused checks from the repository root:

```sh
cmake --build --preset sdk-debug
ctest --preset sdk-debug -L sdk-mutation --output-on-failure --no-tests=error
python3 tests/sdk/controls.py --sanitizers
```

The mutation command exercises deterministic hostile media and legal public API
sequences. The sanitizer supervisor configures and builds separate presets,
checks their private compile/link flags and installed consumer export, starts an
instrumented executable, and only then runs the corresponding CTest suite. It
writes stage logs and a machine-readable report under each preset's
`build/<preset>/sanitizer-control/` directory. Configure, build, startup and
runtime status are reported separately. A startup-only pass is not a suite pass.

## Executed sanitizer lanes

Evidence recorded on AppleClang 21.0.0.21000101, Debug, arm64 Darwin 25.6.0.
Both lanes compiled and linked with lane-private flags. The installed
`GlueyneoTargets.cmake` export contains no sanitizer flag; the normal consumer
target receives no sanitizer or test usage requirement.

| Lane | Startup probe | Runtime suite | SDK cases / assertions | Runtime wall time |
| --- | --- | --- | ---: | ---: |
| ASan + UBSan | pass, 17 checks | 8/8 tests passed | 31 cases / 577,077 assertions | 0.49 s |
| TSan | pass, 18 checks including a joined worker thread | 2/2 tests passed | 2 cases / 30 assertions | 2.96 s |

The ASan + UBSan suite ran lifecycle, media, fault, run, diagnostic, both
mutation entrypoints, and the minimizer self-test. The seven SDK result records
reported:

| Suite | Cases | Assertions |
| --- | ---: | ---: |
| Lifecycle | 2 | 42 |
| Media | 3 | 118 |
| Faults | 3 | 476 |
| Run | 6 | 149 |
| Diagnostic | 4 | 119 |
| Mutation media | 11 | 34,739 |
| Mutation sequence | 2 | 541,434 |

The minimizer self-test is the eighth CTest case; it verifies that deterministic
byte deletion reduces a synthetic 25-byte failure to its 2-byte trigger while
preserving the same failure ID. TSan exercised 13 equal-boundary observations,
16 interleaved pairs, 16 barrier-synchronized pairs, 32 concurrent candidate
failure paths, and eight cold processes covering 16 owners, 16 failure paths,
and 16 reset recoveries. No sanitizer finding was reported.

The final supervisor pass took about 0.87 seconds for the ASan + UBSan configure,
incremental build, startup and runtime stages, and 3.68 seconds for TSan. The
first successful full compiles took 0.73 seconds for ASan + UBSan and 0.75
seconds for TSan; configure took 1.23 and 0.91 seconds, respectively. Peak RSS
is **unmeasured**: this host denied process inspection (`ps`: “Operation not
permitted”), so the supervisor records the memory measurement as unsupported.
These timings describe this local diagnostic suite only.

## Bounded mutation corpus

Both C harnesses use seeded xorshift64 mutation, with 1,024 iterations each.
This is finite deterministic mutation, not coverage-guided fuzzing. The common
limits are 4,096 input bytes, 64 operations per input, four live instances,
1,000,000 guest-requested cycles per input, two media descriptors, 256 possible
trace events, and the existing 1 MiB mapped-plus-source storage budget.

| Harness | Seed | Named corpus cases | Unique generated inputs | Operations | Max cycles per input | Max input bytes | Peak storage |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Media | `0x6e656f67656f3235` | 10 | 1,024 | 1,034 total | 432 | 64 | within the 1 MiB cap |
| Public call sequence | `0x6e656f67656f3235 XOR 0xa17f00d5` | 2 | 1,017 | 33,169 total | 3,313 | 64 | 20,520 bytes |

The 1,114,212 sequence cycles in the run log aggregate work over all inputs; the
largest individual input requested 3,313 cycles, below the 1,000,000-cycle cap.
The harness checks valid caller-owned storage, exact rejection statuses,
repeat/reset behavior, peer isolation and bounded lifecycle recovery. No trace
events are collected by these public-API harnesses, so the 256-event ceiling is
not exercised. The mutation CTest run passed all three registered cases
(media, sequence, and minimizer), with nonzero assertions in both C entrypoints.

`tests/fuzz/regressions.json` records original diagnostic boundary inputs and
the deterministic seeds. No runtime defect was found in this run; therefore no
real failing input was minimized or promoted. The minimizer self-test validates
exact failure-ID preservation on its synthetic trigger. `findings` remains
empty in the corpus manifest.

## Unsupported coverage

The matching AppleClang libFuzzer archive is absent on this host, so no
coverage-guided libFuzzer lane was built or run locally. The hosted workflow
selects only the exact compiler/runtime combinations listed below. Other
operating systems, compilers, hardware profiles, arbitrary hostile host
pointers, and real-game compatibility are not qualified by these finite
diagnostic checks. A hash, bounded mutation pass, or reference-emulator result
does not establish hardware truth.

## Current platform and cost evidence

The exact local profile recorded by the committed-head Phase 03 matrix is
AppleClang 21.0.0.21000101, macOS arm64 (`Darwin-26`), Apple SDK 26.5, CMake
4.4.3, Ninja 1.13.2, Debug, with the SDK sanitizer disabled. At source revision
`2054c3d6d07427d0e4a045b2388bcc933478bec9`, its local diagnostic and installed
consumer checks passed 36 cases and 1,440 assertions in nine lane executions.
The measured local lane duration was 9.374 seconds and one clean configure/build
took 1.636 seconds. These are measurements of that local invocation only; they
do not establish a supported platform range, hosted critical path, or GitHub
runner-minutes.

The first complete hosted matrix passed at source
`2c7926383222cee174ede5ddde06374b43002191` in [CI run 37525280735](https://github.com/szTheory/glueyneo/actions/runs/37525280735).
It exercised these exact combinations with nonzero SDK assertions:

| Lane | Exact compiler and SDK/userspace | Image / architecture | Result |
| --- | --- | --- | --- |
| linux-clang | Clang 18.1.3; GNU/Linux userspace glibc 2.39 | `ubuntu24@20260927.320.1` / x86_64 | pass |
| linux-clang-fuzz | Clang 18.1.3; GNU/Linux userspace glibc 2.39 | `ubuntu24@20260927.320.1` / x86_64 | pass |
| linux-clang-sanitizer | Clang 18.1.3; GNU/Linux userspace glibc 2.39 | `ubuntu24@20260927.320.1` / x86_64 | pass |
| linux-gcc | GNU 13.3.0; GNU/Linux userspace glibc 2.39 | `ubuntu24@20260927.320.1` / x86_64 | pass |
| macos-appleclang | AppleClang 17.0.0.17000013; macOS SDK 15.5 | `macos15@20260907.0337.1` / arm64 | pass |
| windows-msvc | MSVC 19.51.36260.0; Windows SDK 10.0.26100.0 | `win25-vs2026@20260925.250.1` / AMD64 | pass |

Primary runtime checks use Debug/NONE with static/shared installed Release
consumers; the sanitizer and seeded-fuzz jobs retain separate instrumentation.
Linux uses CMake 3.31.6; macOS/Windows use 4.4.3; all use Ninja 1.13.2.
The matrix recorded 1,159,040 SDK assertion executions, 33.479 seconds for the
slowest verifier lane, 27.010 seconds maximum cold build and 1.601 summed
verification minutes. GitHub timestamps show 112 seconds run elapsed and
3.083 summed job wall minutes including setup. Verifier execution, workflow
elapsed time and billed cost are distinct; no billing multiplier or rounding
is included. The schema's slowest-lane “critical path” excludes queue/setup and
is not the workflow's end-to-end critical path.

The [hosted receipt](../.planning/phases/03-distributable-release-qualification/03-CI-HOSTED-RECEIPT.json)
retains exact job/build/fixture/binary identities and seven previous failed
attempts. A new SHA requires new evidence; no platform range, published SDK
release, original-silicon or general-game claim follows from this finite pass.
The release App, first-time fork boundary, protected merge and released
archive/download evidence remain pending. Failed/skipped/unsupported/unknown
outcomes remain distinct and cannot contribute passing assertions.

The later PR head `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1` also passed all six
matrix lanes, `public-content`, and `ci-policy` in [CI run
37618668537](https://github.com/szTheory/glueyneo/actions/runs/37618668537).
That run extends the pass outcome to that exact revision. The detailed
compiler, SDK, assertion, and artifact table above remains bound to
`2c7926383222cee174ede5ddde06374b43002191`; the later run's timings do not
replace those measurements. The release App, first-time fork boundary,
protected merge, and released archive/download evidence remain pending.

The rights inventory currently contains affirmative records for the shipped
original diagnostic material and pinned Unity subset. No commercial game ROM,
BIOS, private corpus, or private capture is licensed into the release. Any new
item without an affirmative record tied to exact bytes remains excluded and its
rights status unknown; a clean content scan cannot resolve that question.

## Required CI aggregate

The focused selectors are `matrix` (SDK diagnostic CTest groups and installed
static/shared consumers), `release-consumer`, `ci-policy`, `public-content`,
`sanitizer`, and `fuzz`; `all` retains the full local verification path. The
matrix command is `python3 tools/verify_sdk.py --suite matrix`. It records
compiler, SDK, runner image, architecture, build and fixture identities from
the active runner. Sanitizer and seeded mutation controls run as separate Linux
Clang lanes in `.github/workflows/ci.yml`.

CI always starts the `ci-policy` aggregate for pull requests and pushes to
`main`; branch protection should require the current `CI / ci-policy` check.
The workflow has no path filters. Its internal classifier sends recognized
documentation-only changes through the public-content gate and sends source,
build, package, release, unknown, and unclassifiable changes through the full
matrix. Missing or failed jobs, cancelled or empty lanes, zero assertion counts,
stale source revisions, and absent receipts fail the aggregate. Pull request
jobs use the workflow's read-only `contents: read` token, contain no secrets,
and use `pull_request`; GitHub's first-time contributor workflow-approval
safeguard remains active where repository settings require it. There is no
privileged PR job that consumes or executes an uploaded PR artifact.

Successful hosted runs retain per-lane receipts and an aggregate under
`evidence/sdk/ci-aggregate.json`. A local parser fixture proves rejection
behavior; it does not establish a hosted result. GitHub Actions run
`37618668537` passed the six named matrix lanes and `ci-policy` at exact PR head
`2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1`; the detailed toolchain and
assertion receipt above belongs to the earlier exact source revision. A
read-only API check observed that `main` requires the strict `CI / ci-policy`
check and one approval, with stale reviews dismissed and approval required
after the last push. Those settings do not establish a protected merge: no
independent approval, merge, or first-time fork approval event has been
exercised. The current documentation-only correction has no new hosted run.
These receipts establish only the named outcomes at their recorded revisions,
not a broader platform range. Runner execution minutes and matrix critical path
are computed from measured verification command durations after checkout; they
exclude checkout/upload overhead and GitHub's billing rounding. They describe
those observed lane commands only.
Public-content scanning is detector coverage, not proof
that every private value is absent, and it cannot establish redistribution
rights.
