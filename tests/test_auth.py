import json

import httpx
import pytest

from app.config import Settings
from app.kiwoom.auth import AuthenticationError, KiwoomAuthClient


def settings() -> Settings:
    return Settings(environment="mock", app_key="test-key", secret_key="test-secret")


def test_requests_mock_oauth_token_only():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://mockapi.kiwoom.com/oauth2/token")
        assert request.headers["content-type"] == "application/json;charset=UTF-8"
        assert json.loads(request.content) == {
            "grant_type": "client_credentials",
            "appkey": "test-key",
            "secretkey": "test-secret",
        }
        return httpx.Response(
            200,
            json={"return_code": 0, "token": "token-value", "token_type": "bearer", "expires_dt": "20260829090000"},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(base_url="https://mockapi.kiwoom.com", transport=transport) as http_client:
        token = KiwoomAuthClient(settings(), http_client).request_access_token()

    assert token.expires_at == "20260829090000"


def test_api_error_is_human_readable():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"return_code": -1, "return_msg": "invalid credentials"})
    )
    with httpx.Client(base_url="https://mockapi.kiwoom.com", transport=transport) as http_client:
        with pytest.raises(AuthenticationError, match="invalid credentials"):
            KiwoomAuthClient(settings(), http_client).request_access_token()


def test_invalid_json_is_reported_safely():
    transport = httpx.MockTransport(lambda request: httpx.Response(502, text="upstream unavailable"))
    with httpx.Client(base_url="https://mockapi.kiwoom.com", transport=transport) as http_client:
        with pytest.raises(AuthenticationError, match="invalid JSON"):
            KiwoomAuthClient(settings(), http_client).request_access_token()
