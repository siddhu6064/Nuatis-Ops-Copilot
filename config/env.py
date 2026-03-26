"""Environment file loading utilities."""

from __future__ import annotations

from pathlib import Path
import os


def load_env_file(path: str = ".env", override: bool = False) -> dict[str, str]:
    """Load key/value pairs from a .env-style file into process env."""
    env_path = Path(path)
    loaded: dict[str, str] = {}

    if not env_path.exists():
        return loaded

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and (override or key not in os.environ):
            os.environ[key] = value
            loaded[key] = value

    return loaded
