#!/usr/bin/env python3
"""Supervise exact SDK negative controls and independent public runner results."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
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
    print("PASS: cold_processes=8 concurrent_pairs=8 owners=16 "
          "candidate_failure_paths=16 reset_recoveries=16 teardown_leaks=0")
    return 0


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
    if len(arguments) == 3 and arguments[1] == "--isolation":
        self_control = supervisor_self_controls()
        return self_control if self_control != 0 else run_isolation_matrix(arguments[2])
    if len(arguments) == 3 and arguments[1] == "--cold":
        return run_cold_processes(arguments[2])
    if len(arguments) != 4 or arguments[1] != "--controls":
        return fail("usage: controls.py --controls SDK_DIAGNOSTIC PUBLIC_RUNNER | "
                    "--isolation SDK_DIAGNOSTIC | --cold SDK_DIAGNOSTIC")
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
