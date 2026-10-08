#!/usr/bin/env python3
"""Behavioral controls for Phase 04 validation-map reconciliation."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))
import check_phase04_validation_map as validation_map  # noqa: E402


PHASE = ROOT / ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer"
COMMANDS = {
    "python3 tests/tools/test_verify_playable.py -v": 23,
    "python3 tests/libretro/test_retroarch_smoke.py -v": 27,
}


def reconciled_review_documents(directory: Path) -> dict[str, Path]:
    """Return internally consistent records after the repaired CR-01 is no longer current."""
    sources = {
        "VALIDATION": PHASE / "04-VALIDATION.md",
        "SECURITY": PHASE / "04-SECURITY.md",
        "VERIFICATION": PHASE / "04-VERIFICATION.md",
        "DISPOSITION": PHASE / "04-REVIEW-DISPOSITION.md",
        "REVIEW": PHASE / "04-REVIEW.md",
    }
    copied: dict[str, Path] = {}
    for name, source in sources.items():
        destination = directory / source.name
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        copied[name] = destination

    validation = copied["VALIDATION"].read_text(encoding="utf-8")
    validation = validation.replace("pass, 20 tests on source `04-13`", "pass, 23 tests on source `04-13`")
    validation = validation.replace("pass, 26 tests on source `04-13`", "pass, 27 tests on source `04-13`")
    validation = validation.replace(
        "The historical CR-01 identity finding was fixed, but the current reused CR-01 ID names a distinct boolean-count bypass and remains open in the current disposition record.",
        "The CR-01 boolean-count bypass was fixed by exact-integer checks and is absent from the fresh review.",
    )
    validation = validation.replace(
        "All five current/carried review dispositions remain open until independent review.",
        "Five current/carried findings remain open; the repaired CR-01 record is retained as fixed.",
    )
    # The copied map models the latest observed run; the checker must compare that
    # run with its recorded current result before checking reconciliation semantics.
    validation = validation.replace("pass, 19 tests on source `33bef8c`", "pass, 20 tests on source `33bef8c`")
    validation = validation.replace("pass, 25 tests on source `33bef8c`", "pass, 26 tests on source `33bef8c`")
    records = validation_map.parse_disposition_yaml(copied["DISPOSITION"].read_text(encoding="utf-8"))
    lines = validation.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] in records:
            cells[3] = records[cells[0]]["disposition"]
            lines[index] = "| " + " | ".join(cells) + " |"
    validation = "\n".join(lines) + "\n"
    copied["VALIDATION"].write_text(validation, encoding="utf-8")

    disposition_path = copied["DISPOSITION"]
    disposition = disposition_path.read_text(encoding="utf-8")
    block = re.search(r"(?ms)^  - id: CR-01\n(.*?)(?=^  - id:|\Z)", disposition.split("---", 2)[1])
    if block is None:
        raise AssertionError("CR-01 history is missing")
    updated_block = re.sub(r"(?m)^    disposition: open$", "    disposition: fixed", block.group(0))
    updated_block = re.sub(r"(?m)^    title:.*$", '    title: "Boolean byte count bypass fixed by exact integer validation"', updated_block)
    updated_block = re.sub(r"(?m)^    severity:.*$", "    severity: critical", updated_block)
    sections = disposition.split("---", 2)
    frontmatter = sections[1].replace(block.group(0), updated_block)
    body = re.sub(r"(?m)^\| CR-01 \|[^\n]*$", "| CR-01 | critical | fixed | 04-12 exact integer receipt validation |", sections[2])
    body = body.replace("| CR-02 | critical | open | - |", "| CR-02 | critical | open | 04-REVIEW.md current |")
    body = body.replace("| WR-01 | warning | open | - |", "| WR-01 | warning | open | 04-REVIEW.md current |")
    body = body.replace("| WR-02 | warning | open | - (not in the current review) |", "| WR-02 | warning | open | Carried from prior review; no new independent evidence |")
    body = body.replace("| WR-03 | warning | open | - (not in the current review) |", "| WR-03 | warning | open | Carried from prior review; no new independent evidence |")
    disposition_path.write_text(f"---{frontmatter}---{body}", encoding="utf-8")
    return copied


def mutate_document(documents: dict[str, Path], name: str, transform) -> None:
    path = documents[name]
    path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")


def set_crosswalk_disposition(documents: dict[str, Path], finding_id: str, state: str) -> None:
    path = documents["VALIDATION"]
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith(f"| {finding_id} |"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            cells[3] = state
            lines[index] = "| " + " | ".join(cells) + " |"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
    raise AssertionError(f"crosswalk row for {finding_id} is missing")


def add_info_finding(documents: dict[str, Path], crosswalk_severity: str = "info") -> None:
    mutate_document(documents, "REVIEW", lambda text: text + (
        "\n## Info\n\n### IN-01: Informational diagnostic note [INFO]\n\n"
        "**Issue:** Synthetic informational finding.\n\n**Fix:** Record consistently.\n"
    ))
    disposition = documents["DISPOSITION"]
    text = disposition.read_text(encoding="utf-8")
    text = text.replace(
        "open: 5\ntotal: 8",
        '  - id: IN-01\n    severity: info\n    disposition: open\n'
        '    title: "Informational diagnostic note"\nopen: 6\ntotal: 9',
        1,
    )
    text = text.replace(
        "| CR-02 | critical | open |",
        "| CR-02 | critical | open |", 1,
    )
    disposition_separator = "|---------|----------|-------------|--------|\n"
    text = text.replace(
        disposition_separator,
        disposition_separator + "| IN-01 | info | open | 04-14 synthetic Info fixture |\n",
        1,
    )
    disposition.write_text(text, encoding="utf-8")
    validation = documents["VALIDATION"]
    lines = validation.read_text(encoding="utf-8").splitlines()
    header = next(index for index, line in enumerate(lines) if line.startswith("| Review Finding |"))
    lines.insert(header + 2, f"| IN-01 | {crosswalk_severity} | synthetic Info scope | open |")
    validation.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ValidationMapReconciliationTest(unittest.TestCase):
    def run_checker(self, documents: dict[str, Path]) -> None:
        def observed_suite(command: str) -> tuple[int, int, str]:
            count = COMMANDS[command]
            return 0, count, f"Ran {count} tests in 0.01s\n\nOK\n"

        with mock.patch.multiple(validation_map, **documents):
            with mock.patch.object(validation_map, "run_suite", side_effect=observed_suite):
                validation_map.main()

    def test_checker_accepts_a_reconciled_review_after_repaired_finding_disappears(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase04-review-reconciliation-") as temporary:
            documents = reconciled_review_documents(Path(temporary))
            try:
                self.run_checker(documents)
            except AssertionError as error:
                self.fail(f"reconciled records were rejected: {error}")

    def test_checker_accepts_a_new_current_finding_with_matching_records(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase04-new-finding-") as temporary:
            documents = reconciled_review_documents(Path(temporary))
            mutate_document(documents, "REVIEW", lambda text: text.replace(
                "## Warnings\n", "## Warnings\n\n### WR-06: New current warning [WARNING]\n\n**Issue:** Synthetic finding.\n\n**Fix:** Track it.\n", 1))
            path = documents["DISPOSITION"]
            content = path.read_text(encoding="utf-8")
            content = content.replace(
                '    title: "Repository-backed receipt validation accepts forged file-content hashes"\nopen: 5',
                '    title: "Repository-backed receipt validation accepts forged file-content hashes"\n'
                '  - id: WR-06\n    severity: warning\n    disposition: open\n    title: "New current warning"\nopen: 6',
            )
            content = content.replace("total: 8", "total: 9", 1)
            disposition_lines = content.splitlines()
            table_header = next(index for index, line in enumerate(disposition_lines) if line.startswith("| Finding | Severity | Disposition | Source |"))
            disposition_lines.insert(table_header + 2, "| WR-06 | warning | open | synthetic current review |")
            content = "\n".join(disposition_lines) + "\n"
            path.write_text(content, encoding="utf-8")
            validation = documents["VALIDATION"]
            text = validation.read_text(encoding="utf-8")
            lines = text.splitlines()
            header = next(index for index, line in enumerate(lines) if line.startswith("| Review Finding |"))
            lines.insert(header + 2, "| WR-06 | warning | new review scope | open |")
            text = "\n".join(lines) + "\n"
            validation.write_text(text, encoding="utf-8")
            self.run_checker(documents)

    def test_checker_accepts_info_finding_with_matching_severity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase04-info-finding-") as temporary:
            documents = reconciled_review_documents(Path(temporary))
            add_info_finding(documents)
            self.run_checker(documents)

    def test_checker_accepts_normalized_exact_crosswalk_disposition(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase04-normalized-disposition-") as temporary:
            documents = reconciled_review_documents(Path(temporary))
            set_crosswalk_disposition(documents, "CR-03", "  OpEn  ")
            self.run_checker(documents)

    def test_checker_rejects_contradictory_or_extra_crosswalk_states(self) -> None:
        for state in ("fixed; not open", "not open", "open; fixed", "unrecognized"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                set_crosswalk_disposition(documents, "CR-03", state)
                with self.assertRaisesRegex(AssertionError, r"CR-03 disposition"):
                    self.run_checker(documents)

    def test_review_parser_maps_info_and_in_ids_to_info_severity(self) -> None:
        parsed = validation_map.parse_review_findings(
            "## Info\n\n### IN-01: Informational diagnostic note [INFO]\n"
        )
        self.assertEqual(parsed, {"IN-01": ("info", "Informational diagnostic note [INFO]")})

    def test_checker_rejects_info_finding_with_mismatched_crosswalk_severity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase04-info-mismatch-") as temporary:
            documents = reconciled_review_documents(Path(temporary))
            add_info_finding(documents, crosswalk_severity="warning")
            with self.assertRaisesRegex(AssertionError, r"IN-01.*severity"):
                self.run_checker(documents)

    def test_checker_rejects_contradictory_records(self) -> None:
        mutations = {
            "yaml disposition": lambda text: text.replace("disposition: open", "disposition: fixed", 1),
            "yaml severity": lambda text: text.replace("severity: critical", "severity: warning", 1),
            "table disposition": lambda text: text.replace("| CR-03 | critical | open |", "| CR-03 | critical | fixed |"),
            "severity": lambda text: text.replace("| CR-03 | critical | open |", "| CR-03 | warning | open |"),
            "duplicate id": lambda text: text.replace("| CR-03 | critical | open |", "| CR-03 | critical | open |\n| CR-03 | critical | open |"),
            "drop yaml id": lambda text: re.sub(r"(?ms)^  - id: WR-03\n.*?(?=^  - id:|^open:)", "", text),
            "count": lambda text: text.replace("open: 5", "open: 99", 1),
            "total count": lambda text: text.replace("total: 8", "total: 99", 1),
        }
        for label, transform in mutations.items():
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                mutate_document(documents, "DISPOSITION", transform)
                with self.assertRaises(AssertionError):
                    self.run_checker(documents)

    def test_checker_rejects_missing_crosswalk_and_closed_current_finding(self) -> None:
        for label, name, transform in (
            ("crosswalk", "VALIDATION", lambda text: re.sub(r"(?m)^\| WR-01 \|[^\n]*\n", "", text)),
            ("current closure", "DISPOSITION", lambda text: text.replace("| CR-03 | critical | open |", "| CR-03 | critical | fixed |")),
        ):
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                mutate_document(documents, name, transform)
                with self.assertRaises(AssertionError):
                    self.run_checker(documents)

    def test_checker_rejects_security_or_frontend_claim_contradictions(self) -> None:
        mutations = (
            ("security count", "SECURITY", lambda text: text.replace("threats_open: 4", "threats_open: 3", 1)),
            ("security row", "SECURITY", lambda text: re.sub(r"(?m)^(\| T-04-11 \|[^\n]*\| )open(\s*\|)$", r"\1closed\2", text)),
            ("HOST-02 observed", "VERIFICATION", lambda text: re.sub(r"(?m)^(\| HOST-02 \|.*\| )\? NEEDS HUMAN(?: / PENDING)?( \|.*)$", r"\1pass\2", text)),
            ("QUAL-03 observed", "VERIFICATION", lambda text: re.sub(r"(?m)^(\| QUAL-03 \|.*\| )\? NEEDS HUMAN(?: / PENDING)?( \|.*)$", r"\1pass\2", text)),
        )
        for label, name, transform in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                mutate_document(documents, name, transform)
                with self.assertRaises(AssertionError):
                    self.run_checker(documents)


if __name__ == "__main__":
    unittest.main()
