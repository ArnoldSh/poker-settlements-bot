from __future__ import annotations

from dataclasses import dataclass

from poker_bot.billing import StripeBillingService
from poker_bot.config import Settings
from poker_bot.store import DatabaseStore


@dataclass
class AppServices:
    settings: Settings
    store: DatabaseStore
    billing: StripeBillingService


SERVICES: AppServices | None = None


def configure_services(services: AppServices) -> None:
    global SERVICES
    SERVICES = services


def get_services() -> AppServices:
    if SERVICES is None:
        raise RuntimeError("Services are not configured.")
    return SERVICES

