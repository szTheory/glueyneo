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


def reconciled_review_documents(directory: Path) -> dict[str, Path]:
    """Model a fresh review after the repaired CR-01 finding is no longer reported."""
    documents = {
        "VALIDATION": PHASE / "04-VALIDATION.md",
        "SECURITY": PHASE / "04-SECURITY.md",
        "VERIFICATION": PHASE / "04-VERIFICATION.md",
        "DISPOSITION": PHASE / "04-REVIEW-DISPOSITION.md",
        "REVIEW": PHASE / "04-REVIEW.md",
    }
    copied: dict[str, Path] = {}
    for name, source in documents.items():
        destination = directory / source.name
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        copied[name] = destination

    validation = copied["VALIDATION"].read_text(encoding="utf-8")
    validation = re.sub(r"(?m)^\| CR-01 \|[^\n]*\n", "", validation)
    validation = validation.replace(
        "The historical CR-01 identity finding was fixed, but the current reused CR-01 ID names a distinct boolean-count bypass and remains open in the current disposition record.",
        "The historical CR-01 identity finding and the later boolean-count bypass are repaired; the fresh review no longer reports CR-01.",
    )
    validation = validation.replace(
        "All five current/carried review dispositions remain open until independent review.",
        "All four current/carried review dispositions remain open until independent review.",
    )
    copied["VALIDATION"].write_text(validation, encoding="utf-8")

    disposition = copied["DISPOSITION"].read_text(encoding="utf-8")
    sections = disposition.split("---", 2)
    frontmatter = re.sub(
        r"(?ms)^  - id: CR-01\n.*?(?=^  - id:|\Z)",
        "",
        sections[1],
    )
    frontmatter = re.sub(r"(?m)^open: 5$", "open: 4", frontmatter)
    frontmatter = re.sub(r"(?m)^total: 5$", "total: 4", frontmatter)
    body = re.sub(r"(?m)^\| CR-01 \|[^\n]*\n", "", sections[2])
    copied["DISPOSITION"].write_text(f"---{frontmatter}---{body}", encoding="utf-8")
    return copied


class ValidationMapReconciliationTest(unittest.TestCase):
    def test_checker_accepts_a_reconciled_review_after_a_repaired_finding_disappears(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase04-review-reconciliation-") as temporary:
            documents = reconciled_review_documents(Path(temporary))
            observed_counts = {
                "python3 -m unittest discover -s tests/tools -p 'test_verify_playable.py' -v": 19,
                "python3 -m unittest discover -s tests/libretro -p 'test_retroarch_smoke.py' -v": 25,
            }

            def observed_suite(command: str) -> tuple[int, int, str]:
                count = observed_counts[command]
                return 0, count, f"Ran {count} tests in 0.01s\n\nOK\n"

            with mock.patch.multiple(validation_map, **documents):
                with mock.patch.object(validation_map, "run_suite", side_effect=observed_suite):
                    validation_map.main()


if __name__ == "__main__":
    unittest.main()
