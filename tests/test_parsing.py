from __future__ import annotations

import unittest
from decimal import Decimal

from poker_bot.parsing import normalize_name, parse_line, parse_line_with_buyin_entries, parse_number_only


class ParseLineTests(unittest.TestCase):
    def test_single_amount_sets_zero_out(self) -> None:
        self.assertEqual(parse_line("ivan 100"), ("@ivan", Decimal("100.00"), Decimal("0.00")))

    def test_comma_splits_buyin_and_out(self) -> None:
        self.assertEqual(parse_line("@ivan 100, 20"), ("@ivan", Decimal("100.00"), Decimal("20.00")))

    def test_sum_expression_is_supported(self) -> None:
        self.assertEqual(parse_line("ivan 10+20+20"), ("@ivan", Decimal("50.00"), Decimal("0.00")))

    def test_sum_expression_with_explicit_out_is_supported(self) -> None:
        self.assertEqual(parse_line("ivan 10+20+20, 5"), ("@ivan", Decimal("50.00"), Decimal("5.00")))

    def test_sum_expression_preserves_buyin_entries(self) -> None:
        self.assertEqual(
            parse_line_with_buyin_entries("ivan 20+20, 10"),
            ("@ivan", Decimal("40.00"), Decimal("10.00"), [Decimal("20.00"), Decimal("20.00")]),
        )

    def test_legacy_space_syntax_is_still_supported(self) -> None:
        self.assertEqual(parse_line("ivan 100 20"), ("@ivan", Decimal("100.00"), Decimal("20.00")))

    def test_legacy_arrow_syntax_is_still_supported(self) -> None:
        self.assertEqual(parse_line("@ivan 100 -> 20"), ("@ivan", Decimal("100.00"), Decimal("20.00")))

    def test_name_is_normalized_to_tag(self) -> None:
        self.assertEqual(normalize_name("ivan_123"), "@ivan_123")

    def test_name_rejects_non_tag_characters(self) -> None:
        with self.assertRaises(ValueError):
            normalize_name("@ivan-poker")

    def test_name_rejects_more_than_64_characters(self) -> None:
        with self.assertRaises(ValueError):
            normalize_name("@" + "a" * 64)

    def test_number_only_accepts_dot_and_comma_decimal_separators(self) -> None:
        self.assertEqual(parse_number_only("10.5"), Decimal("10.50"))
        self.assertEqual(parse_number_only("10,5"), Decimal("10.50"))

    def test_number_only_rejects_mixed_text(self) -> None:
        self.assertIsNone(parse_number_only("ivan 10"))


if __name__ == "__main__":
    unittest.main()
