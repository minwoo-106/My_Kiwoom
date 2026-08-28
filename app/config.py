"""Configuration guarded to allow only Kiwoom mock trading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


MOCK_ENV = "mock"
MOCK_API_HOST = "https://mockapi.kiwoom.com"
PRODUCTION_API_HOST = "https://api.kiwoom.com"


class ConfigurationError(ValueError):
    """Raised when the process is not provably configured for mock trading."""


@dataclass(frozen=True)
class Settings:
    environment: str
    app_key: str
    secret_key: str
    api_host: str = MOCK_API_HOST

    @classmethod
    def load(cls, env_file: Path | str = ".env") -> "Settings":
        load_dotenv(dotenv_path=env_file, override=False)

        # Do not normalize whitespace: only the exact value is safe and supported.
        environment = os.getenv("KIWOOM_ENV", MOCK_ENV).lower()
        if environment != MOCK_ENV:
            raise ConfigurationError(
                "KIWOOM_ENV must be exactly 'mock'. Real/production trading is unsupported."
            )

        # The host deliberately has no configurable setting. Reject attempted overrides,
        # especially the production host, so an order path can never be redirected.
        requested_host = os.getenv("KIWOOM_API_HOST")
        if requested_host:
            if requested_host.rstrip("/") == PRODUCTION_API_HOST:
                raise ConfigurationError("Production API host is blocked permanently.")
            raise ConfigurationError("KIWOOM_API_HOST overrides are not allowed; mock host is fixed.")

        app_key = os.getenv("KIWOOM_APP_KEY", "").strip()
        secret_key = os.getenv("KIWOOM_SECRET_KEY", "").strip()
        if not app_key or not secret_key:
            raise ConfigurationError(
                "Missing KIWOOM_APP_KEY or KIWOOM_SECRET_KEY. Add mock credentials to .env locally."
            )

        return cls(environment=environment, app_key=app_key, secret_key=secret_key)


def assert_mock_host(host: str) -> None:
    """Defence in depth for all future HTTP and order clients."""
    if host.rstrip("/") != MOCK_API_HOST:
        raise ConfigurationError("Only https://mockapi.kiwoom.com is permitted.")
