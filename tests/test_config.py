from __future__ import annotations

import os
import unittest
from datetime import timedelta
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
        self.assertEqual(settings.permission_table_cache_ttl, timedelta(hours=1))
        self.assertEqual(settings.chat_usage_warning_threshold, 0.8)
        self.assertEqual(
            settings.enabled_features,
            frozenset({"revanche", "savegroup", "groups", "analyze", "history", "export_csv", "sub_refund"}),
        )

    def test_loads_enabled_features(self) -> None:
        env = {
            "BOT_TOKEN": "token",
            "DATABASE_URL": "sqlite://",
            "ENABLED_FEATURES": "revanche, analyze, sub_refund",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(settings.enabled_features, frozenset({"revanche", "analyze", "sub_refund"}))

    def test_loads_permission_table_cache_ttl(self) -> None:
        env = {
            "BOT_TOKEN": "token",
            "DATABASE_URL": "sqlite://",
            "PERMISSION_TABLE_CACHE_TTL": "PT5M",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(settings.permission_table_cache_ttl, timedelta(minutes=5))

    def test_loads_permission_table_cache_ttl_as_timedelta_text(self) -> None:
        env = {
            "BOT_TOKEN": "token",
            "DATABASE_URL": "sqlite://",
            "PERMISSION_TABLE_CACHE_TTL": "P1DT2H3M4S",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(settings.permission_table_cache_ttl, timedelta(days=1, hours=2, minutes=3, seconds=4))

    def test_loads_chat_usage_warning_threshold(self) -> None:
        env = {
            "BOT_TOKEN": "token",
            "DATABASE_URL": "sqlite://",
            "CHAT_USAGE_WARNING_THRESHOLD": "0.75",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(settings.chat_usage_warning_threshold, 0.75)


if __name__ == "__main__":
    unittest.main()
