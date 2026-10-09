#!/usr/bin/env python3
"""Behavioral controls for Phase 04 validation-map reconciliation."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))
import check_phase04_validation_map as validation_map  # noqa: E402


PHASE = ROOT / ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer"
COMMANDS = {
    "python3 tests/tools/test_verify_playable.py -v": 27,
    "python3 tests/libretro/test_retroarch_smoke.py -v": 27,
}


def reconciled_review_documents(directory: Path) -> dict[str, Path]:
    """Build a controlled current-review baseline over copied phase evidence."""
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
    # Mutations always start from the actual current source documents. In
    # particular, do not replace the review or append expected evidence here:
    # that would let a stale fixture mask source drift.

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
    body = re.sub(
        r"(?m)^\| WR-01 \| warning \| open \|[^\n]*$",
        "| WR-01 | warning | open | Historical review `04-REVIEW.md` at `87f8d4c`; reviewed revision `870848e553aca6e43f6fec8ae0acefac87270f5b`, 2026-10-08T23:46:34Z; carried open |",
        body,
        count=1,
    )
    body = body.replace("| WR-02 | warning | open | - (not in the current review) |", "| WR-02 | warning | open | Carried from prior review; no new independent evidence |")
    body = body.replace("| WR-03 | warning | open | - (not in the current review) |", "| WR-03 | warning | open | Carried from prior review; no new independent evidence |")
    disposition_path.write_text(f"---{frontmatter}---{body}", encoding="utf-8")
    return copied


def mutate_document(documents: dict[str, Path], name: str, transform) -> None:
    path = documents[name]
    path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")


def with_frontend_goal_evidence(text: str, evidence: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("| 3 |"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            raise AssertionError("frontend goal row is malformed")
        cells[3] = evidence
        lines[index] = "| " + " | ".join(cells) + " |"
        return "\n".join(lines) + "\n"
    raise AssertionError("frontend goal row is missing")


def add_frontend_success_claim(text: str) -> str:
    rows = validation_map.table_rows(text, "| # | Truth | Status | Evidence |")
    frontend = next((row for row in rows if len(row) == 4 and row[0] == "3"), None)
    if frontend is None:
        raise AssertionError("frontend goal row is missing")
    return with_frontend_goal_evidence(
        text, frontend[3] + " The pinned RetroArch app displayed guest pixels."
    )


def add_frontend_claim(text: str, claim: str) -> str:
    rows = validation_map.table_rows(text, "| # | Truth | Status | Evidence |")
    frontend = next((row for row in rows if len(row) == 4 and row[0] == "3"), None)
    if frontend is None:
        raise AssertionError("frontend goal row is missing")
    return with_frontend_goal_evidence(text, frontend[3] + " " + claim)


def with_requirement_status(text: str, requirement_id: str, status: str) -> str:
    lines = text.splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.startswith("| Requirement | Plans | Status | Evidence |"))
    for index, line in enumerate(lines[header_index + 2:], start=header_index + 2):
        if not line.startswith("|"):
            break
        if not line.startswith(f"| {requirement_id} |"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) not in {4, 5}:
            raise AssertionError(f"requirement row {requirement_id} is malformed")
        cells[3 if len(cells) == 5 else 2] = status
        lines[index] = "| " + " | ".join(cells) + " |"
        return "\n".join(lines) + "\n"
    raise AssertionError(f"requirement row {requirement_id} is missing")


def with_requirement_evidence(text: str, requirement_id: str, evidence: str) -> str:
    lines = text.splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.startswith("| Requirement | Plans | Status | Evidence |"))
    for index, line in enumerate(lines[header_index + 2:], start=header_index + 2):
        if not line.startswith("|"):
            break
        if not line.startswith(f"| {requirement_id} |"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) not in {4, 5}:
            raise AssertionError(f"requirement row {requirement_id} is malformed")
        cells[4 if len(cells) == 5 else 3] = evidence
        lines[index] = "| " + " | ".join(cells) + " |"
        return "\n".join(lines) + "\n"
    raise AssertionError(f"requirement row {requirement_id} is missing")


def with_table_cell(text: str, header: str, key: str, column: int, value: str) -> str:
    lines = text.splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith(header)), None)
    if header_index is None:
        raise AssertionError(f"table header is missing: {header}")
    for index in range(header_index + 2, len(lines)):
        if not lines[index].startswith("|"):
            break
        cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        if cells and cells[0] == key:
            if not 0 <= column < len(cells):
                raise AssertionError(f"column {column} is outside row {key}")
            cells[column] = value
            lines[index] = "| " + " | ".join(cells) + " |"
            return "\n".join(lines) + "\n"
    raise AssertionError(f"row is missing for {key!r} in {header}")


def with_duplicate_requirement(text: str, requirement_id: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(f"| {requirement_id} |"):
            lines.insert(index + 1, line)
            return "\n".join(lines) + "\n"
    raise AssertionError(f"requirement row {requirement_id} is missing")


def with_malformed_duplicate_requirement(text: str, requirement_id: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(f"| {requirement_id} |"):
            lines.insert(index + 1, line[:-1] + " | contradictory extra status |")
            return "\n".join(lines) + "\n"
    raise AssertionError(f"requirement row {requirement_id} is missing")


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


def commit_review_source_tree(root: Path) -> str:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Validation Test"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "validation@example.invalid"], check=True)
    for index, relative in enumerate(validation_map.REQUIRED_REVIEWED_PATHS):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"reviewed source {index}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", *validation_map.REQUIRED_REVIEWED_PATHS], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "reviewed source"], check=True)
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def review_frontmatter(revision: str, paths: tuple[str, ...] | None = None) -> str:
    reviewed = paths or validation_map.REQUIRED_REVIEWED_PATHS
    entries = "".join(f"  - {path}\n" for path in reviewed)
    return f"---\nreviewed_revision: {revision}\nfiles_reviewed: {len(reviewed)}\nfiles_reviewed_list:\n{entries}---\n"
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
                with mock.patch.object(validation_map, "require_reviewed_source_identity"):
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
            mutated = with_frontend_goal_evidence(
                original, "Actual pinned RetroArch fixture load and input were observed."
            )
            self.assertNotEqual(mutated, original, "frontend uncertainty removal was a no-op")
            report.write_text(mutated, encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "verification goal evidence"):
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
            set_crosswalk_disposition(documents, "WR-06", "  OpEn  ")
            self.run_checker(documents)

    def test_checker_rejects_contradictory_or_extra_crosswalk_states(self) -> None:
        for state in ("fixed; not open", "not open", "open; fixed", "unrecognized"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                set_crosswalk_disposition(documents, "WR-06", state)
                with self.assertRaisesRegex(AssertionError, r"WR-06 disposition"):
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
            "yaml disposition": (lambda text: text.replace("disposition: open", "disposition: fixed", 1),
                                 "WR-09 severity or disposition differs between YAML and table"),
            "yaml severity": (lambda text: text.replace("severity: critical", "severity: warning", 1),
                              "CR-03 severity or disposition differs between YAML and table"),
            "table disposition": (lambda text: text.replace("| WR-06 | warning | open |", "| WR-06 | warning | fixed |"),
                                  "WR-06 severity or disposition differs between YAML and table"),
            "severity": (lambda text: text.replace("| CR-03 | critical | fixed |", "| CR-03 | warning | fixed |"),
                         "CR-03 severity or disposition differs between YAML and table"),
            "duplicate id": (lambda text: re.sub(r"(?m)^(\| CR-03 \|[^\n]*)$", r"\1\n\1", text, count=1),
                             "duplicate disposition table ID CR-03"),
            "drop yaml id": (lambda text: re.sub(r"(?ms)^  - id: WR-03\n.*?(?=^  - id:|^open:)", "", text),
                             "disposition YAML and table IDs differ"),
            "count": (lambda text: re.sub(r"(?m)^open: (\d+)$", lambda match: f"open: {int(match.group(1)) + 1}", text, count=1),
                      "disposition YAML open count differs from its records"),
            "total count": (lambda text: re.sub(r"(?m)^total: (\d+)$", lambda match: f"total: {int(match.group(1)) + 1}", text, count=1),
                            "disposition YAML total count differs from its records"),
        }
        for label, (transform, expected_error) in mutations.items():
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                before = documents["DISPOSITION"].read_text(encoding="utf-8")
                after = transform(before)
                self.assertNotEqual(after, before, f"{label} mutation did not change its fixture")
                mutate_document(documents, "DISPOSITION", lambda _text: after)
                with self.assertRaisesRegex(AssertionError, re.escape(expected_error)):
                    self.run_checker(documents)

    def test_checker_rejects_missing_crosswalk_and_closed_current_finding(self) -> None:
        for label, name, transform, expected_error in (
            ("crosswalk", "VALIDATION", lambda text: re.sub(r"(?m)^\| WR-01 \|[^\n]*\n", "", text),
             "review crosswalk differs from retained disposition history"),
        ):
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                mutate_document(documents, name, transform)
                with self.assertRaisesRegex(AssertionError, re.escape(expected_error)):
                    self.run_checker(documents)

    def test_checker_rejects_missing_or_duplicate_wr06_provenance_and_crosswalk(self) -> None:
        mutations = (
            ("missing provenance", "DISPOSITION", lambda text: re.sub(
                r"(?m)^(\| WR-06 \| warning \| open \| ).*( \|)$", r"\1-\2", text, count=1),
             "WR-06 has no provenance source"),
            ("missing crosswalk", "VALIDATION", lambda text: re.sub(r"(?m)^\| WR-06 \|[^\n]*\n", "", text, count=1),
             "review crosswalk differs from retained disposition history"),
            ("duplicate crosswalk", "VALIDATION", lambda text: re.sub(
                r"(?m)^(\| WR-06 \| warning \|[^\n]+\| open \|)$",
                lambda match: match.group(1) + chr(10) + "| WR-06 | warning | duplicate frontend documentation-gate claim | open |",
                text, count=1),
             "duplicate validation crosswalk ID WR-06"),
        )
        for label, name, transform, expected_error in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                before = documents[name].read_text(encoding="utf-8")
                after = transform(before)
                self.assertNotEqual(after, before, f"{label} mutation did not change its fixture")
                mutate_document(documents, name, lambda _text: after)
                with self.assertRaisesRegex(AssertionError, re.escape(expected_error)):
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
            ("security count", "SECURITY", lambda text: text.replace("threats_open: 4", "threats_open: 3", 1),
             "security frontmatter blocking count differs from high/open register rows"),
            ("security row", "SECURITY", lambda text: re.sub(r"(?m)^(\| T-04-11 \|[^\n]*\| )open(\s*\|)$", r"\1closed\2", text),
             "security frontmatter blocking count differs from high/open register rows"),
            ("missing current medium threat", "SECURITY", lambda text: re.sub(r"(?m)^\| T-04-43 \|[^\n]*\n", "", text, count=1),
             "the three expected medium/open findings differ from the active security register"),
            ("current medium threat downgraded", "SECURITY", lambda text: re.sub(
                r"(?m)^(\| T-04-43 \|[^|]*\|[^|]*\| )medium( \|)", r"\1low\2", text, count=1,
            ), "the three expected medium/open findings differ from the active security register"),
            ("HOST-02 observed", "VERIFICATION", lambda text: re.sub(r"(?m)^(\| HOST-02 \|.*\| )\? NEEDS HUMAN(?: / PENDING)?( \|.*)$", r"\1pass\2", text),
             "HOST-02 is not explicitly marked as awaiting human evidence"),
            ("QUAL-03 observed", "VERIFICATION", lambda text: with_requirement_status(text, "QUAL-03", "✓ SATISFIED"),
             "QUAL-03 is not explicitly marked blocked, partial, or pending human evidence"),
            ("HOST-02 positive evidence", "VERIFICATION", lambda text: with_requirement_evidence(
                text, "HOST-02", "Actual pinned RetroArch app loaded and accepted input; game output was visible."
            ), "HOST-02 evidence no longer matches the current actual-app uncertainty record"),
            ("QUAL-03 positive evidence", "VERIFICATION", lambda text: with_requirement_evidence(
                text, "QUAL-03", "Procedure documented; successful actual frontend load remains unknown; the app displayed pixels."
            ), "QUAL-03 evidence no longer explicitly marks actual frontend load unobserved or unknown"),
            ("qualification goal positive evidence", "VERIFICATION", lambda text: with_table_cell(
                text, "| # | Truth | Status | Evidence |", "5", 3, "Actual pinned frontend loaded successfully."
            ), "current qualification goal evidence no longer preserves the actual frontend unknown boundary"),
            ("qualification artifact positive evidence", "VERIFICATION", lambda text: with_table_cell(
                text, "| Artifact/link | Status | Evidence |",
                "Qualification input/log → redaction → retained/printed diagnostics", 2,
                "Pinned RetroArch loaded and displayed pixels."
            ), "qualification artifact/link asserts unobserved frontend success"),
            ("libretro artifact positive evidence", "VERIFICATION", lambda text: with_table_cell(
                text, "| Artifact/link | Status | Evidence |", "Libretro content → native load/frame → synchronous video callback", 2,
                "Adapter calls and callback contract exist; RetroArch displayed guest pixels."
            ), "libretro artifact/link evidence overstates actual frontend behavior"),
            ("qualification link positive evidence", "VERIFICATION", lambda text: with_table_cell(
                text, "| Artifact/link | Status | Evidence |", "Qualification input/log → redaction → retained/printed diagnostics", 2,
                "Pinned RetroArch launched and displayed guest pixels."
            ), "qualification artifact/link asserts unobserved frontend success"),
            ("libretro link positive evidence", "VERIFICATION", lambda text: with_table_cell(
                text, "| Artifact/link | Status | Evidence |", "Libretro content → native load/frame → synchronous video callback", 2,
                "The actual app loaded successfully."
            ), "libretro artifact/link evidence overstates actual frontend behavior"),
            ("actual frontend spot-check passed", "VERIFICATION", lambda text: with_table_cell(
                text, "| Behavior | Command/result | Status |",
                "Actual pinned RetroArch", 1,
                "Pinned RetroArch loaded, displayed pixels, and accepted input."
            ), "actual frontend spot-check is no longer marked manual-only and unrun"),
            ("evidence-map spot-check success claim", "VERIFICATION", lambda text: with_table_cell(
                text, "| Behavior | Command/result | Status |",
                "Review/security evidence-map mutation suite", 1,
                "Passed; actual pinned RetroArch loaded and displayed guest pixels."
            ), "behavioral spot-check claims actual frontend success"),
            ("qualification test spot-check success claim", "VERIFICATION", lambda text: with_table_cell(
                text, "| Behavior | Command/result | Status |",
                "Qualification, path/redaction, snapshot and guide claims", 1,
                "23/23 passed; actual pinned RetroArch loaded successfully."
            ), "behavioral spot-check claims actual frontend success"),
            ("GUI-free runner spot-check success claim", "VERIFICATION", lambda text: with_table_cell(
                text, "| Behavior | Command/result | Status |",
                "GUI-free frontend diagnostics and smoke contract", 1,
                "27/27 passed; actual pinned RetroArch displayed pixels."
            ), "behavioral spot-check claims actual frontend success"),
            ("docs gate spot-check success claim", "VERIFICATION", lambda text: with_table_cell(
                text, "| Behavior | Command/result | Status |",
                "Consumer docs gate", 1,
                "Passed; the pinned app loaded and presented output."
            ), "behavioral spot-check claims actual frontend success"),
            ("duplicate HOST-02", "VERIFICATION", lambda text: with_duplicate_requirement(text, "HOST-02"),
             "current frontend report row 'HOST-02' is absent or duplicated"),
            ("duplicate QUAL-03", "VERIFICATION", lambda text: with_duplicate_requirement(text, "QUAL-03"),
             "current frontend report row 'QUAL-03' is absent or duplicated"),
            ("malformed duplicate HOST-02", "VERIFICATION", lambda text: with_malformed_duplicate_requirement(text, "HOST-02"),
             "current frontend report row 'HOST-02' is absent or duplicated"),
            ("malformed duplicate QUAL-03", "VERIFICATION", lambda text: with_malformed_duplicate_requirement(text, "QUAL-03"),
             "current frontend report row 'QUAL-03' is absent or duplicated"),
            ("actual frontend success claim", "VERIFICATION", add_frontend_success_claim,
             "current verification goal evidence must explicitly mark actual pinned-app load unobserved or unknown and contain no success claim"),
            ("confirmed gameplay presentation", "VERIFICATION", lambda text: add_frontend_claim(text, "Gameplay presentation was confirmed."),
             "current verification goal evidence must explicitly mark actual pinned-app load unobserved or unknown and contain no success claim"),
            ("successful display output", "VERIFICATION", lambda text: add_frontend_claim(text, "Display output was successful."),
             "current verification goal evidence must explicitly mark actual pinned-app load unobserved or unknown and contain no success claim"),
        )
        for label, name, transform, expected_error in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                before = documents[name].read_text(encoding="utf-8")
                after = transform(before)
                self.assertNotEqual(after, before, f"{label} mutation did not change its fixture")
                mutate_document(documents, name, lambda _text: after)
                with self.assertRaisesRegex(AssertionError, re.escape(expected_error)):
                    self.run_checker(documents)

    def test_security_register_requires_exact_four_high_and_three_medium_open_rows(self) -> None:
        mutations = (
            ("remove current medium", lambda text: re.sub(r"(?m)^\| T-04-43 \|[^\n]*\n", "", text, count=1),
             "the three expected medium/open findings differ from the active security register"),
            ("close current medium", lambda text: re.sub(r"(?m)^(\| T-04-43 \|[^\n]*\| )open( \|)$", r"\1closed\2", text, count=1),
             "the three expected medium/open findings differ from the active security register"),
            ("unexpected open", lambda text: re.sub(r"(?m)^(\| T-04-39 \|[^\n]*\| )closed( \|)$", r"\1open\2", text, count=1),
             "the three expected medium/open findings differ from the active security register"),
            ("duplicate row", lambda text: re.sub(
                r"(?m)^(\| T-04-38 \|[^\n]*)$", r"\1\n\1", text, count=1,
            ), "duplicate security register ID T-04-38"),
        )
        for label, transform, expected_error in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                before = documents["SECURITY"].read_text(encoding="utf-8")
                after = transform(before)
                self.assertNotEqual(after, before, f"{label} mutation was a no-op")
                mutate_document(documents, "SECURITY", lambda _text: after)
                with self.assertRaisesRegex(AssertionError, re.escape(expected_error)):
                    self.run_checker(documents)

    def test_copied_wr01_history_requires_exact_historical_review_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            documents = reconciled_review_documents(Path(temporary))
            disposition = documents["DISPOSITION"]
            source = "Historical review `04-REVIEW.md` at `87f8d4c`; reviewed revision `870848e553aca6e43f6fec8ae0acefac87270f5b`, 2026-10-08T23:46:34Z; carried open"
            self.assertIn(source, disposition.read_text(encoding="utf-8"))
            self.run_checker(documents)
            text = disposition.read_text(encoding="utf-8").replace(source, "-", 1)
            disposition.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "WR-01.*historical review source"):
                self.run_checker(documents)

    def test_review_identity_accepts_exact_paths_and_source_bytes(self) -> None:
        self.assertTrue(callable(getattr(validation_map, "require_reviewed_source_identity", None)),
                        "the checker must validate reviewed paths and revision content identity")
        with tempfile.TemporaryDirectory(prefix="phase04-review-identity-") as temporary:
            repository = Path(temporary)
            revision = commit_review_source_tree(repository)
            validation_map.require_reviewed_source_identity(review_frontmatter(revision), repository=repository)

    def test_review_identity_rejects_missing_path_stale_revision_and_changed_bytes(self) -> None:
        self.assertTrue(callable(getattr(validation_map, "require_reviewed_source_identity", None)),
                        "the checker must validate reviewed paths and revision content identity")
        with tempfile.TemporaryDirectory(prefix="phase04-review-identity-") as temporary:
            repository = Path(temporary)
            revision = commit_review_source_tree(repository)
            omitted = tuple(path for path in validation_map.REQUIRED_REVIEWED_PATHS if path != "tests/libretro/retroarch_smoke.py")
            with self.assertRaisesRegex(AssertionError, "reviewed path list"):
                validation_map.require_reviewed_source_identity(review_frontmatter(revision, omitted), repository=repository)
            false_path = tuple(
                "tests/libretro/test_retroarch_smoke.py" if path == "tests/libretro/retroarch_smoke.py" else path
                for path in validation_map.REQUIRED_REVIEWED_PATHS
            )
            with self.assertRaisesRegex(AssertionError, "reviewed path list"):
                validation_map.require_reviewed_source_identity(review_frontmatter(revision, false_path), repository=repository)
            extra_path = validation_map.REQUIRED_REVIEWED_PATHS + ("tests/unreviewed/nonexistent.py",)
            with self.assertRaisesRegex(AssertionError, "exact required gate and sanitizer scope"):
                validation_map.require_reviewed_source_identity(review_frontmatter(revision, extra_path), repository=repository)
            with self.assertRaisesRegex(AssertionError, "does not exist"):
                validation_map.require_reviewed_source_identity(review_frontmatter("f" * 40), repository=repository)
            target = repository / validation_map.REQUIRED_REVIEWED_PATHS[0]
            target.write_text("changed after review\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "differs from reviewed revision"):
                validation_map.require_reviewed_source_identity(review_frontmatter(revision), repository=repository)

    def test_review_identity_rejects_duplicate_revision_keys(self) -> None:
        for second_value in ("second-valid", "malformed"):
            with self.subTest(second_value=second_value), tempfile.TemporaryDirectory(
                prefix="phase04-review-duplicate-revision-"
            ) as temporary:
                repository = Path(temporary)
                first_revision = commit_review_source_tree(repository)
                if second_value == "second-valid":
                    subprocess.run(
                        ["git", "-C", str(repository), "commit", "--allow-empty", "-qm", "second valid revision"],
                        check=True,
                    )
                    duplicate_value = subprocess.run(
                        ["git", "-C", str(repository), "rev-parse", "HEAD"], check=True, text=True,
                        stdout=subprocess.PIPE,
                    ).stdout.strip()
                    self.assertNotEqual(first_revision, duplicate_value)
                else:
                    duplicate_value = "malformed-not-a-commit"
                review = review_frontmatter(first_revision).replace(
                    f"reviewed_revision: {first_revision}\n",
                    f"reviewed_revision: {first_revision}\nreviewed_revision: {duplicate_value}\n",
                    1,
                )
                with self.assertRaisesRegex(AssertionError, "exactly one reviewed_revision field"):
                    validation_map.require_reviewed_source_identity(review, repository=repository)

        with tempfile.TemporaryDirectory(prefix="phase04-review-malformed-revision-") as temporary:
            repository = Path(temporary)
            commit_review_source_tree(repository)
            malformed = review_frontmatter("malformed-not-a-commit")
            with self.assertRaisesRegex(AssertionError, "full lowercase immutable commit ID"):
                validation_map.require_reviewed_source_identity(malformed, repository=repository)

    def test_frontend_claim_grammar_rejects_render_screen_and_output_paraphrases(self) -> None:
        uncertain = "Actual pinned RetroArch load remains unknown; launch previously aborted before screenshot."
        positives = (
            "a frame was rendered to the window",
            "the screen was visible",
            "video output was confirmed",
            "control input worked",
            "content unloaded and RetroArch exited normally",
        )
        for claim in positives:
            with self.subTest(claim=claim):
                evidence = f"{uncertain} {claim}."
                self.assertFalse(validation_map.has_frontend_load_uncertainty(evidence, scope="goal"))
                self.assertTrue(validation_map.contains_frontend_success_claim(claim))
        self.assertTrue(validation_map.has_frontend_load_uncertainty(
            uncertain + " No frame was rendered to the window; no input or unload was observed.", scope="goal"
        ))

    def test_frontend_claim_grammar_rejects_control_success_without_subject_prefix(self) -> None:
        claim = "Controls worked as expected in RetroArch."
        self.assertTrue(validation_map.contains_frontend_success_claim(claim))
        self.assertFalse(validation_map.has_frontend_load_uncertainty(
            "Actual pinned RetroArch load remains unknown; " + claim, scope="goal"
        ))

    def test_report_claim_mutations_fail_across_every_current_frontend_surface(self) -> None:
        claims = (
            "A frame was rendered to the window.",
            "The screen was visible.",
            "Video output was confirmed.",
            "Guest pixels were displayed.",
            "Control input worked as expected.",
            "Content unloaded and RetroArch exited normally.",
        )
        for claim in claims:
            surfaces = (
                ("goal", lambda text: with_table_cell(text, "| # | Truth | Status | Evidence |", "3", 3,
                                                       validation_map.PINNED_FRONTEND_UNCERTAINTY_EVIDENCE + " " + claim),
                 "current verification goal evidence must explicitly mark actual pinned-app load unobserved or unknown and contain no success claim"),
                ("HOST-02 evidence", lambda text: with_requirement_evidence(text, "HOST-02",
                                                                               validation_map.HOST_FRONTEND_UNCERTAINTY_EVIDENCE + " " + claim),
                 "HOST-02 evidence no longer matches the current actual-app uncertainty record"),
                ("QUAL-03 evidence", lambda text: with_requirement_evidence(text, "QUAL-03",
                                                                               validation_map.QUAL_FRONTEND_UNCERTAINTY_EVIDENCE + " " + claim),
                 "QUAL-03 evidence no longer explicitly marks actual frontend load unobserved or unknown"),
                ("artifact/link", lambda text: with_table_cell(text, "| Artifact/link | Status | Evidence |",
                                                               "Libretro content → native load/frame → synchronous video callback", 2, claim),
                 "libretro artifact/link evidence overstates actual frontend behavior"),
                ("data-flow", lambda text: with_table_cell(text, "| Output | Source | Status |",
                                                           "Actual frontend state", 2, "? UNKNOWN; " + claim),
                 "frontend qualification data-flow no longer preserves actual-app unknown status"),
                ("spot-check", lambda text: with_table_cell(text, "| Behavior | Command/result | Status |",
                                                             "Actual pinned RetroArch", 1, claim),
                 "actual frontend spot-check is no longer marked manual-only and unrun"),
            )
            for surface, transform, expected_error in surfaces:
                with self.subTest(claim=claim, surface=surface), tempfile.TemporaryDirectory() as temporary:
                    documents = reconciled_review_documents(Path(temporary))
                    before = documents["VERIFICATION"].read_text(encoding="utf-8")
                    after = transform(before)
                    self.assertNotEqual(after, before, f"{surface} {claim!r} mutation was a no-op")
                    mutate_document(documents, "VERIFICATION", lambda _text: after)
                    with self.assertRaisesRegex(AssertionError, re.escape(expected_error)):
                        self.run_checker(documents)

    def test_pending_status_cells_reject_appended_frontend_observations(self) -> None:
        observations = (
            "actual pinned RetroArch app loaded successfully",
            "pinned RetroArch app displayed guest pixels",
            "RIGHT input moved the marker",
            "content unloaded and RetroArch exited normally",
        )
        for requirement_id in ("HOST-02", "QUAL-03"):
            for observation in observations:
                with self.subTest(requirement=requirement_id, observation=observation), tempfile.TemporaryDirectory() as temporary:
                    documents = reconciled_review_documents(Path(temporary))
                    status = "? NEEDS HUMAN / PENDING — " + observation
                    mutate_document(
                        documents,
                        "VERIFICATION",
                        lambda text, rid=requirement_id, value=status: with_requirement_status(text, rid, value),
                    )
                    expected_error = (
                        "HOST-02 is not explicitly marked as awaiting human evidence"
                        if requirement_id == "HOST-02"
                        else "QUAL-03 is not explicitly marked blocked, partial, or pending human evidence"
                    )
                    with self.assertRaisesRegex(AssertionError, re.escape(expected_error)):
                        self.run_checker(documents)

    def test_actual_frontend_spotcheck_requires_current_manual_unknown_state(self) -> None:
        mutations = (
            (1, "RetroArch launched successfully"),
            (2, "✓ VERIFIED"),
        )
        for column, value in mutations:
            with self.subTest(column=column, value=value), tempfile.TemporaryDirectory() as temporary:
                documents = reconciled_review_documents(Path(temporary))
                mutate_document(
                    documents,
                    "VERIFICATION",
                    lambda text, col=column, replacement=value: with_table_cell(
                        text, "| Behavior | Command/result | Status |", "Actual pinned RetroArch", col, replacement
                    ),
                )
                with self.assertRaisesRegex(AssertionError, "actual frontend spot-check"):
                    self.run_checker(documents)

    def test_frontend_uncertainty_is_bound_to_pinned_app_and_rejects_success_paraphrases(self) -> None:
        accepted = validation_map.PINNED_FRONTEND_UNCERTAINTY_EVIDENCE
        host_accepted = validation_map.HOST_FRONTEND_UNCERTAINTY_EVIDENCE
        qual_accepted = validation_map.QUAL_FRONTEND_UNCERTAINTY_EVIDENCE
        self.assertTrue(validation_map.has_frontend_load_uncertainty(accepted, scope="goal"))
        self.assertTrue(validation_map.has_frontend_load_uncertainty(host_accepted, scope="host"))
        self.assertTrue(validation_map.has_frontend_load_uncertainty(qual_accepted, scope="qual"))
        self.assertTrue(validation_map.has_frontend_load_uncertainty(
            validation_map.QUALIFICATION_GOAL_UNCERTAINTY_EVIDENCE, scope="qual_goal"
        ))
        self.assertTrue(validation_map.has_frontend_load_uncertainty(
            validation_map.QUALIFICATION_ARTIFACT_UNCERTAINTY_EVIDENCE, scope="qual_artifact"
        ))
        self.assertTrue(validation_map.has_frontend_load_uncertainty(
            validation_map.LIBRETRO_ARTIFACT_FRONTEND_BOUNDARY, scope="libretro_artifact"
        ))
        self.assertTrue(validation_map.has_frontend_load_uncertainty(
            validation_map.LIBRETRO_LINK_FRONTEND_BOUNDARY, scope="libretro_link"
        ))
        self.assertTrue(validation_map.has_frontend_load_uncertainty(
            validation_map.QUALIFICATION_RUNNER_UNCERTAINTY_EVIDENCE, scope="qual_runner"
        ))
        self.assertTrue(validation_map.has_frontend_load_uncertainty(qual_accepted, scope="goal"))
        self.assertTrue(validation_map.has_frontend_load_uncertainty(host_accepted, scope="qual"))
        rejected = (
            "Actual frontend load remains unknown; the pinned RetroArch app displayed guest pixels.",
            "Actual pinned RetroArch app load remains unknown; the app showed a guest frame.",
            "Actual pinned RetroArch app load remains unknown; the game screen was visible in the app.",
            "Actual pinned RetroArch app load remains unknown; gameplay presentation was confirmed.",
            "Actual pinned RetroArch app load remains unknown; display output was successful.",
            "Actual pinned RetroArch app load remains unknown; we saw the game screen.",
            "Actual pinned RetroArch app load remains unknown; video output passed.",
            "Actual pinned RetroArch app load remains unknown; the app produced guest video.",
            "Actual pinned RetroArch app load remains unknown; the screenshot contained game pixels.",
            "Actual pinned RetroArch app load remains unknown; we can see the game screen.",
            "Actual pinned RetroArch app load remains unknown; RetroArch launched.",
            "Actual pinned RetroArch app load remains unknown; logs confirm video output.",
            "Actual pinned RetroArch app load remains unknown; RIGHT input moved the marker.",
            "Actual pinned RetroArch app load remains unknown; content unloaded and RetroArch exited normally.",
            "Actual app load remains unknown; the app displayed guest pixels.",
        )
        for evidence in rejected:
            with self.subTest(evidence=evidence):
                self.assertFalse(validation_map.has_frontend_load_uncertainty(evidence, scope="goal"))

    def test_checker_rejects_stale_current_qualification_denominator(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase04-stale-denominator-") as temporary:
            documents = reconciled_review_documents(Path(temporary))
            report = documents["VALIDATION"]
            original = report.read_text(encoding="utf-8")
            mutated = original.replace(
                "Plan 04-22 current suite denominators: qualification 27/27; frontend 27/27.",
                "Plan 04-22 current suite denominators: qualification 25/25; frontend 27/27.",
                1,
            )
            self.assertNotEqual(mutated, original, "stale-denominator mutation was a no-op")
            report.write_text(mutated, encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "validation denominators"):
                self.run_checker(documents)

if __name__ == "__main__":
    unittest.main()
