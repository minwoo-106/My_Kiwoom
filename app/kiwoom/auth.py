"""OAuth client for Kiwoom's mock REST API only."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings, assert_mock_host


class AuthenticationError(RuntimeError):
    """Raised for safe, human-readable authentication failures."""


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
            raise AuthenticationError("Mock API request timed out. Check network and registered IP.") from exc
        except httpx.RequestError as exc:
            raise AuthenticationError("Could not reach Kiwoom mock API. Check network and DNS.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthenticationError("Mock API returned an invalid JSON response.") from exc

        if response.is_error or payload.get("return_code") not in (None, 0, "0"):
            message = payload.get("return_msg") or "No error message supplied"
            raise AuthenticationError(f"Token issuance failed (HTTP {response.status_code}): {message}")

        token = payload.get("token")
        token_type = payload.get("token_type")
        expires_at = payload.get("expires_dt")
        if not all(isinstance(value, str) and value for value in (token, token_type, expires_at)):
            raise AuthenticationError("Token response is missing token, token_type, or expires_dt.")
        return AccessToken(token=token, token_type=token_type, expires_at=expires_at)
