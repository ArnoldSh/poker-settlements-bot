from __future__ import annotations

from decimal import Decimal

from poker_bot.domain import Game, Transfer
from poker_bot.formatting import MONEY_Q, eur
from poker_bot.i18n import tr


def render_table(game: Game) -> str:
    if not game.players:
        return tr("list_empty")

    lines = [tr("table_header"), "—" * 30]
    for player in sorted(game.players.values(), key=lambda item: item.name.lower()):
        lines.append(f"{player.name} | {eur(player.buyin)} | {eur(player.out)} | <b>{eur(player.net)}</b>")

    lines.append("—" * 30)
    lines.append(
        tr(
            "table_totals",
            buyin=eur(game.total_buyin),
            out=eur(game.total_out),
            net=eur(game.total_out - game.total_buyin),
        )
    )
    return "\n".join(lines)


def render_transfers(header: str, highlights: str, transfers: list[Transfer]) -> str:
    total = sum((transfer.amount for transfer in transfers), Decimal(0)).quantize(MONEY_Q)
    lines = [f"{index}. {transfer}" for index, transfer in enumerate(transfers, start=1)]

    return (
        f"{header}\n\n"
        f"{highlights}\n\n"
        f"{tr('calc_transfers_header')}\n"
        f"{'\n'.join(lines)}\n\n"
        f"{tr('calc_summary', count=len(transfers), total=eur(total))}"
    )

