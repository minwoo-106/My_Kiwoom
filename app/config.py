"""키움 모의투자만 허용하도록 보호된 설정입니다."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


MOCK_ENV = "mock"
MOCK_API_HOST = "https://mockapi.kiwoom.com"
PRODUCTION_API_HOST = "https://api.kiwoom.com"


class ConfigurationError(ValueError):
    """모의투자 설정이 확실하지 않을 때 발생합니다."""


@dataclass(frozen=True)
class Settings:
    environment: str
    app_key: str
    secret_key: str
    api_host: str = MOCK_API_HOST

    @classmethod
    def load(cls, env_file: Path | str = ".env") -> "Settings":
        load_dotenv(dotenv_path=env_file, override=False)

        # 공백을 정규화하지 않습니다. 정확한 값만 안전하게 허용합니다.
        environment = os.getenv("KIWOOM_ENV", MOCK_ENV).lower()
        if environment != MOCK_ENV:
            raise ConfigurationError(
                "KIWOOM_ENV는 정확히 'mock'이어야 합니다. 실전투자는 지원하지 않습니다."
            )

        # 호스트는 의도적으로 설정값으로 바꾸지 못하게 합니다. 운영 서버를 포함한
        # 모든 재지정을 거부하여 주문 요청이 다른 서버로 향하지 않게 합니다.
        requested_host = os.getenv("KIWOOM_API_HOST")
        if requested_host:
            if requested_host.rstrip("/") == PRODUCTION_API_HOST:
                raise ConfigurationError("운영 API 호스트는 영구적으로 차단됩니다.")
            raise ConfigurationError("KIWOOM_API_HOST 변경은 허용되지 않습니다. 모의 호스트는 고정입니다.")

        app_key = os.getenv("KIWOOM_APP_KEY", "").strip()
        secret_key = os.getenv("KIWOOM_SECRET_KEY", "").strip()
        if not app_key or not secret_key:
            raise ConfigurationError(
                "KIWOOM_APP_KEY 또는 KIWOOM_SECRET_KEY가 없습니다. 로컬 .env에 모의투자 키를 입력하세요."
            )

        return cls(environment=environment, app_key=app_key, secret_key=secret_key)


def assert_mock_host(host: str) -> None:
    """향후 모든 HTTP·주문 클라이언트에 적용하는 이중 안전장치입니다."""
    if host.rstrip("/") != MOCK_API_HOST:
        raise ConfigurationError("https://mockapi.kiwoom.com만 허용됩니다.")
