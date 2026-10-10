#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check every phase security register's blocking count against its rows.

GSD's secure-phase and ship gates trust the `threats_open` frontmatter, so it
must equal the number of open threat-register rows at or above the configured
`workflow.security_block_on` severity. Threat IDs must be unique and each row
status must be open, closed or accepted. Prose, review provenance and other
phase-specific wording are deliberately not checked here.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
SEVERITY = {"low": 0, "medium": 1, "high": 2, "critical": 3}
HEADER = re.compile(r"^\|\s*Threat ID\s*\|(.+)\|\s*$")


def block_on(root: Path) -> int:
    config = json.loads((root / ".planning/config.json").read_text(encoding="utf-8"))
    return SEVERITY[str(config.get("workflow", {}).get("security_block_on", "high")).lower()]


def register_errors(path: Path, threshold: int) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    declared = re.search(r"(?m)^threats_open:\s*(\d+)\s*$", text)
    if declared is None:
        return [f"{path.name}: missing threats_open frontmatter"]
    lines = text.splitlines()
    tables: list[tuple[list[str], list[list[str]]]] = []
    for index, line in enumerate(lines):
        header = HEADER.match(line)
        if header is None:
            continue
        columns = ["Threat ID", *[cell.strip() for cell in header.group(1).split("|")]]
        if "Severity" not in columns or "Status" not in columns:
            continue
        table_rows: list[list[str]] = []
        for row in lines[index + 2:]:
            if not row.startswith("|"):
                break
            table_rows.append([cell.strip() for cell in row.strip().strip("|").split("|")])
        tables.append((columns, table_rows))
    if not tables:
        return [f"{path.name}: no threat register table"]
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
    if int(declared.group(1)) != blocking:
        errors.append(f"{path.name}: threats_open is {declared.group(1)} but {blocking} open rows meet block_on")
    return errors


def main(arguments: list[str] | None = None, root: Path = ROOT) -> int:
    # One workstream per run: shipped workstreams keep their historical records.
    workstream = (sys.argv[1:] if arguments is None else arguments) or ["first-playable-game"]
    threshold = block_on(root)
    registers = sorted(root.glob(f".planning/workstreams/{workstream[0]}/phases/*/[0-9][0-9]-SECURITY.md"))
    if not registers:
        print(f"FAIL: no security registers for workstream {workstream[0]}", file=sys.stderr)
        return 1
    errors = [error for path in registers for error in register_errors(path, threshold)]
    for error in errors:
        print(f"FAIL: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"PASS: {len(registers)} security registers reconcile with block_on")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
