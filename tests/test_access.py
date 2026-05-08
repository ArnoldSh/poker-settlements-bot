from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import timedelta
import importlib.util

from poker_bot.access import EntitlementPolicy, PermissionTableCache

DEPENDENCIES_AVAILABLE = importlib.util.find_spec("sqlalchemy") is not None

if DEPENDENCIES_AVAILABLE:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from poker_bot.models import Base, ChatAdminPermissionModel


@dataclass(frozen=True)
class SubscriptionStub:
    is_active: bool


class EntitlementPolicyTests(unittest.TestCase):
    def test_admin_user_is_billing_exempt_in_any_chat(self) -> None:
        policy = EntitlementPolicy(admin_user_id=42)

        self.assertTrue(policy.is_billing_exempt(42, 42))
        self.assertTrue(policy.is_billing_exempt(42, -100))
        self.assertTrue(policy.has_premium_access(42, SubscriptionStub(is_active=False), -100))

    def test_non_admin_needs_active_subscription(self) -> None:
        policy = EntitlementPolicy(admin_user_id=42)

        self.assertFalse(policy.is_billing_exempt(100, 200))
        self.assertFalse(policy.has_premium_access(100, SubscriptionStub(is_active=False), 200))
        self.assertTrue(policy.has_premium_access(100, SubscriptionStub(is_active=True), 200))

    def test_missing_admin_config_disables_exemption(self) -> None:
        policy = EntitlementPolicy()

        self.assertFalse(policy.is_billing_exempt(42, 42))
        self.assertFalse(policy.has_premium_access(42, None, 42))

    @unittest.skipUnless(DEPENDENCIES_AVAILABLE, "sqlalchemy dependency is not installed in this environment")
    def test_chat_admin_permission_grants_billing_exemption(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        with session_factory() as session:
            session.add(ChatAdminPermissionModel(telegram_user_id=42, chat_id=-100, is_active=True))
            session.commit()

        policy = EntitlementPolicy(
            permission_cache=PermissionTableCache(session_factory, timedelta(minutes=5)),
        )

        self.assertTrue(policy.is_billing_exempt(42, -100))
        self.assertFalse(policy.is_billing_exempt(42, -200))
        self.assertFalse(policy.is_billing_exempt(100, -100))

    @unittest.skipUnless(DEPENDENCIES_AVAILABLE, "sqlalchemy dependency is not installed in this environment")
    def test_permission_cache_uses_ttl(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        cache = PermissionTableCache(session_factory, timedelta(minutes=5))
        policy = EntitlementPolicy(permission_cache=cache)

        self.assertFalse(policy.is_billing_exempt(42, -100))

        with session_factory() as session:
            session.add(ChatAdminPermissionModel(telegram_user_id=42, chat_id=-100, is_active=True))
            session.commit()

        self.assertFalse(policy.is_billing_exempt(42, -100))
        cache.invalidate()
        self.assertTrue(policy.is_billing_exempt(42, -100))


if __name__ == "__main__":
    unittest.main()
