import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.prepare_demo as prep
from debit_ai import approvals
from debit_ai.contracts import Proposal, RuleRef
from debit_ai.synthetic import SyntheticStore
from tools.backup_db import backup_database, content_fingerprint

ROOT = Path(__file__).resolve().parent.parent
LIVE_DB = ROOT / "demo_data" / "demo.db"
REVIEWER = "auto-test-protect"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(db: str) -> dict:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return content_fingerprint(con)
    finally:
        con.close()


def _seed(db: Path, gen: Path) -> SyntheticStore:
    prep.main(str(db), str(gen))
    return SyntheticStore(str(db))


def _add_records(s: SyntheticStore) -> str:
    pid = s.new_proposal_id("DEMO-F123")
    s.save_proposal("DEMO-F123", Proposal(
        pid, "DEMO-F123", "Agreements", RuleRef("Agreements", 4, ("x",)),
        "route_team", "e", ("r",)))
    approvals.review(s, pid, REVIEWER, "approved", "ok")
    approvals.followup(s, pid, "pending", 0, 0, "auto-test-owner")
    return pid


class _EnvGuard:
    def __init__(self, test):
        self.test = test
        self.had = "IA_DEMO_DB" in os.environ
        self.old = os.environ.get("IA_DEMO_DB")

    def set(self, value):
        os.environ["IA_DEMO_DB"] = value
        self.test.addCleanup(self.restore)

    def restore(self):
        if self.had:
            os.environ["IA_DEMO_DB"] = self.old
        else:
            os.environ.pop("IA_DEMO_DB", None)


class TestDestinationRequired(unittest.TestCase):
    def test_cli_without_destination_fails_and_changes_nothing(self):
        before = _sha(LIVE_DB)
        files_before = sorted(p.name for p in (ROOT / "demo_data").glob("*"))
        env = {k: v for k, v in os.environ.items() if k != "IA_DEMO_DB"}
        r = subprocess.run([sys.executable, "-B", "tools/prepare_demo.py"],
                           cwd=str(ROOT), env=env, capture_output=True,
                           text=True, timeout=60)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("explicit destination", r.stderr)
        self.assertEqual(_sha(LIVE_DB), before)
        files_after = sorted(p.name for p in (ROOT / "demo_data").glob("*"))
        self.assertEqual(files_after, files_before)

    def test_library_without_destination_raises(self):
        g = _EnvGuard(self)
        os.environ.pop("IA_DEMO_DB", None)
        g.had, g.old = False, None
        self.addCleanup(g.restore)
        with self.assertRaises(ValueError):
            prep.main(None, tempfile.mkdtemp())


class TestExistingPreserved(unittest.TestCase):
    def test_existing_destination_fails_and_keeps_records(self):
        tmp = Path(tempfile.mkdtemp())
        db, gen = tmp / "demo.db", tmp / "generated"
        s = _seed(db, gen)
        pid = _add_records(s)
        want = _fingerprint(str(db))
        with self.assertRaises(FileExistsError):
            prep.main(str(db), str(tmp / "generated2"))
        self.assertTrue(db.is_file())
        self.assertEqual(_fingerprint(str(db)), want)
        s2 = SyntheticStore(str(db))
        self.assertIsNotNone(s2.get_proposal(pid))
        self.assertTrue(approvals.has_approved_review(s2, pid))
        self.assertIsNotNone(s2.get_followup(pid))


class TestActiveDbProtected(unittest.TestCase):
    def test_active_db_refuses_ordinary_and_unconfirmed_replace(self):
        tmp = Path(tempfile.mkdtemp())
        db, gen = tmp / "demo.db", tmp / "generated"
        s = _seed(db, gen)
        pid = _add_records(s)
        want = _fingerprint(str(db))
        _EnvGuard(self).set(str(db))  # this scratch DB is now "active"
        with self.assertRaises(FileExistsError):
            prep.main(str(db), str(gen))
        with self.assertRaises(PermissionError):
            prep.main(str(db), str(gen), replace=True,
                      backup_to=str(tmp / "b.db"))
        with self.assertRaises(ValueError):
            prep.main(str(db), str(gen), replace=True,
                      backup_to=None, confirm_active=True)
        self.assertEqual(_fingerprint(str(db)), want)
        s2 = SyntheticStore(str(db))
        self.assertTrue(approvals.has_approved_review(s2, pid))

    def test_confirmed_replace_keeps_verified_backup(self):
        tmp = Path(tempfile.mkdtemp())
        db, gen = tmp / "demo.db", tmp / "generated"
        s = _seed(db, gen)
        pid = _add_records(s)
        want = _fingerprint(str(db))
        _EnvGuard(self).set(str(db))
        bak = tmp / "backups" / "pre-replace.db"
        summary = prep.main(str(db), str(gen), replace=True,
                            backup_to=str(bak), confirm_active=True)
        self.assertEqual(summary["backup"], str(bak))
        self.assertEqual(_fingerprint(str(bak)), want)
        fresh = SyntheticStore(str(db))
        self.assertIsNone(fresh.get_proposal(pid))
        self.assertEqual(len(fresh.list_cases()), 8)

    def test_replace_refuses_existing_backup_target(self):
        tmp = Path(tempfile.mkdtemp())
        db, gen = tmp / "demo.db", tmp / "generated"
        s = _seed(db, gen)
        _add_records(s)
        want = _fingerprint(str(db))
        clash = tmp / "clash.db"
        clash.write_bytes(b"previous backup, must survive")
        with self.assertRaises(FileExistsError):
            prep.main(str(db), str(gen), replace=True,
                      backup_to=str(clash), confirm_active=True)
        self.assertEqual(clash.read_bytes(), b"previous backup, must survive")
        self.assertEqual(_fingerprint(str(db)), want)


class TestFreshPrepare(unittest.TestCase):
    def test_fresh_prepare_on_separate_path_leaves_live_db(self):
        before = _sha(LIVE_DB)
        tmp = Path(tempfile.mkdtemp())
        summary = prep.main(str(tmp / "demo.db"), str(tmp / "generated"))
        self.assertEqual(summary["cases"], 8)
        self.assertEqual(summary["main_case"], "EXP-900")
        self.assertEqual(_sha(LIVE_DB), before)


class TestBackupRoundtrip(unittest.TestCase):
    def test_backup_restores_proposals_reviews_history(self):
        tmp = Path(tempfile.mkdtemp())
        db = tmp / "demo.db"
        s = _seed(db, tmp / "generated")
        pid = _add_records(s)
        bak = tmp / "backups" / "snap.db"
        rep = backup_database(str(db), str(bak))
        self.assertTrue(rep["valid"])
        self.assertEqual(rep["integrity"], "ok")
        self.assertEqual(rep["restore_test"], "ok")
        restored = tmp / "restored.db"
        src_con = sqlite3.connect(f"file:{bak}?mode=ro", uri=True)
        dst_con = sqlite3.connect(str(restored))
        try:
            src_con.backup(dst_con)
        finally:
            dst_con.close()
            src_con.close()
        self.assertEqual(_fingerprint(str(restored)), _fingerprint(str(db)))
        r = SyntheticStore(str(restored))
        self.assertIsNotNone(r.get_proposal(pid))
        self.assertTrue(approvals.has_approved_review(r, pid))
        self.assertIsNotNone(r.get_followup(pid))
        rev = [h for h in r.history("DEMO-F123") if h[1] == "review"][0]
        self.assertIn(REVIEWER, rev[4])

    def test_backup_refuses_existing_target(self):
        tmp = Path(tempfile.mkdtemp())
        db = tmp / "demo.db"
        _seed(db, tmp / "generated")
        bak = tmp / "snap.db"
        rep = backup_database(str(db), str(bak))
        self.assertTrue(rep["valid"])
        with self.assertRaises(FileExistsError):
            backup_database(str(db), str(bak))


if __name__ == "__main__":
    unittest.main()
