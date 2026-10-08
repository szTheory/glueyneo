from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import retroarch_smoke as smoke


class ScreenshotFreshnessTests(unittest.TestCase):
    def test_old_screenshot_is_not_selected_for_a_new_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            stale = directory / "stale.png"
            stale.write_bytes(b"old capture")
            prior = smoke.screenshot_snapshot(directory)

            selector = getattr(smoke, "select_fresh_screenshot", None)
            selected = selector(directory, prior) if callable(selector) else None
            self.assertIsNone(selected)

    def test_new_screenshot_is_selected_after_the_prior_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            stale = directory / "stale.png"
            stale.write_bytes(b"old capture")
            prior = smoke.screenshot_snapshot(directory)
            fresh = directory / "fresh.png"
            fresh.write_bytes(b"new capture")
            fresh.touch()

            selector = getattr(smoke, "select_fresh_screenshot", None)
            selected = selector(directory, prior) if callable(selector) else None
            self.assertEqual(selected, fresh)


class DiagnosticTests(unittest.TestCase):
    def test_failure_diagnostic_preserves_stage_exit_and_survival(self) -> None:
        builder = getattr(smoke, "build_diagnostic", None)
        record = builder(
            stage="frontend",
            return_code=-6,
            survived_before_screenshot=False,
            output="RetroArch exited before screenshot (status -6)",
        ) if callable(builder) else {}

        self.assertEqual(record.get("stage"), "frontend")
        self.assertEqual(record.get("return_code"), -6)
        self.assertFalse(record.get("survived_before_screenshot"))
        self.assertIn("status -6", record.get("output", ""))

    def test_diagnostic_output_redacts_user_temp_and_checkout_paths(self) -> None:
        builder = getattr(smoke, "build_diagnostic", None)
        record = builder(
            stage="core-content-load",
            return_code=1,
            survived_before_screenshot=False,
            output="failed /Users/alice/private/game.rom in /private/var/folders/xy/temp and /Users/bob/worktree",
            temporary_root=Path("/private/var/folders/xy/temp"),
        ) if callable(builder) else {}

        serialized = str(record)
        self.assertNotIn("alice", serialized)
        self.assertNotIn("bob", serialized)
        self.assertNotIn("private/game.rom", serialized)
        self.assertNotIn("/private/var/folders/xy/temp", serialized)
        self.assertIn("[user]", serialized)
        self.assertIn("[temporary]", serialized)

    def test_crash_parser_keeps_only_bounded_reason_fields(self) -> None:
        report = """Process: RetroArch [123]
Path: /Users/alice/Applications/RetroArch.app/Contents/MacOS/RetroArch
Exception Type: EXC_CRASH (SIGABRT)
Termination Reason: Namespace DYLD, Code 1 Library not loaded: /Users/alice/private/lib.dylib
Sensitive unrelated line: private capture name
"""

        parser = getattr(smoke, "extract_crash_reason", None)
        reason = parser(report) if callable(parser) else ""

        self.assertIn("EXC_CRASH", reason)
        self.assertIn("DYLD", reason)
        self.assertNotIn("alice", reason)
        self.assertNotIn("private capture", reason)

    def test_crash_parser_reads_macos_ips_json_reason_fields(self) -> None:
        report = "\n".join(
            [
                json.dumps({"app_name": "RetroArch", "procName": "RetroArch"}),
                json.dumps({
                    "exception": {"type": "EXC_CRASH", "signal": "SIGABRT"},
                    "termination": {
                        "namespace": "DYLD", "code": 1,
                        "indicator": "Library not loaded: /Users/alice/private/lib.dylib",
                        "details": "private desktop session detail",
                    },
                }),
            ]
        )

        reason = smoke.extract_crash_reason(report)

        self.assertIn("EXC_CRASH", reason)
        self.assertIn("DYLD", reason)
        self.assertNotIn("alice", reason)
        self.assertNotIn("desktop session", reason)

    def test_crash_parser_extracts_reasons_from_bounded_truncated_ips(self) -> None:
        report = json.dumps({
            "exception": {"type": "EXC_CRASH", "signal": "SIGABRT"},
            "termination": {"namespace": "DYLD", "code": 1, "indicator": "Library not loaded"},
            "large_tail": "x" * (smoke.DIAGNOSTIC_OUTPUT_LIMIT * 2),
        })[:smoke.DIAGNOSTIC_OUTPUT_LIMIT]

        reason = smoke.extract_crash_reason(report)

        self.assertIn("EXC_CRASH", reason)
        self.assertIn("DYLD", reason)

    def test_diagnostic_tail_is_bounded(self) -> None:
        record = smoke.build_diagnostic(
            stage="frontend", return_code=1, survived_before_screenshot=False,
            output="x" * (smoke.DIAGNOSTIC_OUTPUT_LIMIT + 100),
        )

        self.assertLessEqual(len(record["output"]), smoke.DIAGNOSTIC_OUTPUT_LIMIT)
        self.assertIn("diagnostic output truncated", record["output"])

    def test_pre_screenshot_exit_attaches_process_and_stage_diagnostic(self) -> None:
        class ExitedProcess:
            returncode = -6

            def poll(self) -> int:
                return self.returncode

        args = mock.Mock(timeout=1)
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=(
                Path("/RetroArch"), Path("/core"), Path("/fixture"), {"bundle_id": "org.example.RetroArch"},
            )),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "find_recent_crash_reason", return_value=None),
            mock.patch.object(smoke.subprocess, "Popen", return_value=ExitedProcess()),
            mock.patch.object(smoke, "request_frontend_quit"),
            mock.patch.object(smoke.time, "sleep"),
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.run_smoke(args)

        self.assertEqual(raised.exception.stage, "first-screenshot")
        self.assertEqual(raised.exception.diagnostic["return_code"], -6)
        self.assertFalse(raised.exception.diagnostic["survived_before_screenshot"])

    def test_launch_comparison_localizes_content_failure_after_clean_startup(self) -> None:
        compare = getattr(smoke, "compare_launch_probes", None)
        finding = compare(
            {"return_code": None, "survived_window": True},
            {"return_code": -6, "survived_window": False},
        ) if callable(compare) else ""

        self.assertEqual(finding, "core-or-content-invocation-failed")

    def test_keyboard_authority_failure_is_unavailable_not_a_pass(self) -> None:
        with mock.patch.object(
            smoke.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["osascript"]),
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.inject_key(smoke.RIGHT_KEY_CODE, repeats=1)

        self.assertEqual(raised.exception.stage, "input")
        self.assertIn("could not inject", str(raised.exception))
        self.assertEqual(raised.exception.availability, "unavailable")

    def test_blocked_keyboard_authority_stays_unknown_in_command_result(self) -> None:
        error = smoke.SmokeBlocked("input", "macOS could not inject the mapped arrow-key input")
        stdout = io.StringIO()
        with (
            mock.patch.object(sys, "argv", [
                "retroarch_smoke.py", "--retroarch", "/Applications/RetroArch.app",
                "--core", "/tmp/core.dylib", "--content", "/tmp/fixture.bin",
            ]),
            mock.patch.object(smoke, "run_smoke", side_effect=error),
            mock.patch.object(smoke, "validate_inputs", return_value=(Path("/app"), Path("/core"), Path("/fixture"), {"fixture_sha256": "abc"})),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = smoke.main()

        result = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "blocked_or_unknown")
        self.assertEqual(result["availability"], "unavailable")
        self.assertNotEqual(result["status"], "pass")

    def test_launch_probes_use_distinct_profiles_without_starting_gui(self) -> None:
        class FakeProcess:
            def __init__(self, return_code: int | None) -> None:
                self.returncode = return_code

            def wait(self, timeout: float | None = None) -> int:
                if self.returncode is None:
                    raise subprocess.TimeoutExpired("fake-retroarch", timeout)
                return self.returncode

            def poll(self) -> int | None:
                return self.returncode

        with (
            mock.patch.object(smoke.subprocess, "Popen", side_effect=[FakeProcess(None), FakeProcess(-6)]) as popen,
            mock.patch.object(smoke, "request_frontend_quit"),
            mock.patch.object(smoke, "find_recent_crash_reason", return_value=None),
            mock.patch.object(smoke, "DIAGNOSTIC_PROBE_SECONDS", 0.01),
        ):
            no_content = smoke.run_launch_probe(
                Path("/RetroArch"), Path("/core"), Path("/fixture"), "org.example.RetroArch",
                probe="no_content", timeout=1,
            )
            core_content = smoke.run_launch_probe(
                Path("/RetroArch"), Path("/core"), Path("/fixture"), "org.example.RetroArch",
                probe="core_content", timeout=1,
            )

        config_paths = [call.args[0][call.args[0].index("--config") + 1] for call in popen.call_args_list]
        self.assertNotEqual(config_paths[0], config_paths[1])
        self.assertTrue(no_content["survived_window"])
        self.assertFalse(core_content["survived_window"])
        self.assertEqual(smoke.compare_launch_probes(no_content, core_content), "core-or-content-invocation-failed")


if __name__ == "__main__":
    unittest.main()
