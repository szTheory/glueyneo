#!/usr/bin/env python3
"""Fail-closed public content and rights inventory controls."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import public_content as content  # noqa: E402
import release_manifest as release  # noqa: E402


class PublicContentTests(unittest.TestCase):
    def test_source_scan_tracks_release_archive_policy(self) -> None:
        self.assertEqual(tuple(content.SOURCE_PATHS), release.SOURCE_PATHS)
        self.assertIn(".github/workflows", content.REPOSITORY_PATHS)
        self.assertIn("release-please-config.json", content.REPOSITORY_PATHS)
        self.assertNotIn(".github/workflows", content.SOURCE_PATHS)

    def test_deleted_reachable_blob_is_scanned_without_exposing_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("public\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            env = {**os.environ, "GIT_AUTHOR_NAME": "Public User",
                   "GIT_AUTHOR_EMAIL": "public@example.org", "GIT_COMMITTER_NAME": "Public User",
                   "GIT_COMMITTER_EMAIL": "public@example.org"}
            marker = "ghp_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            (root / "deleted.bin").write_text(marker, encoding="ascii")
            subprocess.run(["git", "add", "README.md", "deleted.bin"], cwd=root, env=env, check=True)
            subprocess.run(["git", "commit", "-qm", "add synthetic canary"], cwd=root, env=env, check=True)
            (root / "deleted.bin").unlink()
            subprocess.run(["git", "add", "-u"], cwd=root, env=env, check=True)
            subprocess.run(["git", "commit", "-qm", "remove synthetic canary"], cwd=root, env=env, check=True)
            result = content.scan_inputs(root=root, paths=["README.md"])
        self.assertEqual(result["outcome"], "fail")
        self.assertTrue(any("credential" in finding["rules"] and finding["location"].startswith("history/")
                            for finding in result["findings"]))
        self.assertNotIn(marker, json.dumps(result))

    def test_exact_history_dispositions_remain_visible_and_provenance_bound(self) -> None:
        _, dispositions, _, _ = content._git_history(ROOT)
        expected = set(content.HISTORY_FINDING_DISPOSITIONS)
        observed = {row["object"] for row in dispositions if "reason" in row}
        self.assertEqual(observed, expected)
        for row in dispositions:
            if "reason" in row:
                self.assertTrue(row["location"].startswith("history/"))
                self.assertTrue(row["rules"])
                self.assertTrue(row["reason"])

    def test_uncatalogued_binary_test_asset_fails_tree_and_archive_rights_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            (root / "tests/cpu").mkdir(parents=True)
            (root / "tests/cpu/title.bin").write_bytes(b"synthetic")
            (root / "docs/rights-inventory.md").write_text(
                "```json\n{\"schema\":1,\"items\":[]}\n```\n", encoding="utf-8")
            with mock.patch.object(content, "_git_source_paths", return_value=["tests/cpu/title.bin"]):
                with self.assertRaises(content.ContentError) as caught:
                    content.validate_repository_inventory(root)
            self.assertEqual(caught.exception.reason, "rights-path-set")
            archive = root / "source.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                item = tarfile.TarInfo("tests/cpu/title.bin")
                item.size = len(b"synthetic")
                stream.addfile(item, io.BytesIO(b"synthetic"))
            with self.assertRaises(content.ContentError) as caught:
                content.scan_archive(archive)
            self.assertEqual(caught.exception.reason, "rights-path-set")

    def test_secret_canaries_are_redacted_and_rule_labeled(self) -> None:
        personal_path = "/".join(("Users", "alice", "private.txt"))
        identity = "alice" + "@" + "private-domain" + ".example"
        machine = "machine" + "_id=" + "HOST-SECRET"
        credential = "ghp_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        private_url = "https://user" + ":pass" + "word" + "@private-host.invalid/repo"
        data = ("/" + personal_path + " " + identity + " " + machine +
                " token=" + credential + " " + private_url + "\n").encode()
        result = content.scan_bytes(data, "tests/canary.txt")
        rendered = json.dumps(result, sort_keys=True)
        for rule in ("personal-path", "machine-identifier", "credential", "private-url"):
            self.assertIn(rule, rendered)
        expected_path = "/".join(("Users", "alice"))
        expected_url_identity = "user:pass" + "word" + "@private-host.invalid"
        for secret in (identity, "HOST-SECRET", credential, "/" + expected_path, expected_url_identity):
            self.assertNotIn(secret, rendered)

    def test_archive_rejects_escape_links_duplicates_and_limits(self) -> None:
        for name, kind, reason in (("../escape", tarfile.REGTYPE, "archive-path"),
                                   ("link", tarfile.SYMTYPE, "archive-link"),
                                   ("duplicate", tarfile.REGTYPE, "archive-duplicate")):
            archive = Path(tempfile.mkstemp(suffix=".tar.gz")[1])
            try:
                with tarfile.open(archive, "w:gz") as stream:
                    first = tarfile.TarInfo(name)
                    first.type = kind
                    if kind == tarfile.REGTYPE:
                        first.size = 1
                        stream.addfile(first, io.BytesIO(b"x"))
                    else:
                        first.linkname = "../outside"
                        stream.addfile(first)
                    if name == "duplicate":
                        second = tarfile.TarInfo(name)
                        second.size = 1
                        stream.addfile(second, io.BytesIO(b"y"))
                with self.assertRaises(content.ContentError) as caught:
                    content.scan_archive(archive)
                self.assertEqual(caught.exception.reason, reason)
            finally:
                archive.unlink(missing_ok=True)

    def test_archive_limits_fail_before_acceptance(self) -> None:
        archive = Path(tempfile.mkstemp(suffix=".tar.gz")[1])
        original_file_limit = content.MAX_FILE_BYTES
        original_count_limit = content.MAX_MEMBERS
        try:
            with tarfile.open(archive, "w:gz") as stream:
                item = tarfile.TarInfo("small.txt")
                item.size = 4
                stream.addfile(item, io.BytesIO(b"four"))
            content.MAX_FILE_BYTES = 3
            with self.assertRaises(content.ContentError) as caught:
                content.scan_archive(archive)
            self.assertEqual(caught.exception.reason, "archive-file-limit")
            content.MAX_FILE_BYTES = original_file_limit
            content.MAX_MEMBERS = 0
            with self.assertRaises(content.ContentError) as caught:
                content.scan_archive(archive)
            self.assertEqual(caught.exception.reason, "archive-count")
        finally:
            content.MAX_FILE_BYTES = original_file_limit
            content.MAX_MEMBERS = original_count_limit
            archive.unlink(missing_ok=True)

    def test_archive_rights_gate_rejects_uninventoried_fixture_and_missing_notice(self) -> None:
        inventory = content.load_rights_inventory(ROOT)
        full_without_notice = [(item["path"], (ROOT / item["path"]).read_bytes())
                               for item in inventory["items"]]
        cases = [([( "fixtures/private.bin", b"private")], "rights-path-set"),
                 (full_without_notice, "rights-notice")]
        for members, reason in cases:
            archive = Path(tempfile.mkstemp(suffix=".tar.gz")[1])
            try:
                with tarfile.open(archive, "w:gz") as stream:
                    for name, body in members:
                        item = tarfile.TarInfo(name)
                        item.size = len(body)
                        stream.addfile(item, io.BytesIO(body))
                with self.assertRaises(content.ContentError) as caught:
                    content.scan_archive(archive)
                self.assertEqual(caught.exception.reason, reason)
            finally:
                archive.unlink(missing_ok=True)

    def test_repository_inventory_matches_recorded_fixture_and_dependency_bytes(self) -> None:
        result = content.validate_repository_inventory(ROOT)
        self.assertTrue(result["passed"])
        self.assertGreater(result["items"], 0)

    def test_rights_inventory_binds_bytes_and_rejects_unknown_or_changed_item(self) -> None:
        inventory = {"schema": 1, "items": [{
            "path": "fixture.bin", "sha256": hashlib.sha256(b"fixture").hexdigest(),
            "kind": "fixture", "license": "MIT", "rights": "affirmative",
            "source_revision": "a" * 40, "provenance": "original project work", "notice": "LICENSE",
        }]}
        self.assertTrue(content.validate_inventory(inventory, {"fixture.bin": b"fixture"})["passed"])
        for actual in ({"unknown.bin": b"x"}, {"fixture.bin": b"changed"}):
            with self.assertRaises(content.ContentError):
                content.validate_inventory(inventory, actual)
        inventory["items"][0]["rights"] = "unknown"
        with self.assertRaises(content.ContentError):
            content.validate_inventory(inventory, {"fixture.bin": b"fixture"})

    def test_full_scan_reports_each_available_class_and_detector_limitation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("Public documentation\n", encoding="utf-8")
            (root / "ci.log").write_text("all checks passed\n", encoding="utf-8")
            with tarfile.open(root / "release.tar.gz", "w:gz") as stream:
                item = tarfile.TarInfo("README.md")
                body = b"Public documentation\n"
                item.size = len(body)
                stream.addfile(item, io.BytesIO(body))
            result = content.scan_inputs(root=root, paths=["README.md"],
                                         logs=[root / "ci.log"], archives=[root / "release.tar.gz"],
                                         history_text="commit Author: Public User <user@example.org>\n")
        self.assertTrue(result["detector_negative_only"])
        self.assertEqual(set(result["counts"]), {"source", "history", "logs", "archives"})
        self.assertTrue(all(row["files"] > 0 for row in result["counts"].values()))

    def test_unreadable_or_non_regular_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "link").symlink_to(root / "missing")
            with self.assertRaises(content.ContentError) as caught:
                content.scan_tree(root, ["link"])
            self.assertEqual(caught.exception.reason, "input-type")
            (root / "original").write_bytes(b"public")
            os.link(str(root / "original"), str(root / "hardlink"))
            with self.assertRaises(content.ContentError) as caught:
                content.scan_tree(root, ["hardlink"])
            self.assertEqual(caught.exception.reason, "input-type")


if __name__ == "__main__":
    unittest.main(verbosity=2)
