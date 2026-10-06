#!/usr/bin/env python3
"""Fail-closed controls for CI path classification and required aggregation."""

from __future__ import annotations

import sys
import tempfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "workflow"))
import ci_policy as policy  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
import sdk_evidence as evidence  # noqa: E402


def expect(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> int:
    # Merge readiness must bind both the required aggregate and the separate
    # GSD review to the exact proposed PR head.
    proposed_sha = "a" * 40
    receipt = {
        "schema_version": 1,
        "pr_head_sha": proposed_sha,
        "required_aggregate": {
            "sha": proposed_sha, "outcome": "pass", "lane_count": 6,
            "assertion_count": 120,
        },
        "independent_review": {
            "sha": proposed_sha, "review_type": "gsd-code-review", "outcome": "pass",
            "findings": [{"id": "R-1", "status": "dispositioned",
                          "disposition": "not-applicable", "evidence": "review note"}],
        },
    }
    expect(policy.validate_merge_readiness(receipt, proposed_sha=proposed_sha)["outcome"] == "pass",
           "complete exact-SHA aggregate and independent review must pass")
    for stale_field in ("pr_head_sha", "required_aggregate", "independent_review"):
        stale = json.loads(json.dumps(receipt))
        if stale_field == "required_aggregate":
            stale[stale_field]["sha"] = "b" * 40
        elif stale_field == "independent_review":
            stale[stale_field]["sha"] = "b" * 40
        else:
            stale[stale_field] = "b" * 40
        expect(policy.validate_merge_readiness(stale, proposed_sha=proposed_sha)["outcome"] == "fail",
               f"stale {stale_field} must reject merge readiness")
    open_finding = json.loads(json.dumps(receipt))
    open_finding["independent_review"]["findings"][0]["status"] = "open"
    expect(policy.validate_merge_readiness(open_finding, proposed_sha=proposed_sha)["outcome"] == "fail",
           "open review finding must reject merge readiness")
    unsupported_disposition = json.loads(json.dumps(receipt))
    unsupported_disposition["independent_review"]["findings"][0]["evidence"] = ""
    expect(policy.validate_merge_readiness(unsupported_disposition, proposed_sha=proposed_sha)["outcome"] == "fail",
           "finding disposition without evidence must reject merge readiness")
    resolved_without_evidence = json.loads(json.dumps(receipt))
    resolved_without_evidence["independent_review"]["findings"][0] = {"id": "R-1", "status": "resolved"}
    expect(policy.validate_merge_readiness(resolved_without_evidence, proposed_sha=proposed_sha)["outcome"] == "fail",
           "resolved finding without resolution evidence must reject merge readiness")
    other_review = json.loads(json.dumps(receipt))
    other_review["independent_review"]["review_type"] = "security-review"
    expect(policy.validate_merge_readiness(other_review, proposed_sha=proposed_sha)["outcome"] == "fail",
           "security review must not substitute for independent GSD code review")
    zero_lane = json.loads(json.dumps(receipt))
    zero_lane["required_aggregate"]["lane_count"] = 0
    expect(policy.validate_merge_readiness(zero_lane, proposed_sha=proposed_sha)["outcome"] == "fail",
           "zero-count aggregate must reject merge readiness")

    expect(policy.classify_paths(["docs/testing.md"]) == {policy.DOCS_JOB}, "docs-only change must retain the content gate")
    expect(policy.classify_paths(["src/instance.c"]) == set(policy.REQUIRED_JOBS), "source change must run every required lane")
    expect(policy.classify_paths(["new/unknown.file"]) == set(policy.REQUIRED_JOBS), "unknown path must fail open to every lane")
    expect(policy.classify_paths(None) == set(policy.REQUIRED_JOBS), "missing diff must fail open")
    expect(policy.classify_paths([], diff_error=True) == set(policy.REQUIRED_JOBS), "diff failure must fail open")

    jobs = {name: {"result": "success", "lane_count": 1, "assertion_count": 12}
            for name in policy.REQUIRED_JOBS}
    expect(policy.validate_aggregate(jobs, planned=set(policy.REQUIRED_JOBS))["outcome"] == "pass",
           "complete successful positive lanes must pass")
    expect(policy.validate_aggregate(jobs, planned={policy.MATRIX_JOB})["outcome"] == "fail",
           "matrix changes must not omit the independent public-content gate")
    for result in ("missing", "failure", "cancelled", "skipped"):
        altered = {key: dict(value) for key, value in jobs.items()}
        altered[policy.MATRIX_JOB]["result"] = result
        expect(policy.validate_aggregate(altered, planned=set(policy.REQUIRED_JOBS))["outcome"] == "fail",
               f"{result} matrix job must fail aggregate")
    altered = {key: dict(value) for key, value in jobs.items()}
    altered[policy.MATRIX_JOB]["lane_count"] = 0
    expect(policy.validate_aggregate(altered, planned=set(policy.REQUIRED_JOBS))["outcome"] == "fail",
           "empty required matrix must fail")
    altered = {key: dict(value) for key, value in jobs.items()}
    altered[policy.MATRIX_JOB]["result"] = "skipped"
    altered[policy.DOCS_JOB]["result"] = "success"
    altered[policy.DOCS_JOB]["assertion_count"] = 5
    expect(policy.validate_aggregate(altered, planned={policy.DOCS_JOB})["outcome"] == "pass",
           "documented selective skip may pass only with docs evidence")
    altered[policy.DOCS_JOB]["assertion_count"] = 0
    expect(policy.validate_aggregate(altered, planned={policy.DOCS_JOB})["outcome"] == "fail",
           "docs-only skip without positive evidence must fail")
    expect(policy.validate_aggregate(jobs, planned=set(policy.REQUIRED_JOBS) - {policy.MATRIX_JOB})["outcome"] == "fail",
           "unplanned matrix success must not be silently accepted")
    altered = {key: dict(value) for key, value in jobs.items()}
    altered[policy.DOCS_JOB]["result"] = "cancelled"
    expect(policy.validate_aggregate(altered, planned=set(policy.REQUIRED_JOBS))["outcome"] == "fail",
           "cancelled public content check must fail")

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for required in (
        "pull_request:", "push:", "permissions:\n  contents: read", "max-parallel: 2",
        "if: always()", "linux-clang", "linux-gcc", "macos-appleclang", "windows-msvc",
        "linux-clang-sanitizer", "linux-clang-fuzz",
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
    ):
        expect(required in workflow, f"workflow omitted required contract: {required}")
    expect("paths:" not in workflow, "workflow-level path filters can omit the required aggregate")
    expect("pull_request_target" not in workflow and "secrets." not in workflow,
           "untrusted PR workflow must not use privileged events or secrets")
    expect("contents: write" not in workflow, "PR workflow token must remain read-only")
    expect('"${{ matrix.' not in workflow,
           "matrix values must enter runner shells through environment variables, not inline interpolation")

    releasing = (ROOT / "docs/releasing.md").read_text(encoding="utf-8")
    for required in (
        "strict up-to-date branches", "independent GSD code review", "Any head change",
        "native auto-merge", "measured merge contention", "security-review threat dispositions",
        "This local validator does not fetch GitHub receipts or grant merge",
    ):
        expect(required in releasing, f"release policy documentation omitted: {required}")
    testing = (ROOT / "docs/testing.md").read_text(encoding="utf-8")
    for required in (
        "Darwin-26", "Apple SDK 26.5", "1,440 assertions", "9.374 seconds",
        "runner-minutes", "unknown; no hosted receipt", "rights status unknown",
    ):
        expect(required in testing, f"qualification documentation omitted: {required}")

    revision = "a" * 40
    with tempfile.TemporaryDirectory(prefix="ci-matrix-test-") as temp:
        matrix_dir = Path(temp)
        for lane in evidence.REQUIRED_MATRIX_LANES:
            os_name, compiler_ids, architectures = evidence.MATRIX_LANE_IDENTITY[lane]
            row = {
                "lane": lane, "compiler": {"id": next(iter(compiler_ids)), "version": "18.1"},
                "sdk": {"name": "test-sdk", "version": "1.0"},
                "os_image": {"Linux": "ubuntu-test", "Darwin": "macos-test", "Windows": "windows-test"}[os_name],
                "os": os_name, "architecture": next(iter(architectures)), "configuration": "Debug",
                "source_revision": revision, "working_tree_dirty": False,
                "build_identity": {"cmake": "3.31", "generator": "Ninja 1.13", "fixture_sha256": "b" * 64},
                "outcome": "pass", "assertions": 3, "duration_seconds": 6.0,
                "cold_build_seconds": 1.0, "runner_id": f"runner-{lane}", "runner_minutes": 0.1,
            }
            (matrix_dir / f"{lane}.json").write_bytes(evidence.canonical_bytes(row))
        planned = {"selected_jobs": sorted(policy.REQUIRED_JOBS)}
        results = {"classify": "success", "matrix": "success", "public-content": "success",
                   "source_revision": revision,
                   "public_content_receipt": {"lane_count": 1, "assertion_count": 10,
                                               "outcome": "pass", "detector_negative_only": True,
                                               "coverage": {"logs_supplied": 6}}}
        aggregate = policy.assemble_aggregate(results, planned, matrix_dir)
        expect(aggregate["outcome"] == "pass", "full current-SHA matrix with positive content scan must pass")
        stale = dict(results, source_revision="c" * 40)
        expect(policy.assemble_aggregate(stale, planned, matrix_dir)["outcome"] == "fail",
               "matrix evidence from a different current SHA must fail")
        docs_plan = {"selected_jobs": [policy.DOCS_JOB]}
        docs_only = dict(results, matrix="skipped")
        docs_only.pop("public_content_receipt")
        docs_only["public_content_receipt"] = {"lane_count": 1, "assertion_count": 4,
                                               "outcome": "pass", "detector_negative_only": True}
        expect(policy.assemble_aggregate(docs_only, docs_plan, matrix_dir)["outcome"] == "pass",
               "documented classifier skip must pass only with positive docs evidence")
    print("PASS: conservative CI classification and aggregate controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
