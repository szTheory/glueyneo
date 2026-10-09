#!/usr/bin/env python3
"""Fail-closed snapshot tests for the playable qualification runner."""

from __future__ import annotations

import hashlib
import copy
import io
import os
from pathlib import Path
import re
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


class ConsumerInputTest(unittest.TestCase):
    def copy_documentation(self, source_root: Path) -> Path:
        guide = source_root / "docs/first-playable-build.md"
        guide.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "docs/first-playable-build.md", guide)
        validation = source_root / ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md"
        validation.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md", validation)
        return validation

    def test_check_docs_accepts_controlled_review_states_and_pending_frontend_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-docs-positive-") as temporary:
            self.copy_documentation(Path(temporary))
            try:
                playable.check_docs(Path(temporary))
            except RuntimeError as error:
                self.fail(f"valid controlled states and Pending/unknown evidence were rejected: {error}")

    def test_check_docs_rejects_affirmative_frontend_claims_in_build_guide(self) -> None:
        claims = (
            "The actual frontend app loaded successfully and displayed pixels.",
            "The frontend accepted RIGHT input and unloaded cleanly.",
            "The game appeared on screen in RetroArch.",
            "The game ran successfully in RetroArch.",
            "The frontend accepted the mapped controller input.",
            "The frontend successfully presented the game to the user.",
            "Gameplay was confirmed in RetroArch.",
            "The frontend booted the game and showed its output.",
            "The controls worked as expected in RetroArch.",
            "A frame was rendered to the window.",
            "The screen was visible and video output was confirmed.",
            "The controls worked as expected in RetroArch.",
            "RetroArch exited normally after content unloaded.",
            "No screenshot was obtained, but the game appeared on screen in RetroArch.",
            "The app did not fail; the game appeared on screen in RetroArch.",
        )
        for claim in claims:
            with self.subTest(claim=claim), tempfile.TemporaryDirectory(prefix="playable-docs-guide-claim-") as temporary:
                source_root = Path(temporary)
                self.copy_documentation(source_root)
                guide = source_root / "docs/first-playable-build.md"
                guide.write_text(guide.read_text(encoding="utf-8") + "\n" + claim + "\n", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "affirmative frontend claim"):
                    playable.check_docs(source_root)

    def test_check_docs_allows_explicit_negation_of_frontend_claim(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-docs-negated-claim-") as temporary:
            source_root = Path(temporary)
            self.copy_documentation(source_root)
            guide = source_root / "docs/first-playable-build.md"
            guide.write_text(
                guide.read_text(encoding="utf-8")
                + "\nThe guide does not claim that the app loaded successfully. The guide does not claim that the game appeared on screen in RetroArch.\n",
                encoding="utf-8",
            )
            playable.check_docs(source_root)

    def test_check_docs_does_not_let_an_earlier_denial_mask_a_later_claim(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-docs-separated-claims-") as temporary:
            source_root = Path(temporary)
            self.copy_documentation(source_root)
            guide = source_root / "docs/first-playable-build.md"
            guide.write_text(
                guide.read_text(encoding="utf-8")
                + "\nThe guide does not claim that the app loaded successfully. A frame was rendered to the window.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "affirmative frontend claim"):
                playable.check_docs(source_root)

    def test_check_docs_rejects_reverse_order_guest_pixel_claim(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-docs-reversed-pixels-") as temporary:
            source_root = Path(temporary)
            self.copy_documentation(source_root)
            guide = source_root / "docs/first-playable-build.md"
            guide.write_text(
                guide.read_text(encoding="utf-8") + "\nGuest pixels were displayed.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "affirmative frontend claim"):
                playable.check_docs(source_root)

    def test_check_docs_rejects_placeholders_and_missing_or_closed_frontend_evidence(self) -> None:
        def update_row(text: str, task_id: str, status: str | None) -> str:
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if line.startswith(f"| {task_id} |"):
                    if status is None:
                        del lines[index]
                    else:
                        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                        cells[-1] = status
                        lines[index] = "| " + " | ".join(cells) + " |"
                    return "\n".join(lines) + "\n"
            raise AssertionError(f"validation row {task_id} is missing")

        mutations = (
            ("TBD", lambda text: re.sub(
                r"(?m)^(\| CR-03 \|[^|]*\|[^|]*\|)[^|]*(\|)$", r"\1 TBD \2", text, count=1,
            ), "controlled review disposition"),
            ("planned", lambda text: update_row(
                text, "04-15 T2", "HOST-02 planned; frontend QUAL-03 Pending; actual-app identities unavailable; frontend claim unknown",
            ), "unfinished placeholder"),
            ("missing frontend row", lambda text: update_row(text, "04-15 T2", None), "Pending/unknown"),
            ("false frontend closure", lambda text: update_row(
                text, "04-15 T2", "HOST-02 pass; frontend QUAL-03 pass; actual-app evidence unavailable; frontend claim unknown",
            ), "Pending/unknown"),
            ("mixed pending and collective closure", lambda text: update_row(
                text, "04-15 T2", "HOST-02 Pending; frontend QUAL-03 Pending; frontend claim unknown; both requirements pass",
            ), "Pending/unknown"),
            *[
                (f"mixed pending and affirmative frontend claim: {claim}", lambda text, claim=claim: update_row(
                    text, "04-15 T2",
                    f"HOST-02 Pending; frontend QUAL-03 Pending; actual-app identities and observations unavailable; frontend app {claim}; frontend claim unknown",
                ), "Pending/unknown")
                for claim in ("loaded successfully", "pixels were presented", "accepted RIGHT input", "unloaded cleanly")
            ],
            *[
                (f"mixed pending and {claim} closure", lambda text, claim=claim: update_row(
                    text, "04-15 T2", f"HOST-02 Pending; frontend QUAL-03 Pending; frontend claim unknown; HOST-02 {claim}",
                ), "Pending/unknown")
                for claim in ("pass", "passed", "closed", "complete", "completed", "verified", "satisfied")
            ],
            ("missing unknown claim", lambda text: update_row(
                text, "04-15 T2", "HOST-02 Pending; frontend QUAL-03 Pending; actual-app identities unavailable",
            ), "Pending/unknown"),
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


if __name__ == "__main__":
    unittest.main()
