import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from debit_ai.money import (check_sum, format_money, format_money_us,
                              parse_amount)


class TestMoney(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_amount("$57.000"), 5700000)
        self.assertEqual(parse_amount("1.749.497,80"), 174949780)
        self.assertEqual(parse_amount("$0"), 0)

    def test_parse_invalid(self):
        for bad in ("abc", "$", "12.34.56", "", "1,234"):
            with self.assertRaises(ValueError, msg=bad):
                parse_amount(bad)

    def test_format_roundtrip(self):
        self.assertEqual(format_money(5700000), "$57.000,00")
        for cents in (0, 1, 99, 100, 174949780):
            self.assertEqual(parse_amount(format_money(cents)), cents)

    def test_format_us(self):
        self.assertEqual(format_money_us(5700000), "$57,000.00")
        self.assertEqual(format_money_us(0), "$0.00")
        self.assertEqual(format_money_us(-650000), "-$6,500.00")
        with self.assertRaises(ValueError):
            format_money_us(1.5)

    def test_exact_sum(self):
        self.assertEqual(check_sum([3200000, 2500000], 5700000), (True, 0))
        ok, dif = check_sum([3200000, 2500000], 5700001)
        self.assertEqual((ok, dif), (False, -1))


if __name__ == "__main__":
    unittest.main()
