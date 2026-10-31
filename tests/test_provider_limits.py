"""Preventive I/O limits: input truncation before any call, output token
caps passed to the provider. Offline only: stubbed clients, no network."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai.agent import Agent
from debit_ai.contracts import Case, LineItem
from debit_ai.provider import (BasetenProvider, MetaProvider, ProviderError,
                               apply_input_budget, build_provider)
from debit_ai.synthetic import SyntheticStore

VARS = ("IA_MAX_INPUT_CHARS", "META_MAX_OUTPUT_TOKENS",
        "BASETEN_MAX_OUTPUT_TOKENS", "MODEL_API_KEY", "BASETEN_API_KEY")


class _Env:
    def __init__(self, test):
        self.saved = {k: os.environ.pop(k, None) for k in VARS}
        test.addCleanup(self.restore)

    def restore(self):
        for k, v in self.saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


class _ChatStub:
    """Captures chat.completions.create kwargs; canned JSON reply."""
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None
        msg = type("M", (), {"content": json.dumps(payload)})()
        choice = type("C", (), {"message": msg})()
        self.resp = type("R", (), {"choices": [choice], "model": "m",
                                   "id": "r", "usage": None})()

    @property
    def chat(self):
        outer = self

        class _Compl:
            def create(self, **kw):
                outer.kwargs = kw
                return outer.resp
        return type("C", (), {"completions": _Compl()})()


class _RespStub:
    """Captures responses.create kwargs; canned JSON reply."""
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None
        self.resp = type("R", (), {"output_text": json.dumps(payload),
                                    "model": "m", "id": "r",
                                    "usage": None})()

    @property
    def responses(self):
        outer = self

        class _R:
            def create(self, **kw):
                outer.kwargs = kw
                return outer.resp
        return _R()


class TestInputBudget(unittest.TestCase):
    def test_short_prompt_untouched(self):
        _Env(self)
        out, info = apply_input_budget("hello")
        self.assertEqual(out, "hello")
        self.assertEqual(info, {"input_chars": 5, "sent_chars": 5,
                                "truncated": False})

    def test_long_prompt_truncated_with_mark(self):
        _Env(self)
        out, info = apply_input_budget("x" * 13000)
        self.assertTrue(info["truncated"])
        self.assertEqual(info["input_chars"], 13000)
        self.assertEqual(info["sent_chars"], 12000)
        self.assertIn("[TRUNCATED by input budget: 13000>12000 chars]", out)

    def test_env_limit_and_invalid(self):
        _Env(self)
        os.environ["IA_MAX_INPUT_CHARS"] = "100"
        out, info = apply_input_budget("x" * 101)
        self.assertTrue(info["truncated"])
        self.assertEqual(info["sent_chars"], 100)
        os.environ["IA_MAX_INPUT_CHARS"] = "nope"
        with self.assertRaisesRegex(ProviderError, "IA_MAX_INPUT_CHARS"):
            apply_input_budget("x")
        os.environ["IA_MAX_INPUT_CHARS"] = "0"
        with self.assertRaisesRegex(ProviderError, "IA_MAX_INPUT_CHARS"):
            apply_input_budget("x")


class TestOutputCaps(unittest.TestCase):
    def test_baseten_default_and_override(self):
        _Env(self)
        os.environ["BASETEN_API_KEY"] = "dummy-no-net"
        self.assertEqual(build_provider("baseten")._max_out, 2000)
        os.environ["BASETEN_MAX_OUTPUT_TOKENS"] = "500"
        self.assertEqual(BasetenProvider()._max_out, 500)
        os.environ["BASETEN_MAX_OUTPUT_TOKENS"] = "bad"
        with self.assertRaisesRegex(ProviderError,
                                    "BASETEN_MAX_OUTPUT_TOKENS"):
            BasetenProvider()

    def test_baseten_sends_max_tokens(self):
        _Env(self)
        os.environ["BASETEN_API_KEY"] = "dummy-no-net"
        os.environ["BASETEN_MAX_OUTPUT_TOKENS"] = "321"
        p = BasetenProvider()
        stub = _ChatStub({"a": 1})
        p._client = stub
        p.complete_structured("hi", {"properties": {"a": {"type": "number"}}},
                              "t")
        self.assertEqual(stub.kwargs["max_tokens"], 321)
        self.assertEqual(p.last_call["max_output_tokens"], 321)
        self.assertEqual(p.last_call["input_chars"], 2)

    def test_meta_responses_and_chat_caps(self):
        _Env(self)
        os.environ["MODEL_API_KEY"] = "dummy-no-net"
        self.assertEqual(MetaProvider()._max_out, 2000)
        os.environ["META_MAX_OUTPUT_TOKENS"] = "bad"
        with self.assertRaisesRegex(ProviderError,
                                    "META_MAX_OUTPUT_TOKENS"):
            MetaProvider()
        os.environ["META_MAX_OUTPUT_TOKENS"] = "432"
        pr = MetaProvider()
        stub = _RespStub({"a": "s"})
        pr._client = stub
        pr.complete_structured("hi", {"properties": {"a": {"type": "string"}}},
                               "t", protocol="responses")
        self.assertEqual(stub.kwargs["max_output_tokens"], 432)
        pc = MetaProvider()
        cstub = _ChatStub({"a": "s"})
        pc._client = cstub
        pc.complete_structured("hi", {"properties": {"a": {"type": "string"}}},
                               "t", protocol="chat")
        self.assertEqual(cstub.kwargs["max_tokens"], 432)


class TestAgentEnforcesInputBudget(unittest.TestCase):
    def test_huge_document_never_sent_whole(self):
        _Env(self)
        os.environ["IA_MAX_INPUT_CHARS"] = "2000"
        seen = {}

        class Cap:
            name = "cap"
            last_call = {"provider": "cap", "status": "no-calls"}

            def complete_structured(self, prompt, schema, schema_name="r",
                                    protocol=None):
                seen["prompt"] = prompt
                return {"findings": []}

        db = tempfile.mktemp(suffix=".db")
        s = SyntheticStore(db)
        s.seed_case(Case("C9", "P", "F-9",
                         (LineItem(1, "PR", "m", 100, 0),), 100))
        big = "EVIDENCE " * 5000  # 45000 chars
        s.add_document("C9", "invoice", "f.pdf", 1, big)
        case = s.get_case("C9")
        agent = Agent(s, Cap())
        inv = agent.investigate("C9")
        agent._model_findings(case, inv)
        self.assertIn("TRUNCATED by input budget", seen["prompt"])
        self.assertLess(len(seen["prompt"]), 2600)
        self.assertTrue(Cap.last_call["input_truncated"])


if __name__ == "__main__":
    unittest.main()


class TestCoverageTransparency(unittest.TestCase):
    def _case_with_doc(self, text):
        db = tempfile.mktemp(suffix=".db")
        s = SyntheticStore(db)
        s.seed_case(Case("C9", "P", "F-9",
                         (LineItem(1, "PR", "m", 100, 0),), 100))
        s.add_document("C9", "invoice", "f.pdf", 1, text)
        return s

    def test_truncated_run_marks_partial(self):
        _Env(self)
        os.environ["IA_MAX_INPUT_CHARS"] = "2000"

        class Cap:
            name = "cap"

            def __init__(self):
                self.last_call = {"provider": "cap"}

            def complete_structured(self, prompt, schema, schema_name="r",
                                    protocol=None):
                return {"findings": [{
                    "line_no": 1, "kind": "backed_difference",
                    "document": "invoice", "page": 1,
                    "excerpt": "EVIDENCE", "interpretation": "i",
                    "limitations": ""}]}

        s = self._case_with_doc("EVIDENCE " * 5000)
        agent = Agent(s, Cap())
        prop = agent.propose("C9")
        self.assertIn("PARTIAL INPUT", prop.explanation)
        cov = agent.provider.last_call["input_coverage"]
        self.assertIn("TRUNCATED", cov)
        self.assertIn("invoice", cov)
        det = [h[2] for h in s.history("C9") if h[1] == "model_call"][0]
        self.assertIn("coverage=", det)
        self.assertIn("TRUNCATED", det)

    def test_full_coverage_recorded(self):
        _Env(self)

        class Cap:
            name = "cap"

            def __init__(self):
                self.last_call = {"provider": "cap"}

            def complete_structured(self, prompt, schema, schema_name="r",
                                    protocol=None):
                return {"findings": []}

        s = self._case_with_doc("short text")
        agent = Agent(s, Cap())
        prop = agent.propose("C9")
        self.assertNotIn("PARTIAL INPUT", prop.explanation)
        self.assertIn("invoice", agent.provider.last_call["input_coverage"])
        self.assertFalse(agent.provider.last_call["input_truncated"])
