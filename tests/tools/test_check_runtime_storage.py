#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Canned nm-output tests for the runtime writable-storage audit."""

from __future__ import annotations

import io
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_runtime_storage as audit  # noqa: E402

DARWIN = """\
0000000000001000 (__TEXT,__text) external _gn_create
0000000000002000 (__TEXT,__const) non-external _table
0000000000003000 (__DATA_CONST,__const) non-external _ro_table
0000000000004000 (__DATA,__data) external _counter
0000000000004010 (__DATA,__bss) non-external _scratch
0000000000004020 (__DATA,__common) external _tentative
                 (undefined) external _malloc
"""

LINUX = """\
0000000000001000 T gn_create
0000000000001100 t local_fn
0000000000002000 R table
0000000000002100 r ro_table
0000000000003000 D counter
0000000000003010 d local_data
0000000000003020 B zeroed
0000000000003030 b local_zero
0000000000003040 G small_data
0000000000003050 g local_small
0000000000003060 V weak_data
                 U malloc
"""


class WritableSymbolsTest(unittest.TestCase):
    def test_darwin_selects_writable_sections_only(self) -> None:
        self.assertEqual(audit.writable_symbols(DARWIN, "darwin"),
                         ["_counter", "_scratch", "_tentative"])

    def test_darwin_ignores_const_and_text(self) -> None:
        self.assertEqual(audit.writable_symbols(
            "0 (__TEXT,__const) external _a\n0 (__DATA_CONST,__const) external _b\n"
            "0 (__TEXT,__text) external _c\n", "darwin"), [])

    def test_linux_selects_writable_types_only(self) -> None:
        self.assertEqual(audit.writable_symbols(LINUX, "linux"),
                         ["counter", "local_data", "zeroed", "local_zero",
                          "small_data", "local_small", "weak_data"])

    def test_linux_ignores_text_const_and_undefined(self) -> None:
        self.assertEqual(audit.writable_symbols(
            "0 T a\n0 t b\n0 R c\n0 r d\n  U e\n", "linux"), [])


class CoverageTest(unittest.TestCase):
    """GWR-02 (T-04-56): common, small-data and thread-local storage is writable storage too."""

    def test_elf_common_and_small_data_symbols_are_reported(self) -> None:
        output = "0000000000000004 C common_var\n0000 s small_var\n0000 S small_global\n0 T f\n"
        self.assertEqual(audit.writable_symbols(output, "linux"), ["common_var", "small_var", "small_global"])

    def test_darwin_thread_local_sections_are_reported(self) -> None:
        output = (
            "0000000000005000 (__DATA,__thread_bss) non-external _tls_zero\n"
            "0000000000005010 (__DATA,__thread_data) external _tls_init\n"
            "0000000000005020 (__DATA,__thread_vars) external _tls_desc\n"
            "0000000000001000 (__TEXT,__text) external _f\n")
        self.assertEqual(audit.writable_symbols(output, "darwin"), ["_tls_zero", "_tls_init", "_tls_desc"])

    def test_parse_reports_how_many_lines_were_symbols(self) -> None:
        self.assertEqual(audit.parse_symbols(DARWIN, "darwin")[1], 7)
        self.assertEqual(audit.parse_symbols(LINUX, "linux")[1], 12)
        self.assertEqual(audit.parse_symbols("", "linux"), ([], 0))
        self.assertEqual(audit.parse_symbols("not a symbol table at all\n", "darwin"), ([], 0))


class CliTest(unittest.TestCase):
    def run_cli(self, output: str, platform: str = "darwin") -> tuple[int, str, str]:
        with mock.patch.object(audit, "run_nm", return_value=output), \
                mock.patch.object(audit, "host_platform", return_value=platform), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out, \
                mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            code = audit.main(["--nm", "nm", "/x/libruntime.a"])
        return code, out.getvalue(), err.getvalue()

    def test_fails_and_names_each_writable_symbol(self) -> None:
        code, out, err = self.run_cli(DARWIN)
        self.assertEqual(code, 1)
        text = out + err
        for name in ("_counter", "_scratch", "_tentative"):
            self.assertIn(name, text)
        self.assertIn("FAIL: writable runtime storage", text)

    def test_passes_when_clean(self) -> None:
        code, out, _ = self.run_cli("0 (__TEXT,__text) external _f\n")
        self.assertEqual(code, 0)
        self.assertIn("PASS: no writable runtime storage in libruntime.a", out)

    def test_no_symbols_parsed_is_a_failure_not_a_pass(self) -> None:
        for platform, output in (("darwin", ""), ("linux", "\n"), ("darwin", "garbled output\n")):
            with self.subTest(platform=platform, output=output):
                code, out, err = self.run_cli(output, platform)
                self.assertEqual(code, 1)
                self.assertIn("FAIL: no symbols parsed", out + err)
                self.assertNotIn("PASS", out)

    def test_empty_nm_is_unsupported_and_runs_nothing(self) -> None:
        with mock.patch.object(audit, "run_nm") as run_nm, \
                mock.patch.object(audit, "host_platform", return_value="linux"), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            code = audit.main(["--nm", "", "/x/libruntime.a"])
        self.assertEqual(code, 77)
        self.assertIn("unsupported: no nm configured", out.getvalue())
        run_nm.assert_not_called()

    def test_a_failing_nm_is_still_a_failure(self) -> None:
        with mock.patch.object(audit, "run_nm", side_effect=RuntimeError("nm failed with status 1")), \
                mock.patch.object(audit, "host_platform", return_value="linux"), \
                mock.patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(audit.main(["--nm", "nm", "/x/libruntime.a"]), 1)

    def test_windows_is_unsupported_with_skip_code(self) -> None:
        code, out, _ = self.run_cli("", "windows")
        self.assertEqual(code, 77)
        self.assertIn("unsupported", out)


if __name__ == "__main__":
    unittest.main()
