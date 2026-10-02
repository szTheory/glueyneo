#!/usr/bin/env python3
"""Run bounded concurrent first-use cases in independent fresh processes."""

import subprocess
import sys


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        print("FAIL: usage: cold.py PATH_TO_OWNED_CPU_COLD", file=sys.stderr)
        return 1
    executable = arguments[1]
    cases = 16
    for case in range(cases):
        try:
            child = subprocess.run(
                [executable], capture_output=True, text=True, errors="replace",
                timeout=10, check=False
            )
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            print(f"FAIL: cold process case {case + 1}/{cases} timed out", file=sys.stderr)
            print(output, file=sys.stderr)
            return 1
        except OSError as error:
            print(f"FAIL: cannot execute cold fixture: {error}", file=sys.stderr)
            return 1
        output = child.stdout + child.stderr
        if child.returncode != 0 or "1 Tests 0 Failures 0 Ignored" not in output:
            print(f"FAIL: cold process case {case + 1}/{cases} did not pass", file=sys.stderr)
            print(output, file=sys.stderr)
            return 1
    print(f"PASS: cold_process_cases={cases} fresh_processes={cases} concurrent_instances=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
