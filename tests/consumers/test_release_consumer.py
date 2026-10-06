#!/usr/bin/env python3
"""Release archive and single-version-source acceptance tests."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import release_manifest


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

    def test_release_archive_rebuilds_offline_and_relocates_consumers(self) -> None:
        repo = Path(self.temp.name) / "repo"
        subprocess.run(
            ["git", "clone", "--quiet", str(ROOT), str(repo)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, text=True,
            stdout=subprocess.PIPE, timeout=10,
        ).stdout.strip()
        output = Path(self.temp.name) / "artifacts"
        result = subprocess.run(
            [sys.executable, str(repo / "tools/release_manifest.py"), "build",
             "--repo", str(repo), "--commit", commit, "--output-dir", str(output)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=600,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        record = json.loads(result.stdout)
        source_archive = output / record["source"]
        sdk_archive = output / record["sdk"]
        self.assertEqual(hashlib.sha256(source_archive.read_bytes()).hexdigest(), record["source_sha256"])
        self.assertEqual(hashlib.sha256(sdk_archive.read_bytes()).hexdigest(), record["sdk_sha256"])

        source_extract = Path(self.temp.name) / "source-extracted"
        release_manifest.safe_extract(source_archive, source_extract)
        source_root = source_extract / "glueyneo-source"
        source_build = Path(self.temp.name) / "offline-build"
        configure = subprocess.run(
            ["cmake", "-S", str(source_root), "-B", str(source_build),
             "-DBUILD_TESTING=OFF", "-DGLUEYNEO_BUILD_TESTS=OFF",
             "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=120,
        )
        self.assertEqual(configure.returncode, 0, configure.stdout)
        build = subprocess.run(
            ["cmake", "--build", str(source_build), "--parallel", "2"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=180,
        )
        self.assertEqual(build.returncode, 0, build.stdout)

        sdk_extract = Path(self.temp.name) / "sdk-extracted"
        release_manifest.safe_extract(sdk_archive, sdk_extract)
        sdk_root = sdk_extract / f"glueyneo-sdk-{record['version']}"
        manifest = json.loads((sdk_root / "artifact-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_commit"], commit)
        self.assertEqual(manifest["version"], record["version"])
        self.assertEqual(
            manifest["source_archive"]["sha256"],
            hashlib.sha256(source_archive.read_bytes()).hexdigest(),
        )
        for asset in manifest["assets"]:
            asset_path = sdk_root / asset["path"]
            self.assertTrue(asset_path.is_file(), asset["path"])
            self.assertEqual(hashlib.sha256(asset_path.read_bytes()).hexdigest(), asset["sha256"])
            self.assertEqual(asset_path.stat().st_size, asset["size"])
        cmake_sources = [sdk_root / "README.md"]
        cmake_sources.extend(sorted((sdk_root / "static").rglob("*.cmake")))
        cmake_sources.extend(sorted((sdk_root / "shared").rglob("*.cmake")))
        for path in cmake_sources:
            self.assertNotIn(str(repo), path.read_text(encoding="utf-8"))
            self.assertNotIn(str(source_root), path.read_text(encoding="utf-8"))
        source_cmake = (source_root / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertNotRegex(
            source_cmake,
            r"FetchContent_Declare|ExternalProject_Add|CPMAddPackage|file\s*\(\s*DOWNLOAD|COMMAND\s+(?:curl|wget)\b",
        )
        self.assertIn("static", {path.name for path in sdk_root.iterdir() if path.is_dir()})
        self.assertIn("shared", {path.name for path in sdk_root.iterdir() if path.is_dir()})

        moved_sdk = Path(self.temp.name) / "relocated" / "sdk"
        moved_sdk.parent.mkdir()
        shutil.move(str(sdk_root), moved_sdk)
        disabled_repo = repo.with_name("repo-unavailable")
        disabled_source = source_root.with_name("source-unavailable")
        disabled_build = source_build.with_name("build-unavailable")
        repo.rename(disabled_repo)
        source_root.rename(disabled_source)
        source_build.rename(disabled_build)
        for variant in ("static", "shared"):
            prefix = moved_sdk / variant
            fixture = prefix / "share/glueyneo/diagnostic-original-a.bin"
            runner = next((prefix / "bin").glob("glueyneo-diagnostic*"))
            diagnostic = subprocess.run(
                [str(runner), "--check-fixture", str(fixture)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False, timeout=30,
            )
            self.assertEqual(diagnostic.returncode, 0, diagnostic.stdout)
            consumer_source = moved_sdk / "consumer-example/source"
            consumer_build = Path(self.temp.name) / f"consumer-{variant}"
            configure = subprocess.run(
                ["cmake", "-S", str(consumer_source), "-B", str(consumer_build),
                 f"-DGlueyneo_DIR={prefix / 'lib/cmake/Glueyneo'}",
                 "-DGLUEYNEO_CONSUMER_C_SOURCE=diagnostic.c", "-DCMAKE_BUILD_TYPE=Release"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False, timeout=60,
            )
            self.assertEqual(configure.returncode, 0, configure.stdout)
            build = subprocess.run(
                ["cmake", "--build", str(consumer_build), "--parallel", "2"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False, timeout=120,
            )
            self.assertEqual(build.returncode, 0, build.stdout)
            consumer = subprocess.run(
                [str(consumer_build / "glueyneo-installed-c"), str(fixture)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False, timeout=30,
            )
            self.assertEqual(consumer.returncode, 0, consumer.stdout)
            self.assertIn('"outcome":"pass"', consumer.stdout)
        self.assertFalse(repo.exists())
        self.assertFalse(source_root.exists())
        self.assertFalse(source_build.exists())
        self.assertTrue(disabled_repo.exists())
        self.assertTrue(disabled_source.exists())
        self.assertTrue(disabled_build.exists())

    def test_archive_extraction_rejects_traversal_and_links(self) -> None:
        for member in (
            tarfile.TarInfo("../outside"),
            tarfile.TarInfo("glueyneo-source/link"),
        ):
            archive = Path(self.temp.name) / f"unsafe-{len(list(Path(self.temp.name).glob('unsafe-*')))}.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                if member.name.endswith("link"):
                    member.type = tarfile.SYMTYPE
                    member.linkname = "../../outside"
                    stream.addfile(member)
                else:
                    body = b"unsafe"
                    member.size = len(body)
                    stream.addfile(member, io.BytesIO(body))
            with self.assertRaises(release_manifest.ReleaseError):
                release_manifest.safe_extract(archive, Path(self.temp.name) / "unsafe-extract")


if __name__ == "__main__":
    unittest.main(verbosity=2)
