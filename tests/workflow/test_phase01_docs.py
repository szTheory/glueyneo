"""Local controls for the Phase 01 admission and contributor navigation."""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
ADMISSION_GATE = "Phase 01 remains open / GAPS_FOUND and Phase 02 gated"
STATE_PATH = ".planning/STATE.md"


def markdown_link_targets(markdown):
    """Collect inline links and destinations referenced by Markdown labels."""
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)
    definitions = {}
    for label, angle_target, plain_target in re.findall(
                r"(?m)^[ \t]{0,3}\[([^\]]+)\]:\s*(?:<([^>\n]+)>|(\S+))", markdown):
        normalized = " ".join(label.split()).casefold()
        definitions.setdefault(normalized, angle_target or plain_target)

    reference_use = re.compile(r"(?<!!)\[([^\]]+)\](?:\[([^\]]*)\])?")
    for match in reference_use.finditer(markdown):
        if markdown[match.end():].startswith("("):
            continue  # already counted as an inline link
        if match.group(2) is None and markdown[match.end():].startswith(":"):
            continue  # link definition, not a rendered use
        label = match.group(2) or match.group(1)  # empty second label is collapsed form
        normalized = " ".join(label.split()).casefold()
        if normalized in definitions:
            links.append(definitions[normalized])
    return links


class WorkflowDocsControls(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.roadmap = (ROOT / ".planning/ROADMAP.md").read_text(encoding="utf-8")

    def check_navigation(self, readme, roadmap):
        self.assertTrue(ADMISSION_GATE in roadmap, "admission gate missing")
        links = markdown_link_targets(readme)
        self.assertIn(STATE_PATH, links, "canonical STATE link missing")
        self.assertNotRegex(readme, r"\$gsd-execute-phase\s+0?1\b",
                            "fixed Phase 01 execute route")
        local = 0
        for link in links:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc:
                continue
            local += 1
            target = ROOT / unquote(parsed.path)
            self.assertTrue(target.exists(), f"broken local link: {link}")
        return len(links), local

    def test_current_docs_navigation(self):
        links, local = self.check_navigation(self.readme, self.roadmap)
        print(f"README links: {links} Markdown, {local}/{local} local resolved")

    def test_removed_admission_gate_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "admission gate missing"):
            self.check_navigation(self.readme, self.roadmap.replace(ADMISSION_GATE, ""))

    def test_removed_state_link_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "canonical STATE link missing"):
            self.check_navigation(self.readme.replace(f"]({STATE_PATH})", "](README.md)"),
                                  self.roadmap)

    def test_broken_local_link_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "broken local link"):
            self.check_navigation(self.readme + "\n[broken](missing-phase01-doc.md)\n",
                                  self.roadmap)

    def test_reference_style_link_resolves(self):
        readme = (f"[canonical state][Phase State]\n"
                  f"[phase state]: {STATE_PATH}\n")
        links, local = self.check_navigation(readme, self.roadmap)
        self.assertEqual(1, local)
        self.assertEqual(1, links)

    def test_broken_reference_style_link_is_rejected(self):
        readme = (self.readme + "\n[broken][phase01-broken]\n"
                  "[phase01-broken]: missing-phase01-doc.md\n")
        with self.assertRaisesRegex(AssertionError, "broken local link"):
            self.check_navigation(readme, self.roadmap)

    def test_first_duplicate_reference_definition_is_used(self):
        readme = (self.readme + "\n[broken][phase01-duplicate]\n"
                  "[phase01-duplicate]: missing-phase01-doc.md\n"
                  "[PHASE01-DUPLICATE]: README.md\n")
        with self.assertRaisesRegex(AssertionError, "broken local link"):
            self.check_navigation(readme, self.roadmap)

    def test_fixed_execute_route_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "fixed Phase 01 execute route"):
            self.check_navigation(self.readme + "\n$gsd-execute-phase 01\n", self.roadmap)


if __name__ == "__main__":
    unittest.main()
