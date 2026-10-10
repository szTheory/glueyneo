#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail when the runtime library holds writable or zero-initialized storage.

`libretro_callback_test` links two runtime copies (the core's private copy and
the public library). They share no mutable global state only if neither copy
has any: this audit lists every object symbol in writable data or
zero-initialized sections of one library and fails if there is one. There is
no allowlist; a table that is never written is made `const`.

Mach-O (`nm -m`) selects sections __DATA,__data, __DATA,__bss,
__DATA,__common and the thread-local __DATA,__thread_data, __DATA,__thread_bss
and __DATA,__thread_vars. Other POSIX hosts (`nm`) select symbol types D, d,
B, b, G, g, V and v, ELF common C and c, and small-data S and s.

The audit cannot pass without inspecting symbols: output in which no line
parses as a symbol fails with `no symbols parsed`. Windows, or an empty `--nm`,
reports `unsupported` (CTest skip code 77) rather than passing.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

SKIP = 77
DARWIN_SECTIONS = {
    "__DATA,__data", "__DATA,__bss", "__DATA,__common",
    "__DATA,__thread_data", "__DATA,__thread_bss", "__DATA,__thread_vars",
}
MACHO_LINE = re.compile(r"^\s*[0-9A-Fa-f]*\s*\(([^)]*)\)\s+(?:non-external|external)\s+(?:\[[^\]]*\]\s+)?(\S+)")
ELF_LINE = re.compile(r"^\s*(?:[0-9A-Fa-f]+\s+)?([A-Za-z])\s+(\S+)\s*$")
ELF_WRITABLE = set("DdBbGgVvCcSs")


def parse_symbols(output: str, platform: str) -> tuple[list[str], int]:
    """Return (writable-storage symbol names, number of lines that parsed as any symbol)."""
    found: list[str] = []
    parsed = 0
    for line in output.splitlines():
        if platform == "darwin":
            match = MACHO_LINE.match(line)
            if match:
                parsed += 1
                if match.group(1).replace(" ", "") in DARWIN_SECTIONS:
                    found.append(match.group(2))
        else:
            match = ELF_LINE.match(line)
            if match:
                parsed += 1
                if match.group(1) in ELF_WRITABLE:
                    found.append(match.group(2))
    return found, parsed


def writable_symbols(output: str, platform: str) -> list[str]:
    """Return the names of writable-storage symbols in `nm` output."""
    return parse_symbols(output, platform)[0]


def host_platform() -> str:
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform in {"win32", "cygwin", "msys"}:
        return "windows"
    return "linux"


def run_nm(nm: str, library: str, platform: str) -> str:
    command = [nm, "-m", library] if platform == "darwin" else [nm, library]
    environment = {"PATH": os.environ.get("PATH", ""), "LC_ALL": "C"}
    result = subprocess.run(command, capture_output=True, text=True, timeout=60,
                            env=environment, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{nm} failed with status {result.returncode}")
    return result.stdout


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nm", default="nm")
    parser.add_argument("library")
    options = parser.parse_args(arguments)
    platform = host_platform()
    if platform == "windows":
        print("unsupported: writable-storage audit needs nm")
        return SKIP
    if not options.nm.strip():
        print("unsupported: no nm configured")
        return SKIP
    name = Path(options.library).name
    try:
        output = run_nm(options.nm, options.library, platform)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: cannot inspect {name}: {type(error).__name__}", file=sys.stderr)
        return 1
    symbols, parsed = parse_symbols(output, platform)
    if parsed == 0:
        print(f"FAIL: no symbols parsed from {name}", file=sys.stderr)
        return 1
    if symbols:
        print(f"FAIL: writable runtime storage: {', '.join(sorted(set(symbols)))}", file=sys.stderr)
        return 1
    print(f"PASS: no writable runtime storage in {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
