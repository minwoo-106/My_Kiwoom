"""Explicitly confirmed domestic-stock orders for the mock environment only."""

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
    """Order service with no retry and a mandatory human confirmation phrase."""

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
            raise ValueError(f"Refusing order: pass --confirm {MANUAL_CONFIRMATION} exactly.")
        normalized_code = code.strip()
        if not (normalized_code.isdigit() and len(normalized_code) == 6):
            raise ValueError("Stock code must be exactly six digits.")
        if quantity != 1:
            raise ValueError("Manual MVP order is restricted to exactly one share.")

        auth = KiwoomAuthClient(self._settings, self._client)
        try:
            token = auth.request_access_token()
        except AuthenticationError as exc:
            raise KiwoomApiError(f"Authentication required for {tr_id}: {exc}") from exc

        try:
            # Never retry an order: its acceptance may be unknown after a timeout.
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
                    "trde_tp": "3",  # market order, as documented by Kiwoom
                    "ord_uv": "",
                    "cond_uv": "",
                },
            )
        except httpx.TimeoutException as exc:
            raise KiwoomApiError(
                "Order request timed out. Do not resend; check order/fill status first."
            ) from exc
        except httpx.RequestError as exc:
            raise KiwoomApiError(
                "Order request failed before confirmation. Do not resend; check order/fill status first."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise KiwoomApiError("Order response was not valid JSON. Do not resend; check status first.") from exc
        if response.is_error or payload.get("return_code") not in (None, 0, "0"):
            message = payload.get("return_msg") or "No error message supplied"
            raise KiwoomApiError(f"{tr_id} rejected (HTTP {response.status_code}): {message}")
        order_number = str(payload.get("ord_no", ""))
        if not order_number:
            raise KiwoomApiError("Order response has no order number. Do not resend; check status first.")
        return SubmittedOrder(order_number=order_number, exchange=str(payload.get("dmst_stex_tp", "KRX")))
