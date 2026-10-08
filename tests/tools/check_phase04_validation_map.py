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


PINNED_FRONTEND_UNCERTAINTY_EVIDENCE = (
    "Actual pinned-app load, presentation, input, unload, and exit remain unobserved. "
    "The recorded app launch aborted with exit -6 before screenshot; GUI-free callback "
    "and runner tests do not establish this truth."
)
HOST_FRONTEND_UNCERTAINTY_EVIDENCE = (
    "No fresh screenshot or actual app input/unload observation; launch previously aborted before screenshot."
)
QUAL_FRONTEND_UNCERTAINTY_EVIDENCE = (
    "Procedure and identities are documented; successful actual frontend load remains unknown."
)
QUALIFICATION_GOAL_UNCERTAINTY_EVIDENCE = (
    "`docs/first-playable-build.md` records the procedure and environment identities, and the qualification runner checks its documentation contract. "
    "Its actual frontend load lane remains unknown, so successful load on the pinned frontend is not established."
)
QUALIFICATION_ARTIFACT_UNCERTAINTY_EVIDENCE = (
    "Documentation and automated gates are substantive; actual pinned frontend load remains unknown."
)
LIBRETRO_ARTIFACT_FRONTEND_BOUNDARY = (
    "Callback contract is linked to native frame advancement; `libretro_callback` passes. "
    "This does not prove actual RetroArch behavior."
)
LIBRETRO_LINK_FRONTEND_BOUNDARY = (
    "`libretro_callback` passes; actual frontend remains unobserved."
)
QUALIFICATION_RUNNER_UNCERTAINTY_EVIDENCE = (
    "Runner/document contract is tested; app launch is unknown and was not retried."
)
QUALIFICATION_FLOW_UNCERTAINTY_STATUS = "⚠️ UNKNOWN, correctly fail-closed"
ACTUAL_FRONTEND_SPOTCHECK_RESULT = "User direction keeps this manual-only; no GUI launch was made."
CURRENT_FRONTEND_ROWS = {
    "goal": [
        "3",
        "A user can load, run, control, and unload the fixture in an actual pinned macOS RetroArch build with software video, documented controller mapping, and frontend-owned pacing.",
        "? UNCERTAIN",
        PINNED_FRONTEND_UNCERTAINTY_EVIDENCE,
    ],
    "qualification_goal": [
        "5",
        "An integrator can follow the clean-tree build/install/load procedure for the native library and libretro adapter on the selected macOS configuration and identify exact dependency, compiler, SDK, OS, architecture, and frontend identities plus untested configurations.",
        "? UNCERTAIN",
        QUALIFICATION_GOAL_UNCERTAINTY_EVIDENCE,
    ],
    "qualification_artifact": [
        "`tools/verify_playable.py` and `docs/first-playable-build.md`",
        "Clean qualification procedure and identity reporting",
        "⚠️ PARTIAL",
        QUALIFICATION_ARTIFACT_UNCERTAINTY_EVIDENCE,
    ],
    "libretro_artifact": [
        "`src/libretro/libretro_core.c`",
        "Thin consumer forwarding input, video, and lifecycle",
        "✓ VERIFIED",
        LIBRETRO_ARTIFACT_FRONTEND_BOUNDARY,
    ],
    "qualification_link": [
        "Qualification runner",
        "pinned RetroArch process",
        "identity-checked smoke lane and status receipt",
        "⚠️ PARTIAL",
        QUALIFICATION_RUNNER_UNCERTAINTY_EVIDENCE,
    ],
    "libretro_link": [
        "Libretro callback",
        "native frame API",
        "callback forwards sampled input and frame output",
        "✓ WIRED",
        LIBRETRO_LINK_FRONTEND_BOUNDARY,
    ],
    "qualification_flow": [
        "Qualification evidence",
        "frontend status",
        "actual app observation or explicit unknown",
        "No actual app result exists",
        QUALIFICATION_FLOW_UNCERTAINTY_STATUS,
    ],
    "libretro_flow": [
        "Libretro callback",
        "video/input",
        "frontend callback input is forwarded to the native instance; output pixels are submitted through callback",
        "Yes in callback harness",
        "✓ FLOWING; actual frontend observation remains human-only",
    ],
    "actual_spotcheck": [
        "Actual pinned RetroArch load, display, controls, and unload",
        "Not run",
        ACTUAL_FRONTEND_SPOTCHECK_RESULT,
        "? HUMAN",
    ],
    "evidence_map_spotcheck": [
        "Current security/evidence-map consistency and report uncertainty",
        "`python3 tests/tools/check_phase04_validation_map.py`",
        "Passed; preserves four high/open threats, T-04-34 medium/open, and Pending/unknown frontend state.",
        "✓ PASS",
    ],
    "qualification_spotcheck": [
        "Qualification/privacy regressions",
        "`python3 tests/tools/test_verify_playable.py -v`",
        "23/23 passed.",
        "✓ PASS",
    ],
    "runner_spotcheck": [
        "GUI-free RetroArch runner contract",
        "`python3 tests/libretro/test_retroarch_smoke.py -v`",
        "27/27 passed.",
        "✓ PASS",
    ],
    "docs_spotcheck": [
        "Documentation claim gate",
        "`python3 tools/verify_playable.py --check-docs`",
        "Passed.",
        "✓ PASS",
    ],
    "host_requirement": [
        "HOST-02",
        "04-02, 04-08, 04-15, 04-18",
        "Actual pinned RetroArch load, run, control, and unload",
        "? NEEDS HUMAN / PENDING",
        HOST_FRONTEND_UNCERTAINTY_EVIDENCE,
    ],
    "qual_requirement": [
        "QUAL-03",
        "04-06, 04-08, 04-15, 04-18",
        "Clean-tree build/install/load steps and selected macOS identities",
        "? NEEDS HUMAN / PENDING",
        QUAL_FRONTEND_UNCERTAINTY_EVIDENCE,
    ],
}


def has_frontend_load_uncertainty(evidence: str, *, scope: str) -> bool:
    """Accept only the exact current report evidence for each frontend scope."""
    normalized = " ".join(evidence.split()).casefold()
    expected_by_scope = {
        "goal": PINNED_FRONTEND_UNCERTAINTY_EVIDENCE,
        "host": HOST_FRONTEND_UNCERTAINTY_EVIDENCE,
        "qual": QUAL_FRONTEND_UNCERTAINTY_EVIDENCE,
        "qual_goal": QUALIFICATION_GOAL_UNCERTAINTY_EVIDENCE,
        "qual_artifact": QUALIFICATION_ARTIFACT_UNCERTAINTY_EVIDENCE,
        "libretro_artifact": LIBRETRO_ARTIFACT_FRONTEND_BOUNDARY,
        "libretro_link": LIBRETRO_LINK_FRONTEND_BOUNDARY,
        "qual_runner": QUALIFICATION_RUNNER_UNCERTAINTY_EVIDENCE,
    }
    expected = expected_by_scope.get(scope)
    return expected is not None and normalized == " ".join(expected.split()).casefold()


def require_current_frontend_row(rows: list[list[str]], key: str, scope: str) -> None:
    expected = CURRENT_FRONTEND_ROWS[scope]
    matches = [row for row in rows if row and row[0] == key]
    require(len(matches) == 1 and matches[0] == expected,
            f"current frontend report row {key!r} changed or contradicts its audited state")


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
    require(all(len(row) == 4 for row in goal_rows), "malformed phase-goal verification row")
    require_current_frontend_row(goal_rows, "3", "goal")
    require_current_frontend_row(goal_rows, "5", "qualification_goal")
    actual_frontend = [row for row in goal_rows if len(row) == 4 and row[0] == "3"]
    require(len(actual_frontend) == 1 and actual_frontend[0][2] == "? UNCERTAIN",
            "current verification report does not mark actual pinned frontend load as uncertain")
    require(has_frontend_load_uncertainty(actual_frontend[0][3], scope="goal"),
            "current verification goal evidence must explicitly mark actual pinned-app load unobserved or unknown and contain no success claim")
    qualification_goal = [row for row in goal_rows if row[0] == "5"]
    require(len(qualification_goal) == 1 and qualification_goal[0][2] == "? UNCERTAIN",
            "current qualification goal does not retain its uncertain status")
    require(has_frontend_load_uncertainty(qualification_goal[0][3], scope="qual_goal"),
            "current qualification goal evidence no longer preserves the actual frontend unknown boundary")

    artifact_rows = table_rows(verification, "| Artifact | Expected | Status | Details |")
    require(all(len(row) == 4 for row in artifact_rows), "malformed required-artifact verification row")
    require_current_frontend_row(
        artifact_rows, "`tools/verify_playable.py` and `docs/first-playable-build.md`", "qualification_artifact"
    )
    require_current_frontend_row(artifact_rows, "`src/libretro/libretro_core.c`", "libretro_artifact")
    qualification_artifact = [row for row in artifact_rows if row[0] == "`tools/verify_playable.py` and `docs/first-playable-build.md`"]
    require(len(qualification_artifact) == 1 and qualification_artifact[0][2] == "⚠️ PARTIAL",
            "qualification artifact status differs from the current report")
    require(has_frontend_load_uncertainty(qualification_artifact[0][3], scope="qual_artifact"),
            "qualification artifact evidence no longer records actual frontend uncertainty")
    libretro_artifact = [row for row in artifact_rows if row[0] == "`src/libretro/libretro_core.c`"]
    require(len(libretro_artifact) == 1 and
            has_frontend_load_uncertainty(libretro_artifact[0][3], scope="libretro_artifact"),
            "libretro artifact evidence overstates actual frontend behavior")

    link_rows = table_rows(verification, "| From | To | Via | Status | Details |")
    require(all(len(row) == 5 for row in link_rows), "malformed key-link verification row")
    require_current_frontend_row(link_rows, "Qualification runner", "qualification_link")
    require_current_frontend_row(link_rows, "Libretro callback", "libretro_link")
    qualification_link = [row for row in link_rows if row[0] == "Qualification runner"]
    require(len(qualification_link) == 1 and qualification_link[0][3] == "⚠️ PARTIAL" and
            has_frontend_load_uncertainty(qualification_link[0][4], scope="qual_runner"),
            "qualification runner link no longer preserves unknown actual-app evidence")
    libretro_link = [row for row in link_rows if row[0] == "Libretro callback"]
    require(len(libretro_link) == 1 and
            has_frontend_load_uncertainty(libretro_link[0][4], scope="libretro_link"),
            "libretro link overstates actual frontend behavior")

    flow_rows = table_rows(verification, "| Artifact | Data variable | Source | Produces Real Data | Status |")
    require(all(len(row) == 5 for row in flow_rows), "malformed data-flow verification row")
    require_current_frontend_row(flow_rows, "Qualification evidence", "qualification_flow")
    require_current_frontend_row(flow_rows, "Libretro callback", "libretro_flow")
    qualification_flow = [row for row in flow_rows if len(row) == 5 and row[0] == "Qualification evidence"]
    require(len(qualification_flow) == 1 and qualification_flow[0][3] == "No actual app result exists" and
            qualification_flow[0][4] == QUALIFICATION_FLOW_UNCERTAINTY_STATUS,
            "qualification data-flow row claims actual frontend evidence")

    spotcheck_rows = table_rows(verification, "| Behavior | Command | Result | Status |")
    require_current_frontend_row(
        spotcheck_rows, "Actual pinned RetroArch load, display, controls, and unload", "actual_spotcheck"
    )
    require_current_frontend_row(
        spotcheck_rows, "Current security/evidence-map consistency and report uncertainty", "evidence_map_spotcheck"
    )
    require_current_frontend_row(spotcheck_rows, "Qualification/privacy regressions", "qualification_spotcheck")
    require_current_frontend_row(spotcheck_rows, "GUI-free RetroArch runner contract", "runner_spotcheck")
    require_current_frontend_row(spotcheck_rows, "Documentation claim gate", "docs_spotcheck")
    actual_frontend_spotcheck = [
        row for row in spotcheck_rows
        if len(row) == 4 and row[0] == "Actual pinned RetroArch load, display, controls, and unload"
    ]
    require(len(actual_frontend_spotcheck) == 1 and actual_frontend_spotcheck[0][1] == "Not run" and
            actual_frontend_spotcheck[0][2] == ACTUAL_FRONTEND_SPOTCHECK_RESULT and
            actual_frontend_spotcheck[0][3] == "? HUMAN",
            "actual frontend spot-check is no longer marked manual-only and unrun")

    requirement_rows = table_rows(verification, "| Requirement | Source Plan")
    require(all(len(row) == 5 for row in requirement_rows), "malformed requirement coverage row")
    require_current_frontend_row(requirement_rows, "HOST-02", "host_requirement")
    require_current_frontend_row(requirement_rows, "QUAL-03", "qual_requirement")
    requirement_ids = [row[0] for row in requirement_rows]
    require(len(requirement_ids) == len(set(requirement_ids)),
            "requirements coverage contains duplicate requirement rows")
    requirement_status = {row[0]: row[3] for row in requirement_rows}
    require(requirement_status.get("HOST-02") == "? NEEDS HUMAN / PENDING",
            "HOST-02 is not explicitly marked as awaiting human evidence")
    host_row = next(row for row in requirement_rows if row[0] == "HOST-02")
    require(has_frontend_load_uncertainty(host_row[4], scope="host"),
            "HOST-02 evidence no longer matches the current actual-app uncertainty record")
    qual_status = requirement_status.get("QUAL-03") or ""
    require(qual_status in {"✗ BLOCKED / PARTIAL", "? NEEDS HUMAN / PENDING"},
            "QUAL-03 is not explicitly marked blocked, partial, or pending human evidence")
    qual_row = next(row for row in requirement_rows if row[0] == "QUAL-03")
    require(has_frontend_load_uncertainty(qual_row[4], scope="qual"),
            "QUAL-03 evidence no longer explicitly marks actual frontend load unobserved or unknown")
    print("Phase 04 validation map matches current focused test results and preserves open security and frontend gates.")


if __name__ == "__main__":
    main()
