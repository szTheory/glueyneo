#!/usr/bin/env python3
"""Bounded process-level guest persistence regression."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
import re
import select
import struct
import subprocess
import sys
import threading
import tempfile
import time
import unittest
from pathlib import Path


EXPECTED = {"A": "123456789abc", "B": "a1b2c3d4e5f6"}
LEGACY_FIXTURE_BYTES = 67_108_976
LEGACY_FIXTURE_SHA256 = "9cefb11420e190f5902e8861f5becda1c63c7ccd988118d7d93dc814a1b36690"
CHILD_TIMEOUT_SECONDS = 15
CHILD_OUTPUT_LIMIT_BYTES = 1024 * 1024
DOC_OBSERVATIONS: dict[str, object] = {}


@dataclass(frozen=True)
class BoundedChildResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    output_limited: bool
    reaped: bool


def _run_bounded_child(
    command: list[str], *, timeout_seconds: float = CHILD_TIMEOUT_SECONDS,
    output_limit_bytes: int = CHILD_OUTPUT_LIMIT_BYTES,
    input_bytes: bytes | None = None,
) -> BoundedChildResult:
    if timeout_seconds <= 0 or output_limit_bytes < 128:
        raise ValueError("child timeout and output limit must be positive and bounded")
    child = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    streams = (child.stdout, child.stderr)
    captured = [bytearray(), bytearray()]
    observed = [0, 0]
    output_overrun = threading.Event()

    def drain(index: int) -> None:
        stream = streams[index]
        assert stream is not None
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                return
            observed[index] += len(chunk)
            remaining = output_limit_bytes - len(captured[index])
            if remaining > 0:
                captured[index].extend(chunk[:remaining])
            if observed[index] > output_limit_bytes:
                output_overrun.set()

    readers = [threading.Thread(target=drain, args=(index,), daemon=True)
               for index in range(2)]
    for reader in readers:
        reader.start()

    if input_bytes is not None and child.stdin is not None:
        try:
            child.stdin.write(input_bytes)
            child.stdin.flush()
        except BrokenPipeError:
            pass
        finally:
            child.stdin.close()

    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    while child.poll() is None:
        if output_overrun.is_set():
            break
        if time.monotonic() >= deadline:
            timed_out = True
            break
        time.sleep(0.005)

    output_limited = output_overrun.is_set()
    if child.poll() is None and (timed_out or output_limited):
        try:
            child.terminate()
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    returncode = child.wait()
    for reader in readers:
        reader.join(timeout=1.0)
    output_limited = output_overrun.is_set()

    reason = "output limit" if output_limited else "timeout" if timed_out else None
    stderr_bytes = bytes(captured[1])
    if reason is not None:
        marker = f"\n[child terminated for {reason}; captured output is bounded]\n".encode()
        marker = marker[:output_limit_bytes]
        stderr_bytes = stderr_bytes[:output_limit_bytes - len(marker)] + marker
    return BoundedChildResult(
        returncode=returncode,
        stdout=bytes(captured[0]).decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
        timed_out=timed_out,
        output_limited=output_limited,
        reaped=child.returncode is not None,
    )


class SaveProcessTests(unittest.TestCase):
    runner: Path
    assertion_count = 0

    def __getattribute__(self, name: str):
        attribute = super().__getattribute__(name)
        if name.startswith("assert") and callable(attribute):
            def count_assertion(*args, **kwargs):
                type(self).assertion_count += 1
                return attribute(*args, **kwargs)
            return count_assertion
        return attribute

    def test_write_fixture_is_stable_and_preserves_legacy_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-fixture-") as directory:
            hashes = []
            for index in range(2):
                fixture = Path(directory) / f"save-{index}.gnmv"
                result = _run_bounded_child(
                    [str(self.runner), "--write-fixture", str(fixture)])
                self.assertEqual(0, result.returncode,
                                 f"save.fixture-generation: {result.stdout}"
                                 f"{result.stderr}")
                self.assertEqual(LEGACY_FIXTURE_BYTES, fixture.stat().st_size,
                                 "save.fixture-size")
                hashes.append(hashlib.sha256(fixture.read_bytes()).hexdigest())
            self.assertEqual([LEGACY_FIXTURE_SHA256] * 2, hashes,
                             "save.fixture-identity")
            DOC_OBSERVATIONS.update({
                "fixture_bytes": LEGACY_FIXTURE_BYTES,
                "fixture_sha256": hashes[0],
                "child_timeout_seconds": CHILD_TIMEOUT_SECONDS,
                "child_output_bound_bytes": CHILD_OUTPUT_LIMIT_BYTES,
            })

    def test_child_output_flood_is_terminated_and_reaped_with_bounded_capture(self) -> None:
        flood = (
            "import os\n"
            "block = b'x' * 65536\n"
            "while True:\n"
            "    os.write(1, block)\n"
            "    os.write(2, block)\n"
        )
        result = _run_bounded_child(
            [sys.executable, "-c", flood], timeout_seconds=5,
            output_limit_bytes=4096)
        self.assertTrue(result.output_limited, "save.child-output-limit-enforced")
        self.assertFalse(result.timed_out, "save.child-output-overrun-is-not-timeout")
        self.assertTrue(result.reaped, "save.child-output-child-reaped")
        self.assertNotEqual(0, result.returncode, "save.child-output-child-terminated")
        self.assertLessEqual(len(result.stdout.encode("utf-8")), 4096,
                             "save.child-output-capture-bound")
        self.assertLessEqual(len(result.stderr.encode("utf-8")), 4096,
                             "save.child-error-capture-bound")
        self.assertIn("output limit", result.stderr, "save.child-output-limit-diagnostic")

        timed_out = _run_bounded_child(
            [sys.executable, "-c",
             "import time; print('bounded-timeout-prefix', flush=True); time.sleep(5)"],
            timeout_seconds=0.1, output_limit_bytes=128)
        self.assertTrue(timed_out.timed_out, "save.child-timeout-enforced")
        self.assertTrue(timed_out.reaped, "save.child-timeout-child-reaped")
        self.assertLessEqual(len(timed_out.stdout.encode("utf-8")), 128,
                             "save.child-timeout-output-bound")
        self.assertLessEqual(len(timed_out.stderr.encode("utf-8")), 128,
                             "save.child-timeout-error-bound")
        self.assertIn("bounded-timeout-prefix", timed_out.stdout)

    def run_child(
        self, mode: str, value: str, save_file: Path, *, no_import: bool = False,
        fail_after_rename: bool = False, resolve_action: str | None = None,
        test_retry_fsync_failures: int = 0, fail_stage: str | None = None,
        short_write_limit: int = 0, interrupted_writes: int = 0,
        false_ack_control: bool = False,
        disk_latest_branch_control: bool = False,
        print_immutable_export: bool = False,
        expect_invalid_authoritative: bool = False,
        probe_failed_barriers: bool = False,
        retry_failed_commit: bool = False,
    ) -> BoundedChildResult:
        command = [str(self.runner), "--mode", mode, "--value", value,
                   "--save-file", str(save_file)]
        if no_import:
            command.append("--no-import")
        if fail_after_rename:
            command.append("--test-fail-after-rename")
        input_bytes = None
        if test_retry_fsync_failures:
            command.extend(("--test-retry-fsync-failures",
                            str(test_retry_fsync_failures)))
            input_bytes = b"retry\n" * test_retry_fsync_failures
        if fail_stage is not None:
            command.extend(("--test-fail-stage", fail_stage))
        if short_write_limit:
            command.extend(("--test-short-write-limit", str(short_write_limit)))
        if interrupted_writes:
            command.extend(("--test-interrupted-writes", str(interrupted_writes)))
        if false_ack_control:
            command.append("--test-control-false-ack")
        if disk_latest_branch_control:
            command.append("--test-control-disk-latest-branch")
        if print_immutable_export:
            command.append("--test-print-immutable-export")
        if expect_invalid_authoritative:
            command.append("--test-control-invalid-authoritative")
        if probe_failed_barriers:
            command.append("--test-probe-failed-barriers")
        if retry_failed_commit:
            command.append("--test-retry-failed-commit")
        if resolve_action is not None:
            command.extend(("--resolve-uncertain", resolve_action))
        result = _run_bounded_child(command, input_bytes=input_bytes)
        self.assertFalse(result.timed_out, result.stderr or "save.child-timeout")
        self.assertFalse(result.output_limited, result.stderr or "save.child-output-bound")
        return result

    def run_child_to_stage(
        self, value: str, save_file: Path, stage_name: str, *, release: bool,
        barrier_ordering: bool = False, obsolete_publication: bool = False,
        fail_after_rename: bool = False,
    ) -> tuple[str | None, BoundedChildResult]:
        notify_read, notify_write = os.pipe()
        release_read, release_write = os.pipe()
        command = [str(self.runner), "--mode", "write", "--value", value,
                   "--save-file", str(save_file), "--test-stage-name", stage_name,
                   "--test-stage-notify-fd", str(notify_write),
                   "--test-stage-release-fd", str(release_read)]
        if stage_name == "partial-write":
            command.extend(("--test-short-write-limit", "4096"))
        if barrier_ordering:
            command.append("--test-barrier-ordering")
        if obsolete_publication:
            command.append("--test-control-obsolete-publication")
        if fail_after_rename:
            command.append("--test-fail-after-rename")
        child = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0,
            pass_fds=(notify_write, release_read),
        )
        os.close(notify_write)
        os.close(release_read)
        streams = (child.stdout, child.stderr)
        captured = [bytearray(), bytearray()]
        overrun = threading.Event()

        def drain(index: int) -> None:
            stream = streams[index]
            assert stream is not None
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    return
                remaining = CHILD_OUTPUT_LIMIT_BYTES - len(captured[index])
                if remaining > 0:
                    captured[index].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    overrun.set()

        readers = [threading.Thread(target=drain, args=(index,), daemon=True)
                   for index in range(2)]
        for reader in readers:
            reader.start()
        ready, _, _ = select.select([notify_read], [], [], CHILD_TIMEOUT_SECONDS)
        notified_stage = None
        timed_out = not ready and child.poll() is None
        if ready:
            stage_line = os.read(notify_read, 128).decode("ascii", errors="replace")
            notified_stage = stage_line.rstrip("\n")
            if release:
                os.write(release_write, b"R")
            else:
                child.terminate()
        elif child.poll() is None:
            child.terminate()
        os.close(notify_read)
        os.close(release_write)
        if child.poll() is None:
            try:
                child.wait(timeout=CHILD_TIMEOUT_SECONDS if release else 0.25)
            except subprocess.TimeoutExpired:
                timed_out = release
                child.kill()
                child.wait()
        returncode = child.wait()
        for reader in readers:
            reader.join(timeout=1.0)
        limited = overrun.is_set()
        suffix = b"\n[child terminated at stage or bound; capture is bounded]\n"
        stderr_bytes = bytes(captured[1])
        if timed_out or limited:
            stderr_bytes = stderr_bytes[:CHILD_OUTPUT_LIMIT_BYTES - len(suffix)] + suffix
        return notified_stage, BoundedChildResult(
            returncode=returncode,
            stdout=bytes(captured[0]).decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            timed_out=timed_out,
            output_limited=limited,
            reaped=child.returncode is not None,
        )

    @staticmethod
    def observation(child: BoundedChildResult) -> dict[str, object]:
        line = next((line for line in child.stdout.splitlines()
                     if line.startswith("SAVE_OBSERVATION ")), None)
        if line is None:
            raise AssertionError("save.observation missing")
        return json.loads(line.removeprefix("SAVE_OBSERVATION "))

    def test_guest_output_uses_value_from_previous_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-") as directory:
            media_identities = []
            writers = []
            readers = []
            envelopes = []
            reader_outputs = []
            writer_pids = []
            reader_pids = []
            for value in ("A", "B"):
                save_file = Path(directory) / f"slot-{value}.gnsave"
                writer = self.run_child("write", value, save_file)
                self.assertEqual(0, writer.returncode, writer.stdout + writer.stderr)
                writer_initial = writer.stdout.split("save.guest-output=")[-1].splitlines()[0]
                self.assertEqual("000000000000", writer_initial,
                                 "save.guest-read-before-write")
                writer_values = writer.stdout.split("save.writer-readback=")[-1].splitlines()[0]
                self.assertEqual(EXPECTED[value], writer_values, "save.guest-write")
                writer_pid = writer.stdout.split("save.process-id=")[-1].splitlines()[0]
                writer_pids.append(writer_pid)
                writer_observation = self.observation(writer)
                writers.append(writer_observation)
                self.assertEqual("committed", writer_observation["host_outcome"])
                self.assertEqual(1, writer_observation["after_guest_dirty"])
                self.assertEqual(1, writer_observation["after_export_dirty"])
                self.assertEqual(0, writer_observation["after_ack_dirty"])
                self.assertEqual(1, writer_observation["after_ack_baseline_known"])
                self.assertEqual(1, writer_observation["reset_preserved_sram"])
                self.assertEqual(1, writer_observation["restore_branched"])
                self.assertEqual(1, writer_observation["stale_ack_preserved_dirty"])
                self.assertEqual(1, writer_observation["duplicate_ack_rejected"])
                self.assertEqual(4, writer_observation["receipt_mutation_sequence"])
                self.assertEqual(1, writer_observation["receipt_restore_branch"])
                self.assertEqual(2, writer_observation["receipt_export_sequence"])
                self.assertEqual(
                    "temp-created,write,file-fullfsync,file-close,rename,"
                    "directory-open,directory-fsync,directory-close,ack",
                    writer_observation["stages"],
                )
                envelope = save_file.read_bytes()
                envelopes.append(envelope)
                media_identities.append(envelope[32:64])
                self.assertEqual(65_632, len(envelope), "save.envelope-length")
                self.assertEqual(b"GNSV", envelope[:4], "save.envelope-magic")
                self.assertEqual((1, 96, 65_632, 65_536, 1),
                                 struct.unpack(">IIIII", envelope[4:24]),
                                 "save.envelope-header")
                self.assertEqual(0, struct.unpack(">I", envelope[28:32])[0],
                                 "save.envelope-reserved")
                self.assertEqual(
                    hashlib.sha256(b"Glueyneo MVS save v1" +
                                   envelope[:64] + envelope[96:]).digest(),
                    envelope[64:96], "save.envelope-digest",
                )
                self.assertEqual(EXPECTED[value], bytes(
                    envelope[96 + offset] for offset in (0, 1, 0x1234, 0x1235,
                                                         0xFFFE, 0xFFFF)
                ).hex(), "save.envelope-payload")

                reader = self.run_child("read", value, save_file)
                self.assertEqual(0, reader.returncode, reader.stdout + reader.stderr)
                reader_pid = reader.stdout.split("save.process-id=")[-1].splitlines()[0]
                reader_pids.append(reader_pid)
                self.assertNotEqual(writer_pid, reader_pid, "save.process-isolation")
                observed = reader.stdout.split("save.guest-output=")[-1].splitlines()[0]
                reader_outputs.append(observed)
                self.assertEqual(EXPECTED[value], observed, "save.guest-output")
                reader_observation = self.observation(reader)
                readers.append(reader_observation)
                self.assertEqual(1, reader_observation["after_import_baseline_known"])
                self.assertEqual(0, reader_observation["after_guest_dirty"])
                self.assertEqual(0, reader_observation["after_guest_startup_import_allowed"])
                self.assertEqual(1, reader_observation["closed_import_rejected"])
                self.assertEqual("read,import", reader_observation["stages"])
            self.assertEqual(media_identities[0], media_identities[1],
                             "save.shared-media-identity")
            DOC_OBSERVATIONS.update({
                "writers": writers,
                "readers": readers,
                "envelopes": envelopes,
                "reader_outputs": reader_outputs,
                "writer_pids": writer_pids,
                "reader_pids": reader_pids,
                "writer_exit_before_reader": True,
                "media_identities": media_identities,
                "shared_media_identity": media_identities[0] == media_identities[1],
                "host_stage_trace": writers[0]["stages"],
                "scope_bytes": writers[0]["scope_bytes"],
                "receipt_bytes": writers[0]["receipt_bytes"],
                "info_bytes": writers[0]["info_bytes"],
                "detail_bytes": writers[0]["detail_bytes"],
                "envelope_bytes": writers[0]["envelope_bytes"],
                "payload_bytes": writers[0]["payload_bytes"],
            })

    def assert_guest_output_control_fails(
        self, child: BoundedChildResult
    ) -> None:
        self.assertEqual(1, child.returncode, child.stdout + child.stderr)
        self.assertIn("ASSERTION FAILED save.guest-output", child.stderr)

    def test_no_import_control_fails_at_guest_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-no-import-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            writer = self.run_child("write", "A", save_file)
            self.assertEqual(0, writer.returncode, writer.stdout + writer.stderr)
            control = self.run_child("read", "A", save_file, no_import=True)
            self.assert_guest_output_control_fails(control)

    def test_wrong_valid_value_control_fails_at_guest_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-wrong-value-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            writer = self.run_child("write", "B", save_file)
            self.assertEqual(0, writer.returncode, writer.stdout + writer.stderr)
            control = self.run_child("read", "A", save_file)
            self.assert_guest_output_control_fails(control)

    def test_missing_first_slot_starts_with_unknown_zero_sram(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-first-slot-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            child = self.run_child("read", "A", save_file)
            self.assertEqual(0, child.returncode, child.stdout + child.stderr)
            observed = child.stdout.split("save.guest-output=")[-1].splitlines()[0]
            self.assertEqual("000000000000", observed, "save.first-slot-zero-sram")
            observation = self.observation(child)
            self.assertEqual("missing", observation["startup_read_result"])
            self.assertEqual(0, observation["after_import_baseline_known"])
            self.assertEqual(0, observation["after_guest_dirty"])
            self.assertEqual(0, observation["after_guest_baseline_known"])
            self.assertEqual("missing", observation["stages"])
            self.assertFalse(save_file.exists())
            DOC_OBSERVATIONS["fresh_slot_observation"] = observation

    def test_fifo_without_writer_fails_invalid_without_timeout(self) -> None:
        if not hasattr(os, "mkfifo"):
            self.skipTest("named FIFOs are unavailable on this platform")
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-fifo-") as directory:
            fifo = Path(directory) / "slot.gnsave"
            os.mkfifo(fifo)
            timeout_seconds = 2.0
            started = time.monotonic()
            child = _run_bounded_child(
                [str(self.runner), "--mode", "read", "--value", "A",
                 "--save-file", str(fifo)],
                timeout_seconds=timeout_seconds,
            )
            elapsed_seconds = time.monotonic() - started
            self.assertFalse(child.timed_out,
                             child.stderr or "save.fifo-open-must-not-timeout")
            self.assertFalse(child.output_limited,
                             child.stderr or "save.fifo-diagnostic-within-bound")
            self.assertTrue(child.reaped, "save.fifo-child-reaped")
            self.assertEqual(2, child.returncode, child.stdout + child.stderr)
            self.assertIn("save.authoritative-read failed outcome=invalid",
                          child.stderr, "save.fifo-explicit-invalid-outcome")
            self.assertLess(elapsed_seconds, timeout_seconds,
                            "save.fifo-rejected-before-parent-timeout")
            DOC_OBSERVATIONS["fifo_invalid_observation"] = {
                "timed_out": child.timed_out,
                "reaped": child.reaped,
                "returncode": child.returncode,
                "stderr": child.stderr,
                "elapsed_seconds": elapsed_seconds,
                "timeout_seconds": timeout_seconds,
            }

    def test_invalid_authoritative_targets_fail_before_guest_and_are_not_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-invalid-authoritative-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            baseline = self.run_child("write", "A", save_file)
            self.assertEqual(0, baseline.returncode,
                             baseline.stdout + baseline.stderr)
            valid = save_file.read_bytes()
            bad_digest = bytearray(valid)
            bad_digest[64] ^= 1
            incompatible_media = bytearray(valid)
            incompatible_media[32] ^= 1
            incompatible_media[64:96] = hashlib.sha256(
                b"Glueyneo MVS save v1" + incompatible_media[:64] +
                incompatible_media[96:]
            ).digest()
            cases = (
                ("truncated", valid[:-1],
                 "save.authoritative-read failed outcome=invalid"),
                ("trailing-byte", valid + b"\x00",
                 "save.authoritative-read failed outcome=invalid"),
                ("bad-digest", bytes(bad_digest),
                 "save.baseline-import failed host-read=readable outcome=invalid"),
                ("media-incompatible", bytes(incompatible_media),
                 "save.baseline-import failed host-read=readable outcome=invalid"),
            )
            observed = []
            for label, malformed, expected_diagnostic in cases:
                with self.subTest(case=label):
                    save_file.write_bytes(malformed)
                    reader = self.run_child(
                        "read", "A", save_file,
                        expect_invalid_authoritative=True)
                    self.assertEqual(2, reader.returncode,
                                     reader.stdout + reader.stderr)
                    self.assertIn(expected_diagnostic, reader.stderr,
                                  f"save.authoritative-{label}-explicit-invalid")
                    self.assertNotIn("missing", reader.stderr,
                                     f"save.authoritative-{label}-never-missing")
                    self.assertNotIn("save.guest-output=", reader.stdout,
                                     f"save.authoritative-{label}-no-guest-work")
                    self.assertNotIn("SAVE_OBSERVATION ", reader.stdout,
                                     f"save.authoritative-{label}-no-zero-baseline")
                    observed.append(label)
            self.assertEqual([case[0] for case in cases], observed,
                             "save.authoritative-invalid-case-denominator")
            DOC_OBSERVATIONS["invalid_authoritative_cases"] = observed

    def test_uncertain_retry_republishes_retained_transaction_through_full_protocol(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-uncertain-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            child = self.run_child("write", "A", save_file,
                                   fail_after_rename=True, resolve_action="retry",
                                   print_immutable_export=True)
            self.assertEqual(0, child.returncode, child.stdout + child.stderr)
            observation = self.observation(child)
            self.assertEqual("retry", observation["host_resolution"])
            self.assertEqual("committed", observation["host_outcome"])
            self.assertEqual(0, observation["after_ack_dirty"])
            self.assertEqual(1, observation["duplicate_ack_rejected"])
            self.assertEqual(
                "temp-created,write,file-fullfsync,file-close,rename,"
                "temp-created,write,file-fullfsync,file-close,rename,"
                "directory-open,directory-fsync,directory-close,ack",
                observation["stages"],
                "save.retry-complete-protocol",
            )
            envelope = save_file.read_bytes()
            self.assertEqual(65_632, len(envelope), "save.uncertain-retained-envelope")
            immutable_line = next((line for line in child.stdout.splitlines()
                                    if line.startswith("save.immutable-export=")), None)
            self.assertIsNotNone(immutable_line,
                                 "save.retry-pre-failure-envelope-captured")
            immutable = bytes.fromhex(immutable_line.split("=", 1)[1])
            self.assertEqual(len(envelope), len(immutable),
                             "save.retry-immutable-envelope-length")
            self.assertEqual(immutable, envelope,
                             "save.retry-exact-retained-envelope")
            self.assertEqual(hashlib.sha256(immutable).digest(),
                             hashlib.sha256(envelope).digest(),
                             "save.retry-whole-envelope-digest")
            self.assertEqual(
                hashlib.sha256(b"Glueyneo MVS save v1" + envelope[:64] +
                               envelope[96:]).digest(),
                envelope[64:96], "save.retry-final-envelope-digest-valid",
            )
            self.assertEqual(EXPECTED["A"], bytes(
                envelope[96 + offset] for offset in (0, 1, 0x1234, 0x1235,
                                                     0xFFFE, 0xFFFF)
            ).hex(), "save.uncertain-retained-payload")
            reader = self.run_child("read", "A", save_file)
            self.assertEqual(0, reader.returncode, reader.stdout + reader.stderr)
            self.assertEqual(EXPECTED["A"],
                             reader.stdout.split("save.guest-output=")[-1].splitlines()[0],
                             "save.retry-fresh-reader-import")
            DOC_OBSERVATIONS["uncertain_retry_observation"] = observation
            DOC_OBSERVATIONS["uncertain_retry_envelope"] = {
                "bytes": len(immutable),
                "sha256": hashlib.sha256(immutable).hexdigest(),
                "exact_after_retry": immutable == envelope,
                "fresh_reader_value": EXPECTED["A"],
            }

    def test_uncertain_retry_survives_repeated_sync_failures(self) -> None:
        failure_count = 8
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-retry-failures-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            child = self.run_child(
                "write", "A", save_file, fail_after_rename=True,
                resolve_action="retry",
                test_retry_fsync_failures=failure_count,
            )
            self.assertEqual(failure_count,
                             child.stderr.count("save.host-retry=still_uncertain"),
                             "save.retry-injected-sync-failure-count")
            self.assertEqual(0, child.returncode, child.stdout + child.stderr)
            observation = self.observation(child)
            self.assertEqual("retry", observation["host_resolution"])
            self.assertEqual("committed", observation["host_outcome"])
            self.assertEqual(0, observation["after_ack_dirty"])
            self.assertEqual(
                "temp-created,write,file-fullfsync,file-close,rename,"
                "temp-created,write,file-fullfsync,file-close,rename,"
                "directory-open,directory-fsync,directory-close,ack",
                observation["stages"],
                "save.retry-final-attempt-trace-is-complete",
            )
            self.assertTrue(save_file.exists(), "save.retry-recovered-slot-published")
            DOC_OBSERVATIONS["uncertain_retry_after_repeated_failures"] = observation
            DOC_OBSERVATIONS["uncertain_retry_failure_count"] = failure_count

    def test_syscall_fault_matrix_preserves_authoritative_history(self) -> None:
        pre_rename = {"create", "write", "file-sync", "file-close", "rename"}
        failure_names = {"create": "exclusive-create",
                         "file-sync": "file-fullfsync",
                         "directory-sync": "directory-fsync"}
        cases = ("create", "write", "file-sync", "file-close", "rename",
                 "directory-open", "directory-sync", "directory-close", "ack")
        results = []
        for prior_a in (False, True):
            for stage in cases:
                with self.subTest(prior_a=prior_a, stage=stage), \
                        tempfile.TemporaryDirectory(prefix="glueyneo-save-fault-") as directory:
                    save_file = Path(directory) / "slot.gnsave"
                    if prior_a:
                        baseline = self.run_child("write", "A", save_file)
                        self.assertEqual(0, baseline.returncode,
                                         baseline.stdout + baseline.stderr)
                    post_rename = stage not in pre_rename
                    child = self.run_child(
                        "write", "B", save_file,
                        fail_stage=stage,
                        resolve_action="discard" if post_rename else None,
                        probe_failed_barriers=(not prior_a and stage == "rename"),
                    )
                    self.assertEqual(4, child.returncode,
                                     child.stdout + child.stderr)
                    observation = self.observation(child)
                    self.assertEqual(failure_names.get(stage, stage),
                                     observation["failed_stage"],
                                     f"save.fault-stage-{stage}")
                    self.assertEqual(1, observation["after_export_dirty"],
                                     f"save.fault-dirty-before-ack-{stage}")
                    self.assertEqual(1, observation["after_ack_dirty"],
                                     f"save.fault-no-ack-{stage}")
                    if post_rename:
                        self.assertEqual("outcome_uncertain",
                                         observation["host_outcome"],
                                         f"save.fault-post-rename-uncertain-{stage}")
                        self.assertEqual("discard", observation["host_resolution"])
                        self.assertEqual("B", self._slot_value(save_file),
                                         f"save.fault-new-bytes-may-be-visible-{stage}")
                    else:
                        self.assertEqual("not_committed", observation["host_outcome"],
                                         f"save.fault-pre-rename-not-committed-{stage}")
                        self.assertEqual("none", observation["host_resolution"])
                        if not prior_a and stage == "rename":
                            state_line = next((line for line in child.stdout.splitlines()
                                               if line.startswith("SAVE_FAILED_BARRIER_STATE ")),
                                              None)
                            self.assertIsNotNone(state_line,
                                "save.failed-commit-barrier-state-observed")
                            state = json.loads(state_line.removeprefix(
                                "SAVE_FAILED_BARRIER_STATE "))
                            self.assertEqual(1, state["active"],
                                "save.failed-commit-retains-pending-barrier")
                            self.assertEqual(1, state["commit_failed"],
                                "save.failed-commit-is-distinct-from-uncertain")
                            self.assertEqual(0, state["unresolved"],
                                "save.pre-rename-failure-is-not-uncertain")
                            self.assertEqual((1 << 6) - 1, state["barrier_mask"],
                                "save.failed-commit-blocks-nondiscard-transitions")
                            self.assertEqual("ok", state["explicit_discard"],
                                "save.failed-commit-allows-only-explicit-discard")
                            self.assertEqual(1, state["discarded_pending"],
                                "save.explicit-discard-reports-pending-data")
                            self.assertEqual(1, state["after_discard_transition_ready"],
                                "save.explicit-discard-clears-transition-barrier")
                            DOC_OBSERVATIONS["pre_rename_failure_barrier"] = state
                        if prior_a:
                            self.assertEqual("A", self._slot_value(save_file),
                                             f"save.fault-preserves-A-{stage}")
                        else:
                            self.assertFalse(save_file.exists(),
                                             f"save.fault-preserves-absence-{stage}")
                    results.append({"prior_a": prior_a, "stage": stage,
                                    "post_rename": post_rename})
        self.assertEqual(18, len(results), "save.fault-matrix-case-denominator")
        DOC_OBSERVATIONS["host_fault_matrix"] = results
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-pre-rename-retry-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            retry = self.run_child(
                "write", "B", save_file, fail_stage="rename",
                probe_failed_barriers=True, retry_failed_commit=True,
                print_immutable_export=True,
            )
            self.assertEqual(0, retry.returncode, retry.stdout + retry.stderr)
            retry_state_line = next((line for line in retry.stdout.splitlines()
                                     if line.startswith("SAVE_FAILED_RETRY_STATE ")), None)
            self.assertIsNotNone(retry_state_line,
                                 "save.failed-commit-retry-state-observed")
            retry_state = json.loads(retry_state_line.removeprefix(
                "SAVE_FAILED_RETRY_STATE "))
            self.assertEqual("committed", retry_state["retry_outcome"])
            self.assertEqual(0, retry_state["commit_failed"])
            self.assertEqual(1, retry_state["transition_ready"])
            self.assertEqual(0, retry_state["after_ack_dirty"])
            immutable_line = next((line for line in retry.stdout.splitlines()
                                   if line.startswith("save.immutable-export=")), None)
            self.assertIsNotNone(immutable_line,
                                 "save.failed-commit-retry-retains-export")
            immutable = bytes.fromhex(immutable_line.split("=", 1)[1])
            self.assertEqual(immutable, save_file.read_bytes(),
                             "save.failed-commit-retry-publishes-retained-bytes")
            fresh = self.run_child("read", "B", save_file)
            self.assertEqual(0, fresh.returncode, fresh.stdout + fresh.stderr)
            self.assertEqual(EXPECTED["B"],
                             fresh.stdout.split("save.guest-output=")[-1].splitlines()[0],
                             "save.failed-commit-retry-fresh-reader")
            DOC_OBSERVATIONS["pre_rename_retry"] = retry_state

    @staticmethod
    def _slot_value(save_file: Path) -> str:
        envelope = save_file.read_bytes()
        if len(envelope) != 65_632 or envelope[:4] != b"GNSV":
            return "invalid"
        payload = bytes(envelope[96 + offset] for offset in
                        (0, 1, 0x1234, 0x1235, 0xFFFE, 0xFFFF)).hex()
        return next((name for name, expected in EXPECTED.items()
                     if payload == expected), "invalid")

    def test_short_writes_and_eintr_publish_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-short-write-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            child = self.run_child("write", "A", save_file,
                                   short_write_limit=4096,
                                   interrupted_writes=4)
            self.assertEqual(0, child.returncode, child.stdout + child.stderr)
            observed = self.observation(child)
            self.assertEqual("committed", observed["host_outcome"])
            self.assertEqual(0, observed["after_ack_dirty"])
            self.assertEqual("A", self._slot_value(save_file),
                             "save.short-write-eintr-exact-envelope")
            DOC_OBSERVATIONS["short_write_eintr_observation"] = observed

    def test_false_ack_control_fails_when_published_bytes_are_readable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-false-ack-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            child = self.run_child("write", "B", save_file,
                                   fail_stage="directory-close",
                                   false_ack_control=True)
            self.assertEqual(1, child.returncode, child.stdout + child.stderr)
            self.assertIn("ASSERTION FAILED save.no-false-ack", child.stderr)
            self.assertEqual("B", self._slot_value(save_file),
                             "save.no-false-ack-readable-published-bytes")
            DOC_OBSERVATIONS["false_ack_control"] = {
                "returncode": child.returncode,
                "assertion": "save.no-false-ack",
                "readable_value": self._slot_value(save_file),
            }

    def test_stage_gate_notifies_after_real_file_close(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-stage-red-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            observed_stage, child = self.run_child_to_stage(
                "A", save_file, "file-close", release=False)
            self.assertEqual("file-close", observed_stage,
                             "save.stage-gate-before-file-rename")
            self.assertTrue(child.reaped, child.stderr)
            self.assertNotEqual(0, child.returncode)

    def test_killed_stage_writers_recover_only_authoritative_target(self) -> None:
        before_rename = {"temp-created", "partial-write", "write",
                         "file-fullfsync", "file-close"}
        stages = ("temp-created", "partial-write", "write", "file-fullfsync",
                  "file-close", "rename", "directory-fsync", "directory-close",
                  "protocol-complete", "ack")
        cases = []
        for prior_a in (False, True):
            for stage_name in stages:
                with self.subTest(prior_a=prior_a, stage=stage_name), \
                        tempfile.TemporaryDirectory(prefix="glueyneo-save-kill-stage-") as directory:
                    save_file = Path(directory) / "slot.gnsave"
                    if prior_a:
                        baseline = self.run_child("write", "A", save_file)
                        self.assertEqual(0, baseline.returncode,
                                         baseline.stdout + baseline.stderr)
                    observed_stage, killed = self.run_child_to_stage(
                        "B", save_file, stage_name, release=False)
                    self.assertEqual(stage_name, observed_stage,
                                     f"save.recovery-stage-notified-{stage_name}")
                    self.assertTrue(killed.reaped,
                                    f"save.recovery-writer-reaped-{stage_name}")
                    self.assertFalse(killed.timed_out,
                                     f"save.recovery-stage-not-a-timeout-{stage_name}")
                    self.assertFalse(killed.output_limited,
                                     f"save.recovery-stage-output-bounded-{stage_name}")
                    self.assertNotEqual(0, killed.returncode,
                                        f"save.recovery-writer-terminated-{stage_name}")
                    post_rename = stage_name not in before_rename
                    expected_disk = "B" if post_rename else ("A" if prior_a else None)
                    if expected_disk is None:
                        self.assertFalse(save_file.exists(),
                                         f"save.recovery-first-create-remains-absent-{stage_name}")
                    else:
                        self.assertEqual(expected_disk, self._slot_value(save_file),
                                         f"save.recovery-authoritative-{stage_name}")
                    orphans = sorted(save_file.parent.glob(save_file.name + ".tmp.*"))
                    expected_orphans = 0 if post_rename else 1
                    self.assertEqual(expected_orphans, len(orphans),
                                     f"save.recovery-orphan-count-{stage_name}")
                    if stage_name in {"write", "file-fullfsync", "file-close"}:
                        self.assertEqual("B", self._slot_value(orphans[0]),
                                         f"save.recovery-valid-orphan-{stage_name}")
                    reader_value = expected_disk or "A"
                    reader = self.run_child("read", reader_value, save_file)
                    self.assertEqual(0, reader.returncode,
                                     reader.stdout + reader.stderr)
                    reader_observation = self.observation(reader)
                    expected_startup = "readable" if expected_disk else "missing"
                    self.assertEqual(expected_startup,
                                     reader_observation["startup_read_result"],
                                     f"save.recovery-fresh-reader-{stage_name}")
                    expected_output = EXPECTED[expected_disk] if expected_disk else "000000000000"
                    self.assertEqual(expected_output,
                                     reader.stdout.split("save.guest-output=")[-1].splitlines()[0],
                                     f"save.recovery-target-only-{stage_name}")
                    cases.append({"prior_a": prior_a, "stage": stage_name,
                                  "authoritative": expected_disk or "missing",
                                  "orphan_count": len(orphans), "reader": "fresh"})
        self.assertEqual(20, len(cases), "save.recovery-stage-case-denominator")
        DOC_OBSERVATIONS["recovery_kill_cases"] = cases

    def test_host_barriers_serialize_old_a_before_restored_branch_b(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-barrier-order-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            stage, writer = self.run_child_to_stage(
                "A", save_file, "file-close", release=True,
                barrier_ordering=True)
            self.assertEqual("file-close", stage, "save.barrier-stage-handshake")
            self.assertFalse(writer.timed_out, writer.stderr)
            self.assertFalse(writer.output_limited, writer.stderr)
            self.assertTrue(writer.reaped, writer.stderr)
            self.assertEqual(0, writer.returncode, writer.stdout + writer.stderr)
            observation = self.observation(writer)
            self.assertEqual((1 << 6) - 1, observation["barrier_probe_mask"],
                             "save.transition-six-barrier-denominator")
            self.assertEqual("committed", observation["host_outcome"])
            self.assertEqual("B", self._slot_value(save_file),
                             "save.disk-latest-branch")
            reader = self.run_child("read", "B", save_file)
            self.assertEqual(0, reader.returncode, reader.stdout + reader.stderr)
            self.assertEqual(EXPECTED["B"],
                             reader.stdout.split("save.guest-output=")[-1].splitlines()[0],
                             "save.disk-latest-branch")
            DOC_OBSERVATIONS["barrier_ordering"] = {
                "barrier_mask": observation["barrier_probe_mask"],
                "latest_disk_value": self._slot_value(save_file),
                "fresh_reader_value": EXPECTED["B"],
            }

    def test_unresolved_post_rename_transaction_blocks_all_transitions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-unresolved-barrier-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            stage, child = self.run_child_to_stage(
                "A", save_file, "unresolved", release=False,
                barrier_ordering=True, fail_after_rename=True)
            self.assertEqual("unresolved", stage,
                             "save.unresolved-barrier-stage-handshake")
            self.assertFalse(child.timed_out, child.stderr)
            self.assertFalse(child.output_limited, child.stderr)
            self.assertTrue(child.reaped, child.stderr)
            self.assertNotEqual(0, child.returncode,
                                "save.unresolved-writer-terminated-at-gate")
            state_line = next((line for line in child.stdout.splitlines()
                               if line.startswith("SAVE_BARRIER_STATE ")), None)
            self.assertIsNotNone(state_line,
                                 "save.unresolved-barrier-state-observed")
            state = json.loads(state_line.removeprefix("SAVE_BARRIER_STATE "))
            self.assertEqual(0, state["active"], "save.unresolved-not-active")
            self.assertEqual(0, state["publication_in_flight"],
                             "save.unresolved-not-in-flight")
            self.assertEqual(1, state["unresolved"],
                             "save.unresolved-state-retained")
            self.assertEqual((1 << 6) - 1, state["barrier_mask"],
                             "save.unresolved-six-transition-barriers")
            self.assertEqual(1, state["destroy_owner_preserved"],
                             "save.unresolved-destroy-preserves-owner")
            self.assertEqual("A", self._slot_value(save_file),
                             "save.unresolved-post-rename-bytes-visible")
            DOC_OBSERVATIONS["unresolved_barrier"] = state

    def test_obsolete_publication_control_fails_disk_latest_branch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-obsolete-control-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            stage, writer = self.run_child_to_stage(
                "A", save_file, "file-close", release=True,
                barrier_ordering=True, obsolete_publication=True)
            self.assertEqual("file-close", stage, "save.obsolete-stage-handshake")
            self.assertFalse(writer.timed_out, writer.stderr)
            self.assertFalse(writer.output_limited, writer.stderr)
            self.assertTrue(writer.reaped, writer.stderr)
            self.assertEqual(0, writer.returncode, writer.stdout + writer.stderr)
            observation = self.observation(writer)
            self.assertEqual((1 << 6) - 1, observation["barrier_probe_mask"],
                             "save.obsolete-control-barriers-were-probed")
            self.assertEqual("outcome_uncertain",
                             observation["obsolete_publication_outcome"])
            self.assertEqual(1, observation["obsolete_stale_ack_rejected"],
                             "save.obsolete-control-stale-ack-still-rejected")
            self.assertEqual("A", self._slot_value(save_file),
                             "save.obsolete-control-landed-old-a-last")
            reader = self.run_child("read", "B", save_file,
                                    disk_latest_branch_control=True)
            self.assertEqual(1, reader.returncode, reader.stdout + reader.stderr)
            self.assertIn("ASSERTION FAILED save.disk-latest-branch", reader.stderr)
            DOC_OBSERVATIONS["obsolete_publication_control"] = {
                "assertion": "save.disk-latest-branch",
                "stale_ack_rejected": observation["obsolete_stale_ack_rejected"],
                "final_disk_value": self._slot_value(save_file),
            }

    def test_uncertain_rename_requires_explicit_discard_to_drop_pending_work(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-save-discard-") as directory:
            save_file = Path(directory) / "slot.gnsave"
            child = self.run_child("write", "B", save_file,
                                   fail_after_rename=True, resolve_action="discard")
            self.assertEqual(4, child.returncode, child.stdout + child.stderr)
            observation = self.observation(child)
            self.assertEqual("discard", observation["host_resolution"])
            self.assertEqual("outcome_uncertain", observation["host_outcome"])
            self.assertEqual(1, observation["after_export_dirty"])
            self.assertEqual(1, observation["after_ack_dirty"])
            self.assertNotIn("ack", observation["stages"].split(","))
            self.assertTrue(save_file.exists())
            DOC_OBSERVATIONS["uncertain_discard_observation"] = observation


class SaveDocsError(AssertionError):
    def __init__(self, claim_id: str, message: str):
        super().__init__(f"{claim_id}: {message}")
        self.claim_id = claim_id


def _docs_require(condition: bool, claim_id: str, message: str) -> None:
    if not condition:
        raise SaveDocsError(claim_id, message)


def _clean_cell(value: str) -> str:
    return value.strip().replace("`", "")


def _read_table(
    document: str, heading: str, path: str, claim_id: str
) -> tuple[list[str], list[dict[str, str]]]:
    heading_pattern = re.compile(rf"^##?#?\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = heading_pattern.search(document)
    _docs_require(match is not None, claim_id,
                  f"{path}: missing normative table heading {heading!r}")
    lines = document[match.end():].splitlines()
    start = next((i for i, line in enumerate(lines) if line.lstrip().startswith("|")), None)
    _docs_require(start is not None, claim_id,
                  f"{path}: no table follows {heading!r}")

    raw_rows = []
    for line in lines[start:]:
        if not line.lstrip().startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        raw_rows.append(cells)
    _docs_require(len(raw_rows) >= 2, claim_id,
                  f"{path}: table {heading!r} has no data rows")
    headers = [header.replace("`", "") for header in raw_rows[0]]
    rows = []
    for row_number, cells in enumerate(raw_rows[1:], start=2):
        _docs_require(len(cells) == len(headers), claim_id,
                      f"{path}: row {row_number} has {len(cells)} cells; expected {len(headers)}")
        rows.append(dict(zip(headers, cells, strict=True)))
    return headers, rows


def _field_names(header: str, type_name: str) -> list[str]:
    ending = re.search(rf"\}}\s*{re.escape(type_name)}\s*;", header)
    if ending is None:
        raise SaveDocsError("save.docs-api", f"public header lacks record {type_name}")
    start = header.rfind("typedef struct", 0, ending.start())
    opening = header.find("{", start, ending.start())
    if start < 0 or opening < 0:
        raise SaveDocsError("save.docs-api", f"public header lacks record body {type_name}")
    body = header[opening + 1:ending.start()]
    fields = []
    for declaration in body.split(";"):
        declaration = declaration.strip()
        if not declaration:
            continue
        field = re.search(r"([A-Za-z_]\w*)(\[[^\]]+\])?\s*$", declaration)
        if field is not None:
            fields.append(field.group(1) + (field.group(2) or ""))
    return fields


def _normalize_declaration(value: str) -> str:
    value = _clean_cell(value).replace("GN_API ", "")
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"\(\s+", "(", value)


def _public_signatures(header: str) -> dict[str, str]:
    signatures = {}
    for declaration in re.findall(r"GN_API\s+([^;]+);", header, flags=re.DOTALL):
        normalized = _normalize_declaration(declaration + ";")
        name = re.search(r"([A-Za-z_]\w*)\s*\(", normalized)
        if name is not None:
            signatures[name.group(1)] = normalized
    return signatures


def _integer_macro(header: str, name: str) -> int:
    match = re.search(rf"^#define\s+{re.escape(name)}\s+([^\n]+)",
                      header, flags=re.MULTILINE)
    if match is None:
        raise SaveDocsError("save.docs-envelope", f"public header lacks {name}")
    literal = re.search(
        r"(?:UINT32_C\s*\(\s*|\(size_t\)\s*)(0x[0-9a-fA-F]+|\d+)",
        match.group(1),
    )
    if literal is None:
        raise SaveDocsError("save.docs-envelope", f"{name} has no literal value")
    return int(literal.group(1), 0)


def _check_api_docs(
    documents: dict[str, str], header: str, source: str,
    observations: dict[str, object]
) -> int:
    path = "docs/native-save.md"
    headers, rows = _read_table(documents[path], "Public records and operations",
                                path, "save.docs-api")
    _docs_require(headers == ["Kind", "Name", "Fields or declaration", "Bytes / contract"],
                  "save.docs-api", f"{path}: declaration table headings changed")
    by_kind_name = {}
    for row in rows:
        key = (_clean_cell(row["Kind"]), _clean_cell(row["Name"]))
        _docs_require(key not in by_kind_name, "save.docs-api",
                      f"{path}: duplicate row {key[0]} {key[1]}")
        by_kind_name[key] = row

    record_sizes = {
        "gn_mvs_save_scope_v1": int(observations["scope_bytes"]),
        "gn_mvs_save_receipt_v1": int(observations["receipt_bytes"]),
        "gn_mvs_save_info_v1": int(observations["info_bytes"]),
        "gn_mvs_save_detail_v1": int(observations["detail_bytes"]),
        "gn_mvs_save_lifecycle_result_v1":
            _save_record_sizes_from_source(source)["gn_mvs_save_lifecycle_result_v1"],
    }
    record_count = 0
    for type_name, size in record_sizes.items():
        row = by_kind_name.get(("record", type_name))
        _docs_require(row is not None, "save.docs-api",
                      f"{path}: missing record row {type_name}")
        fields = [_clean_cell(value.strip()) for value in
                  row["Fields or declaration"].split(",")]
        expected_fields = _field_names(header, type_name)
        _docs_require(fields == expected_fields, "save.docs-api",
                      f"{path} row {type_name}: fields {fields!r}; expected {expected_fields!r}")
        row_size = re.match(r"\s*(\d+)", row["Bytes / contract"])
        _docs_require(row_size is not None and int(row_size.group(1)) == size,
                      "save.docs-api",
                      f"{path} row {type_name}: documented size differs from observed {size}")
        record_count += len(expected_fields)

    signatures = _public_signatures(header)
    save_api_names = {
        "gn_mvs_save_query_v1", "gn_mvs_save_export_v1",
        "gn_mvs_save_import_baseline_v1", "gn_mvs_save_ack_v1",
        "gn_mvs_save_scope_renew_v1", "gn_mvs_save_reason_string",
        "gn_load_mvs_v3_checked_v1", "gn_unload_checked_v1",
        "gn_destroy_checked_v1",
    }
    legacy_names = {"gn_load", "gn_load_mvs", "gn_load_mvs_v3",
                    "gn_unload", "gn_destroy"}
    for kind, names in (("api", save_api_names), ("legacy", legacy_names)):
        listed = {name for row_kind, name in by_kind_name if row_kind == kind}
        _docs_require(listed == names, "save.docs-api",
                      f"{path}: {kind} rows differ; missing={sorted(names - listed)}, extra={sorted(listed - names)}")
        for name in names:
            row = by_kind_name[(kind, name)]
            actual = signatures.get(name)
            _docs_require(actual is not None, "save.docs-api",
                          f"public header lacks declaration for {name}")
            documented = _normalize_declaration(row["Fields or declaration"])
            _docs_require(documented == actual, "save.docs-api",
                          f"{path} row {name}: declaration {documented!r}; header has {actual!r}")

    compatibility = by_kind_name.get(("compatibility", "durable_save_id"))
    _docs_require(compatibility is not None and "1 for supported MVS MSX" in
                  compatibility["Bytes / contract"] and "0 for diagnostic" in
                  compatibility["Bytes / contract"], "save.docs-api",
                  f"{path}: durable_save_id must distinguish MVS from diagnostic")
    compatibility_body = _c_function_body(
        source, "gn_state_compatibility_v1", "save.docs-api")
    query_body = _c_function_body(source, "gn_mvs_save_query_v1", "save.docs-api")
    _docs_require("image->profile == GN_MVS_PROFILE_MSX" in compatibility_body and
                  "? GN_MVS_SAVE_ID_V1 : 0u" in compatibility_body and
                  "memset(out_info, 0, sizeof(*out_info))" in query_body and
                  "out_info->supported = 1u" in query_body and
                  "out_info->save_id = GN_MVS_SAVE_ID_V1" in query_body,
                  "save.docs-api", "implementation support/save ID does not match the table")
    native_state = "docs/native-state.md"
    _, compatibility_rows = _read_table(
        documents[native_state], "Durable save compatibility field",
        native_state, "save.docs-api")
    profile_rows = { _clean_cell(row["Loaded profile"]): row
                     for row in compatibility_rows }
    _docs_require(len(profile_rows) == len(compatibility_rows) == 3 and
                  profile_rows.get("GN_MVS_PROFILE_MSX") is not None and
                  profile_rows["GN_MVS_PROFILE_MSX"]["durable_save_id"] == "1" and
                  profile_rows.get("GN_PROFILE_DIAGNOSTIC") is not None and
                  profile_rows["GN_PROFILE_DIAGNOSTIC"]["durable_save_id"] == "0" and
                  profile_rows.get("Unsupported profile") is not None and
                  profile_rows["Unsupported profile"]["durable_save_id"] == "—" and
                  "rejects" in profile_rows["Unsupported profile"]["Meaning"].lower(),
                  "save.docs-api", f"{native_state}: compatibility table contradicts the profile IDs")

    reason_headers, reason_rows = _read_table(
        documents[path], "Numeric save reasons", path, "save.docs-api")
    _docs_require(reason_headers == ["Reason", "Value"], "save.docs-api",
                  f"{path}: save reason table headings changed")
    try:
        documented_reasons = {_clean_cell(row["Reason"]): int(row["Value"])
                              for row in reason_rows}
    except ValueError as error:
        raise SaveDocsError("save.docs-api",
                            f"{path}: numeric save reason is not an integer") from error
    actual_reasons = {
        name: int(value) for name, value in re.findall(
            r"GN_MVS_SAVE_REASON_(\w+)\s*=\s*UINT32_C\((\d+)\)", header)
    }
    _docs_require(len(documented_reasons) == len(reason_rows) and
                  documented_reasons == actual_reasons, "save.docs-api",
                  f"{path}: reason values differ from public header")
    return record_count + len(save_api_names) + len(legacy_names) + len(reason_rows) + 1


def _check_envelope_docs(
    documents: dict[str, str], header: str, source: str,
    observations: dict[str, object]
) -> int:
    path = "docs/native-save.md"
    headers, rows = _read_table(documents[path], "GNSV v1 envelope", path,
                                "save.docs-envelope")
    _docs_require(headers == ["Offset", "Length", "Field", "Value"],
                  "save.docs-envelope", f"{path}: envelope table headings changed")
    by_field = {}
    for row in rows:
        field = _clean_cell(row["Field"])
        _docs_require(field not in by_field, "save.docs-envelope",
                      f"{path}: duplicate envelope row {field}")
        by_field[field] = row
    expected_layout = {
        "Magic": ("0", "4"), "Envelope version": ("4", "4"),
        "Header length": ("8", "4"), "Total length": ("12", "4"),
        "SRAM payload length": ("16", "4"), "Durable save identity": ("20", "4"),
        "Profile": ("24", "4"), "Reserved": ("28", "4"),
        "Normalized media identity": ("32", "32"),
        "Envelope digest": ("64", "32"), "Digest domain": ("domain", "20"),
        "MVS backup RAM": ("96", "65,536"),
    }
    _docs_require(set(by_field) == set(expected_layout), "save.docs-envelope",
                  f"{path}: envelope rows missing or extra: expected {sorted(expected_layout)}")
    for field, (offset, length) in expected_layout.items():
        row = by_field[field]
        _docs_require(row["Offset"] == offset and row["Length"] == length,
                      "save.docs-envelope",
                      f"{path} row {field}: documented {row['Offset']}/{row['Length']}; expected {offset}/{length}")

    version = _integer_macro(header, "GN_MVS_SAVE_FORMAT_V1_VERSION")
    header_bytes = _integer_macro(header, "GN_MVS_SAVE_HEADER_V1_BYTES")
    payload_bytes = _integer_macro(header, "GN_MVS_SAVE_PAYLOAD_V1_BYTES")
    save_id = _integer_macro(header, "GN_MVS_SAVE_ID_V1")
    profile = _integer_macro(header, "GN_MVS_PROFILE_MSX")
    envelope_bytes = header_bytes + payload_bytes
    expected_values = {
        "Magic": "GNSV", "Envelope version": str(version),
        "Header length": str(header_bytes), "Total length": f"{envelope_bytes:,}",
        "SRAM payload length": f"{payload_bytes:,}",
        "Durable save identity": str(save_id),
        "Reserved": "zero", "Digest domain": "Glueyneo MVS save v1",
    }
    for field, expected in expected_values.items():
        row_value = _clean_cell(by_field[field]["Value"]).replace(",", "")
        expected_clean = expected.replace(",", "")
        _docs_require(expected_clean.lower() in row_value.lower(),
                      "save.docs-envelope",
                      f"{path} row {field}: expected value {expected!r}, observed {row_value!r}")
    _docs_require("no terminating NUL" in by_field["Digest domain"]["Value"],
                  "save.docs-envelope", f"{path}: digest domain must exclude a terminating NUL")
    _docs_require("GN_MVS_PROFILE_MSX" in by_field["Profile"]["Value"],
                  "save.docs-envelope", f"{path}: MVS profile ID macro is missing")

    envelope = observations["envelopes"][0]
    _docs_require(isinstance(envelope, bytes) and len(envelope) == envelope_bytes,
                  "save.docs-envelope", "observed exported envelope length differs from header constants")
    actual_version, actual_header, actual_total, actual_payload, actual_id = struct.unpack(
        ">IIIII", envelope[4:24])
    actual_profile, actual_reserved = struct.unpack(">II", envelope[24:32])
    _docs_require((actual_version, actual_header, actual_total, actual_payload,
                   actual_id, actual_profile, actual_reserved) ==
                  (version, header_bytes, envelope_bytes, payload_bytes,
                   save_id, profile, 0), "save.docs-envelope",
                  "exported header bytes differ from the public constants")
    domain = b"Glueyneo MVS save v1"
    _docs_require(domain.decode("ascii") in source and
                  hashlib.sha256(domain + envelope[:64] + envelope[96:]).digest() ==
                  envelope[64:96], "save.docs-envelope",
                  "source digest domain or exported envelope digest differs")
    _docs_require(envelope[32:64] == observations["media_identities"][0] and
                  len(envelope[96:]) == payload_bytes,
                  "save.docs-envelope", "media identity or payload bytes differ from the observed export")
    _docs_require(int(observations["envelope_bytes"]) == envelope_bytes and
                  int(observations["payload_bytes"]) == payload_bytes,
                  "save.docs-envelope", "SAVE_OBSERVATION lengths differ from constants")
    return len(expected_layout)


def _c_function_body(source: str, name: str, claim_id: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*\(", source)
    _docs_require(match is not None, claim_id, f"implementation lacks function {name}")
    opening = source.find("{", match.end())
    _docs_require(opening >= 0, claim_id, f"implementation lacks body for {name}")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise SaveDocsError(claim_id, f"implementation body for {name} is unterminated")


def _check_lifecycle_docs(
    documents: dict[str, str], source: str,
    observations: dict[str, object] | None,
) -> int:
    path = "docs/native-save.md"
    headers, rows = _read_table(documents[path], "Ownership and lifecycle",
                                path, "save.docs-ownership")
    _docs_require(headers == ["Event", "Core state effect", "Required host/core rule"],
                  "save.docs-ownership", f"{path}: lifecycle table headings changed")
    by_event = {_clean_cell(row["Event"]): row for row in rows}
    expected_events = {
        "Successful MVS load", "Effective changed unlocked byte or word store",
        "MVS reset or watchdog reset", "Valid startup baseline import",
        "First guest execution", "Successful full continuation restore",
        "Successful export", "Successful ACK",
        "Rejected import, restore, or ACK",
        "Successful load replacement, unload, or destroy",
        "Checked lifecycle transition",
    }
    _docs_require(set(by_event) == expected_events and len(rows) == len(expected_events),
                  "save.docs-ownership", f"{path}: lifecycle event rows are missing, duplicated, or extra")
    fragments = {
        "Successful MVS load": ("load_generation", "startup import"),
        "Effective changed unlocked byte or word store": ("dirty", "mutation_sequence", "same-value"),
        "MVS reset or watchdog reset": ("preserves sram", "does not reopen"),
        "Valid startup baseline import": ("baseline", "repeat", "before first guest"),
        "First guest execution": ("permanently closes",),
        "Successful full continuation restore": ("dirty", "restore_branch", "invalidates"),
        "Successful export": ("export_sequence", "leaves dirty"),
        "Successful ACK": ("latest current receipt", "clears dirty"),
        "Rejected import, restore, or ACK": ("does not copy", "cannot clear dirty"),
        "Successful load replacement, unload, or destroy": ("ends", "resolve host work"),
        "Checked lifecycle transition": ("require_resolved", "allow_discard", "failed replacement"),
    }
    for event, needles in fragments.items():
        content = " ".join(by_event[event].values()).lower()
        for needle in needles:
            _docs_require(needle in content, "save.docs-ownership",
                          f"{path} row {event}: missing required statement {needle!r}")

    owner_path = "docs/ownership-and-errors.md"
    _, owner_rows = _read_table(documents[owner_path], "MVS durable save boundaries",
                                owner_path, "save.docs-ownership")
    owner_operations = {_clean_cell(row["Operation"]): row for row in owner_rows}
    expected_owner_operations = {
        "Successful MVS load", "MVS reset or watchdog reset", "First guest execution",
        "Valid startup import", "Successful GNST continuation restore",
        "Rejected GNST restore", "GNSV export", "Receipt ACK",
        "Successful load replacement, unload, or destroy",
        "Checked lifecycle transition",
    }
    _docs_require(set(owner_operations) == expected_owner_operations and
                  len(owner_operations) == len(owner_rows),
                  "save.docs-ownership", f"{owner_path}: lifecycle rows missing or changed")
    _docs_require("does not clear dirty" in owner_operations["MVS reset or watchdog reset"][
                      "Ownership or error effect"].lower() and
                  "does not reopen" in owner_operations["MVS reset or watchdog reset"][
                      "Ownership or error effect"].lower(),
                  "save.docs-ownership", f"{owner_path}: reset contradicts save owner")

    load_body = _c_function_body(source, "gn_mvs_save_load_committed", "save.docs-ownership")
    mutation_body = _c_function_body(source, "gn_mvs_save_guest_mutation", "save.docs-ownership")
    restore_body = _c_function_body(source, "gn_mvs_save_restore_committed", "save.docs-ownership")
    startup_body = _c_function_body(source, "gn_mvs_save_close_startup", "save.docs-ownership")
    import_body = _c_function_body(source, "gn_mvs_save_import_baseline_v1", "save.docs-ownership")
    export_body = _c_function_body(source, "gn_mvs_save_export_v1", "save.docs-ownership")
    ack_body = _c_function_body(source, "gn_mvs_save_ack_v1", "save.docs-ownership")
    restore_apply = _c_function_body(source, "gn_state_restore_mvs", "save.docs-ownership")
    load_apply = _c_function_body(source, "gn_load_mvs_regions", "save.docs-ownership")
    candidate_commit = _c_function_body(source, "gn_mvs_candidate_commit", "save.docs-ownership")
    _docs_require("save->startup_import_allowed = 1u" in load_body and
                  "++save->load_generation" in load_body and
                  "save->dirty = 0u" in load_body,
                  "save.docs-ownership", "load owner hook disagrees with documented lifecycle")
    _docs_require("save->dirty = 1u" in mutation_body and
                  "++save->mutation_sequence" in mutation_body and
                  source.count("gn_mvs_save_guest_mutation(image)") >= 2,
                  "save.docs-ownership", "effective byte/word mutation hooks are not wired")
    _docs_require("++save->restore_branch" in restore_body and
                  "save->dirty = 1u" in restore_body and
                  "gn_mvs_save_restore_committed(image)" in restore_apply,
                  "save.docs-ownership", "restore branch hook is missing from successful apply")
    _docs_require("startup_import_allowed = 0u" in startup_body and
                  "save->startup_import_allowed = 0u" not in import_body and
                  "save->baseline_known = 1u" in import_body,
                  "save.docs-ownership", "startup gate/import implementation differs")
    _docs_require("save->dirty = 0u" not in export_body and
                  "save->dirty = 0u" in ack_body and
                  "save->receipt_consumed = 1u" in ack_body and
                  "candidate->save_owner = instance" in candidate_commit and
                  "gn_mvs_candidate_commit(instance, candidate)" in load_apply,
                  "save.docs-ownership", "export, ACK, or candidate owner binding differs")

    if observations is not None:
        writer = observations["writers"][0]
        reader = observations["readers"][0]
        _docs_require(writer["after_guest_dirty"] == 1 and
                      writer["after_export_dirty"] == 1 and
                      writer["after_ack_dirty"] == 0 and
                      writer["after_ack_baseline_known"] == 1 and
                      writer["receipt_mutation_sequence"] == 4 and
                      writer["restore_branched"] == 1 and
                      writer["reset_preserved_sram"] == 1 and
                      writer["stale_ack_preserved_dirty"] == 1,
                      "save.docs-ownership", "writer observation contradicts lifecycle table")
        _docs_require(reader["after_import_baseline_known"] == 1 and
                      reader["after_guest_dirty"] == 0 and
                      reader["after_guest_startup_import_allowed"] == 0,
                      "save.docs-ownership", "fresh-reader observation contradicts import gate table")
    return len(expected_events) + len(expected_owner_operations) + (8 if observations else 0)


def _check_snapshot_docs(
    documents: dict[str, str], source: str
) -> int:
    path = "docs/state-inventory.md"
    headers, rows = _read_table(documents[path], "MVS save lineage and snapshot exclusion",
                                path, "save.docs-ownership")
    _docs_require(headers == ["Owner item", "Class", "GNST snapshot bytes",
                              "GNSV durable bytes", "Restore or lifecycle effect"],
                  "save.docs-ownership", f"{path}: snapshot exclusion table headings changed")
    by_item = {_clean_cell(row["Owner item"]): row for row in rows}
    expected = {
        "gn_instance.mvs_save and its listed fields": ("No", "No"),
        "gn_image.save_owner": ("No", "No"),
        "gn_image.mvs_save_ram contents": ("Yes, MVS memory section",
                                             "Yes, exact 65,536-byte GNSV payload"),
    }
    _docs_require(set(by_item) == set(expected), "save.docs-ownership",
                  f"{path}: save owner or SRAM inventory row is missing")
    _docs_require(len(by_item) == len(rows), "save.docs-ownership",
                  f"{path}: duplicate snapshot-inventory rows")
    for item, (snapshot, durable) in expected.items():
        row = by_item[item]
        _docs_require(row["GNST snapshot bytes"] == snapshot and
                      row["GNSV durable bytes"] == durable,
                      "save.docs-ownership", f"{path} row {item}: snapshot/durable boundary differs")
    effects = {
        "gn_instance.mvs_save and its listed fields":
            "Dirty/baseline status and nonrewinding receipt lineage remain on the instance; successful restore branches lineage after apply",
        "gn_image.save_owner":
            "Candidate commit binds the destination instance; image restore retains its destination link",
        "gn_image.mvs_save_ram contents":
            "Snapshot restore may restore historical SRAM and marks save state dirty; neither restore nor export is a host disk commit",
    }
    for item, expected_effect in effects.items():
        actual_effect = " ".join(by_item[item]["Restore or lifecycle effect"].split())
        _docs_require(actual_effect == expected_effect, "save.docs-ownership",
                      f"{path} row {item}: lifecycle effect differs; expected={expected_effect!r} observed={actual_effect!r}")
    _, inventory_rows = _read_table(documents[path], "Image and instance ownership (`src/instance.c`)",
                                    path, "save.docs-ownership")
    owner_rows = [row for row in inventory_rows
                  if "gn_instance.mvs_save (" in
                  _clean_cell(row["Structure and fields"])]
    hook_rows = [row for row in inventory_rows
                 if _clean_cell(row["Structure and fields"]) == "gn_image.save_owner"]
    owner_row = owner_rows[0] if owner_rows else None
    save_ram_rows = [row for row in inventory_rows
                     if _clean_cell(row["Structure and fields"]) ==
                     "gn_image.mvs_work_ram, .mvs_work_ram_size; .mvs_save_ram, .mvs_save_ram_size; .mvs_palette_ram, .mvs_palette_ram_size; .mvs_video_ram, .mvs_video_ram_words"]
    _docs_require(len(owner_rows) == 1 and len(hook_rows) == 1 and
                  len(save_ram_rows) == 1 and owner_row is not None,
                  "save.docs-ownership", f"{path}: detailed owner-field inventory is incomplete")
    owner_fields_match = re.search(
        r"gn_instance\.mvs_save\s*\(([^)]*)\)",
        _clean_cell(owner_row["Structure and fields"]),
    )
    documented_fields = [] if owner_fields_match is None else [
        _clean_cell(field.strip()) for field in owner_fields_match.group(1).split(",")
    ]
    actual_fields = _field_names(source, "gn_mvs_save_ownership")
    _docs_require(documented_fields == actual_fields,
                  "save.docs-ownership",
                  f"{path}: ownership fields differ; documented={documented_fields!r}, actual={actual_fields!r}")
    detailed_rows = {
        "gn_image.save_owner": (
            "Host/non-owned ownership hook",
            "Bound to the owning `gn_instance` only when the initialized image candidate is committed. It is not copied into snapshots or durable bytes; restore keeps the destination image link."),
        "gn_instance.mvs_save": (
            "Host lifecycle/ownership",
            "Per-instance save lineage, startup gate, and receipt-consumption state. Explicitly absent from GNST snapshots and GNSV durable bytes. A successful continuation restore updates this owner only after validated apply; rejected restore leaves it unchanged."),
    }
    for row in hook_rows + owner_rows:
        key = _clean_cell(row["Structure and fields"])
        key = "gn_instance.mvs_save" if key.startswith("gn_instance.mvs_save (") else key
        expected_class, expected_effect = detailed_rows[key]
        _docs_require(_clean_cell(row["Class"]) == expected_class and
                      " ".join(row["Current encoding, validation, or reconstruction"].split()) ==
                      expected_effect, "save.docs-ownership",
                      f"{path} row {key}: detailed ownership claim differs")
    save_ram_row = save_ram_rows[0]
    _docs_require(_clean_cell(save_ram_row["Class"]) == "Host + Guest" and
                  " ".join(save_ram_row[
                      "Current encoding, validation, or reconstruction"].split()) ==
                  "Pointers and extents remain destination-owned. GNST memory section copies exact work/save/palette bytes and explicit big-endian video words into those same allocations. GNSV separately exports only the 65,536 backup-RAM bytes. Successful and rejected restore preserve the backup-RAM address.",
                  "save.docs-ownership",
                  f"{path}: detailed SRAM ownership claim differs")
    image_end = source.find("} gn_image;")
    image_start = source.rfind("typedef struct", 0, image_end) if image_end >= 0 else -1
    image_body = source[image_start:image_end] if image_start >= 0 else ""
    instance_struct = re.search(r"struct gn_instance\s*\{(?P<body>.*?)\};",
                                source, re.DOTALL)
    _docs_require("gn_instance *save_owner;" in image_body and instance_struct is not None and
                  "gn_mvs_save_ownership mvs_save;" in instance_struct.group("body"),
                  "save.docs-ownership", "implementation owner fields differ from the inventory")
    encode_mvs = _c_function_body(source, "gn_state_encode_mvs_image", "save.docs-ownership")
    encode_diagnostic = _c_function_body(source, "gn_state_encode_image", "save.docs-ownership")
    load_mvs = _c_function_body(source, "gn_mvs_candidate_commit", "save.docs-ownership")
    restore_mvs = _c_function_body(source, "gn_state_restore_mvs", "save.docs-ownership")
    _docs_require("image->mvs_save_ram" in encode_mvs and
                  not re.search(r"\bimage->save_owner\b|\binstance->mvs_save\b", encode_mvs) and
                  not re.search(r"\bimage->save_owner\b|\binstance->mvs_save\b", encode_diagnostic),
                  "save.docs-ownership", "serialized state fields contradict the inventory")
    _docs_require("candidate->save_owner = instance" in load_mvs and
                  "gn_mvs_save_restore_committed(image)" in restore_mvs,
                  "save.docs-ownership", "non-owned owner link or post-restore hook is missing")
    return len(expected) + len(effects) + 2


def _normalized_contract_cell(value: str) -> str:
    return " ".join(_clean_cell(value).split())


def _check_exact_doc_rows(
    documents: dict[str, str], path: str, heading: str, headers: list[str],
    key_columns: tuple[str, ...], expected_rows: list[dict[str, str]], claim_id: str,
) -> int:
    actual_headers, rows = _read_table(documents[path], heading, path, claim_id)
    _docs_require(actual_headers == headers, claim_id,
                  f"{path}: {heading} table headings changed")
    actual_keys = [tuple(_clean_cell(row[column]) for column in key_columns) for row in rows]
    expected_keys = [tuple(_clean_cell(row[column]) for column in key_columns)
                     for row in expected_rows]
    _docs_require(len(set(actual_keys)) == len(actual_keys), claim_id,
                  f"{path}: {heading} contains duplicate keys")
    _docs_require(actual_keys == expected_keys, claim_id,
                  f"{path}: {heading} inventory is missing, duplicated, extra, or reordered")
    for actual, expected in zip(rows, expected_rows, strict=True):
        key = tuple(_clean_cell(expected[column]) for column in key_columns)
        for column in headers:
            expected_value = _normalized_contract_cell(expected[column])
            actual_value = _normalized_contract_cell(actual[column])
            _docs_require(actual_value == expected_value, claim_id,
                          f"{path} {heading} row {key!r}, cell {column!r} differs: "
                          f"expected={expected_value!r} observed={actual_value!r}")
    return len(rows) * len(headers)


def _save_record_sizes_from_source(source: str) -> dict[str, int]:
    sizes = {}
    for type_name in (
        "gn_mvs_save_scope_v1", "gn_mvs_save_receipt_v1",
        "gn_mvs_save_info_v1", "gn_mvs_save_detail_v1",
        "gn_mvs_save_lifecycle_result_v1",
    ):
        match = re.search(
            rf"_Static_assert\s*\(\s*sizeof\s*\(\s*{re.escape(type_name)}\s*\)\s*==\s*(\d+)u?",
            source,
        )
        _docs_require(match is not None, "save.docs-api",
                      f"implementation lacks the fixed ABI size assertion for {type_name}")
        sizes[type_name] = int(match.group(1))
    return sizes


def _portable_save_measurement_observations(
    fixture: dict[str, object], source_identity: str
) -> dict[str, object]:
    oracle = fixture["oracle"]
    artifact = fixture["artifact"]
    recipe = fixture["recipe"]
    generator = fixture["generator_source"]
    stages = list(oracle["process_interruption_stages"])
    histories = (False, True)
    recovery = [{"stage": stage, "prior_a": prior_a}
                for prior_a in histories for stage in stages]
    return {
        "fixture_bytes": int(recipe["artifact_bytes"]),
        "fixture_sha256": str(artifact["sha256"]),
        "shared_media_identity": bool(oracle["shared_media_identity_a_b"]),
        "host_stage_trace": str(oracle["host_stage_trace"]),
        "recovery_kill_cases": recovery,
        "writers": [{} for _ in range(int(oracle["writer_reader_process_pairs"]))],
        "child_timeout_seconds": int(oracle["child_timeout_bound_seconds"]),
        "child_output_bound_bytes": int(oracle["child_output_bound_bytes"]),
        "host_identity": str(oracle["measured_host"]),
        "save_source_identity_sha256": source_identity,
        "guest_fixture_source_sha256": str(generator["sha256"]),
        "build_identity": str(oracle["build_identity"]),
        "supported_sync_operations":
            "F_FULLFSYNC, checked file close, atomic rename, directory fsync, and directory close",
        "host_fault_cases":
            f"{int(oracle['host_fault_matrix_cases'])} (9 syscall stages × first-create and A-to-B replacement)",
        "unsupported_host_protocol": str(oracle["unsupported_host_protocol"]),
    }


def _synthetic_envelope_observations(header: str, source: str) -> dict[str, object]:
    version = _integer_macro(header, "GN_MVS_SAVE_FORMAT_V1_VERSION")
    header_bytes = _integer_macro(header, "GN_MVS_SAVE_HEADER_V1_BYTES")
    payload_bytes = _integer_macro(header, "GN_MVS_SAVE_PAYLOAD_V1_BYTES")
    save_id = _integer_macro(header, "GN_MVS_SAVE_ID_V1")
    total_bytes = header_bytes + payload_bytes
    profile = _integer_macro(header, "GN_MVS_PROFILE_MSX")
    _docs_require(total_bytes == header_bytes + payload_bytes,
                  "save.docs-envelope", "header total length does not equal header plus payload")
    envelope = bytearray(total_bytes)
    envelope[:4] = b"GNSV"
    struct.pack_into(">IIIIIII", envelope, 4, version, header_bytes, total_bytes,
                     payload_bytes, save_id, profile, 0)
    media_identity = bytes(32)
    envelope[32:64] = media_identity
    domain = b"Glueyneo MVS save v1"
    _docs_require(domain.decode("ascii") in source, "save.docs-envelope",
                  "implementation omitted the exact v1 digest domain")
    envelope[64:96] = hashlib.sha256(domain + envelope[:64] + envelope[96:]).digest()
    return {"envelopes": [bytes(envelope)], "media_identities": [media_identity],
            "envelope_bytes": total_bytes, "payload_bytes": payload_bytes}


def check_save_contract_docs(
    documents: dict[str, str], header: str, source: str,
    fixture_manifest: dict[str, object], source_identity: str,
) -> dict[str, int]:
    """Validate the exact four-document contract on portable and measured hosts."""
    try:
        fixture = fixture_manifest["mvs_save_fixture"]
        oracle = fixture["oracle"]
        recipe = fixture["recipe"]
        artifact = fixture["artifact"]
        generator = fixture["generator_source"]
        host_trace = str(oracle["host_stage_trace"])
        manifest_stages = list(oracle["process_interruption_stages"])
    except (KeyError, TypeError) as error:
        raise SaveDocsError("save.docs-measurements", "save rights manifest lacks contract evidence") from error

    counts = check_portable_save_contract_docs(documents, source)
    native = "docs/native-save.md"
    identity = _public_signatures(header)
    sizes = _save_record_sizes_from_source(source)
    api_contracts = {
        "gn_mvs_save_scope_v1": "nonzero host-issued scope, never reused across instance lifetimes",
        "gn_mvs_save_receipt_v1": "exact tuple for one successful export",
        "gn_mvs_save_info_v1": "current support and ownership state",
        "gn_mvs_save_detail_v1": "numeric diagnostics only",
        "gn_mvs_save_lifecycle_result_v1": "reports core SRAM discarded by a successful checked transition; never claims host durability",
        "gn_mvs_save_query_v1": "Queries save support and lineage without running the guest or doing I/O",
        "gn_mvs_save_export_v1": "Writes one canonical envelope and issues the latest receipt only after success; export does not clear dirty state",
        "gn_mvs_save_import_baseline_v1": "Validates the full envelope, then copies its payload as the authoritative startup baseline",
        "gn_mvs_save_ack_v1": "Consumes the exact latest unconsumed receipt after the host commit completes",
        "gn_mvs_save_scope_renew_v1": "Binds a caller-issued nonzero scope; the host promises lifetime nonreuse",
        "gn_mvs_save_reason_string": "Static fixed text; unknown values return fixed generic text",
        "gn_load_mvs_v3_checked_v1": "Stages and validates a replacement image before applying the selected pending-save policy",
        "gn_unload_checked_v1": "Unloads only after the selected pending-save policy succeeds",
        "gn_destroy_checked_v1": "Destroys and clears the caller handle only after the selected policy succeeds",
        "gn_load": "Successful image replacement discards the previous save lineage",
        "gn_load_mvs": "Successful image replacement discards the previous save lineage",
        "gn_load_mvs_v3": "Successful image replacement discards the previous save lineage",
        "gn_unload": "Unload ends the current image and save lineage",
        "gn_destroy": "Destruction ends the instance and save lineage",
        "durable_save_id": "1 for supported MVS MSX; 0 for diagnostic; unsupported profiles are rejected",
    }
    api_headers, api_rows = _read_table(documents[native], "Public records and operations",
                                       native, "save.docs-api")
    _docs_require(api_headers == ["Kind", "Name", "Fields or declaration", "Bytes / contract"],
                  "save.docs-api", f"{native}: public record/API table headings changed")
    expected_api = []
    for name in ("gn_mvs_save_scope_v1", "gn_mvs_save_receipt_v1",
                 "gn_mvs_save_info_v1", "gn_mvs_save_detail_v1",
                 "gn_mvs_save_lifecycle_result_v1"):
        fields = ", ".join(_field_names(header, name))
        expected_api.append({"Kind": "record", "Name": name,
                             "Fields or declaration": fields,
                             "Bytes / contract": f"{sizes[name]}; {api_contracts[name]}"})
    for name in ("gn_mvs_save_query_v1", "gn_mvs_save_export_v1",
                 "gn_mvs_save_import_baseline_v1", "gn_mvs_save_ack_v1",
                 "gn_mvs_save_scope_renew_v1", "gn_mvs_save_reason_string",
                 "gn_load_mvs_v3_checked_v1", "gn_unload_checked_v1",
                 "gn_destroy_checked_v1"):
        expected_api.append({"Kind": "api", "Name": name,
                             "Fields or declaration": identity[name],
                             "Bytes / contract": api_contracts[name]})
    for name in ("gn_load", "gn_load_mvs", "gn_load_mvs_v3", "gn_unload", "gn_destroy"):
        expected_api.append({"Kind": "legacy", "Name": name,
                             "Fields or declaration": identity[name],
                             "Bytes / contract": api_contracts[name]})
    expected_api.append({"Kind": "compatibility", "Name": "durable_save_id",
                         "Fields or declaration": "gn_state_compatibility_info_v1.durable_save_id",
                         "Bytes / contract": api_contracts["durable_save_id"]})
    counts[native] = _check_exact_doc_rows(
        documents, native, "Public records and operations", api_headers,
        ("Kind", "Name"), expected_api, "save.docs-api")
    sizes_observation = {"scope_bytes": sizes["gn_mvs_save_scope_v1"],
                         "receipt_bytes": sizes["gn_mvs_save_receipt_v1"],
                         "info_bytes": sizes["gn_mvs_save_info_v1"],
                         "detail_bytes": sizes["gn_mvs_save_detail_v1"]}
    counts["save.docs-api"] = counts.get("save.docs-api", 0) + _check_api_docs(
        documents, header, source, sizes_observation)

    reason_values = [(name, int(value)) for name, value in re.findall(
        r"GN_MVS_SAVE_REASON_(\w+)\s*=\s*UINT32_C\((\d+)\)", header)]
    expected_reasons = [{"Reason": name, "Value": str(value)}
                        for name, value in reason_values]
    counts[native] += _check_exact_doc_rows(
        documents, native, "Numeric save reasons", ["Reason", "Value"],
        ("Reason",), expected_reasons, "save.docs-api")

    version = _integer_macro(header, "GN_MVS_SAVE_FORMAT_V1_VERSION")
    header_bytes = _integer_macro(header, "GN_MVS_SAVE_HEADER_V1_BYTES")
    payload_bytes = _integer_macro(header, "GN_MVS_SAVE_PAYLOAD_V1_BYTES")
    total_bytes = header_bytes + payload_bytes
    save_id = _integer_macro(header, "GN_MVS_SAVE_ID_V1")
    envelope_rows = [
        {"Offset": "0", "Length": "4", "Field": "Magic", "Value": "ASCII `GNSV`"},
        {"Offset": "4", "Length": "4", "Field": "Envelope version", "Value": f"`GN_MVS_SAVE_FORMAT_V1_VERSION` ({version})"},
        {"Offset": "8", "Length": "4", "Field": "Header length", "Value": f"`GN_MVS_SAVE_HEADER_V1_BYTES` ({header_bytes})"},
        {"Offset": "12", "Length": "4", "Field": "Total length", "Value": f"`GN_MVS_SAVE_ENVELOPE_V1_BYTES` ({total_bytes:,})"},
        {"Offset": "16", "Length": "4", "Field": "SRAM payload length", "Value": f"`GN_MVS_SAVE_PAYLOAD_V1_BYTES` ({payload_bytes:,})"},
        {"Offset": "20", "Length": "4", "Field": "Durable save identity", "Value": f"`GN_MVS_SAVE_ID_V1` ({save_id})"},
        {"Offset": "24", "Length": "4", "Field": "Profile", "Value": "`GN_MVS_PROFILE_MSX`"},
        {"Offset": "28", "Length": "4", "Field": "Reserved", "Value": "Zero"},
        {"Offset": "32", "Length": "32", "Field": "Normalized media identity", "Value": "SHA-256 identity cached for the loaded MVS image"},
        {"Offset": "64", "Length": "32", "Field": "Envelope digest", "Value": "SHA-256 of domain bytes, header bytes `[0,64)`, and payload bytes `[96,65632)"},
        {"Offset": "domain", "Length": "20", "Field": "Digest domain", "Value": "ASCII `Glueyneo MVS save v1`; no terminating NUL"},
        {"Offset": "96", "Length": f"{payload_bytes:,}", "Field": "MVS backup RAM", "Value": "Exact canonical byte-addressed SRAM contents"},
    ]
    counts[native] += _check_exact_doc_rows(
        documents, native, "GNSV v1 envelope",
        ["Offset", "Length", "Field", "Value"], ("Field",), envelope_rows,
        "save.docs-envelope")
    counts["save.docs-envelope"] = _check_envelope_docs(
        documents, header, source, _synthetic_envelope_observations(header, source))

    lifecycle = [
        ("Successful MVS load", "Resets per-load branch, mutation, export, dirty, baseline, and receipt state; opens startup import; advances `load_generation` when a scope is already bound", "Bind or renew a never-reused scope before persistence work"),
        ("Effective changed unlocked byte or word store", "Sets dirty and advances `mutation_sequence`; exhaustion latches conservatively without blocking the guest store", "Locked and same-value stores do not advance the sequence"),
        ("MVS reset or watchdog reset", "Preserves SRAM bytes and save lineage", "Reset does not reopen startup import after it closes"),
        ("Valid startup baseline import", "Copies SRAM only after full envelope validation; sets baseline known, clears dirty, and branches lineage", "May repeat before first guest execution while no guest, export, receipt, or unresolved host work is pending"),
        ("First guest execution", "Permanently closes startup import for that loaded image", "Later clean state or reset cannot reopen the gate"),
        ("Successful full continuation restore", "Restores historical SRAM, sets dirty, advances `restore_branch`, and invalidates the prior receipt", "Snapshot restore is not a disk commit and may replace newer SRAM history"),
        ("Successful export", "Advances `export_sequence`, returns an exact receipt, and leaves dirty set", "Keep immutable exported bytes until host commit outcome is resolved"),
        ("Successful ACK", "Consumes only the exact latest current receipt; clears dirty and establishes baseline", "Call only after complete host publication and namespace synchronization"),
        ("Rejected import, restore, or ACK", "Does not copy SRAM or clean pending state", "Stale, foreign, reordered, and duplicate receipts cannot clear dirty state"),
        ("Successful load replacement, unload, or destroy", "Ends the old image's save ownership lifetime", "Legacy signatures remain unchanged; resolve host work before replacement or unload"),
        ("Checked lifecycle transition", "Both policies refuse host attestation=false; `REQUIRE_RESOLVED` also refuses dirty core state; `ALLOW_DISCARD` reports pending core SRAM loss only after success", "Host supplies its unresolved-work attestation; a failed replacement leaves the existing image and receipt usable"),
    ]
    lifecycle_rows = [{"Event": event, "Core state effect": effect,
                       "Required host/core rule": rule}
                      for event, effect, rule in lifecycle]
    counts[native] += _check_exact_doc_rows(
        documents, native, "Ownership and lifecycle",
        ["Event", "Core state effect", "Required host/core rule"],
        ("Event",), lifecycle_rows, "save.docs-ownership")
    counts["save.docs-ownership"] = counts.get("save.docs-ownership", 0) + \
        _check_lifecycle_docs(documents, source, None)

    startup_rows = [
        {"Outcome": "`missing`", "File condition": "Opening the selected slot returns `ENOENT`", "Startup behavior": "Keep zero-filled SRAM, leave the baseline unknown, and run the guest without import"},
        {"Outcome": "`readable`", "File condition": "A regular slot has the exact-size envelope and a complete read/close", "Startup behavior": "Validate the envelope; malformed or incompatible bytes, including a bad digest or media identity, fail visibly before import"},
        {"Outcome": "`invalid`", "File condition": "An existing slot is unreadable, nonregular (including a FIFO), wrong-size, truncated, or has a trailing byte", "Startup behavior": "Open the selected path nonblocking and reject nonregular files before reading; fail visibly and never treat invalid data as a fresh zero baseline"},
        {"Outcome": "`not_applicable`", "File condition": "A writer starts a new slot without reading a prior save", "Startup behavior": "Start from zero-filled SRAM and write a new transaction"},
    ]
    counts[native] += _check_exact_doc_rows(
        documents, native, "Startup authoritative-slot outcomes",
        ["Outcome", "File condition", "Startup behavior"], ("Outcome",),
        startup_rows, "save.docs-host-order")

    host_order = [
        ("temp-created", "Exclusive same-directory temporary file", "No"),
        ("write", "Write the complete bounded envelope, retrying short writes and `EINTR`", "No"),
        ("file-fullfsync", "`F_FULLFSYNC` succeeds", "No"),
        ("file-close", "Temporary file descriptor closes successfully", "No"),
        ("rename", "Atomically replace the authoritative slot", "No; later failures are outcome-uncertain"),
        ("directory-open", "Open the containing directory", "No"),
        ("directory-fsync", "Synchronize the directory namespace", "No"),
        ("directory-close", "Directory descriptor closes successfully", "No"),
        ("ack", "Consume the receipt corresponding to these committed bytes", "Yes, only after every prior stage succeeds"),
    ]
    trace_stages = host_trace.split(",")
    expected_stages = [stage for stage, _, _ in host_order]
    _docs_require(trace_stages == expected_stages, "save.docs-host-order",
                  "rights evidence host stage trace differs from normative stage inventory")
    host_rows = [{"Order": str(index), "Stage": f"`{stage}`",
                  "Requirement": requirement, "ACK allowed": ack}
                 for index, (stage, requirement, ack) in enumerate(host_order, start=1)]
    counts[native] += _check_exact_doc_rows(
        documents, native, "Synchronous host commit order",
        ["Order", "Stage", "Requirement", "ACK allowed"], ("Stage",),
        host_rows, "save.docs-host-order")

    uncertain_rows = [
        {"Action": "`retry`", "Behavior": "Retain the original slot, bytes, receipt, and owner; republish those bytes through exclusive create, complete write, `F_FULLFSYNC`, checked file close, rename, directory sync and checked directory close; ACK that receipt last; never ACK from readback; reset failed-attempt trace suffixes", "Allowed transition": "Unblocks only after the full publication protocol and exact receipt ACK succeed; otherwise remains blocked"},
        {"Action": "`discard`", "Behavior": "Retain transaction state until the host explicitly chooses discard; do not ACK or claim the save committed", "Allowed transition": "Allows deliberate shutdown after the host accepts unresolved data loss"},
    ]
    counts[native] += _check_exact_doc_rows(
        documents, native, "Uncertain outcome resolution",
        ["Action", "Behavior", "Allowed transition"], ("Action",),
        uncertain_rows, "save.docs-host-order")

    malformed_rows = [
        {"Case": "`truncated`", "Host read": "Invalid: wrong-size envelope", "Core import": "Not attempted", "Guest work": "No"},
        {"Case": "`trailing-byte`", "Host read": "Invalid: oversized envelope", "Core import": "Not attempted", "Guest work": "No"},
        {"Case": "`bad-digest`", "Host read": "Readable exact-size file", "Core import": "Reject digest", "Guest work": "No"},
        {"Case": "`media-incompatible`", "Host read": "Readable exact-size file", "Core import": "Reject media identity", "Guest work": "No"},
    ]
    counts[native] += _check_exact_doc_rows(
        documents, native, "Malformed authoritative target regressions",
        ["Case", "Host read", "Core import", "Guest work"], ("Case",),
        malformed_rows, "save.docs-host-order")
    static_host_sources = {
        "host_stage_trace": host_trace,
        "writer_exit_before_reader": True,
        "writer_pids": [1], "reader_pids": [2],
        "invalid_authoritative_cases": [row["Case"].strip("`") for row in malformed_rows],
    }
    counts["save.docs-host-order"] = _check_host_order_docs(
        documents, None, host_trace)

    measurements = _portable_save_measurement_observations(fixture, source_identity)
    counts["save.docs-measurements"] = _check_measurements(documents, measurements, True)
    counts[native] += counts["save.docs-measurements"]

    native_state_rows = [
        {"Loaded profile": "`GN_PROFILE_DIAGNOSTIC`", "durable_save_id": "0", "Meaning": "No durable-save transfer for the diagnostic profile"},
        {"Loaded profile": "`GN_MVS_PROFILE_MSX`", "durable_save_id": "1", "Meaning": "`GN_MVS_SAVE_ID_V1`; the bounded MVS backup-RAM transfer is available"},
        {"Loaded profile": "Unsupported profile", "durable_save_id": "—", "Meaning": "Compatibility query rejects the profile; no save identity is issued"},
    ]
    counts["docs/native-state.md"] += _check_exact_doc_rows(
        documents, "docs/native-state.md", "Durable save compatibility field",
        ["Loaded profile", "durable_save_id", "Meaning"], ("Loaded profile",),
        native_state_rows, "save.docs-ownership")

    counts["docs/state-inventory.md"] += _check_snapshot_docs(documents, source)
    detailed_path = "docs/state-inventory.md"
    detailed_headers, detailed_rows = _read_table(
        documents[detailed_path], "Image and instance ownership (`src/instance.c`)",
        detailed_path, "save.docs-ownership")
    _docs_require(detailed_headers == [
        "Structure and fields", "Class", "Current encoding, validation, or reconstruction"
    ], "save.docs-ownership", f"{detailed_path}: detailed owner table headings changed")
    expected_detailed = {
        "gn_image.save_owner": (
            "Host/non-owned ownership hook",
            "Bound to the owning `gn_instance` only when the initialized image candidate is committed. It is not copied into snapshots or durable bytes; restore keeps the destination image link."),
        "gn_instance.mvs_save": (
            "Host lifecycle/ownership",
            "Per-instance save lineage, startup gate, and receipt-consumption state. Explicitly absent from GNST snapshots and GNSV durable bytes. A successful continuation restore updates this owner only after validated apply; rejected restore leaves it unchanged."),
        "gn_image.mvs_work_ram, .mvs_work_ram_size; .mvs_save_ram, .mvs_save_ram_size; .mvs_palette_ram, .mvs_palette_ram_size; .mvs_video_ram, .mvs_video_ram_words": (
            "Host + Guest",
            "Pointers and extents remain destination-owned. GNST memory section copies exact work/save/palette bytes and explicit big-endian video words into those same allocations. GNSV separately exports only the 65,536 backup-RAM bytes. Successful and rejected restore preserve the backup-RAM address."),
    }
    for key, (expected_class, expected_effect) in expected_detailed.items():
        matches = [row for row in detailed_rows
                   if _clean_cell(row["Structure and fields"]).startswith(key)]
        _docs_require(len(matches) == 1, "save.docs-ownership",
                      f"{detailed_path}: expected exactly one detailed save-owner row {key!r}")
        row = matches[0]
        _docs_require(_clean_cell(row["Class"]) == expected_class and
                      _normalized_contract_cell(row[
                          "Current encoding, validation, or reconstruction"]) ==
                      _normalized_contract_cell(expected_effect),
                      "save.docs-ownership",
                      f"{detailed_path} row {key!r}: exact owner claim differs")
    save_related_rows = []
    for row in detailed_rows:
        key = _clean_cell(row["Structure and fields"])
        if (key.startswith("gn_instance.mvs_save") or
                (key.startswith("gn_image.") and
                 ("save_owner" in key or "save_ram" in key))):
            save_related_rows.append(row)
    _docs_require(len(save_related_rows) == len(expected_detailed) and
                  {"gn_image.save_owner" if _clean_cell(row["Structure and fields"]) ==
                   "gn_image.save_owner" else
                   "gn_instance.mvs_save" if _clean_cell(row["Structure and fields"]).startswith(
                       "gn_instance.mvs_save") else
                   "gn_image.mvs_work_ram, .mvs_work_ram_size; .mvs_save_ram, .mvs_save_ram_size; .mvs_palette_ram, .mvs_palette_ram_size; .mvs_video_ram, .mvs_video_ram_words"
                   for row in save_related_rows} == set(expected_detailed),
                  "save.docs-ownership",
                  f"{detailed_path}: save-owner inventory has duplicate or extra rows")
    counts["docs/state-inventory.md"] += len(expected_detailed) * 2

    return counts


def check_portable_save_contract_docs(
    documents: dict[str, str], source: str
) -> dict[str, int]:
    """Compatibility wrapper kept for focused supporting-document tests."""
    native_state = "docs/native-state.md"
    scope = " ".join(documents[native_state].lower().split())
    for claim in (
        "the separate mvs backup-ram transfer uses `durable_save_id` and the gnsv v1 contract",
        "gnst restore is not a disk commit",
    ):
        _docs_require(claim in scope, "save.docs-ownership",
                      f"{native_state}: missing durable-save boundary {claim!r}")
    headers, rows = _read_table(documents[native_state], "Durable save compatibility field",
                                native_state, "save.docs-ownership")
    _docs_require(headers == ["Loaded profile", "durable_save_id", "Meaning"],
                  "save.docs-ownership", f"{native_state}: compatibility table headings changed")
    by_profile = {_clean_cell(row["Loaded profile"]): row for row in rows}
    expected_profiles = {
        "GN_PROFILE_DIAGNOSTIC", "GN_MVS_PROFILE_MSX", "Unsupported profile",
    }
    _docs_require(set(by_profile) == expected_profiles and len(rows) == len(expected_profiles),
                  "save.docs-ownership",
                  f"{native_state}: compatibility row inventory is missing, duplicate, or extra")
    compatibility = {
        "GN_PROFILE_DIAGNOSTIC": ("0", "No durable-save transfer for the diagnostic profile"),
        "GN_MVS_PROFILE_MSX": ("1", "GN_MVS_SAVE_ID_V1; the bounded MVS backup-RAM transfer is available"),
        "Unsupported profile": ("—", "Compatibility query rejects the profile; no save identity is issued"),
    }
    for profile, (save_id, expected_meaning) in compatibility.items():
        row = by_profile[profile]
        _docs_require(_clean_cell(row["durable_save_id"]) == save_id,
                      "save.docs-ownership",
                      f"{native_state} row {profile}: durable_save_id differs")
        _docs_require(" ".join(_clean_cell(row["Meaning"]).split()) == expected_meaning,
                      "save.docs-ownership",
                      f"{native_state} row {profile}: compatibility meaning differs")

    inventory_count = _check_snapshot_docs(documents, source)

    owner_path = "docs/ownership-and-errors.md"
    headers, owner_rows = _read_table(documents[owner_path], "MVS durable save boundaries",
                                      owner_path, "save.docs-ownership")
    _docs_require(headers == ["Operation", "Backup-RAM effect", "Ownership or error effect"],
                  "save.docs-ownership", f"{owner_path}: durable-save table headings changed")
    operations = {_clean_cell(row["Operation"]): row for row in owner_rows}
    expected_operations = {
        "Successful MVS load", "MVS reset or watchdog reset", "First guest execution",
        "Valid startup import", "Successful GNST continuation restore",
        "Rejected GNST restore", "GNSV export", "Receipt ACK",
        "Successful load replacement, unload, or destroy", "Checked lifecycle transition",
    }
    _docs_require(set(operations) == expected_operations and len(owner_rows) == len(expected_operations),
                  "save.docs-ownership",
                  f"{owner_path}: lifecycle row inventory is missing, duplicate, or extra")
    owner_claims = {
        "Successful MVS load": ("Creates the new image's SRAM",
                                 "Resets per-load lineage and opens startup import; a failed replacement preserves the previous image"),
        "MVS reset or watchdog reset": ("Preserves SRAM bytes",
                                        "Does not clear dirty state; does not reopen a closed startup gate"),
        "First guest execution": ("No direct SRAM change",
                                  "Closes startup baseline import for that load"),
        "Valid startup import": ("Copies the fully validated payload",
                                 "Establishes baseline and can repeat before first guest execution; malformed, foreign-media, or late input leaves SRAM unchanged"),
        "Successful GNST continuation restore": ("Replaces SRAM with snapshot history",
                                                 "Marks save dirty, advances restore branch, and invalidates the previous receipt after validation and apply"),
        "Rejected GNST restore": ("Preserves SRAM", "Leaves save lineage unchanged"),
        "GNSV export": ("Copies current SRAM to caller storage",
                        "Returns the latest receipt but does not clear dirty state"),
        "Receipt ACK": ("No SRAM copy",
                        "Clears dirty only for the exact latest current receipt after the host has completed publication"),
        "Successful load replacement, unload, or destroy":
            ("Ends the old image lifetime",
             "Resolve host pending work before transition; legacy public signatures are unchanged"),
        "Checked lifecycle transition": (
            "`ALLOW_DISCARD` may discard pending core SRAM after successful staging",
            "`REQUIRE_RESOLVED` requires host attestation and clean core state; failed replacement preserves the current image and receipt"),
    }
    for operation, (expected_sram, expected_effect) in owner_claims.items():
        row = operations[operation]
        _docs_require(" ".join(_clean_cell(row["Backup-RAM effect"]).split()) ==
                      _clean_cell(expected_sram), "save.docs-ownership",
                      f"{owner_path} row {operation}: backup-RAM effect differs")
        _docs_require(" ".join(_clean_cell(row["Ownership or error effect"]).split()) ==
                      _clean_cell(expected_effect), "save.docs-ownership",
                      f"{owner_path} row {operation}: lifecycle effect differs")
    return {
        native_state: len(compatibility) + sum(len(item[1]) for item in compatibility.values()) + 2,
        "docs/state-inventory.md": inventory_count,
        owner_path: len(owner_claims) + sum(len(fragments) for fragments in owner_claims.values()),
    }


def _check_host_order_docs(
    documents: dict[str, str], observations: dict[str, object] | None,
    host_stage_trace: str,
) -> int:
    path = "docs/native-save.md"
    headers, rows = _read_table(documents[path], "Synchronous host commit order",
                                path, "save.docs-host-order")
    _docs_require(headers == ["Order", "Stage", "Requirement", "ACK allowed"],
                  "save.docs-host-order", f"{path}: host order table headings changed")
    expected = (str(observations["host_stage_trace"]) if observations is not None
                else host_stage_trace).split(",")
    stages = [_clean_cell(row["Stage"]) for row in rows]
    order = [int(row["Order"]) for row in rows]
    _docs_require(stages == expected and order == list(range(1, len(expected) + 1)),
                  "save.docs-host-order",
                  f"{path}: documented stages/order {stages!r}/{order!r}; observed {expected!r}")
    _docs_require(len(rows) == 9 and
                  all(row["ACK allowed"].lower().startswith("no") for row in rows[:-1]) and
                  rows[-1]["ACK allowed"].lower().startswith("yes"),
                  "save.docs-host-order", f"{path}: ACK must follow namespace completion")
    row_by_stage = {stage: row for stage, row in zip(stages, rows, strict=True)}
    for stage, needles in {
        "write": ("complete", "short writes", "EINTR"),
        "file-fullfsync": ("F_FULLFSYNC", "succeeds"),
        "rename": ("authoritative", "atomically"),
        "directory-fsync": ("namespace",),
        "ack": ("receipt", "committed bytes"),
    }.items():
        content = row_by_stage[stage]["Requirement"].lower()
        for needle in needles:
            _docs_require(needle.lower() in content,
                          "save.docs-host-order",
                          f"{path} row {stage}: missing {needle!r}")
    if observations is not None:
        _docs_require(observations["writer_exit_before_reader"] and
                      observations["writer_pids"][0] != observations["reader_pids"][0],
                      "save.docs-host-order", "observed reader did not follow an exited distinct writer")
    return (len(rows) + 2 + _check_startup_read_outcomes(documents, observations) +
            _check_uncertain_transaction(documents, observations))


def _check_measurements(
    documents: dict[str, str], observations: dict[str, object],
    require_measured: bool,
) -> int:
    path = "docs/native-save.md"
    headers, rows = _read_table(documents[path], "Measurements and pending evidence",
                                path, "save.docs-measurements")
    _docs_require(headers == ["Claim", "Status", "Value"],
                  "save.docs-measurements", f"{path}: measurement table headings changed")
    by_claim = {_clean_cell(row["Claim"]): row for row in rows}
    _docs_require(len(by_claim) == len(rows), "save.docs-measurements",
                  f"{path}: duplicate measurement rows")
    recovery_cases = observations["recovery_kill_cases"]
    recovery_stage_count = len({str(case["stage"]) for case in recovery_cases})
    recovery_histories = {bool(case["prior_a"]) for case in recovery_cases}
    recovery_scenarios = (
        "first-create and A-to-B replacement"
        if recovery_histories == {False, True}
        else "incomplete first-create/replacement coverage"
    )
    expected = {
        "fixture_bytes": str(observations["fixture_bytes"]),
        "fixture_sha256": str(observations["fixture_sha256"]),
        "shared_media_identity_a_b": "true" if observations["shared_media_identity"] else "false",
        "host_stage_trace": str(observations["host_stage_trace"]),
        "process_interruption_stage_cases": str(
            f"{len(recovery_cases)} ({recovery_stage_count} publication stages × "
            f"{recovery_scenarios})"),
        "writer_reader_process_pairs": str(len(observations["writers"])),
        "child_timeout_bound_seconds": str(observations["child_timeout_seconds"]),
        "child_output_bound_bytes": str(observations["child_output_bound_bytes"]),
        "save_suite_critical_path_bound_seconds": "900",
    }
    for observation_key, claim in (
        ("host_identity", "tested_host_identity"),
        ("save_source_identity_sha256", "save_source_identity_sha256"),
        ("guest_fixture_source_sha256", "guest_fixture_source_sha256"),
        ("build_identity", "build_identity"),
        ("supported_sync_operations", "supported_sync_operations"),
        ("host_fault_cases", "host_fault_matrix_cases"),
        ("unsupported_host_protocol", "unsupported_host_protocol"),
    ):
        if observation_key in observations:
            expected[claim] = str(observations[observation_key])
    optional_measurements = {
        "tested_host_identity", "save_source_identity_sha256",
        "guest_fixture_source_sha256", "build_identity",
        "supported_sync_operations", "host_fault_matrix_cases",
        "unsupported_host_protocol",
    }
    missing_measurements = optional_measurements - set(expected)
    _docs_require(not require_measured or not missing_measurements,
                  "save.docs-measurements",
                  f"{path}: measured observations are missing {sorted(missing_measurements)}")
    expected_status = {claim: "measured" for claim in expected}
    expected_status["child_timeout_bound_seconds"] = "bound"
    expected_status["child_output_bound_bytes"] = "bound"
    expected_status["save_suite_critical_path_bound_seconds"] = "bound"
    expected_status["unsupported_host_protocol"] = "bound"
    pending = []
    for claim, value in expected.items():
        row = by_claim.get(claim)
        _docs_require(row is not None, "save.docs-measurements",
                      f"{path}: missing measured claim {claim}")
        _docs_require(row["Status"].lower() == expected_status[claim] and
                      _clean_cell(row["Value"]).replace(",", "") == value.replace(",", ""),
                      "save.docs-measurements",
                      f"{path} row {claim}: documented {row['Value']!r}; observed {value!r}")
    for claim, row in by_claim.items():
        status = row["Status"].lower()
        _docs_require(status in {"measured", "bound", "pending"}, "save.docs-measurements",
                      f"{path} row {claim}: status must be measured, bound, or pending")
        if status == "pending":
            pending.append(claim)
    _docs_require(set(by_claim) == set(expected) | missing_measurements | {
        "peak_restore_staging_bytes", "interrupted_commit_recovery",
        "physical_board_or_game_save_behavior",
    }, "save.docs-measurements", f"{path}: measurement inventory changed unexpectedly")
    for claim in missing_measurements:
        row = by_claim[claim]
        required_status = "bound" if claim == "unsupported_host_protocol" else "measured"
        _docs_require(row["Status"].lower() == required_status and
                      bool(_clean_cell(row["Value"])),
                      "save.docs-measurements",
                      f"{path} row {claim}: expected nonempty {required_status} observation")
    for claim in ("peak_restore_staging_bytes", "interrupted_commit_recovery",
                  "physical_board_or_game_save_behavior"):
        _docs_require(by_claim[claim]["Status"].lower() == "pending",
                      "save.docs-measurements",
                      f"{path} row {claim}: this witness has no measurement for that claim")
    _docs_require("power loss" in by_claim["physical_board_or_game_save_behavior"]["Value"].lower() and
                  "not qualified" in by_claim["physical_board_or_game_save_behavior"]["Value"].lower(),
                  "save.docs-measurements",
                  f"{path} row physical_board_or_game_save_behavior: physical power-loss scope must remain unqualified")
    if "suite_critical_path_seconds" in observations:
        try:
            suite_seconds = float(observations["suite_critical_path_seconds"])
        except (TypeError, ValueError):
            suite_seconds = 0.0
        _docs_require(0 < suite_seconds <= 900, "save.docs-measurements",
                      f"{path}: observed save suite critical path {suite_seconds!r}s exceeds the 900s bound")
    intentionally_pending = {
        "peak_restore_staging_bytes", "interrupted_commit_recovery",
        "physical_board_or_game_save_behavior",
    }
    if require_measured and set(pending) - intentionally_pending:
        raise SaveDocsError("save.docs-measurements",
                            f"{path}: required measured claims remain pending: {sorted(set(pending) - intentionally_pending)}")
    return len(by_claim)


def _replace_table_row_cell(
    document: str, heading: str, key_header: str, key_value: str,
    target_header: str, target_value: str,
) -> str:
    lines = document.splitlines()
    heading_index = next(i for i, line in enumerate(lines)
                         if line.strip() == f"## {heading}")
    table_index = next(i for i in range(heading_index + 1, len(lines))
                       if lines[i].lstrip().startswith("|"))
    headers = [cell.strip() for cell in lines[table_index].strip().strip("|").split("|")]
    key_index = headers.index(key_header)
    target_index = headers.index(target_header)
    for index in range(table_index + 2, len(lines)):
        if not lines[index].lstrip().startswith("|"):
            break
        cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        if len(cells) == len(headers) and _clean_cell(cells[key_index]) == key_value:
            cells[target_index] = target_value
            lines[index] = "| " + " | ".join(cells) + " |"
            return "\n".join(lines) + "\n"
    raise ValueError(f"unable to find {key_value!r} in {heading!r}")


def _remove_table_row(
    document: str, heading: str, key_header: str, key_value: str
) -> str:
    lines = document.splitlines()
    heading_index = next(i for i, line in enumerate(lines)
                         if line.strip() == f"## {heading}")
    table_index = next(i for i in range(heading_index + 1, len(lines))
                       if lines[i].lstrip().startswith("|"))
    headers = [cell.strip() for cell in lines[table_index].strip().strip("|").split("|")]
    key_index = headers.index(key_header)
    for index in range(table_index + 2, len(lines)):
        if not lines[index].lstrip().startswith("|"):
            break
        cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        if len(cells) == len(headers) and _clean_cell(cells[key_index]) == key_value:
            del lines[index]
            return "\n".join(lines) + "\n"
    raise ValueError(f"unable to remove {key_value!r} from {heading!r}")


def _move_ack_before_directory_sync(document: str) -> str:
    lines = document.splitlines()
    heading_index = next(i for i, line in enumerate(lines)
                         if line.strip() == "## Synchronous host commit order")
    table_index = next(i for i in range(heading_index + 1, len(lines))
                       if lines[i].lstrip().startswith("|"))
    rows = []
    for index in range(table_index + 2, len(lines)):
        if not lines[index].lstrip().startswith("|"):
            break
        rows.append((index, lines[index]))
    ack_index = next(i for i, (_, line) in enumerate(rows) if "| `ack` |" in line)
    _, ack = rows.pop(ack_index)
    fsync_index = next(i for i, (_, line) in enumerate(rows)
                       if "| `directory-fsync` |" in line)
    rows.insert(fsync_index, (-1, ack))
    # Replace the table's data rows only; keep its header and separator intact.
    first_data = table_index + 2
    last_data = first_data + len(rows)
    lines[first_data:last_data] = [line for _, line in rows]
    return "\n".join(lines) + "\n"


def _check_startup_read_outcomes(
    documents: dict[str, str], observations: dict[str, object]
) -> int:
    path = "docs/native-save.md"
    headers, rows = _read_table(documents[path], "Startup authoritative-slot outcomes",
                                path, "save.docs-host-order")
    _docs_require(headers == ["Outcome", "File condition", "Startup behavior"],
                  "save.docs-host-order", f"{path}: startup outcome table headings changed")
    by_outcome = {_clean_cell(row["Outcome"]): row for row in rows}
    expected = {"missing", "readable", "invalid", "not_applicable"}
    _docs_require(set(by_outcome) == expected and len(by_outcome) == len(rows),
                  "save.docs-host-order",
                  f"{path}: startup outcomes are missing, duplicated, or extra")
    row_text = {name: " ".join(row.values()).lower()
                for name, row in by_outcome.items()}
    for outcome, needles in {
        "missing": ("enoent", "zero-filled", "baseline unknown", "without import"),
        "readable": ("regular", "exact-size", "validate the envelope", "import",
                     "bad digest", "media identity"),
        "invalid": ("unreadable", "fifo", "nonblocking", "before reading",
                    "wrong-size", "truncated", "trailing byte",
                    "fail visibly", "fresh zero baseline"),
        "not_applicable": ("writer",),
    }.items():
        for needle in needles:
            _docs_require(needle in row_text[outcome], "save.docs-host-order",
                          f"{path} row {outcome}: missing {needle!r}")
    _docs_require("bad digest" not in row_text["invalid"] and
                  "media-incompatible" not in row_text["invalid"],
                  "save.docs-host-order",
                  f"{path}: host-invalid row must not include core validation failures")

    source = (Path(__file__).resolve().parents[2] / "tests/sdk/save_host.c").read_text(
        encoding="utf-8")
    read_body = _c_function_body(source, "save_host_read_authoritative",
                                 "save.docs-host-order")
    nonblocking_open = read_body.find("open(path, O_RDONLY | O_NONBLOCK)")
    descriptor_check = read_body.find("fstat(")
    _docs_require("errno == ENOENT ? SAVE_HOST_READ_MISSING : SAVE_HOST_READ_INVALID" in read_body and
                  "SAVE_HOST_READ_READY" in read_body and "SAVE_HOST_READ_INVALID" in read_body and
                  "S_ISREG(file_status.st_mode)" in read_body and
                  "file_status.st_size == (off_t)GN_MVS_SAVE_ENVELOPE_V1_BYTES" in read_body and
                  nonblocking_open >= 0 and descriptor_check > nonblocking_open and
                  "trusted directory" in documents[path].lower(),
                  "save.docs-host-order",
                  "host startup reader must reject nonregular files after nonblocking open")

    malformed_headers, malformed_rows = _read_table(
        documents[path], "Malformed authoritative target regressions", path,
        "save.docs-host-order")
    _docs_require(malformed_headers == ["Case", "Host read", "Core import", "Guest work"],
                  "save.docs-host-order",
                  f"{path}: malformed authoritative-target table headings changed")
    malformed = {_clean_cell(row["Case"]): row for row in malformed_rows}
    expected_cases = ["truncated", "trailing-byte", "bad-digest", "media-incompatible"]
    _docs_require(list(malformed) == expected_cases and
                  (observations is None or
                   observations["invalid_authoritative_cases"] == expected_cases),
                  "save.docs-host-order",
                  f"{path}: malformed target cases differ from fresh-reader observations")
    _docs_require(all("no" in malformed[case]["Guest work"].lower()
                      for case in expected_cases) and
                  all("not attempted" in malformed[case]["Core import"].lower()
                      for case in expected_cases[:2]) and
                  all("reject" in malformed[case]["Core import"].lower()
                      for case in expected_cases[2:]) and
                  all("invalid" in malformed[case]["Host read"].lower()
                      for case in expected_cases[:2]) and
                  all("readable" in malformed[case]["Host read"].lower()
                      for case in expected_cases[2:]),
                  "save.docs-host-order",
                  f"{path}: malformed target rejection order differs from observed behavior")

    if observations is None:
        return len(rows) + len(malformed_rows)

    writer = observations["writers"][0]
    reader = observations["readers"][0]
    fresh = observations["fresh_slot_observation"]
    _docs_require(writer["startup_read_result"] == "not_applicable" and
                  reader["startup_read_result"] == "readable" and
                  fresh["startup_read_result"] == "missing" and
                  fresh["after_import_baseline_known"] == 0 and
                  fresh["after_guest_baseline_known"] == 0 and
                  fresh["after_guest_dirty"] == 0 and fresh["stages"] == "missing",
                  "save.docs-host-order",
                  "observed first-slot startup differs from the documented missing-file policy")
    fifo = observations["fifo_invalid_observation"]
    _docs_require(fifo["timed_out"] is False and fifo["reaped"] is True and
                  fifo["returncode"] == 2 and fifo["elapsed_seconds"] < fifo["timeout_seconds"] and
                  "save.authoritative-read failed outcome=invalid" in fifo["stderr"],
                  "save.docs-host-order",
                  "FIFO without a writer did not return the explicit invalid outcome before timeout")
    return len(rows) + len(malformed_rows) + 3


def _check_uncertain_transaction(
    documents: dict[str, str], observations: dict[str, object] | None
) -> int:
    path = "docs/native-save.md"
    normalized_recovery_docs = " ".join(
        " ".join(content.lower().split()) for content in documents.values())
    headers, rows = _read_table(documents[path], "Uncertain outcome resolution",
                                path, "save.docs-host-order")
    _docs_require(headers == ["Action", "Behavior", "Allowed transition"] and
                  {_clean_cell(row["Action"]) for row in rows} == {"retry", "discard"} and
                  len(rows) == 2, "save.docs-host-order",
                  f"{path}: uncertain resolution actions are missing, duplicated, or extra")
    by_action = {_clean_cell(row["Action"]): row for row in rows}
    retry_text = " ".join(by_action["retry"].values()).lower()
    discard_text = " ".join(by_action["discard"].values()).lower()
    for needle in ("retain", "sync", "close", "ack", "readback", "remains blocked"):
        _docs_require(needle in retry_text, "save.docs-host-order",
                      f"{path} retry row: missing {needle!r}")
    for needle in ("explicitly chooses", "do not ack", "unresolved data loss"):
        _docs_require(needle in discard_text, "save.docs-host-order",
                      f"{path} discard row: missing {needle!r}")
    recovery_docs = documents[path].lower()
    for needle in ("process-interruption recovery is exercised", "pipe-gated live writer",
                   "distinct fresh reader", "ignores every orphan temp",
                   "six transition barriers", "save.disk-latest-branch",
                   "post-rename unresolved state", "do not prove power-loss survival"):
        _docs_require(needle in recovery_docs, "save.docs-host-order",
                      f"{path}: interruption evidence is missing {needle!r}")

    source = (Path(__file__).resolve().parents[2] / "tests/sdk/save_process.c").read_text(
        encoding="utf-8")
    host_source = (Path(__file__).resolve().parents[2] / "tests/sdk/save_host.c").read_text(
        encoding="utf-8")
    header = (Path(__file__).resolve().parents[2] / "tests/sdk/save_host.h").read_text(
        encoding="utf-8")
    transaction = re.search(
        r"typedef struct\s*\{(?P<body>.*?)\}\s*save_host_context\s*;",
        header, re.DOTALL)
    _docs_require(transaction is not None, "save.docs-host-order",
                  "host pending transaction record is missing")
    fields = transaction.group("body") if transaction is not None else ""
    for field in ("char slot[", "const uint8_t *immutable_bytes;",
                  "gn_mvs_save_receipt_v1 receipt;", "gn_instance *owner;",
                  "int commit_failed;", "int unresolved;"):
        _docs_require(field in fields, "save.docs-host-order",
                      f"host pending transaction record lacks {field!r}")
    retry_body = _c_function_body(host_source, "save_host_reconcile",
                                  "save.docs-host-order")
    publish_body = _c_function_body(host_source, "save_host_publish",
                                    "save.docs-host-order")
    write_body = _c_function_body(host_source, "save_host_write_all",
                                  "save.docs-host-order")
    resolve_body = _c_function_body(source, "host_resolve_uncertain_transaction",
                                    "save.docs-host-order")
    process_body = _c_function_body(source, "run_process", "save.docs-host-order")
    transition_body = _c_function_body(host_source, "save_host_before_transition",
                                       "save.docs-host-order")
    for field in ("transaction->active == 0", "transaction->commit_failed == 0",
                  "transaction->publication_in_flight == 0",
                  "transaction->unresolved == 0"):
        _docs_require(field in transition_body, "save.docs-host-order",
                      f"host transition barrier omits {field!r}")
    commit_body = _c_function_body(host_source, "save_host_commit",
                                   "save.docs-host-order")
    unload_body = _c_function_body(host_source, "save_host_unload",
                                   "save.docs-host-order")
    destroy_body = _c_function_body(host_source, "save_host_destroy",
                                    "save.docs-host-order")
    _docs_require("transaction->commit_failed =" in commit_body and
                  "SAVE_HOST_NOT_COMMITTED" in commit_body and
                  "transaction->active = transaction->commit_failed" in commit_body,
                  "save.docs-host-order",
                  "known pre-rename failure must retain its retry/discard barrier")
    for wrapper in (unload_body, destroy_body):
        _docs_require("explicit_failed_discard" in wrapper and
                      "GN_MVS_SAVE_LIFECYCLE_ALLOW_DISCARD" in wrapper and
                      "transaction->commit_failed = 0" in wrapper,
                      "save.docs-host-order",
                      "only successful explicit discard may release failed-commit ownership")
    for name, call in {
        "save_host_restore": "gn_state_restore_v1",
        "save_host_renew_scope": "gn_mvs_save_scope_renew_v1",
        "save_host_unload": "gn_unload_checked_v1",
        "save_host_destroy": "gn_destroy_checked_v1",
    }.items():
        wrapper = _c_function_body(host_source, name, "save.docs-host-order")
        _docs_require("save_host_before_transition(transaction)" in wrapper and
                      call in wrapper,
                      "save.docs-host-order",
                      f"{name} must gate its checked core transition")
    slot_wrapper = _c_function_body(host_source, "save_host_change_slot",
                                    "save.docs-host-order")
    replacement_wrapper = _c_function_body(host_source, "save_host_replace",
                                            "save.docs-host-order")
    _docs_require("save_host_before_transition(transaction)" in slot_wrapper and
                  "save_host_before_transition(transaction)" in replacement_wrapper,
                  "save.docs-host-order", "slot and content replacement bypass host barrier")
    gate_callback = _c_function_body(source, "save_stage_gate_callback",
                                     "save.docs-host-order")
    python_source = (Path(__file__).resolve().read_text(encoding="utf-8"))
    _docs_require("read(gate->release_fd" in gate_callback and
                  "write(descriptor" in _c_function_body(source, "stage_write_all",
                                                           "save.docs-host-order") and
                  "select.select([notify_read]" in python_source and
                  "pass_fds=(notify_write, release_read)" in python_source and
                  "child.terminate()" in python_source,
                  "save.docs-host-order",
                  "recovery must use explicit parent-controlled pipes and terminate a live writer")
    _docs_require("save_host_publish(transaction, 1)" in retry_body and
                  "transaction->stages[stage_base] = '\\0';" in retry_body and
                  "F_FULLFSYNC" in publish_body and "write(" in write_body and
                  "rename(temporary, transaction->slot)" in publish_body and
                  "fsync(directory_fd)" in publish_body and
                  "gn_mvs_save_ack_v1" in publish_body and "read(" not in publish_body and
                  "transaction->unresolved = 1" in retry_body and
                  "while (transaction->unresolved != 0 && actions < SAVE_HOST_MAX_ATTEMPTS)" in resolve_body and
                  'strcmp(action, "retry")' in resolve_body and
                  'strcmp(action, "discard")' in resolve_body and
                  "gn_destroy" not in resolve_body and "free(" not in resolve_body and
                  "if (pending_transaction.unresolved != 0)" in process_body,
                  "save.docs-host-order",
                  "uncertain resolution does not retain and gate the live transaction")
    guard = process_body.find("if (pending_transaction.unresolved != 0)")
    cleanup = process_body.find("free(save_bytes)", guard)
    _docs_require(guard >= 0 and cleanup > guard,
                  "save.docs-host-order",
                  "transaction memory is released before the unresolved transition gate")

    if observations is None:
        return len(rows) + 27

    observed = observations["uncertain_retry_observation"]
    discarded = observations["uncertain_discard_observation"]
    stages = observed["stages"].split(",")
    full_protocol = ["temp-created", "write", "file-fullfsync", "file-close",
                     "rename", "directory-open", "directory-fsync",
                     "directory-close", "ack"]
    _docs_require(observed["host_resolution"] == "retry" and
                  observed["host_outcome"] == "committed" and
                  observed["after_ack_dirty"] == 0 and
                  stages[:5] == full_protocol[:5] and
                  stages[5:] == full_protocol,
                  "save.docs-host-order",
                  "forced post-rename uncertainty did not republish through the full protocol before ACK")
    normalized_recovery_docs = " ".join(documents[path].lower().split())
    retry_envelope = observations["uncertain_retry_envelope"]
    _docs_require(retry_envelope["bytes"] == 65_632 and
                  retry_envelope["exact_after_retry"] is True and
                  retry_envelope["fresh_reader_value"] == EXPECTED["A"] and
                  "entire immutable envelope" in normalized_recovery_docs and
                  "fresh reader" in normalized_recovery_docs,
                  "save.docs-host-order",
                  "retry must compare the entire immutable envelope and validate it in a fresh reader")
    repeated = observations["uncertain_retry_after_repeated_failures"]
    _docs_require(observations["uncertain_retry_failure_count"] == 8 and
                  repeated["host_resolution"] == "retry" and
                  repeated["host_outcome"] == "committed" and
                  repeated["after_ack_dirty"] == 0 and
                  repeated["stages"] == observed["stages"],
                  "save.docs-host-order",
                  "repeated failed retries did not reset trace and preserve final successful order")
    _docs_require("failed retry attempts reset their stage suffix" in
                  normalized_recovery_docs and
                  "stage recording is best-effort" in normalized_recovery_docs,
                  "save.docs-host-order",
                  f"{path}: retry trace must be observational and reset per failed attempt")
    _docs_require(discarded["host_resolution"] == "discard" and
                  discarded["host_outcome"] == "outcome_uncertain" and
                  discarded["after_export_dirty"] == 1 and
                  discarded["after_ack_dirty"] == 1 and
                  "ack" not in discarded["stages"].split(","),
                  "save.docs-host-order",
                  "explicit discard must preserve unresolved status and never ACK")
    barrier = observations["barrier_ordering"]
    _docs_require(barrier["barrier_mask"] == (1 << 6) - 1 and
                  barrier["latest_disk_value"] == "B" and
                  barrier["fresh_reader_value"] == EXPECTED["B"],
                  "save.docs-host-order",
                  "ordered restored branch B did not survive fresh-process recovery")
    unresolved = observations["unresolved_barrier"]
    _docs_require(unresolved["active"] == 0 and
                  unresolved["publication_in_flight"] == 0 and
                  unresolved["unresolved"] == 1 and
                  unresolved["barrier_mask"] == (1 << 6) - 1 and
                  unresolved["destroy_owner_preserved"] == 1,
                  "save.docs-host-order",
                  "post-rename unresolved state did not independently block all six transitions")
    failed_commit = observations["pre_rename_failure_barrier"]
    _docs_require(failed_commit["active"] == 1 and
                  failed_commit["commit_failed"] == 1 and
                  failed_commit["unresolved"] == 0 and
                  failed_commit["barrier_mask"] == (1 << 6) - 1 and
                  failed_commit["explicit_discard"] == "ok" and
                  failed_commit["discarded_pending"] == 1 and
                  failed_commit["after_discard_transition_ready"] == 1,
                  "save.docs-host-order",
                  "known pre-rename failure must block mutation until successful explicit discard")
    _docs_require("a known pre-rename failure keeps the pending receipt and dirty sram blocked until retry succeeds or an explicit discard"
                  in normalized_recovery_docs,
                  "save.docs-host-order",
                  "native-save contract omits the known failed-commit transition boundary")
    retry_known_failure = observations["pre_rename_retry"]
    _docs_require(retry_known_failure["retry_outcome"] == "committed" and
                  retry_known_failure["commit_failed"] == 0 and
                  retry_known_failure["transition_ready"] == 1 and
                  retry_known_failure["after_ack_dirty"] == 0,
                  "save.docs-host-order",
                  "known pre-rename failed commit did not retain and successfully retry the pending transfer")
    obsolete = observations["obsolete_publication_control"]
    _docs_require(obsolete["assertion"] == "save.disk-latest-branch" and
                  obsolete["stale_ack_rejected"] == 1 and
                  obsolete["final_disk_value"] == "A",
                  "save.docs-host-order",
                  "obsolete publication control failed to isolate the disk oracle from stale ACK")
    return len(rows) + 27


def _save_manifest_source_identity(
    root: Path, manifest: dict[str, object]
) -> str:
    try:
        fixture = manifest["mvs_save_fixture"]
        sources = [fixture["generator_source"], fixture["base_source"],
                   *fixture["assertion_sources"]]
    except (KeyError, TypeError) as error:
        raise SaveDocsError("save.docs-measurements",
                            "save rights manifest lacks the save source closure") from error
    entries = []
    for record in sources:
        if not isinstance(record, dict):
            raise SaveDocsError("save.docs-measurements",
                                "save rights manifest source entry is malformed")
        relative = record.get("path")
        if not isinstance(relative, str):
            raise SaveDocsError("save.docs-measurements",
                                "save rights manifest source path is malformed")
        path = root / relative
        try:
            content = path.read_bytes()
        except OSError as error:
            raise SaveDocsError("save.docs-measurements",
                                f"save source is unavailable: {relative}") from error
        digest = hashlib.sha256(content).hexdigest()
        entries.append((relative, digest))
    material = b"".join(
        relative.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\n"
        for relative, digest in sorted(entries))
    return hashlib.sha256(material).hexdigest()


def check_save_docs(
    root: Path, observations: dict[str, object], require_measured: bool = False,
    *, _document_overrides: dict[str, str] | None = None,
    _run_mutations: bool = True,
) -> dict[str, int]:
    document_paths = (
        "docs/native-save.md", "docs/native-state.md",
        "docs/state-inventory.md", "docs/ownership-and-errors.md",
    )
    documents = {path: (root / path).read_text(encoding="utf-8")
                 for path in document_paths}
    if _document_overrides:
        documents.update(_document_overrides)
    header = (root / "include/glueyneo/glueyneo.h").read_text(encoding="utf-8")
    source = (root / "src/instance.c").read_text(encoding="utf-8")
    try:
        fixture_manifest = json.loads(
            (root / "tests/fixture/rights-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SaveDocsError("save.docs-measurements",
                            "save rights manifest is unavailable") from error
    source_identity = _save_manifest_source_identity(root, fixture_manifest)
    if "save_source_identity_sha256" in observations:
        _docs_require(observations["save_source_identity_sha256"] == source_identity,
                      "save.docs-measurements",
                      "measured source identity differs from the current source closure")

    counts = check_save_contract_docs(
        documents, header, source, fixture_manifest, source_identity)
    measured_counts = {
        "save.docs-api": _check_api_docs(documents, header, source, observations),
        "save.docs-envelope": _check_envelope_docs(documents, header, source, observations),
        "save.docs-host-order": _check_host_order_docs(
            documents, observations,
            str(fixture_manifest["mvs_save_fixture"]["oracle"]["host_stage_trace"])),
        "save.docs-measurements": _check_measurements(
            documents, observations, require_measured),
        "save.docs-ownership": _check_lifecycle_docs(
            documents, source, observations),
    }
    for key, value in measured_counts.items():
        counts[key] = counts.get(key, 0) + value
    if not _run_mutations:
        return counts

    native_path = "docs/native-save.md"
    api_mutation = dict(documents)
    api_mutation[native_path] = _remove_table_row(
        documents[native_path], "Public records and operations", "Name",
        "gn_mvs_save_ack_v1")
    envelope_mutation = dict(documents)
    envelope_mutation[native_path] = _replace_table_row_cell(
        documents[native_path], "GNSV v1 envelope", "Field", "Total length",
        "Length", "65,631")
    ownership_mutation = dict(documents)
    ownership_mutation[native_path] = _replace_table_row_cell(
        documents[native_path], "Ownership and lifecycle", "Event", "Successful ACK",
        "Core state effect", "Sets dirty = 1 and establishes baseline")
    order_mutation = dict(documents)
    order_mutation[native_path] = _move_ack_before_directory_sync(
        documents[native_path])
    startup_mutation = dict(documents)
    startup_mutation[native_path] = _remove_table_row(
        documents[native_path], "Startup authoritative-slot outcomes", "Outcome", "missing")
    uncertain_mutation = dict(documents)
    uncertain_mutation[native_path] = _remove_table_row(
        documents[native_path], "Uncertain outcome resolution", "Action", "retry")
    controls = (
        ("api row removal", api_mutation, "save.docs-api", "missing"),
        ("envelope length alteration", envelope_mutation, "save.docs-envelope", "contradiction"),
        ("dirty/ACK reversal", ownership_mutation, "save.docs-ownership", "contradiction"),
        ("ACK before directory sync", order_mutation, "save.docs-host-order", "contradiction"),
        ("missing first-slot outcome removed", startup_mutation,
         "save.docs-host-order", "missing"),
        ("uncertain retry outcome removed", uncertain_mutation,
         "save.docs-host-order", "missing"),
    )
    control_counts = {"save.docs-missing": 0, "save.docs-contradiction": 0}
    for label, mutated, expected_claim, category in controls:
        try:
            check_save_docs(root, observations, require_measured,
                            _document_overrides=mutated, _run_mutations=False)
        except SaveDocsError as error:
            _docs_require(error.claim_id == expected_claim,
                          "save.docs-contradiction",
                          f"mutation {label!r} failed at {error.claim_id}, expected {expected_claim}")
            control_counts[f"save.docs-{category}"] += 1
        else:
            raise SaveDocsError("save.docs-contradiction",
                                f"mutation {label!r} was accepted")
    counts.update(control_counts)
    pending_mutation = dict(documents)
    pending_mutation[native_path] = _replace_table_row_cell(
        documents[native_path], "Measurements and pending evidence", "Claim",
        "host_stage_trace", "Status", "pending")
    pending_observations = dict(observations)
    _, measurement_rows = _read_table(
        documents[native_path], "Measurements and pending evidence",
        native_path, "save.docs-measurements")
    row_by_claim = {_clean_cell(row["Claim"]): row for row in measurement_rows}
    for observation_key, claim in (
        ("host_identity", "tested_host_identity"),
        ("save_source_identity_sha256", "save_source_identity_sha256"),
        ("guest_fixture_source_sha256", "guest_fixture_source_sha256"),
        ("build_identity", "build_identity"),
        ("supported_sync_operations", "supported_sync_operations"),
        ("host_fault_cases", "host_fault_matrix_cases"),
        ("unsupported_host_protocol", "unsupported_host_protocol"),
    ):
        if observation_key not in pending_observations:
            pending_observations[observation_key] = _clean_cell(row_by_claim[claim]["Value"])
    try:
        check_save_docs(root, pending_observations, True,
                        _document_overrides=pending_mutation, _run_mutations=False)
    except SaveDocsError as error:
        _docs_require(error.claim_id == "save.docs-measurements" and
                      "host_stage_trace" in str(error).lower(),
                      "save.docs-contradiction",
                      f"require_measured failed at the wrong gate: {error}")
        counts["save.docs-require-measured-block"] = 1
    else:
        raise SaveDocsError("save.docs-contradiction",
                            "require_measured accepted pending evidence")
    _docs_require(control_counts["save.docs-missing"] > 0 and
                  control_counts["save.docs-contradiction"] > 0,
                  "save.docs-contradiction", "mutation controls did not exercise both failure classes")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", required=True, type=Path)
    parser.add_argument("--mode", choices=("process", "host-faults", "recovery",
                                             "barriers", "docs"), default="process")
    args = parser.parse_args()
    SaveProcessTests.runner = args.runner.resolve()
    SaveProcessTests.assertion_count = 0
    if args.mode == "host-faults":
        suite = unittest.TestSuite(
            SaveProcessTests(name) for name in (
                "test_syscall_fault_matrix_preserves_authoritative_history",
                "test_short_writes_and_eintr_publish_exact_bytes",
                "test_false_ack_control_fails_when_published_bytes_are_readable",
                "test_uncertain_retry_survives_repeated_sync_failures",
            )
        )
    elif args.mode == "recovery":
        suite = unittest.TestSuite(
            SaveProcessTests(name) for name in (
                "test_killed_stage_writers_recover_only_authoritative_target",
            )
        )
    elif args.mode == "barriers":
        suite = unittest.TestSuite(
            SaveProcessTests(name) for name in (
                "test_stage_gate_notifies_after_real_file_close",
                "test_host_barriers_serialize_old_a_before_restored_branch_b",
                "test_unresolved_post_rename_transaction_blocks_all_transitions",
                "test_obsolete_publication_control_fails_disk_latest_branch",
            )
        )
    elif args.mode == "process":
        excluded = {
            "test_syscall_fault_matrix_preserves_authoritative_history",
            "test_short_writes_and_eintr_publish_exact_bytes",
            "test_false_ack_control_fails_when_published_bytes_are_readable",
            "test_stage_gate_notifies_after_real_file_close",
            "test_killed_stage_writers_recover_only_authoritative_target",
            "test_host_barriers_serialize_old_a_before_restored_branch_b",
            "test_unresolved_post_rename_transaction_blocks_all_transitions",
            "test_obsolete_publication_control_fails_disk_latest_branch",
        }
        suite = unittest.TestSuite(
            SaveProcessTests(name) for name in
            unittest.defaultTestLoader.getTestCaseNames(SaveProcessTests)
            if name not in excluded
        )
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SaveProcessTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("SAVE_PYTHON_RESULT " + json.dumps({
        "tests": result.testsRun,
        "assertions": SaveProcessTests.assertion_count,
    }, sort_keys=True))
    if not result.wasSuccessful():
        return 1
    if args.mode == "docs":
        try:
            counts = check_save_docs(
                Path(__file__).resolve().parents[2], DOC_OBSERVATIONS,
                require_measured=False,
            )
        except Exception as error:
            print(f"SAVE_DOCS failed: {error}", file=sys.stderr)
            return 1
        print("SAVE_DOCS " + json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
