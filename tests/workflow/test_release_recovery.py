#!/usr/bin/env python3
"""Adversarial controls for serialized draft recovery."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import release_state
import sdk_evidence


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


def release_record(release_id, tag):
    return {"id": release_id, "tag_name": tag, "draft": True, "assets": []}


class FakeGitHubReleaseAPI(release_state.GitHubReleaseAPI):
    def __init__(self, responses):
        super().__init__("owner/repo", "test-token")
        self.responses = responses
        self.calls = []

    def _get(self, path, *, timeout=20):
        self.calls.append((path, timeout))
        if path not in self.responses:
            raise AssertionError(f"unexpected GitHub API request: {path}")
        response = self.responses[path]
        if isinstance(response, BaseException):
            raise response
        return response


class GitHubReleaseLookupTests(unittest.TestCase):
    tag = "v0.2.0"
    tag_path = "/releases/tags/v0.2.0"
    page_size = 100
    list_timeout = 10
    max_pages = 5
    max_response_bytes = 8 * 1024 * 1024

    def page_path(self, page):
        return f"/releases?per_page={self.page_size}&page={page}"

    def test_published_tag_lookup_keeps_the_direct_fast_path(self):
        published = release_record(42, self.tag)
        published["draft"] = False
        api = FakeGitHubReleaseAPI({self.tag_path: published})

        self.assertIs(api.get_release_by_tag(self.tag), published)
        self.assertEqual(api.calls, [(self.tag_path, 20)])

    def test_tag_404_lists_bounded_pages_and_matches_the_exact_tag(self):
        first_page = [release_record(index + 1, f"v0.1.{index}")
                      for index in range(self.page_size)]
        second_page = [release_record(101, self.tag), release_record(102, "v0.2.0-rc.1")]
        api = FakeGitHubReleaseAPI({self.tag_path: None, self.page_path(1): first_page,
                                    self.page_path(2): second_page})

        self.assertEqual(api.get_release_by_tag(self.tag), second_page[0])
        self.assertEqual(api.calls, [
            (self.tag_path, 20),
            (self.page_path(1), self.list_timeout),
            (self.page_path(2), self.list_timeout),
        ])

    def test_exact_tag_absence_requires_a_complete_short_page(self):
        page = [release_record(1, "v0.1.0"), release_record(2, "V0.2.0")]
        api = FakeGitHubReleaseAPI({self.tag_path: None, self.page_path(1): page})

        result = release_state.query_existing_release(api, self.tag, release_created=False)

        self.assertEqual(result, {"status": "absent", "release": None})
        self.assertEqual(api.calls[-1], (self.page_path(1), self.list_timeout))

    def test_duplicate_exact_tags_are_rejected_across_pages(self):
        first_page = [release_record(1, self.tag)] + [
            release_record(index + 2, f"v0.1.{index}")
            for index in range(self.page_size - 1)
        ]
        second_page = [release_record(101, self.tag)]
        api = FakeGitHubReleaseAPI({self.tag_path: None, self.page_path(1): first_page,
                                    self.page_path(2): second_page})

        with self.assertRaisesRegex(release_state.ReleaseStateError, "ambiguous"):
            api.get_release_by_tag(self.tag)

    def test_malformed_release_list_or_rows_are_rejected(self):
        malformed_pages = (
            None,
            {"message": "not a list"},
            ["not a release object"],
            [{"id": 1, "draft": True}],
            [{"id": True, "tag_name": self.tag, "draft": True}],
            [{"id": 1, "tag_name": self.tag, "draft": "true"}],
            [{"id": 1, "tag_name": self.tag, "draft": True}],
        )
        for page in malformed_pages:
            with self.subTest(page=page):
                api = FakeGitHubReleaseAPI({self.tag_path: None, self.page_path(1): page})
                with self.assertRaises(release_state.ReleaseStateError):
                    api.get_release_by_tag(self.tag)

    def test_full_page_bound_fails_closed_instead_of_claiming_absence(self):
        responses = {self.tag_path: None}
        for page in range(1, self.max_pages + 1):
            responses[self.page_path(page)] = [
                release_record(page * self.page_size + index,
                               f"v0.1.{page}.{index}")
                for index in range(self.page_size)
            ]
        api = FakeGitHubReleaseAPI(responses)

        with self.assertRaisesRegex(release_state.ReleaseStateError, "page limit"):
            api.get_release_by_tag(self.tag)
        self.assertEqual(len(api.calls), self.max_pages + 1)

    def test_api_response_body_read_is_size_bounded(self):
        class Response:
            def __init__(self):
                self.read_size = None

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, size=-1):
                self.read_size = size
                return b"x" * size

        response = Response()
        api = release_state.GitHubReleaseAPI("owner/repo", "test-token")
        with mock.patch.object(release_state, "urlopen", return_value=response):
            with self.assertRaisesRegex(release_state.ReleaseStateError, "size limit"):
                api._get("/releases")
        self.assertEqual(response.read_size, self.max_response_bytes + 1)


class ReleaseRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.cli_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.cli_temp.cleanup)
        self.cli_directory = Path(self.cli_temp.name)
        self.cli_manifest_path = self.cli_directory / "release-manifest.json"
        archive_names = sorted(release_state.required_archive_names("0.1.0"))
        rows = []
        for name in archive_names:
            data = f"release archive fixture: {name}".encode("ascii")
            rows.append({"name": name, "size": len(data),
                         "sha256": hashlib.sha256(data).hexdigest()})
        manifest = {"schema_version": 1, "version": "0.1.0", "tag": "v0.1.0",
                    "source_commit": COMMIT, "assets": rows}
        self.cli_manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        self.cli_assets = release_state.expected_api_assets(self.cli_manifest_path)

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

    def test_validate_draft_cli_accepts_found_query_snapshot_for_empty_resume(self):
        result = self.run_validate_draft_cli({"status": "found", "release": self.cli_release([])})
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["status"], "resume")
        self.assertFalse(value["publishable"])

    def test_validate_draft_cli_accepts_complete_found_query_snapshot(self):
        assets = [{"name": name, **record} for name, record in self.cli_assets.items()]
        result = self.run_validate_draft_cli({"status": "found", "release": self.cli_release(assets)})
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["status"], "ready")
        self.assertTrue(value["publishable"])

    def test_validate_draft_cli_rejects_wrong_tag_in_query_snapshot(self):
        result = self.run_validate_draft_cli({
            "status": "found", "release": self.cli_release([], tag_name="v0.1.1")
        })
        self.assertNotEqual(result.returncode, 0)

    def test_validate_draft_cli_rejects_non_found_query_status(self):
        result = self.run_validate_draft_cli({"status": "absent", "release": None})
        self.assertNotEqual(result.returncode, 0)

    def test_validate_draft_cli_rejects_malformed_query_snapshot(self):
        result = self.run_validate_draft_cli({"status": "found", "release": []})
        self.assertNotEqual(result.returncode, 0)

    def cli_release(self, assets, *, tag_name="v0.1.0"):
        return {"draft": True, "tag_name": tag_name, "target_commitish": COMMIT,
                "tag_commit": COMMIT, "assets": assets}

    def run_validate_draft_cli(self, snapshot):
        snapshot_path = self.cli_directory / "release-query.json"
        snapshot_path.write_text(json.dumps(snapshot, sort_keys=True, separators=(",", ":")) + "\n",
                                 encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[2] / "tools/release_state.py"),
             "validate-draft", "--release", str(snapshot_path), "--manifest", str(self.cli_manifest_path),
             "--tag", "v0.1.0", "--version", "0.1.0", "--commit", COMMIT],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=10,
        )

    def test_release_workflow_keeps_publish_behind_three_downloaded_consumers(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
        config = json.loads((root / "release-please-config.json").read_text(encoding="utf-8"))
        self.assertIn("googleapis/release-please-action@5c625bfb5d1ff62eadeeb3772007f7f66fdcf071", workflow)
        self.assertIn("actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("verify-downloaded-release", workflow)
        self.assertIn("needs: [release-control, stage-release, verify-downloaded-release]", workflow)
        self.assertIn(
            "publish:\n        description: Publish the verified draft after all staging and downloaded-consumer checks pass\n        required: false\n        default: false\n        type: boolean",
            workflow,
        )
        self.assertIn("&& (github.event_name == 'push' || inputs.publish)", workflow)
        self.assertIs(config["packages"]["."]["draft"], True)
        self.assertTrue(config["$schema"].endswith("release-please/v17.3.0/schemas/config.json"))
        for platform in ("linux-x86_64", "macos-arm64", "windows-x86_64"):
            self.assertIn(f"name: {platform}", workflow)
        self.assertIn("validate-draft", workflow)
        self.assertIn("verify-download", workflow)

    def test_release_build_matrix_uses_supported_sdk_lanes_and_compilers(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
        build = workflow.split("\n  build-release:\n", 1)[1].split("\n  stage-release:\n", 1)[0]
        matrix_section = build.split("      matrix:\n", 1)[1].split("\n    steps:\n", 1)[0]

        rows = []
        current = None
        for line in matrix_section.splitlines():
            if line.startswith("          - "):
                if current is not None:
                    rows.append(current)
                key, value = line.strip()[2:].split(": ", 1)
                current = {key: value.strip('"')}
            elif current is not None and line.startswith("            "):
                key, value = line.strip().split(": ", 1)
                current[key] = value.strip('"')
        if current is not None:
            rows.append(current)

        expected = {
            "linux-x86_64": ("ubuntu-24.04", "linux-clang", "clang", "clang++"),
            "macos-arm64": ("macos-15", "macos-appleclang", "", ""),
            "windows-x86_64": ("windows-2025", "windows-msvc", "", ""),
        }
        self.assertEqual({row.get("name") for row in rows}, set(expected))
        runner_os = {"ubuntu-24.04": "Linux", "macos-15": "Darwin", "windows-2025": "Windows"}
        verify_sdk = (root / "tools/verify_sdk.py").read_text(encoding="utf-8")
        self.assertIn("parser.add_argument(\"--lane\", choices=evidence.REQUIRED_MATRIX_LANES)", verify_sdk)

        for row in rows:
            name = row["name"]
            self.assertIn("lane", row, f"release matrix row {name} must select an SDK evidence lane")
            runner, lane, cc, cxx = expected[name]
            self.assertEqual((row.get("runner"), row.get("lane"), row.get("cc"), row.get("cxx")),
                             (runner, lane, cc, cxx))
            self.assertIn(row["lane"], sdk_evidence.REQUIRED_MATRIX_LANES)
            observed_os, compiler_ids, _architectures = sdk_evidence.MATRIX_LANE_IDENTITY[row["lane"]]
            self.assertEqual(observed_os, runner_os[row["runner"]])
            compiler_for_lane = {
                "linux-clang": "Clang",
                "macos-appleclang": "AppleClang",
                "windows-msvc": "MSVC",
            }[row["lane"]]
            self.assertIn(compiler_for_lane, compiler_ids)

        linux_step = workflow.split("- name: Run exact-commit SDK matrix and installed consumers\n", 1)[1].split(
            "- name: Run exact-commit Windows SDK matrix and installed consumers\n", 1
        )[0]
        windows_step = workflow.split("- name: Run exact-commit Windows SDK matrix and installed consumers\n", 1)[1]
        for contract in (
            "SDK_MATRIX_LANE: ${{ matrix.lane }}",
            "CC: ${{ matrix.cc }}",
            "CXX: ${{ matrix.cxx }}",
            "--lane \"$SDK_MATRIX_LANE\"",
        ):
            self.assertIn(contract, linux_step)
        self.assertIn("SDK_MATRIX_LANE: ${{ matrix.lane }}", windows_step)
        self.assertIn("--lane ' + $env:SDK_MATRIX_LANE", windows_step)
        self.assertIn("name: release-matrix-${{ matrix.name }}", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
