"""Adversarial controls for the Phase 01 admission recommendation."""

import copy
import sys
import unittest
from pathlib import Path

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
        "requirements": copy.deepcopy(requirements or {
            key: {"decision": "sufficient", "evidence": evidence(), "limitation": "bounded evidence"}
            for key in REQUIREMENTS}),
        "open_high_or_critical": open_high,
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
    reqs = copy.deepcopy(REQUIREMENTS)
    reqs["CPU-02"] = "blocked"
    review_reqs = {
        key: {"decision": reqs[key], "evidence": evidence(), "limitation": "bounded evidence"}
        for key in reqs}
    review = report("cpu-admission-review", "reviewer-a", review_reqs, blocker)
    security = report("cpu-admission-security", "assessor-b")
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
        "security": {"open_high_or_critical": 0},
        "blocker": copy.deepcopy(blocker),
    }
    return decision, review, security


class TerminalControls(unittest.TestCase):
    def test_precise_blocked_record_is_valid_but_never_admits(self):
        decision, review, security = blocked_fixture()
        result = admission.validate_terminal(decision, review, security)
        self.assertEqual("blocked", result["disposition"])
        self.assertIs(False, result["phase_admitted"])
        self.assertEqual("CPU-02", result["blocker"]["requirement"])


if __name__ == "__main__":
    unittest.main()
