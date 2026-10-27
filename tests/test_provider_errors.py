import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia_debitos.provider import (ProviderError, SimulatedProvider,
                                 _check_json_schema, build_provider)


class TestProviderErrors(unittest.TestCase):
    def test_meta_sin_clave(self):
        import os
        vieja = os.environ.pop("MODEL_API_KEY", None)
        try:
            with self.assertRaises(ProviderError):
                build_provider("meta")
        finally:
            if vieja is not None:
                os.environ["MODEL_API_KEY"] = vieja

    def test_proveedor_desconocido(self):
        with self.assertRaises(ProviderError):
            build_provider("openai-directo")

    def test_schema_invalido(self):
        schema = {"required": ["a"], "properties": {"a": {"type": "string"}}}
        with self.assertRaises(ProviderError):
            _check_json_schema({"b": 1}, schema)
        with self.assertRaises(ProviderError):
            _check_json_schema({"a": 5}, schema)

    def test_simulado_etiquetado(self):
        p = SimulatedProvider()
        self.assertEqual(p.name, "simulated")
        out = p.complete_structured("x", {"properties": {}}, "explicacion")
        self.assertIn("SIMULADO", out["explicacion"])


if __name__ == "__main__":
    unittest.main()
