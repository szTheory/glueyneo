# SPDX-License-Identifier: MIT
"""Private-path redaction and the fail-closed public-sink scan.

Diagnostics are unstructured, so a quote, newline or other punctuation cannot
prove where a private path ends: once a private root appears, the rest of the
value is dropped. Roots are the concrete values known at runtime (checkout,
home, temporary and run directories) plus generic per-user prefixes, matched in
every form seen in practice: realpath and /private aliases, case-insensitive
(APFS), JSON-escaped, percent-encoded, Windows separators, and without the
leading separator (CMake mangles absolute source paths into object directory
names that way). Matching uses plain substring search after NFKC folding,
not word-boundary guesses.

Redaction is best effort. scan_public() is the control: every public sink
calls it on its final serialized text and refuses to write on any survivor.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unicodedata
from typing import Iterable
import urllib.parse

GENERIC_ROOTS = ("/Users/", "/home/", "/Volumes/", "/tmp/", "/var/tmp/", "/var/folders/")


class PrivatePathError(RuntimeError):
    pass


def _forms(root: str, *, slashless: bool) -> set[str]:
    forms: set[str] = set()
    trailing = root.endswith("/")
    for value in {root, os.path.realpath(root) + ("/" if trailing else "")}:
        if value.startswith("/private/"):
            value_set = {value, value[len("/private"):]}
        else:
            value_set = {value, "/private" + value} if value.startswith(("/tmp/", "/var/")) else {value}
        for item in value_set:
            item = item if trailing else item.rstrip("/")
            if len(item.strip("/")) < 3:
                continue
            variants = [item, item.replace("/", "\\/"), item.replace("/", "\\"), urllib.parse.quote(item, safe="")]
            if slashless:
                # Specific roots only: generic ones like "home/" would match "chrome/".
                variants += [item.lstrip("/"), urllib.parse.quote(item.lstrip("/"), safe="")]
            for variant in variants:
                if len(variant.strip("/\\")) >= 3:
                    forms.add(variant.casefold())
    return forms


def private_needles(extra_roots: Iterable[Path | str] = ()) -> tuple[str, ...]:
    roots = {str(Path.home()), tempfile.gettempdir()}
    if os.environ.get("TMPDIR"):
        roots.add(os.environ["TMPDIR"])
    roots.update(str(root) for root in extra_roots if str(root))
    needles: set[str] = set()
    for root in GENERIC_ROOTS:
        needles.update(_forms(root, slashless=False))
    for root in roots:
        needles.update(_forms(root, slashless=True))
    return tuple(sorted(needles, key=len, reverse=True))


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def redact(text: str, marker: str = "[redacted-path]",
           extra_roots: Iterable[Path | str] = ()) -> str:
    """Drop everything from the first private root to the end of the value."""
    folded = _fold(text)
    positions = [index for needle in private_needles(extra_roots)
                 if (index := folded.find(needle)) >= 0]
    if not positions:
        return text
    # NFKC folding can change lengths; cut the original at the same prefix.
    cut = min(positions)
    prefix = ""
    for character in text:
        if len(_fold(prefix + character)) > cut:
            break
        prefix += character
    return prefix + marker


def scan_public(text: str, extra_roots: Iterable[Path | str] = ()) -> None:
    """Fail closed if any private root survives in text bound for a sink."""
    folded = _fold(text)
    if any(needle in folded for needle in private_needles(extra_roots)):
        raise PrivatePathError("private-path-survived")
    name = Path.home().name.casefold()
    if len(name) >= 3 and any(token == name for token in
                              "".join(c if c.isalnum() or c in "._-" else " " for c in folded).split()):
        raise PrivatePathError("private-path-survived")
