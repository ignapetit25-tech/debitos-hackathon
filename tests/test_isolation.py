import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestIsolation(unittest.TestCase):
    def test_sin_imports_privados(self):
        root = Path(__file__).resolve().parent.parent
        for py in list((root / "ia_debitos").glob("*.py")) + list((root / "tools").glob("*.py")):
            txt = py.read_text(encoding="utf-8")
            self.assertNotIn("pmc_validator", txt, py.name)
            self.assertNotIn("from sistema", txt, py.name)
            self.assertNotIn("import sistema", txt, py.name)

    def test_nombres_sinteticos(self):
        from ia_debitos.synthetic import FINANCIADORES
        for f in FINANCIADORES:
            self.assertIn("FICTICI", f)

    def test_adaptador_desactivado(self):
        import os
        os.environ.pop("IA_DEMO_MODE", None)
        import importlib, ia_debitos.adapter_real as ar
        importlib.reload(ar)
        self.assertFalse(ar.ACTIVO)


if __name__ == "__main__":
    unittest.main()
