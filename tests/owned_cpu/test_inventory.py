"""Corruption controls for the owned CPU source inventory checker."""

from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.owned_cpu import inventory


class InventoryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = (ROOT / inventory.RUNTIME_PATH).read_text(encoding="utf-8")
        cls.header = (ROOT / inventory.HEADER_PATH).read_text(encoding="utf-8")
        cls.fixture = (ROOT / inventory.FIXTURE_PATH).read_text(encoding="utf-8")
        cls.document = inventory.json.loads(
            (ROOT / inventory.INVENTORY_PATH).read_text(encoding="utf-8")
        )

    def test_missing_field_has_named_rejection(self):
        fields = [entry for entry in self.document["fields"]
                  if entry["name"] != "reset_signal_events"]
        errors = inventory.field_errors(fields, self.runtime)
        self.assertIn("missing field inventory entry: reset_signal_events", errors)

    def test_extra_field_has_named_rejection(self):
        fields = self.document["fields"] + [
            {"name": "foreign", "declaration": "uint32_t foreign"}
        ]
        errors = inventory.field_errors(fields, self.runtime)
        self.assertIn("extra field inventory entry: foreign", errors)

    def test_field_type_change_has_named_rejection(self):
        fields = [dict(entry) for entry in self.document["fields"]]
        fields[0]["declaration"] = "void * bus"
        errors = inventory.field_errors(fields, self.runtime)
        self.assertIn("field declaration mismatch: bus", errors)

    def test_private_state_inventory_matches_named_record_fields(self):
        actual = inventory.parse_state_record_fields(self.header)
        declared = {entry["name"]: entry["declaration"]
                    for entry in self.document["private_state_record"]["record_fields"]}
        self.assertEqual(actual, declared)

    def test_private_state_identity_is_bound_to_exact_cpu_source(self):
        digest = inventory.sha256(ROOT / inventory.RUNTIME_PATH)
        stale = self.header.replace(digest, "0" * 64, 1)
        self.assertIn(
            "private state core identity is stale against cpu.c SHA-256",
            inventory.state_identity_errors(stale, digest),
        )

    def test_nested_private_state_identity_is_bound_to_exact_cpu_source(self):
        stale = copy.deepcopy(self.document)
        stale["private_state_record"]["core_identity_sha256"] = "0" * 64
        self.assertIn(
            "private state inventory core identity is stale against cpu.c SHA-256",
            inventory.state_record_errors(ROOT, stale),
        )

    def test_refresh_state_inventory_preserves_field_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cpu_dir = root / "experiments/owned_cpu"
            cpu_dir.mkdir(parents=True)
            runtime_path = cpu_dir / "cpu.c"
            runtime_path.write_text("owned cpu\n", encoding="utf-8")
            header_path = cpu_dir / "cpu.h"
            header_text = (
                "#define OWNED_CPU_STATE_CORE_IDENTITY_SHA256 " + chr(92) + "\n"
                + '    "' + "0" * 64 + '"\n'
            )
            header_path.write_text(header_text, encoding="utf-8")
            field = {"name": "reset_signal_events",
                     "declaration": "uint64_t reset_signal_events",
                     "classification": "guest-state"}
            private_field = {"name": "reset_signal_events",
                             "declaration": "uint64_t reset_signal_events"}
            document = {
                "core_identity_sha256": "0" * 64,
                "fields": [field],
                "private_state_record": {
                    "core_identity_sha256": "0" * 64,
                    "record_fields": [private_field],
                },
                "source_hashes": {
                    "experiments/owned_cpu/cpu.c": "0" * 64,
                    "experiments/owned_cpu/cpu.h": "0" * 64,
                },
            }
            inventory_path = cpu_dir / "state-inventory.json"
            inventory_path.write_text(json.dumps(document), encoding="utf-8")

            inventory.refresh_state_inventory(root)

            refreshed = json.loads(inventory_path.read_text(encoding="utf-8"))
            runtime_hash = inventory.sha256(runtime_path)
            self.assertEqual(runtime_hash, refreshed["core_identity_sha256"])
            self.assertEqual(runtime_hash,
                             refreshed["private_state_record"]["core_identity_sha256"])
            self.assertEqual([field], refreshed["fields"])
            self.assertEqual([private_field],
                             refreshed["private_state_record"]["record_fields"])
            self.assertEqual(runtime_hash,
                             refreshed["source_hashes"]["experiments/owned_cpu/cpu.c"])
            self.assertEqual(inventory.sha256(header_path),
                             refreshed["source_hashes"]["experiments/owned_cpu/cpu.h"])

    def test_stale_source_hash_has_named_rejection(self):
        hashes = dict(self.document["source_hashes"])
        hashes["experiments/owned_cpu/cpu.c"] = "0" * 64
        errors = inventory.hash_errors(ROOT, hashes)
        self.assertIn("stale source hash: experiments/owned_cpu/cpu.c", errors)

    def test_hidden_runtime_global_has_named_rejection(self):
        source = self.runtime + "\nstatic uint32_t hidden_cpu_state;\n"
        errors = inventory.runtime_global_errors(source)
        self.assertIn("hidden mutable global state: hidden_cpu_state", errors)

    def test_callback_owner_mutation_has_named_rejection(self):
        source = self.fixture.replace(
            "    iso_probe_reentry(machine);",
            "    machine->owner = 1u;\n    iso_probe_reentry(machine);",
            1,
        )
        errors = inventory.callback_owner_errors(source)
        self.assertIn("callback mutates owner binding: iso_read16", errors)

    def test_compile_database_has_closed_source_set(self):
        self.assertEqual(set(self.document["compiled_sources"]),
                         inventory.EXPECTED_COMPILED_SOURCES)

    def test_compile_contract_is_scoped_to_owned_cmake_targets(self):
        rows = []
        for source in sorted(inventory.EXPECTED_COMPILED_SOURCES):
            if source == "experiments/owned_cpu/cpu.c":
                target = "owned_cpu"
            elif source == "third_party/unity/src/unity.c":
                target = "owned_cpu_unity"
            elif source == "tests/cpu/guest_fixture.c":
                target = "owned_cpu_diagnostic"
            else:
                target = "owned_cpu_" + Path(source).stem.removeprefix("test_")
            rows.append({"file": source, "arguments": ["cc", "-std=c17", "-O0", "-o",
                         f"experiments/owned_cpu/CMakeFiles/{target}.dir/{Path(source).name}.o",
                         "-c", source]})
        # Shared owned sources and C++ have unrelated flags on SDK targets.
        rows.extend([
            {"file": "experiments/owned_cpu/cpu.c", "arguments": ["cc", "-std=c17", "-o",
             "CMakeFiles/glueyneo.dir/experiments/owned_cpu/cpu.c.o"]},
            {"file": "src/chips/ym2610_candidate.cpp", "arguments": ["c++", "-std=c++14", "-o",
             "CMakeFiles/gn_ym2610_candidate.dir/src/chips/ym2610_candidate.cpp.o"]},
        ])
        with tempfile.TemporaryDirectory() as temporary:
            build = Path(temporary)
            (build / "build.ninja").touch()
            database = build / "compile_commands.json"
            archive = mock.Mock(returncode=0, stdout="ar qc libowned_cpu.a experiments/owned_cpu/CMakeFiles/owned_cpu.dir/cpu.c.o\n")
            with (mock.patch.object(inventory, "load_cache", return_value={}),
                  mock.patch.object(inventory.shutil, "which", return_value="ninja"),
                  mock.patch.object(inventory.subprocess, "run", return_value=archive)):
                def check(commands):
                    database.write_text(json.dumps(commands), encoding="utf-8")
                    return inventory.compile_errors(ROOT, build, sorted(inventory.EXPECTED_COMPILED_SOURCES))

                self.assertEqual([], check(rows))
                missing_flag = copy.deepcopy(rows)
                missing_flag[0]["arguments"].remove("-std=c17")
                self.assertTrue(any("not strict C17" in error for error in check(missing_flag)))
                missing_opt = copy.deepcopy(rows)
                missing_opt[0]["arguments"].remove("-O0")
                self.assertTrue(any("optimization mode missing" in error for error in check(missing_opt)))
                missing_source = [row for row in rows if row["file"] != "tests/owned_cpu/test_state.c"]
                self.assertIn("missing compiled source: tests/owned_cpu/test_state.c", check(missing_source))
                extra = {"file": "src/instance.c", "arguments": ["cc", "-std=c17", "-O0", "-o",
                         "experiments/owned_cpu/CMakeFiles/owned_cpu.dir/foreign.c.o"]}
                self.assertIn("extra compiled source: src/instance.c", check(rows + [extra]))
                # SDK compilation of cpu.c cannot substitute for its owned row.
                without_owned = [row for row in rows if "owned_cpu.dir" not in " ".join(row["arguments"])]
                self.assertIn("missing compiled source: experiments/owned_cpu/cpu.c", check(without_owned))
                sanitized = copy.deepcopy(rows)
                for row in sanitized[:-2]:
                    row["arguments"].extend(["-fsanitize=address,undefined", "-fno-sanitize-recover=all"])
                def ninja_commands(command, **kwargs):
                    if command[-1] == "owned_cpu":
                        return archive
                    return mock.Mock(returncode=0, stdout=f"cc -fsanitize=address,undefined -o {command[-1]} objects.o\n")
                with (mock.patch.object(inventory, "load_cache", return_value={"GLUEYNEO_OWNED_CPU_SANITIZER": "ADDRESS_UNDEFINED"}),
                      mock.patch.object(inventory.subprocess, "run", side_effect=ninja_commands)):
                    self.assertEqual([], check(sanitized))
                    sanitized[0]["arguments"].remove("-fsanitize=address,undefined")
                    self.assertTrue(any("ASan+UBSan missing" in error for error in check(sanitized)))

    def test_manifest_corruption_controls(self):
        import copy
        document = inventory.make_manifest(ROOT)
        self.assertEqual([], inventory.manifest_errors(ROOT, document))
        for kind in ("missing", "duplicate", "stale", "forbidden"):
            broken = copy.deepcopy(document)
            if kind == "missing":
                broken["files"].pop()
            elif kind == "duplicate":
                broken["files"].append(broken["files"][0])
            elif kind == "stale":
                broken["files"][0]["sha256"] = "0" * 64
            else:
                broken["files"].append({"path": "third_party/musashi/m68kcpu.c"})
            self.assertTrue(any(kind in error for error in inventory.manifest_errors(ROOT, broken)), kind)

    def test_self_test_reaches_every_mutation_control(self):
        expected_named = [
            "missing field inventory entry: reset_signal_events",
            "extra field inventory entry: invented",
            "missing private state inventory entry: reset_signal_events",
            "private state inventory core identity is stale against cpu.c SHA-256",
            "private state core identity is stale against cpu.c SHA-256",
            "stale source hash: experiments/owned_cpu/cpu.c",
            "hidden mutable global state: hidden_cpu_state",
            "callback mutates owner binding: iso_read16",
        ]
        named_calls = []
        manifest_controls = []
        real_expect_named = inventory.expect_named
        real_manifest_errors = inventory.manifest_errors
        baseline_manifest = inventory.make_manifest(ROOT)

        def observe_expect_named(errors, expected):
            named_calls.append((expected, list(errors)))
            return real_expect_named(errors, expected)

        def observe_manifest_errors(root, document):
            errors = real_manifest_errors(root, document)
            if document != baseline_manifest:
                kinds = [kind for kind in ("missing", "duplicate", "stale", "forbidden")
                         if any(kind in error for error in errors)]
                manifest_controls.append((kinds, list(errors), copy.deepcopy(document)))
            return errors

        output = StringIO()
        raised = None
        with (mock.patch.object(inventory, "expect_named", side_effect=observe_expect_named),
              mock.patch.object(inventory, "manifest_errors", side_effect=observe_manifest_errors),
              redirect_stdout(output)):
            try:
                result = inventory.run_self_test(ROOT, copy.deepcopy(self.document))
            except inventory.InventoryError as error:
                raised = str(error)
                result = None

        self.assertEqual(
            0, result,
            f"actual self-test must reach PASS after every named and manifest control; raised={raised!r}; "
            f"first named errors={named_calls[0][1] if named_calls else None!r}",
        )
        self.assertEqual(expected_named, [expected for expected, _ in named_calls])
        self.assertIn("PASS:", output.getvalue())
        self.assertEqual(4, len(manifest_controls))
        observed_kinds = []
        for kinds, errors, document in manifest_controls:
            self.assertEqual(1, len(kinds), f"manifest mutation must have one real rejection: {errors}")
            observed_kinds.extend(kinds)
            self.assertNotEqual(baseline_manifest, document)
        self.assertCountEqual(["missing", "duplicate", "stale", "forbidden"], observed_kinds)

    def test_self_test_rejects_suppressed_named_control(self):
        target = "missing field inventory entry: reset_signal_events"
        expected_error = f"self-test control missed named rejection: {target}"

        for mode in ("suppressed", "misreported"):
            with self.subTest(mode=mode):
                reached = []
                actual_error = None
                real_field_errors = inventory.field_errors

                def observe_field_errors(entries, source):
                    errors = real_field_errors(entries, source)
                    if len(entries) == len(self.document["fields"]) - 1:
                        names = {entry.get("name") for entry in entries}
                        reached.append(names)
                        if "reset_signal_events" not in names:
                            if mode == "suppressed":
                                return [error for error in errors if error != target]
                            return ["missing field inventory entry: bus_cycles"
                                    if error == target else error for error in errors]
                    return errors

                with mock.patch.object(inventory, "field_errors", side_effect=observe_field_errors):
                    try:
                        inventory.run_self_test(ROOT, copy.deepcopy(self.document))
                    except inventory.InventoryError as error:
                        actual_error = str(error)

                self.assertEqual(1, len(reached), "the real missing-field mutation must be exercised")
                self.assertEqual(
                    {entry["name"] for entry in self.document["fields"]
                     if entry["name"] != "reset_signal_events"},
                    reached[0],
                )
                self.assertEqual(expected_error, actual_error)


if __name__ == "__main__":
    unittest.main()
