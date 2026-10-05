#!/usr/bin/env python3
"""Read-only terminal validation for the bounded Phase 01 admission assessment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PROFILE = "owned-p01-c14-continuation-2"
REQS = tuple(f"CPU-0{i}" for i in range(1, 6))
RESULTS = "experiments/owned_cpu/acceptance-results.json"
MANIFEST = "experiments/owned_cpu/source-manifest.json"
LEDGER = "experiments/owned_cpu/budget-ledger.json"
UAT = ".planning/phases/01-cpu-acceptance-experiment/01-UAT.md"
GATE = "Phase 01 remains open / GAPS_FOUND and Phase 02 gated"
MAX_FILE = 4 * 1024 * 1024


class EvidenceError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise EvidenceError(message)


def digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data, label):
    try:
        value = json.loads(data, object_pairs_hook=unique_pairs,
                           parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
    except EvidenceError:
        raise
    except (ValueError, TypeError) as error:
        raise EvidenceError(f"malformed JSON: {label}") from error
    need(isinstance(value, dict), f"JSON object required: {label}")
    return value


def file_bytes(root, relative, limit=MAX_FILE):
    need(isinstance(relative, str) and relative and "\\" not in relative, "invalid repository path")
    path = PurePosixPath(relative)
    need(not path.is_absolute() and all(part not in ("", ".", "..") for part in path.parts),
         "path must be repository-relative")
    target = root.joinpath(*path.parts)
    need(not target.is_symlink(), f"symlink evidence path rejected: {relative}")
    try:
        resolved = target.resolve(strict=True)
        data = target.read_bytes()
    except OSError as error:
        raise EvidenceError(f"missing evidence file: {relative}") from error
    need(root.resolve() in resolved.parents and target.is_file(), f"non-file/outside evidence path: {relative}")
    need(len(data) <= limit, f"evidence file exceeds size limit: {relative}")
    return data


def json_file(root, relative):
    return parse_json(file_bytes(root, relative), relative)


def file_hash(root, relative):
    return sha(file_bytes(root, relative))


def candidate_identity(root):
    results = json_file(root, RESULTS)
    rows = results.get("collections")
    need(isinstance(rows, list) and len(rows) == 6, "candidate must preserve all six collections")
    record = rows[-1]
    need(record.get("evidence_profile") == PROFILE and record.get("revision"), "current candidate profile missing")
    need(record.get("sha256") == digest({k: v for k, v in record.items() if k != "sha256"}),
         "current collection digest mismatch")
    source_hashes = record.get("source_hashes")
    need(isinstance(source_hashes, dict) and source_hashes, "current source map missing")
    manifest = json_file(root, MANIFEST)
    manifest_rows = manifest.get("files")
    need(isinstance(manifest_rows, list) and len(manifest_rows) == 38, "current source manifest closure changed")
    listed = {row.get("path"): row.get("sha256") for row in manifest_rows if isinstance(row, dict)}
    need(len(listed) == 38 and listed == {k: v for k, v in source_hashes.items() if k != MANIFEST},
         "collection and manifest source maps differ")
    need(source_hashes.get(MANIFEST) == file_hash(root, MANIFEST), "source manifest identity changed")
    for path, expected in source_hashes.items():
        need(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected) is not None,
             f"invalid source digest: {path}")
        need(file_hash(root, path) == expected, f"stale included source: {path}")
    need(manifest.get("runtime_archive_sources") == ["experiments/owned_cpu/cpu.c"] and
         manifest.get("generated_runtime") == [], "runtime closure differs from the reviewed owned core")

    seal = results.get("seal")
    need(results.get("disposition") == "unqualified" and isinstance(seal, dict) and
         seal.get("defer_admission") is True and len(results.get("superseded_seals", [])) == 3,
         "candidate receipt or superseded seal history changed")
    review_path = "experiments/owned_cpu/REVIEW.md"
    security_path = seal.get("security_path")
    review_hash, security_hash = file_hash(root, review_path), file_hash(root, security_path)
    need(seal.get("review", {}).get("sha256") == review_hash and
         seal.get("security", {}).get("sha256") == security_hash,
         "existing candidate report bytes no longer match the receipt")
    review_att = seal.get("review", {}).get("attestation", {})
    security_att = seal.get("security", {}).get("attestation", {})
    source_map_hash = digest(source_hashes)
    amendment_hash = record.get("amendment_sha256")
    need(seal.get("collection_sha256") == record.get("sha256") and
         review_att.get("collection_sha256") == record.get("sha256") and
         security_att.get("collection_sha256") == record.get("sha256") and
         review_att.get("source_map_sha256") == source_map_hash and
         security_att.get("source_map_sha256") == source_map_hash and
         review_att.get("amendment_sha256") == amendment_hash and
         security_att.get("amendment_sha256") == amendment_hash,
         "current receipt identity chain disagrees")
    need(review_att.get("hardware_saved_pc") == "unknown" and
         security_att.get("hardware_saved_pc") == "unknown" and
         security_att.get("review_sha256") == review_hash, "saved-PC uncertainty or report binding changed")
    need(security_att.get("open_high_or_critical") == 0, "existing security seal has open high/critical findings")

    return {
        "profile": PROFILE,
        "source_revision": record["revision"],
        "collection_sha256": record["sha256"],
        "source_map_sha256": source_map_hash,
        "amendment_sha256": amendment_hash,
        "active_contract_identity_sha256": record["active_contract_identity_sha256"],
        "contract_sha256": file_hash(root, "experiments/owned_cpu/CONTRACT.md"),
        "subset_sha256": file_hash(root, "experiments/owned_cpu/SUBSET.md"),
        "acceptance_sha256": file_hash(root, "experiments/owned_cpu/ACCEPTANCE.md"),
        "receipt_sha256": file_hash(root, RESULTS),
        "source_manifest_sha256": file_hash(root, MANIFEST),
        "state_inventory_sha256": file_hash(root, "experiments/owned_cpu/state-inventory.json"),
        "runtime_sha256": source_hashes["experiments/owned_cpu/cpu.c"],
        "oracle_sha256": file_hash(root, "tests/owned_cpu/ORACLE.md"),
        "old_review_sha256": review_hash,
        "old_security_sha256": security_hash,
        "hardware_saved_pc": "unknown",
        "unsupported_opcodes": ["0x4AFC"],
    }


def check_guards(root):
    requirements = file_bytes(root, ".planning/REQUIREMENTS.md").decode()
    roadmap = file_bytes(root, ".planning/ROADMAP.md").decode()
    state = file_bytes(root, ".planning/STATE.md").decode()
    acceptance = file_bytes(root, "experiments/owned_cpu/ACCEPTANCE.md").decode()
    for requirement in REQS:
        need(re.search(rf"\|\s*{requirement}\s*\|\s*Phase 1\s*\|\s*Pending\s*\|", requirements),
             f"{requirement} is no longer Pending")
    need(GATE in roadmap, "canonical Phase 01/02 admission gate changed")
    need("Disposition: **unqualified / GAPS_FOUND**" in acceptance and "This decision establishes no backend" in acceptance,
         "candidate-level unqualified disposition changed")
    need("CPU-01–05 remain Pending" in state and "Phase 02" in state and
         "Phase: 01" in state and "COMPLETE" not in state,
         "STATE no longer records the phase open and requirements pending")


def report_json(root, spec):
    need(isinstance(spec, dict), "report binding must be an object")
    path, expected = spec.get("path"), spec.get("sha256")
    data = file_bytes(root, path)
    need(sha(data) == expected, f"independent report hash mismatch: {path}")
    text = data.decode("utf-8")
    blocks = re.findall(r"```json\s*\n(.*?)\n```", text, re.S)
    need(len(blocks) == 1, f"independent report must contain one JSON assessment: {path}")
    return parse_json(blocks[0], path)


def valid_ref(root, ref):
    need(isinstance(ref, dict), "evidence reference must be an object")
    path, expected = ref.get("path"), ref.get("sha256")
    need(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected) is not None,
         "evidence reference digest missing")
    need(file_hash(root, path) == expected, f"stale evidence reference: {path}")
    need(isinstance(ref.get("claim"), str) and ref["claim"].strip(), "evidence claim missing")
    need(type(ref.get("denominator")) is int and ref["denominator"] > 0, "nonzero denominator required")
    need(isinstance(ref.get("oracle"), str) and ref["oracle"].strip(), "oracle ancestry missing")
    need(isinstance(ref.get("limitation"), str) and ref["limitation"].strip(), "evidence limitation missing")


def valid_blocker(blocker):
    need(isinstance(blocker, dict) and set(blocker) ==
         {"requirement", "predicate", "reason", "next_dependency", "evidence"},
         "blocker must name one exact predicate, reason and next dependency")
    need(blocker["requirement"] in (*REQS, "SECURITY"), "blocker requirement invalid")
    for field in ("predicate", "reason", "next_dependency"):
        need(isinstance(blocker[field], str) and len(blocker[field].strip()) >= 24,
             f"blocker {field} is vague or missing")
    need(isinstance(blocker["evidence"], list) and blocker["evidence"], "blocker needs direct evidence")
    return blocker


def validate_terminal(decision, review, security):
    need(type(decision.get("schema")) is int and decision["schema"] == 1, "decision schema mismatch")
    need(decision.get("disposition") in ("accept_recommended", "blocked"), "unknown terminal disposition")
    need(decision.get("phase_admitted") is False, "a gap assessment cannot admit the phase")
    need(decision.get("hardware_saved_pc") == "unknown", "original-silicon saved PC must remain unknown")
    identity = decision.get("identity")
    need(isinstance(identity, dict) and identity.get("profile") == PROFILE and
         identity.get("hardware_saved_pc") == "unknown" and identity.get("unsupported_opcodes") == ["0x4AFC"],
         "wrong candidate or support boundary")
    need(review.get("kind") == "cpu-admission-review" and
         security.get("kind") == "cpu-admission-security", "independent report roles mismatch")
    need(review.get("independent_non_author") is True and security.get("independent_non_author") is True,
         "independent non-author attestations required")
    need(review.get("agent_id") == decision.get("reviewer_agent_id") and
         security.get("agent_id") == decision.get("security_agent_id"), "report owner identity mismatch")
    need(len({decision.get("executor_agent_id"), review.get("agent_id"), security.get("agent_id")}) == 3,
         "executor, reviewer and assessor must be distinct")
    for report in (review, security):
        need(report.get("identity") == identity, "report evidence identity differs from decision")
        need(report.get("hardware_saved_pc") == "unknown" and
             report.get("unsupported_opcodes") == ["0x4AFC"] and report.get("hardware_claim") == "none",
             "report crosses the candidate-only support boundary")

    reqs = decision.get("requirements")
    reviewed = review.get("requirements")
    need(isinstance(reqs, dict) and set(reqs) == set(REQS), "decision must account for CPU-01 through CPU-05 once")
    need(isinstance(reviewed, dict) and set(reviewed) == set(REQS), "independent report must assess all five requirements")
    need(all(isinstance(item, dict) and item.get("decision") in {"sufficient", "blocked"} and
             isinstance(item.get("evidence"), list) and item["evidence"] for item in reqs.values()),
         "each decision predicate needs an explicit status and evidence")
    for requirement in REQS:
        item = reviewed[requirement]
        need(isinstance(item, dict) and item.get("decision") == reqs[requirement]["decision"] and
             item.get("evidence") == reqs[requirement]["evidence"],
             f"decision/report disagreement for {requirement}")
        evidence = item.get("evidence")
        need(isinstance(evidence, list) and evidence, f"{requirement} lacks evidence references")
        need(all(isinstance(ref, dict) for ref in evidence), f"{requirement} evidence references malformed")
        need(isinstance(item.get("limitation"), str) and item["limitation"].strip(),
             f"{requirement} limitation missing")

    security_count = security.get("open_high_or_critical")
    need(type(security_count) is int and security_count >= 0, "security count must be a nonnegative integer")
    security_status = "verified" if security_count == 0 else "blocked"
    need(security.get("status") == security_status and security.get("asvs_level") == 1 and
         security.get("block_on") == "high", "security disposition must use ASVS L1/high-block")
    decision_security = decision.get("security")
    need(isinstance(decision_security, dict) and decision_security.get("status") == security_status and
         decision_security.get("open_high_or_critical") == security_count, "security report/decision mismatch")

    req_blockers = [key for key, value in reqs.items() if value["decision"] == "blocked"]
    security_blocked = security_count > 0
    blockers = []
    if req_blockers:
        need(len(req_blockers) == 1, "multiple blocked requirements need separate evidence")
        need(review.get("blocker", {}).get("requirement") == req_blockers[0], "review blocker does not match unmet requirement")
        blockers.append(valid_blocker(review["blocker"]))
    else:
        need(review.get("blocker") is None, "review reports an unaccounted blocker")
    if security_blocked:
        blockers.append(valid_blocker(security.get("blocker")))
    else:
        need(security.get("blocker") is None, "security report has an unaccounted blocker")

    if decision["disposition"] == "accept_recommended":
        need(all(value["decision"] == "sufficient" for value in reqs.values()) and security_count == 0 and
             not blockers and decision.get("blocker") is None,
             "accept recommendation has an unmet predicate or blocking finding")
    else:
        need(len(blockers) == 1, "blocked outcome must identify exactly one material blocker")
        need(decision.get("blocker") == blockers[0], "blocked reason/evidence/dependency differs from independent report")
    return {"disposition": decision["disposition"], "phase_admitted": False,
            "blocker": decision.get("blocker")}


def load_reports(root, decision_path):
    decision = json_file(root, decision_path)
    reports = decision.get("reports")
    need(isinstance(reports, dict) and set(reports) == {"review", "security"}, "two report bindings required")
    review = report_json(root, reports["review"])
    security = report_json(root, reports["security"])
    return decision, review, security


def immutable_snapshot(root):
    identity = candidate_identity(root)
    results = json_file(root, RESULTS)
    ledger = json_file(root, LEDGER)
    uat = file_bytes(root, UAT)
    paths = (
        "experiments/owned_cpu/CONTRACT.md", "experiments/owned_cpu/SUBSET.md",
        "experiments/owned_cpu/ACCEPTANCE.md", RESULTS, MANIFEST,
        "experiments/owned_cpu/state-inventory.json", "experiments/owned_cpu/illegal-reconciliation.json",
        "experiments/owned_cpu/REVIEW.md", results["seal"]["security_path"],
        "tests/owned_cpu/ORACLE.md",
    )
    return {
        "immutable_files": {path: file_hash(root, path) for path in paths},
        "source_hashes": results["collections"][-1]["source_hashes"],
        "receipt_objects_sha256": digest({key: results.get(key) for key in ("collections", "superseded_seals", "seal")}),
        "ledger": {"prefix_entries": len(ledger["entries"]), "prefix_sha256": digest(ledger["entries"]),
                   "frozen_sha256": digest({k: v for k, v in ledger.items() if k != "entries"})},
        "uat": {"prefix_bytes": len(uat), "prefix_sha256": sha(uat),
                "historical_rows": len(re.findall(rb"(?m)^###\s+\d+\.", uat))},
        "identity": identity,
    }


def check_ledger_prefix(ledger, saved):
    before = saved["prefix_entries"]
    entries = ledger.get("entries")
    need(isinstance(entries, list) and len(entries) >= before, "ledger history was removed")
    need(digest(entries[:before]) == saved["prefix_sha256"], "ledger historical entries changed")
    need(digest({k: v for k, v in ledger.items() if k != "entries"}) == saved["frozen_sha256"],
         "frozen ledger fields changed")
    added = entries[before:]
    expected = saved.get("appended")
    need(isinstance(expected, dict) and len(added) == expected.get("count") and
         digest(added) == expected.get("sha256"), "ledger append differs from validated new charges")
    return added


def check_receipt_history(results, expected):
    keys = ("collections", "superseded_seals", "seal")
    need(digest({key: results.get(key) for key in keys}) == expected,
         "receipt collection/seal history changed")


def check_uat_prefix(data, saved):
    need(len(data) >= saved["prefix_bytes"] and sha(data[:saved["prefix_bytes"]]) == saved["prefix_sha256"],
         "historical UAT content changed")
    rows = len(re.findall(rb"(?m)^###\s+\d+\.", data))
    need(rows == saved.get("final_rows") and rows > saved["historical_rows"],
         "additive UAT rows missing or unexpected")
    tail = data[saved["prefix_bytes"]:]
    additions = re.split(rb"(?m)^###\s+\d+\. .*\n", tail)[1:]
    need(len(additions) == rows - saved["historical_rows"], "appended UAT rows malformed")
    for row in additions:
        need(re.search(rb"(?m)^result: (?:pass|blocked|unknown)$", row) and
             re.search(rb"(?m)^source: automated$", row) and
             re.search(rb"(?m)^command: \S", row) and re.search(rb"(?m)^evidence: \S", row),
             "appended UAT evidence is incomplete")
    return rows


def check_preservation(root, decision):
    snapshot = decision.get("preservation")
    need(isinstance(snapshot, dict), "preservation checkpoint missing")
    current = candidate_identity(root)
    need(snapshot.get("identity") == current == decision.get("identity"), "candidate identity changed")
    for path, expected in snapshot.get("immutable_files", {}).items():
        need(file_hash(root, path) == expected, f"preserved artifact changed: {path}")
    results = json_file(root, RESULTS)
    check_receipt_history(results, snapshot.get("receipt_objects_sha256"))
    source_hashes = snapshot.get("source_hashes")
    need(isinstance(source_hashes, dict) and source_hashes == results["collections"][-1]["source_hashes"],
         "preserved candidate source map changed")
    for path, expected in source_hashes.items():
        need(file_hash(root, path) == expected, f"candidate source changed: {path}")

    ledger = json_file(root, LEDGER)
    before = snapshot["ledger"]["prefix_entries"]
    added = check_ledger_prefix(ledger, snapshot["ledger"])
    need(file_hash(root, LEDGER) == snapshot.get("final_ledger_sha256"), "final ledger hash mismatch")
    try:
        budget = subprocess.run([sys.executable, "tools/owned_cpu/contract.py", "budget"], cwd=root,
                                text=True, capture_output=True, timeout=10, check=False)
        budget_result = json.loads(budget.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise EvidenceError(f"append-only budget validation failed: {error}") from error
    need(budget.returncode == 0 and budget_result.get("status") == "pass",
         "appended ledger charges fail the existing budget validator")

    rows = check_uat_prefix(file_bytes(root, UAT), snapshot["uat"])
    return {"immutable_files": len(snapshot["immutable_files"]), "candidate_sources": len(source_hashes),
            "receipt_collections": 6, "superseded_seals": 3, "ledger_prefix_entries": before,
            "ledger_appended_entries": len(added), "historical_uat_rows": old_uat["historical_rows"],
            "current_uat_rows": rows}


def verify(root, decision_path, preservation=False):
    decision, review, security = load_reports(root, decision_path)
    current = candidate_identity(root)
    need(decision.get("identity") == current, "decision identity is stale")
    check_guards(root)
    result = validate_terminal(decision, review, security)
    implementation = decision.get("implementation", {})
    need(implementation.get("checker_sha256") == file_hash(root, "tools/workflow/phase01_admission.py") and
         implementation.get("tests_sha256") == file_hash(root, "tests/workflow/test_phase01_admission.py"),
         "checker/test hash binding changed")
    ledger_hash = file_hash(root, LEDGER)
    need(decision.get("preservation", {}).get("final_ledger_sha256") == ledger_hash,
         "final ledger binding mismatch")
    for item in decision.get("requirements", {}).values():
        for ref in item.get("evidence", []):
            valid_ref(root, ref)
    for report in (review, security):
        for item in report.get("requirements", {}).values():
            for ref in item.get("evidence", []):
                valid_ref(root, ref)
        if report.get("blocker"):
            for ref in report["blocker"]["evidence"]:
                valid_ref(root, ref)
    if security.get("blocker"):
        for ref in security["blocker"]["evidence"]:
            valid_ref(root, ref)
    if preservation:
        result["preservation"] = check_preservation(root, decision)
    return result


def conditional_exit(root, decision_path, result):
    command = [sys.executable, "tools/workflow/phase01_admission.py", "verify", "--decision", decision_path,
               "--require-recommendation"]
    try:
        child = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EvidenceError(f"conditional recommendation child failed: {error}") from error
    try:
        payload = json.loads(child.stdout)
    except ValueError as error:
        raise EvidenceError("conditional recommendation child output is not JSON") from error
    expected = 0 if result["disposition"] == "accept_recommended" else 2
    need(child.returncode == expected and payload.get("disposition") == result["disposition"] and
         payload.get("phase_admitted") is False and payload.get("blocker") == result.get("blocker"),
         "conditional recommendation child exit/output mismatch")
    display_command = [Path(sys.executable).name, *command[1:]]
    return {"status": "conditional-pass", "disposition": result["disposition"],
            "phase_admitted": False, "child": {"command": display_command, "exit": child.returncode,
            "stdout": child.stdout[:8192], "stderr": child.stderr[:8192],
            "display_command": display_command, "interpreter_resolution": "sys.executable"}}


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("verify")
    check.add_argument("--decision", required=True)
    check.add_argument("--require-recommendation", action="store_true")
    check.add_argument("--check-recommendation-exit", action="store_true")
    check.add_argument("--check-preservation", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = verify(ROOT, args.decision, args.check_preservation)
        if args.require_recommendation:
            result = {"disposition": result["disposition"], "phase_admitted": False,
                      "blocker": result.get("blocker")}
            print(json.dumps(result, sort_keys=True))
            return 0 if result["disposition"] == "accept_recommended" else 2
        if args.check_recommendation_exit:
            result = conditional_exit(ROOT, args.decision, result)
        else:
            result["status"] = "validated"
        print(json.dumps(result, sort_keys=True))
        return 0
    except (EvidenceError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "invalid", "error": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
