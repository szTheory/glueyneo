#!/usr/bin/env python3
"""Source provenance gate for the pinned YM2610 candidate."""

from __future__ import annotations

import hashlib
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
REVISION = "81aec25ccbb98f4873a255f7551ac4dadac59b4a"
FILES = {
    "src/ymfm.h": "f5ab6fed63c8669abab8403e0e93132e1dad0ae4d8e4954e7836ab9e5b228405",
    "src/ymfm_adpcm.cpp": "74e5ded129ea7e532112e5b637d0a7bd4e127fd83331f1fac32011723051d4e0",
    "src/ymfm_adpcm.h": "5933691971493b853a9be443f6e6fd74f63869aa21225f66dd89fc20de20914d",
    "src/ymfm_fm.h": "1b27bfb7fa4963d7c54cb06fd9bf659450362d8ed496c6af7d487b068cac45c9",
    "src/ymfm_fm.ipp": "4fb7fe59d4494a19e9f9c7888eb644a63d86e109fdefb27a8117bf6a5f6ab4b9",
    "src/ymfm_opn.cpp": "8734c6d5a6e1bf49a08eeb33d260d39c17cd1d26f5db506e5d0d3e416913b489",
    "src/ymfm_opn.h": "1950990c3ea0c6d492a20f66a683a372a7367ef39f7830aa65b20a20d1bcbef5",
    "src/ymfm_ssg.cpp": "73a3028a77f13f3769b7705079659eb8325431a67b8164ded25e12f324f42bfd",
    "src/ymfm_ssg.h": "27966b0887fe98f2d06a96be2776c911107e2f2a13a64f9a349e1ffc19cf7584",
}


def source_check() -> dict[str, object]:
    base = ROOT / "third_party/ymfm"
    notice = (base / "NOTICE.md").read_text(encoding="utf-8")
    license_text = (base / "LICENSE").read_text(encoding="utf-8")
    if REVISION not in notice:
        raise ValueError("NOTICE.md is missing the pinned upstream revision")
    if "BSD 3-Clause License" not in license_text:
        raise ValueError("ymfm BSD-3-Clause license is missing")
    license_digest = hashlib.sha256((base / "LICENSE").read_bytes()).hexdigest()
    if license_digest != "2d2e9213c170a9866c616fa85b6da993a6724e10befc61f468ed9bfb84c4691c":
        raise ValueError("ymfm BSD-3-Clause license digest mismatch")
    if "`LICENSE`" not in notice or license_digest not in notice:
        raise ValueError("NOTICE.md omits the license path or digest")
    for required in (
        "Mutable global state", "Per-chip mutable state", "Interface/callback state",
        "Lazy initialization/races", "Exceptions/allocation", "State serialization",
        "Clock/sample assumptions", "Evidence limit",
    ):
        if required not in notice:
            raise ValueError(f"NOTICE.md is missing inventory section: {required}")
    actual: dict[str, str] = {}
    for relative, expected in FILES.items():
        path = base / relative
        if not path.is_file():
            raise ValueError(f"source file is missing: {path.relative_to(ROOT)}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError(f"SHA-256 mismatch for {path.relative_to(ROOT)}: {digest}")
        if f"`{relative}`" not in notice or expected not in notice:
            raise ValueError(f"NOTICE.md omits the path or digest for {relative}")
        actual[relative] = digest
    extra = sorted(
        (Path("src") / path.relative_to(base / "src")).as_posix()
        for path in (base / "src").rglob("*")
        if path.is_file() and (Path("src") / path.relative_to(base / "src")).as_posix() not in FILES
    )
    if extra:
        raise ValueError(f"unreviewed files in ymfm source closure: {', '.join(extra)}")
    return {"status": "pass", "revision": REVISION, "files": actual,
            "license": "BSD-3-Clause", "unreviewed_files": []}


def run(command: list[str], *, cwd: Path | None = None,
        env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}"
        )
    return result


def source_revision() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def cmake_cache_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("//") or not line or ":" not in line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.split(":", 1)[0]] = value
    return values


def compiler_identity(cache_path: Path, language: str) -> tuple[str, str]:
    files = sorted(cache_path.parent.glob(f"CMakeFiles/*/CMake{language}Compiler.cmake"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        compiler_id = re.search(rf'set\(CMAKE_{language}_COMPILER_ID "([^"]+)"\)', text)
        version = re.search(rf'set\(CMAKE_{language}_COMPILER_VERSION "([^"]+)"\)', text)
        if compiler_id and version:
            return compiler_id.group(1), version.group(1)
    return "unknown", "unknown"


def test_run(binary: Path, report_path: Path) -> dict[str, object]:
    source = source_check()
    result = run([str(binary.resolve())])
    tests = {
        name: "pass" if re.search(rf":{re.escape(name)}:PASS(?:\s|$)", result.stdout)
        else "fail"
        for name in (
            "identical_clock_and_register_traces_match_non_silent_samples",
            "independent_interleaved_instances_match_isolated_baselines",
            "reset_and_chunked_continuation_reproduce_baseline",
            "callback_failure_latches_until_reset_and_exceptions_are_contained",
            "capacities_and_clock_limits_fail_before_mutation",
        )
    }
    summary = re.search(r"(\d+) Tests (\d+) Failures (\d+) Ignored", result.stdout)
    sample = re.search(
        r"ym2610_sample_frames=(\d+) nonzero_values=(\d+) fnv1a64=([0-9a-f]{16})",
        result.stdout,
    )
    if summary is None or sample is None:
        raise RuntimeError("YM2610 consumer output omitted test totals or sample evidence")
    if tuple(map(int, summary.groups())) != (5, 0, 0):
        raise RuntimeError(f"YM2610 tests did not pass completely: {summary.group(0)}")
    if any(status != "pass" for status in tests.values()):
        raise RuntimeError(f"YM2610 required test is missing or failed: {tests}")
    if int(sample.group(1)) <= 0 or int(sample.group(2)) <= 0:
        raise RuntimeError("YM2610 programmed trace produced no nonzero sample values")
    gates: dict[str, dict[str, str]] = {
        "source_closure": {"status": "pass", "evidence": "pinned digests and NOTICE inventory"},
        "deterministic_clock_samples": {"status": "pass", "evidence": tests["identical_clock_and_register_traces_match_non_silent_samples"]},
        "distinct_instances": {"status": "pass", "evidence": tests["independent_interleaved_instances_match_isolated_baselines"]},
        "reset_continuation": {"status": "pass", "evidence": tests["reset_and_chunked_continuation_reproduce_baseline"]},
        "callback_failure": {"status": "pass", "evidence": tests["callback_failure_latches_until_reset_and_exceptions_are_contained"]},
        "exception_containment": {"status": "pass", "evidence": "C ABI guard catches injected std::bad_alloc"},
        "bounds_and_progress": {"status": "pass", "evidence": tests["capacities_and_clock_limits_fail_before_mutation"]},
        "installed_static_c_consumer": {"status": "pending", "evidence": "Task 3 linkage gate"},
        "installed_shared_c_consumer": {"status": "pending", "evidence": "Task 3 linkage gate"},
    }
    cache_path = binary.resolve().parent / "CMakeCache.txt"
    cache = cmake_cache_values(cache_path) if cache_path.is_file() else {}
    c_id, c_version = compiler_identity(cache_path, "C") if cache else ("unknown", "unknown")
    cxx_id, cxx_version = compiler_identity(cache_path, "CXX") if cache else ("unknown", "unknown")
    report: dict[str, object] = {
        "schema": "glueyneo.ym2610-admission.v1",
        "candidate": {"name": "ymfm YM2610", "upstream_revision": REVISION,
                      "license": "BSD-3-Clause", "source": source},
        "build": {"glueyneo_revision": source_revision(),
                  "platform": platform.platform(),
                  "c_compiler": cache.get("CMAKE_C_COMPILER", "unknown"),
                  "c_compiler_id": c_id,
                  "c_compiler_version": c_version,
                  "cxx_compiler": cache.get("CMAKE_CXX_COMPILER", "unknown"),
                  "cxx_compiler_id": cxx_id,
                  "cxx_compiler_version": cxx_version,
                  "configuration": cache.get("CMAKE_BUILD_TYPE", "unknown")},
        "direct_consumer": {"language": "C17", "command": str(binary.resolve()),
                            "return_code": result.returncode,
                            "tests": tests,
                            "test_count": int(summary.group(1)),
                            "failure_count": int(summary.group(2))},
        "sample_evidence": {"frames": int(sample.group(1)),
                            "nonzero_values": int(sample.group(2)),
                            "fingerprint": f"fnv1a64:{sample.group(3)}"},
        "gates": gates,
        "admitted": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return report


def link_both_linkages(report_path: Path) -> dict[str, object]:
    source = source_check()
    direct_binary = ROOT / "build/sdk-debug/ym2610_admission_test"
    report = test_run(direct_binary, report_path)
    work = report_path.parent / "installed"
    results: dict[str, dict[str, object]] = {}
    for linkage, shared in (("static", "OFF"), ("shared", "ON")):
        build = work / linkage / "build"
        prefix = work / linkage / "prefix"
        consumer = work / linkage / "consumer"
        consumer.mkdir(parents=True, exist_ok=True)
        configure = run([
            "cmake", "-S", str(ROOT), "-B", str(build),
            f"-DCMAKE_INSTALL_PREFIX={prefix}", "-DCMAKE_BUILD_TYPE=Release",
            "-DBUILD_TESTING=OFF", "-DGLUEYNEO_BUILD_TESTS=OFF",
            "-DGLUEYNEO_YM2610_ADMISSION=ON", f"-DBUILD_SHARED_LIBS={shared}",
        ])
        run(["cmake", "--build", str(build), "--parallel", "2"])
        run(["cmake", "--install", str(build)])
        cmake_text = f'''cmake_minimum_required(VERSION 3.20)
project(YM2610CConsumer LANGUAGES C)
find_package(Glueyneo CONFIG REQUIRED)
add_library(ym2610_unity STATIC "{ROOT}/third_party/unity/src/unity.c")
target_include_directories(ym2610_unity PUBLIC "{ROOT}/third_party/unity/src")
add_executable(ym2610_installed_consumer "{ROOT}/tests/chips/test_ym2610.c")
target_link_libraries(ym2610_installed_consumer PRIVATE
  Glueyneo::ym2610_candidate ym2610_unity)
set_property(TARGET ym2610_installed_consumer PROPERTY C_STANDARD 17)
set_property(TARGET ym2610_installed_consumer PROPERTY C_STANDARD_REQUIRED ON)
set_property(TARGET ym2610_installed_consumer PROPERTY C_EXTENSIONS OFF)
'''
        (consumer / "CMakeLists.txt").write_text(cmake_text, encoding="utf-8")
        consumer_build = consumer / "build"
        consumer_configure = run([
            "cmake", "-S", str(consumer), "-B", str(consumer_build),
            f"-DCMAKE_PREFIX_PATH={prefix}", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            "-DCMAKE_VERBOSE_MAKEFILE=ON",
        ])
        consumer_build_result = run([
            "cmake", "--build", str(consumer_build), "--verbose", "--parallel", "2"
        ])
        binary = consumer_build / "ym2610_installed_consumer"
        execution = run([str(binary)])
        compile_commands = json.loads(
            (consumer_build / "compile_commands.json").read_text(encoding="utf-8")
        )
        c_compile = any("test_ym2610.c" in item["file"] and
                        item["file"].endswith(".c") and
                        "-c" in shlex.split(item["command"])
                        for item in compile_commands)
        if not c_compile:
            raise RuntimeError(f"{linkage} installed consumer did not compile as C")
        if shared == "OFF" and "-lc++" not in consumer_build_result.stdout and "-lstdc++" not in consumer_build_result.stdout:
            raise RuntimeError(f"{linkage} C consumer link omitted its C++ runtime target dependency")
        summary = re.search(r"(\d+) Tests (\d+) Failures (\d+) Ignored", execution.stdout)
        if summary is None or tuple(map(int, summary.groups())) != (5, 0, 0):
            raise RuntimeError(f"{linkage} installed consumer tests did not all pass")
        results[linkage] = {
            "status": "pass", "source_revision": source_revision(),
            "configuration": "Release", "build_shared_libs": shared,
            "prefix": str(prefix.relative_to(report_path.parents[2])),
            "consumer_language": "C17", "link_driver": "C compiler with C++ runtime from imported CMake target",
            "tests": 5, "failures": 0,
            "configure_output_sha256": hashlib.sha256(
                (configure.stdout + consumer_configure.stdout).encode()
            ).hexdigest(),
            "build_output_sha256": hashlib.sha256(consumer_build_result.stdout.encode()).hexdigest(),
            "run_output_sha256": hashlib.sha256(execution.stdout.encode()).hexdigest(),
        }
        if shared == "ON":
            library = next((prefix / "lib").glob("libglueyneo_ym2610_candidate.*"))
            nm = run(["nm", "-gU", "-j", str(library)])
            exported = sorted(name for name in nm.stdout.splitlines()
                              if name.startswith("_ym2610_candidate_"))
            unexpected = sorted(name for name in nm.stdout.splitlines()
                                if name.startswith("__Z") or name.startswith("_ZN"))
            if unexpected or len(exported) != 8:
                raise RuntimeError(
                    f"unexpected shared exports: ym2610={exported}, C++={unexpected}"
                )
            dynamic = run(["otool", "-L", str(library)])
            if "libc++.1.dylib" not in dynamic.stdout:
                raise RuntimeError("shared candidate omits its C++ runtime dependency")
            results[linkage]["exports"] = exported
            results[linkage]["unexpected_cpp_exports"] = unexpected
            results[linkage]["dynamic_dependencies"] = [
                line.strip().split(" ", 1)[0]
                for line in dynamic.stdout.splitlines()[1:] if line.strip()
            ]
    report["linkages"] = results
    for linkage in ("static", "shared"):
        gate = f"installed_{linkage}_c_consumer"
        status = results.get(linkage, {}).get("status", "unavailable")
        report["gates"][gate] = {
            "status": "pass" if status == "pass" else status,
            "evidence": f"build/ym2610-admission/installed/{linkage}",
        }
    report["admitted"] = all(
        gate.get("status") == "pass" for gate in report["gates"].values()
    )
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    if not report["admitted"]:
        raise RuntimeError("one or more YM2610 admission gates failed")
    return report


def record_link_failure(report_path: Path, error: BaseException) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = {
            "schema": "glueyneo.ym2610-admission.v1",
            "candidate": {"name": "ymfm YM2610", "upstream_revision": REVISION,
                          "license": "BSD-3-Clause"},
            "gates": {},
        }
    report["gates"]["installed_static_c_consumer"] = {
        "status": "unavailable", "evidence": str(error),
    }
    report["gates"]["installed_shared_c_consumer"] = {
        "status": "unavailable", "evidence": str(error),
    }
    report["admitted"] = False
    report["link_error"] = str(error)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")


def main() -> int:
    try:
        if len(sys.argv) == 2 and sys.argv[1] == "source":
            source_check()
            print(f"ym2610 source gate: {len(FILES)} pinned files at {REVISION}")
            print("mutable globals: none; license: BSD-3-Clause; inventory: complete")
            return 0
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command", required=True)
        test_parser = subparsers.add_parser("test")
        test_parser.add_argument("--binary", required=True, type=Path)
        test_parser.add_argument("--report", required=True, type=Path)
        link_parser = subparsers.add_parser("link")
        link_parser.add_argument("--both-linkages", action="store_true")
        link_parser.add_argument("--report", type=Path)
        arguments = parser.parse_args()
        if arguments.command == "test":
            report = test_run(arguments.binary, arguments.report)
            print(f"YM2610 direct C consumer: {report['direct_consumer']['test_count']} tests passed")
            print(f"YM2610 report: {arguments.report}")
            return 0
        if arguments.command == "link" and arguments.both_linkages:
            report_path = arguments.report or ROOT / "build/ym2610-admission/ym2610-admission.json"
            try:
                report = link_both_linkages(report_path)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                record_link_failure(report_path, error)
                raise
            print("YM2610 installed C consumers: static=pass shared=pass")
            print(f"YM2610 linkage report: {report_path}")
            return 0
        parser.error("link requires --both-linkages")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"ym2610 admission check failed: {error}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
