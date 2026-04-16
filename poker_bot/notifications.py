from __future__ import annotations

from dataclasses import dataclass

from telegram import Bot


@dataclass(frozen=True)
class CancelRequestNotification:
    telegram_user_id: int
    username: str | None
    provider: str
    provider_subscription_id: str | None
    local_status: str
    provider_status: str | None
    source_chat_id: int | None


class TelegramAdminNotifier:
    def __init__(self, admin_chat_id: int | None) -> None:
        self.admin_chat_id = admin_chat_id

    @property
    def enabled(self) -> bool:
        return self.admin_chat_id is not None

    async def notify_cancel_request(self, bot: Bot, payload: CancelRequestNotification) -> bool:
        if self.admin_chat_id is None:
            return False

        username = payload.username or f"id:{payload.telegram_user_id}"
        await bot.send_message(
            chat_id=self.admin_chat_id,
            text=(
                "Запрос на ручную отмену или рефанд подписки\n"
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
