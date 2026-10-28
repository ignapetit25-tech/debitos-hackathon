import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia_debitos import approvals, proceso
from ia_debitos.agent import Agente
from ia_debitos.contracts import Caso, Renglon
from ia_debitos.provider import SimulatedProvider
from ia_debitos.synthetic import SyntheticStore, sembrar_convenios


def caso(cid="P1", motivo="supera el valor del convenio", fact=2000000, liq=500000):
    return Caso(cid, "OS FICTICIA ANDINA", "F-1", (Renglon(
        1, "CONSULTA GENERAL", motivo, fact, liq),), fact - liq, "nuevo", "2026-08-15")


class TestProceso(unittest.TestCase):
    def test_prioridad(self):
        self.assertEqual(proceso.prioridad(100000001), "P1")
        self.assertEqual(proceso.prioridad(100000000), "P2")
        self.assertEqual(proceso.prioridad(50000000), "P2")
        self.assertEqual(proceso.prioridad(49999999), "P3")

    def test_sla_salta_fin_de_semana(self):
        self.assertEqual(proceso.sumar_habiles("2026-10-30", 1), "2026-11-02")
        self.assertEqual(proceso.sumar_habiles("2026-10-28", 5), "2026-11-04")

    def test_checklist(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(caso(motivo="coseguro no descontado al facturar"))
        ag = Agente(s, SimulatedProvider())
        chk = {i["item"]: i for i in proceso.checklist(s.obtener_caso("P1"), ag.expediente("P1"))}
        self.assertEqual(chk["Sumas"]["estado"], "ok")
        self.assertEqual(chk["Coseguros"]["valor"], "identificados")

    def test_seguimiento_ok_y_errores(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(caso())
        prop = Agente(s, SimulatedProvider()).proponer("P1")
        d = approvals.seguimiento(s, prop.id, "parcial", 1000000, 500000,
                                  "R. Convenios", "2026-10-28", "ok")
        self.assertEqual(d["decision"], "parcial")
        self.assertTrue(any(h[1] == "seguimiento" for h in s.historial("P1")))
        with self.assertRaises(ValueError):
            approvals.seguimiento(s, prop.id, "otra", 0, 0, "R", "2026-10-28")
        with self.assertRaises(ValueError):
            approvals.seguimiento(s, prop.id, "parcial", -1, 0, "R", "2026-10-28")
        with self.assertRaises(ValueError):
            approvals.seguimiento(s, prop.id, "parcial", True, 0, "R", "2026-10-28")
        with self.assertRaises(ValueError):
            approvals.seguimiento(s, prop.id, "parcial", 0, 0, "  ", "2026-10-28")
        with self.assertRaises(KeyError):
            approvals.seguimiento(s, "P-X-99", "parcial", 0, 0, "R", "2026-10-28")

    def test_gestor_solape_y_siembra(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        conv, amb = s.convenio_vigente("OS FICTICIA ANDINA", "2026-06-15")
        self.assertEqual(conv["id"], "CONV-AND-2026")
        self.assertTrue(amb)
        conv, amb = s.convenio_vigente("OS FICTICIA ANDINA", "2027-01-01")
        self.assertIsNone(conv)
        n0 = len(s.convenios_financiador("OS FICTICIA ANDINA"))
        sembrar_convenios(s)
        self.assertEqual(len(s.convenios_financiador("OS FICTICIA ANDINA")), n0)


if __name__ == "__main__":
    unittest.main()
