from __future__ import annotations

from decimal import Decimal

from poker_bot.domain import Game, Transfer
from poker_bot.formatting import MONEY_Q, eur
from poker_bot.i18n import tr
from poker_bot.store import GameHistoryEntry, PlayerStatsEntry, SavedGroupSnapshot


def render_table(game: Game) -> str:
    if not game.players:
        return tr("list_empty")

    lines = [tr("table_header"), "-" * 30]
    for player in sorted(game.players.values(), key=lambda item: item.name.lower()):
        lines.append(f"{player.name} | {eur(player.buyin)} | {eur(player.out)} | <b>{eur(player.net)}</b>")

    lines.append("-" * 30)
    lines.append(
        tr(
            "table_totals",
            buyin=eur(game.total_buyin),
            out=eur(game.total_out),
            net=eur(game.total_out - game.total_buyin),
        )
    )
    return "\n".join(lines)


def render_transfers(header: str, highlights: str, game: Game, transfers: list[Transfer]) -> str:
    total = sum((transfer.amount for transfer in transfers), Decimal(0)).quantize(MONEY_Q)
    sorted_players = sorted(game.players.values(), key=lambda item: (item.net, item.name), reverse=True)
    standings = []
    for player in sorted_players:
        marker = "🏆" if player.net > 0 else ("😬" if player.net < 0 else "🤝")
        standings.append(f"{marker} {player.name} {eur(player.net)}")

    transfer_lines = [f"{transfer.frm} -> {transfer.to} {eur(transfer.amount)}" for transfer in transfers]

    return (
        f"{header}\n\n"
        f"{highlights}\n\n"
        f"{tr('pretty_results_title')}\n"
        f"{'\n'.join(standings)}\n\n"
        f"{tr('calc_transfers_header')}\n"
        f"{'\n'.join(transfer_lines)}\n\n"
        f"{tr('calc_summary', count=len(transfers), total=eur(total))}\n"
        f"{tr('pretty_results_footer')}"
    )


def render_basic_transfers(header: str, transfers: list[Transfer]) -> str:
    total = sum((transfer.amount for transfer in transfers), Decimal(0)).quantize(MONEY_Q)
    transfer_lines = [f"{index}. {transfer}" for index, transfer in enumerate(transfers, start=1)]
    return (
        f"{header}\n\n"
        f"{tr('calc_transfers_header')}\n"
        f"{'\n'.join(transfer_lines)}\n\n"
        f"{tr('calc_summary', count=len(transfers), total=eur(total))}"
    )


def render_saved_groups(groups: list[SavedGroupSnapshot]) -> str:
    if not groups:
        return tr("groups_empty")

    lines = [tr("groups_title")]
    for group in groups:
        players = ", ".join(group.player_names)
        lines.append(tr("groups_item", name=group.name, count=len(group.player_names), players=players))
    return "\n".join(lines)


def render_history(entries: list[GameHistoryEntry]) -> str:
    if not entries:
        return tr("history_empty")

    lines = [tr("history_title")]
    for entry in entries:
        date = (entry.finalized_at or entry.created_at).strftime("%d %b")
        players = ", ".join(entry.players)
        lines.append(
            tr(
                "history_item",
                date=date,
                player_count=entry.player_count,
                total_pot=eur(entry.total_pot),
                players=players,
            )
        )
    return "\n".join(lines)


def render_stats(entries: list[PlayerStatsEntry]) -> str:
    if not entries:
        return tr("stats_empty")

    lines = [tr("stats_title")]
    for index, entry in enumerate(entries, start=1):
        lines.append(
            tr(
                "stats_item",
                index=index,
                name=entry.player_name,
                total=eur(entry.total_net),
                games=entry.games_played,
                average=eur(entry.average_net),
                wins=entry.wins,
                losses=entry.losses,
            )
        )
    return "\n".join(lines)


def render_stats_basic(entries: list[PlayerStatsEntry]) -> str:
    if not entries:
        return tr("stats_empty")

    lines = [tr("stats_title_basic")]
    for entry in entries:
        lines.append(
            tr(
                "stats_item_basic",
                name=entry.player_name,
                total=eur(entry.total_net),
                games=entry.games_played,
            )
        )
    return "\n".join(lines)


def render_calc_with_stats(
    header: str,
    highlights: str,
    game: Game,
    transfers: list[Transfer],
    stats_text: str,
) -> str:
    return f"{render_transfers(header, highlights, game, transfers)}\n\n{stats_text}"


def render_basic_calc_with_stats(
    header: str,
    transfers: list[Transfer],
    stats_text: str,
) -> str:
    return f"{render_basic_transfers(header, transfers)}\n\n{stats_text}"
