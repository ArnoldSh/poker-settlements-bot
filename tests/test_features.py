from __future__ import annotations

import unittest

from poker_bot.features import FeatureFlags, parse_feature_list


class FeatureFlagTests(unittest.TestCase):
    def test_parse_feature_list_normalizes_items(self) -> None:
        self.assertEqual(
            parse_feature_list("revanche, savegroup, analyze, export-csv"),
            frozenset({"revanche", "savegroup", "analyze", "export_csv"}),
        )

    def test_parse_feature_list_uses_commas_as_separators(self) -> None:
        self.assertEqual(parse_feature_list("groups, analyze"), frozenset({"groups", "analyze"}))

    def test_only_listed_features_are_enabled(self) -> None:
        flags = FeatureFlags(enabled_features=frozenset({"history"}))

        self.assertTrue(flags.is_enabled("history"))
        self.assertFalse(flags.is_enabled("revanche"))


if __name__ == "__main__":
    unittest.main()
