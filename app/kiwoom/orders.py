"""명시적으로 확인된 모의투자 전용 국내주식 주문 기능입니다."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings, assert_mock_host
from app.kiwoom.auth import AuthenticationError, KiwoomAuthClient
from app.kiwoom.client import KiwoomApiError


ORDER_PATH = "/api/dostk/ordr"
MANUAL_CONFIRMATION = "MOCK-ORDER"


@dataclass(frozen=True)
class SubmittedOrder:
    order_number: str
    exchange: str


class ManualMockOrderService:
    """재시도하지 않고 사람의 확인 문구를 반드시 요구하는 주문 서비스입니다."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        assert_mock_host(settings.api_host)
        self._settings = settings
        self._client = client or httpx.Client(base_url=settings.api_host, timeout=10.0)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def buy_market(self, *, code: str, quantity: int, confirmation: str) -> SubmittedOrder:
        return self._submit("kt10000", code, quantity, confirmation)

    def sell_market(self, *, code: str, quantity: int, confirmation: str) -> SubmittedOrder:
        return self._submit("kt10001", code, quantity, confirmation)

    def _submit(self, tr_id: str, code: str, quantity: int, confirmation: str) -> SubmittedOrder:
        assert_mock_host(self._settings.api_host)
        if confirmation != MANUAL_CONFIRMATION:
            raise ValueError(f"주문을 거부했습니다. --confirm {MANUAL_CONFIRMATION}을 정확히 입력하세요.")
        normalized_code = code.strip()
        if not (normalized_code.isdigit() and len(normalized_code) == 6):
            raise ValueError("종목코드는 정확히 여섯 자리 숫자여야 합니다.")
        if quantity != 1:
            raise ValueError("수동 MVP 주문은 정확히 1주로 제한됩니다.")

        auth = KiwoomAuthClient(self._settings, self._client)
        try:
            token = auth.request_access_token()
        except AuthenticationError as exc:
            raise KiwoomApiError(f"{tr_id} 인증 필요: {exc}") from exc

        try:
            # 주문 접수 여부가 불분명해질 수 있으므로 절대 재시도하지 않습니다.
            response = self._client.post(
                ORDER_PATH,
                headers={
                    "Content-Type": "application/json;charset=UTF-8",
                    "authorization": f"Bearer {token.token}",
                    "api-id": tr_id,
                },
                json={
                    "dmst_stex_tp": "KRX",
                    "stk_cd": normalized_code,
                    "ord_qty": "1",
                    "trde_tp": "3",  # 키움 공식 명세의 시장가
                    "ord_uv": "",
                    "cond_uv": "",
                },
            )
        except httpx.TimeoutException as exc:
            raise KiwoomApiError(
                "주문 요청 시간이 초과되었습니다. 재전송하지 말고 주문·체결 상태를 먼저 확인하세요."
            ) from exc
        except httpx.RequestError as exc:
            raise KiwoomApiError(
                "주문 요청이 완료되지 않았습니다. 재전송하지 말고 주문·체결 상태를 먼저 확인하세요."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise KiwoomApiError("주문 응답이 올바른 JSON이 아닙니다. 재전송하지 말고 상태를 먼저 확인하세요.") from exc
        if response.is_error or payload.get("return_code") not in (None, 0, "0"):
            message = payload.get("return_msg") or "오류 메시지가 제공되지 않았습니다"
            raise KiwoomApiError(f"{tr_id} rejected (HTTP {response.status_code}): {message}")
        order_number = str(payload.get("ord_no", ""))
        if not order_number:
            raise KiwoomApiError("주문 응답에 주문번호가 없습니다. 재전송하지 말고 상태를 먼저 확인하세요.")
        return SubmittedOrder(order_number=order_number, exchange=str(payload.get("dmst_stex_tp", "KRX")))
