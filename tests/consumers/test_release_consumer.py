#!/usr/bin/env python3
"""Release archive and single-version-source acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ReleaseConsumerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="glueyneo-release-red-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        shutil.copytree(
            ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "build", "__pycache__", ".planning"),
        )

    def configure(self) -> subprocess.CompletedProcess[str]:
        build = Path(self.temp.name) / "build"
        return subprocess.run(
            ["cmake", "-S", str(self.root), "-B", str(build), "-DBUILD_TESTING=OFF"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=60,
        )

    def test_root_manifest_controls_cmake_and_package_version(self) -> None:
        (self.root / ".release-please-manifest.json").write_text(
            '{".": "9.8.7"}\n', encoding="utf-8"
        )
        result = self.configure()
        self.assertEqual(result.returncode, 0, result.stdout)
        cache = (Path(self.temp.name) / "build" / "CMakeCache.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("Glueyneo_VERSION:STATIC=9.8.7", cache)
        version_file = Path(self.temp.name) / "build" / "GlueyneoConfigVersion.cmake"
        self.assertTrue(version_file.is_file(), result.stdout)
        self.assertIn("PACKAGE_VERSION \"9.8.7\"", version_file.read_text(encoding="utf-8"))

    def test_malformed_manifest_fails_before_project_configuration(self) -> None:
        (self.root / ".release-please-manifest.json").write_text(
            '{".": "not-a-version"}\n', encoding="utf-8"
        )
        result = self.configure()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("release-please", result.stdout.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
