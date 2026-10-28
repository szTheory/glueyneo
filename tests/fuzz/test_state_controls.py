#!/usr/bin/env python3
"""Reporter-backed regression for the native YM IRQ bypass control."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE = ROOT / "build" / "sdk-debug" / "sdk_state_mutation"


class StateControlTests(unittest.TestCase):
    def test_ym_irq_relation_bypass_reaches_expected_acceptance(self) -> None:
        result = subprocess.run(
            [str(EXECUTABLE), "negative-control-ym-irq-relation"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, output)
        self.assertIn(
            "sdk.state.hostile.negative-control-ym-irq-relation-is-active "
            "expected=3 observed=3",
            output,
        )
        self.assertIn(
            "SDK_STATE_NEGATIVE_CONTROL "
            "accepted_disabled_validator=ym-irq-relation",
            output,
        )
        self.assertIn(
            "sdk.state.hostile.negative-control.expected-rejection "
            "expected=3 observed=0",
            output,
        )


if __name__ == "__main__":
    unittest.main()
