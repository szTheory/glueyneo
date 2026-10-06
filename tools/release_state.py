#!/usr/bin/env python3
"""Fail-closed validation of staged GitHub draft and downloaded release assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class ReleaseStateError(ValueError):
    """A staged release does not satisfy its immutable identity contract."""


def query_existing_release(api: Any, tag: str, *, release_created: bool) -> dict[str, Any]:
    """Always query by tag, including release-please no-output and retry runs.

    The API adapter is read-only. ``release_created`` is accepted to make the
    recovery condition explicit, but never gates the lookup.
    """
    del release_created
    response = api.get_release_by_tag(tag)
    if response is None:
        return {"status": "absent", "release": None}
    if not isinstance(response, dict):
        raise ReleaseStateError("release API returned a malformed response")
    return {"status": "found", "release": response}


class GitHubReleaseAPI:
    """Small authenticated read-only adapter used to snapshot draft state."""

    def __init__(self, repository: str, token: str, api_url: str = "https://api.github.com"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not token:
            raise ReleaseStateError("repository or API credential is unavailable")
        self.base = api_url.rstrip("/") + f"/repos/{repository}"
        self.token = token

    def _get(self, path: str) -> dict[str, Any] | None:
        request = Request(self.base + path, headers={
            "Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            with urlopen(request, timeout=20) as response:
                value = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 404:
                return None
            raise ReleaseStateError(f"GitHub release API returned HTTP {error.code}") from error
        except (OSError, URLError, UnicodeError, json.JSONDecodeError) as error:
            raise ReleaseStateError("GitHub release API could not be read") from error
        if not isinstance(value, dict):
            raise ReleaseStateError("GitHub release API returned malformed JSON")
        return value

    def get_release_by_tag(self, tag: str) -> dict[str, Any] | None:
        return self._get("/releases/tags/" + quote(tag, safe=""))

    def tag_commit(self, tag: str) -> str:
        ref = self._get("/git/ref/tags/" + quote(tag, safe=""))
        if ref is None:
            raise ReleaseStateError("release tag ref is missing")
        target = ref.get("object")
        for _ in range(5):
            if not isinstance(target, dict) or not isinstance(target.get("sha"), str):
                raise ReleaseStateError("release tag target is malformed")
            if target.get("type") == "commit":
                if not COMMIT_RE.fullmatch(target["sha"]):
                    raise ReleaseStateError("release tag target is not a full commit ID")
                return target["sha"].lower()
            if target.get("type") != "tag":
                raise ReleaseStateError("release tag does not resolve to a commit")
            annotated = self._get("/git/tags/" + quote(target["sha"], safe=""))
            if annotated is None:
                raise ReleaseStateError("annotated release tag object is missing")
            target = annotated.get("object")
        raise ReleaseStateError("release tag nesting exceeds the resolution limit")


def query_github_release(repository: str, token: str, tag: str,
                         api_url: str = "https://api.github.com") -> dict[str, Any]:
    api = GitHubReleaseAPI(repository, token, api_url)
    found = query_existing_release(api, tag, release_created=False)
    if found["status"] == "found":
        found["release"]["tag_commit"] = api.tag_commit(tag)
    return found


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$", re.I)


def required_archive_names(version: str) -> set[str]:
    return {
        f"glueyneo-source-{version}.tar.gz",
        f"glueyneo-sdk-{version}-linux-x86_64.tar.gz",
        f"glueyneo-sdk-{version}-macos-arm64.tar.gz",
        f"glueyneo-sdk-{version}-windows-x86_64.tar.gz",
    }


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseStateError("JSON contains a duplicate key")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseStateError("release metadata could not be read as valid UTF-8 JSON") from error


def _digest(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.removeprefix("sha256:").lower()
    return value if SHA256_RE.fullmatch(value) else None


def _expected_inventory(expected_assets: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not isinstance(expected_assets, dict) or not expected_assets:
        raise ReleaseStateError("expected asset inventory must be a non-empty object")
    result: dict[str, dict[str, Any]] = {}
    for name, record in expected_assets.items():
        if (not isinstance(name, str) or not name or "/" in name or "\\" in name
                or name in {".", ".."} or not isinstance(record, dict)):
            raise ReleaseStateError("expected asset inventory contains an invalid record")
        size, digest = record.get("size"), _digest(record.get("sha256"))
        if type(size) is not int or size < 0 or digest is None:
            raise ReleaseStateError("expected asset inventory contains an invalid size or SHA-256")
        result[name] = {"size": size, "sha256": digest}
    return result


def validate_release(
    release: dict[str, Any], *, expected_tag: str, expected_version: str,
    expected_commit: str, manifest_version: str,
    expected_assets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Classify an existing draft without performing API mutations.

    A verified subset is resumable, but only an exact complete draft is publishable.
    ``tag_commit`` must be resolved from the repository's tag ref API, not inferred
    from the release object's mutable ``target_commitish`` field.
    """
    try:
        if not isinstance(release, dict):
            raise ReleaseStateError("release response is not an object")
        inventory = _expected_inventory(expected_assets)
        if not COMMIT_RE.fullmatch(expected_commit or ""):
            raise ReleaseStateError("tested commit must be a full immutable object ID")
        if (manifest_version != expected_version or expected_tag != f"v{expected_version}"
                or release.get("tag_name") != expected_tag):
            raise ReleaseStateError("release tag, expected version, and manifest version disagree")
        if set(inventory) != required_archive_names(expected_version) | {"release-manifest.json"}:
            raise ReleaseStateError("release asset allowlist differs from the exact archive and manifest set")
        tag_commit = release.get("tag_commit")
        if not isinstance(tag_commit, str) or tag_commit.lower() != expected_commit.lower():
            raise ReleaseStateError("release tag does not target the tested versioned commit")
        target = release.get("target_commitish")
        if isinstance(target, str) and COMMIT_RE.fullmatch(target) and target.lower() != expected_commit.lower():
            raise ReleaseStateError("release target commit differs from the tested commit")
        if release.get("draft") is not True or release.get("prerelease") is True:
            raise ReleaseStateError("release is published or is not an unpublished draft")
        assets = release.get("assets")
        if not isinstance(assets, list):
            raise ReleaseStateError("release asset response is not a list")
        observed: dict[str, dict[str, Any]] = {}
        for asset in assets:
            if not isinstance(asset, dict):
                raise ReleaseStateError("release contains a malformed asset")
            name = asset.get("name")
            if not isinstance(name, str) or name in observed:
                raise ReleaseStateError("release contains a missing or duplicate asset name")
            if name not in inventory:
                raise ReleaseStateError("release contains an unexpected asset")
            size, digest = asset.get("size"), _digest(asset.get("digest", asset.get("sha256")))
            if asset.get("state", "uploaded") != "uploaded":
                raise ReleaseStateError("release contains an asset that is not fully uploaded")
            if type(size) is not int or digest is None:
                raise ReleaseStateError("release asset has no valid size or SHA-256")
            if size != inventory[name]["size"] or digest != inventory[name]["sha256"]:
                raise ReleaseStateError("existing release asset bytes differ from staged bytes")
            observed[name] = {"size": size, "sha256": digest}
        missing = sorted(set(inventory) - set(observed))
        ready = not missing
        return {"status": "ready" if ready else "resume", "publishable": ready,
                "missing_assets": missing, "verified_assets": sorted(observed),
                "error": None}
    except ReleaseStateError as error:
        return {"status": "reject", "publishable": False, "missing_assets": [],
                "verified_assets": [], "error": str(error)}


def validate_downloaded_assets(directory: Path, manifest_path: Path) -> dict[str, Any]:
    """Verify exact downloaded release bytes against a trusted staged manifest."""
    manifest = load_json(manifest_path)
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
            or not isinstance(manifest.get("version"), str)
            or not isinstance(manifest.get("source_commit"), str)
            or not COMMIT_RE.fullmatch(manifest["source_commit"])
            or manifest.get("tag") != f"v{manifest['version']}"):
        raise ReleaseStateError("release asset manifest identity is malformed")
    rows = manifest.get("assets")
    if not isinstance(rows, list) or not rows:
        raise ReleaseStateError("release asset manifest inventory is empty or malformed")
    expected: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"name", "size", "sha256"}:
            raise ReleaseStateError("release asset manifest row is malformed")
        name = row["name"]
        if not isinstance(name, str) or name in expected:
            raise ReleaseStateError("release asset manifest has a duplicate or invalid name")
        expected[name] = {"size": row["size"], "sha256": row["sha256"]}
    expected = _expected_inventory(expected)
    if set(expected) != required_archive_names(manifest["version"]):
        raise ReleaseStateError("download manifest does not list the exact required archive set")
    try:
        entries = list(directory.iterdir())
    except OSError as error:
        raise ReleaseStateError("downloaded release asset directory could not be read") from error
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise ReleaseStateError("downloaded release asset directory contains a link or non-file")
    actual_names = {entry.name for entry in entries}
    if actual_names != set(expected) | {"release-manifest.json"}:
        raise ReleaseStateError("downloaded release asset names differ from the manifest")
    downloaded_manifest = directory / "release-manifest.json"
    if downloaded_manifest.resolve() != manifest_path.resolve():
        try:
            identical = downloaded_manifest.read_bytes() == manifest_path.read_bytes()
        except OSError as error:
            raise ReleaseStateError("downloaded release manifest could not be read") from error
        if not identical:
            raise ReleaseStateError("downloaded release manifest differs from the staged identity")
    verified = []
    for name, record in expected.items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ReleaseStateError("downloaded release asset is not a regular file")
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    size += len(block)
                    digest.update(block)
        except OSError as error:
            raise ReleaseStateError("downloaded release asset could not be read") from error
        if size != record["size"] or digest.hexdigest() != record["sha256"]:
            raise ReleaseStateError("downloaded release asset bytes differ from the manifest")
        verified.append(name)
    return {"outcome": "pass", "source_commit": manifest["source_commit"],
            "version": manifest["version"], "assets": sorted(verified)}


def expected_api_assets(manifest_path: Path) -> dict[str, dict[str, Any]]:
    """Build the exact API asset allowlist, including the manifest's own bytes."""
    manifest = load_json(manifest_path)
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
            or not isinstance(manifest.get("version"), str)
            or not isinstance(manifest.get("source_commit"), str)
            or not COMMIT_RE.fullmatch(manifest["source_commit"])):
        raise ReleaseStateError("release asset manifest identity is malformed")
    if manifest.get("tag") != f"v{manifest['version']}":
        raise ReleaseStateError("release tag and version in the asset manifest disagree")
    rows = manifest.get("assets")
    if not isinstance(rows, list) or not rows:
        raise ReleaseStateError("release asset manifest inventory is empty or malformed")
    expected: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"name", "size", "sha256"}:
            raise ReleaseStateError("release asset manifest row is malformed")
        name = row["name"]
        if not isinstance(name, str) or name in expected:
            raise ReleaseStateError("release asset manifest has a duplicate or invalid name")
        expected[name] = {"size": row["size"], "sha256": row["sha256"]}
    expected = _expected_inventory(expected)
    if set(expected) != required_archive_names(manifest["version"]):
        raise ReleaseStateError("release asset manifest does not list the exact required archive set")
    payload = manifest_path.read_bytes()
    expected["release-manifest.json"] = {
        "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()
    }
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    draft = sub.add_parser("validate-draft")
    draft.add_argument("--release", type=Path, required=True)
    draft.add_argument("--manifest", type=Path, required=True)
    draft.add_argument("--tag", required=True)
    draft.add_argument("--version", required=True)
    draft.add_argument("--commit", required=True)
    query = sub.add_parser("query-api")
    query.add_argument("--repository", required=True)
    query.add_argument("--tag", required=True)
    query.add_argument("--output", type=Path, required=True)
    downloaded = sub.add_parser("verify-download")
    downloaded.add_argument("--directory", type=Path, required=True)
    downloaded.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "query-api":
            # The token is read from the environment and never included in output.
            result = query_github_release(args.repository, os.environ.get("GH_TOKEN", ""),
                                          args.tag, os.environ.get("GH_API_URL", "https://api.github.com"))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
                                   encoding="utf-8")
            print(json.dumps({"status": result["status"]}, separators=(",", ":")))
            return 0
        if args.command == "validate-draft":
            manifest = load_json(args.manifest)
            if (not isinstance(manifest, dict) or manifest.get("version") != args.version
                    or manifest.get("source_commit", "").lower() != args.commit.lower()
                    or manifest.get("tag") != args.tag):
                raise ReleaseStateError("staged manifest differs from the release identity")
            result = validate_release(
                load_json(args.release), expected_tag=args.tag, expected_version=args.version,
                expected_commit=args.commit, manifest_version=manifest["version"],
                expected_assets=expected_api_assets(args.manifest),
            )
            print(json.dumps(result, sort_keys=True, separators=(",", ":")))
            return 1 if result["status"] == "reject" else 0
        result = validate_downloaded_assets(args.directory, args.manifest)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ReleaseStateError, ValueError) as error:
        print(json.dumps({"outcome": "fail", "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
