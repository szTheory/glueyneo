#!/usr/bin/env python3
"""Source provenance gate for the pinned YM2610 candidate."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
REVISION = "81aec25ccbb98f4873a255f7551ac4dadac59b4a"
FILES = {
    "src/ymfm.h": "f5ab6fed63c8669abab8403e0e93132e1dad0ae4d8e4954e7836ab9e5b228405",
    "src/ymfm_adpcm.cpp": "74e5ded129ea7e532112e5b637d0a7bd4e127fd83331f1fac32011723051d4e0",
    "src/ymfm_adpcm.h": "5933691971493b853a9be443f6e6fd74f63869aa21225f66dd89fc20de20914d",
    "src/ymfm_fm.h": "1b27bfb7fa4963d7c54cb06fd9bf659450362d8ed496c6af7d487b068cac45c9",
    "src/ymfm_fm.ipp": "4fb7fe59d4494a19e9f9c7888eb644a63d86e109fdefb27a8117bf6a5f6ab4b9",
    "src/ymfm_opn.cpp": "8734c6d5a6e1bf49a08eeb33d260d39c17cd1d26f5db506e5d0d3e416913b489",
    "src/ymfm_opn.h": "1950990c3ea0c6d492a20f66a683a372a7367ef39f7830aa65b20a20d1bcbef5",
    "src/ymfm_ssg.cpp": "73a3028a77f13f3769b7705079659eb8325431a67b8164ded25e12f324f42bfd",
    "src/ymfm_ssg.h": "27966b0887fe98f2d06a96be2776c911107e2f2a13a64f9a349e1ffc19cf7584",
}


def source_check() -> dict[str, object]:
    base = ROOT / "third_party/ymfm"
    notice = (base / "NOTICE.md").read_text(encoding="utf-8")
    license_text = (base / "LICENSE").read_text(encoding="utf-8")
    if REVISION not in notice:
        raise ValueError("NOTICE.md is missing the pinned upstream revision")
    if "BSD 3-Clause License" not in license_text:
        raise ValueError("ymfm BSD-3-Clause license is missing")
    license_digest = hashlib.sha256((base / "LICENSE").read_bytes()).hexdigest()
    if license_digest != "2d2e9213c170a9866c616fa85b6da993a6724e10befc61f468ed9bfb84c4691c":
        raise ValueError("ymfm BSD-3-Clause license digest mismatch")
    if "`LICENSE`" not in notice or license_digest not in notice:
        raise ValueError("NOTICE.md omits the license path or digest")
    for required in (
        "Mutable global state", "Per-chip mutable state", "Interface/callback state",
        "Lazy initialization/races", "Exceptions/allocation", "State serialization",
        "Clock/sample assumptions", "Evidence limit",
    ):
        if required not in notice:
            raise ValueError(f"NOTICE.md is missing inventory section: {required}")
    actual: dict[str, str] = {}
    for relative, expected in FILES.items():
        path = base / relative
        if not path.is_file():
            raise ValueError(f"source file is missing: {path.relative_to(ROOT)}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError(f"SHA-256 mismatch for {path.relative_to(ROOT)}: {digest}")
        if f"`{relative}`" not in notice or expected not in notice:
            raise ValueError(f"NOTICE.md omits the path or digest for {relative}")
        actual[relative] = digest
    extra = sorted(
        (Path("src") / path.relative_to(base / "src")).as_posix()
        for path in (base / "src").rglob("*")
        if path.is_file() and (Path("src") / path.relative_to(base / "src")).as_posix() not in FILES
    )
    if extra:
        raise ValueError(f"unreviewed files in ymfm source closure: {', '.join(extra)}")
    return {"status": "pass", "revision": REVISION, "files": actual,
            "license": "BSD-3-Clause", "unreviewed_files": []}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] != "source":
        print("usage: check_ym2610.py source", file=sys.stderr)
        return 2
    try:
        result = source_check()
    except (OSError, ValueError) as error:
        print(f"ym2610 source check failed: {error}", file=sys.stderr)
        return 1
    print(f"ym2610 source gate: {len(FILES)} pinned files at {REVISION}")
    print("mutable globals: none; license: BSD-3-Clause; inventory: complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
