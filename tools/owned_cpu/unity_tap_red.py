#!/usr/bin/env python3
"""Capture a single-failure Unity run and translate its complete report to TAP."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


TEST_ROW = re.compile(r"^.+?:\d+:([A-Za-z0-9_]+):(PASS|FAIL)(?::(.*))?$")
SUMMARY = re.compile(r"^(\d+) Tests (\d+) Failures (\d+) Ignored\s*$", re.M)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="exact Unity test function name")
    parser.add_argument("--expected", required=True, help="planned behavior")
    parser.add_argument("--semantic-assessment", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="test executable and optional arguments, after --")
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a Unity test command is required after --")

    run = subprocess.run(command, text=True, capture_output=True)
    raw = run.stdout + (run.stderr if run.stderr else "")
    summary = SUMMARY.search(run.stdout)
    rows = []
    failures = []
    for line in run.stdout.splitlines():
        match = TEST_ROW.match(line)
        if match:
            name, status, detail = match.groups()
            rows.append((name, status))
            if status == "FAIL":
                failures.append((name, (detail or "").strip()))

    if run.returncode != 1 or summary is None:
        raise SystemExit("Unity command did not produce the expected failing-test report")
    total, failed, ignored = map(int, summary.groups())
    if total != len(rows) or failed != len(failures) or ignored != 0:
        raise SystemExit("Unity summary does not match its complete test rows")
    if len(failures) != 1 or failures[0][0] != args.target:
        raise SystemExit("Unity report does not contain exactly the named target failure")

    tap = ["TAP version 13", f"1..{total}"]
    for number, (name, status) in enumerate(rows, 1):
        tap.append(f"{'ok' if status == 'PASS' else 'not ok'} {number} - {name}")
    tap_output = "\n".join(tap) + "\n"
    record = {
        "command": " ".join(command),
        "exitCode": run.returncode,
        "output": tap_output,
        "raw_output": raw,
        "targetTest": args.target,
        "targetFile": "tests/owned_cpu/test_semantics.c",
        "expected": args.expected,
        "actual": failures[0][1],
        "semanticAssessment": args.semantic_assessment,
        "reportAdapter": "tools/owned_cpu/unity_tap_red.py",
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(record, indent=2) + "\n")
    sys.stdout.write(tap_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
