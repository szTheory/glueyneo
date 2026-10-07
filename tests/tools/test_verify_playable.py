#!/usr/bin/env python3
"""Fail-closed snapshot tests for the playable qualification runner."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

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
        (self.repository / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(snapshot_fixture C)\n"
            "add_executable(fixture_writer writer.c public_guest.c)\n",
            encoding="utf-8",
        )
        (self.repository / "writer.c").write_text(
            "#include <stddef.h>\n"
            "int public_guest_write(const char *);\n"
            "int main(int argc, char **argv) { return argc == 2 && public_guest_write(argv[1]) ? 0 : 1; }\n",
            encoding="utf-8",
        )
        shutil.copyfile(ROOT / "tests/fixture/public_guest.c", self.repository / "public_guest.c")
        subprocess.run(["git", "-C", str(self.repository), "add", "CMakeLists.txt", "writer.c", "public_guest.c"], check=True)
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

    def test_dirty_and_untracked_checkout_inputs_do_not_change_snapshot_build(self) -> None:
        commit = self.commit_fixture_project()
        (self.repository / "public_guest.c").write_text("#error checkout injection\n", encoding="utf-8")
        (self.repository / "injected.c").write_text("#error untracked injection\n", encoding="utf-8")
        snapshot = playable.create_snapshot(self.repository, commit, self.base / "snapshot")
        rows, digest = playable.verify_snapshot(snapshot)
        self.assertEqual(snapshot.commit, commit)
        self.assertEqual(snapshot.digest, digest)
        self.assertEqual([row["path"] for row in rows], ["CMakeLists.txt", "public_guest.c", "writer.c"])
        self.assertNotIn("injected.c", {row["path"] for row in rows})

        build = self.base / "build"
        subprocess.run(["cmake", "-S", str(snapshot.root), "-B", str(build), "-G", "Ninja"], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        subprocess.run(["cmake", "--build", str(build), "--parallel", "2"], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        fixture = self.base / "public-playable.bin"
        subprocess.run([str(build / "fixture_writer"), str(fixture)], check=True)
        self.assertEqual(fixture.stat().st_size, 602)
        self.assertEqual(playable.sha256(fixture), "59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0")

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


if __name__ == "__main__":
    unittest.main()
