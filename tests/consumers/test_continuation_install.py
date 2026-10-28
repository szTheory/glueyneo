#!/usr/bin/env python3
"""Exercise the public continuation example from a relocated installed SDK."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

from check_package import (
    ROOT,
    build_package,
    installed_layout,
    new_work_dir,
    run,
    run_with_loader_trace,
    stage_consumer_project,
)


def _exe(build: Path, name: str) -> Path:
    return build / (name + (".exe" if sys.platform == "win32" else ""))


class ContinuationInstallTests(unittest.TestCase):
    variant = "static"
    mode = "instance"

    @classmethod
    def setUpClass(cls) -> None:
        if cls.mode not in {"instance", "process"}:
            raise ValueError(f"unknown continuation mode: {cls.mode}")
        cls.work = new_work_dir(f"continuation-{cls.variant}-{cls.mode}")
        package = build_package(cls.variant, cls.work)
        old_prefix = package["prefix"]
        cls.relocated_prefix = cls.work / "relocated" / "sdk-prefix"
        cls.relocated_prefix.parent.mkdir(parents=True)
        shutil.move(str(old_prefix), str(cls.relocated_prefix))
        if old_prefix.exists():
            raise AssertionError("original install prefix remains after relocation")
        cls.package_build = package["build_dir"]
        cls.layout = installed_layout(cls.relocated_prefix, cls.variant)
        cls.consumer_source = cls.work / "consumer-source"
        stage_consumer_project(cls.consumer_source)
        cls.consumer_build = cls.work / "consumer-build"
        cmake = shutil.which("cmake") or "cmake"
        run([
            cmake, "-G", "Ninja", "-S", str(cls.consumer_source),
            "-B", str(cls.consumer_build), "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            f"-DGlueyneo_DIR={cls.layout['config'].parent}",
            "-DGLUEYNEO_CONSUMER_C_SOURCE=diagnostic.c",
        ])
        run([cmake, "--build", str(cls.consumer_build), "--parallel", "2"])
        cls.fixture = cls.work / "public-sound-mvs.bin"
        sound = _exe(cls.consumer_build, "glueyneo-installed-sound")
        if cls.variant == "shared":
            run_with_loader_trace(sound, ["--write-fixture", str(cls.fixture)], cls.layout)
        else:
            run([str(sound), "--write-fixture", str(cls.fixture)])
        if not cls.fixture.is_file() or cls.fixture.stat().st_size <= 0:
            raise AssertionError("staged original public sound fixture was not generated")
        cls.continuation = _exe(cls.consumer_build, "glueyneo-installed-continuation")

    def _run_sample(self, fixture: Path, trace: Path, expected_returncode: int = 0) -> str:
        args = [str(self.continuation), str(fixture), str(trace)]
        if self.variant == "shared":
            return run_with_loader_trace(
                self.continuation, args[1:], self.layout,
                expected_returncode=expected_returncode,
            )
        return run(args, expected_returncode=expected_returncode).stdout

    def _run_process(self, executable: Path, *args: Path | str) -> tuple[int, int, str]:
        child = subprocess.Popen(
            [str(executable), *(str(arg) for arg in args)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            output, _ = child.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            child.kill()
            output, _ = child.communicate()
            self.fail(f"continuation child exceeded 30 seconds: {output[-2000:]}")
        self.assertLessEqual(len(output.encode("utf-8")), 16 * 1024)
        return child.returncode, child.pid, output

    def _process_pair(self, suffix: str = "normal") -> tuple[dict[str, object], dict[str, object], bytes, bytes]:
        state = self.work / f"{suffix}.gnst"
        expected_trace = self.work / f"{suffix}.expected.gnct"
        observed_trace = self.work / f"{suffix}.observed.gnct"
        producer_code, producer_pid, producer_output = self._run_process(
            self.continuation, "--produce", self.fixture, state, expected_trace,
        )
        self.assertEqual(producer_code, 0, f"producer failed: {producer_output}")
        producer = self._process_record(producer_output, "producer")
        self.assertTrue(0 < state.stat().st_size <= 4 * 1024 * 1024)
        self.assertTrue(0 < expected_trace.stat().st_size <= 2 * 1024 * 1024)

        reader_code, reader_pid, reader_output = self._run_process(
            self.continuation, "--consume", self.fixture, state,
            expected_trace, observed_trace,
        )
        self.assertNotEqual(producer_pid, reader_pid)
        self.assertEqual(reader_code, 0, f"reader failed: {reader_output}")
        reader = self._process_record(reader_output, "reader")
        self.assertTrue(0 < observed_trace.stat().st_size <= 2 * 1024 * 1024)
        return producer, reader, expected_trace.read_bytes(), observed_trace.read_bytes()

    @staticmethod
    def _process_record(output: str, role: str) -> dict[str, object]:
        records = [line.removeprefix("SDK_CONTINUATION ")
                   for line in output.splitlines()
                   if line.startswith("SDK_CONTINUATION ")]
        if len(records) != 1:
            raise AssertionError(f"{role} must emit one continuation result")
        record = json.loads(records[0])
        if record.get("outcome") != "pass" or record.get("role") != role:
            raise AssertionError(f"{role} result failed: {record}")
        return record

    def _build_mutant(self, name: str, source: str) -> Path:
        mutant_source = self.consumer_source / f"continuation_{name}.c"
        mutant_source.write_text(source, encoding="utf-8")
        target = f"glueyneo-installed-continuation-{name}"
        cmake_lists = self.consumer_source / "CMakeLists.txt"
        with cmake_lists.open("a", encoding="utf-8") as stream:
            stream.write(
                f"\nadd_executable({target} continuation_{name}.c)\n"
                f"target_link_libraries({target} PRIVATE Glueyneo::glueyneo)\n"
                f"set_target_properties({target} PROPERTIES C_STANDARD 17 "
                "C_STANDARD_REQUIRED YES C_EXTENSIONS NO)\n"
            )
        cmake = shutil.which("cmake") or "cmake"
        run([cmake, "-S", str(self.consumer_source), "-B", str(self.consumer_build),
             f"-DGlueyneo_DIR={self.layout['config'].parent}",
             "-DGLUEYNEO_CONSUMER_C_SOURCE=diagnostic.c"])
        run([cmake, "--build", str(self.consumer_build), "--target", target,
             "--parallel", "2"])
        return _exe(self.consumer_build, target)

    def test_installed_instance_continuation(self) -> None:
        trace = self.work / "instance.trace"
        output = self._run_sample(self.fixture, trace)
        records = [line.removeprefix("SDK_CONTINUATION ")
                   for line in output.splitlines()
                   if line.startswith("SDK_CONTINUATION ")]
        self.assertEqual(len(records), 1, "example must emit one public result record")
        result = json.loads(records[0])
        self.assertEqual(result.get("outcome"), "pass")
        self.assertEqual(result.get("case_id"), "sdk.continuation.instance")
        self.assertGreaterEqual(result.get("assertions", 0), 20)
        self.assertEqual(result.get("frames"), 3)
        self.assertGreater(result.get("elapsed_cycles", 0), 0)
        self.assertEqual(result.get("video_pixels"), 320 * 224)
        self.assertGreater(result.get("audio_frames", 0), 0)
        self.assertGreater(result.get("nonzero_audio_samples", 0), 0)
        self.assertTrue(result.get("tone") == "pass")
        self.assertTrue(result.get("fire") == "pass")
        self.assertTrue(result.get("release") == "pass")
        self.assertGreater(trace.stat().st_size, 0)

    def test_missing_fixture_and_output_failures_are_nonzero(self) -> None:
        missing = self.work / "missing-public-media.bin"
        self._run_sample(missing, self.work / "missing.trace", expected_returncode=2)
        blocked_output = self.work / "absent-directory" / "trace.bin"
        self._run_sample(self.fixture, blocked_output, expected_returncode=2)

    def test_public_only_example_has_no_checkout_or_private_dependency(self) -> None:
        source = ROOT / "examples" / "continuation.c"
        contents = source.read_text(encoding="utf-8")
        includes = re.findall(r"^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]",
                              contents, re.MULTILINE)
        self.assertIn("glueyneo/glueyneo.h", includes)
        self.assertFalse(any("gn_test_" in name or "/src/" in name
                             for name in includes))
        for forbidden in ("gn_test_", "tests/fixture", "experiments/owned_cpu",
                          "third_party/", "GLUEYNEO_SOURCE_DIR"):
            self.assertNotIn(forbidden, contents)
        staged = self.consumer_source / "continuation.c"
        self.assertEqual(staged.read_bytes(), source.read_bytes())
        compile_commands = json.loads(
            (self.consumer_build / "compile_commands.json").read_text(encoding="utf-8"))
        continuation_rows = [row for row in compile_commands
                             if row.get("file", "").endswith("/continuation.c")]
        self.assertEqual(len(continuation_rows), 1)
        compile_text = json.dumps(continuation_rows[0], sort_keys=True)
        self.assertIn(str(self.relocated_prefix), compile_text)
        for forbidden in (str(ROOT), str(self.package_build), str(self.work / "producer")):
            self.assertNotIn(forbidden, compile_text)

    def test_fresh_process_continuation(self) -> None:
        producer, reader, expected, observed = self._process_pair("fresh")
        self.assertGreaterEqual(producer.get("assertions", 0), 8)
        self.assertGreaterEqual(reader.get("assertions", 0), 20)
        self.assertEqual(reader.get("frames"), 3)
        self.assertGreater(reader.get("elapsed_cycles", 0), 0)
        self.assertEqual(expected[:12], b"GNCT\x01\x00\x00\x00\x03\x00\x00\x00")
        self.assertEqual(observed, expected)

    def test_rejected_state_continues(self) -> None:
        _producer, reader, expected, observed = self._process_pair("rejection")
        self.assertEqual(reader.get("truncated_status"), 1)
        self.assertEqual(reader.get("truncated_reason"), 8)
        self.assertEqual(reader.get("foreign_status"), 3)
        self.assertEqual(reader.get("foreign_reason"), 16)
        self.assertEqual(reader.get("control"), "pass")
        self.assertEqual(observed, expected)

    def test_omitted_restore_is_detected(self) -> None:
        source = (ROOT / "examples" / "continuation.c").read_text(encoding="utf-8")
        before = "return gn_state_restore_v1(destination, state, state_size,\n                               &detail, sizeof(detail)) == GN_STATUS_OK;"
        self.assertIn(before, source)
        mutant = source.replace(before, "(void)destination; (void)state; (void)state_size;\n    (void)detail; return 1;", 1)
        self.assertNotEqual(mutant, source)
        producer_state = self.work / "omitted.gnst"
        expected = self.work / "omitted.expected.gnct"
        producer_code, _, producer_output = self._run_process(
            self.continuation, "--produce", self.fixture, producer_state, expected,
        )
        self.assertEqual(producer_code, 0, f"producer failed: {producer_output}")
        omitted = self._build_mutant("omitted", mutant)
        observed = self.work / "omitted.observed.gnct"
        code, _, output = self._run_process(
            omitted, "--consume", self.fixture, producer_state, expected, observed,
        )
        self.assertNotEqual(code, 0, f"omitted restore unexpectedly passed: {output}")

    def test_wrong_future_input_is_detected(self) -> None:
        source = (ROOT / "examples" / "continuation.c").read_text(encoding="utf-8")
        before = "0u, GN_MVS_INPUT_P1_A, 0u"
        self.assertIn(before, source)
        mutant = source.replace(before, "0u, 0u, 0u", 1)
        producer_state = self.work / "wrong-input.gnst"
        expected = self.work / "wrong-input.expected.gnct"
        producer_code, _, producer_output = self._run_process(
            self.continuation, "--produce", self.fixture, producer_state, expected,
        )
        self.assertEqual(producer_code, 0, f"producer failed: {producer_output}")
        wrong = self._build_mutant("wrong-input", mutant)
        observed = self.work / "wrong-input.observed.gnct"
        code, _, output = self._run_process(
            wrong, "--consume", self.fixture, producer_state, expected, observed,
        )
        self.assertNotEqual(code, 0, f"wrong future input unexpectedly passed: {output}")

    def test_corrupted_trace_is_rejected(self) -> None:
        producer_state = self.work / "corrupt-trace.gnst"
        expected = self.work / "corrupt-trace.expected.gnct"
        producer_code, _, producer_output = self._run_process(
            self.continuation, "--produce", self.fixture, producer_state, expected,
        )
        self.assertEqual(producer_code, 0, f"producer failed: {producer_output}")
        trace = bytearray(expected.read_bytes())
        self.assertGreater(len(trace), 16)
        trace[-1] ^= 0x01
        expected.write_bytes(trace)
        observed = self.work / "corrupt-trace.observed.gnct"
        code, _, output = self._run_process(
            self.continuation, "--consume", self.fixture, producer_state, expected, observed,
        )
        self.assertNotEqual(code, 0, f"corrupted trace unexpectedly passed: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("static", "shared"), required=True)
    parser.add_argument("--mode", choices=("instance", "process"), required=True)
    parser.add_argument("--test", choices=(
        "test_fresh_process_continuation", "test_rejected_state_continues",
        "test_omitted_restore_is_detected", "test_wrong_future_input_is_detected",
        "test_corrupted_trace_is_rejected",
    ))
    args = parser.parse_args()
    ContinuationInstallTests.variant = args.variant
    ContinuationInstallTests.mode = args.mode
    if args.test:
        suite = unittest.defaultTestLoader.loadTestsFromName(
            f"ContinuationInstallTests.{args.test}",
            module=sys.modules[__name__],
        )
    elif args.mode == "instance":
        names = ("test_installed_instance_continuation",
                 "test_missing_fixture_and_output_failures_are_nonzero",
                 "test_public_only_example_has_no_checkout_or_private_dependency")
        suite = unittest.TestSuite(
            unittest.defaultTestLoader.loadTestsFromName(
                f"ContinuationInstallTests.{name}", module=sys.modules[__name__])
            for name in names
        )
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ContinuationInstallTests)
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
