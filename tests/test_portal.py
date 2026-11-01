import unittest
from pathlib import Path

PORTAL = Path(__file__).resolve().parent.parent / "debit_ai" / "static" / "portal.html"


class TestPortal(unittest.TestCase):
    def test_markers_and_attribution(self):
        html = PORTAL.read_text(encoding="utf-8")
        for marker in ("Every debit, traced to its backing.",
                       'href="/"', "EXP-2501", "100% FICTITIOUS DATA",
                       "stunning-ia-lp", "Pedro Estev", "(MIT)",
                       "ignapetit25-tech/debitos-hackathon"):
            self.assertIn(marker, html)

    def test_no_external_assets(self):
        html = PORTAL.read_text(encoding="utf-8")
        self.assertNotIn("<script", html)
        self.assertNotIn("@import", html)
        for line in html.splitlines():
            for token in ("src=\"http", "href=\"http"):
                if token in line:
                    self.assertIn("github.com", line)


if __name__ == "__main__":
    unittest.main()
