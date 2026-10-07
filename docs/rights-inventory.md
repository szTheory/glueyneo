# Release rights inventory

This inventory applies to public source and release archives. An affirmative row
records the project's basis for distribution; scanner findings do not determine
whether that basis is legally sufficient. Every listed path is bound to its
current SHA-256 digest and must retain the named notice. Unknown items are
excluded from release inputs and block the gate.

The Unity source is the four-file subset copied from upstream commit
`b6763fbd9cedfacaa89e2ad9fd00d615a234e355`. Its upstream MIT license is retained
in `third_party/unity/LICENSE.txt`. Diagnostic and public playable fixture
recipes, manifests, guest source, and assertion contracts are original
Glueyneo work under the repository MIT license. The experimental
Musashi tree is excluded from the SDK source archive because the candidate was
not admitted. Its permissively licensed experimental source and notices remain
in repository history; `third_party/musashi/PROVENANCE.md` and
`tools/cpu/source-manifest.json` record the immutable origin, adapted/generated
bytes and retained grants. Repository publication preserves those notices.
This does not admit that candidate into the SDK runtime.

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
    {"path":"tests/owned_cpu/ORACLE.md","sha256":"518aca2bd49516bd6cd76d9357eb4fe6529e79de921fbc22b5263ed4caff6beb","kind":"test-oracle-documentation","license":"MIT","rights":"affirmative","source_revision":"da3f680279a56142552e7b253def5c76ef077a0e","provenance":"Original Glueyneo owned CPU acceptance oracle documentation, including the exact two guest instruction forms used by the playable fixture","notice":"LICENSE"},
    {"path":"tests/sdk/ORACLE.md","sha256":"a981a824568820e94c81189f1e9d9995a8dfcac028921e6f3a61bda884ecfb32","kind":"test-oracle-documentation","license":"MIT","rights":"affirmative","source_revision":"cb4834ed89e2422491387eb8ef4a2598fb5824dd","provenance":"Original Glueyneo SDK diagnostic oracle documentation","notice":"LICENSE"},
    {"path":"tests/fixture/ORACLE.md","sha256":"7e8a9e3321b6850ec1906f8a62f33578e3271e8c91ae9f4ea9b1d0cde3f508e2","kind":"test-oracle-documentation","license":"MIT","rights":"affirmative","source_revision":"0216c4f1d4fd3a0854221cbf0ec926ba2df98be1","provenance":"Original Glueyneo public fixture oracle, with primary CPU-manual and community board-reference ancestry; no hardware-truth claim","notice":"LICENSE"},
    {"path":"tests/fixture/public_guest.c","sha256":"597b3e01b9fc0d58328e37573d945a3b067e55604017683a084ffc1028788555","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"da3f680279a56142552e7b253def5c76ef077a0e","provenance":"Original Glueyneo BIOS-free GNFX v1 guest, seed, bitmap, and deterministic output writer","notice":"LICENSE"},
    {"path":"tests/fixture/test_public_guest.c","sha256":"f392b2794b7dbf00a7bae24cb4184c2aabff4a6336c88934ab4c34ca0995d4b7","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"64c10656822f56691fc2d78fe8856257a39709b5","provenance":"Original Glueyneo native public-fixture assertions and generator entry point; contains no game or BIOS bytes","notice":"LICENSE"},
    {"path":"tests/fixture/rights-manifest.json","sha256":"0b9eab10fc6a8f42096cab5c5f4a6a2136fad788da23d37344c8a816f5381404","kind":"fixture-rights-manifest","license":"MIT","rights":"affirmative","source_revision":"0216c4f1d4fd3a0854221cbf0ec926ba2df98be1","provenance":"Original Glueyneo public fixture source, assertion, generated artifact identity, and affirmative rights record","notice":"LICENSE"},
    {"path":"tests/fixture/check_fixture.py","sha256":"af07eafd0d387dd33beb4b890305895b97022bce967942597486c337953fba38","kind":"test-tool","license":"MIT","rights":"affirmative","source_revision":"e6547a1e671a2a615315487bc5d95d5bfe442d70","provenance":"Original Glueyneo standard-library checker for fixture identity, CMake producer, deterministic rebuild, and rights metadata","notice":"LICENSE"},
    {"path":"tests/libretro/callback_harness.c","sha256":"5ad0f2de417fda4cb090fcd2744a6bdd35d09958d89697e5e1db72ccf8b81367","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"c86082da2816226b40ae8c5fa99c748a3be2b818","provenance":"Original Glueyneo Libretro callback contract harness; no game or BIOS data","notice":"LICENSE"},
    {"path":"tests/libretro/retroarch_smoke.py","sha256":"14f70ab4017792b07a5129f98472ce7141775de04bc2b4b39dbed37b2281a059","kind":"test-tool","license":"MIT","rights":"affirmative","source_revision":"6d179b4bb0ddb86bd63a6a779873ced9d852358f","provenance":"Original Glueyneo bounded RetroArch smoke automation; no private media identifiers or bytes","notice":"LICENSE"}
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
additional backstop. On 2026-10-06, the GitHub repository API reported secret
scanning and push protection enabled for `szTheory/glueyneo`. No seeded live
credential was used to test the detectors.
