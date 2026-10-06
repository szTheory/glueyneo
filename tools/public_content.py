#!/usr/bin/env python3
"""Bounded public-content and redistribution-rights scanner.

Findings deliberately contain rule identifiers and repository-relative locations,
never the text that matched. A negative result describes this detector's bounded
coverage; it cannot prove that secret material is absent or that rights exist.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 50_000
MAX_HISTORY_OBJECTS = 50_000
BLOCK_SIZE = 1024 * 1024
SOURCE_PATHS = (
    ".release-please-manifest.json", "CMakeLists.txt", "CMakePresets.json",
    "LICENSE", "README.md", "cmake", "docs", "examples",
    "experiments/owned_cpu", "fixtures/diagnostic", "include", "src",
    "tests", "third_party/unity", "tools/diagnostic", "tools/release_manifest.py",
    "tools/release_state.py",
)
# Repository publication includes workflow and release configuration even
# though the SDK source archive intentionally has a narrower file set.
REPOSITORY_PATHS = SOURCE_PATHS + (".github/workflows", "release-please-config.json")
TEST_SOURCE_PATHS = frozenset({
    "tests/consumers/CMakeLists.txt", "tests/consumers/check_package.py",
    "tests/consumers/header.cpp", "tests/consumers/test_exports.py",
    "tests/consumers/test_release_consumer.py", "tests/cpu/guest_fixture.c",
    "tests/cpu/guest_fixture.h", "tests/cpu/isolation_fixture.h",
    "tests/cpu/isolation_negative.py", "tests/cpu/negative.py",
    "tests/cpu/state_negative.py", "tests/cpu/test_acceptance.py",
    "tests/cpu/test_audit.py", "tests/cpu/test_cold.c", "tests/cpu/test_faults.c",
    "tests/cpu/test_guest.c", "tests/cpu/test_inventory.py",
    "tests/cpu/test_isolation.c", "tests/cpu/test_state.c", "tests/cpu/test_timing.c",
    "tests/fuzz/minimize.py", "tests/fuzz/sdk_mutation.c", "tests/owned_cpu/cold.py",
    "tests/owned_cpu/isolation_fixture.h", "tests/owned_cpu/negative.py",
    "tests/owned_cpu/negative_timing.py", "tests/owned_cpu/test_acceptance.py",
    "tests/owned_cpu/test_cold.c", "tests/owned_cpu/test_contract.py",
    "tests/owned_cpu/test_diagnostic.c", "tests/owned_cpu/test_faults.c",
    "tests/owned_cpu/test_inventory.py", "tests/owned_cpu/test_isolation.c",
    "tests/owned_cpu/test_semantics.c", "tests/owned_cpu/test_state.c",
    "tests/owned_cpu/test_timing.c", "tests/sdk/controls.py", "tests/sdk/guest_fixture.c",
    "tests/sdk/guest_fixture.h", "tests/sdk/test_evidence.py",
    "tests/sdk/test_matrix_evidence.py", "tests/sdk/test_sdk.c",
    "tests/sdk/test_support.h", "tests/workflow/test_ci_policy.py",
    "tests/workflow/test_phase01_admission.py", "tests/workflow/test_phase01_docs.py",
    "tests/workflow/test_public_content.py", "tests/workflow/test_release_recovery.py",
})

PRIVACY_RULES = (
    ("personal-path", re.compile(r"(?i)(?:^|[\s\"'=(@<])/(?:Users|home)/[^\s\"')\]>]+")),
    ("personal-path", re.compile(r"(?i)\b[A-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\s\"')\]>]+")),
    ("personal-path", re.compile(r"(?i)(?:^|[\s\"'=])/(?:private/var|var/folders)/[^\s\"']+")),
    ("private-identity", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("machine-identifier", re.compile(r"(?i)\b(?:serial(?:_number)?|machine_id|hostname|computer_name)\s*[:=]\s*[^\s,}\]]+")),
    ("private-url", re.compile(r"(?i)https?://[^\s/@:]+:[^\s/@]+@[^\s]+")),
    ("private-url", re.compile(r"(?i)https?://(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)(?::\d+)?[^\s]*")),
    ("credential", re.compile(r"(?i)\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("credential", re.compile(r"(?i)\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("credential", re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key|password)\s*[:=]\s*[\"']?[A-Za-z0-9/+_=-]{12,}")),
    ("private-key", re.compile(r"(?i)-{5}BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-{5}")),
    ("private-key", re.compile(r"(?i)-{5}BEGIN PGP PRIVATE KEY BLOCK-{5}")),
)
PUBLIC_EMAILS = {"noreply@github.com"}
SYNTHETIC_PATH_MARKERS = {"private-person"}
SYNTHETIC_EMAIL_SUFFIXES = (".invalid", ".example", ".example.com", ".example.org", ".example.net")
# Exact immutable history objects audited as bounded false positives. These
# dispositions are tied to object IDs, not paths or rule classes globally:
# upstream Musashi contains a public copyright contact; historical redaction
# tests contain synthetic identity/path canaries. A changed blob is scanned.
HISTORY_FINDING_DISPOSITIONS = {
    "007bd7fabaee7b0c171cb38a2581abeacf0f0c15": {
        "path": "third_party/musashi/m68kmake.c", "rules": {"private-identity"},
        "reason": "immutable upstream public copyright contact; preserved source and license history",
    },
    "1c94ae35fe4334c8a1ecbb273a12e1e12a60fa79": {
        "path": "tests/workflow/test_public_content.py", "rules": {"personal-path"},
        "reason": "synthetic path canary used by the historical redaction regression",
    },
}


class ContentError(ValueError):
    """A stable fail-closed reason with no matched content in its message."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_location(location: str) -> str:
    candidate = PurePosixPath(location.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        return "<redacted-location>"
    return candidate.as_posix()


def scan_bytes(data: bytes, location: str) -> dict[str, Any]:
    """Inspect a bounded byte string and return value-free findings."""
    if len(data) > MAX_FILE_BYTES:
        raise ContentError("input-file-limit", "input exceeds the per-file byte limit")
    text = data.decode("utf-8", errors="replace")
    rules: set[str] = set()
    for rule, pattern in PRIVACY_RULES:
        for match in pattern.finditer(text):
            if rule == "private-identity":
                email = match.group(0).lower()
                domain = email.rsplit("@", 1)[-1]
                if (email in PUBLIC_EMAILS or domain.endswith("users.noreply.github.com")
                        or domain in {"invalid", "test", "example", "example.com", "example.org", "example.net"}
                        or domain.endswith(SYNTHETIC_EMAIL_SUFFIXES)):
                    continue
            if rule == "personal-path" and any(f"/{marker}/" in match.group(0) for marker in SYNTHETIC_PATH_MARKERS):
                continue
            rules.add(rule)
    return {"bytes": len(data), "sha256": sha256_bytes(data),
            "findings": ([{"location": _safe_location(location), "rules": sorted(rules)}] if rules else [])}


def _read_regular(path: Path, *, reason_prefix: str = "input") -> bytes:
    try:
        info = path.lstat()
    except OSError as error:
        raise ContentError(f"{reason_prefix}-unreadable", "required input could not be read") from error
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ContentError("input-type", "input must be a regular, unlinked file")
    if info.st_size < 0 or info.st_size > MAX_FILE_BYTES:
        raise ContentError("input-file-limit", "input exceeds the per-file byte limit")
    blocks: list[bytes] = []
    total = 0
    try:
        with path.open("rb") as stream:
            while block := stream.read(BLOCK_SIZE):
                total += len(block)
                if total > MAX_FILE_BYTES:
                    raise ContentError("input-file-limit", "input exceeds the per-file byte limit")
                blocks.append(block)
    except OSError as error:
        raise ContentError(f"{reason_prefix}-unreadable", "required input could not be read") from error
    return b"".join(blocks)


def scan_tree(root: Path, paths: list[str]) -> dict[str, Any]:
    """Read only the explicitly proposed public tree and fail on links/specials."""
    rows: list[dict[str, Any]] = []
    total = 0
    seen: set[str] = set()
    for entry in sorted(paths):
        relative = PurePosixPath(entry)
        if relative.is_absolute() or ".." in relative.parts or entry in seen:
            raise ContentError("source-path", "public source list has an unsafe or duplicate path")
        seen.add(entry)
        target = root.joinpath(*relative.parts)
        try:
            info = target.lstat()
        except OSError as error:
            raise ContentError("source-unreadable", "a proposed public source path is unavailable") from error
        candidates = [target] if stat.S_ISREG(info.st_mode) else sorted(target.rglob("*")) if stat.S_ISDIR(info.st_mode) else []
        if not candidates and not stat.S_ISDIR(info.st_mode):
            raise ContentError("input-type", "public source tree contains a link or special file")
        for path in candidates:
            try:
                mode = path.lstat().st_mode
            except OSError as error:
                raise ContentError("source-unreadable", "a proposed public source file is unavailable") from error
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode) or path.lstat().st_nlink != 1:
                raise ContentError("input-type", "public source tree contains a link or special file")
            rel = path.relative_to(root).as_posix()
            data = _read_regular(path, reason_prefix="source")
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise ContentError("input-total-limit", "public source exceeds the total byte limit")
            result = scan_bytes(data, rel)
            rows.append({"path": rel, **result})
    return {"files": len(rows), "bytes": total, "findings": _findings(rows),
            "inventory_sha256": sha256_bytes(canonical_bytes([{k: row[k] for k in ("path", "sha256", "bytes")} for row in rows]))}


def _findings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((finding for row in rows for finding in row["findings"]),
                  key=lambda item: (item["location"], item["rules"]))


def _is_rights_candidate(path: str) -> bool:
    relative = PurePosixPath(path)
    if path.startswith("third_party/") or path.startswith("fixtures/"):
        return True
    return path.startswith("tests/") and (
        path not in TEST_SOURCE_PATHS or "fixture" in relative.name.lower()
    )


def load_rights_inventory(root: Path = ROOT) -> dict[str, Any]:
    """Read the canonical JSON object embedded in the published inventory page."""
    page = root / "docs/rights-inventory.md"
    try:
        text = page.read_text(encoding="utf-8")
    except OSError as error:
        raise ContentError("rights-unreadable", "rights inventory document could not be read") from error
    blocks = re.findall(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if len(blocks) != 1:
        raise ContentError("rights-schema", "rights inventory must contain one JSON record")
    try:
        inventory = json.loads(blocks[0])
    except json.JSONDecodeError as error:
        raise ContentError("rights-schema", "rights inventory JSON is malformed") from error
    return inventory


def validate_repository_inventory(root: Path = ROOT) -> dict[str, Any]:
    """Bind every fixture/dependency candidate in the source tree to its record."""
    paths = _git_source_paths(root)
    inventory = load_rights_inventory(root)
    actual: dict[str, bytes] = {}
    for relative in paths:
        if _is_rights_candidate(relative):
            actual[relative] = _read_regular(root / relative, reason_prefix="source")
    result = validate_inventory(inventory, actual)
    shipped = set(paths)
    for item in inventory["items"]:
        if item["notice"] not in shipped:
            raise ContentError("rights-notice", "a required license notice is absent from public source")
    return result


def _validate_archive_inventory(rows: list[dict[str, Any]], root: Path = ROOT) -> dict[str, Any] | None:
    normalized: dict[str, dict[str, Any]] = {}
    all_paths: set[str] = set()
    for row in rows:
        path = row["path"]
        if path.startswith("glueyneo-source/"):
            path = path[len("glueyneo-source/"):]
        all_paths.add(path)
        if _is_rights_candidate(path):
            normalized[path] = row
    if not normalized:
        return None
    inventory = load_rights_inventory(root)
    declared = {item.get("path"): item for item in inventory.get("items", []) if isinstance(item, dict)}
    if set(normalized) != set(declared):
        raise ContentError("rights-path-set", "release archive contains unknown or missing fixture/dependency paths")
    for path, row in normalized.items():
        item = declared[path]
        if item.get("rights") != "affirmative":
            raise ContentError("rights-unknown", "release archive item lacks affirmative redistribution evidence")
        if row.get("sha256") != item.get("sha256"):
            raise ContentError("rights-digest", "release archive item differs from its recorded digest")
        if item.get("notice") not in all_paths:
            raise ContentError("rights-notice", "release archive omits a required license notice")
    return {"passed": True, "items": len(normalized),
            "inventory_sha256": sha256_bytes(canonical_bytes(inventory))}


def scan_archive(path: Path) -> dict[str, Any]:
    """Inspect every member without extraction, before reading member bodies."""
    try:
        info = path.lstat()
    except OSError as error:
        raise ContentError("archive-unreadable", "release archive could not be read") from error
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ContentError("input-type", "release archive must be a regular, unlinked file")
    if info.st_size > MAX_TOTAL_BYTES:
        raise ContentError("archive-limit", "compressed archive exceeds the byte limit")
    rows: list[dict[str, Any]] = []
    total = 0
    try:
        with tarfile.open(path, "r:*") as archive:
            members = archive.getmembers()
            if not members or len(members) > MAX_MEMBERS:
                raise ContentError("archive-count", "release archive member count is empty or exceeds the limit")
            names: set[str] = set()
            for member in members:
                name = member.name
                pure = PurePosixPath(name)
                if (not name or "\\" in name or "\x00" in name or pure.is_absolute()
                        or re.match(r"^[A-Za-z]:", name) or any(part in {"", ".", ".."} for part in name.split("/"))):
                    raise ContentError("archive-path", "release archive contains an unsafe member path")
                if name in names:
                    raise ContentError("archive-duplicate", "release archive contains duplicate member names")
                names.add(name)
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ContentError("archive-link", "release archive contains a link or special member")
                if member.size < 0 or member.size > MAX_FILE_BYTES:
                    raise ContentError("archive-file-limit", "release archive member exceeds the per-file byte limit")
                total += member.size
                if total > MAX_TOTAL_BYTES:
                    raise ContentError("archive-total-limit", "release archive exceeds the total uncompressed byte limit")
            for member in members:
                if not member.isfile():
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    raise ContentError("archive-unreadable", "release archive member body is unavailable")
                with stream:
                    data = stream.read(member.size + 1)
                if len(data) != member.size:
                    raise ContentError("archive-unreadable", "release archive member body is truncated or oversized")
                rows.append({"path": member.name, **scan_bytes(data, member.name)})
    except ContentError:
        raise
    except (OSError, tarfile.TarError, EOFError) as error:
        raise ContentError("archive-unreadable", "release archive is malformed or unreadable") from error
    rights = _validate_archive_inventory(rows)
    return {"files": len(rows), "members": len(members), "bytes": total, "findings": _findings(rows),
            "rights": rights,
            "inventory_sha256": sha256_bytes(canonical_bytes([{k: row[k] for k in ("path", "sha256", "bytes")} for row in rows]))}


def validate_inventory(inventory: Any, actual: dict[str, bytes]) -> dict[str, Any]:
    """Require exact path/digest coverage and affirmative item-level rights."""
    if not isinstance(inventory, dict) or inventory.get("schema") != 1 or not isinstance(inventory.get("items"), list):
        raise ContentError("rights-schema", "rights inventory schema is invalid")
    declared: dict[str, dict[str, Any]] = {}
    for item in inventory["items"]:
        if not isinstance(item, dict):
            raise ContentError("rights-schema", "rights inventory item is malformed")
        path = item.get("path")
        if not isinstance(path, str) or path in declared or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            raise ContentError("rights-path", "rights inventory contains an unsafe or duplicate path")
        declared[path] = item
        if item.get("rights") != "affirmative":
            raise ContentError("rights-unknown", "shipped item lacks affirmative redistribution evidence")
        if not all(isinstance(item.get(key), str) and item[key] for key in
                   ("kind", "license", "provenance", "source_revision", "notice")):
            raise ContentError("rights-record", "shipped item is missing its license, provenance, or notice")
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", item["source_revision"]) is None:
            raise ContentError("rights-record", "source revision must be an immutable Git object ID")
        if re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))) is None:
            raise ContentError("rights-record", "shipped item digest is malformed")
    if set(declared) != set(actual):
        raise ContentError("rights-path-set", "shipped content differs from the exact rights inventory")
    for path, data in actual.items():
        if sha256_bytes(data) != declared[path]["sha256"]:
            raise ContentError("rights-digest", "shipped item bytes differ from the rights inventory")
    return {"passed": True, "items": len(declared),
            "inventory_sha256": sha256_bytes(canonical_bytes(inventory))}


def _git_history(root: Path, revision: str = "--all") -> tuple[bytes, list[dict[str, Any]], int, int]:
    """Scan reachable commit metadata and every unique reachable blob body."""
    try:
        result = subprocess.run(["git", "log", revision, "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%s%x00%b"],
                                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContentError("history-unreadable", "publishable commit metadata could not be inspected") from error
    if result.returncode or not result.stdout:
        raise ContentError("history-unreadable", "publishable history is empty or unavailable")
    if len(result.stdout) > MAX_TOTAL_BYTES:
        raise ContentError("history-limit", "publishable history metadata exceeds the byte limit")
    metadata = result.stdout
    try:
        listing = subprocess.run(["git", "rev-list", "--objects", revision], cwd=root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContentError("history-unreadable", "publishable blob list could not be inspected") from error
    if listing.returncode:
        raise ContentError("history-unreadable", "publishable blob list could not be inspected")
    if len(listing.stdout) > MAX_TOTAL_BYTES:
        raise ContentError("history-limit", "publishable history object list exceeds the byte limit")
    object_paths: dict[str, str] = {}
    for line in listing.stdout.splitlines():
        parts = line.split(b" ", 1)
        object_id = parts[0]
        if re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", object_id):
            oid = object_id.decode("ascii")
            path = parts[1].decode("utf-8", errors="replace") if len(parts) == 2 else ""
            object_paths.setdefault(oid, path)
            if len(object_paths) > MAX_HISTORY_OBJECTS:
                raise ContentError("history-object-limit", "reachable history exceeds the object count limit")
    if not object_paths:
        raise ContentError("history-unreadable", "publishable history contains no reachable objects")
    input_data = ("\n".join(sorted(object_paths)) + "\n").encode("ascii")
    try:
        checked = subprocess.run(["git", "cat-file", "--batch-check"], cwd=root, input=input_data,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContentError("history-unreadable", "reachable history objects could not be inspected") from error
    if checked.returncode:
        raise ContentError("history-unreadable", "reachable history objects could not be inspected")
    blobs: list[tuple[str, int]] = []
    blob_bytes = 0
    for line in checked.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3 or fields[1] == b"missing":
            raise ContentError("history-unreadable", "reachable history object metadata is incomplete")
        if fields[1] != b"blob":
            continue
        try:
            size = int(fields[2])
        except ValueError as error:
            raise ContentError("history-unreadable", "reachable blob size is malformed") from error
        if size < 0 or size > MAX_FILE_BYTES:
            raise ContentError("history-file-limit", "reachable history blob exceeds the per-file byte limit")
        blob_bytes += size
        if blob_bytes > MAX_TOTAL_BYTES:
            raise ContentError("history-total-limit", "reachable history blobs exceed the total byte limit")
        blobs.append((fields[0].decode("ascii"), size))
    if len(blobs) > MAX_HISTORY_OBJECTS:
        raise ContentError("history-object-limit", "reachable history exceeds the object count limit")
    if len(metadata) + blob_bytes > MAX_TOTAL_BYTES:
        raise ContentError("history-total-limit", "reachable history metadata and blobs exceed the total byte limit")
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
        assert process.stdin is not None and process.stdout is not None
        dispositions: list[dict[str, Any]] = []
        for object_id, size in blobs:
            process.stdin.write(object_id.encode("ascii") + b"\n")
            process.stdin.flush()
            header = process.stdout.readline(256)
            fields = header.rstrip(b"\n").split()
            if len(fields) != 3 or fields[0].decode("ascii", errors="ignore") != object_id or fields[1] != b"blob":
                raise ContentError("history-unreadable", "reachable history blob stream is malformed")
            body = process.stdout.read(size)
            if len(body) != size or process.stdout.read(1) != b"\n":
                raise ContentError("history-unreadable", "reachable history blob stream is truncated")
            path = object_paths.get(object_id, "")
            result = scan_bytes(body, f"history/{path}" if path else "history/reachable-blob")
            disposition = HISTORY_FINDING_DISPOSITIONS.get(object_id)
            if disposition is not None:
                actual_rules = set(result["findings"][0]["rules"] if result["findings"] else ())
                if path != disposition["path"] or actual_rules != disposition["rules"]:
                    raise ContentError("history-disposition", "a provenance-bound history disposition no longer matches its object")
                dispositions.append({"object": object_id, "location": _safe_location(f"history/{path}"),
                                     "rules": sorted(disposition["rules"]), "reason": disposition["reason"]})
            elif result["findings"]:
                dispositions.extend({"object": object_id, **finding} for finding in result["findings"])
        process.stdin.close()
        if process.wait(timeout=120):
            raise ContentError("history-unreadable", "reachable history blob stream failed")
        process.stdout.close()
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContentError("history-unreadable", "reachable history blobs could not be read") from error
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            if process.stdout is not None and not process.stdout.closed:
                process.stdout.close()
    return metadata, dispositions, blob_bytes, len(blobs)


def _git_source_paths(root: Path) -> list[str]:
    try:
        result = subprocess.run(["git", "ls-files", "-z", "--", *REPOSITORY_PATHS], cwd=root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContentError("source-unreadable", "the proposed source archive file list is unavailable") from error
    if result.returncode:
        raise ContentError("source-unreadable", "the proposed source archive file list is unavailable")
    paths = [raw.decode("utf-8") for raw in result.stdout.split(b"\0") if raw]
    if not paths:
        raise ContentError("source-unreadable", "the proposed public source file list is empty")
    return sorted(paths)


def _scan_blob(data: bytes, location: str) -> dict[str, Any]:
    total = len(data)
    if total > MAX_TOTAL_BYTES:
        raise ContentError("input-total-limit", "input class exceeds the total byte limit")
    rows = []
    for offset in range(0, total, MAX_FILE_BYTES):
        rows.append(scan_bytes(data[offset:offset + MAX_FILE_BYTES], location))
    if not rows:
        rows.append(scan_bytes(b"", location))
    findings = _findings(rows)
    return {"files": 1, "bytes": total, "findings": findings}


def scan_inputs(*, root: Path = ROOT, paths: list[str] | None = None,
                logs: list[Path] | None = None, archives: list[Path] | None = None,
                history_text: str | None = None, history_revision: str = "--all") -> dict[str, Any]:
    """Scan source, history, captured logs and each supplied release archive."""
    root = root.resolve()
    selected = paths if paths is not None else _git_source_paths(root)
    source = scan_tree(root, selected)
    rights = validate_repository_inventory(root) if paths is None else None
    if history_text is not None:
        history_data = history_text.encode()
        history = _scan_blob(history_data, "history/commit-metadata")
        history_dispositions = []
    else:
        history_data, history_dispositions, history_blob_bytes, history_blob_count = _git_history(root, history_revision)
        history = _scan_blob(history_data, "history/commit-metadata")
        history["bytes"] += history_blob_bytes
        history["files"] += history_blob_count
    log_rows = []
    log_bytes = 0
    for index, log in enumerate(logs or []):
        data = _read_regular(log, reason_prefix="log")
        log_bytes += len(data)
        if log_bytes > MAX_TOTAL_BYTES:
            raise ContentError("log-total-limit", "captured CI logs exceed the total byte limit")
        result = scan_bytes(data, f"ci-log-{index + 1}")
        log_rows.append({"bytes": result["bytes"], "findings": result["findings"]})
    archive_rows = []
    archive_bytes = 0
    for index, archive in enumerate(archives or []):
        result = scan_archive(archive)
        archive_bytes += result["bytes"]
        archive_rows.append({"files": result["files"], "members": result["members"], "bytes": result["bytes"], "findings": result["findings"]})
    counts = {
        "source": {"files": source["files"], "bytes": source["bytes"]},
        "history": {"files": history["files"], "bytes": history["bytes"]},
        "logs": {"files": len(log_rows), "bytes": log_bytes},
        "archives": {"files": sum(item["files"] for item in archive_rows), "bytes": archive_bytes},
    }
    unresolved_history = [row for row in history_dispositions if "reason" not in row]
    finding_dispositions = [row for row in history_dispositions if "reason" in row]
    findings = source["findings"] + history["findings"] + unresolved_history + [f for row in log_rows + archive_rows for f in row["findings"]]
    findings.sort(key=lambda item: (item["location"], item["rules"]))
    return {"schema": 1, "outcome": "fail" if findings else "pass", "findings": findings,
            "rights": rights, "history_dispositions": finding_dispositions,
            "counts": counts, "detector_negative_only": True,
            "coverage": {"logs_supplied": len(log_rows), "archives_supplied": len(archive_rows),
                         "history_mode": "all reachable refs" if history_text is None else "synthetic supplied input"},
            "limits": {"file_bytes": MAX_FILE_BYTES, "total_bytes": MAX_TOTAL_BYTES, "archive_members": MAX_MEMBERS}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--log", type=Path, action="append", default=[])
    parser.add_argument("--archive", type=Path, action="append", default=[])
    parser.add_argument("--history-revision", default="--all")
    parser.add_argument("--json", type=Path, help="write canonical redacted JSON report here")
    args = parser.parse_args(argv)
    try:
        report = scan_inputs(root=args.root, logs=args.log, archives=args.archive,
                             history_revision=args.history_revision)
    except ContentError as error:
        report = {"schema": 1, "outcome": "fail", "reason": error.reason,
                  "message": str(error), "detector_negative_only": True}
        output = canonical_bytes(report)
        if args.json:
            args.json.write_bytes(output)
        else:
            sys.stdout.buffer.write(output)
        return 2
    output = canonical_bytes(report)
    if args.json:
        args.json.write_bytes(output)
    else:
        sys.stdout.buffer.write(output)
    return 0 if report["outcome"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
