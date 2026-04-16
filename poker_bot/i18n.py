from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommentaryCatalog:
    winner_big: tuple[str, ...]
    winner_small: tuple[str, ...]
    loser_big: tuple[str, ...]
    loser_small: tuple[str, ...]


@dataclass(frozen=True)
class Catalog:
    locale: str
    messages: dict[str, str]
    commentary: CommentaryCatalog


RU_CATALOG = Catalog(
    locale="ru",
    messages={
        "missing_message": "Нужен текст сообщения, чтобы я понял команду.",
        "missing_chat": "Не удалось определить чат для этой команды.",
        "webhook_secret_invalid": "Неверный secret token вебхука.",
        "empty_name": "Пустое имя игрока.",
        "invalid_player_tag": (
            "Имя игрока должно быть Telegram-тегом: только латиница, цифры и underscore, "
            "с символом @ в начале и длиной не больше 64 символов."
        ),
        "parse_line_format": (
            "Строка не распознана. Форматы: "
            "@user 100, @user 100, 20, @user 10+20+20, @user 10+20+20, 5."
        ),
        "parse_amount_expression": (
            "Не удалось распознать сумму '{expression}'. Используйте числа и знак '+'."
        ),
        "balance_mismatch": (
            "Сумма выходов не равна сумме входов.\n"
            "Входы: {buyin}, выходы: {out}.\n"
            "Проверьте ввод игроков и сумм."
        ),
        "hub_not_found": "Указанный hub не найден среди игроков.",
        "start_text": (
            "Привет! Я считаю взаиморасчеты по итогам игры.\n"
            "В каждом чате доступны 3 бесплатные финализации игр через /calc.\n"
            "После этого нужна подписка пользователя через /subscribe.\n"
            "Справка: /help, статус подписки: /subscription."
        ),
        "help_text": (
            "<b>Бот расчета взаиморасчетов для покера</b>\n\n"
            "Команды:\n"
            "/start — краткая справка\n"
            "/help — полная справка\n"
            "/subscribe — получить ссылку на оплату подписки\n"
            "/subscription — статус вашей подписки\n"
            "/cancel_subscription — запросить ручную отмену подписки\n"
            "/newgame — начать новую игру в этом чате\n"
            "/add &lt;строка&gt; — добавить или обновить игрока\n"
            "/addblock — добавить несколько игроков блоком\n"
            "/remove @user — удалить игрока\n"
            "/removeAll — удалить всех игроков из текущей открытой игры\n"
            "/list — показать текущую таблицу\n"
            "/calc [direct|hub] [@hub] — завершить игру и посчитать переводы\n\n"
            "Поддерживаемый ввод:\n"
            "<code>/add @ivan 100</code>\n"
            "<code>/add @ivan 100, 20</code>\n"
            "<code>/add @ivan 10+20+20</code>\n"
            "<code>/add @ivan 10+20+20, 5</code>\n\n"
            "Правила игры:\n"
            "• одна игра начинается через /newgame\n"
            "• до /calc игроков можно добавлять, удалять и очищать через /removeAll\n"
            "• первый /calc закрывает игру, повторный /calc уже ничего не меняет\n"
            "• имена игроков должны быть Telegram-тегами в формате @username\n\n"
            "Монетизация:\n"
            "• в каждом чате доступны 3 бесплатные финализации для 3 уникальных игр\n"
            "• после исчерпания бесплатных игр нужна подписка пользователя\n"
            "• подписка считается на пользователя и дает до {subscription_games_limit} новых игр за период подписки\n"
            "• повторный /calc для уже закрытой игры лимиты не расходует\n"
            "• если подписка создана, но оплата не завершена, бот будет напоминать об оплате\n"
        ),
        "subscription_required_new_calc": (
            "Бесплатный лимит для этого чата исчерпан. Чтобы завершить новую игру, нужна подписка. "
            "Используйте /subscribe."
        ),
        "subscription_period_limit_reached": (
            "Лимит новых игр по вашей подписке за текущий период исчерпан. "
            "Повторный /calc для уже закрытых игр доступен, для новых дождитесь следующего периода."
        ),
        "subscription_status_active": "Подписка активна до {date}.",
        "subscription_status_active_open": "Подписка активна.",
        "subscription_status_pending": (
            "Подписка создана, но оплата еще не завершена. Завершите оплату по вашей ссылке Stripe."
        ),
        "subscription_status_payment_problem": (
            "У подписки есть проблема с оплатой. Проверьте оплату в Stripe или оформите подписку заново через /subscribe."
        ),
        "subscription_status_canceled": "Подписка отменена.",
        "subscription_status_expired": "Подписка истекла.",
        "subscription_status_inactive": "Подписка сейчас неактивна. Используйте /subscribe.",
        "subscription_checkout_unavailable": "Оплата пока не настроена. Проверьте конфигурацию Stripe.",
        "subscription_checkout_created": "Оформить подписку можно по ссылке:\n{url}",
        "subscription_cancel_requested": (
            "Запрос на ручную отмену подписки отправлен администратору. Мы свяжемся отдельно по возврату, если он нужен."
        ),
        "subscription_cancel_unavailable": (
            "Ручная отмена подписки пока не настроена. Попробуйте позже или свяжитесь с администратором."
        ),
        "subscription_cancel_no_subscription": "Активной или ожидающей подписки не найдено.",
        "newgame_done": "Новая игра создана. Теперь можно добавлять игроков.",
        "no_active_game": "Нет текущей игры. Начните новую через /newgame.",
        "game_closed": "Эта игра уже закрыта. Чтобы начать новую, используйте /newgame.",
        "add_usage": (
            "Использование: /add @user 100 или /add @user 100, 40 "
            "или /add @user 10+20+20, 40"
        ),
        "add_success": "OK: {name} — вход {buyin}, выход {out}",
        "generic_error": "Ошибка: {error}",
        "addblock_usage": (
            "Отправьте команду так:\n"
            "<code>/addblock\n"
            "@ivan 100\n"
            "@anna 50, 0\n"
            "@petr 80+20, 200</code>"
        ),
        "addblock_added": "Добавлены: {players}",
        "addblock_added_empty": "Добавлены: —",
        "addblock_errors": "Ошибки:\n{errors}",
        "remove_usage": "Использование: /remove @user",
        "remove_done": "Удален.",
        "remove_missing": "Игрок не найден.",
        "remove_all_done": "Все игроки из текущей игры удалены.",
        "player_limit_reached": "В одной игре можно держать не больше {limit} игроков.",
        "list_empty": "Список игроков пуст.",
        "table_header": "<b>Игрок</b> | <b>Вход</b> | <b>Выход</b> | <b>Итог</b>",
        "table_totals": "Σ | {buyin} | {out} | <b>{net}</b>",
        "calc_no_data": "Нет данных по игрокам. Сначала добавьте игроков через /add или /addblock.",
        "calc_mode_hub": "Режим: HUB. Хаб: <b>{hub}</b>.",
        "calc_mode_direct": "Режим: DIRECT.",
        "calc_no_transfers": "{highlights}\n\nВсе и так в нуле — переводов не требуется.",
        "calc_transfers_header": "<b>Переводы:</b>",
        "calc_summary": (
            "Всего движений денег: {count}; "
            "общая сумма по всем переводам: {total}"
        ),
        "highlights_title": "<b>🏆 Итоги</b>",
        "highlights_zero": "Никто ничего не выиграл и не проиграл — магия равновесия.",
        "highlights_big_winner": "🥇 {name} {amount} — {comment}",
        "highlights_small_winner": "🟢 {name} {amount} — {comment}",
        "highlights_big_loser": "🥄 {name} {amount} в минус — {comment}",
        "highlights_small_loser": "🟠 {name} {amount} в минус — {comment}",
        "highlights_other": "{name} {amount} ({direction})",
        "highlights_other_title": "Прочие: {items}",
        "highlights_plus": "плюс",
        "highlights_minus": "минус",
        "highlights_zero_direction": "ноль",
        "billing_success_page": "Оплата прошла успешно. Можно вернуться в Telegram и проверить /subscription.",
        "billing_cancel_page": "Оплата отменена. Можно вернуться в Telegram и попробовать позже.",
    },
    commentary=CommentaryCatalog(
        winner_big=(
            "волк с Макариу стрит",
            "возможно потерял друзей, но не пофиг ли?",
            "может хотя бы купишь нам пива?!",
            "не знает, куда ему тратить наш кеш!",
            "теперь у него будут проблемы с налоговой",
            "так, с этим больше не играем",
            "стэк как на дрожжах!",
            "поздравляем, но не от всего сердца",
            "сегодня пьет за счет стола",
            "это просто ограбление",
        ),
        winner_small=(
            "не проиграл и то праздник",
            "скромно, но в плюс — зачет",
            "микро-ап, но приятно",
            "чай на сдачу твой",
            "держишь баланс — дзен мастер",
            "тихо зашел, тихо в плюс вышел",
            "стек не вырос, но и не упал — аккуратист",
            "+копеечка, зато стабильно",
            "без фанатизма, но по делу",
            "мелочь, а приятно",
        ),
        loser_big=(
            "unlucky bro, повезет в другой раз",
            "денег нет, но вы держитесь",
            "поддержим товарища",
            "мы никому не расскажем",
            "пора сходить в церковь",
            "яйца стальные, карманы пустые",
            "зато истории будут",
            "если что, мы тебя все равно любим",
            "деньги не главное",
            "мы с тобой, даже если карты против",
        ),
        loser_small=(
            "знает меру — красавчик",
            "знает, когда остановиться",
            "минимизировал урон — капитан экономии",
            "отступил, чтобы вернуться и победить",
            "потерял мало, сохранил много",
            "затерпел, но настрой боевой",
            "чек-колл дисциплина засчитана",
            "банку помахал, а кошелек спас",
            "тоненько прошел по краю",
            "разумный луз это всегда уважаемо",
        ),
    ),
)


def tr(key: str, **kwargs: object) -> str:
    template = RU_CATALOG.messages[key]
    if kwargs:
        return template.format(**kwargs)
    return template
