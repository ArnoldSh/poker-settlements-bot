from __future__ import annotations

from io import BytesIO
from datetime import datetime, timedelta, timezone

from telegram import InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from poker_bot.commentary import build_highlights
from poker_bot.domain import Game, settle_direct, settle_hub
from poker_bot.exporting import build_game_csv
from poker_bot.formatting import eur
from poker_bot.history_import import (
    build_dry_run_report,
    import_games,
    parse_history_dump,
    parse_import_command_request,
    summarize_games,
)
from poker_bot.i18n import tr
from poker_bot.billing import PAYMENT_PROBLEM_SUBSCRIPTION_STATUSES
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
from poker_bot.subscription_plans import parse_limit_boost_code, parse_plan_code


def _chat_id(update: Update) -> int:
    chat = update.effective_chat
    if chat is None:
        raise ValueError(tr("missing_chat"))
    return chat.id


def _is_private_chat(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.type == "private"


def _is_group_chat(update: Update) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.type in {"group", "supergroup"}


def _is_super_admin_update(update: Update) -> bool:
    return get_services().entitlements.is_super_admin(_telegram_user_id(update))


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


def _import_target_chat_id(update: Update, requested_chat_id: int | None) -> int:
    if requested_chat_id is not None:
        return requested_chat_id
    if _is_private_chat(update):
        raise ValueError(tr("importhistory_chat_id_required"))
    return _chat_id(update)
    _validate_player_limit(session)


def _apply_buyin_entry(session: GameSession, name: str, amount) -> None:
    limit = get_services().settings.max_players_per_game
    player = session.game.players.get(name)
    if player is None:
        if len(session.game.players) >= limit:
            raise ValueError(tr("player_limit_reached", limit=limit))
        session.game.add_or_update(name, amount, 0)
        return
    session.game.add_or_update(name, player.buyin + amount, player.out)
    _validate_player_limit(session)


def _apply_out_value(session: GameSession, name: str, amount) -> None:
    limit = get_services().settings.max_players_per_game
    player = session.game.players.get(name)
    if player is None:
        if len(session.game.players) >= limit:
            raise ValueError(tr("player_limit_reached", limit=limit))
        session.game.add_or_update(name, 0, amount)
        return
    session.game.add_or_update(name, player.buyin, amount)
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


def _limits_text(update: Update, subscription=None, user_id: int | None = None) -> str:
    services = get_services()
    user_id = _telegram_user_id(update) if user_id is None else user_id
    chat_id = _chat_id(update)
    if services.entitlements.is_billing_exempt(user_id, chat_id) or services.billing.chat_has_active_subscription(chat_id):
        return ""
    return tr("limits_status_free_only", free_games_left=_remaining_free_games(chat_id))


def _join_text(parts: list[str]) -> str:
    return "\n\n".join(part for part in parts if part)


def _chat_usage_window_start() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=30)


def _usage_limit_text(kind: str, used: int, limit: int) -> str:
    if kind == "games":
        return tr("chat_usage_closed_games_limit_reached", used=used, limit=limit)
    return tr("chat_usage_unique_players_limit_reached", used=used, limit=limit)


def _usage_warning_text(kind: str, used: int, limit: int) -> str:
    if kind == "games":
        return tr("chat_usage_closed_games_warning", used=used, limit=limit)
    return tr("chat_usage_unique_players_warning", used=used, limit=limit)


def _chat_usage_gate(update: Update) -> tuple[bool, str | None, str | None]:
    services = get_services()
    user_id = _telegram_user_id(update)
    chat_id = _chat_id(update)
    if services.entitlements.is_billing_exempt(user_id, chat_id):
        return True, None, None

    subscription = services.billing.get_chat_subscription(chat_id)
    if subscription is None or not subscription.is_active:
        return True, None, None

    limits = services.billing.get_effective_plan_limits(chat_id, subscription.plan_code)
    if limits is None:
        return True, None, None

    since = _chat_usage_window_start()
    closed_games = services.store.count_closed_games_for_chat_since(chat_id, since)
    unique_players = services.store.count_unique_players_for_chat_since(chat_id, since)

    if closed_games >= limits.closed_games_30d_limit:
        return False, _usage_limit_text("games", closed_games, limits.closed_games_30d_limit), None
    if unique_players >= limits.unique_players_30d_limit:
        return False, _usage_limit_text("players", unique_players, limits.unique_players_30d_limit), None

    threshold = services.settings.chat_usage_warning_threshold
    warnings: list[str] = []
    if closed_games + 1 >= limits.closed_games_30d_limit * threshold:
        warnings.append(_usage_warning_text("games", closed_games + 1, limits.closed_games_30d_limit))
    if unique_players >= limits.unique_players_30d_limit * threshold:
        warnings.append(_usage_warning_text("players", unique_players, limits.unique_players_30d_limit))
    return True, None, "\n\n".join(warnings)


def _can_start_new_game(update: Update) -> tuple[bool, str | None]:
    services = get_services()
    chat_id = _chat_id(update)
    user_id = _telegram_user_id(update)
    if _is_private_chat(update) and not services.entitlements.is_super_admin(user_id):
        return False, tr("private_chat_info_board")
    if not _is_group_chat(update) and not services.entitlements.is_super_admin(user_id):
        return False, tr("group_chat_required")
    if user_id is None:
        return False, _join_text([tr("subscription_required_new_game"), _limits_text(update)])

    if services.entitlements.is_billing_exempt(user_id, chat_id):
        return True, None

    if services.billing.chat_has_active_subscription(chat_id):
        allowed, reason, _warning = _chat_usage_gate(update)
        if not allowed:
            return False, reason
        return True, None

    if services.billing.chat_has_subscription_history(chat_id):
        return False, _join_text([tr("subscription_required_after_subscription"), _limits_text(update, None, user_id)])

    if _remaining_free_games(chat_id) > 0:
        return True, None

    if not services.billing.chat_has_active_subscription(chat_id):
        return False, _join_text([tr("subscription_required_new_game"), _limits_text(update, None, user_id)])

    return True, None


def _subscription_text(update: Update, subscription, user_id: int | None = None) -> str:
    services = get_services()
    user_id = _telegram_user_id(update) if user_id is None else user_id
    chat_id = _chat_id(update)
    if services.entitlements.is_billing_exempt(user_id, chat_id):
        return tr("subscription_status_admin")

    if subscription and subscription.is_active and subscription.requested_chat_id == chat_id:
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

    if subscription is None:
        return _join_text([tr("subscription_status_inactive"), _limits_text(update, subscription)])
    if subscription.status == "pending_activation":
        return _join_text([tr("subscription_status_pending"), _limits_text(update, subscription)])
    if subscription.status in PAYMENT_PROBLEM_SUBSCRIPTION_STATUSES:
        return _join_text([tr("subscription_status_payment_problem"), _limits_text(update, subscription)])
    if subscription.status == "canceled":
        return _join_text([tr("subscription_status_canceled"), _limits_text(update, subscription)])
    if subscription.status == "expired":
        return _join_text([tr("subscription_status_expired"), _limits_text(update, subscription)])
    return _join_text([tr("subscription_status_inactive"), _limits_text(update, subscription)])


def _parse_plan_code(args: list[str]) -> str | None:
    return parse_plan_code(args)


def _plan_catalog_text() -> str:
    services = get_services()
    lines = [tr("subscription_plan_choose")]
    for item in services.billing.available_plan_aliases():
        lines.append(
            tr(
                "subscription_plan_item_priced",
                code=item.alias,
                period=tr(f"plan_period_{item.code}"),
                price=item.price or tr("price_unknown"),
            )
        )
    return "\n".join(lines)


def _limit_boost_catalog_text() -> str:
    services = get_services()
    lines = [tr("limit_boost_choose")]
    for item in services.billing.available_limit_boost_aliases():
        lines.append(
            tr(
                "limit_boost_item",
                code=item.alias,
                period=tr(f"limit_boost_period_{item.code}"),
                price=item.price or tr("price_unknown"),
            )
        )
    return "\n".join(lines)


def _get_subscription_for_update(update: Update):
    services = get_services()
    user_id = _telegram_user_id(update)
    if user_id is None:
        return None
    if services.entitlements.is_billing_exempt(user_id, _chat_id(update)):
        return None
    if services.billing.enabled:
        return services.billing.refresh_subscription(user_id)
    return services.billing.get_subscription(user_id)


def _has_premium(update: Update) -> bool:
    services = get_services()
    user_id = _telegram_user_id(update)
    chat_id = _chat_id(update)
    if services.entitlements.is_billing_exempt(user_id, chat_id):
        return True
    return services.billing.chat_has_active_subscription(chat_id)


async def _reply_private_info_for_non_admin(update: Update) -> bool:
    if _is_private_chat(update) and not _is_super_admin_update(update):
        await _message(update).reply_text(tr("private_chat_info_board"), parse_mode=ParseMode.HTML)
        return True
    return False


def _premium_feature_enabled(feature: str) -> bool:
    return get_services().features.is_enabled(feature)


def _help_text() -> str:
    plan_lines = _plan_catalog_text().splitlines()[1:]
    boost_lines = _limit_boost_catalog_text().splitlines()[1:]

    lines = [
        "<b>Покерные расчеты в Telegram</b>",
        "",
        "<b>Где работает бот</b>",
        "Игровые команды работают в группах. В личной переписке для обычных пользователей доступна только справка.",
        "Подписка покупается из той группы, где должен работать бот, и действует только в этой группе.",
        "Играть в оплаченной группе могут все участники. Управлять подпиской может только пользователь, который ее оформил.",
        "",
        "<b>Обычный режим</b>",
        "/newgame - новая пустая игра",
        "/add [@user] &lt;sum&gt; - добавить закуп",
        "/out [@user] &lt;sum&gt; - зафиксировать выход",
        "/addAll - задать игроков блоком",
        "/remove [@user] - удалить игрока",
        "/removeAll - удалить всех игроков",
        "",
        "<b>Итоги и анализ</b>",
        "/list - текущая таблица",
        "/stats - статистика игроков по чату",
    ]
    if _premium_feature_enabled("analyze"):
        lines.append("/analyze - таблица и анализ расхождения")
    lines.append("/calc [direct|hub] [@hub] - закрыть игру и посчитать переводы")
    if _premium_feature_enabled("history"):
        lines.append("/history [N] - история последних игр")
    if _premium_feature_enabled("export_csv"):
        lines.append("/export_csv - выгрузить последнюю закрытую игру в CSV")

    lines.extend(
        [
            "",
            "<b>Подписки и лимиты</b>",
            "/sub - планы подписки",
            *plan_lines,
            "",
            "/sub_status - статус подписки этого чата",
            "/sub_cancel - отменить подписку, только владелец",
        ]
    )
    if _premium_feature_enabled("sub_refund"):
        lines.append("/sub_refund - запросить рефанд, только владелец")
    lines.extend(
        [
            "",
            "/boost - пакеты увеличения лимитов x2",
            *boost_lines,
            "",
            "/limits - текущие лимиты и использование за 30 дней",
            "",
            "<b>Форматы ввода</b>",
            "<code>/add 20</code>",
            "<code>/add @ivan -5</code>",
            "<code>/out 136.20</code>",
            "<code>/out @ivan 136.20</code>",
            "<code>/addAll\n@ivan 20 40 40 -> 133.50</code>",
            "В /addAll можно писать по одному игроку на строку.",
        ]
    )
    return "\n".join(lines)

    lines = [
        "<b>Покерные расчеты в Telegram</b>",
        "",
        "<b>Где работает бот</b>",
        "Игровые команды работают в группах. В личной переписке для обычных пользователей доступна только эта справка.",
        "Подписка покупается из той группы, где должен работать бот, и действует только в этой группе.",
        "Играть в оплаченной группе могут все участники. Управлять подпиской может только пользователь, который ее оформил.",
        "",
        "<b>Обычный режим</b>",
        "/newgame - новая пустая игра",
        "/startgame &lt;название&gt; - новая игра из сохраненной компании",
    ]
    if _premium_feature_enabled("revanche"):
        lines.append("/revanche - новая игра с составом прошлой закрытой игры")
    if _premium_feature_enabled("savegroup"):
        lines.append("/savegroup &lt;название&gt; - сохранить текущий состав")
    if _premium_feature_enabled("groups"):
        lines.append("/groups - список сохраненных компаний")
    lines.extend(
        [
            "/add &lt;строка&gt; - добавить или обновить игрока",
            "/addblock - добавить игроков блоком",
            "/remove @user - удалить игрока",
            "/removeAll - удалить всех игроков",
            "/list - текущая таблица",
        ]
    )
    if _premium_feature_enabled("analyze"):
        lines.append("/analyze - таблица и premium-анализ расхождения")
    lines.append("/calc [direct|hub] [@hub] - закрыть игру и посчитать переводы")
    if _premium_feature_enabled("history"):
        lines.append("/history [N] - история последних игр")
    if _premium_feature_enabled("export_csv"):
        lines.append("/export_csv - выгрузить последнюю закрытую игру в CSV")
    lines.append("/limits - текущие лимиты и использование за 30 дней")

    lines.extend(
        [
            "",
            "<b>Интерактивный режим</b>",
            "/newgame i - начать сбор входов и выходов сообщениями",
            "/finish - завершить этап входов и перейти к выходам",
            "/restart - пересобрать интерактивную игру из сообщений",
            "/list - проверить текущую таблицу",
            "/calc [direct|hub] [@hub] - закрыть игру и посчитать переводы",
            "",
            "<b>Подписка</b>",
            "/sub - планы подписки",
            "/sub 1m, /sub 3m, /sub 6m, /sub 1y - оформить подписку для этого чата",
            "/sub_status - статус подписки этого чата",
            "/sub_cancel - отменить подписку, только владелец",
        ]
    )
    lines.append("/boost - пакеты увеличения лимитов x2")
    lines.append("/boost 1m - купить boost на 1 месяц для этого чата")
    lines.append("/boost 3m - купить boost на 3 месяца для этого чата")
    lines.append("/boost 6m - купить boost на 6 месяцев для этого чата")
    lines.append("/boost 1y - купить boost на 1 год для этого чата")
    if _premium_feature_enabled("sub_refund"):
        lines.append("/sub_refund - запросить рефанд, только владелец")
    lines.extend(
        [
            "",
            "<b>Форматы ввода</b>",
            "<code>/add @ivan 100</code>",
            "<code>/add @ivan 100, 20</code>",
            "<code>/add @ivan 10+20+20</code>",
            "<code>/add @ivan 10+20+20, 50</code>",
            "В /addblock можно писать по одному игроку на строку.",
        ]
    )
    return "\n".join(lines)


def _interactive_player_name(update: Update) -> str:
    user = update.effective_user
    if user is None:
        raise ValueError(tr("missing_user"))
    if user.username:
        return normalize_name(user.username)
    return normalize_name(f"user_{user.id}")


def _command_author_player_name(update: Update) -> str:
    user = update.effective_user
    if user is None:
        raise ValueError(tr("missing_user"))
    if not user.username:
        raise ValueError(tr("missing_username"))
    return normalize_name(user.username)


def _player_and_amount_from_args(update: Update, args: list[str]) -> tuple[str, str]:
    if not args:
        raise ValueError(tr("parse_line_format"))
    if len(args) == 1:
        return _command_author_player_name(update), args[0]
    if args[0].startswith("@"):
        return normalize_name(args[0]), " ".join(args[1:])
    return _command_author_player_name(update), " ".join(args)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    if await _reply_private_info_for_non_admin(update):
        return
    await _message(update).reply_text(_help_text(), parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _sync_user(update)
    if await _reply_private_info_for_non_admin(update):
        return
    await _message(update).reply_text(_help_text(), parse_mode=ParseMode.HTML)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = get_services()
    user = update.effective_user
    message = _message(update)
    chat_id = _chat_id(update)
    if user is None:
        await message.reply_text(tr("subscription_checkout_unavailable"))
        return

    if await _reply_private_info_for_non_admin(update):
        return
    if not _is_group_chat(update) and not services.entitlements.is_super_admin(user.id):
        await message.reply_text(tr("group_chat_required"))
        return

    if not services.billing.enabled:
        await message.reply_text(tr("subscription_checkout_unavailable"))
        return

    chat_subscription = services.billing.get_chat_subscription(chat_id)
    if chat_subscription is not None and chat_subscription.telegram_user_id != user.id:
        await message.reply_text(tr("subscription_chat_already_bound"))
        return

    user_subscription = services.billing.refresh_subscription(user.id) if services.billing.enabled else services.billing.get_subscription(user.id)
    if (
        user_subscription.status in {"active", "pending_activation", *PAYMENT_PROBLEM_SUBSCRIPTION_STATUSES}
        and user_subscription.requested_chat_id is not None
        and user_subscription.requested_chat_id != chat_id
        and not services.entitlements.is_super_admin(user.id)
    ):
        await message.reply_text(tr("subscription_user_bound_to_other_chat"))
        return

    plan_code = _parse_plan_code(context.args)
    if plan_code is None:
        await message.reply_text(_plan_catalog_text())
        return

    try:
        checkout_url = services.billing.create_checkout_session(
            telegram_user_id=user.id,
            chat_id=chat_id,
            plan_code=plan_code,
            username=user.username,
            first_name=user.first_name,
        )
    except ValueError:
        await message.reply_text(tr("subscription_plan_unavailable"))
        return
    services.store.record_product_event(
        "subscription_checkout_started",
        telegram_user_id=user.id,
        chat_id=chat_id,
        properties={"plan_code": plan_code},
    )
    await message.reply_text(
        tr("subscription_checkout_created", plan=tr(f"plan_{plan_code}"), url=checkout_url)
    )


async def limit_boost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = get_services()
    user = update.effective_user
    message = _message(update)
    chat_id = _chat_id(update)
    if user is None:
        await message.reply_text(tr("limit_boost_checkout_unavailable"))
        return

    if await _reply_private_info_for_non_admin(update):
        return
    if not _is_group_chat(update) and not services.entitlements.is_super_admin(user.id):
        await message.reply_text(tr("group_chat_required"))
        return

    if not services.billing.enabled:
        await message.reply_text(tr("limit_boost_checkout_unavailable"))
        return

    boost_code = parse_limit_boost_code(context.args)
    if boost_code is None:
        await message.reply_text(_limit_boost_catalog_text())
        return

    chat_subscription = services.billing.get_chat_subscription(chat_id)
    if chat_subscription is None or not chat_subscription.is_active:
        await message.reply_text(tr("limit_boost_active_subscription_required"))
        return
    if chat_subscription.telegram_user_id != user.id:
        await message.reply_text(tr("subscription_owner_only"))
        return

    active_boost = services.billing.get_active_limit_boost(chat_id)
    if active_boost is not None and active_boost.expires_at is not None:
        await message.reply_text(
            tr("limit_boost_already_active", expires_at=active_boost.expires_at.strftime("%Y-%m-%d %H:%M UTC"))
        )
        return

    try:
        checkout_url = services.billing.create_limit_boost_checkout_session(
            telegram_user_id=user.id,
            chat_id=chat_id,
            boost_code=boost_code,
            username=user.username,
            first_name=user.first_name,
        )
    except ValueError as exc:
        reason = str(exc)
        if reason == "active_limit_boost_exists":
            await message.reply_text(tr("limit_boost_already_active_unknown"))
        elif reason == "active_subscription_required":
            await message.reply_text(tr("limit_boost_active_subscription_required"))
        else:
            await message.reply_text(tr("limit_boost_plan_unavailable"))
        return

    services.store.record_product_event(
        "limit_boost_checkout_started",
        telegram_user_id=user.id,
        chat_id=chat_id,
        properties={"boost_code": boost_code},
    )
    await message.reply_text(
        tr("limit_boost_checkout_created", boost=tr(f"limit_boost_{boost_code}"), url=checkout_url)
    )


async def subscription_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = get_services()
    message = _message(update)
    if await _reply_private_info_for_non_admin(update):
        return
    user_id = _sync_user(update)
    if user_id is None:
        await message.reply_text(
            "\n\n".join([tr("subscription_status_inactive"), _limits_text(update)]),
        )
        return

    chat_subscription = services.billing.get_chat_subscription(_chat_id(update))
    if chat_subscription is not None and chat_subscription.telegram_user_id != user_id:
        await message.reply_text(
            tr("subscription_status_chat_active")
            if chat_subscription.is_active
            else tr("subscription_status_chat_pending")
        )
        return

    subscription = chat_subscription or _get_subscription_for_update(update)
    await message.reply_text(_subscription_text(update, subscription, user_id))


async def cancel_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = get_services()
    message = _message(update)
    user = update.effective_user
    user_id = _sync_user(update)
    if await _reply_private_info_for_non_admin(update):
        return
    if user is None or user_id is None:
        await message.reply_text(tr("subscription_cancel_unavailable"))
        return

    if not services.billing.enabled:
        await message.reply_text(tr("subscription_cancel_unavailable"))
        return

    chat_subscription = services.billing.get_chat_subscription(_chat_id(update))
    if chat_subscription is None or chat_subscription.telegram_user_id != user_id:
        await message.reply_text(tr("subscription_owner_only"))
        return

    subscription = services.billing.refresh_subscription(user_id)
    if subscription.status not in {"active", "pending_activation", *PAYMENT_PROBLEM_SUBSCRIPTION_STATUSES}:
        await message.reply_text(tr("subscription_cancel_no_subscription"))
        return

    if not subscription.stripe_subscription_id:
        await message.reply_text(tr("subscription_cancel_no_subscription"))
        return

    try:
        subscription = services.billing.cancel_subscription(
            telegram_user_id=user_id,
            requested_by_telegram_user_id=user_id,
            source_chat_id=_chat_id(update),
        )
    except ValueError as exc:
        await message.reply_text(str(exc))
        return
    except Exception:
        await message.reply_text(tr("subscription_cancel_unavailable"))
        return

    services.store.record_product_event(
        "subscription_cancel_requested",
        telegram_user_id=user_id,
        chat_id=_chat_id(update),
        properties={"plan_code": subscription.plan_code or "unknown"},
    )
    await message.reply_text(tr("subscription_cancel_requested"))


async def refund_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services = get_services()
    message = _message(update)
    user = update.effective_user
    user_id = _sync_user(update)
    if await _reply_private_info_for_non_admin(update):
        return
    if user is None or user_id is None:
        await message.reply_text(tr("subscription_refund_unavailable"))
        return

    chat_subscription = services.billing.get_chat_subscription(_chat_id(update))
    if chat_subscription is None or chat_subscription.telegram_user_id != user_id:
        await message.reply_text(tr("subscription_owner_only"))
        return

    subscription = services.billing.refresh_subscription(user_id) if services.billing.enabled else services.billing.get_subscription(user_id)
    if subscription.status not in {"active", "pending_activation", "canceled", *PAYMENT_PROBLEM_SUBSCRIPTION_STATUSES}:
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

    session = services.store.start_new_game(
        _chat_id(update),
        created_by_telegram_user_id=_telegram_user_id(update),
        input_mode="manual",
    )
    services.store.record_product_event(
        "game_started",
        telegram_user_id=user_id,
        chat_id=_chat_id(update),
        game_id=session.id,
        properties={"source": "empty"},
    )
    subscription = _get_subscription_for_update(update)
    _allowed, _reason, usage_warning = _chat_usage_gate(update)
    await _message(update).reply_text(
        _join_text(
            [
                tr("newgame_done"),
                usage_warning or "",
                _limits_text(update, subscription, user_id),
            ]
        ),
    )


async def finish_interactive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
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
    if await _reply_private_info_for_non_admin(update):
        return
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
    if await _reply_private_info_for_non_admin(update):
        return
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
    if await _reply_private_info_for_non_admin(update):
        return
    _sync_user(update)
    message = _message(update)
    try:
        owner_user_id = _require_user_id(update)
        groups = get_services().store.list_saved_groups(owner_user_id)
        await message.reply_text(render_saved_groups(groups))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
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
        subscription = _get_subscription_for_update(update)
        _allowed, _reason, usage_warning = _chat_usage_gate(update)
        await message.reply_text(
            _join_text(
                [
                    tr("startgame_done", name=group_name, players=", ".join(group.player_names)),
                    usage_warning or "",
                    _limits_text(update, subscription, user_id),
                ]
            )
        )
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def revanche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
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
    subscription = _get_subscription_for_update(update)
    _allowed, _reason, usage_warning = _chat_usage_gate(update)
    await message.reply_text(
        _join_text(
            [
                tr("revanche_done", players=", ".join(player_names)),
                usage_warning or "",
                _limits_text(update, subscription, user_id),
            ]
        )
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
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
        name, amount_expr = _player_and_amount_from_args(update, context.args)
        amount = parse_number_only(amount_expr)
        if amount is None:
            await message.reply_text(tr("add_usage"))
            return
        _apply_buyin_entry(session, name, amount)
        services.store.save_players_and_add_manual_buyin(
            session.id,
            session.game,
            name,
            amount,
            source_message_id=message.message_id,
            raw_text=" ".join(context.args),
        )
        await message.reply_text(
            tr(
                "add_adjustment_success" if amount < 0 else "add_success",
                name=name,
                amount=eur(amount),
                buyin=eur(session.game.players[name].buyin),
            )
        )
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def out(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
    _sync_user(update)
    services = get_services()
    message = _message(update)

    try:
        session = _require_open_game(services.store.get_latest(_chat_id(update)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))
        return

    if not context.args:
        await message.reply_text(tr("out_usage"))
        return

    try:
        name, amount_expr = _player_and_amount_from_args(update, context.args)
        amount = parse_number_only(amount_expr)
        if amount is None:
            await message.reply_text(tr("out_usage"))
            return
        _apply_out_value(session, name, amount)
        services.store.save_players(session.id, session.game)
        await message.reply_text(tr("out_success", name=name, out=eur(amount)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def add_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
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
        await message.reply_text(tr("addall_usage"), parse_mode=ParseMode.HTML)
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
        tr("addall_added", players=", ".join(added)) if added else tr("addall_added_empty")
    ]
    if errors:
        response_lines.append(tr("addall_errors", errors="\n".join(errors)))

    await message.reply_text("\n".join(response_lines), parse_mode=ParseMode.HTML)


async def addblock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await add_all(update, context)


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
    _sync_user(update)
    services = get_services()
    message = _message(update)
    try:
        session = _require_open_game(services.store.get_latest(_chat_id(update)))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))
        return
    try:
        player_name = normalize_name(context.args[0]) if context.args else _command_author_player_name(update)
        if session.game.remove(player_name):
            services.store.save_players(session.id, session.game)
            services.store.delete_manual_buyins_for_player(session.id, player_name)
            await message.reply_text(tr("remove_done"))
        else:
            await message.reply_text(tr("remove_missing"))
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def remove_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
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
    services.store.delete_manual_buyins_for_game(session.id)
    await message.reply_text(tr("remove_all_done"))


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
    _sync_user(update)
    services = get_services()
    session = services.store.get_latest(_chat_id(update))
    if session is None:
        await _message(update).reply_text(tr("no_active_game"))
        return
    response = render_table(session.game)
    await _message(update).reply_text(response, parse_mode=ParseMode.HTML)


async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
    _sync_user(update)
    services = get_services()
    session = services.store.get_latest(_chat_id(update))
    if session is None:
        await _message(update).reply_text(tr("no_active_game"))
        return

    response = render_table(session.game)
    if session.game.check_balance():
        if _has_premium(update):
            entries = services.store.list_game_amount_entries(session.id)
            response = f"{response}\n\n{render_balance_analysis(session.game, entries)}"
        else:
            response = f"{response}\n\n{tr('list_analysis_premium_required')}"
    await _message(update).reply_text(response, parse_mode=ParseMode.HTML)


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
    _sync_user(update)
    services = get_services()
    try:
        limit = int(context.args[0]) if context.args else 5
    except ValueError:
        limit = 5
    limit = min(max(limit, 1), 20)
    entries = services.store.list_closed_games(_chat_id(update), limit=limit)
    await _message(update).reply_text(render_history(entries))


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
    _sync_user(update)
    services = get_services()
    entries = services.store.build_chat_player_stats(_chat_id(update))
    response = render_stats(entries) if _has_premium(update) else render_stats_basic(entries)
    await _message(update).reply_text(response, parse_mode=ParseMode.HTML)


async def import_history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = _message(update)
    if not _is_super_admin_update(update):
        await message.reply_text(tr("system_command_forbidden"))
        return

    text = message.text or ""
    parts = text.split("\n", 1)
    if len(parts) == 1:
        await message.reply_text(tr("importhistory_usage"), parse_mode=ParseMode.HTML)
        return

    services = get_services()
    try:
        first_line = parts[0]
        _, _, command_args_text = first_line.partition(" ")
        request = parse_import_command_request(command_args_text, parts[1])
        target_chat_id = _import_target_chat_id(update, request.chat_id)
        games = parse_history_dump(
            request.history_text,
            alias_map=request.alias_map,
            date_fixes=request.date_fixes,
            tz_name="Asia/Nicosia",
        )
        summary = summarize_games(games)
        if request.dry_run:
            await message.reply_text(
                tr("importhistory_dry_run", chat_id=target_chat_id, summary=build_dry_run_report(games))
            )
            return

        imported, skipped = import_games(
            services.store.session_factory,
            chat_id=target_chat_id,
            games=games,
        )
        await message.reply_text(
            tr(
                "importhistory_done",
                chat_id=target_chat_id,
                imported=imported,
                skipped=skipped,
                summary=summary,
            )
        )
    except Exception as exc:
        await message.reply_text(tr("generic_error", error=exc))


async def limits_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
    _sync_user(update)
    services = get_services()
    chat_id = _chat_id(update)
    user_id = _telegram_user_id(update)
    message = _message(update)

    if services.entitlements.is_billing_exempt(user_id, chat_id):
        await message.reply_text(tr("limits_status_admin"))
        return

    subscription = services.billing.get_chat_subscription(chat_id)
    if subscription is None or not subscription.is_active:
        await message.reply_text(
            _join_text(
                [
                    tr("limits_no_active_subscription"),
                    tr("limits_status_free_only", free_games_left=_remaining_free_games(chat_id)),
                ]
            )
        )
        return

    limits = services.billing.get_effective_plan_limits(chat_id, subscription.plan_code)
    if limits is None:
        await message.reply_text(tr("limits_plan_unavailable"))
        return

    since = _chat_usage_window_start()
    closed_games = services.store.count_closed_games_for_chat_since(chat_id, since)
    unique_players = services.store.count_unique_players_for_chat_since(chat_id, since)
    active_boost = services.billing.get_active_limit_boost(chat_id)
    await message.reply_text(
        _join_text(
            [
                tr(
                    "limits_status_chat_usage",
                    plan=tr(f"plan_{subscription.plan_code or 'monthly'}"),
                    closed_games=closed_games,
                    closed_games_limit=limits.closed_games_30d_limit,
                    unique_players=unique_players,
                    unique_players_limit=limits.unique_players_30d_limit,
                    warning_threshold=int(services.settings.chat_usage_warning_threshold * 100),
                ),
                tr(
                    "limits_status_active_boost",
                    expires_at=active_boost.expires_at.strftime("%Y-%m-%d %H:%M UTC"),
                )
                if active_boost and active_boost.expires_at
                else tr("limits_status_no_boost"),
            ]
        ),
        parse_mode=ParseMode.HTML,
    )


async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reply_private_info_for_non_admin(update):
        return
    user_id = _sync_user(update)
    services = get_services()
    message = _message(update)
    session = services.store.get_latest(_chat_id(update))

    if session is None:
        await message.reply_text(tr("no_active_game"))
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
    if await _reply_private_info_for_non_admin(update):
        return
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
    if await _reply_private_info_for_non_admin(update):
        return
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
    application.add_handler(CommandHandler("boost", limit_boost))
    application.add_handler(CommandHandler("sub_status", subscription_status))
    application.add_handler(CommandHandler("sub_cancel", cancel_subscription))
    if _premium_feature_enabled("sub_refund"):
        application.add_handler(CommandHandler("sub_refund", refund_subscription))
    application.add_handler(CommandHandler("newgame", newgame))
    if _premium_feature_enabled("savegroup"):
        application.add_handler(CommandHandler("savegroup", savegroup))
    if _premium_feature_enabled("groups"):
        application.add_handler(CommandHandler("groups", groups_cmd))
    application.add_handler(CommandHandler("startgame", startgame))
    if _premium_feature_enabled("revanche"):
        application.add_handler(CommandHandler("revanche", revanche))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("out", out))
    application.add_handler(CommandHandler(["addAll", "addall"], add_all))
    application.add_handler(CommandHandler("addblock", addblock))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(CommandHandler("removeAll", remove_all))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("importhistory", import_history_cmd))
    if _premium_feature_enabled("analyze"):
        application.add_handler(CommandHandler("analyze", analyze_cmd))
    if _premium_feature_enabled("history"):
        application.add_handler(CommandHandler("history", history_cmd))
    if _premium_feature_enabled("export_csv"):
        application.add_handler(CommandHandler("export_csv", export_csv_cmd))
    application.add_handler(CommandHandler("limits", limits_cmd))
    application.add_handler(CommandHandler("calc", calc))
