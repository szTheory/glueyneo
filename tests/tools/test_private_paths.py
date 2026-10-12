#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression tests for private-path redaction and the public-sink scan."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests/libretro"))
import private_paths  # noqa: E402
import retroarch_smoke  # noqa: E402
import verify_playable as playable  # noqa: E402

HOME = str(Path.home())
# Built from parts so the public-content scan does not read them as real homes.
RUNNER_HOME = "/" + "home/runner"


class RedactionTest(unittest.TestCase):
    # Each class reproduced a leak through the previous regex sanitizers.
    BYPASSES = {
        "cmake object dir without leading slash": "CMakeFiles/x.dir" + HOME + "/p/a.c.o",
        "home without leading slash": HOME.lstrip("/") + "/p/a.c",
        "word prefix": "dir_" + HOME + "/x",
        "dot prefix": "." + "/" + "Users/u/x",
        "percent-encoded": "%2FUsers%2Fu%2Fx",
        "json-escaped": json.dumps("/" + "Users/u/x").replace("/", "\\/"),
        "case-folded": "/" + "users/u/x",
        "linux home": "/" + "home/u/x",
        "var tmp": "/var/tmp/x",
        "private var tmp": "/" + "private/var/tmp/x",
        "windows": "C:" + "\\" + "Users\\u\\x",
        "fullwidth slash": "\uff0fUsers\uff0fu",
        "newline suffix": "tool failed: " + HOME + "/a\nb/c",
        "macOS temporary realpath": "/" + "private/var/folders/ab/T/x",
    }

    def test_every_known_bypass_is_redacted_and_scans_clean(self) -> None:
        for label, value in self.BYPASSES.items():
            with self.subTest(bypass=label):
                safe = private_paths.redact(value)
                self.assertIn("[redacted-path]", safe)
                private_paths.scan_public(json.dumps(safe))

    def test_scan_fails_closed_on_every_unredacted_bypass(self) -> None:
        for label, value in self.BYPASSES.items():
            with self.subTest(bypass=label), self.assertRaises(private_paths.PrivatePathError):
                private_paths.scan_public(value)

    def test_benign_text_is_preserved(self) -> None:
        for value in ("chrome/extension ok", "build/tmp-like ok", "lanes: shared-build pass",
                      "RetroPad RIGHT <- Right Arrow", "macOS 26.6.2 arm64"):
            with self.subTest(value=value):
                self.assertEqual(private_paths.redact(value), value)
                private_paths.scan_public(value)

    def test_scan_rejects_the_bare_local_username(self) -> None:
        name = Path.home().name
        if len(name) < 3:
            self.skipTest("username too short to scan as a token")
        if name.casefold() in private_paths.SERVICE_ACCOUNT_NAMES and os.environ.get("GITHUB_ACTIONS") == "true":
            self.skipTest("generic service-account home name is not scanned as a token under GitHub Actions")
        with self.assertRaises(private_paths.PrivatePathError):
            private_paths.scan_public(f"owner {name} ran it")

    def test_extra_runtime_roots_are_redacted_in_slashless_form(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-root-") as temporary:
            root = Path(temporary) / "run"
            value = "CMakeFiles/t.dir" + str(root.resolve()) + "/x.o"
            self.assertIn("[redacted-path]", private_paths.redact(value, extra_roots=(root,)))
            with self.assertRaises(private_paths.PrivatePathError):
                private_paths.scan_public(str(root.resolve()).lstrip("/"), (root,))

EXTRA_ROOT = "/opt/ci/work/glueyneo"


def _slash_variant(root: str, separator: str) -> str:
    return root.replace("/", separator)


class CanonicalRootTest(unittest.TestCase):
    """One canonical form for every root, including a non-home extra root (CR-01, CR-02)."""

    VALUE = "err " + _slash_variant(EXTRA_ROOT, "\u2215") + "/build/x.o"

    def test_division_slash_root_is_redacted(self) -> None:
        safe = private_paths.redact(self.VALUE, extra_roots=(EXTRA_ROOT,))
        self.assertTrue(safe.endswith("[redacted-path]"), safe)
        self.assertNotIn("glueyneo", safe)
        with self.assertRaises(private_paths.PrivatePathError):
            private_paths.scan_public(self.VALUE, (EXTRA_ROOT,))

    def test_json_escaped_division_slash_root_fails_the_scan(self) -> None:
        with self.assertRaises(private_paths.PrivatePathError):
            private_paths.scan_public(json.dumps({"k": self.VALUE}), (EXTRA_ROOT,))

    def test_receipt_sink_cleans_keys_and_values(self) -> None:
        for where in ("key", "value"):
            with self.subTest(where=where), tempfile.TemporaryDirectory(prefix="glueyneo-canon-") as temporary:
                output = Path(temporary)
                lanes = {self.VALUE: {"status": "pass"}} if where == "key" else {"lane": {"status": self.VALUE}}
                receipt = {"status": "pass", "identity": {}, "lanes": lanes}
                with mock.patch.object(playable, "OUTPUT", output), \
                        mock.patch.object(playable, "ROOT", Path(EXTRA_ROOT)), \
                        mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    playable._write_receipt(receipt)
                written = (output / "receipt.json").read_text(encoding="utf-8") + stdout.getvalue()
                self.assertNotIn("opt\u2215ci", written)
                self.assertNotIn("opt" + "\u2215" + "ci", written)
                self.assertNotIn("glueyneo\u2215", written)
                self.assertNotIn("glueyneo\\u2215", written)
                self.assertNotIn("\\u2215", written)


def _variants(root: str) -> dict[str, str]:
    """The CR-01 separator and encoding table for one root, applied to its path text."""
    bare = root.lstrip("/")
    table = {
        "U+2215 separators": root.replace("/", "\u2215"),
        "U+2044 separators": root.replace("/", "\u2044"),
        "double percent": root.replace("/", "%252F"),
        "json escape text": root.replace("/", "\\/"),
        "NBSP separators": root.replace("/", "\u00a0"),
        "colon separators": root.replace("/", ":"),
    }
    for label, mark in (("dash", "-"), ("underscore", "_"), ("dot", ".")):
        table[f"{label}-mangled with leading separator"] = root.replace("/", mark)
        table[f"{label}-mangled without leading separator"] = bare.replace("/", mark)
    return table


class BypassMatrixTest(unittest.TestCase):
    """Every CR-01 variant for the home, checkout and a non-home root (CR-01, CR-02, IN-04)."""

    ROOTS = {"home": HOME, "checkout": str(ROOT), "non-home": EXTRA_ROOT}
    EXTRA = (ROOT, EXTRA_ROOT)

    def test_every_variant_is_cut_and_fails_the_scan(self) -> None:
        for root_label, root in self.ROOTS.items():
            last = Path(root).name.casefold()
            for label, variant in _variants(root).items():
                value = "err " + variant + "/p/a.o"
                with self.subTest(root=root_label, variant=label):
                    safe = private_paths.redact(value, extra_roots=self.EXTRA)
                    self.assertIn("[redacted-path]", safe)
                    self.assertNotIn(last, safe.casefold())
                    private_paths.scan_public(json.dumps(safe), self.EXTRA)
                    with self.assertRaises(private_paths.PrivatePathError):
                        private_paths.scan_public(value, self.EXTRA)
                    with self.assertRaises(private_paths.PrivatePathError):
                        private_paths.scan_public(json.dumps(value), self.EXTRA)
                    with self.assertRaises(private_paths.PrivatePathError):
                        private_paths.scan_public(json.dumps({"k": value}), self.EXTRA)

    def test_temporary_directory_written_with_division_slash(self) -> None:
        value = "err " + "/tmp/x".replace("/", "\u2215")
        self.assertIn("[redacted-path]", private_paths.redact(value))
        with self.assertRaises(private_paths.PrivatePathError):
            private_paths.scan_public(value)
        with self.assertRaises(private_paths.PrivatePathError):
            private_paths.scan_public(json.dumps(value))

    def test_existing_bypasses_are_rejected_in_json_encoded_form(self) -> None:
        for label, value in RedactionTest.BYPASSES.items():
            with self.subTest(bypass=label), self.assertRaises(private_paths.PrivatePathError):
                private_paths.scan_public(json.dumps(value))

    def test_benign_text_is_unchanged_and_passes(self) -> None:
        for value in ("chrome/extension ok", "build/tmp-like ok", "docs/tmp/notes", "public_users_list",
                      "lanes: shared-build pass", "RetroPad RIGHT <- Right Arrow", "macOS 26.6.2 arm64"):
            with self.subTest(value=value):
                self.assertEqual(private_paths.redact(value, extra_roots=self.EXTRA), value)
                private_paths.scan_public(value, self.EXTRA)
                private_paths.scan_public(json.dumps(value), self.EXTRA)


def _home(path: str, github_actions: bool):
    """Patch the home lookup and set or remove GITHUB_ACTIONS regardless of the host."""
    environment = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
    if github_actions:
        environment["GITHUB_ACTIONS"] = "true"
    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch.object(Path, "home", return_value=Path(path)))
    stack.enter_context(mock.patch.dict(os.environ, environment, clear=True))
    return stack


class ServiceAccountTest(unittest.TestCase):
    """WR-06: a generic account name is skipped only under GitHub Actions (T-04-59, T-04-60)."""

    def test_generic_runner_name_passes_under_github_actions(self) -> None:
        with _home(RUNNER_HOME, True):
            private_paths.scan_public("lanes: the runner wrote a receipt")

    def test_runner_receipt_is_written_under_github_actions(self) -> None:
        receipt = {"status": "pass", "identity": {}, "lanes": {"lane": {"status": "the runner wrote it"}}}
        with tempfile.TemporaryDirectory(prefix="glueyneo-ci-") as temporary:
            output = Path(temporary)
            with _home(RUNNER_HOME, True), \
                    mock.patch.object(playable, "OUTPUT", output), \
                    mock.patch("sys.stdout", new_callable=io.StringIO):
                status = playable._write_receipt(receipt)
        self.assertEqual(status, "pass")

    def test_runner_home_paths_still_fail_under_github_actions(self) -> None:
        with _home(RUNNER_HOME, True):
            for value in (RUNNER_HOME + "/work/x", (RUNNER_HOME + "/work/x").replace("/", "\u2215")):
                with self.subTest(value=value), self.assertRaises(private_paths.PrivatePathError):
                    private_paths.scan_public(value)

    def test_generic_name_is_still_rejected_outside_github_actions(self) -> None:
        with _home("/" + "Users/build", False), self.assertRaises(private_paths.PrivatePathError):
            private_paths.scan_public("build ok")

    def test_personal_name_is_rejected_under_github_actions(self) -> None:
        with _home("/" + "Users/alice", True), self.assertRaises(private_paths.PrivatePathError):
            private_paths.scan_public("owner alice ran it")

    def test_repository_relative_inventory_paths_pass(self) -> None:
        private_paths.scan_public_value({"entries": [{"path": ".planning/tmp/notes.md"},
                                                     {"path": "tmp/home/x"}, {"path": "docs/var/y"}]})


class SinkTest(unittest.TestCase):
    def test_artifact_tree_omits_cmake_internals(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glueyneo-artifacts-") as temporary:
            output = Path(temporary)
            tree = output / "installed"
            mangled = tree / "consumer/build/CMakeFiles/x.dir" / HOME.lstrip("/") / "a.c.o"
            mangled.parent.mkdir(parents=True)
            mangled.write_bytes(b"o")
            (tree / "consumer/build/consumer").write_bytes(b"exe")
            record = playable._artifact_tree(tree, output)
            paths = [row["path"] for row in record["entries"]]
            self.assertEqual(paths, ["consumer/build/consumer"])
            private_paths.scan_public(json.dumps(record))

    def test_receipt_writer_fails_closed_on_a_surviving_path(self) -> None:
        receipt = {"status": "pass", "identity": {}, "lanes": {HOME + "/lane": {"status": "pass"}}}
        with tempfile.TemporaryDirectory(prefix="glueyneo-receipt-") as temporary:
            output = Path(temporary)
            with mock.patch.object(playable, "OUTPUT", output), \
                    mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                status = playable._write_receipt(receipt)
            written = (output / "receipt.json").read_text(encoding="utf-8")
        self.assertEqual(status, "fail")
        self.assertEqual(json.loads(written), {"status": "fail", "reason": "private-path-survived"})
        self.assertNotIn(HOME, written + stdout.getvalue())

    def test_smoke_output_fails_closed_on_a_surviving_path(self) -> None:
        result: dict[str, object] = {"status": "pass", "identity": {HOME + "/core": "x"}}
        text = retroarch_smoke.public_json(result)
        self.assertEqual(json.loads(text), {"status": "fail", "reason": "private-path-survived"})
        self.assertEqual(result["status"], "fail")

    def test_unscannable_value_fails_closed_as_a_private_path_error(self) -> None:
        """GIN-02: a structure json.dumps cannot serialize is refused, not raised as TypeError."""
        for value in ({("a", "b"): 1}, {"k": {(1, 2): "v"}}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(private_paths.PrivatePathError):
                    private_paths.scan_public_value(value)

    def test_specific_root_overmatch_in_unrelated_text_is_a_deliberate_fail_closed_limit(self) -> None:
        """GIN-01 (accepted): a specific root is matched anywhere, so embedded look-alikes are flagged."""
        root = "/opt/glueyneo-overmatch/checkout"
        with self.assertRaises(private_paths.PrivatePathError):
            private_paths.scan_public("x" + root + "/file", (root,))
        with self.assertRaises(private_paths.PrivatePathError):
            private_paths.scan_public_value({"note": "x" + root}, (root,))

    def test_scan_public_value_scans_keys_and_decoded_values(self) -> None:
        for label, value in (("key", {"fullwidth key \uff0ftmp\uff0fx": "ok"}),
                             ("nested value", {"a": [{"b": "x \u2215" + "tmp\u2215y"}]}),
                             ("tuple value", {"a": ("ok", "\uff0fUsers\uff0fu")})):
            with self.subTest(where=label), self.assertRaises(private_paths.PrivatePathError):
                private_paths.scan_public_value(value)
        private_paths.scan_public_value({"lane": {"status": "pass", "n": 3, "ok": None}})

    def test_smoke_output_scans_decoded_values_and_keys(self) -> None:
        division = str(ROOT).replace("/", "\u2215")
        for label, result in (("nested value", {"status": "pass", "identity": {"core": [division + "/core"]}}),
                              ("key", {"status": "pass", "identity": {division + "/core": "x"}})):
            with self.subTest(where=label):
                text = retroarch_smoke.public_json(dict(result))
                self.assertEqual(json.loads(text), {"status": "fail", "reason": "private-path-survived"})

    def test_diagnostic_output_never_keeps_a_mangled_checkout_root(self) -> None:
        mangled = str(ROOT).replace("/", "-")
        record = retroarch_smoke.build_diagnostic(
            stage="load", return_code=1, survived_before_screenshot=False,
            output="CMakeFiles/x.dir" + mangled + "/a.c.o failed")
        self.assertNotIn("glueyneo", json.dumps(record))

    def test_frontend_evidence_rejects_a_division_slash_home_path(self) -> None:
        summary = json.loads((ROOT / playable.FRONTEND_EVIDENCE).read_text(encoding="utf-8"))
        playable.validate_frontend_evidence(summary)
        summary["os"] = "macOS " + HOME.replace("/", "\u2215") + "/build"
        with self.assertRaisesRegex(RuntimeError, "private absolute path"):
            playable.validate_frontend_evidence(summary)

    def test_smoke_main_turns_unexpected_errors_into_a_scanned_failure(self) -> None:
        arguments = ["retroarch_smoke.py", "--retroarch", "a.app", "--core", "b.dylib", "--content", "c.bin"]
        with mock.patch.object(sys, "argv", arguments), \
                mock.patch.object(retroarch_smoke, "run_smoke", side_effect=struct.error("unpack requires a buffer")), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            status = retroarch_smoke.main()
        self.assertEqual(status, 1)
        lines = stdout.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 1)
        result = json.loads(lines[0])
        self.assertEqual((result["status"], result["stage"]), ("blocked_or_unknown", "internal"))


class UnicodeCompositionTest(unittest.TestCase):
    """A decomposed (NFD) and a composed (NFC) spelling of one root are the same root.

    The previous normalization applied NFKC one code point at a time, so a base letter
    followed by a combining mark never composed (T-04-11, T-04-15, T-04-18, T-04-20).
    """

    COMPOSED = "/opt/café-build/glueyneo"
    DECOMPOSED = "/opt/café-build/glueyneo"

    def _both_directions(self):
        yield "NFC root, NFD text", self.COMPOSED, self.DECOMPOSED + "/src/a.c"
        yield "NFD root, NFC text", self.DECOMPOSED, self.COMPOSED + "/src/a.c"

    def test_t_04_11_decomposed_root_and_username_token_match_their_composed_form(self) -> None:
        for label, root, text in self._both_directions():
            with self.subTest(label):
                with self.assertRaises(private_paths.PrivatePathError):
                    private_paths.scan_public("error in " + text, (root,))
                self.assertTrue(private_paths.redact("error in " + text, extra_roots=(root,))
                                .endswith("[redacted-path]"))
        for label, home, token in (("NFC home, NFD token", "/zz/José", "by José today"),
                                   ("NFD home, NFC token", "/zz/José", "by José today")):
            with self.subTest(label), mock.patch.object(private_paths.Path, "home",
                                                        return_value=Path(home)):
                with self.assertRaises(private_paths.PrivatePathError):
                    private_paths.scan_public(token, ())

    def test_t_04_15_receipt_scan_rejects_a_decomposed_runtime_root(self) -> None:
        for label, root, text in self._both_directions():
            with self.subTest(label):
                receipt = {"status": "pass", "reason": "compiler said " + text}
                with self.assertRaises(private_paths.PrivatePathError):
                    private_paths.scan_public_value(receipt, (root,))

    def test_t_04_18_smoke_public_json_fails_closed_on_a_decomposed_root(self) -> None:
        for label, home, text in (("NFC home, NFD text", "/zz/Jos\u00e9", "/zz/Jose\u0301/build/x.o"),
                                  ("NFD home, NFC text", "/zz/Jose\u0301", "/zz/Jos\u00e9/build/x.o")):
            with self.subTest(label), mock.patch.object(private_paths.Path, "home",
                                                        return_value=Path(home)):
                output = retroarch_smoke.public_json({"status": "pass", "detail": text})
                self.assertEqual(json.loads(output),
                                 {"status": "fail", "reason": "private-path-survived"})

    def test_t_04_20_decomposed_form_of_a_root_is_not_missed(self) -> None:
        for label, root, text in self._both_directions():
            with self.subTest(label):
                safe = private_paths.redact(text, extra_roots=(root,))
                self.assertNotIn("glueyneo", safe)
                self.assertNotIn("build", safe)


if __name__ == "__main__":
    unittest.main()
