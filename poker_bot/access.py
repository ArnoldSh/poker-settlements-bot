from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SubscriptionAccess(Protocol):
    @property
    def is_active(self) -> bool: ...


@dataclass(frozen=True)
class EntitlementPolicy:
    admin_user_id: int | None = None

    def is_billing_exempt(self, telegram_user_id: int | None) -> bool:
        return self.admin_user_id is not None and telegram_user_id == self.admin_user_id

    def has_premium_access(self, telegram_user_id: int | None, subscription: SubscriptionAccess | None) -> bool:
        if self.is_billing_exempt(telegram_user_id):
            return True
        return bool(subscription and subscription.is_active)
