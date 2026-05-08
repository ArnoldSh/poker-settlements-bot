from __future__ import annotations

import unittest
from dataclasses import dataclass

from poker_bot.access import EntitlementPolicy


@dataclass(frozen=True)
class SubscriptionStub:
    is_active: bool


class EntitlementPolicyTests(unittest.TestCase):
    def test_admin_user_is_billing_exempt(self) -> None:
        policy = EntitlementPolicy(admin_user_id=42)

        self.assertTrue(policy.is_billing_exempt(42))
        self.assertTrue(policy.has_premium_access(42, SubscriptionStub(is_active=False)))

    def test_non_admin_needs_active_subscription(self) -> None:
        policy = EntitlementPolicy(admin_user_id=42)

        self.assertFalse(policy.is_billing_exempt(100))
        self.assertFalse(policy.has_premium_access(100, SubscriptionStub(is_active=False)))
        self.assertTrue(policy.has_premium_access(100, SubscriptionStub(is_active=True)))

    def test_missing_admin_config_disables_exemption(self) -> None:
        policy = EntitlementPolicy()

        self.assertFalse(policy.is_billing_exempt(42))
        self.assertFalse(policy.has_premium_access(42, None))


if __name__ == "__main__":
    unittest.main()
