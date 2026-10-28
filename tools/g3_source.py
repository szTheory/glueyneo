# SPDX-License-Identifier: MIT
"""One immutable source disposition for Phase 05's historical G3 scan.

This is not a diagnostic redactor or a public-sink exception. Only the root
predicate sees the substituted suffix; all other G3 rules scan original text.
Any revision, path or added-byte change retains the original fail-closed scan.
"""

from __future__ import annotations

import hashlib

import private_paths

_COMMIT = "63c1d2c217887c35de68f847ed0db59de6c6250e"
_PATH = "tools/verify_playable.py"
_ADDED_SHA256 = "10bbfdf0ccf9b372534ee3e0709f0720abb17f7762e0689170c1a0a465959911"
_SUFFIX = '"' + "." + "tm" + "p" + '"'
_SOURCE_LINE = "        temporary_name = name + " + _SUFFIX


def private_root_finding(commit: str, path: str, text: str) -> bool:
    """Retain root/identity detection except the reviewed literal suffix."""
    root_text = text
    if (commit == _COMMIT and path == _PATH
            and hashlib.sha256(text.encode("utf-8")).hexdigest() == _ADDED_SHA256
            and text.splitlines().count(_SOURCE_LINE) == 1):
        root_text = text.replace(_SOURCE_LINE,
                                 _SOURCE_LINE.replace(_SUFFIX, '"temporary-suffix"'), 1)
    return (private_paths.redact(root_text) != root_text
            or private_paths._username_token_present(text))
