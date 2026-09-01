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
from app.news.monitor import NewsLevel, NewsMonitor, NewsSettings


@dataclass(frozen=True)
class AccountSnapshot:
    deposit: int | None = None
    estimated_assets: int | None = None
    total_purchase: int | None = None
    total_profit_loss: int | None = None
    holdings: tuple[Holding, ...] = ()


@dataclass(frozen=True)
class DashboardState:
    """화면이 필요로 하는 값만 담는 표시 전용 상태입니다."""

    account: AccountSnapshot = field(default_factory=AccountSnapshot)
    quote: Quote | None = None
    watch_rows: tuple["WatchRow", ...] = ()
    market_phase: str = "연결 대기"
    strategy_status: str = "대기"
    risk_status: str = "대기"
    daily_summary: str | None = None
    execution_mode: str = "DRY RUN(주문 전송 없음)"
    emergency_stop: bool = False
    last_market_data_at: datetime | None = None
    news_overview: str = "미설정"
    news_checked_at: datetime | None = None
    trades: tuple["TradeRow", ...] = ()
    api_status: str = "연결 대기"
    api_error: str | None = None
    api_requests: int = 0
    last_api_success: datetime | None = None
    started_at: float = field(default_factory=monotonic)
    events: tuple[str, ...] = ()


@dataclass(frozen=True)
class WatchRow:
    symbol: str
    completed_price: float | None
    status: str
    reason: str
    score: float = 0.0
    rsi: float | None = None
    current_price: int | None = None
    change_rate: str | None = None
    name: str = ""
    news_level: str = "미설정"
    news_reason: str = ""


@dataclass(frozen=True)
class TradeRow:
    timestamp: str
    symbol: str
    side: str
    price: float
    quantity: int
    realized_profit: int
    status: str


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
        self._cached_state = DashboardState(started_at=self._started_at)

    def close(self) -> None:
        self._client.close()

    def refresh(self, *, include_quote: bool = True) -> DashboardState:
        try:
            summary, holdings = AccountService(self._client).portfolio()
            self._api_requests += 1
            quote = None
            if include_quote:
                quote = MarketService(self._client).quote(self._stock_code)
                self._api_requests += 1
            self._last_success = datetime.now()
            source = f"{quote.code} 시세·잔고" if quote else "잔고"
            self._events.appendleft(f"[{self._last_success:%H:%M:%S}] INFO  {source} 갱신")
            self._cached_state = DashboardState(
                account=AccountSnapshot(
                    deposit=summary["deposit"],
                    estimated_assets=summary["estimated_assets"],
                    total_purchase=summary.get("total_purchase"),
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
            return self._cached_state
        except (KiwoomApiError, ValueError) as exc:
            now = datetime.now()
            self._events.appendleft(f"[{now:%H:%M:%S}] ERROR {exc}")
            self._cached_state = DashboardState(
                account=self._cached_state.account,
                quote=self._cached_state.quote,
                api_status="오류",
                api_error=str(exc),
                api_requests=self._api_requests,
                last_api_success=self._last_success,
                started_at=self._started_at,
                events=tuple(self._events),
            )
            return self._cached_state

    def cached_state(self) -> DashboardState:
        """장 마감 중에는 마지막 성공 상태를 다시 그리기만 하며 API를 호출하지 않습니다."""
        return self._cached_state

    def hydrate_account(self, summary: dict[str, int], holdings: list[Holding]) -> None:
        """복구 단계에서 이미 받은 잔고를 재사용해 동일 TR의 즉시 재호출을 막습니다."""
        now = datetime.now()
        self._last_success = now
        self._events.appendleft(f"[{now:%H:%M:%S}] INFO  복구 잔고 재사용 (추가 API 호출 없음)")
        self._cached_state = DashboardState(
            account=AccountSnapshot(
                deposit=summary["deposit"],
                estimated_assets=summary["estimated_assets"],
                total_purchase=summary.get("total_purchase"),
                total_profit_loss=summary["total_profit_loss"],
                holdings=tuple(holdings),
            ),
            api_status="정상",
            api_requests=self._api_requests,
            last_api_success=now,
            started_at=self._started_at,
            events=tuple(self._events),
        )

    def watch_quotes(self, symbols: tuple[str, ...], *, sleep_fn) -> dict[str, Quote]:
        """5종목 현재가를 공식 ka10001로 순차 조회합니다.

        같은 시세 TR을 초당 한 번보다 자주 호출하지 않도록 종목 사이에 대기합니다.
        일부 종목의 실패는 나머지 화면·전략을 멈추게 하지 않습니다.
        """
        market = MarketService(self._client)
        quotes: dict[str, Quote] = {}
        for index, symbol in enumerate(symbols):
            if index:
                sleep_fn(1.05)
            try:
                quotes[symbol] = market.quote(symbol)
                self._api_requests += 1
            except (KiwoomApiError, ValueError) as exc:
                self._events.appendleft(f"[{datetime.now():%H:%M:%S}] WARN  {symbol} 현재가 조회 실패: {exc}")
        return quotes


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
    invested = state.account.total_purchase
    if invested is None:
        invested = sum(holding.average_price * holding.quantity for holding in state.account.holdings)
    evaluated = sum(holding.evaluation_amount or holding.current_price * holding.quantity for holding in state.account.holdings)
    holding_profit = evaluated - invested
    return_rate = holding_profit / invested * 100 if invested else None
    table.add_row("주식 매입금", _money(invested))
    table.add_row("주식 평가금", _money(evaluated))
    table.add_row("보유 손익", _signed_money(holding_profit))
    table.add_row("보유 수익률", "계산 불가" if return_rate is None else f"{return_rate:+.2f}%")
    for holding in state.account.holdings:
        invested = holding.average_price * holding.quantity
        evaluated = holding.evaluation_amount or holding.current_price * holding.quantity
        profit = holding.profit_loss if holding.profit_loss else evaluated - invested
        return_rate = profit / invested * 100 if invested else None
        rate_text = "계산 불가" if return_rate is None else f"{return_rate:+.2f}%"
        table.add_row(f"{holding.name} ({holding.code.lstrip('A')})", f"{holding.quantity}주 · 매입 {invested:,}원 · 평가 {evaluated:,}원 · {profit:+,}원 ({rate_text})")
    return Panel(table, title="[bold]계좌 현황[/bold]", border_style="green")


def _watch_panel(state: DashboardState) -> Panel:
    table = Table(expand=True, box=None, header_style="bold cyan")
    for label in ("종목", "현재가", "등락률", "완료 15분봉", "전략 상태", "사유", "뉴스", "점수"):
        table.add_column(label, justify="right" if label in {"현재가", "등락률", "완료 15분봉", "점수"} else "left")
    if state.watch_rows:
        news_styles = {"양호": "green", "주의": "yellow", "위험": "bold red", "오류/지연": "bold red", "미설정": "grey62"}
        for row in state.watch_rows:
            status_style = "red" if row.status in {"ERROR", "RISK_BLOCKED", "STALE_DATA"} else "yellow" if row.status in {"BUY_SIGNAL", "PULLBACK"} else "white"
            current_price = "-" if row.current_price is None else f"{row.current_price:,}원"
            completed_price = "-" if row.completed_price is None else f"{row.completed_price:,.0f}원"
            reason = row.reason if len(row.reason) <= 28 else f"{row.reason[:27]}…"
            rate_style = "red" if (row.change_rate or "").startswith("-") else "green"
            symbol = f"{row.name} ({row.symbol})" if row.name else row.symbol
            table.add_row(symbol, current_price, Text(row.change_rate or "-", style=rate_style), completed_price, Text(row.status, style=status_style), reason, Text(row.news_level, style=news_styles.get(row.news_level, "white")), f"{row.score:.2f}" if row.score else "-")
    elif state.quote is None:
        table.add_row("조회 대기", "-", "-", "-", "NOT STARTED", "-", "-", "-")
    else:
        table.add_row(state.quote.code, f"{state.quote.current_price:,}원", state.quote.change_rate or "-", "-", "단일 시세 조회", "대시보드 모드", "-", "-")
    return Panel(table, title="[bold]5종목 감시 상태[/bold]", border_style="cyan")


def _signal_panel(state: DashboardState) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="yellow")
    table.add_column(justify="right", style="white")
    table.add_row("전략", state.strategy_status)
    table.add_row("시장", state.market_phase)
    table.add_row("위험관리", state.risk_status)
    table.add_row("긴급 정지", "[bold red]신규 매수 즉시 중단[/bold red]" if state.emergency_stop else "꺼짐")
    table.add_row("시장 데이터", state.last_market_data_at.strftime("%H:%M:%S 정상 수신") if state.last_market_data_at else "대기")
    news_style = {"양호": "green", "주의": "yellow", "위험": "bold red", "오류/지연": "bold red", "미설정": "grey62"}.get(state.news_overview, "white")
    table.add_row("뉴스 위험", Text(state.news_overview, style=news_style))
    table.add_row("뉴스 갱신", state.news_checked_at.strftime("%H:%M:%S") if state.news_checked_at else "미설정")
    table.add_row("주문 전송", state.execution_mode)
    if state.daily_summary:
        table.add_row("오늘 결과", state.daily_summary)
    return Panel(table, title="[bold]전략 / 신호 통계[/bold]", border_style="red" if state.emergency_stop else "yellow")


def _trades_panel(state: DashboardState) -> Panel:
    table = Table(expand=True, box=None, header_style="bold cyan")
    for label in ("시간", "종목", "방향", "체결가", "수량", "손익", "상태"):
        table.add_column(label)
    if state.trades:
        for row in state.trades:
            table.add_row(row.timestamp[11:19], row.symbol, row.side, f"{row.price:,.0f}원", str(row.quantity), f"{row.realized_profit:+,}원", row.status)
    else:
        table.add_row("-", "-", "-", "-", "-", "-", "체결 기록 없음")
    return Panel(table, title="[bold]최근 거래[/bold]", border_style="blue")


def _health_panel(state: DashboardState) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column()
    table.add_row("API", "[OK] 정상" if state.api_status == "정상" else "[ERROR] 오류")
    table.add_row("DB", "[OK] 신호 기록 연결")
    table.add_row("Strategy", state.strategy_status)
    table.add_row("Risk Manager", state.risk_status)
    table.add_row("오늘 API 요청", str(state.api_requests))
    table.add_row("마지막 API 성공", state.last_api_success.strftime("%H:%M:%S") if state.last_api_success else "없음")
    if state.api_error:
        table.add_row("최근 오류", Text(state.api_error, style="red"))
    return Panel(table, title="[bold]시스템 상태[/bold]", border_style="red" if state.api_error else "green")


def render_dashboard(state: DashboardState) -> Layout:
    """DashboardState를 Rich 레이아웃으로 변환합니다. 네트워크 호출은 하지 않습니다."""

    layout = Layout(name="root")
    layout.split_column(Layout(name="header", size=5), Layout(name="body"), Layout(name="events", size=7))
    header = Text.assemble("KIWOOM AUTO TRADER", " " * 8, "[MOCK] TRADING ONLY\n", "모의 API 전용 · ", state.execution_mode, " · ", f"실행시간 {_uptime(state.started_at)} · {datetime.now():%Y-%m-%d %H:%M:%S}", style="bold white")
    layout["header"].update(Panel(Align.center(header), border_style="green"))
    layout["body"].split_row(Layout(name="left", ratio=1), Layout(name="right", ratio=2))
    layout["left"].split_column(Layout(_account_panel(state)), Layout(_signal_panel(state)))
    layout["right"].split_column(Layout(_watch_panel(state)), Layout(_trades_panel(state)), Layout(_health_panel(state)))
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


def run_auto_dashboard(settings: Settings, *, interval_seconds: float, console: Console | None = None, order_service=None, once: bool = False) -> None:
    """5종목 전략과 관제 화면을 한 프로세스로 실행합니다. 기본값은 주문 없는 DRY RUN입니다."""
    from app.storage.sqlite import TradingStore
    from app.strategy.runner import DryRunStrategyRunner
    from app.strategy.settings import TradingSettings
    import time
    output = console or Console()
    provider = DashboardDataProvider(settings, "005930")
    store = TradingStore()
    trading_settings = TradingSettings.load()
    runner = DryRunStrategyRunner(MarketService(provider._client), trading_settings, store, order_service=order_service)
    news_monitor = NewsMonitor(NewsSettings.load())
    try:
        summary, holdings = runner.restore_from_account()
        # restore_from_account의 kt00004 결과를 그대로 써서 장외 시작 직후 429를 막습니다.
        provider.hydrate_account(summary, holdings)
        def refresh_cycle() -> DashboardState:
            results = runner.run_once()
            label = "MOCK AUTO" if order_service else "DRY RUN"
            event_rows = [f"[{datetime.now():%H:%M:%S}] {label}  {result.symbol} {result.decision.status} · {result.decision.reason}" for result in results]
            phase = results[0].market_phase if results else "CLOSED"
            quotes = provider.watch_quotes(tuple(result.symbol for result in results), sleep_fn=time.sleep) if phase != "CLOSED" else {}
            news_states = news_monitor.refresh(tuple(result.symbol for result in results))
            state = provider.cached_state() if phase == "CLOSED" and provider.cached_state().last_api_success else provider.refresh(include_quote=False)
            day_summary = store.daily_summary(datetime.now().strftime("%Y-%m-%d"))
            daily = f"신호 {day_summary.signals} · 차단 {day_summary.blocked} · 실현 {day_summary.realized_profit:,}원"
            mode = "모의 자동주문 활성 · 체결 확인 후 상태 반영" if order_service else "DRY RUN(주문 전송 없음)"
            trades = tuple(TradeRow(item.timestamp, item.symbol, item.side, item.price, item.quantity, item.realized_profit, item.status) for item in store.recent_trades())
            risk_status = "긴급 정지: 신규 매수 차단" if runner.settings.emergency_stop else "정상 (매수 제한 적용)"
            levels = [item.level for item in news_states.values()]
            news_overview = "위험" if NewsLevel.RISK in levels else "주의" if NewsLevel.CAUTION in levels else "오류/지연" if NewsLevel.UNAVAILABLE in levels else "양호" if NewsLevel.GOOD in levels else "미설정"
            checked = max((item.checked_at for item in news_states.values() if item.checked_at), default=None)
            return DashboardState(account=state.account, api_status=state.api_status, api_error=state.api_error, api_requests=state.api_requests, last_api_success=state.last_api_success, started_at=state.started_at, watch_rows=tuple(WatchRow(result.symbol, result.completed_bar_price, str(result.decision.status), result.decision.reason, result.decision.score, result.decision.rsi, quotes.get(result.symbol).current_price if result.symbol in quotes else None, quotes.get(result.symbol).change_rate if result.symbol in quotes else None, quotes.get(result.symbol).name if result.symbol in quotes else "", str(news_states[result.symbol].level), news_states[result.symbol].reason) for result in results), market_phase=phase, strategy_status="정상 분석" if phase != "CLOSED" else "장 마감 대기", risk_status=risk_status, daily_summary=daily, execution_mode=mode, emergency_stop=runner.settings.emergency_stop, last_market_data_at=runner.last_market_data_at, news_overview=news_overview, news_checked_at=checked, trades=trades, events=tuple(event_rows[-5:]))
        if once:
            output.print(render_dashboard(refresh_cycle()))
            return
        with Live(render_dashboard(DashboardState()), console=output, refresh_per_second=4, screen=True) as live:
            while True:
                state = refresh_cycle()
                live.update(render_dashboard(state))
                time.sleep(interval_seconds)
    finally:
        news_monitor.close(); store.close(); provider.close()
