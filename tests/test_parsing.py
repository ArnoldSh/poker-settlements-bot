from __future__ import annotations

import unittest
from decimal import Decimal

from poker_bot.parsing import parse_line


class ParseLineTests(unittest.TestCase):
    def test_single_amount_sets_zero_out(self) -> None:
        self.assertEqual(parse_line("ivan 100"), ("@ivan", Decimal("100.00"), Decimal("0.00")))

    def test_comma_splits_buyin_and_out(self) -> None:
        self.assertEqual(parse_line("@ivan 100, 20"), ("@ivan", Decimal("100.00"), Decimal("20.00")))

    def test_sum_expression_is_supported(self) -> None:
        self.assertEqual(parse_line("ivan 10+20+20"), ("@ivan", Decimal("50.00"), Decimal("0.00")))

    def test_sum_expression_with_explicit_out_is_supported(self) -> None:
        self.assertEqual(parse_line("ivan 10+20+20, 5"), ("@ivan", Decimal("50.00"), Decimal("5.00")))

    def test_legacy_space_syntax_is_still_supported(self) -> None:
        self.assertEqual(parse_line("ivan 100 20"), ("@ivan", Decimal("100.00"), Decimal("20.00")))

    def test_legacy_arrow_syntax_is_still_supported(self) -> None:
        self.assertEqual(parse_line("@ivan 100 -> 20"), ("@ivan", Decimal("100.00"), Decimal("20.00")))


if __name__ == "__main__":
    unittest.main()

