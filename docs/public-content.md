# Public content and rights gate

`tools/public_content.py` scans a proposed public source tree, reachable commit
metadata, optional captured CI logs, and each supplied release archive. It uses
only Python's standard library. A clean result means this bounded detector found
no configured pattern in the bytes it read; it does not prove that every secret
is absent, that private content was never committed, or that any item has legal
redistribution rights.

Run the repository scanner with:

```sh
python3 tools/public_content.py [--log PATH ...] [--archive PATH ...]
```

The repository scan includes the exact source archive path set plus published
workflow and root release configuration files. The SDK source archive policy
remains separate. History covers all reachable Git refs and scans commit
author/committer names and addresses, subject, message, and every unique
reachable blob body, including blobs whose paths were later deleted. Each
`--log` is one bounded captured log; each `--archive` is read member by member
without extraction. The scanner emits canonical sorted JSON to
stdout, or `--json PATH`; exit status is zero for a detector-negative result,
one for a content finding, and two for an unreadable, malformed, or out-of-limit
input. Findings contain stable rule IDs and repository-relative locations only;
matched content is never included.

The scanner rejects unreadable inputs, symlinks, multiply linked or non-regular
files, unsafe/absolute/traversing/duplicate archive members, archive links and
special files, and limits exceeded before extraction. Its current bounds are
64 MiB per file or archive member; 512 MiB total for each source, history,
captured-log, or individual archive input class; 50,000 source files; 50,000
archive members per archive; and 50,000 reachable history objects. Git source
listing is bounded to 30 seconds, history metadata to 60 seconds, object-list
and object metadata queries to 120 seconds, and streamed object reading to 120
seconds. History fails closed if a reachable object, blob, aggregate byte
count, or subprocess limit is exceeded. Source paths and archive members are
measured before scanning. Reports include file/member and byte denominators for
source, history, logs, and archives; zero means that class was not supplied. A
missing class remains an uncovered class and cannot support a full
release-qualification claim.

The configured detector covers common personal POSIX and Windows paths, email identities,
machine/serial identifiers, credential assignments, common GitHub/AWS token
forms, private-key PEM and OpenPGP headers, credential-bearing URLs, and private-network
URLs. Home-directory paths are detected when they follow mentions or appear in
Markdown and parenthesized references. It does not decode arbitrary binary
formats, discover every credential shape, inspect remote
services, detect all personal data, or scan unbounded history/log/archive sets.
Most synthetic test addresses, paths, and credentials are constructed from
pieces so source text does not contain complete detector canaries. The
example-guide offline test explicitly uses `localhost` on unserved port `9` as
its HTTP proxy so accidental network access fails locally.
The scanner binds that one `private-url` disposition to the exact test path and
source digest. A changed file, another source path, a log, or an archive member
still receives ordinary detection.

The separate rights gate reads the JSON record in
[`rights-inventory.md`](rights-inventory.md), compares every tracked fixture,
test asset, and vendored dependency candidate by exact path and SHA-256. Test
source files are classified by exact repository-relative paths; every other
test path requires an affirmative inventory row, regardless of extension or
whether its bytes look like text. Unknown and extensionless test paths therefore
fail the exact path-set comparison. The gate also checks that required notices
appear in source and source archives. Unknown or changed items fail. The current
source archive contains 115 rights-candidate paths; all 115 have affirmative,
path-specific records. The inventory covers the original MIT diagnostic assets,
persistence guest, test sources and metadata, plus the Unity subset pinned to upstream commit
`b6763fbd9cedfacaa89e2ad9fd00d615a234e355`. Game ROMs, BIOS images,
save states, capture files, private corpora, and the experimental Musashi tree
remain excluded.

The silent public playable GNFX v1 tracer has a separate
[`tests/fixture/rights-manifest.json`](../tests/fixture/rights-manifest.json)
record that binds its tracked guest recipe and assertion source to the 602-byte
build output. `tests/fixture/check_fixture.py` checks those identities,
affirmative MIT rights, the single CMake producer, and the common native/
RetroArch artifact path. With `--check-rebuild --negative-control`, it invokes
the named CMake target twice and verifies that a mutated artifact is rejected.
GNFX remains a separate silent, reset-per-frame fixture.

The same manifest also records the independent GNMV v3 sound fixture:
[`public_sound_guest.c`](../tests/fixture/public_sound_guest.c) builds its
first-party launch substitute, Z80 sound program, fixed-layer marker, and
formula-generated 256-byte ADPCM-B sample; the native consumer tests the exact
recipe, signal controls, and the generated build digest. The observed owned-
debug output is 67,108,976 bytes and remains ignored build output. The manifest
also binds the original standard-library FIR design tool and the runtime
converter source. It explicitly identifies the pinned BSD-3-Clause YMFM code
as a third-party emulator dependency, not fixture authorship. The rights rows
document ownership and source provenance; a digest is an identity record, not
proof that rights apply or that the binary is a public source asset.

The same rights manifest binds the public persistence guest to its original C
recipe and the source-derived synthetic fixture it extends. Its expected
outcomes are emulator-consumer assertions only; they establish neither
hardware truth nor production BIOS or commercial-game behavior. The example's
`persistence_host.[ch]` helper is a Glueyneo-owned MIT sample copy derived from
the pinned `tests/sdk/save_host.[ch]` source at the revision recorded in the
manifest. The manifest records exact current and origin bytes and requires
maintainers to review drift against that source when the sample copy changes.
The provenance record does not claim the two implementations remain identical.

Rights are an evidence question distinct from pattern detection. A digest binds
bytes to a record; it does not prove ownership, license scope, or permission.
On 2026-10-06, GitHub reported secret scanning and push protection enabled for
`szTheory/glueyneo`. Hosted CI logs and release publication remain pending.

Before the first source push, an isolated publication clone was sanitized with
`git-filter-repo` to replace historical personal home prefixes with portable
`$HOME` references. The original local history was retained separately; it must
never be pushed. Current source bytes are unchanged by the rewrite. Historical
receipt SHA values remain point-in-time identities from the original run; the
Phase 03 publication commit map records their corresponding public history
identities. Locally retained private refs remain outside the publication set;
scan the explicit publication head with `--history-revision HEAD`. Hosted
checkouts scan every fetched public ref.

Scanner results describe only the supplied revision and inputs. Before public
delivery, refresh source and history scans against the final sanitized source
identity after all delivery-plan edits, and scan the actual source and SDK
archives plus any supplied logs. This intermediate source closure does not
qualify later changes or authorize publishing private local history.

The protected release workflow preserves its bounded source/history/archive
scan report and producer outputs. After publication, its read-only named
platform jobs download the public tag assets without credentials, compare the
actual bytes with the staged manifest, and repeat the offline source and
relocated SDK consumers. These post-publication observations are bound to the
same immutable source and archive digests in the delivery receipt.
