# SPDX-License-Identifier: MIT
"""Private-path redaction and the fail-closed public-sink scan.

Diagnostics are unstructured, so a quote, newline or other punctuation cannot
prove where a private path ends: once a private root appears, the rest of the
value is dropped.

Matching works on one canonical form instead of an enumeration of encodings.
canonicalize() decodes ``\\uXXXX`` and ``\\/`` escape text, percent-decodes to a
bounded fixpoint (``%252F`` needs two passes), applies NFKC and casefolding
(APFS is case-insensitive; fullwidth and fraction slashes fold to ``/``), and
collapses every run of non-alphanumeric characters (``/ \\ : . _ -``, U+2215,
U+2044, NBSP, whitespace) to a single ``/``. It also returns, for every
canonical character, the index of the original character it came from, so
redact() cuts the original text at the true position.

Roots are canonicalized the same way. Specific roots (checkout, home,
temporary and run directories, caller-supplied extra roots; at least two path
components, with realpath and /private aliases) match anywhere in the canonical
text, which also covers the slashless object-directory names CMake derives from
absolute source paths. Generic roots (/Users/, /tmp/ and the rest) match only at
a path start, so that ``build/tmp-like`` and ``docs/tmp/notes`` stay benign.

Redaction is best effort. scan_public() and scan_public_value() are the
control: every public sink calls one of them on the decoded values and keys it
is about to write, and refuses to write on any survivor. scan_public_value()
also scans the ``json.dumps`` form, whose ``\\uXXXX`` escapes canonicalize()
decodes.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile
import unicodedata
from typing import Iterable

GENERIC_ROOTS = ("/Users/", "/home/", "/Volumes/", "/tmp/", "/var/tmp/", "/var/folders/")
# macOS reports the same directories under /private; they are generic roots too.
_GENERIC_ALIASES = ("/private/tmp/", "/private/var/tmp/", "/private/var/folders/")
_PERCENT_PASSES = 8
_START_CHARACTERS = frozenset("\"'=([<,;:")
_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})|\\/")
_PERCENT_RUN = re.compile(r"(?:%[0-9a-fA-F]{2})+")


class PrivatePathError(RuntimeError):
    pass


def _substitute(text: str, index: list[int], pattern: re.Pattern[str], replace) -> tuple[str, list[int]]:
    pieces: list[str] = []
    mapped: list[int] = []
    last = 0
    for match in pattern.finditer(text):
        pieces.append(text[last:match.start()])
        mapped.extend(index[last:match.start()])
        replacement = replace(match)
        pieces.append(replacement)
        mapped.extend([index[match.start()]] * len(replacement))
        last = match.end()
    pieces.append(text[last:])
    mapped.extend(index[last:])
    return "".join(pieces), mapped


def _decode_escape(match: re.Match[str]) -> str:
    return "/" if match.group(0) == "\\/" else chr(int(match.group(1), 16))


def _decode_percent(match: re.Match[str]) -> str:
    raw = bytes.fromhex(match.group(0).replace("%", ""))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return "".join(chr(byte) if byte < 0x80 else f"%{byte:02X}" for byte in raw)


def _normalize(text: str) -> tuple[str, list[int]]:
    """Escapes, bounded percent fixpoint, NFKC and casefold, with an origin map."""
    value, index = text, list(range(len(text)))
    if "\\" in value:
        value, index = _substitute(value, index, _ESCAPE, _decode_escape)
    for _ in range(_PERCENT_PASSES):
        if "%" not in value:
            break
        decoded, mapped = _substitute(value, index, _PERCENT_RUN, _decode_percent)
        if decoded == value:
            break
        value, index = decoded, mapped
    if value.isascii():
        return value.casefold(), index
    folded: list[str] = []
    mapped = []
    for character, origin in zip(value, index):
        piece = unicodedata.normalize("NFKC", character).casefold()
        folded.append(piece)
        mapped.extend([origin] * len(piece))
    return "".join(folded), mapped


def _canonical(text: str) -> tuple[str, list[int], set[int]]:
    value, index = _normalize(text)
    canon: list[str] = []
    origin: list[int] = []
    starts: set[int] = set()
    in_run = False
    run_start = False
    for position, character in enumerate(value):
        if character.isalnum():
            in_run = False
            canon.append(character)
            origin.append(index[position])
            continue
        trigger = character.isspace() or character in _START_CHARACTERS
        if in_run:
            if trigger:
                starts.add(len(canon) - 1)
            continue
        in_run = True
        if trigger or position == 0:
            starts.add(len(canon))
        canon.append("/")
        origin.append(index[position])
    return "".join(canon), origin, starts


def canonicalize(text: str) -> tuple[str, list[int]]:
    """Return the canonical form of text and, per canonical character, its origin index."""
    canon, origin, _ = _canonical(text)
    return canon, origin


def _canonical_root(root: str) -> str:
    return _canonical(root)[0].strip("/")


def _root_aliases(root: str) -> set[str]:
    values = {root}
    try:
        values.add(os.path.realpath(root))
    except (OSError, ValueError):
        pass
    aliases: set[str] = set()
    for value in values:
        aliases.add(value)
        if value.startswith("/private/"):
            aliases.add(value[len("/private"):])
        elif value.startswith(("/tmp", "/var", "/etc")):
            aliases.add("/private" + value)
    return aliases


def _runtime_roots(extra_roots: Iterable[Path | str]) -> set[str]:
    roots = {tempfile.gettempdir()}
    try:
        roots.add(str(Path.home()))
    except (RuntimeError, KeyError, OSError):
        pass  # An unresolvable home leaves nothing to protect by path.
    if os.environ.get("TMPDIR"):
        roots.add(os.environ["TMPDIR"])
    roots.update(str(root) for root in extra_roots if str(root))
    return roots


def private_needles(extra_roots: Iterable[Path | str] = ()) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (specific, generic) canonical needles, longest first.

    Specific needles carry no leading separator and match anywhere. Generic
    needles keep their separators and match only at a path start.
    """
    specific: set[str] = set()
    generic: set[str] = set()
    for root in GENERIC_ROOTS + _GENERIC_ALIASES:
        generic.add(_canonical(root)[0])
    for root in _runtime_roots(extra_roots):
        for alias in _root_aliases(root):
            needle = _canonical_root(alias)
            if len(needle) < 3:
                continue
            if len([part for part in needle.split("/") if part]) >= 2:
                specific.add(needle)
            else:
                generic.add("/" + needle + "/")
    ordered = lambda items: tuple(sorted(items, key=len, reverse=True))  # noqa: E731
    return ordered(specific), ordered(generic)


def _first_match(canon: str, starts: set[int], extra_roots: Iterable[Path | str]) -> int | None:
    specific, generic = private_needles(extra_roots)
    found: list[int] = []
    for needle in specific:
        position = canon.find(needle)
        if position >= 0:
            found.append(position)
    for needle in generic:
        position = canon.find(needle)
        while position >= 0:
            if position in starts:
                found.append(position)
                break
            position = canon.find(needle, position + 1)
    return min(found) if found else None


def redact(text: str, marker: str = "[redacted-path]",
           extra_roots: Iterable[Path | str] = ()) -> str:
    """Drop everything from the first private root to the end of the value."""
    canon, origin, starts = _canonical(text)
    position = _first_match(canon, starts, extra_roots)
    if position is None:
        return text
    if position > 0 and canon[position - 1] == "/":
        position -= 1  # Drop the separator run in front of a specific root too.
    return text[:origin[position]] + marker


def _username_token_present(text: str) -> bool:
    try:
        name = Path.home().name.casefold()
    except (RuntimeError, KeyError, OSError):
        return False
    if len(name) < 3:
        return False
    folded, _ = _normalize(text)
    tokens = "".join(c if c.isalnum() or c in "._-" else " " for c in folded).split()
    return any(token == name for token in tokens)


def scan_public(text: str, extra_roots: Iterable[Path | str] = ()) -> None:
    """Fail closed if any private root survives in text bound for a sink."""
    canon, _, starts = _canonical(text)
    if _first_match(canon, starts, extra_roots) is not None or _username_token_present(text):
        raise PrivatePathError("private-path-survived")
