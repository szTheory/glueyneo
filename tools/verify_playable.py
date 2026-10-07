#!/usr/bin/env python3
"""Clean-build and qualify the public playable tracer on the selected host.

The receipt and command logs are generated under ignored build/ and contain no
private content. An unavailable frontend or candidate gate remains unknown and
fails the aggregate result; mocks never count as evidence.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import plistlib
import posixpath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unicodedata
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "playable-qualification"
FIXTURE_SHA256 = "59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0"
YMFM_REVISION = "81aec25ccbb98f4873a255f7551ac4dadac59b4a"
Z80_REVISION = "9e88298ce56319953ac7a43213a1120359f7a3a6"
INVENTORY_SCHEMA = "glueyneo.source-inventory/v1"
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


class SnapshotError(RuntimeError):
    """A named fail-closed error while identifying or validating source bytes."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


@dataclass(frozen=True)
class SourceSnapshot:
    root: Path
    commit: str
    inventory: tuple[dict[str, Any], ...]
    digest: str
    archive_sha256: str


def clean_environment() -> dict[str, str]:
    """Keep host tool discovery while dropping build, loader, and Python injection."""
    blocked = {
        "CC", "CXX", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS",
        "CMAKE_PREFIX_PATH", "CMAKE_MODULE_PATH", "CMAKE_TOOLCHAIN_FILE",
        "CMAKE_PROJECT_INCLUDE", "CMAKE_PROJECT_INCLUDE_BEFORE", "CMAKE_GENERATOR",
        "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH",
        "LIBRARY_PATH", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH",
        "DYLD_INSERT_LIBRARIES", "PKG_CONFIG_PATH", "PKG_CONFIG_LIBDIR",
        "PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "GIT_DIR", "GIT_WORK_TREE",
        "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR", "GIT_CEILING_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_COUNT",
        "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_GLOBAL", "GIT_ATTR_NOSYSTEM",
    }
    environment = {
        key: value for key, value in os.environ.items()
        if key not in blocked and not key.startswith(("CMAKE_", "GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_TRACE"))
    }
    path_entries = []
    for entry in environment.get("PATH", "").split(os.pathsep):
        candidate = Path(entry or os.curdir).resolve()
        if candidate == ROOT or ROOT in candidate.parents:
            continue
        path_entries.append(entry)
    environment["PATH"] = os.pathsep.join(path_entries)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_ATTR_NOSYSTEM"] = "1"
    return environment


def _git(repository: Path, arguments: list[str]) -> bytes:
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=repository, env=clean_environment(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SnapshotError("git-archive-failed", f"Git source snapshot command failed ({type(error).__name__})") from error
    if result.returncode != 0:
        raise SnapshotError("git-archive-failed", "Git could not resolve or archive the committed source")
    return result.stdout


def _commit_id(repository: Path, revision: str) -> str:
    output = _git(repository, ["rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"])
    commit = output.decode("ascii", errors="strict").strip()
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
        raise SnapshotError("invalid-source-commit", "Git did not return a full immutable commit ID")
    return commit


def _safe_repo_path(path: str) -> str:
    if (not path or path.startswith("/") or "\\" in path or
            unicodedata.normalize("NFC", path) != path or
            any(ord(character) < 32 or ord(character) == 127 for character in path)):
        raise SnapshotError("unsafe-archive-path", "source archive contains a non-portable or ambiguous path")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise SnapshotError("unsafe-archive-path", "source archive contains a non-canonical path")
    return path


def _expected_tree(repository: Path, commit: str) -> dict[str, str]:
    raw = _git(repository, ["ls-tree", "-rz", "--full-tree", commit])
    expected: dict[str, str] = {}
    folded: dict[str, str] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path_bytes = record.split(b"\t", 1)
            mode, object_type, _object_id = metadata.decode("ascii").split(" ")
            path = _safe_repo_path(path_bytes.decode("utf-8", errors="strict"))
        except (ValueError, UnicodeDecodeError) as error:
            raise SnapshotError("ambiguous-source-tree", "committed source tree has an ambiguous entry") from error
        for prefix in _path_prefixes(path):
            folded_path = prefix.casefold()
            if folded_path in folded and folded[folded_path] != prefix:
                raise SnapshotError("ambiguous-source-tree", "committed source tree has case-colliding paths")
            folded[folded_path] = prefix
        if path in expected:
            raise SnapshotError("ambiguous-source-tree", "committed source tree has duplicate paths")
        if object_type == "commit" or mode == "160000":
            raise SnapshotError("unsupported-submodule", "source snapshot contains a Git submodule entry")
        if object_type != "blob" or mode not in {"100644", "100755", "120000"}:
            raise SnapshotError("unsupported-source-entry", "source snapshot contains an unsupported Git tree entry")
        expected[path] = "symlink" if mode == "120000" else "file"
    return expected


def _validate_symlink(path: str, target: str, expected: dict[str, str]) -> str:
    if (not target or target.startswith("/") or "\\" in target or
            any(ord(character) < 32 or ord(character) == 127 for character in target)):
        raise SnapshotError("unsafe-symlink", "source snapshot contains an absolute or ambiguous symlink")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
    if resolved in ("", ".", "..") or resolved.startswith("../") or resolved.startswith("/"):
        raise SnapshotError("unsafe-symlink", "source snapshot contains a symlink that escapes its root")
    resolved = _safe_repo_path(resolved)
    if expected.get(resolved) == "symlink":
        raise SnapshotError("unsafe-symlink", "source snapshot contains a chained symlink")
    components = resolved.split("/")
    for end in range(1, len(components)):
        if expected.get("/".join(components[:end])) == "symlink":
            raise SnapshotError("unsafe-symlink", "source snapshot traverses a symlink directory")
    if resolved not in expected and not any(candidate.startswith(resolved + "/") for candidate in expected):
        raise SnapshotError("unsafe-symlink", "source snapshot contains a dangling symlink")
    return target


def inventory_tree(root: Path) -> tuple[dict[str, Any], ...]:
    """Inventory regular files and symlinks without traversing symlink directories."""
    root = root.resolve()
    rows: list[dict[str, Any]] = []
    folded: set[str] = set()
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        entries = sorted(directories + files)
        directories[:] = [name for name in directories if not (current_path / name).is_symlink()]
        for name in entries:
            path = current_path / name
            relative = _safe_repo_path(path.relative_to(root).as_posix())
            if path.is_dir() and not path.is_symlink():
                continue
            folded_path = relative.casefold()
            if folded_path in folded:
                raise SnapshotError("ambiguous-materialization", "materialized source has case-colliding paths")
            folded.add(folded_path)
            metadata = path.lstat()
            if stat.S_ISREG(metadata.st_mode):
                rows.append({"path": relative, "type": "file", "bytes": metadata.st_size, "sha256": sha256(path)})
            elif stat.S_ISLNK(metadata.st_mode):
                target = os.readlink(path)
                encoded = target.encode("utf-8", errors="strict")
                rows.append({"path": relative, "type": "symlink", "target": target,
                             "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()})
            else:
                raise SnapshotError("unsupported-materialized-entry", "materialized source contains a special file")
    return tuple(sorted(rows, key=lambda row: row["path"].encode("utf-8")))


def inventory_digest(rows: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> str:
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def create_snapshot(repository: Path, revision: str, destination: Path) -> SourceSnapshot:
    """Materialize and verify the complete committed Git archive without checkout inputs."""
    repository = repository.resolve()
    commit = _commit_id(repository, revision)
    expected = _expected_tree(repository, commit)
    archive = _git(repository, ["-c", f"core.attributesFile={os.devnull}", "archive", "--format=tar", commit])
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise SnapshotError("archive-size-limit", "committed source archive exceeds the configured size bound")

    files: dict[str, bytes] = {}
    symlinks: dict[str, str] = {}
    directories: set[str] = set()
    all_names: set[str] = set()
    folded: set[str] = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            for member in tar:
                name = member.name[:-1] if member.isdir() and member.name.endswith("/") else member.name
                name = _safe_repo_path(name)
                folded_name = name.casefold()
                if name in all_names or folded_name in folded:
                    raise SnapshotError("ambiguous-archive", "Git archive contains duplicate or case-colliding names")
                all_names.add(name)
                folded.add(folded_name)
                if member.isdir():
                    directories.add(name)
                elif member.isfile():
                    stream = tar.extractfile(member)
                    if stream is None:
                        raise SnapshotError("archive-read-failed", "Git archive file entry could not be read")
                    data = stream.read(MAX_ARCHIVE_BYTES + 1)
                    if len(data) > MAX_ARCHIVE_BYTES or len(data) != member.size:
                        raise SnapshotError("archive-read-failed", "Git archive file entry exceeded its declared size")
                    files[name] = data
                elif member.issym():
                    symlinks[name] = member.linkname
                else:
                    raise SnapshotError("unsupported-archive-entry", "Git archive contains a non-file source entry")
    except SnapshotError:
        raise
    except (tarfile.TarError, OSError, UnicodeError) as error:
        raise SnapshotError("archive-read-failed", "Git archive could not be parsed safely") from error

    archived_types = {**{path: "file" for path in files}, **{path: "symlink" for path in symlinks}}
    if archived_types != expected:
        raise SnapshotError("incomplete-archive", "Git archive does not contain the complete committed source tree")
    for path in directories:
        if path in expected or not any(candidate.startswith(path + "/") for candidate in expected):
            raise SnapshotError("ambiguous-archive", "Git archive contains an unexpected directory entry")
    for path, target in symlinks.items():
        _validate_symlink(path, target, expected)

    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise SnapshotError("snapshot-destination-exists", "source snapshot destination must be fresh")
    try:
        destination.mkdir(parents=True, exist_ok=False)
        directory_names = {parent for name in expected for parent in _parent_paths(name)}
        for directory in sorted(directory_names, key=lambda value: (value.count("/"), value)):
            (destination / Path(*directory.split("/"))).mkdir(exist_ok=True)
        for path, data in files.items():
            target_path = destination / Path(*path.split("/"))
            with target_path.open("xb") as stream:
                stream.write(data)
        for path, target in symlinks.items():
            (destination / Path(*path.split("/"))).symlink_to(target)
    except (OSError, ValueError) as error:
        shutil.rmtree(destination, ignore_errors=True)
        raise SnapshotError("snapshot-materialization-failed", "committed source snapshot could not be materialized") from error

    rows = inventory_tree(destination)
    for path, target in symlinks.items():
        _validate_symlink(path, target, expected)
    actual_types = {row["path"]: row["type"] for row in rows}
    if actual_types != expected:
        raise SnapshotError("incomplete-snapshot", "materialized source inventory differs from the committed tree")
    return SourceSnapshot(destination, commit, rows, inventory_digest(rows), hashlib.sha256(archive).hexdigest())


def _parent_paths(path: str) -> set[str]:
    parts = path.split("/")
    return {"/".join(parts[:index]) for index in range(1, len(parts))}


def _path_prefixes(path: str) -> tuple[str, ...]:
    parts = path.split("/")
    return tuple("/".join(parts[:index]) for index in range(1, len(parts) + 1))


def verify_snapshot(snapshot: SourceSnapshot) -> tuple[tuple[dict[str, Any], ...], str]:
    rows = inventory_tree(snapshot.root)
    digest = inventory_digest(rows)
    if rows != snapshot.inventory or digest != snapshot.digest:
        raise SnapshotError("snapshot-inventory-mismatch", "materialized source inventory changed after archive creation")
    return rows, digest


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def redact(text: str) -> str:
    text = text.replace(str(ROOT), "[repo]").replace(str(Path.home()), "[home]")
    text = re.sub(r"/(?:private/)?(?:var/folders|tmp)/[^\s:'\"]+", "[temporary-path]", text)
    return text


class Runner:
    def __init__(self, work: Path, source_root: Path, snapshot: SourceSnapshot) -> None:
        self.work = work
        self.source_root = source_root
        self.snapshot = snapshot
        self.lanes: dict[str, dict[str, object]] = {}

    def command(self, name: str, argv: list[str], *, cwd: Path | None = None,
                timeout: int = 600, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
        verify_snapshot(self.snapshot)
        started = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=cwd or self.source_root, env=clean_environment(), text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    check=False, timeout=timeout)
            output = result.stdout
            code = result.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            output = f"{type(error).__name__}: {error}"
            code = -1
        verify_snapshot(self.snapshot)
        elapsed = round(time.monotonic() - started, 3)
        safe_output = redact(output)
        (self.work / f"{name}.log").write_text(safe_output, encoding="utf-8")
        status = "pass" if code == 0 else "fail"
        self.lanes[name] = {
            "status": status, "command": [redact(part) for part in [Path(argv[0]).name, *argv[1:]]],
            "exit_code": code, "seconds": elapsed,
            "log_sha256": sha256(self.work / f"{name}.log"),
        }
        if code != 0 and not allow_failure:
            raise RuntimeError(f"{name} failed; see ignored build/playable-qualification logs")
        return subprocess.CompletedProcess(argv, code, output)


def cache_identity(cache: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in cache.read_text(encoding="utf-8").splitlines():
        if line.startswith("//") or not line or ":" not in line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.split(":", 1)[0]] = value
    identity = {key: values.get(key, "unknown") for key in (
        "CMAKE_C_COMPILER_ID", "CMAKE_C_COMPILER_VERSION", "CMAKE_CXX_COMPILER_ID",
        "CMAKE_CXX_COMPILER_VERSION", "CMAKE_GENERATOR", "CMAKE_BUILD_TYPE",
        "CMAKE_OSX_SYSROOT", "CMAKE_OSX_DEPLOYMENT_TARGET",
    )}
    for language in ("C", "CXX"):
        files = sorted(cache.parent.glob(f"CMakeFiles/*/CMake{language}Compiler.cmake"))
        if files:
            text = files[0].read_text(encoding="utf-8")
            for key in ("ID", "VERSION"):
                match = re.search(rf'set\(CMAKE_{language}_COMPILER_{key} "([^"]*)"\)', text)
                if match:
                    identity[f"CMAKE_{language}_COMPILER_{key}"] = match.group(1)
    return identity


def run_consumer(runner: Runner, source_root: Path, prefix: Path, fixture: Path, core: Path,
                 variant: str) -> None:
    consumer_source = source_root / "tests" / "consumers"
    consumer_build = runner.work / f"consumer-{variant}"
    runner.command(f"consumer-{variant}-configure", [
        "cmake", "-S", str(consumer_source), "-B", str(consumer_build),
        f"-DGlueyneo_DIR={prefix / 'lib/cmake/Glueyneo'}",
        f"-DGLUEYNEO_CONSUMER_C_SOURCE={source_root / 'examples/diagnostic.c'}",
        "-DCMAKE_BUILD_TYPE=Release",
    ])
    runner.command(f"consumer-{variant}-build", ["cmake", "--build", str(consumer_build), "--parallel", "2"])
    consumer = consumer_build / "glueyneo-installed-c"
    runner.command(f"consumer-{variant}-check", [
        sys.executable, str(source_root / "tests/consumers/test_playable_install.py"),
        "--prefix", str(prefix), "--consumer", str(consumer), "--fixture", str(fixture),
        "--core", str(core),
    ])


def frontend_identity(bundle: Path) -> dict[str, str]:
    plist_path = bundle / "Contents/Info.plist"
    if not plist_path.is_file():
        return {"status": "unknown", "reason": "RetroArch bundle or Info.plist missing"}
    try:
        with plist_path.open("rb") as stream:
            info = plistlib.load(stream)
        executable = bundle / "Contents/MacOS" / str(info.get("CFBundleExecutable", ""))
        return {
            "status": "identified" if executable.is_file() else "unknown",
            "version": str(info.get("CFBundleShortVersionString", "unknown")),
            "bundle_id": str(info.get("CFBundleIdentifier", "unknown")),
            "executable_sha256": sha256(executable) if executable.is_file() else "unknown",
        }
    except (OSError, plistlib.InvalidFileException):
        return {"status": "unknown", "reason": "RetroArch identity could not be read"}


def check_docs(source_root: Path) -> None:
    guide = (source_root / "docs/first-playable-build.md").read_text(encoding="utf-8")
    validation = (source_root / ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md").read_text(encoding="utf-8")
    required = (
        "python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean",
        "public-playable.bin", "RetroArch", "macOS", "unsupported", "unknown",
        YMFM_REVISION, Z80_REVISION,
    )
    missing = [term for term in required if term not in guide]
    if missing:
        raise RuntimeError(f"integrator documentation omits: {', '.join(missing)}")
    if re.search(r"\b(TBD|pending|planned)\b", validation, re.IGNORECASE):
        raise RuntimeError("validation map still contains TBD/pending/planned status")


def _tool_record(name: str) -> dict[str, str]:
    executable = shutil.which(name, path=clean_environment().get("PATH", ""))
    if not executable:
        return {"status": "unknown", "name": name, "path_basename": "unknown", "sha256": "unknown"}
    resolved = Path(executable).resolve()
    return {"status": "identified", "name": name, "path_basename": resolved.name,
            "sha256": sha256(resolved) if resolved.is_file() else "unknown"}


def _artifact_file(path: Path, output_root: Path) -> dict[str, object]:
    if not path.is_file():
        return {"status": "unknown", "path": path.relative_to(output_root).as_posix() if path.is_relative_to(output_root) else "external"}
    return {"status": "identified", "path": path.relative_to(output_root).as_posix() if path.is_relative_to(output_root) else "external",
            "bytes": path.stat().st_size, "sha256": sha256(path)}


def _artifact_tree(path: Path, output_root: Path) -> dict[str, object]:
    if not path.is_dir():
        return {"status": "unknown", "path": path.relative_to(output_root).as_posix() if path.is_relative_to(output_root) else "external"}
    rows = inventory_tree(path)
    return {"status": "identified", "path": path.relative_to(output_root).as_posix(),
            "inventory_schema": INVENTORY_SCHEMA, "inventory_sha256": inventory_digest(rows), "entries": rows}


def _write_receipt(receipt: dict[str, Any]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    temporary_path = OUTPUT / "receipt.json.tmp"
    receipt_path = OUTPUT / "receipt.json"
    temporary_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary_path.replace(receipt_path)
    print(json.dumps({
        "status": receipt["status"], "receipt": "build/playable-qualification/receipt.json",
        "fixture_sha256": receipt.get("fixture", {}).get("sha256", "unknown"),
        "retroarch_status": receipt.get("retroarch_smoke", {}).get("status", "unknown"),
        "reason": receipt.get("reason", ""),
    }, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retroarch", type=Path, required=True)
    parser.add_argument("--clean", action="store_true", help="qualify a fresh committed-source snapshot and fresh build/install directories")
    parser.add_argument("--check-docs", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="clean-", dir=OUTPUT))
    snapshot: SourceSnapshot | None = None
    runner: Runner | None = None
    source_root = work / "source"
    identity: dict[str, Any] = {
        "source_revision": "unknown", "source_snapshot": {"status": "unknown"},
        "os": platform.platform(), "architecture": platform.machine(),
        "python": platform.python_version(), "fixture_sha256_expected": FIXTURE_SHA256,
        "ymfm_candidate_revision": YMFM_REVISION, "z80_candidate_revision": Z80_REVISION,
    }
    status = "fail"
    reason = "qualification did not start"
    fixture_static = Path()
    fixture_shared = Path()
    static_core = Path()
    shared_core = Path()
    prefixes: dict[str, Path] = {}
    report_path = work / "ym2610-admission.json"
    try:
        if not args.clean:
            raise RuntimeError("--clean is required for qualification")
        snapshot = create_snapshot(ROOT, "HEAD", source_root)
        archived_runner = source_root / "tools/verify_playable.py"
        if not archived_runner.is_file() or sha256(Path(__file__).resolve()) != sha256(archived_runner):
            raise SnapshotError("runner-source-mismatch", "executing qualification runner differs from the committed archive")
        verify_snapshot(snapshot)
        identity["source_revision"] = snapshot.commit
        identity["source_snapshot"] = {
            "status": "pass", "commit": snapshot.commit,
            "schema": INVENTORY_SCHEMA, "digest_algorithm": "sha256(canonical-json-v1)",
            "inventory_sha256": snapshot.digest, "archive_sha256": snapshot.archive_sha256,
            "file_count": sum(row["type"] == "file" for row in snapshot.inventory),
            "symlink_count": sum(row["type"] == "symlink" for row in snapshot.inventory),
            "entries": list(snapshot.inventory),
        }
        source_root = snapshot.root
        runner = Runner(work, source_root, snapshot)
        environment = clean_environment()
        identity["toolchain"] = {
            "python": {"version": platform.python_version(), "path_basename": Path(sys.executable).name,
                       "sha256": sha256(Path(sys.executable).resolve())},
            "cmake": _tool_record("cmake"), "ninja": _tool_record("ninja"),
        }
        cmake_version = subprocess.run(["cmake", "--version"], cwd=source_root, env=environment,
                                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       check=False, timeout=30)
        ninja_version = subprocess.run(["ninja", "--version"], cwd=source_root, env=environment,
                                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       check=False, timeout=30)
        identity["cmake"] = cmake_version.stdout.splitlines()[0] if cmake_version.returncode == 0 and cmake_version.stdout else "unknown"
        identity["ninja"] = ninja_version.stdout.strip() if ninja_version.returncode == 0 else "unknown"
        identity["retroarch"] = frontend_identity(args.retroarch.resolve())
        if sys.platform == "darwin" and shutil.which("xcrun", path=environment.get("PATH", "")):
            sdk = subprocess.run(["xcrun", "--show-sdk-version"], cwd=source_root, env=environment,
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 check=False, timeout=30)
            identity["macos_sdk"] = sdk.stdout.strip() if sdk.returncode == 0 else "unknown"
        else:
            identity["macos_sdk"] = "unsupported on this host"

        static_core = work / "static-install/lib/libretro/glueyneo_libretro.dylib"
        shared_core = work / "shared-install/lib/libretro/glueyneo_libretro.dylib"
        build_roots: dict[str, Path] = {}
        for variant, shared in (("static", "OFF"), ("shared", "ON")):
            build = work / f"{variant}-build"
            prefix = work / f"{variant}-install"
            build_roots[variant] = build
            prefixes[variant] = prefix
            runner.command(f"{variant}-configure", [
                "cmake", "-S", str(source_root), "-B", str(build), "-G", "Ninja",
                "-DCMAKE_BUILD_TYPE=Debug", f"-DCMAKE_INSTALL_PREFIX={prefix}",
                f"-DBUILD_SHARED_LIBS={shared}",
                "-DBUILD_TESTING=ON", "-DGLUEYNEO_BUILD_TESTS=ON",
                "-DGLUEYNEO_CPU_EXPERIMENT=OFF", "-DGLUEYNEO_OWNED_CPU_EXPERIMENT=OFF",
                "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF", "-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY=ON",
            ])
            runner.command(f"{variant}-build", ["cmake", "--build", str(build), "--parallel", "2"], timeout=1200)
            runner.command(f"{variant}-install", ["cmake", "--install", str(build)])
            candidate = build / "public-playable.bin"
            if not candidate.is_file() or sha256(candidate) != FIXTURE_SHA256:
                raise RuntimeError(f"{variant} generated fixture identity mismatch")
            if variant == "shared":
                fixture_shared = candidate
                shared_cache = build / "CMakeCache.txt"
            else:
                fixture_static = candidate
            run_consumer(runner, source_root, prefix, candidate,
                         prefix / "lib/libretro/glueyneo_libretro.dylib", variant)

        identity["build"] = cache_identity(shared_cache)
        if sha256(fixture_static) != sha256(fixture_shared):
            raise RuntimeError("static and shared builds generated different public fixture bytes")
        runner.command("full-sdk-ctest", [
            "ctest", "--test-dir", str(build_roots["shared"]), "--verbose",
            "--output-on-failure", "--no-tests=error", "--parallel", "2",
        ], timeout=1200)
        runner.command("z80-source", [sys.executable, str(source_root / "tests/chips/check_z80_source.py")])
        runner.command("ym2610-source", [sys.executable, str(source_root / "tests/chips/check_ym2610.py"), "source"])
        runner.command("ym2610-installed-linkages", [
            sys.executable, str(source_root / "tests/chips/check_ym2610.py"), "link",
            "--both-linkages", "--report", str(report_path),
        ], timeout=1200)
        verify_snapshot(snapshot)
        status, reason = "pass", ""
    except (RuntimeError, OSError, SnapshotError) as error:
        status = "fail"
        reason = getattr(error, "reason", "qualification-failed")
        if not isinstance(error, SnapshotError):
            reason = redact(str(error))
    except Exception as error:  # Fail closed while still retaining an inspectable receipt.
        status = "fail"
        reason = f"qualification-internal-error: {type(error).__name__}: {redact(str(error))}"

    receipt: dict[str, object] = {
        "schema": "glueyneo.playable-qualification/v1",
        "status": status,
        "identity": identity,
        "lanes": runner.lanes,
        "fixture": {"status": "pass" if fixture_shared.is_file() and sha256(fixture_shared) == FIXTURE_SHA256 else "unknown",
                    "sha256": sha256(fixture_shared) if fixture_shared.is_file() else "unknown"},
        "retroarch_smoke": {"status": "unknown", "reason": "not run"},
        "artifacts": {
            "static_fixture": _artifact_file(fixture_static, OUTPUT),
            "shared_fixture": _artifact_file(fixture_shared, OUTPUT),
            "static_core": _artifact_file(static_core, OUTPUT),
            "shared_core": _artifact_file(shared_core, OUTPUT),
            "static_install": _artifact_tree(prefixes["static"], OUTPUT) if "static" in prefixes else {"status": "unknown"},
            "shared_install": _artifact_tree(prefixes["shared"], OUTPUT) if "shared" in prefixes else {"status": "unknown"},
            "ym2610_candidate_report": _artifact_file(report_path, OUTPUT),
        },
        "unsupported_configurations": ["non-macOS", "architectures other than this host", "unlisted compilers and SDKs"],
    }
    if snapshot is None:
        receipt["identity"]["source_snapshot"] = {"status": "fail", "reason": reason}  # type: ignore[index]
    if runner is None:
        receipt["lanes"] = {}
    if snapshot is not None and runner is not None and shared_core.is_file() and fixture_shared.is_file():
        smoke = runner.command("actual-retroarch-smoke", [
            sys.executable, str(source_root / "tests/libretro/retroarch_smoke.py"),
            "--retroarch", str(args.retroarch.resolve()), "--core", str(shared_core),
            "--content", str(fixture_shared),
        ], timeout=180, allow_failure=True)
        try:
            smoke_data = json.loads(smoke.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            smoke_data = {"status": "unknown", "reason": "smoke omitted a machine-readable result"}
        if smoke.returncode == 0 and smoke_data.get("status") == "pass":
            receipt["retroarch_smoke"] = smoke_data
        else:
            receipt["retroarch_smoke"] = {**smoke_data, "status": "unknown"}
            status = "fail"
            reason = reason or "actual pinned RetroArch load/input/video/unload gate is unknown or failed"
    else:
        receipt["retroarch_smoke"] = {"status": "unknown", "reason": "clean installed core or fixture unavailable"}
        status = "fail"
        reason = reason or "actual RetroArch lane could not run"
    if args.check_docs:
        try:
            if snapshot is None:
                raise SnapshotError("documentation-snapshot-unavailable", "documentation cannot be checked without a source snapshot")
            verify_snapshot(snapshot)
            check_docs(source_root)
            verify_snapshot(snapshot)
            receipt["documentation"] = {"status": "pass"}
        except RuntimeError as error:
            receipt["documentation"] = {"status": "fail", "reason": str(error)}
            status = "fail"
            reason = reason or str(error)
    if snapshot is not None:
        try:
            verify_snapshot(snapshot)
        except SnapshotError as error:
            receipt["identity"]["source_snapshot"]["status"] = "fail"  # type: ignore[index]
            receipt["identity"]["source_snapshot"]["reason"] = error.reason  # type: ignore[index]
            status = "fail"
            reason = reason or error.reason
    receipt["status"] = status
    receipt["reason"] = reason
    receipt["output"] = {"run_directory": work.relative_to(OUTPUT).as_posix()}
    if runner is not None:
        receipt["lanes"] = runner.lanes
    _write_receipt(receipt)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
