"""Baseten sin red: construcción, errores explícitos, timeout, sin reintentos."""
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia_debitos.provider import BasetenProvider, ProviderError, build_provider


class TestBaseten(unittest.TestCase):
    def setUp(self):
        self._v = {}
        for k in ("BASETEN_API_KEY", "BASETEN_MODEL", "BASETEN_TIMEOUT",
                  "BASETEN_BASE_URL", "IA_PROVIDER"):
            self._v[k] = os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._v.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    def test_sin_clave_falla_explicito(self):
        with self.assertRaisesRegex(ProviderError, "BASETEN_API_KEY"):
            build_provider("baseten")

    def test_modelo_y_base_por_defecto(self):
        os.environ["BASETEN_API_KEY"] = "dummy-sin-red"
        p = build_provider("baseten")
        self.assertEqual(p.name, "baseten")
        self.assertEqual(p._model, "meta-models/muse-spark-open-1026")
        self.assertIn("inference.baseten.co", str(p._client.base_url))

    def test_timeout_y_sin_reintentos(self):
        os.environ["BASETEN_API_KEY"] = "dummy-sin-red"
        p = BasetenProvider()
        self.assertEqual(p._client.timeout, 60)
        self.assertEqual(p._client.max_retries, 0)
        os.environ["BASETEN_TIMEOUT"] = "7"
        self.assertEqual(BasetenProvider()._client.timeout, 7)
        os.environ["BASETEN_TIMEOUT"] = "no-numero"
        with self.assertRaisesRegex(ProviderError, "BASETEN_TIMEOUT"):
            BasetenProvider()

    def test_error_red_no_simula_exito(self):
        os.environ["BASETEN_API_KEY"] = "dummy-sin-red"
        p = BasetenProvider()

        class Rota:
            @property
            def chat(self):
                raise ConnectionError("red caída")
        p._client = Rota()
        with self.assertRaisesRegex(ProviderError, "error Baseten"):
            p.complete_structured("x", {"properties": {}}, "explicacion")
        self.assertEqual(p.last_call["proveedor"], "baseten")
        self.assertEqual(p.last_call["estado"], "error")

    def test_solo_chat(self):
        os.environ["BASETEN_API_KEY"] = "dummy-sin-red"
        with self.assertRaisesRegex(ProviderError, "solo admite chat"):
            BasetenProvider().complete_structured("x", {"properties": {}},
                                                  "explicacion", protocol="responses")


if __name__ == "__main__":
    unittest.main()
