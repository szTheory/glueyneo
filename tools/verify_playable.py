#!/usr/bin/env python3
"""Clean-build and qualify the public playable tracer on the selected host.

The receipt and command logs are generated under ignored build/ and contain no
private content. An unavailable frontend or candidate gate remains unknown and
fails the aggregate result; mocks never count as evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "playable-qualification"
FIXTURE_SHA256 = "59ed3645b156db15e20599ab71f40d416f870472078e8f6751d2174afe7a5cf0"
YMFM_REVISION = "81aec25ccbb98f4873a255f7551ac4dadac59b4a"
Z80_REVISION = "9e88298ce56319953ac7a43213a1120359f7a3a6"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_revision() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def redact(text: str) -> str:
    text = text.replace(str(ROOT), "[repo]").replace(str(Path.home()), "[home]")
    text = re.sub(r"/(?:private/var/folders|private/tmp|tmp)/[^\s:'\"]+", "[temporary-path]", text)
    return text


class Runner:
    def __init__(self, work: Path) -> None:
        self.work = work
        self.lanes: dict[str, dict[str, object]] = {}

    def command(self, name: str, argv: list[str], *, cwd: Path = ROOT,
                timeout: int = 600, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
        started = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=cwd, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    check=False, timeout=timeout)
            output = result.stdout
            code = result.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            output = f"{type(error).__name__}: {error}"
            code = -1
        elapsed = round(time.monotonic() - started, 3)
        safe_output = redact(output)
        (self.work / f"{name}.log").write_text(safe_output, encoding="utf-8")
        status = "pass" if code == 0 else "fail"
        self.lanes[name] = {
            "status": status, "command": [redact(part) for part in [Path(argv[0]).name, *argv[1:]]],
            "exit_code": code, "seconds": elapsed,
            "log_sha256": sha256(self.work / f"{name}.log"),
        }
        if code != 0 and not allow_failure:
            raise RuntimeError(f"{name} failed; see ignored build/playable-qualification logs")
        return subprocess.CompletedProcess(argv, code, output)


def cache_identity(cache: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in cache.read_text(encoding="utf-8").splitlines():
        if line.startswith("//") or not line or ":" not in line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.split(":", 1)[0]] = value
    identity = {key: values.get(key, "unknown") for key in (
        "CMAKE_C_COMPILER_ID", "CMAKE_C_COMPILER_VERSION", "CMAKE_CXX_COMPILER_ID",
        "CMAKE_CXX_COMPILER_VERSION", "CMAKE_GENERATOR", "CMAKE_BUILD_TYPE",
        "CMAKE_OSX_SYSROOT", "CMAKE_OSX_DEPLOYMENT_TARGET",
    )}
    for language in ("C", "CXX"):
        files = sorted(cache.parent.glob(f"CMakeFiles/*/CMake{language}Compiler.cmake"))
        if files:
            text = files[0].read_text(encoding="utf-8")
            for key in ("ID", "VERSION"):
                match = re.search(rf'set\(CMAKE_{language}_COMPILER_{key} "([^"]*)"\)', text)
                if match:
                    identity[f"CMAKE_{language}_COMPILER_{key}"] = match.group(1)
    return identity


def run_consumer(runner: Runner, prefix: Path, fixture: Path, core: Path,
                 variant: str) -> None:
    consumer_source = ROOT / "tests" / "consumers"
    consumer_build = runner.work / f"consumer-{variant}"
    runner.command(f"consumer-{variant}-configure", [
        "cmake", "-S", str(consumer_source), "-B", str(consumer_build),
        f"-DGlueyneo_DIR={prefix / 'lib/cmake/Glueyneo'}",
        f"-DGLUEYNEO_CONSUMER_C_SOURCE={ROOT / 'examples/diagnostic.c'}",
        "-DCMAKE_BUILD_TYPE=Release",
    ])
    runner.command(f"consumer-{variant}-build", ["cmake", "--build", str(consumer_build), "--parallel", "2"])
    consumer = consumer_build / "glueyneo-installed-c"
    runner.command(f"consumer-{variant}-check", [
        sys.executable, str(ROOT / "tests/consumers/test_playable_install.py"),
        "--prefix", str(prefix), "--consumer", str(consumer), "--fixture", str(fixture),
        "--core", str(core),
    ])


def frontend_identity(bundle: Path) -> dict[str, str]:
    plist_path = bundle / "Contents/Info.plist"
    if not plist_path.is_file():
        return {"status": "unknown", "reason": "RetroArch bundle or Info.plist missing"}
    try:
        with plist_path.open("rb") as stream:
            info = plistlib.load(stream)
        executable = bundle / "Contents/MacOS" / str(info.get("CFBundleExecutable", ""))
        return {
            "status": "identified" if executable.is_file() else "unknown",
            "version": str(info.get("CFBundleShortVersionString", "unknown")),
            "bundle_id": str(info.get("CFBundleIdentifier", "unknown")),
            "executable_sha256": sha256(executable) if executable.is_file() else "unknown",
        }
    except (OSError, plistlib.InvalidFileException):
        return {"status": "unknown", "reason": "RetroArch identity could not be read"}


def check_docs() -> None:
    guide = (ROOT / "docs/first-playable-build.md").read_text(encoding="utf-8")
    validation = (ROOT / ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer/04-VALIDATION.md").read_text(encoding="utf-8")
    required = (
        "python3 tools/verify_playable.py --retroarch /Applications/RetroArch.app --clean",
        "public-playable.bin", "RetroArch", "macOS", "unsupported", "unknown",
        YMFM_REVISION, Z80_REVISION,
    )
    missing = [term for term in required if term not in guide]
    if missing:
        raise RuntimeError(f"integrator documentation omits: {', '.join(missing)}")
    if re.search(r"\b(TBD|pending|planned)\b", validation, re.IGNORECASE):
        raise RuntimeError("validation map still contains TBD/pending/planned status")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retroarch", type=Path, required=True)
    parser.add_argument("--clean", action="store_true", help="use fresh build and install directories")
    parser.add_argument("--check-docs", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.mkdtemp(prefix="clean-", dir=OUTPUT)
    work = Path(temporary)
    runner = Runner(work)
    identity: dict[str, object] = {
        "source_revision": source_revision(),
        "source_files": {path: sha256(ROOT / path) for path in (
            "CMakeLists.txt", "tools/verify_playable.py", "tests/consumers/test_playable_install.py",
            "tests/fixture/public_guest.c", "tests/fixture/test_public_guest.c",
            "tests/libretro/retroarch_smoke.py", "tests/chips/test_z80.c", "tests/chips/test_ym2610.c",
        )},
        "os": platform.platform(), "architecture": platform.machine(),
        "python": platform.python_version(),
        "cmake": subprocess.run(["cmake", "--version"], text=True,
                                 stdout=subprocess.PIPE, check=False).stdout.splitlines()[0],
        "ninja": subprocess.run(["ninja", "--version"], text=True,
                                 stdout=subprocess.PIPE, check=False).stdout.strip(),
        "retroarch": frontend_identity(args.retroarch.resolve()),
        "fixture_sha256_expected": FIXTURE_SHA256,
        "ymfm_candidate_revision": YMFM_REVISION,
        "z80_candidate_revision": Z80_REVISION,
    }
    if sys.platform == "darwin":
        sdk = subprocess.run(["xcrun", "--show-sdk-version"], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        identity["macos_sdk"] = sdk.stdout.strip() if sdk.returncode == 0 else "unknown"
    else:
        identity["macos_sdk"] = "unsupported on this host"

    status = "pass"
    reason = ""
    fixture = Path()
    shared_core = Path()
    shared_cache = Path()
    try:
        if not args.clean:
            raise RuntimeError("--clean is required for qualification")
        build_roots: dict[str, Path] = {}
        prefixes: dict[str, Path] = {}
        for variant, shared in (("static", "OFF"), ("shared", "ON")):
            build = work / f"{variant}-build"
            prefix = work / f"{variant}-install"
            build_roots[variant] = build
            prefixes[variant] = prefix
            runner.command(f"{variant}-configure", [
                "cmake", "-S", str(ROOT), "-B", str(build), "-G", "Ninja",
                "-DCMAKE_BUILD_TYPE=Debug", f"-DCMAKE_INSTALL_PREFIX={prefix}",
                f"-DBUILD_SHARED_LIBS={shared}",
                "-DBUILD_TESTING=ON", "-DGLUEYNEO_BUILD_TESTS=ON",
                "-DGLUEYNEO_CPU_EXPERIMENT=OFF", "-DGLUEYNEO_OWNED_CPU_EXPERIMENT=OFF",
            ])
            runner.command(f"{variant}-build", ["cmake", "--build", str(build), "--parallel", "2"], timeout=1200)
            runner.command(f"{variant}-install", ["cmake", "--install", str(build)])
            candidate = build / "public-playable.bin"
            if not candidate.is_file() or sha256(candidate) != FIXTURE_SHA256:
                raise RuntimeError(f"{variant} generated fixture identity mismatch")
            if variant == "shared":
                fixture = candidate
                shared_core = prefix / "lib/libretro/glueyneo_libretro.dylib"
                shared_cache = build / "CMakeCache.txt"
            else:
                fixture = candidate
            run_consumer(runner, prefix, build / "diagnostic-original-a.bin",
                         prefix / "lib/libretro/glueyneo_libretro.dylib", variant)

        identity["build"] = cache_identity(shared_cache)
        runner.command("full-sdk-ctest", [
            "ctest", "--test-dir", str(build_roots["shared"]), "--verbose",
            "--output-on-failure", "--no-tests=error", "--parallel", "2",
        ], timeout=1200)
        runner.command("z80-source", [sys.executable, str(ROOT / "tests/chips/check_z80_source.py")])
        runner.command("ym2610-source", [sys.executable, str(ROOT / "tests/chips/check_ym2610.py"), "source"])
        runner.command("ym2610-installed-linkages", [
            sys.executable, str(ROOT / "tests/chips/check_ym2610.py"), "link",
            "--both-linkages", "--report", str(ROOT / "build/ym2610-admission/ym2610-admission.json"),
        ], timeout=1200)
    except (RuntimeError, OSError) as error:
        status, reason = "fail", str(error)

    receipt: dict[str, object] = {
        "schema": "glueyneo.playable-qualification/v1",
        "status": status,
        "identity": identity,
        "lanes": runner.lanes,
        "fixture": {"status": "pass" if fixture.is_file() and sha256(fixture) == FIXTURE_SHA256 else "unknown",
                    "sha256": sha256(fixture) if fixture.is_file() else "unknown"},
        "retroarch_smoke": {"status": "unknown", "reason": "not run"},
        "ym2610_candidate_report": {"path": "build/ym2610-admission/ym2610-admission.json",
                                     "sha256": "unknown", "status": "unknown"},
        "unsupported_configurations": ["non-macOS", "architectures other than this host", "unlisted compilers and SDKs"],
    }
    if runner.lanes.get("ym2610-installed-linkages", {}).get("status") == "pass":
        report_path = ROOT / "build/ym2610-admission/ym2610-admission.json"
        if report_path.is_file():
            receipt["ym2610_candidate_report"] = {
                "path": "build/ym2610-admission/ym2610-admission.json",
                "sha256": sha256(report_path), "status": "candidate-only; gates pass",
            }
    if shared_core.is_file() and fixture.is_file():
        smoke = runner.command("actual-retroarch-smoke", [
            sys.executable, str(ROOT / "tests/libretro/retroarch_smoke.py"),
            "--retroarch", str(args.retroarch.resolve()), "--core", str(shared_core),
            "--content", str(fixture),
        ], timeout=180, allow_failure=True)
        try:
            smoke_data = json.loads(smoke.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            smoke_data = {"status": "unknown", "reason": "smoke omitted a machine-readable result"}
        if smoke.returncode == 0 and smoke_data.get("status") == "pass":
            receipt["retroarch_smoke"] = smoke_data
        else:
            receipt["retroarch_smoke"] = {**smoke_data, "status": "unknown"}
            status = "fail"
            reason = "actual pinned RetroArch load/input/video/unload gate is unknown or failed"
    else:
        receipt["retroarch_smoke"] = {"status": "unknown", "reason": "clean installed core or fixture unavailable"}
        status = "fail"
        reason = reason or "actual RetroArch lane could not run"
    if args.check_docs:
        try:
            check_docs()
            receipt["documentation"] = {"status": "pass"}
        except RuntimeError as error:
            receipt["documentation"] = {"status": "fail", "reason": str(error)}
            status = "fail"
            reason = reason or str(error)
    receipt["status"] = status
    receipt["reason"] = reason
    receipt_path = OUTPUT / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "receipt": "build/playable-qualification/receipt.json",
                      "fixture_sha256": receipt["fixture"]["sha256"],
                      "retroarch_status": receipt["retroarch_smoke"]["status"],
                      "reason": reason}, sort_keys=True))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
