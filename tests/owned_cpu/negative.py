#!/usr/bin/env python3
"""Require the original guest's wrong-operand mutation to fail one exact assertion."""

import re
import subprocess
import sys


def fail(message: str, output: str = "") -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    if output:
        print(output, file=sys.stderr)
    return 1


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        return fail("usage: negative.py PATH_TO_OWNED_DIAGNOSTIC")
    try:
        child = subprocess.run(
            [arguments[1], "--mutate"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return fail("mutated guest timed out", output)
    except OSError as error:
        return fail(f"cannot execute owned diagnostic: {error}")

    output = child.stdout + child.stderr
    expected_assertion = "Expected 10 Was 11:guest arithmetic/store result"
    expected_summary = re.search(r"(?m)^1 Tests 1 Failures 0 Ignored\s*$", output)
    one_failure = len(re.findall(r":FAIL:", output)) == 1
    denominator = "Unity denominator: expected=1 observed=1" in output
    if child.returncode != 1:
        return fail(f"expected exactly one Unity assertion failure, got exit {child.returncode}", output)
    if expected_assertion not in output or expected_summary is None or not one_failure or not denominator:
        return fail("failure was not the single named 10-versus-11 guest result assertion", output)

    print("PASS: mutation changed 10 to 11; only the named guest arithmetic/store assertion failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
