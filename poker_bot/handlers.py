from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from poker_bot.commentary import build_highlights
from poker_bot.domain import settle_direct, settle_hub
from poker_bot.formatting import eur
from poker_bot.i18n import tr
from poker_bot.parsing import normalize_name, parse_line
from poker_bot.rendering import render_table, render_transfers
from poker_bot.runtime import get_services


def _chat_id(update: Update) -> int:
    chat = update.effective_chat
    if chat is None:
        raise ValueError(tr("missing_chat"))
    return chat.id


def _message(update: Update):
    message = update.effective_message
    if message is None:
        raise ValueError(tr("missing_message"))
    return message


def _telegram_user_id(update: Update) -> int | None:
    user = update.effective_user
    if user is None:
        return None
    return user.id


def _sync_user(update: Update) -> int | None:
    services = get_services()
    user = update.effective_user
    if user is None:
        return None

    services.billing.ensure_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
    )
    return user.id


async def _require_subscription(update: Update) -> bool:
    services = get_services()
    user_id = _sync_user(update)
    if user_id is None:
        await _message(update).reply_text(tr("subscription_required"))
        return False

    if services.billing.has_active_subscription(user_id):
        return True

    await _message(update).reply_text(tr("subscription_required"))
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    await _message(update).reply_text(tr("start_text"), parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    await _message(update).reply_text(tr("help_text"), parse_mode=ParseMode.HTML)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = get_services()
    user = update.effective_user
    if user is None:
        await _message(update).reply_text(tr("subscription_checkout_unavailable"))
        return

    if not services.billing.enabled:
        await _message(update).reply_text(tr("subscription_checkout_unavailable"))
        return

    checkout_url = services.billing.create_checkout_session(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
    )
    await _message(update).reply_text(tr("subscription_checkout_created", url=checkout_url))


async def subscription_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = get_services()
    user_id = _sync_user(update)
    if user_id is None:
        await _message(update).reply_text(tr("subscription_status_inactive"))
        return

    subscription = services.billing.get_subscription(user_id)
    if subscription.is_active:
        if subscription.current_period_end is not None:
            await _message(update).reply_text(
                tr("subscription_status_active", date=subscription.current_period_end.strftime("%Y-%m-%d %H:%M UTC"))
            )
        else:
            await _message(update).reply_text(tr("subscription_status_active_open"))
        return

    await _message(update).reply_text(tr("subscription_status_inactive"))


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_subscription(update):
        return

    services = get_services()
    services.store.reset(_chat_id(update), created_by_telegram_user_id=_telegram_user_id(update))
    await _message(update).reply_text(tr("newgame_done"))


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_subscription(update):
        return

    services = get_services()
    message = _message(update)
    chat_id = _chat_id(update)
    game = services.store.get(chat_id)

    if not context.args:
        await message.reply_text(tr("add_usage"))
        return

    try:
        name, buyin, out = parse_line(" ".join(context.args))
        game.add_or_update(name, buyin, out)
        services.store.save(chat_id, game, created_by_telegram_user_id=_telegram_user_id(update))
        await message.reply_text(tr("add_success", name=name, buyin=eur(buyin), out=eur(out)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def addblock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_subscription(update):
        return

    services = get_services()
    message = _message(update)
    chat_id = _chat_id(update)
    game = services.store.get(chat_id)
    text = message.text or ""
    parts = text.split("\n", 1)

    if len(parts) == 1:
        await message.reply_text(tr("addblock_usage"), parse_mode=ParseMode.HTML)
        return

    added: list[str] = []
    errors: list[str] = []
    for raw_line in parts[1].splitlines():
        if not raw_line.strip():
            continue
        try:
            name, buyin, out = parse_line(raw_line)
            game.add_or_update(name, buyin, out)
            added.append(name)
        except Exception as exc:
            errors.append(f"{raw_line} -> {exc}")

    services.store.save(chat_id, game, created_by_telegram_user_id=_telegram_user_id(update))

    response_lines = [
        tr("addblock_added", players=", ".join(added)) if added else tr("addblock_added_empty")
    ]
    if errors:
        response_lines.append(tr("addblock_errors", errors="\n".join(errors)))

    await message.reply_text("\n".join(response_lines), parse_mode=ParseMode.HTML)


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_subscription(update):
        return

    services = get_services()
    message = _message(update)
    chat_id = _chat_id(update)
    game = services.store.get(chat_id)

    if not context.args:
        await message.reply_text(tr("remove_usage"))
        return

    if game.remove(normalize_name(context.args[0])):
        services.store.save(chat_id, game, created_by_telegram_user_id=_telegram_user_id(update))
        await message.reply_text(tr("remove_done"))
    else:
        await message.reply_text(tr("remove_missing"))


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_subscription(update):
        return

    services = get_services()
    game = services.store.get(_chat_id(update))
    await _message(update).reply_text(render_table(game), parse_mode=ParseMode.HTML)


async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_subscription(update):
        return

    services = get_services()
    message = _message(update)
    game = services.store.get(_chat_id(update))

    if not game.players:
        await message.reply_text(tr("calc_no_data"))
        return

    balance_error = game.check_balance()
    if balance_error:
        await message.reply_text(balance_error, parse_mode=ParseMode.HTML)
        return

    mode = "direct"
    hub_name: str | None = None
    if context.args:
        mode = context.args[0].lower()
        if len(context.args) > 1:
            hub_name = normalize_name(context.args[1])

    nets = game.nets()
    highlights = build_highlights(nets)

    if mode == "hub":
        hub, transfers = settle_hub(nets, hub_name)
        header = tr("calc_mode_hub", hub=hub)
    else:
        transfers = settle_direct(nets)
        header = tr("calc_mode_direct")

    if not transfers:
        await message.reply_text(tr("calc_no_transfers", highlights=highlights), parse_mode=ParseMode.HTML)
        return

    await message.reply_text(render_transfers(header, highlights, transfers), parse_mode=ParseMode.HTML)


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("subscription", subscription_status))
    application.add_handler(CommandHandler("newgame", newgame))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("addblock", addblock))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("calc", calc))
