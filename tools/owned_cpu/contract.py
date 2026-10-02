#!/usr/bin/env python3
"""Small fail-closed validator and append-only recorder for the owned CPU experiment."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path("experiments/owned_cpu/CONTRACT.md")
LEDGER_PATH = Path("experiments/owned_cpu/budget-ledger.json")
CANONICAL_STORY = (
    "As a maintainer, I want to reproduce acceptance of a C 68000 backend, "
    "so that I can build the diagnostic SDK on independent instances with "
    "explicit state and timing limits."
)
EFFORT_CAP_SECONDS = 32 * 60 * 60
DIAGNOSTIC_CAP_SECONDS = 8 * 60 * 60
RUNTIME_CHURN_CAP = 6000
TEST_TOOL_CHURN_CAP = 8000

# Immutable evidence from the rejected Musashi experiment. These hashes are
# also copied to the owned ledger at freeze time. No code here rewrites them.
HISTORICAL_SHA256 = {
    "experiments/cpu/budget-ledger.json": "62266377e31f81cba19526c78fb23390bb21448181c06cdea1c77d385da43800",
    "experiments/cpu/ACCEPTANCE.md": "00b2da4548384c78e921d0085ced2147f0ec7eca30635a2961f49279dcd6cf3b",
    "experiments/cpu/REVIEW.md": "35bf8e3a849d05e90e7291c9868cffcae014ada4d1607ad3542de7f912e9be6e",
    "experiments/cpu/acceptance-results.json": "6e5efacd1ec655d803b4edb56570615ea8b8a81f89deda725ffc551a17bc3641",
    "experiments/cpu/evidence/plan-01-05/prior-acceptance-results.json": "3b9d6a736fb7ac8e647aed77f1ca9c10cc17233b3f1991c2d3be13ae25f9a2d3",
    "experiments/cpu/evidence/plan-01-05/prior-REVIEW.md": "254fae71bfdb3a468dec1126bfd4f8b4e73f8c194b6cc594945219243b17c649",
    "experiments/cpu/evidence/attempt-1/receipt.json": "c63d0fcfb2588498f7f0672a3a4d00d7f823a35fec6a575ea72163281a9fa721",
    "experiments/cpu/evidence/attempt-1/source.patch": "b69a0c887e92cd588892c024c33ebebe58e2031cac26ec83bb6175fea36772ce",
    "experiments/cpu/evidence/attempt-2/qualification.json": "fffc599d92dea0a401651f8e323805ce471cb26b54140c8876b0e7f74eb7ca55",
    "experiments/cpu/evidence/recovery-accounting/history.json": "27879b678585ba229303620469fa22cb25f1716412c4090e1962b53efcf1f3c4",
}

REQUIRED_MARKERS = (
    "MOVEQ #imm8,Dn",
    "0111 ddd 0 iiiiiiii",
    "ADDQ.L #1..8,Dn",
    "MOVE.L Dn,(abs.L)",
    "0010 001 111 000 ddd",
    "STOP #imm16",
    "UNSUPPORTED_OPCODE",
    "NOP",
    "RESET",
    "RTE",
    "TRAP #0",
    "ILLEGAL",
    "MOVE.W #imm16,SR",
    "MOVE.W (abs.L),Dn",
    "0011 ddd 000 111 001",
    "Level-3 IRQ masking",
    "Level-7 edge IRQ",
    "current SR priority is lowered below 7",
    "Address error",
    "32 cumulative active hours",
    "8-hour diagnostic gate",
    "6,000 cumulative added/deleted nonblank authored runtime",
    "8,000 cumulative added/deleted nonblank test/tool",
    "no substantive-attempt counter",
)


class ContractError(Exception):
    """A named contract failure suitable for tests and machine-readable output."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def require(condition: bool, reason: str, message: str) -> None:
    if not condition:
        raise ContractError(reason, message)


def sha256(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError as exc:
        raise ContractError("historical_hash", f"cannot read {path}: {exc}") from exc


def check_history(root: Path, expected: dict[str, str] = HISTORICAL_SHA256) -> dict[str, str]:
    observed: dict[str, str] = {}
    for relative, wanted in expected.items():
        path = root / relative
        require(path.is_file(), "historical_hash", f"missing frozen history file: {relative}")
        actual = sha256(path)
        require(actual == wanted, "historical_hash", f"frozen history changed: {relative}")
        observed[relative] = actual
    return observed


def _gsd_tools_path() -> Path | None:
    configured = os.environ.get("GSD_TOOLS")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.extend((Path.home() / ".codex/gsd-core/bin/gsd-tools.cjs",
                       Path.home() / ".agents/gsd-core/bin/gsd-tools.cjs"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def check_story(root: Path) -> dict:
    roadmap = root / ".planning/ROADMAP.md"
    require(roadmap.is_file(), "canonical_story", "ROADMAP.md is missing")
    require(CANONICAL_STORY in roadmap.read_text(encoding="utf-8"),
            "canonical_story", "canonical Phase 01 story changed or is absent")
    tools = _gsd_tools_path()
    node = shutil.which("node")
    require(tools is not None and node is not None, "story_validator_unavailable",
            "installed GSD story validator or Node.js is unavailable")
    result = subprocess.run(
        [node, str(tools), "query", "user-story.validate", "--story", CANONICAL_STORY],
        cwd=root, text=True, capture_output=True, check=False,
    )
    require(result.returncode == 0, "canonical_story",
            "installed GSD story validator returned nonzero: " + result.stderr.strip())
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError("canonical_story", "GSD story validator returned invalid JSON") from exc
    require(report.get("valid") is True and report.get("errors") == [], "canonical_story",
            "GSD story validator must return valid=true and errors=[]")
    return report


def check_requirements(root: Path) -> None:
    requirements_path = root / ".planning/REQUIREMENTS.md"
    roadmap_path = root / ".planning/ROADMAP.md"
    require(requirements_path.is_file(), "pending_gate", "REQUIREMENTS.md is missing")
    require(roadmap_path.is_file(), "pending_gate", "ROADMAP.md is missing")
    requirements = requirements_path.read_text(encoding="utf-8")
    roadmap = roadmap_path.read_text(encoding="utf-8")
    for requirement in ("CPU-01", "CPU-02", "CPU-03", "CPU-04", "CPU-05"):
        require(re.search(rf"\|\s*{requirement}\s*\|\s*Phase 1\s*\|\s*Pending\s*\|", requirements),
                "pending_gate", f"{requirement} must remain Pending for Phase 1")
    require("Phase 01 remains open / GAPS_FOUND and Phase 02 gated" in roadmap,
            "pending_gate", "Phase 01/02 admission gate changed")


def check_contract(root: Path, markers: tuple[str, ...] = REQUIRED_MARKERS) -> None:
    path = root / CONTRACT_PATH
    require(path.is_file(), "contract_missing", f"contract is missing: {CONTRACT_PATH}")
    content = path.read_text(encoding="utf-8")
    if "MOVEQ #imm8,Dn" in markers and "0111 ddd 0 iiiiiiii" in markers:
        require("0111 ddd 0 iiiiiiii" in content, "opcode_scope",
                "MOVEQ encoding scope is missing or changed")
    missing = [marker for marker in markers if marker not in content]
    require(not missing, "contract_requirement", "missing contract fields: " + ", ".join(missing))
    require("FPU" in content and "SoftFloat" in content and "generator" in content,
            "runtime_exclusions", "FPU, SoftFloat, or generator exclusion is missing")


def validate(root: Path = ROOT) -> dict:
    check_contract(root)
    history = check_history(root)
    story = check_story(root)
    check_requirements(root)
    return {"status": "pass", "contract_markers": len(REQUIRED_MARKERS),
            "historical_files": len(history), "canonical_story": story,
            "requirements_pending": ["CPU-01", "CPU-02", "CPU-03", "CPU-04", "CPU-05"],
            "phase_02": "gated"}


def _integer(value, name: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            "ledger_schema", f"{name} must be a nonnegative integer")
    return value


def _parse_time(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ContractError("agent_intervals", f"invalid {name} timestamp: {value!r}") from exc
    require(parsed.tzinfo is not None, "agent_intervals", f"{name} timestamp must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _interval_seconds(interval: dict) -> int:
    agent = interval.get("agent")
    require(isinstance(agent, str) and agent.strip(), "agent_intervals", "agent identity is required")
    start = _parse_time(interval.get("start"), "start")
    end = _parse_time(interval.get("end"), "end")
    require(end > start, "agent_intervals", "agent interval end must follow start")
    return int((end - start).total_seconds())


def validate_budget(root: Path = ROOT) -> dict:
    path = root / LEDGER_PATH
    require(path.is_file(), "ledger_missing", f"owned budget ledger is missing: {LEDGER_PATH}")
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("ledger_schema", f"cannot parse owned budget ledger: {exc}") from exc
    require(ledger.get("schema") == 1, "ledger_schema", "unsupported owned ledger schema")
    require(ledger.get("status") == "frozen-pre-implementation", "ledger_freeze",
            "ledger must retain its pre-implementation freeze status")
    baseline = ledger.get("code_start")
    require(isinstance(baseline, dict), "ledger_schema", "code_start record is required")
    commit = baseline.get("commit")
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
            "ledger_schema", "code_start commit must be a full lowercase Git object ID")
    contract_hash = baseline.get("contract_sha256")
    require(isinstance(contract_hash, str) and re.fullmatch(r"[0-9a-f]{64}", contract_hash) is not None,
            "ledger_schema", "code_start contract SHA-256 is required")
    require(contract_hash == sha256(root / CONTRACT_PATH), "ledger_freeze",
            "contract differs from the pre-implementation frozen digest")
    expected_history = ledger.get("historical_sha256")
    require(expected_history == HISTORICAL_SHA256, "historical_hash",
            "ledger's frozen Musashi hashes differ from the contract baseline")
    check_history(root, expected_history)

    caps = ledger.get("caps")
    require(caps == {"active_effort_seconds": EFFORT_CAP_SECONDS,
                     "diagnostic_gate_seconds": DIAGNOSTIC_CAP_SECONDS,
                     "runtime_churn_added_deleted_nonblank_lines": RUNTIME_CHURN_CAP,
                     "test_tool_churn_added_deleted_nonblank_lines": TEST_TOOL_CHURN_CAP},
            "caps_changed", "owned effort or churn caps changed")
    entries = ledger.get("entries")
    require(isinstance(entries, list) and entries, "required_records",
            "at least the 01-07 governance effort record is required")
    require(isinstance(entries[0], dict) and entries[0].get("stage") == "plan-01-07-governance"
            and entries[0].get("diagnostic_gate") is False,
            "required_records", "first entry must charge 01-07 governance outside the diagnostic clock")
    total_effort = 0
    diagnostic_effort = 0
    for entry in entries:
        require(isinstance(entry, dict), "ledger_schema", "ledger entry must be an object")
        intervals = entry.get("agent_intervals")
        require(isinstance(intervals, list) and intervals, "agent_intervals",
                "every effort record must contain explicit agent intervals")
        seconds = sum(_interval_seconds(interval) for interval in intervals)
        recorded = _integer(entry.get("active_seconds"), "entry.active_seconds")
        require(recorded == seconds, "agent_intervals",
                "recorded effort must equal the sum of its explicit agent intervals")
        tests = entry.get("test_results")
        require(isinstance(tests, dict) and tests.get("expected", 0) > 0
                and tests.get("observed", 0) > 0 and tests.get("status") == "pass",
                "required_records", "each stage needs nonempty passing test results")
        total_effort += recorded
        if entry.get("diagnostic_gate") is True:
            diagnostic_effort += recorded
        churn = entry.get("cumulative_churn")
        require(isinstance(churn, dict), "required_records", "cumulative churn record is required")
        for key in ("runtime_added", "runtime_deleted", "test_tool_added", "test_tool_deleted"):
            _integer(churn.get(key), "cumulative_churn." + key)
    require(total_effort <= EFFORT_CAP_SECONDS, "effort_cap", "32-hour cumulative effort cap exceeded")
    require(diagnostic_effort <= DIAGNOSTIC_CAP_SECONDS, "diagnostic_cap",
            "8-hour diagnostic effort gate exceeded")
    final_churn = entries[-1]["cumulative_churn"]
    runtime_churn = final_churn["runtime_added"] + final_churn["runtime_deleted"]
    tooling_churn = final_churn["test_tool_added"] + final_churn["test_tool_deleted"]
    require(ledger.get("threshold_policy") == "pause-for-user-scope-review",
            "threshold_outcome", "threshold policy must pause for a user scope review")
    over_runtime = runtime_churn > RUNTIME_CHURN_CAP
    over_tooling = tooling_churn > TEST_TOOL_CHURN_CAP
    pause = ledger.get("pause")
    paused = over_runtime or over_tooling or (isinstance(pause, dict) and pause.get("active") is True)
    if over_runtime or over_tooling:
        require(isinstance(pause, dict) and pause.get("active") is True
                and pause.get("disposition") == "pause-for-user-scope-review"
                and pause.get("reason") in ("runtime-churn-threshold", "test-tool-churn-threshold"),
                "threshold_outcome", "exceeded churn needs a named pause/replan record")
    return {"status": "pause-for-review" if paused else "pass",
            "phase_disposition": "GAPS_FOUND" if paused else "not-admitted",
            "active_seconds": total_effort,
            "diagnostic_gate_seconds": diagnostic_effort,
            "runtime_churn_added_deleted": runtime_churn,
            "test_tool_churn_added_deleted": tooling_churn,
            "records": len(entries), "pause": pause if paused else None}


def _parse_intervals(values: list[str]) -> list[dict]:
    intervals = []
    for value in values:
        parts = value.split(",", 2)
        require(len(parts) == 3, "agent_intervals",
                "use --agent-interval AGENT,START_ISO8601,END_ISO8601")
        interval = {"agent": parts[0].strip(), "start": parts[1].strip(), "end": parts[2].strip()}
        _interval_seconds(interval)
        intervals.append(interval)
    require(bool(intervals), "agent_intervals", "at least one --agent-interval is required")
    return intervals


def _git_output(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True,
                            capture_output=True, check=False)
    require(result.returncode == 0, "git_identity",
            "Git identity query failed: " + result.stderr.strip())
    return result.stdout.strip()


def _nonblank_numstat(root: Path, baseline: str, category_paths: list[str]) -> tuple[int, int]:
    committed = _git_output(root, "log", "--format=", "--no-ext-diff", "--no-renames",
                            "--unified=0", f"{baseline}..HEAD", "--", *category_paths)
    pending = _git_output(root, "diff", "--no-ext-diff", "--unified=0", "HEAD", "--",
                          *category_paths)
    added = 0
    deleted = 0
    for output in (committed, pending):
        for line in output.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+") and line[1:].strip():
                added += 1
            elif line.startswith("-") and line[1:].strip():
                deleted += 1
    untracked = _git_output(root, "ls-files", "--others", "--exclude-standard", "--", *category_paths)
    for relative in untracked.splitlines():
        path = root / relative
        require(path.is_file(), "churn_measurement", f"untracked churn path disappeared: {relative}")
        try:
            added += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        except (OSError, UnicodeDecodeError) as exc:
            raise ContractError("churn_measurement", f"cannot count {relative}: {exc}") from exc
    return added, deleted


def _test_results(build_dir: Path) -> dict:
    log = build_dir / "Testing/Temporary/LastTest.log"
    require(log.is_file(), "stage_test_results", "CTest LastTest.log is missing")
    content = log.read_text(encoding="utf-8", errors="replace")
    passed = re.findall(r"(?m)^\d+/\d+ Test #\d+:\s+(.+?)\s+\.\.\.\s+Passed", content)
    failed_log = build_dir / "Testing/Temporary/LastTestsFailed.log"
    failed = failed_log.read_text(encoding="utf-8", errors="replace").splitlines() if failed_log.is_file() else []
    require(bool(passed), "stage_test_results", "CTest log contains no observed passing cases")
    require(not failed, "stage_test_results", "CTest last-failure file is nonempty")
    return {"expected": len(passed), "observed": len(passed), "status": "pass",
            "cases": passed, "log_sha256": sha256(log)}


def record(root: Path, stage: str, build_dir: Path, interval_values: list[str]) -> dict:
    before = validate_budget(root)
    require(before["status"] == "pass", "scope_pause", "mutation is paused pending user scope review")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", stage) is not None,
            "stage_name", "stage name contains unsupported characters")
    intervals = _parse_intervals(interval_values)
    seconds = sum(_interval_seconds(interval) for interval in intervals)
    root = root.resolve()
    build_dir = build_dir.resolve()
    require(build_dir.is_dir(), "build_identity", f"build directory does not exist: {build_dir}")
    try:
        relative_build_dir = build_dir.relative_to(root).as_posix()
    except ValueError as exc:
        raise ContractError("build_identity", "build directory must be inside the checkout; absolute paths are not recorded") from exc
    cache = build_dir / "CMakeCache.txt"
    ninja = build_dir / "build.ninja"
    require(cache.is_file() and ninja.is_file(), "build_identity",
            "CMakeCache.txt and build.ninja are required build identities")
    tests = _test_results(build_dir)
    baseline = json.loads((root / LEDGER_PATH).read_text(encoding="utf-8"))["code_start"]["commit"]
    runtime_paths = ["experiments/owned_cpu/*.c", "experiments/owned_cpu/*.h"]
    test_tool_paths = ["CMakeLists.txt", "experiments/owned_cpu/CMakeLists.txt",
                       "tests/owned_cpu", "tools/owned_cpu", "CMakePresets.json"]
    runtime_added, runtime_deleted = _nonblank_numstat(root, baseline, runtime_paths)
    test_tool_added, test_tool_deleted = _nonblank_numstat(root, baseline, test_tool_paths)
    fixture_paths = [root / "tests/cpu/guest_fixture.c", root / "tests/cpu/guest_fixture.h",
                     root / "tests/cpu/ORACLE.md"]
    fixture_hashes = {p.relative_to(root).as_posix(): sha256(p) for p in fixture_paths if p.is_file()}
    require(len(fixture_hashes) == len(fixture_paths), "fixture_identity", "diagnostic fixture/oracle is incomplete")
    ledger_path = root / LEDGER_PATH
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = {
        "stage": stage,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "commit": _git_output(root, "rev-parse", "HEAD"),
        "working_tree_dirty": bool(_git_output(root, "status", "--porcelain")),
        "build_dir": relative_build_dir,
        "build_identity": {"cmake_cache_sha256": sha256(cache), "build_ninja_sha256": sha256(ninja)},
        "fixture_sha256": fixture_hashes,
        "agent_intervals": intervals,
        "active_seconds": seconds,
        "diagnostic_gate": stage not in ("plan-01-07-governance",),
        "test_results": tests,
        "cumulative_churn": {"runtime_added": runtime_added, "runtime_deleted": runtime_deleted,
                              "test_tool_added": test_tool_added, "test_tool_deleted": test_tool_deleted},
    }
    ledger["entries"].append(entry)
    runtime_total = runtime_added + runtime_deleted
    tooling_total = test_tool_added + test_tool_deleted
    if runtime_total > RUNTIME_CHURN_CAP or tooling_total > TEST_TOOL_CHURN_CAP:
        ledger["pause"] = {
            "active": True,
            "reason": "runtime-churn-threshold" if runtime_total > RUNTIME_CHURN_CAP
                     else "test-tool-churn-threshold",
            "disposition": "pause-for-user-scope-review",
            "runtime_added_deleted": runtime_total,
            "test_tool_added_deleted": tooling_total,
            "recorded_at": entry["recorded_at"],
        }
    pause = ledger.get("pause")
    is_paused = isinstance(pause, dict) and pause.get("active") is True
    result = {**entry, "status": "pause-for-review" if is_paused else "pass",
              "phase_disposition": "GAPS_FOUND" if is_paused else "not-admitted"}
    temporary = ledger_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, ledger_path)
    updated = validate_budget(root)
    result["status"] = updated["status"]
    result["phase_disposition"] = updated["phase_disposition"]
    result["budget_totals"] = updated
    return result


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _copy_subject(target: Path) -> None:
    for relative in (CONTRACT_PATH, Path(".planning/REQUIREMENTS.md"), Path(".planning/ROADMAP.md"),
                     Path("tests/cpu/guest_fixture.c"), Path("tests/cpu/guest_fixture.h"),
                     Path("tests/cpu/ORACLE.md")):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    for relative in HISTORICAL_SHA256:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    commit = _git_output(ROOT, "rev-parse", "HEAD")
    ledger = {
        "schema": 1,
        "status": "frozen-pre-implementation",
        "code_start": {"commit": commit, "contract_sha256": sha256(ROOT / CONTRACT_PATH)},
        "historical_sha256": HISTORICAL_SHA256,
        "caps": {"active_effort_seconds": EFFORT_CAP_SECONDS,
                 "diagnostic_gate_seconds": DIAGNOSTIC_CAP_SECONDS,
                 "runtime_churn_added_deleted_nonblank_lines": RUNTIME_CHURN_CAP,
                 "test_tool_churn_added_deleted_nonblank_lines": TEST_TOOL_CHURN_CAP},
        "threshold_policy": "pause-for-user-scope-review",
        "pause": None,
        "entries": [{"stage": "plan-01-07-governance", "active_seconds": 1,
                     "agent_intervals": [{"agent": "self-test", "start": "2026-01-01T00:00:00Z",
                                          "end": "2026-01-01T00:00:01Z"}],
                     "test_results": {"expected": 1, "observed": 1, "status": "pass"},
                     "diagnostic_gate": False,
                     "cumulative_churn": {"runtime_added": 0, "runtime_deleted": 0,
                                           "test_tool_added": 0, "test_tool_deleted": 0}}],
    }
    _write_json(target / LEDGER_PATH, ledger)


def _expect_reason(action, wanted: str, name: str) -> None:
    try:
        action()
    except ContractError as exc:
        require(exc.reason == wanted, "self_test", f"{name}: expected {wanted}, got {exc.reason}")
        return
    raise ContractError("self_test", f"{name}: expected rejection {wanted}, but validation passed")


def self_test() -> dict:
    controls = 0
    with tempfile.TemporaryDirectory(prefix="owned-cpu-contract-") as temporary:
        subject = Path(temporary)
        _copy_subject(subject)
        check_contract(subject)
        check_history(subject)
        check_story(subject)
        check_requirements(subject)
        validate_budget(subject)

        contract_file = subject / CONTRACT_PATH
        original_contract = contract_file.read_text(encoding="utf-8")
        contract_file.write_text(original_contract.replace("0111 ddd 0 iiiiiiii", "0111 ??? changed"),
                                 encoding="utf-8")
        _expect_reason(lambda: check_contract(subject), "opcode_scope", "opcode scope mutation")
        controls += 1
        contract_file.write_text(original_contract, encoding="utf-8")

        ledger_file = subject / LEDGER_PATH
        baseline_ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
        too_much = json.loads(json.dumps(baseline_ledger))
        too_much["entries"][0]["active_seconds"] = EFFORT_CAP_SECONDS + 1
        _write_json(ledger_file, too_much)
        _expect_reason(lambda: validate_budget(subject), "agent_intervals", "effort total mismatch")
        controls += 1
        too_much["entries"][0]["agent_intervals"][0]["end"] = "2026-01-02T08:00:02Z"
        too_much["entries"][0]["active_seconds"] = EFFORT_CAP_SECONDS + 2
        _write_json(ledger_file, too_much)
        _expect_reason(lambda: validate_budget(subject), "effort_cap", "effort cap mutation")
        controls += 1

        history_target = subject / "experiments/cpu/ACCEPTANCE.md"
        history_target.write_text(history_target.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
        _expect_reason(lambda: check_history(subject), "historical_hash", "frozen history mutation")
        controls += 1
        shutil.copyfile(ROOT / "experiments/cpu/ACCEPTANCE.md", history_target)

        empty = json.loads(json.dumps(baseline_ledger))
        empty["entries"] = []
        _write_json(ledger_file, empty)
        _expect_reason(lambda: validate_budget(subject), "required_records", "empty required records")
        controls += 1

        script = Path(__file__).resolve()
        probe = subprocess.run([sys.executable, "-O", str(script), "_probe-empty-ledger", str(subject)],
                               cwd=ROOT, text=True, capture_output=True, check=False)
        try:
            probe_report = json.loads(probe.stderr)
        except json.JSONDecodeError:
            probe_report = {}
        require(probe.returncode == 2 and probe_report.get("reason") == "required_records",
                "self_test", "optimized-Python empty-record control did not fail by named reason")
        controls += 1

        _write_json(ledger_file, baseline_ledger)
        optimized_positive = subprocess.run([sys.executable, "-O", str(script), "_probe-valid-ledger", str(subject)],
                                            cwd=ROOT, text=True, capture_output=True, check=False)
        require(optimized_positive.returncode == 0 and '"status": "pass"' in optimized_positive.stdout,
                "self_test", "optimized-Python positive validation did not pass")

    require(controls >= 5, "self_test", "negative-control denominator is empty")
    return {"status": "pass", "positive_cases": 2, "negative_controls": controls,
            "control_names": ["scope", "interval-mismatch", "effort-cap", "frozen-history",
                              "empty-records", "python-O"]}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate current scope, immutable history, story, and admission gate")
    sub.add_parser("budget", help="validate the frozen owned effort/churn ledger")
    sub.add_parser("self-test", help="exercise positive and named negative controls")
    rec = sub.add_parser("record", help="append measured stage effort, churn, build, fixture, and test evidence")
    rec.add_argument("--stage", required=True)
    rec.add_argument("--build-dir", required=True, type=Path)
    rec.add_argument("--agent-interval", action="append", default=[], metavar="AGENT,START,END")
    probe = sub.add_parser("_probe-empty-ledger", help=argparse.SUPPRESS)
    probe.add_argument("root", type=Path)
    probe = sub.add_parser("_probe-valid-ledger", help=argparse.SUPPRESS)
    probe.add_argument("root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = validate()
        elif args.command == "budget":
            result = validate_budget()
        elif args.command == "self-test":
            result = self_test()
        elif args.command == "record":
            result = record(ROOT, args.stage, args.build_dir, args.agent_interval)
        elif args.command == "_probe-empty-ledger":
            validate_budget(args.root)
            raise ContractError("self_test", "empty ledger probe unexpectedly passed")
        elif args.command == "_probe-valid-ledger":
            result = validate_budget(args.root)
        else:
            raise ContractError("command", "unknown command")
    except ContractError as exc:
        print(json.dumps({"status": "fail", "reason": exc.reason, "message": str(exc)}, sort_keys=True),
              file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("status") == "pause-for-review":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
