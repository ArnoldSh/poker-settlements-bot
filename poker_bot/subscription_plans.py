from __future__ import annotations


PLAN_ALIASES = {
    "monthly": "monthly",
    "1m": "monthly",
    "quarterly": "quarterly",
    "3m": "quarterly",
    "semiannual": "semiannual",
    "6m": "semiannual",
    "yearly": "yearly",
    "1y": "yearly",
}

LIMIT_BOOST_ALIASES = {
    "boost_30d": "boost_30d",
    "1m": "boost_30d",
    "boost_90d": "boost_90d",
    "3m": "boost_90d",
    "boost_180d": "boost_180d",
    "6m": "boost_180d",
    "boost_365d": "boost_365d",
    "1y": "boost_365d",
}


def parse_plan_code(args: list[str]) -> str | None:
    if not args:
        return None
    return PLAN_ALIASES.get(args[0].strip().lower())


def parse_limit_boost_code(args: list[str]) -> str | None:
    if not args:
        return None
    return LIMIT_BOOST_ALIASES.get(args[0].strip().lower())
