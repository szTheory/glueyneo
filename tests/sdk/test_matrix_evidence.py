#!/usr/bin/env python3
"""Adversarial controls for exact platform-matrix evidence."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import sdk_evidence as evidence  # noqa: E402
import verify_sdk  # noqa: E402
import controls  # noqa: E402


def require_rejection(report: dict, reason: str) -> None:
    try:
        evidence.validate_matrix_report(report)
    except evidence.EvidenceError as error:
        assert error.reason == reason, (error.reason, reason)
    else:
        raise AssertionError(f"invalid matrix report accepted; expected {reason}")


def valid_report() -> dict:
    lanes = []
    for lane in evidence.REQUIRED_MATRIX_LANES:
        os_name, compiler_ids, architectures = evidence.MATRIX_LANE_IDENTITY[lane]
        lanes.append({
            "lane": lane,
            "compiler": {"id": next(iter(compiler_ids)), "version": "18.1.8"},
            "sdk": {"name": "SDK", "version": "15.0"},
            "os_image": {"Linux": "ubuntu-24.04", "Darwin": "macos-15", "Windows": "windows-2025"}[os_name],
            "os": os_name,
            "architecture": next(iter(architectures)),
            "configuration": "Debug",
            "source_revision": "a" * 40,
            "working_tree_dirty": False,
            "build_identity": {"cmake": "3.31.6", "generator": "Ninja", "fixture_sha256": "b" * 64},
            "outcome": "pass",
            "assertions": 12,
            "duration_seconds": 3.5,
            "cold_build_seconds": 6.0,
            "runner_id": "local-macos-arm64",
            "runner_minutes": 0.058333,
        })
    return {
        "schema_version": evidence.MATRIX_SCHEMA_VERSION,
        "source_revision": "a" * 40,
        "outcome": "pass",
        "lanes": lanes,
        "cost": {
            "cold_build_seconds": 12.5,
            "critical_path_seconds": 3.5,
            "runner_minutes": 0.35,
            "job_durations_seconds": [3.5, 3.5, 3.5, 3.5, 3.5, 3.5],
            "runner_id": "local-macos-arm64",
        },
    }


def sanitizer_failure_controls() -> None:
    identity = {"source_revision": "a" * 40, "relevant_source_sha256": "b" * 64,
                "compiler": {"id": "Clang", "version": "18.1.8"}}
    passing = {"lane": "asan-ubsan", "preset": "sdk-asan-ubsan", "status": "passed",
               "runtime_status": "passed", "startup_status": "passed",
               "expected_tests": 8, "tests_passed": 8, "sdk_assertions": 80,
               "compiler": {**identity["compiler"], "configuration": "Debug"}}
    native_path = "/" + "home/" + "private-account/runner.c"
    native_failure = (
        "1/2 Test #10: sdk_isolation ...........***Failed    0.01 sec\n"
        "2/2 Test #11: sdk_cold ................   Passed    0.02 sec\n"
        "50% tests passed, 1 tests failed out of 2\n"
        "Total Test time (real) =   0.03 sec\n"
        "The following tests FAILED:\n"
        " 10 - sdk_isolation (Failed)\n"
        "ThreadSanitizer: native child failure at " + native_path + "\n")
    timed_out = (
        "1/2 Test #10: sdk_isolation ...........***Timeout 180.00 sec\n"
        "2/2 Test #11: sdk_cold ................***Timeout 180.00 sec\n"
        "The following tests FAILED:\n"
        " 10 - sdk_isolation (Timeout)\n"
        " 11 - sdk_cold (Timeout)\n")
    variants = [
        ({"status": "failed_runtime", "runtime_status": "failed",
          "error": "runtime CTest suite exited 8", "tests_passed": 1,
          "sdk_assertions": 7, "runtime_log_tail": native_failure.splitlines()},
         native_failure, ["sdk_isolation"], 2, 7, "runtime"),
        ({"status": "failed_runtime", "runtime_status": "failed",
          "error": "runtime CTest suite exited 8", "tests_passed": 0,
          "sdk_assertions": 0, "runtime_log_tail": timed_out.splitlines()},
         timed_out, ["sdk_cold", "sdk_isolation"], 2, 0, "runtime"),
        ({"status": "failed", "startup_status": "failed", "failure_stage": "startup",
          "error": "startup probe returned 66 without a runtime failure signature",
          "tests_passed": 0, "sdk_assertions": 0,
          "startup_log_tail": ["ThreadSanitizer: native failure at " + native_path]},
         "", [], 0, 0, "startup"),
    ]
    for changes, runtime, failed_tests, attempts, failed_assertions, stage in variants:
        failed = {"lane": "tsan", "preset": "sdk-tsan", "expected_tests": 2,
                  "ctest_parallel_jobs": 1, **changes}
        wire = "\n".join("SANITIZER_LANE " + json.dumps(row) for row in (passing, failed))
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            runtime_path = base / "sdk-tsan/sanitizer-control/runtime.log"
            runtime_path.parent.mkdir(parents=True)
            runtime_path.write_text(runtime, encoding="utf-8")
            with mock.patch.object(verify_sdk, "BUILD", base / "sdk-debug"), \
                    mock.patch.object(verify_sdk, "TREE", base / "sdk-debug/verify-sdk"), \
                    mock.patch.object(verify_sdk, "preserve_output", return_value="c" * 64), \
                    mock.patch.object(verify_sdk, "run", return_value=subprocess.CompletedProcess([], 1, wire)):
                result, _ = verify_sdk.sanitizer_summary(identity)
        assert result["outcome"] == "fail"
        assert result["cases"] == 8 and result["assertions"] == 80
        assert result["attempted_tests"] == 8 + attempts
        assert result["reported_failed_assertions"] == failed_assertions
        failure = result["failed"][0]
        assert failure["failed_tests"] == failed_tests and failure["stage"] == stage
        assert failure["source_revision"] == identity["source_revision"]
        assert failure["relevant_source_sha256"] == identity["relevant_source_sha256"]
        assert native_path not in failure["failure_diagnostic"]
        if stage == "startup" or failed_assertions:
            assert "ThreadSanitizer" in failure["failure_diagnostic"]
            assert "[private-path-redacted]" in failure["failure_diagnostic"]
    # Exercise the native supervisor's partial CTest counts without running a
    # native sanitizer or relying on a particular host's runtime availability.
    startup = 'SANITIZER_STARTUP ' + json.dumps({
        "outcome": "pass", "lane": "tsan", "startup_checks": 17,
        "sanitizer": "THREAD", "compiler": "Clang 18.1.8"})
    with tempfile.TemporaryDirectory() as directory, \
            mock.patch.object(controls, "__file__", str(Path(directory) / "tests/sdk/controls.py")), \
            mock.patch.object(controls, "cache_values", return_value={"GLUEYNEO_SDK_SANITIZER": "THREAD"}), \
            mock.patch.object(controls, "verify_target_scoped_flags", return_value=(True, "verified")), \
            mock.patch.object(controls, "run_logged", side_effect=[
                (0, 0.01, None, ""), (0, 0.01, None, ""),
                (0, 0.01, None, startup), (8, 0.03, None, native_failure)]):
        supervised = controls.sanitizer_lane("sdk-tsan", "tsan", "THREAD", "-fsanitize=thread", "^sdk_(isolation|cold)$")
    assert supervised["status"] == "failed_runtime" and supervised["failure_stage"] == "runtime"
    assert supervised["tests_attempted"] == 2 and supervised["tests_passed"] == 1
    assert supervised["failed_tests"] == ["sdk_isolation"]


def mvs_lane_controls() -> None:
    names = sorted(verify_sdk.CTEST_CASES["mvs"])
    identity = {"source_revision": "a" * 40,
                "relevant_source_sha256": "b" * 64}

    def output_for(observed: list[str], denominator: int | None = None,
                   percent: int = 100) -> str:
        lines = [f"Start {index}: {name}" for index, name in enumerate(observed, 1)]
        total = len(observed) if denominator is None else denominator
        lines.append(f"{percent}% tests passed out of {total}")
        return "\n".join(lines)

    def collect(output: str, returncode: int = 0) -> dict:
        with mock.patch.object(verify_sdk, "run", return_value=subprocess.CompletedProcess([], returncode, output, "")), \
             mock.patch.object(verify_sdk, "preserve_output", return_value="c" * 64):
            lane, _ = verify_sdk.collect_ctest_lane("mvs", identity)
            return lane

    lane = collect(output_for(names))
    assert lane["ctest_cases"] == 7 and lane["named_tests"] == names
    assert lane["source_revision"] == identity["source_revision"]
    verify_sdk.validate_mvs_lane(lane, identity)

    for observed, denominator, percent, returncode in (
            (names[:-1], 6, 100, 0),
            (names, 0, 100, 0),
            ([*names[:-1], "mvs_renamed"], 7, 100, 0),
            (names, 7, 85, 1)):
        try:
            collect(output_for(observed, denominator, percent), returncode)
        except verify_sdk.VerificationError:
            pass
        else:
            raise AssertionError("MVS CTest collector accepted omitted, zero, renamed, or failed evidence")

    stale = dict(lane)
    stale["relevant_source_sha256"] = "d" * 64
    try:
        verify_sdk.validate_mvs_lane(stale, identity)
    except verify_sdk.VerificationError:
        pass
    else:
        raise AssertionError("MVS lane accepted a stale relevant-source digest")


class MvsLaneTests(unittest.TestCase):
    def test_mvs_lane_registered_exact_inventory(self) -> None:
        expected = {
            "mvs_synthetic_trace", "mvs_media_contract", "mvs_import_contract",
            "mvs_import_mutation", "mvs_callback_contract", "mvs_boot_checkpoint",
            "mvs_import_fuzz_corpus",
        }
        self.assertEqual(verify_sdk.CTEST_CASES.get("mvs"), expected)


def main() -> int:
    mvs_lane_controls()
    expected_mvs_sources = {
        "tools/mvs/mvs_import.c", "tools/mvs/qualify_local_boot.py",
        "tools/mvs/mvs_qualify.c", "src/mvs/mvs_bus.c",
        "src/libretro/libretro_core.c", "experiments/owned_cpu/cpu.c",
        "tests/mvs/test_mvs.c", "tests/mvs/test_mvs_qualification.py",
        "tests/mvs/fuzz_import.c", "tests/libretro/retroarch_smoke.py",
        "tests/libretro/test_retroarch_smoke.py", "CMakeLists.txt",
        "docs/mvs-media.md",
    }
    assert expected_mvs_sources.issubset(set(evidence.RELEVANT_FILES))
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "tools/mvs/mvs_import.c"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"first source revision")
        with mock.patch.object(evidence, "RELEVANT_FILES", ("tools/mvs/mvs_import.c",)):
            before = evidence.relevant_source_rows(root)
            source.write_bytes(b"second source revision")
            after = evidence.relevant_source_rows(root)
        assert evidence.sha256_bytes(evidence.canonical_bytes(before)) != \
               evidence.sha256_bytes(evidence.canonical_bytes(after))
    # Exercise the collector's actual Windows artifact lookup without claiming
    # that these synthetic bytes are a native Windows runtime qualification.
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        build = root / "build/sdk-debug"
        build.mkdir(parents=True)
        (root / "experiments/owned_cpu").mkdir(parents=True)
        (root / "experiments/owned_cpu/cpu.c").write_bytes(b"synthetic source")
        manifest = root / evidence.MANIFEST_PATH
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(b"synthetic manifest")
        for name in ("glueyneo.lib", "glueyneo_test.lib", "glueyneo-diagnostic.exe"):
            (build / name).write_bytes(name.encode())
        with mock.patch.object(evidence.sys, "platform", "win32"), \
             mock.patch.object(evidence.shutil, "which", return_value=None), \
             mock.patch.object(evidence, "relevant_source_rows", return_value=[{"path": "synthetic.c", "sha256": "a" * 64, "bytes": 1}]), \
             mock.patch.object(evidence, "_git", return_value=""), \
             mock.patch.object(evidence, "_run", return_value="synthetic version"):
            identity = evidence.public_source_identity(root)
            assert {row["path"] for row in identity["runtime_artifacts"]} == {
                "glueyneo.lib", "glueyneo_test.lib", "glueyneo-diagnostic.exe"}
            for row in identity["runtime_artifacts"]:
                assert row["sha256"] == evidence.sha256_file(build / row["path"])
            (build / "glueyneo-diagnostic.exe").unlink()
            try:
                evidence.public_source_identity(root)
            except evidence.EvidenceError as error:
                assert error.reason == "missing-artifact"
            else:
                raise AssertionError("missing Windows runner accepted as built evidence")
    report = valid_report()
    evidence.validate_matrix_report(report)

    mutation = copy.deepcopy(report)
    mutation["lanes"][0]["outcome"] = "pass"
    mutation["lanes"][0]["assertions"] = 0
    require_rejection(mutation, "matrix-zero-assertions")

    mutation = copy.deepcopy(report)
    mutation["lanes"].pop()
    require_rejection(mutation, "matrix-missing-lane")

    mutation = copy.deepcopy(report)
    mutation["lanes"][1]["outcome"] = "pass"
    mutation["lanes"][1]["source_revision"] = "c" * 40
    require_rejection(mutation, "matrix-revision-mismatch")

    mutation = copy.deepcopy(report)
    mutation["lanes"][2]["duration_seconds"] = 0
    require_rejection(mutation, "matrix-invalid-duration")

    mutation = copy.deepcopy(report)
    mutation["lanes"][3]["outcome"] = "pass"
    mutation["lanes"][3]["compiler"]["version"] = "unknown"
    require_rejection(mutation, "matrix-identity-missing")

    mutation = copy.deepcopy(report)
    mutation["lanes"][1]["compiler"]["id"] = "Clang"
    require_rejection(mutation, "matrix-lane-identity-mismatch")

    mutation = copy.deepcopy(report)
    mutation["lanes"][0]["working_tree_dirty"] = True
    require_rejection(mutation, "matrix-dirty-source")

    mutation = copy.deepcopy(report)
    mutation["cost"]["runner_minutes"] = 99
    require_rejection(mutation, "matrix-cost-mismatch")

    mutation = copy.deepcopy(report)
    mutation["lanes"][0]["outcome"] = "unknown"
    mutation["lanes"][0]["reason"] = "Hosted lane has not run locally"
    mutation["lanes"][0]["assertions"] = 0
    mutation["outcome"] = "unknown"
    evidence.validate_matrix_report(mutation)

    sanitizer_failure_controls()
    print("PASS: matrix evidence positive identity, outcome, count, timing, and cost controls")
    print("PASS: sanitizer non-timeout, timeout, and startup failures preserve identity and excluded counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
