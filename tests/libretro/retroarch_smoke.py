#!/usr/bin/env python3
"""Bounded real-RetroArch load/input/software-video/unload smoke for macOS."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import importlib
import io
import json
import math
import os
import plistlib
import platform
import re
import signal
import stat as stat_module
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import private_paths  # noqa: E402


EXPECTED_VERSION = "1.22.2"
EXPECTED_EXECUTABLE_SHA256 = (
    "ed90b54434a2899de0ddbfed59f335255fb462c8691bd970a1a761ebb5656d65"
)
EXPECTED_FIXTURE_SHA256 = "59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0"
EXPECTED_BUNDLE_IDENTIFIER = "com.libretro.dist.RetroArch"
RASTATE_MAX_BYTES = 8 * 1024 * 1024
RASTATE_MAX_BLOCK_BYTES = 1024 * 1024
RASTATE_MAX_BLOCKS = 8
RASTATE_BLOCK_ALIGNMENT = 8
CONTINUATION_LOG_MAX_BYTES = 16 * 1024 * 1024
CONTINUATION_RAW_MAX_BYTES = 8 * 1024 * 1024
CONTINUATION_WINDOW_FRAMES = 4
CONTINUATION_CHUNK_BYTES = 192
CONTINUATION_AUDIO_MAX_FRAMES = 812
GNMV_PROFILE_MSX = 0x4D53584D
MVS_GNST_MEMORY_BYTES = 217_088
MVS_GNST_BACKUP_RAM_OFFSET = 0x10000
MVS_GNST_BACKUP_RAM_BYTES = 0x10000
GNMV_REGION_LENGTHS = {
    1: 0x80000,
    2: 0x500000,
    3: 0x20000,
    4: 0x20000,
    5: 0xA00000,
    6: 0x3000000,
    7: 0x20000,
    8: 0x20000,
}
GNMV_V2_ROLES = frozenset(range(1, 8))
GNMV_V3_REQUIRED_ROLES = frozenset((*range(1, 7), 8))
GNMV_MAX_REGIONS = 8
GNMV_MAX_BYTES = 64 * 1024 * 1024 + 16 + GNMV_MAX_REGIONS * 12
WIDTH = 320
HEIGHT = 224
CONTINUATION_VIDEO_BYTES = WIDTH * HEIGHT * 4
RIGHT_KEY_CODE = 124
DIAGNOSTIC_OUTPUT_LIMIT = 12 * 1024
DIAGNOSTIC_PROBE_SECONDS = 1.0
CRASH_REPORT_WAIT_SECONDS = 8.0
APPLICATION_SERVICES = "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
CG_HID_EVENT_TAP = 0
CG_LEFT_MOUSE_DOWN = 1
CG_LEFT_MOUSE_UP = 2
CG_LEFT_MOUSE_BUTTON = 0
POINTER_READBACK_TIMEOUT_SECONDS = 2.0


class _CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]
OWNED_FOCUS_READBACK_TIMEOUT_SECONDS = 2.0
OWNED_FOCUS_READBACK_POLL_SECONDS = 0.01
# RetroArch samples keyboard state once per frame (~16.7 ms at 60 Hz); hold
# each injected key for several frames so the poll observes the press.
KEY_HOLD_SECONDS = 0.1
QUIT_KEY_CODE = 53
ARROW_HOLD_SECONDS = 0.25
KEY_GAP_SECONDS = 0.05
FOCUS_SETTLE_SECONDS = 0.2
SCREENSHOT_KEY_CODE = 100
SAVE_STATE_KEY_CODE = 120
LOAD_STATE_KEY_CODE = 118
MENU_TOGGLE_KEY_CODE = 122
MENU_DOWN_KEY_CODE = 125
MENU_CONFIRM_KEY_CODE = 36
# RetroArch 1.22.2 menu_displaylist.c orders the direct state list as
# State Slot, Save State, Load State, Undo Save State, Undo Load State.
UNDO_LOAD_MENU_DOWN_PRESSES = 4
NATIVE_MENU_ACTION_TIMEOUT_SECONDS = 8
STATE_SLOT_DECREASE_KEY_CODE = 97
STATE_SLOT_INCREASE_KEY_CODE = 98
RESET_KEY_CODE = 4
PAUSE_KEY_CODE = 35
FRAME_ADVANCE_KEY_CODE = 40
FRAME_ADVANCE_RELEASE_SECONDS = 0.1
FRONTEND_STDIN_COMMANDS = frozenset({
    "VERSION", "GET_STATUS", "RESET", "SAVE_STATE", "LOAD_STATE",
    "QUIT", "PAUSE_TOGGLE", "FRAMEADVANCE", "MENU_TOGGLE", "MENU_DOWN",
    "MENU_A", "MENU_B", "STATE_SLOT_PLUS", "STATE_SLOT_MINUS",
})
RESET_PENDING_SAMPLE_DELAY_SECONDS = 0.75
RESET_PENDING_SAMPLE_SECONDS = 1
RESET_PENDING_SAMPLE_TIMEOUT_SECONDS = 5
CONTINUATION_STARTUP_NEUTRAL_FRAME_COUNT = 2
SCREENSHOT_RETRY_SECONDS = 1.0
LEFT_KEY_CODE = 123
TITLE_OCR_TIMEOUT_SECONDS = 10.0
TITLE_OCR_EXECUTABLE = "/usr/bin/swift"
TITLE_OCR_ENVIRONMENT = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "HOME": "/tmp",
    "TMPDIR": "/tmp",
}
TITLE_CAPTURE_MAX_BYTES = 12 * 1024 * 1024
AUDIO_CAPTURE_MAX_BYTES = 16 * 1024 * 1024
MVS_FRONTEND_LOAD_MARKER = "glueyneo: MVS bundle loaded"
MVS_VIDEO_CHECKPOINT_MARKER = "glueyneo: MVS video checkpoint: 720 frames"
MVS_FRONTEND_FAILURE_MARKERS = (
    "glueyneo: MVS input update failed",
    "glueyneo: MVS guest run fault",
    "glueyneo: MVS guest run error",
    "glueyneo: MVS video rendering failed",
)
TITLE_OCR_SCRIPT = r'''import Foundation
import Vision
let path = ProcessInfo.processInfo.environment["GLUEYNEO_TITLE_CAPTURE"]!
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
do {
    try VNImageRequestHandler(url: URL(fileURLWithPath: path), options: [:]).perform([request])
    let text = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string.lowercased() }
        .joined(separator: " ").replacingOccurrences(of: "-", with: " ")
    if text.contains("metal") && text.contains("slug") {
        print("metal_slug_title")
    } else if text.contains("neogeo") || text.contains("neo geo") {
        print("known_wrong_title")
    } else {
        print("title_unrecognized")
    }
} catch {
    print("title_ocr_unknown")
}
'''


class SmokeBlocked(RuntimeError):
    def __init__(self, stage: str, detail: str, *, diagnostic: dict[str, object] | None = None) -> None:
        super().__init__(detail)
        self.stage = stage
        self.diagnostic = diagnostic
        self.availability = (
            "unavailable" if stage == "input" and "could not inject" in detail else None
        )


def extract_rastate_mem(container: bytes) -> bytes:
    """Return the single uncompressed core payload from a bounded RASTATE1 file.

    Framing follows RetroArch 1.22.2 at pinned commit
    69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576: an 8-byte file header,
    little-endian 8-byte block headers, 8-byte padded payloads, and a final
    zero-size END block. The core receives only the unaligned MEM payload.
    """
    if not isinstance(container, bytes) or len(container) > RASTATE_MAX_BYTES:
        raise SmokeBlocked("state-container", "RASTATE file exceeds its byte bound")
    if len(container) < 24 or container[:8] != b"RASTATE\x01":
        raise SmokeBlocked("state-container", "unsupported RASTATE header or compression")

    cursor = 8
    seen: set[bytes] = set()
    order = {b"RPLY": 0, b"MEM ": 1, b"ACHV": 2}
    last_order = -1
    mem_payload: bytes | None = None
    ended = False
    for _ in range(RASTATE_MAX_BLOCKS):
        if cursor > len(container) or len(container) - cursor < 8:
            raise SmokeBlocked("state-container", "truncated RASTATE block header")
        marker = container[cursor:cursor + 4]
        block_size = int.from_bytes(container[cursor + 4:cursor + 8], "little")
        cursor += 8
        if marker == b"END ":
            if block_size != 0 or cursor != len(container):
                raise SmokeBlocked("state-container", "invalid RASTATE end block or trailing bytes")
            ended = True
            break
        if marker not in order or marker in seen or order[marker] <= last_order:
            raise SmokeBlocked("state-container", "duplicate, unknown, or misordered RASTATE block")
        if block_size == 0 or block_size > RASTATE_MAX_BLOCK_BYTES:
            raise SmokeBlocked("state-container", "RASTATE block size is outside its bound")
        padded_size = (block_size + RASTATE_BLOCK_ALIGNMENT - 1) & ~(RASTATE_BLOCK_ALIGNMENT - 1)
        if padded_size < block_size or padded_size > len(container) - cursor:
            raise SmokeBlocked("state-container", "truncated or overflowing RASTATE block")
        block_end = cursor + block_size
        padded_end = cursor + padded_size
        if any(container[block_end:padded_end]):
            raise SmokeBlocked("state-container", "RASTATE alignment padding is not zero")
        seen.add(marker)
        last_order = order[marker]
        if marker == b"MEM ":
            mem_payload = container[cursor:block_end]
        cursor = padded_end
    if not ended or mem_payload is None or b"MEM " not in seen:
        raise SmokeBlocked("state-container", "RASTATE requires one complete MEM block and END")
    if not mem_payload.startswith(b"GNST"):
        raise SmokeBlocked("state-container", "RASTATE MEM payload is not a native GNST state")
    return mem_payload


def parse_continuation_observations(log: bytes) -> dict[str, object]:
    """Parse a bounded capture/restore, optional paused snapshot, and four frames."""
    prefix = b"glueyneo: continuation "
    if not isinstance(log, bytes) or len(log) > CONTINUATION_LOG_MAX_BYTES:
        raise SmokeBlocked("continuation-observations", "continuation log exceeds its byte bound")
    selected: list[bytes] = []
    for line in log.splitlines(keepends=True):
        if prefix not in line:
            continue
        if not line.endswith(b"\n") or len(line) > 600 or line.count(prefix) != 1:
            raise SmokeBlocked("continuation-observations", "truncated continuation log record")
        selected.append(line[line.index(prefix):-1])
    selected_bytes = sum(len(line) + 1 for line in selected)
    if selected_bytes > CONTINUATION_RAW_MAX_BYTES or len(selected) > 10_000:
        raise SmokeBlocked("continuation-observations", "continuation records exceed their bound")
    if not selected:
        raise SmokeBlocked("continuation-observations", "continuation records are missing")

    def integer(value: str, maximum: int) -> int:
        if not value or not value.isascii() or not value.isdecimal():
            raise ValueError("invalid integer")
        number = int(value)
        if number > maximum:
            raise ValueError("integer exceeds bound")
        return number

    state = "capture"
    captures: list[dict[str, int]] = []
    capture: dict[str, int] | None = None
    restore: dict[str, int] | None = None
    restore_state: bytearray | None = None
    paused_states: list[dict[str, object]] = []
    frames: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    raw_kind: str | None = None
    raw_buffer: bytearray | None = None
    raw_expected = 0
    last_cycle = 0
    try:
        for raw_line in selected:
            if len(raw_line) > 600:
                raise ValueError("oversized record")
            text = raw_line[len(prefix):].decode("ascii")
            fields = text.split(" ")
            kind = fields[0]
            if kind == "S" and state in {"capture", "restore"} and len(fields) == 4:
                candidate = {
                    "state_bytes": integer(fields[1], 1024 * 1024),
                    "completed_frames": integer(fields[2], (1 << 64) - 1),
                    "executed_cycles": integer(fields[3], (1 << 64) - 1),
                }
                if (candidate["state_bytes"] < 72 or candidate["completed_frames"] == 0 or
                        (captures and (
                            candidate["state_bytes"] != captures[0]["state_bytes"] or
                            candidate["completed_frames"] <= captures[-1]["completed_frames"] or
                            candidate["executed_cycles"] <= captures[-1]["executed_cycles"]))):
                    raise ValueError("invalid capture boundary")
                captures.append(candidate)
                capture = captures[0]
                state = "restore"
            elif kind == "S" and state == "frames" and not frames and len(fields) == 4:
                # A frontend-triggered serialization while paused gives us the
                # effective state after RetroArch applies block_sram_overwrite.
                # It is accepted only before the measured post-load frames.
                candidate = {
                    "state_bytes": integer(fields[1], 1024 * 1024),
                    "completed_frames": integer(fields[2], (1 << 64) - 1),
                    "executed_cycles": integer(fields[3], (1 << 64) - 1),
                }
                if (candidate["state_bytes"] != captures[0]["state_bytes"] or
                        candidate["completed_frames"] < restore["completed_frames"] or
                        candidate["executed_cycles"] < restore["executed_cycles"]):
                    raise ValueError("invalid paused post-restore snapshot boundary")
                paused_states.append(candidate)
            elif kind == "R" and state == "restore" and len(fields) == 4 and captures:
                restore = {
                    "state_bytes": integer(fields[1], 1024 * 1024),
                    "completed_frames": integer(fields[2], (1 << 64) - 1),
                    "executed_cycles": integer(fields[3], (1 << 64) - 1),
                }
                last_capture = captures[-1]
                same_boundary = (
                    restore["completed_frames"] == last_capture["completed_frames"] and
                    restore["executed_cycles"] == last_capture["executed_cycles"])
                later_boundary = (
                    restore["completed_frames"] > last_capture["completed_frames"] and
                    restore["executed_cycles"] > last_capture["executed_cycles"])
                if (restore["state_bytes"] != captures[0]["state_bytes"] or
                        not (same_boundary or later_boundary)):
                    raise ValueError("restore boundary does not follow the latest capture")
                restore_state = bytearray()
                state = "restore-payload"
            elif kind == "M" and state == "restore-payload" and len(fields) == 4 and restore and restore_state is not None:
                frame = integer(fields[1], 0)
                offset = integer(fields[2], 1024 * 1024)
                encoded = fields[3]
                if (frame != 0 or not encoded or len(encoded) > CONTINUATION_CHUNK_BYTES * 2 or
                        len(encoded) % 2 or offset != len(restore_state)):
                    raise ValueError("invalid restored state chunk")
                chunk = bytes.fromhex(encoded)
                if len(chunk) > int(restore["state_bytes"]) - len(restore_state):
                    raise ValueError("restored state exceeds its exact extent")
                restore_state.extend(chunk)
                if len(restore_state) == int(restore["state_bytes"]):
                    restore["state"] = bytes(restore_state)
                    state = "frames"
            elif kind == "F" and state == "frames" and len(fields) == 5:
                frame = integer(fields[1], CONTINUATION_WINDOW_FRAMES)
                input_mask = integer(fields[2], 0x3ff)
                cycle_delta = integer(fields[3], (1 << 64) - 1)
                audio_frames = integer(fields[4], CONTINUATION_AUDIO_MAX_FRAMES)
                if (frame != len(frames) or frame >= CONTINUATION_WINDOW_FRAMES or
                        cycle_delta <= last_cycle or audio_frames == 0):
                    raise ValueError("invalid post-restore frame boundary")
                current = {"frame": frame, "input_mask": input_mask,
                           "cycle_delta": cycle_delta,
                           "audio_frames": audio_frames}
                raw_kind = "V"
                raw_buffer = bytearray()
                raw_expected = CONTINUATION_VIDEO_BYTES
                state = "video"
                last_cycle = cycle_delta
            elif kind in {"V", "A"} and len(fields) == 4 and current and raw_buffer is not None:
                frame = integer(fields[1], CONTINUATION_WINDOW_FRAMES)
                offset = integer(fields[2], CONTINUATION_VIDEO_BYTES +
                                 CONTINUATION_AUDIO_MAX_FRAMES * 4)
                encoded = fields[3]
                if (kind != raw_kind or frame != current["frame"] or
                        not encoded or len(encoded) > CONTINUATION_CHUNK_BYTES * 2 or
                        len(encoded) % 2 or offset != len(raw_buffer)):
                    raise ValueError("invalid raw callback chunk")
                chunk = bytes.fromhex(encoded)
                if len(chunk) > raw_expected - len(raw_buffer):
                    raise ValueError("raw callback exceeds its exact frame extent")
                raw_buffer.extend(chunk)
                if len(raw_buffer) == raw_expected:
                    if raw_kind == "V":
                        current["video"] = bytes(raw_buffer)
                        raw_kind = "A"
                        raw_buffer = bytearray()
                        raw_expected = int(current["audio_frames"]) * 4
                        state = "audio"
                    else:
                        current["audio"] = bytes(raw_buffer)
                        frames.append(current)
                        current = None
                        raw_buffer = None
                        raw_kind = None
                        state = "frames"
            elif kind == "E" and state == "frames" and len(fields) == 2:
                completed = integer(fields[1], CONTINUATION_WINDOW_FRAMES)
                if completed != CONTINUATION_WINDOW_FRAMES or len(frames) != completed:
                    raise ValueError("continuation ended before all frames completed")
                state = "complete"
            else:
                raise ValueError("unexpected, duplicate, or incomplete continuation event")
    except (UnicodeDecodeError, ValueError, OverflowError) as error:
        raise SmokeBlocked("continuation-observations", "continuation records are malformed") from error
    if state != "complete" or capture is None or not captures or restore is None or len(frames) != CONTINUATION_WINDOW_FRAMES:
        raise SmokeBlocked("continuation-observations", "continuation window is incomplete")
    return {"capture": capture, "captures": captures, "restore": restore,
            "paused_states": paused_states, "frames": frames,
            "record_bytes": selected_bytes}


def read_private_regular_file(path: Path, maximum: int) -> bytes:
    """Read one stable, bounded, no-follow file owned by the private invocation."""
    descriptor = -1
    try:
        before_path = path.lstat()
        if (not stat_module.S_ISREG(before_path.st_mode) or before_path.st_size > maximum):
            raise SmokeBlocked("state-container", "private evidence file is not a bounded regular file")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        before_fd = os.fstat(descriptor)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        if not stat_module.S_ISREG(before_fd.st_mode) or identity(before_fd) != identity(before_path):
            raise SmokeBlocked("state-container", "private evidence file changed before read")
        chunks: list[bytes] = []
        total = 0
        while total <= maximum:
            chunk = os.read(descriptor, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after_fd = os.fstat(descriptor)
        after_path = path.lstat()
        if (total > maximum or identity(before_fd) != identity(after_fd) or
                identity(after_fd) != identity(after_path) or total != after_fd.st_size):
            raise SmokeBlocked("state-container", "private evidence file changed during read")
        return b"".join(chunks)
    except OSError as error:
        raise SmokeBlocked("state-container", "private evidence file is unavailable") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def preserve_private_unclassified_state(directory: Path, native_state: bytes) -> str:
    """Keep an unknown guest state only inside the mode-0700 attempt workspace."""
    root = directory.parent.parent
    digest = hashlib.sha256(native_state).hexdigest()
    target = root / f"unclassified-state-{digest[:24]}.gnst"
    try:
        root_info = root.lstat()
    except OSError as error:
        raise SmokeBlocked("state-container", "private state evidence workspace is unavailable") from error
    effective_uid = getattr(os, "geteuid", None)
    current_uid = effective_uid() if effective_uid is not None else None
    if (stat_module.S_ISLNK(root_info.st_mode) or not stat_module.S_ISDIR(root_info.st_mode) or
            root_info.st_mode & 0o077 or
            (current_uid is not None and root_info.st_uid != current_uid)):
        raise SmokeBlocked("state-container", "private state evidence workspace is not owner-only")
    descriptor = -1
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        if read_private_regular_file(target, len(native_state)) != native_state:
            raise SmokeBlocked("state-container", "private state evidence name collision")
        return digest
    except OSError as error:
        raise SmokeBlocked("state-container", "private state evidence could not be retained") from error
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(native_state)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        try:
            target.unlink()
        except OSError:
            pass
        raise SmokeBlocked("state-container", "private state evidence could not be retained") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return digest


def _mvs_state_memory_bounds(state: bytes) -> tuple[int, int]:
    """Return the bounded native GNST memory payload range."""
    if (not isinstance(state, bytes) or not 72 <= len(state) <= 1024 * 1024 or
            state[:4] != b"GNST" or int.from_bytes(state[8:12], "big") != 72 or
            int.from_bytes(state[12:16], "big") != len(state) or
            int.from_bytes(state[24:28], "big") != GNMV_PROFILE_MSX or
            int.from_bytes(state[64:68], "big") != 5):
        raise SmokeBlocked("state-container", "native MVS state header is invalid")
    cursor = 72
    memory_bounds: tuple[int, int] | None = None
    for expected_id in range(1, 6):
        if len(state) - cursor < 8:
            raise SmokeBlocked("state-container", "native MVS state section header is truncated")
        section_id = int.from_bytes(state[cursor:cursor + 4], "big")
        section_size = int.from_bytes(state[cursor + 4:cursor + 8], "big")
        cursor += 8
        if section_id != expected_id or section_size > len(state) - cursor:
            raise SmokeBlocked("state-container", "native MVS state sections are invalid")
        if section_id == 2:
            if section_size != MVS_GNST_MEMORY_BYTES:
                raise SmokeBlocked("state-container", "native MVS memory section has an invalid extent")
            memory_bounds = (cursor, section_size)
        cursor += section_size
    if cursor != len(state) or memory_bounds is None:
        raise SmokeBlocked("state-container", "native MVS state is incomplete")
    return memory_bounds


def extract_mvs_memory(state: bytes) -> bytes:
    """Extract the complete fixed memory section from native MVS GNST."""
    start, size = _mvs_state_memory_bounds(state)
    return state[start:start + size]


def extract_mvs_save_ram(state: bytes) -> bytes:
    """Extract exactly the fixed SAVE_RAM window from a validated native GNST."""
    memory = extract_mvs_memory(state)
    start = MVS_GNST_BACKUP_RAM_OFFSET
    end = start + MVS_GNST_BACKUP_RAM_BYTES
    return memory[start:end]


def public_save_guest_readback(state: bytes) -> str | None:
    """Classify the six read-before-write bytes retained in the guest work RAM."""
    memory = extract_mvs_memory(state)
    actual = bytes(memory[index] for index in range(6))
    if actual == bytes((0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC)):
        return "A"
    if actual == bytes((0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6)):
        return "B"
    return None


def native_state_without_save_ram(state: bytes) -> bytes:
    """Return a comparison copy with only the modeled SRAM window zeroed."""
    memory_start, memory_size = _mvs_state_memory_bounds(state)
    if (MVS_GNST_BACKUP_RAM_OFFSET > memory_size or
            MVS_GNST_BACKUP_RAM_BYTES > memory_size - MVS_GNST_BACKUP_RAM_OFFSET):
        raise SmokeBlocked("state-container", "native MVS backup RAM window exceeds memory")
    result = bytearray(state)
    start = memory_start + MVS_GNST_BACKUP_RAM_OFFSET
    result[start:start + MVS_GNST_BACKUP_RAM_BYTES] = bytes(MVS_GNST_BACKUP_RAM_BYTES)
    return bytes(result)


def native_state_with_save_ram(state: bytes, source_state: bytes) -> bytes:
    """Compose a witness state from one machine history and another SRAM image."""
    memory_start, memory_size = _mvs_state_memory_bounds(state)
    source = extract_mvs_save_ram(source_state)
    if (MVS_GNST_BACKUP_RAM_OFFSET > memory_size or
            len(source) > memory_size - MVS_GNST_BACKUP_RAM_OFFSET):
        raise SmokeBlocked("state-container", "native MVS backup RAM window exceeds memory")
    result = bytearray(state)
    start = memory_start + MVS_GNST_BACKUP_RAM_OFFSET
    result[start:start + len(source)] = source
    return bytes(result)


def public_save_guest_sram_outcome(state: bytes) -> str | None:
    """Classify the public A/B fixture's six independently checked SRAM bytes."""
    save_ram = extract_mvs_save_ram(state)
    offsets = (0, 1, 0x1234, 0x1235, 0xFFFE, 0xFFFF)
    actual = bytes(save_ram[offset] for offset in offsets)
    if actual == bytes((0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC)):
        return "A"
    if actual == bytes((0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6)):
        return "B"
    return None


def compare_frontend_trace(trace: bytes, observations: dict[str, object]) -> dict[str, int]:
    """Compare each exact raw frontend callback and cycle with native GNFO bytes."""
    frames = observations.get("frames")
    if (not isinstance(frames, list) or len(frames) != CONTINUATION_WINDOW_FRAMES or
            not isinstance(trace, bytes) or len(trace) > 8 * 1024 * 1024 or
            len(trace) < 12 or trace[:12] != b"GNFO" + struct.pack(">II", 1, 4)):
        raise SmokeBlocked("continuation-witness", "fresh native witness trace is malformed")
    cursor = 12
    prior_cycles = 0
    nonzero_audio = nonzero_video = 0
    for frame in frames:
        if len(trace) - cursor < 24:
            raise SmokeBlocked("continuation-witness", "fresh native witness frame is truncated")
        input_mask, = struct.unpack_from(">I", trace, cursor)
        elapsed_cycles, = struct.unpack_from(">Q", trace, cursor + 4)
        audio_frames, video_bytes, audio_bytes = struct.unpack_from(">III", trace, cursor + 12)
        cursor += 24
        if (input_mask != frame["input_mask"] or
                elapsed_cycles != frame["cycle_delta"] - prior_cycles or
                audio_frames != frame["audio_frames"] or
                video_bytes != CONTINUATION_VIDEO_BYTES or audio_bytes != audio_frames * 4 or
                video_bytes + audio_bytes > len(trace) - cursor):
            raise SmokeBlocked("continuation-witness", "native input, cycle, or callback extent differs")
        native_video = trace[cursor:cursor + video_bytes]
        cursor += video_bytes
        native_audio = trace[cursor:cursor + audio_bytes]
        cursor += audio_bytes
        if native_video != frame["video"] or native_audio != frame["audio"]:
            raise SmokeBlocked("continuation-witness", "raw callback video or core PCM differs")
        nonzero_video += sum(value != 0 for value in native_video)
        nonzero_audio += sum(sample != 0 for sample, in struct.iter_unpack("<h", native_audio))
        prior_cycles = frame["cycle_delta"]
    if cursor != len(trace):
        raise SmokeBlocked("continuation-witness", "native continuation trace has trailing bytes")
    return {"elapsed_cycles": prior_cycles, "nonzero_audio_samples": nonzero_audio,
            "nonzero_video_bytes": nonzero_video, "trace_bytes": len(trace)}


def require_matching_frontend_mem(observed_mem: object, extracted_mem: object) -> None:
    """Require the actual frontend restore payload to equal its saved RASTATE MEM."""
    if (not isinstance(observed_mem, bytes) or not isinstance(extracted_mem, bytes) or
            observed_mem != extracted_mem):
        raise SmokeBlocked("continuation-observations",
                           "actual loaded MEM differs from slot-zero state")


def parse_frontend_save_ram_queries(log: bytes) -> dict[str, object]:
    """Summarize the observer-only SAVE_RAM API queries made by RetroArch."""
    if not isinstance(log, bytes) or len(log) > MVS_FRONTEND_LOG_LIMIT:
        raise SmokeBlocked("continuation-observations", "frontend log exceeds its byte bound")
    text = log.decode("utf-8", errors="replace")
    sizes = re.findall(
        r"glueyneo: frontend queried MVS SAVE_RAM size: ([0-9]+) bytes", text)
    data_queries = text.count("glueyneo: frontend queried MVS SAVE_RAM data")
    size_bytes = int(sizes[-1]) if sizes else None
    if data_queries < 1 or size_bytes != MVS_GNST_BACKUP_RAM_BYTES:
        raise SmokeBlocked(
            "continuation-observations",
            "RetroArch did not query the expected MVS SAVE_RAM interface",
            diagnostic={"data_query_count": data_queries, "size_query_count": len(sizes),
                        "size_bytes": size_bytes},
        )
    return {"data_query_count": data_queries, "size_query_count": len(sizes),
            "size_bytes": size_bytes}


def private_public_state_workspace(report_value: Path | None) -> tuple[Path, Path]:
    raw_root = os.environ.get("GLUEYNEO_FRONTEND_WORK")
    if not raw_root or report_value is None:
        raise SmokeBlocked("preflight", "private frontend workspace or report is unavailable")
    root_candidate = Path(raw_root)
    try:
        root_stat = root_candidate.lstat()
        root = root_candidate.resolve(strict=True)
    except OSError as error:
        raise SmokeBlocked("preflight", "private frontend workspace is unavailable") from error
    repository = Path(__file__).resolve().parents[2]
    if (stat_module.S_ISLNK(root_stat.st_mode) or not root.is_dir() or
            root == repository or root.is_relative_to(repository) or
            root_stat.st_mode & 0o077 or not os.access(root, os.W_OK)):
        raise SmokeBlocked("preflight", "private frontend workspace is not isolated outside Git")
    report = report_value if report_value.is_absolute() else (Path.cwd() / report_value)
    try:
        parent = report.parent.resolve(strict=True)
        report_stat = report.lstat() if report.exists() or report.is_symlink() else None
    except OSError as error:
        raise SmokeBlocked("preflight", "private result report location is unavailable") from error
    if (not parent.is_relative_to(root) or report_stat is not None or
            report.suffix.lower() != ".json"):
        raise SmokeBlocked("preflight", "private result report must be a new JSON file inside the workspace")
    return root, parent / report.name


def write_private_public_state_report(path: Path, report: dict[str, object]) -> None:
    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > 64 * 1024:
        raise SmokeBlocked("report", "private result report exceeds its size bound")
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            if stream.write(encoded) != len(encoded):
                raise OSError("short report write")
    except OSError as error:
        raise SmokeBlocked("report", "private result report could not be retained") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def read_frontend_log(path: Path) -> bytes:
    descriptor = -1
    try:
        before_path = path.lstat()
    except FileNotFoundError:
        return b""
    try:
        if (not stat_module.S_ISREG(before_path.st_mode) or
                before_path.st_size > MVS_FRONTEND_LOG_LIMIT):
            raise SmokeBlocked("observations", "frontend log is not a bounded regular file")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) |
                             getattr(os, "O_NONBLOCK", 0))
        before_fd = os.fstat(descriptor)
        identity = lambda item: (item.st_dev, item.st_ino)
        if not stat_module.S_ISREG(before_fd.st_mode) or identity(before_fd) != identity(before_path):
            raise SmokeBlocked("observations", "frontend log changed before read")
        chunks: list[bytes] = []
        remaining = before_fd.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise SmokeBlocked("observations", "frontend log was truncated during read")
            chunks.append(chunk)
            remaining -= len(chunk)
        after_fd = os.fstat(descriptor)
        after_path = path.lstat()
        if (identity(before_fd) != identity(after_fd) or
                identity(after_fd) != identity(after_path) or
                after_fd.st_size < before_fd.st_size or
                after_fd.st_size > MVS_FRONTEND_LOG_LIMIT):
            raise SmokeBlocked("observations", "frontend log changed during read")
        return b"".join(chunks)
    except OSError as error:
        raise SmokeBlocked("observations", "frontend log could not be read safely") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def send_frontend_stdin_command(process, command: str) -> dict[str, object]:
    """Send one pinned RetroArch command over its private stdin pipe."""
    if not isinstance(command, str) or command not in FRONTEND_STDIN_COMMANDS:
        raise SmokeBlocked("input", "unsupported or batched RetroArch stdin command")
    requires_ready = bool(getattr(process, "_glueyneo_require_guest_ready", False))
    guest_ready = bool(getattr(process, "_glueyneo_guest_ready", False))
    cleanup_allowed = bool(getattr(process, "_glueyneo_cleanup_command_allowed", False))
    if (requires_ready and not guest_ready and command != "VERSION" and
            not (command == "QUIT" and cleanup_allowed)):
        raise SmokeBlocked("input", "owned frontend guest startup readiness was not established")
    if frontend_exited(process):
        raise SmokeBlocked("input", "RetroArch exited before the stdin command")
    stream = getattr(process, "stdin", None)
    if stream is None or getattr(stream, "closed", False):
        raise SmokeBlocked("input", "owned RetroArch stdin command pipe is unavailable")
    payload = (command + "\n").encode("ascii")
    try:
        written = stream.write(payload)
        stream.flush()
    except (BrokenPipeError, OSError, ValueError) as error:
        raise SmokeBlocked("input", "owned RetroArch stdin command pipe failed") from error
    if written != len(payload):
        raise SmokeBlocked("input", "owned RetroArch stdin command was not fully written")
    trace = getattr(process, "_glueyneo_command_trace", None)
    if isinstance(trace, list):
        trace.append(command)
    return {"command": command, "bytes_written": written}


def wait_for_frontend_stdin_reply(process_log: Path, *, command: str,
                                  previous_size: int, process,
                                  deadline: float) -> str:
    """Read one bounded stdout response emitted by a pinned stdin query."""
    if (command not in {"VERSION", "GET_STATUS"} or type(previous_size) is not int or
            previous_size < 0):
        raise SmokeBlocked("input", "invalid RetroArch stdin reply request")
    while time.monotonic() < deadline:
        if frontend_exited(process):
            exit_code = frontend_returncode(process)
            output = read_frontend_log(process_log)
            tail = output[previous_size:]
            protocol_lines = []
            for line in tail.splitlines():
                if (line == EXPECTED_VERSION.encode("ascii") or
                        line.startswith(b"GET_STATUS ") or
                        line.startswith(b"[Command] Command ")):
                    protocol_lines.append(
                        sanitize_diagnostic_text(
                            line.decode("utf-8", errors="replace"))[:256])
            raise SmokeBlocked(
                "input", "RetroArch exited before the stdin command reply",
                diagnostic={"command": command, "exit_code": exit_code,
                            "stdout_bytes_after_request": len(tail),
                            "stdout_tail_sha256": hashlib.sha256(tail).hexdigest(),
                            "protocol_lines": protocol_lines[-8:]},
            )
        current = read_frontend_log(process_log)
        if len(current) < previous_size:
            raise SmokeBlocked("input", "RetroArch stdout changed during command reply")
        for line in current[previous_size:].splitlines():
            if command == "VERSION" and line == EXPECTED_VERSION.encode("ascii"):
                return EXPECTED_VERSION
            if command == "GET_STATUS" and (
                    line == b"GET_STATUS CONTENTLESS" or re.fullmatch(
                        rb"GET_STATUS (?:PAUSED|PLAYING) [^\r\n]+,crc32=[0-9a-f]+", line)):
                return line.decode("ascii")
        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked("input", "RetroArch stdin command reply timed out")


def query_frontend_stdin(process, process_log: Path, command: str,
                         deadline: float) -> str:
    """Issue a single query and require its exact pinned protocol response."""
    if command not in {"VERSION", "GET_STATUS"}:
        raise SmokeBlocked("input", "unsupported RetroArch stdin query")
    before_size = len(read_frontend_log(process_log))
    send_frontend_stdin_command(process, command)
    return wait_for_frontend_stdin_reply(
        process_log, command=command, previous_size=before_size,
        process=process, deadline=deadline)


def continuation_marker_records(log: bytes) -> list[tuple[str, tuple[int, ...]]]:
    prefix = b"glueyneo: continuation "
    records: list[tuple[str, tuple[int, ...]]] = []
    for line in log.splitlines(keepends=True):
        if prefix not in line:
            continue
        if not line.endswith(b"\n") or len(line) > 600:
            raise SmokeBlocked("continuation-observations", "truncated continuation log record")
        try:
            fields = line[line.index(prefix) + len(prefix):-1].decode("ascii").split(" ")
            kind = fields[0]
            if kind in {"S", "R"} and len(fields) == 4:
                values = tuple(int(value) for value in fields[1:])
            elif kind == "F" and len(fields) == 5:
                values = tuple(int(value) for value in fields[1:])
            elif kind in {"E", "X"} and len(fields) == 2:
                values = (int(fields[1]),)
            elif kind in {"M", "V", "A"} and len(fields) == 4:
                continue
            else:
                raise ValueError("record shape")
            if any(value < 0 for value in values):
                raise ValueError("negative value")
            records.append((kind, values))
        except (UnicodeDecodeError, ValueError) as error:
            raise SmokeBlocked("continuation-observations", "malformed continuation marker") from error
    return records


def completed_continuation_frame_count(log: bytes) -> int:
    """Count frames only after their synchronous video and audio traces finish."""
    prefix = b"glueyneo: continuation "
    if not isinstance(log, bytes) or len(log) > CONTINUATION_LOG_MAX_BYTES:
        raise SmokeBlocked("continuation-observations", "continuation log exceeds its byte bound")
    restore = log.rfind(prefix + b"R ")
    if restore < 0:
        return 0

    complete = 0
    current: dict[str, int] | None = None
    for line in log[restore:].splitlines(keepends=True):
        if prefix not in line:
            continue
        if not line.endswith(b"\n"):
            # The frontend can append a callback record while this file is read.
            # The next poll will see the completed line.
            continue
        if len(line) > 600 or line.count(prefix) != 1:
            raise SmokeBlocked("continuation-observations", "invalid continuation callback chunk")
        try:
            fields = line[line.index(prefix) + len(prefix):-1].decode("ascii").split(" ")
            kind = fields[0]
            if kind == "R" and len(fields) == 4:
                complete = 0
                current = None
            elif kind == "F" and len(fields) == 5:
                frame, _input_mask, cycle_delta, audio_frames = (
                    int(value) for value in fields[1:])
                if (frame != complete or frame >= CONTINUATION_WINDOW_FRAMES or
                        cycle_delta <= 0 or not 0 < audio_frames <= CONTINUATION_AUDIO_MAX_FRAMES or
                        current is not None):
                    raise ValueError("invalid frame boundary")
                current = {"frame": frame, "video_bytes": 0,
                           "audio_bytes": 0, "audio_expected": audio_frames * 4}
            elif kind in {"V", "A"} and len(fields) == 4 and current is not None:
                frame, offset = (int(value) for value in fields[1:3])
                encoded = fields[3]
                if (frame != current["frame"] or not encoded or
                        len(encoded) > CONTINUATION_CHUNK_BYTES * 2 or len(encoded) % 2):
                    raise ValueError("invalid callback extent")
                chunk = bytes.fromhex(encoded)
                if kind == "V":
                    if current["audio_bytes"] or offset != current["video_bytes"]:
                        raise ValueError("nonsequential video callback")
                    next_offset = current["video_bytes"] + len(chunk)
                    if next_offset > CONTINUATION_VIDEO_BYTES:
                        raise ValueError("video callback exceeds its extent")
                    current["video_bytes"] = next_offset
                else:
                    if (current["video_bytes"] != CONTINUATION_VIDEO_BYTES or
                            offset != current["audio_bytes"]):
                        raise ValueError("audio callback precedes complete video")
                    next_offset = current["audio_bytes"] + len(chunk)
                    if next_offset > current["audio_expected"]:
                        raise ValueError("audio callback exceeds its extent")
                    current["audio_bytes"] = next_offset
                    if next_offset == current["audio_expected"]:
                        complete += 1
                        current = None
            elif kind in {"S", "M", "E", "X"}:
                continue
            else:
                raise ValueError("unexpected continuation record")
        except (UnicodeDecodeError, ValueError, OverflowError) as error:
            raise SmokeBlocked("continuation-observations", "malformed continuation callback trace") from error
    return complete


def parse_continuation_restore_states(log: bytes, *,
                                      allow_partial_tail: bool = False) -> list[bytes]:
    """Extract each complete native GNST payload emitted by a frontend restore."""
    if (not isinstance(log, bytes) or len(log) > MVS_FRONTEND_LOG_LIMIT or
            type(allow_partial_tail) is not bool):
        raise SmokeBlocked("continuation-observations", "frontend log exceeds its byte bound")
    prefix = b"glueyneo: continuation "
    restores: list[bytes] = []
    expected_size: int | None = None
    restored = bytearray()
    lines = log.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if prefix not in line:
            continue
        if not line.endswith(b"\n") or len(line) > 600 or line.count(prefix) != 1:
            if allow_partial_tail and index == len(lines) - 1 and not line.endswith(b"\n"):
                break
            raise SmokeBlocked("continuation-observations", "truncated continuation restore record")
        marker_offset = line.index(prefix)
        if line[:marker_offset] not in (b"", b"[INFO] ", b"[libretro INFO] "):
            raise SmokeBlocked("continuation-observations", "unexpected continuation restore prefix")
        try:
            fields = line[marker_offset + len(prefix):-1].decode("ascii").split(" ")
            kind = fields[0]
            if kind == "R" and len(fields) == 4:
                if expected_size is not None or len(restores) >= 16:
                    raise ValueError("nested or excessive restore")
                size, completed_frames, cycles = (int(value) for value in fields[1:])
                if not 72 <= size <= 1024 * 1024 or min(completed_frames, cycles) < 0:
                    raise ValueError("invalid restore boundary")
                expected_size = size
                restored = bytearray()
            elif kind == "M" and len(fields) == 4:
                if expected_size is None:
                    raise ValueError("payload without restore")
                frame, offset = int(fields[1]), int(fields[2])
                encoded = fields[3]
                if (frame != 0 or offset != len(restored) or not encoded or
                        len(encoded) > CONTINUATION_CHUNK_BYTES * 2 or
                        len(encoded) % 2):
                    raise ValueError("invalid restore chunk")
                chunk = bytes.fromhex(encoded)
                if len(chunk) > expected_size - len(restored):
                    raise ValueError("restore chunk exceeds exact extent")
                restored.extend(chunk)
                if len(restored) == expected_size:
                    if restored[:4] != b"GNST":
                        raise ValueError("restore payload is not GNST")
                    _mvs_state_memory_bounds(bytes(restored))
                    restores.append(bytes(restored))
                    expected_size = None
                    restored = bytearray()
            elif expected_size is not None:
                raise ValueError("restore payload was interrupted")
        except (UnicodeDecodeError, ValueError, OverflowError, SmokeBlocked) as error:
            raise SmokeBlocked("continuation-observations",
                               "continuation restore payloads are malformed") from error
    if expected_size is not None and not allow_partial_tail:
        raise SmokeBlocked("continuation-observations", "frontend restore payload is incomplete")
    return restores


def wait_for_continuation_restore_states(log: Path, count: int, process,
                                         deadline: float) -> list[bytes]:
    """Wait for complete chunked restore payloads after their early R markers."""
    if type(count) is not int or not 1 <= count <= 16:
        raise SmokeBlocked("continuation-observations", "invalid restore payload count")
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked("continuation-observations",
                               "RetroArch exited before restore payload completion")
        restores = parse_continuation_restore_states(
            read_frontend_log(log), allow_partial_tail=True)
        if len(restores) >= count:
            return restores
        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked(
        "continuation-observations", "frontend restore payload did not complete",
        diagnostic={"required_restore_count": count,
                    "complete_restore_count": len(restores) if "restores" in locals() else 0})


def validate_undo_load_restore_history(restores: object,
                                       loaded_state: object) -> dict[str, object]:
    """Require undo-load to restore distinct pre-load B history.

    RetroArch captures the live machine immediately before Load State. That
    branch may have advanced since its separately saved B container, so verify
    the actual guest B readback and SRAM plus non-SRAM divergence from the A
    load instead of requiring byte identity with the older B file.
    """
    if (not isinstance(restores, (list, tuple)) or len(restores) != 2 or
            not isinstance(loaded_state, bytes) or
            any(not isinstance(state, bytes) for state in restores)):
        raise SmokeBlocked("continuation-observations", "load and undo-load restore history is incomplete")
    loaded, undo = restores
    if loaded != loaded_state:
        raise SmokeBlocked("continuation-observations", "load payload differs from historical A state")
    if (native_state_without_save_ram(undo) ==
            native_state_without_save_ram(loaded)):
        raise SmokeBlocked("continuation-observations", "undo-load did not restore distinct machine history")
    guest_readback = public_save_guest_readback(undo)
    sram_outcome = public_save_guest_sram_outcome(undo)
    if guest_readback != "B" or sram_outcome != "B":
        raise SmokeBlocked("continuation-observations", "undo-load payload does not carry B guest state and SRAM")
    return {"undo_guest_readback": guest_readback, "undo_sram_outcome": sram_outcome,
            "distinct_non_sram_machine_state": True}


def validate_focused_undo_load_history(restores: object,
                                       loaded_state: object) -> dict[str, object]:
    """Check focused actual undo A/B state without requiring a prior raw seed."""
    if (not isinstance(restores, (list, tuple)) or len(restores) != 2 or
            not isinstance(loaded_state, bytes) or
            any(not isinstance(state, bytes) for state in restores)):
        raise SmokeBlocked("continuation-observations",
                           "focused load and undo restore history is incomplete")
    loaded, undo = restores
    if loaded != loaded_state:
        raise SmokeBlocked("continuation-observations",
                           "focused Load State payload differs from saved A")
    if native_state_without_save_ram(undo) == native_state_without_save_ram(loaded):
        raise SmokeBlocked("continuation-observations",
                           "focused Undo Load did not restore distinct machine history")
    sram_outcome = public_save_guest_sram_outcome(undo)
    guest_readback = public_save_guest_readback(undo)
    if sram_outcome != "B" or guest_readback not in (None, "B"):
        raise SmokeBlocked("continuation-observations",
                           "focused Undo Load lacks the actual live B SRAM witness")
    return {"undo_guest_readback": guest_readback,
            "undo_sram_outcome": sram_outcome,
            "distinct_non_sram_machine_state": True}


def validate_continuation_operation_matrix(
    route: str, *, state_operations: bool, autosave_interval: int,
    external_sram_write: bool = False,
) -> str:
    """Enforce the pinned frontend's separate state and threaded-autosave routes."""
    if (route not in {"sram-policies", "periodic-save", "focused-undo-control", "private-state"} or
            type(state_operations) is not bool or type(autosave_interval) is not int or
            autosave_interval < 0 or type(external_sram_write) is not bool):
        raise SmokeBlocked("operation-matrix", "invalid SRAM continuation operation profile")
    if route in {"sram-policies", "focused-undo-control", "private-state"}:
        if not state_operations or autosave_interval != 0 or external_sram_write:
            raise SmokeBlocked(
                "operation-matrix",
                "SRAM load/undo requires state operations, autosave_interval=0, and no external writer")
    elif state_operations or autosave_interval == 0 or external_sram_write:
        raise SmokeBlocked(
            "operation-matrix",
            "periodic save requires a nonzero interval with no state operations or external writer")
    return route


def public_state_files(directory: Path, expected_count: int, *,
                       started_ns: int,
                       require_distinct: bool = True) -> list[dict[str, object]]:
    files = list(directory.iterdir())
    if len(files) > 4:
        raise SmokeBlocked("state-container", "frontend created too many state files")
    result: list[dict[str, object]] = []
    total = 0
    for path in files:
        try:
            info = path.lstat()
        except OSError as error:
            raise SmokeBlocked("state-container", "frontend state file changed during enumeration") from error
        entry_name = "".join(
            char if char.isascii() and (char.isalnum() or char in "._-") else "_"
            for char in path.name)[:80] or "<empty>"
        if stat_module.S_ISLNK(info.st_mode):
            raise SmokeBlocked("state-container", f"frontend state directory contains a symbolic link entry: {entry_name}")
        if not stat_module.S_ISREG(info.st_mode):
            entry_kind = "directory" if stat_module.S_ISDIR(info.st_mode) else "special"
            raise SmokeBlocked("state-container", f"frontend state directory contains a {entry_kind} entry: {entry_name}")
        if info.st_mtime_ns < started_ns or info.st_size > RASTATE_MAX_BYTES:
            raise SmokeBlocked("state-container", "frontend state file is stale or oversized")
        total += info.st_size
        if total > 2 * RASTATE_MAX_BYTES:
            raise SmokeBlocked("state-container", "frontend state files exceed their aggregate bound")
        container = read_private_regular_file(path, RASTATE_MAX_BYTES)
        if not container.startswith(b"RASTATE"):
            raise SmokeBlocked("state-container", "frontend state directory contains an unexpected file")
        try:
            mem = extract_rastate_mem(container)
        except SmokeBlocked:
            continue  # The pinned frontend writes its bounded state asynchronously.
        outcome = public_save_guest_sram_outcome(mem)
        if outcome is None:
            digest = preserve_private_unclassified_state(directory, mem)
            raise SmokeBlocked(
                "state-container",
                "actual frontend state has no expected public save-guest effects "
                f"(private GNST sha256 {digest})")
        result.append({"name": path.name, "container": container, "mem": mem,
                       "sram_outcome": outcome,
                       "guest_readback": public_save_guest_readback(mem),
                       "container_sha256": hashlib.sha256(container).hexdigest(),
                       "mem_sha256": hashlib.sha256(mem).hexdigest()})
    if len(result) != expected_count:
        return []
    if (require_distinct and
            len({item["sram_outcome"] for item in result}) != expected_count):
        raise SmokeBlocked("state-container", "saved A/B branches are not distinguishable")
    return result


def public_state_file_identity_snapshot(
    directory: Path, states: list[dict[str, object]] | None = None,
) -> dict[str, dict[str, object]]:
    """Bind each complete public state to its current disk identity."""
    if not directory.exists():
        return {}
    entries = list(directory.iterdir())
    if len(entries) > 4:
        raise SmokeBlocked("state-container", "frontend created too many state files")
    if states is None:
        states = public_state_files(
            directory, len(entries), started_ns=0, require_distinct=False)
    if len(states) != len(entries):
        raise SmokeBlocked("state-container", "state directory has an incomplete existing capture")
    snapshot: dict[str, dict[str, object]] = {}
    for state in states:
        name = state.get("name")
        if not isinstance(name, str) or name in snapshot:
            raise SmokeBlocked("state-container", "state capture identity is ambiguous")
        path = directory / name
        try:
            info = path.lstat()
        except OSError as error:
            raise SmokeBlocked("state-container", "state capture changed during identity read") from error
        if (not stat_module.S_ISREG(info.st_mode) or
                info.st_size != len(state.get("container", b""))):
            raise SmokeBlocked("state-container", "state capture changed after complete parsing")
        snapshot[name] = {
            "sha256": state["container_sha256"],
            "mtime_ns": info.st_mtime_ns,
            "size": info.st_size,
            "device": info.st_dev,
            "inode": info.st_ino,
        }
    return snapshot


def wait_for_public_state_files(directory: Path, expected_count: int,
                                started_ns: int, deadline: float, *,
                                require_distinct: bool = True) -> list[dict[str, object]]:
    while time.monotonic() < deadline:
        candidates = public_state_files(
            directory, expected_count, started_ns=started_ns,
            require_distinct=require_distinct)
        if candidates:
            return candidates
        time.sleep(min(0.025, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked("state-container", "frontend did not produce the expected complete A/B state files")


def wait_for_changed_public_state_files(
    directory: Path, expected_count: int, started_ns: int,
    previous: dict[str, dict[str, object]], deadline: float,
) -> tuple[list[dict[str, object]], list[str]]:
    """Wait until the requested complete state set includes one post-save file identity."""
    if (type(expected_count) is not int or not 1 <= expected_count <= 4 or
            not isinstance(previous, dict)):
        raise SmokeBlocked("state-container", "invalid state-save identity request")
    while time.monotonic() < deadline:
        candidates = public_state_files(
            directory, expected_count, started_ns=started_ns,
            require_distinct=False)
        if candidates:
            current = public_state_file_identity_snapshot(directory, candidates)
            changed = [name for name, identity in current.items()
                       if previous.get(name) != identity]
            if len(changed) == 1:
                return candidates, changed
            if len(changed) > 1:
                raise SmokeBlocked(
                    "state-container", "one state-save command changed multiple slot files",
                    diagnostic={"changed_slot_count": len(changed)})
        time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked(
        "state-container", "state-save callback completed without one changed complete RASTATE file",
        diagnostic={"expected_state_files": expected_count})


def wait_for_new_public_state_file(directory: Path, expected_count: int,
                                  previous_names: set[str], started_ns: int,
                                  deadline: float) -> dict[str, object]:
    candidates = wait_for_public_state_files(
        directory, expected_count, started_ns, deadline, require_distinct=False)
    new_files = [item for item in candidates if item["name"] not in previous_names]
    if len(new_files) != 1:
        raise SmokeBlocked("state-container", "frontend state save did not create one new slot file")
    return new_files[0]


def wait_for_mvs_completed_mask(log: Path, mask: int, baseline_video: int,
                                process, invocation_id: str, deadline: float) -> dict[str, object]:
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked("observations", "RetroArch exited before the requested input frame")
        text = read_frontend_log(log).decode("utf-8", errors="replace")
        records = parse_latest_mvs_input_epoch(text, invocation_id=invocation_id)
        videos = [record for record in records if record["event_kind"] == "V" and
                  record["sampled_mask"] == mask and
                  record["successful_video_sequence"] > baseline_video]
        if videos:
            return videos[-1]
        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked("observations", "requested guest input did not reach a completed frame")


def mvs_observation_epoch_count(log: bytes) -> int:
    """Count complete core-emitted observer begins in a bounded frontend log."""
    if not isinstance(log, bytes) or len(log) > MVS_FRONTEND_LOG_LIMIT:
        raise SmokeBlocked("observations", "frontend log exceeds its byte bound")
    prefix = b"glueyneo: mvs "
    begins = 0
    for line in log.splitlines(keepends=True):
        if prefix not in line or not line.endswith(b"\n") or line.count(prefix) != 1:
            continue
        marker_offset = line.index(prefix)
        if line[:marker_offset] not in (b"", b"[INFO] ", b"[libretro INFO] "):
            continue
        if re.search(rb"glueyneo: mvs B 0 0 0 0\n$", line[marker_offset:]):
            begins += 1
    return begins


def wait_for_new_mvs_observation_epoch(log: Path, previous_count: int, process,
                                       deadline: float) -> int:
    """Wait for an owned frontend reset to restart the core observation epoch."""
    if type(previous_count) is not int or previous_count < 0:
        raise SmokeBlocked("observations", "invalid prior MVS observation epoch count")
    last_log = b""
    current_count = previous_count
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked("observations", "RetroArch exited before the reset epoch")
        last_log = read_frontend_log(log)
        current_count = mvs_observation_epoch_count(last_log)
        if current_count > previous_count:
            return current_count
        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    diagnostic: dict[str, object] = {
        "previous_epoch_count": previous_count,
        "final_epoch_count": current_count,
        "frontend_log_sha256": hashlib.sha256(last_log).hexdigest(),
    }
    try:
        write_private_bytes(log.parent.parent / "reset-failure.log",
                            last_log, MVS_FRONTEND_LOG_LIMIT)
        diagnostic["private_log_retained"] = True
    except SmokeBlocked:
        diagnostic["private_log_retained"] = False
    raise SmokeBlocked("observations", "owned reset did not start a new MVS observation epoch",
                       diagnostic=diagnostic)


def take_owned_process_sample(process, directory: Path) -> dict[str, object]:
    """Take one bounded private stack sample for an owned frontend process."""
    pid = getattr(process, "pid", None)
    if type(pid) is not int or pid <= 0:
        return {"status": "invalid-owned-process"}
    path = directory / f"reset-pending-{pid}-{time.monotonic_ns()}.sample.txt"
    try:
        result = subprocess.run(
            ["/usr/bin/sample", str(pid), str(RESET_PENDING_SAMPLE_SECONDS), "10",
             "-file", str(path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
            timeout=RESET_PENDING_SAMPLE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"status": "sample-timeout"}
    except OSError:
        return {"status": "sample-unavailable"}
    if not path.exists():
        return {"status": "sample-unavailable", "return_code": result.returncode,
                "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()}
    try:
        sample = read_private_regular_file(path, 4 * 1024 * 1024)
    except SmokeBlocked:
        return {"status": "sample-output-invalid", "return_code": result.returncode}
    return {"status": "sampled" if result.returncode == 0 else "sample-command-failed",
            "return_code": result.returncode, "bytes": len(sample),
            "sha256": hashlib.sha256(sample).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()}


def sample_owned_process_if_reset_pending(log: Path, previous_count: int, process,
                                          deadline: float) -> dict[str, object]:
    """Take one bounded private stack sample if the native reset stays pending."""
    sample_at = min(deadline, time.monotonic() + RESET_PENDING_SAMPLE_DELAY_SECONDS)
    while time.monotonic() < sample_at:
        if frontend_exited(process):
            return {"status": "process-exited-before-sample"}
        if mvs_observation_epoch_count(read_frontend_log(log)) > previous_count:
            return {"status": "reset-epoch-arrived-before-sample"}
        time.sleep(min(0.01, max(0.0, sample_at - time.monotonic())))

    if frontend_exited(process):
        return {"status": "process-exited-before-sample"}
    if mvs_observation_epoch_count(read_frontend_log(log)) > previous_count:
        return {"status": "reset-epoch-arrived-before-sample"}
    return take_owned_process_sample(process, log.parent)


def reset_guest_under_mask(keys: "HeldMVSKeys", mask: int, log: Path,
                           process, invocation_id: str,
                           deadline: float, *,
                           via_native_menu: bool = False) -> dict[str, object]:
    """Prove reset was delivered while the fixture selector remained held."""
    if type(via_native_menu) is not bool:
        raise SmokeBlocked("input", "invalid guest reset trigger")
    keys.set_mask(mask)
    previous_epochs = mvs_observation_epoch_count(read_frontend_log(log))
    reset_menu_probe: dict[str, object] | None = None
    pending_sample: dict[str, object] | None = None
    if via_native_menu:
        reset_menu_probe = invoke_native_reset_menu(process, log=log)
        pending_sample = reset_menu_probe.pop("pending_sample", {"status": "not-pending"})
        if pending_sample.get("status") == "not-pending":
            pending_sample = sample_owned_process_if_reset_pending(
                log, previous_epochs, process, deadline)
        try:
            reset_epoch = wait_for_new_mvs_observation_epoch(
                log, previous_epochs, process, deadline)
        except SmokeBlocked as error:
            if error.diagnostic is None:
                error.diagnostic = {}
            error.diagnostic.update({"reset_menu_probe": reset_menu_probe,
                                     "reset_pending_sample": pending_sample})
            raise
    else:
        keys.post_key(RESET_KEY_CODE, True)
        try:
            reset_epoch = wait_for_new_mvs_observation_epoch(
                log, previous_epochs, process, deadline)
        finally:
            keys.post_key(RESET_KEY_CODE, False)
    reset_frame = wait_for_mvs_completed_mask(
        log, mask, -1, process, invocation_id, deadline)
    # For keyboard reset, RetroArch detects a key-down edge. The reset marker
    # may arrive before that runloop poll has consumed our key-up, so wait
    # through one more completed frame under the held selector before another
    # reset may be requested. The native Command action has no key release but
    # follows the same two-frame selector witness contract.
    released_frame = wait_for_mvs_completed_mask(
        log, mask, int(reset_frame["successful_video_sequence"]),
        process, invocation_id, deadline)
    if via_native_menu:
        reset_action = ("RetroArch stdin RESET" if reset_menu_probe and
                        reset_menu_probe.get("activation") ==
                        "pinned stdin RESET command" else "RetroArch Command > Reset")
    else:
        reset_action = "configured reset key"
    result = {**released_frame, "observation_epoch": reset_epoch,
              "reset_trigger_video_sequence": reset_frame["successful_video_sequence"],
              "reset_action": reset_action}
    if via_native_menu:
        result.update(reset_menu_probe=reset_menu_probe,
                      reset_pending_sample=pending_sample)
    return result


def parse_latest_mvs_input_epoch(log_text: str, *, invocation_id: str) -> list[dict[str, object]]:
    lines = log_text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines)
              if re.search(r"glueyneo: mvs B 0 0 0 0\n$", line)]
    if not starts:
        return []
    return parse_mvs_input_observations("".join(lines[starts[-1]:]),
                                        invocation_id=invocation_id, complete=False)


def wait_for_continuation_frame(log: Path, frame_count: int, process,
                                deadline: float) -> None:
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked("continuation-observations", "RetroArch exited before the observer frame")
        if completed_continuation_frame_count(read_frontend_log(log)) >= frame_count:
            return
        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked("continuation-observations", "post-restore observer frame timed out")


def preserve_continuation_failure_log(base: Path, log: Path) -> None:
    """Retain a bounded frontend trace privately when a live route fails."""
    try:
        write_private_bytes(base / "continuation-failure.log",
                            read_frontend_log(log), MVS_FRONTEND_LOG_LIMIT)
    except SmokeBlocked:
        pass


def press_owned_key(keys: "HeldMVSKeys", key_code: int, hold: float = 0.06) -> None:
    keys.post_key(key_code, True)
    try:
        time.sleep(hold)
    finally:
        keys.post_key(key_code, False)


def press_owned_menu_key(keys: "HeldMVSKeys", key_code: int) -> None:
    """Pulse one RGUI key and leave a full release interval for its frame poll."""
    press_owned_key(keys, key_code, KEY_HOLD_SECONDS)
    time.sleep(KEY_GAP_SECONDS)


def wait_for_neutral_mvs_guest_frames(log: Path, process,
                                      baseline_log_size: int, count: int,
                                      deadline: float) -> list[dict[str, object]]:
    """Wait for distinct appended guest audio-frame callbacks with neutral input."""
    if (type(baseline_log_size) is not int or baseline_log_size < 0 or
            type(count) is not int or not 1 <= count <= 8):
        raise SmokeBlocked("continuation-observations",
                           "invalid menu input-release frame request")
    frames: list[dict[str, object]] = []
    nonneutral_frames: list[dict[str, object]] = []
    previous_frame = -1
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked("continuation-observations",
                               "RetroArch exited during the guest input-release interval",
                               diagnostic={"neutral_frames_observed": frames})
        data = read_frontend_log(log)
        if len(data) < baseline_log_size:
            raise SmokeBlocked("observations", "frontend log shrank during input-release wait")
        appended = data[baseline_log_size:]
        for line in appended.splitlines(keepends=True):
            if not line.endswith(b"\n"):
                continue
            match = re.search(
                rb"glueyneo: MVS audio frame: ([0-9]+) ([0-9]+) ", line)
            if match is None:
                continue
            frame_number, sampled_mask = map(int, match.groups())
            if frame_number <= previous_frame:
                continue
            if sampled_mask != 0:
                frames.clear()
                nonneutral_frames.append({"frame": frame_number,
                                          "sampled_mask": sampled_mask})
                nonneutral_frames = nonneutral_frames[-8:]
                previous_frame = frame_number
                continue
            frames.append({"frame": frame_number, "sampled_mask": sampled_mask})
            previous_frame = frame_number
            if len(frames) >= count:
                return frames
        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked(
        "observations", "guest did not produce consecutive neutral input-release frames",
        diagnostic={"required_neutral_frames": count,
                    "neutral_frames_observed": frames,
                    "nonneutral_frames_observed": nonneutral_frames})


def wait_for_owned_quick_menu_release(process, log: Path,
                                      baseline_log_size: int,
                                      deadline: float) -> dict[str, object]:
    """Wait after Undo Load's source-pinned RESUME closes RGUI and flushes input."""
    release_frames = wait_for_neutral_mvs_guest_frames(
        log, process, baseline_log_size, 3, deadline)
    return {
        "closure": "Undo Load State -> CMD_EVENT_RESUME -> retroarch_menu_running_finished(false)",
        "input_release_frames": release_frames,
        "baseline_log_bytes": baseline_log_size,
    }


def activate_owned_menu_item(keys: "HeldMVSKeys", down_presses: int) -> None:
    """Select a source-pinned direct Quick Menu row from its initial State Slot."""
    if type(down_presses) is not int or not 0 <= down_presses <= 16:
        raise SmokeBlocked("input", "invalid pinned Quick Menu row offset")
    press_owned_menu_key(keys, MENU_TOGGLE_KEY_CODE)
    time.sleep(FOCUS_SETTLE_SECONDS)
    for _ in range(down_presses):
        press_owned_menu_key(keys, MENU_DOWN_KEY_CODE)
    press_owned_menu_key(keys, MENU_CONFIRM_KEY_CODE)


def write_private_bytes(path: Path, data: bytes, maximum: int) -> None:
    if not isinstance(data, bytes) or len(data) > maximum:
        raise SmokeBlocked("continuation-witness", "private witness input exceeds its byte bound")
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            if stream.write(data) != len(data):
                raise OSError("short private input write")
    except OSError as error:
        raise SmokeBlocked("continuation-witness", "private witness input could not be retained") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def invoke_frontend_native_witness(witness: Path, bundle: Path, mem: bytes,
                                   observations: dict[str, object], work: Path,
                                   stem: str) -> dict[str, object]:
    frames = observations.get("frames")
    if not isinstance(frames, list) or len(frames) != CONTINUATION_WINDOW_FRAMES:
        raise SmokeBlocked("continuation-witness", "observed future input window is incomplete")
    state_path = work / f"{stem}.gnst"
    inputs_path = work / f"{stem}.gnfi"
    trace_path = work / f"{stem}.gnfo"
    write_private_bytes(state_path, mem, 1024 * 1024)
    inputs = bytearray(b"GNFI" + struct.pack(">II", 1, len(frames)))
    for frame in frames:
        inputs.extend(struct.pack(">IQ", frame["input_mask"], frame["cycle_delta"]))
    write_private_bytes(inputs_path, bytes(inputs), 1024)
    try:
        child = subprocess.run(
            [str(witness), "frontend-import", str(bundle), str(state_path),
             str(inputs_path), str(trace_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SmokeBlocked("continuation-witness", "fresh native witness process could not complete") from error
    if child.returncode != 0 or len(child.stdout) > 256 * 1024:
        raise SmokeBlocked("continuation-witness", "fresh native witness rejected the actual frontend state",
                           diagnostic={"return_code": child.returncode,
                                       "stdout_sha256": hashlib.sha256(child.stdout).hexdigest(),
                                       "stderr_sha256": hashlib.sha256(child.stderr).hexdigest()})
    result_lines = [line for line in child.stdout.splitlines()
                    if line.startswith(b"STATE_FRONTEND_RESULT ")]
    if len(result_lines) != 1:
        raise SmokeBlocked("continuation-witness", "fresh native witness result is missing or duplicated")
    try:
        result = json.loads(result_lines[0].split(b" ", 1)[1])
    except (json.JSONDecodeError, IndexError) as error:
        raise SmokeBlocked("continuation-witness", "fresh native witness result is malformed") from error
    if (result.get("outcome") != "pass" or result.get("frames") != 4 or
            result.get("state_bytes") != len(mem)):
        retained = {
            "actual-frontend.gnst": (state_path, 1024 * 1024),
            "actual-frontend.gnfi": (inputs_path, 1024),
            "actual-frontend.gnfo": (trace_path, 8 * 1024 * 1024),
        }
        for name, (source, maximum) in retained.items():
            try:
                payload = read_private_regular_file(source, maximum)
            except SmokeBlocked:
                continue
            write_private_bytes(work.parent.parent / name, payload, maximum)
        raise SmokeBlocked(
            "continuation-witness",
            "fresh native witness did not prove known-signal continuation",
            diagnostic={key: result.get(key) for key in (
                "outcome", "assertions", "frames", "elapsed_cycles",
                "nonzero_audio_samples", "nonzero_video_bytes", "state_bytes")},
        )
    trace = read_private_regular_file(trace_path, 8 * 1024 * 1024)
    stats = compare_frontend_trace(trace, observations)
    return {"result": result, "trace_sha256": hashlib.sha256(trace).hexdigest(),
            "comparison": stats}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_frontend_audio_capture(path: Path, *, owned_directory: Path,
                                 started_ns: int, finished_ns: int,
                                 maximum_bytes: int = AUDIO_CAPTURE_MAX_BYTES,
                                 _allow_empty: bool = False) -> dict[str, object]:
    """Validate a fresh bounded RetroArch WAV of raw libretro audio callbacks.

    RetroArch v1.22.2 forwards the recorder's input batch before audio flush
    applies mute, resampling, DSP, and device output. The receipt therefore
    binds frontend callback PCM, never device playback or listener audibility.
    """
    if (type(started_ns) is not int or type(finished_ns) is not int or
            started_ns <= 0 or finished_ns < started_ns or
            type(maximum_bytes) is not int or not 44 <= maximum_bytes <= AUDIO_CAPTURE_MAX_BYTES or
            type(_allow_empty) is not bool):
        raise SmokeBlocked("audio-capture", "invalid audio capture bounds")
    root = Path(owned_directory)
    target = Path(path)
    try:
        root_real = root.resolve(strict=True)
        before_path = target.lstat()
        resolved = target.resolve(strict=True)
    except OSError as error:
        raise SmokeBlocked("audio-capture", "frontend audio capture is missing") from error
    if (stat_module.S_ISLNK(before_path.st_mode) or not stat_module.S_ISREG(before_path.st_mode)
            or not resolved.is_relative_to(root_real)
            or before_path.st_size < 44 or before_path.st_size > maximum_bytes
            or not started_ns <= before_path.st_mtime_ns <= finished_ns):
        raise SmokeBlocked("audio-capture", "frontend audio capture is stale, oversized, or outside its owner")
    descriptor = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags)
        before_fd = os.fstat(descriptor)
        if (not stat_module.S_ISREG(before_fd.st_mode) or
                (before_fd.st_dev, before_fd.st_ino, before_fd.st_size, before_fd.st_mtime_ns) !=
                (before_path.st_dev, before_path.st_ino, before_path.st_size, before_path.st_mtime_ns)):
            raise SmokeBlocked("audio-capture", "frontend audio capture changed before read")
        chunks = []
        total = 0
        while total <= maximum_bytes:
            chunk = os.read(descriptor, min(1024 * 1024, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after_fd = os.fstat(descriptor)
        after_path = target.lstat()
        if (total > maximum_bytes or
                (before_fd.st_dev, before_fd.st_ino, before_fd.st_size, before_fd.st_mtime_ns) !=
                (after_fd.st_dev, after_fd.st_ino, after_fd.st_size, after_fd.st_mtime_ns) or
                (after_fd.st_dev, after_fd.st_ino, after_fd.st_size, after_fd.st_mtime_ns) !=
                (after_path.st_dev, after_path.st_ino, after_path.st_size, after_path.st_mtime_ns)):
            raise SmokeBlocked("audio-capture", "frontend audio capture changed during read")
    except OSError as error:
        raise SmokeBlocked("audio-capture", "frontend audio capture could not be read safely") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    encoded = b"".join(chunks)
    container = "riff_wave"
    if (len(encoded) >= 56 and encoded[:8] == b"RIFF\0\0\0\0" and
            encoded[12:24] == b"WAVE\0fmt \0\0\0" and
            encoded[44:52] == b"data\0\0\0\0"):
        # Pinned RetroArch v1.22.2 record/drivers/record_wav.c writes its
        # wav_hdr_t directly: char[5] tags and ABI padding make 56 bytes.
        # Recognize only this exact layout; it is explicitly not standard WAV.
        # https://github.com/libretro/RetroArch/blob/v1.22.2/record/drivers/record_wav.c
        riff_size, = struct.unpack_from("<I", encoded, 8)
        fmt_size, = struct.unpack_from("<I", encoded, 24)
        tag, channels, sample_rate, byte_rate, block, bits = struct.unpack_from(
            "<HHIIHH", encoded, 28)
        data_size, = struct.unpack_from("<I", encoded, 52)
        if (riff_size != len(encoded) - 12 or fmt_size != 16 or tag != 1 or
                channels != 2 or sample_rate != 48000 or byte_rate != 192000 or
                block != 4 or bits != 16 or data_size != len(encoded) - 56 or
                data_size % 4 != 0):
            raise SmokeBlocked("audio-capture", "pinned recorder header is incomplete or unsupported")
        container = "retroarch_v1_22_2_wav_padded56"
        sample_width, compression = 2, "NONE"
        frame_count = data_size // 4
        samples = encoded[56:]
    else:
        if (len(encoded) < 12 or encoded[:4] != b"RIFF" or encoded[8:12] != b"WAVE" or
                struct.unpack_from("<I", encoded, 4)[0] != len(encoded) - 8):
            raise SmokeBlocked("audio-capture", "frontend audio capture is not a complete RIFF/WAVE file")
        try:
            import wave
            with wave.open(io.BytesIO(encoded), "rb") as capture:
                channels = capture.getnchannels()
                sample_width = capture.getsampwidth()
                sample_rate = capture.getframerate()
                frame_count = capture.getnframes()
                compression = capture.getcomptype()
                samples = capture.readframes(frame_count)
        except (EOFError, OSError, wave.Error) as error:
            raise SmokeBlocked("audio-capture", "frontend audio capture is not a complete WAV") from error
    expected_bytes = frame_count * 4
    if (channels != 2 or sample_width != 2 or sample_rate != 48000 or
            compression != "NONE" or frame_count < 0 or
            (frame_count == 0 and not _allow_empty) or len(samples) != expected_bytes):
        raise SmokeBlocked("audio-capture", "frontend audio capture format or frame count is unsupported")
    sample_values = (sample[0] for sample in struct.iter_unpack("<h", samples))
    nonzero_samples = 0
    peak = 0
    for value in sample_values:
        if value:
            nonzero_samples += 1
            peak = max(peak, abs(value))
    if not nonzero_samples and not (_allow_empty and frame_count == 0):
        raise SmokeBlocked("audio-capture", "frontend audio capture is silent")
    return {
        # Empty startup segments are diagnostic candidates, never qualification.
        "status": "empty" if frame_count == 0 else "pass",
        "container": container,
        "stage": "frontend_libretro_audio_callback_pre_flush",
        "format": "pcm_s16le_interleaved_stereo",
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_frames": frame_count,
        "pcm_bytes": len(samples),
        "pcm_sha256": hashlib.sha256(samples).hexdigest(),
        "recording_sha256": hashlib.sha256(encoded).hexdigest(),
        "nonzero_samples": nonzero_samples,
        "peak_sample": peak,
        "capture_bytes": len(encoded),
        "capture_started_ns": started_ns,
        "capture_finished_ns": finished_ns,
        "capture_mtime_ns": after_fd.st_mtime_ns,
    }


def select_frontend_audio_recording(captures: Path, *, started_ns: int,
                                    finished_ns: int) -> dict[str, object]:
    """Require one complete stream; AV reinit may leave an empty startup file."""
    root = Path(captures)
    directory = root / "recordings"
    if directory.is_symlink() or not directory.is_dir():
        raise SmokeBlocked("audio-capture", "owned recorder restart directory is missing")
    entries = []
    for entry in directory.iterdir():
        entries.append(entry)
        if len(entries) > 2:
            raise SmokeBlocked("audio-capture", "recorder restart count exceeds its bound")
    initial = root / "frontend-audio-callback.wav"
    candidates = [initial, *entries]
    total, empty, nonempty = 0, 0, []
    for path in candidates:
        try:
            info = path.lstat()
        except OSError as error:
            raise SmokeBlocked("audio-capture", "owned recording candidate is missing") from error
        if not stat_module.S_ISREG(info.st_mode):
            raise SmokeBlocked("audio-capture", "owned recording candidate is not a regular file")
        total += info.st_size
        if total > AUDIO_CAPTURE_MAX_BYTES:
            raise SmokeBlocked("audio-capture", "combined recordings exceed their output bound")
        result = parse_frontend_audio_capture(
            path, owned_directory=root, started_ns=started_ns,
            finished_ns=finished_ns, _allow_empty=True)
        if result["status"] == "empty":
            if path != initial:
                raise SmokeBlocked("audio-capture", "restarted recording contains no PCM")
            empty += 1
        else:
            nonempty.append({**result, "recording_relative_path": path.relative_to(root).as_posix()})
    if len(nonempty) != 1:
        raise SmokeBlocked("audio-capture", "one complete nonempty recording is required")
    return {**nonempty[0], "startup_empty_recordings": empty}


def stop_owned_frontend_recording(process, keys, timeout: float) -> None:
    """Use the owned frontend's ordinary exit so the recorder finalizes."""
    if type(timeout) not in (int, float) or not 0 < timeout <= 8:
        raise SmokeBlocked("unload", "invalid recording shutdown timeout")
    keys.post_key(53, True)  # Configured Escape: normal runloop shutdown.
    try:
        time.sleep(0.05)
    finally:
        keys.post_key(53, False)
    if reap_frontend(process, timeout) != 0:
        raise SmokeBlocked("unload", "frontend did not finalize recording through normal exit")


def parse_frontend_audio_frames(log_path: Path) -> list[dict[str, object]]:
    """Read opt-in per-frame chip deltas; no sample bytes or hardware-truth claim."""
    try:
        if Path(log_path).is_symlink():
            raise SmokeBlocked("audio-frames", "audio frame log must be owned")
        with Path(log_path).open("rb") as stream:
            encoded = stream.read(MVS_FRONTEND_LOG_LIMIT + 1)
    except OSError as error:
        raise SmokeBlocked("audio-frames", "audio frame log unavailable") from error
    if len(encoded) > MVS_FRONTEND_LOG_LIMIT:
        raise SmokeBlocked("audio-frames", "audio frame log exceeds its bound")
    marker = "glueyneo: MVS audio frame:"
    counters = ("chip_clocks", "fm_key_on_writes", "fm_key_off_writes", "fm_register_writes",
                "ssg_register_writes", "ssg_volume_writes", "adpcm_a_register_writes",
                "adpcm_a_control_writes", "adpcm_a_reads", "adpcm_b_register_writes",
                "adpcm_b_control_writes", "adpcm_b_reads", "native_nonzero_frames")
    rows = []
    text = encoded.decode("utf-8", errors="replace")
    if "glueyneo: MVS audio frame unavailable" in text:
        raise SmokeBlocked("audio-frames", "chip observation unavailable")
    for line in text.splitlines():
        if marker not in line:
            continue
        numbers = line.split(marker, 1)[1].strip().split()
        if (line.count(marker) != 1 or len(numbers) != 18 or
                any(re.fullmatch(r"0|[1-9][0-9]{0,6}", value) is None for value in numbers)):
            raise SmokeBlocked("audio-frames", "malformed chip frame record")
        sequence, mask, cycles, frames, reset, *values = map(int, numbers)
        if (sequence != len(rows) + 1 or sequence > 8192 or mask > 1023 or
                not 202752 - 159 <= cycles <= 202752 + 159 or not 0 < frames <= 812 or
                reset not in (0, 1) or any(value > 1_000_000 for value in values) or
                values[-1] > 100_000):
            raise SmokeBlocked("audio-frames", "inconsistent chip frame record")
        rows.append(dict(sequence=sequence, sampled_mask=mask, elapsed_cycles=cycles,
                         audio_frames=frames, chip=dict(chip_reset=bool(reset), **dict(zip(counters, values)))))
    if not rows:
        raise SmokeBlocked("audio-frames", "audio frame records are missing")
    return rows


def parse_frontend_audio_delivery(log_path: Path) -> dict[str, object]:
    """Read one opt-in adapter total, separately from recorder and device stages."""
    try:
        with Path(log_path).open("rb") as stream:
            encoded = stream.read(MVS_FRONTEND_LOG_LIMIT + 1)
    except OSError as error:
        raise SmokeBlocked("audio-delivery", "adapter audio totals unavailable") from error
    if len(encoded) > MVS_FRONTEND_LOG_LIMIT:
        raise SmokeBlocked("audio-delivery", "adapter audio log exceeds its bound")
    marker = "glueyneo: MVS audio final delivery:"
    lines = [line for line in encoded.decode("utf-8", errors="replace").splitlines() if marker in line]
    if len(lines) != 1 or lines[0].count(marker) != 1:
        raise SmokeBlocked("audio-delivery", "one final adapter audio total is required")
    number = r"(0|[1-9][0-9]{0,6})"
    match = re.search(re.escape(marker) + " generated=" + number +
        " submitted=" + number + " processed=" + number + " discarded=" + number +
        " overreports=" + number + r"$", lines[0])
    if match is None:
        raise SmokeBlocked("audio-delivery", "malformed adapter audio totals")
    generated, submitted, processed, discarded, overreports = map(int, match.groups())
    if (generated > 8192 * 812 or not processed <= submitted <= generated or
            generated != processed + discarded or overreports > 8192):
        raise SmokeBlocked("audio-delivery", "inconsistent adapter audio totals")
    return dict(status="pass", stage="adapter_callback_return_totals",
                generated=generated, submitted=submitted, processed=processed,
                discarded=discarded, overreports=overreports)


def parse_frontend_audio_route(log_path: Path, *, control: str) -> dict[str, object]:
    """Summarize the owned process log without exposing raw host paths."""
    if control not in ("normal", "muted", "disabled"):
        raise SmokeBlocked("audio-route", "unsupported audio route control")
    try:
        info = Path(log_path).stat()
        if not stat_module.S_ISREG(info.st_mode) or info.st_size > MVS_FRONTEND_LOG_LIMIT:
            raise SmokeBlocked("audio-route", "frontend audio route log exceeds its bound")
        with Path(log_path).open("rb") as stream:
            raw = stream.read(MVS_FRONTEND_LOG_LIMIT + 1)
    except OSError as error:
        raise SmokeBlocked("audio-route", "frontend audio route log unavailable") from error
    if len(raw) > MVS_FRONTEND_LOG_LIMIT:
        raise SmokeBlocked("audio-route", "frontend audio route log exceeds its bound")
    text = raw.decode("utf-8", errors="replace")
    driver_match = re.search(
        r"(?i)(?:found audio driver|using audio driver|audio driver)\s*[:=]?\s*[\"']?"
        r"(coreaudio3|coreaudio|null|sdl2?|pulseaudio|alsa|pipewire|wasapi|dsound|xaudio|audioio)\b",
        text,
    )
    driver = driver_match.group(1).lower() if driver_match else "unknown"
    # This driver-owned initialization message is not translated, unlike the
    # generic driver-selection message. Still require the separate started log.
    if driver == "unknown" and re.search(
            r"\[CoreAudio3\] Using buffer size of [1-9][0-9]* bytes: "
            r"\(latency = [0-9]+ ms\)\.", text):
        driver = "coreaudio3"
    started = bool(re.search(r"(?i)started synchronous audio driver|audio driver initialized", text))
    enabled = control != "disabled"
    muted = control == "muted"
    if control == "disabled":
        route_status = "pass" if not started else "fail"
        route_state = "disabled" if not started else "unexpectedly-active"
    elif not enabled:
        route_status, route_state = "unknown", "unknown"
    elif not started or driver in ("unknown", "null"):
        route_status, route_state = "unknown", "unobserved"
    else:
        route_status, route_state = "pass", "active-driver-initialized"
    control_status = ("configured_unverified" if muted else route_status)
    return {
        "status": route_status,
        "control": control,
        "audio_enabled": enabled,
        "mute_configured": muted,
        "driver": driver,
        "driver_initialized": started,
        "route_state": route_state,
        "control_status": control_status,
        "evidence": "launch-config-plus-owned-frontend-stderr",
    }


def frontend_audio_evidence_is_valid(capture: object, route: object, *,
                                     expected_control: str,
                                     delivery: object = None) -> bool:
    """Fail closed on stale/mis-staged PCM or a route inconsistent with its control."""
    if (expected_control not in ("normal", "muted", "disabled") or
            not isinstance(capture, dict) or not isinstance(route, dict)):
        return False
    integer_fields = (
        "sample_rate_hz", "channels", "sample_width_bytes", "sample_frames", "pcm_bytes",
        "nonzero_samples", "peak_sample", "capture_bytes", "capture_started_ns",
        "capture_finished_ns", "capture_mtime_ns",
    )
    if (capture.get("status") != "pass" or
            capture.get("container") not in ("riff_wave", "retroarch_v1_22_2_wav_padded56") or
            capture.get("stage") != "frontend_libretro_audio_callback_pre_flush" or
            capture.get("format") != "pcm_s16le_interleaved_stereo" or
            any(type(capture.get(field)) is not int for field in integer_fields) or
            capture.get("sample_rate_hz") != 48000 or capture.get("channels") != 2 or
            capture.get("sample_width_bytes") != 2 or capture.get("sample_frames") <= 0 or
            capture.get("pcm_bytes") != capture.get("sample_frames") * 4 or
            not 0 < capture.get("nonzero_samples") <= capture.get("sample_frames") * 2 or
            not 0 < capture.get("peak_sample") <= 32768 or
            not capture.get("capture_started_ns") <= capture.get("capture_mtime_ns") <=
                capture.get("capture_finished_ns") or
            not 44 <= capture.get("capture_bytes") <= AUDIO_CAPTURE_MAX_BYTES or
            any(not isinstance(capture.get(field), str) or
                re.fullmatch(r"[0-9a-f]{64}", capture[field]) is None
                for field in ("pcm_sha256", "recording_sha256"))):
        return False
    if (not isinstance(delivery, dict) or delivery.get("status") != "pass" or
            delivery.get("stage") != "adapter_callback_return_totals" or
            any(type(delivery.get(key)) is not int for key in
                ("generated", "submitted", "processed", "discarded", "overreports")) or
            not 0 < delivery["generated"] <= 8192 * 812 or
            delivery["generated"] != delivery["submitted"] or
            delivery["submitted"] != delivery["processed"] or
            capture["sample_frames"] != delivery["processed"] or
            delivery["discarded"] != 0 or delivery["overreports"] != 0):
        return False
    if (route.get("status") != "pass" or route.get("control") != expected_control or
            type(route.get("audio_enabled")) is not bool or
            type(route.get("mute_configured")) is not bool or
            type(route.get("driver_initialized")) is not bool or
            not isinstance(route.get("driver"), str) or
            not isinstance(route.get("route_state"), str)):
        return False
    if expected_control == "disabled":
        return (route["audio_enabled"] is False and route["mute_configured"] is False and
                route["driver_initialized"] is False and route["route_state"] == "disabled" and
                route.get("control_status") == "pass")
    driver_is_active = route["driver_initialized"] and route["driver"] not in ("", "null", "unknown")
    if expected_control == "muted":
        return (route["audio_enabled"] is True and route["mute_configured"] is True and
                route["route_state"] == "active-driver-initialized" and driver_is_active and
                route.get("control_status") == "configured_unverified")
    return (route["audio_enabled"] is True and route["mute_configured"] is False and
            route["route_state"] == "active-driver-initialized" and driver_is_active and
            route.get("control_status") == "pass")


def is_normalized_mvs_bundle(content: bytes) -> bool:
    if (len(content) < 16 or content[:4] != b"GNMV" or
            int.from_bytes(content[8:12], "big") != GNMV_PROFILE_MSX or
            len(content) > GNMV_MAX_BYTES):
        return False
    version = int.from_bytes(content[4:8], "big")
    region_count = int.from_bytes(content[12:16], "big")
    if version == 2:
        expected_roles = GNMV_V2_ROLES
    elif version == 3 and region_count in (7, 8):
        expected_roles = GNMV_V3_REQUIRED_ROLES
        if region_count == 8:
            expected_roles = expected_roles | {7}
    else:
        return False
    if region_count != len(expected_roles) or region_count > GNMV_MAX_REGIONS:
        return False
    cursor = 16
    found: set[int] = set()
    for _ in range(region_count):
        if len(content) - cursor < 12:
            return False
        role = int.from_bytes(content[cursor:cursor + 4], "big")
        size = int.from_bytes(content[cursor + 4:cursor + 12], "big")
        cursor += 12
        if role not in GNMV_REGION_LENGTHS or role in found:
            return False
        if size != GNMV_REGION_LENGTHS[role] or size > len(content) - cursor:
            return False
        cursor += size
        found.add(role)
    return cursor == len(content) and found == expected_roles


def sanitize_diagnostic_text(text: str, *, temporary_root: Path | None = None) -> str:
    # Frontend and crash output is one unstructured value; drop everything
    # from the first private root (in any known form) to its end.
    roots = [Path(__file__).resolve().parents[2]] + ([temporary_root] if temporary_root is not None else [])
    text = private_paths.redact(text, extra_roots=roots)
    if len(text) > DIAGNOSTIC_OUTPUT_LIMIT:
        marker = "\n[diagnostic output truncated]"
        text = text[-(DIAGNOSTIC_OUTPUT_LIMIT - len(marker)):] + marker
    return text.strip()


def public_json(result: dict[str, object]) -> str:
    """Serialize a result for stdout, failing closed if a private root survives."""
    try:
        text = json.dumps(result, sort_keys=True)
    except (TypeError, ValueError, OverflowError):
        return json.dumps({"status": "fail", "reason": "private-report-serialization-failed"},
                          sort_keys=True)
    try:
        private_paths.scan_public_value(result, (Path(__file__).resolve().parents[2],))
    except private_paths.PrivatePathError:
        result["status"] = "fail"
        text = json.dumps({"status": "fail", "reason": "private-path-survived"}, sort_keys=True)
    return text


def private_state_public_receipt(status: object) -> dict[str, str]:
    """Publish only fixed route/status values; identities and diagnostics stay local.

    Do not add fields from the private result here: even serializable hashes,
    nested witness fields, exception names and diagnostic text can identify
    private media, state or captures. The full report is persisted separately.
    """
    if type(status) is not str or status not in ("pass", "fail", "blocked_or_unknown"):
        status = "fail"
    return {"mode": "private-state", "status": status}


PRIVATE_STATE_IDENTITY_FIELDS = frozenset({
    "scene_contract_sha256", "sound_contract_sha256", "schedule_identity",
    "media_identity_sha256", "importer_sha256", "content_sha256",
    "production_core_sha256", "observed_core_sha256", "witness_sha256",
    "retroarch_sha256",
})


def validate_private_state_identity(expected: object, actual: object) -> bool:
    """Require complete, current source and artifact identities for local state evidence."""
    if (not isinstance(expected, dict) or not isinstance(actual, dict) or
            set(expected) != PRIVATE_STATE_IDENTITY_FIELDS or
            set(actual) != PRIVATE_STATE_IDENTITY_FIELDS):
        return False
    if any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
           for value in (*expected.values(), *actual.values())):
        return False
    return expected == actual


def extract_crash_reason(report: str) -> str:
    selected: list[str] = []
    for line in report.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                record = None
            if isinstance(record, dict):
                exception = record.get("exception")
                termination = record.get("termination")
                if isinstance(exception, dict):
                    fields = [str(exception.get(key, "")) for key in ("type", "signal", "subtype")]
                    value = " ".join(field for field in fields if field)
                    if value:
                        selected.append("Exception: " + value)
                if isinstance(termination, dict):
                    fields = [str(termination.get(key, "")) for key in ("namespace", "code", "indicator")]
                    value = " ".join(field for field in fields if field)
                    if value:
                        selected.append("Termination: " + value)
            continue
        if re.search(
            r"(?i)(exception type|termination reason|dyld error message|library not loaded|namespace dyld)",
            stripped,
        ):
            selected.append(stripped)
    if not selected and report.lstrip().startswith("{"):
        for section, label, keys in (
            ("exception", "Exception", ("type", "signal", "subtype")),
            ("termination", "Termination", ("namespace", "code", "indicator")),
        ):
            match = re.search(rf'"{section}"\s*:\s*\{{([^}}]*)\}}', report, re.DOTALL)
            if not match:
                continue
            values: list[str] = []
            for key in keys:
                field = re.search(
                    rf'"{key}"\s*:\s*(?:"((?:\\.|[^"\\])*)"|(-?\d+))',
                    match.group(1),
                )
                if field:
                    values.append(field.group(1) if field.group(1) is not None else field.group(2))
            if values:
                selected.append(f"{label}: " + " ".join(values))
    return sanitize_diagnostic_text("\n".join(dict.fromkeys(selected)))


def build_diagnostic(
    *,
    stage: str,
    return_code: int | None,
    survived_before_screenshot: bool | None,
    output: str,
    temporary_root: Path | None = None,
    crash_report: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "stage": stage,
        "return_code": return_code,
        "survived_before_screenshot": survived_before_screenshot,
        "output": sanitize_diagnostic_text(output, temporary_root=temporary_root),
        "output_available": bool(output.strip()),
    }
    reason = extract_crash_reason(crash_report or "")
    if reason:
        reason = sanitize_diagnostic_text(reason, temporary_root=temporary_root)
    if not reason and crash_report:
        reason = sanitize_diagnostic_text(crash_report, temporary_root=temporary_root)
    record["macos_crash_reason_available"] = bool(reason)
    if reason:
        record["macos_crash_reason"] = reason
    return record


def compare_launch_probes(no_content: dict[str, object], core_content: dict[str, object]) -> str:
    for probe in (no_content, core_content):
        diagnostic = probe.get("diagnostic")
        if isinstance(diagnostic, dict) and diagnostic.get("stage") == "pid-record":
            # A PID record failure says nothing about whether the frontend started (G3WR-03).
            return "diagnostic-pid-record-failed"
    if not bool(no_content.get("survived_window")):
        return "frontend-startup-failed"
    if not bool(core_content.get("survived_window")):
        return "core-or-content-invocation-failed"
    return "both-launch-probes-survived"


PNG_IEND_TRAILER = b"\x00\x00\x00\x00IEND\xaeB`\x82"
SCREENSHOT_STABLE_SECONDS = 0.05
MAX_CAPTURE_DIMENSION = 4096


def select_fresh_screenshot(directory: Path, prior: dict[Path, int]) -> Path | None:
    """Pick the newest new capture that is a complete, no-longer-growing PNG (WR-04)."""
    candidates: list[tuple[int, Path]] = []
    for path in directory.glob("*.png"):
        try:
            stat = path.stat()
            if path in prior and stat.st_mtime_ns <= prior[path]:
                continue
            if stat.st_size < len(PNG_IEND_TRAILER):
                continue
            with path.open("rb") as stream:
                stream.seek(-len(PNG_IEND_TRAILER), os.SEEK_END)
                if stream.read(len(PNG_IEND_TRAILER)) != PNG_IEND_TRAILER:
                    continue
        except OSError:
            continue
        candidates.append((stat.st_mtime_ns, path))
    for _, path in sorted(candidates, reverse=True):
        try:
            first = path.stat()
            time.sleep(SCREENSHOT_STABLE_SECONDS)
            second = path.stat()
        except OSError:
            continue
        if (first.st_size, first.st_mtime_ns) == (second.st_size, second.st_mtime_ns):
            return path
    return None


def read_bounded_text(
    path: Path, limit: int = DIAGNOSTIC_OUTPUT_LIMIT, *, tail: bool = True
) -> str:
    try:
        with path.open("rb") as stream:
            if tail:
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                stream.seek(max(0, size - limit))
            data = stream.read(limit)
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def collect_frontend_output(process_log: Path, frontend_log: Path, temporary_root: Path) -> str:
    process_text = read_bounded_text(process_log, DIAGNOSTIC_OUTPUT_LIMIT // 2)
    frontend_text = read_bounded_text(frontend_log, DIAGNOSTIC_OUTPUT_LIMIT // 2)
    sections = []
    if process_text:
        sections.append("stdout/stderr:\n" + process_text)
    if frontend_text:
        sections.append("RetroArch file log:\n" + frontend_text)
    return sanitize_diagnostic_text("\n".join(sections), temporary_root=temporary_root)


def crash_report_snapshot() -> dict[Path, tuple[int, int]]:
    if sys.platform != "darwin":
        return {}
    reports = Path.home() / "Library" / "Logs" / "DiagnosticReports"
    snapshot: dict[Path, tuple[int, int]] = {}
    try:
        for pattern in ("RetroArch*.crash", "RetroArch*.ips"):
            for path in reports.glob(pattern):
                if path.is_file():
                    stat = path.stat()
                    snapshot[path] = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return snapshot
    return snapshot


def find_recent_crash_reason(
    started_at: float, prior_reports: dict[Path, tuple[int, int]] | None = None
) -> str | None:
    if sys.platform != "darwin":
        return None
    reports = Path.home() / "Library" / "Logs" / "DiagnosticReports"
    candidates: list[tuple[float, Path]] = []
    for pattern in ("RetroArch*.crash", "RetroArch*.ips"):
        try:
            paths = reports.glob(pattern)
            for path in paths:
                try:
                    stat = path.stat()
                except OSError:
                    continue
                identity = (stat.st_mtime_ns, stat.st_size)
                if (path.is_file() and stat.st_mtime >= started_at - 1.0
                        and (prior_reports is None or prior_reports.get(path) != identity)):
                    candidates.append((stat.st_mtime, path))
        except OSError:
            continue
    for _, path in sorted(candidates, reverse=True)[:3]:
        report = read_bounded_text(path, DIAGNOSTIC_OUTPUT_LIMIT, tail=False)
        reason = extract_crash_reason(report)
        if reason:
            return reason
    return None


def wait_for_recent_crash_reason(
    started_at: float,
    prior_reports: dict[Path, tuple[int, int]] | None = None,
    timeout: float = CRASH_REPORT_WAIT_SECONDS,
) -> str | None:
    deadline = time.monotonic() + timeout
    while True:
        reason = find_recent_crash_reason(started_at, prior_reports)
        if reason:
            return reason
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(0.1, remaining))


def decode_png(path: Path) -> tuple[int, int, int, bytes]:
    try:
        return _decode_png(path)
    except (struct.error, zlib.error, IndexError, ValueError, OSError) as error:
        raise SmokeBlocked("video", "frontend screenshot could not be decoded") from error


def recognize_title_capture(path: Path, execute=None) -> str:
    """Use macOS Vision but expose only finite title-recognition tokens."""
    execute = subprocess.run if execute is None else execute
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= TITLE_CAPTURE_MAX_BYTES:
            return "unknown"
        image = decode_png(path)
        if image[:2] != (WIDTH, HEIGHT):
            return "unknown"
        if capture_is_black(image):
            return "fail"
        swift = Path(TITLE_OCR_EXECUTABLE)
        if not swift.is_file() or not os.access(swift, os.X_OK):
            return "unknown"
        environment = dict(TITLE_OCR_ENVIRONMENT)
        environment["GLUEYNEO_TITLE_CAPTURE"] = str(path)
        result = execute(
            [str(swift), "-e", TITLE_OCR_SCRIPT], capture_output=True, text=True,
            check=False, timeout=TITLE_OCR_TIMEOUT_SECONDS, env=environment,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError, SmokeBlocked):
        return "unknown"
    stdout = getattr(result, "stdout", "")
    stderr = getattr(result, "stderr", "")
    if (result.returncode != 0 or not isinstance(stdout, str) or
            not isinstance(stderr, str) or len(stdout) > 128 or len(stderr) > 1024):
        return "unknown"
    token = stdout.strip()
    if token == "metal_slug_title":
        return "pass"
    if token == "known_wrong_title":
        return "fail"
    return "unknown"


def capture_is_black(image: tuple[int, int, int, bytes]) -> bool:
    """Classify only a fully black frame as a definite negative title result."""
    width, height, channels, pixels = image
    if (width <= 0 or height <= 0 or channels not in {3, 4} or
            len(pixels) != width * height * channels):
        return False
    return all(max(pixels[offset:offset + 3]) <= 8
               for offset in range(0, len(pixels), channels))


def title_recognition_outcome(results: list[str]) -> str:
    """Aggregate bounded captures without letting uncertain OCR claim a title."""
    if any(result not in {"pass", "fail", "unknown"} for result in results):
        return "unknown"
    if "pass" in results:
        return "pass"
    if results and all(result == "fail" for result in results):
        return "fail"
    return "unknown"


def mvs_frontend_log_outcome(log_text: object) -> str:
    """Require a load marker and reject any bounded generic runtime failure."""
    if not isinstance(log_text, str):
        return "unknown"
    lowered = log_text.lower()
    if any(marker.lower() in lowered for marker in MVS_FRONTEND_FAILURE_MARKERS):
        return "fail"
    if MVS_FRONTEND_LOAD_MARKER.lower() in lowered:
        return "pass"
    return "unknown"


MVS_OBSERVATION_PREFIX = "glueyneo: mvs "
MVS_OBSERVATION_LIMIT = 256
MVS_FRONTEND_LOG_LIMIT = 16 * 1024 * 1024
MVS_MASK_KEY_CODES = {1: 18, 2: 19, 4: 126, 8: 125,
                      16: 123, 32: 124, 64: 6, 128: 7, 256: 0, 512: 1}


class BoundedFrontendLog:
    """Drain owned stderr continuously, retaining at most one finite prefix.

    stdout is mirrored RetroArch noise and goes to DEVNULL. Overflow is latched
    independently of protocol parsing and remains a failure after child exit.
    The reader is nonblocking so even an inherited writer cannot strand cleanup.
    """
    def __init__(self, stream, *, limit: int | None = None):
        self.stream = stream
        self.limit = MVS_FRONTEND_LOG_LIMIT if limit is None else limit
        self.reader, self.writer = os.pipe()
        os.set_blocking(self.reader, False)
        self.stop = threading.Event()
        self.exceeded = threading.Event()
        self.failed = threading.Event()
        self.thread = threading.Thread(target=self._pump, name="frontend-stderr-pump")

    def __enter__(self):
        self.thread.start()
        return self

    def close_writer(self):
        if self.writer is not None:
            os.close(self.writer)
            self.writer = None

    def _pump(self):
        retained = 0
        try:
            while not self.stop.is_set():
                try:
                    chunk = os.read(self.reader, 64 * 1024)
                except BlockingIOError:
                    self.stop.wait(0.005)
                    continue
                if not chunk:
                    break
                keep = min(len(chunk), self.limit - retained)
                if keep:
                    self.stream.write(chunk[:keep])
                    self.stream.flush()  # live authoritative observation reader
                    retained += keep
                if keep < len(chunk):
                    self.exceeded.set()
        except (OSError, ValueError):
            self.failed.set()
        finally:
            os.close(self.reader)

    def finish(self):
        self.close_writer()
        # The caller first sweeps the owned group. A writer that nevertheless
        # remains open is an explicit failure, never an unbounded thread join.
        self.thread.join(1.0)
        if self.thread.is_alive():
            self.failed.set()
            self.stop.set()
            self.thread.join()

    def check(self):
        if self.exceeded.is_set():
            raise SmokeBlocked("observations", "frontend log output budget exhausted")
        if self.failed.is_set():
            raise SmokeBlocked("observations", "frontend log pump failed or did not close")

    def __exit__(self, *_exc):
        self.finish()


def parse_mvs_input_observations(log_text: str, *, invocation_id: str,
                                 expected_invocation_id: str | None = None,
                                 complete: bool = True) -> list[dict[str, object]]:
    """Parse one owned invocation's bounded protocol; return private records.

    Host identity is bound by the fresh log owner, never by guest-provided text.
    Partial trailing lines are allowed only while collecting an append-only log.
    """
    if (not isinstance(log_text, str) or not isinstance(invocation_id, str)
            or not invocation_id or len(invocation_id) > 128
            or (expected_invocation_id is not None and invocation_id != expected_invocation_id)
            or type(complete) is not bool):
        raise SmokeBlocked("observations", "invalid observation invocation")
    if mvs_frontend_log_outcome(log_text) == "fail":
        raise SmokeBlocked("observations", "MVS runtime failed during observations")
    lines = log_text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        if complete and MVS_OBSERVATION_PREFIX in lines[-1]:
            raise SmokeBlocked("observations", "truncated observation record")
        lines.pop()
    records: list[dict[str, object]] = []
    observation_bytes = 0
    sample = video = cycles = mask = last_video_sample = 0
    sampled = False
    events: set[str] = set()
    for line in lines:
        if MVS_OBSERVATION_PREFIX not in line:
            continue
        payload = line[line.index(MVS_OBSERVATION_PREFIX):]
        observation_bytes += len(payload.encode("utf-8"))
        if observation_bytes > DIAGNOSTIC_OUTPUT_LIMIT or len(records) >= MVS_OBSERVATION_LIMIT:
            raise SmokeBlocked("observations", "observation collection budget exhausted")
        match = re.fullmatch(r"glueyneo: mvs ([BSVRPX]) (0|[1-9][0-9]{0,19}) (0|[1-9][0-9]{0,3}) (0|[1-9][0-9]{0,19}) (0|[1-9][0-9]{0,19})\n", payload)
        if match is None:
            raise SmokeBlocked("observations", "malformed observation record")
        kind = match[1]
        current_sample, current_mask, current_video, current_cycles = map(int, match.groups()[1:])
        if max(current_sample, current_video, current_cycles) > (1 << 64) - 1 or current_mask > 1023:
            raise SmokeBlocked("observations", "observation integer exceeds limit")
        if not records:
            if kind != "B" or any((current_sample, current_mask, current_video, current_cycles)):
                raise SmokeBlocked("observations", "missing initial observation begin")
        elif kind == "B":
            raise SmokeBlocked("observations", "duplicate or reset observation begin")
        elif kind == "X":
            raise SmokeBlocked("observations", "observation emission budget exhausted")
        else:
            if current_sample < sample or current_video < video or current_cycles < cycles:
                raise SmokeBlocked("observations", "reordered observation progress")
            if kind == "S":
                if current_sample <= sample:
                    raise SmokeBlocked("observations", "reordered sampled input")
                if sampled and current_mask == mask:
                    raise SmokeBlocked("observations", "duplicate sampled input")
                sampled = True
            elif (not sampled or current_mask != mask):
                raise SmokeBlocked("observations", "video missing its sampled input")
            if kind == "V":
                if current_sample <= last_video_sample or current_video <= video or current_cycles <= cycles:
                    raise SmokeBlocked("observations", "duplicate successful video")
                last_video_sample = current_sample
            elif kind in ("R", "P"):
                if (kind in events or current_video == 0 or current_video != video
                        or current_cycles != cycles or current_sample != sample
                        or sample != last_video_sample):
                    raise SmokeBlocked("observations", "invalid readiness observation")
                events.add(kind)
        sample, mask, video, cycles = current_sample, current_mask, current_video, current_cycles
        records.append(dict(event_kind=kind, sample_sequence=sample, sampled_mask=mask,
                            successful_video_sequence=video, executed_cycles=cycles,
                            invocation_id=invocation_id))
    if complete and not records:
        raise SmokeBlocked("observations", "missing initial observation begin")
    return records


def _validated_observation_records(records: object, invocation_id: str) -> list[dict[str, object]]:
    if not isinstance(records, list) or not records or len(records) > MVS_OBSERVATION_LIMIT:
        raise SmokeBlocked("observations", "missing observation chain")
    lines = []
    keys = ("sample_sequence", "sampled_mask", "successful_video_sequence", "executed_cycles")
    for record in records:
        if (not isinstance(record, dict) or record.get("invocation_id") != invocation_id
                or any(type(record.get(key)) is not int for key in keys)
                or record.get("event_kind") not in ("B", "S", "V", "R", "P", "X")):
            raise SmokeBlocked("observations", "invalid or stale observation chain")
        lines.append("glueyneo: mvs " + record["event_kind"] + " " +
                     " ".join(str(record[key]) for key in keys) + "\n")
    return parse_mvs_input_observations("".join(lines), invocation_id=invocation_id)


def bind_active_scene_capture(before: list[dict[str, object]], after: list[dict[str, object]], *,
                              invocation_id: str, expected_mask: int,
                              capture_sha256: str) -> dict[str, object]:
    """Bind a fresh stable software capture to a conservative callback interval.

    ``before`` is fully drained immediately before F8, ``after`` after the fresh
    PNG completed. The caller owns freshness/geometry checks. No exact frame is
    claimed: the screenshot may land anywhere between the two video records. The upper
    endpoint is the latest fully drained callback after PNG completion.
    """
    if type(expected_mask) is not int or not 0 <= expected_mask <= 1023 or not isinstance(capture_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", capture_sha256) is None:
        raise SmokeBlocked("observations", "invalid capture identity or mask")
    before = _validated_observation_records(before, invocation_id)
    after = _validated_observation_records(after, invocation_id)
    if after[:len(before)] != before:
        raise SmokeBlocked("observations", "capture observation chain was replaced")
    videos = [record for record in before if record["event_kind"] == "V"]
    later = [record for record in after[len(before):] if record["event_kind"] == "V"]
    if not videos or not later:
        raise SmokeBlocked("observations", "capture lacks progressing successful video")
    lower, upper = videos[-1], later[-1]
    relevant = after[before.index(lower):]
    if any(record["sampled_mask"] != expected_mask for record in relevant):
        raise SmokeBlocked("observations", "capture interval has wrong or released input")
    return dict(invocation_id=invocation_id, capture_sha256=capture_sha256,
                sampled_mask=expected_mask,
                successful_video_interval=[lower["successful_video_sequence"], upper["successful_video_sequence"]],
                exact_frame="unknown")


class MVSObservationCollector:
    """Drain one fresh owned log, bounded independently of unrelated log noise.

    Construct before launching with a missing or empty log. Call drain() before
    F8 and after its fresh PNG is complete; preserve records in private evidence.
    """
    def __init__(self, process, log: Path, invocation_id: str):
        if log.exists() and log.stat().st_size != 0:
            raise SmokeBlocked("observations", "observation log is not fresh")
        if not isinstance(invocation_id, str) or not invocation_id or len(invocation_id) > 128:
            raise SmokeBlocked("observations", "invalid observation invocation")
        self.process, self.log, self.invocation_id = process, log, invocation_id
        self.log_guard = None
        self.offset = 0
        self.identity = None
        self.pending = b""
        self.protocol = ""
        self.records: list[dict[str, object]] = []
        self.expected_mask: int | None = None
        self.previous_mask: int | None = None
        self.transition_seen = False

    def expect_mask(self, mask: int) -> None:
        """Allow one intentional old-to-new transition, rejecting other samples.

        Drain the old segment before calling, then post the requested key changes.
        Initial neutral expectation may be set before the process is launched.
        """
        if type(mask) is not int or not 0 <= mask <= 1023:
            raise SmokeBlocked("observations", "invalid expected input mask")
        self.previous_mask = self.expected_mask
        self.expected_mask = mask
        self.transition_seen = self.previous_mask == mask

    def drain(self) -> list[dict[str, object]]:
        """Drain all current backlog before readiness; later failures win."""
        if self.log_guard is not None:
            self.log_guard.check()
        if frontend_exited(self.process):
            raise SmokeBlocked("observations", "frontend exited before capture evidence")
        try:
            with self.log.open("rb") as stream:
                stat = os.fstat(stream.fileno())
                identity = (stat.st_dev, stat.st_ino)
                if self.identity is not None and self.identity != identity or stat.st_size < self.offset:
                    raise SmokeBlocked("observations", "observation log replaced or truncated")
                self.identity = identity
                stream.seek(self.offset)
                while True:
                    chunk = stream.read(64 * 1024)
                    self.offset += len(chunk)
                    if self.offset > MVS_FRONTEND_LOG_LIMIT:
                        raise SmokeBlocked("observations", "frontend log scan budget exhausted")
                    data = self.pending + chunk
                    # Keep incomplete log lines bounded, including unrelated noise.
                    lines = data.split(b"\n")
                    self.pending = lines.pop()
                    if len(self.pending) > DIAGNOSTIC_OUTPUT_LIMIT:
                        raise SmokeBlocked("observations", "observation line budget exhausted")
                    for line in lines:
                        text = line.decode("utf-8", errors="replace") + "\n"
                        if mvs_frontend_log_outcome(text) == "fail":
                            raise SmokeBlocked("observations", "MVS runtime failed during observations")
                        if MVS_OBSERVATION_PREFIX in text:
                            self.protocol += text[text.index(MVS_OBSERVATION_PREFIX):]
                            if len(self.protocol.encode("utf-8")) > DIAGNOSTIC_OUTPUT_LIMIT:
                                raise SmokeBlocked("observations", "observation collection budget exhausted")
                    if len(chunk) < 64 * 1024:
                        break
        except FileNotFoundError:
            if self.offset:
                raise SmokeBlocked("observations", "observation log disappeared")
        if self.pending and (MVS_OBSERVATION_PREFIX.encode() in self.pending or any(marker.encode() in self.pending for marker in MVS_FRONTEND_FAILURE_MARKERS)):
            raise SmokeBlocked("observations", "truncated observation or failure record")
        previous_count = len(self.records)
        self.records = parse_mvs_input_observations(self.protocol, invocation_id=self.invocation_id, complete=False)
        if self.expected_mask is not None:
            for record in self.records[previous_count:]:
                if record["event_kind"] == "B":
                    continue
                mask = record["sampled_mask"]
                if mask == self.expected_mask:
                    self.transition_seen = True
                elif self.transition_seen or mask != self.previous_mask:
                    raise SmokeBlocked("observations", "unexpected sampled input mask")
        if frontend_exited(self.process):
            raise SmokeBlocked("observations", "frontend exited before capture evidence")
        return [dict(record) for record in self.records]

    def wait_for_video(self, target: int, expected_mask: int, timeout: float) -> list[dict[str, object]]:
        if type(target) is not int or target < 1 or type(expected_mask) is not int or not 0 <= expected_mask <= 1023 or not 0 <= timeout <= 120:
            raise SmokeBlocked("observations", "invalid observation wait bound")
        deadline = time.monotonic() + timeout
        while True:
            records = self.drain()
            videos = [record for record in records if record["event_kind"] == "V"]
            if videos and videos[-1]["successful_video_sequence"] >= target and videos[-1]["sampled_mask"] == expected_mask and records[-1]["sampled_mask"] == expected_mask:
                return records
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SmokeBlocked("observations", "sampled video observation timed out")
            time.sleep(min(0.005, remaining))


def wait_for_mvs_video_checkpoint(process, log: Path, timeout: float) -> None:
    """Wait for successful guest frames, never mistake boot blanking for title."""
    deadline = time.monotonic() + timeout
    offset = 0
    overlap = b""
    checkpoint_seen = False
    # Keep markers spanning reads, without retaining an unbounded log or line.
    marker_bytes = max(len(marker.encode("utf-8")) for marker in (
        MVS_VIDEO_CHECKPOINT_MARKER, *MVS_FRONTEND_FAILURE_MARKERS))
    chunk_size = 64 * 1024
    while True:
        if frontend_exited(process):
            raise SmokeBlocked("video", "frontend exited before video checkpoint")
        try:
            # The invocation owns a fresh append-only log. Advance through it;
            # rereading a fixed prefix would hide later readiness/fault markers.
            with log.open("rb") as stream:
                stream.seek(offset)
                chunk = stream.read(chunk_size)
        except FileNotFoundError:
            chunk = b""
        offset += len(chunk)
        observed = overlap + chunk
        text = observed.decode("utf-8", errors="replace")
        overlap = observed[-(marker_bytes - 1):]
        if mvs_frontend_log_outcome(text) == "fail":
            raise SmokeBlocked("video", "MVS runtime failed before video checkpoint")
        checkpoint_seen = checkpoint_seen or MVS_VIDEO_CHECKPOINT_MARKER in text
        # Drain the current backlog before accepting readiness, so a fault in
        # the next chunk still takes precedence over an earlier checkpoint.
        if checkpoint_seen and len(chunk) < chunk_size:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SmokeBlocked("video", "MVS video checkpoint timed out")
        if len(chunk) < chunk_size:
            time.sleep(min(0.05, remaining))


def retain_frontend_logs(log: Path, process_log: Path, process_log_stream,
                         capture_dir: Path) -> tuple[str, list[str], list[str]]:
    """Retain bounded prefixes; any truncated log is an explicit failure.

    This also serves the ordinary smoke lane, whose existing files may already
    exceed the limit on early exit. Never read or copy such files wholesale.
    """
    paths: list[str] = []
    digests: list[str] = []
    outcome = "unknown"
    oversized = False
    marker_bytes = max(len(marker.encode()) for marker in
                       (MVS_FRONTEND_LOAD_MARKER, *MVS_FRONTEND_FAILURE_MARKERS))
    try:
        process_log_stream.flush()
        for source, destination in (
                (log, capture_dir / "retroarch-private.log"),
                (process_log, capture_dir / "frontend-process-private.log")):
            if destination.exists() or destination.is_symlink() or not source.is_file():
                return "fail" if oversized else "unknown", paths, digests
            retained = 0
            overlap = b""
            with source.open("rb") as reader, destination.open("xb") as writer:
                while True:
                    chunk = reader.read(min(64 * 1024, MVS_FRONTEND_LOG_LIMIT - retained + 1))
                    if not chunk:
                        break
                    keep = min(len(chunk), MVS_FRONTEND_LOG_LIMIT - retained)
                    writer.write(chunk[:keep])
                    retained += keep
                    if source == log:
                        observed = overlap + chunk[:keep]
                        status = mvs_frontend_log_outcome(observed.decode("utf-8", errors="replace"))
                        if status == "fail" or outcome == "unknown":
                            outcome = status
                        overlap = observed[-(marker_bytes - 1):]
                    if keep < len(chunk):
                        oversized = True
                        break
            paths.append(destination.as_posix())
            digests.append(sha256(destination))
        return "fail" if oversized else outcome, paths, digests
    except (OSError, UnicodeError):
        return "fail" if oversized else "unknown", paths, digests


def frontend_acceptance_outcome(*, exited_cleanly: bool,
                                capture_geometry_ok: bool,
                                log_outcome: str) -> str:
    if log_outcome == "fail" or not exited_cleanly or not capture_geometry_ok:
        return "fail"
    if log_outcome == "pass":
        return "pass"
    return "unknown"


def _decode_png(path: Path) -> tuple[int, int, int, bytes]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SmokeBlocked("video", "RetroArch screenshot is not a PNG")
    offset = 8
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        if length > len(data) - offset - 12:
            raise SmokeBlocked("video", "PNG chunk is truncated")
        chunk = data[offset + 8 : offset + 8 + length]
        offset += length + 12
        if kind == b"IHDR":
            if length != 13:
                raise SmokeBlocked("video", "PNG header is malformed")
            width, height, bit_depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", chunk)
            )
            if compression != 0 or filtering != 0:
                raise SmokeBlocked("video", "PNG uses unsupported compression metadata")
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
    if width is None or height is None or bit_depth != 8 or interlace != 0:
        raise SmokeBlocked("video", "PNG format is outside the bounded decoder")
    if not (0 < width <= MAX_CAPTURE_DIMENSION and 0 < height <= MAX_CAPTURE_DIMENSION):
        raise SmokeBlocked("video", "PNG dimensions are outside the bounded decoder")
    channels = {2: 3, 6: 4}.get(color_type)
    if channels is None:
        raise SmokeBlocked("video", "PNG is not RGB or RGBA")
    bpp = channels
    stride = width * bpp
    expected = height * (stride + 1)
    inflater = zlib.decompressobj()
    raw = inflater.decompress(bytes(compressed), expected + 1)  # bounded: never inflate past expected
    if (len(raw) != expected or inflater.unconsumed_tail
            or not inflater.eof or inflater.unused_data):
        raise SmokeBlocked("video", "PNG has an unexpected decoded byte count")
    pixels = bytearray(height * stride)
    source = 0
    for y in range(height):
        filter_type = raw[source]
        source += 1
        row_start = y * stride
        for x in range(stride):
            value = raw[source + x]
            left = pixels[row_start + x - bpp] if x >= bpp else 0
            above = pixels[row_start - stride + x] if y else 0
            upper_left = pixels[row_start - stride + x - bpp] if y and x >= bpp else 0
            if filter_type == 1:
                value += left
            elif filter_type == 2:
                value += above
            elif filter_type == 3:
                value += (left + above) // 2
            elif filter_type == 4:
                estimate = left + above - upper_left
                distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
                predictor = left if distances[0] <= min(distances[1:]) else (
                    above if distances[1] <= distances[2] else upper_left
                )
                value += predictor
            elif filter_type != 0:
                raise SmokeBlocked("video", "PNG uses an unknown row filter")
            pixels[row_start + x] = value & 0xFF
        source += stride
    return width, height, channels, bytes(pixels)


def rgb_at(image: tuple[int, int, int, bytes], x: int, y: int) -> tuple[int, int, int]:
    width, height, channels, pixels = image
    if x < 0 or y < 0 or x >= width or y >= height:
        return (-1, -1, -1)
    offset = (y * width + x) * channels
    return tuple(pixels[offset : offset + 3])  # type: ignore[return-value]


def find_marker(image: tuple[int, int, int, bytes]) -> tuple[int, int, int]:
    """Find the solid 8x8 white fixture tile over its black backdrop."""
    width, height, _, pixels = image
    candidates: list[tuple[int, int, int]] = []
    for scale in range(1, 9):
        side = scale * 8
        for y in range(1, height - side):
            for x in range(1, width - side):
                if rgb_at(image, x, y) != (255, 255, 255):
                    continue
                if rgb_at(image, x - 1, y + side // 2) != (0, 0, 0):
                    continue
                if rgb_at(image, x + side, y + side // 2) != (0, 0, 0):
                    continue
                if rgb_at(image, x + side // 2, y - 1) != (0, 0, 0):
                    continue
                if rgb_at(image, x + side // 2, y + side) != (0, 0, 0):
                    continue
                if any(
                    rgb_at(image, x + dx, y + dy) != (255, 255, 255)
                    for dy in range(side)
                    for dx in range(side)
                ):
                    continue
                candidates.append((x, y, scale))
    if not candidates:
        raise SmokeBlocked("video", "visible 8x8 guest marker on black backdrop was not found")
    if len(candidates) != 1:
        raise SmokeBlocked("video", "semantic marker inspection was ambiguous")
    return candidates[0]


def request_screenshot(process: subprocess.Popen[bytes], directory: Path,
                       prior: dict[Path, int], timeout: float) -> Path:
    if frontend_exited(process):
        raise SmokeBlocked("first-screenshot", f"RetroArch exited before screenshot (status {frontend_returncode(process)})")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # A hotkey sent before the window and frame loop are ready is dropped,
        # so repeat the request at a bounded interval until a capture appears.
        if frontend_exited(process):
            raise SmokeBlocked("first-screenshot", f"RetroArch exited before screenshot (status {frontend_returncode(process)})")
        inject_key(SCREENSHOT_KEY_CODE)
        retry_at = min(deadline, time.monotonic() + SCREENSHOT_RETRY_SECONDS)
        while time.monotonic() < retry_at:
            fresh = select_fresh_screenshot(directory, prior)
            if fresh is not None:
                return fresh
            time.sleep(0.1)
    raise SmokeBlocked("video", "RetroArch did not create a software-video screenshot")


def _keyboard_services():
    import ctypes
    services = ctypes.CDLL(APPLICATION_SERVICES)
    services.CGPreflightPostEventAccess.restype = ctypes.c_bool
    services.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    services.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    services.CGEventPost.restype = None
    services.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    services.CFRelease.restype = None
    services.CFRelease.argtypes = [ctypes.c_void_p]
    if not services.CGPreflightPostEventAccess():
        raise OSError("macOS denied keyboard event posting")
    return services


def _mouse_services():
    services = ctypes.CDLL(APPLICATION_SERVICES)
    services.CGPreflightPostEventAccess.restype = ctypes.c_bool
    services.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    services.CGEventCreateMouseEvent.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, _CGPoint, ctypes.c_uint32,
    ]
    services.CGEventGetLocation.restype = _CGPoint
    services.CGEventGetLocation.argtypes = [ctypes.c_void_p]
    services.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    services.CGEventPost.restype = None
    services.CFRelease.argtypes = [ctypes.c_void_p]
    services.CFRelease.restype = None
    if not services.CGPreflightPostEventAccess():
        raise OSError("macOS denied mouse event posting")
    return services


def current_global_mouse_location() -> dict[str, object]:
    """Read AppKit's current pointer position and convert it to Quartz space."""
    script = (
        'ObjC.import("AppKit"); ObjC.import("CoreGraphics"); '
        'var p=$.NSEvent.mouseLocation; var b=$.CGDisplayBounds($.CGMainDisplayID()); '
        'console.log("GLUEYNEO_MOUSE_LOCATION="+p.x+","+p.y+","+b.size.height);'
    )
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-l", "JavaScript", "-e", script],
            check=False, capture_output=True, text=True,
            timeout=POINTER_READBACK_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timed-out"}
    except OSError as error:
        return {"status": "unavailable", "error_type": type(error).__name__}
    # JXA's `console.log` is emitted on stderr by osascript. The probe emits a
    # single line, so accept that channel when stdout is empty while still
    # rejecting any extra diagnostics or malformed response.
    output = result.stdout.strip() if result.stdout.strip() else result.stderr.strip()
    match = re.fullmatch(
        r"GLUEYNEO_MOUSE_LOCATION=(-?\d+(?:\.\d+)?),"
        r"(-?\d+(?:\.\d+)?),(\d+(?:\.\d+)?)",
        output,
    )
    if result.returncode != 0 or match is None:
        return {"status": "unavailable", "return_code": result.returncode,
                "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
                "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest()}
    appkit_x, appkit_y, main_height = (float(value) for value in match.groups())
    if (not all(math.isfinite(value) for value in (appkit_x, appkit_y, main_height)) or
            main_height <= 0):
        return {"status": "invalid-readback"}
    return {"status": "read", "appkit_lower_left": [appkit_x, appkit_y],
            "main_display_height": main_height,
            "quartz_global": [appkit_x, main_height - appkit_y]}


def post_owned_mouse_click(pid: int, x: int, y: int) -> dict[str, object]:
    """Post and read back a global left click while its intended process is frontmost."""
    if (type(pid) is not int or pid <= 0 or
            type(x) is not int or type(y) is not int):
        raise ValueError("invalid owned mouse target")
    if frontmost_pid() != pid:
        raise SmokeBlocked("input", "owned RetroArch is not frontmost for menu dismissal")
    services = _mouse_services()
    point = _CGPoint(float(x), float(y))
    event_locations: list[list[float]] = []
    for event_type in (CG_LEFT_MOUSE_DOWN, CG_LEFT_MOUSE_UP):
        event = services.CGEventCreateMouseEvent(
            None, event_type, point, CG_LEFT_MOUSE_BUTTON)
        if not event:
            raise OSError("macOS could not create an owned mouse event")
        try:
            services.CGEventPost(CG_HID_EVENT_TAP, event)
            location = services.CGEventGetLocation(event)
            if (location.x != point.x or location.y != point.y):
                raise SmokeBlocked(
                    "input", "posted mouse event location differs from the requested global point",
                    diagnostic={"requested_global": [x, y],
                                "event_global": [location.x, location.y]})
            event_locations.append([location.x, location.y])
        finally:
            services.CFRelease(event)
    pointer_readback = current_global_mouse_location()
    owned_frontmost_after_click = frontmost_pid() == pid
    if not owned_frontmost_after_click:
        raise SmokeBlocked(
            "input", "RetroArch lost foreground after the owned mouse click",
            diagnostic={"requested_global": [x, y],
                        "event_locations_global": event_locations,
                        "pointer_readback": pointer_readback,
                        "owned_frontmost_after_click": False},
        )
    quartz_pointer = (pointer_readback.get("quartz_global")
                      if isinstance(pointer_readback, dict) else None)
    pointer_matches_requested_global = (
        isinstance(pointer_readback, dict) and pointer_readback.get("status") == "read" and
        isinstance(quartz_pointer, (list, tuple)) and len(quartz_pointer) == 2 and
        all(type(value) in (int, float) and math.isfinite(value)
            for value in quartz_pointer) and
        abs(float(quartz_pointer[0]) - x) <= 1.0 and
        abs(float(quartz_pointer[1]) - y) <= 1.0
    )
    if not pointer_matches_requested_global:
        raise SmokeBlocked(
            "input", "system pointer did not confirm the owned global click location",
            diagnostic={"requested_global": [x, y],
                        "event_locations_global": event_locations,
                        "pointer_readback": pointer_readback,
                        "owned_frontmost_after_click": True},
        )
    return {"event_locations_global": event_locations,
            "pointer_readback": pointer_readback,
            "owned_frontmost_after_click": True,
            "pointer_matches_requested_global": True}


def window_relative_point_to_global(
        point: tuple[int, int], window_position: tuple[int, int],
        window_size: tuple[int, int]) -> tuple[int, int]:
    """Map an AX window-local point into Quartz global screen coordinates.

    Accessibility positions use the global screen coordinate space with the
    menu-bar display at the origin. Quartz mouse events use that same global
    space, so this transform is translation only; the size validates that the
    local point belongs to the captured window and must not be used to scale it.
    """
    pairs = (point, window_position, window_size)
    if any(type(pair) is not tuple or len(pair) != 2 or
           any(type(value) is not int for value in pair) for pair in pairs):
        raise ValueError("window mapping requires integer coordinate pairs")
    local_x, local_y = point
    origin_x, origin_y = window_position
    width, height = window_size
    if width <= 0 or height <= 0 or not (0 <= local_x < width and 0 <= local_y < height):
        raise ValueError("window-local point is outside the captured window")
    return origin_x + local_x, origin_y + local_y


def _active_scene_process_readbacks(process, *, foreground_pid: int | None = None) -> dict[str, object]:
    """Collect independent local PIDs without changing foreground ownership."""
    pid = getattr(process, "pid", None) if process is not None else None
    if type(pid) is not int or pid <= 0:
        pid = None
    if foreground_pid is None:
        try:
            foreground = frontmost_pid()
            foreground_status = "available"
        except SmokeBlocked:
            foreground = None
            foreground_status = "unavailable"
    else:
        foreground = foreground_pid
        foreground_status = "available"
    try:
        retroarch_pids = sorted(running_retroarch_pids())
        retroarch_status = "available"
    except SmokeBlocked:
        retroarch_pids = None
        retroarch_status = "unavailable"
    try:
        exited = _exited_unreaped(process) if process is not None else None
    except (OSError, TypeError, AttributeError):
        exited = None
    return {"owned_pid": pid, "owned_process_exited": exited,
            "foreground_pid": foreground, "foreground_readback": foreground_status,
            "retroarch_pids": retroarch_pids,
            "retroarch_process_readback": retroarch_status,
            "foreground_is_owned": (foreground == pid)
            if foreground is not None and pid is not None else None,
            "owned_pid_present": (pid in retroarch_pids)
            if pid is not None and retroarch_pids is not None else None}


def preflight_keyboard_posting(*, process=None) -> None:
    """Check posting authority before focusing or holding any input."""
    try:
        _keyboard_services()
    except (OSError, AttributeError) as error:
        blocked = SmokeBlocked("input", "macOS could not inject frontend keyboard input")
        blocked.diagnostic = {"preactivation_readbacks":
                              _active_scene_process_readbacks(process)}
        raise blocked from error


def post_key_transition(key_code: int, down: bool, *, pid: int | None = None) -> None:
    """Post one key transition without focus changes or timing sleeps."""
    if type(key_code) is not int or not 0 <= key_code <= 127 or type(down) is not bool:
        raise ValueError("invalid keyboard transition")
    services = _keyboard_services()
    event = services.CGEventCreateKeyboardEvent(None, key_code, down)
    if not event:
        raise OSError("macOS could not create a keyboard event")
    try:
        if pid is None:
            services.CGEventPost(CG_HID_EVENT_TAP, event)
        else:
            import ctypes
            if type(pid) is not int or pid <= 0:
                raise ValueError("invalid keyboard target")
            services.CGEventPostToPid.argtypes = [ctypes.c_int, ctypes.c_void_p]
            services.CGEventPostToPid.restype = None
            services.CGEventPostToPid(pid, event)
    finally:
        services.CFRelease(event)


def post_held_key(key_code: int, hold: float) -> None:
    """Post keyDown and guarantee keyUp even if the bounded hold is interrupted."""
    post_key_transition(key_code, True)
    try:
        time.sleep(hold)
    finally:
        post_key_transition(key_code, False)


class HeldMVSKeys:
    """Hold complete Classic masks while the caller polls sampled video.

    Use inside the owned frontend invocation. Enter preflights posting; the first
    guest key after readiness acquires foreground ownership. Every press rechecks
    ownership and targets that PID. Exit releases every key, including after
    polling/capture errors.
    """
    def __init__(self, process):
        self.process = process
        self.held: set[int] = set()
        self.observation_burst = False
        self.preactivation_readbacks: dict[str, object] | None = None

    def __enter__(self):
        if frontend_exited(self.process):
            raise SmokeBlocked("input", "frontend exited before input")
        if (getattr(self.process, "_glueyneo_require_guest_ready", False) and
                not getattr(self.process, "_glueyneo_guest_ready", False)):
            raise SmokeBlocked("input", "owned frontend guest startup readiness was not established")
        preflight_keyboard_posting(process=self.process)
        # Wait for the guest-ready callback before activating the newly launched
        # frontend. Its process can exist before macOS accepts it as foreground.
        return self

    def post_key(self, key: int, down: bool) -> None:
        if frontend_exited(self.process):
            if down:
                raise SmokeBlocked("input", "frontend exited before owned input")
            return  # Never address a PID after its child has exited.
        if down:
            try:
                foreground = frontmost_pid()
            except SmokeBlocked as error:
                readbacks = _active_scene_process_readbacks(self.process)
                self.preactivation_readbacks = readbacks
                error.diagnostic = {"preactivation_readbacks": readbacks}
                raise
        else:
            foreground = None
        if down and foreground != self.process.pid:
            readbacks = _active_scene_process_readbacks(
                self.process, foreground_pid=foreground)
            self.preactivation_readbacks = readbacks
            try:
                focus_owned_frontend(self.process)
            except SmokeBlocked as error:
                error.diagnostic = {"preactivation_readbacks": readbacks}
                raise
            # Cocoa may clear its keyboard state on resigning active. Reassert
            # the complete held state after reacquisition, including diagnostic L3.
            for held in sorted(self.held - {key}):
                post_key_transition(held, False, pid=self.process.pid)
                post_key_transition(held, True, pid=self.process.pid)
        post_key_transition(key, down, pid=self.process.pid)

    def set_mask(self, mask: int) -> None:
        if type(mask) is not int or not 0 <= mask <= 1023:
            raise ValueError("invalid complete MVS mask")
        wanted = {key for bit, key in MVS_MASK_KEY_CODES.items() if mask & bit}
        if self.observation_burst:
            wanted.add(12)
        try:
            for key in sorted(self.held - wanted):
                self.post_key(key, False)
                self.held.remove(key)
            for key in sorted(wanted - self.held):
                # Track before posting so partial authority failures still release.
                self.held.add(key)
                self.post_key(key, True)
        except (OSError, AttributeError) as error:
            self.release_all()
            raise SmokeBlocked("input", "macOS could not inject frontend keyboard input") from error

    def set_observation_burst(self, enabled: bool) -> None:
        """Hold diagnostic-only RetroPad L3; it never enters the game mask."""
        if type(enabled) is not bool:
            raise ValueError("invalid observation burst flag")
        if enabled == self.observation_burst:
            return
        if enabled:
            self.held.add(12)
            self.post_key(12, True)
        else:
            self.post_key(12, False)
            self.held.discard(12)
        self.observation_burst = enabled

    def release_all(self) -> None:
        error = None
        for key in sorted(self.held):
            try:
                self.post_key(key, False)
                self.held.remove(key)
            except (OSError, AttributeError) as failure:
                error = failure
        if error is not None:
            raise SmokeBlocked("input", "macOS could not inject frontend release input") from error

    def __exit__(self, *_):
        self.release_all()


def frontmost_pid() -> int:
    """Read the foreground process without launching a slow script per frame.

    Carbon's process readback is limited to this pinned macOS host lane. An
    unavailable readback is an error, never evidence that another app has focus.
    """
    import ctypes
    try:
        services = ctypes.CDLL(APPLICATION_SERVICES)
        serial = (ctypes.c_uint32 * 2)()
        pid = ctypes.c_int()
        services.GetFrontProcess.argtypes = [ctypes.c_void_p]
        services.GetFrontProcess.restype = ctypes.c_int32
        services.GetProcessPID.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        services.GetProcessPID.restype = ctypes.c_int32
        if (services.GetFrontProcess(ctypes.byref(serial)) != 0
                or services.GetProcessPID(ctypes.byref(serial), ctypes.byref(pid)) != 0
                or pid.value <= 0):
            raise OSError("foreground readback unavailable")
        return pid.value
    except (OSError, AttributeError) as error:
        raise SmokeBlocked("input", "macOS foreground ownership readback unavailable") from error


def _activate_owned_pid_with_appkit(pid: int) -> bool:
    """Ask AppKit to activate only the already-owned frontend PID."""
    if type(pid) is not int or pid <= 0:
        return False
    source = (
        "import AppKit\n"
        "import Foundation\n"
        'guard let pid = Int32(ProcessInfo.processInfo.environment["GLUEYNEO_TARGET_PID"] ?? "") else { exit(2) }\n'
        "guard let app = NSRunningApplication(processIdentifier: pid) else { exit(3) }\n"
        "exit(app.activate(options: [.activateIgnoringOtherApps]) ? 0 : 4)\n"
    )
    environment = os.environ.copy()
    environment["GLUEYNEO_TARGET_PID"] = str(pid)
    try:
        result = subprocess.run(
            ["/usr/bin/swift", "-e", source], check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=8, env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def focus_owned_frontend(process) -> None:
    """Focus only the freshly launched PID, never another RetroArch instance."""
    if type(process.pid) is not int or process.pid <= 0 or frontend_exited(process):
        raise SmokeBlocked("input", "frontend exited before owned focus")
    script = ('tell application "System Events" to set frontmost of '
              f'(first process whose unix id is {process.pid}) to true')
    system_events_failed = False
    try:
        subprocess.run(["/usr/bin/osascript", "-e", script], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
    except (OSError, subprocess.SubprocessError) as error:
        system_events_failed = True
        system_events_error = error
    deadline = time.monotonic() + OWNED_FOCUS_READBACK_TIMEOUT_SECONDS
    readback_error = None
    if not system_events_failed:
        while True:
            if frontend_exited(process):
                raise SmokeBlocked("input", "frontend exited before owned focus")
            try:
                if frontmost_pid() == process.pid:
                    return
                readback_error = None
            except SmokeBlocked as error:
                readback_error = error
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(OWNED_FOCUS_READBACK_POLL_SECONDS, remaining))
    if readback_error is not None:
        raise readback_error
    if not _activate_owned_pid_with_appkit(process.pid):
        if system_events_failed:
            raise SmokeBlocked("input", "macOS could not activate owned frontend") from system_events_error
        raise SmokeBlocked("input", "owned frontend did not acquire foreground input")
    deadline = time.monotonic() + OWNED_FOCUS_READBACK_TIMEOUT_SECONDS
    while True:
        if frontend_exited(process):
            raise SmokeBlocked("input", "frontend exited before owned focus")
        try:
            if frontmost_pid() == process.pid:
                return
        except SmokeBlocked as error:
            readback_error = error
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if readback_error is not None:
                raise readback_error
            raise SmokeBlocked("input", "owned frontend did not acquire foreground input")
        time.sleep(min(OWNED_FOCUS_READBACK_POLL_SECONDS, remaining))


def read_png_capture_geometry(path: Path) -> tuple[int, int]:
    """Read only the bounded IHDR; full pixel validation runs after frontend exit.

    Freshness, stable size/time and complete IEND are checked by the screenshot
    selector. This cheap header read keeps RGB decompression out of the measured
    callback interval without treating the header as full PNG validity evidence.
    """
    try:
        if path.stat().st_size > TITLE_CAPTURE_MAX_BYTES:
            raise SmokeBlocked("video", "active scene capture exceeds size limit")
        with path.open("rb") as stream:
            header = stream.read(33)
    except OSError as error:
        raise SmokeBlocked("video", "active scene capture header unavailable") from error
    if (len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n"
            or header[8:16] != b"\x00\x00\x00\rIHDR"
            or zlib.crc32(header[12:29]) & 0xffffffff != int.from_bytes(header[29:33], "big")):
        raise SmokeBlocked("video", "invalid active scene capture header")
    return struct.unpack(">II", header[16:24])


def _active_png_framing_is_valid(data: bytes) -> bool:
    """Validate bounded PNG framing/CRCs, leaving RGB inflation until exit."""
    if len(data) > TITLE_CAPTURE_MAX_BYTES or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset, chunks, idat, idat_ended = 8, 0, False, False
    while offset < len(data) and chunks < 4096:
        if len(data) - offset < 12:
            return False
        size = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        if (size > len(data) - offset - 12
                or any(not (65 <= value <= 90 or 97 <= value <= 122) for value in kind)):
            return False
        if not kind[0] & 0x20 and kind not in (b"IHDR", b"PLTE", b"IDAT", b"IEND"):
            return False
        end = offset + 8 + size
        if zlib.crc32(memoryview(data)[offset + 4:end]) & 0xffffffff != int.from_bytes(data[end:end + 4], "big"):
            return False
        if chunks == 0:
            if kind != b"IHDR" or size != 13:
                return False
            fields = struct.unpack(">IIBBBBB", data[offset + 8:end])
            if fields not in ((WIDTH, HEIGHT, 8, 2, 0, 0, 0),
                              (WIDTH, HEIGHT, 8, 6, 0, 0, 0)):
                return False
        elif kind == b"IHDR":
            return False
        if kind == b"IDAT":
            if idat_ended:
                return False
            idat = True
        elif idat:
            idat_ended = True
        offset = end + 4
        chunks += 1
        if kind == b"IEND":
            return size == 0 and idat and offset == len(data)
    return False


def snapshot_active_scene_png(path: Path, prior: dict[Path, int]) -> tuple[Path, str] | None:
    """Own one consistent complete PNG byte snapshot without a pacing sleep.

    Producer completion is not asserted: one no-follow regular-file read must
    have stable descriptor/path identity and metadata and valid chunk framing.
    The copied bytes, never the producer inode, own the evidence identity.
    """
    def identity(value):
        return (value.st_dev, value.st_ino, value.st_size,
                value.st_mtime_ns, value.st_ctime_ns)
    try:
        initial = path.lstat()
        if (not stat_module.S_ISREG(initial.st_mode) or initial.st_size > TITLE_CAPTURE_MAX_BYTES
                or (path in prior and initial.st_mtime_ns <= prior[path])):
            return None
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb", buffering=0) as producer:
            before = os.fstat(producer.fileno())
            if not stat_module.S_ISREG(before.st_mode) or identity(before) != identity(initial):
                return None
            data = producer.read(TITLE_CAPTURE_MAX_BYTES + 1)
            after = os.fstat(producer.fileno())
        current = path.lstat()
        if (identity(before) != identity(after) or identity(after) != identity(current)
                or not stat_module.S_ISREG(current.st_mode) or len(data) != after.st_size
                or not _active_png_framing_is_valid(data)):
            return None
    except OSError:
        return None
    descriptor, name = tempfile.mkstemp(prefix="active-capture-", suffix=".png", dir=path.parent)
    stored = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as owned:
            owned.write(data)
    except OSError as error:
        stored.unlink(missing_ok=True)
        raise SmokeBlocked("video", "active scene snapshot could not be retained") from error
    return stored, hashlib.sha256(data).hexdigest()


def select_active_scene_png(directory: Path, prior: dict[Path, int]) -> tuple[Path, str] | None:
    """Try bounded fresh producer candidates; ordinary screenshot policy stays separate."""
    candidates = []
    for path in directory.glob("*.png"):
        try:
            candidates.append((path.lstat().st_mtime_ns, path))
        except OSError:
            continue
    for _, path in sorted(candidates, reverse=True):
        snapshot = snapshot_active_scene_png(path, prior)
        if snapshot is not None:
            return snapshot
    return None


def request_active_scene_screenshot(collector: MVSObservationCollector, directory: Path,
                                    expected_mask: int, timeout: float = 10.0, *, post_transition=None):
    """Pulse/retry F8 on observed callbacks and retain an immutable fresh PNG."""
    if not 0 < timeout <= 120:
        raise SmokeBlocked("video", "invalid screenshot timeout")
    prior = screenshot_snapshot(directory)
    post = post_key_transition if post_transition is None else post_transition
    before = collector.drain()
    deadline = time.monotonic() + timeout
    def progress():
        records = collector.drain()
        videos = [record for record in records if record["event_kind"] == "V"]
        target = videos[-1]["successful_video_sequence"] + 1 if videos else 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SmokeBlocked("video", "active scene screenshot timed out")
        return collector.wait_for_video(target, expected_mask, remaining)
    while True:
        fresh = None
        after = None
        records = collector.drain()
        videos = [record for record in records if record["event_kind"] == "V"]
        attempt_start = videos[-1]["successful_video_sequence"] if videos else 0
        post(SCREENSHOT_KEY_CODE, True)
        try:
            progress()
            # RA's screenshot hotkey queues a threaded write. Poll availability
            # before spending callback progress on keyUp cleanup. Keep the same
            # complete framing/CRC and stable-read snapshot, never narrow late PNGs.
            # RA 69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576:
            # retroarch.c:3386-3391; tasks/task_screenshot.c:385-410.
            # Holding F8 does not enqueue another screenshot each callback:
            # runloop.c:5916 uses the rising-edge HOTKEY_CHECK at5084-5092.
            while True:
                collector.drain()
                fresh = select_active_scene_png(directory, prior)
                if fresh is not None:
                    break
                records = collector.drain()
                videos = [record for record in records if record["event_kind"] == "V"]
                if videos and videos[-1]["successful_video_sequence"] - attempt_start >= 8:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SmokeBlocked("video", "active scene screenshot timed out")
                time.sleep(min(0.005, remaining))
            if fresh is not None:
                # Bind the first fully drained callback after PNG completion,
                # before unrelated keyUp cleanup callbacks widen the interval.
                after = progress()
        finally:
            post(SCREENSHOT_KEY_CODE, False)
            progress()
            progress()
        if fresh is None:
            fresh = select_active_scene_png(directory, prior)
        if fresh is None:
            # Every retry follows two complete progressing release callbacks.
            continue
        if after is None:
            # A file first noticed after release retains the wider interval.
            after = progress()
        stored, capture_digest = fresh
        binding = bind_active_scene_capture(before, after, invocation_id=collector.invocation_id,
                                             expected_mask=expected_mask, capture_sha256=capture_digest)
        return stored, binding


def focus_frontend() -> None:
    script = 'tell application "System Events" to set frontmost of process "RetroArch" to true'
    try:
        subprocess.run(["/usr/bin/osascript", "-e", script], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=8)
        time.sleep(FOCUS_SETTLE_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        raise SmokeBlocked("input", "macOS could not inject frontend focus input") from error


def inject_key(key_code: int, *, repeats: int = 1, hold: float = KEY_HOLD_SECONDS) -> None:
    focus_frontend()
    try:
        for _ in range(repeats):
            post_held_key(key_code, hold)
            time.sleep(KEY_GAP_SECONDS)
    except (OSError, AttributeError, subprocess.SubprocessError) as error:
        raise SmokeBlocked("input", "macOS could not inject the mapped arrow-key input") from error


def screenshot_snapshot(directory: Path) -> dict[Path, int]:
    return {path: path.stat().st_mtime_ns for path in directory.glob("*.png")}


def validate_active_config_destinations(
    text: str, work: Path, captures: Path, *, savefiles: Path | None = None,
    savestates: Path | None = None, public_state: bool = False,
    periodic_save: bool = False, block_sram_overwrite: bool = False,
    autosave_interval: int = 0, stdin_commands: bool = False,
) -> bool:
    """Validate requested destinations before any cross-run path projection.

    This validates the owned launch contract, not an unobserved frontend runtime
    setting. Exact config bytes are checked separately after the invocation.
    """
    if (not isinstance(text, str) or len(text.encode("utf-8")) > 12 * 1024 or
            type(public_state) is not bool or type(periodic_save) is not bool or
            (public_state and periodic_save) or type(block_sram_overwrite) is not bool or
            type(autosave_interval) is not int or autosave_interval < 0 or
            type(stdin_commands) is not bool):
        return False
    settings = {}
    for line in text.splitlines():
        match = re.fullmatch(r'([a-z0-9_]+) = "([^"\r\n]*)"', line)
        if match is None or match[1] in settings:
            return False
        settings[match[1]] = match[2]
    expected = {key: work for key in (
        "playlist_directory", "content_history_directory", "content_favorites_directory",
        "content_image_history_directory", "content_music_history_directory", "content_video_directory",
        "system_directory", "cache_directory", "log_dir")}
    expected.update(savefile_directory=work if savefiles is None else savefiles,
                    savestate_directory=work if savestates is None else savestates)
    expected.update(content_history_path=work / "content_history.lpl", screenshot_directory=captures)
    if settings.get("record_driver") == "wav":
        expected.update(recording_output_directory=captures / "recordings",
                        recording_config_directory=work)
    for key, path in expected.items():
        value = settings.get(key)
        if not value or not Path(value).is_absolute() or Path(value).resolve() != path.resolve():
            return False
    if (settings.get("bundle_assets_extract_enable") != "false" or
            settings.get("config_save_on_exit") != "false"):
        return False
    if public_state:
        required = {
            "sort_savestates_enable": "false",
            "sort_savefiles_enable": "false",
            "sort_savestates_by_content_enable": "false",
            "sort_savefiles_by_content_enable": "false",
            "input_enable_hotkey": "nul",
            "input_save_state": "f2",
            "input_load_state": "f4",
            "input_menu_toggle": "f1",
            "menu_driver": "rgui",
            # Pin the source-defined state row order used by the real undo path.
            "quick_menu_show_resume_content": "false",
            "quick_menu_show_restart_content": "false",
            "quick_menu_show_close_content": "false",
            "quick_menu_show_savestate_submenu": "false",
            "quick_menu_show_save_load_state": "true",
            "quick_menu_show_undo_save_load_state": "true",
            "quick_menu_show_take_screenshot": "false",
            "quit_press_twice": "false",
            "input_pause_toggle": "p",
            "input_frame_advance": "k",
            "input_state_slot_decrease": "f6",
            "input_state_slot_increase": "f7",
            "input_reset": "h",
            "state_slot": "0",
            "savestate_file_compression": "false",
            "savestate_thumbnail_enable": "false",
            "savestate_auto_save": "false",
            "savestate_auto_load": "false",
            "savestate_auto_index": "false",
            "block_sram_overwrite": "true" if block_sram_overwrite else "false",
            "autosave_interval": str(autosave_interval),
            "save_file_compression": "false",
            "input_exit_emulator": "escape",
            "quit_press_twice": "false",
        }
        if stdin_commands:
            required.update(stdin_cmd_enable="true", network_cmd_enable="false")
        return all(settings.get(key) == value for key, value in required.items())
    if periodic_save:
        required = {
            "input_enable_hotkey": "nul",
            "input_save_state": "nul",
            "input_load_state": "nul",
            "input_reset": "h",
            "state_slot": "0",
            "savestate_file_compression": "false",
            "savestate_thumbnail_enable": "false",
            "savestate_auto_save": "false",
            "savestate_auto_load": "false",
            "savestate_auto_index": "false",
            "block_sram_overwrite": "false",
            "input_menu_toggle": "nul",
            "autosave_interval": str(autosave_interval),
            "save_file_compression": "false",
            "input_exit_emulator": "escape",
            "quit_press_twice": "false",
        }
        if stdin_commands:
            required.update(stdin_cmd_enable="true", network_cmd_enable="false")
        return autosave_interval > 0 and all(
            settings.get(key) == value for key, value in required.items())
    return True


def write_frontend_config(work: Path, screenshots: Path, *, direct_log: bool = False,
                          savefiles: Path | None = None,
                          savestates: Path | None = None,
                          public_state: bool = False,
                          periodic_save: bool = False,
                          stdin_commands: bool = False,
                          block_sram_overwrite: bool = False,
                          autosave_interval: int = 0,
                          null_audio: bool = False) -> Path:
    config = work / "retroarch.cfg"
    settings = [
                'video_driver = "gl"',
                'video_fullscreen = "false"',
                'video_windowed_fullscreen = "false"',
                'video_scale = "2"',
                'video_smooth = "false"',
                'video_vsync = "true"',
                'pause_nonactive = "false"',
                'video_gpu_screenshot = "false"',
                'notification_show_screenshot = "false"',
                # Pinned RA menu_driver.c bundle_decompressed saves configuration
                # even when config_save_on_exit is false. This lane needs no extraction.
                'bundle_assets_extract_enable = "false"',
                'input_driver = "cocoa"',
                'input_player1_up = "up"',
                'input_player1_down = "down"',
                'input_player1_select = "num1"',
                'input_player1_start = "num2"',
                'input_player1_b = "z"',
                'input_player1_a = "x"',
                'input_player1_y = "a"',
                'input_player1_x = "s"',
                'input_player1_l3 = "q"',
                'input_player1_left = "left"',
                'input_player1_right = "right"',
                'input_screenshot = "f8"',
                f'content_history_path = "{work / "content_history.lpl"}"',
                # configuration.c migrates a path when its directory is default.
                f'playlist_directory = "{work}"',
                f'content_history_directory = "{work}"',
                f'content_favorites_directory = "{work}"',
                f'content_image_history_directory = "{work}"',
                f'content_music_history_directory = "{work}"',
                f'content_video_directory = "{work}"',
                f'savefile_directory = "{work if savefiles is None else savefiles}"',
                'save_file_compression = "false"',
                f'savestate_directory = "{work if savestates is None else savestates}"',
                f'autosave_interval = "{autosave_interval if periodic_save else 0}"',
                f'system_directory = "{work}"',
                f'cache_directory = "{work}"',
                f'screenshot_directory = "{screenshots}"',
                'log_to_file = "false"' if direct_log else 'log_to_file = "true"',
                f'log_dir = "{work}"',
            ]
    if null_audio:
        # The core observer captures raw PCM before the frontend sink. A null
        # sink keeps this evidence lane independent of host audio backpressure.
        settings.insert(0, 'audio_driver = "null"')
    config.write_text(
        "\n".join(settings) + "\n",
        encoding="utf-8",
    )
    if public_state or periodic_save:
        if (public_state and periodic_save) or type(block_sram_overwrite) is not bool or \
                type(autosave_interval) is not int or autosave_interval < 0 or \
                type(stdin_commands) is not bool or \
                (stdin_commands and not (public_state or periodic_save)):
            raise SmokeBlocked("operation-matrix", "invalid state/SRAM frontend configuration")
        state_load = "f4" if public_state else "nul"
        block_sram_value = "true" if block_sram_overwrite else "false"
        settings_to_append = [
                'config_save_on_exit = "false"',
                'sort_savestates_enable = "false"',
                'sort_savefiles_enable = "false"',
                'sort_savestates_by_content_enable = "false"',
                'sort_savefiles_by_content_enable = "false"',
                'input_enable_hotkey = "nul"',
                f'input_save_state = "{"f2" if public_state else "nul"}"',
                f'input_load_state = "{state_load}"',
                'input_reset = "h"',
                'state_slot = "0"',
                'savestate_file_compression = "false"',
                'savestate_thumbnail_enable = "false"',
                'savestate_auto_save = "false"',
                'savestate_auto_load = "false"',
                'savestate_auto_index = "false"',
                f'block_sram_overwrite = "{block_sram_value}"',
                'input_exit_emulator = "escape"',
            ]
        if stdin_commands:
            settings_to_append.extend((
                'stdin_cmd_enable = "true"',
                'network_cmd_enable = "false"',
            ))
        if public_state:
            settings_to_append.extend((
                'input_menu_toggle = "f1"',
                'menu_driver = "rgui"',
                'quick_menu_show_resume_content = "false"',
                'quick_menu_show_restart_content = "false"',
                'quick_menu_show_close_content = "false"',
                'quick_menu_show_savestate_submenu = "false"',
                'quick_menu_show_save_load_state = "true"',
                'quick_menu_show_undo_save_load_state = "true"',
                'quick_menu_show_take_screenshot = "false"',
                'quit_press_twice = "false"',
                'input_pause_toggle = "p"',
                'input_frame_advance = "k"',
                'input_state_slot_decrease = "f6"',
                'input_state_slot_increase = "f7"',
            ))
        if periodic_save:
            settings_to_append.extend((
                'input_menu_toggle = "nul"',
                'quit_press_twice = "false"',
            ))
        with config.open("a", encoding="utf-8") as stream:
            stream.write("\n".join(settings_to_append) + "\n")
    return config


def running_retroarch_pids() -> set[int]:
    """Return the PIDs of every running RetroArch process; fail closed on any doubt.

    The project allows at most one RetroArch instance, and key injection and the
    bundle-id quit act on any instance, so every launch and quit consults this.
    """
    try:
        result = subprocess.run(
            ["/usr/bin/pgrep", "-x", "RetroArch"], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, check=False, timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SmokeBlocked("pre-launch", "cannot enumerate running RetroArch instances") from error
    if result.returncode == 1:
        return set()
    if result.returncode != 0:
        raise SmokeBlocked("pre-launch", "cannot enumerate running RetroArch instances")
    try:
        return {int(token) for token in result.stdout.split()}
    except ValueError as error:
        raise SmokeBlocked("pre-launch", "cannot enumerate running RetroArch instances") from error


def record_child_pid(path: object, process: subprocess.Popen[bytes]) -> None:
    """Persist the launched frontend PID atomically for the runner's scoped survivor cleanup."""
    pid = getattr(process, "pid", None)
    if not isinstance(path, Path) or not isinstance(pid, int):
        return
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(f"{pid}\n", encoding="utf-8")
    os.replace(temporary, path)


def _exited_unreaped(process: subprocess.Popen[bytes]) -> bool | None:
    """True/False for an exited/running child of this process, None when it is not waitable.

    Uses WNOWAIT so the leader is NOT reaped: an exited leader stays a zombie that pins
    its PID and process group until `reap_frontend` has swept the group (GWR-05b).
    """
    pid = getattr(process, "pid", None)
    if not isinstance(pid, int) or pid <= 1:
        return None
    try:
        return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
    except ChildProcessError:
        return None


def frontend_exited(process: subprocess.Popen[bytes]) -> bool:
    """Non-reaping liveness check for the launched frontend."""
    if getattr(process, "returncode", None) is not None:
        return True
    state = _exited_unreaped(process)
    if state is None:  # already reaped elsewhere, or not a waitable child
        return process.poll() is not None
    return state


def reap_frontend(process: subprocess.Popen[bytes], timeout: float) -> int | None:
    """Wait for the frontend leader to exit, sweep its group while it is a zombie, then reap.

    Returns the return code, or None when the leader is still running at `timeout`.
    """
    deadline = time.monotonic() + timeout
    while True:
        if getattr(process, "returncode", None) is not None:
            return process.returncode
        state = _exited_unreaped(process)
        if state is None:  # not a waitable child (already reaped elsewhere): plain bounded wait
            try:
                process.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                return None
            return process.returncode
        if state:
            pid = process.pid
            try:
                os.killpg(pid, signal.SIGKILL)  # the unreaped leader pins the group
            except (ProcessLookupError, PermissionError):
                pass
            process.wait()
            return process.returncode
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.05)


def frontend_returncode(process: subprocess.Popen[bytes]) -> int | None:
    """Return code of an exited frontend (reaped after the group sweep), None while running."""
    if frontend_exited(process):
        return reap_frontend(process, 2.0)
    return None


def kill_launched_group(process: subprocess.Popen[bytes]) -> None:
    """Kill the frontend's own session group while the leader is unreaped (pgid == pid).

    The leader may be alive or an exited zombie; either pins the PID, so the group cannot
    be a recycled one. After reaping nothing is signalled.
    """
    pid = getattr(process, "pid", None)
    if not isinstance(pid, int) or pid <= 1 or getattr(process, "returncode", None) is not None:
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return
    reap_frontend(process, 2.0)


# Launch-window state for GWR-05a. Signals are deferred (not masked) while the frontend is
# being launched. Do NOT use pthread_sigmask for this: a blocked mask is inherited across
# fork/exec, so the frontend would start with SIGTERM blocked and could never be stopped.
_LAUNCH_WINDOW: dict[str, object] = {"open": False, "pending": None}


def _ignore_further_signals() -> None:
    for name in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(name, signal.SIG_IGN)  # a second signal must not abort the cleanup


@contextlib.contextmanager
def launch_window():  # type: ignore[no-untyped-def]
    """Defer termination signals around Popen, process assignment and the child PID record.

    On exit, a signal that arrived inside the window raises SmokeBlocked("interrupted"),
    after the caller has assigned `process`, so its cleanup always sees the child. The
    signal is raised from `finally`, chained from any body exception, so it is never dropped
    when the window body raises (G2WR-06).
    """
    _LAUNCH_WINDOW["open"] = True
    _LAUNCH_WINDOW["pending"] = None
    body_error: BaseException | None = None
    try:
        yield
    except BaseException as error:
        body_error = error
        raise
    finally:
        _LAUNCH_WINDOW["open"] = False
        # G2WR-06: the pending check runs here so a raising body cannot drop the signal; the
        # SmokeBlocked below replaces the body exception and is chained from it.
        if _LAUNCH_WINDOW["pending"] is not None:
            _LAUNCH_WINDOW["pending"] = None
            _ignore_further_signals()
            raise SmokeBlocked(
                "interrupted", "smoke was signalled before completion") from body_error


def install_signal_cleanup() -> None:
    """Turn SIGTERM/SIGINT/SIGHUP into SmokeBlocked so the launch `finally` quit runs."""
    def interrupted(signum: int, _frame: object) -> None:
        if _LAUNCH_WINDOW["open"]:
            _LAUNCH_WINDOW["pending"] = signum  # raised by launch_window on exit
            return
        _ignore_further_signals()
        raise SmokeBlocked("interrupted", "smoke was signalled before completion")

    for name in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(name, interrupted)


def refuse_stacked_launch() -> None:
    if running_retroarch_pids():
        raise SmokeBlocked(
            "pre-launch", "another RetroArch instance is running; refusing to start a second instance")


def request_frontend_quit(bundle_id: str, process: subprocess.Popen[bytes], timeout: float) -> bool:
    if frontend_exited(process):
        return frontend_returncode(process) == 0
    sole_instance = False
    if bundle_id == EXPECTED_BUNDLE_IDENTIFIER:
        try:
            sole_instance = running_retroarch_pids() == {process.pid}
        except SmokeBlocked:
            sole_instance = False
    # The bundle-id quit addresses any instance; use it only when ours is the only one.
    if sole_instance:
        try:
            subprocess.run(
                ["/usr/bin/osascript", "-e", f'tell application id "{bundle_id}" to quit'],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=min(8.0, timeout),
            )
            if reap_frontend(process, min(8.0, timeout)) is not None:
                return process.returncode == 0
        except (OSError, subprocess.SubprocessError):
            pass
    process.terminate()
    if reap_frontend(process, 2.0) is None:
        process.kill()
        reap_frontend(process, 2.0)
    return process.returncode == 0


def run_launch_probe(
    executable: Path,
    core: Path,
    content: Path,
    bundle_id: str,
    *,
    probe: str,
    timeout: float,
    child_pid_file: Path | None = None,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"glueyneo-retroarch-{probe}-") as temporary:
        work = Path(temporary)
        screenshots = work / "screenshots"
        screenshots.mkdir()
        config = write_frontend_config(work, screenshots, null_audio=True)
        log = work / "retroarch.log"
        process_log = work / "process-output.log"
        prior_crash_reports = crash_report_snapshot()
        arguments = [str(executable), "--verbose", "--config", str(config)]
        if probe == "core_content":
            arguments.extend(["-L", str(core), str(content)])
        started_at = time.time()
        refuse_stacked_launch()
        try:
            process = None
            pid_record_error: OSError | None = None
            with process_log.open("wb") as log_stream:
                try:
                    with launch_window():
                        process = subprocess.Popen(
                            arguments, stdout=log_stream, stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )
                        # A PID record failure is not a launch failure (G3WR-03): the frontend
                        # is running and the finally below still kills its group.
                        try:
                            record_child_pid(child_pid_file, process)
                        except OSError as error:
                            pid_record_error = error
                    if pid_record_error is not None:
                        survived_window = None
                        return_code = None
                        diagnostic = build_diagnostic(
                            stage="pid-record",
                            return_code=None,
                            survived_before_screenshot=None,
                            output=f"{type(pid_record_error).__name__}: {pid_record_error}",
                            temporary_root=work,
                        )
                    else:
                        reaped = reap_frontend(process, min(DIAGNOSTIC_PROBE_SECONDS, timeout))
                        survived_window = reaped is None
                        return_code = reaped
                        crash_reason = (
                            wait_for_recent_crash_reason(started_at, prior_crash_reports)
                            if return_code is not None and return_code < 0
                            else find_recent_crash_reason(started_at, prior_crash_reports)
                        )
                        diagnostic = build_diagnostic(
                            stage="no-content-startup" if probe == "no_content" else "core-content-load",
                            return_code=return_code,
                            survived_before_screenshot=None,
                            output=collect_frontend_output(process_log, log, work),
                            temporary_root=work,
                            crash_report=crash_reason,
                        )
                        request_frontend_quit(bundle_id, process, timeout)
                    cleanup_return_code = None
                finally:
                    if process is not None:
                        kill_launched_group(process)
                if process is not None:
                    cleanup_return_code = frontend_returncode(process)
        except OSError as error:
            survived_window = False
            return_code = None
            cleanup_return_code = None
            diagnostic = build_diagnostic(
                stage="launch",
                return_code=None,
                survived_before_screenshot=None,
                output=str(error),
                temporary_root=work,
            )
        return {
            "return_code": return_code,
            "survived_window": survived_window,
            "cleanup_return_code": cleanup_return_code,
            "diagnostic": diagnostic,
            "profile": "fresh temporary config and capture directory",
        }


def run_diagnostics(args: argparse.Namespace) -> dict[str, object]:
    executable, core, content, identity = validate_inputs(args)
    child_pid_file = getattr(args, "child_pid_file", None)
    no_content = run_launch_probe(
        executable, core, content, identity["bundle_id"],
        probe="no_content", timeout=args.timeout, child_pid_file=child_pid_file,
    )
    diagnostic = no_content.get("diagnostic")
    if isinstance(diagnostic, dict) and diagnostic.get("stage") == "pid-record":
        # The PID file cannot be trusted after a record failure, and the finding is already decided, so a
        # second frontend launch adds nothing (G4IN-03).
        core_content = {"probe": "core_content", "status": "not-run", "reason": "skipped-after-pid-record"}
    else:
        core_content = run_launch_probe(
            executable, core, content, identity["bundle_id"],
            probe="core_content", timeout=args.timeout, child_pid_file=child_pid_file,
        )
    return {
        "status": "diagnostic_only",
        "finding": compare_launch_probes(no_content, core_content),
        "identity": identity,
        "probes": {"no_content": no_content, "core_content": core_content},
        "acceptance": "diagnostic probes do not satisfy HOST-02",
    }


def validate_inputs(args: argparse.Namespace) -> tuple[Path, Path, Path, dict[str, str]]:
    if sys.platform != "darwin":
        raise SmokeBlocked("identity", "actual frontend smoke is supported only on macOS")
    bundle = args.retroarch.resolve()
    core = args.core.resolve()
    content = args.content.resolve()
    plist_path = bundle / "Contents" / "Info.plist"
    if not bundle.is_dir() or not plist_path.is_file():
        raise SmokeBlocked("identity", "RetroArch bundle or Info.plist is missing")
    with plist_path.open("rb") as stream:
        info = plistlib.load(stream)
    bundle_id = info.get("CFBundleIdentifier")
    if bundle_id != EXPECTED_BUNDLE_IDENTIFIER:
        raise SmokeBlocked("identity", "RetroArch bundle identifier does not match the pinned application")
    version = str(info.get("CFBundleShortVersionString", ""))
    executable_name = str(info.get("CFBundleExecutable", ""))
    executable = bundle / "Contents" / "MacOS" / executable_name
    if version != EXPECTED_VERSION:
        raise SmokeBlocked("identity", f"expected RetroArch {EXPECTED_VERSION}; observed {version or 'unknown'}")
    if not executable.is_file():
        raise SmokeBlocked("identity", "RetroArch executable is missing from its bundle")
    executable_hash = sha256(executable)
    if executable_hash != EXPECTED_EXECUTABLE_SHA256:
        raise SmokeBlocked("identity", "RetroArch executable digest does not match the pinned artifact")
    if not core.is_file() or not content.is_file():
        raise SmokeBlocked("input", "built Libretro core or requested content is missing")
    with content.open("rb") as stream:
        magic = stream.read(4)
    fixture_digest: str | None = None
    if magic == b"GNMV":
        if content.stat().st_size > GNMV_MAX_BYTES:
            raise SmokeBlocked("input", "selected MVS bundle exceeds the bounded input size")
        with content.open("rb") as stream:
            selected_bundle = stream.read(GNMV_MAX_BYTES + 1)
        if len(selected_bundle) > GNMV_MAX_BYTES:
            raise SmokeBlocked("input", "selected MVS bundle exceeds the bounded input size")
        if not is_normalized_mvs_bundle(selected_bundle):
            raise SmokeBlocked("input", "selected MVS bundle is malformed or outside the supported profile")
        content_kind = "selected-mvs"
    else:
        if content.stat().st_size != 602:
            raise SmokeBlocked("input", "content is neither the public GNFX fixture nor a normalized MVS bundle")
        fixture = content.read_bytes()
        if len(fixture) != 602 or fixture[:4] != b"GNFX" or fixture[4:8] != b"\0\0\0\1":
            raise SmokeBlocked("input", "content is neither the public GNFX fixture nor a normalized MVS bundle")
        fixture_digest = hashlib.sha256(fixture).hexdigest()
        if fixture_digest != EXPECTED_FIXTURE_SHA256:
            raise SmokeBlocked("input", "content digest does not match the pinned public GNFX fixture")
        content_kind = "public-fixture"
    identity = {
        "retroarch_version": version,
        "retroarch_executable_sha256": executable_hash,
        "core_sha256": sha256(core),
        "content_kind": content_kind,
        "os": f"macOS {platform.mac_ver()[0]} {platform.machine()}",
        "input_mapping": "RetroPad RIGHT <- Right Arrow; LEFT control <- Left Arrow",
        "control": "local keyboard and frontend screenshots; no network command interface",
        "bundle_id": bundle_id,
    }
    if fixture_digest is not None:
        identity["fixture_sha256"] = fixture_digest
    return executable, core, content, identity


def sampled_mvs_masks(actual: dict, frame_count: int) -> list[int]:
    """Expand the complete observed input chain, without fitting frame offsets."""
    records = _validated_observation_records(actual.get("observations"), actual.get("invocation_id"))
    if (type(frame_count) is not int or not 1 <= frame_count <= 8192 or
            max(row["successful_video_sequence"] for row in records) < frame_count):
        raise SmokeBlocked("input-replay", "incomplete replay input history")
    changes = {row["sample_sequence"]: row["sampled_mask"] for row in records if row["event_kind"] == "S"}
    if 1 not in changes:
        raise SmokeBlocked("input-replay", "missing initial replay sample")
    mask, result = 0, []
    for sequence in range(1, frame_count + 1):
        mask = changes.get(sequence, mask)
        result.append(mask)
    return result


def mvs_input_replay_bytes(masks: list[int], *, dense_from: int, dense_until: int) -> bytes:
    """Independently authored input-only BSV1 producer for pinned RA1.22.2.

    Format facts: upstream input/bsv/bsvmovie.h, input/input_driver.h and
    bsv_movie_reset_playback/read_next_events, tag v1.22.2. No upstream code
    copied. Zero state and no checkpoints: this is not snapshot compatibility.
    The pinned zero-state reader consumes 40 header bytes even for version1.
    Cocoa's nonthreaded task queue starts CLI playback after the first guest
    frame; record1 therefore supplies frame2. Require the neutral bootstrap,
    omit it from the file, and check every actual sample after acquisition.
    This fixed source-derived launch mapping is not an offset search.
    Explicit keyed queries cover all joypad IDs, including observation-only L3.
    """
    if (not isinstance(masks, list) or not 2 <= len(masks) <= 8192 or
            any(type(mask) is not int or not 0 <= mask <= 1023 for mask in masks) or
            masks[0] != 0 or
            type(dense_from) is not int or type(dense_until) is not int or
            not 1 <= dense_from <= dense_until <= len(masks)):
        raise SmokeBlocked("input-replay", "invalid bounded replay masks")
    # Neo Geo bits map to libretro SELECT, START, UP, DOWN, LEFT, RIGHT,
    # B, A, Y, X. Other IDs remain explicitly neutral; L3 only enables logs.
    bits = {2: 1, 3: 2, 4: 4, 5: 8, 6: 16, 7: 32, 0: 64, 8: 128, 1: 256, 9: 512}
    output = bytearray(struct.pack("<10I", 0x42535632, 1, 0, 0, 0, 0, 0, 0, 0, 0))
    for sequence, mask in enumerate(masks[1:], 2):
        output.extend(struct.pack("<BH", 0, 16))  # no keyboard; 16 keyed joypad events
        for identifier in range(16):
            value = int(dense_from <= sequence <= dense_until) if identifier == 14 else int(bool(mask & bits.get(identifier, 0)))
            output.extend(struct.pack("<BBBBHh", 0, 1, 0, 0, identifier, value))
        output.append(ord("f"))
    return bytes(output)


def run_mvs_active_scene(args: argparse.Namespace, schedule: dict[str, object], *,
                         invocation_id: str,
                         audio_control: str | None = None,
                         input_replay: dict | None = None) -> dict[str, object]:
    """Retain a private reason when active-scene preflight blocks before launch."""
    try:
        return _run_mvs_active_scene_impl(args, schedule, invocation_id=invocation_id,
                                          audio_control=audio_control, input_replay=input_replay)
    except SmokeBlocked as error:
        diagnostic=getattr(error,"diagnostic",None)
        if not isinstance(diagnostic,dict):
            diagnostic={}
        error.diagnostic={**diagnostic,"status":"incomplete","stage":error.stage,
                          "failure_reason":str(error)[:256],"invocation_id":invocation_id,
                          "observations":diagnostic.get("observations",[]),
                          "captures":diagnostic.get("captures",[]),
                          "observed_events":diagnostic.get("observed_events",[])}
        raise


def bind_manual_gameplay_capture(before, after, *, invocation_id, capture_sha256):
    """Full history supports variable input; no semantic or exact-phase claim."""
    _validated_observation_records(before, invocation_id)
    _validated_observation_records(after, invocation_id)
    if after[:len(before)] != before:
        raise SmokeBlocked("observations", "manual capture history prefix changed")
    earlier = [r for r in before if r["event_kind"] == "V"]
    later = [r for r in after[len(before):] if r["event_kind"] == "V"]
    if not earlier or not later or re.fullmatch(r"[0-9a-f]{64}", capture_sha256) is None:
        raise SmokeBlocked("observations", "manual capture lacks progressing endpoints")
    lo, hi = earlier[-1]["successful_video_sequence"], later[-1]["successful_video_sequence"]
    if not 0 < hi - lo <= 64:
        raise SmokeBlocked("observations", "manual capture interval exceeded")
    masks = sorted({r["sampled_mask"] for r in after
                    if lo <= r["successful_video_sequence"] <= hi and r["event_kind"] in ("S", "V")})
    return dict(manual_capture_policy="manual_full_history_interval_v1",
        capture_sha256=capture_sha256, successful_video_interval=[lo, hi],
        sampled_masks=masks, before_record_count=len(before), after_record_count=len(after),
        exact_frame="unknown", invocation_id=invocation_id)


def request_manual_gameplay_screenshot(collector, directory, timeout, *, post_transition):
    """Actual screenshot, any progressing input mask, immutable byte ownership."""
    before = collector.drain(); prior = screenshot_snapshot(directory)
    deadline = time.monotonic() + timeout
    post_transition(SCREENSHOT_KEY_CODE, True)
    try:
        while True:
            after = collector.drain()
            fresh = select_active_scene_png(directory, prior)
            if fresh is not None and any(r["event_kind"] == "V" for r in after[len(before):]):
                path, sha = fresh
                return path, bind_manual_gameplay_capture(before, after,
                    invocation_id=collector.invocation_id, capture_sha256=sha)
            if frontend_exited(collector.process) or time.monotonic() >= deadline:
                raise SmokeBlocked("video", "manual screenshot unavailable")
            time.sleep(.005)
    finally:
        post_transition(SCREENSHOT_KEY_CODE, False)


def _manual_from_boot(collector, keys, captures, total, targets, remaining, handoff):
    """Human owns Coin/Start and all gameplay input from the first callback."""
    collector.expected_mask = None
    handoff(0)
    while True:
        records = collector.drain()
        if len(records) > 250:
            raise SmokeBlocked("observations", "manual boot record budget")
        ready = [r for r in records if r["event_kind"] == "R"]
        started = [r for r in records if r["event_kind"] == "P"]
        if ready and started:
            origin = started[0]["successful_video_sequence"]
            result = _manual_active_window(collector, keys, captures, origin,
                total, targets, remaining, lambda _origin: None, from_boot=True)
            result["active_origin_video_sequence"] = origin
            result["manual_boot_policy"] = "human_coin_start_from_boot_v1"
            return result
        if frontend_exited(collector.process):
            raise SmokeBlocked("unload", "manual boot exited before actual readiness/start")
        time.sleep(min(.005, remaining()))


def _manual_active_window(collector, keys, captures, origin, total, targets, remaining, handoff, *, from_boot=False):
    """Owned live human window; only screenshot hotkeys after explicit handoff.

    This lane never interprets the scripted schedule as human input evidence.
    Thirty-two changes and the existing source cap are fail-closed resource limits.
    """
    if total > 1800 or len(targets) != 3 or not callable(handoff):
        raise SmokeBlocked("input", "manual window requires <=1800 frames and three captures")
    if not from_boot:
        keys.release_all()
    before = collector.drain()
    if len(before) > 47:
        raise SmokeBlocked("observations", "manual preactive record budget")
    collector.expected_mask = None
    begin = 1 if from_boot else len(before)
    original_drain = collector.drain
    def bounded_drain():
        records = original_drain()
        if (len(records) > 250 or
            sum(r["event_kind"] == "S" for r in records[begin:]) > 32 or
            any(r["successful_video_sequence"] > origin + total + 128 for r in records[begin:])):
            raise SmokeBlocked("observations", "manual observation/input/horizon budget")
        return records
    collector.drain = bounded_drain
    try:
        handoff(origin)
        result = {"input_mode": "manual", "handoff_record_count": begin, "captures": []}
        pending = iter(targets); target = next(pending, None)
        while True:
            records = collector.drain()
            if len(records) > 250 or sum(r["event_kind"] == "S" for r in records[begin:]) > 32:
                raise SmokeBlocked("observations", "manual observation/input budget")
            videos = [r for r in records if r["event_kind"] == "V"]
            if not videos:
                raise SmokeBlocked("observations", "manual video missing")
            video = videos[-1]
            if target is not None and video["successful_video_sequence"] >= origin + target:
                path, binding = request_manual_gameplay_screenshot(collector, captures,
                    min(8.0, remaining()), post_transition=keys.post_key)
                result["captures"].append(dict(path=path.as_posix(), sha256=binding["capture_sha256"],
                                               target_frame=target, **binding))
                target = next(pending, None)
            if video["successful_video_sequence"] >= origin + total:
                if target is not None:
                    raise SmokeBlocked("observations", "manual window incomplete or unreleased")
                break
            if frontend_exited(collector.process):
                raise SmokeBlocked("unload", "manual window exited before horizon")
            time.sleep(min(.005, remaining()))
        result["close_record_count"] = len(collector.drain())
        return result
    finally:
        collector.drain = original_drain


def _run_mvs_active_scene_impl(args: argparse.Namespace, schedule: dict[str, object], *,
                               invocation_id: str, manual_handoff=None,
                               audio_control: str | None = None,
                               input_replay: dict | None = None) -> dict[str, object]:
    """Run one private owned frontend case; completion is never scene acceptance.

    schedule={"events": [[relative_video, complete_mask], ...],
              "capture_frames": [nominal_video, ...], "active_frames": N}.
    Relative videos begin at the first observed neutral callback after P1 start.
    Captures carry conservative intervals and actual observed transition times.
    All output here is PRIVATE; the qualification caller projects finite status.
    """
    executable, core, content, identity = validate_inputs(args)
    if identity.get("content_kind") != "selected-mvs":
        raise SmokeBlocked("input", "active scene requires selected MVS content")
    if not isinstance(schedule, dict) or set(schedule) != {"events", "capture_frames", "active_frames"}:
        raise SmokeBlocked("input", "invalid active scene schedule")
    total, events, targets = schedule["active_frames"], schedule["events"], schedule["capture_frames"]
    if (type(total) is not int or not 1 <= total <= 3600 or not isinstance(events, list)
            or not isinstance(targets, list) or not 1 <= len(targets) <= 6 or len(events) > 64
            or any(type(frame) is not int or not 0 <= frame <= total for frame in targets)
            or targets != sorted(set(targets))):
        raise SmokeBlocked("input", "invalid active scene bounds")
    previous = -1
    for event in events:
        if (not isinstance(event, (list, tuple)) or len(event) != 2
                or type(event[0]) is not int or not previous < event[0] <= total
                or type(event[1]) is not int or not 0 <= event[1] <= 1023):
            raise SmokeBlocked("input", "invalid active scene event")
        previous = event[0]
    if type(args.timeout) not in (int, float) or not 0 < args.timeout <= 120:
        raise SmokeBlocked("input", "invalid frontend invocation timeout")
    if audio_control is not None and audio_control not in ("normal", "muted", "disabled"):
        raise SmokeBlocked("audio-route", "unsupported audio route control")
    captures = Path(args.capture_dir).resolve()
    captures.mkdir(parents=True, exist_ok=True)
    if any(captures.iterdir()):
        raise SmokeBlocked("input", "active scene capture directory is not fresh")
    deadline = time.monotonic() + args.timeout
    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise SmokeBlocked("observations", "active scene invocation timed out")
        return value
    with tempfile.TemporaryDirectory(prefix="glueyneo-active-scene-") as temporary:
        work = Path(temporary)
        config = write_frontend_config(work, captures, direct_log=True)
        # Bind the exact launch bytes; frontend exit must not replace this small
        # explicit contract with a serialized defaults/runtime configuration.
        with config.open("a", encoding="utf-8") as configuration:
            configuration.write('config_save_on_exit = "false"\n')
            if manual_handoff is not None or audio_control is not None:
                configuration.write('quit_press_twice = "false"\nthreaded_data_runloop_enable = "false"\ninput_exit_emulator = "escape"\n')
            if audio_control is not None:
                configuration.write('record_driver = "wav"\n')
                configuration.write(f'recording_output_directory = "{captures / "recordings"}"\n')
                configuration.write(f'recording_config_directory = "{work}"\n')
                (captures / "recordings").mkdir()
                configuration.write('audio_enable = "false"\n' if audio_control == "disabled"
                                    else 'audio_enable = "true"\n')
                configuration.write('audio_mute_enable = "true"\n' if audio_control == "muted"
                                    else 'audio_mute_enable = "false"\n')
        launch_configuration = config.read_bytes()
        if not validate_active_config_destinations(launch_configuration.decode("utf-8"), work, captures):
            raise SmokeBlocked("identity", "active scene configuration destinations invalid")
        launch_configuration_sha256 = hashlib.sha256(launch_configuration).hexdigest()
        log, process_log = work / "retroarch.log", work / "process-output.log"
        # File logging is disabled for this active-only lane; retain an explicit
        # empty placeholder alongside the live stderr stream for local diagnosis.
        log.touch()
        # Total frontend safety cap is separate from the requested active
        # horizon and host deadline; capture intervals remain explicitly bounded.
        command = [str(executable), "--verbose", "--max-frames=8192", "--no-patch",
                   "--sram-mode=noload-nosave", "--config", str(config), "-L", str(core), str(content)]
        audio_path = None
        audio_started_ns = None
        if audio_control is not None:
            audio_path = captures / "frontend-audio-callback.wav"
            if audio_path.exists() or audio_path.is_symlink():
                raise SmokeBlocked("audio-capture", "frontend audio capture destination is not fresh")
            command.extend(("--record", str(audio_path)))
        replay_masks = None
        if input_replay is not None:
            if manual_handoff is not None or audio_control is None:
                raise SmokeBlocked("input-replay", "replay requires bounded automated audio control")
            replay_masks = input_replay["masks"]
            replay_origin = input_replay["origin"]
            if (type(replay_origin) is not int or not 1 <= replay_origin < 8192 or
                    not isinstance(replay_masks, list) or len(replay_masks) != replay_origin + total):
                raise SmokeBlocked("input-replay", "invalid replay origin or horizon")
            replay_path = work / "input-only.bsv"
            replay_bytes = mvs_input_replay_bytes(replay_masks + [0] * min(128, 8192-len(replay_masks)),
                                                 dense_from=max(1, replay_origin + targets[0] - 40),
                                                 dense_until=min(len(replay_masks), replay_origin + targets[-1] + 32))
            replay_path.write_bytes(replay_bytes)
            command.extend(("--play-replay", str(replay_path)))
        process = None
        collector = MVSObservationCollector(None, process_log, invocation_id)
        if manual_handoff is None and replay_masks is None:
            collector.expect_mask(0)
        result: dict[str, object] = dict(status="incomplete", invocation_id=invocation_id,
                                         identity=identity, captures=[], observed_events=[],
                                         frontend_log_source="owned-process-stderr")
        preflight_keyboard_posting()
        with process_log.open("wb") as stream, BoundedFrontendLog(stream) as log_sink:
            collector.log_guard = log_sink
            refuse_stacked_launch()
            primary_error = None
            try:
                with launch_window():
                    try:
                        # RA v1.22.2 verbosity.c:287-326 mirrors macOS log lines
                        # to buffered stdout and flushed stderr. Combining them
                        # replays protocol records when stdout's buffer flushes.
                        # https://github.com/libretro/RetroArch/blob/v1.22.2/verbosity.c#L287
                        audio_started_ns = time.time_ns() if audio_control is not None else None
                        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=log_sink.writer,
                                                   start_new_session=True)
                    except OSError as error:
                        raise SmokeBlocked("launch", "pinned active scene frontend could not be started") from error
                    finally:
                        log_sink.close_writer()
                    try:
                        record_child_pid(getattr(args, "child_pid_file", None), process)
                    except OSError as error:
                        raise SmokeBlocked("pid-record", "active scene child PID could not be recorded") from error
                collector.process = process
                def wait_event(kind):
                    while True:
                        records = collector.drain()
                        found = [record for record in records if record["event_kind"] == kind]
                        if found:
                            return found[0]
                        time.sleep(min(0.005, remaining()))
                def latest_video(records):
                    videos = [record for record in records if record["event_kind"] == "V"]
                    if not videos:
                        raise SmokeBlocked("observations", "missing successful callback video")
                    return videos[-1]
                with HeldMVSKeys(process) as keys:
                    if manual_handoff is not None:
                        focus_owned_frontend(process)
                        result.update(_manual_from_boot(collector, keys, captures,
                            total, targets, remaining, manual_handoff))
                    else:
                        def transition(mask):
                            collector.drain()
                            collector.expect_mask(mask)
                            keys.set_mask(mask)
                        # A background RetroArch process can emit one video callback,
                        # then stop advancing before the game reaches readiness. Activate
                        # only this owned process as soon as its window has rendered.
                        wait_event("V")
                        focus_owned_frontend(process)
                        ready = wait_event("R")
                        ready_video = ready["successful_video_sequence"]
                        if replay_masks is None:
                            transition(1)
                            coin = latest_video(collector.wait_for_video(ready_video + 1, 1, remaining()))
                            collector.wait_for_video(coin["successful_video_sequence"] + 8, 1, remaining())
                            transition(0)
                            collector.wait_for_video(ready_video + 600, 0, remaining())
                            transition(2)
                            start = wait_event("P")
                            if start["sampled_mask"] != 2:
                                raise SmokeBlocked("observations", "P1 start lacks requested sampled input")
                            transition(0)
                            origin = latest_video(collector.wait_for_video(start["successful_video_sequence"] + 1,
                                                                            0, remaining()))["successful_video_sequence"]
                        else:
                            start = wait_event("P")
                            origin = replay_origin
                            if start["sampled_mask"] != 2 or start["successful_video_sequence"] >= origin:
                                raise SmokeBlocked("input-replay", "replay start differs from reference")
                            collector.wait_for_video(origin, 0, remaining())
                        result["active_origin_video_sequence"] = origin
                        mask = 0
                        timeline = [(frame, 0, value) for frame, value in events]
                        timeline += [(frame, 1, None) for frame in targets]
                        # Ordinary observation checkpoints may lag by 31 callbacks;
                        # arm the diagnostic burst before the first capture target.
                        timeline.append((max(0, targets[0] - 40), -1, None))
                        for frame, kind, value in sorted(timeline):
                            wait_mask = (replay_masks[min(len(replay_masks), origin + frame)-1]
                                         if replay_masks is not None else mask)
                            records = collector.wait_for_video(max(1, origin + frame), wait_mask, remaining())
                            if kind == -1:
                                if replay_masks is None:
                                    keys.set_observation_burst(True)
                            elif kind == 0:
                                before_video = latest_video(records)["successful_video_sequence"]
                                if replay_masks is None:
                                    transition(value)
                                    observed = latest_video(collector.wait_for_video(before_video + 1, value, remaining()))
                                else:
                                    # Retain a real observed video inside the same frozen
                                    # transition allowance, including redundant neutral events.
                                    observed = latest_video(collector.wait_for_video(before_video + 1, value, remaining()))
                                result["observed_events"].append(dict(target_frame=frame, mask=value,
                                    sample_sequence=observed["sample_sequence"],
                                    successful_video_sequence=observed["successful_video_sequence"]))
                                mask = value
                            else:
                                path, binding = request_active_scene_screenshot(collector, captures, mask,
                                                                                min(10.0, remaining()),
                                                                                post_transition=keys.post_key)
                                result["captures"].append(dict(target_frame=frame, path=path.as_posix(),
                                    sha256=binding["capture_sha256"], **binding))
                                if frame == targets[-1] and replay_masks is None:
                                    keys.set_observation_burst(False)
                        collector.wait_for_video(origin + total, mask, remaining())
                    result["observations"] = collector.drain()
                    if replay_masks is not None:
                        if sampled_mvs_masks(result, len(replay_masks)) != replay_masks:
                            raise SmokeBlocked("input-replay", "actual sampled input differs from replay")
                        result["input_replay"] = dict(policy="pinned_bsv1_input_only", state_bytes=0,
                            neutral_bootstrap_frames=1,
                            sha256=hashlib.sha256(replay_bytes).hexdigest(), frames=len(replay_masks),
                            sampled_masks_sha256=hashlib.sha256(struct.pack("<" + "H" * len(replay_masks), *replay_masks)).hexdigest())
                    if audio_control is not None:
                        keys.set_mask(0)
                        stop_owned_frontend_recording(process, keys, min(8.0, remaining()))
                quit_ok = request_frontend_quit(identity["bundle_id"], process, min(8.0, remaining()))
                code = frontend_returncode(process)
                result["frontend_exit_code"] = code
                if not quit_ok or code != 0:
                    raise SmokeBlocked("unload", "active scene frontend did not exit cleanly")
                try:
                    with config.open("rb") as configuration:
                        unchanged = configuration.read(len(launch_configuration) + 1) == launch_configuration
                except OSError as error:
                    raise SmokeBlocked("identity", "active scene launch configuration unavailable") from error
                if not unchanged:
                    raise SmokeBlocked("identity", "active scene launch configuration changed")
                if audio_control is not None and audio_path is not None and audio_started_ns is not None:
                    finished_ns = time.time_ns()
                    try:
                        audio_receipt = select_frontend_audio_recording(
                            captures, started_ns=audio_started_ns, finished_ns=finished_ns)
                    except SmokeBlocked as error:
                        detail = str(error).lower()
                        reason = ("silent" if "silent" in detail else
                                  "missing" if "missing" in detail else "invalid")
                        audio_receipt = {"status": "unavailable" if reason == "missing" else "fail",
                                         "stage": "frontend_libretro_audio_callback_pre_flush",
                                         "reason": reason,
                                         "format": "pcm_s16le_interleaved_stereo"}
                    try:
                        route_receipt = parse_frontend_audio_route(process_log, control=audio_control)
                    except SmokeBlocked:
                        route_receipt = {"status": "unknown", "control": audio_control,
                                         "driver": "unknown", "driver_initialized": False,
                                         "control_status": "unknown"}
                    try:
                        delivery_receipt = parse_frontend_audio_delivery(process_log)
                    except SmokeBlocked:
                        delivery_receipt = {"status": "unknown", "stage": "adapter_callback_return_totals"}
                    result["audio_evidence"] = {
                        "capture": audio_receipt,
                        "route": route_receipt,
                        "delivery": delivery_receipt,
                        "stage_source": "RetroArch v1.22.2 audio/audio_driver.c recorder-before-flush",
                    }
                # Full decompression/pixel validation happens after the owned
                # frontend exits, preserving the already bound capture intervals.
                for capture in result["captures"]:
                    path = Path(capture["path"])
                    if (decode_png(path)[:2] != (WIDTH, HEIGHT)
                            or sha256(path) != capture["sha256"]):
                        raise SmokeBlocked("video", "active scene capture failed full validation")
                result.update(status="complete", configuration_text=launch_configuration.decode("utf-8"),
                              configuration_work_directory=work.as_posix(),
                              configuration_sha256=launch_configuration_sha256, selected_bundle_sha256=sha256(content),
                              frontend_command=command)
            except SmokeBlocked as error:
                primary_error = error
                diagnostic=getattr(error,"diagnostic",None)
                if not isinstance(diagnostic,dict):
                    diagnostic={}
                if process is not None and error.stage == "observations":
                    diagnostic["failure_process_readbacks"] = _active_scene_process_readbacks(process)
                error.diagnostic={**diagnostic,"status":"incomplete","stage":error.stage,
                                  "failure_reason":str(error)[:256],"invocation_id":invocation_id,
                                  "observations":diagnostic.get(
                                      "observations",[] if collector is None else collector.records),
                                  "captures":diagnostic.get("captures",result["captures"]),
                                  "observed_events":diagnostic.get(
                                      "observed_events",result["observed_events"])}
                raise
            except BaseException as error:
                primary_error = error
                raise
            finally:
                try:
                    if process is not None:
                        try:
                            if getattr(process, "returncode", None) is None:
                                request_frontend_quit(identity["bundle_id"], process, 2.0)
                        finally:
                            kill_launched_group(process)
                finally:
                    log_sink.finish()
                    log_status, _, _ = retain_frontend_logs(log, process_log, stream, captures)
                    try:
                        log_sink.check()
                        if log_status == "fail":
                            raise SmokeBlocked("observations", "frontend log retention budget or runtime failure")
                    except SmokeBlocked as output_error:
                        if primary_error is None:
                            raise
                        # Keep the first fault and its process readbacks. Output
                        # failure is still explicit, including after early exit.
                        if isinstance(primary_error, SmokeBlocked):
                            primary_error.diagnostic["secondary_output_failure"] = str(output_error)[:256]
        return result


def run_smoke(args: argparse.Namespace) -> dict[str, object]:
    executable, core, content, identity = validate_inputs(args)
    acceptance_mode = getattr(args, "acceptance", False) is True
    if acceptance_mode and identity["content_kind"] != "selected-mvs":
        raise SmokeBlocked("input", "acceptance requires selected MVS content")
    with tempfile.TemporaryDirectory(prefix="glueyneo-retroarch-") as temporary:
        work = Path(temporary)
        capture_value = getattr(args, "capture_dir", None) if acceptance_mode else None
        if capture_value is None:
            screenshots = work / "screenshots"
            screenshots.mkdir()
        else:
            screenshots = Path(capture_value).resolve()
            screenshots.mkdir(parents=True, exist_ok=False)
        config = write_frontend_config(work, screenshots, null_audio=True)
        log = work / "retroarch.log"
        process_log = work / "process-output.log"
        prior_crash_reports = crash_report_snapshot()
        started_at = time.time()
        with process_log.open("wb") as log_stream:
            refuse_stacked_launch()
            process = None
            outcome: dict[str, object] = {"observations": []}
            survived_before_screenshot = False
            title_status = "unknown"
            title_results: list[str] = []
            capture_geometry_ok = False
            frontend_exit_code: int | None = None
            try:
                with launch_window():
                    try:
                        frontend_command = [
                            str(executable), "--verbose", "--config", str(config),
                        ]
                        frontend_command.extend([
                            "-L", str(core), str(content),
                        ])
                        process = subprocess.Popen(
                            frontend_command,
                            stdout=log_stream,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )
                    except OSError as error:
                        diagnostic = build_diagnostic(
                            stage="launch", return_code=None, survived_before_screenshot=False,
                            output=str(error), temporary_root=work,
                        )
                        raise SmokeBlocked(
                            "launch", "pinned RetroArch could not be started", diagnostic=diagnostic
                        ) from error
                    # Signals stay deferred around the PID record (T-04-66). A record failure is
                    # not a launch failure (G2WR-06): `process` is already assigned, so the outer
                    # cleanup still quits and reaps the started frontend. The outer handler
                    # builds the single diagnostic; the detail keeps the error class (G3IN-02).
                    try:
                        record_child_pid(getattr(args, "child_pid_file", None), process)
                    except OSError as error:
                        raise SmokeBlocked(
                            "pid-record",
                            f"child PID could not be recorded ({type(error).__name__})",
                        ) from error
                time.sleep(0.5)
                survived_before_screenshot = not frontend_exited(process)
                if acceptance_mode:
                    focus_frontend()
                    wait_for_mvs_video_checkpoint(process, log, args.timeout)
                    capture = request_screenshot(
                        process, screenshots, screenshot_snapshot(screenshots), args.timeout)
                    first_frame = decode_png(capture)
                    if first_frame[:2] != (WIDTH, HEIGHT):
                        raise SmokeBlocked(
                            "video", "selected MVS screenshot geometry is unsupported")
                    title_results.append(recognize_title_capture(capture))
                    title_status = title_recognition_outcome(title_results)
                    capture_geometry_ok = True
                    outcome["input_response"] = "not-classified"
                    outcome["frontend_capture_method"] = "software-screenshot-hotkey"
                    outcome["frontend_frame_boundary"] = "at-least-720-successful-video-frames"
                else:
                    first = request_screenshot(process, screenshots, {}, args.timeout)
                    first_frame = decode_png(first)
                first_marker = right_marker = None
                if acceptance_mode:
                    capture_geometry_ok = capture_geometry_ok and first_frame[:2] == (
                        WIDTH, HEIGHT)
                else:
                    time.sleep(0.25)
                    second = request_screenshot(process, screenshots,
                                                screenshot_snapshot(screenshots),
                                                args.timeout)
                    second_frame = decode_png(second)
                if not acceptance_mode and identity["content_kind"] == "public-fixture":
                    first_marker = find_marker(first_frame)
                    second_marker = find_marker(second_frame)
                    if second_marker != first_marker:
                        raise SmokeBlocked("input", "no-input control changed the guest marker")
                    inject_key(LEFT_KEY_CODE, hold=ARROW_HOLD_SECONDS)
                    time.sleep(0.25)
                    wrong_input = request_screenshot(
                        process, screenshots, screenshot_snapshot(screenshots), args.timeout
                    )
                    wrong_marker = find_marker(decode_png(wrong_input))
                    if wrong_marker != first_marker:
                        raise SmokeBlocked("input", "Left Arrow wrong-input control moved the guest marker")
                    inject_key(RIGHT_KEY_CODE, hold=ARROW_HOLD_SECONDS)
                    time.sleep(0.25)
                    third = request_screenshot(
                        process, screenshots, screenshot_snapshot(screenshots), args.timeout
                    )
                    right_marker = find_marker(decode_png(third))
                    if (right_marker[1] != first_marker[1] or right_marker[2] != first_marker[2]
                            or right_marker[0] <= first_marker[0]):
                        raise SmokeBlocked("input", "mapped Right Arrow did not move the guest marker right")
                    outcome["input_response"] = "observed"
                elif not acceptance_mode:
                    inject_key(RIGHT_KEY_CODE, hold=ARROW_HOLD_SECONDS)
                    request_screenshot(process, screenshots,
                                       screenshot_snapshot(screenshots), args.timeout)
                    outcome["input_response"] = "unknown"

                if not request_frontend_quit(identity["bundle_id"], process, args.timeout):
                    raise SmokeBlocked("unload", "RetroArch did not quit cleanly after loaded content")
                frontend_exit_code = frontend_returncode(process)
                if acceptance_mode and frontend_exit_code != 0:
                    raise SmokeBlocked("unload", "RetroArch did not exit successfully")
                outcome["observations"] = [
                    "RetroArch launched the requested core and content path",
                    ("frontend captured a screenshot through the software screenshot hotkey"
                     if acceptance_mode else "frontend produced bounded screenshots"),
                    ("RetroArch exited through its application quit path after capture"
                     if acceptance_mode else "RetroArch exited through its application quit path"),
                ]
                if not acceptance_mode:
                    outcome["observations"].insert(
                        2, "configured Right Arrow input was injected")
                if acceptance_mode:
                    outcome["observations"].append(
                        "selected MVS screenshot matched 320x224 software-video geometry")
                    outcome["observations"].append(
                        "selected MVS title recognition returned a finite local result")
                elif first_marker is not None and right_marker is not None:
                    outcome["observations"].extend([
                        "frontend screenshot contained the guest marker and black backdrop",
                        "repeated no-input screenshots retained the same marker position",
                        "configured Left Arrow wrong-input control did not move the marker",
                        "configured Right Arrow input moved the marker right",
                    ])
                    outcome["marker_before"] = list(first_marker)
                    outcome["marker_after_right"] = list(right_marker)
                else:
                    outcome["observations"].append("selected-game input response remains unclassified")
                outcome["frontend_unloaded"] = True
            except SmokeBlocked as error:
                if process is None:
                    raise
                return_code = frontend_returncode(process)
                crash_reason = (
                    wait_for_recent_crash_reason(started_at, prior_crash_reports)
                    if return_code is not None and return_code < 0
                    else find_recent_crash_reason(started_at, prior_crash_reports)
                )
                error.diagnostic = build_diagnostic(
                    stage=error.stage,
                    return_code=return_code,
                    survived_before_screenshot=survived_before_screenshot,
                    output=collect_frontend_output(process_log, log, work),
                    temporary_root=work,
                    crash_report=crash_reason,
                )
                raise
            finally:
                try:
                    if process is not None:
                        try:
                            request_frontend_quit(identity["bundle_id"], process, args.timeout)
                        finally:
                            kill_launched_group(process)
                finally:
                    frontend_log_status = "unknown"
                    frontend_log_paths: list[str] = []
                    frontend_log_hashes: list[str] = []
                    if acceptance_mode and capture_value is not None:
                        (frontend_log_status, frontend_log_paths,
                         frontend_log_hashes) = retain_frontend_logs(
                             log, process_log, log_stream, screenshots)
                    active_error = sys.exc_info()[1]
                    diagnostic = getattr(active_error, "diagnostic", None)
                    if isinstance(active_error, SmokeBlocked) and isinstance(diagnostic, dict):
                        diagnostic.update({
                            "frontend_log_status": frontend_log_status,
                            "frontend_log_paths": frontend_log_paths,
                            "frontend_log_sha256": frontend_log_hashes,
                        })
            actual_frontend = (
                frontend_acceptance_outcome(
                    exited_cleanly=(outcome.get("frontend_unloaded") is True and
                                    frontend_exit_code == 0),
                    capture_geometry_ok=capture_geometry_ok,
                    log_outcome=frontend_log_status,
                ) if acceptance_mode else "unknown")
            result_status = (
                "pass" if identity["content_kind"] == "public-fixture" or
                (acceptance_mode and actual_frontend == "pass") else "unknown")
            result: dict[str, object] = {"status": result_status,
                                        "identity": identity, **outcome}
            if acceptance_mode:
                captures = sorted(screenshots.glob("*.png"))
                result["acceptance"] = {
                    "actual_frontend": actual_frontend,
                    "recognizable_title": title_status,
                }
                result["private_evidence"] = {
                    "retroarch_bundle_path": args.retroarch.resolve().as_posix(),
                    "core_path": core.as_posix(),
                    "content_path": content.as_posix(),
                    "identity": identity,
                    "frontend_command": frontend_command,
                    "configuration_path": config.as_posix(),
                    "configuration_sha256": sha256(config),
                    "configuration_text": config.read_text(encoding="utf-8"),
                    "selected_bundle_sha256": sha256(content),
                    "capture_paths": [path.as_posix() for path in captures],
                    "capture_sha256": [sha256(path) for path in captures],
                    "capture_geometry": [list(decode_png(path)[:2])
                                         for path in captures],
                    "title_ocr_executable": TITLE_OCR_EXECUTABLE,
                    "title_result": title_status,
                    "title_capture_results": title_results,
                    "frontend_exit_code": frontend_exit_code,
                    "frontend_capture_method": outcome.get(
                        "frontend_capture_method", "unspecified"),
                    "frontend_frame_boundary": outcome.get(
                        "frontend_frame_boundary", "unmeasured"),
                    "frontend_log_status": frontend_log_status,
                    "frontend_log_paths": frontend_log_paths,
                    "frontend_log_sha256": frontend_log_hashes,
                }
            return result


def _wait_frontend_log_marker(log: Path, marker: bytes, process,
                              deadline: float, stage: str) -> bytes:
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked(stage, "RetroArch exited before the requested frontend event")
        current = read_frontend_log(log)
        if marker in current:
            return current
        time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked(stage, "requested frontend event timed out")


def _wait_mvs_audio_frame_after(log: Path, previous_size: int, process,
                                deadline: float) -> bytes:
    """Require a completed guest observer callback after one frontend input poll."""
    if type(previous_size) is not int or previous_size < 0:
        raise SmokeBlocked("continuation-observations", "invalid observer log offset")
    marker = b"glueyneo: MVS audio frame:"
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked("continuation-observations",
                               "RetroArch exited before the post-command observer frame")
        current = read_frontend_log(log)
        if len(current) < previous_size:
            raise SmokeBlocked("continuation-observations",
                               "frontend observer log shrank after the menu command")
        appended = current[previous_size:]
        start = appended.find(marker)
        if start >= 0:
            end = appended.find(b"\n", start)
            if end > start:
                return appended[start:end]
        time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked("continuation-observations",
                       "no guest observer frame followed the menu-close command")


def _wait_continuation_event_count(log: Path, event: str, count: int,
                                   process, deadline: float,
                                   poll_interval: float = 0.02) -> list[tuple[str, tuple[int, ...]]]:
    if not isinstance(poll_interval, (int, float)) or not 0 < poll_interval <= 0.1:
        raise SmokeBlocked("continuation-observations", "invalid frontend event polling interval")
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked("continuation-observations", "RetroArch exited before the state operation")
        records = continuation_marker_records(read_frontend_log(log))
        if sum(kind == event for kind, _ in records) >= count:
            return records
        time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked("continuation-observations", "frontend state operation was not observed")


def continuation_event_count(log: bytes, event: str) -> int:
    if event not in {"S", "R", "E", "X"}:
        raise SmokeBlocked("continuation-observations", "unsupported continuation event count")
    return sum(kind == event for kind, _ in continuation_marker_records(log))


def _regular_save_ram_outcome(save_ram: bytes) -> str | None:
    if len(save_ram) != 0x10000:
        return None
    offsets = (0, 1, 0x1234, 0x1235, 0xFFFE, 0xFFFF)
    actual = bytes(save_ram[offset] for offset in offsets)
    if actual == bytes((0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC)):
        return "A"
    if actual == bytes((0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6)):
        return "B"
    return None


def validate_final_policy_sram(live_state: bytes,
                               disk_snapshot: dict[str, object] | None,
                               expected_outcome: str) -> dict[str, object]:
    """Compare final live MEM SRAM with the quiescent raw frontend save bytes."""
    if expected_outcome not in {"A", "B"}:
        raise SmokeBlocked("sram-persistence", "invalid final SRAM outcome expectation")
    live_save_ram = extract_mvs_save_ram(live_state)
    live_digest = hashlib.sha256(live_save_ram).hexdigest()
    live_outcome = public_save_guest_sram_outcome(live_state)
    live_guest = public_save_guest_readback(live_state)
    disk_bytes = disk_snapshot.get("bytes") if isinstance(disk_snapshot, dict) else None
    disk_digest = disk_snapshot.get("sha256") if isinstance(disk_snapshot, dict) else None
    disk_outcome = disk_snapshot.get("sram_outcome") if isinstance(disk_snapshot, dict) else None
    result: dict[str, object] = {
        "live_guest_readback": live_guest,
        "live_sram_outcome": live_outcome,
        "live_sram_bytes": len(live_save_ram),
        "live_sram_sha256": live_digest,
        "disk_sram_outcome": disk_outcome,
        "disk_sram_bytes": disk_bytes,
        "disk_sram_sha256": disk_digest,
        "live_disk_bytes_match": (
            disk_bytes == len(live_save_ram) and disk_digest == live_digest),
    }
    if (live_guest != expected_outcome or live_outcome != expected_outcome or
            disk_outcome != expected_outcome or
            result["live_disk_bytes_match"] is not True):
        raise SmokeBlocked(
            "sram-persistence",
            "final live guest SRAM and raw frontend save do not match the expected policy bytes",
            diagnostic=result,
        )
    return result


def validate_focused_reset_state(state: object) -> dict[str, object]:
    """Require the selected A SRAM state without inventing a prior save read."""
    if not isinstance(state, dict) or state.get("sram_outcome") != "A":
        raise SmokeBlocked(
            "state-container",
            "focused actual state lacks the held-A SRAM witness",
            diagnostic={"sram_outcome": (state.get("sram_outcome")
                                          if isinstance(state, dict) else None),
                        "guest_readback": (state.get("guest_readback")
                                           if isinstance(state, dict) else None),
                        "state_container_sha256": (state.get("container_sha256")
                                                    if isinstance(state, dict) else None)},
        )
    return {"sram_outcome": "A", "guest_readback": state.get("guest_readback"),
            "container_sha256": state.get("container_sha256")}


def frontend_sram_snapshot(savefiles: Path) -> dict[str, object] | None:
    """Read the single stable raw SAVE_RAM file without preserving its path."""
    entries = list(savefiles.iterdir())
    if not entries:
        return None
    if len(entries) != 1:
        raise SmokeBlocked("sram-persistence", "save directory does not contain one isolated SRAM file",
                           diagnostic={"entry_count": len(entries)})
    path = entries[0]
    try:
        before = path.lstat()
    except OSError as error:
        raise SmokeBlocked("sram-persistence", "frontend SRAM file changed during enumeration") from error
    if not stat_module.S_ISREG(before.st_mode):
        raise SmokeBlocked("sram-persistence", "frontend SRAM entry is not a regular file")
    data = read_private_regular_file(path, MVS_GNST_BACKUP_RAM_BYTES)
    try:
        after = path.lstat()
    except OSError as error:
        raise SmokeBlocked("sram-persistence", "frontend SRAM file changed after read") from error
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
        raise SmokeBlocked("sram-persistence", "frontend SRAM file changed during snapshot")
    return {"name": path.name, "bytes": len(data), "size": after.st_size,
            "mtime_ns": after.st_mtime_ns,
            "sha256": hashlib.sha256(data).hexdigest(),
            "sram_outcome": _regular_save_ram_outcome(data)}


def validate_periodic_save_update(before: dict[str, object] | None,
                                  after: dict[str, object] | None, *,
                                  owned_process_alive: bool,
                                  initial_outcome: str = "A",
                                  expected_outcome: str = "B") -> dict[str, object]:
    """Require changed expected SRAM bytes while the owned frontend is alive."""
    if type(owned_process_alive) is not bool or before is None or after is None:
        raise SmokeBlocked("periodic-save", "periodic SRAM update lacks a bounded before/after file identity")
    if not owned_process_alive:
        raise SmokeBlocked("periodic-save", "frontend exited before a periodic SRAM update")
    if (before.get("size") != MVS_GNST_BACKUP_RAM_BYTES or
            after.get("size") != MVS_GNST_BACKUP_RAM_BYTES or
            before.get("name") != after.get("name") or
            before.get("sha256") == after.get("sha256") or
            type(before.get("mtime_ns")) is not int or
            type(after.get("mtime_ns")) is not int or
            after["mtime_ns"] <= before["mtime_ns"]):
        raise SmokeBlocked("periodic-save", "SRAM bytes did not change before frontend exit")
    if (before.get("sram_outcome") != initial_outcome or
            after.get("sram_outcome") != expected_outcome):
        raise SmokeBlocked("periodic-save", "pre-exit SRAM bytes do not match the guest branch")
    return {"status": "updated-before-exit", "before_sha256": before["sha256"],
            "after_sha256": after["sha256"], "before_mtime_ns": before["mtime_ns"],
            "after_mtime_ns": after["mtime_ns"], "bytes": after["size"],
            "sram_outcome": after["sram_outcome"], "owned_process_alive": True}


def validate_periodic_seed_file(seed: dict[str, object] | None,
                                snapshot: dict[str, object] | None,
                                expected_outcome: str = "A") -> dict[str, object]:
    """Bind the periodic lane's initial raw file to its actual frontend producer."""
    if not isinstance(seed, dict) or not isinstance(snapshot, dict):
        raise SmokeBlocked("periodic-save", "initial SRAM seed identity is missing")
    digest = seed.get("sha256")
    if (seed.get("status") != "persisted" or seed.get("sram_outcome") != expected_outcome or
            seed.get("bytes") != MVS_GNST_BACKUP_RAM_BYTES or
            not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None or
            snapshot.get("size") != MVS_GNST_BACKUP_RAM_BYTES or
            snapshot.get("sha256") != digest or snapshot.get("sram_outcome") != expected_outcome or
            not isinstance(snapshot.get("name"), str) or not snapshot["name"]):
        raise SmokeBlocked("periodic-save", "initial raw SRAM file does not match the frontend-produced A seed")
    return {"status": "frontend-seed-verified", "sha256": digest,
            "bytes": MVS_GNST_BACKUP_RAM_BYTES, "sram_outcome": expected_outcome,
            "seed_frontend_pid": seed.get("frontend_pid"),
            "savefile_name": snapshot["name"]}


def validate_initial_neutral_guest_frame(records: object) -> dict[str, object]:
    """Require two distinct neutral guest frames before frontend controls."""
    if not isinstance(records, list) or not records:
        raise SmokeBlocked("periodic-save", "fresh periodic frontend has no startup input observations")
    samples = [record for record in records if isinstance(record, dict) and
               record.get("event_kind") == "S"]
    videos = [record for record in records if isinstance(record, dict) and
              record.get("event_kind") == "V"]
    if (len(videos) < CONTINUATION_STARTUP_NEUTRAL_FRAME_COUNT or
            any(sample.get("sampled_mask") != 0 for sample in samples) or
            any(video.get("sampled_mask") != 0 for video in videos) or
            any(type(video.get("successful_video_sequence")) is not int or
                video["successful_video_sequence"] <= 0 for video in videos) or
            any(later["successful_video_sequence"] <= earlier["successful_video_sequence"]
                for earlier, later in zip(videos, videos[1:]))):
        raise SmokeBlocked("periodic-save", "periodic guest received a write input before its startup SRAM read")
    return {"status": "seed-loaded-before-write-input",
            "first_video_sequence": videos[0]["successful_video_sequence"],
            "first_input_mask": 0,
            "neutral_completed_frames": len(videos),
            "neutral_video_sequences": [
                video["successful_video_sequence"]
                for video in videos[:CONTINUATION_STARTUP_NEUTRAL_FRAME_COUNT]],
            "last_neutral_video_sequence": videos[
                CONTINUATION_STARTUP_NEUTRAL_FRAME_COUNT - 1][
                    "successful_video_sequence"]}


def wait_for_initial_neutral_guest_frame(log: Path, process, invocation_id: str,
                                         deadline: float) -> dict[str, object]:
    """Drain the pinned frontend's two-poll startup input flush before controls."""
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked("periodic-save", "frontend exited before its initial guest SRAM read")
        records = parse_latest_mvs_input_epoch(
            read_frontend_log(log).decode("utf-8", errors="replace"),
            invocation_id=invocation_id)
        videos = [record for record in records if record.get("event_kind") == "V"]
        if videos and videos[0].get("sampled_mask") != 0:
            raise SmokeBlocked(
                "periodic-save", "periodic guest received a write input before its startup SRAM read")
        if len(videos) >= CONTINUATION_STARTUP_NEUTRAL_FRAME_COUNT:
            # Pinned 1.22.2 task_content.c issues CMD_EVENT_RESUME after content
            # initialization. retroarch_menu_running_finished(false) sets
            # input_driver_flushing_input=2; runloop.c decrements it only on
            # neutral input polls and clears hotkeys while it remains nonzero.
            # Two distinct successful guest video callbacks therefore drain
            # that startup flush before any stdin or keyboard control is sent.
            startup = validate_initial_neutral_guest_frame(records)
            return {**startup,
                    "observation_epoch": mvs_observation_epoch_count(
                        read_frontend_log(log))}
        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked("periodic-save", "periodic guest did not run a neutral startup frame")


def wait_for_periodic_save_update(savefiles: Path,
                                  before: dict[str, object] | None, process,
                                  expected_outcome: str,
                                  deadline: float) -> dict[str, object]:
    last_snapshot: dict[str, object] | None = None
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked("periodic-save", "frontend exited before a periodic SRAM update")
        current = frontend_sram_snapshot(savefiles)
        if current is not None:
            last_snapshot = current
            if before is not None and current.get("sha256") != before.get("sha256"):
                try:
                    if running_retroarch_pids() != {process.pid}:
                        raise SmokeBlocked("periodic-save", "owned frontend is not the sole live RetroArch writer")
                    return validate_periodic_save_update(
                        before, current, owned_process_alive=True,
                        expected_outcome=expected_outcome)
                except SmokeBlocked as error:
                    if (current.get("size") != MVS_GNST_BACKUP_RAM_BYTES or
                            current.get("sram_outcome") != expected_outcome):
                        time.sleep(min(0.025, max(0.0, deadline - time.monotonic())))
                        continue
                    raise error
        time.sleep(min(0.025, max(0.0, deadline - time.monotonic())))
    if last_snapshot is not None and before is not None:
        validate_periodic_save_update(
            before, last_snapshot, owned_process_alive=True,
            expected_outcome=expected_outcome)
    raise SmokeBlocked("periodic-save", "no matching periodic SRAM update occurred before the deadline")


def _clean_exit_sram(savefiles: Path, *, expected_outcome: str = "A") -> dict[str, object]:
    entries = list(savefiles.iterdir())
    if not entries:
        return {"status": "not_written", "entry_count": 0}
    if len(entries) != 1:
        raise SmokeBlocked(
            "sram-persistence",
            "frontend did not retain one isolated SRAM file on clean exit",
            diagnostic={"entry_count": len(entries)},
        )
    path = entries[0]
    data = read_private_regular_file(path, 0x10000)
    outcome = _regular_save_ram_outcome(data)
    if outcome != expected_outcome:
        return {"status": "unexpected_bytes", "entry_count": 1,
                "sram_outcome": outcome or "unclassified", "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest()}
    return {"status": "persisted", "entry_count": 1,
            "bytes": len(data), "sram_outcome": outcome,
            "sha256": hashlib.sha256(data).hexdigest()}


def _continuation_identity(args: argparse.Namespace,
                           attempt: dict[str, object]) -> tuple[Path, Path, Path, Path,
                                                                  dict[str, str], str, str, str]:
    executable, core, content, identity = validate_inputs(args)
    if identity.get("content_kind") != "selected-mvs":
        raise SmokeBlocked("input", "SRAM continuation requires the original normalized save guest")
    observed_core = args.observed_core.resolve()
    witness = args.witness.resolve()
    if (not observed_core.is_file() or not witness.is_file() or
            observed_core == core or observed_core.stat().st_size == 0 or
            witness.stat().st_size == 0):
        raise SmokeBlocked("identity", "observed core or fresh native witness is missing or mismatched")
    observed_digest = sha256(observed_core)
    witness_digest = sha256(witness)
    content_digest = sha256(content)
    if observed_digest == identity["core_sha256"]:
        raise SmokeBlocked("identity", "observed and production core artifacts are identical")
    identity.update(observed_core_sha256=observed_digest,
                    witness_sha256=witness_digest, content_sha256=content_digest)
    attempt["identity"] = identity
    return (executable, core, content, observed_core, identity,
            observed_digest, witness_digest, content_digest)


def _continuation_work_tree(work: Path, savefiles: Path, *,
                            state_route: bool = True,
                            periodic_save: bool = False,
                            block_sram_overwrite: bool = False,
                            autosave_interval: int = 0) -> tuple[Path, Path]:
    captures = work / "captures"
    savestates = work / "savestates"
    system = work / "system"
    for directory in (captures, savestates, system):
        directory.mkdir(mode=0o700)
    config = write_frontend_config(
        work, captures, savefiles=savefiles, savestates=savestates,
        public_state=state_route, periodic_save=periodic_save,
        stdin_commands=True,
        block_sram_overwrite=block_sram_overwrite,
        autosave_interval=autosave_interval, null_audio=True,
    )
    config_bytes = read_private_regular_file(config, 12 * 1024)
    if not validate_active_config_destinations(
            config_bytes.decode("utf-8"), work, captures,
            savefiles=savefiles, savestates=savestates,
            public_state=state_route, periodic_save=periodic_save,
            stdin_commands=True,
            block_sram_overwrite=block_sram_overwrite,
            autosave_interval=autosave_interval):
        raise SmokeBlocked("identity", "isolated SRAM policy configuration failed its contract")
    return config, captures


def _start_continuation_frontend(args: argparse.Namespace, *, executable: Path,
                                 content: Path, observed_core: Path,
                                 identity: dict[str, str], config: Path,
                                 log: Path, process_log: Path,
                                 observed_digest: str, witness: Path,
                                 witness_digest: str, content_digest: str,
                                 core: Path) -> tuple[subprocess.Popen[bytes], float, str]:
    deadline = time.monotonic() + args.timeout
    config_digest = sha256(config)
    process: subprocess.Popen[bytes] | None = None
    try:
        refuse_stacked_launch()
        preflight_keyboard_posting()
        executable_now, core_now, content_now, identity_now = validate_inputs(args)
        if (executable_now != executable or core_now != core or content_now != content or
                identity_now["retroarch_executable_sha256"] != identity["retroarch_executable_sha256"] or
                sha256(observed_core) != observed_digest or sha256(witness) != witness_digest or
                sha256(content) != content_digest or sha256(core) != identity["core_sha256"] or
                sha256(config) != config_digest):
            raise SmokeBlocked("identity", "frontend evidence inputs changed before the owned launch")
        with process_log.open("wb") as output:
            command = [str(executable), "--verbose", "--config", str(config),
                       "-L", str(observed_core), str(content)]
            with launch_window():
                process = subprocess.Popen(command, stdout=output,
                                           stderr=subprocess.STDOUT,
                                           stdin=subprocess.PIPE,
                                           start_new_session=True)
                process._glueyneo_stdin_commands = True
                process._glueyneo_command_trace = []
                record_child_pid(getattr(args, "child_pid_file", None), process)
        _wait_frontend_log_marker(log, MVS_FRONTEND_LOAD_MARKER.encode(),
                                  process, deadline, "launch")
        if running_retroarch_pids() != {process.pid}:
            raise SmokeBlocked("pre-launch", "owned RetroArch process set changed after launch")
        preflight_keyboard_posting(process=process)
        focus_owned_frontend(process)
        return process, deadline, config_digest
    except BaseException:
        if process is not None:
            try:
                if getattr(process, "returncode", None) is None:
                    request_frontend_quit(identity["bundle_id"], process, 2.0)
            finally:
                kill_launched_group(process)
        raise


class OwnedContinuationFrontend:
    """Scope one private stdin-controlled frontend and all of its cleanup."""

    def __init__(self, args: argparse.Namespace, *, executable: Path,
                 content: Path, observed_core: Path, identity: dict[str, str],
                 config: Path, log: Path, process_log: Path, observed_digest: str,
                 witness: Path, witness_digest: str, content_digest: str,
                 core: Path, failure_root: Path):
        self.args = args
        self.executable = executable
        self.content = content
        self.observed_core = observed_core
        self.identity = identity
        self.config = config
        self.log = log
        self.process_log = process_log
        self.observed_digest = observed_digest
        self.witness = witness
        self.witness_digest = witness_digest
        self.content_digest = content_digest
        self.core = core
        self.failure_root = failure_root
        self.process: subprocess.Popen[bytes] | None = None
        self.deadline = 0.0
        self.config_digest = ""
        self.version = ""
        self.status = ""
        self.exit_code: int | None = None
        self.command_trace: list[str] = []
        self.startup: dict[str, object] | None = None

    def start(self) -> "OwnedContinuationFrontend":
        if self.process is not None:
            raise SmokeBlocked("launch", "owned frontend session was started more than once")
        self.process, self.deadline, self.config_digest = _start_continuation_frontend(
            self.args, executable=self.executable, content=self.content,
            observed_core=self.observed_core, identity=self.identity,
            config=self.config, log=self.log, process_log=self.process_log,
            observed_digest=self.observed_digest, witness=self.witness,
            witness_digest=self.witness_digest, content_digest=self.content_digest,
            core=self.core)
        self.command_trace = self.process._glueyneo_command_trace
        self.process._glueyneo_require_guest_ready = True
        self.process._glueyneo_guest_ready = False
        self.process._glueyneo_cleanup_command_allowed = False
        try:
            self.version = self.query("VERSION")
            if self.version != EXPECTED_VERSION:
                raise SmokeBlocked("identity", "stdin frontend version did not match the pinned build")
            return self
        except BaseException:
            self.cleanup(preserve=True)
            raise

    def __enter__(self) -> "OwnedContinuationFrontend":
        return self.start()

    def ready(self, invocation_id: str) -> dict[str, object]:
        """Establish the one shared neutral guest startup boundary before input."""
        if self.process is None:
            raise SmokeBlocked("launch", "owned frontend session was not started")
        if self.startup is not None:
            return self.startup
        self.startup = wait_for_initial_neutral_guest_frame(
            self.log, self.process, invocation_id, self.deadline)
        self.process._glueyneo_guest_ready = True
        return self.startup

    def send(self, command: str) -> dict[str, object]:
        if self.process is None:
            raise SmokeBlocked("input", "owned frontend session was not started")
        return send_frontend_stdin_command(self.process, command)

    def query(self, command: str) -> str:
        if self.process is None:
            raise SmokeBlocked("input", "owned frontend session was not started")
        before_size = len(read_frontend_log(self.process_log))
        self.send(command)
        return wait_for_frontend_stdin_reply(
            self.process_log, command=command, previous_size=before_size,
            process=self.process, deadline=self.deadline)

    def quit(self, timeout: float) -> int:
        if (self.process is None or
                self.identity.get("bundle_id") != EXPECTED_BUNDLE_IDENTIFIER):
            raise SmokeBlocked("unload", "owned frontend identity is unavailable for stdin quit")
        self.send("QUIT")
        code = reap_frontend(self.process, timeout)
        if code is None:
            raise SmokeBlocked("unload", "frontend did not exit after stdin QUIT")
        if code != 0:
            raise SmokeBlocked("unload", "owned RetroArch frontend returned a failure code")
        if running_retroarch_pids():
            raise SmokeBlocked("unload", "RetroArch process remained after stdin QUIT")
        self.exit_code = int(code)
        self.close_stdin()
        return int(code)

    def close_stdin(self) -> None:
        if self.process is None:
            return
        stream = getattr(self.process, "stdin", None)
        if stream is not None and not getattr(stream, "closed", False):
            try:
                stream.close()
            except OSError:
                pass

    def _fallback_cleanup(self, *, preserve: bool) -> None:
        process = self.process
        if process is None:
            return
        if preserve:
            preserve_continuation_failure_log(self.failure_root, self.log)
        try:
            if not frontend_exited(process):
                try:
                    request_frontend_quit(
                        self.identity["bundle_id"], process, 2.0)
                finally:
                    kill_launched_group(process)
        finally:
            self.close_stdin()
            if self.exit_code is None:
                self.exit_code = frontend_returncode(process)

    def cleanup(self, *, preserve: bool = True) -> None:
        """Reap a failed or abandoned session without hiding its evidence."""
        process = self.process
        if process is None:
            return
        if not frontend_exited(process):
            process._glueyneo_cleanup_command_allowed = True
            try:
                try:
                    self.quit(min(2.0, max(0.1, float(self.args.timeout))))
                except SmokeBlocked:
                    self._fallback_cleanup(preserve=preserve)
            finally:
                process._glueyneo_cleanup_command_allowed = False
            return
        if self.exit_code is None:
            self.exit_code = frontend_returncode(process)
        self.close_stdin()

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if self.process is None:
            return False
        if exc_type is not None:
            self.cleanup(preserve=True)
            return False
        if not frontend_exited(self.process):
            try:
                self.quit(self.args.timeout)
            except SmokeBlocked:
                self.cleanup(preserve=True)
                raise
        else:
            self.exit_code = frontend_returncode(self.process)
            self.close_stdin()
        return False


def _stop_continuation_frontend(process: subprocess.Popen[bytes],
                                bundle_id: str, timeout: float) -> int:
    if bundle_id != EXPECTED_BUNDLE_IDENTIFIER:
        raise SmokeBlocked("unload", "configured frontend exit route has an unexpected application identity")
    if frontend_exited(process):
        code = frontend_returncode(process)
        if code != 0:
            raise SmokeBlocked("unload", "owned RetroArch frontend returned a failure code")
        return int(code)
    # The successful policy transaction closes the source-pinned Quick Menu,
    # then uses RetroArch's configured exit key. Keep that verified path for
    # writeback routes; an app-level quit exited cleanly but wrote no A file in
    # the isolated seed probe.
    with HeldMVSKeys(process) as keys:
        press_owned_key(keys, QUIT_KEY_CODE, KEY_HOLD_SECONDS)
        time.sleep(KEY_GAP_SECONDS)
    if reap_frontend(process, timeout) is None:
        raise SmokeBlocked("unload", "frontend did not exit through its configured quit action")
    code = frontend_returncode(process)
    if code != 0:
        raise SmokeBlocked("unload", "owned RetroArch frontend returned a failure code")
    if running_retroarch_pids():
        raise SmokeBlocked("unload", "RetroArch process remained after the owned frontend exit")
    return int(code)


def _quit_continuation_application(process: subprocess.Popen[bytes],
                                   bundle_id: str, timeout: float) -> int:
    """Quit read-only/periodic routes through the owned application identity."""
    if bundle_id != EXPECTED_BUNDLE_IDENTIFIER:
        raise SmokeBlocked("unload", "application quit has an unexpected frontend identity")
    if frontend_exited(process):
        code = frontend_returncode(process)
        if code != 0:
            raise SmokeBlocked("unload", "owned RetroArch frontend returned a failure code")
        return int(code)
    if not request_frontend_quit(bundle_id, process, timeout):
        raise SmokeBlocked("unload", "frontend did not exit through its application quit action")
    code = frontend_returncode(process)
    if code is None or code != 0:
        raise SmokeBlocked("unload", "owned RetroArch frontend returned a failure code")
    if running_retroarch_pids():
        raise SmokeBlocked("unload", "RetroArch process remained after the owned frontend exit")
    return int(code)


def frontend_stdin_commands_available(process) -> bool:
    return (getattr(process, "_glueyneo_stdin_commands", False) is True and
            getattr(process, "stdin", None) is not None)


def native_save_state_menu_script(pid: int) -> str:
    """Build the pinned macOS menu path for RetroArch's native Save State action."""
    return native_state_menu_script(pid, "Save State")


def native_state_menu_script(pid: int, action: str) -> str:
    """Build a pinned native menu action for the current savestate slot."""
    if type(pid) is not int or pid <= 0:
        raise SmokeBlocked("input", "invalid RetroArch process for native state menu")
    if not isinstance(action, str) or action not in {"Save State", "Load State"}:
        raise SmokeBlocked("input", "unsupported RetroArch native state menu action")
    quote = chr(34)
    return "\n".join((
        "tell application " + quote + "System Events" + quote,
        "  tell first process whose unix id is " + str(pid),
        *_native_menu_dismissal_setup_lines(),
        "    click menu bar item " + quote + "Command" + quote + " of menu bar 1",
        "    delay 0.2",
        "    click menu item " + quote + action + quote + " of menu 1 of menu item " +
        quote + "Save State Options" + quote + " of menu 1 of menu bar item " +
        quote + "Command" + quote + " of menu bar 1",
        _native_menu_dismissal_click_line(),
        "  end tell",
        "end tell",
    ))


def _native_menu_dismissal_setup_lines() -> tuple[str, ...]:
    """Capture the owned window center before native menu tracking starts."""
    return (
        "    set dismissWindow to window 1",
        "    set dismissPosition to position of dismissWindow",
        "    set dismissSize to size of dismissWindow",
        "    set dismissX to (item 1 of dismissPosition) + ((item 1 of dismissSize) / 2)",
        "    set dismissY to (item 2 of dismissPosition) + ((item 2 of dismissSize) / 2)",
    )


def _native_menu_dismissal_click_line() -> str:
    """Dismiss AppKit menu tracking with the previously captured center."""
    return "    click at {dismissX, dismissY}"


def native_reset_menu_script(pid: int) -> str:
    """Build the accessible pinned Command > Reset action for the owned app."""
    if type(pid) is not int or pid <= 0:
        raise SmokeBlocked("input", "invalid RetroArch process for native Reset menu")
    quote = chr(34)
    return "\n".join((
        "tell application " + quote + "System Events" + quote,
        "  tell first process whose unix id is " + str(pid),
        *_native_menu_dismissal_setup_lines(),
        "    set commandMenuBarItem to menu bar item " + quote + "Command" +
        quote + " of menu bar 1",
        "    click commandMenuBarItem",
        "    delay 0.2",
        "    click menu item " + quote + "Reset" + quote + " of menu 1 of menu bar item " +
        quote + "Command" + quote + " of menu bar 1",
        "    return " + quote + "MENU_WINDOW_GEOMETRY=" + quote +
        " & ((item 1 of dismissPosition as integer) as text) & " + quote + "," + quote +
        " & ((item 2 of dismissPosition as integer) as text) & " + quote + "," + quote +
        " & ((item 1 of dismissSize as integer) as text) & " + quote + "," + quote +
        " & ((item 2 of dismissSize as integer) as text) & linefeed & " +
        quote + "RESET_MENU_CONFIRMED" + quote,
        "  end tell",
        "end tell",
    ))


def invoke_native_reset_menu(process, *, log: Path | None = None) -> dict[str, object]:
    """Trigger a pinned Reset action; an observer epoch proves delivery."""
    if frontend_exited(process):
        raise SmokeBlocked("input", "RetroArch exited before native Reset menu action")
    if frontend_stdin_commands_available(process):
        command = send_frontend_stdin_command(process, "RESET")
        return {"activation": "pinned stdin RESET command", "command": command,
                "pending_sample": {"status": "not-applicable"}}
    pid = getattr(process, "pid", None)
    script = native_reset_menu_script(pid)
    if frontmost_pid() != pid:
        raise SmokeBlocked("input", "RetroArch is not frontmost for native Reset menu action")
    started = time.monotonic()
    command = ["/usr/bin/osascript", "-e", script]
    try:
        action = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pending_sample: dict[str, object] = {"status": "not-pending"}
        try:
            stdout, stderr = action.communicate(
                timeout=min(RESET_PENDING_SAMPLE_DELAY_SECONDS,
                            NATIVE_MENU_ACTION_TIMEOUT_SECONDS))
        except subprocess.TimeoutExpired:
            pending_sample = (
                take_owned_process_sample(process, log.parent)
                if log is not None else {"status": "sample-context-unavailable"})
            remaining = max(0.0, NATIVE_MENU_ACTION_TIMEOUT_SECONDS -
                            (time.monotonic() - started))
            stdout, stderr = action.communicate(timeout=remaining)
    except subprocess.TimeoutExpired as error:
        action.kill()
        stdout, stderr = action.communicate()
        raise SmokeBlocked(
            "input", "RetroArch native Reset menu action timed out",
            diagnostic={"pending_sample": pending_sample,
                        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                        "stderr_sha256": hashlib.sha256(stderr).hexdigest()},
        ) from error
    except (OSError, subprocess.SubprocessError) as error:
        raise SmokeBlocked("input", "RetroArch native Reset menu action could not run") from error
    if action.returncode != 0:
        raise SmokeBlocked(
            "input", "RetroArch native Reset menu action failed",
            diagnostic={"return_code": action.returncode,
                        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
                        "stderr_summary": sanitize_diagnostic_text(
                            stderr.decode("utf-8", errors="replace"),
                            temporary_root=log.parent if log is not None else None),
                        "pending_sample": pending_sample},
        )
    try:
        output_lines = stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        output_lines = []
    geometry_match = (re.fullmatch(
        r"MENU_WINDOW_GEOMETRY=(-?\d+),(-?\d+),(\d+),(\d+)", output_lines[0])
                    if len(output_lines) == 2 else None)
    if geometry_match is None or output_lines[1] != "RESET_MENU_CONFIRMED":
        raise SmokeBlocked("input", "RetroArch native Reset menu selection was not confirmed",
                           diagnostic={"stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                                       "pending_sample": pending_sample})
    window_x, window_y, window_width, window_height = (
        int(value) for value in geometry_match.groups())
    window_position = (window_x, window_y)
    window_size = (window_width, window_height)
    center_x, center_y = window_relative_point_to_global(
        (window_width // 2, window_height // 2), window_position, window_size)
    try:
        # System Events can become the foreground process while selecting a
        # native menu item. Reacquire only the owned PID, then let the click
        # helper verify foreground again before posting any global event.
        focus_owned_frontend(process)
        mouse_event_probe = post_owned_mouse_click(pid, center_x, center_y)
    except (OSError, AttributeError, ValueError) as error:
        raise SmokeBlocked(
            "input", "macOS could not dismiss native Reset menu tracking",
            diagnostic={"window_position_global": list(window_position),
                        "window_size": list(window_size),
                        "window_center_global": [center_x, center_y],
                        "pending_sample": pending_sample},
        ) from error
    return {"menu_bar_item": "Command", "item": "Reset",
            "activation": "accessible menu-item click returned",
            "dismissal": "frontmost-owned global HID click posted",
            "window_position_global": list(window_position),
            "window_size": list(window_size),
            "window_center_global": [center_x, center_y],
            "mouse_event_probe": mouse_event_probe,
            "pending_sample": pending_sample}


def invoke_native_save_state_menu(process) -> None:
    """Request a real frontend state save through stdin or the pinned menu."""
    invoke_native_state_menu(process, "Save State")


def invoke_native_load_state_menu(process) -> None:
    """Use the pinned app's accessible Command menu to load the selected slot."""
    invoke_native_state_menu(process, "Load State")


def invoke_native_state_menu(process, action: str) -> None:
    """Run a whitelisted native save/load action against the owned process."""
    if frontend_exited(process):
        raise SmokeBlocked("input", "RetroArch exited before native state menu action")
    if frontend_stdin_commands_available(process):
        token = {"Save State": "SAVE_STATE", "Load State": "LOAD_STATE"}.get(action)
        if token is None:
            raise SmokeBlocked("input", "unsupported RetroArch native state menu action")
        send_frontend_stdin_command(process, token)
        return
    pid = getattr(process, "pid", None)
    script = native_state_menu_script(pid, action)
    focus_owned_frontend(process)
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            check=False, timeout=NATIVE_MENU_ACTION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SmokeBlocked("input", "RetroArch native state menu action could not run") from error
    if result.returncode != 0:
        raise SmokeBlocked(
            "input", "RetroArch native state menu action failed",
            diagnostic={"return_code": result.returncode,
                        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()},
        )


def _save_state_file(keys: "HeldMVSKeys", log: Path,
                     savestates: Path, count: int, started_ns: int,
                     process, deadline: float, *, via_native_menu: bool = False,
                     event_count: int | None = None) -> list[dict[str, object]]:
    if (type(via_native_menu) is not bool or
            (event_count is not None and
             (type(event_count) is not int or event_count <= 0))):
        raise SmokeBlocked("input", "invalid state-save trigger")
    previous = public_state_file_identity_snapshot(savestates)
    requested_events = count if event_count is None else event_count
    if via_native_menu:
        invoke_native_save_state_menu(process)
    else:
        press_owned_key(keys, SAVE_STATE_KEY_CODE, KEY_HOLD_SECONDS)
    records = _wait_continuation_event_count(
        log, "S", requested_events, process, deadline)
    state_records = [values for kind, values in records if kind == "S"]
    if (len(state_records) < requested_events or
            state_records[requested_events - 1][1] == 0):
        raise SmokeBlocked("continuation-observations", "frontend state save lacked a completed-frame boundary")
    states, changed = wait_for_changed_public_state_files(
        savestates, count, started_ns, previous, deadline)
    if len(changed) != 1:
        raise SmokeBlocked(
            "state-container", "state-save completion lacks one changed slot identity")
    changed_names = set(changed)
    for state in states:
        state["save_file_changed"] = state["name"] in changed_names
    return states


def _run_fresh_sram_reader(args: argparse.Namespace, *, base: Path,
                           savefiles: Path, executable: Path, core: Path,
                           content: Path, observed_core: Path,
                           identity: dict[str, str], observed_digest: str,
                           witness: Path, witness_digest: str,
                           content_digest: str, expected: str) -> dict[str, object]:
    before = frontend_sram_snapshot(savefiles)
    if before is None or before.get("sram_outcome") != expected:
        raise SmokeBlocked("sram-persistence", "fresh reader has no matching raw SRAM input")
    work = base / f"reader-{hashlib.sha256(os.urandom(16)).hexdigest()[:12]}"
    work.mkdir(mode=0o700)
    config, captures = _continuation_work_tree(work, savefiles)
    log = work / "retroarch.log"
    process_log = work / "process-output.log"
    owner = OwnedContinuationFrontend(
        args, executable=executable, content=content,
        observed_core=observed_core, identity=identity, config=config,
        log=log, process_log=process_log, observed_digest=observed_digest,
        witness=witness, witness_digest=witness_digest,
        content_digest=content_digest, core=core, failure_root=base)
    process: subprocess.Popen[bytes] | None = None
    exit_code: int | None = None
    invocation = hashlib.sha256(os.urandom(24)).hexdigest()[:24]
    try:
        owner.start()
        process = owner.process
        if process is None:
            raise SmokeBlocked("launch", "owned fresh-reader frontend did not start")
        deadline = owner.deadline
        config_digest = owner.config_digest
        startup = owner.ready(invocation)
        with HeldMVSKeys(process) as keys:
            first_read = reset_guest_under_mask(keys, 0, log, process,
                                                invocation, deadline,
                                                via_native_menu=True)
            input_records = parse_latest_mvs_input_epoch(
                read_frontend_log(log).decode("utf-8", errors="replace"),
                invocation_id=invocation)
            if (not input_records or
                    any(item["sampled_mask"] != 0 for item in input_records)):
                raise SmokeBlocked("sram-consumption", "fresh process sampled an SRAM write input before readback")
            states = _save_state_file(
                keys, log, work / "savestates", 1, time.time_ns(),
                process, deadline, via_native_menu=True)
            state = states[0]
            if (state["sram_outcome"] != expected or
                    state.get("guest_readback") != expected):
                raise SmokeBlocked("sram-consumption", "fresh guest readback does not match the saved SRAM bytes")
        if sha256(config) != config_digest:
            raise SmokeBlocked("identity", "fresh-reader configuration changed during execution")
        exit_code = owner.quit(args.timeout)
    finally:
        owner.cleanup()
        if process is not None and exit_code is None:
            exit_code = owner.exit_code
    if exit_code != 0:
        raise SmokeBlocked("unload", "fresh SRAM reader did not exit cleanly")
    after = frontend_sram_snapshot(savefiles)
    if after is None or after.get("sha256") != before.get("sha256"):
        raise SmokeBlocked("sram-consumption", "read-only fresh guest changed the persisted SRAM bytes")
    return {"status": "consumed-before-write", "pid": process.pid,
            "input_mask": 0, "input_samples": len(input_records),
            "startup_observation_epoch": startup["observation_epoch"],
            "reset_action": first_read["reset_action"],
            "reset_video_sequence": first_read["successful_video_sequence"],
            "state_container_sha256": state["container_sha256"],
            "guest_readback": state["guest_readback"],
            "sram_sha256": after["sha256"], "frontend_exit_code": exit_code}


def _run_sram_policy_case(args: argparse.Namespace, *, base: Path,
                          executable: Path, core: Path, content: Path,
                          observed_core: Path, identity: dict[str, str],
                          observed_digest: str, witness: Path,
                          witness_digest: str, content_digest: str,
                          block_sram_overwrite: bool) -> dict[str, object]:
    policy = "preserve-current" if block_sram_overwrite else "restore-history"
    run_id = hashlib.sha256(os.urandom(16)).hexdigest()[:12]
    work = base / f"policy-{policy}-{run_id}"
    work.mkdir(mode=0o700)
    savefiles = work / "savefiles"
    savefiles.mkdir(mode=0o700)
    seed = _run_sram_seed_frontend(
        args, base=base, run_id=f"policy-{run_id}", executable=executable,
        core=core, content=content, observed_core=observed_core,
        identity=identity, observed_digest=observed_digest, witness=witness,
        witness_digest=witness_digest, content_digest=content_digest,
        savefiles=savefiles)
    config_work = work / "writer"
    config_work.mkdir(mode=0o700)
    config, captures = _continuation_work_tree(
        config_work, savefiles, block_sram_overwrite=block_sram_overwrite)
    savestates = config_work / "savestates"
    config_bytes = read_private_regular_file(config, 12 * 1024)
    config_digest = hashlib.sha256(config_bytes).hexdigest()
    if not validate_active_config_destinations(
            config_bytes.decode("utf-8"), config_work, captures,
            savefiles=savefiles, savestates=savestates, public_state=True,
            block_sram_overwrite=block_sram_overwrite, autosave_interval=0):
        raise SmokeBlocked("operation-matrix", "effective SRAM policy configuration failed validation")
    log = config_work / "retroarch.log"
    process_log = config_work / "process-output.log"
    invocation = hashlib.sha256(os.urandom(24)).hexdigest()[:24]
    owner = OwnedContinuationFrontend(
        args, executable=executable, content=content,
        observed_core=observed_core, identity=identity, config=config,
        log=log, process_log=process_log, observed_digest=observed_digest,
        witness=witness, witness_digest=witness_digest,
        content_digest=content_digest, core=core, failure_root=base)
    process: subprocess.Popen[bytes] | None = None
    exit_code: int | None = None
    observations: dict[str, object] | None = None
    try:
        owner.start()
        process = owner.process
        if process is None:
            raise SmokeBlocked("launch", "owned policy frontend did not start")
        deadline = owner.deadline
        launched_config_digest = owner.config_digest
        if launched_config_digest != config_digest:
            raise SmokeBlocked("identity", "launch configuration identity changed")
        startup = owner.ready(invocation)
        with HeldMVSKeys(process) as keys:
            branch_a = reset_guest_under_mask(keys, 64, log, process,
                                              invocation, deadline,
                                              via_native_menu=True)
            if (branch_a.get("sampled_mask") != 64 or
                    branch_a.get("observation_epoch", 0) <=
                    startup.get("observation_epoch", 0)):
                raise SmokeBlocked(
                    "continuation-observations",
                    "A policy branch lacks a new reset epoch under held A")
            keys.set_mask(0)
            state_started_ns = time.time_ns()
            state_a_candidates = _save_state_file(
                keys, log, savestates, 1, state_started_ns, process, deadline,
                via_native_menu=True)
            state_a = state_a_candidates[0]
            if state_a["sram_outcome"] != "A" or state_a["guest_readback"] != "A":
                raise SmokeBlocked("state-container", "actual A save state lacks matching SRAM and guest effects")
            state_a_capture = state_a

            branch_b = reset_guest_under_mask(keys, 128, log, process,
                                              invocation, deadline,
                                              via_native_menu=True)
            keys.set_mask(0)
            press_owned_key(keys, STATE_SLOT_INCREASE_KEY_CODE, KEY_HOLD_SECONDS)
            states = _save_state_file(
                keys, log, savestates, 2, state_started_ns, process, deadline,
                via_native_menu=True)
            state_a = next((item for item in states if item["sram_outcome"] == "A"), None)
            state_b = next((item for item in states if item["sram_outcome"] == "B"), None)
            if (state_a is None or state_b is None or
                    state_a["container_sha256"] == state_b["container_sha256"] or
                    state_a["container_sha256"] != state_a_capture["container_sha256"] or
                    state_a["mem_sha256"] != state_a_capture["mem_sha256"] or
                    state_a["guest_readback"] != "A" or state_b["guest_readback"] != "B"):
                raise SmokeBlocked("state-container", "actual A/B state files are not distinguishable")
            if (state_a["name"] != f"{content.stem}.state" or
                    state_b["name"] != f"{content.stem}.state1"):
                raise SmokeBlocked(
                    "state-container",
                    "actual A/B frontend state files do not match pinned slots 0 and 1")

            # Pause, select the historical A state, then serialize while paused
            # to observe RetroArch's effective policy copy before later input.
            press_owned_menu_key(keys, PAUSE_KEY_CODE)
            press_owned_menu_key(keys, STATE_SLOT_DECREASE_KEY_CODE)
            invoke_native_load_state_menu(process)
            wait_for_continuation_restore_states(log, 1, process, deadline)
            # RetroArch has returned to slot 0 with the loaded historical A
            # state. Snapshot the post-load policy result over that same file;
            # the original A/B containers are already retained in memory. A
            # LOAD_STATE command first serializes the undo buffer, so count
            # state saves only after its restore marker before waiting for this
            # separate post-load snapshot.
            postload_save_baseline = continuation_event_count(
                read_frontend_log(log), "S")
            state_candidates = _save_state_file(
                keys, log, savestates, 2, state_started_ns, process, deadline,
                via_native_menu=True, event_count=postload_save_baseline + 1)
            postload = [item for item in state_candidates if item["name"] == state_a["name"]]
            if len(postload) != 1 or postload[0]["guest_readback"] != "A":
                raise SmokeBlocked("state-container", "effective post-load state snapshot is missing")
            effective = postload[0]
            requested_future_masks = (0, 64, 128, 32)
            keys.set_mask(0)
            for index, mask in enumerate(requested_future_masks):
                keys.set_mask(mask)
                press_owned_key(keys, FRAME_ADVANCE_KEY_CODE)
                wait_for_continuation_frame(log, index + 1, process, deadline)
                time.sleep(FRAME_ADVANCE_RELEASE_SECONDS)
            keys.set_mask(0)
            press_owned_key(keys, PAUSE_KEY_CODE)
            load_log = read_frontend_log(log)
            try:
                observations = parse_continuation_observations(load_log)
            except SmokeBlocked:
                preserve_continuation_failure_log(base, log)
                raise
            if ([frame["input_mask"] for frame in observations["frames"]] !=
                    list(requested_future_masks) or len(observations["paused_states"]) != 1):
                raise SmokeBlocked(
                    "continuation-observations",
                    "load policy input or effective state evidence differs",
                    diagnostic={
                        "expected_input_masks": list(requested_future_masks),
                        "observed_input_masks": [frame["input_mask"]
                                                 for frame in observations["frames"]],
                        "paused_state_count": len(observations["paused_states"]),
                    },
                )
            loaded_state = observations["restore"]["state"]
            if loaded_state != state_a_capture["mem"]:
                raise SmokeBlocked(
                    "continuation-observations",
                    "load payload does not match the exact captured A state file MEM",
                    diagnostic={
                        "state_a_container_sha256": state_a_capture["container_sha256"],
                        "state_a_mem_sha256": state_a_capture["mem_sha256"],
                        "load_payload_sha256": hashlib.sha256(loaded_state).hexdigest(),
                    },
                )
            require_matching_frontend_mem(loaded_state, state_a["mem"])
            if not block_sram_overwrite:
                if effective.get("save_file_changed") is not True:
                    raise SmokeBlocked(
                        "state-container", "post-load state file was not rewritten by its Save State event")
                require_matching_frontend_mem(effective["mem"], state_a["mem"])
                policy_claim = "historical SRAM and machine state restored"
            else:
                expected_hybrid = native_state_with_save_ram(state_a["mem"], state_b["mem"])
                effective_machine_matches = (
                    native_state_without_save_ram(effective["mem"]) ==
                    native_state_without_save_ram(expected_hybrid))
                effective_sram_matches = (
                    extract_mvs_save_ram(effective["mem"]) ==
                    extract_mvs_save_ram(state_b["mem"]))
                if (effective.get("save_file_changed") is not True or
                        not effective_machine_matches or not effective_sram_matches):
                    raise SmokeBlocked(
                        "continuation-observations",
                        "preserve-current route did not produce the expected hybrid",
                        diagnostic={
                            "state_a_container_sha256": state_a_capture["container_sha256"],
                            "state_a_mem_sha256": state_a_capture["mem_sha256"],
                            "state_b_container_sha256": state_b["container_sha256"],
                            "load_payload_sha256": hashlib.sha256(loaded_state).hexdigest(),
                            "load_payload_matches_captured_a_mem": True,
                            "postload_state_container_sha256": effective["container_sha256"],
                            "postload_state_mem_sha256": effective["mem_sha256"],
                            "postload_state_file_changed_after_save_event":
                                effective.get("save_file_changed") is True,
                            "postload_machine_matches_hybrid": effective_machine_matches,
                            "postload_sram_matches_current_b": effective_sram_matches,
                        },
                    )
                policy_claim = "historical machine state with current SRAM retained; exact historical output withheld"
            witness_result = invoke_frontend_native_witness(
                witness, content, effective["mem"], observations, config_work,
                f"actual-{policy}")

            # The pinned 1.22.2 display-list source places these five rows in
            # the exact order below. The config hides every earlier Quick Menu
            # item and the nested savestate submenu, so four Down presses from
            # the initial State Slot row select Undo Load State.
            activate_owned_menu_item(keys, UNDO_LOAD_MENU_DOWN_PRESSES)
            restores = wait_for_continuation_restore_states(log, 2, process, deadline)
            final_log = read_frontend_log(log)
            undo_evidence = validate_undo_load_restore_history(restores, state_a["mem"])
            menu_close_baseline = len(read_frontend_log(log))
            menu_close = wait_for_owned_quick_menu_release(
                process, log, menu_close_baseline, deadline)
            # Capture actual live MEM after Undo Load State, independently of
            # the retro_unserialize payload. The retained A bytes are already
            # in memory, so reuse slot 0 rather than relying on another hotkey
            # slot change while the frontend returns from its menu.
            final_states = _save_state_file(
                keys, log, savestates, 2, state_started_ns, process, deadline,
                via_native_menu=True, event_count=6)
            final_live_states = [item for item in final_states
                                 if item["name"] == state_a["name"] and
                                 item.get("save_file_changed") is True and
                                 item["container_sha256"] != state_a["container_sha256"]]
            if (len(final_live_states) != 1 or
                    final_live_states[0]["guest_readback"] != "B" or
                    final_live_states[0]["sram_outcome"] != "B"):
                raise SmokeBlocked(
                    "sram-persistence",
                    "new frontend state immediately before quit did not contain live B guest/SRAM",
                    diagnostic={
                    "final_state_count": len(final_live_states),
                        "live_guest_readback": (final_live_states[0]["guest_readback"]
                                                if final_live_states else None),
                        "live_sram_outcome": (final_live_states[0]["sram_outcome"]
                                              if final_live_states else None),
                    },
                )
            final_live_state = final_live_states[0]

        if sha256(config) != config_digest or sha256(content) != content_digest or \
                sha256(observed_core) != observed_digest or sha256(witness) != witness_digest:
            raise SmokeBlocked("identity", "SRAM policy evidence input changed during execution")
        exit_code = owner.quit(args.timeout)
    except SmokeBlocked:
        preserve_continuation_failure_log(base, log)
        raise
    finally:
        owner.cleanup()
        if process is not None and exit_code is None:
            exit_code = owner.exit_code
    if exit_code != 0:
        raise SmokeBlocked("unload", "SRAM policy frontend did not exit cleanly")
    sram_exit = _clean_exit_sram(savefiles, expected_outcome="B")
    raw_after_exit = frontend_sram_snapshot(savefiles)
    try:
        final_sram_evidence = validate_final_policy_sram(
            final_live_state["mem"], raw_after_exit, "B")
    except SmokeBlocked as error:
        raise SmokeBlocked(
            "sram-persistence",
            "clean-exit raw SRAM differs from the new native MEM state captured before quit",
            diagnostic={"clean_exit_snapshot": sram_exit,
                        "final_live_disk_comparison": error.diagnostic},
        ) from error
    if (sram_exit.get("status") != "persisted" or raw_after_exit is None or
            raw_after_exit.get("sha256") != sram_exit.get("sha256")):
        raise SmokeBlocked(
            "sram-persistence", "clean-exit SRAM identity changed before fresh consumption",
            diagnostic={"clean_exit_snapshot": sram_exit,
                        "quiescent_snapshot_sha256": (raw_after_exit.get("sha256")
                                                       if raw_after_exit else None),
                        "final_live_state_sha256": final_live_state["mem_sha256"]},
        )
    reader = _run_fresh_sram_reader(
        args, base=base, savefiles=savefiles, executable=executable, core=core,
        content=content, observed_core=observed_core, identity=identity,
        observed_digest=observed_digest, witness=witness,
        witness_digest=witness_digest, content_digest=content_digest,
        expected="B")
    final_log = read_frontend_log(log)
    restores = parse_continuation_restore_states(final_log)
    queries = parse_frontend_save_ram_queries(final_log)
    raw_after_reader = frontend_sram_snapshot(savefiles)
    if raw_after_reader is None or raw_after_reader["sha256"] != sram_exit["sha256"]:
        raise SmokeBlocked("sram-persistence", "raw SRAM identity changed across quiescent teardown")
    return {
        "status": "pass", "policy": policy, "block_sram_overwrite": block_sram_overwrite,
        "startup_observation_epoch": startup["observation_epoch"],
        "reset_observation_epochs": [branch_a["observation_epoch"],
                                     branch_b["observation_epoch"]],
        "reset_action": branch_a["reset_action"],
        "reset_menu_diagnostics": [
            {"menu": branch_a.get("reset_menu_probe"),
             "pending_sample": branch_a.get("reset_pending_sample")},
            {"menu": branch_b.get("reset_menu_probe"),
             "pending_sample": branch_b.get("reset_pending_sample")}],
        "state_menu_actions": {
            "save": "RetroArch stdin SAVE_STATE",
            "load": "RetroArch stdin LOAD_STATE",
        },
        "state_slots": {"A": {"slot": 0, "file": state_a["name"]},
                        "B": {"slot": 1, "file": state_b["name"]},
                        "policy_load": 0},
        "claim": policy_claim, "identity": identity,
        "sram_seed": seed,
        "state_a_sha256": state_a["container_sha256"],
        "state_a_captured_file": {
            "container_sha256": state_a_capture["container_sha256"],
            "mem_sha256": state_a_capture["mem_sha256"],
            "rewritten_by_save_event": state_a_capture.get("save_file_changed") is True,
        },
        "state_b_sha256": state_b["container_sha256"],
        "load_payload_sha256": hashlib.sha256(restores[0]).hexdigest(),
        "load_payload_matches_captured_a_mem": restores[0] == state_a_capture["mem"],
        "undo_load_payload_sha256": hashlib.sha256(restores[1]).hexdigest(),
        "effective_state_sha256": effective["mem_sha256"],
        "effective_state_file": {
            "container_sha256": effective["container_sha256"],
            "mem_sha256": effective["mem_sha256"],
            "rewritten_by_postload_save_event": effective.get("save_file_changed") is True,
        },
        "effective_sram": public_save_guest_sram_outcome(effective["mem"]),
        "effective_guest_readback": effective["guest_readback"],
        "undo_kind": "Quick Menu Undo Load State; Undo Save State not selected",
            "undo_menu_close": menu_close,
        "undo_guest_readback": undo_evidence["undo_guest_readback"],
        "undo_sram_outcome": undo_evidence["undo_sram_outcome"],
        "undo_distinct_non_sram_machine_state": undo_evidence[
            "distinct_non_sram_machine_state"],
        "final_live_state": {
            "slot": state_a["name"],
            "container_sha256": final_live_state["container_sha256"],
            "native_mem_sha256": final_live_state["mem_sha256"],
            "guest_readback": final_live_state["guest_readback"],
            "sram_outcome": final_live_state["sram_outcome"],
            "sram_sha256": hashlib.sha256(
                extract_mvs_save_ram(final_live_state["mem"])).hexdigest(),
        },
        "native_witness": witness_result,
        "frontend_save_ram_queries": queries,
        "retained_sram_ordering": {
            "save_ram_queries_precede_first_restore": final_log.find(b"frontend queried MVS SAVE_RAM data") < final_log.find(b"continuation R "),
            "restore_count": len(restores), "frontend_exit_code": exit_code,
            "raw_file_read_after_frontend_exit": True,
            "fresh_frontend_pid": reader["pid"],
            "fresh_guest_consumed_before_write": reader["status"] == "consumed-before-write",
        },
        "sram_exit": sram_exit, "final_live_disk_comparison": final_sram_evidence,
        "fresh_reader": reader,
        "input_probes": {"save_a_video": branch_a["successful_video_sequence"],
                         "save_b_video": branch_b["successful_video_sequence"]},
    }


def run_sram_policies(args: argparse.Namespace) -> dict[str, object]:
    validate_continuation_operation_matrix(
        "sram-policies", state_operations=True, autosave_interval=0,
        external_sram_write=False)
    base, report_path = private_public_state_workspace(getattr(args, "report", None))
    attempt: dict[str, object] = {"schema_version": 1, "mode": "sram-policies",
                                  "status": "running",
                                  "invocation_id": hashlib.sha256(os.urandom(24)).hexdigest()[:24]}
    try:
        executable, core, content, observed_core, identity, observed_digest, \
            witness_digest, content_digest = _continuation_identity(args, attempt)
        # Match the proven public-state lane: an isolated production-core
        # invocation establishes normal content loading/unloading before the
        # observed core performs its frontend state operations.
        refuse_stacked_launch()
        preflight_keyboard_posting()
        production = run_smoke(args)
        if (production.get("frontend_unloaded") is not True or
                not isinstance(production.get("identity"), dict) or
                production["identity"].get("core_sha256") != identity["core_sha256"]):
            raise SmokeBlocked("production-control", "separate production-core frontend smoke did not unload cleanly")
        attempt["production_control"] = {
            "status": production.get("status"),
            "frontend_unloaded": production.get("frontend_unloaded"),
            "core_sha256": production["identity"].get("core_sha256"),
            "content_sha256": content_digest,
        }
        results = []
        for policy in (False, True):
            results.append(_run_sram_policy_case(
                args, base=base, executable=executable, core=core,
                content=content, observed_core=observed_core,
                identity=identity, observed_digest=observed_digest,
                witness=args.witness.resolve(), witness_digest=witness_digest,
                content_digest=content_digest, block_sram_overwrite=policy))
        result: dict[str, object] = {"status": "pass", "mode": "sram-policies",
                                     "identity": identity,
                                     "production_control": attempt["production_control"],
                                     "policies": results}
        attempt.update(status="pass", result=result)
        write_private_public_state_report(report_path, attempt)
        return result
    except SmokeBlocked as error:
        attempt.update(status="fail", stage=error.stage,
                       reason=sanitize_diagnostic_text(str(error)),
                       identity=attempt.get("identity", {}))
        if error.diagnostic is not None:
            attempt["diagnostic"] = error.diagnostic
        write_private_public_state_report(report_path, attempt)
        raise
    except Exception as error:
        attempt.update(status="fail", stage="internal",
                       reason=f"execution failed ({type(error).__name__})",
                       identity=attempt.get("identity", {}))
        write_private_public_state_report(report_path, attempt)
        raise


def run_focused_reset_control(args: argparse.Namespace) -> dict[str, object]:
    """Run one scoped RESET/SAVE_STATE/QUIT and prove normal SRAM writeback."""
    validate_continuation_operation_matrix(
        "sram-policies", state_operations=True, autosave_interval=0,
        external_sram_write=False)
    base, report_path = private_public_state_workspace(getattr(args, "report", None))
    attempt: dict[str, object] = {
        "schema_version": 1, "mode": "focused-reset-control", "status": "running",
        "invocation_id": hashlib.sha256(os.urandom(24)).hexdigest()[:24],
    }
    started = time.monotonic()
    failure_log: Path | None = None
    try:
        executable, core, content, observed_core, identity, observed_digest, \
            witness_digest, content_digest = _continuation_identity(args, attempt)
        work = base / f"focused-reset-{attempt['invocation_id']}"
        work.mkdir(mode=0o700)
        savefiles = work / "savefiles"
        savefiles.mkdir(mode=0o700)
        config, captures = _continuation_work_tree(
            work, savefiles, state_route=True, autosave_interval=0)
        log = work / "retroarch.log"
        process_log = work / "process-output.log"
        failure_log = log
        invocation = hashlib.sha256(os.urandom(24)).hexdigest()[:24]
        processes_before = running_retroarch_pids()
        with OwnedContinuationFrontend(
                args, executable=executable, content=content,
                observed_core=observed_core, identity=identity, config=config,
                log=log, process_log=process_log, observed_digest=observed_digest,
                witness=args.witness.resolve(), witness_digest=witness_digest,
                content_digest=content_digest, core=core, failure_root=base) as owner:
            if sha256(config) != owner.config_digest:
                raise SmokeBlocked("identity", "focused route configuration changed during launch")
            process = owner.process
            if process is None:
                raise SmokeBlocked("launch", "owned frontend launch returned no process")
            startup = owner.ready(invocation)
            with HeldMVSKeys(process) as keys:
                # GET_STATUS crashes the exact pinned 1.22.2 build after
                # startup; the completed neutral guest frame is the route's
                # non-invasive running-state witness.
                owner.status = "neutral-completed-frame-observed"
                reset = reset_guest_under_mask(
                    keys, 64, log, process, invocation, owner.deadline,
                    via_native_menu=True)
                if (reset.get("sampled_mask") != 64 or
                        reset.get("observation_epoch", 0) <=
                        startup.get("observation_epoch", 0)):
                    raise SmokeBlocked(
                        "continuation-observations",
                        "focused reset did not create a new observed epoch under held A")
                keys.set_mask(0)
                state_started_ns = time.time_ns()
                states = _save_state_file(
                    keys, log, work / "savestates", 1, state_started_ns,
                    process, owner.deadline, via_native_menu=True)
                state = states[0]
                focused_state = validate_focused_reset_state(state)
            if frontend_exited(process) or running_retroarch_pids() != {process.pid}:
                raise SmokeBlocked(
                    "continuation-observations",
                    "frontend process identity changed before focused QUIT")
            if frontend_sram_snapshot(savefiles) is not None:
                raise SmokeBlocked(
                    "sram-persistence",
                    "focused raw SRAM appeared before normal frontend QUIT")
            owner.quit(args.timeout)
        if owner.exit_code != 0:
            raise SmokeBlocked("unload", "focused frontend did not exit cleanly")
        persisted = _clean_exit_sram(savefiles, expected_outcome="A")
        if persisted.get("status") != "persisted":
            raise SmokeBlocked(
                "sram-persistence",
                "normal stdin QUIT did not write the focused A SRAM bytes",
                diagnostic=persisted)
        if running_retroarch_pids():
            raise SmokeBlocked("unload", "RetroArch process remained after focused QUIT")
        result: dict[str, object] = {
            "status": "pass", "mode": "focused-reset-control",
            "claim": "one frontend reset under held A, actual state save, and raw A SRAM writeback on stdin QUIT",
            "identity": identity,
            "version_reply": owner.version,
            "startup_status": owner.status,
            "commands": owner.command_trace,
            "startup_observation_epoch": startup["observation_epoch"],
            "reset_observation_epoch": reset["observation_epoch"],
            "reset_action": reset["reset_action"],
            "state_container_sha256": focused_state["container_sha256"],
            "state_guest_readback": focused_state["guest_readback"],
            "state_sram_outcome": focused_state["sram_outcome"],
            "raw_sram_files_before_quit": 0,
            "same_owned_pid_for_reset_and_save": process.pid,
            "frontend_exit_code": owner.exit_code,
            "writeback": persisted,
            "process_count": {"before": len(processes_before),
                              "owned_peak": 1, "after": len(running_retroarch_pids())},
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "configuration_sha256": owner.config_digest,
        }
        attempt.update(status="pass", result=result)
        write_private_public_state_report(report_path, attempt)
        return result
    except SmokeBlocked as error:
        if failure_log is not None:
            preserve_continuation_failure_log(base, failure_log)
        attempt.update(status="fail", stage=error.stage,
                       reason=sanitize_diagnostic_text(str(error)),
                       identity=attempt.get("identity", {}))
        if error.diagnostic is not None:
            attempt["diagnostic"] = error.diagnostic
        write_private_public_state_report(report_path, attempt)
        raise
    except Exception as error:
        if failure_log is not None:
            preserve_continuation_failure_log(base, failure_log)
        attempt.update(status="fail", stage="internal",
                       reason=f"execution failed ({type(error).__name__})",
                       identity=attempt.get("identity", {}))
        write_private_public_state_report(report_path, attempt)
        raise


def run_focused_undo_control(args: argparse.Namespace) -> dict[str, object]:
    """Reproduce A/B save, load, real Undo Load, menu close and live B save."""
    validate_continuation_operation_matrix(
        "focused-undo-control", state_operations=True, autosave_interval=0,
        external_sram_write=False)
    base, report_path = private_public_state_workspace(getattr(args, "report", None))
    attempt: dict[str, object] = {
        "schema_version": 1, "mode": "focused-undo-control", "status": "running",
        "invocation_id": hashlib.sha256(os.urandom(24)).hexdigest()[:24],
    }
    started = time.monotonic()
    failure_log: Path | None = None
    try:
        executable, core, content, observed_core, identity, observed_digest, \
            witness_digest, content_digest = _continuation_identity(args, attempt)
        work = base / f"focused-undo-{attempt['invocation_id']}"
        work.mkdir(mode=0o700)
        savefiles = work / "savefiles"
        savefiles.mkdir(mode=0o700)
        config, captures = _continuation_work_tree(
            work, savefiles, state_route=True, block_sram_overwrite=False,
            autosave_interval=0)
        log = work / "retroarch.log"
        process_log = work / "process-output.log"
        failure_log = log
        savestates = work / "savestates"
        invocation = hashlib.sha256(os.urandom(24)).hexdigest()[:24]
        state_started_ns = time.time_ns()
        processes_before = running_retroarch_pids()
        owner = OwnedContinuationFrontend(
            args, executable=executable, content=content,
            observed_core=observed_core, identity=identity, config=config,
            log=log, process_log=process_log, observed_digest=observed_digest,
            witness=args.witness.resolve(), witness_digest=witness_digest,
            content_digest=content_digest, core=core, failure_root=base)
        with owner:
            if sha256(config) != owner.config_digest:
                raise SmokeBlocked("identity", "focused undo configuration changed during launch")
            process = owner.process
            if process is None:
                raise SmokeBlocked("launch", "focused undo frontend launch returned no process")
            deadline = owner.deadline
            startup = owner.ready(invocation)
            with HeldMVSKeys(process) as keys:
                branch_a = reset_guest_under_mask(
                    keys, 64, log, process, invocation, deadline, via_native_menu=True)
                keys.set_mask(0)
                saved_a = _save_state_file(
                    keys, log, savestates, 1, state_started_ns, process, deadline,
                    via_native_menu=True)[0]
                if saved_a["sram_outcome"] != "A":
                    raise SmokeBlocked(
                        "state-container", "focused Undo Load A state lacks SRAM A")

                branch_b = reset_guest_under_mask(
                    keys, 128, log, process, invocation, deadline, via_native_menu=True)
                keys.set_mask(0)
                baseline = len(read_frontend_log(log))
                slot_plus = owner.send("STATE_SLOT_PLUS")
                slot_plus_frame = wait_for_neutral_mvs_guest_frames(
                    log, process, baseline, 1, deadline)[0]
                saved_states = _save_state_file(
                    keys, log, savestates, 2, state_started_ns, process, deadline,
                    via_native_menu=True)
                saved_a = next((state for state in saved_states
                                if state["name"] == f"{content.stem}.state"), None)
                saved_b = next((state for state in saved_states
                                if state["name"] == f"{content.stem}.state1"), None)
                if (saved_a is None or saved_b is None or
                        saved_a["sram_outcome"] != "A" or
                        saved_b["sram_outcome"] != "B" or
                        saved_a["container_sha256"] == saved_b["container_sha256"]):
                    raise SmokeBlocked(
                        "state-container", "focused Undo Load did not produce distinct A/B state files")

                baseline = len(read_frontend_log(log))
                slot_minus = owner.send("STATE_SLOT_MINUS")
                slot_minus_frame = wait_for_neutral_mvs_guest_frames(
                    log, process, baseline, 1, deadline)[0]
                owner.send("LOAD_STATE")
                load_restore_states = wait_for_continuation_restore_states(
                    log, 1, process, deadline)
                if (len(load_restore_states) != 1 or
                        load_restore_states[0] != saved_a["mem"]):
                    raise SmokeBlocked(
                        "continuation-observations", "focused Load State did not restore the saved A state")

                activate_owned_menu_item(keys, UNDO_LOAD_MENU_DOWN_PRESSES)
                restores = wait_for_continuation_restore_states(
                    log, 2, process, deadline)
                undo = validate_focused_undo_load_history(restores, saved_a["mem"])
                menu_close_baseline = len(read_frontend_log(log))
                menu_close = wait_for_owned_quick_menu_release(
                    process, log, menu_close_baseline, deadline)

                save_baseline = continuation_event_count(read_frontend_log(log), "S")
                final_states = _save_state_file(
                    keys, log, savestates, 2, state_started_ns, process, deadline,
                    via_native_menu=True, event_count=save_baseline + 1)
                final_live = [state for state in final_states
                              if state["name"] == f"{content.stem}.state" and
                              state.get("save_file_changed") is True and
                              state["container_sha256"] != saved_a["container_sha256"]]
                if (len(final_live) != 1 or final_live[0]["sram_outcome"] != "B" or
                        final_live[0]["guest_readback"] not in (None, "B")):
                    raise SmokeBlocked(
                        "sram-persistence",
                        "post-undo actual state save did not contain live B guest/SRAM",
                        diagnostic={
                            "final_state_count": len(final_live),
                            "live_guest_readback": (final_live[0]["guest_readback"]
                                                    if final_live else None),
                            "live_sram_outcome": (final_live[0]["sram_outcome"]
                                                  if final_live else None),
                        },
                    )
                final_live = final_live[0]

            if (frontend_exited(process) or running_retroarch_pids() != {process.pid} or
                    sha256(config) != owner.config_digest or
                    sha256(content) != content_digest or
                    sha256(observed_core) != observed_digest or
                    sha256(args.witness.resolve()) != witness_digest):
                raise SmokeBlocked(
                    "identity", "focused undo frontend or evidence identity changed before QUIT")
            if frontend_sram_snapshot(savefiles) is not None:
                raise SmokeBlocked(
                    "sram-persistence", "focused raw SRAM appeared before normal frontend QUIT")
            owner.quit(args.timeout)
        if owner.exit_code != 0:
            raise SmokeBlocked("unload", "focused undo frontend did not exit cleanly")
        persisted = _clean_exit_sram(savefiles, expected_outcome="B")
        if persisted.get("status") != "persisted" or running_retroarch_pids():
            raise SmokeBlocked(
                "sram-persistence", "focused undo normal QUIT did not persist B and reap RetroArch",
                diagnostic=persisted)
        result: dict[str, object] = {
            "status": "pass", "mode": "focused-undo-control",
            "claim": "one frontend saved A/B, loaded A, performed actual Quick Menu Undo Load, saved live B SRAM, and wrote B on normal QUIT; initial raw SRAM readback is not claimed",
            "identity": identity,
            "version_reply": owner.version,
            "commands": owner.command_trace,
            "startup_observation_epoch": startup["observation_epoch"],
            "reset_observation_epochs": [branch_a["observation_epoch"],
                                         branch_b["observation_epoch"]],
            "state_a_sha256": saved_a["container_sha256"],
            "state_b_sha256": saved_b["container_sha256"],
            "load_restore_sha256": hashlib.sha256(load_restore_states[0]).hexdigest(),
            "undo_restore_sha256": hashlib.sha256(restores[1]).hexdigest(),
            "undo_guest_readback": undo["undo_guest_readback"],
            "undo_sram_outcome": undo["undo_sram_outcome"],
            "undo_distinct_non_sram_machine_state": undo[
                "distinct_non_sram_machine_state"],
            "menu_close": menu_close,
            "slot_commands": {"plus": slot_plus, "plus_frame": slot_plus_frame,
                              "minus": slot_minus, "minus_frame": slot_minus_frame},
            "final_live_state": {
                "container_sha256": final_live["container_sha256"],
                "mem_sha256": final_live["mem_sha256"],
                "guest_readback": final_live["guest_readback"],
                "sram_outcome": final_live["sram_outcome"],
            },
            "frontend_exit_code": owner.exit_code,
            "writeback": persisted,
            "process_count": {"before": len(processes_before), "owned_peak": 1,
                              "after": len(running_retroarch_pids())},
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "configuration_sha256": owner.config_digest,
        }
        attempt.update(status="pass", result=result)
        write_private_public_state_report(report_path, attempt)
        return result
    except SmokeBlocked as error:
        if failure_log is not None:
            preserve_continuation_failure_log(base, failure_log)
        attempt.update(status="fail", stage=error.stage,
                       reason=sanitize_diagnostic_text(str(error)),
                       identity=attempt.get("identity", {}))
        if error.diagnostic is not None:
            attempt["diagnostic"] = error.diagnostic
        write_private_public_state_report(report_path, attempt)
        raise
    except Exception as error:
        if failure_log is not None:
            preserve_continuation_failure_log(base, failure_log)
        attempt.update(status="fail", stage="internal",
                       reason=f"execution failed ({type(error).__name__})",
                       identity=attempt.get("identity", {}))
        write_private_public_state_report(report_path, attempt)
        raise


def _run_sram_seed_frontend(args: argparse.Namespace, *, base: Path,
                            run_id: str,
                            executable: Path, core: Path, content: Path,
                            observed_core: Path, identity: dict[str, str],
                            observed_digest: str, witness: Path,
                            witness_digest: str, content_digest: str,
                            savefiles: Path) -> dict[str, object]:
    """Create a real A seed through the pinned frontend's normal exit writeback."""
    work = base / f"sram-seed-{run_id}"
    work.mkdir(mode=0o700)
    config_work = work / "writer"
    config_work.mkdir(mode=0o700)
    config, _ = _continuation_work_tree(
        config_work, savefiles, state_route=True,
        periodic_save=False, autosave_interval=0)
    savestates = config_work / "savestates"
    log = config_work / "retroarch.log"
    process_log = config_work / "process-output.log"
    owner = OwnedContinuationFrontend(
        args, executable=executable, content=content,
        observed_core=observed_core, identity=identity, config=config,
        log=log, process_log=process_log, observed_digest=observed_digest,
        witness=witness, witness_digest=witness_digest,
        content_digest=content_digest, core=core, failure_root=base)
    invocation = hashlib.sha256(os.urandom(24)).hexdigest()[:24]
    process: subprocess.Popen[bytes] | None = None
    exit_code: int | None = None
    try:
        owner.start()
        process = owner.process
        if process is None:
            raise SmokeBlocked("launch", "owned SRAM seed frontend did not start")
        deadline = owner.deadline
        config_digest = owner.config_digest
        startup = owner.ready(invocation)
        with HeldMVSKeys(process) as keys:
            # Drain the initial neutral epoch before reset_guest_under_mask
            # snapshots its epoch count. Otherwise startup's first B marker
            # can be mistaken for the requested reset, before this one-shot
            # selector guest has sampled A.
            write_a = reset_guest_under_mask(keys, 64, log, process,
                                             invocation, deadline,
                                             via_native_menu=True)
            if (write_a.get("sampled_mask") != 64 or
                    write_a.get("observation_epoch", 0) <=
                    startup.get("observation_epoch", 0)):
                raise SmokeBlocked(
                    "sram-persistence",
                    "A seed reset did not start a new observed epoch under held A")
            keys.set_mask(0)
            if list(savefiles.iterdir()):
                raise SmokeBlocked(
                    "sram-persistence",
                    "autosave-disabled A producer wrote SRAM before normal frontend exit")
            states = _save_state_file(
                keys, log, savestates, 1, time.time_ns(), process, deadline,
                via_native_menu=True)
            seed_state = states[0]
            if seed_state.get("sram_outcome") != "A":
                raise SmokeBlocked(
                    "sram-persistence",
                    "A producer did not hold distinguishable guest SRAM before exit")
        if sha256(config) != config_digest:
            raise SmokeBlocked("identity", "SRAM seed configuration changed during execution")
        exit_code = owner.quit(args.timeout)
    finally:
        owner.cleanup()
        if process is not None and exit_code is None:
            exit_code = owner.exit_code
    if exit_code != 0:
        raise SmokeBlocked("unload", "SRAM seed frontend did not exit cleanly")
    persisted = _clean_exit_sram(savefiles, expected_outcome="A")
    if persisted.get("status") != "persisted":
        raise SmokeBlocked("sram-persistence", "normal frontend exit did not write the expected A SRAM bytes",
                           diagnostic=persisted)
    return {**persisted, "frontend_pid": process.pid,
            "frontend_exit_code": exit_code,
            "source": "pinned RetroArch normal-exit SAVE_RAM writeback",
            "pre_exit_state_sha256": seed_state["container_sha256"],
            "pre_exit_sram_outcome": seed_state["sram_outcome"],
            "reset_menu_probe": write_a.get("reset_menu_probe"),
            "reset_pending_sample": write_a.get("reset_pending_sample"),
            "startup_video_sequence": startup["first_video_sequence"],
            "startup_observation_epoch": startup["observation_epoch"],
            "reset_observation_epoch": write_a["observation_epoch"],
            "reset_action": write_a["reset_action"],
            "reset_trigger_video_sequence": write_a["reset_trigger_video_sequence"],
            "reset_video_sequence": write_a["successful_video_sequence"],
            "configuration_sha256": config_digest,
            "autosave_interval_seconds": 0}


def _run_periodic_save_transaction(args: argparse.Namespace, base: Path,
                                   attempt: dict[str, object]) -> dict[str, object]:
    executable, core, content, observed_core, identity, observed_digest, \
        witness_digest, content_digest = _continuation_identity(args, attempt)
    route = validate_continuation_operation_matrix(
        "periodic-save", state_operations=False, autosave_interval=1,
        external_sram_write=False)
    if route != "periodic-save":
        raise SmokeBlocked("operation-matrix", "periodic save route selection failed")
    run_id = hashlib.sha256(os.urandom(16)).hexdigest()[:12]
    work = base / f"periodic-live-{run_id}"
    work.mkdir(mode=0o700)
    savefiles = work / "savefiles"
    savefiles.mkdir(mode=0o700)
    seed = _run_sram_seed_frontend(
        args, base=base, run_id=run_id,
        executable=executable, core=core, content=content,
        observed_core=observed_core, identity=identity,
        observed_digest=observed_digest, witness=args.witness.resolve(),
        witness_digest=witness_digest, content_digest=content_digest,
        savefiles=savefiles)
    seed_snapshot = frontend_sram_snapshot(savefiles)
    seed_identity = validate_periodic_seed_file(seed, seed_snapshot)
    seed_reader = _run_fresh_sram_reader(
        args, base=base, savefiles=savefiles, executable=executable, core=core,
        content=content, observed_core=observed_core, identity=identity,
        observed_digest=observed_digest, witness=args.witness.resolve(),
        witness_digest=witness_digest, content_digest=content_digest,
        expected="A")
    if seed_reader.get("guest_readback") != "A":
        raise SmokeBlocked("sram-consumption", "fresh A seed reader did not consume A before periodic launch")
    after_seed_read = frontend_sram_snapshot(savefiles)
    if after_seed_read is None or after_seed_read.get("sha256") != seed_snapshot.get("sha256"):
        raise SmokeBlocked("periodic-save", "read-only A seed consumer changed the periodic input file")

    writer = work / "writer"
    writer.mkdir(mode=0o700)
    config, _ = _continuation_work_tree(
        writer, savefiles, state_route=False, periodic_save=True,
        autosave_interval=1)
    config_bytes = read_private_regular_file(config, 12 * 1024)
    config_digest = hashlib.sha256(config_bytes).hexdigest()
    log = writer / "retroarch.log"
    process_log = writer / "process-output.log"
    invocation = hashlib.sha256(os.urandom(24)).hexdigest()[:24]
    owner = OwnedContinuationFrontend(
        args, executable=executable, content=content,
        observed_core=observed_core, identity=identity, config=config,
        log=log, process_log=process_log, observed_digest=observed_digest,
        witness=args.witness.resolve(), witness_digest=witness_digest,
        content_digest=content_digest, core=core, failure_root=base)
    process: subprocess.Popen[bytes] | None = None
    exit_code: int | None = None
    try:
        owner.start()
        process = owner.process
        if process is None:
            raise SmokeBlocked("launch", "owned periodic-save frontend did not start")
        deadline = owner.deadline
        launched_config_digest = owner.config_digest
        if launched_config_digest != config_digest:
            raise SmokeBlocked("identity", "periodic-save configuration identity changed")
        startup = owner.ready(invocation)
        with HeldMVSKeys(process) as keys:
            before = frontend_sram_snapshot(savefiles)
            if before is None or before.get("sha256") != seed_snapshot.get("sha256"):
                raise SmokeBlocked("periodic-save", "periodic frontend did not retain the seeded A file at startup")
            branch_a = reset_guest_under_mask(keys, 64, log, process,
                                              invocation, deadline,
                                              via_native_menu=True)
            keys.set_mask(0)
            if (branch_a.get("sampled_mask") != 64 or
                    branch_a.get("observation_epoch", 0) <=
                    startup.get("observation_epoch", 0)):
                raise SmokeBlocked("periodic-save", "A guest branch lacks a new reset epoch under held A")
            a_branch_file = frontend_sram_snapshot(savefiles)
            if a_branch_file is None or a_branch_file.get("sha256") != before.get("sha256"):
                raise SmokeBlocked("periodic-save", "initial A branch changed the seeded file before B")
            branch_b = reset_guest_under_mask(keys, 128, log, process,
                                              invocation, deadline,
                                              via_native_menu=True)
            keys.set_mask(0)
            update = wait_for_periodic_save_update(
                savefiles, before, process, "B", deadline)
        if (running_retroarch_pids() != {process.pid} or frontend_exited(process)):
            raise SmokeBlocked("periodic-save", "matching SRAM update was not observed before owned-process exit")
        if sha256(config) != config_digest or sha256(content) != content_digest or \
                sha256(observed_core) != observed_digest or sha256(args.witness.resolve()) != witness_digest:
            raise SmokeBlocked("identity", "periodic-save evidence input changed during execution")
        exit_code = owner.quit(args.timeout)
    finally:
        owner.cleanup()
        if process is not None and exit_code is None:
            exit_code = owner.exit_code
    if exit_code != 0:
        raise SmokeBlocked("unload", "periodic-save frontend did not exit cleanly")
    after_exit = _clean_exit_sram(savefiles, expected_outcome="B")
    if after_exit.get("status") != "persisted" or after_exit.get("sha256") != update["after_sha256"]:
        raise SmokeBlocked("sram-persistence", "clean exit changed bytes after the periodic update")
    reader = _run_fresh_sram_reader(
        args, base=base, savefiles=savefiles, executable=executable, core=core,
        content=content, observed_core=observed_core, identity=identity,
        observed_digest=observed_digest, witness=args.witness.resolve(),
        witness_digest=witness_digest, content_digest=content_digest,
        expected="B")
    return {"status": "pass", "mode": "periodic-save", "identity": identity,
            "configuration_sha256": config_digest, "autosave_interval_seconds": 1,
            "seed": seed, "seed_identity": seed_identity,
            "seed_reader": seed_reader,
            "before": {"bytes": before["size"], "sram_sha256": before["sha256"],
                       "sram_outcome": before["sram_outcome"]},
            "startup": startup,
            "A_branch_file_unchanged": a_branch_file["sha256"] == before["sha256"],
            "periodic_update": update,
            "writer": {"pid": process.pid, "exit_code": exit_code,
                       "guest_branches": ["A", "B"],
                       "reset_action": branch_a["reset_action"],
                       "reset_menu_diagnostics": [
                           {"menu": branch_a.get("reset_menu_probe"),
                            "pending_sample": branch_a.get("reset_pending_sample")},
                           {"menu": branch_b.get("reset_menu_probe"),
                            "pending_sample": branch_b.get("reset_pending_sample")}],
                       "initial_reset_epoch": branch_a["observation_epoch"],
                       "reset_epoch": branch_b["observation_epoch"],
                       "initial_reset_trigger_video_sequence":
                           branch_a["reset_trigger_video_sequence"],
                       "reset_trigger_video_sequence":
                           branch_b["reset_trigger_video_sequence"],
                       "initial_reset_video_sequence": branch_a["successful_video_sequence"],
                       "reset_video_sequence": branch_b["successful_video_sequence"]},
            "clean_exit": after_exit, "fresh_reader": reader,
            "no_restore_or_undo": True, "external_sram_writer": False}


def run_periodic_save(args: argparse.Namespace) -> dict[str, object]:
    validate_continuation_operation_matrix(
        "periodic-save", state_operations=False, autosave_interval=1,
        external_sram_write=False)
    base, report_path = private_public_state_workspace(getattr(args, "report", None))
    attempt: dict[str, object] = {"schema_version": 1, "mode": "periodic-save",
                                  "status": "running",
                                  "invocation_id": hashlib.sha256(os.urandom(24)).hexdigest()[:24]}
    try:
        result = _run_periodic_save_transaction(args, base, attempt)
        attempt.update(status="pass", result=result)
        write_private_public_state_report(report_path, attempt)
        return result
    except SmokeBlocked as error:
        attempt.update(status="fail", stage=error.stage,
                       reason=sanitize_diagnostic_text(str(error)),
                       identity=attempt.get("identity", {}))
        if error.diagnostic is not None:
            attempt["diagnostic"] = error.diagnostic
        write_private_public_state_report(report_path, attempt)
        raise
    except Exception as error:
        attempt.update(status="fail", stage="internal",
                       reason=f"execution failed ({type(error).__name__})",
                       identity=attempt.get("identity", {}))
        write_private_public_state_report(report_path, attempt)
        raise


def _run_public_state_transaction(args: argparse.Namespace, base: Path,
                                  attempt: dict[str, object]) -> dict[str, object]:
    executable, core, content, identity = validate_inputs(args)
    if identity.get("content_kind") != "selected-mvs":
        raise SmokeBlocked("input", "public-state continuation requires the original normalized save guest")
    observed_core = args.observed_core.resolve()
    witness = args.witness.resolve()
    if (not observed_core.is_file() or not witness.is_file() or
            observed_core == core or observed_core.stat().st_size == 0 or
            witness.stat().st_size == 0):
        raise SmokeBlocked("identity", "observed core or fresh native witness is missing or mismatched")
    observed_digest = sha256(observed_core)
    witness_digest = sha256(witness)
    if observed_digest == identity["core_sha256"]:
        raise SmokeBlocked("identity", "observed and production core artifacts are identical")
    content_digest = sha256(content)
    identity.update(observed_core_sha256=observed_digest,
                    witness_sha256=witness_digest, content_sha256=content_digest)
    attempt["identity"] = identity

    # Establish the production-core frontend control in its own invocation.
    refuse_stacked_launch()
    preflight_keyboard_posting()
    production = run_smoke(args)
    if (production.get("frontend_unloaded") is not True or
            not isinstance(production.get("identity"), dict) or
            production["identity"].get("core_sha256") != identity["core_sha256"]):
        raise SmokeBlocked("production-control", "separate production-core frontend smoke did not unload cleanly")
    attempt["production_control"] = {
        "status": production.get("status"),
        "frontend_unloaded": production.get("frontend_unloaded"),
        "core_sha256": production["identity"].get("core_sha256"),
        "content_sha256": content_digest,
    }

    invocation = hashlib.sha256(os.urandom(24)).hexdigest()[:24]
    with tempfile.TemporaryDirectory(prefix="glueyneo-public-state-", dir=base) as temporary:
        work = Path(temporary)
        os.chmod(work, 0o700)
        captures = work / "captures"
        savefiles = work / "savefiles"
        savestates = work / "savestates"
        system = work / "system"
        for directory in (captures, savefiles, savestates, system):
            directory.mkdir(mode=0o700)
        config = write_frontend_config(work, captures, savefiles=savefiles,
                                       savestates=savestates, public_state=True,
                                       null_audio=True)
        config_bytes = config.read_bytes()
        config_sha = hashlib.sha256(config_bytes).hexdigest()
        if not validate_active_config_destinations(
                config_bytes.decode("utf-8"), work, captures,
                savefiles=savefiles, savestates=savestates, public_state=True):
            raise SmokeBlocked("identity", "isolated public-state configuration failed its contract")
        log = work / "retroarch.log"
        process_log = work / "process-output.log"
        deadline = time.monotonic() + args.timeout
        process = None
        frontend_exit_code: int | None = None
        final_log = b""
        with process_log.open("wb") as process_output:
            try:
                refuse_stacked_launch()
                preflight_keyboard_posting()
                # Rebind app, input, core, content and witness after creating the
                # fresh isolated config and immediately before the owned launch.
                executable_now, core_now, content_now, identity_now = validate_inputs(args)
                if (executable_now != executable or core_now != core or content_now != content or
                        identity_now["retroarch_executable_sha256"] != identity["retroarch_executable_sha256"] or
                        sha256(observed_core) != observed_digest or sha256(witness) != witness_digest or
                        sha256(content) != content_digest or sha256(core) != identity["core_sha256"]):
                    raise SmokeBlocked("identity", "frontend inputs changed after their initial binding")
                command = [str(executable), "--verbose", "--config", str(config),
                           "-L", str(observed_core), str(content)]
                with launch_window():
                    process = subprocess.Popen(command, stdout=process_output,
                                               stderr=subprocess.STDOUT,
                                               start_new_session=True)
                    record_child_pid(getattr(args, "child_pid_file", None), process)
                _wait_frontend_log_marker(log, b"glueyneo: MVS bundle loaded",
                                          process, deadline, "launch")
                if running_retroarch_pids() != {process.pid}:
                    raise SmokeBlocked("pre-launch", "owned RetroArch process set changed after launch")
                preflight_keyboard_posting(process=process)
                focus_owned_frontend(process)

                with HeldMVSKeys(process) as keys:
                    # The public save guest reads its A/B selector once. Reset
                    # while holding each key so each state captures that branch.
                    branch_a_video = reset_guest_under_mask(
                        keys, 64, log, process, invocation, deadline)
                    keys.set_mask(0)

                    save_a_started_ns = time.time_ns()
                    press_owned_key(keys, SAVE_STATE_KEY_CODE)
                    save_records = _wait_continuation_event_count(
                        log, "S", 1, process, deadline)
                    if save_records[0][1][1] == 0:
                        raise SmokeBlocked("continuation-observations", "initial save lacked a completed-frame boundary")
                    state_a_candidates = wait_for_public_state_files(
                        savestates, 1, save_a_started_ns, deadline)
                    state_a_file = state_a_candidates[0]
                    if state_a_file["sram_outcome"] != "A":
                        raise SmokeBlocked("state-container", "slot-zero state does not contain the A guest branch")

                    # The guest samples its A/B selector only at reset. Keep B
                    # held until the core proves reset began a new epoch.
                    branch_b_video = reset_guest_under_mask(
                        keys, 128, log, process, invocation, deadline)
                    keys.set_mask(0)
                    press_owned_key(keys, STATE_SLOT_INCREASE_KEY_CODE)
                    save_b_started_ns = time.time_ns()
                    press_owned_key(keys, SAVE_STATE_KEY_CODE)
                    save_records = _wait_continuation_event_count(
                        log, "S", 2, process, deadline)
                    if save_records[1][1][1] <= save_records[0][1][1]:
                        raise SmokeBlocked("continuation-observations", "A/B saves lack distinct frame boundaries")
                    state_candidates = wait_for_public_state_files(
                        savestates, 2, save_a_started_ns, deadline)
                    state_a = next((item for item in state_candidates
                                    if item["sram_outcome"] == "A"), None)
                    state_b = next((item for item in state_candidates
                                    if item["sram_outcome"] == "B"), None)
                    if (state_a is None or state_b is None or
                            state_a["container_sha256"] == state_b["container_sha256"]):
                        raise SmokeBlocked("state-container", "actual A/B state files are not distinct")

                    # Slot 1 contains the distinguishable B branch; explicitly
                    # return to slot 0 and load its real RASTATE file. Pause the
                    # frontend so host key posting cannot race the four measured
                    # post-load frames; each requested mask gets one UI step.
                    press_owned_key(keys, PAUSE_KEY_CODE)
                    press_owned_key(keys, STATE_SLOT_DECREASE_KEY_CODE)
                    press_owned_key(keys, LOAD_STATE_KEY_CODE)
                    restore_records = _wait_continuation_event_count(
                        log, "R", 1, process, deadline)
                    if not restore_records:
                        raise SmokeBlocked("continuation-observations", "actual UI load did not restore the core")

                    keys.set_mask(0)
                    requested_future_masks = (0, 64, 128, 32)
                    try:
                        for index, mask in enumerate(requested_future_masks):
                            keys.set_mask(mask)
                            press_owned_key(keys, FRAME_ADVANCE_KEY_CODE)
                            wait_for_continuation_frame(log, index + 1, process, deadline)
                            # The pinned frontend edge-detects frame advance;
                            # let its paused runloop observe key-up before the
                            # next key-down can request another measured frame.
                            time.sleep(FRAME_ADVANCE_RELEASE_SECONDS)
                    except SmokeBlocked:
                        preserve_continuation_failure_log(base, log)
                        raise
                    keys.set_mask(0)
                    press_owned_key(keys, PAUSE_KEY_CODE)

                final_log = read_frontend_log(log)
                try:
                    observations = parse_continuation_observations(final_log)
                except SmokeBlocked:
                    try:
                        write_private_bytes(base / "continuation-failure.log",
                                            final_log, MVS_FRONTEND_LOG_LIMIT)
                    except SmokeBlocked:
                        pass
                    raise
                if (len(observations["captures"]) not in (2, 3) or
                        [frame["input_mask"] for frame in observations["frames"]] !=
                        list(requested_future_masks)):
                    try:
                        write_private_bytes(base / "continuation-failure.log",
                                            final_log, MVS_FRONTEND_LOG_LIMIT)
                    except SmokeBlocked:
                        pass
                    raise SmokeBlocked("continuation-observations", "actual post-load input sequence differs")
                restored_mem = observations["restore"].get("state")
                require_matching_frontend_mem(restored_mem, state_a["mem"])
                if state_b["mem"] == restored_mem:
                    raise SmokeBlocked("continuation-observations", "loaded state is not distinguishable from branch B")
                try:
                    witness_result = invoke_frontend_native_witness(
                        witness, content, restored_mem, observations, work, "actual-frontend")
                except SmokeBlocked:
                    preserve_continuation_failure_log(base, log)
                    raise
                if (sha256(config) != config_sha or sha256(content) != content_digest or
                        sha256(observed_core) != observed_digest or sha256(witness) != witness_digest):
                    raise SmokeBlocked("identity", "frontend evidence inputs changed during execution")
                if not request_frontend_quit(identity["bundle_id"], process, args.timeout):
                    raise SmokeBlocked("unload", "actual observed-core RetroArch did not exit cleanly")
                frontend_exit_code = frontend_returncode(process)
                if frontend_exit_code != 0:
                    raise SmokeBlocked("unload", "actual observed-core RetroArch returned a failure code")
                final_log = read_frontend_log(log)
            finally:
                if process is not None:
                    try:
                        if getattr(process, "returncode", None) is None:
                            request_frontend_quit(identity["bundle_id"], process, 2.0)
                    finally:
                        kill_launched_group(process)
                if process is not None and frontend_exit_code is None:
                    frontend_exit_code = frontend_returncode(process)

        if frontend_exit_code != 0:
            raise SmokeBlocked("unload", "actual observed-core RetroArch cleanup did not exit cleanly")
        if sha256(config) != config_sha:
            raise SmokeBlocked("identity", "frontend changed the isolated configuration")
        try:
            sram_exit = _clean_exit_sram(savefiles)
        except SmokeBlocked:
            preserve_continuation_failure_log(base, log)
            raise
        try:
            observations = parse_continuation_observations(final_log)
        except SmokeBlocked:
            try:
                write_private_bytes(base / "continuation-failure.log",
                                    final_log, MVS_FRONTEND_LOG_LIMIT)
            except SmokeBlocked:
                pass
            raise
        frames = [{"input_mask": frame["input_mask"],
                   "cycle_delta": frame["cycle_delta"],
                   "audio_frames": frame["audio_frames"],
                   "video_sha256": hashlib.sha256(frame["video"]).hexdigest(),
                   "audio_sha256": hashlib.sha256(frame["audio"]).hexdigest()}
                  for frame in observations["frames"]]
        save_ram_interface = parse_frontend_save_ram_queries(final_log)
        return {
            "status": "pass",
            "mode": "public-state",
            "identity": identity,
            "production_control": attempt["production_control"],
            "observer_window": {
                "capture_count": len(observations["captures"]),
                "restore_state_bytes": len(restored_mem),
                "restore_state_sha256": hashlib.sha256(restored_mem).hexdigest(),
                "restored_slot": "A",
                "branch_state_sha256": state_b["mem_sha256"],
                "slot_zero_container_sha256": state_a["container_sha256"],
                "slot_one_container_sha256": state_b["container_sha256"],
                "frames": frames,
                "raw_record_bytes": observations["record_bytes"],
            },
            "native_witness": witness_result,
            "save_ram_interface": save_ram_interface,
            "sram_exit": sram_exit,
            "frontend_exit_code": frontend_exit_code,
            "configuration_sha256": config_sha,
            "capture_boundaries": [
                {"completed_frames": capture["completed_frames"],
                 "executed_cycles": capture["executed_cycles"]}
                for capture in observations["captures"]],
            "restore_boundary": {"completed_frames": observations["restore"]["completed_frames"],
                                 "executed_cycles": observations["restore"]["executed_cycles"]},
            "input_probes": {
                "save_a": {"mask": 64, "completed_video": branch_a_video["successful_video_sequence"],
                           "cycles": branch_a_video["executed_cycles"]},
                "branch_b": {"mask": 128, "completed_video": branch_b_video["successful_video_sequence"],
                             "cycles": branch_b_video["executed_cycles"]},
            },
        }


def _private_state_scene(args: argparse.Namespace, base: Path) -> dict[str, object]:
    """Bind the local scene, frozen sound schedule, selected media, and importer."""
    contract_path = getattr(args, "private_contract", None)
    if not isinstance(contract_path, Path):
        raise SmokeBlocked("preflight", "private continuation requires its selected scene contract")
    contract_path = contract_path.resolve()
    try:
        local_state = importlib.import_module("mvs.qualify_local_state")
        boot = local_state.load_module(
            "_glueyneo_private_state_boot",
            Path(__file__).resolve().parents[2] / "tools/mvs/qualify_local_boot.py")
        scene, sound, media_pair, scene_digest = local_state.read_scene(contract_path, boot)
        capture_frame, masks, schedule_identity = local_state.selected_schedule(scene, sound)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as error:
        raise SmokeBlocked("preflight", "selected private scene, sound contract, or media is unavailable") from error
    importer = boot.checked_importer_command(identity=scene.get("code_identity", {}).get("importer"))
    if importer is None or len(media_pair) != 2:
        raise SmokeBlocked("identity", "selected scene importer or media identity is unavailable")
    importer_path = Path(importer)
    imported_content = base / "selected-source-bound.gnmv"
    if imported_content.exists() or imported_content.is_symlink():
        raise SmokeBlocked("preflight", "private source-bound content destination is not fresh")
    try:
        imported = subprocess.run(
            [importer, "--selected", *map(str, media_pair), str(imported_content)],
            cwd=Path(__file__).resolve().parents[2], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise SmokeBlocked("preflight", "selected MVS media could not be normalized") from error
    if (imported.returncode != 0 or not imported_content.is_file() or
            imported_content.is_symlink() or imported_content.stat().st_size > GNMV_MAX_BYTES or
            not is_normalized_mvs_bundle(read_private_regular_file(imported_content, GNMV_MAX_BYTES))):
        raise SmokeBlocked("input", "selected source import is missing or outside the bounded MVS profile")
    supplied = getattr(args, "content", None)
    if not isinstance(supplied, Path):
        raise SmokeBlocked("input", "private continuation requires its normalized selected content")
    supplied = supplied.resolve()
    try:
        info = supplied.lstat()
    except OSError as error:
        raise SmokeBlocked("input", "normalized selected content is unavailable") from error
    if (not stat_module.S_ISREG(info.st_mode) or info.st_size > GNMV_MAX_BYTES or
            sha256(supplied) != sha256(imported_content)):
        raise SmokeBlocked("identity", "normalized content does not match the current selected media import")
    return {
        "local_state": local_state, "boot": boot, "scene": scene, "sound": sound,
        "contract_path": contract_path,
        "media_pair": media_pair, "scene_digest": scene_digest,
        "sound_digest": sha256(Path(boot.PHASE07_SOUND_CONTRACT_PATH)),
        "capture_frame": capture_frame, "masks": masks,
        "schedule_identity": schedule_identity, "importer_path": importer_path,
        "importer_digest": sha256(importer_path), "content": supplied,
        "content_digest": sha256(supplied),
    }


def _private_state_identity(context: dict[str, object], identity: dict[str, str],
                            observed_digest: str, witness_digest: str) -> dict[str, str]:
    media_identity = context["scene"].get("media_identity")
    media_bytes = json.dumps(media_identity, sort_keys=True, separators=(",", ":")).encode()
    return {
        "scene_contract_sha256": context["scene_digest"],
        "sound_contract_sha256": context["sound_digest"],
        "schedule_identity": context["schedule_identity"],
        "media_identity_sha256": hashlib.sha256(media_bytes).hexdigest(),
        "importer_sha256": context["importer_digest"],
        "content_sha256": context["content_digest"],
        "production_core_sha256": identity["core_sha256"],
        "observed_core_sha256": observed_digest,
        "witness_sha256": witness_digest,
        "retroarch_sha256": identity["retroarch_executable_sha256"],
    }


def _wait_mvs_event(collector: "MVSObservationCollector", kind: str,
                    deadline: float) -> dict[str, object]:
    if kind not in {"R", "P"}:
        raise SmokeBlocked("observations", "unsupported active-scene event")
    while time.monotonic() < deadline:
        records = collector.drain()
        found = [record for record in records if record["event_kind"] == kind]
        if found:
            return found[0]
        time.sleep(min(0.005, max(0.0, deadline - time.monotonic())))
    raise SmokeBlocked("observations", "selected scene did not reach its observed input boundary")


def _latest_mvs_video(records: list[dict[str, object]]) -> dict[str, object]:
    videos = [record for record in records if record.get("event_kind") == "V"]
    if not videos:
        raise SmokeBlocked("observations", "selected scene has no completed input video")
    return videos[-1]


def _wait_for_private_rastate(path: Path, process, started_ns: int,
                              deadline: float) -> dict[str, object]:
    """Read one complete, stable private RASTATE file after a save callback."""
    if type(started_ns) is not int or started_ns <= 0:
        raise SmokeBlocked("state-container", "invalid private state file start boundary")
    while time.monotonic() < deadline:
        if frontend_exited(process):
            raise SmokeBlocked("state-container", "frontend exited before its private RASTATE save")
        try:
            first_stat = path.lstat()
            if (not stat_module.S_ISREG(first_stat.st_mode) or first_stat.st_size > RASTATE_MAX_BYTES or
                    first_stat.st_mtime_ns < started_ns):
                time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
                continue
            first = read_private_regular_file(path, RASTATE_MAX_BYTES)
            time.sleep(min(0.025, max(0.0, deadline - time.monotonic())))
            second_stat = path.lstat()
            second = read_private_regular_file(path, RASTATE_MAX_BYTES)
        except (OSError, SmokeBlocked):
            time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
            continue
        first_identity = (first_stat.st_dev, first_stat.st_ino, first_stat.st_size, first_stat.st_mtime_ns)
        second_identity = (second_stat.st_dev, second_stat.st_ino, second_stat.st_size, second_stat.st_mtime_ns)
        if first_identity != second_identity or first != second:
            continue
        mem = extract_rastate_mem(second)
        return {"container": second, "mem": mem,
                "container_sha256": hashlib.sha256(second).hexdigest(),
                "mem_sha256": hashlib.sha256(mem).hexdigest()}
    raise SmokeBlocked("state-container", "frontend did not produce one stable private RASTATE file")


def _wait_for_paused_mvs_frontend(collector: "MVSObservationCollector",
                                  process, deadline: float) -> int:
    """Confirm host callback progress stopped after the pinned pause command."""
    stable_since = time.monotonic()
    last_video = _latest_mvs_video(collector.drain())["successful_video_sequence"]
    while time.monotonic() < deadline:
        time.sleep(min(0.025, max(0.0, deadline - time.monotonic())))
        current = collector.drain()
        sequence = _latest_mvs_video(current)["successful_video_sequence"]
        if sequence != last_video:
            last_video = sequence
            stable_since = time.monotonic()
        if time.monotonic() - stable_since >= 0.25:
            return last_video
        if frontend_exited(process):
            raise SmokeBlocked("input", "frontend exited while entering its paused runloop")
    raise SmokeBlocked("input", "frontend did not hold a stable paused runloop")


def _run_private_state_transaction(args: argparse.Namespace, base: Path,
                                   attempt: dict[str, object]) -> dict[str, object]:
    context = _private_state_scene(args, base)
    executable, core, content, observed_core, identity, observed_digest, \
        witness_digest, content_digest = _continuation_identity(args, attempt)
    if content != context["content"] or content_digest != context["content_digest"]:
        raise SmokeBlocked("identity", "private continuation content binding changed before launch")
    capture_frame = context["capture_frame"]
    masks = context["masks"]
    future_masks = masks[capture_frame + 1:capture_frame + 5]
    if (type(capture_frame) is not int or capture_frame < 1 or
            len(future_masks) != CONTINUATION_WINDOW_FRAMES or masks[0] != 0):
        raise SmokeBlocked("input", "selected scene continuation window is outside its approved schedule")
    operation = validate_continuation_operation_matrix(
        "private-state", state_operations=True, autosave_interval=0,
        external_sram_write=False)
    if operation != "private-state":
        raise SmokeBlocked("operation-matrix", "private state operation profile was not selected")

    refuse_stacked_launch()
    preflight_keyboard_posting()
    production = run_smoke(args)
    if (production.get("frontend_unloaded") is not True or
            not isinstance(production.get("identity"), dict) or
            production["identity"].get("core_sha256") != identity["core_sha256"]):
        raise SmokeBlocked("production-control", "separate production-core frontend smoke failed to unload")
    work = base / f"private-state-{attempt['invocation_id']}"
    work.mkdir(mode=0o700)
    savefiles = work / "savefiles"
    savefiles.mkdir(mode=0o700)
    config, _ = _continuation_work_tree(
        work, savefiles, state_route=True, block_sram_overwrite=False,
        autosave_interval=0)
    config_bytes = read_private_regular_file(config, 12 * 1024)
    if not validate_active_config_destinations(
            config_bytes.decode("utf-8"), work, work / "captures",
            savefiles=savefiles, savestates=work / "savestates", public_state=True,
            stdin_commands=True, block_sram_overwrite=False, autosave_interval=0):
        raise SmokeBlocked("operation-matrix", "private state configuration failed its bounded route contract")
    config_digest = hashlib.sha256(config_bytes).hexdigest()
    log, process_log = work / "retroarch.log", work / "process-output.log"
    invocation = hashlib.sha256(os.urandom(24)).hexdigest()[:24]
    failure_log: Path | None = log
    owner = OwnedContinuationFrontend(
        args, executable=executable, content=content, observed_core=observed_core,
        identity=identity, config=config, log=log, process_log=process_log,
        observed_digest=observed_digest, witness=args.witness.resolve(),
        witness_digest=witness_digest, content_digest=content_digest, core=core,
        failure_root=base)
    collector = MVSObservationCollector(None, log, invocation)
    collector.expect_mask(0)
    exit_code: int | None = None
    saved_mem: bytes | None = None
    restored_mem: bytes | None = None
    witness: dict[str, object] | None = None
    alignment: dict[str, object] | None = None
    capture_boundary: dict[str, object] | None = None
    branch_video: dict[str, object] | None = None
    try:
        owner.start()
        process = owner.process
        if process is None or owner.config_digest != config_digest:
            raise SmokeBlocked("launch", "private observed-core frontend failed its launch identity")
        startup = owner.ready(invocation)
        collector.process = process
        deadline = owner.deadline

        def remaining() -> float:
            value = deadline - time.monotonic()
            if value <= 0:
                raise SmokeBlocked("observations", "private continuation exceeded its invocation deadline")
            return value

        def transition(mask: int) -> None:
            collector.drain()
            collector.expect_mask(mask)
            keys.set_mask(mask)

        with HeldMVSKeys(process) as keys:
            ready = _wait_mvs_event(collector, "R", deadline)
            transition(1)
            coin = _latest_mvs_video(collector.wait_for_video(
                int(ready["successful_video_sequence"]) + 1, 1, remaining()))
            collector.wait_for_video(int(coin["successful_video_sequence"]) + 8, 1, remaining())
            transition(0)
            collector.wait_for_video(int(ready["successful_video_sequence"]) + 600, 0, remaining())
            transition(2)
            start = _wait_mvs_event(collector, "P", deadline)
            if start["sampled_mask"] != 2:
                raise SmokeBlocked("observations", "private scene start event lacks its sampled input")
            transition(0)
            origin_records = collector.wait_for_video(
                int(start["successful_video_sequence"]) + 1, 0, remaining())
            origin = int(_latest_mvs_video(origin_records)["successful_video_sequence"])
            current_mask = 0
            for frame_index in range(1, capture_frame + 1):
                desired = masks[frame_index]
                if desired != current_mask:
                    transition(desired)
                    current_mask = desired
                collector.wait_for_video(origin + frame_index, desired, remaining())
            capture_records = collector.drain()
            capture_boundary = _latest_mvs_video(capture_records)
            started_ns = time.time_ns()
            owner.send("SAVE_STATE")
            _wait_continuation_event_count(log, "S", 1, process, deadline)
            savestate_path = work / "savestates" / f"{content.stem}.state"
            captured = _wait_for_private_rastate(savestate_path, process, started_ns, deadline)
            saved_mem = captured["mem"]
            if not isinstance(saved_mem, bytes):
                raise SmokeBlocked("state-container", "private saved state has no complete GNST payload")

            branch_mask = future_masks[0] ^ 1
            transition(branch_mask)
            branch_baseline = int(_latest_mvs_video(collector.drain())["successful_video_sequence"])
            branch_records = collector.wait_for_video(branch_baseline + 1, branch_mask, remaining())
            branch_video = _latest_mvs_video(branch_records)
            transition(future_masks[0])
            owner.send("LOAD_STATE")
            # Wait for RetroArch's early restore marker before pausing. Sending
            # both commands in one poll can coalesce them before Load State is
            # applied; every callback that runs while waiting remains part of
            # the measured continuation and is checked below.
            _wait_continuation_event_count(
                log, "R", 1, process, deadline, poll_interval=0.001)
            owner.send("PAUSE_TOGGLE")
            restored_states = wait_for_continuation_restore_states(log, 1, process, deadline)
            restored_mem = restored_states[0]
            require_matching_frontend_mem(restored_mem, saved_mem)
            _wait_for_paused_mvs_frontend(collector, process, deadline)
            already_completed = completed_continuation_frame_count(read_frontend_log(log))
            if already_completed > CONTINUATION_WINDOW_FRAMES:
                raise SmokeBlocked("continuation-observations",
                                   "state load advanced beyond its measured continuation window")
            restore_boundary = branch_video
            for index in range(already_completed, CONTINUATION_WINDOW_FRAMES):
                expected_mask = future_masks[index]
                if index:
                    transition(expected_mask)
                    time.sleep(KEY_HOLD_SECONDS)
                owner.send("FRAMEADVANCE")
                wait_for_continuation_frame(log, index + 1, process, deadline)
                collector.drain()
            final_records = collector.drain()
            observed = parse_continuation_observations(read_frontend_log(log))
            if ([frame["input_mask"] for frame in observed["frames"]] != future_masks or
                    observed["restore"].get("state") != saved_mem):
                raise SmokeBlocked("continuation-observations", "restored scene inputs or RASTATE payload diverged")
            replay_module = importlib.import_module("mvs.frontend_replay")
            alignment = replay_module.continuation_alignment(
                final_records, observed["frames"], invocation_id=invocation,
                after_video_sequence=int(restore_boundary["successful_video_sequence"]))
            witness = invoke_frontend_native_witness(
                args.witness.resolve(), content, restored_mem, observed, work,
                "private-scene-continuation")
            comparison = witness.get("comparison")
            if (not isinstance(comparison, dict) or
                    comparison.get("nonzero_audio_samples", 0) <= 0 or
                    comparison.get("nonzero_video_bytes", 0) <= 0):
                raise SmokeBlocked("continuation-witness", "private continuation did not emit meaningful raw core outputs")
        if (sha256(config) != config_digest or sha256(content) != content_digest or
                sha256(observed_core) != observed_digest or
                sha256(args.witness.resolve()) != witness_digest or
                sha256(core) != identity["core_sha256"]):
            raise SmokeBlocked("identity", "private continuation artifact changed while the frontend was running")
        local_state = context["local_state"]
        boot = context["boot"]
        scene, sound, media_pair, scene_digest = local_state.read_scene(context["contract_path"], boot)
        capture_now, masks_now, schedule_now = local_state.selected_schedule(scene, sound)
        current_context = dict(context, scene=scene, sound=sound, media_pair=media_pair,
                               scene_digest=scene_digest,
                               sound_digest=sha256(Path(boot.PHASE07_SOUND_CONTRACT_PATH)),
                               capture_frame=capture_now, masks=masks_now,
                               schedule_identity=schedule_now,
                               importer_digest=sha256(context["importer_path"]))
        if (not validate_private_state_identity(
                _private_state_identity(context, identity, observed_digest, witness_digest),
                _private_state_identity(current_context, identity, observed_digest, witness_digest)) or
                capture_now != capture_frame or masks_now != masks or
                boot.checked_importer_command(identity=scene.get("code_identity", {}).get("importer")) !=
                str(context["importer_path"])):
            raise SmokeBlocked("identity", "private scene, source, schedule, or frontend identity changed")
        exit_code = owner.quit(args.timeout)
    except SmokeBlocked:
        if failure_log is not None:
            preserve_continuation_failure_log(base, failure_log)
        raise
    finally:
        owner.cleanup()
        if owner.process is not None and exit_code is None:
            exit_code = owner.exit_code
    if exit_code != 0 or saved_mem is None or restored_mem is None or witness is None or alignment is None:
        raise SmokeBlocked("unload", "private observed-core continuation did not exit with complete evidence")
    observed = parse_continuation_observations(read_frontend_log(log))
    frame_evidence = [{"input_mask": frame["input_mask"],
                       "cycle_delta": frame["cycle_delta"],
                       "audio_frames": frame["audio_frames"],
                       "video_sha256": hashlib.sha256(frame["video"]).hexdigest(),
                       "audio_sha256": hashlib.sha256(frame["audio"]).hexdigest()}
                      for frame in observed["frames"]]
    production_identity = production["identity"]
    private_identity = _private_state_identity(context, identity, observed_digest, witness_digest)
    attempt["identity"] = {**identity,
                           "production_control_core_sha256": production_identity["core_sha256"],
                           "observed_core_sha256": observed_digest,
                           "witness_sha256": witness_digest,
                           "content_sha256": content_digest}
    return {"status": "pass", "mode": "private-state", "identity": private_identity,
            "production_control": {"status": production.get("status"),
                                   "frontend_unloaded": production.get("frontend_unloaded"),
                                   "core_sha256": production_identity["core_sha256"]},
            "private_continuation": {"saved_mem_sha256": hashlib.sha256(saved_mem).hexdigest(),
                                     "restored_mem_sha256": hashlib.sha256(restored_mem).hexdigest(),
                                     "saved_and_restored_mem_equal": saved_mem == restored_mem,
                                     "branch_mask": future_masks[0] ^ 1,
                                     "branch_video_sequence": (branch_video or {}).get("successful_video_sequence"),
                                     "capture_video_sequence": (capture_boundary or {}).get("successful_video_sequence"),
                                     "future_masks": future_masks,
                                     "alignment": alignment,
                                     "frames": frame_evidence,
                                     "native_witness": witness,
                                     "frontend_exit_code": exit_code,
                                     "configuration_sha256": config_digest,
                                     "autosave_interval_seconds": 0,
                                     "block_sram_overwrite": False,
                                     "sram_claim": "not evaluated"}}


def run_private_state(args: argparse.Namespace) -> dict[str, object]:
    validate_continuation_operation_matrix(
        "private-state", state_operations=True, autosave_interval=0,
        external_sram_write=False)
    base, report_path = private_public_state_workspace(getattr(args, "report", None))
    attempt: dict[str, object] = {
        "schema_version": 1, "mode": "private-state", "status": "running",
        "invocation_id": hashlib.sha256(os.urandom(24)).hexdigest()[:24],
    }
    try:
        result = _run_private_state_transaction(args, base, attempt)
        attempt.update(status="pass", result=result)
        write_private_public_state_report(report_path, attempt)
        return result
    except SmokeBlocked as error:
        status = "blocked_or_unknown" if error.stage in {
            "preflight", "pre-launch", "launch", "input", "interrupted"} else "fail"
        trace = traceback.extract_tb(error.__traceback__)
        attempt.update(status=status, stage=error.stage,
                       reason=sanitize_diagnostic_text(str(error)),
                       failure_frames=[{"function": frame.name, "line": frame.lineno}
                                       for frame in trace[-6:]],
                       identity=attempt.get("identity", {}))
        write_private_public_state_report(report_path, attempt)
        raise
    except Exception as error:
        trace = traceback.extract_tb(error.__traceback__)
        attempt.update(status="fail", stage="internal",
                       reason=f"execution failed ({type(error).__name__})",
                       internal_error=type(error).__name__,
                       internal_frames=[{"function": frame.name, "line": frame.lineno}
                                        for frame in trace[-6:]],
                       identity=attempt.get("identity", {}))
        symbol = getattr(error, "name", None)
        if isinstance(symbol, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", symbol):
            attempt["internal_symbol"] = symbol
        write_private_public_state_report(report_path, attempt)
        raise


def run_public_state(args: argparse.Namespace) -> dict[str, object]:
    base, report_path = private_public_state_workspace(getattr(args, "report", None))
    attempt: dict[str, object] = {
        "schema_version": 1,
        "mode": "public-state",
        "status": "running",
        "invocation_id": hashlib.sha256(os.urandom(24)).hexdigest()[:24],
    }
    try:
        result = _run_public_state_transaction(args, base, attempt)
        attempt.update(status="pass", result=result)
        write_private_public_state_report(report_path, attempt)
        return result
    except SmokeBlocked as error:
        status = "blocked_or_unknown" if error.stage in {
            "preflight", "pre-launch", "launch", "input", "interrupted"} else "fail"
        attempt.update(status=status, stage=error.stage,
                       reason=sanitize_diagnostic_text(str(error)),
                       identity=attempt.get("identity", {}))
        if error.stage == "sram-persistence" and isinstance(error.diagnostic, dict):
            attempt["diagnostic"] = {
                key: error.diagnostic[key]
                for key in ("entry_count", "sram_outcome", "bytes", "sha256")
                if key in error.diagnostic
            }
        write_private_public_state_report(report_path, attempt)
        raise
    except Exception as error:
        attempt.update(status="fail", stage="internal",
                       reason=f"execution failed ({type(error).__name__})",
                       identity=attempt.get("identity", {}))
        write_private_public_state_report(report_path, attempt)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retroarch", type=Path, required=True, help="RetroArch .app bundle")
    parser.add_argument("--core", type=Path, required=True, help="built glueyneo_libretro.dylib")
    parser.add_argument("--content", type=Path, required=True,
                        help="generated GNFX fixture or normalized GNMV bundle")
    parser.add_argument(
        "--diagnose", action="store_true",
        help="compare fresh no-content and core/content launches; this is not acceptance",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--continuation-route",
                        choices=("public-state", "sram-policies", "periodic-save",
                                 "focused-reset-control", "focused-undo-control",
                                 "private-state"),
                        default=None)
    parser.add_argument("--private-contract", type=Path, default=None,
                        help="ignored current selected-scene contract for private-state continuation")
    parser.add_argument("--observed-core", type=Path, default=None)
    parser.add_argument("--witness", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--child-pid-file", type=Path, default=None,
                        help="record the launched frontend PID here for the runner's scoped cleanup")
    args = parser.parse_args()
    continuation_arguments = (args.observed_core, args.witness, args.report)
    if args.continuation_route is None and any(value is not None for value in continuation_arguments):
        parser.error("--observed-core, --witness, and --report require a continuation route")
    if args.continuation_route is not None and any(value is None for value in continuation_arguments):
        parser.error("--continuation-route requires --observed-core, --witness, and --report")
    if args.continuation_route == "private-state" and args.private_contract is None:
        parser.error("--continuation-route private-state requires --private-contract")
    if args.continuation_route != "private-state" and args.private_contract is not None:
        parser.error("--private-contract requires --continuation-route private-state")
    if args.timeout <= 0 or args.timeout > 120:
        parser.error("--timeout must be greater than 0 and at most 120 seconds")
    install_signal_cleanup()
    try:
        if args.continuation_route == "public-state":
            result = run_public_state(args)
        elif args.continuation_route == "private-state":
            result = run_private_state(args)
            result = private_state_public_receipt(result.get("status"))
        elif args.continuation_route == "sram-policies":
            result = run_sram_policies(args)
        elif args.continuation_route == "periodic-save":
            result = run_periodic_save(args)
        elif args.continuation_route == "focused-reset-control":
            result = run_focused_reset_control(args)
        elif args.continuation_route == "focused-undo-control":
            result = run_focused_undo_control(args)
        else:
            result = run_diagnostics(args) if args.diagnose else run_smoke(args)
        print(public_json(result))
        return 0 if result.get("status") == "pass" else 1
    except SmokeBlocked as error:
        if args.continuation_route == "private-state":
            status = "blocked_or_unknown" if error.stage in {
                "preflight", "pre-launch", "launch", "input", "interrupted"} else "fail"
            print(public_json(private_state_public_receipt(status)))
            return 1
        identity: dict[str, str] = {}
        try:
            _, _, _, identity = validate_inputs(args)
        except SmokeBlocked:
            pass
        result: dict[str, object] = {
            "status": "blocked_or_unknown",
            "stage": error.stage,
            "reason": sanitize_diagnostic_text(str(error)),
            "identity": identity,
        }
        if error.diagnostic is not None:
            result["diagnostic"] = error.diagnostic
        if error.availability is not None:
            result["availability"] = error.availability
        print(public_json(result))
        return 1
    except Exception as error:  # A decode or parser failure must not print an unscanned traceback.
        if args.continuation_route == "private-state":
            print(public_json(private_state_public_receipt("fail")))
            return 1
        print(public_json({"status": "blocked_or_unknown", "stage": "internal",
                           "reason": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
