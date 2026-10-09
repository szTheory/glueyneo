#!/usr/bin/env python3
"""Run bounded, private MVS import/guest qualification without logging identity."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


MAX_ARCHIVE_BYTES = 96 * 1024 * 1024
MAX_COMBINED_BYTES = 128 * 1024 * 1024
MAX_ENTRY_BYTES = 8 * 1024 * 1024
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
BIOS_IDENTITY = ("sp-s2.sp1", 0x20000, 0x9036d879,
                 "4f5ed7105b7128794654ce82b51723e16e389543")
BIOS_CATALOG = {
    "sp-s2.sp1", "sp-s.sp1", "sp-45.sp1", "sp-s3.sp1", "sp-u2.sp1",
    "sp-e.sp1", "sp1-u2", "sp1-u4.bin", "sp1-u3.bin", "vs-bios.rom",
    "sp-j2.sp1", "sp1.jipan.1024", "japan-j3.bin", "sp1-j3.bin",
    "sp-j3.sp1", "sp-1v1_3db8c.bin", "sp-1v2_2db8c.bin",
    "sp-1v2_2db8c-bios.bin", "sp-1v3_2db8c.bin", "sp-1v4_2db8c.bin",
    "sp-1v4_2db8c-fix.bin", "sp-1v5_2db8c.bin", "sp-1v5_2db8c-fix.bin",
    "sp-1v6_2db8c.bin", "sp-1v7_2db8c.bin", "sp-1v8_2db8c.bin",
    "sm1.sm1", "sp-1v1.bin",
}


def identify_archive(path: Path) -> str | None:
    """Classify a bounded ZIP by public content while keeping local values private."""
    try:
        if path.stat().st_size > MAX_ARCHIVE_BYTES:
            return None
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > 64 or sum(item.file_size for item in entries) > MAX_COMBINED_BYTES:
                return None
            names = [item.filename for item in entries]
            if len(set(names)) != len(names) or any(item.file_size > MAX_ENTRY_BYTES for item in entries):
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
            if BIOS_IDENTITY[0] not in names or not set(names).issubset(BIOS_CATALOG):
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
    if not isinstance(status, str):
        return {"status": "qualification_report_invalid"}
    clean: dict[str, object] = {
        "status": status,
        "retroarch_observation": "manual-only-unknown",
        "private_identity_recorded": False,
    }
    if report.get("guest_executed") is True:
        clean["guest_executed"] = True
    event = report.get("first_unsupported_event")
    if isinstance(event, dict):
        pc, opcode = event.get("pc"), event.get("opcode")
        if isinstance(pc, int) and isinstance(opcode, int):
            clean["first_unsupported_event"] = {"pc": pc, "opcode": opcode}
    return clean


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", default="local/roms")
    parser.add_argument("--report", default="local/qualification/phase05.json")
    parser.add_argument("--importer", default="build/sdk-debug/mvs_importer")
    parser.add_argument("--runner", default="build/sdk-debug/mvs_qualify")
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
        pairs = [(game, bios) for game in games for bios in bioses if game != bios]
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
                    execution = subprocess.run([args.runner, str(normalized)],
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
