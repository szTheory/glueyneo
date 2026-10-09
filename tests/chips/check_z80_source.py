#!/usr/bin/env python3
"""Verify the exact pinned Z80 source and the required audit inventory."""

from pathlib import Path
import hashlib
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "third_party/chips/z80.h"
NOTICE = ROOT / "third_party/chips/NOTICE.md"
ADMISSION = ROOT / "tests/chips/Z80-ADMISSION.md"
EXPECTED_SHA256 = "6ca70ffd91b1bdbaf00f7a41e7092b326145fd1c95dcdd7bb01183370de734f3"
REVISION = "9e88298ce56319953ac7a43213a1120359f7a3a6"


def require(text: str, terms: tuple[str, ...], source: Path) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{source.relative_to(ROOT)} is missing inventory terms: {', '.join(missing)}")


def main() -> int:
    for path in (SOURCE, NOTICE, ADMISSION):
        if not path.is_file():
            raise SystemExit(f"required Z80 admission artifact is missing: {path.relative_to(ROOT)}")

    source_bytes = SOURCE.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"Z80 source digest mismatch: expected {EXPECTED_SHA256}, got {digest}")

    notice = NOTICE.read_text(encoding="utf-8")
    require(notice, (REVISION, EXPECTED_SHA256, "zlib/libpng license", "Copyright (c) 2018 Andre Weissflog", "This notice may not be removed"), NOTICE)
    admission = ADMISSION.read_text(encoding="utf-8")
    require(admission.lower(), (
        REVISION, EXPECTED_SHA256, "transitive source", "mutable globals", "z80_t",
        "callbacks", "lazy initialization", "reset", "failure", "upstream-test provenance",
        "cycle", "interrupt", "bus", "continuation", "instance",
    ), ADMISSION)
    source = source_bytes.decode("utf-8")
    allowed_includes = {
        "stdint.h", "stdbool.h", "string.h", "assert.h",
    }
    includes = set(re.findall(r'^\s*#include\s*[<"]([^>"]+)[>"]', source, re.MULTILINE))
    if includes != allowed_includes:
        raise SystemExit(f"unexpected Z80 source include closure: {sorted(includes)}")
    mutable_static = re.findall(
        r"^\s*static\s+(?!inline\b|const\b)[^\n]+",
        source,
        re.MULTILINE,
    )
    if mutable_static:
        raise SystemExit(f"mutable Z80 static storage requires audit: {mutable_static[0].strip()}")

    fields = ("step", "addr", "dlatch", "opcode", "hlx_idx", "prefix_active", "pins", "int_bits", "pc", "af", "bc", "de", "hlx", "wz", "sp", "ir", "af2", "bc2", "de2", "hl2", "im", "iff1", "iff2")
    for field in fields:
        if not re.search(rf"\b{field}\b", source):
            raise SystemExit(f"pinned Z80 state field missing from header: {field}")

    print(f"z80_source_revision={REVISION}")
    print(f"z80_source_sha256={digest}")
    print("z80_source_closure=third_party/chips/z80.h + C standard library headers")
    print("z80_notice_and_state_inventory=present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
