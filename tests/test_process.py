import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai import approvals, process
from debit_ai.agent import Agent
from debit_ai.contracts import Case, LineItem
from debit_ai.provider import SimulatedProvider
from debit_ai.synthetic import SyntheticStore, seed_agreements


def case(cid="P1", reason="supera el valor del convenio", billed=2000000, settled=500000):
    return Case(cid, "OS FICTICIA ANDINA", "F-1", (LineItem(
        1, "CONSULTA GENERAL", reason, billed, settled),), billed - settled, "new", "2026-08-15")


class TestProcess(unittest.TestCase):
    def test_priority(self):
        self.assertEqual(process.priority(100000001), "P1")
        self.assertEqual(process.priority(100000000), "P2")
        self.assertEqual(process.priority(50000000), "P2")
        self.assertEqual(process.priority(49999999), "P3")

    def test_sla_skips_weekend(self):
        self.assertEqual(process.add_business_days("2026-10-30", 1), "2026-11-02")
        self.assertEqual(process.add_business_days("2026-10-28", 5), "2026-11-04")

    def test_checklist(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case(reason="coseguro no descontado al facturar"))
        ag = Agent(s, SimulatedProvider())
        chk = {i["item"]: i for i in process.checklist(s.get_case("P1"), ag.investigate("P1"))}
        self.assertEqual(chk["Sums"]["state"], "ok")
        self.assertEqual(chk["Copays"]["value"], "identified")

    def _approved(self, cid="P1"):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case(cid))
        prop = Agent(s, SimulatedProvider()).propose(cid)
        approvals.review(s, prop.id, "auto-test", "approved", "ok")
        return s, prop

    def test_followup_ok_and_errors(self):
        s, prop = self._approved()
        d = approvals.followup(s, prop.id, "partial", 1000000, 500000,
                               "R. Agreements", "2026-10-28", "ok")
        self.assertEqual(d["decision"], "partial")
        self.assertTrue(any(h[1] == "followup" for h in s.history("P1")))
        with self.assertRaises(ValueError):
            approvals.followup(s, prop.id, "other", 0, 0, "R", "2026-10-28")
        with self.assertRaises(ValueError):
            approvals.followup(s, prop.id, "partial", -1, 0, "R", "2026-10-28")
        with self.assertRaises(ValueError):
            approvals.followup(s, prop.id, "partial", True, 0, "R", "2026-10-28")
        with self.assertRaises(ValueError):
            approvals.followup(s, prop.id, "partial", 0, 0, "  ", "2026-10-28")
        with self.assertRaises(KeyError):
            approvals.followup(s, "P-X-99", "partial", 0, 0, "R", "2026-10-28")

    def test_followup_needs_approved_review(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case())
        prop = Agent(s, SimulatedProvider()).propose("P1")
        with self.assertRaisesRegex(ValueError, "approved review"):
            approvals.followup(s, prop.id, "pending", 0, 0, "R", "2026-10-28")
        approvals.review(s, prop.id, "auto-test", "rejected", "no")
        with self.assertRaisesRegex(ValueError, "approved review"):
            approvals.followup(s, prop.id, "pending", 0, 0, "R", "2026-10-28")
        approvals.review(s, prop.id, "auto-test", "approved", "yes")
        d = approvals.followup(s, prop.id, "pending", 0, 0, "R", "2026-10-28")
        self.assertEqual(d["decision"], "pending")

    def test_followup_amount_scope(self):
        # Case debit is 1500000 cents.
        s, prop = self._approved()
        with self.assertRaisesRegex(ValueError, "exceed case debit"):
            approvals.followup(s, prop.id, "partial", 1000000, 600000,
                               "R", "2026-10-28")
        with self.assertRaisesRegex(ValueError, "pending.*zero"):
            approvals.followup(s, prop.id, "pending", 1, 0, "R", "2026-10-28")
        with self.assertRaisesRegex(ValueError, "recovered"):
            approvals.followup(s, prop.id, "recovered", 1000000, 500000,
                               "R", "2026-10-28")
        with self.assertRaisesRegex(ValueError, "accepted"):
            approvals.followup(s, prop.id, "accepted", 100, 500, "R", "2026-10-28")
        with self.assertRaisesRegex(ValueError, "partial"):
            approvals.followup(s, prop.id, "partial", 1000000, 0, "R", "2026-10-28")
        d = approvals.followup(s, prop.id, "recovered", 1500000, 0,
                               "R", "2026-10-28")
        self.assertEqual(d["recoverable_cents"], 1500000)

    def test_followup_correction_keeps_before_after(self):
        s, prop = self._approved()
        approvals.followup(s, prop.id, "partial", 1000000, 500000,
                           "R", "2026-10-28", "first")
        approvals.followup(s, prop.id, "recovered", 1500000, 0,
                           "R", "2026-10-29", "fixed")
        evs = [h for h in s.history("P1") if h[1] == "followup"]
        self.assertEqual(len(evs), 2)
        self.assertEqual(evs[0][3], "no reply")
        self.assertIn("partial: recoverable 1000000", evs[1][3])
        self.assertEqual(s.get_followup(prop.id)["decision"], "recovered")

    def test_manager_overlap_and_seed(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        conv, amb = s.current_agreement("OS FICTICIA ANDINA", "2026-06-15")
        self.assertEqual(conv["id"], "CONV-AND-2026")
        self.assertTrue(amb)
        conv, amb = s.current_agreement("OS FICTICIA ANDINA", "2027-01-01")
        self.assertIsNone(conv)
        n0 = len(s.payer_agreements("OS FICTICIA ANDINA"))
        seed_agreements(s)
        self.assertEqual(len(s.payer_agreements("OS FICTICIA ANDINA")), n0)


if __name__ == "__main__":
    unittest.main()
