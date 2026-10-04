"""Controls for the proposed owned-core contract, budget, and frozen history."""

import json
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.owned_cpu import contract


class ContractControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="owned-cpu-contract-test-")
        self.root = Path(self.temporary.name)
        contract._copy_subject(self.root)
        target = self.root / "experiments/owned_cpu/illegal-reconciliation.json"
        shutil.copyfile(contract.ROOT / "experiments/owned_cpu/illegal-reconciliation.json", target)

    def tearDown(self):
        self.temporary.cleanup()

    def read_ledger(self):
        return json.loads((self.root / contract.LEDGER_PATH).read_text(encoding="utf-8"))

    def write_ledger(self, ledger):
        contract._write_json(self.root / contract.LEDGER_PATH, ledger)

    def test_current_candidate_requires_active_amendment(self):
        record = json.loads((self.root / "experiments/owned_cpu/illegal-reconciliation.json")
                            .read_text(encoding="utf-8"))
        self.assertIn("candidate_contract_amendments", record,
                      "P01-C-14 active candidate must carry its amendment")

    def read_reconciliation(self):
        return json.loads((self.root / contract.RECONCILIATION_PATH).read_text(encoding="utf-8"))

    def write_reconciliation(self, record):
        contract._write_json(self.root / contract.RECONCILIATION_PATH, record)

    def expect_candidate_reason(self, reason):
        with self.assertRaises(contract.ContractError) as caught:
            contract.check_candidate_contract(self.root)
        self.assertEqual(caught.exception.reason, reason)

    def test_active_amendment_binds_frozen_root_and_exact_scope(self):
        result = contract.check_candidate_contract(self.root)
        self.assertEqual(result["excluded_opcodes"], [0x4afc])
        self.assertEqual(result["hardware_saved_pc"], "unknown")
        self.assertEqual(result["frozen_contract_sha256"], self.read_ledger()["code_start"]["contract_sha256"])
        self.assertEqual(result["active_contract_identity_sha256"],
                         contract.ACTIVE_CONTRACT_IDENTITY_SHA256)
        active = contract.validate(self.root)["active_candidate_contract"]
        self.assertEqual(active, result)

    def test_missing_duplicate_reordered_and_malformed_amendments_fail(self):
        original = self.read_reconciliation()
        amendment = original["candidate_contract_amendments"][0]
        variants = [(None, "amendment_required"), ([], "amendment_required"),
                    ([amendment, amendment], "amendment_chain"),
                    ([{"decision": "P01-C-13"}, amendment], "amendment_chain"),
                    ([amendment, {"decision": "P01-C-13"}], "amendment_chain"),
                    ([None], "amendment_chain"), ({}, "amendment_required")]
        for value, reason in variants:
            with self.subTest(value=value):
                record = json.loads(json.dumps(original))
                record["candidate_contract_amendments"] = value
                self.write_reconciliation(record)
                self.expect_candidate_reason(reason)
        original.pop("candidate_contract_amendments")
        self.write_reconciliation(original)
        self.expect_candidate_reason("amendment_required")

    def test_amendment_chain_authorization_digest_and_identity_tamper_fail(self):
        original = self.read_reconciliation()
        variants = [("preceding_sha256", "0" * 64, "amendment_chain"),
                    ("root_contract_sha256", "0" * 64, "amendment_chain"),
                    ("schema", 2, "amendment_authorization"),
                    ("version", 2, "amendment_authorization"),
                    ("decision", "P01-C-13", "amendment_authorization"),
                    ("decision_reference", "D1-13", "amendment_authorization"),
                    ("authorized_date", "2026-10-02", "amendment_authorization"),
                    ("content_sha256", "0" * 64, "amendment_digest"),
                    ("active_contract_identity_sha256", "0" * 64, "amendment_identity")]
        for field, value, reason in variants:
            with self.subTest(field=field):
                record = json.loads(json.dumps(original))
                record["candidate_contract_amendments"][0][field] = value
                self.write_reconciliation(record)
                self.expect_candidate_reason(reason)

    def test_broadened_or_nonnumeric_opcode_and_old_success_result_fail(self):
        original = self.read_reconciliation()
        for excluded in ([0x4afc, 0x4e40], ["0x4afc"], [], [0x4afd], [0x4afc, 0x4afc]):
            with self.subTest(excluded=excluded):
                record = json.loads(json.dumps(original))
                record["candidate_contract_amendments"][0]["candidate_scope"]["excluded_opcodes"] = excluded
                self.write_reconciliation(record)
                self.expect_candidate_reason("amendment_scope")
        original["candidate_contract_amendments"][0]["candidate_scope"]["result"] = "OWNED_CPU_BUDGET"
        self.write_reconciliation(original)
        self.expect_candidate_reason("amendment_scope")

    def test_recomputed_digests_do_not_authorize_changed_rules_or_retained_cases(self):
        original = self.read_reconciliation()
        for target in ("cycles", "bus", "pc", "retained", "superseded", "extra"):
            with self.subTest(target=target):
                record = json.loads(json.dumps(original))
                amendment = record["candidate_contract_amendments"][0]
                if target == "cycles": amendment["candidate_scope"]["guest_exception_cycles"] = 34
                if target == "bus": amendment["candidate_scope"]["vector_4_reads"] = 2
                if target == "pc": amendment["candidate_scope"]["pc"] = "sequential PC"
                if target == "retained": amendment["retained_cases"].remove("TRAP #0")
                if target == "superseded": amendment["superseded"]["reference_scope"] = "all exceptions"
                if target == "extra": amendment["unapproved"] = True
                content = {k: v for k, v in amendment.items()
                           if k not in ("content_sha256", "active_contract_identity_sha256")}
                amendment["active_contract_identity_sha256"] = contract.canonical_digest(content)
                amendment["content_sha256"] = contract.canonical_digest(
                    {k: v for k, v in amendment.items() if k != "content_sha256"})
                self.write_reconciliation(record)
                self.expect_candidate_reason("amendment_identity")

    def test_hardware_question_cannot_be_selected_by_amendment(self):
        record = self.read_reconciliation()
        record["candidate_contract_amendments"][0]["hardware_saved_pc"]["selected"] = "0x100"
        self.write_reconciliation(record)
        self.expect_candidate_reason("amendment_hardware")

    def test_historical_reconciliation_fields_are_immutable(self):
        original = self.read_reconciliation()
        for field, value in (("resolution", "resolved"), ("saved_pc_rule", {"selected": "0x102"}),
                             ("sources", []), ("unresolved_need", {})):
            with self.subTest(field=field):
                record = json.loads(json.dumps(original))
                record[field] = value
                self.write_reconciliation(record)
                self.expect_candidate_reason("reconciliation_history")

    def test_frozen_archive_and_root_checks_are_independent_of_amendment(self):
        original = self.read_reconciliation()
        for value in ("invalid!", "", original["frozen_contract"]["bytes_base64"] + "\n"):
            with self.subTest(archive=value[:10]):
                record = json.loads(json.dumps(original))
                record.pop("candidate_contract_amendments")
                record["frozen_contract"]["bytes_base64"] = value
                self.write_reconciliation(record)
                self.expect_candidate_reason("amendment_archive")
        record = json.loads(json.dumps(original))
        record["frozen_contract"]["sha256"] = "0" * 64
        self.write_reconciliation(record)
        self.expect_candidate_reason("amendment_root")
        self.write_reconciliation(original)
        ledger = self.read_ledger()
        ledger["code_start"]["contract_sha256"] = "0" * 64
        self.write_ledger(ledger)
        self.expect_candidate_reason("amendment_root")

    def test_marker_preserving_contract_mutation_cannot_change_root(self):
        path = self.root / contract.CONTRACT_PATH
        path.write_text(path.read_text(encoding="utf-8") + "\nunauthorized amendment\n", encoding="utf-8")
        contract.check_contract(self.root)  # Legacy marker check is insufficient by itself.
        self.expect_candidate_reason("amendment_root")

    def test_frozen_subject_and_pending_gate_validate(self):
        contract.check_contract(self.root)
        history = contract.check_history(self.root)
        self.assertEqual(len(contract.HISTORICAL_SHA256), len(history))
        self.assertTrue(contract.check_story(self.root)["valid"])
        contract.check_requirements(self.root)
        self.assertEqual(contract.validate_budget(self.root)["status"], "pass")
        content = (self.root / contract.CONTRACT_PATH).read_text(encoding="utf-8")
        self.assertIn("current SR priority is lowered below 7", content)
        self.assertNotIn("a continuously high level does not create repeated interrupts", content)

    def test_mutated_opcode_scope_has_named_rejection(self):
        path = self.root / contract.CONTRACT_PATH
        content = path.read_text(encoding="utf-8")
        path.write_text(content.replace("0111 ddd 0 iiiiiiii", "0111 ??? changed"), encoding="utf-8")
        with self.assertRaises(contract.ContractError) as caught:
            contract.check_contract(self.root)
        self.assertEqual(caught.exception.reason, "opcode_scope")

    def test_caps_are_frozen(self):
        ledger = self.read_ledger()
        ledger["caps"]["active_effort_seconds"] += 1
        self.write_ledger(ledger)
        with self.assertRaises(contract.ContractError) as caught:
            contract.validate_budget(self.root)
        self.assertEqual(caught.exception.reason, "caps_changed")

    def test_effort_is_summed_from_explicit_agent_intervals(self):
        ledger = self.read_ledger()
        ledger["entries"][0]["active_seconds"] = 2
        self.write_ledger(ledger)
        with self.assertRaises(contract.ContractError) as caught:
            contract.validate_budget(self.root)
        self.assertEqual(caught.exception.reason, "agent_intervals")

    def test_frozen_musashi_bytes_are_checked(self):
        path = self.root / "experiments/cpu/ACCEPTANCE.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nmutated\n", encoding="utf-8")
        with self.assertRaises(contract.ContractError) as caught:
            contract.check_history(self.root)
        self.assertEqual(caught.exception.reason, "historical_hash")

    def test_empty_required_ledger_records_are_rejected(self):
        ledger = self.read_ledger()
        ledger["entries"] = []
        self.write_ledger(ledger)
        with self.assertRaises(contract.ContractError) as caught:
            contract.validate_budget(self.root)
        self.assertEqual(caught.exception.reason, "required_records")

    def test_churn_threshold_is_a_pause_and_not_a_backend_rejection(self):
        ledger = self.read_ledger()
        ledger["entries"][-1]["cumulative_churn"]["runtime_added"] = contract.RUNTIME_CHURN_CAP + 1
        self.write_ledger(ledger)
        with self.assertRaises(contract.ContractError) as caught:
            contract.validate_budget(self.root)
        self.assertEqual(caught.exception.reason, "threshold_outcome")
        ledger["pause"] = {"active": True, "reason": "runtime-churn-threshold",
                           "disposition": "pause-for-user-scope-review"}
        self.write_ledger(ledger)
        result = contract.validate_budget(self.root)
        self.assertEqual(result["status"], "pause-for-review")
        self.assertEqual(result["phase_disposition"], "GAPS_FOUND")

    def test_cumulative_churn_cannot_refund_penultimate_threshold_crossing(self):
        ledger = self.read_ledger()
        penultimate_entry = json.loads(json.dumps(ledger["entries"][-1]))
        penultimate_entry["stage"] = "synthetic-penultimate-crossing"
        penultimate_entry["cumulative_churn"]["runtime_added"] = contract.RUNTIME_CHURN_CAP + 1
        final_entry = json.loads(json.dumps(ledger["entries"][-1]))
        final_entry["stage"] = "synthetic-final-under-limit"
        final_entry["cumulative_churn"] = {key: 0 for key in penultimate_entry["cumulative_churn"]}
        ledger["entries"].extend((penultimate_entry, final_entry))
        penultimate = ledger["entries"][-2]["cumulative_churn"]
        final = ledger["entries"][-1]["cumulative_churn"]
        self.assertLess(final["runtime_added"], contract.RUNTIME_CHURN_CAP + 1)
        self.assertEqual(penultimate["runtime_added"], contract.RUNTIME_CHURN_CAP + 1)
        self.write_ledger(ledger)

        with self.assertRaises(contract.ContractError) as caught:
            contract.validate_budget(self.root)
        self.assertEqual(caught.exception.reason, "cumulative_decrease")
        self.assertIn("runtime_added", str(caught.exception))
        self.assertIn(f"entry {len(ledger['entries']) - 1}", str(caught.exception))

    def test_record_measures_intervals_build_fixture_churn_and_ctest(self):
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Contract Test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "contract-test@example.invalid"],
                       cwd=self.root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "test baseline"], cwd=self.root, check=True)

        ledger_path = self.root / contract.LEDGER_PATH
        ledger = self.read_ledger()
        ledger["code_start"]["commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        ledger["code_start"]["contract_sha256"] = contract.sha256(self.root / contract.CONTRACT_PATH)
        self.write_ledger(ledger)

        runtime = self.root / "experiments/owned_cpu/cpu.c"
        runtime.parent.mkdir(parents=True, exist_ok=True)
        runtime.write_text("int owned_cpu_step(void) { return 1; }\n", encoding="utf-8")
        behavior = self.root / "tests/owned_cpu/test_behavior.c"
        behavior.parent.mkdir(parents=True, exist_ok=True)
        behavior.write_text("int test_owned_cpu(void) { return 1; }\n", encoding="utf-8")
        build = self.root / "build/owned-cpu"
        (build / "Testing/Temporary").mkdir(parents=True, exist_ok=True)
        (build / "CMakeCache.txt").write_text("CMAKE_BUILD_TYPE=Debug\n", encoding="utf-8")
        (build / "build.ninja").write_text("ninja_required_version = 1.10\n", encoding="utf-8")
        (build / "Testing/Temporary/LastTest.log").write_text(
            """Start testing: Oct 02 15:46 EDT
----------------------------------------------------------
1/1 Testing: owned_cpu_contract
1/1 Test: owned_cpu_contract
Command: owned_cpu_contract
Test time =   0.01 sec
----------------------------------------------------------
Test Passed.
----------------------------------------------------------
End testing: Oct 02 15:46 EDT
""", encoding="utf-8")
        # CTest may leave this from an earlier run; LastTest.log is the current run's receipt.
        (build / "Testing/Temporary/LastTestsFailed.log").write_text(
            "owned_cpu_contract\n", encoding="utf-8")

        result = contract.record(
            self.root, "record-control", build,
            ["test-agent,2026-01-01T00:00:01Z,2026-01-01T00:00:03Z"],
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["active_seconds"], 2)
        self.assertEqual(result["build_dir"], "build/owned-cpu")
        self.assertEqual(result["cumulative_churn"]["runtime_added"], 1)
        self.assertEqual(result["cumulative_churn"]["test_tool_added"], 1)
        self.assertEqual(result["test_results"]["expected"], 1)
        self.assertEqual(result["test_results"]["observed"], 1)
        self.assertEqual(result["test_results"]["cases"], ["owned_cpu_contract"])
        self.assertFalse(result["diagnostic_gate"])
        self.assertNotIn(str(self.root), Path(ledger_path).read_text(encoding="utf-8"))

    def test_ctest_log_records_each_passed_test_block(self):
        build = self.root / "build/owned-cpu"
        temporary = build / "Testing/Temporary"
        temporary.mkdir(parents=True)
        (temporary / "LastTest.log").write_text(
            """Start testing: Oct 02 15:46 EDT
----------------------------------------------------------
1/2 Testing: owned_cpu_diagnostic
1/2 Test: owned_cpu_diagnostic
Command: owned_cpu_diagnostic
Test time =   0.00 sec
----------------------------------------------------------
Test Passed.
----------------------------------------------------------
2/2 Testing: owned_cpu_negative
2/2 Test: owned_cpu_negative
Command: owned_cpu_negative
Test time =   0.02 sec
----------------------------------------------------------
Test Passed.
----------------------------------------------------------
End testing: Oct 02 15:46 EDT
""", encoding="utf-8")
        (temporary / "LastTestsFailed.log").write_text(
            "owned_cpu_diagnostic\n", encoding="utf-8")

        results = contract._test_results(build)
        self.assertEqual(results["cases"], ["owned_cpu_diagnostic", "owned_cpu_negative"])
        self.assertEqual(results["expected"], 2)
        self.assertEqual(results["observed"], 2)
        self.assertEqual(results["status"], "pass")

        log = temporary / "LastTest.log"
        log.write_text(log.read_text(encoding="utf-8").replace(
            "Test Passed.", "Test Failed.", 1), encoding="utf-8")
        with self.assertRaises(contract.ContractError) as caught:
            contract._test_results(build)
        self.assertEqual(caught.exception.reason, "stage_test_results")

    def test_churn_counts_committed_lines_even_after_revert(self):
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Contract Test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "contract-test@example.invalid"],
                       cwd=self.root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "test baseline"], cwd=self.root, check=True)
        baseline = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()

        transient = self.root / "experiments/owned_cpu/transient.c"
        transient.parent.mkdir(parents=True, exist_ok=True)
        transient.write_text("int first(void) { return 1; }\nint second(void) { return 2; }\n",
                             encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "add transient runtime"],
                       cwd=self.root, check=True)
        transient.unlink()
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "revert transient runtime"],
                       cwd=self.root, check=True)

        self.assertEqual(contract._nonblank_numstat(
            self.root, baseline, ["experiments/owned_cpu/*.c"]), (2, 2))

    def test_diagnostic_gate_requires_both_named_guest_cases(self):
        with self.assertRaises(contract.ContractError) as caught:
            contract.check_diagnostic_gate(self.root)
        self.assertEqual(caught.exception.reason, "diagnostic_gate")

    def test_diagnostic_gate_rejects_malformed_case_names_explicitly(self):
        ledger = self.read_ledger()
        ledger["diagnostic_gate"]["status"] = "passed"
        ledger["diagnostic_gate"]["started_at"] = "2026-01-01T00:00:00Z"
        ledger["diagnostic_gate"]["completed_at"] = "2026-01-01T00:00:02Z"
        entry = dict(ledger["entries"][0])
        entry["stage"] = "diagnostic"
        entry["diagnostic_gate"] = True
        entry["test_results"] = {"expected": 2, "observed": 2, "status": "pass",
                                 "cases": ["owned_cpu_diagnostic", {"invalid": "name"}]}
        ledger["diagnostic_gate"]["active_seconds"] = entry["active_seconds"]
        ledger["entries"].append(entry)
        self.write_ledger(ledger)
        with self.assertRaises(contract.ContractError) as caught:
            contract.check_diagnostic_gate(self.root)
        self.assertEqual(caught.exception.reason, "diagnostic_gate")

    def test_self_test_has_nonempty_positive_and_negative_denominators(self):
        result = contract.self_test()
        self.assertGreater(result["positive_cases"], 0)
        self.assertGreater(result["negative_controls"], 0)
        self.assertEqual(result["status"], "pass")


if __name__ == "__main__":
    unittest.main()
