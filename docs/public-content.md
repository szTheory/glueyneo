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
special files, and limits exceeded before extraction. The current limits are
64 MiB per file/member, 512 MiB total per input class, 50,000 archive members,
and 50,000 reachable history objects. History fails closed if a reachable blob
exceeds these limits. Source paths and archive members are measured before
scanning. Reports
include file/member and byte denominators for source, history, logs, and
archives; zero means that class was not supplied. A missing class remains an
uncovered class and cannot support a full release-qualification claim.

The configured detector covers common personal POSIX paths, email identities,
machine/serial identifiers, credential assignments and common GitHub/AWS token
forms, plus credential-bearing and private-network URLs. It does not decode
arbitrary binary formats, discover every credential shape, inspect remote
services, detect all personal data, or scan unbounded history/log/archive sets.
The synthetic test addresses, paths and credentials are constructed from pieces
so the public test sources do not themselves contain the canary values.

The separate rights gate reads the JSON record in
[`rights-inventory.md`](rights-inventory.md), compares every tracked fixture and
vendored dependency candidate by exact path and SHA-256, and requires an
affirmative rights row for every non-code or non-text asset under `tests/`.
Unknown and extensionless test paths are treated as rights candidates. It also
requires item-level rights and checks that required notices appear in source
and source archives. Unknown or changed items fail. The inventory currently
covers the original MIT diagnostic fixture assets and the Unity subset pinned to
upstream commit `b6763fbd9cedfacaa89e2ad9fd00d615a234e355`. Game ROMs, BIOS images,
save states, capture files, private corpora, and the experimental Musashi tree
remain excluded.

Rights are an evidence question distinct from pattern detection. A digest binds
bytes to a record; it does not prove ownership, license scope, or permission.
GitHub secret scanning and push protection can provide another backstop only
after enablement is observed on the actual repository. This checkout has no
hosted repository configuration, CI-captured logs, public artifact publication,
or hosted secret-scanning evidence, so those outcomes remain pending.
