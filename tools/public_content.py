#!/usr/bin/env python3
"""Bounded public-content and redistribution-rights scanner.

Findings deliberately contain rule identifiers and repository-relative locations,
never the text that matched. A negative result describes this detector's bounded
coverage; it cannot prove that secret material is absent or that rights exist.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 50_000
MAX_HISTORY_OBJECTS = 50_000
MAX_SOURCE_FILES = 50_000
BLOCK_SIZE = 1024 * 1024
SOURCE_PATHS = (
    ".release-please-manifest.json", "CMakeLists.txt", "CMakePresets.json",
    "LICENSE", "README.md", "cmake", "docs", "examples",
    "experiments/owned_cpu", "fixtures/diagnostic", "include", "src",
    "tests", "third_party/unity", "third_party/libretro", "third_party/zlib",
    "third_party/chips", "third_party/ymfm", "tools/diagnostic", "tools/release_manifest.py",
    "tools/release_state.py",
)
# Repository publication includes workflow and release configuration even
# though the SDK source archive intentionally has a narrower file set.
REPOSITORY_PATHS = SOURCE_PATHS + (".github/workflows", "release-please-config.json", ".gitattributes")
TEST_SOURCE_PATHS = frozenset({
    "tests/cmake/test_state_test_metadata.py",
    "tests/consumers/CMakeLists.txt", "tests/consumers/check_package.py",
    "tests/consumers/header.cpp", "tests/consumers/test_exports.py",
    "tests/consumers/test_release_consumer.py", "tests/cpu/guest_fixture.c",
    "tests/cpu/guest_fixture.h", "tests/cpu/isolation_fixture.h",
    "tests/cpu/isolation_negative.py", "tests/cpu/negative.py",
    "tests/cpu/state_negative.py", "tests/cpu/test_acceptance.py",
    "tests/cpu/test_audit.py", "tests/cpu/test_cold.c", "tests/cpu/test_faults.c",
    "tests/cpu/test_guest.c", "tests/cpu/test_inventory.py",
    "tests/cpu/test_isolation.c", "tests/cpu/test_state.c", "tests/cpu/test_timing.c",
    "tests/fuzz/minimize.py", "tests/fuzz/sdk_mutation.c",
    "tests/fuzz/state_mutation.c", "tests/fuzz/state_oom.c",
    "tests/fuzz/verify_state_controls.py", "tests/owned_cpu/cold.py",
    "tests/owned_cpu/isolation_fixture.h", "tests/owned_cpu/negative.py",
    "tests/owned_cpu/negative_timing.py", "tests/owned_cpu/test_acceptance.py",
    "tests/owned_cpu/test_cold.c", "tests/owned_cpu/test_contract.py",
    "tests/owned_cpu/test_diagnostic.c", "tests/owned_cpu/test_faults.c",
    "tests/owned_cpu/test_inventory.py", "tests/owned_cpu/test_isolation.c",
    "tests/owned_cpu/test_semantics.c", "tests/owned_cpu/test_state.c",
    "tests/owned_cpu/test_timing.c", "tests/sdk/controls.py", "tests/sdk/guest_fixture.c",
    "tests/sdk/guest_fixture.h", "tests/sdk/state_controls.py",
    "tests/sdk/state_fixture.h", "tests/sdk/state_process.c",
    "tests/sdk/test_evidence.py", "tests/sdk/test_matrix_evidence.py",
    "tests/sdk/test_sdk.c", "tests/sdk/test_state.c",
    "tests/sdk/test_state_exchange.py",
    "tests/sdk/test_support.h", "tests/workflow/test_ci_policy.py",
    "tests/workflow/test_phase01_admission.py", "tests/workflow/test_phase01_docs.py",
    "tests/workflow/test_app_scope.py", "tests/workflow/test_release_build_reuse.py", "tests/workflow/test_release_identity.py",
    "tests/workflow/test_public_content.py", "tests/workflow/test_release_recovery.py",
})

PRIVACY_RULES = (
    ("personal-path", re.compile(r"(?i)(?:^|[\s\"'=(@<])/(?:Users|home)/[^\s\"')\]>]+")),
    ("personal-path", re.compile(r"(?i)\b[A-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\s\"')\]>]+")),
    ("personal-path", re.compile(r"(?i)(?:^|[\s\"'=])/(?:private/var|var/folders)/[^\s\"']+")),
    ("private-identity", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("machine-identifier", re.compile(r"(?i)\b(?:serial(?:_number)?|machine_id|hostname|computer_name)\s*[:=]\s*[^\s,}\]]+")),
    ("private-url", re.compile(r"(?i)https?://[^\s/@:]+:[^\s/@]+@[^\s]+")),
    ("private-url", re.compile(r"(?i)https?://(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)(?::\d+)?[^\s]*")),
    ("credential", re.compile(r"(?i)\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("credential", re.compile(r"(?i)\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("credential", re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key|password)\s*[:=]\s*[\"']?[A-Za-z0-9/+_=-]{12,}")),
    ("private-key", re.compile(r"(?i)-{5}BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-{5}")),
    ("private-key", re.compile(r"(?i)-{5}BEGIN PGP PRIVATE KEY BLOCK-{5}")),
)
PUBLIC_EMAILS = {"noreply@github.com", "noreply@anthropic.com"}
SYNTHETIC_PATH_MARKERS = {"private-person"}
SYNTHETIC_EMAIL_SUFFIXES = (".invalid", ".example", ".example.com", ".example.org", ".example.net")
# Audited current-source false positives. Both path and complete bytes must
# match; logs, changed files and other paths retain the ordinary detectors.
SOURCE_FINDING_DISPOSITIONS = {
    ("third_party/zlib/LICENSE", "e32ff4e00d9d94930537635291da39e7e612703334bf6fde8c7f1686fe8a45a2"): {
        "rules": {"private-identity"},
        "reason": "upstream public copyright contacts in the retained zlib license at da607da739fa6047df13e66a2af6b8bec7c2a498",
    },
    ("third_party/zlib/zlib.h", "818667d6ab6a37fe7469cb06a7f0cb2c2cb2f2c948a03e5accf1a4a74bf3020a"): {
        "rules": {"private-identity"},
        "reason": "upstream public copyright contacts in unchanged zlib.h at da607da739fa6047df13e66a2af6b8bec7c2a498",
    },
    ("tests/libretro/retroarch_smoke.py", "a2ee8649681ab38113d6d1f23241119503083be395ae7f2bba687523cf374f1d"): {
        "rules": {"machine-identifier"},
        "reason": "serial is a zero-initialized Carbon ProcessSerialNumber local variable, not a host identifier value",
    },
    ("tests/consumers/test_example_docs.py", "5dcfdcf13cfeff8d9529ecfc7746edce959bb505305ed7de2bdae3cb03f20d5b"): {
        "rules": {"private-url"},
        "reason": "the offline guide regression binds staged target sources and C17 metadata emitted by CMake, while retaining a synthetic localhost port-9 proxy; exact path and bytes are bound",
    },
}
# Exact immutable history objects audited as bounded false positives. These
# dispositions are tied to object IDs, not paths or rule classes globally:
# upstream Musashi and zlib contain public copyright contacts; historical
# redaction tests contain synthetic identity/path canaries. A changed blob is
# scanned.
HISTORY_FINDING_DISPOSITIONS = {
    "1c8033be6e079de0794a6f82b13e0c3779c6797c": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact reviewed Visual Studio guide test blob retains its synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "f295b390cadcb34a50c8ece59e67996041cab213": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact strict-selector alias regressions retain the offline test synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "90216ee3217f034dac3d19bee5918b9c86cfda5a": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact tokenized compile-policy regression retains the offline test synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "568f4b5e118528b9550925ed93b1c57047a86111": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact staged source-closure regression retains the offline test synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "c9d1ec68556b640056a27c2d4196ca5f768d1f60": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact target source-origin and Release compile-policy regression retains the offline test synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "2e70f80d961045ec8f6476e4cb0cbc3b04407a06": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact per-target Release compile metadata regression retains the offline test synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "6e5a3ec0fb8fdc78cf0aef433f78d18e9d502356": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact generator-neutral compile metadata regression retains the offline test synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "289e06a48018d46bdf571800c4b10ef05a56633b": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact Windows child-process fix retains the offline test synthetic localhost port-9 proxy; path and blob are bound",
    },
    "3d0b0de0ee4b7ccb132edd0f0d39d41f101b55b0": {
        "path": "tests/consumers/test_example_docs.py",
        "rules": {"personal-path", "private-url"},
        "reason": "exact intermediate Windows launcher diagnostic test bytes contain synthetic path canaries and the offline test localhost port-9 proxy; path and blob are bound",
    },
    "747fd5525479af237b24e8e1cbdae38c4a8c865e": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact intermediate guide regression bytes retain the offline test synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "a3d2ee98203fc48c505323f163aa4388f92b743e": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact Windows launcher regression bytes retain the offline documentation test synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "8ebe5d0c04f914d2aeb92b3947c877fba746cc16": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact updated multi-config guide regression bytes retain the offline test synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "e4e09163a26c3f43455177765ac4922b888fdce3": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact updated guide regression bytes retain the offline test synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "7cbfaa1a5e5b4c0cda12642be5364fb05215010c": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact current documentation-command regression bytes retain the offline test's synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "8fe1f746fb7ee736baf4c249e9b0696c1be82b96": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact updated documentation-command regression bytes retain the offline test's synthetic localhost port-9 proxy; path and blob identity are bound",
    },
    "239b1e38898909c88843cc39505a5ca37f4c6a2b": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact historical bytes retain the offline documentation test's synthetic localhost port-9 proxy with the refreshed measured save identity",
    },
    "2c031c28d50713b8edaabcf49262c97ee0036338": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact historical bytes retain the offline documentation test's synthetic localhost port-9 proxy with the corrected measured save identity",
    },
    "b5768eac5f6a183b6e21613d244bea18dc621c34": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact historical bytes retain the offline documentation test's synthetic localhost port-9 proxy; only the bound save-source identity literals changed",
    },
    "a66573bcf978e1bc8db8ff53dd121f38c894e31e": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact historical bytes are the offline documentation test's localhost port-9 proxy; the path and blob identity are bound",
    },
    "f5356b7f12b6876d2bbddca2fea22667a7257f84": {
        "path": "tests/libretro/retroarch_smoke.py", "rules": {"machine-identifier"},
        "reason": "exact historical bytes use a zero-initialized Carbon ProcessSerialNumber local, not a host identifier value",
    },
    "007bd7fabaee7b0c171cb38a2581abeacf0f0c15": {
        "path": "third_party/musashi/m68kmake.c", "rules": {"private-identity"},
        "reason": "immutable upstream public copyright contact; preserved source and license history",
    },
    "1c94ae35fe4334c8a1ecbb273a12e1e12a60fa79": {
        "path": "tests/workflow/test_public_content.py", "rules": {"personal-path"},
        "reason": "synthetic path canary used by the historical redaction regression",
    },
    "a57d336134217efeddab550ed53df4b89adeca5d": {
        "path": "third_party/zlib/zlib.h", "rules": {"private-identity"},
        "reason": "immutable upstream zlib 1.3.2 author attribution at da607da739fa6047df13e66a2af6b8bec7c2a498; preserve source notice",
    },
    "b7a69d058e616651eae27b3f90c0b7fd36c099b2": {
        "path": "third_party/zlib/LICENSE", "rules": {"private-identity"},
        "reason": "immutable upstream zlib 1.3.2 license attribution at da607da739fa6047df13e66a2af6b8bec7c2a498; preserve license notice",
    },
    "a4aef26d7f87492ee6b18b88648fb0860835a9a9": {
        "path": ".planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-07-SUMMARY.md",
        "rules": {"machine-identifier"},
        "reason": "plan summary quotes the urlsplit attribute expression that tripped the hostname rule; no machine identifier present",
    },
    "12fd262aa4412f648acfdfa443585e505f587e81": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact current guide test blob retains its synthetic localhost proxy; path and blob identity are bound",
    },
    "1d9fad38ddd7043dd8bd69b7110b18a311c55b93": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact current guide test blob retains its synthetic localhost proxy; path and blob identity are bound",
    },
    "108f34893a947120147108ebad7e8be6d9057fd8": {
        "path": "tests/consumers/test_example_docs.py", "rules": {"private-url"},
        "reason": "exact current guide test blob retains its synthetic localhost proxy; path and blob identity are bound",
    },
}

# Exact history blobs from the first-playable-game branch whose personal-path
# matches were audited one by one as synthetic canaries (placeholder users,
# runner homes, generic temp prefixes and detector regex fragments). Each row
# binds one object ID to its path and the personal-path rule only.
_SYNTHETIC_PATH_HISTORY_OBJECTS = (
    ("01ba5ed714cfab44cc756ca4ea48ebf6d13a42bb", "tests/libretro/test_retroarch_smoke.py"),
    ("01e17288be1d7d4ffa251e7002268f0087e48cf2", "tools/private_paths.py"),
    ("01f7afe43a0558010baea6b19f0e550b8eff7c79", "tools/verify_playable.py"),
    ("02a95ca8e61692853ac8471d46e52b4f3c6bc876", "tests/libretro/retroarch_smoke.py"),
    ("03e8c40633d5a7aac877a25b11400b019d8679ec", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW.md"),
    ("04ed3ebe998a4303b66a2cae1ad09120aa2f3562", "tests/libretro/retroarch_smoke.py"),
    ("061ae0e5ff41ba0db65f82e5d07133352dd2fe40", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-39-PLAN.md"),
    ("068e021c150ea44879ed8df797d0ac691214a9ac", "tests/libretro/test_retroarch_smoke.py"),
    ("06f30fe9012e831a2d9ded60e9e31b34f7a6341f", "tests/libretro/retroarch_smoke.py"),
    ("0b8ca440053028a0dd2aa93a4eae65222b90e499", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-43-PLAN.md"),
    ("0b9c2e673f1c9fdb87071445668025f334be8fe5", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-38-PLAN.md"),
    ("0b9e5477a71c782c0934a68e486e7e68bccc6e47", "tools/verify_playable.py"),
    ("0e4c233ecf49e81c286bae6eb2b6a4afc36c356f", "tests/libretro/test_retroarch_smoke.py"),
    ("0ecf2efc53e82693b33ca44fa2a8cc88e70ab059", "tests/tools/test_verify_playable.py"),
    ("0fc7b9fce8465a0767812a333299d2c651ef139f", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW.md"),
    ("12cf5053711a3e61d4a58ff31c372505e0f9acb4", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-30-PLAN.md"),
    ("14cf5e1320833fa415da958b005b730d0eccd49c", "tests/tools/test_verify_playable.py"),
    ("15b2c3e0b97ada59f46ad6b33d6423d524246179", "tools/verify_playable.py"),
    ("1d0b6275b2f23332a034839b51ec8061c31c6d6d", "tools/verify_playable.py"),
    ("1d9a2368e333e1270b35285bc164c11df7d55534", "tests/tools/test_verify_playable.py"),
    ("230cc2d54969ff05a32d7616ddd6951dfe883bf6", "tools/verify_playable.py"),
    ("28fdfb51c9f81b8e9576c6620e559b93e3fa2aa8", "tests/libretro/test_retroarch_smoke.py"),
    ("2b3d07159275c74ddbabc5662687d2b8737a9fa2", "tools/verify_playable.py"),
    ("2b800ae1dabe8bac52422fb620646d2df42d8581", "tests/tools/test_verify_playable.py"),
    ("2f044a6cce685e44102b95ad96c77b6860b78823", "tests/libretro/test_retroarch_smoke.py"),
    ("2fc5fc873af6d685ea5d642e6ef0a5bed16317f2", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-43-PLAN.md"),
    ("3acb9b61c85fd1d999fcce271c3e48ec5b124b80", "tests/tools/test_verify_playable.py"),
    ("3bef6e19314a571a44503e7f6a2d293d86e55c7b", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-42-PLAN.md"),
    ("42973242f18a2a5db0be4221dbc81dc6911a0c44", "tests/tools/test_private_paths.py"),
    ("4345709b3aa29b3c5b52658e2b586dc77b0f1320", "tests/libretro/retroarch_smoke.py"),
    ("455e9ab30d4ce4c16f0e45d0b10133474dce78fd", "tests/tools/test_private_paths.py"),
    ("45f1aa1fd042fa8ea886a3877d12e5bc418d3bb4", "tools/verify_playable.py"),
    ("46341d5d473cce3f1bf281ee160a6372bdbc17bc", "tools/private_paths.py"),
    ("47443d1a338c64276ca1a5d6d111b653b21e23ec", "tools/verify_playable.py"),
    ("48361d205ab4163714bdeac904b947e5a25718ba", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-37-PLAN.md"),
    ("48aadb0778117deb4785e18d7a399dc786ed8d00", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-37-PLAN.md"),
    ("4a1d73376f8fbb7a3002fd2a6f5131cb88dc8f90", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VERIFICATION.md"),
    ("4eb0b4ee267f6e59775f5691c375c0a55983690b", "tests/tools/test_verify_playable.py"),
    ("5077b42b46e3d9de135c3e129c8a1373fe91ba9f", "tests/tools/test_verify_playable.py"),
    ("5ac275071a2dc2e1f2ee06756a18edf22b6468c6", "tools/private_paths.py"),
    ("5c9f1070d209bcaab556fb04b69dcd29370458e9", "tests/tools/test_verify_playable.py"),
    ("5e15540926d28644426aa008f5bca89946692092", "tools/verify_playable.py"),
    ("60dfeba0dce7ffa7cef615187008904fbea7375b", "tests/libretro/retroarch_smoke.py"),
    ("67dfa5522bf86f2babe68f65f2534dbecfbaa9bd", "tests/libretro/retroarch_smoke.py"),
    ("69226d4d64a51aa5e7155efa087931880b753a7f", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VERIFICATION.md"),
    ("6ec4701a524bc672c61ace4e2f37c030e69e7d4b", "tests/tools/test_verify_playable.py"),
    ("721436cfa502ac53555f91bb8ac91fd45518096f", "tests/libretro/test_retroarch_smoke.py"),
    ("72c78c75dffc503c99fb705d5a25473ca3365558", "tests/tools/test_verify_playable.py"),
    ("733b608efd84b6c68928c035078f2b176d649660", "tests/libretro/test_retroarch_smoke.py"),
    ("74e36a53e893fd62e42875200862a64a72a71c32", "tests/libretro/test_retroarch_smoke.py"),
    ("7a233621d199c153ca79faa65480617c5f519307", "tests/libretro/test_retroarch_smoke.py"),
    ("7cfc7d0788f27ffc03b8f8a13ce54900227215f4", "tests/libretro/test_retroarch_smoke.py"),
    ("82dba63884ed58c3202103fe271787da4cdb012a", "tests/tools/test_private_paths.py"),
    ("85f73ded136452d7d059102f52bba2b6f787a2af", "tests/libretro/retroarch_smoke.py"),
    ("86557d6d3dff4d0d103e8790627f8d179cae2a7f", "tools/verify_playable.py"),
    ("8b966132cb5358f74596f25962d7983a460e1792", "tools/verify_playable.py"),
    ("8ecda945735658d9d66e6319a72bef4071cb4a17", "tests/tools/test_verify_playable.py"),
    ("8f9c2b532b7833e9e637bdc696e55d2b34943aaf", "tools/verify_playable.py"),
    ("901c4f0391f20ab1673e6d097b8e7535581bc5d4", "tests/tools/test_verify_playable.py"),
    ("9c15279f324dce97e757e771fa06febb2d6005f5", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-38-PLAN.md"),
    ("9ff902369760515ec67d15eae35324ef43476098", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-30-PLAN.md"),
    ("a4f3c0cfa89798fe6f72356dd58b3d2fcbde33aa", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-37-PLAN.md"),
    ("b0cc19dd2aa04d75d8462b2d480356f996d4b916", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-REVIEW.md"),
    ("b36b0f725f587a2167af7ba80ad2e7bffdc038f7", "tools/verify_playable.py"),
    ("b45cf8e0bcb3aa05ad30e818cff0c1a1d85c97bd", "tests/tools/test_verify_playable.py"),
    ("b47af0fc4422068dc62f03a4d6e7cbf33f89842c", "tests/tools/test_private_paths.py"),
    ("b7d1ce2ddd5d55d9b9db771fd16c6d8b2715f597", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-43-PLAN.md"),
    ("b924ae6c35855e5e6ef0ac00b17e87c5c828b396", "tests/tools/test_verify_playable.py"),
    ("ba616dfd7c018b6ab08c8c5e918cf970e7610dcd", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-42-PLAN.md"),
    ("bc4f1f3f43b286ae9189dab2992c35117152be68", "tests/tools/test_verify_playable.py"),
    ("bca9247d386d8392c85892a181ca6fa9f94747cb", "tests/libretro/test_retroarch_smoke.py"),
    ("bdbbe0c1b077b709bda98b0c31dfea6a99c9272d", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VERIFICATION.md"),
    ("be550c9fbfa5ebbfec4197f7acc40dd825bef639", "tests/tools/test_verify_playable.py"),
    ("c2dbe4600165e26e8b63593148931ac41789cdf9", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-14-PLAN.md"),
    ("c41e868a1afaab2da9e575c386abb18c3ae06c3e", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-10-PLAN.md"),
    ("c816e726f7ac82309c2c6dd2587b824ec799e89b", "tests/libretro/retroarch_smoke.py"),
    ("c95f19ad908f7565f7b398c8ce4448697c0ee747", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-39-PLAN.md"),
    ("cba606beb50da1dea12838706f24841f85bde727", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-42-PLAN.md"),
    ("cc60319807243a398f96365cc2bdd18589fff3d6", "tests/libretro/test_retroarch_smoke.py"),
    ("cf15e7c4f84ec1089c32696085e0bfff0cae21fd", "tests/tools/test_verify_playable.py"),
    ("d2e3231af1cf9e3363a7b06a79e2d1500040e4b3", "tests/libretro/test_retroarch_smoke.py"),
    ("dca7422fa3bc70c5fae16a378317f45aa75478ce", "tools/verify_playable.py"),
    ("de2e90e63f9aec561476129b6cad7d08ed2ce90f", "tests/libretro/test_retroarch_smoke.py"),
    ("dffbdffd12434fb453eebc0784ce7806d29ff02b", "tools/private_paths.py"),
    ("e26f3a03f9ffdf16b321b3407aeed5dffce03aff", "tools/private_paths.py"),
    ("eb51d0bb4357c1447884efa159ac8240adb76a60", "tests/tools/test_verify_playable.py"),
    ("ed37dcc0e622cb25f991854c3f2394998ae8ae5e", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-39-PLAN.md"),
    ("eef3595fd43a626d74091b8c1ed619d53df78bea", "tests/libretro/test_retroarch_smoke.py"),
    ("f28a85b8a2965f46f51c1ef80f3c5801c2dd80e7", "tests/tools/test_verify_playable.py"),
    ("f455b31816e892c45c6310c9abfa1f71f5e4ea84", "tests/libretro/test_retroarch_smoke.py"),
    ("f781000b7eb4b91ebfd138c1bd5f7fcf41a176eb", "tests/libretro/test_retroarch_smoke.py"),
    ("fd280cfbc24217d2f68b8c849f22a907d45a8538", "tests/tools/test_private_paths.py"),
    ("fd40f966998de1411b92b2ac8585f36bfa6a817d", "tests/tools/test_verify_playable.py"),
    ("fead28e7de760ab3daca8d167c3d6dc7fb0d442c", ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-38-PLAN.md"),
)
_PLAN_PATTERN_HISTORY_OBJECTS = (
    ("01c43d2ff4a43531e2c8685533374a8ce152e02a", ".planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-21-PLAN.md"),
    ("016eafeba35b6e8acbdc2fd85833adb4bc1a85a9", ".planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-22-PLAN.md"),
    ("167aa3a8021e43c6a0a149531532a2becc639906", ".planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-22-PLAN.md"),
    ("a39d0178b83cc9320c6ebdb45971b1d7fcf953dc", ".planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-22-PLAN.md"),
    ("fe678bd5cf7d6078456184c746f1b85899ab6e63", ".planning/workstreams/first-playable-game/phases/05-selected-mvs-boot/05-22-PLAN.md"),
)
_SYNTHETIC_PATH_OBJECT_IDS = [object_id for object_id, _ in _SYNTHETIC_PATH_HISTORY_OBJECTS]
_PLAN_PATTERN_OBJECT_IDS = [object_id for object_id, _ in _PLAN_PATTERN_HISTORY_OBJECTS]
if (len(set(_SYNTHETIC_PATH_OBJECT_IDS)) != len(_SYNTHETIC_PATH_OBJECT_IDS)
        or len(set(_PLAN_PATTERN_OBJECT_IDS)) != len(_PLAN_PATTERN_OBJECT_IDS)
        or HISTORY_FINDING_DISPOSITIONS.keys() & set(_SYNTHETIC_PATH_OBJECT_IDS)
        or HISTORY_FINDING_DISPOSITIONS.keys() & set(_PLAN_PATTERN_OBJECT_IDS)
        or set(_SYNTHETIC_PATH_OBJECT_IDS) & set(_PLAN_PATTERN_OBJECT_IDS)):
    raise RuntimeError("history disposition object IDs must be unique")  # G9IN-01: never overwrite silently
HISTORY_FINDING_DISPOSITIONS.update({
    object_id: {"path": path, "rules": {"personal-path"},
                "reason": "synthetic path canary in a redaction or smoke-test fixture; audited object"}
    for object_id, path in _SYNTHETIC_PATH_HISTORY_OBJECTS
})
HISTORY_FINDING_DISPOSITIONS.update({
    object_id: {
        "path": path,
        "rules": {"personal-path"},
        "reason": "planner-authored detector alternation in a plan check; audited with no user segment",
    }
    for object_id, path in _PLAN_PATTERN_HISTORY_OBJECTS
})


class ContentError(ValueError):
    """A stable fail-closed reason with no matched content in its message."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_location(location: str) -> str:
    candidate = PurePosixPath(location.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        return "<redacted-location>"
    return candidate.as_posix()


def scan_bytes(data: bytes, location: str) -> dict[str, Any]:
    """Inspect a bounded byte string and return value-free findings."""
    if len(data) > MAX_FILE_BYTES:
        raise ContentError("input-file-limit", "input exceeds the per-file byte limit")
    text = data.decode("utf-8", errors="replace")
    rules: set[str] = set()
    for rule, pattern in PRIVACY_RULES:
        for match in pattern.finditer(text):
            if rule == "private-identity":
                email = match.group(0).lower()
                domain = email.rsplit("@", 1)[-1]
                if (email in PUBLIC_EMAILS or domain.endswith("users.noreply.github.com")
                        or domain in {"invalid", "test", "example", "example.com", "example.org", "example.net"}
                        or domain.endswith(SYNTHETIC_EMAIL_SUFFIXES)):
                    continue
            if rule == "personal-path":
                path_parts = {part.casefold() for part in match.group(0).replace("\\", "/").split("/")}
                if any(marker.casefold() in path_parts for marker in SYNTHETIC_PATH_MARKERS):
                    continue
            rules.add(rule)
    digest = sha256_bytes(data)
    source_path = location.removeprefix("glueyneo-source/")
    if re.fullmatch(r"glueyneo-sdk-[^/]+/(?:static|shared)/share/licenses/Glueyneo/zlib/LICENSE", location):
        source_path = "third_party/zlib/LICENSE"
    disposition = SOURCE_FINDING_DISPOSITIONS.get((source_path, digest))
    disposed = rules.intersection(disposition["rules"]) if disposition else set()
    rules -= disposed
    return {"bytes": len(data), "sha256": digest,
            "dispositions": ([{"location": _safe_location(location), "sha256": digest,
                               "rules": sorted(disposed), "reason": disposition["reason"]}] if disposed else []),
            "findings": ([{"location": _safe_location(location), "rules": sorted(rules)}] if rules else [])}


def _read_regular(path: Path, *, reason_prefix: str = "input") -> bytes:
    try:
        info = path.lstat()
    except OSError as error:
        raise ContentError(f"{reason_prefix}-unreadable", "required input could not be read") from error
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ContentError("input-type", "input must be a regular, unlinked file")
    if info.st_size < 0 or info.st_size > MAX_FILE_BYTES:
        raise ContentError("input-file-limit", "input exceeds the per-file byte limit")
    blocks: list[bytes] = []
    total = 0
    try:
        with path.open("rb") as stream:
            while block := stream.read(BLOCK_SIZE):
                total += len(block)
                if total > MAX_FILE_BYTES:
                    raise ContentError("input-file-limit", "input exceeds the per-file byte limit")
                blocks.append(block)
    except OSError as error:
        raise ContentError(f"{reason_prefix}-unreadable", "required input could not be read") from error
    return b"".join(blocks)


def scan_tree(root: Path, paths: list[str]) -> dict[str, Any]:
    """Read only the explicitly proposed public tree and fail on links/specials."""
    if len(paths) > MAX_SOURCE_FILES:
        raise ContentError("source-count", "public source exceeds the file count limit")
    rows: list[dict[str, Any]] = []
    total = 0
    seen: set[str] = set()
    for entry in sorted(paths):
        relative = PurePosixPath(entry)
        if relative.is_absolute() or ".." in relative.parts or entry in seen:
            raise ContentError("source-path", "public source list has an unsafe or duplicate path")
        seen.add(entry)
        target = root.joinpath(*relative.parts)
        try:
            info = target.lstat()
        except OSError as error:
            raise ContentError("source-unreadable", "a proposed public source path is unavailable") from error
        candidates = [target] if stat.S_ISREG(info.st_mode) else sorted(target.rglob("*")) if stat.S_ISDIR(info.st_mode) else []
        if not candidates and not stat.S_ISDIR(info.st_mode):
            raise ContentError("input-type", "public source tree contains a link or special file")
        for path in candidates:
            try:
                mode = path.lstat().st_mode
            except OSError as error:
                raise ContentError("source-unreadable", "a proposed public source file is unavailable") from error
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode) or path.lstat().st_nlink != 1:
                raise ContentError("input-type", "public source tree contains a link or special file")
            rel = path.relative_to(root).as_posix()
            data = _read_regular(path, reason_prefix="source")
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise ContentError("input-total-limit", "public source exceeds the total byte limit")
            result = scan_bytes(data, rel)
            rows.append({"path": rel, **result})
    return {"files": len(rows), "bytes": total, "findings": _findings(rows),
            "dispositions": [item for row in rows for item in row.get("dispositions", [])],
            "inventory_sha256": sha256_bytes(canonical_bytes([{k: row[k] for k in ("path", "sha256", "bytes")} for row in rows]))}


def _findings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((finding for row in rows for finding in row["findings"]),
                  key=lambda item: (item["location"], item["rules"]))


def _is_rights_candidate(path: str) -> bool:
    relative = PurePosixPath(path)
    if path.startswith("third_party/") or path.startswith("fixtures/"):
        return True
    return path.startswith("tests/") and (
        path not in TEST_SOURCE_PATHS or "fixture" in relative.name.lower()
    )


def load_rights_inventory(root: Path = ROOT) -> dict[str, Any]:
    """Read the canonical JSON object embedded in the published inventory page."""
    page = root / "docs/rights-inventory.md"
    try:
        text = page.read_text(encoding="utf-8")
    except OSError as error:
        raise ContentError("rights-unreadable", "rights inventory document could not be read") from error
    blocks = re.findall(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if len(blocks) != 1:
        raise ContentError("rights-schema", "rights inventory must contain one JSON record")
    try:
        inventory = json.loads(blocks[0])
    except json.JSONDecodeError as error:
        raise ContentError("rights-schema", "rights inventory JSON is malformed") from error
    return inventory


def validate_repository_inventory(root: Path = ROOT) -> dict[str, Any]:
    """Bind every fixture/dependency candidate in the source tree to its record."""
    paths = _git_source_paths(root)
    inventory = load_rights_inventory(root)
    actual: dict[str, bytes] = {}
    for relative in paths:
        if _is_rights_candidate(relative):
            actual[relative] = _read_regular(root / relative, reason_prefix="source")
    result = validate_inventory(inventory, actual)
    shipped = set(paths)
    for item in inventory["items"]:
        if item["notice"] not in shipped:
            raise ContentError("rights-notice", "a required license notice is absent from public source")
    return result


def _validate_archive_inventory(rows: list[dict[str, Any]], root: Path = ROOT) -> dict[str, Any] | None:
    normalized: dict[str, dict[str, Any]] = {}
    all_paths: set[str] = set()
    for row in rows:
        path = row["path"]
        if not isinstance(path, str):
            raise ContentError("archive-path", "release archive contains an unsafe member path")
        if path.startswith("glueyneo-source/"):
            path = path[len("glueyneo-source/"):]
        all_paths.add(path)
        if _is_rights_candidate(path):
            if path in normalized:
                raise ContentError("archive-duplicate", "release archive contains duplicate member names")
            normalized[path] = row
    if not normalized:
        return None
    inventory = load_rights_inventory(root)
    declared = _validated_inventory_items(inventory, set(normalized))
    for path, row in normalized.items():
        item = declared[path]
        if item.get("rights") != "affirmative":
            raise ContentError("rights-unknown", "release archive item lacks affirmative redistribution evidence")
        if row.get("sha256") != item.get("sha256"):
            raise ContentError("rights-digest", "release archive item differs from its recorded digest")
        if item.get("notice") not in all_paths:
            raise ContentError("rights-notice", "release archive omits a required license notice")
    return {"passed": True, "items": len(normalized),
            "inventory_sha256": sha256_bytes(canonical_bytes(inventory))}


def scan_archive(path: Path) -> dict[str, Any]:
    """Inspect every member without extraction, before reading member bodies."""
    try:
        info = path.lstat()
    except OSError as error:
        raise ContentError("archive-unreadable", "release archive could not be read") from error
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ContentError("input-type", "release archive must be a regular, unlinked file")
    if info.st_size > MAX_TOTAL_BYTES:
        raise ContentError("archive-limit", "compressed archive exceeds the byte limit")
    rows: list[dict[str, Any]] = []
    total = 0
    try:
        with tarfile.open(path, "r:*") as archive:
            members = archive.getmembers()
            if not members or len(members) > MAX_MEMBERS:
                raise ContentError("archive-count", "release archive member count is empty or exceeds the limit")
            names: set[str] = set()
            for member in members:
                name = member.name
                pure = PurePosixPath(name)
                if (not name or "\\" in name or "\x00" in name or pure.is_absolute()
                        or re.match(r"^[A-Za-z]:", name) or any(part in {"", ".", ".."} for part in name.split("/"))):
                    raise ContentError("archive-path", "release archive contains an unsafe member path")
                if name in names:
                    raise ContentError("archive-duplicate", "release archive contains duplicate member names")
                names.add(name)
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ContentError("archive-link", "release archive contains a link or special member")
                if member.size < 0 or member.size > MAX_FILE_BYTES:
                    raise ContentError("archive-file-limit", "release archive member exceeds the per-file byte limit")
                total += member.size
                if total > MAX_TOTAL_BYTES:
                    raise ContentError("archive-total-limit", "release archive exceeds the total uncompressed byte limit")
            for member in members:
                if not member.isfile():
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    raise ContentError("archive-unreadable", "release archive member body is unavailable")
                with stream:
                    data = stream.read(member.size + 1)
                if len(data) != member.size:
                    raise ContentError("archive-unreadable", "release archive member body is truncated or oversized")
                rows.append({"path": member.name, **scan_bytes(data, member.name)})
    except ContentError:
        raise
    except (OSError, tarfile.TarError, EOFError) as error:
        raise ContentError("archive-unreadable", "release archive is malformed or unreadable") from error
    rights = _validate_archive_inventory(rows)
    return {"files": len(rows), "members": len(members), "bytes": total, "findings": _findings(rows),
            "dispositions": [item for row in rows for item in row.get("dispositions", [])],
            "rights": rights,
            "inventory_sha256": sha256_bytes(canonical_bytes([{k: row[k] for k in ("path", "sha256", "bytes")} for row in rows]))}


def _validated_inventory_items(inventory: Any, actual_paths: set[str]) -> dict[str, dict[str, Any]]:
    """Validate inventory structure before building maps or comparing source paths."""
    if (not isinstance(inventory, dict) or type(inventory.get("schema")) is not int
            or inventory["schema"] != 1 or not isinstance(inventory.get("items"), list)):
        raise ContentError("rights-schema", "rights inventory schema is invalid")
    declared: dict[str, dict[str, Any]] = {}
    for item in inventory["items"]:
        if not isinstance(item, dict):
            raise ContentError("rights-schema", "rights inventory item is malformed")
        path = item.get("path")
        if (not isinstance(path, str) or not path or path.startswith("-") or "\\" in path or
                "\x00" in path or path in declared or PurePosixPath(path).is_absolute() or
                any(part in {"", ".", ".."} for part in path.split("/"))):
            raise ContentError("rights-path", "rights inventory contains an unsafe or duplicate path")
        declared[path] = item
        if item.get("rights") != "affirmative":
            raise ContentError("rights-unknown", "shipped item lacks affirmative redistribution evidence")
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in
                   ("kind", "license", "provenance", "source_revision", "notice")):
            raise ContentError("rights-record", "shipped item is missing its license, provenance, or notice")
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", item["source_revision"]) is None:
            raise ContentError("rights-record", "source revision must be an immutable Git object ID")
        if not isinstance(item.get("sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None:
            raise ContentError("rights-record", "shipped item digest is malformed")
    if set(declared) != actual_paths:
        raise ContentError("rights-path-set", "shipped content differs from the exact rights inventory")
    return declared


def validate_inventory(inventory: Any, actual: dict[str, bytes]) -> dict[str, Any]:
    """Require exact path/digest coverage and affirmative item-level rights."""
    declared = _validated_inventory_items(inventory, set(actual))
    for path, data in actual.items():
        if sha256_bytes(data) != declared[path]["sha256"]:
            raise ContentError("rights-digest", "shipped item bytes differ from the rights inventory")
    return {"passed": True, "items": len(declared),
            "inventory_sha256": sha256_bytes(canonical_bytes(inventory))}


def _git_history(root: Path, revision: str = "--all") -> tuple[bytes, list[dict[str, Any]], int, int]:
    """Scan reachable commit metadata and every unique reachable blob body."""
    try:
        result = subprocess.run(["git", "log", revision, "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%s%x00%b"],
                                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContentError("history-unreadable", "publishable commit metadata could not be inspected") from error
    if result.returncode or not result.stdout:
        raise ContentError("history-unreadable", "publishable history is empty or unavailable")
    if len(result.stdout) > MAX_TOTAL_BYTES:
        raise ContentError("history-limit", "publishable history metadata exceeds the byte limit")
    metadata = result.stdout
    try:
        listing = subprocess.run(["git", "rev-list", "--objects", revision], cwd=root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContentError("history-unreadable", "publishable blob list could not be inspected") from error
    if listing.returncode:
        raise ContentError("history-unreadable", "publishable blob list could not be inspected")
    if len(listing.stdout) > MAX_TOTAL_BYTES:
        raise ContentError("history-limit", "publishable history object list exceeds the byte limit")
    object_paths: dict[str, str] = {}
    for line in listing.stdout.splitlines():
        parts = line.split(b" ", 1)
        object_id = parts[0]
        if re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", object_id):
            oid = object_id.decode("ascii")
            path = parts[1].decode("utf-8", errors="replace") if len(parts) == 2 else ""
            object_paths.setdefault(oid, path)
            if len(object_paths) > MAX_HISTORY_OBJECTS:
                raise ContentError("history-object-limit", "reachable history exceeds the object count limit")
    if not object_paths:
        raise ContentError("history-unreadable", "publishable history contains no reachable objects")
    input_data = ("\n".join(sorted(object_paths)) + "\n").encode("ascii")
    try:
        checked = subprocess.run(["git", "cat-file", "--batch-check"], cwd=root, input=input_data,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContentError("history-unreadable", "reachable history objects could not be inspected") from error
    if checked.returncode:
        raise ContentError("history-unreadable", "reachable history objects could not be inspected")
    blobs: list[tuple[str, int]] = []
    blob_bytes = 0
    for line in checked.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3 or fields[1] == b"missing":
            raise ContentError("history-unreadable", "reachable history object metadata is incomplete")
        if fields[1] != b"blob":
            continue
        try:
            size = int(fields[2])
        except ValueError as error:
            raise ContentError("history-unreadable", "reachable blob size is malformed") from error
        if size < 0 or size > MAX_FILE_BYTES:
            raise ContentError("history-file-limit", "reachable history blob exceeds the per-file byte limit")
        blob_bytes += size
        if blob_bytes > MAX_TOTAL_BYTES:
            raise ContentError("history-total-limit", "reachable history blobs exceed the total byte limit")
        blobs.append((fields[0].decode("ascii"), size))
    if len(blobs) > MAX_HISTORY_OBJECTS:
        raise ContentError("history-object-limit", "reachable history exceeds the object count limit")
    if len(metadata) + blob_bytes > MAX_TOTAL_BYTES:
        raise ContentError("history-total-limit", "reachable history metadata and blobs exceed the total byte limit")
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
        assert process.stdin is not None and process.stdout is not None
        dispositions: list[dict[str, Any]] = []
        for object_id, size in blobs:
            process.stdin.write(object_id.encode("ascii") + b"\n")
            process.stdin.flush()
            header = process.stdout.readline(256)
            fields = header.rstrip(b"\n").split()
            if len(fields) != 3 or fields[0].decode("ascii", errors="ignore") != object_id or fields[1] != b"blob":
                raise ContentError("history-unreadable", "reachable history blob stream is malformed")
            body = process.stdout.read(size)
            if len(body) != size or process.stdout.read(1) != b"\n":
                raise ContentError("history-unreadable", "reachable history blob stream is truncated")
            path = object_paths.get(object_id, "")
            result = scan_bytes(body, f"history/{path}" if path else "history/reachable-blob")
            disposition = HISTORY_FINDING_DISPOSITIONS.get(object_id)
            if disposition is not None:
                actual_rules = set(result["findings"][0]["rules"] if result["findings"] else ())
                accepted_paths = {disposition["path"]}
                original = ".planning/workstreams/first-playable-game/"
                archived = ".planning/milestones/ws-first-playable-game-2026-10-24/"
                if disposition["path"].startswith(original):
                    accepted_paths.add(archived + disposition["path"][len(original):])
                if path not in accepted_paths or actual_rules != disposition["rules"]:
                    raise ContentError("history-disposition", "a provenance-bound history disposition no longer matches its object")
                dispositions.append({"object": object_id, "location": _safe_location(f"history/{path}"),
                                     "rules": sorted(disposition["rules"]), "reason": disposition["reason"]})
            elif result["findings"]:
                dispositions.extend({"object": object_id, **finding} for finding in result["findings"])
        process.stdin.close()
        if process.wait(timeout=120):
            raise ContentError("history-unreadable", "reachable history blob stream failed")
        process.stdout.close()
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContentError("history-unreadable", "reachable history blobs could not be read") from error
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            if process.stdout is not None and not process.stdout.closed:
                process.stdout.close()
    return metadata, dispositions, blob_bytes, len(blobs)


def _git_source_paths(root: Path) -> list[str]:
    try:
        result = subprocess.run(["git", "ls-files", "-z", "--", *REPOSITORY_PATHS], cwd=root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContentError("source-unreadable", "the proposed source archive file list is unavailable") from error
    if result.returncode:
        raise ContentError("source-unreadable", "the proposed source archive file list is unavailable")
    paths = [raw.decode("utf-8") for raw in result.stdout.split(b"\0") if raw]
    if not paths:
        raise ContentError("source-unreadable", "the proposed public source file list is empty")
    return sorted(paths)


def _scan_blob(data: bytes, location: str) -> dict[str, Any]:
    total = len(data)
    if total > MAX_TOTAL_BYTES:
        raise ContentError("input-total-limit", "input class exceeds the total byte limit")
    rows = []
    for offset in range(0, total, MAX_FILE_BYTES):
        rows.append(scan_bytes(data[offset:offset + MAX_FILE_BYTES], location))
    if not rows:
        rows.append(scan_bytes(b"", location))
    findings = _findings(rows)
    return {"files": 1, "bytes": total, "findings": findings}


def scan_inputs(*, root: Path = ROOT, paths: list[str] | None = None,
                logs: list[Path] | None = None, archives: list[Path] | None = None,
                history_text: str | None = None, history_revision: str = "--all") -> dict[str, Any]:
    """Scan source, history, captured logs and each supplied release archive."""
    root = root.resolve()
    selected = paths if paths is not None else _git_source_paths(root)
    source = scan_tree(root, selected)
    rights = validate_repository_inventory(root) if paths is None else None
    if history_text is not None:
        history_data = history_text.encode()
        history = _scan_blob(history_data, "history/commit-metadata")
        history_dispositions = []
    else:
        history_data, history_dispositions, history_blob_bytes, history_blob_count = _git_history(root, history_revision)
        history = _scan_blob(history_data, "history/commit-metadata")
        history["bytes"] += history_blob_bytes
        history["files"] += history_blob_count
    log_rows = []
    log_bytes = 0
    for index, log in enumerate(logs or []):
        data = _read_regular(log, reason_prefix="log")
        log_bytes += len(data)
        if log_bytes > MAX_TOTAL_BYTES:
            raise ContentError("log-total-limit", "captured CI logs exceed the total byte limit")
        result = scan_bytes(data, f"ci-log-{index + 1}")
        log_rows.append({"bytes": result["bytes"], "findings": result["findings"]})
    archive_rows = []
    archive_bytes = 0
    for index, archive in enumerate(archives or []):
        result = scan_archive(archive)
        archive_bytes += result["bytes"]
        archive_rows.append({"files": result["files"], "members": result["members"], "bytes": result["bytes"], "findings": result["findings"], "dispositions": result["dispositions"]})
    counts = {
        "source": {"files": source["files"], "bytes": source["bytes"]},
        "history": {"files": history["files"], "bytes": history["bytes"]},
        "logs": {"files": len(log_rows), "bytes": log_bytes},
        "archives": {"files": sum(item["files"] for item in archive_rows), "bytes": archive_bytes},
    }
    unresolved_history = [row for row in history_dispositions if "reason" not in row]
    finding_dispositions = [row for row in history_dispositions if "reason" in row]
    findings = source["findings"] + history["findings"] + unresolved_history + [f for row in log_rows + archive_rows for f in row["findings"]]
    findings.sort(key=lambda item: (item["location"], item["rules"]))
    return {"schema": 1, "outcome": "fail" if findings else "pass", "findings": findings,
            "rights": rights, "history_dispositions": finding_dispositions,
            "source_dispositions": source["dispositions"],
            "archive_dispositions": [item for row in archive_rows for item in row["dispositions"]],
            "counts": counts, "detector_negative_only": True,
            "coverage": {"logs_supplied": len(log_rows), "archives_supplied": len(archive_rows),
                         "history_mode": ("synthetic supplied input" if history_text is not None
                                          else "all reachable refs" if history_revision == "--all"
                                          else "selected revision"),
                         "history_revision": history_revision if history_text is None else None,
                         "history_scope": "objects available in this checkout" if history_text is None else None},
            "limits": {"file_bytes": MAX_FILE_BYTES, "total_bytes": MAX_TOTAL_BYTES,
                       "archive_members": MAX_MEMBERS, "source_files": MAX_SOURCE_FILES,
                       "history_objects": MAX_HISTORY_OBJECTS}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--log", type=Path, action="append", default=[])
    parser.add_argument("--archive", type=Path, action="append", default=[])
    parser.add_argument("--history-revision", default="--all")
    parser.add_argument("--json", type=Path, help="write canonical redacted JSON report here")
    args = parser.parse_args(argv)
    try:
        report = scan_inputs(root=args.root, logs=args.log, archives=args.archive,
                             history_revision=args.history_revision)
    except ContentError as error:
        report = {"schema": 1, "outcome": "fail", "reason": error.reason,
                  "message": str(error), "detector_negative_only": True}
        output = canonical_bytes(report)
        if args.json:
            args.json.write_bytes(output)
        else:
            sys.stdout.buffer.write(output)
        return 2
    output = canonical_bytes(report)
    if args.json:
        args.json.write_bytes(output)
    else:
        sys.stdout.buffer.write(output)
    return 0 if report["outcome"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
