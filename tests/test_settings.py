import os
import unittest

from config.settings import load_settings


class SettingsTests(unittest.TestCase):
    def test_defaults_when_env_not_set(self) -> None:
        for key in [
            "SERVICE_NAME",
            "ENVIRONMENT",
            "LOG_LEVEL",
            "DATABASE_URL",
            "NOTIFICATIONS_ENABLED",
            "WEBHOOK_URL",
        ]:
            os.environ.pop(key, None)

        settings = load_settings()

        self.assertEqual(settings.service_name, "nuatis_ops_copilot")
        self.assertEqual(settings.environment, "development")
        self.assertEqual(settings.log_level, "INFO")
        self.assertEqual(settings.database_url, "sqlite:///./nuatis_ops.db")
        self.assertFalse(settings.notifications_enabled)
        self.assertIsNone(settings.webhook_url)

    def test_uses_env_values(self) -> None:
        os.environ["SERVICE_NAME"] = "ops"
        os.environ["ENVIRONMENT"] = "staging"
        os.environ["LOG_LEVEL"] = "WARNING"
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        os.environ["NOTIFICATIONS_ENABLED"] = "true"
        os.environ["WEBHOOK_URL"] = "https://example.test/webhook"

        settings = load_settings()

        self.assertEqual(settings.service_name, "ops")
        self.assertEqual(settings.environment, "staging")
        self.assertEqual(settings.log_level, "WARNING")
        self.assertEqual(settings.database_url, "sqlite:///:memory:")
        self.assertTrue(settings.notifications_enabled)
        self.assertEqual(settings.webhook_url, "https://example.test/webhook")


if __name__ == "__main__":
    unittest.main()
