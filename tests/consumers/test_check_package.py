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
            for name in (
                "tests/consumers/CMakeLists.txt", "tests/consumers/header.cpp",
                "tests/consumers/sound_consumer.c", "examples/diagnostic.c",
                "examples/continuation.c", "examples/persistence.c",
                "examples/persistence_host.c", "examples/persistence_host.h",
                "tests/fixture/public_sound_guest.c",
                "tests/fixture/public_persistence_guest.c",
            ):
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, target)
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
                        'include(CMakePackageConfigHelpers)\n'
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


class DocumentationClosureTest(unittest.TestCase):
    def source_tree(self, omitted: str | None = None) -> Path:
        self.temporary = tempfile.TemporaryDirectory(prefix="glueyneo-doc-closure-")
        self.addCleanup(self.temporary.cleanup)
        source = Path(self.temporary.name) / "source"
        for relative in (
            "cmake", "include", "src", "experiments/owned_cpu",
            "third_party/libretro", "third_party/zlib", "third_party/chips",
            "third_party/ymfm", "third_party/unity",
        ):
            (source / relative).mkdir(parents=True, exist_ok=True)
        files = (
            "CMakeLists.txt", "LICENSE", ".release-please-manifest.json",
            "docs/sdk-examples.md", "tools/diagnostic/main.c",
            "docs/native-state.md", "docs/native-save.md", "docs/frontend-continuation.md",
            "docs/testing.md", "docs/ownership-and-errors.md",
            "tests/sdk/guest_fixture.c", "tests/sdk/guest_fixture.h",
            "tests/consumers/CMakeLists.txt", "tests/consumers/header.cpp",
            "tests/consumers/sound_consumer.c", "tests/fixture/public_sound_guest.c",
            "tests/fixture/public_save_guest.c",
            "examples/diagnostic.c", "examples/continuation.c",
            "examples/persistence.c", "examples/persistence_host.c",
            "examples/persistence_host.h", "tests/fixture/public_persistence_guest.c",
            "third_party/libretro/NOTICE.md", "third_party/zlib/LICENSE",
            "third_party/chips/NOTICE.md", "third_party/ymfm/LICENSE",
            "third_party/ymfm/NOTICE.md", "third_party/unity/LICENSE.txt",
        )
        for relative in files:
            if relative == omitted:
                continue
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture: {relative}\n", encoding="utf-8")
        return source

    def stage(self, source: Path) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-doc-stage-") as temporary, \
                mock.patch.object(check_package, "ROOT", source):
            check_package.stage_documentation_project(Path(temporary) / "staged")

    def test_missing_example_helper_fails_with_a_named_reason(self) -> None:
        source = self.source_tree("examples/persistence_host.c")
        with self.assertRaisesRegex(check_package.CheckError, "missing example helper"):
            self.stage(source)

    def test_missing_recipe_fails_with_a_named_reason(self) -> None:
        source = self.source_tree("tests/fixture/public_persistence_guest.c")
        with self.assertRaisesRegex(check_package.CheckError, "missing recipe"):
            self.stage(source)

    def test_missing_notice_fails_with_a_named_reason(self) -> None:
        source = self.source_tree("third_party/ymfm/LICENSE")
        with self.assertRaisesRegex(check_package.CheckError, "missing notice"):
            self.stage(source)


if __name__ == "__main__":
    unittest.main()
