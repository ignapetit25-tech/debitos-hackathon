"""Aceptación Baseten REAL: llamada -> propuesta -> revisión -> aprobación.

Se OMITE sin BASETEN_API_KEY (ni entorno ni .env del repo nuevo).
CON clave, cualquier fallo de Baseten es FALLO del test: el modo
degradado NO demuestra integración real. Corre solo contra Baseten
(IA_PROVIDER forzado a baseten); consume créditos del hackathon.
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
    return bool(os.environ.get("BASETEN_API_KEY")) and os.environ.get("BASETEN_LIVE") == "1"


@unittest.skipUnless(_habilitado(), "aceptación Baseten omitida (requiere BASETEN_API_KEY y BASETEN_LIVE=1)")
class TestBasetenLive(unittest.TestCase):
    def test_caso_admin_con_baseten_y_aprobacion(self):
        os.environ["IA_PROVIDER"] = "baseten"
        prov = build_provider()
        self.assertEqual(prov.name, "baseten")
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_caso(Caso("BASE-1", "OS FICTICIA ANDINA", "F-900", (Renglon(
            1, "CONSULTA GENERAL", "supera el valor del convenio",
            20000, 5000),), 15000))
        ag = Agente(s, prov)
        prop = ag.proponer("BASE-1")  # 1 llamada real a Baseten
        m = dict(getattr(prov, "last_call", {}) or {})
        print(f"\n[baseten-live] modelo={m.get('modelo_devuelto')} "
              f"resp_id={m.get('respuesta_id')} latencia_ms={m.get('latencia_ms')} "
              f"uso={m.get('uso')}")
        self.assertIn("Modelo (baseten):", prop.explicacion)
        self.assertNotIn("DEGRADADO", prop.explicacion)
        llamadas = [h for h in s.historial("BASE-1") if h[1] == "llamada_modelo"]
        self.assertEqual(len(llamadas), 1)
        det, despues = llamadas[0][2], llamadas[0][4]
        self.assertIn("proveedor=baseten", det)
        self.assertIn("estado=ok", det)
        self.assertNotIn("resp_id=-", det)
        self.assertIn("ok: texto del modelo usado", despues)
        dec = approvals.revisar(s, prop.id, "revisor-hito", "aprobada",
                                "aceptación Baseten")
        self.assertEqual(dec.veredicto, "aprobada")
        revs = [h for h in s.historial("BASE-1") if h[1] == "revision"]
        self.assertEqual(len(revs), 1)
        self.assertIn("revisor-hito", revs[0][4])


if __name__ == "__main__":
    unittest.main()
