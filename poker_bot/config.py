from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    host: str
    port: int
    telegram_webhook_path: str
    telegram_webhook_secret_token: str | None
    stripe_secret_key: str | None
    stripe_webhook_secret: str | None
    stripe_price_id: str | None
    app_base_url: str | None
    admin_secret: str | None

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_price_id and self.app_base_url)


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
        stripe_secret_key=os.environ.get("STRIPE_SECRET_KEY"),
        stripe_webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET"),
        stripe_price_id=os.environ.get("STRIPE_PRICE_ID"),
        app_base_url=_normalise_base_url(os.environ.get("APP_BASE_URL")),
        admin_secret=os.environ.get("ADMIN_SECRET"),
    )

