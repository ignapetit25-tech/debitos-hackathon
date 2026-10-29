"""Baseten without network: build, explicit errors, timeout, no retries."""
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai.provider import BasetenProvider, ProviderError, build_provider


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

    def test_missing_key_fails_explicit(self):
        with self.assertRaisesRegex(ProviderError, "BASETEN_API_KEY"):
            build_provider("baseten")

    def test_default_model_and_base(self):
        os.environ["BASETEN_API_KEY"] = "dummy-no-net"
        p = build_provider("baseten")
        self.assertEqual(p.name, "baseten")
        self.assertEqual(p._model, "meta-models/muse-spark-open-1026")
        self.assertIn("inference.baseten.co", str(p._client.base_url))

    def test_timeout_and_no_retries(self):
        os.environ["BASETEN_API_KEY"] = "dummy-no-net"
        p = BasetenProvider()
        self.assertEqual(p._client.timeout, 60)
        self.assertEqual(p._client.max_retries, 0)
        os.environ["BASETEN_TIMEOUT"] = "7"
        self.assertEqual(BasetenProvider()._client.timeout, 7)
        os.environ["BASETEN_TIMEOUT"] = "not-a-number"
        with self.assertRaisesRegex(ProviderError, "BASETEN_TIMEOUT"):
            BasetenProvider()

    def test_net_error_fakes_no_success(self):
        os.environ["BASETEN_API_KEY"] = "dummy-no-net"
        p = BasetenProvider()

        class Broken:
            @property
            def chat(self):
                raise ConnectionError("net down")
        p._client = Broken()
        with self.assertRaisesRegex(ProviderError, "Baseten error"):
            p.complete_structured("x", {"properties": {}}, "explanation")
        self.assertEqual(p.last_call["provider"], "baseten")
        self.assertEqual(p.last_call["status"], "error")

    def test_chat_only(self):
        os.environ["BASETEN_API_KEY"] = "dummy-no-net"
        with self.assertRaisesRegex(ProviderError, "only supports chat"):
            BasetenProvider().complete_structured("x", {"properties": {}},
                                                  "explanation", protocol="responses")


if __name__ == "__main__":
    unittest.main()
