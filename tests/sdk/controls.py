#!/usr/bin/env python3
"""Supervise exact SDK negative controls and independent public runner results."""

from __future__ import annotations

import json
import math
import os
import platform
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


CONTROL_CASES = {
    "arithmetic": ("sdk.observe.arithmetic", 10, 11),
    "initialized": ("sdk.observe.initialized", 0x1237, 0x1238),
    "bss": ("sdk.observe.bss", 1, 2),
    "run-instructions": ("sdk.run.instructions", 12, 13),
    "run-elapsed": ("sdk.run.elapsed-cycles", 172, 173),
    "run-stop": ("sdk.run.reason-stopped", 1, 0),
    "byte-order": ("sdk.observe.arithmetic-byte-order", 10, 167772160),
    "access-order": ("sdk.bus.event.00.address", 0, 2),
}
ISOLATION_CONTROL_CASES = {
    "swapped-owner": ("sdk.isolation.owner.arithmetic", 10, 16),
    "altered-split-progress": ("sdk.isolation.split-progress", 40, 41),
}

ASSERTION = re.compile(
    r"(?m)^# ASSERT (?P<id>\S+) expected=(?P<expected>\d+) observed=(?P<observed>\d+)$"
)
SUMMARY = re.compile(r"(?m)^(?P<cases>\d+) Tests (?P<failures>\d+) Failures 0 Ignored\s*$")
FAILURE = re.compile(r"(?m)^.*:FAIL:.*$")
RESULT = re.compile(r"(?m)^SDK_RESULT (\{.*\})$")


def fail(message: str, output: str = "") -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    if output:
        print(output, file=sys.stderr)
    return 1


def negative_control_is_valid(returncode: int, output: str,
                              expected_id: str,
                              expected_pair: tuple[int, int] | None = None) -> bool:
    if returncode != 1:
        return False
    summaries = list(SUMMARY.finditer(output))
    if len(summaries) != 1 or summaries[0].group("cases") != "1" or \
            summaries[0].group("failures") != "1":
        return False
    failures = list(FAILURE.finditer(output))
    if len(failures) != 1 or expected_id not in failures[0].group(0):
        return False
    assertions = [match for match in ASSERTION.finditer(output)
                  if match.group("id") == expected_id]
    if len(assertions) != 1:
        return False
    observed_pair = (int(assertions[0].group("expected")),
                     int(assertions[0].group("observed")))
    if observed_pair[0] == observed_pair[1]:
        return False
    if expected_pair is not None and observed_pair != expected_pair:
        return False
    results = list(RESULT.finditer(output))
    if len(results) != 1:
        return False
    try:
        record = json.loads(results[0].group(1))
    except json.JSONDecodeError:
        return False
    return (record.get("outcome") == "fail" and record.get("cases", 0) == 1 and
            isinstance(record.get("assertions"), int) and record["assertions"] > 0)


def run_child(command: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True,
                          errors="replace", timeout=timeout, check=False)


def supervisor_self_controls() -> int:
    target_id = "sdk.observe.arithmetic"
    good = (
        "# ASSERT sdk.observe.arithmetic expected=10 observed=11\n"
        "1 Tests 1 Failures 0 Ignored\n"
        'SDK_RESULT {"outcome":"fail","cases":1,"assertions":1}\n'
        "file.c:1:test:FAIL: Expected 10 Was 11:sdk.observe.arithmetic\n"
    )
    rejected = {
        "normal exit": (0, good, (10, 11)),
        "signal": (-11, good, (10, 11)),
        "unrelated assertion": (
            1, good.replace("sdk.observe.arithmetic", "sdk.other.claim"), (10, 11)),
        "unchanged value": (
            1, good.replace("observed=11", "observed=10")
               .replace("Was 11", "Was 10"), (10, 11)),
        "multiple failures": (
            1, good + "file.c:2:test:FAIL: unrelated\n", (10, 11)),
        "zero denominator": (
            1, good.replace('"assertions":1', '"assertions":0'), (10, 11)),
        "zero cases": (
            1, good.replace("1 Tests 1 Failures", "0 Tests 1 Failures"), (10, 11)),
        "timeout output": (None, good, (10, 11)),
    }
    for name, (returncode, output, pair) in rejected.items():
        if returncode is None:
            valid = False
        else:
            valid = negative_control_is_valid(returncode, output, target_id, pair)
        if valid:
            return fail(f"supervisor accepted malformed child outcome: {name}")
    print(f"PASS: supervisor_self_controls={len(rejected)} rejected_outcomes")
    return 0


def sdk_result(output: str) -> dict[str, Any] | None:
    matches = list(RESULT.finditer(output))
    if len(matches) != 1:
        return None
    try:
        return json.loads(matches[0].group(1))
    except json.JSONDecodeError:
        return None


def run_control_matrix(executable: str) -> int:
    normal = run_child([executable, "controls"])
    output = normal.stdout + normal.stderr
    record = sdk_result(output)
    if (normal.returncode != 0 or record is None or
            record.get("outcome") != "pass" or record.get("cases", 0) < 1 or
            record.get("assertions", 0) < 1):
        return fail("normal named-observation and functional trace checks failed", output)
    print("PASS: normal-sdk-controls "
          f"cases={record['cases']} assertions={record['assertions']}")

    for name, (assertion_id, expected, observed) in CONTROL_CASES.items():
        try:
            child = run_child([executable, f"control-{name}"])
        except subprocess.TimeoutExpired as error:
            return fail(f"{name} mutation timed out", str(error.stdout or ""))
        except OSError as error:
            return fail(f"cannot execute {name} mutation: {error}")
        output = child.stdout + child.stderr
        if not negative_control_is_valid(child.returncode, output,
                                         assertion_id, (expected, observed)):
            return fail(f"{name} mutation did not fail its exact assertion", output)
        child_record = sdk_result(output)
        print(f"PASS: control={name} assertion={assertion_id} "
              f"expected={expected} observed={observed} "
              f"assertions={child_record['assertions']}")
    return 0


def run_isolation_matrix(executable: str, timeout_seconds: float = 30.0) -> int:
    try:
        normal = run_child([executable, "isolation"], timeout=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        return fail("normal isolation comparison timed out", str(error.stdout or ""))
    except OSError as error:
        return fail(f"cannot execute isolation comparison: {error}")
    output = normal.stdout + normal.stderr
    record = sdk_result(output)
    expected_summary = (
        "SDK_ISOLATION boundaries=13 interleaved_pairs=16 "
        "barrier_concurrent_pairs=16 concurrent_candidate_failure_paths=32"
    )
    summaries = [line for line in output.splitlines()
                 if line.startswith("SDK_ISOLATION ")]
    if (normal.returncode != 0 or record is None or
            record.get("outcome") != "pass" or record.get("cases") != 1 or
            record.get("assertions") != 11 or summaries != [expected_summary]):
        return fail("normal equal-boundary isolation checks failed", output)
    print("PASS: normal-isolation boundaries=13 interleaved_pairs=16 "
          "barrier_concurrent_pairs=16 assertions=11")
    print("SDK_CONTROL_RESULT " + json.dumps(record, sort_keys=True))

    for name, (assertion_id, expected, observed) in ISOLATION_CONTROL_CASES.items():
        try:
            child = run_child([executable, f"control-{name}"])
        except subprocess.TimeoutExpired as error:
            return fail(f"isolation {name} mutation timed out", str(error.stdout or ""))
        except OSError as error:
            return fail(f"cannot execute isolation {name} mutation: {error}")
        output = child.stdout + child.stderr
        if not negative_control_is_valid(child.returncode, output,
                                         assertion_id, (expected, observed)):
            return fail(f"isolation {name} mutation did not fail its exact assertion",
                        output)
        child_record = sdk_result(output)
        print(f"PASS: isolation_control={name} assertion={assertion_id} "
              f"expected={expected} observed={observed} "
              f"assertions={child_record['assertions']}")
    return 0


def run_cold_processes(executable: str) -> int:
    process_count = 8
    expected_line = (
        "SDK_COLD process_pairs=1 owners=2 candidate_failure_paths=2 "
        "reset_recoveries=2 teardown_leaks=0"
    )
    for process_number in range(1, process_count + 1):
        try:
            child = run_child([executable, "cold"], timeout=30.0)
        except subprocess.TimeoutExpired as error:
            return fail(f"cold process {process_number} timed out",
                        str(error.stdout or ""))
        except OSError as error:
            return fail(f"cannot execute cold process {process_number}: {error}")
        output = child.stdout + child.stderr
        record = sdk_result(output)
        summaries = [line for line in output.splitlines()
                     if line.startswith("SDK_COLD ")]
        if (child.returncode != 0 or record is None or
                record.get("outcome") != "pass" or record.get("cases") != 1 or
                record.get("assertions") != 19 or summaries != [expected_line]):
            return fail(f"cold process {process_number} did not prove pair lifecycle",
                        output)
        if process_number == 1:
            representative_record = record
    print("PASS: cold_processes=8 concurrent_pairs=8 owners=16 "
          "candidate_failure_paths=16 reset_recoveries=16 teardown_leaks=0")
    print("SDK_CONTROL_RESULT " + json.dumps(representative_record, sort_keys=True))
    return 0


SANITIZER_LANES = (
    ("sdk-asan-ubsan", "asan-ubsan", "ADDRESS_UNDEFINED",
     "-fsanitize=address,undefined",
     "^sdk_(diagnostic|lifecycle|media|faults|run|mutation_media|mutation_sequence|mutation_minimizer|state_hostile|state_oom|save_api|save_receipts|save_lifecycle)$"),
    ("sdk-tsan", "tsan", "THREAD", "-fsanitize=thread", "^sdk_(isolation|cold|state_isolation)$"),
)


def process_tree_rss_kib(root_pid: int) -> int | None:
    """Return one sampled descendant-tree RSS total, or None without ps."""
    try:
        result = subprocess.run(["ps", "-axo", "pid=,ppid=,rss="],
                                capture_output=True, text=True, timeout=2.0,
                                check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    children: dict[int, list[tuple[int, int]]] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        try:
            pid, ppid, rss = (int(field) for field in fields)
        except ValueError:
            continue
        children.setdefault(ppid, []).append((pid, rss))
    pending = [root_pid]
    total = 0
    while pending:
        parent = pending.pop()
        for child_pid, rss in children.get(parent, []):
            total += rss
            pending.append(child_pid)
    return total


def run_logged(command: list[str], log_path: Path, sample_rss: bool = False,
               timeout: float = 600.0,
               environment: dict[str, str] | None = None) -> tuple[int, float, int | None, str]:
    start = time.perf_counter()
    peak_rss: int | None = None
    with log_path.open("w", encoding="utf-8") as log_file:
        try:
            child = subprocess.Popen(command, stdout=log_file,
                                     stderr=subprocess.STDOUT, text=True,
                                     start_new_session=(os.name == "posix"),
                                     env=environment)
        except OSError as error:
            log_file.write(f"could not start command: {error}\n")
            return 127, time.perf_counter() - start, None, str(error)
        deadline = start + timeout
        while child.poll() is None:
            if sample_rss:
                rss = process_tree_rss_kib(child.pid)
                if rss is not None:
                    peak_rss = max(peak_rss or 0, rss)
            if time.perf_counter() >= deadline:
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
                log_file.write(f"\ncommand timed out after {timeout} seconds\n")
                break
            time.sleep(0.02)
        returncode = child.returncode if child.returncode is not None else 124
    elapsed = time.perf_counter() - start
    return returncode, elapsed, peak_rss, log_path.read_text(encoding="utf-8", errors="replace")


def cache_values(cache_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not cache_path.exists():
        return values
    for line in cache_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("//") or not line or "=" not in line or ":" not in line:
            continue
        key_type, value = line.split("=", 1)
        key = key_type.split(":", 1)[0]
        values[key] = value
    return values


def verify_target_scoped_flags(build_dir: Path, sanitizer_flag: str,
                               lane_mode: str) -> tuple[bool, str]:
    cache = cache_values(build_dir / "CMakeCache.txt")
    if cache.get("CMAKE_C_FLAGS", "") != "":
        return False, "CMAKE_C_FLAGS is not empty; instrumentation may be global"
    if cache.get("GLUEYNEO_SDK_SANITIZER") != lane_mode:
        return False, "configured sanitizer cache mode does not match this lane"
    commands_file = build_dir / "compile_commands.json"
    if not commands_file.exists():
        return False, "compile_commands.json was not generated"
    try:
        commands = json.loads(commands_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return False, f"compile_commands.json is unreadable: {error}"
    relevant = [entry for entry in commands
                if any(name in Path(entry.get("file", "")).as_posix()
                       for name in ("src/instance.c", "tests/sdk/test_sdk.c",
                                    "tests/fuzz/sdk_mutation.c"))]
    if not relevant or any(sanitizer_flag not in entry.get("command", "")
                           and sanitizer_flag not in " ".join(entry.get("arguments", []))
                           for entry in relevant):
        return False, "a core, SDK suite, or mutation compile command lacks its sanitizer flag"
    try:
        link_commands = subprocess.run(
            ["ninja", "-C", str(build_dir), "-t", "commands", "sdk_mutation"],
            capture_output=True, text=True, timeout=10.0, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"could not inspect sanitizer link command: {error}"
    if (link_commands.returncode != 0 or
            not any("-fsanitize=" in line and sanitizer_flag in line
                    for line in link_commands.stdout.splitlines())):
        return False, "sdk_mutation link command lacks its lane sanitizer flag"
    install_prefix = build_dir / "sanitizer-control" / "consumer-install"
    try:
        installation = subprocess.run(
            ["cmake", "--install", str(build_dir), "--prefix", str(install_prefix)],
            capture_output=True, text=True, timeout=30.0, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"could not inspect installed consumer export: {error}"
    if installation.returncode != 0:
        return False, "could not install sanitized package for export inspection"
    export_files = list(install_prefix.rglob("GlueyneoTargets.cmake"))
    if not export_files:
        return False, "installed package did not contain GlueyneoTargets.cmake"
    export_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in export_files)
    link_options = re.findall(
        r"(?m)^\s*INTERFACE_LINK_OPTIONS\s+\"([^\"]*)\"", export_text)
    if len(link_options) != 1 or link_options[0].split(";") != [sanitizer_flag]:
        return False, ("installed static target must export exactly its sanitizer "
                       "runtime selector and no other link policy")
    compile_options = re.findall(
        r"(?m)^\s*INTERFACE_COMPILE_OPTIONS\s+\"([^\"]*)\"", export_text)
    if any("-fsanitize" in value or "-fno-" in value for value in compile_options):
        return False, "private sanitizer compile or recovery flags leaked to consumers"
    if not re.search(r"INTERFACE_LINK_LIBRARIES.*LINK_LANGUAGE:C>:[^\"]+", export_text):
        return False, "installed C consumer lost the private C++ runtime dependency"
    return True, (f"private compile policy, runtime-only interface option, and C++ "
                  f"runtime closure verified ({len(relevant)} relevant compile entries)")


INSTALLED_SANITIZER_FLAGS = {
    "ADDRESS_UNDEFINED": "-fsanitize=address,undefined",
    "THREAD": "-fsanitize=thread",
}


def sanitizer_runtime_diagnostic_tail(ctest_output: str, test_details: str,
                                      limit: int = 60) -> list[str]:
    """Retain each failed test's output and CTest summary within a line bound."""
    ctest_lines = ctest_output.splitlines()
    detail_lines = test_details.splitlines()
    failure_start = next((index for index in range(len(ctest_lines) - 1, -1, -1)
                          if ctest_lines[index].strip() == "The following tests FAILED:"),
                         None)
    if failure_start is None:
        return (ctest_lines + detail_lines)[-limit:]

    failure_names = re.findall(
        r"(?m)^\s*\d+\s+-\s+(sdk_\w+)\s+\([^\n]+\)\s*$",
        "\n".join(ctest_lines[failure_start + 1:]))
    failure_summary = [
        line for line in ctest_lines[:failure_start]
        if re.search(r"\d+% tests passed, \d+ tests? failed", line) or
        "Total Test time" in line
    ]
    failure_summary.append(ctest_lines[failure_start])
    failure_summary.extend(
        line for line in ctest_lines[failure_start + 1:]
        if re.match(r"^\s*\d+\s+-\s+sdk_\w+\s+\([^\n]+\)\s*$", line))

    starts = list(re.finditer(r"(?m)^\d+/\d+ Testing: (sdk_\w+)\s*$", test_details))
    test_output: dict[str, list[str]] = {}
    for index, match in enumerate(starts):
        name = match.group(1)
        if name not in failure_names:
            continue
        section_end = starts[index + 1].start() if index + 1 < len(starts) else len(test_details)
        section = test_details[match.start():section_end].splitlines()
        output_start = next((line_index for line_index, line in enumerate(section)
                             if line.strip() == "Output:"), None)
        if output_start is None:
            continue
        output_end = next((line_index for line_index in range(output_start + 1, len(section))
                           if re.match(rf'^"{re.escape(name)}" (?:end time|time elapsed):',
                                       section[line_index]) or
                           section[line_index] in {"Test Passed.", "Test Failed."}),
                          len(section))
        output = [line for line in section[output_start + 1:output_end]
                  if line.strip() and not re.fullmatch(r"[-=]{3,}", line.strip())]
        if output:
            test_output[name] = output

    if len(failure_summary) >= limit:
        failure_summary = [failure_summary[0], *failure_summary[-(limit - 1):]]
    detail_budget = limit - len(failure_summary)
    details: list[str] = []
    selected_names = [name for name in failure_names if name in test_output]
    if selected_names and detail_budget > 0:
        per_test_budget = max(1, detail_budget // len(selected_names))
        for name in selected_names:
            output = test_output[name]
            if len(output) > per_test_budget:
                output = output[-per_test_budget:]
            details.extend(output)
    elif detail_budget > 0:
        details = detail_lines[-detail_budget:]

    remaining = limit - len(failure_summary) - len(details)
    context = ctest_lines[:failure_start][-remaining:] if remaining > 0 else []
    return (details + context + failure_summary)[-limit:]


def stage_consumer_project(destination: Path) -> None:
    """Copy only public consumer inputs so final links cannot use source-tree paths."""
    destination.mkdir(parents=True, exist_ok=True)
    files = {
        "tests/consumers/CMakeLists.txt": "CMakeLists.txt",
        "tests/consumers/header.cpp": "header.cpp",
        "tests/consumers/sanitizer_runtime.cpp": "sanitizer_runtime.cpp",
        "tests/consumers/sound_consumer.c": "sound_consumer.c",
        "examples/continuation.c": "continuation.c",
        "examples/persistence.c": "persistence.c",
        "examples/persistence_host.c": "persistence_host.c",
        "examples/persistence_host.h": "persistence_host.h",
        "tests/fixture/public_persistence_guest.c": "public_persistence_guest.c",
        "tests/fixture/public_sound_guest.c": "public_sound_guest.c",
        ".release-please-manifest.json": ".release-please-manifest.json",
    }
    root = Path(__file__).resolve().parents[2]
    for source, name in files.items():
        shutil.copy2(root / source, destination / name)


def sanitizer_missing_runtime(output: str, mode: str) -> bool:
    """Recognize a final-link failure naming this mode's actual runtime symbols."""
    lowered = output.lower()
    if not any(marker in lowered for marker in (
            "undefined symbols", "undefined reference", "symbol(s) not found",
            "unresolved external", "ld.lld: error: undefined")):
        return False
    names = (r"_{0,2}asan_", r"_{0,2}ubsan_") if mode == "ADDRESS_UNDEFINED" else (
        r"_{0,2}tsan_",)
    return any(re.search(name, lowered) for name in names)


def run_installed_sanitizers(mode: str) -> int:
    """Build, relocate, link, run, and mutate a real instrumented static SDK."""
    if mode not in INSTALLED_SANITIZER_FLAGS:
        return fail("installed sanitizer mode must be ADDRESS_UNDEFINED or THREAD")

    root = Path(__file__).resolve().parents[2]
    flag = INSTALLED_SANITIZER_FLAGS[mode]
    run_name = f"{time.time_ns()}-{os.getpid()}"
    result_dir = root / "build" / "installed-sanitizer-controls" / mode / run_name
    result_dir.mkdir(parents=True, exist_ok=False)
    report_path = result_dir / "report.json"
    report: dict[str, Any] = {
        "schema_version": 1,
        "mode": mode,
        "status": "failed",
        "linkage": "static",
        "runtime_flag": flag,
        "platform": {"system": platform.system(), "release": platform.release(),
                     "machine": platform.machine()},
        "compiler": {},
        "cases": [],
        "commands": [],
        "duration_seconds": 0.0,
        "first_failure": None,
    }
    started = time.perf_counter()

    def command(name: str, argv: list[str], timeout: float = 600.0,
                environment: dict[str, str] | None = None) -> tuple[int, str]:
        log = result_dir / f"{name}.log"
        code, seconds, _, output = run_logged(argv, log, timeout=timeout,
                                               environment=environment)
        report["commands"].append({"name": name, "argv": argv,
                                   "returncode": code, "seconds": seconds,
                                   "log": log.name})
        return code, output

    def record_case(case_id: str, outcome: str, assertions: int,
                    detail: str, seconds: float | None = None,
                    *, tested_mode: str | None = None,
                    linkage: str = "static",
                    prefixes: list[str] | None = None,
                    unsupported_reason: str | None = None) -> None:
        row_mode = tested_mode or mode
        compiler = dict(report["compiler"])
        compiler["sanitizer"] = row_mode
        row = {
            "schema_version": 1,
            "case_id": case_id,
            "mode": mode,
            "tested_mode": row_mode,
            "run_id": run_name,
            "prefix_id": f"installed/{mode}/{run_name}",
            "linkage": linkage,
            "configuration": "Debug",
            "outcome": outcome,
            "cases": 1 if outcome == "pass" else 0,
            "assertions": assertions if outcome == "pass" else 0,
            "duration_seconds": seconds if seconds is not None else time.perf_counter() - started,
            "detail": detail,
            "compiler": compiler,
            "platform": report["platform"],
        }
        if prefixes is not None:
            row["prefixes"] = prefixes
        if unsupported_reason is not None:
            row["unsupported_reason"] = unsupported_reason
        report["cases"].append(row)
        print("SDK_INSTALLED_SANITIZER " + json.dumps(row, sort_keys=True))

    def finish(status: str, error: str | None = None) -> int:
        existing = {row["case_id"] for row in report["cases"]}
        fallback_outcome = "unsupported" if status == "unsupported" else "failed"
        for missing_case in sorted({"ordinary_none_export", "installed_c_chip",
                                    "installed_cxx_chip", "removed_runtime_usage"} - existing):
            reason = error or f"installed sanitizer verification ended with {status}"
            record_case(
                missing_case, fallback_outcome, 0, reason,
                tested_mode="NONE" if missing_case == "ordinary_none_export" else mode,
                linkage="static_shared" if missing_case == "ordinary_none_export" else "static",
                unsupported_reason=reason if fallback_outcome == "unsupported" else None)
        report["status"] = status
        report["duration_seconds"] = time.perf_counter() - started
        if error:
            report["first_failure"] = error
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print("SDK_INSTALLED_SANITIZER_REPORT " + json.dumps({
            "mode": mode, "status": status, "report": report_path.relative_to(root).as_posix(),
            "duration_seconds": report["duration_seconds"],
        }, sort_keys=True))
        return 0 if status in {"passed", "unsupported"} else 1

    def run_none_exports(consumer_source: Path, workspace: Path) -> tuple[str | None, int, list[str]]:
        stage_consumer_project(consumer_source)
        prefix_ids: list[str] = []
        assertions = 0
        for linkage in ("static", "shared"):
            shared = linkage == "shared"
            producer_build_none = workspace / f"none-{mode.lower()}-{linkage}-build"
            install_none = workspace / f"none-{mode.lower()}-{linkage}-install"
            prefix_none = workspace / f"none-{mode.lower()}-{linkage}-prefix"
            consumer_build_none = workspace / f"none-{mode.lower()}-{linkage}-consumer"
            prefix_ids.append(f"installed/NONE/{linkage}/{run_name}")
            configure_argv_none = [
                shutil.which("cmake") or "cmake", "-S", str(root), "-B", str(producer_build_none),
                "-G", "Ninja", f"-DBUILD_SHARED_LIBS={'ON' if shared else 'OFF'}",
                "-DGLUEYNEO_BUILD_TESTS=OFF", "-DGLUEYNEO_YM2610_ADMISSION=OFF",
                "-DGLUEYNEO_SDK_SANITIZER=NONE", "-DCMAKE_BUILD_TYPE=Debug",
            ]
            configure_status_none, configure_output_none = command(
                f"none-{linkage}-configure", configure_argv_none)
            if configure_status_none != 0:
                return (f"NONE {linkage} producer configure failed: " +
                        " | ".join(configure_output_none.splitlines()[-8:]), assertions, prefix_ids)
            cache_none = cache_values(producer_build_none / "CMakeCache.txt")
            if not report["compiler"].get("c_id"):
                c_identity = re.search(
                    r"(?m)^-- The C compiler identification is ([^\r\n]+)$", configure_output_none)
                cxx_identity = re.search(
                    r"(?m)^-- The CXX compiler identification is ([^\r\n]+)$", configure_output_none)
                c_parts = c_identity.group(1).split() if c_identity else []
                cxx_parts = cxx_identity.group(1).split() if cxx_identity else []
                report["compiler"] = {
                    "c_id": c_parts[0] if c_parts else "unknown",
                    "c_version": " ".join(c_parts[1:]) if c_parts else "unknown",
                    "c_path": cache_none.get("CMAKE_C_COMPILER", "unknown"),
                    "cxx_id": cxx_parts[0] if cxx_parts else "unknown",
                    "cxx_version": " ".join(cxx_parts[1:]) if cxx_parts else "unknown",
                    "cxx_path": cache_none.get("CMAKE_CXX_COMPILER", "unknown"),
                    "linker": cache_none.get("CMAKE_LINKER", "compiler driver"),
                    "generator": cache_none.get("CMAKE_GENERATOR", "unknown"),
                    "configuration": "Debug", "sanitizer": "NONE",
                }
            build_status_none, build_output_none = command(
                f"none-{linkage}-producer-build", [
                    shutil.which("cmake") or "cmake", "--build", str(producer_build_none),
                    "--target", "glueyneo", "glueyneo-diagnostic", "glueyneo_libretro",
                    "glueyneo-original-fixture",
                    "--parallel", "2",
                ], timeout=900.0)
            if build_status_none != 0:
                return (f"NONE {linkage} producer build failed: " +
                        " | ".join(build_output_none.splitlines()[-8:]), assertions, prefix_ids)
            install_status_none, install_output_none = command(
                f"none-{linkage}-install", [
                    shutil.which("cmake") or "cmake", "--install", str(producer_build_none),
                    "--prefix", str(install_none),
                ], timeout=120.0)
            if install_status_none != 0:
                return (f"NONE {linkage} install failed: " +
                        " | ".join(install_output_none.splitlines()[-8:]), assertions, prefix_ids)
            shutil.move(str(install_none), str(prefix_none))
            shutil.move(str(producer_build_none), str(workspace / f"none-{mode.lower()}-{linkage}-hidden"))
            export_files_none = list(prefix_none.rglob("GlueyneoTargets.cmake"))
            if not export_files_none:
                return (f"NONE {linkage} installed target export is missing", assertions, prefix_ids)
            export_text_none = "\n".join(
                path.read_text(encoding="utf-8", errors="replace") for path in export_files_none)
            if "-fsanitize" in export_text_none or "-fno-sanitize" in export_text_none:
                return (f"NONE {linkage} export contains sanitizer usage", assertions, prefix_ids)
            assertions += 1

            consumer_configure_none = [
                shutil.which("cmake") or "cmake", "-S", str(consumer_source), "-B",
                str(consumer_build_none), "-G", "Ninja", f"-DCMAKE_PREFIX_PATH={prefix_none}",
                f"-DGLUEYNEO_CONSUMER_C_SOURCE={consumer_source / 'sound_consumer.c'}",
                f"-DGLUEYNEO_SOUND_FIXTURE_SOURCE={consumer_source / 'public_sound_guest.c'}",
                "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            ]
            consumer_configure_status_none, consumer_configure_output_none = command(
                f"none-{linkage}-consumer-configure", consumer_configure_none)
            if consumer_configure_status_none != 0:
                return (f"NONE {linkage} consumer configure failed: " +
                        " | ".join(consumer_configure_output_none.splitlines()[-8:]), assertions, prefix_ids)
            consumer_build_status_none, consumer_build_output_none = command(
                f"none-{linkage}-consumer-build", [
                    shutil.which("cmake") or "cmake", "--build", str(consumer_build_none),
                    "--target", "glueyneo-installed-sound", "glueyneo-installed-cxx-runtime",
                    "--parallel", "2", "--verbose",
                ], timeout=360.0)
            if consumer_build_status_none != 0:
                return (f"NONE {linkage} installed C/C++ consumers did not link: " +
                        " | ".join(consumer_build_output_none.splitlines()[-8:]), assertions, prefix_ids)
            compile_text_none = (consumer_build_none / "compile_commands.json").read_text(
                encoding="utf-8", errors="replace")
            if "-fsanitize" in compile_text_none or "-fno-sanitize" in compile_text_none:
                return (f"NONE {linkage} consumer compile received sanitizer flags", assertions, prefix_ids)
            link_lines_none = [line for line in consumer_build_output_none.splitlines()
                               if " -o glueyneo-installed-sound " in line or
                               " -o glueyneo-installed-cxx-runtime " in line]
            if (len(link_lines_none) != 2 or any("-fsanitize" in line or
                    "-fno-sanitize" in line for line in link_lines_none)):
                return (f"NONE {linkage} consumer final link has sanitizer flags", assertions, prefix_ids)
            assertions += 2

            runtime_env = None
            if shared:
                runtime_env = os.environ.copy()
                for variable in ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "LD_LIBRARY_PATH"):
                    runtime_env.pop(variable, None)
                if os.name == "nt":
                    runtime_env["PATH"] = str(prefix_none / "bin") + os.pathsep + runtime_env.get("PATH", "")
                elif platform.system() == "Darwin":
                    runtime_env["DYLD_LIBRARY_PATH"] = str(prefix_none / "lib")
                else:
                    runtime_env["LD_LIBRARY_PATH"] = str(prefix_none / "lib")
            c_executable_none = consumer_build_none / "glueyneo-installed-sound"
            cxx_executable_none = consumer_build_none / "glueyneo-installed-cxx-runtime"
            if os.name == "nt":
                c_executable_none = c_executable_none.with_suffix(".exe")
                cxx_executable_none = cxx_executable_none.with_suffix(".exe")
            fixture_none = workspace / f"none-{mode.lower()}-{linkage}-fixture.gnmv"
            c_trace_none = workspace / f"none-{mode.lower()}-{linkage}-c.trace"
            cxx_trace_none = workspace / f"none-{mode.lower()}-{linkage}-cxx.trace"
            fixture_code, fixture_output = command(
                f"none-{linkage}-fixture", [str(c_executable_none), "--write-fixture",
                                              str(fixture_none)], timeout=30.0,
                environment=runtime_env)
            if fixture_code != 0 or not fixture_none.is_file():
                return (f"NONE {linkage} C consumer failed to write its public fixture: " +
                        " | ".join(fixture_output.splitlines()[-6:]), assertions, prefix_ids)
            c_code, c_output = command(
                f"none-{linkage}-c-run", [str(c_executable_none), str(fixture_none), "--trace",
                                           str(c_trace_none)], timeout=120.0,
                environment=runtime_env)
            cxx_code, cxx_output = command(
                f"none-{linkage}-cxx-run", [str(cxx_executable_none), str(fixture_none), "--trace",
                                             str(cxx_trace_none)], timeout=120.0,
                environment=runtime_env)
            if c_code != 0 or cxx_code != 0:
                return (f"NONE {linkage} installed consumer failed at runtime: " +
                        " | ".join((c_output + "\n" + cxx_output).splitlines()[-8:]), assertions, prefix_ids)
            c_rows = records_from_log(c_output, "SDK_SOUND ")
            cxx_rows = records_from_log(cxx_output, "SDK_SANITIZER_CONSUMER ")
            if (len(c_rows) != 1 or c_rows[0].get("outcome") != "pass" or
                    c_rows[0].get("frames") != 4 or c_rows[0].get("sample_frames", 0) <= 0 or
                    len(cxx_rows) != 1 or cxx_rows[0].get("outcome") != "pass" or
                    cxx_rows[0].get("language") != "C++17" or cxx_rows[0].get("assertions", 0) <= 0 or
                    not c_trace_none.is_file() or c_trace_none.stat().st_size <= 0 or
                    c_trace_none.read_bytes() != cxx_trace_none.read_bytes()):
                return (f"NONE {linkage} installed C/C++ workload or trace parity failed",
                        assertions, prefix_ids)
            assertions += 4
        return None, assertions, prefix_ids

    with tempfile.TemporaryDirectory(prefix="glueyneo-installed-sanitizer-") as temporary:
        workspace = Path(temporary)
        producer = workspace / "producer-build"
        install = workspace / "install-before-relocation"
        relocated = workspace / "sdk-relocated"
        consumer_source = workspace / "consumer-source"
        consumer_build = workspace / "consumer-build"
        mutated_prefix = workspace / "sdk-without-runtime-usage"
        mutated_build = workspace / "consumer-build-without-runtime-usage"

        none_error, none_assertions, none_prefixes = run_none_exports(consumer_source, workspace)
        if none_error is not None:
            return finish("failed", none_error)
        record_case(
            "ordinary_none_export", "pass", none_assertions,
            "relocated ordinary NONE static/shared packages exported no sanitizer usage and ran C/C++ workloads",
            tested_mode="NONE", linkage="static_shared", prefixes=none_prefixes)

        configure_argv = [
            shutil.which("cmake") or "cmake", "-S", str(root), "-B", str(producer),
            "-G", "Ninja", "-DBUILD_SHARED_LIBS=OFF",
            "-DGLUEYNEO_BUILD_TESTS=OFF", "-DGLUEYNEO_YM2610_ADMISSION=OFF",
            f"-DGLUEYNEO_SDK_SANITIZER={mode}", "-DCMAKE_BUILD_TYPE=Debug",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        ]
        configure_status, configure_output = command("configure", configure_argv)
        if configure_status != 0:
            if "SDK_SANITIZER_UNSUPPORTED:" in configure_output:
                reason = configure_output.split("SDK_SANITIZER_UNSUPPORTED:", 1)[1].strip()
                report["unsupported_reason"] = reason.splitlines()[0]
                for case_id in ("installed_c_chip", "installed_cxx_chip",
                                "removed_runtime_usage"):
                    record_case(case_id, "unsupported", 0, report["unsupported_reason"])
                return finish("unsupported", report["unsupported_reason"])
            return finish("failed", "producer configure failed without an unsupported marker")

        cache = cache_values(producer / "CMakeCache.txt")
        c_identity = re.search(
            r"(?m)^-- The C compiler identification is ([^\r\n]+)$", configure_output)
        cxx_identity = re.search(
            r"(?m)^-- The CXX compiler identification is ([^\r\n]+)$", configure_output)
        c_identity_parts = c_identity.group(1).split() if c_identity else []
        cxx_identity_parts = cxx_identity.group(1).split() if cxx_identity else []
        report["compiler"] = {
            "c_id": c_identity_parts[0] if c_identity_parts else "unknown",
            "c_version": " ".join(c_identity_parts[1:]) if c_identity_parts else "unknown",
            "c_path": cache.get("CMAKE_C_COMPILER", "unknown"),
            "cxx_id": cxx_identity_parts[0] if cxx_identity_parts else "unknown",
            "cxx_version": " ".join(cxx_identity_parts[1:]) if cxx_identity_parts else "unknown",
            "cxx_path": cache.get("CMAKE_CXX_COMPILER", "unknown"),
            "linker": cache.get("CMAKE_LINKER", "compiler driver"),
            "generator": cache.get("CMAKE_GENERATOR", "unknown"),
            "configuration": cache.get("CMAKE_BUILD_TYPE", "unknown"),
            "sanitizer": cache.get("GLUEYNEO_SDK_SANITIZER", "unknown"),
        }
        if (report["compiler"]["c_id"] == "unknown" or
                report["compiler"]["cxx_id"] == "unknown" or
                report["compiler"]["sanitizer"] != mode):
            return finish("failed", "producer compiler or mode identity is incomplete")

        build_argv = [shutil.which("cmake") or "cmake", "--build", str(producer),
                      "--target", "glueyneo", "glueyneo-diagnostic",
                      "glueyneo_libretro", "glueyneo-original-fixture", "--parallel", "2"]
        build_status, build_output = command("producer-build", build_argv, timeout=900.0)
        if build_status != 0:
            return finish("failed", "instrumented static SDK build failed: " +
                          " | ".join(build_output.splitlines()[-8:]))
        install_status, install_output = command(
            "install", [shutil.which("cmake") or "cmake", "--install",
                        str(producer), "--prefix", str(install)], timeout=120.0)
        if install_status != 0 or not (install / "lib" / "cmake" / "Glueyneo" /
                                       "GlueyneoTargets.cmake").is_file():
            return finish("failed", "instrumented SDK install failed: " +
                          " | ".join(install_output.splitlines()[-8:]))

        shutil.move(str(install), str(relocated))
        shutil.move(str(producer), str(workspace / "producer-build-hidden"))
        stage_consumer_project(consumer_source)
        consumer_configure = [
            shutil.which("cmake") or "cmake", "-S", str(consumer_source), "-B",
            str(consumer_build), "-G", "Ninja", f"-DCMAKE_PREFIX_PATH={relocated}",
            f"-DGLUEYNEO_CONSUMER_C_SOURCE={consumer_source / 'sound_consumer.c'}",
            f"-DGLUEYNEO_SOUND_FIXTURE_SOURCE={consumer_source / 'public_sound_guest.c'}",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        ]
        consumer_configure_status, consumer_configure_output = command(
            "consumer-configure", consumer_configure)
        if consumer_configure_status != 0:
            return finish("failed", "relocated consumer configure failed: " +
                          " | ".join(consumer_configure_output.splitlines()[-8:]))

        target_file = relocated / "lib" / "cmake" / "Glueyneo" / "GlueyneoTargets.cmake"
        export_text = target_file.read_text(encoding="utf-8", errors="replace")
        link_values = re.findall(
            r"(?m)^\s*INTERFACE_LINK_OPTIONS\s+\"([^\"]*)\"", export_text)
        if len(link_values) != 1 or link_values[0].split(";") != [flag]:
            return finish("failed", "relocated target lacks the exact runtime-only interface option")
        compile_values = re.findall(
            r"(?m)^\s*INTERFACE_COMPILE_OPTIONS\s+\"([^\"]*)\"", export_text)
        if any("-fsanitize" in value or "-fno-" in value for value in compile_values):
            return finish("failed", "private compile or recovery flags leaked to installed consumers")
        if not re.search(r"INTERFACE_LINK_LIBRARIES.*LINK_LANGUAGE:C>:[^\"]+", export_text):
            return finish("failed", "relocated C consumer lost the private C++ runtime closure")

        consumer_build_argv = [
            shutil.which("cmake") or "cmake", "--build", str(consumer_build),
            "--target", "glueyneo-installed-sound", "glueyneo-installed-cxx-runtime",
            "--parallel", "2", "--verbose",
        ]
        consumer_build_status, consumer_build_output = command(
            "consumer-build", consumer_build_argv, timeout=360.0)
        if consumer_build_status != 0:
            return finish("failed", "relocated installed C/C++ consumer final links failed: " +
                          " | ".join(consumer_build_output.splitlines()[-10:]))

        compile_commands_path = consumer_build / "compile_commands.json"
        try:
            compile_commands = json.loads(compile_commands_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return finish("failed", f"consumer compile commands are unreadable: {error}")
        consumer_entries = [entry for entry in compile_commands
                            if Path(entry.get("file", "")).name in
                            {"sound_consumer.c", "sanitizer_runtime.cpp"}]
        consumer_source_names = {Path(entry.get("file", "")).name
                                 for entry in consumer_entries}
        if consumer_source_names != {"sound_consumer.c", "sanitizer_runtime.cpp"}:
            source_names = [Path(entry.get("file", "")).name for entry in compile_commands]
            return finish("failed", "consumer compile database omitted C or C++ runtime source: " +
                          repr(source_names))
        if any("-fsanitize" in entry.get("command", "") or
               "-fsanitize" in " ".join(entry.get("arguments", [])) or
               "-fno-sanitize" in entry.get("command", "")
               for entry in consumer_entries):
            return finish("failed", "consumer compile instrumentation leaked from installed target")
        link_lines = [line for line in consumer_build_output.splitlines()
                      if " -o glueyneo-installed-sound " in line or
                      " -o glueyneo-installed-cxx-runtime " in line]
        if (len(link_lines) != 2 or any(flag not in line for line in link_lines) or
                any("-fno-omit-frame-pointer" in line or "-fno-sanitize-recover" in line
                    for line in link_lines)):
            return finish("failed", "consumer final link commands lack only the required runtime selector")
        if any(str(root / "src") in line or str(root / "include") in line or
               str(workspace / "producer-build-hidden") in line
               for line in compile_commands_path.read_text(encoding="utf-8").splitlines()):
            return finish("failed", "consumer build command still references producer source/build paths")

        c_exe = consumer_build / "glueyneo-installed-sound"
        cxx_exe = consumer_build / "glueyneo-installed-cxx-runtime"
        fixture = workspace / "public-sound.gnmv"
        c_trace = workspace / "installed-c.trace"
        cxx_trace = workspace / "installed-cxx.trace"
        fixture_status, fixture_output = command(
            "fixture-write", [str(c_exe), "--write-fixture", str(fixture)], timeout=30.0)
        if fixture_status != 0 or not fixture.is_file():
            return finish("failed", "installed C consumer could not write the public fixture: " +
                          " | ".join(fixture_output.splitlines()[-6:]))
        c_run_status, c_output = command(
            "installed-c-run", [str(c_exe), str(fixture), "--trace", str(c_trace)], timeout=120.0)
        if c_run_status != 0:
            return finish("failed", "installed C consumer runtime failed: " +
                          " | ".join(c_output.splitlines()[-8:]))
        c_records = records_from_log(c_output, "SDK_SOUND ")
        if (len(c_records) != 1 or c_records[0].get("outcome") != "pass" or
                c_records[0].get("frames") != 4 or c_records[0].get("sample_frames", 0) <= 0 or
                any(c_records[0].get(field) != "pass" for field in ("tone", "fire", "release"))):
            return finish("failed", "installed C consumer omitted meaningful sound/video evidence")

        cxx_run_status, cxx_output = command(
            "installed-cxx-run", [str(cxx_exe), str(fixture), "--trace", str(cxx_trace)],
            timeout=120.0)
        if cxx_run_status != 0:
            return finish("failed", "installed C++ consumer runtime failed: " +
                          " | ".join(cxx_output.splitlines()[-8:]))
        cxx_records = records_from_log(cxx_output, "SDK_SANITIZER_CONSUMER ")
        if (len(cxx_records) != 1 or cxx_records[0].get("language") != "C++17" or
                cxx_records[0].get("outcome") != "pass" or cxx_records[0].get("cases") != 1 or
                cxx_records[0].get("assertions", 0) <= 0 or cxx_records[0].get("frames") != 4 or
                cxx_records[0].get("sample_frames", 0) <= 0):
            return finish("failed", "installed C++ consumer omitted its loaded-media assertions")
        if not c_trace.is_file() or not cxx_trace.is_file() or \
                c_trace.stat().st_size <= 0 or c_trace.read_bytes() != cxx_trace.read_bytes():
            return finish("failed", "C and C++ public fixture video/PCM traces differ")
        record_case("installed_c_chip", "pass", 8,
                    "relocated C17 consumer linked imported runtime usage and matched the public fixture workload")
        record_case("installed_cxx_chip", "pass", cxx_records[0]["assertions"],
                    "relocated C++17 consumer loaded original public media and matched C video/PCM trace")

        shutil.copytree(relocated, mutated_prefix)
        mutated_target = mutated_prefix / "lib" / "cmake" / "Glueyneo" / "GlueyneoTargets.cmake"
        mutated_text = mutated_target.read_text(encoding="utf-8", errors="replace")
        usage_pattern = re.compile(
            r"(?m)^(\s*INTERFACE_LINK_OPTIONS\s+\")([^\"]*)(\"\s*)$")
        removed = 0

        def remove_runtime_usage(match: re.Match[str]) -> str:
            nonlocal removed
            items = match.group(2).split(";")
            if flag not in items:
                return match.group(0)
            items.remove(flag)
            removed += 1
            return match.group(1) + ";".join(items) + match.group(3)

        mutated_text = usage_pattern.sub(remove_runtime_usage, mutated_text)
        if removed != 1:
            return finish("failed", "removed-runtime mutation did not remove exactly one exported option")
        mutated_target.write_text(mutated_text, encoding="utf-8")
        mutated_configure_status, mutated_configure_output = command(
            "negative-configure", [
                shutil.which("cmake") or "cmake", "-S", str(consumer_source), "-B",
                str(mutated_build), "-G", "Ninja", f"-DCMAKE_PREFIX_PATH={mutated_prefix}",
                f"-DGLUEYNEO_CONSUMER_C_SOURCE={consumer_source / 'sound_consumer.c'}",
                f"-DGLUEYNEO_SOUND_FIXTURE_SOURCE={consumer_source / 'public_sound_guest.c'}",
            ])
        if mutated_configure_status != 0:
            return finish("failed", "removed-runtime consumer configure failed before linking: " +
                          " | ".join(mutated_configure_output.splitlines()[-8:]))
        negative_results: list[bool] = []
        for case_name, target in (("c", "glueyneo-installed-sound"),
                                  ("cxx", "glueyneo-installed-cxx-runtime")):
            negative_status, negative_output = command(
                f"removed-runtime-{case_name}", [
                    shutil.which("cmake") or "cmake", "--build", str(mutated_build),
                    "--target", target, "--parallel", "2", "--verbose",
                ], timeout=180.0)
            expected_missing_runtime = (
                negative_status != 0 and
                sanitizer_missing_runtime(negative_output, mode) and
                ("Linking CXX executable" in negative_output or
                 "clang++: error: linker command failed" in negative_output or
                 "collect2: error: ld returned" in negative_output))
            negative_results.append(expected_missing_runtime)
        if negative_results != [True, True]:
            return finish("failed", "removed-runtime mutation did not fail both C and C++ final links for sanitizer symbols")
        record_case("removed_runtime_usage", "pass", 4,
                    "removing only exported runtime usage makes both C and C++ final links fail on sanitizer symbols")

    return finish("passed")


def records_from_log(output: str, prefix: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in output.splitlines():
        if not line.startswith(prefix):
            continue
        try:
            value = json.loads(line[len(prefix):])
        except json.JSONDecodeError:
            return []
        if isinstance(value, dict):
            records.append(value)
    return records


def sanitizer_lane(preset: str, probe_name: str, cache_mode: str,
                   sanitizer_flag: str, labels: str) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    build_dir = root / "build" / preset
    result_dir = build_dir / "sanitizer-control"
    result_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "preset": preset,
        "lane": probe_name,
        "status": "failed",
        "unsupported_reason": None,
        "configure_seconds": 0.0,
        "build_seconds": 0.0,
        "startup_seconds": 0.0,
        "runtime_seconds": None,
        "peak_process_tree_rss_kib_sampled_lower_bound": None,
        "rss_measurement_status": "unsupported",
        "rss_measurement_reason": "host process listing is unavailable or denied",
        "platform": {"system": platform.system(), "release": platform.release(),
                     "machine": platform.machine()},
        "compiler": {},
        "expected_tests": 13 if probe_name == "asan-ubsan" else 3,
        "ctest_parallel_jobs": 1 if probe_name == "tsan" else 2,
        "tests_passed": 0,
        "tests_attempted": 0,
        "sdk_assertions": 0,
        "commands": [],
        "configure_status": "not_started",
        "build_status": "not_started",
        "startup_status": "not_started",
        "runtime_status": "not_started",
    }

    def execute(stage: str, command: list[str], sample_rss: bool = False,
                timeout: float = 600.0) -> tuple[int, str]:
        log_path = result_dir / f"{stage}.log"
        returncode, seconds, peak_rss, output = run_logged(command, log_path,
                                                           sample_rss, timeout)
        report[f"{stage}_seconds"] = seconds
        report["commands"].append({"stage": stage, "argv": command,
                                   "returncode": returncode,
                                   "log": log_path.name})
        report[f"{stage}_status"] = "passed" if returncode == 0 else "failed"
        if sample_rss:
            report["peak_process_tree_rss_kib_sampled_lower_bound"] = peak_rss
            if peak_rss is not None:
                report["rss_measurement_status"] = "measured"
        return returncode, output

    configure_status, configure_output = execute(
        "configure", ["cmake", "--preset", preset])
    if configure_status != 0:
        report["failure_stage"] = "configure"
        if "SDK_SANITIZER_UNSUPPORTED:" in configure_output:
            report["status"] = "unsupported"
            report["configure_status"] = "unsupported"
            report["unsupported_reason"] = configure_output.split(
                "SDK_SANITIZER_UNSUPPORTED:", 1)[1].strip().splitlines()[0]
        else:
            report["error"] = "configure failed without an explicit unsupported marker"
            report["configure_log_tail"] = configure_output.splitlines()[-40:]
        return report

    cache = cache_values(build_dir / "CMakeCache.txt")
    report["compiler"] = {
        "id": cache.get("CMAKE_C_COMPILER_ID", "unknown"),
        "version": cache.get("CMAKE_C_COMPILER_VERSION", "unknown"),
        "configuration": cache.get("CMAKE_BUILD_TYPE", "unknown"),
        "sanitizer": cache.get("GLUEYNEO_SDK_SANITIZER", "unknown"),
    }
    build_status, build_output = execute("build", ["cmake", "--build", "--preset", preset])
    if build_status != 0:
        report["failure_stage"] = "build"
        report["error"] = "sanitized build failed"
        report["build_log_tail"] = build_output.splitlines()[-40:]
        return report

    scoped, scoped_message = verify_target_scoped_flags(build_dir, sanitizer_flag, cache_mode)
    report["target_scoped_flags"] = scoped_message
    if not scoped:
        report["failure_stage"] = "target_flags"
        report["error"] = scoped_message
        return report

    executable = build_dir / "sdk_mutation"
    startup_status, startup_output = execute(
        "startup", [str(executable), "--startup-probe", probe_name], timeout=30.0)
    startup_records = records_from_log(startup_output, "SANITIZER_STARTUP ")
    if startup_status != 0:
        report["failure_stage"] = "startup"
        known_runtime_unavailable = any(
            marker in startup_output.lower()
            for marker in ("fatal: threadsanitizer: unexpected memory mapping",
                           "threadsanitizer: failed to allocate shadow memory",
                           "addresssanitizer runtime does not come first",
                           "failed to allocate shadow memory", "library not loaded:",
                           "image not found", "dyld: library not loaded"))
        if known_runtime_unavailable:
            report["status"] = "unsupported"
            report["startup_status"] = "unsupported"
            report["unsupported_reason"] = (
                f"sanitized startup probe exit={startup_status}, "
                f"command={executable.name} --startup-probe {probe_name}; "
                "see startup.log for exact output")
            return report
        report["error"] = f"startup probe returned {startup_status} without a runtime failure signature"
        report["startup_log_tail"] = startup_output.splitlines()[-40:]
        return report
    if (len(startup_records) != 1 or startup_records[0].get("outcome") != "pass" or
            startup_records[0].get("lane") != probe_name or
            startup_records[0].get("startup_checks", 0) < 17 or
            startup_records[0].get("sanitizer") != cache_mode):
        report["error"] = "startup probe identity or check count is invalid"
        report["failure_stage"] = "startup"
        report["startup_log_tail"] = startup_output.splitlines()[-40:]
        return report
    report["startup"] = startup_records[0]
    report["startup_status"] = "passed"
    compiler_identity = startup_records[0].get("compiler", "unknown")
    compiler_id, separator, compiler_version = compiler_identity.partition(" ")
    report["compiler"]["id"] = compiler_id
    report["compiler"]["version"] = compiler_version if separator else "unknown"
    report["status"] = "startup_passed"

    ctest_command = ["ctest", "--preset", preset]
    if probe_name == "tsan":
        # These process/thread-heavy TSan tests pass individually, but running
        # both at once can starve the runtime until CTest's per-test timeout.
        ctest_command.extend(["--parallel", "1"])
    ctest_command.extend(["-R", labels, "--output-on-failure", "--no-tests=error"])
    ctest_status, ctest_output = execute(
        "runtime", ctest_command,
        sample_rss=True, timeout=900.0)
    last_test_log = build_dir / "Testing" / "Temporary" / "LastTest.log"
    test_details = (last_test_log.read_text(encoding="utf-8", errors="replace")
                    if last_test_log.exists() else "")
    ctest_log = ctest_output + "\n" + test_details
    sdk_records = records_from_log(ctest_log, "SDK_RESULT ")
    control_records = (records_from_log(ctest_log, "SDK_CONTROL_RESULT ")
                       if probe_name == "tsan" else [])
    log_records = sdk_records + control_records
    state_hostile_records = records_from_log(ctest_log, "STATE_HOSTILE_RESULT ")
    # Completed test rows retain partial progress on a failed CTest run. The
    # failure-list status may be Failed, Timeout, SEGFAULT, or another native
    # outcome; none of those is interchangeable with the old timeout receipt.
    completed = re.findall(
        r"(?m)^\s*\d+/\d+\s+Test #\d+:\s+(sdk_\w+)\s+([^\n]*?)\s+[\d.]+\s+sec\s*$",
        ctest_output)
    started = set(re.findall(r"(?m)^\s*Start \d+:\s+(sdk_\w+)\s*$", ctest_output))
    report["tests_attempted"] = len(started | {name for name, _ in completed})
    report["tests_passed"] = len({name for name, status in completed
                                  if re.search(r"\bPassed\b", status)})
    report["failed_tests"] = sorted(set(re.findall(
        r"(?m)^\s*\d+\s+-\s+(sdk_\w+)\s+\([^\n]+\)\s*$", ctest_output)))
    report["sdk_assertions"] = sum(
        record.get("assertions", 0) for record in log_records
        if isinstance(record.get("assertions"), int)) + sum(
            record.get("assertions", 0) for record in state_hostile_records
            if isinstance(record.get("assertions"), int))
    if ctest_status != 0:
        report["failure_stage"] = "runtime"
        report["runtime_status"] = "failed"
        report["status"] = "failed_runtime"
        report["error"] = f"runtime CTest suite exited {ctest_status}"
        report["runtime_log_tail"] = sanitizer_runtime_diagnostic_tail(
            ctest_output, test_details)
        return report
    if report["tests_passed"] != report["expected_tests"]:
        report["failure_stage"] = "runtime"
        report["runtime_status"] = "failed"
        report["status"] = "failed_runtime"
        report["error"] = (f"expected {report['expected_tests']} runtime tests, "
                            f"observed {report['tests_passed']}")
        return report
    expected_sdk_records = 10 if probe_name == "asan-ubsan" else 1
    expected_control_records = 0 if probe_name == "asan-ubsan" else 2
    if (len(sdk_records) != expected_sdk_records or
            sum(record.get("identity", {}).get("sanitizer") == cache_mode
                for record in sdk_records) != expected_sdk_records or
            len(control_records) != expected_control_records or
            len(state_hostile_records) != (1 if probe_name == "asan-ubsan" else 0)):
        report["failure_stage"] = "runtime"
        report["runtime_status"] = "failed"
        report["status"] = "failed_runtime"
        report["error"] = "sanitizer CTest lane omitted one or more exact positive SDK identity records"
        return report
    if any(record.get("outcome") != "pass" or record.get("cases", 0) < 1 or
           record.get("assertions", 0) < 1 or
           record.get("identity", {}).get("sanitizer") != cache_mode
           for record in log_records):
        report["failure_stage"] = "runtime"
        report["runtime_status"] = "failed"
        report["status"] = "failed_runtime"
        report["error"] = "an SDK suite result was not a passing identity record"
        return report
    if state_hostile_records and any(
            row.get("outcome") != "pass" or row.get("cases", 0) < 1 or
            row.get("assertions", 0) < 1 for row in state_hostile_records):
        report["failure_stage"] = "runtime"
        report["runtime_status"] = "failed"
        report["status"] = "failed_runtime"
        report["error"] = "state hostile sanitizer result was not a positive assertion record"
        return report
    report["status"] = "passed"
    report["runtime_status"] = "passed"
    return report


def run_sanitizer_matrix() -> int:
    overall = 0
    reports = []
    for lane in SANITIZER_LANES:
        report = sanitizer_lane(*lane)
        reports.append(report)
        report_path = Path(__file__).resolve().parents[2] / "build" / lane[0] / \
                      "sanitizer-control" / "report.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(f"SANITIZER_LANE {json.dumps(report, sort_keys=True)}")
        if report["status"] not in {"passed", "unsupported"}:
            overall = 1
    for mode in ("ADDRESS_UNDEFINED", "THREAD"):
        if run_installed_sanitizers(mode) != 0:
            overall = 1
    print(f"SANITIZER_MATRIX platform={platform.system()} {platform.release()} "
          f"{platform.machine()} memory=recorded-per-lane")
    return overall


def diagnostic_records(runner: str, result_dir: Path) -> int:
    expected_by_scenario = {
        "a": {"arithmetic": 10, "initialized": 0x1237},
        "b": {"arithmetic": 16, "initialized": 0x2348},
    }
    total_processes = 0
    for scenario, expected in expected_by_scenario.items():
        records: list[dict[str, Any]] = []
        for process_number in (1, 2):
            command = [runner]
            if scenario == "b":
                command.append("--scenario-b")
            try:
                child = run_child(command, timeout=10.0)
            except subprocess.TimeoutExpired as error:
                return fail(f"runner scenario {scenario} timed out", str(error.stdout or ""))
            except OSError as error:
                return fail(f"cannot execute runner scenario {scenario}: {error}")
            output = child.stdout + child.stderr
            lines = [line[len("SDK_DIAGNOSTIC "):] for line in output.splitlines()
                     if line.startswith("SDK_DIAGNOSTIC ")]
            if child.returncode != 0 or len(lines) != 1:
                return fail(f"runner scenario {scenario} process {process_number} failed",
                            output)
            try:
                record = json.loads(lines[0])
            except json.JSONDecodeError as error:
                return fail(f"runner emitted malformed JSON: {error}", output)
            observed = record.get("observed", {})
            if (record.get("outcome") != "pass" or record.get("assertions", 0) <= 0 or
                    observed.get("arithmetic") != expected["arithmetic"] or
                    observed.get("initialized") != expected["initialized"] or
                    observed.get("bss") != 1 or observed.get("cycles") != 172 or
                    observed.get("instructions") != 12 or observed.get("pc") != 302 or
                    observed.get("reason") != 1):
                return fail(f"runner scenario {scenario} did not report named progress/results",
                            output)
            result_path = result_dir / f"runner-{scenario}-process-{process_number}.json"
            result_path.write_text(json.dumps(record, sort_keys=True) + "\n",
                                   encoding="utf-8")
            records.append(record)
            total_processes += 1
        if records[0] != records[1]:
            return fail(f"independent runner scenario {scenario} results differ")
    print(f"PASS: independent_runner_processes={total_processes} "
          "distinct_result_paths=4 scenarios=2")
    return 0


def main(arguments: list[str]) -> int:
    if (len(arguments) == 4 and arguments[1] == "--installed-sanitizers" and
            arguments[2] == "--mode"):
        return run_installed_sanitizers(arguments[3])
    if len(arguments) == 2 and arguments[1] == "--sanitizers":
        return run_sanitizer_matrix()
    if len(arguments) in (3, 4) and arguments[1] == "--isolation":
        self_control = supervisor_self_controls()
        try:
            timeout_seconds = 30.0 if len(arguments) == 3 else float(arguments[3])
        except ValueError:
            return fail("isolation timeout must be a positive number of seconds")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0.0:
            return fail("isolation timeout must be a positive number of seconds")
        return self_control if self_control != 0 else run_isolation_matrix(
            arguments[2], timeout_seconds)
    if len(arguments) == 3 and arguments[1] == "--cold":
        return run_cold_processes(arguments[2])
    if len(arguments) != 4 or arguments[1] != "--controls":
        return fail("usage: controls.py --controls SDK_DIAGNOSTIC PUBLIC_RUNNER | "
                    "--isolation SDK_DIAGNOSTIC [TIMEOUT_SECONDS] | "
                    "--cold SDK_DIAGNOSTIC | --sanitizers | "
                    "--installed-sanitizers --mode ADDRESS_UNDEFINED|THREAD")
    self_control = supervisor_self_controls()
    if self_control != 0:
        return self_control
    sdk_status = run_control_matrix(arguments[2])
    if sdk_status != 0:
        return sdk_status
    with tempfile.TemporaryDirectory(prefix="glueyneo-sdk-controls-") as directory:
        return diagnostic_records(arguments[3], Path(directory))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
