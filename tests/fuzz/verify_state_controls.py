#!/usr/bin/env python3
"""Run the hostile state matrix and prove each nested validator control."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


SANITIZER_MARKERS = (
    "AddressSanitizer", "UndefinedBehaviorSanitizer", "ThreadSanitizer",
    "runtime error:", "Sanitizer: ",
)
RESULT = re.compile(r"(?m)^SDK_RESULT (\{.*\})$")
RECIPE_CASE = re.compile(r"(?m)^# CASE (state\.[A-Za-z0-9_.-]+)$")


def run(executable: str, suite: str) -> tuple[int | None, str]:
    try:
        result = subprocess.run(
            [executable, suite], capture_output=True, text=True,
            errors="replace", timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"could not run {suite}: {error}"
    return result.returncode, result.stdout + result.stderr


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify_state_controls.py <sdk_state_mutation>",
              file=sys.stderr)
        return 2
    executable = sys.argv[1]
    status, output = run(executable, "hostile")
    if status != 0 or any(marker in output for marker in SANITIZER_MARKERS):
        print("FAIL: hostile state matrix did not pass cleanly", file=sys.stderr)
        print(output, file=sys.stderr)
        return 1
    matches = RESULT.findall(output)
    if len(matches) != 1:
        print("FAIL: hostile matrix emitted no unique SDK_RESULT", file=sys.stderr)
        print(output, file=sys.stderr)
        return 1
    result = json.loads(matches[0])
    if (result.get("outcome") != "pass" or result.get("cases", 0) <= 0 or
            result.get("assertions", 0) <= 0):
        print("FAIL: hostile matrix has zero cases/assertions or did not pass",
              file=sys.stderr)
        print(output, file=sys.stderr)
        return 1
    corpus_path = Path(__file__).resolve().parents[2] / "tests" / "fuzz" / \
        "state_regressions.json"
    try:
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAIL: cannot load synthetic state corpus: {error}",
              file=sys.stderr)
        return 1
    expected_recipes = {recipe["id"] for recipe in corpus.get("recipes", [])}
    observed_recipes = set(RECIPE_CASE.findall(output))
    if (len(expected_recipes) < 20 or expected_recipes != observed_recipes or
            len(RECIPE_CASE.findall(output)) != len(expected_recipes)):
        print("FAIL: emitted mutation cases do not match the registered corpus",
              file=sys.stderr)
        print(f"expected={sorted(expected_recipes)}", file=sys.stderr)
        print(f"observed={sorted(observed_recipes)}", file=sys.stderr)
        return 1

    validators = (
        "z80", "ym", "ym-irq-relation", "ym-timer-relation",
        "ym-busy-relation",
    )
    for validator in validators:
        suite = f"negative-control-{validator}"
        status, output = run(executable, suite)
        marker = f"SDK_STATE_NEGATIVE_CONTROL accepted_disabled_validator={validator}"
        expected_assertion = (
            "sdk.state.hostile.negative-control.expected-rejection"
        )
        if (status != 1 or marker not in output or expected_assertion not in output or
                any(item in output for item in SANITIZER_MARKERS)):
            print(f"FAIL: {validator} validator negative control did not trip "
                  "its named import assertion", file=sys.stderr)
            print(output, file=sys.stderr)
            return 1
    print("PASS: hostile matrix plus five validator disabled controls")
    print("STATE_HOSTILE_RESULT " + json.dumps({
        "outcome": "pass", "cases": int(result["cases"]) + len(validators),
        "assertions": int(result["assertions"]) + len(validators),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
