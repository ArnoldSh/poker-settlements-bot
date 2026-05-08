from __future__ import annotations

import importlib.util
import unittest

DEPENDENCIES_AVAILABLE = (
    importlib.util.find_spec("sqlalchemy") is not None
    and importlib.util.find_spec("stripe") is not None
)

if DEPENDENCIES_AVAILABLE:
    from poker_bot.billing import StripeBillingService


@unittest.skipUnless(DEPENDENCIES_AVAILABLE, "stripe/sqlalchemy dependencies are not installed in this environment")
class BillingStatusMappingTests(unittest.TestCase):
    def test_active_provider_status_maps_to_active(self) -> None:
        self.assertEqual(StripeBillingService._map_provider_status("active"), "active")

    def test_incomplete_provider_status_maps_to_pending_activation(self) -> None:
        self.assertEqual(
            StripeBillingService._map_provider_status("incomplete"),
            "pending_activation",
        )

    def test_past_due_provider_status_maps_to_past_due(self) -> None:
        self.assertEqual(StripeBillingService._map_provider_status("past_due"), "past_due")

    def test_unpaid_provider_status_maps_to_unpaid(self) -> None:
        self.assertEqual(StripeBillingService._map_provider_status("unpaid"), "unpaid")

    def test_incomplete_expired_maps_to_expired(self) -> None:
        self.assertEqual(
            StripeBillingService._map_provider_status("incomplete_expired"),
            "expired",
        )

    def test_paused_provider_status_maps_to_paused(self) -> None:
        self.assertEqual(StripeBillingService._map_provider_status("paused"), "paused")

    def test_formats_eur_minor_amount(self) -> None:
        self.assertEqual(StripeBillingService._format_amount(499, "eur"), "€4.99")

    def test_formats_unknown_currency_minor_amount(self) -> None:
        self.assertEqual(StripeBillingService._format_amount(1199, "usd"), "11.99 USD")

    def test_deleted_subscription_builds_user_and_admin_notifications(self) -> None:
        from poker_bot.billing import SubscriptionSnapshot

        service = object.__new__(StripeBillingService)
        previous = SubscriptionSnapshot(
            telegram_user_id=42,
            status="active",
            provider="stripe",
            provider_status="active",
            plan_code="monthly",
            current_period_start=None,
            current_period_end=None,
            checkout_session_id=None,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            requested_chat_id=100,
            pending_since=None,
            cancel_requested_at=None,
            cancel_requested_chat_id=200,
            refund_requested_at=None,
            refund_requested_chat_id=None,
        )
        current = SubscriptionSnapshot(
            telegram_user_id=42,
            status="canceled",
            provider="stripe",
            provider_status="canceled",
            plan_code="monthly",
            current_period_start=None,
            current_period_end=None,
            checkout_session_id=None,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            requested_chat_id=100,
            pending_since=None,
            cancel_requested_at=None,
            cancel_requested_chat_id=200,
            refund_requested_at=None,
            refund_requested_chat_id=None,
        )

        user_notifications, admin_notifications = service._build_subscription_notifications(
            previous,
            current,
            "customer.subscription.deleted",
        )

        self.assertEqual(user_notifications[0].chat_id, 200)
        self.assertEqual(len(admin_notifications), 1)


if __name__ == "__main__":
    unittest.main()
