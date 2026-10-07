#!/usr/bin/env python3
"""Verify public fixture provenance, rights, and deterministic generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CheckError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise CheckError("paths must be repository-relative")
    result = (ROOT / path).resolve()
    if ROOT not in result.parents:
        raise CheckError("path resolves outside the repository")
    return result


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CheckError("rights manifest is unreadable or invalid JSON") from error
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise CheckError("rights manifest schema is not supported")
    return value


def assert_file_identity(record: dict, label: str, *, check_size: bool = False) -> Path:
    if not isinstance(record, dict) or not isinstance(record.get("path"), str):
        raise CheckError(f"{label} identity is missing its path")
    path = repo_path(record["path"])
    if not path.is_file() or path.is_symlink():
        raise CheckError(f"{label} source is missing or is a symlink")
    if record.get("sha256") != sha256(path):
        raise CheckError(f"{label} SHA-256 does not match the recorded identity")
    if check_size and record.get("bytes") != path.stat().st_size:
        raise CheckError(f"{label} byte length does not match the recorded identity")
    return path


def validate_private_paths() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    paths = [entry.decode("utf-8", "strict") for entry in result.stdout.split(b"\0") if entry]
    forbidden = re.compile(
        r"(?i)(?:^|/)(?:local/roms|private-media|private-captures)(?:/|$)"
    )
    media_suffix = re.compile(r"(?i)\.(?:zip|7z|chd|cue|iso|neo|aes|mvs|bios|rom)$")
    for value in paths:
        if forbidden.search(value):
            raise CheckError("tracked or unignored private-media path is present")
        if value.startswith("tests/fixture/") and media_suffix.search(value):
            raise CheckError("private-media or binary fixture path is present under tests/fixture")


def validate_rights(rights: dict, source_arg: Path, artifact_arg: Path) -> dict:
    if rights.get("fixture") != "GNFX v1 public playable tracer":
        raise CheckError("rights manifest does not identify the expected fixture")
    source = rights.get("source", {})
    if source.get("path") != source_arg.relative_to(ROOT).as_posix():
        raise CheckError("source argument differs from the rights manifest")
    assert_file_identity(source, "guest source", check_size=True)
    assert_file_identity(rights.get("assertions", {}), "assertion source")
    assert_file_identity(rights.get("oracle_document", {}), "oracle document")

    rights_record = rights.get("rights", {})
    if (rights_record.get("status") != "affirmative"
            or rights_record.get("license") != "MIT"
            or rights_record.get("notice") != "LICENSE"
            or rights_record.get("third_party_guest_bytes") is not False
            or rights_record.get("game_rom_or_bios_bytes") is not False
            or rights_record.get("private_media_or_derived_output") is not False):
        raise CheckError("fixture rights are not affirmative or exclude private media")
    notice = ROOT / "LICENSE"
    if not notice.is_file() or "MIT License" not in notice.read_text(encoding="utf-8"):
        raise CheckError("affirmative MIT notice is absent")
    if rights.get("assets", {}).get("embedded_external_assets") != []:
        raise CheckError("fixture declares an unreviewed external asset")

    artifact = rights.get("artifact", {})
    if artifact.get("path") != artifact_arg.relative_to(ROOT).as_posix():
        raise CheckError("artifact argument differs from the recorded artifact path")
    if not artifact_arg.is_file() or artifact_arg.is_symlink():
        raise CheckError("generated artifact is missing or is a symlink")
    if artifact.get("bytes") != artifact_arg.stat().st_size:
        raise CheckError("generated artifact byte length differs from the record")
    if artifact.get("sha256") != sha256(artifact_arg):
        raise CheckError("generated artifact SHA-256 differs from the record")
    if rights.get("oracle", {}).get("hardware_truth_established") is not False:
        raise CheckError("oracle record must leave hardware truth unestablished")
    if rights.get("generator", {}).get("external_generator_dependencies") != []:
        raise CheckError("fixture generator has an unreviewed external dependency")
    validate_private_paths()
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="repository-relative guest C source")
    parser.add_argument("--artifact", required=True, help="repository-relative generated fixture")
    parser.add_argument("--rights", required=True, help="repository-relative rights manifest")
    args = parser.parse_args()
    try:
        args.source = repo_path(args.source)
        args.artifact = repo_path(args.artifact)
        args.rights = repo_path(args.rights)
        rights = read_json(args.rights)
        validate_rights(rights, args.source, args.artifact)
    except (CheckError, OSError, subprocess.CalledProcessError) as error:
        print(f"fixture check failed: {error}", file=sys.stderr)
        return 1
    print("fixture source/artifact identities and affirmative rights passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
