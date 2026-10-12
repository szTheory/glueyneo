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


class GfmTableFormTest(SecurityRegisterTest):
    """T-04-62: every table form GFM renders is counted; other Threat ID header lines fail closed."""

    COLUMNS = "Threat ID | Category | Component | Severity | Disposition | Mitigation | Status"
    DELIMITER = "---|---|---|---|---|---|---"
    ROW = "T-09-05 | Tampering | docs | high | mitigate | gate | open"

    def table(self, indent: str = "", lead: str = "", trail: str = "", delimiter: str | None = None,
              row_lead: str | None = None, row_trail: str | None = None) -> str:
        row_lead = lead if row_lead is None else row_lead
        row_trail = trail if row_trail is None else row_trail
        return "\n".join((f"{indent}{lead}{self.COLUMNS}{trail}",
                          f"{indent}{lead}{delimiter or self.DELIMITER}{trail}",
                          f"{indent}{row_lead}{self.ROW}{row_trail}"))

    def assert_counted(self, table: str) -> None:
        # The declared count of 1 matches the first table only; the second adds a blocking row.
        code, _, err = self.run_checker_output(register(1, extra=table))
        self.assertEqual(code, 1)
        self.assertIn("threats_open is 1 but 2 open rows", err)
        self.assertEqual(self.run_checker(register(2, extra=table)), 0)

    def test_t_04_62_table_without_any_pipes_at_the_edges_is_counted(self) -> None:
        self.assert_counted(self.table())

    def test_t_04_62_indented_one_to_three_spaces_is_counted(self) -> None:
        for indent in (" ", "  ", "   "):
            with self.subTest(indent=len(indent)):
                self.assert_counted(self.table(indent=indent))
                self.assert_counted(self.table(indent=indent, lead="| ", trail=" |"))

    def test_t_04_62_header_and_rows_may_disagree_about_pipes(self) -> None:
        self.assert_counted(self.table(lead="| ", trail=" |", row_lead="", row_trail=""))
        self.assert_counted(self.table(row_lead="| ", row_trail=" |"))

    def test_t_04_62_delimiter_alignment_colons_and_spaces(self) -> None:
        for delimiter in (":--- | ---: | :---: | --- | --- | --- | ---", "  :-- |--:| :-: |-|-|-|-  "):
            with self.subTest(delimiter=delimiter):
                self.assert_counted(self.table(delimiter=delimiter))

    def test_t_04_62_unparsed_threat_id_header_forms_fail_closed(self) -> None:
        pipe = self.table(lead="| ", trail=" |")
        forms = {
            "four spaces": self.table(indent="    "),
            "tab": "\t" + pipe.replace("\n", "\n\t"),
            "blockquote": "\n".join("> " + line for line in pipe.split("\n")),
            "no delimiter row": f"| {self.COLUMNS} |\n| {self.ROW} |",
            "delimiter with other cell count": f"| {self.COLUMNS} |\n|---|---|\n| {self.ROW} |",
        }
        for label, table in forms.items():
            with self.subTest(form=label):
                code, _, err = self.run_checker_output(register(1, extra=table))
                self.assertEqual(code, 1)
                self.assertRegex(err, r"unrecognized threat table form at line \d+")

    def test_t_04_62_malformed_row_still_fails(self) -> None:
        table = f"| {self.COLUMNS} |\n|{self.DELIMITER}|\n| T-09-06 | only | three |"
        code, _, err = self.run_checker_output(register(1, extra=table))
        self.assertEqual(code, 1)
        self.assertIn("malformed threat row", err)

    def test_t_04_62_prose_mentioning_the_header_is_not_a_table(self) -> None:
        prose = "- T-04-62 OPEN: the table form (`Threat ID | Severity | Status`) was skipped."
        self.assertEqual(self.run_checker(register(1, extra=prose)), 0)

    TRAILING_ROW = "| T-09-06 | Tampering | docs | high | mitigate | gate | open |"

    def table_then(self, line: str) -> str:
        return "\n".join((self.table(lead="| ", trail=" |"), line, self.TRAILING_ROW))

    def assert_row_not_hidden(self, line: str) -> None:
        # The declared count of 2 covers the rows before the line; the row after it still renders.
        code, _, err = self.run_checker_output(register(2, extra=self.table_then(line)))
        self.assertEqual(code, 1)
        self.assertIn("threats_open is 2 but 3 open rows meet block_on", err)
        self.assertIn("malformed threat row", err)

    def test_t_04_62_table_end_non_heading_hash_lines_do_not_hide_rows(self) -> None:
        for line in ("#note", "#x", "#5 bolt", "   #note", "####### x"):
            with self.subTest(line=line):
                self.assert_row_not_hidden(line)

    def test_t_04_62_table_end_backtick_fence_lookalike_does_not_hide_rows(self) -> None:
        self.assert_row_not_hidden("```a`b")

    def test_t_04_62_commonmark_block_starts_still_close_the_table(self) -> None:
        forms = ("# H", "## H", "###### H", "#", "#\tH", "   ## H", "> quote", "```", "```py", "~~~", "~~~ x`y")
        for line in forms:
            with self.subTest(line=line):
                code, _, err = self.run_checker_output(register(2, extra=self.table_then(line)))
                self.assertEqual((code, err), (0, ""))


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
        for label, header, delimiter in (
            ("only Severity", "| Threat ID | Category | Severity | Disposition | State |", "|---|---|---|---|---|"),
            ("only Status", "| Threat ID | Category | Sev | Disposition | Status |", "|---|---|---|---|---|"),
            # T-04-62: the delimiter row must have the header's cell count to form a GFM table.
            ("neither", "| Threat ID | ASVS L1 result | Current evidence |", "|---|---|---|"),
        ):
            with self.subTest(table=label):
                text = register(1) + "\n" + header + "\n" + delimiter + "\n"
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
    def run_phases(self, phases: dict[str, str], arguments: tuple[str, ...],
                   extra_files: dict[str, str] | None = None) -> tuple[int, str, str]:
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
            for relative, text in (extra_files or {}).items():
                (root / ".planning/workstreams/ws/phases" / relative).write_text(text, encoding="utf-8")
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

    def test_g2wr_04_unscoped_gate_counts_decimal_phase_registers(self) -> None:
        phases = {"04-x": self.CLOSED, "04.1-y": register(1)}
        code, _, err = self.run_phases(phases, ("ws", "--require-closed"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: 04.1-SECURITY.md: 1 blocking open threats", err)
        code, out, err = self.run_phases(phases, ("ws",))
        self.assertEqual(code, 0, err)
        self.assertIn("2 security registers", out)
        self.assertIn("04.1-SECURITY.md=1", out)

    def test_g2wr_04_non_register_names_are_not_counted(self) -> None:
        phases = {"04-x": self.CLOSED, "04.1-y": register(1)}
        # G3IN-03 (intentional baseline change): a register-shaped file with a non-register name used to be
        # skipped silently, which hid its open rows. It must now fail instead of being ignored.
        code, out, err = self.run_phases(phases, ("ws",), {"04-x/04-draft-SECURITY.md": register(1)})
        self.assertEqual(code, 1)
        self.assertIn("misnamed security register 04-draft-SECURITY.md", err)
        code, out, err = self.run_phases(phases, ("ws", "--phase", "04.1"))
        self.assertEqual(code, 0, err)
        self.assertIn("1 security registers", out)
        self.assertIn("04.1-SECURITY.md=1", out)

    def test_g3in_03_misnamed_register_shaped_files_fail(self) -> None:
        phases = {"04-x": self.CLOSED}
        for name, text in (("04-x/04-draft-SECURITY.md", register(1)),
                           ("04-x/04-notes-SECURITY.md", "---\nthreats_open: 0\n---\n"),
                           ("04-x/04-table-SECURITY.md", "# t\n\n" + register(1).split("---\n", 2)[2])):
            with self.subTest(name=name):
                code, _, err = self.run_phases(phases, ("ws",), {name: text})
                self.assertEqual(code, 1)
                self.assertIn(f"misnamed security register {name.split('/')[1]}", err)

    def test_g3in_03_non_register_documents_are_skipped_and_reported(self) -> None:
        phases = {"04-x": self.CLOSED}
        admission = "---\nphase: 04\nstatus: draft\n---\n\nNo threat table here.\n"
        code, out, err = self.run_phases(phases, ("ws",), {"04-x/04-29-ADMISSION-SECURITY.md": admission})
        self.assertEqual(code, 0, err)
        self.assertIn("SKIP: 04-29-ADMISSION-SECURITY.md is not a register name", out)
        self.assertIn("1 security registers", out)

    def test_g3in_03_verified_may_carry_a_trailing_comment(self) -> None:
        code, _, err = self.run_phases({"04-x": register(1, frontmatter_lines=("status: verified  # reviewed",))},
                                       ("ws",))
        self.assertEqual(code, 1)
        self.assertIn("status verified with threats_open 1", err)
        closed = register(0, ROWS[:1] + ROWS[3:], frontmatter_lines=("status: verified  # reviewed",))
        self.assertEqual(self.run_phases({"04-x": closed}, ("ws",))[0], 0)

    def test_g4in_01_stray_register_names_fail(self) -> None:
        phases = {"04-x": self.CLOSED}
        for name in ("4-SECURITY.md", "SECURITY.md", "phase-04-security.md"):
            for arguments in (("ws", "--require-closed"), ("ws", "--require-closed", "--phase", "04")):
                with self.subTest(name=name, arguments=arguments):
                    code, out, err = self.run_phases(phases, arguments, {f"04-x/{name}": register(1)})
                    self.assertEqual(code, 1, out)
                    self.assertIn(f"misnamed security register {name}", err)

    def test_g4in_01_non_register_security_named_file_is_skipped(self) -> None:
        phases = {"04-x": self.CLOSED}
        for arguments in (("ws", "--require-closed"), ("ws", "--require-closed", "--phase", "04")):
            with self.subTest(arguments=arguments):
                code, out, err = self.run_phases(
                    phases, arguments, {"04-x/notes-security.md": "# Notes\n\nNo threat table here.\n"})
                self.assertEqual(code, 0, err)
                self.assertIn("SKIP: notes-security.md is not a register name", out)

    def test_g2in_01_verified_status_is_case_insensitive(self) -> None:
        for status in ("status: Verified", "status: VERIFIED", 'status: "Verified"'):
            with self.subTest(status=status):
                code, _, err = self.run_phases({"04-x": register(1, frontmatter_lines=(status,))}, ("ws",))
                self.assertEqual(code, 1)
                self.assertIn("status verified with threats_open 1", err)

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


class FrontmatterKeyTest(SecurityRegisterTest):
    """T-04-48: frontmatter is a set of normalized top-level keys; anything unreadable fails closed."""

    @staticmethod
    def doc(*front: str) -> str:
        body = register(1).split("---\n", 2)[2]
        return "\n".join(("---", *front, "---")) + "\n" + body

    def assert_fails(self, text: str, expected: str) -> None:
        code, _, err = self.run_checker_output(text)
        self.assertEqual(code, 1, err)
        self.assertIn("FAIL:", err)
        self.assertIn(expected, err)

    def test_t_04_48_quoted_and_cased_duplicates_fail(self) -> None:
        for label, duplicate in (("double-quoted", '"threats_open": 0'), ("single-quoted", "'threats_open': 0"),
                                 ("re-cased", "Threats_Open: 0")):
            with self.subTest(duplicate=label):
                self.assert_fails(self.doc("threats_open: 1", duplicate), "duplicate frontmatter key threats_open")

    def test_t_04_48_quoted_key_alone_is_the_same_key(self) -> None:
        for key in ('"threats_open"', "'threats_open'"):
            with self.subTest(key=key):
                self.assertEqual(self.run_checker(self.doc(f"{key}: 1")), 0)

    def test_t_04_48_status_duplicates_and_quoted_status(self) -> None:
        self.assert_fails(self.doc("status: open", "'status': verified", "threats_open: 1"),
                          "duplicate frontmatter key status")
        self.assert_fails(self.doc('"status": verified', "threats_open: 1"), "status verified with threats_open 1")

    def test_t_04_48_any_duplicate_top_level_key_fails(self) -> None:
        self.assert_fails(self.doc("phase: 04", '"phase": 05', "threats_open: 1"), "duplicate frontmatter key phase")

    def test_t_04_48_unsupported_lines_fail_with_line_number(self) -> None:
        for bad in ("{threats_open: 0}", "<<: *base", "? threats_open", r'"threats\x5fopen": 0',
                    "&a threats_open: 0", "- item", "*alias", "\tthreats_open: 0"):
            with self.subTest(line=bad):
                self.assert_fails(self.doc("threats_open: 1", bad), "unsupported frontmatter line 3")

    def test_t_04_48_commented_or_indented_keys_fail(self) -> None:
        for bad in ('# "threats_open": 0', "  'threats_open': 0", "# status: verified", "  status: verified"):
            with self.subTest(line=bad):
                code, _, err = self.run_checker_output(self.doc("threats_open: 1", bad))
                self.assertEqual(code, 1)
                self.assertRegex(err, r"(commented|indented) (threats_open|status) key at line 3")

    def test_t_04_48_threats_open_must_be_a_bare_integer(self) -> None:
        for value in ('"1"', "1.0", "one", "''"):
            with self.subTest(value=value):
                self.assert_fails(self.doc(f"threats_open: {value}"), "threats_open must be a bare non-negative integer")
        self.assertEqual(self.run_checker(self.doc("threats_open: 1  # note")), 0)

    def test_t_04_48_accepted_forms_stay_accepted(self) -> None:
        template = "# threats_open = count of OPEN threats at or above workflow.security_block_on severity"
        self.assertEqual(self.run_checker(self.doc(template, "threats_open: 1")), 0)
        self.assertEqual(self.run_checker(self.doc("findings:", "  high: 0", "phase: \"04\"", "threats_open: 1")), 0)
        verified = register(0, ROWS[:1] + ROWS[3:], frontmatter_lines=("status: verified  # reviewed",))
        self.assertEqual(self.run_checker(verified), 0)


    @staticmethod
    def closed_doc(*front: str) -> str:
        """A document whose register rows are closed, so a spelling the checker honors passes."""
        body = register(0, ROWS[:1] + ROWS[3:]).split("---\n", 2)[2]
        return "\n".join(("---", *front, "---")) + "\n" + body

    def test_g4wr_02_threats_open_key_must_be_spelled_exactly(self) -> None:
        for bad in ("Threats_Open: 0", '"THREATS_OPEN": 0', "'Threats_open': 0"):
            with self.subTest(key=bad):
                self.assert_fails(self.closed_doc(bad), "threats_open key must be spelled exactly")
        for good in ('"threats_open": 0', "'threats_open': 0"):
            with self.subTest(key=good):
                self.assertEqual(self.run_checker(self.closed_doc(good)), 0)

    def test_g4wr_02_threats_open_requires_ascii_digits(self) -> None:
        for value in ("\u0663", "\uff13"):
            with self.subTest(value=value):
                self.assert_fails(self.closed_doc(f"threats_open: {value}"),
                                  "threats_open must be a bare non-negative integer")

    def test_g4wr_02_status_key_must_be_spelled_exactly(self) -> None:
        self.assert_fails(self.closed_doc("threats_open: 0", "Status: verified"), "status key must be spelled exactly")
        # The value stays case-insensitive (G2IN-01).
        self.assertEqual(self.run_checker(self.closed_doc("threats_open: 0", "status: Verified")), 0)

    def test_g4wr_02_duplicates_still_case_insensitive(self) -> None:
        self.assert_fails(self.closed_doc("threats_open: 0", "Threats_Open: 0"), "duplicate frontmatter key threats_open")


if __name__ == "__main__":
    unittest.main()
