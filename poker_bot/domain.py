from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from poker_bot.formatting import MONEY_Q, decimal_amount, eur
from poker_bot.i18n import tr


@dataclass
class Player:
    name: str
    buyin: Decimal = Decimal(0)
    out: Decimal = Decimal(0)

    @property
    def net(self) -> Decimal:
        return (self.out - self.buyin).quantize(MONEY_Q)


@dataclass
class Game:
    players: dict[str, Player] = field(default_factory=dict)

    def add_or_update(self, name: str, buyin: Decimal, out: Decimal) -> None:
        player = self.players.get(name) or Player(name=name)
        player.buyin = decimal_amount(buyin)
        player.out = decimal_amount(out)
        self.players[name] = player

    def remove(self, name: str) -> bool:
        return self.players.pop(name, None) is not None

    @property
    def total_buyin(self) -> Decimal:
        return sum((player.buyin for player in self.players.values()), Decimal(0)).quantize(MONEY_Q)

    @property
    def total_out(self) -> Decimal:
        return sum((player.out for player in self.players.values()), Decimal(0)).quantize(MONEY_Q)

    def nets(self) -> dict[str, Decimal]:
        return {player.name: player.net for player in self.players.values()}

    def check_balance(self) -> str | None:
        diff = (self.total_out - self.total_buyin).quantize(MONEY_Q)
        if diff == 0:
            return None

        return tr(
            "balance_mismatch",
            buyin=eur(self.total_buyin),
            out=eur(self.total_out),
        )


@dataclass
class Transfer:
    frm: str
    to: str
    amount: Decimal

    def __str__(self) -> str:
        return f"{self.frm} -> {self.to}: {eur(self.amount)}"


def settle_direct(nets: dict[str, Decimal]) -> list[Transfer]:
    creditors: list[tuple[str, Decimal]] = []
    debtors: list[tuple[str, Decimal]] = []

    for name, value in nets.items():
        if value > 0:
            creditors.append((name, value))
        elif value < 0:
            debtors.append((name, -value))

    creditors.sort(key=lambda item: item[1], reverse=True)
    debtors.sort(key=lambda item: item[1], reverse=True)

    transfers: list[Transfer] = []
    debtor_index = 0
    creditor_index = 0

    while debtor_index < len(debtors) and creditor_index < len(creditors):
        debtor_name, debtor_amount = debtors[debtor_index]
        creditor_name, creditor_amount = creditors[creditor_index]

        payment = min(debtor_amount, creditor_amount).quantize(MONEY_Q)
        if payment > 0:
            transfers.append(Transfer(debtor_name, creditor_name, payment))
            debtor_amount = (debtor_amount - payment).quantize(MONEY_Q)
            creditor_amount = (creditor_amount - payment).quantize(MONEY_Q)

        if debtor_amount == 0:
            debtor_index += 1
        else:
            debtors[debtor_index] = (debtor_name, debtor_amount)

        if creditor_amount == 0:
            creditor_index += 1
        else:
            creditors[creditor_index] = (creditor_name, creditor_amount)

    return transfers


def pick_hub_auto(nets: dict[str, Decimal]) -> str:
    return max(nets.items(), key=lambda item: (abs(item[1]), item[0]))[0]


def settle_hub(nets: dict[str, Decimal], hub: str | None = None) -> tuple[str, list[Transfer]]:
    if not nets:
        return "", []

    hub_name = hub or pick_hub_auto(nets)
    if hub_name not in nets:
        raise ValueError(tr("hub_not_found"))

    transfers: list[Transfer] = []
    for name, net in nets.items():
        if name == hub_name or net == 0:
            continue
        if net < 0:
            transfers.append(Transfer(name, hub_name, -net))
        else:
            transfers.append(Transfer(hub_name, name, net))

    return hub_name, transfers

