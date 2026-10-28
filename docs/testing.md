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
Both in-tree lanes compiled and linked with lane-private flags. Instrumented
static package exports carry only the selected sanitizer runtime link option;
compile instrumentation and warning, frame-pointer, and recovery policy remain
private. Ordinary `NONE` static and shared exports carry no sanitizer usage.

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

## Installed sanitizer consumer controls (2026-10-28)

`python3 tools/verify_sdk.py --suite sanitizer` also performs actual relocated
static package checks in separate `ADDRESS_UNDEFINED` and `THREAD` build
prefixes. For each mode it builds and installs the package, links a C17 sound
consumer and a separate C++17 loaded-media consumer through
`Glueyneo::glueyneo`, then runs the same public fixture and compares the full
video/PCM trace. Consumer compile commands contain no sanitizer flags; final
link commands inherit only the selected runtime selector. A copied install has
that one exported option removed, after which both language final links must
fail on the corresponding sanitizer runtime symbols.

Each mode also builds and relocates ordinary `NONE` static and shared packages.
Their installed targets, consumer compile commands, and final links contain no
sanitizer usage. Both C/C++ consumer pairs run and produce matching fixture
traces. The existing Linux Clang matrix job continues to run the ordinary
installed consumers; the existing `linux-clang-sanitizer` matrix lane runs the
new two-mode installed checks and requires positive rows when invoked with that
named lane. `build/installed-sanitizer-controls/<MODE>/<run-id>/report.json`
records per-case mode, linkage, compiler/linker identity, duration, assertion
count, and outcome without claiming other operating systems or instrumented
shared-library support.

The direct installed route passed on AppleClang 21.0.0.21000101 / arm64 / Darwin
25.6.0. ASan + UBSan passed 4/4 cases and 158 assertions in 22.63 seconds;
TSan passed 4/4 cases and 158 assertions in 26.36 seconds. Each four-case
inventory includes `ordinary_none_export`, `installed_c_chip`,
`installed_cxx_chip`, and `removed_runtime_usage`. The named Linux Clang CI lane
has not executed for this source revision here, so its required result remains
pending and these local rows do not complete BUILD-05.

## Native state continuation lanes (2026-10-26)

`python3 tools/verify_sdk.py --suite state` is the required, nonzero verification
entrypoint for native save-state continuation. It builds the Debug SDK, selects
the required `sdk_state_tracer`, `sdk_state_identity`, `sdk_state_ym`,
`sdk_state_machine`, `sdk_state_continuation`, `sdk_state_controls`,
`sdk_state_isolation`, `sdk_state_repeat`, `sdk_state_hostile`, `sdk_state_oom`,
`sdk_state_process`, and `sdk_state_registration` CTests, and includes
`sdk_state_exchange` whenever that test is registered. It fails on missing
required names, zero cases or zero assertions; empty test selections fail via
`--no-tests=error`. This route has no human UAT step. On this host it passed
13/13 named tests with 1,673
assertions; the measured CTest critical path was 37.85 seconds. The exchange
test ran eight Debug/Release pairs with 176 assertions. These are local
Darwin arm64 / AppleClang measurements, not a claim about other toolchains.

The required state suite is also part of the existing Linux Clang matrix job,
which already runs on matrix-suite changes. CI keeps the existing two-runner
parallel limit and fail-closed path classifier: an unavailable or invalid diff
selects every job. Unknown path classification is covered by `ci-policy`.

`python3 tools/verify_sdk.py --suite sanitizer` now includes MVS state hostile
input and allocation-failure cases in ASan + UBSan, plus per-instance state
isolation in TSan. This host passed ASan + UBSan 10/10 tests (578,088
assertions) and TSan 3/3 tests (97 assertions). The sanitizer startup probes
passed; process-tree peak RSS remains unsupported on this host. Those results
are separate from the older diagnostic-only sanitizer counts above.

`python3 tools/mvs/qualify_local_state.py --self-test` exercises the actual
exporter/importer process and comparison path using only the public fixture.
The optional local selected-scene run accepts an explicit existing local
qualification configuration; its private media, state buffers, full traces,
and report stay in ignored local storage. Its comparison includes full raw
video and PCM, guest results, and emulated time, with invalid-import atomicity
and historical save-RAM address checks. Private inputs and their identities
are not CI fixtures or public evidence.

## Frontend continuation and recurring public coverage

Run the public frontend boundary suite with:

```sh
python3 tools/verify_sdk.py --suite frontend
```

This entrypoint configures and builds `owned-debug`, checks the live CTest JSON
for the nine required callback, state, save-RAM, observer, frontend-smoke, and
registration tests, runs the named registration mutations, selects only those
nine CTests, and verifies the installed public exports. It rejects an empty,
partial, skipped, widened, or failed selection and binds the result to the
current source/build identity. It does not run the broader native campaigns.
The suite runs in the existing `linux-clang` matrix lane and uses its fail-safe
changed-path classifier; it adds no frontend app,
private scene, local qualification input, or GUI action to public CI.

The selected private MVS continuation route is a separate local macOS check.
It requires the already-authorized local content and scene contract and keeps
state, captures, and the full report in ignored local storage. For example:

```sh
# The observer target is deliberately opt-in and is not built by the standard
# owned-debug preset. Enable it explicitly for this local private route, then
# build it alongside the native process witness used below:
cmake --preset owned-debug \
  -DGLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS=ON
cmake --build --preset owned-debug \
  --target glueyneo_libretro_observed sdk_state_process

python3 tests/libretro/retroarch_smoke.py \
  --retroarch "$GLUEYNEO_RETROARCH_APP" \
  --core build/owned-debug/glueyneo_libretro.dylib \
  --observed-core build/owned-debug/glueyneo_libretro_observed.dylib \
  --content "$GLUEYNEO_PRIVATE_MVS_BUNDLE" \
  --private-contract "$GLUEYNEO_PRIVATE_SCENE_CONTRACT" \
  --witness build/owned-debug/sdk_state_process \
  --continuation-route private-state \
  --report "$GLUEYNEO_FRONTEND_WORK/private-state.json" \
  --timeout 120
```

The route has a per-invocation timeout capped at 120 seconds. There is no
background watcher and no lifetime observation counter. Run it sequentially with
other work that rebuilds or uses the same adapter artifacts. A missing local
input or unsupported host is reported as a narrow blocked/unknown outcome; it
does not substitute a public fixture or turn the private route into CI
coverage.

## Native MVS durable backup-RAM save suite (2026-10-26)

Run the current focused save checks with:

```sh
python3 tools/verify_sdk.py --suite save
```

The route selects exactly `sdk_save_api`, `sdk_save_receipts`,
`sdk_save_lifecycle`, and `sdk_save_registration` on every supported native
build. Darwin additionally runs `sdk_save_process`, `sdk_save_host_faults`,
and `sdk_save_recovery`. A missing, extra, duplicate, skipped-on-Darwin, or
zero-assertion case fails. The route binds its result to the source/build
identity, records the observed host qualification, and runs the existing
four-document checker with measured values plus omission/contradiction
controls. The shared portable and Darwin contract checks cover 13 table
families; registration exercises missing, duplicate, extra, and appended
contradiction mutations for each family (52 negative controls). It requires
no human UAT.

On this host the route passed 7/7 named tests (CTests) with 2,182 reported
assertions and 881 direct documentation assertions; its measured critical
path was 235.110 seconds, including a 19-test observation replay with 1,308
Python assertion calls. The executed identity was macOS 26.6.2 / Darwin
25.6.0 / APFS, AppleClang 21.0.0.21000101, Debug, with
the SDK sanitizer disabled. The save source identity was
`ce644f7208a34527d22075858b31b0f13a8b5f64187225de7c5a8be5c1458ccd`; the
separate guest source identity was
`af74e58521d294c324c9510a2fba7432cbfcf57f2489f26c7d7045db5868734d`. The
measured host results cover 18 syscall-fault cases and 20 process-kill cases.
They qualify the tested Darwin/APFS process path only. Physical power-loss
recovery and other host commit protocols remain unqualified.

`python3 tools/verify_sdk.py --suite sanitizer` passed 18/18 lane tests with
579,704 assertions. ASan + UBSan passed 13/13 tests with 579,607 assertions
in 75.874 seconds of CTest runtime. TSan passed 3/3 tests with 97 assertions
in 42.650 seconds, covering state isolation and cold/isolation controls rather
than the host filesystem writer. ASan's
allocator quarantine does not promise exact instance-address reuse, so that
single allocator-address assertion is compiled out there; the ASan receipt
case still checks that a stale receipt is rejected, and the ordinary Debug
save suite retains the address-reuse check. Peak process-tree RSS remains
unsupported because host process inspection is denied. The sanitizer lanes
ran serially where the TSan isolation comparison uses a bounded 60-second
child timeout; the ASan hostile-state CTest has a 120-second outer timeout.
To rerun the focused receipt check:

```sh
ctest --preset sdk-asan-ubsan --no-tests=error -R '^sdk_save_receipts$' --output-on-failure
```

The existing Linux Clang CI lane runs the same route after `--suite state`.
That invocation qualifies the native save subset and reports the Darwin host
protocol as unsupported; it does not promote Linux filesystem behavior to a
qualified result or replace the measured Darwin row.

The final review follow-up and any targeted repairs are recorded in the Phase
05 review report. To rerun the portable evidence controls and sanitizer
timeouts individually:

```sh
ctest --preset sdk-debug --no-tests=error -R '^sdk_save_registration$' --output-on-failure
ctest --preset sdk-tsan --parallel 1 --no-tests=error -R '^sdk_isolation$' --output-on-failure
ctest --preset sdk-asan-ubsan --no-tests=error -R '^sdk_state_hostile$' --output-on-failure
```

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

## Planning security register gate

`python3 tests/tools/check_security_register.py <workstream> [--require-closed] [--phase NN]`
checks the `phases/*/NN-SECURITY.md` registers of one workstream, or only
`phases/NN-*/NN-SECURITY.md` with `--phase NN`. The CTest names are
`planning_security_register_consistency` and
`planning_security_register_mutations` (the latter runs the mutation suite in
`tests/tools/test_check_security_register.py`). The first is a consistency check
only: a green CTest never means the threats are closed.

The blocking threshold is `workflow.security_block_on` from
`.planning/workstreams/<workstream>/config.json` when that file sets it, and
otherwise from `.planning/config.json` (default `high`). A workstream config is
local GSD runtime state that is not tracked, so it may not lower the gate: a
value less strict than the root value (for example `critical` over `high`) fails
with `weakens security_block_on`; an equal or stricter value is accepted. A
missing or unreadable root config, an unreadable workstream config and an
unknown severity at either level fail with `FAIL:`. The `PASS:` line names the
threshold and its source (`block_on high from .planning/config.json`).

Default mode checks consistency only. The YAML frontmatter (the first `---`
block) is read as a set of top-level keys. Keys are compared after removing
quotes and case-folding for duplicate and guarded-key detection, so
`"threats_open"`, `'threats_open'` and `Threats_Open` are one key, and any
duplicate top-level key in any quoting form fails (T-04-48). The `threats_open`
and `status` declarations themselves must be spelled exactly (bare or quoted, no
case folding): `Threats_Open: 0`, `"THREATS_OPEN": 0` and `Status: verified` fail
with `<key> key must be spelled exactly`, because GSD reads the literal key. The
integer accepts ASCII digits only, so `threats_open: ٣` fails as not a bare
non-negative integer; the `verified` value stays case-insensitive (G4WR-02,
G2IN-01). A commented or indented `threats_open`/`status` key fails.
Unsupported YAML lines (flow mappings, merge keys, complex keys, anchors,
aliases, escaped quoted keys, top-level list items) fail with their line number
instead of being skipped. `threats_open` must be a bare non-negative integer,
optionally followed by a ` # comment`, and must equal the open rows at or above
`workflow.security_block_on` across every GFM table whose header's first cell,
whitespace-collapsed and case-folded, is `Threat ID`. Such a table is indented 0
to 3 spaces, may omit leading and trailing pipes, has a delimiter row with the
same cell count, and runs to the first blank line or the first line that opens
a CommonMark ATX heading (0 to 3 spaces, then 1 to 6 `#` followed by a space, a
tab or the end of the line), a blockquote (`>`) or a code fence (three or more
backticks with no backtick after them on the line, or three or more tildes).
Any other line, such as `#note`, `####### x` or a backtick line whose info
string contains a backtick, is read as a row, as GFM renders it, so a line that
is not a threat row fails as a malformed row instead of hiding the rows after
it (T-04-48, T-04-62; 04-55). Lines GFM may also treat as a table end, such as
list items or thematic breaks, are read as rows too, which fails closed. A row
without a leading pipe still counts (T-04-62). Any other line whose first
cell reads `Threat ID` (4 or more spaces or a tab of indentation, a blockquote,
no delimiter row) fails as `unrecognized threat table form at line N`. Such a table must have `Severity` and `Status` columns; one that
lacks either (for example `Sev` and `State`) is an error naming its line, never
silently skipped (GWR-01). A table that only audits threats, such as the ASVS
result table in a SECURITY.md, uses another first header cell, by convention
`Audited Threat`. The `PASS:` line lists each register's blocking count
(`blocking open: 04-SECURITY.md=6, ...`). A `PASS:` therefore means the
declared count matches the rows; it does not mean the threats are closed.

`--require-closed` additionally exits 1 and prints
`FAIL: <file>: <n> blocking open threats` for each register that still has
blocking open threats. Use it, not the default mode, as the closure check.

`--phase NN` (two digits, optionally `.N`) requires exactly one matching
register, fails otherwise, and appends `scope: phase NN` to the `PASS:` line.
It scopes a closure check to one phase, so a blocking draft row in another
phase does not affect it.

`FAIL:` reasons: missing frontmatter; a missing, commented or indented
`threats_open` key; a `threats_open`/`status` key that is not spelled exactly; a `duplicate frontmatter key`; an `unsupported frontmatter
line`; a `threats_open` that is not a bare integer; an `unrecognized threat
table form`; a `misnamed security register`; a count that differs from the rows; a malformed
row, duplicate threat ID, uncontrolled status or unknown severity; a `Threat ID`
table without Severity and Status; `status: verified` (also `"verified"` or
`'verified'`, optionally followed by a ` # comment`) with a non-zero count; a missing or unreadable
`.planning/config.json` or an unknown `security_block_on`; a workstream config
that weakens `security_block_on`; an invalid `--phase`; and a workstream name
that does not match `^[A-Za-z0-9][A-Za-z0-9._-]*$`. Table cells split on
unescaped pipes only, so `\|` inside a cell is literal.

### Closure gates

Phase acceptance runs
`python3 tests/tools/check_security_register.py <workstream> --require-closed --phase NN`.
The unscoped run counts every `NN-SECURITY.md` and `NN.N-SECURITY.md` register
(names must fully match; G2WR-04). In both the unscoped and the `--phase` run,
every `*.md` file whose name contains `security` in any letter case, directly
under the scoped phase directories (every phase directory when unscoped), is a
candidate (G4IN-01). A candidate that is not a register fails as `misnamed
security register` when it has a `threats_open` key or a `Threat ID` table, so
`4-SECURITY.md`, `SECURITY.md` and `phase-04-security.md` cannot hide open
rows; otherwise it is reported as `SKIP:` and not counted (G3IN-03). `status: verified` is matched
case-insensitively (G2IN-01). Executor-recorded fix evidence never closes a row:
threat closure needs the separate headless security-audit verdict (T-04-48).
Milestone shipping runs it without `--phase`, so every register counts there,
including draft registers of later phases: a blocking draft row blocks milestone
shipping by design. The CTest is a consistency check only. The
`.github/workflows/release.yml` workflow is not wired to this gate because the
first-playable-game workstream assigns no release version (ROADMAP); assigning
one must add the unscoped `--require-closed` to that release gate.

### Review provenance

`python3 tools/verify_playable.py --check-docs` binds review dispositions to a
revision window (T-04-38, T-04-67, WR-11, G2WR-01, G2WR-02). 04-REVIEW.md must
carry exactly one `reviewed_revision` of 40 lowercase hex characters that
resolves to an ancestor of the checked head. Each disposition that is not `open`
must cite a revision, in the form `review (04-NN, <12 to 40 hex>)` or
`` revision `<40 hex>` ``, that resolves, strictly descends from the anchor of the
review round that raised the finding (never equal to it), and is an ancestor of
the head. The anchor is per round (G3WR-05): `CR/WR/IN` findings use 04-REVIEW.md
`reviewed_revision`; `GCR/GWR/GIN` findings use the commit that added
04-REVIEW-GAPS.md; `G<n>CR/G<n>WR/G<n>IN` findings use the commit that added
04-REVIEW-GAPS-R<n>.md. An ID that matches no review round, or a round file that
is not committed at the checked head, fails. Other hexadecimal text, such as
digests, is not a revision. A missing, unresolvable or out-of-window revision
fails the gate, and review crosswalk scope paths may not contain `..`.

The gate proves ordering only, relative to the review round that raised the
finding (T-04-38, G3WR-05). It does not prove that a review ran at the cited
commit, that the verdict covered the cited files, or that they are unchanged
since; that freshness comes from the focused re-review's changed-path rule. A
`--clean --check-docs` failure that is not a reported documentation error is
recorded as `documentation-check-error: <ExceptionType>` with no message text.
After a squash merge the ordering proof above cannot hold for every row; see
"History gates after a squash merge" below.

### History gates after a squash merge

The repository merges by squash only, so the first-playable-game milestone
branch history disappears from `main`. The revision gates (review provenance,
frontend receipt evidence and rights provenance) therefore tolerate selected rows
whose cited revision is gone (G5WR-01, T-04-104). User decision 2026-10-11,
"Scope tolerance": the change is in the tooling; the repository merge settings
are unchanged. There is no repository-wide mode: tolerance is decided per row.

Scope (orchestrator resolution, 2026-10-11): `main` is a single commit, so every
phase of the first-playable-game milestone was built on this branch. The
allowlist covers pre-ship records of that milestone branch. The generator lists
only rows whose cited revision is not reachable from `git merge-base HEAD main`
and that pass strictly; rows citing a revision reachable from main are never
listed and stay strict.

History-absent rule: a cited revision is history-absent when it does not resolve, or when it resolves but is neither an ancestor nor a descendant of the checked head (unrelated history, for example a squashed-away feature branch whose objects a local clone still holds). Ancestor and descendant revisions are always strict, and unlisted rows are strict in every case. A local squashed repository that still holds the branch objects and a fresh clone without them behave identically: both tolerate an allowlisted, pin-matching row, and both are strict for an unlisted row. Rationale: with does-not-resolve alone, every developer checkout that still holds the old feature-branch objects would fail `--check-docs` permanently after the squash merge while fresh clones pass; the protection is the allowlist plus the per-record pin plus (rights) the digest of the file at the checked head, not object presence.

The per-row rule: a row is tolerated only when its revision is history-absent,
the row is listed in `docs/history-allowlist.json` with a matching per-record
pin, and, for a rights row, the committed file at its path in the checked head
(a regular file, read with `git cat-file`, never the working tree) hashes to the
recorded `sha256` (G7WR-03), so untracked, ignored, dirty or hard-linked
working-tree content cannot pass or fail a row differently than a fresh clone.
The result is the same function of the records, the
allowlist and the history on full history, on the squashed main and on any
branch cut from it.

Per-record pins: the 04-REVIEW.md `reviewed_revision` field, the finding's own
04-REVIEW-DISPOSITION.md table row, the canonical digest of the receipt object,
and the canonical digest of each rights item. Appending rows, rounds or prose to
a record voids no pin; editing a pinned row voids that row only, which is then
evaluated strictly. A stale row is reported by `--history-allowlist check`, not
by `--check-docs`.

Commands: `python3 tools/verify_playable.py --history-allowlist write [--base <rev>]`
generates the file (a strict pre-check; it refuses on a squashed history and on
any row that does not verify), and
`python3 tools/verify_playable.py --history-allowlist check [--base <rev>]`
reports whether the committed file is current. `--base` defaults to
`origin/main`, the ref a pull request to main is compared with, and never to the
local `main` branch, which can be arbitrarily stale (G7CR-02); run
`git fetch origin` first, or the commands refuse because the base does not
resolve.

The in-tree anchoring of the allowlist is a consistency check, not a protection
against forged rows (G6WR-01, corrected by G7WR-01). `base_revision` must be a
commit of the repository and an ancestor of the checked head, and a row whose
revision resolves must not be reachable from `base_revision`; otherwise
`--check-docs` fails with the reason and the row is dropped to strict. Dropping
cannot change a gate outcome: tolerance needs a history-absent revision, and a
row reachable from an ancestor of the head is an ancestor itself, so it was
already strict. A real but stale `base_revision` passes, and a row whose
revision does not resolve is accepted on its pin alone, because that is the
squash tolerance itself. Forged or invented rows are therefore caught only by
the CI `--history-allowlist ci` step before merge, which regenerates the file
from the pull request history; after the squash the pins are self-attested,
and signing them would be a policy change and is not done. A repeated (kind, key, revision) row is malformed. The tolerated rights
branch hashes only a normalized path that is a regular file (not a symlink) in
the checked head's tree.
CI runs `--history-allowlist ci --base <pull request base>` on every pull
request, from a full-history checkout (G7WR-02). It runs the full `check`
whenever `docs/history-allowlist.json` differs from the base or any listed
revision is an ancestor of the checked head, which holds for every pull request
from the pre-ship branch whatever it touches: a disposition row, the receipt, a
rights item or a rights file's bytes can each make the allowlist stale without
changing it. So neither a changed nor a stale allowlist can merge from that
branch. After the milestone squash merge an unchanged allowlist none of whose
rows is in the history does not apply (the check refuses on squashed history by
design, and a voided row is strict, so `--check-docs` is the gate there). No
history-independent staleness check was added (G8IN-01): after the squash an
unrefreshed edit to a listed rights file already fails the tolerated branch's
digest check, a refreshed row cites a main commit and is evaluated strictly, and
an orphaned allowlist row is inert. The allowlist cannot be edited after the
squash because `ci` mode refuses on squashed history, so a gate that failed on
orphaned rows could never be satisfied. The CTest `qualification_history_allowlist` runs the same
check locally against `-DGLUEYNEO_HISTORY_BASE=<ref>` (default `origin/main`,
which must be fetched) and is registered only with
`-DGLUEYNEO_PRE_SHIP_HISTORY_CHECK=ON`.
It is off by default because the check refuses on a squashed or shallow
checkout, which includes main after the squash merge. `--check-docs` itself also
needs the history back to the allowlist's `base_revision` (a full clone, or
`--shallow-since` reaching it); otherwise it fails first with "history
allowlist base_revision is not a commit of this repository" (G7IN-01). Once squashed, the pins
are an accepted, documented residual (G6WR-01, deferred under the 2026-10-11
squash-tolerance decision): no signing scheme is added, and editing the
allowlist after the squash fails the CI check, because its rows no longer
resolve.

Pre-ship step, required before the milestone squash merge: run
`git fetch origin`, then `--history-allowlist check --base origin/main`; if it
reports stale, run `--history-allowlist write --base origin/main` (which lists
only strictly passing rows), commit the
file alone, run `check` again, then run the squash simulation with the committed
file. The allowlist docs/history-allowlist.json is tracked: plan 04-64
generated it after its last pinned-record change and proved it with the squash
simulation using the committed file. Later steps on this branch (for example
`/gsd-code-review` editing disposition rows, or a new receipt) make it stale
until this step runs.

Stated openly: listed rows are tolerated permanently on a squashed history, and
for them the ordering and ancestry proof is replaced by the digest pins; on full
history they are checked strictly only because their revisions are ancestors of
the checked head there. Ancestor and descendant revisions and unlisted rows
(including an unlisted row whose revision resolves on unrelated history) are
always strict: a row on this branch is strict until a pre-ship `write` lists it,
and rows added after the milestone squash merge are never covered because
`write` refuses on a squashed history.

Every row, tolerated or not, still gets the path-form, 40-hex, recognized-form,
known-round, round-file-committed and receipt-schema checks. Each tolerated row
is printed as `unverifiable-history: <item>` before the pass line (none are
expected on full history). On a tolerated frontend_receipt row the receipt-to-archived-snapshot content binding is not re-verified on squashed history; only the canonical receipt object digest is pinned.

Evidence: `SquashMergeHistoryTest`, and the real-repository squash simulation
(`build/playable-qualification/04-59-squash/` in round 7,
`build/playable-qualification/04-63-squash/` in round 8), which checks that a local
squashed clone and a fresh clone give byte-identical `--check-docs` output. Its
suite arbiter accepts a clone-only failure only for a repository-relative
ignored input under `build/` with a recorded provisioning command, after
verifying the input and showing that adding only that input to a fresh copy of
the squashed clone makes the test pass (a main-checkout pass is not evidence).
A tolerated rights row is checked against the file at the checked head of the
bound repository, so the suite's documentation copies judge it exactly as a
checkout does. No suite test checks out a live receipt revision, so the
qualification suite passes in full on a squash-merged clone; the live receipt's
committed-inventory binding stays pinned on full history by
`test_live_receipt_binds_its_committed_inventory_on_full_history`, which skips
with a recorded reason only when that revision is absent.
The residual, stated honestly: a test that is both history-dependent and
satisfied by supplying an ignored `build/` input cannot be distinguished
mechanically, so the history-dependent or environmental label is
executor-authored and is reviewed by the diff-scoped `/gsd-code-review`.

## Playable qualification tooling contracts

These contracts back the Phase 04 playable-tracer gates. A passing unit test is
evidence for the named behavior only; none of them closes a security register
row (see Closure gates).

- **Review-tool containment** (`tools/independent_review.py`, T-04-61,
  G2CR-01). A glob is not contained when any `{}` or extglob alternative begins
  with `/` or `~`, in relative and absolute patterns; `(` ends an absolute
  pattern's literal prefix. `check --revision` accepts exactly 40 lowercase hex
  characters (exit 2 otherwise, value not echoed) and matches the
  `Reviewed revision:` line as a whole line (G2WR-03). Any `CR/WR/IN`,
  `GCR/GWR/GIN` or `G<n>CR/G<n>WR/G<n>IN` finding ID and `T-NN-NNN` threat
  numbers are reviewable without editing the tool, and a malformed ID in the
  review ID list is rejected (G3WR-02). A pattern or path beginning with `$` is
  not contained, as for a `$` alternative inside a group (G3IN-01).
- **Qualification receipt errors** (T-04-11, G2CR-02, G2IN-03). Any error after
  the build yields stderr `receipt: receipt-error: <ExceptionType>` and a minimal
  fail receipt; if that write also fails the output is
  `receipt: receipt-write-failed`. Build-failure reasons pass through the
  scan-backed reason helper. Setup and entry (T-04-11): if the output directory
  or run directory cannot be created, stderr is
  `qualification: setup-error: <ExceptionType>`, with a minimal fail receipt
  (`reason: setup-error: <ExceptionType>`) when the output directory exists, or
  `receipt: receipt-write-failed` if that write fails. The script entry maps any
  uncaught error to `verify_playable: internal-error: <ExceptionType>` (exit 1)
  and an interrupt to `verify_playable: interrupted` (exit 130); argparse usage
  errors keep exit 2. No path prints a traceback. Limit: an import-time failure
  (a missing standard-library or `tools/private_paths.py` module) happens before
  the entry guard runs.
- **Snapshot integrity** (04-52). The clean qualification materializes the
  committed Git archive, and `verify_snapshot` runs before and after every
  lane. It compares the file and symlink rows (type, mode, size, SHA-256,
  symlink target) and the directory set, which must equal the parent
  directories of those rows. An added file, an added empty directory (for
  example `build/playable-qualification`) or a changed byte fails with
  `snapshot-inventory-mismatch` at the lane that caused it. Symlinked
  directories are rows, not directories. The receipt inventory schema and
  `inventory_sha256` are unchanged (directories are checked but not recorded).
  Limit: this proves the snapshot was not mutated between checks, not that a
  lane wrote nothing outside the snapshot.
- **Archive completeness diagnostics.** `_archive_members` rejects any differing
  committed-tree and tar-member path/type map with `incomplete-archive`. Its
  public error reports missing, extra and changed-type counts without source
  paths. For private investigation, the original `SnapshotError.archive_mismatch`
  retains expected/archived totals and up to five sorted differing relative
  paths with expected/archived types. Each path is capped at 160 characters;
  `path_truncated` identifies truncation. For a normal Python/CTest recurrence,
  set `GLUEYNEO_ARCHIVE_DIAGNOSTIC_DIR` to an existing private directory outside
  the repository before directly running Python/unittest or CTest from that
  shell (for example, `ctest --preset owned-debug -R '^qualification_runner$'
  --output-on-failure --no-tests=error`). Capture is off by default. The setting
  is stripped from Git/build/frontend children launched through
  `clean_environment`, including qualification Runner children; it applies to
  the directly invoked diagnostic process, not those nested lanes.
  On this rejection, `create_snapshot` writes a unique mode-0600
  `glueyneo-archive-mismatch-*.json` with the immutable commit, archive SHA-256
  and bounded mismatch metadata. Reports appear only after a complete write;
  stdout, stderr and public receipts contain no diagnostic directory or source
  paths. An invalid/unavailable sink preserves the original rejection and
  reports only that private capture was unavailable. Keep these files outside
  Git and retain the failed archive separately when available. Wrapped
  documentation errors retain the original exception as their cause. Unsafe archive paths
  still fail before mismatch metadata is collected. These diagnostics do not
  establish a cause or clear an earlier failure when a later run passes.
- **Phase 05 historical G3 source disposition.** The three 05-27 content gates
  use `tools/g3_source.py` only for the private-root predicate. Commit
  `63c1d2c217887c35de68f847ed0db59de6c6250e`, path `tools/verify_playable.py`,
  and the SHA-256 of its complete added-line text must all match before the
  exact generic temporary suffix is substituted for root scanning. The rest
  of that text is still root-scanned; identity detection and every other G3
  rule scan the original bytes. Unknown revisions, paths and byte changes
  receive the original fail-closed detection. Binary, ownership and diagnostic
  commit provenance gates retain their separate checks. This disposition does
  not change `tools/private_paths.py`, authorize a file or commit exemption,
  diagnose archive-completeness failures, or authorize a private scenario run.
  Run `python3 -B tests/tools/test_g3_source.py` for the source-disposition and
  embedded-gate regressions; historical cases are explicitly skipped in a
  source archive without Git history. The oracle is the reviewed source
  literal and exact immutable addition, not output from a reference emulator.
  Admitting this original MIT regression source adds one affirmative rights
  inventory item, intentionally increasing the exact repository-inventory
  assertion from 46 to 47; byte, path, notice and provenance checks remain
  unchanged.
- **Frontend receipt currency.** The tracked receipt is current only while no
  receipt-bound path has changed since its `source_revision`: anything under
  `src/`, `include/`, `third_party/`, `tests/fixture/` or `tests/libretro/`, or
  `tools/verify_playable.py`, `tools/private_paths.py`, `CMakeLists.txt` and
  `CMakePresets.json`. `--check-docs` binds a receipt to its own committed
  snapshot inventory and does not detect later changes, so a gap round that
  changes a receipt-bound path re-qualifies pinned RetroArch before citing the
  receipt.
- **Evidence recording** (G2WR-05, G4IN-02). First-time generation with absent
  files works. Rollback unlinks files that did not exist before, continues past
  a failed restore and raises `evidence rollback incomplete: <names>` (base
  names only) for files whose content was not restored. A failure removing a
  `.restore` or `.tmp` file never aborts the rollback or replaces the original
  error. Such leftover files are reported apart from unrestored files: after a
  full restore the error is `evidence rollback complete; could not remove:
  <names>`, and with unrestored files the `incomplete` message gains a
  `; could not remove: <names>` clause (G3WR-04). Any surviving `.tmp` file is
  named, and the original failure is always the `__cause__`. A write that
  succeeded returns normally even if a temporary could not be removed. An
  interrupt or exit is never replaced by that error: it is re-raised unchanged
  with the leftover report on stderr.
- **Lane timeouts** (G2IN-02, G4WR-01, G4WR-03). Output is drained during the
  SIGTERM grace without reaping the leader; the no-signal-after-reap invariant
  (T-04-54) is unchanged. The lane pipe is binary: the first segment, the
  drained chunks and the genuinely new tail are kept as bytes, joined in
  emission order and decoded once as UTF-8 with replacement, with one newline
  translation, so each segment is recorded once, CRLF written during the grace
  is translated and a character split across segments is whole. The earlier
  segment survives a detached descendant that keeps the pipe open (the second
  collection is bounded by `LANE_AFTER_KILL_SECONDS`, then the leader is reaped
  and the parent's pipe end closed). A lane that closed its own stdout and kept
  running is still signalled, because a closed stream no longer stops the group
  signals. Non-UTF-8 output is recorded with U+FFFD on both the normal and the
  timeout path, and no decode error escapes `Runner.command`. The lane-signalling
  regression tests wait (bounded, 30 s) for a single child ready marker,
  `lane.ready`, before the lane timeout starts, so a slow interpreter start
  cannot turn into an output failure (G5WR-02).
- **Smoke harness** (G2WR-06). A signal deferred in the launch window is always
  raised as `interrupted`, even when launch raises; a child-PID record failure is
  reported as `pid-record`, not `launch`, by both paths. The actual smoke
  (`run_smoke`) builds one diagnostic whose detail keeps the error class
  (G3IN-02). The diagnostic launch probes record `survived_window` as unknown,
  still kill the started frontend, and the probe comparison reports the finding
  `diagnostic-pid-record-failed` (G3WR-03). The diagnostic runner
  (`run_diagnostics`) stops after a `pid-record` failure of the first probe: it
  does not launch the second probe, which could not trust the PID file, and
  records it as `{"status": "not-run", "reason": "skipped-after-pid-record"}`
  (G4IN-03).
- **Rights provenance** (G4WR-04, T-04-103). `rights_revision_errors` in
  `tools/verify_playable.py` checks every `docs/rights-inventory.md` row whose
  path is not under `third_party/` (those cite an upstream pin and are exempt).
  The rule has five parts: `path` is a relative POSIX path (non-empty, not
  starting with `/`, no `..` segment, no leading `-`); `source_revision` is 40
  lowercase hex; it resolves to a commit; it is an ancestor of the checked head;
  and the blob at `path` in that commit hashes to the recorded `sha256`. The path
  form and the hex form are checked before any Git call, so no unvalidated
  inventory value becomes a Git argument. The path-form check precedes the
  `third_party/` exemption, so `third_party/../x` is rejected, and an `items`
  value that is not a list is a malformed inventory (G5IN-01). Rows of the
  milestone branch whose revision is history-absent after a squash merge follow
  "History gates after a squash merge". `--check-docs` raises on the first
  error whenever a repository is available, and the `qualification_runner` CTest
  runs the same check on the real repository. A source archive without `.git`
  skips that CTest case visibly. The refresh writes the last commit that
  changed the file by convention; the gate does not require it.

### CTest registration

`planning_security_register_consistency` is registered when
`.planning/workstreams/<name>` exists. The cache variable
`GLUEYNEO_PLANNING_WORKSTREAM` defaults to the empty string, meaning auto: the
`first-playable-game` workstream when present, with no test and a status message
in a source archive. An explicitly set name that names no
`.planning/workstreams` directory fails configure with
`GLUEYNEO_PLANNING_WORKSTREAM=<name> names no .planning/workstreams directory`.
The mutation suite stays registered unconditionally.

## Phase 05 MVS lane evidence (2026-10-14)

The configured SDK MVS lane is this exact ten-case inventory:

- `mvs_synthetic_trace`
- `mvs_media_contract`
- `mvs_import_contract`
- `mvs_failure_diagnostics`
- `mvs_import_mutation`
- `mvs_callback_contract`
- `mvs_boot_checkpoint`
- `mvs_attract_predicate`
- `mvs_board_behavior`
- `mvs_import_fuzz_corpus`

`mvs_synthetic_trace` imports the original synthetic bundle and executes its
boot checkpoint once. Callback checks run in `mvs_callback_contract`; P1 and
bus-fault checks in `mvs_boot_checkpoint`; attract/stall checks in
`mvs_attract_predicate`; and media/zoom checks in `mvs_media_contract`.
These dedicated cases retain the full assertions without repeating their
content loads in the smoke test. The smoke test retains its 60-second limit.

Historical nine-case receipts remain dated evidence and are not the current
inventory. At source revision
`e3cdebb395ca1ace8a6a54fe1fb4b309372c18c5`, the configured owned Debug run
executed 66 cases: 65 passed and `owned_cpu_inventory_check` failed because
the `CMakeLists.txt` source-manifest record was stale. All ten MVS-labeled
cases, including `mvs_failure_diagnostics`, passed. The run's private
mode-0700 archive-capture directory produced zero mismatch reports. This is a
measured partial gate, not an owned Debug pass; later SDK and sanitizer gates
and a selected-media observation were stopped at that failure.

### Plan 05-31 source-manifest reconciliation — 2026-10-15

The 05-30 CTest registration changed the authored `CMakeLists.txt` blob, so the
owned CPU source manifest correctly rejected its old file identity. Plan 05-31
used the existing `inventory.py refresh-manifest` generator; the only changed
manifest record is `CMakeLists.txt`. Its SHA-256 changed from
`25cc6cf4216e374b032e8a37215e3f00f9fefbb7d4bee0a393f9ec66330ed465` to
`fa9d01ea9081cb3c475a68253b6e64ad51ea91c51b58bedf16c2cb4864648540`. All 38
closure paths and other manifest fields are unchanged. The owned CPU source,
header, state inventory, timing tests and historical `acceptance-results.json`
remain byte-identical to the pre-refresh capture. The current manifest check
passes for 31 fields and 10 compiled sources. This reconciles source identity;
it does not qualify additional CPU behavior or rewrite the historical
acceptance receipt.

The separate `inventory.py self-test` currently fails before reaching its
mutation controls: it removes the final `bus_cycles` field and receives that
correct missing-field error, but its expected message is still hard-coded as
`reset_signal_events`. The generator and its rules remain unchanged; see
Phase 05 `deferred-items.md` for the preserved out-of-scope gate defect.

## Runtime writable-storage audit

`libretro_callback_test` intentionally links two runtime copies: the core's
private copy and the independent native reference. The CTest
`runtime_writable_storage` (label `qualification-tools`) runs
`tests/tools/check_runtime_storage.py` with the configured `nm` over the
runtime library and fails on any object symbol in writable data or
zero-initialized storage, so the two copies provably share no mutable global
state. There is no allowlist: a never-written table is made `const`. The audit
reports Mach-O sections `__DATA,__data`, `__DATA,__bss`, `__DATA,__common` and
the thread-local `__DATA,__thread_data`, `__DATA,__thread_bss` and
`__DATA,__thread_vars`, whatever the symbol binding (`external`, `private
external`, `weak external`, `non-external`), and unlinked `(common)` symbols
(T-04-56, WR-08), and ELF symbol types `D d B b G g V v` plus common
(`C c`) and small-data (`S s`). It cannot pass vacuously: `nm` output in which no
line parses as a symbol fails with `no symbols parsed`. On Windows, or with an
empty `--nm`, it reports `unsupported` (CTest skip code 77) instead of passing; a
failing `nm` still fails. The unit tests (`runtime_writable_storage_audit`) cover
canned Mach-O and ELF `nm` output.

Sanitizer builds retain the same strict symbol parser and build a storage-audit
archive from the production runtime source list with the production compile
properties and a final `-fno-sanitize=all`. The audit compares actual compile
commands: source closure and all options except output filenames and that final
override must match. Missing sources, changed definitions, or a later inherited
sanitizer option fail. `nm` still rejects every writable symbol, including any
remaining instrumentation metadata. Sanitizer execution uses the instrumented
runtime; this separate archive establishes the source's mutable-global property,
not absence of compiler-generated storage in an instrumented binary.

The configure-time `sdk_private.h` guard in `CMakeLists.txt` stays heuristic and
is an accepted residual: it inspects direct `.c`/`.cpp` sources only, top-level
targets only, ignores generator-expression links, and is enforced in static
builds as the early warning for the shared-build link failure. The storage
audit, not the guard, is the isolation control.

## Private-path scan limits

Receipts, smoke output and the artifact inventory pass through
`tools/private_paths.py` before they are written. Generic roots (`/tmp/`,
`/Users/` and the rest) match only at a path start (04-24), so repository
relative paths such as `.planning/tmp/notes.md` and `tmp/home/x` pass. Full home
paths are rejected in every canonical form (separator, percent and Unicode
variants, including composed and decomposed spellings of the same accented
character, which are normalized together, T-04-11). The bare home-directory name is also rejected as a token, with one
documented exception: when the casefolded name is a generic service-account
name (`runner`, `build`, `admin` and the rest of `SERVICE_ACCOUNT_NAMES`) and
`GITHUB_ACTIONS` equals `true`, the bare name in prose is not rejected, because
it is not a personal identifier on a hosted runner. Personal usernames are
rejected everywhere and a developer host is never relaxed, even with a generic
account name. Exporting `GITHUB_ACTIONS=true` on a host whose account has a
generic name disables only that bare-token check. This residual is accepted as
register row T-04-60 (low).

A specific root (the checkout, the temporary directory, the home directory)
matches anywhere inside a value, so unrelated text that merely embeds one is also
rejected. This over-matching is a deliberate fail-closed limit (GIN-01): matching
is never narrowed to avoid it. A structure that cannot be serialized to JSON fails
closed as `unscannable-value` (GIN-02).

## Unsupported coverage

The matching AppleClang libFuzzer archive is absent on this host, so no
coverage-guided libFuzzer lane was built or run locally. The hosted workflow
selects only the exact compiler/runtime combinations listed below. Other
operating systems, compilers, hardware profiles, arbitrary hostile host
pointers, and real-game compatibility are not qualified by these finite
diagnostic checks. A hash, bounded mutation pass, or reference-emulator result
does not establish hardware truth.

## Current platform and cost evidence

### Package consumption support matrix

This matrix is owned by the SDK package and downloaded-consumer checks. Its
identity fields are the published source/artifact, OS and architecture,
compiler and SDK, build configuration and linkage. The only outcome values are
`pass`, `fail`, `unsupported`, `skipped`, and `unknown`. A failure is retained;
skipped means the row did not execute, and unknown means no matching
observation exists. Neither state is promoted to pass. Native exchange,
durable host publication, and frontend operation evidence have their own
matrices in [native state](native-state.md), [native save](native-save.md),
and [frontend continuation](frontend-continuation.md).

| Source/artifact identity | OS / architecture | Compiler / SDK | Configuration / linkage | Outcome | Result identity |
|---|---|---|---|---|---|
| v0.2.1, source `fdc241e0f554d61c7a270cad141fd51c2aa2b334`; `glueyneo-sdk-0.2.1-linux-x86_64.tar.gz`, SHA-256 `c596341c0d83829e1112b35fc92fb255590a0df87258da22717c9476d25b3c7e` | `ubuntu24@20260927.320.1`, Linux x86_64, glibc 2.39 | GNU 13.3.0; CMake 3.31.6; Ninja 1.13.2 | Release package; downloaded C17 consumer in Release against both static and shared packages | `pass` | CI run 40222108429; release run 40222108594 |
| v0.2.1, same source commit; `glueyneo-sdk-0.2.1-macos-arm64.tar.gz`, SHA-256 `4ed8cfcb60e51f6046a23e4340478107aa5dd64c112b22854b63b3fe81cd11c6` | `macos15@20260907.0337.1`, macOS arm64, SDK 15.5 | AppleClang 17.0.0.17000013; CMake 4.4.3; Ninja 1.13.2 | Release package; downloaded C17 consumer in Release against both static and shared packages | `pass` | CI run 40222108429; release run 40222108594 |
| v0.2.1, same source commit; `glueyneo-sdk-0.2.1-windows-x86_64.tar.gz`, SHA-256 `6aefffd47053667262da7a610a1813041010fc7a04022b950dd46664e1e70dd0` | `win25-vs2026@20260925.250.1`, Windows x86_64, Windows SDK 10.0.26100.0 | MSVC 19.51.36260.0; CMake 4.4.3; Ninja inside the Visual Studio environment | Release package; downloaded C17 consumer in Release against both static and shared packages | `pass` | CI run 40222108429; release run 40222108594 |
| Local source guide at `197810eb4c4b971020f593685795ebb343b8f2c6`; manifest version `0.1.0`; no published artifact | Darwin 25.6.0 arm64 | AppleClang 21.0.0.21000101; CMake 4.4.3; Apple SDK identity not recorded by this guide run | Staged Release source build; static and shared installed targets; C17 consumer | `pass` | `sdk.docs.runnable-entry-guide`: 28 commands, 12 result records, 143 assertions |
| Current Phase 07 Linux Clang sanitizer consumer gate at source `197810eb4c4b971020f593685795ebb343b8f2c6`; no Linux artifact was built by the local guide run | Linux x86_64 hosted Clang lane; exact runner/compiler result for this source is not observed | Compiler / SDK identity `unknown` for this source revision | Installed sanitizer consumer check; hosted result remains required | `unknown` | BUILD-05 remains pending until the exact hosted result in 07-08 |

The v0.2.1 rows qualify that release's bounded diagnostic package. They do not
place the later continuation/persistence examples in that older artifact. The
local row is the exact command run for the current source guide, not a hosted
or published package result. The archive names and digests are retained in the
[published expected manifest](../.planning/workstreams/cpu-bus-diagnostic-sdk-alpha/milestones/v0.1-phases/03-distributable-release-qualification/03-PUBLISHED-EXPECTED-MANIFEST.json).

The current hosted qualification is bound to source revision
`fdc241e0f554d61c7a270cad141fd51c2aa2b334`. [CI run
40222108429](https://github.com/szTheory/glueyneo/actions/runs/40222108429)
passed its seven-lane aggregate with 1,159,842 total checks: 1,159,040 matrix
assertions and 802 public-content input checks. Its maximum cold-build duration
was 42.427865 seconds. The measured matrix-command critical path was 72.156
seconds, and summed matrix-command execution was 3.5422573167 runner-minutes.
These command measurements exclude checkout, upload, aggregate, and other job
overhead; they are not the workflow's end-to-end critical path or GitHub billing.

The same commit is published as [SDK v0.2.1](https://github.com/szTheory/glueyneo/releases/tag/v0.2.1).
[Release run 40222108594](https://github.com/szTheory/glueyneo/actions/runs/40222108594)
passed the archive checks and all three downloaded consumers before publishing.
The archive compiler profiles were GNU 13.3.0 on Linux x86_64 (`ubuntu-24.04`),
AppleClang 17.0.0.17000013 on macOS arm64 (`macos-15`), and MSVC 19.51.36260.0
on Windows x86_64 (`windows-2025`, Windows SDK 10.0.26100.0); the Windows
archive build uses Ninja inside the Visual Studio environment. The separate CI
matrix exercises Linux Clang and GNU, macOS AppleClang, Windows MSVC, and Linux
Clang sanitizer and fuzz lanes. This evidence qualifies only these named
profiles. The declared CMake 3.20 floor, other compiler/platform combinations,
original hardware behavior, and general game compatibility remain unqualified.

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

The [hosted receipt](../.planning/workstreams/cpu-bus-diagnostic-sdk-alpha/milestones/v0.1-phases/03-distributable-release-qualification/03-CI-HOSTED-RECEIPT.json)
retains exact job/build/fixture/binary identities and seven previous failed
attempts. Those results apply to their recorded source revision and do not
establish a broader platform range, original-silicon behavior, or general-game
compatibility. The v0.2.1 evidence above supersedes the earlier statement that
publication and downloaded-archive checks were pending. Failed, skipped,
unsupported, and unknown outcomes remain distinct and cannot contribute passing
assertions.

A new SHA requires new evidence for claims about that SHA; documentation-only
planning edits do not invalidate the retained exact-source release qualification.
The release App's scoped authority, recovery and publication observations are
recorded separately from compiler and diagnostic correctness.

The later PR head `2c1b40bc27980da6d3d29fd3ef42436ce8e6b8e1` also passed all six
matrix lanes, `public-content`, and `ci-policy` in [CI run
37618668537](https://github.com/szTheory/glueyneo/actions/runs/37618668537).
That run extends the pass outcome to that exact revision. The detailed
compiler, SDK, assertion, and artifact table above remains bound to
`2c7926383222cee174ede5ddde06374b43002191`; the later run's timings do not
replace those measurements. At that time the protected merge and release
evidence were pending; v0.2.1's later exact-source results are listed above.
First-time fork approval and execution remain deferred and unverified.

The rights inventory currently contains affirmative records for the shipped
original diagnostic material and pinned Unity subset. No commercial game ROM,
BIOS, private corpus, or private capture is licensed into the release. Any new
item without an affirmative record tied to exact bytes remains excluded and its
rights status unknown; a clean content scan cannot resolve that question.

## Required CI aggregate

The focused selectors are `matrix` (SDK diagnostic CTest groups and installed
static/shared consumers), `release-consumer`, `ci-policy`, `public-content`,
`sanitizer`, and `fuzz`; `all` retains the full local verification path. The
`public-content` selector first runs bounded scanner regression fixtures, then
scans the actual selected source/history and rights inventory. Disposition
fixtures retain exact available audited blobs without scanning unrelated local
refs; the actual scan keeps its existing limits and fails closed. Release
consumer setup copies only tracked distributable source paths, so ignored local
qualification data cannot inflate fixture setup or enter its source tree.
The matrix command is `python3 tools/verify_sdk.py --suite matrix`. It records
compiler, SDK, runner image, architecture, build and fixture identities from
the active runner. Sanitizer and seeded mutation controls run as separate Linux
Clang lanes in `.github/workflows/ci.yml`.

The local MVS CTest lane additionally binds the importer executable selected by
the generated CTest commands to its artifact digest and complete source closure,
including the vendored zlib sources, headers, license, and CMake build inputs.
The collector checks that proof immediately before and after the named MVS test
run and rejects a missing, substituted, or stale importer identity. Before the
SDK Debug build, it removes the existing importer artifact and requires the
build to recreate it before the expected digest is captured. This rejects a
same-path substitute present before collection begins. Existing non-MVS
evidence records may omit this MVS-specific field.

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
read-only API check at that earlier qualification observed the strict
`CI / ci-policy` check and one approval, with stale reviews dismissed and
approval required after the last push. That dated configuration observation
did not itself establish a protected merge. PROJECT-D-50, approved on
2026-10-25, now accepts independent exact-SHA GSD review with strict protected
current-head checks and zero GitHub-account approvals. The v0.2.1 delivery
receipt records actual protected expected-head merges, required checks and
release App publication. First-time fork approval and execution remain deferred
and unverified; an owner PR does not establish a live fork event.
These receipts establish only the named outcomes at their recorded revisions,
not a broader platform range. Runner execution minutes and matrix critical path
are computed from measured verification command durations after checkout; they
exclude checkout/upload overhead and GitHub's billing rounding. They describe
those observed lane commands only.
Public-content scanning is detector coverage, not proof
that every private value is absent, and it cannot establish redistribution
rights.

## Phase 05 Plan 05-32 inventory self-test repair

On 2026-10-15, before the first source or test repair, Plan 05-32 froze its
immutable entry at `3e537838f556edbe93bb2400efaf6bd213677668` (tree
`68a0f3bc48a1bf2dd685cd591f0efbb14d2869ba`). The SHA-256 of the complete
`git ls-files --stage -z` index inventory was
`34b04960678952d13f6a7623af92e7c6c8228b05b7719cbd4396526cd9d5d612`.
All five declared repair paths were clean in both index and worktree. The
ignored, mode-0700 `local/qualification/05-32-entry/` contains 46 read-only
source and history snapshots: five repair sources, 21 unchanged source,
contract, timing, acceptance, oracle, budget, scanner and rights files, and 20
Phase 05 validation, ledger and 05-27/05-30/05-31 plan, summary, review and
history files. The separately checksum-bound entry manifest records all five
repair blob/content identities, unchanged-path identities and the snapshot
inventory. Its SHA-256 is
`e2dea4cbc88378833dd757e6735eb64535d375f5cb85830af45a2b58d35b3092`; the
checksums manifest SHA-256 is
`589d117ffe9b0d39cd7f6ae1c0df129a5a9c9ae24c451d3af1f0f3ec27dda65c`.
Together the snapshot files and entry manifest have 47 checksummed items. All
private payloads and the raw test report remain ignored local evidence.

| Repair path at entry | Git blob | SHA-256 |
|---|---|---|
| `tools/owned_cpu/inventory.py` | `a5b474e83eb4ea4086c527e8f533747e8ad865bf` | `8d5be1ea3abc0dc51f1e1c7ef756798feae545d9a06fd2d8ead42d71961dff5b` |
| `tests/owned_cpu/test_inventory.py` | `03ff58e023304996d6bcc46a2553c1da9966d6a2` | `1e7de1d4866eea31ce22d168bf714b1b4f5e7a74c4aa030335c36f950d487c74` |
| `experiments/owned_cpu/state-inventory.json` | `9af5bc735c712d683a6aad32c7dcfed223b7acf8` | `49d5eedcc5570d29f1ff6f76b37e44a5c8805164d584e5c93a5ea8aa9cc30d01` |
| `experiments/owned_cpu/source-manifest.json` | `ee990337695b9932a0655fd9ba38a603705c14d7` | `745bc9a23c1f3b4fbf80843cb9709de266012b6e559b981fc2c84d6cd467ca50` |
| `docs/testing.md` | `b6d7a72c44a1b038ac70f89738afe1b7c02c0e00` | `d181dbc9ed6063d9b8a4d123143543927ec69f8fd401998c4db4947813739253` |

The test-first command
`python3 tests/owned_cpu/test_inventory.py InventoryControls.test_self_test_reaches_every_mutation_control InventoryControls.test_self_test_rejects_suppressed_named_control -v`
ran two tests and exited 1. The target test failed because the actual
`run_self_test` removes the final `bus_cycles` row while asking for the named
`reset_signal_events` rejection, so it stops before the later named and
manifest controls. `gsd_run check tdd-red-evidence` classified the unchanged
captured unittest report as `RED_EVIDENCE_OK`; the complete report remains in
ignored local evidence. This records the original failure before the
implementation changed. The dated 05-31 failure above remains historical
evidence and is not rewritten by this repair.

After GREEN, the two new entry-point regressions passed (2/2), the complete
owned inventory Python suite passed (13 tests), and the actual inventory
self-test passed. The inventory check reports 31 owned fields and 10 compiled
sources. The committed repair source identities are
`tools/owned_cpu/inventory.py` SHA-256
`576a0a5a37cacf441f56daa2aa292f7d507f3da9fa0e648c9c7677c047659250` and
`tests/owned_cpu/test_inventory.py` SHA-256
`526e09b25d292a87f6fc3b857e24b1ae671df0068580ef6176d68cd82c34465f`.
Only these two `source_hashes` entries changed in `state-inventory.json`.
After that commit, the existing generator updated exactly three manifest
records (`inventory.py`, `test_inventory.py`, and `state-inventory.json`),
changing only their `sha256` values. The manifest still has 38 paths in the
same order; every other record and top-level value is equal to the immutable
entry copy, including the `CMakeLists.txt` record
`fa9d01ea9081cb3c475a68253b6e64ad51ea91c51b58bedf16c2cb4864648540`.
The immutable CPU, header, private-state, timing, acceptance, oracle, budget,
scanner and rights identities remain unchanged. The owned Debug configured
denominator remains 66 pending the complete current gate; no CMake test
registration changed.

## Phase 05 Plan 05-32 current gates — 2026-10-15

The repaired inventory entry point is green on the real current document: the
two targeted regressions pass, the complete owned inventory suite passes 13
tests, `inventory.py self-test` reaches every named and four manifest control,
and `inventory.py check` reports 31 fields and 10 compiled sources with zero
mutable globals or callback-owner mutation. The full owned Debug CTest suite
passes 66/66 (126.92 seconds) with the existing private archive-capture sink
enabled; it produced no mismatch capture. This does not explain either
historical archive failure.

| Gate | Actual result | Evidence boundary |
|---|---|---|
| SDK Debug MVS/Z80/storage | 18/18 CTests pass; SDK matrix controls 8/8; evidence 28 cases and 62 assertions pass; qualifier freshness passes | Synthetic/build/identity controls only; no selected boot claim |
| Pinned sources | MVS S25, S25b, S25c, S25d and S25e pass; the pinned Z80 source/state/license check passes | Exact existing source identities; no pin or dependency changes |
| Owned ASan/UBSan | 66/66 CTests pass (132.38 seconds) | Current owned Debug target |
| SDK ASan/UBSan | 53/53 CTests pass | Current SDK target |
| SDK MVS/Z80 TSan | 16/16 CTests pass (136.65 seconds), with no exclusions or unsupported cases | Required MVS/Z80 selection |
| Phase 04 docs and public content/history | Pass; 48 rights rows, 136 current source files, 3,724 history files and zero findings | Detector coverage only; no redistribution-rights claim |

The task-2 G3 run passed after commit `19367c7` (188 segment-3 commits,
196 local media digests, 49 media names, zero guest PCs). Task-3 G3 is rerun
after each task-3 commit and its final result is recorded in the execution
summary. Full logs and raw private reports remain in ignored local qualification
storage. Before the required fresh review, the shared validation table still
ends at C46/R22 and the single carried C47 observation remains unattempted.


## Phase 05 Plan 05-32 independent review and diagnostic outcome — 2026-10-15

The same-run full-entry-base repair review is CLEAR with zero open findings. The immutable entry's two original snapshot pointer strings remain unresolved; the separate checksum-bound alias mapping was independently verified against the fixed base, and all 47 protected items match.

After all required current gates and the immediate post-review exact G3 pass, the one carried diagnostic invocation returned exit 1. The ignored safe receipt records a fresh qualifier build, native invocation attempted, guest execution, and `native_execution_error`, with the bounded discriminator `sound_cpu` / `bus_access` / `bus_failure`. This consumes C47 and is not a selected-game acceptance result. The existing C1-C46 history remains unchanged; the new C47 row routes halted with no retry.

## Phase 05 C47 synthetic YM integration repair — 2026-10-15

The retained C47 discriminator does not identify the exact rejected access.
Inspection and an original synthetic program independently reproduced the
missing chip connection: YM writes were discarded and mapped reads failed.
The SSG register round-trip regression failed before repair, then passed with
real per-instance register state. No selected-media execution was repeated;
C47 and both original archive causes retain their existing unknown limits.

`build/sdk-debug/mvs_test --sound-sources` exercises that round trip, a
mirrored-port public `gn_run_mvs` reply with reset and two-instance controls,
timer-A expiry at 216 main clocks with adjacent boundaries and all 220
partitions through 219 clocks, IRQ clear/isolation, actual Z80 IM1 handler
execution, and ADPCM-A/B checked-sample failure/recovery boundaries. Oracles
derive from the immutable MAME mapping/clock/IRQ/fallback rows S25x-S26 and
the pinned ymfm timer/register logic. They establish emulator-differential
synthetic behavior, not selected-driver or physical-hardware fidelity.

The initial full SDK Debug and ASan/UBSan runs passed 54/54 each (the added
runtime host-source audit accounts for the increase from 53). The initial
affected TSan selection passed 19/20 and timed out `mvs_board_behavior` at
180.20 seconds. That failure is retained. The instrumented C++ runtime now
uses `-O1`, retaining `-g`, full TSan instrumentation, all tests and the
unchanged 180-second bound, following [Clang's TSan usage guidance](https://clang.llvm.org/docs/ThreadSanitizer.html#usage).
Fresh results after that correction and review repairs are recorded below.

The source host-call audit now runs the existing exact pinned ymfm source,
license and inventory gate before treating those immutable C++ sources as
audited. Owned member calls are distinguished from global host calls;
global, `::` and `std::` calls remain rejected. Mutated upstream bytes fail
the pin, and the complete linked-symbol and writable-storage gates remain
mandatory. This lexical check is not a general C++ parser or whole-program
call-graph proof. All runtime copies contain the same admitted C++14 closure,
also when separate admission tests are disabled; packages retain its notices.
Chip-native samples are discarded internally. Audible output, public state
compatibility and Windows/MinGW execution remain unqualified.

Final affected checks after the allocator/linkage review repairs:

| Check | Measured result | Scope |
|---|---|---|
| SDK Debug affected board/admission/package/host/storage | 13/13, 21.99 seconds | Current repair source |
| SDK ASan/UBSan same affected selection | 13/13, 62.96 seconds | No sanitizer findings |
| SDK TSan complete MVS/Z80/YM/host/storage selection | 20/20, 182.85 seconds total; board test 132.63 seconds | Full instrumentation, no exclusions, unchanged per-test limits |
| Candidate installed static and shared C consumers | Five tests each pass, ten expected C exports, no unexpected C++ exports | Private candidate interface; native shared runtime symbols remain hidden |
| Matrix and evidence controls | Eight matrix tests; 28 evidence cases / 66 assertions | Full linked YM source and private-header identity controls |
| Pinned source and owned inventory | 132 source rows; 31 owned fields / ten compiled sources; self-test pass | Generated owned manifest changes only the current CMake record; CPU state inventory unchanged |

Four isolated repair-site mutants (missing read, discarded write, wrong clock,
missing IRQ) fail the driving assertions. Compiling the entry-original board
source against the same regression fails; recompiling repaired source passes.
These checks touch no selected workload. Independent re-review cleared the
compiler-runtime linkage and nested-allocation findings. Committed rights,
history/content/security and owning-G3 evidence is recorded by the debug
closeout separately; the earlier executed plan receipts remain immutable.
