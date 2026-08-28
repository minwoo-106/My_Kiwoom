"""읽기 전용 키움 모의투자 REST 요청 공통 클라이언트입니다."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, assert_mock_host
from app.kiwoom.auth import AccessToken, AuthenticationError, KiwoomAuthClient


class KiwoomApiError(RuntimeError):
    """키움 API 요청에서 발생한 사람이 이해할 수 있는 안전한 오류입니다."""


class KiwoomReadClient:
    """고정된 모의 호스트로만 인증된 읽기 요청을 보냅니다."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        assert_mock_host(settings.api_host)
        self._settings = settings
        self._client = client or httpx.Client(base_url=settings.api_host, timeout=10.0)
        self._owns_client = client is None
        # 메모리 전용 캐시입니다. 토큰은 디스크나 로그에 기록하지 않습니다.
        self._token: AccessToken | None = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def post(self, *, path: str, tr_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """인증된 멱등 읽기 요청을 한 번 보냅니다.

        이 클라이언트는 향후 주문 처리와 의도적으로 분리합니다. 호출자는
        읽기 전용 엔드포인트에 한해서만 재시도할 수 있습니다.
        """
        assert_mock_host(self._settings.api_host)
        if self._token is None:
            auth = KiwoomAuthClient(self._settings, self._client)
            try:
                self._token = auth.request_access_token()
            except AuthenticationError as exc:
                raise KiwoomApiError(f"{tr_id} 인증 필요: {exc}") from exc

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
            raise KiwoomApiError(f"{tr_id} 요청 시간이 초과되었습니다. 네트워크 확인 후 읽기 요청만 다시 시도하세요.") from exc
        except httpx.RequestError as exc:
            raise KiwoomApiError(f"{tr_id}용 모의 API에 연결할 수 없습니다.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise KiwoomApiError(f"{tr_id}이(가) 올바르지 않은 JSON을 반환했습니다(HTTP {response.status_code}).") from exc
        if not isinstance(payload, dict):
            raise KiwoomApiError(f"{tr_id}이(가) 예상하지 못한 JSON 구조를 반환했습니다.")
        if response.is_error or payload.get("return_code") not in (None, 0, "0"):
            message = payload.get("return_msg") or "오류 메시지가 제공되지 않았습니다"
            raise KiwoomApiError(f"{tr_id} 요청 실패(HTTP {response.status_code}): {message}")
        return payload
