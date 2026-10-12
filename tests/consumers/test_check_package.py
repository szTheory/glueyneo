#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Installed-core dependency parsing and the macOS system-path allowlist (IN-03, T-04-58)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "consumers"))
import check_package  # noqa: E402

SPACED = "/Library/Application Support/x/libfoo.dylib"
VERSION = "(compatibility version 1.0.0, current version 1.0.0)"


def otool_output(*dependencies: str) -> str:
    lines = ["/prefix/lib/glueyneo_libretro.dylib:"]
    lines += [f"\t{dependency} {VERSION}" for dependency in dependencies]
    return "\n".join(lines) + "\n"


def completed(output: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout=output)


class CoreDependencyTest(unittest.TestCase):
    def dependencies(self, *names: str) -> list[str]:
        with mock.patch.object(check_package.sys, "platform", "darwin"), \
                mock.patch.object(check_package.shutil, "which", return_value="/usr/bin/otool"), \
                mock.patch.object(check_package, "run", return_value=completed(otool_output(*names))):
            return check_package.core_dependencies(Path("core.dylib"))

    def check(self, *names: str) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-core-") as temporary:
            prefix = Path(temporary)
            core = prefix / "lib" / "glueyneo_libretro.dylib"
            core.parent.mkdir()
            core.write_bytes(b"core")
            with mock.patch.object(check_package.sys, "platform", "darwin"), \
                    mock.patch.object(check_package.shutil, "which", return_value="/usr/bin/otool"), \
                    mock.patch.object(check_package, "run", return_value=completed(otool_output(*names))):
                check_package.check_core_self_contained(prefix)

    def test_dependency_path_with_spaces_is_returned_whole(self) -> None:
        self.assertEqual(self.dependencies(SPACED, "/usr/lib/libSystem.B.dylib"),
                         [SPACED, "/usr/lib/libSystem.B.dylib"])

    def test_non_system_dependencies_are_rejected_on_macos(self) -> None:
        for name in ("@rpath/libglueyneo.dylib", "/opt/homebrew/lib/libz.1.dylib", SPACED):
            with self.subTest(name=name), self.assertRaises(check_package.CheckError) as raised:
                self.check("/usr/lib/libSystem.B.dylib", name)
            self.assertIn(raised.exception.code, {"core-dependency", "core-not-self-contained"})

    def test_system_dependencies_pass_on_macos(self) -> None:
        self.check("/usr/lib/libSystem.B.dylib",
                   "/System/Library/Frameworks/CoreFoundation.framework/Versions/A/CoreFoundation")

    def test_own_install_name_line_is_not_a_dependency(self) -> None:
        self.check("@rpath/glueyneo_libretro.dylib", "/usr/lib/libSystem.B.dylib")

    def test_unexpected_dependency_error_names_the_dependency(self) -> None:
        with self.assertRaises(check_package.CheckError) as raised:
            self.check("/opt/homebrew/lib/libz.1.dylib")
        self.assertEqual(raised.exception.code, "core-dependency")
        self.assertIn("/opt/homebrew/lib/libz.1.dylib", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
