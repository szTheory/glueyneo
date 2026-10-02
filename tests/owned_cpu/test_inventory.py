"""Corruption controls for the owned CPU source inventory checker."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.owned_cpu import inventory


class InventoryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = (ROOT / inventory.RUNTIME_PATH).read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
