import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai import approvals
from debit_ai.agent import Agent
from debit_ai.contracts import Case, LineItem
from debit_ai.provider import SimulatedProvider
from debit_ai.synthetic import SyntheticStore


class TestHistory(unittest.TestCase):
    def test_flow_leaves_ordered_trace(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(Case("C1", "OS FICTICIA ANDINA", "F-1", (LineItem(
            1, "CONSULTA GENERAL", "supera el valor del convenio",
            20000, 5000),), 15000))
        ag = Agent(s, SimulatedProvider())
        prop = ag.propose("C1")
        self.assertEqual(prop.team, "Agreements")
        approvals.review(s, prop.id, "auto-test", "approved", "ok")
        kinds = [h[1] for h in s.history("C1")]
        self.assertIn("tool", kinds)
        self.assertIn("proposal", kinds)
        self.assertIn("review", kinds)
        seqs = [h[0] for h in s.history("C1")]
        self.assertEqual(seqs, sorted(seqs))

    def test_events_carry_datetime(self):
        s = SyntheticStore(tempfile.mktemp(suffix=".db"))
        s.seed_case(Case("C2", "OS FICTICIA ANDINA", "F-2", (LineItem(
            1, "CONSULTA GENERAL", "supera el valor del convenio",
            20000, 5000),), 15000))
        ag = Agent(s, SimulatedProvider())
        prop = ag.propose("C2")
        approvals.review(s, prop.id, "auto-test", "approved", "ok")
        for h in s.history("C2"):
            self.assertEqual(len(h), 6)
            self.assertIn("T", h[5])  # ISO date+time
        rev = [h for h in s.history("C2") if h[1] == "review"][0]
        self.assertIn("auto-test", rev[4])


if __name__ == "__main__":
    unittest.main()
