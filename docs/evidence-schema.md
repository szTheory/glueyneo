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

The baseline is one fixed workload: the original scenario A fixture, Debug SDK
configuration, one public API create/load/run/destroy path, exactly 172 guest
cycles, output tuple `10, 0x1237, 1`, twelve instructions, PC `0x012e`, STOP.
The collector performs three warmups, retains at least thirty separate load
and diagnostic-execution samples, and records three clean local builds in
distinct temporary build directories with at most two build workers. Retained
raw nanosecond samples, monotonic clock resolution, median, minimum, maximum,
range and normalized spread are recorded. No outlier is silently discarded;
any discarded observation must retain an explanation and original value.

Private test allocator counters identify owned allocation count and bytes.
The first-load workload keeps each allocation live after candidate publication,
so the post-load live count/bytes are also its exact peak for this workload.
Process RSS, when available, is separately labeled as a host-process metric;
it is unsupported if the host denies inspection and is never used to infer
owned bytes. Cold-build samples include configure and build wall time and use
separate clean directories. These three observations are low-count and
environment-sensitive. They are reproducibility data, not calibrated budgets,
tail-latency estimates, hosted runner-minutes, or gameplay throughput.

The supported local gate is `python3 tools/verify_sdk.py`. It has named focused
suite selectors and finite child-command timeouts. Unsupported optional tool
lanes remain explicit with zero pass/assertion contribution. Phase 03 owns
hosted CI, branch protection, release authority, and support-matrix qualification.
