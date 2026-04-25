from __future__ import annotations

import re
from decimal import Decimal

from poker_bot.formatting import decimal_amount
from poker_bot.i18n import tr

MAX_PLAYER_NAME_LENGTH = 64
TAG_PATTERN = re.compile(r"^@?[A-Za-z0-9_]+$")
NUMBER_ONLY_PATTERN = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")


def normalize_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ValueError(tr("empty_name"))
    if not TAG_PATTERN.match(normalized):
        raise ValueError(tr("invalid_player_tag"))
    if not normalized.startswith("@"):
        normalized = f"@{normalized}"
    if len(normalized) > MAX_PLAYER_NAME_LENGTH:
        raise ValueError(tr("invalid_player_tag"))
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


def parse_amount_components(expression: str) -> list[Decimal]:
    cleaned = expression.strip()
    if not cleaned:
        raise ValueError(tr("parse_amount_expression", expression=expression))

    parts = [part.strip() for part in cleaned.split("+")]
    if any(not part for part in parts):
        raise ValueError(tr("parse_amount_expression", expression=expression))

    try:
        return [decimal_amount(part) for part in parts]
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


def parse_line_with_buyin_entries(text: str) -> tuple[str, Decimal, Decimal, list[Decimal]]:
    stripped = text.strip()
    if not stripped:
        raise ValueError(tr("parse_line_format"))

    try:
        raw_name, rest = stripped.split(maxsplit=1)
    except ValueError as exc:
        raise ValueError(tr("parse_line_format")) from exc

    buy_expr, out_expr = split_amounts(rest)
    buyin_entries = parse_amount_components(buy_expr)
    return (
        normalize_name(raw_name),
        sum(buyin_entries, Decimal(0)),
        parse_amount_expression(out_expr),
        buyin_entries,
    )


def parse_number_only(text: str) -> Decimal | None:
    stripped = text.strip()
    if not NUMBER_ONLY_PATTERN.match(stripped):
        return None
    return parse_amount_expression(stripped)
