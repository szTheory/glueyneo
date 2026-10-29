#!/usr/bin/env python3
"""Release archive and single-version-source acceptance tests."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import release_manifest
import release_state
import public_content


ROOT = Path(__file__).resolve().parents[2]


def copy_release_fixture(source: Path, destination: Path) -> None:
    """Copy working bytes of tracked distributable paths, excluding local data."""
    source = source.resolve(strict=True)
    paths = subprocess.run(
        ["git", "ls-files", "-z", "--", *release_manifest.SOURCE_PATHS],
        cwd=source, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=30,
    ).stdout.split(b"\0")
    destination.mkdir(parents=True)
    for encoded in paths:
        if not encoded:
            continue
        relative = Path(os.fsdecode(encoded))
        original = source / relative
        if (relative.is_absolute() or ".." in relative.parts
                or not original.resolve(strict=True).is_relative_to(source)
                or any(path.is_symlink() for path in (original, *original.parents)
                       if path != source and source in path.parents)
                or not original.is_file()):
            raise release_manifest.ReleaseError("release fixture requires contained regular source files")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)


class ReleaseFixtureTests(unittest.TestCase):
    def assert_source_directory_alias_rejected(self, *, external: bool) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-fixture-alias-") as temp:
            root = Path(temp).resolve()
            source = root / "repo"
            original = source / "src"
            original.mkdir(parents=True)
            (original / "owned.c").write_text("int owned;\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            subprocess.run(["git", "add", "src/owned.c"], cwd=source, check=True)
            target = root / "outside" if external else source / "actual-src"
            original.rename(target)
            copied = root / "copied"

            def rejected() -> None:
                with mock.patch.object(shutil, "copy2", wraps=shutil.copy2) as copy:
                    with self.assertRaisesRegex(release_manifest.ReleaseError, "contained regular"):
                        copy_release_fixture(source, copied)
                    copy.assert_not_called()
                self.assertFalse((copied / "src/owned.c").exists())

            try:
                original.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                # Windows runners may lack symlink privilege. Model the same
                # resolved escape/ancestor link while retaining ordinary bytes
                # at the source path, so the old leaf-only check still fails.
                original.mkdir()
                (original / "owned.c").write_text("int owned;\n", encoding="utf-8")
                real_resolve = Path.resolve
                real_is_symlink = Path.is_symlink

                def resolve(path: Path, *args, **kwargs):
                    if path == original / "owned.c":
                        return target / "owned.c"
                    return real_resolve(path, *args, **kwargs)

                def is_symlink(path: Path):
                    return path == original or real_is_symlink(path)

                with mock.patch.object(Path, "resolve", resolve), \
                        mock.patch.object(Path, "is_symlink", is_symlink):
                    rejected()
            else:
                rejected()

    def test_source_directory_symlink_cannot_escape_checkout(self) -> None:
        self.assert_source_directory_alias_rejected(external=True)

    def test_source_directory_symlink_cannot_alias_tracked_paths(self) -> None:
        self.assert_source_directory_alias_rejected(external=False)

    def test_only_tracked_distributable_files_are_copied(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-fixture-copy-") as temp:
            root = Path(temp)
            source = root / "repo"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            files = {
                "CMakeLists.txt": "project(synthetic C)\n",
                ".release-please-manifest.json": '{".":"1.2.3"}\n',
                "src/owned.c": "int original;\n",
                "local/private.bin": "private local input\n",
                ".env.local": "private configuration\n",
                "src/untracked-private.bin": "private untracked input\n",
                ".gitignore": "src/untracked-private.bin\n",
                ".planning/private.md": "private planning\n",
            }
            for relative, data in files.items():
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(data, encoding="utf-8")
            subprocess.run(
                ["git", "add", "CMakeLists.txt", ".release-please-manifest.json",
                 "src/owned.c", "local/private.bin", ".env.local", ".planning/private.md"],
                cwd=source, check=True,
            )
            # Exercise working-tree edits, not just the bytes stored in Git.
            (source / "src/owned.c").write_text("int current;\n", encoding="utf-8")
            copied = root / "source"
            copy_release_fixture(source, copied)
            self.assertEqual(
                {path.relative_to(copied).as_posix() for path in copied.rglob("*") if path.is_file()},
                {"CMakeLists.txt", ".release-please-manifest.json", "src/owned.c"},
            )
            self.assertEqual((copied / "src/owned.c").read_text(), "int current;\n")


class ReleaseWorkspaceTests(unittest.TestCase):
    def test_explicit_parent_precedes_runner_temp_and_runner_precedes_default(self):
        with tempfile.TemporaryDirectory(prefix="glueyneo-workspace-test-") as temp:
            root = Path(temp)
            explicit, runner = root / "explicit", root / "runner"
            explicit.mkdir()
            runner.mkdir()
            with mock.patch.dict(os.environ, {"RUNNER_TEMP": str(runner)}), \
                    mock.patch.object(release_manifest.platform, "system", return_value="Linux"):
                self.assertEqual(release_manifest.workspace_parent(explicit), explicit.resolve())
                self.assertEqual(release_manifest.workspace_parent(), runner.resolve())
            with mock.patch.dict(os.environ, {"RUNNER_TEMP": ""}), \
                    mock.patch.object(tempfile, "gettempdir", return_value=str(root)), \
                    mock.patch.object(release_manifest.platform, "system", return_value="Linux"):
                self.assertEqual(release_manifest.workspace_parent(), root.resolve())

    def test_parent_must_be_absolute_existing_directory(self):
        with self.assertRaisesRegex(release_manifest.ReleaseError, "absolute"):
            release_manifest.workspace_parent(Path("relative-workspace"))
        with tempfile.TemporaryDirectory(prefix="glueyneo-workspace-test-") as temp:
            root = Path(temp)
            with self.assertRaisesRegex(release_manifest.ReleaseError, "directory"):
                release_manifest.workspace_parent(root / "missing")
            file = root / "file"
            file.write_text("not a directory", encoding="ascii")
            with self.assertRaisesRegex(release_manifest.ReleaseError, "directory"):
                release_manifest.workspace_parent(file)

    def test_windows_rejects_resolved_profile_parents_including_runner_temp(self):
        # Model resolved Windows paths on every test host; links must be checked
        # after resolution, and no rejected identity may appear in the error.
        selected = Path(tempfile.gettempdir())
        for path in ("C:/" + "Users/synthetic/AppData/Local/Temp", "c:/USERS",
                     "D:/" + "Documents and Settings/synthetic/temp",
                     "//?/C:/" + "Users/synthetic/temp"):
            with self.subTest(path=path):
                resolved = mock.Mock(spec=Path)
                resolved.is_dir.return_value = True
                resolved.as_posix.return_value = path
                with mock.patch.object(release_manifest.platform, "system", return_value="Windows"), \
                        mock.patch.object(Path, "resolve", return_value=resolved), \
                        mock.patch.dict(os.environ, {"RUNNER_TEMP": str(selected)}):
                    with self.assertRaisesRegex(release_manifest.ReleaseError, "outside user profiles") as caught:
                        release_manifest.workspace_parent()
                    self.assertNotIn(path, str(caught.exception))

    def test_windows_accepts_neutral_parent_and_profile_prefix_neighbor(self):
        selected = Path(tempfile.gettempdir())
        for path in ("D:/runner/temp", "C:/UsersBackup/temp", "//?/D:/runner/temp"):
            with self.subTest(path=path):
                resolved = mock.Mock(spec=Path)
                resolved.is_dir.return_value = True
                resolved.as_posix.return_value = path
                with mock.patch.object(release_manifest.platform, "system", return_value="Windows"), \
                        mock.patch.object(Path, "resolve", return_value=resolved):
                    self.assertIs(release_manifest.workspace_parent(selected), resolved)


class ArchiveMemberBoundaryTests(unittest.TestCase):
    @staticmethod
    def member(name: str, size: int = 0) -> tarfile.TarInfo:
        result = tarfile.TarInfo(name)
        result.size = size
        return result

    def test_member_count_limit_accepts_limit_minus_one_and_limit(self) -> None:
        release_manifest.validate_member_info(
            [self.member("a"), self.member("b")], max_members=3)
        release_manifest.validate_member_info(
            [self.member("a"), self.member("b"), self.member("c")], max_members=3)
        with self.assertRaisesRegex(release_manifest.ReleaseError, "member count"):
            release_manifest.validate_member_info(
                [self.member("a"), self.member("b"), self.member("c"), self.member("d")],
                max_members=3)

    def test_member_extent_limit_accepts_limit_minus_one_and_limit(self) -> None:
        release_manifest.validate_member_info([self.member("below", 7)], max_member_bytes=8)
        release_manifest.validate_member_info([self.member("at", 8)], max_member_bytes=8)
        with self.assertRaisesRegex(release_manifest.ReleaseError, "per-file size limit"):
            release_manifest.validate_member_info([self.member("above", 9)], max_member_bytes=8)

    def test_expanded_total_limit_accepts_limit_minus_one_and_limit(self) -> None:
        release_manifest.validate_member_info(
            [self.member("a", 3), self.member("b", 4)],
            max_member_bytes=8, max_archive_bytes=8)
        release_manifest.validate_member_info(
            [self.member("a", 3), self.member("b", 5)],
            max_member_bytes=8, max_archive_bytes=8)
        with self.assertRaisesRegex(release_manifest.ReleaseError, "total uncompressed size"):
            release_manifest.validate_member_info(
                [self.member("a", 4), self.member("b", 5)],
                max_member_bytes=8, max_archive_bytes=8)


class ReleaseManifestBoundaryTests(unittest.TestCase):
    VERSION = "0.1.0"
    COMMIT = "a" * 40
    DIGEST = "b" * 64

    def expected_inventory(self, size: int = 7) -> dict[str, dict[str, object]]:
        names = release_state.required_archive_names(self.VERSION) | {"release-manifest.json"}
        return {name: {"size": size, "sha256": self.DIGEST} for name in names}

    def valid_release(self, size: int = 7) -> dict[str, object]:
        return {
            "tag_name": f"v{self.VERSION}", "tag_commit": self.COMMIT,
            "target_commitish": self.COMMIT, "draft": True, "prerelease": False,
            "assets": [
                {"name": name, "size": size, "digest": self.DIGEST, "state": "uploaded"}
                for name in sorted(self.expected_inventory(size))
            ],
        }

    def validate(self, release: dict[str, object], *, size: int = 7,
                 commit: str | None = None) -> dict[str, object]:
        return release_state.validate_release(
            release, expected_tag=f"v{self.VERSION}", expected_version=self.VERSION,
            expected_commit=commit or self.COMMIT, manifest_version=self.VERSION,
            expected_assets=self.expected_inventory(size),
        )

    def test_release_rejects_each_nonobject_asset_and_mixed_rows(self) -> None:
        for malformed in (None, "not-an-object", [], 7):
            with self.subTest(row=malformed):
                release = self.valid_release()
                release["assets"].append(malformed)
                result = self.validate(release)
                self.assertEqual(result["error"], "release contains a malformed asset")

    def test_release_sizes_are_exact_integers_above_float_precision_boundary(self) -> None:
        size = 2**53 + 1
        release = self.valid_release(size)
        self.assertEqual(self.validate(release, size=size)["status"], "ready")
        release["assets"][0]["size"] += 1
        result = self.validate(release, size=size)
        self.assertEqual(result["error"], "existing release asset bytes differ from staged bytes")

    def test_release_requires_full_digest_and_full_commit_identity(self) -> None:
        release = self.valid_release()
        release["assets"][0]["digest"] = self.DIGEST[:-1] + "c"
        self.assertEqual(self.validate(release)["error"],
                         "existing release asset bytes differ from staged bytes")
        release = self.valid_release()
        release["tag_commit"] = self.COMMIT[:-1] + "c"
        self.assertEqual(self.validate(release)["error"],
                         "release tag does not target the tested versioned commit")

    def test_download_manifest_rejects_nonobject_and_mixed_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-manifest-shape-") as temporary:
            root = Path(temporary)
            names = sorted(release_state.required_archive_names(self.VERSION))
            rows = [{"name": name, "size": 1, "sha256": self.DIGEST} for name in names]
            manifest_path = root / "manifest.json"
            for malformed in (None, "not-an-object", [], 7):
                manifest = {"schema_version": 1, "tag": f"v{self.VERSION}",
                            "source_commit": self.COMMIT, "version": self.VERSION,
                            "assets": [*rows, malformed]}
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.subTest(row=malformed), self.assertRaisesRegex(
                        release_state.ReleaseStateError, "manifest row is malformed"):
                    release_state.validate_downloaded_assets(root, manifest_path)

    def test_boolean_schema_version_is_not_integer_schema_version(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-manifest-schema-") as temporary:
            root = Path(temporary)
            manifest = {"schema_version": True, "tag": f"v{self.VERSION}",
                        "source_commit": self.COMMIT, "version": self.VERSION,
                        "assets": [{"name": name, "size": 1, "sha256": self.DIGEST}
                                   for name in sorted(release_state.required_archive_names(self.VERSION))]}
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(release_state.ReleaseStateError, "identity is malformed"):
                release_state.validate_downloaded_assets(root, manifest_path)
            with self.assertRaisesRegex(release_state.ReleaseStateError, "identity is malformed"):
                release_state.expected_api_assets(manifest_path)


def packaged_record(output: str, marker: str, *, role: str | None = None) -> dict[str, object]:
    rows = [line[len(marker):] for line in output.splitlines() if line.startswith(marker)]
    if len(rows) != 1:
        raise release_manifest.ReleaseError(f"expected one {marker.strip()} result record, found {len(rows)}")
    try:
        record = json.loads(rows[0])
    except json.JSONDecodeError as error:
        raise release_manifest.ReleaseError(f"malformed {marker.strip()} result record") from error
    if (not isinstance(record, dict) or type(record.get("schema_version")) is not int
            or record["schema_version"] != 1):
        raise release_manifest.ReleaseError(f"invalid {marker.strip()} result record")
    if role is not None and record.get("role") != role:
        raise release_manifest.ReleaseError(f"unexpected role in {marker.strip()} result record")
    return record


_PACKAGED_CONSUMER_TARGETS = frozenset({
    "glueyneo-installed-c",
    "glueyneo-installed-cxx",
    "glueyneo-installed-sound",
    "glueyneo-installed-continuation",
    "glueyneo-installed-persistence",
})


def packaged_consumer_executable(consumer_build: Path, target: str) -> Path:
    """Resolve a staged consumer target at its declared config-independent output root."""
    if target not in _PACKAGED_CONSUMER_TARGETS:
        raise release_manifest.ReleaseError("unknown packaged consumer target")
    suffix = ".exe" if os.name == "nt" else ""
    build_root = consumer_build.resolve(strict=True)
    executable = build_root / f"{target}{suffix}"
    if executable.is_symlink():
        raise release_manifest.ReleaseError(
            f"packaged consumer target is not a direct build output: {target}"
        )
    if executable.is_file():
        resolved = executable.resolve(strict=True)
        if resolved.parent != build_root:
            raise release_manifest.ReleaseError(
                f"packaged consumer target resolved outside its output root: {target}"
            )
        return resolved
    release_executable = build_root / "Release" / f"{target}{suffix}"
    if release_executable.is_file():
        raise release_manifest.ReleaseError(
            f"packaged consumer target used a config-specific output directory: {target}"
        )
    raise release_manifest.ReleaseError(f"packaged SDK omitted consumer executable: {target}")


class PackagedConsumerExecutableTests(unittest.TestCase):
    def test_target_symlink_cannot_select_an_outside_executable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-consumer-symlink-") as temporary:
            root = Path(temporary)
            build = root / "consumer-build"
            outside = root / "outside"
            build.mkdir()
            outside.mkdir()
            suffix = ".exe" if os.name == "nt" else ""
            executable = build.resolve() / f"glueyneo-installed-c{suffix}"
            external = outside.resolve() / executable.name
            external.write_bytes(b"outside executable marker")
            try:
                executable.symlink_to(external)
            except (OSError, NotImplementedError):
                # Model a Windows symlink when the current account lacks the
                # privilege; the production path must still reject it before launch.
                executable.write_bytes(b"modeled symlink target")
                original_is_symlink = Path.is_symlink

                def is_symlink(path: Path) -> bool:
                    return path == executable or original_is_symlink(path)

                with mock.patch.object(Path, "is_symlink", is_symlink):
                    with self.assertRaisesRegex(
                            release_manifest.ReleaseError, "not a direct build output"):
                        packaged_consumer_executable(build, "glueyneo-installed-c")
            else:
                with self.assertRaisesRegex(
                        release_manifest.ReleaseError, "not a direct build output"):
                    packaged_consumer_executable(build, "glueyneo-installed-c")

    def test_resolved_target_must_remain_at_the_staged_output_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-consumer-alias-") as temporary:
            root = Path(temporary)
            build = root / "consumer-build"
            outside = root / "outside"
            build.mkdir()
            outside.mkdir()
            suffix = ".exe" if os.name == "nt" else ""
            executable = build.resolve() / f"glueyneo-installed-c{suffix}"
            executable.write_bytes(b"regular staged output")
            resolved_elsewhere = outside.resolve() / executable.name
            resolved_elsewhere.write_bytes(b"external target")
            original_resolve = Path.resolve

            def resolve(path: Path, *args, **kwargs) -> Path:
                if path == executable:
                    return resolved_elsewhere
                return original_resolve(path, *args, **kwargs)

            with mock.patch.object(Path, "resolve", resolve):
                with self.assertRaisesRegex(
                        release_manifest.ReleaseError, "outside its output root"):
                    packaged_consumer_executable(build, "glueyneo-installed-c")


def run_packaged_examples(
    consumer_build: Path, prefix: Path, run_root: Path, *,
    environment: dict[str, str] | None = None,
) -> dict[str, object]:
    """Run the packaged continuation and persistence examples against a relocated SDK."""
    env = dict(os.environ if environment is None else environment)
    env["PATH"] = str(prefix / "bin") + os.pathsep + env.get("PATH", "")
    run_root.mkdir(parents=True)

    def invoke(name: str, arguments: list[str], *, timeout: int = 120) -> str:
        executable = packaged_consumer_executable(consumer_build, name)
        result = subprocess.run(
            [str(executable), *arguments], cwd=run_root, env=env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=timeout,
        )
        if result.returncode:
            raise release_manifest.ReleaseError(
                f"packaged SDK example failed ({name}, {result.returncode}): {result.stdout[-4000:]}"
            )
        return result.stdout

    media = run_root / "public-sound-mvs.bin"
    invoke("glueyneo-installed-sound", ["--write-fixture", str(media)])
    trace = run_root / "sound.trace"
    sound_output = invoke("glueyneo-installed-sound", [str(media), "--trace", str(trace)])
    if (not any(line.startswith('SDK_SOUND {"outcome":"pass"') for line in sound_output.splitlines())
            or not media.is_file() or media.stat().st_size <= 0
            or not trace.is_file() or trace.stat().st_size <= 0):
        raise release_manifest.ReleaseError("packaged sound recipe did not produce its public fixture")

    state, expected, observed = (run_root / name for name in ("position.gnst", "expected.gnct", "observed.gnct"))
    producer = packaged_record(invoke("glueyneo-installed-continuation", [
        "--produce", str(media), str(state), str(expected),
    ]), "SDK_CONTINUATION ", role="producer")
    reader = packaged_record(invoke("glueyneo-installed-continuation", [
        "--consume", str(media), str(state), str(expected), str(observed),
    ]), "SDK_CONTINUATION ", role="reader")
    for record, fields in (
        (producer, ("frames", "elapsed_cycles", "audio_frames", "nonzero_audio_samples")),
        (reader, ("frames", "elapsed_cycles", "audio_frames")),
    ):
        if (record.get("outcome") != "pass" or record.get("case_id") != "sdk.continuation.process"
                or not all(type(record.get(field)) is int and record[field] > 0 for field in fields)):
            raise release_manifest.ReleaseError("packaged continuation did not prove guest/time/video/PCM progress")
    if (producer.get("frames") != reader.get("frames")
            or producer.get("elapsed_cycles") != reader.get("elapsed_cycles")
            or producer.get("audio_frames") != reader.get("audio_frames")
            or not expected.is_file() or not observed.is_file()
            or expected.read_bytes() != observed.read_bytes()
            or reader.get("control") != "pass"):
        raise release_manifest.ReleaseError("packaged continuation trace, including video and PCM, did not match")

    portable_slot = run_root / "portable.gnsave"
    portable_producer = packaged_record(invoke("glueyneo-installed-persistence", [
        "--mode", "portable", "--role", "producer", "--value", "A",
        "--slot", str(portable_slot), "--scope", "00000000000000000000000000000021",
    ]), "SDK_PERSISTENCE ", role="producer")
    portable_reader = packaged_record(invoke("glueyneo-installed-persistence", [
        "--mode", "portable", "--role", "reader", "--slot", str(portable_slot),
        "--scope", "00000000000000000000000000000022",
    ]), "SDK_PERSISTENCE ", role="reader")
    portable_omitted = packaged_record(invoke("glueyneo-installed-persistence", [
        "--mode", "portable", "--role", "reader", "--slot", str(portable_slot),
        "--scope", "00000000000000000000000000000025", "--no-import",
    ]), "SDK_PERSISTENCE ", role="reader")
    for record in (portable_producer, portable_reader, portable_omitted):
        if (record.get("case_id") != "sdk.persistence.portable" or record.get("outcome") != "pass"
                or record.get("host_file_commit") != "not_claimed"
                or type(record.get("assertions")) is not int or record["assertions"] <= 0):
            raise release_manifest.ReleaseError("packaged portable persistence did not report guest consumption")
    if (portable_reader.get("public_observation") == portable_omitted.get("public_observation")
            or not isinstance(portable_reader.get("public_observation"), dict)
            or type(portable_reader["public_observation"].get("instructions")) is not int
            or portable_reader["public_observation"]["instructions"] <= 0
            or portable_reader.get("transfer_bytes") != 65632):
        raise release_manifest.ReleaseError("packaged portable persistence did not prove the imported guest state was consumed")

    host_dir = run_root / "host"
    host_dir.mkdir()
    host_slot = host_dir / "slot.gnsave"
    host_producer = packaged_record(invoke("glueyneo-installed-persistence", [
        "--mode", "host", "--role", "producer", "--value", "A", "--slot", str(host_slot),
        "--scratch-dir", str(host_dir), "--scope", "00000000000000000000000000000023",
    ]), "SDK_PERSISTENCE ", role="producer")
    host_reader = packaged_record(invoke("glueyneo-installed-persistence", [
        "--mode", "host", "--role", "reader", "--reopen", "--slot", str(host_slot),
        "--scratch-dir", str(host_dir), "--scope", "00000000000000000000000000000024",
    ]), "SDK_PERSISTENCE ", role="reader")
    if (host_producer.get("case_id") != "sdk.persistence.host"
            or host_reader.get("case_id") != "sdk.persistence.host"):
        raise release_manifest.ReleaseError("packaged host persistence result was mislabeled")
    if host_producer.get("outcome") == "unsupported":
        if (host_reader.get("outcome") != "unsupported"
                or host_producer.get("host_file_commit") != "unsupported"
                or host_reader.get("host_file_commit") != "unsupported"
                or not host_producer.get("reason") or not host_reader.get("reason")):
            raise release_manifest.ReleaseError("packaged unsupported host persistence result was incomplete")
        host_outcome = "unsupported"
    elif (host_producer.get("outcome") == "pass" and host_reader.get("outcome") == "pass"
          and host_producer.get("host_file_commit") == "committed_darwin_apfs"
          and host_reader.get("host_file_commit") == "read_only_reopen"
          and host_producer.get("receipt_acked") == 1 and host_reader.get("receipt_acked") == 0):
        host_outcome = "committed-and-reopened"
    else:
        raise release_manifest.ReleaseError("packaged host persistence result did not match its platform contract")
    return {"continuation": "guest/time/video/PCM pass", "portable_persistence": "guest-consumed",
            "host_persistence": host_outcome}


class ReleaseManifestCompilerIdentityTests(unittest.TestCase):
    def test_generated_compiler_identity_accepts_visual_studio_string_and_filepath_cache(self):
        compiler = (
            "C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/MSVC/"
            "14.44.35207/bin/Hostx64/x64/cl.exe"
        )
        expected = {"path_basename": "cl.exe", "id": "MSVC", "version": "19.44.35207.1"}
        with tempfile.TemporaryDirectory(prefix="glueyneo-compiler-id-") as temp:
            build = Path(temp)
            generated = build / "CMakeFiles/4.2.0/CMakeCCompiler.cmake"
            generated.parent.mkdir(parents=True)
            generated.write_text(
                f'set(CMAKE_C_COMPILER "{compiler}")\n'
                'set(CMAKE_C_COMPILER_ID "MSVC")\n'
                'set(CMAKE_C_COMPILER_VERSION "19.44.35207.1")\n',
                encoding="utf-8",
            )
            cache = build / "CMakeCache.txt"
            for cache_type in ("STRING", "FILEPATH"):
                with self.subTest(cache_type=cache_type):
                    cache.write_text(f"CMAKE_C_COMPILER:{cache_type}={compiler}\n", encoding="utf-8")
                    self.assertEqual(release_manifest.generated_compiler_identity(build), expected)

    def test_generated_compiler_identity_rejects_missing_fields(self):
        incomplete = (
            'set(CMAKE_C_COMPILER_ID "MSVC")\nset(CMAKE_C_COMPILER_VERSION "19.44.35207.1")\n',
            'set(CMAKE_C_COMPILER "C:/VS/cl.exe")\nset(CMAKE_C_COMPILER_VERSION "19.44.35207.1")\n',
            'set(CMAKE_C_COMPILER "C:/VS/cl.exe")\nset(CMAKE_C_COMPILER_ID "MSVC")\n',
        )
        for generated_text in incomplete:
            with self.subTest(generated_text=generated_text):
                with tempfile.TemporaryDirectory(prefix="glueyneo-compiler-id-missing-") as temp:
                    generated = Path(temp) / "CMakeFiles/4.2.0/CMakeCCompiler.cmake"
                    generated.parent.mkdir(parents=True)
                    generated.write_text(generated_text, encoding="utf-8")
                    with self.assertRaisesRegex(release_manifest.ReleaseError, "compiler identity"):
                        release_manifest.generated_compiler_identity(generated.parents[2])


class ReleaseConsumerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="glueyneo-release-red-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        copy_release_fixture(ROOT, self.root)

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
        copy_release_fixture(ROOT, repo)
        subprocess.run(["git", "init", "--quiet", str(repo)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        subprocess.run(["git", "add", "--all"], cwd=repo, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        subprocess.run(
            ["git", "-c", "user.name=Glueyneo Tests", "-c", "user.email=tests@example.org",
             "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "test: snapshot release source"],
            cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        (repo / ".release-please-manifest.json").write_text('{".": "9.8.7"}\n', encoding="utf-8")
        subprocess.run(
            ["git", "-c", "user.name=Glueyneo Tests", "-c", "user.email=tests@example.org",
             "-c", "commit.gpgsign=false", "commit", "--quiet", "-am", "test: bump release version"],
            cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, text=True,
            stdout=subprocess.PIPE, timeout=10,
        ).stdout.strip()
        output = Path(self.temp.name) / "artifacts"
        workspace_temp = tempfile.TemporaryDirectory(
            prefix="glueyneo-packaging-test-", dir=release_manifest.workspace_parent())
        self.addCleanup(workspace_temp.cleanup)
        workspace = Path(workspace_temp.name)
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/release_manifest.py"), "build",
             "--repo", str(repo), "--commit", commit, "--output-dir", str(output),
             "--workspace-dir", str(workspace)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=600,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(workspace.iterdir()), [])
        record = json.loads(result.stdout)
        source_archive = output / record["source"]
        sdk_archive = output / record["sdk"]
        self.assertEqual(record["version"], "9.8.7")
        self.assertEqual(hashlib.sha256(source_archive.read_bytes()).hexdigest(), record["source_sha256"])
        self.assertEqual(hashlib.sha256(sdk_archive.read_bytes()).hexdigest(), record["sdk_sha256"])
        source_extract = Path(self.temp.name) / "source-extracted"
        release_manifest.safe_extract(source_archive, source_extract)
        source_root = source_extract / "glueyneo-source"
        source_build = Path(self.temp.name) / "offline-build"
        configure = subprocess.run(
            ["cmake", "-S", str(source_root), "-B", str(source_build),
             "-DBUILD_TESTING=OFF", "-DGLUEYNEO_BUILD_TESTS=OFF",
             "-DCMAKE_BUILD_TYPE=Release",
             "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=120,
        )
        self.assertEqual(configure.returncode, 0, configure.stdout)
        build = subprocess.run(
            ["cmake", "--build", str(source_build), "--config", "Release", "--parallel", "2"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=180,
        )
        self.assertEqual(build.returncode, 0, build.stdout)
        guide = subprocess.run(
            [sys.executable, str(source_root / "tests/consumers/test_example_docs.py"), "--mode", "commands"],
            cwd=source_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False, timeout=900,
        )
        self.assertEqual(guide.returncode, 0, guide.stdout)
        self.assertIn('"commands_executed": 28', guide.stdout)

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
        example_closure = {
            "consumer-example/source/continuation.c": "examples/continuation.c",
            "consumer-example/source/persistence.c": "examples/persistence.c",
            "consumer-example/source/persistence_host.c": "examples/persistence_host.c",
            "consumer-example/source/persistence_host.h": "examples/persistence_host.h",
            "consumer-example/source/public_persistence_guest.c": "tests/fixture/public_persistence_guest.c",
            "docs/sdk-examples.md": "docs/sdk-examples.md",
            "docs/native-state.md": "docs/native-state.md",
            "docs/native-save.md": "docs/native-save.md",
            "docs/testing.md": "docs/testing.md",
            "docs/frontend-continuation.md": "docs/frontend-continuation.md",
        }
        for packaged, original in example_closure.items():
            self.assertEqual((sdk_root / packaged).read_bytes(), (source_root / original).read_bytes(), packaged)
        notices = {
            "libretro/libretro.h": "third_party/libretro/libretro.h",
            "libretro/NOTICE.md": "third_party/libretro/NOTICE.md",
            "chips/NOTICE.md": "third_party/chips/NOTICE.md",
            "ymfm/LICENSE": "third_party/ymfm/LICENSE",
            "ymfm/NOTICE.md": "third_party/ymfm/NOTICE.md",
            "zlib/LICENSE": "third_party/zlib/LICENSE",
        }
        for variant in ("static", "shared"):
            for notice, original in notices.items():
                self.assertEqual((sdk_root / variant / "share/licenses/Glueyneo" / notice).read_bytes(),
                                 (source_root / original).read_bytes(), f"{variant}/{notice}")
        consumer_source = sdk_root / "consumer-example/source"
        self.assertEqual((consumer_source / ".release-please-manifest.json").read_bytes(),
                         (source_root / ".release-please-manifest.json").read_bytes())
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
                ["cmake", "--build", str(consumer_build), "--config", "Release", "--parallel", "2"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False, timeout=120,
            )
            self.assertEqual(build.returncode, 0, build.stdout)
            cache = (consumer_build / "CMakeCache.txt").read_text(encoding="utf-8")
            multi_config = any(line.startswith("CMAKE_CONFIGURATION_TYPES:")
                               for line in cache.splitlines())
            consumer_exe = packaged_consumer_executable(
                consumer_build, "glueyneo-installed-c"
            )
            consumer_cxx_exe = packaged_consumer_executable(
                consumer_build, "glueyneo-installed-cxx"
            )
            if multi_config:
                self.assertEqual(consumer_exe.parent, consumer_build.resolve())
                self.assertEqual(consumer_cxx_exe.parent, consumer_build.resolve())
            consumer_env = os.environ.copy()
            consumer_env["PATH"] = (str(prefix / "bin") + os.pathsep
                                     + consumer_env.get("PATH", ""))
            consumer = subprocess.run(
                [str(consumer_exe), str(fixture)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False, timeout=30, env=consumer_env,
            )
            self.assertEqual(consumer.returncode, 0, "installed C consumer failed")
            self.assertIn('"outcome":"pass"', consumer.stdout)
            consumer_cxx = subprocess.run(
                [str(consumer_cxx_exe)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False, timeout=30, env=consumer_env,
            )
            self.assertEqual(consumer_cxx.returncode, 0, "installed C++ consumer failed")
            self.assertIn('SDK_CONSUMER_CPP {"schema_version":1,"case_id":"sdk.consumer.cpp","outcome":"pass"',
                          consumer_cxx.stdout)
            examples = run_packaged_examples(
                consumer_build, prefix, Path(self.temp.name) / f"examples-{variant}",
            )
            self.assertEqual(examples["continuation"], "guest/time/video/PCM pass")
            self.assertEqual(examples["portable_persistence"], "guest-consumed")
            self.assertIn(examples["host_persistence"], {"unsupported", "committed-and-reopened"})
        self.assertFalse(repo.exists())
        self.assertFalse(source_root.exists())
        self.assertFalse(source_build.exists())
        self.assertTrue(disabled_repo.exists())
        self.assertTrue(disabled_source.exists())
        self.assertTrue(disabled_build.exists())
        content_errors = []
        for label, archive in (("source", source_archive), ("SDK", sdk_archive)):
            try:
                report = public_content.scan_archive(archive)
            except public_content.ContentError as error:
                content_errors.append(f"{label}: {error}")
            else:
                self.assertEqual(report["findings"], [], label)
        self.assertEqual(content_errors, [], "; ".join(content_errors))

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

        linux_archive = download / "glueyneo-sdk-0.1.0-linux-x86_64.tar.gz"
        linux_archive.write_bytes(b"x" + contents[linux_archive.name][1:])
        with self.assertRaises(release_state.ReleaseStateError):
            release_state.validate_downloaded_assets(download, staged_manifest)
        linux_archive.write_bytes(contents[linux_archive.name])
        (download / "unexpected.zip").write_bytes(b"extra")
        with self.assertRaises(release_state.ReleaseStateError):
            release_state.validate_downloaded_assets(download, staged_manifest)
        (download / "unexpected.zip").unlink()
        (download / "glueyneo-sdk-0.1.0-linux-x86_64.tar.gz").unlink()
        with self.assertRaisesRegex(release_state.ReleaseStateError, "names differ from the manifest"):
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

    def cache_values(cache: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in cache.read_text(encoding="utf-8").splitlines():
            if line.startswith(("CMAKE_C_COMPILER_ID:", "CMAKE_C_COMPILER_VERSION:", "CMAKE_GENERATOR:")):
                key, value = line.split("=", 1)
                values[key.split(":", 1)[0]] = value
        return values

    with tempfile.TemporaryDirectory(prefix="glueyneo-downloaded-consumer-") as temp_name:
        work = Path(temp_name)
        source_dir = work / "source"
        release_manifest.safe_extract(source_archive, source_dir)
        source_root = source_dir / "glueyneo-source"
        build = work / "offline-build"
        cases: list[dict[str, str]] = [
            {"id": "downloaded-assets", "status": "pass",
             "detail": "all downloaded bytes matched the trusted staged manifest"},
        ]
        run([cmake, "-S", str(source_root), "-B", str(build), "-DBUILD_TESTING=OFF",
             "-DGLUEYNEO_BUILD_TESTS=OFF", "-DCMAKE_BUILD_TYPE=Release",
             "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"], cwd=source_root)
        run([cmake, "--build", str(build), "--config", "Release", "--parallel", "2"], cwd=source_root)
        cases.append({"id": "offline-source-build", "status": "pass",
                      "detail": "the downloaded source archive configured and built offline"})
        source_toolchain = cache_values(build / "CMakeCache.txt")
        if not source_toolchain.get("CMAKE_C_COMPILER_ID") or not source_toolchain.get("CMAKE_C_COMPILER_VERSION"):
            raise RuntimeError("offline source build did not record its C compiler identity")
        guide = run(
            [sys.executable, str(source_root / "tests/consumers/test_example_docs.py"), "--mode", "commands"],
            cwd=source_root, timeout=900,
        )
        if ('"commands_executed": 28' not in guide or '"result_records_checked": 12' not in guide
                or '"outcome": "pass"' not in guide):
            raise RuntimeError(f"downloaded source archive guide command closure was incomplete: {guide[-4000:]}")
        cases.append({"id": "guide-command-closure", "status": "pass",
                      "detail": "28 documented commands and 12 result records passed"})
        cmake_version = run([cmake, "--version"], cwd=work).splitlines()[0]

        sdk_dir = work / "sdk"
        release_manifest.safe_extract(sdk_archive, sdk_dir)
        sdk_root = sdk_dir / f"glueyneo-sdk-{version}"
        toolchain_builds: list[dict[str, str]] = []
        for variant in ("static", "shared"):
            prefix = sdk_root / variant
            fixture = prefix / "share/glueyneo/diagnostic-original-a.bin"
            runner = next((prefix / "bin").glob("glueyneo-diagnostic*"))
            diagnostic = subprocess.run([str(runner), "--check-fixture", str(fixture)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        check=False, timeout=30)
            if diagnostic.returncode:
                raise RuntimeError(f"relocated {variant} diagnostic failed: {diagnostic.stdout[-4000:]}")
            cases.append({"id": f"{variant}-diagnostic", "status": "pass",
                          "detail": "relocated SDK diagnostic accepted the original public fixture"})
            consumer_source = sdk_root / "consumer-example/source"
            consumer_build = work / f"consumer-{variant}"
            run([cmake, "-S", str(consumer_source), "-B", str(consumer_build),
                 f"-DGlueyneo_DIR={prefix / 'lib/cmake/Glueyneo'}",
                 "-DGLUEYNEO_CONSUMER_C_SOURCE=diagnostic.c", "-DCMAKE_BUILD_TYPE=Release"], cwd=work)
            run([cmake, "--build", str(consumer_build), "--config", "Release", "--parallel", "2"], cwd=work)
            consumer_exe = packaged_consumer_executable(
                consumer_build, "glueyneo-installed-c"
            )
            process_env = dict(__import__("os").environ)
            binary_dir = str(prefix / "bin")
            process_env["PATH"] = binary_dir + __import__("os").pathsep + process_env.get("PATH", "")
            consumer = subprocess.run([str(consumer_exe), str(fixture)],
                                      text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      check=False, timeout=30, env=process_env)
            if consumer.returncode or '"outcome":"pass"' not in consumer.stdout:
                raise RuntimeError(f"relocated {variant} SDK consumer failed: {consumer.stdout[-4000:]}")
            cases.append({"id": f"{variant}-c-consumer", "status": "pass",
                          "detail": "compiled installed C consumer passed"})
            examples = run_packaged_examples(
                consumer_build, prefix, work / f"examples-{variant}",
                environment=process_env,
            )
            cases.append({"id": f"{variant}-continuation", "status": "pass",
                          "detail": str(examples["continuation"])})
            cases.append({"id": f"{variant}-portable-persistence", "status": "pass",
                          "detail": str(examples["portable_persistence"])})
            host_status = "unsupported" if examples["host_persistence"] == "unsupported" else "pass"
            cases.append({"id": f"{variant}-host-persistence", "status": host_status,
                          "detail": "host file-commit route is unsupported on this platform" if host_status == "unsupported"
                          else "host file persistence committed and reopened in a fresh process"})
            cache = cache_values(consumer_build / "CMakeCache.txt")
            if not cache.get("CMAKE_C_COMPILER_ID") or not cache.get("CMAKE_C_COMPILER_VERSION"):
                raise RuntimeError(f"{variant} installed consumer build did not record its C compiler identity")
            toolchain_builds.append({"linkage": variant, "compiler_id": cache["CMAKE_C_COMPILER_ID"],
                                     "compiler_version": cache["CMAKE_C_COMPILER_VERSION"],
                                     "generator": cache.get("CMAKE_GENERATOR", "unknown")})
        return {"outcome": "pass", "source_commit": commit, "version": version,
                "platform": platform_name, "variants": ["static", "shared"], "downloaded_byte_verification": "pass",
                "source_archive_sha256": hashlib.sha256(source_archive.read_bytes()).hexdigest(),
                "sdk_archive_sha256": hashlib.sha256(sdk_archive.read_bytes()).hexdigest(),
                "offline_source_rebuild": "pass", "guide_command_closure": "pass",
                "relocated_consumer": "pass", "packaged_examples": "pass", "cases": cases,
                "toolchain": {"cmake_version": cmake_version, "configuration": "Release",
                              "source_compiler_id": source_toolchain["CMAKE_C_COMPILER_ID"],
                              "source_compiler_version": source_toolchain["CMAKE_C_COMPILER_VERSION"],
                              "builds": toolchain_builds}}

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
        parser.add_argument("--output", type=Path)
        args = parser.parse_args()
        result = verify_downloaded_release(args.directory, args.manifest,
                                           commit=args.commit, version=args.version,
                                           platform_name=args.platform)
        serialized = json.dumps(result, sort_keys=True, separators=(",", ":"))
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized + "\n", encoding="utf-8")
        print(serialized)
    else:
        unittest.main(verbosity=2)
