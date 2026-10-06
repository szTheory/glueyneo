#!/usr/bin/env python3
"""Adversarial controls for serialized draft recovery."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import release_state


COMMIT = "a" * 40
ASSETS = {
    "glueyneo-source-0.1.0.tar.gz": {"size": 3, "sha256": hashlib.sha256(b"src").hexdigest()},
    "glueyneo-sdk-0.1.0-linux-x86_64.tar.gz": {"size": 3, "sha256": hashlib.sha256(b"lin").hexdigest()},
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
        self.assertEqual(result["missing_assets"], ["glueyneo-sdk-0.1.0-linux-x86_64.tar.gz"])

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
