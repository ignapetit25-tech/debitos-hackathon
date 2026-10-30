import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai.demo_app import load_dotenv
from debit_ai.synthetic import SyntheticStore


class TestDotenv(unittest.TestCase):
    def test_parsing_and_setdefault(self):
        p = Path(tempfile.mkdtemp()) / ".env"
        p.write_text("# comment\n\nA=1\nB=\"x y\"\nC=\nBADLINE\nA=2\n",
                     encoding="utf-8")
        for k in ("TSET_A", "TSET_B", "TSET_C"):
            os.environ.pop(k, None)
        q = Path(tempfile.mkdtemp()) / ".env"
        q.write_text("TSET_A=1\nTSET_B='v'\nTSET_C=\n", encoding="utf-8")
        self.assertEqual(load_dotenv(q), 3)
        self.assertEqual(os.environ["TSET_A"], "1")
        self.assertEqual(os.environ["TSET_B"], "v")
        self.assertEqual(os.environ["TSET_C"], "")
        os.environ["TSET_A"] = "keep"
        os.environ.pop("TSET_B", None)
        os.environ.pop("TSET_C", None)
        self.assertEqual(load_dotenv(q), 2)  # explicit env wins
        self.assertEqual(os.environ["TSET_A"], "keep")
        for k in ("TSET_A", "TSET_B", "TSET_C"):
            os.environ.pop(k, None)

    def test_missing_file_is_zero(self):
        self.assertEqual(load_dotenv(Path(tempfile.mkdtemp()) / "nope"), 0)


class TestPrepare(unittest.TestCase):
    def test_full_demo_on_scratch_dirs(self):
        import tools.prepare_demo as prep
        tmp = Path(tempfile.mkdtemp())
        db, gen = tmp / "demo.db", tmp / "generated"
        summary = prep.main(str(db), str(gen))
        self.assertEqual(summary["cases"], 8)
        self.assertEqual(summary["main_case"], "EXP-900")
        self.assertEqual(summary["documents"], 3)
        s = SyntheticStore(str(db))
        ids = sorted(c.id for c in s.list_cases())
        self.assertEqual(len(ids), 8)
        self.assertIn("EXP-900", ids)
        exp = s.get_case("EXP-900")
        self.assertEqual(exp.service_date, "2026-08-10")
        roles = sorted(d["role"] for d in s.documents("EXP-900"))
        self.assertEqual(roles, ["agreement", "invoice", "settlement"])
        self.assertEqual(s.get_case("DEMO-DOCFALTA").service_date, "")
        dated = [c for c in s.list_cases() if c.service_date]
        self.assertEqual(len(dated), 7)
        self.assertTrue((gen / "expected.json").exists())
        self.assertTrue((gen / "EXP-900-invoice.pdf").exists())

    def test_rejects_non_db_target(self):
        import tools.prepare_demo as prep
        with self.assertRaises(ValueError):
            prep.main("/tmp/x.txt", tempfile.mkdtemp())


if __name__ == "__main__":
    unittest.main()


class TestMigration(unittest.TestCase):
    def test_old_documents_table_gains_pages(self):
        import sqlite3
        db = Path(tempfile.mkdtemp()) / "old.db"
        con = sqlite3.connect(str(db))
        con.execute("CREATE TABLE documents (case_id TEXT, role TEXT,"
                    " filename TEXT, pages INTEGER, text TEXT,"
                    " PRIMARY KEY (case_id, role))")
        con.execute("INSERT INTO documents VALUES (?,?,?,?,?)",
                    ("C1", "agreement", "c.pdf", 1, "SOME RATE TEXT HERE"))
        con.commit()
        con.close()
        s = SyntheticStore(str(db))
        docs = s.documents("C1")
        self.assertEqual(docs[0]["page_texts"], ["SOME RATE TEXT HERE"])
