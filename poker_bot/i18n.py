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
        "missing_message": "Нужно текстовое сообщение, чтобы я понял команду.",
        "missing_chat": "Не удалось определить чат для этой команды.",
        "missing_user": "Не удалось определить пользователя Telegram.",
        "webhook_secret_invalid": "Неверный secret token вебхука.",
        "empty_name": "Пустое имя игрока.",
        "invalid_player_tag": (
            "Имя игрока должно быть Telegram-тегом: только латиница, цифры и underscore, "
            "с символом @ в начале и длиной не более 64 символов."
        ),
        "parse_line_format": (
            "Строка не распознана. Форматы: "
            "@user 100, @user 100, 20, @user 10+20+20, @user 10+20+20, 5."
        ),
        "parse_amount_expression": "Не удалось распознать сумму '{expression}'. Используйте числа и знак '+'.",
        "balance_mismatch": (
            "Сумма выходов не равна сумме входов.\n"
            "Входы: {buyin}, выходы: {out}.\n"
            "Проверьте ввод игроков и сумм."
        ),
        "hub_not_found": "Указанный hub не найден среди игроков.",
        "start_text": (
            "Привет! Я считаю взаиморасчеты по итогам покерной игры.\n"
            "В каждом чате доступны 3 бесплатные игры через /newgame.\n"
            "Дальше новые игры доступны по персональной подписке через /sub.\n"
            "Можно сохранять постоянные компании, запускать реванш, смотреть историю и статистику.\n"
            "Справка: /help, статус подписки: /sub_status."
        ),
        "help_text": (
            "<b>Бот расчета взаиморасчетов для покера</b>\n\n"
            "<b>Основные команды</b>\n"
            "/start - краткая справка\n"
            "/help - полная справка\n"
            "/newgame - пустая новая игра\n"
            "/startgame &lt;название группы&gt; - новая игра из сохраненной компании\n"
            "/revanche - новая игра с составом прошлой закрытой игры\n"
            "/savegroup &lt;название&gt; - сохранить текущий состав игроков\n"
            "/groups - список сохраненных компаний\n"
            "/add &lt;строка&gt; - добавить или обновить игрока\n"
            "/addblock - добавить игроков блоком\n"
            "/remove @user - удалить игрока\n"
            "/removeAll - удалить всех игроков из открытой игры\n"
            "/list - показать текущую таблицу\n"
            "/calc [direct|hub] [@hub] - завершить игру, посчитать переводы и показать статистику\n"
            "/history [N] - история последних игр\n"
            "/export_csv - выгрузить последнюю закрытую игру в CSV\n\n"
            "<b>Подписка</b>\n"
            "/sub - показать доступные планы подписки\n"
            "/sub monthly - месячная подписка\n"
            "/sub quarterly - подписка на 3 месяца\n"
            "/sub semiannual - подписка на полгода\n"
            "/sub yearly - подписка на год\n"
            "/sub_status - статус вашей подписки\n"
            "/sub_cancel - запросить ручную отмену\n"
            "/sub_refund - запросить ручной рефанд\n\n"
            "<b>Поддерживаемый ввод</b>\n"
            "<code>/add @ivan 100</code>\n"
            "<code>/add @ivan 100, 20</code>\n"
            "<code>/add @ivan 10+20+20</code>\n"
            "<code>/add @ivan 10+20+20, 5</code>\n\n"
            "<b>Что продает Premium</b>\n"
            "• быстрый старт игры без ручного ввода состава\n"
            "• история всех вечеров\n"
            "• расширенная статистика по друзьям внутри /calc\n"
            "• реванш в один клик\n"
            "• красивые итоговые сообщения и экспорт\n\n"
            "<b>Монетизация</b>\n"
            "• в каждом чате есть 3 бесплатные игры\n"
            "• после этого новые игры доступны с активной персональной подпиской\n"
            "• подписка открывает новые игры без лимита внутри оплаченного периода\n"
            "• если подписка создана, но оплата не завершена, бот будет напоминать об оплате"
        ),
        "subscription_required_new_game": (
            "Бесплатный лимит для этого чата исчерпан. Чтобы создать новую игру, нужна активная подписка. "
            "Используйте /sub."
        ),
        "limits_status_free_only": "Бесплатных игр в этом чате осталось: {free_games_left}",
        "limits_status_unlimited": (
            "Бесплатных игр в этом чате осталось: {free_games_left}\n"
            "По активной подписке новые игры сейчас без лимита."
        ),
        "subscription_status_active": "Подписка активна: {plan}. Следующее продление или окончание периода: {date}.",
        "subscription_status_active_open": "Подписка активна: {plan}.",
        "subscription_status_pending": "Подписка создана, но оплата еще не завершена. Завершите оплату по вашей ссылке Stripe.",
        "subscription_status_payment_problem": "У подписки есть проблема с оплатой. Проверьте платеж в Stripe или оформите подписку заново через /sub.",
        "subscription_status_canceled": "Подписка отменена.",
        "subscription_status_expired": "Подписка истекла.",
        "subscription_status_inactive": "Подписка сейчас неактивна. Используйте /sub.",
        "subscription_checkout_unavailable": "Оплата пока не настроена. Проверьте конфигурацию Stripe.",
        "subscription_checkout_created": "Оформить подписку ({plan}) можно по ссылке:\n{url}",
        "subscription_plan_choose": (
            "Выберите план подписки командой:\n"
            "/sub monthly\n"
            "/sub quarterly\n"
            "/sub semiannual\n"
            "/sub yearly"
        ),
        "subscription_plan_item": "• {label}: /sub {code}",
        "subscription_cancel_requested": "Запрос на ручную отмену подписки отправлен администратору.",
        "subscription_cancel_unavailable": "Ручная отмена подписки пока не настроена. Попробуйте позже.",
        "subscription_cancel_no_subscription": "Активной или ожидающей подписки не найдено.",
        "subscription_refund_requested": "Запрос на рефанд отправлен администратору. Ответ придет отдельно в Telegram.",
        "subscription_refund_unavailable": "Рефанд пока нельзя запросить через бота. Попробуйте позже.",
        "subscription_refund_no_subscription": "Подходящая подписка для запроса рефанда не найдена.",
        "plan_monthly": "месячная",
        "plan_quarterly": "на 3 месяца",
        "plan_semiannual": "на полгода",
        "plan_yearly": "годовая",
        "newgame_done": "Новая игра создана. Теперь можно добавлять игроков.",
        "savegroup_usage": "Использование: /savegroup Friday Home Game",
        "savegroup_done": "Компания '{name}' сохранена. Игроков: {count}.",
        "groups_title": "<b>Сохраненные компании</b>",
        "groups_empty": "Сохраненных компаний пока нет.",
        "groups_item": "• <b>{name}</b> ({count}) — {players}",
        "startgame_usage": "Использование: /startgame Friday Home Game",
        "startgame_missing_group": "Компания '{name}' не найдена.",
        "startgame_done": "Игра создана из компании '{name}'.\nИгроки: {players}",
        "revanche_missing": "Нет закрытой игры, из которой можно собрать реванш.",
        "revanche_done": "Реванш создан.\nИгроки: {players}",
        "group_players_empty": "Сначала добавьте игроков, потом можно сохранять компанию.",
        "no_active_game": "Нет текущей игры. Начните новую через /newgame.",
        "game_closed": "Эта игра уже закрыта. Чтобы начать новую, используйте /newgame.",
        "add_usage": "Использование: /add @user 100 или /add @user 100, 40 или /add @user 10+20+20, 40",
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
        "addblock_added_empty": "Добавлены: -",
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
        "calc_no_transfers_basic": "Все и так в нуле — переводов не требуется.",
        "calc_transfers_header": "<b>Переводы</b>",
        "calc_summary": "Всего переводов: {count}; общая сумма по всем переводам: {total}",
        "pretty_results_title": "<b>♠️ Poker Night Results</b>",
        "pretty_results_footer": "GG WP",
        "history_title": "<b>История игр</b>",
        "history_empty": "История игр пока пуста.",
        "history_item": "• {date} — {player_count} игроков — банк {total_pot} — {players}",
        "stats_title_basic": "<b>Короткая статистика</b>",
        "stats_title": "<b>Статистика по чату</b>",
        "stats_empty": "Пока нет закрытых игр для статистики.",
        "stats_item_basic": "• {name} {total} | игр: {games}",
        "stats_item": "{index}. {name} {total} | игр: {games} | средний итог: {average} | плюсовых: {wins} | минусовых: {losses}",
        "highlights_title": "<b>Итоги</b>",
        "highlights_zero": "Никто ничего не выиграл и не проиграл — магия равновесия.",
        "highlights_big_winner": "🥇 {name} {amount} — {comment}",
        "highlights_small_winner": "🟢 {name} {amount} — {comment}",
        "highlights_big_loser": "🥴 {name} {amount} в минус — {comment}",
        "highlights_small_loser": "🟠 {name} {amount} в минус — {comment}",
        "highlights_other": "{name} {amount} ({direction})",
        "highlights_other_title": "Прочие: {items}",
        "highlights_plus": "плюс",
        "highlights_minus": "минус",
        "highlights_zero_direction": "ноль",
        "subscription_event_started_pending": "Подписка создана. Ждем завершения оплаты.",
        "subscription_event_paid": "Оплата прошла успешно. Подписка {plan} активна до {date}.",
        "subscription_event_canceled": "Подписка отменена.",
        "subscription_event_refunded": "Рефанд выполнен успешно.",
        "billing_return_to_telegram_page": "Можно вернуться в Telegram. Дальнейшие уведомления придут в чат.",
    },
    commentary=CommentaryCatalog(
        winner_big=(
            "волк с Макариу стрит 💸",
            "возможно потерял друзей, но не похер ли? 💼",
            "может хотя бы купишь нам пива?! 😈",
            "не знает, куда ему тратить наш кеш! 🏴‍☠️",
            "теперь у него будут проблемы с налоговой 😎",
            "так, с этим больше не играем 💀",
            "стэк как на дрожжах! 💸",
            "поздравляем, но не от всего сердца 💔",
            "сегодня пьёт за счёт стола 🥂",
            "это просто ограбление 🚨",
        ),
        winner_small=(
            "не проиграл — и то праздник 🎈",
            "скромно, но в плюс — зачёт ✅",
            "микро-ап, но приятно 😉",
            "чай на сдачу — твой ☕",
            "держишь баланс — дзен мастер 🧘",
            "тихо зашёл, тихо в плюс вышел 🐾",
            "стек не вырос, но и не упал — аккуратист ✂️",
            "+копеечка, зато стабильно 💁",
            "без фанатизма, но по делу 🧮",
            "мелочь, а приятно 💫",
        ),
        loser_big=(
            "может пора сходить в церковь?.."
            "карты сегодня были против тебя",
            "unlucky bro - повезёт в другой раз 🥲",
            "денег нет, но вы держитесь 🤜🤛",
            "поддержим товарища 🫂",
            "мы никому не расскажем 🤫",
            "пора сходить в церковь 🕯️⛪",
            "яйца стальные, карманы - пустые 📉",
            "зато истории будут 📖",
            "если что — мы тебя всё равно любим ❤️",
            "деньги - не главное 🫶",
            "мы с тобой, даже если карты против ❤️",
        ),
        loser_small=(
            "кошелек спасен... частично",
            "знает меру — красавчик 👍",
            "знает, когда остановиться 🛑",
            "минимизировал урон — капитан экономии ⚓",
            "отступил, чтоб вернуться и победить 🧭",
            "потерял мало, сохранил много 🛡️",
            "затерпел, но настрой боевой 💪",
            "чек-колл дисциплина засчитана ✅",
            "банку помахал, а кошелёк спас 💼",
            "тоненько прошёл по краю 🎯",
            "разумный луз это всегда уважаемо 🤝",
        ),
    ),
)


def tr(key: str, **kwargs: object) -> str:
    template = RU_CATALOG.messages[key]
    if kwargs:
        return template.format(**kwargs)
    return template
