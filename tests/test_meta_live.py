"""REAL Meta acceptance: call -> proposal -> review -> approval.

SKIPPED without MODEL_API_KEY (neither env nor new-repo .env).
WITH a key, any Meta failure FAILS the test: degraded mode
(rules without model) does NOT meet the real-integration bar.
Runs only against Meta (IA_PROVIDER forced to meta); its results
are never mixed with simulator metrics.
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
    return bool(os.environ.get("MODEL_API_KEY")) and os.environ.get("META_LIVE") == "1"


@unittest.skipUnless(_enabled(), "Meta acceptance skipped (needs MODEL_API_KEY and META_LIVE=1)")
class TestMetaLive(unittest.TestCase):
    def test_admin_case_with_meta_and_approval(self):
        os.environ["IA_PROVIDER"] = "meta"
        prov = build_provider()  # no key here = error (already checked)
        self.assertEqual(prov.name, "meta")
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(Case("META-1", "OS FICTICIA ANDINA", "F-900", (LineItem(
            1, "CONSULTA GENERAL", "supera el valor del convenio",
            20000, 5000),), 15000))
        ag = Agent(s, prov)
        prop = ag.propose("META-1")  # 1 real Meta call
        # 1. successful call with text USED in the proposal
        self.assertIn("Model (meta):", prop.explanation)
        self.assertNotIn("DEGRADED", prop.explanation)
        calls = [h for h in s.history("META-1") if h[1] == "model_call"]
        self.assertEqual(len(calls), 1)
        det, after = calls[0][2], calls[0][4]
        self.assertIn("provider=meta", det)
        self.assertIn("status=ok", det)
        self.assertNotIn("response_id=-", det)  # a real response ID exists
        self.assertIn("ok: model text used", after)
        # 2. human review + recorded approval
        dec = approvals.review(s, prop.id, "reviewer-milestone", "approved",
                               "Meta acceptance")
        self.assertEqual(dec.verdict, "approved")
        revs = [h for h in s.history("META-1") if h[1] == "review"]
        self.assertEqual(len(revs), 1)
        self.assertIn("reviewer-milestone", revs[0][4])


if __name__ == "__main__":
    unittest.main()
