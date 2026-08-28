import httpx

from app.config import Settings
from app.kiwoom.account import AccountService
from app.kiwoom.client import KiwoomReadClient
from app.kiwoom.market import MarketService


def settings() -> Settings:
    return Settings(environment="mock", app_key="test-key", secret_key="test-secret")


def token_response() -> httpx.Response:
    return httpx.Response(200, json={"return_code": 0, "token": "test-token", "token_type": "bearer", "expires_dt": "20260829090000"})


def test_account_request_uses_mock_host_and_tr_id():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return token_response()
        assert request.url == httpx.URL("https://mockapi.kiwoom.com/api/dostk/acnt")
        assert request.headers["api-id"] == "ka00001"
        assert request.headers["authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"return_code": 0, "acctNo": "1234567890"})

    with httpx.Client(base_url="https://mockapi.kiwoom.com", transport=httpx.MockTransport(handler)) as http_client:
        assert AccountService(KiwoomReadClient(settings(), http_client)).list_accounts() == ["1234567890"]


def test_portfolio_parses_summary_and_holdings():
    responses = [token_response(), httpx.Response(200, json={"return_code": 0, "entr": "10000000", "prsm_dpst_aset_amt": "10000000", "lspft": "0", "stk_acnt_evlt_prst": [{"stk_cd": "005930", "stk_nm": "Samsung", "rmnd_qty": "1", "cur_prc": "70000"}]})]
    with httpx.Client(base_url="https://mockapi.kiwoom.com", transport=httpx.MockTransport(lambda request: responses.pop(0))) as http_client:
        summary, holdings = AccountService(KiwoomReadClient(settings(), http_client)).portfolio()
    assert summary["deposit"] == 10_000_000
    assert holdings[0].quantity == 1


def test_quote_uses_stock_info_tr():
    responses = [token_response(), httpx.Response(200, json={"return_code": 0, "stk_cd": "005930", "stk_nm": "Samsung", "cur_prc": "70000", "pred_pre": "100", "flu_rt": "0.14", "trde_qty": "10"})]
    with httpx.Client(base_url="https://mockapi.kiwoom.com", transport=httpx.MockTransport(lambda request: responses.pop(0))) as http_client:
        quote = MarketService(KiwoomReadClient(settings(), http_client)).quote("005930")
    assert quote.current_price == 70_000


def test_read_client_reuses_its_memory_only_token():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/oauth2/token":
            return token_response()
        return httpx.Response(200, json={"return_code": 0})

    with httpx.Client(base_url="https://mockapi.kiwoom.com", transport=httpx.MockTransport(handler)) as http_client:
        client = KiwoomReadClient(settings(), http_client)
        client.post(path="/api/dostk/acnt", tr_id="ka00001", body={})
        client.post(path="/api/dostk/acnt", tr_id="kt00004", body={})

    assert calls.count("/oauth2/token") == 1
