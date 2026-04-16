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
from poker_bot.store import GameSession


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


def _require_existing_game(session: GameSession | None) -> GameSession:
    if session is None:
        raise ValueError(tr("no_active_game"))
    return session


def _require_open_game(session: GameSession | None) -> GameSession:
    session = _require_existing_game(session)
    if session.is_closed:
        raise ValueError(tr("game_closed"))
    return session


def _validate_player_limit(session: GameSession) -> None:
    limit = get_services().settings.max_players_per_game
    if len(session.game.players) > limit:
        raise ValueError(tr("player_limit_reached", limit=limit))


def _apply_player_line(session: GameSession, name: str, buyin, out) -> None:
    limit = get_services().settings.max_players_per_game
    if name not in session.game.players and len(session.game.players) >= limit:
        raise ValueError(tr("player_limit_reached", limit=limit))
    session.game.add_or_update(name, buyin, out)
    _validate_player_limit(session)


def _can_finalize_new_game(update: Update, session: GameSession) -> tuple[bool, str | None]:
    services = get_services()
    chat_id = _chat_id(update)
    finalized_games_for_chat = services.store.count_finalized_games_for_chat(chat_id)
    if finalized_games_for_chat < services.settings.free_trial_games_per_chat:
        return True, None

    user_id = _telegram_user_id(update)
    if user_id is None:
        return False, tr("subscription_required_new_calc")

    subscription = services.billing.get_subscription(user_id)
    if not subscription.is_active:
        return False, tr("subscription_required_new_calc")

    games_in_period = services.store.count_finalized_games_for_user_in_period(
        telegram_user_id=user_id,
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
    )
    if games_in_period >= services.settings.max_subscription_games_per_period:
        return False, tr("subscription_period_limit_reached")

    return True, None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    await _message(update).reply_text(tr("start_text"), parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    await _message(update).reply_text(
        tr(
            "help_text",
            subscription_games_limit=get_services().settings.max_subscription_games_per_period,
        ),
        parse_mode=ParseMode.HTML,
    )


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
    _sync_user(update)
    services = get_services()
    services.store.start_new_game(_chat_id(update), created_by_telegram_user_id=_telegram_user_id(update))
    await _message(update).reply_text(tr("newgame_done"))


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    message = _message(update)

    try:
        session = _require_open_game(services.store.get_latest(_chat_id(update)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))
        return

    if not context.args:
        await message.reply_text(tr("add_usage"))
        return

    try:
        name, buyin, out = parse_line(" ".join(context.args))
        _apply_player_line(session, name, buyin, out)
        services.store.save_players(session.id, session.game)
        await message.reply_text(tr("add_success", name=name, buyin=eur(buyin), out=eur(out)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def addblock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    message = _message(update)
    try:
        session = _require_open_game(services.store.get_latest(_chat_id(update)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))
        return

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
            _apply_player_line(session, name, buyin, out)
            added.append(name)
        except Exception as exc:
            errors.append(f"{raw_line} -> {exc}")

    services.store.save_players(session.id, session.game)

    response_lines = [
        tr("addblock_added", players=", ".join(added)) if added else tr("addblock_added_empty")
    ]
    if errors:
        response_lines.append(tr("addblock_errors", errors="\n".join(errors)))

    await message.reply_text("\n".join(response_lines), parse_mode=ParseMode.HTML)


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    message = _message(update)
    try:
        session = _require_open_game(services.store.get_latest(_chat_id(update)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))
        return

    if not context.args:
        await message.reply_text(tr("remove_usage"))
        return

    if session.game.remove(normalize_name(context.args[0])):
        services.store.save_players(session.id, session.game)
        await message.reply_text(tr("remove_done"))
    else:
        await message.reply_text(tr("remove_missing"))


async def remove_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    message = _message(update)
    try:
        session = _require_open_game(services.store.get_latest(_chat_id(update)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))
        return

    session.game.players.clear()
    services.store.save_players(session.id, session.game)
    await message.reply_text(tr("remove_all_done"))


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    session = services.store.get_latest(_chat_id(update))
    if session is None:
        await _message(update).reply_text(tr("no_active_game"))
        return
    await _message(update).reply_text(render_table(session.game), parse_mode=ParseMode.HTML)


async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    message = _message(update)
    session = services.store.get_latest(_chat_id(update))

    if session is None:
        await message.reply_text(tr("no_active_game"))
        return
    if not session.game.players:
        await message.reply_text(tr("calc_no_data"))
        return

    if session.is_open:
        can_finalize, reason = _can_finalize_new_game(update, session)
        if not can_finalize:
            await message.reply_text(reason or tr("subscription_required_new_calc"))
            return

    balance_error = session.game.check_balance()
    if balance_error:
        await message.reply_text(balance_error, parse_mode=ParseMode.HTML)
        return

    mode = "direct"
    hub_name: str | None = None
    if context.args:
        mode = context.args[0].lower()
        if len(context.args) > 1:
            hub_name = normalize_name(context.args[1])

    nets = session.game.nets()
    highlights = build_highlights(nets)

    if mode == "hub":
        hub, transfers = settle_hub(nets, hub_name)
        header = tr("calc_mode_hub", hub=hub)
    else:
        transfers = settle_direct(nets)
        header = tr("calc_mode_direct")

    if session.is_open:
        services.store.complete_game(session.id, finalized_by_telegram_user_id=_telegram_user_id(update))

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
    application.add_handler(CommandHandler("removeAll", remove_all))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("calc", calc))
