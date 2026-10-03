"""Nonempty corruption, classification, freshness and review controls."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.owned_cpu import acceptance as a


def log_fixture():
    blocks = []
    for index, name in enumerate(sorted(a.CASES), 1):
        output = ""
        if name in a.UNITY:
            output += f"{a.UNITY[name]} Tests 0 Failures 0 Ignored\n"
        if name == "owned_cpu_state":
            output += "state_checkpoints=13 continuation_run_calls=91\n"
        if name == "owned_cpu_isolation":
            output += "interleaved_pairs=32 boundaries_per_instance=6\nconcurrent_pairs=32 boundaries_per_instance=6\n"
        if name == "owned_cpu_cold":
            output += "PASS: cold_process_cases=16 fresh_processes=16 concurrent_instances=2\n"
        if name == "owned_cpu_negative":
            output += "PASS: diagnostic\nPASS: pending IRQ\nPASS: counter rejection\n"
        if name in ("owned_cpu_isolation_negative", "owned_cpu_timing_negative"):
            output += "PASS: exact control\n"
        blocks.append(f"{index}/12 Testing: {name}\n{output}Test Passed.\n")
    return "".join(blocks)


def document_fixture():
    log = log_fixture()
    step = {"command": ["cmake", "--preset", "owned-debug"], "exit": 0,
            "status": "pass", "output": "", "output_sha256": hashlib.sha256(b"").hexdigest()}
    lane = {"preset": "owned-debug", "optional": False, "status": "pass", "steps": [copy.deepcopy(step) for _ in range(3)],
            "test_log": log, "test_log_sha256": hashlib.sha256(log.encode()).hexdigest(),
            "counts": a.test_counts(log), "artifacts": {"binary": "a" * 64},
            "configuration": {"sanitizer": "NONE"}, "compiler": {"status": "pass"}}
    record = {"revision": "a" * 40, "source_hashes": {"cpu.c": "a" * 64},
              "host": {"architecture": "test"}, "tools": {"cmake": "test"}, "runs": [lane]}
    record["sha256"] = a.digest(record)
    return {"schema": 1, "collections": [record], "disposition": "unqualified",
            "phase_disposition": "GAPS_FOUND", "blockers": ["review pending"]}


def rehash(document):
    record = document["collections"][0]
    record["sha256"] = a.digest({key: value for key, value in record.items() if key != "sha256"})


class AcceptanceControls(unittest.TestCase):
    def test_budget_and_churn_pause_cannot_accept(self):
        good = {"status": "pass", "active_seconds": 30000, "runtime_churn_added_deleted": 1206, "test_tool_churn_added_deleted": 4538}
        a.budget_check(good)
        for key, value in (("active_seconds", 115200), ("runtime_churn_added_deleted", 6000), ("test_tool_churn_added_deleted", 8000), ("status", "pause-for-review")):
            with self.assertRaises(a.EvidenceError):
                a.budget_check(good | {key: value})
    def test_positive_fixture_has_nonzero_counts(self):
        document = document_fixture()
        self.assertEqual("pass", a.verify(document, False)["status"])
        self.assertEqual(12, document["collections"][0]["runs"][0]["counts"]["ctest_observed"])

    def test_empty_and_corrupt_evidence(self):
        for document in ({"schema": 1, "collections": []}, {"schema": 1, "collections": [{"sha256": "0" * 64}]}):
            with self.assertRaises(a.EvidenceError):
                a.verify(document, False)

    def test_wrong_empty_and_duplicate_counts(self):
        log = log_fixture()
        for content in ("", log.replace("17 Tests", "0 Tests"), log + "13/13 Testing: owned_cpu_state\nTest Passed.\n", log.replace("state_checkpoints=13", "state_checkpoints=0"), log.replace("PASS: counter rejection\n", "")):
            with self.assertRaises(a.EvidenceError):
                a.test_counts(content)

    def test_failure_not_promoted_to_success(self):
        document = document_fixture()
        document["collections"][0]["runs"][0]["steps"][0]["exit"] = 1
        rehash(document)
        with self.assertRaisesRegex(a.EvidenceError, "false successful"):
            a.verify(document, False)

    def test_mutated_output_rejected_even_if_record_rehashed(self):
        document = document_fixture()
        document["collections"][0]["runs"][0]["steps"][0]["output"] = "hidden failure"
        rehash(document)
        with self.assertRaisesRegex(a.EvidenceError, "corrupted command output"):
            a.verify(document, False)

    def test_stale_sources_rejected_read_only(self):
        with patch.object(a, "snapshot", return_value={"cpu.c": "b" * 64}):
            with self.assertRaisesRegex(a.EvidenceError, "stale collected source"):
                a.verify(document_fixture())

    def test_no_acceptance_without_complete_lanes_and_review(self):
        document = document_fixture()
        document["disposition"] = "accepted"
        with self.assertRaisesRegex(a.EvidenceError, "unqualified lane"):
            a.verify(document, False)

    def test_optional_classification_is_exact(self):
        self.assertEqual("fail", a.classify_optional({"exit": 1, "status": "fail", "output": "build failure"}))
        self.assertEqual("unknown", a.classify_optional({"exit": None, "status": "unknown", "output": "timeout"}))
        self.assertEqual("unsupported", a.classify_optional({"exit": 1, "status": "fail", "output": "The selected compiler/linker cannot provide required ThreadSanitizer instrumentation"}))

    def test_presets_reject_optimized_false_green(self):
        original = json.loads((ROOT / "CMakePresets.json").read_text())
        a.validate_presets(original)
        for mutation in ("floor", "backend", "workers", "optimization", "duplicate"):
            document = copy.deepcopy(original)
            if mutation == "floor": document["version"] = 3
            elif mutation == "backend": document["configurePresets"][0]["cacheVariables"]["GLUEYNEO_CPU_EXPERIMENT"] = "ON"
            elif mutation == "workers": document["buildPresets"][0]["jobs"] = 3
            elif mutation == "optimization": document["configurePresets"][1]["cacheVariables"]["GLUEYNEO_OWNED_CPU_OPTIMIZATION"] = "NONE"
            else: document["configurePresets"][1] = document["configurePresets"][0]
            with self.assertRaises(a.EvidenceError): a.validate_presets(document)

    def test_review_headings_revision_independence_and_blockers(self):
        revision = "a" * 40
        text = "\n".join("## " + heading + "\n" + (revision if index == 0 else "explicit evidence") for index, heading in enumerate(a.REVIEW_HEADINGS))
        text += "\nIndependent reviewer: separate non-author agent\nAuthored runtime/collector/tests: no\nDisposition: clean\n"
        with tempfile.TemporaryDirectory() as directory, patch.object(a, "git", return_value=revision):
            path = Path(directory) / "REVIEW.md"
            path.write_text(text)
            self.assertEqual("clean", a.review_check(path, "HEAD")["status"])
            for broken in (text.replace(revision, "b" * 40), text.replace("Prior findings:", "Omitted:"), text.replace("Authored runtime/collector/tests: no", "Authored runtime/collector/tests: yes"), text.replace("Disposition: clean", "Disposition: GAPS_FOUND")):
                path.write_text(broken)
                with self.assertRaises(a.EvidenceError): a.review_check(path, "HEAD")

    def test_self_test_normal_and_optimized(self):
        for flags in ([], ["-O"]):
            child = subprocess.run([sys.executable, *flags, str(ROOT / "tools/owned_cpu/acceptance.py"), "self-test"], capture_output=True, text=True)
            self.assertEqual(0, child.returncode, child.stdout + child.stderr)
            self.assertEqual(6, json.loads(child.stdout)["negative_controls"])


if __name__ == "__main__":
    unittest.main()
