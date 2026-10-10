#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Containment, verdict and transcription checks for the independent review.

The independent security review runs a read-only headless session in a scratch
extraction of the reviewed revision. Its closure records rest on three
mechanical questions, answered here in tracked, tested code instead of inline
plan snippets: was the session contained, what verdict did each ID get, and do
the tracked records equal those verdicts. Any zero, duplicate or malformed
verdict, any non-contained stream and any halt count as OPEN (T-04-48).

D-GAP-01 provenance. The user approved one boundary correction at Phase 04 gap
planning on 2026-10-10, after the 04-31 run halted on a read-only call whose
only path argument was the scratch directory itself: a path is contained when
its realpath equals the scratch realpath or lies under it, so the scratch
directory counts as contained. This corrects an over-strict boundary; it is not
a relaxation made to obtain a green result. No other 04-31 condition is
relaxed: exactly one init event, init tools a subset of {Read, Grep, Glob}, init
cwd equal to the scratch directory, only Read, Grep or Glob tool calls, no
permission denials, and a result event.

Strengthenings, added under the user-approved simple rule of the 2026-10-10 plan
revision and the D-GAP-01 clarification that strengthening is permitted: any
path, Glob pattern, Grep glob or base path containing a `..` segment anywhere is
not contained (fail closed); an absolute pattern is contained only when its
literal prefix up to the last `/` before the first wildcard is contained, so
`<scratch>/*.c` passes and `<scratch>*/x`, which could match a sibling such as
`<scratch>-evil`, does not; a relative path or pattern without `..` resolves
under the verified cwd or the contained Glob/Grep base; and `preflight` refuses a
scratch tree holding a symlink that resolves outside it. The reviewer prompt
forbids `..` and asks for scratch-relative paths, so a compliant all-in-scratch
review never trips the `..` rule.

Output carries IDs and reason codes only. Every printed line passes
`private_paths.scan_public` first and becomes `private-path-survived` on
failure; no input path is ever printed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import private_paths  # noqa: E402

ALLOWED_TOOLS = frozenset({"Read", "Grep", "Glob"})
WILDCARDS = "*?[{"
PROMPT_PREFIX = "Review IDs: "
HALT_PREFIX = "REVIEW HALTED:"
ID_PATTERN = r"T-\d{2}-\d{2}|T-\d{2}-SC \(\d{2}-\d{2}\)|(?:CR|WR|IN|GWR|GIN)-\d{2}"
ATTEMPT = re.compile(rf"^VERDICT ({ID_PATTERN})(?= |$)")
VERDICT_LINE = re.compile(rf"^VERDICT ({ID_PATTERN}) (CLOSED|OPEN|FIXED) (\S.*)$")
CELL_SPLIT = re.compile(r"(?<!\\)\|")
PHASE_NUMBER = re.compile(r"^(\d{2}(?:\.\d+)?)-")


class InputError(Exception):
    """Unreadable or malformed input (exit 2)."""


# --- containment -----------------------------------------------------------


def has_dotdot(text: str) -> bool:
    """True iff `text` contains `..` anywhere (fail closed, brace forms included)."""
    return ".." in text


def _inside(real_path: str, real_scratch: str) -> bool:
    return real_path == real_scratch or real_path.startswith(real_scratch + os.sep)


def path_contained(path: str, scratch: str, cwd: str) -> bool:
    """D-GAP-01: equal to the scratch realpath, or under it, after symlinks resolve."""
    if has_dotdot(path):
        return False
    try:
        joined = path if os.path.isabs(path) else os.path.join(cwd, path)
        return _inside(os.path.realpath(joined), os.path.realpath(scratch))
    except (ValueError, OSError):
        return False


def glob_contained(pattern: str, scratch: str, base: str) -> bool:
    """Whether every match of `pattern` stays inside the scratch directory."""
    if has_dotdot(pattern):
        return False
    if os.path.isabs(pattern):
        wild = [pattern.find(char) for char in WILDCARDS if char in pattern]
        if not wild:
            return path_contained(pattern, scratch, base)
        prefix = pattern[:min(wild)]
        cut = prefix.rfind("/")
        return path_contained(prefix[:cut] or "/", scratch, base)
    return path_contained(base, scratch, base)


def external_symlinks(scratch: str) -> list[str]:
    """Relative paths of symlinks in the tree whose realpath leaves the scratch root."""
    root = os.path.realpath(scratch)
    found: list[str] = []
    for directory, names, files in os.walk(root, followlinks=False):
        for name in (*names, *files):
            full = os.path.join(directory, name)
            if os.path.islink(full) and not _inside(os.path.realpath(full), root):
                found.append(os.path.relpath(full, root))
    return sorted(found)


def _tool_uses(events: list[dict]):
    for event in events:
        if event.get("type") != "assistant":
            continue
        content = (event.get("message") or {}).get("content") or []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                yield block


def _access_contained(block: dict, scratch: str, cwd: str) -> bool:
    arguments = block.get("input")
    if not isinstance(arguments, dict):
        return False
    base = cwd
    for key in ("file_path", "path"):
        value = arguments.get(key)
        if value is None or value == "":
            continue
        if not isinstance(value, str) or not path_contained(value, scratch, cwd):
            return False
        if key == "path":
            base = value if os.path.isabs(value) else os.path.join(cwd, value)
    for key in ("pattern", "glob"):
        # Glob `pattern` and Grep `glob` are path patterns; a Grep `pattern` is a regex.
        if key == "pattern" and block.get("name") != "Glob":
            continue
        value = arguments.get(key)
        if value is None or value == "":
            continue
        if not isinstance(value, str) or not glob_contained(value, scratch, base):
            return False
    return True


def containment(events: list[dict], scratch: str) -> tuple[bool, str]:
    """Return (contained, reason). Every 04-31 condition is kept; see the module docstring."""
    init = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
    if len(init) != 1:
        return False, "init-count"
    tools = init[0].get("tools")
    if not isinstance(tools, list) or not set(tools).issubset(ALLOWED_TOOLS):
        return False, "init-tools"
    cwd = init[0].get("cwd")
    if not isinstance(cwd, str) or not cwd or os.path.realpath(cwd) != os.path.realpath(scratch):
        return False, "init-cwd"
    for block in _tool_uses(events):
        if block.get("name") not in ALLOWED_TOOLS:
            return False, "tool-name"
    for block in _tool_uses(events):
        if not _access_contained(block, scratch, cwd):
            return False, "path-outside"
    results = [e for e in events if e.get("type") == "result"]
    if any(e.get("permission_denials") for e in results):
        return False, "permission-denials"
    if not results:
        return False, "no-result"
    return True, "contained"


# --- verdicts --------------------------------------------------------------


def review_ids(prompt_text: str) -> list[str]:
    lines = [line for line in prompt_text.splitlines() if line.startswith(PROMPT_PREFIX)]
    if len(lines) != 1:
        raise ValueError(f"prompt needs exactly one `{PROMPT_PREFIX.strip()}` line, found {len(lines)}")
    ids = [item.strip() for item in lines[0][len(PROMPT_PREFIX):].split(", ")]
    if not ids or any(not item for item in ids):
        raise ValueError("empty ID in the review ID list")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ID in the review ID list")
    return ids


def _is_threat(identifier: str) -> bool:
    return identifier.startswith("T-")


def parse_verdicts(review_text: str, ids: list[str], contained: bool) -> dict[str, str]:
    """Map each ID to CLOSED/OPEN/FIXED; anything but one well-formed verdict is OPEN."""
    lines = review_text.splitlines()
    if not contained or any(line.startswith(HALT_PREFIX) for line in lines):
        return {identifier: "OPEN" for identifier in ids}
    attempts: dict[str, list[str | None]] = {}
    for line in lines:
        line = line.rstrip()
        head = ATTEMPT.match(line)
        if head is None:
            continue
        full = VERDICT_LINE.match(line)
        attempts.setdefault(head.group(1), []).append(full.group(2) if full else None)
    verdicts: dict[str, str] = {}
    for identifier in ids:
        found = attempts.get(identifier, [])
        verdict = found[0] if len(found) == 1 else None
        allowed = ("CLOSED", "OPEN") if _is_threat(identifier) else ("FIXED", "OPEN")
        verdicts[identifier] = verdict if verdict in allowed else "OPEN"
    return verdicts


# --- transcription ---------------------------------------------------------


def split_cells(row: str) -> list[str]:
    return [cell.strip() for cell in CELL_SPLIT.split(row.strip().strip("|"))]


def expected_status(identifier: str, verdict: str, disposition: str,
                    fixed_means_deferred=(), maintainer_accepted=()) -> str:
    """The status a tracked record must carry for one verdict."""
    if _is_threat(identifier):
        if identifier in maintainer_accepted:
            return "accepted"  # D-GAP-02: the verdict is evidence only
        if verdict == "CLOSED":
            return "accepted" if disposition == "accept" else "closed"
        return "open"
    if verdict == "FIXED":
        return "deferred" if identifier in fixed_means_deferred else "fixed"
    return "open"


def _single_row(path: Path, identifier: str, width: int, errors: list[str]) -> list[str] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        errors.append(f"{identifier}: {path.name} is unreadable")
        return None
    rows = [cells for cells in (split_cells(line) for line in text.splitlines() if line.startswith("|"))
            if cells and cells[0] == identifier and len(cells) == width]
    if len(rows) != 1:
        errors.append(f"{identifier}: {path.name} has {len(rows)} matching rows, expected exactly one")
        return None
    return rows[0]


def transcription_errors(phase_dir: str, ids: list[str], verdicts: dict[str, str],
                         fixed_means_deferred=(), maintainer_accepted=()) -> list[str]:
    """Compare mapped verdicts with the security, disposition and crosswalk rows."""
    for identifier in maintainer_accepted:
        if not _is_threat(identifier):
            raise ValueError(f"{identifier} is a finding; maintainer acceptance applies to threats only")
        if identifier not in ids:
            raise ValueError(f"{identifier} is not a review ID")
    directory = Path(phase_dir)
    number = PHASE_NUMBER.match(directory.name)
    if number is None:
        raise ValueError("phase directory name does not start with a phase number")
    prefix = number.group(1)
    security = directory / f"{prefix}-SECURITY.md"
    disposition = directory / f"{prefix}-REVIEW-DISPOSITION.md"
    crosswalk = directory / f"{prefix}-VALIDATION.md"
    errors: list[str] = []
    for identifier in ids:
        verdict = verdicts.get(identifier, "OPEN")
        if _is_threat(identifier):
            row = _single_row(security, identifier, 7, errors)
            if row is None:
                continue
            kind, status = row[4].lower(), row[6].lower()
            if identifier in maintainer_accepted and kind != "accept":
                errors.append(f"{identifier}: {security.name} Disposition is {row[4]!r}, "
                              "maintainer acceptance needs 'accept'")
            want = expected_status(identifier, verdict, kind, fixed_means_deferred, maintainer_accepted)
            if status != want:
                errors.append(f"{identifier}: {security.name} Status is {row[6]!r}, expected {want!r} "
                              f"for verdict {verdict}")
            continue
        want = expected_status(identifier, verdict, "", fixed_means_deferred, maintainer_accepted)
        row = _single_row(disposition, identifier, 4, errors)
        if row is not None and row[2].lower() != want:
            errors.append(f"{identifier}: {disposition.name} Disposition is {row[2]!r}, expected {want!r} "
                          f"for verdict {verdict}")
        row = _single_row(crosswalk, identifier, 4, errors)
        if row is not None and row[3].lower() != want:
            errors.append(f"{identifier}: {crosswalk.name} crosswalk Disposition is {row[3]!r}, "
                          f"expected {want!r} for verdict {verdict}")
    return errors


# --- command line ----------------------------------------------------------


def safe_line(text: str) -> str:
    try:
        private_paths.scan_public(text)
    except private_paths.PrivatePathError:
        return "private-path-survived"
    return text


def _emit(text: str, stream=None) -> None:
    print(safe_line(text), file=stream or sys.stdout)


def _read(path: str, label: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise InputError(f"unreadable {label} ({type(error).__name__})") from None


def _load_scratch(path: str) -> str:
    lines = _read(path, "scratch file").strip().splitlines()
    if not lines or not os.path.isabs(lines[0].strip()) or not os.path.isdir(lines[0].strip()):
        raise InputError("scratch file does not name an existing absolute directory")
    return lines[0].strip()


def _load_events(path: str) -> list[dict] | None:
    """The stream's events, or None when no stream was produced."""
    if not os.path.exists(path):
        return None
    events = []
    for line in _read(path, "stream").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            raise InputError("malformed stream line") from None
        if not isinstance(event, dict):
            raise InputError("malformed stream line")
        events.append(event)
    return events


def _stream_state(path: str, scratch: str) -> tuple[bool, str, bool]:
    events = _load_events(path)
    if events is None:
        return False, "no-stream", False
    contained, reason = containment(events, scratch)
    return contained, reason, True


def _halt_lines(review_text: str) -> list[str]:
    return [line for line in review_text.splitlines() if line.startswith(HALT_PREFIX)]


def _id_list(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split(",") if item.strip())


def _cmd_preflight(args) -> int:
    count = len(external_symlinks(_load_scratch(args.scratch_file)))
    if count:
        _emit(f"refused: external-symlink {count}")
        return 1
    _emit("scratch-ok")
    return 0


def _cmd_gate(args) -> int:
    contained, reason, _ = _stream_state(args.stream, _load_scratch(args.scratch_file))
    if contained:
        _emit("contained")
        return 0
    _emit(f"not-contained: {reason}")
    return 1


def _cmd_verdicts(args) -> int:
    contained, reason, _ = _stream_state(args.stream, _load_scratch(args.scratch_file))
    text = _read(args.review, "review")
    try:
        ids = review_ids(_read(args.prompt, "prompt"))
    except ValueError as error:
        raise InputError(str(error)) from None
    halts = _halt_lines(text)
    halted = halts[0][len(HALT_PREFIX):].strip() if halts else None
    verdicts = parse_verdicts(text, ids, contained and halted is None)
    _emit(json.dumps({"contained": contained, "reason": reason, "halted": halted, "verdicts": verdicts},
                     sort_keys=True))
    return 0


def _cmd_check(args) -> int:
    scratch = _load_scratch(args.scratch_file)
    contained, reason, ran = _stream_state(args.stream, scratch)
    text = _read(args.review, "review")
    try:
        ids = review_ids(_read(args.prompt, "prompt"))
        accepted = _id_list(args.maintainer_accepted)
        deferred = _id_list(args.fixed_means_deferred)
        halts = _halt_lines(text)
        failures: list[str] = []
        lines = text.splitlines()
        if not lines or not lines[0].startswith(f"Reviewed revision: {args.revision}"):
            failures.append("review is not pinned to the revision")
        if len(halts) > 1 or (halts and (len(lines) != 2 or lines[1] != halts[0])):
            failures.append("halted review is not exactly the revision line plus one REVIEW HALTED line")
        if not contained and not halts:
            failures.append(f"stream is not contained ({reason}) but the review has no REVIEW HALTED line")
        if ran and not contained and halts != [f"{HALT_PREFIX} containment-violation"]:
            failures.append("non-contained stream is not recorded as REVIEW HALTED: containment-violation")
        effective = contained and not halts
        verdicts = parse_verdicts(text, ids, effective)
        failures += transcription_errors(args.phase_dir, ids, verdicts, deferred, accepted)
    except ValueError as error:
        raise InputError(str(error)) from None
    if failures:
        for failure in failures:
            _emit(f"FAIL: {failure}")
        return 1
    state = "contained" if effective else "halted " + (
        halts[0][len(HALT_PREFIX):].strip() if halts else "containment-violation")
    _emit(f"transcribed {len(ids)} ids ({state})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    preflight = commands.add_parser("preflight", help="refuse a scratch tree with an external symlink")
    preflight.add_argument("--scratch-file", required=True)
    gate = commands.add_parser("gate", help="decide containment of a saved stream")
    gate.add_argument("--stream", required=True)
    gate.add_argument("--scratch-file", required=True)
    for name in ("verdicts", "check"):
        sub = commands.add_parser(name)
        sub.add_argument("--stream", required=True)
        sub.add_argument("--scratch-file", required=True)
        sub.add_argument("--review", required=True)
        sub.add_argument("--prompt", required=True)
        if name == "check":
            sub.add_argument("--revision", required=True)
            sub.add_argument("--phase-dir", required=True)
            sub.add_argument("--fixed-means-deferred", default="")
            sub.add_argument("--maintainer-accepted", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    handlers = {"preflight": _cmd_preflight, "gate": _cmd_gate, "verdicts": _cmd_verdicts,
                "check": _cmd_check}
    try:
        args = build_parser().parse_args(argv)
        return handlers[args.command](args)
    except InputError as error:
        _emit(f"usage: {error}", sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
