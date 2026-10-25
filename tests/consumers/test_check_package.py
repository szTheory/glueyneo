#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Installed-core dependency parsing and the macOS system-path allowlist (IN-03, T-04-58)."""

from __future__ import annotations

from pathlib import Path
import shutil
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


class ConsumerVersionTest(unittest.TestCase):
    def test_staged_consumer_requires_exact_manifest_version_after_bump(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-version-") as temporary:
            work = Path(temporary)
            source = work / "source"
            source.mkdir()
            (source / ".release-please-manifest.json").write_text('{".":"9.8.7"}\n')
            consumer = source / "tests/consumers"
            consumer.mkdir(parents=True)
            shutil.copy2(ROOT / "tests/consumers/CMakeLists.txt", consumer / "CMakeLists.txt")
            shutil.copy2(ROOT / "tests/consumers/header.cpp", consumer / "header.cpp")
            example = source / "examples"
            example.mkdir()
            shutil.copy2(ROOT / "examples/diagnostic.c", example / "diagnostic.c")
            staged = work / "relocated-consumer"
            with mock.patch.object(check_package, "ROOT", source):
                check_package.stage_consumer_project(staged)
            shutil.rmtree(source)

            package = work / "package"
            package.mkdir()
            (package / "GlueyneoConfig.cmake").write_text(
                "add_library(Glueyneo::glueyneo INTERFACE IMPORTED)\n")
            for version, succeeds in (("9.8.7", True), ("9.8.8", False)):
                with self.subTest(installed_version=version):
                    version_script = work / "version.cmake"
                    version_script.write_text(
                        "include(CMakePackageConfigHelpers)\n"
                        f'write_basic_package_version_file("{(package / "GlueyneoConfigVersion.cmake").as_posix()}" '
                        f'VERSION "{version}" COMPATIBILITY SameMajorVersion ARCH_INDEPENDENT)\n')
                    subprocess.run(["cmake", "-P", str(version_script)], check=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                    result = subprocess.run(
                        ["cmake", "-S", str(staged), "-B", str(work / f"build-{version}"),
                         f"-DGlueyneo_DIR={package}", "-DGLUEYNEO_CONSUMER_C_SOURCE=diagnostic.c"],
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        check=False, timeout=60)
                    self.assertEqual(result.returncode == 0, succeeds, result.stdout)
                    if not succeeds:
                        self.assertIn('requested version "9.8.7"', result.stdout)


if __name__ == "__main__":
    unittest.main()
