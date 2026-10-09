#!/usr/bin/env python3
"""Public synthetic archive checks for the bounded MVS importer."""
from __future__ import annotations

import argparse
import io
import os
import struct
import subprocess
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

NAMES = (
    "bios.bin", "program.bin", "fixed.bin", "audio.bin", "samples.bin",
    "sprites.bin",
)
SIZES = (0x80000, 0x500000, 0x20000, 0x20000, 0xA00000, 0x3000000)

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


def make_split_archives(*, replace_program: bool = False,
                        duplicate_program: bool = False,
                        wrong_bios_member: bool = False) -> tuple[bytes, bytes]:
    game, bios = io.BytesIO(), io.BytesIO()
    with zipfile.ZipFile(game, "w", compression=zipfile.ZIP_STORED,
                         allowZip64=False) as archive:
        for index, (name, size) in enumerate(GAME_MEMBERS.items()):
            if replace_program and name == "250-p1.p1":
                name = "250-p1-wrong.p1"
            payload = bytearray([0x11 + index]) * size
            if name == "250-p1.p1":
                payload[:12] = bytes.fromhex("5a72c13310000000724e0027")
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
        archive.writestr(BIOS_MEMBER, data)
    return game.getvalue(), bios.getvalue()


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
        command = [compiler, "/nologo", "/std:c17", "/DMVS_IMPORT_TEST_IDENTITIES",
                   f"/I{root / 'third_party/zlib'}", str(root / "tools/mvs/mvs_import.c"), str(library),
                   f"/Fe:{binary}"]
    else:
        library = build_dir / "libglueyneo_mvs_zlib.a"
        sanitizer_flags = (["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
                           if cache_values.get("GLUEYNEO_SDK_SANITIZER") == "ADDRESS_UNDEFINED"
                           else [])
        command = [compiler, "-std=c17", *sanitizer_flags,
                   "-DMVS_IMPORT_TEST_IDENTITIES",
                   "-I", str(root / "third_party/zlib"), str(root / "tools/mvs/mvs_import.c"), str(library),
                   *sanitizer_flags, "-o", str(binary)]
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return str(binary), temporary


def make_archive(*, method: int = zipfile.ZIP_DEFLATED,
                 wrong_size: bool = False, duplicate: bool = False) -> bytes:
    data = [bytearray(size) for size in SIZES]
    data[0][0:8] = bytes.fromhex("0010fffe00000100")
    data[0][0x100:0x10C] = bytes.fromhex("725a33c1001000004e722700")
    if wrong_size:
        data[-1] = data[-1][:-1]
    target = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(target, "w", compression=method,
                             compresslevel=6, allowZip64=False) as archive:
            for index, (name, payload) in enumerate(zip(NAMES, data)):
                if duplicate and index == 2:
                    continue
                archive.writestr(name, payload)
            if duplicate:
                archive.writestr("program.bin", bytes(SIZES[1]))
    return target.getvalue()


class ImporterTests(unittest.TestCase):
    importer = os.environ.get("MVS_IMPORTER", "build/sdk-debug/mvs_importer")
    production_importer = importer

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
            self.assertEqual(execution.returncode, 0, execution.stdout)
            self.assertIn('"guest_executed":true', execution.stdout)
            self.assertIn('"status":"guest_stopped"', execution.stdout)
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
    parser.add_argument("--fuzzer")
    parser.add_argument("--mode", choices=("positive", "mutation", "fuzz"))
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
    test_importer_dir = None
    if args.mode in ("positive", "mutation") and args.importer:
        ImporterTests.production_importer = args.importer
        test_importer, test_importer_dir = test_identity_importer(args.importer)
        ImporterTests.importer = test_importer
    if args.mode == "positive":
        suite = unittest.TestSuite([
            ImporterTests("test_deflated_archive_normalizes_selected_profile"),
            ImporterTests("test_eocd_signature_inside_comment_does_not_hide_directory"),
            ImporterTests("test_selected_split_archives_normalize_exact_mslugx_map"),
        ])
    elif args.mode == "mutation":
        suite = unittest.TestSuite([
            ImporterTests("test_malformed_and_unsupported_archives_have_stable_statuses"),
            ImporterTests("test_selected_wrong_member_and_duplicate_are_rejected_without_output"),
            ImporterTests("test_selected_crc_unsupported_zip_and_output_failures_are_atomic"),
        ])
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ImporterTests)
    succeeded = unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
    if test_importer_dir is not None:
        test_importer_dir.cleanup()
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
