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
    if len(arguments) == 3 and arguments[1] == "--isolation":
        return swapped_owner_control(arguments[2])
    if len(arguments) == 4 and arguments[2] == "--state":
        status = diagnostic_control(arguments[1])
        if status != 0:
            return status
        return state_omission_controls(arguments[3])
    if len(arguments) != 2:
        return fail("usage: negative.py PATH_TO_OWNED_DIAGNOSTIC [--state PATH_TO_OWNED_STATE]")
    return diagnostic_control(arguments[1])


def diagnostic_control(executable: str) -> int:
    try:
        child = subprocess.run(
            [executable, "--mutate"],
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


def state_omission_controls(executable: str) -> int:
    controls = (
        ("--omit-irq7", "Expected 1 Was 0:state omission pending level7 changed D1"),
    )
    for option, expected_assertion in controls:
        try:
            child = subprocess.run(
                [executable, option], capture_output=True, text=True,
                errors="replace", timeout=20, check=False
            )
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return fail(f"state omission control {option} timed out", output)
        except OSError as error:
            return fail(f"cannot execute state omission control {option}: {error}")

        output = child.stdout + child.stderr
        summary = re.search(r"(?m)^1 Tests 1 Failures 0 Ignored\s*$", output)
        if (child.returncode != 1 or expected_assertion not in output or
                summary is None or len(re.findall(r":FAIL:", output)) != 1):
            return fail(f"state omission {option} did not produce its one named assertion", output)
        print(f"PASS: {option} was caught by its exact continuation assertion")

    option = "--omit-instruction-counter"
    try:
        child = subprocess.run(
            [executable, option], capture_output=True, text=True,
            errors="replace", timeout=20, check=False
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return fail(f"state counter control {option} timed out", output)
    except OSError as error:
        return fail(f"cannot execute state counter control {option}: {error}")

    output = child.stdout + child.stderr
    summary = re.search(r"(?m)^1 Tests 0 Failures 0 Ignored\s*$", output)
    counter_rejected = (
        "state_instruction_counter_mismatch_rejected=1 atomic_destination_and_bus=1" in output
    )
    if (child.returncode != 0 or not counter_rejected or
            "Unity denominator: expected=1 observed=1" not in output or
            summary is None or re.search(r"(?m)^.*:FAIL:", output)):
        return fail(f"state counter mismatch {option} was not rejected atomically", output)
    print("PASS: instruction-counter mismatch was rejected without destination or bus mutation")
    return 0


def swapped_owner_control(executable: str) -> int:
    try:
        child = subprocess.run(
            [executable, "--swapped-owner"], capture_output=True, text=True,
            errors="replace", timeout=20, check=False
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return fail("swapped-owner control timed out", output)
    except OSError as error:
        return fail(f"cannot execute ownership control: {error}")

    output = child.stdout + child.stderr
    expected_assertion = "Expected 10 Was 16:swapped-owner guest D0"
    expected_summary = re.search(r"(?m)^2 Tests 1 Failures 0 Ignored\s*$", output)
    if (child.returncode != 1 or expected_assertion not in output or
            expected_summary is None or len(re.findall(r":FAIL:", output)) != 1):
        return fail("swapped owner was not rejected by the exact D0 assertion", output)
    print("PASS: swapped owner produced D0 16 against isolated owner D0 10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
