#!/usr/bin/env python3
"""Run the named, fail-closed local verification suites for the Glueyneo SDK."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/sdk-debug"
TREE = BUILD / "verify-sdk"
LOG_DIR = BUILD / "verify-sdk/logs"
sys.path.insert(0, str(ROOT / "tools"))
import sdk_evidence as evidence  # noqa: E402
import public_content  # noqa: E402

MAX_WORKERS = 2
CHILD_TIMEOUT_SECONDS = 600
FILTERED_ENVIRONMENT = {
    "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "CMAKE_PREFIX_PATH",
    "CMAKE_MODULE_PATH", "CMAKE_TOOLCHAIN_FILE", "CMAKE_PROJECT_INCLUDE",
    "CMAKE_PROJECT_INCLUDE_BEFORE", "CMAKE_GENERATOR",
}

SUITE_LABELS = {
    "contract": "sdk-contract",
    "diagnostic": "sdk-diagnostic",
    "run": "sdk-run",
    "controls": "sdk-controls",
    "isolation": "sdk-isolation",
    "hostile": "sdk-hostile",
    "provenance": "sdk-provenance",
    "capabilities": "sdk-capabilities",
    "package-build": "sdk-package-build",
    "package-consumers": "sdk-package-consumers",
    "package-docs": "sdk-package-docs",
    "package-capabilities": "sdk-package-capabilities",
    "mvs": "mvs",
    "state": "sdk-state",
    "save": "sdk-save",
    "examples": "sdk-example-continuation|sdk-example-persistence",
}

STATE_REQUIRED_CASES = {
    "sdk_state_tracer", "sdk_state_identity", "sdk_state_ym",
    "sdk_state_machine", "sdk_state_continuation", "sdk_state_controls",
    "sdk_state_isolation", "sdk_state_repeat", "sdk_state_hostile",
    "sdk_state_oom", "sdk_state_process", "sdk_state_registration",
}
STATE_OPTIONAL_CASES = {"sdk_state_exchange"}
SAVE_NATIVE_REQUIRED_CASES = {
    "sdk_save_api", "sdk_save_receipts", "sdk_save_lifecycle", "sdk_save_registration",
}
SAVE_DARWIN_REQUIRED_CASES = {
    "sdk_save_process", "sdk_save_host_faults", "sdk_save_recovery",
}
SAVE_SOURCE_PATHS = (
    "CMakeLists.txt", "CMakePresets.json", "include/glueyneo/glueyneo.h", "src/instance.c",
    "src/sdk_private.h", "tests/sdk/save_process.c", "tests/sdk/save_host.c",
    "tests/sdk/save_host.h", "tests/sdk/save_controls.py",
    "tests/sdk/save_fixture.c", "tests/sdk/save_fixture.h",
    "tests/sdk/test_save.c", "tests/sdk/test_save_lifecycle.c",
    "tests/sdk/test_support.h",
    "tests/fixture/public_save_guest.c", "tests/fixture/public_sound_guest.c",
    "tests/sdk/test_save_process.py",
    "tests/sdk/test_save_registration.py", "tests/fixture/ORACLE.md",
    "tools/verify_sdk.py",
)
FRONTEND_REQUIRED_CASES = frozenset({
    "libretro_callback", "libretro_audio_contract", "libretro_mvs_state_contract",
    "libretro_mvs_save_ram_contract", "libretro_mvs_state_rejection",
    "libretro_mvs_retention", "libretro_frontend_observer",
    "qualification_frontend_smoke", "libretro_frontend_registration",
})
FRONTEND_REQUIRED_COMMANDS = {
    "libretro_callback": ("libretro_callback_test", "public-playable.bin"),
    "libretro_audio_contract": ("libretro_callback_test", "--sound", "public-sound-mvs.bin"),
    "libretro_mvs_state_contract": ("libretro_callback_test", "--mvs-state", "public-save.gnmv"),
    "libretro_mvs_save_ram_contract": ("libretro_callback_test", "--mvs-save-ram", "public-save.gnmv"),
    "libretro_mvs_state_rejection": ("libretro_mvs_state_safety_test", "--state-rejection"),
    "libretro_mvs_retention": ("libretro_mvs_state_safety_test", "--retention"),
    "libretro_frontend_observer": (
        "frontend_observer_test.py", "--harness", "libretro_frontend_observer_test",
        "--production", "libretro_frontend_production_test", "--witness", "sdk_state_process",
        "--bundle", "public-sound-mvs.bin",
    ),
    "qualification_frontend_smoke": (
        "-m", "unittest", "discover", "-s", "tests/libretro", "-p", "test_retroarch_smoke.py",
    ),
    "libretro_frontend_registration": (
        "test_frontend_registration.py", "--build-dir", "build/owned-debug",
        "--mode", "registration",
    ),
}
FRONTEND_CTEST_REGEX = (
    r"^libretro_(callback|audio_contract|mvs_state_contract|mvs_save_ram_contract|"
    r"mvs_state_rejection|mvs_retention|frontend_observer|frontend_registration)$|"
    r"^qualification_frontend_smoke$"
)
FRONTEND_PHASE_SOURCE_FILES = (
    ".github/workflows/ci.yml", "CMakeLists.txt",
    "docs/first-playable-build.md", "docs/frontend-continuation.md",
    "docs/native-save.md", "docs/native-state.md", "docs/testing.md",
    "src/instance.c", "src/libretro/libretro_core.c", "src/sdk_private.h",
    "tests/libretro/callback_harness.c", "tests/libretro/frontend_observer_test.py",
    "tests/libretro/retroarch_smoke.py", "tests/libretro/test_frontend_registration.py",
    "tests/libretro/state_safety.c", "tests/libretro/test_frontend_replay.py",
    "tests/libretro/test_retroarch_smoke.py", "tests/sdk/state_process.c",
    "tools/mvs/frontend_replay.py", "tools/verify_sdk.py",
)
FRONTEND_DOC_PATHS = {
    "frontend": "docs/frontend-continuation.md",
    "first_playable": "docs/first-playable-build.md",
    "native_state": "docs/native-state.md",
    "native_save": "docs/native-save.md",
    "testing": "docs/testing.md",
}
RETROARCH_PINNED_SOURCE_REVISION = "69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576"
RETROARCH_PINNED_EXECUTABLE_SHA256 = "ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65"
FRONTEND_SOURCE_PATHS = (
    "CMakeLists.txt", "CMakePresets.json", ".github/workflows/ci.yml",
    "docs/first-playable-build.md", "docs/frontend-continuation.md",
    "docs/native-save.md", "docs/native-state.md", "docs/testing.md",
    "src/instance.c", "src/libretro/libretro_core.c", "src/sdk_private.h",
    "tests/consumers/check_package.py", "tests/consumers/test_exports.py",
    "tests/fixture/public_save_guest.c", "tests/fixture/public_sound_guest.c",
    "tests/libretro/callback_harness.c", "tests/libretro/frontend_observer_test.py",
    "tests/libretro/retroarch_smoke.py", "tests/libretro/state_safety.c",
    "tests/libretro/test_frontend_registration.py", "tests/libretro/test_frontend_replay.py",
    "tests/libretro/test_retroarch_smoke.py", "tests/sdk/state_process.c",
    "tools/mvs/frontend_replay.py", "tools/verify_sdk.py",
)
FRONTEND_CMAKE_PACKAGES = frozenset({"Python3", "Threads"})
FRONTEND_CMAKE_LINK_SURFACE = frozenset({
    '"$<$<LINK_LANGUAGE:C>:c++>"', '"$<$<LINK_LANGUAGE:C>:stdc++>"',
    "${CMAKE_DL_LIBS}", "${target}", "Glueyneo::glueyneo", "Threads::Threads",
    "glueyneo", "glueyneo-diagnostic", "glueyneo_libretro", "glueyneo_libretro_observed",
    "glueyneo_mvs_zlib", "glueyneo_runtime_static", "glueyneo_test", "glueyneo_unity",
    "glueyneo_ym2610_candidate", "libretro_callback_test", "libretro_frontend_observer_test",
    "libretro_frontend_production_test", "libretro_mvs_state_safety_test", "mvs_failure_driver",
    "mvs_import_fuzz", "mvs_import_lib", "mvs_importer", "mvs_observations_test",
    "mvs_qualify", "mvs_test", "public_guest_test", "public_sound_test", "sdk_diagnostic",
    "sdk_mutation", "sdk_save_lifecycle_test", "sdk_save_process", "sdk_save_test",
    "sdk_state_mutation", "sdk_state_process", "sdk_state_test", "sound_consumer_reference",
    "ym2610_admission_test", "z80_admission_test",
})
SANITIZER_EXPECTED_TESTS = {"asan-ubsan": 13, "tsan": 3}
EXAMPLE_CTEST_CASES = frozenset({
    "sdk_example_continuation_static", "sdk_example_continuation_shared",
    "sdk_example_persistence_static", "sdk_example_persistence_shared",
    "sdk_example_persistence_faults",
})

CTEST_CASES = {
    "contract": {"sdk_diagnostic", "sdk_lifecycle", "sdk_media", "sdk_faults", "sdk_run"},
    "diagnostic": {"sdk_diagnostic"},
    "run": {"sdk_run"},
    "controls": {"sdk_controls"},
    "isolation": {"sdk_isolation", "sdk_cold"},
    "hostile": {"sdk_mutation_media", "sdk_mutation_sequence", "sdk_mutation_minimizer"},
    "provenance": {"sdk_fixture_write", "sdk_provenance"},
    "capabilities": {"sdk_host_closure"},
    "mvs": {"mvs_synthetic_trace", "mvs_media_contract", "mvs_import_contract",
            "mvs_import_mutation", "mvs_callback_contract", "mvs_boot_checkpoint",
            "mvs_attract_predicate", "mvs_board_behavior",
            "mvs_board_io", "mvs_board_calendar", "mvs_board_sound",
            "mvs_board_cartridge", "mvs_board_video",
            "mvs_import_fuzz_corpus", "mvs_failure_diagnostics", "mvs_import_max_horizon",
            "mvs_input_observations", "public_sound_fixture", "sdk_sound_reference",
            "libretro_audio_contract", "mvs_audio_call_corpus"},
    "examples": set(EXAMPLE_CTEST_CASES),
}

PACKAGE_CASES = {
    "build": {"sdk_package_build_static", "sdk_package_build_shared"},
    "consumers": {"sdk_sound_reference", "sdk_package_consumers_static", "sdk_package_consumers_shared"},
    "docs": {"sdk_package_docs_static", "sdk_package_docs_shared", "sdk_package_docs_readme",
             "sdk_example_docs"},
    "capabilities": {"sdk_package_capabilities"},
}

EVIDENCE_CASES = {
    "legacy_identity": "sdk_evidence_legacy_identity",
    "stale_mvs_importer_source": "sdk_evidence_stale_mvs_importer_source",
    "mvs_diagnostic_source_closure": "sdk_evidence_mvs_diagnostic_source_closure",
    "missing_identity": "sdk_evidence_missing_identity",
    "malformed": "sdk_evidence_malformed",
    "duplicate_key": "sdk_evidence_duplicate_key",
    "zero_count": "sdk_evidence_zero_count",
    "stale_identity": "sdk_evidence_stale_identity",
    "mismatched_config": "sdk_evidence_mismatched_config",
    "duplicate_identity": "sdk_evidence_duplicate_identity",
    "duplicate_case": "sdk_evidence_duplicate_case",
    "noncanonical_order": "sdk_evidence_noncanonical_order",
    "noncanonical_json": "sdk_evidence_noncanonical_json",
    "privacy_contamination": "sdk_evidence_privacy_contamination",
    "erased_failure": "sdk_evidence_erased_failure",
    "spoofed_outcome": "sdk_evidence_spoofed_outcome",
    "mixed_artifacts": "sdk_evidence_mixed_artifacts",
    "row_shape_matrix_aggregator": "sdk_evidence_row_shape_matrix_aggregator",
    "row_shape_identity_source": "sdk_evidence_row_shape_identity_source",
    "row_shape_identity_unity": "sdk_evidence_row_shape_identity_unity",
    "row_shape_identity_artifact": "sdk_evidence_row_shape_identity_artifact",
    "row_shape_importer_source": "sdk_evidence_row_shape_importer_source",
    "row_shape_manifest_source": "sdk_evidence_row_shape_manifest_source",
    "row_shape_manifest_dependency": "sdk_evidence_row_shape_manifest_dependency",
    "row_shape_manifest_dependency_file": "sdk_evidence_row_shape_manifest_dependency_file",
    "row_shape_manifest_fixture": "sdk_evidence_row_shape_manifest_fixture",
    "manifest_source_size_precision": "sdk_evidence_manifest_source_size_precision",
    "canonical_preservation": "sdk_evidence_canonical_preservation",
    "manifest_erased_failure": "sdk_evidence_manifest_erased_failure",
    "empty_manifest": "sdk_evidence_empty_manifest",
    "empty_ancestry": "sdk_evidence_empty_ancestry",
    "stale_manifest_source": "sdk_evidence_stale_manifest_source",
    "unknown_outcome": "sdk_evidence_unknown_outcome",
}
EVIDENCE_CASE_IDS = {
    "legacy_identity": "evidence.legacy-identity-without-mvs-importer",
    "stale_mvs_importer_source": "evidence.stale-mvs-importer-source",
    "mvs_diagnostic_source_closure": "evidence.mvs-diagnostic-source-closure",
    "missing_identity": "evidence.missing-identity",
    "malformed": "evidence.malformed-truncated",
    "duplicate_key": "evidence.duplicate-key",
    "zero_count": "evidence.zero-cases",
    "stale_identity": "evidence.stale-source",
    "mismatched_config": "evidence.config-mismatch",
    "duplicate_identity": "evidence.duplicate-identity-row",
    "duplicate_case": "evidence.duplicate-case",
    "noncanonical_order": "evidence.noncanonical-case-order",
    "noncanonical_json": "evidence.noncanonical-json-order",
    "privacy_contamination": "evidence.private-path",
    "erased_failure": "evidence.erased-failure",
    "spoofed_outcome": "evidence.spoofed-pass",
    "mixed_artifacts": "evidence.mixed-foreign-artifact",
    "row_shape_matrix_aggregator": "evidence.row-shape-matrix-aggregator",
    "row_shape_identity_source": "evidence.row-shape-identity-source",
    "row_shape_identity_unity": "evidence.row-shape-identity-unity",
    "row_shape_identity_artifact": "evidence.row-shape-identity-artifact",
    "row_shape_importer_source": "evidence.row-shape-importer-source",
    "row_shape_manifest_source": "evidence.row-shape-manifest-source",
    "row_shape_manifest_dependency": "evidence.row-shape-manifest-dependency",
    "row_shape_manifest_dependency_file": "evidence.row-shape-manifest-dependency-file",
    "row_shape_manifest_fixture": "evidence.row-shape-manifest-fixture",
    "manifest_source_size_precision": "evidence.manifest-source-size-precision",
    "canonical_preservation": "evidence.canonical-preservation",
    "manifest_erased_failure": "evidence.manifest-erased-failure",
    "empty_manifest": "evidence.empty-manifest",
    "empty_ancestry": "evidence.empty-oracle-ancestry",
    "stale_manifest_source": "evidence.stale-manifest-source",
    "unknown_outcome": "evidence.unknown-outcome",
}
BASELINE_CASES = {
    "baseline_insufficient_samples": "sdk_baseline_insufficient_samples",
    "baseline_missing_raw_samples": "sdk_baseline_missing_raw_samples",
    "baseline_invalid_measurement": "sdk_baseline_invalid_measurement",
    "baseline_workload_mismatch": "sdk_baseline_workload_mismatch",
    "baseline_summary_mismatch": "sdk_baseline_summary_mismatch",
    "baseline_discarded_sample": "sdk_baseline_discarded_sample",
    "baseline_memory_unsupported": "sdk_baseline_memory_unsupported",
}
BASELINE_CASE_IDS = {
    "baseline_insufficient_samples": "baseline.insufficient-samples",
    "baseline_missing_raw_samples": "baseline.missing-raw-samples",
    "baseline_invalid_measurement": "baseline.invalid-measurement",
    "baseline_workload_mismatch": "baseline.workload-output-mismatch",
    "baseline_summary_mismatch": "baseline.fake-summary-precision",
    "baseline_discarded_sample": "baseline.unexplained-discard",
    "baseline_memory_unsupported": "baseline.unsupported-memory-remains-unsupported",
}


def validate_evidence_case_inventory(actual_keys: list[str],
                                     expected_cases: dict[str, str],
                                     expected_ids: dict[str, str]) -> None:
    """Fail closed if named SDK evidence controls are missing or duplicated."""
    if len(actual_keys) != len(set(actual_keys)):
        raise VerificationError("evidence control inventory contains duplicate case keys")
    case_keys = set(actual_keys)
    if case_keys != set(expected_cases) or set(expected_cases) != set(expected_ids):
        raise VerificationError("evidence control inventory differs from the exact expected keys")
    test_names = list(expected_cases.values())
    case_ids = list(expected_ids.values())
    if len(test_names) != len(set(test_names)):
        raise VerificationError("evidence control inventory contains duplicate CTest names")
    if len(case_ids) != len(set(case_ids)):
        raise VerificationError("evidence control inventory contains duplicate case IDs")
BASELINE_FAILURE_HISTORY = [{
    "attempt": 1,
    "outcome": "fail",
    "reason": "collector-configuration-error",
    "detail": "The first baseline command stopped before sampling because an empty CMAKE_C_FLAGS cache value was treated as missing; no timing or cold-build samples were collected. The collector was corrected to accept the empty value.",
    "resolution": "resolved before retained sample collection",
}, {
    "attempt": 2,
    "outcome": "fail",
    "reason": "measurement-helper-compile-error",
    "detail": "The helper defined GLUEYNEO_SDK_TEST_HOOKS in both its generated source and compiler arguments; the warning-as-error stopped collection before timing or cold-build samples.",
    "resolution": "removed the duplicate source definition; compiler argument remains the single definition",
}, {
    "attempt": 3,
    "outcome": "fail",
    "reason": "measurement-probe-validation-error",
    "detail": "The generated helper rejected its first warmup before raw samples or cold builds were emitted; this was a collector/workload-probe failure and not a measured SDK lane result.",
    "resolution": "the focused output exposed a zero-nanosecond single-call interval and confirmed unchanged allocator counters",
}, {
    "attempt": 4,
    "outcome": "fail",
    "reason": "timer-quantization",
    "detail": "The helper measured load as 14,000 ns while a single exact run interval was 0 ns; allocator counters stayed exactly 6 allocations / 7,010 bytes before and after.",
    "resolution": "changed execution timing to a batch of 32 independent preloaded instances, preserving batch totals and the integer average",
}, {
    "attempt": 5,
    "outcome": "fail",
    "reason": "timer-quantization",
    "detail": "The next focused run measured a zero-nanosecond single-load warmup; no timing or cold-build samples were retained.",
    "resolution": "changed load timing to 32 precreated independent instances, preserving the total batch interval and integer per-load average",
}]


class VerificationError(RuntimeError):
    pass


def clean_environment() -> dict[str, str]:
    env = dict(os.environ)
    for name in FILTERED_ENVIRONMENT:
        env.pop(name, None)
    return env


def run(argv: list[str], *, timeout: int = CHILD_TIMEOUT_SECONDS,
        cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(argv, cwd=cwd, env=clean_environment(), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        try:
            preserve_output(f"command-timeout-{Path(argv[0]).stem}", output)
        except OSError:
            pass
        raise VerificationError(f"command timed out after {timeout}s: {Path(argv[0]).name}\n{output[-6000:]}") from error
    except OSError as error:
        raise VerificationError(f"could not execute required command: {Path(argv[0]).name}") from error
    if check and result.returncode != 0:
        try:
            preserve_output(f"command-failed-{Path(argv[0]).stem}", result.stdout)
        except OSError:
            pass
        raise VerificationError(f"command failed ({result.returncode}): {' '.join(argv)}\n{result.stdout[-8000:]}")
    return result


def preserve_output(lane: str, output: str) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{lane}.log"
    path.write_text(output, encoding="utf-8")
    return evidence.sha256_file(path)


_DIAGNOSTIC_SECRET_PATTERNS = (
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.S), "[private-key-redacted]"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "[credential-redacted]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "[credential-redacted]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[credential-redacted]"),
    (re.compile(r"(?i)\b(?:token|password|secret|api[_-]?key)\s*[:=]\s*[^\s,;]+"), "[credential-redacted]"),
    (re.compile(r"(?i)\b[^\s/@:]+@(?:[^\s/:@]+\.)+[A-Za-z]{2,}\b"), "[identity-redacted]"),
    (re.compile(r"(?i)(?:[A-Z]:[\\/](?:Users|Documents and Settings)[\\/])[^\s\"']+"), "[private-path-redacted]"),
    (re.compile(r"/(?:Users|home|private/var|private/tmp|tmp|var/folders)/[^\s\"']+"), "[private-path-redacted]"),
)


def redacted_failure_diagnostic(output: str, *, limit: int = 8000) -> str:
    """Return bounded diagnostics only after path/identity/secret redaction and scan."""
    value = output[-limit:]
    for private_path in sorted({str(ROOT), str(Path.home())}, key=len, reverse=True):
        if private_path and private_path != "/":
            value = value.replace(private_path, "[private-path-redacted]")
    for pattern, replacement in _DIAGNOSTIC_SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    if len(value.encode("utf-8", errors="replace")) > limit:
        value = value.encode("utf-8", errors="replace")[-limit:].decode("utf-8", errors="replace")
    try:
        findings = public_content.scan_bytes(value.encode("utf-8", errors="replace"),
                                             "ci-failure-diagnostic")["findings"]
    except Exception:
        return "[diagnostic withheld: privacy detector did not complete]"
    if findings:
        return "[diagnostic withheld: privacy detector found sensitive content after redaction]"
    return value


def failure_receipt(suite: str, lane: str | None, error: BaseException) -> dict[str, Any]:
    detail = redacted_failure_diagnostic(str(error))
    revision = os.environ.get("SDK_SOURCE_REVISION") or os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        revision = ""
    return {"schema": "sdk-verify-failure/v1", "suite": suite,
            "stage": lane or suite, "outcome": "fail", "source_revision": revision or None,
            "detail": detail or "verification failed; no diagnostic output was captured"}


def ensure_debug_build() -> float:
    started = time.monotonic()
    run(["cmake", "--preset", "sdk-debug"], timeout=180)
    importer = BUILD / ("mvs_importer.exe" if os.name == "nt" else "mvs_importer")
    try:
        importer.unlink(missing_ok=True)
    except OSError as error:
        raise VerificationError("could not remove the existing MVS importer before SDK Debug build") from error
    run(["cmake", "--build", "--preset", "sdk-debug", "--parallel", str(MAX_WORKERS)], timeout=300)
    if not importer.is_file():
        raise VerificationError("sdk-debug build did not produce the MVS importer")
    runner = BUILD / ("glueyneo-diagnostic.exe" if os.name == "nt"
                      else "glueyneo-diagnostic")
    if not runner.is_file():
        raise VerificationError("sdk-debug build did not produce the diagnostic runner")
    fixture_b = BUILD / "diagnostic-original-b.bin"
    run([str(runner), "--write-fixture", str(fixture_b), "--scenario-b"], timeout=20)
    run([str(runner), "--check-fixture", str(fixture_b), "--scenario-b"], timeout=20)
    return round(time.monotonic() - started, 6)


def _bracket(value: str) -> str:
    # CTest's CMake-language bracket arguments keep spaces and shell syntax inert.
    fence = "="
    while "]" + fence + "]" in value:
        fence += "="
    return "[" + fence + "[" + value + "]" + fence + "]"


def ctest_denominator(output: str) -> int | None:
    modern = re.search(r"(?m)(\d+)% tests passed out of (\d+)", output)
    if modern:
        percent, total = map(int, modern.groups())
        return total if percent == 100 else None
    compatible = re.search(r"(?m)(\d+)% tests passed, (\d+) tests failed out of (\d+)", output)
    if compatible:
        percent, failed, total = map(int, compatible.groups())
        return total if percent == 100 and failed == 0 else None
    return None


def write_generated_ctest_tree(kind: str = "evidence") -> tuple[Path, list[str]]:
    directory = TREE / kind
    directory.mkdir(parents=True, exist_ok=True)
    tests_path = ROOT / "tests/sdk/test_evidence.py"
    catalogs = {
        "evidence": (EVIDENCE_CASES, "sdk-evidence"),
        "baseline": (BASELINE_CASES, "sdk-baseline-control"),
    }
    if kind not in catalogs:
        raise VerificationError(f"unknown generated CTest control suite: {kind}")
    cases, label = catalogs[kind]
    rows = list(cases.items())
    lines = ["# Generated by tools/verify_sdk.py; do not edit."]
    names = []
    for key, test_name in rows:
        name = test_name
        names.append(name)
        command = [sys.executable, str(tests_path), "--case", key]
        args = " ".join(_bracket(item) for item in command)
        lines.append(f"add_test({name} {args})")
        lines.append(f"set_tests_properties({name} PROPERTIES LABELS [=[{label};sdk-controls]=] TIMEOUT 30)")
    (directory / "CTestTestfile.cmake").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory, names


def run_generated_controls(kind: str) -> tuple[int, int, list[dict[str, Any]], str]:
    cases = EVIDENCE_CASES if kind == "evidence" else BASELINE_CASES
    expected_ids = EVIDENCE_CASE_IDS if kind == "evidence" else BASELINE_CASE_IDS
    label = "sdk-evidence" if kind == "evidence" else "sdk-baseline-control"
    if set(EVIDENCE_CASES) & set(BASELINE_CASES):
        raise VerificationError("evidence and baseline control inventories overlap")
    expected_all_cases = {**EVIDENCE_CASES, **BASELINE_CASES}
    expected_all_ids = {**EVIDENCE_CASE_IDS, **BASELINE_CASE_IDS}
    inventory_output = run([sys.executable, "tests/sdk/test_evidence.py", "--list"], timeout=30).stdout
    inventory_match = re.search(r"(?m)^SDK_EVIDENCE_INVENTORY (\[.*\])$", inventory_output)
    if inventory_match is None:
        raise VerificationError("evidence control inventory listing is missing")
    try:
        actual_keys = json.loads(inventory_match.group(1))
    except json.JSONDecodeError as error:
        raise VerificationError("evidence control inventory listing is malformed") from error
    if not isinstance(actual_keys, list) or not all(isinstance(key, str) for key in actual_keys):
        raise VerificationError("evidence control inventory listing must be a string array")
    validate_evidence_case_inventory(actual_keys, expected_all_cases, expected_all_ids)
    directory, expected_tests = write_generated_ctest_tree(kind)
    result = run(["ctest", "--test-dir", str(directory), "--verbose", "--output-on-failure",
                  "--no-tests=error", "--parallel", str(MAX_WORKERS), "-L", label], timeout=120)
    output = result.stdout
    test_names = re.findall(r"(?m)^\s*Start\s+\d+:\s*(\S+)\s*$", output)
    if len(test_names) != len(expected_tests) or set(test_names) != set(expected_tests):
        raise VerificationError(f"generated evidence CTest selection mismatch: expected {len(expected_tests)} named controls, observed {len(test_names)}")
    records = []
    for match in re.finditer(r"(?m)^(?:\d+: )?SDK_EVIDENCE_CASE (\{.*\})$", output):
        records.append(json.loads(match.group(1)))
    expected_case_ids = set(expected_ids.values())
    if len(records) != len(expected_tests) or {row.get("case_id") for row in records} != expected_case_ids:
        # Each individual control emits a stable case id; validate it instead of
        # treating a nonzero CTest summary as evidence.
        raise VerificationError("generated evidence controls omitted or duplicated named result records")
    if any(row.get("outcome") != "pass" or row.get("assertions", 0) < 1 for row in records):
        raise VerificationError("one or more named evidence rejection controls did not pass")
    denominator = ctest_denominator(output)
    if denominator != len(expected_tests):
        raise VerificationError("generated evidence CTest summary was missing or had a zero/mismatched denominator")
    assertions = sum(row["assertions"] for row in records)
    return len(records), assertions, sorted(records, key=lambda r: r["case_id"]), output


def run_generated_evidence_controls() -> tuple[int, int, list[dict[str, Any]], str]:
    return run_generated_controls("evidence")


def ctest_names(output: str) -> list[str]:
    return re.findall(r"(?m)^\s*Start\s+\d+:\s*(\S+)\s*$", output)


def validate_example_inventory(denominator: int | None, observed: list[str]) -> int:
    """Require every continuation/persistence CTest exactly once with a positive denominator."""
    expected = CTEST_CASES["examples"]
    if (not isinstance(denominator, int) or isinstance(denominator, bool) or denominator <= 0
            or len(observed) != denominator or len(set(observed)) != len(observed)
            or set(observed) != expected):
        raise VerificationError(
            f"example CTest inventory mismatch: expected {sorted(expected)}, "
            f"denominator {denominator}, observed {observed}"
        )
    return denominator


def validate_frontend_ctest_registration(document: Any) -> dict[str, Any]:
    """Require each source-backed frontend case exactly once with its intended command."""
    tests = document.get("tests") if isinstance(document, dict) else None
    if not isinstance(tests, list) or not tests:
        raise VerificationError("frontend CTest registration is empty or malformed")
    names: list[str] = []
    rows: dict[str, dict[str, Any]] = {}
    for row in tests:
        if not isinstance(row, dict):
            raise VerificationError("frontend CTest inventory contains a malformed test")
        name = row.get("name")
        if not isinstance(name, str) or not name.strip() or name in rows:
            raise VerificationError("frontend CTest names are empty or duplicated")
        names.append(name)
        rows[name] = row
    missing = FRONTEND_REQUIRED_CASES - set(names)
    if missing:
        raise VerificationError(f"frontend CTest inventory omitted required cases: {sorted(missing)}")
    for name, expected in FRONTEND_REQUIRED_COMMANDS.items():
        command = rows[name].get("command")
        if (not isinstance(command, list) or not command or
                any(not isinstance(token, str) or not token.strip() for token in command)):
            raise VerificationError(f"frontend CTest command is empty or malformed: {name}")
        normalized = set()
        for token in command:
            normalized.add(token)
            normalized.add(token.replace("\\", "/").rsplit("/", 1)[-1])
        if any(token not in normalized and
               token.replace("\\", "/").rsplit("/", 1)[-1] not in normalized
               for token in expected):
            raise VerificationError(f"frontend CTest command is not source-backed: {name}")
        if any(token in " ".join(command) for token in
               ("--private-contract", "--continuation-route", "GLUEYNEO_FRONTEND_WORK",
                "local/qualification/", "commercial")):
            raise VerificationError(f"private frontend inputs reached public CTest: {name}")
    return {"required_cases": sorted(FRONTEND_REQUIRED_CASES),
            "inventory_count": len(names), "unique_names": len(set(names))}


def validate_frontend_ctest_output(output: str) -> dict[str, Any]:
    """Reject empty, skipped, duplicate, failed, or widened frontend CTest selections."""
    total = ctest_denominator(output)
    if total is None:
        raise VerificationError("frontend CTest summary is missing or reports failures")
    names = ctest_names(output)
    start_rows = re.findall(r"(?m)^\s*Start\s+(\d+):\s*(\S+)\s*$", output)
    result_rows = re.findall(
        r"(?mi)^\s*(\d+)/(\d+)\s+Test\s+#(\d+):\s+(\S+)\s+.*?\b(Passed|Failed|Skipped|Timeout|Not Run)\b",
        output,
    )
    parsed_results = [(int(position), int(denominator), int(test_id), name, status)
                      for position, denominator, test_id, name, status in result_rows]
    expected_positions = [(position, total) for position in range(1, total + 1)]
    start_bindings = [(int(test_id), name) for test_id, name in start_rows]
    result_bindings = [(test_id, name) for _, _, test_id, name, _ in parsed_results]
    if (total != len(FRONTEND_REQUIRED_CASES) or len(names) != total or
            len(set(names)) != total or set(names) != FRONTEND_REQUIRED_CASES or
            len(start_rows) != total or len(set(start_bindings)) != total or
            {name for _, name in start_bindings} != FRONTEND_REQUIRED_CASES or
            len(parsed_results) != total or
            [(position, denominator) for position, denominator, _, _, _ in parsed_results] != expected_positions or
            len(set(result_bindings)) != total or set(result_bindings) != set(start_bindings) or
            {name for _, _, _, name, _ in parsed_results} != FRONTEND_REQUIRED_CASES or
            any(status != "Passed" for _, _, _, _, status in parsed_results)):
        raise VerificationError("frontend CTest selection was empty, skipped, failed, or mismatched")
    return {"cases": total, "named_tests": sorted(names),
            "statuses": {name: status for _, _, _, name, status in parsed_results}}


def validate_frontend_dependency_surface(cmake_source: str) -> int:
    """Pin the complete CMake package and target-link surface against new dependencies."""
    packages = set(re.findall(r"(?mi)^\s*find_package\(\s*([A-Za-z0-9_+.-]+)", cmake_source))
    links: set[str] = set()
    for block in re.findall(r"target_link_libraries\((.*?)\)", cmake_source, flags=re.S):
        links.update(token for token in re.split(r"\s+", block.strip())
                     if token and token not in {"PRIVATE", "PUBLIC", "INTERFACE"})
    if packages != FRONTEND_CMAKE_PACKAGES:
        raise VerificationError("frontend CMake package dependency surface changed")
    if links != FRONTEND_CMAKE_LINK_SURFACE:
        raise VerificationError("frontend CMake target/link dependency surface changed")
    if re.search(r"(?i)FetchContent|ExternalProject_Add|CPMAddPackage|add_subdirectory\s*\(\s*third_party", cmake_source):
        raise VerificationError("frontend CMake introduced an external package acquisition surface")
    return 3


def validate_frontend_source_contract(cmake_source: str, smoke_source: str,
                                      observer_source: str, exports_source: str) -> None:
    """Require named source-backed enforcement for continuation and public API claims."""
    verifier_source = (ROOT / "tools/verify_sdk.py").read_text(encoding="utf-8")
    cmake_anchor = re.search(
        r"add_test\(NAME libretro_frontend_registration(?P<body>.*?)(?=\n\s*add_test\(|\Z)",
        cmake_source, flags=re.S,
    )
    if (cmake_anchor is None or "test_frontend_registration.py" not in cmake_anchor.group("body") or
            "--mode" not in cmake_anchor.group("body") or "registration" not in cmake_anchor.group("body") or
            re.search(r"(?i)--private-contract|--continuation-route|GLUEYNEO_FRONTEND_WORK", cmake_anchor.group("body"))):
        raise VerificationError("frontend registration test is missing or carries private route inputs")
    required_smoke = (
        "def run_private_state(args:", "PRIVATE_STATE_IDENTITY_FIELDS", "validate_private_state_identity",
        "require_matching_frontend_mem(restored_mem, saved_mem)", "continuation_alignment(",
        "nonzero_audio_samples", "nonzero_video_bytes", "private_paths.scan_public_value",
        "failure_frames", "--private-contract", "args.timeout > 120",
        "validate_continuation_operation_matrix(",
    )
    required_observer = (
        'observations["restore"].get("state") == state', "mutated_state",
        "accepts-actual-frontend-mem-payload", 'native_video == frame["video"] and native_audio == frame["audio"]',
    )
    required_exports = (
        "test_rejects_private_test_symbols", "test_export_contract_rejects_extra_missing_and_private_names",
        "test_installed_save_consumer_references_each_exported_function",
    )
    for source, required, label in ((smoke_source, required_smoke, "private continuation"),
                                    (observer_source, required_observer, "observer negative controls"),
                                    (exports_source, required_exports, "public export checks")):
        missing = [token for token in required if token not in source]
        if missing:
            raise VerificationError(f"frontend {label} enforcement is missing: {missing}")
    if ("def suite_frontend()" not in verifier_source or
            'elif args.suite == "frontend"' not in verifier_source or
            '"--preset", "owned-debug"' not in verifier_source or
            "--show-only=json-v1" not in verifier_source or
            "validate_frontend_ctest_output" not in verifier_source):
        raise VerificationError("frontend suite omits its bounded build, membership, or focused CTest gates")
    return None


def validate_frontend_ci_contract(workflow_source: str) -> None:
    """Require the public frontend suite only in the existing Linux clang job."""
    occurrences = list(re.finditer(r"python3 tools/verify_sdk\.py --suite frontend", workflow_source))
    if len(occurrences) != 1:
        raise VerificationError("CI must invoke the frontend suite exactly once")
    start = workflow_source.rfind("- name:", 0, occurrences[0].start())
    end = workflow_source.find("\n      - ", occurrences[0].end())
    block = workflow_source[start:end if end >= 0 else None]
    required = ("if: matrix.lane == 'linux-clang'", "shell: bash", "python3 tools/verify_sdk.py --suite frontend")
    if any(token not in block for token in required):
        raise VerificationError("CI frontend suite is not attached to the existing Linux clang matrix lane")
    if any(token in block for token in
           ("GLUEYNEO_FRONTEND_WORK", "--private-contract", "--continuation-route", "local/qualification/")):
        raise VerificationError("private scene, media, or GUI inputs reached public CI")
    return None


def validate_frontend_documentation(documents: Any) -> int:
    """Keep the frontend, native state, durable save, and testing contracts distinct."""
    if not isinstance(documents, dict) or set(documents) != set(FRONTEND_DOC_PATHS):
        raise VerificationError("frontend documentation input set is incomplete or widened")
    if any(not isinstance(value, str) or not value.strip() for value in documents.values()):
        raise VerificationError("frontend documentation contains a missing or empty current contract")
    frontend = " ".join(documents["frontend"].split()).casefold()
    required_frontend = (
        "GN_PROFILE_DIAGNOSTIC", "MVS MSX only", "GNFX v1 public tracer",
        "not the MVS continuation route", "GNST", "RASTATE", "GNSV",
        "one complete uncompressed `MEM` block", "They have no `GNSV` header",
        "224,113 bytes", "fixed for that loaded image", "exact capacity",
        "normal `STOP` boundary", "do not run the guest", "poll input",
        "call video or", "audio callbacks", "perform file I/O", "read host time",
        "RETRO_MEMORY_SAVE_RAM", "direct pointer", "retained 65,536-byte backup-RAM allocation",
        "external frontend write", "no longer valid after unload",
        "`block_sram_overwrite=false`", "`block_sram_overwrite=true`",
        "Historical continuation", "hybrid", "out-of-memory limit", "does not abort state loading",
        "Undo Load State", "Undo Save State", "CMD_EVENT_RESUME", "does not use it",
        "startup SRAM import", "clean-exit writeback", "autosave_interval=1",
        "autosave_interval=0", "combined threaded-autosave and state-operation case is unsupported",
        "emitted core callbacks", "raw video callback pixels", "delivered core PCM",
        "emulated cycles", "sampled MVS input transitions", "display compositor",
        "audio device queue", "frontend replay position", "c045d4805a14983b5222e71d4ec6b560b7e4ee0e",
        RETROARCH_PINNED_EXECUTABLE_SHA256, RETROARCH_PINNED_SOURCE_REVISION,
        "--continuation-route private-state", "--timeout 120", "no background",
        "no lifetime observation counter", "no human UAT", "blocked/unknown",
        "screenshots are not acceptance evidence", "physical hardware truth",
    )
    missing = [token for token in required_frontend if token.casefold() not in frontend]
    if missing:
        raise VerificationError(f"frontend continuation document omitted required distinctions: {missing}")
    owner_docs = ("first_playable", "native_state", "native_save")
    if any("frontend-continuation.md" not in documents[name] for name in owner_docs):
        raise VerificationError("an owning first-playable/native contract omits the frontend contract link")
    testing = " ".join(documents["testing"].split()).casefold()
    if any(token not in testing for token in (
            "python3 tools/verify_sdk.py --suite frontend", "--continuation-route private-state",
            "--timeout 120", "no background watcher", "no lifetime observation counter")):
        raise VerificationError("testing guide omits the bounded public suite or local-only route")
    build_prerequisites = (
        "cmake --preset owned-debug",
        "-DGLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS=ON",
        "--target glueyneo_libretro_observed sdk_state_process",
    )
    for key in ("frontend", "testing"):
        if any(token not in documents[key] for token in build_prerequisites):
            raise VerificationError(f"{key} private route omits its opt-in observer/witness build")
    return len(required_frontend) + len(owner_docs) + 5 + 2 * len(build_prerequisites)


def _frontend_document_inputs(root: Path) -> dict[str, str]:
    documents = {}
    for key, relative in FRONTEND_DOC_PATHS.items():
        path = root / relative
        if not path.is_file():
            raise VerificationError(f"frontend documentation input is missing: {relative}")
        documents[key] = path.read_text(encoding="utf-8")
    return documents


def frontend_docs_checks(root: Path = ROOT) -> dict[str, int]:
    """Run positive and mislabel/omission controls for the current docs contract."""
    documents = _frontend_document_inputs(root)
    assertions = validate_frontend_documentation(documents)
    mutations = (
        ("GNST/RASTATE", "GNST", "NOT-STATE"),
        ("GNST/RASTATE", "RASTATE", "OTHER-CONTAINER"),
        ("SRAM/GNSV", "GNSV", "OTHER-SAVE-ENVELOPE"),
        ("historical policy", "block_sram_overwrite=false", "block_sram_overwrite=true"),
        ("undo distinction", "Undo Save State", "Undo Load State"),
        ("exact retained SRAM", "65,536-byte", "64-byte"),
        ("callback outputs", "emitted core callbacks", "displayed device output"),
    )
    for label, token, replacement in mutations:
        candidate = dict(documents)
        candidate["frontend"] = candidate["frontend"].replace(token, replacement)
        if token in {"GNST", "GNSV", "RASTATE", "Undo Save State", "65,536-byte"}:
            candidate["frontend"] = candidate["frontend"].replace(token, replacement)
        try:
            validate_frontend_documentation(candidate)
        except VerificationError:
            assertions += 1
        else:
            raise VerificationError(f"frontend documentation mutation passed unexpectedly: {label}")
    for key in ("first_playable", "native_state", "native_save"):
        candidate = dict(documents)
        candidate[key] = candidate[key].replace("frontend-continuation.md", "missing-contract.md")
        try:
            validate_frontend_documentation(candidate)
        except VerificationError:
            assertions += 1
        else:
            raise VerificationError(f"frontend owner-link omission passed unexpectedly: {key}")
    for key in ("frontend", "testing"):
        for token in ("cmake --preset owned-debug",
                      "-DGLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS=ON",
                      "--target glueyneo_libretro_observed sdk_state_process"):
            candidate = dict(documents)
            candidate[key] = candidate[key].replace(token, "omitted-build-prerequisite")
            try:
                validate_frontend_documentation(candidate)
            except VerificationError:
                assertions += 1
            else:
                raise VerificationError(f"frontend build prerequisite omission passed unexpectedly: {key}")
    return {"documents": len(documents), "mutation_controls": len(mutations) + 9,
            "assertions": assertions}


def _frontend_private_manifest_safe(section: dict[str, Any]) -> bool:
    encoded = json.dumps(section, sort_keys=True)
    if re.search(r"(?i)(?:/Users/|/private/|/home/|[A-Za-z]:\\\\|local/qualification/)", encoded):
        return False
    def has_digest_key(value: Any) -> bool:
        if isinstance(value, dict):
            return any(("sha256" in str(key).lower() or "media_hash" in str(key).lower() or
                        "scene_hash" in str(key).lower() or has_digest_key(item))
                       for key, item in value.items())
        if isinstance(value, list):
            return any(has_digest_key(item) for item in value)
        return False
    return not has_digest_key(section)


def validate_frontend_phase_provenance(manifest: Any, root: Path = ROOT) -> int:
    """Bind phase-owned sources and first-party rights without publishing private inputs."""
    if not isinstance(manifest, dict):
        raise VerificationError("fixture rights manifest is not an object")
    section = manifest.get("frontend_continuation")
    if not isinstance(section, dict):
        raise VerificationError("phase-specific frontend continuation provenance is missing")
    required = {
        "scope": "Phase 06 frontend continuation tooling and source contracts",
        "license": "MIT", "notice": "LICENSE",
    }
    if any(section.get(key) != value for key, value in required.items()):
        raise VerificationError("frontend phase scope or first-party notice changed")
    rights = section.get("rights")
    if (not isinstance(rights, dict) or rights.get("status") != "first-party-sources-only" or
            rights.get("license") != "MIT" or rights.get("notice") != "LICENSE" or
            rights.get("private_content_included") is not False or
            rights.get("commercial_media_included") is not False or
            rights.get("hashes_establish_redistribution_rights") is not False):
        raise VerificationError("frontend phase rights do not isolate original sources from private media")
    private_scene = section.get("selected_private_scene")
    if (not isinstance(private_scene, dict) or private_scene.get("status") != "local-only" or
            private_scene.get("content_bytes_committed") is not False or
            private_scene.get("state_captures_committed") is not False or
            private_scene.get("identity_hashes_published") is not False or
            private_scene.get("public_ci_inputs") is not False or
            not _frontend_private_manifest_safe(private_scene)):
        raise VerificationError("private scene bytes, paths, or content identities escaped local storage")
    pinned = section.get("pinned_frontend")
    if (not isinstance(pinned, dict) or pinned.get("product") != "RetroArch" or
            pinned.get("version") != "1.22.2" or
            pinned.get("source_revision") != RETROARCH_PINNED_SOURCE_REVISION or
            pinned.get("executable_sha256") != RETROARCH_PINNED_EXECUTABLE_SHA256):
        raise VerificationError("frontend provenance no longer identifies the measured RetroArch pin")

    source_rows = section.get("source_files")
    expected_paths = set(FRONTEND_PHASE_SOURCE_FILES)
    if (not isinstance(source_rows, list) or
            any(not isinstance(row, dict) for row in source_rows)):
        raise VerificationError("frontend source inventory is missing or malformed")
    names = [row.get("path") for row in source_rows]
    if len(names) != len(set(names)) or set(names) != expected_paths:
        raise VerificationError("frontend source inventory omitted, duplicated, or widened phase files")
    for row in source_rows:
        relative = row.get("path")
        if (not isinstance(relative, str) or Path(relative).is_absolute() or
                ".." in Path(relative).parts or "\\" in relative or
                row.get("license") != "MIT" or row.get("notice") != "LICENSE" or
                not isinstance(row.get("provenance"), str) or
                "Glueyneo" not in row["provenance"] or
                not isinstance(row.get("sha256"), str) or
                re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None or
                type(row.get("bytes")) is not int or row["bytes"] <= 0):
            raise VerificationError(f"frontend source provenance row is invalid: {relative}")
        path = root / relative
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root.resolve(strict=True))
            if path.is_symlink() or not path.is_file():
                raise OSError("source path is not a regular tracked file")
            size = path.stat().st_size
            digest = evidence.sha256_file(path)
        except (OSError, ValueError) as error:
            raise VerificationError(f"frontend source file is missing or outside the project: {relative}") from error
        if row["bytes"] != size or row["sha256"] != digest:
            raise VerificationError(f"frontend source fingerprint is stale: {relative}")

    ancestry = section.get("public_fixture_ancestry")
    save_fixture = manifest.get("mvs_save_fixture")
    sound_fixture = manifest.get("sound_fixture")
    if not isinstance(save_fixture, dict) or not isinstance(sound_fixture, dict):
        raise VerificationError("public native witness fixture ancestry is missing")
    generator = save_fixture.get("generator_source", {})
    origin = save_fixture.get("recipe_origin", {})
    sound_generator = sound_fixture.get("generator_source", {})
    if (not isinstance(ancestry, dict) or ancestry.get("save_fixture_manifest_path") != "mvs_save_fixture" or
            ancestry.get("save_guest_source_revision") != generator.get("source_revision") or
            ancestry.get("recipe_origin_revision") != origin.get("source_revision") or
            ancestry.get("sound_fixture_source_path") != sound_generator.get("path") or
            ancestry.get("sound_fixture_source_sha256") != sound_generator.get("sha256") or
            ancestry.get("hardware_truth_established") is not False):
        raise VerificationError("public fixture ancestry was changed, misattributed, or promoted to hardware truth")
    source_refs = ((generator.get("source_revision"), generator.get("path")),
                   (origin.get("source_revision"), origin.get("path")))
    if any(not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None or
               not isinstance(relative, str) or Path(relative).is_absolute() or
               ".." in Path(relative).parts for revision, relative in source_refs):
        raise VerificationError("frontend public fixture ancestry is not recorded as immutable Git refs")
    shallow = run(["git", "rev-parse", "--is-shallow-repository"], cwd=root, check=False)
    if shallow.returncode != 0 or shallow.stdout.strip() not in {"true", "false"}:
        raise VerificationError("frontend fixture ancestry checkout state could not be determined")
    if shallow.stdout.strip() == "false":
        for revision, relative in source_refs:
            if (run(["git", "cat-file", "-e", f"{revision}^{{commit}}"], cwd=root, check=False).returncode != 0 or
                    run(["git", "cat-file", "-e", f"{revision}:{relative}"], cwd=root, check=False).returncode != 0):
                raise VerificationError("frontend public fixture ancestry does not resolve to immutable source")
    history = section.get("historical_results")
    if (not isinstance(history, dict) or history.get("phase04_accepted_results") != "preserved" or
            history.get("phase05_original_regression") != {
                "label": "Phase 05 original 105/106 regression", "status": "preserved"} or
            history.get("phase05_targeted_manifest_repair") != {
                "label": "affected targeted manifest repair 2/2", "status": "preserved"} or
            history.get("relabelled_as_phase06") is not False):
        raise VerificationError("Phase 04/05 historical frontend results were merged or relabelled")
    if section.get("phase07_global_rights_inventory_closed") is not False:
        raise VerificationError("Phase 06 provenance may not close Phase 07 global rights inventory debt")
    return len(source_rows) + 12


def frontend_provenance_checks(root: Path = ROOT) -> dict[str, int]:
    """Run positive and source/private/history mutation controls on the phase manifest."""
    path = root / "tests/fixture/rights-manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError("fixture rights manifest could not be read as JSON") from error
    assertions = validate_frontend_phase_provenance(manifest, root)
    controls = []
    for required_path in FRONTEND_PHASE_SOURCE_FILES:
        missing_source = json.loads(json.dumps(manifest))
        missing_source["frontend_continuation"]["source_files"] = [
            row for row in missing_source["frontend_continuation"]["source_files"]
            if row.get("path") != required_path
        ]
        controls.append(missing_source)
    stale_source = json.loads(json.dumps(manifest))
    stale_source["frontend_continuation"]["source_files"][0]["sha256"] = "0" * 64
    controls.append(stale_source)
    private_bytes = json.loads(json.dumps(manifest))
    private_bytes["frontend_continuation"]["selected_private_scene"]["content_bytes_committed"] = True
    controls.append(private_bytes)
    private_hash = json.loads(json.dumps(manifest))
    private_hash["frontend_continuation"]["selected_private_scene"]["media_sha256"] = "a" * 64
    controls.append(private_hash)
    closed_global_debt = json.loads(json.dumps(manifest))
    closed_global_debt["frontend_continuation"]["phase07_global_rights_inventory_closed"] = True
    controls.append(closed_global_debt)
    bad_ancestry = json.loads(json.dumps(manifest))
    bad_ancestry["frontend_continuation"]["public_fixture_ancestry"]["recipe_origin_revision"] = "unknown"
    controls.append(bad_ancestry)
    mislabelled_history = json.loads(json.dumps(manifest))
    mislabelled_history["frontend_continuation"]["historical_results"]["phase05_original_regression"] = "passed"
    controls.append(mislabelled_history)
    for candidate in controls:
        try:
            validate_frontend_phase_provenance(candidate, root)
        except VerificationError:
            assertions += 1
        else:
            raise VerificationError("frontend provenance mutation passed unexpectedly")
    return {"source_files": len(FRONTEND_PHASE_SOURCE_FILES),
            "mutation_controls": len(controls), "assertions": assertions}


def frontend_source_identity(root: Path = ROOT) -> str:
    """Hash the frontend implementation, public harness, build wiring, and verifier sources."""
    missing = sorted(set(FRONTEND_PHASE_SOURCE_FILES) - set(FRONTEND_SOURCE_PATHS))
    if missing:
        raise VerificationError(
            "frontend source identity omitted phase source(s): " + ", ".join(missing))
    rows = []
    for relative in sorted(FRONTEND_SOURCE_PATHS):
        path = root / relative
        if not path.is_file():
            raise VerificationError(f"frontend source identity input is missing: {relative}")
        rows.append(relative.encode("utf-8") + b"\0" + evidence.sha256_file(path).encode("ascii") + b"\n")
    return evidence.sha256_bytes(b"".join(rows))


def require_frontend_evidence_identity_stable(source_before: str, source_after: str) -> None:
    if (not isinstance(source_before, str) or not isinstance(source_after, str) or
            re.fullmatch(r"[0-9a-f]{64}", source_before) is None or
            re.fullmatch(r"[0-9a-f]{64}", source_after) is None):
        raise VerificationError("frontend source identity is malformed")
    if source_before != source_after:
        raise VerificationError("frontend implementation or assertion sources changed during the suite")


def marker_records(output: str, marker: str) -> list[dict[str, Any]]:
    records = []
    for match in re.finditer(rf"(?m)^(?:\d+: )?{re.escape(marker)} (\{{.*\}})$", output):
        try:
            record = json.loads(match.group(1))
        except json.JSONDecodeError as error:
            raise VerificationError(f"{marker} emitted malformed JSON") from error
        if not isinstance(record, dict):
            raise VerificationError(f"{marker} emitted a non-object record")
        records.append(record)
    return records


INSTALLED_SANITIZER_CASES = {
    "ordinary_none_export", "installed_c_chip", "installed_cxx_chip",
    "removed_runtime_usage",
}
INSTALLED_SANITIZER_MODES = {"ADDRESS_UNDEFINED", "THREAD"}


def validate_installed_sanitizer_inventory(
        rows: list[dict[str, Any]], *, require_supported: bool = False) -> None:
    """Require exact installed consumer evidence for separate sanitizer builds."""
    if not isinstance(rows, list) or len(rows) != len(INSTALLED_SANITIZER_CASES) * len(
            INSTALLED_SANITIZER_MODES):
        raise VerificationError("installed sanitizer inventory is missing or duplicates required cases")
    grouped: dict[str, list[dict[str, Any]]] = {mode: [] for mode in INSTALLED_SANITIZER_MODES}
    for row in rows:
        if not isinstance(row, dict) or row.get("mode") not in grouped:
            raise VerificationError("installed sanitizer row has an unknown mode or malformed shape")
        grouped[row["mode"]].append(row)

    mode_ids: set[str] = set()
    prefix_ids: set[str] = set()
    for mode, mode_rows in grouped.items():
        case_ids = [row.get("case_id") for row in mode_rows]
        if len(mode_rows) != len(INSTALLED_SANITIZER_CASES) or set(case_ids) != INSTALLED_SANITIZER_CASES:
            raise VerificationError(f"installed sanitizer {mode} inventory is missing, duplicated, or extra")
        run_ids = {row.get("run_id") for row in mode_rows}
        prefixes = {row.get("prefix_id") for row in mode_rows}
        if len(run_ids) != 1 or len(prefixes) != 1:
            raise VerificationError(f"installed sanitizer {mode} rows do not share one isolated run prefix")
        run_id, prefix_id = next(iter(run_ids)), next(iter(prefixes))
        if (not isinstance(run_id, str) or not run_id or not isinstance(prefix_id, str) or
                not prefix_id.startswith(f"installed/{mode}/") or prefix_id.endswith("/") or
                Path(prefix_id).is_absolute()):
            raise VerificationError(f"installed sanitizer {mode} prefix identity is malformed")
        mode_ids.add(run_id)
        prefix_ids.add(prefix_id)
        compiler_identities = set()
        platform_identities = set()
        for row in mode_rows:
            case_id = row["case_id"]
            expected_tested_mode = "NONE" if case_id == "ordinary_none_export" else mode
            expected_linkage = "static_shared" if case_id == "ordinary_none_export" else "static"
            if (row.get("tested_mode") != expected_tested_mode or
                    row.get("linkage") != expected_linkage or
                    row.get("configuration") != "Debug"):
                raise VerificationError(f"installed sanitizer {mode}/{case_id} has the wrong mode or linkage")
            if case_id == "ordinary_none_export":
                prefixes = row.get("prefixes")
                if (not isinstance(prefixes, list) or len(prefixes) != 2 or
                        any(not isinstance(value, str) or Path(value).is_absolute()
                            for value in prefixes) or
                        not any(value.startswith("installed/NONE/static/") and value.endswith("/" + run_id)
                                for value in prefixes) or
                        not any(value.startswith("installed/NONE/shared/") and value.endswith("/" + run_id)
                                for value in prefixes) or
                        len(set(prefixes)) != 2):
                    raise VerificationError("ordinary NONE export evidence lacks distinct static/shared prefixes")
            compiler = row.get("compiler")
            platform_value = row.get("platform")
            required_compiler = ("c_id", "c_version", "c_path", "cxx_id", "cxx_version",
                                 "cxx_path", "linker", "sanitizer")
            if (not isinstance(compiler, dict) or any(
                    not isinstance(compiler.get(key), str) or not compiler[key]
                    for key in required_compiler) or
                    not isinstance(platform_value, dict) or any(
                    not isinstance(platform_value.get(key), str) or not platform_value[key]
                    for key in ("system", "release", "machine"))):
                raise VerificationError(f"installed sanitizer {mode}/{case_id} lacks toolchain identity")
            if compiler.get("sanitizer") != expected_tested_mode:
                raise VerificationError(f"installed sanitizer {mode}/{case_id} has a mismatched runtime identity")
            compiler_identities.add(tuple(
                compiler[key] for key in required_compiler if key != "sanitizer"))
            platform_identities.add(tuple(platform_value[key] for key in ("system", "release", "machine")))
            duration = row.get("duration_seconds")
            if (isinstance(duration, bool) or not isinstance(duration, (int, float)) or
                    duration < 0):
                raise VerificationError(f"installed sanitizer {mode}/{case_id} has an invalid duration")
            outcome = row.get("outcome")
            detail = row.get("detail")
            if outcome == "pass":
                if (not isinstance(row.get("cases"), int) or row["cases"] < 1 or
                        not isinstance(row.get("assertions"), int) or row["assertions"] < 1 or
                        duration <= 0 or
                        any(compiler.get(key) == "unknown" for key in required_compiler) or
                        not isinstance(detail, str) or not detail.strip()):
                    raise VerificationError(f"installed sanitizer {mode}/{case_id} lacks positive evidence")
            elif outcome == "unsupported":
                reason = row.get("unsupported_reason")
                if not isinstance(reason, str) or not reason.strip():
                    raise VerificationError(f"installed sanitizer {mode}/{case_id} omitted its unsupported reason")
                if require_supported:
                    raise VerificationError(
                        f"required installed sanitizer {mode}/{case_id} is unsupported: {reason}")
            elif outcome == "failed":
                if not isinstance(detail, str) or not detail.strip():
                    raise VerificationError(f"failed installed sanitizer {mode}/{case_id} omitted its failure")
                if require_supported:
                    raise VerificationError(
                        f"required installed sanitizer {mode}/{case_id} failed: {detail}")
            else:
                raise VerificationError(f"installed sanitizer {mode}/{case_id} has unknown outcome {outcome!r}")
        if len(compiler_identities) != 1 or len(platform_identities) != 1:
            raise VerificationError(f"installed sanitizer {mode} mixes compiler or platform identities")
    if len(mode_ids) != 2 or len(prefix_ids) != 2:
        raise VerificationError("ASan+UBSan and TSan did not use separate installed build prefixes")


def validate_state_ctest_output(output: str) -> dict[str, Any]:
    """Require the complete state CTest inventory and positive evidence per case."""
    total = ctest_denominator(output)
    observed = ctest_names(output)
    if total is None or total <= 0:
        raise VerificationError("state suite produced no positive all-passing CTest denominator")
    if len(observed) != total or len(set(observed)) != total:
        raise VerificationError("state suite CTest names are missing, duplicated, or inconsistent")
    observed_set = set(observed)
    expected = STATE_REQUIRED_CASES | (observed_set & STATE_OPTIONAL_CASES)
    if observed_set != expected:
        raise VerificationError(
            f"state suite named CTest inventory mismatch: expected {sorted(expected)}, observed {observed}")

    starts = list(re.finditer(r"(?m)^\s*Start\s+(\d+):\s*(\S+)\s*$", output))
    if len(starts) != total:
        raise VerificationError("state suite omitted a complete named CTest output block")
    per_case: dict[str, int] = {}
    for start in starts:
        test_id, name = start.groups()
        block = "\n".join(re.findall(
            rf"(?m)^\s*{re.escape(test_id)}:\s?(.*)$", output))
        records: list[dict[str, Any]] = []
        for marker in ("SDK_RESULT", "SDK_CONTROL_RESULT", "STATE_EXCHANGE_RESULT",
                       "STATE_HOSTILE_RESULT"):
            records.extend(marker_records(block, marker))
        assertions = re.findall(
            r"(?m)^(?:\d+:\s*)?# ASSERT .+ expected=(\S+) observed=(\S+)\s*$",
            block)
        if assertions and any(expected_value != observed_value
                              for expected_value, observed_value in assertions):
            raise VerificationError(f"{name} emitted a failed assertion in a passing CTest block")
        if records:
            if any(row.get("outcome") != "pass" or
                   not isinstance(row.get("cases", row.get("pair_cases")), int) or
                   row.get("cases", row.get("pair_cases")) <= 0 or
                   not isinstance(row.get("assertions"), int) or row["assertions"] <= 0
                   for row in records):
                raise VerificationError(f"{name} emitted a zero or non-passing assertion record")
            count = sum(row["assertions"] for row in records)
        elif assertions:
            count = len(assertions)
        elif name == "sdk_state_controls":
            controls = re.findall(
                r"(?m)^(?:\d+:\s*)?(?:cpu|memory|board|sound|ym2610): expected observation assertion failed$",
                block)
            if len(controls) != 5 or not re.search(
                    r"(?m)^(?:\d+:\s*)?unknown selector: rejected$", block):
                raise VerificationError("state omission controls omitted a named assertion")
            count = len(controls) + 1
        elif name == "sdk_state_registration":
            match = re.search(r"(?m)^\s*(?:\d+:\s*)?Ran (\d+) tests? in [\d.]+s$", block)
            if match is None or int(match.group(1)) <= 0 or not re.search(
                    r"(?m)^\s*(?:\d+:\s*)?OK\s*$", block):
                raise VerificationError("state registration test omitted positive unittest evidence")
            count = int(match.group(1))
        else:
            raise VerificationError(f"{name} emitted no positive assertion evidence")
        if count <= 0:
            raise VerificationError(f"{name} emitted zero assertions")
        per_case[name] = count
    if set(per_case) != expected or any(value <= 0 for value in per_case.values()):
        raise VerificationError("state suite per-case assertion inventory is incomplete")
    return {"cases": total, "assertions": sum(per_case.values()),
            "named_tests": sorted(observed_set), "per_case_assertions": per_case}


def _unittest_denominator(block: str, name: str) -> int:
    match = re.search(r"(?m)^\s*(?:\d+:\s*)?Ran (\d+) tests? in [\d.]+s$", block)
    if match is None or int(match.group(1)) <= 0 or not re.search(
            r"(?m)^\s*(?:\d+:\s*)?OK(?: \(skipped=0\))?\s*$", block):
        raise VerificationError(f"{name} omitted positive passing unittest evidence")
    if re.search(r"(?m)^\s*(?:\d+:\s*)?OK \(skipped=[1-9]\d*\)\s*$", block):
        raise VerificationError(f"{name} passed with skipped tests")
    return int(match.group(1))


def _python_assertion_count(block: str, name: str) -> int:
    """Require the Python harness to report executed assert-method calls."""
    records = marker_records(block, "SAVE_PYTHON_RESULT")
    if len(records) != 1:
        raise VerificationError(f"{name} omitted or duplicated SAVE_PYTHON_RESULT")
    row = records[0]
    tests = row.get("tests")
    assertions = row.get("assertions")
    if (not isinstance(tests, int) or isinstance(tests, bool) or tests <= 0 or
            tests != _unittest_denominator(block, name) or
            not isinstance(assertions, int) or isinstance(assertions, bool) or
            assertions <= 0):
        raise VerificationError(f"{name} emitted zero or inconsistent Python assertion evidence")
    return assertions


def validate_save_ctest_output(
    output: str, *, host_supported: bool,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Require the exact native save inventory and honest host protocol status."""
    total = ctest_denominator(output)
    observed = ctest_names(output)
    expected = SAVE_NATIVE_REQUIRED_CASES | SAVE_DARWIN_REQUIRED_CASES
    if total is None or total <= 0:
        raise VerificationError("save suite produced no positive CTest denominator")
    if len(observed) != total or len(set(observed)) != total or set(observed) != expected:
        raise VerificationError(
            f"save suite named CTest inventory mismatch: expected {sorted(expected)}, observed {observed}")

    starts = list(re.finditer(r"(?m)^\s*Start\s+(\d+):\s*(\S+)\s*$", output))
    if len(starts) != total:
        raise VerificationError("save suite omitted a complete named CTest output block")

    per_case: dict[str, int] = {}
    unsupported: list[str] = []
    for index, start in enumerate(starts):
        test_id, name = start.groups()
        block = "\n".join(re.findall(
            rf"(?m)^\s*{re.escape(test_id)}:\s?(.*)$", output))
        host_case = name in SAVE_DARWIN_REQUIRED_CASES
        summary = re.search(
            rf"(?m)^\s*\d+/\d+\s+Test #{re.escape(test_id)}:\s*{re.escape(name)}\b([^\n]*)$",
            output)
        skipped = bool(summary and re.search(r"(?i)(?:\*\*\*Skipped|Test not available|exit code 77)", summary.group(1)))
        if host_case and not host_supported:
            if not skipped:
                raise VerificationError(f"{name} did not report unsupported host protocol status")
            unsupported.append(name)
            per_case[name] = 0
            continue
        if host_case and skipped:
            raise VerificationError(f"{name} was skipped on a host that must qualify the protocol")

        if name in {"sdk_save_api", "sdk_save_lifecycle"}:
            records = marker_records(block, "SDK_RESULT")
            if len(records) != 1:
                raise VerificationError(f"{name} omitted or duplicated its SDK_RESULT assertion record")
            row = records[0]
            if (row.get("outcome") != "pass" or
                    not isinstance(row.get("cases"), int) or row["cases"] <= 0 or
                    not isinstance(row.get("assertions"), int) or row["assertions"] <= 0):
                raise VerificationError(f"{name} emitted a zero or non-passing SDK_RESULT")
            result_identity = row.get("identity", {})
            if identity is not None and (
                    result_identity.get("source_revision") != identity.get("source_revision", "")[:12] or
                    result_identity.get("configuration") != "Debug" or
                    result_identity.get("sanitizer") != "NONE"):
                raise VerificationError(f"{name} emitted a stale source/build SDK_RESULT")
            count = row["assertions"]
        elif name == "sdk_save_receipts":
            match = re.search(
                r"(?m)^(?:\d+:\s*)?save receipts passed: positive cases=(\d+) assertions=(\d+); negative control=([a-z0-9_.-]+)$",
                block)
            if match is None or int(match.group(1)) != 3 or int(match.group(2)) <= 0 or \
                    match.group(3) != "save.pending-newer":
                raise VerificationError("sdk_save_receipts omitted positive cases or stale-clean detection")
            count = int(match.group(2))
        elif name in {"sdk_save_registration", "sdk_save_process",
                      "sdk_save_host_faults", "sdk_save_recovery"}:
            count = _python_assertion_count(block, name)
        else:
            raise VerificationError(f"save suite contains an unrecognized test case: {name}")
        if count <= 0:
            raise VerificationError(f"{name} emitted zero assertions")
        per_case[name] = count

    if set(per_case) != expected:
        raise VerificationError("save suite per-case assertion inventory is incomplete")
    host_qualification = "qualified" if host_supported else "unsupported"
    if not host_supported and set(unsupported) != SAVE_DARWIN_REQUIRED_CASES:
        raise VerificationError("save suite omitted explicit unsupported host outcomes")
    return {"cases": total, "assertions": sum(per_case.values()),
            "named_tests": sorted(observed), "per_case_assertions": per_case,
            "host_qualification": host_qualification,
            "unsupported_host_cases": sorted(unsupported)}


def run_existing_ctest(label: str, lane: str) -> tuple[int, str]:
    result = run(["ctest", "--preset", "sdk-debug", "--verbose", "--output-on-failure",
                  "--no-tests=error", "--parallel", str(MAX_WORKERS), "-L", label], timeout=600)
    output = result.stdout
    total = ctest_denominator(output)
    if total is None:
        raise VerificationError(f"{lane} produced no CTest denominator")
    if total <= 0:
        raise VerificationError(f"{lane} CTest result was not all passing with a positive denominator")
    expected = CTEST_CASES.get(lane)
    observed = ctest_names(output)
    if lane == "examples":
        validate_example_inventory(total, observed)
    if expected is None or total != len(expected) or len(observed) != total or set(observed) != expected:
        raise VerificationError(
            f"{lane} named CTest inventory mismatch: expected {sorted(expected or ())}, observed {observed}")
    return total, output


def configured_mvs_importer_path(build_dir: Path) -> Path:
    """Read the importer path from the generated commands CTest will execute."""
    ctest_file = build_dir / "CTestTestfile.cmake"
    if not ctest_file.is_file():
        raise VerificationError("configured CTest inventory is missing for the MVS importer")
    importer_tests = {"mvs_import_contract", "mvs_import_mutation", "mvs_import_fuzz_corpus"}
    observed: dict[str, Path] = {}
    for line in ctest_file.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r'^add_test\("([^\"]+)"\s+(.*)\)$', line)
        if match is None or match.group(1) not in importer_tests:
            continue
        paths = re.findall(r'"--importer"\s+"([^\"]+)"', match.group(2))
        if len(paths) != 1:
            raise VerificationError("configured MVS importer test has no unique importer executable")
        observed[match.group(1)] = Path(paths[0]).resolve()
    if set(observed) != importer_tests or len(set(observed.values())) != 1:
        raise VerificationError("configured MVS importer tests do not share the complete exact artifact")
    return next(iter(observed.values()))


def current_mvs_importer_identity(identity: dict[str, Any]) -> dict[str, Any]:
    expected = identity.get("mvs_importer")
    if not isinstance(expected, dict):
        raise VerificationError("MVS identity is missing the importer artifact and source proof")
    configured = configured_mvs_importer_path(BUILD)
    expected_path = (BUILD / str(expected.get("basename", ""))).resolve()
    if configured != expected_path:
        raise VerificationError("configured MVS tests execute a different importer artifact")
    try:
        observed = evidence.mvs_importer_identity(
            ROOT, BUILD.relative_to(ROOT).as_posix())
    except (ValueError, evidence.EvidenceError) as error:
        raise VerificationError("could not verify the configured MVS importer identity") from error
    if observed != expected:
        raise VerificationError("MVS importer artifact or source closure differs from SDK identity")
    return observed


def verify_fixture_runner(runner: Path, key: str) -> None:
    spec = evidence.FIXTURES[key]
    path = ROOT / spec["file"]
    command = [str(runner), "--check-fixture", str(path)] + (["--scenario-b"] if key == "b" else [])
    result = run(command, timeout=20)
    record_match = re.search(r"(?m)^SDK_FIXTURE (\{.*\})$", result.stdout)
    if not record_match:
        raise VerificationError(f"fixture {key} runner returned no named machine result")
    record = json.loads(record_match.group(1))
    if record.get("outcome") != "pass" or record.get("bytes") != 522:
        raise VerificationError(f"fixture {key} runner did not verify the expected 522 bytes")


def validate_sdk_result_records(output: str, expected_suites: set[str], identity: dict[str, Any]) -> list[dict[str, Any]]:
    records = marker_records(output, "SDK_RESULT")
    if {row.get("suite") for row in records} != expected_suites or len(records) != len(expected_suites):
        raise VerificationError("SDK CTest output omitted or duplicated an expected named result suite")
    expected_compiler = identity["compiler"]
    compiler = f"{expected_compiler.get('id')} {expected_compiler.get('version')}"
    for row in records:
        record_identity = row.get("identity", {})
        if (row.get("outcome") != "pass" or row.get("cases", 0) < 1 or
                row.get("assertions", 0) < 1 or
                record_identity.get("source_revision") != identity.get("source_revision", "")[:12] or
                record_identity.get("configuration") != "Debug" or
                record_identity.get("compiler") != compiler or
                record_identity.get("sanitizer") != "NONE"):
            raise VerificationError(f"SDK result identity/count/outcome failed for {row.get('suite')}")
    return records


def collect_ctest_lane(name: str, identity: dict[str, Any]) -> tuple[dict[str, Any], str]:
    label = SUITE_LABELS[name]
    importer_before = current_mvs_importer_identity(identity) if name == "mvs" else None
    count, output = run_existing_ctest(label, name)
    importer_after = current_mvs_importer_identity(identity) if name == "mvs" else None
    if name == "mvs" and importer_after != importer_before:
        raise VerificationError("MVS importer changed during the configured CTest run")
    lane: dict[str, Any] = {
        "outcome": "pass", "label": label, "ctest_cases": count,
        "named_tests": sorted(CTEST_CASES[name]),
    }
    if name == "mvs":
        lane["output_sha256"] = preserve_output("ctest-mvs", output)
        lane["source_revision"] = identity.get("source_revision")
        lane["relevant_source_sha256"] = identity.get("relevant_source_sha256")
        lane["importer_basename"] = importer_before["basename"]
        lane["importer_sha256"] = importer_before["sha256"]
        lane["importer_source_sha256"] = importer_before["source_sha256"]
        validate_mvs_lane(lane, identity)
    elif name in {"contract", "diagnostic", "run"}:
        suites = {"contract": {"diagnostic", "lifecycle", "media", "faults", "run"},
                  "diagnostic": {"diagnostic"}, "run": {"run"}}[name]
        records = validate_sdk_result_records(output, suites, identity)
        lane["cases"] = sum(row["cases"] for row in records)
        lane["assertions"] = sum(row["assertions"] for row in records)
        lane["results"] = records
    elif name == "controls":
        plain = re.sub(r"(?m)^\s*\d+:\s?", "", output)
        normal = re.search(r"(?m)^PASS: normal-sdk-controls cases=(\d+) assertions=(\d+)$", plain)
        controls = re.findall(
            r"(?m)^PASS: control=([a-z-]+) assertion=([^ ]+) expected=([^ ]+) observed=([^ ]+) assertions=(\d+)$",
            plain)
        expected_controls = {"arithmetic", "initialized", "bss", "run-instructions",
                             "run-elapsed", "run-stop", "byte-order", "access-order"}
        if (normal is None or int(normal.group(1)) <= 0 or int(normal.group(2)) <= 0 or
                {row[0] for row in controls} != expected_controls or len(controls) != 8 or
                "PASS: independent_runner_processes=4 distinct_result_paths=4 scenarios=2" not in plain):
            raise VerificationError("controls lane omitted named counterfactual or fresh-process outcomes")
        lane["cases"] = int(normal.group(1))
        lane["assertions"] = int(normal.group(2))
        lane["negative_controls"] = [
            {"name": row[0], "assertion_id": row[1], "expected": row[2],
             "observed": row[3], "assertions": int(row[4])} for row in controls]
        lane["process_summary"] = "independent_runner_processes=4 distinct_result_paths=4 scenarios=2"
        lane["summaries"] = [line.strip() for line in plain.splitlines()
                              if line.lstrip().startswith("PASS:")]
    elif name == "isolation":
        records = marker_records(output, "SDK_CONTROL_RESULT")
        if (len(records) < 2 or any(row.get("outcome") != "pass" or row.get("assertions", 0) < 1 for row in records)):
            raise VerificationError("isolation did not emit passing named control assertions")
        if not all(token in output for token in
                   ("interleaved_pairs=16", "barrier_concurrent_pairs=16", "cold_processes=8")):
            raise VerificationError("isolation lane omitted interleaving, concurrent-pair, or process denominators")
        lane["cases"] = len(records)
        lane["assertions"] = sum(row["assertions"] for row in records)
        lane["results"] = records
        lane["summaries"] = [line.strip() for line in output.splitlines()
                              if line.lstrip().startswith("PASS:")]
    elif name == "hostile":
        records = []
        for line in output.splitlines():
            line = re.sub(r"^\s*\d+: ", "", line)
            match = re.match(r"SDK_MUTATION suite=(media|sequence)\s+(.*)$", line)
            if not match:
                continue
            row: dict[str, Any] = {"suite": match.group(1)}
            for field, value in re.findall(r"([a-zA-Z0-9_]+)=([^\s]+)", match.group(2)):
                try:
                    row[field] = int(value)
                except ValueError:
                    row[field] = value
            records.append(row)
        if {row.get("suite") for row in records} != {"media", "sequence"} or len(records) != 2:
            raise VerificationError("hostile lane omitted its media or sequence mutation result")
        for row in records:
            for field in ("iterations", "corpus_cases", "unique_inputs", "operations",
                          "guest_requested_cycles_total", "max_guest_requested_cycles_per_input"):
                if not isinstance(row.get(field), int) or row[field] <= 0:
                    raise VerificationError(f"hostile mutation result has no positive {field}")
        sdk_records = validate_sdk_result_records(
            output, {"sdk-mutation-media", "sdk-mutation-sequence"}, identity)
        if "minimizer" not in output.lower() or "sdk_mutation_minimizer" not in ctest_names(output):
            raise VerificationError("hostile lane omitted its named minimizer self-test")
        lane["cases"] = sum(row["cases"] for row in sdk_records)
        lane["assertions"] = sum(row["assertions"] for row in sdk_records)
        lane["mutation"] = records
        storage_records = []
        for line in output.splitlines():
            line = re.sub(r"^\s*\d+: ", "", line)
            match = re.match(r"SDK_MUTATION_STORAGE suite=sequence\s+(.*)$", line)
            if match:
                storage_records.append({field: int(value) for field, value in
                                        re.findall(r"([a-zA-Z0-9_]+)=(\d+)", match.group(1))})
        if len(storage_records) != 1 or any(value <= 0 for value in storage_records[0].values()):
            raise VerificationError("hostile sequence lane omitted peak storage and configured limit")
        lane["sequence_storage"] = storage_records[0]
        lane["results"] = sdk_records
    elif name == "provenance":
        records = marker_records(output, "SDK_FIXTURE")
        if not records or any(row.get("outcome") != "pass" or row.get("bytes") != 522 for row in records):
            raise VerificationError("provenance CTest omitted the expected fixture output identity")
        lane["cases"] = len(records)
        lane["assertions"] = len(records)
        lane["fixture_results"] = records
    elif name == "capabilities":
        if "SDK runtime host-call closure passed" not in output:
            raise VerificationError("capability CTest omitted the host-closure result")
        lane["cases"] = 1
        lane["assertions"] = 0
        lane["assertions_status"] = "not emitted by CTest producer; positive named CTest case recorded"
    lane["output_sha256"] = preserve_output(name, output)
    return lane, output


def validate_mvs_lane(lane: dict[str, Any], identity: dict[str, Any]) -> None:
    expected = sorted(CTEST_CASES["mvs"])
    importer = identity.get("mvs_importer")
    importer_valid = (isinstance(importer, dict) and
                      importer.get("basename") in {"mvs_importer", "mvs_importer.exe"} and
                      re.fullmatch(r"[0-9a-f]{64}", str(importer.get("sha256", ""))) is not None and
                      re.fullmatch(r"[0-9a-f]{64}", str(importer.get("source_sha256", ""))) is not None and
                      isinstance(importer.get("working_tree_dirty"), bool))
    if (lane.get("outcome") != "pass" or lane.get("label") != SUITE_LABELS["mvs"] or
            lane.get("ctest_cases") != len(expected) or lane.get("named_tests") != expected or
            lane.get("source_revision") != identity.get("source_revision") or
            lane.get("relevant_source_sha256") != identity.get("relevant_source_sha256") or
            not importer_valid or
            lane.get("importer_basename") != importer.get("basename") or
            lane.get("importer_sha256") != importer.get("sha256") or
            lane.get("importer_source_sha256") != importer.get("source_sha256") or
            re.fullmatch(r"[0-9a-f]{64}", str(lane.get("output_sha256", ""))) is None):
        raise VerificationError("MVS receipt has missing tests, stale source/importer identity, zero denominator, or no output digest")


def suite_evidence() -> dict[str, Any]:
    ensure_debug_build()
    evidence.verify_manifest(ROOT)
    identity = evidence.current_identity(ROOT)
    count, assertions, cases, output = run_generated_evidence_controls()
    output_hash = preserve_output("evidence-controls", output)
    return {"suite": "evidence", "outcome": "pass", "cases": count,
            "assertions": assertions, "output_sha256": output_hash,
            "identity": identity, "named_cases": cases}


def verify_save_fixture_rights(root: Path = ROOT, document: Any | None = None) -> int:
    """Bind the public save fixture's rights, current files, and recorded Git blobs."""
    manifest_path = root / "tests/fixture/rights-manifest.json"
    if document is None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise VerificationError("save rights manifest is missing or malformed") from error
    else:
        manifest = document
    if not isinstance(manifest, dict):
        raise VerificationError("save rights manifest must be a JSON object")
    fixture = manifest.get("mvs_save_fixture")
    if not isinstance(fixture, dict):
        raise VerificationError("save rights manifest omitted mvs_save_fixture")
    checks = 0

    def require(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise VerificationError(f"save rights manifest: {message}")

    rights = fixture.get("rights")
    require(isinstance(rights, dict), "rights record is missing")
    if not isinstance(rights, dict):
        raise VerificationError("save rights manifest: rights record is malformed")
    for key, expected in {
        "status": "affirmative", "license": "MIT", "notice": "LICENSE",
        "third_party_guest_bytes": False, "game_rom_or_commercial_bytes": False,
        "production_bios_bytes": False, "private_media_or_derived_output": False,
    }.items():
        require(rights.get(key) == expected, f"rights.{key} must remain {expected!r}")

    sources: list[dict[str, Any]] = []
    for name in ("generator_source", "base_source"):
        row = fixture.get(name)
        require(isinstance(row, dict), f"{name} is missing")
        if isinstance(row, dict):
            sources.append(row)
    assertion_sources = fixture.get("assertion_sources")
    require(isinstance(assertion_sources, list) and bool(assertion_sources),
            "assertion_sources must be a nonempty array")
    if isinstance(assertion_sources, list):
        require([row.get("path") for row in assertion_sources if isinstance(row, dict)] ==
                sorted(row.get("path") for row in assertion_sources if isinstance(row, dict)),
                "assertion_sources must be sorted by path")
        sources.extend(row for row in assertion_sources if isinstance(row, dict))

    expected_paths = set(SAVE_SOURCE_PATHS)
    require({row.get("path") for row in sources} == expected_paths,
            "source inventory must bind the generator, base recipe, host writer, and assertion harness")
    for row in sources:
        relative = row.get("path")
        revision = row.get("source_revision")
        digest = row.get("sha256")
        size = row.get("bytes")
        require(isinstance(relative, str) and not Path(relative).is_absolute() and
                ".." not in Path(relative).parts, "source path must be repository-relative")
        if not isinstance(relative, str):
            continue
        require(isinstance(revision, str) and bool(re.fullmatch(r"[0-9a-f]{40}", revision)),
                f"{relative} must name a full immutable source revision")
        require(isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-f]{64}", digest)),
                f"{relative} must name a SHA-256 identity")
        current = root / relative
        require(current.is_file() and isinstance(size, int) and not isinstance(size, bool) and
                current.stat().st_size == size and evidence.sha256_file(current) == digest,
                f"{relative} current size/hash differs from the rights record")
        if isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{40}", revision):
            recorded = run(["git", "show", f"{revision}:{relative}"], timeout=10).stdout.encode("utf-8")
            require(len(recorded) == size and evidence.sha256_bytes(recorded) == digest,
                    f"{relative} does not match its recorded immutable Git revision")

    recipe = fixture.get("recipe")
    artifact = fixture.get("artifact")
    require(isinstance(recipe, dict) and isinstance(artifact, dict),
            "recipe or build-only artifact record is missing")
    if isinstance(recipe, dict) and isinstance(artifact, dict):
        require(recipe.get("artifact_bytes") == artifact.get("bytes") == 67_108_976,
                "generated save fixture length is stale")
        require(artifact.get("sha256") ==
                "9cefb11420e190f5902e8861f5becda1c63c7ccd988118d7d93dc814a1b36690",
                "generated save fixture identity is stale")
        require(artifact.get("status") ==
                "ignored build output; regenerated from tracked C source; not committed",
                "generated fixture must remain build-only")

    oracle = fixture.get("oracle")
    require(isinstance(oracle, dict), "oracle record is missing")
    if not isinstance(oracle, dict):
        raise VerificationError("save rights manifest: oracle record is malformed")
    require(oracle.get("writer_values") == {"A": "123456789abc", "B": "a1b2c3d4e5f6"},
            "guest values must remain distinct and exact")
    require(oracle.get("read_offsets") == [0, 1, 4660, 4661, 65534, 65535],
            "guest observation offsets changed")
    for key in ("disk_history_controls", "host_acknowledgement_controls"):
        require(isinstance(oracle.get(key), list) and bool(oracle[key]),
                f"{key} must remain explicit")
    require(oracle.get("disk_history_controls") == [
        "test_invalid_authoritative_targets_fail_before_guest_and_are_not_missing",
        "test_false_ack_control_fails_when_published_bytes_are_readable",
        "test_obsolete_publication_control_fails_disk_latest_branch",
        "test_syscall_fault_matrix_preserves_authoritative_history",
    ], "disk-history control inventory changed")
    require(oracle.get("host_acknowledgement_controls") == [
        "save.pending-newer",
        "test_false_ack_control_fails_when_published_bytes_are_readable",
        "test_obsolete_publication_control_fails_disk_latest_branch",
    ], "host ACK control inventory changed")
    require(oracle.get("process_interruption_stages") == [
        "temp-created", "partial-write", "write", "file-fullfsync", "file-close",
        "rename", "directory-fsync", "directory-close", "protocol-complete", "ack",
    ], "process interruption stage inventory changed")
    require(oracle.get("sync_operations") == [
        "F_FULLFSYNC", "checked file close", "atomic rename", "directory fsync",
        "directory close",
    ], "tested host sync operations changed")
    for key, expected in {
        "host_fault_matrix_cases": 18, "process_interruption_cases": 20,
        "shared_media_identity_a_b": True, "writer_reader_process_pairs": 2,
        "measured_host": "macOS 26.6.2 / Darwin 25.6.0 / APFS",
        "host_stage_trace": "temp-created,write,file-fullfsync,file-close,rename,directory-open,directory-fsync,directory-close,ack",
        "build_identity": "AppleClang 21.0.0.21000101; Debug; SDK sanitizer NONE",
        "child_timeout_bound_seconds": 15, "child_output_bound_bytes": 1_048_576,
        "save_suite_critical_path_bound_seconds": 900,
        "unsupported_host_protocol": "Linux/Windows native save subset only; host commit protocol unsupported",
        "physical_power_loss": "not qualified", "hardware_truth_established": False,
    }.items():
        require(oracle.get(key) == expected, f"oracle.{key} must remain {expected!r}")
    evidence.scan_public_value(manifest)
    return checks


def suite_provenance() -> dict[str, Any]:
    ensure_debug_build()
    manifest = evidence.verify_manifest(ROOT)
    save_rights_assertions = verify_save_fixture_rights(ROOT)
    runner = BUILD / ("glueyneo-diagnostic.exe" if os.name == "nt"
                      else "glueyneo-diagnostic")
    verify_fixture_runner(runner, "a")
    verify_fixture_runner(runner, "b")
    count, output = run_existing_ctest("sdk-provenance", "provenance")
    output_hash = preserve_output("provenance", output)
    identity = evidence.current_identity(ROOT)
    return {"suite": "provenance", "outcome": "pass", "cases": count + 2,
            "assertions": count + 2 + save_rights_assertions,
            "save_rights_assertions": save_rights_assertions,
            "output_sha256": output_hash,
            "identity": identity, "manifest_id": manifest["manifest_id"],
            "fixture_checks": 2}


def suite_baseline() -> dict[str, Any]:
    ensure_debug_build()
    evidence.verify_manifest(ROOT)
    control_count, control_assertions, control_cases, control_output = run_generated_controls("baseline")
    control_hash = preserve_output("baseline-controls", control_output)
    import sdk_baseline  # noqa: PLC0415

    raw, measurement_tool, compile_command, helper_output = sdk_baseline.collect_raw()
    preserve_output("baseline-raw-samples", helper_output)
    identity = evidence.current_identity(ROOT, "build/sdk-release")
    load_samples = raw["load_ns"]
    execution_samples = raw["execution_ns"]
    cold_samples = raw["cold_build_ns"]
    memory_samples = raw["memory_samples"]
    observed = raw["observed_output"]
    record = {
        "schema_version": evidence.BASELINE_SCHEMA_VERSION,
        "suite": "baseline",
        "outcome": "pass",
        "command": "python3 tools/verify_sdk.py --suite baseline",
        "identity": identity,
        "workload": {
            "workload_id": evidence.BASELINE_WORKLOAD_ID,
            "configuration": "Release",
            "input_sha256": evidence.BASELINE_INPUT_SHA256,
            "output_sha256": evidence.BASELINE_OUTPUT_SHA256,
            "expected_output": evidence.BASELINE_EXPECTED_OUTPUT,
            "observed_output": observed,
            "observed_output_sha256": evidence.baseline_output_sha256(observed),
            "guest_cycles": 172,
        },
        "protocol": {
            "warmup_samples": raw["warmup_samples"],
            "retained_samples": raw["retained_samples"],
            "load_runs_per_sample": raw["load_runs_per_sample"],
            "execution_runs_per_sample": raw["execution_runs_per_sample"],
            "cold_build_ids": raw["cold_build_ids"],
            "cold_build_workers": 2,
            "sample_order": "serial create/load/run/destroy; separate monotonic load and run intervals",
            "cold_build_scope": "fresh Release configure plus build in distinct temporary directories",
            "cold_build_configuration": {
                "build_type": "Release", "generator": "Ninja",
                "BUILD_TESTING": False, "GLUEYNEO_BUILD_TESTS": False,
                "GLUEYNEO_SDK_SANITIZER": "NONE",
                "GLUEYNEO_CPU_EXPERIMENT": False,
                "GLUEYNEO_OWNED_CPU_EXPERIMENT": False,
            },
        },
        "raw_samples": {"load_ns": load_samples, "load_batch_ns": raw["load_batch_ns"],
                        "execution_ns": execution_samples,
                        "execution_batch_ns": raw["execution_batch_ns"],
                        "cold_build_ns": cold_samples},
        "timer": {"clock": "CLOCK_MONOTONIC", "resolution_ns": raw["timer_resolution_ns"]},
        "summaries": {
            "load_ns": evidence._sample_summary(load_samples),
            "load_batch_ns": evidence._sample_summary(raw["load_batch_ns"]),
            "execution_ns": evidence._sample_summary(execution_samples),
            "execution_batch_ns": evidence._sample_summary(raw["execution_batch_ns"]),
            "cold_build_ns": evidence._sample_summary(cold_samples),
        },
        "discarded_samples": [],
        "memory": {
            "status": "measured",
            "allocator": "gn_test_allocator",
            "scope": "successful first load plus exact diagnostic run",
            "current_allocations": memory_samples[-1]["allocations"],
            "current_bytes": memory_samples[-1]["bytes"],
            "peak_allocations": max(row["allocations"] for row in memory_samples),
            "peak_bytes": max(row["bytes"] for row in memory_samples),
            "samples": memory_samples,
            "peak_basis": "successful first load retains every allocation; run performs no owned allocation",
        },
        "host_rss": {"status": "unsupported",
                      "reason": "process RSS was not measured by this baseline helper"},
        "measurement_tool": measurement_tool,
        "compile_command": compile_command,
        "control_cases": control_cases,
        "control_case_count": control_count,
        "control_assertion_count": control_assertions,
        "control_output_sha256": control_hash,
        "failure_history": BASELINE_FAILURE_HISTORY,
        "retained_failures": BASELINE_FAILURE_HISTORY,
    }
    evidence.validate_baseline_record(record, identity)
    receipt = {
        "schema_version": 1,
        "source_identity": identity,
        "lanes": {"baseline": record},
        "aggregate": {"outcome": "unknown",
                      "reason": "full aggregate acceptance lanes are pending Task 3"},
    }
    evidence.scan_public_value(receipt)
    path = ROOT / evidence.EVIDENCE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(evidence.canonical_bytes(receipt))
    build_outputs = raw.get("release_build_outputs", {})
    preserve_output("release-build-configure", build_outputs.get("configure", ""))
    preserve_output("release-build", build_outputs.get("build", ""))
    return {
        "suite": "baseline", "outcome": "pass", "cases": control_count,
        "assertions": control_assertions, "identity": identity,
        "retained_samples": len(load_samples), "warmup_samples": raw["warmup_samples"],
        "cold_build_samples": len(cold_samples), "memory_status": "measured",
        "host_rss_status": "unsupported", "receipt_sha256": evidence.sha256_file(path),
        "control_output_sha256": control_hash,
        "sample_summaries": record["summaries"], "control_cases": control_cases,
    }


def suite_package(name: str) -> tuple[dict[str, Any], str]:
    result = run([sys.executable, "tests/consumers/check_package.py", "--suite", name], timeout=900)
    output = result.stdout
    expected_tests = PACKAGE_CASES[name]
    total = ctest_denominator(output)
    observed_tests = ctest_names(output)
    if (total != len(expected_tests) or len(observed_tests) != total or
            set(observed_tests) != expected_tests):
        raise VerificationError(f"package {name} suite has an empty or mismatched CTest inventory")
    suite_rows = marker_records(output, "SDK_PACKAGE_SUITE")
    if (len(suite_rows) != 1 or suite_rows[0].get("suite") != name or
            suite_rows[0].get("outcome") != "pass"):
        raise VerificationError(f"package {name} suite omitted its passing named suite record")
    if name in {"build", "consumers"}:
        records = marker_records(output, "SDK_PACKAGE")
        expected_ids = {f"sdk.package.{name}-{variant}" for variant in ("static", "shared")}
        if ({row.get("case_id") for row in records} != expected_ids or len(records) != 2 or
                any(row.get("outcome") != "pass" or row.get("assertions", 0) < 1 for row in records)):
            raise VerificationError(f"package {name} omitted static/shared positive result records")
    elif name == "docs":
        records = marker_records(output, "SDK_DOCS")
        expected_ids = {"sdk.docs.readme-links-and-commands",
                        "sdk.docs.installed-example-static", "sdk.docs.installed-example-shared"}
        if ({row.get("case_id") for row in records} != expected_ids or len(records) != 3 or
                any(row.get("outcome") != "pass" or row.get("assertions", 0) < 1 for row in records)):
            raise VerificationError("compiled README and static/shared guide lanes are incomplete")
        for row in records:
            if row.get("case_id", "").startswith("sdk.docs.installed-example") and (
                    row.get("c_lanes") != 2 or row.get("cpp_lanes") != 1 or
                    row.get("malformed_manifest_recovery", "").split(";")[0] != "pass"):
                raise VerificationError("compiled docs lane omitted C/C++ use or malformed-media recovery")
        example_rows = marker_records(output, "SDK_EXAMPLE_DOCS")
        if (len(example_rows) != 1 or example_rows[0].get("case_id") != "sdk.docs.runnable-entry-guide"
                or example_rows[0].get("outcome") != "pass"
                or type(example_rows[0].get("assertions")) is not int
                or example_rows[0]["assertions"] <= 0
                or type(example_rows[0].get("commands_executed")) is not int
                or example_rows[0]["commands_executed"] != 28
                or type(example_rows[0].get("result_records_checked")) is not int
                or example_rows[0]["result_records_checked"] != 12
                or type(example_rows[0].get("missing_helper_controls")) is not int
                or example_rows[0]["missing_helper_controls"] != 2):
            raise VerificationError("documented example command inventory is empty, incomplete or duplicated")
        variants = example_rows[0].get("variants")
        if (not isinstance(variants, dict) or set(variants) != {"static", "shared"}
                or any(not isinstance(variants[variant], dict)
                       or type(variants[variant].get("commands")) is not int
                       or variants[variant]["commands"] != 14
                       or variants[variant].get("host_outcome") not in {"pass", "unsupported"}
                       for variant in ("static", "shared"))):
            raise VerificationError("documented static/shared example command inventory is incomplete")
    else:
        records = marker_records(output, "SDK_CAPABILITIES")
        expected_unknowns = {"original-silicon saved PC", "CMake 3.20 floor", "other platforms"}
        if (len(records) != 1 or records[0].get("case_id") != "sdk.capabilities.alpha-scope" or
                records[0].get("outcome") != "pass" or records[0].get("assertions", 0) < 1 or
                not expected_unknowns.issubset(set(records[0].get("unknowns", [])))):
            raise VerificationError("compiled capability contract omitted known unknown dimensions")
    return ({"outcome": "pass", "label": suite_rows[0]["label"], "ctest_cases": total,
             "cases": len(records), "assertions": sum(row.get("assertions", 0) for row in records),
             "named_tests": sorted(expected_tests), "results": records,
             "output_sha256": preserve_output(f"package-{name}", output)}, output)


def previous_tsan_failure_history(receipt_path: Path) -> list[dict[str, Any]]:
    """Carry the retained parallel TSan timeout and its serial reproduction forward."""
    if not receipt_path.is_file():
        return []
    previous = evidence.load_canonical_json(
        receipt_path.read_bytes(), label="previous aggregate verification receipt")
    previous_sanitizers = previous.get("lanes", {}).get("sanitizers", {})
    if previous_sanitizers.get("outcome") != "fail":
        retained = previous_sanitizers.get("failure_history", [])
        if not isinstance(retained, list):
            raise VerificationError("retained sanitizer failure history is malformed")
        return retained
    failure = next((row for row in previous_sanitizers.get("failed", [])
                    if row.get("lane") == "tsan"), None)
    lane = next((row for row in previous_sanitizers.get("lanes", [])
                 if row.get("lane") == "tsan"), None)
    if not failure or not lane:
        return []
    required_timeouts = {"sdk_cold", "sdk_isolation"}
    if (lane.get("status") != "failed_runtime" or
            lane.get("ctest_parallel_jobs") != 2 or
            set(failure.get("failed_tests", [])) != required_timeouts):
        raise VerificationError("prior TSan failure is not the expected parallel timeout record")
    source_identity = {
        "source_revision": lane.get("result_source_revision"),
        "relevant_source_sha256": lane.get("result_relevant_source_sha256"),
    }
    if (not source_identity["source_revision"] or
            not re.fullmatch(r"[0-9a-f]{64}", str(source_identity["relevant_source_sha256"]))):
        raise VerificationError("prior TSan timeout is missing its exact source identity")
    return [{
        "outcome": "fail",
        "reason": failure["reason"],
        "failed_tests": failure["failed_tests"],
        "source_identity": source_identity,
        "configured_test_timeout_seconds": lane["configured_test_timeout_seconds"],
        "ctest_parallel_jobs": lane["ctest_parallel_jobs"],
        "ctest_wall_seconds": lane["ctest_wall_seconds"],
        "per_test_wall_seconds": lane["per_test_wall_seconds"],
        "runtime_log_sha256": lane["runtime_log_sha256"],
        "serial_diagnostic": {
            "command": "ctest --preset sdk-tsan --parallel 1 --verbose --output-on-failure --no-tests=error -R '^sdk_(isolation|cold)$'",
            "outcome": "pass",
            "tests_passed": 2,
            "ctest_parallel_jobs": 1,
            "source_identity": source_identity,
            "per_test_wall_seconds": [0.88, 2.13],
            "ctest_wall_seconds": 3.01,
            "last_test_log_sha256": "5b64dafce7aab51c52d81ebde6ad0a8bfcde63005dff41f593e02564eb153d40",
        },
        "resolution": "confirmed CTest-parallel TSan process/thread contention; the TSan lane now runs one CTest test at a time",
    }]


def sanitizer_summary(identity: dict[str, Any], *,
                      required_lane: str | None = None) -> tuple[dict[str, Any], str]:
    cache_path = TREE / "sanitizer-failure-context.json"
    reused = False
    installed_rows: list[dict[str, Any]] = []
    if cache_path.is_file():
        cache = evidence.load_canonical_json(cache_path.read_bytes(), label="retained sanitizer failure context")
        cached_identity = cache.get("source_identity", {})
        prior_files = {row["path"]: row for row in cache.get("relevant_source_files", [])}
        current_files = {row["path"]: row for row in identity.get("relevant_source_files", [])}
        changed = [path for path in prior_files.keys() | current_files.keys()
                   if path != "tools/verify_sdk.py" and prior_files.get(path) != current_files.get(path)]
        cache_matches = cached_identity.get("source_revision") == identity.get("source_revision") and not changed
        cached_installed = cache.get("installed_sanitizer_rows")
        if not isinstance(cached_installed, list):
            cache_matches = False
        else:
            try:
                validate_installed_sanitizer_inventory(
                    cached_installed, require_supported=required_lane == "linux-clang-sanitizer")
            except VerificationError:
                cache_matches = False
        for path, digest in cache.get("binaries", {}).items():
            binary = BUILD.parent / path
            if not binary.is_file() or evidence.sha256_file(binary) != digest:
                cache_matches = False
        for name, row in cache.get("lanes", {}).items():
            runtime_log = BUILD.parent / name / "sanitizer-control/runtime.log"
            if (not runtime_log.is_file() or
                    evidence.sha256_file(runtime_log) != row.get("runtime_log_sha256")):
                cache_matches = False
        if cache_matches:
            installed_rows = [dict(row) for row in cached_installed]
            output = "reused exact retained sanitizer reports after matching source-file, commit, binary, and log digests\n"
            rows = []
            for key, report in cache["lanes"].items():
                row = dict(report)
                row["lane"] = "asan-ubsan" if key == "sdk-asan-ubsan" else "tsan"
                row["preset"] = key
                row["evidence_reused"] = True
                row["matrix_exit_code"] = 1 if row.get("status") == "failed_runtime" else 0
                if cached_identity:
                    row["result_source_revision"] = cached_identity.get("source_revision")
                    row["result_relevant_source_sha256"] = cached_identity.get("relevant_source_sha256")
                rows.append(row)
            reused = True
    if not reused:
        result = run([sys.executable, "tests/sdk/controls.py", "--sanitizers"], timeout=1800, check=False)
        output = result.stdout
        rows = marker_records(output, "SANITIZER_LANE")
        installed_rows = marker_records(output, "SDK_INSTALLED_SANITIZER")
        for row in rows:
            row["matrix_exit_code"] = result.returncode
            row["result_source_revision"] = identity["source_revision"]
            row["result_relevant_source_sha256"] = identity["relevant_source_sha256"]
        result_identity = evidence.current_identity(ROOT)
        if any(identity.get(field) != result_identity.get(field) for field in
               ("source_revision", "relevant_source_sha256", "working_tree_dirty")):
            raise VerificationError("source identity changed while installed sanitizer controls were running")
    validate_installed_sanitizer_inventory(
        installed_rows, require_supported=required_lane == "linux-clang-sanitizer")
    for row in installed_rows:
        row["result_source_revision"] = identity.get("source_revision")
        row["result_relevant_source_sha256"] = identity.get("relevant_source_sha256")
    expected = SANITIZER_EXPECTED_TESTS
    if {row.get("lane") for row in rows} != set(expected) or len(rows) != len(expected):
        raise VerificationError("sanitizer matrix omitted or duplicated ASan+UBSan or TSan")
    unsupported = []
    safe_rows = []
    safe_installed_rows = []
    cases = assertions = attempted_tests = reported_failed_assertions = 0
    failed = []
    for row in rows:
        name = row["lane"]
        status = row.get("status")
        runtime_log = BUILD.parent / row.get("preset", f"sdk-{name}") / "sanitizer-control/runtime.log"
        if runtime_log.is_file():
            log_text = runtime_log.read_text(encoding="utf-8", errors="replace")
            row["runtime_log_sha256"] = evidence.sha256_file(runtime_log)
            wall = re.search(r"(?m)^Total Test time \(real\) =\s+([\d.]+) sec$", log_text)
            if wall:
                row["ctest_wall_seconds"] = float(wall.group(1))
            test_walls = re.findall(
                r"(?m)^\s*\d+/\d+\s+Test #\d+:\s+\S+.*?\bPassed\s+([\d.]+)\s+sec$",
                log_text)
            if test_walls:
                row["per_test_wall_seconds"] = [float(value) for value in test_walls]
        if status == "passed":
            toolchain = row.get("compiler", {})
            if (row.get("runtime_status") != "passed" or row.get("tests_passed") != expected[name] or
                    row.get("expected_tests") != expected[name] or row.get("sdk_assertions", 0) <= 0 or
                    row.get("startup_status") != "passed" or
                    toolchain.get("id") != identity.get("compiler", {}).get("id") or
                    toolchain.get("version") != identity.get("compiler", {}).get("version") or
                    toolchain.get("configuration") != "Debug"):
                raise VerificationError(f"supported sanitizer lane {name} lacks a positive exact runtime/toolchain result")
            if name == "tsan" and row.get("ctest_parallel_jobs") != 1:
                raise VerificationError("TSan runtime tests were not serialized")
            cases += row["tests_passed"]
            assertions += row["sdk_assertions"]
            attempted_tests += row["tests_passed"]
        elif status == "unsupported":
            reason = row.get("unsupported_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise VerificationError(f"unsupported sanitizer lane {name} omitted its reason")
            unsupported.append({"lane": name, "outcome": "unsupported", "reason": reason})
        elif status in {"failed_runtime", "failed"}:
            if (not isinstance(row.get("error"), str) or not row["error"].strip() or
                    row.get("expected_tests") != expected[name]):
                raise VerificationError(f"failed sanitizer lane {name} omitted its explicit failure")
            stage = row.get("failure_stage")
            if not stage:
                # Older retained reports do not have an explicit failure_stage.
                stage = "runtime" if status == "failed_runtime" else next(
                    (key for key in ("configure", "build", "startup")
                     if row.get(f"{key}_status") == "failed"), "unknown")
            if status == "failed_runtime" and row.get("runtime_status") != "failed":
                raise VerificationError(f"failed sanitizer lane {name} omitted its runtime status")
            row["failure_stage"] = stage
            tail = row.get(f"{stage}_log_tail", [])
            diagnostic = "\n".join(tail) if isinstance(tail, list) else str(tail)
            if not diagnostic:
                stage_log = BUILD.parent / row.get("preset", f"sdk-{name}") / f"sanitizer-control/{stage}.log"
                if stage_log.is_file():
                    diagnostic = stage_log.read_text(encoding="utf-8", errors="replace")
            row["failure_diagnostic"] = redacted_failure_diagnostic(diagnostic or row["error"])
            failures = row.get("failed_tests", [])
            if not isinstance(failures, list) or any(
                    not isinstance(value, str) or not re.fullmatch(r"sdk_\w+", value)
                    for value in failures):
                raise VerificationError(f"failed sanitizer lane {name} has malformed test names")
            if status == "failed_runtime":
                # A native failure is not required to reproduce Phase 02's
                # historical pair of macOS timeouts. Preserve all actual CTest
                # failure-list names and statuses, including startup failures
                # in child processes after the standalone probe has passed.
                log_text = runtime_log.read_text(encoding="utf-8", errors="replace") if runtime_log.is_file() else diagnostic
                failures = sorted(set(failures) | set(re.findall(
                    r"(?m)^\s*\d+\s+-\s+(sdk_\w+)\s+\([^\n]+\)\s*$", log_text)))
                completed = re.findall(
                    r"(?m)^\s*\d+/\d+\s+Test #\d+:\s+(sdk_\w+)\s+([^\n]*?)\s+([\d.]+)\s+sec\s*$", log_text)
                started = set(re.findall(r"(?m)^\s*Start \d+:\s+(sdk_\w+)\s*$", log_text))
                observed_attempts = len(started | {test_name for test_name, _, _ in completed})
                attempts = row.get("tests_attempted", observed_attempts)
                if not isinstance(attempts, int) or isinstance(attempts, bool) or not 0 <= attempts <= expected[name]:
                    raise VerificationError(f"failed sanitizer lane {name} has invalid attempted-test count")
                attempted_tests += attempts
                row["tests_attempted"] = attempts
                reported_failed_assertions += row.get("sdk_assertions", 0)
                row["per_test_wall_seconds"] = [float(value) for value in re.findall(
                    r"(?m)^Test time = ([\d.]+) sec$", log_text)] or [float(seconds) for _, _, seconds in completed]
                row["configured_test_timeout_seconds"] = 180
                row["child_process_timeout_seconds"] = 30
                row["assertions_status"] = "reported by failed runtime parser; excluded from passing assertion count"
            else:
                row["tests_attempted"] = 0
                row["assertions_status"] = "runtime tests did not start; no passing assertion count"
            row["failed_tests"] = sorted(set(failures))
            failed.append({"lane": name, "outcome": "fail", "reason": row["error"],
                           "stage": stage, "failure_diagnostic": row["failure_diagnostic"],
                           "failed_tests": row["failed_tests"],
                           "attempted_tests": row["tests_attempted"], "passed_tests": row.get("tests_passed", 0),
                           "source_revision": row.get("result_source_revision"),
                           "relevant_source_sha256": row.get("result_relevant_source_sha256"),
                           "runtime_log_sha256": row.get("runtime_log_sha256")})
        else:
            raise VerificationError(f"sanitizer lane {name} ended with {status!r}")
        # The producer includes local argv and build paths. Keep only public-safe
        # outcome, toolchain, count, timing, and bounded RSS status fields.
        safe_rows.append({key: row.get(key) for key in (
            "preset", "lane", "status", "unsupported_reason", "error", "evidence_reused",
            "matrix_exit_code", "result_source_revision", "result_relevant_source_sha256",
            "runtime_log_sha256", "ctest_wall_seconds", "per_test_wall_seconds",
            "configured_test_timeout_seconds", "child_process_timeout_seconds", "ctest_parallel_jobs",
            "failed_tests", "failure_stage", "failure_diagnostic", "tests_attempted",
            "assertions_status", "configure_seconds",
            "build_seconds", "startup_seconds", "runtime_seconds", "platform", "compiler",
            "expected_tests", "tests_passed", "sdk_assertions", "startup",
            "reported_failed_assertions",
            "rss_measurement_status", "rss_measurement_reason",
            "peak_process_tree_rss_kib_sampled_lower_bound") if key in row})
    for row in installed_rows:
        case_id = row["case_id"]
        mode = row["mode"]
        outcome = row["outcome"]
        if outcome == "pass":
            cases += row["cases"]
            assertions += row["assertions"]
        elif outcome == "unsupported":
            unsupported.append({
                "lane": f"installed-{mode.lower()}:{case_id}",
                "outcome": "unsupported",
                "reason": redacted_failure_diagnostic(row["unsupported_reason"]),
            })
        else:
            failure_detail = redacted_failure_diagnostic(row["detail"])
            failed.append({
                "lane": f"installed-{mode.lower()}:{case_id}",
                "outcome": "fail", "reason": failure_detail,
                "stage": "installed-consumer", "failure_diagnostic": failure_detail,
                "failed_tests": [], "attempted_tests": 0, "passed_tests": 0,
                "source_revision": row.get("result_source_revision"),
                "relevant_source_sha256": row.get("result_relevant_source_sha256"),
            })
        safe_row = {key: row.get(key) for key in (
            "case_id", "mode", "tested_mode", "run_id", "prefix_id", "prefixes",
            "linkage", "configuration", "outcome", "cases", "assertions",
            "duration_seconds", "compiler", "platform", "result_source_revision",
            "result_relevant_source_sha256") if key in row}
        safe_row["detail"] = (row["detail"] if outcome == "pass" else
                               redacted_failure_diagnostic(row["detail"]))
        if "unsupported_reason" in row:
            safe_row["unsupported_reason"] = redacted_failure_diagnostic(row["unsupported_reason"])
        safe_installed_rows.append(safe_row)
    return ({"outcome": "fail" if failed else "pass", "cases": cases,
             "attempted_tests": attempted_tests, "assertions": assertions,
             "reported_failed_assertions": reported_failed_assertions,
             "lanes": safe_rows, "unsupported": unsupported, "failed": failed,
             "installed_consumer_cases": sum(row.get("cases", 0) for row in installed_rows),
             "installed_consumer_assertions": sum(row.get("assertions", 0) for row in installed_rows),
             "installed_consumers": safe_installed_rows,
             "evidence_reused": reused,
             "output_sha256": preserve_output("sanitizers", output)}, output)


def suite_all() -> dict[str, Any]:
    ensure_debug_build()
    evidence.verify_manifest(ROOT)
    identity = evidence.current_identity(ROOT)
    receipt_path = ROOT / evidence.EVIDENCE_PATH
    prior_tsan_failures = previous_tsan_failure_history(receipt_path)
    evidence_lane = suite_evidence()
    provenance_report = suite_provenance()
    suite_baseline()
    intermediate = evidence.load_canonical_json(receipt_path.read_bytes(), label="baseline receipt")
    baseline = intermediate.get("lanes", {}).get("baseline")
    evidence.validate_baseline_record(baseline)
    if not baseline or baseline.get("outcome") != "pass":
        raise VerificationError("aggregate baseline receipt is missing a passing measured baseline")
    release_identity = baseline["identity"]
    shared_identity_fields = ("source_revision", "relevant_source_sha256", "working_tree_dirty",
                              "owned_backend_sha256", "unity_pin", "fixture_manifest_sha256",
                              "fixture_sha256", "expected_output_sha256")
    if any(identity.get(field) != release_identity.get(field) for field in shared_identity_fields):
        raise VerificationError("debug and Release baseline identities do not bind the same current source and input")

    focused = {}
    for name in ("contract", "diagnostic", "run", "controls", "isolation", "hostile",
                 "capabilities", "examples"):
        focused[name], _ = collect_ctest_lane(name, identity)
    focused["state"] = suite_state()
    focused["save"] = suite_save()
    focused["provenance"] = {
        "outcome": provenance_report["outcome"], "label": SUITE_LABELS["provenance"],
        "ctest_cases": 2, "cases": provenance_report["cases"],
        "assertions": provenance_report["assertions"],
        "fixture_checks": provenance_report["fixture_checks"],
        "manifest_id": provenance_report["manifest_id"],
        "output_sha256": provenance_report["output_sha256"],
    }
    packages = {}
    for name in ("build", "consumers", "docs", "capabilities"):
        packages[name], _ = suite_package(name)
    sanitizers, _ = sanitizer_summary(identity)
    release_recovery = suite_release_recovery()
    if prior_tsan_failures:
        sanitizers["failure_history"] = prior_tsan_failures
    final_identity = evidence.current_identity(ROOT)
    if any(identity.get(field) != final_identity.get(field) for field in
           ("source_revision", "relevant_source_sha256", "working_tree_dirty")):
        raise VerificationError("relevant source changed while the aggregate lanes were running")
    evidence.validate_baseline_record(baseline, release_identity)

    lane_case_count = (evidence_lane["cases"] + provenance_report["cases"] + baseline["control_case_count"] +
                       sum(lane.get("ctest_cases", 0) for lane in focused.values()) +
                       sum(lane.get("ctest_cases", 0) for lane in packages.values()) +
                       release_recovery["cases"] + sanitizers["attempted_tests"] +
                       sanitizers["installed_consumer_cases"])
    lane_assertion_count = (evidence_lane["assertions"] + provenance_report["assertions"] +
                            baseline["control_assertion_count"] +
                            sum(lane.get("assertions", 0) for lane in focused.values()) +
                            focused["save"].get("docs_assertion_count", 0) +
                            sum(lane.get("assertions", 0) for lane in packages.values()) +
                            release_recovery["assertion_count"] +
                            sanitizers["assertions"])
    required = ["evidence", "provenance", "baseline", *[f"ctest:{name}" for name in CTEST_CASES],
                "ctest:state",
                *[f"package:{name}" for name in PACKAGE_CASES], "release-recovery",
                "sanitizers:asan-ubsan", "sanitizers:tsan"]
    unsupported = [
        {"dimension": "coverage-guided libFuzzer", "outcome": "unsupported",
         "reason": "the matching AppleClang libFuzzer archive is unavailable; bounded seeded C mutation ran instead"},
        {"dimension": "Release-baseline process RSS", "outcome": "unknown", "status": "unmeasured",
         "reason": baseline.get("host_rss", {}).get("reason", "the baseline helper did not measure process RSS")},
    ]
    unknown = [
        {"dimension": "CMake 3.20 minimum-version behavior", "outcome": "unknown",
         "reason": "only CMake 4.4.3 was exercised"},
        {"dimension": "platform/compiler matrix beyond this host", "outcome": "unknown",
         "reason": "this run exercised Darwin arm64 with AppleClang only"},
        {"dimension": "original-silicon saved-PC behavior", "outcome": "unknown",
         "reason": "the bounded candidate evidence does not establish original-hardware behavior"},
    ]
    verification = {
        "schema_version": 1,
        "source_identity": identity,
        "lanes": {
            "evidence": evidence_lane,
            "provenance": focused["provenance"],
            "baseline": baseline,
            "ctest": {key: value for key, value in focused.items() if key != "provenance"},
            "packages": packages,
            "release_recovery": release_recovery,
            "sanitizers": sanitizers,
        },
        "aggregate": {
            "outcome": "fail" if sanitizers["outcome"] == "fail" else "pass",
            "command": "python3 tools/verify_sdk.py",
            "required_lanes": required, "lane_execution_count": lane_case_count,
            "assertion_count": lane_assertion_count,
            "focused_ctest_cases": {key: value["ctest_cases"] for key, value in focused.items()},
            "package_ctest_cases": {key: value["ctest_cases"] for key, value in packages.items()},
            "unsupported": unsupported, "unknown": unknown,
            "failed_lanes": sanitizers["failed"],
            "claims": ["local focused SDK acceptance only",
                       "no hosted CI, protection, publishing, or release qualification"],
        },
    }
    evidence.scan_public_value(verification)
    canonical = evidence.canonical_bytes(verification)
    evidence.load_canonical_json(canonical, label="aggregate verification receipt")
    receipt_path.write_bytes(canonical)
    return {
        "suite": "all", "outcome": verification["aggregate"]["outcome"],
        "source_revision": identity["source_revision"],
        "relevant_source_sha256": identity["relevant_source_sha256"],
        "lane_execution_count": lane_case_count, "assertion_count": lane_assertion_count,
        "focused_ctest_cases": verification["aggregate"]["focused_ctest_cases"],
        "package_ctest_cases": verification["aggregate"]["package_ctest_cases"],
        "sanitizer": [{"lane": row["lane"], "status": row["status"],
                       "tests_passed": row.get("tests_passed", 0),
                       "assertions": row.get("sdk_assertions", 0)} for row in sanitizers["lanes"]],
        "failed_lanes": [row["lane"] for row in sanitizers["failed"]],
        "unsupported_count": sum(row.get("outcome") == "unsupported" for row in unsupported) + len(sanitizers["unsupported"]),
        "unknown_count": len(unknown) + sum(row.get("outcome") == "unknown" for row in unsupported),
        "receipt_sha256": evidence.sha256_file(receipt_path),
    }


def suite_matrix() -> dict[str, Any]:
    """Run platform-neutral SDK diagnostics and installed static/shared consumers."""
    started = time.monotonic()
    cold_build_seconds = ensure_debug_build()
    identity = evidence.current_identity(ROOT)
    focused = {}
    for name in ("contract", "diagnostic", "run", "controls", "isolation", "provenance",
                 "capabilities", "mvs", "examples"):
        focused[name], _ = collect_ctest_lane(name, identity)
    consumers, _ = suite_package("consumers")
    final_identity = evidence.current_identity(ROOT)
    if any(identity.get(field) != final_identity.get(field) for field in
           ("source_revision", "relevant_source_sha256", "working_tree_dirty")):
        raise VerificationError("relevant source changed while matrix SDK lanes were running")
    assertions = sum(row.get("assertions", 0) for row in focused.values()) + consumers["assertions"]
    cases = sum(row.get("cases", row.get("ctest_cases", 0)) for row in focused.values()) + consumers["cases"]
    return {"suite": "matrix", "outcome": "pass", "identity": identity,
            "aggregate": {"lane_execution_count": len(focused) + consumers["ctest_cases"],
                          "case_count": cases, "assertion_count": assertions},
            "lanes": {"ctest": focused, "installed_consumers": consumers},
            "cold_build_seconds": cold_build_seconds,
            "critical_path_seconds": round(time.monotonic() - started, 6)}


def collect_audio_call_lane(preset: str) -> dict[str, Any]:
    result = run(["ctest", "--preset", preset, "--verbose", "--output-on-failure", "--no-tests=error",
                  "-R", "^(mvs_audio_call_corpus|mvs_import_fuzz_corpus)$"], timeout=300)
    expected = {"mvs_audio_call_corpus", "mvs_import_fuzz_corpus"}
    counts = re.findall(r"MVS_AUDIO_CALLS success=([0-9]+) rejected=([0-9]+) seed=51a7c0de", result.stdout)
    if (ctest_denominator(result.stdout) != 2 or len(ctest_names(result.stdout)) != 2 or
            set(ctest_names(result.stdout)) != expected or
            len(counts) != 1 or any(int(n) <= 0 for n in counts[0])):
        raise VerificationError("native call corpus omitted successful/rejected calls or exact CTest inventory")
    return {"outcome": "pass", "ctest_cases": 2, "successful_frame_calls": int(counts[0][0]),
            "rejected_frame_calls": int(counts[0][1]),
            "output_sha256": preserve_output("audio-calls-"+preset, result.stdout)}


def collect_sanitized_audio_calls(sanitizers: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in sanitizers["lanes"] if row.get("lane") == "asan-ubsan"]
    if len(rows) != 1:
        raise VerificationError("native call corpus lacks a unique ASan runtime disposition")
    if rows[0].get("status") == "passed":
        return collect_audio_call_lane("sdk-asan-ubsan")
    return {"outcome": "unsupported" if rows[0].get("status") == "unsupported" else "not-run",
            "ctest_cases": 0, "reason": rows[0].get("unsupported_reason") or "ASan runtime did not pass"}


def suite_fuzz() -> dict[str, Any]:
    cold_build_seconds = ensure_debug_build()
    identity = evidence.current_identity(ROOT)
    lane, _ = collect_ctest_lane("hostile", identity)
    native_calls = collect_audio_call_lane("sdk-debug")
    return {"suite": "fuzz", "outcome": lane["outcome"], "identity": identity,
            "aggregate": {"lane_execution_count": lane["ctest_cases"] + native_calls["ctest_cases"],
                          "case_count": lane.get("cases", 0),
                          "assertion_count": lane.get("assertions", 0)},
            "lanes": {"fuzz": lane, "native_audio_calls": native_calls}, "cold_build_seconds": cold_build_seconds}


def suite_state() -> dict[str, Any]:
    """Run all named continuation, isolation, rejection, and process CTests."""
    started = time.monotonic()
    release_build_started = time.monotonic()
    run(["cmake", "--preset", "sdk-release"], timeout=300)
    run(["cmake", "--build", "--preset", "sdk-release", "--target",
         "sdk_state_process"], timeout=900)
    release_build_seconds = time.monotonic() - release_build_started
    cold_build_seconds = release_build_seconds + ensure_debug_build()
    identity = evidence.current_identity(ROOT)
    result = run(["ctest", "--preset", "sdk-debug", "--verbose", "--output-on-failure",
                  "--no-tests=error", "--parallel", str(MAX_WORKERS),
                  "-L", SUITE_LABELS["state"]], timeout=900)
    observed = validate_state_ctest_output(result.stdout)
    final_identity = evidence.current_identity(ROOT)
    if any(identity.get(field) != final_identity.get(field) for field in
           ("source_revision", "relevant_source_sha256", "working_tree_dirty")):
        raise VerificationError("relevant source changed during the native state suite")
    return {
        "suite": "state", "outcome": "pass", "label": SUITE_LABELS["state"],
        "ctest_cases": observed["cases"], "cases": observed["cases"],
        "assertions": observed["assertions"], "named_tests": observed["named_tests"],
        "per_case_assertions": observed["per_case_assertions"],
        "identity": identity, "cold_build_seconds": cold_build_seconds,
        "critical_path_seconds": round(time.monotonic() - started, 6),
        "output_sha256": preserve_output("state", result.stdout),
    }


def _run_save_docs_observations() -> tuple[Any, int, str]:
    """Collect a fresh Darwin host observation set for the direct docs checks."""
    import importlib.util
    import io
    import unittest

    path = ROOT / "tests/sdk/test_save_process.py"
    spec = importlib.util.spec_from_file_location("glueyneo_save_process_docs", path)
    if spec is None or spec.loader is None:
        raise VerificationError("could not load the save process observation suite")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.SaveProcessTests.runner = BUILD / "sdk_save_process"
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.SaveProcessTests)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    output = stream.getvalue()
    if not result.wasSuccessful():
        preserve_output("save-doc-observations-failed", output)
        raise VerificationError("Darwin save documentation observation rerun failed")
    assertions = getattr(module.SaveProcessTests, "assertion_count", 0)
    if not isinstance(assertions, int) or assertions <= 0:
        raise VerificationError("save documentation observation rerun emitted no Python assertions")
    return module, result.testsRun, assertions, output


def save_source_identity(root: Path = ROOT) -> str:
    """Hash the implementation and the complete evidence harness for the save route."""
    source_material = b"".join(
        relative.encode("utf-8") + b"\0" +
        evidence.sha256_file(root / relative).encode("ascii") + b"\n"
        for relative in sorted(SAVE_SOURCE_PATHS))
    return evidence.sha256_bytes(source_material)


def _portable_save_docs_counts(
    document_overrides: dict[str, str] | None = None,
) -> dict[str, int]:
    """Run the shared exact save-contract inventory without Darwin measurements."""
    paths = ("docs/native-save.md", "docs/native-state.md",
             "docs/state-inventory.md", "docs/ownership-and-errors.md")
    documents = {
        path: (document_overrides[path] if document_overrides is not None and path in document_overrides
               else (ROOT / path).read_text(encoding="utf-8"))
        for path in paths
    }
    try:
        manifest = json.loads((ROOT / "tests/fixture/rights-manifest.json").read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise VerificationError("save rights evidence cannot anchor the portable Darwin rows") from error
    rights_assertions = verify_save_fixture_rights(ROOT)
    import importlib.util
    docs_path = ROOT / "tests/sdk/test_save_process.py"
    spec = importlib.util.spec_from_file_location("glueyneo_portable_save_docs", docs_path)
    if spec is None or spec.loader is None:
        raise VerificationError("could not load portable save contract checks")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    source = (ROOT / "src/instance.c").read_text(encoding="utf-8")
    header = (ROOT / "include/glueyneo/glueyneo.h").read_text(encoding="utf-8")
    try:
        contract_counts = module.check_save_contract_docs(
            documents, header, source, manifest, save_source_identity(ROOT))
    except module.SaveDocsError as error:
        raise VerificationError(str(error)) from error
    contract_counts["docs/native-save.md"] += rights_assertions
    return contract_counts


def darwin_filesystem_type(path: Path) -> str:
    """Return the filesystem type for a Darwin path without exposing its device or mount path."""
    df_lines = [line for line in run(["df", "-P", str(path)], timeout=10).stdout.splitlines()
                if line.strip()]
    if len(df_lines) < 2:
        raise VerificationError("Darwin filesystem observation omitted the mounted volume")
    mount_path = df_lines[-1].split()[-1]
    for line in run(["mount"], timeout=10).stdout.splitlines():
        _, separator, attributes = line.strip().partition(f" on {mount_path} (")
        if separator and attributes.endswith(")"):
            filesystem = attributes[:-1].split(",", 1)[0].strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]+", filesystem):
                break
            return filesystem.upper()
    raise VerificationError("Darwin filesystem observation could not resolve the mounted volume type")


def require_save_evidence_identity_stable(
    source_before: str, source_after: str,
    rights_before: str, rights_after: str,
) -> None:
    if source_before != source_after:
        raise VerificationError("save implementation or assertion sources changed during the suite")
    if rights_before != rights_after:
        raise VerificationError("save rights manifest changed during the suite")


def suite_save() -> dict[str, Any]:
    """Run exact native save coverage and qualify the reference host only on Darwin."""
    started = time.monotonic()
    cold_build_seconds = ensure_debug_build()
    identity = evidence.current_identity(ROOT)
    source_identity = save_source_identity(ROOT)
    rights_identity = evidence.sha256_file(ROOT / "tests/fixture/rights-manifest.json")
    host_supported = sys.platform == "darwin"
    result = run([
        "ctest", "--preset", "sdk-debug", "--verbose", "--output-on-failure",
        "--no-tests=error", "--parallel", str(MAX_WORKERS),
        "-R", "^sdk_save_(api|receipts|lifecycle|registration|process|host_faults|recovery)$",
    ], timeout=900)
    observed = validate_save_ctest_output(
        result.stdout, host_supported=host_supported, identity=identity)

    host_measurements: dict[str, Any] = {
        "host_qualification": observed["host_qualification"],
        "unsupported_host_cases": observed["unsupported_host_cases"],
    }
    if host_supported:
        (observation_module, docs_replay_tests, docs_replay_assertions,
         docs_replay_output) = _run_save_docs_observations()
        observations = observation_module.DOC_OBSERVATIONS
        if docs_replay_tests <= 0 or docs_replay_assertions <= 0:
            raise VerificationError("save documentation observation rerun selected no tests")
        compiler = identity.get("compiler", {})
        if not isinstance(compiler, dict) or not compiler.get("id") or not compiler.get("version"):
            raise VerificationError("save suite identity omitted compiler id/version")
        filesystem = darwin_filesystem_type(ROOT)
        host_trace = str(observations.get("host_stage_trace", ""))
        if "file-fullfsync" not in host_trace or "directory-fsync" not in host_trace:
            raise VerificationError("save host observation omitted the tested file/directory sync stages")
        fault_cases = observations.get("host_fault_matrix", [])
        if len(fault_cases) != 18:
            raise VerificationError("save host observation omitted the 18-case fault matrix")
        observations.update({
            "host_identity": f"macOS {platform.mac_ver()[0]} / Darwin {platform.release()} / {filesystem}",
            "save_source_identity_sha256": source_identity,
            "guest_fixture_source_sha256": evidence.sha256_file(
                ROOT / "tests/fixture/public_save_guest.c"),
            "build_identity": f"{compiler['id']} {compiler['version']}; Debug; SDK sanitizer NONE",
            "supported_sync_operations": "F_FULLFSYNC, checked file close, atomic rename, directory fsync, and directory close",
            "host_fault_cases": "18 (9 syscall stages × first-create and A-to-B replacement)",
            "unsupported_host_protocol": "Linux/Windows native save subset only; host commit protocol unsupported",
            "host_qualification": "qualified",
            "suite_critical_path_seconds": round(time.monotonic() - started, 6),
        })
        doc_counts = observation_module.check_save_docs(
            ROOT, observations, require_measured=True)
        if not doc_counts or any(not isinstance(count, int) or count <= 0
                                 for count in doc_counts.values()):
            raise VerificationError("save docs omitted a positive direct assertion count")
        docs_output_sha256 = evidence.sha256_bytes(docs_replay_output.encode("utf-8"))
        host_measurements.update({
            "host_identity": observations["host_identity"],
            "save_source_identity_sha256": observations["save_source_identity_sha256"],
            "guest_fixture_source_sha256": observations["guest_fixture_source_sha256"],
            "build_identity": observations["build_identity"],
            "supported_sync_operations": observations["supported_sync_operations"],
            "host_fault_cases": observations["host_fault_cases"],
            "interruption_cases": len(observations["recovery_kill_cases"]),
            "host_stage_trace": observations["host_stage_trace"],
            "docs_observation_tests": docs_replay_tests,
            "docs_observation_assertions": docs_replay_assertions,
        })
    else:
        doc_counts = _portable_save_docs_counts()
        docs_replay_tests = 0
        docs_output_sha256 = ""

    final_identity = evidence.current_identity(ROOT)
    if any(identity.get(field) != final_identity.get(field) for field in
           ("source_revision", "relevant_source_sha256", "working_tree_dirty")):
        raise VerificationError("relevant source changed during the save suite")
    require_save_evidence_identity_stable(
        source_identity, save_source_identity(ROOT),
        rights_identity, evidence.sha256_file(ROOT / "tests/fixture/rights-manifest.json"))
    return {
        "suite": "save", "outcome": "pass", "label": SUITE_LABELS["save"],
        "ctest_cases": observed["cases"], "cases": observed["cases"],
        "assertions": observed["assertions"], "named_tests": observed["named_tests"],
        "per_case_assertions": observed["per_case_assertions"],
        "host_qualification": observed["host_qualification"],
        "unsupported_host_cases": observed["unsupported_host_cases"],
        "host_measurements": host_measurements,
        "save_source_identity_sha256": source_identity,
        "save_rights_manifest_sha256": rights_identity,
        "save_source_files": list(SAVE_SOURCE_PATHS),
        "docs_assertions": doc_counts,
        "docs_assertion_count": sum(doc_counts.values()),
        "docs_observation_tests": docs_replay_tests,
        "docs_observation_assertions": docs_replay_assertions if host_supported else 0,
        "docs_observation_test_count": docs_replay_tests,
        "docs_observation_output_sha256": docs_output_sha256,
        "identity": identity, "cold_build_seconds": cold_build_seconds,
        "critical_path_seconds": round(time.monotonic() - started, 6),
        "output_sha256": preserve_output("save", result.stdout),
    }


def suite_frontend() -> dict[str, Any]:
    """Build the owned-debug adapter and run only the recurring public frontend boundary."""
    started = time.monotonic()
    source_identity = frontend_source_identity(ROOT)
    configure_started = time.monotonic()
    configure = run(["cmake", "--preset", "owned-debug"], timeout=300)
    configure_seconds = round(time.monotonic() - configure_started, 6)
    build_started = time.monotonic()
    build = run(["cmake", "--build", "--preset", "owned-debug"], timeout=900)
    build_seconds = round(time.monotonic() - build_started, 6)
    build_dir = ROOT / "build/owned-debug"
    inventory_result = run(["ctest", "--test-dir", str(build_dir), "--show-only=json-v1"], timeout=30)
    try:
        inventory = json.loads(inventory_result.stdout)
    except json.JSONDecodeError as error:
        raise VerificationError("frontend CTest membership output is malformed JSON") from error
    registration = validate_frontend_ctest_registration(inventory)
    require_frontend_evidence_identity_stable(source_identity, frontend_source_identity(ROOT))

    registration_started = time.monotonic()
    registration_result = run([
        sys.executable, "tests/libretro/test_frontend_registration.py",
        "--build-dir", str(build_dir), "--mode", "registration",
    ], timeout=180)
    registration_seconds = round(time.monotonic() - registration_started, 6)
    registration_rows = re.findall(r"(?m)^FRONTEND_REGISTRATION_RESULT (\{.*\})$",
                                   registration_result.stdout)
    if len(registration_rows) != 1:
        raise VerificationError("frontend registration controls omitted their positive result receipt")
    try:
        registration_counts = json.loads(registration_rows[0])
    except json.JSONDecodeError as error:
        raise VerificationError("frontend registration result receipt is malformed") from error
    if (not isinstance(registration_counts, dict) or
            not isinstance(registration_counts.get("tests"), int) or registration_counts["tests"] <= 0 or
            not isinstance(registration_counts.get("assertions"), int) or registration_counts["assertions"] <= 0):
        raise VerificationError("frontend registration controls emitted no positive denominator")

    ctest_started = time.monotonic()
    ctest = run([
        "ctest", "--preset", "owned-debug", "--verbose", "--output-on-failure",
        "--no-tests=error", "-R", FRONTEND_CTEST_REGEX,
    ], timeout=900)
    ctest_seconds = round(time.monotonic() - ctest_started, 6)
    observed = validate_frontend_ctest_output(ctest.stdout)

    exports_started = time.monotonic()
    exports = run([sys.executable, "tests/consumers/test_exports.py"], timeout=120)
    exports_seconds = round(time.monotonic() - exports_started, 6)
    export_match = re.search(r"(?m)^Ran (\d+) tests? in [\d.]+s$", exports.stdout)
    if (export_match is None or int(export_match.group(1)) <= 0 or
            not re.search(r"(?m)^OK(?: \(.*\))?$", exports.stdout)):
        raise VerificationError("frontend public export controls omitted a passing positive denominator")
    export_tests = int(export_match.group(1))

    identity = evidence.current_identity(ROOT, "build/owned-debug")
    require_frontend_evidence_identity_stable(source_identity, frontend_source_identity(ROOT))
    return {
        "suite": "frontend", "outcome": "pass", "identity": identity,
        "frontend_source_identity_sha256": source_identity,
        "ctest_cases": observed["cases"], "named_tests": observed["named_tests"],
        "registration_inventory": registration,
        "registration_tests": registration_counts["tests"],
        "registration_assertions": registration_counts["assertions"],
        "public_export_tests": export_tests,
        "cases": observed["cases"] + export_tests,
        "assertions": registration_counts["assertions"] + export_tests,
        "critical_path_seconds": round(time.monotonic() - started, 6),
        "stage_seconds": {"configure": configure_seconds, "build": build_seconds,
                          "registration": registration_seconds, "ctest": ctest_seconds,
                          "public_exports": exports_seconds},
        "output_sha256": preserve_output("frontend-ctest", ctest.stdout),
        "registration_output_sha256": evidence.sha256_bytes(registration_result.stdout.encode("utf-8")),
        "exports_output_sha256": evidence.sha256_bytes(exports.stdout.encode("utf-8")),
        "configure_output_sha256": evidence.sha256_bytes(configure.stdout.encode("utf-8")),
        "build_output_sha256": evidence.sha256_bytes(build.stdout.encode("utf-8")),
    }


def suite_ci_policy() -> dict[str, Any]:
    results = []
    for test in ("tests/workflow/test_ci_policy.py", "tests/sdk/test_matrix_evidence.py"):
        output = run([sys.executable, test], timeout=60).stdout
        if "PASS:" not in output:
            raise VerificationError(f"CI policy control omitted positive marker: {Path(test).name}")
        results.append({"test": test, "outcome": "pass"})
    return {"suite": "ci-policy", "outcome": "pass", "lane_execution_count": len(results),
            "assertion_count": len(results), "tests": results}


def suite_public_content() -> dict[str, Any]:
    output = run([sys.executable, "tests/workflow/test_public_content.py"], timeout=60).stdout
    match = re.search(r"(?m)^Ran (\d+) tests? in [\d.]+s$", output)
    if match is None or int(match.group(1)) <= 0 or "OK" not in output.splitlines()[-1:]:
        raise VerificationError("public-content controls omitted a positive unittest denominator")
    report_path = ROOT / "build/verify-sdk/public-content.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    result = run([sys.executable, "tools/public_content.py", "--root", str(ROOT),
                  "--history-revision=--all", "--json", str(report_path)], timeout=300)
    report = evidence.load_canonical_json(report_path.read_bytes(), label="public-content report")
    if result.returncode != 0 or report.get("outcome") != "pass":
        raise VerificationError("public-content scan failed")
    counts = report.get("counts", {})
    return {"suite": "public-content", "outcome": "pass", "lane_execution_count": 1,
            "assertion_count": sum(value for value in counts.values() if isinstance(value, int)),
            "control_cases": int(match.group(1)),
            "report_sha256": evidence.sha256_file(report_path), "coverage": report.get("coverage")}


def suite_release_consumer() -> dict[str, Any]:
    output = run([sys.executable, "tests/consumers/test_release_consumer.py"], timeout=1800).stdout
    match = re.search(r"(?m)^Ran (\d+) tests? in [\d.]+s$", output)
    if match is None or int(match.group(1)) <= 0 or "OK" not in output.splitlines()[-1:]:
        raise VerificationError("release-consumer suite omitted a positive unittest denominator")
    return {"suite": "release-consumer", "outcome": "pass", "cases": int(match.group(1)),
            "assertion_count": int(match.group(1)), "output_sha256": evidence.sha256_bytes(output.encode())}


def suite_release_recovery() -> dict[str, Any]:
    output = run([sys.executable, "-m", "unittest", "discover", "-s", "tests/workflow",
                  "-p", "test_release_*.py"], timeout=60).stdout
    match = re.search(r"(?m)^Ran (\d+) tests? in [\d.]+s$", output)
    if match is None or int(match.group(1)) <= 0 or "OK" not in output.splitlines()[-1:]:
        raise VerificationError("release-recovery suite omitted a positive unittest denominator")
    return {"suite": "release-recovery", "outcome": "pass", "cases": int(match.group(1)),
            "assertion_count": int(match.group(1)), "output_sha256": evidence.sha256_bytes(output.encode())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("evidence", "provenance", "baseline", "matrix", "frontend",
                                             "release-consumer", "release-recovery", "ci-policy", "public-content",
                                             "fuzz", "sanitizer", "state", "save", "all"), default="all")
    parser.add_argument("--lane", choices=evidence.REQUIRED_MATRIX_LANES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    start = time.monotonic()
    try:
        if args.suite == "evidence":
            report = suite_evidence()
        elif args.suite == "provenance":
            report = suite_provenance()
        elif args.suite == "baseline":
            report = suite_baseline()
        elif args.suite == "matrix":
            report = suite_matrix()
        elif args.suite == "release-consumer":
            report = suite_release_consumer()
        elif args.suite == "release-recovery":
            report = suite_release_recovery()
        elif args.suite == "ci-policy":
            report = suite_ci_policy()
        elif args.suite == "public-content":
            report = suite_public_content()
        elif args.suite == "fuzz":
            report = suite_fuzz()
        elif args.suite == "sanitizer":
            cold_build_seconds = ensure_debug_build()
            identity = evidence.current_identity(ROOT)
            sanitizers, _ = sanitizer_summary(identity, required_lane=args.lane)
            native_calls = collect_sanitized_audio_calls(sanitizers)
            report = {"suite": "sanitizer", "outcome": sanitizers["outcome"],
                      "identity": identity, "aggregate": {
                          "lane_execution_count": (sanitizers["attempted_tests"] + native_calls["ctest_cases"] +
                                                   sanitizers["installed_consumer_cases"]),
                          "assertion_count": sanitizers["assertions"]}, "lanes": sanitizers,
                      "cold_build_seconds": cold_build_seconds}
            report["native_audio_calls"] = native_calls
        elif args.suite == "state":
            report = suite_state()
        elif args.suite == "save":
            report = suite_save()
        elif args.suite == "frontend":
            report = suite_frontend()
        else:
            report = suite_all()
        report["duration_seconds"] = round(time.monotonic() - start, 6)
        if args.suite in {"matrix", "fuzz", "sanitizer"} and args.lane:
            lane = evidence.matrix_lane_from_environment(args.lane, report, report["duration_seconds"], ROOT)
            report["matrix_lane"] = lane
            if lane["outcome"] != "pass":
                report["outcome"] = lane["outcome"]
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(evidence.canonical_bytes(lane))
        evidence.scan_public_value(report)
        print("SDK_VERIFY " + json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0 if report.get("outcome") == "pass" else 1
    except (VerificationError, evidence.EvidenceError, OSError, ValueError, RuntimeError) as error:
        try:
            preserve_output(f"{args.suite}-failed", str(error))
        except OSError:
            pass
        receipt = failure_receipt(args.suite, args.lane, error)
        if args.output:
            try:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(evidence.canonical_bytes(receipt))
            except OSError:
                pass
        print("SDK_VERIFY " + json.dumps(receipt, sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
