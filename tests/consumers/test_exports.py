#!/usr/bin/env python3
"""Cross-platform shared-library export contract tests."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "consumers"))
import check_package


WINDOWS_EXPORTS = """
Microsoft (R) COFF/PE Dumper Version 14.43.34808.0
Dump of file glueyneo.dll

File Type: DLL

  Section contains the following exports for glueyneo.dll

    ordinal hint RVA      name
          1    0 00001000 gn_create
          2    1 00001010 gn_load
          3    2 00001020 gn_reset
          4    3 00001030 gn_run
          5    4 00001040 gn_observe
          6    5 00001050 gn_unload
          7    6 00001060 gn_destroy
          8    7 00001070 gn_status_string
"""


class SharedExportTests(unittest.TestCase):
    def test_linux_loader_initialization_resolves_relocated_parent_segments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp) / "sdk prefix"
            (prefix / "bin").mkdir(parents=True)
            (prefix / "lib").mkdir()
            library = prefix / "lib/libglueyneo.so"
            library.touch()
            loader_path = str(prefix / "bin/../lib/libglueyneo.so")
            self.assertTrue(check_package.linux_trace_loaded_library(
                "  132: calling init: " + loader_path + "\n", library))
            for output in (
                "  132: trying file=" + loader_path + "\n",
                "  132: calling init: " + str(prefix / "wrong/libglueyneo.so") + "\n",
                "  132: calling init: libglueyneo.so\n",
            ):
                self.assertFalse(check_package.linux_trace_loaded_library(output, library))

    def test_windows_dll_exports_use_the_shared_exact_contract(self) -> None:
        parser = getattr(check_package, "parse_windows_exports", None)
        self.assertIsNotNone(parser, "Windows DUMPBIN export parsing is required")
        if parser is None:
            return
        self.assertEqual(
            parser(WINDOWS_EXPORTS),
            {
                "gn_create", "gn_load", "gn_reset", "gn_run", "gn_observe",
                "gn_unload", "gn_destroy", "gn_status_string",
            },
        )

    def test_export_contract_rejects_extra_missing_and_private_names(self) -> None:
        parser = getattr(check_package, "parse_windows_exports", None)
        contract = getattr(check_package, "check_export_contract", None)
        self.assertTrue(callable(parser) and callable(contract), "Windows export contract helpers are required")
        if not callable(parser) or not callable(contract):
            return
        expected = parser(WINDOWS_EXPORTS)
        self.assertEqual(contract(expected), sorted(expected))
        for output in (
            WINDOWS_EXPORTS.replace("gn_status_string", "gn_status_string\n          9    8 00001080 gn_extra"),
            WINDOWS_EXPORTS.replace("          8    7 00001070 gn_status_string\n", ""),
            WINDOWS_EXPORTS.replace("          8    7 00001070 gn_status_string", "          8    7 00001070 owned_cpu_secret"),
        ):
            with self.assertRaises(check_package.CheckError):
                contract(parser(output))

    def test_windows_parser_fails_closed_on_unknown_output(self) -> None:
        parser = getattr(check_package, "parse_windows_exports", None)
        self.assertTrue(callable(parser), "Windows DUMPBIN export parser is required")
        if not callable(parser):
            return
        for output in (
            "DUMPBIN failed to load this file",
            "File Type: DLL\nordinal hint RVA name\nnot an export row",
            "File Type: executable\nordinal hint RVA name\n  1 0 10 gn_create",
        ):
            with self.assertRaises(check_package.CheckError):
                parser(output)

    def test_windows_inspector_is_required(self) -> None:
        with mock.patch.object(check_package.sys, "platform", "win32"), \
             mock.patch.object(check_package.shutil, "which", return_value=None):
            with self.assertRaisesRegex(check_package.CheckError, "dumpbin"):
                check_package.shared_exports(Path("glueyneo.dll"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
