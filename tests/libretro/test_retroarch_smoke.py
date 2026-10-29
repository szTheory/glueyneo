from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import plistlib
import re
import signal
import struct
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zlib
from unittest import mock

import retroarch_smoke as smoke


def active_png_fixture(marker=b"", *, compressed=None, width=320, height=224):
    def chunk(kind,body):
        return struct.pack(">I",len(body))+kind+body+struct.pack(">I",zlib.crc32(kind+body)&0xffffffff)
    if compressed is None:
        compressed=zlib.compress(bytes(height*(width*3+1)))
    return (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,2,0,0,0))+
            (chunk(b"tEXt",b"fixture\x00"+marker) if marker else b"")+chunk(b"IDAT",compressed)+chunk(b"IEND",b""))


class ActivePNGSnapshotTests(unittest.TestCase):
    def test_complete_active_png_snapshot_is_unique_and_immutable(self):
        snapshot=getattr(smoke,"snapshot_active_scene_png",None)
        self.assertTrue(callable(snapshot),"active capture requires immutable validated owned bytes")
        with tempfile.TemporaryDirectory() as temporary:
            producer=Path(temporary)/"producer.png"
            original=active_png_fixture(b"first")
            producer.write_bytes(original)
            first,digest=snapshot(producer,{})
            producer.write_bytes(active_png_fixture(b"second"))
            second,_=snapshot(producer,{})
            self.assertNotEqual(first,producer)
            self.assertNotEqual(first,second)
            self.assertEqual(first.read_bytes(),original)
            self.assertEqual(smoke.sha256(first),digest)
            self.assertTrue(producer.exists())


class RetroArchStateContainerTests(unittest.TestCase):
    @staticmethod
    def _rastate(mem):
        padding = bytes((-len(mem)) % 8)
        return (b"RASTATE\x01" + b"MEM " + len(mem).to_bytes(4, "little") +
                mem + padding + b"END " + bytes(4))

    @staticmethod
    def _mvs_state(save_bytes, guest_readback=None):
        memory = bytearray(0x35000)
        if guest_readback is not None:
            memory[:len(guest_readback)] = bytes(guest_readback)
        for offset, value in zip((0, 1, 0x1234, 0x1235, 0xFFFE, 0xFFFF), save_bytes):
            memory[0x10000 + offset] = value
        sections = ((1, bytes(152)), (2, bytes(memory)), (3, bytes(2794)),
                    (4, bytes(2781)), (5, bytes(1186)))
        state = bytearray(72)
        state[:4] = b"GNST"
        state[4:8] = (1).to_bytes(4, "big")
        state[8:12] = (72).to_bytes(4, "big")
        state[16:20] = (1).to_bytes(4, "big")
        state[20:24] = (1).to_bytes(4, "big")
        state[24:28] = smoke.GNMV_PROFILE_MSX.to_bytes(4, "big")
        state[28:32] = (2).to_bytes(4, "big")
        state[64:68] = (5).to_bytes(4, "big")
        for section_id, payload in sections:
            state.extend(section_id.to_bytes(4, "big"))
            state.extend(len(payload).to_bytes(4, "big"))
            state.extend(payload)
        state[12:16] = len(state).to_bytes(4, "big")
        return bytes(state)

    def test_save_guest_classifier_uses_measured_mvs_backup_ram_extent(self):
        state_a = self._mvs_state((0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC))
        state_b = self._mvs_state((0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6))
        self.assertEqual(len(state_a), 224113)
        self.assertEqual(smoke.public_save_guest_sram_outcome(state_a), "A")
        self.assertEqual(smoke.public_save_guest_sram_outcome(state_b), "B")
        malformed = bytearray(state_a)
        malformed[236:240] = (0x20000).to_bytes(4, "big")
        with self.assertRaisesRegex(smoke.SmokeBlocked, "memory section"):
            smoke.extract_mvs_save_ram(bytes(malformed))

    def test_final_policy_sram_compares_actual_state_mem_with_raw_save(self):
        state_a = self._mvs_state((0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC))
        state_b = self._mvs_state((0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6),
                                  (0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6))
        raw_b = smoke.extract_mvs_save_ram(state_b)
        snapshot_b = {"bytes": len(raw_b), "sha256": hashlib.sha256(raw_b).hexdigest(),
                      "sram_outcome": "B"}

        evidence = smoke.validate_final_policy_sram(state_b, snapshot_b, "B")
        self.assertEqual(evidence["live_guest_readback"], "B")
        self.assertEqual(evidence["live_sram_outcome"], "B")
        self.assertTrue(evidence["live_disk_bytes_match"])

        raw_a = smoke.extract_mvs_save_ram(state_a)
        snapshot_a = {"bytes": len(raw_a), "sha256": hashlib.sha256(raw_a).hexdigest(),
                      "sram_outcome": "A"}
        with self.assertRaises(smoke.SmokeBlocked) as raised:
            smoke.validate_final_policy_sram(state_b, snapshot_a, "B")
        self.assertEqual(raised.exception.stage, "sram-persistence")
        self.assertEqual(raised.exception.diagnostic["live_sram_outcome"], "B")
        self.assertEqual(raised.exception.diagnostic["disk_sram_outcome"], "A")


    def test_unclassified_frontend_mem_is_retained_only_in_private_workspace(self):
        native = self._mvs_state((0, 0, 0, 0, 0, 0))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            transaction = root / "transaction"
            directory = transaction / "savestates"
            directory.mkdir(parents=True, mode=0o700)
            (directory / "public-save.state").write_bytes(self._rastate(native))
            with self.assertRaisesRegex(smoke.SmokeBlocked, "no expected public save-guest effects"):
                smoke.public_state_files(directory, 1, started_ns=0)
            retained = list(root.glob("unclassified-state-*.gnst"))
            self.assertEqual(len(retained), 1)
            self.assertEqual(smoke.read_private_regular_file(retained[0], len(native)), native)
            self.assertEqual(retained[0].stat().st_mode & 0o777, 0o600)

    def test_state_directory_reports_and_rejects_non_regular_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "states"
            directory.mkdir()
            (directory / "unexpected").mkdir()
            with self.assertRaisesRegex(smoke.SmokeBlocked, "directory entry: unexpected"):
                smoke.public_state_files(directory, 0, started_ns=0)
            (directory / "unexpected").rmdir()
            target = Path(temporary) / "outside-state"
            target.write_bytes(b"private")
            (directory / "linked").symlink_to(target)
            with self.assertRaisesRegex(smoke.SmokeBlocked, "symbolic link entry: linked"):
                smoke.public_state_files(directory, 0, started_ns=0)

    def test_state_save_waits_for_one_changed_complete_container(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "states"
            directory.mkdir()
            path = directory / "public-save.state"
            mem_a = self._mvs_state((0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC))
            mem_b = self._mvs_state((0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6),
                                    (0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6))
            path.write_bytes(self._rastate(mem_a))
            previous = smoke.public_state_file_identity_snapshot(directory)

            path.write_bytes(self._rastate(mem_b))
            states, changed = smoke.wait_for_changed_public_state_files(
                directory, 1, 0, previous, time.monotonic() + 1)

            self.assertEqual(changed, ["public-save.state"])
            self.assertEqual(states[0]["mem"], mem_b)
            self.assertNotEqual(states[0]["container_sha256"],
                                previous["public-save.state"]["sha256"])

    def test_state_save_does_not_accept_the_unchanged_existing_container(self):
        unchanged = [{"name": "public-save.state", "container": b"old",
                      "container_sha256": "a" * 64}]
        identity = {"public-save.state": {"sha256": "a" * 64,
                                           "mtime_ns": 10, "size": 3,
                                           "device": 1, "inode": 2}}
        with mock.patch.object(smoke, "public_state_files", return_value=unchanged), \
             mock.patch.object(smoke, "public_state_file_identity_snapshot",
                               return_value=identity), \
             mock.patch.object(smoke.time, "monotonic",
                               side_effect=[0.0, 0.0, 2.0]), \
             mock.patch.object(smoke.time, "sleep"):
            with self.assertRaisesRegex(smoke.SmokeBlocked,
                                        "without one changed complete RASTATE"):
                smoke.wait_for_changed_public_state_files(
                    Path("states"), 1, 0, identity, 1.0)

    def test_extracts_the_exact_aligned_mem_payload(self):
        extract = getattr(smoke, "extract_rastate_mem", None)
        self.assertTrue(callable(extract), "public-state evidence needs a bounded RASTATE MEM extractor")
        native = b"GNST" + bytes(range(13))
        padding = bytes((-len(native)) % 8)
        container = (b"RASTATE\x01" + b"MEM " + struct.pack("<I", len(native)) + native +
                     padding + b"END " + bytes(4))
        self.assertEqual(extract(container), native)

    def test_rastate_mem_rejects_duplicate_unknown_compressed_and_bad_padding(self):
        native = b"GNST" + bytes(range(13))
        padding = bytes((-len(native)) % 8)
        mem = b"MEM " + struct.pack("<I", len(native)) + native + padding
        valid = b"RASTATE\x01" + mem + b"END " + bytes(4)
        mutations = (
            valid[:-12] + mem + valid[-12:],
            b"RASTATE\x01" + b"NOPE" + struct.pack("<I", 1) + b"x" * 8 + mem +
            b"END " + bytes(4),
            valid[:-12],
            valid + b"extra",
            valid[:8] + b"MEM " + struct.pack("<I", len(native)) + native +
            b"\x01" + padding[1:] + b"END " + bytes(4),
            b"RASTATE\x00" + valid[8:],
        )
        for mutation in mutations:
            with self.subTest(size=len(mutation)):
                with self.assertRaises(smoke.SmokeBlocked):
                    smoke.extract_rastate_mem(mutation)


class PrivateStateContinuationTests(unittest.TestCase):
    @staticmethod
    def _synthetic_private_result():
        identifiers = {
            name: hashlib.sha256(f"synthetic-only-private-{name}".encode()).hexdigest()
            for name in (*sorted(smoke.PRIVATE_STATE_IDENTITY_FIELDS),
                         "saved_mem_sha256", "restored_mem_sha256", "video_sha256",
                         "audio_sha256", "unexpected_nested_identifier")
        }
        result = {
            "status": "pass", "mode": "private-state",
            "identity": {name: value for name, value in identifiers.items()
                         if name in smoke.PRIVATE_STATE_IDENTITY_FIELDS},
            "private_continuation": {
                "saved_mem_sha256": identifiers["saved_mem_sha256"],
                "restored_mem_sha256": identifiers["restored_mem_sha256"],
                "saved_and_restored_mem_equal": True,
                "frames": [{name: identifiers[name]
                            for name in ("video_sha256", "audio_sha256")}],
                "native_witness": {"unexpected": [{"identifier": identifiers[
                    "unexpected_nested_identifier"]}]},
            },
            "unexpected": {"nested": list(identifiers.values())},
        }
        return result, identifiers

    def _private_main(self, transaction):
        with tempfile.TemporaryDirectory(prefix="glueyneo-private-receipt-") as temporary:
            root = Path(temporary)
            report = root / "private.json"
            argv = ["retroarch_smoke.py", "--retroarch", "synthetic-app",
                    "--core", "synthetic-core", "--content", "synthetic-content",
                    "--observed-core", "synthetic-observed", "--witness", "synthetic-witness",
                    "--continuation-route", "private-state",
                    "--private-contract", "synthetic-contract", "--report", str(report)]
            with (mock.patch.object(sys, "argv", argv),
                  mock.patch.dict(os.environ, {"GLUEYNEO_FRONTEND_WORK": str(root)}),
                  mock.patch.object(smoke, "install_signal_cleanup"),
                  mock.patch.object(smoke, "_run_private_state_transaction", side_effect=transaction),
                  mock.patch.object(smoke, "validate_inputs", return_value=(
                      Path("synthetic-app"), Path("synthetic-core"), Path("synthetic-content"),
                      {"unexpected": "synthetic-private-input-identity"})),
                  contextlib.redirect_stdout(io.StringIO()) as stdout,
                  contextlib.redirect_stderr(io.StringIO()) as stderr):
                code = smoke.main()
            lines = stdout.getvalue().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            persisted = json.loads(report.read_text(encoding="utf-8"))
        return code, json.loads(lines[0]), stdout.getvalue() + stderr.getvalue(), persisted

    def test_private_main_success_only_publishes_receipt_and_preserves_full_report(self):
        result, identifiers = self._synthetic_private_result()
        original = json.loads(json.dumps(result))

        def transaction(_args, _root, attempt):
            attempt["identity"] = dict(result["identity"])
            return result

        code, receipt, output, persisted = self._private_main(transaction)
        self.assertEqual(code, 0)
        self.assertEqual(receipt, {"mode": "private-state", "status": "pass"})
        for identifier in identifiers.values():
            self.assertNotIn(identifier, output)
        self.assertEqual(result, original, "publication must not mutate the private result")
        self.assertEqual(persisted["result"], original)
        self.assertEqual(persisted["identity"], original["identity"])
        self.assertEqual(persisted["status"], "pass")

    def test_private_main_blocked_and_failed_diagnostics_stay_private(self):
        result, identifiers = self._synthetic_private_result()
        for stage, status in (("preflight", "blocked_or_unknown"),
                              ("continuation-observations", "fail"),
                              (identifiers["unexpected_nested_identifier"], "fail")):
            with self.subTest(stage=stage):
                def transaction(_args, _root, attempt):
                    attempt["identity"] = dict(result["identity"])
                    attempt["unexpected"] = result["unexpected"]
                    error = smoke.SmokeBlocked(stage, identifiers["saved_mem_sha256"],
                                               diagnostic=result)
                    error.availability = identifiers["audio_sha256"]
                    raise error

                code, receipt, output, persisted = self._private_main(transaction)
                self.assertEqual(code, 1)
                self.assertEqual(receipt, {"mode": "private-state", "status": status})
                for identifier in identifiers.values():
                    self.assertNotIn(identifier, output)
                self.assertNotIn("synthetic-private-input-identity", output)
                self.assertEqual(persisted["status"], status)
                self.assertEqual(persisted["identity"], result["identity"])
                self.assertEqual(persisted["unexpected"], result["unexpected"])
                self.assertEqual(persisted["stage"], stage)
                self.assertEqual(persisted["reason"], identifiers["saved_mem_sha256"])

    def test_private_main_internal_failure_does_not_publish_exception_identity(self):
        result, identifiers = self._synthetic_private_result()
        private_error = type("SyntheticPrivateError_" + identifiers["video_sha256"],
                             (RuntimeError,), {})

        def transaction(_args, _root, attempt):
            attempt["identity"] = dict(result["identity"])
            raise private_error(identifiers["audio_sha256"])

        code, receipt, output, persisted = self._private_main(transaction)
        self.assertEqual(code, 1)
        self.assertEqual(receipt, {"mode": "private-state", "status": "fail"})
        for identifier in identifiers.values():
            self.assertNotIn(identifier, output)
        self.assertEqual(persisted["status"], "fail")
        self.assertEqual(persisted["internal_error"], private_error.__name__)
        self.assertEqual(persisted["identity"], result["identity"])

    def test_private_main_rejects_untrusted_status_values(self):
        result, identifiers = self._synthetic_private_result()
        for status in (identifiers["content_sha256"], {"nested": identifiers["video_sha256"]}):
            with self.subTest(status=status):
                candidate = dict(result, status=status)
                code, receipt, output, persisted = self._private_main(
                    lambda _args, _root, _attempt: candidate)
                self.assertEqual(code, 1)
                self.assertEqual(receipt, {"mode": "private-state", "status": "fail"})
                for identifier in identifiers.values():
                    self.assertNotIn(identifier, output)
                self.assertEqual(persisted["result"], candidate)

    def test_source_bound_private_state_validator_is_exposed(self):
        validator = getattr(smoke, "validate_private_state_identity", None)
        self.assertTrue(callable(validator),
                        "private continuation must bind current source, scene, and content identities")
        expected = {key: "a" * 64 for key in (
            "scene_contract_sha256", "sound_contract_sha256", "schedule_identity",
            "media_identity_sha256", "importer_sha256", "content_sha256",
            "production_core_sha256", "observed_core_sha256", "witness_sha256",
            "retroarch_sha256")}
        self.assertTrue(validator(expected, dict(expected)))
        stale_scene = dict(expected, scene_contract_sha256="b" * 64)
        self.assertFalse(validator(expected, stale_scene), "a different selected scene must fail closed")
        missing_media = dict(expected)
        del missing_media["media_identity_sha256"]
        self.assertFalse(validator(expected, missing_media), "missing selected media identity must fail closed")

    def test_public_json_rejects_raw_private_bytes(self):
        try:
            encoded = smoke.public_json({"status": "pass", "payload": b"private-state-bytes"})
        except (TypeError, ValueError):
            encoded = None
        self.assertEqual(json.loads(encoded) if encoded is not None else None,
                         {"status": "fail", "reason": "private-report-serialization-failed"})

    def test_public_json_redacts_private_capture_paths(self):
        encoded = smoke.public_json({"status": "pass",
                                     "capture": "/private/tmp/owned-session/private-frame.png"})
        self.assertEqual(json.loads(encoded),
                         {"status": "fail", "reason": "private-path-survived"})


class MVSObserverEpochTests(unittest.TestCase):
    def test_reset_records_new_epoch_with_selector_sampled_frame(self):
        keys = mock.Mock()
        process = mock.Mock()
        log = Path("retroarch.log")
        reset_frame = {"sampled_mask": 64, "successful_video_sequence": 1}
        release_frame = {"sampled_mask": 64, "successful_video_sequence": 2}
        with mock.patch.object(smoke, "read_frontend_log", return_value=b"startup"), \
             mock.patch.object(smoke, "mvs_observation_epoch_count", return_value=1), \
             mock.patch.object(smoke, "wait_for_new_mvs_observation_epoch",
                               return_value=2) as wait_epoch, \
             mock.patch.object(smoke, "wait_for_mvs_completed_mask",
                               side_effect=[reset_frame, release_frame]) as wait_frame:
            result = smoke.reset_guest_under_mask(
                keys, 64, log, process, "fresh", 10)
        keys.set_mask.assert_called_once_with(64)
        keys.post_key.assert_has_calls([mock.call(smoke.RESET_KEY_CODE, True),
                                        mock.call(smoke.RESET_KEY_CODE, False)])
        wait_epoch.assert_called_once_with(log, 1, process, 10)
        self.assertEqual(wait_frame.call_args_list, [
            mock.call(log, 64, -1, process, "fresh", 10),
            mock.call(log, 64, 1, process, "fresh", 10),
        ])
        self.assertEqual(result, {**release_frame, "observation_epoch": 2,
                                  "reset_trigger_video_sequence": 1,
                                  "reset_action": "configured reset key"})

    def test_reset_can_use_native_command_action_and_still_requires_new_epoch(self):
        keys = mock.Mock()
        process = mock.Mock()
        log = Path("retroarch.log")
        reset_frame = {"sampled_mask": 64, "successful_video_sequence": 1}
        release_frame = {"sampled_mask": 64, "successful_video_sequence": 2}
        with mock.patch.object(smoke, "read_frontend_log", return_value=b"startup"), \
             mock.patch.object(smoke, "mvs_observation_epoch_count", return_value=1), \
             mock.patch.object(smoke, "invoke_native_reset_menu",
                               return_value={"menu_bar_item": "Command",
                                             "item": "Reset",
                                             "activation": "accessible menu-item click returned"}) as reset_menu, \
             mock.patch.object(smoke, "sample_owned_process_if_reset_pending",
                               return_value={"status": "reset-epoch-arrived-before-sample"}) as sample_pending, \
             mock.patch.object(smoke, "wait_for_new_mvs_observation_epoch",
                               return_value=2) as wait_epoch, \
             mock.patch.object(smoke, "wait_for_mvs_completed_mask",
                               side_effect=[reset_frame, release_frame]) as wait_frame:
            result = smoke.reset_guest_under_mask(
                keys, 64, log, process, "fresh", 10, via_native_menu=True)
        keys.set_mask.assert_called_once_with(64)
        keys.post_key.assert_not_called()
        reset_menu.assert_called_once_with(process, log=log)
        sample_pending.assert_called_once_with(log, 1, process, 10)
        wait_epoch.assert_called_once_with(log, 1, process, 10)
        self.assertEqual(wait_frame.call_args_list, [
            mock.call(log, 64, -1, process, "fresh", 10),
            mock.call(log, 64, 1, process, "fresh", 10),
        ])
        self.assertEqual(result["reset_action"], "RetroArch Command > Reset")
        self.assertEqual(result["observation_epoch"], 2)
        self.assertEqual(result["reset_menu_probe"]["activation"],
                         "accessible menu-item click returned")
        self.assertEqual(result["reset_pending_sample"]["status"],
                         "reset-epoch-arrived-before-sample")

    def test_counts_only_complete_frontend_prefixed_begin_records(self):
        count = getattr(smoke, "mvs_observation_epoch_count", None)
        self.assertTrue(callable(count), "reset-driven guest input needs an observable new MVS epoch")
        log = (
            b"[INFO] glueyneo: mvs B 0 0 0 0\n"
            b"[INFO] glueyneo: mvs S 1 64 0 0\n"
            b"[libretro INFO] glueyneo: mvs B 0 0 0 0\n"
            b"noise glueyneo: mvs B 0 0 0 0\n"
            b"[INFO] glueyneo: mvs B 0 0 0 0"
        )
        self.assertEqual(count(log), 2)

    def test_epoch_counter_rejects_unbounded_or_nonbyte_logs(self):
        count = getattr(smoke, "mvs_observation_epoch_count", None)
        self.assertTrue(callable(count), "reset-driven guest input needs an observable new MVS epoch")
        with self.assertRaisesRegex(smoke.SmokeBlocked, "log exceeds"):
            count(b"x" * (smoke.MVS_FRONTEND_LOG_LIMIT + 1))
        with self.assertRaises(smoke.SmokeBlocked):
            count("not bytes")


class RetroArchContinuationLogTests(unittest.TestCase):
    @staticmethod
    def records():
        prefix = b"glueyneo: continuation "
        restored_state = RetroArchStateContainerTests._mvs_state(
            (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC))
        lines = [prefix + f"S {len(restored_state)} 2 200".encode(),
                 prefix + f"R {len(restored_state)} 3 300".encode()]
        for offset in range(0, len(restored_state), smoke.CONTINUATION_CHUNK_BYTES):
            chunk = restored_state[offset:offset + smoke.CONTINUATION_CHUNK_BYTES]
            lines.append(prefix + f"M 0 {offset} ".encode() + chunk.hex().encode())
        for frame in range(4):
            lines.append(prefix + f"F {frame} {frame} {(frame + 1) * 100} 2".encode())
            for kind, data in (("V", bytes(smoke.CONTINUATION_VIDEO_BYTES)),
                               ("A", bytes(8))):
                for offset in range(0, len(data), smoke.CONTINUATION_CHUNK_BYTES):
                    chunk = data[offset:offset + smoke.CONTINUATION_CHUNK_BYTES]
                    lines.append(prefix + f"{kind} {frame} {offset} ".encode() +
                                 chunk.hex().encode())
        lines.append(prefix + b"E 4")
        return lines

    @staticmethod
    def witness_trace(frames):
        trace = bytearray(b"GNFO" + struct.pack(">II", 1, 4))
        prior_cycles = 0
        for frame in frames:
            audio_bytes = len(frame["audio"])
            trace.extend(struct.pack(">IQIII", frame["input_mask"],
                                     frame["cycle_delta"] - prior_cycles,
                                     frame["audio_frames"],
                                     len(frame["video"]), audio_bytes))
            trace.extend(frame["video"])
            trace.extend(frame["audio"])
            prior_cycles = frame["cycle_delta"]
        return bytes(trace)

    def test_raw_observer_window_parses_exactly_four_frames(self):
        parsed = smoke.parse_continuation_observations(b"\n".join(self.records()) + b"\n")
        self.assertEqual(parsed["capture"]["completed_frames"], 2)
        self.assertEqual(parsed["restore"]["completed_frames"], 3)
        self.assertEqual(parsed["restore"]["state"], RetroArchStateContainerTests._mvs_state(
            (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC)))
        self.assertEqual(len(parsed["frames"]), 4)
        self.assertEqual(len(parsed["frames"][0]["video"]), smoke.CONTINUATION_VIDEO_BYTES)
        self.assertEqual(parsed["frames"][3]["input_mask"], 3)

    def test_frame_barrier_waits_for_synchronous_video_and_audio_trace(self):
        records = self.records()
        first_frame = records.index(next(record for record in records
                                          if record.startswith(b"glueyneo: continuation F 0 ")))
        second_frame = records.index(next(record for record in records
                                           if record.startswith(b"glueyneo: continuation F 1 ")))
        f_only = b"\n".join(records[:first_frame + 1]) + b"\n"
        first_complete = b"\n".join(records[:second_frame]) + b"\n"
        partial_audio = first_complete[:-2]
        self.assertEqual(smoke.completed_continuation_frame_count(f_only), 0)
        self.assertEqual(smoke.completed_continuation_frame_count(partial_audio), 0)
        self.assertEqual(smoke.completed_continuation_frame_count(first_complete), 1)
        self.assertEqual(smoke.completed_continuation_frame_count(
            b"\n".join(records) + b"\n"), 4)

    def test_load_undo_snapshot_is_not_counted_as_the_post_restore_save(self):
        prefix = b"glueyneo: continuation "
        before_restore = b"\n".join((
            prefix + b"S 224113 15 300",
            prefix + b"S 224113 35 700",
            prefix + b"S 224113 37 750",  # load's undo-buffer serialization
            prefix + b"R 224113 37 750",
        )) + b"\n"
        baseline = smoke.continuation_event_count(before_restore, "S")
        self.assertEqual(baseline, 3)
        after_restore = before_restore + prefix + b"S 224113 37 760\n"
        self.assertEqual(smoke.continuation_event_count(after_restore, "S"), baseline + 1)
        self.assertEqual(smoke.continuation_event_count(after_restore, "R"), 1)
        with self.assertRaises(smoke.SmokeBlocked):
            smoke.continuation_event_count(after_restore, "F")

    def test_failed_live_continuation_trace_is_retained_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "transaction").mkdir(mode=0o700)
            log = root / "transaction" / "retroarch.log"
            log.write_bytes(b"[libretro INFO] glueyneo: continuation F 0 1 2 0\n")
            smoke.preserve_continuation_failure_log(root, log)
            retained = root / "continuation-failure.log"
            self.assertEqual(retained.read_bytes(), log.read_bytes())
            self.assertEqual(retained.stat().st_mode & 0o777, 0o600)


    def test_raw_observer_window_accepts_pinned_frontend_log_prefixes(self):
        log = b"\n".join(b"[INFO] " + line for line in self.records()) + b"\n"
        parsed = smoke.parse_continuation_observations(log)
        self.assertEqual(parsed["restore"]["state"], RetroArchStateContainerTests._mvs_state(
            (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC)))
        self.assertEqual([frame["input_mask"] for frame in parsed["frames"]], [0, 1, 2, 3])

    def test_frontend_load_undo_capture_may_share_the_restore_boundary(self):
        prefix = b"glueyneo: continuation "
        records = self.records()
        size = len(RetroArchStateContainerTests._mvs_state(
            (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC)))
        records.insert(1, prefix + f"S {size} 3 300".encode())
        records[2] = prefix + f"R {size} 3 300".encode()
        parsed = smoke.parse_continuation_observations(b"\n".join(records) + b"\n")
        self.assertEqual(len(parsed["captures"]), 2)
        self.assertEqual(parsed["captures"][-1]["completed_frames"],
                         parsed["restore"]["completed_frames"])

    def test_public_save_route_compares_exact_silent_output(self):
        parsed = smoke.parse_continuation_observations(b"\n".join(self.records()) + b"\n")
        comparison = smoke.compare_frontend_trace(self.witness_trace(parsed["frames"]), parsed)
        self.assertEqual(comparison["nonzero_audio_samples"], 0)
        self.assertEqual(comparison["nonzero_video_bytes"], 0)

    def test_raw_video_and_pcm_byte_mutations_fail_the_exact_callback_comparison(self):
        parsed = smoke.parse_continuation_observations(b"\n".join(self.records()) + b"\n")
        baseline = self.witness_trace(parsed["frames"])
        first_frame = 12
        video_offset = first_frame + 24
        audio_offset = video_offset + smoke.CONTINUATION_VIDEO_BYTES
        for name, offset in (("video", video_offset), ("PCM", audio_offset)):
            mutated = bytearray(baseline)
            mutated[offset] ^= 0x01
            with self.subTest(callback=name), self.assertRaisesRegex(
                    smoke.SmokeBlocked, "raw callback video or core PCM differs"):
                smoke.compare_frontend_trace(bytes(mutated), parsed)

    def test_input_mask_order_and_replay_cursor_mutations_fail_alignment(self):
        parsed = smoke.parse_continuation_observations(b"\n".join(self.records()) + b"\n")
        baseline = self.witness_trace(parsed["frames"])
        first_mask = bytearray(baseline)
        first_mask[12] ^= 0x40
        with self.assertRaisesRegex(smoke.SmokeBlocked, "native input, cycle, or callback extent differs"):
            smoke.compare_frontend_trace(bytes(first_mask), parsed)

        second_frame_offset = 12 + 24 + smoke.CONTINUATION_VIDEO_BYTES + 8
        reordered = bytearray(baseline)
        reordered[12:16], reordered[second_frame_offset:second_frame_offset + 4] = (
            reordered[second_frame_offset:second_frame_offset + 4], reordered[12:16])
        with self.assertRaisesRegex(smoke.SmokeBlocked, "native input, cycle, or callback extent differs"):
            smoke.compare_frontend_trace(bytes(reordered), parsed)

        replay_cancelled = [dict(frame) for frame in parsed["frames"]]
        replay_cancelled[1]["input_mask"] = replay_cancelled[0]["input_mask"]
        with self.assertRaisesRegex(smoke.SmokeBlocked, "native input, cycle, or callback extent differs"):
            smoke.compare_frontend_trace(baseline, {**parsed, "frames": replay_cancelled})

    def test_cycle_mutation_fails_the_emulated_time_alignment_assertion(self):
        parsed = smoke.parse_continuation_observations(b"\n".join(self.records()) + b"\n")
        mutated = bytearray(self.witness_trace(parsed["frames"]))
        mutated[16] ^= 0x01  # First frame's big-endian elapsed-cycle field.
        with self.assertRaisesRegex(smoke.SmokeBlocked, "native input, cycle, or callback extent differs"):
            smoke.compare_frontend_trace(bytes(mutated), parsed)

    def test_mutated_restore_boundary_and_omitted_load_fail_before_native_import(self):
        prefix = b"glueyneo: continuation "
        valid = self.records()
        restore_index = next(index for index, line in enumerate(valid)
                             if line.startswith(prefix + b"R "))
        boundary_mutation = list(valid)
        size = len(RetroArchStateContainerTests._mvs_state(
            (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC)))
        boundary_mutation[restore_index] = prefix + f"R {size} 2 300".encode()
        for name, records in (
                ("restore boundary", boundary_mutation),
                ("swallowed load", [line for line in valid
                                    if not line.startswith((prefix + b"R ", prefix + b"M "))])):
            with self.subTest(mutation=name), self.assertRaises(smoke.SmokeBlocked):
                smoke.parse_continuation_observations(b"\n".join(records) + b"\n")

    def test_mutated_extracted_mem_differs_from_the_observed_restore_payload(self):
        state = RetroArchStateContainerTests._mvs_state(
            (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC))
        padding = bytes((-len(state)) % 8)
        container = bytearray(b"RASTATE\x01" + b"MEM " + struct.pack("<I", len(state)) +
                              state + padding + b"END " + bytes(4))
        container[16 + len(state) - 1] ^= 0x01
        extracted = smoke.extract_rastate_mem(bytes(container))
        self.assertNotEqual(extracted, state,
                            "one changed extracted MEM byte must break the observed restore identity")
        with self.assertRaisesRegex(smoke.SmokeBlocked,
                                    "actual loaded MEM differs from slot-zero state"):
            smoke.require_matching_frontend_mem(state, extracted)

    def test_raw_observer_window_rejects_missing_duplicate_mutated_and_incomplete_records(self):
        base = self.records()
        prefix = b"glueyneo: continuation "
        video_line = next(index for index, line in enumerate(base)
                          if line.startswith(prefix + b"V "))
        mutations = []
        mutations.append(base[1:])
        mutations.append(base[:1] + [base[0]] + base[1:])
        mutations.append(base[:video_line] + [base[video_line].replace(b"V 0 0 ", b"V 0 1 ", 1)] +
                         base[video_line + 1:])
        mutations.append(base[:video_line] + [prefix + b"X 0"] + base[video_line:])
        mutations.append(base[:-1])
        oversized = base[:video_line] + [base[video_line] + b"00"] + base[video_line + 1:]
        mutations.append(oversized)
        for records in mutations:
            with self.subTest(record_count=len(records)):
                with self.assertRaises(smoke.SmokeBlocked):
                    smoke.parse_continuation_observations(b"\n".join(records) + b"\n")
        with self.assertRaises(smoke.SmokeBlocked):
            smoke.parse_continuation_observations(bytes(smoke.CONTINUATION_LOG_MAX_BYTES + 1))

    def test_active_snapshot_rejects_partial_bad_crc_and_trailing_png_bytes(self):
        valid=active_png_fixture()
        idat=valid.index(b"IDAT")
        size=int.from_bytes(valid[idat-4:idat],"big")
        crc=idat+4+size
        bad_crc=valid[:crc]+bytes([valid[crc]^1])+valid[crc+1:]
        without_idat=valid[:idat-4]+valid[crc+4:]
        iend_body=b"IENDx"
        bad_iend=valid[:-12]+struct.pack(">I",1)+iend_body+struct.pack(">I",zlib.crc32(iend_body)&0xffffffff)
        mutations=(valid[:-12],valid[:-1],bad_crc,valid+b"trailing PNG bytes",
                   without_idat,bad_iend,valid[:33]+valid[8:33]+valid[33:],active_png_fixture(width=321))
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"candidate.png"
            for data in mutations:
                path.write_bytes(data)
                self.assertIsNone(smoke.snapshot_active_scene_png(path,{}))
            self.assertEqual(list(Path(temporary).glob("active-capture-*.png")),[])

    def test_active_snapshot_rejects_stale_symlink_oversized_and_changing_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            path=directory/"candidate.png"
            path.write_bytes(active_png_fixture())
            self.assertIsNone(smoke.snapshot_active_scene_png(path,{path:path.stat().st_mtime_ns}))
            link=directory/"link.png"
            link.symlink_to(path)
            self.assertIsNone(smoke.snapshot_active_scene_png(link,{}))
            with path.open("ab") as stream:
                stream.truncate(smoke.TITLE_CAPTURE_MAX_BYTES+1)
            with mock.patch.object(smoke.os,"open") as opened:
                self.assertIsNone(smoke.snapshot_active_scene_png(path,{}))
                opened.assert_not_called()
            path.write_bytes(active_png_fixture())
            before=path.stat()
            changed=mock.Mock(**{key:getattr(before,key) for key in
                ("st_dev","st_ino","st_size","st_mtime_ns","st_ctime_ns","st_mode")})
            changed.st_ctime_ns+=1
            with mock.patch.object(smoke.os,"fstat",side_effect=[before,changed]):
                self.assertIsNone(smoke.snapshot_active_scene_png(path,{}))
            replacement=directory/"replacement.png"
            replacement.write_bytes(active_png_fixture(b"replacement"))
            fstat=smoke.os.fstat
            calls=[0]
            def swapped(descriptor):
                value=fstat(descriptor)
                calls[0]+=1
                if calls[0]==2:
                    replacement.replace(path)
                return value
            with mock.patch.object(smoke.os,"fstat",side_effect=swapped):
                self.assertIsNone(smoke.snapshot_active_scene_png(path,{}))
            self.assertEqual(list(directory.glob("active-capture-*.png")),[])

    def test_active_snapshot_rejects_unknown_critical_chunk(self):
        valid=active_png_fixture()
        kind=b"ABCD"
        unknown=struct.pack(">I",0)+kind+struct.pack(">I",zlib.crc32(kind)&0xffffffff)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"critical.png"
            path.write_bytes(valid[:33]+unknown+valid[33:])
            self.assertIsNone(smoke.snapshot_active_scene_png(path,{}))

    def test_active_snapshot_rejects_nonconsecutive_idat(self):
        valid=active_png_fixture()
        start=valid.index(b"IDAT")
        size=int.from_bytes(valid[start-4:start],"big")
        stream=valid[start+4:start+4+size]
        def chunk(kind,body):
            return struct.pack(">I",len(body))+kind+body+struct.pack(">I",zlib.crc32(kind+body)&0xffffffff)
        split=(chunk(b"IDAT",stream[:len(stream)//2])+chunk(b"tEXt",b"fixture\x00gap")+
               chunk(b"IDAT",stream[len(stream)//2:]))
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"split.png"
            path.write_bytes(valid[:start-4]+split+valid[start+size+8:])
            self.assertIsNone(smoke.snapshot_active_scene_png(path,{}))

    def test_active_snapshot_bounds_chunk_count(self):
        valid=active_png_fixture()
        chunk=b"tEXt"
        empty_chunk=struct.pack(">I",0)+chunk+struct.pack(">I",zlib.crc32(chunk)&0xffffffff)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"many.png"
            path.write_bytes(valid[:33]+empty_chunk*4096+valid[33:])
            self.assertIsNone(smoke.snapshot_active_scene_png(path,{}))

    def test_full_decoder_rejects_incomplete_or_trailing_deflate_stream(self):
        raw=bytes(224*(320*3+1))
        stream=zlib.compress(raw)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"stream.png"
            for bad in (stream[:-4],stream+b"trailing deflate bytes"):
                path.write_bytes(active_png_fixture(compressed=bad))
                with self.assertRaises(smoke.SmokeBlocked):
                    smoke.decode_png(path)


class RetroArchSavePolicyRouteTests(unittest.TestCase):
    def test_cli_exposes_sram_policy_route(self):
        completed = smoke.subprocess.run(
            [smoke.sys.executable, str(Path(smoke.__file__)), "--help"],
            stdout=smoke.subprocess.PIPE, stderr=smoke.subprocess.PIPE,
            text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("sram-policies", completed.stdout)
        self.assertIn("periodic-save", completed.stdout)
        self.assertIn("focused-undo-control", completed.stdout)

    def test_fresh_guest_readback_is_decodable_from_native_state(self):
        readback = getattr(smoke, "public_save_guest_readback", None)
        self.assertTrue(callable(readback),
                        "fresh save-file consumption needs a native guest readback extractor")
        state_a = bytearray(RetroArchStateContainerTests._mvs_state(
            (0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6)))
        state_a[240:246] = bytes((0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6))
        self.assertEqual(readback(bytes(state_a)), "B")
        state_a[240:246] = bytes(6)
        self.assertIsNone(readback(bytes(state_a)))

    def test_restore_history_parser_keeps_load_and_undo_payloads_distinct(self):
        parser = getattr(smoke, "parse_continuation_restore_states", None)
        self.assertTrue(callable(parser),
                        "load and undo-load need separately bound native restore payloads")
        state_a = RetroArchStateContainerTests._mvs_state(
            (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC))
        state_b = RetroArchStateContainerTests._mvs_state(
            (0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6))

        def records(state):
            prefix = b"glueyneo: continuation "
            lines = [prefix + f"R {len(state)} 2 200".encode()]
            for offset in range(0, len(state), smoke.CONTINUATION_CHUNK_BYTES):
                chunk = state[offset:offset + smoke.CONTINUATION_CHUNK_BYTES]
                lines.append(prefix + f"M 0 {offset} ".encode() + chunk.hex().encode())
            return lines

        parsed = parser(b"\n".join(records(state_a) + records(state_b)) + b"\n")
        self.assertEqual(parsed, [state_a, state_b])

    def test_restore_payload_wait_handles_marker_before_final_chunk(self):
        state_a = RetroArchStateContainerTests._mvs_state(
            (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC))
        state_b = RetroArchStateContainerTests._mvs_state(
            (0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6))

        def records(state):
            prefix = b"glueyneo: continuation "
            lines = [prefix + f"R {len(state)} 2 200".encode()]
            for offset in range(0, len(state), smoke.CONTINUATION_CHUNK_BYTES):
                chunk = state[offset:offset + smoke.CONTINUATION_CHUNK_BYTES]
                lines.append(prefix + f"M 0 {offset} ".encode() + chunk.hex().encode())
            return lines

        partial_tail = (b"\n".join(records(state_a) + records(state_b)[:-1]) +
                        b"\n" + records(state_b)[-1][:100])
        parser = smoke.parse_continuation_restore_states
        with self.assertRaises(smoke.SmokeBlocked):
            parser(partial_tail)
        self.assertEqual(parser(partial_tail, allow_partial_tail=True), [state_a])
        complete = b"\n".join(records(state_a) + records(state_b)) + b"\n"
        process = mock.Mock(returncode=None)
        process.poll.return_value = None
        with mock.patch.object(smoke, "read_frontend_log",
                               side_effect=[partial_tail, complete]), \
             mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke.time, "sleep"):
            restored = smoke.wait_for_continuation_restore_states(
                Path("private.log"), 2, process, time.monotonic() + 1)
        self.assertEqual(restored, [state_a, state_b])

    def test_undo_load_accepts_preload_b_history_after_it_advanced_past_saved_b_file(self):
        validate = getattr(smoke, "validate_undo_load_restore_history", None)
        self.assertTrue(callable(validate),
                        "undo-load must validate its real pre-load B snapshot")
        def state(save_bytes, guest_bytes):
            value = bytearray(RetroArchStateContainerTests._mvs_state(save_bytes))
            memory_start, _ = smoke._mvs_state_memory_bounds(bytes(value))
            value[memory_start:memory_start + 6] = guest_bytes
            return bytes(value), memory_start

        state_a, _ = state((0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC),
                           (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC))
        saved_b, memory_start = state((0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6),
                                      (0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6))
        undo_b = bytearray(saved_b)
        undo_b[memory_start + 6] ^= 1  # B continued before the later load captured undo.
        result = validate([state_a, bytes(undo_b)], state_a)
        self.assertEqual(result["undo_guest_readback"], "B")
        self.assertEqual(result["undo_sram_outcome"], "B")
        self.assertTrue(result["distinct_non_sram_machine_state"])
        undo_a = bytearray(state_a)
        undo_a[memory_start + 6] ^= 1
        invalid = (("duplicate load", [state_a, state_a]),
                   ("wrong guest branch", [state_a, bytes(undo_a)]))
        for label, bad_restores in invalid:
            with self.subTest(label=label), self.assertRaises(smoke.SmokeBlocked):
                validate(bad_restores, state_a)

    def test_focused_undo_requires_b_sram_but_allows_empty_initial_readback(self):
        validate = getattr(smoke, "validate_focused_undo_load_history", None)
        self.assertTrue(callable(validate),
                        "focused undo must still prove B SRAM without requiring a seeded file")
        state_a = RetroArchStateContainerTests._mvs_state(
            (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC))
        undo_b = bytearray(RetroArchStateContainerTests._mvs_state(
            (0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6)))
        memory_start, _ = smoke._mvs_state_memory_bounds(bytes(undo_b))
        undo_b[memory_start + 6] = 1  # Distinct non-SRAM live history.
        result = validate([state_a, bytes(undo_b)], state_a)
        self.assertIsNone(result["undo_guest_readback"])
        self.assertEqual(result["undo_sram_outcome"], "B")
        self.assertTrue(result["distinct_non_sram_machine_state"])
        wrong_sram = bytearray(undo_b)
        for offset, value in zip((0, 1, 0x1234, 0x1235, 0xFFFE, 0xFFFF),
                                 (0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC)):
            wrong_sram[memory_start + 0x10000 + offset] = value
        with self.assertRaises(smoke.SmokeBlocked):
            validate([state_a, bytes(wrong_sram)], state_a)

    def test_operation_matrix_fails_closed_for_autosave_restore_and_external_writes(self):
        validator = getattr(smoke, "validate_continuation_operation_matrix", None)
        self.assertTrue(callable(validator),
                        "frontend route selection needs a fail-closed operation matrix")
        self.assertEqual(validator("sram-policies", state_operations=True,
                                   autosave_interval=0), "sram-policies")
        self.assertEqual(validator("focused-undo-control", state_operations=True,
                                   autosave_interval=0), "focused-undo-control")
        self.assertEqual(validator("periodic-save", state_operations=False,
                                   autosave_interval=1), "periodic-save")
        invalid = (
            {"route": "sram-policies", "state_operations": True,
             "autosave_interval": 1},
            {"route": "periodic-save", "state_operations": True,
             "autosave_interval": 1},
            {"route": "periodic-save", "state_operations": False,
             "autosave_interval": 1, "external_sram_write": True},
        )
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(smoke.SmokeBlocked):
                validator(**options)

    def test_periodic_config_is_separate_and_pins_normal_sram_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work, captures = root / "work", root / "captures"
            savefiles, savestates = root / "savefiles", root / "savestates"
            for directory in (work, captures, savefiles, savestates):
                directory.mkdir()
            path = smoke.write_frontend_config(
                work, captures, savefiles=savefiles, savestates=savestates,
                periodic_save=True, autosave_interval=1, null_audio=True)
            config = path.read_text()
            self.assertIn('autosave_interval = "1"', config)
            self.assertIn('block_sram_overwrite = "false"', config)
            self.assertIn('input_save_state = "nul"', config)
            self.assertIn('input_load_state = "nul"', config)
            self.assertIn('input_menu_toggle = "nul"', config)
            self.assertIn('input_exit_emulator = "escape"', config)
            self.assertIn('save_file_compression = "false"', config)
            self.assertTrue(smoke.validate_active_config_destinations(
                config, work, captures, savefiles=savefiles, savestates=savestates,
                periodic_save=True, autosave_interval=1))
            for invalid in (
                    config.replace('autosave_interval = "1"', 'autosave_interval = "0"'),
                    config.replace('input_load_state = "nul"', 'input_load_state = "f4"'),
                    config.replace('block_sram_overwrite = "false"',
                                   'block_sram_overwrite = "true"'),
                    config.replace('input_exit_emulator = "escape"',
                                   'input_exit_emulator = "nul"'),
                    config.replace('save_file_compression = "false"',
                                   'save_file_compression = "true"')):
                self.assertFalse(smoke.validate_active_config_destinations(
                    invalid, work, captures, savefiles=savefiles, savestates=savestates,
                    periodic_save=True, autosave_interval=1))

    def test_periodic_save_transaction_observes_live_a_then_b_before_clean_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            process = mock.Mock(pid=4321, returncode=0)
            keys = mock.Mock()
            identity = {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER}
            executable, core = Path("RetroArch"), Path("core")
            content, observed, witness = Path("content"), Path("observed"), Path("witness")
            digest = hashlib.sha256(b"config").hexdigest()
            config = root / "writer" / "retroarch.cfg"
            captures = root / "writer" / "captures"
            events = []
            route_options = {}
            reset_a = {"successful_video_sequence": 2, "sampled_mask": 64,
                       "observation_epoch": 2, "reset_trigger_video_sequence": 1,
                       "reset_action": "RetroArch Command > Reset"}
            reset_b = {"successful_video_sequence": 2, "sampled_mask": 128,
                       "observation_epoch": 3, "reset_trigger_video_sequence": 1,
                       "reset_action": "RetroArch Command > Reset"}
            seed = {"status": "persisted", "bytes": 65536, "sha256": "a" * 64,
                    "sram_outcome": "A", "frontend_pid": 1111}
            initial_snapshot = {"name": "public-save.srm", "size": 65536,
                                "mtime_ns": 100, "sha256": "a" * 64,
                                "sram_outcome": "A"}
            seed_identity = {"status": "frontend-seed-verified", "sha256": "a" * 64,
                             "bytes": 65536, "sram_outcome": "A",
                             "seed_frontend_pid": 1111, "savefile_name": "public-save.srm"}
            seed_reader = {"status": "consumed-before-write", "pid": 1001,
                           "guest_readback": "A"}
            startup = {"status": "seed-loaded-before-write-input",
                       "first_video_sequence": 1, "first_input_mask": 0,
                       "observation_epoch": 1}
            update = {"status": "updated-before-exit", "before_sha256": "a" * 64,
                      "after_sha256": "b" * 64, "before_mtime_ns": 100,
                      "after_mtime_ns": 200, "bytes": 65536,
                      "sram_outcome": "B", "owned_process_alive": True}
            clean_b = {"status": "persisted", "sha256": "b" * 64,
                       "bytes": 65536, "sram_outcome": "B"}
            reader = {"status": "consumed-before-write", "pid": 8765,
                      "guest_readback": "B"}
            owner = mock.Mock(process=process, deadline=100,
                              config_digest=digest, exit_code=0)
            owner.start.return_value = owner
            owner.quit.side_effect = lambda _timeout: events.append("clean-exit") or 0

            def work_tree(work, save_root, **options):
                route_options.update(options)
                return config, captures

            def reset(keys_arg, mask, *_args, **_kwargs):
                events.append(f"reset-{mask}")
                return reset_a if mask == 64 else reset_b

            def ready(*_args):
                events.append("startup-neutral-frame")
                return startup

            owner.ready.side_effect = ready

            def wait_update(save_root, before, owned, outcome, _deadline):
                events.append("update-b-live")
                self.assertIs(before, initial_snapshot)
                self.assertIs(owned, process)
                self.assertEqual(outcome, "B")
                return update

            def stop(owned, bundle_id, timeout):
                events.append("clean-exit")
                self.assertIs(owned, process)
                self.assertEqual(bundle_id, identity["bundle_id"])
                self.assertEqual(timeout, 45)
                return 0

            with mock.patch.object(smoke, "_continuation_identity", return_value=(
                    executable, core, content, observed, identity, digest,
                    digest, digest)), \
                 mock.patch.object(smoke, "validate_continuation_operation_matrix",
                                   return_value="periodic-save"), \
                 mock.patch.object(smoke, "_run_sram_seed_frontend",
                                   return_value=seed) as make_seed, \
                 mock.patch.object(smoke, "validate_periodic_seed_file",
                                   return_value=seed_identity) as check_seed, \
                 mock.patch.object(smoke, "_run_fresh_sram_reader",
                                   side_effect=[seed_reader, reader]) as readers, \
                 mock.patch.object(smoke, "frontend_sram_snapshot",
                                   side_effect=[initial_snapshot] * 4), \
                 mock.patch.object(smoke, "_continuation_work_tree", side_effect=work_tree), \
                 mock.patch.object(smoke, "read_private_regular_file", return_value=b"config"), \
                 mock.patch.object(smoke, "OwnedContinuationFrontend",
                                   return_value=owner) as owner_type, \
                 mock.patch.object(smoke, "_start_continuation_frontend",
                                   return_value=(process, 100, digest)), \
                 mock.patch.object(smoke, "sha256", return_value=digest), \
                 mock.patch.object(smoke, "HeldMVSKeys") as keys_type, \
                 mock.patch.object(smoke, "reset_guest_under_mask", side_effect=reset), \
                 mock.patch.object(smoke, "wait_for_periodic_save_update",
                                   side_effect=wait_update), \
                 mock.patch.object(smoke, "running_retroarch_pids", return_value={process.pid}), \
                 mock.patch.object(smoke, "frontend_exited", return_value=False), \
                 mock.patch.object(smoke, "_clean_exit_sram", return_value=clean_b):
                keys_type.return_value.__enter__.return_value = keys
                result = smoke._run_periodic_save_transaction(
                    mock.Mock(timeout=45, witness=witness), root, {})

            self.assertEqual(route_options, {
                "state_route": False, "periodic_save": True,
                "autosave_interval": 1,
            })
            make_seed.assert_called_once()
            owner_type.assert_called_once()
            owner.start.assert_called_once_with()
            owner.ready.assert_called_once()
            owner.quit.assert_called_once_with(45)
            owner.cleanup.assert_called_once_with()
            check_seed.assert_called_once_with(seed, initial_snapshot)
            self.assertEqual(readers.call_args_list[0].kwargs["expected"], "A")
            self.assertEqual(readers.call_args_list[1].kwargs["expected"], "B")
            self.assertEqual(events, ["startup-neutral-frame", "reset-64",
                                      "reset-128", "update-b-live", "clean-exit"])
            self.assertEqual(result["seed"], seed)
            self.assertEqual(result["seed_identity"], seed_identity)
            self.assertEqual(result["seed_reader"], seed_reader)
            self.assertEqual(result["startup"], startup)
            self.assertEqual(result["periodic_update"], update)
            self.assertEqual(result["writer"]["guest_branches"], ["A", "B"])
            self.assertEqual(result["writer"]["initial_reset_epoch"], 2)
            self.assertEqual(result["writer"]["reset_epoch"], 3)
            self.assertEqual(result["fresh_reader"], reader)

    def test_sram_seed_requires_live_a_witness_then_uses_policy_exit_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            savefiles = root / "savefiles"
            savefiles.mkdir()
            work = root / "sram-seed-seed"
            writer = work / "writer"
            config = writer / "retroarch.cfg"
            process = mock.Mock(pid=4321, returncode=0)
            owner = mock.Mock(process=process, deadline=100,
                              config_digest=hashlib.sha256(b"config").hexdigest(),
                              exit_code=0)
            owner.start.return_value = owner
            identity = {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER}
            keys = mock.Mock()
            digest = hashlib.sha256(b"config").hexdigest()
            options = {}
            events = []
            menu_calls = []
            owner.quit.side_effect = lambda _timeout: events.append("quit") or 0
            startup = {"first_video_sequence": 1, "observation_epoch": 1}
            owner.ready.side_effect = lambda _invocation: events.append("startup") or startup
            state = {"sram_outcome": "A", "container_sha256": "a" * 64}
            persisted = {"status": "persisted", "bytes": 65536,
                         "sha256": "b" * 64, "sram_outcome": "A"}

            def work_tree(work_dir, save_root, **kwargs):
                options.update(kwargs)
                self.assertEqual(save_root, savefiles)
                return config, work_dir / "captures"

            def reset(*_args, **_kwargs):
                events.append("reset")
                return {"successful_video_sequence": 2,
                        "sampled_mask": 64, "observation_epoch": 2,
                        "reset_trigger_video_sequence": 1,
                        "reset_action": "RetroArch Command > Reset"}

            def save(*_args, **_kwargs):
                events.append("save")
                return [state]

            with mock.patch.object(smoke, "_continuation_work_tree", side_effect=work_tree), \
                 mock.patch.object(smoke, "OwnedContinuationFrontend",
                                   return_value=owner) as owner_type, \
                 mock.patch.object(smoke, "_start_continuation_frontend",
                                   return_value=(process, 100, digest)), \
                 mock.patch.object(smoke, "HeldMVSKeys") as keys_type, \
                 mock.patch.object(smoke, "reset_guest_under_mask",
                                   side_effect=reset) as reset_guest, \
                 mock.patch.object(smoke, "_save_state_file", side_effect=save) as save_state, \
                 mock.patch.object(smoke, "press_owned_menu_key",
                                   side_effect=lambda _keys, code: menu_calls.append(code)), \
                 mock.patch.object(smoke.time, "sleep"), \
                 mock.patch.object(smoke, "sha256", return_value=digest), \
                 mock.patch.object(smoke, "_clean_exit_sram", return_value=persisted):
                keys_type.return_value.__enter__.return_value = keys
                result = smoke._run_sram_seed_frontend(
                    mock.Mock(timeout=45), base=root, run_id="seed",
                    executable=Path("RetroArch"), core=Path("core"),
                    content=Path("content"), observed_core=Path("observed"),
                    identity=identity, observed_digest="c" * 64,
                    witness=Path("witness"), witness_digest="d" * 64,
                    content_digest="e" * 64, savefiles=savefiles)

            self.assertEqual(options, {
                "state_route": True, "periodic_save": False,
                "autosave_interval": 0,
            })
            owner.ready.assert_called_once()
            self.assertEqual(reset_guest.call_args.args[:4],
                             (keys, 64, writer / "retroarch.log", process))
            self.assertEqual(reset_guest.call_args.args[4],
                             owner.ready.call_args.args[0])
            self.assertEqual(reset_guest.call_args.args[5], 100)
            self.assertEqual(reset_guest.call_args.kwargs,
                             {"via_native_menu": True})
            self.assertEqual(events, ["startup", "reset", "save", "quit"])
            save_state.assert_called_once_with(
                keys, writer / "retroarch.log", writer / "savestates", 1,
                mock.ANY, process, 100, via_native_menu=True)
            self.assertEqual(menu_calls, [])
            owner_type.assert_called_once()
            owner.start.assert_called_once_with()
            owner.quit.assert_called_once_with(45)
            owner.cleanup.assert_called_once_with()
            self.assertEqual(result["pre_exit_sram_outcome"], "A")
            self.assertEqual(result["pre_exit_state_sha256"], "a" * 64)
            self.assertEqual(result["reset_trigger_video_sequence"], 1)
            self.assertEqual(result["reset_action"], "RetroArch Command > Reset")
            self.assertEqual(result["sha256"], persisted["sha256"])

            owner.ready.side_effect = None
            owner.ready.return_value = {"first_video_sequence": 1,
                                        "observation_epoch": 1}
            with mock.patch.object(smoke, "_continuation_work_tree", side_effect=work_tree), \
                 mock.patch.object(smoke, "_start_continuation_frontend",
                                   return_value=(process, 100, digest)), \
                 mock.patch.object(smoke, "HeldMVSKeys") as keys_type, \
                 mock.patch.object(smoke, "reset_guest_under_mask",
                                   return_value={"successful_video_sequence": 2,
                                                 "sampled_mask": 64,
                                                 "observation_epoch": 2,
                                                 "reset_trigger_video_sequence": 1,
                                                 "reset_action": "RetroArch Command > Reset"}), \
                 mock.patch.object(smoke, "_save_state_file",
                                   return_value=[{**state, "sram_outcome": "B"}]), \
                 mock.patch.object(smoke, "sha256", return_value=digest), \
                 mock.patch.object(smoke, "_stop_continuation_frontend") as rejected_exit, \
                 mock.patch.object(smoke, "frontend_returncode", return_value=0):
                keys_type.return_value.__enter__.return_value = keys
                with self.assertRaises(smoke.SmokeBlocked):
                    smoke._run_sram_seed_frontend(
                        mock.Mock(timeout=45), base=root, run_id="wrong-seed",
                        executable=Path("RetroArch"), core=Path("core"),
                        content=Path("content"), observed_core=Path("observed"),
                        identity=identity, observed_digest="c" * 64,
                        witness=Path("witness"), witness_digest="d" * 64,
                        content_digest="e" * 64, savefiles=savefiles)
                rejected_exit.assert_not_called()

    def test_continuation_exit_uses_configured_escape_command(self):
        process = mock.Mock(pid=4321)
        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "HeldMVSKeys") as keys_type, \
             mock.patch.object(smoke, "press_owned_key") as press, \
             mock.patch.object(smoke.time, "sleep") as sleep, \
             mock.patch.object(smoke, "reap_frontend", return_value=0), \
             mock.patch.object(smoke, "frontend_returncode", return_value=0), \
             mock.patch.object(smoke, "running_retroarch_pids", return_value=set()), \
             mock.patch.object(smoke, "request_frontend_quit") as app_quit:
            keys_type.return_value.__enter__.return_value = "owned-keys"
            result = smoke._stop_continuation_frontend(
                process, smoke.EXPECTED_BUNDLE_IDENTIFIER, 5)
        self.assertEqual(result, 0)
        press.assert_called_once_with(
            "owned-keys", smoke.QUIT_KEY_CODE, smoke.KEY_HOLD_SECONDS)
        sleep.assert_called_once_with(smoke.KEY_GAP_SECONDS)
        app_quit.assert_not_called()

    def test_read_only_continuation_quit_uses_the_owned_application_identity(self):
        process = mock.Mock(pid=4321)
        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "request_frontend_quit", return_value=True) as app_quit, \
             mock.patch.object(smoke, "frontend_returncode", return_value=0), \
             mock.patch.object(smoke, "running_retroarch_pids", return_value=set()):
            result = smoke._quit_continuation_application(
                process, smoke.EXPECTED_BUNDLE_IDENTIFIER, 5)
        self.assertEqual(result, 0)
        app_quit.assert_called_once_with(
            smoke.EXPECTED_BUNDLE_IDENTIFIER, process, 5)

    def test_menu_key_pulses_leave_a_release_interval(self):
        keys = object()
        with mock.patch.object(smoke, "press_owned_key") as press, \
             mock.patch.object(smoke.time, "sleep") as sleep:
            smoke.press_owned_menu_key(keys, smoke.MENU_DOWN_KEY_CODE)
        press.assert_called_once_with(
            keys, smoke.MENU_DOWN_KEY_CODE, smoke.KEY_HOLD_SECONDS)
        sleep.assert_called_once_with(smoke.KEY_GAP_SECONDS)

    def test_quick_menu_undo_action_uses_the_pinned_direct_state_row_order(self):
        keys = object()
        with mock.patch.object(smoke, "press_owned_menu_key") as press, \
             mock.patch.object(smoke.time, "sleep") as sleep:
            smoke.activate_owned_menu_item(keys, smoke.UNDO_LOAD_MENU_DOWN_PRESSES)
        press.assert_has_calls([
            mock.call(keys, smoke.MENU_TOGGLE_KEY_CODE),
            *[mock.call(keys, smoke.MENU_DOWN_KEY_CODE)
              for _ in range(smoke.UNDO_LOAD_MENU_DOWN_PRESSES)],
            mock.call(keys, smoke.MENU_CONFIRM_KEY_CODE),
        ])
        self.assertEqual(press.call_count, smoke.UNDO_LOAD_MENU_DOWN_PRESSES + 2)
        sleep.assert_called_once_with(smoke.FOCUS_SETTLE_SECONDS)

    def test_native_save_state_script_targets_the_owned_pid_and_pinned_menu_item(self):
        script = smoke.native_save_state_menu_script(1234)
        self.assertIn("unix id is 1234", script)
        self.assertIn('menu bar item "Command" of menu bar 1', script)
        self.assertIn('menu item "Save State" of menu 1 of menu item "Save State Options"', script)
        self.assertIn("set dismissWindow to window 1", script)
        self.assertIn("set dismissPosition to position of dismissWindow", script)
        self.assertIn("set dismissSize to size of dismissWindow", script)
        self.assertIn("click at {dismissX, dismissY}", script)
        self.assertLess(script.index("set dismissPosition to position of dismissWindow"),
                        script.index('click menu bar item "Command"'))
        self.assertGreater(script.index("click at {dismissX, dismissY}"),
                           script.index('menu item "Save State"'))
        self.assertTrue(script.endswith("end tell"))
        load_script = smoke.native_state_menu_script(1234, "Load State")
        self.assertIn('menu item "Load State" of menu 1 of menu item "Save State Options"',
                      load_script)
        self.assertIn("click at {dismissX, dismissY}", load_script)
        reset_script = smoke.native_reset_menu_script(1234)
        self.assertIn('click commandMenuBarItem', reset_script)
        self.assertIn('click menu item "Reset" of menu 1 of menu bar item "Command"',
                      reset_script)
        self.assertLess(reset_script.index("set dismissPosition to position of dismissWindow"),
                        reset_script.index("click commandMenuBarItem"))
        self.assertIn('"MENU_WINDOW_GEOMETRY="', reset_script)
        self.assertIn('"RESET_MENU_CONFIRMED"', reset_script)
        self.assertNotIn("click at {dismissX, dismissY}", reset_script)
        self.assertGreater(reset_script.index("MENU_WINDOW_GEOMETRY="),
                           reset_script.index('menu item "Reset"'))
        self.assertTrue(reset_script.endswith("end tell"))
        for invalid_pid in (0, -1, True, "1234"):
            with self.subTest(pid=invalid_pid), self.assertRaises(smoke.SmokeBlocked):
                smoke.native_save_state_menu_script(invalid_pid)
            with self.subTest(reset_pid=invalid_pid), self.assertRaises(smoke.SmokeBlocked):
                smoke.native_reset_menu_script(invalid_pid)
        for invalid_action in ("Undo Load State", "", None, []):
            with self.subTest(action=invalid_action), self.assertRaises(smoke.SmokeBlocked):
                smoke.native_state_menu_script(1234, invalid_action)

    def test_native_reset_samples_owned_process_while_menu_action_is_pending(self):
        process = mock.Mock(pid=1234)
        action = mock.Mock(returncode=0)
        mouse_probe = {
            "event_locations_global": [[486.0, 620.0], [486.0, 620.0]],
            "pointer_readback": {"status": "read", "quartz_global": [486.0, 620.0]},
            "owned_frontmost_after_click": True,
        }
        action.communicate.side_effect = [
            subprocess.TimeoutExpired(["osascript"], 0.75),
            (b"MENU_WINDOW_GEOMETRY=86,20,800,1200\nRESET_MENU_CONFIRMED\n", b""),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "retroarch.log"
            with mock.patch.object(smoke, "frontend_exited", return_value=False), \
                 mock.patch.object(smoke, "frontmost_pid", return_value=1234), \
                 mock.patch.object(smoke, "focus_owned_frontend") as focus, \
                 mock.patch.object(smoke.subprocess, "Popen", return_value=action) as popen, \
             mock.patch.object(smoke, "post_owned_mouse_click") as dismiss, \
                 mock.patch.object(smoke, "take_owned_process_sample",
                                   return_value={"status": "sampled", "bytes": 100,
                                                 "sha256": "a" * 64}) as sample, \
                 mock.patch.object(smoke.time, "monotonic", side_effect=[1.0, 1.75]):
                dismiss.return_value = mouse_probe
                result = smoke.invoke_native_reset_menu(process, log=log)
        self.assertEqual(result["activation"], "accessible menu-item click returned")
        self.assertEqual(result["dismissal"], "frontmost-owned global HID click posted")
        self.assertEqual(result["pending_sample"]["status"], "sampled")
        self.assertEqual(result["mouse_event_probe"], mouse_probe)
        focus.assert_called_once_with(process)
        dismiss.assert_called_once_with(1234, 486, 620)
        sample.assert_called_once_with(process, log.parent)
        self.assertEqual(popen.call_args.args[0][:2], ["/usr/bin/osascript", "-e"])
        action.communicate.assert_has_calls([
            mock.call(timeout=smoke.RESET_PENDING_SAMPLE_DELAY_SECONDS),
            mock.call(timeout=smoke.NATIVE_MENU_ACTION_TIMEOUT_SECONDS -
                      smoke.RESET_PENDING_SAMPLE_DELAY_SECONDS),
        ])

    def test_native_reset_failure_keeps_a_path_redacted_apple_event_summary(self):
        process = mock.Mock(pid=1234)
        with tempfile.TemporaryDirectory() as temporary:
            private_dir = Path(temporary) / "private-output"
            private_dir.mkdir()
            log = private_dir / "retroarch.log"
            action = mock.Mock(returncode=1)
            action.communicate.return_value = (
                b"", f"System Events: missing menu {private_dir}/Command".encode())
            with mock.patch.object(smoke, "frontend_exited", return_value=False), \
                 mock.patch.object(smoke, "frontmost_pid", return_value=1234), \
                 mock.patch.object(smoke.subprocess, "Popen", return_value=action):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.invoke_native_reset_menu(process, log=log)
        summary = raised.exception.diagnostic["stderr_summary"]
        self.assertIn("System Events: missing menu", summary)
        self.assertNotIn(temporary, summary)

    def test_pending_native_reset_takes_one_bounded_owned_process_sample(self):
        process = mock.Mock(pid=1234)
        log = Path("/private/tmp/writer/retroarch.log")
        sampled_bytes = b"Process: RetroArch [1234]\nThread 0: runloop sample\n"

        def sample_process(command, **kwargs):
            Path(command[-1]).write_bytes(sampled_bytes)
            return subprocess.CompletedProcess(command, 0, b"", b"")

        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "retroarch.log"
            with mock.patch.object(smoke, "frontend_exited", return_value=False), \
                 mock.patch.object(smoke, "read_frontend_log", return_value=b"running"), \
                 mock.patch.object(smoke, "mvs_observation_epoch_count", return_value=1), \
                 mock.patch.object(smoke.time, "monotonic",
                                   side_effect=[0.0, 0.0, 0.1, 0.8]), \
                 mock.patch.object(smoke.time, "sleep"), \
                 mock.patch.object(smoke.subprocess, "run", side_effect=sample_process) as run:
                result = smoke.sample_owned_process_if_reset_pending(
                    log, 1, process, 5.0)
        self.assertEqual(result["status"], "sampled")
        self.assertEqual(result["bytes"], len(sampled_bytes))
        self.assertEqual(result["sha256"], hashlib.sha256(sampled_bytes).hexdigest())
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][:4],
                         ["/usr/bin/sample", "1234",
                          str(smoke.RESET_PENDING_SAMPLE_SECONDS), "10"])
        self.assertEqual(run.call_args.kwargs["timeout"],
                         smoke.RESET_PENDING_SAMPLE_TIMEOUT_SECONDS)

    def test_fresh_reader_state_capture_can_use_the_frontend_menu_action(self):
        keys, process = object(), object()
        saved_state = [{"name": "public-save.state", "mem_sha256": "b" * 64}]
        with mock.patch.object(smoke, "invoke_native_save_state_menu") as save_menu, \
             mock.patch.object(smoke, "press_owned_key") as hotkey, \
             mock.patch.object(smoke, "_wait_continuation_event_count",
                               return_value=[("S", (224113, 1, 2)),
                                             ("R", (224113, 1, 2)),
                                             ("F", (0, 0, 1, 1)),
                                             ("S", (224113, 10, 20))]), \
             mock.patch.object(smoke, "public_state_file_identity_snapshot",
                               return_value={}) as snapshot, \
             mock.patch.object(smoke, "wait_for_changed_public_state_files",
                               return_value=(saved_state, ["public-save.state"])) as changed:
            result = smoke._save_state_file(
                keys, Path("retroarch.log"), Path("savestates"), 1, 0,
                process, 10, via_native_menu=True, event_count=2)
        self.assertEqual(result, saved_state)
        save_menu.assert_called_once_with(process)
        hotkey.assert_not_called()
        self.assertTrue(saved_state[0]["save_file_changed"])
        snapshot.assert_called_once_with(Path("savestates"))
        self.assertEqual(changed.call_args.args[:4],
                         (Path("savestates"), 1, 0, {}))

    def test_periodic_save_requires_matching_pre_exit_file_mutation(self):
        validate = smoke.validate_periodic_save_update
        before = {"name": "public-save.srm", "size": 65536,
                  "mtime_ns": 100, "sha256": "a" * 64, "sram_outcome": "A"}
        after = {"name": "public-save.srm", "size": 65536,
                 "mtime_ns": 200, "sha256": "b" * 64, "sram_outcome": "B"}
        result = validate(before, after, owned_process_alive=True)
        self.assertEqual(result["status"], "updated-before-exit")
        controls = (
            (before, after, False),  # exit-only change
            (before, None, True),    # missing save file
            (before, {**after, "sram_outcome": "A"}, True),  # wrong guest branch
            (before, {**after, "sha256": before["sha256"]}, True),  # no byte change
            (before, {**after, "name": "other.srm"}, True),  # different save identity
            (before, {**after, "mtime_ns": before["mtime_ns"]}, True),
        )
        for original, current, alive in controls:
            with self.subTest(current=current, alive=alive), self.assertRaises(smoke.SmokeBlocked):
                validate(original, current, owned_process_alive=alive)


class RetroArchSRAMPersistenceTests(unittest.TestCase):
    def test_missing_exit_writeback_is_reported_without_claiming_persistence(self):
        with tempfile.TemporaryDirectory() as temporary:
            savefiles = Path(temporary) / "savefiles"
            savefiles.mkdir(mode=0o700)
            self.assertEqual(smoke._clean_exit_sram(savefiles),
                             {"status": "not_written", "entry_count": 0})

    def test_frontend_memory_api_requires_size_and_data_queries(self):
        log = (b"[libretro INFO] glueyneo: frontend queried MVS SAVE_RAM size: 65536 bytes\n"
               b"[libretro INFO] glueyneo: frontend queried MVS SAVE_RAM data\n")
        self.assertEqual(smoke.parse_frontend_save_ram_queries(log), {
            "data_query_count": 1, "size_query_count": 1, "size_bytes": 65536})
        with self.assertRaises(smoke.SmokeBlocked):
            smoke.parse_frontend_save_ram_queries(
                b"glueyneo: frontend queried MVS SAVE_RAM data\n")

    def test_periodic_seed_identity_requires_actual_a_writeback_and_same_file(self):
        validate = smoke.validate_periodic_seed_file
        seed = {"status": "persisted", "bytes": 65536,
                "sha256": "a" * 64, "sram_outcome": "A", "frontend_pid": 1234}
        snapshot = {"name": "public-save.srm", "size": 65536,
                    "mtime_ns": 100, "sha256": "a" * 64, "sram_outcome": "A"}
        result = validate(seed, snapshot)
        self.assertEqual(result["status"], "frontend-seed-verified")
        self.assertEqual(result["seed_frontend_pid"], 1234)
        controls = (
            (None, snapshot),
            ({**seed, "status": "not_written"}, snapshot),
            ({**seed, "sram_outcome": "B"}, snapshot),
            (seed, {**snapshot, "sram_outcome": "B"}),
            (seed, {**snapshot, "sha256": "c" * 64}),
            (seed, {**snapshot, "size": 1}),
        )
        for source, current in controls:
            with self.subTest(source=source, current=current), self.assertRaises(smoke.SmokeBlocked):
                validate(source, current)

    def test_periodic_startup_neutral_frame_precedes_guest_write_input(self):
        validate = smoke.validate_initial_neutral_guest_frame
        records = [{"event_kind": "B", "sampled_mask": 0,
                    "successful_video_sequence": 0},
                   {"event_kind": "S", "sampled_mask": 0,
                    "successful_video_sequence": 0},
                   {"event_kind": "V", "sampled_mask": 0,
                    "successful_video_sequence": 1},
                   {"event_kind": "S", "sampled_mask": 0,
                    "successful_video_sequence": 1},
                   {"event_kind": "V", "sampled_mask": 0,
                    "successful_video_sequence": 2}]
        startup = validate(records)
        self.assertEqual(startup["first_video_sequence"], 1)
        self.assertEqual(startup["neutral_video_sequences"], [1, 2])
        self.assertEqual(startup["neutral_completed_frames"], 2)
        with self.assertRaises(smoke.SmokeBlocked):
            validate(records[:3])
        with self.assertRaises(smoke.SmokeBlocked):
            validate([{**records[2], "sampled_mask": 64}])
        with self.assertRaises(smoke.SmokeBlocked):
            validate([{**record, "sampled_mask": 64} if index == 1 else record
                      for index, record in enumerate(records)])
        with self.assertRaises(smoke.SmokeBlocked):
            validate([])

    def test_shared_startup_wait_drains_two_distinct_neutral_video_polls(self):
        first_poll = [
            {"event_kind": "B", "sampled_mask": 0,
             "successful_video_sequence": 0},
            {"event_kind": "S", "sampled_mask": 0,
             "successful_video_sequence": 0},
            {"event_kind": "V", "sampled_mask": 0,
             "successful_video_sequence": 1},
        ]
        second_poll = first_poll + [
            {"event_kind": "S", "sampled_mask": 0,
             "successful_video_sequence": 1},
            {"event_kind": "V", "sampled_mask": 0,
             "successful_video_sequence": 2},
        ]
        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "read_frontend_log", return_value=b"trace"), \
             mock.patch.object(smoke, "parse_latest_mvs_input_epoch",
                               side_effect=[first_poll, second_poll]) as parse, \
             mock.patch.object(smoke, "mvs_observation_epoch_count", return_value=1), \
             mock.patch.object(smoke.time, "monotonic",
                               side_effect=[0.0, 0.0, 0.1]), \
             mock.patch.object(smoke.time, "sleep"):
            startup = smoke.wait_for_initial_neutral_guest_frame(
                Path("retroarch.log"), object(), "invocation", 1.0)
        self.assertEqual(parse.call_count, 2)
        self.assertEqual(startup["neutral_video_sequences"], [1, 2])
        self.assertEqual(startup["observation_epoch"], 1)


class ActiveSceneObservationTests(unittest.TestCase):
    def test_complete_sampled_video_chain_has_strict_host_binding(self):
        parser = getattr(smoke, "parse_mvs_input_observations", None)
        self.assertTrue(callable(parser), "active-scene input observations require a strict parser")
        records = parser("glueyneo: mvs B 0 0 0 0\n"
                         "glueyneo: mvs S 1 32 0 0\n"
                         "glueyneo: mvs V 1 32 1 202752\n",
                         invocation_id="fresh")
        self.assertEqual(records[-1]["sampled_mask"], 32)
        self.assertEqual(records[-1]["successful_video_sequence"], 1)
        self.assertEqual(records[-1]["invocation_id"], "fresh")

    CHAIN = ("glueyneo: mvs B 0 0 0 0\n"
             "glueyneo: mvs S 1 0 0 0\n"
             "glueyneo: mvs V 32 0 32 6488064\n"
             "glueyneo: mvs S 40 32 39 7907328\n"
             "glueyneo: mvs V 40 32 40 8110080\n")

    def parse(self, text=None, **kwargs):
        return smoke.parse_mvs_input_observations(self.CHAIN if text is None else text,
                                                  invocation_id="fresh", **kwargs)

    def test_rejects_malformed_stale_reordered_exhausted_or_incomplete_protocol(self):
        mutations = [self.CHAIN.replace("B 0 0 0 0\n", "B 0 0 0 0\nglueyneo: mvs B 0 0 0 0\n"),
                     self.CHAIN.split("\n", 1)[1],
                     self.CHAIN[:-1],
                     self.CHAIN.replace("S 40 32", "S 30 32"),
                     self.CHAIN.replace("V 40 32", "V 40 16"),
                     self.CHAIN.replace("V 40 32 40", "V 40 32 31"),
                     self.CHAIN.replace("S 40 32", "S True 32"),
                     self.CHAIN.replace("V 40 32", "V 40 1024"),
                     self.CHAIN + "glueyneo: mvs X 41 32 41 8312832\n",
                     self.CHAIN + smoke.MVS_FRONTEND_FAILURE_MARKERS[0] + "\n",
                     "glueyneo: mvs B 0 0 0 0\n" + "glueyneo: mvs V 1 32 1 1\n"]
        for text in mutations:
            with self.subTest(text=text[-60:]), self.assertRaises(smoke.SmokeBlocked):
                self.parse(text)
        with self.assertRaises(smoke.SmokeBlocked):
            self.parse(expected_invocation_id="stale")
        with self.assertRaises(smoke.SmokeBlocked):
            self.parse("glueyneo: mvs B 0 0 0 0\n" + "glueyneo: mvs S 1 0 0 0\n" * 256)

    def test_capture_binds_interval_and_rejects_wrong_reverse_release_or_stale(self):
        before = self.parse()
        after = self.parse(self.CHAIN + "glueyneo: mvs V 44 32 44 8921088\n")
        binding = smoke.bind_active_scene_capture(before, after, invocation_id="fresh",
                                                   expected_mask=32, capture_sha256="a" * 64)
        self.assertEqual(binding["successful_video_interval"], [40, 44])
        self.assertEqual(binding["exact_frame"], "unknown")
        bad = [before, self.parse(self.CHAIN + "glueyneo: mvs S 41 0 40 8110080\n"
                                 "glueyneo: mvs V 44 0 44 8921088\n"),
               self.parse(self.CHAIN + "glueyneo: mvs S 41 16 40 8110080\n"
                          "glueyneo: mvs V 44 16 44 8921088\n")]
        for records in bad:
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.bind_active_scene_capture(before, records, invocation_id="fresh",
                                                 expected_mask=32, capture_sha256="a" * 64)
        for kwargs in ({"invocation_id": "stale", "expected_mask": 32},
                       {"invocation_id": "fresh", "expected_mask": 16},
                       {"invocation_id": "fresh", "expected_mask": True}):
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.bind_active_scene_capture(before, after, capture_sha256="a" * 64, **kwargs)
        corrupted = [dict(record) for record in after]
        corrupted[-1]["successful_video_sequence"] = -1
        with self.assertRaises(smoke.SmokeBlocked):
            smoke.bind_active_scene_capture(before, corrupted, invocation_id="fresh",
                                             expected_mask=32, capture_sha256="a" * 64)

    def test_incremental_collector_drains_failure_after_ready_and_rejects_early_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "fresh.log"
            collector = smoke.MVSObservationCollector(object(), log, "fresh")
            log.write_text(self.CHAIN.rsplit("glueyneo:", 1)[0])
            with mock.patch.object(smoke, "frontend_exited", return_value=False):
                self.assertEqual(len(collector.drain()), 4)
                with log.open("a") as stream:
                    stream.write("glueyneo:" + self.CHAIN.rsplit("glueyneo:", 1)[1])
                self.assertEqual(collector.wait_for_video(40, 32, 0)[-1]["successful_video_sequence"], 40)
                with log.open("a") as stream:
                    stream.write("noise\n" * 20000 + smoke.MVS_FRONTEND_FAILURE_MARKERS[1] + "\n")
                with self.assertRaisesRegex(smoke.SmokeBlocked, "runtime failed"):
                    collector.wait_for_video(40, 32, 0)
            with mock.patch.object(smoke, "frontend_exited", return_value=True):
                with self.assertRaisesRegex(smoke.SmokeBlocked, "exited"):
                    collector.drain()
            with self.assertRaisesRegex(smoke.SmokeBlocked, "fresh"):
                smoke.MVSObservationCollector(object(), log, "fresh")

    def test_held_masks_only_post_transitions_and_always_release(self):
        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "frontmost_pid", return_value=4321), \
             mock.patch.object(smoke, "preflight_keyboard_posting"), \
             mock.patch.object(smoke, "focus_owned_frontend") as focus, \
             mock.patch.object(smoke, "post_key_transition") as post:
            with self.assertRaisesRegex(RuntimeError, "capture failure"):
                with smoke.HeldMVSKeys(mock.Mock(pid=4321)) as keys:
                    keys.set_mask(32)
                    keys.set_mask(32 | 64)
                    keys.set_mask(32 | 64)
                    keys.set_mask(16)
                    raise RuntimeError("capture failure")
            self.assertEqual(post.call_args_list, [mock.call(124, True,pid=4321), mock.call(6, True,pid=4321),
                                                  mock.call(6, False,pid=4321), mock.call(124, False,pid=4321),
                                                  mock.call(123, True,pid=4321), mock.call(123, False,pid=4321)])
            focus.assert_not_called()

    def test_owned_press_recovers_focus_and_reasserts_held_keys(self):
        process = mock.Mock(pid=4321)
        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "frontmost_pid", return_value=999, create=True), \
             mock.patch.object(smoke, "focus_owned_frontend") as focus, \
             mock.patch.object(smoke, "post_key_transition") as post:
            keys = smoke.HeldMVSKeys(process)
            keys.held = {124, 12}
            keys.observation_burst = True
            keys.set_mask(32 | 64)
            focus.assert_called_once_with(process)
            self.assertEqual(post.call_args_list, [mock.call(12,False,pid=4321),
                mock.call(12,True,pid=4321), mock.call(124,False,pid=4321),
                mock.call(124,True,pid=4321), mock.call(6,True,pid=4321)])

    def test_appkit_pointer_readback_converts_to_quartz_global_coordinates(self):
        result = subprocess.CompletedProcess(
            args=["osascript"], returncode=0,
            stdout="", stderr="GLUEYNEO_MOUSE_LOCATION=36.5,375.5,982\n")
        with mock.patch.object(smoke.subprocess, "run", return_value=result) as run:
            location = smoke.current_global_mouse_location()
        self.assertEqual(location, {
            "status": "read",
            "appkit_lower_left": [36.5, 375.5],
            "main_display_height": 982.0,
            "quartz_global": [36.5, 606.5],
        })
        self.assertEqual(run.call_args.args[0][:3],
                         ["/usr/bin/osascript", "-l", "JavaScript"])
        self.assertEqual(run.call_args.kwargs["timeout"],
                         smoke.POINTER_READBACK_TIMEOUT_SECONDS)

    def test_appkit_pointer_readback_preserves_unavailable_status(self):
        result = subprocess.CompletedProcess(
            args=["osascript"], returncode=0, stdout="", stderr="connection denied")
        with mock.patch.object(smoke.subprocess, "run", return_value=result):
            location = smoke.current_global_mouse_location()
        self.assertEqual(location["status"], "unavailable")
        self.assertEqual(location["return_code"], 0)
        self.assertEqual(len(location["stderr_sha256"]), 64)

    def test_owned_event_uses_pid_delivery_and_releases_native_event(self):
        services = mock.Mock()
        services.CGEventCreateKeyboardEvent.return_value = 123
        with mock.patch.object(smoke,"_keyboard_services",return_value=services):
            smoke.post_key_transition(124,True,pid=4321)
        services.CGEventPostToPid.assert_called_once_with(4321,123)
        services.CGEventPost.assert_not_called()
        services.CFRelease.assert_called_once_with(123)

    def test_owned_mouse_click_posts_globally_only_while_owned_process_is_frontmost(self):
        self.assertTrue(callable(getattr(smoke, "post_owned_mouse_click", None)),
                        "owned window dismissal needs a frontmost-guarded click helper")
        services = mock.Mock()
        services.CGEventCreateMouseEvent.side_effect = [101, 102]
        services.CGEventGetLocation.return_value = smoke._CGPoint(486.0, 620.0)
        pointer = {"status": "read", "quartz_global": [486.0, 620.0]}
        with mock.patch.object(smoke, "_mouse_services", return_value=services), \
             mock.patch.object(smoke, "frontmost_pid", return_value=4321) as frontmost, \
             mock.patch.object(smoke, "current_global_mouse_location", return_value=pointer):
            result = smoke.post_owned_mouse_click(4321, 486, 620)

        calls = services.CGEventCreateMouseEvent.call_args_list
        self.assertEqual([call.args[1] for call in calls],
                         [smoke.CG_LEFT_MOUSE_DOWN, smoke.CG_LEFT_MOUSE_UP])
        for call in calls:
            self.assertEqual(call.args[0], None)
            self.assertEqual(call.args[2].x, 486)
            self.assertEqual(call.args[2].y, 620)
            self.assertEqual(call.args[3], smoke.CG_LEFT_MOUSE_BUTTON)
        self.assertEqual(services.CGEventPost.call_args_list,
                         [mock.call(smoke.CG_HID_EVENT_TAP, 101),
                          mock.call(smoke.CG_HID_EVENT_TAP, 102)])
        services.CGEventPostToPid.assert_not_called()
        services.CGEventGetLocation.assert_has_calls([mock.call(101), mock.call(102)])
        frontmost.assert_has_calls([mock.call(), mock.call()])
        self.assertEqual(result, {
            "event_locations_global": [[486.0, 620.0], [486.0, 620.0]],
            "pointer_readback": pointer,
            "owned_frontmost_after_click": True,
            "pointer_matches_requested_global": True,
        })
        self.assertEqual(services.CFRelease.call_args_list,
                         [mock.call(101), mock.call(102)])
        with mock.patch.object(smoke, "_mouse_services") as unused_services, \
             mock.patch.object(smoke, "frontmost_pid", return_value=999):
            with self.assertRaisesRegex(smoke.SmokeBlocked, "not frontmost"):
                smoke.post_owned_mouse_click(4321, 486, 620)
        unused_services.assert_not_called()

    def test_owned_mouse_click_rejects_focus_loss_after_posting(self):
        services = mock.Mock()
        services.CGEventCreateMouseEvent.side_effect = [101, 102]
        services.CGEventGetLocation.return_value = smoke._CGPoint(486.0, 620.0)
        with mock.patch.object(smoke, "_mouse_services", return_value=services), \
             mock.patch.object(smoke, "frontmost_pid", side_effect=[4321, 9876]), \
             mock.patch.object(smoke, "current_global_mouse_location",
                               return_value={"status": "read", "quartz_global": [486.0, 620.0]}):
            with self.assertRaisesRegex(smoke.SmokeBlocked, "lost foreground"):
                smoke.post_owned_mouse_click(4321, 486, 620)

    def test_owned_mouse_click_requires_matching_system_pointer_readback(self):
        for pointer in (
                {"status": "unavailable"},
                {"status": "read", "quartz_global": [700.0, 220.0]}):
            services = mock.Mock()
            services.CGEventCreateMouseEvent.side_effect = [101, 102]
            services.CGEventGetLocation.return_value = smoke._CGPoint(486.0, 620.0)
            with self.subTest(pointer=pointer), \
                 mock.patch.object(smoke, "_mouse_services", return_value=services), \
                 mock.patch.object(smoke, "frontmost_pid", return_value=4321), \
                 mock.patch.object(smoke, "current_global_mouse_location",
                                   return_value=pointer):
                with self.assertRaisesRegex(smoke.SmokeBlocked, "pointer did not confirm"):
                    smoke.post_owned_mouse_click(4321, 486, 620)

    def test_window_relative_point_maps_through_moved_window_geometry(self):
        map_point = getattr(smoke, "window_relative_point_to_global", None)
        self.assertTrue(callable(map_point),
                        "window-relative clicks need an explicit global coordinate conversion")
        self.assertEqual(
            map_point((400, 120), (300, 100), (800, 600)),
            (700, 220),
        )
        self.assertEqual(
            map_point((400, 120), (500, 250), (800, 600)),
            (900, 370),
        )
        for invalid in (
                ((800, 120), (300, 100), (800, 600)),
                ((400, 120), (300, 100), (0, 600)),
                ((True, 120), (300, 100), (800, 600)),
                ([400, 120], (300, 100), (800, 600))):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                map_point(*invalid)

    def test_owned_readback_error_is_not_treated_as_focus_loss(self):
        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "frontmost_pid", side_effect=smoke.SmokeBlocked("input","readback unavailable")), \
             mock.patch.object(smoke, "focus_owned_frontend") as focus, \
             mock.patch.object(smoke, "post_key_transition") as post:
            with self.assertRaisesRegex(smoke.SmokeBlocked,"readback unavailable"):
                smoke.HeldMVSKeys(mock.Mock(pid=4321)).post_key(124,True)
            focus.assert_not_called()
            post.assert_not_called()

    def test_owned_focus_rejects_unsuccessful_acquisition(self):
        now = [0.0]

        def clock():
            return now[0]

        def sleep(duration):
            now[0] += duration

        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "frontmost_pid", return_value=999), \
             mock.patch.object(smoke.subprocess, "run"), \
             mock.patch.object(smoke, "OWNED_FOCUS_READBACK_TIMEOUT_SECONDS", 0.02), \
             mock.patch.object(smoke.time, "monotonic", side_effect=clock), \
             mock.patch.object(smoke.time, "sleep", side_effect=sleep):
            with self.assertRaisesRegex(smoke.SmokeBlocked,"did not acquire"):
                smoke.focus_owned_frontend(mock.Mock(pid=4321))

    def test_owned_focus_uses_pid_scoped_appkit_activation_after_readback_timeout(self):
        process = mock.Mock(pid=4321)
        now = [0.0]

        def clock():
            return now[0]

        def sleep(duration):
            now[0] += duration

        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "frontmost_pid", return_value=999) as readback, \
             mock.patch.object(smoke.subprocess, "run"), \
             mock.patch.object(smoke, "_activate_owned_pid_with_appkit", create=True) as activate, \
             mock.patch.object(smoke, "OWNED_FOCUS_READBACK_TIMEOUT_SECONDS", 0.02), \
             mock.patch.object(smoke.time, "monotonic", side_effect=clock), \
             mock.patch.object(smoke.time, "sleep", side_effect=sleep):
            def activate_owned(pid):
                readback.return_value = pid
                return True

            activate.side_effect = activate_owned
            blocked = None
            try:
                smoke.focus_owned_frontend(process)
            except smoke.SmokeBlocked as error:
                blocked = error
        self.assertIsNone(blocked, "owned AppKit activation should recover a missed System Events focus")
        activate.assert_called_once_with(4321)

    def test_owned_focus_waits_for_delayed_foreground_readback(self):
        process = mock.Mock(pid=4321)
        now = [0.0]

        def clock():
            return now[0]

        def sleep(duration):
            now[0] += duration

        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "frontmost_pid", side_effect=(999, 999, 4321)) as readback, \
             mock.patch.object(smoke.subprocess, "run"), \
             mock.patch.object(smoke.time, "monotonic", side_effect=clock), \
             mock.patch.object(smoke.time, "sleep", side_effect=sleep) as wait:
            try:
                smoke.focus_owned_frontend(process)
            except smoke.SmokeBlocked:
                acquired = False
            else:
                acquired = True
        self.assertTrue(acquired, "transient foreground readback should settle on the owned process")
        self.assertEqual(readback.call_count, 3)
        self.assertEqual(wait.call_count, 2)

    def test_owned_focus_is_deferred_until_first_guest_input(self):
        process = mock.Mock(pid=4321)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(smoke, "frontend_exited", return_value=False))
            stack.enter_context(mock.patch.object(smoke, "frontmost_pid", return_value=999))
            stack.enter_context(mock.patch.object(smoke, "preflight_keyboard_posting"))
            focus = stack.enter_context(mock.patch.object(smoke, "focus_owned_frontend"))
            stack.enter_context(mock.patch.object(smoke, "post_key_transition"))
            with smoke.HeldMVSKeys(process) as keys:
                focus.assert_not_called()
                keys.set_mask(32)
            focus.assert_called_once_with(process)

    def test_owned_input_never_addresses_an_exited_child(self):
        with mock.patch.object(smoke, "frontend_exited", return_value=True), \
             mock.patch.object(smoke, "post_key_transition") as post:
            keys = smoke.HeldMVSKeys(mock.Mock(pid=4321))
            keys.post_key(124,False)
            with self.assertRaisesRegex(smoke.SmokeBlocked,"exited"):
                keys.post_key(124,True)
            post.assert_not_called()

    def test_fresh_config_disables_extraction_and_isolates_playlist_migration(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            config = smoke.write_frontend_config(work,work).read_text()
            self.assertIn('bundle_assets_extract_enable = "false"',config)
            for key in ("playlist_directory", "content_history_directory", "content_favorites_directory",
                        "content_image_history_directory", "content_music_history_directory", "content_video_directory"):
                self.assertIn(f'{key} = "{work}"',config)

    def test_fresh_config_uses_null_audio_sink_without_disabling_core_audio_callbacks(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            config = smoke.write_frontend_config(work, work, null_audio=True).read_text()
        self.assertIn('audio_driver = "null"', config)
        self.assertNotIn('audio_enable = "false"', config)

    def test_public_state_config_satisfies_isolated_frontend_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work, captures = root / "work", root / "captures"
            savefiles, savestates = root / "savefiles", root / "savestates"
            for directory in (work, captures, savefiles, savestates):
                directory.mkdir()
            config = smoke.write_frontend_config(
                work, captures, savefiles=savefiles, savestates=savestates,
                public_state=True, null_audio=True).read_text()
            self.assertIn('config_save_on_exit = "false"', config)
            self.assertIn('quit_press_twice = "false"', config)
            self.assertIn('input_pause_toggle = "p"', config)
            self.assertIn('input_frame_advance = "k"', config)
            self.assertIn('input_exit_emulator = "escape"', config)
            self.assertIn('save_file_compression = "false"', config)
            for setting in (
                    'quick_menu_show_resume_content = "false"',
                    'quick_menu_show_restart_content = "false"',
                    'quick_menu_show_close_content = "false"',
                    'quick_menu_show_savestate_submenu = "false"',
                    'quick_menu_show_save_load_state = "true"',
                    'quick_menu_show_undo_save_load_state = "true"',
                    'quick_menu_show_take_screenshot = "false"'):
                self.assertIn(setting, config)
            for key in ("sort_savestates_enable", "sort_savefiles_enable",
                        "sort_savestates_by_content_enable", "sort_savefiles_by_content_enable"):
                self.assertIn(f'{key} = "false"', config)
            self.assertTrue(smoke.validate_active_config_destinations(
                config, work, captures, savefiles=savefiles, savestates=savestates,
                public_state=True))
            confirmed_reset = config.replace(
                'quit_press_twice = "false"', 'quit_press_twice = "true"')
            self.assertFalse(smoke.validate_active_config_destinations(
                confirmed_reset, work, captures, savefiles=savefiles,
                savestates=savestates, public_state=True))
            continuous = config.replace(
                'input_frame_advance = "k"', 'input_frame_advance = "nul"')
            self.assertFalse(smoke.validate_active_config_destinations(
                continuous, work, captures, savefiles=savefiles,
                savestates=savestates, public_state=True))
            for altered in (
                    config.replace('input_exit_emulator = "escape"',
                                   'input_exit_emulator = "nul"'),
                    config.replace('save_file_compression = "false"',
                                   'save_file_compression = "true"'),
                    config.replace('quick_menu_show_savestate_submenu = "false"',
                                   'quick_menu_show_savestate_submenu = "true"'),
                    config.replace('quick_menu_show_undo_save_load_state = "true"',
                                   'quick_menu_show_undo_save_load_state = "false"')):
                self.assertFalse(smoke.validate_active_config_destinations(
                    altered, work, captures, savefiles=savefiles,
                    savestates=savestates, public_state=True))

    def test_continuation_configs_enable_stdin_commands_without_network_listener(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work, captures = root / "work", root / "captures"
            savefiles, savestates = root / "savefiles", root / "savestates"
            for directory in (work, captures, savefiles, savestates):
                directory.mkdir()
            config = smoke.write_frontend_config(
                work, captures, savefiles=savefiles, savestates=savestates,
                public_state=True, stdin_commands=True, null_audio=True).read_text()
            self.assertIn('stdin_cmd_enable = "true"', config)
            self.assertIn('network_cmd_enable = "false"', config)
            self.assertTrue(smoke.validate_active_config_destinations(
                config, work, captures, savefiles=savefiles, savestates=savestates,
                public_state=True, stdin_commands=True))
            self.assertFalse(smoke.validate_active_config_destinations(
                config.replace('network_cmd_enable = "false"',
                               'network_cmd_enable = "true"'),
                work, captures, savefiles=savefiles, savestates=savestates,
                public_state=True, stdin_commands=True))
            self.assertFalse(smoke.validate_active_config_destinations(
                config.replace('stdin_cmd_enable = "true"',
                               'stdin_cmd_enable = "false"'),
                work, captures, savefiles=savefiles, savestates=savestates,
                public_state=True, stdin_commands=True))

    def test_frontend_stdin_command_sends_one_whitelisted_line_and_flushes(self):
        stream = io.BytesIO()
        process = mock.Mock(returncode=None, stdin=stream)
        process.poll.return_value = None
        result = smoke.send_frontend_stdin_command(process, "RESET")
        self.assertEqual(stream.getvalue(), b"RESET\n")
        self.assertEqual(result, {"command": "RESET", "bytes_written": 6})

    def test_frontend_stdin_command_rejects_batching_and_closed_process(self):
        process = mock.Mock(returncode=None, stdin=io.BytesIO())
        process.poll.return_value = None
        for invalid in ("RESET\nSAVE_STATE", "QUIT;RESET", "GET_STATUS path"):
            with self.subTest(command=invalid), self.assertRaises(smoke.SmokeBlocked):
                smoke.send_frontend_stdin_command(process, invalid)
        process.returncode = 0
        with self.assertRaises(smoke.SmokeBlocked):
            smoke.send_frontend_stdin_command(process, "QUIT")

    def test_owned_frontend_guest_commands_wait_for_shared_startup_readiness(self):
        process = mock.Mock(returncode=None, stdin=io.BytesIO(), pid=4321)
        process.poll.return_value = None
        process._glueyneo_require_guest_ready = True
        process._glueyneo_guest_ready = False
        process._glueyneo_cleanup_command_allowed = False
        process._glueyneo_command_trace = []
        owner = object.__new__(smoke.OwnedContinuationFrontend)
        owner.process = process
        owner.startup = None
        owner.log = Path("private.log")
        owner.deadline = 10.0
        startup = {"observation_epoch": 1}
        with self.assertRaisesRegex(smoke.SmokeBlocked, "startup readiness"):
            smoke.send_frontend_stdin_command(process, "RESET")
        with mock.patch.object(smoke, "wait_for_initial_neutral_guest_frame",
                               return_value=startup) as wait_startup:
            self.assertEqual(owner.ready("invocation"), startup)
            self.assertEqual(owner.ready("invocation"), startup)
        wait_startup.assert_called_once_with(
            owner.log, process, "invocation", owner.deadline)
        self.assertTrue(process._glueyneo_guest_ready)
        smoke.send_frontend_stdin_command(process, "RESET")
        self.assertEqual(process.stdin.getvalue(), b"RESET\n")

    def test_owned_frontend_can_send_bounded_quit_when_startup_readiness_fails(self):
        process = mock.Mock(returncode=None, stdin=io.BytesIO(), pid=4322)
        process.poll.return_value = None
        process._glueyneo_require_guest_ready = True
        process._glueyneo_guest_ready = False
        process._glueyneo_cleanup_command_allowed = False
        process._glueyneo_command_trace = []
        owner = object.__new__(smoke.OwnedContinuationFrontend)
        owner.process = process
        owner.identity = {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER}
        owner.args = mock.Mock(timeout=45)
        owner.exit_code = None
        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "reap_frontend", return_value=0), \
             mock.patch.object(smoke, "running_retroarch_pids", return_value=[]), \
             mock.patch.object(owner, "close_stdin"):
            owner.cleanup(preserve=False)
        self.assertEqual(process.stdin.getvalue(), b"QUIT\n")
        self.assertEqual(owner.exit_code, 0)
        self.assertFalse(process._glueyneo_cleanup_command_allowed)

    def test_owned_keyboard_input_is_blocked_before_startup_readiness(self):
        process = mock.Mock(pid=4323)
        process._glueyneo_require_guest_ready = True
        process._glueyneo_guest_ready = False
        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "preflight_keyboard_posting") as preflight:
            with self.assertRaisesRegex(smoke.SmokeBlocked, "startup readiness"):
                smoke.HeldMVSKeys(process).__enter__()
        preflight.assert_not_called()

    def test_neutral_guest_audio_wait_requires_distinct_appended_records(self):
        process = mock.Mock(returncode=None)
        process.poll.return_value = None
        frames = [
            b"[libretro INFO] glueyneo: MVS audio frame: 21 128 202750 811 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n",
            b"[libretro INFO] glueyneo: MVS audio frame: 22 0 202750 811 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n",
            b"[libretro INFO] glueyneo: MVS audio frame: 23 0 202750 811 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n",
            b"[libretro INFO] glueyneo: MVS audio frame: 24 0 202750 811 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n",
        ]
        baseline = b"prior log\n"
        with mock.patch.object(smoke, "read_frontend_log",
                               side_effect=[baseline] +
                               [baseline + b"".join(frames[:index])
                                for index in (1, 2, 3, 4)]), \
             mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke.time, "sleep"):
            result = smoke.wait_for_neutral_mvs_guest_frames(
                Path("private.log"), process, len(baseline), 3,
                time.monotonic() + 1)
        self.assertEqual(result, [
            {"frame": 22, "sampled_mask": 0},
            {"frame": 23, "sampled_mask": 0},
            {"frame": 24, "sampled_mask": 0},
        ])

    def test_undo_resume_release_waits_neutral_frames_without_retoggling_menu(self):
        process = mock.Mock()
        frames = [{"frame": sequence, "sampled_mask": 0}
                  for sequence in (4, 6, 8)]
        deadline = time.monotonic() + 1
        baseline_size = 10
        with mock.patch.object(smoke, "wait_for_neutral_mvs_guest_frames",
                               return_value=frames) as wait_neutral:
            result = smoke.wait_for_owned_quick_menu_release(
                process, Path("private.log"), baseline_size, deadline)
        self.assertEqual(result["closure"],
                         "Undo Load State -> CMD_EVENT_RESUME -> retroarch_menu_running_finished(false)")
        self.assertEqual(result["input_release_frames"], frames)
        wait_neutral.assert_called_once_with(
            Path("private.log"), process, baseline_size, 3, deadline)

    def test_stdin_reply_failure_retains_bounded_exit_and_protocol_evidence(self):
        output = b'startup\n[Command] Command "GET_STATUS" failed.\n'
        with mock.patch.object(smoke, "frontend_exited", side_effect=[False, True]), \
             mock.patch.object(smoke, "frontend_returncode", return_value=1), \
             mock.patch.object(smoke, "read_frontend_log", return_value=output), \
             mock.patch.object(smoke.time, "sleep"):
            with self.assertRaises(smoke.SmokeBlocked) as captured:
                smoke.wait_for_frontend_stdin_reply(
                    Path("private-process.log"), command="GET_STATUS",
                    previous_size=len(b"startup\n"), process=object(),
                    deadline=time.monotonic() + 1)
        self.assertEqual(captured.exception.stage, "input")
        self.assertEqual(captured.exception.diagnostic["exit_code"], 1)
        self.assertEqual(captured.exception.diagnostic["protocol_lines"],
                         ['[Command] Command "GET_STATUS" failed.'])
        self.assertEqual(captured.exception.diagnostic["stdout_bytes_after_request"],
                         len(b'[Command] Command "GET_STATUS" failed.\n'))

    def test_stdin_status_query_accepts_pinned_contentless_reply_without_newline(self):
        output = b"prefix\nGET_STATUS CONTENTLESS"
        with mock.patch.object(smoke, "frontend_exited", return_value=False), \
             mock.patch.object(smoke, "read_frontend_log", return_value=output):
            result = smoke.wait_for_frontend_stdin_reply(
                Path("private-process.log"), command="GET_STATUS",
                previous_size=len(b"prefix\n"), process=object(),
                deadline=time.monotonic() + 1)
        self.assertEqual(result, "GET_STATUS CONTENTLESS")

    def test_focused_reset_state_requires_a_sram_but_allows_no_prior_save_read(self):
        validate = getattr(smoke, "validate_focused_reset_state", None)
        self.assertTrue(callable(validate),
                        "focused control must distinguish startup readback from selected SRAM write")
        result = validate({"sram_outcome": "A", "guest_readback": None,
                          "container_sha256": "a" * 64})
        self.assertEqual(result["sram_outcome"], "A")
        self.assertIsNone(result["guest_readback"])
        with self.assertRaises(smoke.SmokeBlocked):
            validate({"sram_outcome": "B", "guest_readback": None,
                      "container_sha256": "b" * 64})

    def test_fresh_config_has_explicit_classic_full_mask_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            config = smoke.write_frontend_config(work, work).read_text()
        for key, value in {"select": "num1", "start": "num2", "up": "up", "down": "down",
                           "left": "left", "right": "right", "b": "z", "a": "x", "y": "a", "x": "s"}.items():
            self.assertIn(f'input_player1_{key} = "{value}"', config)

    def test_original_callback_trace_parses_when_executable_is_supplied(self):
        # CTest may supply the synthetic callback producer; no private media.
        executable = os.environ.get("GLUEYNEO_MVS_OBSERVATION_TEST")
        if executable is None:
            self.skipTest("original callback trace exercised by local integration command")
        trace = subprocess.run([executable, "--input-observations"], check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        records = self.parse(trace.stdout)
        masks = [record["sampled_mask"] for record in records if record["event_kind"] == "S"]
        self.assertEqual(masks, [35, 3, 19, 99, 67, 3])
        self.assertTrue(any(record["event_kind"] == "V" for record in records))

    def test_collector_rejects_truncation_replacement_and_typed_record_bypasses(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "fresh.log"
            collector = smoke.MVSObservationCollector(object(), log, "fresh")
            with mock.patch.object(smoke, "frontend_exited", return_value=False):
                log.write_text(self.CHAIN)
                collector.drain()
                log.write_text(self.CHAIN[:20])
                with self.assertRaises(smoke.SmokeBlocked):
                    collector.drain()
        before = self.parse()
        after = self.parse(self.CHAIN + "glueyneo: mvs V 44 32 44 8921088\n")
        for value in (True, "44", -1):
            corrupt = [dict(record) for record in after]
            corrupt[-1]["sample_sequence"] = value
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.bind_active_scene_capture(before, corrupt, invocation_id="fresh",
                                                 expected_mask=32, capture_sha256="a" * 64)

    def test_diagnostic_l3_remains_held_across_masks_and_releases_on_failure(self):
        with mock.patch.object(smoke,"frontend_exited",return_value=False), \
             mock.patch.object(smoke,"frontmost_pid",return_value=4321), \
             mock.patch.object(smoke,"preflight_keyboard_posting"), \
             mock.patch.object(smoke,"focus_owned_frontend"), \
             mock.patch.object(smoke,"post_key_transition") as post:
            with self.assertRaisesRegex(RuntimeError,"failure"):
                with smoke.HeldMVSKeys(mock.Mock(pid=4321)) as keys:
                    keys.set_observation_burst(True)
                    keys.set_mask(32)
                    keys.set_mask(16)
                    self.assertNotIn(mock.call(12,False,pid=4321),post.call_args_list)
                    raise RuntimeError("failure")
        self.assertEqual(post.call_args_list.count(mock.call(12,True,pid=4321)),1)
        self.assertEqual(post.call_args_list.count(mock.call(12,False,pid=4321)),1)

    def test_active_only_config_uses_direct_live_stderr(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            normal = smoke.write_frontend_config(work,work).read_text()
            active = smoke.write_frontend_config(work,work,direct_log=True).read_text()
        self.assertIn('log_to_file = "true"',normal)
        self.assertIn('log_to_file = "false"',active)
        self.assertIn('input_player1_l3 = "q"',active)

    def test_key_release_runs_even_when_wait_is_interrupted(self):
        with mock.patch.object(smoke, "post_key_transition") as post, \
             mock.patch.object(smoke.time, "sleep", side_effect=RuntimeError("interrupted")):
            with self.assertRaises(RuntimeError):
                smoke.post_held_key(124, 0.1)
        self.assertEqual(post.call_args_list, [mock.call(124, True), mock.call(124, False)])

    def test_active_capture_binds_after_file_completion_and_never_refocuses(self):
        before = self.parse()
        after = self.parse(self.CHAIN + "glueyneo: mvs V 44 32 44 8921088\n")
        collector = mock.Mock(invocation_id="fresh", records=before)
        collector.drain.return_value = before
        collector.wait_for_video.return_value = after
        with tempfile.TemporaryDirectory() as temporary:
            capture = Path(temporary) / "fresh.png"
            capture.write_bytes(active_png_fixture(b"synthetic"))
            with mock.patch.object(smoke, "screenshot_snapshot", return_value={}), \
                 mock.patch.object(smoke, "select_active_scene_png", side_effect=lambda *args: smoke.snapshot_active_scene_png(capture, {})), \
                 mock.patch.object(smoke, "decode_png", return_value=(320,224,3,b"")) as decode, \
                 mock.patch.object(smoke, "read_png_capture_geometry", return_value=(320,224)), \
                 mock.patch.object(smoke, "post_key_transition") as post, \
                 mock.patch.object(smoke, "focus_frontend") as focus:
                path, binding = smoke.request_active_scene_screenshot(collector, Path(temporary), 32)
            self.assertNotEqual(path, capture)
            self.assertEqual(path.read_bytes(), active_png_fixture(b"synthetic"))
        self.assertEqual(binding["successful_video_interval"], [40,44])
        focus.assert_not_called()
        decode.assert_not_called()
        self.assertEqual(post.call_args_list, [mock.call(100, True), mock.call(100, False)])

    def test_repeated_active_captures_are_immutable_and_release_crosses_a_poll(self):
        test = self
        transitions = []
        class Collector:
            invocation_id = "fresh"
            def __init__(self):
                self.text = test.CHAIN
                self.records = test.parse(self.text)
                self.sequence = 40
            def drain(self):
                return list(self.records)
            def wait_for_video(self, target, mask, timeout):
                self.sequence = max(self.sequence + 1, target)
                self.text += f"glueyneo: mvs V {self.sequence} 32 {self.sequence} {self.sequence * 202752}\n"
                self.records = test.parse(self.text)
                transitions.append(("video", self.sequence))
                return list(self.records)
        collector = Collector()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            # RetroArch's filename has only second resolution and overwrites.
            producer_path = directory / "content-2026-10-21-120000.png"
            payloads = iter((active_png_fixture(b"first synthetic PNG"), active_png_fixture(b"second synthetic PNG")))
            def post(key, down):
                transitions.append(("down" if down else "up", key))
                if down:
                    producer_path.write_bytes(next(payloads))
            with mock.patch.object(smoke, "post_key_transition", side_effect=post), \
                 mock.patch.object(smoke, "select_active_scene_png", side_effect=lambda *args: smoke.snapshot_active_scene_png(producer_path, {})), \
                 mock.patch.object(smoke, "read_png_capture_geometry", return_value=(320,224)):
                first, first_binding = smoke.request_active_scene_screenshot(collector, directory, 32)
                second, second_binding = smoke.request_active_scene_screenshot(collector, directory, 32)
            self.assertNotEqual(first, second, "successive capture records must never share an overwritten file")
            self.assertEqual(first.read_bytes(), active_png_fixture(b"first synthetic PNG"))
            self.assertEqual(second.read_bytes(), active_png_fixture(b"second synthetic PNG"))
            self.assertEqual(smoke.sha256(first), first_binding["capture_sha256"])
            self.assertEqual(smoke.sha256(second), second_binding["capture_sha256"])
            first_up = transitions.index(("up",100))
            second_down = transitions.index(("down",100), 1)
            self.assertTrue(any(event[0] == "video" for event in transitions[first_up + 1:second_down]),
                            "F8 keyup must cross a successful input poll before a new keydown")

    def test_readiness_cannot_relabel_prior_video_under_a_new_sample(self):
        text = ("glueyneo: mvs B 0 0 0 0\n"
                "glueyneo: mvs S 1 0 0 0\n"
                "glueyneo: mvs V 1 0 1 202752\n"
                "glueyneo: mvs S 2 32 1 202752\n")
        for kind in ("R", "P"):
            with self.assertRaises(smoke.SmokeBlocked, msg="readiness requires video under the current sampled mask"):
                self.parse(text + f"glueyneo: mvs {kind} 2 32 1 202752\n")

    def test_active_screenshot_retries_dropped_hotkey_only_after_release_polls(self):
        test = self
        clock = [0.0]
        actions = []
        class Collector:
            invocation_id = "fresh"
            def __init__(self):
                self.text = test.CHAIN
                self.records = test.parse(self.text)
                self.sequence = 40
            def drain(self):
                return list(self.records)
            def wait_for_video(self, target, mask, timeout):
                self.sequence = max(self.sequence + 1, target)
                self.text += f"glueyneo: mvs V {self.sequence} 32 {self.sequence} {self.sequence * 202752}\n"
                self.records = test.parse(self.text)
                actions.append("video")
                clock[0] += 0.01
                return list(self.records)
        collector = Collector()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            producer = directory / "same-second.png"
            presses = [0]
            def post(key, down):
                actions.append("down" if down else "up")
                if down:
                    presses[0] += 1
                    if presses[0] == 2:
                        producer.write_bytes(active_png_fixture(b"fresh second attempt"))
            def sleep(seconds):
                clock[0] += seconds
                collector.wait_for_video(collector.sequence + 1,32,1)
            with mock.patch.object(smoke, "post_key_transition", side_effect=post), \
                 mock.patch.object(smoke, "select_active_scene_png", side_effect=lambda *args: smoke.snapshot_active_scene_png(producer,{}) if producer.exists() else None), \
                 mock.patch.object(smoke, "read_png_capture_geometry", return_value=(320,224)), \
                 mock.patch.object(smoke.time, "monotonic", side_effect=lambda: clock[0]), \
                 mock.patch.object(smoke.time, "sleep", side_effect=sleep):
                try:
                    stored, _ = smoke.request_active_scene_screenshot(collector,directory,32,timeout=1)
                    succeeded = stored.read_bytes() == active_png_fixture(b"fresh second attempt")
                except smoke.SmokeBlocked:
                    succeeded = False
            self.assertTrue(succeeded, "dropped F8 must retry within the bounded capture invocation")
            self.assertEqual(presses[0],2)
            up = actions.index("up")
            down = actions.index("down",1)
            self.assertGreaterEqual(actions[up+1:down].count("video"),2)

    def test_collector_rejects_unrequested_mask_changes_before_wait_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "fresh.log"
            collector = smoke.MVSObservationCollector(object(), log, "fresh")
            expect = getattr(collector, "expect_mask", None)
            self.assertTrue(callable(expect), "collector must reject input outside the requested full mask")
            with mock.patch.object(smoke, "frontend_exited", return_value=False):
                expect(0)
                log.write_text("glueyneo: mvs B 0 0 0 0\n"
                               "glueyneo: mvs S 1 0 0 0\n"
                               "glueyneo: mvs V 1 0 1 202752\n")
                collector.drain()
                expect(32)
                with log.open("a") as stream:
                    stream.write("glueyneo: mvs S 2 16 1 202752\n"
                                 "glueyneo: mvs V 2 16 2 405504\n")
                with self.assertRaisesRegex(smoke.SmokeBlocked, "unexpected sampled input"):
                    collector.wait_for_video(2,32,0)

    def test_capture_upper_bound_precedes_post_completion_keyup_callbacks(self):
        test = self
        actions = []
        class Collector:
            invocation_id = "fresh"
            def __init__(self):
                self.text = test.CHAIN
                self.records = test.parse(self.text)
                self.sequence = 40
            def drain(self):
                return list(self.records)
            def wait_for_video(self, target, mask, timeout):
                self.sequence = max(self.sequence + 1,target)
                self.text += f"glueyneo: mvs V {self.sequence} 32 {self.sequence} {self.sequence * 202752}\n"
                self.records = test.parse(self.text)
                actions.append(("video",self.sequence))
                return list(self.records)
        collector = Collector()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            fresh = directory / "fresh.png"
            fresh.write_bytes(active_png_fixture(b"complete stable PNG"))
            with mock.patch.object(smoke,"screenshot_snapshot",return_value={}), \
                 mock.patch.object(smoke,"select_active_scene_png",side_effect=lambda *args: smoke.snapshot_active_scene_png(fresh, {})), \
                 mock.patch.object(smoke,"read_png_capture_geometry",return_value=(320,224)), \
                 mock.patch.object(smoke,"post_key_transition",side_effect=lambda key,down:actions.append(("down" if down else "up",key))):
                stored,binding=smoke.request_active_scene_screenshot(collector,directory,32)
                self.assertEqual(stored.read_bytes(),active_png_fixture(b"complete stable PNG"))
        upper=binding["successful_video_interval"][1]
        self.assertLess(upper,collector.sequence,
                        "post-completion keyup callbacks belong to cleanup, not the capture interval")
        up=actions.index(("up",100))
        self.assertEqual([seq for kind,seq in actions[up+1:] if kind=="video"], [upper+1,upper+2])
        self.assertEqual(binding["exact_frame"],"unknown")

    def test_png_first_seen_after_release_keeps_wider_interval(self):
        test=self
        held=[False]
        class Collector:
            invocation_id="fresh"
            def __init__(self):
                self.text=test.CHAIN
                self.records=test.parse(self.text)
                self.sequence=40
            def drain(self):
                if held[0]:
                    self.wait_for_video(self.sequence+1,32,1)
                return list(self.records)
            def wait_for_video(self,target,mask,timeout):
                self.sequence=max(self.sequence+1,target)
                self.text+=f"glueyneo: mvs V {self.sequence} 32 {self.sequence} {self.sequence*202752}\n"
                self.records=test.parse(self.text)
                return list(self.records)
        collector=Collector()
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            fresh=directory/"late.png"
            fresh.write_bytes(active_png_fixture(b"late complete PNG"))
            with mock.patch.object(smoke,"screenshot_snapshot",return_value={}), \
                 mock.patch.object(smoke,"select_active_scene_png",side_effect=lambda *args: None if held[0] else smoke.snapshot_active_scene_png(fresh,{})), \
                 mock.patch.object(smoke,"read_png_capture_geometry",return_value=(320,224)), \
                 mock.patch.object(smoke,"post_key_transition",side_effect=lambda key,down:held.__setitem__(0,down)):
                _,binding=smoke.request_active_scene_screenshot(collector,directory,32)
        self.assertEqual(binding["successful_video_interval"][0],40)
        self.assertGreater(binding["successful_video_interval"][1],48)
        self.assertEqual(binding["successful_video_interval"][1],collector.sequence)
        self.assertEqual(binding["exact_frame"],"unknown")

    def test_bounded_png_header_checks_crc_and_wrong_geometry(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"header.png"
            import struct
            body=struct.pack(">IIBBBBB",320,224,8,2,0,0,0)
            chunk=b"IHDR"+body
            header=b"\x89PNG\r\n\x1a\n"+struct.pack(">I",13)+chunk+struct.pack(">I",zlib.crc32(chunk)&0xffffffff)
            path.write_bytes(header)
            self.assertEqual(smoke.read_png_capture_geometry(path),(320,224))
            path.write_bytes(header[:-1]+bytes([header[-1]^1]))
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.read_png_capture_geometry(path)
            path.write_bytes(header[:12])
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.read_png_capture_geometry(path)
            path.write_bytes(header)
            path.write_bytes(active_png_fixture(width=321))
            self.assertIsNone(smoke.snapshot_active_scene_png(path,{}))

    def test_active_completion_requires_full_png_validation_after_clean_quit(self):
        order=[]
        process=mock.Mock(pid=4321,returncode=None)
        records=[dict(event_kind="R",sampled_mask=0,successful_video_sequence=1,sample_sequence=1),
                 dict(event_kind="P",sampled_mask=2,successful_video_sequence=700,sample_sequence=700),
                 dict(event_kind="V",sampled_mask=0,successful_video_sequence=900,sample_sequence=900)]
        collector=mock.Mock(records=records)
        collector.drain.return_value=records
        collector.wait_for_video.return_value=records
        def quit_frontend(*args):
            order.append("quit")
            process.returncode=0
            return True
        def full_decode(path):
            self.assertEqual(process.returncode,0,"full validation must follow clean owned frontend exit")
            order.append("full-decode")
            raise smoke.SmokeBlocked("video","synthetic invalid pixel stream")
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)/"captures"
            args=mock.Mock(timeout=1,capture_dir=directory,child_pid_file=None)
            def capture(*args, **kwargs):
                path=directory/"capture.png"
                path.write_bytes(b"plausible header but invalid pixel stream")
                return path,dict(capture_sha256=smoke.sha256(path),invocation_id="fresh")
            with mock.patch.object(smoke,"validate_inputs",return_value=(Path("app"),Path("core"),Path("content"),
                         {"content_kind":"selected-mvs","bundle_id":smoke.EXPECTED_BUNDLE_IDENTIFIER})), \
                 mock.patch.object(smoke,"MVSObservationCollector",return_value=collector), \
                 mock.patch.object(smoke,"HeldMVSKeys"), \
                 mock.patch.object(smoke,"preflight_keyboard_posting"), \
                 mock.patch.object(smoke,"focus_owned_frontend"), \
                 mock.patch.object(smoke,"refuse_stacked_launch"), \
                 mock.patch.object(smoke,"record_child_pid"), \
                 mock.patch.object(smoke,"request_frontend_quit",side_effect=quit_frontend), \
                 mock.patch.object(smoke,"frontend_returncode",return_value=0), \
                 mock.patch.object(smoke,"kill_launched_group"), \
                 mock.patch.object(smoke,"request_active_scene_screenshot",side_effect=capture), \
                 mock.patch.object(smoke,"decode_png",side_effect=full_decode), \
                 mock.patch.object(smoke.subprocess,"Popen",return_value=process):
                with self.assertRaisesRegex(smoke.SmokeBlocked,"invalid pixel stream"):
                    smoke.run_mvs_active_scene(args,{"events":[],"capture_frames":[1],"active_frames":2},invocation_id="fresh")
        self.assertEqual(order,["quit","full-decode"])

    def test_async_png_is_polled_while_hotkey_held_before_release_cleanup(self):
        test=self
        held=[False]
        checked=[]
        class Collector:
            invocation_id="fresh"
            def __init__(self):
                self.text=test.CHAIN
                self.records=test.parse(self.text)
                self.sequence=40
            def drain(self):
                return list(self.records)
            def wait_for_video(self,target,mask,timeout):
                self.sequence=max(self.sequence+1,target)
                self.text+=f"glueyneo: mvs V {self.sequence} 32 {self.sequence} {self.sequence*202752}\n"
                self.records=test.parse(self.text)
                return list(self.records)
        collector=Collector()
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            fresh=directory/"async.png"
            fresh.write_bytes(active_png_fixture(b"complete asynchronous PNG"))
            def select(*args):
                checked.append(held[0])
                return smoke.snapshot_active_scene_png(fresh,{}) if len(checked)>=3 else None
            def post(key,down):
                held[0]=down
            with mock.patch.object(smoke,"screenshot_snapshot",return_value={}), \
                 mock.patch.object(smoke,"select_active_scene_png",side_effect=select), \
                 mock.patch.object(smoke,"read_png_capture_geometry",return_value=(320,224)), \
                 mock.patch.object(smoke,"post_key_transition",side_effect=post):
                path,binding=smoke.request_active_scene_screenshot(collector,directory,32)
                self.assertEqual(path.read_bytes(),active_png_fixture(b"complete asynchronous PNG"))
        self.assertEqual(checked[:3],[True,True,True],
                         "asynchronous PNG needs another availability poll before keyup cleanup")
        self.assertEqual(binding["exact_frame"],"unknown")

    def test_active_launch_identity_rejects_frontend_config_rewrite(self):
        process=mock.Mock(pid=4321,returncode=None)
        records=[dict(event_kind="R",sampled_mask=0,successful_video_sequence=1,sample_sequence=1),
                 dict(event_kind="P",sampled_mask=2,successful_video_sequence=700,sample_sequence=700),
                 dict(event_kind="V",sampled_mask=0,successful_video_sequence=900,sample_sequence=900)]
        collector=mock.Mock(records=records)
        collector.drain.return_value=records
        collector.wait_for_video.return_value=records
        launch_identity={}
        def launch(command,**kwargs):
            config=Path(command[command.index("--config")+1])
            launch_identity.update(path=config,text=config.read_text())
            return process
        def quit_frontend(*args):
            process.returncode=0
            launch_identity["path"].write_text('# synthetic frontend rewritten configuration\n')
            return True
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)/"captures"
            content=Path(temporary)/"content"
            content.write_bytes(b"original synthetic media identity")
            args=mock.Mock(timeout=1,capture_dir=directory,child_pid_file=None)
            def capture(*args, **kwargs):
                path=directory/"capture.png"
                path.write_bytes(b"synthetic pixels")
                return path,dict(capture_sha256=smoke.sha256(path),invocation_id="fresh")
            with mock.patch.object(smoke,"validate_inputs",return_value=(Path("app"),Path("core"),content,
                         {"content_kind":"selected-mvs","bundle_id":smoke.EXPECTED_BUNDLE_IDENTIFIER})), \
                 mock.patch.object(smoke,"MVSObservationCollector",return_value=collector), \
                 mock.patch.object(smoke,"HeldMVSKeys"), \
                 mock.patch.object(smoke,"preflight_keyboard_posting"), \
                 mock.patch.object(smoke,"focus_owned_frontend"), \
                 mock.patch.object(smoke,"refuse_stacked_launch"), \
                 mock.patch.object(smoke,"record_child_pid"), \
                 mock.patch.object(smoke,"request_frontend_quit",side_effect=quit_frontend), \
                 mock.patch.object(smoke,"frontend_returncode",return_value=0), \
                 mock.patch.object(smoke,"kill_launched_group"), \
                 mock.patch.object(smoke,"request_active_scene_screenshot",side_effect=capture), \
                 mock.patch.object(smoke,"decode_png",return_value=(320,224,3,b"")), \
                 mock.patch.object(smoke.subprocess,"Popen",side_effect=launch):
                with self.assertRaisesRegex(smoke.SmokeBlocked,"configuration changed"):
                    smoke.run_mvs_active_scene(args,{"events":[],"capture_frames":[1],"active_frames":2},invocation_id="fresh")
        self.assertIn('config_save_on_exit = "false"',launch_identity["text"])

    def test_active_preflight_failure_retains_private_diagnostic(self):
        failure=smoke.SmokeBlocked("input","synthetic invalid selected content")
        with tempfile.TemporaryDirectory() as temporary:
            args=mock.Mock(timeout=1,capture_dir=Path(temporary)/"captures",child_pid_file=None)
            with mock.patch.object(smoke,"validate_inputs",side_effect=failure):
                with self.assertRaisesRegex(smoke.SmokeBlocked,"synthetic invalid selected content") as caught:
                    smoke.run_mvs_active_scene(args,{"events":[],"capture_frames":[1],"active_frames":2},
                                               invocation_id="fresh")
        self.assertEqual(caught.exception.diagnostic,{
            "status":"incomplete","stage":"input",
            "failure_reason":"synthetic invalid selected content","invocation_id":"fresh",
            "observations":[],"captures":[],"observed_events":[]})

    def test_active_keyboard_preflight_failure_retains_readbacks_before_focus(self):
        process=mock.Mock(pid=4321,returncode=None)
        with mock.patch.object(smoke,"frontend_exited",return_value=False), \
             mock.patch.object(smoke,"_exited_unreaped",return_value=False), \
             mock.patch.object(smoke,"frontmost_pid",return_value=1234), \
             mock.patch.object(smoke,"running_retroarch_pids",return_value={1234,4321}), \
             mock.patch.object(smoke,"_keyboard_services",side_effect=OSError("synthetic permission denial")), \
             mock.patch.object(smoke,"focus_owned_frontend") as focus:
            with self.assertRaisesRegex(smoke.SmokeBlocked,"could not inject frontend keyboard input") as caught:
                with smoke.HeldMVSKeys(process):
                    self.fail("failed preflight must not enter the owned-key context")
        diagnostic=getattr(caught.exception,"diagnostic",None)
        if not isinstance(diagnostic,dict):
            diagnostic={}
        self.assertEqual(diagnostic.get("preactivation_readbacks"),{
            "owned_pid":4321,"owned_process_exited":False,
            "foreground_pid":1234,"foreground_readback":"available",
            "retroarch_pids":[1234,4321],"retroarch_process_readback":"available",
            "foreground_is_owned":False,"owned_pid_present":True})
        focus.assert_not_called()

    def test_active_scene_focuses_after_first_video_before_waiting_for_game_ready(self):
        process=mock.Mock(pid=4321,returncode=None)
        collector=mock.Mock()
        order=[]
        calls=[0]
        first_video=[
            dict(event_kind="B"),
            dict(event_kind="S"),
            dict(event_kind="V"),
        ]
        def drain():
            order.append("drain")
            calls[0]+=1
            if calls[0] == 1:
                return first_video
            raise smoke.SmokeBlocked("observations","synthetic stop before ready event")
        collector.drain.side_effect=drain
        def focus(_process):
            order.append("focus")
        def quit_frontend(*_args):
            process.returncode=0
            return True
        with tempfile.TemporaryDirectory() as temporary:
            args=mock.Mock(timeout=1,capture_dir=Path(temporary)/"captures",child_pid_file=None)
            with mock.patch.object(smoke,"validate_inputs",return_value=(Path("app"),Path("core"),Path("content"),
                         {"content_kind":"selected-mvs","bundle_id":smoke.EXPECTED_BUNDLE_IDENTIFIER})), \
                 mock.patch.object(smoke,"MVSObservationCollector",return_value=collector), \
                 mock.patch.object(smoke,"preflight_keyboard_posting"), \
                 mock.patch.object(smoke,"frontend_exited",return_value=False), \
                 mock.patch.object(smoke,"_exited_unreaped",return_value=False), \
                 mock.patch.object(smoke,"frontmost_pid",return_value=1234), \
                 mock.patch.object(smoke,"running_retroarch_pids",return_value={1234,4321}), \
                 mock.patch.object(smoke,"refuse_stacked_launch"), \
                 mock.patch.object(smoke,"launch_window",return_value=contextlib.nullcontext()), \
                 mock.patch.object(smoke,"record_child_pid"), \
                 mock.patch.object(smoke,"request_frontend_quit",side_effect=quit_frontend), \
                 mock.patch.object(smoke,"kill_launched_group"), \
                 mock.patch.object(smoke,"retain_frontend_logs",return_value=("unknown",[],[])), \
                 mock.patch.object(smoke,"focus_owned_frontend",side_effect=focus), \
                 mock.patch.object(smoke.subprocess,"Popen",return_value=process):
                with self.assertRaisesRegex(smoke.SmokeBlocked,"synthetic stop before ready event"):
                    smoke.run_mvs_active_scene(args,{"events":[],"capture_frames":[1],"active_frames":2},
                                               invocation_id="fresh")
        self.assertEqual(order,["drain","focus","drain"],
                         "focus the owned frontend after its window renders, before waiting on guest readiness")

    def test_active_owned_focus_reads_process_identity_before_activation(self):
        process=mock.Mock(pid=4321,returncode=None)
        keys=smoke.HeldMVSKeys(process)
        order=[]
        snapshots=[]
        def foreground():
            order.append("foreground")
            return 1234
        def processes():
            order.append("processes")
            return {4321}
        def focus(_process):
            order.append("focus")
            snapshots.append(getattr(keys,"preactivation_readbacks",None))
        with mock.patch.object(smoke,"frontend_exited",return_value=False), \
             mock.patch.object(smoke,"_exited_unreaped",return_value=False), \
             mock.patch.object(smoke,"frontmost_pid",side_effect=foreground), \
             mock.patch.object(smoke,"running_retroarch_pids",side_effect=processes), \
             mock.patch.object(smoke,"focus_owned_frontend",side_effect=focus), \
             mock.patch.object(smoke,"post_key_transition"):
            keys.post_key(32,True)
        self.assertEqual(snapshots[0],{
            "owned_pid":4321,"owned_process_exited":False,
            "foreground_pid":1234,"foreground_readback":"available",
            "retroarch_pids":[4321],"retroarch_process_readback":"available",
            "foreground_is_owned":False,"owned_pid_present":True})
        self.assertEqual(order,["foreground","processes","focus"])

    def test_active_observation_failure_records_process_readbacks_before_cleanup(self):
        process=mock.Mock(pid=4321,returncode=None)
        collector=mock.Mock()
        collector.drain.side_effect=smoke.SmokeBlocked(
            "observations","synthetic unexpected sampled input mask")
        order=[]
        def frontmost():
            order.append("foreground")
            return 1234
        def process_list():
            order.append("processes")
            return {1234,4321}
        def quit_frontend(*_args):
            order.append("quit")
            process.returncode=0
            return True
        with tempfile.TemporaryDirectory() as temporary:
            args=mock.Mock(timeout=1,capture_dir=Path(temporary)/"captures",child_pid_file=None)
            with mock.patch.object(smoke,"validate_inputs",return_value=(Path("app"),Path("core"),Path("content"),
                         {"content_kind":"selected-mvs","bundle_id":smoke.EXPECTED_BUNDLE_IDENTIFIER})), \
                 mock.patch.object(smoke,"MVSObservationCollector",return_value=collector), \
                 mock.patch.object(smoke,"preflight_keyboard_posting"), \
                 mock.patch.object(smoke,"frontend_exited",return_value=False), \
                 mock.patch.object(smoke,"_exited_unreaped",return_value=False), \
                 mock.patch.object(smoke,"frontmost_pid",side_effect=frontmost), \
                 mock.patch.object(smoke,"running_retroarch_pids",side_effect=process_list), \
                 mock.patch.object(smoke,"refuse_stacked_launch"), \
                 mock.patch.object(smoke,"launch_window",return_value=contextlib.nullcontext()), \
                 mock.patch.object(smoke,"record_child_pid"), \
                 mock.patch.object(smoke,"request_frontend_quit",side_effect=quit_frontend), \
                 mock.patch.object(smoke,"frontend_returncode",return_value=0), \
                 mock.patch.object(smoke,"kill_launched_group"), \
                 mock.patch.object(smoke,"retain_frontend_logs",return_value=("unknown",[],[])), \
                 mock.patch.object(smoke,"focus_owned_frontend") as focus, \
                 mock.patch.object(smoke,"post_key_transition") as post_key, \
                 mock.patch.object(smoke.subprocess,"Popen",return_value=process):
                with self.assertRaisesRegex(smoke.SmokeBlocked,"unexpected sampled input mask") as caught:
                    smoke.run_mvs_active_scene(args,{"events":[],"capture_frames":[1],"active_frames":2},
                                               invocation_id="fresh")
        self.assertEqual(getattr(caught.exception,"diagnostic",{}).get("failure_process_readbacks"),{
            "owned_pid":4321,"owned_process_exited":False,
            "foreground_pid":1234,"foreground_readback":"available",
            "retroarch_pids":[1234,4321],"retroarch_process_readback":"available",
            "foreground_is_owned":False,"owned_pid_present":True})
        self.assertEqual(order,["foreground","processes","quit"],
                         "capture readbacks inside the owned invocation before cleanup")
        focus.assert_not_called()
        post_key.assert_not_called()

    def test_active_launch_separates_mirrored_stdout_from_observed_stderr(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = mock.Mock(timeout=1,capture_dir=Path(temporary)/"captures",child_pid_file=None)
            with mock.patch.object(smoke,"validate_inputs",return_value=(Path("app"),Path("core"),Path("content"),
                         {"content_kind":"selected-mvs","bundle_id":smoke.EXPECTED_BUNDLE_IDENTIFIER})), \
                 mock.patch.object(smoke,"preflight_keyboard_posting"), \
                 mock.patch.object(smoke,"refuse_stacked_launch"), \
                 mock.patch.object(smoke.subprocess,"Popen",side_effect=OSError("synthetic unavailable launch")) as launch:
                with self.assertRaises(smoke.SmokeBlocked):
                    smoke.run_mvs_active_scene(args,{"events":[],"capture_frames":[1],"active_frames":2},invocation_id="fresh")
            command=launch.call_args.args[0]
            for flag in ("--max-frames=8192","--no-patch","--sram-mode=noload-nosave"):
                self.assertIn(flag,command,"active invocation must bound frames and isolate persistent inputs")
            kwargs=launch.call_args.kwargs
            self.assertNotEqual(kwargs["stderr"],subprocess.STDOUT,
                                "RA macOS mirrors buffered stdout and flushed stderr; never merge observation channels")
            self.assertIsNot(kwargs["stdout"],kwargs["stderr"])

    def test_active_schedule_rejects_bad_bounds_before_any_launch(self):
        with mock.patch.object(smoke, "validate_inputs", return_value=(Path("app"), Path("core"), Path("content"),
                                  {"content_kind":"selected-mvs"})), \
             mock.patch.object(smoke.subprocess, "Popen") as launch:
            for schedule in ({"events": [], "capture_frames": [1], "active_frames": True},
                             {"events": [[-1,32]], "capture_frames": [1], "active_frames": 10},
                             {"events": [], "capture_frames": [2,1], "active_frames": 10}):
                with self.assertRaises(smoke.SmokeBlocked):
                    smoke.run_mvs_active_scene(mock.Mock(timeout=1), schedule, invocation_id="fresh")
        launch.assert_not_called()


class FrontendLogBoundTests(unittest.TestCase):
    def test_bounded_stderr_sink_preserves_exact_limit_and_rejects_one_more_byte(self):
        for size in (4096, 4097):
            with self.subTest(size=size), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "stderr.log"
                with path.open("wb") as stream, smoke.BoundedFrontendLog(stream, limit=4096) as sink:
                    process = subprocess.Popen(
                        [sys.executable, "-c", "import os,sys; os.write(2,b'x'*int(sys.argv[1]))", str(size)],
                        stdout=subprocess.DEVNULL, stderr=sink.writer, start_new_session=True)
                    sink.close_writer()
                    try:
                        self.assertEqual(process.wait(timeout=5), 0)
                    finally:
                        smoke.kill_launched_group(process)
                        sink.finish()
                    self.assertFalse(sink.thread.is_alive(), "owned stderr pump must stop")
                    if size == 4096:
                        sink.check()
                    else:
                        with self.assertRaisesRegex(smoke.SmokeBlocked, "log.*budget"):
                            sink.check()
                self.assertEqual(path.stat().st_size, 4096)

    def test_sink_cleanup_is_bounded_when_another_writer_remains_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            with (Path(temporary) / "stderr.log").open("wb") as stream:
                with smoke.BoundedFrontendLog(stream, limit=4096) as sink:
                    inherited_writer = os.dup(sink.writer)
                    try:
                        started = time.monotonic()
                        sink.finish()
                        self.assertLess(time.monotonic() - started, 2.0)
                        self.assertFalse(sink.thread.is_alive())
                        with self.assertRaisesRegex(smoke.SmokeBlocked, "pump failed"):
                            sink.check()
                    finally:
                        os.close(inherited_writer)

    def test_retention_bounds_both_files_and_never_classifies_truncated_load_as_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            captures = work / "captures"
            captures.mkdir()
            log, process_log = work / "frontend.log", work / "process.log"
            log.write_bytes(smoke.MVS_FRONTEND_LOAD_MARKER.encode() + b"\n" + b"x" * 8192)
            process_log.write_bytes(b"y" * 8192)
            with process_log.open("ab") as stream, \
                 mock.patch.object(smoke, "MVS_FRONTEND_LOG_LIMIT", 4096), \
                 mock.patch.object(Path, "read_text", side_effect=AssertionError("unbounded read_text")):
                status, retained, digests = smoke.retain_frontend_logs(log, process_log, stream, captures)
            self.assertEqual(status, "fail")
            self.assertEqual(len(retained), 2)
            self.assertEqual(len(digests), 2)
            self.assertEqual([Path(path).stat().st_size for path in retained], [4096, 4096])

    def test_output_overflow_preserves_primary_failure_and_process_readbacks(self):
        real_popen = subprocess.Popen
        def launch(_command, **kwargs):
            process = real_popen([sys.executable, "-c", "import os; os.write(2,b'e'*1048576)"], **kwargs)
            process.wait(timeout=5)  # ensure overflow precedes the primary fault
            return process
        collector = mock.Mock(records=[])
        collector.drain.side_effect = smoke.SmokeBlocked("observations", "synthetic primary observation failure")
        readbacks = {"owned_process_exited": True, "foreground_is_owned": False}
        with tempfile.TemporaryDirectory() as temporary:
            args = mock.Mock(timeout=2, capture_dir=Path(temporary) / "captures", child_pid_file=None)
            with mock.patch.object(smoke, "validate_inputs", return_value=(Path("app"), Path("core"), Path("content"),
                         {"content_kind": "selected-mvs", "bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER})), \
                 mock.patch.object(smoke, "MVS_FRONTEND_LOG_LIMIT", 4096), \
                 mock.patch.object(smoke, "MVSObservationCollector", return_value=collector), \
                 mock.patch.object(smoke, "preflight_keyboard_posting"), \
                 mock.patch.object(smoke, "refuse_stacked_launch"), \
                 mock.patch.object(smoke, "launch_window", return_value=contextlib.nullcontext()), \
                 mock.patch.object(smoke, "record_child_pid"), \
                 mock.patch.object(smoke, "HeldMVSKeys"), \
                 mock.patch.object(smoke, "request_frontend_quit", return_value=False), \
                 mock.patch.object(smoke, "_active_scene_process_readbacks", return_value=readbacks), \
                 mock.patch.object(smoke.subprocess, "Popen", side_effect=launch):
                with self.assertRaisesRegex(smoke.SmokeBlocked, "synthetic primary observation failure") as caught:
                    smoke.run_mvs_active_scene(args, {"events": [], "capture_frames": [1], "active_frames": 2},
                                               invocation_id="public-dual-fault")
            diagnostic = caught.exception.diagnostic
            self.assertEqual(diagnostic["failure_process_readbacks"], readbacks)
            self.assertEqual(diagnostic["failure_reason"], "synthetic primary observation failure")
            self.assertEqual(diagnostic["status"], "incomplete")
            self.assertIn("budget", diagnostic["secondary_output_failure"])
            self.assertLessEqual(len(diagnostic["secondary_output_failure"]), 256)

    def test_active_early_exit_noisy_both_channels_is_bounded_and_nonpassing(self):
        real_popen = subprocess.Popen
        children = []
        def launch(_command, **kwargs):
            # stdout exceeds a pipe capacity before stderr: a serial/unread pipe
            # implementation would hang; stderr then exceeds its own sink cap.
            script = "import os; os.write(1,b'o'*1048576); os.write(2,b'e'*1048576)"
            process = real_popen([sys.executable, "-c", script], **kwargs)
            children.append(process)
            return process
        with tempfile.TemporaryDirectory() as temporary:
            captures = Path(temporary) / "captures"
            args = mock.Mock(timeout=2, capture_dir=captures, child_pid_file=None)
            with mock.patch.object(smoke, "validate_inputs", return_value=(Path("app"), Path("core"), Path("content"),
                         {"content_kind": "selected-mvs", "bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER})), \
                 mock.patch.object(smoke, "MVS_FRONTEND_LOG_LIMIT", 4096), \
                 mock.patch.object(smoke, "preflight_keyboard_posting"), \
                 mock.patch.object(smoke, "refuse_stacked_launch"), \
                 mock.patch.object(smoke, "launch_window", return_value=contextlib.nullcontext()), \
                 mock.patch.object(smoke, "record_child_pid"), \
                 mock.patch.object(smoke, "HeldMVSKeys"), \
                 mock.patch.object(smoke, "request_frontend_quit", return_value=False), \
                 mock.patch.object(smoke, "_active_scene_process_readbacks", return_value={}), \
                 mock.patch.object(smoke.subprocess, "Popen", side_effect=launch):
                with self.assertRaises(smoke.SmokeBlocked) as caught:
                    smoke.run_mvs_active_scene(args, {"events": [], "capture_frames": [1], "active_frames": 2},
                                               invocation_id="public-noisy-child")
            self.assertEqual(caught.exception.diagnostic["status"], "incomplete")
            self.assertIn("log output budget", json.dumps(caught.exception.diagnostic))
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].returncode, "owned child must be reaped")
            self.assertLessEqual(sum(path.stat().st_size for path in captures.iterdir()), 2 * 4096)
            self.assertFalse(any(thread.name == "frontend-stderr-pump"
                                 for thread in threading.enumerate()), "owned pump must not leak")
            self.assertFalse((captures / "frontend-stdout-private.log").exists(),
                             "mirrored stdout is deliberately discarded")


class VideoCheckpointTests(unittest.TestCase):
    def test_waits_for_emulated_checkpoint_not_load_or_wall_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "retroarch.log"
            log.write_text(smoke.MVS_FRONTEND_LOAD_MARKER)
            def advance(_seconds):
                log.write_text(smoke.MVS_FRONTEND_LOAD_MARKER + "\n" +
                               smoke.MVS_VIDEO_CHECKPOINT_MARKER)
            with mock.patch.object(smoke, "frontend_exited", return_value=False), \
                 mock.patch.object(smoke.time, "sleep", side_effect=advance) as sleep:
                smoke.wait_for_mvs_video_checkpoint(object(), log, 1)
            self.assertEqual(sleep.call_count, 1)

    def test_missing_checkpoint_times_out_and_failure_overrides_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "retroarch.log"
            with mock.patch.object(smoke, "frontend_exited", return_value=False):
                with self.assertRaisesRegex(smoke.SmokeBlocked, "timed out"):
                    smoke.wait_for_mvs_video_checkpoint(object(), log, 0)
                log.write_text(smoke.MVS_VIDEO_CHECKPOINT_MARKER + "\n" +
                               smoke.MVS_FRONTEND_FAILURE_MARKERS[0])
                with self.assertRaisesRegex(smoke.SmokeBlocked, "runtime failed"):
                    smoke.wait_for_mvs_video_checkpoint(object(), log, 1)
            with mock.patch.object(smoke, "frontend_exited", return_value=True):
                with self.assertRaisesRegex(smoke.SmokeBlocked, "exited"):
                    smoke.wait_for_mvs_video_checkpoint(object(), log, 1)

    def test_checkpoint_beyond_old_prefix_limit_and_split_read_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "retroarch.log"
            # Split the marker across a 64-KiB boundary beyond the old 1-MiB
            # prefix. This also exceeds the bounded overlap's retained size.
            log.write_text("x" * (17 * 64 * 1024 - 7) +
                           smoke.MVS_VIDEO_CHECKPOINT_MARKER)
            with mock.patch.object(smoke, "frontend_exited", return_value=False):
                smoke.wait_for_mvs_video_checkpoint(object(), log, 1)

    def test_runtime_failure_split_across_read_boundary_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "retroarch.log"
            log.write_text("x" * (64 * 1024 - 7) +
                           smoke.MVS_FRONTEND_FAILURE_MARKERS[0] + "\n" +
                           smoke.MVS_VIDEO_CHECKPOINT_MARKER)
            with mock.patch.object(smoke, "frontend_exited", return_value=False):
                with self.assertRaisesRegex(smoke.SmokeBlocked, "runtime failed"):
                    smoke.wait_for_mvs_video_checkpoint(object(), log, 1)

    def test_checkpoint_before_later_chunk_failure_does_not_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "retroarch.log"
            log.write_text(smoke.MVS_VIDEO_CHECKPOINT_MARKER + "x" * (64 * 1024) +
                           smoke.MVS_FRONTEND_FAILURE_MARKERS[0])
            with mock.patch.object(smoke, "frontend_exited", return_value=False):
                with self.assertRaisesRegex(smoke.SmokeBlocked, "runtime failed"):
                    smoke.wait_for_mvs_video_checkpoint(object(), log, 1)


class FixtureIdentityTests(unittest.TestCase):
    EXPECTED_FIXTURE_SHA256 = "59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0"
    EXPECTED_APP_SHA256 = smoke.EXPECTED_EXECUTABLE_SHA256

    def make_fixture(self, directory: Path) -> Path:
        compiler = shutil.which("cc")
        self.assertIsNotNone(compiler, "the project C compiler is required to generate its public fixture")
        writer = directory / "fixture_writer.c"
        writer.write_text(
            '#include "public_guest.c"\n'
            'int main(int argc, char **argv) { return argc == 2 && public_guest_write(argv[1]) ? 0 : 1; }\n',
            encoding="utf-8",
        )
        executable = directory / "fixture_writer"
        root = Path(__file__).resolve().parents[2]
        subprocess.run(
            [compiler, "-std=c17", "-I", str(root / "tests/fixture"), str(writer), "-o", str(executable)],
            cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        fixture = directory / "public-playable.bin"
        subprocess.run([str(executable), str(fixture)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return fixture

    def make_inputs(self, directory: Path, fixture: Path) -> tuple[object, Path]:
        bundle = directory / "RetroArch.app"
        executable = bundle / "Contents" / "MacOS" / "RetroArch"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"mock pinned app bytes")
        (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleShortVersionString": smoke.EXPECTED_VERSION,
            "CFBundleExecutable": "RetroArch",
            "CFBundleIdentifier": "com.libretro.dist.RetroArch",
        }))
        core = directory / "glueyneo_libretro.dylib"
        core.write_bytes(b"core")
        args = type("Args", (), {"retroarch": bundle, "core": core, "content": fixture, "timeout": 20.0})()
        return args, executable

    def validate(self, args: object, executable: Path) -> dict[str, str]:
        actual_sha = smoke.sha256
        with (
            mock.patch.object(smoke.sys, "platform", "darwin"),
            mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                self.EXPECTED_APP_SHA256 if Path(path).resolve() == executable.resolve() else actual_sha(Path(path))
            )),
        ):
            return smoke.validate_inputs(args)[3]

    def test_generated_public_fixture_is_accepted_as_the_pinned_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            fixture = self.make_fixture(directory)
            args, executable = self.make_inputs(directory, fixture)

            identity = self.validate(args, executable)

        self.assertEqual(identity["fixture_sha256"], self.EXPECTED_FIXTURE_SHA256)

    def test_wrong_digest_fixture_is_rejected_before_frontend_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            fixture = self.make_fixture(directory)
            content = bytearray(fixture.read_bytes())
            self.assertEqual(len(content), 602)
            self.assertEqual(content[:8], b"GNFX\0\0\0\1")
            content[-1] ^= 1
            fixture.write_bytes(content)
            args, executable = self.make_inputs(directory, fixture)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    self.EXPECTED_APP_SHA256 if Path(path).resolve() == executable.resolve() else actual_sha(Path(path))
                )),
                mock.patch.object(smoke.subprocess, "Popen", side_effect=OSError("launch attempted")) as popen,
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)

        self.assertEqual(raised.exception.stage, "input")
        self.assertIn("digest", str(raised.exception))
        popen.assert_not_called()


class SelectedMVSContentTests(unittest.TestCase):
    REGION_LENGTHS = (0x80000, 0x500000, 0x20000, 0x20000, 0xA00000, 0x3000000)
    PROFILE_MSX = 0x4D53584D

    def make_bundle(self, directory: Path, *, malformed: bool = False,
                    version: int = 1, roles: tuple[int, ...] | None = None) -> Path:
        if roles is None:
            roles = ((1, 2, 3, 4, 5, 6) if version == 1 else
                     (1, 2, 3, 4, 5, 6, 7) if version == 2 else
                     (1, 2, 3, 4, 5, 6, 8))
        lengths_by_role = dict(zip(range(1, 7), self.REGION_LENGTHS)) | {
            7: 0x20000, 8: 0x20000,
        }
        bundle = bytearray(b"GNMV" + version.to_bytes(4, "big") +
                           self.PROFILE_MSX.to_bytes(4, "big") +
                           len(roles).to_bytes(4, "big"))
        for role in roles:
            length = lengths_by_role[role]
            if malformed and role == 1:
                length -= 1
            bundle.extend(role.to_bytes(4, "big"))
            bundle.extend(length.to_bytes(8, "big"))
            bundle.extend(bytes(length))
        path = directory / "selected.gnmv"
        path.write_bytes(bundle)
        return path

    def make_inputs(self, directory: Path, content: Path) -> tuple[object, Path]:
        app = directory / "RetroArch.app"
        executable = app / "Contents" / "MacOS" / "RetroArch"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"mock pinned app bytes")
        (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleShortVersionString": smoke.EXPECTED_VERSION,
            "CFBundleExecutable": "RetroArch",
            "CFBundleIdentifier": smoke.EXPECTED_BUNDLE_IDENTIFIER,
        }))
        core = directory / "glueyneo_libretro.dylib"
        core.write_bytes(b"synthetic core")
        args = type("Args", (), {
            "retroarch": app, "core": core, "content": content, "timeout": 20.0,
        })()
        return args, executable

    def test_synthetic_selected_bundle_is_accepted_without_publishing_content_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = self.make_bundle(directory, version=2)
            args, executable = self.make_inputs(directory, content)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    smoke.EXPECTED_EXECUTABLE_SHA256 if Path(path).resolve() == executable.resolve()
                    else actual_sha(Path(path))
                )),
            ):
                identity = smoke.validate_inputs(args)[3]
            serialized = json.dumps(identity, sort_keys=True)
            content_digest = smoke.sha256(content)

        self.assertEqual(identity["content_kind"], "selected-mvs")
        self.assertNotIn("fixture_sha256", identity)
        self.assertNotIn("content_sha256", identity)
        self.assertNotIn(str(content), serialized)
        self.assertNotIn(content_digest, serialized)

    def test_frontend_rejects_missing_audio_bios_and_accepts_current_versions(self) -> None:
        for version, roles, expected in (
            (1, (1, 2, 3, 4, 5, 6), False),
            (2, (1, 2, 3, 4, 5, 6, 7), True),
            (3, (1, 2, 3, 4, 5, 6, 8), True),
            (3, (1, 2, 3, 4, 5, 6, 7, 8), True),
        ):
            with self.subTest(version=version, roles=roles), \
                    tempfile.TemporaryDirectory() as temporary:
                content = self.make_bundle(Path(temporary), version=version,
                                           roles=roles)
                self.assertIs(smoke.is_normalized_mvs_bundle(content.read_bytes()), expected)

    def test_wrong_zoom_version_role_sets_are_rejected(self) -> None:
        invalid = (
            (2, (1, 2, 3, 4, 5, 6, 8)),
            (3, (1, 2, 3, 4, 5, 6, 7)),
            (3, (1, 2, 3, 4, 5, 6, 7, 7)),
            (4, (1, 2, 3, 4, 5, 6)),
        )
        for version, roles in invalid:
            with self.subTest(version=version, roles=roles), \
                    tempfile.TemporaryDirectory() as temporary:
                content = self.make_bundle(Path(temporary), version=version,
                                           roles=roles)
                self.assertFalse(smoke.is_normalized_mvs_bundle(content.read_bytes()))

    def test_title_ocr_returns_only_finite_outcomes_and_fails_closed(self) -> None:
        executable = getattr(smoke, "TITLE_OCR_EXECUTABLE", None)
        self.assertEqual(executable, "/usr/bin/swift",
                         "title OCR must use the trusted system Swift executable")
        with tempfile.TemporaryDirectory() as temporary:
            capture = Path(temporary) / "capture.png"
            capture.write_bytes(b"bounded test capture")
            cases = (
                ("metal_slug_title\n", "pass"),
                ("known_wrong_title\n", "fail"),
                ("title_unrecognized\n", "unknown"),
                ("raw OCR text with private data", "unknown"),
            )
            nonblack = (smoke.WIDTH, smoke.HEIGHT, 3,
                        bytes([32, 24, 16]) * (smoke.WIDTH * smoke.HEIGHT))
            for output, expected in cases:
                with self.subTest(output=expected), \
                        mock.patch.object(smoke, "decode_png", return_value=nonblack), \
                        mock.patch.object(smoke.Path, "is_file", autospec=True,
                                          side_effect=lambda path: True), \
                        mock.patch.object(smoke.os, "access", return_value=True), \
                        mock.patch.object(smoke.shutil, "which",
                                          side_effect=AssertionError("PATH lookup is forbidden")), \
                        mock.patch.dict(smoke.os.environ, {
                            "PATH": "/untrusted/test/path",
                            "GLUEYNEO_TEST_SECRET": "must-not-be-inherited",
                        }), \
                        mock.patch.object(
                            smoke.subprocess, "run",
                            return_value=subprocess.CompletedProcess(
                                [executable], 0, output, "")) as run:
                    self.assertEqual(smoke.recognize_title_capture(capture), expected)
                    self.assertLessEqual(run.call_args.kwargs["timeout"], 10.0)
                    self.assertEqual(run.call_args.args[0][0],
                                     executable)
                    self.assertEqual(set(run.call_args.kwargs["env"]), {
                        "PATH", "HOME", "TMPDIR", "GLUEYNEO_TITLE_CAPTURE",
                    })
                    self.assertEqual(
                        run.call_args.kwargs["env"]["PATH"],
                        smoke.TITLE_OCR_ENVIRONMENT["PATH"],
                    )
                    self.assertEqual(
                        run.call_args.kwargs["env"]["GLUEYNEO_TITLE_CAPTURE"],
                        str(capture),
                    )
            with mock.patch.object(smoke.Path, "is_file", autospec=True,
                                   side_effect=lambda path: True), \
                    mock.patch.object(smoke.os, "access", return_value=True), \
                    mock.patch.object(smoke.shutil, "which",
                                      side_effect=AssertionError("PATH lookup is forbidden")), \
                    mock.patch.object(
                        smoke.subprocess, "run",
                        side_effect=subprocess.TimeoutExpired(
                            [executable], 10)):
                self.assertEqual(smoke.recognize_title_capture(capture), "unknown")
            with mock.patch.object(smoke.Path, "is_file", autospec=True,
                                   side_effect=lambda path: True), \
                    mock.patch.object(smoke.os, "access", return_value=True), \
                    mock.patch.object(smoke.shutil, "which",
                                      side_effect=AssertionError("PATH lookup is forbidden")), \
                    mock.patch.object(smoke.subprocess, "run", side_effect=OSError("unavailable")):
                self.assertEqual(smoke.recognize_title_capture(capture), "unknown")
            capture.unlink()
            self.assertEqual(smoke.recognize_title_capture(capture), "unknown")

    def test_black_title_capture_fails_without_calling_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            capture = Path(temporary) / "black.png"
            capture.write_bytes(b"bounded test capture")
            black = (smoke.WIDTH, smoke.HEIGHT, 3,
                     bytes(smoke.WIDTH * smoke.HEIGHT * 3))
            with mock.patch.object(smoke, "decode_png", return_value=black), \
                    mock.patch.object(smoke.subprocess, "run") as run:
                self.assertEqual(smoke.recognize_title_capture(capture), "fail")
                run.assert_not_called()

    def test_title_retry_uses_later_recognized_capture_and_fails_closed(self) -> None:
        self.assertEqual(smoke.title_recognition_outcome(["fail", "pass"]), "pass")
        self.assertEqual(smoke.title_recognition_outcome(["fail", "fail", "fail"]), "fail")
        self.assertEqual(smoke.title_recognition_outcome(["fail", "unknown"]), "unknown")
        self.assertEqual(smoke.title_recognition_outcome([]), "unknown")
        self.assertEqual(smoke.title_recognition_outcome(["pass", "private text"]), "unknown")

    def test_mvs_frontend_log_keeps_runtime_fault_active_after_title(self) -> None:
        loaded = "[INFO] glueyneo: MVS bundle loaded\n"
        classify = smoke.mvs_frontend_log_outcome
        self.assertEqual(classify(loaded), "pass")
        self.assertEqual(classify(loaded +
                         "[ERROR] glueyneo: MVS guest run fault\n"), "fail")
        self.assertEqual(classify("[WARN] stock GLSL\n"), "unknown")
        self.assertEqual(classify(None), "unknown")
        # A title in the first frame cannot mask a fault logged during later captures.
        self.assertEqual(smoke.title_recognition_outcome(["pass", "fail", "fail"]), "pass")
        self.assertEqual(smoke.frontend_acceptance_outcome(
            exited_cleanly=True, capture_geometry_ok=True,
            log_outcome=classify(loaded +
                                 "[ERROR] glueyneo: MVS guest run fault\n")),
            "fail")
        self.assertEqual(smoke.frontend_acceptance_outcome(
            exited_cleanly=True, capture_geometry_ok=True, log_outcome="pass"),
            "pass")
        self.assertEqual(smoke.frontend_acceptance_outcome(
            exited_cleanly=True, capture_geometry_ok=True, log_outcome="unknown"),
            "unknown")

    def test_frontend_logs_are_retained_and_runtime_fault_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            frontend_log = directory / "retroarch.log"
            process_log = directory / "process.log"
            capture_dir = directory / "captures"
            capture_dir.mkdir()
            frontend_log.write_text(
                "glueyneo: MVS bundle loaded\n"
                "glueyneo: MVS guest run fault\n", encoding="utf-8")
            with process_log.open("wb") as stream:
                status, retained, _hashes = smoke.retain_frontend_logs(
                    frontend_log, process_log, stream, capture_dir)
            self.assertEqual(status, "fail")
            self.assertEqual(len(retained), 2)
            self.assertEqual(len(list(capture_dir.iterdir())), 2)

    def test_selected_acceptance_retains_logs_and_hashes_after_frontend_failure(self) -> None:
        class CrashedProcess:
            pid = 4321
            returncode: int | None = None

            def poll(self) -> int | None:
                return self.returncode

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            capture_dir = directory / "captures"
            content = self.make_bundle(directory, version=3)
            args, _executable = self.make_inputs(directory, content)
            args.acceptance = True
            args.capture_dir = capture_dir
            process = CrashedProcess()

            def screenshot(_process: CrashedProcess, screenshots: Path,
                           _prior: dict[Path, int], _timeout: float) -> Path:
                capture = screenshots / "selected-capture.png"
                capture.write_bytes(b"bounded screenshot")
                process.returncode = -11
                return capture

            def launch(command: list[str], **kwargs: object) -> CrashedProcess:
                config = Path(command[command.index("--config") + 1])
                (config.parent / "retroarch.log").write_text(
                    "glueyneo: MVS bundle loaded\n" +
                    smoke.MVS_VIDEO_CHECKPOINT_MARKER + "\n", encoding="utf-8")
                stream = kwargs.get("stdout")
                if stream is not None:
                    stream.write(b"bounded process output\n")
                return process

            with (
                mock.patch.object(smoke, "validate_inputs", return_value=(
                    args.retroarch / "Contents" / "MacOS" / "RetroArch",
                    args.core, content,
                    {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER,
                     "content_kind": "selected-mvs"},
                )),
                mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
                mock.patch.object(smoke, "wait_for_recent_crash_reason",
                                  return_value="Exception: EXC_BAD_ACCESS SIGSEGV"),
                mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
                mock.patch.object(smoke, "record_child_pid"),
                mock.patch.object(smoke, "request_frontend_quit", return_value=False),
                mock.patch.object(smoke, "kill_launched_group"),
                mock.patch.object(smoke, "focus_frontend"),
                mock.patch.object(smoke, "request_screenshot", side_effect=screenshot),
                mock.patch.object(smoke, "decode_png", return_value=(
                    smoke.WIDTH, smoke.HEIGHT, 3,
                    bytes([32, 24, 16]) * (smoke.WIDTH * smoke.HEIGHT))),
                mock.patch.object(smoke, "recognize_title_capture", return_value="unknown"),
                mock.patch.object(smoke.subprocess, "Popen", side_effect=launch),
                mock.patch.object(smoke.time, "sleep"),
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)

            diagnostic = raised.exception.diagnostic
            self.assertEqual(raised.exception.stage, "unload")
            self.assertEqual(diagnostic["return_code"], -11)
            self.assertEqual(diagnostic["frontend_log_status"], "pass")
            self.assertEqual(len(diagnostic["frontend_log_paths"]), 2)
            self.assertEqual(len(diagnostic["frontend_log_sha256"]), 2)
            self.assertEqual(len(list(capture_dir.glob("*-private.log"))), 2)

    def test_selected_acceptance_uses_bounded_hotkey_capture_and_clean_exit(self) -> None:
        class RunningProcess:
            pid = 4321
            returncode: int | None = None

            def poll(self) -> int | None:
                return self.returncode

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            capture_dir = directory / "captures"
            content = self.make_bundle(directory, version=3)
            args, _executable = self.make_inputs(directory, content)
            args.acceptance = True
            args.capture_dir = capture_dir
            process = RunningProcess()
            command: list[str] = []

            def launch(arguments: list[str], **kwargs: object) -> RunningProcess:
                command.extend(arguments)
                config = Path(arguments[arguments.index("--config") + 1])
                (config.parent / "retroarch.log").write_text(
                    "glueyneo: MVS bundle loaded\n" +
                    smoke.MVS_VIDEO_CHECKPOINT_MARKER + "\n", encoding="utf-8")
                return process

            def screenshot(_process: RunningProcess, screenshots: Path,
                           _prior: dict[Path, int], _timeout: float) -> Path:
                capture = screenshots / "selected-capture.png"
                capture.write_bytes(b"bounded screenshot")
                return capture

            def quit_frontend(*_args: object) -> bool:
                process.returncode = 0
                return True

            with (
                mock.patch.object(smoke, "validate_inputs", return_value=(
                    args.retroarch / "Contents" / "MacOS" / "RetroArch",
                    args.core, content,
                    {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER,
                     "content_kind": "selected-mvs"},
                )),
                mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
                mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
                mock.patch.object(smoke, "record_child_pid"),
                mock.patch.object(smoke, "focus_frontend") as focus,
                mock.patch.object(smoke, "wait_for_mvs_video_checkpoint",
                                  wraps=smoke.wait_for_mvs_video_checkpoint) as checkpoint,
                mock.patch.object(smoke, "request_screenshot", side_effect=screenshot) as request,
                mock.patch.object(smoke, "decode_png", return_value=(
                    smoke.WIDTH, smoke.HEIGHT, 3,
                    bytes([32, 24, 16]) * (smoke.WIDTH * smoke.HEIGHT))),
                mock.patch.object(smoke, "recognize_title_capture", return_value="unknown"),
                mock.patch.object(smoke, "request_frontend_quit", side_effect=quit_frontend),
                mock.patch.object(smoke, "kill_launched_group"),
                mock.patch.object(smoke, "launch_window", return_value=contextlib.nullcontext()),
                mock.patch.object(smoke, "inject_key",
                                  side_effect=AssertionError("selected-game input is not part of acceptance")),
                mock.patch.object(smoke.subprocess, "Popen", side_effect=launch),
                mock.patch.object(smoke.time, "sleep"),
            ):
                result = smoke.run_smoke(args)

        self.assertEqual(request.call_count, 1)
        self.assertEqual(focus.call_count, 1)
        self.assertEqual(checkpoint.call_count, 1)
        self.assertFalse(any(arg.startswith("--max-frames") for arg in command))
        self.assertEqual(result["acceptance"], {
            "actual_frontend": "pass", "recognizable_title": "unknown"})
        self.assertEqual(result["frontend_frame_boundary"], "at-least-720-successful-video-frames")
        observations = result["observations"]
        self.assertTrue(any("software screenshot hotkey" in entry for entry in observations))
        self.assertTrue(any("application quit path after capture" in entry
                            for entry in observations))
        self.assertFalse(any("600-frame boundary" in entry for entry in observations))
        private = result["private_evidence"]
        self.assertEqual(private["frontend_log_status"], "pass")
        self.assertEqual(private["capture_geometry"], [[smoke.WIDTH, smoke.HEIGHT]])
        self.assertEqual(private["frontend_frame_boundary"], "at-least-720-successful-video-frames")

    def test_malformed_selected_bundle_is_rejected_before_frontend_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = self.make_bundle(directory, malformed=True)
            args, executable = self.make_inputs(directory, content)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    smoke.EXPECTED_EXECUTABLE_SHA256 if Path(path).resolve() == executable.resolve()
                    else actual_sha(Path(path))
                )),
                mock.patch.object(smoke.subprocess, "Popen", side_effect=OSError("launch attempted")) as popen,
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)

        self.assertEqual(raised.exception.stage, "input")
        popen.assert_not_called()

    def test_missing_selected_bundle_is_rejected_before_frontend_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = directory / "missing.gnmv"
            args, executable = self.make_inputs(directory, content)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    smoke.EXPECTED_EXECUTABLE_SHA256 if Path(path).resolve() == executable.resolve()
                    else actual_sha(Path(path))
                )),
                mock.patch.object(smoke.subprocess, "Popen", side_effect=OSError("launch attempted")) as popen,
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)

        self.assertEqual(raised.exception.stage, "input")
        popen.assert_not_called()

    def test_oversized_selected_bundle_is_rejected_before_frontend_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = directory / "oversized.gnmv"
            with content.open("wb") as stream:
                stream.write(b"GNMV")
                stream.truncate(smoke.GNMV_MAX_BYTES + 1)
            args, executable = self.make_inputs(directory, content)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    smoke.EXPECTED_EXECUTABLE_SHA256 if Path(path).resolve() == executable.resolve()
                    else actual_sha(Path(path))
                )),
                mock.patch.object(smoke.subprocess, "Popen", side_effect=OSError("launch attempted")) as popen,
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)

        self.assertEqual(raised.exception.stage, "input")
        self.assertIn("bounded input size", str(raised.exception))
        popen.assert_not_called()


class BundleIdentifierTests(unittest.TestCase):
    VALID_BUNDLE_ID = "com.libretro.dist.RetroArch"
    INVALID_BUNDLE_IDS = (
        "", "com.libretro.dist.RetroArch\"; do shell script \"open /tmp/private\"; --",
        "com.libretro.dist.RetroArch\nquit", "com.libretro.dist.RetroArch'",
        "com.libretro.dist.RetroArch\x01",
    )

    class RunningProcess:
        returncode: int | None = None

        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def poll(self) -> int | None:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = 0
            return 0

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

    def test_plist_identifier_must_match_pinned_app_before_input_validation(self) -> None:
        for bundle_id in self.INVALID_BUNDLE_IDS:
            with self.subTest(bundle_id="malformed"):
                with tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    bundle = directory / "RetroArch.app"
                    contents = bundle / "Contents"
                    contents.mkdir(parents=True)
                    executable = contents / "MacOS" / "RetroArch"
                    executable.parent.mkdir()
                    executable.write_bytes(b"mock executable bytes")
                    (contents / "Info.plist").write_bytes(plistlib.dumps({
                        "CFBundleShortVersionString": smoke.EXPECTED_VERSION,
                        "CFBundleExecutable": "RetroArch",
                        "CFBundleIdentifier": bundle_id,
                    }, fmt=plistlib.FMT_BINARY))
                    args = type("Args", (), {
                        "retroarch": bundle, "core": directory / "core", "content": directory / "fixture",
                    })()
                    with (
                        mock.patch.object(smoke.sys, "platform", "darwin"),
                        mock.patch.object(smoke.subprocess, "run") as run,
                    ):
                        with self.assertRaises(smoke.SmokeBlocked) as raised:
                            smoke.validate_inputs(args)

                self.assertEqual(raised.exception.stage, "identity")
                self.assertIn("bundle identifier", str(raised.exception))
                if bundle_id:
                    self.assertNotIn(bundle_id, str(raised.exception))
                run.assert_not_called()

    def test_quit_helper_uses_one_bounded_fixed_command_for_pinned_identifier(self) -> None:
        process = self.RunningProcess()
        process.pid = 4321
        with (
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4321}),
            mock.patch.object(smoke.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run,
        ):
            smoke.request_frontend_quit(self.VALID_BUNDLE_ID, process, 20.0)

        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0][0:2], ["/usr/bin/osascript", "-e"])
        self.assertEqual(args[0][2], 'tell application id "com.libretro.dist.RetroArch" to quit')
        self.assertTrue(kwargs["check"])
        self.assertLessEqual(kwargs["timeout"], 8.0)
        self.assertFalse(process.terminated)

    def test_invalid_identifier_skips_quit_subprocess_and_terminates_owned_process(self) -> None:
        for bundle_id in self.INVALID_BUNDLE_IDS:
            with self.subTest(bundle_id="malformed"):
                process = self.RunningProcess()
                with mock.patch.object(smoke.subprocess, "run") as run:
                    smoke.request_frontend_quit(bundle_id, process, 20.0)

                run.assert_not_called()
                self.assertTrue(process.terminated)

    def test_cleanup_after_smoke_failure_cannot_launch_quit_for_bad_identifier(self) -> None:
        process = self.RunningProcess()
        identity = {"bundle_id": self.INVALID_BUNDLE_IDS[1]}
        args = mock.Mock(timeout=1.0)
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=(Path("/app"), Path("/core"), Path("/fixture"), identity)),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "request_screenshot", side_effect=smoke.SmokeBlocked("video", "expected test failure")),
            mock.patch.object(smoke, "collect_frontend_output", return_value=""),
            mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
            mock.patch.object(smoke.subprocess, "Popen", return_value=process),
            mock.patch.object(smoke.subprocess, "run") as run,
            mock.patch.object(smoke.time, "sleep"),
        ):
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.run_smoke(args)

        run.assert_not_called()
        self.assertTrue(process.terminated)


class IdentityCheckTest(unittest.TestCase):
    """IN-02: the pinned equality alone refuses every other bundle id; the bounds test is subsumed."""

    def refuse(self, bundle_id: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            contents = directory / "RetroArch.app" / "Contents"
            (contents / "MacOS").mkdir(parents=True)
            (contents / "Info.plist").write_bytes(plistlib.dumps({
                "CFBundleShortVersionString": smoke.EXPECTED_VERSION,
                "CFBundleExecutable": "RetroArch",
                "CFBundleIdentifier": bundle_id,
            }, fmt=plistlib.FMT_BINARY))
            args = type("Args", (), {"retroarch": directory / "RetroArch.app",
                                     "core": directory / "core", "content": directory / "fixture"})()
            with mock.patch.object(smoke.sys, "platform", "darwin"), \
                    mock.patch.object(smoke.subprocess, "run") as run:
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.validate_inputs(args)
            run.assert_not_called()
            self.assertEqual(raised.exception.stage, "identity")

    def test_non_pinned_and_spaced_bundle_ids_are_refused(self) -> None:
        for bundle_id in ("com.example.Other", "com.libretro.dist.Retro Arch"):
            with self.subTest(bundle_id=bundle_id):
                self.refuse(bundle_id)

    def test_validate_inputs_has_no_redundant_pattern_check(self) -> None:
        import inspect
        source = inspect.getsource(smoke.validate_inputs)
        self.assertNotIn("re.fullmatch", source)
        self.assertNotIn("cursor > len(content)", source)

    def test_truncated_bundles_are_still_rejected(self) -> None:
        header = b"GNMV" + (1).to_bytes(4, "big") + smoke.GNMV_PROFILE_MSX.to_bytes(4, "big") \
            + len(smoke.GNMV_REGION_LENGTHS).to_bytes(4, "big")
        for label, content in (("header only", header), ("partial region header", header + b"\x00" * 5)):
            with self.subTest(label=label):
                self.assertFalse(smoke.is_normalized_mvs_bundle(content))


class SingleInstanceTest(unittest.TestCase):
    """E6/CR-07: never stack a second RetroArch and never quit an instance we did not start."""

    class Running:
        returncode: int | None = None

        def __init__(self, pid: int = 4321) -> None:
            self.pid = pid
            self.terminated = False
            self.killed = False

        def poll(self) -> int | None:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = 0
            return 0

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

    def stub_inputs(self) -> mock._patch:
        identity = {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER}
        return mock.patch.object(
            smoke, "validate_inputs",
            return_value=(Path("/app"), Path("/core"), Path("/fixture"), identity))

    def test_run_smoke_refuses_when_an_instance_exists(self) -> None:
        args = mock.Mock(timeout=1.0, child_pid_file=None)
        with (
            self.stub_inputs(),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4242}),
            mock.patch.object(smoke.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.run_smoke(args)
        self.assertEqual(raised.exception.stage, "pre-launch")
        popen.assert_not_called()

    def test_run_launch_probe_refuses_when_an_instance_exists(self) -> None:
        with (
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4242}),
            mock.patch.object(smoke.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.run_launch_probe(Path("/RetroArch"), Path("/core"), Path("/fixture"),
                                       smoke.EXPECTED_BUNDLE_IDENTIFIER,
                                       probe="no_content", timeout=1)
        self.assertEqual(raised.exception.stage, "pre-launch")
        popen.assert_not_called()

    def test_main_prints_one_blocked_json_line_and_returns_one(self) -> None:
        argv = ["retroarch_smoke.py", "--retroarch", "/app", "--core", "/core", "--content", "/fixture"]
        with (
            mock.patch.object(sys, "argv", argv),
            self.stub_inputs(),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4242}),
            mock.patch.object(smoke.subprocess, "Popen") as popen,
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            exit_code = smoke.main()
        lines = stdout.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 1)
        result = json.loads(lines[0])
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "blocked_or_unknown")
        self.assertEqual(result["stage"], "pre-launch")
        popen.assert_not_called()

    def test_lister_fails_closed(self) -> None:
        failures = (
            mock.patch.object(smoke.subprocess, "run", side_effect=OSError("no pgrep")),
            mock.patch.object(smoke.subprocess, "run",
                              side_effect=subprocess.TimeoutExpired("pgrep", 5)),
            mock.patch.object(smoke.subprocess, "run", return_value=subprocess.CompletedProcess([], 2, "", "")),
        )
        for failure in failures:
            with failure, self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.running_retroarch_pids()
            self.assertEqual(raised.exception.stage, "pre-launch")

    def test_lister_maps_pgrep_exit_codes(self) -> None:
        with mock.patch.object(smoke.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 1, "", "")) as run:
            self.assertEqual(smoke.running_retroarch_pids(), set())
        self.assertEqual(run.call_args.args[0], ["/usr/bin/pgrep", "-x", "RetroArch"])
        with mock.patch.object(smoke.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, "4242\n4243\n", "")):
            self.assertEqual(smoke.running_retroarch_pids(), {4242, 4243})

    def test_quit_uses_osascript_only_when_started_pid_is_the_sole_instance(self) -> None:
        process = self.Running(pid=4321)
        with (
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4321}),
            mock.patch.object(smoke.subprocess, "run",
                              return_value=subprocess.CompletedProcess([], 0)) as run,
        ):
            smoke.request_frontend_quit(smoke.EXPECTED_BUNDLE_IDENTIFIER, process, 20.0)
        run.assert_called_once()
        self.assertFalse(process.terminated)

    def test_quit_terminates_by_pid_when_a_foreign_instance_exists(self) -> None:
        process = self.Running(pid=4321)
        with (
            mock.patch.object(smoke, "running_retroarch_pids", return_value={4321, 999}),
            mock.patch.object(smoke.subprocess, "run") as run,
        ):
            smoke.request_frontend_quit(smoke.EXPECTED_BUNDLE_IDENTIFIER, process, 20.0)
        run.assert_not_called()
        self.assertTrue(process.terminated)

    def test_quit_terminates_by_pid_when_the_lister_fails(self) -> None:
        process = self.Running(pid=4321)
        with (
            mock.patch.object(smoke, "running_retroarch_pids",
                              side_effect=smoke.SmokeBlocked("pre-launch", "cannot enumerate")),
            mock.patch.object(smoke.subprocess, "run") as run,
        ):
            smoke.request_frontend_quit(smoke.EXPECTED_BUNDLE_IDENTIFIER, process, 20.0)
        run.assert_not_called()
        self.assertTrue(process.terminated)


class OuterTimeoutTest(unittest.TestCase):
    """E6: an outer runner timeout must not orphan the launched frontend (uses a fake executable)."""

    ROOT = Path(__file__).resolve().parents[2]

    def test_child_pid_file_is_written_before_frontend_interaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pid_file = Path(temporary) / "child.pid"
            process = SingleInstanceTest.Running(pid=4321)
            args = mock.Mock(timeout=1.0, child_pid_file=pid_file)
            observed: list[str] = []

            def screenshot(*_a: object, **_k: object) -> Path:
                observed.append(pid_file.read_text(encoding="utf-8"))
                raise smoke.SmokeBlocked("video", "expected test failure")

            with (
                mock.patch.object(smoke, "validate_inputs", return_value=(
                    Path("/app"), Path("/core"), Path("/fixture"),
                    {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER})),
                mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
                mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
                mock.patch.object(smoke, "request_screenshot", side_effect=screenshot),
                mock.patch.object(smoke, "collect_frontend_output", return_value=""),
                mock.patch.object(smoke, "request_frontend_quit"),
                mock.patch.object(smoke.subprocess, "Popen", return_value=process),
                mock.patch.object(smoke.os, "killpg"),
                mock.patch.object(smoke.time, "sleep"),
            ):
                with self.assertRaises(smoke.SmokeBlocked):
                    smoke.run_smoke(args)
        self.assertEqual(observed, ["4321\n"])

    def test_outer_timeout_leaves_no_fake_frontend_behind(self) -> None:
        sys.path.insert(0, str(self.ROOT / "tools"))
        import verify_playable as playable

        with tempfile.TemporaryDirectory(prefix="outer-timeout-") as temporary:
            base = Path(temporary)
            pid_file = base / "frontend.pid"
            fake = base / "fake-frontend"
            fake.write_text(
                f"#!/bin/sh\necho $$ > '{pid_file}'\nexec sleep 60\n", encoding="utf-8")
            fake.chmod(0o755)
            driver = base / "driver.py"
            driver.write_text(
                "import sys, time\n"
                # Deliberately exceed the operational timeout before startup:
                # fixture readiness must be independent of interpreter/import cost.
                "time.sleep(3.25)\n"
                f"sys.path.insert(0, {str(self.ROOT / 'tests/libretro')!r})\n"
                "import retroarch_smoke as smoke\n"
                "from pathlib import Path\n"
                "identity = {'bundle_id': smoke.EXPECTED_BUNDLE_IDENTIFIER}\n"
                f"smoke.validate_inputs = lambda a: (Path({str(fake)!r}), Path('/core'), Path('/fixture'), identity)\n"
                "smoke.running_retroarch_pids = lambda: set()\n"
                "smoke.crash_report_snapshot = lambda: {}\n"
                "smoke.request_screenshot = lambda *a, **k: time.sleep(60)\n"
                "sys.argv = ['retroarch_smoke.py', '--retroarch', '/a', '--core', '/c', '--content', '/f']\n"
                "raise SystemExit(smoke.main())\n",
                encoding="utf-8")

            seen: list[int] = []

            def reap() -> None:
                # The temporary directory is gone by cleanup time; use the PID captured in the test body.
                for survivor in seen:
                    try:
                        os.kill(survivor, signal.SIGKILL)
                    except OSError:
                        pass

            self.addCleanup(reap)
            work = base / "work"
            work.mkdir()
            runner = playable.Runner(work, base, None)  # type: ignore[arg-type]
            real_popen = subprocess.Popen

            def launch_ready(*args: object, **kwargs: object):
                process = real_popen(*args, **kwargs)
                ready_deadline = time.monotonic() + 10
                while not pid_file.is_file():
                    if playable._leader_exited(process.pid) or time.monotonic() >= ready_deadline:
                        playable._terminate_lane_group(process, subprocess.TimeoutExpired(args[0], 10))
                        self.fail("fake frontend failed bounded startup before timeout exercise")
                    time.sleep(0.01)
                return process

            started = time.monotonic()
            with mock.patch.object(playable, "verify_snapshot"), \
                 mock.patch.object(playable.subprocess, "Popen", side_effect=launch_ready):
                result = runner.command("actual-retroarch-smoke", [sys.executable, str(driver)],
                                        timeout=3, allow_failure=True)
            self.assertLess(time.monotonic() - started, 60)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("TimeoutExpired:", result.stdout, "cleanup must follow a real outer timeout")
            self.assertTrue(pid_file.is_file(), "the fake frontend never started")
            pid = int(pid_file.read_text(encoding="utf-8"))
            seen.append(pid)
            deadline = time.monotonic() + 10
            alive = True
            while alive and time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    alive = False
            self.assertFalse(alive, f"fake frontend survived the outer timeout: pid {pid}")


class CaptureRobustnessTest(unittest.TestCase):
    """WR-04/WR-05: partial captures and hostile PNGs stay inside the scanned smoke result."""

    IEND = b"\x00\x00\x00\x00IEND\xaeB`\x82"

    @staticmethod
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return len(data).to_bytes(4, "big") + kind + data + crc.to_bytes(4, "big")

    def png(self, width: int, height: int, raw: bytes, *, ihdr: bytes | None = None,
            idat: bytes | None = None) -> bytes:
        header = ihdr if ihdr is not None else (
            width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([8, 2, 0, 0, 0]))
        body = idat if idat is not None else zlib.compress(raw)
        return (b"\x89PNG\r\n\x1a\n" + self.chunk(b"IHDR", header)
                + self.chunk(b"IDAT", body) + self.chunk(b"IEND", b""))

    def decode_error(self, data: bytes) -> smoke.SmokeBlocked:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "capture.png"
            path.write_bytes(data)
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.decode_png(path)
        return raised.exception

    def test_valid_png_still_decodes(self) -> None:
        raw = b"".join(b"\x00" + bytes(range(6)) for _ in range(2))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ok.png"
            path.write_bytes(self.png(2, 2, raw))
            self.assertEqual(smoke.decode_png(path)[:3], (2, 2, 3))

    def test_png_without_iend_is_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "partial.png").write_bytes(b"\x89PNG\r\n\x1a\npartial")
            self.assertIsNone(smoke.select_fresh_screenshot(directory, {}))

    def test_complete_stable_png_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            capture = directory / "done.png"
            capture.write_bytes(b"\x89PNG\r\n\x1a\nbody" + self.IEND)
            self.assertEqual(smoke.select_fresh_screenshot(directory, {}), capture)

    def test_still_growing_png_is_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            capture = directory / "growing.png"
            capture.write_bytes(b"\x89PNG\r\n\x1a\nbody" + self.IEND)

            def grow(_seconds: float) -> None:
                with capture.open("ab") as stream:
                    stream.write(self.IEND)

            with mock.patch.object(smoke.time, "sleep", side_effect=grow):
                self.assertIsNone(smoke.select_fresh_screenshot(directory, {}))

    def test_decode_failures_are_video_stage_blocks(self) -> None:
        width, height = 320, 224
        expected = height * (1 + width * 3)
        cases = {
            "truncated-ihdr": self.png(width, height, b"", ihdr=b"\x00\x00\x01"),
            "corrupt-idat": self.png(width, height, b"", idat=b"not a zlib stream" * 4),
            "oversized-inflate": self.png(width, height, bytes(expected + 4096)),
            "zero-dimensions": self.png(0, 0, b""),
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.decode_error(data).stage, "video")

    def test_truncated_chunk_stream_is_a_video_stage_block(self) -> None:
        data = b"\x89PNG\r\n\x1a\n" + (500).to_bytes(4, "big") + b"IDATshort"
        self.assertEqual(self.decode_error(data).stage, "video")

    def test_non_gnmv_content_is_size_checked_before_it_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            content = directory / "blob.bin"
            content.write_bytes(b"NOPE" + bytes(696))
            fixtures = FixtureIdentityTests()
            args, executable = fixtures.make_inputs(directory, content)
            actual_sha = smoke.sha256
            with (
                mock.patch.object(smoke.sys, "platform", "darwin"),
                mock.patch.object(smoke, "sha256", side_effect=lambda path: (
                    smoke.EXPECTED_EXECUTABLE_SHA256 if Path(path).resolve() == executable.resolve()
                    else actual_sha(Path(path)))),
                mock.patch.object(Path, "read_bytes", side_effect=AssertionError("read before size check")),
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.validate_inputs(args)
        self.assertEqual(raised.exception.stage, "input")


class ScreenshotFreshnessTests(unittest.TestCase):
    def test_ambiguous_paths_and_temporary_descendants_are_fully_redacted(self) -> None:
        roots = ("/Users/private-person", "/Volumes/synthetic", "/tmp/synthetic",
                 "/private/var/folders/private-person", str(Path.home()),
                 str(Path(__file__).resolve().parents[2]), "/custom/synthetic-root")
        for root in roots:
            for component in ("private,tail", "private:tail", "private in tail"):
                for quote in ("", '"', "'"):
                    with self.subTest(component=component, quoted=bool(quote)):
                        path = f"{root}/{component}/sensitive.bin"
                        text = f"video failed status -6: {quote}{path}{quote}"
                        safe = smoke.sanitize_diagnostic_text(text, temporary_root=Path(root))
                        record = smoke.build_diagnostic(
                            stage="video", return_code=-6, survived_before_screenshot=False,
                            output=text, temporary_root=Path(root),
                            crash_report=f"Exception Type: EXC_CRASH {quote}{path}{quote}",
                        )
                        retained = safe + json.dumps(record)
                        self.assertNotIn(root, retained)
                        self.assertNotIn(component, retained)
                        self.assertNotIn("sensitive.bin", retained)
                        self.assertIn("video failed status -6", retained)

    def test_old_screenshot_is_not_selected_for_a_new_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            stale = directory / "stale.png"
            stale.write_bytes(b"old capture")
            prior = smoke.screenshot_snapshot(directory)

            selector = getattr(smoke, "select_fresh_screenshot", None)
            selected = selector(directory, prior) if callable(selector) else None
            self.assertIsNone(selected)

    def test_new_screenshot_is_selected_after_the_prior_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            stale = directory / "stale.png"
            stale.write_bytes(b"old capture")
            prior = smoke.screenshot_snapshot(directory)
            fresh = directory / "fresh.png"
            fresh.write_bytes(b"new capture" + CaptureRobustnessTest.IEND)
            fresh.touch()

            selector = getattr(smoke, "select_fresh_screenshot", None)
            selected = selector(directory, prior) if callable(selector) else None
            self.assertEqual(selected, fresh)


class DiagnosticTests(unittest.TestCase):
    def test_json_escaped_quote_and_apostrophe_paths_are_removed_from_frontend_records(self) -> None:
        with tempfile.TemporaryDirectory(prefix="private-root-") as temporary:
            root = Path(temporary)
            diagnostics = (
                f'video failed status -6: "{root}/private capture/secret\\"tail.rom" permission denied',
                f"Exception Type: EXC_CRASH '{root}/O'Brien/private secret.rom' signal 6",
                f'video failed status -6: "{root}/private"tail/sensitive.bin"',
            )
            for diagnostic in diagnostics:
                with self.subTest(diagnostic=diagnostic):
                    safe = smoke.sanitize_diagnostic_text(diagnostic, temporary_root=root)
                    self.assertEqual(smoke.sanitize_diagnostic_text(safe, temporary_root=root), safe)
                    record = smoke.build_diagnostic(
                        stage="video", return_code=-6, survived_before_screenshot=False,
                        output=f"video failed status -6: {diagnostic}", temporary_root=root,
                        crash_report=diagnostic if diagnostic.startswith("Exception") else None,
                    )
                    serialized = json.dumps(record, sort_keys=True)
                    self.assertEqual(record["stage"], "video")
                    self.assertEqual(record["return_code"], -6)
                    self.assertIn("status -6", record["output"])
                    self.assertNotIn(str(root), serialized)
                    for private in ("private capture", "secret", "tail.rom", "O'Brien", "private secret", "secret.rom", "tail/sensitive.bin"):
                        self.assertNotIn(private, serialized)
                    if diagnostic.startswith("Exception"):
                        self.assertIn("EXC_CRASH", serialized)

    def test_newline_private_path_suffix_is_removed_from_frontend_and_crash_sinks(self) -> None:
        root = Path("/tmp/synthetic-frontend-temp")
        output = f"video failed status -6: {root}/private\n/tail/sensitive.bin"
        crash_report = (
            f"Exception Type: EXC_CRASH {root}/private\n"
            "Termination Reason: namespace POSIX, code 9, /tail/sensitive.bin"
        )

        safe = smoke.sanitize_diagnostic_text(output, temporary_root=root)
        reason = smoke.extract_crash_reason(crash_report)
        record = smoke.build_diagnostic(
            stage="video", return_code=-6, survived_before_screenshot=False,
            output=output, temporary_root=root, crash_report=crash_report,
        )
        serialized = json.dumps(record, sort_keys=True)
        retained = safe + reason + serialized

        self.assertEqual(smoke.sanitize_diagnostic_text(safe, temporary_root=root), safe)
        self.assertIn("video failed status -6", retained)
        self.assertIn("EXC_CRASH", retained)
        self.assertEqual(record["stage"], "video")
        self.assertEqual(record["return_code"], -6)
        self.assertFalse(record["survived_before_screenshot"])
        self.assertNotIn("/tail/sensitive.bin", retained)
        self.assertNotIn("private", retained)

    def test_space_containing_private_paths_are_removed_from_all_diagnostic_forms(self) -> None:
        cases = (
            ('failed: "/Users/private-person home/private capture/secret.rom": permission denied',
             ("synthetic home", "private capture", "secret.rom")),
            ("failed exit 5: /tmp/temporary work/private file.rom", ("temporary work", "private file.rom")),
            ("failed: /private/var/folders/private-person root/private cache/secret.bin\ncontinued",
             ("cache root", "private cache", "secret.bin")),
            ("failed exit 6: /Volumes/private drive/private media/secret.rom\nready",
             ("private drive", "private media", "secret.rom")),
        )
        for diagnostic, private_parts in cases:
            with self.subTest(prefix=diagnostic.split(":", 1)[0]):
                safe = smoke.sanitize_diagnostic_text(diagnostic)
                for private in private_parts:
                    self.assertNotIn(private, safe)
                self.assertIn("failed", safe)
                details = ("exit 5", "exit 6")
                if any(detail in diagnostic for detail in details):
                    self.assertTrue(any(detail in safe for detail in details))
                if "continued" in diagnostic:
                    self.assertNotIn("continued", safe)
                if "ready" in diagnostic:
                    self.assertNotIn("ready", safe)

    def test_crash_reason_and_serialized_diagnostic_redact_complete_paths(self) -> None:
        report = (
            'Exception Type: EXC_CRASH /Users/private-person home/private capture/secret.rom: '
            'signal 6\nTermination Reason: namespace POSIX, code 9'
        )
        reason = smoke.extract_crash_reason(report)
        record = smoke.build_diagnostic(
            stage="frontend", return_code=-6, survived_before_screenshot=False,
            output='stderr exit 6: /Volumes/private drive/private media/secret.rom',
            crash_report=report,
        )
        serialized = json.dumps(record, sort_keys=True) + reason

        for private in ("synthetic home", "private capture", "secret.rom", "private drive", "private media"):
            self.assertNotIn(private, serialized)
        self.assertIn("EXC_CRASH", serialized)
        self.assertNotIn("Termination Reason", serialized)
        self.assertIn("exit 6", serialized)
    def test_failure_diagnostic_preserves_stage_exit_and_survival(self) -> None:
        builder = getattr(smoke, "build_diagnostic", None)
        record = builder(
            stage="frontend",
            return_code=-6,
            survived_before_screenshot=False,
            output="RetroArch exited before screenshot (status -6)",
        ) if callable(builder) else {}

        self.assertEqual(record.get("stage"), "frontend")
        self.assertEqual(record.get("return_code"), -6)
        self.assertFalse(record.get("survived_before_screenshot"))
        self.assertIn("status -6", record.get("output", ""))

    def test_diagnostic_output_redacts_user_temp_and_checkout_paths(self) -> None:
        builder = getattr(smoke, "build_diagnostic", None)
        record = builder(
            stage="core-content-load",
            return_code=1,
            survived_before_screenshot=False,
            output="failed /Users/private-person/private/game.rom\ntemporary /private/var/folders/private-person/temp\ncheckout /Users/private-person/worktree",
            temporary_root=Path("/private/var/folders/private-person/temp"),
        ) if callable(builder) else {}

        serialized = str(record)
        self.assertNotIn("alice", serialized)
        self.assertNotIn("bob", serialized)
        self.assertNotIn("private/game.rom", serialized)
        self.assertNotIn("/private/var/folders/private-person/temp", serialized)
        self.assertIn("[redacted-path]", serialized)
        self.assertNotIn("temporary", serialized)
        self.assertNotIn("checkout", serialized)

    def test_diagnostic_output_redacts_the_full_home_relative_path(self) -> None:
        text = f"file load failed: {Path.home()}/projects/private-data/rom.bin"

        sanitized = smoke.sanitize_diagnostic_text(text)

        self.assertNotIn("projects/private-data/rom.bin", sanitized)
        self.assertNotIn(str(Path.home()), sanitized)

    def test_frontend_and_subprocess_logs_are_captured_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            process_log = work / "process-output.log"
            frontend_log = work / "retroarch.log"
            process_log.write_text("stdout and stderr", encoding="utf-8")
            frontend_log.write_text("frontend startup trace", encoding="utf-8")

            output = smoke.collect_frontend_output(process_log, frontend_log, work)

        self.assertIn("stdout and stderr", output)
        self.assertIn("frontend startup trace", output)
        self.assertIn("stdout/stderr", output)
        self.assertIn("RetroArch file log", output)

    def test_crash_parser_keeps_only_bounded_reason_fields(self) -> None:
        report = """Process: RetroArch [123]
Path: /Users/private-person/Applications/RetroArch.app/Contents/MacOS/RetroArch
Exception Type: EXC_CRASH (SIGABRT)
Termination Reason: Namespace DYLD, Code 1 Library not loaded: /Users/private-person/private/lib.dylib
Sensitive unrelated line: private capture name
"""

        parser = getattr(smoke, "extract_crash_reason", None)
        reason = parser(report) if callable(parser) else ""

        self.assertIn("EXC_CRASH", reason)
        self.assertIn("DYLD", reason)
        self.assertNotIn("alice", reason)
        self.assertNotIn("private capture", reason)

    def test_crash_parser_reads_macos_ips_json_reason_fields(self) -> None:
        report = "\n".join(
            [
                json.dumps({"app_name": "RetroArch", "procName": "RetroArch"}),
                json.dumps({
                    "exception": {"type": "EXC_CRASH", "signal": "SIGABRT"},
                    "termination": {
                        "namespace": "DYLD", "code": 1,
                        "indicator": "Library not loaded: /Users/private-person/private/lib.dylib",
                        "details": "private desktop session detail",
                    },
                }),
            ]
        )

        reason = smoke.extract_crash_reason(report)

        self.assertIn("EXC_CRASH", reason)
        self.assertIn("DYLD", reason)
        self.assertNotIn("alice", reason)
        self.assertNotIn("desktop session", reason)

    def test_crash_parser_extracts_reasons_from_bounded_truncated_ips(self) -> None:
        report = json.dumps({
            "exception": {"type": "EXC_CRASH", "signal": "SIGABRT"},
            "termination": {"namespace": "DYLD", "code": 1, "indicator": "Library not loaded"},
            "large_tail": "x" * (smoke.DIAGNOSTIC_OUTPUT_LIMIT * 2),
        })[:smoke.DIAGNOSTIC_OUTPUT_LIMIT]

        reason = smoke.extract_crash_reason(report)

        self.assertIn("EXC_CRASH", reason)
        self.assertIn("DYLD", reason)

    def test_diagnostic_preserves_pre_extracted_macos_crash_reason(self) -> None:
        record = smoke.build_diagnostic(
            stage="no-content-startup", return_code=-6,
            survived_before_screenshot=None, output="",
            crash_report="Exception: EXC_CRASH SIGABRT\nTermination: SIGNAL 6 Abort trap: 6",
        )

        self.assertTrue(record["macos_crash_reason_available"])
        self.assertIn("EXC_CRASH", record["macos_crash_reason"])
        self.assertIn("Abort trap", record["macos_crash_reason"])

    def test_diagnostic_tail_is_bounded(self) -> None:
        record = smoke.build_diagnostic(
            stage="frontend", return_code=1, survived_before_screenshot=False,
            output="x" * (smoke.DIAGNOSTIC_OUTPUT_LIMIT + 100),
        )

        self.assertLessEqual(len(record["output"]), smoke.DIAGNOSTIC_OUTPUT_LIMIT)
        self.assertIn("diagnostic output truncated", record["output"])

    def test_pre_screenshot_exit_attaches_process_and_stage_diagnostic(self) -> None:
        class ExitedProcess:
            returncode = -6

            def poll(self) -> int:
                return self.returncode

        args = mock.Mock(timeout=1)
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=(
                Path("/RetroArch"), Path("/core"), Path("/fixture"), {"bundle_id": "org.example.RetroArch"},
            )),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "find_recent_crash_reason", return_value=None),
            mock.patch.object(smoke, "wait_for_recent_crash_reason", return_value=None),
            mock.patch.object(smoke, "CRASH_REPORT_WAIT_SECONDS", 0),
            mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
            mock.patch.object(smoke.subprocess, "Popen", return_value=ExitedProcess()),
            mock.patch.object(smoke, "request_frontend_quit"),
            mock.patch.object(smoke.time, "sleep"),
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.run_smoke(args)

        self.assertEqual(raised.exception.stage, "first-screenshot")
        self.assertEqual(raised.exception.diagnostic["return_code"], -6)
        self.assertFalse(raised.exception.diagnostic["survived_before_screenshot"])

    def test_launch_comparison_localizes_content_failure_after_clean_startup(self) -> None:
        compare = getattr(smoke, "compare_launch_probes", None)
        finding = compare(
            {"return_code": None, "survived_window": True},
            {"return_code": -6, "survived_window": False},
        ) if callable(compare) else ""

        self.assertEqual(finding, "core-or-content-invocation-failed")

    def test_keyboard_authority_failure_is_unavailable_not_a_pass(self) -> None:
        with mock.patch.object(
            smoke.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["osascript"]),
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.inject_key(smoke.RIGHT_KEY_CODE, repeats=1)

        self.assertEqual(raised.exception.stage, "input")
        self.assertIn("could not inject", str(raised.exception))
        self.assertEqual(raised.exception.availability, "unavailable")

    def test_injected_keys_are_held_across_frame_polls_not_tapped(self) -> None:
        # RetroArch samples key state once per frame; a back-to-back down/up
        # (System Events `key code`) can fall between polls and be ignored.
        with (
            mock.patch.object(smoke.subprocess, "run") as run,
            mock.patch.object(smoke, "post_held_key") as post,
            mock.patch.object(smoke.time, "sleep"),
        ):
            smoke.inject_key(smoke.SCREENSHOT_KEY_CODE)
            smoke.inject_key(smoke.RIGHT_KEY_CODE, hold=smoke.ARROW_HOLD_SECONDS)

        for call in run.call_args_list:
            self.assertNotIn("key code", call.args[0][-1])
            self.assertIn("frontmost", call.args[0][-1])
        self.assertEqual(post.call_args_list, [
            mock.call(smoke.SCREENSHOT_KEY_CODE, smoke.KEY_HOLD_SECONDS),
            mock.call(smoke.RIGHT_KEY_CODE, smoke.ARROW_HOLD_SECONDS),
        ])
        frame = 1.0 / 60.0
        self.assertGreaterEqual(smoke.KEY_HOLD_SECONDS, 3 * frame)
        self.assertGreaterEqual(smoke.ARROW_HOLD_SECONDS, smoke.KEY_HOLD_SECONDS)

    def test_held_key_posts_down_then_waits_hold_then_up(self) -> None:
        log: list[tuple[str, object]] = []

        class Services:
            def __init__(self, preflight: bool) -> None:
                self.preflight = preflight
                self.CGPreflightPostEventAccess = lambda: self.preflight
                self.CGEventCreateKeyboardEvent = lambda source, key, down: 1000 + key * 2 + int(down)
                self.CGEventPost = lambda tap, event: log.append(("post", (tap, event)))
                self.CFRelease = lambda event: log.append(("release", event))

        with (
            mock.patch("ctypes.CDLL", return_value=Services(True)),
            mock.patch.object(smoke.time, "sleep", side_effect=lambda s: log.append(("sleep", s))),
        ):
            smoke.post_held_key(smoke.RIGHT_KEY_CODE, 0.25)

        down = 1000 + smoke.RIGHT_KEY_CODE * 2 + 1
        up = 1000 + smoke.RIGHT_KEY_CODE * 2
        self.assertEqual(log, [
            ("post", (smoke.CG_HID_EVENT_TAP, down)), ("release", down), ("sleep", 0.25),
            ("post", (smoke.CG_HID_EVENT_TAP, up)), ("release", up),
        ])

        log.clear()
        with (
            mock.patch("ctypes.CDLL", return_value=Services(False)),
            mock.patch.object(smoke.subprocess, "run"),
            mock.patch.object(smoke.time, "sleep"),
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.inject_key(smoke.RIGHT_KEY_CODE)
        self.assertEqual(log, [])
        self.assertEqual(raised.exception.availability, "unavailable")

    def test_screenshot_request_repeats_hotkey_dropped_before_frontend_is_ready(self) -> None:
        class Running:
            returncode = None

            def poll(self) -> None:
                return None

        clock = [0.0]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            requests: list[int] = []

            def inject(key_code: int) -> None:
                requests.append(key_code)
                if len(requests) == 3:  # first two requests are dropped
                    (directory / "capture.png").write_bytes(b"png" + CaptureRobustnessTest.IEND)

            def sleep(seconds: float) -> None:
                clock[0] += seconds

            with (
                mock.patch.object(smoke, "inject_key", side_effect=inject),
                mock.patch.object(smoke.time, "monotonic", side_effect=lambda: clock[0]),
                mock.patch.object(smoke.time, "sleep", side_effect=sleep),
            ):
                selected = smoke.request_screenshot(Running(), directory, {}, timeout=20.0)

            self.assertEqual(selected, directory / "capture.png")
            self.assertEqual(requests, [smoke.SCREENSHOT_KEY_CODE] * 3)

            with (
                mock.patch.object(smoke, "inject_key", side_effect=lambda key_code: requests.append(key_code)),
                mock.patch.object(smoke.time, "monotonic", side_effect=lambda: clock[0]),
                mock.patch.object(smoke.time, "sleep", side_effect=sleep),
            ):
                requests.clear()
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.request_screenshot(Running(), directory, smoke.screenshot_snapshot(directory), timeout=3.0)
            self.assertEqual(raised.exception.stage, "video")
            self.assertLessEqual(len(requests), 4)  # bounded by timeout / retry interval

    def test_frontend_config_captures_raw_core_frame_without_osd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            text = smoke.write_frontend_config(work, work / "screenshots").read_text(encoding="utf-8")
        self.assertIn('video_gpu_screenshot = "false"', text)
        self.assertIn('video_scale = "2"', text)
        self.assertIn('notification_show_screenshot = "false"', text)
        self.assertIn('input_screenshot = "f8"', text)

    def test_selected_acceptance_uses_software_hotkey_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            text = smoke.write_frontend_config(work, work / "screenshots").read_text(encoding="utf-8")
        self.assertIn('video_gpu_screenshot = "false"', text)
        self.assertIn('video_scale = "2"', text)

    def test_blocked_keyboard_authority_stays_unknown_in_command_result(self) -> None:
        error = smoke.SmokeBlocked("input", "macOS could not inject the mapped arrow-key input")
        stdout = io.StringIO()
        with (
            mock.patch.object(sys, "argv", [
                "retroarch_smoke.py", "--retroarch", "/Applications/RetroArch.app",
                "--core", "/tmp/core.dylib", "--content", "/tmp/fixture.bin",
            ]),
            mock.patch.object(smoke, "run_smoke", side_effect=error),
            mock.patch.object(smoke, "validate_inputs", return_value=(Path("/app"), Path("/core"), Path("/fixture"), {"fixture_sha256": "abc"})),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = smoke.main()

        result = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "blocked_or_unknown")
        self.assertEqual(result["availability"], "unavailable")
        self.assertNotEqual(result["status"], "pass")

    def test_launch_probes_use_distinct_profiles_without_starting_gui(self) -> None:
        class FakeProcess:
            def __init__(self, return_code: int | None) -> None:
                self.returncode = return_code

            def wait(self, timeout: float | None = None) -> int:
                if self.returncode is None:
                    raise subprocess.TimeoutExpired("fake-retroarch", timeout)
                return self.returncode

            def poll(self) -> int | None:
                return self.returncode

        with (
            mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
            mock.patch.object(smoke.subprocess, "Popen", side_effect=[FakeProcess(None), FakeProcess(-6)]) as popen,
            mock.patch.object(smoke, "request_frontend_quit"),
            mock.patch.object(smoke, "find_recent_crash_reason", return_value=None),
            mock.patch.object(smoke, "wait_for_recent_crash_reason", return_value=None),
            mock.patch.object(smoke, "CRASH_REPORT_WAIT_SECONDS", 0),
            mock.patch.object(smoke, "DIAGNOSTIC_PROBE_SECONDS", 0.01),
        ):
            no_content = smoke.run_launch_probe(
                Path("/RetroArch"), Path("/core"), Path("/fixture"), "org.example.RetroArch",
                probe="no_content", timeout=1,
            )
            core_content = smoke.run_launch_probe(
                Path("/RetroArch"), Path("/core"), Path("/fixture"), "org.example.RetroArch",
                probe="core_content", timeout=1,
            )

        config_paths = [call.args[0][call.args[0].index("--config") + 1] for call in popen.call_args_list]
        self.assertNotEqual(config_paths[0], config_paths[1])
        self.assertTrue(no_content["survived_window"])
        self.assertFalse(core_content["survived_window"])
        self.assertEqual(smoke.compare_launch_probes(no_content, core_content), "core-or-content-invocation-failed")


class LaunchWindowTest(unittest.TestCase):
    """GWR-05a: a termination signal during the frontend launch is deferred, never lost (T-04-66)."""

    def install(self) -> dict[int, object]:
        handlers: dict[int, object] = {}
        patcher = mock.patch.object(
            smoke.signal, "signal", side_effect=lambda signum, handler: handlers.__setitem__(signum, handler))
        patcher.start()
        self.addCleanup(patcher.stop)
        smoke.install_signal_cleanup()
        return handlers

    def test_launch_window_defers_a_signal_and_raises_on_exit(self) -> None:
        handlers = self.install()
        handler = handlers[signal.SIGTERM]
        with self.assertRaises(smoke.SmokeBlocked) as raised:
            with smoke.launch_window():
                handler(signal.SIGTERM, None)  # type: ignore[operator]
                inside = True
        self.assertTrue(inside)
        self.assertEqual(raised.exception.stage, "interrupted")
        # The second-signal guards are installed before the raise.
        self.assertEqual(handlers[signal.SIGTERM], signal.SIG_IGN)

    def test_launch_window_without_a_signal_exits_quietly(self) -> None:
        self.install()
        with smoke.launch_window():
            pass

    def test_handler_outside_the_launch_window_raises_immediately(self) -> None:
        handlers = self.install()
        with self.assertRaises(smoke.SmokeBlocked) as raised:
            handlers[signal.SIGHUP](signal.SIGHUP, None)  # type: ignore[operator]
        self.assertEqual(raised.exception.stage, "interrupted")

    def test_signal_during_popen_still_records_and_kills_the_child(self) -> None:
        handlers = self.install()
        process = SingleInstanceTest.Running(pid=4321)
        with tempfile.TemporaryDirectory() as temporary:
            pid_file = Path(temporary) / "child.pid"
            args = mock.Mock(timeout=1.0, child_pid_file=pid_file)

            def popen(*_a: object, **_k: object) -> object:
                handlers[signal.SIGTERM](signal.SIGTERM, None)  # type: ignore[operator]
                return process

            with (
                mock.patch.object(smoke, "validate_inputs", return_value=(
                    Path("/app"), Path("/core"), Path("/fixture"),
                    {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER})),
                mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
                mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
                mock.patch.object(smoke, "collect_frontend_output", return_value=""),
                mock.patch.object(smoke, "request_frontend_quit") as quit_frontend,
                mock.patch.object(smoke, "kill_launched_group") as kill_group,
                mock.patch.object(smoke.subprocess, "Popen", side_effect=popen),
                mock.patch.object(smoke.time, "sleep"),
            ):
                with self.assertRaises(smoke.SmokeBlocked) as raised:
                    smoke.run_smoke(args)
            self.assertEqual(raised.exception.stage, "interrupted")
            self.assertEqual(pid_file.read_text(encoding="utf-8"), "4321\n")
        quit_frontend.assert_called_once()
        kill_group.assert_called_once_with(process)

    def test_g2wr_06_deferred_signal_survives_a_raising_body(self) -> None:
        handlers = self.install()
        body_error = OSError("x")
        with self.assertRaises(smoke.SmokeBlocked) as raised:
            with smoke.launch_window():
                handlers[signal.SIGTERM](signal.SIGTERM, None)  # type: ignore[operator]
                raise body_error
        self.assertEqual(raised.exception.stage, "interrupted")
        self.assertIs(raised.exception.__cause__, body_error)
        self.assertIsNone(smoke._LAUNCH_WINDOW["pending"])
        self.assertFalse(smoke._LAUNCH_WINDOW["open"])

    def test_g2wr_06_body_error_without_signal_propagates_unchanged(self) -> None:
        self.install()
        body_error = OSError("x")
        with self.assertRaises(OSError) as raised:
            with smoke.launch_window():
                raise body_error
        self.assertIs(raised.exception, body_error)

    def test_g2wr_06_pid_record_failure_is_not_a_launch_failure(self) -> None:
        self.install()
        process = SingleInstanceTest.Running(pid=4321)
        args = mock.Mock(timeout=1.0, child_pid_file=Path("child.pid"))
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=(
                Path("/app"), Path("/core"), Path("/fixture"),
                {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER})),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
            mock.patch.object(smoke, "collect_frontend_output", return_value=""),
            mock.patch.object(smoke, "record_child_pid", side_effect=OSError("disk full")),
            mock.patch.object(smoke, "request_frontend_quit") as quit_frontend,
            mock.patch.object(smoke, "kill_launched_group") as kill_group,
            mock.patch.object(smoke.subprocess, "Popen", return_value=process),
            mock.patch.object(smoke.time, "sleep"),
        ):
            with self.assertRaises(smoke.SmokeBlocked) as raised:
                smoke.run_smoke(args)
        self.assertEqual(raised.exception.stage, "pid-record")
        self.assertNotIn("could not be started", str(raised.exception))
        quit_frontend.assert_called_once()
        kill_group.assert_called_once_with(process)

    def run_smoke_pid_record_failure(self, error: OSError) -> tuple[smoke.SmokeBlocked, mock.Mock, mock.Mock, mock.Mock]:
        self.install()
        process = SingleInstanceTest.Running(pid=4321)
        args = mock.Mock(timeout=1.0, child_pid_file=Path("child.pid"))
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=(
                Path("/app"), Path("/core"), Path("/fixture"),
                {"bundle_id": smoke.EXPECTED_BUNDLE_IDENTIFIER})),
            mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
            mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
            mock.patch.object(smoke, "collect_frontend_output", return_value=""),
            mock.patch.object(smoke, "record_child_pid", side_effect=error),
            mock.patch.object(smoke, "request_frontend_quit") as quit_frontend,
            mock.patch.object(smoke, "kill_launched_group") as kill_group,
            mock.patch.object(smoke, "build_diagnostic", wraps=smoke.build_diagnostic) as build,
            mock.patch.object(smoke.subprocess, "Popen", return_value=process),
            mock.patch.object(smoke.time, "sleep"),
        ):
            try:
                smoke.run_smoke(args)
            except smoke.SmokeBlocked as blocked:
                return blocked, quit_frontend, kill_group, build
            except Exception as unexpected:  # noqa: BLE001 - RED discipline: report, never error
                self.fail(f"uncaught {type(unexpected).__name__}")
        self.fail("run_smoke did not raise SmokeBlocked")

    def test_g3in_02_pid_record_detail_keeps_the_error_class(self) -> None:
        blocked, quit_frontend, kill_group, _build = self.run_smoke_pid_record_failure(
            PermissionError("denied"))
        self.assertEqual(blocked.stage, "pid-record")
        self.assertIn("PermissionError", str(blocked))
        self.assertEqual(blocked.diagnostic["stage"], "pid-record")
        quit_frontend.assert_called_once()
        kill_group.assert_called_once()

    def test_g3in_02_single_pid_record_diagnostic(self) -> None:
        _blocked, _quit, _kill, build = self.run_smoke_pid_record_failure(OSError("disk full"))
        self.assertEqual(build.call_count, 1)
        self.assertEqual(build.call_args.kwargs["stage"], "pid-record")

    def probe_with(self, *, popen: dict[str, object], pid_record: dict[str, object]) -> tuple[dict[str, object], mock.Mock, mock.Mock]:
        """Run `run_launch_probe` with every host operation mocked (G3WR-03)."""
        self.install()
        try:
            with (
                mock.patch.object(smoke, "running_retroarch_pids", return_value=set()),
                mock.patch.object(smoke, "crash_report_snapshot", return_value={}),
                mock.patch.object(smoke, "collect_frontend_output", return_value=""),
                mock.patch.object(smoke, "find_recent_crash_reason", return_value=None),
                mock.patch.object(smoke, "record_child_pid", **pid_record),
                mock.patch.object(smoke, "request_frontend_quit"),
                mock.patch.object(smoke, "reap_frontend", return_value=None) as reap,
                mock.patch.object(smoke, "kill_launched_group") as kill_group,
                mock.patch.object(smoke.subprocess, "Popen", **popen),
                mock.patch.object(smoke, "DIAGNOSTIC_PROBE_SECONDS", 0.01),
            ):
                record = smoke.run_launch_probe(
                    Path("/RetroArch"), Path("/core"), Path("/fixture"), "org.example.RetroArch",
                    probe="no_content", timeout=1, child_pid_file=Path("child.pid"),
                )
        except Exception as error:  # noqa: BLE001 - RED discipline: report, never error
            self.fail(f"uncaught {type(error).__name__}")
        return record, kill_group, reap

    def test_g3wr_03_probe_pid_record_failure_is_not_a_launch_failure(self) -> None:
        process = SingleInstanceTest.Running(pid=4321)
        record, kill_group, reap = self.probe_with(
            popen={"return_value": process}, pid_record={"side_effect": OSError("disk full")})
        self.assertEqual(record["diagnostic"]["stage"], "pid-record")
        self.assertIsNone(record["survived_window"])
        self.assertIsNone(record["return_code"])
        self.assertIn("OSError", record["diagnostic"]["output"])
        kill_group.assert_called_once_with(process)
        reap.assert_not_called()

    def test_g3wr_03_probe_popen_failure_is_still_launch(self) -> None:
        record, kill_group, _reap = self.probe_with(
            popen={"side_effect": OSError("no such file")}, pid_record={"return_value": None})
        self.assertEqual(record["diagnostic"]["stage"], "launch")
        self.assertIs(record["survived_window"], False)
        kill_group.assert_not_called()

    def test_g3wr_03_compare_launch_probes_reports_pid_record(self) -> None:
        failed = {"survived_window": None, "diagnostic": {"stage": "pid-record"}}
        ok = {"survived_window": True, "diagnostic": {"stage": "no-content-startup"}}
        self.assertEqual(smoke.compare_launch_probes(failed, ok), "diagnostic-pid-record-failed")
        self.assertEqual(smoke.compare_launch_probes(ok, failed), "diagnostic-pid-record-failed")
        self.assertEqual(smoke.compare_launch_probes(ok, ok), "both-launch-probes-survived")
        dead = {"survived_window": False, "diagnostic": {"stage": "launch"}}
        self.assertEqual(smoke.compare_launch_probes(dead, ok), "frontend-startup-failed")

    def test_g3wr_03_run_diagnostics_reports_pid_record_finding(self) -> None:
        failed = {"survived_window": None, "diagnostic": {"stage": "pid-record"}}
        ok = {"survived_window": True, "diagnostic": {"stage": "core-content-load"}}
        args = mock.Mock(timeout=1.0, child_pid_file=None)
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=(
                Path("/app"), Path("/core"), Path("/fixture"), {"bundle_id": "org.example.RetroArch"})),
            mock.patch.object(smoke, "run_launch_probe", side_effect=[failed, ok]),
        ):
            result = smoke.run_diagnostics(args)
        self.assertEqual(result["finding"], "diagnostic-pid-record-failed")

    def test_g4in_03_pid_record_failure_skips_second_probe(self) -> None:
        failed = {"survived_window": None, "diagnostic": {"stage": "pid-record"}}
        ok = {"survived_window": True, "diagnostic": {"stage": "core-content-load"}}
        args = mock.Mock(timeout=1.0, child_pid_file=None)
        inputs = (Path("/app"), Path("/core"), Path("/fixture"), {"bundle_id": "org.example.RetroArch"})
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=inputs),
            mock.patch.object(smoke, "run_launch_probe", side_effect=[failed, ok]) as launch,
        ):
            result = smoke.run_diagnostics(args)
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(result["probes"]["core_content"],
                         {"probe": "core_content", "status": "not-run", "reason": "skipped-after-pid-record"})
        self.assertEqual(result["finding"], "diagnostic-pid-record-failed")
        # A normal first probe still runs the second.
        with (
            mock.patch.object(smoke, "validate_inputs", return_value=inputs),
            mock.patch.object(smoke, "run_launch_probe", side_effect=[ok, ok]) as launch,
        ):
            result = smoke.run_diagnostics(args)
        self.assertEqual(launch.call_count, 2)
        self.assertEqual(result["finding"], "both-launch-probes-survived")

    def test_launch_window_does_not_use_a_signal_mask(self) -> None:
        source = Path(smoke.__file__).read_text(encoding="utf-8")
        calls = [line for line in source.splitlines()
                 if "pthread_sigmask(" in line and not line.lstrip().startswith("#")]
        self.assertEqual(calls, [], "a blocked mask would be inherited by the frontend")


class LeaderSweepTest(unittest.TestCase):
    """GWR-05b: liveness checks do not reap, and the group is swept while the leader pins it."""

    def spawn(self, script: str) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(["/bin/sh", "-c", script], stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(self.finish, process)
        return process

    def finish(self, process: subprocess.Popen[bytes]) -> None:
        self.kill_group(process.pid)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        if process.stdout is not None:
            process.stdout.close()

    @staticmethod
    def kill_group(pid: int) -> None:
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass

    @staticmethod
    def gone(pid: int, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.05)
        return False

    def test_frontend_exited_does_not_reap(self) -> None:
        process = self.spawn("exit 3")
        deadline = time.monotonic() + 5
        while not smoke.frontend_exited(process) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(smoke.frontend_exited(process))
        self.assertIsNone(process.returncode, "the liveness check reaped the leader")
        self.assertEqual(smoke.reap_frontend(process, 2.0), 3)
        self.assertEqual(process.returncode, 3)

    def test_frontend_exited_is_false_for_a_running_leader(self) -> None:
        process = self.spawn("sleep 30")
        self.assertFalse(smoke.frontend_exited(process))

    def test_reap_frontend_returns_none_when_the_leader_outlives_the_timeout(self) -> None:
        process = self.spawn("sleep 30")
        self.assertIsNone(smoke.reap_frontend(process, 0.2))

    def test_reap_frontend_sweeps_the_group_of_an_exited_leader(self) -> None:
        process = self.spawn("sleep 60 </dev/null >/dev/null 2>&1 & echo $!; exit 0")
        helper = int(process.stdout.readline())  # type: ignore[union-attr]
        self.assertEqual(smoke.reap_frontend(process, 5.0), 0)
        self.assertTrue(self.gone(helper), "a helper in the frontend group outlived cleanup")

    def test_group_sweep_happens_before_the_leader_is_reaped(self) -> None:
        process = self.spawn("exit 0")
        seen: list[int | None] = []
        real_killpg = os.killpg

        def killpg(pgid: int, signum: int) -> None:
            seen.append(process.returncode)
            real_killpg(pgid, signum)

        with mock.patch.object(smoke.os, "killpg", side_effect=killpg):
            smoke.reap_frontend(process, 5.0)
        self.assertEqual(seen, [None], "killpg must run exactly once, while the leader is unreaped")

    def test_kill_launched_group_sweeps_an_exited_but_unreaped_leader(self) -> None:
        process = self.spawn("sleep 60 </dev/null >/dev/null 2>&1 & echo $!; exit 0")
        helper = int(process.stdout.readline())  # type: ignore[union-attr]
        deadline = time.monotonic() + 5
        while not smoke.frontend_exited(process) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertIsNone(process.returncode)
        smoke.kill_launched_group(process)
        self.assertTrue(self.gone(helper), "the sweep skipped an exited but unreaped leader")
        self.assertIsNotNone(process.returncode)

    def test_kill_launched_group_never_signals_after_the_leader_is_reaped(self) -> None:
        process = self.spawn("exit 0")
        process.wait(timeout=5)
        with mock.patch.object(smoke.os, "killpg") as killpg:
            smoke.kill_launched_group(process)
        killpg.assert_not_called()

    def test_liveness_is_routed_through_the_non_reaping_helpers(self) -> None:
        source = Path(smoke.__file__).read_text(encoding="utf-8")
        direct = [line for line in source.splitlines()
                  if re.search(r"process\.(poll|wait)\(", line)]
        self.assertLessEqual(len(direct), 3, direct)
        self.assertIn("WNOWAIT", source)


class InputOnlyReplayTests(unittest.TestCase):
    def test_bsv1_zero_state_keyed_masks_cover_all_queries_and_bounds(self):
        masks = [0, *[1 << bit for bit in range(10)], 1023, 0]
        encoded = smoke.mvs_input_replay_bytes(masks, dense_from=3, dense_until=8)
        self.assertEqual(struct.unpack('<10I', encoded[:40]), (0x42535632,1,0,0,0,0,0,0,0,0))
        self.assertEqual(len(encoded), 40 + 132 * (len(masks)-1))
        mapping = {0:64, 1:256, 2:1, 3:2, 4:4, 5:8, 6:16, 7:32, 8:128, 9:512}
        for frame, mask in enumerate(masks[1:], 2):
            block = encoded[40 + (frame-2)*132:40+(frame-1)*132]
            self.assertEqual(block[:3], b'\0\x10\0')
            self.assertEqual(block[-1:], b'f')
            for identifier in range(16):
                port, device, index, padding, key, value = struct.unpack_from('<BBBBHh', block, 3+identifier*8)
                self.assertEqual((port,device,index,padding,key), (0,1,0,0,identifier))
                expected = int(3 <= frame <= 8) if key == 14 else int(bool(mask & mapping.get(key,0)))
                self.assertEqual(value, expected, (frame,key))
        for bad in ([], [0], [True], [-1], [1024], [1,0], [0]*8193):
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.mvs_input_replay_bytes(bad, dense_from=1, dense_until=1)
        for lo, hi in ((0,1),(1,0),(2,1),(1,14),(True,1)):
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.mvs_input_replay_bytes(masks, dense_from=lo, dense_until=hi)
        self.assertEqual(len(smoke.mvs_input_replay_bytes([0]*8192,dense_from=1,dense_until=8192)),40+132*8191)


class FrontendAudioCaptureTests(unittest.TestCase):
    def make_wave(self, path: Path, samples: bytes) -> None:
        import wave
        with wave.open(str(path), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(48000)
            output.writeframes(samples)

    def test_adapter_audio_totals_require_one_bounded_complete_account(self) -> None:
        parse = getattr(smoke, "parse_frontend_audio_delivery", None)
        self.assertTrue(callable(parse), "frontend receipt needs actual adapter submission totals")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frontend.log"
            valid = ('[INFO] glueyneo: MVS audio final delivery: generated=1622 '
                     'submitted=1622 processed=1622 discarded=0 overreports=0\n')
            path.write_text(valid)
            self.assertEqual(parse(path)["processed"], 1622)
            for text in ('', valid+valid, valid.replace('processed=1622','processed=1621'),
                         valid.replace('generated=1622','generated=99999999999999999999')):
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(smoke.SmokeBlocked):
                    parse(path)

    def test_audio_restart_destinations_and_owned_normal_exit_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work, captures = root / "work", root / "captures"
            work.mkdir(); captures.mkdir()
            path = smoke.write_frontend_config(work, captures, direct_log=True)
            text = path.read_text() + 'config_save_on_exit = "false"\nrecord_driver = "wav"\n'
            self.assertFalse(smoke.validate_active_config_destinations(text, work, captures),
                             "a recorder restart must not use an ambient output directory")
            text += (f'recording_output_directory = "{captures / "recordings"}"\n'
                     f'recording_config_directory = "{work}"\n')
            self.assertTrue(smoke.validate_active_config_destinations(text, work, captures))
        stop = getattr(smoke, "stop_owned_frontend_recording", None)
        self.assertTrue(callable(stop), "recording must finalize through the owned normal exit")
        process, keys = mock.Mock(), mock.Mock()
        with mock.patch.object(smoke, "reap_frontend", return_value=0), \
                mock.patch.object(smoke.time, "sleep"):
            stop(process, keys, 2.0)
        self.assertEqual(keys.post_key.call_args_list,
                         [mock.call(53, True), mock.call(53, False)])
        with mock.patch.object(smoke, "reap_frontend", return_value=None), \
                mock.patch.object(smoke.time, "sleep"), self.assertRaises(smoke.SmokeBlocked):
            stop(process, keys, 2.0)

    def test_restarted_recording_selects_only_one_fresh_nonempty_owned_stream(self) -> None:
        select = getattr(smoke, "select_frontend_audio_recording", None)
        self.assertTrue(callable(select), "AV reinit can restart recording in the explicit owned directory")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recordings = root / "recordings"; recordings.mkdir()
            initial = root / "frontend-audio-callback.wav"
            started = time.time_ns()
            self.make_wave(initial, b"")
            path = recordings / "restart.mkv"
            self.make_wave(path, struct.pack("<hhhh", 1, -1, 2, -2))
            result = select(root, started_ns=started, finished_ns=time.time_ns() + 1_000_000)
            self.assertEqual(result["recording_relative_path"], "recordings/restart.mkv")
            self.assertEqual(result["startup_empty_recordings"], 1)
            second = recordings / "second.mkv"
            self.make_wave(second, struct.pack("<hhhh", 1, -1, 2, -2))
            with self.assertRaises(smoke.SmokeBlocked):
                select(root, started_ns=started, finished_ns=time.time_ns() + 1_000_000)
            second.unlink()
            path.unlink(); path.symlink_to(initial)
            with self.assertRaises(smoke.SmokeBlocked):
                select(root, started_ns=started, finished_ns=time.time_ns() + 1_000_000)

    def test_pinned_recorder_padded_header_is_explicit_and_strict(self) -> None:
        # RetroArch v1.22.2 record_wav.c writes sizeof(wav_hdr_t): five-byte
        # tags plus ABI padding. It is not standard RIFF; retain that identity.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "capture.wav"
            pcm = struct.pack("<hhhh", 1, -1, 2, -2)
            header = bytearray(56)
            header[:4] = b"RIFF"
            struct.pack_into("<I", header, 8, 44 + len(pcm))
            header[12:17] = b"WAVE\0"
            header[17:22] = b"fmt \0"
            struct.pack_into("<IHHIIHH", header, 24, 16, 1, 2, 48000, 192000, 4, 16)
            header[44:49] = b"data\0"
            struct.pack_into("<I", header, 52, len(pcm))
            before = time.time_ns()
            path.write_bytes(header + pcm)
            result = smoke.parse_frontend_audio_capture(
                path, owned_directory=root, started_ns=before,
                finished_ns=time.time_ns() + 1_000_000)
            self.assertEqual(result["container"], "retroarch_v1_22_2_wav_padded56")
            self.assertEqual(result["sample_frames"], 2)
            self.assertEqual(result["pcm_sha256"], hashlib.sha256(pcm).hexdigest())
            for offset in (5, 8, 12, 17, 24, 28, 30, 32, 36, 40, 42, 44, 49, 52):
                bad = bytearray(header + pcm)
                bad[offset] ^= 1
                path.write_bytes(bad)
                with self.subTest(offset=offset), self.assertRaises(smoke.SmokeBlocked):
                    smoke.parse_frontend_audio_capture(
                        path, owned_directory=root, started_ns=before,
                        finished_ns=time.time_ns() + 1_000_000)
            path.write_bytes(header + pcm[:-1])
            with self.assertRaises(smoke.SmokeBlocked):
                smoke.parse_frontend_audio_capture(
                    path, owned_directory=root, started_ns=before,
                    finished_ns=time.time_ns() + 1_000_000)

    def test_coreaudio3_runtime_message_survives_localized_driver_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frontend.log"
            message = '[INFO] [CoreAudio3] Using buffer size of 24576 bytes: (latency = 64 ms).\n'
            path.write_text(message + '[INFO] [Audio]: Started synchronous audio driver.\n')
            route = smoke.parse_frontend_audio_route(path, control="normal")
            self.assertEqual((route["status"], route["driver"]), ("pass", "coreaudio3"))
            for text in (message, '[INFO] [Audio]: Started synchronous audio driver.\n',
                         '[INFO] [CoreAudio3] Failed to initialize.\n'):
                path.write_text(text)
                self.assertNotEqual(smoke.parse_frontend_audio_route(
                    path, control="normal")["status"], "pass")

    def test_frontend_audio_chip_frames_require_complete_bounded_contiguous_records(self):
        parse = getattr(smoke,"parse_frontend_audio_frames",None)
        self.assertTrue(callable(parse))
        first="glueyneo: MVS audio frame: 1 0 202752 811 0 135168 0 0 0 1 1 0 0 0 1 1 128 7000\n"
        second="glueyneo: MVS audio frame: 2 64 202752 811 0 135168 1 0 1 0 0 1 1 120 0 0 0 7000\n"
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"log"
            path.write_text(first+second)
            rows=parse(path)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[1]["sampled_mask"],64)
            self.assertEqual(rows[1]["chip"]["fm_key_on_writes"],1)
            self.assertFalse(rows[1]["chip"]["chip_reset"])
            for bad in ("",second,first+first,first+second.replace("2 64","3 64"),
                        first.replace("202752","0"),first.replace(" 811 "," 813 "),
                        first.replace(" 0 135168 "," 2 135168 "),first.rstrip()+" extra\n"):
                path.write_text(bad)
                with self.assertRaises(smoke.SmokeBlocked): parse(path)

    def test_audio_chip_frames_allow_current_cpu_atomic_excess_and_reject_overbound(self):
        # Current owned DIVS.W #1,D0 with D0=-1 costs160 clocks, not132.
        # Frame carry can therefore leave159 clocks of indivisible excess.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "log"
            for excess in (-159, -136, 0, 136, 159):
                path.write_text("glueyneo: MVS audio frame: 1 0 " + str(202752 + excess) +
                                " 811 0 135168 0 0 0 1 1 0 0 0 1 1 128 7000\n")
                with self.subTest(excess=excess):
                    self.assertEqual(len(smoke.parse_frontend_audio_frames(path)), 1)
            for excess in (-160, 160):
                path.write_text("glueyneo: MVS audio frame: 1 0 " + str(202752 + excess) +
                                " 811 0 135168 0 0 0 1 1 0 0 0 1 1 128 7000\n")
                with self.subTest(excess=excess):
                    with self.assertRaises(smoke.SmokeBlocked):
                        smoke.parse_frontend_audio_frames(path)
        maximum_main = 202752 + 159
        ticks = (maximum_main + 2) // 3
        samples = (2 * ticks + 15) // 16
        self.assertEqual((12 * samples + 124) // 125, 812)

    def test_frontend_audio_capture_requires_fresh_bounded_non_silent_callback_pcm(self) -> None:
        parse = getattr(smoke, "parse_frontend_audio_capture", None)
        self.assertTrue(callable(parse), "frontend audio needs a bounded actual callback receipt")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "capture.wav"
            self.make_wave(path, struct.pack("<hhhh", 1, -1, 2, -2))
            # Anchor the positive interval to the stored timestamp. A
            # filesystem may round mtime down past a wall-clock sample taken
            # immediately before writing the fixture.
            capture_mtime = path.stat().st_mtime_ns
            before = capture_mtime
            after = max(time.time_ns(), capture_mtime) + 1_000_000
            receipt = parse(path, owned_directory=root, started_ns=before, finished_ns=after)
            self.assertEqual(receipt["stage"], "frontend_libretro_audio_callback_pre_flush")
            self.assertEqual(receipt["format"], "pcm_s16le_interleaved_stereo")
            self.assertEqual(receipt["sample_rate_hz"], 48000)
            self.assertEqual(receipt["channels"], 2)
            self.assertEqual(receipt["sample_frames"], 2)
            self.assertEqual(receipt["nonzero_samples"], 4)
            self.assertEqual(len(receipt["pcm_sha256"]), 64)
            with self.assertRaises(smoke.SmokeBlocked):
                parse(path, owned_directory=root, started_ns=capture_mtime + 1,
                      finished_ns=after)

            self.make_wave(path, bytes(8))
            with self.assertRaises(smoke.SmokeBlocked):
                parse(path, owned_directory=root, started_ns=before, finished_ns=time.time_ns() + 1_000_000)

    def test_frontend_audio_capture_rejects_malformed_stale_and_wrong_format_files(self) -> None:
        parse = getattr(smoke, "parse_frontend_audio_capture", None)
        self.assertTrue(callable(parse), "frontend audio needs freshness and format rejection")
        import wave
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "capture.wav"
            path.write_bytes(b"not a RIFF capture")
            now = time.time_ns()
            for start, finish in ((now + 1_000_000_000, now + 2_000_000_000),
                                  (now - 2_000_000_000, now - 1_000_000_000)):
                with self.subTest(start=start), self.assertRaises(smoke.SmokeBlocked):
                    parse(path, owned_directory=root, started_ns=start, finished_ns=finish)
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(44100)
                output.writeframes(struct.pack("<hh", 1, -1))
            with self.assertRaises(smoke.SmokeBlocked):
                parse(path, owned_directory=root, started_ns=now - 1_000_000_000,
                      finished_ns=time.time_ns() + 1_000_000_000)

    def test_frontend_audio_capture_rejects_symlinks_and_outside_owned_directory(self) -> None:
        parse = getattr(smoke, "parse_frontend_audio_capture", None)
        self.assertTrue(callable(parse), "frontend audio must stay inside the owned capture directory")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside.wav"
            self.make_wave(outside, struct.pack("<hh", 1, -1))
            owned = root / "owned"
            owned.mkdir()
            link = owned / "capture.wav"
            link.symlink_to(outside)
            now = time.time_ns()
            with self.assertRaises(smoke.SmokeBlocked):
                parse(link, owned_directory=owned, started_ns=now - 1_000_000_000,
                      finished_ns=time.time_ns() + 1_000_000_000)
            with self.assertRaises(smoke.SmokeBlocked):
                parse(outside, owned_directory=owned, started_ns=now - 1_000_000_000,
                      finished_ns=time.time_ns() + 1_000_000_000)

    def test_frontend_audio_route_keeps_driver_initialization_separate_from_mute(self) -> None:
        route = getattr(smoke, "parse_frontend_audio_route", None)
        self.assertTrue(callable(route), "audio route requires runtime log evidence")
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "frontend.log"
            log.write_text('[Audio]: Found audio driver: "coreaudio"\n'
                           '[Audio]: Started synchronous audio driver\n', encoding="utf-8")
            active = route(log, control="normal")
            self.assertEqual((active["status"], active["driver_initialized"], active["driver"]),
                             ("pass", True, "coreaudio"))
            muted = route(log, control="muted")
            self.assertEqual(muted["status"], "pass")
            self.assertEqual(muted["control_status"], "configured_unverified")
            self.assertTrue(muted["mute_configured"])

            log.write_text("[Audio]: audio is disabled by launch config\n", encoding="utf-8")
            disabled = route(log, control="disabled")
            self.assertEqual((disabled["status"], disabled["route_state"]), ("pass", "disabled"))
            log.write_text('[Audio]: Found audio driver: "coreaudio"\n'
                           '[Audio]: Started synchronous audio driver\n', encoding="utf-8")
            self.assertEqual(route(log, control="disabled")["status"], "fail")
            log.write_text('[Audio]: Found audio driver: "null"\n'
                           '[Audio]: Started synchronous audio driver\n', encoding="utf-8")
            self.assertEqual(route(log, control="normal")["status"], "unknown")

    def test_frontend_audio_evidence_rejects_stale_stage_format_and_inactive_route(self) -> None:
        validate = getattr(smoke, "frontend_audio_evidence_is_valid", None)
        self.assertTrue(callable(validate), "audio evidence needs strict stage, format, age, and route binding")
        capture = {
            "status": "pass", "container": "riff_wave",
            "stage": "frontend_libretro_audio_callback_pre_flush",
            "format": "pcm_s16le_interleaved_stereo", "sample_rate_hz": 48000,
            "channels": 2, "sample_width_bytes": 2, "sample_frames": 2,
            "pcm_bytes": 8, "pcm_sha256": "a" * 64, "recording_sha256": "b" * 64,
            "nonzero_samples": 4, "peak_sample": 2, "capture_bytes": 52,
            "capture_started_ns": 100, "capture_finished_ns": 200,
            "capture_mtime_ns": 150,
        }
        active = {"status": "pass", "control": "normal", "audio_enabled": True,
                  "mute_configured": False, "driver": "coreaudio",
                  "driver_initialized": True, "route_state": "active-driver-initialized",
                  "control_status": "pass"}
        delivery = dict(status="pass", stage="adapter_callback_return_totals",
                        generated=2, submitted=2, processed=2, discarded=0, overreports=0)
        self.assertFalse(validate(capture, active, expected_control="normal"))
        self.assertTrue(validate(capture, active, expected_control="normal", delivery=delivery))
        for key, value in (("generated", 3), ("processed", 1), ("discarded", 1), ("overreports", 1)):
            self.assertFalse(validate(capture, active, expected_control="normal",
                                      delivery={**delivery, key:value}))
        for field, value in (("container", "unannounced"), ("stage", "device-output"), ("format", "float32-stereo"),
                             ("sample_rate_hz", 44100), ("capture_mtime_ns", 201),
                             ("pcm_sha256", "bad"), ("nonzero_samples", 0)):
            with self.subTest(field=field):
                self.assertFalse(validate({**capture, field: value}, active,
                                          expected_control="normal", delivery=delivery))
        muted = {**active, "control": "muted", "mute_configured": True,
                 "control_status": "configured_unverified"}
        self.assertTrue(validate(capture, muted, expected_control="muted", delivery=delivery),
                        "pre-flush callback PCM may remain non-silent when device mute is configured")
        disabled = {"status": "pass", "control": "disabled", "audio_enabled": False,
                    "mute_configured": False, "driver": "unknown",
                    "driver_initialized": False, "route_state": "disabled",
                    "control_status": "pass"}
        self.assertTrue(validate(capture, disabled, expected_control="disabled", delivery=delivery),
                        "pre-flush callback PCM may remain non-silent when device audio is disabled")
        self.assertFalse(validate(capture, active, expected_control="disabled", delivery=delivery))


if __name__ == "__main__":
    unittest.main()
