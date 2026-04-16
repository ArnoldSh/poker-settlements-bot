from __future__ import annotations

from dataclasses import dataclass

from telegram import Bot


@dataclass(frozen=True)
class AdminRequestNotification:
    request_kind: str
    telegram_user_id: int
    username: str | None
    provider: str
    provider_subscription_id: str | None
    local_status: str
    provider_status: str | None
    source_chat_id: int | None


@dataclass(frozen=True)
class UserChatNotification:
    chat_id: int
    text: str


class TelegramAdminNotifier:
    def __init__(self, admin_chat_id: int | None) -> None:
        self.admin_chat_id = admin_chat_id

    @property
    def enabled(self) -> bool:
        return self.admin_chat_id is not None

    async def notify_request(self, bot: Bot, payload: AdminRequestNotification) -> bool:
        if self.admin_chat_id is None:
            return False

        username = payload.username or f"id:{payload.telegram_user_id}"
        request_label = "отмену" if payload.request_kind == "cancel" else "рефанд"
        await bot.send_message(
            chat_id=self.admin_chat_id,
            text=(
                f"Запрос на ручную {request_label} подписки\n"
                f"Пользователь: {username}\n"
                f"Telegram user id: {payload.telegram_user_id}\n"
                f"Provider: {payload.provider}\n"
                f"Provider subscription id: {payload.provider_subscription_id or '-'}\n"
                f"Локальный статус: {payload.local_status}\n"
                f"Provider status: {payload.provider_status or '-'}\n"
                f"Исходный chat id: {payload.source_chat_id or '-'}"
            ),
        )
        return True


class TelegramUserNotifier:
    async def notify(self, bot: Bot, payload: UserChatNotification) -> None:
        await bot.send_message(chat_id=payload.chat_id, text=payload.text)
