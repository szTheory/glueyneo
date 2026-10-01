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


if __name__ == "__main__":
    unittest.main()
