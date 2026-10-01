"""MIT: consequential controls for CPU admission evidence."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cpu_audit", ROOT / "tools/cpu/audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class BudgetControls(unittest.TestCase):
    def test_budget_rejects_empty_ledger(self):
        self.assertFalse(audit.validate_budget({}), "empty ledger must not qualify")

if __name__ == "__main__":
    unittest.main()
