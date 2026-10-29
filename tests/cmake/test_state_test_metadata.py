"""Check generated CTest metadata for the native state suites."""

import json
import importlib.util
import pathlib
import shutil
import subprocess
import unittest


class StateTestMetadataTests(unittest.TestCase):
    def test_local_state_schedule_has_a_bounded_binary_contract(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "glueyneo_qualify_local_state", root / "tools" / "mvs" /
            "qualify_local_state.py")
        module_path = root / "tools" / "mvs" / "qualify_local_state.py"
        if module_path.is_file():
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            qualification = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(qualification)
            encoded = qualification.encode_schedule(
                capture_frame=2, future_inputs=[0, 0x40, 0, 0x80],
                private_scene=False)
        else:
            encoded = b""
        self.assertEqual(encoded, bytes.fromhex(
            "474e534c0000000100000002000000010000000100000004"
            "00000000000000400000000000000080"))
        with self.assertRaises(ValueError):
            qualification.encode_schedule(
                capture_frame=3, future_inputs=[0, 0x400],
                private_scene=False)

    def test_state_suite_has_exact_named_cases_and_rejects_empty_evidence(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "glueyneo_verify_sdk", root / "tools" / "verify_sdk.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)

        expected = {
            "sdk_state_tracer", "sdk_state_identity", "sdk_state_ym",
            "sdk_state_machine", "sdk_state_continuation", "sdk_state_controls",
            "sdk_state_isolation", "sdk_state_repeat", "sdk_state_hostile",
            "sdk_state_oom", "sdk_state_process", "sdk_state_registration",
        }
        self.assertEqual(verifier.SUITE_LABELS.get("state"), "sdk-state")
        self.assertEqual(verifier.STATE_REQUIRED_CASES, expected)
        self.assertEqual(verifier.STATE_OPTIONAL_CASES, {"sdk_state_exchange"})

        names = sorted(expected) + ["sdk_state_exchange"]
        output_lines = [f"Start {index}: {name}" for index, name in
                        enumerate(names, start=1)]
        for index, name in enumerate(names, start=1):
            if name == "sdk_state_exchange":
                output_lines.append(
                    f'{index}: STATE_EXCHANGE_RESULT {{"outcome":"pass",'
                    '"pair_cases":8,"assertions":176}')
            elif name == "sdk_state_controls":
                output_lines.extend(
                    f"{index}: {selector}: expected observation assertion failed"
                    for selector in ("cpu", "memory", "board", "sound", "ym2610"))
                output_lines.append(f"{index}: unknown selector: rejected")
            else:
                output_lines.append(
                    f'{index}: SDK_RESULT {{"outcome":"pass",'
                    '"cases":1,"assertions":1}')
        output_lines.append(
            f"100% tests passed, 0 tests failed out of {len(names)}")
        complete_output = "\n".join(output_lines)
        validated = verifier.validate_state_ctest_output(complete_output)
        self.assertEqual(validated["cases"], len(names))
        self.assertEqual(validated["assertions"], len(expected) - 1 + 6 + 176)
        self.assertEqual(set(validated["per_case_assertions"]),
                         expected | {"sdk_state_exchange"})

        missing_output = complete_output.replace(
            f"1: SDK_RESULT {{\"outcome\":\"pass\",\"cases\":1,\"assertions\":1}}\n", "", 1)
        with self.assertRaises(verifier.VerificationError):
            verifier.validate_state_ctest_output(missing_output)

        zero_output = complete_output.replace(
            "\"assertions\":1", "\"assertions\":0", 1)
        with self.assertRaises(verifier.VerificationError):
            verifier.validate_state_ctest_output(zero_output)

    def test_both_state_suites_have_bounded_state_metadata(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        build_dir = root / "build" / "sdk-debug"
        ctest = shutil.which("ctest")
        self.assertIsNotNone(ctest, "CTest must be available")

        result = subprocess.run(
            [
                ctest,
                "--test-dir",
                str(build_dir),
                "--show-only=json-v1",
                "-R",
                r"^sdk_state_(tracer|identity)$",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        tests = {
            test["name"]: {
                prop["name"]: prop["value"]
                for prop in test.get("properties", [])
            }
            for test in json.loads(result.stdout)["tests"]
        }
        self.assertEqual(set(tests), {"sdk_state_tracer", "sdk_state_identity"})
        for name, properties in tests.items():
            with self.subTest(test=name):
                self.assertIn("sdk-state", properties.get("LABELS", []))
                self.assertEqual(properties.get("TIMEOUT"), 60.0)


if __name__ == "__main__":
    unittest.main()
