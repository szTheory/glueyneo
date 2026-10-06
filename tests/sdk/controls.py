#!/usr/bin/env python3
"""Supervise exact SDK negative controls and independent public runner results."""

from __future__ import annotations

import json
import os
import platform
import re
import signal
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


def run_isolation_matrix(executable: str) -> int:
    try:
        normal = run_child([executable, "isolation"], timeout=30.0)
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
     "^sdk_(diagnostic|lifecycle|media|faults|run|mutation_media|mutation_sequence|mutation_minimizer)$"),
    ("sdk-tsan", "tsan", "THREAD", "-fsanitize=thread", "^sdk_(isolation|cold)$"),
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
               timeout: float = 600.0) -> tuple[int, float, int | None, str]:
    start = time.perf_counter()
    peak_rss: int | None = None
    with log_path.open("w", encoding="utf-8") as log_file:
        try:
            child = subprocess.Popen(command, stdout=log_file,
                                     stderr=subprocess.STDOUT, text=True,
                                     start_new_session=(os.name == "posix"))
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
    if any("-fsanitize" in path.read_text(encoding="utf-8", errors="replace")
           for path in export_files):
        return False, "sanitizer flags leaked into the exported consumer target"
    return True, (f"PRIVATE compile/link flags and clean consumer export verified "
                  f"({len(relevant)} relevant compile entries)")


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
        "expected_tests": 8 if probe_name == "asan-ubsan" else 2,
        "tests_passed": 0,
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
        if "SDK_SANITIZER_UNSUPPORTED:" in configure_output:
            report["status"] = "unsupported"
            report["configure_status"] = "unsupported"
            report["unsupported_reason"] = configure_output.split(
                "SDK_SANITIZER_UNSUPPORTED:", 1)[1].strip().splitlines()[0]
        else:
            report["error"] = "configure failed without an explicit unsupported marker"
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
        report["error"] = "sanitized build failed"
        report["build_log_tail"] = build_output.splitlines()[-40:]
        return report

    scoped, scoped_message = verify_target_scoped_flags(build_dir, sanitizer_flag, cache_mode)
    report["target_scoped_flags"] = scoped_message
    if not scoped:
        report["error"] = scoped_message
        return report

    executable = build_dir / "sdk_mutation"
    startup_status, startup_output = execute(
        "startup", [str(executable), "--startup-probe", probe_name], timeout=30.0)
    startup_records = records_from_log(startup_output, "SANITIZER_STARTUP ")
    if startup_status != 0:
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
        report["startup_log_tail"] = startup_output.splitlines()[-40:]
        return report
    report["startup"] = startup_records[0]
    report["startup_status"] = "passed"
    compiler_identity = startup_records[0].get("compiler", "unknown")
    compiler_id, separator, compiler_version = compiler_identity.partition(" ")
    report["compiler"]["id"] = compiler_id
    report["compiler"]["version"] = compiler_version if separator else "unknown"
    report["status"] = "startup_passed"

    ctest_status, ctest_output = execute(
        "runtime", ["ctest", "--preset", preset, "-R", labels,
                    "--output-on-failure", "--no-tests=error"],
        sample_rss=True, timeout=900.0)
    last_test_log = build_dir / "Testing" / "Temporary" / "LastTest.log"
    test_details = (last_test_log.read_text(encoding="utf-8", errors="replace")
                    if last_test_log.exists() else "")
    ctest_log = ctest_output + "\n" + test_details
    log_records = records_from_log(ctest_log, "SDK_RESULT ")
    if probe_name == "tsan":
        log_records = records_from_log(ctest_log, "SDK_CONTROL_RESULT ")
    summary_matches = re.findall(r"100% tests passed out of (\d+)",
                                 ctest_log)
    if ctest_status == 0 and summary_matches:
        report["tests_passed"] = int(summary_matches[-1])
    report["sdk_assertions"] = sum(
        record.get("assertions", 0) for record in log_records
        if isinstance(record.get("assertions"), int))
    if ctest_status != 0:
        report["runtime_status"] = "failed"
        report["status"] = "failed_runtime"
        report["error"] = f"runtime CTest suite exited {ctest_status}"
        report["runtime_log_tail"] = ctest_log.splitlines()[-60:]
        return report
    if report["tests_passed"] != report["expected_tests"]:
        report["runtime_status"] = "failed"
        report["status"] = "failed_runtime"
        report["error"] = (f"expected {report['expected_tests']} runtime tests, "
                            f"observed {report['tests_passed']}")
        return report
    if len(log_records) != (7 if probe_name == "asan-ubsan" else 2):
        report["runtime_status"] = "failed"
        report["status"] = "failed_runtime"
        report["error"] = f"expected SDK identity records, observed {len(log_records)}"
        return report
    if any(record.get("outcome") != "pass" or record.get("cases", 0) < 1 or
           record.get("assertions", 0) < 1 or
           record.get("identity", {}).get("sanitizer") != cache_mode
           for record in log_records):
        report["runtime_status"] = "failed"
        report["status"] = "failed_runtime"
        report["error"] = "an SDK suite result was not a passing identity record"
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
    if len(arguments) == 2 and arguments[1] == "--sanitizers":
        return run_sanitizer_matrix()
    if len(arguments) == 3 and arguments[1] == "--isolation":
        self_control = supervisor_self_controls()
        return self_control if self_control != 0 else run_isolation_matrix(arguments[2])
    if len(arguments) == 3 and arguments[1] == "--cold":
        return run_cold_processes(arguments[2])
    if len(arguments) != 4 or arguments[1] != "--controls":
        return fail("usage: controls.py --controls SDK_DIAGNOSTIC PUBLIC_RUNNER | "
                    "--isolation SDK_DIAGNOSTIC | --cold SDK_DIAGNOSTIC | --sanitizers")
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
