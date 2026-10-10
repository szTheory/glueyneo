#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check every phase security register's blocking count against its rows.

GSD's secure-phase and ship gates trust the `threats_open` frontmatter, so it
must equal the number of open threat-register rows at or above the configured
`workflow.security_block_on` severity. Rules:

- The YAML frontmatter (the first `---` block) is read as a set of top-level
  keys; bare, double-quoted and single-quoted spellings of a key, compared
  case-insensitively, are the same key (T-04-48). A duplicate top-level key in
  any spelling, a commented or indented `threats_open`/`status` key, and any
  line that is not a blank line, a comment, an indented nested line or a
  simple `key: value` line (flow mapping, merge key, complex key, anchor,
  alias, escaped quoted key, top-level list item) is an error, never skipped.
  `threats_open` must be one bare non-negative integer, optionally followed by
  ` # comment`.
- Every table whose first header cell is exactly `Threat ID` is a register
  table and must have Severity and Status columns; one that lacks either is an
  error, never skipped (GWR-01). Non-register audit tables use another first
  header such as `Audited Threat`. Cells split on unescaped pipes only.
- Threat IDs must be unique across tables; status must be open, closed or
  accepted; `status: verified` (also quoted, any letter case: G2IN-01)
  requires `threats_open: 0`.
- Default mode checks consistency only and prints per-register blocking counts,
  so a PASS is not closure. `--require-closed` additionally exits 1 while any
  register has blocking open threats. `--phase NN` restricts the run to the one
  `phases/NN-*/NN-SECURITY.md` register (exactly one must exist) for phase
  acceptance; milestone shipping runs without it so every register counts,
  `NN-SECURITY.md` and decimal-phase `NN.N-SECURITY.md` alike (G2WR-04).

The blocking threshold is `workflow.security_block_on` from
`.planning/workstreams/<workstream>/config.json` when that file sets it, else
from `.planning/config.json` (default `high`). A workstream config is local,
untracked runtime state, so it may only be as strict as the root value or
stricter: a less strict value fails with `weakens security_block_on`. A missing
or unreadable root config, an unreadable workstream config and an unknown
severity at either level fail closed. The PASS line names the threshold and the
config file it came from.

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
# One simple top-level `key: value` line: bare, double-quoted (no backslash) or single-quoted key.
KEY_LINE = re.compile(r"""^(?P<key>[A-Za-z_][A-Za-z0-9_.-]*|"[^"\\]*"|'(?:[^']|'')*') *:(?: (?P<value>.*))?$""")
GUARDED_KEYS = frozenset({"threats_open", "status"})
INTEGER = re.compile(r"\d+")
CELL_SPLIT = re.compile(r"(?<!\\)\|")
# Any row whose first cell reads "Threat ID" starts a register table; the case and the trailing pipe
# are not significant, so a loosely written table is checked rather than skipped (T-04-62).
HEADER = re.compile(r"^\|\s*threat\s+id\s*\|(.*?)\|?\s*$", re.IGNORECASE)
PHASE_NUMBER = re.compile(r"^[0-9]{2}(\.[0-9]+)?$")
# One definition of a register file name, shared by the scoped and unscoped globs (G2WR-04).
REGISTER_NAME = re.compile(r"[0-9]{2}(?:\.[0-9]+)?-SECURITY\.md")


def configured_level(path: Path, label: str) -> str | None | tuple[str]:
    """Return `workflow.security_block_on` from one config, None when unset, or (error,)."""
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        value = config.get("workflow", {}).get("security_block_on")
        if value is not None:
            value = str(value).lower()
    except (OSError, ValueError, AttributeError) as error:
        return (f"cannot read {label}: {type(error).__name__}",)
    if value is not None and value not in SEVERITY:
        return (f"unknown workflow.security_block_on {value!r} in {label}",)
    return value


def block_on(root: Path, workstream: str) -> tuple[int, str, str] | str:
    """Return (threshold, level name, source file), or an error string.

    The workstream's own `.planning/workstreams/<name>/config.json` applies when
    it sets `workflow.security_block_on`, but it may not be less strict than the
    root value (default `high`): that untracked local file must not lower the
    gate. Unreadable files and unknown severities at either level are errors.
    """
    root_label = ".planning/config.json"
    level = configured_level(root / root_label, root_label)
    if isinstance(level, tuple):
        return level[0]
    root_name, root_source = ("high", "default") if level is None else (level, root_label)
    workstream_label = f".planning/workstreams/{workstream}/config.json"
    workstream_path = root / workstream_label
    if workstream_path.exists():
        value = configured_level(workstream_path, workstream_label)
        if isinstance(value, tuple):
            return value[0]
        if value is not None:
            if SEVERITY[value] > SEVERITY[root_name]:
                return f"{workstream_label} weakens security_block_on ({value} > {root_name})"
            return SEVERITY[value], value, workstream_label
    return SEVERITY[root_name], root_name, root_source


def frontmatter(text: str) -> list[str] | None:
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None
    for end in range(1, len(lines)):
        if lines[end].rstrip() == "---":
            return lines[1:end]
    return None


def normalized_key(raw: str) -> str:
    if raw[0] == '"':
        raw = raw[1:-1]
    elif raw[0] == "'":
        raw = raw[1:-1].replace("''", "'")
    return raw.casefold()


def strip_comment(value: str) -> str:
    return re.sub(r"(?:^|\s+)#.*$", "", value).strip()


def unquoted(value: str) -> str:
    """Remove one pair of matching quotes."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def frontmatter_keys(front: list[str]) -> tuple[dict[str, list[tuple[int, str]]], list[str]]:
    """Return (normalized key -> [(file line number, raw value)], errors) for the frontmatter lines."""
    keys: dict[str, list[tuple[int, str]]] = {}
    errors: list[str] = []
    for index, line in enumerate(front):
        number = index + 2
        stripped = line.strip()
        if not stripped:
            continue
        guarded_text = stripped[1:].strip() if stripped.startswith("#") else stripped if line[0] == " " else None
        if guarded_text is not None:
            found = KEY_LINE.match(guarded_text)
            if found and normalized_key(found.group("key")) in GUARDED_KEYS:
                kind = "commented" if stripped.startswith("#") else "indented"
                errors.append(f"{kind} {normalized_key(found.group('key'))} key at line {number}")
            continue
        found = KEY_LINE.match(line)
        if found is None:
            errors.append(f"unsupported frontmatter line {number}")
            continue
        keys.setdefault(normalized_key(found.group("key")), []).append((number, found.group("value") or ""))
    errors.extend(f"duplicate frontmatter key {key}" for key, entries in keys.items() if len(entries) > 1)
    return keys, errors


def split_cells(row: str) -> list[str]:
    return [cell.strip() for cell in CELL_SPLIT.split(row.strip().strip("|"))]


def register_errors(path: Path, threshold: int) -> tuple[list[str], int]:
    """Return (errors, blocking open count)."""
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    front = frontmatter(text)
    if front is None:
        return [f"{path.name}: missing frontmatter"], 0
    keys, key_errors = frontmatter_keys(front)
    errors.extend(f"{path.name}: {error}" for error in key_errors)
    declared = keys.get("threats_open", [])
    if not declared:
        errors.append(f"{path.name}: frontmatter needs exactly one `threats_open: <n>` line, found 0")
    if len(declared) == 1 and INTEGER.fullmatch(strip_comment(declared[0][1])) is None:
        errors.append(f"{path.name}: threats_open must be a bare non-negative integer")
    if errors:
        return errors, 0
    verified = any(unquoted(strip_comment(value)).casefold() == "verified" for _, value in keys.get("status", []))
    lines = text.splitlines()
    tables: list[tuple[list[str], list[list[str]]]] = []
    for index, line in enumerate(lines):
        header = HEADER.match(line)
        if header is None:
            continue
        columns = ["Threat ID", *split_cells(header.group(1))]
        if "Severity" not in columns or "Status" not in columns:
            errors.append(f"{path.name}: threat table at line {index + 1} lacks Severity or Status columns")
            continue
        table_rows: list[list[str]] = []
        for row in lines[index + 2:]:
            if not row.startswith("|"):
                break
            table_rows.append(split_cells(row))
        tables.append((columns, table_rows))
    if not tables:
        return [*errors, f"{path.name}: no threat register table"], 0
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
    count = int(strip_comment(declared[0][1]))
    if count != blocking:
        errors.append(f"{path.name}: threats_open is {count} but {blocking} open rows meet block_on")
    if verified and count != 0:
        errors.append(f"{path.name}: status verified with threats_open {count}")
    return errors, blocking


def parse_arguments(words: list[str]) -> tuple[bool, str | None, list[str]] | str:
    """Return (require_closed, phase, positional names), or an error string."""
    require_closed = False
    phase: str | None = None
    names: list[str] = []
    index = 0
    while index < len(words):
        word = words[index]
        if word == "--require-closed":
            require_closed = True
        elif word == "--phase":
            index += 1
            if index >= len(words):
                return "--phase needs a phase number"
            phase = words[index]
            if not PHASE_NUMBER.match(phase):
                return f"invalid --phase argument {phase!r}"
        else:
            names.append(word)
        index += 1
    return require_closed, phase, names


def main(arguments: list[str] | None = None, root: Path = ROOT) -> int:
    # One workstream per run: shipped workstreams keep their historical records.
    words = sys.argv[1:] if arguments is None else arguments
    parsed = parse_arguments(words)
    if isinstance(parsed, str):
        print(f"FAIL: {parsed}", file=sys.stderr)
        return 1
    require_closed, phase, names = parsed
    names = names or ["first-playable-game"]
    workstream = names[0]
    if len(names) > 1 or not WORKSTREAM.match(workstream):
        print(f"FAIL: invalid workstream argument {workstream!r}", file=sys.stderr)
        return 1
    threshold = block_on(root, workstream)
    if isinstance(threshold, str):
        print(f"FAIL: {threshold}", file=sys.stderr)
        return 1
    level, level_name, source = threshold
    pattern = f"phases/{phase}-*/{phase}-SECURITY.md" if phase else "phases/*/[0-9][0-9]*-SECURITY.md"
    registers = sorted(path for path in root.glob(f".planning/workstreams/{workstream}/{pattern}")
                       if REGISTER_NAME.fullmatch(path.name))
    if not registers:
        scope = f"phase {phase}" if phase else f"workstream {workstream}"
        print(f"FAIL: no security registers for {scope}", file=sys.stderr)
        return 1
    if phase and len(registers) != 1:
        print(f"FAIL: phase {phase} has {len(registers)} security registers, expected exactly one",
              file=sys.stderr)
        return 1
    errors: list[str] = []
    counts: list[tuple[str, int]] = []
    for path in registers:
        try:
            found, blocking = register_errors(path, level)
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
    scope = f"; scope: phase {phase}" if phase else ""
    print(f"PASS: {len(registers)} security registers reconcile with block_on; blocking open: {summary}"
          f"{scope}; block_on {level_name} from {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
