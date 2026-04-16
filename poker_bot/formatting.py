from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONEY_Q = Decimal("0.01")


def decimal_amount(value: str | int | float | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        amount = value
    else:
        normalized = str(value).strip().replace(",", ".")
        try:
            amount = Decimal(normalized)
        except InvalidOperation as exc:
            raise ValueError(f"Не могу распознать число: {value}") from exc

    return amount.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def eur(amount: Decimal) -> str:
    return f"{amount:,.2f} €".replace(",", "_").replace(".", ",").replace("_", " ")

