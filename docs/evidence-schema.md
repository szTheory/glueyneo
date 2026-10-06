# SDK evidence schema and local measurement protocol

`evidence/sdk/verification.json` is the current public-safe result for the exact
source inputs and local SDK build recorded in each identity. It is evidence for
the bounded diagnostic SDK only. It does not qualify a supported platform
matrix, game or BIOS compatibility, original-silicon behavior, hosted CI,
release artifacts, gameplay performance, or an enforced speed/memory budget.

## Identity and result records

Schema version 1 uses canonical UTF-8 JSON: object keys sorted lexically,
compact separators, no duplicate keys, and one final newline. File and case
arrays are sorted by their relative `path` or stable `case_id`. Digests are
lowercase SHA-256. Identity includes the full Git source revision, a digest of
the sorted relevant source-file inventory, an explicit relevant-tree dirty
flag, the owned CPU source digest, every pinned Unity source and MIT notice
digest, fixture-manifest and generated-input/output digests, built runtime and
runner digests, compiler, CMake, generator, SDK status, OS class, architecture,
build configuration, and public-safe host class. Filesystem paths in published
records are repository-relative or artifact basenames; usernames, hostnames,
serial numbers, environment dumps, private media and private corpus hashes are
excluded.

Every suite/case preserves one of `pass`, `fail`, `skipped`, `unsupported`, or
`unknown`. A passing behavioral lane requires at least one named case and a
positive assertion denominator. Each pass record carries expected and observed
values. `skipped`, `unsupported`, and `unknown` require a specific reason and
cannot increase passing-case or assertion counts. Required lanes must pass;
an all-skipped/empty aggregate fails closed. Failure records are retained
instead of being replaced by a later favorable rerun. Controls exercise named
rejection reasons for malformed, zero-count, stale, mismatched, duplicate,
noncanonical, privacy-contaminated, erased-failure, and spoofed-pass records.
The process-heavy ThreadSanitizer CTest lane runs one test at a time; its receipt
retains the earlier parallel timeout and the serial diagnostic that identified
host process/thread contention.

`fixtures/diagnostic/manifest.json` records the MIT original C fixture recipe,
source identities, build-local 522-byte ROM+RAM-prefix outputs, rights and
notices, no-firmware requirement, Unity pin/file notices, independent Motorola
manual references, explicit oracle ancestry, and limitations. Expected output
digests serialize fields as `>IIIQQQQII`: arithmetic, initialized-data, BSS,
requested cycles, elapsed cycles, overshoot, instruction count, terminal PC,
and stop reason. This avoids C-struct padding and host byte-order dependence.
The manuals support the selected CPU instructions and timing, not board timing
or physical bus behavior. The source fixture binaries are generated locally;
they are not committed.

The privacy scan rejects personal absolute paths, email addresses, and obvious
serial/host identifier fields in public records. It is a conservative text
scan, not a general secret detector: it does not inspect arbitrary binary
artifacts or infer whether an unlabelled string is private. The aggregate
therefore records only allowlisted identities and summaries rather than raw
process logs or environment contents.

## Cost protocol

The baseline is one fixed workload: the original scenario A fixture, unsanitized
Release SDK configuration, one private-test-allocator create/load/run/destroy
path around the public load/run/observe calls, exactly 172 guest cycles, output
tuple `10, 0x1237, 1`, twelve instructions, PC `0x012e`, STOP. The collector
performs exactly three warmups, retains 31 paired load and diagnostic-execution
samples, and records three clean local builds in distinct temporary build
directories with at most two build workers. Each load sample times 32
precreated independent instances, and each run sample times 32 separate
preloaded instances, in separate monotonic-clock intervals. The collector
retains each batch total and reports its integer per-operation average. This
avoids publishing a false zero when one short operation falls within a host
clock tick. Retained raw nanosecond samples, clock resolution, median, minimum,
maximum, range and normalized spread are recorded and checked against the raw
arrays. No outlier is silently discarded; every discarded observation would
need its original value and explanation, and a passing baseline currently
permits none.

Private test allocator counters identify owned allocation count and bytes for
every retained sample. The recorded peak is the maximum measured live count and
bytes after successful first load. All allocations remain live after candidate
publication and the run path makes no owned allocations, so this boundary
measurement covers the fixed workload. Process RSS is explicitly unsupported
in this record because the helper did not measure it; it is never used to infer
owned bytes. Cold-build samples include configure and build wall time and use
separate cleaned temporary directories. These three observations are low-count
and environment-sensitive. They are reproducibility data, not calibrated
budgets, tail-latency estimates, hosted runner-minutes, or gameplay throughput.

The baseline identity names the Release runtime/test library/runner hashes,
compiler identity read from generated CMake metadata, fixture and output
digests, source revision and relevant-file inventory, helper source/binary
digests, build flags, host class and exact workload. Host timing uses
`CLOCK_MONOTONIC`; guest-cycle time remains the fixed 172 cycles and is not
mixed into host nanoseconds. Reported ranges describe these samples only; they
do not establish independent-run variance or rare latency tails.

The supported local gate is `python3 tools/verify_sdk.py`. It has named focused
suite selectors and finite child-command timeouts. Unsupported optional tool
lanes remain explicit with zero pass/assertion contribution. Phase 03 owns
hosted CI, branch protection, release authority, and support-matrix qualification.

## Platform matrix evidence

The platform matrix is a separate schema from the local SDK receipt. Each
required row names one exact compiler/SDK/OS-image/architecture/configuration
combination, the full source revision, the actual CMake/compiler and fixture
identities, a runner identifier, outcome, positive behavioral assertion count,
and measured job and cold-build durations. The required rows are Linux x64
Clang and GCC, macOS arm64 AppleClang, Windows x64 MSVC, plus Linux Clang
sanitizer and seeded-fuzz controls. A green parser fixture does not execute any
of these lanes.

Outcomes remain `pass`, `fail`, `skipped`, `unsupported`, or `unknown`. Only an
observed `pass` with a positive assertion denominator can qualify a support
row. Unknown, skipped, unsupported and failed rows require a reason and never
contribute passing assertions. The aggregate requires every named row at the
same source revision. It records the slowest measured required job as critical
path and computes runner minutes from the retained per-job elapsed durations;
cold-build duration comes from a measured clean configure/build. These values
are evidence for that runner image and commit, not a generalized platform or
cost guarantee.
