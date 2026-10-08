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
    "python3 -m unittest discover -s tests/tools -p 'test_verify_playable.py' -v": 20,
    "python3 -m unittest discover -s tests/libretro -p 'test_retroarch_smoke.py' -v": 26,
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
    validation = re.sub(
        r"(?m)^\| CR-01 \|[^\n]*$",
        "| CR-01 | T-04-24 receipt numeric types | Fixed after exact-integer receipt validation |",
        validation,
    )
    validation = validation.replace(
        "The historical CR-01 identity finding was fixed, but the current reused CR-01 ID names a distinct boolean-count bypass and remains open in the current disposition record.",
        "The CR-01 boolean-count bypass was fixed by exact-integer checks and is absent from the fresh review.",
    )
    validation = validation.replace(
        "All five current/carried review dispositions remain open until independent review.",
        "Four current/carried findings remain open; the repaired CR-01 record is retained as fixed.",
    )
    # The copied map models the latest observed run; the checker must compare that
    # run with its recorded current result before checking reconciliation semantics.
    validation = validation.replace("pass, 19 tests on source `33bef8c`", "pass, 20 tests on source `33bef8c`")
    validation = validation.replace("pass, 25 tests on source `33bef8c`", "pass, 26 tests on source `33bef8c`")
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
    frontmatter = re.sub(r"(?m)^open: 5$", "open: 4", frontmatter)
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
                "## Warnings\n", "## Warnings\n\n### WR-04: New current warning [WARNING]\n\n**Issue:** Synthetic finding.\n\n**Fix:** Track it.\n", 1))
            path = documents["DISPOSITION"]
            content = path.read_text(encoding="utf-8")
            content = content.replace(
                '    title: "Repository-backed receipt validation accepts forged file-content hashes"\nopen: 4',
                '    title: "Repository-backed receipt validation accepts forged file-content hashes"\n'
                '  - id: WR-04\n    severity: warning\n    disposition: open\n    title: "New current warning"\nopen: 5',
            )
            content = content.replace("total: 5", "total: 6", 1)
            content = content.replace("| CR-01 | critical | fixed | 04-12 exact integer receipt validation |", "| CR-01 | critical | fixed | 04-12 exact integer receipt validation |\n| WR-04 | warning | open | 04-13 current review |")
            path.write_text(content, encoding="utf-8")
            validation = documents["VALIDATION"]
            text = validation.read_text(encoding="utf-8")
            separator = "|----------------|-----------------------|-------------|\n"
            text = text.replace(separator, separator + "| WR-04 | new review scope | Open pending independent review |\n")
            validation.write_text(text, encoding="utf-8")
            self.run_checker(documents)

    def test_checker_rejects_contradictory_records(self) -> None:
        mutations = {
            "yaml disposition": lambda text: text.replace("disposition: open", "disposition: fixed", 1),
            "yaml severity": lambda text: text.replace("severity: critical", "severity: warning", 1),
            "table disposition": lambda text: text.replace("| CR-02 | critical | open |", "| CR-02 | critical | fixed |"),
            "severity": lambda text: text.replace("| CR-02 | critical | open |", "| CR-02 | warning | open |"),
            "duplicate id": lambda text: text.replace("| CR-02 | critical | open |", "| CR-02 | critical | open |\n| CR-02 | critical | open |"),
            "drop yaml id": lambda text: re.sub(r"(?ms)^  - id: WR-03\n.*?(?=^  - id:|^open:)", "", text),
            "count": lambda text: text.replace("open: 4", "open: 99", 1),
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
            ("current closure", "DISPOSITION", lambda text: text.replace("| CR-02 | critical | open |", "| CR-02 | critical | fixed |")),
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
            ("HOST-02 observed", "VERIFICATION", lambda text: re.sub(r"(?m)^(\| HOST-02 \|.*\| )\? NEEDS HUMAN( \|.*)$", r"\1pass\2", text)),
            ("QUAL-03 observed", "VERIFICATION", lambda text: re.sub(r"(?m)^(\| QUAL-03 \|.*\| )\? NEEDS HUMAN( \|.*)$", r"\1pass\2", text)),
        )
        for label, name, transform in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                mutate_document(documents, name, transform)
                with self.assertRaises(AssertionError):
                    self.run_checker(documents)


if __name__ == "__main__":
    unittest.main()
