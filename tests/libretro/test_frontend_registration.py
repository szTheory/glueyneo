#!/usr/bin/env python3
"""Fail-closed frontend registration, policy, and provenance controls."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = ROOT / "build/owned-debug"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests/libretro"))
import verify_sdk as VERIFY  # noqa: E402
import retroarch_smoke as SMOKE  # noqa: E402


EXPECTED_COMMANDS = {
    "libretro_callback": ("libretro_callback_test", "public-playable.bin"),
    "libretro_audio_contract": ("libretro_callback_test", "--sound", "public-sound-mvs.bin"),
    "libretro_mvs_state_contract": ("libretro_callback_test", "--mvs-state", "public-save.gnmv"),
    "libretro_mvs_save_ram_contract": ("libretro_callback_test", "--mvs-save-ram", "public-save.gnmv"),
    "libretro_mvs_state_rejection": ("libretro_mvs_state_safety_test", "--state-rejection"),
    "libretro_mvs_retention": ("libretro_mvs_state_safety_test", "--retention"),
    "libretro_frontend_observer": (
        "frontend_observer_test.py", "--harness", "libretro_frontend_observer_test",
        "--production", "libretro_frontend_production_test", "--witness", "sdk_state_process",
        "--bundle", "public-sound-mvs.bin",
    ),
    "qualification_frontend_smoke": (
        "-m", "unittest", "discover", "-s", "tests/libretro", "-p", "test_retroarch_smoke.py",
    ),
    "libretro_frontend_registration": (
        "test_frontend_registration.py", "--build-dir", "build/owned-debug",
        "--mode", "registration",
    ),
}
REQUIRED_CASES = frozenset(EXPECTED_COMMANDS)
FRONTEND_DOC_PATHS = {
    "frontend": "docs/frontend-continuation.md",
    "first_playable": "docs/first-playable-build.md",
    "native_state": "docs/native-state.md",
    "native_save": "docs/native-save.md",
    "testing": "docs/testing.md",
}


def _fixture_registration() -> dict[str, object]:
    return {"tests": [{"name": name, "command": list(command)}
                       for name, command in EXPECTED_COMMANDS.items()]}


def _ctest_json(build_dir: Path) -> dict[str, object]:
    result = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "--show-only=json-v1"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False, timeout=30,
    )
    if result.returncode != 0:
        raise VERIFY.VerificationError("CTest registration query failed")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise VERIFY.VerificationError("CTest registration JSON is malformed") from error
    if not isinstance(value, dict):
        raise VERIFY.VerificationError("CTest registration JSON is not an object")
    return value


class FrontendRegistrationTests(unittest.TestCase):
    assertion_count = 0
    build_dir = BUILD_DIR

    def __getattribute__(self, name: str):
        attribute = super().__getattribute__(name)
        if name.startswith("assert") and callable(attribute):
            def count_assertion(*args, **kwargs):
                type(self).assertion_count += 1
                return attribute(*args, **kwargs)
            return count_assertion
        return attribute

    def test_verifier_has_a_named_frontend_suite_and_exact_case_inventory(self) -> None:
        self.assertTrue(hasattr(VERIFY, "suite_frontend"), "verify_sdk must expose --suite frontend")
        self.assertEqual(set(getattr(VERIFY, "FRONTEND_REQUIRED_CASES", ())), REQUIRED_CASES)
        self.assertTrue(callable(getattr(VERIFY, "validate_frontend_ctest_registration", None)))
        self.assertTrue(callable(getattr(VERIFY, "validate_frontend_ctest_output", None)))
        self.assertTrue(callable(getattr(VERIFY, "validate_frontend_source_contract", None)))

    def test_live_ctest_membership_has_unique_nonempty_source_backed_commands(self) -> None:
        self.assertEqual(
            VERIFY.validate_frontend_ctest_registration(_ctest_json(self.build_dir))["required_cases"],
            sorted(REQUIRED_CASES),
        )

    def test_every_required_omission_or_rename_fails(self) -> None:
        for name in sorted(REQUIRED_CASES):
            omitted = _fixture_registration()
            omitted["tests"] = [row for row in omitted["tests"] if row["name"] != name]
            with self.subTest(mutation=f"omit {name}"), self.assertRaises(VERIFY.VerificationError):
                VERIFY.validate_frontend_ctest_registration(omitted)

            renamed = _fixture_registration()
            for row in renamed["tests"]:
                if row["name"] == name:
                    row["name"] = f"renamed_{name}"
            with self.subTest(mutation=f"rename {name}"), self.assertRaises(VERIFY.VerificationError):
                VERIFY.validate_frontend_ctest_registration(renamed)

    def test_empty_selection_duplicate_names_and_empty_commands_fail(self) -> None:
        for mutation in ({"tests": []}, {"tests": None}, {"tests": [{"name": "x", "command": []}]}):
            with self.subTest(mutation=mutation), self.assertRaises(VERIFY.VerificationError):
                VERIFY.validate_frontend_ctest_registration(mutation)
        duplicate = _fixture_registration()
        duplicate["tests"].append(copy.deepcopy(duplicate["tests"][0]))
        with self.assertRaises(VERIFY.VerificationError):
            VERIFY.validate_frontend_ctest_registration(duplicate)
        empty = _fixture_registration()
        empty["tests"][0]["command"] = []
        with self.assertRaises(VERIFY.VerificationError):
            VERIFY.validate_frontend_ctest_registration(empty)

    def test_source_backed_command_mutations_fail(self) -> None:
        for name, token in (("libretro_audio_contract", "--sound"),
                            ("libretro_mvs_state_contract", "--mvs-state"),
                            ("libretro_mvs_save_ram_contract", "--mvs-save-ram"),
                            ("libretro_mvs_state_rejection", "--state-rejection"),
                            ("libretro_mvs_retention", "--retention"),
                            ("libretro_frontend_observer", "--witness"),
                            ("qualification_frontend_smoke", "test_retroarch_smoke.py"),
                            ("libretro_frontend_registration", "--mode")):
            candidate = _fixture_registration()
            row = next(item for item in candidate["tests"] if item["name"] == name)
            row["command"].remove(token)
            with self.subTest(name=name), self.assertRaises(VERIFY.VerificationError):
                VERIFY.validate_frontend_ctest_registration(candidate)

    def test_zero_or_partial_ctest_output_cannot_pass(self) -> None:
        positive = "".join(f"Start {i + 12}: {name}\n{i}/9 Test #{i + 12}: {name} Passed 0.01 sec\n"
                           for i, name in enumerate(sorted(REQUIRED_CASES), 1))
        positive += "100% tests passed out of 9\n"
        self.assertEqual(VERIFY.validate_frontend_ctest_output(positive)["cases"], 9)
        mutations = (
            "100% tests passed out of 0\n",
            positive.replace("100% tests passed out of 9", "0% tests passed out of 9"),
            positive.replace("100% tests passed out of 9", "100% tests passed out of 8"),
            positive.replace("Start 21:", "Start 20:", 1),
            positive.replace(" Passed 0.01 sec", " ***Failed 0.01 sec", 1),
        )
        for candidate in mutations:
            with self.subTest(output=candidate[-80:]), self.assertRaises(VERIFY.VerificationError):
                VERIFY.validate_frontend_ctest_output(candidate)

    def test_dependency_surface_has_no_new_package_or_link_dependency(self) -> None:
        cmake_source = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertGreater(VERIFY.validate_frontend_dependency_surface(cmake_source), 0)
        mutations = (
            cmake_source.replace("find_package(Python3", "find_package(NewFrontendPackage REQUIRED)\n  find_package(Python3", 1),
            cmake_source + "\nFetchContent_Declare(frontend_helper GIT_REPOSITORY example)\n",
            cmake_source + "\ntarget_link_libraries(glueyneo PRIVATE NewFrontend::NewFrontend)\n",
        )
        for candidate in mutations:
            with self.assertRaises(VERIFY.VerificationError):
                VERIFY.validate_frontend_dependency_surface(candidate)

    def test_actual_route_source_mutations_and_bad_matrix_fail(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        smoke = (ROOT / "tests/libretro/retroarch_smoke.py").read_text(encoding="utf-8")
        observer = (ROOT / "tests/libretro/frontend_observer_test.py").read_text(encoding="utf-8")
        exports = (ROOT / "tests/consumers/test_exports.py").read_text(encoding="utf-8")
        self.assertIsNone(VERIFY.validate_frontend_source_contract(cmake, smoke, observer, exports))
        with self.assertRaises(VERIFY.VerificationError):
            VERIFY.validate_frontend_source_contract(cmake, smoke.replace("def run_private_state(", "def removed_private_state(", 1), observer, exports)
        with self.assertRaises(VERIFY.VerificationError):
            VERIFY.validate_frontend_source_contract(
                cmake, smoke, observer.replace("accepts-actual-frontend-mem-payload", "removed_control", 1), exports)
        with self.assertRaisesRegex(SMOKE.SmokeBlocked, "requires state operations"):
            SMOKE.validate_continuation_operation_matrix(
                "private-state", state_operations=True, autosave_interval=1)
        with self.assertRaisesRegex(SMOKE.SmokeBlocked, "periodic save requires"):
            SMOKE.validate_continuation_operation_matrix(
                "periodic-save", state_operations=True, autosave_interval=1)

    def test_raw_frontend_mem_must_equal_direct_gnst_payload(self) -> None:
        native = b"GNST" + bytes(range(32))
        SMOKE.require_matching_frontend_mem(native, native)
        for candidate in (b"RASTATE" + native, native[:-1], native + b"extra"):
            with self.subTest(size=len(candidate)), self.assertRaises(SMOKE.SmokeBlocked):
                SMOKE.require_matching_frontend_mem(candidate, native)

    def test_private_identity_paths_and_blocked_route_are_fail_closed(self) -> None:
        expected = {key: "a" * 64 for key in SMOKE.PRIVATE_STATE_IDENTITY_FIELDS}
        self.assertTrue(SMOKE.validate_private_state_identity(expected, dict(expected)))
        for bad in (dict(expected, scene_contract_sha256="b" * 64),
                    {key: value for key, value in expected.items() if key != "media_identity_sha256"}):
            self.assertFalse(SMOKE.validate_private_state_identity(expected, bad))
        self.assertEqual(json.loads(SMOKE.public_json({"status": "pass", "capture": "/private/tmp/owned/frame.png"})),
                         {"status": "fail", "reason": "private-path-survived"})

        with tempfile.TemporaryDirectory(prefix="glueyneo-frontend-blocked-") as temporary:
            root = Path(temporary)
            report = root / "blocked.json"
            blocked = SMOKE.SmokeBlocked("continuation-observations", "synthetic blocked route")
            with mock.patch.dict(os.environ, {"GLUEYNEO_FRONTEND_WORK": str(root)}), \
                 mock.patch.object(SMOKE, "_run_private_state_transaction", side_effect=blocked):
                with self.assertRaises(SMOKE.SmokeBlocked):
                    SMOKE.run_private_state(SimpleNamespace(report=report))
            receipt = json.loads(report.read_text(encoding="utf-8"))
            self.assertNotEqual(receipt.get("status"), "pass")
            self.assertEqual(receipt.get("stage"), "continuation-observations")

    def test_source_and_matrix_identity_drift_is_rejected(self) -> None:
        paths = getattr(VERIFY, "FRONTEND_SOURCE_PATHS", ())
        self.assertIn("tests/libretro/test_frontend_registration.py", paths)
        identity = VERIFY.frontend_source_identity(ROOT)
        self.assertRegex(identity, r"^[0-9a-f]{64}$")
        VERIFY.require_frontend_evidence_identity_stable(identity, identity)
        with self.assertRaisesRegex(VERIFY.VerificationError, "sources changed"):
            VERIFY.require_frontend_evidence_identity_stable(identity, "0" * 64)
        for required_path in VERIFY.FRONTEND_PHASE_SOURCE_FILES:
            reduced = tuple(path for path in paths if path != required_path)
            with self.subTest(omitted_identity_source=required_path), \
                    mock.patch.object(VERIFY, "FRONTEND_SOURCE_PATHS", reduced), \
                    self.assertRaisesRegex(VERIFY.VerificationError,
                                           "omitted phase source"):
                VERIFY.frontend_source_identity(ROOT)

    @unittest.skipIf(os.name == "nt", "the regression targets POSIX shell expansion")
    def test_fresh_process_launcher_keeps_shell_metacharacters_literal(self) -> None:
        executable = self.build_dir.resolve() / "libretro_mvs_state_safety_test"
        self.assertTrue(executable.is_file(), "state-safety executable must be built")
        with tempfile.TemporaryDirectory(prefix="glueyneo-shell-path-") as temporary:
            root = Path(temporary)
            marker = root / "shell-injected"
            malicious_path = root / "safety$(touch${IFS}shell-injected)"
            malicious_path.symlink_to(executable)
            result = subprocess.run(
                [str(malicious_path), "--state-rejection"], cwd=root,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertFalse(marker.exists(), "executable path must never be interpreted by a shell")

    def test_ci_public_lane_and_cli_modes_are_wired_without_private_inputs(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIsNone(VERIFY.validate_frontend_ci_contract(workflow))
        for command, required in (([sys.executable, str(ROOT / "tools/verify_sdk.py"), "--help"], "frontend"),
                                  ([sys.executable, str(ROOT / "tests/libretro/retroarch_smoke.py"), "--help"], "private-state")):
            result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, check=False, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn(required, result.stdout)

    def test_current_frontend_contract_is_complete_and_mislabels_fail(self) -> None:
        self.assertTrue(callable(getattr(VERIFY, "validate_frontend_documentation", None)),
                        "frontend continuation documentation checker is required")
        documents = {key: ((ROOT / path).read_text(encoding="utf-8")
                           if (ROOT / path).is_file() else "")
                     for key, path in FRONTEND_DOC_PATHS.items()}
        self.assertGreater(VERIFY.validate_frontend_documentation(documents), 0)
        mutations = (
            ("frontend", "`GNST`", "`NOT-STATE`"),
            ("frontend", "`RASTATE`", "`UNRELATED-CONTAINER`"),
            ("frontend", "`GNSV`", "`GNST`"),
            ("frontend", "block_sram_overwrite=false", "block_sram_overwrite=true"),
            ("frontend", "Undo Load State", "Undo Save State"),
            ("frontend", "65,536-byte", "64-byte"),
            ("frontend", "emitted core callbacks", "displayed device output"),
            ("native_state", "frontend-continuation.md", "removed-contract.md"),
            ("native_save", "frontend-continuation.md", "removed-contract.md"),
            ("first_playable", "frontend-continuation.md", "removed-contract.md"),
        )
        for key, expected, replacement in mutations:
            candidate = dict(documents)
            candidate[key] = candidate[key].replace(expected, replacement)
            if expected in {"`GNST`", "`RASTATE`", "`GNSV`", "Undo Load State", "65,536-byte"}:
                candidate[key] = candidate[key].replace(expected, replacement)
            with self.subTest(document=key, mutation=expected), self.assertRaises(VERIFY.VerificationError):
                VERIFY.validate_frontend_documentation(candidate)

    def test_phase_provenance_and_private_content_mutations_fail_closed(self) -> None:
        self.assertTrue(callable(getattr(VERIFY, "validate_frontend_phase_provenance", None)),
                        "phase-specific frontend provenance checker is required")
        manifest = json.loads((ROOT / "tests/fixture/rights-manifest.json").read_text(encoding="utf-8"))
        self.assertGreater(VERIFY.validate_frontend_phase_provenance(manifest, ROOT), 0)
        section = manifest["frontend_continuation"]
        mutations = []
        for required_path in VERIFY.FRONTEND_PHASE_SOURCE_FILES:
            missing_source = copy.deepcopy(manifest)
            missing_source["frontend_continuation"]["source_files"] = [
                row for row in missing_source["frontend_continuation"]["source_files"]
                if row.get("path") != required_path
            ]
            mutations.append(missing_source)
        stale_source = copy.deepcopy(manifest)
        stale_source["frontend_continuation"]["source_files"][0]["sha256"] = "0" * 64
        mutations.append(stale_source)
        private_bytes = copy.deepcopy(manifest)
        private_bytes["frontend_continuation"]["selected_private_scene"]["content_bytes_committed"] = True
        mutations.append(private_bytes)
        private_hash = copy.deepcopy(manifest)
        private_hash["frontend_continuation"]["selected_private_scene"]["media_sha256"] = "a" * 64
        mutations.append(private_hash)
        closed_global_debt = copy.deepcopy(manifest)
        closed_global_debt["frontend_continuation"]["phase07_global_rights_inventory_closed"] = True
        mutations.append(closed_global_debt)
        bad_ancestry = copy.deepcopy(manifest)
        bad_ancestry["frontend_continuation"]["public_fixture_ancestry"]["recipe_origin_revision"] = "unknown"
        mutations.append(bad_ancestry)
        mislabelled_history = copy.deepcopy(manifest)
        mislabelled_history["frontend_continuation"]["historical_results"]["phase05_original_regression"] = "passed"
        mutations.append(mislabelled_history)
        for candidate in mutations:
            with self.subTest(section=candidate.get("frontend_continuation")), \
                    self.assertRaises(VERIFY.VerificationError):
                VERIFY.validate_frontend_phase_provenance(candidate, ROOT)
        self.assertIn("source_files", section)

    def test_documentation_and_provenance_modes_have_redacted_pass_receipts(self) -> None:
        for mode, marker in (("docs", "FRONTEND_DOCS_RESULT"),
                             ("provenance", "FRONTEND_PROVENANCE_RESULT")):
            result = subprocess.run(
                [sys.executable, str(ROOT / "tests/libretro/test_frontend_registration.py"),
                 "--build-dir", str(self.build_dir), "--mode", mode],
                cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn(marker, result.stdout)
            self.assertNotIn("/private/", result.stdout)


def _run_registration(build_dir: Path) -> int:
    FrontendRegistrationTests.build_dir = build_dir.resolve()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FrontendRegistrationTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    cases = result.testsRun
    assertions = FrontendRegistrationTests.assertion_count
    if cases <= 0 or assertions <= 0:
        raise VERIFY.VerificationError("frontend registration controls emitted no positive denominator")
    print("FRONTEND_REGISTRATION_RESULT " + json.dumps(
        {"tests": cases, "assertions": assertions}, sort_keys=True, separators=(",", ":")))
    return 0


def main() -> int:
    parser = __import__("argparse").ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=BUILD_DIR)
    parser.add_argument("--mode", choices=("registration", "docs", "provenance"), default="registration")
    args = parser.parse_args()
    try:
        if args.mode == "registration":
            if not args.build_dir.is_dir():
                raise VERIFY.VerificationError("frontend registration build directory is unavailable")
            _ctest_json(args.build_dir)
            return _run_registration(args.build_dir)
        if args.mode == "docs":
            checker = getattr(VERIFY, "frontend_docs_checks", None)
            if not callable(checker):
                raise VERIFY.VerificationError("frontend documentation checks are not wired")
            print("FRONTEND_DOCS_RESULT " + json.dumps(checker(ROOT), sort_keys=True))
            return 0
        checker = getattr(VERIFY, "frontend_provenance_checks", None)
        if not callable(checker):
            raise VERIFY.VerificationError("frontend provenance checks are not wired")
        print("FRONTEND_PROVENANCE_RESULT " + json.dumps(checker(ROOT), sort_keys=True))
        return 0
    except (VERIFY.VerificationError, OSError, ValueError, RuntimeError) as error:
        print(f"frontend registration failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
