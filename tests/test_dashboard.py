from datetime import datetime
from io import StringIO

from rich.console import Console

from app.kiwoom.market import Quote
from app.monitoring.dashboard import AccountSnapshot, DashboardState, render_dashboard


def test_dashboard_renders_mock_only_and_placeholder_statuses():
    state = DashboardState(
        account=AccountSnapshot(deposit=10_000_000, estimated_assets=10_000_000, total_profit_loss=0),
        quote=Quote(code="005930", name="Samsung", current_price=70_000, change=100, change_rate="0.14", volume=10),
        api_status="정상",
        api_requests=2,
        last_api_success=datetime(2026, 8, 31, 13, 0, 0),
    )
    output = StringIO()
    console = Console(file=output, width=150, height=60, color_system=None)

    console.print(render_dashboard(state))

    rendered = output.getvalue()
    assert "[MOCK] TRADING ONLY" in rendered
    assert "10,000,000원" in rendered
    assert "005930" in rendered
    assert "NOT STARTED" in rendered
    assert "NOT IMPLEMENTED" in rendered
