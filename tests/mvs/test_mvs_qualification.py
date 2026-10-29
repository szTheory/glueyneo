#!/usr/bin/env python3
"""Public synthetic archive checks for the bounded MVS importer."""
from __future__ import annotations

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
import struct
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
import uuid
import warnings
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "libretro"))
from tools.mvs.qualify_local_boot import (
    IMPORT_ERROR_CLASSES, NEGATIVE_EXPECTED, NATIVE_FAILURE_KEYS, _archive_structure_valid,
    active_scene_contract_is_valid, active_scene_native_contract_is_valid,
    active_scene_calibration_evidence_is_valid, active_scene_configuration_identity,
    _active_scene_input_events, _active_schedule_valid, evaluate_active_scene_pairs,
    PHASE06_CALIBRATION_FRAMES, MAX_ACTIVE_FRAMES,
    _central_directory_matches, import_error_class, pair_fits_import_limits,
    public_result, run_negative_controls, safe_result,
)
from retroarch_smoke import is_normalized_mvs_bundle

NAMES = (
    "bios.bin", "program.bin", "fixed.bin", "audio.bin", "samples.bin",
    "sprites.bin",
)
SIZES = (0x80000, 0x500000, 0x20000, 0x20000, 0xA00000, 0x3000000)
AUDIO_BIOS_NAME = "audio-bios.bin"
AUDIO_BIOS_SIZE = 0x20000
Y_ZOOM_NAME = "000-lo.lo"
Y_ZOOM_SIZE = 0x20000

# Test-only member names mirror the pinned MAME mslugx declaration.  These
# fixture identities are intentionally synthetic and never compile into the
# production importer.
GAME_MEMBERS = {
    "250-p1.p1": 0x100000, "250-p2.ep1": 0x400000,
    "250-s1.s1": 0x20000, "250-m1.m1": 0x20000,
    "250-v1.v1": 0x400000, "250-v2.v2": 0x400000,
    "250-v3.v3": 0x200000,
    "250-c1.c1": 0x800000, "250-c2.c2": 0x800000,
    "250-c3.c3": 0x800000, "250-c4.c4": 0x800000,
    "250-c5.c5": 0x800000, "250-c6.c6": 0x800000,
}
BIOS_MEMBER = "sp-s2.sp1"

# Stable `mvs_importer --selected` exit codes and generic messages. These are
# the documented contract in docs/ownership-and-errors.md; the messages never
# contain input-derived text.
IMPORT_EXIT = {
    "malformed": 1, "unsupported_feature": 2, "limit_exceeded": 3,
    "decompress_failed": 5, "memory": 6, "ambiguous": 7,
    "missing_input": 8, "unsupported_set": 9, "bios_missing": 10,
    "bios_incompatible": 11, "output_failed": 12,
    "zoom_incompatible": 13,
}
IMPORT_MESSAGE = {
    "malformed": "malformed ZIP32 media archive",
    "unsupported_feature": "archive uses an unsupported ZIP feature",
    "limit_exceeded": "media exceeds selected profile or resource limits",
    "decompress_failed": "DEFLATE stream, expanded size, or CRC validation failed",
    "memory": "insufficient memory for bounded media import",
    "ambiguous": "archive contains ambiguous MVS region entries",
    "missing_input": "selected media input is missing or unreadable",
    "unsupported_set": "game archive is not the supported game set; supply the supported game archive",
    "bios_missing": "BIOS archive lacks the required BIOS member; supply the Europe MVS v2 BIOS archive",
    "bios_incompatible": "BIOS member does not match the required BIOS; supply the Europe MVS v2 BIOS archive",
    "output_failed": "normalized media could not be published atomically",
    "zoom_incompatible": "board zoom lookup does not match the required MVS data",
}


def swap_pairs(data: bytes) -> bytes:
    """Archive members hold CPU regions with each byte pair swapped."""
    swapped = bytearray(data)
    swapped[0::2], swapped[1::2] = data[1::2], data[0::2]
    return bytes(swapped)


# Synthetic BIOS-to-cartridge handoff (docs/mvs-media.md "Attract/start
# predicate"): BIOS-region code writes the Demo request to BIOS_USER_REQUEST
# ($10FDAE) and calls the USER entry ($000122); cartridge code at the entry
# writes 1 to BIOS_USER_MODE ($10FDAF) and returns. Rights-clear opcodes only.
ATTRACT_BIOS = bytes.fromhex("13fc00020010fdae" "4eb900000122" "4e722700")
ATTRACT_CART = bytes.fromhex("13fc00010010fdaf" "4e75")
ATTRACT_CART_UNSUPPORTED_ZOOM = bytes.fromhex(
    "33fc8000003c0000" "33fc0000003c0002"  # zoom control = 0
    "33fc8200003c0000" "33fc003f003c0002"  # active sprite row count
    "33fc8400003c0000" "33fc0000003c0002"  # visible x position
) + ATTRACT_CART
ATTRACT_VECTORS = bytes.fromhex("0010fffe00c00100")
# BIOS-region spin on one public register (MOVE.W ($3C0000).L,D0; JMP $C00100)
# with interrupts masked, for the budget-exhaustion diagnosis check.
SPIN_BIOS = bytes.fromhex("303900" "3c0000" "4ef900c00100")


def make_split_archives(*, replace_program: bool = False,
                        duplicate_program: bool = False,
                        wrong_bios_member: bool = False,
                        attract_guest: bool = False,
                        attract_loop: bool = False,
                        attract_timeout: bool = False,
                        unsupported_player_start: bool = False,
                        delayed_start_guest: bool = False,
                        delayed_coin_guest: bool = False,
                        active_input_guest: bool = False,
                        unsupported_zoom_guest: bool = False,
                        spin_guest: bool = False,
                        drop_member: str | None = None,
                        oversize_member: str | None = None,
                        zip64_member: str | None = None,
                        malformed_zip64_member: str | None = None,
                        omit_bios_member: bool = False,
                        short_bios: bool = False,
                        bios_extras: tuple[tuple[str, bytes], ...] = ()) -> tuple[bytes, bytes]:
    game, bios = io.BytesIO(), io.BytesIO()
    with zipfile.ZipFile(game, "w", compression=zipfile.ZIP_STORED,
                         allowZip64=False) as archive:
        for index, (name, size) in enumerate(GAME_MEMBERS.items()):
            if name == drop_member:
                continue
            if name == oversize_member:
                size += 1
            if replace_program and name == "250-p1.p1":
                name = "250-p1-wrong.p1"
            payload = bytearray([0x11 + index]) * size
            if name == "250-p1.p1":
                payload[:12] = bytes.fromhex("5a72c13310000000724e0027")
                if attract_guest:
                    attract_cart = (ATTRACT_CART_UNSUPPORTED_ZOOM
                                    if unsupported_zoom_guest else ATTRACT_CART)
                    payload[0x122:0x122 + len(attract_cart)] = swap_pairs(attract_cart)
                if active_input_guest:
                    # A rights-clear P1 guest observes active-low P1 lines,
                    # draws one fixed tile while any line is held, and loops.
                    # Its exact pixels make native schedule/capture checks
                    # independent of commercial media and frontend behavior.
                    active = bytearray.fromhex(
                        "33fc7002003c0000"  # VRAM address = fixed map word 2
                        "33fc1001003c0002")  # tile 1, palette group 1
                    for pen in range(1, 9):
                        address = 0x400000 + (0x10 + pen) * 2
                        active.extend(bytes.fromhex("33fc7fff"))
                        active.extend(struct.pack(">I", address))
                    active.extend(bytes.fromhex("4ef900000160"))  # loop at player entry
                    neutral = bytearray.fromhex(
                        "33fc7002003c0000"  # same fixed map word
                        "33fc0000003c0002"  # clear tile on release
                        "4ef900000160")
                    prefix = bytearray.fromhex(
                        "103900300000"  # MOVE.B ($300000).L,D0
                        "0c0000f7"      # CMPI.B #$f7,D0 (RIGHT asserted)
                        "6600")         # BNE.S neutral
                    prefix[-1] = len(active)
                    entry = prefix + active + neutral
                    if attract_loop:
                        payload[0x128:0x12E] = swap_pairs(
                            bytes.fromhex("4ef900000160"))
                        payload[0x160:0x160 + len(entry)] = swap_pairs(entry)
                    else:
                        payload[0x128:0x128 + len(entry)] = swap_pairs(entry)
                if attract_loop:
                    # Keep the attract handoff entry distinct from the public
                    # PLAYER_START entry at 0x128 used by the progress observer.
                    player_start_entry = bytes.fromhex("4ef900000140")
                    payload[0x122:0x128] = swap_pairs(player_start_entry)
                    if active_input_guest:
                        payload[0x140:0x140 + len(ATTRACT_CART)] = swap_pairs(ATTRACT_CART)
                    else:
                        player_start = (bytes.fromhex("ffff") if unsupported_player_start
                                        else bytes.fromhex("4e75"))
                        payload[0x128:0x12A] = swap_pairs(player_start)
                        payload[0x140:0x140 + len(ATTRACT_CART)] = swap_pairs(ATTRACT_CART)
            if name == "250-s1.s1" and active_input_guest:
                payload[:] = bytes(len(payload))
                payload[0x20 + 0x10] = 0x20
                payload[0x20 + 0x18] = 0x03
                payload[0x20 + 0x00] = 0x05
                payload[0x20 + 0x08] = 0x07
            if name == zip64_member or name == malformed_zip64_member:
                info = zipfile.ZipInfo(name)
                info.extra = struct.pack("<HHQ", 1, 8, 0)  # ZIP64 extended-information field
                if name == malformed_zip64_member:
                    info.extra += b"\x01"  # trailing incomplete extra-field header
                archive.writestr(info, payload)
            else:
                archive.writestr(name, payload)
        if duplicate_program:
            archive.writestr("250-p1.p1", bytes(GAME_MEMBERS["250-p1.p1"]))
    with zipfile.ZipFile(bios, "w", compression=zipfile.ZIP_STORED,
                         allowZip64=False) as archive:
        data = bytearray(0x20000)
        if not wrong_bios_member:
            # Reset vectors and a tiny guest that writes the sentinel and stops.
            data[0:8] = bytes.fromhex("1000feff00000001")
            data[0x100:0x10C] = bytes.fromhex("5a72c13310000000724e0027")
            if attract_guest:
                data[0:8] = swap_pairs(ATTRACT_VECTORS)
                data[0x100:0x100 + len(ATTRACT_BIOS)] = swap_pairs(ATTRACT_BIOS)
                if attract_loop:
                    # Poll coin then Start through their active-low bits;
                    # publish the documented BIOS P1 start indication before
                    # calling PLAYER_START. Entry alone is also a timeout path.
                    repeat_entry = bytes.fromhex(
                        "1039003200010800000066f4"
                        "1039003800000800000066f4"
                        "13fc00010010fdb4"
                        "4eb9000001284e722700")
                    if delayed_start_guest:
                        # Coin is accepted and the BIOS pets the watchdog,
                        # then waits about 2.46 frame budgets before polling
                        # Start. This isolates the held-input behavior.
                        repeat_entry = bytes.fromhex(
                            "1039003200010800000066f4"
                            "705a13c000300001"
                            "7202747f767f"
                            "51cbfffe51cafff851c9fff2"
                            "1039003800000800000066f4"
                            "13fc00010010fdb4"
                            "4eb9000001284e722700")
                    if delayed_coin_guest:
                        # The BIOS polls Coin after a roughly 1.5M-clock wait.
                        # Keep Coin held until the scheduled Start event so
                        # reverting to a one-frame pulse misses this poll.
                        repeat_entry = bytes.fromhex(
                            "7208747f767f"
                            "51cbfffe51cafff8"
                            "705a13c00030000151c9ffea"
                            "1039003200010800000066f4"
                            "705a13c0003000011039003800000800000066ec"
                            "13fc00010010fdb4"
                            "4eb9000001284e722700")
                    if attract_timeout:
                        # Reads observe asserted values but do not control the
                        # transfer: only the DBRA countdown does. No P1 flag.
                        repeat_entry = bytes.fromhex(
                            "343c7fff10390032000110390038000051cafff2"
                            "4eb9000001284e722700")
                    loop_offset = 0x100 + len(ATTRACT_BIOS) - 4
                    data[loop_offset:loop_offset + len(repeat_entry)] = swap_pairs(
                        repeat_entry)
            if spin_guest:
                data[0:8] = swap_pairs(ATTRACT_VECTORS)
                data[0x100:0x100 + len(SPIN_BIOS)] = swap_pairs(SPIN_BIOS)
        if short_bios:
            data = data[:0x10000]
        if not omit_bios_member:
            archive.writestr(BIOS_MEMBER, data)
        elif not bios_extras:
            bios_extras = (("synthetic-unrelated.bin", b"unrelated" * 16),)
        for name, payload in bios_extras:
            method = zipfile.ZIP_DEFLATED if name.endswith(".deflated") else zipfile.ZIP_STORED
            archive.writestr(name, payload, compress_type=method)
    return game.getvalue(), bios.getvalue()


def corrupt_member_payload(source: bytes, member_name: str) -> bytes:
    """Flip an expanded member byte without changing its ZIP CRC metadata."""
    archive = bytearray(source)
    cursor = 0
    while True:
        local = archive.find(b"PK\x03\x04", cursor)
        if local < 0:
            raise AssertionError("synthetic ZIP local member not found")
        name_len, extra_len = struct.unpack_from("<HH", archive, local + 26)
        name = bytes(archive[local + 30:local + 30 + name_len]).decode("ascii")
        compressed = struct.unpack_from("<I", archive, local + 18)[0]
        if name == member_name:
            payload = local + 30 + name_len + extra_len
            if compressed == 0:
                raise AssertionError("synthetic member has no payload")
            archive[payload] ^= 1
            return bytes(archive)
        cursor = local + 30 + name_len + extra_len + compressed


def mutate_member_flags(source: bytes, member_name: str, flags: int) -> bytes:
    archive = bytearray(source)
    central = archive.find(b"PK\x01\x02")
    while central >= 0:
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", archive, central + 28)
        name = bytes(archive[central + 46:central + 46 + name_len]).decode("ascii")
        if name == member_name:
            local = struct.unpack_from("<I", archive, central + 42)[0]
            struct.pack_into("<H", archive, central + 8, flags)
            struct.pack_into("<H", archive, local + 6, flags)
            return bytes(archive)
        central = archive.find(b"PK\x01\x02", central + 46 + name_len + extra_len + comment_len)
    raise AssertionError("synthetic ZIP central member not found")


def mutate_zip_record(source: bytes, *, flags: int | None = None,
                      corrupt_crc: bool = False) -> bytes:
    archive = bytearray(source)
    central = archive.find(b"PK\x01\x02")
    local = struct.unpack_from("<I", archive, central + 42)[0]
    if flags is not None:
        struct.pack_into("<H", archive, central + 8, flags)
        struct.pack_into("<H", archive, local + 6, flags)
    if corrupt_crc:
        crc = struct.unpack_from("<I", archive, central + 16)[0] ^ 1
        struct.pack_into("<I", archive, central + 16, crc)
        struct.pack_into("<I", archive, local + 14, crc)
    return bytes(archive)


def mutate_central_zip64_extra_to_opaque(source: bytes, member_name: str) -> bytes:
    """Leave a ZIP64 extra in the local header while making its central twin valid."""
    archive = bytearray(source)
    central = archive.find(b"PK\x01\x02")
    while central >= 0:
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", archive, central + 28)
        name_start = central + 46
        name = bytes(archive[name_start:name_start + name_len]).decode("ascii")
        extra = name_start + name_len
        if name == member_name:
            field_id, field_size = struct.unpack_from("<HH", archive, extra)
            if field_id != 1 or field_size != 8 or extra_len != 12:
                raise AssertionError("expected one ZIP64 field in the central header")
            struct.pack_into("<H", archive, extra, 0x0002)
            return bytes(archive)
        central = archive.find(b"PK\x01\x02", central + 46 + name_len + extra_len + comment_len)
    raise AssertionError("synthetic ZIP central member not found")


def mutate_local_zip64_extra_to_opaque(source: bytes, member_name: str) -> bytes:
    """Leave a ZIP64 extra in the central header while making its local twin valid."""
    archive = bytearray(source)
    central = archive.find(b"PK\x01\x02")
    while central >= 0:
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", archive, central + 28)
        name_start = central + 46
        name = bytes(archive[name_start:name_start + name_len]).decode("ascii")
        if name == member_name:
            local = struct.unpack_from("<I", archive, central + 42)[0]
            local_name, local_extra = struct.unpack_from("<HH", archive, local + 26)
            extra = local + 30 + local_name
            field_id, field_size = struct.unpack_from("<HH", archive, extra)
            if field_id != 1 or field_size != 8 or local_extra != 12:
                raise AssertionError("expected one ZIP64 field in the local header")
            struct.pack_into("<H", archive, extra, 0x0002)
            return bytes(archive)
        central = archive.find(b"PK\x01\x02", central + 46 + name_len + extra_len + comment_len)
    raise AssertionError("synthetic ZIP central member not found")


def test_identity_importer(importer: str) -> tuple[str, tempfile.TemporaryDirectory[str]]:
    build_dir = Path(importer).resolve().parent
    root = Path(__file__).resolve().parents[2]
    cache = build_dir / "CMakeCache.txt"
    cache_values: dict[str, str] = {}
    for line in cache.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("//"):
            key, value = line.split("=", 1)
            cache_values[key.split(":", 1)[0]] = value
    compiler = cache_values.get("CMAKE_C_COMPILER")
    if not compiler:
        raise RuntimeError("configured C compiler is missing from CMakeCache")
    temporary = tempfile.TemporaryDirectory(prefix="mvs-test-importer-")
    binary = Path(temporary.name) / ("mvs_importer_test.exe" if os.name == "nt" else "mvs_importer_test")
    if os.name == "nt":
        library = next(build_dir.rglob("glueyneo_mvs_zlib.lib"))
        # Match the CMake default MSVC runtime of the zlib library, or the link fails with LNK2038.
        runtime = "/MDd" if cache_values.get("CMAKE_BUILD_TYPE") == "Debug" else "/MD"
        command = [compiler, "/nologo", "/std:c17", runtime, "/DMVS_IMPORT_TEST_IDENTITIES",
                   f"/I{root / 'third_party/zlib'}", str(root / "tools/mvs/mvs_import.c"), str(library),
                   f"/Fo:{temporary.name}\\", f"/Fe:{binary}"]
    else:
        library = build_dir / "libglueyneo_mvs_zlib.a"
        sanitizer_mode = cache_values.get(
            "GLUEYNEO_SDK_SANITIZER",
            cache_values.get("GLUEYNEO_OWNED_CPU_SANITIZER", "NONE"),
        )
        sanitizer_flags = {
            "NONE": [],
            "ADDRESS_UNDEFINED": ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"],
            "THREAD": ["-fsanitize=thread", "-fno-omit-frame-pointer"],
        }[sanitizer_mode]
        command = [compiler, "-std=c17", *sanitizer_flags,
                   "-DMVS_IMPORT_TEST_IDENTITIES",
                   "-I", str(root / "third_party/zlib"), str(root / "tools/mvs/mvs_import.c"), str(library),
                   *sanitizer_flags, "-o", str(binary)]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"test importer build failed ({result.returncode}):\n{result.stdout}")
    return str(binary), temporary


def make_archive(*, method: int = zipfile.ZIP_DEFLATED,
                 wrong_size: bool = False, duplicate: bool = False,
                 audio_bios: bytes | None = None,
                 main_bios_program: bytes | None = None,
                 main_bios_reset: bool = False,
                 duplicate_audio_bios: bool = False) -> bytes:
    data = [bytearray(size) for size in SIZES]
    data[0][0:8] = bytes.fromhex("0010fffe00000100")
    if main_bios_reset:
        data[0][0:8] = bytes.fromhex("0010fffe00c00100")
    default_main_bios_program = bytes.fromhex("725a33c1001000004e722700")
    main_program = (default_main_bios_program if main_bios_program is None
                    else main_bios_program)
    if len(main_program) > len(data[0]) - 0x100:
        raise ValueError("synthetic main BIOS program exceeds its region")
    data[0][0x100:0x100 + len(main_program)] = main_program
    if wrong_size:
        data[-1] = data[-1][:-1]
    target = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(target, "w", compression=method,
                             compresslevel=6, allowZip64=False) as archive:
            for index, (name, payload) in enumerate(zip(NAMES, data)):
                if duplicate_audio_bios and name == "sprites.bin":
                    continue
                if duplicate and index == 2:
                    continue
                archive.writestr(name, payload)
            if duplicate:
                archive.writestr("program.bin", bytes(SIZES[1]))
            if audio_bios is not None:
                archive.writestr(AUDIO_BIOS_NAME, audio_bios)
            if duplicate_audio_bios:
                archive.writestr(AUDIO_BIOS_NAME, bytes([0xA8]) * AUDIO_BIOS_SIZE)
    return target.getvalue()


class ImporterTests(unittest.TestCase):
    def test_phase07_frontend_current_core_rebind_keeps_frontend_identity_pinned(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        matches = getattr(qualification, "_active_frontend_identity_matches", None)
        self.assertTrue(callable(matches),
                        "Phase07 frontend runs must bind current core separately from historical scene identity")
        historical = {
            "retroarch_version": "1.22.2",
            "retroarch_executable_sha256": "a" * 64,
            "bundle_id": "org.libretro.RetroArch",
            "core_sha256": "b" * 64,
        }
        current = {**historical, "core_sha256": "c" * 64}
        sources = {"core_sha256": current["core_sha256"]}
        self.assertTrue(matches(historical, current, sources))
        for key, value in (("retroarch_version", "other"),
                           ("retroarch_executable_sha256", "d" * 64),
                           ("bundle_id", "org.other.frontend"),
                           ("core_sha256", "e" * 64)):
            with self.subTest(changed_field=key):
                self.assertFalse(matches(historical, {**current, key: value},
                                         sources))
        self.assertFalse(matches(historical, current, {"core_sha256": "not-a-core-digest"}))

    def test_frontend_identity_canonicalizes_all_owned_playlist_directories(self):
        from tools.mvs.qualify_local_boot import _frontend_configuration_identity
        from retroarch_smoke import write_frontend_config
        with tempfile.TemporaryDirectory() as temporary:
            roots=[Path(temporary)/name for name in ("first","second")]
            configs=[]
            for root in roots:
                root.mkdir()
                configs.append(write_frontend_config(root,root,direct_log=True).read_text()
                               + 'config_save_on_exit = "false"\n')
            def identity(text,index=0):
                return _frontend_configuration_identity(text,work_directory=roots[index],capture_directory=roots[index])
            self.assertIsNotNone(identity(configs[0]))
            self.assertEqual(identity(configs[0]),identity(configs[1],1))
            changed=configs[0].replace('bundle_assets_extract_enable = "false"',
                                       'bundle_assets_extract_enable = "true"')
            self.assertIsNone(identity(changed))
            for key in ("playlist_directory", "content_history_directory", "content_favorites_directory",
                        "content_image_history_directory", "content_music_history_directory", "content_video_directory"):
                for bad in ('default', str(roots[0]/'outside'), '/outside'):
                    self.assertIsNone(identity(configs[0].replace(f'{key} = "{roots[0]}"',f'{key} = "{bad}"')))
            self.assertIsNone(identity(configs[0]+f'playlist_directory = "{roots[0]}"\n'))

    @unittest.skipIf(os.name == "nt", "POSIX sanitizer compiler contract")
    def test_identity_importer_links_configured_sdk_sanitizer(self) -> None:
        for mode, flag, owned_cpu_mode in (
            ("NONE", None, "ADDRESS_UNDEFINED"),
            ("ADDRESS_UNDEFINED", "-fsanitize=address,undefined", "NONE"),
            ("THREAD", "-fsanitize=thread", "NONE"),
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                build = Path(directory)
                (build / "CMakeCache.txt").write_text(
                    "CMAKE_C_COMPILER:FILEPATH=cc\n"
                    "GLUEYNEO_SDK_SANITIZER:STRING=" + mode + "\n"
                    "GLUEYNEO_OWNED_CPU_SANITIZER:STRING=" + owned_cpu_mode + "\n")
                with mock.patch.object(subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
                    _binary, owner = test_identity_importer(str(build / "mvs_importer"))
                try:
                    command = run.call_args.args[0]
                    sanitizer = [arg for arg in command if arg.startswith("-fsanitize=")]
                    self.assertEqual(sanitizer, [flag, flag] if flag else [])
                finally:
                    owner.cleanup()

    def test_selected_import_output_reaches_frontend_bundle_validator(self) -> None:
        zoom = bytes([0x6D]) * Y_ZOOM_SIZE
        audio_bios = bytes([0xA8]) * AUDIO_BIOS_SIZE
        cases = (
            ("audio-bios-v2", ( ("sm1.sm1", audio_bios), ), 2, 7),
            ("zoom-v3", (("sm1.sm1", audio_bios), (Y_ZOOM_NAME, zoom)), 3, 8),
        )
        for label, bios_extras, expected_version, expected_count in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory(prefix="mvs-smoke-contract-") as directory:
                game, bios = make_split_archives(bios_extras=bios_extras)
                game_path = Path(directory) / "game.zip"
                bios_path = Path(directory) / "bios.zip"
                output_path = Path(directory) / "selected.gnmv"
                game_path.write_bytes(game)
                bios_path.write_bytes(bios)

                result = subprocess.run(
                    [self.importer, "--selected", str(game_path), str(bios_path), str(output_path)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                imported = output_path.read_bytes()

                self.assertTrue(is_normalized_mvs_bundle(imported))
                self.assertEqual(int.from_bytes(imported[4:8], "big"), expected_version)
                self.assertEqual(int.from_bytes(imported[12:16], "big"), expected_count)
    importer = os.environ.get("MVS_IMPORTER", "build/owned-debug/mvs_importer")
    production_importer = importer
    failure_driver: str | None = None

    def test_private_frame_output_is_ignored_and_bounded(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        report = Path("local/qualification/phase05-" + "a" * 32 + ".json")
        frame_path = qualification.private_frame_path(report)
        self.assertEqual(frame_path.suffix, ".ppm")
        self.assertTrue(qualification.private_frame_path_is_safe(frame_path))
        with tempfile.TemporaryDirectory(prefix="mvs-private-frame-") as directory:
            frame = Path(directory) / "frame.ppm"
            header = b"P6\n320 224\n255\n"
            frame.write_bytes(header + bytes(320 * 224 * 3))
            self.assertTrue(qualification.private_frame_is_valid(frame))
            frame.write_bytes(header + bytes(320 * 224 * 3 - 1))
            self.assertFalse(qualification.private_frame_is_valid(frame))
            frame.write_bytes(b"P6\n1 1\n255\n\x00\x00\x00")
            self.assertFalse(qualification.private_frame_is_valid(frame))

    def test_frontend_failure_diagnostic_projects_only_numeric_exit_code(self) -> None:
        from types import SimpleNamespace
        from tools.mvs import qualify_local_boot as qualification
        self.assertEqual(qualification._frontend_failure_return_code(
            SimpleNamespace(diagnostic={"return_code": -9, "output": "private"})), -9)
        self.assertEqual(qualification._frontend_failure_return_code(
            SimpleNamespace(diagnostic={"return_code": 0})), 0)
        self.assertIsNone(qualification._frontend_failure_return_code(
            SimpleNamespace(diagnostic={"return_code": True})))
        self.assertIsNone(qualification._frontend_failure_return_code(
            SimpleNamespace(diagnostic=None)))

        capture_dir = Path("local/qualification") / (
            f"phase05-{uuid.uuid4().hex}-captures")
        capture_dir.mkdir()
        logs = [capture_dir / "retroarch-private.log",
                capture_dir / "frontend-process-private.log"]
        try:
            for log in logs:
                log.write_text("private host log bytes\n", encoding="utf-8")
            hashes = [hashlib.sha256(log.read_bytes()).hexdigest() for log in logs]
            diagnostic = {
                "stage": "unload", "return_code": -11,
                "survived_before_screenshot": True,
                "output_available": True, "output": "private diagnostic text",
                "macos_crash_reason_available": True,
                "frontend_log_status": "pass",
                "frontend_log_paths": [str(log.resolve()) for log in logs],
                "frontend_log_sha256": hashes,
            }
            with mock.patch.object(qualification, "ignored", return_value=True):
                projected = qualification._private_frontend_failure_diagnostic(
                    SimpleNamespace(diagnostic=diagnostic), capture_dir)
                self.assertEqual(projected["return_code"], -11)
                self.assertEqual(projected["frontend_log_status"], "pass")
                self.assertEqual(projected["frontend_log_sha256"], hashes)
                self.assertNotIn("output", projected)
                logs[0].write_text("changed private log\n", encoding="utf-8")
                changed = qualification._private_frontend_failure_diagnostic(
                    SimpleNamespace(diagnostic=diagnostic), capture_dir)
                self.assertEqual(changed["frontend_log_status"], "unknown")
                self.assertEqual(changed["frontend_log_sha256"], [])
        finally:
            for log in logs:
                log.unlink(missing_ok=True)
            capture_dir.rmdir()

    def test_video_frame_advance_is_bounded_and_forwarded(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        calls: list[list[str]] = []
        native_report: dict[str, object] = {
            "status": "attract_start", "guest_executed": True,
            "checkpoint": {"user_request": "demo", "chunk": 1,
                           "user_mode_corroborated": True},
            "frame_output_written": True,
        }

        class Freshness(str):
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}
            qualifier_identity = {"scope": "production", "path": "fixture-runner",
                                  "sha256": "b" * 64}

            def __new__(cls) -> "Freshness":
                return str.__new__(cls, "fresh")

        class Result:
            def __init__(self, returncode: int, stdout: str = "") -> None:
                self.returncode = returncode
                self.stdout = stdout

        def execute(command: list[str], **_kwargs: object) -> Result:
            calls.append(command)
            if command[0] == "fixture-importer":
                return Result(0)
            return Result(0, json.dumps(native_report))

        with tempfile.TemporaryDirectory(prefix="mvs-frame-advance-") as directory, \
             mock.patch.object(qualification, "checked_importer_command",
                               return_value="fixture-importer"), \
             mock.patch.object(qualification, "checked_qualifier_command",
                               return_value="fixture-runner"), \
             mock.patch.object(qualification, "find_pairs", return_value=[(
                 Path("synthetic-game.zip"), Path("synthetic-bios.zip"))]), \
             mock.patch.object(qualification, "private_frame_path_is_safe",
                               return_value=True), \
             mock.patch.object(qualification, "private_frame_is_valid",
                               side_effect=[True, False, True]):
            frame = Path(directory) / "private-frame.ppm"
            result = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute, frame_output_path=frame,
                video_advance_frames=3)
            native_report.clear()
            native_report.update({"status": "guest_stopped",
                                  "frame_output_written": True})
            missing_stopped_frame = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute, frame_output_path=frame)
            native_report.clear()
            native_report.update({"status": "guest_stopped"})
            early_stopped = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute, frame_output_path=frame)
            native_report.clear()
            native_report.update({
                "status": "attract_start", "guest_executed": True,
                "checkpoint": {"user_request": "demo", "chunk": 1,
                               "user_mode_corroborated": True},
                "input_response": "not_observed",
                "frame_output_written": True,
            })
            scripted_no_response = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute, frame_output_path=frame, scripted_start=True)

        self.assertEqual(result["status"], "attract_start")
        self.assertEqual(calls[1][-2:], ["--video-advance-frames", "3"])
        self.assertEqual(missing_stopped_frame["status"],
                         "native_qualification_failed")
        self.assertEqual(early_stopped["status"], "native_qualification_failed")
        self.assertEqual(scripted_no_response["status"], "attract_start")
        self.assertEqual(scripted_no_response["input_response"], "not_observed")
        invalid = qualification.run_selected_qualification(
            Path("."), "not-run", freshness=lambda: self.fail("must validate first"),
            video_advance_frames=601)
        self.assertEqual(invalid["status"], "video_advance_out_of_bounds")

    def test_private_video_activity_is_forwarded_and_retained_locally(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        calls: list[list[str]] = []
        activity = {
            "nonzero_vram_words": 10, "fixed_tilemap_words": 2,
            "sprite_words": 4, "palette_entries": 1, "visible_sprites": 1,
            "visible_nonfull_y_zoom_samples": 0, "frame_count": 60,
            "backdrop_palette_nonzero": 1, "video_ram_offset": 0,
            "video_ram_modulo": 0, "palette_bank_selected": 0,
            "screen_shadow": 0, "video_auto_animation_speed": 0,
            "video_auto_animation_disabled": 0,
            "display_position_interrupt_control": 0,
        }

        class Freshness(str):
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}
            qualifier_identity = {"scope": "production", "path": "fixture-runner",
                                  "sha256": "b" * 64}

            def __new__(cls) -> "Freshness":
                return str.__new__(cls, "fresh")

        class Result:
            def __init__(self, returncode: int, stdout: str = "",
                         stderr: str = "") -> None:
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        native = {
            "status": "attract_start", "guest_executed": True,
            "checkpoint": {"user_request": "demo", "chunk": 1,
                           "user_mode_corroborated": True},
            "frame_output_written": True,
        }
        stderr_output = [json.dumps({"private_video_activity": activity})]

        def execute(command: list[str], **_kwargs: object) -> Result:
            calls.append(command)
            if command[0] == "fixture-importer":
                return Result(0)
            return Result(0, json.dumps(native),
                          stderr_output[0])

        with tempfile.TemporaryDirectory(prefix="mvs-video-activity-") as directory, \
             mock.patch.object(qualification, "checked_importer_command",
                               return_value="fixture-importer"), \
             mock.patch.object(qualification, "checked_qualifier_command",
                               return_value="fixture-runner"), \
             mock.patch.object(qualification, "find_pairs", return_value=[(
                 Path("synthetic-game.zip"), Path("synthetic-bios.zip"))]), \
             mock.patch.object(qualification, "private_frame_path_is_safe",
                               return_value=True), \
             mock.patch.object(qualification, "private_frame_is_valid",
                               return_value=True):
            result = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute, frame_output_path=Path(directory) / "frame.ppm",
                video_state_diagnostic=True)

        self.assertEqual(result["status"], "attract_start")
        self.assertIn("--video-state-diagnostic", calls[1])
        self.assertEqual(result["private_video_activity"], activity)

        stderr_output[0] = json.dumps({"private_video_activity": {
            **activity, "visible_sprites": True,
        }})
        with tempfile.TemporaryDirectory(prefix="mvs-video-activity-invalid-") as directory, \
             mock.patch.object(qualification, "checked_importer_command",
                               return_value="fixture-importer"), \
             mock.patch.object(qualification, "checked_qualifier_command",
                               return_value="fixture-runner"), \
             mock.patch.object(qualification, "find_pairs", return_value=[(
                 Path("synthetic-game.zip"), Path("synthetic-bios.zip"))]), \
             mock.patch.object(qualification, "private_frame_path_is_safe",
                               return_value=True), \
             mock.patch.object(qualification, "private_frame_is_valid",
                               return_value=True):
            malformed = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute, frame_output_path=Path(directory) / "frame.ppm",
                video_state_diagnostic=True)
        self.assertEqual(malformed["status"], "native_qualification_failed")
        self.assertNotIn("private_video_activity", malformed)

    def test_requested_frame_requires_matching_native_completion_marker(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        native_report: dict[str, object] = {
            "status": "attract_start", "guest_executed": True,
            "checkpoint": {"user_request": "demo", "chunk": 1,
                           "user_mode_corroborated": True},
        }

        class Freshness(str):
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}
            qualifier_identity = {"scope": "production", "path": "fixture-runner",
                                  "sha256": "b" * 64}

            def __new__(cls) -> "Freshness":
                return str.__new__(cls, "fresh")

        class Result:
            def __init__(self, returncode: int, stdout: str = "") -> None:
                self.returncode = returncode
                self.stdout = stdout

        def execute(command: list[str], **_kwargs: object) -> Result:
            if command[0] == "fixture-importer":
                return Result(0)
            return Result(0, json.dumps(native_report))

        with tempfile.TemporaryDirectory(prefix="mvs-frame-marker-") as directory, \
             mock.patch.object(qualification, "checked_importer_command",
                               return_value="fixture-importer"), \
             mock.patch.object(qualification, "checked_qualifier_command",
                               return_value="fixture-runner"), \
             mock.patch.object(qualification, "find_pairs", return_value=[(
                 Path("synthetic-game.zip"), Path("synthetic-bios.zip"))]), \
             mock.patch.object(qualification, "private_frame_path_is_safe",
                               return_value=True), \
             mock.patch.object(qualification, "private_frame_is_valid",
                               return_value=True):
            frame = Path(directory) / "private-frame.ppm"
            missing_marker = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute, frame_output_path=frame)
            native_report["frame_output_written"] = True
            unrequested_marker = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute)

        self.assertEqual(missing_marker["status"], "native_qualification_failed")
        self.assertEqual(unrequested_marker["status"], "native_qualification_failed")

    def test_qualifier_freshness_classifies_build_results(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        ensure_fresh = getattr(qualification, "ensure_fresh_qualifier", None)
        self.assertIsNotNone(ensure_fresh, "ensure_fresh_qualifier must classify build freshness")

        with tempfile.TemporaryDirectory(prefix="mvs-qualifier-build-identity-") as directory:
            configured = Path(directory) / "build" / "owned-debug" / "mvs_importer"
            qualifier = configured.with_name("mvs_qualify")
            configured.parent.mkdir(parents=True)
            configured.write_bytes(b"existing importer")
            configured.chmod(0o755)
            qualifier.write_bytes(b"existing runner")
            qualifier.chmod(0o755)
            calls: list[list[str]] = []
            artifacts_present_at_build: list[tuple[bool, bool]] = []

            class Result:
                def __init__(self, returncode: int, stdout: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout

            def runner(command: list[str], **_kwargs: object) -> Result:
                calls.append(command)
                if len(calls) == 1:
                    artifacts_present_at_build.append(
                        (configured.exists(), qualifier.exists()))
                    return Result(0)
                return Result(0, "ninja: no work to do.\n")

            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification, "CONFIGURED_QUALIFIER_PATH", qualifier):
                freshness = ensure_fresh(run=runner)
                self.assertEqual(freshness, "fresh")
                self.assertEqual(freshness.importer_identity, {
                    "scope": "production", "path": str(configured.resolve()),
                    "sha256": hashlib.sha256(configured.read_bytes()).hexdigest(),
                })
                self.assertEqual(freshness.qualifier_identity, {
                    "scope": "production", "path": str(qualifier.resolve()),
                    "sha256": hashlib.sha256(qualifier.read_bytes()).hexdigest(),
                })
            self.assertEqual(artifacts_present_at_build, [(True, True)])
            self.assertEqual(calls[0][2:7], ["--preset", "owned-debug", "--target",
                                              "mvs_importer", "mvs_qualify"])
            self.assertEqual(calls[1][2:7], ["--preset", "owned-debug", "--target",
                                              "mvs_importer", "mvs_qualify"])
            self.assertEqual(calls[1][-2:], ["--", "-n"])

            calls.clear()
            def failed_build(command: list[str], **_kwargs: object) -> Result:
                calls.append(command)
                return Result(1)

            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification, "CONFIGURED_QUALIFIER_PATH", qualifier):
                self.assertEqual(ensure_fresh(run=failed_build), "build_failed")
            self.assertEqual(len(calls), 1)

            calls.clear()
            def timed_out_build(command: list[str], **kwargs: object) -> Result:
                calls.append(command)
                self.assertTrue(configured.exists())
                self.assertTrue(qualifier.exists())
                self.assertEqual(kwargs.get("timeout"), 180)
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])

            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification, "CONFIGURED_QUALIFIER_PATH", qualifier):
                self.assertEqual(ensure_fresh(run=timed_out_build), "build_failed")
            self.assertEqual(len(calls), 1)

            calls.clear()
            def stale_dry_run(command: list[str], **_kwargs: object) -> Result:
                calls.append(command)
                if len(calls) == 1:
                    configured.write_bytes(b"rebuilt importer")
                    configured.chmod(0o755)
                    qualifier.write_bytes(b"rebuilt runner")
                    qualifier.chmod(0o755)
                    return Result(0)
                return Result(0, "[1/2] Building C object\n")

            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification, "CONFIGURED_QUALIFIER_PATH", qualifier):
                self.assertEqual(ensure_fresh(run=stale_dry_run), "stale")
            self.assertEqual(len(calls), 2)

    def test_qualifier_freshness_refusal_runs_no_guest(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        run_selected = getattr(qualification, "run_selected_qualification", None)
        self.assertIsNotNone(run_selected, "run_selected_qualification must enforce freshness")

        for freshness, expected in (("stale", "qualifier_stale"),
                                    ("build_failed", "qualifier_build_failed")):
            executed: list[object] = []
            with tempfile.TemporaryDirectory(prefix="mvs-qualifier-freshness-") as directory:
                result = run_selected(
                    Path(directory), ["not-run"], freshness=lambda value=freshness: value,
                    execute=lambda *args, **kwargs: executed.append((args, kwargs)),
                )
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["qualifier_build"], freshness)
            self.assertIn("retroarch_observation", result)
            self.assertIn("private_identity_recorded", result)
            self.assertEqual(executed, [])

        with tempfile.TemporaryDirectory(prefix="mvs-qualifier-empty-") as directory:
            from tools.mvs import qualify_local_boot as qualification
            configured = Path(self.production_importer).resolve()
            synthetic = qualification.synthetic_importer_identity(
                str(configured), expected_path=configured,
                expected_sha256=hashlib.sha256(configured.read_bytes()).hexdigest())
            result = run_selected(
                Path(directory), self.production_importer, freshness=lambda: "fresh",
                synthetic_identity=synthetic,
                execute=lambda *args, **kwargs: self.fail("empty media must not execute"),
            )
        self.assertEqual(result["status"], "no_supported_role_bundle_archive")
        self.assertEqual(result["qualifier_build"], "unchecked")

    def test_scripted_start_keeps_qualifier_freshness(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        calls: list[list[str]] = []

        for freshness, expected in (("stale", "qualifier_stale"),
                                    ("build_failed", "qualifier_build_failed")):
            with tempfile.TemporaryDirectory(prefix="mvs-scripted-freshness-") as directory:
                result = qualification.run_selected_qualification(
                    Path(directory), ["not-run"],
                    freshness=lambda value=freshness: value,
                    execute=lambda command, **kwargs: calls.append(command),
                    scripted_start=True)
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["qualifier_build"], freshness)
            self.assertEqual(result["qualification_invocation_state"], "not_started")
            self.assertEqual(calls, [])

        class Freshness(str):
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}

            def __new__(cls) -> "Freshness":
                return str.__new__(cls, "fresh")

        class Result:
            def __init__(self, returncode: int, stdout: str = "") -> None:
                self.returncode = returncode
                self.stdout = stdout

        def execute(command: list[str], **_kwargs: object) -> Result:
            calls.append(command)
            if command[0] == "fixture-importer":
                return Result(0)
            return Result(0, '{"status":"attract_start","guest_executed":true,'
                          '"checkpoint":{"user_request":"demo","chunk":1,'
                          '"user_mode_corroborated":true},'
                          '"input_response":"observed"}')

        with tempfile.TemporaryDirectory(prefix="mvs-scripted-freshness-fresh-") as directory, \
             mock.patch.object(qualification, "checked_importer_command",
                               return_value="fixture-importer"), \
             mock.patch.object(qualification, "checked_qualifier_command",
                               return_value="fixture-runner"), \
             mock.patch.object(qualification, "find_pairs", return_value=[(
                 Path("synthetic-game.zip"), Path("synthetic-bios.zip"))]):
            result = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute, scripted_start=True)

        self.assertEqual(result["status"], "attract_start")
        self.assertEqual(result["qualifier_build"], "fresh")
        self.assertEqual(result["input_response"], "observed")
        self.assertEqual(result["qualification_invocation_state"], "attempted")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][-2:], ["--input-script", "coin@1,start@600"])

    def test_selected_qualification_rejects_qualifier_substitution(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        for stage in ("before-import", "after-import", "missing-identity", "unchanged"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(
                    prefix="mvs-qualifier-substitution-") as directory:
                root = Path(directory)
                runner = root / "mvs_qualify"
                runner.write_bytes(b"current BIOS indication predicate")
                runner.chmod(0o755)
                identity = {"scope": "production", "path": str(runner.resolve()),
                            "sha256": hashlib.sha256(runner.read_bytes()).hexdigest()}
                build = type("Freshness", (str,), {
                    "importer_identity": {"scope": "production",
                                          "path": "fixture-importer", "sha256": "a" * 64},
                    "qualifier_identity": None if stage == "missing-identity" else identity,
                })("fresh")
                calls: list[list[str]] = []

                def substitute() -> None:
                    runner.write_bytes(b"old host-edge-only predicate")
                    # A newer timestamp must not make substituted bytes current.
                    os.utime(runner, (2000000000, 2000000000))

                def pairs(_root: Path) -> list[tuple[Path, Path]]:
                    if stage == "before-import":
                        substitute()
                    return [(root / "game.zip", root / "bios.zip")]

                def execute(command: list[str], **_kwargs: object):
                    calls.append(command)
                    if "--selected" in command:
                        if stage == "after-import":
                            substitute()
                        return subprocess.CompletedProcess(command, 0, "", "")
                    # Model the obsolete runner's positive token for a timer entry.
                    return subprocess.CompletedProcess(command, 0, json.dumps({
                        "status": "attract_start", "guest_executed": True,
                        "checkpoint": {"user_request": "demo", "chunk": 1,
                                       "user_mode_corroborated": True},
                        "input_response": "observed"}), "")

                with mock.patch.object(qualification, "CONFIGURED_QUALIFIER_PATH", runner,
                                       create=True), \
                     mock.patch.object(qualification, "checked_importer_command",
                                       return_value="fixture-importer"), \
                     mock.patch.object(qualification, "find_pairs", side_effect=pairs):
                    result = qualification.run_selected_qualification(
                        root, "fixture-importer", freshness=lambda: build,
                        execute=execute, scripted_start=True)
                if stage == "unchanged":
                    self.assertEqual(result["input_response"], "observed")
                    self.assertEqual(calls[1][0], str(runner.resolve()))
                else:
                    self.assertEqual(result["status"], "qualifier_stale")
                    self.assertEqual(result["qualifier_build"], "stale")
                    self.assertEqual(result["qualification_invocation_state"], "not_started")
                    self.assertNotIn("input_response", result)
                    self.assertEqual(len(calls), 1 if stage == "after-import" else 0)

    def test_media_identity_accepts_native_absolute_paths_and_rejects_relative_paths(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        def identity(path: str, digest: str) -> dict[str, object]:
            return {"path": path, "size": 1, "sha256": digest * 64}

        self.assertTrue(qualification._media_identity_is_valid([
            identity("/private/game.zip", "a"),
            identity("/private/bios.zip", "b"),
        ]))
        self.assertTrue(qualification._media_identity_is_valid([
            identity("C:/private/game.zip", "a"),
            identity("D:/private/bios.zip", "b"),
        ]))
        for path in ("relative/game.zip", "C:relative/game.zip",
                     "C:/../game.zip", "C:\\private\\game.zip"):
            with self.subTest(path=path):
                self.assertFalse(qualification._media_identity_is_valid([
                    identity(path, "a"),
                    identity("/private/bios.zip", "b"),
                ]))

    def test_selected_qualification_uses_expected_media_snapshots(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        class Freshness(str):
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}
            qualifier_identity = {"scope": "production", "path": "fixture-runner",
                                  "sha256": "b" * 64}

            def __new__(cls) -> "Freshness":
                return str.__new__(cls, "fresh")

        original_game = b"selected game archive"
        original_bios = b"selected BIOS archive"
        with tempfile.TemporaryDirectory(prefix="mvs-media-snapshot-") as directory:
            root = Path(directory)
            game = root / "game.zip"
            bios = root / "bios.zip"
            game.write_bytes(original_game)
            bios.write_bytes(original_bios)
            pairs = [(game, bios)]
            expected_identity = [qualification._file_identity(path)
                                 for path in pairs[0]]
            importer_arguments: list[list[str]] = []
            run_directories: list[Path] = []

            def remove_run_directory(run_directory: Path) -> None:
                for name in ("media-game.zip", "media-bios.zip", "frame-0000.ppm"):
                    (run_directory / name).unlink(missing_ok=True)
                run_directory.rmdir()

            def new_run_directory() -> Path:
                run_directory = (Path("local/qualification/phase06") /
                                 f"run-{uuid.uuid4().hex}")
                run_directory.mkdir(parents=True, exist_ok=False)
                self.addCleanup(remove_run_directory, run_directory)
                self.assertTrue(
                    qualification.private_active_capture_directory_is_safe(
                        run_directory))
                run_directories.append(run_directory)
                return run_directory

            def execute(command: list[str], **_kwargs: object):
                if "--selected" in command:
                    importer_arguments.append(command)
                    self.assertNotEqual(Path(command[2]), game)
                    self.assertNotEqual(Path(command[3]), bios)
                    self.assertEqual(Path(command[2]).name, "media-game.zip")
                    self.assertEqual(Path(command[3]).name, "media-bios.zip")
                    self.assertEqual(Path(command[2]).parent,
                                     Path(command[3]).parent)
                    self.assertIn(Path(command[2]).parent, run_directories)
                    self.assertEqual(Path(command[2]).read_bytes(), original_game)
                    self.assertEqual(Path(command[3]).read_bytes(), original_bios)
                    return subprocess.CompletedProcess(command, 0, "", "")
                capture_directory = Path(
                    command[command.index("--capture-directory") + 1])
                (capture_directory / "frame-0000.ppm").write_bytes(
                    b"P6\n320 224\n255\n" + bytes(320 * 224 * 3))
                return subprocess.CompletedProcess(command, 0, json.dumps({
                    "status": "active_frames_completed", "guest_executed": True,
                    "start_observed": True,
                    "active_frames_requested": 1,
                    "active_frames_completed": 1,
                    "capture_frames_requested": [0],
                    "capture_frames": [0], "sampled_inputs": [],
                }), "")

            with mock.patch.object(qualification, "checked_importer_command",
                                   return_value="fixture-importer"), \
                 mock.patch.object(qualification, "checked_qualifier_command",
                                   return_value="fixture-runner"), \
                 mock.patch.object(qualification, "find_pairs", return_value=pairs):
                result = qualification.run_selected_qualification(
                    root, "fixture-importer", freshness=Freshness, execute=execute,
                    scripted_start=True,
                    active_frames=1, capture_frames=[0],
                    capture_directory=new_run_directory(),
                    expected_media_identity=expected_identity)

            if not qualification._private_active_capture_directory_open_supported():
                self.assertEqual(result["status"], "media_identity_rejected")
                self.assertEqual(importer_arguments, [])
                self.assertTrue(all(
                    not (run_directory / name).exists()
                    for run_directory in run_directories
                    for name in ("media-game.zip", "media-bios.zip")))
                return

            self.assertEqual(result["status"], "active_frames_completed")
            self.assertEqual(len(importer_arguments), 1)

            game.write_bytes(original_game)
            calls_after_substitution: list[list[str]] = []

            def replace_selected_media(command: list[str], **_kwargs: object):
                calls_after_substitution.append(command)
                if "--selected" in command:
                    game.write_bytes(b"replacement selected game")
                    return subprocess.CompletedProcess(command, 0, "", "")
                self.fail("the runner must not execute after media identity changes")

            with mock.patch.object(qualification, "checked_importer_command",
                                   return_value="fixture-importer"), \
                 mock.patch.object(qualification, "checked_qualifier_command",
                                   return_value="fixture-runner"), \
                 mock.patch.object(qualification, "find_pairs", return_value=pairs):
                rejected = qualification.run_selected_qualification(
                    root, "fixture-importer", freshness=Freshness,
                    execute=replace_selected_media, scripted_start=True,
                    active_frames=1, capture_frames=[0],
                    capture_directory=new_run_directory(),
                    expected_media_identity=expected_identity)
            self.assertEqual(rejected["status"], "media_identity_rejected")
            self.assertEqual(len(calls_after_substitution), 1)
            self.assertTrue(all(
                qualification.ignored(run_directory) for run_directory in run_directories))

    def test_selected_qualification_rejects_snapshot_symlink_race(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        class Freshness(str):
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}
            qualifier_identity = {"scope": "production", "path": "fixture-runner",
                                  "sha256": "b" * 64}

            def __new__(cls) -> "Freshness":
                return str.__new__(cls, "fresh")

        with tempfile.TemporaryDirectory(prefix="mvs-snapshot-race-") as directory:
            root = Path(directory)
            game = root / "game.zip"
            bios = root / "bios.zip"
            victim = root / "victim.bin"
            game.write_bytes(b"selected game archive")
            bios.write_bytes(b"selected BIOS archive")
            victim.write_bytes(b"preserve this unrelated file")
            expected_victim = victim.read_bytes()
            run_directory = (Path("local/qualification/phase06") /
                             f"run-{uuid.uuid4().hex}")
            run_directory.mkdir(parents=True, exist_ok=False)

            def remove_run_directory() -> None:
                for name in ("media-game.zip", "media-bios.zip", "frame-0000.ppm"):
                    (run_directory / name).unlink(missing_ok=True)
                run_directory.rmdir()

            self.addCleanup(remove_run_directory)
            snapshot = run_directory / "media-game.zip"
            expected_identity = [qualification._file_identity(path)
                                 for path in (game, bios)]
            injected = [False]
            original_is_symlink = Path.is_symlink

            def insert_symlink_after_collision_check(path: Path) -> bool:
                result = original_is_symlink(path)
                if path == snapshot and not result and not injected[0]:
                    snapshot.symlink_to(victim)
                    injected[0] = True
                return result

            calls: list[list[str]] = []

            def execute(command: list[str], **_kwargs: object):
                calls.append(command)
                self.fail("media substitution must stop before importer or runner")

            with mock.patch.object(qualification, "checked_importer_command",
                                   return_value="fixture-importer"), \
                 mock.patch.object(qualification, "checked_qualifier_command",
                                   return_value="fixture-runner"), \
                 mock.patch.object(qualification, "find_pairs",
                                   return_value=[(game, bios)]), \
                 mock.patch.object(Path, "is_symlink",
                                   insert_symlink_after_collision_check):
                result = qualification.run_selected_qualification(
                    root, "fixture-importer", freshness=Freshness, execute=execute,
                    scripted_start=True, active_frames=1, capture_frames=[0],
                    capture_directory=run_directory,
                    expected_media_identity=expected_identity)

            if not qualification._private_active_capture_directory_open_supported():
                self.assertEqual(result["status"], "media_identity_rejected")
                self.assertFalse(injected[0])
                self.assertFalse(snapshot.exists())
                self.assertEqual(victim.read_bytes(), expected_victim)
                self.assertEqual(calls, [])
                return

            self.assertTrue(injected[0])
            self.assertEqual(result["status"], "media_identity_rejected")
            self.assertEqual(victim.read_bytes(), expected_victim)
            self.assertEqual(calls, [])

    def test_selected_qualification_bounds_media_snapshot_growth(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        class Freshness(str):
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}
            qualifier_identity = {"scope": "production", "path": "fixture-runner",
                                  "sha256": "b" * 64}

            def __new__(cls) -> "Freshness":
                return str.__new__(cls, "fresh")

        with tempfile.TemporaryDirectory(prefix="mvs-snapshot-growth-") as directory:
            root = Path(directory)
            game = root / "game.zip"
            bios = root / "bios.zip"
            game.write_bytes(b"selected game archive")
            bios.write_bytes(b"selected BIOS archive")
            expected_identity = [qualification._file_identity(path)
                                 for path in (game, bios)]
            expected_size = expected_identity[0]["size"]
            run_directory = (Path("local/qualification/phase06") /
                             f"run-{uuid.uuid4().hex}")
            run_directory.mkdir(parents=True, exist_ok=False)

            def remove_run_directory() -> None:
                for name in ("media-game.zip", "media-bios.zip", "frame-0000.ppm"):
                    (run_directory / name).unlink(missing_ok=True)
                run_directory.rmdir()

            self.addCleanup(remove_run_directory)
            snapshot = run_directory / "media-game.zip"
            expanded = [False]
            original_is_symlink = Path.is_symlink

            def grow_source_after_identity_check(path: Path) -> bool:
                result = original_is_symlink(path)
                if path == snapshot and not result and not expanded[0]:
                    with game.open("ab") as source:
                        source.write(b"x" * (2 * 1024 * 1024))
                    expanded[0] = True
                return result

            calls: list[list[str]] = []

            def execute(command: list[str], **_kwargs: object):
                calls.append(command)
                self.fail("oversized media must stop before importer or runner")

            with mock.patch.object(qualification, "checked_importer_command",
                                   return_value="fixture-importer"), \
                 mock.patch.object(qualification, "checked_qualifier_command",
                                   return_value="fixture-runner"), \
                 mock.patch.object(qualification, "find_pairs",
                                   return_value=[(game, bios)]), \
                 mock.patch.object(Path, "is_symlink",
                                   grow_source_after_identity_check):
                result = qualification.run_selected_qualification(
                    root, "fixture-importer", freshness=Freshness, execute=execute,
                    scripted_start=True, active_frames=1, capture_frames=[0],
                    capture_directory=run_directory,
                    expected_media_identity=expected_identity)

            if not qualification._private_active_capture_directory_open_supported():
                self.assertEqual(result["status"], "media_identity_rejected")
                self.assertFalse(expanded[0])
                self.assertFalse(snapshot.exists())
                self.assertEqual(game.stat().st_size, expected_size)
                self.assertEqual(calls, [])
                return

            self.assertTrue(expanded[0])
            self.assertEqual(result["status"], "media_identity_rejected")
            self.assertTrue(snapshot.is_file())
            self.assertLessEqual(snapshot.stat().st_size, expected_size + 1)
            self.assertEqual(calls, [])

    def test_selected_qualification_rejects_capture_directory_symlink_race(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        class Freshness(str):
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}
            qualifier_identity = {"scope": "production", "path": "fixture-runner",
                                  "sha256": "b" * 64}

            def __new__(cls) -> "Freshness":
                return str.__new__(cls, "fresh")

        with tempfile.TemporaryDirectory(prefix="mvs-directory-race-") as directory:
            root = Path(directory)
            game = root / "game.zip"
            bios = root / "bios.zip"
            redirected = root / "redirected"
            redirected.mkdir()
            sentinel = redirected / "sentinel.bin"
            sentinel.write_bytes(b"preserve redirected directory")
            game.write_bytes(b"selected game archive")
            bios.write_bytes(b"selected BIOS archive")
            expected_sentinel = sentinel.read_bytes()
            run_directory = (Path("local/qualification/phase06") /
                             f"run-{uuid.uuid4().hex}")
            moved_directory = run_directory.with_name(run_directory.name + "-moved")
            run_directory.mkdir(parents=True, exist_ok=False)

            def remove_run_directory() -> None:
                if run_directory.is_symlink():
                    run_directory.unlink()
                for directory_path in (run_directory, moved_directory):
                    if directory_path.is_dir() and not directory_path.is_symlink():
                        for name in ("media-game.zip", "media-bios.zip",
                                     "frame-0000.ppm"):
                            (directory_path / name).unlink(missing_ok=True)
                        directory_path.rmdir()

            self.addCleanup(remove_run_directory)
            expected_identity = [qualification._file_identity(path)
                                 for path in (game, bios)]
            original_safe = qualification.private_active_capture_directory_is_safe
            validations = [0]

            def replace_validated_directory(path: Path, **kwargs: object) -> bool:
                valid = original_safe(path, **kwargs)
                if path == run_directory and valid:
                    validations[0] += 1
                    if (validations[0] == 2 and
                            qualification._private_active_capture_directory_open_supported()):
                        run_directory.rename(moved_directory)
                        run_directory.symlink_to(redirected, target_is_directory=True)
                return valid

            commands: list[list[str]] = []

            def execute(command: list[str], **_kwargs: object):
                commands.append(command)
                if "--selected" in command:
                    return subprocess.CompletedProcess(command, 0, "", "")
                capture_directory = Path(
                    command[command.index("--capture-directory") + 1])
                (capture_directory / "frame-0000.ppm").write_bytes(
                    b"P6\n320 224\n255\n" + bytes(320 * 224 * 3))
                return subprocess.CompletedProcess(command, 0, json.dumps({
                    "status": "active_frames_completed", "guest_executed": True,
                    "start_observed": True,
                    "active_frames_requested": 1,
                    "active_frames_completed": 1,
                    "capture_frames_requested": [0],
                    "capture_frames": [0], "sampled_inputs": [],
                }), "")

            with mock.patch.object(qualification, "checked_importer_command",
                                   return_value="fixture-importer"), \
                 mock.patch.object(qualification, "checked_qualifier_command",
                                   return_value="fixture-runner"), \
                 mock.patch.object(qualification, "find_pairs",
                                   return_value=[(game, bios)]), \
                 mock.patch.object(qualification,
                                   "private_active_capture_directory_is_safe",
                                   replace_validated_directory):
                result = qualification.run_selected_qualification(
                    root, "fixture-importer", freshness=Freshness, execute=execute,
                    scripted_start=True, active_frames=1, capture_frames=[0],
                    capture_directory=run_directory,
                    expected_media_identity=expected_identity)

            if not qualification._private_active_capture_directory_open_supported():
                self.assertEqual(validations[0], 2)
                self.assertEqual(result["status"], "media_identity_rejected")
                self.assertTrue(run_directory.is_dir())
                self.assertFalse(run_directory.is_symlink())
                self.assertFalse(moved_directory.exists())
                self.assertEqual(sentinel.read_bytes(), expected_sentinel)
                self.assertEqual({path.name for path in redirected.iterdir()},
                                 {"sentinel.bin"})
                self.assertEqual(commands, [])
                return

            self.assertEqual(validations[0], 2)
            self.assertEqual(result["status"], "media_identity_rejected")
            self.assertTrue(moved_directory.is_dir())
            self.assertTrue(run_directory.is_symlink())
            self.assertEqual(sentinel.read_bytes(), expected_sentinel)
            self.assertEqual({path.name for path in redirected.iterdir()},
                             {"sentinel.bin"})
            self.assertEqual(commands, [])

    def test_selected_qualification_binds_execution_to_configured_importer(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        with tempfile.TemporaryDirectory(prefix="mvs-identity-contract-") as directory:
            root = Path(directory)
            configured = root / "build" / "owned-debug" / "mvs_importer"
            configured.parent.mkdir(parents=True)
            configured.write_bytes(b"configured importer")
            configured.chmod(0o755)
            alias = root / "importer-alias"
            alias.symlink_to(configured)
            wrapper = root / "wrapper"
            wrapper.write_bytes(b"different executable")
            wrapper.chmod(0o755)
            game = root / "game.zip"
            bios = root / "bios.zip"
            synthetic = qualification.synthetic_importer_identity(
                str(configured), expected_path=configured,
                expected_sha256=hashlib.sha256(configured.read_bytes()).hexdigest())

            for candidate in (None, str(configured), [str(alias)]):
                calls: list[list[str]] = []

                class Result:
                    def __init__(self, returncode: int, stdout: str = "") -> None:
                        self.returncode = returncode
                        self.stdout = stdout

                def execute(command: list[str], **_kwargs: object) -> Result:
                    calls.append(command)
                    if "--selected" in command:
                        return Result(0)
                    return Result(0, '{"status":"attract_start","guest_executed":true,'
                                 '"checkpoint":{"user_request":"demo","chunk":1,'
                                 '"user_mode_corroborated":true}}')

                with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                     mock.patch.object(qualification, "find_pairs", return_value=[(game, bios)]):
                    result = qualification.run_selected_qualification(
                        root, candidate, freshness=lambda: "fresh", execute=execute,
                        synthetic_identity=synthetic)

                self.assertEqual(result["qualifier_build"], "unchecked")
                self.assertEqual(result["status"], "synthetic_importer_identity_verified")
                self.assertEqual(result["importer_identity_scope"], "synthetic")
                self.assertEqual(calls[0][0], str(configured.resolve()))
                self.assertEqual(len(calls), 1)

            for candidate in (str(wrapper), [str(configured), "--wrapper-flag"]):
                executed: list[object] = []
                with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured):
                    result = qualification.run_selected_qualification(
                        root, candidate, freshness=lambda: "fresh",
                        execute=lambda *args, **kwargs: executed.append((args, kwargs)),
                        synthetic_identity=synthetic)
                self.assertEqual(result["status"], "importer_identity_rejected")
                self.assertEqual(result["qualifier_build"], "unchecked")
                self.assertEqual(executed, [])
                self.assertNotIn(str(root), json.dumps(result))

    def run_wrapper_attempt(self, *, importer_returncode: int = 0,
                             importer_exception: BaseException | None = None,
                             runner_result: subprocess.CompletedProcess[str] | None = None,
                             runner_exception: BaseException | None = None
                             ) -> tuple[dict[str, object], list[list[str]]]:
        from tools.mvs import qualify_local_boot as qualification

        class Freshness:
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}

            def __str__(self) -> str:
                return "fresh"

        calls: list[list[str]] = []

        def execute(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[0] == "fixture-importer":
                if importer_exception is not None:
                    raise importer_exception
                return subprocess.CompletedProcess(command, importer_returncode, "", "")
            if runner_exception is not None:
                raise runner_exception
            assert runner_result is not None
            return runner_result

        with tempfile.TemporaryDirectory(prefix="mvs-wrapper-attempt-") as directory, \
             mock.patch.object(qualification, "checked_importer_command",
                               return_value="fixture-importer"), \
             mock.patch.object(qualification, "checked_qualifier_command",
                               return_value="fixture-runner"), \
             mock.patch.object(qualification, "find_pairs",
                               return_value=[(Path("game.zip"), Path("bios.zip"))]):
            result = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute)
        return result, calls

    def test_nonzero_native_positive_is_rejected(self) -> None:
        positive = {
            "status": "attract_start", "guest_executed": True,
            "checkpoint": {"user_request": "demo", "chunk": 1,
                           "user_mode_corroborated": True},
        }
        for returncode, accepted in ((0, True), (9, False), (-15, False)):
            with self.subTest(returncode=returncode):
                runner = subprocess.CompletedProcess(
                    ["mvs_qualify"], returncode, json.dumps(positive), "")
                result, calls = self.run_wrapper_attempt(runner_result=runner)
                self.assertEqual(len(calls), 2)
                self.assertEqual(result["qualification_invocation_state"], "attempted")
                if accepted:
                    self.assertEqual(result["status"], "attract_start")
                    self.assertEqual(result["checkpoint"], positive["checkpoint"])
                else:
                    self.assertEqual(result["status"], "native_qualification_failed")
                    self.assertNotIn("checkpoint", result)
                    self.assertNotIn("guest_executed", result)

    def test_nonzero_main_bus_guest_fault_preserves_validated_diagnostic(self) -> None:
        failure = {
            "component": "main_cpu", "stage": "bus_access",
            "reason": "bus_failure", "site": "main_bus_read",
            "site_valid": True, "device_cause": "main_bus_callback",
            "device_cause_valid": True, "underlying_status": "unknown",
            "underlying_status_valid": False, "emulated_cycle": 256,
            "emulated_cycle_valid": True, "completed_main_instructions": 1,
            "instruction_boundary_valid": True, "pc": 0, "pc_valid": False,
            "opcode": 0, "opcode_valid": False, "operation": "read",
            "address": 0x900000, "width": 2, "bus_access_valid": True,
        }
        native = {"status": "unsupported_guest_event", "guest_executed": True,
                  "native_failure": failure}
        runner = subprocess.CompletedProcess(
            ["mvs_qualify"], 1, json.dumps(native), "")
        result, calls = self.run_wrapper_attempt(runner_result=runner)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["qualification_invocation_state"], "attempted")
        self.assertEqual(result["status"], "unsupported_guest_event")
        self.assertIs(result["guest_executed"], True)
        self.assertEqual(result["native_failure"], failure)

        malformed = {"status": "unsupported_guest_event", "guest_executed": True}
        runner = subprocess.CompletedProcess(
            ["mvs_qualify"], 1, json.dumps(malformed), "")
        result, _ = self.run_wrapper_attempt(runner_result=runner)
        self.assertEqual(result["status"], "native_qualification_failed")
        self.assertNotIn("native_failure", result)

    def test_invalid_utf8_preserves_durable_uncertain_receipt(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        class Freshness:
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}

            def __str__(self) -> str:
                return "fresh"

        original_run_selected = qualification.run_selected_qualification
        for stream in ("stdout", "stderr"):
            with self.subTest(stream=stream), tempfile.TemporaryDirectory(
                    prefix="mvs-invalid-native-output-") as directory:
                root = Path(directory)
                (root / "local/roms").mkdir(parents=True)
                importer = root / "fixture-importer"
                importer.write_text("#!/usr/bin/env python3\nraise SystemExit(0)\n",
                                    encoding="utf-8")
                importer.chmod(0o755)
                launcher = root / "build/owned-debug/mvs_qualify"
                launcher.parent.mkdir(parents=True)
                launcher.write_text(
                    "#!/usr/bin/env python3\nimport sys\n"
                    f"sys.{stream}.buffer.write(bytes([129]))\n",
                    encoding="utf-8")
                launcher.chmod(0o755)
                calls: list[list[str]] = []

                def execute(command: list[str], **kwargs: object):
                    calls.append(command)
                    if os.name == "nt" and command[0] == str(importer):
                        # The checked command is synthetic; avoid launching a
                        # POSIX shebang script on Windows while preserving the
                        # selected-import success branch.
                        return subprocess.CompletedProcess(command, 0)
                    if os.name == "nt" and command[0] == str(launcher):
                        # Use a real child process so Python's Windows text
                        # decoder exercises the same invalid-output exception.
                        # Pin UTF-8 here so the regression is independent of
                        # the runner's active Windows code page.
                        command = [sys.executable, "-c",
                                   f"import sys; sys.{stream}.buffer.write(bytes([129]))"]
                        kwargs["encoding"] = "utf-8"
                    return subprocess.run(command, **kwargs)

                def run_selected(input_root: Path, importer_argument=None, **options: object):
                    return original_run_selected(
                        input_root, importer_argument,
                        freshness=Freshness, execute=execute, **options)

                previous_cwd = Path.cwd()
                os.chdir(root)
                try:
                    with mock.patch.object(qualification, "ignored", return_value=True), \
                         mock.patch.object(qualification, "find_pairs", return_value=[
                             (root / "local/roms/game.zip", root / "local/roms/bios.zip")]), \
                         mock.patch.object(qualification, "checked_importer_command",
                                           return_value=str(importer)), \
                         mock.patch.object(qualification, "checked_qualifier_command",
                                           return_value=str(launcher)), \
                         mock.patch.object(qualification, "run_selected_qualification",
                                           side_effect=run_selected), \
                         mock.patch("sys.argv", ["qualify_local_boot.py"]):
                        try:
                            exit_code = qualification.main()
                        except UnicodeDecodeError:
                            # Exercise the real subprocess text-decoding failure without
                            # echoing its output-derived exception details into test logs.
                            exit_code = None

                    report_paths = list((root / "local/qualification").glob("phase05-*.json"))
                    self.assertEqual(exit_code, 1)
                    self.assertEqual(
                        sum(command[0] == str(launcher)
                            for command in calls), 1)
                    self.assertEqual(len(report_paths), 1)
                    report_bytes = report_paths[0].read_bytes()
                    report = json.loads(report_bytes)
                    self.assertEqual(report, {
                        "qualifier_build": "fresh",
                        "qualification_invocation_state": "uncertain",
                        "private_identity_recorded": False,
                        "retroarch_observation": "manual-only-unknown",
                        "status": "native_qualification_failed",
                    })
                    self.assertNotIn(bytes([129]), report_bytes)
                    self.assertNotIn(str(root), report_bytes.decode("utf-8"))
                finally:
                    os.chdir(previous_cwd)

    def test_runner_zero_instruction_attempt_is_counted(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        failure = {
            "component": "main_cpu", "stage": "execute",
            "reason": "internal_failure", "site": "main_execution",
            "site_valid": True, "device_cause": "owned_cpu",
            "device_cause_valid": True, "underlying_status": "unknown",
            "underlying_status_valid": False, "emulated_cycle": 0,
            "emulated_cycle_valid": True, "completed_main_instructions": 0,
            "instruction_boundary_valid": True, "pc": 0, "pc_valid": False,
            "opcode": 0, "opcode_valid": False, "operation": "unknown",
            "address": 0, "width": 0, "bus_access_valid": False,
        }
        native = {"status": "native_execution_error", "guest_executed": False,
                  "native_failure": failure}
        runner = subprocess.CompletedProcess(["mvs_qualify"], 1,
                                             json.dumps(native), "")
        result, calls = self.run_wrapper_attempt(runner_result=runner)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["qualification_invocation_state"], "attempted")
        self.assertEqual(result["status"], "native_execution_error")
        self.assertIs(result["guest_executed"], False)
        self.assertEqual(result["native_failure"], native["native_failure"])

        native_with_progress = {
            **native, "guest_executed": True,
            "native_failure": {**failure, "completed_main_instructions": 1},
        }
        runner = subprocess.CompletedProcess(["mvs_qualify"], 1,
                                             json.dumps(native_with_progress), "")
        result, calls = self.run_wrapper_attempt(runner_result=runner)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["qualification_invocation_state"], "attempted")
        self.assertEqual(result["status"], "native_execution_error")
        self.assertIs(result["guest_executed"], True)
        self.assertEqual(result["native_failure"],
                         native_with_progress["native_failure"])

    def test_pre_entry_refusal_is_not_counted(self) -> None:
        result, calls = self.run_wrapper_attempt(importer_returncode=9)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "selected_media_import_failed")
        self.assertEqual(result["qualification_invocation_state"], "not_started")

    def test_importer_timeout_is_retained_without_native_execution(self) -> None:
        timeout = subprocess.TimeoutExpired(["fixture-importer"], 30)
        result, calls = self.run_wrapper_attempt(importer_exception=timeout)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "selected_media_import_timeout")
        self.assertEqual(result["qualification_invocation_state"], "not_started")

    def test_ambiguous_runner_attempt_consumes_slot(self) -> None:
        timeout = subprocess.TimeoutExpired(["mvs_qualify"], 1)
        result, calls = self.run_wrapper_attempt(runner_exception=timeout)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["status"], "native_qualification_failed")
        self.assertEqual(result["qualification_invocation_state"], "uncertain")

    def test_native_runner_interruption_is_retained_as_uncertain(self) -> None:
        try:
            result, calls = self.run_wrapper_attempt(
                runner_exception=KeyboardInterrupt())
        except KeyboardInterrupt:
            self.fail("native runner interruption escaped without a failure result")
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["status"], "native_qualification_interrupted")
        self.assertEqual(result["qualification_invocation_state"], "uncertain")

    def test_native_runner_uses_host_timeouts_and_rejects_oversized_report(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        class Freshness:
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}

            def __str__(self) -> str:
                return "fresh"

        checkpoint = {
            "status": "attract_start", "guest_executed": True,
            "checkpoint": {"user_request": "demo", "chunk": 1,
                           "user_mode_corroborated": True},
        }
        too_large = json.dumps(checkpoint) + " " * (2 * 1024 * 1024)
        calls: list[tuple[list[str], dict[str, object]]] = []

        def execute(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            if command[0] == "fixture-importer":
                return subprocess.CompletedProcess(command, 0, "", "")
            return subprocess.CompletedProcess(command, 0, too_large, "")

        with tempfile.TemporaryDirectory(prefix="mvs-runner-bounds-") as directory, \
             mock.patch.object(qualification, "checked_importer_command",
                               return_value="fixture-importer"), \
             mock.patch.object(qualification, "checked_qualifier_command",
                               return_value="fixture-runner"), \
             mock.patch.object(qualification, "find_pairs",
                               return_value=[(Path("game.zip"), Path("bios.zip"))]):
            result = qualification.run_selected_qualification(
                Path(directory), "fixture-importer", freshness=Freshness,
                execute=execute)

        self.assertEqual(calls[0][1].get("timeout"), 30)
        self.assertEqual(calls[1][1].get("timeout"), 120)
        self.assertEqual(result["status"], "native_qualification_output_limit")
        self.assertEqual(result["qualification_invocation_state"], "attempted")

    def test_main_keeps_unique_atomic_failure_reports(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        first = {"status": "qualifier_build_failed", "qualifier_build": "build_failed"}
        second = {"status": "native_qualification_interrupted",
                  "qualifier_build": "fresh",
                  "qualification_invocation_state": "uncertain"}
        with tempfile.TemporaryDirectory(prefix="mvs-report-retention-") as directory:
            root = Path(directory)
            (root / "local/roms").mkdir(parents=True)
            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                with mock.patch.object(qualification, "ignored", return_value=True), \
                     mock.patch.object(qualification, "run_selected_qualification",
                                       side_effect=[first, second]), \
                     mock.patch("sys.argv", ["qualify_local_boot.py"]):
                    self.assertEqual(qualification.main(), 1)
                    self.assertEqual(qualification.main(), 1)
                report_paths = sorted((root / "local/qualification").glob("phase05-*.json"))
                self.assertEqual(len(report_paths), 2)
                report_bytes = [path.read_bytes() for path in report_paths]
                self.assertEqual({json.loads(raw)["status"] for raw in report_bytes},
                                 {"qualifier_build_failed",
                                  "native_qualification_interrupted"})
                self.assertFalse(qualification.write_report(
                    report_paths[0], {"status": "overwritten"}))
                self.assertEqual(report_paths[0].read_bytes(), report_bytes[0])
            finally:
                os.chdir(previous_cwd)

    def test_windows_report_uses_atomic_no_replace_rename(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        with tempfile.TemporaryDirectory(prefix="mvs-windows-report-") as directory:
            report = Path(directory) / "receipt.json"
            with mock.patch.object(qualification.sys, "platform", "win32"), \
                    mock.patch.object(qualification.os, "rename",
                                      wraps=os.rename) as rename, \
                    mock.patch.object(qualification.os, "link") as link:
                self.assertTrue(qualification.write_report(report, {"status": "first"}))
            rename.assert_called_once()
            link.assert_not_called()
            original = report.read_bytes()
            with mock.patch.object(qualification.sys, "platform", "win32"), \
                    mock.patch.object(qualification.os, "rename",
                                      side_effect=FileExistsError("destination exists")) as rename, \
                    mock.patch.object(qualification.os, "link") as link:
                self.assertFalse(qualification.write_report(report, {"status": "replacement"}))
            rename.assert_called_once()
            link.assert_not_called()
            self.assertEqual(report.read_bytes(), original)

    def test_simultaneous_selected_invocations_use_distinct_bundles(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        class Freshness:
            importer_identity = {"scope": "production", "path": "fixture-importer",
                                 "sha256": "a" * 64}
            qualifier_identity = {"scope": "production", "path": "fixture-runner",
                                  "sha256": "b" * 64}

            def __str__(self) -> str:
                return "fresh"

        positive = json.dumps({
            "status": "attract_start", "guest_executed": True,
            "checkpoint": {"user_request": "demo", "chunk": 1,
                           "user_mode_corroborated": True},
        })
        rendezvous = threading.Barrier(2)
        bundle_paths: list[str] = []

        with tempfile.TemporaryDirectory(prefix="mvs-parallel-runner-") as directory:
            root = Path(directory)
            input_root = root / "local/roms"
            input_root.mkdir(parents=True)
            game = input_root / "synthetic-game.zip"
            bios = input_root / "synthetic-bios.zip"
            game.write_bytes(b"original synthetic game archive")
            bios.write_bytes(b"original synthetic BIOS archive")
            originals = (game.read_bytes(), bios.read_bytes())

            def execute(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                if command[0] == "fixture-importer":
                    bundle = Path(command[-1])
                    bundle.write_bytes(b"normalized synthetic bundle")
                    bundle_paths.append(str(bundle))
                    return subprocess.CompletedProcess(command, 0, "", "")
                rendezvous.wait(timeout=10)
                return subprocess.CompletedProcess(command, 0, positive, "")

            with mock.patch.object(qualification, "checked_importer_command",
                                   return_value="fixture-importer"), \
                 mock.patch.object(qualification, "checked_qualifier_command",
                                   return_value="fixture-runner"), \
                 mock.patch.object(qualification, "find_pairs",
                                   return_value=[(game, bios)]):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(
                        qualification.run_selected_qualification, input_root,
                        "fixture-importer", Freshness, execute) for _ in range(2)]
                    results = [future.result(timeout=15) for future in futures]

            self.assertEqual([result["status"] for result in results],
                             ["attract_start", "attract_start"])
            self.assertEqual(len(set(bundle_paths)), 2)
            self.assertEqual((game.read_bytes(), bios.read_bytes()), originals)

    def test_non_object_runner_json_preserves_counted_attempt(self) -> None:
        for payload in ("[]", "null", "7", '"unexpected"'):
            with self.subTest(payload=payload):
                runner = subprocess.CompletedProcess(["mvs_qualify"], 1, payload, "")
                result, calls = self.run_wrapper_attempt(runner_result=runner)
                self.assertEqual(len(calls), 2)
                self.assertEqual(result["status"], "native_qualification_failed")
                self.assertEqual(result["qualification_invocation_state"], "attempted")
                self.assertEqual(result["retroarch_observation"], "manual-only-unknown")
                self.assertIs(result["private_identity_recorded"], False)
                self.assertNotIn("guest_executed", result)
                self.assertNotIn("native_failure", result)
                self.assertNotIn("diagnosis", result)

    def test_selected_qualification_rechecks_identity_immediately_before_execution(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        with tempfile.TemporaryDirectory(prefix="mvs-identity-recheck-") as directory:
            root = Path(directory)
            configured = root / "build" / "owned-debug" / "mvs_importer"
            configured.parent.mkdir(parents=True)
            configured.write_bytes(b"configured importer")
            configured.chmod(0o755)
            replacement = root / "replacement"
            replacement.write_bytes(b"replacement executable")
            replacement.chmod(0o755)
            game = root / "game.zip"
            bios = root / "bios.zip"
            executed: list[object] = []
            synthetic = qualification.synthetic_importer_identity(
                str(configured), expected_path=configured,
                expected_sha256=hashlib.sha256(configured.read_bytes()).hexdigest())

            def pairs(_input_root: Path) -> list[tuple[Path, Path]]:
                configured.unlink()
                configured.symlink_to(replacement)
                return [(game, bios)]

            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification, "find_pairs", side_effect=pairs):
                result = qualification.run_selected_qualification(
                    root, str(configured), freshness=lambda: "fresh",
                    execute=lambda *args, **kwargs: executed.append((args, kwargs)),
                    synthetic_identity=synthetic)

            self.assertEqual(result["status"], "importer_identity_rejected")
            self.assertEqual(result["qualifier_build"], "unchecked")
            self.assertEqual(executed, [])

    def test_selected_qualification_rejects_same_path_byte_substitution(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        with tempfile.TemporaryDirectory(prefix="mvs-identity-bytes-selected-") as directory:
            root = Path(directory)
            configured = root / "build" / "owned-debug" / "mvs_importer"
            configured.parent.mkdir(parents=True)
            configured.write_bytes(b"configured importer")
            configured.chmod(0o755)
            expected_identity = {
                "scope": "production", "path": str(configured.resolve()),
                "sha256": hashlib.sha256(configured.read_bytes()).hexdigest(),
            }
            game, bios = root / "game.zip", root / "bios.zip"
            executed: list[object] = []

            class Result:
                def __init__(self, returncode: int, stdout: str = "") -> None:
                    self.returncode = returncode
                    self.stdout = stdout

            class FreshBuild(str):
                def __new__(cls) -> "FreshBuild":
                    result = str.__new__(cls, "fresh")
                    result.importer_identity = expected_identity
                    return result

            def pairs(_input_root: Path) -> list[tuple[Path, Path]]:
                configured.write_bytes(b"same-path substitute")
                return [(game, bios)]

            def execute(command: list[str], **_kwargs: object) -> Result:
                executed.append(command)
                if "--selected" in command:
                    return Result(0)
                return Result(0, '{"status":"attract_start","guest_executed":true,'
                              '"checkpoint":{"user_request":"demo","chunk":1,'
                              '"user_mode_corroborated":true}}')

            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification, "checked_qualifier_command",
                                   return_value="fixture-runner"), \
                 mock.patch.object(qualification, "find_pairs", side_effect=pairs):
                result = qualification.run_selected_qualification(
                    root, str(configured), freshness=FreshBuild,
                    execute=execute)

            self.assertEqual(result["status"], "importer_identity_rejected")
            self.assertEqual(result["qualifier_build"], "unchecked")
            self.assertEqual(executed, [])

    def test_mock_freshness_status_alone_does_not_grant_importer_identity(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        with tempfile.TemporaryDirectory(prefix="mvs-identity-mock-freshness-") as directory:
            root = Path(directory)
            configured = root / "build" / "owned-debug" / "mvs_importer"
            configured.parent.mkdir(parents=True)
            configured.write_bytes(b"configured importer")
            configured.chmod(0o755)
            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured):
                result = qualification.run_selected_qualification(
                    root, str(configured), freshness=lambda: "fresh",
                    execute=lambda *args, **kwargs: self.fail(
                        "a mocked freshness status must not authorize execution"))

            self.assertEqual(result["status"], "importer_identity_rejected")
            self.assertEqual(result["qualifier_build"], "unchecked")

    def test_check_fresh_rejects_same_path_byte_substitution(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        with tempfile.TemporaryDirectory(prefix="mvs-identity-bytes-fresh-") as directory:
            configured = Path(directory) / "build" / "owned-debug" / "mvs_importer"
            qualifier = configured.with_name("mvs_qualify")
            configured.parent.mkdir(parents=True)
            configured.write_bytes(b"configured importer")
            configured.chmod(0o755)

            def replace_bytes(**_kwargs: object) -> bool:
                configured.write_bytes(b"same-path substitute")
                return True

            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification, "CONFIGURED_QUALIFIER_PATH", qualifier), \
                 mock.patch.object(qualification, "qualifier_dry_run_fresh",
                                   side_effect=replace_bytes), \
                 mock.patch.object(qualification.subprocess, "run") as run, \
                 mock.patch("sys.argv", ["qualify_local_boot.py", "--check-fresh",
                                          "--importer", str(configured)]), \
                 io.StringIO() as output, redirect_stdout(output):
                class BuildResult:
                    returncode = 0
                def build(_command: list[str], **_kwargs: object) -> BuildResult:
                    configured.write_bytes(b"rebuilt importer")
                    configured.chmod(0o755)
                    qualifier.write_bytes(b"rebuilt runner")
                    qualifier.chmod(0o755)
                    return BuildResult()
                run.side_effect = build
                exit_code = qualification.main()
                captured = output.getvalue()

            self.assertEqual(exit_code, 1)
            self.assertIn("importer_identity_rejected", captured)
            self.assertNotIn("qualifier fresh", captured)

    def test_negative_controls_reject_same_path_byte_substitution(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        with tempfile.TemporaryDirectory(prefix="mvs-identity-bytes-negative-") as directory:
            root = Path(directory)
            configured = root / "build" / "owned-debug" / "mvs_importer"
            configured.parent.mkdir(parents=True)
            configured.write_bytes(b"configured importer")
            configured.chmod(0o755)
            expected_identity = {
                "scope": "production", "path": str(configured.resolve()),
                "sha256": hashlib.sha256(configured.read_bytes()).hexdigest(),
            }
            report = root / "negative.json"
            executed: list[object] = []

            class FreshBuild(str):
                def __new__(cls) -> "FreshBuild":
                    result = str.__new__(cls, "fresh")
                    result.importer_identity = expected_identity
                    return result

            def pairs(_input_root: Path) -> list[tuple[Path, Path]]:
                configured.write_bytes(b"same-path substitute")
                return [(root / "game.zip", root / "bios.zip")]

            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification, "NEGATIVE_REPORT", report), \
                 mock.patch.object(qualification, "ignored", return_value=True), \
                 mock.patch.object(qualification, "find_pairs", side_effect=pairs), \
                 mock.patch.object(qualification, "run_negative_controls",
                                   side_effect=lambda *args, **kwargs:
                                   executed.append((args, kwargs)) or ({"positive_import": "imported"}, True)):
                result = qualification.negative_controls_main(
                    root, str(configured), freshness=FreshBuild)

            self.assertEqual(result, 1)
            self.assertEqual(executed, [])
            report_path = next(root.glob("negative-*.json"))
            report_data = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report_data["status"], "importer_identity_rejected")
            self.assertEqual(report_data["qualifier_build"], "unchecked")

    def test_negative_controls_recheck_identity_before_each_import(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        with tempfile.TemporaryDirectory(prefix="mvs-identity-negative-boundary-") as directory:
            root = Path(directory)
            configured = root / "mvs_importer"
            configured.write_bytes(b"configured importer")
            configured.chmod(0o755)
            identity = {
                "scope": "production", "path": str(configured.resolve()),
                "sha256": hashlib.sha256(configured.read_bytes()).hexdigest(),
            }
            calls: list[list[str]] = []

            class Result:
                returncode = 0

            def run(command: list[str], **_kwargs: object) -> Result:
                calls.append(command)
                configured.write_bytes(b"same-path substitute")
                return Result()

            check_identity = lambda: qualification.checked_importer_command(
                str(configured), identity=identity) == str(configured.resolve())
            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification.subprocess, "run", side_effect=run):
                with self.assertRaises(qualification.ImporterIdentityChanged):
                    qualification.run_negative_controls(
                        [str(configured)], root / "game.zip", root / "bios.zip",
                        root, identity_check=check_identity)

            self.assertEqual(len(calls), 1)

    def test_check_fresh_and_negative_controls_reject_unchecked_importers(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        with tempfile.TemporaryDirectory(prefix="mvs-identity-entrypoints-") as directory:
            root = Path(directory)
            configured = root / "build" / "owned-debug" / "mvs_importer"
            configured.parent.mkdir(parents=True)
            configured.write_bytes(b"configured importer")
            configured.chmod(0o755)
            wrapper = root / "wrapper"
            wrapper.write_bytes(b"wrapper")
            wrapper.chmod(0o755)

            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification, "qualifier_dry_run_fresh", return_value=True), \
                 mock.patch("sys.argv", ["qualify_local_boot.py", "--check-fresh", "--importer", str(wrapper)]), \
                 io.StringIO() as output, redirect_stdout(output):
                self.assertEqual(qualification.main(), 1)
                self.assertIn("importer_identity_rejected", output.getvalue())
                self.assertNotIn("qualifier fresh", output.getvalue())

            report = root / "negative.json"
            executed: list[object] = []
            with mock.patch.object(qualification, "CONFIGURED_IMPORTER_PATH", configured), \
                 mock.patch.object(qualification, "NEGATIVE_REPORT", report), \
                 mock.patch.object(qualification, "ignored", return_value=True), \
                 mock.patch.object(qualification, "find_pairs", return_value=[(root / "game.zip", root / "bios.zip")]), \
                 mock.patch.object(qualification, "run_negative_controls", side_effect=lambda *args, **kwargs: executed.append(args)), \
                 mock.patch.object(qualification, "write_report", wraps=qualification.write_report):
                result = qualification.negative_controls_main(root, str(wrapper), freshness=lambda: "fresh")

            self.assertEqual(result, 1)
            self.assertEqual(executed, [])
            report_path = next(root.glob("negative-*.json"))
            report_data = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report_data["status"], "importer_identity_rejected")
            self.assertEqual(report_data["qualifier_build"], "unchecked")
            self.assertNotIn(str(root), report_path.read_text(encoding="utf-8"))

    def test_synthetic_importer_identity_requires_exact_path_and_digest(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        with tempfile.TemporaryDirectory(prefix="mvs-synthetic-identity-") as directory:
            executable = Path(directory) / "synthetic-importer"
            executable.write_bytes(b"synthetic importer bytes")
            executable.chmod(0o755)
            expected_digest = hashlib.sha256(executable.read_bytes()).hexdigest()
            identity = qualification.synthetic_importer_identity(
                str(executable), expected_path=executable, expected_sha256=expected_digest)
            self.assertEqual(identity["importer_identity_scope"], "synthetic")
            self.assertEqual(identity["synthetic_importer_identity"], {
                "path": str(executable.resolve()), "sha256": expected_digest})
            self.assertIsNone(qualification.synthetic_importer_identity(
                str(executable), expected_path=executable, expected_sha256="0" * 64))
            self.assertIsNone(qualification.synthetic_importer_identity(
                [str(executable), "--wrapper"], expected_path=executable,
                expected_sha256=expected_digest))

    def test_source_gate_uses_exact_required_ids_and_rejects_duplicates(self) -> None:
        from tools.mvs import check_sources

        def run_gate(ids: list[str], required: str) -> tuple[int, str]:
            with tempfile.TemporaryDirectory(prefix="mvs-source-id-") as directory:
                doc = Path(directory) / "sources.md"
                row = "| {id} | element | https://example.invalid/source | 2026-10-13 | {digest} | excerpt | text | class |\n"
                doc.write_text("".join(row.format(id=sid, digest="0" * 64) for sid in ids),
                               encoding="utf-8")
                output = io.StringIO()
                with mock.patch.object(check_sources, "check_row", return_value=None), \
                     mock.patch("sys.argv", ["check_sources.py", "--doc", str(doc), "--require", required]), \
                     redirect_stdout(output):
                    result = check_sources.main()
                return result, output.getvalue()

        self.assertEqual(run_gate(["S1"], "S1")[0], 0)
        suffix_only, suffix_output = run_gate(["S1b"], "S1")
        self.assertEqual(suffix_only, 1)
        self.assertIn("S1 missing", suffix_output)
        absent, absent_output = run_gate(["S2"], "S1")
        self.assertEqual(absent, 1)
        self.assertIn("S1 missing", absent_output)
        duplicate, duplicate_output = run_gate(["S1", "S1"], "S1")
        self.assertEqual(duplicate, 1)
        self.assertIn("S1 duplicate", duplicate_output)

    def test_source_gate_keeps_digest_and_excerpt_checks(self) -> None:
        from tools.mvs import check_sources

        body = b"immutable source excerpt"
        digest = hashlib.sha256(body).hexdigest()
        cells = ["S1", "element", "https://raw.githubusercontent.com/o/r/" + "a" * 40 + "/file",
                 "2026-10-13", digest, "excerpt", "immutable source excerpt", "class"]
        with mock.patch.object(check_sources, "fetch", return_value=(body, None)):
            self.assertIsNone(check_sources.check_row(cells, {}))
            self.assertEqual(check_sources.check_row([*cells[:4], "0" * 64, *cells[5:]], {}),
                             "digest_mismatch")
            self.assertEqual(check_sources.check_row([*cells[:6], "absent text", cells[7]], {}),
                             "excerpt_absent")

    def run_import(self, source: bytes) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="mvs-test-") as directory:
            input_path = os.path.join(directory, "synthetic.zip")
            output_path = os.path.join(directory, "normalized.gnmv")
            with open(input_path, "wb") as handle:
                handle.write(source)
            return subprocess.run(
                [self.importer, input_path, output_path], text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )

    def test_deflated_archive_normalizes_selected_profile(self) -> None:
        source = make_archive()
        with tempfile.TemporaryDirectory(prefix="mvs-test-") as directory:
            input_path = os.path.join(directory, "input.zip")
            output_path = os.path.join(directory, "output.gnmv")
            with open(input_path, "wb") as handle:
                handle.write(source)
            checked = subprocess.run([self.importer, input_path, output_path],
                                     capture_output=True, text=True, check=False)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            with open(output_path, "rb") as handle:
                bundle = handle.read()
        self.assertEqual(bundle[:4], b"GNMV")
        self.assertEqual(struct.unpack_from(">III", bundle, 4),
                         (1, 0x4D53584D, 6))
        cursor = 16
        for role, expected_size in enumerate(SIZES, 1):
            actual_role, actual_size = struct.unpack_from(">IQ", bundle, cursor)
            self.assertEqual((actual_role, actual_size), (role, expected_size))
            cursor += 12 + actual_size
        self.assertEqual(cursor, len(bundle))

    def test_optional_audio_bios_emits_v2_bundle_and_preserves_exact_bytes(self) -> None:
        # Rights-safe synthetic payload: unique from the six other regions and
        # never presented as an authentic BIOS image.
        audio_bios = bytes([0xA7]) * AUDIO_BIOS_SIZE
        source = make_archive(audio_bios=audio_bios)
        with tempfile.TemporaryDirectory(prefix="mvs-test-audio-bios-") as directory:
            input_path = os.path.join(directory, "input.zip")
            output_path = os.path.join(directory, "output.gnmv")
            with open(input_path, "wb") as handle:
                handle.write(source)
            checked = subprocess.run([self.importer, input_path, output_path],
                                     capture_output=True, text=True, check=False)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            with open(output_path, "rb") as handle:
                bundle = handle.read()
        self.assertEqual(bundle[:4], b"GNMV")
        self.assertEqual(struct.unpack_from(">III", bundle, 4),
                         (2, 0x4D53584D, 7))
        cursor = 16
        regions: dict[int, bytes] = {}
        for role, expected_size in enumerate((*SIZES, AUDIO_BIOS_SIZE), 1):
            actual_role, actual_size = struct.unpack_from(">IQ", bundle, cursor)
            self.assertEqual((actual_role, actual_size), (role, expected_size))
            cursor += 12
            regions[role] = bundle[cursor:cursor + actual_size]
            cursor += actual_size
        self.assertEqual(cursor, len(bundle))
        self.assertEqual(regions[7], audio_bios)

    def test_optional_audio_bios_rejects_wrong_size_and_duplicate_role(self) -> None:
        cases = (
            ("audio_bios_size", make_archive(audio_bios=bytes(AUDIO_BIOS_SIZE + 1)), 3),
            ("audio_bios_duplicate", make_archive(
                audio_bios=bytes(AUDIO_BIOS_SIZE), duplicate_audio_bios=True), 7),
        )
        for label, archive, expected in cases:
            with self.subTest(label=label):
                result = self.run_import(archive)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn("/", result.stderr)
                self.assertNotIn(".bin", result.stderr)

    def test_selected_split_archives_normalize_exact_mslugx_map(self) -> None:
        game, bios = make_split_archives()
        with tempfile.TemporaryDirectory(prefix="mvs-split-test-") as directory:
            game_path = os.path.join(directory, "game.zip")
            bios_path = os.path.join(directory, "bios.zip")
            output_path = os.path.join(directory, "selected.gnmv")
            with open(game_path, "wb") as handle:
                handle.write(game)
            with open(bios_path, "wb") as handle:
                handle.write(bios)
            checked = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            with open(output_path, "rb") as handle:
                bundle = handle.read()
            runner = str(Path(self.production_importer).resolve().parent / "mvs_qualify")
            execution = subprocess.run([runner, output_path], capture_output=True,
                                       text=True, check=False)
            # The six-region legacy contract loads, then explicitly stops
            # before guest execution because reset selects its absent audio BIOS.
            self.assertEqual(execution.returncode, 0, execution.stdout)
            self.assertEqual(execution.stdout.strip(),
                             '{"status":"missing_audio_region"}')
        self.assertEqual(bundle[:4], b"GNMV")
        self.assertEqual(struct.unpack_from(">III", bundle, 4),
                         (1, 0x4D53584D, 6))
        cursor = 16
        for role, expected_size in enumerate(SIZES, 1):
            actual_role, actual_size = struct.unpack_from(">IQ", bundle, cursor)
            self.assertEqual((actual_role, actual_size), (role, expected_size))
            cursor += 12 + actual_size
        self.assertEqual(cursor, len(bundle))
        regions: dict[int, bytes] = {}
        cursor = 16
        for role in range(1, 7):
            _, length = struct.unpack_from(">IQ", bundle, cursor)
            cursor += 12
            regions[role] = bundle[cursor:cursor + length]
            cursor += length
        self.assertEqual(regions[1][:8], bytes.fromhex("0010fffe00000100"))
        self.assertEqual(regions[1][0x100:0x10C], bytes.fromhex("725a33c1001000004e722700"))
        self.assertEqual(regions[2][0x100000:0x100004], bytes.fromhex("12121212"))
        self.assertEqual(regions[3][:4], bytes.fromhex("13131313"))
        self.assertEqual(regions[4][:4], bytes.fromhex("14141414"))
        self.assertEqual(regions[5][:4], bytes.fromhex("15151515"))
        self.assertEqual(regions[5][0x400000:0x400004], bytes.fromhex("16161616"))
        self.assertEqual(regions[5][0x800000:0x800004], bytes.fromhex("17171717"))
        self.assertEqual(regions[6][:4], bytes.fromhex("18191819"))
        self.assertEqual(regions[6][1:5], bytes.fromhex("19181918"))

    def test_selected_optional_audio_bios_emits_v2_bundle_and_loads(self) -> None:
        # Synthetic fixture identity deliberately bypasses only public BIOS
        # hashes; this verifies optional-region transport and loader handling.
        audio_bios = bytes([0xA7]) * AUDIO_BIOS_SIZE
        game, bios = make_split_archives(
            attract_guest=True,
            bios_extras=(("sm1.sm1", audio_bios),))
        with tempfile.TemporaryDirectory(prefix="mvs-selected-audio-bios-") as directory:
            game_path = os.path.join(directory, "game.zip")
            bios_path = os.path.join(directory, "bios.zip")
            output_path = os.path.join(directory, "selected.gnmv")
            for path, payload in ((game_path, game), (bios_path, bios)):
                with open(path, "wb") as handle:
                    handle.write(payload)
            checked = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            bundle = Path(output_path).read_bytes()
            runner = str(Path(self.production_importer).resolve().parent / "mvs_qualify")
            execution = subprocess.run([runner, output_path], capture_output=True,
                                       text=True, check=False)
        self.assertEqual(struct.unpack_from(">III", bundle, 4),
                         (2, 0x4D53584D, 7))
        cursor = 16
        regions: dict[int, bytes] = {}
        for role, expected_size in enumerate((*SIZES, AUDIO_BIOS_SIZE), 1):
            actual_role, actual_size = struct.unpack_from(">IQ", bundle, cursor)
            self.assertEqual((actual_role, actual_size), (role, expected_size))
            cursor += 12
            regions[role] = bundle[cursor:cursor + actual_size]
            cursor += actual_size
        self.assertEqual(cursor, len(bundle))
        self.assertEqual(regions[7], audio_bios)
        self.assertEqual(execution.returncode, 0, execution.stdout)
        self.assertNotIn('"status":"normalized_bundle_unavailable"', execution.stdout)
        self.assertIn('"guest_executed":true', execution.stdout)

    def test_selected_zoom_table_emits_v3_with_optional_audio_role_and_loads(self) -> None:
        zoom_table = bytes((index * 13 + 7) & 0xff for index in range(Y_ZOOM_SIZE))
        audio_bios = bytes([0xA7]) * AUDIO_BIOS_SIZE
        runner = str(Path(self.production_importer).resolve().parent / "mvs_qualify")
        for extras, expected_roles in (
            (((Y_ZOOM_NAME, zoom_table),), (1, 2, 3, 4, 5, 6, 8)),
            ((("sm1.sm1", audio_bios), (Y_ZOOM_NAME, zoom_table)),
             (1, 2, 3, 4, 5, 6, 7, 8)),
        ):
            with self.subTest(role_count=len(expected_roles)), \
                 tempfile.TemporaryDirectory(prefix="mvs-selected-v3-") as directory:
                game, bios = make_split_archives(
                    attract_guest=True, bios_extras=extras)
                game_path = os.path.join(directory, "game.zip")
                bios_path = os.path.join(directory, "bios.zip")
                output_path = os.path.join(directory, "selected.gnmv")
                for path, payload in ((game_path, game), (bios_path, bios)):
                    with open(path, "wb") as handle:
                        handle.write(payload)
                checked = subprocess.run(
                    [self.importer, "--selected", game_path, bios_path,
                     output_path], capture_output=True, text=True, check=False)
                self.assertEqual(checked.returncode, 0, checked.stderr)
                bundle = Path(output_path).read_bytes()
                execution = subprocess.run(
                    [runner, output_path], capture_output=True,
                    text=True, check=False)
            self.assertEqual(struct.unpack_from(">III", bundle, 4),
                             (3, 0x4D53584D, len(expected_roles)))
            cursor = 16
            regions: dict[int, bytes] = {}
            for role in expected_roles:
                actual_role, actual_size = struct.unpack_from(">IQ", bundle, cursor)
                self.assertEqual(actual_role, role)
                cursor += 12
                self.assertEqual(actual_size, Y_ZOOM_SIZE if role == 8 else
                                 AUDIO_BIOS_SIZE if role == 7 else SIZES[role - 1])
                regions[role] = bundle[cursor:cursor + actual_size]
                cursor += actual_size
            self.assertEqual(cursor, len(bundle))
            self.assertEqual(regions[8], zoom_table)
            if 7 in regions:
                self.assertEqual(regions[7], audio_bios)
            self.assertEqual(execution.returncode, 0, execution.stdout)
            self.assertIn('"guest_executed":true', execution.stdout)

    def test_selected_zoom_table_wrong_size_and_duplicate_reject(self) -> None:
        cases = (
            ("zoom_size", ((Y_ZOOM_NAME, bytes(Y_ZOOM_SIZE + 1)),), 13),
            ("zoom_duplicate", ((Y_ZOOM_NAME, bytes(Y_ZOOM_SIZE)),
                                 (Y_ZOOM_NAME, bytes(Y_ZOOM_SIZE))), 7),
        )
        for label, extras, expected in cases:
            with self.subTest(label=label), \
                 tempfile.TemporaryDirectory(prefix="mvs-selected-v3-invalid-") as directory:
                game, bios = make_split_archives(bios_extras=extras)
                game_path = os.path.join(directory, "game.zip")
                bios_path = os.path.join(directory, "bios.zip")
                output_path = os.path.join(directory, "selected.gnmv")
                for path, payload in ((game_path, game), (bios_path, bios)):
                    with open(path, "wb") as handle:
                        handle.write(payload)
                checked = subprocess.run(
                    [self.importer, "--selected", game_path, bios_path,
                     output_path], capture_output=True, text=True, check=False)
            self.assertEqual(checked.returncode, expected, checked.stderr)
            self.assertEqual(checked.stderr.strip(), IMPORT_MESSAGE[
                "zoom_incompatible" if expected == 13 else "ambiguous"])

    def test_production_importer_rejects_wrong_zoom_table_identity(self) -> None:
        game, _ = make_split_archives()
        # Put the optional board source first so this control reaches its
        # production CRC/SHA check before the synthetic main-BIOS identity.
        bios_stream = io.BytesIO()
        with zipfile.ZipFile(bios_stream, "w", compression=zipfile.ZIP_STORED,
                             allowZip64=False) as archive:
            archive.writestr(Y_ZOOM_NAME, bytes(Y_ZOOM_SIZE))
            archive.writestr(BIOS_MEMBER, bytes(0x20000))
        with tempfile.TemporaryDirectory(prefix="mvs-wrong-zoom-id-") as directory:
            game_path = os.path.join(directory, "game.zip")
            bios_path = os.path.join(directory, "bios.zip")
            output_path = os.path.join(directory, "selected.gnmv")
            for path, payload in ((game_path, game),
                                  (bios_path, bios_stream.getvalue())):
                with open(path, "wb") as handle:
                    handle.write(payload)
            checked = subprocess.run(
                [self.production_importer, "--selected", game_path,
                 bios_path, output_path], capture_output=True, text=True,
                check=False)
        self.assertEqual(checked.returncode, IMPORT_EXIT["zoom_incompatible"])
        self.assertEqual(checked.stderr.strip(), IMPORT_MESSAGE["zoom_incompatible"])

    def test_selected_bios_ignores_flat_bounded_extras_after_crc_validation(self) -> None:
        extras = (("synthetic-extra-a.bin", b"extra-a" * 64),
                  ("synthetic-extra-b.dat", b"extra-b" * 32))
        game, bios = make_split_archives(bios_extras=extras)
        with tempfile.TemporaryDirectory(prefix="mvs-split-test-") as directory:
            game_path, bios_path = (os.path.join(directory, name)
                                    for name in ("game.zip", "bios.zip"))
            output_path = os.path.join(directory, "selected.gnmv")
            for path, payload in ((game_path, game), (bios_path, bios)):
                with open(path, "wb") as handle:
                    handle.write(payload)
            checked = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertTrue(Path(output_path).is_file())

    def test_selected_bios_allows_deflate_hints_only_on_deflated_members(self) -> None:
        game, bios = make_split_archives(
            bios_extras=(("synthetic-compressed.deflated", b"extra" * 128),))
        accepted = mutate_member_flags(bios, "synthetic-compressed.deflated", 0x0006)
        rejected = mutate_member_flags(bios, BIOS_MEMBER, 0x0002)
        for candidate, should_pass in ((accepted, True), (rejected, False)):
            with tempfile.TemporaryDirectory(prefix="mvs-split-test-") as directory:
                game_path, bios_path = (os.path.join(directory, name)
                                        for name in ("game.zip", "bios.zip"))
                output_path = os.path.join(directory, "selected.gnmv")
                for path, payload in ((game_path, game), (bios_path, candidate)):
                    with open(path, "wb") as handle:
                        handle.write(payload)
                checked = subprocess.run(
                    [self.importer, "--selected", game_path, bios_path, output_path],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(checked.returncode == 0, should_pass, checked.stderr)
                self.assertEqual(Path(output_path).exists(), should_pass)

    def test_classifier_structure_rejects_zip64_extra_fields(self) -> None:
        target = io.BytesIO()
        info = zipfile.ZipInfo("synthetic-flat.bin")
        info.extra = struct.pack("<HHQ", 1, 8, 0)
        with zipfile.ZipFile(target, "w", allowZip64=False) as archive:
            archive.writestr(info, b"synthetic")
        with zipfile.ZipFile(io.BytesIO(target.getvalue())) as archive:
            self.assertFalse(_archive_structure_valid(archive, archive.infolist()))

    def test_classifier_candidate_requires_exact_central_extent(self) -> None:
        with zipfile.ZipFile(io.BytesIO(make_archive()), "r") as archive:
            entries = archive.infolist()
            archive.fp.seek(0, 2)
            total_size = archive.fp.tell()
            tail_len = min(total_size, 65557)
            archive.fp.seek(total_size - tail_len)
            tail = archive.fp.read(tail_len)
            pos = tail.rfind(b"PK\x05\x06")
            _, _, _, _, central_size, central_offset, _ = struct.unpack_from(
                "<HHHHIIH", tail, pos + 4)
            actual_end = total_size - tail_len + pos
            self.assertTrue(_central_directory_matches(archive, entries, actual_end))
            self.assertFalse(_central_directory_matches(
                archive, entries, central_offset + central_size + 1))

    def test_classifier_pair_respects_combined_import_limit(self) -> None:
        cap = 128 * 1024 * 1024
        self.assertTrue(pair_fits_import_limits(96 * 1024 * 1024,
                                                32 * 1024 * 1024, cap, 0))
        self.assertFalse(pair_fits_import_limits(96 * 1024 * 1024,
                                                 32 * 1024 * 1024 + 1, cap, 0))
        self.assertFalse(pair_fits_import_limits(96 * 1024 * 1024 + 1, 1, 0, 0))
        self.assertFalse(pair_fits_import_limits(1, 1, cap, 1))

    def test_budget_result_keeps_only_bounded_private_diagnostic_fields(self) -> None:
        safe = safe_result({
            "status": "guest_instruction_budget_exhausted",
            "guest_executed": True,
            "last_execution": {"pc": 0x1234, "opcode": 0x4E71, "instructions": 17,
                               "elapsed_cycles": 128000000,
                               "mame_watchdog_reset_count": 2},
            "recent_fetches": [{"pc": 0x1234, "word": 0x4E71,
                                "cursor": 0x1236, "run": 11, "cycles": 64}],
            "profile": {"chunks": 256, "stable_chunks": 249,
                        "output_transition_chunks": 3,
                        "video_transition_chunks": 4,
                        "bank_transition_chunks": 0,
                        "watchdog_pet_count": 129,
                        "watchdog_reset_count": 0,
                        "repeated_boundary_suffix": True,
                        "private_registers": [1, 2, 3]},
            "private_identity_recorded": True,
            "archive_path": "synthetic-private-path",
        })
        self.assertEqual(safe["status"], "guest_instruction_budget_exhausted")
        self.assertIs(safe["guest_executed"], True)
        self.assertIs(safe["private_identity_recorded"], False)
        self.assertEqual(safe["last_execution"], {
            "pc": 0x1234, "opcode": 0x4E71, "instructions": 17,
            "elapsed_cycles": 128000000,
            "mame_watchdog_reset_count": 2,
        })
        self.assertEqual(safe["recent_fetches"], [{
            "pc": 0x1234, "word": 0x4E71, "cursor": 0x1236,
            "run": 11, "cycles": 64,
        }])
        self.assertEqual(safe["profile"], {
            "chunks": 256, "stable_chunks": 249,
            "output_transition_chunks": 3,
            "video_transition_chunks": 4,
            "bank_transition_chunks": 0,
            "watchdog_pet_count": 129,
            "watchdog_reset_count": 0,
            "repeated_boundary_suffix": True,
        })

    def test_selected_acceptance_keeps_independent_predicates_and_publicly_projects_tokens(self) -> None:
        outcomes = {
            "selected_import": "pass",
            "native_guest": "pass",
            "actual_frontend": "pass",
            "recognizable_title": "pass",
            "identity": "pass",
            "overall": "pass",
        }
        report = {
            "status": "attract_start",
            "guest_executed": True,
            "checkpoint": {"user_request": "title", "chunk": 1,
                           "user_mode_corroborated": True},
            "acceptance": outcomes,
            "private_identity": {"path": "/private/roms/source.zip",
                                 "sha256": "private-content-digest"},
            "archive_path": "/private/roms/source.zip",
            "private_registers": [0x1234],
        }

        # Producer JSON cannot self-assert the wrapper's acceptance predicates.
        self.assertNotIn("acceptance", safe_result(report))
        safe = safe_result(report, acceptance=outcomes)
        public = public_result(report, acceptance=outcomes)

        self.assertEqual(safe.get("acceptance"), outcomes)
        self.assertEqual(public.get("acceptance"), outcomes)
        serialized = json.dumps(public)
        self.assertNotIn("/private/roms", serialized)
        self.assertNotIn("private-content-digest", serialized)
        self.assertNotIn("archive_path", safe)
        self.assertNotIn("private_registers", serialized)
        for predicate in (
                "selected_import", "native_guest", "actual_frontend",
                "recognizable_title", "identity"):
            for value, expected in (("fail", "fail"), ("unknown", "unknown")):
                with self.subTest(predicate=predicate, value=value):
                    partial = {**outcomes, predicate: value,
                               "overall": "fail" if value == "fail" else "unknown"}
                    projected = safe_result(report, acceptance=partial)
                    self.assertEqual(projected.get("acceptance"), partial)
        inconsistent = {**outcomes, "actual_frontend": "fail"}
        self.assertNotIn("acceptance", safe_result(report, acceptance=inconsistent))
        spoofed = safe_result({
            "status": "attract_start", "guest_executed": True,
            "checkpoint": "private guest signal",
        })
        self.assertEqual(spoofed["status"], "native_qualification_failed")
        self.assertIsNot(spoofed.get("guest_executed"), True)
        self.assertNotIn("checkpoint", spoofed)

    def test_manual_visual_title_review_resolves_only_bound_unknown(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        make_review = getattr(qualification, "make_manual_visual_title_review", None)
        resolve_review = getattr(qualification, "resolve_manual_visual_title_review", None)
        self.assertTrue(callable(make_review),
                        "maintained visual-review record builder is required")
        self.assertTrue(callable(resolve_review),
                        "maintained visual-review validator is required")

        Path("local/qualification").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir="local/qualification") as temporary:
            capture = Path(temporary) / "frame.png"
            capture.write_bytes(b"synthetic capture identity")
            capture_sha = hashlib.sha256(capture.read_bytes()).hexdigest()
            config_text = 'video_driver = "gl"\n'
            config_hash = hashlib.sha256(config_text.encode()).hexdigest()
            archive_identity = [{"sha256": "e" * 64}]
            machine = {
                "selected_import": "pass", "native_guest": "pass",
                "actual_frontend": "pass", "recognizable_title": "unknown",
                "identity": "pass", "overall": "unknown",
            }
            private = {
                "acceptance_predicates": machine,
                "frontend_result": {
                    "actual_frontend": "pass", "recognizable_title": "unknown",
                    "reported_status": "pass",
                },
                "frontend_smoke": {
                    "capture_paths": [str(capture)],
                    "capture_sha256": [capture_sha],
                    "capture_geometry": [[320, 224]],
                    "frontend_exit_code": 0,
                    "frontend_log_status": "pass",
                    "selected_bundle_sha256": "d" * 64,
                    "configuration_sha256": config_hash,
                    "configuration_text": config_text,
                    "frontend_command": ["retroarch", "selected-mvs"],
                    "identity": {
                        "content_kind": "selected-mvs",
                        "core_sha256": "a" * 64,
                        "retroarch_executable_sha256": "b" * 64,
                        "retroarch_version": "1.22.2",
                    },
                },
                "native_command": ["native", "selected-mvs"],
                "importer_command": ["importer", "selected-mvs"],
                "input_archive_identities_before": archive_identity,
                "input_archive_identities_after_import": archive_identity,
                "input_archive_identities_after_frontend": archive_identity,
                "input_archive_identities_after_run": archive_identity,
                "normalized_bundle_identity": {"sha256": "d" * 64},
                "importer_identity": {"scope": "production"},
                "qualifier_identity": {"scope": "production"},
            }
            with mock.patch.object(qualification, "ignored", return_value=True):
                review = make_review(private, user_live_corroboration=True)
                self.assertIsNotNone(review)
                self.assertEqual(review["method"], "direct_visual_inspection")
                self.assertEqual(review["source"], "agent_visual_inspection")
                self.assertTrue(review["user_live_corroboration"])
                self.assertFalse(review["user_saw_exact_capture"])
                self.assertEqual(review["automated_title_ocr"], "unknown")
                resolved = resolve_review(machine, private, review)
                self.assertEqual(resolved["recognizable_title"], "pass")
                self.assertEqual(resolved["overall"], "pass")
                self.assertEqual(machine["recognizable_title"], "unknown")
                wrong_title_review = make_review(private, outcome="fail")
                self.assertEqual(
                    resolve_review(machine, private, wrong_title_review)[
                        "recognizable_title"], "fail")

                changed_capture = dict(private)
                changed_frontend = dict(private["frontend_smoke"])
                changed_frontend["capture_sha256"] = ["e" * 64]
                changed_capture["frontend_smoke"] = changed_frontend
                self.assertIsNone(resolve_review(machine, changed_capture, review))

                changed_core = dict(private)
                changed_frontend = dict(private["frontend_smoke"])
                changed_identity = dict(changed_frontend["identity"])
                changed_identity["core_sha256"] = "f" * 64
                changed_frontend["identity"] = changed_identity
                changed_core["frontend_smoke"] = changed_frontend
                self.assertIsNone(resolve_review(machine, changed_core, review))

                failed = {**machine, "recognizable_title": "fail", "overall": "fail"}
                failed_private = dict(private)
                failed_private["acceptance_predicates"] = failed
                failed_private["frontend_result"] = {
                    **private["frontend_result"], "recognizable_title": "fail",
                }
                self.assertIsNone(resolve_review(failed, failed_private, review))

                other_failure = {**machine, "selected_import": "fail", "overall": "fail"}
                self.assertIsNone(resolve_review(other_failure, private, review))

                changed_archive = dict(private)
                changed_archive["input_archive_identities_after_frontend"] = [
                    {"sha256": "f" * 64}]
                self.assertIsNone(make_review(changed_archive),
                                  "a title review cannot conceal changed inputs")

                evidence_path = Path("local/qualification") / (
                    f"phase05-{uuid.uuid4().hex}-private.json")
                review_path = qualification.private_visual_review_path(evidence_path)
                self.assertIsNotNone(review_path)
                try:
                    evidence_path.write_text(json.dumps(private), encoding="utf-8")
                    with mock.patch.object(qualification, "ignored", return_value=True):
                        recorded = qualification.record_manual_visual_title_review(
                            evidence_path, user_live_corroboration=True)
                        self.assertIsNotNone(recorded)
                        self.assertEqual(
                            recorded["machine_acceptance"]["recognizable_title"],
                            "unknown")
                        self.assertEqual(
                            recorded["reviewed_acceptance"]["recognizable_title"],
                            "pass")
                        self.assertTrue(review_path.is_file())
                        self.assertEqual(
                            json.loads(review_path.read_text(encoding="utf-8"))["automated_title_ocr"],
                            "unknown")
                        self.assertIsNone(qualification.record_manual_visual_title_review(
                            evidence_path, user_live_corroboration=True),
                            "a review sidecar must never replace prior evidence")
                        review_path.unlink()
                        output = io.StringIO()
                        with mock.patch("sys.argv", [
                                "qualify_local_boot.py", "--record-title-review",
                                evidence_path.as_posix(), "--title-review-outcome", "pass",
                                "--user-live-corroboration"]), \
                             redirect_stdout(output):
                            self.assertEqual(qualification.main(), 0)
                        cli_result = json.loads(output.getvalue())
                        self.assertEqual(
                            cli_result["machine_acceptance"]["recognizable_title"],
                            "unknown")
                        self.assertEqual(
                            cli_result["reviewed_acceptance"]["recognizable_title"],
                            "pass")
                        self.assertTrue(cli_result["review_recorded"])
                        self.assertTrue(review_path.is_file())
                        review_path.unlink()

                        output = io.StringIO()
                        with mock.patch.object(qualification, "ignored", return_value=False), \
                             mock.patch("sys.argv", [
                                 "qualify_local_boot.py", "--record-title-review",
                                 evidence_path.as_posix(), "--title-review-outcome", "pass"]), \
                             redirect_stdout(output):
                            self.assertEqual(qualification.main(), 2)
                        self.assertFalse(review_path.exists())
                finally:
                    evidence_path.unlink(missing_ok=True)
                    if review_path is not None:
                        review_path.unlink(missing_ok=True)

                capture.write_bytes(b"replacement capture bytes")
                self.assertIsNone(resolve_review(machine, private, review))

    def test_selected_native_acceptance_requires_complete_600_frame_window(self) -> None:
        from tools.mvs import qualify_local_boot as qualification

        native = {"status": "attract_start", "guest_executed": True,
                  "video_advance_requested": 600,
                  "video_advance_completed": 600}
        frontend = {"actual_frontend": "pass", "recognizable_title": "pass"}
        common = {"selected_import_ok": True, "frontend_result": frontend,
                  "identity_ok": True}
        self.assertEqual(
            qualification.evaluate_acceptance_predicates(
                native_result=native, **common)["native_guest"], "pass")
        self.assertEqual(
            qualification.evaluate_acceptance_predicates(
                native_result={**native, "video_advance_completed": 599},
                **common)["native_guest"], "fail")
        self.assertEqual(
            qualification.evaluate_acceptance_predicates(
                native_result={"status": "attract_start", "guest_executed": True},
                **common)["native_guest"], "unknown")

    def test_synthetic_handoff_reaches_attract_start_through_real_qualifier(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        game, bios = make_split_archives(
            attract_guest=True, attract_loop=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        with tempfile.TemporaryDirectory(prefix="mvs-attract-test-") as directory:
            game_path = os.path.join(directory, "game.zip")
            bios_path = os.path.join(directory, "bios.zip")
            output_path = os.path.join(directory, "selected.gnmv")
            with open(game_path, "wb") as handle:
                handle.write(game)
            with open(bios_path, "wb") as handle:
                handle.write(bios)
            checked = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            runner = str(Path(self.production_importer).resolve().parent / "mvs_qualify")
            missing_bundle = subprocess.run([runner], capture_output=True,
                                            text=True, check=False)
            execution = subprocess.run([runner, output_path], capture_output=True,
                                       text=True, check=False)
            advanced = subprocess.run(
                [runner, output_path, "--video-advance-frames", "1"],
                capture_output=True, text=True, check=False)
            scripted = subprocess.run(
                [runner, output_path, "--input-script", "coin@1,start@2"],
                capture_output=True, text=True, check=False)
            for invalid in ("coin@0,start@2", "coin@2,start@2",
                            "coin@1,start@1201", "coin@1,start@2x"):
                rejected = subprocess.run(
                    [runner, output_path, "--input-script", invalid],
                    capture_output=True, text=True, check=False)
                self.assertEqual(rejected.returncode, 2, invalid)
                self.assertEqual(rejected.stdout, "", invalid)
            self.assertEqual(missing_bundle.returncode, 2)
            self.assertEqual(missing_bundle.stdout, "")
            outside = Path(directory) / "outside"
            outside.mkdir()
            for suffix, parent_link in (
                    ("a", Path(directory) / "symlinked-local"),
                    ("b", Path(directory) / "nested-symlink")):
                frame_cwd = Path(directory) / f"frame-root-{suffix}"
                frame_cwd.mkdir()
                if suffix == "a":
                    (frame_cwd / "local").symlink_to(outside, target_is_directory=True)
                else:
                    local_dir = frame_cwd / "local"
                    local_dir.mkdir()
                    (local_dir / "qualification").symlink_to(
                        outside, target_is_directory=True)
                token = "a" * 32 if suffix == "a" else "b" * 32
                private_path = f"local/qualification/phase05-{token}.ppm"
                rejected_path = subprocess.run(
                    [runner, output_path, "--frame-output", private_path],
                    cwd=frame_cwd, capture_output=True, text=True, check=False)
                self.assertEqual(rejected_path.returncode, 2, suffix)
                self.assertEqual(rejected_path.stdout, "", suffix)
            self.assertEqual(list(outside.glob("phase05-*.ppm")), [])
            for invalid in ("0", "601", "-1", "1x"):
                rejected = subprocess.run(
                    [runner, output_path, "--video-advance-frames", invalid],
                    capture_output=True, text=True, check=False)
                self.assertEqual(rejected.returncode, 2, invalid)
                self.assertEqual(rejected.stdout, "", invalid)
            combined = subprocess.run(
                [runner, output_path, "--input-script", "coin@1,start@2",
                 "--video-advance-frames", "1"],
                capture_output=True, text=True, check=False)
            self.assertEqual(combined.returncode, 2)
            self.assertEqual(combined.stdout, "")
            # Reuse the same synthetic auxiliary members for both paths.
            with zipfile.ZipFile(io.BytesIO(bios)) as archive:
                extras = tuple((name, archive.read(name))
                               for name in archive.namelist() if name != BIOS_MEMBER)
            timeout_game, timeout_bios = make_split_archives(
                attract_guest=True, attract_loop=True, attract_timeout=True,
                bios_extras=extras)
            Path(game_path).write_bytes(timeout_game)
            Path(bios_path).write_bytes(timeout_bios)
            timeout_import = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False)
            self.assertEqual(timeout_import.returncode, 0, timeout_import.stderr)
            timeout_frame_root = Path(directory) / "timeout-frame-root"
            timeout_frame_directory = timeout_frame_root / "local" / "qualification"
            timeout_frame_directory.mkdir(parents=True)
            timeout_frame_name = "local/qualification/phase05-" + "e" * 32 + ".ppm"
            timeout_execution = subprocess.run(
                [runner, output_path, "--input-script", "coin@1,start@2",
                 "--frame-output", timeout_frame_name], cwd=timeout_frame_root,
                capture_output=True, text=True, check=False)
            self.assertEqual(timeout_execution.returncode, 0, timeout_execution.stdout)
            timeout_report = json.loads(timeout_execution.stdout)
            self.assertEqual(timeout_report["input_response"], "not_observed")
            self.assertIs(timeout_report["frame_output_written"], True)
            self.assertTrue(qualification.private_frame_is_valid(
                timeout_frame_directory / Path(timeout_frame_name).name))
        self.assertEqual(execution.returncode, 0, execution.stdout)
        self.assertEqual(
            execution.stdout.strip(),
            '{"status":"attract_start","guest_executed":true,"checkpoint":'
            '{"user_request":"demo","chunk":1,"user_mode_corroborated":true}}')
        self.assertEqual(advanced.returncode, 0, advanced.stdout)
        advanced_report = json.loads(advanced.stdout)
        self.assertEqual(advanced_report.get("video_advance_frames"), 1)
        self.assertEqual(advanced_report.get("video_advance_requested"), 1)
        self.assertEqual(advanced_report.get("video_advance_completed"), 1)
        advanced_safe = safe_result(advanced_report)
        self.assertEqual(advanced_safe.get("video_advance_frames"), 1)
        self.assertEqual(advanced_safe.get("video_advance_completed"), 1)
        safe = safe_result(json.loads(execution.stdout))
        self.assertEqual(safe["status"], "attract_start")
        self.assertEqual(safe["checkpoint"], {
            "user_request": "demo", "chunk": 1, "user_mode_corroborated": True})
        self.assertEqual(scripted.returncode, 0, scripted.stdout)
        self.assertEqual(json.loads(scripted.stdout)["input_response"], "observed")
        scripted_safe = safe_result(json.loads(scripted.stdout))
        self.assertEqual(scripted_safe["input_response"], "observed")

    def test_frame_indexed_held_input_captures_real_guest_pixels_and_rejects_bad_scripts(self) -> None:
        game, bios = make_split_archives(
            attract_guest=True, attract_loop=True, active_input_guest=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        with tempfile.TemporaryDirectory(prefix="mvs-active-script-") as directory:
            root = Path(directory)
            game_path = root / "game.zip"
            bios_path = root / "bios.zip"
            bundle_path = root / "selected.gnmv"
            game_path.write_bytes(game)
            bios_path.write_bytes(bios)
            imported = subprocess.run(
                [self.importer, "--selected", str(game_path), str(bios_path),
                 str(bundle_path)], capture_output=True, text=True, check=False)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            runner = str(Path(self.production_importer).resolve().parent /
                         "mvs_qualify")
            capture_root = root / "capture-root"
            capture_dir = (capture_root / "local" / "qualification" /
                           "phase06" / ("run-" + "a" * 32))
            capture_dir.mkdir(parents=True)
            capture_arg = capture_dir.relative_to(capture_root).as_posix()
            command = [runner, str(bundle_path), "--input-script", "coin@1,start@2",
                       "--frame-inputs", "0:0x20,1:0x0",
                       "--active-frames", "2", "--capture-frames", "0,1",
                       "--capture-directory", capture_arg]
            execution = subprocess.run(
                command, cwd=capture_root, capture_output=True, text=True,
                check=False)
            self.assertEqual(execution.returncode, 0, execution.stdout)
            report = json.loads(execution.stdout)
            self.assertEqual(report["status"], "active_frames_completed")
            self.assertIs(report["guest_executed"], True)
            self.assertEqual(report["active_frames_requested"], 2)
            self.assertEqual(report["active_frames_completed"], 2)
            self.assertEqual(report["capture_frames"], [0, 1])
            self.assertEqual(report["sampled_inputs"], [
                {"frame": 0, "mask": 0x20},
                {"frame": 1, "mask": 0},
            ])
            header = b"P6\n320 224\n255\n"
            frames = [(capture_dir / f"frame-{frame:04d}.ppm").read_bytes()
                      for frame in range(2)]
            self.assertTrue(all(frame.startswith(header) for frame in frames))
            self.assertEqual(frames[0][len(header) + 3:len(header) + 6],
                             b"\xff\xff\xff")
            self.assertEqual(frames[1][len(header):len(header) + 24], bytes(24))

            invalid_commands = (
                ["--active-frames", "0"],
                ["--active-frames", "3601"],
                ["--active-frames", "4294967296"],
                ["--active-frames", "3", "--frame-inputs", "1:0x20,1:0"],
                ["--active-frames", "3", "--frame-inputs", "2:0x20,1:0"],
                ["--active-frames", "3", "--frame-inputs", "3:0x20"],
                ["--active-frames", "3", "--frame-inputs", "0:0x80000000"],
                ["--active-frames", "3", "--frame-inputs", "0:0x400"],
                ["--active-frames", "3", "--frame-inputs", "0:0x20x"],
                ["--active-frames", "3", "--capture-frames", "0,0"],
                ["--active-frames", "3", "--capture-frames", "2,1"],
                ["--active-frames", "3", "--capture-frames", "3"],
                ["--active-frames", "3", "--capture-frames", "0,1,2,3,4,5,6"],
                ["--active-frames", "3", "--capture-frames", "0x1"],
                ["--active-frames", "3", "--capture-frames", "0",
                 "--capture-directory", "../outside"],
                ["--active-frames", "3", "--capture-frames", "0",
                 "--capture-directory",
                 "local/qualification/phase06/run-" + "b" * 32],
                ["--active-frames", "1200", "--frame-inputs", ",".join(
                    f"{frame}:0x20" for frame in range(65))],
                ["--active-frames", "1200", "--frame-inputs",
                 "0:0x" + "0" * 4094],
            )
            for options in invalid_commands:
                with self.subTest(options=options):
                    rejected = subprocess.run(
                        [runner, str(bundle_path), *options], cwd=capture_root,
                        capture_output=True, text=True, check=False)
                    self.assertEqual(rejected.returncode, 2, rejected.stdout)
                    self.assertEqual(rejected.stdout, "")

            if os.name != "nt":
                symlink_root = root / "symlink-root"
                symlink_root.mkdir()
                outside = root / "symlink-outside"
                outside.mkdir()
                (symlink_root / "local").symlink_to(outside, target_is_directory=True)
                rejected_link = subprocess.run(
                    [runner, str(bundle_path), "--active-frames", "1",
                     "--capture-frames", "0", "--capture-directory",
                     "local/qualification/phase06/run-" + "c" * 32],
                    cwd=symlink_root, capture_output=True, text=True, check=False)
                self.assertEqual(rejected_link.returncode, 2)
                self.assertEqual(rejected_link.stdout, "")

    def test_maximum_active_frame_horizon_completes_guest_and_capture(self) -> None:
        game, bios = make_split_archives(
            attract_guest=True, attract_loop=True, active_input_guest=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        with tempfile.TemporaryDirectory(prefix="mvs-max-horizon-") as directory:
            root = Path(directory)
            game_path = root / "game.zip"
            bios_path = root / "bios.zip"
            bundle_path = root / "selected.gnmv"
            game_path.write_bytes(game)
            bios_path.write_bytes(bios)
            imported = subprocess.run(
                [self.importer, "--selected", str(game_path), str(bios_path),
                 str(bundle_path)], capture_output=True, text=True, check=False)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            runner = str(Path(self.production_importer).resolve().parent /
                         "mvs_qualify")
            capture_root = root / "capture-root"
            capture_dir = (capture_root / "local" / "qualification" /
                           "phase06" / ("run-" + "d" * 32))
            capture_dir.mkdir(parents=True)
            capture_arg = capture_dir.relative_to(capture_root).as_posix()
            execution = subprocess.run(
                [runner, str(bundle_path), "--input-script", "coin@1,start@2",
                 "--frame-inputs", "0:0x20,3599:0x0",
                 "--active-frames", "3600", "--capture-frames", "0,3599",
                 "--capture-directory", capture_arg],
                cwd=capture_root, capture_output=True, text=True, check=False,
                timeout=240 if os.name == "nt" else 120)
            self.assertEqual(execution.returncode, 0, execution.stdout)
            report = json.loads(execution.stdout)
            self.assertEqual(report["status"], "active_frames_completed")
            self.assertEqual(report["active_frames_requested"], 3600)
            self.assertEqual(report["active_frames_completed"], 3600)
            self.assertEqual(report["capture_frames"], [0, 3599])
            self.assertEqual(report["sampled_inputs"], [
                {"frame": 0, "mask": 0x20},
                {"frame": 3599, "mask": 0},
            ])
            self.assertTrue((capture_dir / "frame-0000.ppm").is_file())
            self.assertTrue((capture_dir / "frame-3599.ppm").is_file())

    def test_native_sound_window_capture_is_bounded_and_input_aligned(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        game, bios = make_split_archives(
            attract_guest=True, attract_loop=True, active_input_guest=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        with tempfile.TemporaryDirectory(prefix="mvs-native-sound-window-") as directory:
            root = Path(directory)
            game_path, bios_path = root / "game.zip", root / "bios.zip"
            bundle_path = root / "selected.gnmv"
            game_path.write_bytes(game)
            bios_path.write_bytes(bios)
            imported = subprocess.run(
                [self.importer, "--selected", str(game_path), str(bios_path),
                 str(bundle_path)], capture_output=True, text=True, check=False)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            runner = str(Path(self.production_importer).resolve().parent /
                         "mvs_qualify")
            capture_root = root / "capture-root"
            capture_directory = (capture_root / "local" / "qualification" /
                                 "phase07" / ("run-" + "e" * 32))
            capture_directory.mkdir(parents=True)
            execution = subprocess.run(
                [runner, str(bundle_path), "--input-script", "coin@1,start@2",
                 "--active-frames", "8", "--capture-directory",
                 capture_directory.relative_to(capture_root).as_posix(),
                 "--sound-windows", "music:0-2"],
                cwd=capture_root, capture_output=True, text=True, check=False,
                timeout=30)
            self.assertEqual(execution.returncode, 0, execution.stdout)
            report = json.loads(execution.stdout)
            self.assertEqual(report["status"], "active_frames_completed")
            window, = report["sound_windows"]
            self.assertEqual((window["first_frame"], window["last_frame"],
                              window["completed_frames"]), (0, 2, 3))
            frame_observations = window["frame_observations"]
            self.assertEqual([frame["frame"] for frame in frame_observations],
                             [0, 1, 2])
            self.assertEqual([frame["input_mask"] for frame in frame_observations],
                             [0, 0, 0])
            self.assertTrue(all(frame["elapsed_cycles"] > 0 and
                                0 < frame["audio_frames"] <= 812
                                for frame in frame_observations))
            pcm_path = capture_directory / "sound-music.s16le"
            self.assertEqual(pcm_path.stat().st_size, window["pcm_bytes"])
            self.assertEqual(pcm_path.stat().st_size,
                             window["audio_frames_delivered"] * 4)
            self.assertLessEqual(pcm_path.stat().st_size, 3 * 812 * 4)
            chip = window["chip_observation"]
            self.assertEqual(chip["version"], 1)
            self.assertLessEqual(len(chip["register_events"]), 32)
            self.assertIn("chip_frames", window)
            chip_frames = window["chip_frames"]
            self.assertEqual([frame["frame"] for frame in chip_frames], [0, 1, 2])
            self.assertTrue(all(type(frame["chip_reset"]) is bool
                                for frame in chip_frames))
            for counter in (
                    "chip_clocks", "fm_key_on_writes", "fm_key_off_writes",
                    "fm_register_writes", "ssg_register_writes",
                    "ssg_volume_writes", "adpcm_a_register_writes",
                    "adpcm_a_control_writes", "adpcm_a_reads",
                    "adpcm_b_register_writes", "adpcm_b_control_writes",
                    "adpcm_b_reads",
                    "native_nonzero_frames"):
                self.assertTrue(all(type(frame[counter]) is int and
                                    frame[counter] >= 0 for frame in chip_frames))
            last_chip_reset = max(
                (index for index, frame in enumerate(chip_frames)
                 if frame["chip_reset"]), default=0)
            current_chip_epoch = chip_frames[last_chip_reset:]
            self.assertEqual(
                sum(frame["chip_clocks"] for frame in current_chip_epoch),
                chip["clocks"])
            self.assertEqual(
                sum(frame["fm_key_on_writes"] for frame in current_chip_epoch),
                chip["fm_key_on_writes"])
            for frame_counter, aggregate_counter in \
                    qualification.SOUND_CHIP_FRAME_COUNTERS.items():
                self.assertEqual(
                    sum(frame[frame_counter] for frame in current_chip_epoch),
                    chip[aggregate_counter])
            self.assertEqual(len(window["board_observations"]), 3)
            board_cycles = [entry["sound_cpu_cycles"]
                            for entry in window["board_observations"]]
            for previous, current in zip(window["board_observations"],
                                         window["board_observations"][1:]):
                self.assertEqual(current["sound_cpu_reset"],
                                 current["sound_cpu_cycles"] <
                                 previous["sound_cpu_cycles"])
            self.assertTrue(all(0 <= entry["sound_cpu_pc"] <= 0xffff
                                for entry in window["board_observations"]))
            for counter in (
                    "register_writes", "ssg_register_writes", "ssg_volume_writes",
                    "control_register_writes", "fm_register_writes",
                    "fm_key_on_writes", "fm_key_off_writes",
                    "fm_frequency_writes", "fm_level_writes", "fm_pan_writes",
                    "adpcm_a_register_writes", "adpcm_b_register_writes",
                    "adpcm_a_control_writes", "adpcm_b_control_writes",
                    "adpcm_a_reads", "adpcm_b_reads", "native_frames",
                    "native_nonzero_frames", "timer_programs", "timer_expirations",
                    "irq_assertions", "irq_deassertions"):
                self.assertIsInstance(chip[counter], int)
                self.assertGreaterEqual(chip[counter], 0)

    def test_scripted_coin_stays_held_until_delayed_bios_poll(self) -> None:
        game, bios = make_split_archives(
            attract_guest=True, attract_loop=True, delayed_coin_guest=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        with tempfile.TemporaryDirectory(prefix="mvs-scripted-held-coin-") as directory:
            root = Path(directory)
            game_path, bios_path = root / "game.zip", root / "bios.zip"
            bundle_path = root / "selected.gnmv"
            game_path.write_bytes(game)
            bios_path.write_bytes(bios)
            imported = subprocess.run(
                [self.importer, "--selected", str(game_path), str(bios_path),
                 str(bundle_path)], capture_output=True, text=True, check=False)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            runner = str(Path(self.production_importer).resolve().parent /
                         "mvs_qualify")
            execution = subprocess.run(
                [runner, str(bundle_path), "--input-script", "coin@1,start@600"],
                capture_output=True, text=True, check=False, timeout=30)
            self.assertEqual(execution.returncode, 0, execution.stdout)
            report = json.loads(execution.stdout)
            self.assertEqual(report.get("status"), "attract_start")
            self.assertEqual(report.get("input_response"), "observed")

    def test_scripted_start_stays_held_until_delayed_bios_poll(self) -> None:
        game, bios = make_split_archives(
            attract_guest=True, attract_loop=True, delayed_start_guest=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        with tempfile.TemporaryDirectory(prefix="mvs-scripted-held-start-") as directory:
            root = Path(directory)
            game_path, bios_path = root / "game.zip", root / "bios.zip"
            bundle_path = root / "selected.gnmv"
            game_path.write_bytes(game)
            bios_path.write_bytes(bios)
            imported = subprocess.run(
                [self.importer, "--selected", str(game_path), str(bios_path),
                 str(bundle_path)], capture_output=True, text=True, check=False)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            runner = str(Path(self.production_importer).resolve().parent /
                         "mvs_qualify")
            execution = subprocess.run(
                [runner, str(bundle_path), "--input-script", "coin@1,start@2"],
                capture_output=True, text=True,
                check=False, timeout=30)
            self.assertEqual(execution.returncode, 0, execution.stdout)
            report = json.loads(execution.stdout)
            self.assertEqual(report.get("status"), "attract_start")
            self.assertEqual(report.get("input_response"), "observed")

    def test_active_frame_and_scene_contract_projection_is_strict(self) -> None:
        native = {
            "status": "active_frames_completed", "guest_executed": True,
            "start_observed": True,
            "active_frames_requested": 3, "active_frames_completed": 3,
            "capture_frames_requested": [0, 2], "capture_frames": [0, 2],
            "sampled_inputs": [
                {"frame": 0, "mask": 0x20}, {"frame": 1, "mask": 0},
            ],
        }
        projected = safe_result(native)
        self.assertEqual(projected["status"], "active_frames_completed")
        self.assertEqual(projected["active_frames_completed"], 3)
        self.assertEqual(projected["capture_frames"], [0, 2])
        self.assertEqual(projected["sampled_input_count"], 2)

        for changes in (
            {"active_frames_completed": 2},
            {"capture_frames": [0]},
            {"capture_frames_requested": [2, 0]},
            {"sampled_inputs": [{"frame": 0, "mask": 0x400}]},
            {"sampled_inputs": [{"frame": True, "mask": 0}]},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(safe_result({**native, **changes})["status"],
                                 "native_qualification_failed")

        contract = {
            "schema_version": 1, "mode": "calibrate", "code_identity": {},
            "evaluator_identity": {"path": "/local/evaluator.py",
                                   "scope": "production", "sha256": "9" * 64},
            "media_identity": [], "configuration_identity": "a" * 64,
            "schedule": {}, "t0_frame": None, "endpoint_frame": None,
            "checkpoints": [], "regions": [], "predicates": [], "limits": {},
            "frozen": False, "sampled_inputs": [], "requested_frames": 1,
            "completed_frames": 1, "observations": {}, "outcomes": {},
        }
        contract["contract_identity"] = hashlib.sha256(
            json.dumps(contract, sort_keys=True, separators=(",", ":"))
            .encode("utf-8")).hexdigest()
        self.assertTrue(active_scene_contract_is_valid(contract))
        stale = {**contract, "t0_frame": 1}
        self.assertFalse(active_scene_contract_is_valid(stale))

    def test_phase06_calibration_captures_full_active_horizon(self) -> None:
        from tools.mvs.qualify_local_boot import _active_schedule_valid
        frames = PHASE06_CALIBRATION_FRAMES
        self.assertEqual(tuple(sorted(set(frames))), frames)
        self.assertEqual(len(frames), 6)
        self.assertEqual(frames[0], 2523)
        self.assertEqual(MAX_ACTIVE_FRAMES, 3600)
        self.assertEqual(frames[-1], 2700)
        self.assertTrue(_active_schedule_valid(MAX_ACTIVE_FRAMES,
                                               f"{MAX_ACTIVE_FRAMES - 1}:0x20",
                                               None, None))
        self.assertFalse(_active_schedule_valid(MAX_ACTIVE_FRAMES + 1,
                                                f"{MAX_ACTIVE_FRAMES - 1}:0x20",
                                                None, None))

    def test_phase06_calibration_forwards_bounded_capture_window(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        frames = [3000, 3120, 3240, 3360, 3480, 3599]
        argv = [
            "qualify_local_boot.py", "--active-scene", "calibrate",
            "--scene-contract", "local/qualification/phase06-contract.json",
            "--active-capture-frames", ",".join(map(str, frames)),
        ]
        with mock.patch("sys.argv", argv), \
             mock.patch.object(qualification, "calibrate_active_scene", return_value={
                 "status": "active_scene_calibration_recorded",
                 "calibration_outcome": "captures_ready",
             }) as calibrate, \
             redirect_stdout(io.StringIO()):
            try:
                result = qualification.main()
            except SystemExit as error:
                self.fail(f"a bounded calibration capture window must be accepted: {error}")
            self.assertEqual(result, 0)
        self.assertEqual(calibrate.call_args.kwargs["capture_frames"], frames)

        for invalid in ("1,1,2,3,4,5", "5,4,3,2,1,0", "1,2,3,4,5,3600",
                        "1,2,3,4,5", "0,1,2,3,4,5,6", "1,2,3,4,5,6x",
                        "-1,1,2,3,4,5", "1,2,3,4,5,999999999999999999999"):
            with self.subTest(frames=invalid), \
                 mock.patch("sys.argv", argv[:-1] + [invalid]), \
                 mock.patch.object(qualification, "calibrate_active_scene") as run, \
                 mock.patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    qualification.main()
                run.assert_not_called()

    def test_phase07_sound_contract_option_is_bound_to_active_scene(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        argv = [
            "qualify_local_boot.py", "--active-scene", "calibrate",
            "--scene-contract", "local/qualification/phase06-contract.json",
            "--sound-contract", "local/qualification/phase07-sound-contract.json",
        ]
        with mock.patch("sys.argv", argv), \
             mock.patch.object(qualification, "calibrate_active_scene", return_value={
                 "status": "active_scene_sound_calibration_recorded",
                 "calibration_outcome": "windows_ready",
             }) as calibrate, \
             redirect_stdout(io.StringIO()):
            try:
                result = qualification.main()
            except SystemExit as error:
                self.fail(f"the sound contract option should be accepted on the existing "
                          f"active-scene route: {error}")
        self.assertEqual(result, 0)
        self.assertEqual(
            calibrate.call_args.kwargs["sound_contract_path"],
            Path("local/qualification/phase07-sound-contract.json"),
        )

    def test_retained_frontend_audio_evaluation_rejects_unowned_paths_without_execution(self):
        from tools.mvs import qualify_local_boot as q
        with mock.patch.object(q,"run_active_scene_frontend") as acquire, \
                mock.patch.object(q,"_load_frontend_replay") as replay:
            result=q.evaluate_retained_frontend_audio(Path("outside/trace.json"),q.PHASE06_CONTRACT_PATH,
                                                       q.PHASE07_SOUND_CONTRACT_PATH)
        self.assertEqual(result["status"],"retained_frontend_audio_rejected")
        self.assertFalse(result["new_frontend_observation"])
        self.assertEqual(result["native_execution"],"not-run")
        acquire.assert_not_called(); replay.assert_not_called()

    def test_retained_frontend_evaluation_never_launches_and_keeps_device_evidence_historical(self):
        from tools.mvs import qualify_local_boot as q
        with mock.patch.object(q, "_load_retroarch_smoke") as collector, \
                mock.patch.object(q, "_build_frontend_core") as build, \
                mock.patch.object(q, "run_active_scene_frontend") as acquire:
            result = q.evaluate_retained_frontend_captures(
                Path("outside/frontend-report.json"), q.PHASE06_CONTRACT_PATH)
        self.assertEqual(result["status"], "retained_frontend_evaluation_rejected")
        self.assertFalse(result["new_frontend_observation"])
        self.assertEqual(result["device_evidence"], "not-refreshed")
        collector.assert_not_called(); build.assert_not_called(); acquire.assert_not_called()

    def test_frontend_audio_only_dispatch_cannot_claim_full_scene_acceptance(self):
        from tools.mvs import qualify_local_boot as q
        argv = ["qualify_local_boot.py", "--active-scene", "frontend",
                "--scene-contract", "local/qualification/phase06-contract.json",
                "--sound-contract", "local/qualification/phase07-sound-contract.json"]
        tracer = dict(status="active_scene_frontend_audio_recorded", private_identity_recorded=True,
                      predicate_results={"overall": "unknown"}, audio_evidence={"status": "pass"})
        with mock.patch.object(q, "run_active_scene_frontend", return_value=tracer) as run, \
                mock.patch("sys.argv", argv + ["--frontend-audio-only"]), redirect_stdout(io.StringIO()):
            self.assertEqual(q.main(), 0)
            self.assertTrue(run.call_args.kwargs["audio_only"])
        with mock.patch.object(q, "run_active_scene_frontend", return_value=tracer), \
                mock.patch("sys.argv", argv), redirect_stdout(io.StringIO()):
            self.assertEqual(q.main(), 1, "an audio tracer is not a passing full scene")
        for bad in (["qualify_local_boot.py", "--frontend-audio-only"],
                    argv + ["--frontend-audio-only", "--active-frontend-calibrate"]):
            with mock.patch("sys.argv", bad), mock.patch("sys.stderr", new_callable=io.StringIO), \
                    mock.patch.object(q, "run_active_scene_frontend") as run:
                with self.assertRaises(SystemExit): q.main()
                run.assert_not_called()

        controls = dict(tracer, status="active_scene_frontend_audio_controls_recorded",
                        audio_evidence={"status": "pass", "controls_status": "pass"},
                        sound_outcomes={"music": "pass", "overall": "unknown"})
        with mock.patch.object(q, "run_active_scene_frontend", return_value=controls) as run, \
                mock.patch("sys.argv", argv + ["--frontend-audio-controls-only"]), redirect_stdout(io.StringIO()):
            self.assertEqual(q.main(), 0)
            self.assertTrue(run.call_args.kwargs["audio_controls_only"])
        for bad in (argv, argv + ["--frontend-audio-only", "--frontend-audio-controls-only"],
                    argv + ["--frontend-audio-controls-only", "--active-frontend-calibrate"]):
            with mock.patch.object(q, "run_active_scene_frontend", return_value=controls), \
                    mock.patch("sys.argv", bad), redirect_stdout(io.StringIO()), \
                    mock.patch("sys.stderr", new_callable=io.StringIO):
                if bad == argv:
                    self.assertEqual(q.main(), 1, "controls alone cannot pass the full scene")
                else:
                    with self.assertRaises(SystemExit): q.main()
        controls["audio_evidence"]["controls_status"] = "incomplete"
        with mock.patch.object(q, "run_active_scene_frontend", return_value=controls), \
                mock.patch("sys.argv", argv + ["--frontend-audio-controls-only"]), redirect_stdout(io.StringIO()):
            self.assertEqual(q.main(), 1)

    def test_frontend_audio_control_matrix_reuses_tracer_and_stops_before_visual_on_missing_control(self):
        from tools.mvs import qualify_local_boot as q
        first={"status":"pass","private_report_path":"original"}
        acquire=mock.Mock(return_value={"status":"pass","private_report_path":"control"})
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(q,"_create_active_scene_run_directory",return_value=Path(tmp)), \
                mock.patch.object(q,"write_report",return_value=True), \
                mock.patch.object(q,"_read_frontend_audio_trace",return_value={"actual":{},"rows":[],"pcm":b"original"}) as read, \
                mock.patch.object(q,"_frontend_sound_window_bounds",return_value={}), \
                mock.patch.object(q,"_frontend_audio_pair_inputs_valid",return_value=True) as inputs, \
                mock.patch.object(q,"_frontend_sound_window_recording",return_value={"windows":{}}), \
                mock.patch.object(q,"_phase07_calibration_outcomes",return_value={"music":"pass","overall":"unknown"}) as causal:
            result=q._run_frontend_audio_controls(first,acquire,{"active_frames":210}, {},"a"*64,"b"*64,{},mock.Mock())
            self.assertEqual(result["status"],"pass")
            self.assertEqual(acquire.call_args_list,[mock.call("control","normal"),mock.call("action","muted"),mock.call("action","disabled")])
            self.assertEqual(set(result["recordings"]),{"action","control"})
            self.assertTrue(all(not call.kwargs.get("retained",False) for call in read.call_args_list),
                            "live controls must retain current-source validation")
            acquire.reset_mock(); acquire.return_value={"status":"unavailable"}
            result=q._run_frontend_audio_controls(first,acquire,{"active_frames":210}, {},"a"*64,"b"*64,{},mock.Mock())
            self.assertNotEqual(result["status"],"pass")
            acquire.assert_called_once_with("control","normal")
            acquire.reset_mock(); acquire.return_value={"status":"pass","private_report_path":"control"}; inputs.return_value=False
            causal.return_value={"music":"pass","overall":"unknown"}
            unmatched=q._run_frontend_audio_controls(first,acquire,{"active_frames":210}, {},"a"*64,"b"*64,{},mock.Mock())
            self.assertNotEqual(unmatched["status"],"pass")
            acquire.assert_called_once_with("control","normal")
            self.assertEqual(unmatched["input_prefix_and_branch"],"fail")
            acquire.reset_mock(); acquire.return_value={"status":"pass","private_report_path":"control"}
            inputs.return_value=True
            causal.return_value={"music":"unknown","overall":"unknown"}
            unmatched=q._run_frontend_audio_controls(first,acquire,{"active_frames":210}, {},"a"*64,"b"*64,{},mock.Mock())
            self.assertNotEqual(unmatched["status"],"pass")
            acquire.assert_called_once_with("control","normal")
        for bad in ({},{"status":"pass","private_report_path":"outside/trace.json"}):
            with self.assertRaises(ValueError):
                q._read_frontend_audio_trace(bad,"action","normal",{},"a"*64,"b"*64,"c"*64,mock.Mock())

    def test_frontend_audio_replay_preserves_every_prefix_mask_and_only_omits_fire(self):
        from tools.mvs import qualify_local_boot as q
        smoke=q._load_retroarch_smoke()
        contract,_,_=self._phase06_pair_evidence_fixture()
        schedule=contract["schedule"]; schedule["active_frames"]=210
        for name,pair in schedule["pairs"].items():
            pair["capture_frames"]=[0,130,145,155,180,200]
            for role in ("action","control"):
                mask=int(pair[role].split(":0x")[1].split(",")[0],16)
                pair[role]=f"138:0x{mask:x},{198 if name=='scroll' else 168}:0x0"
        def actual(masks, origin=10):
            identifier="original"
            records=[dict(event_kind="B",sample_sequence=0,sampled_mask=0,
                          successful_video_sequence=0,executed_cycles=0,invocation_id=identifier)]
            previous=None
            for sequence,mask in enumerate(masks,1):
                if mask != previous:
                    records.append(dict(event_kind="S",sample_sequence=sequence,sampled_mask=mask,
                        successful_video_sequence=sequence-1,executed_cycles=(sequence-1)*100,invocation_id=identifier))
                records.append(dict(event_kind="V",sample_sequence=sequence,sampled_mask=mask,
                    successful_video_sequence=sequence,executed_cycles=sequence*100,invocation_id=identifier))
                previous=mask
            return dict(active_origin_video_sequence=origin,invocation_id=identifier,observations=records)
        masks=[0]*220
        masks[1]=1; masks[3]=2; masks[14:16]=[64]*2; masks[149:179]=[64]*30
        action=actual(masks)
        plan=q._frontend_audio_replay_plan(action,schedule,"control",smoke)
        expected=masks[:]; expected[149:179]=[0]*30
        self.assertEqual(plan,{"origin":10,"masks":expected})
        self.assertEqual(q._frontend_audio_replay_plan(action,schedule,"action",smoke)["masks"],masks)
        self.assertTrue(q._frontend_audio_pair_inputs_valid(action,actual(expected),schedule,smoke))
        for index in (0,1,2,3,4,13,14,15,16,148,149,178,179,180,219):
            changed=expected[:]; changed[index] ^= 64
            self.assertFalse(q._frontend_audio_pair_inputs_valid(action,actual(changed),schedule,smoke),index)
        self.assertFalse(q._frontend_audio_pair_inputs_valid(action,actual(expected,11),schedule,smoke))
        incomplete=actual(expected[:-1])
        self.assertFalse(q._frontend_audio_pair_inputs_valid(action,incomplete,schedule,smoke))
        with self.assertRaises(smoke.SmokeBlocked): smoke.sampled_mvs_masks(action,0)
        with self.assertRaises(smoke.SmokeBlocked): smoke.sampled_mvs_masks(action,8193)

    def test_frontend_sound_windows_preserve_frozen_causal_rules_at_observed_transitions(self):
        from tools.mvs import qualify_local_boot as q
        contract,_,_=self._phase06_pair_evidence_fixture()
        schedule=contract["schedule"]; schedule["active_frames"]=210
        for name,pair in schedule["pairs"].items():
            pair["capture_frames"]=[0,130,145,155,180,200]
            for role in ("action","control"):
                mask=int(pair[role].split(":0x")[1].split(",")[0],16)
                pair[role]=f"138:0x{mask:x},{198 if name=='scroll' else 168}:0x0"
        actual=dict(active_origin_video_sequence=10,observations=[
            dict(event_kind="S",sample_sequence=150,sampled_mask=64),
            dict(event_kind="S",sample_sequence=180,sampled_mask=0)])
        # The ordinary entry schedule can use the same A key to confirm a
        # character before the frozen fire event. That is not a second shot.
        actual["observations"][0:0]=[
            dict(event_kind="S",sample_sequence=15,sampled_mask=64),
            dict(event_kind="S",sample_sequence=17,sampled_mask=0)]
        bounds=q._frontend_sound_window_bounds(actual,schedule)
        self.assertEqual(bounds,{"music":(20,139),"fire":(140,163),"release":(170,194)})
        recordings={}; original=Path.cwd()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(q,"ignored",return_value=True):
            try:
                os.chdir(tmp)
                for role in ("action","control"):
                    rows=[]; blocks=[]
                    for seq in range(1,220):
                        relative=seq-10; firing=role=="action" and 140<=relative<170
                        chip={key:0 for key in q.SOUND_CHIP_FRAME_COUNTERS}
                        chip.update(chip_clocks=135168,native_nonzero_frames=5)
                        if relative==20: chip.update(ssg_volume_writes=1,ssg_register_writes=1)
                        if firing and relative==142: chip.update(fm_key_on_writes=1,fm_register_writes=1)
                        if role=="action" and relative==170: chip.update(fm_key_off_writes=1,fm_register_writes=1)
                        rows.append(dict(sequence=seq,sampled_mask=64 if firing or 15<=seq<17 else 0,
                            elapsed_cycles=202752,audio_frames=5,chip=dict(chip_reset=False,**chip)))
                        blocks.append(struct.pack("<10h",*([300 if firing else 100]*10)))
                    directory=q._create_active_scene_run_directory(q.PHASE07_RUN_ROOT)
                    recordings[role]=q._frontend_sound_window_recording(
                        actual,rows,b"".join(blocks),role,bounds,directory,210)
                self.assertEqual(q._phase07_calibration_outcomes(recordings,{"overall":"pass"}),
                                 {"music":"pass","fire":"pass","release":"pass","overall":"pass"})
                bounded=copy.deepcopy(recordings["control"])
                bounded["windows"]["music"]["bytes"]=q.SOUND_PCM_MAX_WINDOW_BYTES+4
                self.assertIsNone(q._phase07_recording_pcm(bounded,"music"),
                                  "window metadata must bound a later private file read")
                bad=copy.deepcopy(recordings)
                for row in bad["action"]["windows"]["fire"]["chip_frames"]:
                    row["native_nonzero_frames"]=0
                self.assertNotEqual(q._phase07_calibration_outcomes(bad,{"overall":"pass"})["fire"],"pass")
                with self.assertRaises(ValueError):
                    q._frontend_sound_window_recording(actual,rows,b"truncated","control",bounds,
                        q._create_active_scene_run_directory(q.PHASE07_RUN_ROOT),210)
                crossing=copy.deepcopy(actual); crossing["observations"][2]["sample_sequence"]=300
                with self.assertRaises(ValueError): q._frontend_sound_window_bounds(crossing,schedule)
                ambiguous=copy.deepcopy(actual)
                ambiguous["observations"].append(dict(event_kind="S",sample_sequence=151,sampled_mask=64))
                with self.assertRaises(ValueError): q._frontend_sound_window_bounds(ambiguous,schedule)
            finally: os.chdir(original)

    def test_frontend_audio_frame_history_binds_inputs_clocks_and_replayed_counts(self):
        from tools.mvs import qualify_local_boot as q
        from retroarch_smoke import parse_mvs_input_observations
        records=parse_mvs_input_observations("glueyneo: mvs B 0 0 0 0\n"
            "glueyneo: mvs S 1 0 0 0\n"
            "glueyneo: mvs V 1 0 1 202752\n"
            "glueyneo: mvs S 2 64 1 202752\n"
            "glueyneo: mvs V 2 64 2 405504\n",invocation_id="original")
        actual=dict(invocation_id="original",observations=records)
        rows=[dict(sequence=1,sampled_mask=0,elapsed_cycles=202752,audio_frames=811),
              dict(sequence=2,sampled_mask=64,elapsed_cycles=202752,audio_frames=811)]
        receipt=dict(audio=dict(completed_sequences=2,frame_sample_counts=[811,811]))
        self.assertTrue(q._frontend_audio_frame_history_valid(actual,rows,receipt))
        for mutate in (lambda r:r[1].update(sampled_mask=0),lambda r:r[1].update(elapsed_cycles=202753),
                       lambda r:r[1].update(audio_frames=810),lambda r:r.pop()):
            bad=copy.deepcopy(rows); mutate(bad)
            self.assertFalse(q._frontend_audio_frame_history_valid(actual,bad,receipt))

    def test_frontend_audio_trace_replays_control_and_route_with_complete_frame_metadata(self):
        from contextlib import ExitStack
        from tools.mvs import qualify_local_boot as q
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as patches:
            directory=Path(tmp); core={"path":"core","sha256":"a"*64}
            app=dict(core_sha256="a"*64,retroarch_version="1.22.2",
                     retroarch_executable_sha256="b"*64,bundle_id="org.example.original")
            source={"core_sha256":"a"*64}
            schedule={"active_frames":48,"pairs":{"fire":{"capture_frames":[0,8,16,24,32,40]}}}
            contract=dict(code_identity={"importer":{}},media_identity=[{"sha256":"c"*64}]*2,
                          frontend={"app_identity":app},contract_identity="d"*64)
            actual=dict(status="complete",identity=app,configuration_text="original config",
                        captures=[{"path":str(directory/"captures"/"sample.png")}],observations=[],
                        active_origin_video_sequence=1,selected_bundle_sha256="e"*64,
                        audio_evidence=dict(capture={"status":"pass","sample_frames":2},
                                            route={"status":"pass"},delivery={"status":"pass"}))
            smoke=mock.Mock(); smoke.run_mvs_active_scene.return_value=actual
            smoke.frontend_audio_evidence_is_valid.return_value=True
            smoke.parse_frontend_audio_frames.return_value=[dict(sequence=1,audio_frames=2)]
            receipt=dict(status="pass",audio=dict(frame_sample_counts=[2],completed_sequences=1))
            replay=mock.Mock(); replay.validate_receipt.return_value=True
            def replay_now(core_,bundle,inv,identity,*,require_audio=False):
                self.assertTrue(Path(bundle).exists(),"normalized media must live through child replay")
                self.assertTrue(require_audio)
                self.assertEqual(inv["audio_replay_context"]["control"],"disabled")
                return receipt
            replay.run_replay.side_effect=replay_now
            def imported(command,**kwargs):
                Path(command[-1]).write_bytes(b"original fixture")
                return subprocess.CompletedProcess(command,0)
            values={"_create_active_scene_run_directory":directory,
                    "_active_scene_input_events":[(10,0),(30,0)],"_phase07_sound_windows":"control:10-29",
                    "_active_frontend_sources":source,"_phase07_contract_files_unchanged":True,
                    "_sha256_path":"f"*64,"active_scene_configuration_identity":"f"*64,
                    "find_pairs":[(Path("game"),Path("bios"))],"checked_importer_command":"importer",
                    "_selected_v3_bundle_has_zoom_role":True,"_frontend_configuration_identity":"config-id",
                    "_active_frontend_events_valid":True,"active_scene_frontend_capture_is_valid":True,
                    "_frontend_audio_frame_history_valid":True,"_frontend_audio_replay_plan":{"masks":[0],"origin":1},
                    "_phase07_sound_contract_scene_binding_valid":True,"_load_frontend_replay":replay,
                    "write_report":True}
            for name,value in values.items(): patches.enter_context(mock.patch.object(q,name,return_value=value))
            patches.enter_context(mock.patch.object(q,"_file_identity",side_effect=lambda p:
                {"sha256":"a"*64} if str(p)=="core" else {"sha256":"c"*64}))
            patches.enter_context(mock.patch.object(q.subprocess,"run",side_effect=imported))
            result=q._run_active_scene_audio_trace(Path("local/roms"),None,contract,schedule,core,source,smoke,
                sound_contract={},contract_path=Path("scene"),sound_contract_path=Path("sound"),
                scene_digest="f"*64,sound_digest="f"*64,expected_app_identity=app,
                role="control",audio_control="disabled",input_reference={"original":"history"})
            self.assertEqual(result["status"],"pass")
            self.assertEqual(smoke.run_mvs_active_scene.call_args.kwargs["audio_control"],"disabled")
            self.assertEqual(smoke.run_mvs_active_scene.call_args.kwargs["input_replay"],{"masks":[0],"origin":1})
            self.assertEqual(smoke.frontend_audio_evidence_is_valid.call_args.kwargs["expected_control"],"disabled")
            replay.run_replay.assert_called_once()
            q.write_report.return_value=False
            missing=q._run_active_scene_audio_trace(Path("local/roms"),None,contract,schedule,core,source,smoke,
                sound_contract={},contract_path=Path("scene"),sound_contract_path=Path("sound"),
                scene_digest="f"*64,sound_digest="f"*64,expected_app_identity=app,
                role="control",audio_control="disabled",input_reference={"original":"history"})
            self.assertNotEqual(missing["status"],"pass","missing durable evidence cannot qualify")
            self.assertNotIn("private_report_path",missing)

    def test_phase07_frontend_traces_audio_before_visual_campaign(self) -> None:
        from contextlib import ExitStack
        from tools.mvs import qualify_local_boot as q
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as patches:
            root = Path(temporary)
            schedule = {"active_frames": 3600, "pairs": {}}
            contract = {"contract_identity": "d" * 64, "schedule": schedule, "frontend": {
                "schedule": schedule, "native_schedule_identity": "schedule",
                "app_identity": {"core_sha256": "b" * 64}},
                "code_identity": {"importer": {}}, "media_identity": []}
            values = {
                "validate_scene_contract": ("valid", contract),
                "_current_frontend_core": {"path": "core", "sha256": "a" * 64},
                "_active_frontend_sources": {"core_sha256": "a" * 64},
                "_sha256_path": "c" * 64,
                "_read_phase07_sound_contract": {"frozen": True},
                "_phase07_sound_contract_scene_binding_valid": True,
                "_active_frontend_frozen_evidence_valid": True,
                "_active_frontend_schedule_compatible": True,
                "active_scene_configuration_identity": "schedule",
                "_create_active_scene_run_directory": root,
                "_load_retroarch_smoke": mock.Mock(),
                "_run_frontend_audio_controls": {"status":"pass","recordings":{},"traces":{}},
                "_active_scene_input_events": [],
                "find_pairs": [],
                "checked_importer_command": None,
                "_phase07_contract_files_unchanged": True,
                "_evaluate_active_frontend_pairs": {"overall": "unknown"},
            }
            for name, value in values.items():
                patches.enter_context(mock.patch.object(q, name, return_value=value))
            audio = patches.enter_context(mock.patch.object(
                q, "_run_active_scene_audio_trace", return_value={
                    "status": "unavailable", "capture_status": "unavailable",
                    "route_status": "unknown"}))
            result = q.run_active_scene_frontend(
                root, None, root / "scene.json",
                sound_contract_path=q.PHASE07_SOUND_CONTRACT_PATH)
            audio.assert_called_once()
            self.assertEqual(result["audio_evidence"]["status"], "unavailable")
            self.assertFalse((root / "frontend-case.json").exists(),
                             "a failed first audio trace must stop before visual expansion")
            self.assertNotEqual(result["predicate_results"]["overall"], "pass")
            audio.return_value = {"status": "pass", "capture_status": "pass",
                                  "route_status": "pass"}
            tracer = q.run_active_scene_frontend(
                root, None, root / "scene.json", audio_only=True,
                sound_contract_path=q.PHASE07_SOUND_CONTRACT_PATH)
            self.assertEqual(tracer["status"], "active_scene_frontend_audio_recorded")
            self.assertEqual(tracer["predicate_results"]["overall"], "unknown")
            self.assertFalse((root / "frontend-case.json").exists())
            controls = q.run_active_scene_frontend(
                root, None, root / "scene.json", audio_controls_only=True,
                sound_contract_path=q.PHASE07_SOUND_CONTRACT_PATH)
            self.assertEqual(controls["status"], "active_scene_frontend_audio_controls_recorded")
            self.assertEqual(controls["audio_evidence"]["controls_status"], "pass")
            self.assertEqual(controls["predicate_results"]["overall"], "unknown")
            self.assertFalse((root / "frontend-case.json").exists(), "audio controls must not open visual boots")
            result = q.run_active_scene_frontend(
                root, None, root / "scene.json",
                sound_contract_path=q.PHASE07_SOUND_CONTRACT_PATH)
            self.assertEqual(audio.call_count, 4)
            self.assertTrue((root / "frontend-case.json").exists(),
                            "a passing tracer must still run the visual campaign")
            self.assertEqual(result["audio_evidence"]["status"], "pass")
            self.assertNotEqual(result["predicate_results"]["overall"], "pass",
                                "audio alone cannot satisfy visual acceptance")

    def test_phase07_frontend_accepts_bound_sound_contract(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        argv = [
            "qualify_local_boot.py", "--active-scene", "frontend",
            "--scene-contract", "local/qualification/phase06-contract.json",
            "--sound-contract", "local/qualification/phase07-sound-contract.json",
        ]
        result = {
            "status": "active_scene_frontend_recorded",
            "private_identity_recorded": True,
            "predicate_results": {"overall": "pass"},
            "audio_evidence": {"status": "pass"}, "sound_outcomes": {"overall":"pass"},
        }
        with mock.patch("sys.argv", argv), \
             mock.patch.object(qualification, "run_active_scene_frontend",
                               return_value=result) as run, \
             redirect_stdout(io.StringIO()):
            try:
                exit_code = qualification.main()
            except SystemExit as error:
                self.fail(f"frontend mode must accept the frozen sound contract: {error}")
        self.assertEqual(exit_code, 0)
        self.assertEqual(run.call_args.kwargs["sound_contract_path"],
                         Path("local/qualification/phase07-sound-contract.json"))

    def test_phase07_native_route_rejects_unknown_sound_even_when_visuals_pass(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        argv = [
            "qualify_local_boot.py", "--active-scene", "native",
            "--scene-contract", "local/qualification/phase06-contract.json",
            "--sound-contract", "local/qualification/phase07-sound-contract.json",
        ]
        result = {
            "status": "active_scene_native_recorded",
            "private_identity_recorded": True,
            "predicate_results": {"overall": "pass"},
            "sound_outcomes": {"music": "unknown", "fire": "unknown",
                               "release": "unknown", "overall": "unknown"},
        }
        with mock.patch("sys.argv", argv), \
             mock.patch.object(qualification, "run_active_scene",
                               return_value=result), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(qualification.main(), 1)

    def test_phase07_freeze_binds_fixed_rules_without_promoting_unknown_outcomes(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        schedule = {"active_frames": 10, "pairs": {}}
        scene_identity = "a" * 64
        scene_digest = "b" * 64
        media = [
            {"path": "/private/game.zip", "size": 1, "sha256": "1" * 64},
            {"path": "/private/bios.zip", "size": 1, "sha256": "2" * 64},
        ]
        importer = {"scope": "production", "path": "/build/importer",
                    "sha256": "3" * 64}
        qualifier = {"scope": "production", "path": "/build/qualifier",
                     "sha256": "4" * 64}
        evaluator = {"scope": "production", "path": "/source/evaluator.py",
                     "sha256": "5" * 64}
        schedule_identity = hashlib.sha256(json.dumps(
            {"phase06_contract_identity": scene_identity, "schedule": schedule},
            sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")).hexdigest()
        calibration = {
            "schema_version": 1, "mode": "calibrate",
            "phase06_contract_sha256": scene_digest,
            "phase06_contract_identity": scene_identity,
            "code_identity": {"importer": importer, "qualifier": qualifier},
            "evaluator_identity": evaluator, "media_identity": media,
            "schedule_identity": schedule_identity, "schedule": schedule,
            "recordings": {
                "action": {"windows": {"music": {}, "fire": {}, "release": {}}},
                "control": {"windows": {"music": {}, "control": {}, "release": {}}},
            },
            "families": {"fm": "unknown"}, "thresholds": {},
            "criteria_identity": None, "calibration_identity": None,
            "outcomes": {"music": "unknown", "fire": "unknown",
                         "release": "unknown", "overall": "unknown",
                         "calibration": "windows_ready",
                         "visual_predicates": {"overall": "pass"}},
            "frozen": False, "contract_identity": "c" * 64,
        }
        scene = {"contract_identity": scene_identity, "schedule": schedule,
                 "media_identity": media}
        pair = (Path("game.zip"), Path("bios.zip"))
        run_directory = Path("local/qualification/phase07/run-" + "e" * 32)
        captured: dict[str, object] = {}

        class Freshness(qualification.QualifierFreshness):
            pass

        def write_contract(_path, frozen, _run_directory):
            qualification._seal_phase07_sound_contract(frozen)
            captured.update(frozen)
            return qualification.phase07_sound_contract_is_valid(
                frozen, require_frozen=True)

        with mock.patch.object(qualification, "validate_scene_contract",
                               return_value=("active_scene_contract_valid", scene)) as validate_scene, \
             mock.patch.object(qualification, "_read_phase07_sound_contract",
                               return_value=calibration), \
             mock.patch.object(qualification, "ensure_fresh_qualifier",
                               return_value=Freshness("fresh", importer, qualifier)), \
             mock.patch.object(qualification, "_production_importer_identity",
                               return_value=importer), \
             mock.patch.object(qualification, "_production_qualifier_identity",
                               return_value=qualifier), \
             mock.patch.object(qualification, "_production_evaluator_identity",
                               return_value=evaluator), \
             mock.patch.object(qualification, "find_pairs", return_value=[pair]), \
             mock.patch.object(qualification, "_file_identity",
                               side_effect=media), \
             mock.patch.object(qualification, "_sha256_path",
                               return_value=scene_digest), \
             mock.patch.object(qualification, "_create_active_scene_run_directory",
                               return_value=run_directory), \
             mock.patch.object(qualification, "_write_phase07_sound_contract",
                               side_effect=write_contract), \
             mock.patch.object(qualification, "write_report", return_value=True):
            result = qualification.freeze_phase07_sound_contract(
                Path("local/roms"), Path("local/qualification/phase06-contract.json"),
                Path("local/qualification/phase07-sound-contract.json"))
        self.assertEqual(result["status"], "active_scene_sound_contract_frozen")
        self.assertFalse(validate_scene.call_args.kwargs["check_current_identity"])
        self.assertEqual(result["sound_outcomes"], {
            "music": "unknown", "fire": "unknown", "release": "unknown",
            "overall": "unknown",
        })
        self.assertEqual(captured["calibration_identity"], "c" * 64)
        self.assertEqual(captured["thresholds"], qualification.PHASE07_SOUND_THRESHOLDS)
        self.assertEqual(captured["criteria_identity"], qualification._phase07_criteria_identity(
            qualification.PHASE07_SOUND_THRESHOLDS))
        current = {
            "phase06_identity": scene_identity, "phase06_digest": scene_digest,
            "schedule": schedule, "code_identity": {
                "importer": importer, "qualifier": qualifier},
            "evaluator_identity": evaluator, "media_identity": media,
        }
        self.assertTrue(qualification._phase07_sound_contract_matches_current(
            captured, **current))
        for field, replacement in (
                ("code_identity", {"importer": importer,
                                   "qualifier": {**qualifier, "sha256": "f" * 64}}),
                ("evaluator_identity", {**evaluator, "sha256": "e" * 64}),
                ("media_identity", [*media[:1], {**media[1], "sha256": "d" * 64}]),
                ("schedule", {**schedule, "active_frames": 11})):
            stale = dict(current)
            stale[field] = replacement
            self.assertFalse(qualification._phase07_sound_contract_matches_current(
                captured, **stale))
        with tempfile.TemporaryDirectory(prefix="phase07-contract-identity-") as directory:
            scene_file = Path(directory) / "scene.json"
            sound_file = Path(directory) / "sound.json"
            scene_file.write_bytes(b"scene criteria")
            sound_file.write_bytes(b"sound criteria")
            scene_file_hash = hashlib.sha256(scene_file.read_bytes()).hexdigest()
            sound_file_hash = hashlib.sha256(sound_file.read_bytes()).hexdigest()
            self.assertTrue(qualification._phase07_contract_files_unchanged(
                scene_file, scene_file_hash, sound_file, sound_file_hash))
            sound_file.write_bytes(b"mutated contract")
            self.assertFalse(qualification._phase07_contract_files_unchanged(
                scene_file, scene_file_hash, sound_file, sound_file_hash))
        changed = copy.deepcopy(captured)
        changed["thresholds"]["fire"]["minimum_changed_int16_samples_in_one_frame"] = 1
        qualification._seal_phase07_sound_contract(changed)
        self.assertFalse(qualification.phase07_sound_contract_is_valid(
            changed, require_frozen=True))

    def test_phase07_freeze_cli_uses_existing_calibrate_route(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        argv = [
            "qualify_local_boot.py", "--active-scene", "calibrate",
            "--scene-contract", "local/qualification/phase06-contract.json",
            "--sound-contract", "local/qualification/phase07-sound-contract.json",
            "--freeze-sound-contract",
        ]
        with mock.patch("sys.argv", argv), \
             mock.patch.object(qualification, "freeze_phase07_sound_contract", return_value={
                 "status": "active_scene_sound_contract_frozen",
                 "sound_outcomes": {"overall": "unknown"},
             }) as freeze, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(qualification.main(), 0)
        self.assertEqual(freeze.call_args.args[0], Path("local/roms"))

    def test_phase07_causal_outcomes_need_local_chip_correlated_fire(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        frame_cycles = 202752

        def frame(frame_id: int, mask: int, *, key_on: int = 0,
                  key_off: int = 0, ssg_volume: int = 0,
                  adpcm_a_control: int = 0, adpcm_b_control: int = 0,
                  adpcm_a_reads: int = 0, adpcm_b_reads: int = 0,
                  native: int = 0, reset: bool = False) -> dict[str, object]:
            return {
                "frame": frame_id, "input_mask": mask,
                "elapsed_cycles": frame_cycles, "audio_frames": 5,
                "chip": {
                    "chip_reset": reset, "chip_clocks": 100,
                    "fm_key_on_writes": key_on,
                    "fm_key_off_writes": key_off,
                    "fm_register_writes": key_on + key_off,
                    "ssg_register_writes": ssg_volume,
                    "ssg_volume_writes": ssg_volume,
                    "adpcm_a_register_writes": adpcm_a_control,
                    "adpcm_a_control_writes": adpcm_a_control,
                    "adpcm_b_register_writes": adpcm_b_control,
                    "adpcm_b_control_writes": adpcm_b_control,
                    "adpcm_a_reads": adpcm_a_reads,
                    "adpcm_b_reads": adpcm_b_reads,
                    "native_nonzero_frames": native,
                },
            }

        def window(first: int, masks: list[int], *, event_at: int | None = None,
                   reset_at: int | None = None, release: bool = False
                   ) -> dict[str, object]:
            rows = [frame(first + offset, mask,
                          key_on=1 if event_at == offset and not release else 0,
                          key_off=1 if release and event_at == offset else 0,
                          native=1 if event_at == offset else 0,
                          reset=reset_at == offset)
                    for offset, mask in enumerate(masks)]
            return {"first_frame": first, "last_frame": first + len(masks) - 1,
                    "frame_observations": [
                        {key: value for key, value in row.items()
                         if key in ("frame", "input_mask", "elapsed_cycles",
                                    "audio_frames")}
                        for row in rows],
                    "chip_frames": [
                        {"frame": row["frame"], **row["chip"]} for row in rows]}

        common_block = struct.pack("<10h", *([100] * 10))
        fire_block = struct.pack("<10h", *([300] * 10))
        pcm = {
            ("action", "music"): common_block * 2,
            ("control", "music"): common_block * 2,
            ("action", "fire"): common_block + fire_block,
            ("control", "control"): common_block * 2,
            ("action", "release"): common_block * 3,
            ("control", "release"): common_block * 3,
        }
        recordings = {
            "action": {"role": "action", "windows": {
                "music": window(10, [0, 0], event_at=0),
                "fire": window(20, [0x40, 0x40], event_at=1),
                "release": window(30, [0, 0, 0], event_at=0, release=True),
            }},
            "control": {"role": "control", "windows": {
                "music": window(10, [0, 0], event_at=0),
                "control": window(20, [0, 0]),
                "release": window(30, [0, 0, 0]),
            }},
        }
        for window_name, excess in (("fire", 1), ("release", 3)):
            for row in recordings["action"]["windows"][window_name][
                    "frame_observations"]:
                row["elapsed_cycles"] = frame_cycles + excess
        with mock.patch.object(qualification, "_phase07_recording_pcm",
                               side_effect=lambda recording, name:
                               pcm.get((recording["role"], name))):
            outcomes = qualification._phase07_calibration_outcomes(
                recordings, {"overall": "pass"})
        self.assertEqual(outcomes, {
            "music": "pass", "fire": "pass", "release": "pass",
            "overall": "pass",
        })

        pcm[("control", "music")] = fire_block * 2
        with mock.patch.object(qualification, "_phase07_recording_pcm",
                               side_effect=lambda recording, name:
                               pcm.get((recording["role"], name))):
            divergent_history = qualification._phase07_calibration_outcomes(
                recordings, {"overall": "pass"})
        self.assertEqual(divergent_history["music"], "unknown")
        self.assertEqual(divergent_history["fire"], "unknown")
        self.assertEqual(divergent_history["overall"], "unknown")
        pcm[("control", "music")] = common_block * 2

        action_fire = recordings["action"]["windows"]["fire"]
        action_fire["chip_frames"][1]["fm_key_on_writes"] = 0
        action_fire["chip_frames"][1]["native_nonzero_frames"] = 0
        with mock.patch.object(qualification, "_phase07_recording_pcm",
                               side_effect=lambda recording, name:
                               pcm.get((recording["role"], name))):
            unsupported = qualification._phase07_calibration_outcomes(
                recordings, {"overall": "pass"})
        self.assertEqual(unsupported["fire"], "unknown")
        self.assertEqual(unsupported["overall"], "unknown")

    def test_phase07_causal_outcomes_reject_misaligned_and_reset_windows(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        frame_cycles = 202752

        pcm = struct.pack("<10h", *([100] * 10))
        effect_pcm = struct.pack("<10h", *([200] * 10))
        def make_window(first: int, mask: int, *, reset: bool = False,
                        event: bool = False) -> dict[str, object]:
            chip = {
                "chip_reset": reset, "chip_clocks": 100,
                "fm_key_on_writes": int(event),
                "fm_key_off_writes": 0, "ssg_volume_writes": 0,
                "fm_register_writes": int(event), "ssg_register_writes": 0,
                "adpcm_a_register_writes": 0,
                "adpcm_a_control_writes": 0, "adpcm_b_control_writes": 0,
                "adpcm_b_register_writes": 0,
                "adpcm_a_reads": 0, "adpcm_b_reads": 0,
                "native_nonzero_frames": int(event),
            }
            return {"first_frame": first, "last_frame": first,
                    "frame_observations": [{
                        "frame": first, "input_mask": mask,
                        "elapsed_cycles": frame_cycles, "audio_frames": 5}],
                    "chip_frames": [{"frame": first, **chip}]}

        action = {"role": "action", "windows": {
            "music": make_window(1, 0, event=True),
            "fire": make_window(2, 0x40, event=True),
            "release": make_window(3, 0),
        }}
        control = {"role": "control", "windows": {
            "music": make_window(1, 0, event=True),
            "control": make_window(2, 0),
            "release": make_window(3, 0),
        }}
        recordings = {"action": action, "control": control}
        pcm_map = {(role, name): pcm for role, recording in recordings.items()
                   for name in recording["windows"]}
        pcm_map[("action", "fire")] = effect_pcm
        control_window = control["windows"]["control"]
        control_window["first_frame"] = 4
        control_window["last_frame"] = 4
        control_window["frame_observations"][0]["frame"] = 4
        control_window["chip_frames"][0]["frame"] = 4
        with mock.patch.object(qualification, "_phase07_recording_pcm",
                               side_effect=lambda recording, name:
                               pcm_map.get((recording["role"], name))):
            misaligned = qualification._phase07_calibration_outcomes(
                recordings, {"overall": "pass"})
        self.assertEqual(misaligned["fire"], "unknown")

        control_window["first_frame"] = 2
        control_window["last_frame"] = 2
        control_window["frame_observations"][0]["frame"] = 2
        control_window["chip_frames"][0]["frame"] = 2

        action["windows"]["fire"]["chip_frames"][0]["chip_reset"] = True
        with mock.patch.object(qualification, "_phase07_recording_pcm",
                               side_effect=lambda recording, name:
                               pcm_map.get((recording["role"], name))):
            reset = qualification._phase07_calibration_outcomes(
                recordings, {"overall": "pass"})
        self.assertEqual(reset["fire"], "unknown")

    def test_phase07_alignment_uses_sample_prefixes_and_supported_clock_excess(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        frame_cycles = 202752
        max_excess = 159
        for excess in (-159, -136, 0, 136, 159):
            self.assertTrue(qualification._phase07_elapsed_frame_clocks_are_valid(frame_cycles + excess))
        for excess in (-160, 160):
            self.assertFalse(qualification._phase07_elapsed_frame_clocks_are_valid(frame_cycles + excess))

        def frames(audio: list[int], cycles: list[int], first: int = 10
                   ) -> list[dict[str, int]]:
            return [{"frame": first + offset,
                     "audio_frames": audio[offset],
                     "elapsed_cycles": cycles[offset]}
                    for offset in range(len(audio))]

        left = frames([2, 3], [frame_cycles + 25, frame_cycles - 25])
        right = frames([2, 3], [frame_cycles - 25, frame_cycles + 25])
        self.assertTrue(qualification._phase07_aligned_windows(left, right))

        # Equal per-window totals do not excuse a different sample position at
        # the first guest-frame boundary.
        self.assertFalse(qualification._phase07_aligned_windows(
            frames([3, 2], [frame_cycles, frame_cycles]), right))
        self.assertFalse(qualification._phase07_aligned_windows(
            left, frames([2, 3], [frame_cycles, frame_cycles], first=11)))

        # Per-frame actual clocks are bounded by the frame budget plus the
        # proven159-clock supported atomic excess, and common-history pairs
        # may differ cumulatively by at most that excess.
        self.assertFalse(qualification._phase07_aligned_windows(
            frames([2], [frame_cycles + max_excess + 1]),
            frames([2], [frame_cycles])))
        self.assertFalse(qualification._phase07_aligned_windows(
            frames([2, 3], [frame_cycles + 100, frame_cycles - 100]),
            frames([2, 3], [frame_cycles - 100, frame_cycles + 100])))
        self.assertFalse(qualification._phase07_aligned_windows(
            [{"frame": 10, "audio_frames": 2}],
            frames([2], [frame_cycles])))
        self.assertFalse(qualification._phase07_aligned_windows(
            frames([2], [0]), frames([2], [frame_cycles])))
        self.assertFalse(qualification._phase07_aligned_windows(
            frames([0], [frame_cycles]), frames([0], [frame_cycles])))

    def test_phase07_sound_windows_require_bounded_aligned_non_silent_pcm(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        spec = {"name": "fire", "first_frame": 3, "last_frame": 4}
        pcm = struct.pack("<hhhhhhhh", 1, -1, 2, -2, 3, -3, 4, -4)
        observation = {
            "name": "fire", "first_frame": 3, "last_frame": 4,
            "completed_frames": 2, "actual_cycles": 405504,
            "audio_frames_generated": 4, "audio_frames_delivered": 4,
            "audio_frames_discarded": 0, "pcm_bytes": len(pcm),
            "frame_observations": [
                {"frame": 3, "input_mask": 0x40,
                 "elapsed_cycles": 202752, "audio_frames": 2},
                {"frame": 4, "input_mask": 0x40,
                 "elapsed_cycles": 202752, "audio_frames": 2},
            ],
            "chip_observation": {"register_events": [
                {"register": 0x28, "value": 0xf0}],
                "adpcm_a_reads": 1},
            "board_observations": [{"sound_cpu_pc": 0x1234,
                                    "sound_cpu_cycles": 100}],
        }
        self.assertEqual(
            qualification._sound_window_observation_is_valid(
                observation, spec, pcm, expected_masks=[0x40, 0x40])[0], True)
        for malformed, samples, masks in (
                (None, pcm, [0x40, 0x40]),
                (observation, bytes(len(pcm)), [0x40, 0x40]),
                ({**observation, "frame_observations": [
                    observation["frame_observations"][0],
                    {**observation["frame_observations"][1], "frame": 5}]},
                 pcm, [0x40, 0x40]),
                (observation, pcm[:-4], [0x40, 0x40]),
                (observation, pcm, [0x40, 0]),
        ):
            with self.subTest(malformed=malformed is None, length=len(samples)):
                valid, _features = qualification._sound_window_observation_is_valid(
                    malformed, spec, samples, expected_masks=masks)
                self.assertFalse(valid)
        over_bound = {
            **observation,
            "actual_cycles": 405664,
            "frame_observations": [
                {**observation["frame_observations"][0],
                 "elapsed_cycles": 202912},
                observation["frame_observations"][1],
            ],
        }
        valid, _features = qualification._sound_window_observation_is_valid(
            over_bound, spec, pcm, expected_masks=[0x40, 0x40])
        self.assertFalse(valid)
        self.assertIsNone(qualification._parse_sound_windows(
            "music:0-120", 3600))
        self.assertIsNone(qualification._parse_sound_windows(
            "music:0-1,music:3-4", 3600))
        self.assertIsNone(qualification._parse_sound_windows(
            "unknown:0-1", 3600))
        projected = qualification.public_result({
            "status": "active_frames_completed", "guest_executed": True,
            "start_observed": True, "active_frames_requested": 2,
            "active_frames_completed": 2, "capture_frames_requested": [],
            "capture_frames": [], "sampled_inputs": [],
            "sound_windows": [observation], "private_pcm": pcm.hex(),
        })
        self.assertEqual(projected, {
            "status": "active_frames_completed", "guest_executed": True,
        })

    def test_phase07_release_window_begins_at_localized_release_input(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        schedule = {"active_frames": 300}
        parsed = {"fire": {
            "action": [(130, 0x40), (133, 0)],
            "control": [(130, 0x00)],
        }}
        with mock.patch.object(qualification, "_active_scene_schedule_masks",
                               return_value=parsed):
            windows = qualification._phase07_sound_windows(schedule, "action")
        self.assertEqual(windows, "music:10-129,fire:130-132,release:133-157")

    def test_phase07_chip_observation_is_bounded_and_keeps_family_evidence_local(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        chip = {
            "version": 1, "clocks": 200, "register_writes": 1,
            "ssg_register_writes": 0, "ssg_volume_writes": 0,
            "control_register_writes": 1, "fm_register_writes": 0,
            "fm_key_on_writes": 1, "fm_key_off_writes": 0,
            "fm_frequency_writes": 0, "fm_level_writes": 0,
            "fm_pan_writes": 0, "adpcm_a_register_writes": 0,
            "adpcm_a_control_writes": 0, "adpcm_b_register_writes": 0,
            "adpcm_b_control_writes": 0, "adpcm_a_reads": 0,
            "adpcm_b_reads": 0, "timer_programs": 0,
            "timer_expirations": 0, "irq_assertions": 0,
            "irq_deassertions": 0, "native_frames": 2,
            "native_nonzero_frames": 0, "native_stereo_nonzero_frames": 0,
            "native_ssg_nonzero_frames": 0, "native_peak": 0,
            "event_dropped": 0,
            "register_events": [{
                "clock": 1, "port": 1, "bank": 0, "register": 0x28,
                "value": 0xf0, "family": 5,
            }],
        }
        board = [
            {"frame": frame, "sound_cpu_reset": False,
             "cart_selected": 1, "command": 0,
             "reply": 0, "command_pending": 0, "nmi_enabled": 1,
             "ym_irq": 0, "banks": [0, 0, 0, 0],
             "sound_cpu_pc": 0x1234, "sound_cpu_cycles": cycles}
            for frame, cycles in ((3, 500), (4, 600))
        ]
        observation = {
            "name": "fire", "first_frame": 3, "last_frame": 4,
            "completed_frames": 2, "actual_cycles": 405504,
            "audio_frames_generated": 4, "audio_frames_delivered": 4,
            "audio_frames_discarded": 0, "pcm_bytes": 16,
            "frame_observations": [
                {"frame": frame, "input_mask": 0x40,
                 "elapsed_cycles": 202752, "audio_frames": 2}
                for frame in (3, 4)
            ],
            "chip_observation": chip,
            "chip_frames": [
                {"frame": 3, "chip_reset": False, "chip_clocks": 100,
                 "fm_key_on_writes": 1, "fm_key_off_writes": 0,
                 "fm_register_writes": 0, "ssg_register_writes": 0,
                 "ssg_volume_writes": 0,
                 "adpcm_a_register_writes": 0, "adpcm_a_reads": 0,
                 "adpcm_a_control_writes": 0,
                 "adpcm_b_register_writes": 0, "adpcm_b_reads": 0,
                 "adpcm_b_control_writes": 0,
                 "native_nonzero_frames": 0},
                {"frame": 4, "chip_reset": False, "chip_clocks": 100,
                 "fm_key_on_writes": 0, "fm_key_off_writes": 0,
                 "fm_register_writes": 0, "ssg_register_writes": 0,
                 "ssg_volume_writes": 0,
                 "adpcm_a_register_writes": 0, "adpcm_a_reads": 0,
                 "adpcm_a_control_writes": 0,
                 "adpcm_b_register_writes": 0, "adpcm_b_reads": 0,
                 "adpcm_b_control_writes": 0,
                 "native_nonzero_frames": 0},
            ],
            "board_observations": board,
        }
        pcm = struct.pack("<hhhhhhhh", 1, -1, 2, -2, 3, -3, 4, -4)
        self.assertTrue(qualification._sound_window_observation_is_valid(
            observation, {"name": "fire", "first_frame": 3, "last_frame": 4},
            pcm, expected_masks=[0x40, 0x40], require_diagnostics=True)[0])
        reset_board = [board[0], {**board[1], "sound_cpu_cycles": 50,
                                  "sound_cpu_reset": True}]
        self.assertTrue(qualification._sound_window_observation_is_valid(
            {**observation, "board_observations": reset_board},
            {"name": "fire", "first_frame": 3, "last_frame": 4},
            pcm, expected_masks=[0x40, 0x40], require_diagnostics=True)[0])
        malformed_chip = {**chip, "event_dropped": 1}
        malformed_family = {**chip, "register_events": [
            {**chip["register_events"][0], "family": 2}]}
        malformed_board = [{**board[0], "frame": 99}, board[1]]
        decreasing_cycles = [board[0], {**board[1], "sound_cpu_cycles": 400}]
        for malformed in (
                {**observation, "chip_observation": malformed_chip},
                {**observation, "chip_observation": malformed_family},
                {**observation, "board_observations": malformed_board},
                {**observation, "board_observations": decreasing_cycles},
                {**observation, "chip_frames": [observation["chip_frames"][0]]},
                {**observation, "chip_frames": [
                    observation["chip_frames"][0],
                    {**observation["chip_frames"][1], "frame": 5}]},
                {**observation, "chip_frames": [
                    observation["chip_frames"][0],
                    {**observation["chip_frames"][1], "chip_clocks": 99}]},
                {key: value for key, value in observation.items()
                 if key != "chip_observation"},
        ):
            with self.subTest(observation=malformed):
                self.assertFalse(qualification._sound_window_observation_is_valid(
                    malformed,
                    {"name": "fire", "first_frame": 3, "last_frame": 4},
                    pcm, expected_masks=[0x40, 0x40],
                    require_diagnostics=True)[0])

    def test_phase07_family_status_never_equates_register_writes_with_output(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        def window(**overrides: int) -> dict[str, object]:
            chip = {
                "ssg_register_writes": 0, "native_ssg_nonzero_frames": 0,
                "fm_register_writes": 0, "fm_key_on_writes": 0,
                "native_stereo_nonzero_frames": 0,
                "adpcm_a_register_writes": 0, "adpcm_a_reads": 0,
                "adpcm_b_register_writes": 0, "adpcm_b_reads": 0,
            }
            chip.update(overrides)
            return {"chip_observation": chip,
                    "board_observations": [
                        {"sound_cpu_cycles": 100, "sound_cpu_reset": False},
                        {"sound_cpu_cycles": 200, "sound_cpu_reset": False},
                    ]}

        families = qualification._phase07_family_classification({
            "action": {"windows": {
                "music": window(fm_register_writes=4),
                "fire": window(ssg_register_writes=3,
                               native_ssg_nonzero_frames=0),
                "control": window(adpcm_a_register_writes=2),
                "release": window(adpcm_b_register_writes=1,
                                  adpcm_b_reads=4),
            }},
        })
        self.assertEqual(families["status"], "classified_local_diagnostics")
        self.assertEqual(families["fm"], "register_activity_without_key_on")
        self.assertEqual(families["ssg"], "activity_observed_without_native_output")
        self.assertEqual(families["adpcm_a"], "register_activity_without_sample_reads")
        self.assertEqual(families["adpcm_b"], "decoder_activity_without_native_output")
        self.assertEqual(families["sound_cpu_execution"], "cycles_advanced")
        for reset in (True, None):
            row = window()
            if reset is None:
                row["board_observations"][-1].pop("sound_cpu_reset")
            else:
                row["board_observations"][-1]["sound_cpu_reset"] = reset
            rejected = qualification._phase07_family_classification({
                "action": {"windows": {"music": row}}})
            self.assertEqual(rejected["sound_cpu_execution"], "no_cycle_progress")

    def test_phase06_frontend_dispatch_requires_actual_bound_predicates(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        argv = ["qualify_local_boot.py", "--active-scene", "frontend",
                "--scene-contract", "local/qualification/phase06-contract.json",
                "--sound-contract", "local/qualification/phase07-sound-contract.json"]
        good = {"status": "active_scene_frontend_recorded",
                "private_identity_recorded": True,
                "predicate_results": {"overall": "pass"},
                "audio_evidence": {"status": "pass"}, "sound_outcomes": {"overall":"pass"}}
        for result, expected in ((good, 0),
                                 ({**good, "private_identity_recorded": False}, 1),
                                 ({**good, "predicate_results": {"overall": "unknown"}}, 1),
                                 ({**good, "audio_evidence": {"status": "unavailable"}}, 1),
                                 ({**good, "sound_outcomes": {"overall":"unknown"}}, 1),
                                 ({key:value for key,value in good.items() if key != "sound_outcomes"},1),
                                 ({key: value for key, value in good.items()
                                   if key != "audio_evidence"}, 1)):
            with self.subTest(result=result), mock.patch("sys.argv", argv), \
                 mock.patch.object(qualification, "run_active_scene_frontend",
                                   create=True, return_value=result) as run, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(qualification.main(), expected)
                run.assert_called_once()

    def test_phase06_frontend_calibration_exit_requires_passing_predicates(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        argv = ["qualify_local_boot.py", "--active-scene", "frontend",
                "--active-frontend-calibrate", "--scene-contract",
                "local/qualification/phase06-contract.json"]
        results = (
            ({"status": "active_scene_frontend_calibration_recorded",
              "private_identity_recorded": True,
              "predicate_results": {"overall": "fail"}}, 1),
            ({"status": "active_scene_frontend_incomplete",
              "private_identity_recorded": True,
              "predicate_results": {"overall": "unknown"}}, 1),
            ({"status": "active_scene_frontend_incomplete",
              "private_identity_recorded": True,
              "predicate_results": {"overall": "pass"}}, 1),
            ({"status": "active_scene_frontend_calibration_recorded",
              "private_identity_recorded": True,
              "predicate_results": {"overall": None}}, 1),
            ({"status": "active_scene_frontend_calibration_recorded",
              "private_identity_recorded": True,
              "predicate_results": []}, 1),
            ({"status": "active_scene_frontend_calibration_recorded",
              "private_identity_recorded": True}, 1),
            ({"status": "active_scene_frontend_calibration_recorded",
              "private_identity_recorded": True,
              "predicate_results": {"overall": "pass"}}, 0),
        )
        for result, expected in results:
            with self.subTest(result=result), mock.patch("sys.argv", argv), \
                 mock.patch.object(qualification, "run_active_scene_frontend",
                                   return_value=result) as run, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(qualification.main(), expected)
                run.assert_called_once()

    def test_phase06_frontend_capture_rejects_missing_or_wrong_observations(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        validate = getattr(qualification, "active_scene_frontend_capture_is_valid", None)
        self.assertTrue(callable(validate), "frontend capture requires a strict observation validator")
        from retroarch_smoke import parse_mvs_input_observations
        records = parse_mvs_input_observations(
            "glueyneo: mvs B 0 0 0 0\n"
            "glueyneo: mvs S 1 32 0 0\n"
            "glueyneo: mvs V 2 32 2 405504\n"
            "glueyneo: mvs V 6 32 6 1216512\n", invocation_id="original-guest")
        capture = {"invocation_id": "original-guest", "sha256": "a" * 64,
                   "target_frame": 2, "sampled_mask": 32,
                   "successful_video_interval": [2, 6], "exact_frame": "unknown"}
        self.assertTrue(validate(capture, records, invocation_id="original-guest",
                                 expected_mask=32, origin=0, target_frame=2))
        for mutation in ({"invocation_id": "stale"}, {"sampled_mask": 0},
                         {"successful_video_interval": [6, 2]},
                         {"successful_video_interval": [2, 99]},
                         {"successful_video_interval": [66, 130]},
                         {"exact_frame": 2}, {"sha256": "bad"}):
            self.assertFalse(validate({**capture, **mutation}, records,
                                     invocation_id="original-guest", expected_mask=32,
                                     origin=0, target_frame=2))

    def test_phase06_frontend_freeze_requires_exact_review_evidence(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        native = {"schedule": {"active_frames": 7}, "predicates": {"minimum": 2},
                  "frontend": {"frozen": False}, "contract_identity": "first"}
        identity = qualification._active_frontend_native_identity(native)
        self.assertEqual(identity, qualification._active_frontend_native_identity({
            **native, "frontend": {"frozen": True}, "contract_identity": "second"}))
        self.assertNotEqual(identity, qualification._active_frontend_native_identity({
            **native, "predicates": {"minimum": 1}}))
        self.assertNotEqual(identity, qualification._active_frontend_native_identity({
            **native, "schedule": {"active_frames": 8}}))
        sources = {"core_sha256": "a" * 64}
        frontend = {"frozen": True, "sources": sources, "calibration_outcome": "captures_ready"}
        self.assertFalse(qualification._active_frontend_frozen_evidence_valid(frontend, sources, {}))
        for changes in ({"semantic_review": "observed"},
                        {"semantic_review": "observed", "reviewed_capture_identity": "b" * 64,
                         "calibration_report": "/unowned/report.json"},
                        {"semantic_review": "observed", "reviewed_capture_identity": "bad"}):
            self.assertFalse(qualification._active_frontend_frozen_evidence_valid(
                {**frontend, **changes}, sources, {}))
        argv = ["qualify_local_boot.py", "--active-scene", "frontend",
                "--scene-contract", "local/qualification/phase06-contract.json",
                "--active-frontend-freeze", "local/qualification/review.json"]
        with mock.patch("sys.argv", argv), \
             mock.patch.object(qualification, "freeze_active_scene_frontend", return_value={
                 "status": "active_scene_frontend_contract_frozen"}) as freeze, \
             mock.patch.object(qualification, "run_active_scene_frontend") as run, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(qualification.main(), 0)
            freeze.assert_called_once()
            run.assert_not_called()

    def test_phase06_frozen_replay_validates_complete_synthetic_calibration(self) -> None:
        from tools.mvs import qualify_local_boot as q
        replay = q._load_frontend_replay()
        smoke = q._load_retroarch_smoke()
        contract, _, _ = self._phase06_pair_evidence_fixture()
        contract.update(t0_frame=0, endpoint_frame=40)
        schedule = contract["schedule"]
        schedule["active_frames"] = 48
        for pair in schedule["pairs"].values():
            pair["capture_frames"] = [0, 8, 16, 24, 32, 40]
            for role in ("action", "control"):
                mask = int(pair[role].split(":0x")[1].split(",")[0], 16)
                pair[role] = f"10:0x{mask:x},30:0x0"
        for role in ("action", "control"):
            schedule["pairs"]["scroll"][role] = schedule["pairs"]["scroll"][role].replace("30:", "40:")
        implementation = replay._implementation_identity()
        sources = {"core_sha256": "a" * 64, "evaluator": {"sha256": implementation["evaluator"]},
                   "collector_sha256": implementation["collector"], "replay_sha256": implementation["helper"]}
        app = dict(core_sha256="a" * 64, retroarch_version="1.22.2",
                   retroarch_executable_sha256="f" * 64, bundle_id="org.example.original")
        config = "synthetic config"
        config_hash = hashlib.sha256(config.encode()).hexdigest()
        report = dict(status="complete", sources=sources,
                      composition_policy=q.FRONTEND_COMPOSITION_POLICY,
                      temporal_alignment="pass", media_identity=[], app_identity=app, contract_identity="d" * 64,
                      configuration_identity="configuration",
                      native_contract_identity=q._active_frontend_native_identity(contract),
                      frontend_schedule_identity=q.active_scene_configuration_identity(schedule),
                      predicates={key: "pass" for key in ("scene", "composition", "right", "left",
                                  "projectile", "release", "combined", "scroll", "overall")},
                      invocations=[])
        contract["media_identity"] = []
        contract["contract_identity"] = "d" * 64
        report["native_contract_identity"] = q._active_frontend_native_identity(contract)
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            try:
                os.chdir(root)
                for index, (pair, role) in enumerate((p, r) for p in sorted(schedule["pairs"])
                                                    for r in ("action", "control")):
                    identifier = f"{index:032x}"
                    directory = Path("local/qualification/phase06") / ("run-" + identifier) / "captures"
                    directory.mkdir(parents=True)
                    events = q._active_scene_input_events(schedule, pair, role)
                    changes = {1: 0, 2: 1, 3: 0, 4: 2, 5: 0}
                    changes.update({6 + target: mask for target, mask in events})
                    records, mask = [], 0
                    def record(kind, sample, value, video):
                        return dict(event_kind=kind, sample_sequence=sample, sampled_mask=value,
                                    successful_video_sequence=video, executed_cycles=video * 100,
                                    invocation_id=identifier)
                    records.append(record("B", 0, 0, 0))
                    for seq in range(1, 49):
                        if seq in changes and (seq == 1 or changes[seq] != mask):
                            mask = changes[seq]
                            records.append(record("S", seq, mask, seq - 1))
                        records.append(record("V", seq, mask, seq))
                        if seq == 4:
                            records.append(record("P", seq, mask, seq))
                    inv = dict(pair=pair, role=role, invocation_id=identifier,
                               status="complete", frontend_exit_code=0,
                               active_origin_video_sequence=6, observations=records,
                               observed_events=[dict(target_frame=t, mask=m, sample_sequence=6+t,
                                                     successful_video_sequence=6+t) for t, m in events],
                               identity=app, selected_bundle_sha256="b" * 64,
                               configuration_text=config, configuration_sha256=config_hash, captures=[])
                    for target in schedule["pairs"][pair]["capture_frames"]:
                        path = directory / f"capture-{target}.png"
                        import zlib
                        def chunk(kind, data):
                            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
                        path.write_bytes(b"\x89PNG\r\n\x1a\n" +
                            chunk(b"IHDR", struct.pack(">IIBBBBB", 320, 224, 8, 2, 0, 0, 0)) +
                            chunk(b"IDAT", zlib.compress((b"\0" + b"\0" * 960) * 224)) + chunk(b"IEND", b""))
                        digest = hashlib.sha256(path.read_bytes()).hexdigest()
                        inv["captures"].append(dict(path=str(path.resolve()), sha256=digest,
                            invocation_id=identifier, capture_sha256=digest, exact_frame="unknown",
                            target_frame=target, sampled_mask=next(r["sampled_mask"] for r in records
                                if r["event_kind"] == "V" and r["sample_sequence"] == 6+target),
                            successful_video_interval=[6+target, 7+target]))
                    inv["replay"] = dict(policy=replay.POLICY, status="pass", core_sha256="a" * 64,
                        bundle_sha256="b" * 64, binding=replay.replay_binding("a" * 64, "b" * 64, inv, "configuration"),
                        captures=[dict(capture_sha256=c["sha256"], successful_video_interval=c["successful_video_interval"],
                                       matching_sequences=c["successful_video_interval"]) for c in inv["captures"]])
                    report["invocations"].append(inv)
                report_path = Path("local/qualification/phase06/run-" + "f"*32 + "/frontend-report.json")
                report_path.parent.mkdir(parents=True)
                frontend = dict(frozen=True, sources=sources, semantic_review="observed",
                    composition_policy=q.FRONTEND_COMPOSITION_POLICY, calibration_outcome="captures_ready",
                    schedule_policy="same_controls_bounded_retiming_v1", schedule=schedule,
                    native_schedule_identity=q.active_scene_configuration_identity(schedule),
                    app_identity=app, configuration_identity="configuration",
                    reviewed_capture_identity=report["invocations"][0]["captures"][0]["sha256"],
                    calibration_report=str(report_path))
                def check(candidate, *, update_digest=True):
                    report_path.write_text(json.dumps(candidate))
                    if update_digest:
                        frontend["calibration_report_sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
                    return q._active_frontend_frozen_evidence_valid(frontend, sources, contract)
                with mock.patch.object(q, "PROJECT_ROOT", root), \
                        mock.patch.object(q, "ignored", return_value=True), \
                        mock.patch.object(q, "_load_frontend_replay", return_value=replay), \
                        mock.patch.object(q, "_load_retroarch_smoke", return_value=smoke):
                    self.assertTrue(check(report))
                    self.assertTrue(q._active_frontend_frozen_evidence_valid(
                        frontend, {"core_sha256": "e" * 64}, contract),
                        "frozen Phase06 evidence must be checked against its persisted "
                        "identity while Phase07 independently reruns current sources")
                    for mutate in (
                            lambda r: r["invocations"][0].pop("replay"),
                            lambda r: r["predicates"].update(right="fail"),
                            lambda r: r.update(composition_policy="legacy_fixed_crop")):
                        bad = copy.deepcopy(report)
                        mutate(bad)
                        self.assertFalse(check(bad))
                    tampered = copy.deepcopy(report)
                    tampered["invocations"][0]["replay"]["binding"] = "0" * 64
                    self.assertFalse(check(tampered, update_digest=False))
                    self.assertTrue(check(report))
                    with mock.patch.object(replay, "_implementation_identity", return_value={"changed": "source"}):
                        self.assertTrue(check(report))
                    self.assertTrue(check(report))
                    contract["frontend"] = frontend
                    with mock.patch.object(q, "validate_scene_contract", return_value=("valid", contract)), \
                            mock.patch.object(q, "_sha256_path", return_value="e" * 64), \
                            mock.patch.object(q, "run_active_scene_frontend", side_effect=AssertionError("no GUI")), \
                            mock.patch.object(replay, "_child", side_effect=AssertionError("no native execution")):
                        original = report_path.read_bytes()
                        evaluated = q.evaluate_retained_frontend_captures(report_path, q.PHASE06_CONTRACT_PATH)
                        self.assertEqual(evaluated["status"], "retained_frontend_evaluated")
                        self.assertNotEqual(evaluated["predicate_results"]["overall"], "pass",
                                            "black PNGs and an incomplete scene oracle cannot pass")
                        self.assertFalse(evaluated["new_frontend_observation"])
                        self.assertEqual(original, report_path.read_bytes())
                        for mutate in (
                                lambda r: r["invocations"][0]["replay"].update(binding="0" * 64),
                                lambda r: r["invocations"].pop(),
                                lambda r: r.update(frontend_schedule_identity="0" * 64),
                                lambda r: r["sources"].update(replay_sha256="0" * 64),
                                lambda r: r["invocations"][0]["captures"][0].update(sha256="0" * 64)):
                            bad = copy.deepcopy(report); mutate(bad)
                            report_path.write_text(json.dumps(bad))
                            rejected = q.evaluate_retained_frontend_captures(report_path, q.PHASE06_CONTRACT_PATH)
                            self.assertEqual(rejected["status"], "retained_frontend_evaluation_rejected")
                        report_path.write_bytes(original)
            finally:
                os.chdir(old_cwd)

    def test_phase06_freeze_and_frozen_acceptance_read_core_without_rebuilding(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        current_core = getattr(qualification, "_current_frontend_core", None)
        self.assertTrue(callable(current_core),
                        "freeze and frozen acceptance must read the exact calibrated core")
        evaluator_identity = {"path": "/private/evaluator.py", "scope": "production",
                              "sha256": "c" * 64}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root / "local" / "qualification"
            private.mkdir(parents=True)
            report_path = private / "frontend-report.json"
            report_path.write_text(json.dumps({"invocations": []}), encoding="utf-8")
            review_path = private / "frontend-review.json"
            review_path.write_text(json.dumps({
                "schema_version": 1, "review_outcome": "pass",
                "semantic_review": "observed", "reviewed_capture_identity": "d" * 64,
                "calibration_report_sha256": "b" * 64,
                "evaluator_identity": evaluator_identity,
                "composition_references": []}), encoding="utf-8")
            contract = {"frontend": {"frozen": False,
                         "calibration_outcome": "captures_ready",
                         "calibration_report": str(report_path),
                         "calibration_report_sha256": "b" * 64}}
            with mock.patch.object(qualification, "PROJECT_ROOT", root), \
                 mock.patch.object(qualification, "validate_scene_contract",
                                   return_value=("active_scene_contract_valid", contract)), \
                 mock.patch.object(qualification, "ignored", return_value=True), \
                 mock.patch.object(qualification, "_production_evaluator_identity",
                                   return_value=evaluator_identity), \
                 mock.patch.object(qualification, "_active_frontend_frozen_evidence_valid",
                                   return_value=True), \
                 mock.patch.object(qualification, "_load_retroarch_smoke",
                                   return_value=mock.Mock()), \
                 mock.patch.object(qualification, "_current_frontend_core",
                                   return_value={"path": str(root / "core.dylib"),
                                                 "sha256": "a" * 64}) as current, \
                 mock.patch.object(qualification, "_active_frontend_sources",
                                   return_value={"core_sha256": "a" * 64}), \
                 mock.patch.object(qualification, "_build_frontend_core",
                                   side_effect=AssertionError("freeze must not rebuild")) as build, \
                 mock.patch.object(qualification, "_create_active_scene_run_directory",
                                   return_value=private / "run-write"), \
                 mock.patch.object(qualification, "_write_active_scene_contract",
                                   return_value=True):
                frozen = qualification.freeze_active_scene_frontend(root / "contract.json", review_path)
                self.assertEqual(frozen["status"], "active_scene_frontend_contract_frozen")
                current.assert_called_once_with(observations=True)
                build.assert_not_called()
                current.reset_mock()
                current.return_value = None
                contract["frontend"]["frozen"] = True
                result = qualification.run_active_scene_frontend(
                    Path("local/roms"), None, root / "contract.json", calibrate=False)
                self.assertEqual(result["status"], "active_scene_frontend_build_failed")
                current.assert_called_once_with(observations=True)
                build.assert_not_called()

    def test_phase06_observation_core_rejects_stale_runtime_input_without_rebuilding(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        suffix = {"darwin": ".dylib", "win32": ".dll"}.get(sys.platform, ".so")
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            build = project / "build" / "local-frontend-observations"
            build.mkdir(parents=True)
            source = build / "runtime.c"
            source.write_text("runtime revision one\n", encoding="utf-8")
            core = build / ("glueyneo_libretro" + suffix)
            (build / "build.ninja").write_text(
                "rule compile\n"
                "  command = cmake -E copy $in $out\n"
                f"build {core.name}: compile {source.name}\n"
                f"build glueyneo_libretro: phony {core.name}\n"
                "default glueyneo_libretro\n", encoding="utf-8")
            built = subprocess.run(["ninja", "-C", str(build), "glueyneo_libretro"],
                                   capture_output=True, text=True, check=False)
            self.assertEqual(built.returncode, 0, built.stderr)
            with mock.patch.object(qualification, "PROJECT_ROOT", project):
                before = qualification._current_frontend_core(observations=True)
                self.assertIsNotNone(before)
                core_sha256 = before["sha256"]
                source.write_text("runtime revision two\n", encoding="utf-8")
                os.utime(source, ns=(source.stat().st_atime_ns,
                                     core.stat().st_mtime_ns + 2_000_000_000))
                self.assertEqual(qualification._file_identity(core)["sha256"], core_sha256)
                self.assertIsNone(
                    qualification._current_frontend_core(observations=True),
                    "read-only freeze/acceptance must reject a changed runtime input even "
                    "when the previously linked core bytes still match")
                report_path = project / "local" / "qualification" / "frontend-report.json"
                report_path.parent.mkdir(parents=True)
                report_path.write_text("{}", encoding="utf-8")
                review_path = report_path.parent / "review.json"
                evaluator_identity = {"path": "/private/evaluator.py", "scope": "production",
                                      "sha256": "c" * 64}
                review_path.write_text(json.dumps({
                    "schema_version": 1, "review_outcome": "pass",
                    "calibration_report_sha256": "b" * 64,
                    "evaluator_identity": evaluator_identity,
                    "composition_references": []}), encoding="utf-8")
                contract = {"schedule": {}, "frontend": {
                    "frozen": False, "calibration_outcome": "captures_ready",
                    "calibration_report": str(report_path),
                    "calibration_report_sha256": "b" * 64}}
                contract_path = project / "contract.json"
                with mock.patch.object(qualification, "validate_scene_contract",
                                       return_value=("active_scene_contract_valid", contract)), \
                     mock.patch.object(qualification, "ignored", return_value=True), \
                     mock.patch.object(qualification, "_production_evaluator_identity",
                                       return_value=evaluator_identity), \
                     mock.patch.object(qualification, "_active_frontend_frozen_evidence_valid",
                                       return_value=True), \
                     mock.patch.object(qualification, "_load_retroarch_smoke",
                                       return_value=mock.Mock()), \
                     mock.patch.object(qualification, "_create_active_scene_run_directory",
                                       return_value=build), \
                     mock.patch.object(qualification, "_write_active_scene_contract",
                                       return_value=True) as write_contract:
                    frozen = qualification.freeze_active_scene_frontend(contract_path, review_path)
                    self.assertEqual(frozen["status"], "active_scene_frontend_freeze_rejected")
                    write_contract.assert_not_called()
                contract["frontend"]["frozen"] = True
                with mock.patch.object(qualification, "validate_scene_contract",
                                       return_value=("active_scene_contract_valid", contract)), \
                     mock.patch.object(qualification, "_active_frontend_frozen_evidence_valid",
                                       return_value=True), \
                     mock.patch.object(qualification, "_active_frontend_schedule_compatible",
                                       return_value=True), \
                     mock.patch.object(qualification, "_create_active_scene_run_directory",
                                       return_value=None):
                    accepted = qualification.run_active_scene_frontend(
                        project, None, contract_path, calibrate=False)
                    self.assertEqual(accepted["status"], "active_scene_frontend_build_failed")

    def test_phase06_frontend_start_and_scheduled_masks_require_successful_video(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        from retroarch_smoke import parse_mvs_input_observations
        text = ("glueyneo: mvs B 0 0 0 0\n"
                "glueyneo: mvs S 1 0 0 0\n"
                "glueyneo: mvs V 1 0 1 202752\n"
                "glueyneo: mvs R 1 0 1 202752\n"
                "glueyneo: mvs S 2 1 1 202752\n"
                "glueyneo: mvs V 2 1 2 405504\n"
                "glueyneo: mvs S 3 0 2 405504\n"
                "glueyneo: mvs V 3 0 3 608256\n"
                "glueyneo: mvs S 4 2 3 608256\n"
                "glueyneo: mvs V 4 2 4 811008\n"
                "glueyneo: mvs P 4 2 4 811008\n"
                "glueyneo: mvs S 5 0 4 811008\n"
                "glueyneo: mvs V 5 0 5 1013760\n"
                "glueyneo: mvs S 7 32 6 1216512\n"
                "glueyneo: mvs V 7 32 7 1419264\n")
        record = {"observations": parse_mvs_input_observations(text, invocation_id="guest"),
                  "active_origin_video_sequence": 5,
                  "observed_events": [{"target_frame": 1, "mask": 32,
                                       "sample_sequence": 7, "successful_video_sequence": 7}]}
        self.assertTrue(qualification._active_frontend_events_valid(record, [(1, 32)], "guest"))
        for mutation in ({"observed_events": []}, {"active_origin_video_sequence": 4},
                         {"observed_events": [{"target_frame": 1, "mask": 0,
                                               "sample_sequence": 7, "successful_video_sequence": 7}]}):
            self.assertFalse(qualification._active_frontend_events_valid(
                {**record, **mutation}, [(1, 32)], "guest"))
        wrong_start = text.replace("S 4 2", "S 4 64").replace("V 4 2", "V 4 64").replace("P 4 2", "P 4 64")
        record["observations"] = parse_mvs_input_observations(wrong_start, invocation_id="guest")
        self.assertFalse(qualification._active_frontend_events_valid(record, [(1, 32)], "guest"))

        extra = text + "glueyneo: mvs S 8 64 7 1419264\n" + "glueyneo: mvs V 8 64 8 1622016\n"
        record["observations"] = parse_mvs_input_observations(extra, invocation_id="guest")
        self.assertFalse(qualification._active_frontend_events_valid(record, [(1, 32)], "guest"))

    def test_phase06_frontend_temporal_comparison_requires_overlapping_held_windows(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        contract, _, _ = self._phase06_pair_evidence_fixture()
        schedule = contract["schedule"]
        schedule["active_frames"] = 100
        records = []
        for pair, value in schedule["pairs"].items():
            release = 70 if pair == "scroll" else 40
            value["capture_frames"] = [0, 10, 20, 30, 60, 80]
            for role in ("action", "control"):
                initial_mask = int(value[role].split(":", 1)[1].split(",")[0], 16)
                value[role] = f"5:0x{initial_mask:x},{release}:0x0"
                records.append({"pair": pair, "role": role, "active_origin_video_sequence": 100,
                                "observed_events": [{"target_frame": 5, "successful_video_sequence": 105},
                                                    {"target_frame": release, "successful_video_sequence": 100 + release}],
                                "captures": [{"successful_video_interval": [100 + frame, 102 + frame]}
                                             for frame in value["capture_frames"]]})
        self.assertTrue(qualification._active_frontend_temporal_bounds_valid(schedule, records))
        delayed = copy.deepcopy(records)
        delayed[1]["captures"][1]["successful_video_interval"] = [120, 122]
        self.assertFalse(qualification._active_frontend_temporal_bounds_valid(schedule, delayed))
        crossing = copy.deepcopy(records)
        crossing[0]["captures"][3]["successful_video_interval"] = [135, 142]
        self.assertFalse(qualification._active_frontend_temporal_bounds_valid(schedule, crossing))
        wide = copy.deepcopy(records)
        wide[0]["captures"][1]["successful_video_interval"] = [110, 125]
        self.assertFalse(qualification._active_frontend_temporal_bounds_valid(schedule, wide))
        self.assertFalse(qualification._active_frontend_temporal_bounds_valid(schedule, records[:-1]))

    def test_phase06_frontend_retiming_preserves_native_controls_and_scene(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        contract, _, _ = self._phase06_pair_evidence_fixture()
        contract.update(t0_frame=0, endpoint_frame=5)
        # The fixture's scroll release is beyond its final capture; compatible
        # translation must release within the reviewed endpoint observation.
        for role in ("action", "control"):
            contract["schedule"]["pairs"]["scroll"][role] = contract["schedule"]["pairs"]["scroll"][role].replace("6:", "5:")
        schedule = copy.deepcopy(contract["schedule"])
        self.assertTrue(qualification._active_frontend_schedule_compatible(contract, schedule))
        for mutation in ({"entry_inputs": "1:0x40,2:0x0"},
                         {"active_frames": 8}, {"frame_cycles": 200000}):
            self.assertFalse(qualification._active_frontend_schedule_compatible(contract, {**schedule, **mutation}))
        changed = copy.deepcopy(schedule)
        changed["pairs"]["right"]["action"] = "1:0x40,4:0x0"
        self.assertFalse(qualification._active_frontend_schedule_compatible(contract, changed))
        changed = copy.deepcopy(schedule)
        changed["pairs"]["right"]["control"] = "2:0x0,4:0x0"
        self.assertFalse(qualification._active_frontend_schedule_compatible(contract, changed))
        extended = copy.deepcopy(contract)
        extended["endpoint_frame"] = 300
        extended["schedule"]["active_frames"] = 1000
        for value in extended["schedule"]["pairs"].values():
            value["capture_frames"] = [0, 100, 150, 200, 250, 300]
            for role in ("action", "control"):
                masks = [int(event.split(":")[1], 16) for event in value[role].split(",")]
                value[role] = f"100:0x{masks[0]:x},200:0x{masks[-1]:x}"
        for role in ("action", "control"):
            extended["schedule"]["pairs"]["scroll"][role] = extended["schedule"]["pairs"]["scroll"][role].replace("200:", "250:")
        shifted = copy.deepcopy(extended["schedule"])
        for role in ("action", "control"):
            shifted["pairs"]["right"][role] = shifted["pairs"]["right"][role].replace("100:", "164:").replace("200:", "264:")
        self.assertTrue(qualification._active_frontend_schedule_compatible(extended, shifted))
        for role in ("action", "control"):
            shifted["pairs"]["right"][role] = shifted["pairs"]["right"][role].replace("164:", "165:").replace("264:", "265:")
        self.assertFalse(qualification._active_frontend_schedule_compatible(extended, shifted))

    def test_phase06_native_contract_requires_frozen_complete_causal_schema(self) -> None:
        capture_frames = [600, 605, 610, 620, 660, 720]
        contract = {
            "schema_version": 1, "mode": "native", "frozen": True,
            "t0_frame": 600, "endpoint_frame": 720,
            "code_identity": {
                "importer": {"path": "/local/importer", "scope": "production",
                             "sha256": "a" * 64},
                "qualifier": {"path": "/local/qualifier", "scope": "production",
                              "sha256": "b" * 64},
            },
            "evaluator_identity": {"path": "/local/evaluator.py",
                                   "scope": "production", "sha256": "9" * 64},
            "media_identity": [{"size": 1, "sha256": "c" * 64},
                               {"size": 2, "sha256": "f" * 64}],
            "configuration_identity": "d" * 64,
            "schedule": {"setup": "scripted_start", "entry_inputs": "30:0x2,40:0x0",
                         "active_frames": 730,
                         "frame_cycles": 202752, "pairs": {
                "right": {"action": "601:0x20,631:0x0", "control": "601:0x0,631:0x0", "capture_frames": capture_frames},
                "left": {"action": "601:0x10,631:0x0", "control": "601:0x0,631:0x0", "capture_frames": capture_frames},
                "fire": {"action": "601:0x40,611:0x0", "control": "601:0x0,611:0x0", "capture_frames": capture_frames},
                "combined": {"action": "601:0x60,631:0x0", "control": "601:0x20,631:0x0", "capture_frames": capture_frames},
                "scroll": {"action": "601:0x20,721:0x0", "control": "601:0x0,721:0x0", "capture_frames": capture_frames},
            }},
            "checkpoints": [{"frame": frame, "file": f"frame-{frame:04}.ppm",
                             "sha256": "e" * 64} for frame in capture_frames],
            "regions": {"actor": [70, 135, 96, 45], "projectile": [145, 95, 165, 65],
                        "background": [0, 50, 92, 70], "composition": [60, 120, 110, 70],
                        "hud": [0, 0, 320, 50],
                        "playfield": [0, 50, 320, 174]},
            "predicates": {
                "scene": {"min_actor_pixels": 8, "min_hud_pixels": 1,
                          "min_playfield_colors": 2},
                "actor": {"min_red": 150, "min_green": 80, "max_blue": 30},
                "projectile": {"min_red": 180, "min_green": 85,
                               "max_blue": 30, "min_pixels": 3,
                               "min_player_separation_px": 8, "min_outward_dx": 2,
                               "min_track_overlap": 0.25},
                "movement": {"min_actor_dx": 2, "min_observations": 2,
                             "min_actor_pixels": 8, "min_track_overlap": 0.25},
                "background": {"min_horizontal_shift_px": 2,
                                "min_feature_overlap": 0.6,
                                "min_observations": 2, "min_unique_colors": 3},
                "combined": {"max_actor_dx_error": 1, "min_projectile_pixels": 3},
                "composition": {"min_unique_colors": 2, "min_observations": 2,
                                "references": [
                                    {"pair": "right", "role": "action", "frame": 605,
                                     "box": [60, 120, 8, 8], "sha256": "8" * 64,
                                     "claim": "palette"},
                                    {"pair": "right", "role": "action", "frame": 610,
                                     "box": [60, 120, 8, 8], "sha256": "7" * 64,
                                     "claim": "palette"},
                                    {"pair": "left", "role": "action", "frame": 605,
                                     "box": [72, 120, 8, 8], "sha256": "6" * 64,
                                     "claim": "layer"},
                                    {"pair": "left", "role": "action", "frame": 610,
                                     "box": [72, 120, 8, 8], "sha256": "5" * 64,
                                     "claim": "layer"},
                                ]},
            },
            "limits": {"active_frames": 730, "capture_count": 6,
                       "host_timeout_seconds": 120, "report_bytes_limit": 1048576},
            "sampled_inputs": [{"frame": 30, "mask": 0x2},
                               {"frame": 40, "mask": 0}],
            "requested_frames": 730,
            "completed_frames": 730,
            "observations": {"status": "active_frames_completed",
                             "calibration_configuration_identity": "1" * 64,
                             "capture_frames_requested": capture_frames,
                             "capture_frames_completed": capture_frames,
                             "images": []},
            "outcomes": {"calibration": "captures_ready",
                         "semantic_t0": "observed"},
        }
        contract["observations"]["images"] = contract["checkpoints"]
        contract["configuration_identity"] = active_scene_configuration_identity(
            contract["schedule"])
        contract["contract_identity"] = hashlib.sha256(
            json.dumps(contract, sort_keys=True, separators=(",", ":"))
            .encode("utf-8")).hexdigest()
        self.assertTrue(active_scene_native_contract_is_valid(contract))

        windows_paths = copy.deepcopy(contract)
        windows_paths["code_identity"]["importer"]["path"] = "C:/local/importer"
        windows_paths["code_identity"]["qualifier"]["path"] = "D:/local/qualifier"
        windows_paths["evaluator_identity"]["path"] = "E:/local/evaluator.py"
        windows_paths["contract_identity"] = hashlib.sha256(
            json.dumps({key: value for key, value in windows_paths.items()
                        if key != "contract_identity"}, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertTrue(active_scene_native_contract_is_valid(windows_paths))

        release_at_t0 = {**contract,
                         "schedule": {**contract["schedule"],
                                      "entry_inputs": "30:0x2,600:0x0"},
                         "sampled_inputs": [{"frame": 30, "mask": 0x2},
                                            {"frame": 600, "mask": 0}]}
        release_at_t0["configuration_identity"] = active_scene_configuration_identity(
            release_at_t0["schedule"])
        release_at_t0["contract_identity"] = hashlib.sha256(
            json.dumps({key: value for key, value in release_at_t0.items()
                        if key != "contract_identity"}, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertTrue(active_scene_native_contract_is_valid(release_at_t0))

        held_at_t0 = {**contract,
                      "schedule": {**contract["schedule"],
                                   "entry_inputs": "30:0x2,600:0x2,601:0x0"},
                      "sampled_inputs": [{"frame": 30, "mask": 0x2},
                                         {"frame": 600, "mask": 0x2},
                                         {"frame": 601, "mask": 0}]}
        held_at_t0["configuration_identity"] = active_scene_configuration_identity(
            held_at_t0["schedule"])
        held_at_t0["contract_identity"] = hashlib.sha256(
            json.dumps({key: value for key, value in held_at_t0.items()
                        if key != "contract_identity"}, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertFalse(active_scene_native_contract_is_valid(held_at_t0))

        delayed_action = {**contract,
                          "schedule": {**contract["schedule"], "pairs": {
                              **contract["schedule"]["pairs"], "right": {
                                  **contract["schedule"]["pairs"]["right"],
                                  "action": "604:0x20,631:0x0",
                                  "control": "604:0x0,631:0x0"}}}}
        delayed_action["configuration_identity"] = active_scene_configuration_identity(
            delayed_action["schedule"])
        delayed_action["contract_identity"] = hashlib.sha256(
            json.dumps({key: value for key, value in delayed_action.items()
                        if key != "contract_identity"}, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertTrue(active_scene_native_contract_is_valid(delayed_action))

        for changes in (
            {"frozen": False},
            {"endpoint_frame": 1200},
            {"regions": {**contract["regions"], "actor": [0, 0, 0, 45]}},
            {"regions": {**contract["regions"],
                          "background": [70, 135, 92, 45]}},
            {"schedule": {**contract["schedule"], "pairs": {
                **contract["schedule"]["pairs"], "left": {
                    "action": "601:0x40,631:0x0", "control": "601:0x0,631:0x0"}}}},
            {"checkpoints": contract["checkpoints"][:-1]},
            {"predicates": {"whole_frame_hash": True}},
            {"predicates": {
                **contract["predicates"], "composition": {
                    **contract["predicates"]["composition"],
                    "references": contract["predicates"]["composition"]["references"][:2] + [
                        {**reference, "claim": "layer"}
                        for reference in contract["predicates"]["composition"]["references"][:2]],
                },
            }},
            {"outcomes": None},
            {"observations": {**contract["observations"],
                              "calibration_configuration_identity": "stale"}},
            {"schedule": {**contract["schedule"], "pairs": {
                **contract["schedule"]["pairs"], "left": {
                    **contract["schedule"]["pairs"]["left"],
                    "capture_frames": [600, 606, 610, 620, 660, 720]}}}},
            {"schedule": {**contract["schedule"], "pairs": {
                **contract["schedule"]["pairs"], "fire": {
                    **contract["schedule"]["pairs"]["fire"],
                    "action": "601:0x40,604:0x0",
                    "control": "601:0x0,604:0x0"}}}},
            {"schedule": {**contract["schedule"], "entry_inputs": "601:0x2,602:0x0"}},
            {"schedule": {key: value for key, value in contract["schedule"].items()
                           if key != "entry_inputs"}},
            {"predicates": {
                **contract["predicates"],
                "scene": {**contract["predicates"]["scene"],
                          "min_actor_pixels": 0},
            }},
            {"predicates": {
                **contract["predicates"],
                "actor": {**contract["predicates"]["actor"], "min_red": 0},
            }},
            {"predicates": {
                **contract["predicates"],
                "projectile": {**contract["predicates"]["projectile"],
                               "max_blue": 85},
            }},
            {"predicates": {
                **contract["predicates"],
                "background": {
                    **contract["predicates"]["background"],
                    "min_horizontal_shift_px": 31,
                },
            }},
            {"evaluator_identity": {"path": "/local/evaluator.py",
                                    "scope": "fixture", "sha256": "0" * 64}},
            {"schedule": {**contract["schedule"], "pairs": {
                **contract["schedule"]["pairs"], "right": {
                    **contract["schedule"]["pairs"]["right"],
                    "action": "725:0x20,726:0x0",
                    "control": "725:0x0,726:0x0"}}}},
            {"schedule": {**contract["schedule"], "pairs": {
                **contract["schedule"]["pairs"], "left": {
                    **contract["schedule"]["pairs"]["left"],
                    "action": "601:0x10,602:0x0",
                    "control": "601:0x0,602:0x0"}}}},
        ):
            with self.subTest(changes=changes):
                mutated = {**contract, **changes}
                if "schedule" in changes:
                    mutated["configuration_identity"] = active_scene_configuration_identity(
                        mutated["schedule"])
                mutated["contract_identity"] = hashlib.sha256(
                    json.dumps({key: value for key, value in mutated.items()
                                if key != "contract_identity"}, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")).hexdigest()
                self.assertFalse(active_scene_native_contract_is_valid(mutated))

        report = {
            "status": "active_frames_completed",
            "code_identity": contract["code_identity"],
            "evaluator_identity": contract["evaluator_identity"],
            "media_identity": contract["media_identity"],
            "media_identity_after": contract["media_identity"],
            "media_identity_unchanged": True,
            "configuration_identity": "1" * 64,
            "active_frames_requested": contract["requested_frames"],
            "active_frames_completed": contract["completed_frames"],
            "capture_frames_requested": capture_frames,
            "capture_frames": capture_frames,
            "capture_observations": contract["checkpoints"],
            "native_report_local": {
                "status": "active_frames_completed", "guest_executed": True,
                "start_observed": True,
                "active_frames_requested": contract["requested_frames"],
                "active_frames_completed": contract["completed_frames"],
                "capture_frames_requested": capture_frames,
                "capture_frames": capture_frames,
                "sampled_inputs": contract["sampled_inputs"],
            },
        }
        self.assertTrue(active_scene_calibration_evidence_is_valid(contract, report))
        missing_samples_report = {
            **report,
            "native_report_local": {
                key: value for key, value in report["native_report_local"].items()
                if key != "sampled_inputs"
            },
        }
        for changes in (
            {"code_identity": {**contract["code_identity"], "qualifier": {}}},
            {"evaluator_identity": {**contract["evaluator_identity"],
                                    "sha256": "0" * 64}},
            {"media_identity": []},
            {"configuration_identity": "stale"},
            {"capture_frames": capture_frames[:-1]},
            {"capture_observations": contract["checkpoints"][:-1]},
            {"native_report_local": {"sampled_inputs": []}},
            {"native_report_local": missing_samples_report["native_report_local"]},
        ):
            self.assertFalse(active_scene_calibration_evidence_is_valid(
                contract, {**report, **changes}))

        self.assertEqual(_active_scene_input_events(contract["schedule"], "right", "action"),
                         [(30, 0x2), (40, 0), (601, 0x20), (631, 0)])
        self.assertEqual(_active_scene_input_events(contract["schedule"], "right", "control"),
                         [(30, 0x2), (40, 0), (601, 0), (631, 0)])

    def _phase06_pair_evidence_fixture(self) -> tuple[dict[str, object], dict[str, object], object]:
        captures = [0, 1, 2, 3, 4, 5]

        def frame(points: tuple[tuple[int, int, tuple[int, int, int]], ...] = ()) -> bytes:
            pixels = bytearray(320 * 224 * 3)
            for x, y, color in points:
                offset = (y * 320 + x) * 3
                pixels[offset:offset + 3] = bytes(color)
            return bytes(pixels)

        pairs = {
            "right": {"action": "1:0x20,4:0x0", "control": "1:0x0,4:0x0",
                      "capture_frames": captures},
            "left": {"action": "1:0x10,4:0x0", "control": "1:0x0,4:0x0",
                     "capture_frames": captures},
            "fire": {"action": "1:0x40,3:0x0", "control": "1:0x0,3:0x0",
                     "capture_frames": captures},
            "combined": {"action": "1:0x60,4:0x0", "control": "1:0x20,4:0x0",
                         "capture_frames": captures},
            "scroll": {"action": "1:0x20,6:0x0", "control": "1:0x0,6:0x0",
                       "capture_frames": captures},
        }
        contract: dict[str, object] = {
            "schedule": {"setup": "scripted_start", "entry_inputs": "",
                         "active_frames": 7, "frame_cycles": 202752,
                         "pairs": pairs},
            "regions": {"actor": [0, 0, 16, 16],
                        "projectile": [16, 0, 32, 16],
                        "background": [64, 64, 16, 16],
                        "composition": [0, 0, 48, 16],
                        "hud": [0, 0, 48, 16],
                        "playfield": [0, 0, 64, 16]},
            "predicates": {
                "scene": {"min_actor_pixels": 4, "min_hud_pixels": 1,
                          "min_playfield_colors": 2},
                "actor": {"min_red": 150, "min_green": 80, "max_blue": 30},
                "projectile": {"min_red": 180, "min_green": 85,
                               "max_blue": 30, "min_pixels": 3,
                               "min_player_separation_px": 8, "min_outward_dx": 2,
                               "min_track_overlap": 0.25},
                "movement": {"min_actor_dx": 2, "min_observations": 2,
                             "min_actor_pixels": 4, "min_track_overlap": 0.25},
                "background": {"min_horizontal_shift_px": 2,
                                "min_feature_overlap": 0.6,
                                "min_observations": 2, "min_unique_colors": 3},
                "combined": {"max_actor_dx_error": 1, "min_projectile_pixels": 3},
                "composition": {"min_unique_colors": 2, "min_observations": 2,
                                "references": []},
            },
        }
        baseline = frame(((2, 2, (220, 120, 20)), (3, 2, (220, 120, 20)),
                          (2, 3, (220, 120, 20)), (3, 3, (220, 120, 20))))
        stationary_scroll = frame(((65, 65, (20, 20, 20)),))
        default_pair = {"action": [baseline] * 6, "control": [baseline] * 6}
        runs: dict[str, object] = {
            "right": copy.deepcopy(default_pair),
            "left": copy.deepcopy(default_pair),
            "fire": copy.deepcopy(default_pair),
            "combined": copy.deepcopy(default_pair),
            "scroll": {"action": [baseline] + [stationary_scroll] * 5,
                       "control": [baseline] * 6},
        }
        return contract, runs, frame

    def test_phase06_scroll_requires_coherent_horizontal_translation(self) -> None:
        contract, runs, frame = self._phase06_pair_evidence_fixture()
        # A static one-pixel difference repeated in every action/control pair is
        # neither translation nor sustained scrolling.
        self.assertNotEqual(evaluate_active_scene_pairs(contract, runs)["scroll"],
                            "pass")

        # Recoloring a fixed background feature must not count as translation.
        recolored = copy.deepcopy(runs)
        actor = ((2, 2, (220, 120, 20)), (3, 2, (220, 120, 20)),
                 (2, 3, (220, 120, 20)), (3, 3, (220, 120, 20)))

        def textured(recolor: int | None = None) -> bytes:
            pixels = bytearray(frame(actor))
            for y in range(64, 80):
                for x in range(64, 80):
                    color = ((x * 37 + y * 17) % 251,
                             (x * 67 + y * 29) % 253,
                             (x * 97 + y * 41) % 255)
                    if recolor is not None and (x, y) == (70, 70):
                        color = (recolor, 200 - recolor, 35)
                    offset = (y * 320 + x) * 3
                    pixels[offset:offset + 3] = bytes(color)
            return bytes(pixels)

        recolored["scroll"] = {
            "action": [frame(actor)] + [textured(20 + index) for index in range(1, 6)],
            "control": [frame(actor)] + [textured() for _ in range(5)],
        }
        self.assertNotEqual(evaluate_active_scene_pairs(contract, recolored)["scroll"],
                            "pass")

        # The search bound must cover large coherent pans in a wide feature strip.
        from tools.mvs import qualify_local_boot as qualification
        contract["regions"]["background"] = [64, 64, 144, 16]

        def translated_features(world_dx: int) -> bytes:
            pixels = bytearray(frame(actor))
            for y in range(64, 80):
                for x in range(64, 208):
                    feature = hashlib.sha256(
                        f"{x + world_dx}:{y}".encode("ascii")).digest()[:3]
                    offset = (y * 320 + x) * 3
                    pixels[offset:offset + 3] = feature
            return bytes(pixels)

        translation = qualification._scene_horizontal_translation(
            contract, translated_features(0), translated_features(40))
        self.assertIsNotNone(translation)
        self.assertEqual(abs(translation[0]), 40)

    def test_phase06_actor_track_preserves_anchor_across_facing_flip(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        contract, _, frame = self._phase06_pair_evidence_fixture()
        contract["regions"]["actor"] = [0, 0, 48, 16]
        contract["regions"]["projectile"] = [20, 0, 28, 16]
        shape = {(2, 2), (2, 3), (2, 4), (2, 5), (3, 5),
                 (4, 5), (5, 5), (5, 4), (6, 5)}
        def actor_image(points, flash=False):
            colors = tuple((x, y, (220, 120, 20)) for x, y in points)
            if flash:
                colors += tuple((x, y, (250, 120, 10))
                                for y in range(2, 8) for x in range(24, 30))
            return frame(colors)
        baseline = actor_image(shape)
        reflected = {(8 - x, y) for x, y in shape}
        translated = {(x + 8, y) for x, y in reflected}
        self.assertEqual(qualification._scene_actor_translation(
            contract, baseline, actor_image(translated)), (8, 0))
        # Facing alone changes shape, but must preserve the position anchor.
        self.assertEqual(qualification._scene_actor_translation(
            contract, baseline, actor_image(reflected)), (0, 0))
        # The larger firing effect in its reserved ROI must not become the actor.
        self.assertEqual(qualification._scene_actor_translation(
            contract, baseline, actor_image(translated, flash=True)), (8, 0))

    def test_combined_animation_uses_independently_unique_intermediate_tracks(self) -> None:
        # Original connected shapes generated with seed 705; no game-derived pixels.
        from tools.mvs import qualify_local_boot as q
        a = {(-3,0),(-3,1),(-2,1),(-1,-1),(-1,0),(-1,1),(-1,2),(-1,3),
             (0,-2),(0,-1),(0,0),(0,1),(0,2),(0,3),(0,4),(1,-2),(1,-1),(1,0)}
        b = {(-3,0),(-3,1),(-2,-1),(-1,-1),(-1,0),(-1,1),(-1,3),
             (0,-2),(0,-1),(0,0),(0,2),(0,3),(1,-2),(1,-1),(1,0),(1,2),(2,-2)}
        c = {(-3,0),(-2,-1),(-1,-1),(-1,0),(-1,1),(0,-3),(0,-2),(0,-1),
             (0,0),(0,2),(0,3),(1,-2),(1,-1),(1,0),(2,-2)}
        contract, _, frame = self._phase06_pair_evidence_fixture()
        contract["regions"].update(actor=[0,0,64,24], projectile=[96,0,48,24])
        def image(shape, dx, shot=None):
            points = tuple((x+12+dx,y+8,(220,120,20)) for x,y in shape)
            if shot is not None:
                points += tuple((x,8,(250,120,10)) for x in range(shot,shot+3))
            return frame(points)
        baseline = image(a,0)
        self.assertIsNone(q._scene_actor_translation(contract, baseline, image(c,12)))
        self.assertEqual(q._scene_actor_translation(contract, baseline, image(b,6)), (6,0))
        self.assertEqual(q._scene_actor_translation(contract, image(b,6), image(c,12)), (6,0))
        action = [baseline,image(b,6,100),image(c,12,106),image(c,12,112),image(c,12),image(c,12)]
        control = [baseline,image(a,6),image(a,12),image(a,12),image(a,12),image(a,12)]
        def result(values):
            return evaluate_active_scene_pairs(contract, {"combined": {
                "action":values,"control":control}})["combined"]
        self.assertEqual(result(action), "pass")
        # Removing the independent anchor must leave the pose tie unresolved.
        no_anchor = [baseline,image(c,6,100),*action[2:]]
        self.assertNotEqual(result(no_anchor), "pass")
        # Translation without firing still cannot satisfy combined controls.
        self.assertNotEqual(result([baseline,image(b,6),image(c,12),image(c,12),
                                    image(c,12),image(c,12)]), "pass")

    def test_temporal_actor_tracks_reject_conflicting_unique_paths(self) -> None:
        from tools.mvs import qualify_local_boot as q
        track = getattr(q, "_scene_actor_track_translations", None)
        self.assertTrue(callable(track))
        base, one, two, target = b"base",b"one",b"two",b"target"
        mappings = {(base,base):{(0,0)},(base,one):{(4,0)},
                    (base,two):{(8,0)},(base,target):{(12,0),(13,0)},
                    (one,target):{(8,0)},(two,target):{(5,0)}}
        with mock.patch.object(q, "_scene_actor_translation_candidates",
                               side_effect=lambda _,a,b:mappings.get((a,b),set())):
            self.assertIsNone(track({},[base,one,two,target])[3])
            mappings[two,target] = {(4,0)}
            self.assertEqual(track({},[base,one,two,target])[3], (12,0))
            mappings[base,target] = set()
            self.assertIsNone(track({},[base,one,two,target])[3],
                              "intermediate evidence cannot rescue a below-threshold direct match")

    def test_phase06_combined_requires_projectile_contrast_against_movement_control(self) -> None:
        contract, runs, frame = self._phase06_pair_evidence_fixture()
        def tracked(actor_dx: int, projectile_x: int | None) -> bytes:
            points = tuple((x + actor_dx, y, (220, 120, 20))
                           for y in (2, 3) for x in (2, 3))
            if projectile_x is not None:
                points += tuple((x, 4, (250, 120, 10))
                                for x in range(projectile_x, projectile_x + 3))
            return frame(points)

        matched_track = [tracked(0, None), tracked(2, 20), tracked(4, 26),
                         tracked(6, 32), tracked(6, None), tracked(6, None)]
        runs["combined"] = {"action": matched_track,
                            "control": matched_track.copy()}
        self.assertNotEqual(evaluate_active_scene_pairs(contract, runs)["combined"],
                            "pass")

    def test_phase06_movement_requires_matched_t0_and_nontrivial_actor_track(self) -> None:
        contract, runs, frame = self._phase06_pair_evidence_fixture()
        left_actor = ((1, 2, (220, 120, 20)), (2, 2, (220, 120, 20)),
                      (1, 3, (220, 120, 20)), (2, 3, (220, 120, 20)))
        right_actor = ((3, 2, (220, 120, 20)), (4, 2, (220, 120, 20)),
                       (3, 3, (220, 120, 20)), (4, 3, (220, 120, 20)))
        # The offset is already present at t0 and never changes; endpoint-only
        # centroids incorrectly call this player movement.
        runs["right"] = {"action": [frame(right_actor)] * 6,
                         "control": [frame(left_actor)] * 6}
        self.assertNotEqual(evaluate_active_scene_pairs(contract, runs)["right"],
                            "pass")

        # A one-pixel animation point cannot stand in for a tracked actor.
        baseline = ((2, 2, (220, 120, 20)), (3, 2, (220, 120, 20)),
                    (2, 3, (220, 120, 20)), (3, 3, (220, 120, 20)))
        runs["right"] = {"action": [frame(baseline)] +
                                    [frame(((3, 2, (220, 120, 20)),))] * 5,
                         "control": [frame(baseline)] * 6}
        self.assertNotEqual(evaluate_active_scene_pairs(contract, runs)["right"],
                            "pass")

    def test_phase06_pixel_predicates_require_complete_distinct_pair_captures(self) -> None:
        contract, runs, frame = self._phase06_pair_evidence_fixture()
        runs["scene"] = {"status": "complete", "t0": runs["right"]["control"][0],
                          "endpoint": runs["right"]["control"][-1]}
        result = evaluate_active_scene_pairs(contract, runs)
        self.assertEqual(result["composition"], "unknown")
        self.assertNotEqual(result["overall"], "pass")

        # A complete but mismatched T0 must invalidate every paired claim.
        altered = copy.deepcopy(runs)
        altered["left"]["action"][0] = frame(((0, 0, (1, 2, 3)),))
        self.assertEqual(evaluate_active_scene_pairs(contract, altered)["overall"],
                         "fail")

        # Missing or partial captures remain unknown and cannot become a pass.
        partial = copy.deepcopy(runs)
        partial["fire"]["action"].pop()
        result = evaluate_active_scene_pairs(contract, partial)
        self.assertEqual(result["projectile"], "unknown")
        self.assertNotEqual(result["overall"], "pass")

    def test_phase06_causal_evidence_accepts_coherent_matched_native_tracks(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        contract, _runs, _unused_frame = self._phase06_pair_evidence_fixture()
        contract["regions"]["actor"] = [0, 0, 24, 16]
        contract["regions"]["projectile"] = [24, 0, 32, 16]
        contract["regions"]["composition"] = [0, 0, 56, 16]

        def frame(*, actor_present: bool = True, actor_dx: int = 0, background_dx: int = 0,
                  projectile_x: int | None = None) -> bytes:
            pixels = bytearray(320 * 224 * 3)

            def put(x: int, y: int, color: tuple[int, int, int]) -> None:
                offset = (y * 320 + x) * 3
                pixels[offset:offset + 3] = bytes(color)

            if actor_present:
                for y in range(2, 4):
                    for x in range(8 + actor_dx, 10 + actor_dx):
                        put(x, y, (220, 120, 20))
            put(40, 4, (255, 255, 255))
            for y in range(4, 12):
                for x in range(27, 35):
                    put(x, y, ((x * 11) % 255, (y * 19) % 255, 70))
            for y in range(64, 80):
                for x in range(64, 80):
                    world_x = x + background_dx
                    put(x, y, ((world_x * 37 + y * 17) % 251,
                               (world_x * 67 + y * 29) % 253,
                               (world_x * 97 + y * 41) % 255))
            if projectile_x is not None:
                for x in range(projectile_x, projectile_x + 3):
                    put(x, 8, (250, 120, 10))
            return bytes(pixels)

        baseline = frame()
        no_movement = [baseline] * 6
        right_action = [frame(actor_dx=min(2 * index, 8)) for index in range(6)]
        left_action = [frame(actor_dx=-min(2 * index, 6)) for index in range(6)]
        runs: dict[str, object] = {
            "right": {"action": right_action, "control": no_movement},
            "left": {"action": left_action, "control": no_movement},
            "fire": {"action": [baseline, frame(projectile_x=27),
                                  frame(projectile_x=35), baseline, baseline, baseline],
                     "control": no_movement},
            "combined": {
                "action": [frame(actor_dx=min(2 * index, 8),
                                 projectile_x=(None if index == 0 else 26 + index * 5))
                           for index in range(6)],
                "control": right_action,
            },
            "scroll": {
                "action": [frame(background_dx=index * 2) for index in range(6)],
                "control": no_movement,
            },
        }
        scene = {"status": "complete", "t0": baseline, "endpoint": baseline}
        runs["scene"] = scene
        composition = contract["predicates"]["composition"]
        composition["min_unique_colors"] = 2
        composition["min_observations"] = 2
        composition["references"] = []
        for claim, pair, box in (
                ("palette", "right", [0, 0, 16, 16]),
                ("layer", "left", [24, 0, 16, 16])):
            for index in (1, 2):
                capture = runs[pair]["action"][index]
                patch = qualification._scene_region_bytes(capture, box)
                composition["references"].append({
                    "pair": pair, "role": "action", "frame": index,
                    "box": box, "sha256": hashlib.sha256(patch).hexdigest(),
                    "claim": claim,
                })
        result = evaluate_active_scene_pairs(contract, runs)
        self.assertEqual(result["right"], "pass", result)
        self.assertEqual(result["left"], "pass", result)
        self.assertEqual(result["projectile"], "pass", result)
        self.assertEqual(result["release"], "pass", result)
        self.assertEqual(result["combined"], "pass", result)
        self.assertEqual(result["scroll"], "pass", result)
        self.assertEqual(result["composition"], "pass", result)
        self.assertEqual(result["overall"], "pass", result)

        # Frontend transfer has a different oracle owner: every actual role
        # needs its own bound replay receipt, while native composition retains
        # independently reviewed exact references. A shared renderer defect can
        # therefore agree with replay and still fail the native oracle.
        invocations = [{"pair": pair, "role": role} for pair in
                       ("right", "left", "fire", "combined", "scroll")
                       for role in ("action", "control")]
        changed_composition = copy.deepcopy(runs)
        changed_pixels = bytearray(changed_composition["right"]["action"][1])
        changed_pixels[(2 * 320 + 10) * 3] ^= 1
        changed_composition["right"]["action"][1] = bytes(changed_pixels)
        self.assertEqual(evaluate_active_scene_pairs(
            contract, changed_composition)["composition"], "fail")
        with mock.patch.object(qualification, "_active_frontend_transfer_valid", return_value=True):
            evaluated = qualification._evaluate_active_frontend_pairs(
                contract, changed_composition, invocations, {}, "configuration")
            self.assertEqual(evaluated["composition"], "pass")
            self.assertEqual(evaluated["overall"], "pass")
            for incomplete in (invocations[:-1], invocations[:-1] + invocations[:1], None):
                self.assertEqual(qualification._evaluate_active_frontend_pairs(
                    contract, runs, incomplete, {}, "configuration")["composition"], "fail")
            no_right = copy.deepcopy(runs)
            no_right["right"]["action"] = no_movement
            self.assertEqual(qualification._evaluate_active_frontend_pairs(
                contract, no_right, invocations, {}, "configuration")["overall"], "fail")
        with mock.patch.object(qualification, "_active_frontend_transfer_valid",
                               side_effect=[True] * 9 + [False]):
            self.assertEqual(qualification._evaluate_active_frontend_pairs(
                contract, runs, invocations, {}, "configuration")["composition"], "fail")

        # A frontend capture is an interval, so unrelated unobserved pixels may
        # differ at T0. Actor, HUD and scenery anchors must still match.
        self.assertEqual(evaluate_active_scene_pairs(
            contract, runs, frontend_intervals=True)["overall"], "pass")
        different_scene = copy.deepcopy(runs)
        different_scene["left"]["action"][0] = frame(actor_dx=8)
        self.assertEqual(evaluate_active_scene_pairs(
            contract, different_scene, frontend_intervals=True)["overall"], "fail")

        # Combined fire must satisfy its own component minimum, not only the
        # lower standalone projectile threshold.
        contract["predicates"]["combined"]["min_projectile_pixels"] = 4
        self.assertEqual(evaluate_active_scene_pairs(contract, runs)["combined"],
                         "fail")
        contract["predicates"]["combined"]["min_projectile_pixels"] = 3

        stationary_projectile = copy.deepcopy(runs)
        stationary_projectile["fire"]["action"][1] = frame(projectile_x=27)
        stationary_projectile["fire"]["action"][2] = frame(projectile_x=27)
        self.assertEqual(evaluate_active_scene_pairs(
            contract, stationary_projectile)["projectile"], "fail")

        matched_omitted_fire = copy.deepcopy(runs)
        matched_omitted_fire["fire"]["control"] = \
            matched_omitted_fire["fire"]["action"].copy()
        self.assertEqual(evaluate_active_scene_pairs(
            contract, matched_omitted_fire)["projectile"], "fail")

        playerless_projectile = copy.deepcopy(runs)
        playerless_projectile["fire"]["action"][1] = frame(
            actor_present=False, projectile_x=27)
        playerless_projectile["fire"]["action"][2] = frame(
            actor_present=False, projectile_x=35)
        self.assertEqual(evaluate_active_scene_pairs(
            contract, playerless_projectile)["projectile"], "fail")

        playerless_release = copy.deepcopy(runs)
        for index in (4, 5):
            playerless_release["fire"]["action"][index] = frame(
                actor_present=False, projectile_x=35)
        self.assertEqual(evaluate_active_scene_pairs(
            contract, playerless_release)["release"], "fail")

        too_close = copy.deepcopy(runs)
        contract["predicates"]["projectile"]["min_player_separation_px"] = 21
        self.assertEqual(evaluate_active_scene_pairs(contract, too_close)["projectile"],
                         "fail")
        contract["predicates"]["projectile"]["min_player_separation_px"] = 8

        projectile_after_release = copy.deepcopy(runs)
        projectile_after_release["fire"]["action"][4] = frame(projectile_x=35)
        self.assertEqual(evaluate_active_scene_pairs(
            contract, projectile_after_release)["release"], "fail")

        # The frozen palette/layer references are exact local evidence; changing
        # a referenced patch cannot be excused by retaining its color count.
        changed = copy.deepcopy(runs)
        changed_patch = bytearray(changed["right"]["action"][1])
        changed_patch[(2 * 320 + 10) * 3] ^= 1
        changed["right"]["action"][1] = bytes(changed_patch)
        self.assertEqual(evaluate_active_scene_pairs(contract, changed)["composition"],
                         "fail")

    def test_phase06_calibration_forwards_bounded_active_input_schedule(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        schedule = "0:0x2,60:0x0"
        argv = [
            "qualify_local_boot.py", "--active-scene", "calibrate",
            "--scene-contract", "local/qualification/phase06-contract.json",
            "--active-frame-inputs", schedule,
        ]
        with mock.patch("sys.argv", argv), \
             mock.patch.object(qualification, "calibrate_active_scene", return_value={
                 "status": "active_scene_calibration_recorded",
                 "calibration_outcome": "captures_ready",
             }) as calibrate, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(qualification.main(), 0)
        self.assertEqual(calibrate.call_args.kwargs, {"frame_inputs": schedule})

        for invalid in ("0:0x2,0:0x0", "3600:0x2", "0:0x400", "0:0x2x"):
            with self.subTest(schedule=invalid):
                rejected = qualification.calibrate_active_scene(
                    Path("missing-private-media"), None,
                    qualification.PHASE06_CONTRACT_PATH,
                    frame_inputs=invalid)
                self.assertEqual(rejected, {
                    "status": "active_scene_schedule_rejected",
                    "private_identity_recorded": False,
                })

    def test_phase06_evaluator_identity_tracks_acceptance_source_bytes(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        with tempfile.TemporaryDirectory(prefix="phase06-evaluator-identity-") as directory:
            source = Path(directory) / "qualifier.py"
            source.write_bytes(b"acceptance = 'first'\n")
            with mock.patch.object(qualification, "__file__", str(source)):
                first = qualification._production_evaluator_identity()
                source.write_bytes(b"acceptance = 'changed'\n")
                second = qualification._production_evaluator_identity()
            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            self.assertNotEqual(first["sha256"], second["sha256"])

    def test_phase06_calibration_binds_native_samples_and_configuration(self) -> None:
        import shutil
        from tools.mvs import qualify_local_boot as qualification

        Path("local/qualification").mkdir(parents=True, exist_ok=True)
        temporary_root = Path(tempfile.mkdtemp(
            prefix="phase06-calibration-contract-",
            dir="local/qualification")).relative_to(Path.cwd())
        run_root = temporary_root / "runs"
        contract_path = temporary_root / "contract.json"
        input_root = temporary_root / "input"
        input_root.mkdir()
        frame_inputs = "1:0x1,2:0x0"
        sampled_inputs = [{"frame": 1, "mask": 1},
                          {"frame": 2, "mask": 0}]
        include_samples = [True]
        media_sha256 = ["b" * 64]
        replace_media_during_run = [False]
        code_identity = {"path": "/tmp/fixture", "scope": "production",
                         "sha256": "a" * 64}
        qualifier_revision = ["before-refresh"]

        def qualifier_identity() -> dict[str, str]:
            return {"path": f"/tmp/qualifier-{qualifier_revision[0]}",
                    "scope": "production", "sha256": "c" * 64}

        def refresh_qualifier():
            qualifier_revision[0] = "after-refresh"
            return qualification.QualifierFreshness(
                "fresh", code_identity, qualifier_identity())

        def run_with_captures(*args, **kwargs):
            self.assertEqual(str(qualification.ensure_fresh_qualifier()), "fresh")
            capture_directory = kwargs["capture_directory"]
            for frame in kwargs["capture_frames"]:
                (capture_directory / f"frame-{frame:04d}.ppm").write_bytes(
                    b"P6\n320 224\n255\n" + bytes(320 * 224 * 3))
            native_report = {
                "status": "active_frames_completed",
                "guest_executed": True,
                "start_observed": True,
                "active_frames_requested": qualification.MAX_ACTIVE_FRAMES,
                "active_frames_completed": qualification.MAX_ACTIVE_FRAMES,
                "capture_frames_requested": list(kwargs["capture_frames"]),
                "capture_frames": list(kwargs["capture_frames"]),
            }
            if include_samples[0]:
                native_report["sampled_inputs"] = sampled_inputs
            if replace_media_during_run[0]:
                media_sha256[0] = "c" * 64
            result = {
                "status": "active_frames_completed",
                "active_frames_requested": qualification.MAX_ACTIVE_FRAMES,
                "active_frames_completed": qualification.MAX_ACTIVE_FRAMES,
                "capture_frames_requested": list(kwargs["capture_frames"]),
                "capture_frames": list(kwargs["capture_frames"]),
                "native_report_local": native_report,
            }
            return result

        try:
            with mock.patch.object(qualification, "PHASE06_RUN_ROOT", run_root), \
                 mock.patch.object(qualification, "PHASE06_CONTRACT_PATH",
                                   contract_path), \
                 mock.patch.object(qualification, "ignored", return_value=True), \
                 mock.patch.object(qualification,
                                   "private_active_capture_directory_is_safe",
                                   return_value=True), \
                 mock.patch.object(qualification,
                                   "private_active_capture_frame_is_valid",
                                   return_value=True), \
                 mock.patch.object(qualification, "find_pairs",
                                   return_value=[(Path("game.zip"), Path("bios.zip"))]), \
                 mock.patch.object(qualification, "_file_identity",
                                   side_effect=lambda path: {
                                       "path": f"/tmp/{path.name}", "size": 1,
                                       "sha256": media_sha256[0]}), \
                 mock.patch.object(qualification, "_production_importer_identity",
                                   return_value=code_identity), \
                 mock.patch.object(qualification, "_production_qualifier_identity",
                                   side_effect=qualifier_identity), \
                 mock.patch.object(qualification, "ensure_fresh_qualifier",
                                   side_effect=refresh_qualifier), \
                 mock.patch.object(qualification, "run_selected_qualification",
                                   side_effect=run_with_captures):
                custom_captures = [3000, 3120, 3240, 3360, 3480, 3599]
                result = qualification.calibrate_active_scene(
                    input_root, None, contract_path, frame_inputs=frame_inputs,
                    capture_frames=custom_captures)
                self.assertEqual(result["status"], "active_scene_calibration_recorded")
                self.assertEqual(result["calibration_outcome"], "captures_ready")
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                self.assertEqual(contract["schedule"]["capture_frames"], custom_captures)
                self.assertEqual([item["frame"] for item in contract["checkpoints"]],
                                 custom_captures)
                report_path = Path("local/qualification") / contract["run_report"]
                report = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual(report["evaluator_identity"],
                                 contract["evaluator_identity"])
                self.assertEqual(contract["sampled_inputs"], sampled_inputs)
                self.assertEqual(
                    contract["observations"]["calibration_configuration_identity"],
                    report["configuration_identity"])
                self.assertTrue(qualification.active_scene_calibration_evidence_is_valid(
                    contract, report))
                stale_evaluator_report = {
                    **report,
                    "evaluator_identity": {
                        **report["evaluator_identity"], "sha256": "0" * 64,
                    },
                }
                self.assertFalse(qualification.active_scene_calibration_evidence_is_valid(
                    contract, stale_evaluator_report))
                include_samples[0] = False
                missing_samples = qualification.calibrate_active_scene(
                    input_root, None, contract_path, frame_inputs=frame_inputs)
                self.assertEqual(missing_samples["calibration_outcome"], "incomplete")
                include_samples[0] = True
                replace_media_during_run[0] = True
                replaced_media = qualification.calibrate_active_scene(
                    input_root, None, contract_path, frame_inputs=frame_inputs)
                self.assertEqual(replaced_media["calibration_outcome"], "incomplete")
        finally:
            contract_path.unlink(missing_ok=True)
            shutil.rmtree(temporary_root, ignore_errors=True)

    def test_attract_checkpoint_without_frame_does_not_require_supported_zoom(self) -> None:
        game, bios = make_split_archives(
            attract_guest=True, unsupported_zoom_guest=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        with tempfile.TemporaryDirectory(prefix="mvs-no-frame-zoom-") as directory:
            root = Path(directory)
            game_path = root / "game.zip"
            bios_path = root / "bios.zip"
            bundle_path = root / "selected.gnmv"
            game_path.write_bytes(game)
            bios_path.write_bytes(bios)
            imported = subprocess.run(
                [self.importer, "--selected", str(game_path), str(bios_path),
                 str(bundle_path)], capture_output=True, text=True, check=False)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            runner = str(Path(self.production_importer).resolve().parent /
                         "mvs_qualify")

            no_frame = subprocess.run(
                [runner, str(bundle_path)], capture_output=True, text=True,
                check=False)
            self.assertEqual(no_frame.returncode, 0, no_frame.stdout)
            no_frame_report = json.loads(no_frame.stdout)
            self.assertEqual(no_frame_report["status"], "attract_start")
            self.assertTrue(no_frame_report["guest_executed"])
            self.assertNotIn("frame_output_written", no_frame_report)

            frame_root = root / "frame-root"
            frame_directory = frame_root / "local" / "qualification"
            frame_directory.mkdir(parents=True)
            frame_name = "local/qualification/phase05-" + "d" * 32 + ".ppm"
            with_frame = subprocess.run(
                [runner, str(bundle_path), "--frame-output", frame_name,
                 "--video-state-diagnostic"],
                cwd=frame_root, capture_output=True, text=True, check=False)
            self.assertEqual(with_frame.returncode, 1, with_frame.stdout)
            self.assertEqual(json.loads(with_frame.stdout)["status"],
                             "native_video_unavailable")
            activity = json.loads(with_frame.stderr)["private_video_activity"]
            self.assertGreater(activity["nonzero_vram_words"], 0)
            self.assertGreater(activity["sprite_words"], 0)
            self.assertGreater(activity["visible_nonfull_y_zoom_samples"], 0)
            self.assertFalse((frame_directory / Path(frame_name).name).exists())

    def test_scripted_start_preserves_native_fault_diagnostics(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        game, bios = make_split_archives(
            attract_guest=True, attract_loop=True, unsupported_player_start=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        with tempfile.TemporaryDirectory(prefix="mvs-scripted-fault-") as directory:
            root = Path(directory)
            game_path = root / "game.zip"
            bios_path = root / "bios.zip"
            output_path = root / "selected.gnmv"
            game_path.write_bytes(game)
            bios_path.write_bytes(bios)
            imported = subprocess.run(
                [self.importer, "--selected", str(game_path), str(bios_path),
                 str(output_path)],
                capture_output=True, text=True, check=False)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            runner = str(Path(self.production_importer).resolve().parent / "mvs_qualify")
            execution = subprocess.run(
                [runner, str(output_path), "--input-script", "coin@1,start@2"],
                capture_output=True, text=True, check=False)

            frame_root = root / "frame-root"
            frame_directory = frame_root / "local" / "qualification"
            frame_directory.mkdir(parents=True)
            frame_name = "local/qualification/phase05-" + "f" * 32 + ".ppm"
            with_frame = subprocess.run(
                [runner, str(output_path), "--input-script", "coin@1,start@2",
                 "--frame-output", frame_name], cwd=frame_root,
                capture_output=True, text=True, check=False)
            saved_frame = frame_directory / Path(frame_name).name
            self.assertEqual(with_frame.returncode, 0, with_frame.stdout)
            frame_report = json.loads(with_frame.stdout)
            self.assertEqual(frame_report["status"], "unsupported_guest_event")
            self.assertIs(frame_report["frame_output_written"], True)
            self.assertTrue(qualification.private_frame_is_valid(saved_frame))

            failed_path = frame_directory / ("phase05-" + "e" * 32 + ".ppm")
            failed_path.write_bytes(b"already exists")
            failed_output = subprocess.run(
                [runner, str(output_path), "--input-script", "coin@1,start@2",
                 "--frame-output", failed_path.relative_to(frame_root).as_posix()],
                cwd=frame_root, capture_output=True, text=True, check=False)

        self.assertEqual(execution.returncode, 0, execution.stdout)
        native = json.loads(execution.stdout)
        self.assertEqual(native["status"], "unsupported_guest_event")
        self.assertIs(native["guest_executed"], True)
        self.assertEqual(native["native_failure"]["component"], "main_cpu")
        self.assertEqual(native["native_failure"]["stage"], "execute")
        self.assertEqual(native["native_failure"]["underlying_status"],
                         "owned_cpu_unsupported_opcode")
        safe = safe_result(native)
        self.assertEqual(safe["status"], "unsupported_guest_event")
        self.assertIs(safe["guest_executed"], True)
        self.assertEqual(safe["native_failure"]["completed_main_instructions"],
                         native["native_failure"]["completed_main_instructions"])

        self.assertEqual(failed_output.returncode, 1, failed_output.stdout)
        self.assertEqual(json.loads(failed_output.stdout),
                         {"status": "native_video_unavailable"})

    def test_requested_fault_boundary_frame_failure_is_not_swallowed(self) -> None:
        from tools.mvs import qualify_local_boot as qualification
        game, bios = make_split_archives(
            attract_guest=True, attract_loop=True, attract_timeout=True,
            unsupported_player_start=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        with tempfile.TemporaryDirectory(prefix="mvs-frame-fault-test-") as directory:
            game_path = Path(directory) / "game.zip"
            bios_path = Path(directory) / "bios.zip"
            bundle_path = Path(directory) / "selected.gnmv"
            game_path.write_bytes(game)
            bios_path.write_bytes(bios)
            imported = subprocess.run(
                [self.importer, "--selected", str(game_path), str(bios_path),
                 str(bundle_path)], capture_output=True, text=True, check=False)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            runner = str(Path(self.production_importer).resolve().parent / "mvs_qualify")
            frame_root = Path(directory) / "frame-root"
            output_directory = frame_root / "local" / "qualification"
            output_directory.mkdir(parents=True)
            frame_name = "local/qualification/phase05-" + "c" * 32 + ".ppm"

            saved_frame = subprocess.run(
                [runner, str(bundle_path), "--video-advance-frames", "2",
                 "--frame-output", frame_name], cwd=frame_root,
                capture_output=True, text=True, check=False)
            saved_report = json.loads(saved_frame.stdout)
            self.assertEqual(saved_frame.returncode, 0, saved_frame.stdout)
            self.assertEqual(saved_report["status"], "unsupported_guest_event")
            self.assertIs(saved_report["frame_output_written"], True)
            self.assertTrue(qualification.private_frame_is_valid(output_directory /
                                                                  Path(frame_name).name))

            failed_path = output_directory / ("phase05-" + "d" * 32 + ".ppm")
            failed_path.write_bytes(b"already exists")
            failed_output = subprocess.run(
                [runner, str(bundle_path), "--video-advance-frames", "2",
                 "--frame-output", failed_path.relative_to(frame_root).as_posix()],
                cwd=frame_root, capture_output=True, text=True, check=False)

        self.assertEqual(failed_output.returncode, 1, failed_output.stdout)
        self.assertEqual(json.loads(failed_output.stdout),
                         {"status": "native_video_unavailable"})

    def test_attract_start_accepts_only_the_exact_checkpoint_shape(self) -> None:
        good = {"user_request": "title", "chunk": 256, "user_mode_corroborated": False}
        safe = safe_result({"status": "attract_start", "guest_executed": True,
                            "checkpoint": dict(good), "private_identity_recorded": True,
                            "archive_path": "synthetic-private-path"})
        self.assertEqual(safe["status"], "attract_start")
        self.assertIs(safe["guest_executed"], True)
        self.assertEqual(safe["checkpoint"], good)
        for token in ("observed", "not_observed"):
            scripted = safe_result({"status": "attract_start", "guest_executed": True,
                                    "checkpoint": dict(good), "input_response": token})
            self.assertEqual(scripted["input_response"], token)
        for token in ("yes", "PLAYER_START", 1, None):
            spoof = safe_result({"status": "attract_start", "guest_executed": True,
                                 "checkpoint": dict(good), "input_response": token})
            self.assertEqual(spoof["status"], "native_qualification_failed")
        spoof = safe_result({"status": "guest_stopped", "guest_executed": True,
                             "input_response": "observed"})
        self.assertEqual(spoof["status"], "native_qualification_failed")
        self.assertIs(safe["private_identity_recorded"], False)
        self.assertNotIn("archive_path", safe)

    def test_video_advance_report_separates_requested_and_completed_frames(self) -> None:
        checkpoint = {"user_request": "demo", "chunk": 1,
                      "user_mode_corroborated": True}
        good = safe_result({
            "status": "attract_start", "guest_executed": True,
            "checkpoint": checkpoint, "frame_output_written": True,
            "video_advance_frames": 360, "video_advance_requested": 360,
            "video_advance_completed": 360,
        })
        self.assertEqual(good["status"], "attract_start")
        self.assertEqual(good["video_advance_frames"], 360)
        self.assertEqual(good["video_advance_completed"], 360)

        faulted = safe_result({
            "status": "unsupported_guest_event", "guest_executed": True,
            "frame_output_written": True,
            "video_advance_frames": 360, "video_advance_requested": 360,
            "video_advance_completed": 17,
        })
        self.assertEqual(faulted["status"], "unsupported_guest_event")
        self.assertEqual(faulted["video_advance_completed"], 17)

        for malformed in (
            {"video_advance_frames": 601, "video_advance_completed": 601},
            {"video_advance_frames": 60, "video_advance_completed": 61},
            {"video_advance_frames": 60, "video_advance_completed": True},
            {"video_advance_completed": 1},
            {"video_advance_requested": 60},
        ):
            report = {
                "status": "attract_start", "guest_executed": True,
                "checkpoint": checkpoint, "frame_output_written": True,
                **malformed,
            }
            self.assertEqual(safe_result(report)["status"],
                             "native_qualification_failed")

        for status in ("unsupported_guest_event", "guest_stopped"):
            report = {
                "status": status, "guest_executed": True,
                "frame_output_written": True,
                "video_advance_requested": 60,
                "video_advance_completed": 60,
            }
            self.assertEqual(safe_result(report)["status"],
                             "native_qualification_failed")

        stopped = safe_result({
            "status": "guest_stopped", "guest_executed": True,
            "frame_output_written": True,
            "video_advance_frames": 360, "video_advance_completed": 12,
        })
        self.assertEqual(stopped["status"], "guest_stopped")
        self.assertEqual(stopped["video_advance_completed"], 12)
        spoofs = {
            "extra key": {**good, "pc": 256},
            "missing key": {"user_request": "demo", "chunk": 1},
            "guest not executed": None,
            "boot request": {**good, "user_request": "boot"},
            "chunk zero": {**good, "chunk": 0},
            "chunk 257": {**good, "chunk": 257},
            "chunk bool": {**good, "chunk": True},
            "chunk string": {**good, "chunk": "1"},
            "corroborated int": {**good, "user_mode_corroborated": 1},
            "not a dict": "private guest signal",
        }
        for label, checkpoint in spoofs.items():
            with self.subTest(label):
                report = {"status": "attract_start", "guest_executed": True,
                          "checkpoint": checkpoint}
                if label == "guest not executed":
                    report = {"status": "attract_start", "guest_executed": False,
                              "checkpoint": dict(good)}
                result = safe_result(report)
                self.assertEqual(result["status"], "native_qualification_failed")
                self.assertIsNot(result.get("guest_executed"), True)
                self.assertNotIn("checkpoint", result)

    def test_missing_audio_region_is_a_safe_stop_without_guest_execution(self) -> None:
        self.assertEqual(safe_result({"status": "missing_audio_region"}), {
            "status": "missing_audio_region",
            "retroarch_observation": "manual-only-unknown",
            "private_identity_recorded": False,
        })
        spoofed = safe_result({"status": "missing_audio_region",
                               "guest_executed": True})
        self.assertEqual(spoofed["status"], "native_qualification_failed")
        self.assertNotIn("guest_executed", spoofed)

    def test_budget_exhaustion_reports_a_sanitized_diagnosis_from_the_real_qualifier(self) -> None:
        game, bios = make_split_archives(
            spin_guest=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        with tempfile.TemporaryDirectory(prefix="mvs-spin-test-") as directory:
            game_path = os.path.join(directory, "game.zip")
            bios_path = os.path.join(directory, "bios.zip")
            output_path = os.path.join(directory, "selected.gnmv")
            with open(game_path, "wb") as handle:
                handle.write(game)
            with open(bios_path, "wb") as handle:
                handle.write(bios)
            checked = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            runner = str(Path(self.production_importer).resolve().parent / "mvs_qualify")
            execution = subprocess.run([runner, output_path], capture_output=True,
                                       text=True, check=False)
        self.assertEqual(execution.returncode, 0, execution.stdout)
        native = json.loads(execution.stdout)
        self.assertEqual(native["status"], "guest_instruction_budget_exhausted")
        self.assertEqual(native["profile"]["chunks"], 256)
        safe = safe_result(native)["diagnosis"]
        self.assertEqual(safe["interrupts_taken"], 0)
        self.assertEqual(safe["polled_registers"][0]["address"], "0x3c0000")
        self.assertEqual(len(safe["polled_registers"]), 1)
        self.assertGreater(safe["polled_registers"][0]["reads"], 1000)
        self.assertEqual(safe["sr_mask_histogram"][:7], [0] * 7)
        self.assertGreater(safe["sr_mask_histogram"][7], 1000)
        self.assertEqual(safe["pc_region_histogram"][1:], [0] * 4)
        self.assertEqual(safe["attract_rejection"], "NO_REQUEST")
        self.assertEqual(safe["bios_variables"],
                         {"system_mode": 0, "user_request": 0, "user_mode": 0})

    def test_diagnosis_keeps_only_the_whitelisted_public_shape(self) -> None:
        diagnosis = {
            "interrupts_taken": 0, "irq_ack_writes": 3,
            "sr_mask_histogram": [0, 0, 0, 0, 0, 0, 0, 900],
            "pc_region_histogram": [900, 0, 0, 0, 0],
            "low_program_window_reads": 12, "unmapped_read_count": 0,
            "polled_registers": [
                {"address": "0x3c0006", "reads": 400},
                {"address": "0x320000", "reads": 300},
                {"address": "0x10fdae", "reads": 200},      # BIOS RAM: outside both windows
                {"address": "0x400000", "reads": 100},      # palette RAM: outside both windows
                {"address": "0x2fffdf", "reads": 90},       # just below the 0x2fffe0 window
                {"address": "0x00100", "reads": 80},        # cartridge program, private-adjacent
                {"address": "0x3c0008", "reads": 70, "pc": 4660},  # extra key
                {"address": 3932160, "reads": 60},          # wrong type
                {"address": "0x2fffe1", "reads": True},     # bool is not a count
            ],
            "polled_untracked_reads": 0,
            "bios_variables": {"system_mode": 0, "user_request": 2, "user_mode": 0,
                               "rom_word": 4660},
            "attract_rejection": "NONE",
            "recent_pc": 4660,                               # unknown key
        }
        safe = safe_result({
            "status": "guest_instruction_budget_exhausted", "guest_executed": True,
            "diagnosis": diagnosis})
        self.assertEqual(safe["diagnosis"], {
            "interrupts_taken": 0, "irq_ack_writes": 3,
            "sr_mask_histogram": [0, 0, 0, 0, 0, 0, 0, 900],
            "pc_region_histogram": [900, 0, 0, 0, 0],
            "low_program_window_reads": 12, "unmapped_read_count": 0,
            "polled_registers": [{"address": "0x3c0006", "reads": 400},
                                 {"address": "0x320000", "reads": 300}],
            "polled_untracked_reads": 0,
            "bios_variables": {"system_mode": 0, "user_request": 2, "user_mode": 0},
            "attract_rejection": "NONE",
        })
        many = dict(diagnosis, polled_registers=[
            {"address": f"0x{0x300000 + 2 * index:x}", "reads": 100 - index}
            for index in range(12)])
        rows = safe_result({"status": "guest_instruction_budget_exhausted",
                            "guest_executed": True,
                            "diagnosis": many})["diagnosis"]["polled_registers"]
        self.assertEqual(len(rows), 8)
        for label, broken in {
            "short histogram": {"sr_mask_histogram": [1] * 7},
            "long pc histogram": {"pc_region_histogram": [1] * 6},
            "negative count": {"irq_ack_writes": -1},
            "bool count": {"interrupts_taken": True},
            "unknown rejection": {"attract_rejection": "private word"},
            "bad variable": {"bios_variables": {"system_mode": 256, "user_request": 0,
                                                "user_mode": 0}},
        }.items():
            with self.subTest(label):
                result = safe_result({"status": "guest_instruction_budget_exhausted",
                                      "guest_executed": True,
                                      "diagnosis": dict(diagnosis, **broken)})
                self.assertNotIn(next(iter(broken)), result.get("diagnosis", {}))
        self.assertNotIn("diagnosis", safe_result({
            "status": "guest_instruction_budget_exhausted", "guest_executed": True,
            "diagnosis": "private guest signal"}))

    def test_sound_io_bus_failure_reports_coarse_native_diagnosis(self) -> None:
        audio_bios = bytearray(AUDIO_BIOS_SIZE)
        audio_bios[:5] = bytes((0x3e, 0x5a, 0xd3, 0x02, 0x76))
        source = make_archive(audio_bios=bytes(audio_bios))
        synthetic_importer, owner = test_identity_importer(self.production_importer)
        try:
            with tempfile.TemporaryDirectory(prefix="mvs-failure-test-") as directory:
                input_path = os.path.join(directory, "synthetic.zip")
                output_path = os.path.join(directory, "selected.gnmv")
                with open(input_path, "wb") as handle:
                    handle.write(source)
                imported = subprocess.run(
                    [synthetic_importer, input_path, output_path],
                    capture_output=True, text=True, check=False)
                self.assertEqual(imported.returncode, 0, imported.stderr)
                if getattr(self, "failure_driver", None) is None:
                    runner = str(Path(self.production_importer).resolve().parent / "mvs_qualify")
                    command = [runner, output_path]
                else:
                    command = [self.failure_driver, output_path, "sound_bus_failure"]
                execution = subprocess.run(command, capture_output=True, text=True,
                                           check=False)
        finally:
            owner.cleanup()
        self.assertEqual(execution.returncode, 1, execution.stdout)
        native = json.loads(execution.stdout)
        self.assertEqual(native["status"], "native_execution_error")
        safe = safe_result(native)
        failure = safe.get("native_failure", {})
        self.assertEqual((failure.get("component"), failure.get("stage"),
                          failure.get("reason"), failure.get("site")),
                         ("sound_cpu", "bus_access", "bus_failure",
                          "sound_io_write"))
        self.assertEqual((failure.get("underlying_status"), failure.get("operation"),
                          failure.get("address"), failure.get("width")),
                         ("z80_bus_failure", "write", 0x5A02, 1))

    def run_failure_diagnostic_case(
        self, case: str, *, main_bios_program: bytes | None = None,
        audio_bios: bytes | None = None,
        main_bios_reset: bool = False,
        driver_extra: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        if getattr(self, "failure_driver", None) is None:
            self.skipTest("failure driver is supplied by the configured CTest target")
        audio_program = bytearray(AUDIO_BIOS_SIZE)
        audio_program[:5] = bytes((0x3e, 0x5a, 0xd3, 0x02, 0x76))
        source = make_archive(audio_bios=(bytes(audio_program) if audio_bios is None
                                         else audio_bios),
                              main_bios_program=main_bios_program,
                              main_bios_reset=main_bios_reset)
        with tempfile.TemporaryDirectory(prefix="mvs-failure-driver-") as directory:
            input_path = os.path.join(directory, "synthetic.zip")
            output_path = os.path.join(directory, "selected.gnmv")
            with open(input_path, "wb") as handle:
                handle.write(source)
            imported = subprocess.run(
                [self.importer, input_path, output_path],
                capture_output=True, text=True, check=False)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            command = [self.failure_driver, output_path, case]
            if driver_extra or case.startswith("active_"):
                capture_dir = Path(directory) / "local/qualification/phase06" / ("run-" + "a" * 32)
                capture_dir.mkdir(parents=True)
                command.append(capture_dir.relative_to(directory).as_posix())
            execution = subprocess.run(command, cwd=directory,
                                       capture_output=True, text=True, check=False)
        try:
            report = ({} if driver_extra and not execution.stdout
                      else json.loads(execution.stdout))
        except json.JSONDecodeError as error:
            self.fail(f"failure driver emitted invalid JSON: {error}")
        return execution, report

    def test_active_failures_retain_requested_and_completed_progress(self) -> None:
        for invalid_case in ("active_typo", "main_failure_before_instruction"):
            with self.subTest(invalid_case=invalid_case):
                execution, _native = self.run_failure_diagnostic_case(
                    invalid_case, driver_extra=True)
                self.assertEqual(execution.returncode, 2, execution.stdout)
                self.assertEqual(execution.stdout, "")
        cases = (
            ("active_prelude_error", None, False, 0, [], "native_execution_error", 1),
            ("active_scripted_error", None, False, 0, [], "native_execution_error", 1),
            ("active_immediate_error", None, True, 0, [], "native_execution_error", 1),
            ("active_scripted_fault", bytes.fromhex("ffff"), False, 0, [],
             "unsupported_guest_event", 0),
            # Poll P1 until RIGHT is held at frame 1, then provoke a real
            # unmapped read through gn_run_mvs after frame 0 was captured.
            ("active_partial_bus_error", bytes.fromhex(
                "1039003000000c0000f766f4303900900000"), True, 1, [0],
             "unsupported_guest_event", 1),
        )
        for case, program, started, completed, captures, status, exit_code in cases:
            with self.subTest(case=case):
                execution, native = self.run_failure_diagnostic_case(
                    case, main_bios_program=program,
                    audio_bios=bytes(AUDIO_BIOS_SIZE), main_bios_reset=True)
                self.assertEqual(execution.returncode, exit_code, execution.stdout)
                self.assertEqual(native.get("status"), status)
                self.assertIs(native.get("start_observed"), started)
                self.assertEqual(native.get("active_frames_requested"), 3)
                self.assertEqual(native.get("active_frames_completed"), completed)
                self.assertEqual(native.get("capture_frames_requested"), [0, 1])
                self.assertEqual(native.get("capture_frames"), captures)
                self.assertEqual(native["native_failure"]["component"], "main_cpu")
                if case.endswith("error") and "partial" not in case:
                    self.assertEqual(native["native_failure"]["site"], "main_observe")
                if "partial" in case:
                    self.assertEqual(native["native_failure"]["address"], 0x900000)
                safe = safe_result(native)
                self.assertEqual(safe["status"], status)
                self.assertEqual(safe.get("active_frames_requested"), 3)
                self.assertEqual(safe.get("active_frames_completed"), completed)
                self.assertEqual(safe.get("capture_frames_requested"), [0, 1])
                self.assertEqual(safe.get("capture_frames"), captures)
                for changes in (
                    {"start_observed": 0},
                    {"start_observed": None},
                    {"guest_executed": 1},
                    {"active_frames_completed": 3},
                    {"active_frames_completed": True},
                    {"active_frames_completed": -1},
                    {"capture_frames": [1]},
                    {"capture_frames": [0, 0]},
                    {"start_observed": False, "active_frames_completed": 1},
                    {"guest_executed": False, "active_frames_completed": 1},
                ):
                    with self.subTest(malformed=changes):
                        self.assertEqual(safe_result({**native, **changes})["status"],
                                         "native_qualification_failed")

    def assert_native_failure(self, case: str, expected: dict[str, str],
                              guest_executed: bool) -> None:
        execution, native = self.run_failure_diagnostic_case(case)
        self.assertEqual(execution.returncode, 1, execution.stdout)
        safe = safe_result(native)
        self.assertEqual(safe["status"], "native_execution_error")
        self.assertIs(safe["guest_executed"], guest_executed)
        self.assertTrue(set(expected).issubset(safe["native_failure"]))
        self.assertEqual(set(safe["native_failure"]), NATIVE_FAILURE_KEYS)
        for name, value in expected.items():
            self.assertEqual(safe["native_failure"][name], value)
        self.assertEqual(set(safe), {"status", "retroarch_observation",
                                     "private_identity_recorded", "guest_executed",
                                     "native_failure"})

    def test_failure_driver_main_failure_before_instruction(self) -> None:
        self.assert_native_failure("main_failure_before_instruction", {
            "component": "main_cpu", "stage": "observe",
            "reason": "internal_failure"}, False)

    def test_failure_driver_main_failure_after_instruction(self) -> None:
        self.assert_native_failure("main_failure_after_instruction", {
            "component": "main_cpu", "stage": "execute",
            "reason": "internal_failure"}, True)

    def test_failure_diagnostic_marks_executed_zero_opcode_valid(self) -> None:
        execution, native = self.run_failure_diagnostic_case(
            "main_failure_after_instruction",
            main_bios_program=bytes.fromhex("000000014e722700"),
        )
        self.assertEqual(execution.returncode, 1, execution.stdout)
        failure = safe_result(native).get("native_failure", {})
        self.assertEqual(failure.get("completed_main_instructions"), 1)
        self.assertEqual(failure.get("opcode"), 0)
        self.assertIs(failure.get("opcode_valid"), True)

    def test_failure_driver_first_instruction_fault_keeps_zero_execution_count(self) -> None:
        execution, native = self.run_failure_diagnostic_case(
            "unsupported_first_instruction",
            main_bios_program=bytes.fromhex("ffff"),
            audio_bios=bytes(AUDIO_BIOS_SIZE), main_bios_reset=True)
        self.assertEqual(execution.returncode, 0, execution.stdout)
        safe = safe_result(native)
        self.assertEqual(safe["status"], "unsupported_guest_event")
        self.assertIs(safe["guest_executed"], False)
        failure = safe["native_failure"]
        self.assertEqual(failure["completed_main_instructions"], 0)

    def test_failure_driver_classifies_main_bus_faults_as_guest_events(self) -> None:
        cases = (
            ("main_bus_read_first_instruction",
             bytes.fromhex("4e71303900900000"), "read", 2),
            ("main_bus_write_after_instruction",
             bytes.fromhex("725a33c100900000"), "write", 2),
        )
        for case, program, operation, width in cases:
            with self.subTest(operation=operation):
                execution, native = self.run_failure_diagnostic_case(
                    case, main_bios_program=program,
                    audio_bios=bytes(AUDIO_BIOS_SIZE), main_bios_reset=True)
                self.assertEqual(execution.returncode, 1, execution.stdout)
                safe = safe_result(native)
                self.assertEqual(safe["status"], "unsupported_guest_event")
                self.assertIs(safe["guest_executed"], True)
                failure = safe["native_failure"]
                self.assertEqual((failure["component"], failure["stage"],
                                  failure["reason"], failure["operation"],
                                  failure["address"], failure["width"]),
                                 ("main_cpu", "bus_access", "bus_failure",
                                  operation, 0x900000, width))

    def test_failure_driver_sound_tick_limit(self) -> None:
        self.assert_native_failure("sound_tick_limit", {
            "component": "sound_cpu", "stage": "sound_catchup",
            "reason": "cycle_limit"}, False)

    def test_failure_driver_sound_before_main_progress(self) -> None:
        self.assert_native_failure("sound_before_main_progress", {
            "component": "sound_cpu", "stage": "bus_access",
            "reason": "bus_failure"}, False)

    def test_failure_driver_reports_typed_main_and_sound_detail(self) -> None:
        detail_keys = {
            "component", "stage", "reason", "site", "site_valid",
            "device_cause", "device_cause_valid", "underlying_status",
            "underlying_status_valid", "emulated_cycle",
            "emulated_cycle_valid", "completed_main_instructions",
            "instruction_boundary_valid", "pc", "pc_valid", "opcode",
            "opcode_valid", "operation", "address", "width",
            "bus_access_valid",
        }
        cases = (
            ("main_failure_after_instruction", "main_cpu", "main_execution"),
            ("sound_bus_failure", "sound_cpu", "sound_io_write"),
        )
        for case, component, site in cases:
            with self.subTest(case=case):
                execution, native = self.run_failure_diagnostic_case(case)
                self.assertEqual(execution.returncode, 1, execution.stdout)
                safe = safe_result(native)
                self.assertEqual(safe["status"], "native_execution_error")
                failure = safe.get("native_failure", {})
                self.assertEqual(set(failure), detail_keys)
                self.assertEqual(failure.get("component"), component)
                self.assertEqual(failure.get("site"), site)
                self.assertIs(failure.get("site_valid"), True)
                self.assertEqual(failure.get("underlying_status"),
                                 "z80_bus_failure" if component == "sound_cpu"
                                 else "unknown")
                self.assertEqual(failure.get("underlying_status_valid"),
                                 component == "sound_cpu")
                self.assertIs(type(failure.get("emulated_cycle")), int)
                self.assertIs(type(failure.get("completed_main_instructions")), int)
                self.assertIs(type(failure.get("pc_valid")), bool)
                self.assertIs(type(failure.get("opcode_valid")), bool)
                self.assertIs(type(failure.get("bus_access_valid")), bool)
        sound_failure = safe_result(
            self.run_failure_diagnostic_case("sound_bus_failure")[1]
        ).get("native_failure", {})
        self.assertEqual(sound_failure.get("device_cause"), "sound_bus_callback")
        self.assertIs(sound_failure.get("device_cause_valid"), True)
        self.assertEqual((sound_failure.get("operation"),
                          sound_failure.get("address"),
                          sound_failure.get("width")), ("write", 0x5A02, 1))

    def test_failure_driver_first_error_precedence(self) -> None:
        expected_records = (
            ("first_error_precedence", {
                "component": "sound_cpu", "stage": "bus_access",
                "reason": "bus_failure", "site": "sound_io_write",
                "device_cause": "sound_bus_callback",
                "underlying_status": "z80_bus_failure", "emulated_cycle": 0,
                "completed_main_instructions": 0, "instruction_boundary_valid": True,
                "operation": "write", "address": 0x5A02, "width": 1,
                "bus_access_valid": True,
            }, False),
            ("main_first_precedence", {
                "component": "main_cpu", "stage": "execute",
                "reason": "internal_failure", "site": "main_execution",
                "device_cause": "owned_cpu", "underlying_status": "unknown",
                "emulated_cycle": 48, "completed_main_instructions": 1,
                "instruction_boundary_valid": True, "pc": 0x100,
                "opcode": 0, "opcode_valid": True, "bus_access_valid": False,
            }, True),
        )
        for case, expected, guest_executed in expected_records:
            with self.subTest(case=case):
                execution, native = self.run_failure_diagnostic_case(case)
                self.assertEqual(execution.returncode, 1, execution.stdout)
                safe = safe_result(native)
                self.assertEqual(safe["status"], "native_execution_error")
                self.assertIs(safe["guest_executed"], guest_executed)
                failure = safe["native_failure"]
                self.assertEqual(set(failure), NATIVE_FAILURE_KEYS)
                for name, value in expected.items():
                    self.assertEqual(failure[name], value)

    def test_failure_driver_diagnostic_reset_isolation(self) -> None:
        execution, report = self.run_failure_diagnostic_case(
            "diagnostic_reset_isolation")
        self.assertEqual(execution.returncode, 0, execution.stdout)
        self.assertEqual(report, {
            "status": "diagnostic_reset_isolation_pass",
            "coverage": {"unloaded_observation": True,
                         "reset_then_distinct_failure": True,
                         "unload_reload_clears_detail": True,
                         "interleaved_instances": True},
        })

    def test_native_failure_schema_rejects_empty_extra_and_invalid_tokens(self) -> None:
        class StringSubclass(str):
            pass

        expected = {
            "component": "sound_cpu", "stage": "bus_access",
            "reason": "bus_failure", "site": "sound_io_write",
            "site_valid": True, "device_cause": "sound_bus_callback",
            "device_cause_valid": True, "underlying_status": "z80_bus_failure",
            "underlying_status_valid": True, "emulated_cycle": 128,
            "emulated_cycle_valid": True, "completed_main_instructions": 0,
            "instruction_boundary_valid": True, "pc": 0, "pc_valid": False,
            "opcode": 0, "opcode_valid": False, "operation": "write",
            "address": 2, "width": 1, "bus_access_valid": True,
        }
        safe = safe_result({"status": "native_execution_error",
                            "guest_executed": False,
                            "native_failure": expected})
        self.assertEqual(safe["native_failure"], expected)
        self.assertIs(safe["guest_executed"], False)
        main_bus_failure = {
            "component": "main_cpu", "stage": "bus_access",
            "reason": "bus_failure", "site": "main_bus_read",
            "site_valid": True, "device_cause": "main_bus_callback",
            "device_cause_valid": True, "underlying_status": "unknown",
            "underlying_status_valid": False, "emulated_cycle": 256,
            "emulated_cycle_valid": True, "completed_main_instructions": 1,
            "instruction_boundary_valid": True, "pc": 0x1234,
            "pc_valid": True, "opcode": 0x4050, "opcode_valid": True,
            "operation": "read", "address": 0x300000, "width": 2,
            "bus_access_valid": True,
        }
        guest_fault = {"status": "unsupported_guest_event", "guest_executed": True,
                       "native_failure": main_bus_failure}
        safe_fault = safe_result(guest_fault)
        self.assertEqual(safe_fault["native_failure"], main_bus_failure)
        public_fault = public_result(guest_fault)
        self.assertEqual(public_fault["native_failure"], {
            "component": "main_cpu", "stage": "bus_access",
            "reason": "bus_failure", "site": "main_bus_read"})
        self.assertNotIn("address", json.dumps(public_fault))
        mismatch_fault = safe_result({**guest_fault, "guest_executed": False})
        self.assertEqual(mismatch_fault["status"], "native_qualification_failed")
        malformed = (
            {}, {**expected, "pc": 0x1234},
            {"component": "sound_cpu", "stage": "bus_access",
             "reason": "bus_failure", "private_identity": "secret"},
            {**expected, "site": "sound_io_write "},
            {**expected, "device_cause": "bυs_callback"},
            {**expected, "underlying_status": b"z80_bus_failure"},
            {**expected, "component": "main_cpu"},
            {**expected, "site_valid": 1},
            {**expected, "address": True},
            {**expected, "width": 256},
            {**expected, "emulated_cycle": -1},
            {**expected, "opcode": 0x10000},
            {**expected, "bus_access_valid": False},
            {**expected, "site": "main_bus_read", "site_valid": False},
            {**expected, "site": "/private/media/secret.rom"},
            {**expected, "device_cause": "game hash 0123456789abcdef"},
            {**expected, "site": StringSubclass("sound_io_write")},
            {**expected, "completed_main_instructions": 0x10000000000000000},
            {**expected, "operation": "read"},
            {**expected, "device_cause": "z80_tick"},
            {**expected, "underlying_status": "z80_cycle_limit"},
            {**expected, "component": "main_cpu", "stage": "observe",
             "reason": "internal_failure", "site": "main_execution",
             "device_cause": "owned_cpu", "underlying_status": "z80_bus_failure",
             "operation": "unknown", "address": 0, "width": 0,
             "bus_access_valid": False},
        )
        for record in malformed:
            with self.subTest(record=record):
                rejected = safe_result({"status": "native_execution_error",
                                        "guest_executed": False,
                                        "native_failure": record})
                self.assertEqual(rejected["status"], "native_qualification_failed")
                self.assertNotIn("native_failure", rejected)
        for progress in (0, 1, "false", None):
            with self.subTest(progress=progress):
                rejected = safe_result({"status": "native_execution_error",
                                        "guest_executed": progress})
                self.assertEqual(rejected["status"], "native_qualification_failed")
        mismatch = safe_result({"status": "native_execution_error",
                                "guest_executed": True,
                                "native_failure": expected})
        self.assertEqual(mismatch["status"], "native_qualification_failed")
        legacy = safe_result({"status": "native_execution_error"})
        self.assertEqual(legacy["status"], "native_execution_error")
        self.assertNotIn("guest_executed", legacy)

    def test_public_failure_projection_removes_private_execution_detail(self) -> None:
        local = {
            "status": "native_execution_error", "guest_executed": True,
            "native_failure": {
                "component": "main_cpu", "stage": "execute",
                "reason": "internal_failure", "site": "main_execution",
                "site_valid": True, "device_cause": "owned_cpu",
                "device_cause_valid": True,
                "underlying_status": "owned_cpu_unsupported_opcode",
                "underlying_status_valid": True, "emulated_cycle": 1234,
                "emulated_cycle_valid": True, "completed_main_instructions": 1,
                "instruction_boundary_valid": True, "pc": 0xC00000,
                "pc_valid": True, "opcode": 0x4E71, "opcode_valid": True,
                "operation": "unknown", "address": 0, "width": 0,
                "bus_access_valid": False,
            },
            "debug_path": "/private/media/secret.rom",
        }
        public = public_result(local)
        self.assertEqual(public, {
            "status": "native_execution_error", "guest_executed": True,
            "native_failure": {"component": "main_cpu", "stage": "execute",
                               "reason": "internal_failure", "site": "main_execution"},
        })
        self.assertNotIn("private/media", json.dumps(public))

    def test_selected_bios_rejects_corrupt_flat_extra_without_output(self) -> None:
        game, bios = make_split_archives(
            bios_extras=(("synthetic-corrupt-extra.bin", bytes(range(64))),))
        corrupt = corrupt_member_payload(bios, "synthetic-corrupt-extra.bin")
        with tempfile.TemporaryDirectory(prefix="mvs-split-test-") as directory:
            game_path, bios_path = (os.path.join(directory, name)
                                    for name in ("game.zip", "bios.zip"))
            output_path = os.path.join(directory, "selected.gnmv")
            for path, payload in ((game_path, game), (bios_path, corrupt)):
                with open(path, "wb") as handle:
                    handle.write(payload)
            checked = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(checked.returncode, 0)
            self.assertFalse(Path(output_path).exists())

    def test_selected_bios_rejects_unsafe_or_duplicate_extra_names(self) -> None:
        cases = (
            (("../unsafe.bin", b"unsafe"),),
            (("synthetic-duplicate.bin", b"one"),
             ("synthetic-duplicate.bin", b"two")),
        )
        for extras in cases:
            game, bios = make_split_archives(bios_extras=extras)
            with tempfile.TemporaryDirectory(prefix="mvs-split-test-") as directory:
                game_path, bios_path = (os.path.join(directory, name)
                                        for name in ("game.zip", "bios.zip"))
                output_path = os.path.join(directory, "selected.gnmv")
                for path, payload in ((game_path, game), (bios_path, bios)):
                    with open(path, "wb") as handle:
                        handle.write(payload)
                checked = subprocess.run(
                    [self.importer, "--selected", game_path, bios_path, output_path],
                    capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(checked.returncode, 0)
                self.assertFalse(Path(output_path).exists())

    def test_selected_wrong_member_and_duplicate_are_rejected_without_output(self) -> None:
        cases = (({"replace_program": True}, self.importer),
                 ({"duplicate_program": True}, self.importer),
                 ({"wrong_bios_member": True}, self.production_importer))
        for options, selected_importer in cases:
            game, bios = make_split_archives(**options)
            with tempfile.TemporaryDirectory(prefix="mvs-split-test-") as directory:
                game_path, bios_path = (os.path.join(directory, name)
                                        for name in ("game.zip", "bios.zip"))
                output_path = os.path.join(directory, "selected.gnmv")
                for path, payload in ((game_path, game), (bios_path, bios)):
                    with open(path, "wb") as handle:
                        handle.write(payload)
                checked = subprocess.run(
                    [selected_importer, "--selected", game_path, bios_path, output_path],
                    capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(checked.returncode, 0)
                self.assertFalse(os.path.exists(output_path))
                self.assertNotIn("250-", checked.stderr)

    def test_selected_crc_unsupported_zip_and_output_failures_are_atomic(self) -> None:
        game, bios = make_split_archives()
        invalid_archives = (
            (mutate_zip_record(game, corrupt_crc=True), bios),
            (mutate_zip_record(game, flags=0x0008), bios),
        )
        for invalid_game, selected_bios in invalid_archives:
            with tempfile.TemporaryDirectory(prefix="mvs-split-test-") as directory:
                game_path, bios_path = (os.path.join(directory, name)
                                        for name in ("game.zip", "bios.zip"))
                output_path = os.path.join(directory, "selected.gnmv")
                for path, payload in ((game_path, invalid_game), (bios_path, selected_bios)):
                    with open(path, "wb") as handle:
                        handle.write(payload)
                result = subprocess.run(
                    [self.importer, "--selected", game_path, bios_path, output_path],
                    capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(os.path.exists(output_path))
                self.assertEqual(list(Path(directory).glob("selected.gnmv.tmp-*")), [])

        with tempfile.TemporaryDirectory(prefix="mvs-split-test-") as directory:
            game_path, bios_path = (os.path.join(directory, name)
                                    for name in ("game.zip", "bios.zip"))
            for path, payload in ((game_path, game), (bios_path, bios)):
                with open(path, "wb") as handle:
                    handle.write(payload)
            output_path = os.path.join(directory, "missing-parent", "selected.gnmv")
            result = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(os.path.exists(output_path))

    def run_selected(self, game: bytes | None, bios: bytes | None,
                     importer: str | None = None) -> tuple[subprocess.CompletedProcess[str], str, bool]:
        """Run the selected importer; a None archive means a nonexistent path.

        Returns the process, the output path and whether the output path (or any
        sibling temporary) exists afterwards.
        """
        with tempfile.TemporaryDirectory(prefix="mvs-class-test-") as directory:
            game_path, bios_path = (os.path.join(directory, name)
                                    for name in ("game.zip", "bios.zip"))
            output_path = os.path.join(directory, "selected.gnmv")
            for path, payload in ((game_path, game), (bios_path, bios)):
                if payload is not None:
                    with open(path, "wb") as handle:
                        handle.write(payload)
            result = subprocess.run(
                [importer or self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False)
            leftovers = [name for name in os.listdir(directory)
                         if name.startswith("selected.gnmv")]
            return result, output_path, bool(leftovers)

    def test_wrapper_maps_each_importer_exit_code_to_one_distinct_token(self) -> None:
        self.assertEqual(set(IMPORT_ERROR_CLASSES.values()), set(IMPORT_EXIT))
        self.assertEqual({code: IMPORT_ERROR_CLASSES[code] for code in IMPORT_ERROR_CLASSES},
                         {code: name for name, code in IMPORT_EXIT.items()})
        self.assertEqual(import_error_class(255), "import_failed")

    def test_selected_import_classes_are_distinct_actionable_and_recoverable(self) -> None:
        """Every selected failure cause has its own exit code and generic
        message, leaves no output, and the next valid pair still imports and
        loads through the native API (mvs_qualify -> gn_load_mvs)."""
        valid_game, valid_bios = make_split_archives(
            attract_guest=True,
            bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),))
        game_corrupt_crc = mutate_zip_record(valid_game, corrupt_crc=True)
        central_signature_broken = bytearray(valid_game)
        central_signature_broken[central_signature_broken.find(b"PK\x01\x02") + 3] = 0x03
        production, test = self.production_importer, self.importer
        zip64_game = make_split_archives(zip64_member="250-m1.m1")[0]
        malformed_zip64_game = make_split_archives(
            malformed_zip64_member="250-m1.m1")[0]
        cases = [
            # (class, game, bios, importer)
            ("malformed", valid_game[:-8], valid_bios, test),
            ("malformed", bytes(central_signature_broken), valid_bios, test),
            ("unsupported_feature", mutate_zip_record(valid_game, flags=0x0001), valid_bios, test),
            ("unsupported_feature", zip64_game, valid_bios, test),
            ("unsupported_feature", mutate_central_zip64_extra_to_opaque(
                zip64_game, "250-m1.m1"), valid_bios, test),
            ("unsupported_feature", mutate_local_zip64_extra_to_opaque(
                zip64_game, "250-m1.m1"), valid_bios, test),
            ("malformed", malformed_zip64_game, valid_bios, test),
            ("limit_exceeded", make_split_archives(oversize_member="250-c6.c6")[0], valid_bios, test),
            ("decompress_failed", game_corrupt_crc, valid_bios, test),
            ("decompress_failed", valid_game, corrupt_member_payload(valid_bios, BIOS_MEMBER), test),
            ("ambiguous", make_split_archives(duplicate_program=True)[0], valid_bios, test),
            ("unsupported_set", make_split_archives(replace_program=True)[0], valid_bios, test),
            ("unsupported_set", make_split_archives(drop_member="250-m1.m1")[0], valid_bios, test),
            ("bios_missing", valid_game, make_split_archives(omit_bios_member=True)[1], test),
            ("bios_incompatible", valid_game, make_split_archives(short_bios=True)[1], test),
            ("bios_incompatible", valid_game, make_split_archives(
                bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE - 1)),))[1], test),
            ("ambiguous", valid_game, make_split_archives(
                bios_extras=(("sm1.sm1", bytes(AUDIO_BIOS_SIZE)),
                             ("sm1.sm1", bytes(AUDIO_BIOS_SIZE))))[1], test),
            # Synthetic zero-filled bytes of the right size fail the pinned
            # CRC/SHA-1 identity that only the production importer enforces.
            ("bios_incompatible", valid_game, make_split_archives(wrong_bios_member=True)[1], production),
        ]
        runner = str(Path(self.production_importer).resolve().parent / "mvs_qualify")
        loaded_after: set[str] = set()
        with tempfile.TemporaryDirectory(prefix="mvs-class-test-") as directory:
            valid_game_path, valid_bios_path, bad_game_path, bad_bios_path = (
                os.path.join(directory, name)
                for name in ("game.zip", "bios.zip", "bad-game.zip", "bad-bios.zip"))
            output_path = os.path.join(directory, "selected.gnmv")
            for path, payload in ((valid_game_path, valid_game), (valid_bios_path, valid_bios)):
                with open(path, "wb") as handle:
                    handle.write(payload)
            for label, game, bios, importer in cases:
                with self.subTest(label=label, importer=Path(importer).name):
                    for path, payload in ((bad_game_path, game), (bad_bios_path, bios)):
                        with open(path, "wb") as handle:
                            handle.write(payload)
                    rejected = subprocess.run(
                        [importer, "--selected", bad_game_path, bad_bios_path, output_path],
                        capture_output=True, text=True, check=False)
                    self.assertEqual(rejected.returncode, IMPORT_EXIT[label], rejected.stderr)
                    self.assertEqual(rejected.stderr.strip(), IMPORT_MESSAGE[label])
                    for private in ("/", ".bin", "250-", "sp-s2", ".zip"):
                        self.assertNotIn(private, rejected.stderr)
                    leftovers = [name for name in os.listdir(directory)
                                 if name.startswith("selected.gnmv")]
                    self.assertEqual(leftovers, [], "rejected import left output or a temporary")
                    # Recovery: the valid pair still imports to the same destination.
                    good = subprocess.run(
                        [test, "--selected", valid_game_path, valid_bios_path, output_path],
                        capture_output=True, text=True, check=False)
                    self.assertEqual(good.returncode, 0, good.stderr)
                    if label not in loaded_after:
                        loaded_after.add(label)
                        loaded = subprocess.run([runner, output_path], capture_output=True,
                                                text=True, check=False)
                        try:
                            loaded_result = json.loads(loaded.stdout)
                        except json.JSONDecodeError as error:
                            self.fail(f"native qualifier returned invalid JSON: {error}")
                        self.assertEqual(loaded.returncode, 0, loaded.stdout)
                        self.assertEqual(loaded_result.get("status"), "attract_start",
                                         loaded.stdout)
                        self.assertIs(loaded_result.get("guest_executed"), True,
                                      loaded.stdout)
                    os.remove(output_path)

    def test_selected_memory_and_output_failures_have_their_own_classes(self) -> None:
        game, bios = make_split_archives()
        # Allocation failure through the test-only seam of the identity build.
        environment = dict(os.environ, MVS_IMPORT_TEST_FAIL_ALLOC="bundle")
        with tempfile.TemporaryDirectory(prefix="mvs-class-test-") as directory:
            game_path, bios_path = (os.path.join(directory, name)
                                    for name in ("game.zip", "bios.zip"))
            output_path = os.path.join(directory, "selected.gnmv")
            for path, payload in ((game_path, game), (bios_path, bios)):
                with open(path, "wb") as handle:
                    handle.write(payload)
            failed = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False, env=environment)
            self.assertEqual(failed.returncode, IMPORT_EXIT["memory"], failed.stderr)
            self.assertEqual(failed.stderr.strip(), IMPORT_MESSAGE["memory"])
            self.assertFalse(os.path.exists(output_path))
            unpublishable = os.path.join(directory, "missing-parent", "selected.gnmv")
            failed = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, unpublishable],
                capture_output=True, text=True, check=False)
            self.assertEqual(failed.returncode, IMPORT_EXIT["output_failed"], failed.stderr)
            self.assertEqual(failed.stderr.strip(), IMPORT_MESSAGE["output_failed"])
            self.assertFalse(os.path.exists(unpublishable))
            recovered = subprocess.run(
                [self.importer, "--selected", game_path, bios_path, output_path],
                capture_output=True, text=True, check=False)
            self.assertEqual(recovered.returncode, 0, recovered.stderr)

    def test_negative_controls_derive_classify_and_clean_up(self) -> None:
        """The local negative-control rule on synthetic archives: each control
        maps to a distinct class, originals are untouched, derived copies are
        removed, and the overall result is true only when the positive import
        and every control match. The identity-free test importer cannot reject
        the zeroed BIOS and the production importer cannot import synthetic
        media, so each alone must report failure while the other five or six
        controls still classify correctly."""
        game, bios = make_split_archives()
        self.assertEqual(len(set(NEGATIVE_EXPECTED.values())), len(NEGATIVE_EXPECTED))
        self.assertGreaterEqual(len(NEGATIVE_EXPECTED), 6)
        with tempfile.TemporaryDirectory(prefix="mvs-negative-test-") as directory:
            root = Path(directory)
            game_path, bios_path = root / "game.zip", root / "bios.zip"
            game_path.write_bytes(game)
            bios_path.write_bytes(bios)
            before = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (game_path, bios_path)}
            for importer, positive, mismatched in (
                    (self.importer, "imported", {"bios_member_zeroed": "imported"}),
                    (self.production_importer, "bios_incompatible", {})):
                work = root / ("work-" + Path(importer).name)
                work.mkdir()
                report, ok = run_negative_controls([importer], game_path, bios_path, work)
                with self.subTest(importer=Path(importer).name):
                    self.assertFalse(ok)
                    self.assertEqual(report["positive_import"], positive)
                    expected = {**NEGATIVE_EXPECTED, **mismatched}
                    self.assertEqual({k: v for k, v in report.items()
                                      if k != "positive_import"}, expected)
                    self.assertEqual(list(work.iterdir()), [], "derived copies were not removed")
                    for token in report.values():
                        self.assertRegex(token, r"^[a-z_]+$")
            self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in before}, before)
            report, ok = run_negative_controls(
                ["definitely-not-an-importer"], game_path, bios_path, root)
            self.assertFalse(ok)
            self.assertEqual(report["positive_import"], "importer_unavailable")

    def test_selected_missing_input_is_distinct_from_limit(self) -> None:
        game, bios = make_split_archives()
        missing, _, produced = self.run_selected(game, None)
        self.assertEqual(missing.returncode, IMPORT_EXIT["missing_input"], missing.stderr)
        self.assertEqual(missing.stderr.strip(), IMPORT_MESSAGE["missing_input"])
        self.assertFalse(produced)
        missing_game, _, produced = self.run_selected(None, bios)
        self.assertEqual(missing_game.returncode, IMPORT_EXIT["missing_input"])
        self.assertFalse(produced)
        with tempfile.TemporaryDirectory(prefix="mvs-class-test-") as directory:
            oversized = os.path.join(directory, "oversized.zip")
            with open(oversized, "wb") as handle:
                handle.truncate(96 * 1024 * 1024 + 1)
            bios_path = os.path.join(directory, "bios.zip")
            with open(bios_path, "wb") as handle:
                handle.write(bios)
            limited = subprocess.run(
                [self.importer, "--selected", oversized, bios_path,
                 os.path.join(directory, "selected.gnmv")],
                capture_output=True, text=True, check=False)
            self.assertEqual(limited.returncode, IMPORT_EXIT["limit_exceeded"], limited.stderr)
            self.assertEqual(limited.stderr.strip(), IMPORT_MESSAGE["limit_exceeded"])
            self.assertFalse(os.path.exists(os.path.join(directory, "selected.gnmv")))

    def test_eocd_signature_inside_comment_does_not_hide_directory(self) -> None:
        archive = bytearray(make_archive(method=zipfile.ZIP_STORED))
        eocd = archive.rfind(b"PK\x05\x06")
        comment = bytearray(b"PK\x05\x06" + bytes(18))
        struct.pack_into("<H", comment, 8, 6)
        struct.pack_into("<H", comment, 10, 6)
        struct.pack_into("<I", comment, 16, len(archive))
        struct.pack_into("<H", archive, eocd + 20, len(comment))
        archive.extend(comment)
        with tempfile.TemporaryDirectory(prefix="mvs-test-") as directory:
            input_path = os.path.join(directory, "input.zip")
            output_path = os.path.join(directory, "output.gnmv")
            with open(input_path, "wb") as handle:
                handle.write(archive)
            result = subprocess.run([self.importer, input_path, output_path],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_malformed_and_unsupported_archives_have_stable_statuses(self) -> None:
        valid = make_archive(method=zipfile.ZIP_STORED)
        cases: list[tuple[str, bytes, int]] = [("truncated", valid[:-8], 1)]

        local_extra_oob = bytearray(valid)
        local = local_extra_oob.find(b"PK\x03\x04")
        struct.pack_into("<H", local_extra_oob, local + 28, 0xFFFF)
        cases.append(("local_extra_oob", bytes(local_extra_oob), 1))

        encrypted = bytearray(valid)
        local = encrypted.find(b"PK\x03\x04")
        central = encrypted.find(b"PK\x01\x02")
        struct.pack_into("<H", encrypted, local + 6, 1)
        struct.pack_into("<H", encrypted, central + 8, 1)
        cases.append(("encrypted", bytes(encrypted), 2))

        unsafe_name = bytearray(valid)
        local = unsafe_name.find(b"PK\x03\x04")
        central = unsafe_name.find(b"PK\x01\x02")
        unsafe_name[local + 30:local + 38] = b"../x.bin"
        unsafe_name[central + 46:central + 54] = b"../x.bin"
        cases.append(("unsafe_name", bytes(unsafe_name), 2))

        unsupported_method = bytearray(valid)
        local = unsupported_method.find(b"PK\x03\x04")
        central = unsupported_method.find(b"PK\x01\x02")
        struct.pack_into("<H", unsupported_method, local + 8, 99)
        struct.pack_into("<H", unsupported_method, central + 10, 99)
        cases.append(("unsupported_method", bytes(unsupported_method), 2))

        mismatch = make_archive(wrong_size=True)
        cases.append(("region_size", mismatch, 3))
        duplicated = make_archive(duplicate=True)
        cases.append(("duplicate_role", duplicated, 7))

        bad_crc = bytearray(valid)
        central = bad_crc.find(b"PK\x01\x02")
        local = struct.unpack_from("<I", bad_crc, central + 42)[0]
        old_crc = struct.unpack_from("<I", bad_crc, central + 16)[0]
        struct.pack_into("<I", bad_crc, central + 16, old_crc ^ 1)
        struct.pack_into("<I", bad_crc, local + 14, old_crc ^ 1)
        cases.append(("crc", bytes(bad_crc), 5))

        for label, archive, expected in cases:
            with self.subTest(label=label):
                result = self.run_import(archive)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn("/", result.stderr)
                self.assertNotIn(".bin", result.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--importer")
    parser.add_argument("--failure-driver")
    parser.add_argument("--fuzzer")
    parser.add_argument("--mode", choices=("positive", "maximum-horizon", "mutation", "fuzz", "failure"))
    args = parser.parse_args()
    if args.mode == "fuzz":
        if not args.fuzzer:
            parser.error("--fuzzer is required for fuzz mode")
        with tempfile.TemporaryDirectory(prefix="mvs-fuzz-") as directory:
            archive = os.path.join(directory, "synthetic.zip")
            with open(archive, "wb") as handle:
                handle.write(make_archive())
            result = subprocess.run([args.fuzzer, archive], capture_output=True,
                                    text=True, check=False)
            if result.returncode != 0:
                print("bounded importer mutation corpus failed", file=__import__("sys").stderr)
                return 1
        return 0
    if args.importer:
        ImporterTests.importer = args.importer
    if args.failure_driver:
        ImporterTests.failure_driver = args.failure_driver
    test_importer_dir = None
    if args.mode in ("positive", "maximum-horizon", "mutation", "failure") and args.importer:
        ImporterTests.production_importer = args.importer
        test_importer, test_importer_dir = test_identity_importer(args.importer)
        ImporterTests.importer = test_importer
    if args.mode == "maximum-horizon":
        suite = unittest.TestSuite([
            ImporterTests("test_maximum_active_frame_horizon_completes_guest_and_capture"),
        ])
    elif args.mode == "positive":
        suite = unittest.TestSuite([
            ImporterTests("test_identity_importer_links_configured_sdk_sanitizer"),
            ImporterTests("test_media_identity_accepts_native_absolute_paths_and_rejects_relative_paths"),
            ImporterTests("test_selected_import_output_reaches_frontend_bundle_validator"),
            ImporterTests("test_deflated_archive_normalizes_selected_profile"),
            ImporterTests("test_optional_audio_bios_emits_v2_bundle_and_preserves_exact_bytes"),
            ImporterTests("test_optional_audio_bios_rejects_wrong_size_and_duplicate_role"),
            ImporterTests("test_eocd_signature_inside_comment_does_not_hide_directory"),
            ImporterTests("test_classifier_candidate_requires_exact_central_extent"),
            ImporterTests("test_classifier_pair_respects_combined_import_limit"),
            ImporterTests("test_budget_result_keeps_only_bounded_private_diagnostic_fields"),
            ImporterTests("test_selected_acceptance_keeps_independent_predicates_and_publicly_projects_tokens"),
            ImporterTests("test_manual_visual_title_review_resolves_only_bound_unknown"),
            ImporterTests("test_sound_io_bus_failure_reports_coarse_native_diagnosis"),
            ImporterTests("test_selected_split_archives_normalize_exact_mslugx_map"),
            ImporterTests("test_selected_optional_audio_bios_emits_v2_bundle_and_loads"),
            ImporterTests("test_synthetic_handoff_reaches_attract_start_through_real_qualifier"),
            ImporterTests("test_frame_indexed_held_input_captures_real_guest_pixels_and_rejects_bad_scripts"),
            ImporterTests("test_scripted_coin_stays_held_until_delayed_bios_poll"),
            ImporterTests("test_scripted_start_stays_held_until_delayed_bios_poll"),
            ImporterTests("test_active_frame_and_scene_contract_projection_is_strict"),
            ImporterTests("test_attract_checkpoint_without_frame_does_not_require_supported_zoom"),
            ImporterTests("test_requested_fault_boundary_frame_failure_is_not_swallowed"),
            ImporterTests("test_attract_start_accepts_only_the_exact_checkpoint_shape"),
            ImporterTests("test_video_advance_report_separates_requested_and_completed_frames"),
            ImporterTests("test_missing_audio_region_is_a_safe_stop_without_guest_execution"),
            ImporterTests("test_budget_exhaustion_reports_a_sanitized_diagnosis_from_the_real_qualifier"),
            ImporterTests("test_diagnosis_keeps_only_the_whitelisted_public_shape"),
            ImporterTests("test_selected_bios_ignores_flat_bounded_extras_after_crc_validation"),
            ImporterTests("test_selected_bios_allows_deflate_hints_only_on_deflated_members"),
            ImporterTests("test_classifier_structure_rejects_zip64_extra_fields"),
            ImporterTests("test_qualifier_freshness_classifies_build_results"),
            ImporterTests("test_qualifier_freshness_refusal_runs_no_guest"),
            ImporterTests("test_private_frame_output_is_ignored_and_bounded"),
            ImporterTests("test_video_frame_advance_is_bounded_and_forwarded"),
            ImporterTests("test_phase06_calibration_binds_native_samples_and_configuration"),
            ImporterTests("test_phase06_calibration_forwards_bounded_capture_window"),
            ImporterTests("test_phase07_sound_windows_require_bounded_aligned_non_silent_pcm"),
            ImporterTests("test_phase07_sound_contract_option_is_bound_to_active_scene"),
            ImporterTests("test_phase07_family_status_never_equates_register_writes_with_output"),
            ImporterTests("test_retained_frontend_evaluation_never_launches_and_keeps_device_evidence_historical"),
            ImporterTests("test_retained_frontend_audio_evaluation_rejects_unowned_paths_without_execution"),
            ImporterTests("test_frontend_audio_only_dispatch_cannot_claim_full_scene_acceptance"),
            ImporterTests("test_frontend_audio_trace_replays_control_and_route_with_complete_frame_metadata"),
            ImporterTests("test_frontend_audio_replay_preserves_every_prefix_mask_and_only_omits_fire"),
            ImporterTests("test_frontend_audio_frame_history_binds_inputs_clocks_and_replayed_counts"),
            ImporterTests("test_frontend_sound_windows_preserve_frozen_causal_rules_at_observed_transitions"),
            ImporterTests("test_frontend_audio_control_matrix_reuses_tracer_and_stops_before_visual_on_missing_control"),
            ImporterTests("test_phase07_frontend_traces_audio_before_visual_campaign"),
            ImporterTests("test_phase07_frontend_accepts_bound_sound_contract"),
            ImporterTests("test_native_sound_window_capture_is_bounded_and_input_aligned"),
            ImporterTests("test_phase06_frontend_dispatch_requires_actual_bound_predicates"),
            ImporterTests("test_phase06_frontend_capture_rejects_missing_or_wrong_observations"),
            ImporterTests("test_phase06_frontend_freeze_requires_exact_review_evidence"),
            ImporterTests("test_phase06_frontend_start_and_scheduled_masks_require_successful_video"),
            ImporterTests("test_phase06_frontend_temporal_comparison_requires_overlapping_held_windows"),
            ImporterTests("test_phase06_frontend_retiming_preserves_native_controls_and_scene"),
            ImporterTests("test_phase06_native_contract_requires_frozen_complete_causal_schema"),
            ImporterTests("test_phase06_scroll_requires_coherent_horizontal_translation"),
            ImporterTests("test_phase06_actor_track_preserves_anchor_across_facing_flip"),
            ImporterTests("test_combined_animation_uses_independently_unique_intermediate_tracks"),
            ImporterTests("test_temporal_actor_tracks_reject_conflicting_unique_paths"),
            ImporterTests("test_phase06_combined_requires_projectile_contrast_against_movement_control"),
            ImporterTests("test_phase06_movement_requires_matched_t0_and_nontrivial_actor_track"),
            ImporterTests("test_phase06_pixel_predicates_require_complete_distinct_pair_captures"),
            ImporterTests("test_phase06_causal_evidence_accepts_coherent_matched_native_tracks"),
            ImporterTests("test_phase06_frozen_replay_validates_complete_synthetic_calibration"),
            ImporterTests("test_phase06_evaluator_identity_tracks_acceptance_source_bytes"),
            ImporterTests("test_scripted_start_keeps_qualifier_freshness"),
            ImporterTests("test_selected_qualification_rejects_qualifier_substitution"),
            ImporterTests("test_selected_qualification_binds_execution_to_configured_importer"),
            ImporterTests("test_nonzero_native_positive_is_rejected"),
            ImporterTests("test_nonzero_main_bus_guest_fault_preserves_validated_diagnostic"),
            ImporterTests("test_invalid_utf8_preserves_durable_uncertain_receipt"),
            ImporterTests("test_runner_zero_instruction_attempt_is_counted"),
            ImporterTests("test_pre_entry_refusal_is_not_counted"),
            ImporterTests("test_importer_timeout_is_retained_without_native_execution"),
            ImporterTests("test_ambiguous_runner_attempt_consumes_slot"),
            ImporterTests("test_native_runner_interruption_is_retained_as_uncertain"),
            ImporterTests("test_native_runner_uses_host_timeouts_and_rejects_oversized_report"),
            ImporterTests("test_main_keeps_unique_atomic_failure_reports"),
            ImporterTests("test_simultaneous_selected_invocations_use_distinct_bundles"),
            ImporterTests("test_non_object_runner_json_preserves_counted_attempt"),
            ImporterTests("test_selected_qualification_rechecks_identity_immediately_before_execution"),
            ImporterTests("test_selected_qualification_rejects_same_path_byte_substitution"),
            ImporterTests("test_selected_qualification_uses_expected_media_snapshots"),
            ImporterTests("test_selected_qualification_rejects_snapshot_symlink_race"),
            ImporterTests("test_selected_qualification_bounds_media_snapshot_growth"),
            ImporterTests("test_selected_qualification_rejects_capture_directory_symlink_race"),
            ImporterTests("test_mock_freshness_status_alone_does_not_grant_importer_identity"),
            ImporterTests("test_check_fresh_rejects_same_path_byte_substitution"),
            ImporterTests("test_negative_controls_reject_same_path_byte_substitution"),
            ImporterTests("test_negative_controls_recheck_identity_before_each_import"),
            ImporterTests("test_check_fresh_and_negative_controls_reject_unchecked_importers"),
            ImporterTests("test_synthetic_importer_identity_requires_exact_path_and_digest"),
            ImporterTests("test_source_gate_uses_exact_required_ids_and_rejects_duplicates"),
            ImporterTests("test_source_gate_keeps_digest_and_excerpt_checks"),
        ])
    elif args.mode == "failure":
        suite = unittest.TestSuite([
            ImporterTests("test_active_failures_retain_requested_and_completed_progress"),
            ImporterTests("test_sound_io_bus_failure_reports_coarse_native_diagnosis"),
            ImporterTests("test_failure_driver_main_failure_before_instruction"),
            ImporterTests("test_failure_driver_main_failure_after_instruction"),
            ImporterTests("test_failure_diagnostic_marks_executed_zero_opcode_valid"),
            ImporterTests("test_failure_driver_first_instruction_fault_keeps_zero_execution_count"),
            ImporterTests("test_failure_driver_classifies_main_bus_faults_as_guest_events"),
            ImporterTests("test_scripted_start_preserves_native_fault_diagnostics"),
            ImporterTests("test_failure_driver_sound_tick_limit"),
            ImporterTests("test_failure_driver_sound_before_main_progress"),
            ImporterTests("test_failure_driver_reports_typed_main_and_sound_detail"),
            ImporterTests("test_failure_driver_first_error_precedence"),
            ImporterTests("test_failure_driver_diagnostic_reset_isolation"),
            ImporterTests("test_native_failure_schema_rejects_empty_extra_and_invalid_tokens"),
            ImporterTests("test_public_failure_projection_removes_private_execution_detail"),
        ])
    elif args.mode == "mutation":
        suite = unittest.TestSuite([
            ImporterTests("test_malformed_and_unsupported_archives_have_stable_statuses"),
            ImporterTests("test_selected_wrong_member_and_duplicate_are_rejected_without_output"),
            ImporterTests("test_selected_crc_unsupported_zip_and_output_failures_are_atomic"),
            ImporterTests("test_selected_bios_rejects_corrupt_flat_extra_without_output"),
            ImporterTests("test_selected_bios_rejects_unsafe_or_duplicate_extra_names"),
            ImporterTests("test_selected_bios_allows_deflate_hints_only_on_deflated_members"),
            ImporterTests("test_classifier_structure_rejects_zip64_extra_fields"),
            ImporterTests("test_selected_missing_input_is_distinct_from_limit"),
            ImporterTests("test_wrapper_maps_each_importer_exit_code_to_one_distinct_token"),
            ImporterTests("test_selected_import_classes_are_distinct_actionable_and_recoverable"),
            ImporterTests("test_selected_memory_and_output_failures_have_their_own_classes"),
            ImporterTests("test_negative_controls_derive_classify_and_clean_up"),
            ImporterTests("test_selected_qualification_binds_execution_to_configured_importer"),
            ImporterTests("test_selected_qualification_rechecks_identity_immediately_before_execution"),
            ImporterTests("test_selected_qualification_rejects_same_path_byte_substitution"),
            ImporterTests("test_mock_freshness_status_alone_does_not_grant_importer_identity"),
            ImporterTests("test_check_fresh_rejects_same_path_byte_substitution"),
            ImporterTests("test_negative_controls_reject_same_path_byte_substitution"),
            ImporterTests("test_negative_controls_recheck_identity_before_each_import"),
            ImporterTests("test_check_fresh_and_negative_controls_reject_unchecked_importers"),
            ImporterTests("test_synthetic_importer_identity_requires_exact_path_and_digest"),
            ImporterTests("test_source_gate_uses_exact_required_ids_and_rejects_duplicates"),
            ImporterTests("test_source_gate_keeps_digest_and_excerpt_checks"),
        ])
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ImporterTests)
    succeeded = unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
    if test_importer_dir is not None:
        test_importer_dir.cleanup()
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
