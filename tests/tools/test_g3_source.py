# SPDX-License-Identifier: MIT
"""Specified-oracle regressions for the immutable historical G3 disposition."""

from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import g3_source as G
import private_paths as Q
import public_content as P

PLAN = ROOT / ".planning/milestones/ws-first-playable-game-2026-10-24/retired/2026-10-16-development-workflow/phase05/05-27-PLAN.md"
COMMIT = "63c1d2c217887c35de68f847ed0db59de6c6250e"
PATH = "tools/verify_playable.py"
SUFFIX_NAME = "." + "tm" + "p"


def added_source():
    diff = subprocess.run(["git", "diff", "--unified=0", "--no-color", "--no-renames",
                           COMMIT + "^", COMMIT, "--", PATH], cwd=ROOT,
                          capture_output=True, check=True, text=True, timeout=10).stdout
    return "\n".join(line[1:] for line in (diff.split("\n@@", 1) + [""])[1].splitlines()
                     if line.startswith("+"))


@unittest.skipUnless((ROOT / ".git").exists(), "historical G3 requires repository history")
class SourceDispositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = added_source()

    def test_exact_reviewed_source_passes_without_relaxing_redactor(self):
        self.assertNotEqual(Q.redact(self.text), self.text)
        self.assertFalse(G.private_root_finding(COMMIT, PATH, self.text))
        with self.assertRaises(Q.PrivatePathError):
            Q.scan_public(G._SOURCE_LINE)

    def test_unknown_revision_path_or_any_byte_change_remains_closed(self):
        cases = [(COMMIT[:-1] + "f", PATH, self.text),
                 (COMMIT[:12], PATH, self.text),
                 (COMMIT, PATH + ".other", self.text),
                 (COMMIT, "(commit message)", self.text),
                 (COMMIT, PATH, self.text + "\n"),
                 (COMMIT, PATH, self.text.replace("temporary_name = None", "temporary_name = 0")),
                 (COMMIT, PATH, self.text + '\n' + G._SOURCE_LINE)]
        for index, (commit, path, text) in enumerate(cases):
            with self.subTest(case=index):
                self.assertTrue(G.private_root_finding(commit, path, text))

    def test_real_encoded_paths_and_identity_are_never_dispositioned(self):
        slash = chr(47)
        path = slash + "tm" + "p" + slash + "x"
        values = [path, path.replace(slash, "%" + "2F"),
                  path.replace(slash, "%" + "252F"),
                  path.replace(slash, chr(92) + "u002f"),
                  path.replace(slash, chr(0xff0f)),
                  slash + "Us" + "ers" + slash + "synthetic" + slash + "x", str(Path.home()) + slash + "x",
                  "owner " + Path.home().name + " ran it"]
        for index, value in enumerate(values):
            with self.subTest(case=index):
                self.assertTrue(G.private_root_finding(COMMIT, PATH, self.text + "\n" + value))
                self.assertTrue(G.private_root_finding("unknown", PATH, value))

    def test_identity_scans_original_even_on_exact_disposition(self):
        with mock.patch.object(Q, "_username_token_present", return_value=True) as detector:
            self.assertTrue(G.private_root_finding(COMMIT, PATH, self.text))
            detector.assert_called_once_with(self.text)

    def test_remaining_root_is_scanned_after_suffix_substitution(self):
        with mock.patch.object(Q, "redact", side_effect=lambda text: text + "changed") as detector:
            self.assertTrue(G.private_root_finding(COMMIT, PATH, self.text))
            scanned = detector.call_args.args[0]
            self.assertEqual(scanned, self.text.replace(G._SOURCE_LINE,
                             G._SOURCE_LINE.replace(G._SUFFIX, '"temporary-suffix"'), 1))


@unittest.skipUnless(PLAN.exists() and (ROOT / ".git").exists(),
                     "embedded historical G3 requires planning and Git")
class EmbeddedGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        blocks = re.findall(r"<automated>(.*?)</automated>", PLAN.read_text(), re.S)
        cls.gates = [block for block in blocks if "segment-3 commits" in block]
        cls.code = shlex.split(cls.gates[0])[-1]
        cls.hx = eval(re.search(r"hx=(.*?);PL=", cls.code).group(1), {"re": re})
        disposition = json.loads(PLAN.with_name("05-27-SOUND-G3-DISPOSITION.json").read_text())
        cls.dq = eval(re.search(r"(?m)^DQ=(.*)$", cls.code).group(1),
                      {"SD": disposition, "hashlib": hashlib})
        cls.rule_expression = re.search(r"rl=(.*?);pa=", cls.code).group(1)

    def test_three_copies_are_identical_and_use_full_commit_and_path(self):
        self.assertEqual(len(self.gates), 3)
        self.assertEqual(len(set(self.gates)), 1)
        self.assertIn("for r in rl(c,p,t)]", self.code)
        self.assertIn("import public_content as P,private_paths as Q,g3_source as G;", self.code)

    def rules(self, text, **overrides):
        environment = dict(P=P, Q=Q, G=G, D=set(), N=set(), PS=set(),
                           hx=type(self).hx, DQ=type(self).dq)
        environment.update(overrides)
        return eval(self.rule_expression, environment)(COMMIT, PATH, text)

    def test_full_rule_expression_accepts_only_reviewed_suffix(self):
        text = added_source()
        self.assertEqual(self.rules(text), [])
        self.assertIn("private-root", self.rules(text + "\n"))

    def test_all_other_predicates_scan_original_bytes_and_multiple_findings(self):
        text = added_source()
        marker = "a" * 32
        # Held-out rules still see the original byte stream, including the suffix.
        with mock.patch.object(P, "scan_bytes", return_value={"findings": [{"rules": ["identity", "credential"]}]}) as scanner:
            self.assertEqual(self.rules(text, N={SUFFIX_NAME}), ["credential", "identity", "media-name"])
            scanner.assert_called_once_with(text.encode(), "x")
        rules = self.rules(text + "\n" + marker, D={marker}, N={SUFFIX_NAME}, PS={marker})
        self.assertTrue({"private-root", "media-digest", "media-name", "guest-pc"}.issubset(rules))

    def test_binary_and_undeclared_ownership_controls_are_retained(self):
        def git(*args):
            return "-\t-\tunknown.bin\n" if "--numstat" in args else "unknown.bin\n"
        environment = dict(cs=["unreviewed"], g=git, AL={}, DA={}, PL=".planning/workstreams/first-playable-game/", pl=lambda c: "")
        binary = eval(re.search(r"B=(.*?);U=", self.code).group(1), environment)
        ownership = eval(re.search(r"U=(.*?);\[print", self.code).group(1), environment)
        self.assertEqual(binary, [("unreviewed", "unknown.bin", "binary-content")])
        self.assertEqual(ownership, [("unreviewed", "unknown.bin", "undeclared-file")])


if __name__ == "__main__":
    unittest.main()
