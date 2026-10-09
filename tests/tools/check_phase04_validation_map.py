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
REQUIRED_REVIEWED_PATHS = (
    "tests/tools/check_phase04_validation_map.py",
    "tests/tools/test_check_phase04_validation_map.py",
    "tools/verify_playable.py",
    "tests/tools/test_verify_playable.py",
    "tests/libretro/retroarch_smoke.py",
)


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


def require_reviewed_source_identity(review: str, *, repository: Path = ROOT) -> None:
    """Bind the current review's required file list and bytes to its immutable commit."""
    yaml = frontmatter(review, "review")
    revision_values = re.findall(r"(?m)^reviewed_revision:\s*(.*?)\s*$", yaml)
    require(len(revision_values) == 1,
            "current review must contain exactly one reviewed_revision field")
    revision_value = revision_values[0]
    if len(revision_value) >= 2 and revision_value[0] == revision_value[-1] and revision_value[0] in "'\"":
        revision_value = revision_value[1:-1]
    require(re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", revision_value) is not None,
            "current review reviewed_revision must be a full lowercase immutable commit ID")
    revision = revision_value
    paths_match = re.search(r"(?ms)^files_reviewed_list:\s*\n((?:^  - .+\n)+)", yaml)
    require(paths_match is not None, "current review lacks files_reviewed_list")
    paths = [re.sub(r"^[\"']|[\"']$", "", value.strip())
             for value in re.findall(r"(?m)^  - (.+?)\s*$", paths_match.group(1))]
    require(len(paths) == len(set(paths)), "current review contains duplicate reviewed paths")
    require(set(paths) == set(REQUIRED_REVIEWED_PATHS),
            "current review reviewed path list differs from the exact required gate and sanitizer scope")
    revision_check = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"], cwd=repository,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(revision_check.returncode == 0, "current review reviewed_revision does not exist as a commit")
    for relative in REQUIRED_REVIEWED_PATHS:
        source = repository / relative
        require(source.is_file(), f"current reviewed source is missing: {relative}")
        archived = subprocess.run(
            ["git", "show", f"{revision}:{relative}"], cwd=repository,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        require(archived.returncode == 0, f"reviewed revision lacks required path {relative}")
        require(archived.stdout == source.read_bytes(),
                f"current reviewed source differs from reviewed revision: {relative}")


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
WR01_HISTORICAL_SOURCE = (
    "Historical review `04-REVIEW.md` at `87f8d4c`; reviewed revision "
    "`870848e553aca6e43f6fec8ae0acefac87270f5b`, 2026-10-08T23:46:34Z; carried open"
)
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
    """Require an explicit unknown boundary and reject appended app success claims."""
    normalized = " ".join(evidence.split()).casefold()
    uncertainty = re.search(r"\b(unknown|uncertain|unobserved|not observed|no successful (?:[\w-]*app )?observation|no [\w-]*app observation|no actual (?:pinned )?(?:app|frontend|retroarch) [\w ,/-]*observation|no actual app [\w ,/-]*observed|no fresh screenshot|launch previously aborted|does not prove actual (?:retroarch )?behavior)\b", normalized)
    success = contains_frontend_success_claim(normalized)
    return scope in {"goal", "host", "qual", "qual_goal", "qual_artifact", "libretro_artifact", "libretro_link", "qual_runner"} and bool(uncertainty) and not success


def contains_frontend_success_claim(text: str) -> bool:
    normalized = " ".join(text.split()).casefold()
    patterns = (
        r"\b(?:app|frontend|retroarch)\b.{0,100}\b(?:loaded|booted|displayed|showed|produced|launched|accepted input|controls worked|input worked|unloaded|exited normally)\b",
        r"\b(?:a frame was rendered to the window|frame rendered to the window|game screen was visible|screen was visible|screen became visible|saw the game screen|can see the game screen|gameplay presentation was confirmed|display output was successful|video output (?:passed|was confirmed|confirmed)|logs confirm video output|right input moved the marker|content unloaded|screenshot contained game pixels|guest pixels were displayed|control input worked)\b",
        r"\b(?:displayed|presented|rendered|showed)\s+(?:guest\s+)?pixels?\b",
        r"\bcontrols?\s+worked\s+(?:as\s+expected\s+)?(?:in\s+(?:retroarch|the\s+frontend))?\b",
        r"\b(?:game|content)\s+unloaded\s+(?:cleanly|successfully)\b",
        r"\b(?:game|content)\s+(?:loaded|booted|ran|played|appeared|was visible)\b.{0,80}\b(?:screen|retroarch|successfully|pixels?|output)?\b",
    )
    clauses = re.split(r"(?<=[.!?;])\s+|\s+(?:but|however|although)\s+", normalized)
    for clause in clauses:
        for pattern in patterns:
            for match in re.finditer(pattern, clause):
                prefix = clause[:match.start()]
                negated = re.search(
                    r"(?:\b(?:does|did|do)\s+not\s+(?:claim|assert|report|show|establish|prove|mean)(?:\s+that)?|"
                    r"\b(?:not|never|no)\s+(?:observed|confirmed|seen|shown|rendered|displayed|presented|loaded|unloaded)?\s*)$",
                    prefix,
                )
                if not negated:
                    return True
    return False


def require_current_frontend_row(rows: list[list[str]], key: str, scope: str) -> None:
    matches = [row for row in rows if row and row[0] == key]
    require(len(matches) == 1,
            f"current frontend report row {key!r} is absent or duplicated")


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
    require_reviewed_source_identity(review)

    # The verifier report is a retained point-in-time artifact. Reconcile the
    # current execution row in VALIDATION against fresh live suite counts.
    qualification_command = "python3 tests/tools/test_verify_playable.py -v"
    frontend_command = "python3 tests/libretro/test_retroarch_smoke.py -v"
    status, count, _output = run_suite(qualification_command)
    frontend_status, frontend_count, _frontend_output = run_suite(frontend_command)
    denominator_rows = re.findall(
        r"(?m)^Plan 04-22 current suite denominators: qualification (\d+)/(\d+); frontend (\d+)/(\d+)\.$",
        validation,
    )
    require(len(denominator_rows) == 1, "validation must contain one current Plan 04-22 suite-denominator row")
    reported = tuple(map(int, denominator_rows[0]))
    require(status == 0 and frontend_status == 0 and reported == (count, count, frontend_count, frontend_count),
            f"validation denominators {reported!r} differ from live qualification/frontend suites "
            f"{count}/{count} and {frontend_count}/{frontend_count}")

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
        if finding_id != "WR-01":
            require(source and source != "-", f"{finding_id} has no provenance source")
        table_records[finding_id] = (severity, state, source)
    historical_wr01_source = table_records.get("WR-01", ("", "", ""))[2]
    require(all(token in historical_wr01_source for token in (
        "87f8d4c", "870848e553aca6e43f6fec8ae0acefac87270f5b", "2026-10-08T23:46:34Z",
    )) and "carried open" in historical_wr01_source.lower(),
        "WR-01 lacks its exact historical review source or carried-open status")
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
    required_medium_open = {"T-04-34", "T-04-38", "T-04-43"}
    require(count is not None and int(count.group(1)) == len(high_open),
            "security frontmatter blocking count differs from high/open register rows")
    require(high_open == required_high_open,
            "four high/open disclosure threats differ from the active security register")
    require({key for key in open_threats if threats[key][0] == "medium"} == required_medium_open,
            "the three expected medium/open findings differ from the active security register")
    require(open_threats == required_high_open | required_medium_open,
            "unexpected open security threat outside the four directed high and three current medium findings")

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

    artifact_link_rows = table_rows(verification, "| Artifact/link | Status | Evidence |")
    require(all(len(row) == 3 for row in artifact_link_rows), "malformed artifact/link verification row")
    libretro_evidence = [row for row in artifact_link_rows if row[0].startswith("Libretro content")]
    qualification_evidence = [row for row in artifact_link_rows if row[0].startswith("Qualification input/log")]
    require(len(libretro_evidence) == 1 and has_frontend_load_uncertainty(libretro_evidence[0][2], scope="libretro_artifact") and
            not contains_frontend_success_claim(libretro_evidence[0][2]),
            "libretro artifact/link evidence overstates actual frontend behavior")
    require(len(qualification_evidence) == 1 and not contains_frontend_success_claim(qualification_evidence[0][2]),
            "qualification artifact/link asserts unobserved frontend success")

    flow_rows = table_rows(verification, "| Output | Source | Status |")
    require(all(len(row) == 3 for row in flow_rows), "malformed data-flow verification row")
    frontend_flow = [row for row in flow_rows if row[0] == "Actual frontend state"]
    require(len(frontend_flow) == 1 and "unknown" in frontend_flow[0][2].lower() and
            not contains_frontend_success_claim(" ".join(frontend_flow[0])),
            "frontend qualification data-flow no longer preserves actual-app unknown status")

    spotcheck_rows = table_rows(verification, "| Behavior | Command/result | Status |")
    spotcheck_section = verification.split("### Behavioral Spot-Checks", 1)[1].split("\n### ", 1)[0]
    actual_frontend_spotcheck = [
        row for row in spotcheck_rows
        if len(row) == 3 and row[0] == "Actual pinned RetroArch"
    ]
    require(len(actual_frontend_spotcheck) == 1 and "not invoked" in actual_frontend_spotcheck[0][1].lower() and
            actual_frontend_spotcheck[0][2].strip().upper() == "? MANUAL / UNKNOWN" and
            not contains_frontend_success_claim(" ".join(actual_frontend_spotcheck[0])),
            "actual frontend spot-check is no longer marked manual-only and unrun")
    require(not any(contains_frontend_success_claim(line) for line in spotcheck_section.splitlines()
                    if line.startswith("|") and not line.startswith("|---")),
            "behavioral spot-check claims actual frontend success")

    requirement_header = next((line for line in verification.splitlines()
                               if line.startswith("| Requirement | Plans | Status | Evidence |")), None)
    require(requirement_header is not None, "verification report lacks requirement coverage table")
    requirement_rows = table_rows(verification, requirement_header)
    require(all(len(row) in {4, 5} for row in requirement_rows), "malformed requirement coverage row")
    require_current_frontend_row(requirement_rows, "HOST-02", "host_requirement")
    require_current_frontend_row(requirement_rows, "QUAL-03", "qual_requirement")
    requirement_ids = [row[0] for row in requirement_rows]
    require(len(requirement_ids) == len(set(requirement_ids)),
            "requirements coverage contains duplicate requirement rows")
    status_index = 3 if len(requirement_rows[0]) == 5 else 2
    evidence_index = status_index + 1
    requirement_status = {row[0]: row[status_index] for row in requirement_rows}
    require(requirement_status.get("HOST-02") == "? NEEDS HUMAN / PENDING",
            "HOST-02 is not explicitly marked as awaiting human evidence")
    host_row = next(row for row in requirement_rows if row[0] == "HOST-02")
    require(has_frontend_load_uncertainty(host_row[evidence_index], scope="host"),
            "HOST-02 evidence no longer matches the current actual-app uncertainty record")
    qual_status = requirement_status.get("QUAL-03") or ""
    require(qual_status in {
        "✗ BLOCKED / PARTIAL", "? NEEDS HUMAN / PENDING", "? NEEDS HUMAN / PARTIAL", "? PARTIAL / NEEDS HUMAN",
    },
            "QUAL-03 is not explicitly marked blocked, partial, or pending human evidence")
    qual_row = next(row for row in requirement_rows if row[0] == "QUAL-03")
    require(has_frontend_load_uncertainty(qual_row[evidence_index], scope="qual"),
            "QUAL-03 evidence no longer explicitly marks actual frontend load unobserved or unknown")
    print("Phase 04 validation map matches current focused test results and preserves open security and frontend gates.")


if __name__ == "__main__":
    main()
