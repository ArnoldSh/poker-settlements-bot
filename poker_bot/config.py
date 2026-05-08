from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import timedelta

from poker_bot.features import DEFAULT_ENABLED_FEATURES, parse_feature_list


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    host: str
    port: int
    telegram_webhook_path: str
    telegram_webhook_secret_token: str | None
    max_players_per_game: int
    free_trial_games_per_chat: int
    free_trial_days: int
    admin_user_id: int | None
    permission_table_cache_ttl: timedelta
    chat_usage_warning_threshold: float
    enabled_features: frozenset[str]
    stripe_secret_key: str | None
    stripe_webhook_secret: str | None
    app_base_url: str | None

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.app_base_url)


def _normalise_base_url(url: str | None) -> str | None:
    """Ensure the base URL carries an explicit https:// scheme.

    Railway's RAILWAY_PUBLIC_DOMAIN variable resolves to a bare domain
    (e.g. ``poker-bot.up.railway.app``).  Stripe's API rejects ``success_url``
    and ``cancel_url`` values that lack an explicit scheme, so we prepend
    ``https://`` whenever the value is present but scheme-less.
    """
    if not url:
        return url
    url = url.rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"https://{url}"
    return url


_ISO_DURATION_PATTERN = re.compile(
    r"^P"
    r"(?:(?P<days>\d+)D)?"
    r"(?:(?P<time>T)"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$",
    re.IGNORECASE,
)


def _parse_duration(value: str | None, default: timedelta) -> timedelta:
    if value is None or not value.strip():
        return default

    raw_value = value.strip()
    match = _ISO_DURATION_PATTERN.match(raw_value)
    if match and any(match.group(name) for name in ("days", "hours", "minutes", "seconds")):
        return timedelta(
            days=int(match.group("days") or 0),
            hours=int(match.group("hours") or 0),
            minutes=int(match.group("minutes") or 0),
            seconds=int(match.group("seconds") or 0),
        )

    raise RuntimeError(
        "PERMISSION_TABLE_CACHE_TTL must be an ISO 8601 duration like PT5M, PT1H, or P1D."
    )


def _parse_ratio(value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    ratio = float(value.strip())
    if ratio <= 0 or ratio > 1:
        raise RuntimeError("CHAT_USAGE_WARNING_THRESHOLD must be greater than 0 and less than or equal to 1.")
    return ratio


def load_settings() -> Settings:
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required.")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")

    return Settings(
        bot_token=bot_token,
        database_url=database_url,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        telegram_webhook_path=os.environ.get("TELEGRAM_WEBHOOK_PATH", "/webhooks/telegram"),
        telegram_webhook_secret_token=os.environ.get("BOT_WEBHOOK_SECRET_TOKEN"),
        max_players_per_game=int(os.environ.get("MAX_PLAYERS_PER_GAME", "10")),
        free_trial_games_per_chat=int(os.environ.get("FREE_TRIAL_GAMES_PER_CHAT", "3")),
        free_trial_days=int(os.environ.get("FREE_TRIAL_DAYS", "31")),
        admin_user_id=(
            int(os.environ["ADMIN_USER_ID"])
            if os.environ.get("ADMIN_USER_ID")
            else None
        ),
        permission_table_cache_ttl=_parse_duration(
            os.environ.get("PERMISSION_TABLE_CACHE_TTL"),
            default=timedelta(hours=1),
        ),
        chat_usage_warning_threshold=_parse_ratio(
            os.environ.get("CHAT_USAGE_WARNING_THRESHOLD"),
            default=0.8,
        ),
        enabled_features=parse_feature_list(
            os.environ.get("ENABLED_FEATURES")
            or DEFAULT_ENABLED_FEATURES
        ),
        stripe_secret_key=os.environ.get("STRIPE_SECRET_KEY"),
        stripe_webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET"),
        app_base_url=_normalise_base_url(os.environ.get("APP_BASE_URL")),
    )

