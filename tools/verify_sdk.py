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
TREE = BUILD / "verify-sdk/evidence"
LOG_DIR = BUILD / "verify-sdk/logs"
sys.path.insert(0, str(ROOT / "tools"))
import sdk_evidence as evidence  # noqa: E402

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
    "package-build": "sdk-package-build",
    "package-consumers": "sdk-package-consumers",
    "package-docs": "sdk-package-docs",
    "package-capabilities": "sdk-package-capabilities",
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
        raise VerificationError(f"command timed out after {timeout}s: {Path(argv[0]).name}\n{output[-6000:]}") from error
    except OSError as error:
        raise VerificationError(f"could not execute required command: {Path(argv[0]).name}") from error
    if check and result.returncode != 0:
        raise VerificationError(f"command failed ({result.returncode}): {' '.join(argv)}\n{result.stdout[-8000:]}")
    return result


def preserve_output(lane: str, output: str) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{lane}.log"
    path.write_text(output, encoding="utf-8")
    return evidence.sha256_file(path)


def ensure_debug_build() -> None:
    run(["cmake", "--preset", "sdk-debug"], timeout=180)
    run(["cmake", "--build", "--preset", "sdk-debug", "--parallel", str(MAX_WORKERS)], timeout=300)
    runner = BUILD / "glueyneo-diagnostic"
    if not runner.is_file():
        raise VerificationError("sdk-debug build did not produce the diagnostic runner")
    fixture_b = BUILD / "diagnostic-original-b.bin"
    run([str(runner), "--write-fixture", str(fixture_b), "--scenario-b"], timeout=20)
    run([str(runner), "--check-fixture", str(fixture_b), "--scenario-b"], timeout=20)


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
    rows = [(key, name) for key, name in EVIDENCE_CASES.items()]
    lines = ["# Generated by tools/verify_sdk.py; do not edit."]
    names = []
    for key, test_name in rows:
        name = test_name
        names.append(name)
        command = [sys.executable, str(tests_path), "--case", key]
        args = " ".join(_bracket(item) for item in command)
        lines.append(f"add_test({name} {args})")
        lines.append(f"set_tests_properties({name} PROPERTIES LABELS [=[sdk-evidence;sdk-controls]=] TIMEOUT 30)")
    (directory / "CTestTestfile.cmake").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory, names


def run_generated_evidence_controls() -> tuple[int, int, list[dict[str, Any]], str]:
    directory, expected_tests = write_generated_ctest_tree()
    result = run(["ctest", "--test-dir", str(directory), "--verbose", "--output-on-failure",
                  "--no-tests=error", "--parallel", str(MAX_WORKERS), "-L", "sdk-evidence"], timeout=120)
    output = result.stdout
    test_names = re.findall(r"(?m)^\s*Start\s+\d+:\s*(\S+)\s*$", output)
    if len(test_names) != len(expected_tests) or set(test_names) != set(expected_tests):
        raise VerificationError(f"generated evidence CTest selection mismatch: expected {len(expected_tests)} named controls, observed {len(test_names)}")
    records = []
    for match in re.finditer(r"(?m)^(?:\d+: )?SDK_EVIDENCE_CASE (\{.*\})$", output):
        records.append(json.loads(match.group(1)))
    expected_case_ids = set(EVIDENCE_CASE_IDS.values())
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


def run_existing_ctest(label: str, lane: str) -> tuple[int, str]:
    result = run(["ctest", "--preset", "sdk-debug", "--verbose", "--output-on-failure",
                  "--no-tests=error", "--parallel", str(MAX_WORKERS), "-L", label], timeout=600)
    output = result.stdout
    total = ctest_denominator(output)
    if total is None:
        raise VerificationError(f"{lane} produced no CTest denominator")
    if total <= 0:
        raise VerificationError(f"{lane} CTest result was not all passing with a positive denominator")
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
    runner = BUILD / "glueyneo-diagnostic"
    verify_fixture_runner(runner, "a")
    verify_fixture_runner(runner, "b")
    count, output = run_existing_ctest("sdk-provenance", "provenance")
    output_hash = preserve_output("provenance", output)
    identity = evidence.current_identity(ROOT)
    return {"suite": "provenance", "outcome": "pass", "cases": count + 2,
            "assertions": count + 2, "output_sha256": output_hash,
            "identity": identity, "manifest_id": manifest["manifest_id"],
            "fixture_checks": 2}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("evidence", "provenance", "baseline", "all"), default="all")
    args = parser.parse_args()
    start = time.monotonic()
    try:
        if args.suite == "evidence":
            report = suite_evidence()
        elif args.suite == "provenance":
            report = suite_provenance()
        elif args.suite == "baseline":
            raise VerificationError("baseline lane is not implemented yet")
        else:
            raise VerificationError("aggregate gate is not complete until the measurement and acceptance lanes are implemented")
        report["duration_seconds"] = round(time.monotonic() - start, 6)
        evidence.scan_public_value(report)
        print("SDK_VERIFY " + json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0
    except (VerificationError, evidence.EvidenceError, OSError, ValueError) as error:
        print("SDK_VERIFY " + json.dumps({"suite": args.suite, "outcome": "fail",
              "reason": getattr(error, "reason", "verification-failed")}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
