from datetime import datetime
from io import StringIO

from rich.console import Console

from app.kiwoom.market import Quote
from app.monitoring.dashboard import AccountSnapshot, DashboardState, WatchRow, render_dashboard


def test_dashboard_renders_mock_only_and_placeholder_statuses():
    state = DashboardState(
        account=AccountSnapshot(deposit=10_000_000, estimated_assets=10_000_000, total_profit_loss=0),
        quote=Quote(code="005930", name="Samsung", current_price=70_000, change=100, change_rate="0.14", volume=10),
        api_status="정상",
        api_requests=2,
        last_api_success=datetime(2026, 8, 31, 13, 0, 0),
        watch_rows=(
            WatchRow("005930", 70_000, "PULLBACK", "EMA20 부근 눌림"),
            WatchRow("000660", 200_000, "RISK_BLOCKED", "MAX_OPEN_POSITIONS"),
        ),
        market_phase="OPEN",
        strategy_status="정상 분석",
        risk_status="정상 (DRY RUN 차단 적용)",
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
    assert "DRY RUN(주문 전송 없음)" in rendered
