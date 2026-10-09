#!/usr/bin/env python3
"""Validate an exact-revision hosted MVS qualification receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
from typing import Any

EXPECTED_TESTS = sorted({
    "mvs_synthetic_trace", "mvs_media_contract", "mvs_import_contract",
    "mvs_import_mutation", "mvs_callback_contract", "mvs_boot_checkpoint",
    "mvs_import_fuzz_corpus",
})
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class ReceiptError(ValueError):
    pass


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReceiptError(f"cannot read JSON receipt: {path.name}") from error
    if not isinstance(value, dict):
        raise ReceiptError("receipt root must be an object")
    return value


def _read_output(path: Path) -> bytes:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ReceiptError("hosted output must be a regular, unlinked file")
        return path.read_bytes()
    except OSError as error:
        raise ReceiptError("cannot read hosted output artifact") from error


def validate(event: dict[str, Any], receipt: dict[str, Any], *,
             source_revision: str, relevant_source_sha256: str,
             output_bytes: bytes, aggregate: dict[str, Any]) -> None:
    if HEX40.fullmatch(source_revision) is None or HEX64.fullmatch(relevant_source_sha256) is None:
        raise ReceiptError("expected source identity is malformed")

    event_name = event.get("name")
    if event_name == "pull_request":
        if event.get("action") not in {"opened", "synchronize", "reopened", "ready_for_review"}:
            raise ReceiptError("ineligible pull request event")
        if event.get("draft") is True:
            raise ReceiptError("draft pull request is ineligible")
        event_sha = event.get("head_sha")
    elif event_name == "push":
        if event.get("ref") != "refs/heads/main":
            raise ReceiptError("ineligible push ref")
        event_sha = event.get("sha")
    else:
        raise ReceiptError("ineligible hosted event")
    if event_sha != source_revision or receipt.get("source_revision") != source_revision:
        raise ReceiptError("event or receipt source revision is stale")

    if receipt.get("outcome") != "pass":
        raise ReceiptError("aggregate result did not pass")
    if receipt.get("label") != "mvs":
        raise ReceiptError("receipt is not the MVS suite")
    denominator = receipt.get("ctest_cases")
    if isinstance(denominator, bool) or denominator != len(EXPECTED_TESTS):
        raise ReceiptError("MVS test denominator is missing or incorrect")
    tests = receipt.get("named_tests")
    if not isinstance(tests, list) or tests != EXPECTED_TESTS:
        raise ReceiptError("MVS test inventory is missing, duplicated, or unexpected")
    if receipt.get("relevant_source_sha256") != relevant_source_sha256:
        raise ReceiptError("relevant source digest is missing or mismatched")
    output_digest = receipt.get("output_sha256")
    if (not isinstance(output_digest, str) or HEX64.fullmatch(output_digest) is None or
            output_digest != hashlib.sha256(output_bytes).hexdigest()):
        raise ReceiptError("hosted output digest is missing or does not match the artifact")

    aggregate_digest = aggregate.get("receipt_sha256")
    unsigned_aggregate = dict(aggregate)
    unsigned_aggregate.pop("receipt_sha256", None)
    aggregate_bytes = (json.dumps(unsigned_aggregate, ensure_ascii=True,
                                  sort_keys=True, separators=(",", ":")) + "\n").encode()
    if (aggregate.get("outcome") != "pass" or
            aggregate.get("source_revision") != source_revision or
            not isinstance(aggregate_digest, str) or
            HEX64.fullmatch(aggregate_digest) is None or
            hashlib.sha256(aggregate_bytes).hexdigest() != aggregate_digest):
        raise ReceiptError("hosted aggregate is failed, stale, or has an invalid digest")
    jobs = aggregate.get("jobs")
    if not isinstance(jobs, dict):
        raise ReceiptError("hosted aggregate job results are missing")
    for name in ("matrix", "public-content"):
        if not isinstance(jobs.get(name), dict) or jobs[name].get("result") != "success":
            raise ReceiptError("a required hosted aggregate job did not pass")
    matrix_job = jobs["matrix"]
    for field in ("lane_count", "assertion_count"):
        count = matrix_job.get(field)
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise ReceiptError("hosted aggregate has no positive matrix denominator")
    matrix = aggregate.get("matrix")
    if (not isinstance(matrix, dict) or matrix.get("outcome") != "pass" or
            matrix.get("source_revision") != source_revision):
        raise ReceiptError("hosted matrix aggregate is missing, failed, or stale")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="exact hosted CTest output artifact whose digest is in the receipt")
    parser.add_argument("--aggregate", type=Path, required=True,
                        help="exact hosted CI aggregate artifact for the same event SHA")
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--relevant-source-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        validate(_read(args.event), _read(args.receipt),
                 source_revision=args.source_revision,
                 relevant_source_sha256=args.relevant_source_sha256,
                 output_bytes=_read_output(args.output),
                 aggregate=_read(args.aggregate))
    except ReceiptError as error:
        print(f"hosted MVS receipt rejected: {error}", file=sys.stderr)
        return 1
    print("hosted MVS receipt accepted for exact source revision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
