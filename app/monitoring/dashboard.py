"""키움 모의투자 정보를 표시만 하는 Rich 터미널 대시보드입니다."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from time import monotonic
from typing import Deque

from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.config import Settings, assert_mock_host
from app.kiwoom.account import AccountService, Holding
from app.kiwoom.client import KiwoomApiError, KiwoomReadClient
from app.kiwoom.market import MarketService, Quote


@dataclass(frozen=True)
class AccountSnapshot:
    deposit: int | None = None
    estimated_assets: int | None = None
    total_profit_loss: int | None = None
    holdings: tuple[Holding, ...] = ()


@dataclass(frozen=True)
class DashboardState:
    """화면이 필요로 하는 값만 담는 표시 전용 상태입니다."""

    account: AccountSnapshot = field(default_factory=AccountSnapshot)
    quote: Quote | None = None
    api_status: str = "연결 대기"
    api_error: str | None = None
    api_requests: int = 0
    last_api_success: datetime | None = None
    started_at: float = field(default_factory=monotonic)
    events: tuple[str, ...] = ()


class DashboardDataProvider:
    """조회 서비스를 호출해 DashboardState를 만드는 어댑터입니다.

    주문·전략 로직에는 접근하지 않으며, 현재는 계좌와 시세 읽기 요청만 보냅니다.
    """

    def __init__(self, settings: Settings, stock_code: str) -> None:
        assert_mock_host(settings.api_host)
        self._client = KiwoomReadClient(settings)
        self._stock_code = stock_code
        self._started_at = monotonic()
        self._api_requests = 0
        self._last_success: datetime | None = None
        self._events: Deque[str] = deque(maxlen=5)

    def close(self) -> None:
        self._client.close()

    def refresh(self) -> DashboardState:
        try:
            summary, holdings = AccountService(self._client).portfolio()
            self._api_requests += 1
            quote = MarketService(self._client).quote(self._stock_code)
            self._api_requests += 1
            self._last_success = datetime.now()
            self._events.appendleft(f"[{self._last_success:%H:%M:%S}] INFO  {quote.code} 시세·잔고 갱신")
            return DashboardState(
                account=AccountSnapshot(
                    deposit=summary["deposit"],
                    estimated_assets=summary["estimated_assets"],
                    total_profit_loss=summary["total_profit_loss"],
                    holdings=tuple(holdings),
                ),
                quote=quote,
                api_status="정상",
                api_requests=self._api_requests,
                last_api_success=self._last_success,
                started_at=self._started_at,
                events=tuple(self._events),
            )
        except (KiwoomApiError, ValueError) as exc:
            now = datetime.now()
            self._events.appendleft(f"[{now:%H:%M:%S}] ERROR {exc}")
            return DashboardState(
                api_status="오류",
                api_error=str(exc),
                api_requests=self._api_requests,
                last_api_success=self._last_success,
                started_at=self._started_at,
                events=tuple(self._events),
            )


def _money(value: int | None) -> str:
    return "조회 대기" if value is None else f"{value:,}원"


def _signed_money(value: int | None) -> str:
    if value is None:
        return "조회 대기"
    return f"{value:+,}원"


def _uptime(started_at: float) -> str:
    seconds = int(monotonic() - started_at)
    return f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"


def _account_panel(state: DashboardState) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column(justify="right")
    table.add_row("예수금", _money(state.account.deposit))
    table.add_row("총 평가금", _money(state.account.estimated_assets))
    table.add_row("총 손익", _signed_money(state.account.total_profit_loss))
    table.add_row("보유 종목", f"{len(state.account.holdings)}개")
    return Panel(table, title="[bold]계좌 현황[/bold]", border_style="green")


def _watch_panel(state: DashboardState) -> Panel:
    table = Table(expand=True, box=None, header_style="bold cyan")
    for label in ("종목", "현재가", "등락률", "전략 상태", "신뢰도"):
        table.add_column(label, justify="right" if label in {"현재가", "등락률", "신뢰도"} else "left")
    if state.quote is None:
        table.add_row("조회 대기", "-", "-", "NOT STARTED", "-")
    else:
        rate_style = "green" if not state.quote.change_rate.startswith("-") else "red"
        table.add_row(state.quote.code, f"{state.quote.current_price:,}원", Text(state.quote.change_rate or "-", style=rate_style), "NOT STARTED", "-")
    return Panel(table, title="[bold]현재 감시 상태[/bold]", border_style="cyan")


def _signal_panel() -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="yellow")
    table.add_column(justify="right", style="white")
    for label in ("BUY SIGNAL", "SELL SIGNAL", "RISK BLOCK", "DUP ORDER BLOCK", "LOW CONFIDENCE", "INVALID PRICE"):
        table.add_row(label, "전략 미구현")
    return Panel(table, title="[bold]전략 / 신호 통계[/bold]", border_style="yellow")


def _trades_panel() -> Panel:
    table = Table(expand=True, box=None, header_style="bold cyan")
    for label in ("시간", "종목", "방향", "체결가", "수량", "손익", "상태"):
        table.add_column(label)
    table.add_row("-", "-", "-", "-", "-", "-", "거래 저장소 미연결")
    return Panel(table, title="[bold]최근 거래[/bold]", border_style="blue")


def _health_panel(state: DashboardState) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column()
    table.add_row("API", "[OK] 정상" if state.api_status == "정상" else "[ERROR] 오류")
    table.add_row("DB", "[WAIT] 미연결")
    table.add_row("Strategy", "[WAIT] NOT STARTED")
    table.add_row("Risk Manager", "[WAIT] NOT IMPLEMENTED")
    table.add_row("오늘 API 요청", str(state.api_requests))
    table.add_row("마지막 API 성공", state.last_api_success.strftime("%H:%M:%S") if state.last_api_success else "없음")
    if state.api_error:
        table.add_row("최근 오류", Text(state.api_error, style="red"))
    return Panel(table, title="[bold]시스템 상태[/bold]", border_style="red" if state.api_error else "green")


def render_dashboard(state: DashboardState) -> Layout:
    """DashboardState를 Rich 레이아웃으로 변환합니다. 네트워크 호출은 하지 않습니다."""

    layout = Layout(name="root")
    layout.split_column(Layout(name="header", size=5), Layout(name="body"), Layout(name="events", size=7))
    header = Text.assemble("KIWOOM AUTO TRADER", " " * 8, "[MOCK] TRADING ONLY\n", "모의 API 전용 · 주문 실행 기능 없음 · ", f"실행시간 {_uptime(state.started_at)} · {datetime.now():%Y-%m-%d %H:%M:%S}", style="bold white")
    layout["header"].update(Panel(Align.center(header), border_style="green"))
    layout["body"].split_row(Layout(name="left", ratio=1), Layout(name="right", ratio=2))
    layout["left"].split_column(Layout(_account_panel(state)), Layout(_signal_panel()))
    layout["right"].split_column(Layout(_watch_panel(state)), Layout(_trades_panel()), Layout(_health_panel(state)))
    events = "\n".join(state.events) if state.events else "[INFO] 첫 조회를 기다리는 중입니다."
    layout["events"].update(Panel(events, title="[bold]최근 이벤트[/bold]", border_style="blue"))
    return layout


def run_dashboard(provider: DashboardDataProvider, *, refresh_seconds: float, once: bool = False, console: Console | None = None) -> None:
    """같은 터미널 화면을 갱신합니다. Ctrl+C로 안전하게 종료할 수 있습니다."""

    output = console or Console()
    if once:
        output.print(render_dashboard(provider.refresh()))
        return
    with Live(render_dashboard(DashboardState()), console=output, refresh_per_second=4, screen=True) as live:
        while True:
            live.update(render_dashboard(provider.refresh()))
            # API 요청 빈도는 Live의 화면 갱신 횟수와 별개로 제한합니다.
            import time
            time.sleep(refresh_seconds)
