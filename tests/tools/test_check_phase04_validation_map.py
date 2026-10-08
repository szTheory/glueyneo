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

    verification = copied["VERIFICATION"]
    current_report = verification.read_text(encoding="utf-8")
    goal_rows = validation_map.table_rows(current_report, "| # | Truth | Status | Evidence |")
    if not any(len(row) == 4 and row[0] == "3" and
               "actual app/load/presentation/input/unload/exit were not observed" in row[3]
               for row in goal_rows):
        raise AssertionError("source verification report lacks current actual frontend uncertainty evidence")

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


def add_current_warning(
    documents: dict[str, Path], finding_id: str, title: str, *, existing_record: bool = True
) -> None:
    """Seed one warning into the copied review, independent of the live report."""
    review_path = documents["REVIEW"]
    review = review_path.read_text(encoding="utf-8")
    if finding_id in validation_map.parse_review_findings(review):
        raise AssertionError(f"synthetic review ID already exists: {finding_id}")
    review_path.write_text(
        review + f"\n\n## Warnings\n\n### {finding_id}: {title}\n\n"
        "**Issue:** Synthetic current warning.\n\n**Fix:** Keep the fixture self-contained.\n",
        encoding="utf-8",
    )
    if existing_record:
        disposition = documents["DISPOSITION"]
        text = disposition.read_text(encoding="utf-8")
        text, changed = re.subn(
            rf"(?m)^(\| {re.escape(finding_id)} \| warning \| open \| )[^\n]*( \|)$",
            rf"\g<1>04-REVIEW.md current\g<2>",
            text,
            count=1,
        )
        if changed != 1:
            raise AssertionError(f"disposition provenance for {finding_id} is missing")
        disposition.write_text(text, encoding="utf-8")


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


def close_disposition_record(text: str, finding_id: str) -> str:
    sections = text.split("---", 2)
    if len(sections) != 3:
        raise AssertionError("disposition frontmatter is malformed")
    block = re.search(rf"(?ms)^  - id: {re.escape(finding_id)}\n(.*?)(?=^  - id: |^open:)", sections[1])
    if block is None:
        raise AssertionError(f"disposition record {finding_id} is missing")
    changed_block = re.sub(r"(?m)^    disposition: open$", "    disposition: fixed", block.group(0), count=1)
    if changed_block == block.group(0):
        raise AssertionError(f"disposition record {finding_id} was not open")
    frontmatter = sections[1].replace(block.group(0), changed_block, 1)
    count = re.search(r"(?m)^open: (\d+)$", frontmatter)
    if count is None:
        raise AssertionError("disposition open count is missing")
    frontmatter = re.sub(r"(?m)^open: \d+$", f"open: {int(count.group(1)) - 1}", frontmatter, count=1)
    body, changed_rows = re.subn(
        rf"(?m)^\| {re.escape(finding_id)} \| ([^|]+) \| open \|",
        rf"| {finding_id} | \1 | fixed |", sections[2], count=1,
    )
    if changed_rows != 1:
        raise AssertionError(f"disposition table row {finding_id} was not changed")
    return f"---{frontmatter}---{body}"


def add_info_finding(documents: dict[str, Path], crosswalk_severity: str = "info") -> str:
    finding_id = "IN-99"
    records = validation_map.parse_disposition_yaml(documents["DISPOSITION"].read_text(encoding="utf-8"))
    review_ids = validation_map.parse_review_findings(documents["REVIEW"].read_text(encoding="utf-8"))
    if finding_id in records or finding_id in review_ids:
        raise AssertionError(f"synthetic Info ID collides with current records: {finding_id}")
    mutate_document(documents, "REVIEW", lambda text: text + (
        f"\n## Info\n\n### {finding_id}: Informational diagnostic note [INFO]\n\n"
        "**Issue:** Synthetic informational finding.\n\n**Fix:** Record consistently.\n"
    ))
    disposition = documents["DISPOSITION"]
    text = disposition.read_text(encoding="utf-8")
    counts = re.search(r"(?m)^open: (\d+)\ntotal: (\d+)$", text)
    if counts is None:
        raise AssertionError("current disposition counts are missing")
    open_count, total_count = map(int, counts.groups())
    text = re.sub(r"(?m)^open: \d+\ntotal: \d+$",
        f'  - id: {finding_id}\n    severity: info\n    disposition: open\n'
        f'    title: "Informational diagnostic note"\nopen: {open_count + 1}\ntotal: {total_count + 1}',
        text, count=1)
    disposition_separator = "|---------|----------|-------------|--------|\n"
    text = text.replace(
        disposition_separator,
        disposition_separator + f"| {finding_id} | info | open | synthetic Info fixture |\n",
        1,
    )
    disposition.write_text(text, encoding="utf-8")
    validation = documents["VALIDATION"]
    lines = validation.read_text(encoding="utf-8").splitlines()
    header = next(index for index, line in enumerate(lines) if line.startswith("| Review Finding |"))
    lines.insert(header + 2, f"| {finding_id} | {crosswalk_severity} | synthetic Info scope | open |")
    validation.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return finding_id


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
            report = documents["VERIFICATION"]
            original = report.read_text(encoding="utf-8")
            mutated = original.replace(
                "The actual app/load/presentation/input/unload/exit were not observed. ",
                "The frontend was observed. ", 1,
            )
            self.assertNotEqual(mutated, original, "frontend uncertainty removal was a no-op")
            report.write_text(mutated, encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "actual pinned-app observations are unobserved"):
                self.run_checker(documents)

    def test_checker_accepts_a_new_current_finding_with_matching_records(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase04-new-finding-") as temporary:
            documents = reconciled_review_documents(Path(temporary))
            self.assertNotIn("WR-99", validation_map.parse_review_findings(documents["REVIEW"].read_text(encoding="utf-8")))
            add_current_warning(documents, "WR-99", "New current warning [WARNING]", existing_record=False)
            path = documents["DISPOSITION"]
            content = path.read_text(encoding="utf-8")
            counts = re.search(r"(?m)^open: (\d+)\ntotal: (\d+)$", content)
            if counts is None:
                raise AssertionError("current disposition counts are missing")
            open_count, total_count = map(int, counts.groups())
            content = re.sub(r"(?m)^open: \d+\ntotal: \d+$",
                f'  - id: WR-99\n    severity: warning\n    disposition: open\n'
                f'    title: "New current warning"\nopen: {open_count + 1}\ntotal: {total_count + 1}',
                content, count=1)
            disposition_lines = content.splitlines()
            table_header = next(index for index, line in enumerate(disposition_lines) if line.startswith("| Finding | Severity | Disposition | Source |"))
            disposition_lines.insert(table_header + 2, "| WR-99 | warning | open | synthetic current review |")
            content = "\n".join(disposition_lines) + "\n"
            path.write_text(content, encoding="utf-8")
            validation = documents["VALIDATION"]
            text = validation.read_text(encoding="utf-8")
            lines = text.splitlines()
            header = next(index for index, line in enumerate(lines) if line.startswith("| Review Finding |"))
            lines.insert(header + 2, "| WR-99 | warning | new review scope | open |")
            text = "\n".join(lines) + "\n"
            validation.write_text(text, encoding="utf-8")
            self.assertIn("WR-99", validation_map.parse_review_findings(documents["REVIEW"].read_text(encoding="utf-8")))
            self.run_checker(documents)

    def test_checker_accepts_info_finding_with_matching_severity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase04-info-finding-") as temporary:
            documents = reconciled_review_documents(Path(temporary))
            finding_id = add_info_finding(documents)
            self.assertIn(finding_id, validation_map.parse_review_findings(documents["REVIEW"].read_text(encoding="utf-8")))
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
            finding_id = add_info_finding(documents, crosswalk_severity="warning")
            with self.assertRaisesRegex(AssertionError, rf"{finding_id}.*severity"):
                self.run_checker(documents)

    def test_checker_rejects_contradictory_records(self) -> None:
        mutations = {
            "yaml disposition": lambda text: text.replace("disposition: open", "disposition: fixed", 1),
            "yaml severity": lambda text: text.replace("severity: critical", "severity: warning", 1),
            "table disposition": lambda text: text.replace("| CR-03 | critical | open |", "| CR-03 | critical | fixed |"),
            "severity": lambda text: text.replace("| CR-03 | critical | open |", "| CR-03 | warning | open |"),
            "duplicate id": lambda text: text.replace("| CR-03 | critical | open |", "| CR-03 | critical | open |\n| CR-03 | critical | open |"),
            "drop yaml id": lambda text: re.sub(r"(?ms)^  - id: WR-03\n.*?(?=^  - id:|^open:)", "", text),
            "count": lambda text: re.sub(r"(?m)^open: (\d+)$", lambda match: f"open: {int(match.group(1)) + 1}", text, count=1),
            "total count": lambda text: re.sub(r"(?m)^total: (\d+)$", lambda match: f"total: {int(match.group(1)) + 1}", text, count=1),
        }
        for label, transform in mutations.items():
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                before = documents["DISPOSITION"].read_text(encoding="utf-8")
                after = transform(before)
                self.assertNotEqual(after, before, f"{label} mutation did not change its fixture")
                mutate_document(documents, "DISPOSITION", lambda _text: after)
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

    def test_checker_rejects_missing_or_duplicate_wr06_provenance_and_crosswalk(self) -> None:
        mutations = (
            ("missing provenance", "DISPOSITION", lambda text: text.replace(
                "| WR-06 | warning | open | 04-REVIEW.md current (not in the current review) |", "| WR-06 | warning | open | - |", 1)),
            ("missing crosswalk", "VALIDATION", lambda text: re.sub(r"(?m)^\| WR-06 \|[^\n]*\n", "", text, count=1)),
            ("duplicate crosswalk", "VALIDATION", lambda text: text.replace(
                "| WR-06 | warning | Alternate affirmative frontend app-load claim passes alongside Pending/unknown | open |\n",
                "| WR-06 | warning | Alternate affirmative frontend app-load claim passes alongside Pending/unknown | open |\n"
                "| WR-06 | warning | duplicate frontend documentation-gate claim | open |\n", 1)),
        )
        for label, name, transform in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                before = documents[name].read_text(encoding="utf-8")
                after = transform(before)
                self.assertNotEqual(after, before, f"{label} mutation did not change its fixture")
                mutate_document(documents, name, lambda _text: after)
                with self.assertRaises(AssertionError):
                    self.run_checker(documents)

    def test_checker_rejects_coherent_false_closure_of_current_wr06(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase04-wr06-closure-") as temporary:
            documents = reconciled_review_documents(Path(temporary))
            records = validation_map.parse_disposition_yaml(documents["DISPOSITION"].read_text(encoding="utf-8"))
            add_current_warning(documents, "WR-06", records["WR-06"]["title"])
            disposition = documents["DISPOSITION"]
            original = disposition.read_text(encoding="utf-8")
            text = close_disposition_record(original, "WR-06")
            self.assertNotEqual(text, original, "WR-06 closure fixture was a no-op")
            disposition.write_text(text, encoding="utf-8")
            set_crosswalk_disposition(documents, "WR-06", "fixed")
            with self.assertRaisesRegex(AssertionError, "current finding WR-06 is recorded as fixed"):
                self.run_checker(documents)

    def test_checker_rejects_security_or_frontend_claim_contradictions(self) -> None:
        mutations = (
            ("security count", "SECURITY", lambda text: text.replace("threats_open: 4", "threats_open: 3", 1)),
            ("security row", "SECURITY", lambda text: re.sub(r"(?m)^(\| T-04-11 \|[^\n]*\| )open(\s*\|)$", r"\1closed\2", text)),
            ("missing required medium threat", "SECURITY", lambda text: re.sub(r"(?m)^\| T-04-34 \|[^\n]*\n", "", text, count=1)),
            ("medium threat downgraded", "SECURITY", lambda text: text.replace("| T-04-34 | Tampering | `check_docs()` frontend qualification status | medium | mitigate |", "| T-04-34 | Tampering | `check_docs()` frontend qualification status | low | mitigate |", 1)),
            ("HOST-02 observed", "VERIFICATION", lambda text: re.sub(r"(?m)^(\| HOST-02 \|.*\| )\? NEEDS HUMAN(?: / PENDING)?( \|.*)$", r"\1pass\2", text)),
            ("QUAL-03 observed", "VERIFICATION", lambda text: re.sub(r"(?m)^(\| QUAL-03 \|[^\n]*\| )✗ BLOCKED / PARTIAL( \|.*)$", r"\1✓ SATISFIED\2", text)),
        )
        for label, name, transform in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                before = documents[name].read_text(encoding="utf-8")
                after = transform(before)
                self.assertNotEqual(after, before, f"{label} mutation did not change its fixture")
                mutate_document(documents, name, lambda _text: after)
                with self.assertRaises(AssertionError):
                    self.run_checker(documents)

if __name__ == "__main__":
    unittest.main()
