import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai.provider import (ProviderError, SimulatedProvider,
                                 _check_json_schema, build_provider)


class TestProviderErrors(unittest.TestCase):
    def test_meta_without_key(self):
        import os
        old = os.environ.pop("MODEL_API_KEY", None)
        try:
            with self.assertRaises(ProviderError):
                build_provider("meta")
        finally:
            if old is not None:
                os.environ["MODEL_API_KEY"] = old

    def test_unknown_provider(self):
        with self.assertRaises(ProviderError):
            build_provider("openai-direct")

    def test_invalid_schema(self):
        schema = {"required": ["a"], "properties": {"a": {"type": "string"}}}
        with self.assertRaises(ProviderError):
            _check_json_schema({"b": 1}, schema)
        with self.assertRaises(ProviderError):
            _check_json_schema({"a": 5}, schema)

    def test_simulated_tagged(self):
        p = SimulatedProvider()
        self.assertEqual(p.name, "simulated")
        out = p.complete_structured("x", {"properties": {}}, "explanation")
        self.assertIn("SIMULATED", out["explanation"])


if __name__ == "__main__":
    unittest.main()
