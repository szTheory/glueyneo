"""Controls for the proposed owned-core contract, budget, and frozen history."""

import json
from pathlib import Path
import tempfile
import unittest

from tools.owned_cpu import contract


class ContractControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="owned-cpu-contract-test-")
        self.root = Path(self.temporary.name)
        contract._copy_subject(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def read_ledger(self):
        return json.loads((self.root / contract.LEDGER_PATH).read_text(encoding="utf-8"))

    def write_ledger(self, ledger):
        contract._write_json(self.root / contract.LEDGER_PATH, ledger)

    def test_frozen_subject_and_pending_gate_validate(self):
        contract.check_contract(self.root)
        history = contract.check_history(self.root)
        self.assertEqual(len(contract.HISTORICAL_SHA256), len(history))
        self.assertTrue(contract.check_story(self.root)["valid"])
        contract.check_requirements(self.root)
        self.assertEqual(contract.validate_budget(self.root)["status"], "pass")

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

    def test_self_test_has_nonempty_positive_and_negative_denominators(self):
        result = contract.self_test()
        self.assertGreater(result["positive_cases"], 0)
        self.assertGreater(result["negative_controls"], 0)
        self.assertEqual(result["status"], "pass")


if __name__ == "__main__":
    unittest.main()
