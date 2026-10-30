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


MERIT_WORDS = ("claim", "founded", "overbilled", "recoverable", "shortfall")


def assert_no_merit(tc, text):
    low = text.lower()
    for w in MERIT_WORDS:
        tc.assertNotIn(w, low, f"merit word {w!r} in: {text[:160]}")


class TestRouting(unittest.TestCase):
    def _run(self, cid, lines, date="2026-08-15", docs=()):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(mkcase(cid, lines, date))
        for role, name, text in docs:
            s.add_document(cid, role, name, 1, text)
        ag = Agent(s, SimulatedProvider())
        return s, ag.investigate(cid), ag.propose(cid)

    def test_literal_reason_routes_to_team(self):
        # Owner-confirmed: "supera el valor del convenio" -> Agreements.
        s, inv, prop = self._run(
            "T1", [(1, "CONSULTA GENERAL", "supera el valor del convenio",
                    2000000, 350000)])
        self.assertEqual((prop.team, prop.action), ("Agreements", "route_team"))
        self.assertFalse(prop.needs_human)
        line = inv["lines"][0]
        self.assertEqual(line["diff_billed_ref_cents"], 350000)
        self.assertEqual(line["diff_ref_settled_cents"], 1300000)
        self.assertEqual(inv["total_ref_cents"], 1650000)
        assert_no_merit(self, prop.explanation)
        for h in inv["findings"]:
            assert_no_merit(self, h.interpretation + " " + h.limitations)

    def test_medication_reason_routes_to_medical_audit(self):
        # Owner-confirmed literal: AI classifies/routes only; Medical
        # Audit evaluates. No judgment on medication pertinence.
        reason = "La medicación utilizada no corresponde al cuadro del paciente"
        s, inv, prop = self._run(
            "T2", [(1, "CONSULTA GENERAL", reason, 2000000, 350000)])
        self.assertEqual((prop.team, prop.action),
                         ("Medical Audit", "route_human"))
        self.assertTrue(prop.needs_human)
        texts = " ".join(h.interpretation + " " + h.limitations
                         for h in inv["findings"])
        self.assertIn("No economic recommendation", texts)
        assert_no_merit(self, prop.explanation)

    def test_missing_date_flags_pending_check(self):
        s, inv, prop = self._run(
            "T3", [(1, "CONSULTA GENERAL", "supera el valor del convenio",
                    2000000, 350000)], date="")
        self.assertEqual(prop.action, "request_extension")
        self.assertEqual(inv["findings"][0].kind, "insufficient_evidence")
        self.assertIn("pending", inv["findings"][0].interpretation.lower())
        assert_no_merit(self, prop.explanation)

    def test_contradictory_documents_route_for_review(self):
        docs = [("settlement", "s.pdf",
                 "RENGLON 1: DEBITO $10.000 MOTIVO: supera el valor del convenio")]
        s, inv, prop = self._run(
            "T4", [(1, "CONSULTA GENERAL", "supera el valor del convenio",
                    2000000, 500000)], docs=docs)
        kinds = {h.kind for h in inv["findings"]}
        self.assertIn("inconsistency", kinds)
        self.assertEqual(prop.action, "request_extension")

    def test_exp900_amounts_are_facts(self):
        lines = [(1, "CONSULTA GENERAL", "supera el valor del convenio",
                  2000000, 350000),
                 (2, "ECOGRAFIA ABDOMINAL",
                  "difiere del valor pactado en convenio", 4500000, 300000)]
        s, inv, prop = self._run("T5", lines)
        self.assertEqual((prop.team, prop.action), ("Agreements", "route_team"))
        self.assertEqual(inv["total_ref_cents"], 5850000)
        l1, l2 = inv["lines"]
        self.assertEqual((l1["diff_billed_ref_cents"], l1["diff_ref_settled_cents"]),
                         (350000, 1300000))
        self.assertEqual((l2["diff_billed_ref_cents"], l2["diff_ref_settled_cents"]),
                         (300000, 3900000))
        assert_no_merit(self, prop.explanation)
        for h in inv["findings"]:
            assert_no_merit(self, h.interpretation + " " + h.limitations)


if __name__ == "__main__":
    unittest.main()
