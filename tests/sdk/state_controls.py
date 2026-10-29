#!/usr/bin/env python3
"""Require each deliberate state-section omission to fail its named oracle."""

import json
import re
import subprocess
import sys


EXPECTED = {
    "cpu": "sdk.state.omission.cpu.guest-output",
    "memory": "sdk.state.omission.memory.raw-video",
    "board": "sdk.state.omission.board.frame-time-carry",
    "sound": "sdk.state.omission.sound.delivered-pcm",
    "ym2610": "sdk.state.omission.ym2610.delivered-pcm",
}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: state_controls.py <sdk_state_test>", file=sys.stderr)
        return 2
    executable = sys.argv[1]
    for selector, assertion in EXPECTED.items():
        try:
            result = subprocess.run(
                [executable, "control-" + selector],
                check=False,
                capture_output=True,
                text=True,
                timeout=55,
            )
        except subprocess.TimeoutExpired:
            print(f"{selector}: timed out", file=sys.stderr)
            return 1
        output = result.stdout + result.stderr
        expected_case = f"# CASE {assertion}"
        expected_assert = f"# ASSERT {assertion} expected=1 observed=0"
        result_rows = re.findall(r"^SDK_RESULT (.+)$", output, re.MULTILINE)
        if result.returncode != 1 or expected_case not in output or \
                expected_assert not in output or len(result_rows) != 1:
            print(f"{selector}: wrong child outcome (exit={result.returncode})",
                  file=sys.stderr)
            print(output, file=sys.stderr)
            return 1
        try:
            row = json.loads(result_rows[0])
        except json.JSONDecodeError:
            print(f"{selector}: malformed SDK_RESULT", file=sys.stderr)
            print(output, file=sys.stderr)
            return 1
        assertions = re.findall(
            r"^# ASSERT (\S+) expected=(\S+) observed=(\S+)$",
            output,
            re.MULTILINE,
        )
        failures = [item for item in assertions if item[1] != item[2]]
        if row.get("suite") != "sdk-state" or row.get("outcome") != "fail" or \
                row.get("cases") != 1 or row.get("assertions") != len(assertions) or \
                len(failures) != 1 or failures[0] != (assertion, "1", "0"):
            print(f"{selector}: unrelated or empty assertion failure",
                  file=sys.stderr)
            print(output, file=sys.stderr)
            return 1
        unity_failures = re.findall(r"^\s*\d+\s+Tests\s+(\d+)\s+Failures\b",
                                    output, re.MULTILINE)
        if not unity_failures or unity_failures[-1] != "1" or \
                re.search(r"AddressSanitizer|UndefinedBehaviorSanitizer|ThreadSanitizer|"
                          r"runtime error:|Segmentation fault|AddressSanitizer ERROR",
                          output, re.IGNORECASE):
            print(f"{selector}: crash, sanitizer diagnostic or wrong Unity count",
                  file=sys.stderr)
            print(output, file=sys.stderr)
            return 1
        print(f"{selector}: expected observation assertion failed")
    try:
        unknown = subprocess.run(
            [executable, "control-not-registered"],
            check=False,
            capture_output=True,
            text=True,
            timeout=55,
        )
    except subprocess.TimeoutExpired:
        print("unknown selector: timed out", file=sys.stderr)
        return 1
    unknown_output = unknown.stdout + unknown.stderr
    if unknown.returncode == 0 or "unknown omission selector" not in unknown_output or \
            re.search(r"AddressSanitizer|UndefinedBehaviorSanitizer|ThreadSanitizer|"
                      r"runtime error:|Segmentation fault|AddressSanitizer ERROR",
                      unknown_output, re.IGNORECASE):
        print("unknown selector was not rejected cleanly", file=sys.stderr)
        print(unknown_output, file=sys.stderr)
        return 1
    print("unknown selector: rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
