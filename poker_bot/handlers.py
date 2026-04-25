from __future__ import annotations

from io import BytesIO
from datetime import datetime, timedelta, timezone

from telegram import InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from poker_bot.commentary import build_highlights
from poker_bot.domain import Game, settle_direct, settle_hub
from poker_bot.exporting import build_game_csv
from poker_bot.formatting import eur
from poker_bot.i18n import tr
from poker_bot.notifications import AdminRequestNotification
from poker_bot.parsing import normalize_name, parse_line_with_buyin_entries, parse_number_only
from poker_bot.rendering import (
    render_basic_calc_with_stats,
    render_basic_transfers,
    render_calc_with_stats,
    render_history,
    render_saved_groups,
    render_stats_basic,
    render_stats,
    render_balance_analysis,
    render_table,
    render_transfers,
)
from poker_bot.runtime import get_services
from poker_bot.store import GameSession


PLAN_ALIASES = {
    "month": "monthly",
    "monthly": "monthly",
    "1m": "monthly",
    "quarter": "quarterly",
    "quarterly": "quarterly",
    "3m": "quarterly",
    "halfyear": "semiannual",
    "half-year": "semiannual",
    "semiannual": "semiannual",
    "6m": "semiannual",
    "year": "yearly",
    "yearly": "yearly",
    "annual": "yearly",
    "12m": "yearly",
}


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


def _require_user_id(update: Update) -> int:
    user_id = _telegram_user_id(update)
    if user_id is None:
        raise ValueError(tr("missing_user"))
    return user_id


def _require_existing_game(session: GameSession | None) -> GameSession:
    if session is None:
        raise ValueError(tr("no_active_game"))
    return session


def _require_open_game(session: GameSession | None) -> GameSession:
    session = _require_existing_game(session)
    if session.is_closed:
        raise ValueError(tr("game_closed"))
    return session


def _require_named_players(game: Game) -> list[str]:
    player_names = sorted(game.players.keys(), key=str.lower)
    if not player_names:
        raise ValueError(tr("group_players_empty"))
    return player_names


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


def _remaining_free_games(chat_id: int) -> int:
    services = get_services()
    if services.billing.chat_has_subscription_history(chat_id):
        return 0
    first_game_at = services.store.first_game_started_at_for_chat(chat_id)
    if first_game_at is None:
        return services.settings.free_trial_games_per_chat
    if first_game_at.tzinfo is None:
        first_game_at = first_game_at.replace(tzinfo=timezone.utc)
    trial_period_end = first_game_at + timedelta(days=services.settings.free_trial_days)
    if trial_period_end < datetime.now(timezone.utc):
        return 0
    started_games_for_chat = services.store.count_trial_games_for_chat(chat_id, trial_period_end)
    return max(0, services.settings.free_trial_games_per_chat - started_games_for_chat)


def _limits_text(update: Update, subscription=None) -> str:
    if subscription is not None and subscription.is_active:
        return ""
    return tr("limits_status_free_only", free_games_left=_remaining_free_games(_chat_id(update)))


def _join_text(parts: list[str]) -> str:
    return "\n\n".join(part for part in parts if part)


def _can_start_new_game(update: Update) -> tuple[bool, str | None]:
    services = get_services()
    chat_id = _chat_id(update)
    user_id = _telegram_user_id(update)
    if user_id is None:
        return False, _join_text([tr("subscription_required_new_game"), _limits_text(update)])

    subscription = services.billing.refresh_subscription(user_id) if services.billing.enabled else services.billing.get_subscription(user_id)
    if subscription.is_active:
        return True, None

    if services.billing.chat_has_subscription_history(chat_id):
        return False, _join_text([tr("subscription_required_after_subscription"), _limits_text(update, subscription)])

    if _remaining_free_games(chat_id) > 0:
        return True, None

    if not subscription.is_active:
        return False, _join_text([tr("subscription_required_new_game"), _limits_text(update, subscription)])

    return True, None


def _subscription_text(update: Update, subscription) -> str:
    if subscription.is_active:
        plan_name = tr(f"plan_{subscription.plan_code or 'monthly'}")
        if subscription.current_period_end is not None:
            return "\n\n".join(
                [
                    tr(
                        "subscription_status_active",
                        plan=plan_name,
                        date=subscription.current_period_end.strftime("%Y-%m-%d %H:%M UTC"),
                    ),
                ]
            )
        return tr("subscription_status_active_open", plan=plan_name)

    if subscription.status == "pending_activation":
        return _join_text([tr("subscription_status_pending"), _limits_text(update, subscription)])
    if subscription.status == "payment_problem":
        return _join_text([tr("subscription_status_payment_problem"), _limits_text(update, subscription)])
    if subscription.status == "canceled":
        return _join_text([tr("subscription_status_canceled"), _limits_text(update, subscription)])
    if subscription.status == "expired":
        return _join_text([tr("subscription_status_expired"), _limits_text(update, subscription)])
    return _join_text([tr("subscription_status_inactive"), _limits_text(update, subscription)])


def _parse_plan_code(args: list[str]) -> str | None:
    if not args:
        return None
    return PLAN_ALIASES.get(args[0].strip().lower())


def _plan_catalog_text() -> str:
    services = get_services()
    lines = [tr("subscription_plan_choose")]
    for plan_code in services.billing.available_plan_codes():
        lines.append(tr("subscription_plan_item", code=plan_code, label=tr(f"plan_{plan_code}")))
    return "\n".join(lines)


def _get_subscription_for_update(update: Update):
    services = get_services()
    user_id = _telegram_user_id(update)
    if user_id is None:
        return None
    if services.billing.enabled:
        return services.billing.refresh_subscription(user_id)
    return services.billing.get_subscription(user_id)


def _has_premium(update: Update) -> bool:
    subscription = _get_subscription_for_update(update)
    return bool(subscription and subscription.is_active)


def _interactive_player_name(update: Update) -> str:
    user = update.effective_user
    if user is None:
        raise ValueError(tr("missing_user"))
    if user.username:
        return normalize_name(user.username)
    return normalize_name(f"user_{user.id}")


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

    plan_code = _parse_plan_code(context.args)
    if plan_code is None:
        await _message(update).reply_text(_plan_catalog_text())
        return

    checkout_url = services.billing.create_checkout_session(
        telegram_user_id=user.id,
        chat_id=_chat_id(update),
        plan_code=plan_code,
        username=user.username,
        first_name=user.first_name,
    )
    services.store.record_product_event(
        "subscription_checkout_started",
        telegram_user_id=user.id,
        chat_id=_chat_id(update),
        properties={"plan_code": plan_code},
    )
    await _message(update).reply_text(
        tr("subscription_checkout_created", plan=tr(f"plan_{plan_code}"), url=checkout_url)
    )


async def subscription_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = get_services()
    message = _message(update)
    user_id = _sync_user(update)
    if user_id is None:
        await message.reply_text(
            "\n\n".join([tr("subscription_status_inactive"), _limits_text(update)]),
        )
        return

    subscription = services.billing.refresh_subscription(user_id) if services.billing.enabled else services.billing.get_subscription(user_id)
    await message.reply_text(_subscription_text(update, subscription))


async def cancel_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = get_services()
    message = _message(update)
    user = update.effective_user
    user_id = _sync_user(update)
    if user is None or user_id is None:
        await message.reply_text(tr("subscription_cancel_unavailable"))
        return

    subscription = services.billing.refresh_subscription(user_id) if services.billing.enabled else services.billing.get_subscription(user_id)
    if subscription.status not in {"active", "pending_activation", "payment_problem"}:
        await message.reply_text(tr("subscription_cancel_no_subscription"))
        return

    if not services.admin_notifier.enabled:
        await message.reply_text(tr("subscription_cancel_unavailable"))
        return

    subscription = services.billing.mark_cancel_requested(
        telegram_user_id=user_id,
        requested_by_telegram_user_id=user_id,
        source_chat_id=_chat_id(update),
    )
    services.store.record_product_event(
        "subscription_cancel_requested",
        telegram_user_id=user_id,
        chat_id=_chat_id(update),
        properties={"plan_code": subscription.plan_code or "unknown"},
    )
    await services.admin_notifier.notify_request(
        context.bot,
        AdminRequestNotification(
            request_kind="cancel",
            telegram_user_id=user_id,
            username=user.username,
            provider=subscription.provider,
            provider_subscription_id=subscription.stripe_subscription_id,
            local_status=subscription.status,
            provider_status=subscription.provider_status,
            source_chat_id=_chat_id(update),
        ),
    )
    await message.reply_text(tr("subscription_cancel_requested"))


async def refund_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = get_services()
    message = _message(update)
    user = update.effective_user
    user_id = _sync_user(update)
    if user is None or user_id is None:
        await message.reply_text(tr("subscription_refund_unavailable"))
        return

    subscription = services.billing.refresh_subscription(user_id) if services.billing.enabled else services.billing.get_subscription(user_id)
    if subscription.status not in {"active", "pending_activation", "payment_problem", "canceled"}:
        await message.reply_text(tr("subscription_refund_no_subscription"))
        return

    if not services.admin_notifier.enabled:
        await message.reply_text(tr("subscription_refund_unavailable"))
        return

    subscription = services.billing.mark_refund_requested(
        telegram_user_id=user_id,
        requested_by_telegram_user_id=user_id,
        source_chat_id=_chat_id(update),
    )
    services.store.record_product_event(
        "subscription_refund_requested",
        telegram_user_id=user_id,
        chat_id=_chat_id(update),
        properties={"plan_code": subscription.plan_code or "unknown"},
    )
    await services.admin_notifier.notify_request(
        context.bot,
        AdminRequestNotification(
            request_kind="refund",
            telegram_user_id=user_id,
            username=user.username,
            provider=subscription.provider,
            provider_subscription_id=subscription.stripe_subscription_id,
            local_status=subscription.status,
            provider_status=subscription.provider_status,
            source_chat_id=_chat_id(update),
        ),
    )
    await message.reply_text(tr("subscription_refund_requested"))


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    services = get_services()
    can_start, reason = _can_start_new_game(update)
    if not can_start:
        await _message(update).reply_text(reason or tr("subscription_required_new_game"))
        return

    interactive = bool(context.args and context.args[0].strip().lower() == "i")
    session = services.store.start_new_game(
        _chat_id(update),
        created_by_telegram_user_id=_telegram_user_id(update),
        input_mode="interactive" if interactive else "manual",
    )
    services.store.record_product_event(
        "game_started",
        telegram_user_id=user_id,
        chat_id=_chat_id(update),
        game_id=session.id,
        properties={"source": "interactive" if interactive else "empty"},
    )
    subscription = None
    if user_id is not None:
        subscription = (
            services.billing.refresh_subscription(user_id)
            if services.billing.enabled
            else services.billing.get_subscription(user_id)
        )
    await _message(update).reply_text(
        _join_text([tr("newgame_interactive_done") if interactive else tr("newgame_done"), _limits_text(update, subscription)]),
    )


async def finish_interactive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    message = _message(update)
    try:
        session = _require_open_game(services.store.get_latest(_chat_id(update)))
        if not session.is_interactive:
            await message.reply_text(tr("interactive_finish_manual_game"))
            return
        services.store.finish_interactive_buyins(session.id)
        await message.reply_text(tr("interactive_buyins_finished"))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def restart_interactive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    message = _message(update)
    try:
        session = _require_open_game(services.store.get_latest(_chat_id(update)))
        if not session.is_interactive:
            await message.reply_text(tr("interactive_restart_manual_game"))
            return
        rebuilt = services.store.restart_interactive_flow(session.id)
        await message.reply_text(tr("interactive_restart_done", players=len(rebuilt.game.players)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def savegroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    message = _message(update)
    try:
        owner_user_id = _require_user_id(update)
        group_name = " ".join(context.args).strip()
        if not group_name:
            await message.reply_text(tr("savegroup_usage"))
            return
        session = _require_existing_game(services.store.get_latest(_chat_id(update)))
        player_names = _require_named_players(session.game)
        services.store.save_group(owner_user_id, group_name, player_names)
        services.store.record_product_event(
            "saved_group_created",
            telegram_user_id=owner_user_id,
            chat_id=_chat_id(update),
            game_id=session.id,
            properties={"group_name": group_name, "player_count": len(player_names)},
        )
        await message.reply_text(tr("savegroup_done", name=group_name, count=len(player_names)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def groups_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    message = _message(update)
    try:
        owner_user_id = _require_user_id(update)
        groups = get_services().store.list_saved_groups(owner_user_id)
        await message.reply_text(render_saved_groups(groups))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    services = get_services()
    message = _message(update)
    can_start, reason = _can_start_new_game(update)
    if not can_start:
        await message.reply_text(reason or tr("subscription_required_new_game"))
        return

    try:
        owner_user_id = _require_user_id(update)
        group_name = " ".join(context.args).strip()
        if not group_name:
            await message.reply_text(tr("startgame_usage"))
            return
        group = services.store.get_saved_group(owner_user_id, group_name)
        if group is None:
            await message.reply_text(tr("startgame_missing_group", name=group_name))
            return
        if len(group.player_names) > services.settings.max_players_per_game:
            await message.reply_text(tr("player_limit_reached", limit=services.settings.max_players_per_game))
            return
        session = services.store.start_new_game(
            _chat_id(update),
            created_by_telegram_user_id=user_id,
            player_names=group.player_names,
        )
        services.store.record_product_event(
            "game_started_from_saved_group",
            telegram_user_id=user_id,
            chat_id=_chat_id(update),
            game_id=session.id,
            properties={"group_name": group_name, "player_count": len(group.player_names)},
        )
        subscription = services.billing.refresh_subscription(user_id) if (user_id and services.billing.enabled) else None
        await message.reply_text(
            "\n\n".join(
                [
                    tr("startgame_done", name=group_name, players=", ".join(group.player_names)),
                    _limits_text(update, subscription),
                ]
            )
        )
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def revanche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    services = get_services()
    message = _message(update)
    can_start, reason = _can_start_new_game(update)
    if not can_start:
        await message.reply_text(reason or tr("subscription_required_new_game"))
        return

    latest_closed = services.store.get_latest_closed(_chat_id(update))
    if latest_closed is None:
        await message.reply_text(tr("revanche_missing"))
        return

    player_names = sorted(latest_closed.game.players.keys(), key=str.lower)
    if len(player_names) > services.settings.max_players_per_game:
        await message.reply_text(tr("player_limit_reached", limit=services.settings.max_players_per_game))
        return

    session = services.store.start_new_game(
        _chat_id(update),
        created_by_telegram_user_id=user_id,
        player_names=player_names,
    )
    services.store.record_product_event(
        "game_started_revanche",
        telegram_user_id=user_id,
        chat_id=_chat_id(update),
        game_id=session.id,
        properties={"player_count": len(player_names), "source_game_id": latest_closed.id},
    )
    subscription = services.billing.refresh_subscription(user_id) if (user_id and services.billing.enabled) else None
    await message.reply_text(
        "\n\n".join([tr("revanche_done", players=", ".join(player_names)), _limits_text(update, subscription)])
    )


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
        raw_line = " ".join(context.args)
        name, buyin, out, buyin_entries = parse_line_with_buyin_entries(raw_line)
        _apply_player_line(session, name, buyin, out)
        services.store.save_players_and_manual_buyins(
            session.id,
            session.game,
            {name: buyin_entries},
            source_message_id=message.message_id,
            raw_text_by_player={name: raw_line},
        )
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
    buyins_by_player = {}
    raw_text_by_player = {}
    for raw_line in parts[1].splitlines():
        if not raw_line.strip():
            continue
        try:
            name, buyin, out, buyin_entries = parse_line_with_buyin_entries(raw_line)
            _apply_player_line(session, name, buyin, out)
            buyins_by_player[name] = buyin_entries
            raw_text_by_player[name] = raw_line
            added.append(name)
        except Exception as exc:
            errors.append(f"{raw_line} -> {exc}")

    services.store.save_players_and_manual_buyins(
        session.id,
        session.game,
        buyins_by_player,
        source_message_id=message.message_id,
        raw_text_by_player=raw_text_by_player,
    )

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
    if session.is_interactive:
        await message.reply_text(tr("remove_interactive_unavailable"))
        return

    if not context.args:
        await message.reply_text(tr("remove_usage"))
        return

    player_name = normalize_name(context.args[0])
    if session.game.remove(player_name):
        services.store.save_players(session.id, session.game)
        services.store.delete_manual_buyins_for_player(session.id, player_name)
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
    if session.is_interactive:
        await message.reply_text(tr("remove_interactive_unavailable"))
        return

    session.game.players.clear()
    services.store.save_players(session.id, session.game)
    services.store.delete_manual_buyins_for_game(session.id)
    await message.reply_text(tr("remove_all_done"))


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    session = services.store.get_latest(_chat_id(update))
    if session is None:
        await _message(update).reply_text(tr("no_active_game"))
        return
    response = render_table(session.game)
    analysis_requested = bool(context.args and context.args[0].strip().lower() in {"a", "analysis"})
    if analysis_requested and session.game.check_balance():
        if _has_premium(update):
            entries = services.store.list_game_amount_entries(session.id)
            response = f"{response}\n\n{render_balance_analysis(session.game, entries)}"
        else:
            response = f"{response}\n\n{tr('list_analysis_premium_required')}"
    await _message(update).reply_text(response, parse_mode=ParseMode.HTML)


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    try:
        limit = int(context.args[0]) if context.args else 5
    except ValueError:
        limit = 5
    limit = min(max(limit, 1), 20)
    entries = services.store.list_closed_games(_chat_id(update), limit=limit)
    await _message(update).reply_text(render_history(entries))


async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _sync_user(update)
    services = get_services()
    message = _message(update)
    session = services.store.get_latest(_chat_id(update))

    if session is None:
        await message.reply_text(tr("no_active_game"))
        return
    if session.is_interactive and session.interactive_phase == "buyin":
        await message.reply_text(tr("interactive_calc_before_finish"))
        return
    if not session.game.players:
        await message.reply_text(tr("calc_no_data"))
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
    premium_enabled = _has_premium(update)
    highlights = build_highlights(nets) if premium_enabled else ""
    chat_stats = services.store.build_chat_player_stats(_chat_id(update))
    stats_text = render_stats(chat_stats) if premium_enabled else render_stats_basic(chat_stats)

    if mode == "hub":
        hub, transfers = settle_hub(nets, hub_name)
        header = tr("calc_mode_hub", hub=hub)
    else:
        transfers = settle_direct(nets)
        header = tr("calc_mode_direct")

    if session.is_open:
        services.store.complete_game(session.id, finalized_by_telegram_user_id=_telegram_user_id(update))
        services.store.record_product_event(
            "game_calculated",
            telegram_user_id=user_id,
            chat_id=_chat_id(update),
            game_id=session.id,
            properties={
                "mode": mode,
                "player_count": len(session.game.players),
                "transfer_count": len(transfers),
            },
        )

    if not transfers:
        if premium_enabled:
            await message.reply_text(
                f"{tr('calc_no_transfers', highlights=highlights)}\n\n{stats_text}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.reply_text(f"{tr('calc_no_transfers_basic')}\n\n{stats_text}", parse_mode=ParseMode.HTML)
        return

    if premium_enabled:
        await message.reply_text(
            render_calc_with_stats(header, highlights, session.game, transfers, stats_text),
            parse_mode=ParseMode.HTML,
        )
        return

    await message.reply_text(
        render_basic_calc_with_stats(header, transfers, stats_text),
        parse_mode=ParseMode.HTML,
    )


async def export_csv_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    message = _message(update)
    session = services.store.get_latest_closed(_chat_id(update))
    if session is None:
        await message.reply_text(tr("history_empty"))
        return

    balance_error = session.game.check_balance()
    if balance_error:
        await message.reply_text(balance_error, parse_mode=ParseMode.HTML)
        return

    transfers = settle_direct(session.game.nets())
    payload = build_game_csv(session.game, transfers)
    filename = f"poker_game_{session.id}.csv"
    await message.reply_document(document=InputFile(BytesIO(payload), filename=filename))


async def interactive_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    services = get_services()
    message = _message(update)
    session = services.store.get_latest(_chat_id(update))
    if session is None or not session.is_open or not session.is_interactive:
        return

    amount = parse_number_only(message.text or "")
    if amount is None:
        return

    phase = session.interactive_phase
    if phase not in {"buyin", "out"}:
        return

    try:
        rebuilt = services.store.save_interactive_message(
            session_id=session.id,
            chat_id=_chat_id(update),
            telegram_message_id=message.message_id,
            telegram_user_id=_telegram_user_id(update),
            player_name=_interactive_player_name(update),
            phase=phase,
            amount=amount,
            raw_text=message.text or "",
        )
        if rebuilt is not None:
            services.store.record_product_event(
                "interactive_game_message_recorded",
                telegram_user_id=_telegram_user_id(update),
                chat_id=_chat_id(update),
                game_id=session.id,
                properties={"phase": phase},
            )
    except Exception:
        return


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("sub", subscribe))
    application.add_handler(CommandHandler("sub_status", subscription_status))
    application.add_handler(CommandHandler("sub_cancel", cancel_subscription))
    application.add_handler(CommandHandler("sub_refund", refund_subscription))
    application.add_handler(CommandHandler("newgame", newgame))
    application.add_handler(CommandHandler("finish", finish_interactive))
    application.add_handler(CommandHandler("restart", restart_interactive))
    application.add_handler(CommandHandler("savegroup", savegroup))
    application.add_handler(CommandHandler("groups", groups_cmd))
    application.add_handler(CommandHandler("startgame", startgame))
    application.add_handler(CommandHandler("revanche", revanche))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("addblock", addblock))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(CommandHandler("removeAll", remove_all))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("history", history_cmd))
    application.add_handler(CommandHandler("export_csv", export_csv_cmd))
    application.add_handler(CommandHandler("calc", calc))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, interactive_message))
    application.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & filters.TEXT & ~filters.COMMAND, interactive_message))
