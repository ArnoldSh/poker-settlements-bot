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


def parse_plan_code(args: list[str]) -> str | None:
    if not args:
        return None
    return PLAN_ALIASES.get(args[0].strip().lower())
