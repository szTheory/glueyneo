"""MIT: consequential controls for CPU admission evidence."""
import importlib.util
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cpu_audit", ROOT / "tools/cpu/audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class BudgetControls(unittest.TestCase):
    def test_budget_rejects_empty_ledger(self):
        self.assertFalse(audit.validate_budget({}), "empty ledger must not qualify")

    def test_each_cap_equality_and_one_over(self):
        at_cap = dict(attempts=2, total_seconds=57600, attempt_seconds=28800,
                      upstream_files=6, handwritten=5000, semantic=500, helpers=600,
                      generated_files=2, generated_lines=50000, generated_bytes=2097152)
        self.assertTrue(audit.validate_budget(at_cap))
        for name in at_cap:
            with self.subTest(cap=name):
                over = dict(at_cap)
                over[name] += 1
                self.assertFalse(audit.validate_budget(over), name)
                missing = dict(at_cap)
                del missing[name]
                self.assertFalse(audit.validate_budget(missing), name)
                malformed = dict(at_cap)
                malformed[name] = None
                self.assertFalse(audit.validate_budget(malformed), name)

    def test_missing_empty_and_null_ledgers(self):
        with tempfile.TemporaryDirectory() as name:
            subject = Path(name)
            path = subject / "experiments/cpu/budget-ledger.json"
            with self.assertRaisesRegex(audit.AuditError, "missing budget ledger"):
                audit.load_ledger(subject)
            path.parent.mkdir(parents=True)
            for invalid in (None, {}, {"attempts": []}):
                path.write_text(json.dumps(invalid))
                with self.assertRaisesRegex(audit.AuditError, "incomplete budget ledger"):
                    audit.load_ledger(subject)

class SourceControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cpu-controls-")
        self.subject = Path(self.temp.name)
        for directory in ("third_party", "experiments", "tests", "tools"):
            shutil.copytree(ROOT / directory, self.subject / directory,
                            ignore=shutil.ignore_patterns("evidence", "__pycache__"))
        for name in ("CMakeLists.txt", "LICENSE"):
            shutil.copy2(ROOT / name, self.subject / name)
        self.manifest_path = self.subject / "tools/cpu/source-manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text())

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def update_hash(self, relative):
        row = next(row for row in self.manifest["files"] if row["path"] == relative)
        row["sha256"] = audit.sha(self.subject / relative)
        if row["origin"] == "Glueyneo":
            row["revision"] = "sha256:" + row["sha256"]
        self.write_manifest()

    def test_null_classification_wrong_pin_and_stale_recipe(self):
        original = copy.deepcopy(self.manifest)
        for field in ("origin", "revision", "compiled", "generated", "copied"):
            self.manifest = copy.deepcopy(original)
            self.manifest["files"][0][field] = None
            self.write_manifest()
            with self.assertRaises(audit.AuditError):
                audit.inventory(self.subject)
        self.manifest = copy.deepcopy(original)
        self.manifest["candidate"] = "wrong revision"
        self.write_manifest()
        with self.assertRaisesRegex(audit.AuditError, "incorrect source pin"):
            audit.inventory(self.subject)
        self.manifest = copy.deepcopy(original)
        self.manifest["adaptation_recipe"]["sha256"] = "0" * 64
        self.write_manifest()
        with self.assertRaisesRegex(audit.AuditError, "stale adaptation recipe"):
            audit.inventory(self.subject)

    def test_generator_template_is_not_a_compiled_test_source(self):
        row = next(r for r in self.manifest["files"] if r["path"] == "third_party/musashi/m68k_in.c")
        self.assertEqual([], row["compiled"])
        row["compiled"] = ["test"]
        self.write_manifest()
        with self.assertRaisesRegex(audit.AuditError, "unclassified runtime/adaptation source"):
            audit.inventory(self.subject)

    def test_semantic_source_change_requires_new_review(self):
        ledger = audit.load_ledger(ROOT)
        audit.check_reviewed_sources(self.subject, ledger)
        source = self.subject / "third_party/musashi/m68kcpu.c"
        source.write_text(source.read_text().replace("ctx->instructions++;", "ctx->instructions += 2;"))
        with self.assertRaisesRegex(audit.AuditError, "stale semantic/source review"):
            audit.check_reviewed_sources(self.subject, ledger)

    def test_current_recipe_must_reproduce_current_inputs(self):
        source = self.subject / "tools/cpu/adapt.py"
        source.write_text(source.read_text().replace("(dst/name).write_text(text)", '(dst/name).write_text(text + "\\n")'))
        with self.assertRaisesRegex(audit.AuditError, "current adaptation recipe mismatch"):
            audit.verify_recipe(self.subject, ROOT)

    def test_inventoried_test_header_cannot_hide_runtime_helper(self):
        relative = "tests/cpu/uncharged.h"
        (self.subject / relative).write_text("/* test-only header deliberately injected into runtime */\n")
        row = copy.deepcopy(next(r for r in self.manifest["files"] if r["path"] == "tests/cpu/guest_fixture.h"))
        row["path"] = relative
        self.manifest["files"].append(row)
        self.update_hash(relative)
        adapter = "experiments/cpu/cpu_adapter.c"
        path = self.subject / adapter
        path.write_text(path.read_text() + '\n#include "../../tests/cpu/uncharged.h"\n')
        self.update_hash(adapter)
        with self.assertRaisesRegex(audit.AuditError, "unclassified runtime dependency"):
            audit.closure(self.subject)

    def test_duplicate_unknown_and_inconsistent_sources(self):
        original = copy.deepcopy(self.manifest)
        self.manifest["files"].append(copy.deepcopy(self.manifest["files"][0]))
        self.write_manifest()
        with self.assertRaisesRegex(audit.AuditError, "duplicate source"):
            audit.inventory(self.subject)
        self.manifest = copy.deepcopy(original)
        self.manifest["files"][0]["path"] = "unknown.c"
        self.write_manifest()
        with self.assertRaisesRegex(audit.AuditError, "unknown or missing"):
            audit.inventory(self.subject)
        self.manifest = copy.deepcopy(original)
        self.manifest["files"][0]["sha256"] = "0" * 64
        self.write_manifest()
        with self.assertRaisesRegex(audit.AuditError, "source hash mismatch"):
            audit.inventory(self.subject)

    def test_removed_notice_rejected_even_with_updated_hash(self):
        relative = "third_party/musashi/m68kcpu.c"
        path = self.subject / relative
        path.write_text(path.read_text().replace("Permission is hereby granted", "grant removed"))
        self.update_hash(relative)
        with self.assertRaisesRegex(audit.AuditError, "missing license notice"):
            audit.inventory(self.subject)

    def test_parallel_generation_and_interruption_do_not_replace_artifacts(self):
        before = {p: audit.sha(self.subject / p) for p in audit.OUTPUTS}
        receipt = self.subject / "generation.json"
        result = audit.regenerate(self.subject, receipt)
        self.assertEqual(2, result["independent_parallel_directories"])
        prior = receipt.read_bytes()
        with self.assertRaisesRegex(audit.AuditError, "injected interruption"):
            audit.regenerate(self.subject, receipt, interrupt=True)
        self.assertEqual(prior, receipt.read_bytes())
        fresh = self.subject / "interrupted.json"
        with self.assertRaisesRegex(audit.AuditError, "injected interruption"):
            audit.regenerate(self.subject, fresh, interrupt=True)
        self.assertFalse(fresh.exists())
        self.assertEqual(before, {p: audit.sha(self.subject / p) for p in audit.OUTPUTS})

    def test_compiled_forbidden_import_trips_closure(self):
        relative = "experiments/cpu/cpu_adapter.c"
        path = self.subject / relative
        path.write_text(path.read_text() + '\n#include <stdlib.h>\nvoid cpu_forbidden_probe(void) { (void)getenv("CPU_FORBIDDEN_PROBE"); }\n')
        self.update_hash(relative)
        # Exercise a real filesystem alias, including macOS /var -> /private/var.
        with tempfile.TemporaryDirectory(prefix="cpu-alias-") as directory:
            alias = Path(directory) / "subject"
            alias.symlink_to(self.subject, target_is_directory=True)
            with self.assertRaisesRegex(audit.AuditError, "forbidden runtime (AST reference|import)"):
                audit.closure(alias)

    def test_unresolved_host_import_is_rejected(self):
        with self.assertRaisesRegex(audit.AuditError, "forbidden runtime import"):
            audit.check_imports({"memcpy", "getenv"})

if __name__ == "__main__":
    unittest.main()
