# Release rights inventory

This inventory applies to public source and release archives. An affirmative row
records the project's basis for distribution; scanner findings do not determine
whether that basis is legally sufficient. Every listed path is bound to its
current SHA-256 digest and must retain the named notice. Unknown items are
excluded from release inputs and block the gate.

The Unity source is the four-file subset copied from upstream commit
`b6763fbd9cedfacaa89e2ad9fd00d615a234e355`. Its upstream MIT license is retained
in `third_party/unity/LICENSE.txt`. The diagnostic fixture recipes and manifests
are original Glueyneo work under the repository MIT license. The experimental
Musashi tree is not in the source archive and is not authorized for distribution.

The machine-readable list below is the scanner's canonical item-level record.
Update it only with exact source revision, digest, license/permission evidence,
and a notice that is present in each applicable package. Adding a fixture,
dependency, BIOS, ROM, or corpus file without an affirmative record fails closed.
Test source files are classified by exact repository-relative paths in the
scanner. Every other path under `tests/` requires its own affirmative row with
exact bytes, provenance, and notice, regardless of extension or whether its
bytes appear textual. Unknown and extensionless test paths fail closed. This
inventory includes each existing oracle document and test-evidence metadata
file, in addition to fixture recipes with separate provenance.

```json
{
  "schema": 1,
  "items": [
    {"path":"fixtures/diagnostic/manifest.json","sha256":"4cd9ae1685bf04fef90c79e588d11bb2ef442cf70324575d863f70d78f5d18cd","kind":"fixture-manifest","license":"MIT","rights":"affirmative","source_revision":"1e8fc5fdec558dcac601cc6e45187b8aecd658bf","provenance":"Original Glueyneo diagnostic fixture metadata at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/cpu/fixture-manifest.json","sha256":"015cbbca8b6898228164ca768629c39ccaa5c2f624c79f0206a0ac0d62ae3bba","kind":"fixture-manifest","license":"MIT","rights":"affirmative","source_revision":"1e8fc5fdec558dcac601cc6e45187b8aecd658bf","provenance":"Original Glueyneo CPU fixture inventory at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/cpu/guest_fixture.c","sha256":"3a85140f2c50f0958d15b4d028108539a84486016c6931f8304b533f8889a83d","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"1e8fc5fdec558dcac601cc6e45187b8aecd658bf","provenance":"Original Glueyneo diagnostic fixture recipe at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/cpu/guest_fixture.h","sha256":"12b0156be07ff491870da8be98ae9b4b853e883f0b52f8f52917deaff2e7381c","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"1e8fc5fdec558dcac601cc6e45187b8aecd658bf","provenance":"Original Glueyneo diagnostic fixture interface at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/cpu/isolation_fixture.h","sha256":"f53554e48a270accd9cdba59e7fbd588f2097afe1d9f961f7d4ab02606acfab8","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"1e8fc5fdec558dcac601cc6e45187b8aecd658bf","provenance":"Original Glueyneo CPU isolation fixture at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/owned_cpu/isolation_fixture.h","sha256":"95ca205b077d7459edd2af0194dc9af79954be011fe9c39e8f1efa7da5eb474d","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"1e8fc5fdec558dcac601cc6e45187b8aecd658bf","provenance":"Original Glueyneo owned CPU isolation fixture at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/sdk/guest_fixture.c","sha256":"bf647458d5bb8e362d66876432f30c774924600de44c7ac97a4110d57174d8cb","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"1e8fc5fdec558dcac601cc6e45187b8aecd658bf","provenance":"Original Glueyneo SDK diagnostic fixture recipe at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/sdk/guest_fixture.h","sha256":"09811d20d1556a2a356ee0ee86afeb1b811ff8b3f764a160e76c2de94f1865a1","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"1e8fc5fdec558dcac601cc6e45187b8aecd658bf","provenance":"Original Glueyneo SDK diagnostic fixture interface at the bound repository revision","notice":"LICENSE"},
    {"path":"third_party/unity/PROVENANCE.md","sha256":"c6666a2ed5b5f44efc9bc5553a0485fd49a23cdf1e64c33da8810d67362c03ce","kind":"dependency-provenance","license":"MIT","rights":"affirmative","source_revision":"b6763fbd9cedfacaa89e2ad9fd00d615a234e355","provenance":"ThrowTheSwitch/Unity immutable commit b6763fbd9cedfacaa89e2ad9fd00d615a234e355","notice":"third_party/unity/LICENSE.txt"},
    {"path":"third_party/unity/LICENSE.txt","sha256":"ec6cf55f05ba2aa538b9677b2481b9ac14a87c63594fce8a0677d4f71c583980","kind":"dependency-notice","license":"MIT","rights":"affirmative","source_revision":"b6763fbd9cedfacaa89e2ad9fd00d615a234e355","provenance":"ThrowTheSwitch/Unity immutable commit b6763fbd9cedfacaa89e2ad9fd00d615a234e355","notice":"third_party/unity/LICENSE.txt"},
    {"path":"third_party/unity/src/unity.c","sha256":"a6cc4b143075a03317d72c760b5ed67a4a12eeda1242f575464ad23f34042275","kind":"dependency-source","license":"MIT","rights":"affirmative","source_revision":"b6763fbd9cedfacaa89e2ad9fd00d615a234e355","provenance":"ThrowTheSwitch/Unity immutable commit b6763fbd9cedfacaa89e2ad9fd00d615a234e355","notice":"third_party/unity/LICENSE.txt"},
    {"path":"third_party/unity/src/unity.h","sha256":"b30ba4db1e0be1a1f6c862d359d73c91025a114977e41d3dad17103363804334","kind":"dependency-source","license":"MIT","rights":"affirmative","source_revision":"b6763fbd9cedfacaa89e2ad9fd00d615a234e355","provenance":"ThrowTheSwitch/Unity immutable commit b6763fbd9cedfacaa89e2ad9fd00d615a234e355","notice":"third_party/unity/LICENSE.txt"},
    {"path":"third_party/unity/src/unity_internals.h","sha256":"35bffad23ebc533977291e7a848c646027513572268fbfa9bd03d5ec21ee818a","kind":"dependency-source","license":"MIT","rights":"affirmative","source_revision":"b6763fbd9cedfacaa89e2ad9fd00d615a234e355","provenance":"ThrowTheSwitch/Unity immutable commit b6763fbd9cedfacaa89e2ad9fd00d615a234e355","notice":"third_party/unity/LICENSE.txt"},
    {"path":"tests/cpu/ORACLE.md","sha256":"8a1f9c113ea4fe7608a41b2fedd856c69533a1009b07f9dda6dafd276dc93ade","kind":"test-oracle-documentation","license":"MIT","rights":"affirmative","source_revision":"cb4834ed89e2422491387eb8ef4a2598fb5824dd","provenance":"Original Glueyneo CPU diagnostic oracle documentation","notice":"LICENSE"},
    {"path":"tests/cpu/audit-red-evidence.json","sha256":"e07a691f294baca90d0d1ff916cd65bb02551a2ffea15f965cfd5411476df62d","kind":"test-evidence-metadata","license":"MIT","rights":"affirmative","source_revision":"cb4834ed89e2422491387eb8ef4a2598fb5824dd","provenance":"Original Glueyneo CPU audit regression metadata; contains no ROM or BIOS bytes","notice":"LICENSE"},
    {"path":"tests/cpu/faults-red-evidence.json","sha256":"f4abb74a45b6566b26b72306de585b8a66bbc169c4e7b4f3140144cbd6f2f520","kind":"test-evidence-metadata","license":"MIT","rights":"affirmative","source_revision":"cb4834ed89e2422491387eb8ef4a2598fb5824dd","provenance":"Original Glueyneo CPU fault regression metadata; contains no ROM or BIOS bytes","notice":"LICENSE"},
    {"path":"tests/cpu/isolation-red-evidence.json","sha256":"2f2fe2cace4fd274e8ba3c21317592e208f000d1b260cffeff2b06011e57f940","kind":"test-evidence-metadata","license":"MIT","rights":"affirmative","source_revision":"cb4834ed89e2422491387eb8ef4a2598fb5824dd","provenance":"Original Glueyneo CPU isolation regression metadata; contains no ROM or BIOS bytes","notice":"LICENSE"},
    {"path":"tests/cpu/red-evidence.json","sha256":"948ac3d908b41d1b1a71724a5cd78896f554738ae8c7e6077c6f0f02839b1d78","kind":"test-evidence-metadata","license":"MIT","rights":"affirmative","source_revision":"cb4834ed89e2422491387eb8ef4a2598fb5824dd","provenance":"Original Glueyneo CPU diagnostic regression metadata; contains no ROM or BIOS bytes","notice":"LICENSE"},
    {"path":"tests/fuzz/regressions.json","sha256":"a382aa1a124b6a5afce716b8be69c25053a4cbbc009b264ec94e39edac5386ac","kind":"fuzz-regression-metadata","license":"MIT","rights":"affirmative","source_revision":"cb4834ed89e2422491387eb8ef4a2598fb5824dd","provenance":"Original Glueyneo seeded SDK mutation regression inputs","notice":"LICENSE"},
    {"path":"tests/owned_cpu/ORACLE.md","sha256":"2af54ed3fd35303c68d92b551ce02a65b1fb94f4b42a84779d03734e264771e0","kind":"test-oracle-documentation","license":"MIT","rights":"affirmative","source_revision":"cb4834ed89e2422491387eb8ef4a2598fb5824dd","provenance":"Original Glueyneo owned CPU acceptance oracle documentation","notice":"LICENSE"},
    {"path":"tests/sdk/ORACLE.md","sha256":"a981a824568820e94c81189f1e9d9995a8dfcac028921e6f3a61bda884ecfb32","kind":"test-oracle-documentation","license":"MIT","rights":"affirmative","source_revision":"cb4834ed89e2422491387eb8ef4a2598fb5824dd","provenance":"Original Glueyneo SDK diagnostic oracle documentation","notice":"LICENSE"}
  ]
}
```

## Unknown and excluded material

There is no affirmative record for game ROMs, BIOS images, private save states,
capture files, or external test corpora; none may be included. The experimental
Musashi candidate and its source history are also excluded from the release
archive. No item with unresolved ownership or redistribution rights is treated
as permitted. A specific new item requires written rights confirmation from its
rights holder, tied to its exact immutable bytes, before it can be added.

## Evidence boundary

The scanner checks path, digest, immutable provenance fields, affirmative record
status, and notice presence. It does not provide legal advice or establish that
the cited license applies. GitHub secret scanning and push protection are an
additional backstop only after the repository's hosted enablement is observed;
no such hosted configuration evidence is available in this local checkout.
