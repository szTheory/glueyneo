#!/usr/bin/env python3
"""Named fail-closed mutation controls for the SDK evidence schema."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import sdk_evidence as evidence  # noqa: E402
import verify_sdk as verifier  # noqa: E402


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


def valid_baseline_record() -> dict[str, Any]:
    identity = valid_identity()
    identity["configuration"] = "Release"
    identity["build_flags"]["configuration_c_flags"] = "-O3 -DNDEBUG"
    load = [100 + index for index in range(31)]
    load_batches = [value * evidence.BASELINE_EXECUTION_RUNS_PER_SAMPLE for value in load]
    execution = [40 + index for index in range(31)]
    execution_batches = [value * evidence.BASELINE_EXECUTION_RUNS_PER_SAMPLE
                        for value in execution]
    cold = [1_000_000, 1_100_000, 1_200_000]
    memory_samples = [{"allocations": 5, "bytes": 5000, "attempts": 5} for _ in load]
    return {
        "schema_version": evidence.BASELINE_SCHEMA_VERSION,
        "suite": "baseline",
        "outcome": "pass",
        "command": "python3 tools/verify_sdk.py --suite baseline",
        "identity": identity,
        "workload": {
            "workload_id": evidence.BASELINE_WORKLOAD_ID,
            "configuration": "Release",
            "input_sha256": evidence.BASELINE_INPUT_SHA256,
            "output_sha256": evidence.BASELINE_OUTPUT_SHA256,
            "expected_output": dict(evidence.BASELINE_EXPECTED_OUTPUT),
            "observed_output": dict(evidence.BASELINE_EXPECTED_OUTPUT),
            "observed_output_sha256": evidence.baseline_output_sha256(
                evidence.BASELINE_EXPECTED_OUTPUT),
            "guest_cycles": 172,
        },
        "protocol": {"warmup_samples": 3, "retained_samples": 31,
                     "load_runs_per_sample": evidence.BASELINE_EXECUTION_RUNS_PER_SAMPLE,
                     "execution_runs_per_sample": evidence.BASELINE_EXECUTION_RUNS_PER_SAMPLE,
                     "cold_build_configuration": {
                         "build_type": "Release", "generator": "Ninja",
                         "BUILD_TESTING": False, "GLUEYNEO_BUILD_TESTS": False,
                         "GLUEYNEO_SDK_SANITIZER": "NONE",
                         "GLUEYNEO_CPU_EXPERIMENT": False,
                         "GLUEYNEO_OWNED_CPU_EXPERIMENT": False,
                     },
                     "cold_build_ids": ["cold-1", "cold-2", "cold-3"]},
        "raw_samples": {"load_ns": load, "load_batch_ns": load_batches,
                        "execution_ns": execution,
                        "execution_batch_ns": execution_batches,
                        "cold_build_ns": cold},
        "timer": {"clock": "CLOCK_MONOTONIC", "resolution_ns": 1},
        "summaries": {"load_ns": evidence._sample_summary(load),
                      "load_batch_ns": evidence._sample_summary(load_batches),
                      "execution_ns": evidence._sample_summary(execution),
                      "execution_batch_ns": evidence._sample_summary(execution_batches),
                      "cold_build_ns": evidence._sample_summary(cold)},
        "discarded_samples": [],
        "memory": {"status": "measured", "allocator": "gn_test_allocator",
                   "scope": "successful first load plus exact diagnostic run",
                   "current_allocations": 5, "current_bytes": 5000,
                   "peak_allocations": 5, "peak_bytes": 5000,
                   "samples": memory_samples},
        "host_rss": {"status": "unsupported", "reason": "process RSS was not measured"},
        "measurement_tool": {"source_sha256": "a" * 64,
                             "binary_sha256": "b" * 64,
                             "compiler": identity["compiler"]},
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


def expect_rejections(name: str, actions: list[tuple[str, Callable[[], Any]]],
                      expected_reason: str) -> dict[str, Any]:
    if not actions:
        raise AssertionError(f"{name}: no malformed-row vectors were exercised")
    for suffix, action in actions:
        expect_rejection(f"{name}.{suffix}", action, expected_reason)
    return {"case_id": name, "outcome": "pass", "assertions": len(actions) * 2,
            "expected": expected_reason, "observed": expected_reason}


def row_shape_actions(name: str, invoke: Callable[[list[Any]], Any],
                      valid_rows: list[dict[str, Any]]) -> list[tuple[str, Callable[[], Any]]]:
    non_objects = [("null", None), ("array", []), ("string", "row"),
                   ("integer", 1), ("fraction", 1.5), ("boolean", True)]
    actions: list[tuple[str, Callable[[], Any]]] = []
    for kind, value in non_objects:
        actions.append((f"singleton-{kind}",
                        lambda value=value: invoke([value])))
        actions.append((f"homogeneous-{kind}",
                        lambda value=value: invoke([value, value])))
        for position, label in ((0, "first"), (1, "middle"), (2, "last")):
            def invoke_mixed(position: int = position, value: Any = value) -> Any:
                rows = [dict(row) for row in valid_rows]
                rows[position] = value
                return invoke(rows)
            actions.append((f"mixed-{kind}-{label}", invoke_mixed))
    return actions


def cases() -> dict[str, Callable[[], dict[str, Any]]]:
    def legacy_identity_without_importer() -> dict[str, Any]:
        record = valid_record()
        assert "mvs_importer" not in record["identity"]
        evidence.validate_case_record(record)
        return {"case_id": "evidence.legacy-identity-without-mvs-importer",
                "outcome": "pass", "assertions": 2,
                "expected": "legacy non-MVS identity remains valid",
                "observed": "identity accepted without optional MVS proof"}

    def stale_mvs_importer_source() -> dict[str, Any]:
        record = valid_record()
        identity = record["identity"]
        source_rows = [{"path": path, "sha256": "a" * 64, "bytes": 1}
                       for path in evidence.MVS_IMPORTER_SOURCE_FILES]
        identity_rows = sorted(identity["relevant_source_files"] + source_rows,
                               key=lambda row: row["path"])
        identity["relevant_source_files"] = identity_rows
        identity["relevant_source_sha256"] = evidence.sha256_bytes(
            evidence.canonical_bytes(identity_rows))
        identity["mvs_importer"] = {
            "basename": "mvs_importer", "sha256": "b" * 64,
            "source_files": source_rows, "source_sha256": "c" * 64,
            "working_tree_dirty": False,
        }
        return expect_rejection(
            "evidence.stale-mvs-importer-source",
            lambda: evidence.validate_case_record(record),
            "importer-identity-mismatch")

    def mvs_diagnostic_sources_in_closure() -> dict[str, Any]:
        expected = {
            "src/instance.c", "src/sdk_private.h", "src/mvs/mvs_bus.c",
            "tools/mvs/mvs_qualify.c", "tools/mvs/qualify_local_boot.py",
            "tests/support/portable_stdio.h",
            "tests/mvs/test_mvs.c", "tests/mvs/test_mvs_qualification.py",
            "tests/mvs/qualification_failure_driver.c",
            "src/chips/ym2610_candidate.cpp", "src/chips/ym2610_candidate.h",
            "third_party/ymfm/src/ymfm_opn.cpp", "third_party/ymfm/NOTICE.md",
        }
        missing = expected - set(evidence.MVS_IMPORTER_SOURCE_FILES)
        if missing:
            raise AssertionError("MVS diagnostic sources omitted from identity closure")
        return {"case_id": "evidence.mvs-diagnostic-source-closure",
                "outcome": "pass", "assertions": len(expected),
                "expected": len(expected), "observed": len(expected)}

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

    def row_shape_matrix_aggregator() -> dict[str, Any]:
        valid_rows = [{"lane": f"lane-{index}", "source_revision": "a" * 40,
                       "duration_seconds": 1.0, "runner_minutes": 1.0 / 60,
                       "cold_build_seconds": 1.0} for index in range(3)]
        case_id = "evidence.row-shape-matrix-aggregator"
        container_values = [("null", None), ("object", {}), ("string", "rows"),
                            ("integer", 1), ("fraction", 1.5), ("boolean", True)]
        container_actions = [(name, lambda value=value: evidence.build_matrix_report(value))
                             for name, value in container_values]
        containers = expect_rejections(f"{case_id}.containers", container_actions,
                                       "matrix-lanes-missing")
        row_actions = row_shape_actions(
            case_id, evidence.build_matrix_report,
            [{"lane": f"lane-{index}", "source_revision": "a" * 40,
              "duration_seconds": 1.0, "runner_minutes": 1.0 / 60,
              "cold_build_seconds": 1.0} for index in range(3)])
        rows = expect_rejections(f"{case_id}.rows", row_actions, "matrix-lane-malformed")
        empty = expect_rejection(f"{case_id}.empty-list", lambda: evidence.build_matrix_report([]),
                                 "matrix-revision-missing")
        one_lane = {"lane": evidence.REQUIRED_MATRIX_LANES[0],
                    "source_revision": "a" * 40, "duration_seconds": 1.0,
                    "runner_minutes": 1.0 / 60, "cold_build_seconds": 1.0}
        singleton = expect_rejection(f"{case_id}.singleton-list",
                                     lambda: evidence.build_matrix_report([one_lane]),
                                     "matrix-missing-lane")
        return {"case_id": case_id, "outcome": "pass",
                "assertions": containers["assertions"] + rows["assertions"] +
                              empty["assertions"] + singleton["assertions"],
                "expected": {"container": "matrix-lanes-missing",
                             "row": "matrix-lane-malformed",
                             "empty": "matrix-revision-missing",
                             "singleton": "matrix-missing-lane"},
                "observed": {"container": "matrix-lanes-missing",
                             "row": "matrix-lane-malformed",
                             "empty": "matrix-revision-missing",
                             "singleton": "matrix-missing-lane"}}

    def row_shape_identity_source() -> dict[str, Any]:
        case_id = "evidence.row-shape-identity-source"
        valid_rows = [{"path": f"src/source-{index}.c", "sha256": str(index) * 64,
                       "bytes": index + 1} for index in range(3)]
        def validate_rows(rows: list[Any]) -> None:
            identity = valid_identity()
            identity["relevant_source_files"] = rows
            evidence.validate_identity(identity)
        result = expect_rejections(
            case_id, row_shape_actions(case_id, validate_rows, valid_rows), "identity-malformed")
        evidence.validate_identity(valid_identity())
        empty = expect_rejection(f"{case_id}.empty-list", lambda: validate_rows([]), "identity-order")
        unsorted = expect_rejection(f"{case_id}.unsorted-list",
                                    lambda: validate_rows(list(reversed(valid_rows))), "identity-order")
        duplicate_rows = [dict(valid_rows[0]), dict(valid_rows[0])]
        duplicate = expect_rejection(f"{case_id}.duplicate-list",
                                     lambda: validate_rows(duplicate_rows), "duplicate-identity-row")
        result["case_id"] = case_id
        result["assertions"] += 2 + empty["assertions"] + unsorted["assertions"] + duplicate["assertions"]
        result["expected"] = {"row": "identity-malformed", "empty": "identity-order",
                              "unsorted": "identity-order", "duplicate": "duplicate-identity-row"}
        result["observed"] = dict(result["expected"])
        return result

    def row_shape_identity_unity() -> dict[str, Any]:
        case_id = "evidence.row-shape-identity-unity"
        valid_rows = [{"path": f"unity-{index}.c", "sha256": str(index) * 64}
                      for index in range(3)]
        def validate_rows(rows: list[Any]) -> None:
            identity = valid_identity()
            identity["unity_files"] = rows
            evidence.validate_identity(identity)
        result = expect_rejections(
            case_id, row_shape_actions(case_id, validate_rows, valid_rows), "identity-malformed")
        evidence.validate_identity(valid_identity())
        empty = expect_rejection(f"{case_id}.empty-list", lambda: validate_rows([]), "identity-mismatch")
        unsorted = expect_rejection(f"{case_id}.unsorted-list",
                                    lambda: validate_rows([valid_rows[2], valid_rows[0]]),
                                    "identity-order")
        result["case_id"] = case_id
        result["assertions"] += 2 + empty["assertions"] + unsorted["assertions"]
        result["expected"] = {"row": "identity-malformed", "empty": "identity-mismatch",
                              "unsorted": "identity-order"}
        result["observed"] = dict(result["expected"])
        return result

    def row_shape_identity_artifact() -> dict[str, Any]:
        case_id = "evidence.row-shape-identity-artifact"
        valid_rows = [{"path": f"libsample-{index}.a", "sha256": str(index) * 64}
                      for index in range(3)]
        def validate_rows(rows: list[Any]) -> None:
            identity = valid_identity()
            identity["runtime_artifacts"] = rows
            evidence.validate_identity(identity)
        result = expect_rejections(
            case_id, row_shape_actions(case_id, validate_rows, valid_rows), "identity-malformed")
        evidence.validate_identity(valid_identity())
        empty = expect_rejection(f"{case_id}.empty-list", lambda: validate_rows([]), "identity-order")
        unsorted = expect_rejection(f"{case_id}.unsorted-list",
                                    lambda: validate_rows([valid_rows[2], valid_rows[0]]),
                                    "identity-order")
        duplicate_rows = [dict(valid_rows[0]), dict(valid_rows[0])]
        duplicate = expect_rejection(f"{case_id}.duplicate-list",
                                     lambda: validate_rows(duplicate_rows), "duplicate-identity-row")
        result["case_id"] = case_id
        result["assertions"] += 2 + empty["assertions"] + unsorted["assertions"] + duplicate["assertions"]
        result["expected"] = {"row": "identity-malformed", "empty": "identity-order",
                              "unsorted": "identity-order", "duplicate": "duplicate-identity-row"}
        result["observed"] = dict(result["expected"])
        return result

    def row_shape_importer_source() -> dict[str, Any]:
        case_id = "evidence.row-shape-importer-source"
        valid_rows = [{"path": path, "sha256": f"{index + 1:064x}", "bytes": index + 1}
                      for index, path in enumerate(evidence.MVS_IMPORTER_SOURCE_FILES)]
        importer = {"basename": "mvs_importer", "sha256": "b" * 64,
                    "source_files": valid_rows,
                    "source_sha256": evidence.sha256_bytes(evidence.canonical_bytes(valid_rows)),
                    "working_tree_dirty": False}
        source_result = expect_rejections(
            f"{case_id}.source-files",
            row_shape_actions(case_id, lambda rows: evidence.validate_mvs_importer_identity(
                {**importer, "source_files": rows}, valid_rows),
                [{"path": f"source-{index}.c", "sha256": "c" * 64, "bytes": 1}
                 for index in range(3)]),
            "importer-identity-malformed")
        relevant_result = expect_rejections(
            f"{case_id}.relevant-rows",
            row_shape_actions(case_id, lambda rows: evidence.validate_mvs_importer_identity(
                importer, rows),
                [{"path": f"relevant-{index}.c", "sha256": "d" * 64, "bytes": 1}
                 for index in range(3)]),
            "identity-malformed")
        evidence.validate_mvs_importer_identity(importer, valid_rows)
        empty = expect_rejection(f"{case_id}.empty-source-files",
                                 lambda: evidence.validate_mvs_importer_identity(
                                     {**importer, "source_files": []}, valid_rows),
                                 "importer-identity-order")
        unsorted_rows = list(reversed(valid_rows))
        unsorted = expect_rejection(f"{case_id}.unsorted-source-files",
                                    lambda: evidence.validate_mvs_importer_identity(
                                        {**importer, "source_files": unsorted_rows}, valid_rows),
                                    "importer-identity-order")
        duplicate_rows = sorted([*valid_rows, dict(valid_rows[0])], key=lambda row: row["path"])
        duplicate = expect_rejection(f"{case_id}.duplicate-source-files",
                                     lambda: evidence.validate_mvs_importer_identity(
                                         {**importer, "source_files": duplicate_rows}, valid_rows),
                                     "duplicate-identity-row")
        return {"case_id": case_id, "outcome": "pass",
                "assertions": source_result["assertions"] + relevant_result["assertions"] +
                              2 + empty["assertions"] + unsorted["assertions"] +
                              duplicate["assertions"],
                "expected": {"source_files": "importer-identity-malformed",
                             "relevant_rows": "identity-malformed",
                             "empty": "importer-identity-order",
                             "unsorted": "importer-identity-order",
                             "duplicate": "duplicate-identity-row"},
                "observed": {"source_files": "importer-identity-malformed",
                             "relevant_rows": "identity-malformed",
                             "empty": "importer-identity-order",
                             "unsorted": "importer-identity-order",
                             "duplicate": "duplicate-identity-row"}}

    def row_shape_manifest_source() -> dict[str, Any]:
        case_id = "evidence.row-shape-manifest-source"
        original = evidence.load_canonical_json(
            (ROOT / evidence.MANIFEST_PATH).read_bytes(), label="fixture manifest")
        valid_rows = original["source_inputs"]
        def validate_rows(rows: list[Any]) -> None:
            manifest = copy.deepcopy(original)
            manifest["source_inputs"] = rows
            evidence.validate_manifest_document(manifest)
        row_result = expect_rejections(
            case_id, row_shape_actions(case_id, validate_rows, valid_rows), "manifest-identity")
        evidence.validate_manifest_document(copy.deepcopy(original))
        cardinalities = []
        for label, rows, reason in (
                ("empty", [], "manifest-empty"),
                ("singleton", valid_rows[:1], "manifest-identity"),
                ("minus-one", valid_rows[:-1], "manifest-identity"),
                ("plus-one", [*valid_rows, dict(valid_rows[-1])], "manifest-identity")):
            cardinalities.append(expect_rejection(
                f"{case_id}.{label}", lambda rows=rows: validate_rows(rows), reason))
        unsorted = expect_rejection(
            f"{case_id}.unsorted", lambda: validate_rows(list(reversed(valid_rows))),
            "manifest-empty")
        duplicate_rows = [dict(valid_rows[0]), dict(valid_rows[0]), dict(valid_rows[2])]
        duplicate_rows.sort(key=lambda row: row["path"])
        duplicate = expect_rejection(
            f"{case_id}.duplicate", lambda: validate_rows(duplicate_rows), "manifest-identity")
        return {"case_id": case_id, "outcome": "pass",
                "assertions": row_result["assertions"] +
                              sum(row["assertions"] for row in cardinalities) +
                              unsorted["assertions"] + duplicate["assertions"] + 2,
                "expected": {"row": "manifest-identity", "empty": "manifest-empty",
                             "singleton": "manifest-identity", "minus_one": "manifest-identity",
                             "plus_one": "manifest-identity", "unsorted": "manifest-empty",
                             "duplicate": "manifest-identity"},
                "observed": {"row": "manifest-identity", "empty": "manifest-empty",
                             "singleton": "manifest-identity", "minus_one": "manifest-identity",
                             "plus_one": "manifest-identity", "unsorted": "manifest-empty",
                             "duplicate": "manifest-identity"}}

    def row_shape_manifest_dependency() -> dict[str, Any]:
        case_id = "evidence.row-shape-manifest-dependency"
        original = evidence.load_canonical_json(
            (ROOT / evidence.MANIFEST_PATH).read_bytes(), label="fixture manifest")
        dependency = original["dependencies"][0]
        def validate_rows(rows: list[Any]) -> None:
            manifest = copy.deepcopy(original)
            manifest["dependencies"] = rows
            evidence.validate_manifest_document(manifest)
        row_result = expect_rejections(
            case_id, row_shape_actions(case_id, validate_rows,
                                       [copy.deepcopy(dependency) for _ in range(3)]),
            "manifest-dependency")
        evidence.validate_manifest_document(copy.deepcopy(original))
        cardinality = expect_rejection(
            f"{case_id}.empty", lambda: validate_rows([]), "manifest-dependency")
        plus_one = expect_rejection(
            f"{case_id}.plus-one",
            lambda: validate_rows([copy.deepcopy(dependency), copy.deepcopy(dependency)]),
            "manifest-dependency")
        return {"case_id": case_id, "outcome": "pass",
                "assertions": row_result["assertions"] + cardinality["assertions"] +
                              plus_one["assertions"] + 2,
                "expected": {"row": "manifest-dependency", "empty": "manifest-dependency",
                             "plus_one": "manifest-dependency"},
                "observed": {"row": "manifest-dependency", "empty": "manifest-dependency",
                             "plus_one": "manifest-dependency"}}

    def row_shape_manifest_dependency_file() -> dict[str, Any]:
        case_id = "evidence.row-shape-manifest-dependency-file"
        original = evidence.load_canonical_json(
            (ROOT / evidence.MANIFEST_PATH).read_bytes(), label="fixture manifest")
        valid_rows = original["dependencies"][0]["files"]
        def validate_rows(rows: list[Any]) -> None:
            manifest = copy.deepcopy(original)
            manifest["dependencies"][0]["files"] = rows
            evidence.validate_manifest_document(manifest)
        row_result = expect_rejections(
            case_id, row_shape_actions(case_id, validate_rows, valid_rows[:3]),
            "manifest-dependency")
        evidence.validate_manifest_document(copy.deepcopy(original))
        empty = expect_rejection(f"{case_id}.empty", lambda: validate_rows([]),
                                 "manifest-dependency")
        singleton = expect_rejection(f"{case_id}.singleton",
                                     lambda: validate_rows(valid_rows[:1]),
                                     "manifest-dependency")
        minus_one = expect_rejection(f"{case_id}.minus-one",
                                     lambda: validate_rows(valid_rows[:-1]),
                                     "manifest-dependency")
        duplicate_rows = sorted([*valid_rows, dict(valid_rows[0])],
                                key=lambda row: row["path"])
        duplicate = expect_rejection(f"{case_id}.duplicate",
                                     lambda: validate_rows(duplicate_rows),
                                     "manifest-dependency")
        unsorted = expect_rejection(f"{case_id}.unsorted",
                                    lambda: validate_rows(list(reversed(valid_rows))),
                                    "manifest-order")
        return {"case_id": case_id, "outcome": "pass",
                "assertions": row_result["assertions"] + sum(
                    row["assertions"] for row in (empty, singleton, minus_one, duplicate, unsorted)) + 2,
                "expected": {"row": "manifest-dependency", "empty": "manifest-dependency",
                             "singleton": "manifest-dependency", "minus_one": "manifest-dependency",
                             "duplicate": "manifest-dependency", "unsorted": "manifest-order"},
                "observed": {"row": "manifest-dependency", "empty": "manifest-dependency",
                             "singleton": "manifest-dependency", "minus_one": "manifest-dependency",
                             "duplicate": "manifest-dependency", "unsorted": "manifest-order"}}

    def row_shape_manifest_fixture() -> dict[str, Any]:
        case_id = "evidence.row-shape-manifest-fixture"
        original = evidence.load_canonical_json(
            (ROOT / evidence.MANIFEST_PATH).read_bytes(), label="fixture manifest")
        valid_rows = original["fixtures"]
        def validate_rows(rows: list[Any]) -> None:
            manifest = copy.deepcopy(original)
            manifest["fixtures"] = rows
            evidence.validate_manifest_document(manifest)
        row_result = expect_rejections(
            case_id, row_shape_actions(case_id, validate_rows,
                                       [copy.deepcopy(valid_rows[0]) for _ in range(3)]),
            "manifest-fixture")
        evidence.validate_manifest_document(copy.deepcopy(original))
        empty = expect_rejection(f"{case_id}.empty", lambda: validate_rows([]), "manifest-empty")
        singleton = expect_rejection(f"{case_id}.singleton",
                                     lambda: validate_rows(valid_rows[:1]), "manifest-order")
        plus_one = expect_rejection(
            f"{case_id}.plus-one", lambda: validate_rows([*valid_rows, copy.deepcopy(valid_rows[0])]),
            "manifest-order")
        unsorted = expect_rejection(f"{case_id}.unsorted",
                                    lambda: validate_rows(list(reversed(valid_rows))),
                                    "manifest-order")
        return {"case_id": case_id, "outcome": "pass",
                "assertions": row_result["assertions"] + sum(
                    row["assertions"] for row in (empty, singleton, plus_one, unsorted)) + 2,
                "expected": {"row": "manifest-fixture", "empty": "manifest-empty",
                             "singleton": "manifest-order", "plus_one": "manifest-order",
                             "unsorted": "manifest-order"},
                "observed": {"row": "manifest-fixture", "empty": "manifest-empty",
                             "singleton": "manifest-order", "plus_one": "manifest-order",
                             "unsorted": "manifest-order"}}

    def manifest_source_size_precision() -> dict[str, Any]:
        case_id = "evidence.manifest-source-size-precision"
        original = evidence.load_canonical_json(
            (ROOT / evidence.MANIFEST_PATH).read_bytes(), label="fixture manifest")
        sizes = [1, (1 << 53) - 1, 1 << 53, (1 << 53) + 1, (1 << 53) + 2]
        canonical_rows = []
        for size in sizes:
            manifest = copy.deepcopy(original)
            manifest["source_inputs"][0]["bytes"] = size
            evidence.validate_manifest_document(manifest)
            encoded = evidence.canonical_bytes(manifest)
            decoded = evidence.load_canonical_json(encoded, label="precision manifest")
            observed = decoded["source_inputs"][0]["bytes"]
            if type(observed) is not int or observed != size:
                raise AssertionError(f"source size precision changed: expected {size}, observed {observed!r}")
            if evidence.canonical_bytes(decoded) != encoded:
                raise AssertionError(f"source size canonical encoding changed at {size}")
            canonical_rows.append({"size": size, "sha256": evidence.sha256_bytes(encoded)})
        invalid = []
        invalid_sizes = (("zero", 0), ("negative", -1),
                         ("boolean", True), ("fraction", 1.5))
        for label, size in invalid_sizes:
            manifest = copy.deepcopy(original)
            manifest["source_inputs"][0]["bytes"] = size
            invalid.append(expect_rejection(
                f"{case_id}.{label}", lambda manifest=manifest: evidence.validate_manifest_document(manifest),
                "manifest-identity"))
        return {"case_id": case_id, "outcome": "pass",
                "assertions": len(sizes) * 2 + sum(row["assertions"] for row in invalid),
                "expected": {"positive_sizes": sizes,
                             "non_positive_or_non_integer": "manifest-identity"},
                "observed": {"positive_sizes": [row["size"] for row in canonical_rows],
                             "canonical_digests": [row["sha256"] for row in canonical_rows],
                             "non_positive_or_non_integer": "manifest-identity"}}

    def canonical_preservation() -> dict[str, Any]:
        manifest_path = ROOT / evidence.MANIFEST_PATH
        frozen_path = ROOT / "evidence/sdk/verification.json"
        manifest_bytes = manifest_path.read_bytes()
        frozen_bytes = frozen_path.read_bytes()
        frozen_digest = evidence.sha256_bytes(frozen_bytes)
        if frozen_digest != "a36b2885cd506c1692def371bb930f0f48485ba2d4dcb1d4435948c66625e9cf":
            raise AssertionError("frozen SDK receipt bytes changed")
        manifest = evidence.load_canonical_json(manifest_bytes, label="fixture manifest")
        canonical_before = evidence.canonical_bytes(manifest)
        if canonical_before != manifest_bytes:
            raise AssertionError("valid manifest is not in its existing canonical byte representation")
        evidence.validate_manifest_document(manifest)
        if evidence.canonical_bytes(manifest) != canonical_before:
            raise AssertionError("valid manifest validation mutated canonical input")
        invalid = copy.deepcopy(manifest)
        invalid["source_inputs"][0] = None
        invalid_before = evidence.canonical_bytes(invalid)
        try:
            evidence.validate_manifest_document(invalid)
        except evidence.EvidenceError as error:
            if error.reason != "manifest-identity":
                raise AssertionError(f"invalid manifest expected manifest-identity, observed {error.reason}") from error
        else:
            raise AssertionError("malformed manifest input was accepted")
        if evidence.canonical_bytes(invalid) != invalid_before:
            raise AssertionError("invalid manifest validation mutated its input")
        if manifest_path.read_bytes() != manifest_bytes or frozen_path.read_bytes() != frozen_bytes:
            raise AssertionError("manifest validation changed frozen evidence bytes")
        return {"case_id": "evidence.canonical-preservation", "outcome": "pass",
                "assertions": 8, "expected": {"manifest": "canonical bytes unchanged",
                                               "receipt_sha256": frozen_digest,
                                               "invalid_input": "unchanged"},
                "observed": {"manifest": "canonical bytes unchanged",
                             "receipt_sha256": evidence.sha256_bytes(frozen_path.read_bytes()),
                             "invalid_input": "unchanged"}}

    def manifest_erased_failure() -> dict[str, Any]:
        record = valid_record()
        record["failure_history"] = [{"outcome": "fail", "reason": "known mutation rejected"}]
        record["retained_failures"] = []
        return expect_rejection("evidence.manifest-erased-failure",
                                lambda: evidence.validate_case_record(record), "erased-failure")

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

    def baseline_insufficient_samples() -> dict[str, Any]:
        record = valid_baseline_record()
        record["raw_samples"]["load_ns"] = record["raw_samples"]["load_ns"][:29]
        record["protocol"]["retained_samples"] = 29
        return expect_rejection("baseline.insufficient-samples",
                                lambda: evidence.validate_baseline_record(record),
                                "insufficient-samples")

    def baseline_missing_raw_samples() -> dict[str, Any]:
        record = valid_baseline_record()
        record.pop("raw_samples")
        return expect_rejection("baseline.missing-raw-samples",
                                lambda: evidence.validate_baseline_record(record),
                                "missing-raw-samples")

    def baseline_invalid_measurement() -> dict[str, Any]:
        record = valid_baseline_record()
        record["raw_samples"]["execution_ns"][0] = -1
        return expect_rejection("baseline.invalid-measurement",
                                lambda: evidence.validate_baseline_record(record),
                                "invalid-measurement")

    def baseline_workload_mismatch() -> dict[str, Any]:
        record = valid_baseline_record()
        record["workload"]["output_sha256"] = "2" * 64
        return expect_rejection("baseline.workload-output-mismatch",
                                lambda: evidence.validate_baseline_record(record),
                                "workload-mismatch")

    def baseline_summary_mismatch() -> dict[str, Any]:
        record = valid_baseline_record()
        record["summaries"]["load_ns"]["median_ns"] += 1
        return expect_rejection("baseline.fake-summary-precision",
                                lambda: evidence.validate_baseline_record(record),
                                "summary-mismatch")

    def baseline_discarded_sample() -> dict[str, Any]:
        record = valid_baseline_record()
        record["discarded_samples"] = [{"kind": "execution_ns", "original_ns": 99}]
        return expect_rejection("baseline.unexplained-discard",
                                lambda: evidence.validate_baseline_record(record),
                                "discarded-sample")

    def baseline_memory_unsupported() -> dict[str, Any]:
        record = valid_baseline_record()
        record["outcome"] = "unsupported"
        record["reason"] = "owned allocator measurements are unavailable"
        record["memory"] = {"status": "unsupported", "reason": "private allocator unavailable"}
        evidence.validate_baseline_record(record)
        return {"case_id": "baseline.unsupported-memory-remains-unsupported",
                "outcome": "pass", "assertions": 2,
                "expected": "unsupported", "observed": record["memory"]["status"]}

    return {
        "legacy_identity": legacy_identity_without_importer,
        "stale_mvs_importer_source": stale_mvs_importer_source,
        "mvs_diagnostic_source_closure": mvs_diagnostic_sources_in_closure,
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
        "row_shape_matrix_aggregator": row_shape_matrix_aggregator,
        "row_shape_identity_source": row_shape_identity_source,
        "row_shape_identity_unity": row_shape_identity_unity,
        "row_shape_identity_artifact": row_shape_identity_artifact,
        "row_shape_importer_source": row_shape_importer_source,
        "row_shape_manifest_source": row_shape_manifest_source,
        "row_shape_manifest_dependency": row_shape_manifest_dependency,
        "row_shape_manifest_dependency_file": row_shape_manifest_dependency_file,
        "row_shape_manifest_fixture": row_shape_manifest_fixture,
        "manifest_source_size_precision": manifest_source_size_precision,
        "canonical_preservation": canonical_preservation,
        "manifest_erased_failure": manifest_erased_failure,
        "empty_manifest": empty_manifest,
        "empty_ancestry": empty_ancestry,
        "stale_manifest_source": stale_manifest_source,
        "unknown_outcome": unknown_outcome,
        "baseline_insufficient_samples": baseline_insufficient_samples,
        "baseline_missing_raw_samples": baseline_missing_raw_samples,
        "baseline_invalid_measurement": baseline_invalid_measurement,
        "baseline_workload_mismatch": baseline_workload_mismatch,
        "baseline_summary_mismatch": baseline_summary_mismatch,
        "baseline_discarded_sample": baseline_discarded_sample,
        "baseline_memory_unsupported": baseline_memory_unsupported,
    }


class EvidenceIdentityRowShapeTests(unittest.TestCase):
    def test_identity_and_importer_rows_reject_nonobjects(self) -> None:
        expected_cases = {
            "row_shape_identity_source": "evidence.row-shape-identity-source",
            "row_shape_identity_unity": "evidence.row-shape-identity-unity",
            "row_shape_identity_artifact": "evidence.row-shape-identity-artifact",
            "row_shape_importer_source": "evidence.row-shape-importer-source",
        }
        for case_name, expected_id in expected_cases.items():
            with self.subTest(case=case_name):
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "--case", case_name],
                    cwd=ROOT, capture_output=True, text=True, check=False)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, output)
                rows = [line.removeprefix("SDK_EVIDENCE_CASE ")
                        for line in output.splitlines()
                        if line.startswith("SDK_EVIDENCE_CASE ")]
                self.assertEqual(len(rows), 1, output)
                record = json.loads(rows[0])
                self.assertEqual(record["case_id"], expected_id)
                self.assertEqual(record["outcome"], "pass")


class EvidenceManifestRowShapeTests(unittest.TestCase):
    def test_manifest_collection_vectors_and_precision_controls(self) -> None:
        expected_cases = {
            "row_shape_manifest_source": "evidence.row-shape-manifest-source",
            "row_shape_manifest_dependency": "evidence.row-shape-manifest-dependency",
            "row_shape_manifest_dependency_file": "evidence.row-shape-manifest-dependency-file",
            "row_shape_manifest_fixture": "evidence.row-shape-manifest-fixture",
            "manifest_source_size_precision": "evidence.manifest-source-size-precision",
            "canonical_preservation": "evidence.canonical-preservation",
            "manifest_erased_failure": "evidence.manifest-erased-failure",
        }
        for case_name, expected_id in expected_cases.items():
            with self.subTest(case=case_name):
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "--case", case_name],
                    cwd=ROOT, capture_output=True, text=True, check=False)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, output)
                rows = [line.removeprefix("SDK_EVIDENCE_CASE ")
                        for line in output.splitlines()
                        if line.startswith("SDK_EVIDENCE_CASE ")]
                self.assertEqual(len(rows), 1, output)
                record = json.loads(rows[0])
                self.assertEqual(record["case_id"], expected_id)
                self.assertEqual(record["outcome"], "pass")

    def test_verifier_requires_exact_unique_case_inventory(self) -> None:
        expected_cases = {**verifier.EVIDENCE_CASES, **verifier.BASELINE_CASES}
        expected_ids = {**verifier.EVIDENCE_CASE_IDS, **verifier.BASELINE_CASE_IDS}
        validate_inventory = getattr(verifier, "validate_evidence_case_inventory", None)
        self.assertTrue(callable(validate_inventory),
                        "verify_sdk must expose its exact evidence-control inventory gate")
        validate_inventory(list(cases()), expected_cases, expected_ids)
        actual_ids = {key: case()["case_id"] for key, case in cases().items()}
        self.assertEqual(actual_ids, expected_ids)
        with self.assertRaises(verifier.VerificationError):
            validate_inventory(list(cases())[:-1], expected_cases, expected_ids)
        with self.assertRaises(verifier.VerificationError):
            validate_inventory([*list(cases()), next(iter(cases()))], expected_cases, expected_ids)
        duplicate_ids = dict(expected_ids)
        first, second = list(duplicate_ids)[:2]
        duplicate_ids[second] = duplicate_ids[first]
        with self.assertRaises(verifier.VerificationError):
            validate_inventory(list(cases()), expected_cases, duplicate_ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", choices=sorted(cases()))
    group.add_argument("--all", action="store_true")
    group.add_argument("--list", action="store_true")
    args = parser.parse_args()
    selected = cases()
    if args.list:
        print("SDK_EVIDENCE_INVENTORY " + json.dumps(sorted(selected)))
        return 0
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
