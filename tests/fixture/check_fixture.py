#!/usr/bin/env python3
"""Verify public fixture provenance, rights, and deterministic generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_OUTPUT = "public-playable.bin"


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


def validate_rights(rights: dict, source_arg: Path, artifact_arg: Path,
                    *, check_artifact_path: bool = True) -> dict:
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
    if (check_artifact_path
            and artifact.get("path") != artifact_arg.relative_to(ROOT).as_posix()):
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


def validate_cmake(source: Path, artifact_path: str) -> None:
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    pattern = re.compile(
        r"add_custom_command\s*\(\s*OUTPUT\s+\"\$\{GLUEYNEO_PUBLIC_FIXTURE\}\"(?P<body>.*?)\n\s*\)",
        re.DOTALL,
    )
    commands = list(pattern.finditer(cmake))
    if len(commands) != 1:
        raise CheckError("CMake must have exactly one public fixture output producer")
    body = commands[0].group("body")
    generator = body.find("$<TARGET_FILE:public_guest_test> --write-fixture")
    source_dependency = body.find("DEPENDS public_guest_test tests/fixture/public_guest.c")
    if generator < 0 or source_dependency < generator:
        raise CheckError("fixture producer or explicit tracked source dependency is missing")
    if cmake.count('"${CMAKE_CURRENT_BINARY_DIR}/public-playable.bin"') != 1:
        raise CheckError("CMake must declare one canonical public-playable.bin output path")
    if cmake.count("add_custom_target(glueyneo-public-fixture ALL") != 1:
        raise CheckError("named fixture build target must have exactly one declaration")
    if 'COMMAND public_guest_test "${GLUEYNEO_PUBLIC_FIXTURE}"' not in cmake:
        raise CheckError("native consumer does not use the generated artifact variable")
    expected = artifact_path.replace("\\", "/")
    expected_build_dir = expected.rsplit("/", 1)[0]
    if not expected.endswith("/public-playable.bin"):
        raise CheckError("artifact path does not name the canonical CMake output")
    if not expected_build_dir:
        raise CheckError("artifact path does not identify its CMake build directory")

    smoke = (ROOT / "tests/libretro/retroarch_smoke.py").read_text(encoding="utf-8")
    if ('parser.add_argument("--content", type=Path, required=True' not in smoke
            or 'content = args.content.resolve()' not in smoke
            or 'str(content)' not in smoke):
        raise CheckError("RetroArch consumer does not load the supplied fixture path")
    for tracked in (source, ROOT / "tests/fixture/test_public_guest.c",
                    ROOT / "CMakeLists.txt", ROOT / "tests/libretro/retroarch_smoke.py"):
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(tracked.relative_to(ROOT))],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if result.returncode:
            raise CheckError("generator, assertion, or consumer dependency is not tracked")


def regenerate(artifact: Path) -> str:
    if artifact.name != EXPECTED_OUTPUT:
        raise CheckError("artifact basename must match the CMake output")
    artifact.unlink(missing_ok=True)
    subprocess.run(
        ["cmake", "--build", str(artifact.parent), "--target", "glueyneo-public-fixture"],
        cwd=ROOT, check=True,
    )
    if not artifact.is_file():
        raise CheckError("named CMake target did not regenerate the fixture")
    return sha256(artifact)


def check_negative_control(args: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(
        prefix="fixture-negative-", dir=args.artifact.parent
    ) as temporary:
        mutated = Path(temporary) / EXPECTED_OUTPUT
        data = bytearray(args.artifact.read_bytes())
        data[-1] ^= 1
        mutated.write_bytes(data)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()),
             "--source", str(args.source.relative_to(ROOT)),
             "--artifact", str(mutated.relative_to(ROOT)),
             "--rights", str(args.rights.relative_to(ROOT)),
             "--skip-artifact-path-check"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if (result.returncode == 0
                or "generated artifact SHA-256 differs from the record" not in result.stderr):
            raise CheckError("negative control was not rejected by the recorded artifact digest")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="repository-relative guest C source")
    parser.add_argument("--artifact", required=True, help="repository-relative generated fixture")
    parser.add_argument("--rights", required=True, help="repository-relative rights manifest")
    parser.add_argument("--check-rebuild", action="store_true")
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--skip-artifact-path-check", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        args.source = repo_path(args.source)
        args.artifact = repo_path(args.artifact)
        args.rights = repo_path(args.rights)
        rights = read_json(args.rights)
        artifact = validate_rights(
            rights, args.source, args.artifact,
            check_artifact_path=not args.skip_artifact_path_check,
        )
        validate_cmake(args.source, artifact["path"])
        if args.check_rebuild:
            first = regenerate(args.artifact)
            second = regenerate(args.artifact)
            if first != second or first != artifact["sha256"]:
                raise CheckError("two named-target regenerations differ from the recorded output")
        if args.negative_control:
            check_negative_control(args)
    except (CheckError, OSError, subprocess.CalledProcessError) as error:
        print(f"fixture check failed: {error}", file=sys.stderr)
        return 1
    print("fixture identities, affirmative rights, single producer, and shared consumer path passed")
    if args.check_rebuild:
        print("two named-target regenerations matched the recorded artifact digest and length")
    if args.negative_control:
        print("mutated artifact was rejected by the digest check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
