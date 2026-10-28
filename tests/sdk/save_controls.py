#!/usr/bin/env python3
"""Run positive save receipts and require the deliberate stale-clean control."""

import argparse
import json
import re
import subprocess
import sys


def fail(message, output=""):
    print(f"save receipt control failed: {message}", file=sys.stderr)
    if output:
        print(output, file=sys.stderr, end="" if output.endswith("\n") else "\n")
    return 1


def execute(runner, suite, timeout_seconds):
    try:
        return subprocess.run(
            [runner, suite], capture_output=True, text=True,
            timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired as error:
        return error
    except OSError as error:
        return error


def result_record(output):
    matches = re.findall(r"^SDK_RESULT (\{.*\})$", output, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError(f"expected one SDK_RESULT record, found {len(matches)}")
    return json.loads(matches[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["receipts"], required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if not 0.0 < args.timeout <= 300.0:
        parser.error("--timeout must be positive and no greater than 300 seconds")

    positive = execute(args.runner, "receipts", args.timeout)
    if isinstance(positive, subprocess.TimeoutExpired):
        return fail("positive receipt suite timed out")
    if isinstance(positive, OSError):
        return fail(f"could not start positive receipt suite: {positive}")
    positive_output = positive.stdout + positive.stderr
    if positive.returncode != 0:
        return fail(f"positive suite exited {positive.returncode}", positive_output)
    try:
        positive_record = result_record(positive_output)
    except (ValueError, json.JSONDecodeError) as error:
        return fail(f"positive suite has invalid SDK_RESULT: {error}", positive_output)
    if (positive_record.get("outcome") != "pass" or
            positive_record.get("cases") != 3 or
            positive_record.get("assertions", 0) <= 0):
        return fail("positive suite missed its case/assertion denominator", positive_output)

    negative = execute(args.runner, "stale-clean", args.timeout)
    if isinstance(negative, subprocess.TimeoutExpired):
        return fail("stale-clean negative control timed out")
    if isinstance(negative, OSError):
        return fail(f"could not start stale-clean negative control: {negative}")
    negative_output = negative.stdout + negative.stderr
    try:
        negative_record = result_record(negative_output)
    except (ValueError, json.JSONDecodeError) as error:
        return fail(f"negative control has invalid SDK_RESULT: {error}", negative_output)

    assertion = "# ASSERT save.pending-newer expected=1 observed=0"
    failure = "FAIL:save.pending-newer"
    failed_assertions = re.findall(r"^.*:FAIL:.*$", negative_output, re.MULTILINE)
    unity_summary = re.search(
        r"^1 Tests 1 Failures 0 Ignored\s*$", negative_output, re.MULTILINE
    )
    if (negative.returncode != 1 or
            negative_record.get("outcome") != "fail" or
            negative_record.get("cases") != 1 or
            negative_record.get("assertions") != 25 or
            negative_output.count(assertion) != 1 or
            len(failed_assertions) != 1 or failure not in failed_assertions[0] or
            unity_summary is None):
        return fail("negative control did not fail only at save.pending-newer",
                    negative_output)

    print(
        "save receipts passed: "
        f"positive cases={positive_record['cases']} "
        f"assertions={positive_record['assertions']}; "
        "negative control=save.pending-newer"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
