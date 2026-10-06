#!/usr/bin/env python3
"""Deterministically reduce a binary input while retaining one failure ID."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable


FAILURE = re.compile(r"(?m)^SDK_MUTATION_FAILURE id=([A-Za-z0-9_.-]+)\b")
MAX_INPUT_BYTES = 4096
RUN_TIMEOUT_SECONDS = 10.0


def failure_id(output: str) -> str | None:
    matches = FAILURE.findall(output)
    return matches[0] if len(matches) == 1 else None


def delta_delete(data: bytes, reproduces: Callable[[bytes], bool]) -> bytes:
    """Remove contiguous chunks in a stable order while preserving the oracle."""
    current = data
    granularity = 2
    while len(current) >= 2:
        chunk_size = math.ceil(len(current) / granularity)
        reduced = False
        for start in range(0, len(current), chunk_size):
            candidate = current[:start] + current[start + chunk_size:]
            if reproduces(candidate):
                current = candidate
                granularity = max(2, granularity - 1)
                reduced = True
                break
        if reduced:
            continue
        if granularity >= len(current):
            break
        granularity = min(len(current), granularity * 2)
    return current


def run_oracle(command: list[str], data: bytes, expected_id: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="glueyneo-minimize-") as directory:
        input_path = Path(directory) / "input.bin"
        input_path.write_bytes(data)
        expanded = [part.replace("{input}", str(input_path)) for part in command]
        if not any("{input}" in part for part in command):
            expanded.append(str(input_path))
        try:
            completed = subprocess.run(
                expanded, capture_output=True, text=True, errors="replace",
                timeout=RUN_TIMEOUT_SECONDS, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, f"oracle could not reproduce input: {error}"
        output = completed.stdout + completed.stderr
        return (completed.returncode == 1 and failure_id(output) == expected_id,
                output)


def self_test() -> int:
    expected = "sdk.synthetic.required-byte-pair"
    marker = b"\xde\xad"
    original = b"prefix\x00noise\xde\xadmore-noise\xff"

    def oracle(candidate: bytes) -> str:
        if marker in candidate:
            return f"SDK_MUTATION_FAILURE id={expected} seed=1 iteration=0\n"
        return "PASS: synthetic input does not contain the two-byte trigger\n"

    def reproduces(candidate: bytes) -> bool:
        return failure_id(oracle(candidate)) == expected

    reduced = delta_delete(original, reproduces)
    observed_id = failure_id(oracle(reduced))
    if reduced != marker or observed_id != expected:
        print("FAIL: minimizer self-test lost or changed its exact failure ID",
              file=sys.stderr)
        return 1
    print(f"PASS: minimizer self-test preserved={observed_id} "
          f"original_bytes={len(original)} minimized_bytes={len(reduced)}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--self-test", action="store_true")
    result.add_argument("--input", type=Path)
    result.add_argument("--failure-id")
    result.add_argument("--output", type=Path)
    result.add_argument("--seed", default="unrecorded")
    result.add_argument("command", nargs=argparse.REMAINDER)
    return result


def main(argv: list[str]) -> int:
    arguments = parser().parse_args(argv)
    if arguments.self_test:
        return self_test()
    if (arguments.input is None or arguments.failure_id is None or
            arguments.output is None or not arguments.command):
        print("FAIL: require --input, --failure-id, --output, and an oracle command",
              file=sys.stderr)
        return 2
    command = list(arguments.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("FAIL: oracle command is empty", file=sys.stderr)
        return 2
    try:
        original = arguments.input.read_bytes()
    except OSError as error:
        print(f"FAIL: cannot read original input: {error}", file=sys.stderr)
        return 2
    if len(original) > MAX_INPUT_BYTES:
        print(f"FAIL: input exceeds {MAX_INPUT_BYTES}-byte cap", file=sys.stderr)
        return 2
    reproduced, original_output = run_oracle(command, original, arguments.failure_id)
    if not reproduced:
        print("FAIL: original input did not reproduce the exact named failure",
              file=sys.stderr)
        print(original_output, file=sys.stderr)
        return 1

    def preserves(candidate: bytes) -> bool:
        accepted, _ = run_oracle(command, candidate, arguments.failure_id)
        return accepted

    minimized = delta_delete(original, preserves)
    if not preserves(minimized):
        print("FAIL: minimized input changed or lost the failure ID", file=sys.stderr)
        return 1
    original_path = arguments.output.with_name(arguments.output.name + ".original")
    metadata_path = arguments.output.with_name(arguments.output.name + ".json")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_bytes(original)
    arguments.output.write_bytes(minimized)
    metadata = {
        "schema_version": 1,
        "failure_id": arguments.failure_id,
        "seed": arguments.seed,
        "command": command,
        "input_limit_bytes": MAX_INPUT_BYTES,
        "original_bytes": len(original),
        "minimized_bytes": len(minimized),
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "minimized_sha256": hashlib.sha256(minimized).hexdigest(),
        "replayed_failure_id": failure_id(run_oracle(command, minimized,
                                                       arguments.failure_id)[1]),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n",
                             encoding="utf-8")
    print(f"PASS: minimized exact_failure_id={arguments.failure_id} "
          f"original={len(original)} bytes minimized={len(minimized)} bytes "
          f"saved={arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
