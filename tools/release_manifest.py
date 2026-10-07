#!/usr/bin/env python3
"""Create deterministic offline source and installed SDK release archives."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile


VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?(?:\+[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$")
SOURCE_PATHS = (
    ".release-please-manifest.json",
    "CMakeLists.txt",
    "CMakePresets.json",
    "LICENSE",
    "README.md",
    "cmake",
    "docs",
    "examples",
    "experiments/owned_cpu",
    "fixtures/diagnostic",
    "include",
    "src",
    "tests",
    "third_party/unity",
    "tools/diagnostic",
    "tools/release_manifest.py",
    "tools/release_state.py",
)
MAX_MEMBERS = 50_000
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024


class ReleaseError(RuntimeError):
    """A release artifact failed a named integrity or build check."""


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(argv: list[str], *, cwd: Path, timeout: int = 300) -> str:
    try:
        result = subprocess.run(
            argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout, check=False,
            env={key: value for key, value in os.environ.items()
                 if key not in {"CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS",
                                "CMAKE_PREFIX_PATH", "CMAKE_MODULE_PATH",
                                "CMAKE_TOOLCHAIN_FILE", "CMAKE_PROJECT_INCLUDE",
                                "CMAKE_PROJECT_INCLUDE_BEFORE", "CMAKE_GENERATOR"}},
        )
    except subprocess.TimeoutExpired as error:
        raise ReleaseError(f"Timed out running {' '.join(argv)}") from error
    if result.returncode:
        raise ReleaseError(f"Command failed ({result.returncode}): {' '.join(argv)}\n{result.stdout[-12000:]}")
    return result.stdout


def manifest_version(raw: bytes) -> str:
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ReleaseError("release-please manifest contains a duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseError("release-please manifest is not valid UTF-8 JSON") from error
    if not isinstance(value, dict) or set(value) != {"."} or not isinstance(value["."], str):
        raise ReleaseError("release-please manifest must contain only the root package key '.'")
    if not VERSION_RE.fullmatch(value["."]):
        raise ReleaseError("release-please manifest root version is malformed")
    return value["."]


def validate_members(archive: Path) -> list[tarfile.TarInfo]:
    try:
        if archive.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ReleaseError("compressed archive exceeds the input size limit")
    except OSError as error:
        raise ReleaseError(f"archive cannot be read: {archive.name}") from error
    try:
        with tarfile.open(archive, "r:gz") as stream:
            members = stream.getmembers()
    except (OSError, tarfile.TarError) as error:
        raise ReleaseError(f"archive cannot be read as gzip tar: {archive.name}") from error
    if len(members) == 0 or len(members) > MAX_MEMBERS:
        raise ReleaseError("archive member count is empty or exceeds the limit")
    names: set[str] = set()
    total = 0
    for member in members:
        name = member.name
        path = PurePosixPath(name)
        if (not name or "\\" in name or "\x00" in name or path.is_absolute()
                or any(part in {"", ".", ".."} for part in name.split("/"))
                or re.match(r"^[A-Za-z]:", name)):
            raise ReleaseError(f"unsafe archive member path: {name!r}")
        if name in names:
            raise ReleaseError(f"duplicate archive member: {name!r}")
        names.add(name)
        if member.isdir():
            continue
        if not member.isfile():
            raise ReleaseError(f"archive member is not a regular file or directory: {name!r}")
        if member.size < 0 or member.size > MAX_MEMBER_BYTES:
            raise ReleaseError(f"archive member exceeds the per-file size limit: {name!r}")
        total += member.size
        if total > MAX_ARCHIVE_BYTES:
            raise ReleaseError("archive exceeds the total uncompressed size limit")
    return members


def safe_extract(archive: Path, destination: Path) -> list[tarfile.TarInfo]:
    members = validate_members(archive)
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(archive, "r:gz") as stream:
        for member in members:
            output = destination.joinpath(*PurePosixPath(member.name).parts)
            if output.resolve().parent != root and root not in output.resolve().parents:
                raise ReleaseError(f"archive member escapes extraction root: {member.name!r}")
            if member.isdir():
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            source = stream.extractfile(member)
            if source is None:
                raise ReleaseError(f"archive member has no file body: {member.name!r}")
            with source, output.open("xb") as target:
                copied = 0
                while block := source.read(1024 * 1024):
                    copied += len(block)
                    if copied > member.size or copied > MAX_MEMBER_BYTES:
                        raise ReleaseError(f"archive member body exceeds its declared size: {member.name!r}")
                    target.write(block)
                if copied != member.size:
                    raise ReleaseError(f"archive member body is truncated: {member.name!r}")
            output.chmod(0o755 if member.mode & 0o111 else 0o644)
    return members


def write_archive(directory: Path, archive: Path, prefix: str) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for path in sorted(directory.rglob("*"), key=lambda item: item.as_posix()):
                relative = path.relative_to(directory).as_posix()
                archive_name = f"{prefix.rstrip('/')}/{relative}" if prefix else relative
                info = tarfile.TarInfo(archive_name)
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                if path.is_symlink():
                    raise ReleaseError(f"release trees cannot contain links: {relative}")
                if path.is_dir():
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    info.size = 0
                    tar.addfile(info)
                elif path.is_file():
                    info.type = tarfile.REGTYPE
                    info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                    info.size = path.stat().st_size
                    with path.open("rb") as body:
                        tar.addfile(info, body)
                else:
                    raise ReleaseError(f"release tree contains an unsupported file: {relative}")


def write_digest(archive: Path) -> None:
    archive.with_suffix(archive.suffix + ".sha256").write_text(
        f"{sha256_file(archive)}  {archive.name}\n", encoding="ascii"
    )


def write_release_manifest(directory: Path, commit: str, version: str, repo: Path = Path.cwd()) -> Path:
    """Create a canonical manifest for all four versioned release archives."""
    resolved, committed_version = read_commit(repo, commit)
    if committed_version != version:
        raise ReleaseError("release manifest version differs from the tested commit manifest")
    names = sorted((f"glueyneo-source-{version}.tar.gz",
                    f"glueyneo-sdk-{version}-linux-x86_64.tar.gz",
                    f"glueyneo-sdk-{version}-macos-arm64.tar.gz",
                    f"glueyneo-sdk-{version}-windows-x86_64.tar.gz"))
    assets = []
    for name in names:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ReleaseError(f"required release archive is missing or unsafe: {name}")
        assets.append({"name": name, "size": path.stat().st_size, "sha256": sha256_file(path)})
    manifest = {"schema_version": 1, "tag": f"v{version}", "source_commit": resolved,
                "version": version, "assets": assets}
    destination = directory / "release-manifest.json"
    destination.write_bytes(canonical_json(manifest))
    return destination


def read_commit(repo: Path, commit: str) -> tuple[str, str]:
    if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit) is None:
        raise ReleaseError("release commit must be a full immutable Git object ID")
    resolved = run(["git", "rev-parse", "--verify", f"{commit}^{{commit}}"], cwd=repo).strip()
    if resolved.lower() != commit.lower():
        raise ReleaseError("resolved release commit differs from the requested full object ID")
    raw = subprocess.run(
        ["git", "show", f"{resolved}:.release-please-manifest.json"], cwd=repo,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30,
    )
    if raw.returncode:
        raise ReleaseError("release commit has no root release-please manifest")
    return resolved, manifest_version(raw.stdout)


def build_archives(repo: Path, commit: str, output_dir: Path) -> dict[str, object]:
    repo = repo.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    commit, version = read_commit(repo, commit)
    source_name = f"glueyneo-source-{version}.tar.gz"
    system = {"darwin": "macos", "windows": "windows"}.get(platform.system().lower(), platform.system().lower())
    machine = {"amd64": "x86_64", "x86-64": "x86_64", "aarch64": "arm64"}.get(
        platform.machine().lower(), platform.machine().lower())
    sdk_name = f"glueyneo-sdk-{version}-{system}-{machine}.tar.gz"
    source_archive = output_dir / source_name
    sdk_archive = output_dir / sdk_name

    with tempfile.TemporaryDirectory(prefix="glueyneo-release-") as temp_name:
        work = Path(temp_name)
        raw_tar = work / "source.tar"
        archive = subprocess.run(
            ["git", "archive", "--format=tar", f"--prefix=glueyneo-source/", commit, *SOURCE_PATHS],
            cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60,
        )
        if archive.returncode:
            raise ReleaseError(f"git archive failed: {archive.stderr.decode(errors='replace')}")
        raw_tar.write_bytes(archive.stdout)
        # Repackage members with normalized ownership and timestamps.
        safe_extract_raw_tar(raw_tar, work / "source-tree")
        write_archive(work / "source-tree", source_archive, "")
        write_digest(source_archive)

        extracted = work / "extracted-source"
        safe_extract(source_archive, extracted)
        source_root = extracted / "glueyneo-source"
        sdk_root = work / "sdk-tree"
        sdk_root.mkdir()
        for variant, shared in (("static", "OFF"), ("shared", "ON")):
            build = work / f"build-{variant}"
            prefix = sdk_root / variant
            cmake = shutil.which("cmake")
            if cmake is None:
                raise ReleaseError("CMake is required to build the release SDK")
            run([cmake, "-S", str(source_root), "-B", str(build),
                 "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=OFF",
                 "-DGLUEYNEO_BUILD_TESTS=OFF", f"-DBUILD_SHARED_LIBS={shared}",
                 f"-DCMAKE_INSTALL_PREFIX={prefix}"], cwd=source_root)
            build_command = [cmake, "--build", str(build), "--parallel", "2"]
            install_command = [cmake, "--install", str(build)]
            if platform.system() == "Windows":
                # Visual Studio is a multi-config generator; CMAKE_BUILD_TYPE is ignored.
                build_command.extend(["--config", "Release"])
                install_command.extend(["--config", "Release"])
            run(build_command, cwd=source_root)
            run(install_command, cwd=source_root)
        shutil.copy2(source_root / "README.md", sdk_root / "README.md")
        shutil.copy2(source_root / "LICENSE", sdk_root / "LICENSE")
        (sdk_root / "licenses").mkdir()
        shutil.copy2(source_root / "third_party/unity/LICENSE.txt", sdk_root / "licenses/Unity-LICENSE.txt")
        example = sdk_root / "consumer-example"
        (example / "source").mkdir(parents=True)
        shutil.copy2(source_root / "tests/consumers/CMakeLists.txt", example / "source/CMakeLists.txt")
        shutil.copy2(source_root / "tests/consumers/header.cpp", example / "source/header.cpp")
        shutil.copy2(source_root / "examples/diagnostic.c", example / "source/diagnostic.c")
        installed_files = [p for p in sorted(sdk_root.rglob("*")) if p.is_file()]
        assets = [{"path": p.relative_to(sdk_root).as_posix(), "size": p.stat().st_size,
                   "sha256": sha256_file(p)} for p in installed_files]
        cache = (work / "build-static" / "CMakeCache.txt").read_text(encoding="utf-8")
        compiler_match = re.search(r"^CMAKE_C_COMPILER:FILEPATH=(.*)$", cache, re.MULTILINE)
        compiler_id_file = next((work / "build-static/CMakeFiles").glob("*/CMakeCCompiler.cmake"), None)
        compiler_data = compiler_id_file.read_text(encoding="utf-8") if compiler_id_file else ""
        compiler_id = re.search(r'set\(CMAKE_C_COMPILER_ID "([^"]*)"\)', compiler_data)
        compiler_version = re.search(r'set\(CMAKE_C_COMPILER_VERSION "([^"]*)"\)', compiler_data)
        if not (compiler_match and compiler_id and compiler_version):
            raise ReleaseError("generated build does not provide compiler identity")
        cmake_version = run([cmake, "--version"], cwd=source_root).splitlines()[0]
        manifest = {
            "schema_version": 1,
            "source_commit": commit,
            "version": version,
            "platform": platform.system(),
            "architecture": platform.machine(),
            "configuration": "Release",
            "cmake": cmake_version,
            "compiler": {"path_basename": Path(compiler_match.group(1)).name,
                         "id": compiler_id.group(1), "version": compiler_version.group(1)},
            "source_archive": {"name": source_name, "sha256": sha256_file(source_archive)},
            "assets": assets,
        }
        (sdk_root / "artifact-manifest.json").write_bytes(canonical_json(manifest))
        write_archive(sdk_root, sdk_archive, f"glueyneo-sdk-{version}")
        write_digest(sdk_archive)
    return {"source": source_name, "sdk": sdk_name, "commit": commit, "version": version,
            "source_sha256": sha256_file(source_archive), "sdk_sha256": sha256_file(sdk_archive)}


def safe_extract_raw_tar(archive: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive, "r:") as stream:
            members = stream.getmembers()
            validate_member_info(members)
            stream.extractall(destination, members=members)
    except (OSError, tarfile.TarError) as error:
        raise ReleaseError(f"source tree archive is invalid: {archive.name}") from error


def validate_member_info(members: list[tarfile.TarInfo]) -> None:
    if not members or len(members) > MAX_MEMBERS:
        raise ReleaseError("archive member count is empty or exceeds the limit")
    seen: set[str] = set()
    total = 0
    for member in members:
        name = member.name
        path = PurePosixPath(name)
        if (not name or "\\" in name or "\x00" in name or path.is_absolute()
                or any(part in {"", ".", ".."} for part in name.split("/"))
                or re.match(r"^[A-Za-z]:", name)):
            raise ReleaseError(f"unsafe archive member path: {name!r}")
        if name in seen:
            raise ReleaseError(f"duplicate archive member: {name!r}")
        seen.add(name)
        if member.isdir():
            continue
        if not member.isfile():
            raise ReleaseError(f"archive member is not a regular file or directory: {name!r}")
        if member.size < 0 or member.size > MAX_MEMBER_BYTES:
            raise ReleaseError(f"archive member exceeds the per-file size limit: {name!r}")
        total += member.size
        if total > MAX_ARCHIVE_BYTES:
            raise ReleaseError("archive exceeds the total uncompressed size limit")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build exact-commit source and local-host SDK archives")
    build.add_argument("--commit", required=True, help="full immutable Git commit ID")
    build.add_argument("--repo", type=Path, default=Path.cwd())
    build.add_argument("--output-dir", type=Path, required=True)
    release_manifest_cmd = subparsers.add_parser("release-manifest", help="manifest the four staged release archives")
    release_manifest_cmd.add_argument("--commit", required=True)
    release_manifest_cmd.add_argument("--version", required=True)
    release_manifest_cmd.add_argument("--repo", type=Path, default=Path.cwd())
    release_manifest_cmd.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build_archives(args.repo, args.commit, args.output_dir)
            print(json.dumps({"outcome": "pass", **result}, sort_keys=True))
        elif args.command == "release-manifest":
            resolved, version = read_commit(args.repo, args.commit)
            if args.version != version:
                raise ReleaseError("requested release version differs from the tested commit manifest")
            output = write_release_manifest(args.output_dir, resolved, version, args.repo)
            print(json.dumps({"outcome": "pass", "manifest": output.name,
                              "commit": resolved, "version": version}, sort_keys=True))
    except (OSError, ReleaseError, ValueError) as error:
        print(f"RELEASE_MANIFEST {{\"outcome\":\"fail\",\"error\":{json.dumps(str(error))}}}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
