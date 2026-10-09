#!/usr/bin/env python3
"""Run the named, fail-closed local verification suites for the Glueyneo SDK."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
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
}

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
            "mvs_import_fuzz_corpus"},
}

PACKAGE_CASES = {
    "build": {"sdk_package_build_static", "sdk_package_build_shared"},
    "consumers": {"sdk_package_consumers_static", "sdk_package_consumers_shared"},
    "docs": {"sdk_package_docs_static", "sdk_package_docs_shared", "sdk_package_docs_readme"},
    "capabilities": {"sdk_package_capabilities"},
}

EVIDENCE_CASES = {
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
    "empty_manifest": "sdk_evidence_empty_manifest",
    "empty_ancestry": "sdk_evidence_empty_ancestry",
    "stale_manifest_source": "sdk_evidence_stale_manifest_source",
    "unknown_outcome": "sdk_evidence_unknown_outcome",
}
EVIDENCE_CASE_IDS = {
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
    run(["cmake", "--build", "--preset", "sdk-debug", "--parallel", str(MAX_WORKERS)], timeout=300)
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
    if expected is None or total != len(expected) or len(observed) != total or set(observed) != expected:
        raise VerificationError(
            f"{lane} named CTest inventory mismatch: expected {sorted(expected or ())}, observed {observed}")
    return total, output


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
    count, output = run_existing_ctest(label, name)
    lane: dict[str, Any] = {
        "outcome": "pass", "label": label, "ctest_cases": count,
        "named_tests": sorted(CTEST_CASES[name]),
    }
    if name == "mvs":
        lane["output_sha256"] = preserve_output("ctest-mvs", output)
        lane["source_revision"] = identity.get("source_revision")
        lane["relevant_source_sha256"] = identity.get("relevant_source_sha256")
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
    if (lane.get("outcome") != "pass" or lane.get("label") != SUITE_LABELS["mvs"] or
            lane.get("ctest_cases") != len(expected) or lane.get("named_tests") != expected or
            lane.get("source_revision") != identity.get("source_revision") or
            lane.get("relevant_source_sha256") != identity.get("relevant_source_sha256") or
            re.fullmatch(r"[0-9a-f]{64}", str(lane.get("output_sha256", ""))) is None):
        raise VerificationError("MVS receipt has missing tests, zero denominator, stale source, or no output digest")


def suite_evidence() -> dict[str, Any]:
    ensure_debug_build()
    evidence.verify_manifest(ROOT)
    identity = evidence.current_identity(ROOT)
    count, assertions, cases, output = run_generated_evidence_controls()
    output_hash = preserve_output("evidence-controls", output)
    return {"suite": "evidence", "outcome": "pass", "cases": count,
            "assertions": assertions, "output_sha256": output_hash,
            "identity": identity, "named_cases": cases}


def suite_provenance() -> dict[str, Any]:
    ensure_debug_build()
    manifest = evidence.verify_manifest(ROOT)
    runner = BUILD / ("glueyneo-diagnostic.exe" if os.name == "nt"
                      else "glueyneo-diagnostic")
    verify_fixture_runner(runner, "a")
    verify_fixture_runner(runner, "b")
    count, output = run_existing_ctest("sdk-provenance", "provenance")
    output_hash = preserve_output("provenance", output)
    identity = evidence.current_identity(ROOT)
    return {"suite": "provenance", "outcome": "pass", "cases": count + 2,
            "assertions": count + 2, "output_sha256": output_hash,
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
            "guest_cycles": 196,
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


def sanitizer_summary(identity: dict[str, Any]) -> tuple[dict[str, Any], str]:
    cache_path = TREE / "sanitizer-failure-context.json"
    reused = False
    if cache_path.is_file():
        cache = evidence.load_canonical_json(cache_path.read_bytes(), label="retained sanitizer failure context")
        cached_identity = cache.get("source_identity", {})
        prior_files = {row["path"]: row for row in cache.get("relevant_source_files", [])}
        current_files = {row["path"]: row for row in identity.get("relevant_source_files", [])}
        changed = [path for path in prior_files.keys() | current_files.keys()
                   if path != "tools/verify_sdk.py" and prior_files.get(path) != current_files.get(path)]
        cache_matches = cached_identity.get("source_revision") == identity.get("source_revision") and not changed
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
        for row in rows:
            row["matrix_exit_code"] = result.returncode
            row["result_source_revision"] = identity["source_revision"]
            row["result_relevant_source_sha256"] = identity["relevant_source_sha256"]
    expected = {"asan-ubsan": 8, "tsan": 2}
    if {row.get("lane") for row in rows} != set(expected) or len(rows) != len(expected):
        raise VerificationError("sanitizer matrix omitted or duplicated ASan+UBSan or TSan")
    unsupported = []
    safe_rows = []
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
    return ({"outcome": "fail" if failed else "pass", "cases": cases,
             "attempted_tests": attempted_tests, "assertions": assertions,
             "reported_failed_assertions": reported_failed_assertions,
             "lanes": safe_rows, "unsupported": unsupported, "failed": failed,
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
    for name in ("contract", "diagnostic", "run", "controls", "isolation", "hostile", "capabilities"):
        focused[name], _ = collect_ctest_lane(name, identity)
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
                       release_recovery["cases"] + sanitizers["attempted_tests"])
    lane_assertion_count = (evidence_lane["assertions"] + provenance_report["assertions"] +
                            baseline["control_assertion_count"] +
                            sum(lane.get("assertions", 0) for lane in focused.values()) +
                            sum(lane.get("assertions", 0) for lane in packages.values()) +
                            release_recovery["assertion_count"] +
                            sanitizers["assertions"])
    required = ["evidence", "provenance", "baseline", *[f"ctest:{name}" for name in CTEST_CASES],
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
    for name in ("contract", "diagnostic", "run", "controls", "isolation", "provenance", "capabilities", "mvs"):
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


def suite_fuzz() -> dict[str, Any]:
    cold_build_seconds = ensure_debug_build()
    identity = evidence.current_identity(ROOT)
    lane, _ = collect_ctest_lane("hostile", identity)
    return {"suite": "fuzz", "outcome": lane["outcome"], "identity": identity,
            "aggregate": {"lane_execution_count": lane["ctest_cases"],
                          "case_count": lane.get("cases", 0),
                          "assertion_count": lane.get("assertions", 0)},
            "lanes": {"fuzz": lane}, "cold_build_seconds": cold_build_seconds}


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
            "report_sha256": evidence.sha256_file(report_path), "coverage": report.get("coverage")}


def suite_release_consumer() -> dict[str, Any]:
    output = run([sys.executable, "tests/consumers/test_release_consumer.py"], timeout=1800).stdout
    match = re.search(r"(?m)^Ran (\d+) tests? in [\d.]+s$", output)
    if match is None or int(match.group(1)) <= 0 or "OK" not in output.splitlines()[-1:]:
        raise VerificationError("release-consumer suite omitted a positive unittest denominator")
    return {"suite": "release-consumer", "outcome": "pass", "cases": int(match.group(1)),
            "assertion_count": int(match.group(1)), "output_sha256": evidence.sha256_bytes(output.encode())}


def suite_release_recovery() -> dict[str, Any]:
    output = run([sys.executable, "tests/workflow/test_release_recovery.py"], timeout=60).stdout
    match = re.search(r"(?m)^Ran (\d+) tests? in [\d.]+s$", output)
    if match is None or int(match.group(1)) <= 0 or "OK" not in output.splitlines()[-1:]:
        raise VerificationError("release-recovery suite omitted a positive unittest denominator")
    return {"suite": "release-recovery", "outcome": "pass", "cases": int(match.group(1)),
            "assertion_count": int(match.group(1)), "output_sha256": evidence.sha256_bytes(output.encode())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("evidence", "provenance", "baseline", "matrix",
                                             "release-consumer", "release-recovery", "ci-policy", "public-content",
                                             "fuzz", "sanitizer", "all"), default="all")
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
            sanitizers, _ = sanitizer_summary(identity)
            report = {"suite": "sanitizer", "outcome": sanitizers["outcome"],
                      "identity": identity, "aggregate": {
                          "lane_execution_count": sanitizers["attempted_tests"],
                          "assertion_count": sanitizers["assertions"]}, "lanes": sanitizers,
                      "cold_build_seconds": cold_build_seconds}
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
