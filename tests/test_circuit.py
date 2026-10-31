import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai import tasks
from debit_ai.contracts import Case, LineItem
from debit_ai.synthetic import SyntheticStore

SEC = "auto-test-sector"
DEB = "auto-test-debitos"


def _store():
    s = SyntheticStore(tempfile.mktemp(suffix=".db"))
    s.seed_case(Case("C1", "P", "F-1", (
        LineItem(1, "PR1", "Falta de autorizacion", 30000, 0),
        LineItem(2, "PR2", "Falta de detalle de descartables", 18500, 0),
    ), 48500))
    return s


def _verified(s, line, team, motive):
    t = tasks.create_task(s, "C1", line, team, motive)
    tasks.answer_task(s, t["id"], SEC, "resp", "backing-ref-1")
    return tasks.verify_task(s, t["id"], DEB)


class TestTaskLifecycle(unittest.TestCase):
    def test_full_answer_return_correct_verify(self):
        s = _store()
        t = tasks.create_task(s, "C1", 1, "Billing",
                              "Falta de autorizacion", "clerk")
        self.assertEqual(t["state"], "assigned")
        a = tasks.answer_task(s, t["id"], SEC, "it is in the file", "HC")
        self.assertEqual(a["state"], "pending_verification")
        r = tasks.return_task(s, t["id"], DEB, "need precise reference")
        self.assertEqual(r["state"], "returned")
        self.assertEqual(r["return_note"], "need precise reference")
        a2 = tasks.answer_task(s, t["id"], SEC, "found it",
                               "mail 2026-08-20 AUT-9")
        self.assertEqual(a2["state"], "pending_verification")
        v = tasks.verify_task(s, t["id"], DEB, "sufficient")
        self.assertEqual(v["state"], "verified")
        self.assertEqual(v["return_note"], "")
        kinds = [h[1] for h in s.history("C1")]
        for k in ("task", "task_return", "task_verify"):
            self.assertIn(k, kinds)
        ret = tasks.task_returns(s, "C1")
        self.assertEqual(len(ret), 1)
        self.assertIn("it is in the file", ret[0][3])  # prior kept

    def test_two_tasks_same_line(self):
        s = _store()
        a = tasks.create_task(s, "C1", 2, "Medical Audit", "m1")
        b = tasks.create_task(s, "C1", 2, "Billing", "m2")
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(len([t for t in s.list_tasks("C1")
                              if t["line_no"] == 2]), 2)

    def test_answer_requires_backing(self):
        s = _store()
        t = tasks.create_task(s, "C1", 1, "Billing", "m")
        for bad in ("", "   "):
            with self.assertRaises(ValueError):
                tasks.answer_task(s, t["id"], SEC, "resp", bad)
        self.assertEqual(s.get_task(t["id"])["state"], "assigned")

    def test_bad_transitions_rejected(self):
        s = _store()
        t = tasks.create_task(s, "C1", 1, "Billing", "m")
        with self.assertRaises(ValueError):  # nothing to verify
            tasks.verify_task(s, t["id"], DEB)
        with self.assertRaises(ValueError):  # nothing to return
            tasks.return_task(s, t["id"], DEB, "x")
        tasks.answer_task(s, t["id"], SEC, "r", "b")
        with self.assertRaises(ValueError):  # already pending
            tasks.answer_task(s, t["id"], SEC, "r2", "b2")
        tasks.verify_task(s, t["id"], DEB)
        with self.assertRaises(ValueError):  # verified: closed
            tasks.answer_task(s, t["id"], SEC, "r3", "b3")

    def test_create_validates(self):
        s = _store()
        with self.assertRaises(KeyError):
            tasks.create_task(s, "C1", 99, "Billing", "m")
        with self.assertRaises(KeyError):
            tasks.create_task(s, "NOPE", 1, "Billing", "m")
        with self.assertRaises(ValueError):
            tasks.create_task(s, "C1", 1, "Unknown", "m")
        with self.assertRaises(ValueError):
            tasks.create_task(s, "C1", 1, "Billing", "  ")


class TestResolution(unittest.TestCase):
    def test_resolution_considers_verified_tasks(self):
        s = _store()
        _verified(s, 1, "Billing", "m")
        _verified(s, 1, "Agreements", "m2")
        res = tasks.resolve_line(s, "C1", 1, DEB, "Rebill with AUT-9.")
        self.assertEqual(res["id"], "R-C1-L1")
        self.assertIn("2 task", [h[2] for h in s.history("C1")
                                 if h[1] == "resolution"][0])

    def test_resolution_lists_pending(self):
        s = _store()
        _verified(s, 1, "Billing", "m")
        t = tasks.create_task(s, "C1", 1, "Agreements", "m2")
        with self.assertRaisesRegex(ValueError, t["id"]):
            tasks.resolve_line(s, "C1", 1, DEB, "x")

    def test_resolution_guards(self):
        s = _store()
        with self.assertRaises(ValueError):  # no tasks
            tasks.resolve_line(s, "C1", 2, DEB, "x")
        _verified(s, 2, "Billing", "m")
        tasks.resolve_line(s, "C1", 2, DEB, "first")
        with self.assertRaises(ValueError):  # one per line
            tasks.resolve_line(s, "C1", 2, DEB, "second")
        with self.assertRaises(KeyError):  # bad line
            tasks.resolve_line(s, "C1", 9, DEB, "x")


class TestRebillingRecovery(unittest.TestCase):
    def test_chain_links(self):
        s = _store()
        _verified(s, 1, "Billing", "m")
        res = tasks.resolve_line(s, "C1", 1, DEB, "Rebill.")
        rb = tasks.record_rebilling(s, "C1", 1, "F-1-R", 30000, "P",
                                    "2026-09-01")
        self.assertEqual(rb["resolution_id"], res["id"])
        rec = tasks.record_recovery(s, rb["id"], "credit_note", "NC-1",
                                    DEB, 30000)
        self.assertEqual(rec["rebilling_id"], rb["id"])
        self.assertEqual(rec["amount_cents"], 30000)
        kinds = [h[1] for h in s.history("C1")]
        self.assertIn("rebilling", kinds)
        self.assertIn("recovery", kinds)

    def test_rebilling_requires_resolution(self):
        s = _store()
        _verified(s, 1, "Billing", "m")
        with self.assertRaises(ValueError):
            tasks.record_rebilling(s, "C1", 1, "F-1-R", 30000, "P")

    def test_single_rebilling_per_line(self):
        s = _store()
        _verified(s, 1, "Billing", "m")
        tasks.resolve_line(s, "C1", 1, DEB, "d")
        tasks.record_rebilling(s, "C1", 1, "F-1-R", 30000, "P")
        with self.assertRaisesRegex(ValueError, "ask first"):
            tasks.record_rebilling(s, "C1", 1, "F-1-R2", 100, "P")

    def test_recovery_guards(self):
        s = _store()
        _verified(s, 1, "Billing", "m")
        tasks.resolve_line(s, "C1", 1, DEB, "d")
        rb = tasks.record_rebilling(s, "C1", 1, "F-1-R", 30000, "P")
        with self.assertRaises(ValueError):
            tasks.record_recovery(s, rb["id"], "wire", "X", DEB)
        with self.assertRaises(KeyError):
            tasks.record_recovery(s, "RB-NOPE", "credit_note", "X", DEB)
        tasks.record_recovery(s, rb["id"], "rebilling_paid", "PAY-1", DEB)
        with self.assertRaisesRegex(ValueError, "ask first"):
            tasks.record_recovery(s, rb["id"], "credit_note", "NC-2", DEB)

    def test_no_amount_rule_derived(self):
        s = _store()
        _verified(s, 1, "Billing", "m")
        tasks.resolve_line(s, "C1", 1, DEB, "d")
        rb = tasks.record_rebilling(s, "C1", 1, "F-1-R", 30000, "P")
        rec = tasks.record_recovery(s, rb["id"], "credit_note", "NC-1",
                                    DEB, 10000)  # observed only
        self.assertEqual(rec["amount_cents"], 10000)
        self.assertNotIn("status", rec)


if __name__ == "__main__":
    unittest.main()
