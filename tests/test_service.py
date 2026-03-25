import os
import unittest

from service import start_service


class ServiceBootstrapTests(unittest.TestCase):
    def test_start_service_returns_success(self) -> None:
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        os.environ["SERVICE_NAME"] = "ops_bootstrap_test"
        os.environ["LOG_LEVEL"] = "INFO"

        result = start_service()

        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
