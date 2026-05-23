from __future__ import annotations

import argparse
from pathlib import Path

from poker_bot.config import load_settings
from poker_bot.db import build_engine, build_session_factory
from poker_bot.history_import import (
    import_games,
    parse_alias_map,
    parse_date_fix_map,
    parse_history_dump,
    summarize_games,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import closed poker games from saved chat messages.")
    parser.add_argument("input_path", help="Path to a UTF-8 text file with saved bot messages.")
    parser.add_argument("--chat-id", type=int, required=True, help="Telegram chat id to import games into.")
    parser.add_argument(
        "--alias",
        action="append",
        default=[],
        help="Player alias mapping in the form OLD=NEW. Can be passed multiple times.",
    )
    parser.add_argument(
        "--date-fix",
        action="append",
        default=[],
        help="Date correction in the form OLD=NEW. Can be passed multiple times.",
    )
    parser.add_argument(
        "--timezone",
        default="Asia/Nicosia",
        help="Timezone used in saved message timestamps. Default: Asia/Nicosia.",
    )
    parser.add_argument(
        "--allow-duplicate-datetime",
        action="store_true",
        help="Import games even if a closed game with the same finalized_at already exists in this chat.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print summary without writing to the database.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    text = Path(args.input_path).read_text(encoding="utf-8")
    alias_map = parse_alias_map(args.alias)
    date_fixes = parse_date_fix_map(args.date_fix)
    games = parse_history_dump(
        text,
        alias_map=alias_map,
        date_fixes=date_fixes,
        tz_name=args.timezone,
    )
    print(summarize_games(games))

    if args.dry_run:
        for game in games:
            print(f"{game.source_date_text} -> {game.played_at.isoformat()} | players={len(game.players)}")
        return 0

    settings = load_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    imported, skipped = import_games(
        session_factory,
        chat_id=args.chat_id,
        games=games,
        skip_existing_datetime=not args.allow_duplicate_datetime,
    )
    print(f"Imported: {imported} | Skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
