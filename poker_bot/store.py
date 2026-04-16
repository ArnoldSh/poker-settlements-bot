from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from poker_bot.domain import Game
from poker_bot.models import ChatGameModel, GamePlayerModel


class DatabaseStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get(self, chat_id: int) -> Game:
        with self.session_factory() as session:
            game_row = session.scalar(select(ChatGameModel).where(ChatGameModel.chat_id == chat_id))
            game = Game()
            if game_row is None:
                return game

            for player_row in game_row.players:
                game.add_or_update(
                    player_row.player_name,
                    Decimal(str(player_row.buyin)),
                    Decimal(str(player_row.out)),
                )
            return game

    def save(self, chat_id: int, game: Game, created_by_telegram_user_id: int | None = None) -> None:
        with self.session_factory.begin() as session:
            game_row = session.scalar(select(ChatGameModel).where(ChatGameModel.chat_id == chat_id))
            if game_row is None:
                game_row = ChatGameModel(
                    chat_id=chat_id,
                    created_by_telegram_user_id=created_by_telegram_user_id,
                )
                session.add(game_row)
                session.flush()

            game_row.players.clear()
            session.flush()

            for player in game.players.values():
                game_row.players.append(
                    GamePlayerModel(
                        player_name=player.name,
                        buyin=float(player.buyin),
                        out=float(player.out),
                    )
                )

    def reset(self, chat_id: int, created_by_telegram_user_id: int | None = None) -> None:
        self.save(chat_id, Game(), created_by_telegram_user_id=created_by_telegram_user_id)

    def debug_chat_payload(self, chat_id: int) -> dict[str, object]:
        game = self.get(chat_id)
        return {
            "chat_id": chat_id,
            "players": [
                {
                    "name": player.name,
                    "buyin": str(player.buyin),
                    "out": str(player.out),
                    "net": str(player.net),
                }
                for player in sorted(game.players.values(), key=lambda item: item.name.lower())
            ],
            "totals": {
                "buyin": str(game.total_buyin),
                "out": str(game.total_out),
            },
        }
