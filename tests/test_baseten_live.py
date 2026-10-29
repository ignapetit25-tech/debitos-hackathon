"""REAL Baseten acceptance: call -> proposal -> review -> approval.

SKIPPED without BASETEN_API_KEY (neither env nor new-repo .env).
WITH a key, any Baseten failure FAILS the test: degraded mode
does NOT prove real integration. Runs only against Baseten
(IA_PROVIDER forced to baseten); spends hackathon credits.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from check_meta import load_repo_env  # noqa: E402

from debit_ai import approvals  # noqa: E402
from debit_ai.agent import Agent  # noqa: E402
from debit_ai.contracts import Case, LineItem  # noqa: E402
from debit_ai.provider import build_provider  # noqa: E402
from debit_ai.synthetic import SyntheticStore  # noqa: E402


def _enabled() -> bool:
    # Double requirement: key + explicit opt-in (default: skipped).
    load_repo_env()
    return bool(os.environ.get("BASETEN_API_KEY")) and os.environ.get("BASETEN_LIVE") == "1"


@unittest.skipUnless(_enabled(), "Baseten acceptance skipped (needs BASETEN_API_KEY and BASETEN_LIVE=1)")
class TestBasetenLive(unittest.TestCase):
    def test_admin_case_with_baseten_and_approval(self):
        os.environ["IA_PROVIDER"] = "baseten"
        prov = build_provider()
        self.assertEqual(prov.name, "baseten")
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(Case("BASE-1", "OS FICTICIA ANDINA", "F-900", (LineItem(
            1, "CONSULTA GENERAL", "supera el valor del convenio",
            20000, 5000),), 15000))
        ag = Agent(s, prov)
        prop = ag.propose("BASE-1")  # 1 real Baseten call
        m = dict(getattr(prov, "last_call", {}) or {})
        print(f"\n[baseten-live] model={m.get('returned_model')} "
              f"resp_id={m.get('response_id')} latency_ms={m.get('latency_ms')} "
              f"usage={m.get('usage')}")
        self.assertIn("Model (baseten):", prop.explanation)
        self.assertNotIn("DEGRADED", prop.explanation)
        calls = [h for h in s.history("BASE-1") if h[1] == "model_call"]
        self.assertEqual(len(calls), 1)
        det, after = calls[0][2], calls[0][4]
        self.assertIn("provider=baseten", det)
        self.assertIn("status=ok", det)
        self.assertNotIn("response_id=-", det)
        self.assertIn("ok: model text used", after)
        dec = approvals.review(s, prop.id, "reviewer-milestone", "approved",
                               "Baseten acceptance")
        self.assertEqual(dec.verdict, "approved")
        revs = [h for h in s.history("BASE-1") if h[1] == "review"]
        self.assertEqual(len(revs), 1)
        self.assertIn("reviewer-milestone", revs[0][4])


if __name__ == "__main__":
    unittest.main()
