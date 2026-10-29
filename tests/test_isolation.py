import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestIsolation(unittest.TestCase):
    def test_no_private_imports(self):
        root = Path(__file__).resolve().parent.parent
        for py in list((root / "debit_ai").glob("*.py")) + list((root / "tools").glob("*.py")):
            txt = py.read_text(encoding="utf-8")
            self.assertNotIn("pmc_validator", txt, py.name)
            self.assertNotIn("from sistema", txt, py.name)
            self.assertNotIn("import sistema", txt, py.name)

    def test_synthetic_names(self):
        from debit_ai.synthetic import PAYERS
        for f in PAYERS:
            self.assertIn("FICTICI", f)

    def test_adapter_disabled(self):
        import os
        os.environ.pop("IA_DEMO_MODE", None)
        import importlib, debit_ai.real_adapter as ar
        importlib.reload(ar)
        self.assertFalse(ar.ACTIVE)


if __name__ == "__main__":
    unittest.main()
