import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia_debitos import approvals
from ia_debitos.contracts import Caso, Propuesta, ReglaRef, Renglon
from ia_debitos.synthetic import SyntheticStore


def _store():
    s = SyntheticStore(tempfile.mktemp(suffix=".db"))
    s.seed_caso(Caso("C1", "F", "F-1", (Renglon(1, "P", "M", 200, 100),), 100))
    s.guardar_propuesta("C1", Propuesta("P1", "C1", "Convenios",
        ReglaRef("Convenios", 4, ("x",)), "reclamar", "e", ("r",)))
    return s


class TestApprovals(unittest.TestCase):
    def test_aprobar_y_rechazar(self):
        for v in ("aprobada", "rechazada"):
            s = _store()
            d = approvals.revisar(s, "P1", "Humano", v, "ok")
            self.assertEqual(d.veredicto, v)
            hist = s.historial("C1")
            self.assertTrue(any(h[1] == "revision" for h in hist))
            rev = [h for h in hist if h[1] == "revision"][0]
            self.assertNotEqual(rev[3], rev[4])  # antes != despues

    def test_requiere_revisor_y_veredicto(self):
        with self.assertRaises(ValueError):
            approvals.revisar(_store(), "P1", "  ", "aprobada")
        with self.assertRaises(ValueError):
            approvals.revisar(_store(), "P1", "H", "quizas")
        with self.assertRaises(KeyError):
            approvals.revisar(_store(), "PX", "H", "aprobada")


if __name__ == "__main__":
    unittest.main()
