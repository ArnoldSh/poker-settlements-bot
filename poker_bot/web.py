from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from telegram import Update
from telegram.ext import ApplicationBuilder

from poker_bot.billing import StripeBillingService
from poker_bot.config import Settings, load_settings
from poker_bot.db import build_engine, build_session_factory
from poker_bot.handlers import register_handlers
from poker_bot.i18n import tr
from poker_bot.logging_utils import configure_logging
from poker_bot.runtime import AppServices, configure_services, get_services
from poker_bot.store import DatabaseStore

configure_logging()
logger = logging.getLogger(__name__)
settings = load_settings()
engine = build_engine(settings.database_url)
session_factory = build_session_factory(engine)
telegram_app = ApplicationBuilder().token(settings.bot_token).build()


def _admin_guard(admin_secret: str | None) -> None:
    if not settings.admin_secret or admin_secret != settings.admin_secret:
        raise HTTPException(status_code=401, detail=tr("admin_unauthorized"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_services(
        AppServices(
            settings=settings,
            store=DatabaseStore(session_factory),
            billing=StripeBillingService(settings, session_factory),
        )
    )
    register_handlers(telegram_app)
    await telegram_app.initialize()
    await telegram_app.start()
    logger.info("application started")
    try:
        yield
    finally:
        await telegram_app.stop()
        await telegram_app.shutdown()
        engine.dispose()
        logger.info("application stopped")


app = FastAPI(title="Poker Settlements Bot", lifespan=lifespan)


class SubscriptionGrantRequest(BaseModel):
    telegram_user_id: int
    status: str
    days: int | None = None


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post(settings.telegram_webhook_path)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if settings.telegram_webhook_secret_token and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret_token:
        logger.warning("telegram webhook rejected: invalid secret")
        raise HTTPException(status_code=401, detail=tr("webhook_secret_invalid"))

    payload = await request.json()
    logger.info("telegram webhook received")
    update = Update.de_json(payload, telegram_app.bot)
    if update is not None:
        try:
            await telegram_app.process_update(update)
        except Exception:
            logger.exception("telegram webhook processing failed")
            raise
    return {"ok": True}


@app.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, str]:
    services = get_services()
    payload = await request.body()
    try:
        return services.billing.process_webhook(payload, stripe_signature)
    except Exception:
        logger.exception("stripe webhook processing failed")
        raise


@app.get("/billing/success", response_class=HTMLResponse)
async def billing_success() -> str:
    return f"<html><body><h1>{tr('billing_success_page')}</h1></body></html>"


@app.get("/billing/cancel", response_class=HTMLResponse)
async def billing_cancel() -> str:
    return f"<html><body><h1>{tr('billing_cancel_page')}</h1></body></html>"


@app.get("/debug/users/{telegram_user_id}")
async def debug_user(telegram_user_id: int, x_admin_secret: str | None = Header(default=None)) -> dict[str, object]:
    _admin_guard(x_admin_secret)
    return get_services().billing.debug_user_payload(telegram_user_id)


@app.get("/debug/chats/{chat_id}")
async def debug_chat(chat_id: int, x_admin_secret: str | None = Header(default=None)) -> dict[str, object]:
    _admin_guard(x_admin_secret)
    return get_services().store.debug_chat_payload(chat_id)


@app.post("/admin/subscriptions/set")
async def admin_set_subscription(
    payload: SubscriptionGrantRequest,
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, object]:
    _admin_guard(x_admin_secret)
    snapshot = get_services().billing.force_subscription(
        telegram_user_id=payload.telegram_user_id,
        status=payload.status,
        days=payload.days,
    )
    return {
        "telegram_user_id": snapshot.telegram_user_id,
        "status": snapshot.status,
        "current_period_end": None
        if snapshot.current_period_end is None
        else snapshot.current_period_end.isoformat(),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
