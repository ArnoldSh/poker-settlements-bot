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
from poker_bot.store import InMemoryStore

STORE = InMemoryStore()


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _message(update).reply_text(tr("start_text"), parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("help_text")
    await _message(update).reply_text(tr("help_text"), parse_mode=ParseMode.HTML)


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    STORE.reset(_chat_id(update))
    await _message(update).reply_text(tr("newgame_done"))


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = _message(update)
    game = STORE.get(_chat_id(update))

    if not context.args:
        await message.reply_text(tr("add_usage"))
        return

    try:
        name, buyin, out = parse_line(" ".join(context.args))
        game.add_or_update(name, buyin, out)
        await message.reply_text(tr("add_success", name=name, buyin=eur(buyin), out=eur(out)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def addblock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = _message(update)
    game = STORE.get(_chat_id(update))
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

    response_lines = [
        tr("addblock_added", players=", ".join(added)) if added else tr("addblock_added_empty")
    ]
    if errors:
        response_lines.append(tr("addblock_errors", errors="\n".join(errors)))

    await message.reply_text("\n".join(response_lines), parse_mode=ParseMode.HTML)


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = _message(update)
    game = STORE.get(_chat_id(update))

    if not context.args:
        await message.reply_text(tr("remove_usage"))
        return

    if game.remove(normalize_name(context.args[0])):
        await message.reply_text(tr("remove_done"))
    else:
        await message.reply_text(tr("remove_missing"))


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = STORE.get(_chat_id(update))
    await _message(update).reply_text(render_table(game), parse_mode=ParseMode.HTML)


async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = _message(update)
    game = STORE.get(_chat_id(update))

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
    application.add_handler(CommandHandler("newgame", newgame))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("addblock", addblock))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("calc", calc))

