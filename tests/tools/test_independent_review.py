#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for the independent-review containment, verdict and transcription gate."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import independent_review as review  # noqa: E402

REVISION = "0123456789abcdef0123456789abcdef01234567"


def init_event(scratch: str, tools=("Read", "Grep", "Glob"), cwd: str | None = None) -> dict:
    return {"type": "system", "subtype": "init", "tools": list(tools),
            "cwd": scratch if cwd is None else cwd, "model": "test-model"}


def use(name: str, **arguments) -> dict:
    return {"type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": name, "input": arguments}]}}


def result_event(denials=()) -> dict:
    return {"type": "result", "subtype": "success", "permission_denials": list(denials)}


class ScratchCase(unittest.TestCase):
    def setUp(self) -> None:
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="independent-review-"))
        self.scratch = os.path.join(self.base, "scratch")
        os.mkdir(self.scratch)
        os.mkdir(self.scratch + "-evil")
        os.mkdir(os.path.join(self.scratch, "src"))
        self.addCleanup(shutil.rmtree, self.base, True)

    def stream(self, *accesses: dict) -> list[dict]:
        return [init_event(self.scratch), *accesses, result_event()]


class PathContainedTest(ScratchCase):
    def test_equal_to_scratch_is_contained(self) -> None:
        # D-GAP-01: the scratch directory itself is contained.
        self.assertTrue(review.path_contained(self.scratch, self.scratch, self.scratch))

    def test_under_scratch_is_contained(self) -> None:
        self.assertTrue(review.path_contained(self.scratch + "/sub/file", self.scratch, self.scratch))

    def test_relative_inside_is_contained(self) -> None:
        for relative in ("src/a.c", ".", "sub/file"):
            with self.subTest(path=relative):
                self.assertTrue(review.path_contained(relative, self.scratch, self.scratch))

    def test_sibling_prefix_is_not_contained(self) -> None:
        self.assertFalse(review.path_contained(self.scratch + "-evil/x", self.scratch, self.scratch))
        self.assertFalse(review.path_contained(self.scratch + "-evil", self.scratch, self.scratch))

    def test_dotdot_escape_is_not_contained(self) -> None:
        self.assertFalse(review.path_contained(self.scratch + "/../outside", self.scratch, self.scratch))
        self.assertFalse(review.path_contained("../outside", self.scratch, self.scratch))

    def test_dotdot_segment_inside_is_not_contained(self) -> None:
        self.assertFalse(review.path_contained(self.scratch + "/a/../b", self.scratch, self.scratch))

    def test_symlink_escape_is_not_contained(self) -> None:
        os.symlink(self.base, os.path.join(self.scratch, "link"))
        self.assertFalse(review.path_contained(self.scratch + "/link/x", self.scratch, self.scratch))
        self.assertFalse(review.path_contained("link", self.scratch, self.scratch))

    def test_symlinked_scratch_compared_by_realpath(self) -> None:
        alias = os.path.join(self.base, "alias")
        os.symlink(self.scratch, alias)
        self.assertTrue(review.path_contained(alias, self.scratch, self.scratch))
        self.assertTrue(review.path_contained(alias + "/src", self.scratch, self.scratch))
        self.assertTrue(review.path_contained(self.scratch + "/src", alias, self.scratch))


class GlobContainedTest(ScratchCase):
    def test_glob_relative_patterns_resolve_under_base(self) -> None:
        for pattern in ("**/*.c", "*.c", "src/*.py", "."):
            with self.subTest(pattern=pattern):
                self.assertTrue(review.glob_contained(pattern, self.scratch, self.scratch))
                self.assertFalse(review.glob_contained(pattern, self.scratch, os.path.dirname(self.scratch)))

    def test_glob_relative_dotdot(self) -> None:
        for pattern in ("../*.c", "src/../../*.c", "../scratch-evil/*.c"):
            with self.subTest(pattern=pattern):
                self.assertFalse(review.glob_contained(pattern, self.scratch, self.scratch))

    def test_glob_dotdot_after_wildcard(self) -> None:
        self.assertFalse(review.glob_contained("src/**/../../*.c", self.scratch, self.scratch))

    def test_glob_brace(self) -> None:
        self.assertFalse(review.glob_contained("{..,}/*.c", self.scratch, self.scratch))
        self.assertFalse(review.glob_contained(self.scratch + "{,-evil}/x", self.scratch, self.scratch))

    def test_glob_absolute_prefix_contained(self) -> None:
        for pattern in ("/*.c", "/src/**/*.py", "/a?.c"):
            with self.subTest(pattern=pattern):
                self.assertTrue(review.glob_contained(self.scratch + pattern, self.scratch, self.scratch))

    def test_glob_sibling_wildcard_not_contained(self) -> None:
        for suffix in ("*/x", "?/x", "[a-z]/x"):
            with self.subTest(suffix=suffix):
                self.assertFalse(review.glob_contained(self.scratch + suffix, self.scratch, self.scratch))

    def test_glob_absolute_without_wildcard_is_checked_as_a_path(self) -> None:
        self.assertTrue(review.glob_contained(self.scratch + "/src/a.c", self.scratch, self.scratch))
        self.assertFalse(review.glob_contained(self.scratch + "-evil/a.c", self.scratch, self.scratch))


class ExternalSymlinkTest(ScratchCase):
    def test_external_symlink_listed(self) -> None:
        os.symlink("/etc", os.path.join(self.scratch, "link"))
        self.assertEqual(review.external_symlinks(self.scratch), ["link"])

    def test_internal_symlink_not_listed(self) -> None:
        target = os.path.join(self.scratch, "src", "f")
        Path(target).write_text("x", encoding="utf-8")
        os.symlink(target, os.path.join(self.scratch, "src", "ok"))
        os.symlink("src", os.path.join(self.scratch, "dirlink"))
        self.assertEqual(review.external_symlinks(self.scratch), [])

    def test_scratch_external_symlink_refused(self) -> None:
        scratch_file = Path(self.base) / "scratch-path.txt"
        scratch_file.write_text(self.scratch + "\n", encoding="utf-8")
        code, out, _ = run_cli("preflight", "--scratch-file", str(scratch_file))
        self.assertEqual((code, out.strip()), (0, "scratch-ok"))
        os.symlink("/etc", os.path.join(self.scratch, "link"))
        code, out, err = run_cli("preflight", "--scratch-file", str(scratch_file))
        self.assertEqual((code, out.strip()), (1, "refused: external-symlink 1"))
        self.assertNotIn(self.scratch, out + err)


class ContainmentTest(ScratchCase):
    def test_contained_when_only_path_is_the_scratch_directory(self) -> None:
        self.assertEqual(review.containment(self.stream(use("Glob", pattern="*.c", path=self.scratch)),
                                            self.scratch), (True, "contained"))
        self.assertEqual(review.containment(self.stream(use("Read", file_path=self.scratch)),
                                            self.scratch), (True, "contained"))

    def test_relative_inside_all_in_scratch_review_is_contained(self) -> None:
        accesses = (use("Read", file_path="src/a.c"), use("Grep", pattern="x", path="."),
                    use("Glob", pattern="**/*.c"), use("Glob", pattern="src/*.py"),
                    use("Glob", path="src", pattern="*.c"), use("Grep", pattern="x", path="src", glob="*.py"),
                    use("Glob", pattern=self.scratch + "/*.c"))
        self.assertEqual(review.containment(self.stream(*accesses), self.scratch), (True, "contained"))

    def test_init_count(self) -> None:
        for events in ([result_event()], [init_event(self.scratch), init_event(self.scratch), result_event()]):
            self.assertEqual(review.containment(events, self.scratch), (False, "init-count"))

    def test_init_tools(self) -> None:
        events = [init_event(self.scratch, tools=("Read", "Bash")), result_event()]
        self.assertEqual(review.containment(events, self.scratch), (False, "init-tools"))

    def test_init_cwd(self) -> None:
        events = [init_event(self.scratch, cwd=self.base), result_event()]
        self.assertEqual(review.containment(events, self.scratch), (False, "init-cwd"))
        events = [init_event(self.scratch, cwd=""), result_event()]
        self.assertEqual(review.containment(events, self.scratch), (False, "init-cwd"))

    def test_tool_name(self) -> None:
        self.assertEqual(review.containment(self.stream(use("Write", file_path=self.scratch + "/x")),
                                            self.scratch), (False, "tool-name"))

    def test_path_outside(self) -> None:
        outside = (use("Read", file_path=self.base + "/x"),
                   use("Read", file_path=self.scratch + "-evil/x"),
                   use("Grep", pattern="x", path=self.base),
                   use("Glob", pattern=self.base + "/*.c"),
                   use("Grep", pattern="x", glob=self.scratch + "*/x"),
                   use("Glob", pattern=self.scratch + "*/x"),
                   use("Read", file_path=self.scratch + "/src/../a.c"),
                   use("Read", file_path=7))
        for access in outside:
            with self.subTest(access=access["message"]["content"][0]["name"]):
                self.assertEqual(review.containment(self.stream(access), self.scratch), (False, "path-outside"))

    def test_glob_path_combination(self) -> None:
        combinations = (
            use("Glob", pattern="../*.c"),
            use("Glob", path=".", pattern="../*.c"),
            use("Glob", path="..", pattern="*.c"),
            use("Glob", path="src/..", pattern="*.c"),
            use("Grep", pattern="x", path=".", glob="../*.c"),
        )
        for access in combinations:
            with self.subTest(access=json.dumps(access["message"]["content"][0]["input"])):
                self.assertEqual(review.containment(self.stream(access), self.scratch), (False, "path-outside"))

    def test_permission_denials(self) -> None:
        events = [init_event(self.scratch), result_event(({"tool_name": "Bash"},))]
        self.assertEqual(review.containment(events, self.scratch), (False, "permission-denials"))

    def test_no_result(self) -> None:
        self.assertEqual(review.containment([init_event(self.scratch)], self.scratch), (False, "no-result"))


IDS = ["T-04-11", "T-04-SC (04-23)", "T-04-44", "CR-01", "WR-08"]


class VerdictTest(unittest.TestCase):
    def lines(self, *lines: str) -> str:
        return "\n".join(("Reviewed revision: " + REVISION, *lines)) + "\n"

    def parse(self, text: str, contained: bool = True) -> dict[str, str]:
        return review.parse_verdicts(text, IDS, contained)

    def test_clean_verdicts_parse(self) -> None:
        text = self.lines("VERDICT T-04-11 CLOSED src/a.c:1 refuted", "VERDICT T-04-SC (04-23) CLOSED none",
                          "VERDICT T-04-44 OPEN cannot refute", "VERDICT CR-01 FIXED a.c:2 fixed",
                          "VERDICT WR-08 OPEN still present")
        self.assertEqual(self.parse(text), {"T-04-11": "CLOSED", "T-04-SC (04-23)": "CLOSED",
                                            "T-04-44": "OPEN", "CR-01": "FIXED", "WR-08": "OPEN"})

    def test_zero_duplicate_or_malformed_verdicts_are_open(self) -> None:
        text = self.lines("VERDICT T-04-11 CLOSED a:1 ok", "VERDICT T-04-11 CLOSED a:1 again",
                          "VERDICT T-04-44 MAYBE a:1 unsure", "VERDICT CR-01 FIXED a:1 ok",
                          "VERDICT CR-01 FIXED", "verdict WR-08 FIXED a:1 lower case")
        verdicts = self.parse(text)
        self.assertEqual(verdicts["T-04-11"], "OPEN")
        self.assertEqual(verdicts["T-04-44"], "OPEN")
        self.assertEqual(verdicts["CR-01"], "OPEN")
        self.assertEqual(verdicts["WR-08"], "OPEN")
        self.assertEqual(verdicts["T-04-SC (04-23)"], "OPEN")

    def test_wrong_vocabulary_is_open(self) -> None:
        text = self.lines("VERDICT T-04-11 FIXED a:1 wrong word", "VERDICT CR-01 CLOSED a:1 wrong word")
        verdicts = self.parse(text)
        self.assertEqual((verdicts["T-04-11"], verdicts["CR-01"]), ("OPEN", "OPEN"))

    def test_empty_evidence_is_open(self) -> None:
        self.assertEqual(self.parse(self.lines("VERDICT T-04-11 CLOSED   "))["T-04-11"], "OPEN")
        self.assertEqual(self.parse(self.lines("VERDICT T-04-11 CLOSED"))["T-04-11"], "OPEN")

    def test_halt_or_not_contained_gives_all_open(self) -> None:
        good = ("VERDICT T-04-11 CLOSED a:1 ok", "VERDICT CR-01 FIXED a:1 ok")
        self.assertEqual(set(self.parse(self.lines(*good), contained=False).values()), {"OPEN"})
        halted = self.lines(*good, "REVIEW HALTED: containment-violation")
        self.assertEqual(set(self.parse(halted).values()), {"OPEN"})


class ReviewIdsTest(unittest.TestCase):
    def test_single_line_parses(self) -> None:
        self.assertEqual(review.review_ids("intro\nReview IDs: T-04-11, T-04-SC (04-23), CR-01\n"),
                         ["T-04-11", "T-04-SC (04-23)", "CR-01"])

    def test_missing_repeated_or_duplicate_is_error(self) -> None:
        for text in ("no ids here", "Review IDs: A-1\nReview IDs: A-2", "Review IDs: CR-01, CR-01", "Review IDs: "):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    review.review_ids(text)


def security_row(identifier: str, disposition: str, status: str) -> str:
    return f"| {identifier} | Cat | Comp | high | {disposition} | mitigation | {status} |"


class PhaseFixture(ScratchCase):
    """A synthetic phase directory with the three transcription targets."""

    THREATS = {"T-04-11": ("mitigate", "open"), "T-04-44": ("accept", "accepted"),
               "T-04-52": ("accept", "open")}
    FINDINGS = {"CR-01": "open", "WR-08": "open"}

    def write_phase(self, threats=None, findings=None, crosswalk=None) -> str:
        phase = Path(self.base) / "04-demo"
        phase.mkdir(exist_ok=True)
        threats = self.THREATS if threats is None else threats
        findings = self.FINDINGS if findings is None else findings
        crosswalk = findings if crosswalk is None else crosswalk
        header = "| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |"
        security = [header, "|---|---|---|---|---|---|---|"]
        security += [security_row(i, d, s) for i, (d, s) in threats.items()]
        (phase / "04-SECURITY.md").write_text("\n".join(security) + "\n", encoding="utf-8")
        disposition = ["| Finding | Severity | Disposition | Source |", "|---|---|---|---|"]
        disposition += [f"| {i} | high | {s} | src |" for i, s in findings.items()]
        (phase / "04-REVIEW-DISPOSITION.md").write_text("\n".join(disposition) + "\n", encoding="utf-8")
        validation = ["| Review Finding | Severity | Existing Threat Scope | Disposition |", "|---|---|---|---|"]
        validation += [f"| {i} | high | scope | {s} |" for i, s in crosswalk.items()]
        (phase / "04-VALIDATION.md").write_text("\n".join(validation) + "\n", encoding="utf-8")
        return str(phase)

    def errors(self, phase: str, verdicts: dict[str, str], ids=None, **options) -> list[str]:
        ids = ids or ["T-04-11", "T-04-44", "T-04-52", "CR-01", "WR-08"]
        return review.transcription_errors(phase, ids, verdicts, options.get("deferred", ()),
                                           options.get("accepted", ()))


class TranscriptionTest(PhaseFixture):
    ALL_OPEN = {"T-04-11": "OPEN", "T-04-44": "OPEN", "T-04-52": "OPEN", "CR-01": "OPEN", "WR-08": "OPEN"}

    def test_matching_rows_have_no_errors(self) -> None:
        verdicts = {"T-04-11": "CLOSED", "T-04-44": "CLOSED", "T-04-52": "OPEN", "CR-01": "FIXED",
                    "WR-08": "FIXED"}
        phase = self.write_phase(
            threats={"T-04-11": ("mitigate", "closed"), "T-04-44": ("accept", "accepted"),
                     "T-04-52": ("accept", "open")},
            findings={"CR-01": "fixed", "WR-08": "deferred"})
        self.assertEqual(self.errors(phase, verdicts, deferred=("WR-08",)), [])

    def test_threat_status_mismatch_names_the_id(self) -> None:
        phase = self.write_phase(threats={"T-04-11": ("mitigate", "closed"), "T-04-44": ("accept", "open"),
                                          "T-04-52": ("accept", "open")})
        errors = self.errors(phase, self.ALL_OPEN)
        self.assertTrue(any("T-04-11" in e for e in errors))
        self.assertFalse(any("T-04-52" in e for e in errors))

    def test_closed_accept_row_maps_to_accepted_not_closed(self) -> None:
        phase = self.write_phase(threats={"T-04-11": ("mitigate", "open"), "T-04-44": ("accept", "closed"),
                                          "T-04-52": ("accept", "open")})
        verdicts = dict(self.ALL_OPEN, **{"T-04-44": "CLOSED"})
        errors = self.errors(phase, verdicts)
        self.assertTrue(any("T-04-44" in e for e in errors))

    def test_finding_mismatch_in_either_table_names_the_id(self) -> None:
        phase = self.write_phase(findings={"CR-01": "open", "WR-08": "open"},
                                 crosswalk={"CR-01": "fixed", "WR-08": "open"})
        errors = self.errors(phase, self.ALL_OPEN)
        self.assertTrue(any("CR-01" in e for e in errors))
        verdicts = dict(self.ALL_OPEN, **{"CR-01": "FIXED"})
        phase = self.write_phase(findings={"CR-01": "open", "WR-08": "open"},
                                 crosswalk={"CR-01": "fixed", "WR-08": "open"})
        self.assertTrue(any("CR-01" in e for e in self.errors(phase, verdicts)))

    def test_fixed_means_deferred_only_for_listed_ids(self) -> None:
        verdicts = dict(self.ALL_OPEN, **{"WR-08": "FIXED", "CR-01": "FIXED"})
        open_threats = {"T-04-11": ("mitigate", "open"), "T-04-44": ("accept", "open"),
                        "T-04-52": ("accept", "open")}
        phase = self.write_phase(threats=open_threats, findings={"CR-01": "fixed", "WR-08": "deferred"})
        self.assertEqual(self.errors(phase, verdicts, deferred=("WR-08",)), [])
        phase = self.write_phase(threats=open_threats, findings={"CR-01": "fixed", "WR-08": "fixed"})
        self.assertTrue(any("WR-08" in e for e in self.errors(phase, verdicts, deferred=("WR-08",))))

    def test_missing_or_duplicated_row_is_an_error(self) -> None:
        phase = self.write_phase(threats={"T-04-11": ("mitigate", "open"), "T-04-44": ("accept", "accepted")})
        self.assertTrue(any("T-04-52" in e for e in self.errors(phase, self.ALL_OPEN)))
        security = Path(phase) / "04-SECURITY.md"
        security.write_text(security.read_text(encoding="utf-8") + security_row("T-04-11", "mitigate", "open")
                            + "\n", encoding="utf-8")
        self.assertTrue(any("T-04-11" in e for e in self.errors(phase, self.ALL_OPEN)))

    def test_maintainer_accepted_expects_accepted_whatever_the_verdict(self) -> None:
        accepted_rows = {"T-04-11": ("mitigate", "open"), "T-04-44": ("accept", "accepted"),
                         "T-04-52": ("accept", "accepted")}
        phase = self.write_phase(threats=accepted_rows)
        for verdict in ("CLOSED", "OPEN"):
            with self.subTest(verdict=verdict):
                verdicts = dict(self.ALL_OPEN, **{"T-04-52": verdict})
                self.assertEqual(self.errors(phase, verdicts, accepted=("T-04-44", "T-04-52")), [])
        # Without the maintainer acceptance an OPEN verdict maps to open and the row disagrees.
        self.assertTrue(any("T-04-52" in e for e in self.errors(phase, self.ALL_OPEN)))

    def test_maintainer_accepted_rejects_open_closed_or_wrong_disposition(self) -> None:
        for status, disposition in (("open", "accept"), ("closed", "accept"), ("accepted", "mitigate")):
            with self.subTest(status=status, disposition=disposition):
                phase = self.write_phase(threats={"T-04-11": ("mitigate", "open"), "T-04-44": ("accept", "accepted"),
                                                  "T-04-52": (disposition, status)})
                errors = self.errors(phase, self.ALL_OPEN, accepted=("T-04-44", "T-04-52"))
                self.assertTrue(any("T-04-52" in e for e in errors), errors)

    def test_maintainer_accepted_finding_is_a_usage_error(self) -> None:
        phase = self.write_phase()
        with self.assertRaises(ValueError):
            self.errors(phase, self.ALL_OPEN, accepted=("CR-01",))


def run_cli(*arguments: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = review.main(list(arguments))
    return code, out.getvalue(), err.getvalue()


class CliTest(PhaseFixture):
    def files(self, events, review_lines, ids=("T-04-11", "T-04-44", "T-04-52", "CR-01", "WR-08")) -> dict[str, str]:
        base = Path(self.base)
        (base / "scratch-path.txt").write_text(self.scratch + "\n", encoding="utf-8")
        (base / "stream.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        (base / "review.md").write_text("\n".join(review_lines) + "\n", encoding="utf-8")
        (base / "prompt.md").write_text("Reviewed revision: x\nReview IDs: " + ", ".join(ids) + "\n",
                                        encoding="utf-8")
        return {"--scratch-file": str(base / "scratch-path.txt"), "--stream": str(base / "stream.jsonl"),
                "--review": str(base / "review.md"), "--prompt": str(base / "prompt.md")}

    @staticmethod
    def argv(command: str, files: dict[str, str], *extra: str) -> list[str]:
        out = [command]
        for key, value in files.items():
            out += [key, value]
        return out + list(extra)

    def test_gate_reports_contained_and_not_contained(self) -> None:
        files = self.files(self.stream(use("Read", file_path=self.scratch)), ["x"])
        code, out, _ = run_cli("gate", "--stream", files["--stream"], "--scratch-file", files["--scratch-file"])
        self.assertEqual((code, out.strip()), (0, "contained"))
        files = self.files(self.stream(use("Bash", command="ls")), ["x"])
        code, out, _ = run_cli("gate", "--stream", files["--stream"], "--scratch-file", files["--scratch-file"])
        self.assertEqual((code, out.strip()), (1, "not-contained: tool-name"))

    def test_verdicts_prints_json(self) -> None:
        files = self.files(self.stream(use("Read", file_path="src/a.c")),
                           ["Reviewed revision: " + REVISION, "VERDICT T-04-11 CLOSED a:1 ok"])
        code, out, _ = run_cli(*self.argv("verdicts", files))
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["contained"])
        self.assertIsNone(payload["halted"])
        self.assertEqual(payload["verdicts"]["T-04-11"], "CLOSED")
        self.assertEqual(payload["verdicts"]["CR-01"], "OPEN")

    def check_args(self, files, phase, *extra) -> list[str]:
        return self.argv("check", files, "--revision", REVISION, "--phase-dir", phase, *extra)

    def test_check_contained_transcription(self) -> None:
        verdicts = ["VERDICT T-04-11 CLOSED a:1 ok", "VERDICT T-04-44 CLOSED a:1 ok",
                    "VERDICT T-04-52 OPEN a:1 no", "VERDICT CR-01 FIXED a:1 ok", "VERDICT WR-08 FIXED a:1 ok"]
        files = self.files(self.stream(use("Read", file_path="src/a.c")),
                           ["Reviewed revision: " + REVISION, *verdicts])
        phase = self.write_phase(
            threats={"T-04-11": ("mitigate", "closed"), "T-04-44": ("accept", "accepted"),
                     "T-04-52": ("accept", "accepted")},
            findings={"CR-01": "fixed", "WR-08": "deferred"})
        code, out, err = run_cli(*self.check_args(files, phase, "--fixed-means-deferred", "WR-08",
                                                  "--maintainer-accepted", "T-04-52"))
        self.assertEqual((code, out.strip(), err), (0, "transcribed 5 ids (contained)", ""))

    def test_check_halted_records_all_open(self) -> None:
        files = self.files(self.stream(use("Write", file_path=self.scratch + "/x")),
                           ["Reviewed revision: " + REVISION, "REVIEW HALTED: containment-violation"])
        phase = self.write_phase(threats={"T-04-11": ("mitigate", "open"), "T-04-44": ("accept", "open"),
                                          "T-04-52": ("accept", "open")})
        code, out, err = run_cli(*self.check_args(files, phase))
        self.assertEqual((code, out.strip()), (0, "transcribed 5 ids (halted containment-violation)"), err)

    def test_check_failures(self) -> None:
        phase = self.write_phase()
        cases = {
            "unpinned": (self.stream(use("Read", file_path="src/a.c")), ["Reviewed revision: other"]),
            "non-contained without halt line": (self.stream(use("Write", file_path="x")),
                                                ["Reviewed revision: " + REVISION]),
            "wrong halt reason": (self.stream(use("Write", file_path="x")),
                                  ["Reviewed revision: " + REVISION, "REVIEW HALTED: sandbox-network-unapproved"]),
            "halt line plus verdict": (self.stream(use("Read", file_path="src/a.c")),
                                       ["Reviewed revision: " + REVISION, "REVIEW HALTED: x",
                                        "VERDICT CR-01 FIXED a:1 ok"]),
            "two halt lines": (self.stream(use("Read", file_path="src/a.c")),
                               ["Reviewed revision: " + REVISION, "REVIEW HALTED: a", "REVIEW HALTED: b"]),
        }
        for label, (events, lines) in cases.items():
            with self.subTest(case=label):
                files = self.files(events, lines)
                code, out, err = run_cli(*self.check_args(files, phase))
                self.assertEqual(code, 1, (out, err))
                self.assertIn("FAIL:", out)

    def test_check_transcription_mismatch_fails(self) -> None:
        files = self.files(self.stream(use("Read", file_path="src/a.c")),
                           ["Reviewed revision: " + REVISION, "VERDICT T-04-11 CLOSED a:1 ok"])
        code, out, _ = run_cli(*self.check_args(files, self.write_phase()))
        self.assertEqual(code, 1)
        self.assertIn("T-04-11", out)

    def test_maintainer_accepted_finding_exits_2(self) -> None:
        files = self.files(self.stream(use("Read", file_path="src/a.c")), ["Reviewed revision: " + REVISION])
        code, _, _ = run_cli(*self.check_args(files, self.write_phase(), "--maintainer-accepted", "CR-01"))
        self.assertEqual(code, 2)

    def test_unreadable_or_malformed_input_exits_2(self) -> None:
        files = self.files(self.stream(), ["Reviewed revision: " + REVISION])
        Path(files["--stream"]).write_text("{not json\n", encoding="utf-8")
        code, _, _ = run_cli(*self.argv("verdicts", files))
        self.assertEqual(code, 2)
        files = self.files(self.stream(), ["Reviewed revision: " + REVISION])
        os.unlink(files["--review"])
        code, _, _ = run_cli(*self.argv("verdicts", files))
        self.assertEqual(code, 2)

    def test_output_never_prints_input_paths(self) -> None:
        files = self.files(self.stream(use("Read", file_path=self.base + "/outside")),
                           ["Reviewed revision: " + REVISION, "REVIEW HALTED: containment-violation"])
        for command in (self.argv("verdicts", files), self.check_args(files, self.write_phase())):
            code, out, err = run_cli(*command)
            self.assertNotIn(self.base, out + err)
            self.assertNotIn(os.path.basename(self.base), out + err)

    def test_private_path_in_message_becomes_private_path_survived(self) -> None:
        line = review.safe_line("FAIL: " + str(Path.home()) + "/secret/file")
        self.assertEqual(line, "private-path-survived")
        self.assertEqual(review.safe_line("FAIL: T-04-11 status mismatch"), "FAIL: T-04-11 status mismatch")


if __name__ == "__main__":
    unittest.main()
