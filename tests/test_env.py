import os
import tempfile
import unittest
from pathlib import Path

from config.env import load_env_file


class EnvLoaderTests(unittest.TestCase):
    def test_loads_keys_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("SERVICE_NAME=my_service\n# comment\nLOG_LEVEL=DEBUG\n")

            loaded = load_env_file(str(env_file), override=True)

            self.assertEqual(loaded["SERVICE_NAME"], "my_service")
            self.assertEqual(os.environ["LOG_LEVEL"], "DEBUG")

    def test_missing_file_returns_empty(self) -> None:
        loaded = load_env_file("/tmp/definitely-missing.env", override=True)
        self.assertEqual(loaded, {})


if __name__ == "__main__":
    unittest.main()
