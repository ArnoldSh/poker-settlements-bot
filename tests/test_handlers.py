from __future__ import annotations

import unittest

from poker_bot.subscription_plans import parse_limit_boost_code, parse_plan_code


class PlanCodeParsingTests(unittest.TestCase):
    def test_short_plan_aliases_are_supported(self) -> None:
        self.assertEqual(parse_plan_code(["1m"]), "monthly")
        self.assertEqual(parse_plan_code(["3m"]), "quarterly")
        self.assertEqual(parse_plan_code(["6m"]), "semiannual")
        self.assertEqual(parse_plan_code(["1y"]), "yearly")

    def test_plan_aliases_are_case_insensitive(self) -> None:
        self.assertEqual(parse_plan_code(["1Y"]), "yearly")
        self.assertEqual(parse_plan_code(["Monthly"]), "monthly")

    def test_ambiguous_plan_aliases_are_not_supported(self) -> None:
        self.assertIsNone(parse_plan_code(["y"]))
        self.assertIsNone(parse_plan_code(["year"]))
        self.assertIsNone(parse_plan_code(["annual"]))


class LimitBoostCodeParsingTests(unittest.TestCase):
    def test_short_boost_aliases_are_supported(self) -> None:
        self.assertEqual(parse_limit_boost_code(["1m"]), "boost_30d")
        self.assertEqual(parse_limit_boost_code(["3m"]), "boost_90d")
        self.assertEqual(parse_limit_boost_code(["6m"]), "boost_180d")
        self.assertEqual(parse_limit_boost_code(["1y"]), "boost_365d")

    def test_boost_aliases_are_case_insensitive(self) -> None:
        self.assertEqual(parse_limit_boost_code(["1Y"]), "boost_365d")
        self.assertEqual(parse_limit_boost_code(["boost_30d"]), "boost_30d")


if __name__ == "__main__":
    unittest.main()
