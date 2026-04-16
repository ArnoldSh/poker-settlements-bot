from __future__ import annotations

import re
from decimal import Decimal

from poker_bot.formatting import decimal_amount
from poker_bot.i18n import tr

NAME_PATTERN = re.compile(r"^@?[^\s,]+$")


def normalize_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ValueError(tr("empty_name"))
    if not NAME_PATTERN.match(normalized):
        raise ValueError(tr("parse_line_format"))
    if not normalized.startswith("@"):
        normalized = f"@{normalized}"
    return normalized


def parse_amount_expression(expression: str) -> Decimal:
    cleaned = expression.strip()
    if not cleaned:
        raise ValueError(tr("parse_amount_expression", expression=expression))

    parts = [part.strip() for part in cleaned.split("+")]
    if any(not part for part in parts):
        raise ValueError(tr("parse_amount_expression", expression=expression))

    try:
        return sum((decimal_amount(part) for part in parts), Decimal(0))
    except ValueError as exc:
        raise ValueError(tr("parse_amount_expression", expression=expression)) from exc


def split_amounts(rest: str) -> tuple[str, str]:
    rest = rest.strip()
    if not rest:
        raise ValueError(tr("parse_line_format"))

    if "->" in rest:
        buy_expr, out_expr = (part.strip() for part in rest.split("->", 1))
        return buy_expr, out_expr

    if "—" in rest:
        buy_expr, out_expr = (part.strip() for part in rest.split("—", 1))
        return buy_expr, out_expr

    if "," in rest:
        buy_expr, out_expr = (part.strip() for part in rest.split(",", 1))
        return buy_expr, out_expr

    parts = rest.split()
    if len(parts) == 1:
        return parts[0], "0"
    if len(parts) == 2:
        return parts[0], parts[1]

    raise ValueError(tr("parse_line_format"))


def parse_line(text: str) -> tuple[str, Decimal, Decimal]:
    stripped = text.strip()
    if not stripped:
        raise ValueError(tr("parse_line_format"))

    try:
        raw_name, rest = stripped.split(maxsplit=1)
    except ValueError as exc:
        raise ValueError(tr("parse_line_format")) from exc

    buy_expr, out_expr = split_amounts(rest)
    return normalize_name(raw_name), parse_amount_expression(buy_expr), parse_amount_expression(out_expr)

