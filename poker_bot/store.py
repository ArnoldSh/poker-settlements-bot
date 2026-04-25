from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from poker_bot.domain import Game
from poker_bot.models import (
    ChatGameModel,
    GameBuyinEntryModel,
    GamePlayerModel,
    InteractiveGameMessageModel,
    ProductMetricEventModel,
    SavedGroupMemberModel,
    SavedGroupModel,
)


@dataclass
class GameSession:
    id: int
    chat_id: int
    status: str
    input_mode: str
    interactive_phase: str | None
    game: Game
    created_by_telegram_user_id: int | None = None
    finalized_by_telegram_user_id: int | None = None
    finalized_at: datetime | None = None
    created_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.status == "open"

    @property
    def is_closed(self) -> bool:
        return self.status == "closed"

    @property
    def is_interactive(self) -> bool:
        return self.input_mode == "interactive"


@dataclass(frozen=True)
class SavedGroupSnapshot:
    id: int
    owner_telegram_user_id: int
    name: str
    player_names: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class GameHistoryEntry:
    id: int
    created_at: datetime
    finalized_at: datetime | None
    player_count: int
    total_pot: Decimal
    players: list[str]


@dataclass(frozen=True)
class PlayerStatsEntry:
    player_name: str
    games_played: int
    total_net: Decimal
    average_net: Decimal
    wins: int
    losses: int


@dataclass(frozen=True)
class GameAmountEntry:
    player_name: str
    phase: str
    amount: Decimal
    source: str
    raw_text: str | None = None


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

    def get_latest_closed(self, chat_id: int) -> GameSession | None:
        with self.session_factory() as session:
            game_row = session.scalar(
                select(ChatGameModel)
                .where(ChatGameModel.chat_id == chat_id, ChatGameModel.status == "closed")
                .order_by(ChatGameModel.id.desc())
            )
            if game_row is None:
                return None
            return self._to_session(game_row)

    def start_new_game(
        self,
        chat_id: int,
        created_by_telegram_user_id: int | None = None,
        player_names: list[str] | None = None,
        input_mode: str = "manual",
    ) -> GameSession:
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
                input_mode=input_mode,
                interactive_phase="buyin" if input_mode == "interactive" else None,
                created_by_telegram_user_id=created_by_telegram_user_id,
            )
            session.add(game_row)
            session.flush()

            for player_name in player_names or []:
                game_row.players.append(
                    GamePlayerModel(
                        player_name=player_name,
                        buyin=0,
                        out=0,
                    )
                )

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

    def save_interactive_message(
        self,
        session_id: int,
        chat_id: int,
        telegram_message_id: int,
        telegram_user_id: int | None,
        player_name: str,
        phase: str,
        amount: Decimal,
        raw_text: str,
    ) -> GameSession | None:
        with self.session_factory.begin() as session:
            game_row = session.get(ChatGameModel, session_id)
            if game_row is None or game_row.status != "open" or game_row.input_mode != "interactive":
                return None

            if phase == "out":
                message_row = session.scalar(
                    select(InteractiveGameMessageModel).where(
                        InteractiveGameMessageModel.game_id == session_id,
                        InteractiveGameMessageModel.player_name == player_name,
                        InteractiveGameMessageModel.phase == "out",
                    )
                )
            else:
                message_row = session.scalar(
                    select(InteractiveGameMessageModel).where(
                        InteractiveGameMessageModel.game_id == session_id,
                        InteractiveGameMessageModel.telegram_message_id == telegram_message_id,
                    )
                )
            if message_row is None:
                message_row = InteractiveGameMessageModel(
                    game_id=session_id,
                    chat_id=chat_id,
                    telegram_message_id=telegram_message_id,
                    telegram_user_id=telegram_user_id,
                    player_name=player_name,
                    phase=phase,
                    amount=float(amount),
                    raw_text=raw_text[:255],
                )
                session.add(message_row)
            else:
                message_row.telegram_message_id = telegram_message_id
                message_row.telegram_user_id = telegram_user_id
                message_row.player_name = player_name
                message_row.phase = phase
                message_row.amount = float(amount)
                message_row.raw_text = raw_text[:255]

            self._rebuild_interactive_players(session, game_row)
            session.flush()
            session.refresh(game_row)
            return self._to_session(game_row)

    def save_players_and_manual_buyins(
        self,
        session_id: int,
        game: Game,
        buyins_by_player: dict[str, list[Decimal]],
        source_message_id: int | None = None,
        raw_text_by_player: dict[str, str] | None = None,
    ) -> None:
        raw_text_by_player = raw_text_by_player or {}
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

            for player_name, buyins in buyins_by_player.items():
                session.execute(
                    delete(GameBuyinEntryModel).where(
                        GameBuyinEntryModel.game_id == session_id,
                        GameBuyinEntryModel.player_name == player_name,
                        GameBuyinEntryModel.source == "manual",
                    )
                )
                for amount in buyins:
                    session.add(
                        GameBuyinEntryModel(
                            game_id=session_id,
                            player_name=player_name,
                            amount=float(amount),
                            source="manual",
                            source_message_id=source_message_id,
                            raw_text=raw_text_by_player.get(player_name, "")[:255],
                        )
                    )

    def delete_manual_buyins_for_player(self, session_id: int, player_name: str) -> None:
        with self.session_factory.begin() as session:
            session.execute(
                delete(GameBuyinEntryModel).where(
                    GameBuyinEntryModel.game_id == session_id,
                    GameBuyinEntryModel.player_name == player_name,
                    GameBuyinEntryModel.source == "manual",
                )
            )

    def delete_manual_buyins_for_game(self, session_id: int) -> None:
        with self.session_factory.begin() as session:
            session.execute(
                delete(GameBuyinEntryModel).where(
                    GameBuyinEntryModel.game_id == session_id,
                    GameBuyinEntryModel.source == "manual",
                )
            )

    def finish_interactive_buyins(self, session_id: int) -> GameSession:
        with self.session_factory.begin() as session:
            game_row = session.get(ChatGameModel, session_id)
            if game_row is None:
                raise ValueError("Game session not found.")
            if game_row.input_mode != "interactive":
                raise ValueError("This game is not in interactive mode.")
            if game_row.interactive_phase != "buyin":
                raise ValueError("Interactive buy-ins are already finished.")

            game_row.interactive_phase = "out"
            session.flush()
            session.refresh(game_row)
            return self._to_session(game_row)

    def restart_interactive_flow(self, session_id: int) -> GameSession:
        with self.session_factory.begin() as session:
            game_row = session.get(ChatGameModel, session_id)
            if game_row is None:
                raise ValueError("Game session not found.")
            if game_row.input_mode != "interactive":
                raise ValueError("This game is not in interactive mode.")

            self._rebuild_interactive_players(session, game_row)
            session.flush()
            session.refresh(game_row)
            return self._to_session(game_row)

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

    def count_started_games_for_chat(self, chat_id: int) -> int:
        with self.session_factory() as session:
            return int(
                session.scalar(
                    select(func.count(ChatGameModel.id)).where(
                        ChatGameModel.chat_id == chat_id,
                    )
                )
                or 0
            )

    def count_trial_games_for_chat(self, chat_id: int, trial_period_end: datetime) -> int:
        with self.session_factory() as session:
            first_game_at = session.scalar(
                select(func.min(ChatGameModel.created_at)).where(ChatGameModel.chat_id == chat_id)
            )
            if first_game_at is None:
                return 0
            return int(
                session.scalar(
                    select(func.count(ChatGameModel.id)).where(
                        ChatGameModel.chat_id == chat_id,
                        ChatGameModel.created_at >= first_game_at,
                        ChatGameModel.created_at < trial_period_end,
                    )
                )
                or 0
            )

    def first_game_started_at_for_chat(self, chat_id: int) -> datetime | None:
        with self.session_factory() as session:
            return session.scalar(
                select(func.min(ChatGameModel.created_at)).where(ChatGameModel.chat_id == chat_id)
            )

    def count_started_games_for_user_in_period(
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
                        ChatGameModel.created_by_telegram_user_id == telegram_user_id,
                        ChatGameModel.created_at >= period_start,
                        ChatGameModel.created_at <= period_end,
                    )
                )
                or 0
            )

    def save_group(
        self,
        owner_telegram_user_id: int,
        name: str,
        player_names: list[str],
    ) -> SavedGroupSnapshot:
        with self.session_factory.begin() as session:
            group_row = session.scalar(
                select(SavedGroupModel).where(
                    SavedGroupModel.owner_telegram_user_id == owner_telegram_user_id,
                    SavedGroupModel.name == name,
                )
            )
            if group_row is None:
                group_row = SavedGroupModel(
                    owner_telegram_user_id=owner_telegram_user_id,
                    name=name,
                )
                session.add(group_row)
                session.flush()

            group_row.members.clear()
            session.flush()

            for player_name in player_names:
                group_row.members.append(SavedGroupMemberModel(player_name=player_name))

            session.flush()
            session.refresh(group_row)
            return self._to_saved_group_snapshot(group_row)

    def get_saved_group(self, owner_telegram_user_id: int, name: str) -> SavedGroupSnapshot | None:
        with self.session_factory() as session:
            group_row = session.scalar(
                select(SavedGroupModel).where(
                    SavedGroupModel.owner_telegram_user_id == owner_telegram_user_id,
                    SavedGroupModel.name == name,
                )
            )
            if group_row is None:
                return None
            return self._to_saved_group_snapshot(group_row)

    def list_saved_groups(self, owner_telegram_user_id: int) -> list[SavedGroupSnapshot]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(SavedGroupModel)
                .where(SavedGroupModel.owner_telegram_user_id == owner_telegram_user_id)
                .order_by(SavedGroupModel.name.asc())
            ).all()
            return [self._to_saved_group_snapshot(row) for row in rows]

    def list_closed_games(self, chat_id: int, limit: int = 10) -> list[GameHistoryEntry]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(ChatGameModel)
                .where(ChatGameModel.chat_id == chat_id, ChatGameModel.status == "closed")
                .order_by(ChatGameModel.id.desc())
                .limit(limit)
            ).all()
            return [self._to_history_entry(row) for row in rows]

    def build_chat_player_stats(self, chat_id: int) -> list[PlayerStatsEntry]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(ChatGameModel)
                .where(ChatGameModel.chat_id == chat_id, ChatGameModel.status == "closed")
                .order_by(ChatGameModel.id.asc())
            ).all()

            totals: dict[str, dict[str, Decimal | int]] = {}
            for game_row in rows:
                for player_row in game_row.players:
                    item = totals.setdefault(
                        player_row.player_name,
                        {
                            "games_played": 0,
                            "total_net": Decimal("0.00"),
                            "wins": 0,
                            "losses": 0,
                        },
                    )
                    net = (Decimal(str(player_row.out)) - Decimal(str(player_row.buyin))).quantize(Decimal("0.01"))
                    item["games_played"] = int(item["games_played"]) + 1
                    item["total_net"] = Decimal(item["total_net"]) + net
                    if net > 0:
                        item["wins"] = int(item["wins"]) + 1
                    elif net < 0:
                        item["losses"] = int(item["losses"]) + 1

            results: list[PlayerStatsEntry] = []
            for player_name, item in totals.items():
                games_played = int(item["games_played"])
                total_net = Decimal(item["total_net"]).quantize(Decimal("0.01"))
                average_net = (total_net / games_played).quantize(Decimal("0.01")) if games_played else Decimal("0.00")
                results.append(
                    PlayerStatsEntry(
                        player_name=player_name,
                        games_played=games_played,
                        total_net=total_net,
                        average_net=average_net,
                        wins=int(item["wins"]),
                        losses=int(item["losses"]),
                    )
                )
            return sorted(results, key=lambda item: (item.total_net, item.average_net, item.player_name), reverse=True)

    def list_game_amount_entries(self, session_id: int) -> list[GameAmountEntry]:
        with self.session_factory() as session:
            game_row = session.get(ChatGameModel, session_id)
            if game_row is None:
                return []

            entries: list[GameAmountEntry] = []
            buyin_players_with_entries: set[str] = set()
            out_players_with_entries: set[str] = set()

            for buyin_entry in game_row.buyin_entries:
                amount = Decimal(str(buyin_entry.amount)).quantize(Decimal("0.01"))
                buyin_players_with_entries.add(buyin_entry.player_name)
                entries.append(
                    GameAmountEntry(
                        player_name=buyin_entry.player_name,
                        phase="buyin",
                        amount=amount,
                        source=buyin_entry.source,
                        raw_text=buyin_entry.raw_text,
                    )
                )

            for message_row in game_row.interactive_messages:
                amount = Decimal(str(message_row.amount)).quantize(Decimal("0.01"))
                if message_row.phase == "buyin":
                    buyin_players_with_entries.add(message_row.player_name)
                elif message_row.phase == "out":
                    out_players_with_entries.add(message_row.player_name)
                entries.append(
                    GameAmountEntry(
                        player_name=message_row.player_name,
                        phase=message_row.phase,
                        amount=amount,
                        source="interactive",
                        raw_text=message_row.raw_text,
                    )
                )

            for player_row in game_row.players:
                buyin = Decimal(str(player_row.buyin)).quantize(Decimal("0.01"))
                out = Decimal(str(player_row.out)).quantize(Decimal("0.01"))
                if buyin != 0 and player_row.player_name not in buyin_players_with_entries:
                    entries.append(
                        GameAmountEntry(
                            player_name=player_row.player_name,
                            phase="buyin",
                            amount=buyin,
                            source="aggregate",
                        )
                    )
                if out != 0 and player_row.player_name not in out_players_with_entries:
                    entries.append(
                        GameAmountEntry(
                            player_name=player_row.player_name,
                            phase="out",
                            amount=out,
                            source="aggregate",
                        )
                    )

            return entries

    def record_product_event(
        self,
        event_name: str,
        telegram_user_id: int | None = None,
        chat_id: int | None = None,
        game_id: int | None = None,
        properties: dict[str, object] | None = None,
    ) -> None:
        with self.session_factory.begin() as session:
            session.add(
                ProductMetricEventModel(
                    event_name=event_name,
                    telegram_user_id=telegram_user_id,
                    chat_id=chat_id,
                    game_id=game_id,
                    properties_json=properties,
                )
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
            input_mode=game_row.input_mode,
            interactive_phase=game_row.interactive_phase,
            game=game,
            created_by_telegram_user_id=game_row.created_by_telegram_user_id,
            finalized_by_telegram_user_id=game_row.finalized_by_telegram_user_id,
            finalized_at=game_row.finalized_at,
            created_at=game_row.created_at,
        )

    @staticmethod
    def _rebuild_interactive_players(session: Session, game_row: ChatGameModel) -> None:
        totals: dict[str, dict[str, Decimal]] = {}
        for message_row in game_row.interactive_messages:
            player_totals = totals.setdefault(
                message_row.player_name,
                {"buyin": Decimal("0.00"), "out": Decimal("0.00")},
            )
            amount = Decimal(str(message_row.amount)).quantize(Decimal("0.01"))
            if message_row.phase == "buyin":
                player_totals["buyin"] += amount
            elif message_row.phase == "out":
                player_totals["out"] += amount

        game_row.players.clear()
        session.flush()
        for player_name, player_totals in totals.items():
            game_row.players.append(
                GamePlayerModel(
                    player_name=player_name,
                    buyin=float(player_totals["buyin"].quantize(Decimal("0.01"))),
                    out=float(player_totals["out"].quantize(Decimal("0.01"))),
                )
            )

    @staticmethod
    def _to_saved_group_snapshot(group_row: SavedGroupModel) -> SavedGroupSnapshot:
        return SavedGroupSnapshot(
            id=group_row.id,
            owner_telegram_user_id=group_row.owner_telegram_user_id,
            name=group_row.name,
            player_names=[member.player_name for member in group_row.members],
            created_at=group_row.created_at,
            updated_at=group_row.updated_at,
        )

    @staticmethod
    def _to_history_entry(game_row: ChatGameModel) -> GameHistoryEntry:
        total_pot = Decimal("0.00")
        players: list[str] = []
        for player_row in game_row.players:
            total_pot += Decimal(str(player_row.buyin))
            players.append(player_row.player_name)
        return GameHistoryEntry(
            id=game_row.id,
            created_at=game_row.created_at,
            finalized_at=game_row.finalized_at,
            player_count=len(players),
            total_pot=total_pot.quantize(Decimal("0.01")),
            players=players,
        )
