import httpx
import pytest

from app.config import Settings
from app.kiwoom.orders import AUTO_CONFIRMATION, MANUAL_CONFIRMATION, AutoMockOrderService, ManualMockOrderService


def settings() -> Settings:
    return Settings(environment="mock", app_key="test-key", secret_key="test-secret")


def test_order_requires_exact_human_confirmation():
    service = ManualMockOrderService(settings(), httpx.Client(base_url="https://mockapi.kiwoom.com"))
    with pytest.raises(ValueError, match="주문을 거부"):
        service.buy_market(code="005930", quantity=1, confirmation="yes")


def test_market_buy_uses_mock_host_and_official_tr():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return httpx.Response(200, json={"return_code": 0, "token": "test-token", "token_type": "bearer", "expires_dt": "20260829090000"})
        assert request.url == httpx.URL("https://mockapi.kiwoom.com/api/dostk/ordr")
        assert request.headers["api-id"] == "kt10000"
        assert request.headers["authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"return_code": 0, "ord_no": "1234567", "dmst_stex_tp": "KRX"})

    with httpx.Client(base_url="https://mockapi.kiwoom.com", transport=httpx.MockTransport(handler)) as http_client:
        order = ManualMockOrderService(settings(), http_client).buy_market(
            code="005930", quantity=1, confirmation=MANUAL_CONFIRMATION
        )
    assert order.order_number == "1234567"


def test_order_restricts_quantity_to_one_share():
    service = ManualMockOrderService(settings(), httpx.Client(base_url="https://mockapi.kiwoom.com"))
    with pytest.raises(ValueError, match="정확히 1주"):
        service.sell_market(code="005930", quantity=2, confirmation=MANUAL_CONFIRMATION)


def test_auto_order_stays_blocked_without_both_gates(monkeypatch):
    monkeypatch.delenv("ENABLE_MOCK_ORDER", raising=False)
    service = AutoMockOrderService(settings(), runtime_confirmation=AUTO_CONFIRMATION, client=httpx.Client(base_url="https://mockapi.kiwoom.com"))
    with pytest.raises(ValueError, match="ENABLE_MOCK_ORDER"):
        service.buy_market(code="005930", quantity=1)


def test_auto_order_uses_mock_only_when_both_gates_are_present(monkeypatch):
    monkeypatch.setenv("ENABLE_MOCK_ORDER", "true")
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return httpx.Response(200, json={"return_code": 0, "token": "test-token", "token_type": "bearer", "expires_dt": "20260829090000"})
        assert request.url.host == "mockapi.kiwoom.com"
        assert request.headers["api-id"] == "kt10000"
        return httpx.Response(200, json={"return_code": 0, "ord_no": "auto-1", "dmst_stex_tp": "KRX"})
    with httpx.Client(base_url="https://mockapi.kiwoom.com", transport=httpx.MockTransport(handler)) as client:
        result = AutoMockOrderService(settings(), runtime_confirmation=AUTO_CONFIRMATION, client=client).buy_market(code="005930", quantity=1)
    assert result.order_number == "auto-1"
