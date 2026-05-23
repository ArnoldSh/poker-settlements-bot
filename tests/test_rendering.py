from __future__ import annotations

import importlib.util
import unittest
from decimal import Decimal

DEPENDENCIES_AVAILABLE = importlib.util.find_spec("sqlalchemy") is not None

if DEPENDENCIES_AVAILABLE:
    from poker_bot.rendering import render_stats, render_stats_basic
    from poker_bot.store import PlayerStatsEntry


@unittest.skipUnless(DEPENDENCIES_AVAILABLE, "sqlalchemy dependency is not installed in this environment")
class RenderingStatsTests(unittest.TestCase):
    def test_render_stats_uses_multiline_cards(self) -> None:
        text = render_stats(
            [
                PlayerStatsEntry(
                    player_name="@leeroy_pk",
                    games_played=5,
                    total_net=Decimal("74.00"),
                    average_net=Decimal("14.80"),
                    wins=3,
                    losses=2,
                )
            ]
        )

        self.assertIn("<b>Статистика по чату</b>", text)
        self.assertIn("<b>1. @leeroy_pk</b>", text)
        self.assertIn("+ 74,00", text)
        self.assertIn("Игры: 5 | Средний итог: 14,80", text)
        self.assertIn("Плюсовых: 3 | Минусовых: 2", text)

    def test_render_stats_basic_is_more_compact(self) -> None:
        text = render_stats_basic(
            [
                PlayerStatsEntry(
                    player_name="@naydaan",
                    games_played=4,
                    total_net=Decimal("-22.30"),
                    average_net=Decimal("-5.58"),
                    wins=1,
                    losses=3,
                )
            ]
        )

        self.assertIn("<b>Короткая статистика</b>", text)
        self.assertIn("• <b>@naydaan</b> - 22,30", text)
        self.assertIn("| игр: 4", text)


if __name__ == "__main__":
    unittest.main()
