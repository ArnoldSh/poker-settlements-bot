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

    def test_problem_provider_status_maps_to_payment_problem(self) -> None:
        self.assertEqual(
            StripeBillingService._map_provider_status("past_due"),
            "payment_problem",
        )

    def test_incomplete_expired_maps_to_expired(self) -> None:
        self.assertEqual(
            StripeBillingService._map_provider_status("incomplete_expired"),
            "expired",
        )


if __name__ == "__main__":
    unittest.main()
