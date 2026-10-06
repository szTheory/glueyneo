#!/usr/bin/env python3
"""Named fail-closed mutation controls for the SDK evidence schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import sdk_evidence as evidence  # noqa: E402


def valid_identity() -> dict[str, Any]:
    identity = {
        "source_revision": "a" * 40,
        "relevant_source_sha256": "b" * 64,
        "working_tree_dirty": False,
        "relevant_source_files": [{"path": "src/sample.c", "sha256": "c" * 64, "bytes": 10}],
        "owned_backend_sha256": "d" * 64,
        "unity_pin": evidence.UNITY_PIN,
        "unity_files": [{"path": path, "sha256": digest} for path, digest in sorted(evidence.UNITY_FILES.items())],
        "fixture_manifest_sha256": "e" * 64,
        "fixture_sha256": "f" * 64,
        "expected_output_sha256": "0" * 64,
        "runtime_artifacts": [{"path": "libglueyneo.a", "sha256": "1" * 64}],
        "compiler": {"id": "TestCC", "version": "1.0", "path_basename": "cc"},
        "cmake": "cmake version 1.0",
        "generator": {"name": "Ninja", "version": "1.0"},
        "sdk": {"status": "unknown", "version": "unknown"},
        "os": "TestOS-1",
        "architecture": "test64",
        "configuration": "Debug",
        "build_flags": {"c_flags": "", "configuration_c_flags": "", "shared_libraries": "OFF", "sdk_sanitizer": "NONE"},
        "host_class": "TestOS-test64",
    }
    identity["relevant_source_sha256"] = evidence.sha256_bytes(
        evidence.canonical_bytes(identity["relevant_source_files"]))
    return identity


def valid_record() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "suite": "control",
        "outcome": "pass",
        "command": "python3 tools/verify_sdk.py --suite evidence",
        "identity": valid_identity(),
        "case_count": 1,
        "assertion_count": 2,
        "cases": [{"case_id": "control.valid", "outcome": "pass", "assertions": 2,
                   "expected": {"value": 1}, "observed": {"value": 1}}],
        "failure_history": [],
        "retained_failures": [],
    }


def expect_rejection(name: str, action: Callable[[], Any], expected_reason: str) -> dict[str, Any]:
    try:
        action()
    except evidence.EvidenceError as error:
        if error.reason != expected_reason:
            raise AssertionError(f"{name}: expected {expected_reason}, observed {error.reason}") from error
        return {"case_id": name, "outcome": "pass", "assertions": 2,
                "expected": expected_reason, "observed": error.reason}
    raise AssertionError(f"{name}: malformed evidence was accepted")


def cases() -> dict[str, Callable[[], dict[str, Any]]]:
    def missing_identity() -> dict[str, Any]:
        record = valid_record()
        record["identity"].pop("compiler")
        return expect_rejection("evidence.missing-identity", lambda: evidence.validate_case_record(record), "identity-missing")

    def malformed() -> dict[str, Any]:
        return expect_rejection("evidence.malformed-truncated", lambda: evidence.load_canonical_json(b'{"schema_version":1', label="control"), "malformed-json")

    def duplicate_key() -> dict[str, Any]:
        return expect_rejection("evidence.duplicate-key", lambda: evidence.load_canonical_json(b'{"a":1,"a":2}\n', label="control"), "duplicate-key")

    def zero_count() -> dict[str, Any]:
        record = valid_record()
        record["cases"] = []
        record["case_count"] = 0
        record["assertion_count"] = 0
        return expect_rejection("evidence.zero-cases", lambda: evidence.validate_case_record(record), "zero-cases")

    def stale_identity() -> dict[str, Any]:
        record = valid_record()
        wanted = valid_identity()
        wanted["source_revision"] = "9" * 40
        return expect_rejection("evidence.stale-source", lambda: evidence.validate_case_record(record, wanted), "identity-mismatch")

    def mismatched_config() -> dict[str, Any]:
        record = valid_record()
        wanted = valid_identity()
        wanted["configuration"] = "Release"
        return expect_rejection("evidence.config-mismatch", lambda: evidence.validate_case_record(record, wanted), "identity-mismatch")

    def duplicate_identity() -> dict[str, Any]:
        record = valid_record()
        record["identity"]["relevant_source_files"].append(dict(record["identity"]["relevant_source_files"][0]))
        return expect_rejection("evidence.duplicate-identity-row", lambda: evidence.validate_case_record(record), "duplicate-identity-row")

    def duplicate_case() -> dict[str, Any]:
        record = valid_record()
        record["cases"].append(dict(record["cases"][0]))
        record["case_count"] = 2
        record["assertion_count"] = 4
        return expect_rejection("evidence.duplicate-case", lambda: evidence.validate_case_record(record), "duplicate-case")

    def noncanonical_order() -> dict[str, Any]:
        record = valid_record()
        record["cases"] = [
            {"case_id": "z", "outcome": "pass", "assertions": 1, "expected": 1, "observed": 1},
            {"case_id": "a", "outcome": "pass", "assertions": 1, "expected": 1, "observed": 1},
        ]
        record["case_count"] = 2
        record["assertion_count"] = 2
        return expect_rejection("evidence.noncanonical-case-order", lambda: evidence.validate_case_record(record), "case-order")

    def noncanonical_json() -> dict[str, Any]:
        return expect_rejection("evidence.noncanonical-json-order", lambda: evidence.load_canonical_json(b'{"z":1,"a":2}\n', label="control"), "noncanonical-json")

    def privacy_contamination() -> dict[str, Any]:
        record = valid_record()
        record["cases"][0]["observed"] = "/Users/private-person/output.bin"
        record["cases"][0]["expected"] = "/Users/private-person/output.bin"
        return expect_rejection("evidence.private-path", lambda: evidence.validate_case_record(record), "privacy-contamination")

    def erased_failure() -> dict[str, Any]:
        record = valid_record()
        record["failure_history"] = [{"case_id": "control.failed-before-repair", "outcome": "fail"}]
        return expect_rejection("evidence.erased-failure", lambda: evidence.validate_case_record(record), "erased-failure")

    def spoofed_outcome() -> dict[str, Any]:
        record = valid_record()
        record["cases"][0]["outcome"] = "fail"
        return expect_rejection("evidence.spoofed-pass", lambda: evidence.validate_case_record(record), "outcome-mismatch")

    def mixed_artifacts() -> dict[str, Any]:
        record = valid_record()
        record["identity"]["runtime_artifacts"].append({"path": "foreign-runtime.a", "sha256": "2" * 64})
        record["identity"]["runtime_artifacts"].sort(key=lambda row: row["path"])
        return expect_rejection("evidence.mixed-foreign-artifact", lambda: evidence.validate_case_record(record, valid_identity()), "identity-mismatch")

    def empty_manifest() -> dict[str, Any]:
        manifest = json.loads((ROOT / evidence.MANIFEST_PATH).read_text(encoding="utf-8"))
        manifest["fixtures"] = []
        return expect_rejection("evidence.empty-manifest", lambda: evidence.validate_manifest_document(manifest), "manifest-empty")

    def empty_ancestry() -> dict[str, Any]:
        manifest = json.loads((ROOT / evidence.MANIFEST_PATH).read_text(encoding="utf-8"))
        manifest["oracle"]["ancestry"] = []
        return expect_rejection("evidence.empty-oracle-ancestry", lambda: evidence.validate_manifest_document(manifest), "manifest-ancestry")

    def stale_manifest_source() -> dict[str, Any]:
        manifest = json.loads((ROOT / evidence.MANIFEST_PATH).read_text(encoding="utf-8"))
        manifest["source_inputs"][0]["sha256"] = "2" * 64
        return expect_rejection("evidence.stale-manifest-source", lambda: evidence.verify_manifest(ROOT, manifest_data=manifest), "manifest-source-mismatch")

    def unknown_outcome() -> dict[str, Any]:
        record = valid_record()
        record["outcome"] = "pending"
        return expect_rejection("evidence.unknown-outcome", lambda: evidence.validate_case_record(record), "outcome-unknown")

    return {
        "missing_identity": missing_identity,
        "malformed": malformed,
        "duplicate_key": duplicate_key,
        "zero_count": zero_count,
        "stale_identity": stale_identity,
        "mismatched_config": mismatched_config,
        "duplicate_identity": duplicate_identity,
        "duplicate_case": duplicate_case,
        "noncanonical_order": noncanonical_order,
        "noncanonical_json": noncanonical_json,
        "privacy_contamination": privacy_contamination,
        "erased_failure": erased_failure,
        "spoofed_outcome": spoofed_outcome,
        "mixed_artifacts": mixed_artifacts,
        "empty_manifest": empty_manifest,
        "empty_ancestry": empty_ancestry,
        "stale_manifest_source": stale_manifest_source,
        "unknown_outcome": unknown_outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", choices=sorted(cases()))
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()
    selected = cases()
    try:
        names = list(selected) if args.all else [args.case]
        results = []
        assertions = 0
        for name in names:
            row = selected[name]()
            assertions += row["assertions"]
            results.append(row)
            print("SDK_EVIDENCE_CASE " + json.dumps(row, sort_keys=True))
        print("SDK_EVIDENCE_RESULT " + json.dumps({"schema_version": 1, "outcome": "pass",
              "cases": len(results), "assertions": assertions}, sort_keys=True))
    except (AssertionError, evidence.EvidenceError) as error:
        print("SDK_EVIDENCE_RESULT " + json.dumps({"schema_version": 1, "outcome": "fail",
              "reason": getattr(error, "reason", "control-failed")}, sort_keys=True), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
