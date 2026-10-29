import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai import approvals
from debit_ai.contracts import Case, Proposal, RuleRef, LineItem
from debit_ai.synthetic import SyntheticStore


def _store():
    s = SyntheticStore(tempfile.mktemp(suffix=".db"))
    s.seed_case(Case("C1", "F", "F-1", (LineItem(1, "P", "M", 200, 100),), 100))
    s.save_proposal("C1", Proposal("P1", "C1", "Agreements",
        RuleRef("Agreements", 4, ("x",)), "claim", "e", ("r",)))
    return s


class TestApprovals(unittest.TestCase):
    def test_approve_and_reject(self):
        for v in ("approved", "rejected"):
            s = _store()
            d = approvals.review(s, "P1", "Human", v, "ok")
            self.assertEqual(d.verdict, v)
            hist = s.history("C1")
            self.assertTrue(any(h[1] == "review" for h in hist))
            rev = [h for h in hist if h[1] == "review"][0]
            self.assertNotEqual(rev[3], rev[4])  # before != after

    def test_requires_reviewer_and_verdict(self):
        with self.assertRaises(ValueError):
            approvals.review(_store(), "P1", "  ", "approved")
        with self.assertRaises(ValueError):
            approvals.review(_store(), "P1", "H", "maybe")
        with self.assertRaises(KeyError):
            approvals.review(_store(), "PX", "H", "approved")


if __name__ == "__main__":
    unittest.main()
