#!/usr/bin/env python3
"""Run bounded, private MVS import/guest qualification without logging identity."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import struct
import tempfile
import zipfile


MAX_ARCHIVE_BYTES = 96 * 1024 * 1024
MAX_COMBINED_BYTES = 128 * 1024 * 1024
MAX_ENTRY_BYTES = 8 * 1024 * 1024
IMPORT_COMBINED_ARCHIVE_BYTES = 128 * 1024 * 1024
IMPORT_COMBINED_EXPANDED_BYTES = 128 * 1024 * 1024
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
BIOS_IDENTITY = ("sp-s2.sp1", 0x20000, 0x9036d879,
                 "4f5ed7105b7128794654ce82b51723e16e389543")
SAFE_RUNNER_STATUSES = frozenset({
    "mvs_bus_access_fault", "native_execution_error",
    "unsupported_guest_event", "guest_stopped",
    "guest_instruction_budget_exhausted",
})

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


def safe_result(report: dict[str, object]) -> dict[str, object]:
    status = report.get("status")
    if not isinstance(status, str) or status not in SAFE_RUNNER_STATUSES:
        return {"status": "native_qualification_failed",
                "retroarch_observation": "manual-only-unknown",
                "private_identity_recorded": False}
    clean: dict[str, object] = {
        "status": status,
        "retroarch_observation": "manual-only-unknown",
        "private_identity_recorded": False,
    }
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", default="local/roms")
    parser.add_argument("--report", default="local/qualification/phase05.json")
    parser.add_argument("--importer", default="build/sdk-debug/mvs_importer")
    args = parser.parse_args()

    input_root = Path(args.input_root)
    report_path = Path(args.report)
    if input_root.as_posix() != "local/roms" or \
            report_path.as_posix() != "local/qualification/phase05.json":
        parser.error("local qualification accepts only the ignored default paths")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not ignored(input_root) or not ignored(report_path):
        print("local qualification paths must be Git-ignored")
        return 2

    if not input_root.is_dir():
        result = {"status": "private_media_unavailable",
                  "retroarch_observation": "manual-only-unknown",
                  "private_identity_recorded": False}
    else:
        archives = [path for path in input_root.iterdir()
                    if path.is_file() and not path.is_symlink() and
                    path.suffix.lower() == ".zip"]
        games = [path for path in archives if identify_archive(path) == "game"]
        bioses = [path for path in archives if identify_archive(path) == "bios"]
        expanded_sizes = {path: archive_expanded_size(path) for path in games + bioses}
        pairs = [(game, bios) for game in games for bios in bioses
                 if game != bios and pair_fits_import_limits(
                     game.stat().st_size, bios.stat().st_size,
                     expanded_sizes[game], expanded_sizes[bios])]
        runner_report: dict[str, object] | None = None
        if len(pairs) == 1:
            with tempfile.TemporaryDirectory(prefix="glueyneo-mvs-") as temporary:
                normalized = Path(temporary) / "normalized.gnmv"
                imported_result = subprocess.run(
                    [args.importer, "--selected", str(pairs[0][0]),
                     str(pairs[0][1]), str(normalized)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False,
                )
                if imported_result.returncode == 0:
                    execution = subprocess.run(["build/sdk-debug/mvs_qualify",
                                                str(normalized)],
                                               capture_output=True, text=True,
                                               check=False)
                    try:
                        decoded = json.loads(execution.stdout)
                        runner_report = safe_result(decoded)
                    except (json.JSONDecodeError, TypeError):
                        runner_report = {"status": "native_qualification_failed"}
                else:
                    runner_report = {"status": "selected_media_import_failed",
                                     "retroarch_observation": "manual-only-unknown",
                                     "private_identity_recorded": False}
        if len(pairs) == 0:
            result = {"status": "no_supported_role_bundle_archive",
                      "retroarch_observation": "manual-only-unknown",
                      "private_identity_recorded": False,
                      "first_blocking_checkpoint": "archive_to_region_mapping",
                      "next_technical_dependency": "select and map the supported game and BIOS archives"}
        elif len(pairs) > 1:
            result = {"status": "ambiguous_private_media_inputs",
                      "retroarch_observation": "manual-only-unknown",
                      "private_identity_recorded": False}
        else:
            result = runner_report or {"status": "native_qualification_failed",
                                       "retroarch_observation": "manual-only-unknown",
                                       "private_identity_recorded": False}

    temporary_report: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=report_path.parent,
                prefix=".phase05-", suffix=".tmp", delete=False) as handle:
            temporary_report = Path(handle.name)
            handle.write(json.dumps(result, sort_keys=True) + "\n")
        os.replace(temporary_report, report_path)
    except OSError:
        if temporary_report is not None:
            temporary_report.unlink(missing_ok=True)
        print("local qualification report could not be written")
        return 1
    return 0 if result.get("status") == "attract_start" and result.get("guest_executed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
