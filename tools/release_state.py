#!/usr/bin/env python3
"""Fail-closed validation of staged GitHub draft and downloaded release assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


class ReleaseStateError(ValueError):
    """A staged release does not satisfy its immutable identity contract."""


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$", re.I)


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
            or not COMMIT_RE.fullmatch(manifest["source_commit"])):
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
    try:
        actual_names = {entry.name for entry in directory.iterdir() if entry.is_file()}
    except OSError as error:
        raise ReleaseStateError("downloaded release asset directory could not be read") from error
    if actual_names != set(expected):
        raise ReleaseStateError("downloaded release asset names differ from the manifest")
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    downloaded = sub.add_parser("verify-download")
    downloaded.add_argument("--directory", type=Path, required=True)
    downloaded.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate_downloaded_assets(args.directory, args.manifest)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ReleaseStateError, ValueError) as error:
        print(json.dumps({"outcome": "fail", "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
