"""Nonempty corruption, classification, freshness and review controls."""
import copy
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.owned_cpu import acceptance as a

LEGACY_C14_PROFILE = "owned-p01-c14-1"
CONTINUATION_PROFILE = "owned-p01-c14-continuation-2"
LEGACY_C14_BOUNDARIES = (
    "reset_debt", "diagnostic_MOVEQ", "diagnostic_ADDQ", "diagnostic_MOVE_store",
    "STOP", "masked_IRQ", "IRQ7_edge_pending_after_deassertion", "IRQ_entry",
    "TRAP_entry", "canonical_unsupported", "privilege_entry", "address_error_entry", "RTE")
CONTINUATION_BOUNDARIES = LEGACY_C14_BOUNDARIES + ("RTE_odd_PC", "SR_switch_odd_USP")


def log_fixture(profile=None):
    blocks = []
    cases = a.CASES if profile is None else a.CURRENT_CASES
    unity = a.UNITY if profile is None else a.CURRENT_UNITY
    for index, name in enumerate(sorted(cases), 1):
        output = ""
        if name in unity:
            output += f"{unity[name]} Tests 0 Failures 0 Ignored\n"
        if name == "owned_cpu_state":
            output += "state_checkpoints=13 continuation_run_calls=91\n"
            if profile == LEGACY_C14_PROFILE:
                output = ("5 Tests 0 Failures 0 Ignored\n"
                          "state_checkpoints=13 continuation_run_calls=78 source_destroyed_and_overwritten=1\n"
                          "state_boundary_names=" + ",".join(LEGACY_C14_BOUNDARIES) + "\n")
            elif profile == CONTINUATION_PROFILE:
                output = ("5 Tests 0 Failures 0 Ignored\n"
                          "state_checkpoints=15 continuation_run_calls=90 source_destroyed_and_overwritten=1\n"
                          "state_boundary_names=" + ",".join(CONTINUATION_BOUNDARIES) + "\n")
        if name == "owned_cpu_isolation":
            output += "interleaved_pairs=32 boundaries_per_instance=6\nconcurrent_pairs=32 boundaries_per_instance=6\n"
        if name == "owned_cpu_cold":
            output += "PASS: cold_process_cases=16 fresh_processes=16 concurrent_instances=2\n"
        if name == "owned_cpu_negative":
            output += "PASS: diagnostic\nPASS: pending IRQ\nPASS: counter rejection\n"
        if name in ("owned_cpu_isolation_negative", "owned_cpu_timing_negative"):
            output += "PASS: exact control\n"
        if profile is not None and name in a.CONTROLS:
            output = "".join("PASS: " + control + "\n" for control in a.CONTROLS[name])
        if profile is not None and name == "owned_cpu_timing":
            source = (ROOT / "tests/owned_cpu/test_timing.c").read_text()
            native = re.findall(r"RUN_TEST\((\w+)\)", source)
            native = [case for case in native if not case.endswith("wrong_status_expectation") and not case.endswith("wrong_cycle_expectation")]
            if len(native) != 25:
                raise ValueError("declared current timing denominator changed")
            output += "".join("test.c:1:" + case + ":PASS\n" for case in native)
        blocks.append(f"{index}/{len(cases)} Testing: {name}\n{output}Test Passed.\n")
    return "".join(blocks)


def document_fixture(profile=None):
    log = log_fixture(profile)
    step = {"command": ["cmake", "--preset", "owned-debug"], "exit": 0,
            "status": "pass", "output": "", "output_sha256": hashlib.sha256(b"").hexdigest()}
    steps = [copy.deepcopy(step) for _ in range(3)]
    steps[1]["command"] = ["cmake", "--build", "--preset", "owned-debug", "--parallel", "2"]
    steps[2]["command"] = ["ctest", "--preset", "owned-debug", "--output-on-failure", "--no-tests=error"]
    lane = {"preset": "owned-debug", "optional": False, "status": "pass", "steps": steps,
            "test_log": log, "test_log_sha256": hashlib.sha256(log.encode()).hexdigest(),
            "counts": a.test_counts(log, profile), "artifacts": {
                "build/owned-debug/" + path: "a" * 64 for path in (
                    "CMakeCache.txt", "build.ninja", "compile_commands.json", "experiments/owned_cpu/libowned_cpu.a",
                    *("experiments/owned_cpu/" + name for name in a.inventory.EXECUTABLE_TARGETS))},
            "configuration": {"CMAKE_BUILD_TYPE": "Debug", "GLUEYNEO_CPU_EXPERIMENT": "OFF",
                              "GLUEYNEO_OWNED_CPU_EXPERIMENT": "ON", "GLUEYNEO_OWNED_CPU_OPTIMIZATION": "NONE",
                              "GLUEYNEO_OWNED_CPU_SANITIZER": "NONE"},
            "compiler": step | {"command": ["cc", "--version"]},
            "diagnostic_cost": step | {"command": ["$REPO/build/owned-debug/experiments/owned_cpu/owned_cpu_diagnostic"]}}
    record = {"revision": "a" * 40, "source_hashes": {"cpu.c": "a" * 64},
              "host": {"architecture": "test"}, "tools": {"cmake": "test"}, "runs": [lane]}
    if profile is not None:
        record.update(evidence_profile=profile, amendment_sha256=a.contract.ACTIVE_AMENDMENT_SHA256,
                      active_contract_identity_sha256=a.contract.ACTIVE_CONTRACT_IDENTITY_SHA256)
    record["sha256"] = a.digest(record)
    return {"schema": 1, "collections": [record], "disposition": "unqualified",
            "phase_disposition": "GAPS_FOUND", "blockers": ["review pending"]}


def rehash(document):
    record = document["collections"][0]
    record["sha256"] = a.digest({key: value for key, value in record.items() if key != "sha256"})


def current_review(record, revision="a" * 40):
    attestation = a.identity_binding(record, revision) | {
        "schema": 1, "independent_non_author": True, "hardware_saved_pc": "unknown",
        "prior_findings": {name: {"disposition": "superseded", "evidence": "exact bounded control/source reassessment"}
                           for name in a.PRIOR_FINDINGS}}
    section = "\n".join("## " + heading + "\n" + (revision if index == 0 else "explicit evidence")
                        for index, heading in enumerate(a.REVIEW_HEADINGS))
    section += ("\nIndependent reviewer: separate non-author agent\nAuthored runtime/collector/tests: no\n"
                "Disposition: clean\n```json\n" + json.dumps(attestation) + "\n```\n")
    return ("Historical F14-03 HIGH open retained\n<!-- owned-cpu-current-review:start -->\n" +
            section + "<!-- owned-cpu-current-review:end -->\n")


def current_security(record, revision="a" * 40):
    attestation = a.identity_binding(record, revision) | {
        "schema": 1, "asvs_level": 1, "block_on": "high", "independent_non_author": True,
        "status": "verified", "open_high_or_critical": 0}
    return ("Historical T-01-15-03 HIGH/open remains dated\n<!-- owned-cpu-current-security:start -->\n"
            "```json\n" + json.dumps(attestation) + "\n```\n<!-- owned-cpu-current-security:end -->\n")


class AcceptanceControls(unittest.TestCase):
    def test_deferred_seal_binds_review_security_and_never_admits(self):
        document = document_fixture(a.PROFILE)
        record = document["collections"][0]
        for lane in a.MANDATORY[1:]:
            row = copy.deepcopy(record["runs"][0])
            row["preset"] = lane
            row["steps"] = [step | {"command": command} for step, command in zip(row["steps"], a.lane_commands(lane))]
            row["configuration"] = a.lane_configuration(lane)
            row["artifacts"] = {path: "a" * 64 for path in a.lane_artifacts(lane)}
            row["diagnostic_cost"]["command"] = [f"$REPO/build/{lane}/experiments/owned_cpu/owned_cpu_diagnostic"]
            record["runs"].append(row)
        rehash(document)
        review_text, security_text = current_review(record), current_security(record)
        budget = {"status": "pass", "active_seconds": 40000, "runtime_churn_added_deleted": 1221,
                  "test_tool_churn_added_deleted": 6500}
        requirements = (ROOT / ".planning/REQUIREMENTS.md").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "experiments/owned_cpu").mkdir(parents=True)
            results = root / "experiments/owned_cpu/acceptance-results.json"
            review = root / "experiments/owned_cpu/REVIEW.md"
            security = root / "SECURITY.md"
            results.write_text(json.dumps(document))
            review.write_text(review_text)
            security.write_text(security_text)
            with patch.object(a, "ROOT", root), patch.object(a, "RESULTS", results), \
                    patch.object(a, "git", return_value="a" * 40), \
                    patch.object(a, "snapshot", return_value=record["source_hashes"]), \
                    patch.object(a.contract, "validate", return_value={"active_candidate_contract": {"amendment_sha256": a.contract.ACTIVE_AMENDMENT_SHA256}}), \
                    patch.object(a.contract, "validate_budget", return_value=budget), \
                    patch.object(a.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
                for path in (None, root / "missing.md"):
                    before = results.read_bytes()
                    with self.assertRaises((a.EvidenceError, OSError)):
                        a.seal(defer_admission=True, security=path)
                    self.assertEqual(before, results.read_bytes())
                with self.assertRaises(a.EvidenceError):
                    a.seal(require_accepted=True, defer_admission=True, security=security)
                security.write_text(security_text.replace('"verified"', '"blocked"'))
                with self.assertRaises(a.EvidenceError):
                    a.seal(defer_admission=True, security=security)
                security.write_text(security_text)
                result = a.seal(defer_admission=True, security=security)
                self.assertEqual({"disposition": "unqualified", "blockers": ["phase-goal-verification-pending"]}, result)
                sealed = json.loads(results.read_text())
                self.assertEqual("GAPS_FOUND", sealed["phase_disposition"])
                self.assertEqual(document["collections"], sealed["collections"])
                self.assertEqual(a.inventory.sha256(security), sealed["seal"]["security"]["sha256"])
                self.assertEqual("pass", a.verify(sealed)["status"])
                for path, original, match in ((review, review_text, "review"), (security, security_text, "security")):
                    path.write_text(original + "\nAudit bytes changed\n")
                    with self.assertRaisesRegex(a.EvidenceError, match):
                        a.verify(sealed)
                    path.write_text(original)
                for field, value in (("disposition", "accepted"), ("phase_disposition", "complete"), ("blockers", [])):
                    mutated = copy.deepcopy(sealed)
                    mutated[field] = value
                    with self.assertRaises(a.EvidenceError):
                        a.verify(mutated)
                modified = copy.deepcopy(sealed)
                modified["seal"]["security"]["attestation"]["open_high_or_critical"] = 1
                with self.assertRaises(a.EvidenceError):
                    a.verify(modified, False)
                modified = copy.deepcopy(sealed)
                modified["seal"]["review"]["attestation"]["source_map_sha256"] = "0" * 64
                with self.assertRaises(a.EvidenceError):
                    a.verify(modified, False)
        self.assertEqual(requirements, (ROOT / ".planning/REQUIREMENTS.md").read_bytes())

    def test_immutable_real_legacy_and_new_profile_counts(self):
        path = ROOT / "experiments/owned_cpu/acceptance-results.json"
        before = path.read_bytes()
        legacy = json.loads(before)
        self.assertEqual("pass", a.verify(legacy, False)["status"])
        self.assertEqual(before, path.read_bytes())
        current = document_fixture(a.PROFILE)
        self.assertEqual("pass", a.verify(current, False)["status"])
        counts = current["collections"][0]["runs"][0]["counts"]
        self.assertEqual((13, 6, 15, 90), (counts["ctest_observed"], counts["negative_controls"],
                                       counts["state_checkpoints"], counts["continuation_run_calls"]))
        self.assertEqual(25, counts["unity"]["owned_cpu_timing"])
        previous = document_fixture(LEGACY_C14_PROFILE)
        previous_counts = previous["collections"][0]["runs"][0]["counts"]
        self.assertEqual((13, 13, 78), (previous_counts["ctest_observed"],
                                        previous_counts["state_checkpoints"],
                                        previous_counts["continuation_run_calls"]))
        self.assertEqual("pass", a.verify(previous, False)["status"])
        old_log = log_fixture(LEGACY_C14_PROFILE)
        for mutated in (old_log.replace(",RTE\n", "\n", 1),
                        old_log.replace("RTE", "TRAP_entry", 1),
                        old_log.replace("continuation_run_calls=78", "continuation_run_calls=90", 1)):
            with self.subTest(old_profile_mutation=mutated[-180:]), self.assertRaises(a.EvidenceError):
                a.test_counts(mutated, LEGACY_C14_PROFILE)

    def test_continuation_profile_keeps_the_old_denominator_and_rejects_rehashed_spoofs(self):
        old_log = log_fixture(LEGACY_C14_PROFILE)
        old_counts = a.test_counts(old_log, LEGACY_C14_PROFILE)
        self.assertEqual((13, 78), (old_counts["state_checkpoints"], old_counts["continuation_run_calls"]))
        new_log = log_fixture(CONTINUATION_PROFILE)
        new_counts = a.test_counts(new_log, CONTINUATION_PROFILE)
        self.assertEqual((13, 15, 90), (new_counts["ctest_observed"], new_counts["state_checkpoints"],
                                        new_counts["continuation_run_calls"]))
        self.assertEqual(list(CONTINUATION_BOUNDARIES), new_counts["state_boundary_names"])

        for mutated in (
                new_log.replace("RTE_odd_PC,", "", 1),
                new_log.replace("RTE_odd_PC", "RTE", 1),
                new_log.replace("SR_switch_odd_USP", "foreign_boundary", 1),
                new_log.replace("continuation_run_calls=90", "continuation_run_calls=78", 1)):
            with self.subTest(mutated=mutated[-180:]), self.assertRaises(a.EvidenceError):
                a.test_counts(mutated, CONTINUATION_PROFILE)

        old = document_fixture(LEGACY_C14_PROFILE)
        lane = old["collections"][0]["runs"][0]
        lane["test_log"] = new_log
        lane["test_log_sha256"] = hashlib.sha256(new_log.encode()).hexdigest()
        lane["counts"] = new_counts
        old["collections"][0]["evidence_profile"] = CONTINUATION_PROFILE
        rehash(old)
        self.assertEqual("pass", a.verify(old, False)["status"])
        with patch.object(a, "snapshot", return_value=old["collections"][0]["source_hashes"]):
            with self.assertRaisesRegex(a.EvidenceError, "current qualification requires"):
                a.verify(document_fixture(LEGACY_C14_PROFILE))
        relabelled_old = document_fixture(LEGACY_C14_PROFILE)
        relabelled_old["collections"][0]["evidence_profile"] = CONTINUATION_PROFILE
        rehash(relabelled_old)
        with self.assertRaises(a.EvidenceError):
            a.verify(relabelled_old, False)
        relabeled = copy.deepcopy(old)
        relabeled["collections"][0]["runs"][0]["test_log"] = new_log.replace(
            "RTE_odd_PC", "", 1).replace("SR_switch_odd_USP", "", 1)
        relabeled["collections"][0]["runs"][0]["test_log_sha256"] = hashlib.sha256(
            relabeled["collections"][0]["runs"][0]["test_log"].encode()).hexdigest()
        relabeled["collections"][0]["sha256"] = a.digest({
            key: value for key, value in relabeled["collections"][0].items() if key != "sha256"})
        with self.assertRaises(a.EvidenceError):
            a.verify(relabeled, False)

    def test_rehashed_current_amendment_and_control_spoofs(self):
        original = document_fixture(a.PROFILE)
        for field in ("amendment_sha256", "active_contract_identity_sha256"):
            document = copy.deepcopy(original)
            document["collections"][0][field] = "0" * 64
            rehash(document)
            with self.assertRaisesRegex(a.EvidenceError, "amendment"):
                a.verify(document, False)
        original_log = log_fixture(a.PROFILE)
        for old, new in (("canonical_unsupported", "ILLEGAL_entry"), ("continuation_run_calls=90", "continuation_run_calls=0"),
                         ("wrong canonical unsupported status", "wrong unrelated status"),
                         ("25 Tests", "23 Tests"), ("TRAP_entry,", ""),
                         ("user_mode_privileged_instructions_raise_vector_eight:PASS", "fake_case:PASS")):
            document = copy.deepcopy(original)
            lane = document["collections"][0]["runs"][0]
            lane["test_log"] = original_log.replace(old, new)
            lane["test_log_sha256"] = hashlib.sha256(lane["test_log"].encode()).hexdigest()
            rehash(document)
            with self.subTest(old=old), self.assertRaises(a.EvidenceError):
                a.verify(document, False)

    def test_current_source_requires_current_profile(self):
        document = document_fixture()
        with patch.object(a, "snapshot", return_value=document["collections"][0]["source_hashes"]):
            with self.assertRaisesRegex(a.EvidenceError, "current qualification requires"):
                a.verify(document)

    def test_current_review_bounds_crosswalk_and_identities(self):
        record = document_fixture(a.PROFILE)["collections"][0]
        text = current_review(record)
        self.assertEqual("clean", a.review_text(text, "a" * 40, record)["status"])
        for broken in (text + text, text.replace("review:end", "review:missing"),
                       text.replace("review:start", "review:missing"),
                       text.replace('"F14-03":', '"missing":'), text.replace('"superseded"', '"open"'),
                       text.replace('"unknown"', '"selected"'), text.replace(record["sha256"], "0" * 64),
                       text.replace("Disposition: clean", "Disposition: clean\nHIGH finding open"),
                       text.replace("Disposition: clean", "Disposition: clean\nopen HIGH finding"),
                       text.replace("Disposition: clean", "Disposition: clean\n### New finding\nSeverity: HIGH\nStatus: open"),
                       text.replace("Disposition: clean", "Disposition: clean\n### New finding\n**Severity:** CRITICAL\n**Status:** open"),
                       text.replace("Disposition: clean", "Disposition: clean\nDisposition: clean"),
                       text.replace('"schema": 1', '"schema": true'),
                       text.replace('"independent_non_author": true', '"independent_non_author": false'),
                       text.replace('"evidence": "exact bounded control/source reassessment"', '"evidence": ""')):
            with self.subTest(broken=broken[-120:]), self.assertRaises(a.EvidenceError):
                a.review_text(broken, "a" * 40, record)

    def test_security_rejects_missing_duplicate_malformed_stale_and_blocked(self):
        record = document_fixture(a.PROFILE)["collections"][0]
        text = current_security(record)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SECURITY.md"
            path.write_text(text)
            self.assertEqual("verified", a.security_check(path, "a" * 40, record)["attestation"]["status"])
            for broken in ("", text + text, text.replace("security:end", "security:missing"),
                           text.replace('"schema": 1', '"schema":'),
                           text.replace('"schema": 1', '"schema": 1, "schema": 1'),
                           text.replace('"schema": 1', '"schema": true'),
                           text.replace('"asvs_level": 1', '"asvs_level": true'),
                           text.replace('"asvs_level": 1', '"asvs_level": 2'),
                           text.replace('"block_on": "high"', '"block_on": "critical"'),
                           text.replace('"independent_non_author": true', '"independent_non_author": false'),
                           text.replace('"verified"', '"blocked"'),
                           text.replace('"open_high_or_critical": 0', '"open_high_or_critical": 1'),
                           text.replace('"open_high_or_critical": 0', '"open_high_or_critical": false'),
                           text.replace(record["sha256"], "0" * 64),
                           text.replace(record["amendment_sha256"], "0" * 64),
                           text.replace(a.digest(record["source_hashes"]), "0" * 64),
                           text.replace("a" * 40, "b" * 40)):
                path.write_text(broken)
                with self.subTest(broken=broken[-120:]), self.assertRaises(a.EvidenceError):
                    a.security_check(path, "a" * 40, record)

    def test_current_profile_rejects_unknown_and_legacy_relabel(self):
        for profile in ("unknown", "owned-p01-c14-1", None):
            document = document_fixture()
            record = document["collections"][0]
            record["evidence_profile"] = profile
            record["amendment_sha256"] = a.contract.ACTIVE_AMENDMENT_SHA256
            rehash(document)
            with self.subTest(profile=profile), self.assertRaises(a.EvidenceError):
                a.verify(document, False)

    def test_budget_check_includes_exact_limits_and_rejects_overages_or_pause(self):
        good = {"status": "pass", "active_seconds": 30000,
                "runtime_churn_added_deleted": 1206, "test_tool_churn_added_deleted": 4538,
                "pause": None}
        limits = {"active_seconds": a.contract.EFFORT_CAP_SECONDS,
                  "runtime_churn_added_deleted": a.contract.RUNTIME_CHURN_CAP,
                  "test_tool_churn_added_deleted": a.contract.TEST_TOOL_CHURN_CAP}
        for key, value in limits.items():
            with self.subTest(exact_limit=key):
                a.budget_check(good | {key: value})
        a.budget_check(good | limits)

        for key, value in limits.items():
            with self.subTest(over_limit=key), self.assertRaises(a.EvidenceError):
                a.budget_check(good | {key: value + 1})
        paused = good | {"status": "pause-for-review",
                         "pause": {"active": True, "reason": "runtime-churn-threshold"}}
        with self.assertRaises(a.EvidenceError):
            a.budget_check(paused)
        inconsistent_active_pause = good | {
            "pause": {"active": True, "reason": "scope-review"}}
        with self.assertRaises(a.EvidenceError):
            a.budget_check(inconsistent_active_pause)

        for key, invalid in (("active_seconds", 0), ("active_seconds", True),
                             ("runtime_churn_added_deleted", 1.5),
                             ("test_tool_churn_added_deleted", "8000")):
            with self.subTest(invalid=(key, invalid)), self.assertRaises(a.EvidenceError):
                a.budget_check(good | {key: invalid})
    def test_positive_fixture_has_nonzero_counts(self):
        document = document_fixture()
        self.assertEqual("pass", a.verify(document, False)["status"])
        self.assertEqual(12, document["collections"][0]["runs"][0]["counts"]["ctest_observed"])

    def test_empty_and_corrupt_evidence(self):
        for document in ({"schema": 1, "collections": []}, {"schema": 1, "collections": [{"sha256": "0" * 64}]}):
            with self.assertRaises(a.EvidenceError):
                a.verify(document, False)

    def test_rehashed_real_asan_configuration_and_command_cannot_false_green(self):
        original = json.loads((ROOT / "experiments/owned_cpu/acceptance-results.json").read_text())
        for mutation in ("sanitizer", "command", "build_command", "test_command", "build_type", "status",
                         "compiler_output", "diagnostic_exit", "diagnostic_output", "artifact_missing", "artifact_digest"):
            document = copy.deepcopy(original)
            lane = next(row for row in document["collections"][0]["runs"] if row["preset"] == "owned-asan-ubsan")
            if mutation == "sanitizer": lane["configuration"]["GLUEYNEO_OWNED_CPU_SANITIZER"] = "NONE"
            elif mutation == "command": lane["steps"][0]["command"] = ["true"]
            elif mutation == "build_command": lane["steps"][1]["command"] = ["true"]
            elif mutation == "test_command": lane["steps"][2]["command"] = ["true"]
            elif mutation == "build_type": lane["configuration"]["CMAKE_BUILD_TYPE"] = "Release"
            elif mutation == "status": lane["steps"][0]["status"] = "unknown"
            elif mutation == "compiler_output": lane["compiler"]["output"] += "tampered"
            elif mutation == "diagnostic_exit": lane["diagnostic_cost"]["exit"] = 1
            elif mutation == "diagnostic_output": lane["diagnostic_cost"]["output"] += "tampered"
            elif mutation == "artifact_missing": lane["artifacts"].pop(next(iter(lane["artifacts"])))
            else: lane["artifacts"][next(iter(lane["artifacts"]))] = "not a digest"
            rehash(document)
            with self.subTest(mutation=mutation), self.assertRaises(a.EvidenceError):
                a.verify(document, False)

    def test_accepted_history_cannot_silently_replace_failure(self):
        document = document_fixture()
        latest = document["collections"][0]
        for name in a.MANDATORY[1:]:
            row = copy.deepcopy(latest["runs"][0])
            row["preset"] = name
            row["artifacts"] = {path.replace("owned-debug", name): value for path, value in row["artifacts"].items()}
            for step in row["steps"]:
                step["command"] = [name if item == "owned-debug" else item for item in step["command"]]
            row["configuration"].update({"CMAKE_BUILD_TYPE": "Release" if name == "owned-release" else "Debug",
                                         "GLUEYNEO_OWNED_CPU_OPTIMIZATION": "RELEASE" if name == "owned-release" else "NONE",
                                         "GLUEYNEO_OWNED_CPU_SANITIZER": "ADDRESS_UNDEFINED" if name == "owned-asan-ubsan" else "NONE"})
            row["diagnostic_cost"]["command"] = [f"$REPO/build/{name}/experiments/owned_cpu/owned_cpu_diagnostic"]
            latest["runs"].append(row)
        rehash(document)
        document.update(disposition="accepted", seal={"review": {"status": "clean"}, "collection_sha256": latest["sha256"]})
        a.verify(document, False)
        for status in ("fail", "unknown", "skipped"):
            mutated = copy.deepcopy(document)
            historical = copy.deepcopy(latest)
            historical["runs"][0]["status"] = status
            historical["sha256"] = a.digest({key: value for key, value in historical.items() if key != "sha256"})
            mutated["collections"].insert(0, historical)
            with self.subTest(status=status), self.assertRaisesRegex(a.EvidenceError, "earlier collection"):
                a.verify(mutated, False)

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
