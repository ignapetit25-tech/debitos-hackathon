import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai.agent import Agent
from debit_ai.contracts import Case, LineItem
from debit_ai.provider import SimulatedProvider
from debit_ai.synthetic import SyntheticStore


def mkcase(cid, lines, date="2026-08-15"):
    items = tuple(LineItem(n, p, r, b, s) for n, p, r, b, s in lines)
    total = sum(x.debit_cents for x in items)
    return Case(cid, "OS FICTICIA ANDINA", "F-1", items, total, "new", date)


class TestReconciliation(unittest.TestCase):
    def _run(self, cid, lines, date="2026-08-15", docs=()):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(mkcase(cid, lines, date))
        for role, name, text in docs:
            s.add_document(cid, role, name, 1, text)
        ag = Agent(s, SimulatedProvider())
        return s, ag.investigate(cid), ag.propose(cid)

    def test_paid_per_agreement_is_no_claim(self):
        # Audit repro: billed 20000, ref 16500, settled 16500.
        s, inv, prop = self._run(
            "R1", [(1, "CONSULTA GENERAL", "supera el valor del convenio",
                    2000000, 1650000)])
        self.assertEqual((prop.team, prop.action), ("Agreements", "no_claim"))
        self.assertTrue(prop.needs_human)
        self.assertEqual(inv["lines"][0]["payment_gap_cents"], 0)
        self.assertEqual(inv["lines"][0]["overbilled_cents"], 350000)
        self.assertEqual(inv["findings"][0].kind, "no_shortfall")
        self.assertIn("No payment shortfall", prop.explanation)

    def test_exact_payment_is_no_claim(self):
        s, inv, prop = self._run(
            "R2", [(1, "CONSULTA GENERAL", "supera el valor del convenio",
                    1650000, 1650000)])
        self.assertEqual(prop.action, "no_claim")
        self.assertEqual(inv["total_gap_cents"], 0)
        self.assertEqual(inv["total_overbilled_cents"], 0)

    def test_underpayment_claims_founded_gap(self):
        s, inv, prop = self._run(
            "R3", [(1, "CONSULTA GENERAL", "supera el valor del convenio",
                    2000000, 350000)])
        self.assertEqual(prop.action, "claim")
        self.assertEqual(inv["total_gap_cents"], 1300000)
        self.assertEqual(inv["total_overbilled_cents"], 350000)
        self.assertIn("$13.000,00 of $16.500,00 debit", prop.explanation)

    def test_exp900_amounts(self):
        lines = [(1, "CONSULTA GENERAL", "supera el valor del convenio",
                  2000000, 350000),
                 (2, "ECOGRAFIA ABDOMINAL",
                  "difiere del valor pactado en convenio", 4500000, 300000)]
        s, inv, prop = self._run("R4", lines)
        self.assertEqual(prop.action, "claim")
        # Founded 52000 of 58500 debit; overbilled 6500 is not claimable.
        self.assertEqual(inv["total_gap_cents"], 5200000)
        self.assertEqual(inv["total_overbilled_cents"], 650000)
        self.assertIn("$52.000,00 of $58.500,00 debit", prop.explanation)

    def test_contradictory_documents_stop_claim(self):
        docs = [("settlement", "s.pdf",
                 "RENGLON 1: DEBITO $10.000 MOTIVO: supera el valor del convenio")]
        s, inv, prop = self._run(
            "R5", [(1, "CONSULTA GENERAL", "supera el valor del convenio",
                    2000000, 500000)], docs=docs)
        kinds = {h.kind for h in inv["findings"]}
        self.assertIn("inconsistency", kinds)
        self.assertEqual(prop.action, "request_extension")

    def test_mixed_lines_claim_only_gap(self):
        lines = [(1, "CONSULTA GENERAL", "supera el valor del convenio",
                  2000000, 350000),
                 (2, "CONSULTA GENERAL", "supera el valor del convenio",
                  2000000, 1650000)]
        s, inv, prop = self._run("R6", lines)
        self.assertEqual(prop.action, "claim")
        self.assertEqual(inv["total_gap_cents"], 1300000)
        kinds = {h.kind for h in inv["findings"]}
        self.assertEqual(kinds, {"backed_difference", "no_shortfall"})


if __name__ == "__main__":
    unittest.main()
