from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from poker_bot.config import load_settings


class SettingsTests(unittest.TestCase):
    def test_loads_admin_user_id(self) -> None:
        env = {
            "BOT_TOKEN": "token",
            "DATABASE_URL": "sqlite://",
            "ADMIN_USER_ID": "42",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(settings.admin_user_id, 42)

    def test_admin_user_id_defaults_to_none(self) -> None:
        env = {
            "BOT_TOKEN": "token",
            "DATABASE_URL": "sqlite://",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertIsNone(settings.admin_user_id)
        self.assertEqual(
            settings.enabled_premium_features,
            frozenset({"revanche", "savegroup", "groups", "analyze", "history", "export_csv", "sub_refund"}),
        )

    def test_loads_enabled_premium_features(self) -> None:
        env = {
            "BOT_TOKEN": "token",
            "DATABASE_URL": "sqlite://",
            "ENABLED_PREMIUM_FEATURES": "revanche, analyze, sub_refund",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(settings.enabled_premium_features, frozenset({"revanche", "analyze", "sub_refund"}))


if __name__ == "__main__":
    unittest.main()
