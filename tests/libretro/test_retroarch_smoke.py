from __future__ import annotations

import contextlib
import io
import json
import os
import plistlib
import re
import signal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
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
        process.pid = 4321
        with (
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4321}),
            mock.patch.object(smoke.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run,
        ):
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
            mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
            mock.patch.object(smoke.subprocess, "Popen", return_value=process),
            mock.patch.object(smoke.subprocess, "run") as run,
            mock.patch.object(smoke.time, "sleep"),
        ):
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.run_smoke(args)

        run.assert_not_called()
        self.assertTrue(process.terminated)


class IdentityCheckTest(unittest.TestCase):
    """IN-02: the pinned equality alone refuses every other bundle id; the bounds test is subsumed."""

    def refuse(self, bundle_id: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            contents = directory / "RetroArch.app" / "Contents"
            (contents / "MacOS").mkdir(parents=True)
            (contents / "Info.plist").write_bytes(plistlib.dumps({
                "CFBundleShortVersionString": smoke.EXPECTED_VERSION,
                "CFBundleExecutable": "RetroArch",
                "CFBundleIdentifier": bundle_id,
            }, fmt=plistlib.FMT_BINARY))
            args = type("Args", (), {"retroarch": directory / "RetroArch.app",
                                     "core": directory / "core", "content": directory / "fixture"})()
            with mock.patch.object(smoke.sys, "platform", "darwin"), \
                    mock.patch.object(smoke.subprocess, "run") as run:
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.validate_inputs(args)
            run.assert_not_called()
            self.assertEqual(raised.exception.stage, "identity")

    def test_non_pinned_and_spaced_bundle_ids_are_refused(self) -> None:
        for bundle_id in ("com.example.Other", "com.libretro.dist.Retro Arch"):
            with self.subTest(bundle_id=bundle_id):
                self.refuse(bundle_id)

    def test_validate_inputs_has_no_redundant_pattern_check(self) -> None:
        source = Path(smoke.__file__).read_text(encoding="utf-8")
        self.assertNotIn("re.fullmatch", source)
        self.assertNotIn("cursor > len(content)", source)

    def test_truncated_bundles_are_still_rejected(self) -> None:
        header = b"GNMV" + (1).to_bytes(4, "big") + smoke.GNMV_PROFILE_MSX.to_bytes(4, "big") \
            + len(smoke.GNMV_REGION_LENGTHS).to_bytes(4, "big")
        for label, content in (("header only", header), ("partial region header", header + b"\x00" * 5)):
            with self.subTest(label=label):
                self.assertFalse(smoke.is_normalized_mvs_bundle(content))


class SingleInstanceTest(unittest.TestCase):
    """E6/CR-07: never stack a second RetroArch and never quit an instance we did not start."""

    class Running:
        returncode: int | None = None

        def __init__(self, pid: int = 4321) -> None:
            self.pid = pid
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

    def stub_inputs(self) -> mock._patch:
        identity = {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER}
        return mock.patch.object(
            smoke, "validate_inputs",
            return_value=(Path("/app"), Path("/core"), Path("/fixture"), identity))

    def test_run_smoke_refuses_when_an_instance_exists(self) -> None:
        args = mock.Mock(timeout=1.0, child_pid_file=None)
        with (
            self.stub_inputs(),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4242}),
            mock.patch.object(smoke.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.run_smoke(args)
        self.assertEqual(raised.exception.stage, "pre-launch")
        popen.assert_not_called()

    def test_run_launch_probe_refuses_when_an_instance_exists(self) -> None:
        with (
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4242}),
            mock.patch.object(smoke.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.run_launch_probe(Path("/RetroArch"), Path("/core"), Path("/fixture"),
                                       smoke.EXPECTED_BUNDLE_IDENTIFIER,
                                       probe="no_content", timeout=1)
        self.assertEqual(raised.exception.stage, "pre-launch")
        popen.assert_not_called()

    def test_main_prints_one_blocked_json_line_and_returns_one(self) -> None:
        argv = ["retroarch_smoke.py", "--retroarch", "/app", "--core", "/core", "--content", "/fixture"]
        with (
            mock.patch.object(sys, "argv", argv),
            self.stub_inputs(),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4242}),
            mock.patch.object(smoke.subprocess, "Popen") as popen,
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            exit_code = smoke.main()
        lines = stdout.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 1)
        result = json.loads(lines[0])
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "blocked_or_unknown")
        self.assertEqual(result["stage"], "pre-launch")
        popen.assert_not_called()

    def test_lister_fails_closed(self) -> None:
        failures = (
            mock.patch.object(smoke.subprocess, "run", side_effect=OSError("no pgrep")),
            mock.patch.object(smoke.subprocess, "run",
                              side_effect=subprocess.TimeoutExpired("pgrep", 5)),
            mock.patch.object(smoke.subprocess, "run", return_value=subprocess.CompletedProcess([], 2, "", "")),
        )
        for failure in failures:
            with failure, self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.running_retroarch_pids()
            self.assertEqual(raised.exception.stage, "pre-launch")

    def test_lister_maps_pgrep_exit_codes(self) -> None:
        with mock.patch.object(smoke.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 1, "", "")) as run:
            self.assertEqual(smoke.running_retroarch_pids(), set())
        self.assertEqual(run.call_args.args[0], ["/usr/bin/pgrep", "-x", "RetroArch"])
        with mock.patch.object(smoke.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, "4242\n4243\n", "")):
            self.assertEqual(smoke.running_retroarch_pids(), {4242, 4243})

    def test_quit_uses_osascript_only_when_started_pid_is_the_sole_instance(self) -> None:
        process = self.Running(pid=4321)
        with (
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4321}),
            mock.patch.object(smoke.subprocess, "run",
                              return_value=subprocess.CompletedProcess([], 0)) as run,
        ):
            smoke.request_frontend_quit(smoke.EXPECTED_BUNDLE_IDENTIFIER, process, 20.0)
        run.assert_called_once()
        self.assertFalse(process.terminated)

    def test_quit_terminates_by_pid_when_a_foreign_instance_exists(self) -> None:
        process = self.Running(pid=4321)
        with (
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4321, 999}),
            mock.patch.object(smoke.subprocess, "run") as run,
        ):
            smoke.request_frontend_quit(smoke.EXPECTED_BUNDLE_IDENTIFIER, process, 20.0)
        run.assert_not_called()
        self.assertTrue(process.terminated)

    def test_quit_terminates_by_pid_when_the_lister_fails(self) -> None:
        process = self.Running(pid=4321)
        with (
            mock.patch.object(smoke, "running_retroarch_pids",
                              side_effect=smoke.SmokeBlocked("pre-launch", "cannot enumerate")),
            mock.patch.object(smoke.subprocess, "run") as run,
        ):
            smoke.request_frontend_quit(smoke.EXPECTED_BUNDLE_IDENTIFIER, process, 20.0)
        run.assert_not_called()
        self.assertTrue(process.terminated)


class OuterTimeoutTest(unittest.TestCase):
    """E6: an outer runner timeout must not orphan the launched frontend (uses a fake executable)."""

    ROOT = Path(__file__).resolve().parents[2]

    def test_child_pid_file_is_written_before_frontend_interaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pid_file = Path(temporary) / "child.pid"
            process = SingleInstanceTest.Running(pid=4321)
            args = mock.Mock(timeout=1.0, child_pid_file=pid_file)
            observed: list[str] = []

            def screenshot(*_a: object, **_k: object) -> Path:
                observed.append(pid_file.read_text(encoding="utf-8"))
                raise smoke.SmokeBlocked("video", "expected test failure")

            with (
                mock.patch.object(smoke, "validate_inputs", return_value=(
                    Path("/app"), Path("/core"), Path("/fixture"),
                    {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER})),
                mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
                mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
                mock.patch.object(smoke, "request_screenshot", side_effect=screenshot),
                mock.patch.object(smoke, "collect_frontend_output", return_value=""),
                mock.patch.object(smoke, "request_frontend_quit"),
                mock.patch.object(smoke.subprocess, "Popen", return_value=process),
                mock.patch.object(smoke.os, "killpg"),
                mock.patch.object(smoke.time, "sleep"),
            ):
                with self.assertRaises(smoke.SmokeBlocked):
                    smoke.run_smoke(args)
        self.assertEqual(observed, ["4321\n"])

    def test_outer_timeout_leaves_no_fake_frontend_behind(self) -> None:
        sys.path.insert(0, str(self.ROOT / "tools"))
        import verify_playable as playable

        with tempfile.TemporaryDirectory(prefix="outer-timeout-") as temporary:
            base = Path(temporary)
            pid_file = base / "frontend.pid"
            fake = base / "fake-frontend"
            fake.write_text(
                f"#!/bin/sh\necho $$ > '{pid_file}'\nexec sleep 60\n", encoding="utf-8")
            fake.chmod(0o755)
            driver = base / "driver.py"
            driver.write_text(
                "import sys, time\n"
                f"sys.path.insert(0, {str(self.ROOT / 'tests/libretro')!r})\n"
                "import retroarch_smoke as smoke\n"
                "from pathlib import Path\n"
                "identity = {'bundle_id': smoke.EXPECTED_BUNDLE_IDENTIFIER}\n"
                f"smoke.validate_inputs = lambda a: (Path({str(fake)!r}), Path('/core'), Path('/fixture'), identity)\n"
                "smoke.running_retroarch_pids = lambda: set()\n"
                "smoke.crash_report_snapshot = lambda: {}\n"
                "smoke.request_screenshot = lambda *a, **k: time.sleep(60)\n"
                "sys.argv = ['retroarch_smoke.py', '--retroarch', '/a', '--core', '/c', '--content', '/f']\n"
                "raise SystemExit(smoke.main())\n",
                encoding="utf-8")

            seen: list[int] = []

            def reap() -> None:
                # The temporary directory is gone by cleanup time; use the PID captured in the test body.
                for survivor in seen:
                    try:
                        os.kill(survivor, signal.SIGKILL)
                    except OSError:
                        pass

            self.addCleanup(reap)
            work = base / "work"
            work.mkdir()
            runner = playable.Runner(work, base, None)  # type: ignore[arg-type]
            started = time.monotonic()
            with mock.patch.object(playable, "verify_snapshot"):
                result = runner.command("actual-retroarch-smoke", [sys.executable, str(driver)],
                                        timeout=3, allow_failure=True)
            self.assertLess(time.monotonic() - started, 60)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(pid_file.is_file(), "the fake frontend never started")
            pid = int(pid_file.read_text(encoding="utf-8"))
            seen.append(pid)
            deadline = time.monotonic() + 10
            alive = True
            while alive and time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    alive = False
            self.assertFalse(alive, f"fake frontend survived the outer timeout: pid {pid}")


class CaptureRobustnessTest(unittest.TestCase):
    """WR-04/WR-05: partial captures and hostile PNGs stay inside the scanned smoke result."""

    IEND = b"\x00\x00\x00\x00IEND\xaeB`\x82"

    @staticmethod
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return len(data).to_bytes(4, "big") + kind + data + crc.to_bytes(4, "big")

    def png(self, width: int, height: int, raw: bytes, *, ihdr: bytes | None = None,
            idat: bytes | None = None) -> bytes:
        header = ihdr if ihdr is not None else (
            width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([8, 2, 0, 0, 0]))
        body = idat if idat is not None else zlib.compress(raw)
        return (b"\x89PNG\r\n\x1a\n" + self.chunk(b"IHDR", header)
                + self.chunk(b"IDAT", body) + self.chunk(b"IEND", b""))

    def decode_error(self, data: bytes) -> smoke.SmokeBlocked:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "capture.png"
            path.write_bytes(data)
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.decode_png(path)
        return raised.exception

    def test_valid_png_still_decodes(self) -> None:
        raw = b"".join(b"\x00" + bytes(range(6)) for _ in range(2))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ok.png"
            path.write_bytes(self.png(2, 2, raw))
            self.assertEqual(smoke.decode_png(path)[:3], (2, 2, 3))

    def test_png_without_iend_is_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "partial.png").write_bytes(b"\x89PNG\r\n\x1a\npartial")
            self.assertIsNone(smoke.select_fresh_screenshot(directory, {}))

    def test_complete_stable_png_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            capture = directory / "done.png"
            capture.write_bytes(b"\x89PNG\r\n\x1a\nbody" + self.IEND)
            self.assertEqual(smoke.select_fresh_screenshot(directory, {}), capture)

    def test_still_growing_png_is_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            capture = directory / "growing.png"
            capture.write_bytes(b"\x89PNG\r\n\x1a\nbody" + self.IEND)

            def grow(_seconds: float) -> None:
                with capture.open("ab") as stream:
                    stream.write(self.IEND)

            with mock.patch.object(smoke.time, "sleep", side_effect=grow):
                self.assertIsNone(smoke.select_fresh_screenshot(directory, {}))

    def test_decode_failures_are_video_stage_blocks(self) -> None:
        width, height = 320, 224
        expected = height * (1 + width * 3)
        cases = {
            "truncated-ihdr": self.png(width, height, b"", ihdr=b"\x00\x00\x01"),
            "corrupt-idat": self.png(width, height, b"", idat=b"not a zlib stream" * 4),
            "oversized-inflate": self.png(width, height, bytes(expected + 4096)),
            "zero-dimensions": self.png(0, 0, b""),
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.decode_error(data).stage, "video")

    def test_truncated_chunk_stream_is_a_video_stage_block(self) -> None:
        data = b"\x89PNG\r\n\x1a\n" + (500).to_bytes(4, "big") + b"IDATshort"
        self.assertEqual(self.decode_error(data).stage, "video")

    def test_non_gnmv_content_is_size_checked_before_it_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = directory / "blob.bin"
            content.write_bytes(b"NOPE" + bytes(696))
            fixtures = FixtureIdentityTests()
            args, executable = fixtures.make_inputs(directory, content)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    smoke.EXPECTED_EXECUTABLE_SHA256 if Path(path).resolve() == executable.resolve()
                    else actual_sha(Path(path)))),
                mock.patch.object(Path, "read_bytes", side_effect=AssertionError("read before size check")),
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.validate_inputs(args)
        self.assertEqual(raised.exception.stage, "input")


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
            fresh.write_bytes(b"new capture" + CaptureRobustnessTest.IEND)
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
        self.assertIn("[redacted-path]", serialized)
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
            mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
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

    def test_injected_keys_are_held_across_frame_polls_not_tapped(self) -> None:
        # RetroArch samples key state once per frame; a back-to-back down/up
        # (System Events `key code`) can fall between polls and be ignored.
        with (
            mock.patch.object(smoke.subprocess, "run") as run,
            mock.patch.object(smoke, "post_held_key") as post,
            mock.patch.object(smoke.time, "sleep"),
        ):
            smoke.inject_key(smoke.SCREENSHOT_KEY_CODE)
            smoke.inject_key(smoke.RIGHT_KEY_CODE, hold=smoke.ARROW_HOLD_SECONDS)

        for call in run.call_args_list:
            self.assertNotIn("key code", call.args[0][-1])
            self.assertIn("frontmost", call.args[0][-1])
        self.assertEqual(post.call_args_list, [
            mock.call(smoke.SCREENSHOT_KEY_CODE, smoke.KEY_HOLD_SECONDS),
            mock.call(smoke.RIGHT_KEY_CODE, smoke.ARROW_HOLD_SECONDS),
        ])
        frame = 1.0 / 60.0
        self.assertGreaterEqual(smoke.KEY_HOLD_SECONDS, 3 * frame)
        self.assertGreaterEqual(smoke.ARROW_HOLD_SECONDS, smoke.KEY_HOLD_SECONDS)

    def test_held_key_posts_down_then_waits_hold_then_up(self) -> None:
        log: list[tuple[str, object]] = []

        class Services:
            def __init__(self, preflight: bool) -> None:
                self.preflight = preflight
                self.CGPreflightPostEventAccess = lambda: self.preflight
                self.CGEventCreateKeyboardEvent = lambda source, key, down: 1000 + key * 2 + int(down)
                self.CGEventPost = lambda tap, event: log.append(("post", (tap, event)))
                self.CFRelease = lambda event: log.append(("release", event))

        with (
            mock.patch("ctypes.CDLL", return_value=Services(True)),
            mock.patch.object(smoke.time, "sleep", side_effect=lambda s: log.append(("sleep", s))),
        ):
            smoke.post_held_key(smoke.RIGHT_KEY_CODE, 0.25)

        down = 1000 + smoke.RIGHT_KEY_CODE * 2 + 1
        up = 1000 + smoke.RIGHT_KEY_CODE * 2
        self.assertEqual(log, [
            ("post", (smoke.CG_HID_EVENT_TAP, down)), ("sleep", 0.25),
            ("post", (smoke.CG_HID_EVENT_TAP, up)), ("release", down), ("release", up),
        ])

        log.clear()
        with (
            mock.patch("ctypes.CDLL", return_value=Services(False)),
            mock.patch.object(smoke.subprocess, "run"),
            mock.patch.object(smoke.time, "sleep"),
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.inject_key(smoke.RIGHT_KEY_CODE)
        self.assertEqual(log, [])
        self.assertEqual(raised.exception.availability, "unavailable")

    def test_screenshot_request_repeats_hotkey_dropped_before_frontend_is_ready(self) -> None:
        class Running:
            returncode = None

            def poll(self) -> None:
                return None

        clock = [0.0]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            requests: list[int] = []

            def inject(key_code: int) -> None:
                requests.append(key_code)
                if len(requests) == 3:  # first two requests are dropped
                    (directory / "capture.png").write_bytes(b"png" + CaptureRobustnessTest.IEND)

            def sleep(seconds: float) -> None:
                clock[0] += seconds

            with (
                mock.patch.object(smoke, "inject_key", side_effect=inject),
                mock.patch.object(smoke.time, "monotonic", side_effect=lambda: clock[0]),
                mock.patch.object(smoke.time, "sleep", side_effect=sleep),
            ):
                selected = smoke.request_screenshot(Running(), directory, {}, timeout=20.0)

            self.assertEqual(selected, directory / "capture.png")
            self.assertEqual(requests, [smoke.SCREENSHOT_KEY_CODE] * 3)

            with (
                mock.patch.object(smoke, "inject_key", side_effect=lambda key_code: requests.append(key_code)),
                mock.patch.object(smoke.time, "monotonic", side_effect=lambda: clock[0]),
                mock.patch.object(smoke.time, "sleep", side_effect=sleep),
            ):
                requests.clear()
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.request_screenshot(Running(), directory, smoke.screenshot_snapshot(directory), timeout=3.0)
            self.assertEqual(raised.exception.stage, "video")
            self.assertLessEqual(len(requests), 4)  # bounded by timeout / retry interval

    def test_frontend_config_captures_raw_core_frame_without_osd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            text = smoke.write_frontend_config(work, work / "screenshots").read_text(encoding="utf-8")
        self.assertIn('video_gpu_screenshot = "false"', text)
        self.assertIn('notification_show_screenshot = "false"', text)
        self.assertIn('input_screenshot = "f8"', text)

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
            mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
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


class LaunchWindowTest(unittest.TestCase):
    """GWR-05a: a termination signal during the frontend launch is deferred, never lost (T-04-66)."""

    def install(self) -> dict[int, object]:
        handlers: dict[int, object] = {}
        patcher = mock.patch.object(
            smoke.signal, "signal", side_effect=lambda signum, handler: handlers.__setitem__(signum, handler))
        patcher.start()
        self.addCleanup(patcher.stop)
        smoke.install_signal_cleanup()
        return handlers

    def test_launch_window_defers_a_signal_and_raises_on_exit(self) -> None:
        handlers = self.install()
        handler = handlers[signal.SIGTERM]
        with self.assertRaises(smoke.SmokeBlocked) as raised:
            with smoke.launch_window():
                handler(signal.SIGTERM, None)  # type: ignore[operator]
                inside = True
        self.assertTrue(inside)
        self.assertEqual(raised.exception.stage, "interrupted")
        # The second-signal guards are installed before the raise.
        self.assertEqual(handlers[signal.SIGTERM], signal.SIG_IGN)

    def test_launch_window_without_a_signal_exits_quietly(self) -> None:
        self.install()
        with smoke.launch_window():
            pass

    def test_handler_outside_the_launch_window_raises_immediately(self) -> None:
        handlers = self.install()
        with self.assertRaises(smoke.SmokeBlocked) as raised:
            handlers[signal.SIGHUP](signal.SIGHUP, None)  # type: ignore[operator]
        self.assertEqual(raised.exception.stage, "interrupted")

    def test_signal_during_popen_still_records_and_kills_the_child(self) -> None:
        handlers = self.install()
        process = SingleInstanceTest.Running(pid=4321)
        with tempfile.TemporaryDirectory() as temporary:
            pid_file = Path(temporary) / "child.pid"
            args = mock.Mock(timeout=1.0, child_pid_file=pid_file)

            def popen(*_a: object, **_k: object) -> object:
                handlers[signal.SIGTERM](signal.SIGTERM, None)  # type: ignore[operator]
                return process

            with (
                mock.patch.object(smoke, "validate_inputs", return_value=(
                    Path("/app"), Path("/core"), Path("/fixture"),
                    {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER})),
                mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
                mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
                mock.patch.object(smoke, "collect_frontend_output", return_value=""),
                mock.patch.object(smoke, "request_frontend_quit") as quit_frontend,
                mock.patch.object(smoke, "kill_launched_group") as kill_group,
                mock.patch.object(smoke.subprocess, "Popen", side_effect=popen),
                mock.patch.object(smoke.time, "sleep"),
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)
            self.assertEqual(raised.exception.stage, "interrupted")
            self.assertEqual(pid_file.read_text(encoding="utf-8"), "4321\n")
        quit_frontend.assert_called_once()
        kill_group.assert_called_once_with(process)

    def test_g2wr_06_deferred_signal_survives_a_raising_body(self) -> None:
        handlers = self.install()
        body_error = OSError("x")
        with self.assertRaises(smoke.SmokeBlocked) as raised:
            with smoke.launch_window():
                handlers[signal.SIGTERM](signal.SIGTERM, None)  # type: ignore[operator]
                raise body_error
        self.assertEqual(raised.exception.stage, "interrupted")
        self.assertIs(raised.exception.__cause__, body_error)
        self.assertIsNone(smoke._LAUNCH_WINDOW["pending"])
        self.assertFalse(smoke._LAUNCH_WINDOW["open"])

    def test_g2wr_06_body_error_without_signal_propagates_unchanged(self) -> None:
        self.install()
        body_error = OSError("x")
        with self.assertRaises(OSError) as raised:
            with smoke.launch_window():
                raise body_error
        self.assertIs(raised.exception, body_error)

    def test_g2wr_06_pid_record_failure_is_not_a_launch_failure(self) -> None:
        self.install()
        process = SingleInstanceTest.Running(pid=4321)
        args = mock.Mock(timeout=1.0, child_pid_file=Path("child.pid"))
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=(
                Path("/app"), Path("/core"), Path("/fixture"),
                {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER})),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
            mock.patch.object(smoke, "collect_frontend_output", return_value=""),
            mock.patch.object(smoke, "record_child_pid", side_effect=OSError("disk full")),
            mock.patch.object(smoke, "request_frontend_quit") as quit_frontend,
            mock.patch.object(smoke, "kill_launched_group") as kill_group,
            mock.patch.object(smoke.subprocess, "Popen", return_value=process),
            mock.patch.object(smoke.time, "sleep"),
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.run_smoke(args)
        self.assertEqual(raised.exception.stage, "pid-record")
        self.assertNotIn("could not be started", str(raised.exception))
        quit_frontend.assert_called_once()
        kill_group.assert_called_once_with(process)

    def probe_with(self, *, popen: dict[str, object], pid_record: dict[str, object]) -> tuple[dict[str, object], mock.Mock, mock.Mock]:
        """Run `run_launch_probe` with every host operation mocked (G3WR-03)."""
        self.install()
        try:
            with (
                mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
                mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
                mock.patch.object(smoke, "collect_frontend_output", return_value=""),
                mock.patch.object(smoke, "find_recent_crash_reason", return_value=None),
                mock.patch.object(smoke, "record_child_pid", **pid_record),
                mock.patch.object(smoke, "request_frontend_quit"),
                mock.patch.object(smoke, "reap_frontend", return_value=None) as reap,
                mock.patch.object(smoke, "kill_launched_group") as kill_group,
                mock.patch.object(smoke.subprocess, "Popen", **popen),
                mock.patch.object(smoke, "DIAGNOSTIC_PROBE_SECONDS", 0.01),
            ):
                record = smoke.run_launch_probe(
                    Path("/RetroArch"), Path("/core"), Path("/fixture"), "org.example.RetroArch",
                    probe="no_content", timeout=1, child_pid_file=Path("child.pid"),
                )
        except Exception as error:  # noqa: BLE001 - RED discipline: report, never error
            self.fail(f"uncaught {type(error).__name__}")
        return record, kill_group, reap

    def test_g3wr_03_probe_pid_record_failure_is_not_a_launch_failure(self) -> None:
        process = SingleInstanceTest.Running(pid=4321)
        record, kill_group, reap = self.probe_with(
            popen={"return_value": process}, pid_record={"side_effect": OSError("disk full")})
        self.assertEqual(record["diagnostic"]["stage"], "pid-record")
        self.assertIsNone(record["survived_window"])
        self.assertIsNone(record["return_code"])
        self.assertIn("OSError", record["diagnostic"]["output"])
        kill_group.assert_called_once_with(process)
        reap.assert_not_called()

    def test_g3wr_03_probe_popen_failure_is_still_launch(self) -> None:
        record, kill_group, _reap = self.probe_with(
            popen={"side_effect": OSError("no such file")}, pid_record={"return_value": None})
        self.assertEqual(record["diagnostic"]["stage"], "launch")
        self.assertIs(record["survived_window"], False)
        kill_group.assert_not_called()

    def test_g3wr_03_compare_launch_probes_reports_pid_record(self) -> None:
        failed = {"survived_window": None, "diagnostic": {"stage": "pid-record"}}
        ok = {"survived_window": True, "diagnostic": {"stage": "no-content-startup"}}
        self.assertEqual(smoke.compare_launch_probes(failed, ok), "diagnostic-pid-record-failed")
        self.assertEqual(smoke.compare_launch_probes(ok, failed), "diagnostic-pid-record-failed")
        self.assertEqual(smoke.compare_launch_probes(ok, ok), "both-launch-probes-survived")
        dead = {"survived_window": False, "diagnostic": {"stage": "launch"}}
        self.assertEqual(smoke.compare_launch_probes(dead, ok), "frontend-startup-failed")

    def test_g3wr_03_run_diagnostics_reports_pid_record_finding(self) -> None:
        failed = {"survived_window": None, "diagnostic": {"stage": "pid-record"}}
        ok = {"survived_window": True, "diagnostic": {"stage": "core-content-load"}}
        args = mock.Mock(timeout=1.0, child_pid_file=None)
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=(
                Path("/app"), Path("/core"), Path("/fixture"), {"bundle_id": "org.example.RetroArch"})),
            mock.patch.object(smoke, "run_launch_probe", side_effect=[failed, ok]),
        ):
            result = smoke.run_diagnostics(args)
        self.assertEqual(result["finding"], "diagnostic-pid-record-failed")

    def test_launch_window_does_not_use_a_signal_mask(self) -> None:
        source = Path(smoke.__file__).read_text(encoding="utf-8")
        calls = [line for line in source.splitlines()
                 if "pthread_sigmask(" in line and not line.lstrip().startswith("#")]
        self.assertEqual(calls, [], "a blocked mask would be inherited by the frontend")


class LeaderSweepTest(unittest.TestCase):
    """GWR-05b: liveness checks do not reap, and the group is swept while the leader pins it."""

    def spawn(self, script: str) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(["/bin/sh", "-c", script], stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(self.finish, process)
        return process

    def finish(self, process: subprocess.Popen[bytes]) -> None:
        self.kill_group(process.pid)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        if process.stdout is not None:
            process.stdout.close()

    @staticmethod
    def kill_group(pid: int) -> None:
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass

    @staticmethod
    def gone(pid: int, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.05)
        return False

    def test_frontend_exited_does_not_reap(self) -> None:
        process = self.spawn("exit 3")
        deadline = time.monotonic() + 5
        while not smoke.frontend_exited(process) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(smoke.frontend_exited(process))
        self.assertIsNone(process.returncode, "the liveness check reaped the leader")
        self.assertEqual(smoke.reap_frontend(process, 2.0), 3)
        self.assertEqual(process.returncode, 3)

    def test_frontend_exited_is_false_for_a_running_leader(self) -> None:
        process = self.spawn("sleep 30")
        self.assertFalse(smoke.frontend_exited(process))

    def test_reap_frontend_returns_none_when_the_leader_outlives_the_timeout(self) -> None:
        process = self.spawn("sleep 30")
        self.assertIsNone(smoke.reap_frontend(process, 0.2))

    def test_reap_frontend_sweeps_the_group_of_an_exited_leader(self) -> None:
        process = self.spawn("sleep 60 </dev/null >/dev/null 2>&1 & echo $!; exit 0")
        helper = int(process.stdout.readline())  # type: ignore[union-attr]
        self.assertEqual(smoke.reap_frontend(process, 5.0), 0)
        self.assertTrue(self.gone(helper), "a helper in the frontend group outlived cleanup")

    def test_group_sweep_happens_before_the_leader_is_reaped(self) -> None:
        process = self.spawn("exit 0")
        seen: list[int | None] = []
        real_killpg = os.killpg

        def killpg(pgid: int, signum: int) -> None:
            seen.append(process.returncode)
            real_killpg(pgid, signum)

        with mock.patch.object(smoke.os, "killpg", side_effect=killpg):
            smoke.reap_frontend(process, 5.0)
        self.assertEqual(seen, [None], "killpg must run exactly once, while the leader is unreaped")

    def test_kill_launched_group_sweeps_an_exited_but_unreaped_leader(self) -> None:
        process = self.spawn("sleep 60 </dev/null >/dev/null 2>&1 & echo $!; exit 0")
        helper = int(process.stdout.readline())  # type: ignore[union-attr]
        deadline = time.monotonic() + 5
        while not smoke.frontend_exited(process) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertIsNone(process.returncode)
        smoke.kill_launched_group(process)
        self.assertTrue(self.gone(helper), "the sweep skipped an exited but unreaped leader")
        self.assertIsNotNone(process.returncode)

    def test_kill_launched_group_never_signals_after_the_leader_is_reaped(self) -> None:
        process = self.spawn("exit 0")
        process.wait(timeout=5)
        with mock.patch.object(smoke.os, "killpg") as killpg:
            smoke.kill_launched_group(process)
        killpg.assert_not_called()

    def test_liveness_is_routed_through_the_non_reaping_helpers(self) -> None:
        source = Path(smoke.__file__).read_text(encoding="utf-8")
        direct = [line for line in source.splitlines()
                  if re.search(r"process\.(poll|wait)\(", line)]
        self.assertLessEqual(len(direct), 3, direct)
        self.assertIn("WNOWAIT", source)


if __name__ == "__main__":
    unittest.main()
