import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai.agent import Agent
from debit_ai.contracts import Case, LineItem
from debit_ai.provider import Provider
from debit_ai.synthetic import SyntheticStore


def case(cid="G1"):
    return Case(cid, "OS FICTICIA ANDINA", "F-1", (LineItem(
        1, "CONSULTA GENERAL", "supera el valor del convenio",
        2000000, 500000),), 1500000, "new", "2026-08-15")


class FakeG(Provider):
    name = "fake"
    def __init__(self, halls):
        self._h = halls
        self.last_call = {"provider": "fake", "status": "ok"}
    def complete_structured(self, *a, **k):
        return {"findings": self._h}


DOC = "VIGENCIA: 2026-01-01..2026-12-31 ARANCEL: CONSULTA GENERAL $16.500"
QUOTE = "ARANCEL: CONSULTA GENERAL $16.500"


def finding(**kw):
    d = {"line_no": 1, "kind": "backed_difference", "document": "agreement",
         "page": 1, "excerpt": QUOTE,
         "interpretation": "Applies.", "limitations": ""}
    d.update(kw)
    return d


class TestGate(unittest.TestCase):
    def _run(self, halls, with_doc=True):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case())
        if with_doc:
            s.add_document("G1", "agreement", "c.pdf", 1, DOC)
        prop = Agent(s, FakeG(halls)).propose("G1")
        return s, prop

    def _gates(self, s):
        return [h for h in s.history("G1") if h[1] == "gate"]

    def test_verified_backed_keeps_claim(self):
        s, prop = self._run([finding()])
        self.assertEqual((prop.team, prop.action), ("Agreements", "claim"))
        self.assertFalse(prop.needs_human)
        self.assertEqual(self._gates(s), [])
        self.assertIn("1 verified finding(s)", prop.explanation)
        self.assertNotIn("GATE:", prop.explanation)

    def test_verified_clinical_routes_human(self):
        s, prop = self._run([finding(kind="clinical_human")])
        self.assertEqual((prop.team, prop.action),
                         ("Medical Audit", "route_human"))
        self.assertTrue(prop.needs_human)
        g = self._gates(s)
        self.assertEqual(len(g), 1)
        self.assertEqual((g[0][3], g[0][4]),
                         ("Agreements/claim", "Medical Audit/route_human"))
        self.assertIn("GATE:", prop.explanation)

    def test_unverified_clinical_routes_human(self):
        # Safe direction: a clinical flag escalates even without
        # a valid citation; it is not used as economic evidence.
        s, prop = self._run([finding(kind="clinical_human")], with_doc=False)
        self.assertEqual((prop.team, prop.action),
                         ("Medical Audit", "route_human"))
        self.assertEqual(len(self._gates(s)), 1)

    def test_verified_inconsistency_stops_claim(self):
        s, prop = self._run([finding(kind="inconsistency")])
        self.assertEqual((prop.team, prop.action),
                         ("Agreements", "request_extension"))
        self.assertTrue(prop.needs_human)
        g = self._gates(s)
        self.assertEqual(len(g), 1)
        self.assertIn("contradiction", g[0][2])

    def test_unverified_inconsistency_keeps_claim(self):
        s, prop = self._run([finding(kind="inconsistency")], with_doc=False)
        self.assertEqual(prop.action, "claim")
        self.assertEqual(self._gates(s), [])
        self.assertIn("CITATION UNVERIFIED (not used as evidence)",
                      prop.explanation)

    def test_no_findings_no_gate(self):
        s, prop = self._run([])
        self.assertIn("DEGRADED", prop.explanation)
        self.assertEqual(self._gates(s), [])


if __name__ == "__main__":
    unittest.main()
