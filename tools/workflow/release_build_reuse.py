#!/usr/bin/env python3
"""Validate an earlier trusted release build before reusing its artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_manifest import ReleaseError, VERSION_RE, read_commit


API_ORIGIN = "https://api.github.com"
API_TIMEOUT_SECONDS = 20
MAX_API_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_API_ITEMS = 100
WORKFLOW_PATH = ".github/workflows/release.yml"
PACKAGING_HELPER_PATH = "tools/release_manifest.py"
PLATFORMS = ("linux-x86_64", "macos-arm64", "windows-x86_64")
REQUIRED_JOBS = (
    "release-control",
    *(f"build-release ({platform})" for platform in PLATFORMS),
    "stage-release",
)
REQUIRED_ARTIFACTS = (
    *(f"release-matrix-{platform}" for platform in PLATFORMS),
    "release-identity-manifest-attempt-1",
)
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
POSITIVE_ID_RE = re.compile(r"^[1-9][0-9]{0,19}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$", re.IGNORECASE)


class ReuseError(ValueError):
    """A prior run failed one of the release-artifact reuse gates."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _unique_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReuseError("duplicate-json-key")
        result[key] = value
    return result


class GitHubActionsAPI:
    """Bounded read-only GitHub API client for release-run metadata."""

    def __init__(self, token: str):
        if not token:
            raise ReuseError("missing-read-token")
        self.token = token

    def _get_json(self, path: str) -> Any:
        if not path.startswith("/repos/") or path.startswith("//"):
            raise ReuseError("invalid-api-path")
        url = API_ORIGIN + path
        request = Request(
            url,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "Glueyneo-release-build-reuse",
            },
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=API_TIMEOUT_SECONDS) as response:
                if response.geturl() != url:
                    raise ReuseError("api-origin-changed")
                payload = response.read(MAX_API_RESPONSE_BYTES + 1)
        except ReuseError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError):
            raise ReuseError("api-request-failed") from None
        if len(payload) > MAX_API_RESPONSE_BYTES:
            raise ReuseError("api-response-too-large")
        try:
            value = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_json_keys)
        except (UnicodeError, json.JSONDecodeError, RecursionError):
            raise ReuseError("api-response-malformed") from None
        return value

    @staticmethod
    def _repo_path(repository: str) -> str:
        if not REPOSITORY_RE.fullmatch(repository):
            raise ReuseError("invalid-repository")
        owner, name = repository.split("/", 1)
        return f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"

    def get_repository(self, repository: str) -> Any:
        return self._get_json(self._repo_path(repository))

    def get_workflow(self, repository: str, path: str) -> Any:
        route = quote(path, safe="/")
        return self._get_json(self._repo_path(repository) + f"/actions/workflows/{route}")

    def get_run(self, repository: str, run_id: int) -> Any:
        return self._get_json(self._repo_path(repository) + f"/actions/runs/{run_id}")

    def list_jobs(self, repository: str, run_id: int, attempt: int) -> Any:
        return self._get_json(
            self._repo_path(repository)
            + f"/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page={MAX_API_ITEMS}&page=1"
        )

    def list_artifacts(self, repository: str, run_id: int) -> Any:
        return self._get_json(
            self._repo_path(repository) + f"/actions/runs/{run_id}/artifacts?per_page={MAX_API_ITEMS}&page=1"
        )


def _positive_id(value: Any) -> bool:
    return type(value) is int and value > 0


def _git_text(repository: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=repository, capture_output=True, text=True,
            check=False, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        raise ReuseError("git-inspection-failed") from None
    if result.returncode != 0:
        raise ReuseError("git-inspection-failed")
    return result.stdout.strip()


def _validate_page(payload: Any, key: str) -> list[dict[str, Any]]:
    if (not isinstance(payload, dict) or type(payload.get("total_count")) is not int
            or payload["total_count"] < 0 or payload["total_count"] > MAX_API_ITEMS):
        raise ReuseError("api-list-limit-or-shape")
    rows = payload.get(key)
    if (not isinstance(rows, list) or len(rows) != payload["total_count"]
            or any(not isinstance(row, dict) for row in rows)):
        raise ReuseError("api-list-limit-or-shape")
    return rows


def _required_job_results(rows: list[dict[str, Any]], run_id: int, head_sha: str) -> None:
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row.get("name")
        if name not in REQUIRED_JOBS:
            continue
        if name in found:
            raise ReuseError("duplicate-required-job")
        job_sha = row.get("head_sha")
        if (type(row.get("run_id")) is not int or row.get("run_id") != run_id
                or not isinstance(job_sha, str) or job_sha.lower() != head_sha
                or row.get("status") != "completed" or row.get("conclusion") != "success"):
            raise ReuseError("required-job-not-successful")
        found[name] = row
    if set(found) != set(REQUIRED_JOBS):
        raise ReuseError("required-job-missing")


def _required_artifacts(
    rows: list[dict[str, Any]], *, run_id: int, repository_id: int, head_sha: str,
) -> None:
    found: set[str] = set()
    for row in rows:
        name = row.get("name")
        if name not in REQUIRED_ARTIFACTS:
            continue
        if name in found:
            raise ReuseError("duplicate-required-artifact")
        found.add(name)
        workflow_run = row.get("workflow_run")
        if (not isinstance(workflow_run, dict) or not _positive_id(row.get("id"))
                or row.get("expired") is not False or type(row.get("size_in_bytes")) is not int
                or row["size_in_bytes"] < 1 or not isinstance(row.get("digest"), str)
                or not SHA256_RE.fullmatch(row["digest"])):
            raise ReuseError("required-artifact-metadata-invalid")
        if (type(workflow_run.get("id")) is not int or type(workflow_run.get("repository_id")) is not int
                or type(workflow_run.get("head_repository_id")) is not int
                or workflow_run.get("id") != run_id
                or workflow_run.get("repository_id") != repository_id
                or workflow_run.get("head_repository_id") != repository_id
                or workflow_run.get("head_branch") != "main"
                or not isinstance(workflow_run.get("head_sha"), str)
                or workflow_run["head_sha"].lower() != head_sha):
            raise ReuseError("required-artifact-origin-mismatch")
    if found != set(REQUIRED_ARTIFACTS):
        raise ReuseError("required-artifact-missing")


def validate_build_run(
    *, run_id: str, version: str, env: dict[str, str], api: Any, repository_path: Path,
) -> dict[str, str]:
    """Validate trusted build provenance and artifact metadata without downloading bytes."""
    if not isinstance(run_id, str) or not POSITIVE_ID_RE.fullmatch(run_id):
        raise ReuseError("invalid-run-id")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise ReuseError("invalid-version")
    repository = env.get("GITHUB_REPOSITORY", "")
    if not REPOSITORY_RE.fullmatch(repository):
        raise ReuseError("invalid-repository")
    repository_id_text = env.get("GITHUB_REPOSITORY_ID", "")
    if not POSITIVE_ID_RE.fullmatch(repository_id_text):
        raise ReuseError("invalid-repository-id")
    repository_id = int(repository_id_text)
    current_sha = env.get("GITHUB_SHA", "").lower()
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", current_sha):
        raise ReuseError("invalid-current-sha")

    current_repo = api.get_repository(repository)
    if (not isinstance(current_repo, dict) or type(current_repo.get("id")) is not int
            or current_repo.get("id") != repository_id
            or not isinstance(current_repo.get("full_name"), str)
            or current_repo["full_name"].casefold() != repository.casefold()):
        raise ReuseError("current-repository-mismatch")
    workflow = api.get_workflow(repository, WORKFLOW_PATH)
    if (not isinstance(workflow, dict) or not _positive_id(workflow.get("id"))
            or workflow.get("path") != WORKFLOW_PATH):
        raise ReuseError("current-workflow-mismatch")

    current_head = _git_text(repository_path, "rev-parse", "--verify", "HEAD^{commit}").lower()
    if current_head != current_sha:
        raise ReuseError("current-checkout-mismatch")
    try:
        resolved_current, current_version = read_commit(repository_path, current_sha)
    except (ReleaseError, subprocess.SubprocessError, OSError):
        raise ReuseError("current-version-unreadable") from None
    if resolved_current.lower() != current_sha or current_version != version:
        raise ReuseError("current-version-mismatch")

    numeric_run_id = int(run_id)
    run = api.get_run(repository, numeric_run_id)
    if (not isinstance(run, dict) or type(run.get("id")) is not int
            or run.get("id") != numeric_run_id):
        raise ReuseError("run-identity-mismatch")
    head_sha = run.get("head_sha")
    if (not isinstance(head_sha, str)
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", head_sha, re.IGNORECASE)):
        raise ReuseError("invalid-prior-sha")
    head_sha = head_sha.lower()
    if (run.get("status") != "completed" or run.get("conclusion") not in {"success", "failure"}
            or type(run.get("run_attempt")) is not int or run.get("run_attempt") != 1
            or run.get("event") not in {"push", "workflow_dispatch"}
            or run.get("head_branch") != "main" or run.get("path") != f"{WORKFLOW_PATH}@main"
            or run.get("workflow_id") != workflow["id"] or run.get("pull_requests") != []):
        raise ReuseError("prior-run-trust-check-failed")
    for field in ("repository", "head_repository"):
        record = run.get(field)
        if (not isinstance(record, dict) or type(record.get("id")) is not int
                or record.get("id") != repository_id
                or not isinstance(record.get("full_name"), str)
                or record["full_name"].casefold() != repository.casefold()):
            raise ReuseError("prior-run-repository-mismatch")

    try:
        resolved_prior, prior_version = read_commit(repository_path, head_sha)
    except (ReleaseError, subprocess.SubprocessError, OSError):
        raise ReuseError("prior-version-unreadable") from None
    if resolved_prior.lower() != head_sha or prior_version != version:
        raise ReuseError("prior-version-mismatch")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", head_sha, current_sha],
        cwd=repository_path, capture_output=True, timeout=20, check=False,
    )
    if ancestry.returncode == 1:
        raise ReuseError("prior-run-not-ancestor")
    if ancestry.returncode != 0:
        raise ReuseError("git-inspection-failed")
    prior_helper_blob = _git_text(repository_path, "rev-parse", "--verify", f"{head_sha}:{PACKAGING_HELPER_PATH}")
    current_helper_blob = _git_text(repository_path, "rev-parse", "--verify", f"{current_sha}:{PACKAGING_HELPER_PATH}")
    if prior_helper_blob != current_helper_blob:
        raise ReuseError("packaging-helper-changed")

    attempt = run["run_attempt"]
    jobs = _validate_page(api.list_jobs(repository, numeric_run_id, attempt), "jobs")
    _required_job_results(jobs, numeric_run_id, head_sha)
    artifacts = _validate_page(api.list_artifacts(repository, numeric_run_id), "artifacts")
    _required_artifacts(artifacts, run_id=numeric_run_id, repository_id=repository_id, head_sha=head_sha)
    return {
        "build_run_id": str(numeric_run_id),
        "version": version,
        "workflow_sha": head_sha,
        "artifact_count": str(len(REQUIRED_ARTIFACTS)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    try:
        env = dict(os.environ)
        if env.get("GITHUB_API_URL", API_ORIGIN).rstrip("/") != API_ORIGIN:
            raise ReuseError("unsupported-api-origin")
        api = GitHubActionsAPI(env.get("GH_TOKEN", ""))
        result = validate_build_run(
            run_id=args.run_id, version=args.version, env=env, api=api,
            repository_path=Path.cwd(),
        )
        output_path = env.get("GITHUB_OUTPUT", "")
        if not output_path:
            raise ReuseError("missing-github-output")
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"build_run_id={result['build_run_id']}\n")
            output.write("reuse_builds=true\n")
            output.write("prior_manifest_artifact_name=release-identity-manifest-attempt-1\n")
        print(json.dumps({"outcome": "pass", **result}, sort_keys=True, separators=(",", ":")))
        return 0
    except ReuseError as error:
        print(f"RELEASE_BUILD_REUSE fail: {error}", file=sys.stderr)
        return 1
    except (ReleaseError, OSError, subprocess.SubprocessError, ValueError):
        print("RELEASE_BUILD_REUSE fail: validation-error", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
