from __future__ import annotations

from pathlib import Path
import subprocess
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


if __name__ == "__main__":
    unittest.main()
