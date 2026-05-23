from __future__ import annotations

import importlib.util
import unittest
from decimal import Decimal

from poker_bot.history_import import parse_history_dump, parse_import_command_request

DEPENDENCIES_AVAILABLE = importlib.util.find_spec("sqlalchemy") is not None

if DEPENDENCIES_AVAILABLE:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from poker_bot.history_import import import_games
    from poker_bot.models import Base, ChatGameModel


SAMPLE_TEXT = """
[23.05.2026 11:10]
РРіСЂРѕРє | Р’С…РѕРґ | Р’С‹С…РѕРґ | РС‚РѕРі
------------------------------
@BugMiner | 100,00 в‚¬ | 133,50 в‚¬ | 33,50 в‚¬
@rudakovable | 120,00 в‚¬ | 122,80 в‚¬ | 2,80 в‚¬
------------------------------
ОЈ | 220,00 в‚¬ | 256,30 в‚¬ | 36,30 в‚¬
"""


class HistoryImportParsingTests(unittest.TestCase):
    def test_parses_command_arguments(self) -> None:
        request = parse_import_command_request(
            '--alias @rudakovable=@kllrrr --date-fix "233.05.2026 11:10=23.05.2026 11:10" --dry-run',
            """
[23.05.2026 11:10]
@BugMiner | 100,00 в‚¬ | 133,50 в‚¬ | 33,50 в‚¬
""",
        )

        self.assertTrue(request.dry_run)
        self.assertIsNone(request.chat_id)
        self.assertEqual(request.alias_map, {"@rudakovable": "@kllrrr"})
        self.assertEqual(request.date_fixes, {"233.05.2026 11:10": "23.05.2026 11:10"})
        self.assertIn("[23.05.2026 11:10]", request.history_text)

    def test_parses_chat_id_argument(self) -> None:
        request = parse_import_command_request(
            "--chat-id -100123 --alias @a=@b",
            "[23.05.2026 11:10]\n@a | 1,00 в‚¬ | 1,00 в‚¬ | 0,00 в‚¬",
        )

        self.assertEqual(request.chat_id, -100123)
        self.assertEqual(request.alias_map, {"@a": "@b"})

    def test_parses_game_block_and_applies_aliases(self) -> None:
        games = parse_history_dump(
            SAMPLE_TEXT,
            alias_map={"@rudakovable": "@kllrrr"},
            tz_name="Asia/Nicosia",
        )

        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].source_date_text, "23.05.2026 11:10")
        self.assertEqual(games[0].players[0].player_name, "@BugMiner")
        self.assertEqual(games[0].players[0].buyin, Decimal("100.00"))
        self.assertEqual(games[0].players[1].player_name, "@kllrrr")
        self.assertEqual(games[0].players[1].out, Decimal("122.80"))

    def test_invalid_date_requires_explicit_fix(self) -> None:
        with self.assertRaises(ValueError):
            parse_history_dump("[233.05.2026 11:10]\nРРіСЂРѕРє | Р’С…РѕРґ | Р’С‹С…РѕРґ | РС‚РѕРі\n@a | 1,00 в‚¬ | 1,00 в‚¬ | 0,00 в‚¬")

    def test_rejects_unknown_option(self) -> None:
        with self.assertRaises(ValueError):
            parse_import_command_request(
                "--wat",
                """
[23.05.2026 11:10]
@a | 1,00 в‚¬ | 1,00 в‚¬ | 0,00 в‚¬
""",
            )


@unittest.skipUnless(DEPENDENCIES_AVAILABLE, "sqlalchemy dependency is not installed in this environment")
class HistoryImportDatabaseTests(unittest.TestCase):
    def test_imports_closed_games(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)

        games = parse_history_dump(SAMPLE_TEXT, alias_map={"@rudakovable": "@kllrrr"})
        imported, skipped = import_games(session_factory, chat_id=-100, games=games)

        self.assertEqual(imported, 1)
        self.assertEqual(skipped, 0)

        with session_factory() as session:
            rows = session.scalars(select(ChatGameModel)).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].status, "closed")
            self.assertEqual(len(rows[0].players), 2)
            self.assertEqual(rows[0].players[1].player_name, "@kllrrr")


if __name__ == "__main__":
    unittest.main()
