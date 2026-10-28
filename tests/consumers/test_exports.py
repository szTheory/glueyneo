#!/usr/bin/env python3
"""Cross-platform shared-library export contract tests."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "consumers"))
import check_package
from tools import verify_sdk


WINDOWS_EXPORTS = """
Microsoft (R) COFF/PE Dumper Version 14.43.34808.0
Dump of file glueyneo.dll

File Type: DLL

  Section contains the following exports for glueyneo.dll

    ordinal hint RVA      name
          1    0 00001000 gn_create
          2    1 00001010 gn_load
          3    2 00001020 gn_load_mvs
          4    3 00001030 gn_run_mvs
          5    4 00001040 gn_observe
          6    5 00001050 gn_observe_mvs_bus_fault
          7    6 00001060 gn_set_mvs_inputs
          8    7 00001070 gn_observe_mvs_progress
          9    8 00001080 gn_reset
         10    9 00001090 gn_run
         11   10 000010a0 gn_advance_frame
         12   11 000010b0 gn_unload
         13   12 000010c0 gn_destroy
         14   13 000010d0 gn_status_string
         15   14 000010e0 gn_load_mvs_v3
         16   15 000010f0 gn_mvs_audio_capacity_v1
         17   16 00001100 gn_mvs_advance_frame_v1
         18   17 00001110 gn_state_capacity_v1
         19   18 00001120 gn_state_capture_v1
         20   19 00001130 gn_state_restore_v1
         21   20 00001140 gn_state_compatibility_v1
         22   21 00001150 gn_state_reason_string
         23   22 00001160 gn_mvs_save_query_v1
         24   23 00001170 gn_mvs_save_export_v1
         25   24 00001180 gn_mvs_save_import_baseline_v1
         26   25 00001190 gn_mvs_save_ack_v1
         27   26 000011a0 gn_mvs_save_scope_renew_v1
         28   27 000011b0 gn_mvs_save_reason_string
         29   28 000011c0 gn_load_mvs_v3_checked_v1
         30   29 000011d0 gn_unload_checked_v1
         31   30 000011e0 gn_destroy_checked_v1
"""

WINDOWS_SYMBOLS = """
Microsoft (R) COFF/PE Dumper Version 14.51.36231.0
Dump of file glueyneo.lib
File Type: LIBRARY

COFF SYMBOL TABLE
000 00000000 SECT1 notype () External | gn_create
001 00000000 UNDEF notype () External | malloc

COFF SYMBOL TABLE
000 00000000 SECT1 notype () External | owned_cpu_create
001 00000000 UNDEF notype () External | memset
"""


class WindowsRuntimeClosureTests(unittest.TestCase):
    def inspect(self, output: str, *, exit_code: int = 0,
                source: str = "void sdk_fixture(void) {}\n") -> subprocess.CompletedProcess[str]:
        # Exercise the actual generated CMake closure with controlled inspector
        # output. This proves rejection behavior without claiming a Windows run.
        cmake_source = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        closure = cmake_source.split("set(SDK_HOST_CLOSURE_CONTENT [=[\n", 1)[1].split("\n]=])", 1)[0]
        with tempfile.TemporaryDirectory(prefix="glueyneo-coff-control-") as temp:
            directory = Path(temp)
            sources = [directory / "instance.c", directory / "cpu.c"]
            for path in sources:
                path.write_text(source, encoding="utf-8")
            library = directory / "glueyneo.lib"
            library.touch()
            inspector = directory / "inspector.py"
            inspector.write_text(
                "import sys\n"
                f"assert sys.argv[1:] == ['/SYMBOLS', {library.as_posix()!r}]\n"
                f"sys.stdout.write({output!r})\n"
                f"raise SystemExit({exit_code})\n",
                encoding="utf-8",
            )
            substitutions = {
                "@CMAKE_CURRENT_SOURCE_DIR@": ROOT.as_posix(),
                "@Python3_EXECUTABLE@": Path(sys.executable).as_posix(),
                "@SDK_RUNTIME_ABSOLUTE_SOURCES@": ";".join(path.as_posix() for path in sources),
                "$<TARGET_FILE:glueyneo>": library.as_posix(),
                "@CMAKE_NM@": "unused-nm",
                "@WIN32@": "TRUE",
                "@GLUEYNEO_SDK_DUMPBIN@": Path(sys.executable).as_posix() + ";" + inspector.as_posix(),
            }
            for key, value in substitutions.items():
                closure = closure.replace(key, value)
            script = directory / "closure.cmake"
            script.write_text(closure + "\n", encoding="utf-8")
            return subprocess.run(
                [shutil.which("cmake") or "cmake", "-P", str(script)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=30, check=False,
            )

    def test_accepts_complete_runtime_coff_tables(self) -> None:
        result = self.inspect(WINDOWS_SYMBOLS)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("SDK runtime host-call closure passed", result.stdout)

    def test_rejects_imported_and_decorated_ambient_host_symbols(self) -> None:
        for symbol in ("__imp_CreateFileW", "__imp_QueryPerformanceCounter",
                       "__imp_WSAStartup", "__imp__beginthreadex", "_ReadFile@20",
                       "__imp_Sleep"):
            with self.subTest(symbol=symbol):
                result = self.inspect(WINDOWS_SYMBOLS.replace("| malloc", "| " + symbol))
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Ambient host symbol found in runtime", result.stdout)

    def test_rejects_private_test_symbols(self) -> None:
        for symbol in ("gn_test_create", "_gn_test_create@8", "__imp_gn_test_create"):
            with self.subTest(symbol=symbol):
                result = self.inspect(WINDOWS_SYMBOLS.replace("| gn_create", "| " + symbol))
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Private test hook leaked", result.stdout)

    def test_fails_closed_on_unknown_partial_and_failed_inspection(self) -> None:
        controls = (
            ("File Type: LIBRARY\n/GL object has no symbol table\n", 0),
            (WINDOWS_SYMBOLS.split("COFF SYMBOL TABLE", 2)[0] + "COFF SYMBOL TABLE\n"
             "000 00000000 SECT1 notype () External | gn_create\n", 0),
            (WINDOWS_SYMBOLS.replace("000 00000000 SECT1", "000 unknown-value SECT1"), 0),
            (WINDOWS_SYMBOLS.replace("External", "Static"), 0),
            (WINDOWS_SYMBOLS, 1),
        )
        for output, code in controls:
            with self.subTest(output=output, code=code):
                result = self.inspect(output, exit_code=code)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn("SDK runtime host-call closure passed", result.stdout)

    def test_retains_windows_ambient_source_call_rejection(self) -> None:
        result = self.inspect(WINDOWS_SYMBOLS, source="void sdk_fixture(void) { GetTickCount64(); }\n")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Ambient host call found in runtime source", result.stdout)


class SharedExportTests(unittest.TestCase):
    def test_instrumented_static_export_selects_only_the_sanitizer_runtime(self) -> None:
        cmake_source = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        sanitizer_function = cmake_source.split(
            "function(glueyneo_apply_sdk_sanitizer target)", 1)[1].split(
                "endfunction()", 1)[0]
        self.assertIn('if(target_type STREQUAL "STATIC_LIBRARY")', sanitizer_function)
        self.assertIn(
            "target_link_options(${target} INTERFACE "
            "${GLUEYNEO_SDK_SANITIZER_RUNTIME_LINK_FLAG})",
            sanitizer_function,
            "instrumented static exports must select only the sanitizer runtime",
        )


class InstalledSanitizerInventoryTests(unittest.TestCase):
    def validate(self, rows: list[dict[str, object]], *, require_supported: bool = False) -> None:
        validator = getattr(verify_sdk, "validate_installed_sanitizer_inventory", None)
        self.assertTrue(callable(validator),
                        "sanitizer verifier must expose exact installed case validation")
        if callable(validator):
            validator(rows, require_supported=require_supported)

    def rows(self) -> list[dict[str, object]]:
        rows = []
        case_ids = ("ordinary_none_export", "installed_c_chip",
                    "installed_cxx_chip", "removed_runtime_usage")
        for mode, run_id in (("ADDRESS_UNDEFINED", "asan-100"), ("THREAD", "tsan-200")):
            for case_id in case_ids:
                none_case = case_id == "ordinary_none_export"
                rows.append({
                    "schema_version": 1,
                    "case_id": case_id,
                    "mode": mode,
                    "tested_mode": "NONE" if none_case else mode,
                    "run_id": run_id,
                    "prefix_id": f"installed/{mode}/{run_id}",
                    "prefixes": ([f"installed/NONE/static/{run_id}",
                                  f"installed/NONE/shared/{run_id}"] if none_case else None),
                    "linkage": "static_shared" if none_case else "static",
                    "configuration": "Debug",
                    "outcome": "pass",
                    "cases": 1,
                    "assertions": 8,
                    "duration_seconds": 0.1,
                    "detail": "synthetic positive consumer record",
                    "compiler": {"c_id": "Clang", "cxx_id": "Clang",
                                 "c_version": "18.1.3", "cxx_version": "18.1.3",
                                 "c_path": "/usr/bin/clang", "cxx_path": "/usr/bin/clang++",
                                 "linker": "/usr/bin/ld.lld", "sanitizer": "NONE" if none_case else mode},
                    "platform": {"system": "Linux", "release": "6.8", "machine": "x86_64"},
                })
        return rows

    def test_accepts_exact_distinct_positive_mode_inventories(self) -> None:
        self.validate(self.rows())

    def test_rejects_missing_duplicate_and_zero_denominator_records(self) -> None:
        valid = self.rows()
        for broken in (
            valid[:-1],
            valid + [dict(valid[1])],
            [dict(row, cases=0) if row["case_id"] == "installed_c_chip" else row
             for row in valid],
            [dict(row, assertions=0) if row["case_id"] == "installed_cxx_chip" else row
             for row in valid],
        ):
            with self.subTest(rows=len(broken)):
                with self.assertRaises(verify_sdk.VerificationError):
                    self.validate(broken)

    def test_rejects_prefix_reuse_and_unsupported_required_ci_rows(self) -> None:
        reused_prefix = self.rows()
        for row in reused_prefix:
            if row["mode"] == "THREAD":
                row["prefix_id"] = "installed/ADDRESS_UNDEFINED/asan-100"
        with self.assertRaises(verify_sdk.VerificationError):
            self.validate(reused_prefix)

        unsupported = self.rows()
        target = next(row for row in unsupported
                      if row["mode"] == "ADDRESS_UNDEFINED" and
                      row["case_id"] == "installed_cxx_chip")
        target.update(outcome="unsupported", cases=0, assertions=0,
                      unsupported_reason="C++ sanitizer runtime unavailable")
        self.validate(unsupported)
        with self.assertRaises(verify_sdk.VerificationError):
            self.validate(unsupported, require_supported=True)

    def test_windows_version_is_bound_to_successful_dll_inspection(self) -> None:
        library = Path("glueyneo.dll")
        with mock.patch.object(check_package, "export_inspector",
                               return_value=("dumpbin", "dumpbin.exe")), \
             mock.patch.object(check_package, "run",
                               return_value=mock.Mock(stdout=WINDOWS_EXPORTS)) as inspector:
            identity = check_package.export_inspector_identity(library)
            self.assertIn("Dumper Version 14.43.34808.0", identity["version"])
            inspector.assert_called_once_with(["dumpbin.exe", "/EXPORTS", str(library)])

    def test_windows_version_rejects_unknown_and_failed_inspection(self) -> None:
        with mock.patch.object(check_package, "export_inspector",
                               return_value=("dumpbin", "dumpbin.exe")):
            with mock.patch.object(check_package, "run",
                                   return_value=mock.Mock(stdout="unrecognized inspector\n")):
                with self.assertRaisesRegex(check_package.CheckError, "unsupported version"):
                    check_package.export_inspector_identity(Path("glueyneo.dll"))
            with mock.patch.object(check_package, "run",
                                   side_effect=check_package.CheckError("inspector failed")):
                with self.assertRaisesRegex(check_package.CheckError, "inspector failed"):
                    check_package.export_inspector_identity(Path("glueyneo.dll"))

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
            check_package.EXPECTED_SHARED_EXPORTS,
        )

    def test_all_additive_save_symbols_are_required_and_public(self) -> None:
        parser = check_package.parse_windows_exports
        contract = check_package.check_export_contract
        observed = parser(WINDOWS_EXPORTS)
        self.assertEqual(9, len(check_package.SAVE_API_EXPORTS))
        self.assertTrue(check_package.SAVE_API_EXPORTS <= observed)
        self.assertTrue(check_package.SAVE_API_EXPORTS <= check_package.EXPECTED_SHARED_EXPORTS)
        for symbol in sorted(check_package.SAVE_API_EXPORTS):
            with self.subTest(symbol=symbol):
                with self.assertRaises(check_package.CheckError) as raised:
                    contract(observed - {symbol})
                self.assertIn(symbol, str(raised.exception))

    def test_installed_save_consumer_references_each_exported_function(self) -> None:
        source = check_package.SAVE_API_CONSUMER_SOURCE
        for symbol in sorted(check_package.SAVE_API_EXPORTS):
            with self.subTest(symbol=symbol):
                self.assertIn(symbol, source)
        self.assertIn("GN_STATUS_INVALID_STATE", source)
        self.assertIn("SDK_SAVE_API pass symbols=9", source)

    def test_export_contract_rejects_extra_missing_and_private_names(self) -> None:
        parser = getattr(check_package, "parse_windows_exports", None)
        contract = getattr(check_package, "check_export_contract", None)
        self.assertTrue(callable(parser) and callable(contract), "Windows export contract helpers are required")
        if not callable(parser) or not callable(contract):
            return
        expected = parser(WINDOWS_EXPORTS)
        self.assertEqual(contract(expected), sorted(expected))
        for output in (
            WINDOWS_EXPORTS.replace("gn_status_string", "gn_status_string\n         16   15 000010f0 gn_extra"),
            WINDOWS_EXPORTS.replace("         14   13 000010d0 gn_status_string\n", ""),
            WINDOWS_EXPORTS.replace("         14   13 000010d0 gn_status_string", "         14   13 000010d0 owned_cpu_secret"),
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
