from datetime import datetime
from io import StringIO

from rich.console import Console

from app.kiwoom.market import Quote
from app.kiwoom.account import Holding
from app.config import Settings
from app.monitoring.dashboard import AccountSnapshot, DashboardDataProvider, DashboardState, TradeRow, WatchRow, render_dashboard


def test_dashboard_renders_mock_only_and_placeholder_statuses():
    state = DashboardState(
        account=AccountSnapshot(deposit=10_000_000, estimated_assets=10_000_000, total_profit_loss=0),
        quote=Quote(code="005930", name="Samsung", current_price=70_000, change=100, change_rate="0.14", volume=10),
        api_status="정상",
        api_requests=2,
        last_api_success=datetime(2026, 8, 31, 13, 0, 0),
        watch_rows=(
            WatchRow("005930", 70_000, "PULLBACK", "EMA20 부근 눌림", current_price=70_200, change_rate="0.29", name="삼성전자"),
            WatchRow("000660", 200_000, "RISK_BLOCKED", "MAX_OPEN_POSITIONS"),
        ),
        market_phase="OPEN",
        strategy_status="정상 분석",
        risk_status="정상 (DRY RUN 차단 적용)",
        trades=(TradeRow("2026-08-31T13:00:00", "005930", "BUY", 70_000, 1, 0, "FILLED"),),
    )
    output = StringIO()
    console = Console(file=output, width=150, height=60, color_system=None)

    console.print(render_dashboard(state))

    rendered = output.getvalue()
    assert "[MOCK] TRADING ONLY" in rendered
    assert "10,000,000원" in rendered
    assert "005930" in rendered
    assert "000660" in rendered
    assert "완료 15분봉" in rendered
    assert "현재가" in rendered
    assert "70,200원" in rendered
    assert "삼성전자 (005930)" in rendered
    assert "DRY RUN(주문 전송 없음)" in rendered
    assert "FILLED" in rendered


def test_restored_account_snapshot_is_reused_without_second_api_request():
    provider = DashboardDataProvider(Settings(environment="mock", app_key="test", secret_key="test"), "005930")
    try:
        provider.hydrate_account({"deposit": 10_000_000, "estimated_assets": 10_000_000, "total_profit_loss": 0}, ())
        state = provider.cached_state()
        assert state.account.deposit == 10_000_000
        assert state.api_requests == 0
    finally:
        provider.close()


def test_dashboard_clearly_shows_emergency_stop():
    output = StringIO()
    console = Console(file=output, width=150, height=60, color_system=None)
    console.print(render_dashboard(DashboardState(emergency_stop=True, risk_status="긴급 정지: 신규 매수 차단")))
    assert "신규 매수 즉시 중단" in output.getvalue()


def test_dashboard_shows_holding_evaluation_profit_and_return_rate():
    holding = Holding("005930", "삼성전자", 2, 100_000, 105_000, 210_000, 10_000)
    state = DashboardState(account=AccountSnapshot(deposit=1_000_000, estimated_assets=1_210_000, total_purchase=200_000, total_profit_loss=10_000, holdings=(holding,)))
    output = StringIO()
    console = Console(file=output, width=150, height=60, color_system=None)
    console.print(render_dashboard(state))
    rendered = output.getvalue()
    assert "주식 매입금" in rendered and "210,000원" in rendered
    assert "보유 수익률" in rendered and "+5.00%" in rendered
    assert "평가 210,000원" in rendered
