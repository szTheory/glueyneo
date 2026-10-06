#!/usr/bin/env python3
"""Adversarial controls for exact platform-matrix evidence."""

from __future__ import annotations

import copy
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import sdk_evidence as evidence  # noqa: E402


def require_rejection(report: dict, reason: str) -> None:
    try:
        evidence.validate_matrix_report(report)
    except evidence.EvidenceError as error:
        assert error.reason == reason, (error.reason, reason)
    else:
        raise AssertionError(f"invalid matrix report accepted; expected {reason}")


def valid_report() -> dict:
    lanes = []
    for lane in evidence.REQUIRED_MATRIX_LANES:
        os_name, compiler_ids, architectures = evidence.MATRIX_LANE_IDENTITY[lane]
        lanes.append({
            "lane": lane,
            "compiler": {"id": next(iter(compiler_ids)), "version": "18.1.8"},
            "sdk": {"name": "SDK", "version": "15.0"},
            "os_image": {"Linux": "ubuntu-24.04", "Darwin": "macos-15", "Windows": "windows-2025"}[os_name],
            "os": os_name,
            "architecture": next(iter(architectures)),
            "configuration": "Debug",
            "source_revision": "a" * 40,
            "working_tree_dirty": False,
            "build_identity": {"cmake": "3.31.6", "generator": "Ninja", "fixture_sha256": "b" * 64},
            "outcome": "pass",
            "assertions": 12,
            "duration_seconds": 3.5,
            "cold_build_seconds": 6.0,
            "runner_id": "local-macos-arm64",
            "runner_minutes": 0.058333,
        })
    return {
        "schema_version": evidence.MATRIX_SCHEMA_VERSION,
        "source_revision": "a" * 40,
        "outcome": "pass",
        "lanes": lanes,
        "cost": {
            "cold_build_seconds": 12.5,
            "critical_path_seconds": 3.5,
            "runner_minutes": 0.35,
            "job_durations_seconds": [3.5, 3.5, 3.5, 3.5, 3.5, 3.5],
            "runner_id": "local-macos-arm64",
        },
    }


def main() -> int:
    report = valid_report()
    evidence.validate_matrix_report(report)

    mutation = copy.deepcopy(report)
    mutation["lanes"][0]["outcome"] = "pass"
    mutation["lanes"][0]["assertions"] = 0
    require_rejection(mutation, "matrix-zero-assertions")

    mutation = copy.deepcopy(report)
    mutation["lanes"].pop()
    require_rejection(mutation, "matrix-missing-lane")

    mutation = copy.deepcopy(report)
    mutation["lanes"][1]["outcome"] = "pass"
    mutation["lanes"][1]["source_revision"] = "c" * 40
    require_rejection(mutation, "matrix-revision-mismatch")

    mutation = copy.deepcopy(report)
    mutation["lanes"][2]["duration_seconds"] = 0
    require_rejection(mutation, "matrix-invalid-duration")

    mutation = copy.deepcopy(report)
    mutation["lanes"][3]["outcome"] = "pass"
    mutation["lanes"][3]["compiler"]["version"] = "unknown"
    require_rejection(mutation, "matrix-identity-missing")

    mutation = copy.deepcopy(report)
    mutation["lanes"][1]["compiler"]["id"] = "Clang"
    require_rejection(mutation, "matrix-lane-identity-mismatch")

    mutation = copy.deepcopy(report)
    mutation["lanes"][0]["working_tree_dirty"] = True
    require_rejection(mutation, "matrix-dirty-source")

    mutation = copy.deepcopy(report)
    mutation["cost"]["runner_minutes"] = 99
    require_rejection(mutation, "matrix-cost-mismatch")

    mutation = copy.deepcopy(report)
    mutation["lanes"][0]["outcome"] = "unknown"
    mutation["lanes"][0]["reason"] = "Hosted lane has not run locally"
    mutation["lanes"][0]["assertions"] = 0
    mutation["outcome"] = "unknown"
    evidence.validate_matrix_report(mutation)

    print("PASS: matrix evidence positive identity, outcome, count, timing, and cost controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
