from __future__ import annotations

import importlib.util
import unittest
from decimal import Decimal

DEPENDENCIES_AVAILABLE = importlib.util.find_spec("sqlalchemy") is not None

if DEPENDENCIES_AVAILABLE:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from poker_bot.domain import Game
    from poker_bot.models import Base, GameBuyinEntryModel
    from poker_bot.store import DatabaseStore


@unittest.skipUnless(DEPENDENCIES_AVAILABLE, "sqlalchemy dependency is not installed in this environment")
class ManualEntryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine)
        self.store = DatabaseStore(self.session_factory)
        self.session = self.store.start_new_game(chat_id=-100, created_by_telegram_user_id=42)

    def test_atomic_buyins_append_entries_and_keep_corrections(self) -> None:
        game = Game()
        game.add_or_update("@ivan", Decimal("20"), Decimal("0"))
        self.store.save_players_and_add_manual_buyin(self.session.id, game, "@ivan", Decimal("20"))

        game.add_or_update("@ivan", Decimal("35"), Decimal("0"))
        self.store.save_players_and_add_manual_buyin(self.session.id, game, "@ivan", Decimal("15"))

        game.add_or_update("@ivan", Decimal("30"), Decimal("0"))
        self.store.save_players_and_add_manual_buyin(self.session.id, game, "@ivan", Decimal("-5"))

        latest = self.store.get_latest(-100)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.game.players["@ivan"].buyin, Decimal("30.00"))

        with self.session_factory() as db:
            rows = db.scalars(
                select(GameBuyinEntryModel).order_by(GameBuyinEntryModel.id.asc())
            ).all()
        self.assertEqual([Decimal(str(row.amount)) for row in rows], [Decimal("20.00"), Decimal("15.00"), Decimal("-5.00")])
        self.assertEqual([row.source for row in rows], ["manual", "manual", "manual_adjustment"])

    def test_manual_block_replaces_previous_entries_for_player(self) -> None:
        game = Game()
        game.add_or_update("@ivan", Decimal("20"), Decimal("0"))
        self.store.save_players_and_add_manual_buyin(self.session.id, game, "@ivan", Decimal("20"))

        game.add_or_update("@ivan", Decimal("50"), Decimal("10"))
        self.store.save_players_and_manual_buyins(self.session.id, game, {"@ivan": [Decimal("30"), Decimal("20")]})

        latest = self.store.get_latest(-100)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.game.players["@ivan"].buyin, Decimal("50.00"))
        self.assertEqual(latest.game.players["@ivan"].out, Decimal("10.00"))

        with self.session_factory() as db:
            rows = db.scalars(
                select(GameBuyinEntryModel).order_by(GameBuyinEntryModel.id.asc())
            ).all()
        self.assertEqual([Decimal(str(row.amount)) for row in rows], [Decimal("30.00"), Decimal("20.00")])


if __name__ == "__main__":
    unittest.main()
