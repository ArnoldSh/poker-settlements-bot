from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import ApplicationBuilder

from poker_bot.billing import StripeBillingService
from poker_bot.config import Settings, load_settings
from poker_bot.db import build_engine, build_session_factory
from poker_bot.handlers import register_handlers
from poker_bot.i18n import tr
from poker_bot.logging_utils import configure_logging
from poker_bot.notifications import TelegramAdminNotifier, TelegramUserNotifier
from poker_bot.runtime import AppServices, configure_services, get_services
from poker_bot.store import DatabaseStore

configure_logging()
logger = logging.getLogger(__name__)
settings = load_settings()
engine = build_engine(settings.database_url)
session_factory = build_session_factory(engine)
telegram_app = ApplicationBuilder().token(settings.bot_token).build()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_services(
        AppServices(
            settings=settings,
            store=DatabaseStore(session_factory),
            billing=StripeBillingService(settings, session_factory),
            admin_notifier=TelegramAdminNotifier(settings.admin_telegram_chat_id),
            user_notifier=TelegramUserNotifier(),
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
        result = services.billing.process_webhook(payload, stripe_signature)
        for notification in result.notifications:
            await services.user_notifier.notify(telegram_app.bot, notification)
        return {"event_id": result.event_id, "status": result.status}
    except Exception:
        logger.exception("stripe webhook processing failed")
        raise


@app.get("/billing/success", response_class=HTMLResponse)
async def billing_success() -> str:
    return f"<html><body><h1>{tr('billing_return_to_telegram_page')}</h1></body></html>"


@app.get("/billing/cancel", response_class=HTMLResponse)
async def billing_cancel() -> str:
    return f"<html><body><h1>{tr('billing_return_to_telegram_page')}</h1></body></html>"
