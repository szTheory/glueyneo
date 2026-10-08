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
REVIEW = PHASE / "04-REVIEW.md"


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
    review = REVIEW.read_text(encoding="utf-8")

    header = "| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |"
    rows = table_rows(validation, header)
    # Earlier rows are dated history, with their original denominators intact.
    selected = [row for row in rows if row[1] == "04-12" and row[0].startswith("04-12 T1")]
    require(len(selected) == 2, "validation map lacks the two current 04-12 focused suite rows")

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
        "T-04-24 receipt numeric types",
    }
    require(expected_crosswalks <= set(crosswalks), "one or more T-04-20..23 old-finding crosswalks are missing")
    for row in selected:
        refs = row[4]
        require(all(f"T-04-{number}" in refs for number in ("11", "15", "18", "24")),
                f"{row[0]} omits an applicable Plan 04-12 threat reference")
    review_crosswalks = table_rows(validation, "| Review Finding | Existing Threat Scope | Disposition |")
    review_links = {row[0]: " ".join(row[1:]) for row in review_crosswalks if len(row) == 3}
    current_findings = set(re.findall(r"(?m)^### ((?:CR|WR)-\d+):", review))
    require(current_findings == {"CR-01", "CR-02", "WR-01"}, "current review IDs changed")
    unresolved = current_findings | {"WR-02", "WR-03"}
    require(set(review_links) == unresolved, "review finding crosswalk differs from unresolved findings")
    require(all("remains open pending independent review" in review_links[finding].lower()
                for finding in unresolved),
            "a review finding is not kept open pending independent review")
    require("no separate threat scope" in review_links["WR-02"].lower(),
            "WR-02 is described as separate from its existing threat scope")

    frontmatter = security.split("---", 2)[1]
    require(re.search(r"(?m)^status: blocked$", frontmatter) is not None,
            "security status is no longer blocked")
    register = table_rows(security, "| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |")
    require(all(len(row) == 7 for row in register), "malformed security register row")
    threats = {row[0]: row[-1] for row in register}
    require(len(threats) == len(register), "duplicate security register IDs")
    require(re.search(r"(?m)^threats_open: 3$", frontmatter) is not None,
            "security register no longer reports three open threats")
    require({key for key, value in threats.items() if value == "open"} == {"T-04-11", "T-04-15", "T-04-18"},
            "open security register rows differ from the current audit")
    for threat in ("T-04-13", "T-04-16", "T-04-17"):
        require(threats.get(threat) == "closed", f"audited closed finding {threat} is missing or reopened")

    requirement_rows = table_rows(verification, "| Requirement | Source Plan | Description | Status | Evidence |")
    requirement_status = {row[0]: row[3] for row in requirement_rows if len(row) == 5}
    for requirement in ("HOST-02", "QUAL-03"):
        require(requirement_status.get(requirement) == "? NEEDS HUMAN",
                f"{requirement} is not explicitly marked human-needed")
    require("actual frontend load remains unobserved" in verification.lower(),
            "verification no longer states that actual frontend load is unobserved")

    disposition_frontmatter = disposition.split("---", 2)[1]
    disposition_rows = table_rows(disposition, "| Finding | Severity | Disposition | Source |")
    require(all(len(row) == 4 for row in disposition_rows), "malformed disposition table")
    require({row[0] for row in disposition_rows} == unresolved and len(disposition_rows) == len(unresolved),
            "disposition table differs from unresolved findings")
    yaml_ids = re.findall(r"(?m)^  - id: (\S+)$", disposition_frontmatter)
    require(set(yaml_ids) == unresolved and len(yaml_ids) == len(unresolved), "disposition YAML IDs differ from table")
    for finding in unresolved:
        block = re.search(rf"(?ms)^  - id: {finding}\n(.*?)(?=^  - id:|\Z)", disposition_frontmatter)
        require(block is not None and re.search(r"(?m)^    disposition: open$", block.group(1)) is not None,
                f"{finding} is not open in disposition YAML")
        severity = "critical" if finding.startswith("CR-") else "warning"
        require(re.search(rf"(?m)^\| {finding} \| {severity} \| open \|", disposition) is not None,
                f"{finding} is not open in the disposition table")
    require(re.search(rf"(?m)^open: {len(disposition_rows)}$", disposition_frontmatter) is not None,
            "disposition YAML open counter differs from its unresolved rows")
    require("04-07-SUMMARY.md" in validation and "04-VERIFICATION.md" in validation,
            "validation map does not preserve the CR-01 source revision context")

    print("Phase 04 validation map matches current focused test results and preserves all open gates.")


if __name__ == "__main__":
    main()
