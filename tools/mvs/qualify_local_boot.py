#!/usr/bin/env python3
"""Run bounded, private MVS import/guest qualification without logging identity."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile


MAX_ARCHIVE_BYTES = 96 * 1024 * 1024
MAX_COMBINED_BYTES = 128 * 1024 * 1024
MAX_ENTRY_BYTES = 8 * 1024 * 1024
IMPORT_COMBINED_ARCHIVE_BYTES = 128 * 1024 * 1024
IMPORT_COMBINED_EXPANDED_BYTES = 128 * 1024 * 1024
QUALIFIER_BUILD_TIMEOUT_SECONDS = 180
IMPORT_TIMEOUT_SECONDS = 30
NATIVE_QUALIFICATION_TIMEOUT_SECONDS = 120
FRONTEND_CORE_BUILD_TIMEOUT_SECONDS = 180
QUALIFICATION_REPORT_MAX_BYTES = 1024 * 1024
MAX_ACTIVE_FRAMES = 3600
MAX_ACTIVE_INPUT_EVENTS = 64
MAX_ACTIVE_SCHEDULE_BYTES = 4096
MAX_ACTIVE_CAPTURE_FRAMES = 6
ACTIVE_SCENE_HUD_FOREGROUND_THRESHOLD = 180
ACTIVE_INPUT_MASK = 0x3FF
QUALIFIER_TARGETS = ("mvs_importer", "mvs_qualify")
QUALIFIER_PRESET = "owned-debug"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIGURED_IMPORTER_PATH = PROJECT_ROOT / "build" / "owned-debug" / (
    "mvs_importer.exe" if os.name == "nt" else "mvs_importer")
DEFAULT_IMPORTER_ARGUMENT = CONFIGURED_IMPORTER_PATH.relative_to(PROJECT_ROOT).as_posix()
CONFIGURED_QUALIFIER_PATH = PROJECT_ROOT / "build" / "owned-debug" / (
    "mvs_qualify.exe" if os.name == "nt" else "mvs_qualify")
NINJA_UP_TO_DATE = "ninja: no work to do."


class QualifierFreshness(str):
    """A build status plus the artifact identity captured from that build."""

    importer_identity: dict[str, str] | None
    qualifier_identity: dict[str, str] | None

    def __new__(cls, status: str,
                importer_identity: dict[str, str] | None = None,
                qualifier_identity: dict[str, str] | None = None) -> "QualifierFreshness":
        result = str.__new__(cls, status)
        result.importer_identity = importer_identity
        result.qualifier_identity = qualifier_identity
        return result


class ImporterIdentityChanged(RuntimeError):
    """A configured importer changed after its build identity was captured."""


GAME_IDENTITIES = {
    "250-p1.p1": (0x100000, 0x81f1f60b, "4c19f2e9824e606178ac1c9d4b0516fbaa625035"),
    "250-p2.ep1": (0x400000, 0x1fda2e12, "18aaa7a3ba8da99f78c430e9be69ccde04bc04d9"),
    "250-s1.s1": (0x20000, 0xfb6f441d, "2cc392ecde5d5afb28ddbaa1030552b48571dcfb"),
    "250-m1.m1": (0x20000, 0xfd42a842, "55769bad4860f64ef53a333e0da9e073db483d6a"),
    "250-v1.v1": (0x400000, 0xc79ede73, "ebfcc67204ff9677cf7972fd5b6b7faabf07280c"),
    "250-v2.v2": (0x400000, 0xea9aabe1, "526c42ca9a388f7435569400e2f132e2724c71ff"),
    "250-v3.v3": (0x200000, 0x2ca65102, "45979d1edb1fc774a415d9386f98d7cb252a2043"),
    "250-c1.c1": (0x800000, 0x09a52c6f, "c3e8a8ccdac0f8bddc4c3413277626532405fae2"),
    "250-c2.c2": (0x800000, 0x31679821, "554f600a3aa09c16c13c625299b087a79d0d15c5"),
    "250-c3.c3": (0x800000, 0xfd602019, "c56646c62387bc1439d46610258c755beb8d7dd8"),
    "250-c4.c4": (0x800000, 0x31354513, "31be8ea2498001f68ce4b06b8b90acbf2dcab6af"),
    "250-c5.c5": (0x800000, 0xa4b56124, "d41069856df990a1a99d39fb263c8303389d5475"),
    "250-c6.c6": (0x800000, 0x83e3e69d, "39be66287696829d243fb71b3fb8b7dc2bc3298f"),
}


def pair_fits_import_limits(game_bytes: int, bios_bytes: int,
                            game_expanded: int, bios_expanded: int) -> bool:
    return (game_bytes <= MAX_ARCHIVE_BYTES and bios_bytes <= MAX_ARCHIVE_BYTES and
            game_bytes + bios_bytes <= IMPORT_COMBINED_ARCHIVE_BYTES and
            game_expanded + bios_expanded <= IMPORT_COMBINED_EXPANDED_BYTES)


def archive_expanded_size(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return sum(item.file_size for item in archive.infolist())


def _resolve_executable_path(value: str | Path | list[str] | None) -> Path | None:
    """Resolve one existing executable path; command vectors are never shell syntax."""
    if value is None:
        candidate = CONFIGURED_IMPORTER_PATH
    elif isinstance(value, (list, tuple)):
        if len(value) != 1 or not isinstance(value[0], str) or not value[0]:
            return None
        candidate = Path(value[0])
    elif isinstance(value, (str, Path)) and str(value):
        candidate = Path(value)
    else:
        return None
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        return None
    return resolved


def _canonical_importer_command(importer: str | Path | list[str] | None = None) -> str | None:
    """Return the configured executable only when the request names that same file."""
    candidate = _resolve_executable_path(importer)
    configured = _resolve_executable_path(CONFIGURED_IMPORTER_PATH)
    if candidate is None or configured is None:
        return None
    try:
        if not os.path.samefile(candidate, configured):
            return None
    except OSError:
        return None
    return str(configured)


def _production_importer_identity() -> dict[str, str] | None:
    configured = _resolve_executable_path(CONFIGURED_IMPORTER_PATH)
    if configured is None:
        return None
    try:
        digest = hashlib.sha256(configured.read_bytes()).hexdigest()
    except OSError:
        return None
    return {"scope": "production", "path": str(configured), "sha256": digest}


def _importer_identity_matches(importer: str | Path | list[str] | None,
                               identity: object) -> bool:
    if not isinstance(identity, dict) or identity.get("scope") != "production":
        return False
    expected_path = identity.get("path")
    expected_digest = identity.get("sha256")
    if (not isinstance(expected_path, str) or
            not re.fullmatch(r"[0-9a-f]{64}", str(expected_digest or ""))):
        return False
    command = _canonical_importer_command(importer)
    if command is None or command != expected_path:
        return False
    try:
        return hashlib.sha256(Path(command).read_bytes()).hexdigest() == expected_digest
    except OSError:
        return False


def checked_importer_command(importer: str | Path | list[str] | None = None,
                             *, identity: object = None) -> str | None:
    """Return the configured importer only while its captured build bytes match."""
    if not _importer_identity_matches(importer, identity):
        return None
    return _canonical_importer_command(importer)


def _production_qualifier_identity() -> dict[str, str] | None:
    configured = _resolve_executable_path(CONFIGURED_QUALIFIER_PATH)
    if configured is None:
        return None
    try:
        return {"scope": "production", "path": str(configured),
                "sha256": hashlib.sha256(configured.read_bytes()).hexdigest()}
    except OSError:
        return None


def _production_evaluator_identity() -> dict[str, str] | None:
    """Bind frozen local scene predicates to the evaluator source bytes."""
    try:
        source = Path(__file__).resolve(strict=True)
        return {"scope": "production", "path": str(source),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    except (OSError, RuntimeError):
        return None


def _frontend_failure_return_code(error: BaseException) -> int | None:
    """Project only a numeric child exit/signal code from a frontend diagnostic."""
    diagnostic = getattr(error, "diagnostic", None)
    if not isinstance(diagnostic, dict):
        return None
    value = diagnostic.get("return_code")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _private_frontend_failure_diagnostic(
        error: BaseException, capture_dir: Path) -> dict[str, object] | None:
    """Bind bounded failure facts to the two ignored logs from this frontend run."""
    diagnostic = getattr(error, "diagnostic", None)
    if not isinstance(diagnostic, dict):
        return None
    stage = diagnostic.get("stage")
    if stage not in {
            "identity", "input", "pre-launch", "launch", "video", "unload",
            "first-screenshot", "pid-record", "unknown"}:
        return None
    return_code = diagnostic.get("return_code")
    if not isinstance(return_code, int) or isinstance(return_code, bool):
        return_code = None
    survived = diagnostic.get("survived_before_screenshot")
    if survived is not None and type(survived) is not bool:
        survived = None
    log_status = diagnostic.get("frontend_log_status")
    if log_status not in {"pass", "fail", "unknown"}:
        log_status = "unknown"
    hashes: list[str] = []
    supplied_paths = diagnostic.get("frontend_log_paths")
    supplied_hashes = diagnostic.get("frontend_log_sha256")
    expected_names = ("retroarch-private.log", "frontend-process-private.log")
    root = Path("local/qualification")
    valid_directory = (
        re.fullmatch(r"local/qualification/phase05-[0-9a-f]{32}-captures",
                     capture_dir.as_posix()) is not None and
        not Path("local").is_symlink() and not root.is_symlink() and
        not capture_dir.is_symlink() and capture_dir.is_dir() and
        capture_dir.parent.resolve() == root.resolve() and ignored(capture_dir))
    if (valid_directory and isinstance(supplied_paths, list) and
            isinstance(supplied_hashes, list) and
            len(supplied_paths) == len(supplied_hashes) == len(expected_names)):
        expected_paths = [capture_dir / name for name in expected_names]
        try:
            for path_value, expected, digest in zip(
                    supplied_paths, expected_paths, supplied_hashes):
                resolved = Path(path_value).resolve(strict=True)
                if (resolved != expected.resolve(strict=True) or
                        expected.is_symlink() or not ignored(expected) or
                        not isinstance(digest, str) or
                        not re.fullmatch(r"[0-9a-f]{64}", digest) or
                        hashlib.sha256(expected.read_bytes()).hexdigest() != digest):
                    hashes = []
                    break
                hashes.append(digest)
        except (OSError, RuntimeError, TypeError, ValueError):
            hashes = []
    if len(hashes) != len(expected_names):
        log_status = "unknown"
        hashes = []
    return {
        "stage": stage,
        "return_code": return_code,
        "survived_before_screenshot": survived,
        "output_available": diagnostic.get("output_available") is True,
        "macos_crash_reason_available":
            diagnostic.get("macos_crash_reason_available") is True,
        "frontend_log_status": log_status,
        "frontend_log_sha256": hashes,
    }


def checked_qualifier_command(*, identity: object) -> str | None:
    """Use only the configured runner whose bytes were captured after rebuilding."""
    current = _production_qualifier_identity()
    if current is None or current != identity:
        return None
    return current["path"]


def checked_synthetic_importer_command(
        importer: str | Path | list[str], identity: object) -> str | None:
    """Return an explicitly synthetic executable only when path and digest match."""
    if not isinstance(identity, dict) or identity.get("importer_identity_scope") != "synthetic":
        return None
    expected = identity.get("synthetic_importer_identity")
    if not isinstance(expected, dict):
        return None
    expected_path_value = expected.get("path")
    candidate = _resolve_executable_path(importer)
    if not isinstance(expected_path_value, str) or not expected_path_value:
        return None
    expected_path = _resolve_executable_path(expected_path_value)
    expected_digest = expected.get("sha256")
    if (candidate is None or expected_path is None or
            not re.fullmatch(r"[0-9a-f]{64}", str(expected_digest or ""))):
        return None
    try:
        if not os.path.samefile(candidate, expected_path):
            return None
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected_digest:
            return None
    except OSError:
        return None
    return str(expected_path)


def synthetic_importer_identity(
        importer: str | Path | list[str], *, expected_path: str | Path,
        expected_sha256: str) -> dict[str, object] | None:
    """Validate an explicitly synthetic test executable without granting production scope."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        return None
    candidate = _resolve_executable_path(importer)
    expected = _resolve_executable_path(expected_path)
    if candidate is None or expected is None:
        return None
    try:
        if not os.path.samefile(candidate, expected):
            return None
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    except OSError:
        return None
    if digest != expected_sha256:
        return None
    return {
        "importer_identity_scope": "synthetic",
        "synthetic_importer_identity": {
            "path": str(candidate),
            "sha256": digest,
        },
    }
BIOS_IDENTITY = ("sp-s2.sp1", 0x20000, 0x9036d879,
                 "4f5ed7105b7128794654ce82b51723e16e389543")
# `mvs_importer --selected` exit codes mapped to fixed report tokens. The
# wrapper never records importer stderr; the class comes from the code alone
# (docs/ownership-and-errors.md "MVS import and load errors").
IMPORT_ERROR_CLASSES = {
    1: "malformed", 2: "unsupported_feature", 3: "limit_exceeded",
    5: "decompress_failed", 6: "memory", 7: "ambiguous",
    8: "missing_input", 9: "unsupported_set", 10: "bios_missing",
    11: "bios_incompatible", 12: "output_failed",
    13: "zoom_incompatible",
}


def import_error_class(returncode: int) -> str:
    """Return the fixed class token for a nonzero importer exit code."""
    return IMPORT_ERROR_CLASSES.get(returncode, "import_failed")


SAFE_RUNNER_STATUSES = frozenset({
    "missing_audio_region", "mvs_bus_access_fault", "native_execution_error",
    "unsupported_guest_event", "guest_stopped",
    "guest_instruction_budget_exhausted", "attract_start",
    "active_frames_completed", "start_input_not_observed",
})
MAX_VIDEO_ADVANCE_FRAMES = 600
PRIVATE_VIDEO_ACTIVITY_FIELDS = frozenset({
    "nonzero_vram_words", "fixed_tilemap_words", "sprite_words",
    "palette_entries", "visible_sprites", "visible_nonfull_y_zoom_samples",
    "frame_count", "backdrop_palette_nonzero", "video_ram_offset",
    "video_ram_modulo", "palette_bank_selected", "screen_shadow",
    "video_auto_animation_speed", "video_auto_animation_disabled",
    "display_position_interrupt_control",
})


def validated_private_video_activity(value: object) -> dict[str, int] | None:
    """Validate the exact native private-video activity schema and integer bounds."""
    if not isinstance(value, dict) or set(value) != PRIVATE_VIDEO_ACTIVITY_FIELDS:
        return None
    if any(type(field_value) is not int or not 0 <= field_value <= 0xFFFFFFFF
           for field_value in value.values()):
        return None
    return value


def _private_video_activity(stderr: str) -> dict[str, int] | None:
    """Accept only the native qualifier's bounded, private diagnostic object."""
    try:
        decoded = json.loads(stderr)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(decoded, dict) or set(decoded) != {"private_video_activity"}:
        return None
    return validated_private_video_activity(decoded["private_video_activity"])


SCRIPTED_START_INPUT_SCRIPT = "coin@1,start@600"

def safe_flat_member(name: str) -> bool:
    return (1 <= len(name) < 64 and name[0] != "." and
            all(character.isascii() and
                (character.isalnum() or character in "._-")
                for character in name))


def _extra_fields_valid(extra: bytes) -> bool:
    cursor = 0
    while cursor < len(extra):
        if len(extra) - cursor < 4:
            return False
        identifier, length = struct.unpack_from("<HH", extra, cursor)
        cursor += 4
        if length > len(extra) - cursor or identifier == 1:  # ZIP64
            return False
        cursor += length
    return True


def _central_directory_matches(archive: zipfile.ZipFile,
                               entries: list[zipfile.ZipInfo],
                               central_end: int) -> bool:
    """Require the entire candidate central extent to match parsed records."""
    central_cursor = archive.start_dir
    for item in entries:
        archive.fp.seek(central_cursor)
        record = archive.fp.read(46)
        if len(record) != 46 or struct.unpack_from("<I", record)[0] != 0x02014B50:
            return False
        flags, method = struct.unpack_from("<HH", record, 8)
        crc, compressed, expanded = struct.unpack_from("<III", record, 16)
        name_length, extra_length, comment_length, disk = struct.unpack_from("<HHHH", record, 28)
        local_offset = struct.unpack_from("<I", record, 42)[0]
        variable = archive.fp.read(name_length + extra_length + comment_length)
        raw_name = item.filename.encode("ascii")
        if (len(variable) != name_length + extra_length + comment_length or
                flags != item.flag_bits or method != item.compress_type or
                crc != item.CRC or compressed != item.compress_size or
                expanded != item.file_size or name_length != len(raw_name) or
                variable[:name_length] != raw_name or disk != 0 or
                local_offset != item.header_offset or
                not _extra_fields_valid(variable[name_length:name_length + extra_length])):
            return False
        central_cursor += 46 + len(variable)
    return central_cursor == central_end


def _archive_structure_valid(archive: zipfile.ZipFile,
                             entries: list[zipfile.ZipInfo]) -> bool:
    """Match the selected C parser's ZIP32 local/central and extent checks."""
    extents: list[tuple[int, int]] = []
    try:
        archive.fp.seek(0, 2)
        total_size = archive.fp.tell()
        tail_length = min(total_size, 65557)
        archive.fp.seek(total_size - tail_length)
        tail = archive.fp.read(tail_length)
        eocd_candidates: list[int] = []
        cursor = 0
        while True:
            position = tail.find(b"PK\x05\x06", cursor)
            if position < 0:
                break
            cursor = position + 1
            if position + 22 > len(tail):
                continue
            disk, central_disk, disk_count, total_count, central_size, central_offset, comment = \
                struct.unpack_from("<HHHHIIH", tail, position + 4)
            absolute = total_size - tail_length + position
            if (absolute + 22 + comment == total_size and disk == 0 and
                    central_disk == 0 and disk_count == total_count == len(entries) and
                    central_offset + central_size == absolute and
                    central_offset == archive.start_dir and
                    _central_directory_matches(archive, entries, absolute)):
                eocd_candidates.append(absolute)
        if len(eocd_candidates) != 1:
            return False
        for item in entries:
            if (not _extra_fields_valid(item.extra) or item.flag_bits & ~0x0806 or
                    (item.compress_type != zipfile.ZIP_DEFLATED and item.flag_bits & 0x0006)):
                return False
            if item.header_offset < 0 or item.header_offset + 30 > archive.start_dir:
                return False
            archive.fp.seek(item.header_offset)
            header = archive.fp.read(30)
            if len(header) != 30 or struct.unpack_from("<I", header)[0] != 0x04034B50:
                return False
            flags, method = struct.unpack_from("<HH", header, 6)
            crc, compressed, expanded = struct.unpack_from("<III", header, 14)
            name_length, extra_length = struct.unpack_from("<HH", header, 26)
            variable = archive.fp.read(name_length + extra_length)
            if len(variable) != name_length + extra_length:
                return False
            raw_name = item.filename.encode("ascii")
            if (flags != item.flag_bits or method != item.compress_type or
                    crc != item.CRC or compressed != item.compress_size or
                    expanded != item.file_size or name_length != len(raw_name) or
                    variable[:name_length] != raw_name or
                    not _extra_fields_valid(variable[name_length:])):
                return False
            start = item.header_offset
            end = start + 30 + name_length + extra_length + compressed
            if end > archive.start_dir:
                return False
            extents.append((start, end))
        for index, (start, end) in enumerate(extents):
            if any(start < other_end and other_start < end
                   for other_start, other_end in extents[index + 1:]):
                return False
        return True
    except (OSError, UnicodeEncodeError, struct.error):
        return False


def identify_archive(path: Path) -> str | None:
    """Classify a bounded ZIP by public content while keeping local values private."""
    try:
        if path.stat().st_size > MAX_ARCHIVE_BYTES:
            return None
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > 64 or sum(item.file_size for item in entries) > MAX_COMBINED_BYTES:
                return None
            if not _archive_structure_valid(archive, entries):
                return None
            names = [item.filename for item in entries]
            if len(set(names)) != len(names) or any(item.file_size > MAX_ENTRY_BYTES for item in entries):
                return None
            if any(not safe_flat_member(item.filename) or
                   item.flag_bits & ~0x0806 or
                   (item.compress_type != zipfile.ZIP_DEFLATED and item.flag_bits & 0x0006) or
                   item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                   for item in entries):
                return None
            if set(names) == set(GAME_IDENTITIES):
                expected = GAME_IDENTITIES
                if any(next(item for item in entries if item.filename == name).file_size != identity[0]
                       for name, identity in expected.items()):
                    return None
                for item in entries:
                    size, crc, digest = expected[item.filename]
                    if item.CRC != crc:
                        return None
                    actual = hashlib.sha1()
                    measured = 0
                    with archive.open(item) as source:
                        while chunk := source.read(1024 * 1024):
                            measured += len(chunk)
                            if measured > size:
                                return None
                            actual.update(chunk)
                    if measured != size or actual.hexdigest() != digest:
                        return None
                return "game"
            if names.count(BIOS_IDENTITY[0]) != 1:
                return None
            for item in entries:
                if item.filename != BIOS_IDENTITY[0]:
                    # Drain and validate CRC for permitted nonselected catalog entries.
                    with archive.open(item) as source:
                        while source.read(1024 * 1024):
                            pass
                    continue
                if item.file_size != BIOS_IDENTITY[1] or item.CRC != BIOS_IDENTITY[2]:
                    return None
                actual = hashlib.sha1()
                with archive.open(item) as source:
                    while chunk := source.read(1024 * 1024):
                        actual.update(chunk)
                if actual.hexdigest() != BIOS_IDENTITY[3]:
                    return None
            return "bios"
    except (OSError, zipfile.BadZipFile, RuntimeError, EOFError, KeyError, ValueError):
        return None


def ignored(path: Path) -> bool:
    result = subprocess.run(["git", "check-ignore", "-q", str(path)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            check=False)
    return result.returncode == 0


PUBLIC_REGISTER_WINDOWS = ((0x300000, 0x3FFFFF), (0x2FFFE0, 0x2FFFFF))
ATTRACT_REJECTION_NAMES = frozenset({
    "NONE", "NO_REQUEST", "WRONG_VALUE", "WRONG_SOURCE", "WRONG_ORDER",
    "TRACE_OVERFLOW",
})
NATIVE_FAILURE_COMPONENTS = frozenset({
    "main_cpu", "sound_cpu", "board", "internal",
})
NATIVE_FAILURE_STAGES = frozenset({
    "observe", "irq_update", "execute", "bus_access", "sound_catchup",
    "watchdog_reset", "timing_accounting",
})
NATIVE_FAILURE_REASONS = frozenset({
    "internal_failure", "bus_failure", "cycle_limit", "invalid_state",
    "clock_overflow", "accounting_mismatch",
})
NATIVE_FAILURE_SITES = frozenset({
    "unknown", "main_observe", "main_irq_update", "main_execution",
    "main_bus_read", "main_bus_write", "sound_memory_read",
    "sound_memory_write", "sound_io_read", "sound_io_write",
    "sound_interrupt_ack", "sound_tick", "sound_reset",
    "ym2610_sample_read", "board_watchdog_reset", "internal_timing",
})
NATIVE_FAILURE_CAUSES = frozenset({
    "unknown", "main_bus_callback", "sound_bus_callback", "z80_tick",
    "z80_reset", "ym2610_callback", "owned_cpu", "board_reset",
    "timing_accounting",
})
NATIVE_FAILURE_STATUSES = frozenset({
    "unknown", "z80_invalid_argument", "z80_out_of_memory",
    "z80_bus_failure", "z80_cycle_limit", "z80_invalid_snapshot",
    "ym2610_invalid_argument", "ym2610_no_memory",
    "ym2610_callback_failure", "ym2610_exception", "ym2610_capacity",
    "ym2610_limit", "owned_cpu_invalid_argument",
    "owned_cpu_allocation_failure", "owned_cpu_address_error",
    "owned_cpu_host_fault", "owned_cpu_unsupported_opcode",
    "owned_cpu_budget", "owned_cpu_counter_overflow",
    "owned_cpu_privilege_violation",
})
NATIVE_FAILURE_OPERATIONS = frozenset({"unknown", "read", "write", "interrupt_ack"})
MAX_POLLED_ROWS = 8
UINT64_MAX = 0xFFFFFFFFFFFFFFFF


def _count(value: object) -> bool:
    return type(value) is int and 0 <= value <= UINT64_MAX


def _polled_row(row: object) -> dict[str, object] | None:
    """Keep only {address, reads} rows whose address is a public register."""
    if not isinstance(row, dict) or set(row) != {"address", "reads"}:
        return None
    address, reads = row["address"], row["reads"]
    if (not isinstance(address, str) or not _count(reads) or
            re.fullmatch(r"0x[0-9a-f]{6}", address) is None):
        return None
    numeric = int(address, 16)
    if not any(low <= numeric <= high for low, high in PUBLIC_REGISTER_WINDOWS):
        return None
    return {"address": address, "reads": reads}


def safe_diagnosis(diagnosis: object) -> dict[str, object] | None:
    """Reduce a native stall diagnosis to counts and public register names.

    Unknown keys, wrong types and out-of-range values are dropped one key at a
    time; polled-register rows outside the two public windows are dropped and
    the table is capped at eight rows (docs/mvs-media.md "Stall diagnosis").
    """
    if not isinstance(diagnosis, dict):
        return None
    clean: dict[str, object] = {}
    for key in ("interrupts_taken", "irq_ack_writes", "low_program_window_reads",
                "unmapped_read_count", "polled_untracked_reads"):
        if _count(diagnosis.get(key)):
            clean[key] = diagnosis[key]
    for key, length in (("sr_mask_histogram", 8), ("pc_region_histogram", 5)):
        values = diagnosis.get(key)
        if isinstance(values, list) and len(values) == length and all(_count(v) for v in values):
            clean[key] = list(values)
    rows = diagnosis.get("polled_registers")
    if isinstance(rows, list):
        kept = [row for row in map(_polled_row, rows[:64]) if row is not None]
        clean["polled_registers"] = kept[:MAX_POLLED_ROWS]
    variables = diagnosis.get("bios_variables")
    names = ("system_mode", "user_request", "user_mode")
    if (isinstance(variables, dict) and
            all(type(variables.get(name)) is int and 0 <= variables[name] <= 255
                for name in names)):
        clean["bios_variables"] = {name: variables[name] for name in names}
    rejection = diagnosis.get("attract_rejection")
    if isinstance(rejection, str) and rejection in ATTRACT_REJECTION_NAMES:
        clean["attract_rejection"] = rejection
    return clean


NATIVE_FAILURE_KEYS = frozenset({
    "component", "stage", "reason", "site", "site_valid", "device_cause",
    "device_cause_valid", "underlying_status", "underlying_status_valid",
    "emulated_cycle", "emulated_cycle_valid", "completed_main_instructions",
    "instruction_boundary_valid", "pc", "pc_valid", "opcode", "opcode_valid",
    "operation", "address", "width", "bus_access_valid",
})


def _native_u64(record: dict[object, object], name: str) -> bool:
    return type(record.get(name)) is int and 0 <= record[name] <= UINT64_MAX


def _native_failure_tuple_is_valid(failure: dict[object, object]) -> bool:
    component, stage, reason = failure["component"], failure["stage"], failure["reason"]
    site, cause = failure["site"], failure["device_cause"]
    underlying, operation = failure["underlying_status"], failure["operation"]
    has_bus = failure["bus_access_valid"]

    if component == "main_cpu":
        if stage in {"observe", "irq_update", "execute"}:
            expected_site = {"observe": "main_observe", "irq_update": "main_irq_update",
                             "execute": "main_execution"}[stage]
            cpu_execution_statuses = {
                "unknown", "owned_cpu_invalid_argument",
                "owned_cpu_allocation_failure", "owned_cpu_address_error",
                "owned_cpu_privilege_violation", "owned_cpu_host_fault",
                "owned_cpu_unsupported_opcode", "owned_cpu_counter_overflow",
            }
            status_valid = (underlying in cpu_execution_statuses
                            if stage == "execute" else underlying == "unknown")
            return (reason == "internal_failure" and site == expected_site and
                    cause == "owned_cpu" and status_valid and not has_bus)
        if stage == "bus_access":
            return (reason == "bus_failure" and
                    site in {"main_bus_read", "main_bus_write"} and
                    cause == "main_bus_callback" and underlying == "unknown" and
                    operation == ("read" if site == "main_bus_read" else "write") and
                    failure["width"] in {1, 2} and has_bus)
        return False

    if component == "sound_cpu":
        if stage == "bus_access" and reason == "bus_failure":
            if (site == "sound_tick" and cause == "z80_tick" and
                    underlying == "z80_bus_failure"):
                return not has_bus
            z80_bus_sites = {
                "sound_memory_read": "read", "sound_memory_write": "write",
                "sound_io_read": "read", "sound_io_write": "write",
                "sound_interrupt_ack": "interrupt_ack",
            }
            if (cause == "sound_bus_callback" and underlying == "z80_bus_failure" and
                    site in z80_bus_sites):
                return operation == z80_bus_sites[site] and failure["width"] == 1 and has_bus
            ym_bus_statuses = {
                "ym2610_invalid_argument", "ym2610_no_memory",
                "ym2610_callback_failure", "ym2610_exception",
                "ym2610_capacity", "ym2610_limit",
            }
            return (cause == "ym2610_callback" and underlying in ym_bus_statuses and
                    site in {"sound_io_read", "sound_io_write"} and
                    operation == ("read" if site == "sound_io_read" else "write") and
                    failure["width"] == 1 and has_bus)

        if stage != "sound_catchup" or has_bus:
            return False
        z80_statuses = {
            "z80_invalid_argument", "z80_out_of_memory", "z80_bus_failure",
            "z80_cycle_limit", "z80_invalid_snapshot",
        }
        ym_statuses = {
            "ym2610_invalid_argument", "ym2610_no_memory",
            "ym2610_callback_failure", "ym2610_exception",
            "ym2610_capacity", "ym2610_limit",
        }
        if site == "sound_tick" and cause == "z80_tick":
            return ((reason == "cycle_limit" and underlying == "z80_cycle_limit") or
                    (reason == "clock_overflow" and underlying == "unknown") or
                    (reason == "invalid_state" and underlying in z80_statuses - {
                        "z80_bus_failure", "z80_cycle_limit"}))
        if site == "sound_tick" and cause == "ym2610_callback":
            return reason == "internal_failure" and underlying in ym_statuses
        if site == "ym2610_sample_read" and cause == "ym2610_callback":
            return (reason == "internal_failure" and
                    underlying == "ym2610_callback_failure")
        if site == "sound_reset" and cause == "z80_reset":
            return reason == "invalid_state" and underlying in z80_statuses
        if site == "sound_reset" and cause == "ym2610_callback":
            return reason == "internal_failure" and underlying in ym_statuses
        return False

    if component == "board":
        return (stage == "watchdog_reset" and reason == "internal_failure" and
                site == "board_watchdog_reset" and cause == "board_reset" and
                underlying == "unknown" and not has_bus)
    if component == "internal":
        return (stage == "timing_accounting" and reason == "accounting_mismatch" and
                site == "internal_timing" and cause == "timing_accounting" and
                underlying == "unknown" and not has_bus)
    return False


def safe_native_failure(value: object) -> dict[str, object] | None:
    """Accept the exact bounded local failure schema; keep private detail local."""
    if not isinstance(value, dict) or set(value) != NATIVE_FAILURE_KEYS:
        return None
    component, stage, reason = value["component"], value["stage"], value["reason"]
    if (type(component) is not str or component not in NATIVE_FAILURE_COMPONENTS or
            type(stage) is not str or stage not in NATIVE_FAILURE_STAGES or
            type(reason) is not str or reason not in NATIVE_FAILURE_REASONS):
        return None
    site, cause, underlying = value["site"], value["device_cause"], value["underlying_status"]
    operation = value["operation"]
    if (type(site) is not str or site not in NATIVE_FAILURE_SITES or
            type(cause) is not str or cause not in NATIVE_FAILURE_CAUSES or
            type(underlying) is not str or underlying not in NATIVE_FAILURE_STATUSES or
            type(operation) is not str or operation not in NATIVE_FAILURE_OPERATIONS):
        return None
    bool_fields = (
        "site_valid", "device_cause_valid", "underlying_status_valid",
        "emulated_cycle_valid", "instruction_boundary_valid", "pc_valid",
        "opcode_valid", "bus_access_valid",
    )
    if any(type(value[name]) is not bool for name in bool_fields):
        return None
    if not all(_native_u64(value, name) for name in
               ("emulated_cycle", "completed_main_instructions")):
        return None
    numeric_ranges = (("pc", 0xFFFFFFFF), ("address", 0xFFFFFFFF),
                      ("opcode", 0xFFFF), ("width", 0xFF))
    if any(type(value[name]) is not int or not 0 <= value[name] <= maximum
           for name, maximum in numeric_ranges):
        return None
    if (value["site_valid"] != (site != "unknown") or
            value["device_cause_valid"] != (cause != "unknown") or
            value["underlying_status_valid"] != (underlying != "unknown")):
        return None
    if ((not value["emulated_cycle_valid"] and value["emulated_cycle"] != 0) or
            (not value["instruction_boundary_valid"] and
             value["completed_main_instructions"] != 0) or
            (not value["pc_valid"] and value["pc"] != 0) or
            (not value["opcode_valid"] and value["opcode"] != 0)):
        return None
    if value["bus_access_valid"]:
        if operation == "unknown" or value["width"] == 0:
            return None
    elif operation != "unknown" or value["address"] != 0 or value["width"] != 0:
        return None
    valid = (
        (component == "main_cpu" and stage in {"observe", "irq_update", "execute"} and
         reason == "internal_failure") or
        (component == "main_cpu" and stage == "bus_access" and reason == "bus_failure") or
        (component == "sound_cpu" and stage == "bus_access" and reason == "bus_failure") or
        (component == "sound_cpu" and stage == "sound_catchup" and
         reason in {"internal_failure", "cycle_limit", "invalid_state", "clock_overflow"}) or
        (component == "board" and stage == "watchdog_reset" and
         reason == "internal_failure") or
        (component == "internal" and stage == "timing_accounting" and
         reason == "accounting_mismatch")
    )
    if not valid:
        return None
    site_matches_component = (
        (site == "unknown") or
        (component == "main_cpu" and site in {
            "main_observe", "main_irq_update", "main_execution", "main_bus_read",
            "main_bus_write"}) or
        (component == "sound_cpu" and site in {
            "sound_memory_read", "sound_memory_write", "sound_io_read",
            "sound_io_write", "sound_interrupt_ack", "sound_tick", "sound_reset",
            "ym2610_sample_read"}) or
        (component == "board" and site == "board_watchdog_reset") or
        (component == "internal" and site == "internal_timing")
    )
    cause_matches_component = (
        (cause == "unknown") or
        (component == "main_cpu" and cause in {"main_bus_callback", "owned_cpu"}) or
        (component == "sound_cpu" and cause in {
            "sound_bus_callback", "z80_tick", "z80_reset", "ym2610_callback"}) or
        (component == "board" and cause == "board_reset") or
        (component == "internal" and cause == "timing_accounting")
    )
    if not site_matches_component or not cause_matches_component:
        return None
    if not _native_failure_tuple_is_valid(value):
        return None
    return {name: value[name] for name in sorted(NATIVE_FAILURE_KEYS)}


def public_result(report: dict[str, object], *,
                  acceptance: dict[str, str] | None = None) -> dict[str, object]:
    """Project a local native report to finite outcome tokens without private fields."""
    local = safe_result(report, acceptance=acceptance)
    public: dict[str, object] = {"status": local["status"]}
    if type(local.get("guest_executed")) is bool:
        public["guest_executed"] = local["guest_executed"]
    failure = local.get("native_failure")
    if isinstance(failure, dict):
        public["native_failure"] = {
            name: failure[name] for name in ("component", "stage", "reason", "site")
        }
    acceptance = local.get("acceptance")
    if isinstance(acceptance, dict):
        public["acceptance"] = dict(acceptance)
    return public


ACCEPTANCE_PREDICATES = (
    "selected_import", "native_guest", "actual_frontend",
    "recognizable_title", "identity",
)
ACCEPTANCE_KEYS = frozenset((*ACCEPTANCE_PREDICATES, "overall"))
ACCEPTANCE_STATES = frozenset(("pass", "fail", "unknown"))


def _acceptance_overall(states: dict[str, str]) -> str:
    if any(states[key] == "fail" for key in ACCEPTANCE_PREDICATES):
        return "fail"
    if any(states[key] == "unknown" for key in ACCEPTANCE_PREDICATES):
        return "unknown"
    return "pass"


def evaluate_acceptance_predicates(
        *, selected_import_ok: bool | None,
        native_result: dict[str, object] | None,
        frontend_result: dict[str, object] | None,
        identity_ok: bool | None) -> dict[str, str]:
    """Derive independent finite acceptance outcomes from verified local results."""
    selected_import = (
        "pass" if selected_import_ok is True else
        "fail" if selected_import_ok is False else "unknown")
    if native_result is None:
        native_guest = "unknown"
    elif (native_result.get("status") == "attract_start" and
          native_result.get("guest_executed") is True and
          "native_failure" not in native_result):
        requested = native_result.get("video_advance_requested")
        completed = native_result.get("video_advance_completed")
        if requested == MAX_VIDEO_ADVANCE_FRAMES and completed == requested:
            native_guest = "pass"
        elif type(requested) is int and type(completed) is int:
            native_guest = "fail"
        else:
            native_guest = "unknown"
    elif (native_result.get("status") in SAFE_RUNNER_STATUSES and
          (native_result.get("status") != "attract_start" or
           native_result.get("guest_executed") is not True)):
        native_guest = "fail"
    else:
        native_guest = "unknown"
    if frontend_result is None:
        actual_frontend = recognizable_title = "unknown"
    else:
        actual_frontend = frontend_result.get("actual_frontend")
        recognizable_title = frontend_result.get("recognizable_title")
        actual_frontend = (
            actual_frontend if isinstance(actual_frontend, str) and
            actual_frontend in ACCEPTANCE_STATES else "unknown")
        recognizable_title = (
            recognizable_title if isinstance(recognizable_title, str) and
            recognizable_title in ACCEPTANCE_STATES else "unknown")
    identity = ("pass" if identity_ok is True else
                "fail" if identity_ok is False else "unknown")
    states = {
        "selected_import": selected_import,
        "native_guest": native_guest,
        "actual_frontend": actual_frontend,
        "recognizable_title": recognizable_title,
        "identity": identity,
    }
    return {**states, "overall": _acceptance_overall(states)}


def safe_acceptance(value: object) -> dict[str, str] | None:
    """Validate wrapper-owned predicate tokens and their derived overall result."""
    if not isinstance(value, dict) or set(value) != ACCEPTANCE_KEYS:
        return None
    if any(type(value[key]) is not str or value[key] not in ACCEPTANCE_STATES
           for key in ACCEPTANCE_PREDICATES):
        return None
    states = {key: value[key] for key in ACCEPTANCE_PREDICATES}
    if value["overall"] != _acceptance_overall(states):
        return None
    return {**states, "overall": value["overall"]}


def _visual_review_binding(private_evidence: dict[str, object]) -> dict[str, object] | None:
    """Bind a semantic title review to the one current private frontend capture."""
    machine = safe_acceptance(private_evidence.get("acceptance_predicates"))
    if (machine is None or machine["recognizable_title"] != "unknown" or
            machine["overall"] != "unknown" or
            any(machine[key] != "pass" for key in ACCEPTANCE_PREDICATES
                if key != "recognizable_title")):
        return None
    frontend_result = private_evidence.get("frontend_result")
    smoke = private_evidence.get("frontend_smoke")
    if (not isinstance(frontend_result, dict) or
            frontend_result.get("actual_frontend") != "pass" or
            frontend_result.get("recognizable_title") != "unknown" or
            frontend_result.get("reported_status") != "pass" or
            not isinstance(smoke, dict) or
            smoke.get("frontend_exit_code") != 0 or
            smoke.get("frontend_log_status") != "pass"):
        return None

    capture_paths = smoke.get("capture_paths")
    capture_hashes = smoke.get("capture_sha256")
    capture_geometry = smoke.get("capture_geometry")
    identities = smoke.get("identity")
    if (not isinstance(capture_paths, list) or len(capture_paths) != 1 or
            not isinstance(capture_hashes, list) or len(capture_hashes) != 1 or
            not isinstance(capture_geometry, list) or len(capture_geometry) != 1 or
            capture_geometry[0] != [320, 224] or
            not isinstance(identities, dict)):
        return None
    capture = Path(capture_paths[0]) if isinstance(capture_paths[0], str) else None
    private_root = Path("local/qualification")
    if (capture is None or capture.is_symlink() or
            Path("local").is_symlink() or private_root.is_symlink() or
            capture.parent.is_symlink() or not capture.is_file() or
            capture.parent.parent.resolve() != private_root.resolve() or
            not ignored(capture)):
        return None
    try:
        current_capture_hash = _sha256_path(capture)
    except OSError:
        return None
    if (not isinstance(capture_hashes[0], str) or
            not re.fullmatch(r"[0-9a-f]{64}", capture_hashes[0]) or
            current_capture_hash != capture_hashes[0]):
        return None

    config_text = smoke.get("configuration_text")
    config_hash = smoke.get("configuration_sha256")
    selected_bundle_hash = smoke.get("selected_bundle_sha256")
    frontend_command = smoke.get("frontend_command")
    native_command = private_evidence.get("native_command")
    importer_command = private_evidence.get("importer_command")
    archive_before = private_evidence.get("input_archive_identities_before")
    archive_after_import = private_evidence.get("input_archive_identities_after_import")
    archive_after_frontend = private_evidence.get("input_archive_identities_after_frontend")
    archive_after = private_evidence.get("input_archive_identities_after_run")
    bundle_identity = private_evidence.get("normalized_bundle_identity")
    importer_identity = private_evidence.get("importer_identity")
    qualifier_identity = private_evidence.get("qualifier_identity")
    if (not isinstance(config_text, str) or not isinstance(config_hash, str) or
            hashlib.sha256(config_text.encode("utf-8")).hexdigest() != config_hash or
            "video_driver = \"gl\"" not in config_text or
            not isinstance(selected_bundle_hash, str) or
            not re.fullmatch(r"[0-9a-f]{64}", selected_bundle_hash) or
            not all(isinstance(command, list) and command and
                    all(isinstance(part, str) for part in command)
                    for command in (frontend_command, native_command, importer_command)) or
            not isinstance(archive_before, list) or
            archive_before != archive_after_import or
            archive_before != archive_after_frontend or
            archive_before != archive_after or
            not isinstance(bundle_identity, dict) or
            not isinstance(importer_identity, dict) or
            importer_identity.get("scope") != "production" or
            not isinstance(qualifier_identity, dict) or
            qualifier_identity.get("scope") != "production"):
        return None
    for key in ("core_sha256", "retroarch_executable_sha256"):
        if (not isinstance(identities.get(key), str) or
                not re.fullmatch(r"[0-9a-f]{64}", identities[key])):
            return None
    if (identities.get("retroarch_version") != "1.22.2" or
            identities.get("content_kind") != "selected-mvs"):
        return None

    def digest(value: object) -> str:
        return hashlib.sha256(json.dumps(
            value, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()

    return {
        "machine_acceptance": machine,
        "capture_sha256": current_capture_hash,
        "capture_geometry": capture_geometry[0],
        "selected_bundle_sha256": selected_bundle_hash,
        "configuration_sha256": config_hash,
        "frontend_identity": {
            key: identities[key] for key in (
                "content_kind", "core_sha256", "retroarch_executable_sha256",
                "retroarch_version",
            )
        },
        "frontend_command_sha256": digest(frontend_command),
        "native_command_sha256": digest(native_command),
        "importer_command_sha256": digest(importer_command),
        "archive_identities_sha256": digest(archive_before),
        "normalized_bundle_identity_sha256": digest(bundle_identity),
        "importer_identity_sha256": digest(importer_identity),
        "qualifier_identity_sha256": digest(qualifier_identity),
    }


def make_manual_visual_title_review(
        private_evidence: dict[str, object], *, outcome: str = "pass",
        user_live_corroboration: bool = False) -> dict[str, object] | None:
    """Create a finite manual title-review record after direct capture inspection."""
    if outcome not in {"pass", "fail"} or type(user_live_corroboration) is not bool:
        return None
    binding = _visual_review_binding(private_evidence)
    if binding is None:
        return None
    serialized = json.dumps(binding, sort_keys=True, separators=(",", ":"))
    return {
        "outcome": outcome,
        "method": "direct_visual_inspection",
        "source": "agent_visual_inspection",
        "user_live_corroboration": user_live_corroboration,
        "user_saw_exact_capture": False,
        "automated_title_ocr": "unknown",
        "binding": binding,
        "binding_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    }


def private_visual_review_path(private_evidence_path: Path) -> Path | None:
    """Return the ignored, non-overwriting sidecar path for one private run."""
    match = re.fullmatch(
        r"local/qualification/(phase05-[0-9a-f]{32})-private\.json",
        private_evidence_path.as_posix())
    if match is None:
        return None
    return private_evidence_path.with_name(match.group(1) + "-visual-review.json")


def record_manual_visual_title_review(
        private_evidence_path: Path, *, outcome: str = "pass",
        user_live_corroboration: bool = False) -> dict[str, object] | None:
    """Persist and resolve a direct visual review against one ignored run record."""
    review_path = private_visual_review_path(private_evidence_path)
    private_root = Path("local/qualification")
    if (review_path is None or Path("local").is_symlink() or
            private_root.is_symlink() or private_evidence_path.is_symlink() or
            not private_evidence_path.is_file() or
            private_evidence_path.parent.resolve() != private_root.resolve() or
            not ignored(private_evidence_path) or
            review_path.exists() or review_path.is_symlink() or not ignored(review_path)):
        return None
    try:
        payload = private_evidence_path.read_bytes()
        if len(payload) > QUALIFICATION_REPORT_MAX_BYTES:
            return None
        private = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    if not isinstance(private, dict):
        return None
    machine = safe_acceptance(private.get("acceptance_predicates"))
    review = make_manual_visual_title_review(
        private, outcome=outcome,
        user_live_corroboration=user_live_corroboration)
    if machine is None or review is None:
        return None
    resolved = resolve_manual_visual_title_review(machine, private, review)
    if resolved is None or not write_report(review_path, review):
        return None
    return {
        "machine_acceptance": machine,
        "reviewed_acceptance": resolved,
        "review_recorded": True,
    }


def resolve_manual_visual_title_review(
        machine_acceptance: object, private_evidence: dict[str, object],
        review: object) -> dict[str, str] | None:
    """Resolve only the current OCR-unknown title predicate; other failures stand."""
    machine = safe_acceptance(machine_acceptance)
    if (machine is None or machine != private_evidence.get("acceptance_predicates") or
            machine["recognizable_title"] != "unknown" or
            machine["overall"] != "unknown" or
            any(machine[key] != "pass" for key in ACCEPTANCE_PREDICATES
                if key != "recognizable_title") or
            not isinstance(review, dict) or set(review) != {
                "outcome", "method", "source", "user_live_corroboration",
                "user_saw_exact_capture", "automated_title_ocr", "binding",
                "binding_sha256",
            }):
        return None
    if (review.get("outcome") not in {"pass", "fail"} or
            review.get("method") != "direct_visual_inspection" or
            review.get("source") != "agent_visual_inspection" or
            type(review.get("user_live_corroboration")) is not bool or
            review.get("user_saw_exact_capture") is not False or
            review.get("automated_title_ocr") != "unknown"):
        return None
    binding = _visual_review_binding(private_evidence)
    if binding is None or review.get("binding") != binding:
        return None
    serialized = json.dumps(binding, sort_keys=True, separators=(",", ":"))
    if (review.get("binding_sha256") !=
            hashlib.sha256(serialized.encode("utf-8")).hexdigest()):
        return None
    states = {key: machine[key] for key in ACCEPTANCE_PREDICATES}
    states["recognizable_title"] = review["outcome"]
    return {**states, "overall": _acceptance_overall(states)}


def safe_result(report: dict[str, object], *,
                acceptance: dict[str, str] | None = None) -> dict[str, object]:
    """Filter native JSON; only a separately supplied wrapper map is trusted."""
    clean = _safe_native_result(report)
    if acceptance is None:
        return clean
    safe_outcomes = safe_acceptance(acceptance)
    if safe_outcomes is None:
        return {"status": "native_qualification_failed",
                "retroarch_observation": "manual-only-unknown",
                "private_identity_recorded": False}
    clean["acceptance"] = safe_outcomes
    return clean


def _strict_frame_indices(value: object, *, maximum_count: int,
                          horizon: int) -> list[int] | None:
    if not isinstance(value, list) or len(value) > maximum_count:
        return None
    frames: list[int] = []
    for frame in value:
        if (type(frame) is not int or frame < 0 or frame >= horizon or
                (frames and frame <= frames[-1])):
            return None
        frames.append(frame)
    return frames


def _safe_active_frame_fields(report: dict[str, object], status: str,
                              clean: dict[str, object]) -> bool:
    fields = {
        "active_frames_requested", "active_frames_completed",
        "capture_frames_requested", "capture_frames",
    }
    if not fields.intersection(report):
        return status not in {"active_frames_completed", "start_input_not_observed"}
    requested = report.get("active_frames_requested")
    completed = report.get("active_frames_completed")
    if (type(requested) is not int or not 1 <= requested <= MAX_ACTIVE_FRAMES or
            type(completed) is not int or not 0 <= completed <= requested):
        return False
    requested_captures = _strict_frame_indices(
        report.get("capture_frames_requested"),
        maximum_count=MAX_ACTIVE_CAPTURE_FRAMES, horizon=requested)
    completed_captures = _strict_frame_indices(
        report.get("capture_frames"),
        maximum_count=MAX_ACTIVE_CAPTURE_FRAMES, horizon=requested)
    if (requested_captures is None or completed_captures is None or
            completed_captures != requested_captures[:len(completed_captures)] or
            any(frame >= completed for frame in completed_captures)):
        return False
    if status == "active_frames_completed":
        if (report.get("guest_executed") is not True or
                report.get("start_observed") is not True or
                completed != requested or completed_captures != requested_captures):
            return False
    elif status == "start_input_not_observed":
        if (report.get("guest_executed") is not True or
                report.get("start_observed") is not False or completed != 0 or
                completed_captures):
            return False
    elif status == "guest_stopped":
        if (report.get("guest_executed") is not True or
                report.get("start_observed") is not True or completed >= requested):
            return False
    elif status in {"native_execution_error", "unsupported_guest_event"}:
        # A failure can precede the Start observation or the first active
        # frame. Retain its bounded progress without turning it into success.
        if (type(report.get("guest_executed")) is not bool or
                type(report.get("start_observed")) is not bool or
                completed >= requested or
                (report["start_observed"] is False and
                 (completed != 0 or completed_captures)) or
                (completed != 0 and report["guest_executed"] is not True)):
            return False
    else:
        return False
    sampled = report.get("sampled_inputs")
    if sampled is not None:
        if not isinstance(sampled, list) or len(sampled) > MAX_ACTIVE_INPUT_EVENTS:
            return False
        previous = -1
        for event in sampled:
            if (not isinstance(event, dict) or
                    set(event) != {"frame", "mask"} or
                    type(event.get("frame")) is not int or
                    type(event.get("mask")) is not int or
                    not previous < event["frame"] < requested or
                    event["mask"] < 0 or
                    event["mask"] & ~ACTIVE_INPUT_MASK):
                return False
            previous = event["frame"]
    clean["active_frames_requested"] = requested
    clean["active_frames_completed"] = completed
    clean["capture_frames_requested"] = requested_captures
    clean["capture_frames"] = completed_captures
    if isinstance(sampled, list):
        clean["sampled_input_count"] = len(sampled)
    return True


def _safe_native_result(report: dict[str, object]) -> dict[str, object]:
    if not isinstance(report, dict):
        return {"status": "native_qualification_failed",
                "retroarch_observation": "manual-only-unknown",
                "private_identity_recorded": False}
    status = report.get("status")
    if not isinstance(status, str) or status not in SAFE_RUNNER_STATUSES:
        return {"status": "native_qualification_failed",
                "retroarch_observation": "manual-only-unknown",
                "private_identity_recorded": False}
    if ("input_response" in report and
            (status != "attract_start" or
             report["input_response"] not in ("observed", "not_observed"))):
        return {"status": "native_qualification_failed",
                "retroarch_observation": "manual-only-unknown",
                "private_identity_recorded": False}
    legacy_advance = report.get("video_advance_frames")
    requested_advance = report.get("video_advance_requested")
    completed_advance = report.get("video_advance_completed")
    has_advance = any(key in report for key in (
        "video_advance_frames", "video_advance_requested",
        "video_advance_completed"))
    if has_advance:
        if status not in {"attract_start", "unsupported_guest_event", "guest_stopped"}:
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
        if ("video_advance_frames" in report and
                (type(legacy_advance) is not int or
                 not 1 <= legacy_advance <= MAX_VIDEO_ADVANCE_FRAMES)):
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
        if ("video_advance_requested" in report and
                (type(requested_advance) is not int or
                 not 1 <= requested_advance <= MAX_VIDEO_ADVANCE_FRAMES)):
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
        if ("video_advance_frames" in report and
                "video_advance_requested" in report and
                legacy_advance != requested_advance):
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
        requested = (requested_advance if "video_advance_requested" in report
                     else legacy_advance)
        if ("video_advance_requested" in report and
                "video_advance_completed" not in report):
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
        if ("video_advance_completed" in report and
                (requested is None or type(completed_advance) is not int or
                 not 0 <= completed_advance <= requested or
                 (status == "attract_start" and
                  completed_advance != requested) or
                 (status in {"unsupported_guest_event", "guest_stopped"} and
                  completed_advance >= requested))):
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
        if "video_advance_completed" in report and requested is None:
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
    if ("frame_output_written" in report and
            (type(report["frame_output_written"]) is not bool or
             report["frame_output_written"] is not True or
             status not in {"attract_start", "unsupported_guest_event",
                            "guest_stopped"})):
        return {"status": "native_qualification_failed",
                "retroarch_observation": "manual-only-unknown",
                "private_identity_recorded": False}
    clean: dict[str, object] = {
        "status": status,
        "retroarch_observation": "manual-only-unknown",
        "private_identity_recorded": False,
    }
    if not _safe_active_frame_fields(report, status, clean):
        return {"status": "native_qualification_failed",
                "retroarch_observation": "manual-only-unknown",
                "private_identity_recorded": False}
    if "frame_output_written" in report:
        clean["frame_output_written"] = True
    if "video_advance_frames" in report:
        clean["video_advance_frames"] = report["video_advance_frames"]
    if "video_advance_requested" in report:
        clean["video_advance_requested"] = report["video_advance_requested"]
    if "video_advance_completed" in report:
        clean["video_advance_completed"] = report["video_advance_completed"]
    if "native_failure" in report:
        native_failure = safe_native_failure(report["native_failure"])
        if (status not in {"native_execution_error", "unsupported_guest_event"} or
                native_failure is None or
                ("guest_executed" in report and
                 type(report["guest_executed"]) is bool and
                 report["guest_executed"] !=
                 (native_failure["completed_main_instructions"] != 0))):
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
        clean["native_failure"] = native_failure
    if "guest_executed" in report:
        if type(report["guest_executed"]) is not bool:
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
        clean["guest_executed"] = report["guest_executed"]
    if status == "missing_audio_region":
        if set(report) != {"status"}:
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
        return clean
    if status == "attract_start":
        # The positive result is accepted only in its exact documented shape:
        # guest_executed true and a checkpoint with exactly three keys. Anything
        # else (extra keys, wrong types, out-of-range chunk, an unknown request
        # name) is not a trustworthy attract/start claim.
        checkpoint = report.get("checkpoint")
        if (report.get("guest_executed") is not True or
                not isinstance(checkpoint, dict) or
                set(checkpoint) != {"user_request", "chunk", "user_mode_corroborated"} or
                checkpoint["user_request"] not in ("demo", "title") or
                type(checkpoint["chunk"]) is not int or
                not 1 <= checkpoint["chunk"] <= 256 or
                type(checkpoint["user_mode_corroborated"]) is not bool):
            return {"status": "native_qualification_failed",
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False}
        clean["guest_executed"] = True
        clean["checkpoint"] = {
            "user_request": checkpoint["user_request"],
            "chunk": checkpoint["chunk"],
            "user_mode_corroborated": checkpoint["user_mode_corroborated"],
        }
        if "input_response" in report:
            input_response = report["input_response"]
            clean["input_response"] = input_response
        return clean
    if report.get("guest_executed") is True:
        clean["guest_executed"] = True
    profile = report.get("profile")
    if isinstance(profile, dict):
        count_fields = ("chunks", "stable_chunks", "output_transition_chunks",
                        "video_transition_chunks", "bank_transition_chunks",
                        "watchdog_pet_count", "watchdog_reset_count")
        bounds = {key: 256 for key in count_fields[:5]}
        bounds.update({"watchdog_pet_count": 0xFFFFFFFF,
                       "watchdog_reset_count": 0xFFFFFFFF})
        if (all(isinstance(profile.get(key), int) and
                0 <= profile[key] <= bounds[key] for key in count_fields) and
                isinstance(profile.get("repeated_boundary_suffix"), bool)):
            clean["profile"] = {key: profile[key] for key in count_fields}
            clean["profile"]["repeated_boundary_suffix"] = profile[
                "repeated_boundary_suffix"]
    last_execution = report.get("last_execution")
    if isinstance(last_execution, dict):
        fields = ("pc", "opcode", "instructions", "elapsed_cycles",
                  "mame_watchdog_reset_count")
        if all(isinstance(last_execution.get(key), int) for key in fields):
            if 0 <= last_execution["pc"] <= 0xFFFFFF and 0 <= last_execution["opcode"] <= 0xFFFF:
                clean["last_execution"] = {key: last_execution[key] for key in fields}
    clean_diagnosis = safe_diagnosis(report.get("diagnosis"))
    if clean_diagnosis:
        clean["diagnosis"] = clean_diagnosis
    recent_fetches = report.get("recent_fetches")
    if isinstance(recent_fetches, list) and len(recent_fetches) <= 16:
        clean_fetches = []
        for event in recent_fetches:
            fields = ("pc", "word", "cursor", "run", "cycles")
            if (not isinstance(event, dict) or
                    not all(isinstance(event.get(key), int) for key in fields) or
                    not 0 <= event["pc"] <= 0xFFFFFF or
                    not 0 <= event["cursor"] <= 0xFFFFFFFF or
                    not 0 <= event["word"] <= 0xFFFF):
                clean_fetches = []
                break
            clean_fetches.append({key: event[key] for key in fields})
        clean["recent_fetches"] = clean_fetches
    event = report.get("first_unsupported_event")
    if isinstance(event, dict):
        pc, opcode = event.get("pc"), event.get("opcode")
        if isinstance(pc, int) and isinstance(opcode, int):
            clean["first_unsupported_event"] = {"pc": pc, "opcode": opcode}
            for key in ("mame_unmapped_write_count", "mame_watchdog_pet_count",
                        "mame_watchdog_reset_count"):
                if isinstance(event.get(key), int):
                    clean["first_unsupported_event"][key] = event[key]
        elif (event.get("kind") == "mvs_bus_access" and
              isinstance(event.get("address"), int) and
              event.get("operation") in ("read", "write") and
              event.get("width") in (1, 2) and
              isinstance(event.get("mame_unmapped_write_count"), int)):
            clean["first_unsupported_event"] = {
                "kind": "mvs_bus_access", "address": event["address"],
                "operation": event["operation"], "width": event["width"],
                "mame_unmapped_write_count": event["mame_unmapped_write_count"]}
    return clean


NEGATIVE_REPORT = Path("local/qualification/phase05-negative.json")


def invocation_report_path(report_path: Path) -> Path:
    """Give each invocation a private destination that cannot replace old evidence."""
    return report_path.with_name(
        f"{report_path.stem}-{uuid.uuid4().hex}{report_path.suffix}")


def private_frame_path(report_path: Path) -> Path:
    """Pair an ignored local report with a non-overwriting private pixel file."""
    return report_path.with_suffix(".ppm")


def private_frame_path_is_safe(path: Path) -> bool:
    frame_name = path.as_posix()
    return (re.fullmatch(r"local/qualification/phase05-[0-9a-f]{32}\.ppm",
                         frame_name) is not None and
            not Path("local").is_symlink() and
            not Path("local/qualification").is_symlink() and ignored(path))


def private_active_capture_directory_is_safe(path: Path, *,
                                             require_existing: bool = True) -> bool:
    if (re.fullmatch(
            r"local/qualification/phase0[67]/run-[0-9a-f]{32}",
            path.as_posix()) is None or
            any(parent.is_symlink() for parent in (
                Path("local"), Path("local/qualification"),
                Path("local/qualification/phase06"),
                Path("local/qualification/phase07"))) or
            path.is_symlink() or not ignored(path)):
        return False
    if require_existing:
        return path.is_dir()
    return not path.exists()


def private_active_capture_frame_path(directory: Path, frame: int) -> Path:
    return directory / f"frame-{frame:04d}.ppm"


def private_active_capture_frame_is_valid(path: Path) -> bool:
    if (re.fullmatch(
            r"local/qualification/phase0[67]/run-[0-9a-f]{32}/frame-[0-9]{4}\.ppm",
            path.as_posix()) is None or
            any(parent.is_symlink() for parent in (
                Path("local"), Path("local/qualification"),
                Path("local/qualification/phase06"),
                Path("local/qualification/phase07"), path.parent)) or
            path.is_symlink() or not ignored(path)):
        return False
    try:
        if path.stat().st_size != 15 + 320 * 224 * 3:
            return False
        with path.open("rb") as frame:
            return frame.read(15) == b"P6\n320 224\n255\n"
    except OSError:
        return False


def private_capture_directory(report_path: Path) -> Path:
    return report_path.with_name(report_path.stem + "-captures")


def private_capture_directory_is_safe(path: Path) -> bool:
    return (re.fullmatch(
        r"local/qualification/phase05-[0-9a-f]{32}-captures",
        path.as_posix()) is not None and
        not Path("local").is_symlink() and
        not Path("local/qualification").is_symlink() and
        not path.exists() and not path.is_symlink() and ignored(path))


def private_evidence_path(report_path: Path) -> Path:
    return report_path.with_name(report_path.stem + "-private.json")


def private_evidence_path_is_safe(path: Path) -> bool:
    return (re.fullmatch(
        r"local/qualification/phase05-[0-9a-f]{32}-private\.json",
        path.as_posix()) is not None and
        not Path("local").is_symlink() and
        not Path("local/qualification").is_symlink() and
        not path.exists() and not path.is_symlink() and ignored(path))


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_identity(path: Path) -> dict[str, object] | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        resolved = path.resolve(strict=True)
        return {"path": resolved.as_posix(), "size": resolved.stat().st_size,
                "sha256": _sha256_path(resolved)}
    except (OSError, RuntimeError):
        return None


def _absolute_identity_path(value: object) -> bool:
    """Accept canonical absolute identities from POSIX and Windows hosts."""
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return False
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return (
        posix.as_posix() == value and
        (posix.is_absolute() or windows.is_absolute()) and
        ".." not in posix.parts and ".." not in windows.parts
    )


def _media_identity_is_valid(value: object) -> bool:
    return (
        isinstance(value, list) and len(value) == 2 and
        all(isinstance(item, dict) and set(item) == {"path", "size", "sha256"} and
            _absolute_identity_path(item.get("path")) and
            type(item.get("size")) is int and item["size"] > 0 and
            isinstance(item.get("sha256"), str) and
            re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None
            for item in value) and
        sum(item["size"] for item in value) <= MAX_COMBINED_BYTES and
        all(item["size"] <= MAX_ARCHIVE_BYTES for item in value))


def _media_identity_content_matches(actual: object, expected: object) -> bool:
    return (
        _media_identity_is_valid(actual) and _media_identity_is_valid(expected) and
        all(actual_item["size"] == expected_item["size"] and
            actual_item["sha256"] == expected_item["sha256"]
            for actual_item, expected_item in zip(actual, expected)))


def _private_active_capture_directory_open_supported() -> bool:
    return (os.open in getattr(os, "supports_dir_fd", set()) and
            hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW"))


def _open_private_active_capture_directory(path: Path) -> int | None:
    if (path.is_absolute() or not path.parts or ".." in path.parts or
            not _private_active_capture_directory_open_supported()):
        return None
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_fd: int | None = None
    try:
        directory_fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
        for component in path.parts:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        return directory_fd
    except OSError:
        if directory_fd is not None:
            os.close(directory_fd)
        return None


def _copy_media_snapshot(source: Path, destination_name: str,
                         expected_size: int, directory_fd: int) -> bool:
    if type(expected_size) is not int or not 1 <= expected_size <= MAX_ARCHIVE_BYTES:
        return False
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    source_fd: int | None = None
    destination_fd: int | None = None
    try:
        source_fd = os.open(
            source, os.O_RDONLY | nofollow | getattr(os, "O_NONBLOCK", 0))
        if not stat.S_ISREG(os.fstat(source_fd).st_mode):
            return False
        destination_fd = os.open(
            destination_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o600,
            dir_fd=directory_fd)
        with os.fdopen(source_fd, "rb") as source_stream:
            source_fd = None
            with os.fdopen(destination_fd, "wb") as destination_stream:
                destination_fd = None
                copied = 0
                while copied <= expected_size:
                    remaining = expected_size - copied
                    block = source_stream.read(min(1024 * 1024, remaining + 1))
                    if not block:
                        break
                    if len(block) > remaining:
                        return False
                    destination_stream.write(block)
                    copied += len(block)
                return copied == expected_size
    except (OSError, ValueError):
        return False
    finally:
        if source_fd is not None:
            os.close(source_fd)
        if destination_fd is not None:
            os.close(destination_fd)


def _load_retroarch_smoke():
    module_path = PROJECT_ROOT / "tests" / "libretro" / "retroarch_smoke.py"
    spec = importlib.util.spec_from_file_location(
        "glueyneo_retroarch_smoke", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("frontend smoke module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_frontend_replay():
    spec = importlib.util.spec_from_file_location(
        "glueyneo_frontend_replay", PROJECT_ROOT / "tools/mvs/frontend_replay.py")
    if spec is None or spec.loader is None:
        raise ImportError("frontend replay module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _selected_v3_bundle_has_zoom_role(path: Path, smoke_module) -> bool:
    try:
        if path.stat().st_size > smoke_module.GNMV_MAX_BYTES:
            return False
        content = path.read_bytes()
    except OSError:
        return False
    if (not smoke_module.is_normalized_mvs_bundle(content) or len(content) < 16 or
            int.from_bytes(content[4:8], "big") != 3):
        return False
    count = int.from_bytes(content[12:16], "big")
    cursor = 16
    roles: set[int] = set()
    for _ in range(count):
        if len(content) - cursor < 12:
            return False
        role = int.from_bytes(content[cursor:cursor + 4], "big")
        size = int.from_bytes(content[cursor + 4:cursor + 12], "big")
        cursor += 12
        if size > len(content) - cursor:
            return False
        cursor += size
        roles.add(role)
    return cursor == len(content) and 8 in roles and count in (7, 8)


def _build_frontend_core(*, observations: bool = False) -> dict[str, object] | None:
    suffix = {"darwin": ".dylib", "win32": ".dll"}.get(
        sys.platform, ".so")
    build_directory = PROJECT_ROOT / "build" / (
        "local-frontend-observations" if observations else QUALIFIER_PRESET)
    core = build_directory / (
        "glueyneo_libretro" + suffix)
    command = (["cmake", "--build", str(build_directory), "--target", "glueyneo_libretro"]
               if observations else ["cmake", "--build", "--preset", QUALIFIER_PRESET,
                                     "--target", "glueyneo_libretro"])
    try:
        if observations:
            configured = subprocess.run(
                ["cmake", "--preset", QUALIFIER_PRESET, "-B", str(build_directory),
                 "-DGLUEYNEO_MVS_INPUT_OBSERVATIONS=ON"], cwd=PROJECT_ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                timeout=FRONTEND_CORE_BUILD_TIMEOUT_SECONDS)
            if configured.returncode != 0:
                return None
        result = subprocess.run(
            command, cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=False,
            timeout=FRONTEND_CORE_BUILD_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    identity = _file_identity(core)
    if result.returncode != 0 or identity is None:
        return None
    return {"command": command, **identity}


def _frontend_core_build_is_fresh(build_directory: Path) -> bool:
    """Check the configured frontend target's dependency graph without building it."""
    try:
        result = subprocess.run(
            ["ninja", "-C", str(build_directory), "-n", "glueyneo_libretro"],
            capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    lines = (getattr(result, "stdout", "") or "").splitlines()
    return (result.returncode == 0 and bool(lines) and
            lines[-1].strip() == NINJA_UP_TO_DATE)


def _current_frontend_core(*, observations: bool = False) -> dict[str, object] | None:
    """Read a fresh existing core identity without relinking calibrated evidence."""
    suffix = {"darwin": ".dylib", "win32": ".dll"}.get(sys.platform, ".so")
    build_directory = PROJECT_ROOT / "build" / (
        "local-frontend-observations" if observations else QUALIFIER_PRESET)
    core = build_directory / ("glueyneo_libretro" + suffix)
    if not _frontend_core_build_is_fresh(build_directory):
        return None
    identity = _file_identity(core)
    if (identity is None or not _frontend_core_build_is_fresh(build_directory) or
            _file_identity(core) != identity):
        return None
    return identity


def private_frame_is_valid(path: Path) -> bool:
    """Check only a local frame's fixed public geometry, never inspect/publish pixels."""
    header = b"P6\n320 224\n255\n"
    try:
        if path.stat().st_size != len(header) + 320 * 224 * 3:
            return False
        with path.open("rb") as frame:
            return frame.read(len(header)) == header
    except OSError:
        return False


def qualifier_dry_run_fresh(run=None) -> bool:
    """Return whether the selected qualifier targets have no pending Ninja work."""
    run = subprocess.run if run is None else run
    command = ["cmake", "--build", "--preset", QUALIFIER_PRESET,
               "--target", *QUALIFIER_TARGETS, "--", "-n"]
    try:
        result = run(command, capture_output=True, text=True, check=False,
                     timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return (result.returncode == 0 and
            NINJA_UP_TO_DATE in (getattr(result, "stdout", "") or ""))


def ensure_fresh_qualifier(run=None) -> QualifierFreshness:
    """Build selected targets incrementally and bind freshness to their bytes."""
    run = subprocess.run if run is None else run
    command = ["cmake", "--build", "--preset", QUALIFIER_PRESET,
               "--target", *QUALIFIER_TARGETS]
    try:
        result = run(command, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, check=False,
                     timeout=QUALIFIER_BUILD_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        return QualifierFreshness("build_failed")
    if result.returncode != 0:
        return QualifierFreshness("build_failed")
    identity = _production_importer_identity()
    qualifier_identity = _production_qualifier_identity()
    if identity is None or qualifier_identity is None:
        return QualifierFreshness("build_failed")
    if not qualifier_dry_run_fresh(run=run):
        return QualifierFreshness("stale")
    if not _importer_identity_matches(identity["path"], identity):
        return QualifierFreshness("unchecked")
    if checked_qualifier_command(identity=qualifier_identity) is None:
        return QualifierFreshness("stale")
    return QualifierFreshness("fresh", identity, qualifier_identity)


def _active_schedule_valid(active_frames: int | None,
                           frame_inputs: str | None,
                           capture_frames: list[int] | tuple[int, ...] | None,
                           capture_directory: Path | None,
                           sound_windows: str | None = None) -> bool:
    fields_present = any(value is not None for value in (
        active_frames, frame_inputs, capture_frames, capture_directory,
        sound_windows))
    if not fields_present:
        return True
    if (type(active_frames) is not int or
            not 1 <= active_frames <= MAX_ACTIVE_FRAMES):
        return False
    if frame_inputs is not None:
        try:
            if not frame_inputs or len(frame_inputs.encode("ascii")) > MAX_ACTIVE_SCHEDULE_BYTES:
                return False
        except UnicodeEncodeError:
            return False
        events = frame_inputs.split(",")
        if len(events) > MAX_ACTIVE_INPUT_EVENTS:
            return False
        previous = -1
        for event in events:
            match = re.fullmatch(r"([0-9]+):0x([0-9a-fA-F]+)", event)
            if match is None:
                return False
            frame = int(match.group(1), 10)
            mask = int(match.group(2), 16)
            if (not previous < frame < active_frames or mask > 0xFFFFFFFF or
                    mask & ~ACTIVE_INPUT_MASK):
                return False
            previous = frame
    if sound_windows is not None and _parse_sound_windows(
            sound_windows, active_frames) is None:
        return False
    if capture_frames is None:
        if sound_windows is None:
            return capture_directory is None
        return (capture_directory is not None and
                private_active_capture_directory_is_safe(capture_directory))
    if (not isinstance(capture_frames, (list, tuple)) or
            not 1 <= len(capture_frames) <= MAX_ACTIVE_CAPTURE_FRAMES or
            capture_directory is None):
        return False
    previous_capture = -1
    for frame in capture_frames:
        if (type(frame) is not int or
                not previous_capture < frame < active_frames):
            return False
        previous_capture = frame
    return private_active_capture_directory_is_safe(capture_directory)


def _parse_sound_windows(text: object, active_frames: int
                         ) -> list[dict[str, int | str]] | None:
    if (not isinstance(text, str) or not text or
            len(text.encode("ascii", errors="ignore")) > MAX_ACTIVE_SCHEDULE_BYTES):
        return None
    parsed: list[dict[str, int | str]] = []
    names: set[str] = set()
    for value in text.split(","):
        match = re.fullmatch(r"(music|fire|control|release):([0-9]+)-([0-9]+)", value)
        if match is None:
            return None
        name, first_text, last_text = match.groups()
        first, last = int(first_text, 10), int(last_text, 10)
        if (name in names or not 0 <= first <= last < active_frames or
                last - first >= SOUND_WINDOW_MAX_FRAMES):
            return None
        names.add(name)
        parsed.append({"name": name, "first_frame": first,
                       "last_frame": last})
    return parsed if 1 <= len(parsed) <= 4 else None


def _sound_pcm_features(pcm: bytes) -> dict[str, int] | None:
    if (not isinstance(pcm, bytes) or not pcm or len(pcm) % 4 != 0 or
            len(pcm) > SOUND_PCM_MAX_WINDOW_BYTES):
        return None
    sample_count = len(pcm) // 2
    peak = 0
    nonzero = 0
    squared = 0
    for (sample,) in struct.iter_unpack("<h", pcm):
        magnitude = abs(sample)
        peak = max(peak, magnitude)
        nonzero += sample != 0
        squared += sample * sample
    rms_milli = math.isqrt(squared * 1_000_000 // sample_count)
    return {"frames": len(pcm) // SOUND_PCM_BYTES_PER_FRAME,
            "samples": sample_count, "peak": peak,
            "nonzero_samples": nonzero, "rms_milli": rms_milli}


def _sound_chip_observation_is_valid(chip: object, frame_count: int) -> bool:
    counters = (
        "clocks", "register_writes", "ssg_register_writes",
        "ssg_volume_writes", "control_register_writes", "fm_register_writes",
        "fm_key_on_writes",
        "fm_key_off_writes", "fm_frequency_writes", "fm_level_writes",
        "fm_pan_writes", "adpcm_a_register_writes",
        "adpcm_a_control_writes", "adpcm_b_register_writes",
        "adpcm_b_control_writes", "adpcm_a_reads", "adpcm_b_reads",
        "timer_programs", "timer_expirations", "irq_assertions",
        "irq_deassertions", "native_frames", "native_nonzero_frames",
        "native_stereo_nonzero_frames", "native_ssg_nonzero_frames",
        "native_peak", "event_dropped",
    )
    if (not isinstance(chip, dict) or type(chip.get("version")) is not int or
            chip.get("version") != 1 or
            any(type(chip.get(name)) is not int or chip[name] < 0
                for name in counters) or
            chip["clocks"] > frame_count * 1_000_000 or
            chip["register_writes"] > chip["clocks"] + 64 or
            chip["timer_programs"] > chip["clocks"] + 64 or
            chip["timer_expirations"] > chip["timer_programs"] or
            chip["adpcm_a_reads"] > chip["clocks"] + 64 or
            chip["adpcm_b_reads"] > chip["clocks"] + 64 or
            chip["native_frames"] > frame_count * 100_000 or
            chip["native_nonzero_frames"] > chip["native_frames"] or
            chip["native_stereo_nonzero_frames"] > chip["native_nonzero_frames"] or
            chip["native_ssg_nonzero_frames"] > chip["native_nonzero_frames"] or
            chip["register_writes"] != sum(chip[name] for name in (
                "ssg_register_writes", "control_register_writes",
                "fm_register_writes",
                "adpcm_a_register_writes", "adpcm_b_register_writes"))):
        return False
    events = chip.get("register_events")
    if (not isinstance(events, list) or len(events) > 32 or
            chip["event_dropped"] != max(0, chip["register_writes"] - len(events))):
        return False
    for event in events:
        if (not isinstance(event, dict) or set(event) != {
                "clock", "port", "bank", "register", "value", "family"} or
                type(event.get("clock")) is not int or
                not 0 <= event["clock"] <= chip["clocks"] or
                type(event.get("port")) is not int or not 0 <= event["port"] <= 3 or
                type(event.get("bank")) is not int or
                event["bank"] != (1 if event["port"] >= 2 else 0) or
                type(event.get("register")) is not int or
                not 0 <= event["register"] <= 255 or
                type(event.get("value")) is not int or
                not 0 <= event["value"] <= 255 or
                type(event.get("family")) is not int):
            return False
        bank, register = event["bank"], event["register"]
        expected_family = (
            1 if bank == 0 and register <= 0x0d else
            4 if bank == 0 and 0x10 <= register <= 0x1b else
            3 if bank == 1 and register <= 0x2f else 2)
        if bank == 0 and (0x0e <= register <= 0x0f or
                          0x1c <= register <= 0x1f or
                          0x20 <= register <= 0x2f):
            expected_family = 5
        if event["family"] != expected_family:
            return False
    return True


def _sound_board_observations_are_valid(observations: object,
                                        first_frame: int,
                                        frame_count: int) -> bool:
    if not isinstance(observations, list) or len(observations) != frame_count:
        return False
    previous_cycles = -1
    for offset, observation in enumerate(observations):
        if (not isinstance(observation, dict) or set(observation) != {
                "frame", "sound_cpu_reset", "cart_selected", "command", "reply", "command_pending",
                "nmi_enabled", "ym_irq", "banks", "sound_cpu_pc",
                "sound_cpu_cycles"} or
                observation.get("frame") != first_frame + offset or
                type(observation.get("sound_cpu_reset")) is not bool or
                (offset == 0 and observation["sound_cpu_reset"]) or
                type(observation.get("sound_cpu_pc")) is not int or
                not 0 <= observation["sound_cpu_pc"] <= 0xffff or
                type(observation.get("sound_cpu_cycles")) is not int or
                observation["sound_cpu_cycles"] < 0 or
                (observation["sound_cpu_cycles"] < previous_cycles) !=
                    observation["sound_cpu_reset"] or
                any(type(observation.get(name)) is not int or
                    not 0 <= observation[name] <= 255
                    for name in ("cart_selected", "command", "reply",
                                 "command_pending", "nmi_enabled", "ym_irq")) or
                not isinstance(observation.get("banks"), list) or
                len(observation["banks"]) != 4 or
                any(type(bank) is not int or not 0 <= bank <= 255
                    for bank in observation["banks"])):
            return False
        previous_cycles = observation["sound_cpu_cycles"]
    return True


def _sound_window_observation_is_valid(
        observation: object, spec: dict[str, int | str], pcm: bytes,
        *, expected_masks: list[int] | None = None,
        require_nonsilent: bool = True,
        require_diagnostics: bool = False,
        ) -> tuple[bool, dict[str, int] | None]:
    features = _sound_pcm_features(pcm)
    if (not isinstance(observation, dict) or features is None or
            observation.get("name") != spec["name"] or
            observation.get("first_frame") != spec["first_frame"] or
            observation.get("last_frame") != spec["last_frame"]):
        return False, features
    frame_count = int(spec["last_frame"]) - int(spec["first_frame"]) + 1
    frames = observation.get("frame_observations")
    if (not isinstance(frames, list) or len(frames) != frame_count or
            observation.get("completed_frames") != frame_count):
        return False, features
    cycles = 0
    audio_frames = 0
    prior_input: int | None = None
    for offset, frame in enumerate(frames):
        if (not isinstance(frame, dict) or set(frame) != {
                "frame", "input_mask", "elapsed_cycles", "audio_frames"} or
                frame.get("frame") != int(spec["first_frame"]) + offset or
                type(frame.get("input_mask")) is not int or
                frame["input_mask"] & ~ACTIVE_INPUT_MASK or
                not _phase07_elapsed_frame_clocks_are_valid(
                    frame.get("elapsed_cycles")) or
                type(frame.get("audio_frames")) is not int or
                not 0 < frame["audio_frames"] <= 812):
            return False, features
        if (expected_masks is not None and
                (len(expected_masks) != frame_count or
                 frame["input_mask"] != expected_masks[offset])):
            return False, features
        prior_input = frame["input_mask"]
        cycles += frame["elapsed_cycles"]
        audio_frames += frame["audio_frames"]
    if (observation.get("actual_cycles") != cycles or
            observation.get("audio_frames_generated") != audio_frames or
            observation.get("audio_frames_delivered") != audio_frames or
            observation.get("audio_frames_discarded") != 0 or
            observation.get("pcm_bytes") != len(pcm) or
            features["frames"] != audio_frames or prior_input is None or
            (require_nonsilent and
             (features["peak"] == 0 or features["nonzero_samples"] == 0))):
        return False, features
    if (require_diagnostics and
            (not _sound_chip_observation_is_valid(
                observation.get("chip_observation"), frame_count) or
             not _sound_chip_frame_observations_are_valid(
                observation, int(spec["first_frame"]), frame_count) or
             not _sound_board_observations_are_valid(
                observation.get("board_observations"),
                int(spec["first_frame"]), frame_count))):
        return False, features
    return True, features


def _sound_chip_frame_observations_are_valid(
        observation: dict[str, object], first_frame: int,
        frame_count: int) -> bool:
    frames = observation.get("chip_frames")
    chip = observation.get("chip_observation")
    required_keys = {"frame", "chip_reset", *SOUND_CHIP_FRAME_COUNTERS}
    if (not isinstance(frames, list) or len(frames) != frame_count or
            not isinstance(chip, dict)):
        return False
    for output_key, source_key in SOUND_CHIP_FRAME_COUNTERS.items():
        value = chip.get(source_key)
        if type(value) is not int or value < 0:
            return False
    last_reset = 0
    for offset, frame in enumerate(frames):
        if (not isinstance(frame, dict) or set(frame) != required_keys or
                type(frame.get("frame")) is not int or
                frame["frame"] != first_frame + offset or
                type(frame.get("chip_reset")) is not bool):
            return False
        if frame["chip_reset"]:
            last_reset = offset
        for counter in SOUND_CHIP_FRAME_COUNTERS:
            value = frame.get(counter)
            if type(value) is not int or value < 0:
                return False
    epoch_totals = {key: 0 for key in SOUND_CHIP_FRAME_COUNTERS}
    for frame in frames[last_reset:]:
        for counter in SOUND_CHIP_FRAME_COUNTERS:
            epoch_totals[counter] += frame[counter]
    return all(epoch_totals[key] == chip[source_key]
               for key, source_key in SOUND_CHIP_FRAME_COUNTERS.items())


def _sound_expected_masks(frame_inputs: str | None, first: int,
                          last: int) -> list[int] | None:
    events: list[tuple[int, int]] = []
    if frame_inputs is not None:
        try:
            events = [(int(frame_text, 10), int(mask_text, 16))
                      for frame_text, mask_text in
                      (event.split(":0x", 1) for event in frame_inputs.split(","))]
        except (ValueError, TypeError):
            return None
    masks: list[int] = []
    held = 0
    next_event = 0
    for frame in range(first, last + 1):
        while next_event < len(events) and events[next_event][0] <= frame:
            held = events[next_event][1]
            next_event += 1
        masks.append(held)
    return masks


def _native_sound_windows_are_valid(
        report: object, sound_windows: str, frame_inputs: str | None,
        capture_directory: Path, active_frames: int
        ) -> tuple[bool, dict[str, dict[str, int]]]:
    specs = _parse_sound_windows(sound_windows, active_frames)
    observations = report.get("sound_windows") if isinstance(report, dict) else None
    if (specs is None or not isinstance(observations, list) or
            len(observations) != len(specs) or
            not private_active_capture_directory_is_safe(capture_directory)):
        return False, {}
    feature_reports: dict[str, dict[str, int]] = {}
    for spec, observation in zip(specs, observations):
        name = str(spec["name"])
        path = capture_directory / f"sound-{name}.s16le"
        if not private_active_sound_path_is_valid(path):
            return False, feature_reports
        try:
            size = path.stat().st_size
            if not 0 < size <= SOUND_PCM_MAX_WINDOW_BYTES:
                return False, feature_reports
            pcm = path.read_bytes()
        except OSError:
            return False, feature_reports
        masks = _sound_expected_masks(frame_inputs,
                                      int(spec["first_frame"]),
                                      int(spec["last_frame"]))
        valid, features = _sound_window_observation_is_valid(
            observation, spec, pcm, expected_masks=masks,
            require_nonsilent=False, require_diagnostics=True)
        if not valid or features is None:
            return False, feature_reports
        feature_reports[name] = features
    return True, feature_reports


def run_selected_qualification(input_root: Path,
                               importer: str | Path | list[str] | None = None,
                               freshness=ensure_fresh_qualifier,
                               execute=subprocess.run,
                               synthetic_identity: dict[str, object] | None = None,
                               scripted_start: bool = False,
                               frame_output_path: Path | None = None,
                               video_advance_frames: int = 0,
                               video_state_diagnostic: bool = False,
                               active_frames: int | None = None,
                               frame_inputs: str | None = None,
                               capture_frames: list[int] | tuple[int, ...] | None = None,
                               capture_directory: Path | None = None,
                               sound_windows: str | None = None,
                               expected_media_identity: list[dict[str, object]] | None = None,
                               preserve_native_report: bool = False,
                               import_callback=None,
                               frontend_callback=None) -> dict[str, object]:
    """Run local selected-media qualification only after freshness is proven."""
    if (isinstance(video_advance_frames, bool) or
            not isinstance(video_advance_frames, int) or
            not 0 <= video_advance_frames <= MAX_VIDEO_ADVANCE_FRAMES or
            (scripted_start and video_advance_frames != 0) or
            not _active_schedule_valid(active_frames, frame_inputs,
                                       capture_frames, capture_directory,
                                       sound_windows) or
            (active_frames is not None and
             (not scripted_start or frame_output_path is not None or
              video_advance_frames != 0 or video_state_diagnostic)) or
            type(video_state_diagnostic) is not bool or
            type(preserve_native_report) is not bool or
            (video_state_diagnostic and frame_output_path is None)):
        return {"qualifier_build": "not_started",
                "retroarch_observation": "manual-only-unknown",
                "private_identity_recorded": False,
                "qualification_invocation_state": "not_started",
                "status": "video_advance_out_of_bounds"}
    build = freshness()
    build_status = str(build)
    base: dict[str, object] = {
        "qualifier_build": build_status,
        "retroarch_observation": "manual-only-unknown",
        "private_identity_recorded": False,
        "qualification_invocation_state": "not_started",
    }
    if build_status != "fresh":
        if build_status == "unchecked":
            base["qualifier_build"] = "unchecked"
            base["status"] = "importer_identity_rejected"
        else:
            base["status"] = ("qualifier_build_failed" if build_status == "build_failed"
                              else "qualifier_stale")
        return base

    if frame_output_path is not None:
        if (not private_frame_path_is_safe(frame_output_path) or
                frame_output_path.exists() or
                frame_output_path.is_symlink()):
            return {**base, "status": "native_qualification_failed"}

    production_identity = getattr(build, "importer_identity", None)
    synthetic_scope = synthetic_identity is not None
    importer_command = (checked_synthetic_importer_command(importer, synthetic_identity)
                        if synthetic_scope else
                        checked_importer_command(importer, identity=production_identity))
    if importer_command is None:
        return {**base, "qualifier_build": "unchecked",
                "status": "importer_identity_rejected"}
    qualifier_identity = getattr(build, "qualifier_identity", None)
    qualifier_command = (None if synthetic_scope else
                         checked_qualifier_command(identity=qualifier_identity))
    if not synthetic_scope and qualifier_command is None:
        return {**base, "qualifier_build": "stale", "status": "qualifier_stale"}
    if synthetic_scope:
        base["qualifier_build"] = "unchecked"
    if not input_root.is_dir():
        return {**base, "status": "private_media_unavailable"}

    pairs = find_pairs(input_root)
    if not pairs:
        return {**base, "status": "no_supported_role_bundle_archive",
                "first_blocking_checkpoint": "archive_to_region_mapping",
                "next_technical_dependency": "select and map the supported game and BIOS archives"}
    if len(pairs) > 1:
        return {**base, "status": "ambiguous_private_media_inputs"}
    if expected_media_identity is not None:
        selected_media_identity = [_file_identity(path) for path in pairs[0]]
        if (not _media_identity_is_valid(expected_media_identity) or
                selected_media_identity != expected_media_identity):
            return {**base, "status": "media_identity_rejected"}

    try:
        with tempfile.TemporaryDirectory(prefix="glueyneo-mvs-") as temporary:
            temporary_root = Path(temporary)
            normalized = temporary_root / "normalized.gnmv"
            import_paths = pairs[0]
            media_snapshots: tuple[Path, Path] | None = None
            if expected_media_identity is not None:
                if (capture_directory is None or
                        not private_active_capture_directory_is_safe(capture_directory)):
                    return {**base, "status": "media_identity_rejected"}
                snapshots = (capture_directory / "media-game.zip",
                             capture_directory / "media-bios.zip")
                directory_fd = _open_private_active_capture_directory(
                    capture_directory)
                if directory_fd is None:
                    return {**base, "status": "media_identity_rejected"}
                try:
                    if any(path.exists() or path.is_symlink() for path in snapshots):
                        return {**base, "status": "media_identity_rejected"}
                    for index, (source, snapshot) in enumerate(
                            zip(pairs[0], snapshots)):
                        if not _copy_media_snapshot(
                                source, snapshot.name,
                                expected_media_identity[index]["size"], directory_fd):
                            return {**base, "status": "media_identity_rejected"}
                except OSError:
                    return {**base, "status": "media_identity_rejected"}
                finally:
                    os.close(directory_fd)
                snapshot_identity = [_file_identity(path) for path in snapshots]
                if (not _media_identity_content_matches(
                        snapshot_identity, expected_media_identity) or
                        [_file_identity(path) for path in pairs[0]] !=
                        expected_media_identity):
                    return {**base, "status": "media_identity_rejected"}
                import_paths = snapshots
                media_snapshots = snapshots
            command_is_current = (
                checked_synthetic_importer_command(importer, synthetic_identity)
                if synthetic_scope else
                checked_importer_command(importer, identity=production_identity))
            if command_is_current != importer_command:
                return {**base, "qualifier_build": "unchecked",
                        "status": "importer_identity_rejected"}
            if (not synthetic_scope and
                    checked_qualifier_command(identity=qualifier_identity) != qualifier_command):
                return {**base, "qualifier_build": "stale", "status": "qualifier_stale"}
            try:
                imported_result = execute(
                    [importer_command, "--selected", str(import_paths[0]),
                     str(import_paths[1]), str(normalized)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False, timeout=IMPORT_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return {**base, "status": "selected_media_import_timeout"}
            except KeyboardInterrupt:
                return {**base, "status": "selected_media_import_interrupted"}
            except OSError:
                return {**base, "status": "selected_media_import_failed"}
            if imported_result.returncode != 0:
                return {**base, "status": "selected_media_import_failed",
                        "import_error_class": import_error_class(imported_result.returncode)}
            if expected_media_identity is not None:
                snapshot_identity = ([_file_identity(path) for path in media_snapshots]
                                     if media_snapshots is not None else None)
                if ([_file_identity(path) for path in pairs[0]] !=
                        expected_media_identity or
                        not _media_identity_content_matches(
                            snapshot_identity, expected_media_identity)):
                    return {**base, "status": "media_identity_rejected"}
            if synthetic_scope:
                return {**base, "qualifier_build": "unchecked",
                        "status": "synthetic_importer_identity_verified",
                        "importer_identity_scope": "synthetic"}
            if checked_importer_command(importer, identity=production_identity) != importer_command:
                return {**base, "qualifier_build": "unchecked",
                        "status": "importer_identity_rejected"}
            if checked_qualifier_command(identity=qualifier_identity) != qualifier_command:
                return {**base, "qualifier_build": "stale", "status": "qualifier_stale"}
            if import_callback is not None:
                import_callback(normalized, pairs[0], importer_command,
                                production_identity, qualifier_identity)
            base["qualification_invocation_state"] = "attempted"
            try:
                native_command = [qualifier_command, str(normalized)]
                if scripted_start:
                    native_command.extend(("--input-script", SCRIPTED_START_INPUT_SCRIPT))
                if active_frames is not None:
                    native_command.extend(("--active-frames", str(active_frames)))
                    if frame_inputs is not None:
                        native_command.extend(("--frame-inputs", frame_inputs))
                    if capture_frames is not None and capture_directory is not None:
                        native_command.extend((
                            "--capture-frames",
                            ",".join(str(frame) for frame in capture_frames),
                            "--capture-directory", capture_directory.as_posix()))
                    elif sound_windows is not None and capture_directory is not None:
                        native_command.extend(("--capture-directory",
                                               capture_directory.as_posix()))
                    if sound_windows is not None:
                        native_command.extend(("--sound-windows", sound_windows))
                if frame_output_path is not None:
                    native_command.extend(("--frame-output",
                                           frame_output_path.as_posix()))
                if video_advance_frames != 0:
                    native_command.extend(("--video-advance-frames",
                                           str(video_advance_frames)))
                if video_state_diagnostic:
                    native_command.append("--video-state-diagnostic")
                execution = execute(
                    native_command, capture_output=True, text=True, check=False,
                    timeout=NATIVE_QUALIFICATION_TIMEOUT_SECONDS,
                )
                if expected_media_identity is not None:
                    snapshot_identity = ([_file_identity(path)
                                          for path in media_snapshots]
                                         if media_snapshots is not None else None)
                    if ([_file_identity(path) for path in pairs[0]] !=
                            expected_media_identity or
                            not _media_identity_content_matches(
                                snapshot_identity, expected_media_identity)):
                        failure = {**base, "status": "media_identity_rejected"}
                        if preserve_native_report:
                            failure["native_stderr_local"] = getattr(
                                execution, "stderr", "")
                            failure["native_stdout_local"] = getattr(
                                execution, "stdout", "")
                        return failure
            except KeyboardInterrupt:
                base["qualification_invocation_state"] = "uncertain"
                return {**base, "status": "native_qualification_interrupted"}
            except (OSError, subprocess.TimeoutExpired, UnicodeError):
                base["qualification_invocation_state"] = "uncertain"
                failure = {**base, "status": "native_qualification_failed"}
                if active_frames is not None:
                    failure["active_frames_requested"] = active_frames
                    failure["active_frames_completed"] = None
                return failure
            try:
                output = execution.stdout
                stderr_output = getattr(execution, "stderr", "")
                if (not isinstance(output, str) or not isinstance(stderr_output, str) or
                        len(output.encode("utf-8")) +
                        len(stderr_output.encode("utf-8")) >
                        QUALIFICATION_REPORT_MAX_BYTES):
                    return {**base, "status": "native_qualification_output_limit"}
                decoded = json.loads(output)
                # A positive checkpoint is trustworthy only when the producer
                # itself exited successfully. Exit 1 is reserved for the
                # bounded native failure paths: execution diagnostics and
                # captured main-CPU bus faults classified as guest events.
                if execution.returncode != 0 and not (
                        execution.returncode == 1 and
                        isinstance(decoded, dict) and
                        (decoded.get("status") == "native_execution_error" or
                         (decoded.get("status") == "unsupported_guest_event" and
                          isinstance(decoded.get("native_failure"), dict)))):
                    failure = {**base, "status": "native_qualification_failed"}
                    if preserve_native_report:
                        failure["native_report_local"] = decoded
                        failure["native_stderr_local"] = stderr_output
                    return failure
                private_sound_features: dict[str, dict[str, int]] | None = None
                private_sound_valid = True
                if sound_windows is not None:
                    sound_valid, private_sound_features = (
                        _native_sound_windows_are_valid(
                            decoded, sound_windows, frame_inputs,
                            capture_directory, active_frames))
                    if not sound_valid:
                        private_sound_valid = False
                safe = safe_result(decoded)
                if active_frames is not None:
                    if (safe.get("active_frames_requested") != active_frames or
                            safe.get("capture_frames_requested") !=
                            list(capture_frames or ())):
                        failure = {**base, "status": "native_qualification_failed"}
                        if preserve_native_report:
                            failure["native_report_local"] = decoded
                            failure["native_stderr_local"] = stderr_output
                        return failure
                    reported_captures = safe.get("capture_frames")
                    if not isinstance(reported_captures, list):
                        failure = {**base, "status": "native_qualification_failed"}
                        if preserve_native_report:
                            failure["native_report_local"] = decoded
                            failure["native_stderr_local"] = stderr_output
                        return failure
                    if (capture_directory is not None and
                            any(not private_active_capture_frame_is_valid(
                                private_active_capture_frame_path(capture_directory, frame))
                                for frame in reported_captures)):
                        failure = {**base, "status": "native_qualification_failed"}
                        if preserve_native_report:
                            failure["native_report_local"] = decoded
                            failure["native_stderr_local"] = stderr_output
                        return failure
                private_activity = None
                if video_state_diagnostic:
                    private_activity = _private_video_activity(stderr_output)
                    if private_activity is None:
                        return {**base, "status": "native_qualification_failed"}
                frame_reported = safe.get("frame_output_written") is True
                if frame_output_path is None:
                    if frame_reported:
                        return {**base, "status": "native_qualification_failed"}
                elif not frame_reported or not private_frame_is_valid(frame_output_path):
                    return {**base, "status": "native_qualification_failed"}
                result = {**safe, **base}
                if not private_sound_valid:
                    result["status"] = "native_sound_capture_invalid"
                if preserve_native_report:
                    result["native_report_local"] = decoded
                    result["native_stderr_local"] = stderr_output
                if private_sound_features is not None:
                    result["sound_features_local"] = private_sound_features
                if private_activity is not None:
                    result["private_video_activity"] = private_activity
                if frontend_callback is not None:
                    return frontend_callback(
                        result, normalized, pairs[0], importer_command,
                        native_command, production_identity, qualifier_identity)
                return result
            except UnicodeError:
                base["qualification_invocation_state"] = "uncertain"
                return {**base, "status": "native_qualification_failed"}
            except (json.JSONDecodeError, TypeError):
                failure = {**base, "status": "native_qualification_failed"}
                if preserve_native_report:
                    failure["native_stdout_local"] = output
                    failure["native_stderr_local"] = stderr_output
                return failure
    except OSError:
        return {**base, "status": "native_qualification_failed"}


PHASE06_CONTRACT_PATH = Path("local/qualification/phase06-contract.json")
PHASE06_RUN_ROOT = Path("local/qualification/phase06")
PHASE07_SOUND_CONTRACT_PATH = Path("local/qualification/phase07-sound-contract.json")
PHASE07_RUN_ROOT = Path("local/qualification/phase07")
PHASE06_CALIBRATION_FRAMES = (2523, 2550, 2560, 2580, 2620, 2700)
# The existing frame API repays the previous frame's instruction excess. A
# logical frame is202,752 clocks. Current owned DIVS.W immediate can take160
# clocks (156 register clocks plus4 EA), so atomic excess is at most159.
# See experiments/owned_cpu/SUBSET.md and the worst-case DIVS regression.
# Earlier131-clock/RESET-only derivations predate the admitted divide forms.
PHASE07_FRAME_CYCLE_BUDGET = 202752
PHASE07_MAX_EVENT_EXCESS_CYCLES = 159
SOUND_WINDOW_NAMES = frozenset(("music", "fire", "control", "release"))
SOUND_WINDOW_MAX_FRAMES = 120
SOUND_PCM_BYTES_PER_FRAME = 4
SOUND_PCM_MAX_WINDOW_BYTES = (SOUND_WINDOW_MAX_FRAMES *
                              812 * SOUND_PCM_BYTES_PER_FRAME)
SOUND_CHIP_FRAME_COUNTERS = {
    "chip_clocks": "clocks",
    "fm_key_on_writes": "fm_key_on_writes",
    "fm_key_off_writes": "fm_key_off_writes",
    "fm_register_writes": "fm_register_writes",
    "ssg_register_writes": "ssg_register_writes",
    "ssg_volume_writes": "ssg_volume_writes",
    "adpcm_a_register_writes": "adpcm_a_register_writes",
    "adpcm_a_control_writes": "adpcm_a_control_writes",
    "adpcm_a_reads": "adpcm_a_reads",
    "adpcm_b_register_writes": "adpcm_b_register_writes",
    "adpcm_b_control_writes": "adpcm_b_control_writes",
    "adpcm_b_reads": "adpcm_b_reads",
    "native_nonzero_frames": "native_nonzero_frames",
}
PHASE07_SOUND_THRESHOLDS = {
    "schema_version": 1,
    "alignment": "same_guest_frame_and_audio_frame_count",
    "music": {
        "minimum_nonzero_int16_samples": 16,
        "require_exact_common_history": True,
        "require_same_frame_family_output": True,
    },
    "fire": {
        "input_mask": 0x40,
        "minimum_changed_int16_samples_in_one_frame": 8,
        "require_same_frame_family_output": True,
    },
    "release": {
        "input_mask": 0,
        "trailing_equal_pcm_frames": 3,
        "accept_same_window_chip_stop_event": True,
    },
}


def _phase07_elapsed_frame_clocks_are_valid(value: object) -> bool:
    return (type(value) is int and
            abs(value - PHASE07_FRAME_CYCLE_BUDGET) <=
            PHASE07_MAX_EVENT_EXCESS_CYCLES)


def _phase07_criteria_identity(thresholds: object) -> str | None:
    if not isinstance(thresholds, dict):
        return None
    try:
        encoded = json.dumps(thresholds, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _phase07_schedule_identity(phase06_identity: object,
                              schedule: object) -> str | None:
    try:
        encoded = json.dumps(
            {"phase06_contract_identity": phase06_identity,
             "schedule": schedule}, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _phase07_sound_contract_matches_current(
        sound_contract: object, *, phase06_identity: object,
        phase06_digest: object, schedule: object, code_identity: object,
        evaluator_identity: object, media_identity: object) -> bool:
    if (not phase07_sound_contract_is_valid(sound_contract, require_frozen=True) or
            not isinstance(sound_contract, dict)):
        return False
    return (
        sound_contract.get("phase06_contract_identity") == phase06_identity and
        sound_contract.get("phase06_contract_sha256") == phase06_digest and
        sound_contract.get("schedule") == schedule and
        sound_contract.get("schedule_identity") ==
            _phase07_schedule_identity(phase06_identity, schedule) and
        sound_contract.get("code_identity") == code_identity and
        sound_contract.get("evaluator_identity") == evaluator_identity and
        sound_contract.get("media_identity") == media_identity)


def _phase07_sound_contract_scene_binding_valid(
        sound_contract: object, scene_contract: object, scene_path: Path,
        *, scene_digest: str | None = None) -> bool:
    """Bind frozen native sound evidence to this unchanged Phase06 scene."""
    if (not isinstance(scene_contract, dict) or
            not phase07_sound_contract_is_valid(sound_contract, require_frozen=True) or
            not isinstance(sound_contract, dict)):
        return False
    digest = scene_digest
    if digest is None:
        try:
            digest = _sha256_path(scene_path)
        except OSError:
            return False
    outcomes = sound_contract.get("outcomes")
    visual = outcomes.get("visual_predicates") if isinstance(outcomes, dict) else None
    identity = scene_contract.get("contract_identity")
    schedule = scene_contract.get("schedule")
    if not isinstance(schedule, dict):
        return False
    return (
        sound_contract.get("phase06_contract_identity") == identity and
        sound_contract.get("phase06_contract_sha256") == digest and
        sound_contract.get("schedule") == schedule and
        sound_contract.get("schedule_identity") ==
            _phase07_schedule_identity(identity, schedule) and
        sound_contract.get("media_identity") == scene_contract.get("media_identity") and
        isinstance(outcomes, dict) and outcomes.get("calibration") == "windows_ready" and
        isinstance(visual, dict) and visual.get("overall") == "pass" and
        all(outcomes.get(name) == "pass" for name in ("music", "fire", "release", "overall")))


def _phase07_contract_files_unchanged(
        scene_path: Path, scene_digest: str | None,
        sound_path: Path, sound_digest: str | None) -> bool:
    if (not isinstance(scene_digest, str) or
            re.fullmatch(r"[0-9a-f]{64}", scene_digest) is None or
            not isinstance(sound_digest, str) or
            re.fullmatch(r"[0-9a-f]{64}", sound_digest) is None):
        return False
    try:
        return (_sha256_path(scene_path) == scene_digest and
                _sha256_path(sound_path) == sound_digest)
    except OSError:
        return False


def _calibration_capture_frames_valid(frames: object) -> bool:
    return (isinstance(frames, (list, tuple)) and
            len(frames) == MAX_ACTIVE_CAPTURE_FRAMES and
            all(type(frame) is int and 0 <= frame < MAX_ACTIVE_FRAMES
                for frame in frames) and list(frames) == sorted(set(frames)))


def _parse_calibration_capture_frames(text: str) -> list[int]:
    if (len(text) > MAX_ACTIVE_SCHEDULE_BYTES or
            re.fullmatch(r"[0-9]+(?:,[0-9]+){5}", text) is None):
        raise argparse.ArgumentTypeError("capture window requires six ascending frame indices")
    # Bound each decimal token before conversion, including hostile huge integers.
    tokens = text.split(",")
    if any(len(token) > 10 for token in tokens):
        raise argparse.ArgumentTypeError("capture frame exceeds the active horizon")
    frames = [int(token, 10) for token in tokens]
    if not _calibration_capture_frames_valid(frames):
        raise argparse.ArgumentTypeError("capture window must be ordered within the active horizon")
    return frames


def phase07_sound_contract_is_valid(contract: object, *,
                                    require_frozen: bool | None = None) -> bool:
    if not isinstance(contract, dict):
        return False
    required = {
        "schema_version", "mode", "phase06_contract_sha256",
        "phase06_contract_identity", "code_identity", "evaluator_identity",
        "media_identity", "schedule_identity", "recordings", "families",
        "schedule", "thresholds", "criteria_identity", "calibration_identity",
        "outcomes", "frozen", "contract_identity",
    }
    if (not required.issubset(contract) or contract.get("schema_version") != 1 or
            type(contract.get("frozen")) is not bool or
            contract.get("mode") not in ("calibrate", "frozen") or
            not isinstance(contract.get("phase06_contract_sha256"), str) or
            re.fullmatch(r"[0-9a-f]{64}",
                         contract["phase06_contract_sha256"]) is None or
            not isinstance(contract.get("phase06_contract_identity"), str) or
            re.fullmatch(r"[0-9a-f]{64}",
                         contract["phase06_contract_identity"]) is None or
            not isinstance(contract.get("schedule_identity"), str) or
            re.fullmatch(r"[0-9a-f]{64}", contract["schedule_identity"]) is None or
            not isinstance(contract.get("contract_identity"), str) or
            re.fullmatch(r"[0-9a-f]{64}", contract["contract_identity"]) is None or
            not isinstance(contract.get("code_identity"), dict) or
            set(contract["code_identity"]) != {"importer", "qualifier"} or
            not isinstance(contract.get("evaluator_identity"), dict) or
            not _media_identity_is_valid(contract.get("media_identity")) or
            not isinstance(contract.get("recordings"), dict) or
            not isinstance(contract.get("families"), dict) or
            not isinstance(contract.get("thresholds"), dict) or
            not isinstance(contract.get("schedule"), dict) or
            not isinstance(contract.get("outcomes"), dict)):
        return False
    outcome_states = {"pass", "fail", "unknown"}
    outcomes = contract["outcomes"]
    if (any(key in outcomes and
            (not isinstance(outcomes[key], str) or
             outcomes[key] not in outcome_states)
            for key in ("music", "fire", "release", "overall")) or
            ("visual_predicates" in outcomes and
             (not isinstance(outcomes["visual_predicates"], dict) or
              any(not isinstance(value, str) or value not in outcome_states
                  for value in outcomes["visual_predicates"].values()))) or
            ("calibration" in outcomes and
             (not isinstance(outcomes["calibration"], str) or
              outcomes["calibration"] not in {"windows_ready", "incomplete"}))):
        return False
    if require_frozen is not None and contract["frozen"] is not require_frozen:
        return False
    if contract["mode"] == "calibrate":
        if (contract["frozen"] is not False or contract["thresholds"] != {} or
                contract["criteria_identity"] is not None or
                contract["calibration_identity"] is not None):
            return False
    else:
        if (contract["frozen"] is not True or
                contract["thresholds"] != PHASE07_SOUND_THRESHOLDS or
                contract["criteria_identity"] !=
                _phase07_criteria_identity(PHASE07_SOUND_THRESHOLDS) or
                not isinstance(contract["calibration_identity"], str) or
                re.fullmatch(r"[0-9a-f]{64}",
                             contract["calibration_identity"]) is None):
            return False
    payload = {key: value for key, value in contract.items()
               if key != "contract_identity"}
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True).encode("utf-8")
    except (TypeError, ValueError):
        return False
    return hashlib.sha256(encoded).hexdigest() == contract["contract_identity"]


def _seal_phase07_sound_contract(contract: dict[str, object]) -> None:
    contract.pop("contract_identity", None)
    contract["contract_identity"] = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True).encode("utf-8")).hexdigest()


def _write_phase07_sound_contract(path: Path, contract: dict[str, object],
                                  run_directory: Path) -> bool:
    if (path != PHASE07_SOUND_CONTRACT_PATH or path.is_symlink() or
            not ignored(path) or
            any(parent.is_symlink() for parent in (
                Path("local"), Path("local/qualification"))) or
            not private_active_capture_directory_is_safe(run_directory)):
        return False
    _seal_phase07_sound_contract(contract)
    if not phase07_sound_contract_is_valid(contract):
        return False
    payload = (json.dumps(contract, sort_keys=True, separators=(",", ":")) +
               "\n").encode("utf-8")
    if len(payload) > QUALIFICATION_REPORT_MAX_BYTES:
        return False
    if path.exists():
        previous = run_directory / "previous-sound-contract.json"
        try:
            with previous.open("xb") as handle:
                handle.write(path.read_bytes())
        except OSError:
            return False
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=".phase07-sound-",
                suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        return True
    except OSError:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        return False


def _read_phase07_sound_contract(path: Path, *, require_frozen: bool | None = None
                                 ) -> dict[str, object] | None:
    if (path != PHASE07_SOUND_CONTRACT_PATH or path.is_symlink() or
            not path.is_file() or not ignored(path) or
            any(parent.is_symlink() for parent in (
                Path("local"), Path("local/qualification")) )):
        return None
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return contract if phase07_sound_contract_is_valid(
        contract, require_frozen=require_frozen) else None


def freeze_phase07_sound_contract(
        input_root: Path, scene_contract_path: Path,
        sound_contract_path: Path) -> dict[str, object]:
    """Freeze the current private schedule and fixed causal rules for a fresh run."""
    unknown = {"music": "unknown", "fire": "unknown", "release": "unknown",
               "overall": "unknown"}
    if sound_contract_path != PHASE07_SOUND_CONTRACT_PATH:
        return {"status": "active_sound_contract_rejected",
                "private_identity_recorded": False,
                "sound_outcomes": unknown}
    # Phase 07's calibration reruns the accepted visual predicates under the
    # current evaluator. Keep Phase 06's immutable contract and evidence as the
    # scenario source, without requiring its historical evaluator digest to
    # match the Phase 07 evaluator that will be bound into this freeze.
    scene_status, scene = validate_scene_contract(
        scene_contract_path, input_root, check_current_identity=False)
    calibration = _read_phase07_sound_contract(
        sound_contract_path, require_frozen=False)
    freshness = ensure_fresh_qualifier()
    if (scene_status != "active_scene_contract_valid" or scene is None or
            calibration is None or calibration.get("mode") != "calibrate" or
            str(freshness) != "fresh"):
        return {"status": "active_sound_contract_stale",
                "private_identity_recorded": False,
                "sound_outcomes": unknown}
    importer_identity = _production_importer_identity()
    qualifier_identity = _production_qualifier_identity()
    evaluator_identity = _production_evaluator_identity()
    code_identity = {"importer": importer_identity,
                     "qualifier": qualifier_identity}
    schedule = scene.get("schedule")
    if (not all(isinstance(value, dict) for value in code_identity.values()) or
            code_identity != calibration.get("code_identity") or
            code_identity["importer"] != freshness.importer_identity or
            code_identity["qualifier"] != freshness.qualifier_identity or
            evaluator_identity is None or
            evaluator_identity != calibration.get("evaluator_identity") or
            not isinstance(schedule, dict) or schedule != calibration.get("schedule")):
        return {"status": "active_sound_contract_stale",
                "private_identity_recorded": False,
                "sound_outcomes": unknown}
    try:
        pairs = find_pairs(input_root)
    except OSError:
        pairs = []
    current_media = ([_file_identity(path) for path in pairs[0]]
                     if len(pairs) == 1 else None)
    expected_schedule_identity = hashlib.sha256(
        json.dumps({"phase06_contract_identity": scene["contract_identity"],
                    "schedule": schedule}, sort_keys=True,
                   separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    outcomes = calibration.get("outcomes")
    recordings = calibration.get("recordings")
    expected_windows = {
        "action": {"music", "fire", "release"},
        "control": {"music", "control", "release"},
    }
    windows_ready = (isinstance(recordings, dict) and all(
        isinstance(recordings.get(role), dict) and
        isinstance(recordings[role].get("windows"), dict) and
        set(recordings[role]["windows"]) >= names
        for role, names in expected_windows.items()))
    visual_outcomes = (outcomes.get("visual_predicates")
                       if isinstance(outcomes, dict) else None)
    if (current_media != scene.get("media_identity") or
            calibration.get("media_identity") != scene.get("media_identity") or
            calibration.get("phase06_contract_identity") != scene.get("contract_identity") or
            calibration.get("phase06_contract_sha256") !=
                _sha256_path(scene_contract_path) or
            calibration.get("schedule_identity") != expected_schedule_identity or
            not isinstance(visual_outcomes, dict) or
            visual_outcomes.get("overall") != "pass" or
            outcomes.get("calibration") != "windows_ready" or not windows_ready):
        return {"status": "active_sound_contract_stale",
                "private_identity_recorded": False,
                "sound_outcomes": unknown}
    run_directory = _create_active_scene_run_directory(PHASE07_RUN_ROOT)
    if run_directory is None:
        return {"status": "private_capture_path_unavailable",
                "private_identity_recorded": False,
                "sound_outcomes": unknown}
    frozen = dict(calibration)
    frozen.update({
        "mode": "frozen",
        "thresholds": PHASE07_SOUND_THRESHOLDS,
        "criteria_identity": _phase07_criteria_identity(
            PHASE07_SOUND_THRESHOLDS),
        "calibration_identity": calibration["contract_identity"],
        "frozen": True,
        "freeze_report": (run_directory / "sound-contract-freeze.json").relative_to(
            Path("local/qualification")).as_posix(),
    })
    frozen_outcomes = frozen.get("outcomes")
    if isinstance(frozen_outcomes, dict):
        frozen["outcomes"] = {**frozen_outcomes,
                               "criteria_freeze": "recorded"}
    freeze_report = run_directory / "sound-contract-freeze.json"
    report_written = write_report(freeze_report, {
        "status": "criteria_freeze_prepared",
        "calibration_identity": frozen["calibration_identity"],
        "criteria_identity": frozen["criteria_identity"],
        "sound_outcomes": {
            key: value for key, value in
            (frozen.get("outcomes", {}).items()
             if isinstance(frozen.get("outcomes"), dict) else [])
            if key in {"music", "fire", "release", "overall"}},
    })
    contract_written = (report_written and _write_phase07_sound_contract(
        sound_contract_path, frozen, run_directory))
    source_outcomes = frozen.get("outcomes")
    sound_outcomes = ({key: source_outcomes.get(key, "unknown")
                       for key in ("music", "fire", "release", "overall")}
                      if isinstance(source_outcomes, dict) else unknown)
    sound_outcomes = {key: (value if value in {"pass", "fail", "unknown"}
                             else "unknown")
                      for key, value in sound_outcomes.items()}
    return {
        "status": ("active_scene_sound_contract_frozen" if contract_written else
                   "active_sound_contract_freeze_failed"),
        "private_identity_recorded": contract_written,
        "criteria_outcome": "frozen" if contract_written else "incomplete",
        "sound_outcomes": sound_outcomes,
    }


def _phase07_sound_windows(schedule: object, role: str
                           ) -> str | None:
    parsed = _active_scene_schedule_masks(schedule)
    if parsed is None or role not in ("action", "control"):
        return None
    fire_events = parsed["fire"][role]
    start, release = fire_events[0][0], fire_events[-1][0]
    active_frames = schedule["active_frames"]
    music_first = start - SOUND_WINDOW_MAX_FRAMES
    music_last = start - 1
    effect_last = min(release - 1, start + 23)
    release_first = release
    release_last = min(active_frames - 1, release + 24)
    if (music_first < 0 or effect_last < start or
            release_first > release_last):
        return None
    effect_name = "fire" if role == "action" else "control"
    windows = (
        ("music", music_first, music_last),
        (effect_name, start, effect_last),
        ("release", release_first, release_last),
    )
    return ",".join(f"{name}:{first}-{last}"
                     for name, first, last in windows)


def active_scene_contract_is_valid(contract: object) -> bool:
    required = {
        "schema_version", "mode", "code_identity", "media_identity",
        "evaluator_identity", "configuration_identity", "schedule",
        "t0_frame", "endpoint_frame",
        "checkpoints", "regions", "predicates", "limits", "frozen",
        "contract_identity", "sampled_inputs", "requested_frames",
        "completed_frames", "observations", "outcomes",
    }
    if (not isinstance(contract, dict) or not required.issubset(contract) or
            type(contract.get("schema_version")) is not int or
            contract["schema_version"] != 1 or
            type(contract.get("frozen")) is not bool or
            not isinstance(contract.get("contract_identity"), str) or
            re.fullmatch(r"[0-9a-f]{64}", contract["contract_identity"]) is None):
        return False
    evaluator_identity = contract.get("evaluator_identity")
    if (not isinstance(evaluator_identity, dict) or
            set(evaluator_identity) != {"path", "scope", "sha256"} or
            not _absolute_identity_path(evaluator_identity.get("path")) or
            evaluator_identity.get("scope") != "production" or
            not isinstance(evaluator_identity.get("sha256"), str) or
            re.fullmatch(r"[0-9a-f]{64}", evaluator_identity["sha256"]) is None):
        return False
    payload = {key: value for key, value in contract.items()
               if key != "contract_identity"}
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True).encode("utf-8")
    except (TypeError, ValueError):
        return False
    return hashlib.sha256(encoded).hexdigest() == contract["contract_identity"]


_ACTIVE_SCENE_PAIR_NAMES = frozenset((
    "right", "left", "fire", "combined", "scroll"))
_ACTIVE_SCENE_REGION_NAMES = frozenset((
    "actor", "projectile", "background", "composition", "hud", "playfield"))


def _active_scene_composition_references_valid(
        references: object, contract: dict[str, object],
        minimum_observations: int) -> bool:
    schedule = contract.get("schedule")
    regions = contract.get("regions")
    if (not isinstance(references, list) or not isinstance(schedule, dict) or
            not isinstance(regions, dict) or
            not isinstance(regions.get("composition"), list)):
        return False
    schedule_pairs = schedule.get("pairs")
    if not isinstance(schedule_pairs, dict) or not isinstance(schedule_pairs.get("right"), dict):
        return False
    captures = schedule_pairs["right"].get("capture_frames")
    composition = regions["composition"]
    if not isinstance(captures, list):
        return False
    claims: dict[str, set[tuple[str, str, int]]] = {"palette": set(), "layer": set()}
    seen: set[tuple[str, str, int, str]] = set()
    patches: set[tuple[str, str, int, tuple[int, ...]]] = set()
    for reference in references:
        if (not isinstance(reference, dict) or set(reference) != {
                "pair", "role", "frame", "box", "sha256", "claim"}):
            return False
        pair, role, frame, box, digest, claim = (
            reference[key] for key in ("pair", "role", "frame", "box", "sha256", "claim"))
        if (not isinstance(pair, str) or pair not in _ACTIVE_SCENE_PAIR_NAMES or
                not isinstance(role, str) or role not in ("action", "control") or
                type(frame) is not int or frame not in captures or
                not isinstance(claim, str) or claim not in claims or
                not isinstance(box, list) or len(box) != 4 or
                any(type(value) is not int for value in box) or
                not isinstance(digest, str) or
                re.fullmatch(r"[0-9a-f]{64}", digest) is None):
            return False
        x, y, width, height = box
        cx, cy, cwidth, cheight = composition
        if (x < cx or y < cy or width <= 0 or height <= 0 or
                x + width > cx + cwidth or y + height > cy + cheight or
                width * height >= 320 * 224):
            return False
        identity = (pair, role, frame, claim)
        patch_identity = (pair, role, frame, tuple(box))
        if identity in seen or patch_identity in patches:
            return False
        seen.add(identity)
        patches.add(patch_identity)
        claims[claim].add((pair, role, frame))
    return all(len(claims[name]) >= minimum_observations for name in claims)


def _active_scene_schedule_masks(
        schedule: object) -> dict[str, dict[str, list[tuple[int, int]]]] | None:
    if not isinstance(schedule, dict) or set(schedule) != {
            "setup", "entry_inputs", "active_frames", "frame_cycles", "pairs"}:
        return None
    active_frames = schedule.get("active_frames")
    if (schedule.get("setup") != "scripted_start" or
            type(active_frames) is not int or
            not 1 <= active_frames <= MAX_ACTIVE_FRAMES or
            schedule.get("frame_cycles") != 202752):
        return None
    entry_inputs = schedule.get("entry_inputs")
    if not isinstance(entry_inputs, str):
        return None
    if entry_inputs:
        if not _active_schedule_valid(active_frames, entry_inputs, None, None):
            return None
        entry_events = [(int(frame, 10), int(mask, 16))
                        for frame, mask in re.findall(
                            r"([0-9]+):0x([0-9a-fA-F]+)", entry_inputs)]
        if len(entry_events) != len(entry_inputs.split(",")):
            return None
    else:
        entry_events = []
    if len(entry_events) > MAX_ACTIVE_INPUT_EVENTS:
        return None
    pairs = schedule.get("pairs")
    if not isinstance(pairs, dict) or set(pairs) != _ACTIVE_SCENE_PAIR_NAMES:
        return None
    parsed: dict[str, dict[str, list[tuple[int, int]]]] = {}
    for name, pair in pairs.items():
        if not isinstance(pair, dict) or set(pair) != {
                "action", "control", "capture_frames"}:
            return None
        events_by_role: dict[str, list[tuple[int, int]]] = {}
        for role in ("action", "control"):
            raw = pair.get(role)
            if not isinstance(raw, str) or not _active_schedule_valid(
                    active_frames, raw, None, None):
                return None
            events = [(int(frame, 10), int(mask, 16))
                      for frame, mask in re.findall(
                          r"([0-9]+):0x([0-9a-fA-F]+)", raw)]
            if len(events) != len(raw.split(",")) or len(events) != 2:
                return None
            events_by_role[role] = events
        action_events = events_by_role["action"]
        control_events = events_by_role["control"]
        if ([frame for frame, _ in action_events] !=
                [frame for frame, _ in control_events] or
                action_events[-1][1] != 0 or control_events[-1][1] != 0):
            return None
        start_frame, start_mask = action_events[0]
        control_frame, control_mask = control_events[0]
        expected = {"right": (0x20, 0), "left": (0x10, 0),
                    "fire": (0x40, 0), "combined": (0x60, 0x20),
                    "scroll": (0x20, 0)}[name]
        captures = pair.get("capture_frames")
        if ((start_mask, control_mask) != expected or start_frame != control_frame or
                start_frame <= 0 or not isinstance(captures, list) or
                len(captures) != MAX_ACTIVE_CAPTURE_FRAMES or
                any(type(frame) is not int or not 0 <= frame < active_frames
                    for frame in captures) or
                captures != sorted(set(captures))):
            return None
        start_frame = action_events[0][0]
        release_frame = action_events[-1][0]
        held_samples = sum(start_frame <= frame < release_frame
                           for frame in captures)
        release_samples = sum(frame > release_frame for frame in captures)
        minimum_held = 3 if name == "scroll" else 2
        minimum_release = (2 if name == "fire" else 0 if name == "scroll" else 1)
        if (start_frame >= release_frame or held_samples < minimum_held or
                release_samples < minimum_release):
            return None
        parsed[name] = events_by_role
        for role in ("action", "control"):
            combined = sorted(entry_events + events_by_role[role])
            combined_frames = [frame for frame, _ in combined]
            combined_text = ",".join(f"{frame}:0x{mask:x}"
                                     for frame, mask in combined)
            if (len(combined) > MAX_ACTIVE_INPUT_EVENTS or
                    len(combined_frames) != len(set(combined_frames)) or
                    len(combined_text.encode("ascii")) > MAX_ACTIVE_SCHEDULE_BYTES):
                return None
    return parsed


def _active_scene_input_events(
        schedule: object, pair_name: str, role: str) -> list[tuple[int, int]] | None:
    parsed = _active_scene_schedule_masks(schedule)
    if (parsed is None or pair_name not in parsed or
            role not in ("action", "control")):
        return None
    entry_inputs = schedule["entry_inputs"]
    entry_events = ([(int(frame, 10), int(mask, 16))
                     for frame, mask in re.findall(
                         r"([0-9]+):0x([0-9a-fA-F]+)", entry_inputs)]
                    if entry_inputs else [])
    return sorted(entry_events + parsed[pair_name][role])


def active_scene_configuration_identity(schedule: dict[str, object]) -> str:
    configuration = {
        "input_root": "local/roms",
        "prelude": SCRIPTED_START_INPUT_SCRIPT,
        "schedule": schedule,
    }
    encoded = json.dumps(configuration, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def active_scene_native_contract_is_valid(contract: object) -> bool:
    outcomes = contract.get("outcomes") if isinstance(contract, dict) else None
    if (not active_scene_contract_is_valid(contract) or
            contract.get("mode") != "native" or
            contract.get("frozen") is not True or
            not isinstance(outcomes, dict) or
            outcomes.get("calibration") != "captures_ready" or
            outcomes.get("semantic_t0") != "observed"):
        return False
    t0 = contract.get("t0_frame")
    endpoint = contract.get("endpoint_frame")
    if (type(t0) is not int or type(endpoint) is not int or
            not 0 <= t0 < endpoint < MAX_ACTIVE_FRAMES):
        return False
    identity = contract.get("code_identity")
    if (not isinstance(identity, dict) or set(identity) != {"importer", "qualifier"} or
            any(not isinstance(value, dict) or
                set(value) != {"path", "scope", "sha256"} or
                not _absolute_identity_path(value.get("path")) or
                value.get("scope") != "production" or
                not isinstance(value.get("sha256"), str) or
                re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None
                for value in identity.values())):
        return False
    media = contract.get("media_identity")
    if (not isinstance(media, list) or len(media) != 2 or
            any(not isinstance(item, dict) or
                type(item.get("size")) is not int or item["size"] <= 0 or
                not isinstance(item.get("sha256"), str) or
                re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None
                for item in media)):
        return False
    if (not isinstance(contract.get("configuration_identity"), str) or
            re.fullmatch(r"[0-9a-f]{64}", contract["configuration_identity"]) is None):
        return False
    schedule = contract.get("schedule")
    if _active_scene_schedule_masks(schedule) is None:
        return False
    if contract["configuration_identity"] != active_scene_configuration_identity(schedule):
        return False
    parsed_schedule = _active_scene_schedule_masks(schedule)
    if any(events[0][0] <= t0 for pair in parsed_schedule.values()
           for events in pair.values()):
        return False
    entry_events = [(int(frame, 10), int(mask, 16))
                    for frame, mask in re.findall(
                        r"([0-9]+):0x([0-9a-fA-F]+)",
                        schedule["entry_inputs"])]
    if any(frame > t0 or (frame == t0 and mask != 0)
           for frame, mask in entry_events):
        return False
    expected_entry_samples = [{"frame": frame, "mask": mask}
                              for frame, mask in entry_events]
    if contract.get("sampled_inputs") != expected_entry_samples:
        return False
    common_capture_frames = schedule["pairs"]["right"]["capture_frames"]
    if (common_capture_frames[0] != t0 or common_capture_frames[-1] != endpoint or
            any(pair["capture_frames"] != common_capture_frames
                for pair in schedule["pairs"].values())):
        return False
    checkpoints = contract.get("checkpoints")
    if not isinstance(checkpoints, list) or len(checkpoints) != MAX_ACTIVE_CAPTURE_FRAMES:
        return False
    checkpoint_frames: list[int] = []
    for item in checkpoints:
        if (not isinstance(item, dict) or
                type(item.get("frame")) is not int or
                not 0 <= item["frame"] < MAX_ACTIVE_FRAMES or
                not isinstance(item.get("file"), str) or
                re.fullmatch(r"frame-[0-9]{4}\.ppm", item["file"]) is None or
                item["file"] != f"frame-{item['frame']:04d}.ppm" or
                not isinstance(item.get("sha256"), str) or
                re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None):
            return False
        checkpoint_frames.append(item["frame"])
    if checkpoint_frames != sorted(set(checkpoint_frames)):
        return False
    if t0 not in checkpoint_frames:
        return False
    if max(max(pair["capture_frames"])
           for pair in schedule["pairs"].values()) != endpoint:
        return False
    regions = contract.get("regions")
    if not isinstance(regions, dict) or set(regions) != _ACTIVE_SCENE_REGION_NAMES:
        return False
    for box in regions.values():
        if (not isinstance(box, list) or len(box) != 4 or
                any(type(value) is not int for value in box)):
            return False
        x, y, width, height = box
        if (width <= 0 or height <= 0 or x < 0 or y < 0 or
                x + width > 320 or y + height > 224):
            return False
    actor_x, actor_y, actor_width, actor_height = regions["actor"]
    background_x, background_y, background_width, background_height = regions["background"]
    if (actor_x < background_x + background_width and
            background_x < actor_x + actor_width and
            actor_y < background_y + background_height and
            background_y < actor_y + actor_height):
        return False
    predicates = contract.get("predicates")
    if (not isinstance(predicates, dict) or
            set(predicates) != {"scene", "actor", "projectile", "movement",
                                "background", "combined", "composition"}):
        return False
    numeric_keys = {
        "scene": {"min_actor_pixels", "min_hud_pixels", "min_playfield_colors"},
        "actor": {"min_red", "min_green", "max_blue"},
        "projectile": {"min_red", "min_green", "max_blue", "min_pixels",
                       "min_player_separation_px", "min_outward_dx",
                       "min_track_overlap"},
        "movement": {"min_actor_dx", "min_observations", "min_actor_pixels",
                     "min_track_overlap"},
        "background": {"min_horizontal_shift_px", "min_feature_overlap",
                       "min_observations", "min_unique_colors"},
        "combined": {"max_actor_dx_error", "min_projectile_pixels"},
        "composition": {"min_unique_colors", "min_observations", "references"},
    }
    for name, required_keys in numeric_keys.items():
        data = predicates[name]
        if not isinstance(data, dict) or set(data) != required_keys:
            return False
        numeric_values = {key: value for key, value in data.items()
                          if key != "references"}
        if any(type(value) not in (int, float) or not math.isfinite(value) or
               value < 0 for value in numeric_values.values()):
            return False
    scene = predicates["scene"]
    actor = predicates["actor"]
    projectile = predicates["projectile"]
    movement = predicates["movement"]
    background = predicates["background"]
    combined = predicates["combined"]
    composition = predicates["composition"]
    positive_ints = (
        (scene["min_actor_pixels"], 3), (scene["min_hud_pixels"], 1),
        (scene["min_playfield_colors"], 2), (projectile["min_pixels"], 2),
        (projectile["min_player_separation_px"], 2),
        (projectile["min_outward_dx"], 2), (movement["min_actor_dx"], 2),
        (movement["min_observations"], 2), (movement["min_actor_pixels"], 4),
        (background["min_horizontal_shift_px"], 2),
        (background["min_observations"], 2), (background["min_unique_colors"], 3),
        (combined["min_projectile_pixels"], 2),
        (composition["min_unique_colors"], 2),
        (composition["min_observations"], 2),
    )
    if any(type(value) is not int or value < minimum
           for value, minimum in positive_ints):
        return False
    if (any(type(value) is not int or not 0 <= value <= 255
            for value in (actor["min_red"], actor["min_green"], actor["max_blue"],
                          projectile["min_red"], projectile["min_green"],
                          projectile["max_blue"]))):
        return False
    if any(minimum_red <= 0 or minimum_green <= 0 or maximum <= 0 or
           maximum >= min(minimum_red, minimum_green)
           for minimum_red, minimum_green, maximum in (
               (actor["min_red"], actor["min_green"], actor["max_blue"]),
               (projectile["min_red"], projectile["min_green"],
                projectile["max_blue"]))):
        return False
    if (type(combined["max_actor_dx_error"]) not in (int, float) or
            not math.isfinite(combined["max_actor_dx_error"]) or
            combined["max_actor_dx_error"] < 0 or
            combined["max_actor_dx_error"] >= movement["min_actor_dx"]):
        return False
    for data, key in ((movement, "min_track_overlap"),
                      (projectile, "min_track_overlap"),
                      (background, "min_feature_overlap")):
        value = data[key]
        if (type(value) not in (int, float) or not math.isfinite(value) or
                not 0 < value <= 1):
            return False
    max_observations = MAX_ACTIVE_CAPTURE_FRAMES - 1
    if (movement["min_observations"] > max_observations or
            background["min_observations"] > max_observations or
            composition["min_observations"] > max_observations or
            projectile["min_track_overlap"] < 0.2 or
            movement["min_track_overlap"] < 0.2 or
            background["min_feature_overlap"] < 0.5):
        return False
    references = composition["references"]
    if not _active_scene_composition_references_valid(
            references, contract, composition["min_observations"]):
        return False
    region_sizes = {name: box[2] * box[3] for name, box in regions.items()}
    if (scene["min_actor_pixels"] > region_sizes["actor"] or
            movement["min_actor_pixels"] > region_sizes["actor"] or
            projectile["min_pixels"] > region_sizes["projectile"] or
            combined["min_projectile_pixels"] > region_sizes["projectile"] or
            background["min_unique_colors"] > region_sizes["background"] or
            composition["min_unique_colors"] > region_sizes["composition"] or
            background["min_horizontal_shift_px"] >
            min(128, regions["background"][2] // 3) or
            projectile["min_outward_dx"] > regions["projectile"][2]):
        return False
    captures = schedule["pairs"]["right"]["capture_frames"]
    if (any(sum(parsed_schedule[name]["action"][0][0] <= frame <
                   parsed_schedule[name]["action"][-1][0] for frame in captures) <
               movement["min_observations"]
               for name in ("right", "left", "combined")) or
            sum(1 for first, second in zip(captures, captures[1:])
                if parsed_schedule["scroll"]["action"][0][0] <= first < second <
                parsed_schedule["scroll"]["action"][-1][0]) <
            background["min_observations"] or
            sum(parsed_schedule["fire"]["action"][0][0] <= frame <
                parsed_schedule["fire"]["action"][-1][0] for frame in captures) < 2):
        return False
    limits = contract.get("limits")
    if (not isinstance(limits, dict) or
            limits != {"active_frames": schedule["active_frames"],
                       "capture_count": MAX_ACTIVE_CAPTURE_FRAMES,
                       "host_timeout_seconds": NATIVE_QUALIFICATION_TIMEOUT_SECONDS,
                       "report_bytes_limit": QUALIFICATION_REPORT_MAX_BYTES}):
        return False
    if (contract.get("requested_frames") != schedule["active_frames"] or
            contract.get("completed_frames") != schedule["active_frames"] or
            not isinstance(contract.get("sampled_inputs"), list) or
            not isinstance(contract.get("observations"), dict) or
            contract["observations"].get("status") != "active_frames_completed" or
            not isinstance(contract.get("outcomes"), dict)):
        return False
    observations = contract["observations"]
    if (not isinstance(observations.get("calibration_configuration_identity"), str) or
            re.fullmatch(r"[0-9a-f]{64}",
                         observations["calibration_configuration_identity"]) is None or
            observations.get("images") != checkpoints):
        return False
    return True


def private_active_sound_path_is_valid(path: Path) -> bool:
    return (re.fullmatch(
        r"local/qualification/phase07/run-[0-9a-f]{32}/sound-(music|fire|control|release)\.s16le",
        path.as_posix()) is not None and
        all(not parent.is_symlink() for parent in (
            Path("local"), Path("local/qualification"), PHASE07_RUN_ROOT,
            path.parent)) and not path.is_symlink() and ignored(path))


def _rgb_region_pixels(frame: bytes, box: list[int]) -> list[tuple[int, int, int]] | None:
    if (not isinstance(frame, bytes) or len(frame) != 320 * 224 * 3 or
            not isinstance(box, list) or len(box) != 4 or
            any(type(value) is not int for value in box)):
        return None
    x, y, width, height = box
    if (x < 0 or y < 0 or width <= 0 or height <= 0 or
            x + width > 320 or y + height > 224):
        return None
    pixels: list[tuple[int, int, int]] = []
    for row in range(y, y + height):
        offset = (row * 320 + x) * 3
        for column in range(width):
            at = offset + column * 3
            pixels.append((frame[at], frame[at + 1], frame[at + 2]))
    return pixels


def _scene_actor_points(contract: dict[str, object], frame: bytes) -> list[tuple[int, int]] | None:
    regions = contract["regions"]
    thresholds = contract["predicates"]["actor"]
    pixels = _rgb_region_pixels(frame, regions["actor"])
    if pixels is None:
        return None
    x, y, width, height = regions["actor"]
    px, py, pwidth, pheight = regions["projectile"]
    points: list[tuple[int, int]] = []
    for index, (red, green, blue) in enumerate(pixels):
        point = (x + index % width, y + index // width)
        # The reserved effect strip may overlap the player search region. Its
        # larger flash must never become the tracked actor's color component.
        if px <= point[0] < px + pwidth and py <= point[1] < py + pheight:
            continue
        if (red >= thresholds["min_red"] and green >= thresholds["min_green"] and
                blue <= thresholds["max_blue"]):
            points.append(point)
    return points


def _scene_projectile_points(contract: dict[str, object], frame: bytes) -> list[tuple[int, int]] | None:
    regions = contract["regions"]
    thresholds = contract["predicates"]["projectile"]
    pixels = _rgb_region_pixels(frame, regions["projectile"])
    if pixels is None:
        return None
    x, y, width, _height = regions["projectile"]
    return [(x + index % width, y + index // width)
            for index, (red, green, blue) in enumerate(pixels)
            if red >= thresholds["min_red"] and green >= thresholds["min_green"] and
            blue <= thresholds["max_blue"]]


def _scene_largest_component(points: list[tuple[int, int]]) -> set[tuple[int, int]]:
    remaining = set(points)
    largest: set[tuple[int, int]] = set()
    while remaining:
        start = remaining.pop()
        component = {start}
        pending = [start]
        while pending:
            x, y = pending.pop()
            for neighbor in ((x + dx, y + dy)
                             for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                             if dx or dy):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    pending.append(neighbor)
        if len(component) > len(largest):
            largest = component
    return largest


def _scene_components(points: list[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    remaining = set(points)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        pending = [start]
        while pending:
            x, y = pending.pop()
            for neighbor in ((x + dx, y + dy)
                             for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                             if dx or dy):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    pending.append(neighbor)
        components.append(component)
    return components


def _scene_centroid(points: set[tuple[int, int]]) -> tuple[float, float]:
    return (sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points))


def _scene_track_candidates(first: set[tuple[int, int]],
                            second: set[tuple[int, int]],
                            *, max_dx: int, max_dy: int,
                            minimum_overlap: float,
                            allow_reflection: bool = False) -> set[tuple[int, int]]:
    if not first or not second:
        return set()
    orientations = [first]
    if allow_reflection:
        horizontal_axis = min(x for x, y in first) + max(x for x, y in first)
        orientations.append({(horizontal_axis - x, y) for x, y in first})
    # Retain every distinct best vector. A symmetric silhouette's identical
    # vector is one hypothesis; a pose tie is unresolved by this pair alone.
    best_overlap = -1
    best: set[tuple[int, int]] = set()
    for orientation in orientations:
        for dy in range(-max_dy, max_dy + 1):
            for dx in range(-max_dx, max_dx + 1):
                overlap = sum((x + dx, y + dy) in second for x, y in orientation)
                if overlap > best_overlap:
                    best_overlap, best = overlap, {(dx, dy)}
                elif overlap == best_overlap:
                    best.add((dx, dy))
    return best if best_overlap / max(len(first), len(second)) >= minimum_overlap else set()


def _scene_track_translation(first: set[tuple[int, int]],
                             second: set[tuple[int, int]],
                             *, max_dx: int, max_dy: int,
                             minimum_overlap: float,
                             allow_reflection: bool = False) -> tuple[int, int] | None:
    candidates = _scene_track_candidates(
        first, second, max_dx=max_dx, max_dy=max_dy,
        minimum_overlap=minimum_overlap, allow_reflection=allow_reflection)
    return next(iter(candidates)) if len(candidates) == 1 else None


def _scene_actor_component(contract: dict[str, object], frame: bytes,
                           minimum_pixels: int) -> set[tuple[int, int]] | None:
    points = _scene_actor_points(contract, frame)
    if points is None:
        return None
    component = _scene_largest_component(points)
    return component if len(component) >= minimum_pixels else None


def _scene_projectile_components(
        contract: dict[str, object], frame: bytes,
        minimum_pixels: int) -> list[set[tuple[int, int]]]:
    points = _scene_projectile_points(contract, frame)
    if points is None:
        return []
    actor = _scene_actor_component(
        contract, frame, contract["predicates"]["movement"]["min_actor_pixels"])
    if actor is None:
        return []
    actor_center = _scene_centroid(actor)
    minimum_separation = contract["predicates"]["projectile"][
        "min_player_separation_px"]
    separated: list[set[tuple[int, int]]] = []
    for component in _scene_components(points):
        if len(component) < minimum_pixels:
            continue
        if actor_center is not None:
            x, y = _scene_centroid(component)
            if math.hypot(x - actor_center[0], y - actor_center[1]) < minimum_separation:
                continue
        separated.append(component)
    return separated


def _scene_projectile_track(
        contract: dict[str, object], action: list[bytes], control: list[bytes],
        held_indices: list[int], *, minimum_pixels: int | None = None
        ) -> tuple[int, int] | None:
    if len(held_indices) < 2:
        return None
    thresholds = contract["predicates"]["projectile"]
    minimum_pixels = (thresholds["min_pixels"] if minimum_pixels is None
                      else minimum_pixels)
    max_dx = max(contract["regions"]["projectile"][2], 1)
    max_dy = max(contract["regions"]["projectile"][3], 1)
    for source_position, source_index in enumerate(held_indices[:-1]):
        source_components = _scene_projectile_components(
            contract, action[source_index], minimum_pixels)
        control_source = _scene_projectile_components(
            contract, control[source_index], minimum_pixels)
        if control_source:
            continue
        for target_index in held_indices[source_position + 1:]:
            target_components = _scene_projectile_components(
                contract, action[target_index], minimum_pixels)
            control_target = _scene_projectile_components(
                contract, control[target_index], minimum_pixels)
            if control_target:
                continue
            for source in source_components:
                sx, sy = _scene_centroid(source)
                for target in target_components:
                    tx, ty = _scene_centroid(target)
                    dx, dy = round(tx - sx), round(ty - sy)
                    if dx < thresholds["min_outward_dx"] or abs(dx) > max_dx or abs(dy) > max_dy:
                        continue
                    overlap = sum((x + dx, y + dy) in target for x, y in source)
                    if overlap / max(len(source), len(target)) < thresholds["min_track_overlap"]:
                        continue
                    return source_index, target_index
    return None


def _scene_region_bytes(frame: bytes, box: list[int]) -> bytes | None:
    if (not isinstance(frame, bytes) or len(frame) != 320 * 224 * 3 or
            not isinstance(box, list) or len(box) != 4 or
            any(type(value) is not int for value in box)):
        return None
    x, y, width, height = box
    if (x < 0 or y < 0 or width <= 0 or height <= 0 or
            x + width > 320 or y + height > 224):
        return None
    rows = []
    for row in range(y, y + height):
        start = (row * 320 + x) * 3
        rows.append(frame[start:start + width * 3])
    return b"".join(rows)


def _scene_horizontal_translation(
        contract: dict[str, object], first: bytes, second: bytes) -> tuple[int, float] | None:
    box = contract["regions"]["background"]
    x, y, width, height = box
    threshold = contract["predicates"]["background"]
    first_pixels = _rgb_region_pixels(first, box)
    second_pixels = _rgb_region_pixels(second, box)
    if (first_pixels is None or second_pixels is None or
            len(set(first_pixels)) < threshold["min_unique_colors"]):
        return None
    maximum_shift = min(128, width // 3)
    if maximum_shift < threshold["min_horizontal_shift_px"]:
        return None
    scores: list[tuple[float, int]] = []
    for shift in range(-maximum_shift, maximum_shift + 1):
        overlap_width = width - abs(shift)
        matches = 0
        total = overlap_width * height
        for row in range(height):
            first_start = row * width + max(0, -shift)
            second_start = row * width + max(0, shift)
            for column in range(overlap_width):
                if first_pixels[first_start + column] == second_pixels[second_start + column]:
                    matches += 1
        scores.append((matches / total, shift))
    scores.sort(reverse=True)
    best_score, best_shift = scores[0]
    runner_up = scores[1][0] if len(scores) > 1 else -1.0
    zero_score = next(score for score, shift in scores if shift == 0)
    if (best_score < threshold["min_feature_overlap"] or
            best_score - runner_up < 0.01 or
            (best_shift != 0 and
             (abs(best_shift) < threshold["min_horizontal_shift_px"] or
              best_score <= zero_score))):
        return None
    return best_shift, best_score


def _scene_actor_translation_candidates(contract: dict[str, object], baseline: bytes,
                                        current: bytes) -> set[tuple[int, int]]:
    minimum_pixels = contract["predicates"]["movement"]["min_actor_pixels"]
    before = _scene_actor_component(contract, baseline, minimum_pixels)
    after = _scene_actor_component(contract, current, minimum_pixels)
    if before is None or after is None:
        return set()
    _, _, width, height = contract["regions"]["actor"]
    return _scene_track_candidates(
        before, after, max_dx=min(width - 1, 48), max_dy=min(height - 1, 24),
        minimum_overlap=contract["predicates"]["movement"]["min_track_overlap"],
        allow_reflection=True)


def _scene_actor_translation(contract: dict[str, object], baseline: bytes,
                             current: bytes) -> tuple[int, int] | None:
    candidates = _scene_actor_translation_candidates(contract, baseline, current)
    return next(iter(candidates)) if len(candidates) == 1 else None


def _scene_actor_track_translations(contract: dict[str, object], frames: list[bytes]
                                    ) -> list[tuple[int, int] | None]:
    """Resolve pose ties only with agreeing, independently unique two-edge paths.

    Every accepted vector remains a highest-overlap direct candidate. Intermediate
    anchors must already be unique against t0; inferred vectors cannot bootstrap
    one another, and the opposite role never selects a preferred hypothesis.
    """
    if not frames or len(frames) > MAX_ACTIVE_CAPTURE_FRAMES:
        return []
    candidates = [_scene_actor_translation_candidates(contract, frames[0], frame)
                  for frame in frames]
    direct = [next(iter(values)) if len(values) == 1 else None for values in candidates]
    resolved = direct.copy()
    for index, values in enumerate(candidates):
        if len(values) < 2:
            continue
        paths = set()
        for anchor, shift in enumerate(direct):
            if anchor in (0, index) or shift is None:
                continue
            edge = _scene_actor_translation_candidates(contract, frames[anchor], frames[index])
            if len(edge) == 1:
                dx, dy = next(iter(edge))
                paths.add((shift[0] + dx, shift[1] + dy))
        if len(paths) == 1:
            vector = next(iter(paths))
            if vector in values:
                resolved[index] = vector
    return resolved


def _scene_movement_evidence(
        contract: dict[str, object], action: list[bytes], control: list[bytes],
        held_indices: list[int], direction: int) -> list[tuple[int, int, int]]:
    thresholds = contract["predicates"]["movement"]
    evidence: list[tuple[int, int, int]] = []
    for index in held_indices:
        action_shift = _scene_actor_translation(contract, action[0], action[index])
        control_shift = _scene_actor_translation(contract, control[0], control[index])
        if action_shift is None or control_shift is None:
            continue
        actor_dx = direction * action_shift[0]
        causal_dx = direction * (action_shift[0] - control_shift[0])
        if (actor_dx >= thresholds["min_actor_dx"] and
                causal_dx >= thresholds["min_actor_dx"]):
            evidence.append((index, action_shift[0], control_shift[0]))
    return evidence


def _scene_complete_samples(value: object, names: tuple[str, ...]) -> bool:
    return (isinstance(value, dict) and
            all(isinstance(value.get(name), list) and
                len(value[name]) == MAX_ACTIVE_CAPTURE_FRAMES and
                all(isinstance(frame, bytes) and len(frame) == 320 * 224 * 3
                    for frame in value[name]) for name in names))


def evaluate_active_scene_pairs(contract: dict[str, object],
                                runs: object, *, frontend_intervals: bool = False) -> dict[str, str]:
    predicate_names = ("scene", "composition", "right", "left", "projectile",
                       "release", "combined", "scroll")
    unknown = {name: "unknown" for name in predicate_names}
    unknown["overall"] = "unknown"
    if (not isinstance(contract, dict) or not isinstance(runs, dict) or
            not isinstance(contract.get("regions"), dict) or
            not isinstance(contract.get("predicates"), dict)):
        return unknown
    schedule = contract.get("schedule")
    parsed_schedule = _active_scene_schedule_masks(schedule)
    if parsed_schedule is None:
        return unknown
    schedule_pairs = schedule["pairs"]
    capture_frames = schedule_pairs["right"]["capture_frames"]
    if any(pair["capture_frames"] != capture_frames
           for pair in schedule_pairs.values()):
        return unknown
    complete_pairs = {
        name: runs.get(name) for name in _ACTIVE_SCENE_PAIR_NAMES
        if _scene_complete_samples(runs.get(name), ("action", "control"))
    }
    if not frontend_intervals and len(complete_pairs) == len(_ACTIVE_SCENE_PAIR_NAMES):
        shared_t0 = complete_pairs["right"]["control"][0]
        if any(pair[role][0] != shared_t0 for pair in complete_pairs.values()
               for role in ("action", "control")):
            unknown["overall"] = "fail"
            return unknown
    if frontend_intervals and len(complete_pairs) == len(_ACTIVE_SCENE_PAIR_NAMES):
        # Wall-clock screenshots need not be the same submitted frame. Require
        # equivalent scene anchors independently of later action/control deltas.
        baseline = complete_pairs["right"]["control"][0]
        baseline_hud = _scene_region_bytes(baseline, contract["regions"]["hud"])
        for pair in complete_pairs.values():
            for role in ("action", "control"):
                candidate = pair[role][0]
                actor = _scene_actor_translation(contract, baseline, candidate)
                scenery = _scene_horizontal_translation(contract, baseline, candidate)
                if (actor is None or abs(actor[0]) > 3 or abs(actor[1]) > 3 or
                        scenery is None or scenery[0] != 0 or
                        _scene_region_bytes(candidate, contract["regions"]["hud"]) != baseline_hud):
                    unknown["overall"] = "fail"
                    return unknown
    scene = runs.get("scene")
    if (isinstance(scene, dict) and scene.get("status") == "complete" and
            isinstance(scene.get("t0"), bytes) and isinstance(scene.get("endpoint"), bytes)):
        if ("right" in complete_pairs and
                scene["t0"] != complete_pairs["right"]["control"][0]):
            unknown["overall"] = "fail"
            return unknown
        actor_points = _scene_actor_points(contract, scene["t0"])
        hud = _rgb_region_pixels(scene["t0"], contract["regions"]["hud"])
        playfield = _rgb_region_pixels(scene["endpoint"], contract["regions"]["playfield"])
        if actor_points and hud is not None and playfield is not None:
            scene_thresholds = contract["predicates"]["scene"]
            hud_count = sum(max(pixel) >= ACTIVE_SCENE_HUD_FOREGROUND_THRESHOLD
                            for pixel in hud)
            playfield_colors = len(set(playfield))
            unknown["scene"] = ("pass" if hud_count >= scene_thresholds["min_hud_pixels"] and
                                playfield_colors >= scene_thresholds["min_playfield_colors"] and
                                len(actor_points) >=
                                scene_thresholds["min_actor_pixels"] else "fail")
    for name in ("right", "left", "combined", "scroll"):
        value = runs.get(name)
        if _scene_complete_samples(value, ("action", "control")):
            action = value["action"]
            control = value["control"]
            start_frame, _ = parsed_schedule[name]["action"][0]
            release_frame, _ = parsed_schedule[name]["action"][-1]
            held_indices = [index for index, frame in enumerate(capture_frames)
                            if start_frame <= frame < release_frame]
            if name in ("right", "left"):
                direction = 1 if name == "right" else -1
                evidence = _scene_movement_evidence(
                    contract, action, control, held_indices, direction)
                minimum = contract["predicates"]["movement"]["min_observations"]
                unknown[name] = "pass" if len(evidence) >= minimum else "fail"
            elif name == "combined":
                thresholds = contract["predicates"]["movement"]
                tolerance = contract["predicates"]["combined"]["max_actor_dx_error"]
                movement_observations = 0
                action_track = _scene_actor_track_translations(contract, action)
                control_track = _scene_actor_track_translations(contract, control)
                for index in held_indices:
                    action_shift = action_track[index]
                    control_shift = control_track[index]
                    if (action_shift is not None and control_shift is not None and
                            action_shift[0] >= thresholds["min_actor_dx"] and
                            control_shift[0] >= thresholds["min_actor_dx"] and
                            abs(action_shift[0] - control_shift[0]) <= tolerance):
                        movement_observations += 1
                combined_track = _scene_projectile_track(
                    contract, action, control, held_indices,
                    minimum_pixels=contract["predicates"]["combined"][
                        "min_projectile_pixels"])
                unknown[name] = (
                    "pass" if movement_observations >= thresholds["min_observations"] and
                    combined_track is not None else "fail")
            else:
                background_thresholds = contract["predicates"]["background"]
                transitions = list(zip(held_indices, held_indices[1:]))
                coherent: list[tuple[int, int]] = []
                expected_direction = 0
                for first_index, second_index in transitions:
                    action_shift = _scene_horizontal_translation(
                        contract, action[first_index], action[second_index])
                    control_shift = _scene_horizontal_translation(
                        contract, control[first_index], control[second_index])
                    if action_shift is None or control_shift is None:
                        continue
                    action_dx = action_shift[0]
                    causal_dx = action_dx - control_shift[0]
                    direction = 1 if action_dx > 0 else -1 if action_dx < 0 else 0
                    if (direction and abs(action_dx) >=
                            background_thresholds["min_horizontal_shift_px"] and
                            direction * causal_dx >=
                            background_thresholds["min_horizontal_shift_px"] and
                            (expected_direction in (0, direction))):
                        expected_direction = direction
                        coherent.append((first_index, second_index))
                required = background_thresholds["min_observations"]
                unknown[name] = "pass" if len(coherent) >= required else "fail"
    fire = runs.get("fire")
    if _scene_complete_samples(fire, ("action", "control")):
        fire_start = parsed_schedule["fire"]["action"][0][0]
        release_frame = parsed_schedule["fire"]["action"][-1][0]
        held_indices = [index for index, frame in enumerate(capture_frames)
                        if fire_start <= frame < release_frame]
        release_indices = [index for index, frame in enumerate(capture_frames)
                           if frame > release_frame]
        trajectory = _scene_projectile_track(
            contract, fire["action"], fire["control"], held_indices)
        projectile_minimum = contract["predicates"]["projectile"]["min_pixels"]
        released_absent = all(
            _scene_actor_component(
                contract, fire["action"][index],
                contract["predicates"]["movement"]["min_actor_pixels"]) is not None and
            not _scene_projectile_components(
                contract, fire["action"][index], projectile_minimum)
            for index in release_indices)
        unknown["projectile"] = "pass" if trajectory is not None else "fail"
        unknown["release"] = ("pass" if trajectory is not None and released_absent
                              else "fail")
    composition_thresholds = contract["predicates"]["composition"]
    references = composition_thresholds.get("references")
    if _active_scene_composition_references_valid(
            references, contract, composition_thresholds["min_observations"]):
        reference_results: list[bool] = []
        for reference in references:
            pair = runs.get(reference["pair"])
            if not _scene_complete_samples(pair, (reference["role"],)):
                reference_results = []
                break
            role_frames = pair[reference["role"]]
            try:
                frame_index = capture_frames.index(reference["frame"])
            except ValueError:
                reference_results = []
                break
            patch = _scene_region_bytes(role_frames[frame_index], reference["box"])
            pixels = _rgb_region_pixels(role_frames[frame_index], reference["box"])
            reference_results.append(
                patch is not None and hashlib.sha256(patch).hexdigest() ==
                reference["sha256"] and pixels is not None and
                len(set(pixels)) >= composition_thresholds["min_unique_colors"])
        if reference_results:
            unknown["composition"] = ("pass" if all(reference_results) else "fail")
    if all(unknown[name] == "pass" for name in predicate_names):
        unknown["overall"] = "pass"
    elif any(unknown[name] == "fail" for name in predicate_names):
        unknown["overall"] = "fail"
    return unknown


def _write_active_scene_contract(path: Path, contract: dict[str, object],
                                 run_directory: Path) -> bool:
    if (path != PHASE06_CONTRACT_PATH or path.is_symlink() or
            not ignored(path) or not private_active_capture_directory_is_safe(
                run_directory)):
        return False
    payload = (json.dumps(contract, sort_keys=True, separators=(",", ":")) +
               "\n").encode("utf-8")
    if len(payload) > QUALIFICATION_REPORT_MAX_BYTES:
        return False
    if path.exists():
        try:
            (run_directory / "previous-contract.json").write_bytes(path.read_bytes())
        except OSError:
            return False
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=".phase06-contract-",
                suffix=".tmp", delete=False) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        return True
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        return False


def calibrate_active_scene(input_root: Path,
                           importer: str | Path | list[str] | None,
                           contract_path: Path, *,
                           frame_inputs: str | None = None,
                           capture_frames: list[int] | tuple[int, ...] | None = None,
                           sound_contract_path: Path | None = None
                           ) -> dict[str, object]:
    if sound_contract_path is not None:
        if (contract_path != PHASE06_CONTRACT_PATH or
                sound_contract_path != PHASE07_SOUND_CONTRACT_PATH or
                frame_inputs is not None or capture_frames is not None):
            return {"status": "active_sound_contract_path_rejected",
                    "private_identity_recorded": False}
        return run_active_scene(
            input_root, importer, contract_path,
            sound_contract_path=sound_contract_path, sound_calibrate=True)
    selected_captures = (PHASE06_CALIBRATION_FRAMES if capture_frames is None
                         else capture_frames)
    if (not _active_schedule_valid(MAX_ACTIVE_FRAMES, frame_inputs, None, None) or
            not _calibration_capture_frames_valid(selected_captures)):
        return {"status": "active_scene_schedule_rejected",
                "private_identity_recorded": False}
    if contract_path != PHASE06_CONTRACT_PATH:
        return {"status": "active_scene_contract_path_rejected",
                "private_identity_recorded": False}
    if (any(path.is_symlink() for path in (
            Path("local"), Path("local/qualification"), PHASE06_RUN_ROOT)) or
            not ignored(PHASE06_RUN_ROOT / ("run-" + "0" * 32))):
        return {"status": "private_capture_path_rejected",
                "private_identity_recorded": False}
    run_id = uuid.uuid4().hex
    run_directory = PHASE06_RUN_ROOT / f"run-{run_id}"
    try:
        run_directory.mkdir(parents=True, exist_ok=False)
    except OSError:
        return {"status": "private_capture_path_unavailable",
                "private_identity_recorded": False}
    if not private_active_capture_directory_is_safe(run_directory):
        return {"status": "private_capture_path_rejected",
                "private_identity_recorded": False}

    try:
        pairs = find_pairs(input_root) if input_root.is_dir() else []
    except OSError:
        pairs = []
    media_identity = ([_file_identity(path) for path in pairs[0]]
                      if len(pairs) == 1 else None)
    freshness_result = ensure_fresh_qualifier()
    freshness_status = str(freshness_result)
    if freshness_status != "fresh":
        status = ("qualifier_build_failed" if freshness_status == "build_failed"
                  else "qualifier_stale" if freshness_status == "stale"
                  else "importer_identity_rejected")
        return {"status": status, "private_identity_recorded": False}
    importer_identity = getattr(freshness_result, "importer_identity", None)
    qualifier_identity = getattr(freshness_result, "qualifier_identity", None)
    evaluator_identity = _production_evaluator_identity()
    if (not isinstance(importer_identity, dict) or
            not isinstance(qualifier_identity, dict) or
            importer_identity != _production_importer_identity() or
            qualifier_identity != _production_qualifier_identity() or
            not isinstance(evaluator_identity, dict)):
        return {"status": "importer_identity_rejected",
                "private_identity_recorded": False}
    configuration = {
        "input_root": input_root.as_posix(),
        "prelude": SCRIPTED_START_INPUT_SCRIPT,
        "active_frames": MAX_ACTIVE_FRAMES,
        "frame_inputs": frame_inputs if frame_inputs is not None else [],
        "capture_frames": list(selected_captures),
        "frame_cycles": 202752,
    }
    configuration_identity = hashlib.sha256(
        json.dumps(configuration, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")).hexdigest()
    started = time.monotonic()
    result = run_selected_qualification(
        input_root, importer, scripted_start=True,
        active_frames=MAX_ACTIVE_FRAMES, frame_inputs=frame_inputs,
        capture_frames=selected_captures,
        capture_directory=run_directory,
        expected_media_identity=media_identity,
        preserve_native_report=True)
    duration_seconds = time.monotonic() - started
    post_importer_identity = _production_importer_identity()
    post_qualifier_identity = _production_qualifier_identity()
    post_evaluator_identity = _production_evaluator_identity()
    try:
        media_pairs_after = find_pairs(input_root) if input_root.is_dir() else []
    except OSError:
        media_pairs_after = []
    media_identity_after = ([_file_identity(path) for path in media_pairs_after[0]]
                            if len(media_pairs_after) == 1 else None)
    media_identity_unchanged = (
        _media_identity_is_valid(media_identity) and
        media_identity_after == media_identity)
    identity_unchanged = (
        importer_identity is not None and qualifier_identity is not None and
        importer_identity == post_importer_identity and
        qualifier_identity == post_qualifier_identity and
        evaluator_identity == post_evaluator_identity)
    if not identity_unchanged:
        result = {**result, "status": "importer_identity_rejected"}

    captures = result.get("capture_frames", [])
    captured_images: list[dict[str, object]] = []
    if isinstance(captures, list):
        for frame in captures:
            image_path = private_active_capture_frame_path(run_directory, frame)
            if not private_active_capture_frame_is_valid(image_path):
                continue
            captured_images.append({
                "frame": frame,
                "file": image_path.name,
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            })
    native_report = result.get("native_report_local")
    native_samples = (native_report.get("sampled_inputs")
                      if isinstance(native_report, dict) else None)
    sampled_inputs = native_samples if isinstance(native_samples, list) else []
    expected_sampled_inputs = []
    if frame_inputs is not None:
        for event in frame_inputs.split(","):
            frame, mask = event.split(":0x", 1)
            expected_sampled_inputs.append({
                "frame": int(frame, 10), "mask": int(mask, 16),
            })
    expected_captures = list(selected_captures)
    media_identity_ready = (
        media_identity_unchanged and _media_identity_is_valid(media_identity))
    captured_frame_indices = [
        image.get("frame") for image in captured_images
        if isinstance(image, dict)
    ]
    sample_events_valid = (
        isinstance(native_samples, list) and
        len(native_samples) == len(expected_sampled_inputs) and
        all(isinstance(event, dict) and set(event) == {"frame", "mask"} and
            type(event.get("frame")) is int and type(event.get("mask")) is int
            for event in native_samples) and
        native_samples == expected_sampled_inputs)
    native_execution_complete = (
        isinstance(native_report, dict) and
        native_report.get("status") == "active_frames_completed" and
        native_report.get("guest_executed") is True and
        native_report.get("start_observed") is True and
        type(native_report.get("active_frames_requested")) is int and
        native_report.get("active_frames_requested") == MAX_ACTIVE_FRAMES and
        type(native_report.get("active_frames_completed")) is int and
        native_report.get("active_frames_completed") == MAX_ACTIVE_FRAMES and
        native_report.get("capture_frames_requested") == expected_captures and
        native_report.get("capture_frames") == expected_captures and
        sample_events_valid)
    wrapper_execution_complete = (
        result.get("status") == "active_frames_completed" and
        type(result.get("active_frames_requested")) is int and
        result.get("active_frames_requested") == MAX_ACTIVE_FRAMES and
        type(result.get("active_frames_completed")) is int and
        result.get("active_frames_completed") == MAX_ACTIVE_FRAMES and
        result.get("capture_frames_requested") == expected_captures and
        captures == expected_captures)
    calibration_ready = (
        identity_unchanged and media_identity_ready and
        wrapper_execution_complete and native_execution_complete and
        len(captured_images) == MAX_ACTIVE_CAPTURE_FRAMES and
        captured_frame_indices == expected_captures)
    private_report = {
        **result,
        "code_identity": {
            "importer": importer_identity,
            "qualifier": qualifier_identity,
        },
        "evaluator_identity": evaluator_identity,
        "media_identity": media_identity,
        "media_identity_after": media_identity_after,
        "media_identity_unchanged": media_identity_unchanged,
        "configuration_identity": configuration_identity,
        "host_duration_seconds": round(duration_seconds, 6),
        "capture_observations": captured_images,
    }
    report_path = run_directory / "report.json"
    if not write_report(report_path, private_report):
        return {"status": "active_scene_report_write_failed",
                "private_identity_recorded": False}

    frozen_payload: dict[str, object] = {
        "schema_version": 1,
        "mode": "calibrate",
        "code_identity": private_report["code_identity"],
        "evaluator_identity": evaluator_identity,
        "media_identity": media_identity,
        "configuration_identity": configuration_identity,
        "schedule": configuration,
        "t0_frame": None,
        "endpoint_frame": None,
        "checkpoints": captured_images,
        "regions": [],
        "predicates": [],
        "limits": {
            "active_frames_requested": MAX_ACTIVE_FRAMES,
            "active_frames_completed": result.get("active_frames_completed"),
            "capture_limit": MAX_ACTIVE_CAPTURE_FRAMES,
            "host_timeout_seconds": NATIVE_QUALIFICATION_TIMEOUT_SECONDS,
            "host_duration_seconds": round(duration_seconds, 6),
            "report_bytes_limit": QUALIFICATION_REPORT_MAX_BYTES,
        },
        "frozen": False,
        "sampled_inputs": sampled_inputs,
        "requested_frames": MAX_ACTIVE_FRAMES,
        "completed_frames": result.get("active_frames_completed"),
        "observations": {
            "status": result.get("status", "unknown"),
            "calibration_configuration_identity": configuration_identity,
            "capture_frames_requested": list(selected_captures),
            "capture_frames_completed": result.get("capture_frames", []),
            "images": captured_images,
        },
        "outcomes": {
            "calibration": "captures_ready" if calibration_ready else "incomplete",
            "semantic_t0": "unresolved",
        },
        "run_report": report_path.relative_to(Path("local/qualification")).as_posix(),
    }
    frozen_payload["contract_identity"] = hashlib.sha256(
        json.dumps(frozen_payload, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")).hexdigest()
    if not active_scene_contract_is_valid(frozen_payload) or not _write_active_scene_contract(
            contract_path, frozen_payload, run_directory):
        return {"status": "active_scene_contract_write_failed",
                "private_identity_recorded": False}
    return {
        "status": "active_scene_calibration_recorded",
        "private_identity_recorded": True,
        "active_frames_requested": MAX_ACTIVE_FRAMES,
        "active_frames_completed": result.get("active_frames_completed"),
        "capture_frames_completed": len(captured_images),
        "calibration_outcome": frozen_payload["outcomes"]["calibration"],
        "semantic_t0": "unresolved",
    }


def active_scene_contract_status(path: Path, *, require_frozen: bool) -> str:
    if path != PHASE06_CONTRACT_PATH:
        return "active_scene_contract_path_rejected"
    if (path.is_symlink() or not path.is_file() or not ignored(path) or
            any(parent.is_symlink() for parent in (
                Path("local"), Path("local/qualification")))):
        return "active_scene_contract_unavailable"
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "active_scene_contract_invalid"
    if not active_scene_contract_is_valid(contract):
        return "active_scene_contract_invalid"
    if require_frozen and contract.get("frozen") is not True:
        return "active_scene_contract_unfrozen"
    return "active_scene_contract_valid"


def validate_scene_contract(path: Path, input_root: Path = Path("local/roms"),
                            *, check_current_identity: bool = True) -> tuple[str, dict[str, object] | None]:
    status = active_scene_contract_status(path, require_frozen=True)
    if status != "active_scene_contract_valid":
        return status, None
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "active_scene_contract_invalid", None
    if not active_scene_native_contract_is_valid(contract):
        return "active_scene_contract_invalid", None
    if input_root != Path("local/roms") or not input_root.is_dir() or input_root.is_symlink():
        return "private_media_unavailable", None
    try:
        pairs = find_pairs(input_root)
    except OSError:
        return "private_media_unavailable", None
    if len(pairs) != 1:
        return ("private_media_unavailable" if not pairs else
                "ambiguous_private_media_inputs"), None
    current_media = [_file_identity(path) for path in pairs[0]]
    if current_media != contract["media_identity"]:
        return "active_scene_identity_rejected", None
    run_report = contract.get("run_report")
    if (not isinstance(run_report, str) or
            re.fullmatch(r"phase06/run-[0-9a-f]{32}/report\.json", run_report) is None):
        return "active_scene_contract_invalid", None
    calibration_report_path = Path("local/qualification") / run_report
    if (calibration_report_path.is_symlink() or not calibration_report_path.is_file() or
            not ignored(calibration_report_path)):
        return "active_scene_calibration_evidence_missing", None
    try:
        calibration_report = json.loads(calibration_report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "active_scene_calibration_evidence_invalid", None
    if not active_scene_calibration_evidence_is_valid(contract, calibration_report):
        return "active_scene_calibration_evidence_invalid", None
    images = contract["observations"]["images"]
    capture_dir = calibration_report_path.parent
    for image in images:
        capture = capture_dir / image["file"]
        if (not private_active_capture_frame_is_valid(capture) or
                _sha256_path(capture) != image["sha256"]):
            return "active_scene_calibration_evidence_invalid", None
    if check_current_identity:
        current_code = {"importer": _production_importer_identity(),
                        "qualifier": _production_qualifier_identity()}
        if (current_code != contract["code_identity"] or
                _production_evaluator_identity() != contract["evaluator_identity"]):
            return "active_scene_identity_rejected", None
    return "active_scene_contract_valid", contract


def active_scene_calibration_evidence_is_valid(contract: object,
                                               report: object) -> bool:
    if not isinstance(contract, dict) or not isinstance(report, dict):
        return False
    observations = contract.get("observations")
    if not isinstance(observations, dict):
        return False
    images = observations.get("images")
    native_report = report.get("native_report_local")
    requested_frames = contract.get("requested_frames")
    requested_captures = observations.get("capture_frames_requested")
    completed_captures = observations.get("capture_frames_completed")
    sampled_inputs = contract.get("sampled_inputs")
    image_frames = ([image.get("frame") for image in images]
                    if isinstance(images, list) and
                    all(isinstance(image, dict) for image in images) else None)
    return (
        report.get("status") == "active_frames_completed" and
        type(requested_frames) is int and requested_frames > 0 and
        type(report.get("active_frames_requested")) is int and
        report.get("active_frames_requested") == requested_frames and
        type(report.get("active_frames_completed")) is int and
        report.get("active_frames_completed") == requested_frames and
        report.get("capture_frames_requested") == requested_captures and
        report.get("capture_frames") == completed_captures and
        isinstance(native_report, dict) and
        native_report.get("status") == "active_frames_completed" and
        native_report.get("guest_executed") is True and
        native_report.get("start_observed") is True and
        type(native_report.get("active_frames_requested")) is int and
        native_report.get("active_frames_requested") == requested_frames and
        type(native_report.get("active_frames_completed")) is int and
        native_report.get("active_frames_completed") == requested_frames and
        native_report.get("capture_frames_requested") == requested_captures and
        native_report.get("capture_frames") == completed_captures and
        native_report.get("sampled_inputs") == sampled_inputs and
        report.get("code_identity") == contract.get("code_identity") and
        report.get("evaluator_identity") == contract.get("evaluator_identity") and
        report.get("media_identity") == contract.get("media_identity") and
        report.get("media_identity_after") == contract.get("media_identity") and
        report.get("media_identity_unchanged") is True and
        report.get("configuration_identity") ==
        observations.get("calibration_configuration_identity") and
        isinstance(images, list) and len(images) == MAX_ACTIVE_CAPTURE_FRAMES and
        requested_captures == completed_captures == image_frames and
        images == contract.get("checkpoints") and
        report.get("capture_observations") == images
    )


def _load_private_capture_rgb(path: Path) -> bytes | None:
    if not private_active_capture_frame_is_valid(path):
        return None
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    if len(payload) != 15 + 320 * 224 * 3 or payload[:15] != b"P6\n320 224\n255\n":
        return None
    return payload[15:]


def _create_active_scene_run_directory(
        run_root: Path = PHASE06_RUN_ROOT) -> Path | None:
    for _ in range(3):
        run_directory = run_root / f"run-{uuid.uuid4().hex}"
        try:
            run_directory.mkdir(parents=True, exist_ok=False)
        except OSError:
            continue
        if private_active_capture_directory_is_safe(run_directory):
            return run_directory
    return None


def _phase07_recordings_from_invocations(
        invocations: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    recordings: dict[str, dict[str, object]] = {}
    for invocation in invocations:
        role = invocation.get("role")
        if invocation.get("pair") != "fire" or role not in ("action", "control"):
            continue
        relative_directory = invocation.get("run_directory")
        native = invocation.get("native_report_local")
        windows = native.get("sound_windows") if isinstance(native, dict) else None
        if (not isinstance(relative_directory, str) or
                re.fullmatch(r"phase07/run-[0-9a-f]{32}", relative_directory) is None or
                not isinstance(windows, list)):
            continue
        directory = Path("local/qualification") / relative_directory
        role_record: dict[str, object] = {"windows": {}}
        for window in windows:
            if not isinstance(window, dict) or window.get("name") not in SOUND_WINDOW_NAMES:
                continue
            name = str(window["name"])
            pcm_path = directory / f"sound-{name}.s16le"
            if not private_active_sound_path_is_valid(pcm_path):
                continue
            expected_bytes = window.get("pcm_bytes")
            if (type(expected_bytes) is not int or not 0 < expected_bytes <= SOUND_PCM_MAX_WINDOW_BYTES or
                    expected_bytes % SOUND_PCM_BYTES_PER_FRAME):
                continue
            try:
                if pcm_path.stat().st_size != expected_bytes:
                    continue
                with pcm_path.open("rb") as stream:
                    pcm = stream.read(expected_bytes + 1)
                if len(pcm) != expected_bytes:
                    continue
            except OSError:
                continue
            valid, features = _sound_window_observation_is_valid(
                window, {"name": name,
                         "first_frame": window.get("first_frame"),
                         "last_frame": window.get("last_frame")}, pcm,
                require_nonsilent=False, require_diagnostics=True)
            if not valid or features is None:
                continue
            role_record["windows"][name] = {
                "first_frame": window["first_frame"],
                "last_frame": window["last_frame"],
                "file": (directory / pcm_path.name).relative_to(
                    Path("local/qualification")).as_posix(),
                "sha256": hashlib.sha256(pcm).hexdigest(),
                "bytes": len(pcm),
                "features": features,
                "frame_observations": window["frame_observations"],
                "chip_frames": window.get("chip_frames"),
                "chip_observation": window.get("chip_observation"),
                "board_observations": window.get("board_observations"),
            }
        role_record["status"] = "windows_ready" if role_record["windows"] else "incomplete"
        recordings[str(role)] = role_record
    return recordings


def _phase07_family_classification(
        recordings: dict[str, dict[str, object]]) -> dict[str, str]:
    observations: list[dict[str, object]] = []
    sound_cpu_progress: list[bool] = []
    for recording in recordings.values():
        windows = recording.get("windows")
        if not isinstance(windows, dict):
            continue
        for window in windows.values():
            chip = window.get("chip_observation") if isinstance(window, dict) else None
            if isinstance(chip, dict):
                observations.append(chip)
            board = window.get("board_observations") if isinstance(window, dict) else None
            if isinstance(board, list) and len(board) >= 2:
                progress = any(
                    isinstance(previous, dict) and isinstance(current, dict) and
                    type(previous.get("sound_cpu_cycles")) is int and
                    type(current.get("sound_cpu_cycles")) is int and
                    current.get("sound_cpu_reset") is False and
                    current["sound_cpu_cycles"] > previous["sound_cpu_cycles"]
                    for previous, current in zip(board, board[1:]))
                sound_cpu_progress.append(progress)

    def classify(*, writes: str, output: str, key_on: str | None = None,
                 reads: str | None = None) -> str:
        family_observations = [item for item in observations
                               if item.get(writes, 0) > 0]
        if not family_observations:
            if reads is not None and any(item.get(reads, 0) > 0
                                         for item in observations):
                return "decoder_activity_without_register_observation"
            return "unknown"
        if reads is not None:
            sample_reads = any(item.get(reads, 0) > 0
                               for item in family_observations)
            if not sample_reads:
                return "register_activity_without_sample_reads"
            if any(item.get(output, 0) > 0 for item in family_observations):
                return "decoder_activity_output_unattributed"
            return "decoder_activity_without_native_output"
        if any(item.get(output, 0) > 0 for item in family_observations):
            return "native_output_observed"
        if key_on is not None and not any(
                item.get(key_on, 0) > 0 for item in family_observations):
            return "register_activity_without_key_on"
        return "activity_observed_without_native_output"

    return {
        "status": "classified_local_diagnostics" if observations else "unknown",
        "ssg": classify(writes="ssg_register_writes",
                        output="native_ssg_nonzero_frames"),
        "fm": classify(writes="fm_register_writes",
                       output="native_stereo_nonzero_frames",
                       key_on="fm_key_on_writes"),
        "adpcm_a": classify(writes="adpcm_a_register_writes",
                             output="native_stereo_nonzero_frames",
                             reads="adpcm_a_reads"),
        "adpcm_b": classify(writes="adpcm_b_register_writes",
                             output="native_stereo_nonzero_frames",
                             reads="adpcm_b_reads"),
        "sound_cpu_execution": (
            "cycles_advanced" if any(sound_cpu_progress) else
            "no_cycle_progress" if sound_cpu_progress else "unknown"),
    }


def _phase07_recording_pcm(recording: object, window_name: str) -> bytes | None:
    if not isinstance(recording, dict) or not isinstance(recording.get("windows"), dict):
        return None
    window = recording["windows"].get(window_name)
    relative_file = window.get("file") if isinstance(window, dict) else None
    if (not isinstance(relative_file, str) or
            re.fullmatch(r"phase07/run-[0-9a-f]{32}/sound-(music|fire|control|release)\.s16le",
                         relative_file) is None):
        return None
    path = Path("local/qualification") / relative_file
    if not private_active_sound_path_is_valid(path):
        return None
    expected = window.get("bytes")
    if type(expected) is not int or not 0 < expected <= SOUND_PCM_MAX_WINDOW_BYTES or expected % 4:
        return None
    try:
        if path.stat().st_size != expected:
            return None
        with path.open("rb") as stream:
            pcm = stream.read(expected + 1)
    except OSError:
        return None
    if len(pcm) != expected or hashlib.sha256(pcm).hexdigest() != window.get("sha256"):
        return None
    return pcm


def _phase07_window_causal_frames(
        recording: object, window_name: str, expected_mask: int
        ) -> list[dict[str, object]] | None:
    if not isinstance(recording, dict) or not isinstance(recording.get("windows"), dict):
        return None
    window = recording["windows"].get(window_name)
    if not isinstance(window, dict):
        return None
    first = window.get("first_frame")
    last = window.get("last_frame")
    frame_rows = window.get("frame_observations")
    chip_rows = window.get("chip_frames")
    pcm = _phase07_recording_pcm(recording, window_name)
    if (type(first) is not int or type(last) is not int or last < first or
            not isinstance(frame_rows, list) or not isinstance(chip_rows, list) or
            len(frame_rows) != last - first + 1 or
            len(chip_rows) != len(frame_rows) or pcm is None):
        return None
    chip_keys = {"frame", "chip_reset", *SOUND_CHIP_FRAME_COUNTERS}
    output: list[dict[str, object]] = []
    pcm_offset = 0
    for offset, (frame, chip) in enumerate(zip(frame_rows, chip_rows)):
        frame_id = first + offset
        if (not isinstance(frame, dict) or set(frame) != {
                "frame", "input_mask", "elapsed_cycles", "audio_frames"} or
                frame.get("frame") != frame_id or
                type(frame.get("input_mask")) is not int or
                frame["input_mask"] != expected_mask or
                not _phase07_elapsed_frame_clocks_are_valid(
                    frame.get("elapsed_cycles")) or
                type(frame.get("audio_frames")) is not int or
                not 0 < frame["audio_frames"] <= 812 or
                not isinstance(chip, dict) or set(chip) != chip_keys or
                chip.get("frame") != frame_id or
                type(chip.get("chip_reset")) is not bool or chip["chip_reset"] or
                any(type(chip.get(counter)) is not int or chip[counter] < 0
                    for counter in SOUND_CHIP_FRAME_COUNTERS)):
            return None
        byte_count = frame["audio_frames"] * SOUND_PCM_BYTES_PER_FRAME
        block = pcm[pcm_offset:pcm_offset + byte_count]
        if len(block) != byte_count:
            return None
        sample_count = len(block) // 2
        try:
            samples = struct.unpack("<" + "h" * sample_count, block)
        except struct.error:
            return None
        output.append({**frame, "chip": chip, "pcm": block,
                       "samples": samples})
        pcm_offset += byte_count
    return output if pcm_offset == len(pcm) else None


def _phase07_family_output_on_frame(row: dict[str, object]) -> bool:
    chip = row.get("chip")
    samples = row.get("samples")
    if not isinstance(chip, dict) or not isinstance(samples, tuple):
        return False
    family_activity = (
        chip.get("fm_key_on_writes", 0) > 0 or
        chip.get("ssg_volume_writes", 0) > 0 or
        (chip.get("adpcm_a_control_writes", 0) > 0 and
         chip.get("adpcm_a_reads", 0) > 0) or
        (chip.get("adpcm_b_control_writes", 0) > 0 and
         chip.get("adpcm_b_reads", 0) > 0))
    return (family_activity and chip.get("native_nonzero_frames", 0) > 0 and
            any(sample != 0 for sample in samples))


def _phase07_aligned_windows(
        left: list[dict[str, object]] | None,
        right: list[dict[str, object]] | None,
        *, clock_divergence_limit: int = PHASE07_MAX_EVENT_EXCESS_CYCLES
        ) -> bool:
    if (left is None or right is None or not left or
            len(left) != len(right) or
            type(clock_divergence_limit) is not int or
            clock_divergence_limit < 0):
        return False
    # Calls close on the same logical guest frame but can execute different
    # instruction tails. Compare cumulative audio positions at every frame
    # boundary and retain actual cumulative clocks with the proven carry bound;
    # exact independent cycle equality would reject valid instruction overshoot.
    left_samples = right_samples = 0
    left_cycles = right_cycles = 0
    for a, b in zip(left, right):
        if (not isinstance(a, dict) or not isinstance(b, dict) or
                type(a.get("frame")) is not int or
                type(b.get("frame")) is not int or
                a.get("frame") != b.get("frame") or
                type(a.get("audio_frames")) is not int or
                type(b.get("audio_frames")) is not int or
                a["audio_frames"] <= 0 or b["audio_frames"] <= 0 or
                not _phase07_elapsed_frame_clocks_are_valid(
                    a.get("elapsed_cycles")) or
                not _phase07_elapsed_frame_clocks_are_valid(
                    b.get("elapsed_cycles"))):
            return False
        left_samples += a["audio_frames"]
        right_samples += b["audio_frames"]
        left_cycles += a["elapsed_cycles"]
        right_cycles += b["elapsed_cycles"]
        if (left_samples != right_samples or
                abs(left_cycles - right_cycles) > clock_divergence_limit):
            return False
    return True


def _phase07_calibration_outcomes(
        recordings: dict[str, dict[str, object]],
        visual_predicates: dict[str, str] | None = None,
        thresholds: dict[str, object] | None = None) -> dict[str, str]:
    criteria = PHASE07_SOUND_THRESHOLDS if thresholds is None else thresholds
    outcomes = {"music": "unknown", "fire": "unknown",
                "release": "unknown", "overall": "unknown"}
    if criteria != PHASE07_SOUND_THRESHOLDS:
        return outcomes
    action = recordings.get("action")
    control = recordings.get("control")
    action_music = _phase07_window_causal_frames(action, "music", 0)
    control_music = _phase07_window_causal_frames(control, "music", 0)
    if (_phase07_aligned_windows(action_music, control_music) and
            all(a["input_mask"] == b["input_mask"] == 0
                for a, b in zip(action_music, control_music)) and
            b"".join(row["pcm"] for row in action_music) ==
            b"".join(row["pcm"] for row in control_music)):
        samples = [sample for row in action_music for sample in row["samples"]]
        if (sum(sample != 0 for sample in samples) >=
                criteria["music"]["minimum_nonzero_int16_samples"] and
                any(_phase07_family_output_on_frame(row)
                    for row in action_music)):
            outcomes["music"] = "pass"

    action_fire = _phase07_window_causal_frames(action, "fire", 0x40)
    control_effect = _phase07_window_causal_frames(control, "control", 0)
    visual_ok = (isinstance(visual_predicates, dict) and
                 visual_predicates.get("overall") == "pass")
    if (visual_ok and outcomes["music"] == "pass" and
            _phase07_aligned_windows(action_fire, control_effect)):
        fire_supported = False
        for action_frame, control_frame in zip(action_fire, control_effect):
            action_samples = action_frame["samples"]
            control_samples = control_frame["samples"]
            if (len(action_samples) != len(control_samples) or
                    action_frame["input_mask"] != 0x40 or
                    control_frame["input_mask"] != 0):
                break
            changed = sum(a != b for a, b in zip(action_samples, control_samples))
            if (changed >= criteria["fire"][
                    "minimum_changed_int16_samples_in_one_frame"] and
                    _phase07_family_output_on_frame(action_frame)):
                fire_supported = True
                break
        if fire_supported:
            outcomes["fire"] = "pass"

    action_release = _phase07_window_causal_frames(action, "release", 0)
    control_release = _phase07_window_causal_frames(control, "release", 0)
    if (outcomes["fire"] == "pass" and
            _phase07_aligned_windows(
                action_release, control_release,
                clock_divergence_limit=2 * PHASE07_MAX_EVENT_EXCESS_CYCLES) and
            len(action_release) >= criteria["release"]["trailing_equal_pcm_frames"] and
            all(row["input_mask"] == 0 for row in action_release + control_release)):
        stop_event = any(
            row["chip"].get("fm_key_off_writes", 0) > 0 or
            row["chip"].get("adpcm_a_control_writes", 0) > 0 or
            row["chip"].get("adpcm_b_control_writes", 0) > 0
            for row in action_release)
        converged = all(
            a["pcm"] == b["pcm"] for a, b in zip(
                action_release[-criteria["release"]["trailing_equal_pcm_frames"]:],
                control_release[-criteria["release"]["trailing_equal_pcm_frames"]:]))
        if stop_event or converged:
            outcomes["release"] = "pass"

    if all(outcomes[name] == "pass" for name in ("music", "fire", "release")):
        outcomes["overall"] = "pass"
    return outcomes


def run_active_scene(input_root: Path, importer: str | Path | list[str] | None,
                     contract_path: Path, *,
                     sound_contract_path: Path | None = None,
                     sound_calibrate: bool = False) -> dict[str, object]:
    sound_mode = sound_contract_path is not None
    status, contract = validate_scene_contract(
        contract_path, input_root, check_current_identity=not sound_mode)
    if status != "active_scene_contract_valid" or contract is None:
        return {"status": status, "private_identity_recorded": False,
                "predicates": {"overall": "unknown"}}
    code_identity = {"importer": _production_importer_identity(),
                     "qualifier": _production_qualifier_identity()}
    evaluator_identity = _production_evaluator_identity()
    sound_contract: dict[str, object] | None = None
    sound_contract_digest_before: str | None = None
    scene_contract_digest_before: str | None = None
    if sound_mode:
        freshness = ensure_fresh_qualifier()
        if str(freshness) != "fresh":
            return {"status": "qualifier_stale", "private_identity_recorded": False,
                    "predicate_results": {"overall": "unknown"},
                    "sound_outcomes": {"overall": "unknown"}}
        code_identity = {
            "importer": getattr(freshness, "importer_identity", None),
            "qualifier": getattr(freshness, "qualifier_identity", None),
        }
        if (not all(isinstance(value, dict) for value in code_identity.values()) or
                code_identity["importer"] != _production_importer_identity() or
                code_identity["qualifier"] != _production_qualifier_identity() or
                not isinstance(evaluator_identity, dict)):
            return {"status": "importer_identity_rejected",
                    "private_identity_recorded": False,
                    "predicate_results": {"overall": "unknown"},
                    "sound_outcomes": {"overall": "unknown"}}
        if not sound_calibrate:
            try:
                sound_contract_digest_before = _sha256_path(sound_contract_path)
                scene_contract_digest_before = _sha256_path(contract_path)
            except OSError:
                sound_contract_digest_before = None
                scene_contract_digest_before = None
            sound_contract = _read_phase07_sound_contract(
                sound_contract_path, require_frozen=True)
            expected_scene_digest = _sha256_path(contract_path)
            if (sound_contract is None or sound_contract_digest_before is None or
                    scene_contract_digest_before is None or
                    not _phase07_sound_contract_matches_current(
                        sound_contract,
                        phase06_identity=contract["contract_identity"],
                        phase06_digest=expected_scene_digest,
                        schedule=contract["schedule"],
                        code_identity=code_identity,
                        evaluator_identity=evaluator_identity,
                        media_identity=contract["media_identity"])):
                return {"status": "active_sound_contract_stale",
                        "private_identity_recorded": False,
                        "predicate_results": {"overall": "unknown"},
                        "sound_outcomes": {"overall": "unknown"}}
    schedule = contract["schedule"]
    runs: dict[str, dict[str, object]] = {}
    invocation_records: list[dict[str, object]] = []
    identity_ok = True
    parsed = _active_scene_schedule_masks(schedule)
    if parsed is None:
        return {"status": "active_scene_contract_invalid",
                "private_identity_recorded": False,
                "predicates": {"overall": "unknown"}}
    for pair_name, pair in schedule["pairs"].items():
        runs[pair_name] = {}
        for role in ("action", "control"):
            run_root = PHASE07_RUN_ROOT if sound_mode else PHASE06_RUN_ROOT
            run_directory = _create_active_scene_run_directory(run_root)
            if run_directory is None:
                invocation_records.append({"pair": pair_name, "role": role,
                                           "status": "private_capture_path_unavailable"})
                identity_ok = False
                continue
            combined_inputs = _active_scene_input_events(schedule, pair_name, role)
            if combined_inputs is None:
                invocation_records.append({"pair": pair_name, "role": role,
                                           "status": "active_scene_contract_invalid"})
                identity_ok = False
                continue
            expected_inputs = [{"frame": frame, "mask": mask}
                               for frame, mask in combined_inputs]
            frame_inputs = ",".join(f"{frame}:0x{mask:x}"
                                     for frame, mask in combined_inputs)
            sound_windows = (_phase07_sound_windows(schedule, role)
                             if sound_mode and pair_name == "fire" else None)
            if sound_mode and pair_name == "fire" and sound_windows is None:
                invocation_records.append({"pair": pair_name, "role": role,
                                           "status": "active_sound_schedule_invalid"})
                identity_ok = False
                continue
            started = time.monotonic()
            result = run_selected_qualification(
                input_root, importer, scripted_start=True,
                active_frames=schedule["active_frames"],
                frame_inputs=frame_inputs,
                capture_frames=pair["capture_frames"],
                capture_directory=run_directory,
                sound_windows=sound_windows,
                expected_media_identity=contract["media_identity"],
                preserve_native_report=True)
            native = result.get("native_report_local")
            captures = result.get("capture_frames")
            sample_ok = isinstance(native, dict) and native.get("sampled_inputs") == expected_inputs
            capture_ok = ((result.get("status") == "active_frames_completed" or
                           (sound_windows is not None and
                            result.get("status") == "native_sound_capture_invalid")) and
                          result.get("active_frames_completed") == schedule["active_frames"] and
                          result.get("capture_frames_requested") == pair["capture_frames"] and
                          captures == pair["capture_frames"])
            images: list[bytes] = []
            capture_observations: list[dict[str, object]] = []
            if capture_ok:
                for frame in pair["capture_frames"]:
                    capture_path = private_active_capture_frame_path(run_directory, frame)
                    rgb = _load_private_capture_rgb(capture_path)
                    if rgb is None:
                        capture_ok = False
                        break
                    images.append(rgb)
                    capture_observations.append({
                        "frame": frame, "file": capture_path.name,
                        "sha256": _sha256_path(capture_path),
                    })
            if sample_ok and capture_ok:
                runs[pair_name][role] = images
            else:
                identity_ok = identity_ok and result.get("status") != "importer_identity_rejected"
            invocation = {
                "pair": pair_name, "role": role,
                "status": (result.get("status") if sample_ok and capture_ok else
                           "active_scene_input_or_capture_rejected"),
                "active_frames_requested": schedule["active_frames"],
                "active_frames_completed": result.get("active_frames_completed"),
                "sampled_inputs": native.get("sampled_inputs") if isinstance(native, dict) else None,
                "capture_frames_requested": pair["capture_frames"],
                "capture_frames_completed": captures,
                "capture_observations": capture_observations,
                "host_duration_seconds": round(time.monotonic() - started, 6),
                "run_directory": run_directory.relative_to(
                    Path("local/qualification")).as_posix(),
                "sound_features_local": result.get("sound_features_local"),
                "native_report_local": native,
                "native_stderr_local": result.get("native_stderr_local"),
            }
            if not write_report(run_directory / "active-scene-report.json", invocation):
                identity_ok = False
                invocation["status"] = "active_scene_report_write_failed"
            invocation_records.append(invocation)
            current_code = {"importer": _production_importer_identity(),
                            "qualifier": _production_qualifier_identity()}
            try:
                media_after = find_pairs(input_root)
            except OSError:
                media_after = []
            current_media = ([_file_identity(path) for path in media_after[0]]
                             if len(media_after) == 1 else None)
            expected_code = code_identity if sound_mode else contract["code_identity"]
            expected_evaluator = evaluator_identity if sound_mode else contract["evaluator_identity"]
            if (current_code != expected_code or
                    _production_evaluator_identity() != expected_evaluator or
                    current_media != contract["media_identity"]):
                identity_ok = False
                break
            if sound_mode and not sound_calibrate:
                unchanged_sound_contract = _phase07_contract_files_unchanged(
                    contract_path, scene_contract_digest_before,
                    sound_contract_path, sound_contract_digest_before)
                if not unchanged_sound_contract:
                    identity_ok = False
                    break
        if not identity_ok:
            break
    if sound_mode and not sound_calibrate:
        identity_ok = (identity_ok and _phase07_contract_files_unchanged(
            contract_path, scene_contract_digest_before,
            sound_contract_path, sound_contract_digest_before))
    if "right" in runs and "control" in runs["right"]:
        neutral = runs["right"]["control"]
        runs["scene"] = {"status": "complete", "t0": neutral[0],
                          "endpoint": neutral[-1]}
    outcomes = evaluate_active_scene_pairs(contract, runs)
    if not identity_ok:
        outcomes = {key: ("fail" if key == "overall" else "unknown")
                    for key in outcomes}
    recordings = (_phase07_recordings_from_invocations(invocation_records)
                  if sound_mode else {})
    sound_outcomes = (_phase07_calibration_outcomes(
        recordings, outcomes,
        sound_contract.get("thresholds") if sound_contract is not None else None)
        if sound_mode else None)
    if sound_mode and not identity_ok:
        sound_outcomes = {key: "unknown" for key in
                          ("music", "fire", "release", "overall")}
    report_directory = _create_active_scene_run_directory(
        PHASE07_RUN_ROOT if sound_mode else PHASE06_RUN_ROOT)
    report_written = False
    if report_directory is not None:
        report_written = write_report(report_directory / "active-scene-report.json", {
            "status": ("active_scene_sound_candidate_recorded"
                       if sound_mode and sound_calibrate else
                       "active_scene_visual_predicates_recorded"
                       if outcomes["overall"] == "pass" else
                       "active_scene_native_incomplete"),
            "code_identity": code_identity if sound_mode else contract["code_identity"],
            "evaluator_identity": evaluator_identity if sound_mode else contract["evaluator_identity"],
            "media_identity": contract["media_identity"],
            "configuration_identity": contract["configuration_identity"],
            "contract_identity": contract["contract_identity"],
            "predicates": outcomes,
            "sound_outcomes": sound_outcomes,
            "invocations": invocation_records,
        })
    status = ("active_scene_native_recorded" if outcomes["overall"] == "pass" and
              identity_ok and report_written else "active_scene_native_failed")
    if sound_mode:
        if report_directory is not None and sound_outcomes is not None:
            sound_result_written = write_report(
                report_directory / "sound-causal-report.json", {
                    "status": "sound_causal_outcomes_recorded",
                    "visual_predicates": outcomes,
                    "sound_outcomes": sound_outcomes,
                    "sound_contract_identity": (
                        sound_contract.get("contract_identity")
                        if sound_contract is not None else None),
                    "sound_contract_digest_unchanged": (
                        identity_ok if not sound_calibrate else None),
                    "recordings": recordings,
                })
        else:
            sound_result_written = False
        sound_windows_ready = (
            isinstance(recordings.get("action"), dict) and
            isinstance(recordings.get("control"), dict) and
            set(recordings["action"].get("windows", {})) >=
                {"music", "fire", "release"} and
            set(recordings["control"].get("windows", {})) >=
                {"music", "control", "release"})
        if sound_calibrate:
            expected_schedule_identity = hashlib.sha256(
                json.dumps({"phase06_contract_identity": contract["contract_identity"],
                            "schedule": schedule}, sort_keys=True,
                           separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            ).hexdigest()
            sound_contract = {
                "schema_version": 1,
                "mode": "calibrate",
                "phase06_contract_sha256": _sha256_path(contract_path),
                "phase06_contract_identity": contract["contract_identity"],
                "code_identity": code_identity,
                "evaluator_identity": evaluator_identity,
                "media_identity": contract["media_identity"],
                "schedule_identity": expected_schedule_identity,
                "schedule": schedule,
                "recordings": recordings,
                "families": _phase07_family_classification(recordings),
                "thresholds": {},
                "criteria_identity": None,
                "calibration_identity": None,
                "outcomes": {
                    **sound_outcomes,
                    "calibration": "windows_ready" if sound_windows_ready else "incomplete",
                    "visual_predicates": outcomes,
                },
                "frozen": False,
                "run_report": (report_directory / "active-scene-report.json").relative_to(
                    Path("local/qualification")).as_posix(),
            }
            contract_written = (
                report_written and identity_ok and
                _write_phase07_sound_contract(
                    sound_contract_path, sound_contract, report_directory))
            return {
                "status": ("active_scene_sound_calibration_recorded"
                           if contract_written else "active_scene_sound_calibration_failed"),
                "private_identity_recorded": contract_written,
                "calibration_outcome": ("windows_ready" if sound_windows_ready and
                                         outcomes["overall"] == "pass" else "incomplete"),
                "predicate_results": outcomes,
                "sound_outcomes": sound_outcomes,
            }
        native_sound_pass = (isinstance(sound_outcomes, dict) and
                             sound_outcomes.get("overall") == "pass")
        return {
            "status": ("active_scene_native_recorded"
                       if outcomes["overall"] == "pass" and identity_ok and
                       report_written and sound_result_written and native_sound_pass
                       else "active_scene_native_failed"),
            "private_identity_recorded": report_written and identity_ok,
            "predicate_results": outcomes,
            "sound_outcomes": sound_outcomes,
        }
    return {"status": status,
            "private_identity_recorded": report_written and identity_ok,
            "predicate_results": outcomes}
def active_scene_frontend_capture_is_valid(
        capture: object, observations: object, *, invocation_id: str,
        expected_mask: int, origin: int, target_frame: int) -> bool:
    """Reconstruct the conservative interval from the actual complete log chain."""
    if (not isinstance(capture, dict) or not isinstance(observations, list) or
            capture.get("invocation_id") != invocation_id or
            type(capture.get("target_frame")) is not int or
            capture.get("target_frame") != target_frame or
            type(origin) is not int or origin < 0 or
            type(target_frame) is not int or not 0 <= target_frame < MAX_ACTIVE_FRAMES or
            capture.get("exact_frame") != "unknown" or
            type(capture.get("sampled_mask")) is not int or
            capture.get("sampled_mask") != expected_mask):
        return False
    interval = capture.get("successful_video_interval")
    if (not isinstance(interval, list) or len(interval) != 2 or
            any(type(value) is not int for value in interval) or
            not origin + target_frame <= interval[0] < interval[1] or
            interval[1] - (origin + target_frame) > 64):
        return False
    try:
        smoke = _load_retroarch_smoke()
        smoke._validated_observation_records(observations, invocation_id)
        indices = [next(index for index, record in enumerate(observations)
                        if record.get("event_kind") == "V" and
                        record.get("successful_video_sequence") == endpoint)
                   for endpoint in interval]
        binding = smoke.bind_active_scene_capture(
            observations[:indices[0] + 1], observations[:indices[1] + 1],
            invocation_id=invocation_id, expected_mask=expected_mask,
            capture_sha256=capture.get("sha256"))
        return binding.get("successful_video_interval") == interval
    except (ValueError, StopIteration, TypeError, AttributeError, RuntimeError):
        return False


def _frontend_configuration_identity(text: object, *, work_directory: Path | None = None,
                                     capture_directory: Path | None = None) -> str | None:
    """Bind settings while canonicalizing only host-owned temporary destinations."""
    if not isinstance(text, str) or len(text.encode("utf-8")) > 12 * 1024:
        return None
    if (not isinstance(work_directory, Path) or not work_directory.is_absolute()
            or not isinstance(capture_directory, Path) or not capture_directory.is_absolute()
            or not _load_retroarch_smoke().validate_active_config_destinations(
                text, work_directory, capture_directory)):
        return None
    destinations = {"content_history_path", "savefile_directory", "savestate_directory",
                    "system_directory", "cache_directory", "screenshot_directory", "log_dir",
                    "playlist_directory", "content_history_directory", "content_favorites_directory",
                    "content_image_history_directory", "content_music_history_directory",
                    "content_video_directory"}
    lines = []
    for line in text.splitlines():
        key = line.partition("=")[0].strip()
        lines.append(f'{key} = "<private-destination>"' if key in destinations else line)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _active_frontend_events_valid(actual, events, invocation_id) -> bool:
    if not isinstance(actual, dict):
        return False
    observations = actual.get("observations")
    observed = actual.get("observed_events")
    origin = actual.get("active_origin_video_sequence")
    if (type(origin) is not int or origin < 1 or not isinstance(observations, list) or
            not isinstance(observed, list) or len(observed) != len(events)):
        return False
    try:
        _load_retroarch_smoke()._validated_observation_records(observations, invocation_id)
        starts = [record for record in observations if record["event_kind"] == "P"]
        videos = [record for record in observations if record["event_kind"] == "V"]
        expected_samples = [0, 1, 0, 2, 0]
        for _target, mask in events:
            if mask != expected_samples[-1]:
                expected_samples.append(mask)
        if [record["sampled_mask"] for record in observations
                if record["event_kind"] == "S"] != expected_samples:
            return False
        if (len(starts) != 1 or starts[0]["sampled_mask"] != 2 or
                not any(record["event_kind"] == "S" and record["sampled_mask"] == 2 and
                        record["sample_sequence"] <= starts[0]["sample_sequence"]
                        for record in observations) or
                starts[0]["successful_video_sequence"] >= origin or
                not any(record["successful_video_sequence"] == origin and
                        record["sampled_mask"] == 0 for record in videos)):
            return False
        previous = origin
        for (target, mask), event in zip(events, observed):
            if (not isinstance(event, dict) or type(event.get("target_frame")) is not int or
                    event.get("target_frame") != target or type(event.get("mask")) is not int or
                    event.get("mask") != mask or
                    type(event.get("successful_video_sequence")) is not int or
                    type(event.get("sample_sequence")) is not int):
                return False
            video = event["successful_video_sequence"]
            if (not max(previous + 1, origin + target) <= video <= origin + target + 64 or
                    not any(record["successful_video_sequence"] == video and
                            record["sample_sequence"] == event["sample_sequence"] and
                            record["sampled_mask"] == mask for record in videos)):
                return False
            previous = video
        return True
    except (KeyError, TypeError, RuntimeError):
        return False


def _active_frontend_sources(core: dict[str, object]) -> dict[str, object]:
    return {"core_sha256": core["sha256"],
            "evaluator": _production_evaluator_identity(),
            "collector_sha256": _sha256_path(PROJECT_ROOT / "tests/libretro/retroarch_smoke.py"),
            "replay_sha256": _sha256_path(PROJECT_ROOT / "tools/mvs/frontend_replay.py")}


def _active_frontend_identity_matches(historical_identity, current_identity,
                                      current_sources) -> bool:
    """Keep the accepted frontend fixed while binding Phase07 to its current core.

    The Phase06 identity is historical provenance. Its app/version/bundle remain
    pinned, while the core digest is checked against the source snapshot captured
    for this Phase07 run and rechecked after every acquisition.
    """
    if (not isinstance(historical_identity, dict) or
            not isinstance(current_identity, dict) or
            not isinstance(current_sources, dict)):
        return False
    historical_core = historical_identity.get("core_sha256")
    current_core = current_sources.get("core_sha256")
    actual_core = current_identity.get("core_sha256")
    if any(not isinstance(value, str) or
           re.fullmatch(r"[0-9a-f]{64}", value) is None
           for value in (historical_core, current_core, actual_core)):
        return False
    if actual_core != current_core:
        return False
    for key in ("retroarch_executable_sha256",):
        historical, current = historical_identity.get(key), current_identity.get(key)
        if (not isinstance(historical, str) or re.fullmatch(r"[0-9a-f]{64}", historical) is None or
                current != historical):
            return False
    for key in ("retroarch_version", "bundle_id"):
        historical, current = historical_identity.get(key), current_identity.get(key)
        if not isinstance(historical, str) or not historical or current != historical:
            return False
    return True


FRONTEND_COMPOSITION_POLICY = "sampled_input_rgb_replay_v1"


def _active_frontend_transfer_valid(invocation, sources, configuration_identity) -> bool:
    """Private receipt is correlated transfer evidence, never renderer truth."""
    if (not isinstance(invocation, dict) or not isinstance(sources, dict) or
            not isinstance(invocation.get("identity"), dict) or
            invocation["identity"].get("core_sha256") != sources.get("core_sha256") or
            not isinstance(invocation.get("selected_bundle_sha256"), str) or
            re.fullmatch(r"[0-9a-f]{64}", invocation["selected_bundle_sha256"]) is None):
        return False
    replay = _load_frontend_replay()
    return replay.validate_receipt(
        invocation.get("replay"), sources["core_sha256"],
        invocation["selected_bundle_sha256"], invocation, configuration_identity)


def _evaluate_active_frontend_pairs(contract, runs, invocations, sources,
                                    configuration_identity):
    # Preserve the native exact composition evaluator and every existing causal
    # predicate. Actual frontend composition now means full RGB transfer from at
    # least one admitted replay submission, with all matching sequences retained.
    outcomes = evaluate_active_scene_pairs(contract, runs, frontend_intervals=True)
    expected = {(pair, role) for pair in _ACTIVE_SCENE_PAIR_NAMES
                for role in ("action", "control")}
    complete = (isinstance(invocations, list) and len(invocations) == len(expected) and
                {(row.get("pair"), row.get("role")) for row in invocations
                 if isinstance(row, dict)} == expected and
                all(_active_frontend_transfer_valid(row, sources, configuration_identity)
                    for row in invocations))
    outcomes["composition"] = "pass" if complete else "fail"
    predicates = [value for key, value in outcomes.items() if key != "overall"]
    outcomes["overall"] = ("pass" if all(value == "pass" for value in predicates) else
                           "fail" if "fail" in predicates else "unknown")
    return outcomes


def _active_frontend_temporal_bounds_valid(schedule, invocations) -> bool:
    """Admit paired pixel comparisons only within overlapping bounded windows.

    Nominal indices label observations, never identify submitted frames. Each
    complete interval must be on the correct side of the actual observed action
    and release, and independently booted role intervals must overlap. These
    fixed bounds precede private calibration; failures remain unknown.
    """
    parsed = _active_scene_schedule_masks(schedule)
    if parsed is None or not isinstance(invocations, list) or len(invocations) != 10:
        return False
    by_pair = {}
    try:
        for invocation in invocations:
            pair, role = invocation["pair"], invocation["role"]
            key = pair, role
            if key in by_pair or pair not in parsed or role not in ("action", "control"):
                return False
            origin = invocation["active_origin_video_sequence"]
            events = invocation["observed_events"]
            start, release = parsed[pair][role][0][0], parsed[pair][role][-1][0]
            observed_start = next(event["successful_video_sequence"] - origin
                                  for event in events if event["target_frame"] == start)
            observed_release = next(event["successful_video_sequence"] - origin
                                    for event in events if event["target_frame"] == release)
            intervals = []
            for target, capture in zip(schedule["pairs"][pair]["capture_frames"], invocation["captures"]):
                lower, upper = (value - origin for value in capture["successful_video_interval"])
                if (not 0 <= lower < upper <= schedule["active_frames"] or upper - lower > 12 or
                        (target < start and upper >= observed_start) or
                        (start <= target < release and not observed_start <= lower < upper < observed_release) or
                        (target >= release and lower < observed_release)):
                    return False
                intervals.append((lower, upper))
            if len(intervals) != MAX_ACTIVE_CAPTURE_FRAMES or any(
                    previous[1] > current[0] for previous, current in zip(intervals, intervals[1:])):
                return False
            by_pair[key] = intervals
        for pair in parsed:
            for action, control in zip(by_pair[pair, "action"], by_pair[pair, "control"]):
                if (max(action[0], control[0]) >= min(action[1], control[1]) or
                        max(action[1], control[1]) - min(action[0], control[0]) > 16):
                    return False
        return True
    except (KeyError, TypeError, ValueError, StopIteration):
        return False


def _active_frontend_native_identity(contract) -> str:
    # Frontend calibration/freeze changes its own nested evidence. Everything
    # belonging to the native scene/threshold contract must remain identical.
    projection = {key: value for key, value in contract.items()
                  if key not in {"frontend", "contract_identity"}}
    return hashlib.sha256(json.dumps(projection, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _active_frontend_schedule_compatible(contract, schedule) -> bool:
    if (not isinstance(contract, dict) or not isinstance(contract.get("schedule"), dict) or
            type(contract.get("t0_frame")) is not int or type(contract.get("endpoint_frame")) is not int):
        return False
    native = contract["schedule"]
    before, after = _active_scene_schedule_masks(native), _active_scene_schedule_masks(schedule)
    if before is None or after is None or any(schedule[key] != native[key] for key in
                                               ("setup", "entry_inputs", "active_frames", "frame_cycles")):
        return False
    captures = schedule["pairs"]["right"]["capture_frames"]
    if (captures[0] != contract["t0_frame"] or captures[-1] > contract["endpoint_frame"] or
            any(value["capture_frames"] != captures for value in schedule["pairs"].values())):
        return False
    for pair in before:
        for role in ("action", "control"):
            old, new = before[pair][role], after[pair][role]
            if ([mask for _, mask in old] != [mask for _, mask in new] or
                    any(abs(old_frame - new_frame) > 64
                        for (old_frame, _), (new_frame, _) in zip(old, new)) or
                    abs((new[-1][0] - new[0][0]) - (old[-1][0] - old[0][0])) > 64 or
                    not captures[0] < new[0][0] < new[-1][0] <= captures[-1]):
                return False
        if ([frame for frame, _ in after[pair]["action"]] !=
                [frame for frame, _ in after[pair]["control"]]):
            return False
    return True


def _active_frontend_historical_transfer_valid(invocation, sources,
                                               configuration_identity) -> bool:
    """Check a saved transfer receipt without reinterpreting it with new code."""
    if (not isinstance(invocation, dict) or not isinstance(sources, dict) or
            not isinstance(invocation.get("identity"), dict) or
            invocation["identity"].get("core_sha256") != sources.get("core_sha256") or
            not isinstance(invocation.get("selected_bundle_sha256"), str) or
            re.fullmatch(r"[0-9a-f]{64}", invocation["selected_bundle_sha256"]) is None or
            not isinstance(configuration_identity, str) or not configuration_identity):
        return False
    receipt = invocation.get("replay")
    captures = invocation.get("captures")
    if (not isinstance(receipt, dict) or set(receipt) != {
            "policy", "binding", "core_sha256", "bundle_sha256", "captures", "status"} or
            receipt.get("policy") != "sampled_input_rgb_replay_v1" or
            receipt.get("status") != "pass" or
            receipt.get("core_sha256") != sources.get("core_sha256") or
            receipt.get("bundle_sha256") != invocation["selected_bundle_sha256"] or
            not isinstance(receipt.get("binding"), str) or
            re.fullmatch(r"[0-9a-f]{64}", receipt["binding"]) is None or
            not isinstance(captures, list) or not isinstance(receipt.get("captures"), list) or
            len(captures) != len(receipt["captures"])):
        return False
    for result, capture in zip(receipt["captures"], captures):
        if (not isinstance(result, dict) or set(result) != {
                "capture_sha256", "successful_video_interval", "matching_sequences"} or
                not isinstance(capture, dict) or
                result.get("capture_sha256") != capture.get("sha256") or
                result.get("successful_video_interval") != capture.get("successful_video_interval")):
            return False
        interval = result["successful_video_interval"]
        matches = result.get("matching_sequences")
        if (not isinstance(interval, list) or len(interval) != 2 or
                any(type(value) is not int for value in interval) or
                not isinstance(matches, list) or not matches or
                any(type(value) is not int or not interval[0] <= value <= interval[1]
                    for value in matches) or matches != sorted(set(matches))):
            return False
    return True


def _active_frontend_frozen_evidence_valid(frontend, sources, contract, *,
                                           require_current_identity: bool = False) -> bool:
    """A frozen flag alone cannot admit stale, partial or unreviewed calibration."""
    if (not isinstance(contract, dict) or not isinstance(contract.get("schedule"), dict) or
            not isinstance(frontend, dict) or frontend.get("frozen") is not True or
            not isinstance(frontend.get("sources"), dict) or
            (require_current_identity and frontend.get("sources") != sources) or
            frontend.get("calibration_outcome") != "captures_ready" or
            frontend.get("semantic_review") != "observed" or
            frontend.get("composition_policy") != FRONTEND_COMPOSITION_POLICY or
            not isinstance(frontend.get("reviewed_capture_identity"), str) or
            re.fullmatch(r"[0-9a-f]{64}", frontend["reviewed_capture_identity"]) is None):
        return False
    if (frontend.get("schedule_policy") != "same_controls_bounded_retiming_v1" or
            frontend.get("native_schedule_identity") != active_scene_configuration_identity(contract["schedule"]) or
            not _active_frontend_schedule_compatible(contract, frontend.get("schedule"))):
        return False
    path_value = frontend.get("calibration_report")
    if (not isinstance(path_value, str) or
            re.fullmatch(r"local/qualification/phase06/run-[0-9a-f]{32}/frontend-report\.json",
                         path_value) is None):
        return False
    path = Path(path_value)
    try:
        if (path.is_symlink() or not path.is_file() or not ignored(path) or
                not private_active_capture_directory_is_safe(path.parent) or
                path.stat().st_size > QUALIFICATION_REPORT_MAX_BYTES or
                _sha256_path(path) != frontend.get("calibration_report_sha256")):
            return False
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return False
    if not isinstance(report, dict):
        return False
    invocations = report.get("invocations")
    persisted_sources = frontend["sources"]
    if (report.get("status") != "complete" or report.get("sources") != persisted_sources or
            report.get("composition_policy") != FRONTEND_COMPOSITION_POLICY or
            not isinstance(report.get("predicates"), dict) or
            any(report["predicates"].get(name) != "pass" for name in
                ("scene", "composition", "right", "left", "projectile", "release",
                 "combined", "scroll", "overall")) or
            report.get("temporal_alignment") != "pass" or
            report.get("native_contract_identity") != _active_frontend_native_identity(contract) or
            report.get("frontend_schedule_identity") != active_scene_configuration_identity(frontend.get("schedule")) or
            report.get("media_identity") != contract["media_identity"] or
            report.get("app_identity") != frontend.get("app_identity") or
            report.get("configuration_identity") != frontend.get("configuration_identity") or
            not isinstance(invocations, list) or len(invocations) != 10):
        return False
    expected = {(pair, role) for pair in _ACTIVE_SCENE_PAIR_NAMES for role in ("action", "control")}
    seen, ids, captures = set(), set(), set()
    for invocation in invocations:
        if not isinstance(invocation, dict):
            return False
        pair_role = (invocation.get("pair"), invocation.get("role"))
        identifier = invocation.get("invocation_id")
        images = invocation.get("captures")
        if (any(not isinstance(value, str) for value in pair_role) or
                pair_role not in expected or pair_role in seen or
                not isinstance(identifier, str) or re.fullmatch(r"[0-9a-f]{32}", identifier) is None or identifier in ids or
                invocation.get("status") != "complete" or
                type(invocation.get("frontend_exit_code")) is not int or
                invocation.get("frontend_exit_code") != 0 or
                not isinstance(images, list) or len(images) != MAX_ACTIVE_CAPTURE_FRAMES):
            return False
        transfer_valid = (_active_frontend_transfer_valid(
            invocation, persisted_sources, report["configuration_identity"])
            if require_current_identity else _active_frontend_historical_transfer_valid(
                invocation, persisted_sources, report["configuration_identity"]))
        if not transfer_valid:
            return False
        seen.add(pair_role)
        ids.add(identifier)
        events = _active_scene_input_events(frontend.get("schedule"), *pair_role)
        if events is None or not _active_frontend_events_valid(invocation, events, identifier):
            return False
        targets = frontend["schedule"]["pairs"][pair_role[0]]["capture_frames"]
        for target, image in zip(targets, images):
            if not isinstance(image, dict) or not isinstance(image.get("path"), str):
                return False
            capture = Path(image["path"])
            expected_mask = 0
            for event_frame, mask in events:
                if event_frame <= target:
                    expected_mask = mask
            if (capture.is_symlink() or not capture.is_file() or not ignored(capture) or
                    not capture.resolve().is_relative_to(
                        (PROJECT_ROOT / PHASE06_RUN_ROOT / ("run-" + identifier) / "captures").resolve()) or
                    not active_scene_frontend_capture_is_valid(
                        image, invocation["observations"], invocation_id=identifier,
                        expected_mask=expected_mask, origin=invocation["active_origin_video_sequence"], target_frame=target) or
                    _sha256_path(capture) != image.get("sha256")):
                return False
            captures.add(image["sha256"])
    return seen == expected and frontend["reviewed_capture_identity"] in captures


def freeze_active_scene_frontend(contract_path: Path, review_path: Path) -> dict[str, object]:
    """Freeze only explicit, exact-capture semantic/composition review evidence."""
    rejected = {"status": "active_scene_frontend_freeze_rejected", "private_identity_recorded": False}
    status, contract = validate_scene_contract(contract_path)
    if contract is None:
        return {**rejected, "status": status}
    frontend = contract.get("frontend")
    if (not isinstance(frontend, dict) or frontend.get("frozen") is not False or
            frontend.get("calibration_outcome") != "captures_ready" or
            review_path.is_symlink() or not review_path.is_file() or
            not ignored(review_path) or
            not review_path.resolve().is_relative_to((PROJECT_ROOT / "local/qualification").resolve()) or
            review_path.stat().st_size > QUALIFICATION_REPORT_MAX_BYTES):
        return rejected
    try:
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if (not isinstance(review, dict) or type(review.get("schema_version")) is not int or
                review.get("schema_version") != 1 or
                review.get("review_outcome") != "pass" or
                review.get("calibration_report_sha256") != frontend.get("calibration_report_sha256") or
                review.get("evaluator_identity") != _production_evaluator_identity()):
            return rejected
        candidate = {**frontend, "frozen": True, "semantic_review": "observed",
                     "reviewed_capture_identity": review.get("reviewed_capture_identity")}
        candidate.pop("composition_references", None)
        core = _current_frontend_core(observations=True)
        if core is None or not _active_frontend_frozen_evidence_valid(
                candidate, _active_frontend_sources(core), contract,
                require_current_identity=True):
            return rejected
        contract["frontend"] = candidate
        contract.pop("contract_identity", None)
        contract["contract_identity"] = hashlib.sha256(json.dumps(
            contract, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        directory = _create_active_scene_run_directory()
        if directory is None or not _write_active_scene_contract(contract_path, contract, directory):
            return rejected
        return {"status": "active_scene_frontend_contract_frozen", "private_identity_recorded": True}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, StopIteration, RuntimeError):
        return rejected


def _frontend_sound_window_bounds(actual, schedule) -> dict[str, tuple[int, int]]:
    """Use observed key samples inside the frozen frontend retiming allowance."""
    parsed = _active_scene_schedule_masks(schedule)
    if parsed is None or not isinstance(actual, dict):
        raise ValueError("frontend-sound-schedule")
    origin, records = actual.get("active_origin_video_sequence"), actual.get("observations")
    if type(origin) is not int or origin < 1 or not isinstance(records, list):
        raise ValueError("frontend-sound-origin")
    nominal_start, nominal_release = parsed["fire"]["action"][0][0], parsed["fire"]["action"][-1][0]
    starts = [row["sample_sequence"] for row in records if row.get("event_kind") == "S"
              and row.get("sampled_mask") == 0x40 and
              origin + nominal_start <= row.get("sample_sequence", 0) <= origin + nominal_start + 64]
    if len(starts) != 1:
        raise ValueError("frontend-fire-onset")
    releases = [row["sample_sequence"] for row in records if row.get("event_kind") == "S"
                and row.get("sampled_mask") == 0 and row.get("sample_sequence", 0) > starts[0] and
                origin + nominal_release <= row.get("sample_sequence", 0) <= origin + nominal_release + 64]
    if len(releases) != 1:
        raise ValueError("frontend-fire-release")
    start, release = starts[0] - origin, releases[0] - origin
    if (not nominal_start <= start <= nominal_start + 64 or
            not nominal_release <= release <= nominal_release + 64 or start >= release):
        raise ValueError("frontend-sound-transition-bound")
    bounds = dict(music=(start - SOUND_WINDOW_MAX_FRAMES, start - 1),
                  fire=(start, min(release - 1, start + 23)),
                  release=(release, min(schedule["active_frames"] - 1, release + 24)))
    encoded = ",".join(f"{name}:{first}-{last}" for name, (first, last) in bounds.items())
    if _parse_sound_windows(encoded, schedule["active_frames"]) is None:
        raise ValueError("frontend-sound-window-bound")
    return bounds


def _frontend_sound_window_recording(actual, rows, pcm, role, bounds, directory, active_frames):
    """Slice verified callback bytes at replayed frame boundaries for existing rules."""
    if (role not in ("action", "control") or directory is None or
            not private_active_capture_directory_is_safe(directory) or
            not isinstance(pcm, bytes) or not pcm or len(pcm) % 4 or
            not isinstance(rows, list) or not 1 <= len(rows) <= 8192 or
            not isinstance(bounds, dict) or set(bounds) != {"music", "fire", "release"} or
            type(actual.get("active_origin_video_sequence")) is not int):
        raise ValueError("frontend-window-evidence")
    origin = actual["active_origin_video_sequence"]
    prefix = [0]
    for sequence, row in enumerate(rows, 1):
        if (row.get("sequence") != sequence or type(row.get("audio_frames")) is not int or
                not 0 < row["audio_frames"] <= 812 or
                not _phase07_elapsed_frame_clocks_are_valid(row.get("elapsed_cycles")) or
                not isinstance(row.get("chip"), dict) or set(row["chip"]) != {
                    "chip_reset", *SOUND_CHIP_FRAME_COUNTERS}):
            raise ValueError("frontend-window-frame")
        prefix.append(prefix[-1] + row["audio_frames"])
    if prefix[-1] * 4 != len(pcm):
        raise ValueError("frontend-window-PCM-boundary")
    recording = dict(role=role, windows={})
    for label, (first, last) in bounds.items():
        if (type(first) is not int or type(last) is not int or
                not 0 <= first <= last < active_frames or last - first >= SOUND_WINDOW_MAX_FRAMES or
                not 1 <= origin + first <= origin + last <= len(rows)):
            raise ValueError("frontend-window-range")
        name = "control" if label == "fire" and role == "control" else label
        wanted_mask = 0x40 if label == "fire" and role == "action" else 0
        selected = rows[origin + first - 1:origin + last]
        if any(row.get("sampled_mask") != wanted_mask for row in selected):
            raise ValueError("frontend-window-input")
        block = pcm[prefix[origin + first - 1] * 4:prefix[origin + last] * 4]
        if not 0 < len(block) <= SOUND_PCM_MAX_WINDOW_BYTES:
            raise ValueError("frontend-window-size")
        path = directory / f"sound-{name}.s16le"
        if not private_active_sound_path_is_valid(path):
            raise ValueError("frontend-window-private-path")
        with path.open("xb") as stream:
            stream.write(block)
        frame_rows = [dict(frame=first + offset, input_mask=row["sampled_mask"],
                           elapsed_cycles=row["elapsed_cycles"], audio_frames=row["audio_frames"])
                      for offset, row in enumerate(selected)]
        count = sum(row["audio_frames"] for row in selected)
        recording["windows"][name] = dict(
            name=name, first_frame=first, last_frame=last, completed_frames=last - first + 1,
            file=path.relative_to(Path("local/qualification")).as_posix(),
            sha256=hashlib.sha256(block).hexdigest(), bytes=len(block),
            actual_cycles=sum(row["elapsed_cycles"] for row in selected),
            audio_frames_generated=count, audio_frames_delivered=count, audio_frames_discarded=0,
            frame_observations=frame_rows,
            chip_frames=[dict(frame=first + offset, **row["chip"])
                         for offset, row in enumerate(selected)])
    return recording


def _frontend_audio_frame_history_valid(actual, rows, receipt) -> bool:
    """Bind chip rows to every replayed callback and the collected input/clock history."""
    try:
        audio = receipt["audio"]
        if (not isinstance(rows, list) or not rows or len(rows) > 8192 or
                audio["completed_sequences"] != len(rows) or
                audio["frame_sample_counts"] != [row["audio_frames"] for row in rows]):
            return False
        records = _load_retroarch_smoke()._validated_observation_records(
            actual["observations"], actual["invocation_id"])
        changes = {row["sample_sequence"]: row["sampled_mask"] for row in records
                   if row["event_kind"] == "S"}
        if 1 not in changes or max(changes) > len(rows):
            return False
        mask, clocks = 0, [0]
        for sequence, row in enumerate(rows, 1):
            mask = changes.get(sequence, mask)
            if (row["sequence"] != sequence or row["sampled_mask"] != mask or
                    not _phase07_elapsed_frame_clocks_are_valid(row["elapsed_cycles"])):
                return False
            clocks.append(clocks[-1] + row["elapsed_cycles"])
        return all(0 <= row["successful_video_sequence"] < len(clocks) and
                   row["executed_cycles"] == clocks[row["successful_video_sequence"]]
                   for row in records)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return False


def _frontend_audio_replay_plan(reference, schedule, role, smoke):
    """Reuse the whole acquired action history, with only the fire omission."""
    if role not in ("action", "control"):
        raise ValueError("audio-replay-role")
    origin = reference["active_origin_video_sequence"]
    if type(origin) is not int or not 1 <= origin < 8192:
        raise ValueError("audio-replay-origin")
    masks = smoke.sampled_mvs_masks(reference, origin + schedule["active_frames"])
    bounds = _frontend_sound_window_bounds(reference, schedule)
    first, release = origin + bounds["fire"][0], origin + bounds["release"][0]
    if not 1 <= first < release <= len(masks) or any(mask != 0x40 for mask in masks[first-1:release-1]):
        raise ValueError("audio-replay-fire-branch")
    if role == "control":
        masks[first-1:release-1] = [0] * (release-first)
    return dict(origin=origin, masks=masks)


def _frontend_audio_pair_inputs_valid(action, control, schedule, smoke):
    """Reject unequal prefixes and every unintended difference before slicing PCM."""
    try:
        plan = _frontend_audio_replay_plan(action, schedule, "control", smoke)
        return (control.get("active_origin_video_sequence") == plan["origin"] and
                smoke.sampled_mvs_masks(control, len(plan["masks"])) == plan["masks"])
    except (KeyError, TypeError, ValueError, RuntimeError):
        return False


def _run_active_scene_audio_trace(input_root: Path, importer, contract: dict[str, object],
                                  schedule: dict[str, object], core: dict[str, object],
                                  sources: dict[str, object], smoke, *,
                                  sound_contract: dict[str, object],
                                  contract_path: Path, sound_contract_path: Path,
                                  scene_digest: str, sound_digest: str,
                                  expected_app_identity: dict[str, object],
                                  role: str = "action", audio_control: str = "normal",
                                  input_reference: dict | None = None) -> dict[str, object]:
    """Capture and replay one ordinary fire role at the stated device-route control."""
    result = {"status": "unavailable", "capture_status": "unknown",
              "route_status": "unknown", "audibility": "unknown",
              "recognizable_sound": "unknown"}
    if role not in ("action", "control") or audio_control not in ("normal", "muted", "disabled"):
        return {**result, "reason": "unsupported-audio-control"}
    converter_identity = {
        "board": _sha256_path(PROJECT_ROOT / "src/mvs/mvs_bus.c"),
        "chip": _sha256_path(PROJECT_ROOT / "src/chips/ym2610_candidate.cpp")}
    if any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
           for value in converter_identity.values()):
        return {**result, "reason": "converter-identity-unavailable"}
    directory = _create_active_scene_run_directory()
    if directory is None:
        result["reason"] = "private-capture-directory-unavailable"
        return result
    invocation_id = directory.name.removeprefix("run-")
    record: dict[str, object] = {
        "invocation_id": invocation_id, "scenario": "fire-" + role, "role": role,
        "control": audio_control,
        "source_identity_before": sources,
        "sound_contract_identity": sound_contract.get("contract_identity"),
        "sound_contract_sha256": sound_digest,
        "sound_contract_schedule_identity": sound_contract.get("schedule_identity"),
        "phase06_contract_identity": contract.get("contract_identity"),
        "scene_contract_sha256": scene_digest,
    }
    try:
        events = _active_scene_input_events(schedule, "fire", role)
        pair_schedule = schedule.get("pairs", {}).get("fire", {})
        targets = pair_schedule.get("capture_frames") if isinstance(pair_schedule, dict) else None
        if not isinstance(events, list) or not events or not isinstance(targets, list) or not targets:
            raise ValueError("schedule")
        sound_windows = _phase07_sound_windows(schedule, role)
        if sound_windows is None:
            raise ValueError("sound-window-schedule")
        if (_active_frontend_sources(core) != sources or
                not _phase07_contract_files_unchanged(
                    contract_path, scene_digest, sound_contract_path, sound_digest)):
            raise ValueError("pre-acquisition-identity")
        record.update(
            frontend_schedule_identity=active_scene_configuration_identity(schedule),
            frontend_fire_events=events,
            frontend_sound_windows=sound_windows,
            audio_stage="frontend_libretro_audio_callback_pre_flush",
            audio_format="pcm_s16le_interleaved_stereo",
            audio_sample_rate_hz=48000,
            audio_interval_alignment="complete callback PCM and frame sample counts checked by real libretro replay")
        target = targets[len(targets) // 2]
        with tempfile.TemporaryDirectory(prefix="glueyneo-active-audio-import-") as temporary:
            normalized = Path(temporary) / "selected.gnmv"
            selected = find_pairs(input_root)
            command = checked_importer_command(importer, identity=contract["code_identity"]["importer"])
            if (len(selected) != 1 or command is None or
                    [_file_identity(path) for path in selected[0]] != contract["media_identity"]):
                raise ValueError("media-identity")
            imported = subprocess.run(
                [command, "--selected", *map(str, selected[0]), str(normalized)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=IMPORT_TIMEOUT_SECONDS, check=False)
            if imported.returncode != 0 or not _selected_v3_bundle_has_zoom_role(normalized, smoke):
                raise ValueError("selected-import")
            replay_kwargs = ({"input_replay": _frontend_audio_replay_plan(input_reference, schedule, role, smoke)}
                             if input_reference is not None else {})
            if (role != "action" or audio_control != "normal") and input_reference is None:
                raise ValueError("audio-replay-reference-required")
            actual = smoke.run_mvs_active_scene(
                argparse.Namespace(retroarch=Path("/Applications/RetroArch.app"),
                                   core=Path(core["path"]), content=normalized,
                                   timeout=120, capture_dir=directory / "captures",
                                   child_pid_file=None),
                {"events": events, "capture_frames": [target],
                 "active_frames": schedule["active_frames"]},
                invocation_id=invocation_id, audio_control=audio_control, **replay_kwargs)
            record["actual_run"] = actual
            work = actual.get("configuration_work_directory")
            replay_configuration = _frontend_configuration_identity(
                actual.get("configuration_text"),
                work_directory=Path(work) if isinstance(work, str) else None,
                capture_directory=(directory / "captures").resolve())
            if replay_configuration is None:
                raise ValueError("audio-configuration")
            chip_log = directory / "captures" / "frontend-process-private.log"
            chip_log_digest = _sha256_path(chip_log)
            chip_rows = smoke.parse_frontend_audio_frames(chip_log)
            audio = actual.get("audio_evidence")
            if not isinstance(audio, dict) or not chip_rows or not isinstance(chip_log_digest, str):
                raise ValueError("audio-chip-evidence")
            audio["chip_frames"] = dict(status="pass", row_count=len(chip_rows),
                                         log_sha256=chip_log_digest,
                                         sample_frames=sum(row["audio_frames"] for row in chip_rows))
            actual["audio_replay_context"] = dict(
                scene_contract_sha256=scene_digest, sound_contract_sha256=sound_digest,
                schedule_identity=active_scene_configuration_identity(schedule),
                converter_identity=converter_identity, control=audio_control)
            replay = _load_frontend_replay()
            actual["replay"] = replay.run_replay(core, normalized, actual, replay_configuration,
                                                 require_audio=True)
            if not _frontend_audio_frame_history_valid(actual, chip_rows, actual["replay"]):
                raise ValueError("audio-chip-frame-alignment")
            record["chip_frame_alignment_status"] = "pass"
        work = actual.get("configuration_work_directory")
        config_identity = _frontend_configuration_identity(
            actual.get("configuration_text"),
            work_directory=Path(work) if isinstance(work, str) else None,
            capture_directory=(directory / "captures").resolve())
        audio = actual.get("audio_evidence")
        capture = audio.get("capture") if isinstance(audio, dict) else None
        route = audio.get("route") if isinstance(audio, dict) else None
        actual_identity = actual.get("identity")
        stable_identity = ({key: actual_identity.get(key) for key in
                            ("retroarch_version", "retroarch_executable_sha256", "bundle_id", "core_sha256")}
                           if isinstance(actual_identity, dict) else None)
        capture_status = capture.get("status") if isinstance(capture, dict) else "unknown"
        route_status = route.get("status") if isinstance(route, dict) else "unknown"
        audio_evidence_valid = smoke.frontend_audio_evidence_is_valid(
            capture, route, expected_control=audio_control,
            delivery=audio.get("delivery") if isinstance(audio, dict) else None)
        replay_valid = replay.validate_receipt(
            actual.get("replay"), core["sha256"], actual.get("selected_bundle_sha256"),
            actual, config_identity)
        observed_events_ok = _active_frontend_events_valid(actual, events, invocation_id)
        captures = actual.get("captures")
        observations = actual.get("observations")
        origin = actual.get("active_origin_video_sequence")
        expected_mask = 0
        for event_frame, mask in events:
            if event_frame <= target:
                expected_mask = mask
        capture_ok = (isinstance(captures, list) and len(captures) == 1 and
                      isinstance(observations, list) and type(origin) is int and
                      active_scene_frontend_capture_is_valid(
                          captures[0], observations, invocation_id=invocation_id,
                          expected_mask=expected_mask, origin=origin, target_frame=target))
        identity_ok = (
            actual.get("status") == "complete" and
            isinstance(stable_identity, dict) and
            stable_identity == expected_app_identity and
            _active_frontend_identity_matches(
                (contract.get("frontend") or {}).get("app_identity"), stable_identity, sources) and
            config_identity is not None and
            _active_frontend_sources(core) == sources and
            _file_identity(Path(core["path"])).get("sha256") == core.get("sha256") and
            [_file_identity(path) for path in selected[0]] == contract["media_identity"] and
            _phase07_sound_contract_scene_binding_valid(
                sound_contract, contract, contract_path, scene_digest=scene_digest) and
            _phase07_contract_files_unchanged(
                contract_path, scene_digest, sound_contract_path, sound_digest) and
            converter_identity == {
                "board": _sha256_path(PROJECT_ROOT / "src/mvs/mvs_bus.c"),
                "chip": _sha256_path(PROJECT_ROOT / "src/chips/ym2610_candidate.cpp")} and
            chip_log_digest == _sha256_path(chip_log))
        record.update(
            audio_configuration_identity=config_identity,
            audio_replay_status="pass" if replay_valid else "fail",
            source_identity_after=_active_frontend_sources(core),
            current_source_identity_status="pass" if identity_ok else "fail",
            sampled_input_and_video_status=("pass" if observed_events_ok and capture_ok else "fail"),
            callback_capture_status=capture_status,
            adapter_delivery_status=(audio.get("delivery", {}).get("status", "unknown")
                                     if isinstance(audio, dict) else "unknown"),
            complete_audio_receipt_status="pass" if audio_evidence_valid else "fail",
            active_route_status=route_status,
            physical_audibility="unknown",
            recognizable_game_sound="unknown")
        status = ("pass" if identity_ok and observed_events_ok and capture_ok and
                  audio_evidence_valid and replay_valid else
                  "unavailable" if capture_status == "unavailable" else "fail")
        result.update(status=status, capture_status=capture_status,
                      route_status=route_status, audibility="unknown",
                      recognizable_sound="unknown")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError,
            subprocess.SubprocessError) as error:
        record.update(status="incomplete", failure_type=type(error).__name__)
        result.update(status="unavailable", reason="actual-audio-trace-incomplete")
    finally:
        record["result"] = dict(result)
        record["report_written"] = write_report(directory / "frontend-audio-trace.json", record)
        if record["report_written"]:
            result["private_report_path"] = (directory / "frontend-audio-trace.json").as_posix()
        else:
            result.update(status="unavailable", reason="private-audio-report-unavailable")
    return result


def _read_frontend_audio_trace(trace, role, control, sources, scene_digest, sound_digest,
                               schedule_digest, smoke, *, retained=False):
    """Revalidate a producer receipt and its retained bytes before causal slicing."""
    value = trace.get("private_report_path") if isinstance(trace, dict) else None
    if (not isinstance(value, str) or re.fullmatch(
            r"local/qualification/phase06/run-[0-9a-f]{32}/frontend-audio-trace\.json", value) is None):
        raise ValueError("audio-control-report-path")
    path = Path(value)
    if (not private_active_capture_directory_is_safe(path.parent) or path.is_symlink() or
            not path.is_file() or path.stat().st_size > QUALIFICATION_REPORT_MAX_BYTES):
        raise ValueError("audio-control-report-owner")
    with path.open("rb") as stream:
        original = stream.read(QUALIFICATION_REPORT_MAX_BYTES + 1)
    if len(original) > QUALIFICATION_REPORT_MAX_BYTES:
        raise ValueError("audio-control-report-limit")
    record = json.loads(original)
    if (record.get("result", {}).get("status") != "pass" or record.get("role") != role or
            record.get("control") != control or
            record.get("source_identity_before") != sources or record.get("source_identity_after") != sources or
            record.get("scene_contract_sha256") != scene_digest or
            record.get("sound_contract_sha256") != sound_digest or
            record.get("frontend_schedule_identity") != schedule_digest):
        raise ValueError("audio-control-source-binding")
    actual = record["actual_run"]
    if (actual["identity"]["core_sha256"] != sources["core_sha256"] or
            actual["audio_replay_context"]["control"] != control):
        raise ValueError("audio-control-stage-binding")
    settings = dict(re.findall(r'^\s*(audio_enable|audio_mute_enable)\s*=\s*"(true|false)"\s*$',
                               actual["configuration_text"], re.MULTILINE))
    if settings != dict(audio_enable="false" if control == "disabled" else "true",
                        audio_mute_enable="true" if control == "muted" else "false"):
        raise ValueError("audio-control-launch-configuration")
    replay = _load_frontend_replay()
    if retained:
        original_implementation = dict(helper=sources["replay_sha256"], collector=sources["collector_sha256"],
                                       evaluator=sources["evaluator"]["sha256"])
        replay_valid = replay.validate_retained_receipt(actual.get("replay"), sources["core_sha256"],
            actual["selected_bundle_sha256"], actual, record["audio_configuration_identity"], original_implementation)
    else:
        replay_valid = replay.validate_receipt(actual.get("replay"), sources["core_sha256"],
            actual["selected_bundle_sha256"], actual, record["audio_configuration_identity"])
    if not replay_valid:
        raise ValueError("audio-control-replay-binding")
    for capture in actual["captures"]:
        replay._capture_rgb(capture)
    pcm = replay._capture_pcm(actual)
    log = path.parent / "captures" / "frontend-process-private.log"
    summary = actual["audio_evidence"]["chip_frames"]
    if summary.get("status") != "pass" or _sha256_path(log) != summary.get("log_sha256"):
        raise ValueError("audio-control-chip-identity")
    rows = smoke.parse_frontend_audio_frames(log)
    if (len(rows) != summary.get("row_count") or
            sum(row["audio_frames"] for row in rows) != summary.get("sample_frames") or
            not _frontend_audio_frame_history_valid(actual, rows, actual["replay"])):
        raise ValueError("audio-control-frame-history")
    with path.open("rb") as stream:
        if stream.read(QUALIFICATION_REPORT_MAX_BYTES + 1) != original:
            raise ValueError("audio-control-report-changed")
    return dict(actual=actual, rows=rows, pcm=pcm)


def _run_frontend_audio_controls(first_trace, acquire, schedule, sources,
                                 scene_digest, sound_digest, thresholds, smoke):
    """Prove all route receipts and common music before spending visual boots."""
    result = dict(status="unavailable", traces={}, recordings={},
                  audibility="unknown", recognizable_sound="unknown")
    directory = _create_active_scene_run_directory(PHASE07_RUN_ROOT)
    if directory is None:
        return result
    loaded = {}
    try:
        digest = active_scene_configuration_identity(schedule)
        for role, control in (("action", "normal"), ("control", "normal"),
                              ("action", "muted"), ("action", "disabled")):
            trace = first_trace if (role, control) == ("action", "normal") else acquire(role, control)
            result["traces"][control + "-" + role] = trace
            if not isinstance(trace, dict) or trace.get("status") != "pass":
                raise ValueError("audio-control-incomplete")
            evidence = _read_frontend_audio_trace(trace, role, control, sources,
                                                   scene_digest, sound_digest, digest, smoke)
            if control == "normal":
                loaded[role] = evidence
            if (role, control) == ("control", "normal"):
                if not _frontend_audio_pair_inputs_valid(loaded["action"]["actual"], loaded["control"]["actual"],
                                                         schedule, smoke):
                    result["input_prefix_and_branch"] = "fail"
                    raise ValueError("audio-control-input-prefix-or-branch")
                result["input_prefix_and_branch"] = "pass"
                bounds = _frontend_sound_window_bounds(loaded["action"]["actual"], schedule)
                for window_role in ("action", "control"):
                    selected = loaded[window_role]
                    target = _create_active_scene_run_directory(PHASE07_RUN_ROOT)
                    result["recordings"][window_role] = _frontend_sound_window_recording(
                        selected["actual"], selected["rows"], selected["pcm"], window_role,
                        bounds, target, schedule["active_frames"])
                result["sound_outcomes"] = _phase07_calibration_outcomes(result["recordings"], thresholds=thresholds)
                if result["sound_outcomes"].get("music") != "pass":
                    raise ValueError("audio-common-music-unmatched")
        # Fire/release still require the actual visual campaign. Missing exact
        # common music can already decide failure and must not trigger ten boots.
        result["status"] = "pass" if result["sound_outcomes"].get("music") == "pass" else "incomplete"
        result["window_alignment"] = "observed action/release samples; equal relative guest frames"
        result["route_control_limits"] = "mute configured only; no physical audibility or recognizability proof"
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as error:
        result.update(status="incomplete", failure_type=type(error).__name__)
    if not write_report(directory / "frontend-audio-controls.json", result):
        result["status"] = "unavailable"
    return result


def evaluate_retained_frontend_audio(report_path: Path, contract_path: Path,
                                     sound_contract_path: Path) -> dict[str, object]:
    """Evaluate one recorded normal/action stream without native/device execution."""
    result = dict(status="retained_frontend_audio_rejected", new_frontend_observation=False,
                  native_execution="not-run", device_evidence="not-refreshed",
                  omission_control="pending", window_alignment="unknown")
    if (contract_path != PHASE06_CONTRACT_PATH or sound_contract_path != PHASE07_SOUND_CONTRACT_PATH or
            re.fullmatch(r"local/qualification/phase06/run-[0-9a-f]{32}/frontend-audio-trace\.json",
                         report_path.as_posix()) is None or
            not private_active_capture_directory_is_safe(report_path.parent) or report_path.is_symlink()):
        return result
    try:
        with report_path.open("rb") as stream:
            original = stream.read(QUALIFICATION_REPORT_MAX_BYTES + 1)
        if not 0 < len(original) <= QUALIFICATION_REPORT_MAX_BYTES:
            return result
        report = json.loads(original)
        scene_digest, sound_digest = _sha256_path(contract_path), _sha256_path(sound_contract_path)
        _, contract = validate_scene_contract(contract_path, Path("local/roms"), check_current_identity=False)
        sound_contract = _read_phase07_sound_contract(sound_contract_path, require_frozen=True)
        if (contract is None or sound_contract is None or
                not _phase07_sound_contract_scene_binding_valid(
                    sound_contract, contract, contract_path, scene_digest=scene_digest)):
            return result
        schedule = contract["frontend"]["schedule"]
        sources = report["source_identity_before"]
        loaded = _read_frontend_audio_trace(dict(private_report_path=report_path.as_posix()),
            "action", "normal", sources, scene_digest, sound_digest,
            active_scene_configuration_identity(schedule), _load_retroarch_smoke(), retained=True)
        bounds = _frontend_sound_window_bounds(loaded["actual"], schedule)
        directory = _create_active_scene_run_directory(PHASE07_RUN_ROOT)
        recording = _frontend_sound_window_recording(loaded["actual"], loaded["rows"], loaded["pcm"],
            "action", bounds, directory, schedule["active_frames"])
        windows = {}
        for name, mask in (("music", 0), ("fire", 0x40), ("release", 0)):
            rows = _phase07_window_causal_frames(recording, name, mask)
            if rows is None:
                return result
            windows[name] = dict(frame_alignment="pass", family_output_observed=any(
                _phase07_family_output_on_frame(row) for row in rows))
        with report_path.open("rb") as stream:
            if stream.read(QUALIFICATION_REPORT_MAX_BYTES + 1) != original:
                return result
        if not _phase07_contract_files_unchanged(contract_path, scene_digest, sound_contract_path, sound_digest):
            return result
        evidence = dict(result, status="retained_frontend_audio_evaluated", window_alignment="pass",
                        windows=windows, acquisition_sources=sources,
                        evaluation_identity=_production_evaluator_identity(), recording=recording,
                        sound_outcomes=_phase07_calibration_outcomes({"action": recording}))
        if write_report(directory / "retained-audio-evaluation.json", evidence):
            return {key: value for key, value in evidence.items()
                    if key not in {"acquisition_sources", "evaluation_identity", "recording"}}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return result
    return result


def evaluate_retained_frontend_captures(report_path: Path, contract_path: Path
                                       ) -> dict[str, object]:
    """Fast pixel diagnosis of one immutable campaign; no frontend/core execution.

    Original acquisition and transfer identities remain historical. Current
    evaluator results are written separately and cannot refresh device, audio,
    pacing, or current-core execution evidence.
    """
    result = {"status": "retained_frontend_evaluation_rejected",
              "new_frontend_observation": False, "device_evidence": "not-refreshed",
              "native_execution": "not-run", "predicate_results": {"overall": "unknown"}}
    if (contract_path != PHASE06_CONTRACT_PATH or
            re.fullmatch(r"local/qualification/phase06/run-[0-9a-f]{32}/frontend-report\.json",
                         report_path.as_posix()) is None or
            not private_active_capture_directory_is_safe(report_path.parent) or
            report_path.is_symlink() or not report_path.is_file()):
        return result
    try:
        with report_path.open("rb") as stream:
            original = stream.read(QUALIFICATION_REPORT_MAX_BYTES + 1)
        if not 0 < len(original) <= QUALIFICATION_REPORT_MAX_BYTES:
            return result
        report = json.loads(original)
        contract_before = _sha256_path(contract_path)
        _, contract = validate_scene_contract(contract_path, Path("local/roms"),
                                              check_current_identity=False)
        if contract is None or not isinstance(report, dict):
            return result
        schedule = contract.get("frontend", {}).get("schedule")
        sources = report.get("sources")
        app_identity = report.get("app_identity")
        configuration = report.get("configuration_identity")
        invocations = report.get("invocations")
        if (report.get("status") != "complete" or
                report.get("composition_policy") != FRONTEND_COMPOSITION_POLICY or
                report.get("contract_identity") != contract.get("contract_identity") or
                report.get("media_identity") != contract.get("media_identity") or
                report.get("native_contract_identity") != _active_frontend_native_identity(contract) or
                not _active_frontend_schedule_compatible(contract, schedule) or
                report.get("frontend_schedule_identity") != active_scene_configuration_identity(schedule) or
                not isinstance(sources, dict) or not isinstance(sources.get("evaluator"), dict) or
                not isinstance(app_identity, dict) or not _active_frontend_identity_matches(
                    contract.get("frontend", {}).get("app_identity"), app_identity, sources) or
                not isinstance(invocations, list) or len(invocations) != 10 or
                not isinstance(configuration, str) or not configuration):
            return result
        recorded_identity = dict(helper=sources.get("replay_sha256"),
                                 collector=sources.get("collector_sha256"),
                                 evaluator=sources["evaluator"].get("sha256"))
        replay = _load_frontend_replay()
        runs: dict[str, dict[str, list[bytes]]] = {}
        seen = set()
        for row in invocations:
            if not isinstance(row, dict):
                return result
            pair, role, identifier = row.get("pair"), row.get("role"), row.get("invocation_id")
            if (pair not in _ACTIVE_SCENE_PAIR_NAMES or role not in ("action", "control") or
                    (pair, role) in seen or not isinstance(identifier, str) or
                    re.fullmatch(r"[0-9a-f]{32}", identifier) is None or
                    row.get("status") != "complete" or type(row.get("frontend_exit_code")) is not int or
                    row["frontend_exit_code"] != 0 or
                    not isinstance(row.get("identity"), dict) or
                    {key: row["identity"].get(key) for key in app_identity} != app_identity or
                    not replay.validate_retained_receipt(
                        row.get("replay"), sources.get("core_sha256"), row.get("selected_bundle_sha256"),
                        row, configuration, recorded_identity)):
                return result
            seen.add((pair, role))
            events = _active_scene_input_events(schedule, pair, role)
            if not _active_frontend_events_valid(row, events, identifier):
                return result
            captures = row.get("captures")
            targets = schedule["pairs"][pair]["capture_frames"]
            if not isinstance(captures, list) or len(captures) != MAX_ACTIVE_CAPTURE_FRAMES:
                return result
            owned = Path("local/qualification/phase06") / ("run-" + identifier)
            if not private_active_capture_directory_is_safe(owned) or (owned / "captures").is_symlink():
                return result
            frames = []
            for capture, target in zip(captures, targets):
                expected_mask = 0
                for event_frame, mask in events:
                    if event_frame <= target:
                        expected_mask = mask
                if not active_scene_frontend_capture_is_valid(
                        capture, row["observations"], invocation_id=identifier,
                        expected_mask=expected_mask, origin=row.get("active_origin_video_sequence"),
                        target_frame=target):
                    return result
                path = Path(capture["path"])
                if (path.is_symlink() or path.parent.resolve() != (owned / "captures").resolve() or
                        not ignored(path)):
                    return result
                frames.append(replay._capture_rgb(capture))
            runs.setdefault(pair, {})[role] = frames
        if not _active_frontend_temporal_bounds_valid(schedule, invocations):
            return result
        neutral = runs["right"]["control"]
        runs["scene"] = {"status": "complete", "t0": neutral[0], "endpoint": neutral[-1]}
        outcomes = evaluate_active_scene_pairs(dict(contract, schedule=schedule), runs,
                                               frontend_intervals=True)
        # Composition here means the already acquired, hash-bound full-RGB
        # transfer. No current-core replay or renderer/device truth is implied.
        outcomes["composition"] = "pass"
        values = [value for key, value in outcomes.items() if key != "overall"]
        outcomes["overall"] = ("pass" if all(value == "pass" for value in values) else
                               "fail" if "fail" in values else "unknown")
        with report_path.open("rb") as stream:
            if stream.read(QUALIFICATION_REPORT_MAX_BYTES + 1) != original:
                return result
        if contract_before != _sha256_path(contract_path):
            return result
        directory = _create_active_scene_run_directory()
        if directory is None:
            return result
        evidence = dict(result, status="retained_frontend_evaluated", predicate_results=outcomes,
                        acquisition_report_sha256=hashlib.sha256(original).hexdigest(),
                        acquisition_sources=sources, evaluation_identity=_production_evaluator_identity(),
                        scene_contract_sha256=contract_before, transfer_evidence="retained-binding-validated")
        if write_report(directory / "retained-evaluation.json", evidence):
            return {key: evidence[key] for key in result}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return result
    return result


def run_active_scene_frontend(input_root: Path, importer, contract_path: Path,
                              *, calibrate: bool = False,
                              sound_contract_path: Path | None = None,
                              audio_only: bool = False,
                              audio_controls_only: bool = False) -> dict[str, object]:
    """Run actual owned frontend boots; all detailed identities/pixels stay ignored."""
    unknown = {name: "unknown" for name in
               ("scene", "composition", "right", "left", "projectile", "release",
                "combined", "scroll", "overall")}
    failure = {"status": "active_scene_frontend_incomplete",
               "private_identity_recorded": False, "predicate_results": unknown}
    if (type(audio_only) is not bool or type(audio_controls_only) is not bool or
            (audio_only or audio_controls_only) and calibrate or audio_only and audio_controls_only):
        return failure
    status, contract = validate_scene_contract(
        contract_path, input_root, check_current_identity=calibrate)
    if contract is None:
        return {**failure, "status": status}
    core = (_build_frontend_core(observations=True) if calibrate else
            _current_frontend_core(observations=True))
    if core is None:
        return {**failure, "status": "active_scene_frontend_build_failed"}
    sources = _active_frontend_sources(core)
    try:
        scene_digest = _sha256_path(contract_path)
    except OSError:
        scene_digest = None
    sound_contract = None
    sound_digest = None
    if not calibrate:
        if sound_contract_path != PHASE07_SOUND_CONTRACT_PATH or scene_digest is None:
            return {**failure, "status": "active_scene_sound_contract_stale"}
        sound_contract = _read_phase07_sound_contract(
            sound_contract_path, require_frozen=True)
        try:
            sound_digest = _sha256_path(sound_contract_path)
        except OSError:
            sound_digest = None
        if (sound_contract is None or sound_digest is None or
                not _phase07_sound_contract_scene_binding_valid(
                    sound_contract, contract, contract_path, scene_digest=scene_digest)):
            return {**failure, "status": "active_scene_sound_contract_stale"}
    frontend = contract.get("frontend")
    if not calibrate and not _active_frontend_frozen_evidence_valid(frontend, sources, contract):
        return {**failure, "status": "active_scene_frontend_contract_unfrozen"}
    schedule = (frontend.get("schedule") if isinstance(frontend, dict) and
                isinstance(frontend.get("schedule"), dict) else contract["schedule"])
    if (not _active_frontend_schedule_compatible(contract, schedule) or
            isinstance(frontend, dict) and frontend.get("native_schedule_identity") !=
            active_scene_configuration_identity(contract["schedule"])):
        return {**failure, "status": "active_scene_frontend_schedule_rejected"}
    # Thresholds, regions, entry and complete mask sequences inherit the native
    # contract. Host capture windows may retime these same controls; calibration
    # and exact-capture review freeze that explicit translation before acceptance.
    evaluation_contract = dict(contract, schedule=schedule)
    report_directory = _create_active_scene_run_directory()
    if report_directory is None:
        return {**failure, "status": "private_capture_path_unavailable"}
    smoke = _load_retroarch_smoke()
    # Prove the first actual audio seam before spending the bounded visual
    # campaign. A missing recorder/route must be diagnosed at the tracer, not
    # hidden behind ten prerequisite boots that consume the desktop window.
    audio_trace = {"status": "not-run", "capture_status": "unknown",
                   "route_status": "unknown", "audibility": "unknown",
                   "recognizable_sound": "unknown"}
    audio_controls = {"status": "not-run", "recordings": {}, "traces": {}}
    if not calibrate:
        expected_identity = dict(frontend["app_identity"], core_sha256=core["sha256"])
        def acquire_audio(role="action", control="normal"):
            reference = None
            if role != "action" or control != "normal":
                reference = _read_frontend_audio_trace(
                    audio_trace, "action", "normal", sources, scene_digest, sound_digest,
                    active_scene_configuration_identity(schedule), smoke)["actual"]
            return _run_active_scene_audio_trace(
                input_root, importer, contract, schedule, core, sources, smoke,
                sound_contract=sound_contract, contract_path=contract_path,
                sound_contract_path=sound_contract_path, scene_digest=scene_digest,
                sound_digest=sound_digest, expected_app_identity=expected_identity,
                role=role, audio_control=control, input_reference=reference)
        audio_trace = acquire_audio()
        if audio_trace.get("status") != "pass":
            return {**failure, "audio_evidence": {key: audio_trace.get(key) for key in
                    ("status", "capture_status", "route_status", "audibility",
                     "recognizable_sound")}}
        if audio_only:
            return {"status": "active_scene_frontend_audio_recorded",
                    "private_identity_recorded": True, "predicate_results": unknown,
                    "audio_evidence": {key: audio_trace.get(key) for key in
                        ("status", "capture_status", "route_status", "audibility", "recognizable_sound")}}
        audio_controls = _run_frontend_audio_controls(
            audio_trace, acquire_audio, schedule, sources, scene_digest, sound_digest,
            sound_contract.get("thresholds", PHASE07_SOUND_THRESHOLDS), smoke)
        if audio_controls.get("status") != "pass":
            return {**failure, "audio_evidence": {"status": "incomplete",
                    "capture_status": audio_trace.get("capture_status"),
                    "route_status": audio_trace.get("route_status"),
                    "controls_status": audio_controls.get("status"),
                    "audibility": "unknown", "recognizable_sound": "unknown"},
                    "sound_outcomes": audio_controls.get("sound_outcomes", {"overall": "unknown"})}
        if audio_controls_only:
            return {"status": "active_scene_frontend_audio_controls_recorded",
                    "private_identity_recorded": True, "predicate_results": unknown,
                    "audio_evidence": {"status": "pass", "controls_status": "pass",
                        "capture_status": audio_trace.get("capture_status"),
                        "route_status": audio_trace.get("route_status"),
                        "audibility": "unknown", "recognizable_sound": "unknown"},
                    "sound_outcomes": audio_controls.get("sound_outcomes", {"overall": "unknown"})}
    invocations = []
    runs = {}
    identities_ok = True
    app_identity = None
    configuration_identity = None
    for pair in ("right", "left", "fire", "combined", "scroll"):
        runs[pair] = {}
        for role in ("action", "control"):
            directory = _create_active_scene_run_directory()
            if directory is None:
                identities_ok = False
                break
            invocation_id = directory.name.removeprefix("run-")
            events = _active_scene_input_events(schedule, pair, role)
            record = {"pair": pair, "role": role, "invocation_id": invocation_id}
            try:
                with tempfile.TemporaryDirectory(prefix="glueyneo-active-import-") as temporary:
                    normalized = Path(temporary) / "selected.gnmv"
                    selected = find_pairs(input_root)
                    command = checked_importer_command(importer, identity=contract["code_identity"]["importer"])
                    if (len(selected) != 1 or command is None or
                            [_file_identity(path) for path in selected[0]] != contract["media_identity"]):
                        raise ValueError("identity")
                    imported = subprocess.run(
                        [command, "--selected", *map(str, selected[0]), str(normalized)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=IMPORT_TIMEOUT_SECONDS, check=False)
                    if imported.returncode != 0 or not _selected_v3_bundle_has_zoom_role(normalized, smoke):
                        raise ValueError("import")
                    actual = smoke.run_mvs_active_scene(argparse.Namespace(
                        retroarch=Path("/Applications/RetroArch.app"), core=Path(core["path"]),
                        content=normalized, timeout=120, capture_dir=directory / "captures",
                        child_pid_file=None), {
                            "events": events, "capture_frames": schedule["pairs"][pair]["capture_frames"],
                            "active_frames": schedule["active_frames"]}, invocation_id=invocation_id)
                    # A replay failure must retain the original real frontend
                    # observations and captures, rather than erase that evidence.
                    record.update(actual)
                    work = actual.get("configuration_work_directory")
                    replay_configuration = _frontend_configuration_identity(
                        actual.get("configuration_text"),
                        work_directory=Path(work) if isinstance(work, str) else None,
                        capture_directory=(directory / "captures").resolve())
                    if replay_configuration is None:
                        raise ValueError("configuration")
                    actual["replay"] = _load_frontend_replay().run_replay(
                        core, normalized, actual, replay_configuration)
                record.update(actual)
                identity = actual.get("identity")
                if not isinstance(identity, dict) or identity.get("core_sha256") != core["sha256"]:
                    raise ValueError("identity")
                stable_identity = {key: identity.get(key) for key in
                                   ("retroarch_version", "retroarch_executable_sha256", "bundle_id", "core_sha256")}
                work_directory = actual.get("configuration_work_directory")
                config_identity = _frontend_configuration_identity(actual.get("configuration_text"),
                    work_directory=Path(work_directory) if isinstance(work_directory,str) else None,
                    capture_directory=(directory / "captures").resolve())
                if app_identity is None:
                    app_identity, configuration_identity = stable_identity, config_identity
                frozen_identity_matches = (calibrate or _active_frontend_identity_matches(
                    frontend.get("app_identity"), stable_identity, sources))
                if (stable_identity != app_identity or config_identity is None or
                        config_identity != configuration_identity or
                        (not calibrate and (not frozen_identity_matches or
                                            frontend.get("configuration_identity") != config_identity))):
                    raise ValueError("identity")
                observations = actual.get("observations")
                captures = actual.get("captures")
                origin = actual.get("active_origin_video_sequence")
                targets = schedule["pairs"][pair]["capture_frames"]
                if (actual.get("status") != "complete" or actual.get("invocation_id") != invocation_id or
                        type(actual.get("frontend_exit_code")) is not int or
                        actual.get("frontend_exit_code") != 0 or not isinstance(captures, list) or
                        len(captures) != MAX_ACTIVE_CAPTURE_FRAMES or
                        not isinstance(observations, list) or
                        not any(item.get("event_kind") == "P" for item in observations)):
                    raise ValueError("incomplete")
                if not _active_frontend_events_valid(actual, events, invocation_id):
                    raise ValueError("inputs")
                frames = []
                for target, capture in zip(targets, captures):
                    expected_mask = 0
                    for event_frame, mask in events:
                        if event_frame <= target:
                            expected_mask = mask
                    if not active_scene_frontend_capture_is_valid(
                            capture, observations, invocation_id=invocation_id,
                            expected_mask=expected_mask, origin=origin, target_frame=target):
                        raise ValueError("capture")
                    if capture["successful_video_interval"][1] > origin + schedule["active_frames"]:
                        raise ValueError("horizon")
                    path = Path(capture["path"])
                    if (path.is_symlink() or not path.is_file() or not ignored(path) or
                            not path.resolve().is_relative_to((directory / "captures").resolve()) or
                            _sha256_path(path) != capture["sha256"]):
                        raise ValueError("capture")
                    width, height, channels, pixels = smoke.decode_png(path)
                    if channels == 4:
                        pixels = b"".join(pixels[index:index + 3]
                                          for index in range(0, len(pixels), 4))
                    if (width, height) != (320, 224) or len(pixels) != 320 * 224 * 3:
                        raise ValueError("capture")
                    frames.append(pixels)
                runs[pair][role] = frames
                if (_active_frontend_sources(core) != sources or
                        _file_identity(Path(core["path"]))["sha256"] != core["sha256"] or
                        [_file_identity(path) for path in selected[0]] != contract["media_identity"] or
                        (not calibrate and not _phase07_contract_files_unchanged(
                            contract_path, scene_digest, sound_contract_path, sound_digest))):
                    raise ValueError("identity")
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError,
                    subprocess.SubprocessError) as error:
                record.update(status="incomplete", failure_type=type(error).__name__,
                              failure_stage=getattr(error, "stage", "binding"))
                if isinstance(getattr(error, "diagnostic", None), dict):
                    record["private_diagnostic"] = error.diagnostic
                identities_ok = False
            finally:
                write_report(directory / "frontend-case.json", record)
                invocations.append(record)
            if not identities_ok:
                break
        if not identities_ok:
            break
    if (not calibrate and
            not _phase07_contract_files_unchanged(
                contract_path, scene_digest, sound_contract_path, sound_digest)):
        identities_ok = False
    if "control" in runs.get("right", {}):
        neutral = runs["right"]["control"]
        runs["scene"] = {"status": "complete", "t0": neutral[0], "endpoint": neutral[-1]}
    temporal_ok = identities_ok and _active_frontend_temporal_bounds_valid(schedule, invocations)
    outcomes = _evaluate_active_frontend_pairs(
        evaluation_contract, runs, invocations, sources, configuration_identity)
    if not identities_ok or not temporal_ok:
        outcomes = unknown
    sound_outcomes = _phase07_calibration_outcomes(
        audio_controls.get("recordings", {}), outcomes,
        sound_contract.get("thresholds", PHASE07_SOUND_THRESHOLDS) if isinstance(sound_contract, dict)
        else PHASE07_SOUND_THRESHOLDS)
    report = {"status": "complete" if identities_ok else "incomplete", "sources": sources,
              "composition_policy": FRONTEND_COMPOSITION_POLICY,
              "native_contract_identity": _active_frontend_native_identity(contract),
              "frontend_schedule_identity": active_scene_configuration_identity(schedule),
              "temporal_alignment": "pass" if temporal_ok else "unknown",
              "app_identity": app_identity, "configuration_identity": configuration_identity,
              "media_identity": contract["media_identity"], "contract_identity": contract["contract_identity"],
              "sound_contract_identity": (sound_contract.get("contract_identity")
                                           if isinstance(sound_contract, dict) else None),
              "sound_contract_sha256": sound_digest,
              "predicates": outcomes, "invocations": invocations,
              "audio_trace": audio_trace, "audio_controls": audio_controls,
              "sound_outcomes": sound_outcomes}
    written = write_report(report_directory / "frontend-report.json", report)
    if calibrate and written:
        contract["frontend"] = {"frozen": False, "sources": sources,
                                "composition_policy": FRONTEND_COMPOSITION_POLICY,
                                "schedule_policy": "same_controls_bounded_retiming_v1",
                                "native_schedule_identity": active_scene_configuration_identity(contract["schedule"]),
                                "app_identity": app_identity, "configuration_identity": configuration_identity,
                                "schedule": schedule, "calibration_report": str(report_directory / "frontend-report.json"),
                                "calibration_report_sha256": _sha256_path(report_directory / "frontend-report.json"),
                                "calibration_outcome": "captures_ready" if temporal_ok and outcomes["overall"] == "pass" else "incomplete"}
        contract.pop("contract_identity", None)
        contract["contract_identity"] = hashlib.sha256(json.dumps(
            contract, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        written = _write_active_scene_contract(contract_path, contract, report_directory)
    return {"status": ("active_scene_frontend_calibration_recorded" if calibrate else
                       "active_scene_frontend_recorded") if written and identities_ok and (not calibrate or temporal_ok) else
                      "active_scene_frontend_incomplete",
            "private_identity_recorded": written and identities_ok,
            "predicate_results": outcomes, "sound_outcomes": sound_outcomes,
            "audio_evidence": {key: audio_trace.get(key) for key in
                               ("status", "capture_status", "route_status", "audibility",
                                "recognizable_sound")}}


def run_selected_acceptance(input_root: Path,
                            importer: str | Path | list[str] | None,
                            *,
                            retroarch_app: Path,
                            capture_dir: Path,
                            frame_output_path: Path | None = None,
                            frontend_timeout: float = 30.0,
                            freshness=ensure_fresh_qualifier,
                            execute=subprocess.run) -> dict[str, object]:
    """Run selected import, native guest, and actual pinned frontend checks."""
    if frontend_timeout <= 0 or frontend_timeout > 120:
        outcomes = evaluate_acceptance_predicates(
            selected_import_ok=None, native_result=None,
            frontend_result=None, identity_ok=None)
        return {"status": "native_qualification_failed", "acceptance": outcomes}

    try:
        pairs_before = find_pairs(input_root) if input_root.is_dir() else []
    except OSError:
        pairs_before = []
    pair_before = pairs_before[0] if len(pairs_before) == 1 else None
    source_before = ([identity for path in pair_before
                      if (identity := _file_identity(path)) is not None]
                     if pair_before is not None else [])
    private: dict[str, object] = {
        "input_archive_identities_before": source_before,
        "frontend_requested": True,
        "app_configuration_source": "installed-default-or-explicit-local-path",
    }
    selected_import_ok: bool | None = None
    identity_ok: bool | None = None
    frontend_result: dict[str, object] | None = None
    smoke_module = None
    normalized_identity: dict[str, object] | None = None
    source_after_import: list[dict[str, object]] = []

    def record_import(normalized: Path, pair: tuple[Path, Path],
                      importer_command: str, importer_identity,
                      qualifier_identity) -> None:
        nonlocal selected_import_ok, normalized_identity, source_after_import
        nonlocal smoke_module
        try:
            smoke_module = _load_retroarch_smoke()
        except (ImportError, OSError):
            selected_import_ok = False
            private["bundle_validator"] = "unavailable"
            return
        normalized_identity = _file_identity(normalized)
        source_after_import = [identity for path in pair
                              if (identity := _file_identity(path)) is not None]
        sources_unchanged = (
            len(source_before) == 2 and source_after_import == source_before and
            [path.resolve().as_posix() for path in pair] ==
            [row["path"] for row in source_before]
        )
        bundle_ok = _selected_v3_bundle_has_zoom_role(normalized, smoke_module)
        selected_import_ok = bool(bundle_ok and sources_unchanged)
        private.update({
            "selected_input_paths": [path.resolve().as_posix() for path in pair],
            "input_archive_identities_after_import": source_after_import,
            "normalized_bundle_identity": normalized_identity,
            "normalized_bundle_version": 3 if bundle_ok else "unverified",
            "bundle_has_required_zoom_role": bundle_ok,
            "importer_identity": importer_identity,
            "qualifier_identity": qualifier_identity,
            "importer_command": [importer_command, "--selected",
                                 pair[0].resolve().as_posix(),
                                 pair[1].resolve().as_posix(),
                                 normalized.resolve().as_posix()],
        })

    def run_frontend(native_result: dict[str, object], normalized: Path,
                     pair: tuple[Path, Path], importer_command: str,
                     native_command: list[str], importer_identity,
                     qualifier_identity) -> dict[str, object]:
        nonlocal identity_ok, frontend_result, selected_import_ok
        core_identity = _build_frontend_core()
        if core_identity is None:
            frontend_result = {"actual_frontend": "unknown",
                               "recognizable_title": "unknown"}
            private["frontend_build"] = "unknown"
            return native_result
        private["frontend_core_identity"] = core_identity
        private["native_command"] = native_command
        if not private_capture_directory_is_safe(capture_dir):
            frontend_result = {"actual_frontend": "unknown",
                               "recognizable_title": "unknown"}
            identity_ok = False
            private["frontend_result"] = "capture_destination_rejected"
            return native_result
        try:
            smoke_module = _load_retroarch_smoke()
            args = argparse.Namespace(
                retroarch=retroarch_app, core=Path(core_identity["path"]),
                content=normalized, timeout=frontend_timeout,
                child_pid_file=None, acceptance=True, capture_dir=capture_dir,
            )
            actual = smoke_module.run_smoke(args)
        except Exception as error:
            stage = getattr(error, "stage", "unknown")
            stage = stage if stage in {
                "identity", "input", "pre-launch", "launch", "video",
                "unload", "first-screenshot", "pid-record", "unknown",
            } else "unknown"
            frontend_result = {"actual_frontend": "unknown",
                               "recognizable_title": "unknown"}
            identity_ok = False if stage in {"identity", "input"} else None
            private["frontend_failure_stage"] = stage
            private["frontend_failure_type"] = type(error).__name__
            private["frontend_failure_return_code"] = _frontend_failure_return_code(error)
            failure_diagnostic = _private_frontend_failure_diagnostic(
                error, capture_dir)
            if failure_diagnostic is not None:
                private["frontend_failure_diagnostic"] = failure_diagnostic
            actual = None
        if actual is None:
            return native_result

        outcomes = actual.get("acceptance")
        frontend_result = {
            "actual_frontend": (outcomes.get("actual_frontend")
                                if isinstance(outcomes, dict) else "unknown"),
            "recognizable_title": (outcomes.get("recognizable_title")
                                   if isinstance(outcomes, dict) else "unknown"),
        }
        smoke_private = actual.get("private_evidence")
        private["frontend_smoke"] = smoke_private if isinstance(smoke_private, dict) else {}
        private["frontend_result"] = {
            **frontend_result, "reported_status": actual.get("status", "unknown")}
        private["frontend_command"] = (
            smoke_private.get("frontend_command", [])
            if isinstance(smoke_private, dict) else [])
        private["native_command"] = native_command
        private["importer_command"] = [
            importer_command, "--selected", pair[0].resolve().as_posix(),
            pair[1].resolve().as_posix(), normalized.resolve().as_posix(),
        ]
        source_after_frontend = [identity for path in pair
                                 if (identity := _file_identity(path)) is not None]
        private["input_archive_identities_after_frontend"] = source_after_frontend
        if (source_after_frontend != source_before or
                selected_import_ok is not True):
            selected_import_ok = False
        app_identity = actual.get("identity")
        config_text = (smoke_private.get("configuration_text")
                       if isinstance(smoke_private, dict) else None)
        capture_paths = (smoke_private.get("capture_paths", [])
                         if isinstance(smoke_private, dict) else [])
        capture_hashes = (smoke_private.get("capture_sha256", [])
                          if isinstance(smoke_private, dict) else [])
        capture_geometry = (smoke_private.get("capture_geometry", [])
                            if isinstance(smoke_private, dict) else [])
        config_hash = (hashlib.sha256(config_text.encode("utf-8")).hexdigest()
                       if isinstance(config_text, str) else None)
        identity_ok = bool(
            selected_import_ok is True and normalized_identity is not None and
            source_after_frontend == source_before and
            isinstance(app_identity, dict) and
            app_identity.get("retroarch_version") == smoke_module.EXPECTED_VERSION and
            app_identity.get("retroarch_executable_sha256") ==
            smoke_module.EXPECTED_EXECUTABLE_SHA256 and
            app_identity.get("content_kind") == "selected-mvs" and
            app_identity.get("core_sha256") == core_identity["sha256"] and
            isinstance(smoke_private, dict) and
            smoke_private.get("selected_bundle_sha256") == normalized_identity["sha256"] and
            isinstance(config_text, str) and
            config_hash == smoke_private.get("configuration_sha256") and
            "video_driver = \"gl\"" in config_text and
            len(capture_paths) > 0 and len(capture_paths) ==
            len(capture_hashes) == len(capture_geometry) and
            all(geometry == [smoke_module.WIDTH, smoke_module.HEIGHT]
                for geometry in capture_geometry) and
            isinstance(importer_identity, dict) and
            importer_identity.get("scope") == "production" and
            isinstance(qualifier_identity, dict) and
            qualifier_identity.get("scope") == "production"
        )
        return native_result

    result = run_selected_qualification(
        input_root, importer, freshness=freshness, execute=execute,
        frame_output_path=frame_output_path,
        video_advance_frames=MAX_VIDEO_ADVANCE_FRAMES,
        import_callback=record_import, frontend_callback=run_frontend)
    if selected_import_ok is None and result.get("status") in {
            "private_media_unavailable", "no_supported_role_bundle_archive",
            "ambiguous_private_media_inputs", "selected_media_import_timeout",
            "selected_media_import_interrupted", "selected_media_import_failed"}:
        selected_import_ok = False
    outcomes = evaluate_acceptance_predicates(
        selected_import_ok=selected_import_ok,
        native_result=result,
        frontend_result=frontend_result,
        identity_ok=identity_ok,
    )
    private["acceptance_predicates"] = outcomes
    private["input_archive_identities_after_run"] = (
        [_file_identity(path) for path in pair_before]
        if pair_before is not None else [])
    return {**result, "acceptance": outcomes, "private_evidence": private}


# Local-only derived controls: name -> class token the importer must report.
# Only these tokens, never paths, member names or digests, reach the report.
NEGATIVE_EXPECTED = {
    "bios_absent": "missing_input",
    "game_member_removed": "unsupported_set",
    "bios_member_zeroed": "bios_incompatible",
    "bios_payload_flipped": "decompress_failed",
    "game_oversized": "limit_exceeded",
    "game_directory_truncated": "malformed",
}


def _rebuild_archive(source: Path, target: Path, *, drop: str | None = None,
                     zero: str | None = None) -> None:
    """Rewrite a ZIP as stored members, dropping or zero-filling one member."""
    with zipfile.ZipFile(source) as original, \
            zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED,
                            allowZip64=False) as rebuilt:
        for item in original.infolist():
            if item.filename == drop:
                continue
            payload = bytes(item.file_size) if item.filename == zero else original.read(item)
            rebuilt.writestr(item.filename, payload)


def _flip_member_payload(source: Path, target: Path, member: str) -> None:
    """Copy a ZIP and flip one low bit in the first stored/compressed payload byte."""
    shutil.copyfile(source, target)
    with zipfile.ZipFile(source) as archive:
        info = archive.getinfo(member)
    with open(target, "r+b") as handle:
        handle.seek(info.header_offset + 26)
        name_length, extra_length = struct.unpack("<HH", handle.read(4))
        payload = info.header_offset + 30 + name_length + extra_length
        handle.seek(payload)
        first = handle.read(1)
        handle.seek(payload)
        handle.write(bytes([first[0] ^ 1]))


def _run_import(importer: list[str], game: Path, bios: Path, output: Path,
                identity_check=None) -> str:
    """Run the selected importer once; return a class token, never its output."""
    if identity_check is not None and not identity_check():
        raise ImporterIdentityChanged
    try:
        result = subprocess.run([*importer, "--selected", str(game), str(bios), str(output)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                check=False, timeout=IMPORT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return "import_timeout"
    except KeyboardInterrupt:
        return "import_interrupted"
    except OSError:
        return "importer_unavailable"
    produced = output.exists() or any(output.parent.glob(output.name + ".tmp-*"))
    for stray in [output, *output.parent.glob(output.name + ".tmp-*")]:
        stray.unlink(missing_ok=True)
    if result.returncode == 0:
        return "imported"
    return "partial_output" if produced else import_error_class(result.returncode)


def run_negative_controls(importer: list[str], game: Path, bios: Path,
                          workdir: Path, identity_check=None) -> tuple[dict[str, str], bool]:
    """Import the selected pair, then derive and classify each local control.

    Derived copies live only in `workdir`, are removed after their control and
    never alter the originals. Returns (token report, every expectation met).
    """
    report: dict[str, str] = {}
    output = workdir / "control.gnmv"
    positive = _run_import(importer, game, bios, output, identity_check)
    report["positive_import"] = positive
    ok = positive == "imported"
    if positive in {"import_timeout", "import_interrupted"}:
        return report, False
    def absent_bios(target: Path) -> tuple[Path, Path]:
        return game, target  # never created: a nonexistent BIOS path

    def member_removed(target: Path) -> tuple[Path, Path]:
        _rebuild_archive(game, target, drop="250-m1.m1")
        return target, bios

    def bios_zeroed(target: Path) -> tuple[Path, Path]:
        _rebuild_archive(bios, target, zero=BIOS_IDENTITY[0])
        return game, target

    def bios_flipped(target: Path) -> tuple[Path, Path]:
        _flip_member_payload(bios, target, BIOS_IDENTITY[0])
        return game, target

    def oversized(target: Path) -> tuple[Path, Path]:
        shutil.copyfile(game, target)
        os.truncate(target, MAX_ARCHIVE_BYTES + 1)
        return target, bios

    def directory_truncated(target: Path) -> tuple[Path, Path]:
        shutil.copyfile(game, target)
        os.truncate(target, game.stat().st_size - 4)
        return target, bios

    controls = {
        "bios_absent": absent_bios,
        "game_member_removed": member_removed,
        "bios_member_zeroed": bios_zeroed,
        "bios_payload_flipped": bios_flipped,
        "game_oversized": oversized,
        "game_directory_truncated": directory_truncated,
    }
    for name, derive in controls.items():
        derived = workdir / (name + ".zip")
        try:
            pair = derive(derived)
            token = _run_import(importer, pair[0], pair[1], output, identity_check)
        except (OSError, zipfile.BadZipFile, KeyError, struct.error):
            token = "derivation_failed"
        finally:
            derived.unlink(missing_ok=True)
        report[name] = token
        ok = ok and token == NEGATIVE_EXPECTED[name]
        if token in {"import_timeout", "import_interrupted"}:
            break
    return report, ok


def find_pairs(input_root: Path) -> list[tuple[Path, Path]]:
    """Return every (game, BIOS) pair that is identified and fits import limits."""
    archives = [path for path in input_root.iterdir()
                if path.is_file() and not path.is_symlink() and
                path.suffix.lower() == ".zip"]
    games = [path for path in archives if identify_archive(path) == "game"]
    bioses = [path for path in archives if identify_archive(path) == "bios"]
    expanded_sizes = {path: archive_expanded_size(path) for path in games + bioses}
    return [(game, bios) for game in games for bios in bioses
            if game != bios and pair_fits_import_limits(
                game.stat().st_size, bios.stat().st_size,
                expanded_sizes[game], expanded_sizes[bios])]


def write_report(report_path: Path, result: dict[str, object]) -> bool:
    temporary_report: Path | None = None
    try:
        payload = (json.dumps(result, sort_keys=True) + "\n").encode("utf-8")
        if len(payload) > QUALIFICATION_REPORT_MAX_BYTES:
            print("local qualification report exceeded the output limit")
            return False
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=report_path.parent,
                prefix=".phase05-", suffix=".tmp", delete=False) as handle:
            temporary_report = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # The same-directory hard link publishes complete contents atomically
        # and fails if the destination exists, preserving earlier diagnostics.
        os.link(temporary_report, report_path)
        temporary_report.unlink()
    except (OSError, TypeError, ValueError):
        if temporary_report is not None:
            temporary_report.unlink(missing_ok=True)
        print("local qualification report could not be written")
        return False
    return True


def negative_controls_main(input_root: Path, importer: str | Path | list[str] | None,
                          freshness=ensure_fresh_qualifier) -> int:
    report_path = invocation_report_path(NEGATIVE_REPORT)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not ignored(report_path):
        print("local qualification paths must be Git-ignored")
        return 2
    result: dict[str, object]
    ok = False
    freshness_result = freshness()
    qualifier_build = str(freshness_result)
    importer_identity = getattr(freshness_result, "importer_identity", None)
    if qualifier_build != "fresh":
        if qualifier_build == "unchecked":
            result = {
                "status": "importer_identity_rejected",
                "qualifier_build": qualifier_build,
                "retroarch_observation": "manual-only-unknown",
                "private_identity_recorded": False,
            }
        else:
            result = {
                "status": ("qualifier_build_failed" if qualifier_build == "build_failed"
                           else "qualifier_stale"),
                "qualifier_build": qualifier_build,
                "retroarch_observation": "manual-only-unknown",
                "private_identity_recorded": False,
            }
    elif (importer_command := checked_importer_command(
            importer, identity=importer_identity)) is None:
        qualifier_build = "unchecked"
        result = {
            "status": "importer_identity_rejected",
            "qualifier_build": qualifier_build,
            "retroarch_observation": "manual-only-unknown",
            "private_identity_recorded": False,
        }
    elif not input_root.is_dir():
        result = {"positive_import": "private_media_unavailable"}
    else:
        pairs = find_pairs(input_root)
        if len(pairs) == 0:
            result = {"positive_import": "no_supported_pair"}
        elif len(pairs) > 1:
            result = {"positive_import": "ambiguous_pairs"}
        else:
            identity_check = lambda: checked_importer_command(
                importer, identity=importer_identity) == importer_command
            if not identity_check():
                qualifier_build = "unchecked"
                result = {
                    "status": "importer_identity_rejected",
                    "qualifier_build": qualifier_build,
                    "retroarch_observation": "manual-only-unknown",
                    "private_identity_recorded": False,
                }
            else:
                with tempfile.TemporaryDirectory(prefix="glueyneo-negative-",
                                                 dir=report_path.parent) as temporary:
                    try:
                        result, ok = run_negative_controls(
                            [importer_command], pairs[0][0], pairs[0][1],
                            Path(temporary), identity_check=identity_check)
                    except ImporterIdentityChanged:
                        qualifier_build = "unchecked"
                        result = {
                            "status": "importer_identity_rejected",
                            "qualifier_build": qualifier_build,
                            "retroarch_observation": "manual-only-unknown",
                            "private_identity_recorded": False,
                        }
    result["qualifier_build"] = qualifier_build
    if not write_report(report_path, result):
        return 1
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", default="local/roms")
    parser.add_argument("--report", default="local/qualification/phase05.json",
                        help="base name for an invocation-specific private report")
    parser.add_argument("--importer", default=DEFAULT_IMPORTER_ARGUMENT)
    parser.add_argument("--negative-controls", action="store_true",
                        help="derive local-only failing copies of the selected pair "
                             "and report only class tokens")
    parser.add_argument("--check-fresh", action="store_true",
                        help="rebuild selected qualifier targets and check executable identities")
    parser.add_argument("--scripted-start", action="store_true",
                        help="run the bounded documented coin/start input schedule")
    parser.add_argument("--video-advance-frames", type=int, default=0,
                        help="advance at most 600 idle frames after the BIOS entry predicate "
                             "before saving the private local image")
    parser.add_argument("--video-state-diagnostic", action="store_true",
                        help="retain the native guest-video activity diagnostic in the "
                             "ignored local report")
    parser.add_argument("--active-scene", choices=("calibrate", "native", "frontend"),
                        help="calibrate local active-scene captures or validate a frozen contract")
    parser.add_argument("--active-frontend-calibrate", action="store_true",
                        help="record frontend-specific intervals before freezing local acceptance")
    audio_modes = parser.add_mutually_exclusive_group()
    audio_modes.add_argument("--frontend-audio-only", action="store_true",
                        help="foreground audio tracer only; skip the ten-boot visual campaign "
                             "and do not claim full scenario acceptance")
    audio_modes.add_argument("--frontend-audio-controls-only", action="store_true",
                        help="foreground audio control matrix only; skip the ten-boot visual "
                             "campaign and leave full scenario and causal visual outcomes unknown")
    parser.add_argument("--active-frontend-freeze", metavar="PRIVATE_REVIEW",
                        help="freeze frontend calibration from an exact-capture local semantic review")
    parser.add_argument("--active-frame-inputs",
                        help="bounded comma-separated active frame input schedule used during calibration")
    parser.add_argument("--active-capture-frames", type=_parse_calibration_capture_frames,
                        help="six ascending comma-separated calibration checkpoint indices")
    parser.add_argument("--scene-contract",
                        help="canonical ignored local Phase 06 contract path")
    parser.add_argument("--sound-contract",
                        help="canonical ignored local Phase 07 sound contract path")
    parser.add_argument("--freeze-sound-contract", action="store_true",
                        help="freeze the current sound schedule and causal rules without "
                             "accepting unknown sound outcomes")
    parser.add_argument("--acceptance", action="store_true",
                        help="require independent selected import, guest, frontend and title outcomes")
    parser.add_argument("--frontend", action="store_true",
                        help="launch the installed pinned RetroArch app with the selected bundle")
    parser.add_argument("--frontend-timeout", type=float, default=30.0,
                        help=argparse.SUPPRESS)
    parser.add_argument("--record-title-review", metavar="PRIVATE_EVIDENCE",
                        help="record a direct visual title review for one ignored run report")
    parser.add_argument("--title-review-outcome", choices=("pass", "fail"))
    parser.add_argument("--user-live-corroboration", action="store_true",
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if ((args.frontend_audio_only or args.frontend_audio_controls_only) and (args.active_scene != "frontend" or
            args.sound_contract is None or args.active_frontend_calibrate or args.active_frontend_freeze)):
        parser.error("frontend audio modes require frontend acceptance and its frozen sound contract")
    if ((args.active_frontend_calibrate or args.active_frontend_freeze) and args.active_scene != "frontend" or
            args.active_frontend_calibrate and args.active_frontend_freeze):
        parser.error("frontend calibration/freeze requires frontend mode and mutually exclusive flags")
    if (args.active_scene is None) != (args.scene_contract is None):
        parser.error("--active-scene and --scene-contract must be used together")
    if (args.sound_contract is not None and
            (args.active_scene not in ("calibrate", "native", "frontend") or
             args.sound_contract != PHASE07_SOUND_CONTRACT_PATH.as_posix())):
        parser.error("--sound-contract requires active-scene calibrate/native/frontend and the "
                     "canonical Phase 07 path")
    if (args.active_scene == "frontend" and not args.active_frontend_calibrate and
            not args.active_frontend_freeze and args.sound_contract is None):
        parser.error("active-scene frontend acceptance requires the frozen --sound-contract")
    if (args.freeze_sound_contract and
            (args.active_scene != "calibrate" or args.sound_contract is None or
             args.active_frame_inputs is not None or
             args.active_capture_frames is not None)):
        parser.error("--freeze-sound-contract requires active-scene calibrate and "
                     "the canonical --sound-contract path without capture options")
    if args.active_scene is None and args.active_frame_inputs is not None:
        parser.error("--active-frame-inputs requires --active-scene calibrate")
    if args.active_capture_frames is not None and args.active_scene != "calibrate":
        parser.error("--active-capture-frames requires --active-scene calibrate")
    if (args.video_advance_frames < 0 or
            args.video_advance_frames > MAX_VIDEO_ADVANCE_FRAMES or
            (args.scripted_start and args.video_advance_frames != 0)):
        parser.error("video frame advance must be 0-600 and cannot combine with --scripted-start")
    if args.video_state_diagnostic and (args.check_fresh or args.negative_controls):
        parser.error("video state diagnostic applies only to selected qualification")
    if args.acceptance != args.frontend:
        parser.error("--acceptance and --frontend must be used together")
    if args.acceptance and (
            args.check_fresh or args.negative_controls or args.scripted_start or
            args.video_advance_frames or args.video_state_diagnostic):
        parser.error("selected acceptance uses its own bounded native and frontend schedule")
    if args.frontend_timeout <= 0 or args.frontend_timeout > 120:
        parser.error("frontend timeout must be greater than 0 and at most 120 seconds")
    review_requested = args.record_title_review is not None
    if (review_requested != (args.title_review_outcome is not None) or
            (not review_requested and args.user_live_corroboration)):
        parser.error("title review needs --record-title-review and --title-review-outcome")
    if review_requested and (
            args.check_fresh or args.negative_controls or args.acceptance or
            args.frontend or args.scripted_start or args.video_advance_frames or
            args.video_state_diagnostic):
        parser.error("title review operates only on a completed private acceptance report")

    if args.active_scene is not None:
        if (args.check_fresh or args.negative_controls or args.acceptance or
                args.frontend or args.scripted_start or args.video_advance_frames or
                args.video_state_diagnostic or review_requested or
                (args.active_frame_inputs is not None and
                 args.active_scene != "calibrate") or
                args.input_root != "local/roms" or
                args.scene_contract != PHASE06_CONTRACT_PATH.as_posix()):
            parser.error("active-scene mode accepts only the private default input root "
                         "and canonical Phase 06 contract path")
        if args.active_scene == "calibrate":
            if args.freeze_sound_contract:
                result = freeze_phase07_sound_contract(
                    Path(args.input_root), Path(args.scene_contract),
                    Path(args.sound_contract))
                print(json.dumps(result, sort_keys=True))
                return 0 if result.get("status") == \
                    "active_scene_sound_contract_frozen" else 1
            capture_options = ({} if args.active_capture_frames is None else
                               {"capture_frames": args.active_capture_frames})
            sound_options = ({} if args.sound_contract is None else
                             {"sound_contract_path": Path(args.sound_contract)})
            result = calibrate_active_scene(
                Path(args.input_root), args.importer,
                Path(args.scene_contract), frame_inputs=args.active_frame_inputs,
                **capture_options, **sound_options)
            print(json.dumps(result, sort_keys=True))
            if args.sound_contract is not None:
                return (0 if result.get("status") ==
                        "active_scene_sound_calibration_recorded" and
                        result.get("calibration_outcome") == "windows_ready" else 1)
            return (0 if result.get("status") == "active_scene_calibration_recorded" and
                    result.get("calibration_outcome") == "captures_ready" else 1)
        if args.active_scene == "native":
            sound_options = ({} if args.sound_contract is None else
                             {"sound_contract_path": Path(args.sound_contract)})
            result = run_active_scene(
                Path(args.input_root), args.importer, Path(args.scene_contract),
                **sound_options)
            print(json.dumps(result, sort_keys=True))
            predicates = result.get("predicate_results")
            sound_outcomes = result.get("sound_outcomes")
            sound_ok = (args.sound_contract is None or
                        (isinstance(sound_outcomes, dict) and
                         sound_outcomes.get("overall") == "pass"))
            return (0 if result.get("status") == "active_scene_native_recorded" and
                    result.get("private_identity_recorded") is True and
                    isinstance(predicates, dict) and predicates.get("overall") == "pass" and
                    sound_ok
                    else 1)
        options = {"calibrate": True} if args.active_frontend_calibrate else {}
        if args.sound_contract is not None and not args.active_frontend_freeze:
            options["sound_contract_path"] = Path(args.sound_contract)
        if args.frontend_audio_only:
            options["audio_only"] = True
        if args.frontend_audio_controls_only:
            options["audio_controls_only"] = True
        if args.active_frontend_freeze:
            result = freeze_active_scene_frontend(Path(args.scene_contract), Path(args.active_frontend_freeze))
            print(json.dumps(result, sort_keys=True))
            return 0 if result.get("status") == "active_scene_frontend_contract_frozen" else 1
        result = run_active_scene_frontend(
            Path(args.input_root), args.importer, Path(args.scene_contract), **options)
        print(json.dumps(result, sort_keys=True))
        predicates = result.get("predicate_results")
        if args.frontend_audio_only:
            success = (result.get("status") == "active_scene_frontend_audio_recorded" and
                       result.get("private_identity_recorded") is True and
                       isinstance(result.get("audio_evidence"), dict) and
                       result["audio_evidence"].get("status") == "pass")
        elif args.frontend_audio_controls_only:
            success = (result.get("status") == "active_scene_frontend_audio_controls_recorded" and
                       result.get("private_identity_recorded") is True and
                       isinstance(result.get("audio_evidence"), dict) and
                       result["audio_evidence"].get("status") == "pass" and
                       result["audio_evidence"].get("controls_status") == "pass")
        elif args.active_frontend_calibrate:
            success = (result.get("status") == "active_scene_frontend_calibration_recorded" and
                       result.get("private_identity_recorded") is True and
                       isinstance(predicates, dict) and predicates.get("overall") == "pass")
        else:
            success = (result.get("status") == "active_scene_frontend_recorded" and
                       result.get("private_identity_recorded") is True and
                       isinstance(predicates, dict) and predicates.get("overall") == "pass" and
                       isinstance(result.get("audio_evidence"), dict) and
                       result["audio_evidence"].get("status") == "pass" and
                       isinstance(result.get("sound_outcomes"), dict) and
                       result["sound_outcomes"].get("overall") == "pass")
        return 0 if success else 1

    if args.check_fresh:
        importer_command = _canonical_importer_command(args.importer)
        if importer_command is None:
            print("importer_identity_rejected")
            return 1
        fresh = ensure_fresh_qualifier()
        if str(fresh) != "fresh":
            if str(fresh) == "unchecked":
                print("importer_identity_rejected")
                return 1
            print("qualifier stale" if str(fresh) == "stale" else "qualifier_build_failed")
            return 1
        if (checked_importer_command(
                args.importer, identity=getattr(fresh, "importer_identity", None)) !=
                importer_command):
            print("importer_identity_rejected")
            return 1
        if checked_qualifier_command(identity=getattr(fresh, "qualifier_identity", None)) is None:
            print("qualifier stale")
            return 1
        print("qualifier fresh")
        return 0

    input_root = Path(args.input_root)
    report_base = Path(args.report)
    if input_root.as_posix() != "local/roms" or \
            report_base.as_posix() != "local/qualification/phase05.json":
        parser.error("local qualification accepts only the ignored default paths")
    report_path = invocation_report_path(report_base)
    if Path("local").is_symlink() or Path("local/qualification").is_symlink():
        print("local qualification paths must be Git-ignored directories")
        return 2
    report_path.parent.mkdir(parents=True, exist_ok=True)
    frame_output_path = private_frame_path(report_path)
    capture_dir = private_capture_directory(report_path)
    evidence_path = private_evidence_path(report_path)
    if (not ignored(input_root) or not ignored(report_path) or
            not private_frame_path_is_safe(frame_output_path) or
            (args.acceptance and (
                not private_capture_directory_is_safe(capture_dir) or
                not private_evidence_path_is_safe(evidence_path)))):
        print("local qualification paths must be Git-ignored")
        return 2
    if review_requested:
        result = record_manual_visual_title_review(
            Path(args.record_title_review), outcome=args.title_review_outcome,
            user_live_corroboration=args.user_live_corroboration)
        outcomes = (result.get("reviewed_acceptance")
                    if isinstance(result, dict) else None)
        print(json.dumps(
            result if isinstance(result, dict) else {
                "status": "title_review_unknown",
                "review_recorded": False,
            }, sort_keys=True))
        return 0 if isinstance(outcomes, dict) and outcomes.get("overall") == "pass" else 1
    if args.negative_controls:
        return negative_controls_main(input_root, args.importer)
    if args.acceptance:
        result = run_selected_acceptance(
            input_root, args.importer,
            retroarch_app=Path("/Applications/RetroArch.app"),
            capture_dir=capture_dir, frame_output_path=frame_output_path,
            frontend_timeout=args.frontend_timeout,
        )
        outcomes = safe_acceptance(result.get("acceptance"))
        private_evidence = result.pop("private_evidence", None)
        private_written = (
            isinstance(private_evidence, dict) and
            write_report(evidence_path, private_evidence))
        if outcomes is None:
            outcomes = evaluate_acceptance_predicates(
                selected_import_ok=None, native_result=None,
                frontend_result=None, identity_ok=None)
        if not private_written:
            predicate_states = {key: outcomes[key]
                                for key in ACCEPTANCE_PREDICATES}
            predicate_states["identity"] = "fail"
            outcomes = {**predicate_states,
                        "overall": _acceptance_overall(predicate_states)}
        projected = public_result(result, acceptance=outcomes)
        projected["private_identity_recorded"] = private_written
        print(json.dumps(projected, sort_keys=True))
        if not write_report(report_path, projected):
            return 1
        return 0 if outcomes["overall"] == "pass" else 1

    if args.scripted_start:
        result = run_selected_qualification(input_root, args.importer,
                                            scripted_start=True,
                                            frame_output_path=frame_output_path,
                                            video_state_diagnostic=args.video_state_diagnostic)
    else:
        result = run_selected_qualification(input_root, args.importer,
                                            frame_output_path=frame_output_path,
                                            video_advance_frames=args.video_advance_frames,
                                            video_state_diagnostic=args.video_state_diagnostic)

    if not write_report(report_path, result):
        return 1
    return 0 if (result.get("status") == "attract_start" and
                 result.get("guest_executed") is True and
                 (not args.scripted_start or
                  result.get("input_response") == "observed")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
