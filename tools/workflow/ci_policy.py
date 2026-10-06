"""Conservative changed-path classification and required CI aggregation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MATRIX_JOB = "matrix"
DOCS_JOB = "public-content"
AGGREGATE_JOB = "ci-policy"
REQUIRED_JOBS = frozenset((MATRIX_JOB, DOCS_JOB))
_COMMIT_SHA_LENGTH = 40


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
    docs_only = all(
        path.startswith("docs/") or path in {"README.md", "LICENSE"}
        for path in rows
    )
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
    if results.get(DOCS_JOB) == "success":
        if docs_receipt.get("outcome") != "pass" or docs_receipt.get("detector_negative_only") is not True:
            docs_receipt = dict(docs_receipt, lane_count=0, assertion_count=0)
        if MATRIX_JOB in planned and docs_receipt.get("coverage", {}).get("logs_supplied", 0) <= 0:
            docs_receipt = dict(docs_receipt, lane_count=0, assertion_count=0)
        docs_assertions = docs_receipt.get("assertion_count", 0)
        jobs[DOCS_JOB].update(lane_count=docs_receipt.get("lane_count", 0),
                               assertion_count=docs_assertions)
    aggregate = validate_aggregate(jobs, planned=planned)
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
    matrix_result = results[MATRIX_JOB]
    content_file = output_dir / "public-content" / (
        "matrix-logs.json" if matrix_result == "success" else "public-content.json")
    scan = {}
    if content_file.is_file():
        scan = json.loads(content_file.read_text(encoding="utf-8"))
    counts = scan.get("counts", {})
    scan_count = sum(value.get("files", 0) for value in counts.values()
                     if isinstance(value, dict) and isinstance(value.get("files", 0), int))
    results["public_content_receipt"] = {
        "lane_count": 1 if scan.get("outcome") == "pass" else 0,
        "assertion_count": scan_count if scan.get("outcome") == "pass" else 0,
        "outcome": scan.get("outcome", "missing"),
        "coverage": scan.get("coverage"),
        "detector_negative_only": scan.get("detector_negative_only", False),
    }
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
        else:
            report = assemble_aggregate(json.loads(args.results.read_text()),
                                        json.loads(args.plan.read_text()), args.matrix_dir)
        from sdk_evidence import canonical_bytes, scan_public_value
        scan_public_value(report)
        output = canonical_bytes(report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(output)
        print(output.decode(), end="")
        return 0 if report.get("outcome") == "pass" else 1
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"outcome": "fail", "reason": type(error).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
