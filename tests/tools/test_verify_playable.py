#!/usr/bin/env python3
"""Fail-closed snapshot tests for the playable qualification runner."""

from __future__ import annotations

import hashlib
import copy
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import verify_playable as playable  # noqa: E402


class SnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="playable-snapshot-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repository = self.base / "repo"
        self.repository.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repository)], check=True)
        subprocess.run(["git", "-C", str(self.repository), "config", "user.name", "Snapshot Test"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "config", "user.email", "snapshot@example.invalid"], check=True)

    def commit_fixture_project(self) -> str:
        (self.repository / "tests/fixture").mkdir(parents=True)
        (self.repository / "tests/libretro").mkdir(parents=True)
        (self.repository / "third_party/vendor/include").mkdir(parents=True)
        (self.repository / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(snapshot_fixture C)\n"
            "add_executable(fixture_writer writer.c tests/fixture/public_guest.c)\n"
            "target_include_directories(fixture_writer PRIVATE third_party/vendor/include)\n",
            encoding="utf-8",
        )
        (self.repository / "writer.c").write_text(
            "#include <fixture_vendor.h>\n"
            "int public_guest_write(const char *);\n"
            "int main(int argc, char **argv) { return argc == 2 && FIXTURE_VENDOR_ABI == 1 && public_guest_write(argv[1]) ? 0 : 1; }\n",
            encoding="utf-8",
        )
        shutil.copyfile(ROOT / "tests/fixture/public_guest.c", self.repository / "tests/fixture/public_guest.c")
        (self.repository / "third_party/vendor/include/fixture_vendor.h").write_text(
            "#define FIXTURE_VENDOR_ABI 1\n", encoding="utf-8"
        )
        (self.repository / "tests/libretro/test_smoke.py").write_text(
            "# committed source-only test input\n", encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(self.repository), "add", "CMakeLists.txt", "writer.c", "tests", "third_party"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "commit", "-qm", "fixture source"], check=True)
        return subprocess.run(
            ["git", "-C", str(self.repository), "rev-parse", "HEAD"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()

    def test_snapshot_constructor_is_available(self) -> None:
        self.assertTrue(
            callable(getattr(playable, "create_snapshot", None)),
            "qualification must materialize an immutable committed Git archive",
        )

    def test_snapshot_receipt_validator_is_available(self) -> None:
        self.assertTrue(
            callable(getattr(playable, "validate_snapshot_record", None)),
            "qualification receipts must reject missing or stale source inventory rows",
        )

    def test_dirty_and_untracked_checkout_inputs_do_not_change_snapshot_build(self) -> None:
        commit = self.commit_fixture_project()
        (self.repository / "tests/fixture/public_guest.c").write_text("#error checkout injection\n", encoding="utf-8")
        (self.repository / "third_party/vendor/include/fixture_vendor.h").write_text(
            "#error vendored checkout injection\n", encoding="utf-8"
        )
        (self.repository / "tests/libretro/test_smoke.py").write_text("raise RuntimeError('checkout injection')\n", encoding="utf-8")
        (self.repository / "injected.c").write_text("#error untracked injection\n", encoding="utf-8")
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        rows, digest = playable.verify_snapshot(snapshot)
        self.assertEqual(snapshot.commit, commit)
        self.assertEqual(snapshot.digest, digest)
        self.assertEqual(
            [row["path"] for row in rows],
            ["CMakeLists.txt", "tests/fixture/public_guest.c", "tests/libretro/test_smoke.py",
             "third_party/vendor/include/fixture_vendor.h", "writer.c"],
        )
        self.assertNotIn("injected.c", {row["path"] for row in rows})

        build = self.base / "build"
        environment = playable.clean_environment()
        subprocess.run(["cmake", "-S", str(snapshot.root), "-B", str(build), "-G", "Ninja"], check=True,
                       env=environment,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        subprocess.run(["cmake", "--build", str(build), "--parallel", "2"], check=True,
                       env=environment,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        fixture = self.base / "public-playable.bin"
        subprocess.run([str(build / "fixture_writer"), str(fixture)], check=True)
        self.assertEqual(fixture.stat().st_size, 602)
        self.assertEqual(playable.sha256(fixture), "59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0")
        playable.verify_snapshot(snapshot)

    def test_snapshot_detects_materialized_source_mutation(self) -> None:
        commit = self.commit_fixture_project()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        (snapshot.root / "writer.c").write_text("mutated\n", encoding="utf-8")
        with self.assertRaises(playable.SnapshotError) as raised:
            playable.verify_snapshot(snapshot)
        self.assertEqual(raised.exception.reason, "snapshot-inventory-mismatch")

    def test_snapshot_hashes_symlink_target_and_rejects_escape(self) -> None:
        commit = self.commit_fixture_project()
        link = self.repository / "inside-link"
        link.symlink_to("writer.c")
        subprocess.run(["git", "-C", str(self.repository), "add", "inside-link"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "commit", "-qm", "safe symlink"], check=True)
        safe_commit = subprocess.run(
            ["git", "-C", str(self.repository), "rev-parse", "HEAD"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        snapshot = playable.create_snapshot(self.repository, safe_commit, self.base / "safe-snapshot")
        row = next(row for row in snapshot.inventory if row["path"] == "inside-link")
        self.assertEqual(row["type"], "symlink")
        self.assertEqual(row["target"], "writer.c")
        self.assertEqual(row["sha256"], hashlib.sha256(b"writer.c").hexdigest())

        (self.repository / "outside-link").symlink_to("../outside")
        subprocess.run(["git", "-C", str(self.repository), "add", "outside-link"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "commit", "-qm", "escaping symlink"], check=True)
        escape_commit = subprocess.run(
            ["git", "-C", str(self.repository), "rev-parse", "HEAD"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        with self.assertRaises(playable.SnapshotError) as raised:
            playable.create_snapshot(self.repository, escape_commit, self.base / "bad-snapshot")
        self.assertEqual(raised.exception.reason, "unsafe-symlink")

    def test_snapshot_preserves_committed_executable_modes(self) -> None:
        self.commit_fixture_project()
        script = self.repository / "tests/libretro/test_smoke.py"
        script.chmod(0o755)
        subprocess.run(["git", "-C", str(self.repository), "add", "tests/libretro/test_smoke.py"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "commit", "-qm", "make smoke script executable"], check=True)
        commit = subprocess.run(
            ["git", "-C", str(self.repository), "rev-parse", "HEAD"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        row = next(row for row in snapshot.inventory if row["path"] == "tests/libretro/test_smoke.py")
        self.assertEqual(row["mode"], "executable")
        self.assertTrue(os.access(snapshot.root / row["path"], os.X_OK))

    def test_fixture_vendor_and_test_inputs_change_the_aggregate_identity(self) -> None:
        commit = self.commit_fixture_project()
        previous = playable.create_snapshot(self.repository, commit, self.base / "baseline")
        paths = (
            "tests/fixture/public_guest.c",
            "third_party/vendor/include/fixture_vendor.h",
            "tests/libretro/test_smoke.py",
        )
        for index, relative in enumerate(paths):
            path = self.repository / relative
            path.write_bytes(path.read_bytes() + f"\n/* identity probe {index} */\n".encode())
            subprocess.run(["git", "-C", str(self.repository), "add", relative], check=True)
            subprocess.run(["git", "-C", str(self.repository), "commit", "-qm", f"change {index}"], check=True)
            commit = subprocess.run(
                ["git", "-C", str(self.repository), "rev-parse", "HEAD"],
                check=True, text=True, stdout=subprocess.PIPE,
            ).stdout.strip()
            current = playable.create_snapshot(self.repository, commit, self.base / f"changed-{index}")
            self.assertNotEqual(current.digest, previous.digest, relative)
            old_row = next(row for row in previous.inventory if row["path"] == relative)
            new_row = next(row for row in current.inventory if row["path"] == relative)
            self.assertNotEqual(new_row["sha256"], old_row["sha256"], relative)
            previous = current

    def test_snapshot_receipt_rejects_missing_or_stale_inventory_rows(self) -> None:
        commit = self.commit_fixture_project()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        record = playable.snapshot_record(snapshot)
        self.assertIsNone(playable.validate_snapshot_record(record))

        missing = copy.deepcopy(record)
        missing["entries"].pop()
        missing["entry_count"] -= 1
        missing["file_count"] -= 1
        missing["inventory_sha256"] = playable.inventory_digest(missing["entries"])
        with self.assertRaises(playable.SnapshotError) as raised:
            playable.validate_snapshot_record(missing, repository=self.repository)
        self.assertEqual(raised.exception.reason, "snapshot-record-incomplete")

        stale = copy.deepcopy(record)
        stale["inventory_sha256"] = "0" * 64
        with self.assertRaises(playable.SnapshotError) as raised:
            playable.validate_snapshot_record(stale)
        self.assertEqual(raised.exception.reason, "snapshot-record-digest-mismatch")

    def test_build_environment_drops_checkout_and_toolchain_injection(self) -> None:
        with mock.patch.dict(os.environ, {
            "CFLAGS": "-include injected.h", "CMAKE_TOOLCHAIN_FILE": "/checkout/toolchain.cmake",
            "CPATH": "/checkout/include", "PYTHONPATH": "/checkout/python",
        }, clear=False):
            environment = playable.clean_environment()
        for name in ("CFLAGS", "CMAKE_TOOLCHAIN_FILE", "CPATH", "PYTHONPATH"):
            self.assertNotIn(name, environment)

    def test_generated_build_overlay_is_outside_and_removed_from_snapshot(self) -> None:
        commit = self.commit_fixture_project()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        work = self.base / "qualification"
        work.mkdir()
        overlay = work / "generated-build"
        runner = playable.Runner(work, snapshot.root, snapshot)
        runner.command(
            "overlay-control",
            [sys.executable, "-c", "from pathlib import Path; Path('build/generated.txt').write_text('output')"],
            source_build_overlay=overlay,
        )
        self.assertEqual((overlay / "generated.txt").read_text(encoding="utf-8"), "output")
        self.assertFalse((snapshot.root / "build").exists())
        playable.verify_snapshot(snapshot)

    def test_redact_removes_complete_space_containing_private_path_spans(self) -> None:
        diagnostics = (
            'build failed: "/Users/synthetic home/private capture/secret.rom": permission denied',
            "compile failed: /tmp/temporary work/secret object.o: exit 7",
            "tool failed: /private/var/folders/ab/private cache/run output/tool: status 9",
            "frontend failed: /Volumes/private drive/private media/secret.rom: exit 2",
        )

        for diagnostic in diagnostics:
            with self.subTest(diagnostic=diagnostic.split(":", 1)[0]):
                safe = playable.redact(diagnostic)
                for private in ("synthetic home", "private capture", "secret.rom", "temporary work",
                                "secret object.o", "private cache", "run output", "private drive",
                                "private media"):
                    self.assertNotIn(private, safe)
                self.assertRegex(safe, r"(?:build|compile|tool|frontend) failed")
                self.assertRegex(safe, r"(?:permission denied|exit 7|status 9|exit 2)")

    def test_runner_redacts_command_metadata_and_persisted_log(self) -> None:
        commit = self.commit_fixture_project()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        work = self.base / "qualification"
        work.mkdir()
        runner = playable.Runner(work, snapshot.root, snapshot)
        private_argument = "/Volumes/private drive/private capture/secret.rom"
        emitted = f"tool failed: {private_argument}: exit 6"
        with mock.patch.object(playable.subprocess, "run", return_value=subprocess.CompletedProcess(
            ["tool"], 6, emitted,
        )):
            result = runner.command("private-path", ["tool", private_argument], allow_failure=True)

        retained = (work / "private-path.log").read_text(encoding="utf-8") + repr(runner.lanes) + result.stdout
        self.assertNotIn("private drive", retained)
        self.assertNotIn("private capture", retained)
        self.assertNotIn("secret.rom", retained)
        self.assertIn("exit 6", retained)

    def test_receipt_writer_sanitizes_retained_and_printed_reason(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            output = Path(temporary) / "qualification"
            reason = "failed at /Users/synthetic home/private capture/secret.rom: exit 12"
            receipt = {
                "status": "fail", "reason": reason,
                "fixture": {}, "retroarch_smoke": {}, "identity": {},
            }
            stdout = io.StringIO()
            with mock.patch.object(playable, "OUTPUT", output), mock.patch("sys.stdout", stdout):
                playable._write_receipt(receipt)
            serialized = (output / "receipt.json").read_text(encoding="utf-8") + stdout.getvalue()

        self.assertNotIn("synthetic home", serialized)
        self.assertNotIn("private capture", serialized)
        self.assertNotIn("secret.rom", serialized)
        self.assertIn("exit 12", serialized)


class ConsumerInputTest(unittest.TestCase):
    def test_installed_consumer_check_uses_original_diagnostic_fixture(self) -> None:
        class CapturingRunner:
            def __init__(self) -> None:
                self.work = Path("/qualification")
                self.commands: list[tuple[str, list[str]]] = []

            def command(self, name: str, argv: list[str], **_: object) -> None:
                self.commands.append((name, argv))

        runner = CapturingRunner()
        build = Path("/qualification/static-build")
        public_fixture = build / "public-playable.bin"

        playable.run_consumer(
            runner, Path("/snapshot"), Path("/install"), public_fixture,
            Path("/install/lib/libretro/glueyneo_libretro.dylib"), "static",
        )

        check_command = runner.commands[-1][1]
        fixture = Path(check_command[check_command.index("--fixture") + 1])
        self.assertEqual(fixture, build / "diagnostic-original-a.bin")


if __name__ == "__main__":
    unittest.main()
