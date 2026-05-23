from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import re
import shlex
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

BLOCK_HEADER_RE = re.compile(r"^\[(?P<raw_date>[^\]]+)\]\s*$")
PLAYER_ROW_RE = re.compile(
    r"^(?P<name>@[^|]+?)\s*\|\s*(?P<buyin>[^|]+?)\s*\|\s*(?P<out>[^|]+?)\s*\|\s*(?P<net>[^|]+?)\s*$"
)
DATE_FORMAT = "%d.%m.%Y %H:%M"
HEADER_PREFIXES = ("Игрок |", "Вход |", "Бай-ин |", "РРіСЂРѕРє |", "Р’С…РѕРґ |", "Р‘Р°Р№-РёРЅ |", "ОЈ |", "Σ |", "РћР€ |")


@dataclass(frozen=True)
class ImportedPlayer:
    player_name: str
    buyin: Decimal
    out: Decimal


@dataclass(frozen=True)
class ImportedGame:
    source_date_text: str
    played_at: datetime
    players: list[ImportedPlayer]


@dataclass(frozen=True)
class ImportCommandRequest:
    chat_id: int | None
    history_text: str
    alias_map: dict[str, str]
    date_fixes: dict[str, str]
    dry_run: bool


def parse_alias_map(values: list[str]) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for value in values:
        raw_source, separator, raw_target = value.partition("=")
        if not separator:
            raise ValueError(f"Invalid alias mapping '{value}'. Expected OLD=NEW.")
        alias_map[raw_source.strip()] = raw_target.strip()
    return alias_map


def parse_date_fix_map(values: list[str]) -> dict[str, str]:
    fix_map: dict[str, str] = {}
    for value in values:
        raw_source, separator, raw_target = value.partition("=")
        if not separator:
            raise ValueError(f"Invalid date fix '{value}'. Expected OLD=NEW.")
        fix_map[raw_source.strip()] = raw_target.strip()
    return fix_map


def parse_import_command_request(command_args_text: str, history_text: str) -> ImportCommandRequest:
    alias_values: list[str] = []
    date_fix_values: list[str] = []
    dry_run = False
    chat_id: int | None = None

    try:
        tokens = shlex.split(command_args_text)
    except ValueError as exc:
        raise ValueError(f"Invalid import command arguments: {exc}") from exc

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--dry-run":
            dry_run = True
            index += 1
            continue
        if token == "--chat-id":
            chat_id = int(_require_option_value(tokens, index, token))
            index += 2
            continue
        if token == "--alias":
            alias_values.append(_require_option_value(tokens, index, token))
            index += 2
            continue
        if token == "--date-fix":
            date_fix_values.append(_require_option_value(tokens, index, token))
            index += 2
            continue
        raise ValueError(
            f"Unknown import option '{token}'. Supported options: --chat-id, --alias, --date-fix, --dry-run."
        )

    normalized_history = history_text.strip()
    if not normalized_history:
        raise ValueError("No game blocks found in import message.")

    return ImportCommandRequest(
        chat_id=chat_id,
        history_text=normalized_history,
        alias_map=parse_alias_map(alias_values),
        date_fixes=parse_date_fix_map(date_fix_values),
        dry_run=dry_run,
    )


def parse_history_dump(
    text: str,
    alias_map: dict[str, str] | None = None,
    date_fixes: dict[str, str] | None = None,
    tz_name: str = "Asia/Nicosia",
) -> list[ImportedGame]:
    alias_map = alias_map or {}
    date_fixes = date_fixes or {}

    lines = text.splitlines()
    games: list[ImportedGame] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue

        header_match = BLOCK_HEADER_RE.match(line)
        if not header_match:
            index += 1
            continue

        raw_date = header_match.group("raw_date").strip()
        played_at = _parse_played_at(raw_date, date_fixes, tz_name)
        index += 1

        players: list[ImportedPlayer] = []
        while index < len(lines):
            current = lines[index].strip()
            index += 1

            if not current:
                if players:
                    break
                continue
            if current.startswith(HEADER_PREFIXES):
                continue
            if set(current) <= {"-", "—", "―"}:
                continue
            if not current.startswith("@"):
                if players:
                    break
                continue

            row_match = PLAYER_ROW_RE.match(current)
            if row_match is None:
                break

            player_name = row_match.group("name").strip()
            canonical_name = alias_map.get(player_name, player_name)
            buyin = _parse_money(row_match.group("buyin"))
            out = _parse_money(row_match.group("out"))
            players.append(ImportedPlayer(player_name=canonical_name, buyin=buyin, out=out))

        if not players:
            raise ValueError(f"No player rows found for block dated '{raw_date}'.")
        games.append(ImportedGame(source_date_text=raw_date, played_at=played_at, players=players))

    if not games:
        raise ValueError("No game blocks found in import text.")
    return games


def import_games(
    session_factory: "sessionmaker[Session]",
    chat_id: int,
    games: list[ImportedGame],
    skip_existing_datetime: bool = True,
) -> tuple[int, int]:
    from sqlalchemy import select

    from poker_bot.models import ChatGameModel, GamePlayerModel

    imported = 0
    skipped = 0
    with session_factory.begin() as session:
        for game in games:
            if skip_existing_datetime:
                existing = session.scalar(
                    select(ChatGameModel.id).where(
                        ChatGameModel.chat_id == chat_id,
                        ChatGameModel.status == "closed",
                        ChatGameModel.finalized_at == game.played_at,
                    )
                )
                if existing is not None:
                    skipped += 1
                    continue

            game_row = ChatGameModel(
                chat_id=chat_id,
                status="closed",
                input_mode="manual",
                interactive_phase=None,
                created_at=game.played_at,
                updated_at=game.played_at,
                finalized_at=game.played_at,
            )
            session.add(game_row)
            session.flush()

            for player in game.players:
                session.add(
                    GamePlayerModel(
                        game_id=game_row.id,
                        player_name=player.player_name,
                        buyin=float(player.buyin),
                        out=float(player.out),
                    )
                )
            imported += 1

    return imported, skipped


def summarize_games(games: list[ImportedGame]) -> str:
    total_players = sum(len(game.players) for game in games)
    start = min(game.played_at for game in games)
    end = max(game.played_at for game in games)
    return (
        f"Games: {len(games)} | Players rows: {total_players} | "
        f"Range: {start.strftime('%Y-%m-%d %H:%M %Z')} -> {end.strftime('%Y-%m-%d %H:%M %Z')}"
    )


def build_dry_run_report(games: list[ImportedGame]) -> str:
    lines = [summarize_games(games)]
    for game in games:
        total_buyin = sum((player.buyin for player in game.players), start=Decimal("0.00"))
        total_out = sum((player.out for player in game.players), start=Decimal("0.00"))
        lines.append(
            f"{game.source_date_text} -> {game.played_at.isoformat()} | "
            f"players={len(game.players)} | buyin={total_buyin:.2f} | out={total_out:.2f}"
        )
    return "\n".join(lines)


def _parse_money(raw_value: str) -> Decimal:
    cleaned = raw_value.replace("€", "").replace("в‚¬", "").replace("РІвЂљВ¬", "").replace(" ", "").strip()
    normalized = cleaned.replace(",", ".")
    return Decimal(normalized).quantize(Decimal("0.01"))


def _parse_played_at(raw_date: str, date_fixes: dict[str, str], tz_name: str) -> datetime:
    fixed_date = date_fixes.get(raw_date, raw_date)
    try:
        naive = datetime.strptime(fixed_date, DATE_FORMAT)
    except ValueError as exc:
        raise ValueError(
            f"Invalid date '{raw_date}'. Add a date fix like '{raw_date}=23.05.2026 11:10'."
        ) from exc
    try:
        tzinfo = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tzinfo = timezone.utc
    local_dt = naive.replace(tzinfo=tzinfo)
    return local_dt.astimezone(timezone.utc)


def _require_option_value(tokens: list[str], index: int, option: str) -> str:
    if index + 1 >= len(tokens):
        raise ValueError(f"Option '{option}' requires a value.")
    return tokens[index + 1]
