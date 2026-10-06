#!/usr/bin/env python3
"""Fail-closed provenance and machine-readable evidence helpers for the SDK."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path("fixtures/diagnostic/manifest.json")
EVIDENCE_PATH = Path("evidence/sdk/verification.json")
UNITY_PIN = "b6763fbd9cedfacaa89e2ad9fd00d615a234e355"
UNITY_FILES = {
    "third_party/unity/src/unity.c": "a6cc4b143075a03317d72c760b5ed67a4a12eeda1242f575464ad23f34042275",
    "third_party/unity/src/unity.h": "b30ba4db1e0be1a1f6c862d359d73c91025a114977e41d3dad17103363804334",
    "third_party/unity/src/unity_internals.h": "35bffad23ebc533977291e7a848c646027513572268fbfa9bd03d5ec21ee818a",
    "third_party/unity/LICENSE.txt": "ec6cf55f05ba2aa538b9677b2481b9ac14a87c63594fce8a0677d4f71c583980",
}
FIXTURES = {
    "a": {
        "file": "build/sdk-debug/diagnostic-original-a.bin",
        "sha256": "495eb195089d0ee7e73f4090514980b47a5fd4a55869d9e7f46376bce1646948",
        "output_sha256": "e0cb8ba07f599ed85a8217d196f577e539cddbba86f2c930da0ed5f468a806bf",
        "values": (10, 0x1237, 1),
    },
    "b": {
        "file": "build/sdk-debug/diagnostic-original-b.bin",
        "sha256": "be1d769bc7c89530a5e09ac60f8cd89858454b0ae604dd0fe506dcd52b154855",
        "output_sha256": "b551afb0fd32171001a3155599f3ee51521a95b7994b4f94fdbb1861790c0cfb",
        "values": (16, 0x2348, 1),
    },
}
OUTCOMES = {"pass", "fail", "skipped", "unsupported", "unknown"}
IDENTITY_FIELDS = {
    "source_revision", "relevant_source_sha256", "working_tree_dirty",
    "owned_backend_sha256", "unity_pin", "unity_files", "fixture_manifest_sha256",
    "fixture_sha256", "expected_output_sha256", "runtime_artifacts",
    "compiler", "cmake", "generator", "sdk", "os", "architecture",
    "configuration", "build_flags", "host_class",
}

BASELINE_SCHEMA_VERSION = 1
BASELINE_WORKLOAD_ID = "diagnostic-original-a-172-cycles"
BASELINE_EXECUTION_RUNS_PER_SAMPLE = 32
BASELINE_INPUT_SHA256 = FIXTURES["a"]["sha256"]
BASELINE_OUTPUT_SHA256 = FIXTURES["a"]["output_sha256"]
BASELINE_EXPECTED_OUTPUT = {
    "arithmetic_result": 10,
    "initialized_result": 0x1237,
    "bss_result": 1,
    "ready": 1,
    "requested_cycles": 172,
    "elapsed_cycles": 172,
    "overshoot_cycles": 0,
    "instructions": 12,
    "terminal_pc": 0x12E,
    "stop_reason": 1,
}

RELEVANT_FILES = (
    "CMakeLists.txt", "CMakePresets.json", "cmake/GlueyneoConfig.cmake.in",
    "include/glueyneo/glueyneo.h", "src/instance.c", "src/sdk_private.h",
    "experiments/owned_cpu/cpu.c", "experiments/owned_cpu/cpu.h",
    "tests/sdk/guest_fixture.c", "tests/sdk/guest_fixture.h",
    "tests/sdk/test_sdk.c", "tests/sdk/test_support.h", "tests/sdk/controls.py",
    "tests/sdk/ORACLE.md", "tests/fuzz/sdk_mutation.c", "tests/fuzz/regressions.json",
    "tests/fuzz/minimize.py", "tests/consumers/CMakeLists.txt",
    "tests/consumers/check_package.py", "tests/consumers/header.cpp",
    "tools/diagnostic/main.c", "tools/sdk_evidence.py", "tools/verify_sdk.py",
    "fixtures/diagnostic/manifest.json",
    "docs/evidence-schema.md", "docs/ownership-and-errors.md", "docs/testing.md",
    "README.md", "tools/sdk_baseline.py", "third_party/unity/src/unity.c", "third_party/unity/src/unity.h",
    "third_party/unity/src/unity_internals.h", "third_party/unity/LICENSE.txt",
    "third_party/unity/PROVENANCE.md",
)

PRIVACY_PATTERNS = (
    re.compile(r"(?i)(?:^|[\s\"'=])/(?:Users|home|private/var|var/folders)/[^\s\"']+"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?i)\b(?:serial|machine_id|hostname)\s*[:=]\s*[^\s,}]+"),
)


class EvidenceError(ValueError):
    """A stable, named rejection reason used by the mutation controls."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def require(condition: bool, reason: str, message: str) -> None:
    if not condition:
        raise EvidenceError(reason, message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError as error:
        raise EvidenceError("missing-input", f"required evidence input is unavailable: {path.name}") from error


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate-key", f"duplicate object key: {key}")
        result[key] = value
    return result


def load_canonical_json(data: bytes, *, label: str = "record") -> Any:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except EvidenceError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError("malformed-json", f"{label} is malformed or truncated JSON") from error
    require(data == canonical_bytes(value), "noncanonical-json", f"{label} is not canonical sorted JSON")
    return value


def _run(argv: list[str], *, timeout: int = 20) -> str:
    try:
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EvidenceError("identity-unavailable", f"could not inspect required build identity: {argv[0]}") from error
    require(result.returncode == 0, "identity-unavailable", f"identity command failed: {Path(argv[0]).name}")
    return result.stdout.strip()


def _git(*args: str) -> str:
    return _run(["git", *args])


def _cache_value(cache: Path, name: str, fallback: str) -> str:
    if not cache.is_file():
        return fallback
    pattern = re.compile(rf"^{re.escape(name)}:[^=]*=(.*)$", re.MULTILINE)
    match = pattern.search(cache.read_text(encoding="utf-8", errors="replace"))
    return match.group(1).strip() if match else fallback


def _cmake_generated_value(build_dir: Path, name: str, fallback: str) -> str:
    generated = sorted((build_dir / "CMakeFiles").glob("*/CMakeCCompiler.cmake"))
    if not generated:
        return fallback
    text = generated[-1].read_text(encoding="utf-8", errors="replace")
    match = re.search(rf'^set\({re.escape(name)} "([^"]*)"\)$', text, re.MULTILINE)
    return match.group(1) if match else fallback


def relevant_source_rows(root: Path = ROOT) -> list[dict[str, Any]]:
    rows = []
    for relative in sorted(RELEVANT_FILES):
        path = root / relative
        require(path.is_file(), "missing-identity-row", f"required identity file is missing: {relative}")
        rows.append({"path": relative, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    require(rows and [r["path"] for r in rows] == sorted({r["path"] for r in rows}),
            "identity-order", "identity paths must be unique and sorted")
    return rows


def public_source_identity(root: Path = ROOT,
                           build_relative: str = "build/sdk-debug") -> dict[str, Any]:
    rows = relevant_source_rows(root)
    relevant_digest = sha256_bytes(canonical_bytes(rows))
    dirty = bool(_git("status", "--porcelain", "--untracked-files=all", "--", *RELEVANT_FILES))
    build_dir = root / build_relative
    cache = build_dir / "CMakeCache.txt"
    compiler_path = _cache_value(cache, "CMAKE_C_COMPILER", "unknown")
    compiler_id = _cmake_generated_value(build_dir, "CMAKE_C_COMPILER_ID", "unknown")
    compiler_version = _cmake_generated_value(build_dir, "CMAKE_C_COMPILER_VERSION", "unknown")
    cmake_version = _run(["cmake", "--version"]).splitlines()[0]
    generator = _cache_value(cache, "CMAKE_GENERATOR", "unknown")
    ninja = shutil.which("ninja")
    generator_version = _run([ninja, "--version"]) if ninja else "unknown"
    runtime_candidates = [build_dir / "libglueyneo.a",
                          build_dir / "libglueyneo_test.a",
                          build_dir / "libglueyneo.dylib",
                          build_dir / "libglueyneo.so"]
    runner = build_dir / "glueyneo-diagnostic"
    runtime = [p for p in runtime_candidates if p.is_file()]
    require(runtime and runner.is_file(), "missing-artifact", "SDK runtime and runner must be built before collecting evidence")
    manifest = root / MANIFEST_PATH
    require(manifest.is_file(), "manifest-missing", "diagnostic fixture manifest is missing")
    fixture_hashes = [FIXTURES[key]["sha256"] for key in ("a", "b")]
    configuration = _cache_value(cache, "CMAKE_BUILD_TYPE", "unknown")
    configuration_flags = _cache_value(cache, "CMAKE_C_FLAGS_" + configuration.upper(), "")
    return {
        "source_revision": _git("rev-parse", "HEAD"),
        "relevant_source_sha256": relevant_digest,
        "working_tree_dirty": dirty,
        "relevant_source_files": rows,
        "owned_backend_sha256": sha256_file(root / "experiments/owned_cpu/cpu.c"),
        "unity_pin": UNITY_PIN,
        "unity_files": [{"path": p, "sha256": h} for p, h in sorted(UNITY_FILES.items())],
        "fixture_manifest_sha256": sha256_file(manifest),
        "fixture_sha256": sha256_bytes(canonical_bytes([{"scenario": key, "sha256": FIXTURES[key]["sha256"]} for key in ("a", "b")])),
        "expected_output_sha256": sha256_bytes(canonical_bytes([{"scenario": key, "sha256": FIXTURES[key]["output_sha256"]} for key in ("a", "b")])),
        "runtime_artifacts": sorted(
            [{"path": p.name, "sha256": sha256_file(p)} for p in runtime] +
            [{"path": runner.name, "sha256": sha256_file(runner)}],
            key=lambda row: row["path"]),
        "compiler": {"path_basename": Path(compiler_path).name, "id": compiler_id, "version": compiler_version},
        "cmake": cmake_version,
        "generator": {"name": generator, "version": generator_version},
        "sdk": {"status": "measured", "version": _run(["xcrun", "--show-sdk-version"]) if sys.platform == "darwin" and shutil.which("xcrun") else "unknown"},
        "os": platform.system() + "-" + (platform.mac_ver()[0].split(".")[0] if sys.platform == "darwin" and platform.mac_ver()[0] else "unknown"),
        "architecture": platform.machine(),
        "configuration": configuration,
        "build_flags": {
            "c_flags": _cache_value(cache, "CMAKE_C_FLAGS", ""),
            "configuration_c_flags": configuration_flags,
            "shared_libraries": _cache_value(cache, "BUILD_SHARED_LIBS", "OFF"),
            "sdk_sanitizer": _cache_value(cache, "GLUEYNEO_SDK_SANITIZER", "NONE"),
        },
        "host_class": ("macOS-" + platform.machine()) if sys.platform == "darwin" else (platform.system() + "-" + platform.machine()),
    }


def scan_public_value(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            scan_public_value(key)
            scan_public_value(child)
    elif isinstance(value, list):
        for child in value:
            scan_public_value(child)
    elif isinstance(value, str):
        for pattern in PRIVACY_PATTERNS:
            require(pattern.search(value) is None, "privacy-contamination", "public evidence contains a personal path or identifier")


def validate_identity(identity: Any, expected: dict[str, Any] | None = None) -> None:
    require(isinstance(identity, dict), "identity-missing", "identity must be an object")
    missing = IDENTITY_FIELDS - identity.keys()
    require(not missing, "identity-missing", "identity fields missing: " + ",".join(sorted(missing)))
    require(bool(identity.get("source_revision")), "identity-missing", "source revision is empty")
    require(re.fullmatch(r"[0-9a-f]{64}", str(identity.get("relevant_source_sha256"))) is not None,
            "identity-malformed", "relevant-source digest is not SHA-256")
    require(isinstance(identity.get("working_tree_dirty"), bool), "identity-malformed", "dirty flag must be boolean")
    require(identity.get("unity_pin") == UNITY_PIN, "identity-mismatch", "Unity immutable pin differs")
    unity_files = identity.get("unity_files")
    require(isinstance(unity_files, list) and unity_files == sorted(unity_files, key=lambda r: r.get("path", "")),
            "identity-order", "Unity identity rows must be present and sorted")
    require({row.get("path"): row.get("sha256") for row in unity_files} == UNITY_FILES,
            "identity-mismatch", "Unity source or notice digest differs")
    rows = identity.get("relevant_source_files")
    require(isinstance(rows, list) and rows and rows == sorted(rows, key=lambda r: r.get("path", "")),
            "identity-order", "relevant source identity rows must be nonempty and sorted")
    paths = [row.get("path") for row in rows]
    require(len(paths) == len(set(paths)), "duplicate-identity-row", "relevant source identity contains duplicate paths")
    require(all(isinstance(row.get("bytes"), int) and row["bytes"] > 0 and re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256"))) for row in rows),
            "identity-malformed", "source identity rows need positive sizes and SHA-256 digests")
    require(sha256_bytes(canonical_bytes(rows)) == identity.get("relevant_source_sha256"),
            "identity-mismatch", "relevant-source digest does not match its canonical file inventory")
    for field in ("owned_backend_sha256", "fixture_manifest_sha256", "fixture_sha256", "expected_output_sha256"):
        require(re.fullmatch(r"[0-9a-f]{64}", str(identity.get(field, ""))) is not None,
                "identity-malformed", f"{field} is not SHA-256")
    artifacts = identity.get("runtime_artifacts")
    require(isinstance(artifacts, list) and artifacts and artifacts == sorted(artifacts, key=lambda r: r.get("path", "")),
            "identity-order", "runtime artifact rows must be nonempty and sorted")
    artifact_paths = [row.get("path") for row in artifacts]
    require(len(artifact_paths) == len(set(artifact_paths)), "duplicate-identity-row", "runtime artifact identity contains duplicate paths")
    require(all(isinstance(path, str) and path and Path(path).name == path and
                re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", "")))
                for row, path in zip(artifacts, artifact_paths)),
            "identity-malformed", "runtime artifact rows require basename and digest")
    if expected is not None:
        require(identity == expected, "identity-mismatch", "record identity does not match current source/build/input identity")


def validate_case_record(record: Any, expected_identity: dict[str, Any] | None = None) -> None:
    require(isinstance(record, dict), "malformed-record", "evidence record must be an object")
    require(record.get("schema_version") == 1, "schema-version", "unsupported evidence schema version")
    status = record.get("outcome")
    require(status in OUTCOMES, "outcome-unknown", "outcome must be one of the five declared values")
    validate_identity(record.get("identity"), expected_identity)
    require(isinstance(record.get("command"), str) and record["command"].strip(), "missing-command", "record command is required")
    failures = record.get("failure_history", [])
    retained = record.get("retained_failures", [])
    require(isinstance(failures, list) and isinstance(retained, list), "malformed-record", "failure history must be arrays")
    require(not failures or len(retained) >= len(failures), "erased-failure", "a prior failed result was omitted from retained evidence")
    if status in {"skipped", "unsupported", "unknown"}:
        require(isinstance(record.get("reason"), str) and record["reason"].strip(), "missing-reason", "non-pass result needs an explicit reason")
    cases = record.get("cases")
    require(isinstance(cases, list), "malformed-record", "cases must be an array")
    if not cases:
        require(status != "pass", "zero-cases", "passing evidence needs at least one executed named case")
        require(record.get("case_count") == 0 and record.get("assertion_count") == 0,
                "count-mismatch", "empty non-pass result must have zero case/assertion counts")
        require(isinstance(record.get("reason"), str) and record["reason"].strip(),
                "missing-reason", "empty non-pass result needs an explicit reason")
        scan_public_value(record)
        return
    ids = [case.get("case_id") if isinstance(case, dict) else None for case in cases]
    require(all(isinstance(case_id, str) and case_id for case_id in ids), "malformed-record", "every case needs a stable case_id")
    require(len(ids) == len(set(ids)), "duplicate-case", "case IDs must be unique")
    require(ids == sorted(ids), "case-order", "case rows must be sorted by case_id")
    assertions = 0
    for case in cases:
        require(case.get("outcome") in OUTCOMES, "outcome-unknown", "case outcome must preserve the five-value vocabulary")
        count = case.get("assertions")
        require(isinstance(count, int) and count >= 0, "invalid-count", "case assertion count must be a nonnegative integer")
        if case["outcome"] == "pass":
            require(count > 0, "zero-assertions", "passing behavioral case needs positive assertion count")
            require("expected" in case and "observed" in case, "missing-observation", "passing case requires expected and observed values")
            require(case["expected"] == case["observed"], "outcome-mismatch", "passing case differs from expected observations")
        if case["outcome"] in {"skipped", "unsupported", "unknown"}:
            require(isinstance(case.get("reason"), str) and case["reason"].strip(), "missing-reason", "non-pass outcomes require a reason")
        assertions += count
    require(record.get("case_count") == len(cases), "count-mismatch", "case_count does not match executed named cases")
    require(record.get("assertion_count") == assertions,
            "count-mismatch", "assertion_count does not match named cases")
    if status == "pass":
        require(assertions > 0, "zero-assertions", "passing evidence needs positive executed assertions")
    require(status != "pass" or all(case["outcome"] == "pass" for case in cases),
            "outcome-mismatch", "record cannot pass while a named case is not passing")
    scan_public_value(record)


def _positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _sample_summary(samples: list[int]) -> dict[str, int]:
    ordered = sorted(samples)
    minimum, maximum = ordered[0], ordered[-1]
    median = ordered[len(ordered) // 2]
    return {
        "median_ns": median,
        "minimum_ns": minimum,
        "maximum_ns": maximum,
        "range_ns": maximum - minimum,
        "spread_basis_points": ((maximum - minimum) * 10000) // median,
    }


def baseline_output_sha256(observed: dict[str, Any]) -> str:
    return sha256_bytes(struct.pack(
        ">IIIQQQQII", observed["arithmetic_result"],
        observed["initialized_result"], observed["bss_result"],
        observed["requested_cycles"], observed["elapsed_cycles"],
        observed["overshoot_cycles"], observed["instructions"],
        observed["terminal_pc"], observed["stop_reason"]))


def validate_baseline_record(record: Any,
                             expected_identity: dict[str, Any] | None = None) -> None:
    """Validate retained raw measurements against their exact fixed workload."""
    require(isinstance(record, dict), "malformed-baseline", "baseline must be an object")
    require(record.get("schema_version") == BASELINE_SCHEMA_VERSION,
            "schema-version", "unsupported baseline schema version")
    require(record.get("suite") == "baseline", "baseline-suite", "record is not the baseline suite")
    outcome = record.get("outcome")
    require(outcome in OUTCOMES, "outcome-unknown", "baseline outcome is outside the five-value vocabulary")
    if outcome != "pass":
        require(isinstance(record.get("reason"), str) and record["reason"].strip(),
                "missing-reason", "non-passing baseline needs an explicit reason")
    failures = record.get("failure_history", [])
    retained = record.get("retained_failures", [])
    require(isinstance(failures, list) and isinstance(retained, list),
            "malformed-baseline", "baseline failure history must be arrays")
    require(not failures or len(retained) >= len(failures), "erased-failure",
            "a previous baseline failure is missing from retained evidence")
    for failure in failures:
        require(isinstance(failure, dict) and failure.get("outcome") == "fail" and
                isinstance(failure.get("reason"), str) and failure["reason"].strip(),
                "malformed-baseline", "failure history entries need a named failure outcome")
    identity = record.get("identity")
    validate_identity(identity, expected_identity)
    require(identity.get("configuration") == "Release", "configuration-mismatch",
            "baseline identity must name the Release configuration")
    require(identity.get("build_flags", {}).get("sdk_sanitizer") == "NONE",
            "configuration-mismatch", "baseline must use the unsanitized Release runtime")

    workload = record.get("workload")
    require(isinstance(workload, dict), "workload-mismatch", "fixed workload identity is missing")
    require(workload.get("workload_id") == BASELINE_WORKLOAD_ID and
            workload.get("configuration") == "Release" and
            workload.get("input_sha256") == BASELINE_INPUT_SHA256 and
            workload.get("output_sha256") == BASELINE_OUTPUT_SHA256 and
            workload.get("expected_output") == BASELINE_EXPECTED_OUTPUT,
            "workload-mismatch", "baseline workload or expected output differs from the fixed original scenario")
    observed_output = workload.get("observed_output")
    require(observed_output == BASELINE_EXPECTED_OUTPUT and
            all(type(value) is int for value in observed_output.values()),
            "workload-mismatch", "measured run did not observe the exact fixed diagnostic output")
    observed_output_digest = baseline_output_sha256(observed_output)
    require(observed_output_digest == BASELINE_OUTPUT_SHA256 and
            workload.get("observed_output_sha256") == observed_output_digest,
            "workload-mismatch", "observed output digest differs from the explicit big-endian result tuple")
    require(workload.get("guest_cycles") == 172,
            "workload-mismatch", "baseline guest-cycle request differs from 172")

    protocol = record.get("protocol")
    require(isinstance(protocol, dict), "missing-raw-samples", "sampling protocol is missing")
    require(protocol.get("warmup_samples") == 3,
            "insufficient-samples", "baseline must perform exactly three warmups")
    raw = record.get("raw_samples")
    require(isinstance(raw, dict), "missing-raw-samples", "raw sample arrays are missing")
    samples_by_kind: dict[str, list[int]] = {}
    for kind in ("load_ns", "load_batch_ns", "execution_ns", "execution_batch_ns", "cold_build_ns"):
        samples = raw.get(kind)
        require(isinstance(samples, list), "missing-raw-samples", f"raw {kind} samples are missing")
        require(all(_positive_integer(sample) for sample in samples),
                "invalid-measurement", f"raw {kind} samples must be positive integer nanoseconds")
        samples_by_kind[kind] = samples
    load_samples = samples_by_kind["load_ns"]
    load_batches = samples_by_kind["load_batch_ns"]
    execution_samples = samples_by_kind["execution_ns"]
    execution_batches = samples_by_kind["execution_batch_ns"]
    cold_samples = samples_by_kind["cold_build_ns"]
    require(isinstance(protocol.get("retained_samples"), int) and
            not isinstance(protocol.get("retained_samples"), bool) and
            protocol["retained_samples"] >= 30 and len(load_samples) >= 30 and
            len(execution_samples) >= 30 and len(cold_samples) >= 3,
            "insufficient-samples", "at least thirty load/execution and three cold-build samples are required")
    require(protocol.get("cold_build_configuration") == {
        "build_type": "Release", "generator": "Ninja", "BUILD_TESTING": False,
        "GLUEYNEO_BUILD_TESTS": False, "GLUEYNEO_SDK_SANITIZER": "NONE",
        "GLUEYNEO_CPU_EXPERIMENT": False,
        "GLUEYNEO_OWNED_CPU_EXPERIMENT": False,
    }, "configuration-mismatch", "cold build configuration differs from the named protocol")
    require(protocol.get("load_runs_per_sample") == BASELINE_EXECUTION_RUNS_PER_SAMPLE and
            len(load_batches) == len(load_samples) and
            all(batch // BASELINE_EXECUTION_RUNS_PER_SAMPLE == average
                for batch, average in zip(load_batches, load_samples)),
            "summary-mismatch", "load averages must match 32-load raw batch intervals")
    require(protocol.get("execution_runs_per_sample") == BASELINE_EXECUTION_RUNS_PER_SAMPLE and
            len(execution_batches) == len(execution_samples) and
            all(batch // BASELINE_EXECUTION_RUNS_PER_SAMPLE == average
                for batch, average in zip(execution_batches, execution_samples)),
            "summary-mismatch", "execution averages must match 32-run raw batch intervals")
    require(len(load_samples) == len(execution_samples) and
            protocol.get("retained_samples") == len(load_samples),
            "insufficient-samples", "at least thirty paired load/execution samples are required")
    cold_ids = protocol.get("cold_build_ids")
    require(isinstance(cold_ids, list) and len(cold_ids) == len(cold_samples) and
            len(cold_samples) >= 3 and len(cold_ids) == len(set(cold_ids)) and
            all(isinstance(item, str) and item for item in cold_ids),
            "insufficient-samples", "at least three distinct cold-build directories are required")
    timer = record.get("timer")
    require(isinstance(timer, dict) and timer.get("clock") == "CLOCK_MONOTONIC" and
            _positive_integer(timer.get("resolution_ns")),
            "timer-resolution", "monotonic timer resolution must be measured and positive")

    summaries = record.get("summaries")
    require(isinstance(summaries, dict), "summary-mismatch", "uncertainty summaries are missing")
    for kind, samples in samples_by_kind.items():
        require(summaries.get(kind) == _sample_summary(samples),
                "summary-mismatch", f"{kind} summary does not match raw retained samples")

    discarded = record.get("discarded_samples")
    require(isinstance(discarded, list), "discarded-sample", "discarded sample inventory must be an array")
    for row in discarded:
        require(isinstance(row, dict) and isinstance(row.get("kind"), str) and
                _positive_integer(row.get("original_ns")) and
                isinstance(row.get("reason"), str) and row["reason"].strip(),
                "discarded-sample", "every discarded observation needs its value and explanation")
    require(outcome != "pass" or not discarded,
            "discarded-sample", "passing baseline may not discard any observation")

    memory = record.get("memory")
    require(isinstance(memory, dict), "memory-unsupported", "memory result must be explicit")
    memory_status = memory.get("status")
    require(memory_status in {"measured", "unsupported"}, "memory-unsupported",
            "memory status must be measured or unsupported")
    if memory_status == "unsupported":
        require(isinstance(memory.get("reason"), str) and memory["reason"].strip(),
                "memory-unsupported", "unsupported memory result needs a reason")
        require(outcome != "pass", "memory-unsupported", "unsupported owned-memory measurement cannot pass the required baseline")
    else:
        memory_samples = memory.get("samples")
        require(isinstance(memory_samples, list) and len(memory_samples) == len(load_samples),
                "memory-unsupported", "allocator memory counters must bind every retained workload sample")
        for row in memory_samples:
            require(isinstance(row, dict) and _positive_integer(row.get("allocations")) and
                    _positive_integer(row.get("bytes")) and _positive_integer(row.get("attempts")),
                    "invalid-measurement", "allocator count, bytes, and attempts must be positive")
        require(memory.get("allocator") == "gn_test_allocator" and
                memory.get("scope") == "successful first load plus exact diagnostic run" and
                memory.get("current_allocations") == memory_samples[-1]["allocations"] and
                memory.get("current_bytes") == memory_samples[-1]["bytes"] and
                memory.get("peak_allocations") == max(row["allocations"] for row in memory_samples) and
                memory.get("peak_bytes") == max(row["bytes"] for row in memory_samples),
                "summary-mismatch", "allocator current/peak summaries differ from measured counters")
    host_rss = record.get("host_rss")
    require(isinstance(host_rss, dict) and host_rss.get("status") in {"measured", "unsupported"},
            "memory-unsupported", "host RSS must be explicitly measured or unsupported")
    if host_rss.get("status") == "unsupported":
        require(isinstance(host_rss.get("reason"), str) and host_rss["reason"].strip(),
                "memory-unsupported", "unsupported host RSS needs a reason")

    measurement_tool = record.get("measurement_tool")
    require(isinstance(measurement_tool, dict) and
            all(re.fullmatch(r"[0-9a-f]{64}", str(measurement_tool.get(field, "")))
                for field in ("source_sha256", "binary_sha256")) and
            measurement_tool.get("compiler") == identity.get("compiler"),
            "identity-mismatch", "measurement helper identity/compiler is incomplete or mismatched")
    require(isinstance(record.get("command"), str) and record["command"].strip(),
            "missing-command", "baseline collection command is required")
    scan_public_value(record)


def validate_manifest_document(manifest: Any) -> None:
    require(isinstance(manifest, dict) and manifest.get("schema_version") == 1,
            "manifest-schema", "fixture manifest has unsupported shape/version")
    require(bool(manifest.get("manifest_id")), "manifest-empty", "fixture manifest identity is empty")
    rights = manifest.get("rights")
    require(isinstance(rights, dict) and rights.get("spdx") == "MIT" and
            rights.get("original_work") is True and rights.get("commercial_media_included") is False and
            rights.get("notice_file") == "LICENSE", "manifest-notice", "fixture rights/notice declaration is incomplete")
    require(manifest.get("firmware_required") is False, "manifest-firmware", "original diagnostic must explicitly require no firmware")
    generation = manifest.get("generation")
    require(isinstance(generation, dict) and all(generation.get(key) for key in
            ("recipe", "interface", "command", "configuration", "source_revision")),
            "manifest-empty", "fixture generation identity is incomplete")
    require(re.fullmatch(r"[0-9a-f]{40,64}", str(manifest.get("source_revision", ""))) is not None,
            "manifest-identity", "manifest source revision is malformed")
    oracle = manifest.get("oracle")
    require(isinstance(oracle, dict) and oracle.get("references"),
            "manifest-ancestry", "fixture oracle references are empty")
    require(oracle.get("primary_sources"), "manifest-ancestry", "fixture primary sources are empty")
    require(oracle.get("ancestry"), "manifest-ancestry", "fixture test-oracle ancestry is empty")
    sources = manifest.get("source_inputs")
    require(isinstance(sources, list) and sources and sources == sorted(sources, key=lambda r: r.get("path", "")),
            "manifest-empty", "fixture source inputs are empty or noncanonical")
    source_paths = [row.get("path") for row in sources]
    require(len(source_paths) == len(set(source_paths)), "manifest-identity", "manifest source identities are duplicated")
    require(set(source_paths) == {"tests/sdk/guest_fixture.c", "tests/sdk/guest_fixture.h", "tests/sdk/ORACLE.md"},
            "manifest-identity", "manifest does not bind the full original recipe, interface, and oracle")
    require(all(re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", ""))) and
                isinstance(row.get("bytes"), int) and row["bytes"] > 0 for row in sources),
            "manifest-identity", "manifest source rows need positive size and SHA-256")
    dependencies = manifest.get("dependencies")
    require(isinstance(dependencies, list) and len(dependencies) == 1, "manifest-dependency", "manifest must identify the pinned test-only dependency")
    dependency = dependencies[0]
    require(dependency.get("name") == "Unity" and dependency.get("revision") == UNITY_PIN and
            dependency.get("license") == "MIT", "manifest-dependency", "Unity manifest pin or notice is not immutable")
    unity_records = dependency.get("files")
    require(isinstance(unity_records, list) and unity_records == sorted(unity_records, key=lambda r: r.get("path", "")),
            "manifest-order", "dependency source and notice rows must be sorted")
    require({row.get("path"): row.get("sha256") for row in unity_records} == UNITY_FILES,
            "manifest-dependency", "Unity source/license digest inventory is incomplete")
    fixtures = manifest.get("fixtures")
    require(isinstance(fixtures, list) and fixtures, "manifest-empty", "fixture manifest contains no generated outputs")
    require(len(fixtures) == 2 and [item.get("scenario") for item in fixtures] == ["a", "b"],
            "manifest-order", "fixture scenarios must include A then B in canonical order")
    for item in fixtures:
        key = item.get("scenario")
        spec = FIXTURES.get(key)
        require(spec is not None, "manifest-fixture", "unknown original fixture scenario")
        require(item.get("bytes") == 522 and item.get("sha256") == spec["sha256"] and
                item.get("layout") == "ROM[512] || RAM_INITIALIZATION[10]" and
                item.get("firmware_required") is False,
                "manifest-fixture", f"fixture {key} digest/length/layout differs from the original oracle")
        expected_values = [*spec["values"], 172, 172, 0, 12, 0x12e, 1]
        record = struct.pack(">IIIQQQQII", *expected_values)
        expected_output = item.get("expected_output")
        require(len(record) == 52 and sha256_bytes(record) == spec["output_sha256"] and
                isinstance(expected_output, dict) and expected_output.get("encoding") == ">IIIQQQQII" and
                expected_output.get("fields") == ["arithmetic:u32", "initialized:u32", "bss:u32", "requested_cycles:u64", "elapsed_cycles:u64", "overshoot_cycles:u64", "instructions:u64", "terminal_pc:u32", "stop_reason:u32"] and
                expected_output.get("bytes") == 52 and expected_output.get("sha256") == spec["output_sha256"] and
                expected_output.get("values") == expected_values,
                "manifest-output", f"fixture {key} explicit big-endian output tuple differs")
    scan_public_value(manifest)


def verify_manifest(root: Path = ROOT, *, check_artifacts: bool = True,
                    manifest_data: Any | None = None) -> dict[str, Any]:
    path = root / MANIFEST_PATH
    if manifest_data is None:
        require(path.is_file(), "manifest-missing", "fixture manifest is missing")
        manifest = load_canonical_json(path.read_bytes(), label="fixture manifest")
    else:
        manifest = manifest_data
    validate_manifest_document(manifest)
    sources = manifest["source_inputs"]
    fixtures = manifest["fixtures"]
    for row in sources:
        require((root / row["path"]).is_file() and sha256_file(root / row["path"]) == row["sha256"],
                "manifest-source-mismatch", f"manifest source identity mismatch: {row['path']}")
    for relative, expected in UNITY_FILES.items():
        require(sha256_file(root / relative) == expected, "manifest-dependency", f"Unity input changed: {relative}")
    for item in fixtures:
        key = item["scenario"]
        spec = FIXTURES.get(key)
        require(spec is not None, "manifest-fixture", "unknown original fixture scenario")
        require(item.get("bytes") == 522 and item.get("sha256") == spec["sha256"],
                "manifest-fixture", f"fixture {key} digest/length differs from the original oracle")
        if check_artifacts:
            artifact = root / spec["file"]
            require(artifact.is_file() and artifact.stat().st_size == 522 and
                    sha256_file(artifact) == spec["sha256"], "fixture-artifact-mismatch",
                    f"generated scenario {key} bytes do not match the manifest")
    scan_public_value(manifest)
    return manifest


def build_manifest(root: Path = ROOT, source_revision: str | None = None) -> dict[str, Any]:
    recipe = "tests/sdk/guest_fixture.c"
    interface = "tests/sdk/guest_fixture.h"
    sources = [{"path": relative, "sha256": sha256_file(root / relative), "bytes": (root / relative).stat().st_size}
               for relative in sorted((recipe, interface, "tests/sdk/ORACLE.md"))]
    fixtures = []
    for key in ("a", "b"):
        spec = FIXTURES[key]
        path = root / spec["file"]
        require(path.is_file() and path.stat().st_size == 522, "fixture-artifact-mismatch", f"generated fixture {key} is absent or has wrong length")
        digest = sha256_file(path)
        require(digest == spec["sha256"], "fixture-artifact-mismatch", f"generated fixture {key} differs from the independently recorded identity")
        output = struct.pack(">IIIQQQQII", *spec["values"], 172, 172, 0, 12, 0x12e, 1)
        fixtures.append({
            "scenario": key,
            "bytes": 522,
            "sha256": digest,
            "layout": "ROM[512] || RAM_INITIALIZATION[10]",
            "firmware_required": False,
            "expected_output": {"encoding": ">IIIQQQQII", "fields": ["arithmetic:u32", "initialized:u32", "bss:u32", "requested_cycles:u64", "elapsed_cycles:u64", "overshoot_cycles:u64", "instructions:u64", "terminal_pc:u32", "stop_reason:u32"], "bytes": len(output), "sha256": sha256_bytes(output), "values": [*spec["values"], 172, 172, 0, 12, 0x12e, 1]},
        })
    unity = [{"path": p, "sha256": h, "notice": p.endswith("LICENSE.txt")} for p, h in sorted(UNITY_FILES.items())]
    return {
        "schema_version": 1,
        "manifest_id": "glueyneo-original-diagnostic-sdk-v1",
        "rights": {"spdx": "MIT", "notice_file": "LICENSE", "original_work": True, "commercial_media_included": False},
        "firmware_required": False,
        "source_revision": source_revision or _git("rev-parse", "HEAD"),
        "source_inputs": sources,
        "generation": {"recipe": recipe, "interface": interface, "command": "glueyneo-diagnostic --write-fixture <build-local-path> [--scenario-b]", "output_not_committed": True, "configuration": "sdk-debug / Debug", "source_revision": source_revision or _git("rev-parse", "HEAD")},
        "fixtures": fixtures,
        "dependencies": [{"name": "Unity", "license": "MIT", "revision": UNITY_PIN, "source_url": "https://github.com/ThrowTheSwitch/Unity/tree/" + UNITY_PIN, "role": "test-only assertion library; absent from runtime exports", "files": unity}],
        "oracle": {
            "references": ["tests/sdk/ORACLE.md", ".planning/phases/01-cpu-acceptance-experiment/01-VERIFICATION.md"],
            "primary_sources": [
                {"title": "Motorola M68000 Family Programmer's Reference Manual", "edition_date": "1992", "url": "https://www.nxp.com/docs/en/reference-manual/M68000PRM.pdf", "claim": "instruction encodings and CPU-visible results"},
                {"title": "Motorola M68000 8-/16-/32-Bit Microprocessors User's Manual", "edition_date": "1993, ninth edition", "url": "https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf", "claim": "reset and selected instruction timing"},
            ],
            "ancestry": ["Original MIT C recipe", "manual-derived expected instruction effects and timing", "explicit big-endian result tuple", "runner output compared against fixed independent expectations"],
            "limits": ["manuals do not establish Neo Geo board behavior", "callback order is not physical bus evidence", "no original BIOS/game/hardware claim"],
        },
        "notices": {"project": "MIT; see LICENSE", "Unity": "MIT; see third_party/unity/LICENSE.txt and third_party/unity/PROVENANCE.md"},
    }


def write_manifest(root: Path = ROOT) -> dict[str, Any]:
    manifest = build_manifest(root)
    scan_public_value(manifest)
    path = root / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(manifest))
    return manifest


def current_identity(root: Path = ROOT,
                     build_relative: str = "build/sdk-debug") -> dict[str, Any]:
    identity = public_source_identity(root, build_relative)
    manifest = verify_manifest(root)
    # Re-evaluate the manifest after verification and bind both lawful scenarios.
    validate_identity(identity)
    return identity


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write-manifest", action="store_true")
    group.add_argument("--verify-manifest", action="store_true")
    args = parser.parse_args()
    try:
        value = write_manifest() if args.write_manifest else verify_manifest()
        print(json.dumps({"schema_version": 1, "outcome": "pass", "manifest_id": value.get("manifest_id"), "fixtures": len(value.get("fixtures", []))}, sort_keys=True))
    except EvidenceError as error:
        print(json.dumps({"schema_version": 1, "outcome": "fail", "reason": error.reason}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
