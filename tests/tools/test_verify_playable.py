#!/usr/bin/env python3
"""Fail-closed snapshot tests for the playable qualification runner."""

from __future__ import annotations

import contextlib
import hashlib
import copy
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def has_two_committed_revisions(root: Path = ROOT) -> bool:
    """Whether root-bound review fixtures can enforce strict parent-to-head ordering."""
    if not (root / ".git").exists():
        return False
    return subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", "HEAD^"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0


def has_bound_documentation_history(root: Path = ROOT) -> bool:
    """Whether copied-document tests can bind review order and the allowlist base in this checkout."""
    if not has_two_committed_revisions(root):
        return False
    try:
        allowlist = json.loads((root / "docs/history-allowlist.json").read_text(encoding="utf-8"))
        base = allowlist.get("base_revision") if isinstance(allowlist, dict) else None
    except (OSError, ValueError):
        return False
    if not isinstance(base, str) or not base:
        return False
    return subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0


sys.path.insert(0, str(ROOT / "tools"))
import public_content  # noqa: E402
import verify_playable as playable  # noqa: E402


class SnapshotTest(unittest.TestCase):
    def test_archive_private_sink_is_not_in_build_child_output(self) -> None:
        with mock.patch.dict(os.environ, {"GLUEYNEO_ARCHIVE_DIAGNOSTIC_DIR": str(self.base)}):
            child = subprocess.run([
                sys.executable, "-B", "-c",
                "import os; print(os.environ.get('GLUEYNEO_ARCHIVE_DIAGNOSTIC_DIR', 'unset'))",
            ], env=playable.clean_environment(), capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, 0)
        self.assertEqual(child.stdout, "unset\n")
        self.assertNotIn(str(self.base), child.stdout + child.stderr)

    def test_archive_directory_replacing_committed_file_is_diagnosed(self) -> None:
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:") as tar:
            member = tarfile.TarInfo("source.c/")
            member.type = tarfile.DIRTYPE
            tar.addfile(member)
        with self.assertRaises(playable.SnapshotError) as raised:
            playable._archive_members(archive.getvalue(), {"source.c": "file"})
        self.assertEqual(raised.exception.reason, "incomplete-archive")
        self.assertEqual(raised.exception.archive_mismatch["examples"], [
            {"path": "source.c", "expected": "file", "archived": "directory"},
        ])

    def test_archive_private_capture_is_opt_in_and_bound_to_real_git_failure(self) -> None:
        commit = self.commit_fixture_project()
        diagnostic_directory = self.base / "diagnostics"
        diagnostic_directory.mkdir()
        (self.repository / ".git/info/attributes").write_text("writer.c export-ignore\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GLUEYNEO_ARCHIVE_DIAGNOSTIC_DIR", None)
            with self.assertRaises(playable.SnapshotError) as raised:
                playable.create_snapshot(self.repository, commit, self.base / "default-off")
            self.assertEqual(raised.exception.reason, "incomplete-archive")
            self.assertEqual(list(diagnostic_directory.iterdir()), [])
        with mock.patch.dict(os.environ, {"GLUEYNEO_ARCHIVE_DIAGNOSTIC_DIR": str(diagnostic_directory)}):
            with self.assertRaises(playable.SnapshotError) as raised:
                playable.create_snapshot(self.repository, commit, self.base / "captured")
            self.assertEqual(raised.exception.reason, "incomplete-archive")
            self.assertIn("private diagnostic recorded", str(raised.exception))
            self.assertNotIn(str(diagnostic_directory), str(raised.exception))
            reports = list(diagnostic_directory.glob("glueyneo-archive-mismatch-*.json"))
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0].stat().st_mode & 0o777, 0o600)
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertEqual(report["commit"], commit)
            self.assertEqual(report["archive_sha256"], hashlib.sha256(playable._git_archive(self.repository, commit)).hexdigest())
            self.assertEqual(report["mismatch"]["examples"], [
                {"path": "writer.c", "expected": "file", "archived": None},
            ])
            child = subprocess.run([
                sys.executable, "-B", "-c",
                "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
                "import verify_playable as p\n"
                "try: p.create_snapshot(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))\n"
                "except p.SnapshotError as e: print(e); sys.exit(17)\n",
                str(ROOT / "tools"), str(self.repository), commit, str(self.base / "child"),
            ], env=os.environ.copy(), capture_output=True, text=True, timeout=10)
            self.assertEqual(child.returncode, 17, child.stderr)
            self.assertIn("private diagnostic recorded", child.stdout)
            self.assertNotIn(str(diagnostic_directory), child.stdout + child.stderr)
            self.assertEqual(len(list(diagnostic_directory.glob("*.json"))), 2)
            (self.repository / ".git/info/attributes").unlink()
            playable.create_snapshot(self.repository, commit, self.base / "matching")
            self.assertEqual(len(list(diagnostic_directory.iterdir())), 2)

    def test_archive_private_capture_rejects_in_tree_or_missing_sink_without_masking(self) -> None:
        commit = self.commit_fixture_project()
        (self.repository / ".git/info/attributes").write_text("writer.c export-ignore\n", encoding="utf-8")
        for index, directory in enumerate((self.repository, ROOT, self.base / "missing")):
            with self.subTest(index=index), mock.patch.dict(os.environ, {
                "GLUEYNEO_ARCHIVE_DIAGNOSTIC_DIR": str(directory),
            }):
                with self.assertRaises(playable.SnapshotError) as raised:
                    playable.create_snapshot(self.repository, commit, self.base / f"rejected-{index}")
                self.assertEqual(raised.exception.reason, "incomplete-archive")
                self.assertIn("private diagnostic unavailable", str(raised.exception))
                self.assertNotIn(str(directory), str(raised.exception))

    def test_archive_mismatch_diagnostics_are_bounded_and_not_public_paths(self) -> None:
        expected = {"changed": "file-executable", "missing": "file"}
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:") as tar:
            for name in ("changed", "extra-private-name"):
                member = tarfile.TarInfo(name)
                member.mode = 0o644
                member.size = 1
                tar.addfile(member, io.BytesIO(b"x"))
        with self.assertRaises(playable.SnapshotError) as raised:
            playable._archive_members(archive.getvalue(), expected)
        error = raised.exception
        self.assertEqual(error.reason, "incomplete-archive")
        self.assertIn("missing=1, extra=1, type_mismatches=1", str(error))
        self.assertNotIn("extra-private-name", str(error))
        self.assertEqual(error.archive_mismatch, {
            "expected_count": 2, "archived_count": 2,
            "missing_count": 1, "extra_count": 1, "type_mismatch_count": 1,
            "examples": [
                {"path": "changed", "expected": "file-executable", "archived": "file"},
                {"path": "extra-private-name", "expected": None, "archived": "file"},
                {"path": "missing", "expected": "file", "archived": None},
            ],
        })

    def test_archive_mismatch_diagnostic_sample_boundaries(self) -> None:
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:"):
            pass
        for count in (1, 5, 6):
            with self.subTest(count=count):
                expected = {f"missing-{index}": "file" for index in range(count)}
                with self.assertRaises(playable.SnapshotError) as raised:
                    playable._archive_members(archive.getvalue(), expected)
                diagnostic = raised.exception.archive_mismatch
                self.assertEqual(diagnostic["missing_count"], count)
                self.assertEqual(len(diagnostic["examples"]), min(count, 5))
        long_path = "a" * 300
        with self.assertRaises(playable.SnapshotError) as raised:
            playable._archive_members(archive.getvalue(), {long_path: "file"})
        self.assertEqual(raised.exception.archive_mismatch["examples"], [
            {"path": "a" * 160, "path_truncated": True, "expected": "file", "archived": None},
        ])
        files, symlinks, rows = playable._archive_members(archive.getvalue(), {})
        self.assertEqual((files, symlinks, rows), ({}, {}, ()))

    def test_archive_mismatch_diagnostics_keep_unsafe_path_gate(self) -> None:
        for name in ("/absolute", "../escape", "back\\slash", "line\nbreak"):
            with self.subTest(name=name):
                archive = io.BytesIO()
                with tarfile.open(fileobj=archive, mode="w:") as tar:
                    tar.addfile(tarfile.TarInfo(name), io.BytesIO())
                with self.assertRaises(playable.SnapshotError) as raised:
                    playable._archive_members(archive.getvalue(), {})
                self.assertEqual(raised.exception.reason, "unsafe-archive-path")
                self.assertIsNone(raised.exception.archive_mismatch)
                self.assertNotIn(name, str(raised.exception))

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

    def test_snapshot_dir_added_empty_directory_fails(self) -> None:
        commit = self.commit_fixture_project()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        (snapshot.root / "build" / "playable-qualification").mkdir(parents=True)
        with self.assertRaises(playable.SnapshotError) as raised:
            playable.verify_snapshot(snapshot)
        self.assertEqual(raised.exception.reason, "snapshot-inventory-mismatch")
        self.assertEqual(str(raised.exception), "materialized source directory set changed after archive creation")

    def test_snapshot_dir_added_nested_empty_directory_fails(self) -> None:
        commit = self.commit_fixture_project()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        (snapshot.root / "tests" / "fixture" / "__pycache__").mkdir()
        with self.assertRaises(playable.SnapshotError) as raised:
            playable.verify_snapshot(snapshot)
        self.assertEqual(raised.exception.reason, "snapshot-inventory-mismatch")
        self.assertEqual(str(raised.exception), "materialized source directory set changed after archive creation")

    def test_snapshot_dir_committed_tree_and_directory_symlink_pass(self) -> None:
        self.commit_fixture_project()
        (self.repository / "fixture-link").symlink_to("tests/fixture")
        subprocess.run(["git", "-C", str(self.repository), "add", "fixture-link"], check=True)
        subprocess.run(["git", "-C", str(self.repository), "commit", "-qm", "directory symlink"], check=True)
        commit = subprocess.run(
            ["git", "-C", str(self.repository), "rev-parse", "HEAD"],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        rows, _digest = playable.verify_snapshot(snapshot)
        self.assertEqual(rows, snapshot.inventory)
        self.assertIn("fixture-link", {row["path"] for row in rows})

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
        finished = mock.Mock(returncode=9, pid=1)
        finished.communicate.return_value = (output.encode("utf-8"), None)
        with mock.patch.object(playable.subprocess, "Popen", return_value=finished):
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
        finished = mock.Mock(returncode=7, pid=1)
        finished.communicate.return_value = (diagnostic.encode("utf-8"), None)
        with mock.patch.object(playable.subprocess, "Popen", return_value=finished):
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
        finished = mock.Mock(returncode=6, pid=1)
        finished.communicate.return_value = (emitted.encode("utf-8"), None)
        with mock.patch.object(playable.subprocess, "Popen", return_value=finished):
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

    # G5WR-02: a lane-signalling test waits (bounded, read at call time) for one child marker, lane.ready,
    # before the lane timeout starts, so a slow interpreter start cannot become an output failure.
    READY_SECONDS = 30

    def make_runner(self, work: Path) -> "playable.Runner":
        return playable.Runner(work, work, None)  # type: ignore[arg-type]

    def wait_ready(self, path: Path, seconds: float | None = None) -> None:
        bound = self.READY_SECONDS if seconds is None else seconds
        deadline = time.monotonic() + bound
        while not path.exists():
            if time.monotonic() >= deadline:
                self.fail(f"lane child never became ready: {path.name}")
            time.sleep(0.02)

    @contextlib.contextmanager
    def ready_gate(self, work: Path, argv: list[str]):  # type: ignore[no-untyped-def]
        """Make the first timed communicate of the lane argv wait for `work/lane.ready`; other Popen pass through."""
        real = subprocess.Popen
        test = self

        class ReadyPopen(real):  # type: ignore[valid-type, misc]
            waited = False

            def communicate(self, input=None, timeout=None):  # type: ignore[no-untyped-def]
                if timeout is not None and not self.waited and list(self.args) == argv:
                    self.waited = True
                    try:
                        test.wait_ready(work / "lane.ready")
                    except AssertionError:
                        with contextlib.suppress(OSError):
                            os.killpg(self.pid, signal.SIGKILL)
                        raise
                return super().communicate(input, timeout)

        with mock.patch.object(playable.subprocess, "Popen", ReadyPopen):
            yield

    def test_timeout_kills_the_whole_lane_group_and_keeps_partial_output(self) -> None:
        program = (
            "import subprocess, sys, time\n"
            "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print('grandchild', g.pid, flush=True)\n"
            "open('lane.ready', 'w').close()\n"
            "time.sleep(60)\n"
        )
        with tempfile.TemporaryDirectory(prefix="lane-group-") as temporary:
            work = Path(temporary)
            runner = self.make_runner(work)
            argv = [sys.executable, "-c", program]
            with mock.patch.object(playable, "verify_snapshot"), self.ready_gate(work, argv):
                result = runner.command("group-lane", argv, timeout=2, allow_failure=True)
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

    def test_grandchild_ignoring_sigterm_is_killed_after_a_lane_timeout(self) -> None:
        program = (
            "import signal, subprocess, sys, time\n"
            "child = ('import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)')\n"
            "g = subprocess.Popen([sys.executable, '-c', child], stdout=subprocess.DEVNULL)\n"
            "print('grandchild', g.pid, flush=True)\n"
            "open('lane.ready', 'w').close()\n"
            "time.sleep(60)\n"
        )
        with tempfile.TemporaryDirectory(prefix="lane-ignore-") as temporary:
            work = Path(temporary)
            runner = self.make_runner(work)
            argv = [sys.executable, "-c", program]
            with (
                mock.patch.object(playable, "verify_snapshot"),
                mock.patch.object(playable, "LANE_GRACE_SECONDS", 1),
                self.ready_gate(work, argv),
            ):
                result = runner.command("ignore-lane", argv, timeout=2, allow_failure=True)
            log = (work / "ignore-lane.log").read_text(encoding="utf-8")
            match = re.search(r"grandchild (\d+)", log)
            self.assertIsNotNone(match, log)
            pid = int(match.group(1))  # type: ignore[union-attr]
            self.addCleanup(lambda: self.kill_quietly(pid))
            self.assertEqual(result.returncode, -1)
            deadline = time.monotonic() + 10
            alive = True
            while alive and time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    alive = False
            self.assertFalse(alive, f"SIGTERM-ignoring grandchild survived: pid {pid}")

    def test_no_group_signal_is_sent_after_the_leader_is_reaped(self) -> None:
        for leader_exits in (True, False):
            with self.subTest(leader_exits=leader_exits):
                class Proc:
                    pid = 424242
                    returncode: int | None = None

                    def communicate(self, timeout: float | None = None) -> tuple[bytes, None]:
                        self.returncode = 0  # reaping happens here
                        return (b"partial\n", None)

                proc = Proc()
                seen: list[tuple[int, int | None]] = []
                with (
                    mock.patch.object(playable.os, "killpg",
                                      side_effect=lambda g, sig: seen.append((sig, proc.returncode))),
                    mock.patch.object(playable, "_leader_exited", return_value=leader_exits, create=True),
                    mock.patch.object(playable, "LANE_GRACE_SECONDS", 0.2),
                ):
                    output = playable._terminate_lane_group(
                        proc, subprocess.TimeoutExpired("lane", 1))  # type: ignore[arg-type]
                self.assertIn("partial", output)
                self.assertTrue(seen, "no group signal was sent")
                self.assertEqual(seen[0][0], signal.SIGTERM)
                self.assertEqual(seen[-1][0], signal.SIGKILL)
                for _signum, returncode in seen:
                    self.assertIsNone(returncode, "a group signal followed reaping (killpg after_reap)")

    def test_g2in_02_lane_drains_pipe_during_grace(self) -> None:
        program = (
            "import os, signal, sys, time\n"
            "def term(signum, frame):\n"
            "    os.write(1, b'x' * 262144 + b'TAIL-MARKER')\n"
            "    os._exit(0)\n"
            "signal.signal(signal.SIGTERM, term)\n"
            "open(sys.argv[1], 'w').close()\n"
            "while True:\n"
            "    time.sleep(0.05)\n"
        )
        ready = tempfile.TemporaryDirectory(prefix="lane-ready-")
        self.addCleanup(ready.cleanup)
        marker = Path(ready.name) / "lane.ready"
        proc = subprocess.Popen([sys.executable, "-c", program, str(marker)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            self.wait_ready(marker)
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                proc.communicate(timeout=1)
            started = time.monotonic()
            with mock.patch.object(playable, "LANE_GRACE_SECONDS", 5):
                output = playable._terminate_lane_group(proc, caught.exception)
            elapsed = time.monotonic() - started
        finally:
            self.kill_quietly(proc.pid)
            proc.wait()
        self.assertLess(elapsed, 4, "the grace period was spent blocked on a full pipe")
        self.assertIn("TAIL-MARKER", output)

    def lane_output_after_timeout(self, early: bool, startup_delay: float = 0) -> str:
        program = (
            "import os, signal, sys, time\n"
            + (f"time.sleep({startup_delay})\n" if startup_delay else "")
            + "def term(signum, frame):\n"
            "    os.write(1, b'LATE\\n')\n"
            "    os._exit(0)\n"
            "signal.signal(signal.SIGTERM, term)\n"
            + ("print('EARLY', flush=True)\n" if early else "")
            + "open(sys.argv[1], 'w').close()\n"
            "while True:\n"
            "    time.sleep(0.05)\n"
        )
        ready = tempfile.TemporaryDirectory(prefix="lane-ready-")
        self.addCleanup(ready.cleanup)
        marker = Path(ready.name) / "lane.ready"
        proc = subprocess.Popen([sys.executable, "-c", program, str(marker)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            self.wait_ready(marker)
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                proc.communicate(timeout=1)
            with mock.patch.object(playable, "LANE_GRACE_SECONDS", 5):
                recorded = playable._terminate_lane_group(proc, caught.exception)
        finally:
            self.kill_quietly(proc.pid)
            proc.wait()
        # The first line is the TimeoutExpired header, which quotes the program text.
        return recorded.split("\n", 1)[1]

    def test_g3wr_01_timed_out_lane_output_is_single_copy_in_order(self) -> None:
        output = self.lane_output_after_timeout(early=True)
        self.assertEqual(output.count("EARLY"), 1, output)
        self.assertEqual(output.count("LATE"), 1, output)
        self.assertLess(output.index("EARLY"), output.index("LATE"))

    def test_g3wr_01_no_earlier_output(self) -> None:
        output = self.lane_output_after_timeout(early=False)
        self.assertEqual(output.count("LATE"), 1, output)
        self.assertNotIn("EARLY", output)

    def g4_lane(self, program: str, *, timeout: int, startup_delay: float = 0, ready: bool = True) -> tuple[subprocess.CompletedProcess[str], bytes, dict[str, dict[str, object]]]:
        """Run `program` as a lane through `Runner.command`; any escaping exception is an assertion failure."""
        if startup_delay:
            program = f"import time\ntime.sleep({startup_delay})\n" + program
        with tempfile.TemporaryDirectory(prefix="lane-g4-") as temporary:
            work = Path(temporary)
            runner = self.make_runner(work)
            argv = [sys.executable, "-c", program]
            try:
                with (
                    mock.patch.object(playable, "verify_snapshot"),
                    mock.patch.object(playable, "LANE_GRACE_SECONDS", 1),
                    mock.patch.object(playable, "LANE_AFTER_KILL_SECONDS", 1, create=True),
                    self.ready_gate(work, argv) if ready else contextlib.nullcontext(),
                ):
                    result = runner.command("g4-lane", argv, timeout=timeout, allow_failure=True)
            except AssertionError:
                raise
            except Exception as error:  # noqa: BLE001 - a red run must fail on the assertion, not on an exception
                self.fail(f"uncaught {type(error).__name__}")
            return result, (work / "g4-lane.log").read_bytes(), dict(runner.lanes)

    def test_g4wr_01_pipe_held_by_detached_descendant_keeps_earlier_output(self) -> None:
        program = (
            "import subprocess, sys, time\n"
            "print('EARLY-MARKER', flush=True)\n"
            "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)\n"
            "print('sleeper', g.pid, flush=True)\n"
            "open('lane.ready', 'w').close()\n"
            "time.sleep(60)\n"
        )
        result, raw, _lanes = self.g4_lane(program, timeout=2)
        log = raw.decode("utf-8")
        match = re.search(r"sleeper (\d+)", log.split("\n", 1)[1])
        if match is not None:
            self.addCleanup(lambda: self.kill_quietly(int(match.group(1))))
        self.assertEqual(result.returncode, -1)
        self.assertIn("TimeoutExpired", log)
        self.assertEqual(log.split("\n", 1)[1].count("EARLY-MARKER"), 1, log)

    def test_g4wr_01_crlf_in_drained_segment_is_translated(self) -> None:
        program = (
            "import os, signal, time\n"
            "def term(signum, frame):\n"
            "    os.write(1, b'B\\r\\nLATE\\r\\n')\n"
            "    os._exit(0)\n"
            "signal.signal(signal.SIGTERM, term)\n"
            "os.write(1, b'A')\n"
            "open('lane.ready', 'w').close()\n"
            "while True:\n"
            "    time.sleep(0.05)\n"
        )
        _result, raw, _lanes = self.g4_lane(program, timeout=2)
        self.assertNotIn(b"\r", raw)
        self.assertIn("AB\nLATE\n", raw.decode("utf-8"))

    def test_g4wr_01_multibyte_split_across_segments(self) -> None:
        program = (
            "import os, signal, time\n"
            "def term(signum, frame):\n"
            "    os.write(1, b'\\xac\\n')\n"
            "    os._exit(0)\n"
            "signal.signal(signal.SIGTERM, term)\n"
            "os.write(1, b'A\\xe2\\x82')\n"
            "open('lane.ready', 'w').close()\n"
            "while True:\n"
            "    time.sleep(0.05)\n"
        )
        _result, raw, _lanes = self.g4_lane(program, timeout=2)
        log = raw.decode("utf-8").split("\n", 1)[1]
        self.assertEqual(log.count("A\u20ac\n"), 1, log)
        self.assertNotIn("\ufffd", log)

    def test_g4wr_03_non_utf8_lane_output_is_recorded(self) -> None:
        program = "import os\nos.write(1, b'\\xff\\n')\n"
        result, raw, lanes = self.g4_lane(program, timeout=20, ready=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("\ufffd", raw.decode("utf-8"))
        self.assertEqual(lanes["g4-lane"]["status"], "pass")

    def test_g4wr_03_non_utf8_output_on_the_timeout_path(self) -> None:
        program = "import os, time\nos.write(1, b'\\xff')\nopen('lane.ready', 'w').close()\ntime.sleep(60)\n"
        result, raw, _lanes = self.g4_lane(program, timeout=2)
        log = raw.decode("utf-8")
        self.assertEqual(result.returncode, -1)
        self.assertIn("TimeoutExpired", log)
        self.assertIn("\ufffd", log)

    def test_g4wr_03_lane_popen_is_byte_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lane-g4-popen-") as temporary:
            runner = self.make_runner(Path(temporary))
            with mock.patch.object(playable, "verify_snapshot"), \
                    mock.patch.object(playable.subprocess, "Popen", wraps=subprocess.Popen) as popen:
                runner.command("byte-lane", [sys.executable, "-c", "print('x')"], timeout=20)
        self.assertEqual(popen.call_count, 1)
        for option in ("text", "universal_newlines", "encoding", "errors"):
            self.assertFalse(popen.call_args.kwargs.get(option), f"lane Popen sets {option}")

    def test_d58wr_02_lane_closing_its_pipe_is_still_terminated_on_timeout(self) -> None:
        program = (
            "import os, time\n"
            "open('lane.pid', 'w').write(str(os.getpid()))\n"
            "print('EARLY-CLOSED', flush=True)\n"
            "open('lane.ready', 'w').close()\n"
            "os.close(1)\n"
            "os.close(2)\n"
            "time.sleep(60)\n"
        )
        with tempfile.TemporaryDirectory(prefix="lane-d58wr02-") as temporary:
            work = Path(temporary)
            runner = self.make_runner(work)
            argv = [sys.executable, "-c", program]
            try:
                with (
                    mock.patch.object(playable, "verify_snapshot"),
                    mock.patch.object(playable, "LANE_GRACE_SECONDS", 1),
                    mock.patch.object(playable, "LANE_AFTER_KILL_SECONDS", 1, create=True),
                    self.ready_gate(work, argv),
                ):
                    result = runner.command("closed-lane", argv, timeout=2, allow_failure=True)
            except AssertionError:
                raise
            except Exception as error:  # noqa: BLE001 - a red run must fail on the assertion, not on an exception
                self.fail(f"uncaught {type(error).__name__}")
            log = (work / "closed-lane.log").read_text(encoding="utf-8")
            self.assertTrue((work / "lane.pid").exists(), "lane child never wrote lane.pid")
            pid = int((work / "lane.pid").read_text(encoding="utf-8"))
            self.addCleanup(lambda: self.kill_quietly(pid))
            deadline = time.monotonic() + 10
            alive = True
            while alive and time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    alive = False
        self.assertFalse(alive, f"the lane survived its timeout: pid {pid}")
        self.assertEqual(result.returncode, -1)
        self.assertIn("TimeoutExpired", log)
        self.assertEqual(log.split("\n", 1)[1].count("EARLY-CLOSED"), 1, log)

    def test_g5wr_02_slow_start_direct_lane_keeps_late_output(self) -> None:
        output = self.lane_output_after_timeout(early=False, startup_delay=3)
        self.assertEqual(output.count("LATE"), 1, output)

    def test_g5wr_02_slow_start_runner_lane_keeps_late_output(self) -> None:
        program = (
            "import os, signal, time\n"
            "def term(signum, frame):\n"
            "    os.write(1, b'LATE\\n')\n"
            "    os._exit(0)\n"
            "signal.signal(signal.SIGTERM, term)\n"
            "os.write(1, b'A')\n"
            "open('lane.ready', 'w').close()\n"
            "while True:\n"
            "    time.sleep(0.05)\n"
        )
        started = time.monotonic()
        _result, raw, _lanes = self.g4_lane(program, timeout=2, startup_delay=3)
        elapsed = time.monotonic() - started
        log = raw.decode("utf-8")
        self.assertIn("TimeoutExpired", log)
        self.assertEqual(log.split("\n", 1)[1].count("LATE"), 1, log)
        # The lane timeout starts only after lane.ready: 3 s startup + 2 s timeout - 0.5 s slack.
        self.assertGreaterEqual(elapsed, 4.5, "the lane timeout started before the child was ready")

    def test_g5wr_02_never_ready_child_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lane-never-ready-") as temporary:
            started = time.monotonic()
            with mock.patch.object(ProcessGroupTest, "READY_SECONDS", 1):
                with self.assertRaises(AssertionError) as caught:
                    self.wait_ready(Path(temporary) / "lane.ready")
            self.assertLess(time.monotonic() - started, 5)
            self.assertIn("lane child never became ready: lane.ready", str(caught.exception))

    @staticmethod
    def kill_quietly(pid: int) -> None:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    def run_lane(self, work: Path, before: set[int] | None, after: set[int] | None,
                 *, child: str | None, group: int | None,
                 later: list[set[int] | None] | None = None,
                 gone_after_sigkill: bool = False) -> tuple[dict[str, object], mock.Mock, mock.Mock, mock.Mock]:
        runner = mock.Mock()
        runner.work = work
        runner.lanes = {}

        def command(name: str, argv: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
            pid_file = Path(argv[argv.index("--child-pid-file") + 1])
            if child is not None:
                pid_file.write_text(child, encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, json.dumps({"status": "pass"}) + "\n")

        runner.command.side_effect = command
        sequence = [before, after, *(later if later is not None else [after])]

        def listing() -> set[int] | None:
            # Later polls repeat the last listing, as a stuck survivor would.
            if gone_after_sigkill and any(c.args[1] == signal.SIGKILL for c in killpg.call_args_list):
                return set()
            return sequence.pop(0) if len(sequence) > 1 else sequence[0]

        killpg = mock.Mock()
        kill = mock.Mock()
        getpgid = mock.Mock(return_value=group) if group is not None else mock.Mock(side_effect=ProcessLookupError)
        with (
            mock.patch.object(playable, "_retroarch_pids", side_effect=listing),
            mock.patch.object(playable, "SURVIVOR_GRACE_SECONDS", 0.05, create=True),
            mock.patch.object(playable.time, "sleep"),
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
        self.assertEqual(killpg.call_args_list[0], mock.call(8, signal.SIGTERM))
        kill.assert_not_called()

    def test_survivor_that_exits_after_sigterm_is_not_escalated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outcome, _, killpg, _ = self.run_lane(
                Path(temporary), set(), {8}, child="8", group=8, later=[set()])
        killpg.assert_called_once_with(8, signal.SIGTERM)
        self.assertIn("recorded group terminated", outcome["receipt"]["detail"])  # type: ignore[index]

    def test_survivor_ignoring_sigterm_is_escalated_to_sigkill_on_the_recorded_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outcome, _, killpg, kill = self.run_lane(
                Path(temporary), set(), {8}, child="8", group=8, gone_after_sigkill=True)
        self.assertEqual(killpg.call_args_list, [mock.call(8, signal.SIGTERM), mock.call(8, signal.SIGKILL)])
        kill.assert_not_called()
        self.assertEqual(outcome["reason"], "retroarch-instance-survived")
        self.assertIn("recorded group killed", outcome["receipt"]["detail"])  # type: ignore[index]

    def test_escalation_reports_a_group_that_is_still_running(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outcome, _, killpg, _ = self.run_lane(
                Path(temporary), set(), {8}, child="8", group=8)
        self.assertEqual([c.args[1] for c in killpg.call_args_list], [signal.SIGTERM, signal.SIGKILL])
        self.assertIn("recorded group still-running", outcome["receipt"]["detail"])  # type: ignore[index]

    def test_t_04_67_unconfirmed_listing_never_escalates_to_sigkill(self) -> None:
        # pgrep fails for the whole grace period: the recorded PID was never confirmed listed.
        with tempfile.TemporaryDirectory() as temporary:
            outcome, _, killpg, kill = self.run_lane(
                Path(temporary), set(), {8}, child="8", group=8, later=[None])
        self.assertEqual([c.args[1] for c in killpg.call_args_list], [signal.SIGTERM])
        kill.assert_not_called()
        self.assertIn("recorded group still-running", outcome["receipt"]["detail"])  # type: ignore[index]

    def test_unrecorded_survivor_detail_counts_it_as_not_signalled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outcome, _, killpg, _ = self.run_lane(Path(temporary), set(), {9}, child="8", group=9)
        killpg.assert_not_called()
        self.assertIn("recorded group not-signalled; 1 not signalled",
                      outcome["receipt"]["detail"])  # type: ignore[index]

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
    """Copy the documents `check_docs` reads, with their review provenance, into a temporary root.

    The copies include the working-tree files of the rights rows, so a tolerated history-absent row is checked
    against its working-tree digest as in a real checkout.
    """

    _synthetic_frontend_summary: dict[str, object] | None = None

    @staticmethod
    def frontend_summary() -> dict[str, object]:
        """Return tracked evidence or a deterministic test receipt for this checkout shape."""
        path = ROOT / playable.FRONTEND_EVIDENCE
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        if DocumentationCopies._synthetic_frontend_summary is None:
            if (ROOT / ".git").exists():
                revision = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, text=True,
                                          stdout=subprocess.PIPE).stdout.strip()
                with tempfile.TemporaryDirectory(prefix="playable-test-snapshot-") as temporary:
                    snapshot = playable.create_snapshot(ROOT, revision, Path(temporary) / "source")
                inventory_sha256 = playable.inventory_digest(snapshot.inventory)
            else:
                # Source archives have no commit inventory to bind. These fixtures exercise document shape only;
                # repository-binding tests are skipped there and use real Git evidence in checkouts.
                revision = "a" * 40
                inventory_sha256 = "1" * 64
            summary: dict[str, object] = {
                "schema": 1,
                "source_revision": revision,
                "inventory_sha256": inventory_sha256,
                "status": "pass",
                "retroarch_status": "pass",
                "retroarch": {"bundle_id": None, "version": "1.22.2",
                              "executable_sha256": playable.RETROARCH_SHA256},
                "os": "test fixture platform",
                "core_sha256": "0" * 64,
                "fixture_sha256": playable.FIXTURE_SHA256,
                "input_mapping": playable.EXPECTED_INPUT_MAPPING,
                "observations": list(playable.REQUIRED_FRONTEND_OBSERVATIONS),
                "marker_before": [10, 10, 1],
                "marker_after_right": [11, 10, 1],
                "frontend_unloaded": True,
                "lanes": {name: "pass" for name in playable.REQUIRED_FRONTEND_LANES},
            }
            playable.validate_frontend_evidence(summary)
            DocumentationCopies._synthetic_frontend_summary = summary
        return json.loads(json.dumps(DocumentationCopies._synthetic_frontend_summary))

    @staticmethod
    def write_sanitized_review_fixture(source_root: Path) -> None:
        """Create public-safe review inputs for tests when private Phase04 records are absent."""
        if (ROOT / ".git").exists():
            revisions = subprocess.run(["git", "-C", str(ROOT), "rev-list", "--max-count=2", "HEAD"],
                                       check=True, text=True, stdout=subprocess.PIPE).stdout.split()
            if not revisions:
                raise AssertionError("Git-backed sanitized review fixture needs a committed HEAD")
            # Full checkouts get a real parent-to-HEAD order. A depth-one checkout still creates valid fixture
            # shape; tests that bind review ordering to this checkout are skipped until a parent is available.
            revision = revisions[0]
            reviewed = revisions[1] if len(revisions) > 1 else revision
        else:
            # Keep fixture references structurally valid without inventing Git history in a source archive.
            revision = reviewed = "a" * 40
        cited = revision
        directory = source_root / playable.PHASE_DIRECTORY
        directory.mkdir(parents=True, exist_ok=True)
        base_files = ("tools/verify_playable.py", "tests/tools/test_verify_playable.py", "docs/first-playable-build.md")
        (source_root / playable.REVIEW).write_text(
            "---\nphase: test-fixture\ndepth: standard\nreviewed_revision: " + reviewed + "\nfiles_reviewed_list:\n"
            + "".join(f"  - {path}\n" for path in base_files)
            + "---\n\n### CR-01: fixture finding\n### CR-03: fixture finding\n### CR-05: fixture finding\n"
              "### IN-03: fixture finding\n### WR-01: fixture finding\n### WR-10: fixture finding\n",
            encoding="utf-8")
        (directory / "04-REVIEW-GAPS-R1.md").write_text(
            "---\nfiles_reviewed_list:\n  - tools/public_content.py\n---\n\n", encoding="utf-8")
        for relative in (*base_files, "tools/public_content.py"):
            source = ROOT / relative
            if source.is_file():
                target = source_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        (source_root / playable.SECURITY).write_text(
            "| Threat ID | Severity | Status |\n|---|---|---|\n| T-04-46 | moderate | mitigated |\n", encoding="utf-8")
        findings = (
            ("CR-01", "critical", "fixed", f"revision `{cited}`"),
            ("CR-03", "warning", "fixed", f"revision `{cited}`"),
            ("CR-05", "warning", "fixed", f"revision `{cited}`"),
            ("IN-03", "info", "open", "recorded"),
            ("WR-01", "warning", "fixed", f"revision `{cited}`"),
            ("WR-10", "warning", "fixed", f"revision `{cited}`"),
        )
        frontmatter = "---\nfindings:\n" + "".join(
            f"  - id: {finding}\n    severity: {severity}\n    disposition: {state}\n"
            for finding, severity, state, _source in findings)
        table = "| Finding | Severity | Disposition | Source |\n|---|---|---|---|\n" + "".join(
            f"| {finding} | {severity} | {state} | {source} |\n"
            for finding, severity, state, source in findings)
        (source_root / playable.DISPOSITION).write_text(frontmatter + "---\n\n" + table, encoding="utf-8")

    @staticmethod
    def write_sanitized_validation_fixture(source_root: Path, summary: dict[str, object] | None) -> None:
        row_status = playable.frontend_row_status(summary)  # type: ignore[arg-type]
        task_header = ("| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | "
                       "Automated Command | File Exists | Status |\n"
                       "|---|---|---|---|---|---|---|---|---|---|\n")
        task = ("| 04-15 T2 | 04-15 | 4 | HOST-02, QUAL-03 | T-04-46 | Generated fixture evidence | "
                "automated | `python3 tools/verify_playable.py --check-docs` | yes | " + row_status + " |\n")
        crosswalk = ("| Review Finding | Severity | Existing Threat Scope | Disposition |\n"
                     "|---|---|---|---|\n"
                     "| CR-01 | critical | T-04-46 | fixed |\n"
                     "| CR-03 | warning | T-04-46 | fixed |\n"
                     "| CR-05 | warning | T-04-46 | fixed |\n"
                     "| IN-03 | info | T-04-46 | open |\n"
                     "| WR-01 | warning | T-04-46 | fixed |\n"
                     "| WR-10 | warning | T-04-46 | fixed |\n")
        path = source_root / playable.VALIDATION
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Public-safe qualification fixture\n\n" + task_header + task + "\n" + crosswalk,
                        encoding="utf-8")

    def copy_review_provenance(self, source_root: Path) -> None:
        live_review = (ROOT / playable.REVIEW).is_file() and (ROOT / playable.DISPOSITION).is_file() \
            and (ROOT / playable.SECURITY).is_file()
        if live_review:
            reviewed = sorted(playable.review_round_paths(ROOT))
            rounds = sorted(path.relative_to(ROOT) for path in (ROOT / playable.PHASE_DIRECTORY).glob(playable.REVIEW_ROUNDS))
            evidence_files = (playable.SECURITY, playable.REVIEW, playable.DISPOSITION, *rounds,
                              *(Path(item) for item in reviewed))
        else:
            self.write_sanitized_review_fixture(source_root)
            evidence_files = ()
        for path in (*evidence_files, Path("README.md"), playable.RIGHTS_INVENTORY, playable.HISTORY_ALLOWLIST):
            if (ROOT / path).is_file():
                (source_root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, source_root / path)
        for item in public_content.load_rights_inventory(ROOT)["items"]:
            row = Path(item["path"])
            if item["path"].startswith("third_party/") or not (ROOT / row).is_file() or (source_root / row).exists():
                continue
            (source_root / row).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / row, source_root / row)

    def copy_documentation(self, source_root: Path) -> Path:
        """Copy the docs as they read without tracked frontend evidence."""
        for path in (playable.GUIDE, playable.VALIDATION, Path("docs/audio-contract.md"),
                     Path("tests/consumers/test_playable_install.py"), Path("tests/consumers/sound_consumer.c"),
                     Path("examples/diagnostic.c")):
            if (ROOT / path).is_file():
                (source_root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, source_root / path)
        self.copy_review_provenance(source_root)
        summary = self.frontend_summary() if (ROOT / playable.FRONTEND_EVIDENCE).is_file() else None
        if not (source_root / playable.GUIDE).is_file():
            (source_root / playable.GUIDE).parent.mkdir(parents=True, exist_ok=True)
            (source_root / playable.GUIDE).write_text(
                f"# First playable build\n\n{playable.frontend_status_block(None)}\n\n"
                "The generated fixture runs from a complete committed Git snapshot and checks its inventory SHA-256. "
                "Dirty and untracked checkout files are excluded. Other prose is not a qualification claim and is "
                "not machine-checked. The gate matches 7 to 40 characters. "
                f"Pinned dependencies: {playable.YMFM_REVISION} {playable.Z80_REVISION}.\n", encoding="utf-8")
        if not (source_root / playable.VALIDATION).is_file():
            self.write_sanitized_validation_fixture(source_root, None)
        guide = source_root / playable.GUIDE
        if summary is not None:
            guide.write_text(guide.read_text(encoding="utf-8").replace(
                playable.frontend_status_block(summary), playable.frontend_status_block(None)), encoding="utf-8")
        else:
            guide_text, replacements = re.subn(
                re.escape(playable.STATUS_BEGIN) + r".*?" + re.escape(playable.STATUS_END),
                playable.frontend_status_block(None), guide.read_text(encoding="utf-8"), count=1, flags=re.DOTALL)
            if replacements != 1:
                raise AssertionError("copied guide lacks exactly one generated frontend status block")
            guide.write_text(guide_text, encoding="utf-8")
        validation = source_root / playable.VALIDATION
        if summary is not None:
            validation.write_text(validation.read_text(encoding="utf-8").replace(
                playable.frontend_row_status(summary), playable.frontend_row_status(None)), encoding="utf-8")
        else:
            row, replacements = re.subn(
                r"(?m)^(\| 04-15 T2 \|(?:[^|]*\|){8})[^|]*\|$",
                lambda match: f"{match.group(1)} {playable.frontend_row_status(None)} |",
                validation.read_text(encoding="utf-8"), count=1)
            if replacements != 1:
                raise AssertionError("copied validation map lacks exactly one frontend qualification row")
            validation.write_text(row, encoding="utf-8")
        return validation

    def copy_documentation_with_evidence(self, source_root: Path) -> dict[str, object]:
        for path in (playable.GUIDE, playable.VALIDATION,
                     Path("docs/audio-contract.md"), Path("tests/consumers/test_playable_install.py"),
                     Path("tests/consumers/sound_consumer.c"), Path("examples/diagnostic.c")):
            if (ROOT / path).is_file():
                (source_root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, source_root / path)
        self.copy_review_provenance(source_root)
        summary = self.frontend_summary()
        if not (source_root / playable.GUIDE).is_file():
            self.copy_documentation(source_root)
        evidence_path = source_root / playable.FRONTEND_EVIDENCE
        if (ROOT / playable.FRONTEND_EVIDENCE).is_file():
            shutil.copyfile(ROOT / playable.FRONTEND_EVIDENCE, evidence_path)
        else:
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if not (source_root / playable.VALIDATION).is_file():
            self.write_sanitized_validation_fixture(source_root, summary)
        guide = source_root / playable.GUIDE
        guide_text, replacements = re.subn(
            re.escape(playable.STATUS_BEGIN) + r".*?" + re.escape(playable.STATUS_END),
            lambda _: playable.frontend_status_block(summary), guide.read_text(encoding="utf-8"),
            count=1, flags=re.DOTALL)
        if replacements != 1:
            raise AssertionError("copied guide lacks exactly one generated frontend status block")
        guide.write_text(guide_text, encoding="utf-8")
        validation = source_root / playable.VALIDATION
        row, replacements = re.subn(
            r"(?m)^(\| 04-15 T2 \|(?:[^|]*\|){8})[^|]*\|$",
            lambda match: f"{match.group(1)} {playable.frontend_row_status(summary)} |",
            validation.read_text(encoding="utf-8"), count=1)
        if replacements != 1:
            raise AssertionError("copied validation map lacks exactly one frontend qualification row")
        validation.write_text(row, encoding="utf-8")
        return summary


class InstalledSoundRecipeTest(unittest.TestCase):
    def validate(self, root: Path) -> None:
        helper = runpy.run_path(str(ROOT / "tests/consumers/test_playable_install.py"))
        helper["validate_sound_recipe"](root)

    def copy_recipe(self, root: Path) -> None:
        for name in ("docs/audio-contract.md", "tests/consumers/sound_consumer.c", "examples/diagnostic.c"):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.validate(root)

    def test_current_recipe_matches_real_consumer(self) -> None:
        self.validate(ROOT)

    def test_missing_documented_consumer_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_recipe(root)
            (root / "examples/diagnostic.c").unlink()
            with self.assertRaisesRegex(RuntimeError, "sound recipe diagnostic source"):
                self.validate(root)

    def test_missing_fixture_command_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_recipe(root)
            path = root / "docs/audio-contract.md"
            original = path.read_text()
            changed = original.replace("--write-fixture", "--old-fixture-option")
            self.assertTrue(original != changed, "required recipe token is absent")
            path.write_text(changed)
            with self.assertRaisesRegex(RuntimeError, "sound recipe"):
                self.validate(root)

    def test_stale_documented_capacity_api_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_recipe(root)
            path = root / "docs/audio-contract.md"
            original = path.read_text()
            changed = original.replace("gn_mvs_audio_capacity_v1", "gn_obsolete_capacity")
            self.assertTrue(original != changed, "required recipe token is absent")
            path.write_text(changed)
            with self.assertRaisesRegex(RuntimeError, "sound recipe"):
                self.validate(root)

    def test_changed_executable_api_sequence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_recipe(root)
            path = root / "tests/consumers/sound_consumer.c"
            path.write_text(path.read_text().replace("gn_mvs_advance_frame_v1", "gn_run_mvs"))
            with self.assertRaisesRegex(RuntimeError, "sound recipe"):
                self.validate(root)


class ConsumerInputTest(DocumentationCopies, unittest.TestCase):
    def test_synthetic_documentation_fixtures_work_without_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-source-archive-") as archive_dir, \
                tempfile.TemporaryDirectory(prefix="playable-source-archive-review-") as review_dir:
            archive = Path(archive_dir)
            self.assertFalse((archive / ".git").exists())
            with mock.patch.dict(globals(), {"ROOT": archive}), \
                    mock.patch.object(DocumentationCopies, "_synthetic_frontend_summary", None), \
                    mock.patch.object(subprocess, "run", side_effect=AssertionError("source archive called Git")):
                summary = DocumentationCopies.frontend_summary()
                self.assertEqual(summary["source_revision"], "a" * 40)
                self.assertEqual(summary["inventory_sha256"], "1" * 64)
                DocumentationCopies.write_sanitized_review_fixture(Path(review_dir))
            review = (Path(review_dir) / playable.REVIEW).read_text(encoding="utf-8")
            self.assertIn("reviewed_revision: " + "a" * 40, review)
            disposition = (Path(review_dir) / playable.DISPOSITION).read_text(encoding="utf-8")
            self.assertEqual(disposition.count("`" + "a" * 40 + "`"), 5)

    def test_root_history_predicate_rejects_source_archive_and_depth_one(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-one-commit-") as temporary:
            repository = Path(temporary)
            subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "-c", "user.name=t", "-c",
                            "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "one"],
                           check=True)
            self.assertFalse(has_two_committed_revisions(repository))
            self.assertFalse(has_bound_documentation_history(repository))

    def test_check_docs_accepts_pending_status_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-docs-pending-") as temporary:
            self.copy_documentation(Path(temporary))
            playable.check_docs(Path(temporary))

    @unittest.skipUnless(has_bound_documentation_history(), "needs a parent commit and allowlist base for review binding")
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
        summary = self.frontend_summary()
        self.assertEqual(playable.validate_frontend_evidence(summary), summary["source_revision"])
        # Forge the receipt against the clone's own HEAD commit, which exists in every checkout (full or
        # squash-merged), instead of checking out the live receipt revision (G5WR-01, C2).
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        forged = dict(summary, source_revision=head, inventory_sha256="0" * 64)
        with tempfile.TemporaryDirectory(prefix="playable-docs-inventory-") as temporary:
            clone = Path(temporary) / "clone"
            subprocess.run(["git", "clone", "--quiet", "--no-checkout", str(ROOT), str(clone)], check=True)
            subprocess.run(["git", "-C", str(clone), "checkout", "--quiet", head], check=True)
            (clone / playable.FRONTEND_EVIDENCE).parent.mkdir(parents=True, exist_ok=True)
            (clone / playable.FRONTEND_EVIDENCE).write_text(json.dumps(forged), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "inventory digest does not match"):
                playable.load_frontend_evidence(clone)

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_live_receipt_binds_its_committed_inventory_on_full_history(self) -> None:
        summary = self.frontend_summary()
        revision = summary["source_revision"]
        present = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", revision + "^{commit}"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        ancestor = present and subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", revision, "HEAD"],
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not ancestor:
            self.skipTest(f"live receipt revision {revision[:12]} absent from history (squashed checkout); "
                          "binding is pinned on full history")
        with tempfile.TemporaryDirectory(prefix="playable-live-receipt-") as temporary:
            source_root = Path(temporary)
            evidence = source_root / playable.FRONTEND_EVIDENCE
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(summary), encoding="utf-8")
            notes: list[str] = []
            self.assertEqual(playable.load_frontend_evidence(source_root, repository=ROOT, unverifiable=notes), summary)
            self.assertEqual(notes, [])
        forged = dict(summary, inventory_sha256="0" * 64)
        with tempfile.TemporaryDirectory(prefix="playable-docs-inventory-live-") as temporary:
            clone = Path(temporary) / "clone"
            subprocess.run(["git", "clone", "--quiet", "--no-checkout", str(ROOT), str(clone)], check=True)
            subprocess.run(["git", "-C", str(clone), "checkout", "--quiet", revision], check=True)
            (clone / playable.FRONTEND_EVIDENCE).parent.mkdir(parents=True, exist_ok=True)
            (clone / playable.FRONTEND_EVIDENCE).write_text(json.dumps(forged), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "inventory digest does not match"):
                playable.load_frontend_evidence(clone)

    @unittest.skipUnless(has_bound_documentation_history(), "needs a parent commit and allowlist base for review binding")
    def test_check_docs_requires_generated_status_to_match_evidence(self) -> None:
        cases = (
            ("evidence with pending block", self.copy_documentation, True, "status block does not match"),
            ("pending docs edited to complete", self.copy_documentation, False, "status block does not match"),
        )
        for label, copy, add_evidence, expected_error in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory(prefix="playable-docs-block-") as temporary:
                source_root = Path(temporary)
                copy(source_root)
                summary = self.frontend_summary()
                guide = source_root / playable.GUIDE
                if add_evidence:
                    evidence = source_root / playable.FRONTEND_EVIDENCE
                    evidence.parent.mkdir(parents=True, exist_ok=True)
                    evidence.write_text(json.dumps(summary), encoding="utf-8")
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
        summary = self.frontend_summary()
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

    @unittest.skipUnless(has_bound_documentation_history(), "needs HEAD^ and the history allowlist base")
    def test_explicit_repository_binds_the_copied_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-bound-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            playable.check_docs(source_root, repository=ROOT)
            # Forge the receipt against the repository's own HEAD commit, which exists in every checkout
            # (full or squash-merged), instead of the live receipt revision and its parent (G5WR-01, C3).
            head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                  check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
            parent = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD^"],
                                    check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
            forged = dict(summary, source_revision=head)
            guide = source_root / playable.GUIDE
            guide.write_text(guide.read_text(encoding="utf-8").replace(
                playable.frontend_status_block(summary), playable.frontend_status_block(forged)), encoding="utf-8")
            validation = source_root / playable.VALIDATION
            validation.write_text(validation.read_text(encoding="utf-8").replace(
                playable.frontend_row_status(summary), playable.frontend_row_status(forged)), encoding="utf-8")
            (source_root / playable.FRONTEND_EVIDENCE).write_text(json.dumps(forged), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "not a committed ancestor"):
                playable.check_docs(source_root, repository=ROOT, head=parent)
            forged["inventory_sha256"] = "0" * 64
            (source_root / playable.FRONTEND_EVIDENCE).write_text(json.dumps(forged), encoding="utf-8")
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
        with tempfile.TemporaryDirectory(prefix="playable-crosswalk-live-") as temporary:
            source_root = Path(temporary)
            validation = self.copy_documentation(source_root)
            self.assertEqual(playable.crosswalk_errors(source_root, validation.read_text(encoding="utf-8")), [])

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

    def test_scope_may_cite_a_path_reviewed_only_by_a_later_round(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-crosswalk-round-") as temporary:
            source_root = Path(temporary)
            validation = self.copy_documentation(source_root)
            later = playable.review_round_paths(source_root) - playable._reviewed_paths(
                (source_root / playable.REVIEW).read_text(encoding="utf-8"))
            self.assertIn("tools/public_content.py", later)
            text = self.with_scope("CR-05", "`tools/public_content.py`")(
                validation.read_text(encoding="utf-8"))
            self.assertEqual(playable.crosswalk_errors(source_root, text), [])

    def test_three_digit_threat_ids_are_read_whole(self) -> None:
        self.assertEqual(playable.THREAT_REFERENCE.findall("T-04-103 / T-04-10 / T-04-SC (04-58)"),
                         ["T-04-103", "T-04-10", "T-04-SC (04-58)"])
        self.mutate_row(self.with_scope("CR-05", "T-04-109999"), "unknown threat T-04-109999")

    def test_scope_path_parent_segments_are_rejected(self) -> None:
        for scope in ("`../x.md`", "`docs/../x.md`", "`tools/../tools/verify_playable.py`"):
            with self.subTest(scope=scope):
                self.mutate_row(self.with_scope("CR-05", scope), "has a parent segment")

    def test_wr_11_duplicate_review_frontmatter_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-review-keys-") as temporary:
            root = Path(temporary)
            self.copy_documentation(root)
            review = root / playable.REVIEW
            text = review.read_text(encoding="utf-8")
            head, separator, rest = text.partition("\n---\n")
            self.assertTrue(separator)
            review.write_text(head + "\nfiles_reviewed_list:\n  - README.md\n" + separator + rest, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "duplicate"):
                playable.check_docs(root)

    def test_wr_11_reviewed_revision_must_appear_exactly_once_and_be_40_hex(self) -> None:
        good = "a" * 40

        def review(*lines: str) -> str:
            return "---\nphase: x\n" + "".join(line + "\n" for line in lines) + "---\n\nbody\n"

        for label, text in (
                ("absent", review()),
                ("empty", review("reviewed_revision:")),
                ("two keys", review(f"reviewed_revision: {good}", f"reviewed_revision: {'b' * 40}")),
                ("quoted duplicate", review(f"reviewed_revision: {good}", f'"reviewed_revision" : {good}')),
                ("padded duplicate", review(f"reviewed_revision: {good}", f"reviewed_revision : {good}")),
                ("12 hex", review("reviewed_revision: " + "a" * 12)),
                ("non-hex letter", review("reviewed_revision: " + "a" * 39 + "g")),
                ("uppercase", review("reviewed_revision: " + "A" * 40)),
                ("trailing comment", review(f"reviewed_revision: {good} # note"))):
            with self.subTest(case=label):
                with self.assertRaisesRegex(RuntimeError, "reviewed_revision"):
                    playable._reviewed_revision(text)
        for label, value in (("bare", good), ("double quoted", f'"{good}"'), ("single quoted", f"'{good}'")):
            with self.subTest(case=label):
                self.assertEqual(playable._reviewed_revision(review(f"reviewed_revision: {value}")), good)

    def test_rows_must_equal_the_disposition_record(self) -> None:
        cases = (
            # Toggle away from the live state so the mutation is never a no-op (the live CR-01 row is already `fixed`).
            ("state differs", lambda text: re.sub(
                r"(?m)^(\| CR-01 \|[^|]*\|[^|]*\|)([^|]*)(\|)$",
                lambda match: f"{match.group(1)} {'open' if match.group(2).strip() == 'fixed' else 'fixed'} {match.group(3)}",
                text, count=1),
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


    def test_every_review_round_finding_needs_a_disposition_record(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-round-") as temporary:
            root = Path(temporary)
            validation = self.copy_documentation(root)
            text = validation.read_text(encoding="utf-8")
            self.assertEqual(playable.crosswalk_errors(root, text), [])
            late_round = root / playable.PHASE_DIRECTORY / "04-REVIEW-GAPS-R99.md"
            late_round.write_text("# Round\n\n### G99WR-01: an unrecorded warning\n\n### G99IN-01: an unrecorded note\n",
                                  encoding="utf-8")
            self.assertIn("review findings have no disposition record: G99IN-01, G99WR-01",
                          playable.crosswalk_errors(root, text))


class ReviewProvenanceTest(DocumentationCopies, unittest.TestCase):
    """Non-open review dispositions cite a review revision that is a committed ancestor of head (T-04-38)."""

    HEADER = "| Finding | Severity | Disposition | Source |\n|---|---|---|---|\n"

    def errors(self, rows: str, head: str = "HEAD", *, repository: Path = ROOT, reviewed: str | None = None) -> list[str]:
        # The reviewed revision defaults to the first commit, so every existing case stays inside the window.
        reviewed = reviewed or self.first_commit()
        with tempfile.TemporaryDirectory(prefix="playable-provenance-") as temporary:
            root = Path(temporary)
            (root / playable.DISPOSITION).parent.mkdir(parents=True, exist_ok=True)
            (root / playable.DISPOSITION).write_text(self.HEADER + rows, encoding="utf-8")
            (root / playable.REVIEW).write_text(
                f"---\nphase: x\nreviewed_revision: {reviewed}\n---\n\nbody\n", encoding="utf-8")
            return playable.review_provenance_errors(root, repository, head)

    def history(self, base: Path) -> list[str]:
        """Linear history C0 -> C1 (review) -> C2 (verdict) -> C3 (head) in a temporary repository."""
        subprocess.run(["git", "init", "-q", str(base)], check=True)
        commits = []
        for index in range(4):
            subprocess.run(["git", "-C", str(base), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                            "commit", "-q", "--allow-empty", "-m", f"c{index}"], check=True)
            commits.append(subprocess.run(["git", "-C", str(base), "rev-parse", "HEAD"], check=True, text=True,
                                          stdout=subprocess.PIPE).stdout.strip())
        return commits

    def test_t_04_38_disposition_older_than_reviewed_revision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-window-") as temporary:
            repository = Path(temporary) / "repo"
            c0, c1, c2, c3 = self.history(repository)
            row = "| CR-01 | critical | fixed | revision `{}` |\n"
            older = self.errors(row.format(c0), c3, repository=repository, reviewed=c1)
            self.assertEqual(older, [f"review finding CR-01 cites revision {c0[:12]} that does not descend from the reviewed revision"])
            self.assertEqual(self.errors(row.format(c2), c3, repository=repository, reviewed=c1), [])
            # G3WR-05: equality with the anchor is no longer accepted; the citation must strictly follow it.
            self.assertEqual(self.errors(row.format(c1), c3, repository=repository, reviewed=c1),
                             [f"review finding CR-01 cites revision {c1[:12]} equal to its review round anchor "
                              "(04-REVIEW.md reviewed_revision)"])
            beyond = self.errors(row.format(c3), c2, repository=repository, reviewed=c1)
            self.assertEqual(beyond, [f"review finding CR-01 cites revision {c3[:12]} that is not a committed ancestor"])

    def rounds(self, base: Path) -> list[str]:
        """C0 -> C1 (adds 04-REVIEW-GAPS.md) -> C2 (adds 04-REVIEW-GAPS-R2.md) -> C3 -> C4 (G3WR-05)."""
        subprocess.run(["git", "init", "-q", str(base)], check=True)
        commits = []
        for index, name in enumerate((None, "04-REVIEW-GAPS.md", "04-REVIEW-GAPS-R2.md", None, None)):
            if name is not None:
                target = base / playable.PHASE_DIRECTORY / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("review\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(base), "add", str(playable.PHASE_DIRECTORY / name)], check=True)
            subprocess.run(["git", "-C", str(base), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                            "commit", "-q", "--allow-empty", "-m", f"c{index}"], check=True)
            commits.append(subprocess.run(["git", "-C", str(base), "rev-parse", "HEAD"], check=True, text=True,
                                          stdout=subprocess.PIPE).stdout.strip())
        return commits

    def round_errors(self, finding: str, cited: str, head: str, repository: Path, reviewed: str) -> list[str]:
        try:
            return self.errors(f"| {finding} | warning | fixed | revision `{cited}` |\n", head,
                               repository=repository, reviewed=reviewed)
        except Exception as error:  # noqa: BLE001 - a red run must fail on the assertion, not on an exception
            self.fail(f"uncaught {type(error).__name__}")

    def check_round(self, finding: str, label: str, anchor_index: int) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rounds-") as temporary:
            repository = Path(temporary) / "repo"
            commits = self.rounds(repository)
            head = commits[4]
            anchor = commits[anchor_index]
            before = commits[anchor_index - 1]
            later = commits[anchor_index + 1]
            self.assertEqual(
                self.round_errors(finding, before, head, repository, commits[0]),
                [f"review finding {finding} cites revision {before[:12]} that does not descend from its review round ({label})"])
            self.assertEqual(
                self.round_errors(finding, anchor, head, repository, commits[0]),
                [f"review finding {finding} cites revision {anchor[:12]} equal to its review round anchor ({label})"])
            self.assertEqual(self.round_errors(finding, later, head, repository, commits[0]), [])

    def test_workstream_archive_preserves_original_review_round_anchor(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-archive-") as temporary:
            repository = Path(temporary) / "repo"
            with mock.patch.object(playable, "PHASE_DIRECTORY", playable.PHASE_HISTORY_DIRECTORY):
                commits = self.rounds(repository)
            old = repository / playable.PHASE_HISTORY_DIRECTORY
            archived = repository / playable.PHASE_DIRECTORY
            archived.parent.mkdir(parents=True, exist_ok=True)
            old.rename(archived)
            subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repository), "-c", "user.name=t", "-c",
                            "user.email=t@example.invalid", "commit", "-qm", "archive workstream"], check=True)
            anchor = (commits[2], "04-REVIEW-GAPS-R2.md")
            self.assertEqual(playable._review_round_anchor("G2WR-01", repository, repository, "HEAD"), anchor)
            self.assertEqual(playable._review_round_anchor("G2WR-01", repository, repository, commits[4]), anchor)
            self.assertEqual(self.round_errors("G2WR-01", commits[3], "HEAD", repository, commits[0]), [])

    def test_g3wr_05_gap_round_two_closure_must_strictly_follow_its_round_file(self) -> None:
        self.check_round("G2WR-01", "04-REVIEW-GAPS-R2.md", 2)

    def test_g3wr_05_first_gap_round_closure_is_bound_to_its_round_file(self) -> None:
        self.check_round("GWR-01", "04-REVIEW-GAPS.md", 1)

    def test_g3wr_05_base_round_closure_equal_to_reviewed_revision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rounds-") as temporary:
            repository = Path(temporary) / "repo"
            commits = self.rounds(repository)
            self.assertEqual(
                self.round_errors("WR-01", commits[1], commits[4], repository, commits[1]),
                [f"review finding WR-01 cites revision {commits[1][:12]} equal to its review round anchor "
                 "(04-REVIEW.md reviewed_revision)"])
            self.assertEqual(self.round_errors("WR-01", commits[3], commits[4], repository, commits[1]), [])

    def test_g3wr_05_round_file_missing_at_head_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rounds-") as temporary:
            repository = Path(temporary) / "repo"
            commits = self.rounds(repository)
            self.assertEqual(
                self.round_errors("G3WR-01", commits[3], commits[4], repository, commits[0]),
                ["review round file 04-REVIEW-GAPS-R3.md for G3WR-01 is not committed at the checked head"])

    def test_g3wr_05_round_file_added_after_head_is_not_committed_at_head(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rounds-") as temporary:
            repository = Path(temporary) / "repo"
            commits = self.rounds(repository)
            self.assertEqual(
                self.round_errors("G2WR-01", commits[1], commits[1], repository, commits[0]),
                ["review round file 04-REVIEW-GAPS-R2.md for G2WR-01 is not committed at the checked head"])

    def test_g3wr_05_unknown_finding_id_has_no_review_round(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rounds-") as temporary:
            repository = Path(temporary) / "repo"
            commits = self.rounds(repository)
            self.assertEqual(
                self.round_errors("XX-01", commits[3], commits[4], repository, commits[0]),
                ["review finding XX-01 has no known review round"])

    def test_g3wr_05_open_rows_need_no_citation_in_any_round(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rounds-") as temporary:
            repository = Path(temporary) / "repo"
            commits = self.rounds(repository)
            rows = "".join(f"| {finding} | warning | open | recorded |\n" for finding in ("WR-01", "GWR-01", "G2WR-01", "G3WR-01", "XX-01"))
            self.assertEqual(self.errors(rows, commits[4], repository=repository, reviewed=commits[0]), [])

    @unittest.skipUnless(has_two_committed_revisions(), "needs at least two commits for the descendant comparison")
    def test_t_04_38_unresolvable_reviewed_revision_fails(self) -> None:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, text=True,
                              stdout=subprocess.PIPE).stdout.strip()
        for label, reviewed in (("not a commit", "f" * 40), ("not an ancestor of head", head)):
            with self.subTest(case=label), tempfile.TemporaryDirectory(prefix="playable-reviewed-") as temporary:
                root = Path(temporary)
                self.copy_documentation(root)
                # The live allowlist's base_revision is no ancestor of the first commit, so its anchor
                # error would preempt the gate under test; without it every row is strict.
                (root / playable.HISTORY_ALLOWLIST).unlink()
                review = root / playable.REVIEW
                text = review.read_text(encoding="utf-8")
                text = re.sub(r"(?m)^reviewed_revision:.*\n", "", text)
                review.write_text(text.replace("depth: standard\n", f"depth: standard\nreviewed_revision: {reviewed}\n", 1),
                                  encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "reviewed revision"):
                    # Check against the first commit so the current head is no ancestor of it.
                    playable.check_docs(root, repository=ROOT, head=self.first_commit() if label != "not a commit" else "HEAD")

    @staticmethod
    def first_commit() -> str:
        return subprocess.run(["git", "-C", str(ROOT), "rev-list", "--max-parents=0", "HEAD"],
                              check=True, text=True, stdout=subprocess.PIPE).stdout.split()[0]

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_open_rows_need_no_revision(self) -> None:
        self.assertEqual(self.errors("| CR-01 | critical | open | recorded, not triaged |\n"), [])

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_closure_rows_without_a_revision_are_rejected(self) -> None:
        for state in ("fixed", "deferred", "skipped"):
            with self.subTest(state=state):
                errors = self.errors(f"| CR-01 | critical | {state} | looked fine |\n")
                self.assertEqual(errors, ["review finding CR-01 disposition cites no review revision"])

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_digests_and_unrelated_hex_are_not_revisions(self) -> None:
        errors = self.errors(f"| WR-01 | warning | fixed | digest `{'a1' * 32}` and 0123abcd |\n")
        self.assertEqual(errors, ["review finding WR-01 disposition cites no review revision"])

    @unittest.skipUnless(has_two_committed_revisions(), "needs a later revision after the first commit")
    def test_ancestor_revision_in_either_recognized_form_is_accepted(self) -> None:
        # G3WR-05: the reviewed revision defaults to the first commit and a citation must strictly follow it,
        # so cite the second commit; the recognized forms under test are unchanged.
        first = subprocess.run(["git", "-C", str(ROOT), "rev-list", "--reverse", "HEAD"], check=True, text=True,
                               stdout=subprocess.PIPE).stdout.split()[1]
        rows = (f"| CR-01 | critical | fixed | independent review (04-31, {first[:12]}) confirmed |\n"
                f"| WR-01 | warning | deferred | at revision `{first}` |\n")
        self.assertEqual(self.errors(rows), [])

    @unittest.skipUnless((ROOT / ".git").exists(), "needs the Git history the summary is bound to")
    def test_unresolvable_revision_is_rejected(self) -> None:
        errors = self.errors("| CR-01 | critical | fixed | revision `" + "f" * 40 + "` |\n")
        self.assertEqual(errors, [f"review finding CR-01 cites revision {'f' * 12} that is not a committed ancestor"])

    @unittest.skipUnless(has_two_committed_revisions(), "needs distinct first and current commits")
    def test_revision_that_is_not_an_ancestor_of_head_is_rejected(self) -> None:
        first = self.first_commit()
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, text=True,
                              stdout=subprocess.PIPE).stdout.strip()
        # Cite the current head while checking against the first commit: a descendant is not an ancestor.
        errors = self.errors(f"| CR-01 | critical | fixed | revision `{head}` |\n", head=first)
        self.assertEqual(errors, [f"review finding CR-01 cites revision {head[:12]} that is not a committed ancestor"])

    @unittest.skipUnless(has_bound_documentation_history(), "needs a parent commit and allowlist base for review binding")
    def test_check_docs_binds_the_live_record_and_rejects_a_stripped_revision(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-provenance-docs-") as temporary:
            root = Path(temporary)
            self.copy_documentation(root)
            playable.check_docs(root, repository=ROOT)
            record = root / playable.DISPOSITION
            text = record.read_text(encoding="utf-8")
            stripped = re.sub(r"(?m)^(\| WR-10 \|[^|]*\|[^|]*\|)[^|]*(\|)$", r"\1 resolved by hand \2", text, count=1)
            self.assertNotEqual(stripped, text)
            record.write_text(stripped, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "review finding WR-10 disposition cites no review revision"):
                playable.check_docs(root, repository=ROOT)


class RightsRevisionTest(DocumentationCopies, unittest.TestCase):
    """Every non-third_party rights row cites a commit holding its recorded bytes (G4WR-04, T-04-103)."""

    def helper(self):
        function = getattr(playable, "rights_revision_errors", None)
        self.assertIsNotNone(function, "rights_revision_errors is missing")
        return function

    @staticmethod
    def git(repository: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repository), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *arguments],
            check=True, text=True, stdout=subprocess.PIPE).stdout.strip()

    def make_repository(self, base: Path) -> tuple[Path, str, str]:
        """A repository whose tests/a.txt is `one` at the first commit and `two` at the second."""
        repository = base / "repo"
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        (repository / "tests").mkdir()
        revisions = []
        for content in ("one\n", "two\n"):
            (repository / "tests/a.txt").write_text(content, encoding="utf-8")
            self.git(repository, "add", "tests/a.txt")
            self.git(repository, "commit", "-q", "-m", content.strip())
            revisions.append(self.git(repository, "rev-parse", "HEAD"))
        return repository, revisions[0], revisions[1]

    @staticmethod
    def write_inventory(repository: Path, items: list[dict[str, str]]) -> None:
        (repository / "docs").mkdir(exist_ok=True)
        (repository / "docs/rights-inventory.md").write_text(
            "# Inventory\n\n```json\n" + json.dumps({"schema": 1, "items": items}) + "\n```\n", encoding="utf-8")

    @staticmethod
    def digest(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def errors(self, repository: Path, items: list[dict[str, str]], head: str = "HEAD") -> list[str]:
        function = self.helper()
        self.write_inventory(repository, items)
        try:
            return function(repository, repository, head)
        except Exception as error:  # noqa: BLE001 - a red run must fail on the assertion, not on an exception
            self.fail(f"uncaught {type(error).__name__}")

    def test_g4wr_04_unresolvable_revision_names_the_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rights-") as temporary:
            repository, _first, _second = self.make_repository(Path(temporary))
            errors = self.errors(repository, [{"path": "tests/a.txt", "sha256": self.digest("two\n"), "source_revision": "e" * 40}])
            self.assertEqual(len(errors), 1, errors)
            self.assertIn("tests/a.txt", errors[0])
            self.assertIn("does not resolve", errors[0])

    def test_g4wr_04_stale_revision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rights-") as temporary:
            repository, first, _second = self.make_repository(Path(temporary))
            errors = self.errors(repository, [{"path": "tests/a.txt", "sha256": self.digest("two\n"), "source_revision": first}])
            self.assertEqual(len(errors), 1, errors)
            self.assertIn("tests/a.txt", errors[0])
            self.assertIn("does not hold the recorded SHA-256", errors[0])

    def test_g4wr_04_third_party_rows_are_exempt_and_correct_rows_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rights-") as temporary:
            repository, _first, second = self.make_repository(Path(temporary))
            items = [
                {"path": "third_party/unity/src/unity.c", "sha256": "0" * 64, "source_revision": "b" * 40},
                {"path": "tests/a.txt", "sha256": self.digest("two\n"), "source_revision": second},
            ]
            self.assertEqual(self.errors(repository, items), [])

    def test_g4wr_04_malformed_revision_never_reaches_git(self) -> None:
        for bad in ("--output=x", "HEAD", "a" * 39, "A" * 40, ""):
            with self.subTest(revision=bad), tempfile.TemporaryDirectory(prefix="playable-rights-") as temporary:
                repository, _first, _second = self.make_repository(Path(temporary))
                real = subprocess.run
                with mock.patch.object(subprocess, "run", wraps=real) as run:
                    errors = self.errors(repository, [{"path": "tests/a.txt", "sha256": self.digest("two\n"), "source_revision": bad}])
                self.assertEqual(len(errors), 1, errors)
                self.assertIn("not 40 hex", errors[0])
                arguments = [argument for call in run.call_args_list for argument in call.args[0]]
                self.assertFalse(any(argument == bad or (bad and bad in argument) for argument in arguments), arguments)

    def test_g4wr_04_malformed_path_never_reaches_git(self) -> None:
        for bad in ("", "/etc/passwd", "tests/../x", "-x"):
            with self.subTest(path=bad), tempfile.TemporaryDirectory(prefix="playable-rights-") as temporary:
                repository, _first, second = self.make_repository(Path(temporary))
                real = subprocess.run
                with mock.patch.object(subprocess, "run", wraps=real) as run:
                    errors = self.errors(repository, [{"path": bad, "sha256": self.digest("two\n"), "source_revision": second}])
                self.assertEqual(len(errors), 1, errors)
                self.assertIn("not a relative POSIX path", errors[0])
                arguments = [argument for call in run.call_args_list for argument in call.args[0]]
                self.assertFalse(any(argument == bad or (bad and bad in argument) for argument in arguments), arguments)

    def test_g5in_01_third_party_dot_dot_path_is_not_exempt(self) -> None:
        bad = "third_party/../tests/x.py"
        with tempfile.TemporaryDirectory(prefix="playable-rights-") as temporary:
            repository, _first, second = self.make_repository(Path(temporary))
            real = subprocess.run
            with mock.patch.object(subprocess, "run", wraps=real) as run:
                errors = self.errors(repository, [{"path": bad, "sha256": self.digest("two\n"), "source_revision": second}])
            self.assertEqual(len(errors), 1, errors)
            self.assertIn("not a relative POSIX path", errors[0])
            arguments = [argument for call in run.call_args_list for argument in call.args[0]]
            self.assertFalse(any(bad in argument for argument in arguments), arguments)

    def test_g5in_01_non_list_items_is_malformed(self) -> None:
        for items in (3, {"a": 1}):
            with self.subTest(items=items), tempfile.TemporaryDirectory(prefix="playable-rights-") as temporary:
                repository, _first, _second = self.make_repository(Path(temporary))
                (repository / "docs").mkdir(exist_ok=True)
                (repository / "docs/rights-inventory.md").write_text(
                    "# Inventory\n\n```json\n" + json.dumps({"schema": 1, "items": items}) + "\n```\n", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "rights inventory JSON is malformed"):
                    self.helper()(repository, repository, "HEAD")

    def test_g4wr_04_revision_outside_the_checked_head_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rights-") as temporary:
            repository, first, second = self.make_repository(Path(temporary))
            self.git(repository, "checkout", "-q", "-b", "side", first)
            (repository / "tests/a.txt").write_text("three\n", encoding="utf-8")
            self.git(repository, "add", "tests/a.txt")
            self.git(repository, "commit", "-q", "-m", "side")
            side = self.git(repository, "rev-parse", "HEAD")
            errors = self.errors(repository, [{"path": "tests/a.txt", "sha256": self.digest("three\n"), "source_revision": side}], head=second)
            self.assertEqual(len(errors), 1, errors)
            self.assertIn("is not an ancestor of the checked head", errors[0])

    @unittest.skipUnless(has_bound_documentation_history(), "needs committed rights origins and the allowlist base")
    def test_g4wr_04_check_docs_raises_the_first_rights_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-rights-docs-") as temporary:
            root = Path(temporary)
            self.copy_documentation_with_evidence(root)
            with mock.patch.object(playable, "rights_revision_errors", create=True, return_value=["rights sentinel"]):
                with self.assertRaisesRegex(RuntimeError, "rights sentinel"):
                    playable.check_docs(root, repository=ROOT)

    def test_g4wr_04_repository_rights_revisions_resolve(self) -> None:
        if not has_bound_documentation_history():
            self.skipTest("checkout lacks the history and allowlist base needed to resolve rights origins")
        function = self.helper()
        self.assertEqual(function(ROOT, ROOT, "HEAD"), [])


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

    @unittest.skipUnless(has_bound_documentation_history(), "needs a parent commit and allowlist base for review binding")
    def test_claims_appended_after_the_generated_block_are_rejected(self) -> None:
        for claim in self.CLAIMS:
            with self.subTest(claim=claim), tempfile.TemporaryDirectory(prefix="playable-claim-") as temporary:
                source_root = Path(temporary)
                self.guide_with(source_root, claim)
                with self.assertRaisesRegex(RuntimeError, "status claim outside the generated block"):
                    playable.check_docs(source_root, repository=ROOT)

    @unittest.skipUnless(has_bound_documentation_history(), "needs a parent commit and allowlist base for review binding")
    def test_digests_and_pinned_revisions_outside_the_block_are_allowed(self) -> None:
        extra = f"Digest {'ab12' * 16} and pins {playable.YMFM_REVISION} {playable.Z80_REVISION}."
        with tempfile.TemporaryDirectory(prefix="playable-claim-ok-") as temporary:
            source_root = Path(temporary)
            self.guide_with(source_root, extra)
            playable.check_docs(source_root, repository=ROOT)

    def test_live_guide_has_no_outside_block_claims(self) -> None:
        guide = (ROOT / playable.GUIDE).read_text(encoding="utf-8")
        self.assertEqual(playable.guide_claims_outside_block(guide), [])

    @unittest.skipUnless(has_bound_documentation_history(), "needs a parent commit and allowlist base for review binding")
    def test_guide_with_a_private_checkout_path_is_rejected(self) -> None:
        private = str(playable.ROOT).replace("/", "\u2215")
        with tempfile.TemporaryDirectory(prefix="playable-claim-path-") as temporary:
            source_root = Path(temporary)
            self.guide_with(source_root, f"Build in {private}/build.")
            with self.assertRaisesRegex(RuntimeError, "private absolute path"):
                playable.check_docs(source_root, repository=ROOT)

    def test_claim_gate_limits_are_documented_and_pinned(self) -> None:
        """GIN-04 (accepted): the gate matches 7 to 40 hex characters; longer tokens are not machine-checked."""
        with tempfile.TemporaryDirectory(prefix="playable-guide-limits-") as temporary:
            source_root = Path(temporary)
            self.copy_documentation(source_root)
            guide = (source_root / playable.GUIDE).read_text(encoding="utf-8")
        self.assertIn("7 to 40 characters", guide)
        self.assertIn("Other prose is not a qualification claim and is not machine-checked", guide)
        outside = guide + "\n\nunreviewed digest " + "a1b2c3d4" * 8 + "\n"
        self.assertEqual(playable.guide_claims_outside_block(outside), playable.guide_claims_outside_block(guide))


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

    def test_replace_failure_rolls_back_every_replaced_file(self) -> None:
        real_replace = os.replace
        for failing_call in (1, 2, 3):
            with self.subTest(failing_call=failing_call), \
                    tempfile.TemporaryDirectory(prefix="playable-rollback-") as temporary:
                source_root = Path(temporary)
                summary = self.copy_documentation_with_evidence(source_root)
                before = self.digests(source_root)
                calls: list[str] = []

                def replace(source: object, destination: object) -> None:
                    calls.append(Path(destination).name)  # type: ignore[arg-type]
                    if len(calls) == failing_call:
                        raise OSError("injected replace failure")
                    real_replace(source, destination)  # type: ignore[arg-type]

                with mock.patch.object(playable.os, "replace", side_effect=replace):
                    with self.assertRaisesRegex(OSError, "injected replace failure"):
                        playable.write_frontend_records(source_root, self.changed_summary(summary))
                self.assertEqual(self.digests(source_root), before)
                self.assertEqual(list(source_root.rglob("*.tmp")), [])

    def test_g2wr_05_first_time_generation_with_absent_evidence_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-first-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            evidence = source_root / playable.FRONTEND_EVIDENCE
            evidence.unlink()
            changed = self.changed_summary(summary)
            playable.write_frontend_records(source_root, changed)
            self.assertEqual(json.loads(evidence.read_text(encoding="utf-8"))["os"], "macOS 99.0 arm64")
            self.assertIn("macOS 99.0 arm64", (source_root / playable.GUIDE).read_text(encoding="utf-8"))
            self.assertEqual(list(source_root.rglob("*.tmp")), [])

    def test_g2wr_05_rollback_unlinks_files_that_did_not_exist(self) -> None:
        real_replace = os.replace
        with tempfile.TemporaryDirectory(prefix="playable-first-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            evidence = source_root / playable.FRONTEND_EVIDENCE
            evidence.unlink()
            validation_before = (source_root / playable.VALIDATION).read_bytes()
            calls: list[str] = []

            def replace(source: object, destination: object) -> None:
                calls.append(Path(destination).name)  # type: ignore[arg-type]
                if len(calls) == 2:
                    raise OSError("injected replace failure")
                real_replace(source, destination)  # type: ignore[arg-type]

            with mock.patch.object(playable.os, "replace", side_effect=replace):
                with self.assertRaisesRegex(OSError, "injected replace failure"):
                    playable.write_frontend_records(source_root, self.changed_summary(summary))
            self.assertFalse(evidence.exists())
            self.assertEqual((source_root / playable.VALIDATION).read_bytes(), validation_before)
            self.assertEqual(list(source_root.rglob("*.tmp")), [])
            self.assertEqual(list(source_root.rglob("*.restore")), [])

    def test_g2wr_05_failed_restore_continues_and_names_files(self) -> None:
        real_replace = os.replace
        for failing_restore, failed_file, restored_file in (
                (4, playable.VALIDATION, playable.FRONTEND_EVIDENCE),
                (5, playable.FRONTEND_EVIDENCE, playable.VALIDATION)):
            with self.subTest(failing_restore=failing_restore), \
                    tempfile.TemporaryDirectory(prefix="playable-restore-") as temporary:
                source_root = Path(temporary)
                summary = self.copy_documentation_with_evidence(source_root)
                originals = {path: path.read_bytes() for path in self.targets(source_root)}
                calls: list[str] = []

                def replace(source: object, destination: object) -> None:
                    calls.append(Path(destination).name)  # type: ignore[arg-type]
                    if len(calls) == 3:
                        raise OSError("injected replace failure")
                    if len(calls) == failing_restore:
                        raise OSError("injected restore failure")
                    real_replace(source, destination)  # type: ignore[arg-type]

                with mock.patch.object(playable.os, "replace", side_effect=replace):
                    with self.assertRaises(RuntimeError) as caught:
                        playable.write_frontend_records(source_root, self.changed_summary(summary))
                self.assertEqual(str(caught.exception), f"evidence rollback incomplete: {failed_file.name}")
                self.assertNotIn(temporary, str(caught.exception))
                self.assertRegex(str(caught.exception.__cause__), "injected replace failure")
                self.assertEqual((source_root / restored_file).read_bytes(), originals[source_root / restored_file])
                if failed_file == playable.FRONTEND_EVIDENCE:  # the validation row text may be unchanged by the new summary
                    self.assertNotEqual((source_root / failed_file).read_bytes(), originals[source_root / failed_file])
                self.assertEqual(list(source_root.rglob("*.restore")), [])
                self.assertEqual(list(source_root.rglob("*.tmp")), [])

    def test_g3wr_04_restore_unlink_failure_does_not_abort_rollback(self) -> None:
        real_replace = os.replace
        real_unlink = Path.unlink
        with tempfile.TemporaryDirectory(prefix="playable-g3wr04-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            originals = {path: path.read_bytes() for path in self.targets(source_root)}
            calls: list[str] = []

            def replace(source: object, destination: object) -> None:
                calls.append(Path(destination).name)  # type: ignore[arg-type]
                if len(calls) == 3:
                    raise OSError("injected replace failure")
                real_replace(source, destination)  # type: ignore[arg-type]

            def unlink(self_path: Path, missing_ok: bool = False) -> None:
                if self_path.name.endswith(".restore"):
                    raise PermissionError("injected restore cleanup failure")
                real_unlink(self_path, missing_ok=missing_ok)

            raised: BaseException | None = None
            with mock.patch.object(playable.os, "replace", side_effect=replace), \
                    mock.patch.object(Path, "unlink", unlink):
                try:
                    playable.write_frontend_records(source_root, self.changed_summary(summary))
                except RuntimeError as error:
                    raised = error
                except Exception as error:  # noqa: BLE001 - report as an assertion, not an error
                    self.fail(f"uncaught {type(error).__name__}")
            self.assertIsNotNone(raised, "the rollback did not raise")
            message = str(raised)
            # G4IN-02 (intentional contract change): every file was restored, only `.restore` debris remains.
            self.assertTrue(message.startswith("evidence rollback complete; could not remove:"), message)
            self.assertIn(".restore", message)
            self.assertNotIn(temporary, message)
            self.assertRegex(str(raised.__cause__), "injected replace failure")
            for path, content in originals.items():
                self.assertEqual(path.read_bytes(), content)

    def test_g3wr_04_temporary_unlink_failure_does_not_mask_the_result(self) -> None:
        real_unlink = Path.unlink
        attempts: list[str] = []
        with tempfile.TemporaryDirectory(prefix="playable-g3wr04-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)

            def unlink(self_path: Path, missing_ok: bool = False) -> None:
                if self_path.name.endswith(".tmp"):
                    attempts.append(self_path.name)
                    if len(attempts) == 1:
                        raise PermissionError("injected temporary cleanup failure")
                real_unlink(self_path, missing_ok=missing_ok)

            with mock.patch.object(Path, "unlink", unlink):
                try:
                    playable.write_frontend_records(source_root, self.changed_summary(summary))
                except Exception as error:  # noqa: BLE001 - report as an assertion, not an error
                    self.fail(f"uncaught {type(error).__name__}")
            self.assertEqual(len(attempts), 3, "cleanup stopped after the first failing temporary")
            evidence = source_root / playable.FRONTEND_EVIDENCE
            self.assertEqual(json.loads(evidence.read_text(encoding="utf-8"))["os"], "macOS 99.0 arm64")

    def test_g4in_02_restore_succeeded_but_restore_file_remains(self) -> None:
        real_replace = os.replace
        real_unlink = Path.unlink
        with tempfile.TemporaryDirectory(prefix="playable-g4in02-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            originals = {path: path.read_bytes() for path in self.targets(source_root)}
            calls: list[str] = []

            def replace(source: object, destination: object) -> None:
                calls.append(Path(destination).name)  # type: ignore[arg-type]
                if len(calls) == 2:
                    raise OSError("injected replace failure")
                real_replace(source, destination)  # type: ignore[arg-type]

            def unlink(self_path: Path, missing_ok: bool = False) -> None:
                if self_path.name.endswith(".restore"):
                    raise PermissionError("injected restore cleanup failure")
                real_unlink(self_path, missing_ok=missing_ok)

            raised: BaseException | None = None
            with mock.patch.object(playable.os, "replace", side_effect=replace), \
                    mock.patch.object(Path, "unlink", unlink):
                try:
                    playable.write_frontend_records(source_root, self.changed_summary(summary))
                except RuntimeError as error:
                    raised = error
                except Exception as error:  # noqa: BLE001 - report as an assertion, not an error
                    self.fail(f"uncaught {type(error).__name__}")
            self.assertIsNotNone(raised, "the rollback did not raise")
            message = str(raised)
            self.assertTrue(message.startswith("evidence rollback complete; could not remove:"), message)
            self.assertIn(playable.FRONTEND_EVIDENCE.name + ".restore", message)
            self.assertNotIn("incomplete", message)
            self.assertNotIn(temporary, message)
            self.assertRegex(str(raised.__cause__), "injected replace failure")
            for path, content in originals.items():
                self.assertEqual(path.read_bytes(), content)

    def test_g4in_02_surviving_tmp_is_named(self) -> None:
        real_replace = os.replace
        real_unlink = Path.unlink
        attempts: list[str] = []
        with tempfile.TemporaryDirectory(prefix="playable-g4in02-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)

            def replace(source: object, destination: object) -> None:
                raise OSError("injected replace failure")

            def unlink(self_path: Path, missing_ok: bool = False) -> None:
                if self_path.name.endswith(".tmp"):
                    attempts.append(self_path.name)
                    if len(attempts) == 1:
                        raise PermissionError("injected temporary cleanup failure")
                real_unlink(self_path, missing_ok=missing_ok)

            raised: BaseException | None = None
            with mock.patch.object(playable.os, "replace", side_effect=replace), \
                    mock.patch.object(Path, "unlink", unlink):
                try:
                    playable.write_frontend_records(source_root, self.changed_summary(summary))
                except RuntimeError as error:
                    raised = error
                except Exception as error:  # noqa: BLE001 - report as an assertion, not an error
                    self.fail(f"uncaught {type(error).__name__}")
            self.assertIsNotNone(raised, "the failure with surviving debris did not raise a named error")
            self.assertIn(attempts[0], str(raised))
            self.assertNotIn(temporary, str(raised))
            self.assertRegex(str(raised.__cause__), "injected replace failure")

    def test_d58in_01_interrupt_is_not_replaced_by_a_runtime_error(self) -> None:
        real_replace = os.replace
        real_unlink = Path.unlink
        with tempfile.TemporaryDirectory(prefix="playable-d58in01-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            calls: list[str] = []

            def replace(source: object, destination: object) -> None:
                calls.append(Path(destination).name)  # type: ignore[arg-type]
                if len(calls) == 2:
                    raise KeyboardInterrupt()
                real_replace(source, destination)  # type: ignore[arg-type]

            def unlink(self_path: Path, missing_ok: bool = False) -> None:
                if self_path.name.endswith(".restore"):
                    raise PermissionError("injected restore cleanup failure")
                real_unlink(self_path, missing_ok=missing_ok)

            with mock.patch.object(playable.os, "replace", side_effect=replace), \
                    mock.patch.object(Path, "unlink", unlink), \
                    mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
                try:
                    playable.write_frontend_records(source_root, self.changed_summary(summary))
                except KeyboardInterrupt:
                    pass
                except BaseException as error:  # noqa: BLE001 - report as an assertion, not an error
                    self.fail(f"the interrupt was replaced by {type(error).__name__}")
                else:
                    self.fail("no exception was raised")
            self.assertIn("could not remove", stderr.getvalue())
            self.assertNotIn(temporary, stderr.getvalue())

    def test_d58in_03_broken_stderr_does_not_replace_the_interrupt(self) -> None:
        class BrokenStream:
            def write(self, _text: str) -> int:
                raise OSError("injected broken stderr")

            def flush(self) -> None:
                raise OSError("injected broken stderr")

        real_replace = os.replace
        real_unlink = Path.unlink
        with tempfile.TemporaryDirectory(prefix="playable-d58in03-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            calls: list[str] = []

            def replace(source: object, destination: object) -> None:
                calls.append(Path(destination).name)  # type: ignore[arg-type]
                if len(calls) == 2:
                    raise KeyboardInterrupt()
                real_replace(source, destination)  # type: ignore[arg-type]

            def unlink(self_path: Path, missing_ok: bool = False) -> None:
                if self_path.name.endswith(".restore"):
                    raise PermissionError("injected restore cleanup failure")
                real_unlink(self_path, missing_ok=missing_ok)

            with mock.patch.object(playable.os, "replace", side_effect=replace), \
                    mock.patch.object(Path, "unlink", unlink), \
                    mock.patch("sys.stderr", BrokenStream()):
                try:
                    playable.write_frontend_records(source_root, self.changed_summary(summary))
                except KeyboardInterrupt:
                    pass
                except BaseException as error:  # noqa: BLE001 - report as an assertion, not an error
                    self.fail(f"the interrupt was replaced by {type(error).__name__}")
                else:
                    self.fail("no exception was raised")

    def test_guide_status_block_is_written_last(self) -> None:
        real_replace = os.replace
        with tempfile.TemporaryDirectory(prefix="playable-order-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            order: list[str] = []

            def replace(source: object, destination: object) -> None:
                order.append(Path(destination).name)  # type: ignore[arg-type]
                real_replace(source, destination)  # type: ignore[arg-type]

            with mock.patch.object(playable.os, "replace", side_effect=replace):
                playable.write_frontend_records(source_root, self.changed_summary(summary))
        self.assertEqual(order, [playable.FRONTEND_EVIDENCE.name, playable.VALIDATION.name, playable.GUIDE.name])

    def test_successful_write_leaves_no_temporary_sibling(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-atomic-") as temporary:
            source_root = Path(temporary)
            summary = self.copy_documentation_with_evidence(source_root)
            before = self.digests(source_root)
            playable.write_frontend_records(source_root, self.changed_summary(summary))
            self.assertNotEqual(self.digests(source_root)[0], before[0])
            self.assertEqual(list(source_root.rglob("*.tmp")), [])


class MainErrorPathTest(unittest.TestCase):
    def test_explicit_headless_clean_reaches_snapshot_without_frontend_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(playable, "OUTPUT", Path(temporary)/"out"), \
                mock.patch.object(playable, "create_snapshot", side_effect=playable.SnapshotError(
                    "synthetic-source-failure", "synthetic failure")) as snapshot, \
                mock.patch.object(playable, "run_frontend_smoke_lane") as frontend, \
                mock.patch.object(sys, "argv", ["verify_playable.py", "--clean", "--headless"]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(playable.main(), 1)
            snapshot.assert_called_once()
            frontend.assert_not_called()
            receipt=json.loads((Path(temporary)/"out/receipt.json").read_text())
            self.assertEqual(receipt["qualification_scope"], "public-core-headless")
            self.assertEqual(receipt["retroarch_smoke"]["status"], "not-run")
            self.assertEqual(receipt["status"], "fail", "headless must preserve public build failures")

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

    def clean_docs_run(self, failure: BaseException) -> tuple[int, str, str, dict[str, object]]:
        with tempfile.TemporaryDirectory(prefix="playable-clean-docs-") as temporary:
            output = Path(temporary) / "out"
            snapshot = mock.Mock(commit="a" * 40, root=Path(temporary) / "source")
            with mock.patch.object(playable, "OUTPUT", output), \
                    mock.patch.object(playable, "create_snapshot", return_value=snapshot), \
                    mock.patch.object(playable, "verify_snapshot"), \
                    mock.patch.object(playable, "snapshot_record", return_value={"status": "pass"}), \
                    mock.patch.object(playable, "validate_snapshot_record"), \
                    mock.patch.object(playable, "check_docs", side_effect=failure):
                status, stdout, stderr = self.run_main(
                    "--retroarch", str(Path(temporary) / "R.app"), "--clean", "--check-docs")
            receipt_text = (output / "receipt.json").read_text(encoding="utf-8")
        return status, stdout, stderr, {"text": receipt_text, "json": json.loads(receipt_text)}

    def test_clean_documentation_check_error_is_a_redacted_receipt_failure(self) -> None:
        home = str(Path.home())
        failures = (OSError(2, "No such file or directory", home + "/private/guide.md"),
                    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
                    KeyError(home + "/private/guide.md"))
        for failure in failures:
            with self.subTest(error=type(failure).__name__):
                status, stdout, stderr, receipt = self.clean_docs_run(failure)
                self.assertEqual(status, 1)
                self.assertEqual(receipt["json"]["documentation"],  # type: ignore[index]
                                 {"status": "fail", "reason": f"documentation-check-error: {type(failure).__name__}"})
                for sink in (stdout, stderr, receipt["text"]):
                    self.assertNotIn(home, sink)
                    self.assertNotIn("guide.md", sink)
                    self.assertNotIn("Traceback", sink)

    def test_clean_documentation_runtime_error_keeps_its_scanned_message(self) -> None:
        home = str(Path.home())
        status, stdout, stderr, receipt = self.clean_docs_run(
            RuntimeError("integrator documentation omits: x " + home + "/private"))
        self.assertEqual(status, 1)
        documentation = receipt["json"]["documentation"]  # type: ignore[index]
        self.assertEqual(documentation["status"], "fail")
        self.assertIn("integrator documentation omits", documentation["reason"])
        for sink in (stdout, stderr, receipt["text"]):
            self.assertNotIn(home, sink)


    def receipt_run(self, patches: dict[str, object] | None = None, *, artifact_file=None,
                    build_failure: BaseException | None = None) -> tuple[int, str, str, Path | None]:
        """Run the clean qualification path with the snapshot stubbed; return the receipt path if written."""
        patches = patches or {}
        with tempfile.TemporaryDirectory(prefix="playable-receipt-") as temporary:
            output = Path(temporary) / "out"
            snapshot = mock.Mock(commit="a" * 40, root=Path(temporary) / "source")
            stack = contextlib.ExitStack()
            with stack:
                stack.enter_context(mock.patch.object(playable, "OUTPUT", output))
                stack.enter_context(mock.patch.object(
                    playable, "create_snapshot", side_effect=build_failure, return_value=snapshot))
                for name in ("verify_snapshot", "validate_snapshot_record"):
                    stack.enter_context(mock.patch.object(playable, name))
                stack.enter_context(mock.patch.object(playable, "snapshot_record", return_value={"status": "pass"}))
                if artifact_file is not None:
                    stack.enter_context(mock.patch.object(playable, "_artifact_file", side_effect=artifact_file(temporary)))
                for name, value in patches.items():
                    stack.enter_context(mock.patch.object(playable, name, **value))  # type: ignore[arg-type]
                status, stdout, stderr = self.run_main("--retroarch", str(Path(temporary) / "R.app"), "--clean")
            written = (output / "receipt.json")
            text = written.read_text(encoding="utf-8") if written.exists() else None
        return status, stderr, stdout, text  # type: ignore[return-value]

    @unittest.skipIf(os.geteuid() == 0, "root can read a mode 000 file")
    def test_t_04_11_unreadable_artifact_writes_a_fail_receipt_without_traceback(self) -> None:
        real = playable._artifact_file
        unreadable: list[Path] = []

        def factory(temporary: str):
            target = Path(temporary) / "unreadable-artifact.bin"
            target.write_bytes(b"x")
            target.chmod(0o000)
            unreadable.append(target)
            return lambda path, root: real(target, root)

        try:
            status, stderr, _stdout, text = self.receipt_run(artifact_file=factory)
        finally:
            for target in unreadable:
                if target.exists():
                    target.chmod(0o600)
        self.assertEqual(status, 1)
        self.assertIn("receipt: receipt-error: PermissionError", stderr)
        for forbidden in ("Traceback", str(Path.home()), "unreadable-artifact", tempfile.gettempdir()):
            self.assertNotIn(forbidden, stderr)
        self.assertIsNotNone(text)
        receipt = json.loads(text)  # type: ignore[arg-type]
        self.assertEqual(receipt["status"], "fail")
        self.assertEqual(receipt["reason"], "receipt-error: PermissionError")
        self.assertNotIn("unreadable-artifact", text)  # type: ignore[arg-type]

    def test_t_04_11_receipt_errors_of_any_type_are_fixed_tokens(self) -> None:
        home = str(Path.home())
        failures = (playable.SnapshotError("x", home + "/p"), KeyError(home + "/p"),
                    OSError(2, "gone", home + "/p"))
        for failure in failures:
            with self.subTest(error=type(failure).__name__):
                status, stderr, stdout, text = self.receipt_run({"_artifact_tree": {"side_effect": failure}})
                self.assertEqual(status, 1)
                self.assertIn(f"receipt: receipt-error: {type(failure).__name__}", stderr)
                for sink in (stderr, stdout, text or ""):
                    self.assertNotIn(home, sink)
                    self.assertNotIn("Traceback", sink)

    def test_t_04_11_failed_minimal_write_prints_receipt_write_failed(self) -> None:
        home = str(Path.home())
        status, stderr, stdout, _text = self.receipt_run(
            {"_write_receipt": {"side_effect": OSError(28, "No space", home + "/out")}})
        self.assertEqual(status, 1)
        self.assertIn("receipt: receipt-write-failed", stderr)
        for sink in (stderr, stdout):
            self.assertNotIn("Traceback", sink)
            self.assertNotIn(home, sink)

    def test_g2in_03_build_failure_reason_uses_public_reason(self) -> None:
        home = str(Path.home())
        real = playable._public_reason
        with mock.patch.object(playable, "_public_reason", side_effect=real) as wrapper:
            status, _stderr, _stdout, text = self.receipt_run(build_failure=RuntimeError(home + "/x"))
        self.assertEqual(status, 1)
        self.assertTrue(any(home in call.args[0] for call in wrapper.call_args_list))
        self.assertNotIn(home, text or "")

    def guarded_main(self, output: Path, *arguments: str) -> tuple[int | None, str, str]:
        """Run main() against a test-owned OUTPUT; report an escaped exception as a failure, not an error."""
        try:
            with mock.patch.object(playable, "OUTPUT", output):
                return self.run_main(*arguments)
        except Exception as error:  # noqa: BLE001 - the regression is that main() leaks it
            self.fail(f"uncaught {type(error).__name__}")
        return None, "", ""

    def test_t_04_11_output_mkdir_error_is_a_typed_token(self) -> None:
        home = str(Path.home())
        with tempfile.TemporaryDirectory(prefix="playable-setup-") as temporary:
            output = Path(temporary) / "out"
            failure = PermissionError(13, "Permission denied", str(ROOT / "build/playable-qualification"))
            with mock.patch.object(Path, "mkdir", side_effect=failure):
                status, stdout, stderr = self.guarded_main(
                    output, "--retroarch", str(Path(temporary) / "RetroArch.app"), "--clean")
        self.assertEqual(status, 1)
        self.assertEqual(stderr.strip(), "qualification: setup-error: PermissionError")
        for sink in (stdout, stderr):
            for forbidden in ("Traceback", str(ROOT), home):
                self.assertNotIn(forbidden, sink)

    def test_t_04_11_mkdtemp_error_writes_a_setup_fail_receipt(self) -> None:
        home = str(Path.home())
        with tempfile.TemporaryDirectory(prefix="playable-setup-") as temporary:
            output = Path(temporary) / "out"
            output.mkdir()
            failure = OSError(28, "No space left on device", str(output))
            with mock.patch.object(playable.tempfile, "mkdtemp", side_effect=failure):
                status, stdout, stderr = self.guarded_main(
                    output, "--retroarch", str(Path(temporary) / "RetroArch.app"), "--clean")
            text = (output / "receipt.json").read_text(encoding="utf-8")
        receipt = json.loads(text)
        self.assertEqual(status, 1)
        self.assertIn("qualification: setup-error: OSError", stderr)
        self.assertEqual(receipt["status"], "fail")
        self.assertEqual(receipt["reason"], "setup-error: OSError")
        for sink in (stdout, stderr, text):
            for forbidden in ("Traceback", str(ROOT), home, temporary):
                self.assertNotIn(forbidden, sink)

    def test_t_04_11_setup_error_with_failed_receipt_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="playable-setup-") as temporary:
            output = Path(temporary) / "out"
            output.mkdir()
            with mock.patch.object(playable.tempfile, "mkdtemp", side_effect=OSError(28, "No space", str(output))), \
                    mock.patch.object(playable, "_write_receipt", side_effect=OSError(28, "No space", str(output))):
                status, stdout, stderr = self.guarded_main(
                    output, "--retroarch", str(Path(temporary) / "RetroArch.app"), "--clean")
        self.assertEqual(status, 1)
        self.assertIn("qualification: setup-error: OSError", stderr)
        self.assertIn("receipt: receipt-write-failed", stderr)
        for sink in (stdout, stderr):
            self.assertNotIn("Traceback", sink)
            self.assertNotIn(temporary, sink)

    def run_script_entry(self, patch_lines: str, tools: Path = ROOT / "tools") -> subprocess.CompletedProcess[str]:
        """Run the real script entry in a child interpreter; the child patches one failure and uses a test-owned cwd.

        The child runs a test-owned copy of the entry modules: main() resolves ROOT from the script path
        and creates ROOT/build/playable-qualification, which must not land in the checked source tree.
        """
        with tempfile.TemporaryDirectory(prefix="playable-entry-") as temporary:
            work = Path(temporary) / "work"
            work.mkdir()
            source_tools = tools
            tools = Path(temporary) / "root" / "tools"
            tools.mkdir(parents=True)
            for name in ("verify_playable.py", "private_paths.py"):
                shutil.copy2(source_tools / name, tools / name)
            script = tools / "verify_playable.py"
            code = (
                "import platform, runpy, sys, tempfile\n"
                f"sys.argv = ['verify_playable.py', '--retroarch', {str(Path(temporary) / 'R.app')!r}, '--clean']\n"
                f"sys.path.insert(0, {str(tools)!r})\n"
                f"_owned = {str(work)!r}\n"
                + patch_lines +
                f"runpy.run_path({str(script)!r}, run_name='__main__')\n"
            )
            # -I ignores PYTHONDONTWRITEBYTECODE; -B keeps the child from writing tools/__pycache__.
            return subprocess.run([sys.executable, "-I", "-B", "-c", code], cwd=temporary, text=True,
                                  capture_output=True, timeout=120, check=False)

    def test_t_04_11_entry_maps_uncaught_errors_without_traceback(self) -> None:
        result = self.run_script_entry(
            "tempfile.mkdtemp = lambda *a, **k: _owned\n"
            f"def _boom(*a, **k):\n    raise ValueError({str(ROOT)!r})\n"
            "platform.platform = _boom\n")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("verify_playable: internal-error: ValueError", result.stderr)
        for sink in (result.stdout, result.stderr):
            self.assertNotIn("Traceback", sink)
            self.assertNotIn(str(ROOT), sink)

    def test_t_04_11_entry_maps_interrupt_to_130(self) -> None:
        result = self.run_script_entry(
            "def _interrupt(*a, **k):\n    raise KeyboardInterrupt()\n"
            "tempfile.mkdtemp = _interrupt\n")
        self.assertEqual(result.returncode, 130, result.stderr)
        self.assertIn("verify_playable: interrupted", result.stderr)
        for sink in (result.stdout, result.stderr):
            self.assertNotIn("Traceback", sink)
            self.assertNotIn(str(ROOT), sink)

    def test_entry_child_writes_nothing_into_the_source_tree(self) -> None:
        # The qualification runner executes this suite inside the materialized source snapshot and
        # verifies its inventory after the lane. -I ignores PYTHONDONTWRITEBYTECODE, so a child that
        # imported private_paths wrote tools/__pycache__ into the snapshot (snapshot-inventory-mismatch).
        # main() also creates ROOT/build/playable-qualification before the patched mkdtemp; those empty
        # directories were invisible to the file inventory and made the later ym2610-installed-linkages
        # overlay fail with generated-output-path-conflict; verify_snapshot now also detects added
        # directories (04-52), and the child still must not run under the source root.
        with tempfile.TemporaryDirectory(prefix="playable-entry-tools-") as temporary:
            source = Path(temporary)
            tools = source / "tools"
            tools.mkdir()
            for name in ("verify_playable.py", "private_paths.py"):
                shutil.copy2(ROOT / "tools" / name, tools / name)
            result = self.run_script_entry(
                "def _interrupt(*a, **k):\n    raise KeyboardInterrupt()\n"
                "tempfile.mkdtemp = _interrupt\n", tools=tools)
            self.assertEqual(result.returncode, 130, result.stderr)
            self.assertEqual(sorted(path.relative_to(source).as_posix() for path in source.rglob("*")),
                             ["tools", "tools/private_paths.py", "tools/verify_playable.py"])

    def test_t_04_11_argparse_exit_passes_through(self) -> None:
        with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()):
            self.run_main("--bogus")
        self.assertEqual(caught.exception.code, 2)


class SquashMergeHistoryTest(DocumentationCopies, unittest.TestCase):
    """Per-row allowlisted tolerance of history-absent pre-ship rows after a squash merge (G5WR-01, T-04-104)."""

    NOTE = "allowlisted pre-ship row (first-playable-game branch)"
    DISPOSITION_HEADER = "| Finding | Severity | Disposition | Source |\n|---|---|---|---|\n"

    def test_g5wr_01_documentation_copies_carry_rights_row_files(self) -> None:
        """The helper models a checkout: every non-third_party rights row's working-tree file is copied (G5WR-01, C1)."""
        items = public_content.load_rights_inventory(ROOT)["items"]
        paths = [item["path"] for item in items if not item["path"].startswith("third_party/")]
        self.assertTrue(paths, "the rights inventory has no non-third_party row")
        with tempfile.TemporaryDirectory(prefix="playable-docs-rights-files-") as temporary:
            source_root = Path(temporary)
            self.copy_review_provenance(source_root)
            for path in paths:
                with self.subTest(path=path):
                    self.assertTrue((source_root / path).is_file(), "rights-row file not copied")
                    self.assertEqual((source_root / path).read_bytes(), (ROOT / path).read_bytes())
        with tempfile.TemporaryDirectory(prefix="playable-docs-rights-sentinel-") as temporary:
            source_root = Path(temporary)
            target = source_root / paths[0]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"caller-placed sentinel\n")
            self.copy_review_provenance(source_root)
            self.assertEqual(target.read_bytes(), b"caller-placed sentinel\n")

    @staticmethod
    def git(cwd: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *arguments],
            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.strip()

    @staticmethod
    def sha(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def canonical(value: object) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=False).encode("utf-8")).hexdigest()

    @staticmethod
    def item(path: str, text: str, revision: str, license: str = "MIT") -> dict[str, str]:
        return {"path": path, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "kind": "test",
                "license": license, "rights": "original", "source_revision": revision,
                "provenance": "fixture", "notice": "none"}

    def write_inventory(self, root: Path, items: list[dict[str, str]]) -> None:
        (root / "docs").mkdir(exist_ok=True)
        (root / playable.RIGHTS_INVENTORY).write_text(
            "# Inventory\n\n```json\n" + json.dumps({"schema": 1, "items": items}) + "\n```\n", encoding="utf-8")

    def write_review(self, root: Path, revision: str, body: str = "body\n") -> None:
        (root / playable.REVIEW).parent.mkdir(parents=True, exist_ok=True)
        (root / playable.REVIEW).write_text(
            f"---\nphase: x\nreviewed_revision: {revision}\n---\n\n{body}", encoding="utf-8")

    def write_disposition(self, root: Path, rows: list[tuple[str, str, str, str]]) -> None:
        (root / playable.DISPOSITION).parent.mkdir(parents=True, exist_ok=True)
        (root / playable.DISPOSITION).write_text(
            self.DISPOSITION_HEADER + "".join(f"| {a} | {b} | {c} | {d} |\n" for a, b, c, d in rows), encoding="utf-8")

    def allowlist(self, root: Path, rows: list[tuple[str, str, str]], base: str) -> None:
        """Write docs/history-allowlist.json; every pin is computed here from the records under `root`."""
        entries = []
        for kind, key, revision in rows:
            if kind == "reviewed_revision":
                value = re.search(r"^reviewed_revision: (\S+)$", (root / playable.REVIEW).read_text(encoding="utf-8"),
                                  re.MULTILINE).group(1)
                pin = self.sha(f"reviewed_revision: {value}")
            elif kind == "review_citation":
                line = next(line.rstrip() for line in (root / playable.DISPOSITION).read_text(encoding="utf-8").splitlines()
                            if line.startswith(f"| {key} |"))
                pin = self.sha(line)
            elif kind == "frontend_receipt":
                pin = self.canonical(json.loads((root / playable.FRONTEND_EVIDENCE).read_text(encoding="utf-8")))
            else:
                text = (root / playable.RIGHTS_INVENTORY).read_text(encoding="utf-8")
                items = json.loads(re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL).group(1))["items"]
                pin = self.canonical(next(item for item in items if item["path"] == key))
            entries.append({"kind": kind, "key": key, "revision": revision, "pin": pin})
        (root / "docs").mkdir(exist_ok=True)
        (root / "docs/history-allowlist.json").write_text(json.dumps({
            "schema": 1, "scope": "first-playable-game milestone branch pre-ship records",
            "base_revision": base, "rows": entries}, indent=1), encoding="utf-8")

    def commit(self, repo: Path, message: str, *paths: str) -> str:
        self.git(repo, "add", "--", *paths)
        self.git(repo, "commit", "-q", "-m", message)
        return self.git(repo, "rev-parse", "HEAD")

    def squashed(self, base: Path, base_row: bool = False):
        """A feature branch (F1..F4) squash-merged into main, plus a single-branch clone without the branch objects.

        With `base_row`, the base commit also adds `tests/base.txt` and the inventory gets a row citing it.
        """
        from types import SimpleNamespace
        repo = base / "repo"
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        (repo / "base.txt").write_text("base\n", encoding="utf-8")
        base_paths = ["base.txt"]
        if base_row:
            (repo / "tests").mkdir()
            (repo / "tests/base.txt").write_text("base two\n", encoding="utf-8")
            base_paths.append("tests/base.txt")
        main_base = self.commit(repo, "base", *base_paths)
        self.git(repo, "checkout", "-q", "-b", "feature")
        (repo / "tests").mkdir(exist_ok=True)
        (repo / "tests/a.txt").write_text("one\n", encoding="utf-8")
        gaps = repo / playable.PHASE_DIRECTORY / "04-REVIEW-GAPS.md"
        gaps.parent.mkdir(parents=True)
        gaps.write_text("gaps\n", encoding="utf-8")
        f1 = self.commit(repo, "f1", "tests/a.txt", gaps.relative_to(repo).as_posix())
        (repo / "tests/a.txt").write_text("two\n", encoding="utf-8")
        f2 = self.commit(repo, "f2", "tests/a.txt")
        self.write_inventory(repo, [self.item("tests/a.txt", "two\n", f2),
                                    *([self.item("tests/base.txt", "base two\n", main_base)] if base_row else [])])
        self.write_review(repo, f1)
        self.write_disposition(repo, [("CR-01", "critical", "fixed", f"revision `{f2}`"),
                                      ("GWR-01", "warning", "fixed", f"revision `{f2}`")])
        f3 = self.commit(repo, "f3", playable.RIGHTS_INVENTORY.as_posix(), playable.REVIEW.as_posix(),
                         playable.DISPOSITION.as_posix())
        self.allowlist(repo, [("reviewed_revision", "04-REVIEW.md", f1), ("review_citation", "CR-01", f2),
                              ("review_citation", "GWR-01", f2), ("rights", "tests/a.txt", f2)], main_base)
        f4 = self.commit(repo, "f4", "docs/history-allowlist.json")
        self.git(repo, "checkout", "-q", "main")
        self.git(repo, "merge", "--squash", "feature")
        self.git(repo, "commit", "-q", "-m", "squash")
        clone = base / "clone"
        self.git(base, "clone", "-q", "--no-local", "--single-branch", "--branch", "main", str(repo), str(clone))
        return SimpleNamespace(repo=repo, clone=clone, B=main_base, F1=f1, F2=f2, F3=f3, F4=f4)

    def fixture(self, base_row: bool = False) -> "SimpleNamespace":
        temporary = tempfile.TemporaryDirectory(prefix="playable-squash-")
        self.addCleanup(temporary.cleanup)
        return self.squashed(Path(temporary.name), base_row)

    def source_identity_fixture(self) -> "SimpleNamespace":
        """A source record and its outer rights row across a full branch, squash, and fresh clone."""
        from types import SimpleNamespace

        temporary = tempfile.TemporaryDirectory(prefix="playable-source-identity-squash-")
        self.addCleanup(temporary.cleanup)
        base_dir = Path(temporary.name)
        repo = base_dir / "repo"
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        (repo / "base.txt").write_text("base\n", encoding="utf-8")
        base = self.commit(repo, "base", "base.txt")
        self.git(repo, "checkout", "-q", "-b", "feature")

        source_path = "tests/source.c"
        source_bytes = b"source identity bytes\n"
        (repo / source_path).parent.mkdir(parents=True)
        (repo / source_path).write_bytes(source_bytes)
        source_revision = self.commit(repo, "source", source_path)

        manifest_path = playable.FIXTURE_RIGHTS_MANIFEST.as_posix()
        record = {
            "path": source_path, "source_revision": source_revision,
            "sha256": hashlib.sha256(source_bytes).hexdigest(), "bytes": len(source_bytes),
            "license": "MIT", "notice": "LICENSE",
        }
        manifest = {"mvs_save_fixture": {"generator_source": record}}
        manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        manifest_file = repo / manifest_path
        manifest_file.parent.mkdir(parents=True)
        manifest_file.write_bytes(manifest_bytes)
        manifest_revision = self.commit(repo, "manifest", manifest_path)

        outer = {
            "path": manifest_path, "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "kind": "fixture-rights-manifest", "license": "MIT", "rights": "affirmative",
            "source_revision": manifest_revision, "provenance": "fixture manifest",
            "notice": "LICENSE",
        }
        self.write_inventory(repo, [outer])
        self.commit(repo, "outer rights row", playable.RIGHTS_INVENTORY.as_posix())
        generated = json.loads(self.generate(repo, base="main"))
        self.assertEqual(generated["rows"], [{
            "kind": "rights", "key": manifest_path, "revision": manifest_revision,
            "pin": self.canonical(outer),
        }])
        (repo / playable.HISTORY_ALLOWLIST).write_text(
            json.dumps(generated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.commit(repo, "allowlist outer rights row", playable.HISTORY_ALLOWLIST.as_posix())

        self.git(repo, "checkout", "-q", "main")
        self.git(repo, "merge", "--squash", "feature")
        self.git(repo, "commit", "-q", "-m", "squash feature")
        clone = base_dir / "clone"
        self.git(base_dir, "clone", "-q", "--no-local", "--single-branch", "--branch", "main",
                 str(repo), str(clone))
        shallow_clone = base_dir / "shallow-clone"
        self.git(base_dir, "clone", "-q", "--depth=1", "--no-local", "--single-branch", "--branch", "main",
                 repo.as_uri(), str(shallow_clone))
        return SimpleNamespace(repo=repo, clone=clone, base=base, source_revision=source_revision,
                               shallow_clone=shallow_clone, manifest_revision=manifest_revision,
                               manifest_path=manifest_path)

    def gate(self, function_name: str, root: Path, *extra: object) -> tuple[list[str], list[str]]:
        function = getattr(playable, function_name, None)
        self.assertIsNotNone(function, f"{function_name} is missing")
        notes: list[str] = []
        try:
            return function(root, root, "HEAD", unverifiable=notes), notes
        except Exception as error:  # noqa: BLE001 - red must fail on an assertion, not on an exception
            self.fail(f"uncaught {type(error).__name__}")

    def test_g5wr_01_rights_row_tolerated_after_squash(self) -> None:
        fx = self.fixture()
        resolves = subprocess.run(["git", "-C", str(fx.repo), "rev-parse", "--verify", "--quiet", f"{fx.F2}^{{commit}}"],
                                  stdout=subprocess.DEVNULL, check=False).returncode
        self.assertEqual(resolves, 0, "the local squash must still hold the branch objects")
        absent = subprocess.run(["git", "-C", str(fx.clone), "rev-parse", "--verify", "--quiet", f"{fx.F2}^{{commit}}"],
                                stdout=subprocess.DEVNULL, check=False).returncode
        self.assertNotEqual(absent, 0, "the single-branch clone must not hold the branch objects")
        results = []
        for root in (fx.repo, fx.clone):
            errors, notes = self.gate("rights_revision_errors", root)
            self.assertEqual(errors, [])
            self.assertEqual(len(notes), 1, notes)
            for expected in ("tests/a.txt", self.NOTE, fx.F2[:12]):
                self.assertIn(expected, notes[0])
            results.append((errors, notes))
        self.assertEqual(results[0], results[1])

    def test_squash_source_identity_uses_only_pinned_outer_manifest_and_checked_head_bytes(self) -> None:
        fx = self.source_identity_fixture()
        retained_notes: list[str] = []
        self.assertEqual(playable.fixture_source_identity_errors(
            fx.repo, fx.repo, "HEAD", unverifiable=retained_notes), [])
        self.assertTrue(any("available but not ordered with the checked head" in note for note in retained_notes),
                        retained_notes)
        self.assertTrue(any("cited blob matches under the exact outer rights-manifest pin" in note
                            for note in retained_notes), retained_notes)

        unpinned_retained = playable.HistoryAllowlist(rows={}, base_revision=fx.base)
        errors = playable.fixture_source_identity_errors(
            fx.repo, fx.repo, "HEAD", allowlist=unpinned_retained)
        self.assertTrue(errors, "available unrelated source objects must still require the exact outer pin")

        for revision in (fx.source_revision, fx.manifest_revision):
            absent = subprocess.run(["git", "-C", str(fx.clone), "rev-parse", "--verify", "--quiet",
                                     f"{revision}^{{commit}}"], stdout=subprocess.DEVNULL, check=False)
            self.assertNotEqual(absent.returncode, 0, "fresh clone must not retain feature-history objects")
        notes: list[str] = []
        self.assertEqual(playable.fixture_source_identity_errors(
            fx.clone, fx.clone, "HEAD", unverifiable=notes), [])
        self.assertTrue(any("historical commit unavailable" in note for note in notes), notes)
        self.assertTrue(any("outer rights-row pin" in note or "rights-row pin" in note for note in notes), notes)

        shallow_notes: list[str] = []
        self.assertEqual(playable.fixture_source_identity_errors(
            fx.shallow_clone, fx.shallow_clone, "HEAD", unverifiable=shallow_notes), [])
        self.assertTrue(any("shallow" in note for note in shallow_notes), shallow_notes)
        self.assertTrue(any("outer rights-row pin" in note or "rights-row pin" in note for note in shallow_notes),
                        shallow_notes)

        allowlist_path = fx.clone / playable.HISTORY_ALLOWLIST
        valid_allowlist = allowlist_path.read_text(encoding="utf-8")
        allowlist = json.loads(valid_allowlist)
        allowlist["rows"] = []
        allowlist_path.write_text(json.dumps(allowlist, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        errors = playable.fixture_source_identity_errors(fx.clone, fx.clone, "HEAD")
        self.assertTrue(errors, "source identity must fail if the outer rights row is unpinned")
        allowlist_path.write_text(valid_allowlist, encoding="utf-8")

        manifest_path = fx.clone / fx.manifest_path
        original = manifest_path.read_text(encoding="utf-8")
        for field, replacement in (("path", "tests/substituted.c"), ("sha256", "0" * 64), ("bytes", 1)):
            mutated = json.loads(original)
            mutated["mvs_save_fixture"]["generator_source"][field] = replacement
            with self.subTest(field=field):
                problems = playable.fixture_source_identity_errors(fx.clone, fx.clone, "HEAD", manifest=mutated)
                self.assertTrue(problems, f"mutated source record {field} passed")

        # An exact outer-manifest pin still cannot excuse an available unrelated commit
        # whose cited source blob differs from the checked-head bytes.
        wrong_source = b"different historical source bytes\n"
        self.git(fx.repo, "checkout", "-q", "-b", "wrong-source-origin", "main")
        (fx.repo / "tests/source.c").write_bytes(wrong_source)
        wrong_revision = self.commit(fx.repo, "wrong source blob", "tests/source.c")
        self.git(fx.repo, "checkout", "-q", "main")
        manifest_path = fx.repo / fx.manifest_path
        changed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        changed_manifest["mvs_save_fixture"]["generator_source"]["source_revision"] = wrong_revision
        manifest_path.write_text(json.dumps(changed_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_revision = self.commit(fx.repo, "substitute unrelated source revision", fx.manifest_path)
        inventory_path = fx.repo / playable.RIGHTS_INVENTORY
        inventory_text = inventory_path.read_text(encoding="utf-8")
        inventory = json.loads(re.search(r"```json\s*\n(.*?)\n```", inventory_text, re.DOTALL).group(1))
        outer = next(item for item in inventory["items"] if item["path"] == fx.manifest_path)
        outer["sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        outer["source_revision"] = manifest_revision
        self.write_inventory(fx.repo, [outer])
        self.commit(fx.repo, "refresh substituted outer rights row", playable.RIGHTS_INVENTORY.as_posix())
        wrong_origin_pin = playable.HistoryAllowlist(
            rows={("rights", fx.manifest_path, manifest_revision): playable._canonical_digest(outer)},
            base_revision=fx.base)
        problems = playable.fixture_source_identity_errors(
            fx.repo, fx.repo, "HEAD", allowlist=wrong_origin_pin)
        self.assertTrue(any("does not hold the recorded bytes" in problem for problem in problems), problems)

    def test_g5wr_01_cli_prints_one_line_per_tolerated_row(self) -> None:
        with mock.patch.object(playable, "check_docs", return_value=["note one", "note two"]), \
                mock.patch.object(sys, "argv", ["verify_playable.py", "--check-docs"]), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout, \
                mock.patch("sys.stderr", new_callable=io.StringIO):
            status = playable.main()
        self.assertEqual(status, 0)
        self.assertEqual(stdout.getvalue(), "unverifiable-history: note one\nunverifiable-history: note two\n"
                         "Phase 04 documentation gate passed.\n")


    # ---- helpers for the adversarial cases ----

    def items(self, root: Path) -> list[dict[str, str]]:
        text = (root / playable.RIGHTS_INVENTORY).read_text(encoding="utf-8")
        return json.loads(re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL).group(1))["items"]

    def add_rights_row(self, root: Path, path: str, text: str, revision: str) -> None:
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
        self.write_inventory(root, [*self.items(root), self.item(path, text, revision)])

    def append_disposition(self, root: Path, row: str) -> None:
        with (root / playable.DISPOSITION).open("a", encoding="utf-8") as handle:
            handle.write(row + "\n")

    def both(self, root: Path) -> tuple[list[str], list[str], list[str], list[str]]:
        rights_errors, rights_notes = self.gate("rights_revision_errors", root)
        review_errors, review_notes = self.gate("review_provenance_errors", root)
        return rights_errors, rights_notes, review_errors, review_notes

    def stale(self, root: Path) -> list[str]:
        function = getattr(playable, "history_allowlist_stale", None)
        self.assertIsNotNone(function, "history_allowlist_stale is missing")
        try:
            return function(root)
        except Exception as error:  # noqa: BLE001
            self.fail(f"uncaught {type(error).__name__}")

    def assert_all_noted(self, root: Path) -> None:
        rights_errors, rights_notes, review_errors, review_notes = self.both(root)
        self.assertEqual((rights_errors, review_errors), ([], []))
        self.assertEqual(len(rights_notes), 1, rights_notes)
        self.assertEqual(len(review_notes), 3, review_notes)
        for note in (*rights_notes, *review_notes):
            self.assertIn(self.NOTE, note)

    def check_fabricated(self, root: Path, *, tolerated: bool) -> None:
        """Fabricated rows (never in the allowlist) fail the same way on full history and on a squashed main."""
        inventory = (root / playable.RIGHTS_INVENTORY).read_text(encoding="utf-8")
        review = (root / playable.REVIEW).read_text(encoding="utf-8")
        disposition = (root / playable.DISPOSITION).read_text(encoding="utf-8")
        # (1) a fabricated rights revision
        self.add_rights_row(root, "tests/b.txt", "b\n", "f" * 40)
        errors, notes = self.gate("rights_revision_errors", root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("tests/b.txt", errors[0])
        self.assertTrue(errors[0].endswith("does not resolve"), errors[0])
        self.assertFalse([note for note in notes if "tests/b.txt" in note], notes)
        (root / playable.RIGHTS_INVENTORY).write_text(inventory, encoding="utf-8")
        # (2) a fabricated reviewed_revision
        self.write_review(root, "e" * 40)
        errors, _notes = self.gate("review_provenance_errors", root)
        self.assertEqual(errors, ["reviewed revision eeeeeeeeeeee is not a committed ancestor of the checked head"])
        (root / playable.REVIEW).write_text(review, encoding="utf-8")
        # (3) a fabricated citation; the append voids no other pin
        self.append_disposition(root, f"| CR-02 | warning | fixed | revision `{'f' * 40}` |")
        errors, notes = self.gate("review_provenance_errors", root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("review finding CR-02 cites revision ffffffffffff that is not a committed ancestor", errors[0])
        self.assertEqual(any("CR-01" in note for note in notes), tolerated, notes)
        self.assertEqual(any("GWR-01" in note for note in notes), tolerated, notes)
        (root / playable.DISPOSITION).write_text(disposition, encoding="utf-8")

    # ---- review provenance, receipts and adversarial rows ----

    def test_g5wr_01_review_tolerated_after_squash(self) -> None:
        fx = self.fixture()
        results = []
        for root in (fx.repo, fx.clone):
            errors, notes = self.gate("review_provenance_errors", root)
            self.assertEqual(errors, [])
            self.assertEqual(len(notes), 3, notes)
            for note in notes:
                self.assertIn(self.NOTE, note)
            self.assertTrue(any("04-REVIEW.md" in note and fx.F1[:12] in note for note in notes), notes)
            self.assertTrue(any("CR-01" in note for note in notes), notes)
            self.assertTrue(any("GWR-01" in note for note in notes), notes)
            results.append((errors, notes))
        self.assertEqual(results[0], results[1])

    def test_g5wr_01_unrelated_resolving_unlisted_row_fails_strict(self) -> None:
        fx = self.fixture()
        for root, rights_message in ((fx.repo, "is not an ancestor of the checked head"), (fx.clone, "does not resolve")):
            self.add_rights_row(root, "tests/c.txt", "c\n", fx.F1)
            self.append_disposition(root, f"| CR-04 | warning | fixed | revision `{fx.F1}` |")
            rights_errors, rights_notes, review_errors, review_notes = self.both(root)
            self.assertEqual(len(rights_errors), 1, rights_errors)
            self.assertIn("tests/c.txt", rights_errors[0])
            self.assertTrue(rights_errors[0].endswith(rights_message), rights_errors[0])
            self.assertFalse([note for note in rights_notes if "tests/c.txt" in note], rights_notes)
            self.assertEqual(len(rights_notes), 1, rights_notes)
            self.assertEqual(len(review_errors), 1, review_errors)
            self.assertIn(f"review finding CR-04 cites revision {fx.F1[:12]} that is not a committed ancestor", review_errors[0])
            self.assertEqual(len(review_notes), 3, review_notes)

    def test_g5wr_01_full_history_has_no_notes(self) -> None:
        fx = self.fixture()
        self.git(fx.repo, "checkout", "-q", "feature")
        rights_errors, rights_notes, review_errors, review_notes = self.both(fx.repo)
        self.assertEqual((rights_errors, rights_notes, review_errors, review_notes), ([], [], [], []))
        self.assertEqual(self.stale(fx.repo), [])

    def test_g5wr_01_fabricated_rows_not_allowlisted_fail_everywhere(self) -> None:
        fx = self.fixture()
        self.git(fx.repo, "checkout", "-q", "feature")
        self.check_fabricated(fx.repo, tolerated=False)
        self.check_fabricated(fx.clone, tolerated=True)

    def test_g5wr_01_side_branch_and_descendant_fail_on_full_history(self) -> None:
        fx = self.fixture()
        self.git(fx.repo, "checkout", "-q", "-b", "side", fx.F1)
        (fx.repo / "tests/a.txt").write_text("two\n", encoding="utf-8")
        side = self.commit(fx.repo, "side", "tests/a.txt")
        self.git(fx.repo, "checkout", "-q", "feature")
        self.write_inventory(fx.repo, [self.item("tests/a.txt", "two\n", side)])
        errors, notes = self.gate("rights_revision_errors", fx.repo)
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].endswith("is not an ancestor of the checked head"), errors[0])
        self.assertEqual(notes, [])
        self.git(fx.repo, "checkout", "-q", "--", playable.RIGHTS_INVENTORY.as_posix())
        self.git(fx.repo, "checkout", "-q", "--detach", fx.F2)
        self.write_inventory(fx.repo, [self.item("tests/a.txt", "two\n", fx.F3)])
        self.allowlist(fx.repo, [("rights", "tests/a.txt", fx.F3)], fx.B)
        errors, notes = self.gate("rights_revision_errors", fx.repo)
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].endswith("is not an ancestor of the checked head"), errors[0])
        self.assertEqual(notes, [])

    def test_g5wr_01_editing_a_pinned_row_voids_only_that_row(self) -> None:
        fx = self.fixture()
        root = fx.clone
        text = (root / playable.DISPOSITION).read_text(encoding="utf-8")
        (root / playable.DISPOSITION).write_text(
            text.replace(f"| CR-01 | critical | fixed | revision `{fx.F2}` |",
                         f"| CR-01 | critical | fixed | revision `{fx.F2}` x |"), encoding="utf-8")
        errors, notes = self.gate("review_provenance_errors", root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn(f"review finding CR-01 cites revision {fx.F2[:12]} that is not a committed ancestor", errors[0])
        self.assertFalse([note for note in notes if "CR-01" in note], notes)
        self.assertTrue([note for note in notes if "GWR-01" in note], notes)
        self.assertEqual(self.stale(root), ["review_citation CR-01"])
        (root / playable.DISPOSITION).write_text(text, encoding="utf-8")
        self.write_inventory(root, [self.item("tests/a.txt", "two\n", fx.F2, license="Apache-2.0")])
        errors, notes = self.gate("rights_revision_errors", root)
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].endswith("does not resolve"), errors[0])
        self.assertEqual(notes, [])

    def test_g5wr_01_appending_keeps_every_pin(self) -> None:
        fx = self.fixture()
        root = fx.clone
        head = self.git(root, "rev-parse", "HEAD")
        self.append_disposition(root, "| CR-03 | info | open | recorded |")
        with (root / playable.REVIEW).open("a", encoding="utf-8") as handle:
            handle.write("\nA new paragraph of review prose.\n")
        (root / playable.PHASE_DIRECTORY / "04-REVIEW-GAPS-R2.md").write_text("round two\n", encoding="utf-8")
        self.write_inventory(root, [*self.items(root), self.item("base.txt", "base\n", head)])
        self.commit(root, "append", playable.DISPOSITION.as_posix(), playable.REVIEW.as_posix(),
                    (playable.PHASE_DIRECTORY / "04-REVIEW-GAPS-R2.md").as_posix(), playable.RIGHTS_INVENTORY.as_posix())
        self.assert_all_noted(root)
        self.assertEqual(self.stale(root), [])

    def test_g5wr_01_rights_digest_still_binds(self) -> None:
        fx = self.fixture()
        (fx.clone / "tests/a.txt").write_text("tampered\n", encoding="utf-8")
        self.commit(fx.clone, "tamper", "tests/a.txt")
        errors, notes = self.gate("rights_revision_errors", fx.clone)
        self.assertEqual(len(errors), 1, errors)
        for expected in ("tests/a.txt", "unverifiable-history", "does not hold the recorded SHA-256"):
            self.assertIn(expected, errors[0])
        self.assertEqual(notes, [])
        self.git(fx.clone, "rm", "-q", "--", "tests/a.txt")
        self.git(fx.clone, "commit", "-q", "-m", "remove")
        errors, _notes = self.gate("rights_revision_errors", fx.clone)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("is missing", errors[0])

    def test_g5wr_01_branch_cut_from_squashed_main(self) -> None:
        fx = self.fixture()
        root = fx.clone
        self.git(root, "checkout", "-q", "-b", "later")
        (root / "notes.txt").write_text("notes\n", encoding="utf-8")
        self.commit(root, "notes", "notes.txt")
        self.assert_all_noted(root)
        self.add_rights_row(root, "tests/b.txt", "b\n", fx.F1)
        self.commit(root, "new row", "tests/b.txt", playable.RIGHTS_INVENTORY.as_posix())
        rights_errors, rights_notes, review_errors, review_notes = self.both(root)
        self.assertEqual(len(rights_errors), 1, rights_errors)
        self.assertIn("tests/b.txt", rights_errors[0])
        self.assertTrue(rights_errors[0].endswith("does not resolve"), rights_errors[0])
        self.assertEqual(len(rights_notes), 1, rights_notes)
        self.assertIn("tests/a.txt", rights_notes[0])
        self.assertEqual((review_errors, len(review_notes)), ([], 3))

    def test_g5wr_01_one_commit_shape_changes_nothing(self) -> None:
        self.assertFalse(hasattr(playable, "phase_history_complete"))
        temporary = tempfile.TemporaryDirectory(prefix="playable-oneshot-")
        self.addCleanup(temporary.cleanup)
        repo = Path(temporary.name) / "repo"
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        (repo / "tests").mkdir()
        (repo / "tests/a.txt").write_text("one\n", encoding="utf-8")
        x1 = self.commit(repo, "x1", "tests/a.txt")
        self.write_review(repo, x1)
        gaps = playable.PHASE_DIRECTORY / "04-REVIEW-GAPS.md"
        (repo / gaps).write_text("gaps\n", encoding="utf-8")
        self.commit(repo, "x2 review and gaps together", playable.REVIEW.as_posix(), gaps.as_posix())
        (repo / "tests/a.txt").write_text("two\n", encoding="utf-8")
        x3 = self.commit(repo, "x3", "tests/a.txt")
        self.write_inventory(repo, [self.item("tests/a.txt", "two\n", x3)])
        self.write_disposition(repo, [("CR-01", "critical", "fixed", f"revision `{x3}`"),
                                      ("GWR-01", "warning", "fixed", f"revision `{x3}`")])
        self.allowlist(repo, [("reviewed_revision", "04-REVIEW.md", x1), ("review_citation", "CR-01", x3),
                              ("review_citation", "GWR-01", x3), ("rights", "tests/a.txt", x3)], x1)
        self.commit(repo, "x4", playable.RIGHTS_INVENTORY.as_posix(), playable.DISPOSITION.as_posix(),
                    "docs/history-allowlist.json")
        self.assertEqual(self.both(repo), ([], [], [], []))
        self.assertEqual(self.stale(repo), [])
        self.check_fabricated(repo, tolerated=False)

    def test_g5wr_01_form_checks_precede_git(self) -> None:
        fx = self.fixture()
        root = fx.clone
        bad = "a" * 39
        self.write_inventory(root, [self.item("tests/a.txt", "two\n", bad)])
        real = subprocess.run
        with mock.patch("subprocess.run", wraps=real) as run:
            errors, _notes = self.gate("rights_revision_errors", root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("not 40 hex", errors[0])
        for call in run.call_args_list:
            self.assertFalse([part for part in call.args[0] if bad in str(part)], call)
        self.write_disposition(root, [("WR-90", "warning", "fixed", "no cited revision"),
                                      ("XX-01", "warning", "fixed", f"revision `{'f' * 40}`")])
        errors, _notes = self.gate("review_provenance_errors", root)
        self.assertEqual(errors, ["review finding WR-90 disposition cites no review revision",
                                  "review finding XX-01 has no known review round"])

    def test_g5wr_01_frontend_receipt_row(self) -> None:
        fx = self.fixture()
        load = getattr(playable, "load_frontend_evidence")
        summary = self.frontend_summary()
        summary["source_revision"] = fx.F2
        temporary = tempfile.TemporaryDirectory(prefix="playable-receipt-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)

        def write(value: dict[str, object]) -> None:
            (root / playable.FRONTEND_EVIDENCE).parent.mkdir(parents=True, exist_ok=True)
            (root / playable.FRONTEND_EVIDENCE).write_text(json.dumps(value, indent=2), encoding="utf-8")

        write(summary)
        self.allowlist(root, [("frontend_receipt", "source_revision", fx.F2)], fx.B)
        notes: list[str] = []
        try:
            loaded = load(root, repository=fx.clone, head="HEAD", unverifiable=notes)
        except Exception as error:  # noqa: BLE001
            self.fail(f"uncaught {type(error).__name__}")
        self.assertEqual(loaded, summary)
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("frontend evidence", notes[0])
        self.assertIn(self.NOTE, notes[0])
        # An edited receipt voids its pin and takes today's strict path.
        write({**summary, "inventory_sha256": "0" * 64})
        notes = []
        with self.assertRaisesRegex(RuntimeError, "^frontend evidence revision cannot be checked$"):
            load(root, repository=fx.clone, head="HEAD", unverifiable=notes)
        self.assertEqual(notes, [])
        # Unrelated-but-resolving revision, not listed after the edit: today's not-an-ancestor message.
        with self.assertRaisesRegex(RuntimeError, "^frontend evidence revision is not a committed ancestor of the checked head$"):
            load(root, repository=fx.repo, head="HEAD", unverifiable=notes)
        # No allowlist at all: strict.
        write(summary)
        (root / "docs/history-allowlist.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "^frontend evidence revision cannot be checked$"):
            load(root, repository=fx.clone, head="HEAD", unverifiable=notes)
        # An ancestor revision is never tolerated: it takes the snapshot-binding path and today's error.
        self.allowlist(root, [("frontend_receipt", "source_revision", fx.F2)], fx.B)
        self.git(fx.repo, "checkout", "-q", "feature")
        with self.assertRaises(RuntimeError) as caught:
            load(root, repository=fx.repo, head="HEAD", unverifiable=notes)
        self.assertNotIn("allowlisted", str(caught.exception))
        self.assertEqual(notes, [])

    def test_g5wr_01_malformed_allowlist(self) -> None:
        load = getattr(playable, "load_history_allowlist", None)
        self.assertIsNotNone(load, "load_history_allowlist is missing")
        good = {"kind": "rights", "key": "tests/a.txt", "revision": "a" * 40, "pin": "b" * 64}
        base = {"schema": 1, "scope": "first-playable-game milestone branch pre-ship records", "base_revision": "c" * 40}
        for label, document in (("rows not a list", {**base, "rows": 3}),
                                ("row without pin", {**base, "rows": [{k: v for k, v in good.items() if k != "pin"}]}),
                                ("wrong schema", {**base, "schema": 2, "rows": [good]}),
                                ("unknown kind", {**base, "rows": [{**good, "kind": "other"}]})):
            with self.subTest(label), tempfile.TemporaryDirectory(prefix="playable-malformed-") as temporary:
                root = Path(temporary)
                (root / "docs").mkdir()
                (root / "docs/history-allowlist.json").write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "^history allowlist is malformed$"):
                    load(root)

    # ---- allowlist generator and freshness check (G5WR-01, 04-60) ----

    GENERATOR_REFUSAL = "^history allowlist cannot be generated: "

    def generate(self, root: Path, base: str = "main", head: str = "HEAD") -> str:
        function = getattr(playable, "history_allowlist_document", None)
        self.assertIsNotNone(function, "history_allowlist_document is missing")
        return function(root, root, head, base)

    def current(self, root: Path, base: str = "main") -> bool:
        function = getattr(playable, "history_allowlist_is_current", None)
        self.assertIsNotNone(function, "history_allowlist_is_current is missing")
        return function(root, root, "HEAD", base)

    def on_feature(self, base_row: bool = False) -> "SimpleNamespace":
        fx = self.fixture(base_row)
        self.git(fx.repo, "checkout", "-q", "feature")
        return fx

    @staticmethod
    def sorted_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        return sorted(rows, key=lambda row: (row["kind"], row["key"], row["revision"]))

    def test_g5wr_01_generator_reproduces_fixture_allowlist(self) -> None:
        fx = self.on_feature()
        text = self.generate(fx.repo)
        document = json.loads(text)
        expected = json.loads((fx.repo / "docs/history-allowlist.json").read_text(encoding="utf-8"))
        self.assertEqual(document["schema"], expected["schema"])
        self.assertEqual(document["scope"], expected["scope"])
        self.assertEqual(document["base_revision"], fx.B)
        self.assertEqual(document["rows"], self.sorted_rows(expected["rows"]))
        self.assertEqual(len(document["rows"]), 4)
        self.assertEqual(self.generate(fx.repo), text)
        self.assertTrue(text.endswith("}\n") and not text.endswith("\n\n"), repr(text[-4:]))

    def test_g5wr_01_generator_excludes_rows_reachable_from_base(self) -> None:
        fx = self.on_feature(base_row=True)
        document = json.loads(self.generate(fx.repo))
        self.assertEqual(document["base_revision"], fx.B)
        self.assertEqual(sorted((row["kind"], row["key"]) for row in document["rows"]),
                         [("review_citation", "CR-01"), ("review_citation", "GWR-01"),
                          ("reviewed_revision", "04-REVIEW.md"), ("rights", "tests/a.txt")])
        everything = json.loads(self.generate(fx.repo, base=fx.F2))
        self.assertEqual(everything["base_revision"], fx.F2)
        self.assertEqual(everything["rows"], [])

    def test_g5wr_01_generator_refuses_on_squashed_history(self) -> None:
        fx = self.fixture()
        with self.assertRaisesRegex(RuntimeError, self.GENERATOR_REFUSAL):
            self.generate(fx.clone)

    def test_g5wr_01_generator_refuses_fabricated_row(self) -> None:
        fx = self.on_feature()
        self.add_rights_row(fx.repo, "tests/b.txt", "b\n", "f" * 40)
        with self.assertRaisesRegex(RuntimeError, self.GENERATOR_REFUSAL):
            self.generate(fx.repo)

    def test_g5wr_01_generator_refuses_bad_base(self) -> None:
        fx = self.on_feature()
        real = subprocess.run
        with mock.patch("subprocess.run", wraps=real) as run:
            with self.assertRaisesRegex(RuntimeError, self.GENERATOR_REFUSAL):
                self.generate(fx.repo, base="-x")
        for call in run.call_args_list:
            self.assertNotIn("-x", [str(part) for part in call.args[0]], call)
        with self.assertRaisesRegex(RuntimeError, self.GENERATOR_REFUSAL):
            self.generate(fx.repo, base="nosuchref")

    def test_sanitized_checkout_generates_strict_rights_only_allowlist(self) -> None:
        """A public checkout without private planning history can still bind rights rows for squash."""
        with tempfile.TemporaryDirectory(prefix="playable-sanitized-allowlist-") as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            self.git(repo, "init", "-q", "-b", "main")
            (repo / "src").mkdir()
            (repo / "src/source.c").write_text("one\n", encoding="utf-8")
            base = self.commit(repo, "public base", "src/source.c")
            public_plan = repo / ".planning/public-context.md"
            public_plan.parent.mkdir()
            public_plan.write_text("Public source-plan metadata.\n", encoding="utf-8")
            self.commit(repo, "public planning context", ".planning/public-context.md")

            self.write_inventory(repo, [self.item("src/source.c", "one\n", base)])
            self.commit(repo, "rights inventory", playable.RIGHTS_INVENTORY.as_posix())
            (repo / "src/source.c").write_text("two\n", encoding="utf-8")
            source_commit = self.commit(repo, "source change", "src/source.c")
            self.write_inventory(repo, [self.item("src/source.c", "two\n", source_commit)])
            self.commit(repo, "updated rights inventory", playable.RIGHTS_INVENTORY.as_posix())

            self.assertTrue(public_plan.is_file())
            document = json.loads(self.generate(repo, base=base))
            self.assertEqual(document["base_revision"], base)
            self.assertEqual(document["rows"], [{
                "kind": "rights", "key": "src/source.c", "revision": source_commit,
                "pin": self.canonical(self.item("src/source.c", "two\n", source_commit)),
            }])

            allowlist_path = repo / playable.HISTORY_ALLOWLIST
            allowlist_path.write_text(self.generate(repo, base=base), encoding="utf-8")
            self.commit(repo, "generated sanitized allowlist", playable.HISTORY_ALLOWLIST.as_posix())
            status, out, err = self.run_cli(repo, "--history-allowlist", "ci", "--base", base)
            self.assertEqual(status, 0, err)
            self.assertIn("History allowlist is current", out)

            # An unrelated public .planning document does not select the private evidence path, but
            # one present review record does and an incomplete set fails closed.
            self.write_review(repo, base)
            with self.assertRaisesRegex(RuntimeError, self.GENERATOR_REFUSAL):
                self.generate(repo, base=base)
            (repo / playable.REVIEW).unlink()

            # Rights-only generation remains strict: changed recorded bytes cannot be pinned.
            inventory = repo / playable.RIGHTS_INVENTORY
            text = inventory.read_text(encoding="utf-8")
            inventory.write_text(text.replace(self.sha("two\n"), "0" * 64), encoding="utf-8")
            self.commit(repo, "tampered rights digest", playable.RIGHTS_INVENTORY.as_posix())
            with self.assertRaisesRegex(RuntimeError, self.GENERATOR_REFUSAL + ".*does not hold"):
                self.generate(repo, base=base)

    def test_g5wr_01_generator_skips_open_and_third_party_rows(self) -> None:
        fx = self.on_feature()
        self.append_disposition(fx.repo, "| CR-03 | info | open | recorded |")
        third_party = self.item("third_party/x", "x\n", "upstream-pin")
        self.write_inventory(fx.repo, [*self.items(fx.repo), third_party])
        document = json.loads(self.generate(fx.repo))
        keys = [row["key"] for row in document["rows"]]
        self.assertEqual(len(keys), 4, keys)
        self.assertNotIn("CR-03", keys)
        self.assertNotIn("third_party/x", keys)

    def test_g5wr_01_check_detects_stale(self) -> None:
        fx = self.on_feature()
        (fx.repo / "docs/history-allowlist.json").write_text(self.generate(fx.repo), encoding="utf-8")
        self.assertTrue(self.current(fx.repo))
        self.append_disposition(fx.repo, "| CR-03 | info | open | recorded |")
        self.assertTrue(self.current(fx.repo))
        text = (fx.repo / playable.DISPOSITION).read_text(encoding="utf-8")
        (fx.repo / playable.DISPOSITION).write_text(
            text.replace(f"revision `{fx.F2}` |\n| GWR-01", f"revision `{fx.F2}` x |\n| GWR-01"), encoding="utf-8")
        self.assertFalse(self.current(fx.repo))
        self.assertEqual(self.stale(fx.repo), ["review_citation CR-01"])
        (fx.repo / "docs/history-allowlist.json").unlink()
        self.assertFalse(self.current(fx.repo))

    def test_g5wr_01_cli_allowlist_check_and_write(self) -> None:
        fx = self.on_feature()

        def run(*arguments: str) -> tuple[int, str, str]:
            with mock.patch.object(playable, "ROOT", fx.repo), \
                    mock.patch.object(sys, "argv", ["verify_playable.py", *arguments]), \
                    mock.patch("sys.stdout", new_callable=io.StringIO) as stdout, \
                    mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
                status = playable.main()
            return status, stdout.getvalue(), stderr.getvalue()

        status, out, _err = run("--history-allowlist", "write", "--base", "main")
        self.assertEqual((status, out), (0, "Wrote docs/history-allowlist.json (4 rows).\n"))
        status, out, _err = run("--history-allowlist", "check", "--base", "main")
        self.assertEqual((status, out), (0, "History allowlist is current (4 rows).\n"))
        text = (fx.repo / playable.DISPOSITION).read_text(encoding="utf-8")
        (fx.repo / playable.DISPOSITION).write_text(
            text.replace(f"| CR-01 | critical | fixed | revision `{fx.F2}` |",
                         f"| CR-01 | critical | fixed | revision `{fx.F2}` x |"), encoding="utf-8")
        status, out, err = run("--history-allowlist", "check", "--base", "main")
        self.assertEqual((status, out), (1, ""))
        self.assertIn("history allowlist is stale or missing", err)
        self.assertIn("review_citation CR-01", err)
        for arguments in (("--base", "main"), ("--history-allowlist", "check", "--check-docs"),
                          ("--history-allowlist", "write", "--clean")):
            with self.assertRaises(SystemExit) as caught:
                run(*arguments)
            self.assertEqual(caught.exception.code, 2, arguments)

    def test_g7cr_01_generator_refuses_rights_row_stale_at_head(self) -> None:
        """A rights row that verifies at its source_revision but not at the head would fail after the squash."""
        fx = self.on_feature()
        (fx.repo / "docs/history-allowlist.json").write_text(self.generate(fx.repo, base="main"), encoding="utf-8")
        self.commit(fx.repo, "allowlist", "docs/history-allowlist.json")
        self.assertTrue(self.current(fx.repo))
        (fx.repo / "tests/a.txt").write_text("three\n", encoding="utf-8")
        self.commit(fx.repo, "edit without refreshing the rights row", "tests/a.txt")
        errors, _notes = self.gate("rights_revision_errors", fx.repo)
        self.assertEqual(errors, [], "the strict branch alone does not catch this")
        with self.assertRaisesRegex(RuntimeError, self.GENERATOR_REFUSAL + "rights row tests/a.txt would fail "
                                    "after the squash"):
            self.generate(fx.repo, base="main")
        with self.assertRaisesRegex(RuntimeError, self.GENERATOR_REFUSAL):
            self.current(fx.repo)

    def run_cli(self, root: Path, *arguments: str) -> tuple[int, str, str]:
        with mock.patch.object(playable, "ROOT", root), \
                mock.patch.object(sys, "argv", ["verify_playable.py", *arguments]), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout, \
                mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            status = playable.main()
        return status, stdout.getvalue(), stderr.getvalue()

    def test_g7wr_02_ci_mode_checks_every_pre_ship_pull_request(self) -> None:
        """On the pre-ship branch the check applies even when the allowlist file is unchanged."""
        fx = self.on_feature()
        (fx.repo / "docs/history-allowlist.json").write_text(self.generate(fx.repo, base="main"), encoding="utf-8")
        self.commit(fx.repo, "allowlist", "docs/history-allowlist.json")
        # A base holding the identical allowlist file: the check still applies through the listed rows.
        reason = playable.history_allowlist_check_applies(fx.repo, fx.repo, "HEAD", "HEAD")
        self.assertIsNotNone(reason)
        self.assertIn("listed revision", reason)
        status, out, _err = self.run_cli(fx.repo, "--history-allowlist", "ci", "--base", fx.B)
        self.assertEqual(status, 0, out)
        self.assertIn("History allowlist check applies", out)
        self.assertIn("History allowlist is current", out)
        # A later pull request edits a pinned disposition row but not the allowlist: it must fail.
        text = (fx.repo / playable.DISPOSITION).read_text(encoding="utf-8")
        (fx.repo / playable.DISPOSITION).write_text(
            text.replace(f"| CR-01 | critical | fixed | revision `{fx.F2}` |",
                         f"| CR-01 | critical | fixed | revision `{fx.F2}` x |"), encoding="utf-8")
        self.commit(fx.repo, "edit a pinned row", playable.DISPOSITION.as_posix())
        status, _out, err = self.run_cli(fx.repo, "--history-allowlist", "ci", "--base", fx.B)
        self.assertEqual(status, 1)
        self.assertIn("review_citation CR-01", err)

    def test_g7wr_02_ci_mode_after_the_squash(self) -> None:
        """After the squash an unchanged allowlist does not apply; editing it applies and fails."""
        fx = self.fixture()
        root = fx.clone
        self.git(root, "checkout", "-q", "-b", "later")
        (root / "notes.txt").write_text("notes\n", encoding="utf-8")
        self.commit(root, "notes", "notes.txt")
        status, out, _err = self.run_cli(root, "--history-allowlist", "ci", "--base", "main")
        self.assertEqual(status, 0, out)
        self.assertIn("does not apply", out)
        path = root / "docs/history-allowlist.json"
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        self.commit(root, "edit allowlist", "docs/history-allowlist.json")
        status, out, _err = self.run_cli(root, "--history-allowlist", "ci", "--base", "main")
        self.assertEqual(status, 1)
        self.assertIn("differs from main", out)
        with self.assertRaises(SystemExit) as caught:
            self.run_cli(root, "--history-allowlist", "ci")
        self.assertEqual(caught.exception.code, 2)

    def test_g7in_01_check_docs_reports_unanchored_allowlist_first(self) -> None:
        """An unresolvable base_revision (as in a shallow clone) is reported before any other docs check."""
        fx = self.fixture()
        self.allowlist(fx.repo, self.all_rows(fx), "e" * 40)
        with self.assertRaisesRegex(RuntimeError, "^history allowlist base_revision is not a commit"):
            playable.check_docs(fx.repo)

    def test_g7cr_02_default_base_is_the_upstream_main_ref(self) -> None:
        """Without --base the generator uses origin/main, never a stale local main, and refuses when it is absent."""
        fx = self.on_feature(base_row=True)
        self.assertEqual(playable.HISTORY_DEFAULT_BASE, "origin/main")
        function = playable.history_allowlist_document
        with self.assertRaisesRegex(RuntimeError, self.GENERATOR_REFUSAL + "base origin/main does not resolve"):
            function(fx.repo, fx.repo, "HEAD")
        # The upstream main has moved past the stale local main: F2 is already upstream.
        self.git(fx.repo, "update-ref", "refs/remotes/origin/main", fx.F2)
        upstream = json.loads(function(fx.repo, fx.repo, "HEAD"))
        self.assertEqual(upstream["base_revision"], fx.F2)
        self.assertEqual(upstream["rows"], [])
        stale_local = json.loads(self.generate(fx.repo, base="main"))
        self.assertEqual(stale_local["base_revision"], fx.B)
        self.assertEqual(len(stale_local["rows"]), 4)

    def test_g5wr_01_one_note_per_listed_revision_form(self) -> None:
        """A finding citing one commit in two recognized forms lists two rows and prints two lines (04-60 SIM-CHECK)."""
        fx = self.fixture()
        root = fx.clone
        short = fx.F2[:12]
        text = (root / playable.DISPOSITION).read_text(encoding="utf-8")
        (root / playable.DISPOSITION).write_text(
            text.replace(f"| CR-01 | critical | fixed | revision `{fx.F2}` |",
                         f"| CR-01 | critical | fixed | revision `{fx.F2}` and review (04-59, {short}) |"), encoding="utf-8")
        self.allowlist(root, [("reviewed_revision", "04-REVIEW.md", fx.F1), ("review_citation", "CR-01", fx.F2),
                              ("review_citation", "CR-01", short), ("review_citation", "GWR-01", fx.F2),
                              ("rights", "tests/a.txt", fx.F2)], fx.B)
        errors, notes = self.gate("review_provenance_errors", root)
        self.assertEqual(errors, [])
        self.assertEqual(len([note for note in notes if "CR-01" in note]), 2, notes)
        self.assertEqual(len(notes), 4, notes)

    def test_g6wr_02_duplicate_rows_are_malformed(self) -> None:
        fx = self.fixture()
        path = fx.repo / "docs/history-allowlist.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        duplicate = {**document["rows"][0], "pin": "0" * 64}
        path.write_text(json.dumps({**document, "rows": [*document["rows"], duplicate]}), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "^history allowlist is malformed$"):
            playable.load_history_allowlist(fx.repo)

    # ---- G6WR: the allowlist is verified against history, duplicates and symlinks fail closed ----

    ALL_ROWS_KEYS = (("reviewed_revision", "04-REVIEW.md"), ("review_citation", "CR-01"),
                     ("review_citation", "GWR-01"), ("rights", "tests/a.txt"))

    def all_rows(self, fx: "SimpleNamespace") -> list[tuple[str, str, str]]:
        revisions = {"reviewed_revision": fx.F1}
        return [(kind, key, revisions.get(kind, fx.F2)) for kind, key in self.ALL_ROWS_KEYS]

    def test_g6wr_01_forged_base_revision_voids_tolerance(self) -> None:
        """A base_revision that is not a commit of this repository or not an ancestor of the head tolerates nothing."""
        fx = self.fixture()
        for label, base in (("unresolvable", "e" * 40), ("not an ancestor of head", fx.F4)):
            with self.subTest(label):
                self.allowlist(fx.repo, self.all_rows(fx), base)
                rights_errors, rights_notes, review_errors, review_notes = self.both(fx.repo)
                self.assertEqual((rights_notes, review_notes), ([], []))
                self.assertTrue(rights_errors and review_errors, (rights_errors, review_errors))
                reported = playable.history_allowlist_anchor_errors(
                    playable.load_history_allowlist(fx.repo), fx.repo, "HEAD")
                self.assertTrue(reported and "base_revision" in reported[0], reported)
        self.allowlist(fx.repo, self.all_rows(fx), fx.B)
        errors, notes = self.gate("rights_revision_errors", fx.repo)
        self.assertEqual((errors, len(notes)), ([], 1))

    def test_g6wr_01_row_reachable_from_base_is_rejected(self) -> None:
        """A row whose revision resolves inside the base's history is outside the documented scope."""
        fx = self.on_feature()
        self.allowlist(fx.repo, self.all_rows(fx), fx.F2)
        allowlist = playable.load_history_allowlist(fx.repo)
        errors = playable.history_allowlist_anchor_errors(allowlist, fx.repo, "HEAD")
        self.assertTrue(any("reachable from base_revision" in error and fx.F1[:12] in error for error in errors), errors)
        kept = playable.anchored_history_allowlist(allowlist, fx.repo, "HEAD")
        self.assertNotIn(("reviewed_revision", "04-REVIEW.md", fx.F1), kept.rows)
        self.allowlist(fx.repo, self.all_rows(fx), fx.B)
        self.assertEqual(playable.history_allowlist_anchor_errors(
            playable.load_history_allowlist(fx.repo), fx.repo, "HEAD"), [])

    def test_batched_reachability_equals_per_row_merge_base(self) -> None:
        """The one-pass reachability check agrees with `merge-base --is-ancestor` per row, including bad revisions."""
        fx = self.on_feature()
        rows = {triple: "pin" for triple in self.all_rows(fx)}
        for odd in ("e" * 40, fx.F1[:7], "not-a-revision"):
            rows[("reviewed_revision", "odd-" + odd, odd)] = "pin"
        for base in (fx.B, fx.F2):
            allowlist = playable.HistoryAllowlist(rows=rows, base_revision=base)
            expected = set()
            for triple in rows:
                full = subprocess.run(["git", "-C", str(fx.repo), "rev-parse", "--verify", "--quiet",
                                       triple[2] + "^{commit}"], capture_output=True, text=True).stdout.strip()
                if full and subprocess.run(["git", "-C", str(fx.repo), "merge-base", "--is-ancestor", full, base],
                                           capture_output=True).returncode == 0:
                    expected.add(triple)
            with self.subTest(base=base[:12]):
                self.assertEqual(playable._rows_reachable_from(allowlist, fx.repo, base), expected)

    def test_g6wr_03_symlinked_rights_file_is_not_hashed(self) -> None:
        fx = self.fixture()
        outside = fx.repo.parent / "outside.txt"
        outside.write_text("two\n", encoding="utf-8")
        target = fx.repo / "tests/a.txt"
        target.unlink()
        target.symlink_to(outside)
        self.commit(fx.repo, "symlink", "tests/a.txt")
        errors, notes = self.gate("rights_revision_errors", fx.repo)
        self.assertEqual(notes, [])
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("file at the checked head is missing", errors[0])

    def test_g6wr_03_symlinked_directory_and_unnormalized_paths_are_rejected(self) -> None:
        fx = self.fixture()
        real = fx.repo / "tests"
        moved = fx.repo.parent / "elsewhere"
        real.rename(moved)
        real.symlink_to(moved)
        self.git(fx.repo, "add", "-A", "--", "tests")
        self.git(fx.repo, "commit", "-q", "-m", "symlinked directory")
        errors, notes = self.gate("rights_revision_errors", fx.repo)
        self.assertEqual(notes, [])
        self.assertEqual(len(errors), 1, errors)
        for path in ("tests/./a.txt", "tests//a.txt", "tests/a.txt/", "tests\\a.txt"):
            with self.subTest(path):
                self.assertFalse(playable._rights_path_is_relative_posix(path))
        self.assertTrue(playable._rights_path_is_relative_posix("tests/a.txt"))

    # ---- G7WR-03: the tolerated rights branch judges the committed bytes at the checked head ----

    def test_g7wr_03_tolerated_rights_row_ignores_working_tree_bytes(self) -> None:
        """Dirty, deleted or untracked working-tree content cannot change a tolerated row's outcome."""
        fx = self.fixture()
        target = fx.clone / "tests/a.txt"
        target.write_text("dirty, uncommitted\n", encoding="utf-8")
        errors, notes = self.gate("rights_revision_errors", fx.clone)
        self.assertEqual((errors, len(notes)), ([], 1))
        self.assertIn("digest at the checked head matches", notes[0])
        target.unlink()
        errors, notes = self.gate("rights_revision_errors", fx.clone)
        self.assertEqual((errors, len(notes)), ([], 1))
        # An untracked file holding the recorded bytes does not stand in for a missing tracked file.
        self.add_rights_row(fx.clone, "tests/untracked.txt", "u\n", fx.F2)
        self.allowlist(fx.clone, [*self.all_rows(fx), ("rights", "tests/untracked.txt", fx.F2)], fx.B)
        errors, _notes = self.gate("rights_revision_errors", fx.clone)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("tests/untracked.txt", errors[0])
        self.assertIn("file at the checked head is missing", errors[0])


if __name__ == "__main__":
    unittest.main()
