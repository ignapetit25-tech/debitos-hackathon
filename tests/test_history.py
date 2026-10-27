import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia_debitos import approvals
from ia_debitos.agent import Agente
from ia_debitos.contracts import Caso, Renglon
from ia_debitos.provider import SimulatedProvider
from ia_debitos.synthetic import SyntheticStore


class TestHistory(unittest.TestCase):
    def test_flujo_deja_traza_ordenada(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(Caso("C1", "OS FICTICIA ANDINA", "F-1", (Renglon(
            1, "CONSULTA GENERAL", "supera el valor del convenio",
            20000, 5000),), 15000))
        ag = Agente(s, SimulatedProvider())
        prop = ag.proponer("C1")
        self.assertEqual(prop.sector, "Convenios")
        approvals.revisar(s, prop.id, "Humano", "aprobada", "ok")
        tipos = [h[1] for h in s.historial("C1")]
        self.assertIn("herramienta", tipos)
        self.assertIn("propuesta", tipos)
        self.assertIn("revision", tipos)
        seqs = [h[0] for h in s.historial("C1")]
        self.assertEqual(seqs, sorted(seqs))


if __name__ == "__main__":
    unittest.main()
