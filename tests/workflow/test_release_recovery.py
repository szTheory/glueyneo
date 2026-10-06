#!/usr/bin/env python3
"""Adversarial controls for serialized draft recovery."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import release_state


COMMIT = "a" * 40
ASSETS = {
    "glueyneo-source-0.1.0.tar.gz": {"size": 3, "sha256": hashlib.sha256(b"src").hexdigest()},
    "glueyneo-sdk-0.1.0-linux-x86_64.tar.gz": {"size": 3, "sha256": hashlib.sha256(b"lin").hexdigest()},
    "glueyneo-sdk-0.1.0-macos-arm64.tar.gz": {"size": 3, "sha256": hashlib.sha256(b"mac").hexdigest()},
    "glueyneo-sdk-0.1.0-windows-x86_64.tar.gz": {"size": 3, "sha256": hashlib.sha256(b"win").hexdigest()},
    "release-manifest.json": {"size": 3, "sha256": hashlib.sha256(b"{}\n").hexdigest()},
}


def draft(assets=None, **overrides):
    value = {"draft": True, "tag_name": "v0.1.0", "target_commitish": COMMIT,
             "tag_commit": COMMIT, "assets": list(assets if assets is not None else
                 [{"name": name, **record} for name, record in ASSETS.items()])}
    value.update(overrides)
    return value


def validate(value):
    return release_state.validate_release(
        value, expected_tag="v0.1.0", expected_version="0.1.0",
        expected_commit=COMMIT, manifest_version="0.1.0", expected_assets=ASSETS,
    )


class ReleaseRecoveryTests(unittest.TestCase):
    def test_api_inventory_binds_all_packages_and_manifest_bytes(self):
        package_rows = [
            {"name": name, **record}
            for name, record in ASSETS.items() if name != "release-manifest.json"
        ]
        manifest = {"schema_version": 1, "version": "0.1.0", "tag": "v0.1.0",
                    "source_commit": COMMIT, "assets": package_rows}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "release-manifest.json"
            path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
            expected = release_state.expected_api_assets(path)
            self.assertEqual(set(expected), set(ASSETS))
            self.assertEqual(expected["release-manifest.json"]["size"], path.stat().st_size)
            self.assertEqual(expected["release-manifest.json"]["sha256"],
                             hashlib.sha256(path.read_bytes()).hexdigest())
            manifest["assets"].pop()
            path.write_text(json.dumps(manifest))
            with self.assertRaises(release_state.ReleaseStateError):
                release_state.expected_api_assets(path)

    def test_retry_queries_existing_draft_even_without_new_release_output(self):
        class FakeAPI:
            def __init__(self):
                self.calls = []
                self.mutations = 0

            def get_release_by_tag(self, tag):
                self.calls.append(tag)
                return draft()

        api = FakeAPI()
        result = release_state.query_existing_release(api, "v0.1.0", release_created=False)
        self.assertEqual(result["status"], "found")
        self.assertEqual(api.calls, ["v0.1.0"])
        self.assertEqual(api.mutations, 0)

    def test_complete_draft_is_publishable_and_order_independent(self):
        assets = [{"name": name, **record} for name, record in reversed(list(ASSETS.items()))]
        result = validate(draft(assets))
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["publishable"])

    def test_partial_verified_upload_is_resumable_but_not_publishable(self):
        first = {"name": next(iter(ASSETS)), **next(iter(ASSETS.values()))}
        result = validate(draft([first]))
        self.assertEqual(result["status"], "resume")
        self.assertFalse(result["publishable"])
        self.assertEqual(result["missing_assets"], sorted(set(ASSETS) - {first["name"]}))

    def test_empty_interrupted_upload_can_resume_without_publication(self):
        result = validate(draft([]))
        self.assertEqual(result["status"], "resume")
        self.assertFalse(result["publishable"])

    def test_wrong_target_version_and_published_state_are_rejected(self):
        for changed in (
            draft(tag_commit="b" * 40), draft(target_commitish="b" * 40),
            draft(tag_name="v0.1.1"), draft(draft=False),
        ):
            with self.subTest(changed=changed):
                self.assertEqual(validate(changed)["status"], "reject")

    def test_extra_missing_duplicate_and_replaced_assets_are_rejected(self):
        complete = [{"name": name, **record} for name, record in ASSETS.items()]
        bad_sets = [complete + [{"name": "unexpected.zip", "size": 1, "sha256": "0" * 64}],
                    [complete[0], complete[0]],
                    [{**complete[0], "sha256": "0" * 64}, complete[1]],
                    [{**complete[0], "size": 4}, complete[1]]]
        for assets in bad_sets:
            with self.subTest(assets=assets):
                self.assertEqual(validate(draft(assets))["status"], "reject")

    def test_missing_assets_are_only_resumable_when_every_existing_asset_matches(self):
        complete = [{"name": name, **record} for name, record in ASSETS.items()]
        self.assertEqual(validate(draft(complete[:-1]))["status"], "resume")

    def test_manifest_and_release_identity_must_agree(self):
        result = release_state.validate_release(
            draft(), expected_tag="v0.1.0", expected_version="0.1.0",
            expected_commit=COMMIT, manifest_version="0.1.1", expected_assets=ASSETS,
        )
        self.assertEqual(result["status"], "reject")

    def test_release_workflow_keeps_publish_behind_three_downloaded_consumers(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
        config = json.loads((root / "release-please-config.json").read_text(encoding="utf-8"))
        self.assertIn("googleapis/release-please-action@5c625bfb5d1ff62eadeeb3772007f7f66fdcf071", workflow)
        self.assertIn("actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("verify-downloaded-release", workflow)
        self.assertIn("needs: [release-control, stage-release, verify-downloaded-release]", workflow)
        self.assertIs(config["packages"]["."]["draft"], True)
        self.assertTrue(config["$schema"].endswith("release-please/v17.3.0/schemas/config.json"))
        for platform in ("linux-x86_64", "macos-arm64", "windows-x86_64"):
            self.assertIn(f"name: {platform}", workflow)
        self.assertIn("validate-draft", workflow)
        self.assertIn("verify-download", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
