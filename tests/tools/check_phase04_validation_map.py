#!/usr/bin/env python3
"""Re-run current Phase 04 suites and reconcile their evidence records."""

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


def frontmatter(document: str, label: str) -> str:
    sections = document.split("---", 2)
    require(len(sections) == 3 and sections[0].strip() == "", f"{label} lacks YAML frontmatter")
    return sections[1]


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


def parse_review_findings(review: str) -> dict[str, tuple[str, str]]:
    findings: dict[str, tuple[str, str]] = {}
    section = ""
    for line in review.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
        match = re.match(r"^### ((?:CR|WR|IN)-\d+):\s*(.*?)\s*$", line)
        if not match:
            continue
        finding_id, title = match.groups()
        require(finding_id not in findings, f"duplicate current review finding {finding_id}")
        if section == "critical issues":
            severity = "critical"
        elif section == "warnings":
            severity = "warning"
        elif section == "info":
            severity = "info"
        else:
            raise AssertionError(f"phase04 validation map: {finding_id} is outside a severity section")
        findings[finding_id] = (severity, title)
    return findings


def parse_disposition_yaml(document: str) -> dict[str, dict[str, str]]:
    yaml = frontmatter(document, "disposition")
    findings_section = re.search(r"(?ms)^findings:\s*\n(.*?)(?=^[A-Za-z_][A-Za-z0-9_-]*:|\Z)", yaml)
    require(findings_section is not None, "disposition YAML has no findings list")
    blocks = re.findall(r"(?ms)^  - id: (\S+)\n(.*?)(?=^  - id: |\Z)", findings_section.group(1))
    records: dict[str, dict[str, str]] = {}
    for finding_id, block in blocks:
        require(finding_id not in records, f"duplicate disposition YAML ID {finding_id}")
        record: dict[str, str] = {}
        for key in ("severity", "disposition", "title"):
            value = re.search(rf"(?m)^    {key}:\s*(.*?)\s*$", block)
            require(value is not None, f"{finding_id} lacks YAML {key}")
            record[key] = value.group(1).strip('"')
        require(record["disposition"] in {"open", "fixed", "skipped", "deferred"},
                f"{finding_id} has invalid disposition {record['disposition']!r}")
        records[finding_id] = record
    return records


def main() -> None:
    validation = VALIDATION.read_text(encoding="utf-8")
    security = SECURITY.read_text(encoding="utf-8")
    verification = VERIFICATION.read_text(encoding="utf-8")
    disposition = DISPOSITION.read_text(encoding="utf-8")
    review = REVIEW.read_text(encoding="utf-8")

    # The current row must reflect this exact source's run. Prior rows remain dated history.
    header = "| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |"
    rows = table_rows(validation, header)
    selected = [row for row in rows if len(row) == 10 and row[1] == "04-16" and row[0].startswith("04-16 T1")]
    require(len(selected) == 2, "validation map lacks the two current 04-16 privacy-suite rows")
    expected_commands = {
        "python3 tests/tools/test_verify_playable.py -v",
        "python3 tests/libretro/test_retroarch_smoke.py -v",
    }
    mapped: dict[str, list[list[str]]] = {}
    for row in selected:
        commands = re.findall(r"`([^`]+)`", row[7])
        require(len(commands) == 1, f"{row[0]} must identify one exact suite command")
        mapped.setdefault(commands[0], []).append(row)
        require("pass" in row[9].lower(), f"{row[0]} does not record a passing result")
        require(row[8].lower() == "yes", f"{row[0]} test file is not recorded present")
    require(set(mapped) == expected_commands, "current focused-suite commands differ from the required pair")
    observed = {command: run_suite(command) for command in sorted(expected_commands)}
    for command, command_rows in mapped.items():
        status, count, _output = observed[command]
        for row in command_rows:
            claimed = re.search(r"pass,\s*(\d+) tests", row[9], re.IGNORECASE)
            require(claimed is not None, f"{row[0]} lacks its observed test denominator")
            require(status == 0 and int(claimed.group(1)) == count,
                    f"{row[0]} records {claimed.group(1)} tests but {command!r} observed {count}")

    threat_rows = table_rows(validation, "| Threat | Evidence and disposition |")
    threat_map = {row[0]: row[1] for row in threat_rows if len(row) == 2}
    required_threat_links = {
        "T-04-20 → T-04-11/T-04-15/T-04-18",
        "T-04-21 → T-04-16",
        "T-04-22 → T-04-17",
        "T-04-23 → T-04-13",
        "T-04-24 receipt numeric types",
    }
    require(required_threat_links <= set(threat_map), "historical T-04-20..24 threat coverage is missing")
    for row in selected:
        require(all(f"T-04-{number}" in row[4] for number in ("11", "15", "18", "20")),
                f"{row[0]} omits a relevant current disclosure threat")

    review_findings = parse_review_findings(review)
    records = parse_disposition_yaml(disposition)
    for finding_id, (severity, _title) in review_findings.items():
        require(finding_id in records, f"current review finding {finding_id} has no disposition record")
        require(records[finding_id]["severity"] == severity,
                f"{finding_id} severity differs between current review and disposition")
        require(records[finding_id]["disposition"] == "open",
                f"current finding {finding_id} is recorded as {records[finding_id]['disposition']}")

    disposition_rows = table_rows(disposition, "| Finding | Severity | Disposition | Source |")
    require(all(len(row) == 4 for row in disposition_rows), "malformed disposition table row")
    table_records: dict[str, tuple[str, str, str]] = {}
    for row in disposition_rows:
        finding_id, severity, state, source = row
        require(finding_id not in table_records, f"duplicate disposition table ID {finding_id}")
        require(source and source != "-", f"{finding_id} has no provenance source")
        table_records[finding_id] = (severity, state, source)
    require(set(table_records) == set(records), "disposition YAML and table IDs differ")
    require(set(review_findings) <= set(records), "a current review finding is missing from disposition history")
    for finding_id, record in records.items():
        require(table_records[finding_id][:2] == (record["severity"], record["disposition"]),
                f"{finding_id} severity or disposition differs between YAML and table")
    yaml_open = re.search(r"(?m)^open: (\d+)$", frontmatter(disposition, "disposition"))
    yaml_total = re.search(r"(?m)^total: (\d+)$", frontmatter(disposition, "disposition"))
    require(yaml_open is not None and int(yaml_open.group(1)) == sum(r["disposition"] == "open" for r in records.values()),
            "disposition YAML open count differs from its records")
    require(yaml_total is not None and int(yaml_total.group(1)) == len(records),
            "disposition YAML total count differs from its records")

    crosswalk_rows = table_rows(validation, "| Review Finding | Severity | Existing Threat Scope | Disposition |")
    require(all(len(row) == 4 for row in crosswalk_rows), "malformed review-finding crosswalk")
    crosswalk: dict[str, tuple[str, str]] = {}
    for finding_id, severity, scope, recorded_state in crosswalk_rows:
        require(finding_id not in crosswalk, f"duplicate validation crosswalk ID {finding_id}")
        require(scope.strip(), f"{finding_id} has no existing threat scope")
        crosswalk[finding_id] = (severity.lower(), recorded_state.strip().lower())
    require(set(crosswalk) == set(records), "review crosswalk differs from retained disposition history")
    for finding_id, record in records.items():
        require(crosswalk[finding_id][0] == record["severity"],
                f"{finding_id} severity differs between validation crosswalk and disposition records")
        require(crosswalk[finding_id][1] == record["disposition"],
                f"{finding_id} disposition must be exactly one normalized controlled state matching its record")
    require("04-07-SUMMARY.md" in validation and "04-VERIFICATION.md" in validation,
            "validation map does not preserve source revision context")

    security_yaml = frontmatter(security, "security")
    require(re.search(r"(?m)^status: blocked$", security_yaml) is not None,
            "security status is not blocked")
    register = table_rows(security, "| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |")
    require(all(len(row) == 7 for row in register), "malformed security register row")
    threats: dict[str, tuple[str, str, str]] = {}
    for row in register:
        threat_id, _category, _component, severity, action, _mitigation, status = row
        require(threat_id not in threats, f"duplicate security register ID {threat_id}")
        threats[threat_id] = (severity, action, status)
    open_threats = {key for key, value in threats.items() if value[2] == "open"}
    high_open = {key for key, value in threats.items() if value[0] == "high" and value[2] == "open"}
    count = re.search(r"(?m)^threats_open: (\d+)$", security_yaml)
    required_high_open = {"T-04-11", "T-04-15", "T-04-18", "T-04-20"}
    required_medium_open = {"T-04-34"}
    require(count is not None and int(count.group(1)) == len(high_open),
            "security frontmatter blocking count differs from high/open register rows")
    require(high_open == required_high_open,
            "four high/open disclosure threats differ from the active security register")
    require({key for key in open_threats if threats[key][0] == "medium"} == required_medium_open,
            "required medium/open T-04-34 differs from the active security register")
    require(open_threats == required_high_open | required_medium_open,
            "unexpected open security threat outside the four disclosure findings and T-04-34")

    goal_rows = table_rows(verification, "| # | Truth | Status | Evidence |")
    actual_frontend = [row for row in goal_rows if len(row) == 4 and row[0] == "3"]
    require(len(actual_frontend) == 1 and actual_frontend[0][2] == "? UNCERTAIN",
            "current verification report does not mark actual pinned frontend load as uncertain")
    require(re.search(r"\bactual app/load/presentation/input/unload/exit were not observed\b",
                      actual_frontend[0][3], re.IGNORECASE) is not None,
            "current verification goal evidence no longer states actual pinned-app observations are unobserved")

    requirement_rows = table_rows(verification, "| Requirement | Source Plans | Description | Status | Evidence |")
    requirement_status = {row[0]: row[3] for row in requirement_rows if len(row) == 5}
    require((requirement_status.get("HOST-02") or "").startswith("? NEEDS HUMAN / PENDING"),
            "HOST-02 is not explicitly marked as awaiting human evidence")
    require((requirement_status.get("QUAL-03") or "").startswith("✗ BLOCKED / PARTIAL"),
            "QUAL-03 is not explicitly marked blocked/partial")
    qual_row = next(row for row in requirement_rows if row[0] == "QUAL-03")
    require("frontend portion remains unknown" in qual_row[4].lower(),
            "QUAL-03 frontend portion is no longer explicitly unknown")
    print("Phase 04 validation map matches current focused test results and preserves open security and frontend gates.")


if __name__ == "__main__":
    main()
