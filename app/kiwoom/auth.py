"""키움 모의투자 REST API 전용 OAuth 클라이언트입니다."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings, assert_mock_host


class AuthenticationError(RuntimeError):
    """사람이 이해할 수 있는 안전한 인증 오류입니다."""


@dataclass(frozen=True)
class AccessToken:
    token: str
    token_type: str
    expires_at: str


class KiwoomAuthClient:
    TOKEN_PATH = "/oauth2/token"
    TR_ID = "au10001"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        assert_mock_host(settings.api_host)
        self._settings = settings
        self._client = client or httpx.Client(base_url=settings.api_host, timeout=10.0)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def request_access_token(self) -> AccessToken:
        try:
            response = self._client.post(
                self.TOKEN_PATH,
                headers={"Content-Type": "application/json;charset=UTF-8"},
                json={
                    "grant_type": "client_credentials",
                    "appkey": self._settings.app_key,
                    "secretkey": self._settings.secret_key,
                },
            )
        except httpx.TimeoutException as exc:
            raise AuthenticationError("모의 API 요청 시간이 초과되었습니다. 네트워크와 등록 IP를 확인하세요.") from exc
        except httpx.RequestError as exc:
            raise AuthenticationError("키움 모의 API에 연결할 수 없습니다. 네트워크와 DNS를 확인하세요.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthenticationError("모의 API가 올바르지 않은 JSON 응답을 반환했습니다.") from exc

        if response.is_error or payload.get("return_code") not in (None, 0, "0"):
            message = payload.get("return_msg") or "오류 메시지가 제공되지 않았습니다"
            raise AuthenticationError(f"토큰 발급 실패(HTTP {response.status_code}): {message}")

        token = payload.get("token")
        token_type = payload.get("token_type")
        expires_at = payload.get("expires_dt")
        if not all(isinstance(value, str) and value for value in (token, token_type, expires_at)):
            raise AuthenticationError("토큰 응답에 token, token_type 또는 expires_dt가 없습니다.")
        return AccessToken(token=token, token_type=token_type, expires_at=expires_at)
