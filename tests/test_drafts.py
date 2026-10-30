import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai import drafts
from debit_ai.contracts import Case, LineItem


def case():
    return Case("D1", "OS FICTICIA ANDINA", "F-1", (LineItem(
        1, "CONSULTA GENERAL", "supera el valor del convenio",
        2000000, 350000),), 1650000)


class TestDrafts(unittest.TestCase):
    def test_referral_for_route_team(self):
        d = drafts.build_draft(case(), "Agreements", "route_team", "basis")
        self.assertIn("Referral", d["title"])
        self.assertIn("Routed team: Agreements", d["body"])
        self.assertIn("requires approval", d["body"])
        self.assertNotIn("claim", d["title"].lower() + d["body"].lower())

    def test_clinical_routing_has_no_economics(self):
        d = drafts.build_draft(case(), "Medical Audit", "route_human", "basis")
        self.assertIn("Clinical routing", d["title"])
        self.assertIn("no economic recommendation", d["body"].lower())

    def test_info_request_lists_missing(self):
        d = drafts.build_draft(case(), "Agreements", "request_extension",
                               "basis", ("L1: no service date",))
        self.assertIn("Information request", d["title"])
        self.assertIn("L1: no service date", d["body"])
        self.assertIn("nothing is concluded", d["body"].lower())

    def test_legacy_actions_map(self):
        for legacy in ("claim", "no_claim"):
            d = drafts.build_draft(case(), "Agreements", legacy, "basis")
            self.assertIn("Referral", d["title"])

    def test_unknown_action_raises(self):
        with self.assertRaises(ValueError):
            drafts.build_draft(case(), "Agreements", "fly", "basis")


if __name__ == "__main__":
    unittest.main()
