#!/usr/bin/env python3
"""Protected delivery evidence contract and fail-closed receipt checks."""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import release_manifest
WORKFLOW = ROOT / ".github/workflows/release.yml"
REPOSITORY = "szTheory/glueyneo"
PROFILES = ("linux-x86_64", "macos-arm64", "windows-x86_64")
ARCHIVES = {
    "glueyneo-source": "source",
    **{f"glueyneo-sdk-{profile}": profile for profile in PROFILES},
}
CASE_IDS = (
    "downloaded-assets",
    "offline-source-build",
    "guide-command-closure",
    "static-diagnostic",
    "static-c-consumer",
    "static-continuation",
    "static-portable-persistence",
    "static-host-persistence",
    "shared-diagnostic",
    "shared-c-consumer",
    "shared-continuation",
    "shared-portable-persistence",
    "shared-host-persistence",
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class DeliveryContractError(ValueError):
    """A receipt or producer output does not prove the required delivery contract."""


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DeliveryContractError(message)


def _review_frontmatter(report: str, *, commit: str) -> dict[str, str]:
    match = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|\s*\Z)", report, re.DOTALL)
    require(match is not None, "independent code review report has no structured frontmatter")
    fields: dict[str, str] = {}
    for name in ("reviewed_commit", "status"):
        values = re.findall(rf"(?m)^{name}:\s*([^\r\n]+)\s*$", match.group(1))
        require(len(values) == 1, f"independent code review report has missing or duplicate {name}")
        fields[name] = values[0]
    require(fields["reviewed_commit"] == commit,
            "independent code review report does not name its exact reviewed commit")
    count_rows = re.findall(r"(?m)^  (critical|warning|info|total):\s*([0-9]+)\s*$", match.group(1))
    counts = dict(count_rows)
    require(len(count_rows) == 4 and set(counts) == {"critical", "warning", "info", "total"},
            "independent code review report has missing or duplicate finding counts")
    require(fields["status"] == "clean" and all(int(value) == 0 for value in counts.values()),
            "independent code review report is not clean")
    return fields


def _security_report_verdict(report: str, *, commit: str) -> tuple[str, int]:
    fields: dict[str, str] = {}
    for name in ("reviewed_commit", "verdict", "threats_open"):
        values = re.findall(rf"(?m)^{name}:\s*([^\r\n]+)\s*$", report)
        require(len(values) == 1, f"independent security report has missing or duplicate {name}")
        fields[name] = values[0]
    require(fields["reviewed_commit"] == commit,
            "independent security report does not name its exact reviewed commit")
    require(fields["verdict"] in {"SECURED", "OPEN_THREATS", "ESCALATE"}
            and fields["threats_open"].isdigit(),
            "independent security report verdict is malformed")
    return fields["verdict"], int(fields["threats_open"])


def workflow_job(name: str) -> str:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(rf"\n  {re.escape(name)}:\n", workflow)
    if match is None:
        raise DeliveryContractError(f"release workflow is missing job {name}")
    following = re.search(r"\n  [a-z][\w-]*:\n", workflow[match.end():])
    end = match.end() + following.start() if following else len(workflow)
    return workflow[match.end():end]


def _asset_rows(manifest: object, *, commit: str, version: str) -> list[dict[str, object]]:
    require(isinstance(manifest, dict), "release manifest is not an object")
    require(type(manifest.get("schema_version")) is int and manifest["schema_version"] == 1,
            "release manifest schema is unsupported")
    require(manifest.get("source_commit") == commit, "release manifest source differs from intended public commit")
    require(manifest.get("version") == version and manifest.get("tag") == f"v{version}",
            "release manifest tag/version differs from Release Please identity")
    rows = manifest.get("assets")
    require(isinstance(rows, list), "release manifest assets are missing")
    names: list[str] = []
    for row in rows:
        require(isinstance(row, dict), "release manifest asset row is malformed")
        name, size, sha = row.get("name"), row.get("size"), row.get("sha256")
        require(isinstance(name, str) and name and name not in names, "release manifest asset names are duplicate or malformed")
        require(type(size) is int and size > 0, "release manifest asset size is not positive")
        require(isinstance(sha, str) and DIGEST_RE.fullmatch(sha) is not None,
                "release manifest asset digest is malformed")
        names.append(name)
    expected = {
        f"glueyneo-source-{version}.tar.gz",
        *(f"glueyneo-sdk-{version}-{profile}.tar.gz" for profile in PROFILES),
    }
    require(set(names) == expected, "release manifest is missing or adds a required distributable")
    return rows


def _validate_consumer_result(result: object, *, commit: str, version: str,
                              profile: str, source_sha: str, sdk_sha: str) -> None:
    require(isinstance(result, dict), "consumer result is not an object")
    require(result.get("outcome") == "pass" and result.get("source_commit") == commit,
            "consumer result does not pass at the intended public source")
    require(result.get("version") == version and result.get("platform") == profile,
            "consumer result source version or named profile differs")
    require(result.get("downloaded_byte_verification") == "pass"
            and result.get("source_archive_sha256") == source_sha
            and result.get("sdk_archive_sha256") == sdk_sha,
            "consumer result is not bound to the exact downloaded source and SDK bytes")
    require(result.get("offline_source_rebuild") == "pass"
            and result.get("guide_command_closure") == "pass",
            "consumer result omits offline source or documented-command qualification")
    require(result.get("variants") == ["static", "shared"], "consumer result omits static/shared consumers")
    cases = result.get("cases")
    require(isinstance(cases, list), "consumer result case rows are missing")
    by_id: dict[str, object] = {}
    for row in cases:
        require(isinstance(row, dict) and isinstance(row.get("id"), str), "consumer case row is malformed")
        case_id = row["id"]
        require(case_id not in by_id, "consumer result duplicates a case row")
        by_id[case_id] = row
    require(set(by_id) == set(CASE_IDS), "consumer result case membership is incomplete or unexpected")
    for case_id in CASE_IDS:
        status = by_id[case_id].get("status")
        if case_id.endswith("host-persistence") and profile != "macos-arm64":
            require(status == "unsupported", "non-Darwin host persistence must remain explicitly unsupported")
        else:
            require(status == "pass", f"consumer case did not pass: {case_id}")
    toolchain = result.get("toolchain")
    require(isinstance(toolchain, dict) and isinstance(toolchain.get("cmake_version"), str)
            and toolchain.get("configuration") == "Release"
            and isinstance(toolchain.get("source_compiler_id"), str) and toolchain["source_compiler_id"]
            and isinstance(toolchain.get("source_compiler_version"), str) and toolchain["source_compiler_version"],
            "consumer toolchain/configuration evidence is missing")
    builds = toolchain.get("builds")
    require(isinstance(builds, list) and [row.get("linkage") for row in builds if isinstance(row, dict)] == ["static", "shared"],
            "consumer toolchain does not identify both linkage profiles")
    for row in builds:
        require(isinstance(row.get("compiler_id"), str) and row["compiler_id"]
                and isinstance(row.get("compiler_version"), str) and row["compiler_version"],
                "consumer toolchain compiler identity is incomplete")


def _validate_platform_evidence(item: object, *, source: dict[str, object], release: dict[str, object],
                                distribution: str, profile: str) -> None:
    require(isinstance(item, dict), "platform evidence is not an object")
    payload = {key: value for key, value in item.items() if key != "evidence_sha256"}
    require(item.get("evidence_sha256") == digest(payload), "platform evidence digest does not match its producer record")
    require(item.get("distribution") == distribution and item.get("platform") == profile,
            "platform evidence has the wrong distribution or profile")
    require(item.get("source_commit") == source["commit"] and item.get("version") == source["version"],
            "platform evidence is stale or uses a planning identity")
    require(item.get("workflow_commit") == source["workflow_commit"],
            "platform evidence is not bound to the trusted workflow source commit")
    manifest = item.get("manifest")
    require(isinstance(manifest, dict) and manifest == release["manifest"],
            "platform evidence manifest differs from the published release manifest")
    require(item.get("manifest_sha256") == digest(manifest), "platform manifest producer digest is invalid")
    rows = _asset_rows(manifest, commit=str(source["commit"]), version=str(source["version"]))
    assets = item.get("downloaded_assets")
    require(isinstance(assets, list), "platform evidence omits its observed downloaded asset rows")
    expected = {row["name"]: row for row in rows}
    observed: dict[str, object] = {}
    for row in assets:
        require(isinstance(row, dict) and isinstance(row.get("name"), str), "downloaded asset evidence row is malformed")
        require(row["name"] not in observed, "downloaded asset evidence has duplicate rows")
        observed[row["name"]] = row
    require(set(observed) == set(expected), "downloaded bytes do not cover the exact manifest asset set")
    for name, expected_row in expected.items():
        require(observed[name] == expected_row, f"downloaded bytes differ from the staged manifest: {name}")
    source_name = f"glueyneo-source-{source['version']}.tar.gz"
    sdk_name = f"glueyneo-sdk-{source['version']}-{profile}.tar.gz"
    consumer = item.get("consumer_result")
    require(item.get("consumer_result_sha256") == digest(consumer), "consumer producer-output digest is invalid")
    _validate_consumer_result(consumer, commit=str(source["commit"]), version=str(source["version"]),
                              profile=profile, source_sha=str(expected[source_name]["sha256"]),
                              sdk_sha=str(expected[sdk_name]["sha256"]))
    run = item.get("run")
    require(isinstance(run, dict), "platform run identity is missing")
    run_id, attempt, job_id = run.get("run_id"), run.get("attempt"), run.get("job_id")
    require(type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0
            and type(job_id) is int and job_id > 0, "platform run/job identity is invalid")
    base = f"https://github.com/{REPOSITORY}/actions/runs/{run_id}"
    require(run.get("repository") == REPOSITORY and run.get("run_url") == base
            and run.get("job_url") == f"{base}/job/{job_id}", "platform evidence URLs are not exact GitHub producer URLs")
    expected_job = "verify-downloaded-release" if distribution == "staged" else "verify-published-release"
    require(run.get("job_name") == f"{expected_job} ({profile})",
            "platform evidence does not identify its unique named producer job")
    release_run = release.get("run")
    require(isinstance(release_run, dict) and run_id == release_run.get("run_id")
            and attempt == release_run.get("attempt"), "platform evidence belongs to a different workflow run")


def validate_receipt(receipt: object) -> dict[str, object]:
    require(isinstance(receipt, dict), "delivery receipt must be a JSON object")
    require(type(receipt.get("schema_version")) is int and receipt["schema_version"] == 1,
            "delivery receipt schema is unsupported")
    require(receipt.get("status") == "published", "receipt is not an actually published delivery")
    source = receipt.get("source")
    require(isinstance(source, dict), "public source identity is missing")
    commit, workflow_commit = source.get("commit"), source.get("workflow_commit")
    version, tag = source.get("version"), source.get("tag")
    require(isinstance(commit, str) and SHA_RE.fullmatch(commit) is not None,
            "source commit must be a full immutable public commit")
    require(isinstance(workflow_commit, str) and SHA_RE.fullmatch(workflow_commit) is not None,
            "workflow revision must be a full immutable commit")
    require(isinstance(version, str) and release_manifest.VERSION_RE.fullmatch(version) is not None
            and tag == f"v{version}", "source version must come from Release Please tag identity")
    require(source.get("repository") == REPOSITORY and source.get("public_ref") == "refs/heads/main",
            "receipt does not identify the public protected source")
    state_head = source.get("planning_state_head")
    require(isinstance(state_head, str) and SHA_RE.fullmatch(state_head) is not None and state_head != commit,
            "mutable planning state head cannot substitute for public source commit")
    require(source.get("private_history_included") is False,
            "private development history must be excluded from the public source")
    pull_request = source.get("pull_request")
    require(isinstance(pull_request, dict)
            and type(pull_request.get("number")) is int and pull_request["number"] > 0
            and pull_request.get("base_ref") == "main"
            and isinstance(pull_request.get("head_commit"), str)
            and SHA_RE.fullmatch(pull_request["head_commit"]) is not None
            and pull_request.get("merge_commit_sha") == commit
            and isinstance(pull_request.get("tree_sha"), str)
            and SHA_RE.fullmatch(pull_request["tree_sha"]) is not None
            and isinstance(pull_request.get("merged_at"), str) and pull_request["merged_at"],
            "merged protected pull request identity is missing or malformed")
    require(pull_request.get("url") == f"https://github.com/{REPOSITORY}/pull/{pull_request['number']}",
            "source pull request URL does not identify this repository")
    refs = source.get("publication_refs")
    require(refs == ["refs/heads/main", f"refs/tags/{tag}"], "public source ref set is not the intended sanitized release set")
    history = source.get("history_scan")
    require(isinstance(history, dict) and history.get("status") == "pass"
            and history.get("revision") == commit and history.get("selected_ref") == "refs/heads/main"
            and history.get("private_refs_included") is False,
            "history scan is not bound to the exact sanitized public refs")
    report = source.get("public_content_report")
    report_sha = digest(report)
    require(source.get("public_content_report_sha256") == report_sha,
            "public-content producer report digest is invalid")
    require(isinstance(report, dict) and report.get("schema") == 1 and report.get("outcome") == "pass"
            and report.get("findings") == [] and report.get("detector_negative_only") is True,
            "public-content producer report is failed or malformed")
    coverage = report.get("coverage")
    counts = report.get("counts")
    rights_report = report.get("rights")
    require(isinstance(coverage, dict) and coverage.get("history_mode") == "selected revision"
            and coverage.get("history_revision") == commit,
            "public-content history report does not scan the exact selected revision")
    require(isinstance(counts, dict) and isinstance(counts.get("history"), dict)
            and isinstance(counts.get("source"), dict) and isinstance(counts.get("logs"), dict)
            and isinstance(rights_report, dict), "public-content report omitted scan denominators")
    require(history.get("report_sha256") == report_sha
            and history.get("files_scanned") == counts["history"].get("files")
            and history.get("bytes_scanned") == counts["history"].get("bytes"),
            "history scan counts differ from the actual public-content producer report")
    for field in ("files_scanned", "bytes_scanned"):
        require(type(history.get(field)) is int and history[field] > 0, f"history scan omitted positive {field}")
    rights = source.get("rights_scan")
    require(isinstance(rights, dict) and rights.get("status") == "pass" and rights.get("revision") == commit,
            "rights scan is not bound to the exact public source")
    for field in ("candidate_count", "rights_rows", "archive_count", "log_count", "source_file_count", "source_bytes"):
        require(type(rights.get(field)) is int and rights[field] > 0, f"rights/content evidence omitted positive {field}")
    require(rights.get("candidate_count") == rights.get("rights_rows"), "rights inventory is not complete")
    require(rights.get("report_sha256") == report_sha
            and rights.get("candidate_count") == rights_report.get("items")
            and rights.get("archive_count") == coverage.get("archives_supplied")
            and rights.get("log_count") == coverage.get("logs_supplied")
            and rights.get("source_file_count") == counts["source"].get("files")
            and rights.get("source_bytes") == counts["source"].get("bytes"),
            "rights/content denominators differ from the actual producer report")
    require(type(rights_report.get("items")) is int and rights_report["items"] > 0
            and isinstance(rights_report.get("inventory_sha256"), str)
            and DIGEST_RE.fullmatch(rights_report["inventory_sha256"]) is not None,
            "rights inventory report is incomplete")
    source_sha = source.get("source_archive_sha256")
    require(isinstance(source_sha, str) and DIGEST_RE.fullmatch(source_sha) is not None,
            "public source archive digest is missing")
    mapping = source.get("local_source_mapping_sha256")
    require(isinstance(mapping, str) and DIGEST_RE.fullmatch(mapping) is not None,
            "local-to-sanitized source correspondence is not recorded")
    require(source.get("source_tree_clean") is True, "sanitized public source tree was not clean")

    release = receipt.get("release")
    require(isinstance(release, dict) and release.get("status") == "published"
            and release.get("tag") == tag and release.get("version") == version
            and release.get("source_commit") == commit, "published release identity differs from source")
    require(release.get("url") == f"https://github.com/{REPOSITORY}/releases/tag/{tag}",
            "published release URL does not name the exact public tag")
    release_run = release.get("run")
    require(isinstance(release_run, dict) and type(release_run.get("run_id")) is int
            and release_run["run_id"] > 0 and type(release_run.get("attempt")) is int
            and release_run["attempt"] > 0, "release workflow run identity is missing")
    run_url = f"https://github.com/{REPOSITORY}/actions/runs/{release_run['run_id']}"
    require(release_run.get("repository") == REPOSITORY and release_run.get("run_url") == run_url
            and isinstance(release_run.get("publish_job_url"), str)
            and release_run["publish_job_url"].startswith(run_url + "/job/"),
            "release workflow or publisher job URL is invalid")
    manifest = release.get("manifest")
    rows = _asset_rows(manifest, commit=commit, version=version)
    require(release.get("manifest_sha256") == digest(manifest), "published manifest digest is invalid")
    require(release.get("anonymous_download") is True, "final anonymous release download was not verified")
    require(release.get("published_at") and isinstance(release.get("published_at"), str),
            "published timestamp is missing")

    correspondence = receipt.get("local_publication")
    require(isinstance(correspondence, dict) and correspondence.get("status") == "pass"
            and correspondence.get("source_commit") == commit and correspondence.get("clean_checkout") is True
            and correspondence.get("private_refs_pushed") is False,
            "isolated sanitized-public source correspondence is incomplete")
    require(type(correspondence.get("path_count")) is int and correspondence["path_count"] > 0
            and correspondence.get("mapping_sha256") == mapping,
            "local/public source mapping does not have a positive exact path denominator")
    source_map = correspondence.get("mapping")
    require(isinstance(source_map, dict)
            and set(source_map) == {"schema_version", "local_revision", "public_revision",
                                   "public_tree_sha", "scope", "path_count", "rows"}
            and source_map.get("schema_version") == 1
            and source_map.get("scope") == "release-manifest.SOURCE_PATHS"
            and isinstance(source_map.get("local_revision"), str)
            and SHA_RE.fullmatch(source_map["local_revision"]) is not None
            and source_map["local_revision"] != state_head
            and source_map.get("public_revision") == pull_request["head_commit"]
            and source_map.get("public_tree_sha") == pull_request["tree_sha"],
            "local/public source-byte correspondence identities are malformed or stale")
    map_rows = source_map.get("rows")
    require(isinstance(map_rows, list) and source_map.get("path_count") == len(map_rows)
            and correspondence.get("path_count") == len(map_rows),
            "source-byte correspondence path denominator differs from its rows")
    remapped_paths = {"docs/rights-inventory.md", "tests/fixture/rights-manifest.json",
                      "tests/workflow/test_public_content.py"}
    mapped_paths: list[str] = []
    for index, row in enumerate(map_rows):
        require(isinstance(row, dict)
                and set(row) == {"path", "local_sha256", "public_sha256", "public_blob_sha1",
                                 "mode", "transformation"},
                f"source-byte correspondence row {index} is malformed")
        path = row.get("path")
        require(isinstance(path, str) and path and "\\" not in path and "\x00" not in path
                and not path.startswith("/") and not path.startswith("-")
                and all(part not in {"", ".", "..", ".git"} for part in PurePosixPath(path).parts)
                and PurePosixPath(path).as_posix() == path,
                f"source-byte correspondence path {index} is unsafe or non-canonical")
        mapped_paths.append(path)
        require(isinstance(row.get("local_sha256"), str)
                and DIGEST_RE.fullmatch(row["local_sha256"]) is not None
                and isinstance(row.get("public_sha256"), str)
                and DIGEST_RE.fullmatch(row["public_sha256"]) is not None
                and isinstance(row.get("public_blob_sha1"), str)
                and SHA_RE.fullmatch(row["public_blob_sha1"]) is not None
                and row.get("mode") in {"100644", "100755"},
                f"source-byte correspondence digest or mode is malformed at {path}")
        transformation = row.get("transformation")
        if transformation == "exact":
            require(row["local_sha256"] == row["public_sha256"],
                    f"source-byte correspondence differs for exact path {path}")
        elif transformation == "public-release-version-authority":
            require(path == ".release-please-manifest.json"
                    and row["local_sha256"] != row["public_sha256"],
                    f"source-byte correspondence has an unapproved release-version authority change at {path}")
        else:
            require(transformation == "sanitized-public-history-remap" and path in remapped_paths
                    and row["local_sha256"] != row["public_sha256"],
                    f"source-byte correspondence has an unapproved public transformation at {path}")
    require(mapped_paths == sorted(set(mapped_paths)),
            "source-byte correspondence paths must be unique and sorted")
    require(digest(source_map) == correspondence.get("mapping_sha256") == mapping,
            "source-byte correspondence digest does not bind the path rows")

    gates = receipt.get("gates")
    require(isinstance(gates, dict), "current-head release gates are missing")
    review = gates.get("independent_review")
    require(isinstance(review, dict) and review.get("review_type") == "gsd-code-review"
            and review.get("sha") == pull_request["head_commit"] and review.get("outcome") == "pass",
            "independent review is not bound to the exact merged pull request head")
    require(isinstance(review.get("url"), str)
            and review.get("url") == pull_request["url"],
            "independent review URL does not identify the merged source pull request")
    require(isinstance(review.get("report_sha256"), str) and DIGEST_RE.fullmatch(review["report_sha256"]) is not None,
            "independent review report digest is missing")
    report_text = review.get("report")
    require(isinstance(report_text, str) and report_text.strip()
            and hashlib.sha256(report_text.encode("utf-8")).hexdigest() == review["report_sha256"],
            "independent review report bytes do not match the cited digest")
    _review_frontmatter(report_text, commit=str(review["sha"]))
    security = gates.get("independent_security_review")
    require(isinstance(security, dict) and security.get("review_type") == "gsd-security-audit"
            and security.get("sha") == pull_request["head_commit"] and security.get("outcome") == "pass"
            and security.get("url") == pull_request["url"],
            "independent security review is not bound to the exact merged pull request head")
    security_report = security.get("report")
    require(isinstance(security_report, str) and security_report.strip()
            and hashlib.sha256(security_report.encode("utf-8")).hexdigest() == security.get("report_sha256"),
            "independent security review report is missing or stale")
    security_verdict, open_threats = _security_report_verdict(security_report, commit=str(security["sha"]))
    require(security_verdict == "SECURED" and open_threats == 0,
            "independent security review has open threats or did not secure the exact source")
    findings = review.get("findings")
    require(isinstance(findings, list), "independent review findings must be an explicit list")
    require(findings == [], "independent review receipt must contain the report's clean zero-finding result")
    for index, finding in enumerate(findings):
        require(isinstance(finding, dict), f"independent review finding {index} is malformed")
        status = finding.get("status")
        if status == "resolved":
            evidence = finding.get("evidence")
            require(isinstance(evidence, str) and evidence.strip(),
                    f"resolved independent review finding {index} lacks evidence")
        else:
            require(status == "dispositioned", f"independent review finding {index} is unresolved")
            disposition, evidence = finding.get("disposition"), finding.get("evidence")
            require(isinstance(disposition, str) and disposition.strip()
                    and isinstance(evidence, str) and evidence.strip(),
                    f"dispositioned independent review finding {index} lacks disposition evidence")
    checks = gates.get("required_checks")
    require(isinstance(checks, dict) and checks.get("sha") == commit and checks.get("outcome") == "pass"
            and checks.get("strict_current_head") is True,
            "required checks are not current and strict for the published source")
    require(type(checks.get("lane_count")) is int and checks["lane_count"] > 0
            and type(checks.get("assertion_count")) is int and checks["assertion_count"] > 0,
            "required-check producer counts must be positive")
    require(isinstance(checks.get("run_url"), str) and checks["run_url"].startswith("https://github.com/")
            and isinstance(checks.get("job_url"), str) and checks["job_url"].startswith(checks["run_url"] + "/job/"),
            "required-check run/job URLs are missing")
    require(gates.get("source_event") in {"push-main", "workflow-dispatch-publish"},
            "receipt event is not an authorized protected-main publication trigger")
    authority = gates.get("publisher_authority")
    require(isinstance(authority, dict) and set(authority) == {"stage-release", "publish-release"},
            "scoped publisher authority observations are missing")
    for job_name, item in authority.items():
        require(isinstance(item, dict) and item.get("schema_version") == 1
                and item.get("outcome") == "pass"
                and item.get("kind") == "effective-token-repository-scope"
                and item.get("repository") == REPOSITORY and item.get("repository_count") == 1
                and item.get("source_revision") == commit
                and item.get("run_id") == str(release_run["run_id"])
                and item.get("job") == job_name
                and isinstance(item.get("installation_id"), str)
                and item["installation_id"].isdigit()
                and item.get("installation_wide_grant") == "not inspected",
                f"scoped App authority producer evidence is incomplete: {job_name}")
    require(gates.get("live_fork_trial") == "not-claimed",
            "an owner pull request cannot be represented as a live first-time-fork trial")

    evidence = receipt.get("platform_evidence")
    require(isinstance(evidence, list), "actual platform producer outputs are missing")
    expected_pairs = {(distribution, profile) for distribution in ("staged", "published") for profile in PROFILES}
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        require(isinstance(item, dict), "platform producer output is malformed")
        key = (item.get("distribution"), item.get("platform"))
        require(key not in seen, "platform producer output is duplicated")
        _validate_platform_evidence(item, source=source, release=release,
                                    distribution=str(key[0]), profile=str(key[1]))
        seen.add(key)
    require(seen == expected_pairs, "actual staged and anonymous-published consumers are incomplete")
    require(next(row for row in rows if row["name"] == f"glueyneo-source-{version}.tar.gz")["sha256"] == source_sha,
            "rights source archive digest differs from release bytes")
    return {"status": "pass", "source_commit": commit, "version": version,
            "platform_rows": len(evidence), "case_rows": len(evidence) * len(CASE_IDS)}


def _job_id_from_url(value: object) -> int:
    require(isinstance(value, str), "GitHub job URL is missing")
    match = re.fullmatch(rf"https://github\.com/{re.escape(REPOSITORY)}/actions/runs/[1-9][0-9]*/job/([1-9][0-9]*)", value)
    require(match is not None, "GitHub job URL does not identify this repository")
    return int(match.group(1))


def _validate_completed_job(jobs: dict[int, dict[str, object]], *, job_id: int,
                            name: str, url: str) -> None:
    job = jobs.get(job_id)
    require(isinstance(job, dict), f"actual workflow job is missing: {name}")
    require(job.get("name") == name and job.get("html_url") == url
            and job.get("status") == "completed" and job.get("conclusion") == "success",
            f"actual workflow job did not pass under the recorded identity: {name}")


def _source_archive_observations(path: Path) -> list[dict[str, object]]:
    """Hash every safe source-archive file as both SHA-256 bytes and a Git blob."""
    file_rows: dict[str, dict[str, object]] = {}
    total_bytes = 0
    try:
        archive = tarfile.open(path, mode="r:gz")
    except (OSError, tarfile.TarError) as error:
        raise DeliveryContractError("anonymous public source archive is malformed") from error
    with archive:
        members = archive.getmembers()
        require(0 < len(members) <= 50_000, "public source archive member count is empty or excessive")
        for member in members:
            name = member.name[:-1] if member.isdir() and member.name.endswith("/") else member.name
            pure = PurePosixPath(name)
            require(name and "\\" not in name and "\x00" not in name
                    and not pure.is_absolute()
                    and not re.match(r"^[A-Za-z]:", name)
                    and all(part not in {"", ".", ".."} for part in name.split("/")),
                    "public source archive contains an unsafe path")
            require(pure.parts and pure.parts[0] == "glueyneo-source",
                    "public source archive member has an unexpected root")
            if member.isdir():
                continue
            require(member.isfile() and not member.issym() and not member.islnk()
                    and member.size >= 0 and member.size <= 64 * 1024 * 1024,
                    "public source archive contains an oversized, linked or special member")
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            require(relative and relative not in file_rows,
                    "public source archive contains duplicate or root-only files")
            total_bytes += member.size
            require(total_bytes <= 512 * 1024 * 1024,
                    "public source archive exceeds the total byte limit")
            stream = archive.extractfile(member)
            require(stream is not None, "public source archive member bytes are unavailable")
            sha256 = hashlib.sha256()
            git_blob = hashlib.sha1(b"blob " + str(member.size).encode("ascii") + b"\0")
            read_bytes = 0
            with stream:
                while block := stream.read(1024 * 1024):
                    read_bytes += len(block)
                    require(read_bytes <= member.size,
                            "public source archive member exceeds its declared size")
                    sha256.update(block)
                    git_blob.update(block)
            require(read_bytes == member.size,
                    "public source archive member is truncated")
            file_rows[relative] = {
                "path": relative,
                "sha256": sha256.hexdigest(),
                "public_blob_sha1": git_blob.hexdigest(),
                "mode": "100755" if member.mode & 0o111 else "100644",
            }
    return [file_rows[path] for path in sorted(file_rows)]


def validate_live_observations(receipt: object, live: object) -> dict[str, object]:
    """Cross-check a structurally valid receipt against observed GitHub producers and public bytes."""
    result = validate_receipt(receipt)
    require(isinstance(live, dict), "live GitHub/release observations are missing")
    source = receipt["source"]
    release = receipt["release"]
    commit = source["commit"]
    run_identity = release["run"]
    run_id = run_identity["run_id"]
    run = live.get("release_run")
    require(isinstance(run, dict) and type(run.get("id")) is int
            and run.get("id") == run_identity.get("run_id")
            and run.get("run_attempt") == run_identity.get("attempt")
            and run.get("head_sha") == source["workflow_commit"] and run.get("head_branch") == "main"
            and run.get("event") in {"push", "workflow_dispatch"} and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and run.get("path", "").split("@", 1)[0] == ".github/workflows/release.yml"
            and isinstance(run.get("repository"), dict)
            and run["repository"].get("full_name") == REPOSITORY,
            "published producer run is not a successful current-source main publication")
    trigger = live.get("publication_trigger")
    require(isinstance(trigger, dict) and trigger.get("schema_version") == 1
            and trigger.get("repository") == REPOSITORY
            and trigger.get("event") == run.get("event")
            and trigger.get("ref") == "refs/heads/main"
            and trigger.get("source_commit") == commit
            and trigger.get("workflow_commit") == source["workflow_commit"] == run.get("head_sha")
            and trigger.get("publication_expected") is True,
            "published release trigger does not prove the exact protected-main source")
    if run.get("event") == "push":
        require(trigger.get("source_event") == "push-main"
                and trigger.get("publish_input") in {None, False},
                "push publication trigger is inconsistent")
    else:
        require(trigger.get("source_event") == "workflow-dispatch-publish"
                and trigger.get("publish_input") is True,
                "manual publication did not record publish=true")
    require(receipt["gates"].get("source_event") == trigger.get("source_event"),
            "receipt source event differs from the recorded trusted publication trigger")
    expected_run_url = f"https://github.com/{REPOSITORY}/actions/runs/{run_identity['run_id']}"
    require(run.get("html_url") == expected_run_url and run_identity.get("run_url") == expected_run_url,
            "release producer run URL differs from the observed workflow")
    pull_request_identity = source["pull_request"]
    live_pr = live.get("pull_request")
    require(isinstance(live_pr, dict)
            and live_pr.get("number") == pull_request_identity["number"]
            and live_pr.get("html_url") == pull_request_identity["url"]
            and live_pr.get("state") == "closed" and live_pr.get("merged") is True
            and isinstance(live_pr.get("merged_at"), str)
            and live_pr.get("merged_at") == pull_request_identity["merged_at"]
            and isinstance(live_pr.get("base"), dict)
            and live_pr["base"].get("ref") == "main"
            and isinstance(live_pr.get("head"), dict)
            and live_pr["head"].get("sha") == pull_request_identity["head_commit"]
            and live_pr.get("merge_commit_sha") == commit,
            "public GitHub pull request does not prove the reviewed source was merged to main")
    head_commit = live.get("pull_request_head_commit")
    merge_commit = live.get("pull_request_merge_commit")
    require(isinstance(head_commit, dict) and isinstance(merge_commit, dict)
            and isinstance(head_commit.get("commit"), dict) and isinstance(merge_commit.get("commit"), dict)
            and isinstance(head_commit["commit"].get("tree"), dict)
            and isinstance(merge_commit["commit"].get("tree"), dict)
            and head_commit["commit"]["tree"].get("sha") == pull_request_identity["tree_sha"]
            and merge_commit["commit"]["tree"].get("sha") == pull_request_identity["tree_sha"],
            "reviewed pull request tree differs from the exact public release source tree")
    mapping_rows = receipt["local_publication"]["mapping"]["rows"]
    source_tree = live.get("public_source_tree")
    require(isinstance(source_tree, list), "public Git tree observation is missing")
    tree_by_path: dict[str, dict[str, object]] = {}
    for row in source_tree:
        require(isinstance(row, dict) and isinstance(row.get("path"), str)
                and row["path"] not in tree_by_path,
                "public Git tree observation has malformed or duplicate paths")
        tree_by_path[row["path"]] = row
    for row in mapping_rows:
        observed = tree_by_path.get(row["path"])
        require(isinstance(observed, dict) and observed.get("type") == "blob"
                and observed.get("sha") == row["public_blob_sha1"]
                and observed.get("mode") == row["mode"],
                f"public Git tree differs from source-byte correspondence at {row['path']}")
    archive_rows = live.get("public_source_archive")
    require(isinstance(archive_rows, list), "anonymous public source archive observations are missing")
    archive_by_path: dict[str, dict[str, object]] = {}
    for row in archive_rows:
        require(isinstance(row, dict) and isinstance(row.get("path"), str)
                and row["path"] not in archive_by_path,
                "anonymous public source archive observations are malformed or duplicated")
        archive_by_path[row["path"]] = row
    require(set(archive_by_path) == {row["path"] for row in mapping_rows},
            "anonymous public source archive path coverage differs from the source-byte mapping")
    for row in mapping_rows:
        observed = archive_by_path[row["path"]]
        require(observed.get("sha256") == row["public_sha256"]
                and observed.get("public_blob_sha1") == row["public_blob_sha1"]
                and observed.get("mode") == row["mode"],
                f"public source archive bytes differ from source-byte correspondence at {row['path']}")
    require(live.get("current_main_sha") == commit,
            "public main no longer points at the exact delivered source commit")
    require(live.get("tag_commit") == commit,
            "public release tag does not resolve to the exact delivered source commit")

    jobs_value = live.get("release_jobs")
    require(isinstance(jobs_value, list), "release workflow job observations are missing")
    jobs: dict[int, dict[str, object]] = {}
    for job in jobs_value:
        require(isinstance(job, dict) and type(job.get("id")) is int and job["id"] > 0,
                "release workflow job observation is malformed")
        require(job["id"] not in jobs, "release workflow contains duplicate job identities")
        jobs[job["id"]] = job
    publisher_id = _job_id_from_url(run_identity.get("publish_job_url"))
    _validate_completed_job(jobs, job_id=publisher_id, name="publish-release",
                            url=run_identity["publish_job_url"])
    platform_evidence = receipt["platform_evidence"]
    expected_job_ids = {publisher_id}
    observed_platforms = live.get("platform_artifacts")
    require(isinstance(observed_platforms, dict), "downloaded platform producer artifacts are missing")
    for item in platform_evidence:
        distribution, profile = item["distribution"], item["platform"]
        job = item["run"]
        job_id = job["job_id"]
        require(job_id not in expected_job_ids, "multiple platform records reuse one GitHub job identity")
        expected_job_ids.add(job_id)
        _validate_completed_job(jobs, job_id=job_id, name=job["job_name"], url=job["job_url"])
        rows = observed_platforms.get(distribution)
        require(isinstance(rows, dict) and rows.get(profile) == item,
                f"receipt platform evidence differs from the uploaded {distribution} producer artifact for {profile}")
    require(expected_job_ids.issubset(set(jobs)), "one or more recorded producer jobs were not observed")

    report = source.get("public_content_report")
    require(live.get("public_content_report_artifact") == report,
            "receipt public-content report differs from the uploaded scanner artifact")
    require(live.get("staged_manifest_artifact") == release.get("manifest")
            and live.get("published_manifest_artifact") == release.get("manifest"),
            "workflow producer manifests differ from the released manifest")
    published_artifact = live.get("published_release_artifact")
    release_api = live.get("release_api")
    require(isinstance(published_artifact, dict) and isinstance(release_api, dict)
            and published_artifact.get("tag_name") == release.get("tag")
            and published_artifact.get("draft") is False
            and published_artifact.get("html_url") == release.get("url")
            and release_api.get("tag_name") == release.get("tag")
            and release_api.get("draft") is False
            and release_api.get("html_url") == release.get("url")
            and release_api.get("published_at") == release.get("published_at"),
            "published-release producer artifact differs from the public release API")
    require(live.get("anonymous_release_manifest") == release.get("manifest"),
            "anonymous public release-manifest bytes differ from the protected producer manifest")
    rows = _asset_rows(release.get("manifest"), commit=commit, version=release["version"])
    expected_asset_rows = {row["name"]: row for row in rows}
    actual_asset_rows = live.get("anonymous_asset_rows")
    require(isinstance(actual_asset_rows, list), "anonymous public asset byte observations are missing")
    by_name: dict[str, object] = {}
    for row in actual_asset_rows:
        require(isinstance(row, dict) and isinstance(row.get("name"), str)
                and row["name"] not in by_name, "anonymous public asset observation is malformed or duplicated")
        by_name[row["name"]] = row
    require(set(by_name) == set(expected_asset_rows) | {"release-manifest.json"},
            "anonymous public asset names differ from the complete release inventory")
    for name, expected in expected_asset_rows.items():
        require(by_name[name] == expected, f"anonymous downloaded public asset differs from the manifest: {name}")
    manifest_bytes = canonical_json(release.get("manifest"))
    manifest_row = by_name["release-manifest.json"]
    require(manifest_row == {"name": "release-manifest.json", "size": len(manifest_bytes),
                             "sha256": hashlib.sha256(manifest_bytes).hexdigest()},
            "anonymous downloaded release-manifest bytes differ from the actual protected manifest")
    assets = release_api.get("assets")
    require(isinstance(assets, list), "public release API asset inventory is missing")
    api_assets: dict[str, object] = {}
    for asset in assets:
        require(isinstance(asset, dict) and isinstance(asset.get("name"), str)
                and asset["name"] not in api_assets, "public release API asset inventory is malformed")
        api_assets[asset["name"]] = asset
    require(set(api_assets) == set(by_name), "public release API asset names differ from anonymous downloads")
    for name, row in by_name.items():
        require(api_assets[name].get("size") == row["size"],
                f"public release API asset size differs from anonymous bytes: {name}")

    protection = live.get("main_protection")
    checks_protection = protection.get("required_status_checks") if isinstance(protection, dict) else None
    admins = protection.get("enforce_admins") if isinstance(protection, dict) else None
    require(isinstance(checks_protection, dict) and checks_protection.get("strict") is True
            and "ci-policy" in checks_protection.get("contexts", [])
            and isinstance(admins, dict) and admins.get("enabled") is True,
            "current public main protection is not strict with enforced admins and ci-policy")
    ci = receipt["gates"]["required_checks"]
    gates = receipt["gates"]
    ci_run = live.get("ci_run")
    ci_job = live.get("ci_policy_job")
    aggregate = live.get("ci_aggregate_artifact")
    ci_run_id = _job_id_from_url(ci["job_url"])
    del ci_run_id
    ci_run_match = re.fullmatch(rf"https://github\.com/{re.escape(REPOSITORY)}/actions/runs/([1-9][0-9]*)", ci["run_url"])
    require(ci_run_match is not None and isinstance(ci_run, dict)
            and ci_run.get("id") == int(ci_run_match.group(1))
            and ci_run.get("head_sha") == commit and ci_run.get("head_branch") == "main"
            and ci_run.get("event") == "push" and ci_run.get("status") == "completed"
            and ci_run.get("conclusion") == "success"
            and ci_run.get("path", "").split("@", 1)[0] == ".github/workflows/ci.yml",
            "required CI run is not successful for the exact source commit on public main")
    require(isinstance(ci_job, dict) and ci_job.get("name") == "ci-policy"
            and ci_job.get("html_url") == ci.get("job_url")
            and ci_job.get("status") == "completed" and ci_job.get("conclusion") == "success",
            "required ci-policy job is not the exact successful producer")
    require(isinstance(aggregate, dict) and aggregate.get("source_revision") == commit
            and aggregate.get("outcome") == "pass"
            and aggregate.get("lane_count") == ci.get("lane_count")
            and aggregate.get("assertion_count") == ci.get("assertion_count"),
            "required-check counts differ from the uploaded current-source aggregate artifact")
    authority = gates.get("publisher_authority")
    actual_authority = live.get("publisher_authority")
    require(isinstance(authority, dict) and isinstance(actual_authority, dict)
            and actual_authority == authority,
            "receipt publisher authority differs from uploaded scoped App evidence")
    for job_name, scope in authority.items():
        require(isinstance(scope, dict) and scope.get("run_id") == str(run_id)
                and scope.get("source_revision") == commit and scope.get("job") == job_name
                and scope.get("repository_count") == 1 and scope.get("repository") == REPOSITORY,
                f"observed App token scope is not tied to the exact release producer: {job_name}")
    return {**result, "live_status": "pass", "run_id": run_identity["run_id"],
            "verified_public_assets": len(by_name), "verified_producer_jobs": len(expected_job_ids),
            "verified_pull_request": pull_request_identity["number"]}


def _github_api_json(endpoint: str) -> object:
    result = subprocess.run(["gh", "api", endpoint], cwd=ROOT, capture_output=True,
                           text=True, check=False, timeout=30)
    require(result.returncode == 0, "read-only GitHub API request failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise DeliveryContractError("read-only GitHub API response is malformed") from error


def _verify_local_source_mapping(mapping: dict[str, object]) -> None:
    """Prove each local-side digest against the recorded immutable local commit."""
    revision = mapping["local_revision"]
    tree_result = subprocess.run(["git", "ls-tree", "-r", "-z", str(revision)], cwd=ROOT,
                                 capture_output=True, check=False, timeout=60)
    require(tree_result.returncode == 0, "recorded local source revision is unavailable")
    local_tree: dict[str, tuple[str, str]] = {}
    for entry in tree_result.stdout.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, kind, blob = metadata.decode("ascii").split(" ")
            path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as error:
            raise DeliveryContractError("recorded local Git tree is malformed") from error
        require(kind == "blob" and path not in local_tree,
                "recorded local source tree contains an unexpected or duplicate entry")
        local_tree[path] = (mode, blob)
    for row in mapping["rows"]:
        path = row["path"]
        observed = local_tree.get(path)
        require(observed is not None and observed[0] == row["mode"]
                and SHA_RE.fullmatch(observed[1]) is not None,
                f"local Git tree differs from source-byte correspondence at {path}")
        blob_result = subprocess.run(["git", "cat-file", "blob", observed[1]], cwd=ROOT,
                                     capture_output=True, check=False, timeout=30)
        require(blob_result.returncode == 0
                and hashlib.sha256(blob_result.stdout).hexdigest() == row["local_sha256"],
                f"local source bytes differ from source-byte correspondence at {path}")


def _download_run_artifact(run_id: int, name: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["gh", "run", "download", str(run_id), "--repo", REPOSITORY,
                             "--name", name, "--dir", str(destination)], cwd=ROOT,
                            capture_output=True, text=True, check=False, timeout=120)
    require(result.returncode == 0, f"required GitHub producer artifact is unavailable: {name}")


def _artifact_json(directory: Path, filename: str) -> object:
    matches = [path for path in directory.rglob(filename) if path.is_file() and not path.is_symlink()]
    require(len(matches) == 1, f"producer artifact is missing or duplicates {filename}")
    path = matches[0]
    require(path.stat().st_size <= 16 * 1024 * 1024,
            f"producer artifact JSON exceeds the evidence size limit: {filename}")
    return _read_json(path)


def _download_public_release(directory: Path, manifest_path: Path, *, tag: str,
                             version: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    require(release_manifest.VERSION_RE.fullmatch(version) is not None and tag == f"v{version}",
            "public release tag/version is malformed or inconsistent")
    import release_state
    manifest = _read_json(manifest_path)
    rows = _asset_rows(manifest, commit=str(manifest.get("source_commit")), version=version)
    directory.mkdir(parents=True, exist_ok=True)
    urls = [f"https://github.com/{REPOSITORY}/releases/download/{tag}/{name}"
            for name in ("release-manifest.json", *(row["name"] for row in rows))]
    asset_rows: list[dict[str, object]] = []
    for url, name in zip(urls, ["release-manifest.json", *(str(row["name"]) for row in rows)], strict=True):
        destination = directory / name
        maximum = 2 * 1024 * 1024 if name == "release-manifest.json" else next(
            int(row["size"]) for row in rows if row["name"] == name)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Glueyneo-release-verifier"})
            with urllib.request.urlopen(request, timeout=120) as response, destination.open("xb") as output:
                host = urllib.parse.urlparse(response.geturl()).hostname or ""
                require(host == "github.com" or host.endswith(".githubusercontent.com"),
                        "anonymous release download followed an unexpected host redirect")
                total = 0
                digest_value = hashlib.sha256()
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    require(total <= maximum, f"anonymous release asset exceeds its expected size: {name}")
                    output.write(block)
                    digest_value.update(block)
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            raise DeliveryContractError(f"anonymous public release download failed: {name}") from error
        asset_rows.append({"name": name, "size": total, "sha256": digest_value.hexdigest()})
    identity = release_state.validate_downloaded_assets(directory, manifest_path)
    require(identity.get("outcome") == "pass" and identity.get("source_commit") == manifest.get("source_commit")
            and identity.get("version") == version, "anonymous public release bytes failed exact manifest verification")
    public_manifest = _read_json(directory / "release-manifest.json")
    require(public_manifest == manifest, "anonymous public manifest differs from the staged producer manifest")
    return public_manifest, asset_rows


def verify_receipt_live(receipt: object) -> dict[str, object]:
    """Verify a receipt against current read-only GitHub APIs, uploaded producers, and anonymous assets."""
    validate_receipt(receipt)
    require(isinstance(receipt, dict), "delivery receipt must be an object")
    source = receipt["source"]
    _verify_local_source_mapping(receipt["local_publication"]["mapping"])
    release = receipt["release"]
    run_record = release["run"]
    run_id, attempt = run_record["run_id"], run_record["attempt"]
    run = _github_api_json(f"repos/{REPOSITORY}/actions/runs/{run_id}")
    require(isinstance(run, dict), "release workflow run API response is malformed")
    jobs_payload = _github_api_json(f"repos/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    artifacts_payload = _github_api_json(f"repos/{REPOSITORY}/actions/runs/{run_id}/artifacts?per_page=100")
    require(isinstance(jobs_payload, dict) and isinstance(jobs_payload.get("jobs"), list),
            "release workflow job API response is malformed")
    require(isinstance(artifacts_payload, dict) and isinstance(artifacts_payload.get("artifacts"), list),
            "release workflow artifact API response is malformed")
    artifact_rows = artifacts_payload["artifacts"]
    artifact_by_name: dict[str, dict[str, object]] = {}
    for artifact in artifact_rows:
        require(isinstance(artifact, dict) and isinstance(artifact.get("name"), str),
                "release workflow artifact API row is malformed")
        if artifact["name"] in artifact_by_name:
            raise DeliveryContractError("release workflow artifact names are ambiguous across attempts")
        artifact_by_name[artifact["name"]] = artifact

    expected_names = [f"delivery-evidence-staged-{profile}-attempt-{attempt}" for profile in PROFILES]
    expected_names += [f"delivery-evidence-published-{profile}-attempt-{attempt}" for profile in PROFILES]
    expected_names += [f"delivery-evidence-public-content-attempt-{attempt}",
                       f"delivery-evidence-published-release-attempt-{attempt}",
                       f"release-app-authority-stage-release-attempt-{attempt}",
                       f"release-identity-manifest-attempt-{attempt}"]
    downloaded: dict[str, Path] = {}
    with tempfile.TemporaryDirectory(prefix="glueyneo-live-receipt-") as temp_name:
        root = Path(temp_name)
        for name in expected_names:
            artifact = artifact_by_name.get(name)
            require(isinstance(artifact, dict) and artifact.get("expired") is False,
                    f"required workflow producer artifact is missing or expired: {name}")
            path = root / name
            _download_run_artifact(run_id, name, path)
            downloaded[name] = path

        platform_artifacts: dict[str, dict[str, object]] = {"staged": {}, "published": {}}
        for distribution in ("staged", "published"):
            for profile in PROFILES:
                name = f"delivery-evidence-{distribution}-{profile}-attempt-{attempt}"
                path = downloaded[name]
                platform = _artifact_json(path, "platform.json")
                consumer = _artifact_json(path, "consumer-result.json")
                require(isinstance(platform, dict) and platform.get("consumer_result") == consumer,
                        "platform producer artifact does not bind its consumer result")
                expected = _artifact_json(path, "expected-release-manifest.json")
                manifest = _artifact_json(path, "release-manifest.json")
                require(expected == release["manifest"] and manifest == release["manifest"],
                        "platform producer artifact manifest differs from the receipt")
                if distribution == "staged":
                    verification = _artifact_json(path, "download-verification.json")
                    require(isinstance(verification, dict) and verification.get("outcome") == "pass"
                            and verification.get("source_commit") == source["commit"]
                            and verification.get("version") == source["version"],
                            "staged platform download verification artifact did not pass")
                platform_artifacts[distribution][profile] = platform
        public_content = _artifact_json(downloaded[f"delivery-evidence-public-content-attempt-{attempt}"],
                                        "public-content.json")
        published_dir = downloaded[f"delivery-evidence-published-release-attempt-{attempt}"]
        published_release_artifact = _artifact_json(published_dir, "published-release.json")
        publication_trigger = _artifact_json(published_dir, "release-trigger.json")
        published_manifest = _artifact_json(published_dir, "expected-release-manifest.json")
        publish_scope = _artifact_json(published_dir, "app-authority.json")
        stage_scope_dir = downloaded[f"release-app-authority-stage-release-attempt-{attempt}"]
        stage_scope = _artifact_json(stage_scope_dir, "app-authority.json")
        staged_manifest = _artifact_json(downloaded[f"release-identity-manifest-attempt-{attempt}"],
                                         "expected-release-manifest.json")

        ci = receipt["gates"]["required_checks"]
        ci_run_match = re.fullmatch(rf"https://github\.com/{re.escape(REPOSITORY)}/actions/runs/([1-9][0-9]*)", ci["run_url"])
        require(ci_run_match is not None, "required CI run URL is malformed")
        ci_run_id = int(ci_run_match.group(1))
        ci_run = _github_api_json(f"repos/{REPOSITORY}/actions/runs/{ci_run_id}")
        ci_jobs_payload = _github_api_json(f"repos/{REPOSITORY}/actions/runs/{ci_run_id}/jobs?per_page=100")
        require(isinstance(ci_jobs_payload, dict) and isinstance(ci_jobs_payload.get("jobs"), list),
                "required CI job API response is malformed")
        ci_job_id = _job_id_from_url(ci.get("job_url"))
        ci_matches = [job for job in ci_jobs_payload["jobs"] if isinstance(job, dict) and job.get("id") == ci_job_id]
        require(len(ci_matches) == 1, "required ci-policy job is absent or ambiguous")
        ci_policy_job = ci_matches[0]
        ci_dir = root / "ci-aggregate-receipt"
        _download_run_artifact(ci_run_id, "ci-aggregate-receipt", ci_dir)
        ci_aggregate = _artifact_json(ci_dir, "ci-aggregate.json")

        with tempfile.TemporaryDirectory(prefix="glueyneo-anonymous-release-") as public_temp:
            public_dir = Path(public_temp)
            expected_path = public_dir / "expected-release-manifest.json"
            expected_path.write_bytes(canonical_json(release["manifest"]))
            public_manifest, public_asset_rows = _download_public_release(
                public_dir / "assets", expected_path, tag=release["tag"], version=release["version"])
            public_source_archive_rows = _source_archive_observations(
                public_dir / "assets" / f"glueyneo-source-{release['version']}.tar.gz")

    release_api = _github_api_json(f"repos/{REPOSITORY}/releases/tags/{release['tag']}")
    pr_number = source["pull_request"]["number"]
    pull_request = _github_api_json(f"repos/{REPOSITORY}/pulls/{pr_number}")
    pr_head_commit = _github_api_json(f"repos/{REPOSITORY}/commits/{source['pull_request']['head_commit']}")
    pr_source_tree = _github_api_json(
        f"repos/{REPOSITORY}/git/trees/{source['pull_request']['tree_sha']}?recursive=1")
    require(isinstance(pr_source_tree, dict) and pr_source_tree.get("truncated") is False
            and isinstance(pr_source_tree.get("tree"), list),
            "public Git tree API response is missing or truncated")
    pr_merge_commit = _github_api_json(f"repos/{REPOSITORY}/commits/{commit}")
    tag_ref = _github_api_json(f"repos/{REPOSITORY}/git/ref/tags/{release['tag']}")
    tag_obj = tag_ref.get("object") if isinstance(tag_ref, dict) else None
    require(isinstance(tag_obj, dict), "public release tag ref response is malformed")
    if tag_obj.get("type") == "tag":
        annotated = _github_api_json(f"repos/{REPOSITORY}/git/tags/{tag_obj.get('sha')}")
        tag_obj = annotated.get("object") if isinstance(annotated, dict) else None
    require(isinstance(tag_obj, dict) and tag_obj.get("type") == "commit", "public release tag is not a commit")
    main_ref = _github_api_json(f"repos/{REPOSITORY}/git/ref/heads/main")
    main_obj = main_ref.get("object") if isinstance(main_ref, dict) else None
    require(isinstance(main_obj, dict) and isinstance(main_obj.get("sha"), str), "public main ref is unavailable")
    main_protection = _github_api_json(f"repos/{REPOSITORY}/branches/main/protection")

    live = {"release_run": run, "release_jobs": jobs_payload["jobs"],
            "current_main_sha": main_obj["sha"], "tag_commit": tag_obj.get("sha"),
            "release_api": release_api, "platform_artifacts": platform_artifacts,
            "pull_request": pull_request, "pull_request_head_commit": pr_head_commit,
            "public_source_tree": pr_source_tree["tree"],
            "pull_request_merge_commit": pr_merge_commit,
            "publication_trigger": publication_trigger,
            "public_content_report_artifact": public_content,
            "staged_manifest_artifact": staged_manifest,
            "published_manifest_artifact": published_manifest,
            "published_release_artifact": published_release_artifact,
            "anonymous_release_manifest": public_manifest, "anonymous_asset_rows": public_asset_rows,
            "public_source_archive": public_source_archive_rows,
            "main_protection": main_protection, "ci_run": ci_run,
            "ci_policy_job": ci_policy_job, "ci_aggregate_artifact": ci_aggregate,
            "publisher_authority": {"stage-release": stage_scope, "publish-release": publish_scope}}
    return validate_live_observations(receipt, live)


def _find_current_job(profile: str) -> dict[str, object]:
    env = os.environ
    repository = env.get("GITHUB_REPOSITORY", "")
    run_id = env.get("GITHUB_RUN_ID", "")
    attempt = env.get("GITHUB_RUN_ATTEMPT", "")
    job_key = env.get("GITHUB_JOB", "")
    require(repository == REPOSITORY and run_id.isdigit() and attempt.isdigit() and job_key,
            "GitHub run/job identity is unavailable")
    api = env.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    endpoint = f"{api}/repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100"
    result = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True, check=False, timeout=30)
    require(result.returncode == 0, "read-only GitHub job metadata query failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise DeliveryContractError("GitHub job metadata response is malformed") from error
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    require(isinstance(jobs, list), "GitHub job metadata omitted jobs")
    matches = [job for job in jobs if isinstance(job, dict)
               and str(job.get("name", "")).startswith(job_key + " (")
               and profile in str(job.get("name", ""))]
    require(len(matches) == 1, "current named platform job is missing or ambiguous")
    job = matches[0]
    require(type(job.get("id")) is int and job["id"] > 0 and job.get("status") in {"in_progress", "completed"},
            "current GitHub job is not an identified running/completed producer")
    run_url = f"{env.get('GITHUB_SERVER_URL', 'https://github.com').rstrip('/')}/{repository}/actions/runs/{run_id}"
    require(job.get("html_url") == f"{run_url}/job/{job['id']}", "GitHub job URL does not match its producer ID")
    return {"repository": repository, "run_id": int(run_id), "attempt": int(attempt),
            "run_url": run_url,
            "job_id": job["id"], "job_url": job.get("html_url"), "job_name": job["name"]}


def create_platform_evidence(*, directory: Path, manifest_path: Path, consumer_path: Path,
                             profile: str, distribution: str) -> dict[str, object]:
    require(profile in PROFILES and distribution in {"staged", "published"},
            "platform evidence profile or distribution is unsupported")
    try:
        import release_state
        identity = release_state.validate_downloaded_assets(directory, manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        consumer = json.loads(consumer_path.read_text(encoding="utf-8"))
        downloaded_manifest = json.loads((directory / "release-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise DeliveryContractError(f"producer inputs are unreadable or invalid: {error}") from error
    commit, version = identity.get("source_commit"), identity.get("version")
    workflow_commit = os.environ.get("RELEASE_WORKFLOW_COMMIT", "")
    require(isinstance(commit, str) and SHA_RE.fullmatch(commit) is not None
            and SHA_RE.fullmatch(workflow_commit) is not None,
            "selected Release Please source or workflow revision is not a full commit identity")
    rows = _asset_rows(manifest, commit=str(commit), version=str(version))
    require(downloaded_manifest == manifest, "downloaded release manifest differs from trusted staged producer manifest")
    downloaded_assets: list[dict[str, object]] = []
    for row in rows:
        path = directory / str(row["name"])
        data = path.read_bytes()
        observed = {"name": row["name"], "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        require(observed == row, f"downloaded asset bytes differ from producer manifest: {row['name']}")
        downloaded_assets.append(observed)
    source_name = f"glueyneo-source-{version}.tar.gz"
    sdk_name = f"glueyneo-sdk-{version}-{profile}.tar.gz"
    _validate_consumer_result(consumer, commit=str(commit), version=str(version), profile=profile,
                              source_sha=str(next(row["sha256"] for row in rows if row["name"] == source_name)),
                              sdk_sha=str(next(row["sha256"] for row in rows if row["name"] == sdk_name)))
    evidence: dict[str, object] = {
        "distribution": distribution,
        "platform": profile,
        "source_commit": commit,
        "workflow_commit": workflow_commit,
        "version": version,
        "manifest": manifest,
        "manifest_sha256": digest(manifest),
        "downloaded_assets": downloaded_assets,
        "consumer_result": consumer,
        "consumer_result_sha256": digest(consumer),
        "run": _find_current_job(profile),
    }
    evidence["evidence_sha256"] = digest(evidence)
    return evidence


def _valid_platform_result(version: str = "1.2.3") -> dict[str, object]:
    cases = [{"id": case_id, "status": "unsupported" if case_id.endswith("host-persistence") else "pass"}
             for case_id in CASE_IDS]
    return {"outcome": "pass", "source_commit": "a" * 40, "version": version,
            "platform": "linux-x86_64", "variants": ["static", "shared"],
            "downloaded_byte_verification": "pass", "source_archive_sha256": "1" * 64,
            "sdk_archive_sha256": "2" * 64, "offline_source_rebuild": "pass",
            "guide_command_closure": "pass", "cases": cases,
            "toolchain": {"cmake_version": "3.30.0", "configuration": "Release",
                          "source_compiler_id": "Clang", "source_compiler_version": "19.1",
                          "builds": [{"linkage": "static", "compiler_id": "Clang", "compiler_version": "19.1"},
                                     {"linkage": "shared", "compiler_id": "Clang", "compiler_version": "19.1"}]}}


def _valid_manifest(version: str = "1.2.3") -> dict[str, object]:
    names = [f"glueyneo-source-{version}.tar.gz",
             *(f"glueyneo-sdk-{version}-{profile}.tar.gz" for profile in PROFILES)]
    return {"schema_version": 1, "tag": f"v{version}", "source_commit": "a" * 40,
            "version": version, "assets": [{"name": name, "size": 12, "sha256": hashlib.sha256(name.encode()).hexdigest()}
                                               for name in names]}


def _valid_evidence(profile: str, distribution: str, version: str = "1.2.3") -> dict[str, object]:
    manifest = _valid_manifest(version)
    rows = manifest["assets"]
    source_sha = next(row["sha256"] for row in rows if row["name"].startswith("glueyneo-source-"))
    sdk_sha = next(row["sha256"] for row in rows if f"-{profile}.tar.gz" in row["name"])
    consumer = _valid_platform_result(version)
    consumer.update(platform=profile, source_archive_sha256=source_sha, sdk_archive_sha256=sdk_sha)
    if profile == "macos-arm64":
        for row in consumer["cases"]:
            if row["id"].endswith("host-persistence"):
                row["status"] = "pass"
    profile_index = PROFILES.index(profile)
    distribution_index = ("staged", "published").index(distribution)
    job_id = 1000 + distribution_index * len(PROFILES) + profile_index
    job_name = "verify-downloaded-release" if distribution == "staged" else "verify-published-release"
    base = {"distribution": distribution, "platform": profile, "source_commit": "a" * 40,
            "workflow_commit": "a" * 40, "version": version, "manifest": manifest,
            "manifest_sha256": digest(manifest),
            "downloaded_assets": copy.deepcopy(rows), "consumer_result": consumer,
            "consumer_result_sha256": digest(consumer),
            "run": {"repository": REPOSITORY, "run_id": 123, "attempt": 1,
                    "run_url": f"https://github.com/{REPOSITORY}/actions/runs/123",
                    "job_id": job_id, "job_name": f"{job_name} ({profile})",
                    "job_url": f"https://github.com/{REPOSITORY}/actions/runs/123/job/{job_id}"}}
    base["evidence_sha256"] = digest(base)
    return base


def _valid_receipt(version: str = "1.2.3") -> dict[str, object]:
    manifest = _valid_manifest(version)
    source_sha = manifest["assets"][0]["sha256"]
    refs = ["refs/heads/main", f"refs/tags/v{version}"]
    run = {"repository": REPOSITORY, "run_id": 123, "attempt": 1,
           "run_url": f"https://github.com/{REPOSITORY}/actions/runs/123",
           "publish_job_url": f"https://github.com/{REPOSITORY}/actions/runs/123/job/999"}
    receipt = {
        "schema_version": 1, "status": "published",
        "source": {"repository": REPOSITORY, "commit": "a" * 40, "workflow_commit": "a" * 40,
                   "pull_request": {"number": 10, "url": f"https://github.com/{REPOSITORY}/pull/10",
                                    "base_ref": "main", "head_commit": "c" * 40,
                                    "merge_commit_sha": "a" * 40, "tree_sha": "d" * 40,
                                    "merged_at": "2026-10-28T11:00:00Z"},
                   "planning_state_head": "b" * 40, "version": version, "tag": f"v{version}",
                   "public_ref": "refs/heads/main", "publication_refs": refs, "private_history_included": False,
                   "source_tree_clean": True, "source_archive_sha256": source_sha,
                   "local_source_mapping_sha256": "3" * 64,
                   "public_content_report": {"schema": 1, "outcome": "pass", "findings": [],
                                             "detector_negative_only": True,
                                             "rights": {"items": 120,
                                                        "inventory_sha256": "7" * 64},
                                             "coverage": {"history_mode": "selected revision",
                                                          "history_revision": "a" * 40,
                                                          "archives_supplied": 4, "logs_supplied": 2},
                                             "counts": {"source": {"files": 250, "bytes": 900000},
                                                        "history": {"files": 200, "bytes": 3000},
                                                        "logs": {"files": 2, "bytes": 1000},
                                                        "archives": {"files": 400, "bytes": 50000}}},
                   "public_content_report_sha256": "",
                   "history_scan": {"status": "pass", "revision": "a" * 40,
                                    "selected_ref": "refs/heads/main", "private_refs_included": False,
                                    "files_scanned": 200, "bytes_scanned": 3000, "report_sha256": ""},
                   "rights_scan": {"status": "pass", "revision": "a" * 40, "candidate_count": 120,
                                   "rights_rows": 120, "archive_count": 4, "log_count": 2,
                                   "source_file_count": 250, "source_bytes": 900000, "report_sha256": ""}},
        "release": {"status": "published", "tag": f"v{version}", "version": version,
                    "source_commit": "a" * 40, "url": f"https://github.com/{REPOSITORY}/releases/tag/v{version}",
                    "published_at": "2026-10-28T12:00:00Z", "run": run, "manifest": manifest,
                    "manifest_sha256": digest(manifest), "anonymous_download": True},
        "local_publication": {"status": "pass", "source_commit": "a" * 40, "clean_checkout": True,
                              "private_refs_pushed": False, "path_count": 1,
                              "mapping_sha256": "", "mapping": {
                                  "schema_version": 1, "local_revision": "1" * 40,
                                  "public_revision": "c" * 40, "public_tree_sha": "d" * 40,
                                  "scope": "release-manifest.SOURCE_PATHS",
                                  "path_count": 1,
                                  "rows": [{"path": "README.md", "local_sha256": "4" * 64,
                                            "public_sha256": "4" * 64, "public_blob_sha1": "5" * 40,
                                            "mode": "100644", "transformation": "exact"}]}},
        "gates": {"independent_review": {"review_type": "gsd-code-review", "sha": "c" * 40,
                                          "outcome": "pass", "url": f"https://github.com/{REPOSITORY}/pull/10",
                                          "report": "---\nreviewed_commit: " + "c" * 40 + "\nfindings:\n  critical: 0\n  warning: 0\n  info: 0\n  total: 0\nstatus: clean\n---\n",
                                          "report_sha256": hashlib.sha256(("---\nreviewed_commit: " + "c" * 40 + "\nfindings:\n  critical: 0\n  warning: 0\n  info: 0\n  total: 0\nstatus: clean\n---\n").encode()).hexdigest(),
                                          "findings": []},
                  "independent_security_review": {"review_type": "gsd-security-audit", "sha": "c" * 40,
                                                   "outcome": "pass", "url": f"https://github.com/{REPOSITORY}/pull/10",
                                                   "report": "reviewed_commit: " + "c" * 40 + "\nverdict: SECURED\nthreats_open: 0\n",
                                                   "report_sha256": hashlib.sha256(("reviewed_commit: " + "c" * 40 + "\nverdict: SECURED\nthreats_open: 0\n").encode()).hexdigest()},
                  "publisher_authority": {job: {"schema_version": 1, "outcome": "pass",
                                                 "kind": "effective-token-repository-scope",
                                                 "repository": REPOSITORY, "repository_count": 1,
                                                 "source_revision": "a" * 40, "run_id": "123", "job": job,
                                                 "installation_id": "42",
                                                 "installation_wide_grant": "not inspected"}
                                           for job in ("stage-release", "publish-release")},
                  "required_checks": {"sha": "a" * 40, "outcome": "pass", "strict_current_head": True,
                                      "lane_count": 3, "assertion_count": 1000,
                                      "run_url": f"https://github.com/{REPOSITORY}/actions/runs/124",
                                      "job_url": f"https://github.com/{REPOSITORY}/actions/runs/124/job/988"},
                  "source_event": "push-main", "live_fork_trial": "not-claimed"},
        "platform_evidence": [_valid_evidence(profile, distribution, version)
                              for distribution in ("staged", "published") for profile in PROFILES],
    }
    mapping = receipt["local_publication"]["mapping"]
    receipt["local_publication"]["mapping_sha256"] = digest(mapping)
    receipt["source"]["local_source_mapping_sha256"] = digest(mapping)
    return _seal_receipt_reports(receipt)


def _seal_receipt_reports(receipt: dict[str, object]) -> dict[str, object]:
    source = receipt["source"]
    report = source["public_content_report"]
    report_sha = digest(report)
    source["public_content_report_sha256"] = report_sha
    source["history_scan"]["report_sha256"] = report_sha
    source["rights_scan"]["report_sha256"] = report_sha
    return receipt


def _valid_live_observations(receipt: dict[str, object]) -> dict[str, object]:
    source, release = receipt["source"], receipt["release"]
    run_id, attempt = release["run"]["run_id"], release["run"]["attempt"]
    jobs = [{"id": 999, "name": "publish-release", "html_url": release["run"]["publish_job_url"],
             "status": "completed", "conclusion": "success"}]
    platform_artifacts = {"staged": {}, "published": {}}
    for item in receipt["platform_evidence"]:
        run = item["run"]
        jobs.append({"id": run["job_id"], "name": run["job_name"], "html_url": run["job_url"],
                     "status": "completed", "conclusion": "success"})
        platform_artifacts[item["distribution"]][item["platform"]] = item
    manifest = release["manifest"]
    manifest_bytes = canonical_json(manifest)
    manifest_row = {"name": "release-manifest.json", "size": len(manifest_bytes),
                    "sha256": hashlib.sha256(manifest_bytes).hexdigest()}
    assets = [*manifest["assets"], manifest_row]
    authority = copy.deepcopy(receipt["gates"]["publisher_authority"])
    pr = source["pull_request"]
    ci = receipt["gates"]["required_checks"]
    return {
        "release_run": {"id": run_id, "run_attempt": attempt, "head_sha": source["workflow_commit"],
                        "head_branch": "main", "event": "push", "status": "completed",
                        "conclusion": "success", "path": ".github/workflows/release.yml@refs/heads/main",
                        "repository": {"full_name": REPOSITORY},
                        "html_url": release["run"]["run_url"]},
        "publication_trigger": {"schema_version": 1, "repository": REPOSITORY,
                                 "event": "push", "source_event": "push-main",
                                 "ref": "refs/heads/main", "source_commit": source["commit"],
                                 "workflow_commit": source["workflow_commit"],
                                 "publish_input": None, "publication_expected": True},
        "pull_request": {"number": pr["number"], "html_url": pr["url"], "state": "closed",
                         "merged": True, "merged_at": pr["merged_at"],
                         "base": {"ref": "main"}, "head": {"sha": pr["head_commit"]},
                         "merge_commit_sha": source["commit"]},
        "pull_request_head_commit": {"commit": {"tree": {"sha": pr["tree_sha"]}}},
        "pull_request_merge_commit": {"commit": {"tree": {"sha": pr["tree_sha"]}}},
        "current_main_sha": source["commit"], "tag_commit": source["commit"],
        "release_jobs": jobs, "platform_artifacts": platform_artifacts,
        "public_content_report_artifact": source["public_content_report"],
        "staged_manifest_artifact": manifest, "published_manifest_artifact": manifest,
        "published_release_artifact": {"tag_name": release["tag"], "draft": False, "html_url": release["url"]},
        "release_api": {"tag_name": release["tag"], "draft": False, "html_url": release["url"],
                        "published_at": release["published_at"], "assets": assets},
        "anonymous_release_manifest": manifest, "anonymous_asset_rows": assets,
        "main_protection": {"required_status_checks": {"strict": True, "contexts": ["ci-policy"]},
                            "enforce_admins": {"enabled": True}},
        "ci_run": {"id": int(ci["run_url"].rsplit("/", 1)[1]), "head_sha": source["commit"],
                   "head_branch": "main", "event": "push", "status": "completed",
                   "conclusion": "success", "path": ".github/workflows/ci.yml@refs/heads/main"},
        "ci_policy_job": {"name": "ci-policy", "html_url": ci["job_url"],
                          "status": "completed", "conclusion": "success"},
        "ci_aggregate_artifact": {"source_revision": source["commit"], "outcome": "pass",
                                  "lane_count": ci["lane_count"], "assertion_count": ci["assertion_count"]},
        "publisher_authority": authority,
        "public_source_tree": [{"path": row["path"], "sha": row["public_blob_sha1"],
                                "type": "blob", "mode": row["mode"]}
                               for row in receipt["local_publication"]["mapping"]["rows"]],
        "public_source_archive": [{"path": row["path"], "sha256": row["public_sha256"],
                                   "public_blob_sha1": row["public_blob_sha1"], "mode": row["mode"]}
                                  for row in receipt["local_publication"]["mapping"]["rows"]],
    }


class DeliveryReceiptTests(unittest.TestCase):
    def test_valid_source_bound_delivery_receipt_passes(self) -> None:
        self.assertEqual(validate_receipt(_valid_receipt())["status"], "pass")

    def test_live_receipt_requires_observed_producer_and_exact_merged_tree(self) -> None:
        receipt = _valid_receipt()
        live = _valid_live_observations(receipt)
        self.assertEqual(validate_live_observations(receipt, live)["live_status"], "pass")
        live["pull_request_merge_commit"]["commit"]["tree"]["sha"] = "e" * 40
        with self.assertRaisesRegex(DeliveryContractError, "tree differs"):
            validate_live_observations(receipt, live)
        live = _valid_live_observations(receipt)
        live["publisher_authority"]["publish-release"]["installation_id"] = "84"
        with self.assertRaisesRegex(DeliveryContractError, "authority differs"):
            validate_live_observations(receipt, live)

    def test_public_source_mapping_is_byte_and_live_tree_bound(self) -> None:
        receipt = _valid_receipt()
        mapping = receipt["local_publication"]["mapping"]
        mapping["rows"][0]["public_sha256"] = "6" * 64
        receipt["local_publication"]["mapping_sha256"] = digest(mapping)
        receipt["source"]["local_source_mapping_sha256"] = digest(mapping)
        with self.assertRaisesRegex(DeliveryContractError, "source-byte correspondence"):
            validate_receipt(receipt)
        receipt = _valid_receipt()
        live = _valid_live_observations(receipt)
        live["public_source_tree"][0]["sha"] = "f" * 40
        with self.assertRaisesRegex(DeliveryContractError, "public Git tree"):
            validate_live_observations(receipt, live)
        live = _valid_live_observations(receipt)
        live["public_source_archive"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(DeliveryContractError, "public source archive bytes"):
            validate_live_observations(receipt, live)

    def test_source_archive_hashes_bytes_as_git_blobs(self) -> None:
        content = b"public source bytes\n"
        archive_bytes = io.BytesIO()
        with tarfile.open(fileobj=archive_bytes, mode="w:gz") as archive:
            root = tarfile.TarInfo("glueyneo-source/")
            root.type = tarfile.DIRTYPE
            root.mode = 0o755
            archive.addfile(root)
            member = tarfile.TarInfo("glueyneo-source/README.md")
            member.mode = 0o644
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        with tempfile.TemporaryDirectory(prefix="delivery-source-archive-") as directory:
            path = Path(directory) / "source.tar.gz"
            path.write_bytes(archive_bytes.getvalue())
            rows = _source_archive_observations(path)
        self.assertEqual(rows, [{"path": "README.md",
                                 "sha256": hashlib.sha256(content).hexdigest(),
                                 "public_blob_sha1": hashlib.sha1(
                                     b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest(),
                                 "mode": "100644"}])

    def test_local_source_mapping_reads_immutable_revision_bytes(self) -> None:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                  capture_output=True, text=True, check=True).stdout.strip()
        path = "tests/consumers/test_delivery_contract.py"
        entry = subprocess.run(["git", "ls-tree", "-r", revision, "--", path], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        metadata, observed_path = entry.split("\t", 1)
        mode, kind, blob = metadata.split(" ")
        self.assertEqual((observed_path, kind), (path, "blob"))
        content = subprocess.run(["git", "cat-file", "blob", blob], cwd=ROOT,
                                 capture_output=True, check=True).stdout
        mapping = {"local_revision": revision,
                   "rows": [{"path": path, "mode": mode,
                             "local_sha256": hashlib.sha256(content).hexdigest()}]}
        _verify_local_source_mapping(mapping)
        mapping["rows"][0]["local_sha256"] = "0" * 64
        with self.assertRaisesRegex(DeliveryContractError, "local source bytes"):
            _verify_local_source_mapping(mapping)

    def test_release_manifest_prerelease_version_is_supported(self) -> None:
        receipt = _valid_receipt("0.3.0-rc.1")
        self.assertEqual(validate_receipt(receipt)["version"], "0.3.0-rc.1")

    def test_review_findings_require_resolution_or_disposition_evidence(self) -> None:
        receipt = _valid_receipt()
        receipt["gates"]["independent_review"]["findings"] = [{"status": "dispositioned"}]
        with self.assertRaisesRegex(DeliveryContractError, "clean zero-finding"):
            validate_receipt(receipt)

    def test_review_report_digest_and_pull_request_are_bound(self) -> None:
        receipt = _valid_receipt()
        receipt["gates"]["independent_review"]["url"] = "https://github.com/other/repo/pull/10"
        with self.assertRaisesRegex(DeliveryContractError, "merged source pull request"):
            validate_receipt(receipt)
        receipt = _valid_receipt()
        receipt["gates"]["independent_review"]["report"] += "edited\n"
        with self.assertRaisesRegex(DeliveryContractError, "report bytes do not match"):
            validate_receipt(receipt)

    def test_failing_review_verdicts_cannot_be_attested_as_passing(self) -> None:
        receipt = _valid_receipt()
        review = receipt["gates"]["independent_review"]
        review["report"] = review["report"].replace("status: clean", "status: issues_found")
        review["report_sha256"] = hashlib.sha256(review["report"].encode()).hexdigest()
        with self.assertRaisesRegex(DeliveryContractError, "report is not clean"):
            validate_receipt(receipt)

        receipt = _valid_receipt()
        security = receipt["gates"]["independent_security_review"]
        security["report"] = security["report"].replace("threats_open: 0", "threats_open: 1")
        security["report_sha256"] = hashlib.sha256(security["report"].encode()).hexdigest()
        with self.assertRaisesRegex(DeliveryContractError, "open threats"):
            validate_receipt(receipt)

        receipt = _valid_receipt()
        review = receipt["gates"]["independent_review"]
        review["report"] = review["report"].replace(
            "status: clean\n---\n", "status: clean\nstatus: issues_found\n---\n")
        review["report_sha256"] = hashlib.sha256(review["report"].encode()).hexdigest()
        with self.assertRaisesRegex(DeliveryContractError, "duplicate status"):
            validate_receipt(receipt)

        receipt = _valid_receipt()
        security = receipt["gates"]["independent_security_review"]
        security["report"] += "verdict: OPEN_THREATS\nthreats_open: 1\n"
        security["report_sha256"] = hashlib.sha256(security["report"].encode()).hexdigest()
        with self.assertRaisesRegex(DeliveryContractError, "duplicate verdict"):
            validate_receipt(receipt)

    def test_manual_publication_requires_recorded_publish_true(self) -> None:
        receipt = _valid_receipt()
        receipt["gates"]["source_event"] = "workflow-dispatch-publish"
        live = _valid_live_observations(receipt)
        live["release_run"]["event"] = "workflow_dispatch"
        live["publication_trigger"].update(event="workflow_dispatch",
                                            source_event="workflow-dispatch-publish",
                                            publish_input=True)
        self.assertEqual(validate_live_observations(receipt, live)["live_status"], "pass")
        live["publication_trigger"]["publish_input"] = False
        with self.assertRaisesRegex(DeliveryContractError, "did not record publish=true"):
            validate_live_observations(receipt, live)

        live = _valid_live_observations(_valid_receipt())
        live["publication_trigger"]["workflow_commit"] = "f" * 40
        with self.assertRaisesRegex(DeliveryContractError, "protected-main source"):
            validate_live_observations(_valid_receipt(), live)

    def test_stale_source_and_state_head_substitution_are_rejected(self) -> None:
        receipt = _valid_receipt()
        receipt["platform_evidence"][0]["source_commit"] = "c" * 40
        receipt["platform_evidence"][0]["evidence_sha256"] = digest({k: v for k, v in receipt["platform_evidence"][0].items() if k != "evidence_sha256"})
        with self.assertRaisesRegex(DeliveryContractError, "stale"):
            validate_receipt(receipt)
        receipt = _valid_receipt()
        receipt["source"]["commit"] = receipt["source"]["planning_state_head"]
        receipt["source"]["workflow_commit"] = receipt["source"]["commit"]
        with self.assertRaisesRegex(DeliveryContractError, "planning state"):
            validate_receipt(receipt)

    def test_private_ref_exclusion_and_history_denominator_are_required(self) -> None:
        receipt = _valid_receipt()
        receipt["source"]["publication_refs"].append("refs/heads/private-work")
        with self.assertRaisesRegex(DeliveryContractError, "ref set"):
            validate_receipt(receipt)
        receipt = _valid_receipt()
        receipt["source"]["history_scan"]["bytes_scanned"] = 0
        with self.assertRaisesRegex(DeliveryContractError, "counts differ"):
            validate_receipt(receipt)

    def test_downloaded_examples_require_exact_manifest_and_nonzero_case_membership(self) -> None:
        receipt = _valid_receipt()
        consumer = receipt["platform_evidence"][0]["consumer_result"]
        consumer["cases"].pop()
        receipt["platform_evidence"][0]["consumer_result_sha256"] = digest(consumer)
        receipt["platform_evidence"][0]["evidence_sha256"] = digest({k: v for k, v in receipt["platform_evidence"][0].items() if k != "evidence_sha256"})
        with self.assertRaisesRegex(DeliveryContractError, "case membership"):
            validate_receipt(receipt)
        receipt = _valid_receipt()
        receipt["platform_evidence"][0]["downloaded_assets"][0]["sha256"] = "f" * 64
        receipt["platform_evidence"][0]["evidence_sha256"] = digest({k: v for k, v in receipt["platform_evidence"][0].items() if k != "evidence_sha256"})
        with self.assertRaisesRegex(DeliveryContractError, "differ from the staged manifest"):
            validate_receipt(receipt)

    def test_receipt_rejects_failed_or_unbound_public_content_producer_report(self) -> None:
        receipt = _valid_receipt()
        receipt["source"]["public_content_report"]["outcome"] = "fail"
        _seal_receipt_reports(receipt)
        with self.assertRaisesRegex(DeliveryContractError, "producer report is failed"):
            validate_receipt(receipt)

    def test_untrusted_job_has_no_publish_authority(self) -> None:
        verify = workflow_job("verify-downloaded-release")
        self.assertIn("permissions:\n      contents: read\n      actions: read", verify)
        self.assertNotIn("contents: write", verify)
        self.assertNotIn("secrets.RELEASE_APP_PRIVATE_KEY", verify)
        published = workflow_job("verify-published-release")
        self.assertIn("contents: read", published)
        self.assertNotIn("contents: write", published)
        self.assertNotIn("GH_TOKEN: ${{ steps.app-token.outputs.token }}", published)


class DeliveryWorkflowTests(unittest.TestCase):
    def test_delivery_current_source_is_checked_and_recorded(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for job in ("build-release", "verify-downloaded-release", "verify-published-release"):
            section = workflow_job(job)
            self.assertIn("ref: ${{ needs.release-control.outputs.commit }}", section)
        control = workflow_job("release-control")
        self.assertIn("workflow_commit: ${{ steps.identity.outputs.workflow_commit }}", control)
        publish = workflow_job("publish-release")
        self.assertIn("outputs.commit == needs.release-control.outputs.workflow_commit", publish)
        self.assertIn("WORKFLOW_COMMIT: ${{ needs.release-control.outputs.workflow_commit }}", publish)
        self.assertIn('"workflow_commit": workflow_commit', publish)
        self.assertIn("workflow_commit", (ROOT / "tools/workflow/release_identity.py").read_text(encoding="utf-8"))

    def test_private_ref_exclusion_uses_exact_sanitized_public_revision(self) -> None:
        verify = workflow_job("verify-downloaded-release")
        self.assertIn('--history-revision "$RELEASE_COMMIT"', verify)
        self.assertNotIn("--history-revision HEAD", verify)
        self.assertNotIn("--history-revision --all", verify)

    def test_stale_source_rejected(self) -> None:
        receipt = _valid_receipt()
        receipt["release"]["source_commit"] = "c" * 40
        with self.assertRaisesRegex(DeliveryContractError, "release identity"):
            validate_receipt(receipt)

    def test_state_head_not_source(self) -> None:
        receipt = _valid_receipt()
        receipt["source"]["commit"] = receipt["source"]["planning_state_head"]
        with self.assertRaises(DeliveryContractError):
            validate_receipt(receipt)

    def test_downloaded_examples_required(self) -> None:
        verify = workflow_job("verify-downloaded-release")
        self.assertIn("test_delivery_contract.py --mode platform", verify)
        self.assertIn("consumer-result.json", verify)
        self.assertIn("actions/upload-artifact@", verify)
        published = workflow_job("verify-published-release")
        self.assertIn("--mode public-download", published)
        self.assertIn("_download_public_release(", (ROOT / "tests/consumers/test_delivery_contract.py").read_text(encoding="utf-8"))
        self.assertIn("--distribution published", published)

    def test_untrusted_job_has_no_publish_authority(self) -> None:
        verify = workflow_job("verify-downloaded-release")
        self.assertNotIn("permission-contents: write", verify)
        self.assertNotIn("secrets.", verify)
        self.assertNotIn("steps.app-token.outputs.token", verify)
        published = workflow_job("verify-published-release")
        self.assertNotIn("permission-contents: write", published)
        self.assertNotIn("secrets.", published)
        self.assertNotIn("steps.app-token.outputs.token", published)

    def test_verify_mode_requires_live_git_hub_observations(self) -> None:
        self.assertIn("result = verify_receipt_live(_read_json(args.receipt))",
                      (ROOT / "tests/consumers/test_delivery_contract.py").read_text(encoding="utf-8"))


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DeliveryContractError(f"JSON producer output is missing or malformed: {path}") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("unit", "platform", "public-download", "verify"), required=True)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--consumer-result", type=Path)
    parser.add_argument("--platform")
    parser.add_argument("--distribution", choices=("staged", "published"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--version")
    args = parser.parse_args(argv)
    try:
        if args.mode == "unit":
            suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            return 0 if result.wasSuccessful() else 1
        if args.mode == "verify":
            require(args.receipt is not None, "--receipt is required")
            result = verify_receipt_live(_read_json(args.receipt))
            result["receipt_sha256"] = hashlib.sha256(args.receipt.read_bytes()).hexdigest()
            print(json.dumps(result, sort_keys=True, separators=(",", ":")))
            return 0
        if args.mode == "public-download":
            require(args.directory is not None and args.manifest is not None
                    and args.tag is not None and args.version is not None,
                    "public-download requires --directory, --manifest, --tag and --version")
            require(release_manifest.VERSION_RE.fullmatch(args.version) is not None
                    and args.tag == f"v{args.version}", "public release tag/version is malformed or inconsistent")
            manifest, assets = _download_public_release(args.directory, args.manifest,
                                                        tag=args.tag, version=args.version)
            print(json.dumps({"outcome": "pass", "tag": args.tag,
                              "source_commit": manifest["source_commit"],
                              "asset_count": len(assets)}, sort_keys=True))
            return 0
        require(args.directory is not None and args.manifest is not None and args.consumer_result is not None
                and args.platform is not None and args.distribution is not None and args.output is not None,
                "platform mode requires producer output paths, profile and distribution")
        evidence = create_platform_evidence(directory=args.directory, manifest_path=args.manifest,
                                            consumer_path=args.consumer_result, profile=args.platform,
                                            distribution=args.distribution)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_json(evidence))
        print(json.dumps({"outcome": "pass", "platform": args.platform,
                          "distribution": args.distribution, "evidence_sha256": evidence["evidence_sha256"]},
                         sort_keys=True, separators=(",", ":")))
        return 0
    except (DeliveryContractError, OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"delivery contract rejected: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
