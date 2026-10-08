#!/usr/bin/env python3
"""Re-run the Phase 04 focused suites and check their validation-map claims."""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHASE = ROOT / ".planning/workstreams/first-playable-game/phases/04-public-playable-tracer"
VALIDATION = PHASE / "04-VALIDATION.md"
SECURITY = PHASE / "04-SECURITY.md"
VERIFICATION = PHASE / "04-VERIFICATION.md"
DISPOSITION = PHASE / "04-REVIEW-DISPOSITION.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(f"phase04 validation map: {message}")


def table_rows(document: str, header: str) -> list[list[str]]:
    lines = document.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.startswith(header))
    except StopIteration as error:
        raise AssertionError(f"phase04 validation map: missing table header {header!r}") from error
    rows: list[list[str]] = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def run_suite(command: str) -> tuple[int, int, str]:
    result = subprocess.run(
        shlex.split(command), cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False, timeout=180,
    )
    count = re.search(r"(?m)^Ran (\d+) tests? in ", result.stdout)
    require(count is not None, f"{command!r} did not report a unittest test count")
    require(re.search(r"(?m)^OK$", result.stdout) is not None,
            f"{command!r} did not report OK")
    require(result.returncode == 0, f"{command!r} exited {result.returncode}")
    return result.returncode, int(count.group(1)), result.stdout


def main() -> None:
    validation = VALIDATION.read_text(encoding="utf-8")
    security = SECURITY.read_text(encoding="utf-8")
    verification = VERIFICATION.read_text(encoding="utf-8")
    disposition = DISPOSITION.read_text(encoding="utf-8")

    header = "| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |"
    rows = table_rows(validation, header)
    selected = [row for row in rows if row[1] in {"04-10", "04-11"}]
    require(any(row[1] == "04-10" for row in selected), "validation map has no 04-10 row")
    require(any(row[1] == "04-11" for row in selected), "validation map has no 04-11 row")

    expected_commands = {
        "python3 -m unittest discover -s tests/tools -p 'test_verify_playable.py' -v",
        "python3 -m unittest discover -s tests/libretro -p 'test_retroarch_smoke.py' -v",
    }
    mapped_commands: set[str] = set()
    rows_by_command: dict[str, list[list[str]]] = {}
    for row in selected:
        require(len(row) == 10, f"malformed validation-map row for {row[0]}")
        commands = re.findall(r"`([^`]+)`", row[7])
        require(bool(commands), f"{row[0]} has no runnable command in its command cell")
        mapped_commands.update(commands)
        for command in commands:
            rows_by_command.setdefault(command, []).append(row)
        require("pass" in row[9].lower(), f"{row[0]} does not record a passing observed result")
    require(mapped_commands == expected_commands,
            f"focused command rows differ from the required exact commands: {sorted(mapped_commands)}")

    observed: dict[str, tuple[int, int, str]] = {}
    for command in sorted(mapped_commands):
        observed[command] = run_suite(command)
    for command, command_rows in rows_by_command.items():
        actual_status, actual_count, _output = observed[command]
        for row in command_rows:
            claimed = re.search(r"pass,\s*(\d+) tests", row[9])
            require(claimed is not None, f"{row[0]} lacks an explicit observed test count")
            require(actual_status == 0 and int(claimed.group(1)) == actual_count,
                    f"{row[0]} records {claimed.group(1)} tests but {command!r} observed {actual_count}")

    threat_rows = table_rows(validation, "| Threat | Evidence and disposition |")
    crosswalks = {row[0]: row[1] for row in threat_rows if len(row) == 2}
    expected_crosswalks = {
        "T-04-20 → T-04-11/T-04-15/T-04-18",
        "T-04-21 → T-04-16",
        "T-04-22 → T-04-17",
        "T-04-23 → T-04-13",
    }
    require(expected_crosswalks <= set(crosswalks), "one or more T-04-20..23 old-finding crosswalks are missing")
    for row in selected:
        refs = row[4]
        require(all(f"T-04-{number}" in refs for number in ("20", "21", "22") if row[1] == "04-10"),
                f"{row[0]} omits an applicable Plan 04-10 threat reference")
        if row[1] == "04-11":
            require("T-04-23" in refs, "04-11 row omits T-04-23")
    review_crosswalks = table_rows(validation, "| Review Finding | Existing Threat Scope | Disposition |")
    review_links = {row[0]: " ".join(row[1:]) for row in review_crosswalks if len(row) == 3}
    require(set(review_links) == {"WR-01", "WR-02", "WR-03"},
            "review finding crosswalk does not contain exactly WR-01/02/03")
    require(all("remains open pending independent review" in review_links[finding].lower()
                for finding in ("WR-01", "WR-02", "WR-03")),
            "a review finding is not kept open pending independent review")
    require("no separate threat scope" in review_links["WR-02"].lower(),
            "WR-02 is described as separate from its existing threat scope")

    frontmatter = security.split("---", 2)[1]
    require(re.search(r"(?m)^status: blocked$", frontmatter) is not None,
            "security status is no longer blocked")
    require(re.search(r"(?m)^threats_open: 6$", frontmatter) is not None,
            "security register no longer reports six open threats")
    for threat in ("T-04-11", "T-04-13", "T-04-15", "T-04-16", "T-04-17", "T-04-18"):
        require(re.search(rf"(?m)^\| {threat} \|[^\n]*\| open \|$", security) is not None,
                f"security finding {threat} is missing or no longer open")

    require(re.search(r"(?m)^\| HOST-02 \| \? NEEDS HUMAN \|", verification) is not None,
            "HOST-02 is not explicitly marked human-needed")
    require(re.search(r"(?m)^\| QUAL-03 \| \? NEEDS HUMAN \|", verification) is not None,
            "actual frontend QUAL-03 is not explicitly marked human-needed")
    require("actual frontend load remains unobserved" in verification.lower(),
            "verification no longer states that actual frontend load is unobserved")

    disposition_frontmatter = disposition.split("---", 2)[1]
    for finding in ("WR-01", "WR-02", "WR-03"):
        block = re.search(rf"(?ms)^  - id: {finding}\n(.*?)(?=^  - id:|\Z)", disposition_frontmatter)
        require(block is not None and re.search(r"(?m)^    disposition: open$", block.group(1)) is not None,
                f"{finding} is not open in disposition YAML")
        require(re.search(rf"(?m)^\| {finding} \| warning \| open \|", disposition) is not None,
                f"{finding} is not open in the disposition table")
    cr_block = re.search(r"(?ms)^  - id: CR-01\n(.*?)(?=^  - id:|\Z)", disposition_frontmatter)
    require(cr_block is not None and re.search(r"(?m)^    disposition: fixed$", cr_block.group(1)) is not None,
            "CR-01 is not fixed in disposition YAML")
    require("04-07-SUMMARY.md" in cr_block.group(1) and "04-VERIFICATION.md" in cr_block.group(1),
            "CR-01 YAML source does not cite both identity records")
    require(re.search(r"(?m)^open: 3$", disposition_frontmatter) is not None,
            "disposition YAML does not report three open findings")
    require(re.search(r"(?m)^\| CR-01 \| critical \| fixed \|.*04-07-SUMMARY\.md.*04-VERIFICATION\.md", disposition) is not None,
            "CR-01 is not fixed with both sources in the disposition table")
    require("04-07-SUMMARY.md" in validation and "04-VERIFICATION.md" in validation,
            "validation map does not preserve the CR-01 source revision context")

    print("Phase 04 validation map matches current focused test results and preserves all open gates.")


if __name__ == "__main__":
    main()
