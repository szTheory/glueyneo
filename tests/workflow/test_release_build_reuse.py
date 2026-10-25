#!/usr/bin/env python3
"""Adversarial tests for reuse of artifacts from an earlier trusted build."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/workflow"))
import release_build_reuse as reuse


REPOSITORY = "szTheory/glueyneo"
REPOSITORY_ID = 1407768047
RUN_ID = 40215191635
WORKFLOW_ID = 382379702
VERSION = "0.2.0"
TOKEN = "test-token-never-printed"


class FakeActionsAPI:
    def __init__(self, *, repository_id=REPOSITORY_ID, workflow_id=WORKFLOW_ID):
        self.repository = {"id": repository_id, "full_name": REPOSITORY}
        self.workflow = {"id": workflow_id, "path": reuse.WORKFLOW_PATH}
        self.run = None
        self.jobs = None
        self.artifacts = None
        self.calls = []

    def get_repository(self, repository):
        self.calls.append(("repository", repository))
        return copy.deepcopy(self.repository)

    def get_workflow(self, repository, path):
        self.calls.append(("workflow", repository, path))
        return copy.deepcopy(self.workflow)

    def get_run(self, repository, run_id):
        self.calls.append(("run", repository, run_id))
        return copy.deepcopy(self.run)

    def list_jobs(self, repository, run_id, attempt):
        self.calls.append(("jobs", repository, run_id, attempt))
        return copy.deepcopy(self.jobs)

    def list_artifacts(self, repository, run_id):
        self.calls.append(("artifacts", repository, run_id))
        return copy.deepcopy(self.artifacts)


class ReleaseBuildReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Release Test")
        self.git("config", "user.email", "test@example.invalid")
        self.old_version_sha = self.commit("0.1.9", "stable release helper", "old-version")
        self.prior_sha = self.commit(VERSION, "stable release helper", "qualified build")
        self.current_sha = self.commit(VERSION, "stable release helper", "workflow staging repair")
        self.env = {
            "GITHUB_API_URL": reuse.API_ORIGIN,
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_REPOSITORY_ID": str(REPOSITORY_ID),
            "GITHUB_SHA": self.current_sha,
        }
        self.api = self.make_api()

    def git(self, *arguments):
        return subprocess.run(
            ["git", *arguments], cwd=self.repo, check=True,
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()

    def commit(self, version, helper_text, message):
        manifest = self.repo / ".release-please-manifest.json"
        manifest.write_text(json.dumps({".": version}) + "\n", encoding="utf-8")
        helper = self.repo / reuse.PACKAGING_HELPER_PATH
        helper.parent.mkdir(parents=True, exist_ok=True)
        helper.write_text(helper_text + "\n", encoding="utf-8")
        (self.repo / ".fixture-commit-marker").write_text(message + "\n", encoding="utf-8")
        self.git("add", ".release-please-manifest.json", reuse.PACKAGING_HELPER_PATH,
                 ".fixture-commit-marker")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def make_api(self):
        api = FakeActionsAPI()
        api.run = {
            "id": RUN_ID,
            "status": "completed",
            # A failed read-only release consumer does not invalidate successful builds/staging.
            "conclusion": "failure",
            "run_attempt": 1,
            "event": "workflow_dispatch",
            "head_branch": "main",
            "head_sha": self.prior_sha,
            "path": reuse.WORKFLOW_PATH,
            "workflow_id": WORKFLOW_ID,
            "pull_requests": [],
            "repository": {"id": REPOSITORY_ID, "full_name": REPOSITORY},
            "head_repository": {"id": REPOSITORY_ID, "full_name": REPOSITORY},
        }
        job_names = (
            "release-control",
            "build-release (linux-x86_64, ubuntu-24.04, linux-clang, clang, clang++)",
            "build-release (macos-arm64, macos-15, macos-appleclang)",
            "build-release (windows-x86_64, windows-2025, windows-msvc)",
            "stage-release",
        )
        api.jobs = {
            "total_count": len(job_names),
            "jobs": [{"name": name, "run_id": RUN_ID, "head_sha": self.prior_sha,
                      "status": "completed", "conclusion": "success"} for name in job_names],
        }
        artifact_run = {"id": RUN_ID, "repository_id": REPOSITORY_ID,
                        "head_repository_id": REPOSITORY_ID, "head_branch": "main",
                        "head_sha": self.prior_sha}
        api.artifacts = {
            "total_count": len(reuse.REQUIRED_ARTIFACTS),
            "artifacts": [
                {"id": index, "name": name, "expired": False, "size_in_bytes": 1024,
                 "digest": "sha256:" + f"{index:064x}", "workflow_run": artifact_run}
                for index, name in enumerate(reuse.REQUIRED_ARTIFACTS, start=1)
            ],
        }
        return api

    def validate(self, api=None, *, run_id=str(RUN_ID), version=VERSION, env=None):
        return reuse.validate_build_run(
            run_id=run_id, version=version, env=env or self.env,
            api=api or self.api, repository_path=self.repo,
        )

    def test_accepts_qualified_builds_even_if_consumers_failed_later(self):
        result = self.validate()
        self.assertEqual(result["build_run_id"], str(RUN_ID))
        self.assertEqual(result["version"], VERSION)
        self.assertEqual(result["workflow_sha"], self.prior_sha)
        self.assertEqual(result["artifact_count"], "4")
        self.assertEqual(self.api.calls[-2:], [
            ("jobs", REPOSITORY, RUN_ID, 1), ("artifacts", REPOSITORY, RUN_ID)
        ])

    def test_main_writes_only_validated_reuse_outputs(self):
        output_path = self.repo / "github-output.txt"
        env = {**self.env, "GH_TOKEN": TOKEN, "GITHUB_OUTPUT": str(output_path)}
        stdout = io.StringIO()
        with (mock.patch.dict(os.environ, env, clear=True),
              mock.patch.object(reuse, "GitHubActionsAPI", return_value=self.api),
              mock.patch.object(Path, "cwd", return_value=self.repo),
              contextlib.redirect_stdout(stdout)):
            result = reuse.main(["--run-id", str(RUN_ID), "--version", VERSION])
        self.assertEqual(result, 0)
        self.assertEqual(output_path.read_text(encoding="utf-8"),
                         f"build_run_id={RUN_ID}\nreuse_builds=true\n"
                         "prior_manifest_artifact_name=release-identity-manifest-attempt-1\n")
        self.assertNotIn(TOKEN, stdout.getvalue())

    def test_rejects_wrong_current_repository_identity(self):
        api = self.make_api()
        api.repository["id"] += 1
        with self.assertRaisesRegex(reuse.ReuseError, "current-repository-mismatch"):
            self.validate(api)

    def test_rejects_fork_head_repository(self):
        api = self.make_api()
        api.run["head_repository"]["id"] += 1
        with self.assertRaisesRegex(reuse.ReuseError, "prior-run-repository-mismatch"):
            self.validate(api)

    def test_rejects_wrong_workflow_id_or_path(self):
        for field, value in (("workflow_id", WORKFLOW_ID + 1),
                             ("path", ".github/workflows/other.yml")):
            with self.subTest(field=field):
                api = self.make_api()
                api.run[field] = value
                with self.assertRaisesRegex(reuse.ReuseError, "prior-run-trust-check-failed"):
                    self.validate(api)

    def test_rejects_wrong_event_branch_or_pull_request_run(self):
        for field, value in (("event", "pull_request"), ("head_branch", "feature"),
                             ("pull_requests", [{"number": 4}])):
            with self.subTest(field=field):
                api = self.make_api()
                api.run[field] = value
                with self.assertRaisesRegex(reuse.ReuseError, "prior-run-trust-check-failed"):
                    self.validate(api)

    def test_rejects_non_first_attempt_and_noncompleted_runs(self):
        for field, value in (("run_attempt", 2), ("status", "in_progress"),
                             ("conclusion", "cancelled")):
            with self.subTest(field=field):
                api = self.make_api()
                api.run[field] = value
                with self.assertRaisesRegex(reuse.ReuseError, "prior-run-trust-check-failed"):
                    self.validate(api)

    def test_rejects_failed_or_missing_required_build_jobs(self):
        api = self.make_api()
        api.jobs["jobs"][1]["conclusion"] = "failure"
        with self.assertRaisesRegex(reuse.ReuseError, "required-job-not-successful"):
            self.validate(api)

        api = self.make_api()
        api.jobs["jobs"].pop()
        api.jobs["total_count"] -= 1
        with self.assertRaisesRegex(reuse.ReuseError, "required-job-missing"):
            self.validate(api)

    def test_rejects_ambiguous_or_unbounded_job_pages(self):
        api = self.make_api()
        api.jobs["jobs"].append(copy.deepcopy(api.jobs["jobs"][0]))
        api.jobs["total_count"] += 1
        with self.assertRaisesRegex(reuse.ReuseError, "duplicate-required-job"):
            self.validate(api)

        api = self.make_api()
        api.jobs["total_count"] = reuse.MAX_API_ITEMS + 1
        with self.assertRaisesRegex(reuse.ReuseError, "api-list-limit-or-shape"):
            self.validate(api)

    def test_normalizes_real_matrix_job_names_and_rejects_foreign_or_duplicate_platforms(self):
        self.assertEqual(self.validate()["workflow_sha"], self.prior_sha)

        api = self.make_api()
        api.jobs["jobs"][1]["name"] = "build-release (linux-x86_64-extra, ubuntu-24.04, linux-clang)"
        with self.assertRaisesRegex(reuse.ReuseError, "required-job-missing"):
            self.validate(api)

        api = self.make_api()
        duplicate = copy.deepcopy(api.jobs["jobs"][1])
        duplicate["name"] = "build-release (linux-x86_64, different-runner, different-lane)"
        api.jobs["jobs"].append(duplicate)
        api.jobs["total_count"] += 1
        with self.assertRaisesRegex(reuse.ReuseError, "duplicate-required-job"):
            self.validate(api)

    def test_rejects_missing_duplicate_expired_or_undigested_artifacts(self):
        api = self.make_api()
        api.artifacts["artifacts"].pop()
        api.artifacts["total_count"] -= 1
        with self.assertRaisesRegex(reuse.ReuseError, "required-artifact-missing"):
            self.validate(api)

        for field, value, expected in (("expired", True, "required-artifact-metadata-invalid"),
                                       ("digest", "", "required-artifact-metadata-invalid")):
            with self.subTest(field=field):
                api = self.make_api()
                api.artifacts["artifacts"][0][field] = value
                with self.assertRaisesRegex(reuse.ReuseError, expected):
                    self.validate(api)

        api = self.make_api()
        api.artifacts["artifacts"].append(copy.deepcopy(api.artifacts["artifacts"][0]))
        api.artifacts["total_count"] += 1
        with self.assertRaisesRegex(reuse.ReuseError, "duplicate-required-artifact"):
            self.validate(api)

    def test_rejects_artifact_from_another_run_or_repository(self):
        for field, value in (("id", RUN_ID + 1), ("repository_id", REPOSITORY_ID + 1),
                             ("head_repository_id", REPOSITORY_ID + 1),
                             ("head_sha", "f" * 40)):
            with self.subTest(field=field):
                api = self.make_api()
                api.artifacts["artifacts"][0]["workflow_run"][field] = value
                with self.assertRaisesRegex(reuse.ReuseError, "required-artifact-origin-mismatch"):
                    self.validate(api)

    def test_rejects_changed_packaging_helper_blob(self):
        current = self.commit(VERSION, "changed packaging recipe", "new package recipe")
        self.env["GITHUB_SHA"] = current
        api = self.make_api()
        api.run["head_sha"] = self.prior_sha
        for collection in (api.jobs["jobs"], api.artifacts["artifacts"]):
            for row in collection:
                if "head_sha" in row:
                    row["head_sha"] = self.prior_sha
                else:
                    row["workflow_run"]["head_sha"] = self.prior_sha
        with self.assertRaisesRegex(reuse.ReuseError, "packaging-helper-changed"):
            self.validate(api)

    def test_rejects_nonancestor_prior_run(self):
        tree = self.git("rev-parse", "HEAD^{tree}")
        orphan_sha = self.git("commit-tree", tree, "-m", "unrelated build history")
        api = self.make_api()
        api.run["head_sha"] = orphan_sha
        for row in api.jobs["jobs"]:
            row["head_sha"] = orphan_sha
        for row in api.artifacts["artifacts"]:
            row["workflow_run"]["head_sha"] = orphan_sha
        with self.assertRaisesRegex(reuse.ReuseError, "prior-run-not-ancestor"):
            self.validate(api)

    def test_rejects_version_mismatch_and_invalid_run_id(self):
        api = self.make_api()
        api.run["head_sha"] = self.old_version_sha
        for row in api.jobs["jobs"]:
            row["head_sha"] = self.old_version_sha
        for row in api.artifacts["artifacts"]:
            row["workflow_run"]["head_sha"] = self.old_version_sha
        with self.assertRaisesRegex(reuse.ReuseError, "prior-version-mismatch"):
            self.validate(api)
        with self.assertRaisesRegex(reuse.ReuseError, "invalid-run-id"):
            self.validate(run_id="0")

    def test_rejects_unsupported_api_origin_before_network_access(self):
        env = {**self.env, "GITHUB_API_URL": "https://github.example.invalid/api/v3"}
        with (mock.patch.dict(os.environ, {**env, "GH_TOKEN": TOKEN,
                                           "GITHUB_OUTPUT": str(self.repo / "out")}, clear=True),
              mock.patch.object(reuse, "GitHubActionsAPI") as api_client,
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(reuse.main(["--run-id", str(RUN_ID), "--version", VERSION]), 1)
        api_client.assert_not_called()

    def test_http_client_caps_json_and_never_follows_redirects(self):
        request = reuse.Request("https://api.github.com/repos/owner/repo")
        self.assertIsNone(reuse.NoRedirect().redirect_request(
            request, None, 302, "Found", {}, "https://other.example.invalid/private"
        ))

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def geturl(self):
                return request.full_url

            def read(self, size):
                return b"{" * size

        class Opener:
            def open(self, actual_request, *, timeout):
                self.request = actual_request
                self.timeout = timeout
                return Response()

        opener = Opener()
        with mock.patch.object(reuse, "build_opener", return_value=opener):
            with self.assertRaisesRegex(reuse.ReuseError, "api-response-too-large"):
                reuse.GitHubActionsAPI(TOKEN)._get_json("/repos/owner/repo")
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertEqual(opener.timeout, reuse.API_TIMEOUT_SECONDS)

    def test_workflow_lookup_uses_filename_route_and_checks_full_path_response(self):
        class Response:
            def __init__(self, url):
                self.url = url

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def geturl(self):
                return self.url

            def read(self, _size):
                return json.dumps({"id": WORKFLOW_ID, "path": reuse.WORKFLOW_PATH}).encode()

        class Opener:
            def open(self, request, *, timeout):
                self.request = request
                self.timeout = timeout
                return Response(request.full_url)

        opener = Opener()
        with mock.patch.object(reuse, "build_opener", return_value=opener):
            workflow = reuse.GitHubActionsAPI(TOKEN).get_workflow(REPOSITORY, reuse.WORKFLOW_PATH)
        self.assertEqual(workflow["path"], reuse.WORKFLOW_PATH)
        self.assertEqual(
            opener.request.full_url,
            f"{reuse.API_ORIGIN}/repos/{REPOSITORY}/actions/workflows/release.yml",
        )
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer " + TOKEN)


if __name__ == "__main__":
    unittest.main(verbosity=2)
