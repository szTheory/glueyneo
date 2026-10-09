#!/usr/bin/env python3
"""Adversarial controls for exact-revision hosted MVS receipts."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from verify_hosted_mvs import EXPECTED_TESTS, ReceiptError, validate  # noqa: E402

OUTPUT = b"seven hosted MVS CTests passed\n"


def valid_pair() -> tuple[dict, dict]:
    revision = "a" * 40
    digest = "b" * 64
    event = {"name": "pull_request", "action": "synchronize",
             "draft": False, "head_sha": revision}
    receipt = {"source_revision": revision, "relevant_source_sha256": digest,
               "label": "mvs", "outcome": "pass", "ctest_cases": 7,
               "named_tests": EXPECTED_TESTS.copy(),
               "output_sha256": hashlib.sha256(OUTPUT).hexdigest()}
    return event, receipt


class HostedMvsReceiptTests(unittest.TestCase):
    def test_accepts_exact_eligible_receipt(self) -> None:
        event, receipt = valid_pair()
        validate(event, receipt, source_revision="a" * 40,
                 relevant_source_sha256="b" * 64, output_bytes=OUTPUT)

    def test_rejects_unbound_output_digest(self) -> None:
        event, receipt = valid_pair()
        receipt["output_sha256"] = "c" * 64
        self.assert_rejected(event, receipt)

    def test_rejects_ineligible_event(self) -> None:
        event, receipt = valid_pair()
        event["name"] = "workflow_dispatch"
        self.assert_rejected(event, receipt)

    def test_rejects_stale_event_or_receipt_sha(self) -> None:
        for field in ("event", "receipt"):
            event, receipt = valid_pair()
            (event if field == "event" else receipt)["head_sha" if field == "event" else "source_revision"] = "d" * 40
            self.assert_rejected(event, receipt)

    def test_rejects_missing_duplicate_or_unexpected_mvs_test(self) -> None:
        for tests in (EXPECTED_TESTS[:-1], [*EXPECTED_TESTS[:-1], EXPECTED_TESTS[0]],
                      [*EXPECTED_TESTS[:-1], "other"]):
            event, receipt = valid_pair()
            receipt["named_tests"] = tests
            self.assert_rejected(event, receipt)

    def test_rejects_zero_or_wrong_denominator(self) -> None:
        for count in (0, 6, 8):
            event, receipt = valid_pair()
            receipt["ctest_cases"] = count
            self.assert_rejected(event, receipt)

    def test_rejects_missing_or_mismatched_digests(self) -> None:
        for field, value in (("relevant_source_sha256", None),
                             ("relevant_source_sha256", "d" * 64),
                             ("output_sha256", None), ("output_sha256", "invalid")):
            event, receipt = valid_pair()
            receipt[field] = value
            self.assert_rejected(event, receipt)

    def test_rejects_failed_aggregate(self) -> None:
        event, receipt = valid_pair()
        receipt["outcome"] = "fail"
        self.assert_rejected(event, receipt)

    def assert_rejected(self, event: dict, receipt: dict) -> None:
        with self.assertRaises(ReceiptError):
            validate(event, receipt, source_revision="a" * 40,
                     relevant_source_sha256="b" * 64, output_bytes=OUTPUT)


if __name__ == "__main__":
    unittest.main()
