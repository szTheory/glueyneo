#!/usr/bin/env python3
"""Require an intentionally wrong address-error cycle expectation to fail exactly once."""

import re
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch


def self_test():
    class Controls(unittest.TestCase):
        def test_exact_unsupported_failure_is_required(self):
            output = ("canonical_unsupported_wrong_status_expectation:FAIL: Expected 8 Was 6\n"
                      "1 Tests 1 Failures 0 Ignored\nUnity denominator: expected=1 observed=1\n")
            child = subprocess.CompletedProcess([], 1, output, "")
            with patch.object(subprocess, "run", return_value=child):
                self.assertEqual(0, main(["wrapper", "--unsupported", "binary"]))

        def test_unrelated_failures_crashes_and_empty_pass_cannot_qualify(self):
            for code, output in ((-11, "crash"), (0, "PASS"), (1, "unrelated:FAIL"),
                                 (1, "0 Tests 0 Failures 0 Ignored")):
                with self.subTest(code=code, output=output):
                    with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], code, output, "")):
                        self.assertEqual(1, main(["wrapper", "--unsupported", "binary"]))
            with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("binary", 20)):
                self.assertEqual(1, main(["wrapper", "--unsupported", "binary"]))
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Controls)
    return 0 if unittest.TextTestRunner().run(suite).wasSuccessful() else 1


def main(arguments: list[str]) -> int:
    unsupported = len(arguments) == 3 and arguments[1] == "--unsupported"
    if len(arguments) != 2 and not unsupported:
        print("FAIL: usage: negative_timing.py [--unsupported] PATH_TO_OWNED_TIMING", file=sys.stderr)
        return 1
    mode = "--mutate-unsupported" if unsupported else "--mutate-cycle"
    exact = "address_error_wrong_cycle_expectation:FAIL: Expected 49 Was 50"
    if unsupported:
        # The deliberate harness expects BUDGET; cpu.h owns numeric enum values.
        header = (Path(__file__).resolve().parents[2] / "experiments/owned_cpu/cpu.h").read_text()
        enum = re.search(r"typedef enum \{(.*?)\} owned_cpu_status;", header, re.S)
        if enum is None:
            print("FAIL: private status enum missing", file=sys.stderr)
            return 1
        names = re.findall(r"\bOWNED_CPU_[A-Z_]+\b", enum.group(1))
        exact = ("canonical_unsupported_wrong_status_expectation:FAIL: Expected " +
                 str(names.index("OWNED_CPU_BUDGET")) + " Was " +
                 str(names.index("OWNED_CPU_UNSUPPORTED_OPCODE")))
    try:
        child = subprocess.run(
            [arguments[-1], mode],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: mutated timing case did not finish normally: {error}", file=sys.stderr)
        return 1
    output = child.stdout + child.stderr
    if (child.returncode != 1 or exact not in output or
            re.search(r"(?m)^1 Tests 1 Failures 0 Ignored\s*$", output) is None or
            output.count(":FAIL:") != 1 or
            "Unity denominator: expected=1 observed=1" not in output):
        print("FAIL: timing mutation was not the one exact expected assertion", file=sys.stderr)
        print(output, file=sys.stderr)
        return 1
    print("PASS: " + ("wrong canonical unsupported status" if unsupported else "wrong address-error cycle") +
          " expectation produced one exact assertion")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test() if sys.argv[1:] == ["--self-test"] else main(sys.argv))
