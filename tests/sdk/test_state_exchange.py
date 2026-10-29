#!/usr/bin/env python3
"""Bounded host-side supervisor for real native-state process exchange."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field


ROOT = Path(__file__).resolve().parents[2]
MAX_CHILD_SECONDS = 60.0
MAX_CHILD_CPU_SECONDS = 30
MAX_CHILD_OUTPUT_BYTES = 16 * 1024
MAX_PAYLOAD_BYTES = 1024 * 1024
MAX_TRACE_BYTES = 2 * 1024 * 1024
MAX_LOCAL_CHILD_SECONDS = 180.0
MAX_LOCAL_CHILD_CPU_SECONDS = 120
MAX_LOCAL_TRACE_BYTES = 16 * 1024 * 1024
MAX_LOCAL_FUTURE_FRAMES = 8
DIAGNOSTIC_BUDGETS = [4, 8, 20, 4, 16, 8, 20, 4, 16, 8, 20, 4]
MVS_INPUTS = [0, 0x40, 0x80, 0]
PROFILE_CASES = ("mvs", "diagnostic")

IDENTITY_ROOTS = (
    "src",
    "include/glueyneo",
    "tests/sdk",
    "tests/fixture",
    "third_party/chips",
    "third_party/ymfm/src",
)
IDENTITY_EXTRA_FILES = (
    "CMakeLists.txt",
    "CMakePresets.json",
    "third_party/ymfm/NOTICE.md",
)
IDENTITY_SUFFIXES = {".c", ".h", ".cpp", ".hpp", ".py", ".json", ".md"}


class ExchangeFailure(RuntimeError):
    def __init__(self, assertion: str, report: dict[str, object]):
        super().__init__(assertion)
        self.assertion = assertion
        self.report = report


@dataclass
class ChildResult:
    command: list[str]
    returncode: int
    started_ns: int
    finished_ns: int
    output: str
    pid: int | None
    wall_seconds: float
    output_bytes: int
    timed_out: bool = False
    output_overflow: bool = False


@dataclass
class PairReport:
    profile: str
    exporter: ChildResult | None = None
    importer: ChildResult | None = None
    export_metadata: dict[str, object] = field(default_factory=dict)
    import_metadata: dict[str, object] = field(default_factory=dict)
    expected_sha256: str = ""
    actual_sha256: str = ""
    payload_sha256: str = ""
    trace_stats: dict[str, int] = field(default_factory=dict)
    passed_assertions: int = 0


def sha256_paths(relative_paths: list[str]) -> str:
    material = bytearray()
    for relative in sorted(relative_paths):
        path = ROOT / relative
        material.extend(relative.encode("utf-8") + b"\0")
        material.extend(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        material.extend(b"\n")
    return hashlib.sha256(material).hexdigest()


def future_input_identity() -> str:
    schedule = {"diagnostic_budgets": DIAGNOSTIC_BUDGETS,
                "mvs_input_masks": MVS_INPUTS}
    encoded = json.dumps(schedule, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def dependency_provenance() -> dict[str, str]:
    chips_notice = (ROOT / "third_party/chips/NOTICE.md").read_text(encoding="utf-8")
    ymfm_notice_path = ROOT / "third_party/ymfm/NOTICE.md"
    ymfm_notice = ymfm_notice_path.read_text(encoding="utf-8")
    chips_revision = re.search(r"Revision:\s*`([0-9a-f]{40})`", chips_notice)
    ymfm_revision = re.search(r"upstream revision `([0-9a-f]{40})`", ymfm_notice)
    ymfm_sources = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "third_party/ymfm/src").rglob("*")
        if path.is_file() and path.suffix in {".cpp", ".h", ".hpp", ".ipp"}
    )
    require(chips_revision is not None, "sdk.state.exchange.z80-revision-present", {})
    require(ymfm_revision is not None, "sdk.state.exchange.ymfm-revision-present", {})
    return {
        "z80_upstream_revision": chips_revision.group(1),
        "z80_source_sha256": hashlib.sha256(
            (ROOT / "third_party/chips/z80.h").read_bytes()).hexdigest(),
        "chips_notice_sha256": hashlib.sha256(chips_notice.encode("utf-8")).hexdigest(),
        "ymfm_upstream_revision": ymfm_revision.group(1),
        "ymfm_source_closure_sha256": sha256_paths(ymfm_sources),
        "ymfm_notice_sha256": hashlib.sha256(ymfm_notice.encode("utf-8")).hexdigest(),
    }


def cmake_cache(path: Path) -> dict[str, str]:
    cache_file = path / "CMakeCache.txt"
    values: dict[str, str] = {}
    if not cache_file.is_file():
        return values
    for line in cache_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("//") or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split("=", 1)
        name = key.split(":", 1)[0]
        values[name] = value
    return values


def normalized_compile_commands(build_dir: Path) -> tuple[str, int]:
    path = build_dir / "compile_commands.json"
    if not path.is_file():
        return "", 0
    entries = json.loads(path.read_text(encoding="utf-8"))
    normalized: list[dict[str, object]] = []
    for entry in entries:
        arguments = entry.get("arguments")
        if arguments is None:
            arguments = shlex.split(str(entry.get("command", "")))
        tokens = [str(token) for token in arguments]
        if tokens:
            tokens[0] = Path(tokens[0]).name
        for index, token in enumerate(tokens):
            token = token.replace(str(build_dir), "$BUILD")
            token = token.replace(str(ROOT), "$SOURCE")
            tokens[index] = token
        normalized.append({
            "file": str(entry.get("file", "")).replace(str(ROOT), "$SOURCE"),
            "arguments": tokens,
        })
    encoded = json.dumps(sorted(normalized, key=lambda item: str(item["file"])),
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest(), len(normalized)


def cmake_compiler_identity(build_dir: Path, language: str) -> tuple[str, str]:
    pattern = f"CMakeFiles/*/CMake{language}Compiler.cmake"
    paths = sorted(build_dir.glob(pattern))
    if not paths:
        return "unknown", "unknown"
    content = paths[-1].read_text(encoding="utf-8", errors="replace")
    identifier = re.search(
        rf'set\(CMAKE_{language}_COMPILER_ID "([^"]+)"\)', content)
    version = re.search(
        rf'set\(CMAKE_{language}_COMPILER_VERSION "([^"]+)"\)', content)
    return (identifier.group(1) if identifier else "unknown",
            version.group(1) if version else "unknown")


def build_provenance(runner: Path, expected_configuration: str) -> dict[str, object]:
    build_dir = runner.resolve().parent
    cache = cmake_cache(build_dir)
    config = cache.get("CMAKE_BUILD_TYPE", "")
    require(config == expected_configuration,
            f"sdk.state.exchange.{expected_configuration.lower()}-build-type", {})
    require(cache.get("GLUEYNEO_BUILD_TESTS") == "ON" and
            cache.get("GLUEYNEO_CPU_EXPERIMENT") == "OFF" and
            cache.get("GLUEYNEO_OWNED_CPU_EXPERIMENT") == "OFF" and
            cache.get("GLUEYNEO_SDK_SANITIZER") == "NONE",
            f"sdk.state.exchange.{expected_configuration.lower()}-full-sdk-options", {})
    compile_digest, compile_count = normalized_compile_commands(build_dir)
    require(bool(compile_digest) and compile_count > 0,
            f"sdk.state.exchange.{expected_configuration.lower()}-compile-options-present", {})
    c_compiler, c_version = cmake_compiler_identity(build_dir, "C")
    cxx_compiler, cxx_version = cmake_compiler_identity(build_dir, "CXX")
    require(c_compiler != "unknown" and c_version != "unknown" and
            cxx_compiler != "unknown" and cxx_version != "unknown",
            f"sdk.state.exchange.{expected_configuration.lower()}-compiler-identities-present",
            {})
    cmake_version = subprocess.run(
        ["cmake", "--version"], cwd=ROOT, capture_output=True, text=True,
        timeout=10, check=True).stdout.splitlines()[0]
    relevant_options = {
        key: value for key, value in sorted(cache.items())
        if key.startswith("GLUEYNEO_") or key in {
            "CMAKE_BUILD_TYPE", "CMAKE_C_COMPILER_ID", "CMAKE_C_COMPILER_VERSION",
            "CMAKE_CXX_COMPILER_ID", "CMAKE_CXX_COMPILER_VERSION",
            "CMAKE_EXPORT_COMPILE_COMMANDS", "CMAKE_GENERATOR",
        }
    }
    relevant_options.update({
        "CMAKE_C_COMPILER_ID": c_compiler,
        "CMAKE_C_COMPILER_VERSION": c_version,
        "CMAKE_CXX_COMPILER_ID": cxx_compiler,
        "CMAKE_CXX_COMPILER_VERSION": cxx_version,
    })
    return {
        "configuration": config,
        "cmake_version": cmake_version,
        "generator": cache.get("CMAKE_GENERATOR", "unknown"),
        "c_compiler": c_compiler,
        "c_compiler_version": c_version,
        "cxx_compiler": cxx_compiler,
        "cxx_compiler_version": cxx_version,
        "compile_commands_sha256": compile_digest,
        "compile_command_count": compile_count,
        "options_sha256": hashlib.sha256(json.dumps(
            relevant_options, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
        "platform": {"system": platform.system(), "release": platform.release(),
                     "architecture": platform.machine()},
    }


def source_identity(root: Path = ROOT) -> str:
    paths: set[str] = set()
    for directory in IDENTITY_ROOTS:
        base = root / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in IDENTITY_SUFFIXES:
                paths.add(path.relative_to(root).as_posix())
    paths.update(IDENTITY_EXTRA_FILES)
    material = bytearray()
    for relative in sorted(paths):
        path = root / relative
        if not path.is_file():
            continue
        file_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        material.extend(f"{relative}:{file_digest}\n".encode("utf-8"))
    return hashlib.sha256(material).hexdigest()


def u32(data: bytes, offset: int) -> tuple[int, int]:
    if len(data) - offset < 4:
        raise ValueError("truncated 32-bit field")
    return struct.unpack_from(">I", data, offset)[0], offset + 4


def u64(data: bytes, offset: int) -> tuple[int, int]:
    if len(data) - offset < 8:
        raise ValueError("truncated 64-bit field")
    return struct.unpack_from(">Q", data, offset)[0], offset + 8


def parse_trace(profile: str, data: bytes) -> dict[str, int]:
    if len(data) > MAX_TRACE_BYTES or len(data) < 12:
        raise ValueError("missing or oversized trace")
    expected_magic = b"GNSM" if profile == "mvs" else b"GNSD"
    if data[:4] != expected_magic:
        raise ValueError("wrong trace profile or missing observation")
    version, offset = u32(data, 4)
    count, offset = u32(data, offset)
    if version != 1 or count == 0 or count > 16:
        raise ValueError("invalid trace header or zero observations")

    stats = {
        "observation_count": count,
        "elapsed_cycles": 0,
        "nonzero_guest_values": 0,
        "video_frames": 0,
        "video_pixels": 0,
        "video_bytes": 0,
        "nonzero_video_bytes": 0,
        "audio_frames": 0,
        "audio_samples": 0,
        "nonzero_audio_samples": 0,
    }
    if profile == "diagnostic":
        if count != len(DIAGNOSTIC_BUDGETS):
            raise ValueError("diagnostic observation count differs from schedule")
        for expected_budget in DIAGNOSTIC_BUDGETS:
            budget, offset = u64(data, offset)
            requested, offset = u64(data, offset)
            elapsed, offset = u64(data, offset)
            _overshoot, offset = u64(data, offset)
            _instructions, offset = u64(data, offset)
            for _ in range(7):
                _field, offset = u32(data, offset)
            if len(data) - offset < 1:
                raise ValueError("missing diagnostic ready observation")
            ready = data[offset]
            offset += 1
            total_cycles, offset = u64(data, offset)
            if budget != expected_budget or requested != expected_budget:
                raise ValueError("diagnostic input/result schedule mismatch")
            stats["elapsed_cycles"] += elapsed
            stats["nonzero_guest_values"] += bool(ready)
            stats["nonzero_guest_values"] += bool(total_cycles)
        if offset != len(data):
            raise ValueError("unexpected diagnostic observation bytes")
        return stats

    if profile != "mvs" or count != len(MVS_INPUTS):
        raise ValueError("unsupported MVS observation count")
    pixel_bytes_per_frame = 320 * 224 * 4
    for expected_input in MVS_INPUTS:
        input_mask, offset = u32(data, offset)
        _version, offset = u32(data, offset)
        _requested, offset = u64(data, offset)
        elapsed, offset = u64(data, offset)
        _instructions, offset = u64(data, offset)
        _frame_num, offset = u64(data, offset)
        _frame_den, offset = u64(data, offset)
        _clock_num, offset = u32(data, offset)
        _clock_den, offset = u32(data, offset)
        _reason, offset = u32(data, offset)
        _audio_format, offset = u32(data, offset)
        _sample_rate, offset = u32(data, offset)
        _channels, offset = u32(data, offset)
        generated, offset = u64(data, offset)
        discarded, offset = u64(data, offset)
        delivered, offset = u64(data, offset)
        pixels, offset = u64(data, offset)
        if len(data) - offset < 1:
            raise ValueError("missing guest effect observation")
        guest_reply = data[offset]
        offset += 1
        _total_cycles, offset = u64(data, offset)
        audio_frames, offset = u64(data, offset)
        if input_mask != expected_input or generated != delivered or discarded != 0:
            raise ValueError("MVS input or exact PCM count mismatch")
        if pixels != 320 * 224 or audio_frames != delivered:
            raise ValueError("MVS raw output count mismatch")
        if len(data) - offset < pixel_bytes_per_frame:
            raise ValueError("missing full raw video frame")
        raw_pixels = data[offset : offset + pixel_bytes_per_frame]
        offset += pixel_bytes_per_frame
        sample_bytes = audio_frames * 4
        if len(data) - offset < sample_bytes:
            raise ValueError("missing complete PCM observation")
        raw_audio = data[offset : offset + sample_bytes]
        offset += sample_bytes
        stats["elapsed_cycles"] += elapsed
        stats["video_frames"] += 1
        stats["video_pixels"] += pixels
        stats["video_bytes"] += pixel_bytes_per_frame
        stats["nonzero_video_bytes"] += sum(value != 0 for value in raw_pixels)
        stats["audio_frames"] += audio_frames
        stats["audio_samples"] += audio_frames * 2
        stats["nonzero_audio_samples"] += sum(
            int.from_bytes(raw_audio[index : index + 2], "big", signed=True) != 0
            for index in range(0, len(raw_audio), 2)
        )
        stats["nonzero_guest_values"] += guest_reply != 0
    if offset != len(data):
        raise ValueError("unexpected MVS observation bytes")
    return stats


def child_limits(cpu_seconds: int = MAX_CHILD_CPU_SECONDS) -> None:
    try:
        import resource

        if hasattr(resource, "RLIMIT_CPU"):
            resource.setrlimit(resource.RLIMIT_CPU,
                               (cpu_seconds, cpu_seconds + 1))
    except (ImportError, OSError, ValueError):
        pass


def terminate_child(child: subprocess.Popen[bytes]) -> None:
    if child.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        child.terminate()
    try:
        child.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            child.kill()
        child.wait()


def run_child(command: list[str], *, timeout: float = MAX_CHILD_SECONDS,
              cpu_seconds: int = MAX_CHILD_CPU_SECONDS,
              output_limit: int = MAX_CHILD_OUTPUT_BYTES) -> ChildResult:
    started_ns = time.time_ns()
    output = bytearray()
    overflow = threading.Event()
    read_error: list[BaseException] = []
    try:
        child = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=(os.name == "posix"),
            preexec_fn=(lambda: child_limits(cpu_seconds)) if os.name == "posix" else None,
        )
    except OSError as error:
        finished_ns = time.time_ns()
        return ChildResult(command, 127, started_ns, finished_ns,
                           f"could not start child: {error.__class__.__name__}",
                           None, (finished_ns - started_ns) / 1_000_000_000,
                           0)

    def read_output() -> None:
        assert child.stdout is not None
        try:
            while True:
                chunk = child.stdout.read(4096)
                if not chunk:
                    return
                if len(output) + len(chunk) > output_limit:
                    overflow.set()
                    return
                output.extend(chunk)
        except BaseException as error:  # surfaced by the supervisor below
            read_error.append(error)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    timed_out = False
    while child.poll() is None:
        if overflow.is_set() or time.monotonic() >= deadline:
            timed_out = not overflow.is_set()
            terminate_child(child)
            break
        time.sleep(0.02)
    returncode = child.wait()
    reader.join(timeout=2.0)
    if child.stdout is not None:
        child.stdout.close()
    finished_ns = time.time_ns()
    decoded = output.decode("utf-8", errors="replace")
    if read_error:
        decoded += "\noutput-reader-error=" + read_error[0].__class__.__name__
    return ChildResult(command, returncode, started_ns, finished_ns, decoded,
                       child.pid, (finished_ns - started_ns) / 1_000_000_000,
                       len(output), timed_out, overflow.is_set())


def parse_child_metadata(child: ChildResult) -> dict[str, object]:
    for line in child.output.splitlines():
        if line.startswith("STATE_RESULT "):
            return json.loads(line[len("STATE_RESULT ") :])
    return {}


def fail(assertion: str, report: dict[str, object]) -> None:
    raise ExchangeFailure(assertion, report)


def require(condition: bool, assertion: str, report: dict[str, object]) -> None:
    if not condition:
        fail(assertion, report)


def ensure_trace(path: Path, profile: str, report: dict[str, object]) -> bytes:
    if not path.is_file():
        fail(f"sdk.state.process.{profile}.observation-result-present", report)
    data = path.read_bytes()
    if not data or len(data) > MAX_TRACE_BYTES:
        fail(f"sdk.state.process.{profile}.observation-result-bounded", report)
    try:
        stats = parse_trace(profile, data)
    except (ValueError, struct.error) as error:
        fail(f"sdk.state.process.{profile}.observation-valid:{error}", report)
    report["trace_stats"] = stats
    return data


def check_metadata(profile: str, mode: str, metadata: dict[str, object],
                   child: ChildResult, report: dict[str, object],
                   expected_configuration: str | None = None) -> None:
    require(child.pid is not None and metadata.get("process_id") == child.pid,
            f"sdk.state.process.{profile}.{mode}-process-identity", report)
    require(metadata.get("mode") == mode and metadata.get("profile") == profile,
            f"sdk.state.process.{profile}.{mode}-result-identity", report)
    if expected_configuration is not None:
        require(metadata.get("configuration") == expected_configuration,
                f"sdk.state.exchange.{expected_configuration.lower()}-child-configuration",
                report)
    require(isinstance(metadata.get("assertions"), int) and
            metadata["assertions"] > 0,
            f"sdk.state.process.{profile}.{mode}-nonzero-assertions", report)
    cpu_seconds = metadata.get("cpu_seconds")
    require(isinstance(cpu_seconds, (int, float)) and
            0.0 <= float(cpu_seconds) <= MAX_CHILD_CPU_SECONDS,
            f"sdk.state.process.{profile}.{mode}-bounded-child-cpu", report)
    require(isinstance(metadata.get("observations"), int) and
            metadata["observations"] > 0,
            f"sdk.state.process.{profile}.{mode}-nonzero-observations", report)
    source_revision = metadata.get("source_revision")
    source_content = metadata.get("source_content_sha256")
    require(source_revision not in (None, "", "unknown") and
            source_content == source_identity(),
            f"sdk.state.process.{profile}.{mode}-current-source-identity", report)
    require(metadata.get("sanitizer") == "NONE",
            f"sdk.state.process.{profile}.{mode}-unsanitized-named-evidence", report)
    identity = metadata.get("media_identity_sha256")
    require(isinstance(identity, str) and re.fullmatch(r"[0-9a-f]{64}", identity),
            f"sdk.state.process.{profile}.{mode}-normalized-media-identity", report)
    if profile == "mvs":
        require(metadata.get("profile_id") == 0x4D53584D and
                metadata.get("configuration_id") == 2,
                f"sdk.state.process.mvs.{mode}-profile-config-identity", report)
    else:
        require(metadata.get("profile_id") == 1 and
                metadata.get("configuration_id") == 1,
                f"sdk.state.process.diagnostic.{mode}-profile-config-identity", report)


def run_profile_pair(export_runner: Path, profile: str,
                     import_runner: Path | None = None,
                     pair_name: str | None = None,
                     expected_export_configuration: str | None = None,
                     expected_import_configuration: str | None = None) -> PairReport:
    report = PairReport(profile)
    import_runner = import_runner or export_runner
    summary: dict[str, object] = {"profile": profile, "pair": pair_name or "same-build"}
    try:
        with tempfile.TemporaryDirectory(prefix="glueyneo-state-process-") as temp:
            temp_dir = Path(temp)
            payload = temp_dir / "state.bin"
            expected = temp_dir / "expected.trace"
            actual = temp_dir / "actual.trace"
            exporter = run_child([str(export_runner), "export", profile,
                                  str(payload), str(expected)])
            report.exporter = exporter
            report.export_metadata = parse_child_metadata(exporter)
            summary["exporter_output"] = exporter.output
            summary["exporter_returncode"] = exporter.returncode
            summary["exporter_pid"] = exporter.pid
            summary["exporter_wall_seconds"] = exporter.wall_seconds
            summary["exporter_output_bytes"] = exporter.output_bytes
            require(not exporter.output_overflow and not exporter.timed_out,
                    f"sdk.state.process.{profile}.exporter-bounded", summary)
            require(exporter.wall_seconds <= MAX_CHILD_SECONDS and
                    exporter.output_bytes <= MAX_CHILD_OUTPUT_BYTES,
                    f"sdk.state.process.{profile}.exporter-wall-output-bounds",
                    summary)
            require(exporter.returncode == 0,
                    f"sdk.state.process.{profile}.exporter-completed", summary)
            check_metadata(profile, "export", report.export_metadata,
                           exporter, summary, expected_export_configuration)
            require(payload.is_file() and 0 < payload.stat().st_size <= MAX_PAYLOAD_BYTES,
                    f"sdk.state.process.{profile}.exported-payload-present-bounded",
                    summary)
            expected_bytes = ensure_trace(expected, profile, summary)
            report.expected_sha256 = hashlib.sha256(expected_bytes).hexdigest()
            report.payload_sha256 = hashlib.sha256(payload.read_bytes()).hexdigest()
            source_exit_ns = exporter.finished_ns

            importer = run_child([str(import_runner), "import", profile,
                                  str(payload), str(actual)])
            report.importer = importer
            report.import_metadata = parse_child_metadata(importer)
            summary["importer_output"] = importer.output
            summary["importer_returncode"] = importer.returncode
            summary["importer_pid"] = importer.pid
            summary["importer_wall_seconds"] = importer.wall_seconds
            summary["importer_output_bytes"] = importer.output_bytes
            summary["importer_started_after_exporter_exit"] = (
                importer.started_ns >= source_exit_ns and
                exporter.returncode is not None
            )
            require(importer.started_ns >= source_exit_ns and
                    exporter.returncode is not None,
                    f"sdk.state.process.{profile}.exporter-terminated-before-importer-start",
                    summary)
            require(importer.pid is not None and exporter.pid != importer.pid,
                    f"sdk.state.process.{profile}.fresh-importer-process-id", summary)
            require(not importer.output_overflow and not importer.timed_out,
                    f"sdk.state.process.{profile}.importer-bounded", summary)
            require(importer.wall_seconds <= MAX_CHILD_SECONDS and
                    importer.output_bytes <= MAX_CHILD_OUTPUT_BYTES,
                    f"sdk.state.process.{profile}.importer-wall-output-bounds",
                    summary)
            require(importer.returncode == 0,
                    f"sdk.state.process.{profile}.importer-completed", summary)
            check_metadata(profile, "import", report.import_metadata,
                           importer, summary, expected_import_configuration)
            require(report.export_metadata.get("media_identity_sha256") ==
                    report.import_metadata.get("media_identity_sha256"),
                    f"sdk.state.process.{profile}.independently-loaded-media-match",
                    summary)
            actual_bytes = ensure_trace(actual, profile, summary)
            report.actual_sha256 = hashlib.sha256(actual_bytes).hexdigest()
            require(expected_bytes == actual_bytes,
                    f"sdk.state.process.{profile}.fresh-process-future-observations-exact",
                    summary)
            report.trace_stats = parse_trace(profile, actual_bytes)
            if profile == "mvs":
                require(report.trace_stats["video_frames"] > 0 and
                        report.trace_stats["nonzero_video_bytes"] > 0,
                        "sdk.state.process.mvs.full-nonzero-raw-video", summary)
                require(report.trace_stats["audio_frames"] > 0 and
                        report.trace_stats["nonzero_audio_samples"] > 0,
                        "sdk.state.process.mvs.full-nonzero-exact-pcm", summary)
            else:
                require(report.trace_stats["nonzero_guest_values"] > 0,
                        "sdk.state.process.diagnostic.guest-effects-observed",
                        summary)
            report.passed_assertions = int(report.export_metadata["assertions"]) + \
                int(report.import_metadata["assertions"]) + 10
    except ExchangeFailure as error:
        summary["failed_assertion"] = error.assertion
        summary["exporter_output"] = (report.exporter.output
                                      if report.exporter else "")
        summary["importer_output"] = (report.importer.output
                                      if report.importer else "")
        summary["exporter_returncode"] = (report.exporter.returncode
                                          if report.exporter else None)
        summary["importer_returncode"] = (report.importer.returncode
                                          if report.importer else None)
        summary["exporter_pid"] = report.exporter.pid if report.exporter else None
        summary["importer_pid"] = report.importer.pid if report.importer else None
        summary["expected_sha256"] = report.expected_sha256
        summary["actual_sha256"] = report.actual_sha256
        summary["payload_sha256"] = report.payload_sha256
        save_failure_evidence(summary, f"state-process-{profile}")
        raise
    summary.update({
        "expected_sha256": report.expected_sha256,
        "actual_sha256": report.actual_sha256,
        "payload_sha256": report.payload_sha256,
        "pair": pair_name or "same-build",
        "exporter_source_revision": report.export_metadata.get("source_revision"),
        "importer_source_revision": report.import_metadata.get("source_revision"),
        "exporter_source_content_sha256": report.export_metadata.get("source_content_sha256"),
        "importer_source_content_sha256": report.import_metadata.get("source_content_sha256"),
        "exporter_configuration": report.export_metadata.get("configuration"),
        "importer_configuration": report.import_metadata.get("configuration"),
        "media_identity_sha256": report.export_metadata.get("media_identity_sha256"),
        "profile_id": report.export_metadata.get("profile_id"),
        "configuration_id": report.export_metadata.get("configuration_id"),
        "input_schedule_sha256": future_input_identity(),
        "exporter_cpu_seconds": report.export_metadata.get("cpu_seconds"),
        "importer_cpu_seconds": report.import_metadata.get("cpu_seconds"),
        "exporter_wall_seconds": report.exporter.wall_seconds,
        "importer_wall_seconds": report.importer.wall_seconds,
        "assertions": report.passed_assertions,
        **report.trace_stats,
    })
    summary.pop("exporter_output", None)
    summary.pop("importer_output", None)
    print("STATE_CASE " + json.dumps(summary, sort_keys=True))
    return report


def save_failure_evidence(report: dict[str, object], stem: str) -> None:
    destination = ROOT / "build" / "sdk-debug" / "state-exchange-failures"
    try:
        destination.mkdir(parents=True, exist_ok=True)
        record = dict(report)
        record["temporary_payload_and_observations"] = "cleaned by supervisor"
        path = destination / f"{stem}-{time.time_ns()}.json"
        path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
        print(f"STATE_FAILURE_EVIDENCE {path.relative_to(ROOT).as_posix()}",
              file=sys.stderr)
    except OSError as error:
        print(f"could not preserve failure record: {error.__class__.__name__}",
              file=sys.stderr)


def run_exchange(debug_runner: Path, release_runner: Path) -> int:
    summary: dict[str, object] = {"mode": "exchange"}
    try:
        require(debug_runner.is_file(), "sdk.state.exchange.debug-runner-present", summary)
        require(release_runner.is_file(), "sdk.state.exchange.release-runner-present", summary)
        debug_runner = debug_runner.resolve()
        release_runner = release_runner.resolve()
        require(debug_runner != release_runner,
                "sdk.state.exchange.distinct-debug-release-runners", summary)
        debug_info = build_provenance(debug_runner, "Debug")
        release_info = build_provenance(release_runner, "Release")
        dependencies = dependency_provenance()
        pair_reports: list[PairReport] = []

        # Same-build controls execute first so cross-build results are not
        # confused with a broken single-configuration continuation.
        for runner, config in ((debug_runner, "Debug"), (release_runner, "Release")):
            for profile in PROFILE_CASES:
                pair_reports.append(run_profile_pair(
                    runner, profile, pair_name=f"{config}-same-build",
                    expected_export_configuration=config,
                    expected_import_configuration=config))

        for exporter, importer, export_config, import_config in (
                (debug_runner, release_runner, "Debug", "Release"),
                (release_runner, debug_runner, "Release", "Debug")):
            for profile in PROFILE_CASES:
                pair_reports.append(run_profile_pair(
                    exporter, profile, importer,
                    pair_name=f"{export_config}-to-{import_config}",
                    expected_export_configuration=export_config,
                    expected_import_configuration=import_config))

        records = [{
            "pair": f"{report.export_metadata.get('configuration')}-to-"
                    f"{report.import_metadata.get('configuration')}",
            "profile": report.profile,
            "exporter_source_revision": report.export_metadata.get("source_revision"),
            "importer_source_revision": report.import_metadata.get("source_revision"),
            "exporter_source_content_sha256": report.export_metadata.get(
                "source_content_sha256"),
            "importer_source_content_sha256": report.import_metadata.get(
                "source_content_sha256"),
            "media_identity_sha256": report.export_metadata.get("media_identity_sha256"),
            "profile_id": report.export_metadata.get("profile_id"),
            "configuration_id": report.export_metadata.get("configuration_id"),
            "input_schedule_sha256": future_input_identity(),
            "future_observations_sha256": report.actual_sha256,
            "observations": report.trace_stats,
            "assertions": report.passed_assertions,
            "payload_bytes": report.export_metadata.get("payload_bytes"),
            "exporter_cpu_seconds": report.export_metadata.get("cpu_seconds"),
            "importer_cpu_seconds": report.import_metadata.get("cpu_seconds"),
            "exporter_wall_seconds": report.exporter.wall_seconds,
            "importer_wall_seconds": report.importer.wall_seconds,
        } for report in pair_reports]
        for record in records:
            print("STATE_EXCHANGE_PAIR " + json.dumps(record, sort_keys=True))
        assertion_count = sum(report.passed_assertions for report in pair_reports)
        require(len(pair_reports) == 8 and assertion_count > 0,
                "sdk.state.exchange.nonzero-pairs-and-assertions", summary)
        print("STATE_EXCHANGE_RESULT " + json.dumps({
            "schema_version": 1,
            "mode": "exchange",
            "outcome": "pass",
            "pair_cases": len(pair_reports),
            "assertions": assertion_count,
            "source_revision": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                text=True, timeout=10, check=True).stdout.strip(),
            "source_content_sha256": source_identity(),
            "input_schedule_sha256": future_input_identity(),
            "platform": debug_info["platform"],
            "debug": debug_info,
            "release": release_info,
            "dependencies": dependencies,
            "pairs": records,
        }, sort_keys=True))
        return 0
    except ExchangeFailure as error:
        summary["failed_assertion"] = error.assertion
        save_failure_evidence(summary, "state-exchange")
        print(f"ASSERTION FAILED {error.assertion}", file=sys.stderr)
        return 1


def parse_local_metadata(child: ChildResult) -> dict[str, object]:
    for line in child.output.splitlines():
        if line.startswith("STATE_LOCAL_RESULT "):
            try:
                value = json.loads(line[len("STATE_LOCAL_RESULT "):])
            except json.JSONDecodeError:
                return {}
            return value if isinstance(value, dict) else {}
    return {}


def local_child_assertion(child: ChildResult) -> str | None:
    for line in child.output.splitlines():
        match = re.match(r"STATE_ASSERT (sdk\.state\.local\.[A-Za-z0-9_.-]+) ", line)
        if match is not None:
            return match.group(1)
    return None


def bounded_file_bytes(path: Path, maximum: int, assertion: str,
                       report: dict[str, object]) -> bytes:
    if not path.is_file():
        fail(assertion + ".present", report)
    size = path.stat().st_size
    if size <= 0 or size > maximum:
        fail(assertion + ".bounded", report)
    return path.read_bytes()


def run_local_state(runner: Path, bundle: Path, schedule: Path,
                    output_dir: Path) -> int:
    report: dict[str, object] = {"mode": "local"}
    try:
        require(runner.is_file() and bundle.is_file() and schedule.is_file() and
                output_dir.is_dir(), "sdk.state.local.inputs-present", report)
        runner = runner.resolve()
        bundle = bundle.resolve()
        schedule = schedule.resolve()
        output_dir = output_dir.resolve()
        state = output_dir / "continuation.bin"
        witness = output_dir / "uninterrupted.trace"
        saved_sram = output_dir / "historical-sram.bin"
        resumed = output_dir / "resumed.trace"
        local_paths = (state, witness, saved_sram, resumed)
        require(not any(path.exists() or path.is_symlink() for path in local_paths),
                "sdk.state.local.output-names-unused", report)
        source_revision = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        source_content = source_identity()
        exporter = run_child(
            [str(runner), "local-export", str(bundle), str(schedule),
             str(state), str(witness), str(saved_sram)],
            timeout=MAX_LOCAL_CHILD_SECONDS,
            cpu_seconds=MAX_LOCAL_CHILD_CPU_SECONDS)
        export_metadata = parse_local_metadata(exporter)
        if exporter.returncode != 0:
            child_assertion = local_child_assertion(exporter)
            if child_assertion is not None:
                report["child_assertion"] = child_assertion
        require(not exporter.output_overflow and not exporter.timed_out and
                exporter.returncode == 0,
                "sdk.state.local.exporter-completed-within-bounds", report)
        require(exporter.pid is not None and exporter.wall_seconds <=
                MAX_LOCAL_CHILD_SECONDS and exporter.output_bytes <=
                MAX_CHILD_OUTPUT_BYTES,
                "sdk.state.local.exporter-process-bounds", report)
        require(export_metadata.get("mode") == "local-export" and
                export_metadata.get("outcome") == "pass" and
                isinstance(export_metadata.get("assertions"), int) and
                export_metadata.get("assertions", 0) > 0 and
                export_metadata.get("source_revision") == source_revision and
                export_metadata.get("source_content_sha256") == source_content and
                export_metadata.get("configuration") == "Debug" and
                export_metadata.get("sanitizer") == "NONE",
                "sdk.state.local.exporter-source-configuration-evidence", report)
        state_bytes = bounded_file_bytes(
            state, MAX_PAYLOAD_BYTES, "sdk.state.local.state", report)
        sram_bytes = bounded_file_bytes(
            saved_sram, 0x10000, "sdk.state.local.historical-sram", report)
        witness_bytes = bounded_file_bytes(
            witness, MAX_LOCAL_TRACE_BYTES, "sdk.state.local.witness", report)
        require(len(sram_bytes) == 0x10000 and
                len(witness_bytes) >= 16,
                "sdk.state.local.private-artifacts-have-exact-bounds", report)
        future_frames = export_metadata.get("future_frames")
        require(isinstance(future_frames, int) and
                1 <= future_frames <= MAX_LOCAL_FUTURE_FRAMES and
                export_metadata.get("state_bytes") == len(state_bytes) and
                export_metadata.get("elapsed_cycles", 0) > 0 and
                export_metadata.get("nonzero_audio_samples", 0) > 0 and
                export_metadata.get("nonzero_video_bytes", 0) > 0,
                "sdk.state.local.exporter-observations-nonzero", report)

        importer = run_child(
            [str(runner), "local-import", str(bundle), str(schedule),
             str(state), str(saved_sram), str(resumed)],
            timeout=MAX_LOCAL_CHILD_SECONDS,
            cpu_seconds=MAX_LOCAL_CHILD_CPU_SECONDS)
        import_metadata = parse_local_metadata(importer)
        if importer.returncode != 0:
            child_assertion = local_child_assertion(importer)
            if child_assertion is not None:
                report["child_assertion"] = child_assertion
        require(importer.started_ns >= exporter.finished_ns and
                importer.returncode == 0 and not importer.output_overflow and
                not importer.timed_out,
                "sdk.state.local.importer-starts-after-exporter-termination", report)
        require(importer.pid is not None and importer.pid != exporter.pid and
                importer.wall_seconds <= MAX_LOCAL_CHILD_SECONDS and
                importer.output_bytes <= MAX_CHILD_OUTPUT_BYTES,
                "sdk.state.local.independent-importer-process-bounds", report)
        require(import_metadata.get("mode") == "local-import" and
                import_metadata.get("outcome") == "pass" and
                isinstance(import_metadata.get("assertions"), int) and
                import_metadata.get("assertions", 0) > 0 and
                import_metadata.get("source_revision") == source_revision and
                import_metadata.get("source_content_sha256") == source_content and
                import_metadata.get("configuration") == "Debug" and
                import_metadata.get("sanitizer") == "NONE" and
                import_metadata.get("future_frames") == future_frames and
                import_metadata.get("state_bytes") == len(state_bytes),
                "sdk.state.local.importer-source-configuration-evidence", report)
        resumed_bytes = bounded_file_bytes(
            resumed, MAX_LOCAL_TRACE_BYTES, "sdk.state.local.resumed", report)
        require(witness_bytes == resumed_bytes,
                "sdk.state.local.full-raw-future-video-pcm-guest-time-equal", report)
        assertion_count = (int(export_metadata["assertions"]) +
                           int(import_metadata["assertions"]) + 11)
        print("STATE_LOCAL_RESULT " + json.dumps({
            "schema_version": 1,
            "outcome": "pass",
            "cases": 1,
            "assertions": assertion_count,
            "source_revision": source_revision,
            "source_content_sha256": source_content,
            "configuration": "Debug",
            "future_frames": future_frames,
            "state_bytes": len(state_bytes),
            "trace_bytes": len(witness_bytes),
            "independent_processes": True,
            "historical_sram_restored": True,
            "invalid_import_atomic": True,
            "full_trace_equal": True,
        }, sort_keys=True))
        return 0
    except ExchangeFailure as error:
        print(f"ASSERTION FAILED {error.assertion}", file=sys.stderr)
        child_assertion = error.report.get("child_assertion")
        if isinstance(child_assertion, str):
            print(f"LOCAL CHILD ASSERTION {child_assertion}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        print("ASSERTION FAILED sdk.state.local.private-runner-error",
              file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-identity", action="store_true")
    parser.add_argument("--mode", choices=("process", "exchange", "local"),
                        default="process")
    parser.add_argument("--runner", type=Path)
    parser.add_argument("--debug-runner", type=Path)
    parser.add_argument("--release-runner", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--schedule", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.source_identity:
        print(source_identity())
        return 0
    if args.mode == "exchange":
        if args.debug_runner is None or args.release_runner is None:
            print("ASSERTION FAILED sdk.state.exchange.runners-present", file=sys.stderr)
            return 2
        return run_exchange(args.debug_runner, args.release_runner)
    if args.mode == "local":
        if (args.runner is None or args.bundle is None or args.schedule is None or
                args.output_dir is None):
            print("ASSERTION FAILED sdk.state.local.arguments-present",
                  file=sys.stderr)
            return 2
        return run_local_state(args.runner, args.bundle, args.schedule,
                               args.output_dir)
    if args.runner is None or not args.runner.is_file():
        print("ASSERTION FAILED sdk.state.process.runner-present", file=sys.stderr)
        return 2
    runner = args.runner.resolve()
    try:
        reports = [run_profile_pair(runner, profile) for profile in PROFILE_CASES]
    except ExchangeFailure as error:
        print(f"ASSERTION FAILED {error.assertion}", file=sys.stderr)
        return 1
    assertion_count = sum(item.passed_assertions for item in reports)
    case_count = len(reports)
    if case_count == 0 or assertion_count == 0:
        print("ASSERTION FAILED sdk.state.process.nonzero-cases-and-assertions",
              file=sys.stderr)
        return 1
    print("STATE_EXCHANGE_RESULT " + json.dumps({
        "schema_version": 1,
        "mode": "process",
        "outcome": "pass",
        "cases": case_count,
        "assertions": assertion_count,
        "source_content_sha256": source_identity(),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
