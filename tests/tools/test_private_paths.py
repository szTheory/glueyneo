#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression tests for private-path redaction and the public-sink scan."""

from __future__ import annotations

import io
import json
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
