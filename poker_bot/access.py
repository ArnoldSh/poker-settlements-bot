from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from time import monotonic
from typing import Any, Protocol


class SubscriptionAccess(Protocol):
    @property
    def is_active(self) -> bool: ...


class PermissionTableCache:
    def __init__(self, session_factory: Any, ttl: timedelta) -> None:
        self.session_factory = session_factory
        self.ttl_seconds = max(0.0, ttl.total_seconds())
        self._expires_at = 0.0
        self._permissions: set[tuple[int, int]] = set()

    def invalidate(self) -> None:
        self._expires_at = 0.0

    def has_chat_admin_access(self, telegram_user_id: int | None, chat_id: int | None) -> bool:
        if telegram_user_id is None or chat_id is None:
            return False
        return (telegram_user_id, chat_id) in self._get_permissions()

    def _get_permissions(self) -> set[tuple[int, int]]:
        now = monotonic()
        if now >= self._expires_at:
            self._permissions = self._load_permissions()
            self._expires_at = now + self.ttl_seconds
        return self._permissions

    def _load_permissions(self) -> set[tuple[int, int]]:
        from sqlalchemy import select

        from poker_bot.models import ChatAdminPermissionModel

        with self.session_factory() as session:
            rows = session.execute(
                select(ChatAdminPermissionModel.telegram_user_id, ChatAdminPermissionModel.chat_id).where(
                    ChatAdminPermissionModel.is_active.is_(True)
                )
            )
            return {(telegram_user_id, chat_id) for telegram_user_id, chat_id in rows}


@dataclass
class EntitlementPolicy:
    admin_user_id: int | None = None
    permission_cache: PermissionTableCache | None = None

    def is_super_admin(self, telegram_user_id: int | None) -> bool:
        return self.admin_user_id is not None and telegram_user_id == self.admin_user_id

    def is_chat_admin(self, telegram_user_id: int | None, chat_id: int | None) -> bool:
        if self.is_super_admin(telegram_user_id):
            return True
        if self.permission_cache is None:
            return False
        return self.permission_cache.has_chat_admin_access(telegram_user_id, chat_id)

    def is_billing_exempt(self, telegram_user_id: int | None, chat_id: int | None = None) -> bool:
        return self.is_chat_admin(telegram_user_id, chat_id)

    def has_premium_access(
        self,
        telegram_user_id: int | None,
        subscription: SubscriptionAccess | None,
        chat_id: int | None = None,
    ) -> bool:
        if self.is_billing_exempt(telegram_user_id, chat_id):
            return True
        return bool(subscription and subscription.is_active)
