#!/usr/bin/env python3
"""Bounded real-RetroArch load/input/software-video/unload smoke for macOS."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import plistlib
import platform
import re
import signal
import struct
import subprocess
import sys
import tempfile
import time
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
GNMV_PROFILE_MSX = 0x4D53584D
GNMV_REGION_LENGTHS = {
    1: 0x80000,
    2: 0x500000,
    3: 0x20000,
    4: 0x20000,
    5: 0xA00000,
    6: 0x3000000,
}
GNMV_MAX_BYTES = 64 * 1024 * 1024
WIDTH = 320
HEIGHT = 224
RIGHT_KEY_CODE = 124
DIAGNOSTIC_OUTPUT_LIMIT = 12 * 1024
DIAGNOSTIC_PROBE_SECONDS = 1.0
CRASH_REPORT_WAIT_SECONDS = 8.0
APPLICATION_SERVICES = "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
CG_HID_EVENT_TAP = 0
# RetroArch samples keyboard state once per frame (~16.7 ms at 60 Hz); hold
# each injected key for several frames so the poll observes the press.
KEY_HOLD_SECONDS = 0.1
ARROW_HOLD_SECONDS = 0.25
KEY_GAP_SECONDS = 0.05
FOCUS_SETTLE_SECONDS = 0.2
SCREENSHOT_KEY_CODE = 100
SCREENSHOT_RETRY_SECONDS = 1.0
LEFT_KEY_CODE = 123


class SmokeBlocked(RuntimeError):
    def __init__(self, stage: str, detail: str, *, diagnostic: dict[str, object] | None = None) -> None:
        super().__init__(detail)
        self.stage = stage
        self.diagnostic = diagnostic
        self.availability = (
            "unavailable" if stage == "input" and "could not inject" in detail else None
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_normalized_mvs_bundle(content: bytes) -> bool:
    if (len(content) < 16 or content[:4] != b"GNMV" or
            int.from_bytes(content[4:8], "big") != 1 or
            int.from_bytes(content[8:12], "big") != GNMV_PROFILE_MSX or
            int.from_bytes(content[12:16], "big") != len(GNMV_REGION_LENGTHS) or
            len(content) > GNMV_MAX_BYTES):
        return False
    cursor = 16
    found: set[int] = set()
    for _ in range(len(GNMV_REGION_LENGTHS)):
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
    return cursor == len(content) and found == set(GNMV_REGION_LENGTHS)


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
    text = json.dumps(result, sort_keys=True)
    try:
        private_paths.scan_public_value(result, (Path(__file__).resolve().parents[2],))
    except private_paths.PrivatePathError:
        result["status"] = "fail"
        text = json.dumps({"status": "fail", "reason": "private-path-survived"}, sort_keys=True)
    return text


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
    if len(raw) != expected or inflater.unconsumed_tail:
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


def post_held_key(key_code: int, hold: float) -> None:
    """Post one HID keyDown, hold it, then post keyUp.

    RetroArch's cocoa input driver records key state from events and samples
    that state once per frame. System Events `key code` sends down and up
    back-to-back, so both can land between samples and the press is never seen.
    Holding for several frames makes the press visible to the per-frame poll.
    """
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
    events = [services.CGEventCreateKeyboardEvent(None, key_code, down) for down in (True, False)]
    try:
        if not all(events):
            raise OSError("macOS could not create a keyboard event")
        services.CGEventPost(CG_HID_EVENT_TAP, events[0])
        time.sleep(hold)
        services.CGEventPost(CG_HID_EVENT_TAP, events[1])
    finally:
        for event in events:
            if event:
                services.CFRelease(event)


def inject_key(key_code: int, *, repeats: int = 1, hold: float = KEY_HOLD_SECONDS) -> None:
    script = 'tell application "System Events" to set frontmost of process "RetroArch" to true'
    try:
        subprocess.run(["/usr/bin/osascript", "-e", script], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=8)
        time.sleep(FOCUS_SETTLE_SECONDS)
        for _ in range(repeats):
            post_held_key(key_code, hold)
            time.sleep(KEY_GAP_SECONDS)
    except (OSError, AttributeError, subprocess.SubprocessError) as error:
        raise SmokeBlocked("input", "macOS could not inject the mapped arrow-key input") from error


def screenshot_snapshot(directory: Path) -> dict[Path, int]:
    return {path: path.stat().st_mtime_ns for path in directory.glob("*.png")}


def write_frontend_config(work: Path, screenshots: Path) -> Path:
    config = work / "retroarch.cfg"
    config.write_text(
        "\n".join(
            [
                'video_driver = "gl"',
                'video_fullscreen = "false"',
                'video_windowed_fullscreen = "false"',
                'video_scale = "2"',
                'video_smooth = "false"',
                'video_vsync = "true"',
                # Capture the raw core frame (WIDTH x HEIGHT), not the scaled
                # viewport, so OSD text cannot cover the guest marker.
                'video_gpu_screenshot = "false"',
                'notification_show_screenshot = "false"',
                'input_driver = "cocoa"',
                'input_player1_left = "left"',
                'input_player1_right = "right"',
                'input_screenshot = "f8"',
                f'content_history_path = "{work / "content_history.lpl"}"',
                f'savefile_directory = "{work}"',
                f'savestate_directory = "{work}"',
                f'system_directory = "{work}"',
                f'cache_directory = "{work}"',
                f'screenshot_directory = "{screenshots}"',
                'log_to_file = "true"',
                f'log_dir = "{work}"',
            ]
        ) + "\n",
        encoding="utf-8",
    )
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
        config = write_frontend_config(work, screenshots)
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


def run_smoke(args: argparse.Namespace) -> dict[str, object]:
    executable, core, content, identity = validate_inputs(args)
    with tempfile.TemporaryDirectory(prefix="glueyneo-retroarch-") as temporary:
        work = Path(temporary)
        screenshots = work / "screenshots"
        screenshots.mkdir()
        config = write_frontend_config(work, screenshots)
        log = work / "retroarch.log"
        process_log = work / "process-output.log"
        prior_crash_reports = crash_report_snapshot()
        started_at = time.time()
        with process_log.open("wb") as log_stream:
            refuse_stacked_launch()
            process = None
            outcome: dict[str, object] = {"observations": []}
            survived_before_screenshot = False
            try:
                with launch_window():
                    try:
                        process = subprocess.Popen(
                            [str(executable), "--verbose", "--config", str(config),
                             "-L", str(core), str(content)],
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
                first = request_screenshot(process, screenshots, {}, args.timeout)
                first_frame = decode_png(first)
                time.sleep(0.25)
                second = request_screenshot(process, screenshots,
                                            screenshot_snapshot(screenshots), args.timeout)
                second_frame = decode_png(second)
                first_marker = right_marker = None
                if identity["content_kind"] == "public-fixture":
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
                else:
                    inject_key(RIGHT_KEY_CODE, hold=ARROW_HOLD_SECONDS)
                    request_screenshot(process, screenshots,
                                       screenshot_snapshot(screenshots), args.timeout)
                    outcome["input_response"] = "unknown"

                if not request_frontend_quit(identity["bundle_id"], process, args.timeout):
                    raise SmokeBlocked("unload", "RetroArch did not quit cleanly after loaded content")
                outcome["observations"] = [
                    "RetroArch launched the requested core and content path",
                    "frontend produced bounded screenshots",
                    "configured Right Arrow input was injected",
                    "RetroArch exited through its application quit path",
                ]
                if first_marker is not None and right_marker is not None:
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
                if process is not None:
                    try:
                        request_frontend_quit(identity["bundle_id"], process, args.timeout)
                    finally:
                        kill_launched_group(process)
            result_status = "pass" if identity["content_kind"] == "public-fixture" else "unknown"
            return {"status": result_status, "identity": identity, **outcome}


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
    parser.add_argument("--child-pid-file", type=Path, default=None,
                        help="record the launched frontend PID here for the runner's scoped cleanup")
    args = parser.parse_args()
    if args.timeout <= 0 or args.timeout > 120:
        parser.error("--timeout must be greater than 0 and at most 120 seconds")
    install_signal_cleanup()
    try:
        result = run_diagnostics(args) if args.diagnose else run_smoke(args)
        print(public_json(result))
        return 0 if result.get("status") == "pass" else 1
    except SmokeBlocked as error:
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
        print(public_json({"status": "blocked_or_unknown", "stage": "internal",
                           "reason": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
