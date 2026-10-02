#!/usr/bin/env python3
"""Require an intentionally wrong address-error cycle expectation to fail exactly once."""

import re
import subprocess
import sys


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        print("FAIL: usage: negative_timing.py PATH_TO_OWNED_TIMING", file=sys.stderr)
        return 1
    try:
        child = subprocess.run(
            [arguments[1], "--mutate-cycle"],
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
    exact = "address_error_wrong_cycle_expectation:FAIL: Expected 49 Was 50"
    if (child.returncode != 1 or exact not in output or
            re.search(r"(?m)^1 Tests 1 Failures 0 Ignored\s*$", output) is None or
            output.count(":FAIL:") != 1 or
            "Unity denominator: expected=1 observed=1" not in output):
        print("FAIL: timing mutation was not the one exact expected cycle assertion", file=sys.stderr)
        print(output, file=sys.stderr)
        return 1
    print("PASS: wrong address-error cycle expectation produced one exact assertion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
