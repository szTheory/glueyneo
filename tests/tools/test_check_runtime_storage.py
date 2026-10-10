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

    def test_windows_is_unsupported_with_skip_code(self) -> None:
        code, out, _ = self.run_cli("", "windows")
        self.assertEqual(code, 77)
        self.assertIn("unsupported", out)


if __name__ == "__main__":
    unittest.main()
