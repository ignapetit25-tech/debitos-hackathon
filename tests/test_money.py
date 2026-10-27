import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ia_debitos.money import parse_importe, formato, validar_suma


class TestMoney(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_importe("$57.000"), 5700000)
        self.assertEqual(parse_importe("1.749.497,80"), 174949780)
        self.assertEqual(parse_importe("$0"), 0)

    def test_parse_invalido(self):
        for malo in ("abc", "$", "12.34.56", "", "1,234"):
            with self.assertRaises(ValueError, msg=malo):
                parse_importe(malo)

    def test_formato_redondo(self):
        self.assertEqual(formato(5700000), "$57.000,00")
        for cents in (0, 1, 99, 100, 174949780):
            self.assertEqual(parse_importe(formato(cents)), cents)

    def test_suma_exacta(self):
        self.assertEqual(validar_suma([3200000, 2500000], 5700000), (True, 0))
        ok, dif = validar_suma([3200000, 2500000], 5700001)
        self.assertEqual((ok, dif), (False, -1))


if __name__ == "__main__":
    unittest.main()
