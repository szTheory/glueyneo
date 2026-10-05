"""Adversarial controls for the Phase 01 admission recommendation."""

import copy
import contextlib
import io
import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.workflow import phase01_admission as admission


IDENTITY = {
    "profile": "owned-p01-c14-continuation-2",
    "source_revision": "a" * 40,
    "collection_sha256": "b" * 64,
    "source_map_sha256": "c" * 64,
    "amendment_sha256": "d" * 64,
    "active_contract_identity_sha256": "e" * 64,
    "receipt_sha256": "1" * 64,
    "hardware_saved_pc": "unknown",
    "unsupported_opcodes": ["0x4AFC"],
}
REQUIREMENTS = {f"CPU-0{i}": "sufficient" for i in range(1, 6)}


def evidence():
    return [{"path": "evidence.md", "sha256": "f" * 64, "claim": "bounded observation",
             "denominator": 1, "oracle": "named project assertion", "limitation": "private scope"}]


def report(kind, agent_id, requirements=None, blocker=None, open_high=0):
    return {
        "schema": 1,
        "kind": kind,
        "agent_id": agent_id,
        "independent_non_author": True,
        "identity": copy.deepcopy(IDENTITY),
        "hardware_saved_pc": "unknown",
        "unsupported_opcodes": ["0x4AFC"],
        "hardware_claim": "none",
        "requirements": copy.deepcopy(requirements or {
            key: {"decision": "sufficient", "evidence": evidence(), "limitation": "bounded evidence"}
            for key in REQUIREMENTS}),
        "open_high_or_critical": open_high,
        "asvs_level": 1,
        "block_on": "high",
        "status": "verified" if open_high == 0 else "blocked",
        "blocker": copy.deepcopy(blocker),
    }


def blocked_fixture():
    blocker = {
        "requirement": "CPU-02",
        "predicate": "a material lifecycle predicate lacks current distinguishable evidence",
        "reason": "The independent reviewer identifies one specific uncovered path.",
        "next_dependency": "Run the named isolated-baseline case at the frozen source identity.",
        "evidence": evidence(),
    }
    review_reqs = {key: {"decision": REQUIREMENTS[key], "evidence": evidence(),
                         "limitation": "bounded evidence"} for key in REQUIREMENTS}
    review_reqs["CPU-02"]["decision"] = "blocked"
    review = report("cpu-admission-review", "reviewer-a", review_reqs, blocker)
    security = report("cpu-admission-security", "assessor-b")
    reqs = {key: {"decision": item["decision"], "evidence": copy.deepcopy(item["evidence"])}
            for key, item in review_reqs.items()}
    decision = {
        "schema": 1,
        "disposition": "blocked",
        "phase_admitted": False,
        "hardware_saved_pc": "unknown",
        "identity": copy.deepcopy(IDENTITY),
        "requirements": reqs,
        "reviewer_agent_id": "reviewer-a",
        "security_agent_id": "assessor-b",
        "executor_agent_id": "executor",
        "security": {"status": "verified", "open_high_or_critical": 0},
        "blocker": copy.deepcopy(blocker),
    }
    return decision, review, security


def accepted_fixture():
    decision, review, security = blocked_fixture()
    decision["disposition"] = "accept_recommended"
    decision["blocker"] = None
    decision["requirements"] = {
        key: {"decision": "sufficient", "evidence": copy.deepcopy(item["evidence"])}
        for key, item in review["requirements"].items()}
    review["blocker"] = None
    review["requirements"] = {
        key: {"decision": "sufficient", "evidence": evidence(), "limitation": "bounded evidence"}
        for key in REQUIREMENTS}
    return decision, review, security


class TerminalControls(unittest.TestCase):
    def test_all_five_supported_requirements_produce_only_a_recommendation(self):
        decision, review, security = accepted_fixture()
        result = admission.validate_terminal(decision, review, security)
        self.assertEqual("accept_recommended", result["disposition"])
        self.assertIs(False, result["phase_admitted"])

    def test_precise_blocked_record_is_valid_but_never_admits(self):
        decision, review, security = blocked_fixture()
        result = admission.validate_terminal(decision, review, security)
        self.assertEqual("blocked", result["disposition"])
        self.assertIs(False, result["phase_admitted"])
        self.assertEqual("CPU-02", result["blocker"]["requirement"])

    def test_adversarial_terminal_mutations_fail_closed(self):
        cases = []
        def add(name, edit, fixture=accepted_fixture):
            triple = fixture()
            edit(*triple)
            cases.append((name, triple))

        add("missing requirement", lambda d, r, s: d["requirements"].pop("CPU-05"))
        add("missing reviewer predicate", lambda d, r, s: r["requirements"].pop("CPU-03"))
        add("fabricated independence", lambda d, r, s: r.update(independent_non_author=False))
        add("stale collection", lambda d, r, s: r["identity"].update(collection_sha256="0" * 64))
        add("open high", lambda d, r, s: (s.update(open_high_or_critical=1, status="blocked"),
                                           d["security"].update(open_high_or_critical=1, status="blocked")))
        add("nonzero boolean is not an integer", lambda d, r, s: s.update(open_high_or_critical=True))
        add("false hardware claim", lambda d, r, s: r.update(hardware_saved_pc="0x100"))
        add("broadened support", lambda d, r, s: d["identity"].update(unsupported_opcodes=["0x4AFC", "0x4AFA"]))
        add("contradictory predicate", lambda d, r, s: r["requirements"]["CPU-04"].update(decision="blocked"))
        add("vague terminal blocker", lambda d, r, s: (d.update(disposition="blocked", blocker={}),
                                                          d["requirements"].update({"CPU-02": {"decision": "blocked", "evidence": evidence()}})))
        def drift_reason(d, r, s):
            d["blocker"]["reason"] = "different claim"
            d["requirements"]["CPU-02"]["decision"] = "blocked"
        add("rehashed blocked reason drift", drift_reason, fixture=blocked_fixture)
        def second_blocker(d, r, s):
            d["requirements"]["CPU-03"]["decision"] = "blocked"
        add("hidden second blocker", second_blocker, fixture=blocked_fixture)
        add("relabel blocked decision as accepted", lambda d, r, s: d.update(disposition="accept_recommended"),
            fixture=blocked_fixture)
        for name, triple in cases:
            with self.subTest(name=name), self.assertRaises(admission.EvidenceError):
                admission.validate_terminal(*triple)
        for field in ("source_revision", "source_map_sha256", "amendment_sha256",
                      "active_contract_identity_sha256", "receipt_sha256"):
            decision, review, security = accepted_fixture()
            review["identity"][field] = "0" * len(IDENTITY[field])
            with self.subTest(field=field), self.assertRaises(admission.EvidenceError):
                admission.validate_terminal(decision, review, security)

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(admission.EvidenceError, "duplicate JSON key"):
            admission.parse_json(b'{"status":"sufficient","status":"blocked"}', "mutation")

    def test_evidence_reference_needs_current_hash_denominator_and_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "evidence.md"
            path.write_text("frozen observation")
            ref = {"path": "evidence.md", "sha256": admission.sha(path.read_bytes()),
                   "claim": "bounded observation", "denominator": 4,
                   "oracle": "independent guest assertion", "limitation": "not hardware truth"}
            admission.valid_ref(root, ref)
            for update, message in (({"denominator": 0}, "denominator"),
                                    ({"oracle": ""}, "oracle"),
                                    ({"sha256": "0" * 64}, "stale evidence")):
                mutated = ref | update
                with self.subTest(message=message), self.assertRaisesRegex(admission.EvidenceError, message):
                    admission.valid_ref(root, mutated)
            with self.assertRaisesRegex(admission.EvidenceError, "repository-relative"):
                admission.file_bytes(root, "../outside")

    def test_blocked_child_exit_two_is_exactly_preserved(self):
        decision, review, security = blocked_fixture()
        result = admission.validate_terminal(decision, review, security)
        output = json.dumps({"disposition": "blocked", "phase_admitted": False,
                             "blocker": result["blocker"]})
        completed = __import__("subprocess").CompletedProcess([], 2, output, "")
        with patch.object(admission.subprocess, "run", return_value=completed) as run:
            record = admission.conditional_exit(Path("/repo"), "decision.json", result)
        run.assert_called_once()
        self.assertEqual(2, record["child"]["exit"])
        self.assertEqual(result["blocker"], json.loads(record["child"]["stdout"])["blocker"])

    def test_wrong_child_exit_or_blocker_output_fails(self):
        decision, review, security = blocked_fixture()
        result = admission.validate_terminal(decision, review, security)
        wrong = __import__("subprocess").CompletedProcess([], 0,
            json.dumps({"disposition": "blocked", "phase_admitted": False, "blocker": result["blocker"]}), "")
        with patch.object(admission.subprocess, "run", return_value=wrong):
            with self.assertRaisesRegex(admission.EvidenceError, "exit/output mismatch"):
                admission.conditional_exit(Path("/repo"), "decision.json", result)
        wrong_payload = {"disposition": "blocked", "phase_admitted": False,
                         "blocker": result["blocker"] | {"reason": "wrong blocker"}}
        wrong = __import__("subprocess").CompletedProcess([], 2, json.dumps(wrong_payload), "")
        with patch.object(admission.subprocess, "run", return_value=wrong):
            with self.assertRaisesRegex(admission.EvidenceError, "exit/output mismatch"):
                admission.conditional_exit(Path("/repo"), "decision.json", result)

    def test_accept_child_exit_zero_is_required(self):
        decision, review, security = accepted_fixture()
        result = admission.validate_terminal(decision, review, security)
        output = json.dumps({"disposition": "accept_recommended", "phase_admitted": False, "blocker": None})
        completed = __import__("subprocess").CompletedProcess([], 0, output, "")
        with patch.object(admission.subprocess, "run", return_value=completed):
            record = admission.conditional_exit(Path("/repo"), "decision.json", result)
        self.assertEqual(0, record["child"]["exit"])

    def test_conditional_child_timeout_is_not_silently_accepted(self):
        decision, review, security = blocked_fixture()
        result = admission.validate_terminal(decision, review, security)
        with patch.object(admission.subprocess, "run", side_effect=__import__("subprocess").TimeoutExpired("verify", 10)):
            with self.assertRaisesRegex(admission.EvidenceError, "child failed"):
                admission.conditional_exit(Path("/repo"), "decision.json", result)

    def test_json_report_hash_and_single_assessment_block_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "report.md"
            path.write_text("```json\n{\"schema\":1}\n```\n")
            bound = {"path": "report.md", "sha256": admission.sha(path.read_bytes())}
            self.assertEqual(1, admission.report_json(root, bound)["schema"])
            with self.assertRaisesRegex(admission.EvidenceError, "hash mismatch"):
                admission.report_json(root, bound | {"sha256": "0" * 64})
            path.write_text("```json\n{\"schema\":1}\n```\n```json\n{\"schema\":1}\n```\n")
            bound["sha256"] = admission.sha(path.read_bytes())
            with self.assertRaisesRegex(admission.EvidenceError, "one JSON assessment"):
                admission.report_json(root, bound)

    def test_ledger_prefix_and_uat_rows_are_append_only(self):
        old_entry = {"stage": "old", "active_seconds": 1}
        frozen = {"caps": {"active": 10}, "status": "pass"}
        new_entry = {"stage": "plan-01-29", "active_seconds": 2}
        ledger = frozen | {"entries": [old_entry, new_entry]}
        saved = {"prefix_entries": 1, "prefix_sha256": admission.digest([old_entry]),
                 "frozen_sha256": admission.digest(frozen),
                 "appended": {"count": 1, "sha256": admission.digest([new_entry])}}
        self.assertEqual([new_entry], admission.check_ledger_prefix(ledger, saved))
        for bad, message in ((frozen | {"entries": [new_entry]}, "historical entries changed"),
                             (frozen | {"entries": []}, "history was removed"),
                             ((frozen | {"caps": {"active": 11}}) | {"entries": [old_entry, new_entry]},
                              "frozen ledger fields changed")):
            with self.subTest(message=message), self.assertRaisesRegex(admission.EvidenceError, message):
                admission.check_ledger_prefix(bad, saved)

        old_uat = b"### 1. old\nresult: pass\n### 2. old\nresult: pass\n"
        suffix = b"\n### 3. current\nresult: pass\nsource: automated\ncommand: python3 check.py\nevidence: report.json\n"
        uat_saved = {"prefix_bytes": len(old_uat), "prefix_sha256": admission.sha(old_uat),
                     "historical_rows": 2, "final_rows": 3}
        self.assertEqual(3, admission.check_uat_prefix(old_uat + suffix, uat_saved))
        for bad in (b"### 1. edited\n" + old_uat[len(b"### 1. old\n"):]+suffix,
                    b"### 1. old\nresult: pass\n" + suffix):
            with self.assertRaises(admission.EvidenceError):
                admission.check_uat_prefix(bad, uat_saved)
        with self.assertRaisesRegex(admission.EvidenceError, "UAT evidence is incomplete"):
            admission.check_uat_prefix(old_uat + b"\n### 3. current\nresult: pending\n", uat_saved)

    def test_changed_candidate_seal_is_rejected_by_preservation_binding(self):
        original = {"collections": [{"sha256": "a"}], "superseded_seals": [{"id": 1}],
                    "seal": {"defer_admission": True}}
        expected = admission.digest(original)
        admission.check_receipt_history(original, expected)
        changed = copy.deepcopy(original)
        changed["seal"]["defer_admission"] = False
        with self.assertRaisesRegex(admission.EvidenceError, "receipt collection/seal history changed"):
            admission.check_receipt_history(changed, expected)

    def test_preservation_result_reports_saved_historical_uat_count(self):
        identity = {"profile": "current"}
        source_hashes = {"src.c": "source-hash"}
        snapshot = {"identity": identity, "immutable_files": {"old.md": "old-hash"},
                    "receipt_objects_sha256": "receipt-hash", "source_hashes": source_hashes,
                    "ledger": {"prefix_entries": 4, "appended": {"count": 1}},
                    "final_ledger_sha256": "ledger-hash", "uat": {"historical_rows": 51}}
        decision = {"identity": identity, "preservation": snapshot}
        hashes = {"old.md": "old-hash", "src.c": "source-hash", admission.LEDGER: "ledger-hash"}
        with patch.object(admission, "candidate_identity", return_value=identity), \
             patch.object(admission, "file_hash", side_effect=lambda _, path: hashes[path]), \
             patch.object(admission, "json_file", return_value={"collections": [{"source_hashes": source_hashes}]}), \
             patch.object(admission, "check_receipt_history"), \
             patch.object(admission, "check_ledger_prefix", return_value=[{"stage": "current"}]), \
             patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout='{"status":"pass"}')), \
             patch.object(admission, "file_bytes", return_value=b"uat"), \
             patch.object(admission, "check_uat_prefix", return_value=52):
            result = admission.check_preservation(ROOT, decision)
        self.assertEqual(51, result["historical_uat_rows"])

    def test_cli_require_mode_returns_exit_two_for_valid_blocker(self):
        blocked, _, _ = blocked_fixture()
        output = io.StringIO()
        with patch.object(admission, "verify", return_value={"disposition": "blocked", "blocker": blocked["blocker"]}), \
             contextlib.redirect_stdout(output):
            code = admission.main(["verify", "--decision", "decision.json", "--require-recommendation"])
        self.assertEqual(2, code)
        self.assertEqual("blocked", json.loads(output.getvalue())["disposition"])

    def test_cli_require_mode_returns_one_for_invalid_record(self):
        output = io.StringIO()
        with patch.object(admission, "verify", side_effect=admission.EvidenceError("invalid")), \
             contextlib.redirect_stdout(output):
            code = admission.main(["verify", "--decision", "decision.json", "--require-recommendation"])
        self.assertEqual(1, code)
        self.assertEqual("invalid", json.loads(output.getvalue())["status"])


if __name__ == "__main__":
    unittest.main()
