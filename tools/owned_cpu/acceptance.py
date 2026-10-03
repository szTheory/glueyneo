#!/usr/bin/env python3
"""Local, append-only qualification receipts for the private owned CPU subset.

Required review headings are REVIEW_HEADINGS below. A review must record a full
revision, explicit independent non-author identity and disposition. Collection
does not admit the backend; sealing remains a separately reviewed decision.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.owned_cpu import contract, inventory

RESULTS = ROOT / "experiments/owned_cpu/acceptance-results.json"
MANDATORY = ("owned-debug", "owned-release", "owned-asan-ubsan")
LANES = MANDATORY + ("owned-tsan",)
CASES = {"owned_cpu_negative", "owned_cpu_isolation_negative", "owned_cpu_diagnostic",
         "owned_cpu_semantics", "owned_cpu_timing", "owned_cpu_timing_negative",
         "owned_cpu_isolation", "owned_cpu_cold", "owned_cpu_faults", "owned_cpu_state",
         "owned_cpu_inventory", "owned_cpu_inventory_check"}
UNITY = {"owned_cpu_diagnostic": 2, "owned_cpu_semantics": 17,
         "owned_cpu_timing": 23, "owned_cpu_isolation": 4,
         "owned_cpu_faults": 5, "owned_cpu_state": 5}
REVIEW_HEADINGS = ("Reviewed revision:", "Reviewer independence:", "Prior findings:",
                   "Evidence runs and denominators:", "Oracle ancestry:", "Findings and dispositions:")


class EvidenceError(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise EvidenceError(reason)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sanitize(value):
    return str(value).replace(str(ROOT), "$REPO").replace(str(Path.home()), "$HOME")


def run(command, timeout=180):
    start = time.monotonic()
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        child = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                               errors="replace", timeout=timeout, check=False)
        output, code = sanitize(child.stdout + child.stderr), child.returncode
        outcome = "pass" if code == 0 else "fail"
    except subprocess.TimeoutExpired as error:
        output = sanitize((error.stdout or b"").decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout or "")
        output += "\ncommand timed out"
        code, outcome = None, "unknown"
    except OSError as error:
        output, code, outcome = sanitize(error), None, "unknown"
    usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"command": [sanitize(item) for item in command], "exit": code,
            "status": outcome, "output": output,
            "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
            "child_user_seconds": usage_after.ru_utime - usage_before.ru_utime,
            "child_system_seconds": usage_after.ru_stime - usage_before.ru_stime,
            "elapsed_seconds": time.monotonic() - start}


def git(*arguments):
    child = subprocess.run(["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=False)
    require(child.returncode == 0, "git identity unavailable")
    return child.stdout.strip()


def snapshot():
    manifest = json.loads((ROOT / inventory.MANIFEST_PATH).read_text())
    require(not inventory.manifest_errors(ROOT, manifest), "source manifest stale or incomplete")
    return {row["path"]: row["sha256"] for row in manifest["files"]} | {
        inventory.MANIFEST_PATH.as_posix(): inventory.sha256(ROOT / inventory.MANIFEST_PATH)}


def validate_presets(document):
    require(document.get("version") == 2 and document.get("cmakeMinimumRequired") ==
            {"major": 3, "minor": 20, "patch": 0}, "preset floor/schema mismatch")
    groups = {}
    for group in ("configurePresets", "buildPresets", "testPresets"):
        rows = document.get(group, [])
        require(len(rows) == 4 and {row.get("name") for row in rows} == set(LANES), "preset names/duplicates")
        groups[group] = {row["name"]: row for row in rows}
    base = groups["configurePresets"]["owned-debug"]
    require(base.get("generator") == "Ninja" and base.get("cacheVariables") == {
        "GLUEYNEO_CPU_EXPERIMENT": "OFF", "GLUEYNEO_OWNED_CPU_EXPERIMENT": "ON",
        "CMAKE_BUILD_TYPE": "Debug", "GLUEYNEO_OWNED_CPU_OPTIMIZATION": "NONE",
        "GLUEYNEO_OWNED_CPU_SANITIZER": "NONE"}, "preset backend/options mismatch")
    overrides = {
        "owned-release": ("owned-debug", {"CMAKE_BUILD_TYPE": "Release", "GLUEYNEO_OWNED_CPU_OPTIMIZATION": "RELEASE"}),
        "owned-asan-ubsan": ("owned-debug", {"GLUEYNEO_OWNED_CPU_SANITIZER": "ADDRESS_UNDEFINED"}),
        "owned-tsan": ("owned-release", {"GLUEYNEO_OWNED_CPU_SANITIZER": "THREAD"})}
    for lane in LANES:
        row = groups["configurePresets"][lane]
        require(row.get("binaryDir") == "${sourceDir}/build/" + lane, "preset binary directory mismatch")
        if lane != "owned-debug":
            parent, cache = overrides[lane]
            require(row.get("inherits") == parent and row.get("cacheVariables") == cache,
                    "preset inherited options mismatch")
        require(set(row) <= {"name", "generator", "binaryDir", "cacheVariables", "inherits"}, "unreviewed preset override")
        require(groups["buildPresets"][lane] == {"name": lane, "configurePreset": lane, "jobs": 2}, "build worker/options mismatch")
        require(groups["testPresets"][lane] == {"name": lane, "configurePreset": lane,
                "output": {"outputOnFailure": True}, "execution": {"jobs": 2, "noTestsAction": "error"}}, "test worker/options mismatch")


def test_counts(content):
    blocks = list(re.finditer(r"(?m)^\d+/\d+ Testing:\s+(.+?)\s*$", content))
    require(len(blocks) == len(CASES), "empty/wrong CTest denominator")
    names = [match.group(1) for match in blocks]
    require(set(names) == CASES and len(names) == len(set(names)), "missing/duplicate CTest case")
    counts = {}
    for index, match in enumerate(blocks):
        block = content[match.end():blocks[index + 1].start() if index + 1 < len(blocks) else len(content)]
        name = match.group(1)
        require(len(re.findall(r"(?m)^Test Passed\.$", block)) == 1 and "Test Failed." not in block, "failed CTest case: " + name)
        if name in UNITY:
            summaries = re.findall(r"(?m)^(\d+) Tests (\d+) Failures (\d+) Ignored\s*$", block)
            require(summaries == [(str(UNITY[name]), "0", "0")], "wrong Unity denominator: " + name)
            counts[name] = UNITY[name]
        if name == "owned_cpu_state":
            require("state_checkpoints=13 " in block, "missing continuation checkpoints")
        if name == "owned_cpu_isolation":
            require("interleaved_pairs=32 " in block and "concurrent_pairs=32 " in block, "missing isolation denominator")
        if name == "owned_cpu_cold":
            require("cold_process_cases=16 fresh_processes=16 concurrent_instances=2" in block, "missing cold denominator")
        if name == "owned_cpu_negative":
            require(block.count("PASS:") == 3, "missing diagnostic/state controls")
        if name in ("owned_cpu_isolation_negative", "owned_cpu_timing_negative"):
            require(block.count("PASS:") == 1, "missing named negative control")
    return {"ctest_expected": 12, "ctest_observed": len(blocks), "unity": counts,
            "state_checkpoints": 13, "interleaved_pairs": 32, "concurrent_pairs": 32,
            "cold_processes": 16, "negative_controls": 5}


def classify_optional(step):
    # Only the exact CMake capability probe can establish unavailable support.
    if (step["exit"] not in (0, None) and
            "The selected compiler/linker cannot provide required ThreadSanitizer instrumentation" in step["output"]):
        return "unsupported"
    return step["status"]


def collect_lane(lane, optional):
    require(lane in LANES and (not optional or lane == "owned-tsan"), "unapproved preset")
    build = ROOT / "build" / lane
    receipt = {"preset": lane, "optional": optional, "steps": [], "status": "unknown"}
    commands = [["cmake", "--preset", lane], ["cmake", "--build", "--preset", lane, "--parallel", "2"],
                ["ctest", "--preset", lane, "--output-on-failure", "--no-tests=error"]]
    for command in commands:
        step = run(command)
        receipt["steps"].append(step)
        if step["status"] != "pass":
            receipt["status"] = classify_optional(step) if optional and len(receipt["steps"]) == 1 else step["status"]
            return receipt
    log = build / "Testing/Temporary/LastTest.log"
    content = sanitize(log.read_text(errors="replace"))
    receipt["test_log"] = content
    receipt["test_log_sha256"] = hashlib.sha256(content.encode()).hexdigest()
    try:
        receipt["counts"] = test_counts(content)
        errors = inventory.compile_errors(ROOT, build, sorted(inventory.EXPECTED_COMPILED_SOURCES))
        require(not errors, "compile closure: " + "; ".join(errors))
        cache = inventory.load_cache(build)
        receipt["configuration"] = {key: cache.get(key) for key in (
            "CMAKE_BUILD_TYPE", "GLUEYNEO_CPU_EXPERIMENT", "GLUEYNEO_OWNED_CPU_EXPERIMENT",
            "GLUEYNEO_OWNED_CPU_OPTIMIZATION", "GLUEYNEO_OWNED_CPU_SANITIZER")}
        expected_mode = "RELEASE" if lane in ("owned-release", "owned-tsan") else "NONE"
        expected_sanitizer = {"owned-asan-ubsan": "ADDRESS_UNDEFINED", "owned-tsan": "THREAD"}.get(lane, "NONE")
        require(cache.get("GLUEYNEO_CPU_EXPERIMENT") == "OFF" and cache.get("GLUEYNEO_OWNED_CPU_EXPERIMENT") == "ON" and
                cache.get("GLUEYNEO_OWNED_CPU_OPTIMIZATION") == expected_mode and cache.get("GLUEYNEO_OWNED_CPU_SANITIZER") == expected_sanitizer,
                "actual preset configuration differs")
        receipt["compiler"] = run([cache["CMAKE_C_COMPILER"], "--version"])
        compiler_output = receipt["compiler"]["output"]
        receipt["compiler"]["output"] = re.sub(r"(?m)^InstalledDir:.*\n?", "", compiler_output)
        receipt["compiler"]["output_sha256"] = hashlib.sha256(receipt["compiler"]["output"].encode()).hexdigest()
        receipt["artifacts"] = {path.relative_to(ROOT).as_posix(): inventory.sha256(path) for path in (
            build / "CMakeCache.txt", build / "build.ninja", build / "compile_commands.json",
            build / "experiments/owned_cpu/libowned_cpu.a", *(build / "experiments/owned_cpu" / target for target in sorted(inventory.EXECUTABLE_TARGETS)))}
        receipt["diagnostic_cost"] = run([str(build / "experiments/owned_cpu/owned_cpu_diagnostic")])
        require(receipt["diagnostic_cost"]["status"] == "pass", "descriptive diagnostic failed")
        receipt["diagnostic_cost"]["scope"] = "one diagnostic process including host startup; elapsed only; no gameplay throughput claim"
        receipt["diagnostic_cost"]["resource_measurement"] = "child user/system CPU deltas; peak resident memory unknown; single sample, startup dominated"
        receipt["status"] = "pass"
    except (EvidenceError, OSError, KeyError) as error:
        receipt["status"], receipt["blocker"] = "fail", sanitize(error)
    return receipt


def write(document):
    temporary = RESULTS.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RESULTS)


def collect(presets, optional):
    require(presets or optional, "no requested lanes")
    require(len(presets + optional) == len(set(presets + optional)), "duplicate requested lane")
    validate_presets(json.loads((ROOT / "CMakePresets.json").read_text()))
    document = json.loads(RESULTS.read_text()) if RESULTS.exists() else {"schema": 1, "collections": []}
    require(document.get("schema") == 1 and isinstance(document.get("collections"), list), "invalid collection document")
    record = {"recorded_at": datetime.now(timezone.utc).isoformat(), "revision": git("rev-parse", "HEAD"),
              "source_hashes": snapshot(), "host": {"os": platform.system(), "os_release": platform.release(),
              "architecture": platform.machine(), "python": platform.python_version()},
              "tools": {"cmake": run(["cmake", "--version"]), "ninja": run(["ninja", "--version"]),
                        "sdk": run(["xcrun", "--show-sdk-version"]) if platform.system() == "Darwin" else {"status": "unknown", "reason": "no SDK query for this host"}},
              "runs": []}
    record["limitations"] = ["CMake 3.20 execution unknown; schema 2 checked against official 3.20 documentation",
                             "Only recorded native host/compiler exercised; other platforms unknown",
                             "No silicon/board capture or gameplay performance oracle"]
    for lane in presets + optional:
        record["runs"].append(collect_lane(lane, lane in optional))
    record["sha256"] = digest(record)
    document["collections"].append(record)
    document["disposition"] = "unqualified"
    document["phase_disposition"] = "GAPS_FOUND"
    document["blockers"] = ["independent current-source review and bounded decision pending in Plan 01-14"]
    document.pop("seal", None)
    write(document)
    verify(document)
    return {lane["preset"]: lane["status"] for lane in record["runs"]}


def review_check(path, revision):
    revision = git("rev-parse", revision)
    text = path.read_text()
    return review_text(text, revision) | {"sha256": inventory.sha256(path)}


def review_text(text, revision):
    for heading in REVIEW_HEADINGS:
        require(re.search(r"(?m)^## " + re.escape(heading) + r"\s*$", text) is not None, "missing review heading: " + heading)
    section = text.split("## Reviewed revision:", 1)[1].split("##", 1)[0]
    require(revision in section, "stale review revision")
    require("Independent reviewer:" in text and "Authored runtime/collector/tests: no" in text,
            "review independence not recorded")
    require(re.search(r"(?m)^Disposition: (clean|GAPS_FOUND)\s*$", text) is not None, "review disposition missing")
    blocking = "Disposition: GAPS_FOUND" in text or re.search(r"(?im)\b(?:high|critical|blocker)\b.*\bopen\b", text) is not None
    require(not blocking, "blocking review finding")
    return {"revision": revision, "status": "clean"}


def budget_check(budget):
    require(budget.get("status") == "pass" and 0 < budget.get("active_seconds", 0) < contract.EFFORT_CAP_SECONDS,
            "budget requires pause/replan")
    require(0 < budget.get("runtime_churn_added_deleted", 0) < contract.RUNTIME_CHURN_CAP and
            0 < budget.get("test_tool_churn_added_deleted", 0) < contract.TEST_TOOL_CHURN_CAP,
            "churn threshold requires pause/replan")


def verify(document, current=True):
    require(document.get("schema") == 1 and document.get("collections"), "empty evidence")
    for record in document["collections"]:
        require(record.get("sha256") == digest({key: value for key, value in record.items() if key != "sha256"}), "corrupted collection")
        require(re.fullmatch(r"[0-9a-f]{40}", record.get("revision", "")) is not None, "missing revision")
        require(record.get("source_hashes") and record.get("host") and record.get("tools"), "missing identities")
        names = [row.get("preset") for row in record.get("runs", [])]
        require(names and len(names) == len(set(names)) and set(names) <= set(LANES), "empty/duplicate/foreign lanes")
        for row in record["runs"]:
            require(row.get("status") in ("pass", "fail", "unsupported", "unknown", "skipped"), "invalid lane status")
            require(row.get("steps"), "missing commands")
            for step in row["steps"]:
                require(step.get("command") and step.get("output_sha256") == hashlib.sha256(step.get("output", "").encode()).hexdigest(), "corrupted command output")
            if row["status"] == "pass":
                require(len(row["steps"]) == 3 and all(step.get("exit") == 0 for step in row["steps"]), "false successful lane")
                require(row.get("counts") == test_counts(row.get("test_log", "")), "wrong recorded counts")
                require(row.get("test_log_sha256") == hashlib.sha256(row["test_log"].encode()).hexdigest(), "corrupted test log")
                require(row.get("artifacts") and row.get("configuration") and row.get("compiler", {}).get("status") == "pass", "missing build identities")
            elif row["status"] == "unsupported":
                require(row.get("optional") is True and row["preset"] == "owned-tsan" and len(row["steps"]) == 1 and classify_optional(row["steps"][0]) == "unsupported", "false unsupported classification")
    latest = document["collections"][-1]
    if current:
        require(latest["source_hashes"] == snapshot(), "stale collected source")
        require(subprocess.run(["git", "merge-base", "--is-ancestor", latest["revision"], "HEAD"], cwd=ROOT).returncode == 0, "collected revision not current ancestor")
    runs = {row["preset"]: row for row in latest["runs"]}
    blockers = ["required lane unqualified: " + lane for lane in MANDATORY if lane not in runs or runs[lane]["status"] != "pass"]
    if document.get("disposition") == "accepted":
        require(not blockers, "accepted with unqualified lane")
        require(document.get("seal", {}).get("review", {}).get("status") == "clean", "accepted without review")
        require(document.get("seal", {}).get("collection_sha256") == latest["sha256"], "seal collection mismatch")
        if current:
            sealed = document["seal"]
            require(sealed["review"] == review_check(ROOT / "experiments/owned_cpu/REVIEW.md", sealed["revision"]), "stale sealed review")
            budget_check(contract.validate_budget(ROOT))
    else:
        require(document.get("disposition") == "unqualified" and document.get("phase_disposition") == "GAPS_FOUND" and document.get("blockers"), "unqualified without explicit blockers")
    return {"status": "pass", "disposition": document["disposition"], "collections": len(document["collections"]), "lane_blockers": blockers}


def seal(require_accepted=False):
    document = json.loads(RESULTS.read_text())
    result = verify(document)
    blockers = list(result["lane_blockers"])
    review = None
    try:
        review = review_check(ROOT / "experiments/owned_cpu/REVIEW.md", "HEAD")
    except (EvidenceError, OSError) as error:
        blockers.append(str(error))
    budget = contract.validate_budget(ROOT)
    try:
        budget_check(budget)
    except EvidenceError as error:
        blockers.append(str(error))
    # An earlier failed collection is never silently replaced by a later green run.
    if any(row["status"] in ("fail", "unknown", "skipped") for record in document["collections"] for row in record["runs"]):
        blockers.append("earlier collection failure/unknown requires independent disposition")
    document.update({"disposition": "unqualified" if blockers else "accepted", "phase_disposition": "GAPS_FOUND",
                     "blockers": blockers, "seal": {"revision": git("rev-parse", "HEAD"), "review": review,
                     "budget": budget, "collection_sha256": document["collections"][-1]["sha256"]}})
    write(document)
    verify(document)
    require(not require_accepted or not blockers, "acceptance required but blocked")
    return {"disposition": document["disposition"], "blockers": blockers}


def self_test():
    validate_presets(json.loads((ROOT / "CMakePresets.json").read_text()))
    controls = 0
    for name, action in (
        ("empty", lambda: verify({"schema": 1, "collections": []}, False)),
        ("counts", lambda: test_counts("")),
        ("corrupted", lambda: verify({"schema": 1, "collections": [{"sha256": "0" * 64}]}, False)),
        ("floor", lambda: validate_presets({"version": 3})),
        ("blocking", lambda: review_text("\n".join("## " + heading + "\n" + "a" * 40 for heading in REVIEW_HEADINGS) +
                                        "\nIndependent reviewer: non-author\nAuthored runtime/collector/tests: no\nDisposition: GAPS_FOUND\n", "a" * 40)),
        ("over-budget", lambda: budget_check({"status": "pass", "active_seconds": 115201}))):
        try:
            action()
        except (EvidenceError, contract.ContractError):
            controls += 1
        else:
            raise EvidenceError("self-test missed " + name)
    require(controls == 6, "empty control denominator")
    step = {"exit": 1, "status": "fail", "output": "random build failure"}
    require(classify_optional(step) == "fail", "misclassified optional failure")
    step["output"] = "The selected compiler/linker cannot provide required ThreadSanitizer instrumentation"
    require(classify_optional(step) == "unsupported", "missed optional capability failure")
    return {"status": "pass", "negative_controls": controls, "classification_controls": 2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("self-test", "verify"):
        sub.add_parser(name)
    collection = sub.add_parser("collect")
    collection.add_argument("--preset", action="append", default=[], choices=LANES)
    collection.add_argument("--optional-preset", action="append", default=[], choices=("owned-tsan",))
    sealing = sub.add_parser("seal")
    sealing.add_argument("--require-accepted", action="store_true")
    review = sub.add_parser("review-check")
    review.add_argument("--review", required=True, type=Path)
    review.add_argument("--revision", required=True)
    options = parser.parse_args()
    try:
        if options.command == "self-test":
            result = self_test()
        elif options.command == "collect":
            result = collect(options.preset, options.optional_preset)
        elif options.command == "verify":
            result = verify(json.loads(RESULTS.read_text()))
        elif options.command == "seal":
            result = seal(options.require_accepted)
        else:
            result = review_check(options.review, options.revision)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (EvidenceError, contract.ContractError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "fail", "reason": sanitize(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
