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


def register(threats_open: int, rows: tuple[str, ...] = ROWS,
             frontmatter_lines: tuple[str, ...] = (), extra: str = "") -> str:
    return "\n".join((
        "---", *frontmatter_lines, f"threats_open: {threats_open}", "---", "",
        "| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |",
        "|---|---|---|---|---|---|---|", *rows, "", extra,
    ))


class SecurityRegisterTest(unittest.TestCase):
    def run_checker(self, text: str, arguments: tuple[str, ...] = ("ws",),
                    config: str | None = None, with_config: bool = True) -> int:
        return self.run_checker_output(text, arguments, config, with_config)[0]

    def run_checker_output(self, text: str, arguments: tuple[str, ...] = ("ws",),
                           config: str | None = None, with_config: bool = True) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory(prefix="security-register-") as temporary:
            root = Path(temporary)
            (root / ".planning").mkdir()
            if with_config:
                (root / ".planning/config.json").write_text(
                    config or json.dumps({"workflow": {"security_block_on": "high"}}), encoding="utf-8")
            phase = root / ".planning/workstreams/ws/phases/09-x"
            phase.mkdir(parents=True)
            (phase / "09-SECURITY.md").write_text(text, encoding="utf-8")
            with mock.patch("sys.stdout", new_callable=io.StringIO) as out, \
                    mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                code = checker.main(list(arguments), root)
            return code, out.getvalue(), err.getvalue()

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

    def test_frontmatter_status_and_configuration_mutations(self) -> None:
        template = ("# threats_open = count of OPEN threats at or above workflow.security_block_on "
                    "severity (the blocking gate)",)
        escaped = ROWS[:3] + ("| T-09-04 | Disclosure | run dir | high | accept | `a \\| b` | accepted |",)
        bad_config = '{"workflow": {"security_block_on": "severe"}}'
        mutations = {
            "duplicate key": (register(1, frontmatter_lines=("threats_open: 0",)), {}),
            "commented key": (register(1, frontmatter_lines=("# threats_open: 0",)), {}),
            "indented duplicate": (register(1, frontmatter_lines=("  threats_open: 0",)), {}),
            "body-only key": ("threats_open: 1\n" + register(1).split("---\n", 2)[2], {}),
            "verified while open": (register(1, frontmatter_lines=("status: verified",)), {}),
            "unknown block_on": (register(1), {"config": bad_config}),
            "missing config": (register(1), {"with_config": False}),
            "unreadable config": (register(1), {"config": "{not json"}),
            "bad workstream name": (register(1), {"arguments": ("../x",)}),
        }
        for label, (text, options) in mutations.items():
            with self.subTest(mutation=label):
                code, _, err = self.run_checker_output(text, **options)
                self.assertEqual(code, 1)
                self.assertIn("FAIL:", err)
        controls = {
            "template comment": register(1, frontmatter_lines=template),
            "escaped pipe cell": register(1, escaped),
            "verified and closed": register(0, ROWS[:1] + ROWS[3:], frontmatter_lines=("status: verified",)),
        }
        for label, text in controls.items():
            with self.subTest(control=label):
                self.assertEqual(self.run_checker(text), 0)

    def test_require_closed_mode(self) -> None:
        code, out, err = self.run_checker_output(register(1), ("ws", "--require-closed"))
        self.assertEqual(code, 1)
        self.assertIn("09-SECURITY.md", err)
        self.assertIn("1 blocking open threats", err)
        code, out, _ = self.run_checker_output(register(0, ROWS[:1] + ROWS[3:]), ("ws", "--require-closed"))
        self.assertEqual(code, 0)
        code, out, _ = self.run_checker_output(register(1))
        self.assertEqual(code, 0)
        self.assertIn("blocking open: 09-SECURITY.md=1", out)

    def test_flag_before_workstream(self) -> None:
        self.assertEqual(self.run_checker(register(1), ("--require-closed", "ws")), 1)


if __name__ == "__main__":
    unittest.main()
