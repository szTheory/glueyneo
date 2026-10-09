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
import platform
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import release_manifest
import release_state


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

    def test_downloaded_release_requires_exact_bytes_and_complete_archive_set(self) -> None:
        download = Path(self.temp.name) / "downloaded"
        download.mkdir()
        contents = {
            "glueyneo-source-0.1.0.tar.gz": b"source archive",
            "glueyneo-sdk-0.1.0-linux-x86_64.tar.gz": b"linux archive",
            "glueyneo-sdk-0.1.0-macos-arm64.tar.gz": b"mac archive",
            "glueyneo-sdk-0.1.0-windows-x86_64.tar.gz": b"windows archive",
        }
        rows = []
        for name, data in contents.items():
            (download / name).write_bytes(data)
            rows.append({"name": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        source_commit = "a" * 40
        manifest = {"schema_version": 1, "tag": "v0.1.0", "source_commit": source_commit,
                    "version": "0.1.0", "assets": rows}
        staged_manifest = Path(self.temp.name) / "expected-release-manifest.json"
        staged_manifest.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
        (download / "release-manifest.json").write_bytes(staged_manifest.read_bytes())

        result = release_state.validate_downloaded_assets(download, staged_manifest)
        self.assertEqual(result["outcome"], "pass")
        self.assertEqual(result["source_commit"], source_commit)

        (download / "glueyneo-sdk-0.1.0-linux-x86_64.tar.gz").write_bytes(b"replaced")
        with self.assertRaises(release_state.ReleaseStateError):
            release_state.validate_downloaded_assets(download, staged_manifest)
        (download / "glueyneo-sdk-0.1.0-linux-x86_64.tar.gz").write_bytes(
            contents["glueyneo-sdk-0.1.0-linux-x86_64.tar.gz"])
        (download / "unexpected.zip").write_bytes(b"extra")
        with self.assertRaises(release_state.ReleaseStateError):
            release_state.validate_downloaded_assets(download, staged_manifest)


def verify_downloaded_release(download: Path, staged_manifest: Path, *, commit: str, version: str,
                              platform_name: str | None = None) -> dict[str, object]:
    """Rebuild source offline and execute consumers from this host's downloaded SDK bytes."""
    identity = release_state.validate_downloaded_assets(download, staged_manifest)
    if identity["source_commit"] != commit or identity["version"] != version:
        raise RuntimeError("downloaded release identity differs from the tested commit and version")
    source_archive = download / f"glueyneo-source-{version}.tar.gz"
    os_name = {"darwin": "macos", "windows": "windows"}.get(platform.system().lower(), platform.system().lower())
    machine_name = {"amd64": "x86_64", "aarch64": "arm64", "x86-64": "x86_64"}.get(
        platform.machine().lower(), platform.machine().lower())
    platform_name = platform_name or f"{os_name}-{machine_name}"
    sdk_archive = download / f"glueyneo-sdk-{version}-{platform_name}.tar.gz"
    cmake = shutil.which("cmake")
    if cmake is None:
        raise RuntimeError("CMake is required for downloaded release verification")

    def run(argv: list[str], *, cwd: Path, timeout: int = 300) -> str:
        try:
            return release_manifest.run(argv, cwd=cwd, timeout=timeout)
        except release_manifest.ReleaseError as error:
            raise RuntimeError(str(error)) from error

    with tempfile.TemporaryDirectory(prefix="glueyneo-downloaded-consumer-") as temp_name:
        work = Path(temp_name)
        source_dir = work / "source"
        release_manifest.safe_extract(source_archive, source_dir)
        source_root = source_dir / "glueyneo-source"
        build = work / "offline-build"
        run([cmake, "-S", str(source_root), "-B", str(build), "-DBUILD_TESTING=OFF",
             "-DGLUEYNEO_BUILD_TESTS=OFF", "-DCMAKE_BUILD_TYPE=Release",
             "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"], cwd=source_root)
        run([cmake, "--build", str(build), "--config", "Release", "--parallel", "2"], cwd=source_root)

        sdk_dir = work / "sdk"
        release_manifest.safe_extract(sdk_archive, sdk_dir)
        sdk_root = sdk_dir / f"glueyneo-sdk-{version}"
        for variant in ("static", "shared"):
            prefix = sdk_root / variant
            fixture = prefix / "share/glueyneo/diagnostic-original-a.bin"
            runner = next((prefix / "bin").glob("glueyneo-diagnostic*"))
            diagnostic = subprocess.run([str(runner), "--check-fixture", str(fixture)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        check=False, timeout=30)
            if diagnostic.returncode:
                raise RuntimeError(f"relocated {variant} diagnostic failed: {diagnostic.stdout[-4000:]}")
            consumer_source = sdk_root / "consumer-example/source"
            consumer_cmake = consumer_source / "CMakeLists.txt"
            consumer_text = consumer_cmake.read_text(encoding="utf-8")
            consumer_text = re.sub(r"find_package\(Glueyneo\s+[0-9A-Za-z.+-]+\s+EXACT\s+CONFIG\s+REQUIRED\)",
                                   "find_package(Glueyneo " + version + " EXACT CONFIG REQUIRED)", consumer_text)
            consumer_cmake.write_text(consumer_text, encoding="utf-8")
            consumer_build = work / f"consumer-{variant}"
            run([cmake, "-S", str(consumer_source), "-B", str(consumer_build),
                 f"-DGlueyneo_DIR={prefix / 'lib/cmake/Glueyneo'}",
                 "-DGLUEYNEO_CONSUMER_C_SOURCE=diagnostic.c", "-DCMAKE_BUILD_TYPE=Release"], cwd=work)
            run([cmake, "--build", str(consumer_build), "--config", "Release", "--parallel", "2"], cwd=work)
            exe_dir = consumer_build / "Release" if platform.system() == "Windows" else consumer_build
            consumer_exe = exe_dir / ("glueyneo-installed-c.exe" if platform.system() == "Windows" else "glueyneo-installed-c")
            process_env = dict(__import__("os").environ)
            binary_dir = str(prefix / "bin")
            process_env["PATH"] = binary_dir + __import__("os").pathsep + process_env.get("PATH", "")
            consumer = subprocess.run([str(consumer_exe), str(fixture)],
                                      text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      check=False, timeout=30, env=process_env)
            if consumer.returncode or '"outcome":"pass"' not in consumer.stdout:
                raise RuntimeError(f"relocated {variant} SDK consumer failed: {consumer.stdout[-4000:]}")
        return {"outcome": "pass", "source_commit": commit, "version": version,
                "platform": platform_name, "variants": ["static", "shared"], "downloaded_byte_verification": "pass",
                "offline_source_rebuild": "pass", "relocated_consumer": "pass"}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify-downloaded":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--verify-downloaded", action="store_true")
        parser.add_argument("--directory", type=Path, required=True)
        parser.add_argument("--manifest", type=Path, required=True)
        parser.add_argument("--commit", required=True)
        parser.add_argument("--version", required=True)
        parser.add_argument("--platform")
        args = parser.parse_args()
        print(json.dumps(verify_downloaded_release(args.directory, args.manifest,
                                                   commit=args.commit, version=args.version,
                                                   platform_name=args.platform),
                         sort_keys=True, separators=(",", ":")))
    else:
        unittest.main(verbosity=2)
