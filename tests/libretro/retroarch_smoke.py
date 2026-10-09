#!/usr/bin/env python3
"""Bounded real-RetroArch load/input/software-video/unload smoke for macOS."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import platform
import re
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path


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
        if cursor > len(content) or len(content) - cursor < 12:
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
    roots = [str(Path.home()), "/Users/", "/Volumes/", "/tmp/", "/private/tmp/",
             "/var" + "/folders/", "/private" + "/var" + "/folders/", str(Path(__file__).resolve().parents[2])]
    if temporary_root is not None:
        roots.append(str(temporary_root))
    roots = sorted({root for root in roots if root}, key=len, reverse=True)
    root_pattern = re.compile(r"(?<![A-Za-z0-9._-])(?:" + "|".join(re.escape(root) for root in roots) + r")")
    match = root_pattern.search(text)
    if match is not None:
        # Frontend and crash output is one unstructured value. A newline or
        # punctuation cannot prove a private-path boundary, so drop its tail.
        root = match.group()
        if root.startswith(str(Path(__file__).resolve().parents[2])):
            marker = "[repo]"
        elif root == str(Path.home()):
            marker = "[home]"
        elif (temporary_root is not None and root == str(temporary_root)) or "/tmp/" in root or "var/folders" in root:
            marker = "[temporary]"
        else:
            marker = "[user]"
        text = text[:match.start()] + marker
    if len(text) > DIAGNOSTIC_OUTPUT_LIMIT:
        marker = "\n[diagnostic output truncated]"
        text = text[-(DIAGNOSTIC_OUTPUT_LIMIT - len(marker)):] + marker
    return text.strip()


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
    if not bool(no_content.get("survived_window")):
        return "frontend-startup-failed"
    if not bool(core_content.get("survived_window")):
        return "core-or-content-invocation-failed"
    return "both-launch-probes-survived"


def select_fresh_screenshot(directory: Path, prior: dict[Path, int]) -> Path | None:
    candidates = [
        path for path in directory.glob("*.png")
        if path not in prior or path.stat().st_mtime_ns > prior[path]
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else None


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
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SmokeBlocked("video", "RetroArch screenshot is not a PNG")
    offset = 8
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += length + 12
        if kind == b"IHDR":
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
    channels = {2: 3, 6: 4}.get(color_type)
    if channels is None:
        raise SmokeBlocked("video", "PNG is not RGB or RGBA")
    bpp = channels
    stride = width * bpp
    raw = zlib.decompress(compressed)
    expected = height * (stride + 1)
    if len(raw) != expected:
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
    if process.poll() is not None:
        raise SmokeBlocked("first-screenshot", f"RetroArch exited before screenshot (status {process.returncode})")
    inject_key(100, repeats=1)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        fresh = select_fresh_screenshot(directory, prior)
        if fresh is not None:
            return fresh
        time.sleep(0.1)
    raise SmokeBlocked("video", "RetroArch did not create a software-video screenshot")


def inject_key(key_code: int, *, repeats: int = 24) -> None:
    script = (
        'tell application "System Events" to set frontmost of process "RetroArch" to true\n'
        'tell application "System Events"\n'
        f"repeat {repeats} times\nkey code {key_code}\ndelay 0.025\nend repeat\n"
        "end tell"
    )
    try:
        subprocess.run(["/usr/bin/osascript", "-e", script], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=8)
    except (OSError, subprocess.SubprocessError) as error:
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


def request_frontend_quit(bundle_id: str, process: subprocess.Popen[bytes], timeout: float) -> bool:
    if process.poll() is not None:
        return process.returncode == 0
    if bundle_id == EXPECTED_BUNDLE_IDENTIFIER:
        try:
            subprocess.run(
                ["/usr/bin/osascript", "-e", f'tell application id "{bundle_id}" to quit'],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=min(8.0, timeout),
            )
            process.wait(timeout=min(8.0, timeout))
            return process.returncode == 0
        except (OSError, subprocess.SubprocessError):
            pass
    process.terminate()
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)
    return process.returncode == 0


def run_launch_probe(
    executable: Path,
    core: Path,
    content: Path,
    bundle_id: str,
    *,
    probe: str,
    timeout: float,
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
        try:
            with process_log.open("wb") as log_stream:
                process = subprocess.Popen(
                    arguments, stdout=log_stream, stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                try:
                    process.wait(timeout=min(DIAGNOSTIC_PROBE_SECONDS, timeout))
                    survived_window = False
                except subprocess.TimeoutExpired:
                    survived_window = True
                return_code = process.poll()
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
                cleanup_return_code = process.poll()
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
    no_content = run_launch_probe(
        executable, core, content, identity["bundle_id"],
        probe="no_content", timeout=args.timeout,
    )
    core_content = run_launch_probe(
        executable, core, content, identity["bundle_id"],
        probe="core_content", timeout=args.timeout,
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
    if (not isinstance(bundle_id, str) or
            bundle_id != EXPECTED_BUNDLE_IDENTIFIER or
            re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", bundle_id) is None):
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
            outcome: dict[str, object] = {"observations": []}
            survived_before_screenshot = False
            try:
                time.sleep(0.5)
                survived_before_screenshot = process.poll() is None
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
                    inject_key(123)
                    time.sleep(0.25)
                    wrong_input = request_screenshot(
                        process, screenshots, screenshot_snapshot(screenshots), args.timeout
                    )
                    wrong_marker = find_marker(decode_png(wrong_input))
                    if wrong_marker != first_marker:
                        raise SmokeBlocked("input", "Left Arrow wrong-input control moved the guest marker")
                    inject_key(RIGHT_KEY_CODE)
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
                    inject_key(RIGHT_KEY_CODE)
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
                return_code = process.poll()
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
                request_frontend_quit(identity["bundle_id"], process, args.timeout)
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
    args = parser.parse_args()
    if args.timeout <= 0 or args.timeout > 120:
        parser.error("--timeout must be greater than 0 and at most 120 seconds")
    try:
        result = run_diagnostics(args) if args.diagnose else run_smoke(args)
        print(json.dumps(result, sort_keys=True))
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
        print(json.dumps(result, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
