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


def _rebilled(s, line=1, amount=30000):
    t = tasks.create_task(s, "C1", line, "Billing", "m")
    tasks.answer_task(s, t["id"], SEC, "r", "b")
    tasks.verify_task(s, t["id"], DEB)
    tasks.resolve_line(s, "C1", line, DEB, "d")
    return tasks.record_rebilling(s, "C1", line, f"F-1-R{line}", amount, "P")


class TestRecognition(unittest.TestCase):
    def test_partial_recognition_and_dispute(self):
        s = _store()
        rb = _rebilled(s)
        rec = tasks.record_recognition(s, rb["id"], "financier_credit_note",
                                       10000, "NC-1", "P", DEB, "2026-09-20")
        self.assertEqual(rec["id"], f"RC-{rb['id']}-1")
        self.assertEqual(tasks.recognized_total(s, rb["id"]), 10000)
        self.assertEqual(tasks.disputed_balance(s, rb["id"]), 20000)
        det = [h[2] for h in s.history("C1") if h[1] == "recognition"][0]
        self.assertIn("balance in dispute", det)
        self.assertIn("may arrive as a new debit", det)

    def test_treasury_confirmation_flags_ambiguous_pair(self):
        s = _store()
        rb = _rebilled(s)
        tasks.record_recognition(s, rb["id"], "financier_credit_note",
                                 10000, "NC-1", "P", DEB, "2026-09-20")
        self.assertFalse(tasks.needs_reconciliation(s, rb["id"]))
        tasks.record_recognition(s, rb["id"], "treasury_confirmation",
                                 10000, "PAY-7", "Treasury", DEB, "2026-09-21")
        self.assertTrue(tasks.needs_reconciliation(s, rb["id"]))
        self.assertEqual(tasks.recognized_total(s, rb["id"]), 20000)

    def test_duplicate_reference_refused(self):
        s = _store()
        rb = _rebilled(s)
        tasks.record_recognition(s, rb["id"], "financier_credit_note",
                                 10000, "NC-1", "P", DEB, "2026-09-20")
        with self.assertRaisesRegex(ValueError, "already recorded"):
            tasks.record_recognition(s, rb["id"], "treasury_confirmation",
                                     10000, "  nc-1 ", "T", DEB, "2026-09-21")
        self.assertEqual(tasks.recognized_total(s, rb["id"]), 10000)

    def test_reconcile_excludes_duplicate(self):
        s = _store()
        rb = _rebilled(s)
        a = tasks.record_recognition(s, rb["id"], "financier_credit_note",
                                     30000, "NC-1", "P", DEB, "2026-09-20")
        b = tasks.record_recognition(s, rb["id"], "treasury_confirmation",
                                     30000, "PAY-1", "Treasury", DEB,
                                     "2026-09-21")
        tasks.reconcile_recognition(s, b["id"], a["id"], DEB, "same payment")
        self.assertEqual(tasks.recognized_total(s, rb["id"]), 30000)
        self.assertFalse(tasks.needs_reconciliation(s, rb["id"]))
        self.assertIn("reconcile", [h[1] for h in s.history("C1")])

    def test_reconcile_guards(self):
        s = _store()
        rb = _rebilled(s)
        a = tasks.record_recognition(s, rb["id"], "financier_credit_note",
                                     10000, "NC-1", "P", DEB, "2026-09-20")
        with self.assertRaises(ValueError):
            tasks.reconcile_recognition(s, a["id"], a["id"], DEB)
        with self.assertRaises(KeyError):
            tasks.reconcile_recognition(s, "RC-X", a["id"], DEB)
        rb2 = _rebilled(s, line=2, amount=18500)
        c = tasks.record_recognition(s, rb2["id"], "treasury_confirmation",
                                     18500, "PAY-2", "T", DEB, "2026-09-21")
        with self.assertRaisesRegex(ValueError, "different rebillings"):
            tasks.reconcile_recognition(s, c["id"], a["id"], DEB)
        b = tasks.record_recognition(s, rb["id"], "treasury_confirmation",
                                     10000, "PAY-9", "T", DEB, "2026-09-21")
        tasks.reconcile_recognition(s, b["id"], a["id"], DEB)
        d = tasks.record_recognition(s, rb["id"], "treasury_confirmation",
                                     5000, "PAY-10", "T", DEB, "2026-09-22")
        with self.assertRaisesRegex(ValueError, "itself a duplicate"):
            tasks.reconcile_recognition(s, d["id"], b["id"], DEB)

    def test_over_recognition_alert(self):
        s = _store()
        rb = _rebilled(s)
        tasks.record_recognition(s, rb["id"], "financier_credit_note",
                                 30000, "NC-1", "P", DEB, "2026-09-20")
        tasks.record_recognition(s, rb["id"], "treasury_confirmation",
                                 5000, "PAY-2", "T", DEB, "2026-09-21")
        alerts = tasks.circuit_alerts(s, "C1")
        self.assertTrue(any("exceeds rebilled" in a for a in alerts))
        self.assertTrue(any("reconcile" in a for a in alerts))

    def test_recognition_validates(self):
        s = _store()
        rb = _rebilled(s)
        with self.assertRaises(KeyError):
            tasks.record_recognition(s, "RB-X", "financier_credit_note",
                                     1, "R", "P", DEB, "2026-09-20")
        with self.assertRaises(ValueError):
            tasks.record_recognition(s, rb["id"], "wire", 1, "R", "P",
                                     DEB, "2026-09-20")
        with self.assertRaises(ValueError):
            tasks.record_recognition(s, rb["id"], "financier_credit_note",
                                     -5, "R", "P", DEB, "2026-09-20")


class TestAcceptedDebit(unittest.TestCase):
    def test_accept_closes_line(self):
        s = _store()
        t = tasks.create_task(s, "C1", 1, "Billing", "m")
        tasks.answer_task(s, t["id"], SEC, "r", "b")
        tasks.verify_task(s, t["id"], DEB)
        acc = tasks.accept_debit(s, "C1", 1, DEB, "billed twice by us",
                                 "pre-invoice checklist")
        self.assertEqual(acc["id"], "A-C1-L1")
        with self.assertRaisesRegex(ValueError, "accepted debit"):
            tasks.resolve_line(s, "C1", 1, DEB, "x")
        self.assertIn("accepted", [h[1] for h in s.history("C1")])

    def test_accept_blocks_rebilling(self):
        s = _store()
        t = tasks.create_task(s, "C1", 1, "Billing", "m")
        tasks.answer_task(s, t["id"], SEC, "r", "b")
        tasks.verify_task(s, t["id"], DEB)
        tasks.accept_debit(s, "C1", 1, DEB, "origin")
        with self.assertRaises(ValueError):
            tasks.record_rebilling(s, "C1", 1, "F-1-R", 30000, "P")

    def test_accept_guards(self):
        s = _store()
        with self.assertRaises(ValueError):
            tasks.accept_debit(s, "C1", 1, DEB, "o")
        t = tasks.create_task(s, "C1", 1, "Billing", "m")
        with self.assertRaisesRegex(ValueError, t["id"]):
            tasks.accept_debit(s, "C1", 1, DEB, "o")
        tasks.answer_task(s, t["id"], SEC, "r", "b")
        tasks.verify_task(s, t["id"], DEB)
        tasks.accept_debit(s, "C1", 1, DEB, "o")
        with self.assertRaisesRegex(ValueError, "already closed"):
            tasks.accept_debit(s, "C1", 1, DEB, "o2")
        with self.assertRaises(ValueError):
            tasks.accept_debit(s, "C1", 1, "  ", "o")
        with self.assertRaises(KeyError):
            tasks.accept_debit(s, "C1", 9, DEB, "o")


class TestAccountingDocs(unittest.TestCase):
    def test_doc_without_closure_alerts(self):
        s = _store()
        t = tasks.create_task(s, "C1", 1, "Billing", "m")
        tasks.answer_task(s, t["id"], SEC, "r", "b")
        tasks.verify_task(s, t["id"], DEB)
        tasks.record_accounting_doc(s, "C1", 1, "provider_credit_note",
                                    "NC-CONT-5", "auto-test-books")
        alerts = tasks.circuit_alerts(s, "C1")
        self.assertTrue(any("without debitos closure" in a for a in alerts))
        tasks.resolve_line(s, "C1", 1, DEB, "d")
        self.assertFalse([a for a in tasks.circuit_alerts(s, "C1")
                          if "NC-CONT-5" in a])

    def test_doc_never_substitutes_authorization(self):
        s = _store()
        t = tasks.create_task(s, "C1", 1, "Billing", "m")
        tasks.answer_task(s, t["id"], SEC, "r", "b")
        tasks.verify_task(s, t["id"], DEB)
        tasks.record_accounting_doc(s, "C1", None, "provider_credit_note",
                                    "NC-CONT-9", "auto-test-books")
        with self.assertRaises(ValueError):  # still needs resolution
            tasks.record_rebilling(s, "C1", 1, "F-1-R", 30000, "P")
        self.assertTrue(any("without debitos resolution" in a
                            for a in tasks.circuit_alerts(s, "C1")))

    def test_doc_validates(self):
        s = _store()
        with self.assertRaises(KeyError):
            tasks.record_accounting_doc(s, "NOPE", None,
                                        "provider_credit_note", "N", "R")
        with self.assertRaises(KeyError):
            tasks.record_accounting_doc(s, "C1", 99, "provider_credit_note",
                                        "N", "R")
        with self.assertRaises(ValueError):
            tasks.record_accounting_doc(s, "C1", None, "invoice", "N", "R")


class TestSharedAudit(unittest.TestCase):
    def _disputed(self):
        s = _store()
        s.seed_case(Case("C2", "P", "F-2",
                         (LineItem(1, "PR", "new motive", 20000, 0),), 20000))
        rb = _rebilled(s)
        tasks.record_recognition(s, rb["id"], "financier_credit_note",
                                 10000, "NC-1", "P", DEB, "2026-09-20")
        return s, rb

    def test_request_links_origin_and_new_case(self):
        s, rb = self._disputed()
        au = tasks.request_shared_audit(s, rb["id"], "C2", "rest re-debited",
                                        DEB, "auto-test-auditor",
                                        "payer staff")
        self.assertEqual(au["id"], "SA-1")
        self.assertEqual(au["channel"], "email")
        self.assertIn("shared_audit", [h[1] for h in s.history("C1")])
        self.assertIn("shared_audit", [h[1] for h in s.history("C2")])
        self.assertEqual(len(s.list_shared_audits("C1")), 1)
        self.assertEqual(len(s.list_shared_audits("C2")), 1)

    def test_requires_disputed_balance(self):
        s = _store()
        s.seed_case(Case("C2", "P", "F-2",
                         (LineItem(1, "PR", "m", 100, 0),), 100))
        rb = _rebilled(s)
        tasks.record_recognition(s, rb["id"], "financier_credit_note",
                                 30000, "NC-FULL", "P", DEB, "2026-09-20")
        with self.assertRaisesRegex(ValueError, "no disputed balance"):
            tasks.request_shared_audit(s, rb["id"], "C2", "m", DEB, "A", "P")

    def test_request_guards(self):
        s, rb = self._disputed()
        with self.assertRaises(KeyError):
            tasks.request_shared_audit(s, "RB-X", "C2", "m", DEB, "A", "P")
        with self.assertRaises(KeyError):
            tasks.request_shared_audit(s, rb["id"], "CX", "m", DEB, "A", "P")
        with self.assertRaisesRegex(ValueError, "email"):
            tasks.request_shared_audit(s, rb["id"], "C2", "m", DEB, "A",
                                       "P", channel="phone")
        with self.assertRaises(ValueError):
            tasks.request_shared_audit(s, rb["id"], "C2", "  ", DEB, "A", "P")
        tasks.request_shared_audit(s, rb["id"], "C2", "m", DEB, "A", "P")
        with self.assertRaisesRegex(ValueError, "already links"):
            tasks.request_shared_audit(s, rb["id"], "C2", "m2", DEB, "A", "P")


class TestAuditConclusion(unittest.TestCase):
    def _audit(self):
        s = _store()
        s.seed_case(Case("C2", "P", "F-2",
                         (LineItem(1, "PR", "new motive", 20000, 0),), 20000))
        rb = _rebilled(s)
        tasks.record_recognition(s, rb["id"], "financier_credit_note",
                                 10000, "NC-1", "P", DEB, "2026-09-20")
        au = tasks.request_shared_audit(s, rb["id"], "C2", "rest re-debited",
                                        DEB, "auto-test-auditor", "staff")
        return s, au

    def test_rebill_conclusion(self):
        s, au = self._audit()
        c = tasks.conclude_shared_audit(s, au["id"], DEB, "rebill", 12000)
        self.assertEqual(c["rebill_cents"], 12000)
        self.assertEqual(c["disputed_cents"], 20000)
        got = [a for a in s.list_shared_audits("C1")
               if a["id"] == au["id"]][0]["conclusion"]
        self.assertEqual(got["outcome"], "rebill")
        self.assertIn("audit_conclusion", [h[1] for h in s.history("C1")])
        self.assertIn("audit_conclusion", [h[1] for h in s.history("C2")])

    def test_accept_conclusion(self):
        s, au = self._audit()
        c = tasks.conclude_shared_audit(s, au["id"], DEB, "accept")
        self.assertEqual(c["outcome"], "accept")
        self.assertIsNone(c["rebill_cents"])

    def test_conclusion_guards(self):
        s, au = self._audit()
        with self.assertRaises(KeyError):
            tasks.conclude_shared_audit(s, "SA-99", DEB, "accept")
        with self.assertRaises(ValueError):
            tasks.conclude_shared_audit(s, au["id"], DEB, "split")
        with self.assertRaises(ValueError):
            tasks.conclude_shared_audit(s, au["id"], "  ", "accept")
        for bad in (None, 0, -100, 20001, 30000):
            with self.assertRaises(ValueError):
                tasks.conclude_shared_audit(s, au["id"], DEB, "rebill", bad)
        tasks.conclude_shared_audit(s, au["id"], DEB, "rebill", 12000)
        with self.assertRaisesRegex(ValueError, "already concluded"):
            tasks.conclude_shared_audit(s, au["id"], DEB, "accept")
