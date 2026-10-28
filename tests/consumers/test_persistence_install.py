#!/usr/bin/env python3
"""Exercise the public persistence example from a relocated installed SDK."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from check_package import (
    ROOT,
    build_package,
    CheckError,
    clean_environment,
    installed_layout,
    new_work_dir,
    run,
    run_with_loader_trace,
    stage_consumer_project,
    validate_persistence_result_record,
)


def _exe(build: Path, name: str) -> Path:
    return build / (name + (".exe" if sys.platform == "win32" else ""))


class PersistenceInstallTests(unittest.TestCase):
    variant = "static"
    mode = "portable"
    assertion_count = 0
    completed_tests = 0

    def __getattribute__(self, name: str):
        attribute = super().__getattribute__(name)
        if name.startswith("assert") and callable(attribute):
            def count_assertion(*args, **kwargs):
                type(self).assertion_count += 1
                return attribute(*args, **kwargs)
            return count_assertion
        return attribute

    @classmethod
    def setUpClass(cls) -> None:
        if cls.mode not in {"portable", "host", "faults", "full"}:
            raise ValueError(f"unknown persistence mode: {cls.mode}")
        cls.assertion_count = 0
        cls.completed_tests = 0
        cls.work = new_work_dir(f"persistence-{cls.variant}-{cls.mode}")
        package = build_package(cls.variant, cls.work)
        old_prefix = package["prefix"]
        cls.original_prefix = old_prefix
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
        target = "glueyneo-installed-persistence-faults" if cls.mode == "faults" else "glueyneo-installed-persistence"
        cls.persistence = _exe(cls.consumer_build, target)

    def _run_sample(self, *args: str) -> str:
        if self.variant == "shared":
            return run_with_loader_trace(self.persistence, list(args), self.layout)
        return run([str(self.persistence), *args]).stdout

    def _run_process(self, *args: str) -> tuple[int, int, str]:
        env = clean_environment()
        library: Path | None = None
        if self.variant == "shared":
            for name in ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH",
                         "LD_LIBRARY_PATH"):
                env.pop(name, None)
            library = self.layout["library"].resolve()
            if sys.platform == "win32":
                env["PATH"] = str(library.parent) + os.pathsep + env.get("PATH", "")
            elif sys.platform == "darwin":
                env["DYLD_PRINT_LIBRARIES"] = "1"
            elif sys.platform.startswith("linux"):
                env["LD_DEBUG"] = "libs"
            else:
                self.fail(f"relocated shared loader check is unsupported on {sys.platform}")
        child = subprocess.Popen(
            [str(self.persistence), *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, env=env,
            cwd=self.work,
        )
        limit = 64 * 1024
        diagnostic_limit = 16 * 1024
        captured = bytearray()
        diagnostics = bytearray()
        overflow = threading.Event()
        loaded = threading.Event()
        expected_library = str(library).encode("utf-8") if library is not None else b""

        def drain(stream, *, keep_output: bool) -> None:
            assert stream is not None
            scan_tail = b""
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    return
                if expected_library:
                    combined = scan_tail + chunk
                    if sys.platform == "darwin" and expected_library in combined:
                        loaded.set()
                    if sys.platform.startswith("linux"):
                        lines = combined.split(b"\n")
                        scan_tail = lines.pop()
                        for line in lines:
                            match = re.match(rb"^\s*\d+:\s*calling init:\s*(.+?)\s*$", line)
                            if match is not None:
                                try:
                                    if Path(match.group(1).decode()).resolve() == library:
                                        loaded.set()
                                except (OSError, UnicodeDecodeError):
                                    pass
                    else:
                        scan_tail = combined[-len(expected_library):]
                if keep_output:
                    remaining = limit - len(captured)
                    if remaining > 0:
                        captured.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        overflow.set()
                else:
                    diagnostics.extend(chunk)
                    if len(diagnostics) > diagnostic_limit:
                        del diagnostics[:-diagnostic_limit]

        readers = [
            threading.Thread(target=drain, args=(child.stdout,), kwargs={"keep_output": True},
                             daemon=True),
            threading.Thread(target=drain, args=(child.stderr,), kwargs={"keep_output": False},
                             daemon=True),
        ]
        for reader in readers:
            reader.start()
        deadline = time.monotonic() + 30
        timed_out = False
        while child.poll() is None:
            if overflow.is_set():
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.005)
        if child.poll() is None and (timed_out or overflow.is_set()):
            child.terminate()
            try:
                child.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        child.wait()
        for reader in readers:
            reader.join(timeout=1.0)
        output = (bytes(captured) + b"\n" + bytes(diagnostics)).decode(
            "utf-8", errors="replace")
        self.assertFalse(timed_out, f"persistence child exceeded 30 seconds: {output[-2000:]}")
        self.assertFalse(overflow.is_set(), "persistence child stdout exceeded the 64 KiB output cap")
        if self.variant == "shared" and sys.platform != "win32":
            self.assertTrue(loaded.is_set(),
                            "shared consumer did not load the relocated runtime library")
        for line in output.splitlines():
            if line.startswith("SDK_PERSISTENCE "):
                print(line)
        return child.returncode, child.pid, output

    def setUp(self) -> None:
        type(self).completed_tests += 1

    @classmethod
    def tearDownClass(cls) -> None:
        print("SDK_PERSISTENCE_TESTS " + json.dumps({
            "variant": cls.variant,
            "mode": cls.mode,
            "tests": cls.completed_tests,
            "assertions": cls.assertion_count,
        }, sort_keys=True))

    @staticmethod
    def _scope() -> str:
        return secrets.token_hex(16)

    def _record(self, output: str, role: str) -> dict[str, object]:
        records = [line.removeprefix("SDK_PERSISTENCE ")
                   for line in output.splitlines()
                   if line.startswith("SDK_PERSISTENCE ")]
        self.assertEqual(len(records), 1, f"{role} must emit one public persistence result")
        record = json.loads(records[0])
        self.assertEqual(record.get("role"), role)
        validate_persistence_result_record(record)
        return record

    def _portable_pair(self, value: str, suffix: str) -> tuple[dict[str, object], dict[str, object], int, int]:
        slot = self.work / f"{suffix}.gnsave"
        producer_code, producer_pid, producer_output = self._run_process(
            "--mode", "portable", "--role", "producer", "--value", value,
            "--slot", str(slot), "--scope", self._scope(),
        )
        self.assertEqual(producer_code, 0, f"producer failed: {producer_output}")
        producer = self._record(producer_output, "producer")
        reader_code, reader_pid, reader_output = self._run_process(
            "--mode", "portable", "--role", "reader", "--slot", str(slot),
            "--scope", self._scope(),
        )
        self.assertNotEqual(producer_pid, reader_pid)
        self.assertEqual(reader_code, 0, f"reader failed: {reader_output}")
        reader = self._record(reader_output, "reader")
        return producer, reader, producer_pid, reader_pid

    def _host_call(self, mode: str, slot: Path, role: str, *, value: str | None = None,
                   reopen: bool = False, discard: bool = False,
                   fail_stage: str | None = None) -> tuple[int, dict[str, object], str]:
        arguments = ["--mode", mode, "--role", role, "--slot", str(slot),
                     "--scope", self._scope()]
        if mode != "portable":
            arguments.extend(("--scratch-dir", str(slot.parent)))
        if value is not None:
            arguments.extend(("--value", value))
        if reopen:
            arguments.append("--reopen")
        if discard:
            arguments.append("--discard")
        if fail_stage is not None:
            arguments.extend(("--test-fail-stage", fail_stage))
        code, _, output = self._run_process(*arguments)
        return code, self._record(output, role), output

    def test_portable_fresh_process_consumes_save(self) -> None:
        producer_a, reader_a, producer_a_pid, reader_a_pid = self._portable_pair("A", "value-a")
        producer_b, reader_b, producer_b_pid, reader_b_pid = self._portable_pair("B", "value-b")
        self.assertNotEqual(producer_a_pid, reader_a_pid)
        self.assertNotEqual(producer_b_pid, reader_b_pid)
        self.assertEqual(producer_a.get("outcome"), "pass")
        self.assertEqual(producer_b.get("outcome"), "pass")
        self.assertEqual(reader_a.get("outcome"), "pass")
        self.assertEqual(reader_b.get("outcome"), "pass")
        self.assertEqual(reader_a.get("host_file_commit"), "not_claimed")
        self.assertEqual(reader_b.get("host_file_commit"), "not_claimed")
        self.assertEqual(reader_a.get("transfer_bytes"), 65632)
        self.assertEqual(reader_b.get("transfer_bytes"), 65632)
        self.assertGreater(reader_a.get("fixture_bytes", 0), 64 * 1024 * 1024)
        self.assertLessEqual(reader_a.get("fixture_bytes", 0),
                             64 * 1024 * 1024 + 16 + 8 * 12)
        self.assertNotEqual(reader_a.get("public_observation"),
                            reader_b.get("public_observation"))

    def test_omitted_and_wrong_import_are_detected(self) -> None:
        slot_a = self.work / "negative-a.gnsave"
        producer_code, _, producer_output = self._run_process(
            "--mode", "portable", "--role", "producer", "--value", "A",
            "--slot", str(slot_a), "--scope", self._scope(),
        )
        self.assertEqual(producer_code, 0, f"producer failed: {producer_output}")
        producer = self._record(producer_output, "producer")
        self.assertEqual(producer.get("outcome"), "pass")
        reader_a_code, _, reader_a_output = self._run_process(
            "--mode", "portable", "--role", "reader", "--slot", str(slot_a),
            "--scope", self._scope(),
        )
        self.assertEqual(reader_a_code, 0, f"reader failed: {reader_a_output}")
        reader_a = self._record(reader_a_output, "reader")
        omitted_code, _, omitted_output = self._run_process(
            "--mode", "portable", "--role", "reader", "--slot", str(slot_a),
            "--scope", self._scope(), "--no-import",
        )
        self.assertEqual(omitted_code, 0, f"omitted-import reader failed: {omitted_output}")
        omitted = self._record(omitted_output, "reader")
        self.assertNotEqual(reader_a.get("public_observation"),
                            omitted.get("public_observation"))

        slot_b = self.work / "negative-b.gnsave"
        producer_b_code, _, producer_b_output = self._run_process(
            "--mode", "portable", "--role", "producer", "--value", "B",
            "--slot", str(slot_b), "--scope", self._scope(),
        )
        self.assertEqual(producer_b_code, 0, f"producer failed: {producer_b_output}")
        reader_b_code, _, reader_b_output = self._run_process(
            "--mode", "portable", "--role", "reader", "--slot", str(slot_b),
            "--scope", self._scope(),
        )
        self.assertEqual(reader_b_code, 0, f"wrong-save reader failed: {reader_b_output}")
        reader_b = self._record(reader_b_output, "reader")
        self.assertNotEqual(reader_a.get("public_observation"),
                            reader_b.get("public_observation"))

    def test_public_example_uses_only_the_relocated_public_consumer(self) -> None:
        source = ROOT / "examples" / "persistence.c"
        contents = source.read_text(encoding="utf-8")
        includes = re.findall(r"^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]",
                              contents, re.MULTILINE)
        self.assertIn("glueyneo/glueyneo.h", includes)
        self.assertEqual(len(includes), 6)
        self.assertNotIn("gn_test_", contents)
        self.assertNotIn("tests/fixture", contents)
        self.assertNotIn(str(ROOT), contents)
        self.assertEqual((self.consumer_source / "persistence.c").read_bytes(),
                         source.read_bytes())
        self.assertEqual((self.consumer_source / "persistence_host.c").read_bytes(),
                         (ROOT / "examples" / "persistence_host.c").read_bytes())
        self.assertEqual((self.consumer_source / "persistence_host.h").read_bytes(),
                         (ROOT / "examples" / "persistence_host.h").read_bytes())
        self.assertEqual((self.consumer_source / "public_persistence_guest.c").read_bytes(),
                         (ROOT / "tests/fixture/public_persistence_guest.c").read_bytes())
        self.assertEqual((self.consumer_source / "public_sound_guest.c").read_bytes(),
                         (ROOT / "tests/fixture/public_sound_guest.c").read_bytes())
        compile_commands = json.loads(
            (self.consumer_build / "compile_commands.json").read_text(encoding="utf-8"))
        rows = [row for row in compile_commands
                if row.get("file", "").endswith("/persistence.c")]
        self.assertEqual(len(rows), 2)
        normal_rows = [row for row in rows
                       if "GLUEYNEO_PERSISTENCE_TESTING" not in
                       json.dumps(row, sort_keys=True)]
        fault_rows = [row for row in rows if row not in normal_rows]
        self.assertEqual(len(normal_rows), 1)
        self.assertEqual(len(fault_rows), 1)
        for row in rows:
            command = json.dumps(row, sort_keys=True)
            self.assertIn(str(self.relocated_prefix), command)
            for forbidden in (str(ROOT), str(self.package_build), str(self.work / "producer")):
                self.assertNotIn(forbidden, command)
        nm = shutil.which("nm")
        if nm is not None:
            symbols = subprocess.run([nm, str(self.persistence)], check=True,
                capture_output=True, text=True, timeout=10).stdout
            self.assertNotIn("persistence_host_test_set_faults", symbols)
            self.assertNotIn("persistence_host_set_stage_callback", symbols)

    def test_publish_before_ack(self) -> None:
        with self.subTest(mode="host"):
            slot = self.work / "host-first" / "slot.gnsave"
            slot.parent.mkdir()
            code, _, output = self._run_process(
                "--mode", "host", "--role", "producer", "--value", "A",
                "--slot", str(slot), "--scratch-dir", str(slot.parent),
                "--scope", self._scope(),
            )
            self.assertEqual(0, code, output)
            record = self._record(output, "producer")
            if record.get("outcome") == "unsupported":
                self.assertTrue(record.get("reason"))
                self.assertEqual(record.get("host_file_commit"), "unsupported")
                self.assertFalse(slot.exists())
                self.assertEqual(record.get("receipt_acked"), 0)
                return
            self.assertEqual(record.get("host_file_commit"), "committed_darwin_apfs")
            self.assertTrue(slot.is_file())
            if self.mode == "faults":
                self.assertEqual(record.get("stages"),
                                 "temp-created,write,file-fullfsync,file-close,rename,"
                                 "directory-open,directory-fsync,directory-close,ack")
            self.assertEqual(record.get("receipt_acked"), 1)
            reader_code, _, reader_output = self._run_process(
                "--mode", "host", "--role", "reader", "--reopen",
                "--slot", str(slot), "--scratch-dir", str(slot.parent),
                "--scope", self._scope(),
            )
            self.assertEqual(reader_code, 0, reader_output)
            reader = self._record(reader_output, "reader")
            self.assertEqual(reader.get("host_file_commit"), "read_only_reopen")

    def test_invalid_existing_slot(self) -> None:
        cases = (
            ("wrong-size", "slot_invalid"),
            ("malformed-envelope", "slot_format_invalid"),
            ("fifo", "slot_invalid"),
            ("directory", "slot_invalid"),
        )
        for case, expected_reason in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(
                    prefix="persistence-invalid-slot-") as directory:
                slot = Path(directory) / "slot.gnsave"
                if case == "wrong-size":
                    slot.write_bytes(b"not-a-save")
                elif case == "malformed-envelope":
                    slot.write_bytes(bytes(65_632))
                elif case == "fifo":
                    os.mkfifo(slot)
                else:
                    slot.mkdir()
                code, record, output = self._host_call(
                    "host", slot, "reader", reopen=True)
                if record.get("outcome") == "unsupported":
                    self.assertTrue(record.get("reason"))
                    self.assertEqual(record.get("host_file_commit"), "unsupported")
                    return
                self.assertEqual(code, 2, output)
                self.assertEqual(record.get("outcome"), "invalid")
                self.assertEqual(record.get("reason"), expected_reason)
                self.assertEqual(record.get("public_observation", {}).get("instructions"), 0)

    def test_repeat_refuses_slot(self) -> None:
        with tempfile.TemporaryDirectory(prefix="persistence-repeat-slot-") as directory:
            slot = Path(directory) / "slot.gnsave"
            code, first, output = self._host_call("host", slot, "producer", value="A")
            if first.get("outcome") == "unsupported":
                self.assertTrue(first.get("reason"))
                return
            self.assertEqual(code, 0, output)
            original = slot.read_bytes()
            code, second, output = self._host_call("host", slot, "producer", value="B")
            self.assertEqual(code, 2, output)
            self.assertEqual(second.get("reason"), "slot_already_exists")
            self.assertEqual(slot.read_bytes(), original)

    def test_explicit_reopen(self) -> None:
        with tempfile.TemporaryDirectory(prefix="persistence-explicit-reopen-") as directory:
            slot = Path(directory) / "slot.gnsave"
            code, first, output = self._host_call("host", slot, "producer", value="A")
            if first.get("outcome") == "unsupported":
                self.assertTrue(first.get("reason"))
                return
            self.assertEqual(code, 0, output)
            code, reopened, output = self._host_call(
                "host", slot, "reader", reopen=True)
            self.assertEqual(code, 0, output)
            self.assertEqual(reopened.get("host_file_commit"), "read_only_reopen")
            self.assertEqual(reopened.get("outcome"), "pass")
            self.assertGreater(reopened.get("public_observation", {}).get("instructions", 0), 0)

    def test_uncertain_blocks_transitions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="persistence-uncertain-") as directory:
            slot = Path(directory) / "slot.gnsave"
            code, record, output = self._host_call(
                "faults", slot, "producer", value="A", fail_stage="directory-sync")
            if record.get("outcome") == "unsupported":
                self.assertTrue(record.get("reason"))
                self.assertEqual(record.get("host_file_commit"), "unsupported")
                return
            self.assertEqual(code, 4, output)
            self.assertEqual(record.get("host_file_commit"), "outcome_uncertain")
            self.assertEqual(record.get("transition_barrier_mask"), 63)
            self.assertEqual(record.get("receipt_acked"), 0)
            self.assertIn("rename", str(record.get("stages")))
            self.assertNotIn("ack", str(record.get("stages")).split(","))
            self.assertTrue(slot.is_file())

    def test_discard_has_no_flush(self) -> None:
        with tempfile.TemporaryDirectory(prefix="persistence-discard-no-flush-") as directory:
            slot = Path(directory) / "slot.gnsave"
            code, record, output = self._host_call(
                "faults", slot, "producer", value="B", fail_stage="directory-sync",
                discard=True)
            if record.get("outcome") == "unsupported":
                self.assertTrue(record.get("reason"))
                return
            self.assertEqual(code, 0, output)
            self.assertEqual(record.get("outcome"), "discarded")
            self.assertEqual(record.get("receipt_acked"), 0)
            stages = str(record.get("stages", "")).split(",")
            self.assertEqual(stages.count("temp-created"), 1)
            self.assertNotIn("ack", stages)
            self.assertNotIn("directory-fsync", stages)
            self.assertTrue(slot.is_file())

    def test_host_route_unsupported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="persistence-host-support-") as directory:
            slot = Path(directory) / "slot.gnsave"
            code, record, output = self._host_call("host", slot, "producer", value="A")
            self.assertEqual(code, 0, output)
            if record.get("outcome") == "unsupported":
                self.assertTrue(record.get("reason"))
                self.assertEqual(record.get("host_file_commit"), "unsupported")
            else:
                self.assertEqual(record.get("host_file_commit"), "committed_darwin_apfs")
                self.assertEqual(record.get("receipt_acked"), 1)

    def test_fault_stage_matrix(self) -> None:
        pre_rename = {"create", "write", "file-sync", "file-close", "rename"}
        stages = ("create", "write", "file-sync", "file-close", "rename",
                  "directory-open", "directory-sync", "directory-close", "ack")
        observed = []
        for stage in stages:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(
                    prefix="persistence-stage-fault-") as directory:
                slot = Path(directory) / "slot.gnsave"
                code, record, output = self._host_call(
                    "faults", slot, "producer", value="A", fail_stage=stage)
                if record.get("outcome") == "unsupported":
                    self.assertTrue(record.get("reason"))
                    self.assertEqual(record.get("host_file_commit"), "unsupported")
                    return
                self.assertEqual(code, 4, output)
                self.assertEqual(record.get("receipt_acked"), 0)
                self.assertNotIn("ack", str(record.get("stages", "")).split(","))
                if stage in pre_rename:
                    self.assertEqual(record.get("host_file_commit"), "not_committed")
                    self.assertFalse(slot.exists())
                else:
                    self.assertEqual(record.get("host_file_commit"), "outcome_uncertain")
                    self.assertTrue(slot.is_file())
                observed.append(stage)
        self.assertEqual(list(stages), observed)

    def test_exact_persistence_membership(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        matches = list(re.finditer(
            r"add_test\s*\(\s*NAME\s+(sdk_example_persistence_[A-Za-z0-9_]+)(.*?)\)",
            cmake, re.DOTALL,
        ))
        actual = [match.group(1) for match in matches]
        expected = {
            "sdk_example_persistence_static",
            "sdk_example_persistence_shared",
            "sdk_example_persistence_faults",
        }
        self.assertEqual(Counter(actual), Counter(expected),
                         "persistence CTest membership must be exact and unique")
        route_modes = {
            "sdk_example_persistence_static": ("static", "full"),
            "sdk_example_persistence_shared": ("shared", "full"),
            "sdk_example_persistence_faults": ("static", "faults"),
        }
        for match in matches:
            name, body = match.group(1), match.group(2)
            variant, mode = route_modes[name]
            self.assertRegex(body, rf"--variant\s+{variant}\b")
            self.assertRegex(body, rf"--mode\s+{mode}\b")
            selected = default_test_names(mode)
            self.assertGreater(len(selected), 0, f"{name} must select at least one test")
            self.assertEqual(len(selected), len(set(selected)),
                             f"{name} must not select duplicate tests")
            for test_name in selected:
                self.assertTrue(hasattr(PersistenceInstallTests, test_name),
                                f"{name} selects missing test {test_name}")

    def test_wrong_host_claim(self) -> None:
        portable = {
            "schema_version": 1, "assertions": 1,
            "case_id": "sdk.persistence.portable", "outcome": "pass",
            "host_file_commit": "not_claimed",
        }
        unsupported = {
            "schema_version": 1, "assertions": 1,
            "case_id": "sdk.persistence.host", "role": "producer",
            "outcome": "unsupported", "host_file_commit": "unsupported",
            "reason": "host filesystem is outside the tested durability contract",
            "receipt_acked": 0,
        }
        self.assertEqual(validate_persistence_result_record(portable), "portable")
        self.assertEqual(validate_persistence_result_record(unsupported), "host")
        forged_portable = dict(portable, host_file_commit="committed_darwin_apfs")
        with self.assertRaises(CheckError):
            validate_persistence_result_record(forged_portable)
        forged_host = dict(unsupported, outcome="pass", host_file_commit="unsupported")
        with self.assertRaises(CheckError):
            validate_persistence_result_record(forged_host)
        zero_denominator = dict(portable, assertions=0)
        with self.assertRaises(CheckError):
            validate_persistence_result_record(zero_denominator)

    def test_relocated_examples(self) -> None:
        self.assertFalse(str(self.work).startswith(str(ROOT) + os.sep))
        self.assertFalse(self.original_prefix.exists(),
                         "original install prefix must be hidden after relocation")
        build_manifest = (self.consumer_build / "build.ninja").read_text(encoding="utf-8")
        for forbidden in (str(ROOT), str(self.package_build), str(self.original_prefix)):
            self.assertNotIn(forbidden, build_manifest)
        producer, reader, producer_pid, reader_pid = self._portable_pair("A", "relocated")
        self.assertNotEqual(producer_pid, reader_pid)
        self.assertEqual(producer.get("outcome"), "pass")
        self.assertEqual(reader.get("outcome"), "pass")


def default_test_names(mode: str) -> tuple[str, ...]:
    if mode == "portable":
        return (
            "test_portable_fresh_process_consumes_save",
            "test_omitted_and_wrong_import_are_detected",
            "test_public_example_uses_only_the_relocated_public_consumer",
        )
    if mode == "host":
        return (
            "test_publish_before_ack", "test_invalid_existing_slot",
            "test_repeat_refuses_slot", "test_explicit_reopen",
            "test_host_route_unsupported",
        )
    if mode == "faults":
        return (
            "test_publish_before_ack", "test_uncertain_blocks_transitions",
            "test_discard_has_no_flush", "test_fault_stage_matrix",
        )
    if mode == "full":
        return (*default_test_names("portable"), *default_test_names("host"),
                "test_exact_persistence_membership", "test_relocated_examples",
                "test_wrong_host_claim")
    raise ValueError(f"unknown persistence mode: {mode}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("static", "shared"), required=True)
    parser.add_argument("--mode", choices=("portable", "host", "faults", "full"), required=True)
    parser.add_argument("--test", choices=(
        "test_portable_fresh_process_consumes_save",
        "test_omitted_and_wrong_import_are_detected",
        "test_public_example_uses_only_the_relocated_public_consumer",
        "test_publish_before_ack",
        "test_invalid_existing_slot",
        "test_repeat_refuses_slot",
        "test_explicit_reopen",
        "test_uncertain_blocks_transitions",
        "test_discard_has_no_flush",
        "test_host_route_unsupported",
        "test_fault_stage_matrix",
        "test_exact_persistence_membership",
        "test_relocated_examples",
        "test_wrong_host_claim",
    ))
    args = parser.parse_args()
    PersistenceInstallTests.variant = args.variant
    PersistenceInstallTests.mode = args.mode
    if args.test:
        names = (args.test,)
    else:
        names = default_test_names(args.mode)
    suite = unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromName(
            f"PersistenceInstallTests.{name}", module=sys.modules[__name__])
        for name in names
    )
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
