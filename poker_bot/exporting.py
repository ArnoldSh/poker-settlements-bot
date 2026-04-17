from __future__ import annotations

import csv
import io

from poker_bot.domain import Game, Transfer
from poker_bot.formatting import eur


def build_game_csv(game: Game, transfers: list[Transfer]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["player_name", "buyin", "cash_out", "net"])
    for player in sorted(game.players.values(), key=lambda item: item.name.lower()):
        writer.writerow([player.name, eur(player.buyin), eur(player.out), eur(player.net)])

    writer.writerow([])
    writer.writerow(["from", "to", "amount"])
    for transfer in transfers:
        writer.writerow([transfer.frm, transfer.to, eur(transfer.amount)])
    return buffer.getvalue().encode("utf-8")
