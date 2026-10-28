#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Negative controls for the runtime host-call source classification."""
from pathlib import Path
import shutil
import tempfile
import sys
import unittest

sys.dont_write_bytecode = True
from check_runtime_host import audit, has_host_call

ROOT = Path(__file__).resolve().parents[2]
NAMES = "read|write|clock|time|fopen"


class RuntimeHostTests(unittest.TestCase):
    def test_c_comments_do_not_create_runtime_host_dependencies(self):
        for source in (
                "/* read(fd, buf, n) */",
                "// write(fd, buf, n)\n",
                "void guest_read(void) { /* clock() is a manual term */ }"):
            with self.subTest(source=source):
                self.assertFalse(has_host_call(source, NAMES, cpp=False))
        self.assertTrue(has_host_call("void probe() { read(fd, p, n); }",
                                      NAMES, cpp=False))
        self.assertFalse(has_host_call('const char *s = "/* read() */";',
                                       NAMES, cpp=False))
        self.assertTrue(has_host_call('const char *s = "//"; read(fd, p, n);',
                                      NAMES, cpp=False))

    def test_owned_cpp_host_calls_rejected(self):
        for expression in ("read(fd, buf, n)", "::read(fd, buf, n)",
                           "std::time(nullptr)", "fopen(path, mode)"):
            with self.subTest(expression=expression):
                self.assertTrue(has_host_call(expression, NAMES, cpp=True))

    def test_member_calls_are_not_global_host_calls(self):
        for expression in ("chip.read(port)", "chip->write(port, data)",
                           "callbacks.read(userdata, address)", "chip.clock()"):
            with self.subTest(expression=expression):
                self.assertFalse(has_host_call(expression, NAMES, cpp=True))
        self.assertTrue(has_host_call("chip.read(0); ::read(fd, p, n)", NAMES, cpp=True))

    def test_changed_immutable_source_fails_before_exclusion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "third_party/ymfm", root / "third_party/ymfm")
            (root / "tests/chips").mkdir(parents=True)
            shutil.copy2(ROOT / "tests/chips/check_ym2610.py",
                         root / "tests/chips/check_ym2610.py")
            source = root / "third_party/ymfm/src/ymfm_opn.cpp"
            audit(root, [source], NAMES)
            owned = root / "owned.cpp"
            for expression in ("read(fd, buf, n)", "::read(fd, buf, n)",
                               "std::time(nullptr)"):
                owned.write_text("void probe() { " + expression + "; }")
                with self.assertRaisesRegex(ValueError, "Ambient host call"):
                    audit(root, [source, owned], NAMES)
            source.write_text(source.read_text() + "\nvoid bad() { time(0); }\n")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                audit(root, [source], NAMES)


if __name__ == "__main__":
    unittest.main()
