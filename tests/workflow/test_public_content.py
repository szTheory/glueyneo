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
    def test_current_source_dispositions_bind_path_bytes_and_rule(self) -> None:
        for (path, digest), disposition in content.SOURCE_FINDING_DISPOSITIONS.items():
            with self.subTest(path=path):
                data = (ROOT / path).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
                for location in (path, "glueyneo-source/" + path):
                    result = content.scan_bytes(data, location)
                    self.assertEqual(result["findings"], [])
                    self.assertEqual(set(result["dispositions"][0]["rules"]), disposition["rules"])
                self.assertTrue(content.scan_bytes(data + b"\n", path)["findings"])
                self.assertTrue(content.scan_bytes(data, "ci-log-1")["findings"])
                self.assertTrue(content.scan_bytes(data, "other/" + path)["findings"])
        license_data = (ROOT / "third_party/zlib/LICENSE").read_bytes()
        location = "glueyneo-sdk-9.8.7/static/share/licenses/Glueyneo/zlib/LICENSE"
        self.assertEqual(content.scan_bytes(license_data, location)["findings"], [])
        self.assertTrue(content.scan_bytes(license_data + b"\n", location)["findings"])

    def test_source_scan_tracks_release_archive_policy(self) -> None:
        self.assertEqual(tuple(content.SOURCE_PATHS), release.SOURCE_PATHS)
        self.assertIn(".github/workflows", content.REPOSITORY_PATHS)
        self.assertIn("release-please-config.json", content.REPOSITORY_PATHS)
        self.assertNotIn(".github/workflows", content.SOURCE_PATHS)

    def test_complete_current_inventory_matches_current_candidate_paths(self) -> None:
        paths = content._git_source_paths(ROOT)
        actual = {
            path for path in paths
            if content._is_rights_candidate(path)
        }
        inventory = content.load_rights_inventory(ROOT)
        declared = {item["path"] for item in inventory["items"]}
        self.assertEqual(declared, actual)
        self.assertEqual(content.validate_repository_inventory(ROOT)["items"], len(actual))

    def test_public_content_cli_accepts_all_history_as_option_value(self) -> None:
        with tempfile.TemporaryDirectory(prefix="public-content-cli-") as temp:
            root = Path(temp)
            (root / "README.md").write_text("synthetic clean input\n", encoding="utf-8")
            (root / "LICENSE").write_text("MIT License\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs/rights-inventory.md").write_text(
                "# Synthetic rights inventory\n\n```json\n{\"schema\":1,\"items\":[]}\n```\n",
                encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            env = {**os.environ, "GIT_AUTHOR_NAME": "Public User",
                   "GIT_AUTHOR_EMAIL": "public@example.org", "GIT_COMMITTER_NAME": "Public User",
                   "GIT_COMMITTER_EMAIL": "public@example.org"}
            subprocess.run(["git", "add", "README.md", "LICENSE", "docs/rights-inventory.md"],
                           cwd=root, env=env, check=True)
            subprocess.run(["git", "commit", "-qm", "synthetic input"], cwd=root, env=env, check=True)
            report = root / "report.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/public_content.py"), "--root", str(root),
                 "--history-revision=--all", "--json", str(report)], cwd=ROOT,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertTrue(report.is_file(), "CLI should parse --all and emit its structured scan report")
            parsed = json.loads(report.read_text(encoding="utf-8"))
            self.assertNotIn("usage:", result.stderr.lower())
            self.assertEqual(parsed.get("outcome"), "pass")
            self.assertEqual(parsed.get("coverage", {}).get("history_mode"), "all reachable refs")
            self.assertEqual(result.returncode, 0)
            selected = content.scan_inputs(root=root, paths=["README.md"], history_revision="HEAD")
            self.assertEqual(selected["coverage"]["history_mode"], "selected revision")
            self.assertEqual(selected["coverage"]["history_revision"], "HEAD")
            self.assertEqual(selected["coverage"]["history_scope"], "objects available in this checkout")

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
        # Exercise the exact available audited blobs, rather than scan unrelated
        # private refs or let repository growth consume the scanner's byte limit.
        # Public clones need not retain every historical object in this register.
        expected = set()
        stream = bytearray()

        def add_blob(path: str, data: bytes) -> None:
            stream.extend(
                b"commit refs/heads/fixture\n"
                b"committer Public User <public@example.invalid> 1 +0000\n"
                b"data 7\nfixture\n"
            )
            stream.extend(f"M 100644 inline {json.dumps(path)}\ndata {len(data)}\n".encode())
            stream.extend(data + b"\n\n")

        add_blob("README.md", b"synthetic bounded history\n")
        inspected = subprocess.run(
            ["git", "cat-file", "--batch-check"], cwd=ROOT, check=True,
            input="\n".join(content.HISTORY_FINDING_DISPOSITIONS) + "\n",
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout.splitlines()
        self.assertEqual(len(inspected), len(content.HISTORY_FINDING_DISPOSITIONS))
        for (object_id, disposition), row in zip(
                content.HISTORY_FINDING_DISPOSITIONS.items(), inspected):
            fields = row.split()
            self.assertEqual(fields[0], object_id)
            if fields[1:] == ["missing"]:
                continue  # an absent old blob is expected in fresh public clones
            self.assertEqual(fields[1], "blob")
            result = subprocess.run(
                ["git", "cat-file", "blob", object_id], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            )
            expected.add(object_id)
            add_blob(disposition["path"], result.stdout)

        with tempfile.TemporaryDirectory(prefix="public-content-dispositions-") as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "fast-import", "--quiet"], cwd=root,
                           input=bytes(stream), check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, dispositions, _, _ = content._git_history(root, "refs/heads/fixture")
        observed = {row["object"] for row in dispositions if "reason" in row}
        self.assertEqual(observed, expected)
        for row in dispositions:
            if "reason" in row:
                self.assertTrue(row["location"].startswith("history/"))
                self.assertTrue(row["rules"])
                self.assertTrue(row["reason"])

    def test_archived_history_disposition_retains_exact_blob_and_path_binding(self) -> None:
        with tempfile.TemporaryDirectory(prefix="public-content-archive-") as temp:
            root = Path(temp)
            original = ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-10-PLAN.md"
            archived = original.replace("workstreams/first-playable-game", "milestones/ws-first-playable-game-2026-10-24")
            target = root / original
            target.parent.mkdir(parents=True)
            target.write_text("/".join(("", "Us" + "ers", "placeholder", "sentinel.txt")), encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def commit(message: str) -> None:
                subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
                subprocess.run(["git", "-C", str(root), "-c", "user.name=Public User", "-c",
                                "user.email=public@example.invalid", "commit", "-qm", message], check=True)
            commit("original")
            oid = subprocess.check_output(["git", "-C", str(root), "hash-object", original], text=True).strip()
            (root / archived).parent.mkdir(parents=True)
            target.rename(root / archived)
            commit("archive")
            entry = {oid: {"path": original, "rules": {"personal-path"}, "reason": "synthetic audited object"}}
            with mock.patch.object(content, "HISTORY_FINDING_DISPOSITIONS", entry):
                _, rows, _, _ = content._git_history(root)
                self.assertTrue(any(row["object"] == oid and "reason" in row for row in rows))
                with mock.patch.dict(entry[oid], {"rules": {"private-identity"}}):
                    with self.assertRaisesRegex(content.ContentError, "no longer matches"):
                        content._git_history(root)
                # A changed blob remains a finding even at the admitted archive path.
                with (root / archived).open("a", encoding="utf-8") as stream:
                    stream.write(" changed")
                commit("changed blob")
                _, rows, _, _ = content._git_history(root)
                self.assertTrue(any("reason" not in row for row in rows))
                (root / archived).write_bytes(subprocess.check_output(["git", "-C", str(root), "cat-file", "blob", oid]))
                (root / archived).rename(root / "other.md")
                commit("unrelated path")
                with self.assertRaisesRegex(content.ContentError, "no longer matches"):
                    content._git_history(root)

    def test_tracked_plan_text_has_no_unaudited_privacy_finding(self) -> None:
        tracked = subprocess.run(
            ["git", "ls-files", "--", ".planning"], cwd=ROOT, check=True,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ).stdout.splitlines()
        findings: list[tuple[str, list[str]]] = []
        for path in tracked:
            if not path.endswith("-PLAN.md"):
                continue
            object_id = subprocess.run(
                ["git", "hash-object", path], cwd=ROOT, check=True,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            ).stdout.strip()
            if object_id in content.HISTORY_FINDING_DISPOSITIONS:
                continue
            report = content.scan_bytes((ROOT / path).read_bytes(), path)
            findings.extend((path, row["rules"]) for row in report["findings"])
        self.assertEqual(findings, [], f"unaudited plan privacy findings: {findings}")

        canary = "/".join(("", "Us" + "ers", "placeholder", "sentinel.txt"))
        detected = content.scan_bytes(canary.encode(), "tests/synthetic-plan-canary.txt")
        self.assertTrue(any("personal-path" in row["rules"]
                            for row in detected["findings"]))

    def test_uncatalogued_binary_test_asset_fails_tree_and_archive_rights_gates(self) -> None:
        for suffix in (".bin", ".json", ".txt", ".md", ".py", ".extension", ""):
            path = f"tests/cpu/title{suffix}"
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "docs").mkdir()
                (root / "tests/cpu").mkdir(parents=True)
                (root / path).write_bytes(b"synthetic test payload")
                (root / "docs/rights-inventory.md").write_text(
                    "```json\n{\"schema\":1,\"items\":[]}\n```\n", encoding="utf-8")
                with mock.patch.object(content, "_git_source_paths", return_value=[path]):
                    with self.assertRaises(content.ContentError) as caught:
                        content.validate_repository_inventory(root)
                self.assertEqual(caught.exception.reason, "rights-path-set", path)
                archive = root / "source.tar.gz"
                with tarfile.open(archive, "w:gz") as stream:
                    item = tarfile.TarInfo(path)
                    item.size = len(b"synthetic test payload")
                    stream.addfile(item, io.BytesIO(b"synthetic test payload"))
                with self.assertRaises(content.ContentError) as caught:
                    content.scan_archive(archive)
                self.assertEqual(caught.exception.reason, "rights-path-set", path)

    def test_personal_home_path_mentions_are_found_and_redacted(self) -> None:
        local_home = os.path.expanduser("~")
        suffix = "/".join((".codex", "config.toml"))
        path = local_home + "/" + suffix
        for text in ("@" + path, "(" + path + ")", "[config] (" + path + ")"):
            result = content.scan_bytes(text.encode(), "tests/synthetic-reference.txt")
            self.assertIn("personal-path", result["findings"][0]["rules"])
            self.assertNotIn(local_home, json.dumps(result))

    def test_only_listed_noreply_trailer_identities_are_public(self) -> None:
        trailer = "Co-Authored-By: Claude <" + "noreply" + "@anthropic.com>"
        self.assertEqual(content.scan_bytes(trailer.encode(), "history/commit-metadata")["findings"], [])
        other = "Contact: <" + "someone" + "@anthropic.com>"
        result = content.scan_bytes(other.encode(), "history/commit-metadata")
        self.assertIn("private-identity", result["findings"][0]["rules"])
        for lookalike in ("noreply" + "@anthropic.com.evil.test", "xnoreply" + "@anthropic.com",
                          "noreply" + "@mail.anthropic.com"):
            with self.subTest(lookalike=lookalike):
                found = content.scan_bytes(("Contact: <" + lookalike + ">").encode(), "history/commit-metadata")
                self.assertIn("private-identity", found["findings"][0]["rules"])

    def test_private_key_header_is_detected_without_echoing_header(self) -> None:
        header = "-----BEGIN " + "OPENSSH " + "PRIVATE KEY-----"
        result = content.scan_bytes((header + "\nsynthetic-key\n-----END OPENSSH PRIVATE KEY-----").encode(),
                                    "tests/synthetic-key.txt")
        self.assertIn("private-key", result["findings"][0]["rules"])
        self.assertNotIn(header, json.dumps(result))

    def test_windows_home_paths_are_detected_and_redacted(self) -> None:
        for separator in ("\\", "/"):
            path = separator.join(("C:", "Users", "synthetic-account", "private.txt"))
            result = content.scan_bytes(("[file](" + path + ")").encode(), "tests/synthetic-reference.txt")
            self.assertIn("personal-path", result["findings"][0]["rules"])
            self.assertNotIn(path, json.dumps(result))

    def test_openpgp_private_key_header_is_detected_and_redacted(self) -> None:
        header = "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----"
        result = content.scan_bytes(header.encode(), "tests/synthetic-key.txt")
        self.assertIn("private-key", result["findings"][0]["rules"])
        self.assertNotIn(header, json.dumps(result))

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

    def test_archive_resource_limits_accept_the_boundary_and_reject_the_next_byte_or_member(self) -> None:
        with tempfile.TemporaryDirectory(prefix="public-content-limits-") as temp:
            archive = Path(temp) / "bounded.tar.gz"

            def write_archive(members: list[tuple[str, bytes]]) -> None:
                with tarfile.open(archive, "w:gz") as stream:
                    for name, body in members:
                        item = tarfile.TarInfo(name)
                        item.size = len(body)
                        stream.addfile(item, io.BytesIO(body))

            with mock.patch.object(content, "MAX_FILE_BYTES", 4), \
                    mock.patch.object(content, "MAX_MEMBERS", 2):
                write_archive([("payload/one.bin", b"1234"), ("payload/two.bin", b"5678")])
                self.assertEqual(content.scan_archive(archive)["members"], 2)
                write_archive([("payload/one.bin", b"12345")])
                with self.assertRaises(content.ContentError) as caught:
                    content.scan_archive(archive)
                self.assertEqual(caught.exception.reason, "archive-file-limit")
                write_archive([(f"payload/{index}.bin", b"x") for index in range(3)])
                with self.assertRaises(content.ContentError) as caught:
                    content.scan_archive(archive)
                self.assertEqual(caught.exception.reason, "archive-count")

            with mock.patch.object(content, "MAX_TOTAL_BYTES", 512):
                write_archive([("payload/one.bin", b"a" * 256), ("payload/two.bin", b"b" * 256)])
                self.assertEqual(content.scan_archive(archive)["bytes"], 512)
                write_archive([("payload/one.bin", b"a" * 256), ("payload/two.bin", b"b" * 257)])
                with self.assertRaises(content.ContentError) as caught:
                    content.scan_archive(archive)
                self.assertEqual(caught.exception.reason, "archive-total-limit")

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
        actual_count = sum(content._is_rights_candidate(path) for path in content._git_source_paths(ROOT))
        self.assertEqual(result["items"], actual_count)

    def test_rights_inventory_binds_bytes_and_rejects_unknown_or_changed_item(self) -> None:
        inventory = {"schema": 1, "items": [{
            "path": "fixture.bin", "sha256": hashlib.sha256(b"fixture").hexdigest(),
            "kind": "fixture", "license": "MIT", "rights": "affirmative",
            "source_revision": "a" * 40, "provenance": "original project work", "notice": "LICENSE",
        }]}
        self.assertTrue(content.validate_inventory(inventory, {"fixture.bin": b"fixture"})["passed"])
        for actual, reason in (({"unknown.bin": b"x"}, "rights-path-set"),
                               ({"fixture.bin": b"changed"}, "rights-digest")):
            with self.assertRaises(content.ContentError):
                try:
                    content.validate_inventory(inventory, actual)
                except content.ContentError as error:
                    self.assertEqual(error.reason, reason)
                    raise
        inventory["items"][0]["rights"] = "unknown"
        with self.assertRaises(content.ContentError):
            content.validate_inventory(inventory, {"fixture.bin": b"fixture"})

    def test_original_recipe_provenance_tracks_guest_and_sample_helper_copy(self) -> None:
        manifest = json.loads((ROOT / "tests/fixture/rights-manifest.json").read_text(encoding="utf-8"))
        fixture = manifest["public_persistence_fixture"]
        self.assertEqual(fixture["rights"], {
            "status": "affirmative", "license": "MIT", "notice": "LICENSE",
            "third_party_guest_bytes": False, "game_rom_or_commercial_bytes": False,
            "production_bios_bytes": False, "private_media_or_capture_bytes": False,
        })
        self.assertFalse(fixture["oracle"]["hardware_truth_established"])
        self.assertTrue(fixture["oracle"]["emulator_only"])
        for row in (fixture["generator_source"], fixture["base_source"]):
            current = (ROOT / row["path"]).read_bytes()
            recorded = subprocess.check_output(
                ["git", "show", f"{row['source_revision']}:{row['path']}"], cwd=ROOT)
            self.assertEqual(len(current), row["bytes"])
            self.assertEqual(hashlib.sha256(current).hexdigest(), row["sha256"])
            self.assertEqual(recorded, current)

        helper = manifest["sample_owned_helper"]
        self.assertEqual(helper["license"], "MIT")
        self.assertEqual(helper["owner"], "Glueyneo Maintainers")
        self.assertIn("review drift", helper["drift_check"].lower())
        origin_revision = "a73a9f543d8743896a5e4b7d2b28d0189f3e94c8"
        for row in helper["origin_sources"]:
            self.assertEqual(row["source_revision"], origin_revision)
            recorded = subprocess.check_output(
                ["git", "show", f"{origin_revision}:{row['path']}"], cwd=ROOT)
            self.assertEqual(len(recorded), row["bytes"])
            self.assertEqual(hashlib.sha256(recorded).hexdigest(), row["sha256"])
        for row in helper["sample_sources"]:
            current = (ROOT / row["path"]).read_bytes()
            recorded = subprocess.check_output(
                ["git", "show", f"{row['source_revision']}:{row['path']}"], cwd=ROOT)
            self.assertEqual(len(current), row["bytes"])
            self.assertEqual(hashlib.sha256(current).hexdigest(), row["sha256"])
            self.assertEqual(recorded, current)

    def test_rights_inventory_rejects_nonobjects_mixed_rows_and_noncanonical_paths(self) -> None:
        valid_item = {
            "path": "fixture.bin", "sha256": hashlib.sha256(b"fixture").hexdigest(),
            "kind": "fixture", "license": "MIT", "rights": "affirmative",
            "source_revision": "a" * 40, "provenance": "original project work", "notice": "LICENSE",
        }
        malformed = (
            (None, "rights-schema"),
            ([], "rights-schema"),
            ({"schema": True, "items": [valid_item]}, "rights-schema"),
            ({"schema": 1, "items": [valid_item, None]}, "rights-schema"),
            ({"schema": 1, "items": [{**valid_item, "path": []}]}, "rights-path"),
        )
        for inventory, reason in malformed:
            with self.subTest(inventory=inventory):
                with self.assertRaises(content.ContentError) as caught:
                    content.validate_inventory(inventory, {"fixture.bin": b"fixture"})
                self.assertEqual(caught.exception.reason, reason)
        for path in ("", "-fixture.bin", "fixture//asset.bin", "fixture/./asset.bin",
                     "fixture/../asset.bin", "/fixture.bin", "fixture\\asset.bin"):
            with self.subTest(path=path):
                candidate = {"schema": 1, "items": [{**valid_item, "path": path}]}
                with self.assertRaises(content.ContentError) as caught:
                    content.validate_inventory(candidate, {path: b"fixture"})
                self.assertEqual(caught.exception.reason, "rights-path")

    def test_archive_rights_inventory_rejects_nonobject_and_mixed_rows(self) -> None:
        candidates = (
            (None, "rights-schema"),
            ([], "rights-schema"),
            ({"schema": True, "items": []}, "rights-schema"),
            ({"schema": 1, "items": [None]}, "rights-schema"),
            ({"schema": 1, "items": [{"path": []}]}, "rights-path"),
        )
        rows = [{"path": "tests/fixture/public.bin", "sha256": hashlib.sha256(b"x").hexdigest()}]
        for inventory, reason in candidates:
            with self.subTest(inventory=inventory), mock.patch.object(
                    content, "load_rights_inventory", return_value=inventory):
                with self.assertRaises(content.ContentError) as caught:
                    content._validate_archive_inventory(rows)
                self.assertEqual(caught.exception.reason, reason)

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

    def test_source_tree_file_count_and_byte_limits_accept_boundary_and_reject_next_unit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="public-content-source-limits-") as temp:
            root = Path(temp)
            for name in ("one.txt", "two.txt", "three.txt"):
                (root / name).write_bytes(b"x")
            with mock.patch.object(content, "MAX_SOURCE_FILES", 2), \
                    mock.patch.object(content, "MAX_TOTAL_BYTES", 2):
                self.assertEqual(content.scan_tree(root, ["one.txt", "two.txt"])["bytes"], 2)
                with self.assertRaises(content.ContentError) as caught:
                    content.scan_tree(root, ["one.txt", "two.txt", "three.txt"])
                self.assertEqual(caught.exception.reason, "source-count")
                with mock.patch.object(content, "MAX_SOURCE_FILES", 3):
                    with self.assertRaises(content.ContentError) as caught:
                        content.scan_tree(root, ["one.txt", "two.txt", "three.txt"])
                    self.assertEqual(caught.exception.reason, "input-total-limit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
