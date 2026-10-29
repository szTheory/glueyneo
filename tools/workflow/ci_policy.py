"""Conservative changed-path classification and required CI aggregation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import private_paths  # noqa: E402

MATRIX_JOB = "matrix"
DOCS_JOB = "public-content"
AGGREGATE_JOB = "ci-policy"
REQUIRED_JOBS = frozenset((MATRIX_JOB, DOCS_JOB))
_COMMIT_SHA_LENGTH = 40
_DOCUMENTATION_SUFFIXES = frozenset({".gif", ".jpeg", ".jpg", ".md", ".png", ".rst", ".svg", ".txt", ".webp"})


def _is_commit_sha(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == _COMMIT_SHA_LENGTH
            and all(character in "0123456789abcdefABCDEF" for character in value))


def validate_merge_readiness(receipt: dict[str, Any], *, proposed_sha: str) -> dict[str, Any]:
    """Validate a local merge receipt whose CI and independent review bind to one PR head."""
    issues: list[str] = []
    if not _is_commit_sha(proposed_sha):
        issues.append("proposed head is not a full commit SHA")
    if receipt.get("schema_version") != 1:
        issues.append("unsupported or missing merge receipt schema_version")
    if receipt.get("pr_head_sha") != proposed_sha:
        issues.append("receipt PR head does not match proposed merge SHA")

    aggregate = receipt.get("required_aggregate")
    if not isinstance(aggregate, dict):
        issues.append("required aggregate receipt is missing")
    else:
        if aggregate.get("sha") != proposed_sha:
            issues.append("required aggregate SHA is stale")
        if aggregate.get("outcome") != "pass":
            issues.append("required aggregate did not pass")
        for field in ("lane_count", "assertion_count"):
            value = aggregate.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                issues.append(f"required aggregate has no positive {field}")

    review = receipt.get("independent_review")
    if not isinstance(review, dict):
        issues.append("independent GSD code review receipt is missing")
    else:
        if review.get("sha") != proposed_sha:
            issues.append("independent GSD code review SHA is stale")
        if review.get("review_type") != "gsd-code-review":
            issues.append("review receipt is not identified as an independent GSD code review")
        if review.get("outcome") != "pass":
            issues.append("independent GSD code review did not pass")
        findings = review.get("findings")
        if not isinstance(findings, list):
            issues.append("review findings must be an explicit list")
        else:
            for index, finding in enumerate(findings):
                if not isinstance(finding, dict):
                    issues.append(f"review finding {index} is malformed")
                    continue
                status = finding.get("status")
                if status == "resolved":
                    evidence = finding.get("evidence")
                    if not isinstance(evidence, str) or not evidence.strip():
                        issues.append(f"resolved review finding {index} lacks resolution evidence")
                    continue
                if status != "dispositioned":
                    issues.append(f"review finding {index} is open or has an invalid status")
                    continue
                disposition = finding.get("disposition")
                evidence = finding.get("evidence")
                if not isinstance(disposition, str) or not disposition.strip():
                    issues.append(f"review finding {index} lacks a disposition")
                if not isinstance(evidence, str) or not evidence.strip():
                    issues.append(f"review finding {index} disposition lacks evidence")

    return {"outcome": "fail" if issues else "pass", "issues": issues,
            "proposed_sha": proposed_sha}


def classify_paths(paths: Iterable[str] | None, *, diff_error: bool = False) -> set[str]:
    """Select all jobs unless every changed path is known documentation-only."""
    if paths is None or diff_error:
        return set(REQUIRED_JOBS)
    rows = list(paths)
    if not rows:
        return set(REQUIRED_JOBS)
    docs_only = all(path in {"README.md", "LICENSE"} or
                    (path.startswith("docs/") and Path(path).suffix.lower() in _DOCUMENTATION_SUFFIXES)
                    for path in rows)
    return {DOCS_JOB} if docs_only else set(REQUIRED_JOBS)


def validate_aggregate(jobs: dict[str, Any], *, planned: set[str]) -> dict[str, Any]:
    """Fail closed on absent, unsuccessful, empty or zero-evidence required jobs."""
    issues: list[str] = []
    lane_count = assertion_count = 0
    if planned - REQUIRED_JOBS:
        issues.append("classifier selected an unknown job")
    for name in sorted(REQUIRED_JOBS):
        row = jobs.get(name)
        if not isinstance(row, dict):
            issues.append(f"missing job record: {name}")
            continue
        result = row.get("result")
        if name not in planned:
            if result != "skipped":
                issues.append(f"unplanned job must be recorded skipped: {name}")
            continue
        if result != "success":
            issues.append(f"required job did not succeed: {name} ({result or 'missing'})")
            continue
        lanes = row.get("lane_count")
        assertions = row.get("assertion_count")
        if not isinstance(lanes, int) or isinstance(lanes, bool) or lanes <= 0:
            issues.append(f"required job has no completed lane denominator: {name}")
        if not isinstance(assertions, int) or isinstance(assertions, bool) or assertions <= 0:
            issues.append(f"required job has no positive assertion denominator: {name}")
        lane_count += lanes if isinstance(lanes, int) and not isinstance(lanes, bool) and lanes > 0 else 0
        assertion_count += assertions if isinstance(assertions, int) and not isinstance(assertions, bool) and assertions > 0 else 0
    if DOCS_JOB not in planned or DOCS_JOB not in jobs:
        issues.append("documentation/privacy gate is absent")
    return {"outcome": "fail" if issues else "pass", "issues": issues,
            "planned_jobs": sorted(planned), "lane_count": lane_count,
            "assertion_count": assertion_count}


def classify_diff(paths: list[str] | None, *, diff_error: bool = False) -> dict[str, Any]:
    selected = classify_paths(paths, diff_error=diff_error)
    return {"schema_version": 1, "outcome": "pass", "paths_known": paths is not None and not diff_error,
            "selected_jobs": sorted(selected), "matrix": MATRIX_JOB in selected,
            "public_content": DOCS_JOB in selected}


def public_content_control_counts(root: Path) -> tuple[int, int]:
    """Return measured unittest case and TestCase assertion-method invocation counts."""
    counted_runner = r'''
import io, inspect, json, re, unittest
counts = {"assertions": 0}
for name in dir(unittest.TestCase):
    method = getattr(unittest.TestCase, name)
    if name.startswith(("assert", "fail")) and inspect.isfunction(method):
        def counted(self, *args, _method=method, **kwargs):
            counts["assertions"] += 1
            return _method(self, *args, **kwargs)
        setattr(unittest.TestCase, name, counted)
suite = unittest.defaultTestLoader.discover("tests/workflow", pattern="test_public_content.py")
result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
failures = result.failures + result.errors
test_ids = []
for test, _detail in failures:
    try:
        identifier = test.id()
    except Exception:
        identifier = ""
    if isinstance(identifier, str) and re.fullmatch(r"[A-Za-z0-9_.]{1,160}", identifier):
        test_ids.append(identifier)
    else:
        test_ids.append("unidentified-test")
summary = {
    "assertions": counts["assertions"],
    "cases": result.testsRun,
    "failure_count": len(failures),
    "failure_test_ids": sorted(set(test_ids))[:5],
    "failure_test_ids_truncated": len(set(test_ids)) > 5,
    "outcome": "pass" if result.wasSuccessful() else "fail",
}
print("PUBLIC_CONTENT_RESULT=" + json.dumps(summary, sort_keys=True, separators=(",", ":")))
raise SystemExit(0 if result.wasSuccessful() else 1)
'''
    child_env = dict(os.environ)
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    control_result = subprocess.run([sys.executable, "-c", counted_runner], cwd=root.resolve(),
                                    env=child_env, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=60, check=False)
    summaries = re.findall(r"(?m)^PUBLIC_CONTENT_RESULT=([^\r\n]{1,4096})$",
                           control_result.stdout or "")
    summary: dict[str, Any] | None = None
    if summaries:
        try:
            candidate = json.loads(summaries[-1])
            if isinstance(candidate, dict):
                summary = candidate
        except (ValueError, TypeError):
            summary = None
    if control_result.returncode != 0:
        case_count = summary.get("cases") if summary is not None else None
        failures = summary.get("failure_count") if summary is not None else None
        raw_ids = summary.get("failure_test_ids") if summary is not None else None
        safe_ids: list[str] = []
        if isinstance(raw_ids, list):
            for identifier in raw_ids[:5]:
                if (type(identifier) is str and
                        re.fullmatch(r"[A-Za-z0-9_.]{1,160}", identifier)):
                    redacted = private_paths.redact(identifier)
                    safe_ids.append(redacted if redacted == identifier else "unidentified-test")
                else:
                    safe_ids.append("unidentified-test")
        cases_label = str(case_count) if type(case_count) is int and case_count >= 0 else "unknown"
        failures_label = str(failures) if type(failures) is int and failures >= 0 else "unknown"
        tests_label = ",".join(safe_ids) if safe_ids else "unavailable"
        truncated = (summary.get("failure_test_ids_truncated") is True
                     if summary is not None else False)
        raise ValueError(
            f"public-content control suite failed (returncode={control_result.returncode}; "
            f"cases={cases_label}; failures={failures_label}; test_ids={tests_label}; "
            f"test_ids_truncated={str(truncated).lower()})"
        )
    cases = summary.get("cases") if summary is not None else None
    assertions = summary.get("assertions") if summary is not None else None
    if (summary is None or summary.get("outcome") != "pass"
            or type(cases) is not int or cases <= 0
            or type(assertions) is not int or assertions <= 0):
        raise ValueError("public-content controls omitted positive case or assertion counts")
    return cases, assertions


def produce_public_content(root: Path, *, source_revision: str,
                           report_path: Path, output_path: Path) -> dict[str, Any]:
    """Run public-content controls and bind their counts to the exact source scan."""
    from sdk_evidence import canonical_bytes, load_canonical_json, sha256_bytes

    root = root.resolve()
    if not _is_commit_sha(source_revision):
        raise ValueError("public-content event revision is not a full commit SHA")

    def git(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=root, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode != 0:
            raise ValueError("public-content source identity is unavailable")
        return result.stdout.strip()

    if git("rev-parse", "HEAD") != source_revision:
        raise ValueError("public-content checkout does not match the workflow event SHA")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("public-content checkout is not a clean immutable source tree")
    control_cases, assertion_count = public_content_control_counts(root)
    scan_env = dict(os.environ)
    scan_env["PYTHONDONTWRITEBYTECODE"] = "1"

    report_path = report_path if report_path.is_absolute() else root / report_path
    output_path = output_path if output_path.is_absolute() else root / output_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    scan_result = subprocess.run(
        [sys.executable, "tools/public_content.py", "--root", str(root),
         "--history-revision=--all", "--json", str(report_path)], cwd=root,
        env=scan_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=300, check=False)
    if scan_result.returncode != 0:
        raise ValueError("public-content source/history scan failed")
    report_bytes = report_path.read_bytes()
    report = load_canonical_json(report_bytes, label="public-content scan artifact")
    if (not isinstance(report, dict) or report.get("schema") != 1
            or report.get("outcome") != "pass" or report.get("findings") != []
            or report.get("detector_negative_only") is not True):
        raise ValueError("public-content scanner artifact is not a passing detector-only report")
    counts = report.get("counts")
    coverage = report.get("coverage")
    if not isinstance(counts, dict) or not isinstance(coverage, dict):
        raise ValueError("public-content scanner artifact omitted counts or coverage")
    scanned_files = 0
    for category in ("source", "history", "logs", "archives"):
        row = counts.get(category)
        files = row.get("files") if isinstance(row, dict) else None
        if not isinstance(files, int) or isinstance(files, bool) or files < 0:
            raise ValueError("public-content scanner emitted a malformed category count")
        scanned_files += files
    if (scanned_files <= 0 or counts["source"]["files"] <= 0 or counts["history"]["files"] <= 0
            or coverage.get("history_mode") != "all reachable refs"
            or coverage.get("history_revision") != "--all"):
        raise ValueError("public-content scanner omitted the required history/count evidence")
    if git("rev-parse", "HEAD") != source_revision or git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("public-content source changed while evidence was collected")
    receipt = {
        "schema_version": 1, "suite": "public-content", "outcome": "pass",
        "source_revision": source_revision, "working_tree_dirty": False,
        "lane_execution_count": 1, "control_cases": control_cases,
        "assertion_count": assertion_count,
        "assertion_count_basis": "unittest.TestCase assertion/fail method calls",
        "scanned_files": scanned_files,
        "report_sha256": sha256_bytes(report_bytes), "coverage": coverage,
        "detector_negative_only": True,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_bytes(receipt))
    return receipt


def assemble_aggregate(results: dict[str, Any], selected: dict[str, Any],
                       matrix_dir: Path) -> dict[str, Any]:
    from sdk_evidence import (EvidenceError, build_matrix_report, canonical_bytes,
                              load_canonical_json, sha256_bytes)

    planned = set(selected.get("selected_jobs", []))
    jobs = {name: {"result": results.get(name)} for name in REQUIRED_JOBS}
    matrix_rows = []
    matrix_summary = None
    if results.get(MATRIX_JOB) == "success":
        for path in sorted(matrix_dir.glob("*.json")):
            row = load_canonical_json(path.read_bytes(), label="matrix lane receipt")
            matrix_rows.append(row)
        try:
            matrix_summary = build_matrix_report(matrix_rows)
            if matrix_summary["source_revision"] != results.get("source_revision"):
                raise EvidenceError("matrix-revision-mismatch", "matrix receipts do not bind to the tested event SHA")
            jobs[MATRIX_JOB].update(lane_count=len(matrix_rows),
                                    assertion_count=sum(row["assertions"] for row in matrix_rows))
        except EvidenceError as error:
            matrix_summary = None
            jobs[MATRIX_JOB].update(lane_count=0, assertion_count=0)
            matrix_error = error.reason
    else:
        matrix_error = "matrix job did not succeed"
    docs_receipt = results.get("public_content_receipt", {})
    docs_receipt_errors: list[str] = []
    if results.get(DOCS_JOB) == "success":
        if not isinstance(docs_receipt, dict):
            docs_receipt = {}
        if docs_receipt.get("schema_version") != 1 or isinstance(docs_receipt.get("schema_version"), bool):
            docs_receipt_errors.append("producer schema is missing or unsupported")
        if docs_receipt.get("artifact_verified") is not True:
            docs_receipt_errors.append("producer artifact or scanner digest was not verified")
        if docs_receipt.get("assertion_count_basis") != "unittest.TestCase assertion/fail method calls":
            docs_receipt_errors.append("producer assertion count basis is missing or unsupported")
        if docs_receipt.get("outcome") != "pass" or docs_receipt.get("detector_negative_only") is not True:
            docs_receipt_errors.append("producer did not report a passing detector-only scan")
        if docs_receipt.get("source_revision") != results.get("source_revision"):
            docs_receipt_errors.append("producer source revision does not match the workflow event SHA")
        if docs_receipt.get("working_tree_dirty") is not False:
            docs_receipt_errors.append("producer source tree is not recorded clean")
        for field in ("lane_count", "assertion_count", "control_cases"):
            value = docs_receipt.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                docs_receipt_errors.append(f"producer has no positive {field}")
        if (MATRIX_JOB in planned and results.get(MATRIX_JOB) == "success"
                and docs_receipt.get("matrix_logs_verified") is not True):
            docs_receipt_errors.append("successful matrix logs were not scanned and bound to the current source")
        if docs_receipt_errors:
            docs_receipt = dict(docs_receipt, lane_count=0, assertion_count=0,
                                receipt_errors=docs_receipt_errors)
        jobs[DOCS_JOB].update(lane_count=docs_receipt.get("lane_count", 0),
                               assertion_count=docs_receipt.get("assertion_count", 0))
    aggregate = validate_aggregate(jobs, planned=planned)
    aggregate["issues"].extend(
        f"public-content producer receipt invalid: {error}" for error in docs_receipt_errors)
    if results.get("classify") != "success":
        aggregate["issues"].append("path classifier did not succeed; required plan is untrusted")
        aggregate["outcome"] = "fail"
    if results.get(MATRIX_JOB) == "success" and matrix_summary is None:
        aggregate["issues"].append(f"matrix receipts failed validation: {matrix_error}")
        aggregate["outcome"] = "fail"
    if matrix_summary is not None and matrix_summary.get("outcome") != "pass":
        aggregate["issues"].append("one or more required matrix lanes are failed or untested")
        aggregate["outcome"] = "fail"
    if matrix_summary is not None:
        aggregate["matrix"] = matrix_summary
    if results.get(DOCS_JOB) == "success":
        aggregate["public_content"] = docs_receipt
    aggregate["jobs"] = {name: jobs[name] for name in sorted(jobs)}
    aggregate["source_revision"] = results.get("source_revision", "unknown")
    aggregate["receipt_sha256"] = sha256_bytes(canonical_bytes(aggregate))
    return aggregate


def prepare_workflow_inputs(output_dir: Path) -> tuple[Path, Path]:
    """Turn GitHub job outputs and redacted scan summaries into aggregate inputs."""
    from sdk_evidence import load_canonical_json, sha256_bytes

    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_planned = os.environ.get("MATRIX_PLANNED") == "true"
    content_planned = os.environ.get("CONTENT_PLANNED") == "true"
    plan_path = output_dir / "plan.json"
    results_path = output_dir / "results.json"
    plan = {"selected_jobs": sorted(
        ([MATRIX_JOB] if matrix_planned else []) + ([DOCS_JOB] if content_planned else []))}
    results = {
        "classify": os.environ.get("CLASSIFY_RESULT", "missing"),
        MATRIX_JOB: os.environ.get("MATRIX_RESULT", "missing"),
        DOCS_JOB: os.environ.get("PUBLIC_CONTENT_RESULT", "missing"),
        "source_revision": os.environ.get("SOURCE_REVISION", "unknown"),
    }
    content_dir = output_dir / "public-content"
    report_path = content_dir / "public-content.json"
    producer_path = content_dir / "public-content-receipt.json"
    receipt: dict[str, Any] = {"schema_version": 0, "outcome": "missing",
                               "lane_count": 0, "assertion_count": 0, "control_cases": 0,
                               "artifact_verified": False, "matrix_logs_verified": False}
    if report_path.is_file() and producer_path.is_file():
        try:
            report_bytes = report_path.read_bytes()
            scan = load_canonical_json(report_bytes, label="public-content scan artifact")
            producer = load_canonical_json(producer_path.read_bytes(), label="public-content producer receipt")
            if not isinstance(scan, dict) or not isinstance(producer, dict):
                raise ValueError("producer artifacts must be JSON objects")
            counts = scan.get("counts")
            if not isinstance(counts, dict):
                raise ValueError("scan counts are missing")
            scan_coverage = scan.get("coverage")
            producer_coverage = producer.get("coverage")
            if not isinstance(scan_coverage, dict) or not isinstance(producer_coverage, dict):
                raise ValueError("scan coverage is malformed")
            scan_count = 0
            for category in ("source", "history", "logs", "archives"):
                row = counts.get(category)
                files = row.get("files") if isinstance(row, dict) else None
                if not isinstance(files, int) or isinstance(files, bool) or files < 0:
                    raise ValueError("scan category file count is malformed")
                scan_count += files
            if counts["source"]["files"] <= 0 or counts["history"]["files"] <= 0:
                raise ValueError("scan source or history count is empty")
            valid_producer = (
                producer.get("schema_version") == 1
                and not isinstance(producer.get("schema_version"), bool)
                and producer.get("suite") == "public-content"
                and producer.get("outcome") == "pass"
                and producer.get("source_revision") == results["source_revision"]
                and producer.get("working_tree_dirty") is False
                and producer.get("lane_execution_count") == 1
                and not isinstance(producer.get("lane_execution_count"), bool)
                and isinstance(producer.get("control_cases"), int)
                and not isinstance(producer.get("control_cases"), bool)
                and producer.get("control_cases", 0) > 0
                and producer.get("scanned_files") == scan_count
                and isinstance(producer.get("scanned_files"), int)
                and not isinstance(producer.get("scanned_files"), bool)
                and producer.get("scanned_files", 0) > 0
                and isinstance(producer.get("assertion_count"), int)
                and not isinstance(producer.get("assertion_count"), bool)
                and producer.get("assertion_count", 0) > 0
                and producer.get("assertion_count_basis") ==
                    "unittest.TestCase assertion/fail method calls"
                and producer.get("report_sha256") == sha256_bytes(report_bytes)
                and producer_coverage == scan_coverage
                and producer.get("detector_negative_only") is True
                and scan.get("schema") == 1
                and not isinstance(scan.get("schema"), bool)
                and scan.get("outcome") == "pass"
                and scan.get("findings") == []
                and scan.get("detector_negative_only") is True
                and scan_coverage.get("history_mode") == "all reachable refs"
                and scan_coverage.get("history_revision") == "--all"
            )
            if valid_producer:
                receipt = {
                    "schema_version": 1, "suite": "public-content",
                    "outcome": producer["outcome"], "source_revision": producer["source_revision"],
                    "working_tree_dirty": producer["working_tree_dirty"],
                    "lane_count": producer["lane_execution_count"],
                    "assertion_count": producer["assertion_count"],
                    "assertion_count_basis": producer["assertion_count_basis"],
                    "control_cases": producer["control_cases"],
                    "scanned_files": producer["scanned_files"],
                    "report_sha256": producer["report_sha256"],
                    "coverage": producer["coverage"],
                    "detector_negative_only": producer["detector_negative_only"],
                    "artifact_verified": True, "matrix_logs_verified": False,
                }
        except (OSError, ValueError, TypeError):
            pass

    if results[MATRIX_JOB] == "success":
        matrix_logs_path = content_dir / "matrix-logs.json"
        try:
            matrix_logs = load_canonical_json(matrix_logs_path.read_bytes(), label="matrix log scan")
            coverage = matrix_logs.get("coverage", {}) if isinstance(matrix_logs, dict) else None
            log_count = coverage.get("logs_supplied") if isinstance(coverage, dict) else None
            logs_verified = (
                isinstance(coverage, dict) and isinstance(matrix_logs, dict)
                and matrix_logs.get("schema") == 1
                and not isinstance(matrix_logs.get("schema"), bool)
                and matrix_logs.get("outcome") == "pass"
                and matrix_logs.get("findings") == []
                and matrix_logs.get("detector_negative_only") is True
                and isinstance(log_count, int) and not isinstance(log_count, bool) and log_count > 0
                and coverage.get("history_revision") == results["source_revision"]
                and coverage.get("history_mode") == "selected revision"
            )
            receipt["matrix_logs_verified"] = bool(logs_verified)
            receipt["matrix_log_coverage"] = coverage if logs_verified else {}
        except (OSError, ValueError, TypeError):
            receipt["matrix_logs_verified"] = False
    results["public_content_receipt"] = receipt
    plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
    results_path.write_text(json.dumps(results, sort_keys=True), encoding="utf-8")
    return plan_path, results_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    classify = commands.add_parser("classify")
    classify.add_argument("--paths-json", type=Path)
    classify.add_argument("--diff-error", action="store_true")
    classify.add_argument("--output", type=Path, required=True)
    aggregate = commands.add_parser("aggregate")
    aggregate.add_argument("--results", type=Path, required=True)
    aggregate.add_argument("--plan", type=Path, required=True)
    aggregate.add_argument("--matrix-dir", type=Path, required=True)
    aggregate.add_argument("--output", type=Path, required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--output-dir", type=Path, required=True)
    content_producer = commands.add_parser("produce-public-content")
    content_producer.add_argument("--root", type=Path, required=True)
    content_producer.add_argument("--source-revision", required=True)
    content_producer.add_argument("--report-output", type=Path, required=True)
    content_producer.add_argument("--output", type=Path, required=True)
    readiness = commands.add_parser("merge-readiness")
    readiness.add_argument("--receipt", type=Path, required=True)
    readiness.add_argument("--head-sha", required=True)
    readiness.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "classify":
            paths = json.loads(args.paths_json.read_text()) if args.paths_json else None
            report = classify_diff(paths, diff_error=args.diff_error)
        elif args.command == "prepare":
            plan_path, results_path = prepare_workflow_inputs(args.output_dir)
            report = {"outcome": "pass", "plan": str(plan_path.name), "results": str(results_path.name)}
        elif args.command == "merge-readiness":
            report = validate_merge_readiness(json.loads(args.receipt.read_text()),
                                              proposed_sha=args.head_sha)
        elif args.command == "produce-public-content":
            report = produce_public_content(args.root, source_revision=args.source_revision,
                                            report_path=args.report_output, output_path=args.output)
        else:
            report = assemble_aggregate(json.loads(args.results.read_text()),
                                        json.loads(args.plan.read_text()), args.matrix_dir)
        from sdk_evidence import canonical_bytes, scan_public_value
        scan_public_value(report)
        output = canonical_bytes(report)
        output_path = getattr(args, "output", None)
        if args.command == "produce-public-content":
            output_path = None
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(output)
        print(output.decode(), end="")
        return 0 if report.get("outcome") == "pass" else 1
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"outcome": "fail", "reason": type(error).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
