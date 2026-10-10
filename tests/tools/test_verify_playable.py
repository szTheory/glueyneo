#!/usr/bin/env python3
"""Fail-closed snapshot tests for the playable qualification runner."""

from __future__ import annotations

import hashlib
import copy
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
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

    def test_repository_receipt_rejects_forged_file_rows_after_aggregate_recompute(self) -> None:
        self.commit_fixture_project()
        script = self.repository / "tests/libretro/test_smoke.py"
        script.chmod(0o755)
        subprocess.run(["git", "-C", str(self.repository), "add", "tests/libretro/test_smoke.py"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "commit", "-qm", "executable source"], check=True)
        commit = subprocess.run(
            ["git", "-C", str(self.repository), "rev-parse", "HEAD"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        original = playable.snapshot_record(snapshot)
        self.assertIsNone(playable.validate_snapshot_record(original, repository=self.repository))
        target_index = next(i for i, row in enumerate(original["entries"]) if row["path"] == "writer.c")

        forged_rows = (
            {"sha256": "0" * 64},
            {"bytes": original["entries"][target_index]["bytes"] + 1},
            {"mode": "executable"},
        )
        for change in forged_rows:
            with self.subTest(change=change):
                record = copy.deepcopy(original)
                record["entries"][target_index].update(change)
                record["inventory_sha256"] = playable.inventory_digest(record["entries"])
                with self.assertRaises(playable.SnapshotError) as raised:
                    playable.validate_snapshot_record(record, repository=self.repository)
                self.assertTrue(raised.exception.reason.startswith("snapshot-record-"))

    def test_repository_receipt_rejects_boolean_numeric_fields(self) -> None:
        (self.repository / "one-byte").write_bytes(b"x")
        subprocess.run(["git", "-C", str(self.repository), "add", "one-byte"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "commit", "-qm", "one byte"], check=True)
        snapshot = playable.create_snapshot(self.repository, "HEAD", self.base / "snapshot")
        original = playable.snapshot_record(snapshot)
        playable.validate_snapshot_record(original, repository=self.repository)
        for field, value in (("bytes", True), ("entry_count", True),
                             ("file_count", True), ("symlink_count", False)):
            with self.subTest(field=field):
                record = copy.deepcopy(original)
                if field == "bytes":
                    record["entries"][0][field] = value
                else:
                    record[field] = value
                record["inventory_sha256"] = playable.inventory_digest(record["entries"])
                with self.assertRaises(playable.SnapshotError) as raised:
                    playable.validate_snapshot_record(record, repository=self.repository)
                self.assertEqual(raised.exception.reason, "snapshot-record-invalid")

    def test_ambiguous_private_paths_are_removed_from_retained_and_printed_evidence(self) -> None:
        for root in ("/Users/private-person", "/Volumes/synthetic", "/tmp/synthetic",
                     "/private/var/folders/private-person", str(ROOT), str(Path.home())):
            for component in ("private,tail", "private:tail", "private in tail"):
                for quote in ("", '"', "'"):
                    with self.subTest(root_kind=root.split("/")[1], component=component, quoted=bool(quote)):
                        path = f"{root}/{component}/sensitive.bin"
                        diagnostic = f"compile failed status 7: {quote}{path}{quote}"
                        safe = playable.redact(diagnostic)
                        self.assertNotIn(component, safe)
                        self.assertNotIn("sensitive.bin", safe)
                        self.assertIn("compile failed status 7", safe)
                        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
                            output = Path(temporary) / "qualification"
                            stdout = io.StringIO()
                            receipt = {"status": "fail", "reason": diagnostic,
                                       "fixture": {}, "retroarch_smoke": {}, "identity": {}}
                            with mock.patch.object(playable, "OUTPUT", output), mock.patch("sys.stdout", stdout):
                                playable._write_receipt(receipt)
                            retained = (output / "receipt.json").read_text() + stdout.getvalue()
                        self.assertNotIn(component, retained)
                        self.assertNotIn("sensitive.bin", retained)
                        self.assertIn("compile failed status 7", retained)

    def test_repository_receipt_rejects_forged_symlink_target_after_aggregate_recompute(self) -> None:
        self.commit_fixture_project()
        (self.repository / "inside-link").symlink_to("writer.c")
        subprocess.run(["git", "-C", str(self.repository), "add", "inside-link"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "commit", "-qm", "safe symlink"], check=True)
        commit = subprocess.run(
            ["git", "-C", str(self.repository), "rev-parse", "HEAD"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        record = playable.snapshot_record(snapshot)
        link = next(row for row in record["entries"] if row["path"] == "inside-link")
        link["target"] = "tests/libretro/test_smoke.py"
        target = link["target"].encode("utf-8")
        link["bytes"] = len(target)
        link["sha256"] = hashlib.sha256(target).hexdigest()
        record["inventory_sha256"] = playable.inventory_digest(record["entries"])

        with self.assertRaises(playable.SnapshotError) as raised:
            playable.validate_snapshot_record(record, repository=self.repository)
        self.assertEqual(raised.exception.reason, "snapshot-record-source-mismatch")

    def test_repository_receipt_rejects_path_type_count_and_archive_digest_changes(self) -> None:
        commit = self.commit_fixture_project()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        original = playable.snapshot_record(snapshot)

        path_change = copy.deepcopy(original)
        writer = next(row for row in path_change["entries"] if row["path"] == "writer.c")
        writer["path"] = "writer-renamed.c"
        path_change["entries"].sort(key=lambda row: row["path"].encode("utf-8"))
        path_change["inventory_sha256"] = playable.inventory_digest(path_change["entries"])
        type_change = copy.deepcopy(original)
        type_change["entries"][0]["type"] = "unknown"
        count_change = copy.deepcopy(original)
        count_change["entry_count"] += 1
        archive_change = copy.deepcopy(original)
        archive_change["archive_sha256"] = "0" * 64

        for record in (path_change, type_change, count_change, archive_change):
            with self.subTest(record=record):
                with self.assertRaises(playable.SnapshotError):
                    playable.validate_snapshot_record(record, repository=self.repository)

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
            'build failed status 9: "/Users/private-person home/private capture/secret.rom": permission denied',
            "compile failed exit 7: /tmp/temporary work/secret object.o",
            "tool failed status 9: /private/var/folders/private-person/private cache/run output/tool",
            "frontend failed exit 2: /Volumes/private drive/private media/secret.rom",
        )

        for diagnostic in diagnostics:
            with self.subTest(diagnostic=diagnostic.split(":", 1)[0]):
                safe = playable.redact(diagnostic)
                for private in ("synthetic home", "private capture", "secret.rom", "temporary work",
                                "secret object.o", "private cache", "run output", "private drive",
                                "private media"):
                    self.assertNotIn(private, safe)
                self.assertRegex(safe, r"(?:build|compile|tool|frontend) failed")
                self.assertRegex(safe, r"(?:exit 7|status 9|exit 2)")

    def test_redact_json_escaped_quotes_and_apostrophes_across_sinks(self) -> None:
        diagnostics = (
            'build failed status 9: "/Users/private-person home/private capture/secret\\"tail.rom" permission denied',
            "build failed status 8: '/Users/private-person home/O'Brien/private secret.rom' permission denied",
            'failed status 7: "/Users/private-person/private"tail/sensitive.bin"',
        )
        for diagnostic, private_parts in zip(
            diagnostics,
            (("synthetic home", "private capture", "secret", "tail.rom"),
             ("synthetic home", "O'Brien", "private secret", "secret.rom"),
             ("/Users/private-person/private", "tail/sensitive.bin")),
        ):
            with self.subTest(diagnostic=diagnostic):
                safe = playable.redact(diagnostic)
                self.assertEqual(playable.redact(safe), safe)
                for private in private_parts:
                    self.assertNotIn(private, safe)
                self.assertRegex(safe, r"(?:build failed status|failed status)")

        commit = self.commit_fixture_project()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        work = self.base / "qualification"
        work.mkdir()
        runner = playable.Runner(work, snapshot.root, snapshot)
        output = diagnostics[2]
        with mock.patch.object(playable.subprocess, "run", return_value=subprocess.CompletedProcess(
            ["tool"], 9, output,
        )):
            result = runner.command("quoted-path", ["tool", output], allow_failure=True)
        retained_log = (work / "quoted-path.log").read_text(encoding="utf-8")
        self.assertIn("exit_code': 9", repr(runner.lanes))
        self.assertIn("status", result.stdout)
        for private in ("/Users/private-person/private", "tail/sensitive.bin"):
            self.assertNotIn(private, retained_log + repr(runner.lanes) + result.stdout)

        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "qualification"
            receipt = {
                "status": "fail", "reason": diagnostics[2],
                "fixture": {}, "retroarch_smoke": {}, "identity": {},
            }
            stdout = io.StringIO()
            with mock.patch.object(playable, "OUTPUT", output_dir), mock.patch("sys.stdout", stdout):
                playable._write_receipt(receipt)
            serialized = (output_dir / "receipt.json").read_text(encoding="utf-8") + stdout.getvalue()
        for private in ("/Users/private-person/private", "tail/sensitive.bin"):
            self.assertNotIn(private, serialized)
        self.assertIn('"status": "fail"', serialized)

    def test_newline_private_path_suffix_is_removed_from_qualification_sinks(self) -> None:
        for root in ("/Users/private-person", "/tmp/synthetic-temp-root"):
            diagnostic = f"compile failed status 7: {root}/private\n/tail/sensitive.bin"
            with self.subTest(root_kind=root.split("/")[1]):
                safe = playable.redact(diagnostic)
                self.assertEqual(playable.redact(safe), safe)
                self.assertIn("compile failed status 7", safe)
                self.assertNotIn("/tail/sensitive.bin", safe)
                self.assertNotIn("private", safe)

        diagnostic = "compile failed status 7: /tmp/synthetic-temp-root/private\n/tail/sensitive.bin"
        commit = self.commit_fixture_project()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        work = self.base / "qualification"
        work.mkdir()
        runner = playable.Runner(work, snapshot.root, snapshot)
        with mock.patch.object(playable.subprocess, "run", return_value=subprocess.CompletedProcess(
            ["tool"], 7, diagnostic,
        )):
            result = runner.command("newline-path", ["tool", diagnostic], allow_failure=True)

        retained = ((work / "newline-path.log").read_text(encoding="utf-8")
                    + repr(runner.lanes) + result.stdout)
        self.assertIn("status 7", retained)
        self.assertNotIn("/tail/sensitive.bin", retained)
        self.assertNotIn("private", retained)
        self.assertEqual(playable.redact(result.stdout), result.stdout)

        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "qualification"
            stdout = io.StringIO()
            receipt = {
                "status": "fail", "reason": diagnostic,
                "fixture": {}, "retroarch_smoke": {}, "identity": {},
            }
            with mock.patch.object(playable, "OUTPUT", output_dir), mock.patch("sys.stdout", stdout):
                playable._write_receipt(receipt)
            serialized = (output_dir / "receipt.json").read_text(encoding="utf-8") + stdout.getvalue()

        self.assertIn('"status": "fail"', serialized)
        self.assertNotIn("/tail/sensitive.bin", serialized)
        self.assertNotIn("private", serialized)

    def test_runner_redacts_command_metadata_and_persisted_log(self) -> None:
        commit = self.commit_fixture_project()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        work = self.base / "qualification"
        work.mkdir()
        runner = playable.Runner(work, snapshot.root, snapshot)
        private_argument = "/Volumes/private drive/private capture/secret.rom"
        emitted = f"tool failed exit 6: {private_argument}"
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
            reason = "failed exit 12 at /Users/private-person home/private capture/secret.rom"
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


class ProcessGroupTest(unittest.TestCase):
    """WR-03 and the RetroArch lane instance assertions (CR-07, T-04-54)."""

    def make_runner(self, work: Path) -> "playable.Runner":
        return playable.Runner(work, work, None)  # type: ignore[arg-type]

    def test_timeout_kills_the_whole_lane_group_and_keeps_partial_output(self) -> None:
        program = (
            "import subprocess, sys, time\n"
            "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print('grandchild', g.pid, flush=True)\n"
            "time.sleep(60)\n"
        )
        with tempfile.TemporaryDirectory(prefix="lane-group-") as temporary:
            work = Path(temporary)
            runner = self.make_runner(work)
            with mock.patch.object(playable, "verify_snapshot"):
                result = runner.command("group-lane", [sys.executable, "-c", program],
                                        timeout=2, allow_failure=True)
            log = (work / "group-lane.log").read_text(encoding="utf-8")
            match = re.search(r"grandchild (\d+)", log)
            self.assertIsNotNone(match, log)
            pid = int(match.group(1))  # type: ignore[union-attr]
            self.addCleanup(lambda: self.kill_quietly(pid))
            self.assertEqual(result.returncode, -1)
            self.assertIn("TimeoutExpired", log)
            deadline = time.monotonic() + 10
            alive = True
            while alive and time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    alive = False
            self.assertFalse(alive, f"grandchild survived: pid {pid}")

    @staticmethod
    def kill_quietly(pid: int) -> None:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    def run_lane(self, work: Path, before: set[int] | None, after: set[int] | None,
                 *, child: str | None, group: int | None) -> tuple[dict[str, object], mock.Mock, mock.Mock, mock.Mock]:
        runner = mock.Mock()
        runner.work = work
        runner.lanes = {}

        def command(name: str, argv: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
            pid_file = Path(argv[argv.index("--child-pid-file") + 1])
            if child is not None:
                pid_file.write_text(child, encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, json.dumps({"status": "pass"}) + "\n")

        runner.command.side_effect = command
        listings = iter([before, after])
        killpg = mock.Mock()
        kill = mock.Mock()
        getpgid = mock.Mock(return_value=group) if group is not None else mock.Mock(side_effect=ProcessLookupError)
        with (
            mock.patch.object(playable, "_retroarch_pids", side_effect=lambda: next(listings)),
            mock.patch.object(playable.os, "killpg", killpg),
            mock.patch.object(playable.os, "kill", kill),
            mock.patch.object(playable.os, "getpgid", getpgid),
        ):
            receipt, reason = playable.run_frontend_smoke_lane(
                runner, work, Path("/RetroArch.app"), Path("/core"), Path("/fixture"))
        return {"receipt": receipt, "reason": reason}, runner, killpg, kill

    def test_lane_is_refused_when_an_instance_already_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outcome, runner, killpg, kill = self.run_lane(
                Path(temporary), {7}, None, child=None, group=None)
        self.assertEqual(outcome["reason"], "retroarch-instance-already-running")
        runner.command.assert_not_called()
        killpg.assert_not_called()
        kill.assert_not_called()

    def test_lane_is_refused_when_enumeration_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outcome, runner, _, _ = self.run_lane(Path(temporary), None, None, child=None, group=None)
        self.assertEqual(outcome["reason"], "retroarch-instance-unknown")
        runner.command.assert_not_called()

    def test_survivor_recorded_as_our_own_child_gets_one_group_sigterm(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outcome, _, killpg, kill = self.run_lane(
                Path(temporary), set(), {8}, child="8", group=8)
        self.assertEqual(outcome["reason"], "retroarch-instance-survived")
        killpg.assert_called_once_with(8, signal.SIGTERM)
        kill.assert_not_called()

    def test_foreign_survivor_is_reported_and_never_signalled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outcome, _, killpg, kill = self.run_lane(
                Path(temporary), set(), {9}, child="8", group=9)
        self.assertEqual(outcome["reason"], "retroarch-instance-survived")
        killpg.assert_not_called()
        kill.assert_not_called()

    def test_survivor_without_child_record_or_group_leadership_is_not_signalled(self) -> None:
        for child, group in ((None, 8), ("8", 5)):
            with self.subTest(child=child, group=group), tempfile.TemporaryDirectory() as temporary:
                outcome, _, killpg, kill = self.run_lane(
                    Path(temporary), set(), {8}, child=child, group=group)
            self.assertEqual(outcome["reason"], "retroarch-instance-survived")
            killpg.assert_not_called()
            kill.assert_not_called()

    def test_clean_lane_passes_through_the_smoke_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outcome, _, killpg, _ = self.run_lane(Path(temporary), set(), set(), child="8", group=None)
        self.assertIsNone(outcome["reason"])
        self.assertEqual(outcome["receipt"]["status"], "pass")  # type: ignore[index]
        killpg.assert_not_called()


class DocumentationCopies:
    """Copy the documents `check_docs` reads, with their review provenance, into a temporary root."""

    def copy_review_provenance(self, source_root: Path) -> None:
        reviewed = [line[4:].strip() for line in (ROOT / playable.REVIEW).read_text(encoding="utf-8").splitlines()
                    if line.startswith("  - ")]
        for path in (playable.SECURITY, playable.REVIEW, playable.DISPOSITION, Path("README.md"),
                     *(Path(item) for item in reviewed)):
            if (ROOT / path).is_file():
                (source_root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, source_root / path)

    def copy_documentation(self, source_root: Path) -> Path:
        """Copy the docs as they read without tracked frontend evidence."""
        for path in (playable.GUIDE, playable.VALIDATION):
            (source_root / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, source_root / path)
        self.copy_review_provenance(source_root)
        summary = json.loads((ROOT / playable.FRONTEND_EVIDENCE).read_text(encoding="utf-8"))
        guide = source_root / playable.GUIDE
        guide.write_text(guide.read_text(encoding="utf-8").replace(
            playable.frontend_status_block(summary), playable.frontend_status_block(None)), encoding="utf-8")
        validation = source_root / playable.VALIDATION
        validation.write_text(validation.read_text(encoding="utf-8").replace(
            playable.frontend_row_status(summary), playable.frontend_row_status(None)), encoding="utf-8")
        return validation

    def copy_documentation_with_evidence(self, source_root: Path) -> dict[str, object]:
        for path in (playable.GUIDE, playable.VALIDATION, playable.FRONTEND_EVIDENCE):
            (source_root / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, source_root / path)
        self.copy_review_provenance(source_root)
        return json.loads((source_root / playable.FRONTEND_EVIDENCE).read_text(encoding="utf-8"))


class ConsumerInputTest(DocumentationCopies, unittest.TestCase):
    def test_check_docs_accepts_pending_status_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-docs-pending-") as temporary:
            self.copy_documentation(Path(temporary))
            playable.check_docs(Path(temporary))

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_check_docs_accepts_complete_status_generated_from_tracked_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-docs-evidence-") as temporary:
            self.copy_documentation_with_evidence(Path(temporary))
            playable.check_docs(Path(temporary), repository=ROOT)

    def test_check_docs_rejects_forged_or_incomplete_receipt_summaries(self) -> None:
        def drop(field: str, value: str):
            return lambda summary: summary.update({field: [item for item in summary[field] if item != value]})

        mutations = (
            ("failed receipt", lambda summary: summary.update(status="fail"), "passing committed-snapshot receipt"),
            ("unknown frontend", lambda summary: summary.update(retroarch_status="unknown"),
             "passing committed-snapshot receipt"),
            ("short revision", lambda summary: summary.update(source_revision="6f91a7e"), "full committed source revision"),
            ("missing inventory digest", lambda summary: summary.pop("inventory_sha256"), "inventory digest"),
            ("unpinned app", lambda summary: summary["retroarch"].update(executable_sha256="0" * 64), "pinned RetroArch"),
            ("other fixture", lambda summary: summary.update(fixture_sha256="0" * 64), "generated public fixture"),
            ("failed lane", lambda summary: summary["lanes"].update({"shared-build": "fail"}), "every qualification lane"),
            ("missing lane", lambda summary: summary["lanes"].pop("actual-retroarch-smoke"), "every qualification lane"),
            ("arbitrary lane only", lambda summary: summary.update(lanes={"x": "pass"}), "every qualification lane"),
            ("missing LEFT control",
             drop("observations", "configured Left Arrow wrong-input control did not move the marker"),
             "required load, video, input or exit observation"),
            ("marker did not move", lambda summary: summary.update(marker_after_right=list(summary["marker_before"])),
             "marker moving right"),
            ("marker changed row", lambda summary: summary.update(
                marker_after_right=[summary["marker_after_right"][0], summary["marker_before"][1] + 1, 1]),
             "marker moving right"),
            ("no unload", lambda summary: summary.update(frontend_unloaded=False), "content unload"),
            ("private path", lambda summary: summary.update(os="macOS /" + "Users/someone/build"), "private absolute path"),
            ("non-dict retroarch", lambda summary: summary.update(retroarch="x"), "pinned RetroArch"),
            ("empty os", lambda summary: summary.update(os=""), "single-line operating system"),
            ("multi-line os", lambda summary: summary.update(os="macOS\nextra"), "single-line operating system"),
            ("malformed core digest", lambda summary: summary.update(core_sha256="xyz"), "core digest"),
            ("other input mapping", lambda summary: summary.update(input_mapping="Up Arrow"), "documented input mapping"),
            ("boolean marker", lambda summary: summary.update(marker_before=[True, 16, 1]), "marker moving right"),
        )
        for label, mutate, expected_error in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory(prefix="playable-docs-evidence-") as temporary:
                source_root = Path(temporary)
                summary = self.copy_documentation_with_evidence(source_root)
                mutate(summary)
                (source_root / playable.FRONTEND_EVIDENCE).write_text(json.dumps(summary), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, expected_error):
                    playable.check_docs(source_root)

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_tracked_receipt_must_match_its_committed_inventory(self) -> None:
        summary = json.loads((ROOT / playable.FRONTEND_EVIDENCE).read_text(encoding="utf-8"))
        self.assertIsNotNone(playable.load_frontend_evidence(ROOT))
        forged = dict(summary, inventory_sha256="0" * 64)
        with tempfile.TemporaryDirectory(prefix="playable-docs-inventory-") as temporary:
            clone = Path(temporary) / "clone"
            subprocess.run(["git", "clone", "--quiet", "--no-checkout", str(ROOT), str(clone)], check=True)
            subprocess.run(["git", "-C", str(clone), "checkout", "--quiet", summary["source_revision"]], check=True)
            (clone / playable.FRONTEND_EVIDENCE).parent.mkdir(parents=True, exist_ok=True)
            (clone / playable.FRONTEND_EVIDENCE).write_text(json.dumps(forged), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "inventory digest does not match"):
                playable.load_frontend_evidence(clone)

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_check_docs_requires_generated_status_to_match_evidence(self) -> None:
        cases = (
            ("evidence with pending block", self.copy_documentation, True, "status block does not match"),
            ("pending docs edited to complete", self.copy_documentation, False, "status block does not match"),
        )
        for label, copy, add_evidence, expected_error in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory(prefix="playable-docs-block-") as temporary:
                source_root = Path(temporary)
                copy(source_root)
                summary = json.loads((ROOT / playable.FRONTEND_EVIDENCE).read_text(encoding="utf-8"))
                guide = source_root / playable.GUIDE
                if add_evidence:
                    shutil.copyfile(ROOT / playable.FRONTEND_EVIDENCE, source_root / playable.FRONTEND_EVIDENCE)
                else:
                    guide.write_text(guide.read_text(encoding="utf-8").replace(
                        playable.frontend_status_block(None), playable.frontend_status_block(summary)), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, expected_error):
                    playable.check_docs(source_root, repository=ROOT)
        with tempfile.TemporaryDirectory(prefix="playable-docs-row-") as temporary:
            source_root = Path(temporary)
            self.copy_documentation_with_evidence(source_root)
            validation = source_root / playable.VALIDATION
            validation.write_text(validation.read_text(encoding="utf-8").replace(
                playable.frontend_row_status(summary), playable.frontend_row_status(None)), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "does not match the tracked evidence"):
                playable.check_docs(source_root, repository=ROOT)

    def test_record_frontend_evidence_summary_drops_receipt_paths(self) -> None:
        summary = json.loads((ROOT / playable.FRONTEND_EVIDENCE).read_text(encoding="utf-8"))
        receipt = {
            "status": "pass",
            "identity": {"source_revision": summary["source_revision"], "retroarch": summary["retroarch"],
                         "source_snapshot": {"inventory_sha256": summary["inventory_sha256"],
                                             "entries": [{"path": "/" + "Users/someone/x"}]}},
            "lanes": {name: {"status": status, "command": ["/" + "Users/someone/checkout"]}
                      for name, status in summary["lanes"].items()},
            "retroarch_smoke": {
                "status": "pass", "observations": summary["observations"],
                "marker_before": summary["marker_before"], "marker_after_right": summary["marker_after_right"],
                "frontend_unloaded": True,
                "identity": {"os": summary["os"], "core_sha256": summary["core_sha256"],
                             "fixture_sha256": summary["fixture_sha256"], "input_mapping": summary["input_mapping"]},
                "diagnostic": {"output": "/" + "Users/someone/private"},
            },
            "artifacts": {"tree": ["/" + "Users/someone/build/object.o"]},
        }
        self.assertEqual(playable.frontend_evidence_summary(receipt), summary)

    def test_check_docs_rejects_placeholders_and_uncontrolled_review_states(self) -> None:
        mutations = (
            ("TBD review state", lambda text: re.sub(
                r"(?m)^(\| CR-03 \|[^|]*\|[^|]*\|)[^|]*(\|)$", r"\1 TBD \2", text, count=1,
            ), "controlled review disposition"),
            ("planned frontend row", lambda text: text.replace(
                playable.frontend_row_status(None), "HOST-02 planned; frontend QUAL-03 Pending"), "unfinished placeholder"),
            ("frontend row closed without evidence", lambda text: text.replace(
                playable.frontend_row_status(None), "HOST-02 Complete; frontend QUAL-03 Complete"),
             "does not match the tracked evidence"),
        )
        for label, transform, expected_error in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory(prefix="playable-docs-negative-") as temporary:
                validation = self.copy_documentation(Path(temporary))
                original = validation.read_text(encoding="utf-8")
                mutated = transform(original)
                self.assertNotEqual(mutated, original, f"{label} mutation did not change the target row")
                validation.write_text(mutated, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, expected_error):
                    playable.check_docs(Path(temporary))

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


class EvidenceBindingTest(DocumentationCopies, unittest.TestCase):
    """Tracked frontend evidence is bound to committed bytes in every check_docs path (CR-03, WR-09, E2)."""

    def test_evidence_without_a_repository_is_never_accepted(self) -> None:
        for forged in (False, True):
            with self.subTest(forged_digest=forged), tempfile.TemporaryDirectory(prefix="playable-unbound-") as temporary:
                source_root = Path(temporary)
                summary = self.copy_documentation_with_evidence(source_root)
                if forged:
                    summary["inventory_sha256"] = "0" * 64
                    (source_root / playable.FRONTEND_EVIDENCE).write_text(json.dumps(summary), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "cannot be bound to committed bytes"):
                    playable.check_docs(source_root)

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_explicit_repository_binds_the_copied_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-bound-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            playable.check_docs(source_root, repository=ROOT)
            parent = subprocess.run(["git", "-C", str(ROOT), "rev-parse", summary["source_revision"] + "^"],
                                    check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
            with self.assertRaisesRegex(RuntimeError, "not a committed ancestor"):
                playable.check_docs(source_root, repository=ROOT, head=parent)
            summary["inventory_sha256"] = "0" * 64
            (source_root / playable.FRONTEND_EVIDENCE).write_text(json.dumps(summary), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "inventory digest does not match"):
                playable.check_docs(source_root, repository=ROOT)

    def test_clean_check_docs_binds_to_the_originating_repository_and_snapshot_commit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-main-docs-") as temporary:
            output = Path(temporary) / "out"
            snapshot = mock.Mock(commit="a" * 40, root=Path(temporary) / "source")
            with mock.patch.object(playable, "OUTPUT", output), \
                    mock.patch.object(playable, "create_snapshot", return_value=snapshot), \
                    mock.patch.object(playable, "verify_snapshot"), \
                    mock.patch.object(playable, "snapshot_record", return_value={"status": "pass"}), \
                    mock.patch.object(playable, "validate_snapshot_record"), \
                    mock.patch.object(playable, "check_docs") as check, \
                    mock.patch.object(sys, "argv", ["verify_playable.py", "--retroarch", str(Path(temporary) / "R.app"),
                                                    "--clean", "--check-docs"]), \
                    mock.patch("sys.stdout", new_callable=io.StringIO), mock.patch("sys.stderr", new_callable=io.StringIO):
                # The archived runner is absent from the stub snapshot, so main fails early but still
                # reaches the documentation gate with the snapshot in hand.
                playable.main()
        check.assert_called_once()
        self.assertEqual(check.call_args.kwargs, {"repository": ROOT, "head": "a" * 40})


class CrosswalkProvenanceTest(DocumentationCopies, unittest.TestCase):
    """The review crosswalk equals the disposition record and resolves its scopes (CR-05, E4)."""

    def mutate_row(self, transform, expected_error: str) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-crosswalk-") as temporary:
            validation = self.copy_documentation(Path(temporary))
            original = validation.read_text(encoding="utf-8")
            mutated = transform(original)
            self.assertNotEqual(mutated, original, "mutation did not change the crosswalk")
            validation.write_text(mutated, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, expected_error):
                playable.check_docs(Path(temporary))

    @staticmethod
    def with_scope(finding: str, scope: str):
        return lambda text: re.sub(rf"(?m)^(\| {finding} \|[^|]*\|)[^|]*(\|[^|]*\|)$",
                                   lambda match: f"{match.group(1)} {scope} {match.group(2)}", text, count=1)

    def test_live_crosswalk_is_accepted(self) -> None:
        text = (ROOT / playable.VALIDATION).read_text(encoding="utf-8")
        self.assertEqual(playable.crosswalk_errors(ROOT, text), [])

    def test_scope_references_must_resolve(self) -> None:
        cases = (
            ("nonexistent path (E4)", self.with_scope("CR-05", "`tools/does_not_exist.py`"),
             "scope path tools/does_not_exist.py does not exist"),
            ("existing but unreviewed path", self.with_scope("CR-05", "`README.md`"), "is not in the reviewed file list"),
            ("unregistered threat", self.with_scope("CR-05", "T-04-99"), "unknown threat T-04-99"),
            ("no reference", self.with_scope("CR-05", "n/a"), "names no threat or reviewed path"),
        )
        for label, transform, expected in cases:
            with self.subTest(case=label):
                self.mutate_row(transform, expected)

    def test_rows_must_equal_the_disposition_record(self) -> None:
        cases = (
            ("state differs", lambda text: re.sub(r"(?m)^(\| CR-01 \|[^|]*\|[^|]*\|)[^|]*(\|)$", r"\1 fixed \2", text, count=1),
             "differs from the disposition record"),
            ("severity differs", lambda text: re.sub(r"(?m)^(\| CR-01 \|)[^|]*(\|)", r"\1 warning \2", text, count=1),
             "differs from the disposition record"),
            ("deleted row", lambda text: re.sub(r"(?m)^\| IN-03 \|.*\n", "", text, count=1),
             "crosswalk findings differ from the disposition record"),
            ("extra row", lambda text: re.sub(
                r"(?m)^(\| IN-03 \|.*\n)", r"\1| CR-99 | critical | T-04-46 | open |\n", text, count=1),
             "crosswalk findings differ from the disposition record"),
            ("duplicate row", lambda text: re.sub(r"(?m)^(\| IN-03 \|.*\n)", r"\1\1", text, count=1),
             "duplicate review finding"),
        )
        for label, transform, expected in cases:
            with self.subTest(case=label):
                self.mutate_row(transform, expected)


class GuideClaimTest(DocumentationCopies, unittest.TestCase):
    """Prose outside the generated block cannot state a claim the receipt does not bind (CR-04, E3)."""

    CLAIMS = (
        "HOST-02 passed in RetroArch.",
        "QUAL-03 is done.",
        "The receipt at 706516b5a60c passed every lane.",
        "Frontend support is Complete.",
        "Pinned build Qualified.",
    )

    def guide_with(self, source_root: Path, extra: str) -> None:
        self.copy_documentation_with_evidence(source_root)
        guide = source_root / playable.GUIDE
        guide.write_text(guide.read_text(encoding="utf-8") + "\n" + extra + "\n", encoding="utf-8")

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_claims_appended_after_the_generated_block_are_rejected(self) -> None:
        for claim in self.CLAIMS:
            with self.subTest(claim=claim), tempfile.TemporaryDirectory(prefix="playable-claim-") as temporary:
                source_root = Path(temporary)
                self.guide_with(source_root, claim)
                with self.assertRaisesRegex(RuntimeError, "status claim outside the generated block"):
                    playable.check_docs(source_root, repository=ROOT)

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_digests_and_pinned_revisions_outside_the_block_are_allowed(self) -> None:
        extra = f"Digest {'ab12' * 16} and pins {playable.YMFM_REVISION} {playable.Z80_REVISION}."
        with tempfile.TemporaryDirectory(prefix="playable-claim-ok-") as temporary:
            source_root = Path(temporary)
            self.guide_with(source_root, extra)
            playable.check_docs(source_root, repository=ROOT)

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_live_guide_has_no_outside_block_claims(self) -> None:
        guide = (ROOT / playable.GUIDE).read_text(encoding="utf-8")
        self.assertEqual(playable.guide_claims_outside_block(guide), [])

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_guide_with_a_private_checkout_path_is_rejected(self) -> None:
        private = str(playable.ROOT).replace("/", "\u2215")
        with tempfile.TemporaryDirectory(prefix="playable-claim-path-") as temporary:
            source_root = Path(temporary)
            self.guide_with(source_root, f"Build in {private}/build.")
            with self.assertRaisesRegex(RuntimeError, "private absolute path"):
                playable.check_docs(source_root, repository=ROOT)


class AtomicRecordTest(DocumentationCopies, unittest.TestCase):
    """`--record-frontend-evidence` validates and scans everything before writing any file (WR-01, T-04-53)."""

    def targets(self, source_root: Path) -> list[Path]:
        return [source_root / playable.FRONTEND_EVIDENCE, source_root / playable.GUIDE, source_root / playable.VALIDATION]

    def digests(self, source_root: Path) -> list[str]:
        return [hashlib.sha256(path.read_bytes()).hexdigest() for path in self.targets(source_root)]

    def changed_summary(self, summary: dict[str, object]) -> dict[str, object]:
        changed = dict(summary)
        changed["os"] = "macOS 99.0 arm64"
        return changed

    def test_missing_validation_row_leaves_all_three_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-atomic-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            validation = source_root / playable.VALIDATION
            validation.write_text(re.sub(r"(?m)^\| 04-15 T2 \|.*\n", "", validation.read_text(encoding="utf-8")),
                                  encoding="utf-8")
            before = self.digests(source_root)
            with self.assertRaises(RuntimeError):
                playable.write_frontend_records(source_root, self.changed_summary(summary))
            self.assertEqual(self.digests(source_root), before)
            self.assertEqual(list(source_root.rglob("*.tmp")), [])

    def test_private_root_in_generated_block_leaves_all_three_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-atomic-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            before = self.digests(source_root)
            leaking = playable.frontend_status_block(summary).replace(
                playable.STATUS_END, str(playable.ROOT) + "\n" + playable.STATUS_END)
            with mock.patch.object(playable, "frontend_status_block", return_value=leaking):
                with self.assertRaises(RuntimeError):
                    playable.write_frontend_records(source_root, self.changed_summary(summary))
            self.assertEqual(self.digests(source_root), before)
            self.assertEqual(list(source_root.rglob("*.tmp")), [])

    def test_successful_write_leaves_no_temporary_sibling(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-atomic-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            before = self.digests(source_root)
            playable.write_frontend_records(source_root, self.changed_summary(summary))
            self.assertNotEqual(self.digests(source_root)[0], before[0])
            self.assertEqual(list(source_root.rglob("*.tmp")), [])


class MainErrorPathTest(unittest.TestCase):
    """Early failures still write a named fail receipt, and printed errors are redacted (CR-08, CR-09, IN-04)."""

    def run_main(self, *arguments: str) -> tuple[int, str, str]:
        with mock.patch.object(sys, "argv", ["verify_playable.py", *arguments]), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout, \
                mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            status = playable.main()
        return status, stdout.getvalue(), stderr.getvalue()

    def test_early_snapshot_failure_writes_a_named_fail_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-main-") as temporary:
            output = Path(temporary) / "out"
            failure = playable.SnapshotError(
                "runner-source-mismatch", "executing qualification runner differs from the committed archive")
            with mock.patch.object(playable, "OUTPUT", output), \
                    mock.patch.object(playable, "create_snapshot", side_effect=failure):
                status, _, _ = self.run_main("--retroarch", str(Path(temporary) / "RetroArch.app"), "--clean")
            receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(status, 1)
        self.assertEqual(receipt["status"], "fail")
        self.assertEqual(receipt["reason"], "runner-source-mismatch")
        self.assertEqual(receipt["lanes"], {})

    def test_check_docs_error_text_is_redacted(self) -> None:
        home = str(Path.home())
        failures = (OSError(2, "No such file or directory", home + "/private/guide.md"),
                    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
                    ValueError("bad value " + home + "/private/guide.md"))
        for failure in failures:
            with self.subTest(error=type(failure).__name__), \
                    mock.patch.object(playable, "check_docs", side_effect=failure):
                status, _, stderr = self.run_main("--check-docs")
            self.assertEqual(status, 1)
            self.assertNotIn(home, stderr)
            self.assertNotIn("guide.md", stderr)

    def test_record_frontend_evidence_error_text_is_redacted(self) -> None:
        for failure in (OSError(2, "No such file", str(ROOT / "receipt.json")),
                        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")):
            with self.subTest(error=type(failure).__name__), \
                    mock.patch.object(Path, "read_text", side_effect=failure):
                status, _, stderr = self.run_main("--record-frontend-evidence")
            self.assertEqual(status, 1)
            self.assertNotIn(str(ROOT), stderr)
            self.assertNotIn("receipt.json", stderr)

    def test_surviving_private_root_prints_only_the_fixed_reason(self) -> None:
        with mock.patch.object(playable, "redact", side_effect=lambda text: text), \
                mock.patch.object(playable, "check_docs", side_effect=OSError(str(Path.home()) + "/x")):
            status, _, stderr = self.run_main("--check-docs")
        self.assertEqual(status, 1)
        self.assertIn("private-path-survived", stderr)
        self.assertNotIn(str(Path.home()), stderr)


if __name__ == "__main__":
    unittest.main()
