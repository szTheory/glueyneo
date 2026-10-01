"""MIT: adversarial admission subjects; never CPU execution evidence."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("acceptance", ROOT / "tools/cpu/acceptance.py")
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


class AcceptanceControls(unittest.TestCase):
    def test_empty_report_never_admits(self):
        self.assertNotEqual(acceptance.decide({}, {})["decision"], "accepted",
                            "empty evidence must never admit a CPU")

    def subject(self):
        identity = {"source_revision": "1" * 40, "content_digest": "a" * 64,
                    "input_hashes": {"input.c": "b" * 64}}
        records = []
        for lane, cases in acceptance.REQUIRED.items():
            for name, count in cases.items():
                records.append(dict(lane=lane, case=name, expected=count, observed=count,
                                    status="pass", kind=acceptance.kind(name),
                                    configuration=acceptance.CONFIG[lane], input_digest=identity["content_digest"],
                                    output_sha256="c" * 64, command=["ctest", name]))
        budget = dict(acceptance.CAPS)
        report = dict(schema=1, identity=identity, records=records, budget=budget,
                      caps=dict(acceptance.CAPS), ledger_sha256="d" * 64,
                      freeze_commit=acceptance.FREEZE, candidate=acceptance.CANDIDATE,
                      attempts=[1, 2], candidate_disposition="eligible",
                      unsupported=copy.deepcopy(acceptance.UNSUPPORTED),
                      lanes={lane: dict(status="pass", diagnostics=0, runtime_objects=["a" * 64] * 3,
                                       instrumentation=acceptance.CONFIG[lane], executed=True,
                                       compiler="compiler", sdk="sdk", platform="platform")
                             for lane in acceptance.CONFIG})
        report["review"] = dict(reviewer="independent-reviewer", independent=True,
                                source_revision=identity["source_revision"],
                                content_digest=identity["content_digest"],
                                evidence_digest=acceptance.evidence_digest(report),
                                inspected=list(acceptance.REVIEW_SCOPE), findings=[])
        return report, identity

    def decision(self, report, identity):
        # Subjects changed by a test are independently reviewed anew unless the
        # test explicitly exercises the stale-review seam.
        if isinstance(report.get("review"), dict):
            report["review"]["evidence_digest"] = acceptance.evidence_digest(report)
        return acceptance.decide(report, identity)["decision"]

    def test_complete_and_review_pending(self):
        report, identity = self.subject()
        self.assertEqual(self.decision(report, identity), "accepted")
        report["review"] = None
        self.assertEqual(self.decision(report, identity), "ready-for-review")

    def test_every_inclusive_cap_and_one_over(self):
        for key, cap in acceptance.CAPS.items():
            with self.subTest(key=key):
                report, identity = self.subject()
                self.assertEqual(self.decision(report, identity), "accepted")
                report["budget"][key] = cap + 1
                self.assertEqual(self.decision(report, identity), "rejected")

    def test_incomplete_and_malformed_evidence(self):
        for key in ("identity", "records", "budget", "caps", "attempts", "lanes", "unsupported"):
            for value in (None, {}, [], ""):
                with self.subTest(key=key, value=value):
                    report, identity = self.subject()
                    report[key] = value
                    self.assertNotEqual(self.decision(report, identity), "accepted")
        for key in ("records", "attempts"):
            report, identity = self.subject()
            report[key] = report[key][:1]
            self.assertNotEqual(self.decision(report, identity), "accepted")

    def test_every_required_case(self):
        report, identity = self.subject()
        for index in range(len(report["records"])):
            changed = copy.deepcopy(report)
            del changed["records"][index]
            self.assertEqual(self.decision(changed, identity), "rejected")

    def test_failed_stale_duplicate_and_zero_records(self):
        with self.assertRaises(acceptance.audit.AuditError):
            acceptance.observe("cpu_closure", '{"status":"pass"}\n[This part of the test output was removed')
        self.assertEqual(acceptance.observe("cpu_audit_controls", '{"status":"pass","tests":13}'), 13)
        with self.assertRaises(acceptance.audit.AuditError):
            acceptance.observe("cpu_audit_controls", '{"status":"fail","tests":13}')
        for key, value in (("status", "fail"), ("status", "unknown"), ("observed", 0),
                           ("configuration", "wrong"), ("input_digest", "b" * 64),
                           ("output_sha256", ""), ("kind", "probe")):
            report, identity = self.subject()
            report["records"][0][key] = value
            self.assertEqual(self.decision(report, identity), "rejected")
        report, identity = self.subject()
        report["records"].append(dict(report["records"][0], status="fail"))
        self.assertEqual(self.decision(report, identity), "rejected")

    def test_stale_identity_and_review(self):
        for key in ("source_revision", "content_digest", "input_hashes"):
            report, identity = self.subject()
            identity = dict(identity, **{key: "stale"})
            self.assertEqual(self.decision(report, identity), "rejected")
        for key, value in (("independent", False), ("reviewer", ""), ("content_digest", "stale"),
                           ("source_revision", "stale"), ("inspected", [])):
            report, identity = self.subject()
            report["review"][key] = value
            self.assertNotEqual(self.decision(report, identity), "accepted")
        report, identity = self.subject()
        report["review"]["evidence_digest"] = "stale"
        self.assertNotEqual(acceptance.decide(report, identity)["decision"], "accepted")

    def test_high_findings_and_rejection_cannot_admit(self):
        for severity in ("high", "critical"):
            report, identity = self.subject()
            report["review"]["findings"] = [dict(severity=severity, status="open", id="F1")]
            self.assertEqual(self.decision(report, identity), "rejected")
        for disposition in ("rejected", "deferred"):
            report, identity = self.subject()
            report["candidate_disposition"] = disposition
            self.assertNotEqual(self.decision(report, identity), "accepted")

    def test_probe_only_instrumentation_and_effort_reset(self):
        for key, value in (("executed", False), ("runtime_objects", []), ("diagnostics", 1),
                           ("instrumentation", "none")):
            report, identity = self.subject()
            report["lanes"]["asan-ubsan"][key] = value
            self.assertEqual(self.decision(report, identity), "rejected")
        for key in ("total_seconds", "attempt_seconds", "handwritten", "helpers", "semantic"):
            report, identity = self.subject()
            report["budget"][key] = 0
            self.assertEqual(self.decision(report, identity), "rejected")

    def test_freeze_and_order(self):
        report, identity = self.subject()
        original = acceptance.decide(report, identity)
        report["records"].reverse()
        report["unsupported"].reverse()
        self.assertEqual(acceptance.decide(report, identity), original)
        report["freeze_commit"] = "0" * 40
        self.assertEqual(self.decision(report, identity), "rejected")


if __name__ == "__main__":
    unittest.main()
