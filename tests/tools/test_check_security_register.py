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

    def test_t_04_62_second_table_with_a_loose_header_is_still_counted(self) -> None:
        columns = "Threat ID | Category | Component | Severity | Disposition | Mitigation | Status"
        row = "| T-09-05 | Tampering | docs | high | mitigate | gate | open |"
        variants = {
            "no trailing pipe": f"| {columns}\n|---|---|---|---|---|---|---\n{row}",
            "re-cased Threat Id": f"| {columns.replace('Threat ID', 'Threat Id')} |\n|---|---|---|---|---|---|---|\n{row}",
        }
        for label, extra in variants.items():
            with self.subTest(table=label):
                # The declared count of 1 matches the first table only; the second adds a blocking row.
                self.assertEqual(self.run_checker(register(1, extra=extra)), 1)
                self.assertEqual(self.run_checker(register(2, extra=extra)), 0)

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
        asvs = "\n".join(("", "| Audited Threat | ASVS L1 result | Current evidence |", "|---|---|---|",
                           "| T-09-02 | OPEN - high | x |", ""))
        for label, text, expected in (
            ("second table hides open high row", register(1) + second, 1),
            ("duplicate ID across tables", register(2) + duplicate, 1),
            ("second table counted when declared", register(2) + second, 0),
            ("audit table named Audited Threat ignored", register(1) + asvs, 0),
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
            "double-quoted verified while open": (register(1, frontmatter_lines=('status: "verified"',)), {}),
            "single-quoted verified while open": (register(1, frontmatter_lines=("status: 'verified'",)), {}),
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


class WorkstreamConfigTest(unittest.TestCase):
    MEDIUM_ROWS = ("| T-09-03 | Tampering | docs | medium | mitigate | gate | open |",)

    def run_with(self, text: str, root_config: str, workstream_config: str | None,
                 arguments: tuple[str, ...] = ("ws",)) -> tuple[int, str]:
        with tempfile.TemporaryDirectory(prefix="security-register-ws-") as temporary:
            root = Path(temporary)
            (root / ".planning").mkdir()
            (root / ".planning/config.json").write_text(root_config, encoding="utf-8")
            workstream = root / ".planning/workstreams/ws"
            phase = workstream / "phases/09-x"
            phase.mkdir(parents=True)
            (phase / "09-SECURITY.md").write_text(text, encoding="utf-8")
            if workstream_config is not None:
                (workstream / "config.json").write_text(workstream_config, encoding="utf-8")
            with mock.patch("sys.stdout", new_callable=io.StringIO), \
                    mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                code = checker.main(list(arguments), root)
            return code, err.getvalue()

    ROOT_HIGH = json.dumps({"workflow": {"security_block_on": "high"}})
    WS_MEDIUM = json.dumps({"workflow": {"security_block_on": "medium"}})

    def test_workstream_threshold_overrides_root(self) -> None:
        self.assertEqual(self.run_with(register(1, self.MEDIUM_ROWS), self.ROOT_HIGH, self.WS_MEDIUM)[0], 0)
        code, err = self.run_with(register(0, self.MEDIUM_ROWS), self.ROOT_HIGH, self.WS_MEDIUM)
        self.assertEqual(code, 1)
        self.assertIn("FAIL:", err)

    def test_root_threshold_applies_without_workstream_setting(self) -> None:
        for label, ws in (("absent", None), ("without key", json.dumps({"workflow": {}})),
                          ("empty object", "{}")):
            with self.subTest(workstream_config=label):
                self.assertEqual(self.run_with(register(0, self.MEDIUM_ROWS), self.ROOT_HIGH, ws)[0], 0)
                self.assertEqual(self.run_with(register(1, self.MEDIUM_ROWS), self.ROOT_HIGH, ws)[0], 1)

    def test_bad_workstream_config_fails_closed(self) -> None:
        for label, ws in (("unknown severity", json.dumps({"workflow": {"security_block_on": "severe"}})),
                          ("not json", "{not json"), ("not an object", "[]")):
            with self.subTest(workstream_config=label):
                code, err = self.run_with(register(0, self.MEDIUM_ROWS), self.ROOT_HIGH, ws)
                self.assertEqual(code, 1)
                self.assertIn("FAIL:", err)
                self.assertNotIn("Traceback", err)


class SchemaDriftTest(unittest.TestCase):
    """GWR-01: a `Threat ID` table lacking Severity or Status must fail, never be skipped."""

    OPEN_HIGH = "| T-09-98 | Tampering | x | high | mitigate | y | open |"

    def errors_for(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory(prefix="security-register-schema-") as temporary:
            path = Path(temporary) / "09-SECURITY.md"
            path.write_text(text, encoding="utf-8")
            return checker.register_errors(path, 2)[0]

    def test_sev_state_table_reproduces_the_verifier_mutation(self) -> None:
        second = "\n".join(("", "| Threat ID | Category | Component | Sev | Disposition | Mitigation | State |",
                            "|---|---|---|---|---|---|---|", self.OPEN_HIGH, ""))
        errors = self.errors_for(register(1) + second)
        self.assertTrue(any("lacks Severity or Status" in error for error in errors), errors)

    def test_table_with_only_one_of_severity_or_status_errors(self) -> None:
        for label, header in (
            ("only Severity", "| Threat ID | Category | Severity | Disposition | State |"),
            ("only Status", "| Threat ID | Category | Sev | Disposition | Status |"),
            ("neither", "| Threat ID | ASVS L1 result | Current evidence |"),
        ):
            with self.subTest(table=label):
                text = register(1) + "\n" + header + "\n|---|---|---|---|---|\n"
                self.assertTrue(any("lacks Severity or Status" in e for e in self.errors_for(text)))

    def test_exit_code_is_nonzero_for_the_mutation(self) -> None:
        second = "\n".join(("", "| Threat ID | Category | Component | Sev | Disposition | Mitigation | State |",
                            "|---|---|---|---|---|---|---|", self.OPEN_HIGH, ""))
        code, _, err = SecurityRegisterTest().run_checker_output(register(1) + second)
        self.assertEqual(code, 1)
        self.assertIn("lacks Severity or Status", err)

    def test_audited_threat_table_is_not_a_register(self) -> None:
        audit = "\n| Audited Threat | ASVS L1 result | Current evidence |\n|---|---|---|\n| T-09-02 | OPEN | x |\n"
        self.assertEqual(self.errors_for(register(1) + audit), [])


class PhaseScopeTest(unittest.TestCase):
    def run_phases(self, phases: dict[str, str], arguments: tuple[str, ...]) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory(prefix="security-register-phase-") as temporary:
            root = Path(temporary)
            (root / ".planning").mkdir()
            (root / ".planning/config.json").write_text(
                json.dumps({"workflow": {"security_block_on": "high"}}), encoding="utf-8")
            for directory, text in phases.items():
                number = directory.split("-", 1)[0]
                target = root / ".planning/workstreams/ws/phases" / directory
                target.mkdir(parents=True)
                (target / f"{number}-SECURITY.md").write_text(text, encoding="utf-8")
            with mock.patch("sys.stdout", new_callable=io.StringIO) as out, \
                    mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                code = checker.main(list(arguments), root)
            return code, out.getvalue(), err.getvalue()

    CLOSED = register(0, ROWS[:1] + ROWS[3:])

    def test_phase_scope_checks_only_that_register(self) -> None:
        phases = {"04-a": self.CLOSED, "05-b": register(1)}
        code, out, err = self.run_phases(phases, ("ws", "--require-closed", "--phase", "04"))
        self.assertEqual(code, 0, err)
        self.assertIn("scope: phase 04", out)
        code, _, err = self.run_phases(phases, ("ws", "--require-closed"))
        self.assertEqual(code, 1)
        self.assertIn("05-SECURITY.md", err)

    def test_phase_scope_fails_for_that_phases_blocking_rows(self) -> None:
        code, _, err = self.run_phases({"04-a": register(1), "05-b": self.CLOSED},
                                       ("ws", "--require-closed", "--phase", "04"))
        self.assertEqual(code, 1)
        self.assertIn("04-SECURITY.md: 1 blocking open threats", err)

    def test_phase_with_no_or_several_registers_fails(self) -> None:
        code, _, err = self.run_phases({"04-a": self.CLOSED}, ("ws", "--phase", "07"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL:", err)
        code, _, err = self.run_phases({"04-a": self.CLOSED, "04-b": self.CLOSED}, ("ws", "--phase", "04"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL:", err)

    def test_phase_argument_is_validated(self) -> None:
        for bad in ("4", "04x", "../04", "004", ""):
            with self.subTest(phase=bad):
                code, _, err = self.run_phases({"04-a": self.CLOSED}, ("ws", "--phase", bad))
                self.assertEqual(code, 1)
                self.assertIn("FAIL:", err)
        code, _, err = self.run_phases({"04-a": self.CLOSED}, ("ws", "--phase"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL:", err)


class NoWeakeningTest(unittest.TestCase):
    MEDIUM_ROWS = WorkstreamConfigTest.MEDIUM_ROWS
    ROOT_HIGH = WorkstreamConfigTest.ROOT_HIGH
    WS_MEDIUM = WorkstreamConfigTest.WS_MEDIUM
    run_with = WorkstreamConfigTest.run_with

    def test_workstream_config_cannot_weaken_the_root_threshold(self) -> None:
        for label, ws in (("critical over high", {"workflow": {"security_block_on": "critical"}}),):
            with self.subTest(case=label):
                code, err = self.run_with(register(1, self.MEDIUM_ROWS), self.ROOT_HIGH, json.dumps(ws))
                self.assertEqual(code, 1)
                self.assertIn("weakens security_block_on", err)

    def test_equal_or_stricter_workstream_value_is_accepted(self) -> None:
        for value in ("high", "medium", "low"):
            with self.subTest(value=value):
                ws = json.dumps({"workflow": {"security_block_on": value}})
                text = register(1, self.MEDIUM_ROWS) if value != "high" else register(0, self.MEDIUM_ROWS)
                self.assertEqual(self.run_with(text, self.ROOT_HIGH, ws)[0], 0)

    def test_pass_line_names_the_threshold_and_its_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="security-register-src-") as temporary:
            root = Path(temporary)
            (root / ".planning").mkdir()
            (root / ".planning/config.json").write_text(self.ROOT_HIGH, encoding="utf-8")
            phase = root / ".planning/workstreams/ws/phases/09-x"
            phase.mkdir(parents=True)
            (phase / "09-SECURITY.md").write_text(register(1, self.MEDIUM_ROWS), encoding="utf-8")
            (root / ".planning/workstreams/ws/config.json").write_text(self.WS_MEDIUM, encoding="utf-8")
            with mock.patch("sys.stdout", new_callable=io.StringIO) as out, \
                    mock.patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(checker.main(["ws"], root), 0)
            self.assertIn("block_on medium from .planning/workstreams/ws/config.json", out.getvalue())
            (root / ".planning/workstreams/ws/config.json").unlink()
            (phase / "09-SECURITY.md").write_text(register(0, self.MEDIUM_ROWS), encoding="utf-8")
            with mock.patch("sys.stdout", new_callable=io.StringIO) as out, \
                    mock.patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(checker.main(["ws"], root), 0)
            self.assertIn("block_on high from .planning/config.json", out.getvalue())


if __name__ == "__main__":
    unittest.main()
