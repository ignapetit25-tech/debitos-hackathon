import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia_debitos import rules


class TestRules(unittest.TestCase):
    def test_convenios(self):
        r = rules.evaluar("supera el valor del convenio")
        self.assertEqual((r.sector, r.puntos), ("Convenios", 4))

    def test_umbral(self):
        r = rules.evaluar("verificar con sector")
        self.assertEqual(r.sector, rules.PENDIENTE)

    def test_clinico(self):
        self.assertTrue(rules.es_clinico("criterio medico dudoso"))
        self.assertFalse(rules.es_clinico("valor del convenio"))

    def test_puntaje_no_es_confianza(self):
        from ia_debitos.contracts import Propuesta, ReglaRef
        p = Propuesta("P1", "C1", "Convenios", ReglaRef("Convenios", 7, ("x",)),
                      "reclamar", "e", ("r",), False, 0.92)
        self.assertIsInstance(p.regla.puntos, int)
        self.assertIsInstance(p.extraccion_confianza, float)
        self.assertNotEqual(p.regla.puntos, p.extraccion_confianza)


if __name__ == "__main__":
    unittest.main()
