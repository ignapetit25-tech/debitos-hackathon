"""Aceptación Meta REAL: llamada -> propuesta -> revisión -> aprobación.

Se OMITE sin MODEL_API_KEY (ni entorno ni .env del repo nuevo).
CON clave, cualquier fallo de Meta es FALLO del test: el modo
degradado (reglas sin modelo) NO cumple el hito de integración real.
Corre solo contra Meta (IA_PROVIDER forzado a meta); sus resultados
nunca se mezclan con métricas del simulador.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from check_meta import cargar_env_repo  # noqa: E402

from ia_debitos import approvals  # noqa: E402
from ia_debitos.agent import Agente  # noqa: E402
from ia_debitos.contracts import Caso, Renglon  # noqa: E402
from ia_debitos.provider import build_provider  # noqa: E402
from ia_debitos.synthetic import SyntheticStore  # noqa: E402


def _habilitado() -> bool:
    # Doble requisito: clave + habilitación explícita (default: omitido).
    cargar_env_repo()
    return bool(os.environ.get("MODEL_API_KEY")) and os.environ.get("META_LIVE") == "1"


@unittest.skipUnless(_habilitado(), "aceptación Meta omitida (requiere MODEL_API_KEY y META_LIVE=1)")
class TestMetaLive(unittest.TestCase):
    def test_caso_admin_con_meta_y_aprobacion(self):
        os.environ["IA_PROVIDER"] = "meta"
        prov = build_provider()  # sin clave aquí = error (ya verificada)
        self.assertEqual(prov.name, "meta")
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(Caso("META-1", "OS FICTICIA ANDINA", "F-900", (Renglon(
            1, "CONSULTA GENERAL", "supera el valor del convenio",
            20000, 5000),), 15000))
        ag = Agente(s, prov)
        prop = ag.proponer("META-1")  # 1 llamada real a Meta
        # 1. llamada exitosa y texto UTILIZADO en la propuesta
        self.assertIn("Modelo (meta):", prop.explicacion)
        self.assertNotIn("DEGRADADO", prop.explicacion)
        llamadas = [h for h in s.historial("META-1") if h[1] == "llamada_modelo"]
        self.assertEqual(len(llamadas), 1)
        det, despues = llamadas[0][2], llamadas[0][4]
        self.assertIn("proveedor=meta", det)
        self.assertIn("estado=ok", det)
        self.assertNotIn("resp_id=-", det)  # hay ID de respuesta real
        self.assertIn("ok: texto del modelo usado", despues)
        # 2. revisión humana + aprobación registrada
        dec = approvals.revisar(s, prop.id, "revisor-hito", "aprobada",
                                "aceptación Meta")
        self.assertEqual(dec.veredicto, "aprobada")
        revs = [h for h in s.historial("META-1") if h[1] == "revision"]
        self.assertEqual(len(revs), 1)
        self.assertIn("revisor-hito", revs[0][4])


if __name__ == "__main__":
    unittest.main()
