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
        "limit_boost_choose": "Выберите пакет увеличения лимитов командой:",
        "limit_boost_item": "/boost {code} - boost x2 на {period} за {price}",
        "subscription_plan_choose": "Выберите план подписки командой:",
        "subscription_plan_item_priced": "/sub {code} - подписка на {period} за {price}",
        "plan_period_monthly": "1 месяц",
        "plan_period_quarterly": "3 месяца",
        "plan_period_semiannual": "полгода",
        "plan_period_yearly": "год",
        "limit_boost_period_boost_30d": "1 месяц",
        "limit_boost_period_boost_90d": "3 месяца",
        "limit_boost_period_boost_180d": "полгода",
        "limit_boost_period_boost_365d": "год",
        "limits_status_active_boost": "Limit boost x2 активен до {expires_at}.",
        "limits_status_no_boost": "Limit boost не активен. Увеличить лимиты можно через /boost.",
        "limit_boost_choose": (
            "Выберите limit boost x2 для этого чата:\n"
            "/boost 1m\n"
            "/boost 3m\n"
            "/boost 6m\n"
            "/boost 1y"
        ),
        "limit_boost_item": "• {label} — {price}: /boost {code}",
        "price_unknown": "цена уточняется",
        "subscription_plan_item_priced": "• {label} — {price}: /sub {code}",
        "limit_boost_boost_30d": "x2 на 30 дней",
        "limit_boost_boost_90d": "x2 на 90 дней",
        "limit_boost_boost_180d": "x2 на 180 дней",
        "limit_boost_boost_365d": "x2 на 365 дней",
        "limit_boost_checkout_unavailable": "Оплата limit boost пока не настроена. Проверьте конфигурацию Stripe.",
        "limit_boost_checkout_created": "Купить limit boost ({boost}) можно по ссылке:\n{url}",
        "limit_boost_active_subscription_required": "Limit boost можно купить только для чата с активной подпиской.",
        "limit_boost_already_active": "В этом чате уже активен limit boost до {expires_at}.",
        "limit_boost_already_active_unknown": "В этом чате уже активен limit boost.",
        "limit_boost_plan_unavailable": "Этот limit boost сейчас недоступен. Используйте /boost, чтобы посмотреть доступные пакеты.",
        "limit_boost_event_paid": "Limit boost x2 активирован. Он действует до {expires_at}.",
        "limit_boost_event_refunded": "Limit boost был возвращен и больше не применяется к лимитам чата.",
        "missing_message": "Нужно текстовое сообщение, чтобы я понял команду.",
        "missing_chat": "Не удалось определить чат для этой команды.",
        "missing_user": "Не удалось определить пользователя Telegram.",
        "missing_username": "У автора сообщения нет Telegram username. Укажите игрока явно: @user.",
        "webhook_secret_invalid": "Неверный secret token вебхука.",
        "empty_name": "Пустое имя игрока.",
        "invalid_player_tag": (
            "Имя игрока должно быть Telegram-тегом: только латиница, цифры и underscore, "
            "с символом @ в начале и длиной не более 64 символов."
        ),
        "parse_line_format": (
            "Строка не распознана. Форматы: "
            "@user 100, @user 10+20+20, @user 10+20+20 -> 5, @user 20 40 40 -> 133.50."
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
            "/newgame i - интерактивный сбор входов и выходов\n"
            "/finish - завершить сбор входов в интерактивной игре\n"
            "/restart - пересобрать интерактивную игру из сохраненных сообщений\n"
            "/startgame &lt;название группы&gt; - новая игра из сохраненной компании\n"
            "/revanche - новая игра с составом прошлой закрытой игры\n"
            "/savegroup &lt;название&gt; - сохранить текущий состав игроков\n"
            "/groups - список сохраненных компаний\n"
            "/add &lt;строка&gt; - добавить или обновить игрока\n"
            "/addblock - добавить игроков блоком\n"
            "/remove @user - удалить игрока\n"
            "/removeAll - удалить всех игроков из открытой игры\n"
            "/list - показать текущую таблицу\n"
            "/analyze - показать таблицу и Premium-анализ расхождения\n"
            "/calc [direct|hub] [@hub] - завершить игру, посчитать переводы и показать статистику\n"
            "/history [N] - история последних игр\n"
            "/export_csv - выгрузить последнюю закрытую игру в CSV\n\n"
            "<b>Подписка</b>\n"
            "/sub - показать доступные планы подписки\n"
            "/sub 1m - месячная подписка\n"
            "/sub 3m - подписка на 3 месяца\n"
            "/sub 6m - подписка на полгода\n"
            "/sub 1y - подписка на год\n"
            "/sub_status - статус вашей подписки\n"
            "/sub_cancel - отменить подписку\n"
            "/sub_refund - запросить рефанд\n\n"
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
        "subscription_required_after_subscription": (
            "Пробный лимит для этого чата больше недоступен: он действует только один раз до первой подписки. "
            "Чтобы создать новую игру, нужна активная подписка. Используйте /sub."
        ),
        "limits_status_free_only": "Бесплатных игр в этом чате осталось: {free_games_left}",
        "limits_status_admin": "Админский доступ активен. Лимиты использования не применяются.",
        "limits_no_active_subscription": "В этом чате нет активной подписки.",
        "limits_plan_unavailable": "Не удалось найти лимиты тарифного плана для этого чата.",
        "limits_status_chat_usage": (
            "<b>Лимиты чата</b>\n"
            "План: {plan}\n"
            "Период: последние 30 дней\n"
            "Закрытые игры: {closed_games} из {closed_games_limit}\n"
            "Уникальные игроки в закрытых играх: {unique_players} из {unique_players_limit}\n"
            "Предупреждение включается с {warning_threshold}% лимита."
        ),
        "chat_usage_closed_games_limit_reached": "Лимит новых игр для этого чата исчерпан: {used} из {limit} закрытых игр за последние 30 дней.",
        "chat_usage_unique_players_limit_reached": "Лимит новых игроков для этого чата исчерпан: {used} из {limit} уникальных игроков в закрытых играх за последние 30 дней.",
        "chat_usage_closed_games_warning": "Предупреждение: в этом чате использовано {used} из {limit} закрытых игр за последние 30 дней.",
        "chat_usage_unique_players_warning": "Предупреждение: в этом чате использовано {used} из {limit} уникальных игроков в закрытых играх за последние 30 дней.",
        "subscription_status_active": "Подписка активна: {plan}. Следующее продление или окончание периода: {date}.",
        "subscription_status_active_open": "Подписка активна: {plan}.",
        "subscription_status_admin": "Админский доступ активен. Платные ограничения не применяются.",
        "subscription_status_pending": "Подписка создана, но оплата еще не завершена. Завершите оплату по вашей ссылке Stripe.",
        "subscription_status_payment_problem": "У подписки есть проблема с оплатой. Проверьте платеж в Stripe или оформите подписку заново через /sub.",
        "subscription_status_canceled": "Подписка отменена.",
        "subscription_status_expired": "Подписка истекла.",
        "subscription_status_inactive": "Подписка сейчас неактивна. Используйте /sub.",
        "subscription_checkout_unavailable": "Оплата пока не настроена. Проверьте конфигурацию Stripe.",
        "subscription_checkout_created": "Оформить подписку ({plan}) можно по ссылке:\n{url}",
        "private_chat_info_board": (
            "<b>Покерные расчеты работают в группах</b>\n\n"
            "Добавьте бота в групповой чат и используйте /help там. "
            "Подписка оформляется из группы и действует только в этой группе."
        ),
        "subscription_chat_already_bound": "В этом чате уже есть подписка другого владельца. Управлять ей может только тот, кто ее оформил.",
        "subscription_user_bound_to_other_chat": "Ваша подписка уже привязана к другому чату. В новом чате она не действует.",
        "subscription_owner_only": "Это действие доступно только владельцу подписки этого чата.",
        "subscription_status_chat_active": "В этом чате активна подписка. Игровые premium-возможности доступны всем участникам.",
        "subscription_status_chat_pending": "В этом чате уже создана подписка, но оплата еще не завершена.",
        "group_chat_required": "Эта команда работает только в групповом чате.",
        "subscription_plan_unavailable": "Этот план подписки сейчас недоступен. Используйте /sub, чтобы посмотреть доступные планы.",
        "subscription_plan_choose": (
            "Выберите план подписки командой:\n"
            "/sub 1m\n"
            "/sub 3m\n"
            "/sub 6m\n"
            "/sub 1y"
        ),
        "subscription_plan_item": "• {label}: /sub {code}",
        "subscription_cancel_requested": "Запрос на отмену подписки отправлен в Stripe. Когда отмена будет подтверждена, я напишу в чат.",
        "subscription_cancel_unavailable": "Не удалось отправить запрос на отмену подписки в Stripe. Попробуйте позже.",
        "subscription_cancel_no_subscription": "Активной или ожидающей подписки не найдено.",
        "subscription_refund_requested": "Запрос на рефанд отправлен администратору. Ответ придет отдельно в Telegram.",
        "subscription_refund_unavailable": "Рефанд пока нельзя запросить через бота. Попробуйте позже.",
        "subscription_refund_no_subscription": "Подходящая подписка для запроса рефанда не найдена.",
        "plan_monthly": "месячная",
        "plan_quarterly": "на 3 месяца",
        "plan_semiannual": "на полгода",
        "plan_yearly": "годовая",
        "newgame_done": "Новая игра создана. Теперь можно добавлять игроков.",
        "newgame_interactive_done": (
            "Интерактивная игра создана. Сейчас собираю входы: игроки отправляют в чат сообщения только с числами. "
            "Когда входы собраны, отправьте /finish, после этого начну собирать выходы."
        ),
        "interactive_buyins_finished": "Входы зафиксированы. Теперь собираю выходы: игроки снова отправляют сообщения только с числами.",
        "interactive_finish_manual_game": "Команда /finish работает только для игры, начатой через /newgame i.",
        "interactive_restart_manual_game": "Команда /restart работает только для игры, начатой через /newgame i.",
        "interactive_restart_done": "Интерактивная игра пересобрана из сохраненных сообщений. Игроков: {players}.",
        "interactive_calc_before_finish": "Сначала завершите сбор входов командой /finish, затем соберите выходы и запускайте /list или /calc.",
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
        "add_usage": "Использование: /add 100 или /add @user 100. Команда принимает одно число; для корректировки можно передать отрицательную сумму.",
        "add_success": "OK: {name} — закуп {amount}. Суммарный вход: {buyin}",
        "add_adjustment_success": "OK: {name} — КОРРЕКТИРОВКА {amount}. Суммарный вход: {buyin}",
        "out_usage": "Использование: /out 136.20 или /out @user 136.20. Команда принимает одно число.",
        "out_success": "OK: {name} — выход {out}",
        "generic_error": "Ошибка: {error}",
        "addall_usage": (
            "Отправьте команду так:\n"
            "<code>/addAll\n"
            "@ivan 100\n"
            "@anna 50 -> 0\n"
            "@petr 80+20 -> 200</code>"
        ),
        "addall_added": "Добавлены: {players}",
        "addall_added_empty": "Добавлены: -",
        "addall_errors": "Ошибки:\n{errors}",
        "addblock_usage": (
            "Отправьте команду так:\n"
            "<code>/addAll\n"
            "@ivan 100\n"
            "@anna 50 -> 0\n"
            "@petr 80+20 -> 200</code>"
        ),
        "addblock_added": "Добавлены: {players}",
        "addblock_added_empty": "Добавлены: -",
        "addblock_errors": "Ошибки:\n{errors}",
        "remove_usage": "Использование: /remove или /remove @user",
        "remove_done": "Удален.",
        "remove_missing": "Игрок не найден.",
        "remove_all_done": "Все игроки из текущей игры удалены.",
        "remove_interactive_unavailable": "В интерактивной игре /remove и /removeAll недоступны. Исправьте сообщения игроков и используйте /restart.",
        "player_limit_reached": "В одной игре можно держать не больше {limit} игроков.",
        "list_empty": "Список игроков пуст.",
        "table_header": "<b>Игрок</b> | <b>Вход</b> | <b>Выход</b> | <b>Итог</b>",
        "table_totals": "Σ | {buyin} | {out} | <b>{net}</b>",
        "list_analysis_premium_required": "Анализ расхождения доступен только с активной подпиской.",
        "list_analysis_title": "<b>Анализ расхождения</b>",
        "list_analysis_balanced": "<b>Анализ расхождения</b>\nВходы и выходы сходятся.",
        "list_analysis_out_over": "Выходы больше входов на {amount}.",
        "list_analysis_buyin_over": "Входы больше выходов на {amount}.",
        "list_analysis_out_over_hint": "Проверьте: возможно, забыли вход на {amount} или лишний/ошибочный выход на {amount}.",
        "list_analysis_buyin_over_hint": "Проверьте: возможно, забыли выход на {amount} или лишний/ошибочный вход на {amount}.",
        "list_analysis_exact_title": "Точные совпадения с размером расхождения:",
        "list_analysis_exact_item": "• {player}: {phase} {amount}{raw}",
        "list_analysis_phase_buyin": "вход",
        "list_analysis_phase_out": "выход",
        "list_analysis_player_buyin_match": "• У {player} суммарный вход ровно {amount}.",
        "list_analysis_player_out_match": "• У {player} выход ровно {amount}.",
        "list_analysis_no_exact": "Точных совпадений на {amount} не нашел. Вероятно, ошибка распределена по нескольким записям.",
        "calc_no_data": "Нет данных по игрокам. Сначала добавьте игроков через /add или /addAll.",
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
        "subscription_event_paused": "Подписка поставлена на паузу или требует оплаты. Новые игры по подписке временно недоступны.",
        "subscription_event_canceled": "Ваша подписка была отменена.",
        "admin_subscription_event_canceled": (
            "Системное оповещение: подписка отменена\n"
            "Telegram user id: {telegram_user_id}\n"
            "Provider: {provider}\n"
            "Provider subscription id: {provider_subscription_id}\n"
            "Локальный статус: {local_status}\n"
            "Provider status: {provider_status}\n"
            "Чат уведомления: {source_chat_id}"
        ),
        "subscription_event_refunded": "Рефанд выполнен успешно.",
        "billing_return_to_telegram_page": "Можно вернуться в Telegram. Дальнейшие уведомления придут в чат.",
        "limit_boost_choose": "Выберите пакет увеличения лимитов командой:",
        "limit_boost_item": "/boost {code} - boost x2 на {period} за {price}",
        "subscription_plan_choose": "Выберите план подписки командой:",
        "subscription_plan_item_priced": "/sub {code} - подписка на {period} за {price}",
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
