#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check every phase security register's blocking count against its rows.

GSD's secure-phase and ship gates trust the `threats_open` frontmatter, so it
must equal the number of open threat-register rows at or above the configured
`workflow.security_block_on` severity. Rules:

- `threats_open:` is read only from the YAML frontmatter (the first `---`
  block) and must appear exactly once; commented or indented copies are errors.
- Rows are counted from every `| Threat ID |` table that has Severity and
  Status columns. Cells split on unescaped pipes only.
- Threat IDs must be unique across tables; status must be open, closed or
  accepted; `status: verified` requires `threats_open: 0`.
- Default mode checks consistency only and prints per-register blocking counts,
  so a PASS is not closure. `--require-closed` additionally exits 1 while any
  register has blocking open threats.

Prose, review provenance and other phase-specific wording are deliberately not
checked here.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SEVERITY = {"low": 0, "medium": 1, "high": 2, "critical": 3}
WORKSTREAM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
KEY = re.compile(r"^threats_open:\s*(\d+)\s*$")
KEY_LIKE = re.compile(r"^\s*#?\s*threats_open\s*:")
CELL_SPLIT = re.compile(r"(?<!\\)\|")
HEADER = re.compile(r"^\|\s*Threat ID\s*\|(.+)\|\s*$")


def block_on(root: Path) -> int | str:
    """Return the severity threshold, or an error string."""
    try:
        config = json.loads((root / ".planning/config.json").read_text(encoding="utf-8"))
        value = str(config.get("workflow", {}).get("security_block_on", "high")).lower()
    except (OSError, ValueError, AttributeError) as error:
        return f"cannot read .planning/config.json: {type(error).__name__}"
    if value not in SEVERITY:
        return f"unknown workflow.security_block_on {value!r}"
    return SEVERITY[value]


def frontmatter(text: str) -> list[str] | None:
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None
    for end in range(1, len(lines)):
        if lines[end].rstrip() == "---":
            return lines[1:end]
    return None


def split_cells(row: str) -> list[str]:
    return [cell.strip() for cell in CELL_SPLIT.split(row.strip().strip("|"))]


def register_errors(path: Path, threshold: int) -> tuple[list[str], int]:
    """Return (errors, blocking open count)."""
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    front = frontmatter(text)
    if front is None:
        return [f"{path.name}: missing frontmatter"], 0
    keys = [line for line in front if KEY_LIKE.match(line)]
    declared = [KEY.match(line) for line in keys]
    if len(keys) != 1 or declared[0] is None:
        return [f"{path.name}: frontmatter needs exactly one `threats_open: <n>` line, found {len(keys)}"], 0
    verified = any(re.match(r"^status:\s*verified\s*$", line) for line in front)
    lines = text.splitlines()
    tables: list[tuple[list[str], list[list[str]]]] = []
    for index, line in enumerate(lines):
        header = HEADER.match(line)
        if header is None:
            continue
        columns = ["Threat ID", *split_cells(header.group(1))]
        if "Severity" not in columns or "Status" not in columns:
            continue
        table_rows: list[list[str]] = []
        for row in lines[index + 2:]:
            if not row.startswith("|"):
                break
            table_rows.append(split_cells(row))
        tables.append((columns, table_rows))
    if not tables:
        return [f"{path.name}: no threat register table"], 0
    seen: set[str] = set()
    blocking = 0
    for columns, rows in tables:
        severity_at, status_at = columns.index("Severity"), columns.index("Status")
        for row in rows:
            if len(row) != len(columns):
                errors.append(f"{path.name}: malformed threat row {row[:1]}")
                continue
            threat_id, severity, status = row[0], row[severity_at].lower(), row[status_at].lower()
            if threat_id in seen:
                errors.append(f"{path.name}: duplicate threat ID {threat_id}")
            seen.add(threat_id)
            if status not in {"open", "closed", "accepted"}:
                errors.append(f"{path.name}: {threat_id} has uncontrolled status {row[status_at]!r}")
            if severity not in SEVERITY:
                errors.append(f"{path.name}: {threat_id} has unknown severity {row[severity_at]!r}")
            elif status == "open" and SEVERITY[severity] >= threshold:
                blocking += 1
    count = int(declared[0].group(1))
    if count != blocking:
        errors.append(f"{path.name}: threats_open is {count} but {blocking} open rows meet block_on")
    if verified and count != 0:
        errors.append(f"{path.name}: status verified with threats_open {count}")
    return errors, blocking


def main(arguments: list[str] | None = None, root: Path = ROOT) -> int:
    # One workstream per run: shipped workstreams keep their historical records.
    words = sys.argv[1:] if arguments is None else arguments
    require_closed = "--require-closed" in words
    names = [word for word in words if word != "--require-closed"] or ["first-playable-game"]
    workstream = names[0]
    if len(names) > 1 or not WORKSTREAM.match(workstream):
        print(f"FAIL: invalid workstream argument {workstream!r}", file=sys.stderr)
        return 1
    threshold = block_on(root)
    if isinstance(threshold, str):
        print(f"FAIL: {threshold}", file=sys.stderr)
        return 1
    registers = sorted(root.glob(f".planning/workstreams/{workstream}/phases/*/[0-9][0-9]-SECURITY.md"))
    if not registers:
        print(f"FAIL: no security registers for workstream {workstream}", file=sys.stderr)
        return 1
    errors: list[str] = []
    counts: list[tuple[str, int]] = []
    for path in registers:
        try:
            found, blocking = register_errors(path, threshold)
        except (OSError, UnicodeDecodeError) as error:
            found, blocking = [f"{path.name}: unreadable ({type(error).__name__})"], 0
        errors.extend(found)
        counts.append((path.name, blocking))
    for error in errors:
        print(f"FAIL: {error}", file=sys.stderr)
    if errors:
        return 1
    if require_closed:
        open_registers = [(name, count) for name, count in counts if count > 0]
        for name, count in open_registers:
            print(f"FAIL: {name}: {count} blocking open threats", file=sys.stderr)
        if open_registers:
            return 1
    summary = ", ".join(f"{name}={count}" for name, count in counts)
    print(f"PASS: {len(registers)} security registers reconcile with block_on; blocking open: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
