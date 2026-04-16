from __future__ import annotations

import random
from decimal import Decimal

from poker_bot.formatting import eur
from poker_bot.i18n import RU_CATALOG, tr


def build_highlights(nets: dict[str, Decimal]) -> str:
    winners = [(name, value) for name, value in nets.items() if value > 0]
    losers = [(name, value) for name, value in nets.items() if value < 0]

    if not winners and not losers:
        return tr("highlights_zero")

    lines: list[str] = [tr("highlights_title")]
    selected: set[str] = set()

    if winners:
        big_winner_name, big_winner_value = max(winners, key=lambda item: item[1])
        lines.append(
            tr(
                "highlights_big_winner",
                name=big_winner_name,
                amount=eur(big_winner_value),
                comment=random.choice(RU_CATALOG.commentary.winner_big),
            )
        )
        selected.add(big_winner_name)

        small_winner_name, small_winner_value = min(winners, key=lambda item: item[1])
        if small_winner_name != big_winner_name:
            lines.append(
                tr(
                    "highlights_small_winner",
                    name=small_winner_name,
                    amount=eur(small_winner_value),
                    comment=random.choice(RU_CATALOG.commentary.winner_small),
                )
            )
            selected.add(small_winner_name)

    if losers:
        big_loser_name, big_loser_value = min(losers, key=lambda item: item[1])
        lines.append(
            tr(
                "highlights_big_loser",
                name=big_loser_name,
                amount=eur(-big_loser_value),
                comment=random.choice(RU_CATALOG.commentary.loser_big),
            )
        )
        selected.add(big_loser_name)

        small_loser_name, small_loser_value = max(losers, key=lambda item: item[1])
        if small_loser_name != big_loser_name:
            lines.append(
                tr(
                    "highlights_small_loser",
                    name=small_loser_name,
                    amount=eur(-small_loser_value),
                    comment=random.choice(RU_CATALOG.commentary.loser_small),
                )
            )
            selected.add(small_loser_name)

    others = sorted(
        ((name, value) for name, value in nets.items() if name not in selected),
        key=lambda item: item[1],
        reverse=True,
    )
    if others:
        rendered = []
        for name, value in others:
            direction = tr("highlights_zero_direction")
            amount = eur(abs(value))
            if value > 0:
                direction = tr("highlights_plus")
            elif value < 0:
                direction = tr("highlights_minus")
            rendered.append(tr("highlights_other", name=name, amount=amount, direction=direction))
        lines.append(tr("highlights_other_title", items=", ".join(rendered)))

    return "\n".join(lines)

