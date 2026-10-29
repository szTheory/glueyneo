"""Conservative changed-path classification and required CI aggregation."""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import private_paths  # noqa: E402
import public_content  # noqa: E402

MATRIX_JOB = "matrix"
DOCS_JOB = "public-content"
AGGREGATE_JOB = "ci-policy"
REQUIRED_JOBS = frozenset((MATRIX_JOB, DOCS_JOB))
_COMMIT_SHA_LENGTH = 40
_DOCUMENTATION_SUFFIXES = frozenset({".gif", ".jpeg", ".jpg", ".md", ".png", ".rst", ".svg", ".txt", ".webp"})
_PUBLIC_CONTROL_SUMMARY_KEYS = frozenset({
    "schema_version", "assertions", "cases", "failure_count",
    "expected_failure_count", "skipped_count", "unexpected_success_count",
    "nonpassing_test_ids", "nonpassing_test_ids_truncated", "outcome",
})
_MAX_PUBLIC_CONTROL_CASES = 1_000_000
_MAX_PUBLIC_CONTROL_ASSERTIONS = 10_000_000
_MAX_PUBLIC_CONTROL_FAILURES = 1_000_000
_MAX_PUBLIC_CONTROL_EXPECTED_FAILURES = 1_000_000
_MAX_PUBLIC_CONTROL_SKIPS = 1_000_000
_MAX_PUBLIC_CONTROL_UNEXPECTED_SUCCESSES = 1_000_000
_MAX_PUBLIC_CONTROL_FAILURE_IDS = 5
_MAX_PUBLIC_CONTROL_FAILURE_ID_LENGTH = 96
_MAX_PUBLIC_CONTROL_DIAGNOSTIC_BYTES = 1024
_PUBLIC_CONTROL_FAILURE_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,95}")


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


def _valid_public_content_summary(summary: Any) -> bool:
    if type(summary) is not dict or frozenset(summary) != _PUBLIC_CONTROL_SUMMARY_KEYS:
        return False
    if (type(summary.get("schema_version")) is not int or summary["schema_version"] != 1
            or type(summary.get("cases")) is not int
            or not 0 < summary["cases"] <= _MAX_PUBLIC_CONTROL_CASES
            or type(summary.get("assertions")) is not int
            or not 0 < summary["assertions"] <= _MAX_PUBLIC_CONTROL_ASSERTIONS
            or type(summary.get("failure_count")) is not int
            or not 0 <= summary["failure_count"] <= _MAX_PUBLIC_CONTROL_FAILURES
            or type(summary.get("expected_failure_count")) is not int
            or not 0 <= summary["expected_failure_count"] <= _MAX_PUBLIC_CONTROL_EXPECTED_FAILURES
            or type(summary.get("skipped_count")) is not int
            or not 0 <= summary["skipped_count"] <= _MAX_PUBLIC_CONTROL_SKIPS
            or type(summary.get("unexpected_success_count")) is not int
            or not 0 <= summary["unexpected_success_count"] <= _MAX_PUBLIC_CONTROL_UNEXPECTED_SUCCESSES
            or type(summary.get("nonpassing_test_ids")) is not list
            or len(summary["nonpassing_test_ids"]) > _MAX_PUBLIC_CONTROL_FAILURE_IDS
            or type(summary.get("nonpassing_test_ids_truncated")) is not bool
            or type(summary.get("outcome")) is not str
            or summary["outcome"] not in {"pass", "fail"}):
        return False
    identifiers = summary["nonpassing_test_ids"]
    if any(type(identifier) is not str for identifier in identifiers):
        return False
    if identifiers != sorted(set(identifiers)):
        return False
    if any(not _PUBLIC_CONTROL_FAILURE_ID.fullmatch(identifier)
           or private_paths.redact(identifier) != identifier
           or public_content.scan_bytes(
               identifier.encode("utf-8"), "ci-policy-failure-test-id")["findings"]
           for identifier in identifiers):
        return False
    if summary["outcome"] == "pass":
        return (summary["failure_count"] == 0
                and summary["expected_failure_count"] == 0
                and summary["skipped_count"] == 0
                and summary["unexpected_success_count"] == 0
                and not identifiers
                and summary["nonpassing_test_ids_truncated"] is False)
    if not (summary["failure_count"] or summary["expected_failure_count"]
            or summary["skipped_count"] or summary["unexpected_success_count"]):
        return False
    return bool(identifiers) and (len(identifiers) == _MAX_PUBLIC_CONTROL_FAILURE_IDS
                                  or not summary["nonpassing_test_ids_truncated"])


def _bounded_public_content_diagnostic(message: str) -> str:
    redacted = private_paths.redact(message)
    if (len(redacted.encode("utf-8")) > _MAX_PUBLIC_CONTROL_DIAGNOSTIC_BYTES
            or public_content.scan_bytes(
                redacted.encode("utf-8"), "ci-policy-failure-diagnostic")["findings"]):
        return "public-content control suite failed (details=redacted)"
    return redacted


def _host_account_class() -> str:
    """Classify the host's account-root convention without reporting its path."""
    home_parts = Path(os.path.expanduser("~")).parts
    if len(home_parts) > 1 and home_parts[1] == "Users":
        return "mac"
    if len(home_parts) > 1 and home_parts[1] == "home":
        return "linux"
    return "other"


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate result field")
        result[key] = value
    return result


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
expected_failures = result.expectedFailures
skipped_tests = result.skipped
unexpected_successes = result.unexpectedSuccesses
nonpassing_tests = ([test for test, _detail in failures]
                    + [test for test, _detail in expected_failures]
                    + [test for test, _detail in skipped_tests]
                    + list(unexpected_successes))
test_ids = []
for test in nonpassing_tests:
    try:
        source_test = getattr(test, "test_case", test)
        identifier = getattr(source_test, "_testMethodName", None)
    except Exception:
        source_test = None
        identifier = ""
    source_method = None
    if isinstance(source_test, unittest.TestCase) and isinstance(identifier, str):
        for test_class in type(source_test).__mro__:
            if identifier in test_class.__dict__:
                source_method = test_class.__dict__[identifier]
                break
    if (type(identifier) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,95}", identifier)
            and callable(source_method)):
        test_ids.append(identifier)
    else:
        test_ids.append("unidentified-test")
summary = {
    "schema_version": 1,
    "assertions": counts["assertions"],
    "cases": result.testsRun,
    "failure_count": len(failures),
    "expected_failure_count": len(expected_failures),
    "skipped_count": len(skipped_tests),
    "unexpected_success_count": len(unexpected_successes),
    "nonpassing_test_ids": sorted(set(test_ids))[:5],
    "nonpassing_test_ids_truncated": len(set(test_ids)) > 5,
    "outcome": "pass" if not nonpassing_tests else "fail",
}
print("PUBLIC_CONTENT_RESULT=" + json.dumps(summary, sort_keys=True, separators=(",", ":")))
raise SystemExit(0 if summary["outcome"] == "pass" else 1)
'''
    child_env = dict(os.environ)
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    control_result = subprocess.run([sys.executable, "-c", counted_runner], cwd=root.resolve(),
                                    env=child_env, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=60, check=False)
    result_prefix = "PUBLIC_CONTENT_RESULT="
    result_lines = []
    for line in io.StringIO(control_result.stdout or ""):
        if line.startswith(result_prefix):
            result_lines.append(line[len(result_prefix):])
        if len(result_lines) > 1:
            break
    summary: dict[str, Any] | None = None
    if len(result_lines) == 1 and 0 < len(result_lines[0].encode("utf-8")) <= 4096:
        try:
            candidate = json.loads(result_lines[0], object_pairs_hook=_reject_duplicate_json_keys)
            if isinstance(candidate, dict):
                summary = candidate
        except (ValueError, TypeError):
            summary = None
    if control_result.returncode != 0:
        case_count = summary.get("cases") if summary is not None else None
        failures = summary.get("failure_count") if summary is not None else None
        expected_failures = (summary.get("expected_failure_count")
                             if summary is not None else None)
        skipped_count = summary.get("skipped_count") if summary is not None else None
        unexpected_successes = (summary.get("unexpected_success_count")
                                if summary is not None else None)
        raw_ids = summary.get("nonpassing_test_ids") if summary is not None else None
        safe_ids: list[str] = []
        if isinstance(raw_ids, list):
            for identifier in raw_ids[:_MAX_PUBLIC_CONTROL_FAILURE_IDS]:
                if (type(identifier) is str and
                        _PUBLIC_CONTROL_FAILURE_ID.fullmatch(identifier)):
                    redacted = private_paths.redact(identifier)
                    findings = public_content.scan_bytes(
                        redacted.encode("utf-8"), "ci-policy-failure-test-id")["findings"]
                    safe_ids.append(redacted if redacted == identifier and not findings
                                    else "unidentified-test")
                else:
                    safe_ids.append("unidentified-test")
        def count_label(value: Any, maximum: int) -> str:
            return str(value) if type(value) is int and 0 <= value <= maximum else "unknown"

        cases_label = count_label(case_count, _MAX_PUBLIC_CONTROL_CASES)
        failures_label = count_label(failures, _MAX_PUBLIC_CONTROL_FAILURES)
        expected_failures_label = count_label(
            expected_failures, _MAX_PUBLIC_CONTROL_EXPECTED_FAILURES)
        skipped_label = count_label(skipped_count, _MAX_PUBLIC_CONTROL_SKIPS)
        unexpected_successes_label = count_label(
            unexpected_successes, _MAX_PUBLIC_CONTROL_UNEXPECTED_SUCCESSES)
        tests_label = ",".join(safe_ids) if safe_ids else "unavailable"
        truncated = (str(summary["nonpassing_test_ids_truncated"]).lower()
                     if summary is not None and
                     type(summary.get("nonpassing_test_ids_truncated")) is bool else "unknown")
        records = "2+" if len(result_lines) > 1 else str(len(result_lines))
        returncode = control_result.returncode
        returncode_label = (str(returncode) if type(returncode) is int
                            and -255 <= returncode <= 255 else "unknown")
        message = (
            f"public-content control suite failed (returncode={returncode_label}; "
            f"result_records={records}; cases={cases_label}; failures={failures_label}; "
            f"expected_failures={expected_failures_label}; skipped={skipped_label}; "
            f"unexpected_successes={unexpected_successes_label}; "
            f"nonpassing_test_ids={tests_label}; test_ids_truncated={truncated}; "
            f"account_class={_host_account_class()})"
        )
        raise ValueError(_bounded_public_content_diagnostic(message))
    cases = summary.get("cases") if summary is not None else None
    assertions = summary.get("assertions") if summary is not None else None
    if (len(result_lines) != 1 or not _valid_public_content_summary(summary)
            or summary.get("outcome") != "pass"):
        raise ValueError("public-content controls omitted one valid, positive, failure-free result")
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
