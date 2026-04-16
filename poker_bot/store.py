from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from poker_bot.domain import Game
from poker_bot.models import ChatGameModel, GamePlayerModel


@dataclass
class GameSession:
    id: int
    chat_id: int
    status: str
    game: Game
    created_by_telegram_user_id: int | None = None
    finalized_by_telegram_user_id: int | None = None
    finalized_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.status == "open"

    @property
    def is_closed(self) -> bool:
        return self.status == "closed"


class DatabaseStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get_latest(self, chat_id: int) -> GameSession | None:
        with self.session_factory() as session:
            game_row = session.scalar(
                select(ChatGameModel)
                .where(ChatGameModel.chat_id == chat_id)
                .order_by(ChatGameModel.id.desc())
            )
            if game_row is None:
                return None
            return self._to_session(game_row)

    def start_new_game(self, chat_id: int, created_by_telegram_user_id: int | None = None) -> GameSession:
        with self.session_factory.begin() as session:
            session.execute(
                delete(ChatGameModel).where(
                    ChatGameModel.chat_id == chat_id,
                    ChatGameModel.status == "open",
                )
            )
            game_row = ChatGameModel(
                chat_id=chat_id,
                status="open",
                created_by_telegram_user_id=created_by_telegram_user_id,
            )
            session.add(game_row)
            session.flush()
            session.refresh(game_row)
            return self._to_session(game_row)

    def save_players(self, session_id: int, game: Game) -> None:
        with self.session_factory.begin() as session:
            game_row = session.get(ChatGameModel, session_id)
            if game_row is None:
                raise ValueError("Game session not found.")

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

    def complete_game(self, session_id: int, finalized_by_telegram_user_id: int | None) -> GameSession:
        with self.session_factory.begin() as session:
            game_row = session.get(ChatGameModel, session_id)
            if game_row is None:
                raise ValueError("Game session not found.")

            game_row.status = "closed"
            game_row.finalized_by_telegram_user_id = finalized_by_telegram_user_id
            game_row.finalized_at = datetime.now(timezone.utc)
            session.flush()
            session.refresh(game_row)
            return self._to_session(game_row)

    def count_finalized_games_for_chat(self, chat_id: int) -> int:
        with self.session_factory() as session:
            return int(
                session.scalar(
                    select(func.count(ChatGameModel.id)).where(
                        ChatGameModel.chat_id == chat_id,
                        ChatGameModel.status == "closed",
                    )
                )
                or 0
            )

    def count_finalized_games_for_user_in_period(
        self,
        telegram_user_id: int,
        period_start: datetime | None,
        period_end: datetime | None,
    ) -> int:
        if period_start is None or period_end is None:
            return 0

        with self.session_factory() as session:
            return int(
                session.scalar(
                    select(func.count(ChatGameModel.id)).where(
                        ChatGameModel.status == "closed",
                        ChatGameModel.finalized_by_telegram_user_id == telegram_user_id,
                        ChatGameModel.finalized_at >= period_start,
                        ChatGameModel.finalized_at <= period_end,
                    )
                )
                or 0
            )

    @staticmethod
    def _to_session(game_row: ChatGameModel) -> GameSession:
        game = Game()
        for player_row in game_row.players:
            game.add_or_update(
                player_row.player_name,
                Decimal(str(player_row.buyin)),
                Decimal(str(player_row.out)),
            )
        return GameSession(
            id=game_row.id,
            chat_id=game_row.chat_id,
            status=game_row.status,
            game=game,
            created_by_telegram_user_id=game_row.created_by_telegram_user_id,
            finalized_by_telegram_user_id=game_row.finalized_by_telegram_user_id,
            finalized_at=game_row.finalized_at,
        )
