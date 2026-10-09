from __future__ import annotations

import contextlib
import io
import json
import plistlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import retroarch_smoke as smoke


class FixtureIdentityTests(unittest.TestCase):
    EXPECTED_FIXTURE_SHA256 = "59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0"
    EXPECTED_APP_SHA256 = smoke.EXPECTED_EXECUTABLE_SHA256

    def make_fixture(self, directory: Path) -> Path:
        compiler = shutil.which("cc")
        self.assertIsNotNone(compiler, "the project C compiler is required to generate its public fixture")
        writer = directory / "fixture_writer.c"
        writer.write_text(
            '#include "public_guest.c"\n'
            'int main(int argc, char **argv) { return argc == 2 && public_guest_write(argv[1]) ? 0 : 1; }\n',
            encoding="utf-8",
        )
        executable = directory / "fixture_writer"
        root = Path(__file__).resolve().parents[2]
        subprocess.run(
            [compiler, "-std=c17", "-I", str(root / "tests/fixture"), str(writer), "-o", str(executable)],
            cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        fixture = directory / "public-playable.bin"
        subprocess.run([str(executable), str(fixture)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return fixture

    def make_inputs(self, directory: Path, fixture: Path) -> tuple[object, Path]:
        bundle = directory / "RetroArch.app"
        executable = bundle / "Contents" / "MacOS" / "RetroArch"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"mock pinned app bytes")
        (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleShortVersionString": smoke.EXPECTED_VERSION,
            "CFBundleExecutable": "RetroArch",
            "CFBundleIdentifier": "com.libretro.dist.RetroArch",
        }))
        core = directory / "glueyneo_libretro.dylib"
        core.write_bytes(b"core")
        args = type("Args", (), {"retroarch": bundle, "core": core, "content": fixture, "timeout": 20.0})()
        return args, executable

    def validate(self, args: object, executable: Path) -> dict[str, str]:
        actual_sha = smoke.sha256
        with (
            mock.patch.object(smoke.sys, "platform", "darwin"),
            mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                self.EXPECTED_APP_SHA256 if Path(path).resolve() == executable.resolve() else actual_sha(Path(path))
            )),
        ):
            return smoke.validate_inputs(args)[3]

    def test_generated_public_fixture_is_accepted_as_the_pinned_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            fixture = self.make_fixture(directory)
            args, executable = self.make_inputs(directory, fixture)

            identity = self.validate(args, executable)

        self.assertEqual(identity["fixture_sha256"], self.EXPECTED_FIXTURE_SHA256)

    def test_wrong_digest_fixture_is_rejected_before_frontend_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            fixture = self.make_fixture(directory)
            content = bytearray(fixture.read_bytes())
            self.assertEqual(len(content), 602)
            self.assertEqual(content[:8], b"GNFX\0\0\0\1")
            content[-1] ^= 1
            fixture.write_bytes(content)
            args, executable = self.make_inputs(directory, fixture)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    self.EXPECTED_APP_SHA256 if Path(path).resolve() == executable.resolve() else actual_sha(Path(path))
                )),
                mock.patch.object(smoke.subprocess, "Popen", side_effect=OSError("launch attempted")) as popen,
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)

        self.assertEqual(raised.exception.stage, "input")
        self.assertIn("digest", str(raised.exception))
        popen.assert_not_called()


class SelectedMVSContentTests(unittest.TestCase):
    REGION_LENGTHS = (0x80000, 0x500000, 0x20000, 0x20000, 0xA00000, 0x3000000)
    PROFILE_MSX = 0x4D53584D

    def make_bundle(self, directory: Path, *, malformed: bool = False) -> Path:
        roles = (1, 2, 3, 4, 5, 6)
        bundle = bytearray(b"GNMV" + (1).to_bytes(4, "big") +
                           self.PROFILE_MSX.to_bytes(4, "big") +
                           (6).to_bytes(4, "big"))
        for role, length in zip(roles, self.REGION_LENGTHS):
            if malformed and role == 1:
                length -= 1
            bundle.extend(role.to_bytes(4, "big"))
            bundle.extend(length.to_bytes(8, "big"))
            bundle.extend(bytes(length))
        path = directory / "selected.gnmv"
        path.write_bytes(bundle)
        return path

    def make_inputs(self, directory: Path, content: Path) -> tuple[object, Path]:
        app = directory / "RetroArch.app"
        executable = app / "Contents" / "MacOS" / "RetroArch"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"mock pinned app bytes")
        (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleShortVersionString": smoke.EXPECTED_VERSION,
            "CFBundleExecutable": "RetroArch",
            "CFBundleIdentifier": smoke.EXPECTED_BUNDLE_IDENTIFIER,
        }))
        core = directory / "glueyneo_libretro.dylib"
        core.write_bytes(b"synthetic core")
        args = type("Args", (), {
            "retroarch": app, "core": core, "content": content, "timeout": 20.0,
        })()
        return args, executable

    def test_synthetic_selected_bundle_is_accepted_without_publishing_content_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = self.make_bundle(directory)
            args, executable = self.make_inputs(directory, content)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    smoke.EXPECTED_EXECUTABLE_SHA256 if Path(path).resolve() == executable.resolve()
                    else actual_sha(Path(path))
                )),
            ):
                identity = smoke.validate_inputs(args)[3]
            serialized = json.dumps(identity, sort_keys=True)
            content_digest = smoke.sha256(content)

        self.assertEqual(identity["content_kind"], "selected-mvs")
        self.assertNotIn("fixture_sha256", identity)
        self.assertNotIn("content_sha256", identity)
        self.assertNotIn(str(content), serialized)
        self.assertNotIn(content_digest, serialized)

    def test_malformed_selected_bundle_is_rejected_before_frontend_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = self.make_bundle(directory, malformed=True)
            args, executable = self.make_inputs(directory, content)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    smoke.EXPECTED_EXECUTABLE_SHA256 if Path(path).resolve() == executable.resolve()
                    else actual_sha(Path(path))
                )),
                mock.patch.object(smoke.subprocess, "Popen", side_effect=OSError("launch attempted")) as popen,
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)

        self.assertEqual(raised.exception.stage, "input")
        popen.assert_not_called()

    def test_missing_selected_bundle_is_rejected_before_frontend_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = directory / "missing.gnmv"
            args, executable = self.make_inputs(directory, content)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    smoke.EXPECTED_EXECUTABLE_SHA256 if Path(path).resolve() == executable.resolve()
                    else actual_sha(Path(path))
                )),
                mock.patch.object(smoke.subprocess, "Popen", side_effect=OSError("launch attempted")) as popen,
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)

        self.assertEqual(raised.exception.stage, "input")
        popen.assert_not_called()

    def test_oversized_selected_bundle_is_rejected_before_frontend_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = directory / "oversized.gnmv"
            with content.open("wb") as stream:
                stream.write(b"GNMV")
                stream.truncate(smoke.GNMV_MAX_BYTES + 1)
            args, executable = self.make_inputs(directory, content)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    smoke.EXPECTED_EXECUTABLE_SHA256 if Path(path).resolve() == executable.resolve()
                    else actual_sha(Path(path))
                )),
                mock.patch.object(smoke.subprocess, "Popen", side_effect=OSError("launch attempted")) as popen,
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)

        self.assertEqual(raised.exception.stage, "input")
        self.assertIn("bounded input size", str(raised.exception))
        popen.assert_not_called()


class BundleIdentifierTests(unittest.TestCase):
    VALID_BUNDLE_ID = "com.libretro.dist.RetroArch"
    INVALID_BUNDLE_IDS = (
        "", "com.libretro.dist.RetroArch\"; do shell script \"open /tmp/private\"; --",
        "com.libretro.dist.RetroArch\nquit", "com.libretro.dist.RetroArch'",
        "com.libretro.dist.RetroArch\x01",
    )

    class RunningProcess:
        returncode: int | None = None

        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def poll(self) -> int | None:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = 0
            return 0

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

    def test_plist_identifier_must_match_pinned_app_before_input_validation(self) -> None:
        for bundle_id in self.INVALID_BUNDLE_IDS:
            with self.subTest(bundle_id="malformed"):
                with tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    bundle = directory / "RetroArch.app"
                    contents = bundle / "Contents"
                    contents.mkdir(parents=True)
                    executable = contents / "MacOS" / "RetroArch"
                    executable.parent.mkdir()
                    executable.write_bytes(b"mock executable bytes")
                    (contents / "Info.plist").write_bytes(plistlib.dumps({
                        "CFBundleShortVersionString": smoke.EXPECTED_VERSION,
                        "CFBundleExecutable": "RetroArch",
                        "CFBundleIdentifier": bundle_id,
                    }, fmt=plistlib.FMT_BINARY))
                    args = type("Args", (), {
                        "retroarch": bundle, "core": directory / "core", "content": directory / "fixture",
                    })()
                    with (
                        mock.patch.object(smoke.sys, "platform", "darwin"),
                        mock.patch.object(smoke.subprocess, "run") as run,
                    ):
                        with self.assertRaises(smoke.SmokeBlocked) as raised:
                            smoke.validate_inputs(args)

                self.assertEqual(raised.exception.stage, "identity")
                self.assertIn("bundle identifier", str(raised.exception))
                if bundle_id:
                    self.assertNotIn(bundle_id, str(raised.exception))
                run.assert_not_called()

    def test_quit_helper_uses_one_bounded_fixed_command_for_pinned_identifier(self) -> None:
        process = self.RunningProcess()
        with mock.patch.object(smoke.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            smoke.request_frontend_quit(self.VALID_BUNDLE_ID, process, 20.0)

        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0][0:2], ["/usr/bin/osascript", "-e"])
        self.assertEqual(args[0][2], 'tell application id "com.libretro.dist.RetroArch" to quit')
        self.assertTrue(kwargs["check"])
        self.assertLessEqual(kwargs["timeout"], 8.0)
        self.assertFalse(process.terminated)

    def test_invalid_identifier_skips_quit_subprocess_and_terminates_owned_process(self) -> None:
        for bundle_id in self.INVALID_BUNDLE_IDS:
            with self.subTest(bundle_id="malformed"):
                process = self.RunningProcess()
                with mock.patch.object(smoke.subprocess, "run") as run:
                    smoke.request_frontend_quit(bundle_id, process, 20.0)

                run.assert_not_called()
                self.assertTrue(process.terminated)

    def test_cleanup_after_smoke_failure_cannot_launch_quit_for_bad_identifier(self) -> None:
        process = self.RunningProcess()
        identity = {"bundle_id": self.INVALID_BUNDLE_IDS[1]}
        args = mock.Mock(timeout=1.0)
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=(Path("/app"), Path("/core"), Path("/fixture"), identity)),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "request_screenshot", side_effect=smoke.SmokeBlocked("video", "expected test failure")),
            mock.patch.object(smoke, "collect_frontend_output", return_value=""),
            mock.patch.object(smoke.subprocess, "Popen", return_value=process),
            mock.patch.object(smoke.subprocess, "run") as run,
            mock.patch.object(smoke.time, "sleep"),
        ):
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.run_smoke(args)

        run.assert_not_called()
        self.assertTrue(process.terminated)


class ScreenshotFreshnessTests(unittest.TestCase):
    def test_ambiguous_paths_and_temporary_descendants_are_fully_redacted(self) -> None:
        roots = ("/Users/private-person", "/Volumes/synthetic", "/tmp/synthetic",
                 "/private/var/folders/private-person", str(Path.home()),
                 str(Path(__file__).resolve().parents[2]), "/custom/synthetic-root")
        for root in roots:
            for component in ("private,tail", "private:tail", "private in tail"):
                for quote in ("", '"', "'"):
                    with self.subTest(component=component, quoted=bool(quote)):
                        path = f"{root}/{component}/sensitive.bin"
                        text = f"video failed status -6: {quote}{path}{quote}"
                        safe = smoke.sanitize_diagnostic_text(text, temporary_root=Path(root))
                        record = smoke.build_diagnostic(
                            stage="video", return_code=-6, survived_before_screenshot=False,
                            output=text, temporary_root=Path(root),
                            crash_report=f"Exception Type: EXC_CRASH {quote}{path}{quote}",
                        )
                        retained = safe + json.dumps(record)
                        self.assertNotIn(root, retained)
                        self.assertNotIn(component, retained)
                        self.assertNotIn("sensitive.bin", retained)
                        self.assertIn("video failed status -6", retained)

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
    def test_json_escaped_quote_and_apostrophe_paths_are_removed_from_frontend_records(self) -> None:
        with tempfile.TemporaryDirectory(prefix="private-root-") as temporary:
            root = Path(temporary)
            diagnostics = (
                f'video failed status -6: "{root}/private capture/secret\\"tail.rom" permission denied',
                f"Exception Type: EXC_CRASH '{root}/O'Brien/private secret.rom' signal 6",
                f'video failed status -6: "{root}/private"tail/sensitive.bin"',
            )
            for diagnostic in diagnostics:
                with self.subTest(diagnostic=diagnostic):
                    safe = smoke.sanitize_diagnostic_text(diagnostic, temporary_root=root)
                    self.assertEqual(smoke.sanitize_diagnostic_text(safe, temporary_root=root), safe)
                    record = smoke.build_diagnostic(
                        stage="video", return_code=-6, survived_before_screenshot=False,
                        output=f"video failed status -6: {diagnostic}", temporary_root=root,
                        crash_report=diagnostic if diagnostic.startswith("Exception") else None,
                    )
                    serialized = json.dumps(record, sort_keys=True)
                    self.assertEqual(record["stage"], "video")
                    self.assertEqual(record["return_code"], -6)
                    self.assertIn("status -6", record["output"])
                    self.assertNotIn(str(root), serialized)
                    for private in ("private capture", "secret", "tail.rom", "O'Brien", "private secret", "secret.rom", "tail/sensitive.bin"):
                        self.assertNotIn(private, serialized)
                    if diagnostic.startswith("Exception"):
                        self.assertIn("EXC_CRASH", serialized)

    def test_newline_private_path_suffix_is_removed_from_frontend_and_crash_sinks(self) -> None:
        root = Path("/tmp/synthetic-frontend-temp")
        output = f"video failed status -6: {root}/private\n/tail/sensitive.bin"
        crash_report = (
            f"Exception Type: EXC_CRASH {root}/private\n"
            "Termination Reason: namespace POSIX, code 9, /tail/sensitive.bin"
        )

        safe = smoke.sanitize_diagnostic_text(output, temporary_root=root)
        reason = smoke.extract_crash_reason(crash_report)
        record = smoke.build_diagnostic(
            stage="video", return_code=-6, survived_before_screenshot=False,
            output=output, temporary_root=root, crash_report=crash_report,
        )
        serialized = json.dumps(record, sort_keys=True)
        retained = safe + reason + serialized

        self.assertEqual(smoke.sanitize_diagnostic_text(safe, temporary_root=root), safe)
        self.assertIn("video failed status -6", retained)
        self.assertIn("EXC_CRASH", retained)
        self.assertEqual(record["stage"], "video")
        self.assertEqual(record["return_code"], -6)
        self.assertFalse(record["survived_before_screenshot"])
        self.assertNotIn("/tail/sensitive.bin", retained)
        self.assertNotIn("private", retained)

    def test_space_containing_private_paths_are_removed_from_all_diagnostic_forms(self) -> None:
        cases = (
            ('failed: "/Users/private-person home/private capture/secret.rom": permission denied',
             ("synthetic home", "private capture", "secret.rom")),
            ("failed exit 5: /tmp/temporary work/private file.rom", ("temporary work", "private file.rom")),
            ("failed: /private/var/folders/private-person root/private cache/secret.bin\ncontinued",
             ("cache root", "private cache", "secret.bin")),
            ("failed exit 6: /Volumes/private drive/private media/secret.rom\nready",
             ("private drive", "private media", "secret.rom")),
        )
        for diagnostic, private_parts in cases:
            with self.subTest(prefix=diagnostic.split(":", 1)[0]):
                safe = smoke.sanitize_diagnostic_text(diagnostic)
                for private in private_parts:
                    self.assertNotIn(private, safe)
                self.assertIn("failed", safe)
                details = ("exit 5", "exit 6")
                if any(detail in diagnostic for detail in details):
                    self.assertTrue(any(detail in safe for detail in details))
                if "continued" in diagnostic:
                    self.assertNotIn("continued", safe)
                if "ready" in diagnostic:
                    self.assertNotIn("ready", safe)

    def test_crash_reason_and_serialized_diagnostic_redact_complete_paths(self) -> None:
        report = (
            'Exception Type: EXC_CRASH /Users/private-person home/private capture/secret.rom: '
            'signal 6\nTermination Reason: namespace POSIX, code 9'
        )
        reason = smoke.extract_crash_reason(report)
        record = smoke.build_diagnostic(
            stage="frontend", return_code=-6, survived_before_screenshot=False,
            output='stderr exit 6: /Volumes/private drive/private media/secret.rom',
            crash_report=report,
        )
        serialized = json.dumps(record, sort_keys=True) + reason

        for private in ("synthetic home", "private capture", "secret.rom", "private drive", "private media"):
            self.assertNotIn(private, serialized)
        self.assertIn("EXC_CRASH", serialized)
        self.assertNotIn("Termination Reason", serialized)
        self.assertIn("exit 6", serialized)
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
            output="failed /Users/private-person/private/game.rom\ntemporary /private/var/folders/private-person/temp\ncheckout /Users/private-person/worktree",
            temporary_root=Path("/private/var/folders/private-person/temp"),
        ) if callable(builder) else {}

        serialized = str(record)
        self.assertNotIn("alice", serialized)
        self.assertNotIn("bob", serialized)
        self.assertNotIn("private/game.rom", serialized)
        self.assertNotIn("/private/var/folders/private-person/temp", serialized)
        self.assertIn("[user]", serialized)
        self.assertNotIn("temporary", serialized)
        self.assertNotIn("checkout", serialized)

    def test_diagnostic_output_redacts_the_full_home_relative_path(self) -> None:
        text = f"file load failed: {Path.home()}/projects/private-data/rom.bin"

        sanitized = smoke.sanitize_diagnostic_text(text)

        self.assertNotIn("projects/private-data/rom.bin", sanitized)
        self.assertNotIn(str(Path.home()), sanitized)

    def test_frontend_and_subprocess_logs_are_captured_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            process_log = work / "process-output.log"
            frontend_log = work / "retroarch.log"
            process_log.write_text("stdout and stderr", encoding="utf-8")
            frontend_log.write_text("frontend startup trace", encoding="utf-8")

            output = smoke.collect_frontend_output(process_log, frontend_log, work)

        self.assertIn("stdout and stderr", output)
        self.assertIn("frontend startup trace", output)
        self.assertIn("stdout/stderr", output)
        self.assertIn("RetroArch file log", output)

    def test_crash_parser_keeps_only_bounded_reason_fields(self) -> None:
        report = """Process: RetroArch [123]
Path: /Users/private-person/Applications/RetroArch.app/Contents/MacOS/RetroArch
Exception Type: EXC_CRASH (SIGABRT)
Termination Reason: Namespace DYLD, Code 1 Library not loaded: /Users/private-person/private/lib.dylib
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
                        "indicator": "Library not loaded: /Users/private-person/private/lib.dylib",
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

    def test_diagnostic_preserves_pre_extracted_macos_crash_reason(self) -> None:
        record = smoke.build_diagnostic(
            stage="no-content-startup", return_code=-6,
            survived_before_screenshot=None, output="",
            crash_report="Exception: EXC_CRASH SIGABRT\nTermination: SIGNAL 6 Abort trap: 6",
        )

        self.assertTrue(record["macos_crash_reason_available"])
        self.assertIn("EXC_CRASH", record["macos_crash_reason"])
        self.assertIn("Abort trap", record["macos_crash_reason"])

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
            mock.patch.object(smoke, "wait_for_recent_crash_reason", return_value=None),
            mock.patch.object(smoke, "CRASH_REPORT_WAIT_SECONDS", 0),
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
            mock.patch.object(smoke, "wait_for_recent_crash_reason", return_value=None),
            mock.patch.object(smoke, "CRASH_REPORT_WAIT_SECONDS", 0),
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
