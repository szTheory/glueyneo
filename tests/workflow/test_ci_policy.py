#!/usr/bin/env python3
"""Fail-closed controls for CI path classification and required aggregation."""

from __future__ import annotations

import io
import sys
import tempfile
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "workflow"))
import ci_policy as policy  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
import sdk_evidence as evidence  # noqa: E402
import verify_sdk  # noqa: E402


class ExampleRoutingTests(TestCase):
    def test_example_helper_change_routes_runtime(self):
        runtime_paths = (
            "CMakeLists.txt",
            "examples/continuation.c",
            "examples/persistence.c",
            "examples/persistence_host.c",
            "examples/persistence_host.h",
            "tests/fixture/public_persistence_guest.c",
            "tests/consumers/test_example_docs.py",
            "tests/consumers/test_continuation_install.py",
            "tests/consumers/test_persistence_install.py",
            "tests/consumers/test_release_consumer.py",
            "tests/consumers/test_check_package.py",
            "tools/release_manifest.py",
            "tools/release_state.py",
            "tools/sdk_evidence.py",
            "tools/verify_sdk.py",
            "tools/workflow/ci_policy.py",
        )
        for path in runtime_paths:
            with self.subTest(path=path):
                self.assertEqual(policy.classify_paths([path]), set(policy.REQUIRED_JOBS))
        self.assertEqual(policy.classify_paths(["docs/sdk-examples.md"]), {policy.DOCS_JOB})
        self.assertEqual(policy.classify_paths(["docs/new-helper.py"]), set(policy.REQUIRED_JOBS))
        expected_sources = set(runtime_paths) | {
            "docs/sdk-examples.md", "docs/native-state.md", "docs/native-save.md",
            "docs/testing.md", "docs/frontend-continuation.md", "docs/releasing.md",
            "docs/ownership-and-errors.md", "tests/fixture/public_save_guest.c",
        }
        self.assertTrue(expected_sources <= set(evidence.RELEVANT_FILES))

    def test_exact_example_inventory(self):
        expected = {
            "sdk_example_continuation_static",
            "sdk_example_continuation_shared",
            "sdk_example_persistence_static",
            "sdk_example_persistence_shared",
            "sdk_example_persistence_faults",
        }
        self.assertEqual(verify_sdk.EXAMPLE_CTEST_CASES, expected)
        self.assertEqual(verify_sdk.validate_example_inventory(len(expected), sorted(expected)), len(expected))
        missing = sorted(expected - {"sdk_example_persistence_faults"})
        duplicate = sorted(expected) + ["sdk_example_persistence_static"]
        for denominator, names in (
            (len(missing), missing),
            (len(duplicate), duplicate),
            (0, []),
        ):
            with self.subTest(denominator=denominator, names=names), self.assertRaises(
                    verify_sdk.VerificationError):
                verify_sdk.validate_example_inventory(denominator, names)


class PublicContentSummaryTests(TestCase):
    def run_output(self, output, returncode):
        result = subprocess.CompletedProcess(
            [sys.executable, "-c", "synthetic"], returncode, output, "",
        )
        with mock.patch.object(policy.subprocess, "run", return_value=result):
            return policy.public_content_control_counts(ROOT)

    def run_summary(self, summary, returncode, *, extra_output=""):
        output = "PUBLIC_CONTENT_RESULT=" + json.dumps(summary) + "\n" + extra_output
        return self.run_output(output, returncode)

    def test_pass_summary_rejects_nonzero_failure_count(self):
        summary = {
            "schema_version": 1, "assertions": 1, "cases": 1,
            "failure_count": 1, "expected_failure_count": 0, "skipped_count": 0,
            "unexpected_success_count": 0,
            "nonpassing_test_ids": ["module.Tests.test_failure"],
            "nonpassing_test_ids_truncated": False, "outcome": "pass",
        }
        with self.assertRaisesRegex(ValueError, "failed|omitted|invalid"):
            self.run_summary(summary, returncode=0)

    def test_pass_summary_requires_exact_schema_and_field_types(self):
        valid = {
            "schema_version": 1, "assertions": 1, "cases": 1,
            "failure_count": 0, "expected_failure_count": 0, "skipped_count": 0,
            "unexpected_success_count": 0, "nonpassing_test_ids": [],
            "nonpassing_test_ids_truncated": False, "outcome": "pass",
        }
        invalid_rows = (
            dict(valid, schema_version=True),
            dict(valid, cases=True),
            dict(valid, assertions=False),
            dict(valid, failure_count=False),
            dict(valid, expected_failure_count=True),
            dict(valid, skipped_count=False),
            dict(valid, unexpected_success_count=0.0),
            dict(valid, nonpassing_test_ids=[{}]),
            dict(valid, nonpassing_test_ids_truncated=0),
            dict(valid, unexpected="extra"),
        )
        for row in invalid_rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.run_summary(row, returncode=0)

    def test_failure_identifier_is_scanned_before_diagnostic(self):
        summary = {
            "schema_version": 1, "assertions": 1, "cases": 1,
            "failure_count": 1, "expected_failure_count": 0, "skipped_count": 0,
            "unexpected_success_count": 0,
            "nonpassing_test_ids": ["module.Tests.ghp_" + ("A" * 36)],
            "nonpassing_test_ids_truncated": False, "outcome": "fail",
        }
        with self.assertRaises(ValueError) as caught:
            self.run_summary(summary, returncode=1)
        self.assertNotIn("ghp_", str(caught.exception))
        self.assertLessEqual(len(str(caught.exception)), 1024)

    def test_large_failure_counts_keep_diagnostic_bounded(self):
        summary = {
            "schema_version": 1, "assertions": 1, "cases": 10 ** 1400,
            "failure_count": 10 ** 1400, "expected_failure_count": 0,
            "skipped_count": 0, "unexpected_success_count": 0,
            "nonpassing_test_ids": ["module.Tests.test_failure"],
            "nonpassing_test_ids_truncated": False, "outcome": "fail",
        }
        with self.assertRaises(ValueError) as caught:
            self.run_summary(summary, returncode=1)
        self.assertLessEqual(len(str(caught.exception)), 1024)

    def test_duplicate_result_records_are_rejected(self):
        actual = {
            "schema_version": 1, "assertions": 1, "cases": 27,
            "failure_count": 0, "expected_failure_count": 0, "skipped_count": 0,
            "unexpected_success_count": 0, "nonpassing_test_ids": [],
            "nonpassing_test_ids_truncated": False, "outcome": "pass",
        }
        forged = dict(actual, assertions=1)
        extra = "PUBLIC_CONTENT_RESULT=" + json.dumps(forged) + "\n"
        with self.assertRaisesRegex(ValueError, "duplicate|invalid|omitted"):
            self.run_summary(actual, returncode=0, extra_output=extra)

    def test_malformed_result_records_count_as_duplicates(self):
        valid = {
            "schema_version": 1, "assertions": 1, "cases": 1,
            "failure_count": 0, "expected_failure_count": 0, "skipped_count": 0,
            "unexpected_success_count": 0, "nonpassing_test_ids": [],
            "nonpassing_test_ids_truncated": False, "outcome": "pass",
        }
        valid_line = "PUBLIC_CONTENT_RESULT=" + json.dumps(valid) + "\n"
        for malformed in ("PUBLIC_CONTENT_RESULT=\n",
                          "PUBLIC_CONTENT_RESULT=" + ("x" * 5000) + "\n"):
            with self.subTest(malformed_length=len(malformed)), self.assertRaises(ValueError):
                self.run_output(valid_line + malformed, returncode=0)

    def test_duplicate_json_object_keys_are_rejected(self):
        output = (
            'PUBLIC_CONTENT_RESULT={"schema_version":1,"assertions":0,'
            '"assertions":1,"cases":1,"failure_count":0,"expected_failure_count":0,'
            '"skipped_count":0,"unexpected_success_count":0,"nonpassing_test_ids":[],'
            '"nonpassing_test_ids_truncated":false,"outcome":"pass"}\n'
        )
        with self.assertRaises(ValueError):
            self.run_output(output, returncode=0)

    def test_expected_failures_and_skips_are_rejected_by_producer(self):
        with tempfile.TemporaryDirectory(prefix="ci-content-status-") as temp:
            root = Path(temp)
            workflow_tests = root / "tests" / "workflow"
            workflow_tests.mkdir(parents=True)
            (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
            (workflow_tests / "__init__.py").write_text("", encoding="utf-8")
            (workflow_tests / "test_public_content.py").write_text(
                "import unittest\n"
                "class OutcomeTests(unittest.TestCase):\n"
                "    @unittest.expectedFailure\n"
                "    def test_expected_failure(self):\n"
                "        self.fail('synthetic')\n"
                "    @unittest.skip('synthetic')\n"
                "    def test_skipped(self):\n"
                "        self.assertTrue(True)\n"
                "    def test_passing_control(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "expected_failures=1; skipped=1") as caught:
                policy.public_content_control_counts(root)
            self.assertIn("test_public_content.OutcomeTests.test_expected_failure",
                          str(caught.exception))
            self.assertIn("test_public_content.OutcomeTests.test_skipped", str(caught.exception))


def expect(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def check_public_content_failure_diagnostics() -> None:
    with tempfile.TemporaryDirectory(prefix="ci-content-failure-") as temp:
        root = Path(temp)
        workflow_tests = root / "tests" / "workflow"
        workflow_tests.mkdir(parents=True)
        (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (workflow_tests / "__init__.py").write_text("", encoding="utf-8")
        failure_methods = "".join(
            f"    def test_failure_{index}(self):\n        self.fail(__file__)\n"
            for index in range(7)
        )
        (workflow_tests / "test_public_content.py").write_text(
            "import unittest\n"
            "class FailureTests(unittest.TestCase):\n" + failure_methods,
            encoding="utf-8",
        )
        try:
            policy.public_content_control_counts(root)
        except ValueError as error:
            diagnostic = str(error)
            expect("returncode=1" in diagnostic,
                   "public-content failure diagnostics must include the child return code")
            expect("failures=7" in diagnostic,
                   "public-content failure diagnostics must count all failing controls")
            expect("test_public_content.FailureTests.test_failure_0" in diagnostic and
                   "test_public_content.FailureTests.test_failure_4" in diagnostic,
                   "public-content failure diagnostics must include a safe failing test identifier")
            expect("test_failure_5" not in diagnostic and "test_ids_truncated=true" in diagnostic,
                   "public-content failure diagnostics must cap and mark its test identifier list")
            expect(str(root) not in diagnostic,
                   "public-content failure diagnostics must not include the temporary host path")
            expect(len(diagnostic) <= 1024,
                   "public-content failure diagnostics must remain bounded")
        else:
            raise AssertionError("failing public-content controls must remain a failure")


def check_public_content_summary_controls() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PublicContentSummaryTests)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    expect(result.wasSuccessful(), "public-content result summary controls must pass")


def check_public_content_handoff() -> tuple[int, int]:
    """Exercise the public-content producer's serialized artifact through aggregation."""
    actual_cases, actual_assertions = policy.public_content_control_counts(ROOT)
    expect(actual_cases == 27 and actual_assertions > actual_cases,
           "public-content controls must report the current 27 cases and measured assertion calls")
    with tempfile.TemporaryDirectory(prefix="ci-content-handoff-") as temp:
        root = Path(temp) / "source"
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / ".gitignore").write_text("/build/\n", encoding="utf-8")
        (root / "README.md").write_text("synthetic public source\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore", "README.md"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.name=Public User", "-c",
                        "user.email=public@example.org", "commit", "-qm", "source"],
                       cwd=root, check=True)
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                                  text=True, stdout=subprocess.PIPE).stdout.strip()
        raw_report = {
            "schema": 1, "outcome": "pass", "findings": [],
            "detector_negative_only": True,
            "counts": {"source": {"files": 4, "bytes": 40},
                       "history": {"files": 23, "bytes": 230},
                       "logs": {"files": 0, "bytes": 0},
                       "archives": {"files": 0, "bytes": 0}},
            "coverage": {"logs_supplied": 0, "archives_supplied": 0,
                         "history_mode": "all reachable refs", "history_revision": "--all",
                         "history_scope": "objects available in this checkout"},
        }

        def run_public_content(argv, **_kwargs):
            if argv[:2] == ["git", "rev-parse"]:
                return subprocess.CompletedProcess(argv, 0, revision + "\n", "")
            if argv[:2] == ["git", "status"]:
                return subprocess.CompletedProcess(argv, 0, "", "")
            if len(argv) > 1 and argv[1] == "-c":
                result = {"schema_version": 1,
                          "assertions": actual_assertions, "cases": actual_cases,
                          "failure_count": 0, "expected_failure_count": 0,
                          "skipped_count": 0, "unexpected_success_count": 0,
                          "nonpassing_test_ids": [],
                          "nonpassing_test_ids_truncated": False, "outcome": "pass"}
                return subprocess.CompletedProcess(
                    argv, 0, "PUBLIC_CONTENT_RESULT=" + json.dumps(result) + "\n", "",
                )
            report_index = argv.index("--json") + 1
            Path(argv[report_index]).write_bytes(evidence.canonical_bytes(raw_report))
            return subprocess.CompletedProcess(argv, 0, "", "")

        receipt_path = root / "build/verify-sdk/public-content-receipt.json"
        previous_argv = sys.argv
        try:
            sys.argv = ["ci_policy.py", "produce-public-content", "--root", str(root),
                        "--source-revision", revision, "--report-output",
                        "build/verify-sdk/public-content.json", "--output",
                        "build/verify-sdk/public-content-receipt.json"]
            with mock.patch.object(policy.subprocess, "run", side_effect=run_public_content):
                expect(policy.main() == 0, "public-content producer should serialize a passing receipt")
        finally:
            sys.argv = previous_argv

        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        report_path = root / "build/verify-sdk/public-content.json"
        expect(receipt.get("source_revision") == revision and
               receipt.get("working_tree_dirty") is False,
               "producer receipt must bind the clean immutable source revision")
        expect(receipt.get("control_cases") == actual_cases and
               receipt.get("assertion_count") == actual_assertions
               and receipt.get("assertion_count_basis") ==
                   "unittest.TestCase assertion/fail method calls"
               and receipt.get("scanned_files") == 27,
               "producer must keep control cases, actual assertion calls, and scanned files distinct")
        expect(receipt.get("lane_execution_count") == 1 and
               receipt.get("report_sha256") == evidence.sha256_bytes(report_path.read_bytes()),
               "producer receipt must bind positive execution and the exact scanner artifact")

        artifact_dir = Path(temp) / "artifacts/public-content"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "public-content.json").write_bytes(report_path.read_bytes())
        (artifact_dir / "public-content-receipt.json").write_bytes(receipt_path.read_bytes())
        matrix_log_report = json.loads(json.dumps(raw_report))
        matrix_log_report["coverage"] = {
            "logs_supplied": 6, "archives_supplied": 0,
            "history_mode": "selected revision", "history_revision": revision,
            "history_scope": "objects available in this checkout",
        }
        (artifact_dir / "matrix-logs.json").write_bytes(evidence.canonical_bytes(matrix_log_report))
        matrix_dir = Path(temp) / "matrix"
        matrix_dir.mkdir()
        for lane in evidence.REQUIRED_MATRIX_LANES:
            os_name, compiler_ids, architectures = evidence.MATRIX_LANE_IDENTITY[lane]
            row = {
                "lane": lane, "compiler": {"id": next(iter(compiler_ids)), "version": "18.1"},
                "sdk": {"name": "test-sdk", "version": "1.0"},
                "os_image": {"Linux": "ubuntu-test", "Darwin": "macos-test",
                             "Windows": "windows-test"}[os_name],
                "os": os_name, "architecture": next(iter(architectures)),
                "configuration": "Debug", "source_revision": revision,
                "working_tree_dirty": False,
                "build_identity": {"cmake": "3.31", "generator": "Ninja 1.13",
                                   "fixture_sha256": "b" * 64},
                "outcome": "pass", "assertions": 3, "duration_seconds": 6.0,
                "cold_build_seconds": 1.0, "runner_id": f"runner-{lane}",
                "runner_minutes": 0.1,
            }
            (matrix_dir / f"{lane}.json").write_bytes(evidence.canonical_bytes(row))

        def aggregate_with_environment(output_dir: Path, *, matrix_result: str,
                                       matrix_planned: bool):
            input_artifacts = output_dir / "public-content"
            input_artifacts.mkdir(parents=True)
            for artifact in artifact_dir.iterdir():
                (input_artifacts / artifact.name).write_bytes(artifact.read_bytes())
            values = {"CLASSIFY_RESULT": "success", "MATRIX_RESULT": matrix_result,
                      "PUBLIC_CONTENT_RESULT": "success",
                      "MATRIX_PLANNED": "true" if matrix_planned else "false",
                      "CONTENT_PLANNED": "true", "SOURCE_REVISION": revision}
            with mock.patch.dict(os.environ, values):
                plan_path, results_path = policy.prepare_workflow_inputs(output_dir)
            return policy.assemble_aggregate(json.loads(results_path.read_text()),
                                             json.loads(plan_path.read_text()), matrix_dir)

        docs_only = aggregate_with_environment(Path(temp) / "docs-only", matrix_result="skipped",
                                               matrix_planned=False)
        expect(docs_only["outcome"] == "pass" and
               docs_only["jobs"][policy.DOCS_JOB]["assertion_count"] == actual_assertions,
               "aggregator should accept the actual serialized passing public-content artifact")

        matrix_success = aggregate_with_environment(Path(temp) / "matrix-success", matrix_result="success",
                                                    matrix_planned=True)
        expect(matrix_success["outcome"] == "pass" and
               matrix_success["jobs"][policy.DOCS_JOB]["assertion_count"] == actual_assertions,
               "aggregator should also accept the producer receipt with current-source scanned matrix logs")

        matrix_failed = aggregate_with_environment(Path(temp) / "matrix-failed", matrix_result="failure",
                                                   matrix_planned=True)
        expect(matrix_failed["outcome"] == "fail" and
               matrix_failed["jobs"][policy.DOCS_JOB]["assertion_count"] == actual_assertions and
               any("required job did not succeed: matrix" in issue
                   for issue in matrix_failed["issues"]),
               "passing content evidence must not mask the original required matrix failure")

        malformed_receipts = (
            ("empty lane", {"lane_execution_count": 0}),
            ("boolean lane", {"lane_execution_count": True}),
            ("zero assertions", {"assertion_count": 0}),
            ("boolean assertions", {"assertion_count": True}),
            ("zero controls", {"control_cases": 0}),
            ("boolean controls", {"control_cases": True}),
            ("boolean scanned files", {"scanned_files": True}),
            ("stale source", {"source_revision": "b" * 40}),
            ("stale report digest", {"report_sha256": "c" * 64}),
        )
        for index, (label, changes) in enumerate(malformed_receipts):
            malformed = dict(receipt, **changes)
            (artifact_dir / "public-content-receipt.json").write_bytes(
                evidence.canonical_bytes(malformed))
            rejected = aggregate_with_environment(Path(temp) / f"malformed-{index}",
                                                  matrix_result="skipped", matrix_planned=False)
            expect(rejected["outcome"] == "fail",
                   f"{label} producer artifact must fail closed")
        malformed_scan = json.loads(json.dumps(raw_report))
        malformed_scan["counts"]["source"]["files"] = True
        malformed_scan_bytes = evidence.canonical_bytes(malformed_scan)
        (artifact_dir / "public-content.json").write_bytes(malformed_scan_bytes)
        (artifact_dir / "public-content-receipt.json").write_bytes(evidence.canonical_bytes(
            dict(receipt, report_sha256=evidence.sha256_bytes(malformed_scan_bytes), scanned_files=24)))
        malformed_count = aggregate_with_environment(Path(temp) / "malformed-scan-count",
                                                     matrix_result="skipped", matrix_planned=False)
        expect(malformed_count["outcome"] == "fail",
               "boolean raw scanner counts must fail closed even with a matching report digest")
        (artifact_dir / "public-content.json").write_bytes(report_path.read_bytes())
        (artifact_dir / "public-content-receipt.json").write_bytes(receipt_path.read_bytes())
    return actual_cases, actual_assertions


def main() -> int:
    hosted = sys.argv[1:] == ["--hosted"]
    if sys.argv[1:] and not hosted:
        raise SystemExit("usage: test_ci_policy.py [--hosted]")

    with tempfile.TemporaryDirectory(prefix="ci-prepare-cli-") as temp:
        output_dir = Path(temp) / "inputs"
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/workflow/ci_policy.py"), "prepare",
             "--output-dir", str(output_dir)], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        expect(completed.returncode == 0 and json.loads(completed.stdout)["outcome"] == "pass",
               "prepare CLI must complete without assuming the classify --output argument")
        expect((output_dir / "plan.json").is_file() and (output_dir / "results.json").is_file(),
               "prepare CLI must write its two expected inputs")

    private_path = os.path.expanduser("~") + "/private-ci-log.txt"
    windows_path = "\\".join(("C:", "Users", "synthetic-user", "AppData", "private.log"))
    fake_token = "ghp_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    fake_bearer = "Bearer " + "synthetic-token-value"
    fake_identity = "runner-user" + "@" + "private.invalid"
    fake_key_header = "-----BEGIN " + "OPENSSH PRIVATE KEY-----"
    diagnostic = verify_sdk.redacted_failure_diagnostic(
        "compile failed at " + private_path + " " + windows_path + " token=" + fake_token + " " +
        fake_bearer + " " + fake_identity + " " + fake_key_header +
        "\nsynthetic-key\n-----END OPENSSH PRIVATE KEY-----")
    expect(all(value not in diagnostic for value in
               (private_path, windows_path, fake_token, fake_bearer, fake_identity, fake_key_header)),
           "failure diagnostics must remove POSIX/Windows paths, keys, credentials and identities")
    expect("compile failed" in diagnostic, "failure diagnostics should retain safe stage details")
    raw_failure = "synthetic compiler output " + ("x" * 9000)
    failed_process = subprocess.CompletedProcess(["synthetic-compiler"], 1, stdout=raw_failure)
    with mock.patch.object(verify_sdk.subprocess, "run", return_value=failed_process), \
            mock.patch.object(verify_sdk, "preserve_output") as preserve:
        try:
            verify_sdk.run(["synthetic-compiler"])
        except verify_sdk.VerificationError:
            pass
        else:
            raise AssertionError("failed command must remain a verification failure")
        expect(preserve.call_args.args[1] == raw_failure,
               "complete raw subprocess output must remain in local private logs")
    with tempfile.TemporaryDirectory(prefix="matrix-failure-") as temp:
        receipt_path = Path(temp) / "matrix" / "linux-gcc.json"
        previous = sys.argv
        try:
            sys.argv = ["verify_sdk.py", "--suite", "matrix", "--lane", "linux-gcc",
                        "--output", str(receipt_path)]
            with mock.patch.dict(os.environ, {"SDK_SOURCE_REVISION": "a" * 40}), mock.patch.object(
                    verify_sdk, "suite_matrix", side_effect=verify_sdk.VerificationError("synthetic compiler stage failed")):
                code = verify_sdk.main()
        finally:
            sys.argv = previous
        failure = json.loads(receipt_path.read_text(encoding="utf-8"))
        expect(code == 1 and failure["outcome"] == "fail" and failure["stage"] == "linux-gcc",
               "verification exception must persist an explicit failed lane receipt")
        expect(failure["source_revision"] == "a" * 40,
               "failed lane receipt must bind the workflow-supplied exact source revision")
        expect("assertion_count" not in failure and "lane_count" not in failure,
               "failure receipt must not fabricate successful counts")

    # Merge readiness must bind both the required aggregate and the separate
    # GSD review to the exact proposed PR head.
    proposed_sha = "a" * 40
    receipt = {
        "schema_version": 1,
        "pr_head_sha": proposed_sha,
        "required_aggregate": {
            "sha": proposed_sha, "outcome": "pass", "lane_count": 6,
            "assertion_count": 120,
        },
        "independent_review": {
            "sha": proposed_sha, "review_type": "gsd-code-review", "outcome": "pass",
            "findings": [{"id": "R-1", "status": "dispositioned",
                          "disposition": "not-applicable", "evidence": "review note"}],
        },
    }
    expect(policy.validate_merge_readiness(receipt, proposed_sha=proposed_sha)["outcome"] == "pass",
           "complete exact-SHA aggregate and independent review must pass")
    for stale_field in ("pr_head_sha", "required_aggregate", "independent_review"):
        stale = json.loads(json.dumps(receipt))
        if stale_field == "required_aggregate":
            stale[stale_field]["sha"] = "b" * 40
        elif stale_field == "independent_review":
            stale[stale_field]["sha"] = "b" * 40
        else:
            stale[stale_field] = "b" * 40
        expect(policy.validate_merge_readiness(stale, proposed_sha=proposed_sha)["outcome"] == "fail",
               f"stale {stale_field} must reject merge readiness")
    open_finding = json.loads(json.dumps(receipt))
    open_finding["independent_review"]["findings"][0]["status"] = "open"
    expect(policy.validate_merge_readiness(open_finding, proposed_sha=proposed_sha)["outcome"] == "fail",
           "open review finding must reject merge readiness")
    unsupported_disposition = json.loads(json.dumps(receipt))
    unsupported_disposition["independent_review"]["findings"][0]["evidence"] = ""
    expect(policy.validate_merge_readiness(unsupported_disposition, proposed_sha=proposed_sha)["outcome"] == "fail",
           "finding disposition without evidence must reject merge readiness")
    resolved_without_evidence = json.loads(json.dumps(receipt))
    resolved_without_evidence["independent_review"]["findings"][0] = {"id": "R-1", "status": "resolved"}
    expect(policy.validate_merge_readiness(resolved_without_evidence, proposed_sha=proposed_sha)["outcome"] == "fail",
           "resolved finding without resolution evidence must reject merge readiness")
    other_review = json.loads(json.dumps(receipt))
    other_review["independent_review"]["review_type"] = "security-review"
    expect(policy.validate_merge_readiness(other_review, proposed_sha=proposed_sha)["outcome"] == "fail",
           "security review must not substitute for independent GSD code review")
    zero_lane = json.loads(json.dumps(receipt))
    zero_lane["required_aggregate"]["lane_count"] = 0
    expect(policy.validate_merge_readiness(zero_lane, proposed_sha=proposed_sha)["outcome"] == "fail",
           "zero-count aggregate must reject merge readiness")

    expect(policy.classify_paths(["docs/testing.md"]) == {policy.DOCS_JOB}, "docs-only change must retain the content gate")
    expect(policy.classify_paths(["src/instance.c"]) == set(policy.REQUIRED_JOBS), "source change must run every required lane")
    expect(policy.classify_paths(["new/unknown.file"]) == set(policy.REQUIRED_JOBS), "unknown path must fail open to every lane")
    expect(policy.classify_paths(None) == set(policy.REQUIRED_JOBS), "missing diff must fail open")
    expect(policy.classify_paths([], diff_error=True) == set(policy.REQUIRED_JOBS), "diff failure must fail open")

    jobs = {name: {"result": "success", "lane_count": 1, "assertion_count": 12}
            for name in policy.REQUIRED_JOBS}
    expect(policy.validate_aggregate(jobs, planned=set(policy.REQUIRED_JOBS))["outcome"] == "pass",
           "complete successful positive lanes must pass")
    expect(policy.validate_aggregate(jobs, planned={policy.MATRIX_JOB})["outcome"] == "fail",
           "matrix changes must not omit the independent public-content gate")
    for result in ("missing", "failure", "cancelled", "skipped"):
        altered = {key: dict(value) for key, value in jobs.items()}
        altered[policy.MATRIX_JOB]["result"] = result
        expect(policy.validate_aggregate(altered, planned=set(policy.REQUIRED_JOBS))["outcome"] == "fail",
               f"{result} matrix job must fail aggregate")
    altered = {key: dict(value) for key, value in jobs.items()}
    altered[policy.MATRIX_JOB]["lane_count"] = 0
    expect(policy.validate_aggregate(altered, planned=set(policy.REQUIRED_JOBS))["outcome"] == "fail",
           "empty required matrix must fail")
    altered = {key: dict(value) for key, value in jobs.items()}
    altered[policy.MATRIX_JOB]["result"] = "skipped"
    altered[policy.DOCS_JOB]["result"] = "success"
    altered[policy.DOCS_JOB]["assertion_count"] = 5
    expect(policy.validate_aggregate(altered, planned={policy.DOCS_JOB})["outcome"] == "pass",
           "documented selective skip may pass only with docs evidence")
    altered[policy.DOCS_JOB]["assertion_count"] = 0
    expect(policy.validate_aggregate(altered, planned={policy.DOCS_JOB})["outcome"] == "fail",
           "docs-only skip without positive evidence must fail")
    expect(policy.validate_aggregate(jobs, planned=set(policy.REQUIRED_JOBS) - {policy.MATRIX_JOB})["outcome"] == "fail",
           "unplanned matrix success must not be silently accepted")
    altered = {key: dict(value) for key, value in jobs.items()}
    altered[policy.DOCS_JOB]["result"] = "cancelled"
    expect(policy.validate_aggregate(altered, planned=set(policy.REQUIRED_JOBS))["outcome"] == "fail",
           "cancelled public content check must fail")

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for required in (
        "pull_request:", "push:", "permissions:\n  contents: read", "max-parallel: 2",
        "if: always()", "linux-clang", "linux-gcc", "macos-appleclang", "windows-msvc",
        "linux-clang-sanitizer", "linux-clang-fuzz",
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
        "Verify native save-state continuation and rejection suite",
        "Verify native durable MVS backup-RAM save suite",
        "produce-public-content", "SDK_SOURCE_REVISION", "public-content-receipt.json",
        "tests/workflow/test_ci_policy.py --hosted",
    ):
        expect(required in workflow, f"workflow omitted required contract: {required}")
    state_command = "run: python3 tools/verify_sdk.py --suite state"
    save_command = "run: python3 tools/verify_sdk.py --suite save"
    expect(workflow.count(state_command) == 1 and workflow.count(save_command) == 1,
           "Linux Clang lane must run each native continuation/save suite exactly once")
    state_index = workflow.index(state_command)
    save_index = workflow.index(save_command)
    state_step_start = workflow.rfind("      - name:", 0, state_index)
    next_step = workflow.find("      - name:", state_index)
    save_step_start = workflow.rfind("      - name:", 0, save_index)
    state_step = workflow[state_step_start:next_step]
    save_step_end = workflow.find("      - name:", save_index)
    save_step = workflow[save_step_start:save_step_end]
    expect(save_index > state_index and next_step == save_step_start,
           "native save suite must run immediately after the existing state suite")
    expect("if: matrix.lane == 'linux-clang'" in state_step and
           "if: matrix.lane == 'linux-clang'" in save_step,
           "native state and save suites must stay in the existing bounded Linux Clang lane")
    expect("paths:" not in workflow, "workflow-level path filters can omit the required aggregate")
    expect("pull_request_target" not in workflow and "secrets." not in workflow,
           "untrusted PR workflow must not use privileged events or secrets")
    expect("contents: write" not in workflow, "PR workflow token must remain read-only")
    expect('"${{ matrix.' not in workflow,
           "matrix values must enter runner shells through environment variables, not inline interpolation")

    releasing = (ROOT / "docs/releasing.md").read_text(encoding="utf-8")
    for required in (
        "strict up-to-date branches", "independent GSD code review", "Any head change",
        "native auto-merge", "measured merge contention", "security-review threat dispositions",
        "This local validator does not fetch GitHub receipts or grant merge",
    ):
        expect(required in releasing, f"release policy documentation omitted: {required}")
    release_workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    expect(release_workflow.count("app-id: ${{ vars.RELEASE_APP_ID }}") == 3
           and "app-id: ${{ secrets.RELEASE_APP_ID }}" not in release_workflow,
           "nonsecret GitHub App ID must come from repository variables in all privileged jobs")
    expect("RELEASE_APP_ID` Actions\nvariable" in releasing,
           "release setup docs must identify the App ID as a nonsecret variable")
    expect("Upload bounded matrix verification evidence" in release_workflow
           and "if: always()" in release_workflow,
           "matrix diagnostics artifact must upload after failed verification steps")
    testing = (ROOT / "docs/testing.md").read_text(encoding="utf-8")
    for required in (
        "Darwin-26", "Apple SDK 26.5", "1,440 assertions", "9.374 seconds",
        "runner-minutes", "A new SHA requires new evidence", "rights status unknown",
        "release App", "passed the archive checks and all three downloaded consumers before publishing",
        "PROJECT-D-50", "First-time fork approval and execution remain deferred and unverified",
        "python3 tools/verify_sdk.py --suite save", "7/7 named tests",
        "2,182 reported", "881 direct documentation assertions", "235.110 seconds",
        "1,308", "Python assertion calls",
        "macOS 26.6.2 / Darwin", "25.6.0 / APFS",
    ):
        expect(required in testing, f"qualification documentation omitted: {required}")
    # Immutable Phase03 publication baseline; source archives need not ship the
    # later local download receipts to retain this documentation regression.
    published_source = "fdc241e0f554d61c7a270cad141fd51c2aa2b334"
    published_tag = "v0.2.1"
    expect(published_source in testing and published_tag in testing,
           "published support docs must identify the exact released source and tag")
    # Hosted observations supersede the former unknown rows only for the exact
    # recorded source and identities. Keep the release/authority boundary above.
    if not hosted:
        hosted_paths = sorted((ROOT / ".planning/workstreams/cpu-bus-diagnostic-sdk-alpha").rglob(
            "03-CI-HOSTED-RECEIPT.json"))
        expect(len(hosted_paths) == 1, "exactly one canonical hosted CI observation must be available")
        hosted_receipt = evidence.load_canonical_json(hosted_paths[0].read_bytes(),
                                                      label="hosted CI observation")
        evidence.validate_matrix_report(hosted_receipt["aggregate"]["matrix"])
        expect(hosted_receipt["source_revision"] in testing,
               "hosted support docs must name the exact observed source")
        for lane in hosted_receipt["aggregate"]["matrix"]["lanes"]:
            expect(lane["outcome"] == "pass" and all(value in testing for value in
                   (lane["lane"], lane["compiler"]["version"], lane["sdk"]["version"],
                    lane["os_image"], lane["architecture"])),
                   "passing support rows must match measured hosted identities")

    check_public_content_summary_controls()
    check_public_content_failure_diagnostics()
    public_content_cases, public_content_assertions = check_public_content_handoff()

    revision = "a" * 40
    with tempfile.TemporaryDirectory(prefix="ci-matrix-test-") as temp:
        matrix_dir = Path(temp)
        for lane in evidence.REQUIRED_MATRIX_LANES:
            os_name, compiler_ids, architectures = evidence.MATRIX_LANE_IDENTITY[lane]
            row = {
                "lane": lane, "compiler": {"id": next(iter(compiler_ids)), "version": "18.1"},
                "sdk": {"name": "test-sdk", "version": "1.0"},
                "os_image": {"Linux": "ubuntu-test", "Darwin": "macos-test", "Windows": "windows-test"}[os_name],
                "os": os_name, "architecture": next(iter(architectures)), "configuration": "Debug",
                "source_revision": revision, "working_tree_dirty": False,
                "build_identity": {"cmake": "3.31", "generator": "Ninja 1.13", "fixture_sha256": "b" * 64},
                "outcome": "pass", "assertions": 3, "duration_seconds": 6.0,
                "cold_build_seconds": 1.0, "runner_id": f"runner-{lane}", "runner_minutes": 0.1,
            }
            (matrix_dir / f"{lane}.json").write_bytes(evidence.canonical_bytes(row))
        planned = {"selected_jobs": sorted(policy.REQUIRED_JOBS)}
        results = {"classify": "success", "matrix": "success", "public-content": "success",
                   "source_revision": revision,
                   "public_content_receipt": {"schema_version": 1, "suite": "public-content",
                                               "source_revision": revision, "working_tree_dirty": False,
                                               "lane_count": 1,
                                               "assertion_count": public_content_assertions,
                                               "assertion_count_basis":
                                                   "unittest.TestCase assertion/fail method calls",
                                               "control_cases": public_content_cases,
                                               "outcome": "pass", "detector_negative_only": True,
                                               "artifact_verified": True, "matrix_logs_verified": True,
                                               "coverage": {"logs_supplied": 6}}}
        aggregate = policy.assemble_aggregate(results, planned, matrix_dir)
        expect(aggregate["outcome"] == "pass", "full current-SHA matrix with positive content scan must pass")
        stale = dict(results, source_revision="c" * 40)
        expect(policy.assemble_aggregate(stale, planned, matrix_dir)["outcome"] == "fail",
               "matrix evidence from a different current SHA must fail")
        docs_plan = {"selected_jobs": [policy.DOCS_JOB]}
        docs_only = dict(results, matrix="skipped")
        docs_only.pop("public_content_receipt")
        docs_only["public_content_receipt"] = {
            "schema_version": 1, "suite": "public-content", "source_revision": revision,
            "working_tree_dirty": False, "lane_count": 1, "assertion_count": 4,
            "assertion_count_basis": "unittest.TestCase assertion/fail method calls",
            "control_cases": public_content_cases, "outcome": "pass", "detector_negative_only": True,
            "artifact_verified": True, "matrix_logs_verified": False,
        }
        expect(policy.assemble_aggregate(docs_only, docs_plan, matrix_dir)["outcome"] == "pass",
               "documented classifier skip must pass only with positive docs evidence")
    print("PASS: hosted CI policy contracts" if hosted else
          "PASS: conservative CI classification and aggregate controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
