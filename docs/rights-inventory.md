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

`source_revision` has one definition. For `third_party/` rows it is the upstream
commit the bytes were copied from. For every other row, `path` is a
relative POSIX path (non-empty, not starting with `/`) with
no `..` segment and no leading `-`, and `source_revision` is a commit of this
repository, written as 40 lowercase hex, that resolves, is an
ancestor of the checked head, and whose blob at `path` has exactly the
recorded sha256. Those five parts (path form, 40 lowercase hex, resolves,
ancestor of the checked head, digest equals the recorded sha256) are the whole
definition and are exactly what `tools/verify_playable.py --check-docs` and the
`qualification_runner` CTest check for every non-third_party row. By convention
the refresh procedure writes the last commit that changed the file; that is a
convention, not part of the definition, and the gate does not check it.

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
    {"path":"fixtures/diagnostic/manifest.json","sha256":"3998dcd2a651fd2054edc3626cfc7494695d542c821d5e7c48c778ae4961dae8","kind":"fixture-manifest","license":"MIT","rights":"affirmative","source_revision":"183c489750d7974a09b11dadef876756b01b6210","provenance":"Original Glueyneo diagnostic fixture metadata at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/cpu/fixture-manifest.json","sha256":"015cbbca8b6898228164ca768629c39ccaa5c2f624c79f0206a0ac0d62ae3bba","kind":"fixture-manifest","license":"MIT","rights":"affirmative","source_revision":"5ed70a61abbfef82e9cea9a68369cac9a34f629c","provenance":"Original Glueyneo CPU fixture inventory at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/cpu/guest_fixture.c","sha256":"3a85140f2c50f0958d15b4d028108539a84486016c6931f8304b533f8889a83d","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"6ecfa4b98032478bb8f84730d9e8123bfebb5aee","provenance":"Original Glueyneo diagnostic fixture recipe at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/cpu/guest_fixture.h","sha256":"12b0156be07ff491870da8be98ae9b4b853e883f0b52f8f52917deaff2e7381c","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"6ecfa4b98032478bb8f84730d9e8123bfebb5aee","provenance":"Original Glueyneo diagnostic fixture interface at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/cpu/isolation_fixture.h","sha256":"f53554e48a270accd9cdba59e7fbd588f2097afe1d9f961f7d4ab02606acfab8","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"fc45d7d9d7113412cac82f483be35cb6ce41e3e5","provenance":"Original Glueyneo CPU isolation fixture at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/owned_cpu/isolation_fixture.h","sha256":"d937309249e972d274fe865fb7666e87207423db4f6d51b9326d65ef51a159ba","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"563437ed783b10c5784b723671492730f5555f8c","provenance":"Original Glueyneo owned CPU isolation fixture at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/sdk/guest_fixture.c","sha256":"bf647458d5bb8e362d66876432f30c774924600de44c7ac97a4110d57174d8cb","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"73ef17d28012a80eea845ca9b014566bc4b88f25","provenance":"Original Glueyneo SDK diagnostic fixture recipe at the bound repository revision","notice":"LICENSE"},
    {"path":"tests/sdk/guest_fixture.h","sha256":"09811d20d1556a2a356ee0ee86afeb1b811ff8b3f764a160e76c2de94f1865a1","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"73ef17d28012a80eea845ca9b014566bc4b88f25","provenance":"Original Glueyneo SDK diagnostic fixture interface at the bound repository revision","notice":"LICENSE"},
    {"path":"third_party/unity/PROVENANCE.md","sha256":"c6666a2ed5b5f44efc9bc5553a0485fd49a23cdf1e64c33da8810d67362c03ce","kind":"dependency-provenance","license":"MIT","rights":"affirmative","source_revision":"b6763fbd9cedfacaa89e2ad9fd00d615a234e355","provenance":"ThrowTheSwitch/Unity immutable commit b6763fbd9cedfacaa89e2ad9fd00d615a234e355","notice":"third_party/unity/LICENSE.txt"},
    {"path":"third_party/unity/LICENSE.txt","sha256":"ec6cf55f05ba2aa538b9677b2481b9ac14a87c63594fce8a0677d4f71c583980","kind":"dependency-notice","license":"MIT","rights":"affirmative","source_revision":"b6763fbd9cedfacaa89e2ad9fd00d615a234e355","provenance":"ThrowTheSwitch/Unity immutable commit b6763fbd9cedfacaa89e2ad9fd00d615a234e355","notice":"third_party/unity/LICENSE.txt"},
    {"path":"third_party/unity/src/unity.c","sha256":"a6cc4b143075a03317d72c760b5ed67a4a12eeda1242f575464ad23f34042275","kind":"dependency-source","license":"MIT","rights":"affirmative","source_revision":"b6763fbd9cedfacaa89e2ad9fd00d615a234e355","provenance":"ThrowTheSwitch/Unity immutable commit b6763fbd9cedfacaa89e2ad9fd00d615a234e355","notice":"third_party/unity/LICENSE.txt"},
    {"path":"third_party/unity/src/unity.h","sha256":"b30ba4db1e0be1a1f6c862d359d73c91025a114977e41d3dad17103363804334","kind":"dependency-source","license":"MIT","rights":"affirmative","source_revision":"b6763fbd9cedfacaa89e2ad9fd00d615a234e355","provenance":"ThrowTheSwitch/Unity immutable commit b6763fbd9cedfacaa89e2ad9fd00d615a234e355","notice":"third_party/unity/LICENSE.txt"},
    {"path":"third_party/unity/src/unity_internals.h","sha256":"35bffad23ebc533977291e7a848c646027513572268fbfa9bd03d5ec21ee818a","kind":"dependency-source","license":"MIT","rights":"affirmative","source_revision":"b6763fbd9cedfacaa89e2ad9fd00d615a234e355","provenance":"ThrowTheSwitch/Unity immutable commit b6763fbd9cedfacaa89e2ad9fd00d615a234e355","notice":"third_party/unity/LICENSE.txt"},
    {"path":"tests/cpu/ORACLE.md","sha256":"8a1f9c113ea4fe7608a41b2fedd856c69533a1009b07f9dda6dafd276dc93ade","kind":"test-oracle-documentation","license":"MIT","rights":"affirmative","source_revision":"14e7be15b8c9490157435a831efd32e07bee5ace","provenance":"Original Glueyneo CPU diagnostic oracle documentation","notice":"LICENSE"},
    {"path":"tests/cpu/audit-red-evidence.json","sha256":"e07a691f294baca90d0d1ff916cd65bb02551a2ffea15f965cfd5411476df62d","kind":"test-evidence-metadata","license":"MIT","rights":"affirmative","source_revision":"165022876f9bdb612c6b8841a04b8e112880c9d9","provenance":"Original Glueyneo CPU audit regression metadata; contains no ROM or BIOS bytes","notice":"LICENSE"},
    {"path":"tests/cpu/faults-red-evidence.json","sha256":"f4abb74a45b6566b26b72306de585b8a66bbc169c4e7b4f3140144cbd6f2f520","kind":"test-evidence-metadata","license":"MIT","rights":"affirmative","source_revision":"d5a535579f81b5e58f1d877d350b93786d50f387","provenance":"Original Glueyneo CPU fault regression metadata; contains no ROM or BIOS bytes","notice":"LICENSE"},
    {"path":"tests/cpu/isolation-red-evidence.json","sha256":"2f2fe2cace4fd274e8ba3c21317592e208f000d1b260cffeff2b06011e57f940","kind":"test-evidence-metadata","license":"MIT","rights":"affirmative","source_revision":"fc45d7d9d7113412cac82f483be35cb6ce41e3e5","provenance":"Original Glueyneo CPU isolation regression metadata; contains no ROM or BIOS bytes","notice":"LICENSE"},
    {"path":"tests/cpu/red-evidence.json","sha256":"948ac3d908b41d1b1a71724a5cd78896f554738ae8c7e6077c6f0f02839b1d78","kind":"test-evidence-metadata","license":"MIT","rights":"affirmative","source_revision":"6ecfa4b98032478bb8f84730d9e8123bfebb5aee","provenance":"Original Glueyneo CPU diagnostic regression metadata; contains no ROM or BIOS bytes","notice":"LICENSE"},
    {"path":"tests/fuzz/regressions.json","sha256":"a382aa1a124b6a5afce716b8be69c25053a4cbbc009b264ec94e39edac5386ac","kind":"fuzz-regression-metadata","license":"MIT","rights":"affirmative","source_revision":"615a6ac8bf678d1f9434ee769095f6eaf0df327e","provenance":"Original Glueyneo seeded SDK mutation regression inputs","notice":"LICENSE"},
    {"path":"tests/owned_cpu/ORACLE.md","sha256":"19a65b6417dd4fc7ae23d51b0fbdbe2c6d9b56543e75c7f85ef34e140c13bc51","kind":"test-oracle-documentation","license":"MIT","rights":"affirmative","source_revision":"563437ed783b10c5784b723671492730f5555f8c","provenance":"Original Glueyneo owned CPU acceptance oracle documentation, including the exact two guest instruction forms used by the playable fixture","notice":"LICENSE"},
    {"path":"tests/sdk/ORACLE.md","sha256":"14112f4cc3db2aba5180c2c979c9d802f10da2742694e71cdc50f6712d51e428","kind":"test-oracle-documentation","license":"MIT","rights":"affirmative","source_revision":"183c489750d7974a09b11dadef876756b01b6210","provenance":"Original Glueyneo SDK diagnostic oracle documentation","notice":"LICENSE"},
    {"path":"tests/fixture/ORACLE.md","sha256":"7e8a9e3321b6850ec1906f8a62f33578e3271e8c91ae9f4ea9b1d0cde3f508e2","kind":"test-oracle-documentation","license":"MIT","rights":"affirmative","source_revision":"e6547a11dbb631ca301bba6a727bd24c83646fc3","provenance":"Original Glueyneo public fixture oracle, with primary CPU-manual and community board-reference ancestry; no hardware-truth claim","notice":"LICENSE"},
    {"path":"tests/fixture/public_guest.c","sha256":"597b3e01b9fc0d58328e37573d945a3b067e55604017683a084ffc1028788555","kind":"fixture-source","license":"MIT","rights":"affirmative","source_revision":"da3f680279a56142552e7b253def5c76ef077a0e","provenance":"Original Glueyneo BIOS-free GNFX v1 guest, seed, bitmap, and deterministic output writer","notice":"LICENSE"},
    {"path":"tests/fixture/test_public_guest.c","sha256":"f392b2794b7dbf00a7bae24cb4184c2aabff4a6336c88934ab4c34ca0995d4b7","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"64c10656822f56691fc2d78fe8856257a39709b5","provenance":"Original Glueyneo native public-fixture assertions and generator entry point; contains no game or BIOS bytes","notice":"LICENSE"},
    {"path":"tests/fixture/rights-manifest.json","sha256":"0b9eab10fc6a8f42096cab5c5f4a6a2136fad788da23d37344c8a816f5381404","kind":"fixture-rights-manifest","license":"MIT","rights":"affirmative","source_revision":"e6547a11dbb631ca301bba6a727bd24c83646fc3","provenance":"Original Glueyneo public fixture source, assertion, generated artifact identity, and affirmative rights record","notice":"LICENSE"},
    {"path":"tests/fixture/check_fixture.py","sha256":"af07eafd0d387dd33beb4b890305895b97022bce967942597486c337953fba38","kind":"test-tool","license":"MIT","rights":"affirmative","source_revision":"3c88019acc9b8ce3ed37b3bbfff8fd6a9531d949","provenance":"Original Glueyneo standard-library checker for fixture identity, CMake producer, deterministic rebuild, and rights metadata","notice":"LICENSE"},
    {"path":"tests/libretro/callback_harness.c","sha256":"5ad0f2de417fda4cb090fcd2744a6bdd35d09958d89697e5e1db72ccf8b81367","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"c86082da2816226b40ae8c5fa99c748a3be2b818","provenance":"Original Glueyneo Libretro callback contract harness; no game or BIOS data","notice":"LICENSE"},
    {"path":"tests/libretro/retroarch_smoke.py","sha256":"3255774a14e81d97579b328bc642b82f58caa2f765d55da266ffa324b1e8c60b","kind":"test-tool","license":"MIT","rights":"affirmative","source_revision":"443f980963d89a8d48720e426878ff434cdada2d","provenance":"Original Glueyneo bounded RetroArch smoke automation; no private media identifiers or bytes","notice":"LICENSE"},
    {"path":"tests/chips/Z80-ADMISSION.md","sha256":"3a6c332b872fd254ae27afee974e737f3d8a4b475eb5353df74b6befa8d61548","kind":"test-document","license":"MIT","rights":"affirmative","source_revision":"96d9d8445a2a82506d0145aedabb08a7215897ca","provenance":"Original Glueyneo qualification record; original prose and evidence table under the project MIT license.","notice":"LICENSE"},
    {"path":"tests/chips/check_ym2610.py","sha256":"2032ff3ba6d8921c49c77a4ff394d7299a4273fe56d45f35762519d738639794","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"2647a987d64ddf22af175f3a4184613012a70964","provenance":"Original Glueyneo source-provenance check for the pinned YM2610 candidate; no third-party implementation is copied into this script.","notice":"LICENSE"},
    {"path":"tests/chips/check_z80_source.py","sha256":"b86187a26f3641b2dd69303d4bcf9948e9703eba02e8280a081b03e1b2a7d57c","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"e1e472727efe91b1b8777391ec134911da4b13b7","provenance":"Original Glueyneo source-provenance and inventory check for the pinned Z80 candidate.","notice":"LICENSE"},
    {"path":"tests/chips/test_ym2610.c","sha256":"9a77b78857ed947097374205ac50b545c2130805ef48af6cb4e0829ec38e9463","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"34e2a343cac023a48224d8a2d4324672eb86f1b1","provenance":"Original Glueyneo test harness for the isolated YM2610 adapter; no commercial media or third-party test vector payload is included.","notice":"LICENSE"},
    {"path":"tests/chips/test_z80.c","sha256":"55a899b4ff040105b24ac4b27a74c02e65bf1b2ead9b9ebcc834409b13e1b327","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"96d9d8445a2a82506d0145aedabb08a7215897ca","provenance":"Original Glueyneo test harness for the isolated Z80 adapter; no commercial media or third-party test vector payload is included.","notice":"LICENSE"},
    {"path":"tests/consumers/test_playable_install.py","sha256":"f79e82969c82966082a3ab817560d75cd2d64a18f3268374a5254c8c347d077f","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"290e218fe4bed3f11f984fef0d4f2f768d23917d","provenance":"Original Glueyneo installed-consumer qualification script.","notice":"LICENSE"},
    {"path":"tests/libretro/test_retroarch_smoke.py","sha256":"5c0e57e3c2f512e86675ca7cb778a16916253b9f2b03228b30469c3e737af495","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"fe3db246567e5631e3185f007022ee8da4496345","provenance":"Original Glueyneo structural Libretro smoke tests; they do not include private media or assert actual frontend behavior.","notice":"LICENSE"},
    {"path":"tests/mvs/fuzz_import.c","sha256":"9a7020e785dd061c1fb171d1fec472005b833d056c15ae0a4f3a6afdf87cb99e","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"716117286ceef474bf898121731b520f20ae2aab","provenance":"Original Glueyneo bounded MVS importer fuzz harness and synthetic inputs.","notice":"LICENSE"},
    {"path":"tests/mvs/test_mvs.c","sha256":"d7db16f288a4d6aaa6482ae0e869d004aaf20086ac58e66f4cf86257edbd9d17","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"563437ed783b10c5784b723671492730f5555f8c","provenance":"Original Glueyneo MVS contract and synthetic guest tests; no commercial game or BIOS bytes are included.","notice":"LICENSE"},
    {"path":"tests/mvs/test_mvs_qualification.py","sha256":"9992903704a559ba3da472a4a411eca765767c380486201a51a76dae423c39cf","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"a7c54badc022199be4f27fd811f024d9e517b649","provenance":"Original Glueyneo public synthetic MVS archive qualification tests.","notice":"LICENSE"},
    {"path":"tests/tools/test_verify_playable.py","sha256":"ca04cacfc7089d59310c4aa0a3fc61a25939539479626adc3ee072972b471797","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"1a208248331f7137610e2b60864d6dcc1b79f4d2","provenance":"Original Glueyneo behavioral tests for the playable qualification verifier.","notice":"LICENSE"},
    {"path":"tests/tools/test_private_paths.py","sha256":"1c29475dba8e52a0c62d9bdb6e31525f09bc60af5f348b7f4333fc8cff475d46","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"722127e87aa56fff775130c948e59a53c928546f","provenance":"Original Glueyneo regression tests for private-path redaction and public-sink scans.","notice":"LICENSE"},
    {"path":"tests/tools/check_security_register.py","sha256":"12a1204e03f899bc5465ce259db6ee11ea0eabd048ff13b5fea4d83272a21340","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"443f980963d89a8d48720e426878ff434cdada2d","provenance":"Original Glueyneo security register blocking-count invariant.","notice":"LICENSE"},
    {"path":"tests/tools/test_check_security_register.py","sha256":"fe8de1328a6d623a7184d9635cd01ca9ab72cf62a47c9f826f19c9afc0fcb4d3","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"fe3db246567e5631e3185f007022ee8da4496345","provenance":"Original Glueyneo mutation tests for the security register invariant.","notice":"LICENSE"},
    {"path":"tests/tools/test_independent_review.py","sha256":"47d0f065d17fc5ba86e17810a0763bb4df139ba97b1ed3bb15833df9f341ba60","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"e1c3ddc9e7ffcfec7f626524d1e0ba61e1f6e62c","provenance":"Original Glueyneo tests for the independent-review containment, verdict and transcription gate","notice":"LICENSE"},
    {"path":"tests/tools/check_runtime_storage.py","sha256":"38770e6d3517f30a9622b0eb32a066bbe5ece7c132d488995766c97d5b716f5d","kind":"test-tool","license":"MIT","rights":"affirmative","source_revision":"6c96250c820395fe196a84b51298b14c24c289a5","provenance":"Original Glueyneo writable-storage audit for the runtime library; standard library only","notice":"LICENSE"},
    {"path":"tests/tools/test_check_runtime_storage.py","sha256":"10ccda3d6c434b12f969adbc6b38c0aab767b061b226ab6fa5b3e8e10e1272d3","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"c3053527367675e697eb630f5c1635b685cab916","provenance":"Original Glueyneo canned nm-output tests for the runtime writable-storage audit","notice":"LICENSE"},
    {"path":"tests/consumers/test_check_package.py","sha256":"f8876125f35eb246bbae9ba36d86b1fc615488b69405a9e9ce799eb535e1f83f","kind":"test-source","license":"MIT","rights":"affirmative","source_revision":"161bfddaf6d2ab9211929e1d33b1740984f78c9b","provenance":"Original Glueyneo tests for installed-core dependency parsing and the macOS system-path allowlist","notice":"LICENSE"}
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
