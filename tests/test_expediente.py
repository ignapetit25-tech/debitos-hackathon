import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia_debitos import drafts, expediente
from ia_debitos.agent import Agente
from ia_debitos.contracts import Caso, Hallazgo, Renglon
from ia_debitos.provider import Provider, SimulatedProvider
from ia_debitos.synthetic import SyntheticStore


def caso(fecha, motivo, fact, liq, cid="E1"):
    return Caso(cid, "OS FICTICIA ANDINA", "F-1", (Renglon(
        1, "CONSULTA GENERAL", motivo, fact, liq),), fact - liq,
        "nuevo", fecha)


class FallaSiempre(Provider):
    name = "falla"
    last_call = {}
    def complete_structured(self, *a, **k):
        raise AssertionError("lectura no debe llamar al modelo")


class TestExpediente(unittest.TestCase):
    def test_respaldada_reclama(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(caso("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        ag = Agente(s, SimulatedProvider())
        prop = ag.proponer("E1")
        self.assertEqual((prop.sector, prop.accion), ("Convenios", "reclamar"))
        inv = ag.expediente("E1")
        self.assertEqual(inv["hallazgos"][0].tipo, "diferencia_respaldada")
        self.assertTrue(inv["hallazgos"][0].verificado)
        self.assertEqual(inv["renglones"][0]["ref_cents"], 1650000)

    def test_facturado_bajo_es_inconsistencia(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(caso("2026-08-15", "supera el valor del convenio", 1000000, 200000))
        ag = Agente(s, SimulatedProvider())
        prop = ag.proponer("E1")
        self.assertEqual(prop.accion, "pedir_extension")
        inv = ag.expediente("E1")
        self.assertEqual(inv["hallazgos"][0].tipo, "inconsistencia")

    def test_sin_fecha_no_respalda(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(caso("", "supera el valor del convenio", 2000000, 500000))
        ag = Agente(s, SimulatedProvider())
        prop = ag.proponer("E1")
        self.assertEqual(prop.sector, "Convenios")  # sector se conserva
        self.assertEqual(prop.accion, "pedir_extension")  # pero no reclama
        inv = ag.expediente("E1")
        self.assertEqual(inv["hallazgos"][0].tipo, "evidencia_insuficiente")

    def test_clinico_deriva(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(caso("2026-08-15", "no se realizo la operacion segun parte quirurgico",
                         4200000, 0))
        ag = Agente(s, SimulatedProvider())
        prop = ag.proponer("E1")
        self.assertEqual((prop.sector, prop.accion),
                         ("Auditoría Médica", "derivar_humano"))

    def test_convenio_vigencia(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(caso("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        s.registrar_documento("E1", "convenio", "conv.pdf", 1,
                              "VIGENCIA: 2026-01-01..2026-06-30\n"
                              "ARANCEL: CONSULTA GENERAL $16.500")
        ag = Agente(s, SimulatedProvider())
        inv = ag.expediente("E1")  # prestacion fuera de vigencia
        self.assertEqual(inv["hallazgos"][0].tipo, "evidencia_insuficiente")
        self.assertIn("fuera de vigencia", inv["renglones"][0]["fuente_ref"])

    def test_verificar_citas(self):
        h = Hallazgo("H", "C", 1, "diferencia_respaldada", "factura", 1,
                     "Supera   el VALOR del convenio", "interp")
        ok, _ = expediente.verificar_hallazgo(h, "motivo: supera el valor del convenio x", 2)
        self.assertTrue(ok)  # normaliza mayusculas/acentos/espacios
        h2 = Hallazgo("H", "C", 1, "diferencia_respaldada", "factura", 5,
                      "Supera el valor del convenio", "interp")
        self.assertFalse(expediente.verificar_hallazgo(h2, "supera el valor del convenio", 2)[0])
        h3 = Hallazgo("H", "C", 1, "diferencia_respaldada", "factura", 1,
                      "texto que no existe en el documento", "interp")
        self.assertFalse(expediente.verificar_hallazgo(h3, "otra cosa distinta", 1)[0])
        h4 = Hallazgo("H", "C", 1, "diferencia_respaldada", "factura", 1, "corto", "interp")
        self.assertFalse(expediente.verificar_hallazgo(h4, "corto", 1)[0])

    def test_ids_persistentes_y_versiones(self):
        db = tempfile.mktemp(suffix=".db")
        s = SyntheticStore(db)
        s.seed_caso(caso("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        ag = Agente(s, SimulatedProvider())
        p1 = ag.proponer("E1")
        s2 = SyntheticStore(db)  # "reinicio": nueva instancia, misma base
        ag2 = Agente(s2, SimulatedProvider())
        p2 = ag2.proponer("E1")
        self.assertEqual((p1.id, p2.id), ("P-E1-1", "P-E1-2"))
        self.assertEqual(s2.propuestas_caso("E1"), ["P-E1-1", "P-E1-2"])
        self.assertIsNotNone(s2.propuesta("P-E1-1"))  # version anterior intacta

    def test_lecturas_no_llaman_modelo(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(caso("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        ag = Agente(s, FallaSiempre())
        ag.consultar_estados()
        ag.expediente("E1")
        ag.historial("E1")
        drafts.borrador_reclamo(s.obtener_caso("E1"), "Convenios", "x")


if __name__ == "__main__":
    unittest.main()


class FakeMeta(Provider):
    name = "meta"
    def __init__(self, halls):
        self._h = halls
        self.last_call = {"proveedor": "meta", "estado": "ok"}
    def complete_structured(self, *a, **k):
        return {"hallazgos": self._h}


class TestHallazgosModelo(unittest.TestCase):
    DOC = "VIGENCIA: 2026-01-01..2026-12-31 ARANCEL: CONSULTA GENERAL $16.500"

    def test_valido_se_verifica_e_invalido_se_descarta(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(caso("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        s.registrar_documento("E1", "convenio", "c.pdf", 1, self.DOC)
        prov = FakeMeta([
            {"renglon_nro": 1, "tipo": "diferencia_respaldada", "documento": "convenio",
             "pagina": 1, "fragmento": "ARANCEL: CONSULTA GENERAL $16.500",
             "interpretacion": "Valor vigente aplicable.", "limitaciones": ""},
            {"renglon_nro": 0, "tipo": "invento", "documento": "convenio",
             "pagina": 1, "fragmento": "x", "interpretacion": "y", "limitaciones": ""},
            {"renglon_nro": 1, "tipo": "inconsistencia", "documento": "liquidacion",
             "pagina": 1, "fragmento": "RENGLON 1: DEBITO $15.000",
             "interpretacion": "Doc no vinculado.", "limitaciones": ""},
        ])
        ag = Agente(s, prov)
        prop = ag.proponer("E1")
        hs = s.hallazgos_propuesta(prop.id)
        self.assertEqual(len(hs), 2)  # tipo inválido descartado
        self.assertTrue(hs[0]["verificado"])  # cita coincide
        self.assertFalse(hs[1]["verificado"])  # doc no vinculado
        self.assertIn("cita OK", prop.explicacion)
        self.assertIn("CITA NO VERIFICADA", prop.explicacion)

    def test_sin_hallazgos_degrada(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(caso("2026-08-15", "supera el valor del convenio", 2000000, 500000))
        ag = Agente(s, FakeMeta([]))
        prop = ag.proponer("E1")
        self.assertIn("DEGRADADO", prop.explicacion)
        self.assertEqual(prop.accion, "reclamar")  # lo determinista se conserva
