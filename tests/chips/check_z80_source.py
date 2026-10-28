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
STATE_INVENTORY = ROOT / "docs/state-z80-inventory.md"
WRAPPER = ROOT / "src/chips/z80_candidate.c"
CMAKE = ROOT / "CMakeLists.txt"
EXPECTED_SHA256 = "6ca70ffd91b1bdbaf00f7a41e7092b326145fd1c95dcdd7bb01183370de734f3"
REVISION = "9e88298ce56319953ac7a43213a1120359f7a3a6"


def require(text: str, terms: tuple[str, ...], source: Path) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{source.relative_to(ROOT)} is missing inventory terms: {', '.join(missing)}")


def decoder_step_labels(source: str) -> set[int]:
    switch_match = re.search(r"switch\s*\(\s*cpu->step\s*\)\s*\{", source)
    if switch_match is None:
        raise SystemExit("pinned Z80 decoder step switch is missing")
    switch_end = source.find("default:", switch_match.end())
    if switch_end < 0:
        raise SystemExit("pinned Z80 decoder step switch has no default case")
    switch = source[switch_match.end():switch_end]
    defines = {
        name: int(value)
        for name, value in re.findall(
            r"^\s*#define\s+(Z80_[A-Z0-9_]+)\s+(\d+)\s*$",
            source,
            re.MULTILINE,
        )
    }
    labels: set[int] = set()
    unresolved: list[str] = []
    for token in re.findall(r"\bcase\s+([A-Za-z_][A-Za-z0-9_]*|\d+)\s*:", switch):
        if token.isdigit():
            labels.add(int(token))
        elif token in defines:
            labels.add(defines[token])
        else:
            unresolved.append(token)
    if unresolved:
        raise SystemExit(f"unresolved named decoder steps: {', '.join(sorted(set(unresolved)))}")
    return labels


def main() -> int:
    for path in (SOURCE, NOTICE, ADMISSION, STATE_INVENTORY, WRAPPER, CMAKE):
        if not path.is_file():
            raise SystemExit(f"required Z80 admission artifact is missing: {path.relative_to(ROOT)}")

    source_bytes = SOURCE.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"Z80 source digest mismatch: expected {EXPECTED_SHA256}, got {digest}")

    notice = NOTICE.read_text(encoding="utf-8")
    require(notice, (
        REVISION, EXPECTED_SHA256, "zlib/libpng license",
        "Copyright (c) 2018 Andre Weissflog", "This notice may not be removed",
        "vendored z80.h is unchanged", "private codec and adapter",
        "src/chips/z80_candidate.c",
    ), NOTICE)
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

    labels = decoder_step_labels(source)
    expected_labels = set(range(1709))
    if labels != expected_labels:
        missing = sorted(expected_labels - labels)
        extra = sorted(labels - expected_labels)
        raise SystemExit(
            f"pinned Z80 decoder label domain changed: missing={missing[:12]} extra={extra[:12]}"
        )

    inventory = STATE_INVENTORY.read_text(encoding="utf-8").lower()
    require(inventory, (
        "z80 v1 canonical state", "gz80", "76 bytes",
        "labels 0..1708 are contiguous", "no interior holes",
        "1685..1699", "1700..1702", "1703..1705", "1706..1708",
        "source-derived admissibility", "opcode/index", "int_bits",
        "callback failure", "allocation-failure sweep", "test-only hook",
        "9e88298ce56319953ac7a43213a1120359f7a3a6",
        "6ca70ffd91b1bdbaf00f7a41e7092b326145fd1c95dcdd7bb01183370de734f3",
    ), STATE_INVENTORY)
    wrapper = WRAPPER.read_text(encoding="utf-8")
    require(wrapper, (
        "static bool valid_decoder_state", "cpu->step == Z80_DDFD_M1_T2",
        "cpu->opcode != 0xDDu", "cpu->opcode != 0xFDu",
        "cpu->opcode == 0xCBu", "cpu->opcode == 0xEDu",
        "Z80_CANDIDATE_STATE_BYTES = 76", "Z80_CANDIDATE_TEST_HOOKS",
    ), WRAPPER)
    cmake = CMAKE.read_text(encoding="utf-8")
    require(cmake, ("target_compile_definitions(z80_admission_test PRIVATE Z80_CANDIDATE_TEST_HOOKS=1)",), CMAKE)

    print(f"z80_source_revision={REVISION}")
    print(f"z80_source_sha256={digest}")
    print(f"z80_decoder_step_domain=0..{max(labels)} labels={len(labels)} holes=0")
    print("z80_state_schema=GZ80 version=1 bytes=76 canonical=big-endian")
    print("z80_test_failpoints=private test target only")
    print("z80_source_closure=third_party/chips/z80.h + C standard library headers")
    print("z80_notice_and_state_inventory=present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
