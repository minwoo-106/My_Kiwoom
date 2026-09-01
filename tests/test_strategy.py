from app.risk.manager import RiskManager
from app.strategy.core import Candle, StrategyStatus, SymbolState, TrendPullbackV1
from app.strategy.runner import DryRunStrategyRunner
from app.storage.sqlite import TradingStore
from app.market_hours import KST, market_phase
from datetime import datetime, timezone
from pathlib import Path


class _FillClient:
    def post(self, *, path, tr_id, body):
        assert path == "/api/dostk/acnt"
        assert tr_id == "ka10076"
        return {"cntr": [{"ord_no": "mock-1", "stk_cd": "005930", "trde_tp": "매수", "ord_qty": "1", "cntr_qty": "1", "oso_qty": "0", "cntr_pric": "70000", "ord_stt": "체결", "ord_tm": "091500"}]}


class _StableMarket:
    client = _FillClient()

    def completed_15m_candles(self, symbol):
        return [Candle(str(index), 100 + index, 101 + index, 99 + index, 100 + index) for index in range(61)]
from app.strategy.settings import DEFAULT_WATCHLIST, TradingSettings
from app.kiwoom.market import MarketService

def test_default_watchlist_has_five_symbols(): assert len(DEFAULT_WATCHLIST) == 5
def test_risk_blocks_existing_holding():
    assert RiskManager().buy_block_reason(SymbolState("005930", holding=True), open_positions=0, daily_entries=0, consecutive_losses=0, daily_loss_pct=0, api_ok=True, market_open=True) == "ALREADY_HOLDING"
def test_same_completed_bar_is_not_processed_twice():
    candles=[Candle(str(i), 100+i, 101+i, 99+i, 100+i) for i in range(61)]
    state=SymbolState("005930"); strategy=TrendPullbackV1()
    strategy.evaluate(candles,state)
    assert strategy.evaluate(candles,state).reason == "동일 완료 봉 재처리 차단"

def test_restored_holding_without_protection_stays_safe():
    candles=[Candle(str(i), 100+i, 101+i, 99+i, 100+i) for i in range(61)]
    decision = TrendPullbackV1().evaluate(candles, SymbolState("005930", holding=True, average_price=100, quantity=1))
    assert decision.status == StrategyStatus.HOLD
    assert decision.signal is None

def test_configured_holiday_is_never_a_market_open_day():
    holiday = datetime(2026, 10, 9, 10, 0, tzinfo=KST)
    assert market_phase(holiday, holidays=frozenset({holiday.date()})) == "CLOSED"

def test_store_calculates_entries_and_consecutive_losses(tmp_path: Path):
    store = TradingStore(tmp_path / "test.sqlite3")
    try:
        store.record_trade(timestamp="2026-08-31T09:00:00", symbol="005930", side="BUY", price=100, quantity=1, realized_profit=0)
        store.record_trade(timestamp="2026-08-31T10:00:00", symbol="005930", side="SELL", price=90, quantity=1, realized_profit=-10)
        store.record_trade(timestamp="2026-08-31T11:00:00", symbol="000660", side="SELL", price=90, quantity=1, realized_profit=-10)
        assert store.today_entries("2026-08-31") == 1
        assert store.today_realized_profit("2026-08-31") == -20
        assert store.consecutive_losses() == 2
    finally:
        store.close()


def test_reconcile_filled_mock_order_updates_position_and_journal(tmp_path: Path):
    store = TradingStore(tmp_path / "test.sqlite3")
    try:
        store.record_order(order_number="mock-1", timestamp="2026-08-31T09:00:00", symbol="005930", side="BUY", quantity=1, stop_price=69_000, target_price=72_000)
        runner = DryRunStrategyRunner(MarketService(_FillClient()), TradingSettings(), store)
        runner.reconcile_orders()
        state = runner.states["005930"]
        assert state.holding and state.average_price == 70_000
        assert state.stop_price == 69_000
        assert store.pending_orders() == []
        assert store.today_entries(datetime.now().strftime("%Y-%m-%d")) == 1
    finally:
        store.close()


def test_runner_resets_per_symbol_daily_entry_counter_on_new_day(tmp_path: Path):
    store = TradingStore(tmp_path / "test.sqlite3")
    try:
        runner = DryRunStrategyRunner(MarketService(_FillClient()), TradingSettings(), store)
        runner.states["005930"].entries_today = 1
        runner._trading_date = datetime(2026, 8, 30).date()
        # 장 마감이면 네트워크 분석 없이 날짜 롤오버만 검증할 수 있습니다.
        runner.run_once()
        assert runner.states["005930"].entries_today == 0
    finally:
        store.close()


def test_dry_run_stays_stable_for_many_cycles_without_order_service(tmp_path: Path):
    """장시간 테스트 축소판: 5종목 × 200회에도 주문 경로 없이 안정적으로 반복된다."""
    store = TradingStore(tmp_path / "stability.sqlite3")
    try:
        runner = DryRunStrategyRunner(_StableMarket(), TradingSettings(), store, phase_provider=lambda: "OPEN", sleep_fn=lambda _: None)
        for _ in range(200):
            results = runner.run_once()
            assert len(results) == 5
        assert store.daily_summary(datetime.now().strftime("%Y-%m-%d")).buys == 0
        assert store.pending_orders() == []
    finally:
        store.close()


def test_signal_record_marks_when_mock_auto_executor_is_attached(tmp_path: Path):
    class _Executor:
        pass
    store = TradingStore(tmp_path / "signal.sqlite3")
    try:
        runner = DryRunStrategyRunner(_StableMarket(), TradingSettings(), store, order_service=_Executor(), phase_provider=lambda: "OPEN", sleep_fn=lambda _: None)
        runner.run_once()
        value = store.connection.execute("SELECT mock_order_enabled FROM signals LIMIT 1").fetchone()[0]
        assert value == 1
    finally:
        store.close()
