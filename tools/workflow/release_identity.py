#!/usr/bin/env python3
"""Bind trusted workflow execution to an immutable, versioned release source."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_manifest import ReleaseError, read_commit
from release_state import COMMIT_RE, ReleaseStateError, load_json


def resolve_identity(repo: Path, snapshot: dict, env: dict[str, str]) -> dict[str, str]:
    workflow_commit = env.get("GITHUB_SHA", "")
    if not COMMIT_RE.fullmatch(workflow_commit):
        raise ReleaseStateError("workflow revision is not a full commit ID")
    workflow_commit, version = read_commit(repo, workflow_commit)
    tag = f"v{version}"
    created = env.get("RELEASE_CREATED", "false") == "true"
    if created and (env.get("RELEASE_VERSION") != version or env.get("RELEASE_TAG") != tag
                    or env.get("RELEASE_SHA") != workflow_commit):
        raise ReleaseStateError("release-please identity differs from the tested workflow revision")
    if env.get("DISPATCH_TAG") and env["DISPATCH_TAG"] != tag:
        raise ReleaseStateError("manual recovery tag differs from root version manifest")
    result = {"should_build": "false", "tag": tag, "version": version, "commit": workflow_commit}
    if snapshot.get("status") == "absent" and snapshot.get("release") is None:
        if created:
            raise ReleaseStateError("release-please reported a release but the expected draft is absent")
        return result
    release = snapshot.get("release")
    if snapshot.get("status") != "found" or not isinstance(release, dict):
        raise ReleaseStateError("release snapshot is malformed")
    source = release.get("tag_commit", "")
    if (release.get("tag_name") != tag or not isinstance(source, str)
            or not COMMIT_RE.fullmatch(source)):
        raise ReleaseStateError("release target differs from its immutable tag identity")
    target = release.get("target_commitish")
    if isinstance(target, str) and COMMIT_RE.fullmatch(target) and target.lower() != source.lower():
        raise ReleaseStateError("release target commit differs from its immutable tag identity")
    if created and source != workflow_commit:
        raise ReleaseStateError("new release tag differs from the tested workflow revision")
    source, source_version = read_commit(repo, source)
    if source_version != version:
        raise ReleaseStateError("tagged source version differs from root version manifest")
    ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", source, workflow_commit],
                              cwd=repo, capture_output=True, timeout=20)
    if ancestry.returncode != 0:
        raise ReleaseStateError("release source is not an ancestor of trusted workflow revision")
    if type(release.get("draft")) is not bool:
        raise ReleaseStateError("release draft state is malformed")
    if not release["draft"]:
        if created:
            raise ReleaseStateError("release-please selected a published release")
        return result
    result.update(should_build="true", commit=source)
    return result


def main() -> int:
    try:
        snapshot = load_json(Path(sys.argv[1]))
        if not isinstance(snapshot, dict):
            raise ReleaseStateError("release snapshot is not an object")
        result = resolve_identity(Path.cwd(), snapshot, dict(os.environ))
        print(json.dumps(result, sort_keys=True))
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.writelines(f"{key}={value}\n" for key, value in result.items())
        return 0
    except (ReleaseError, ReleaseStateError, OSError, subprocess.SubprocessError, IndexError) as error:
        print(f"release identity rejected: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
