import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai import drafts, casefile
from debit_ai.agent import Agent
from debit_ai.contracts import Case, Finding, LineItem
from debit_ai.provider import Provider, SimulatedProvider
from debit_ai.synthetic import SyntheticStore


def case(date, reason, billed, settled, cid="E1"):
    return Case(cid, "OS FICTICIA ANDINA", "F-1", (LineItem(
        1, "CONSULTA GENERAL", reason, billed, settled),), billed - settled,
        "new", date)


class AlwaysFails(Provider):
    name = "fails"
    last_call = {}
    def complete_structured(self, *a, **k):
        raise AssertionError("reads must not call the model")


class TestCasefile(unittest.TestCase):
    def test_backed_routes_team(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        ag = Agent(s, SimulatedProvider())
        prop = ag.propose("E1")
        self.assertEqual((prop.team, prop.action), ("Agreements", "route_team"))
        inv = ag.investigate("E1")
        self.assertEqual(inv["findings"][0].kind, "backed_difference")
        self.assertTrue(inv["findings"][0].verified)
        self.assertEqual(inv["lines"][0]["ref_cents"], 1650000)
        # Signed arithmetic facts, no merit.
        self.assertEqual(inv["lines"][0]["diff_billed_ref_cents"], 350000)
        self.assertEqual(inv["lines"][0]["diff_ref_settled_cents"], 1150000)
        self.assertEqual(inv["total_ref_cents"], 1650000)

    def test_below_ref_routes_with_facts(self):
        # Billed below the agreed value is arithmetic, not suspicion.
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case("2026-08-15", "supera el valor del convenio", 1000000, 200000))
        ag = Agent(s, SimulatedProvider())
        prop = ag.propose("E1")
        self.assertEqual(prop.action, "route_team")
        inv = ag.investigate("E1")
        self.assertEqual(inv["findings"][0].kind, "backed_difference")
        self.assertEqual(inv["lines"][0]["diff_billed_ref_cents"], -650000)
        self.assertEqual(inv["lines"][0]["diff_ref_settled_cents"], 1450000)

    def test_no_date_backs_nothing(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case("", "supera el valor del convenio", 2000000, 500000))
        ag = Agent(s, SimulatedProvider())
        prop = ag.propose("E1")
        self.assertEqual(prop.team, "Agreements")  # team kept
        self.assertEqual(prop.action, "request_extension")  # but stays for review
        inv = ag.investigate("E1")
        self.assertEqual(inv["findings"][0].kind, "insufficient_evidence")

    def test_clinical_routes(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case("2026-08-15", "no se realizo la operacion segun parte quirurgico",
                         4200000, 0))
        ag = Agent(s, SimulatedProvider())
        prop = ag.propose("E1")
        self.assertEqual((prop.team, prop.action),
                         ("Medical Audit", "route_human"))

    def test_agreement_validity(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        s.add_document("E1", "agreement", "conv.pdf", 1,
                       "VIGENCIA: 2026-01-01..2026-06-30\n"
                       "ARANCEL: CONSULTA GENERAL $16.500")
        ag = Agent(s, SimulatedProvider())
        inv = ag.investigate("E1")  # service outside validity
        self.assertEqual(inv["findings"][0].kind, "insufficient_evidence")
        self.assertIn("outside validity", inv["lines"][0]["ref_source"])

    def test_verify_citations(self):
        h = Finding("H", "C", 1, "backed_difference", "invoice", 1,
                    "Supera   el VALOR del convenio", "interp")
        ok, _ = casefile.verify_finding(h, "reason: supera el valor del convenio x", 2)
        self.assertTrue(ok)  # normalizes case/accents/spaces
        h2 = Finding("H", "C", 1, "backed_difference", "invoice", 5,
                     "Supera el valor del convenio", "interp")
        self.assertFalse(casefile.verify_finding(h2, "supera el valor del convenio", 2)[0])
        h3 = Finding("H", "C", 1, "backed_difference", "invoice", 1,
                     "text missing from the document", "interp")
        self.assertFalse(casefile.verify_finding(h3, "something else entirely", 1)[0])
        h4 = Finding("H", "C", 1, "backed_difference", "invoice", 1, "short", "interp")
        self.assertFalse(casefile.verify_finding(h4, "short", 1)[0])

    def test_persistent_ids_and_versions(self):
        db = tempfile.mktemp(suffix=".db")
        s = SyntheticStore(db)
        s.seed_case(case("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        ag = Agent(s, SimulatedProvider())
        p1 = ag.propose("E1")
        s2 = SyntheticStore(db)  # "restart": new instance, same DB
        ag2 = Agent(s2, SimulatedProvider())
        p2 = ag2.propose("E1")
        self.assertEqual((p1.id, p2.id), ("P-E1-1", "P-E1-2"))
        self.assertEqual(s2.list_proposals("E1"), ["P-E1-1", "P-E1-2"])
        self.assertIsNotNone(s2.get_proposal("P-E1-1"))  # prior version intact

    def test_reads_never_call_model(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        ag = Agent(s, AlwaysFails())
        ag.query_status()
        ag.investigate("E1")
        ag.history("E1")
        drafts.claim_draft(s.get_case("E1"), "Agreements", "x")


if __name__ == "__main__":
    unittest.main()


class FakeMeta(Provider):
    name = "meta"
    def __init__(self, halls):
        self._h = halls
        self.last_call = {"provider": "meta", "status": "ok"}
    def complete_structured(self, *a, **k):
        return {"findings": self._h}


class TestModelFindings(unittest.TestCase):
    DOC = "VIGENCIA: 2026-01-01..2026-12-31 ARANCEL: CONSULTA GENERAL $16.500"

    def test_valid_is_verified_and_invalid_dropped(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        s.add_document("E1", "agreement", "c.pdf", 1, self.DOC)
        prov = FakeMeta([
            {"line_no": 1, "kind": "backed_difference", "document": "agreement",
             "page": 1, "excerpt": "ARANCEL: CONSULTA GENERAL $16.500",
             "interpretation": "Current value applies.", "limitations": ""},
            {"line_no": 0, "kind": "invented", "document": "agreement",
             "page": 1, "excerpt": "x", "interpretation": "y", "limitations": ""},
            {"line_no": 1, "kind": "inconsistency", "document": "settlement",
             "page": 1, "excerpt": "RENGLON 1: DEBITO $15.000",
             "interpretation": "Doc not linked.", "limitations": ""},
        ])
        ag = Agent(s, prov)
        prop = ag.propose("E1")
        hs = s.get_findings(prop.id)
        self.assertEqual(len(hs), 2)  # invalid kind dropped
        self.assertTrue(hs[0]["verified"])  # citation matches
        self.assertFalse(hs[1]["verified"])  # doc not linked
        self.assertIn("citation OK", prop.explanation)
        self.assertIn("CITATION UNVERIFIED", prop.explanation)

    def test_no_findings_degrades(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(case("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        ag = Agent(s, FakeMeta([]))
        prop = ag.propose("E1")
        self.assertIn("DEGRADED", prop.explanation)
        self.assertEqual(prop.action, "route_team")  # deterministic part kept
