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


def _telegram_update_reference_log(update: Update) -> dict[str, object]:
    event_types: list[str] = []
    refs: dict[str, object] = {"update_id": update.update_id}

    typed_objects = {
        "message": update.message,
        "edited_message": update.edited_message,
        "channel_post": update.channel_post,
        "edited_channel_post": update.edited_channel_post,
        "callback_query": update.callback_query,
        "inline_query": update.inline_query,
        "chosen_inline_result": update.chosen_inline_result,
        "shipping_query": update.shipping_query,
        "pre_checkout_query": update.pre_checkout_query,
        "poll": update.poll,
        "poll_answer": update.poll_answer,
        "my_chat_member": update.my_chat_member,
        "chat_member": update.chat_member,
        "chat_join_request": update.chat_join_request,
    }
    for event_type, value in typed_objects.items():
        if value is not None:
            event_types.append(event_type)

    message = update.effective_message
    if message is not None:
        refs["message_id"] = message.message_id

    chat = update.effective_chat
    if chat is not None:
        refs["chat_id"] = chat.id
        refs["chat_type"] = chat.type

    user = update.effective_user
    if user is not None:
        refs["user_id"] = user.id

    if update.callback_query is not None:
        refs["callback_query_id"] = update.callback_query.id
        if update.callback_query.message is not None:
            refs["callback_message_id"] = update.callback_query.message.message_id

    if update.inline_query is not None:
        refs["inline_query_id"] = update.inline_query.id

    if update.chosen_inline_result is not None:
        refs["chosen_inline_result_id"] = update.chosen_inline_result.result_id

    if update.shipping_query is not None:
        refs["shipping_query_id"] = update.shipping_query.id

    if update.pre_checkout_query is not None:
        refs["pre_checkout_query_id"] = update.pre_checkout_query.id

    if update.poll is not None:
        refs["poll_id"] = update.poll.id

    if update.poll_answer is not None:
        refs["poll_id"] = update.poll_answer.poll_id

    return {"event_types": event_types or ["unknown"], **refs}


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
    update = Update.de_json(payload, telegram_app.bot)
    if update is not None:
        logger.info("telegram webhook received: %s", _telegram_update_reference_log(update))
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
        services.store.record_product_event(
            "stripe_webhook_processed",
            properties={"event_type": result.event_type, "status": result.status},
        )
        if result.event_type == "checkout.session.completed":
            services.store.record_product_event("subscription_checkout_completed")
        if result.event_type.startswith("customer.subscription."):
            services.store.record_product_event(
                "subscription_provider_state_changed",
                properties={"event_type": result.event_type},
            )
        if result.event_type in {"charge.refunded", "refund.updated"}:
            services.store.record_product_event("subscription_refunded")
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
