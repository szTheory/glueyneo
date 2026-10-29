#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit runtime source calls, with exact provenance for admitted ymfm C++."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import re
import sys

# A provenance check must not modify its source snapshot by importing the gate.
sys.dont_write_bytecode = True


def has_host_call(text: str, names: str, *, cpp: bool) -> bool:
    # Comments are prose, not runtime behavior. Preserve string/character
    # literals while blanking comments so comment markers in a literal cannot
    # hide a real call either.
    text = _without_c_comments(text)
    if cpp:
        # Member calls are chip/callback operations, not global C host symbols.
        # Keep ::read, std::time and unqualified calls visible to the scan.
        text = re.sub(r"(?:\.|->)\s*(?:" + names + r")\s*\(",
                      "member_operation(", text)
    return re.search(r"(^|[^A-Za-z0-9_])(?:" + names + r")\s*\(", text) is not None


def _without_c_comments(text: str) -> str:
    output = list(text)
    index = 0
    quote: str | None = None
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\":
                output[index] = " "
                if index + 1 < len(text) and text[index + 1] != "\n":
                    output[index + 1] = " "
                index += 2
                continue
            if char == quote:
                quote = None
            if char != "\n":
                output[index] = " "
            index += 1
            continue
        if char in "\"'":
            quote = char
            output[index] = " "
            index += 1
            continue
        if text.startswith("//", index):
            end = text.find("\n", index)
            if end < 0:
                end = len(text)
            for position in range(index, end):
                output[position] = " "
            index = end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = len(text) if end < 0 else end + 2
            for position in range(index, end):
                if output[position] != "\n":
                    output[position] = " "
            index = end
            continue
        index += 1
    return "".join(output)


def audit(root: Path, sources: list[Path], names: str) -> None:
    spec = importlib.util.spec_from_file_location(
        "ym2610_source_gate", root / "tests/chips/check_ym2610.py")
    if spec is None or spec.loader is None:
        raise ValueError("YM2610 provenance gate unavailable")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    gate.ROOT = root
    immutable = {root / "third_party/ymfm" / name for name in gate.FILES}
    # No path-only exclusion: every invocation verifies all pinned bytes,
    # license and inventory, even if this source list contains no YM source.
    gate.source_check()
    for source in sources:
        if source in immutable:
            continue
        if has_host_call(source.read_text(encoding="utf-8"), names,
                         cpp=source.suffix == ".cpp"):
            try:
                label = source.relative_to(root).as_posix()
            except ValueError:
                # Test and consumer probes may compile isolated sources outside
                # the checkout; never print their absolute host path.
                label = source.name
            raise ValueError("Ambient host call found in runtime source: " + label)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--names", required=True)
    parser.add_argument("sources", type=Path, nargs="+")
    args = parser.parse_args()
    audit(args.root, args.sources, args.names)


if __name__ == "__main__":
    main()
