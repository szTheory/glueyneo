#!/usr/bin/env python3
"""Adversarial controls for exact platform-matrix evidence."""

from __future__ import annotations

import copy
import json
import re
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
               "expected_tests": 13, "tests_passed": 13, "sdk_assertions": 100,
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
        failed = {"lane": "tsan", "preset": "sdk-tsan", "expected_tests": 3,
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
        assert result["cases"] == 13 and result["assertions"] == 100
        assert result["attempted_tests"] == 13 + attempts
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
        supervised = controls.sanitizer_lane("sdk-tsan", "tsan", "THREAD", "-fsanitize=thread", "^sdk_(isolation|cold|state_isolation)$")
    assert supervised["status"] == "failed_runtime" and supervised["failure_stage"] == "runtime"
    assert supervised["tests_attempted"] == 2 and supervised["tests_passed"] == 1
    assert supervised["failed_tests"] == ["sdk_isolation"]

    identity_record = {
        "suite": "sdk-state", "outcome": "pass", "cases": 1,
        "assertions": 67,
        "identity": {"sanitizer": "THREAD"},
    }
    isolation_record = {
        "suite": "isolation", "outcome": "pass", "cases": 1,
        "assertions": 11,
        "identity": {"sanitizer": "THREAD"},
    }
    cold_record = {
        "suite": "cold", "outcome": "pass", "cases": 1,
        "assertions": 19,
        "identity": {"sanitizer": "THREAD"},
    }
    ctest_output = (
        "Start 35: sdk_state_isolation\n"
        "1/3 Test #35: sdk_state_isolation ............ Passed 0.01 sec\n"
        "Start 51: sdk_isolation\n"
        "2/3 Test #51: sdk_isolation ................. Passed 0.01 sec\n"
        "Start 52: sdk_cold\n"
        "3/3 Test #52: sdk_cold ...................... Passed 0.01 sec\n"
        "100% tests passed, 0 tests failed out of 3\n"
        "Total Test time (real) = 0.03 sec\n")
    last_test_log = ("SDK_RESULT " + json.dumps(identity_record) + "\n" +
                     "SDK_CONTROL_RESULT " + json.dumps(isolation_record) + "\n" +
                     "SDK_CONTROL_RESULT " + json.dumps(cold_record) + "\n")
    startup = "SANITIZER_STARTUP " + json.dumps({
        "outcome": "pass", "lane": "tsan", "startup_checks": 18,
        "sanitizer": "THREAD",
        "compiler": "AppleClang 21.0.0.21000101"})
    original_run_logged = controls.run_logged

    def run_logged_with_positive_ctest(command, log_path, sample_rss=False,
                                       timeout=600.0):
        if command[0] == "cmake" and "--preset" in command:
            output = ""
        elif command[0] == "cmake" and "--build" in command:
            output = ""
        elif "--startup-probe" in command:
            output = startup
        else:
            output = ctest_output
            test_log = (Path(controls.__file__).resolve().parents[2] /
                        "build/sdk-tsan/Testing/Temporary/LastTest.log")
            test_log.parent.mkdir(parents=True, exist_ok=True)
            test_log.write_text(last_test_log, encoding="utf-8")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(output, encoding="utf-8")
        return 0, 0.01, None, output

    with tempfile.TemporaryDirectory() as directory, \
            mock.patch.object(controls, "__file__", str(Path(directory) / "tests/sdk/controls.py")), \
            mock.patch.object(controls, "cache_values", return_value={
                "GLUEYNEO_SDK_SANITIZER": "THREAD",
                "CMAKE_C_COMPILER_ID": "AppleClang",
                "CMAKE_C_COMPILER_VERSION": "21.0.0.21000101",
                "CMAKE_BUILD_TYPE": "Debug"}), \
            mock.patch.object(controls, "verify_target_scoped_flags",
                              return_value=(True, "verified")), \
            mock.patch.object(controls, "run_logged",
                              side_effect=run_logged_with_positive_ctest):
        supervised = controls.sanitizer_lane(
            "sdk-tsan", "tsan", "THREAD", "-fsanitize=thread",
            "^sdk_(isolation|cold|state_isolation)$")
    controls.run_logged = original_run_logged
    assert supervised["status"] == "passed", supervised
    assert supervised["tests_passed"] == 3
    assert supervised["sdk_assertions"] == 97


def mvs_lane_controls() -> None:
    names = sorted(verify_sdk.CTEST_CASES["mvs"])
    importer = evidence.mvs_importer_identity(
        verify_sdk.ROOT, verify_sdk.BUILD.relative_to(verify_sdk.ROOT).as_posix())
    identity = {"source_revision": "a" * 40,
                "relevant_source_sha256": "b" * 64,
                "mvs_importer": importer}

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
    assert lane["ctest_cases"] == 21 and len(names) == 21 and lane["named_tests"] == names
    assert lane["source_revision"] == identity["source_revision"]
    verify_sdk.validate_mvs_lane(lane, identity)

    without_failure_diagnostics = [
        name for name in names if name != "mvs_failure_diagnostics"]
    try:
        collect(output_for(without_failure_diagnostics))
    except verify_sdk.VerificationError:
        pass
    else:
        raise AssertionError("MVS CTest collector accepted the lane without mvs_failure_diagnostics")

    for observed, denominator, percent, returncode in (
            (names[:-1], len(names) - 1, 100, 0),
            (names, 0, 100, 0),
            ([*names[:-1], "mvs_renamed"], len(names), 100, 0),
            (names, len(names), 85, 1)):
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
    def test_build_matrix_report_rejects_nonobject_rows_before_sorting(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests/sdk/test_evidence.py"),
             "--case", "row_shape_matrix_aggregator"],
            cwd=ROOT, capture_output=True, text=True, check=False)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        rows = [line.removeprefix("SDK_EVIDENCE_CASE ") for line in output.splitlines()
                if line.startswith("SDK_EVIDENCE_CASE ")]
        self.assertEqual(len(rows), 1, output)
        case = json.loads(rows[0])
        self.assertEqual(case["case_id"], "evidence.row-shape-matrix-aggregator")
        self.assertEqual(case["outcome"], "pass")
        expected = {"container": "matrix-lanes-missing",
                    "row": "matrix-lane-malformed",
                    "empty": "matrix-revision-missing",
                    "singleton": "matrix-missing-lane"}
        self.assertEqual(case["expected"], expected)
        self.assertEqual(case["observed"], expected)

    def test_build_matrix_report_preserves_valid_order_and_duplicate_control(self) -> None:
        original = valid_report()["lanes"]
        reversed_rows = list(reversed(original))
        before = evidence.canonical_bytes(reversed_rows)
        report = evidence.build_matrix_report(reversed_rows)
        self.assertEqual([row["lane"] for row in report["lanes"]],
                         sorted(row["lane"] for row in original))
        self.assertEqual(evidence.canonical_bytes(reversed_rows), before)
        evidence.validate_matrix_report(report)

        duplicate_rows = [*reversed_rows, dict(reversed_rows[0])]
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.build_matrix_report(duplicate_rows)
        self.assertEqual(caught.exception.reason, "matrix-lane-duplicate")

    def test_validate_matrix_report_keeps_its_nonobject_row_guard(self) -> None:
        non_objects = [None, [], "row", 1, 1.5, True]
        positions = ((0, "first"), (2, "middle"), (-1, "last"))
        for value in non_objects:
            for position, label in positions:
                with self.subTest(value=value, position=label):
                    report = valid_report()
                    report["lanes"][position] = value
                    with self.assertRaises(evidence.EvidenceError) as caught:
                        evidence.validate_matrix_report(report)
                    self.assertEqual(caught.exception.reason, "matrix-lane-malformed")

    def test_board_partitions_preserve_exact_subcheck_coverage(self) -> None:
        # Structural harness oracle: retain the 30 pre-partition subchecks once.
        # Their executable assertions, rather than this registration check,
        # supply the board behavior evidence.
        source = (ROOT / "tests/mvs/test_mvs.c").read_text()
        cmake = (ROOT / "CMakeLists.txt").read_text()
        expected = {
            "check_mvs_pcm_public_api", "check_start_input", "check_irq_timing",
            "check_logical_frame_budget", "check_failed_frame_prefix",
            "check_io_status", "check_mvs_controls_guest", "check_calendar",
            "check_calendar_timing", "check_calendar_interrupt_noops",
            "check_calendar_resume_commands", "check_status_a",
            "check_controller_select_without_host_input", "check_sound_command_reply",
            "check_disabled_nmi_pending_then_enable", "check_sound_bus_boundary",
            "check_sound_clock_and_sources", "check_sound_ym_board",
            "check_sound_selector_reset", "check_status_b", "check_output3_latch",
            "check_output2_latch", "check_single_cartridge_slot_selection",
            "check_p2_banking_guest_write_and_instance_reset",
            "check_p2_banking_guest_byte_lanes", "check_mslugx_protection_guest",
            "check_mslugx_protection_instance_isolation", "check_mvs_fixed_renderer",
            "check_mvs_sprite_renderer", "check_mvs_sprite_instance_isolation",
        }
        groups = ("core", "io", "calendar", "sound", "cartridge", "video")

        def calls(text: str, group: str) -> list[str]:
            body = re.search(
                rf"static void check_board_{group}\([^{{]+\) \{{(.*?)\n\}}",
                text, re.S)
            self.assertIsNotNone(body, group)
            return re.findall(r"\b(check_\w+)\(", body.group(1))

        def require_coverage(text: str) -> None:
            flattened = [name for group in groups for name in calls(text, group)]
            self.assertEqual(set(flattened), expected)
            self.assertEqual(len(flattened), len(expected))

        require_coverage(source)
        call = "    check_mvs_pcm_public_api(bundle, size);"
        with self.assertRaises(AssertionError):
            require_coverage(source.replace(call, "", 1))
        with self.assertRaises(AssertionError):
            require_coverage(source.replace(call, call + "\n" + call, 1))
        self.assertCountEqual(calls(source, "behavior"),
                              [f"check_board_{group}" for group in groups])
        for group in groups:
            case = "behavior" if group == "core" else group
            self.assertIn(
                f"add_test(NAME mvs_board_{case} COMMAND mvs_test --board-{group})",
                cmake)
            self.assertIn(f"mvs_board_{case}", verify_sdk.CTEST_CASES["mvs"])
            self.assertIn(
                f'strcmp(argv[1], "--board-{group}") == 0) {{\n'
                f'        check_board_{group}(bundle, bundle_size);', source)

    def test_mvs_lane_registered_exact_inventory(self) -> None:
        expected = {
            "mvs_synthetic_trace", "mvs_media_contract", "mvs_import_contract",
            "mvs_import_mutation", "mvs_callback_contract", "mvs_boot_checkpoint",
            "mvs_attract_predicate", "mvs_board_behavior",
            "mvs_board_io", "mvs_board_calendar", "mvs_board_sound",
            "mvs_board_cartridge", "mvs_board_video",
            "mvs_import_fuzz_corpus", "mvs_failure_diagnostics",
            "mvs_import_max_horizon", "mvs_input_observations", "public_sound_fixture",
            "sdk_sound_reference", "libretro_audio_contract", "mvs_audio_call_corpus",
        }
        self.assertEqual(verify_sdk.CTEST_CASES.get("mvs"), expected)

    def test_native_call_lane_requires_success_and_rejection_counts(self) -> None:
        text = "Start 1: mvs_audio_call_corpus\nStart 2: mvs_import_fuzz_corpus\n100% tests passed out of 2\n"
        for success, rejected in ((0, 14), (30, 0), (30, 14)):
            with self.subTest(success=success, rejected=rejected), \
                    mock.patch.object(verify_sdk, "run", return_value=subprocess.CompletedProcess(
                        [], 0, text+f"MVS_AUDIO_CALLS success={success} rejected={rejected} seed=51a7c0de\n", "")), \
                    mock.patch.object(verify_sdk, "preserve_output", return_value="a"*64):
                if success and rejected:
                    self.assertEqual(verify_sdk.collect_audio_call_lane("sdk-debug")["ctest_cases"], 2)
                else:
                    with self.assertRaises(verify_sdk.VerificationError):
                        verify_sdk.collect_audio_call_lane("sdk-debug")

    def test_native_call_sanitizer_uses_actual_asan_status(self) -> None:
        with mock.patch.object(verify_sdk, "collect_audio_call_lane", return_value={"outcome":"pass"}) as run:
            result=verify_sdk.collect_sanitized_audio_calls({"outcome":"pass", "lanes":[
                {"lane":"asan-ubsan", "status":"unsupported", "unsupported_reason":"runtime absent"}]})
            self.assertEqual(result["outcome"],"unsupported")
            run.assert_not_called()
            result=verify_sdk.collect_sanitized_audio_calls({"outcome":"pass", "lanes":[
                {"lane":"asan-ubsan", "status":"passed"}]})
            self.assertEqual(result["outcome"],"pass")
            run.assert_called_once_with("sdk-asan-ubsan")

    def test_mvs_lane_rejects_omitted_failure_diagnostics(self) -> None:
        names = sorted(verify_sdk.CTEST_CASES["mvs"])
        identity = {"source_revision": "a" * 40,
                    "relevant_source_sha256": "b" * 64,
                    "mvs_importer": {"basename": "mvs_importer", "sha256": "c" * 64,
                                     "source_sha256": "d" * 64,
                                     "working_tree_dirty": False}}
        omitted = [name for name in names if name != "mvs_failure_diagnostics"]
        output = "\n".join([*(f"Start {index}: {name}"
                               for index, name in enumerate(omitted, 1)),
                            f"100% tests passed out of {len(omitted)}"])
        with mock.patch.object(verify_sdk, "run", return_value=subprocess.CompletedProcess(
                [], 0, output, "")), \
             mock.patch.object(verify_sdk, "preserve_output", return_value="e" * 64):
            with self.assertRaises(verify_sdk.VerificationError):
                verify_sdk.collect_ctest_lane("mvs", identity)

    def test_mvs_lane_requires_matching_importer_identity(self) -> None:
        names = sorted(verify_sdk.CTEST_CASES["mvs"])
        identity = {
            "source_revision": "a" * 40,
            "relevant_source_sha256": "b" * 64,
            "mvs_importer": {
                "basename": "mvs_importer",
                "sha256": "c" * 64,
                "source_sha256": "d" * 64,
                "working_tree_dirty": False,
            },
        }
        lane = {
            "outcome": "pass", "label": "mvs", "ctest_cases": len(names),
            "named_tests": names, "source_revision": identity["source_revision"],
            "relevant_source_sha256": identity["relevant_source_sha256"],
            "output_sha256": "e" * 64,
            "importer_basename": "mvs_importer", "importer_sha256": "c" * 64,
            "importer_source_sha256": "d" * 64,
        }
        verify_sdk.validate_mvs_lane(lane, identity)
        for identity_variant, lane_variant in (
                ({**identity, "mvs_importer": None}, lane),
                (identity, {**lane, "importer_sha256": "f" * 64}),
                (identity, {**lane, "importer_source_sha256": "0" * 64}),
                (identity, {**lane, "importer_basename": "mvs_importer.exe"})):
            with self.subTest(identity=identity_variant.get("mvs_importer"),
                              basename=lane_variant.get("importer_basename")):
                with self.assertRaises(verify_sdk.VerificationError):
                    verify_sdk.validate_mvs_lane(lane_variant, identity_variant)

    def test_debug_build_rebuilds_mvs_importer_before_identity_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory) / "build" / "sdk-debug"
            build.mkdir(parents=True)
            importer = build / ("mvs_importer.exe" if sys.platform == "win32" else "mvs_importer")
            importer.write_bytes(b"same-path substitute")
            runner = build / ("glueyneo-diagnostic.exe" if sys.platform == "win32"
                              else "glueyneo-diagnostic")
            runner.write_bytes(b"synthetic runner")
            importer_absent_during_build: list[bool] = []

            def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                if command[:4] == ["cmake", "--build", "--preset", "sdk-debug"]:
                    importer_absent_during_build.append(not importer.exists())
                    importer.write_bytes(b"rebuilt importer")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch.object(verify_sdk, "BUILD", build), \
                 mock.patch.object(verify_sdk, "run", side_effect=fake_run):
                verify_sdk.ensure_debug_build()

            self.assertEqual(importer_absent_during_build, [True],
                             "a preexisting same-path importer must be removed before rebuilding")
            self.assertEqual(importer.read_bytes(), b"rebuilt importer")

    def test_mvs_importer_source_closure_is_in_sdk_identity(self) -> None:
        expected = {
            "CMakeLists.txt", "CMakePresets.json", "docs/mvs-media.md",
            "tools/mvs/mvs_import.c", "third_party/zlib/LICENSE",
            "third_party/zlib/adler32.c", "third_party/zlib/crc32.c",
            "third_party/zlib/crc32.h", "third_party/zlib/gzguts.h",
            "third_party/zlib/inffast.c", "third_party/zlib/inffast.h",
            "third_party/zlib/inffixed.h", "third_party/zlib/inflate.c",
            "third_party/zlib/inflate.h", "third_party/zlib/inftrees.c",
            "third_party/zlib/inftrees.h", "third_party/zlib/zconf.h",
            "third_party/zlib/zlib.h", "third_party/zlib/zutil.c",
            "third_party/zlib/zutil.h",
        }
        self.assertTrue(expected.issubset(set(evidence.RELEVANT_FILES)))

    def test_replay_and_sound_recipe_mutations_change_identity_and_dirty_flag(self) -> None:
        targets = {"tools/mvs/frontend_replay.py", "tests/libretro/test_frontend_replay.py",
                   "docs/audio-contract.md"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in set(evidence.RELEVANT_FILES) | targets:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("synthetic original source: " + name).encode())
            build = root / "build/sdk-debug"
            build.mkdir(parents=True)
            for name in ("libglueyneo.a", "glueyneo.lib", "glueyneo-diagnostic",
                         "glueyneo-diagnostic.exe", "mvs_importer", "mvs_importer.exe"):
                (build / name).write_bytes(b"synthetic identity-only artifact")
            changed = set()
            def git_output(*args: str, cwd: Path = root) -> str:
                if args[0] == "rev-parse":
                    return "a" * 40
                if args[0] == "status":
                    return "\n".join(" M " + name for name in changed if name in args)
                raise AssertionError(args)
            with mock.patch.object(evidence, "_git", side_effect=git_output), \
                 mock.patch.object(evidence, "_run", return_value="synthetic version"):
                before = evidence.public_source_identity(root)
                self.assertFalse(before["working_tree_dirty"])
                for name in sorted(targets):
                    with self.subTest(source=name):
                        path = root / name
                        original = path.read_bytes()
                        path.write_bytes(original + b"\nsource mutation")
                        changed.add(name)
                        after = evidence.public_source_identity(root)
                        self.assertNotEqual(before["relevant_source_sha256"], after["relevant_source_sha256"])
                        self.assertTrue(after["working_tree_dirty"])
                        path.write_bytes(original)
                        changed.remove(name)

    def test_z80_headers_are_hashed_and_in_dirty_pathspec(self) -> None:
        headers = {"src/chips/z80_candidate.h", "third_party/chips/z80.h"}
        self.assertTrue(headers.issubset(evidence.RELEVANT_FILES))
        rows = evidence.relevant_source_rows(ROOT)
        by_path = {row["path"]: row for row in rows}
        for header in headers:
            self.assertEqual(by_path[header]["sha256"],
                             evidence.sha256_file(ROOT / header))
        # Exercise the actual public collector's Git pathspec. Report dirty
        # only when the mutated header was included in that query.
        for header in headers:
            def git_output(*args: str, cwd: Path = ROOT) -> str:
                if args[0] == "rev-parse":
                    return "a" * 40
                if args[0] == "status":
                    return " M " + header if header in args else ""
                raise AssertionError(args)
            with mock.patch.object(evidence, "_git", side_effect=git_output):
                identity = evidence.public_source_identity(ROOT, "build/owned-debug")
            self.assertTrue(identity["working_tree_dirty"], header)

    def test_public_identity_binds_windows_importer_and_zlib_mutations(self) -> None:
        source_files = set(evidence.MVS_IMPORTER_SOURCE_FILES)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in source_files | {"experiments/owned_cpu/cpu.c"}:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"synthetic source: {relative}".encode())
            manifest = root / evidence.MANIFEST_PATH
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_bytes(b"synthetic manifest")
            build = root / "build/sdk-debug"
            build.mkdir(parents=True)
            for name in ("glueyneo.lib", "glueyneo_test.lib", "glueyneo-diagnostic.exe"):
                (build / name).write_bytes(name.encode())
            importer_path = build / "mvs_importer.exe"
            importer_path.write_bytes(b"synthetic configured importer")
            zlib_header = root / "third_party/zlib/zlib.h"
            original_header = zlib_header.read_bytes()

            def git_output(*args: str, cwd: Path = ROOT) -> str:
                if args[0] == "rev-parse":
                    return "a" * 40
                if args[0] == "status":
                    return "" if zlib_header.read_bytes() == original_header else " M third_party/zlib/zlib.h"
                raise AssertionError(f"unexpected git query: {args[0]}")

            with mock.patch.object(evidence.sys, "platform", "win32"), \
                 mock.patch.object(evidence.shutil, "which", return_value=None), \
                 mock.patch.object(evidence, "RELEVANT_FILES", tuple(sorted(source_files | {"experiments/owned_cpu/cpu.c"}))), \
                 mock.patch.object(evidence, "_git", side_effect=git_output), \
                 mock.patch.object(evidence, "_run", return_value="synthetic version"):
                before = evidence.public_source_identity(root)
                self.assertIn("mvs_importer", before)
                importer = before["mvs_importer"]
                self.assertEqual(importer["basename"], "mvs_importer.exe")
                self.assertEqual(importer["sha256"], evidence.sha256_file(importer_path))
                zlib_header.write_bytes(original_header + b"\nheader mutation")
                after = evidence.public_source_identity(root)

        self.assertNotEqual(before["relevant_source_sha256"], after["relevant_source_sha256"])
        self.assertNotEqual(before["mvs_importer"]["source_sha256"],
                            after["mvs_importer"]["source_sha256"])
        self.assertFalse(before["mvs_importer"]["working_tree_dirty"])
        self.assertTrue(after["mvs_importer"]["working_tree_dirty"])

    def test_mvs_collector_rejects_importer_substitution_during_ctest(self) -> None:
        proof = {"basename": "mvs_importer", "sha256": "a" * 64,
                 "source_sha256": "b" * 64, "working_tree_dirty": False,
                 "source_files": []}
        substituted = {**proof, "sha256": "c" * 64}
        identity = {"source_revision": "d" * 40,
                    "relevant_source_sha256": "e" * 64,
                    "mvs_importer": proof}
        with mock.patch.object(verify_sdk, "run_existing_ctest",
                               return_value=(9, "all named MVS tests passed")), \
             mock.patch.object(verify_sdk, "preserve_output", return_value="f" * 64), \
             mock.patch.object(verify_sdk.evidence, "mvs_importer_identity",
                               side_effect=[proof, substituted], create=True):
            with self.assertRaises(verify_sdk.VerificationError):
                verify_sdk.collect_ctest_lane("mvs", identity)


def main() -> int:
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(MvsLaneTests))
    if not result.wasSuccessful():
        return 1
    mvs_lane_controls()
    expected_mvs_sources = {
        "tools/mvs/mvs_import.c", "tools/mvs/qualify_local_boot.py",
        "tools/mvs/mvs_qualify.c", "src/mvs/mvs_bus.c", "src/mvs/mvs_protocol.c",
        "src/instance.c", "src/sdk_private.h",
        "src/libretro/libretro_core.c", "experiments/owned_cpu/cpu.c",
        "tests/mvs/test_mvs.c", "tests/mvs/test_mvs_qualification.py",
        "tests/mvs/qualification_failure_driver.c",
            "src/chips/ym2610_candidate.cpp", "src/chips/ym2610_candidate.h",
            "third_party/ymfm/src/ymfm_opn.cpp", "third_party/ymfm/NOTICE.md",
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
        for name in ("glueyneo.lib", "glueyneo_test.lib", "glueyneo-diagnostic.exe",
                     "mvs_importer.exe"):
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
