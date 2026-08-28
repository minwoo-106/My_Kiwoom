"""Common mock-only HTTP client for read-only Kiwoom REST requests."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, assert_mock_host
from app.kiwoom.auth import AccessToken, AuthenticationError, KiwoomAuthClient


class KiwoomApiError(RuntimeError):
    """A safe, human-readable error from a Kiwoom API request."""


class KiwoomReadClient:
    """Sends authenticated read requests only to the fixed mock host."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        assert_mock_host(settings.api_host)
        self._settings = settings
        self._client = client or httpx.Client(base_url=settings.api_host, timeout=10.0)
        self._owns_client = client is None
        # Memory-only cache: a token is never written to disk or logs.
        self._token: AccessToken | None = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def post(self, *, path: str, tr_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Make one authenticated, idempotent read request.

        This client is deliberately separate from future order handling. It may be
        retried by a caller only for read-only endpoints.
        """
        assert_mock_host(self._settings.api_host)
        if self._token is None:
            auth = KiwoomAuthClient(self._settings, self._client)
            try:
                self._token = auth.request_access_token()
            except AuthenticationError as exc:
                raise KiwoomApiError(f"Authentication required for {tr_id}: {exc}") from exc

        try:
            response = self._client.post(
                path,
                headers={
                    "Content-Type": "application/json;charset=UTF-8",
                    "authorization": f"Bearer {self._token.token}",
                    "api-id": tr_id,
                },
                json=body,
            )
        except httpx.TimeoutException as exc:
            raise KiwoomApiError(f"{tr_id} timed out. Check network and try the read request again.") from exc
        except httpx.RequestError as exc:
            raise KiwoomApiError(f"Could not reach mock API for {tr_id}.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise KiwoomApiError(f"{tr_id} returned invalid JSON (HTTP {response.status_code}).") from exc
        if not isinstance(payload, dict):
            raise KiwoomApiError(f"{tr_id} returned an unexpected JSON shape.")
        if response.is_error or payload.get("return_code") not in (None, 0, "0"):
            message = payload.get("return_msg") or "No error message supplied"
            raise KiwoomApiError(f"{tr_id} failed (HTTP {response.status_code}): {message}")
        return payload
