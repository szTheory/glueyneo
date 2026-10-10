#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Mutation tests for the generic security register invariant."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_security_register as checker  # noqa: E402

ROWS = (
    "| T-09-01 | Disclosure | logs | high | mitigate | scan | closed |",
    "| T-09-02 | Disclosure | logs | high | mitigate | scan | open |",
    "| T-09-03 | Tampering | docs | medium | mitigate | gate | open |",
    "| T-09-04 | Disclosure | run dir | high | accept | local only | accepted |",
)


def register(threats_open: int, rows: tuple[str, ...] = ROWS) -> str:
    return "\n".join((
        "---", f"threats_open: {threats_open}", "---", "",
        "| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |",
        "|---|---|---|---|---|---|---|", *rows, "",
    ))


class SecurityRegisterTest(unittest.TestCase):
    def run_checker(self, text: str) -> int:
        with tempfile.TemporaryDirectory(prefix="security-register-") as temporary:
            root = Path(temporary)
            (root / ".planning").mkdir()
            (root / ".planning/config.json").write_text(
                json.dumps({"workflow": {"security_block_on": "high"}}), encoding="utf-8")
            phase = root / ".planning/workstreams/ws/phases/09-x"
            phase.mkdir(parents=True)
            (phase / "09-SECURITY.md").write_text(text, encoding="utf-8")
            with mock.patch("sys.stdout", new_callable=io.StringIO), \
                    mock.patch("sys.stderr", new_callable=io.StringIO):
                return checker.main(["ws"], root)

    def test_counts_only_open_rows_at_block_on(self) -> None:
        self.assertEqual(self.run_checker(register(1)), 0)

    def test_rejects_mismatched_count_duplicates_and_uncontrolled_status(self) -> None:
        mutations = {
            "count too low": register(0),
            "count too high": register(2),
            "duplicate ID": register(1, ROWS + (ROWS[0],)),
            "uncontrolled status": register(1, ROWS[:3] + ("| T-09-04 | D | x | high | accept | y | TBD |",)),
            "unknown severity": register(1, ROWS[:3] + ("| T-09-04 | D | x | severe | accept | y | closed |",)),
            "missing frontmatter": register(1).replace("threats_open: 1", ""),
        }
        for label, text in mutations.items():
            with self.subTest(mutation=label):
                self.assertEqual(self.run_checker(text), 1)

    def test_counts_rows_from_every_register_table(self) -> None:
        header = "| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |"
        second = "\n".join(("", "Later table.", "", header, "|---|---|---|---|---|---|---|",
                            "| T-09-05 | Disclosure | logs | high | mitigate | scan | open |", ""))
        duplicate = second.replace("T-09-05", "T-09-01")
        asvs = "\n".join(("", "| Threat ID | ASVS L1 result | Current evidence |", "|---|---|---|",
                           "| T-09-02 | OPEN - high | x |", ""))
        for label, text, expected in (
            ("second table hides open high row", register(1) + second, 1),
            ("duplicate ID across tables", register(2) + duplicate, 1),
            ("second table counted when declared", register(2) + second, 0),
            ("table without Severity/Status ignored", register(1) + asvs, 0),
        ):
            with self.subTest(case=label):
                self.assertEqual(self.run_checker(text), expected)


if __name__ == "__main__":
    unittest.main()
