#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check a trusted release job's effective installation-token repository scope."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

MAX_RESPONSE_BYTES = 512 * 1024


class ScopeError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    # Refuse redirects before an Authorization header can reach another URL.
    return urllib.request.build_opener(NoRedirect()).open(request, timeout=30)


def validate_scope(payload: object, repository: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ScopeError("invalid-repository")
    if not isinstance(payload, dict) or type(payload.get("total_count")) is not int:
        raise ScopeError("invalid-response")
    rows = payload.get("repositories")
    if (payload["total_count"] != 1 or not isinstance(rows, list) or len(rows) != 1
            or not isinstance(rows[0], dict) or rows[0].get("full_name") != repository):
        raise ScopeError("unexpected-repository-scope")


def observe(env: dict[str, str]) -> dict[str, object]:
    if env.get("GITHUB_API_URL", "https://api.github.com").rstrip("/") != "https://api.github.com":
        raise ScopeError("unsupported-api-origin")
    token = env.get("GH_TOKEN", "")
    repository = env.get("GITHUB_REPOSITORY", "")
    sha = env.get("GITHUB_SHA", "")
    run_id = env.get("GITHUB_RUN_ID", "")
    installation_id = env.get("APP_INSTALLATION_ID", "")
    job = env.get("GITHUB_JOB", "")
    if (not token or not re.fullmatch(r"[0-9a-f]{40}", sha)
            or not re.fullmatch(r"[1-9][0-9]*", run_id)
            or not re.fullmatch(r"[1-9][0-9]*", installation_id)
            or not re.fullmatch(r"[A-Za-z0-9_-]+", job)):
        raise ScopeError("missing-job-identity")
    validate_scope({"total_count": 1, "repositories": [{"full_name": repository}]}, repository)
    request = urllib.request.Request(
        "https://api.github.com/installation/repositories?per_page=2",
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2026-03-10", "User-Agent": "Glueyneo-release-scope"})
    with open_request(request) as response:
        if response.geturl() != request.full_url:
            raise ScopeError("unexpected-api-redirect")
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ScopeError("response-limit")
    validate_scope(json.loads(data), repository)
    return {"schema_version": 1, "outcome": "pass", "kind": "effective-token-repository-scope",
            "repository": repository, "repository_count": 1, "source_revision": sha,
            "run_id": run_id, "job": job, "installation_id": installation_id,
            "max_lifetime_seconds": 3600, "lifetime_basis": "GitHub installation-token API contract; not measured",
            "revocation": "pinned token action post-job; inspect job log",
            "installation_wide_grant": "not inspected"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = observe(dict(os.environ))
        encoded = json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0
    except (ScopeError, ValueError, OSError, urllib.error.URLError) as error:
        # A failure may carry an HTTP body, private repo name or credential.
        print("APP_SCOPE fail: " + type(error).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
