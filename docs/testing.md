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
coverage-guided libFuzzer lane was built or run. No compiler/runtime is installed
or selected by this workflow. Other operating systems, compilers, hardware
profiles, arbitrary hostile host pointers, and real-game compatibility are not
qualified by these finite diagnostic checks. A hash, bounded mutation pass, or
reference-emulator result does not establish hardware truth.

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

| Required hosted identity | Current result |
| --- | --- |
| Linux x64, Clang, Ubuntu 24.04 hosted image | unknown; no hosted receipt |
| Linux x64, GCC, Ubuntu 24.04 hosted image | unknown; no hosted receipt |
| macOS arm64, AppleClang, macOS 15 hosted image | unknown; local macOS result does not qualify it |
| Windows x64, MSVC, Windows 2025 hosted image | unknown; no hosted receipt |
| Linux Clang ASan/UBSan hosted lane | unknown; local AppleClang sanitizer run is separate evidence |
| Linux Clang seeded-fuzz hosted lane | unknown; no hosted receipt |

Do not mark a row passing until its current-source GitHub job receipt includes
the exact hosted image, compiler/SDK, architecture, configuration, positive
assertion denominator, cold-build duration, and lane duration. The hosted
matrix aggregate then supplies its measured slowest-job critical path and sum
of runner durations. Failed attempts remain failures, while skipped,
unsupported, and untested combinations keep their distinct outcomes and do not
contribute passing assertions.

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
behavior; it does not claim that any hosted lane ran. At this revision no
remote, hosted runner result, required-check protection, or first-time fork
approval event has been exercised. Linux GCC/Clang, macOS arm64 AppleClang,
Windows x64 MSVC, sanitizer, and fuzz support remain unqualified until matching
current-source receipts are produced by GitHub Actions. Local successful
diagnostic runs do not qualify a hosted runner lane. Runner execution minutes
and matrix critical path are computed from measured verification command
durations after checkout; they exclude checkout/upload overhead and GitHub's
billing rounding. They describe those observed lane commands only.
Public-content scanning is detector coverage, not proof
that every private value is absent, and it cannot establish redistribution
rights.
