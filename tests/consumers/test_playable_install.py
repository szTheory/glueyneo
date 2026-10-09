#!/usr/bin/env python3
"""Check installed native and Libretro artifacts from a clean qualification build."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--consumer", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--core", type=Path)
    args = parser.parse_args()
    prefix = args.prefix.resolve()
    consumer = args.consumer.resolve()
    fixture = args.fixture.resolve()
    core = args.core.resolve() if args.core else None
    runner_candidates = sorted((prefix / "bin").glob("glueyneo-diagnostic*"))
    if len(runner_candidates) != 1:
        raise SystemExit("installed diagnostic runner is missing or ambiguous")
    installed_fixture = prefix / "share" / "glueyneo" / "diagnostic-original-a.bin"
    if not installed_fixture.is_file() or not fixture.is_file():
        raise SystemExit("installed or generated diagnostic fixture is missing")
    if sha256(installed_fixture) != sha256(fixture):
        raise SystemExit("installed fixture differs from the clean build fixture")
    check = subprocess.run([str(runner_candidates[0]), "--check-fixture", str(installed_fixture)],
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           check=False, timeout=30)
    if check.returncode:
        raise SystemExit("installed diagnostic runner rejected its fixture")
    run = subprocess.run([str(consumer), str(installed_fixture)], text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         check=False, timeout=30)
    if run.returncode or '"outcome":"pass"' not in run.stdout:
        raise SystemExit("out-of-tree installed C consumer failed its diagnostic")
    result = {
        "schema": "glueyneo.playable-install-consumer/v1",
        "status": "pass",
        "fixture_sha256": sha256(fixture),
        "installed_native_consumer": "pass",
        "installed_libretro_core": "pass" if core and core.is_file() else "unknown",
    }
    if core and core.is_file():
        result["libretro_sha256"] = sha256(core)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["installed_libretro_core"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
