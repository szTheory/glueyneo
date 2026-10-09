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
MAX_GIT_COMMAND_SECONDS = 120


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
        if key not in blocked and key not in {"SDKROOT", "MACOSX_DEPLOYMENT_TARGET", "ARCHFLAGS"}
        and not key.startswith(("CMAKE_", "GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_TRACE", "DYLD_", "LD_"))
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


def _git_archive(repository: Path, commit: str) -> bytes:
    """Stream the tar to a bounded temporary file instead of buffering an unbounded archive."""
    command = ["git", "-c", f"core.attributesFile={os.devnull}", "archive", "--format=tar", commit]
    try:
        with tempfile.TemporaryFile() as archive_file, tempfile.TemporaryFile() as error_file:
            process = subprocess.Popen(command, cwd=repository, env=clean_environment(),
                                       stdout=archive_file, stderr=error_file)
            deadline = time.monotonic() + MAX_GIT_COMMAND_SECONDS
            while process.poll() is None:
                if archive_file.tell() > MAX_ARCHIVE_BYTES:
                    process.kill()
                    process.wait()
                    raise SnapshotError("archive-size-limit", "committed source archive exceeds the configured size bound")
                if time.monotonic() >= deadline:
                    process.kill()
                    process.wait()
                    raise SnapshotError("git-archive-timeout", "Git source archive exceeded its time bound")
                time.sleep(0.025)
            archive_size = archive_file.tell()
            if process.returncode != 0:
                raise SnapshotError("git-archive-failed", "Git could not archive the committed source")
            if archive_size > MAX_ARCHIVE_BYTES:
                raise SnapshotError("archive-size-limit", "committed source archive exceeds the configured size bound")
            archive_file.seek(0)
            archive = archive_file.read(MAX_ARCHIVE_BYTES + 1)
    except SnapshotError:
        raise
    except (OSError, subprocess.SubprocessError) as error:
        raise SnapshotError("git-archive-failed", f"Git source archive command failed ({type(error).__name__})") from error
    if len(archive) != archive_size:
        raise SnapshotError("archive-read-failed", "Git source archive could not be read completely")
    return archive


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
        expected[path] = "symlink" if mode == "120000" else ("file-executable" if mode == "100755" else "file")
    for path in expected:
        if any(parent in expected for parent in _parent_paths(path)):
            raise SnapshotError("ambiguous-source-tree", "committed source tree uses a file as a directory")
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
                if metadata.st_size > MAX_ARCHIVE_BYTES:
                    raise SnapshotError("source-file-size-limit", "materialized source file exceeds the configured size bound")
                rows.append({"path": relative, "type": "file",
                             "mode": "executable" if metadata.st_mode & 0o111 else "regular",
                             "bytes": metadata.st_size, "sha256": sha256(path)})
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


def _archive_members(
    archive: bytes, expected: dict[str, str],
) -> tuple[dict[str, tuple[bytes, bool]], dict[str, str], tuple[dict[str, Any], ...]]:
    """Parse a bounded Git archive once and derive rows from its actual member bytes."""
    files: dict[str, tuple[bytes, bool]] = {}
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
                    if member.size < 0 or member.size > MAX_ARCHIVE_BYTES:
                        raise SnapshotError("archive-size-limit", "Git archive member exceeds the configured size bound")
                    stream = tar.extractfile(member)
                    if stream is None:
                        raise SnapshotError("archive-read-failed", "Git archive file entry could not be read")
                    data = stream.read(MAX_ARCHIVE_BYTES + 1)
                    if len(data) > MAX_ARCHIVE_BYTES or len(data) != member.size:
                        raise SnapshotError("archive-read-failed", "Git archive file entry exceeded its declared size")
                    files[name] = (data, bool(member.mode & 0o111))
                elif member.issym():
                    symlinks[name] = member.linkname
                else:
                    raise SnapshotError("unsupported-archive-entry", "Git archive contains a non-file source entry")
    except SnapshotError:
        raise
    except (tarfile.TarError, OSError, UnicodeError) as error:
        raise SnapshotError("archive-read-failed", "Git archive could not be parsed safely") from error

    archived_types = {
        **{path: ("file-executable" if executable else "file") for path, (_data, executable) in files.items()},
        **{path: "symlink" for path in symlinks},
    }
    if archived_types != expected:
        raise SnapshotError("incomplete-archive", "Git archive does not contain the complete committed source tree")
    for path in directories:
        if path in expected or not any(candidate.startswith(path + "/") for candidate in expected):
            raise SnapshotError("ambiguous-archive", "Git archive contains an unexpected directory entry")
    for path, target in symlinks.items():
        _validate_symlink(path, target, expected)

    rows: list[dict[str, Any]] = []
    for path, (data, executable) in files.items():
        rows.append({"path": path, "type": "file", "mode": "executable" if executable else "regular",
                     "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    for path, target in symlinks.items():
        try:
            encoded = target.encode("utf-8", errors="strict")
        except UnicodeError as error:
            raise SnapshotError("unsafe-symlink", "source archive contains a non-UTF-8 symlink target") from error
        rows.append({"path": path, "type": "symlink", "target": target,
                     "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()})
    rows.sort(key=lambda row: row["path"].encode("utf-8"))
    return files, symlinks, tuple(rows)


def create_snapshot(repository: Path, revision: str, destination: Path) -> SourceSnapshot:
    """Materialize and verify the complete committed Git archive without checkout inputs."""
    repository = repository.resolve()
    commit = _commit_id(repository, revision)
    expected = _expected_tree(repository, commit)
    archive = _git_archive(repository, commit)

    files, symlinks, archive_rows = _archive_members(archive, expected)

    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise SnapshotError("snapshot-destination-exists", "source snapshot destination must be fresh")
    try:
        destination.mkdir(parents=True, exist_ok=False)
        directory_names = {parent for name in expected for parent in _parent_paths(name)}
        for directory in sorted(directory_names, key=lambda value: (value.count("/"), value)):
            (destination / Path(*directory.split("/"))).mkdir(exist_ok=True)
        for path, (data, executable) in files.items():
            target_path = destination / Path(*path.split("/"))
            with target_path.open("xb") as stream:
                stream.write(data)
            target_path.chmod(0o755 if executable else 0o644)
        for path, target in symlinks.items():
            (destination / Path(*path.split("/"))).symlink_to(target)
    except (OSError, ValueError) as error:
        shutil.rmtree(destination, ignore_errors=True)
        raise SnapshotError("snapshot-materialization-failed", "committed source snapshot could not be materialized") from error

    rows = inventory_tree(destination)
    if rows != archive_rows:
        raise SnapshotError("snapshot-inventory-mismatch", "materialized source inventory differs from archived member bytes")
    for path, target in symlinks.items():
        _validate_symlink(path, target, expected)
    actual_types = {
        row["path"]: ("file-executable" if row["type"] == "file" and row["mode"] == "executable"
                       else "file" if row["type"] == "file" else "symlink")
        for row in rows
    }
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


def snapshot_record(snapshot: SourceSnapshot) -> dict[str, Any]:
    return {
        "status": "pass", "commit": snapshot.commit, "schema": INVENTORY_SCHEMA,
        "digest_algorithm": "sha256(canonical-json-v1)",
        "inventory_sha256": snapshot.digest, "archive_sha256": snapshot.archive_sha256,
        "entry_count": len(snapshot.inventory),
        "file_count": sum(row["type"] == "file" for row in snapshot.inventory),
        "symlink_count": sum(row["type"] == "symlink" for row in snapshot.inventory),
        "entries": list(snapshot.inventory),
    }


def validate_snapshot_record(record: dict[str, Any], repository: Path | None = None) -> None:
    """Reject malformed, incomplete-count, or stale source inventory receipts."""
    if (record.get("status") != "pass" or record.get("schema") != INVENTORY_SCHEMA or
            record.get("digest_algorithm") != "sha256(canonical-json-v1)" or
            not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", str(record.get("commit", ""))) or
            not re.fullmatch(r"[0-9a-f]{64}", str(record.get("archive_sha256", "")))):
        raise SnapshotError("snapshot-record-invalid", "source snapshot receipt identity is incomplete")
    entries = record.get("entries")
    if not isinstance(entries, list):
        raise SnapshotError("snapshot-record-invalid", "source snapshot receipt has no inventory rows")
    for field in ("entry_count", "file_count", "symlink_count"):
        value = record.get(field)
        if type(value) is not int or value < 0:
            raise SnapshotError("snapshot-record-invalid", f"source snapshot receipt has an invalid {field}")
    paths: set[str] = set()
    folded: set[str] = set()
    previous = b""
    file_count = symlink_count = 0
    expected: dict[str, str] = {}
    symlinks: list[tuple[str, str]] = []
    for row in entries:
        if not isinstance(row, dict):
            raise SnapshotError("snapshot-record-invalid", "source snapshot receipt contains a malformed row")
        path = _safe_repo_path(str(row.get("path", "")))
        encoded_path = path.encode("utf-8")
        if encoded_path <= previous or path in paths or path.casefold() in folded:
            raise SnapshotError("snapshot-record-invalid", "source snapshot receipt paths are duplicated or unordered")
        previous = encoded_path
        paths.add(path)
        folded.add(path.casefold())
        digest = row.get("sha256")
        byte_count = row.get("bytes")
        if type(byte_count) is not int or byte_count < 0 or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SnapshotError("snapshot-record-invalid", "source snapshot receipt contains an invalid byte identity")
        if row.get("type") == "file":
            mode = row.get("mode")
            if mode not in {"regular", "executable"}:
                raise SnapshotError("snapshot-record-invalid", "source snapshot file row has an invalid mode")
            expected[path] = "file-executable" if mode == "executable" else "file"
            if set(row) != {"path", "type", "mode", "bytes", "sha256"}:
                raise SnapshotError("snapshot-record-invalid", "source snapshot file row has unexpected fields")
            file_count += 1
        elif row.get("type") == "symlink":
            expected[path] = "symlink"
            target = row.get("target")
            if not isinstance(target, str) or len(target.encode("utf-8")) != byte_count:
                raise SnapshotError("snapshot-record-invalid", "source snapshot symlink row has an invalid target")
            if hashlib.sha256(target.encode("utf-8")).hexdigest() != digest:
                raise SnapshotError("snapshot-record-invalid", "source snapshot symlink digest does not match its target")
            if set(row) != {"path", "type", "target", "bytes", "sha256"}:
                raise SnapshotError("snapshot-record-invalid", "source snapshot symlink row has unexpected fields")
            symlink_count += 1
            symlinks.append((path, target))
        else:
            raise SnapshotError("snapshot-record-invalid", "source snapshot receipt contains an unsupported entry type")
    for path, target in symlinks:
        _validate_symlink(path, target, expected)
    actual_digest = inventory_digest(entries)
    if (record.get("inventory_sha256") != actual_digest or
            record.get("entry_count") != len(entries) or
            record.get("file_count") != file_count or
            record.get("symlink_count") != symlink_count):
        raise SnapshotError("snapshot-record-digest-mismatch", "source snapshot receipt inventory is missing, stale, or inconsistent")
    if repository is not None:
        repository = repository.resolve()
        if _expected_tree(repository, str(record["commit"])) != expected:
            raise SnapshotError("snapshot-record-incomplete", "source snapshot receipt does not list the complete committed tree")
        archive = _git_archive(repository, str(record["commit"]))
        if hashlib.sha256(archive).hexdigest() != record["archive_sha256"]:
            raise SnapshotError("snapshot-record-source-mismatch", "source snapshot receipt archive digest does not match its commit")
        _files, _symlinks, archive_rows = _archive_members(archive, expected)
        if list(archive_rows) != entries:
            raise SnapshotError("snapshot-record-source-mismatch", "source snapshot receipt rows do not match committed archive bytes")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def redact(text: str) -> str:
    roots = [str(ROOT), str(Path.home()), "/Users/", "/Volumes/", "/tmp/",
             "/private/tmp/", "/var" + "/folders/", "/private" + "/var" + "/folders/"]
    roots = sorted({root for root in roots if root}, key=len, reverse=True)
    root_pattern = re.compile(r"(?<![A-Za-z0-9._-])(?:" + "|".join(re.escape(root) for root in roots) + r")")
    match = root_pattern.search(text)
    if match is None:
        return text

    # Subprocess output is one unstructured value: a newline, quote or other
    # punctuation cannot prove where a private path ends. Drop the entire tail.
    root = match.group()
    if root.startswith(str(ROOT)):
        marker = "[repo]"
    elif root.startswith(str(Path.home())):
        marker = "[home]"
    elif "/tmp/" in root or "var/folders" in root:
        marker = "[temporary-path]"
    else:
        marker = "[user]"
    return text[:match.start()] + marker


class Runner:
    def __init__(self, work: Path, source_root: Path, snapshot: SourceSnapshot) -> None:
        self.work = work
        self.source_root = source_root
        self.snapshot = snapshot
        self.lanes: dict[str, dict[str, object]] = {}

    def command(self, name: str, argv: list[str], *, cwd: Path | None = None,
                timeout: int = 600, allow_failure: bool = False,
                source_build_overlay: Path | None = None) -> subprocess.CompletedProcess[str]:
        verify_snapshot(self.snapshot)
        build_link: Path | None = None
        if source_build_overlay is not None:
            build_link = self.source_root / "build"
            overlay = source_build_overlay.resolve()
            if not overlay.is_relative_to(self.work.resolve()):
                raise SnapshotError("generated-output-escape", "generated build output is outside the ignored qualification directory")
            if build_link.exists() or build_link.is_symlink():
                raise SnapshotError("generated-output-path-conflict", "source archive already contains a build output path")
            overlay.mkdir(parents=True, exist_ok=True)
            build_link.symlink_to(overlay, target_is_directory=True)
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
        finally:
            if build_link is not None and build_link.is_symlink():
                build_link.unlink()
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
        return subprocess.CompletedProcess([redact(part) for part in argv], code, safe_output)


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
        "CMAKE_C_COMPILER", "CMAKE_CXX_COMPILER",
    )}
    for language in ("C", "CXX"):
        files = sorted(cache.parent.glob(f"CMakeFiles/*/CMake{language}Compiler.cmake"))
        if files:
            text = files[0].read_text(encoding="utf-8")
            for key in ("ID", "VERSION"):
                match = re.search(rf'set\(CMAKE_{language}_COMPILER_{key} "([^"]*)"\)', text)
                if match:
                    identity[f"CMAKE_{language}_COMPILER_{key}"] = match.group(1)
        compiler = values.get(f"CMAKE_{language}_COMPILER", "")
        compiler_path = Path(compiler) if compiler else Path()
        identity[f"CMAKE_{language}_COMPILER_PATH_BASENAME"] = compiler_path.name if compiler else "unknown"
        identity[f"CMAKE_{language}_COMPILER_SHA256"] = (
            sha256(compiler_path.resolve()) if compiler_path.is_file() else "unknown"
        )
        identity.pop(f"CMAKE_{language}_COMPILER", None)
    if identity.get("CMAKE_OSX_SYSROOT", "").startswith("/"):
        identity["CMAKE_OSX_SYSROOT"] = Path(identity["CMAKE_OSX_SYSROOT"]).name
    return identity


def run_consumer(runner: Runner, source_root: Path, prefix: Path, fixture: Path, core: Path,
                 variant: str) -> None:
    consumer_source = source_root / "tests" / "consumers"
    consumer_build = runner.work / f"consumer-{variant}"
    diagnostic_fixture = fixture.with_name("diagnostic-original-a.bin")
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
        "--prefix", str(prefix), "--consumer", str(consumer), "--fixture", str(diagnostic_fixture),
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


def _markdown_table_rows(document: str, header: str) -> list[list[str]]:
    lines = document.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.startswith(header))
    except StopIteration as error:
        raise RuntimeError(f"validation map is missing table {header!r}") from error
    rows: list[list[str]] = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def check_docs(source_root: Path) -> None:
    guide = (source_root / "docs/first-playable-build.md").read_text(encoding="utf-8")
    validation = (source_root / ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md").read_text(encoding="utf-8")
    affirmative_frontend_claims = (
        r"\b(?:frontend\s+)?(?:app|retroarch)\s+(?:has\s+)?(?:loaded|started)\s+successfully\b",
        r"\b(?:loaded|started)\s+(?:the\s+)?(?:frontend\s+)?(?:app|retroarch)\s+successfully\b",
        r"\b(?:displayed|presented|rendered)\s+(?:guest\s+)?pixels?\b",
        r"\b(?:guest\s+)?pixels?\s+(?:were|are|was)\s+(?:displayed|presented|rendered|shown)\b",
        r"\b(?:frontend|retroarch|app)\s+booted\s+(?:the\s+)?game\s+and\s+showed\s+(?:its\s+)?output\b",
        r"\b(?:a\s+)?frame\s+(?:was\s+)?rendered\s+to\s+(?:the\s+)?window\b",
        r"\b(?:the\s+)?screen\s+(?:was|became)\s+visible\b",
        r"\b(?:video|display|visual)\s+output\s+(?:was\s+)?(?:confirmed|successful|passed)\b",
        r"\b(?:frontend\s+)?(?:accepted|registered)\s+(?:right|left|mapped)\s+input\b",
        r"\b(?:content|game)\s+unloaded\s+(?:cleanly|successfully)\b",
        r"\b(?:retroarch|frontend|app)\s+(?:exited|quit)\s+normally\b",
        r"\b(?:controls?|input)\s+(?:worked|succeeded)\s+(?:as\s+expected\s+)?(?:in\s+(?:retroarch|the\s+frontend))?\b",
        r"\bgame\s+(?:appeared|was\s+visible|ran|played)\b.{0,80}\b(?:screen|retroarch|successfully|pixels?)\b",
        r"\b(?:frontend|retroarch)\s+(?:accepted|registered)\s+(?:the\s+)?(?:(?:mapped|right|left)\s+)?(?:controller\s+)?input\b",
        r"\b(?:frontend|retroarch)\s+(?:loaded|started|presented|displayed|rendered)\b.{0,80}\b(?:successfully|pixels?|fixture|content)\b",
        r"\b(?:frontend|retroarch|gameplay)\b.{0,80}\b(?:successfully|confirmed|observed|presented|displayed|rendered|accepted|loaded|started|launched|unloaded|ran|played)\b.{0,80}\b(?:game|content|fixture|pixels?|screen|input|controller|retroarch|user|successfully)\b",
    )
    negated_claim = re.compile(
        r"\b(?:does|did|do)\s+not\s+(?:claim|assert|report|show|establish|prove|mean)\s+(?:that\s+)?(?:the\s+)?$",
        re.IGNORECASE,
    )
    clauses = re.split(r"(?<=[.!?;])\s+|\s+(?:but|however|although)\s+", guide)
    for clause in clauses:
        for pattern in affirmative_frontend_claims:
            for match in re.finditer(pattern, clause, re.IGNORECASE):
                if not negated_claim.search(clause[:match.start()]):
                    raise RuntimeError("integrator documentation contains an affirmative frontend claim while actual behavior is unknown")
    required = (
        "python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean",
        "public-playable.bin", "RetroArch", "macOS", "unsupported", "unknown",
        "complete committed Git snapshot", "inventory SHA-256", "dirty and untracked checkout files",
        YMFM_REVISION, Z80_REVISION,
    )
    missing = [term for term in required if term not in guide]
    if missing:
        raise RuntimeError(f"integrator documentation omits: {', '.join(missing)}")

    crosswalk = _markdown_table_rows(
        validation, "| Review Finding | Severity | Existing Threat Scope | Disposition |",
    )
    if not crosswalk:
        raise RuntimeError("validation map has no current review dispositions")
    seen_findings: set[str] = set()
    controlled_states = {"open", "fixed", "skipped", "deferred"}
    for row in crosswalk:
        if len(row) != 4:
            raise RuntimeError("validation map has a malformed review disposition row")
        finding_id, _severity, scope, recorded_state = row
        state = recorded_state.strip().lower()
        if finding_id in seen_findings or not scope.strip() or state not in controlled_states:
            raise RuntimeError("review crosswalk controlled review disposition must be one controlled state")
        seen_findings.add(finding_id)

    task_rows = _markdown_table_rows(
        validation,
        "| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |",
    )
    frontend_rows = [
        row for row in task_rows
        if len(row) == 10 and row[0] == "04-15 T2" and row[1] == "04-15"
    ]
    if len(frontend_rows) != 1:
        raise RuntimeError("HOST-02 and frontend QUAL-03 must remain Pending/unknown in the current validation map")
    requirement_ids = {item.strip() for item in frontend_rows[0][3].split(",")}
    frontend_status = frontend_rows[0][9]
    if re.search(r"\b(TBD|planned)\b", frontend_status, re.IGNORECASE):
        raise RuntimeError("unfinished placeholder in current frontend status")
    pending_frontend_status = re.compile(
        r"\s*HOST-02\s+Pending\s*;\s*frontend\s+QUAL-03\s+Pending\s*;\s*"
        r"actual-app identities and observations unavailable\s*;\s*frontend claim unknown\s*",
        re.IGNORECASE,
    )
    if (
        not {"HOST-02", "QUAL-03"}.issubset(requirement_ids)
        or pending_frontend_status.fullmatch(frontend_status) is None
    ):
        raise RuntimeError("HOST-02 and frontend QUAL-03 must remain Pending/unknown in the current validation map")


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
    source_snapshot = receipt.get("identity", {}).get("source_snapshot", {})
    if source_snapshot.get("status") == "pass":
        validate_snapshot_record(source_snapshot)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    temporary_path = OUTPUT / "receipt.json.tmp"
    receipt_path = OUTPUT / "receipt.json"
    def sanitize(value: Any) -> Any:
        if isinstance(value, str):
            return redact(value)
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, tuple):
            return [sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        return value

    safe_receipt = sanitize(receipt)
    temporary_path.write_text(json.dumps(safe_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary_path.replace(receipt_path)
    print(json.dumps({
        "status": safe_receipt["status"], "receipt": "build/playable-qualification/receipt.json",
        "fixture_sha256": safe_receipt.get("fixture", {}).get("sha256", "unknown"),
        "retroarch_status": safe_receipt.get("retroarch_smoke", {}).get("status", "unknown"),
        "reason": safe_receipt.get("reason", ""),
    }, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retroarch", type=Path)
    parser.add_argument("--clean", action="store_true", help="qualify a fresh committed-source snapshot and fresh build/install directories")
    parser.add_argument("--check-docs", action="store_true")
    args = parser.parse_args()
    if args.check_docs and not args.clean:
        try:
            check_docs(ROOT)
        except RuntimeError as error:
            print(str(error), file=sys.stderr)
            return 1
        print("Phase 04 documentation gate passed.")
        return 0
    if args.retroarch is None:
        parser.error("--retroarch is required unless --check-docs is used without --clean")
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
        executing_runner_sha = sha256(Path(__file__).resolve())
        archived_runner_sha = sha256(archived_runner) if archived_runner.is_file() else "unknown"
        runner_matches = archived_runner_sha == executing_runner_sha
        identity["runner_source"] = {
            "status": "pass" if runner_matches else "fail",
            "executing_sha256": executing_runner_sha,
            "archived_sha256": archived_runner_sha,
        }
        if not runner_matches:
            raise SnapshotError("runner-source-mismatch", "executing qualification runner differs from the committed archive")
        verify_snapshot(snapshot)
        identity["source_revision"] = snapshot.commit
        identity["source_snapshot"] = snapshot_record(snapshot)
        validate_snapshot_record(identity["source_snapshot"], repository=ROOT)
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
        # The pinned candidate helper expects ROOT/build/sdk-debug and ROOT/build/ym2610-admission;
        # route that legacy location to ignored output and remove the temporary link after the lane.
        candidate_build_overlay = work / "candidate-generated-build"
        candidate_binary = candidate_build_overlay / "sdk-debug/ym2610_admission_test"
        candidate_binary.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build_roots["shared"] / "ym2610_admission_test", candidate_binary)
        runner.command("ym2610-installed-linkages", [
            sys.executable, str(source_root / "tests/chips/check_ym2610.py"), "link",
            "--both-linkages", "--report", str(report_path),
        ], timeout=1200, source_build_overlay=candidate_build_overlay)
        candidate_report = json.loads(report_path.read_text(encoding="utf-8"))
        candidate_report["build"]["glueyneo_revision"] = snapshot.commit
        candidate_report["build"]["source_snapshot"] = {
            "inventory_sha256": snapshot.digest,
            "archive_sha256": snapshot.archive_sha256,
        }
        for linkage, result in candidate_report.get("linkages", {}).items():
            result["source_revision"] = snapshot.commit
            candidate_report["gates"][f"installed_{linkage}_c_consumer"]["evidence"] = (
                f"{work.relative_to(OUTPUT).as_posix()}/installed/{linkage}"
            )
        report_path.write_text(json.dumps(candidate_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
            "ym2610_candidate_builds": _artifact_tree(work / "installed", OUTPUT),
            "ym2610_direct_test": _artifact_file(work / "candidate-generated-build/sdk-debug/ym2610_admission_test", OUTPUT),
        },
        "unsupported_configurations": ["non-macOS", "architectures other than this host", "unlisted compilers and SDKs"],
    }
    if snapshot is None:
        receipt["identity"]["source_snapshot"] = {"status": "fail", "reason": reason}  # type: ignore[index]
    if runner is None:
        receipt["lanes"] = {}
    if snapshot is not None and runner is not None and shared_core.is_file() and fixture_shared.is_file():
        try:
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
        except Exception as error:
            lane_reason = getattr(error, "reason", "smoke-lane-error")
            receipt["retroarch_smoke"] = {"status": "unknown", "stage": "source-integrity" if isinstance(error, SnapshotError) else "frontend", "reason": lane_reason}
            status = "fail"
            reason = reason or lane_reason
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
            validate_snapshot_record(receipt["identity"]["source_snapshot"], repository=ROOT)  # type: ignore[index]
        except SnapshotError as error:
            receipt["identity"]["source_snapshot"]["status"] = "fail"  # type: ignore[index]
            receipt["identity"]["source_snapshot"]["reason"] = error.reason  # type: ignore[index]
            status = "fail"
            reason = reason or error.reason
    if receipt["identity"]["source_snapshot"].get("status") == "pass":  # type: ignore[index]
        try:
            validate_snapshot_record(receipt["identity"]["source_snapshot"])  # type: ignore[index]
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
