import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai import rules


class TestRules(unittest.TestCase):
    def test_agreements(self):
        r = rules.evaluate("supera el valor del convenio")
        self.assertEqual((r.team, r.points), ("Agreements", 4))

    def test_threshold(self):
        r = rules.evaluate("verificar con sector")
        self.assertEqual(r.team, rules.PENDING)

    def test_clinical(self):
        self.assertTrue(rules.is_clinical(
            "La medicación utilizada no corresponde al cuadro del paciente"))
        self.assertTrue(rules.is_clinical("criterio medico dudoso"))
        self.assertFalse(rules.is_clinical("valor del convenio"))

    def test_score_is_not_confidence(self):
        from debit_ai.contracts import Proposal, RuleRef
        p = Proposal("P1", "C1", "Agreements", RuleRef("Agreements", 7, ("x",)),
                     "route_team", "e", ("r",), False, 0.92)
        self.assertIsInstance(p.rule.points, int)
        self.assertIsInstance(p.extraction_confidence, float)
        self.assertNotEqual(p.rule.points, p.extraction_confidence)


if __name__ == "__main__":
    unittest.main()
