"""Local controls for the Phase 01 admission and contributor navigation."""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
ADMISSION_GATE = "Phase 01 remains open / GAPS_FOUND and Phase 02 gated"
STATE_PATH = ".planning/STATE.md"


class WorkflowDocsControls(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.roadmap = (ROOT / ".planning/ROADMAP.md").read_text(encoding="utf-8")

    def check_navigation(self, readme, roadmap):
        self.assertTrue(ADMISSION_GATE in roadmap, "admission gate missing")
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme)
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

    def test_fixed_execute_route_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "fixed Phase 01 execute route"):
            self.check_navigation(self.readme + "\n$gsd-execute-phase 01\n", self.roadmap)


if __name__ == "__main__":
    unittest.main()
