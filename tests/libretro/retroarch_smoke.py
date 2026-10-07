#!/usr/bin/env python3
"""Bounded real-RetroArch load/input/software-video/unload smoke for macOS."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import platform
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
WIDTH = 320
HEIGHT = 224
RIGHT_KEY_CODE = 124


class SmokeBlocked(RuntimeError):
    def __init__(self, stage: str, detail: str) -> None:
        super().__init__(detail)
        self.stage = stage


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        raise SmokeBlocked("frontend", f"RetroArch exited before screenshot (status {process.returncode})")
    inject_key(100, repeats=1)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        candidates = {
            path for path in directory.glob("*.png")
            if path not in prior or path.stat().st_mtime_ns > prior[path]
        }
        if candidates:
            return max(candidates, key=lambda path: path.stat().st_mtime_ns)
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
        raise SmokeBlocked("input", "built Libretro core or generated fixture is missing")
    fixture = content.read_bytes()
    if len(fixture) != 602 or fixture[:4] != b"GNFX" or fixture[4:8] != b"\0\0\0\1":
        raise SmokeBlocked("input", "content is not the generated bounded GNFX v1 fixture")
    identity = {
        "retroarch_version": version,
        "retroarch_executable_sha256": executable_hash,
        "core_sha256": sha256(core),
        "fixture_sha256": hashlib.sha256(fixture).hexdigest(),
        "os": f"macOS {platform.mac_ver()[0]} {platform.machine()}",
        "input_mapping": "RetroPad RIGHT <- Right Arrow; LEFT control <- Left Arrow",
        "control": "local keyboard and frontend screenshots; no network command interface",
        "bundle_id": str(info.get("CFBundleIdentifier", "")),
    }
    return executable, core, content, identity


def run_smoke(args: argparse.Namespace) -> dict[str, object]:
    executable, core, content, identity = validate_inputs(args)
    with tempfile.TemporaryDirectory(prefix="glueyneo-retroarch-") as temporary:
        work = Path(temporary)
        screenshots = work / "screenshots"
        screenshots.mkdir()
        config = work / "retroarch.cfg"
        log = work / "retroarch.log"
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
        with log.open("wb") as log_stream:
            try:
                process = subprocess.Popen(
                    [str(executable), "--verbose", "--config", str(config),
                     "-L", str(core), str(content)],
                    stdout=log_stream,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            except OSError as error:
                raise SmokeBlocked("launch", "pinned RetroArch could not be started") from error
            outcome: dict[str, object] = {"observations": []}
            try:
                time.sleep(0.5)
                first = request_screenshot(process, screenshots, {}, args.timeout)
                first_marker = find_marker(decode_png(first))
                time.sleep(0.25)
                second = request_screenshot(process, screenshots,
                                            screenshot_snapshot(screenshots), args.timeout)
                second_marker = find_marker(decode_png(second))
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
                if right_marker[1] != first_marker[1] or right_marker[2] != first_marker[2] or right_marker[0] <= first_marker[0]:
                    raise SmokeBlocked("input", "mapped Right Arrow did not move the guest marker right")

                bundle_id = identity["bundle_id"]
                try:
                    subprocess.run(
                        ["/usr/bin/osascript", "-e",
                         f'tell application id "{bundle_id}" to quit'],
                        check=True, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, timeout=8,
                    )
                    process.wait(timeout=args.timeout)
                except (OSError, subprocess.SubprocessError) as error:
                    raise SmokeBlocked("unload", "RetroArch did not quit cleanly after loaded content") from error
                if process.returncode != 0:
                    raise SmokeBlocked("unload", f"RetroArch shutdown status was {process.returncode}")
                outcome["observations"] = [
                    "RetroArch launched the requested core and generated content path",
                    "frontend screenshot contained the guest marker and black backdrop",
                    "repeated no-input screenshots retained the same marker position",
                    "configured Left Arrow wrong-input control did not move the marker",
                    "configured Right Arrow input moved the marker right",
                    "RetroArch exited cleanly through its application quit path after loaded content",
                ]
                outcome["marker_before"] = list(first_marker)
                outcome["marker_after_right"] = list(right_marker)
                outcome["frontend_unloaded"] = True
            finally:
                if process.poll() is None:
                    try:
                        subprocess.run(
                            ["/usr/bin/osascript", "-e",
                             f'tell application id "{identity["bundle_id"]}" to quit'],
                            check=False, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=8,
                        )
                    except (OSError, subprocess.SubprocessError):
                        pass
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=3)
            return {"status": "pass", "identity": identity, **outcome}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retroarch", type=Path, required=True, help="RetroArch .app bundle")
    parser.add_argument("--core", type=Path, required=True, help="built glueyneo_libretro.dylib")
    parser.add_argument("--content", type=Path, required=True, help="CMake-generated public-playable.bin")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    if args.timeout <= 0 or args.timeout > 120:
        parser.error("--timeout must be greater than 0 and at most 120 seconds")
    try:
        result = run_smoke(args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except SmokeBlocked as error:
        identity: dict[str, str] = {}
        try:
            _, _, _, identity = validate_inputs(args)
        except SmokeBlocked:
            pass
        print(json.dumps({
            "status": "blocked_or_unknown",
            "stage": error.stage,
            "reason": str(error),
            "identity": identity,
        }, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
